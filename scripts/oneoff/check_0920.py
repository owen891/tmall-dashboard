"""确认 9-20 万相台明细缺失情况 + 找采集脚本路径。"""
import sqlite3
from pathlib import Path

DB = Path(r"E:\www\tmall-dashboard\data\dashboard.db")
conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row

print("=== promotion_daily_facts 按日期统计最近10天 ===")
rows = conn.execute(
    """
    SELECT date, grain, COUNT(*) cnt, ROUND(SUM(ad_spend),2) spend
    FROM promotion_daily_facts
    WHERE date >= '2026-09-10'
    GROUP BY date, grain
    ORDER BY date DESC, grain
    """
).fetchall()
for r in rows:
    print(f"  {r['date']}  grain={r['grain'] or '(null)':8s}  rows={r['cnt']:4d}  spend={r['spend']}")

print()
print("=== date 为 NULL 的 summary 行（今早 chargeSum 多日区间）===")
rows = conn.execute(
    """
    SELECT period_start, period_end, channel, grain, ROUND(ad_spend,2) spend
    FROM promotion_daily_facts
    WHERE date IS NULL
    ORDER BY rowid DESC LIMIT 10
    """
).fetchall()
for r in rows:
    print(dict(r))
if not rows:
    print("  (无)")
