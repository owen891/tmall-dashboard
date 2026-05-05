import sqlite3
conn = sqlite3.connect('f:/ai/.accelerate/tmall-dashboard/backend/data/dashboard.db')
cursor = conn.cursor()
tables = [
    'traffic_sources', 'product_traffic_detail', 'category_data',
    'store_daily_data', 'keyword_data', 'dmp_audience',
    'products', 'product_lifecycle'
]
for t in tables:
    try:
        count = cursor.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        print(f"{t}: {count} rows")
    except Exception as e:
        print(f"{t}: ERROR - {e}")
conn.close()
