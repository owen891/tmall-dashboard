#!/usr/bin/env python3
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
from datetime import date

file_path = "/workspace/legacy/data/raw/828e389b-d3e5-416c-9b24-5235f39417b0_海贝海-数据分析表-周.xlsx"

print("测试解析...")
df = pd.read_excel(file_path, sheet_name="单品-新", header=0)

print(f"总行数: {len(df)}")
count = 0
for _, row in df.iterrows():
    if pd.isna(row.get("商品ID")):
        print(f"行 {count}: 无商品ID")
        count += 1
        if count > 5:
            break
        continue
    product_id = str(row["商品ID"])
    print(f"找到商品: {product_id} - {row.get('商品标题')}")
    count +=1
    if count >10:
        break
