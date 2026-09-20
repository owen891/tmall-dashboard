"""临时诊断脚本：检查采集数据是否存在异常（空分区、日期错位、数值异常）。

用法: .venv\\Scripts\\python.exe scripts\\diag_collect_data.py
"""
import sqlite3
import sys
from pathlib import Path

DB_PATH = sys.argv[1] if len(sys.argv) > 1 else str(Path(__file__).resolve().parents[1] / 'data' / 'dashboard.db')

FACT_TABLES = {
    'daily_data': 'date',
    'monthly_data': 'month',
    'sycm_flow_source_daily': 'stat_date',
    'sycm_item_flow_source_daily': 'stat_date',
    'sycm_market_item_rank': 'stat_date',
    'promotion_daily_facts': 'date',
}


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    print('=' * 70)
    print(f'数据库: {DB_PATH}')
    print('=' * 70)

    # 1. 最近的采集运行记录
    print('\n[1] 最近 20 条采集运行记录 (collector_runs)')
    try:
        rows = cur.execute(
            '''SELECT id, source_key, status, mode, attempt, error_code,
                      created_at, finished_at, substr(coalesce(error_message,''),1,80) AS err
               FROM collector_runs ORDER BY created_at DESC LIMIT 20'''
        ).fetchall()
        if not rows:
            print('  (无记录)')
        for r in rows:
            print(f"  {r['created_at']} | {r['source_key']:<16} | {r['status']:<10} | {r['mode'] or '-':<6} | "
                  f"try{r['attempt'] or 1} | {r['error_code'] or '-'} | {r['err']}")
    except sqlite3.OperationalError as exc:
        print(f'  [跳过] {exc}')

    # 2. 各事实表按日期的行数分布（最近 14 个日期）
    print('\n[2] 各事实表最近日期分布')
    for table, date_col in FACT_TABLES.items():
        try:
            exists = cur.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
            ).fetchone()
            if not exists:
                print(f'  {table:<30} 表不存在')
                continue
            total = cur.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
            latest = cur.execute(f'SELECT MAX({date_col}) FROM {table}').fetchone()[0]
            print(f'\n  {table}  (总行数={total}, 最新={latest})')
            rows = cur.execute(
                f'SELECT {date_col} AS d, COUNT(*) AS c FROM {table} '
                f'GROUP BY {date_col} ORDER BY {date_col} DESC LIMIT 14'
            ).fetchall()
            for r in rows:
                print(f"      {r['d']}  ->  {r['c']} 行")
        except sqlite3.OperationalError as exc:
            print(f'  {table:<30} 查询失败: {exc}')

    # 3. 每日汇总（daily_data）核心指标
    print('\n[3] daily_data 最近 14 天核心指标合计')
    try:
        cols = [r['name'] for r in cur.execute('PRAGMA table_info(daily_data)').fetchall()]
        print(f"  可用列: {', '.join(cols)}")
        numeric = [c for c in cols if c not in
                   {'date', 'product_id', 'product_name', 'shop_id', 'id', 'category', 'shop_name'}]
        sum_expr = ', '.join(f'SUM("{c}") AS "{c}"' for c in numeric[:12]) if numeric else 'COUNT(*) AS c'
        rows = cur.execute(
            f'SELECT date, COUNT(*) AS rows_cnt, {sum_expr} FROM daily_data '
            f'GROUP BY date ORDER BY date DESC LIMIT 14'
        ).fetchall()
        for r in rows:
            vals = {k: r[k] for k in r.keys() if k not in ('date', 'rows_cnt')}
            print(f"  {r['date']} rows={r['rows_cnt']} | {vals}")
    except sqlite3.OperationalError as exc:
        print(f'  [跳过] {exc}')

    # 4. staging 快照
    print('\n[4] 最近 staging 批次')
    try:
        rows = cur.execute(
            '''SELECT batch_id, status, COUNT(*) AS c FROM collector_data_staging
               GROUP BY batch_id, status ORDER BY batch_id DESC LIMIT 10'''
        ).fetchall()
        if not rows:
            print('  (无记录)')
        for r in rows:
            print(f"  {r['batch_id']} | {r['status']} | {r['c']} 行")
    except sqlite3.OperationalError as exc:
        print(f'  [跳过] {exc}')

    conn.close()


if __name__ == '__main__':
    main()
