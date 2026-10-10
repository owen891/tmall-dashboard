"""深度诊断：定位采集数据的具体异常（字段级缺失、覆盖度骤降、日期缺口）。

用法: .venv\\Scripts\\python.exe scripts\\diag_collect_deep.py
"""
import sqlite3
import sys
from pathlib import Path

DB_PATH = sys.argv[1] if len(sys.argv) > 1 else str(Path(__file__).resolve().parents[1] / 'data' / 'dashboard.db')


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # ---- A. daily_data 字段级：最近 7 天每列的非零行数 ----
    print('=' * 78)
    print('[A] daily_data 最近 7 天：每个指标列的"非零行数"（判断字段是否被抓到）')
    print('=' * 78)
    cols = [r['name'] for r in cur.execute('PRAGMA table_info(daily_data)').fetchall()]
    skip = {'id', 'shop_id', 'product_id', 'date', 'product_name', 'category',
            'shop_name', 'data_source', 'imported_at'}
    metrics = [c for c in cols if c not in skip]
    dates = [r[0] for r in cur.execute(
        'SELECT DISTINCT date FROM daily_data ORDER BY date DESC LIMIT 7').fetchall()]
    print(f"  日期: {dates}")
    print()
    header = '  ' + '指标'.ljust(34) + ''.join(d[-5:].rjust(9) for d in dates)
    print(header)
    print('  ' + '-' * (len(header) - 2))
    for col in metrics:
        try:
            row = cur.execute(
                f'SELECT date, SUM(CASE WHEN "{col}" IS NOT NULL AND "{col}" <> 0 THEN 1 ELSE 0 END) AS nz '
                f'FROM daily_data WHERE date IN ({",".join("?" * len(dates))}) GROUP BY date',
                dates,
            ).fetchall()
        except sqlite3.OperationalError:
            continue
        mapping = {r['date']: r['nz'] for r in row}
        vals = [mapping.get(d, 0) for d in dates]
        # 只打印有异常的（某天为 0 而其它天非 0）或全部非零列
        if max(vals) > 0 and min(vals) == 0:
            print('⚠ ' + col.ljust(32) + ''.join(str(v).rjust(9) for v in vals))
        elif max(vals) == 0:
            print('  ' + col.ljust(32) + ''.join(str(v).rjust(9) for v in vals) + '   (全为0)')

    # ---- B. daily_data 每天行数 & 关键指标 ----
    print('\n' + '=' * 78)
    print('[B] daily_data 最近 7 天关键指标合计')
    print('=' * 78)
    rows = cur.execute(
        '''SELECT date, COUNT(*) AS products,
                  ROUND(SUM(payment_amount),2) AS pay_amt,
                  ROUND(SUM(refund_amount),2) AS refund,
                  ROUND(SUM(net_sales),2) AS net,
                  SUM(payment_qty) AS pay_qty,
                  SUM(ipv) AS ipv, SUM(pv) AS pv,
                  SUM(uv_value) AS uv_value,
                  ROUND(SUM(ad_spend),2) AS ad_spend,
                  SUM(buyers) AS buyers
           FROM daily_data GROUP BY date ORDER BY date DESC LIMIT 7'''
    ).fetchall()
    for r in rows:
        print(f"  {r['date']}  商品{r['products']:>5}  支付¥{r['pay_amt'] or 0:>12,.2f}  "
              f"退款¥{r['refund'] or 0:>11,.2f}  净销¥{r['net'] or 0:>12,.2f}  "
              f"件{r['pay_qty'] or 0:>6}  ipv{r['ipv'] or 0:>7}  pv{r['pv'] or 0:>8}  "
              f"uv_value{r['uv_value'] or 0:>9}  ad¥{r['ad_spend'] or 0:>10,.2f}  买家{r['buyers'] or 0:>5}")

    # ---- C. sycm_item_flow 覆盖度 ----
    print('\n' + '=' * 78)
    print('[C] sycm_item_flow_source_daily 覆盖度（商品数 × 渠道数）')
    print('=' * 78)
    try:
        rows = cur.execute(
            '''SELECT stat_date, COUNT(*) AS rows_cnt,
                      COUNT(DISTINCT item_id) AS items,
                      COUNT(DISTINCT channel_name) AS channels
               FROM sycm_item_flow_source_daily GROUP BY stat_date ORDER BY stat_date DESC LIMIT 7'''
        ).fetchall()
        for r in rows:
            print(f"  {r['stat_date']}  行{r['rows_cnt']:>6}  商品{r['items']:>5}  渠道{r['channels']:>4}")
        print('\n  最近一天各渠道行数 TOP15:')
        latest = cur.execute('SELECT MAX(stat_date) FROM sycm_item_flow_source_daily').fetchone()[0]
        for r in cur.execute(
            '''SELECT channel_name, COUNT(*) AS c, COUNT(DISTINCT item_id) AS items
               FROM sycm_item_flow_source_daily WHERE stat_date = ?
               GROUP BY channel_name ORDER BY c DESC LIMIT 15''', (latest,)
        ).fetchall():
            print(f"      {str(r['channel_name'])[:28]:<30} 行{r['c']:>5}  商品{r['items']:>5}")
    except sqlite3.OperationalError as exc:
        print(f'  [跳过] {exc}')

    # ---- D. sycm_flow 店铺流量 ----
    print('\n' + '=' * 78)
    print('[D] sycm_flow_source_daily 店铺流量')
    print('=' * 78)
    try:
        for r in cur.execute(
            '''SELECT stat_date, COUNT(*) AS rows_cnt, COUNT(DISTINCT channel_name) AS channels,
                      ROUND(SUM(uv),0) AS uv, ROUND(SUM(pay_amount),2) AS pay
               FROM sycm_flow_source_daily GROUP BY stat_date ORDER BY stat_date DESC LIMIT 7'''
        ).fetchall():
            print(f"  {r['stat_date']}  行{r['rows_cnt']:>4}  渠道{r['channels']:>4}  uv={r['uv'] or 0}  支付={r['pay'] or 0}")
    except sqlite3.OperationalError as exc:
        print(f'  [跳过] {exc}')

    # ---- E. 万相台日期缺口 ----
    print('\n' + '=' * 78)
    print('[E] promotion_daily_facts 日期连续性')
    print('=' * 78)
    for r in cur.execute(
        '''SELECT date, COUNT(*) AS c, ROUND(SUM(ad_spend),2) AS spend, SUM(clicks) AS clicks
           FROM promotion_daily_facts GROUP BY date ORDER BY date DESC LIMIT 7'''
    ).fetchall():
        print(f"  {r['date']}  行{r['c']:>5}  花费¥{r['spend'] or 0:>10,.2f}  点击{r['clicks'] or 0:>7}")

    # ---- F. 最近一次各源采集的 checkpoint / 质量结果 ----
    print('\n' + '=' * 78)
    print('[F] 各数据源最近一次运行的质量门禁结果')
    print('=' * 78)
    try:
        for r in cur.execute(
            '''SELECT cr.source_key, cr.id, cr.status, cr.created_at,
                      cr.error_code, cr.stats
               FROM collector_runs cr
               WHERE cr.created_at = (SELECT MAX(created_at) FROM collector_runs c2
                                      WHERE c2.source_key = cr.source_key)
               ORDER BY cr.source_key'''
        ).fetchall():
            stats = (r['stats'] or '')[:160].replace('\n', ' ')
            print(f"  {r['source_key']:<16} {r['status']:<10} {r['created_at'][:19]}  {r['error_code'] or '-'}")
            print(f"      stats: {stats}")
    except sqlite3.OperationalError as exc:
        print(f'  [跳过] {exc}')

    conn.close()


if __name__ == '__main__':
    main()
