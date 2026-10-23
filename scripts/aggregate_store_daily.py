#!/usr/bin/env python3
"""Aggregate product-day facts into store-day facts safely.

The command is read-only by default. ``--apply`` requires an integrity-checked
SQLite online backup before any store summary row is changed.

Anchor semantics (2026-10-23)
-----------------------------
The aggregation window is anchored on the **latest date present in
``daily_data``**, not on the wall clock (``date('now')``).  The previous
wall-clock anchor made the result non-reproducible: a business date silently
fell out of the look-back window a few days later, after which

* a backfill of that date could never be aggregated again, and
* ``--skip-if-current`` compared empty source against empty target, so it
  reported "already in sync" and skipped the very run that was needed.

``--as-of`` pins the anchor explicitly, and ``--dates`` names exact business
dates to aggregate (the backfill path).  Both paths use the *same* filter
builder as :func:`is_current`, so the written rows and the sync check can never
disagree about which days they cover.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
# 确保项目根目录在 sys.path 中，以便导入 scripts 包
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DEFAULT_DB = Path(os.environ.get('TMALL_DB_PATH', PROJECT_ROOT / 'data' / 'dashboard.db'))
DEFAULT_LOOKBACK_DAYS = 14

# 源侧聚合表达式：写入与「是否已同步」判定必须用同一段 SQL，否则两边口径漂移
# 会导致 --skip-if-current 永远认为不一致（或更糟：认为一致而漏更新）。
# {date_filter} 由 _date_filter() 统一生成，两条路径共用。
AGGREGATE_SOURCE_SQL = '''
    SELECT shop_id, date,
           ROUND(SUM(payment_amount), 2) AS sales,
           ROUND(SUM(refund_amount), 2) AS refund,
           ROUND(SUM(ipv), 0) AS visitors,
           ROUND(SUM(buyers), 0) AS buyers,
           ROUND(SUM(returning_payment_buyers), 0) AS returning_buyers,
           ROUND(SUM(ad_spend), 2) AS ad_spend
    FROM daily_data
    WHERE {date_filter}
    GROUP BY shop_id, date
    ORDER BY shop_id, date
'''

# 金额字段容差 0.01（ROUND 到分），计数字段容差 0.5（ROUND 到整数）。
# 用容差而非精确相等：SUM 的浮点累加顺序不同会带来 ULP 级差异。
_MONEY_KEYS = ('payment_amount', 'successful_refund_amount', 'ad_spend')
_COUNT_KEYS = ('product_visitors', 'payment_buyers', 'returning_payment_buyers')
_FACT_COLUMNS = ('payment_amount', 'successful_refund_amount', 'product_visitors',
                 'payment_buyers', 'returning_payment_buyers', 'ad_spend')


def _date_filter(lookback_days, dates=None, anchor=None):
    """Build the shared ``daily_data`` date predicate plus its parameters.

    Returns ``(sql_fragment, params)``.  ``dates`` (a non-empty list of
    ``YYYY-MM-DD``) wins over the window; otherwise the window covers
    ``anchor - (lookback_days - 1) .. anchor``.
    """
    if dates:
        placeholders = ', '.join('?' for _ in dates)
        return f'date IN ({placeholders})', list(dates)
    if anchor is None:
        # 源表为空：不匹配任何行，由调用方判定「无可聚合数据」。
        return '0', []
    start = (dt.date.fromisoformat(anchor) - dt.timedelta(days=lookback_days - 1)).isoformat()
    return 'date >= ? AND date <= ?', [start, anchor]


def resolve_anchor(connection, as_of=None):
    """Return the aggregation anchor date.

    Explicit ``as_of`` wins; otherwise anchor on the newest ``daily_data`` date.
    Anchoring on the data (not on ``date('now')``) keeps reruns reproducible.
    """
    if as_of:
        return as_of
    # 按序号取值而不是按列名：否则本函数会静默要求调用方先设 row_factory，
    # 直接传普通连接时会抛 "tuple indices must be integers"（2026-10-23 修）。
    row = connection.execute('SELECT MAX(date) FROM daily_data').fetchone()
    latest = row[0] if row is not None else None
    return str(latest)[:10] if latest else None


def is_current(connection, lookback_days, dates=None, anchor=None):
    """判断 store_daily_facts 是否已与 daily_data 在回看窗口内一致。

    一致 => 无需重新聚合（也无需付出一份全量备份的代价）。只比较回看窗口
    内的行；窗口外的历史不参与判断。窗口锚点是数据最新日期（见模块说明），
    因此「同一份数据重跑几次」结论恒定。
    """
    resolved = anchor if (dates or anchor) else resolve_anchor(connection)
    date_filter, params = _date_filter(lookback_days, dates=dates, anchor=resolved)

    # 本函数按列名取值。显式设置 row_factory，而不是静默要求调用方先设好：
    # 否则传入普通连接会抛 "tuple indices must be integers"（2026-10-23 修）。
    connection.row_factory = sqlite3.Row

    source = {}
    for row in connection.execute(
        AGGREGATE_SOURCE_SQL.format(date_filter=date_filter), params
    ):
        source[(row['shop_id'], row['date'])] = (
            row['sales'], row['refund'] or 0, row['visitors'],
            row['buyers'], row['returning_buyers'], row['ad_spend'] or 0)

    stored = {}
    for row in connection.execute(
        f'''SELECT shop_id, date, {', '.join(_FACT_COLUMNS)}
            FROM store_daily_facts
            WHERE {date_filter}''', params
    ):
        stored[(row['shop_id'], row['date'])] = tuple(
            row[column] for column in _FACT_COLUMNS)

    if set(source) != set(stored):
        return False

    for key, wanted in source.items():
        actual = stored[key]
        for index, column in enumerate(_FACT_COLUMNS):
            left, right = wanted[index], actual[index]
            if left is None and right is None:
                continue
            tolerance = 0.01 if column in _MONEY_KEYS else 0.5
            if left is None or right is None or abs(left - right) > tolerance:
                return False
    return True


def _parse_dates(raw):
    dates = []
    for chunk in raw:
        for part in str(chunk).split(','):
            part = part.strip()
            if not part:
                continue
            try:
                dates.append(dt.date.fromisoformat(part).isoformat())
            except ValueError:
                raise argparse.ArgumentTypeError(f'无效日期（需 YYYY-MM-DD）: {part}')
    # 去重保序
    seen, ordered = set(), []
    for day in dates:
        if day not in seen:
            seen.add(day)
            ordered.append(day)
    return ordered


def main(argv=None):
    parser = argparse.ArgumentParser(description='Aggregate daily product facts into store daily facts.')
    parser.add_argument('--db', default=str(DEFAULT_DB))
    parser.add_argument('--lookback-days', type=int, default=DEFAULT_LOOKBACK_DAYS)
    parser.add_argument('--apply', action='store_true', help='Persist changes; default is preview only.')
    parser.add_argument('--backup-destination', help='Required with --apply: integrity-checked SQLite backup path')
    parser.add_argument('--skip-if-current', action='store_true',
                        help='Skip backup and writes when store_daily_facts already matches '
                             'daily_data inside the lookback window (idempotent schedulers)')
    parser.add_argument('--as-of', default=None,
                        help='锚点日期 YYYY-MM-DD，默认取 daily_data 的最新日期（不再用墙钟今天）')
    parser.add_argument('--dates', action='append', default=None, metavar='D1,D2',
                        help='只聚合这些业务日期（补采/回填用），与 --as-of 互斥')
    parser.add_argument('--allow-missing-dates', action='store_true',
                        help='--dates 中某些日期在 daily_data 无数据时仍然成功（默认判失败）')
    args = parser.parse_args(argv)
    if args.apply and not args.backup_destination:
        parser.error('--backup-destination is required with --apply')
    if args.lookback_days < 1:
        parser.error('--lookback-days must be positive')

    try:
        requested_dates = _parse_dates(args.dates) if args.dates else None
    except argparse.ArgumentTypeError as exc:
        parser.error(str(exc))
    if requested_dates and args.as_of:
        parser.error('--dates 与 --as-of 不能同时使用')
    if args.as_of:
        try:
            args.as_of = dt.date.fromisoformat(str(args.as_of).strip()).isoformat()
        except ValueError:
            parser.error('--as-of 必须为 YYYY-MM-DD')

    db_path = Path(args.db).resolve()
    if not db_path.exists():
        print(json.dumps({'mode': 'error', 'database': str(db_path),
                          'error': 'database_not_found'}, ensure_ascii=False, indent=2))
        return 2

    # 2026-10-02：聚合现在有两个入口（auto-collect.ps1 [5b] 与独立的
    # TmallDashboard-Aggregate-Daily 计划任务）。先跑的一方真正聚合，后跑的一方
    # 在这里直接跳过——否则每天会白白产生两份全量备份。
    #
    # 2026-10-23：跳过判定之前先做口径校验。请求了 --dates 但源侧根本没有这些日期
    # 时，静默「无可写行」正是 10-22 那次 store_daily_facts 缺天的成因。
    #
    # 2026-10-23：probe 必须以**只读**方式打开。它只做「锚点/源日期/是否已同步」三类
    # 查询，却曾用可写连接——一次 --dry-run 预览就会在 close 时触发 WAL checkpoint，
    # 改写生产库主文件。预览不得改动生产数据，故改用 mode=ro URI。
    probe = sqlite3.connect(f'file:{db_path.as_posix()}?mode=ro', uri=True, timeout=300)
    probe.row_factory = sqlite3.Row
    probe.execute('PRAGMA busy_timeout=300000')
    probe.execute('PRAGMA temp_store=MEMORY')
    try:
        anchor = resolve_anchor(probe, args.as_of)

        source_dates = None
        missing_dates = []
        if requested_dates:
            placeholders = ', '.join('?' for _ in requested_dates)
            present = {str(row['date'])[:10] for row in probe.execute(
                f'SELECT DISTINCT date FROM daily_data WHERE date IN ({placeholders})',
                requested_dates)}
            source_dates = sorted(present)
            missing_dates = [day for day in requested_dates if day not in present]
        elif anchor:
            date_filter, params = _date_filter(args.lookback_days, anchor=anchor)
            source_dates = [str(row['date'])[:10] for row in probe.execute(
                f'SELECT DISTINCT date FROM daily_data WHERE {date_filter}', params)]

        if missing_dates and not args.allow_missing_dates:
            print(json.dumps({
                'mode': 'failed',
                'database': str(db_path),
                'error': 'requested_dates_missing_in_source',
                'requested_dates': requested_dates,
                'missing_dates': missing_dates,
                'present_dates': source_dates,
            }, ensure_ascii=False, indent=2))
            return 3

        if args.skip_if_current and is_current(
                probe, args.lookback_days, dates=requested_dates, anchor=anchor):
            print(json.dumps({
                'mode': 'skipped',
                'database': str(db_path),
                'lookback_days': args.lookback_days,
                'anchor': anchor,
                'reason': 'store_daily_facts 已与 daily_data 一致，跳过备份与写入',
                'backup': None,
            }, ensure_ascii=False, indent=2))
            return 0
    finally:
        probe.close()

    backup = None
    if args.apply:
        from scripts.backup_database import backup_database

        backup = backup_database(db_path, args.backup_destination)
        if not backup['ok']:
            raise RuntimeError('database backup integrity check failed')

    date_filter, params = _date_filter(
        args.lookback_days, dates=requested_dates, anchor=anchor)

    connection = sqlite3.connect(db_path, timeout=300)
    connection.row_factory = sqlite3.Row
    connection.execute('PRAGMA busy_timeout=300000')
    try:
        rows = connection.execute(
            AGGREGATE_SOURCE_SQL.format(date_filter=date_filter), params
        ).fetchall()

        inserted = 0
        updated = 0
        for row in rows:
            existing = connection.execute(
                'SELECT 1 FROM store_daily_facts WHERE shop_id=? AND date=?',
                (row['shop_id'], row['date']),
            ).fetchone()
            if existing:
                updated += 1
                if args.apply:
                    connection.execute(
                        '''UPDATE store_daily_facts SET
                               payment_amount=?, successful_refund_amount=?, product_visitors=?,
                               payment_buyers=?, returning_payment_buyers=?, ad_spend=?
                           WHERE shop_id=? AND date=?''',
                        (row['sales'], row['refund'] or 0, row['visitors'], row['buyers'],
                         row['returning_buyers'], row['ad_spend'], row['shop_id'], row['date']),
                    )
            else:
                inserted += 1
                if args.apply:
                    connection.execute(
                        '''INSERT INTO store_daily_facts
                           (shop_id, date, payment_amount, successful_refund_amount,
                            product_visitors, payment_buyers, returning_payment_buyers, ad_spend)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                        (row['shop_id'], row['date'], row['sales'], row['refund'] or 0,
                         row['visitors'], row['buyers'], row['returning_buyers'], row['ad_spend']),
                    )

        if args.apply:
            connection.commit()
        else:
            connection.rollback()

        latest = connection.execute(
            '''SELECT date, payment_amount, product_visitors, payment_buyers, ad_spend
               FROM store_daily_facts ORDER BY date DESC LIMIT 5'''
        ).fetchall()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

    print(json.dumps({
        'mode': 'apply' if args.apply else 'dry-run',
        'database': str(db_path),
        'lookback_days': args.lookback_days,
        'anchor': anchor,
        'requested_dates': requested_dates,
        'source_dates': source_dates,
        'source_group_count': len(rows),
        'would_insert': inserted,
        'would_update': updated,
        'backup': backup,
        'latest': [dict(row) for row in latest],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
