"""
直接测试数据库查询
"""
import sqlite3

db_path = r'F:\ai\.accelerate\tmall-dashboard\backend\data\db\dashboard.db'
conn = sqlite3.connect(db_path)

# Test query for 2026-04-20
print("查询 2026-04-20 数据:")
row = conn.execute("""
    SELECT 
        SUM(payment_amount) as total_gmv,
        SUM(visitors) as total_visitors,
        AVG(payment_conversion) as avg_conversion,
        SUM(ad_spend) as total_ad_spend,
        SUM(refund_amount) as total_refund
    FROM weekly_data 
    WHERE week_start = '2026-04-20'
""").fetchone()

print(f"  支付金额: {row[0]}")
print(f"  访客数: {row[1]}")
print(f"  转化率: {row[2]}")
print(f"  广告花费: {row[3]}")
print(f"  退款金额: {row[4]}")

# Check latest period
print("\n最新周期:")
latest = conn.execute("SELECT week_start, COUNT(*) FROM weekly_data GROUP BY week_start ORDER BY week_start DESC LIMIT 3").fetchall()
for row in latest:
    print(f"  {row[0]}: {row[1]} 条记录")

conn.close()
