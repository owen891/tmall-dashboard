"""
添加ipv列并同步visitors数据
"""
import sqlite3

db_path = r"F:\ai\.accelerate\tmall-dashboard\backend\data\db\dashboard.db"
conn = sqlite3.connect(db_path)

print("步骤 1: 添加ipv列")
try:
    conn.execute("ALTER TABLE weekly_data ADD COLUMN ipv INTEGER DEFAULT 0")
    print("  ✓ 已添加ipv列")
except Exception as e:
    if "duplicate column" in str(e).lower():
        print("  - ipv列已存在")
    else:
        print(f"  ✗ 添加失败: {e}")

print("\n步骤 2: 同步visitors到ipv")
conn.execute("UPDATE weekly_data SET ipv = visitors WHERE ipv = 0 AND visitors > 0")
updated = conn.execute("SELECT changes()").fetchone()[0]
print(f"  ✓ 更新了 {updated} 条记录")

print("\n步骤 3: 验证数据")
sample = conn.execute("""
    SELECT product_id, week_start, ipv, visitors, payment_amount 
    FROM weekly_data 
    LIMIT 5
""").fetchall()
for row in sample:
    print(f"  商品ID: {row[0]}, 日期: {row[1]}, ipv: {row[2]}, visitors: {row[3]}, 支付金额: {row[4]}")

# Test KPI query
print("\n步骤 4: 测试KPI查询")
row = conn.execute("""
    SELECT 
        SUM(payment_amount) as total_gmv,
        SUM(ipv) as total_visitors,
        AVG(payment_conversion) as avg_conversion,
        SUM(ad_spend) as total_ad_spend
    FROM weekly_data 
    WHERE week_start = '2026-05-04'
""").fetchone()
print(f"  日期: 2026-05-04")
print(f"  支付金额: {row[0]}")
print(f"  访客数: {row[1]}")
print(f"  转化率: {row[2]}")
print(f"  广告花费: {row[3]}")

conn.commit()
conn.close()
print("\n完成！")
