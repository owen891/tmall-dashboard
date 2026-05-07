import pandas as pd
import os
from glob import glob

raw_dir = "/workspace/legacy/data/raw"
files = sorted(glob(os.path.join(raw_dir, "*.xlsx")))

print("=" * 80)
print("目录概览")
print("=" * 80)
print(f"共发现 {len(files)} 个Excel文件\n")

# ============== 1. 海贝海-数据分析表-周.xlsx ==============
haibei_path = [f for f in files if "海贝海" in f][0]
print("=" * 80)
print(f"文件: {os.path.basename(haibei_path)}")
print("=" * 80)

xls = pd.ExcelFile(haibei_path)
print(f"Sheet数量: {len(xls.sheet_names)}")
print(f"Sheet名称: {xls.sheet_names}\n")

# 分析每个sheet
for sheet in xls.sheet_names:
    df = pd.read_excel(haibei_path, sheet_name=sheet)
    print(f"--- Sheet: '{sheet}' ---")
    print(f"  数据行数: {len(df)} | 列数: {len(df.columns)}")
    if len(df) > 0 and len(df.columns) > 0:
        print(f"  列名: {list(df.columns)}")
        print(f"  前2行样例:")
        for idx in range(min(2, len(df))):
            row = df.iloc[idx]
            print(f"    行{idx+1}: {dict(row.head(5))}")
    print()

# ============== 2. 智能选款文件 ==============
zhineng_files = [f for f in files if "智能选款" in f]
print("\n" + "=" * 80)
print("智能选款文件概览")
print("=" * 80)
print(f"共 {len(zhineng_files)} 个文件\n")

# 读取第一个文件做详细分析
sample_file = zhineng_files[0]
print(f"详细分析文件: {os.path.basename(sample_file)}")
df = pd.read_excel(sample_file)
print(f"数据行数: {len(df)}")
print(f"列数: {len(df.columns)}\n")

print("字段列表:")
for i, col in enumerate(df.columns, 1):
    print(f"  {i:2d}. {col}")

print("\n数据类型及空值统计:")
for col in df.columns:
    dtype = df[col].dtype
    non_null = df[col].notna().sum()
    null_count = df[col].isna().sum()
    print(f"  {col}: {dtype} (非空{non_null}, 空值{null_count})")

print("\n前3行数据样例:")
print(df.head(3).to_string())

# 所有智能选款文件一致性检查
print("\n" + "=" * 80)
print("智能选款文件一致性检查")
print("=" * 80)
all_cols = []
for f in zhineng_files:
    d = pd.read_excel(f)
    all_cols.append(list(d.columns))

if all(c == all_cols[0] for c in all_cols):
    print(f"✓ 所有 {len(zhineng_files)} 个文件字段完全一致 ({len(all_cols[0])} 个字段)")
else:
    print("✗ 字段存在差异")

# 各文件行数统计
print("\n各文件数据行数:")
for f in zhineng_files:
    d = pd.read_excel(f)
    print(f"  {os.path.basename(f)}: {len(d)} 行")
