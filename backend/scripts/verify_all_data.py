"""
验证数据库所有数据
"""
import sqlite3

DB_PATH = r"F:\ai\.accelerate\tmall-dashboard\backend\data\db\dashboard.db"

conn = sqlite3.connect(DB_PATH)

print("=" * 70)
print("数据库数据总览")
print("=" * 70)

tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()

total_records = 0
for (table_name,) in sorted(tables):
    count = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
    total_records += count
    if count > 0:
        print(f"  ✅ {table_name}: {count:,} 条")
    else:
        print(f"  ⚪ {table_name}: 0 条")

print("\n" + "=" * 70)
print(f"总计: {total_records:,} 条记录")
print("=" * 70)

# 检查products表
print("\n商品数据:")
prod_count = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
print(f"  products表: {prod_count} 个商品")

# 检查weekly_data
print("\n周维度数据详情:")
weekly = conn.execute("""
    SELECT week_start, COUNT(*) as cnt, 
           SUM(payment_amount) as gmv,
           SUM(visitors) as visitors
    FROM weekly_data 
    GROUP BY week_start 
    ORDER BY week_start DESC 
    LIMIT 5
""").fetchall()
for row in weekly:
    print(f"  {row[0]}: {row[1]:,}条, GMV: ¥{row[2]:,.0f}, 访客: {row[3]:,}")

# 检查daily_data
print("\n日维度数据:")
daily_count = conn.execute("SELECT COUNT(*) FROM daily_data").fetchone()[0]
if daily_count > 0:
    latest = conn.execute("SELECT MAX(date), payment_amount, visitors FROM daily_data").fetchone()
    print(f"  最新: {latest[0]}, 支付金额: ¥{latest[1]:,.0f}, 访客: {latest[2]:,}")
    print(f"  总记录: {daily_count} 条")

# 检查monthly_data
print("\n月维度数据:")
monthly_count = conn.execute("SELECT COUNT(*) FROM monthly_data").fetchone()[0]
if monthly_count > 0:
    months = conn.execute("SELECT DISTINCT month FROM monthly_data ORDER BY month DESC LIMIT 5").fetchall()
    print(f"  月份: {', '.join([m[0] for m in months])}")
    print(f"  总记录: {monthly_count} 条")

conn.close()
print("\n" + "=" * 70)
print("验证完成!")
print("=" * 70)
