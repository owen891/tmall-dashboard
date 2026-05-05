#!/usr/bin/env python3
import pandas as pd
import os

file_path = "/workspace/legacy/data/raw/828e389b-d3e5-416c-9b24-5235f39417b0_海贝海-数据分析表-周.xlsx"

print("检查 Excel 文件...")
xl = pd.ExcelFile(file_path)
print(f"Sheet 名称: {xl.sheet_names}")

for sheet in xl.sheet_names:
    print(f"\n--- {sheet} ---")
    try:
        df = pd.read_excel(file_path, sheet_name=sheet)
        print(f"列名: {list(df.columns)[:20]}")
        print(f"行数: {len(df)}")
        if len(df) > 0:
            print("前3行数据:")
            print(df.head(3))
    except Exception as e:
        print(f"读取失败: {e}")
