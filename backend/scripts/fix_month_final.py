"""
最终修复月格式
"""
import sqlite3
import re

DB_PATH = r"F:\ai\.accelerate\tmall-dashboard\backend\data\db\dashboard.db"

conn = sqlite3.connect(DB_PATH)

print("最终修复月格式...")

# 获取所有不同的月份
months = conn.execute("SELECT DISTINCT month FROM monthly_data").fetchall()

for (month,) in months:
    # 匹配 "2026-3月" -> "2026-03"
    match = re.match(r'(\d{4})-(\d{1,2})月$', month)
    if match:
        year = match.group(1)
        month_num = int(match.group(2))
        new_month = f"{year}-{month_num:02d}"
        
        conn.execute("UPDATE monthly_data SET month = ? WHERE month = ?", (new_month, month))
        updated = conn.execute("SELECT changes()").fetchone()[0]
        if updated > 0:
            print(f"  {month} -> {new_month} ({updated} 条)")

conn.commit()

# 验证
print("\n验证月份格式:")
sample = conn.execute("SELECT DISTINCT month FROM monthly_data ORDER BY month DESC LIMIT 10").fetchall()
for row in sample:
    print(f"  {row[0]}")

conn.close()
print("\n完成！")
