"""
检查并添加缺失的列到daily_data和monthly_data表
"""
import sqlite3

DB_PATH = r"F:\ai\.accelerate\tmall-dashboard\backend\data\db\dashboard.db"

conn = sqlite3.connect(DB_PATH)

# Check daily_data columns
print("daily_data表结构:")
cursor = conn.execute("PRAGMA table_info(daily_data)")
existing_daily = set()
for row in cursor.fetchall():
    print(f"  {row[1]} ({row[2]})")
    existing_daily.add(row[1])

# Columns to add for daily_data
daily_cols = [
    ("total_roi", "FLOAT", "0"),
    ("direct_roi", "FLOAT", "0"),
    ("visitors", "INTEGER", "0"),
    ("ipv", "INTEGER", "0"),
    ("uv_value", "FLOAT", "0"),
    ("payment_conversion", "FLOAT", "0"),
    ("refund_rate", "FLOAT", "0"),
    ("cart_rate", "FLOAT", "0"),
    ("cart_qty", "INTEGER", "0"),
    ("avg_order_value", "FLOAT", "0"),
    ("page_views", "INTEGER", "0"),
    ("search_visitors", "INTEGER", "0"),
    ("search_ratio", "FLOAT", "0"),
    ("click_rate", "FLOAT", "0"),
    ("impressions", "INTEGER", "0"),
    ("clicks", "INTEGER", "0"),
    ("fav_users", "INTEGER", "0"),
    ("payment_users", "INTEGER", "0"),
    ("bounce_rate", "FLOAT", "0"),
    ("avg_stay_duration", "FLOAT", "0"),
]

print("\n添加daily_data缺失的列:")
for col_name, col_type, default in daily_cols:
    if col_name not in existing_daily:
        try:
            conn.execute(f"ALTER TABLE daily_data ADD COLUMN {col_name} {col_type} DEFAULT {default}")
            print(f"  ✓ 添加: {col_name}")
        except Exception as e:
            print(f"  ✗ 失败 {col_name}: {e}")
    else:
        print(f"  - 已存在: {col_name}")

# Check monthly_data columns
print("\n\nmonthly_data表结构:")
cursor = conn.execute("PRAGMA table_info(monthly_data)")
existing_monthly = set()
for row in cursor.fetchall():
    print(f"  {row[1]} ({row[2]})")
    existing_monthly.add(row[1])

# Columns to add for monthly_data
monthly_cols = [
    ("total_roi", "FLOAT", "0"),
    ("direct_roi", "FLOAT", "0"),
    ("visitors", "INTEGER", "0"),
    ("ipv", "INTEGER", "0"),
    ("uv_value", "FLOAT", "0"),
    ("payment_conversion", "FLOAT", "0"),
    ("refund_rate", "FLOAT", "0"),
    ("cart_rate", "FLOAT", "0"),
    ("cart_qty", "INTEGER", "0"),
    ("avg_order_value", "FLOAT", "0"),
    ("page_views", "INTEGER", "0"),
    ("search_visitors", "INTEGER", "0"),
    ("search_ratio", "FLOAT", "0"),
    ("click_rate", "FLOAT", "0"),
    ("impressions", "INTEGER", "0"),
    ("clicks", "INTEGER", "0"),
    ("fav_users", "INTEGER", "0"),
    ("payment_users", "INTEGER", "0"),
    ("bounce_rate", "FLOAT", "0"),
    ("avg_stay_duration", "FLOAT", "0"),
]

print("\n添加monthly_data缺失的列:")
for col_name, col_type, default in monthly_cols:
    if col_name not in existing_monthly:
        try:
            conn.execute(f"ALTER TABLE monthly_data ADD COLUMN {col_name} {col_type} DEFAULT {default}")
            print(f"  ✓ 添加: {col_name}")
        except Exception as e:
            print(f"  ✗ 失败 {col_name}: {e}")
    else:
        print(f"  - 已存在: {col_name}")

conn.commit()
conn.close()
print("\n完成！")
