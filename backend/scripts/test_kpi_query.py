"""
测试KPI查询
"""
import sqlite3

db_path = r"F:\ai\.accelerate\tmall-dashboard\backend\data\db\dashboard.db"
conn = sqlite3.connect(db_path)

# Test the exact query used by the backend
print("测试weekly_data查询 (2026-05-04):")
row = conn.execute("""
    SELECT 
        SUM(payment_amount) as total_gmv,
        SUM(ipv) as total_visitors,
        AVG(payment_conversion) as avg_conversion,
        SUM(ad_spend) as total_ad_spend,
        SUM(refund_amount) as total_refund,
        SUM(net_sales) as total_net_sales
    FROM weekly_data 
    WHERE week_start = '2026-05-04'
""").fetchone()

print(f"  支付金额: {row[0]}")
print(f"  访客数: {row[1]}")
print(f"  转化率: {row[2]}")
print(f"  广告花费: {row[3]}")
print(f"  退款金额: {row[4]}")
print(f"  净销售额: {row[5]}")

# Check week_start values
print("\n周期分布:")
weeks = conn.execute("SELECT week_start, COUNT(*) FROM weekly_data GROUP BY week_start ORDER BY week_start DESC").fetchall()
for week in weeks:
    print(f"  {week[0]}: {week[1]} 条")

conn.close()
print("\n完成！")
