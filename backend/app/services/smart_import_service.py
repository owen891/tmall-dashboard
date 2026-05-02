import os
import re
import json
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from sqlalchemy.orm import Session
import openai
from openai import OpenAI

from app.models import Product, WeeklyData, ImportHistory
from app.services import ExcelImportService


class SmartImportService:
    """AI智能导入服务"""
    
    def __init__(self, db: Session, api_key: str = None):
        self.db = db
        self.client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))
        self.import_service = ExcelImportService(db)
        
        self.file_patterns = {
            "weekly_data": ["周度", "weekly", "单品", "商品数据", "销售数据"],
            "market_analysis": ["市场分析", "市场", "关键词", "market", "keyword"],
            "reviews": ["评价", "评论", "review", "feedback"],
            "orders": ["订单", "order", "交易"],
            "products": ["商品", "product", "商品列表"]
        }
        
        self.key_columns = {
            "weekly_data": ["商品ID", "商品标题", "支付金额", "访客数", "支付转化率"],
            "market_analysis": ["关键词", "搜索人气", "点击率", "转化率"],
            "reviews": ["评价内容", "评分", "评价时间"],
            "orders": ["订单号", "订单金额", "下单时间"],
            "products": ["商品ID", "商品标题", "商品类目"]
        }
    
    def scan_folder(self, folder_path: str) -> List[Dict[str, Any]]:
        """扫描文件夹，识别可导入的文件"""
        if not os.path.exists(folder_path):
            return []
        
        files = []
        for root, dirs, filenames in os.walk(folder_path):
            for filename in filenames:
                if filename.endswith(('.xlsx', '.xls', '.csv')):
                    filepath = os.path.join(root, filename)
                    file_info = self._analyze_file(filepath)
                    files.append(file_info)
        
        return files
    
    def _analyze_file(self, filepath: str) -> Dict[str, Any]:
        """分析文件，识别类型和内容"""
        filename = os.path.basename(filepath)
        file_size = os.path.getsize(filepath)
        
        file_info = {
            "filepath": filepath,
            "filename": filename,
            "file_size": file_size,
            "file_type": None,
            "confidence": 0,
            "sheets": [],
            "preview": None,
            "suggested_type": None,
            "can_import": False
        }
        
        try:
            if filepath.endswith('.csv'):
                df = pd.read_csv(filepath)
                sheets = [{"name": "csv_data", "columns": list(df.columns), "rows": len(df)}]
            else:
                xl = pd.ExcelFile(filepath)
                sheets = []
                for sheet_name in xl.sheet_names:
                    df = pd.read_excel(filepath, sheet_name=sheet_name)
                    sheets.append({
                        "name": sheet_name,
                        "columns": list(df.columns),
                        "rows": len(df)
                    })
            
            file_info["sheets"] = sheets
            
            file_type, confidence = self._identify_file_type(filename, sheets)
            file_info["file_type"] = file_type
            file_info["confidence"] = confidence
            file_info["suggested_type"] = file_type
            file_info["can_import"] = confidence > 0.5
            
            if sheets:
                first_sheet = sheets[0]
                if filepath.endswith('.csv'):
                    df = pd.read_csv(filepath)
                else:
                    df = pd.read_excel(filepath, sheet_name=first_sheet["name"])
                
                file_info["preview"] = {
                    "columns": list(df.columns),
                    "sample_data": df.head(5).fillna('').to_dict(orient='records')
                }
        
        except Exception as e:
            file_info["error"] = str(e)
        
        return file_info
    
    def _identify_file_type(self, filename: str, sheets: List[Dict]) -> Tuple[str, float]:
        """识别文件类型"""
        filename_lower = filename.lower()
        
        scores = {}
        for file_type, patterns in self.file_patterns.items():
            score = 0
            for pattern in patterns:
                if pattern.lower() in filename_lower:
                    score += 0.3
            
            for sheet in sheets:
                columns = [col.lower() for col in sheet.get("columns", [])]
                key_cols = self.key_columns.get(file_type, [])
                
                matching_cols = sum(1 for key_col in key_cols 
                                   if any(key_col.lower() in col for col in columns))
                
                if key_cols:
                    col_score = matching_cols / len(key_cols)
                    score += col_score * 0.7
            
            scores[file_type] = min(score, 1.0)
        
        if not scores:
            return "unknown", 0
        
        best_type = max(scores, key=scores.get)
        confidence = scores[best_type]
        
        return best_type, confidence
    
    def ai_analyze_file(self, filepath: str) -> Dict[str, Any]:
        """使用AI深度分析文件内容"""
        try:
            if filepath.endswith('.csv'):
                df = pd.read_csv(filepath)
            else:
                xl = pd.ExcelFile(filepath)
                df = pd.read_excel(filepath, sheet_name=xl.sheet_names[0])
            
            sample_data = df.head(10).to_string()
            columns = ", ".join(df.columns.tolist())
            
            prompt = f"""分析这个数据文件，识别它的类型和用途。

文件名: {os.path.basename(filepath)}
列名: {columns}

前10行数据:
{sample_data}

请回答以下问题：
1. 这个文件是什么类型的数据？（周度数据/市场分析/评价数据/订单数据/商品数据/其他）
2. 数据的主要用途是什么？
3. 有哪些重要字段？
4. 导入时需要注意什么？

请用JSON格式回答:
{{
    "file_type": "类型",
    "purpose": "用途说明",
    "key_fields": ["字段1", "字段2"],
    "import_notes": "导入注意事项",
    "confidence": 0.95
}}"""

            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "你是一个数据分析专家，擅长识别和分析各种业务数据文件。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3
            )
            
            content = response.choices[0].message.content
            
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                return result
        
        except Exception as e:
            return {
                "file_type": "unknown",
                "error": str(e),
                "confidence": 0
            }
        
        return {
            "file_type": "unknown",
            "confidence": 0
        }
    
    def smart_import(self, filepath: str, file_type: str = None, options: Dict = None) -> Dict[str, Any]:
        """智能导入文件"""
        if not file_type:
            file_info = self._analyze_file(filepath)
            file_type = file_info.get("file_type")
            
            if not file_type or file_type == "unknown":
                ai_result = self.ai_analyze_file(filepath)
                file_type = ai_result.get("file_type", "weekly_data")
        
        options = options or {}
        
        result = {
            "filepath": filepath,
            "filename": os.path.basename(filepath),
            "file_type": file_type,
            "success": False,
            "message": "",
            "imported_count": 0
        }
        
        try:
            if file_type == "weekly_data":
                import_result = self.import_service.parse_weekly_data(
                    filepath, 
                    options.get("week_start")
                )
                
                if import_result.get("errors"):
                    result["message"] = "; ".join(import_result["errors"])
                    return result
                
                saved = self.import_service.save_to_db(import_result)
                
                result["success"] = True
                result["imported_count"] = saved.get("products", 0) + saved.get("weekly_data", 0)
                result["details"] = saved
                result["message"] = f"成功导入 {saved.get('products', 0)} 个商品，{saved.get('weekly_data', 0)} 条周度数据"
            
            elif file_type == "market_analysis":
                result["message"] = "市场分析数据导入功能开发中"
            
            elif file_type == "reviews":
                result["message"] = "评价数据导入功能开发中"
            
            else:
                result["message"] = f"暂不支持 {file_type} 类型的数据导入"
        
        except Exception as e:
            result["message"] = f"导入失败: {str(e)}"
        
        return result
    
    def batch_import(self, folder_path: str, auto_confirm: bool = False) -> List[Dict[str, Any]]:
        """批量导入文件夹中的所有文件"""
        files = self.scan_folder(folder_path)
        results = []
        
        for file_info in files:
            if not file_info.get("can_import"):
                results.append({
                    "filepath": file_info["filepath"],
                    "filename": file_info["filename"],
                    "success": False,
                    "message": "文件类型识别置信度过低，请手动确认"
                })
                continue
            
            import_result = self.smart_import(
                file_info["filepath"],
                file_info["file_type"]
            )
            results.append(import_result)
        
        return results
