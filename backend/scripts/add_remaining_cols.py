"""
添加所有缺失的列到daily_data和monthly_data表
"""
import sqlite3

DB_PATH = r"F:\ai\.accelerate\tmall-dashboard\backend\data\db\dashboard.db"

conn = sqlite3.connect(DB_PATH)

# Check existing columns
daily_cols = set([r[1] for r in conn.execute("PRAGMA table_info(daily_data)").fetchall()])
monthly_cols = set([r[1] for r in conn.execute("PRAGMA table_info(monthly_data)").fetchall()])

# DailyData model columns
daily_model_cols = [
    ("search_conversion", "FLOAT", "0"),
    ("search_visitors", "INTEGER", "0"),
    ("cart_users", "INTEGER", "0"),
    ("payment_qty", "INTEGER", "0"),
    ("buyers", "INTEGER", "0"),
]

# MonthlyData model columns
monthly_model_cols = [
    ("search_conversion", "FLOAT", "0"),
    ("cart_users", "INTEGER", "0"),
    ("payment_qty", "INTEGER", "0"),
    ("buyers", "INTEGER", "0"),
    ("search_ipv", "INTEGER", "0"),
    ("recommend_ipv", "INTEGER", "0"),
    ("paid_ipv", "INTEGER", "0"),
    ("organic_ipv", "INTEGER", "0"),
    ("industry_ctr", "FLOAT", "0"),
    ("cross_sell_qty", "INTEGER", "0"),
    ("repurchase_users", "INTEGER", "0"),
    ("guide_visits", "INTEGER", "0"),
    ("guide_visitors", "INTEGER", "0"),
    ("guide_potential", "INTEGER", "0"),
    ("guide_potential_ratio", "FLOAT", "0"),
    ("new_buyers", "INTEGER", "0"),
    ("new_buyer_ratio", "FLOAT", "0"),
    ("cross_sell_categories", "INTEGER", "0"),
]

print("daily_data缺失的列:")
added_daily = 0
for col_name, col_type, default in daily_model_cols:
    if col_name not in daily_cols:
        try:
            conn.execute(f"ALTER TABLE daily_data ADD COLUMN {col_name} {col_type} DEFAULT {default}")
            print(f"  ✓ {col_name}")
            added_daily += 1
        except Exception as e:
            print(f"  ✗ {col_name}: {e}")
    else:
        print(f"  - {col_name} (已存在)")

print(f"\n月维度缺失的列:")
added_monthly = 0
for col_name, col_type, default in monthly_model_cols:
    if col_name not in monthly_cols:
        try:
            conn.execute(f"ALTER TABLE monthly_data ADD COLUMN {col_name} {col_type} DEFAULT {default}")
            print(f"  ✓ {col_name}")
            added_monthly += 1
        except Exception as e:
            print(f"  ✗ {col_name}: {e}")
    else:
        print(f"  - {col_name} (已存在)")

conn.commit()
conn.close()

print(f"\n✓ daily_data添加 {added_daily} 个列")
print(f"✓ monthly_data添加 {added_monthly} 个列")
print("\n完成！")
