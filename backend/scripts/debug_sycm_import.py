"""
调试生意参谋数据导入问题
"""
import pandas as pd
import sqlite3
import re

DATA_DIR = r"F:\bi\海贝海\原始数据"
DB_PATH = r"F:\ai\.accelerate\tmall-dashboard\backend\data\db\dashboard.db"

# Check weekly_data columns
conn = sqlite3.connect(DB_PATH)
cols = [r[1] for r in conn.execute("PRAGMA table_info(weekly_data)").fetchall()]
print("weekly_data表列:")
for c in sorted(cols):
    print(f"  {c}")

# 检查是否有cart_users列
has_cart_users = 'cart_users' in cols
has_fav_users = 'fav_users' in cols
print(f"\n有cart_users列: {has_cart_users}")
print(f"有fav_users列: {has_fav_users}")

# 测试解析一个文件
xls_file = DATA_DIR + r"\【生意参谋平台】商品_全部_2026-03-01_2026-03-31.xls"
df = pd.read_excel(xls_file, header=None)

for i in range(len(df)):
    row_str = ' '.join([str(v) for v in df.iloc[i] if pd.notna(v)])
    if '统计日期' in row_str and '商品ID' in row_str:
        print(f"\n表头在第 {i} 行")
        data_df = df.iloc[i + 1:]
        header = df.iloc[i]
        data_df.columns = header
        data_df = data_df.reset_index(drop=True)
        
        print(f"\n第一行数据:")
        row = data_df.iloc[0]
        product_id = str(row.get('商品ID', ''))
        print(f"  商品ID原始值: {product_id}")
        
        match = re.search(r'\d{10,}', product_id)
        if match:
            print(f"  提取的商品ID: {match.group()}")
        else:
            print(f"  无法提取商品ID")
        
        print(f"  支付金额: {row.get('支付金额')}")
        print(f"  商品访客数: {row.get('商品访客数')}")
        break

conn.close()
