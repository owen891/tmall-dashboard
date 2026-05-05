"""
修复所有月维度数据格式
"""
import sqlite3
import re

DB_PATH = r"F:\ai\.accelerate\tmall-dashboard\backend\data\db\dashboard.db"

conn = sqlite3.connect(DB_PATH)

print("修复所有月维度数据格式...")

# 获取所有不同的月份
months = conn.execute("SELECT DISTINCT month FROM monthly_data").fetchall()

for (month,) in months:
    if re.match(r'^\d{2}年-\d{1,2}月$', month):
        # 解析 "25年-9月" -> "2025-09"
        match = re.match(r'(\d{2})年-(\d{1,2})月', month)
        if match:
            year = int(match.group(1))
            month_num = int(match.group(2))
            # 假设20-29是2020-2029
            full_year = 2000 + year if year < 100 else year
            new_month = f"{full_year}-{month_num:02d}"
            
            conn.execute("UPDATE monthly_data SET month = ? WHERE month = ?", (new_month, month))
            updated = conn.execute("SELECT changes()").fetchone()[0]
            print(f"  {month} -> {new_month} ({updated} 条)")

conn.commit()

# 验证
print("\n验证月份格式:")
sample = conn.execute("SELECT DISTINCT month FROM monthly_data ORDER BY month DESC LIMIT 5").fetchall()
for row in sample:
    print(f"  {row[0]}")

conn.close()
print("\n完成！")
