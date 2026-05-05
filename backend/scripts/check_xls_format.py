"""
检查生意参谋商品数据文件格式
"""
import pandas as pd
import os

DATA_DIR = r"F:\bi\海贝海\原始数据"
xls_file = os.path.join(DATA_DIR, "【生意参谋平台】商品_全部_2026-03-01_2026-03-31.xls")

print(f"检查文件: {os.path.basename(xls_file)}")
print(f"文件大小: {os.path.getsize(xls_file):,} bytes")

df = pd.read_excel(xls_file, sheet_name=None, header=None)

for name, sheet in df.items():
    print(f"\nSheet: {name}")
    print(f"  行数: {len(sheet)}")
    print(f"  列数: {len(sheet.columns)}")
    print(f"  前3行:")
    print(sheet.head(3).to_string())
