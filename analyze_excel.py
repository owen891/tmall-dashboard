import pandas as pd
import os
from glob import glob

def analyze_excel(filepath):
    """分析单个Excel文件的结构"""
    filename = os.path.basename(filepath)
    print(f"\n{'='*80}")
    print(f"文件: {filename}")
    print(f"{'='*80}")

    try:
        # 读取所有sheet
        xls = pd.ExcelFile(filepath)
        print(f"Sheet数量: {len(xls.sheet_names)}")
        print(f"Sheet名称: {xls.sheet_names}")

        for sheet_name in xls.sheet_names:
            print(f"\n--- Sheet: '{sheet_name}' ---")
            df = pd.read_excel(filepath, sheet_name=sheet_name)

            # 基本信息
            print(f"数据行数: {len(df)} (不含表头)")
            print(f"列数: {len(df.columns)}")

            # 列名
            print(f"\n列名（字段名称）:")
            for i, col in enumerate(df.columns, 1):
                print(f"  {i}. {col}")

            # 数据类型
            print(f"\n数据类型:")
            dtype_info = df.dtypes
            for col, dtype in dtype_info.items():
                non_null = df[col].notna().sum()
                null_count = df[col].isna().sum()
                print(f"  {col}: {dtype} (非空: {non_null}, 空值: {null_count})")

            # 数据样例（前3行）
            print(f"\n数据样例（前3行）:")
            if len(df) > 0:
                sample = df.head(3)
                for idx, row in sample.iterrows():
                    print(f"\n  [行 {idx+1}]")
                    for col in df.columns:
                        val = row[col]
                        if pd.isna(val):
                            val_str = "<空值>"
                        else:
                            val_str = str(val)[:100]
                        print(f"    {col}: {val_str}")
            else:
                print("  <无数据>")

    except Exception as e:
        print(f"读取失败: {e}")

# 分析所有Excel文件
raw_dir = "/workspace/legacy/data/raw"
files = sorted(glob(os.path.join(raw_dir, "*.xlsx")))

print(f"发现 {len(files)} 个Excel文件")

# 先分析海贝海周报表
haibei_files = [f for f in files if "海贝海" in f]
zhineng_files = [f for f in files if "智能选款" in f]

# 分析海贝海文件
for f in haibei_files:
    analyze_excel(f)

# 分析几个代表性的智能选款文件（选不同日期的）
selected_zhineng = zhineng_files[:5]  # 前5个
for f in selected_zhineng:
    analyze_excel(f)

# 汇总所有智能选款文件的字段一致性
print(f"\n\n{'='*80}")
print("智能选款文件字段一致性检查")
print(f"{'='*80}")

all_columns = {}
for f in zhineng_files:
    fname = os.path.basename(f)
    try:
        df = pd.read_excel(f)
        all_columns[fname] = list(df.columns)
    except Exception as e:
        all_columns[fname] = f"ERROR: {e}"

# 检查是否所有文件列名一致
first_cols = None
consistent = True
for fname, cols in all_columns.items():
    if isinstance(cols, list):
        if first_cols is None:
            first_cols = cols
        elif cols != first_cols:
            consistent = False
            print(f"字段不一致: {fname}")

if consistent and first_cols is not None:
    print(f"所有 {len(all_columns)} 个智能选款文件字段完全一致")
    print(f"共同字段 ({len(first_cols)} 个):")
    for i, col in enumerate(first_cols, 1):
        print(f"  {i}. {col}")
else:
    print("字段存在差异，各文件字段如下:")
    for fname, cols in all_columns.items():
        print(f"\n{fname}:")
        if isinstance(cols, list):
            for c in cols:
                print(f"  - {c}")
        else:
            print(f"  {cols}")
