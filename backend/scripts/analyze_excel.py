import pandas as pd
import os
import json

DATA_DIR = r"F:\bi\海贝海\原始数据"

files_to_check = [
    "TOP50-整体_20260503_9166c30f021ad924291e5f0f17d5276c.xlsx",
    "4月10-整体_20260503_866f50e4ba0dbd8a714b172bb47dddd6.xlsx",
    "top20整体_20260503_6b1d5d86e244e260cc6ab5b49b72567d.xlsx",
    "品类-整体_20260503_861a8ec8725f8a64cbdb42554a397565.xlsx",
    "店铺4月_日_20260503_5e79ed5891d064e4161b68a065551ae9.xlsx",
    "DMP2026-04-06至2026-04-12.xlsx",
    "智能选款_2026-05-03~2026-05-03.xlsx",
    "月汇总.xlsx",
    "top10来源_20260503_ac68d7d46e106d8e6d6294523434bf11.xlsx",
    "店铺-来源_20260503_9d8a0905e7f3839bc6ba5f75d180d670.xlsx",
    "品类-来源-月_20260503_2b8cef0f56abfd90868ca81fe3b27580.xlsx",
    "TOP10单品_20260503_b7ae45163bcca6d5a24ef919d7a0ad0e.xlsx",
]

output_file = os.path.join(os.path.dirname(__file__), "excel_analysis.json")
results = {}

for filename in files_to_check:
    filepath = os.path.join(DATA_DIR, filename)
    if not os.path.exists(filepath):
        print(f"[SKIP] 不存在: {filename}")
        continue
    
    print(f"\n{'='*80}")
    print(f"文件: {filename}")
    print(f"{'='*80}")
    
    try:
        xl = pd.ExcelFile(filepath)
        sheets = xl.sheet_names
        print(f"Sheet数量: {len(sheets)}")
        print(f"Sheet列表: {sheets}")
        
        file_data = {
            "sheets": sheets,
            "sheet_details": {}
        }
        
        for sheet in sheets[:3]:
            print(f"\n  --- Sheet: {sheet} ---")
            try:
                df = pd.read_excel(filepath, sheet_name=sheet, header=0)
                print(f"  行数: {len(df)}, 列数: {len(df.columns)}")
                print(f"  列名: {list(df.columns)}")
                print(f"  前3行数据:")
                print(df.head(3).to_string(index=False))
                
                file_data["sheet_details"][sheet] = {
                    "rows": len(df),
                    "columns": len(df.columns),
                    "column_names": list(df.columns),
                    "sample_data": df.head(3).to_dict(orient="records")
                }
            except Exception as e:
                print(f"  读取失败: {e}")
        
        results[filename] = file_data
        
    except Exception as e:
        print(f"读取失败: {e}")
        results[filename] = {"error": str(e)}

with open(output_file, "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2, default=str)

print(f"\n\n分析结果已保存到: {output_file}")
