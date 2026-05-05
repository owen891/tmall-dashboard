import sqlite3

conn = sqlite3.connect('f:/ai/.accelerate/tmall-dashboard/backend/data/db/dashboard.db')
cursor = conn.cursor()

# Check paid_detail columns
print("=== paid_detail 表字段 ===")
cursor.execute("PRAGMA table_info(paid_detail)")
existing_cols = {row[1] for row in cursor.fetchall()}
print(f"现有字段: {len(existing_cols)}个")

# Model fields from advertising.py
model_fields = [
    'id', 'product_id', 'date_range', 'impressions', 'clicks', 'cost', 'ctr', 
    'cpc', 'cpm', 'total_gmv', 'total_orders', 'direct_gmv', 'indirect_gmv', 
    'roi', 'cart_adds', 'cart_rate', 'favs', 'new_buyers', 'members_gmv',
    'imported_at', 'direct_orders', 'indirect_orders', 'click_conversion',
    'presale_roi', 'total_cost', 'direct_cart_adds', 'indirect_cart_adds',
    'store_favs', 'store_fav_cost', 'total_fav_cart', 'total_fav_cart_cost',
    'item_fav_cart', 'item_fav_cart_cost', 'total_favs', 'item_fav_cost',
    'item_fav_rate', 'cart_cost'
]

missing = [f for f in model_fields if f not in existing_cols]
print(f"缺失字段: {missing}")

for col in missing:
    if col in ['id']:
        continue
    col_type = 'INTEGER' if any(x in col for x in ['orders', 'cart', 'favs', 'buyers', 'count']) else 'FLOAT'
    sql = f"ALTER TABLE paid_detail ADD COLUMN {col} {col_type}"
    try:
        cursor.execute(sql)
        print(f"✓ 添加 {col} {col_type}")
    except Exception as e:
        print(f"✗ {col}: {e}")

conn.commit()
print("\n修复完成!")
conn.close()
