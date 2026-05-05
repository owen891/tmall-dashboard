"""
直接测试数据库查询，绕过API
"""
import sqlite3
from datetime import datetime, timedelta

db_path = r"F:\ai\.accelerate\tmall-dashboard\backend\data\db\dashboard.db"
conn = sqlite3.connect(db_path)

# 获取最新的week_start
latest = conn.execute("SELECT week_start FROM weekly_data ORDER BY week_start DESC LIMIT 1").fetchone()[0]
print(f"最新周期: {latest}")

# 计算上一周期
d = datetime.strptime(latest, '%Y-%m-%d')
prev = (d - timedelta(days=7)).strftime('%Y-%m-%d')
print(f"上一周期: {prev}")

# 测试KPI查询 - 当前周期
print(f"\n查询当前周期 ({latest}):")
row = conn.execute("""
    SELECT 
        SUM(payment_amount) as payment,
        SUM(refund_amount) as refund,
        SUM(ipv) as visitors,
        AVG(payment_conversion) as conversion,
        SUM(ad_spend) as ad_spend
    FROM weekly_data 
    WHERE week_start = ?
""", (latest,)).fetchone()

print(f"  支付金额: {row[0]}")
print(f"  退款金额: {row[1]}")
print(f"  访客数: {row[2]}")
print(f"  转化率: {row[3]}")
print(f"  广告花费: {row[4]}")

# 测试KPI查询 - 上一周期
print(f"\n查询上一周期 ({prev}):")
prev_row = conn.execute("""
    SELECT 
        SUM(payment_amount) as payment,
        SUM(refund_amount) as refund,
        SUM(ipv) as visitors,
        AVG(payment_conversion) as conversion,
        SUM(ad_spend) as ad_spend
    FROM weekly_data 
    WHERE week_start = ?
""", (prev,)).fetchone()

print(f"  支付金额: {prev_row[0]}")
print(f"  退款金额: {prev_row[1]}")
print(f"  访客数: {prev_row[2]}")
print(f"  转化率: {prev_row[3]}")
print(f"  广告花费: {prev_row[4]}")

# 计算ROI
curr_payment = row[0] or 0
curr_ad = row[4] or 0
roi = (curr_payment / curr_ad) if curr_ad > 0 else 0
print(f"\n当前ROI: {roi}")

prev_payment = prev_row[0] or 0
prev_ad = prev_row[4] or 0
prev_roi = (prev_payment / prev_ad) if prev_ad > 0 else 0
print(f"上一周期ROI: {prev_roi}")

# 计算环比变化
if prev_payment > 0:
    payment_change = (curr_payment - prev_payment) / prev_payment * 100
    print(f"\n支付金额环比变化: {payment_change:.1f}%")
else:
    print("\n上一周期支付金额为0，无法计算环比")

conn.close()
print("\n完成！")
