#!/usr/bin/env python3
"""
导入真实数据
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core import SessionLocal
from app.services import ExcelImportService
from datetime import date

def main():
    print("正在导入真实数据...")
    
    excel_files = [
        "/workspace/legacy/data/raw/828e389b-d3e5-416c-9b24-5235f39417b0_海贝海-数据分析表-周.xlsx"
    ]
    
    db = SessionLocal()
    import_service = ExcelImportService(db)
    
    total_saved = {"products": 0, "weekly_data": 0, "actions": 0}
    
    for file_path in excel_files:
        if not os.path.exists(file_path):
            print(f"文件不存在: {file_path}")
            continue
        
        print(f"正在解析: {file_path}")
        try:
            parsed = import_service.parse_weekly_data(file_path, week_start=date(2026,4,20))
            print(f"解析完成: {len(parsed['products'])}个商品, {len(parsed['weekly_data'])}条数据")
            saved = import_service.save_to_db(parsed)
            print(f"保存成功: {saved}")
            
            total_saved["products"] += saved.get("products", 0)
            total_saved["weekly_data"] += saved.get("weekly_data", 0)
            total_saved["actions"] += saved.get("actions", 0)
        except Exception as e:
            print(f"导入失败: {e}")
            import traceback
            traceback.print_exc()
    db.close()
    
    print("=" * 40)
    print("导入完成!")
    print(f"总商品数: {total_saved['products']}")
    print(f"总数据条数: {total_saved['weekly_data']}")
    print("=" * 40)

if __name__ == "__main__":
    main()
