#!/usr/bin/env python3
import pandas as pd
import os

file_path = "/workspace/legacy/data/raw/828e389b-d3e5-416c-9b24-5235f39417b0_海贝海-数据分析表-周.xlsx"

print("详细检查单品-新 sheet...")
df = pd.read_excel(file_path, sheet_name="单品-新", header=0)
print(f"行数: {len(df)}")
print(f"列数: {len(df.columns)}")
print("\n列名:")
for i, col in enumerate(df.columns):
    print(f"{i}: {col}")

print("\n前10行商品ID:")
for i in range(min(10, len(df))):
    row = df.iloc[i]
    product_id = row.get('商品ID')
    title = row.get('商品标题')
    print(f"{i}: 商品ID={product_id}, 标题={title}")
