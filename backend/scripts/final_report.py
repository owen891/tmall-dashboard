"""
最终数据验证报告
"""
import sqlite3

DB_PATH = r"F:\ai\.accelerate\tmall-dashboard\backend\data\db\dashboard.db"
conn = sqlite3.connect(DB_PATH)

print("=" * 80)
print("📊 数据导入最终报告")
print("=" * 80)

tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
total_records = 0
active_tables = []

for (table_name,) in tables:
    count = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
    total_records += count
    if count > 0:
        active_tables.append((table_name, count))

print(f"\n✅ 有数据的表 ({len(active_tables)} 个):")
for name, count in active_tables:
    print(f"  • {name}: {count:,} 条")

print(f"\n📈 总记录数: {total_records:,} 条")

# 详细统计
print("\n" + "-" * 80)
print("📋 详细统计")
print("-" * 80)

# weekly_data
print("\n1. 周维度商品数据 (weekly_data):")
total_weekly = conn.execute("SELECT COUNT(*) FROM weekly_data").fetchone()[0]
sources = conn.execute("SELECT data_source, COUNT(*) FROM weekly_data GROUP BY data_source ORDER BY COUNT(*) DESC").fetchall()
for src, cnt in sources:
    print(f"  • {src}: {cnt:,} 条")

# 日期范围
date_range = conn.execute("SELECT MIN(week_start), MAX(week_start) FROM weekly_data").fetchone()
print(f"  📅 日期范围: {date_range[0]} ~ {date_range[1]}")

# daily_data
print("\n2. 日维度店铺数据 (daily_data):")
daily_count = conn.execute("SELECT COUNT(*) FROM daily_data").fetchone()[0]
if daily_count > 0:
    date_range = conn.execute("SELECT MIN(date), MAX(date) FROM daily_data").fetchone()
    print(f"  📅 日期范围: {date_range[0]} ~ {date_range[1]}")
    print(f"  总记录: {daily_count} 条")

# monthly_data
print("\n3. 月维度数据 (monthly_data):")
monthly_count = conn.execute("SELECT COUNT(*) FROM monthly_data").fetchone()[0]
if monthly_count > 0:
    months = conn.execute("SELECT DISTINCT month FROM monthly_data ORDER BY month").fetchall()
    print(f"  📅 月份: {', '.join([m[0] for m in months])}")
    print(f"  总记录: {monthly_count:,} 条")

# products
print("\n4. 商品基础信息 (products):")
prod_count = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
print(f"  📦 商品数: {prod_count} 个")

conn.close()
print("\n" + "=" * 80)
print("✅ 数据导入完成！")
print("=" * 80)
