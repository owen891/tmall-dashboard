"""检查万相台最近入库情况 + 单品流量失败 checkpoint。"""
import sqlite3
from pathlib import Path

DB = Path(r"E:\www\tmall-dashboard\data\dashboard.db")
conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row

print("=== promotion_daily_facts 2026-09-14 起 按 date/channel/grain ===")
rows = conn.execute(
    """
    SELECT date, channel, grain, COUNT(*) cnt,
           ROUND(SUM(ad_spend),2) spend,
           ROUND(SUM(attributed_payment_amount),2) pay_amt
    FROM promotion_daily_facts
    WHERE date >= '2026-09-14'
    GROUP BY date, channel, grain
    ORDER BY date DESC, grain, channel
    """
).fetchall()
for r in rows:
    print(f"{r['date']}  grain={r['grain'] or '(null)':10s}  ch={r['channel'] or '(null)':12s}  rows={r['cnt']:4d}  spend={r['spend']}  pay={r['pay_amt']}")

print()
print("=== promotion_daily_facts 最近 15 行原始记录 ===")
rows2 = conn.execute(
    """
    SELECT date, channel, grain, campaign_id, product_id,
           ROUND(ad_spend,2) spend, ROUND(attributed_payment_amount,2) pay,
           clicks, impressions
    FROM promotion_daily_facts
    ORDER BY rowid DESC LIMIT 15
    """
).fetchall()
for r in rows2:
    print(dict(r))

print()
print("=== collector_checkpoints 今早 sycm_item_flow 失败项 ===")
rows3 = conn.execute(
    """
    SELECT unit_type, unit_key, page_no, row_count,
           last_error_code, last_error_message
    FROM collector_checkpoints
    WHERE run_id = 'b3f15e208f0d4d35b32cd4cff1af864c'
      AND status IN ('failed','blocked')
    ORDER BY unit_key
    """
).fetchall()
for r in rows3:
    print(dict(r))

print()
print("=== collector_runs 最近 5 次 wanxiangtai 运行 ===")
rows4 = conn.execute(
    """
    SELECT run_id, source_key, status, window_start, window_end,
           row_count, started_at, finished_at, error_message
    FROM collector_runs
    WHERE source_key = 'wanxiangtai'
    ORDER BY started_at DESC LIMIT 5
    """
).fetchall()
for r in rows4:
    d = dict(r)
    if d.get('error_message'):
        d['error_message'] = d['error_message'][:200]
    print(d)

conn.close()
