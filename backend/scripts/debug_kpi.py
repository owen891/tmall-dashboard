import sqlite3

db_path = r'F:\ai\.accelerate\tmall-dashboard\backend\data\db\dashboard.db'
conn = sqlite3.connect(db_path)

# Check weekly_data columns
cursor = conn.execute("PRAGMA table_info(weekly_data)")
cols = [row[1] for row in cursor.fetchall()]
print("weekly_data表列:")
for c in sorted(cols):
    print(f"  {c}")

# Check if there's data for the latest week
latest = conn.execute("SELECT week_start, COUNT(*) FROM weekly_data GROUP BY week_start ORDER BY week_start DESC LIMIT 5").fetchall()
print("\n最新周期数据:")
for row in latest:
    print(f"  {row[0]}: {row[1]} 条")

# Check KPI query for 2026-04-20
print("\n2026-04-20数据统计:")
row = conn.execute("""
    SELECT 
        SUM(payment_amount) as total_gmv,
        SUM(visitors) as total_visitors,
        AVG(payment_conversion) as avg_conversion,
        SUM(ad_spend) as total_ad_spend
    FROM weekly_data 
    WHERE week_start = '2026-04-20'
""").fetchone()
print(f"  支付金额: {row[0]}")
print(f"  访客数: {row[1]}")
print(f"  转化率: {row[2]}")
print(f"  广告花费: {row[3]}")

conn.close()
