import pandas as pd
import os

data_dir = r'F:\bi\海贝海\原始数据'

# Check one smart selection file
files = [f for f in os.listdir(data_dir) if '智能选款' in f and f.endswith('.xlsx')]
if files:
    filepath = os.path.join(data_dir, files[0])
    print(f"检查文件: {files[0]}")
    
    xl = pd.ExcelFile(filepath)
    print(f"Sheet名称: {xl.sheet_names}")
    
    df = pd.read_excel(filepath, sheet_name=xl.sheet_names[0], nrows=5)
    print(f"\n列名 ({len(df.columns)}):")
    for i, col in enumerate(df.columns):
        print(f"  {i+1}. {col}")
    
    print(f"\n前3行数据:")
    print(df.head(3).to_string())
