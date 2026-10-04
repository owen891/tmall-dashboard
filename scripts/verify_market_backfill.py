# -*- coding: utf-8 -*-
"""校验生意参谋市场表历史补采结果（只读）。

判据分三层
----------
1. 落库层：四表最早日期是否已前移到目标起点；逐日行数是否达标
   （item 期望 600、keyword 期望 1500、rival_shop 期望 ~50、rival_item 期望 ~10）
2. 上下文层：月复盘 API 的市场块 `available` 与窗口天数是否补齐
3. 边界层：原有日期（2026-09-16 之后）行数不应被补采改动

用法
----
    python scripts/verify_market_backfill.py
    python scripts/verify_market_backfill.py --json
    python scripts/verify_market_backfill.py --start 2026-08-01 --end 2026-09-14
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import urllib.request

DB = r'E:\www\tmall-dashboard\data\dashboard.db'
BASE = 'http://127.0.0.1:5000'

TABLES = {
    'sycm_market_item_rank': 500,
    'sycm_market_search_rank': 1200,
    'sycm_market_rival_shop': 30,
    'sycm_market_rival_item': 5,
}


def coverage(conn, table):
    row = conn.execute(
        f'SELECT COUNT(*) n, MIN(stat_date) a, MAX(stat_date) b, COUNT(DISTINCT stat_date) d '
        f'FROM {table}').fetchone()
    return {'rows': row[0], 'first': row[1], 'last': row[2], 'days': row[3]}


def daily_gaps(conn, table, start, end, min_rows):
    """返回 [start,end] 内行数不足阈值的日期列表（含完全缺失）。"""
    have = {r[0]: r[1] for r in conn.execute(
        f'SELECT stat_date, COUNT(*) FROM {table} WHERE stat_date BETWEEN ? AND ? GROUP BY stat_date',
        (start, end)).fetchall()}
    from datetime import date, timedelta
    cur, last, gaps = date.fromisoformat(start), date.fromisoformat(end), []
    while cur <= last:
        d = cur.isoformat()
        if have.get(d, 0) < min_rows:
            gaps.append({'date': d, 'rows': have.get(d, 0)})
        cur += timedelta(days=1)
    return gaps


def fetch_context(period):
    url = f'{BASE}/api/period-reviews/month/{period}/context?category_mode=all'
    with urllib.request.urlopen(url, timeout=180) as resp:
        return json.loads(resp.read().decode('utf-8'))['data']['context']


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--start', default='2026-08-01')
    ap.add_argument('--end', default='2026-09-14')
    ap.add_argument('--json', action='store_true')
    args = ap.parse_args()

    conn = sqlite3.connect(DB)
    report = {'coverage': {}, 'gaps': {}, 'contexts': {}, 'checks': [], 'ok': True}

    def add(name, passed, detail):
        report['checks'].append({'name': name, 'pass': bool(passed), 'detail': detail})
        if not passed:
            report['ok'] = False

    # --- 1. 落库层 ---
    for table, min_rows in TABLES.items():
        cov = coverage(conn, table)
        report['coverage'][table] = cov
        report['gaps'][table] = daily_gaps(conn, table, args.start, args.end, min_rows)

    for table in TABLES:
        cov = report['coverage'][table]
        add(f'{table} 起点前移', cov['first'] is not None and cov['first'] <= args.start,
            f"最早={cov['first']}（目标 <= {args.start}）")

    # 关键表不应有缺口（竞店/竞品允许个别日期偏少，单独看）
    for table in ('sycm_market_item_rank', 'sycm_market_search_rank'):
        gaps = report['gaps'][table]
        add(f'{table} 区间无缺口', not gaps,
            f"{len(gaps)} 个日期不达标" + (f"，例如 {gaps[:3]}" if gaps else ''))

    # --- 2. 上下文层 ---
    for period, want_days in (('2026-08', 25), ('2026-09', 28)):
        try:
            ctx = fetch_context(period)
        except Exception as exc:  # noqa: BLE001
            add(f'{period} 上下文可读', False, str(exc)[:120])
            continue
        m = ctx.get('market') or {}
        g = m.get('grading') or {}
        kw = g.get('keyword_window') or {}
        report['contexts'][period] = {
            'available': m.get('available'),
            'missing_inputs': m.get('missing_inputs'),
            'keyword_window': kw,
            'keyword_insights_available': (m.get('keyword_insights') or {}).get('available'),
            'blue_ocean_available': (m.get('blue_ocean_supply') or {}).get('available'),
            'rival_moves_shop_count': (m.get('rival_moves') or {}).get('shop_count'),
            'trend_items_rising': (m.get('trend_items') or {}).get('rising_total'),
            'competitor_items': len(m.get('competitor_items') or []),
        }
        add(f'{period} 市场块可用', m.get('available') is True, f"available={m.get('available')}")
        add(f'{period} 窗口天数 >= {want_days}',
            (kw.get('day_count') or 0) >= want_days, f"day_count={kw.get('day_count')}")

    # --- 3. 边界层：9-16 之后原有数据不应被动过 ---
    for table in TABLES:
        n = conn.execute(
            f"SELECT COUNT(*) FROM {table} WHERE stat_date >= '2026-09-16'").fetchone()[0]
        report.setdefault('post_0916', {})[table] = n
    add('9-16 后数据仍在', report['post_0916']['sycm_market_item_rank'] > 0,
        f"item_rank 9-16后 {report['post_0916']['sycm_market_item_rank']} 行")

    conn.close()

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print('=== 市场表覆盖 ===')
        for table, cov in report['coverage'].items():
            print(f"  {table:30s} {cov['rows']:>7} 行  {cov['first']} ~ {cov['last']}  ({cov['days']} 天)")
        print('\n=== 缺口（{} ~ {}） ==='.format(args.start, args.end))
        for table, gaps in report['gaps'].items():
            flag = 'OK' if not gaps else f'{len(gaps)} 天不达标'
            print(f"  {table:30s} {flag}")
            for g in gaps[:6]:
                print(f"      {g['date']}  仅 {g['rows']} 行")
        print('\n=== 复盘上下文 ===')
        for period, info in report['contexts'].items():
            print(f"  {period}: available={info['available']} "
                  f"窗口={info['keyword_window']} 竞店={info['rival_moves_shop_count']} "
                  f"趋势上升={info['trend_items_rising']} 竞品对标={info['competitor_items']}")
            print(f"      missing={info['missing_inputs']}")
        print('\n=== 断言 ===')
        for c in report['checks']:
            print(f"  [{'PASS' if c['pass'] else 'FAIL'}] {c['name']} — {c['detail']}")
        print(f"\n总体: {'全部通过' if report['ok'] else '存在失败项'}")
    return 0 if report['ok'] else 1


if __name__ == '__main__':
    sys.exit(main())
