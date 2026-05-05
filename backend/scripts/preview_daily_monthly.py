"""
预览日/月维度数据文件结构
"""
import pandas as pd
import os

DATA_DIR = r"F:\bi\海贝海\原始数据"

# Check daily data files
daily_files = [
    "店铺4月_日_20260503_5e79ed5891d064e4161b68a065551ae9.xlsx"
]

print("=" * 70)
print("日维度数据文件")
print("=" * 70)

for filename in daily_files:
    filepath = os.path.join(DATA_DIR, filename)
    if os.path.exists(filepath):
        print(f"\n文件: {filename}")
        try:
            df = pd.read_excel(filepath, nrows=3)
            print(f"  列数: {len(df.columns)}")
            print(f"  列名: {list(df.columns)[:10]}")
            print(f"  前2行:")
            print(df.head(2).to_string())
        except Exception as e:
            print(f"  读取失败: {e}")

# Check monthly data files
monthly_files = [
    "月汇总.xlsx",
    "智能选款_2026-04-01~2026-04-30.xlsx"
]

print("\n" + "=" * 70)
print("月维度数据文件")
print("=" * 70)

for filename in monthly_files:
    filepath = os.path.join(DATA_DIR, filename)
    if os.path.exists(filepath):
        print(f"\n文件: {filename}")
        try:
            df = pd.read_excel(filepath, nrows=3)
            print(f"  列数: {len(df.columns)}")
            print(f"  列名: {list(df.columns)[:10]}")
            print(f"  前2行:")
            print(df.head(2).to_string())
        except Exception as e:
            print(f"  读取失败: {e}")
