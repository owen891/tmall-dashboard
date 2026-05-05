"""
检查数据库表
"""
import sqlite3

db_path = r"F:\ai\.accelerate\tmall-dashboard\backend\data\db\dashboard.db"
conn = sqlite3.connect(db_path)

# List all tables
print("所有表:")
tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
for t in tables:
    count = conn.execute(f"SELECT COUNT(*) FROM {t[0]}").fetchone()[0]
    print(f"  {t[0]}: {count} 条")

# Check weekly_history
print("\nweekly_history表结构:")
try:
    cursor = conn.execute("PRAGMA table_info(weekly_history)")
    for col in cursor.fetchall():
        print(f"  {col[1]} ({col[2]})")
    count = conn.execute("SELECT COUNT(*) FROM weekly_history").fetchone()[0]
    print(f"数据: {count} 条")
except Exception as e:
    print(f"  表不存在或查询失败: {e}")

# Check ad_performance
print("\nad_performance表结构:")
try:
    cursor = conn.execute("PRAGMA table_info(ad_performance)")
    for col in cursor.fetchall():
        print(f"  {col[1]} ({col[2]})")
    count = conn.execute("SELECT COUNT(*) FROM ad_performance").fetchone()[0]
    print(f"数据: {count} 条")
except Exception as e:
    print(f"  表不存在或查询失败: {e}")

conn.close()
