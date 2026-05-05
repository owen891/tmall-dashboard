"""
修复月维度数据的月份格式
"""
import sqlite3

DB_PATH = r"F:\ai\.accelerate\tmall-dashboard\backend\data\db\dashboard.db"

conn = sqlite3.connect(DB_PATH)

print("修复月维度数据格式...")

# 更新月份格式: "26年-3月" -> "2026-03"
conn.execute("""
    UPDATE monthly_data 
    SET month = CASE 
        WHEN month LIKE '26年-%' THEN 
            '2026-' || SUBSTR(REPLACE(month, '26年-', ''), 1, 2)
        ELSE month
    END
    WHERE month LIKE '26年-%'
""")

updated = conn.execute("SELECT changes()").fetchone()[0]
print(f"✓ 更新了 {updated} 条记录")

# 验证
print("\n验证月份格式:")
sample = conn.execute("SELECT DISTINCT month FROM monthly_data ORDER BY month DESC LIMIT 5").fetchall()
for row in sample:
    print(f"  {row[0]}")

# 验证数据
print("\n月维度数据统计:")
row = conn.execute("""
    SELECT 
        COUNT(*) as total,
        SUM(payment_amount) as total_payment,
        SUM(visitors) as total_visitors
    FROM monthly_data
""").fetchone()
print(f"  总记录: {row[0]}")
print(f"  总支付金额: {row[1]}")
print(f"  总访客数: {row[2]}")

conn.commit()
conn.close()
print("\n完成！")
