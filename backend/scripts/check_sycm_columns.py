"""
检查生意参谋数据完整列名
"""
import pandas as pd
import os

DATA_DIR = r"F:\bi\海贝海\原始数据"
xls_file = os.path.join(DATA_DIR, "【生意参谋平台】商品_全部_2026-03-01_2026-03-31.xls")

df = pd.read_excel(xls_file, header=None)
header_row = 4
header = df.iloc[header_row]
data_df = df.iloc[header_row + 1:]
data_df.columns = header
data_df = data_df.reset_index(drop=True)

print(f"所有列 ({len(data_df.columns)}):")
for i, col in enumerate(data_df.columns):
    print(f"  {i}. {col}")

# 查看第一行数据
print(f"\n第一行数据:")
for col in data_df.columns:
    val = data_df.iloc[0][col]
    print(f"  {col}: {val}")
