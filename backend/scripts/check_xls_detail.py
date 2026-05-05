"""
检查生意参谋XLS文件的完整内容
"""
import pandas as pd
import os

DATA_DIR = r"F:\bi\海贝海\原始数据"
xls_file = os.path.join(DATA_DIR, "【生意参谋平台】商品_全部_2026-03-01_2026-03-31.xls")

df = pd.read_excel(xls_file, sheet_name=0, header=None)

print("前20行:")
for i in range(20):
    row = df.iloc[i]
    non_null = [f"{j}:{row[j]}" for j in range(len(row)) if pd.notna(row[j])]
    print(f"  行{i}: {non_null[:6]}")

print("\n\n最后10行:")
for i in range(len(df)-10, len(df)):
    row = df.iloc[i]
    non_null = [f"{j}:{row[j]}" for j in range(len(row)) if pd.notna(row[j])]
    print(f"  行{i}: {non_null[:6]}")
