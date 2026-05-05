"""
添加所有缺失的列到weekly_data表
"""
import sqlite3

db_path = r"F:\ai\.accelerate\tmall-dashboard\backend\data\db\dashboard.db"
conn = sqlite3.connect(db_path)

# Get existing columns
cursor = conn.execute("PRAGMA table_info(weekly_data)")
existing = set([row[1] for row in cursor.fetchall()])
print(f"现有 {len(existing)} 个列")

# All columns from WeeklyData model
cols_to_add = [
    ("presale_amount", "FLOAT", "0"),
    ("presale_qty", "INTEGER", "0"),
    ("pv", "INTEGER", "0"),
    ("search_ipv", "INTEGER", "0"),
    ("recommend_ipv", "INTEGER", "0"),
    ("paid_ipv", "INTEGER", "0"),
    ("organic_ipv", "INTEGER", "0"),
    ("fav_rate", "FLOAT", "0"),
    ("search_click_rate", "FLOAT", "0"),
    ("bounce_rate", "FLOAT", "0"),
    ("avg_stay_duration", "FLOAT", "0"),
    ("ad_roi", "FLOAT", "0"),
    ("repurchase_rate", "FLOAT", "0"),
    ("repurchase_users", "INTEGER", "0"),
    ("cross_sell_qty", "INTEGER", "0"),
    ("cross_sell_rate", "FLOAT", "0"),
    ("category_width", "INTEGER", "0"),
    ("action_1", "TEXT", "NULL"),
    ("action_2", "TEXT", "NULL"),
    ("industry_ctr", "FLOAT", "0"),
]

added = 0
for col_name, col_type, default in cols_to_add:
    if col_name not in existing:
        try:
            if default == "NULL":
                conn.execute(f"ALTER TABLE weekly_data ADD COLUMN {col_name} {col_type}")
            else:
                conn.execute(f"ALTER TABLE weekly_data ADD COLUMN {col_name} {col_type} DEFAULT {default}")
            print(f"✓ 添加: {col_name}")
            added += 1
        except Exception as e:
            print(f"✗ 失败 {col_name}: {e}")
    else:
        print(f"- 已存在: {col_name}")

conn.commit()
conn.close()
print(f"\n共添加 {added} 个列")
