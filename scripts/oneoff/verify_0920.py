"""Verify 9-20 wxt detail rows landed in promotion_daily_facts."""
import sqlite3
from pathlib import Path

DB = Path(r"E:\www\tmall-dashboard\data\dashboard.db")
conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row

print("=== 9-20 入库情况（按 grain + channel）===")
rows = conn.execute(
    """
    SELECT grain, channel, COUNT(*) cnt,
           ROUND(SUM(ad_spend),2) spend,
           ROUND(SUM(attributed_payment_amount),2) pay
    FROM promotion_daily_facts
    WHERE date='2026-09-20'
    GROUP BY grain, channel
    ORDER BY grain, channel
    """
).fetchall()
for r in rows:
    print(f"  grain={r['grain'] or '(null)':8s}  ch={r['channel'] or '(null)':12s}  rows={r['cnt']:4d}  spend={r['spend']}  pay={r['pay']}")

print()
print("=== 9-19 vs 9-20 总量对比 ===")
rows = conn.execute(
    """
    SELECT date, grain, COUNT(*) cnt, ROUND(SUM(ad_spend),2) spend
    FROM promotion_daily_facts
    WHERE date IN ('2026-09-19','2026-09-20')
    GROUP BY date, grain
    ORDER BY date DESC, grain
    """
).fetchall()
for r in rows:
    print(f"  {r['date']}  grain={r['grain'] or '(null)':8s}  rows={r['cnt']:4d}  spend={r['spend']}")

print()
print("=== 最近 5 天每日 spend 趋势 ===")
rows = conn.execute(
    """
    SELECT date, grain, COUNT(*) cnt, ROUND(SUM(ad_spend),2) spend
    FROM promotion_daily_facts
    WHERE date >= '2026-09-15'
    GROUP BY date, grain
    ORDER BY date DESC, grain
    """
).fetchall()
for r in rows:
    print(f"  {r['date']}  grain={r['grain'] or '(null)':8s}  rows={r['cnt']:4d}  spend={r['spend']}")
