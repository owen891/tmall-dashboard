"""
同步visitors到ipv列
"""
import sqlite3

db_path = r"F:\ai\.accelerate\tmall-dashboard\backend\data\db\dashboard.db"
conn = sqlite3.connect(db_path)

print("同步visitors到ipv列...")
conn.execute("UPDATE weekly_data SET ipv = visitors WHERE ipv = 0 AND visitors > 0")
updated = conn.execute("SELECT changes()").fetchone()[0]
print(f"✓ 更新了 {updated} 条记录")

# Verify
print("\n验证数据:")
sample = conn.execute("SELECT product_id, week_start, ipv, visitors, payment_amount FROM weekly_data LIMIT 5").fetchall()
for row in sample:
    print(f"  商品ID: {row[0]}, 日期: {row[1]}, ipv: {row[2]}, visitors: {row[3]}, 支付金额: {row[4]}")

conn.commit()
conn.close()
print("\n完成！")
