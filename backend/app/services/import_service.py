import pandas as pd
from typing import List, Dict, Any, Optional
from datetime import datetime, date
from sqlalchemy.orm import Session
from app.models import Product, WeeklyData
import os


class ExcelImportService:
    def __init__(self, db: Session):
        self.db = db
    
    def _read_file(self, file_path: str) -> Dict[str, pd.DataFrame]:
        """读取文件，支持Excel和CSV"""
        file_ext = os.path.splitext(file_path)[1].lower()
        
        if file_ext in ['.xlsx', '.xls']:
            xl = pd.ExcelFile(file_path)
            return {sheet: pd.read_excel(file_path, sheet_name=sheet) for sheet in xl.sheet_names}
        elif file_ext == '.csv':
            return {'csv_data': pd.read_csv(file_path)}
        else:
            raise ValueError(f"不支持的文件格式: {file_ext}")
    
    def preview_data(self, file_path: str) -> Dict[str, Any]:
        """预览数据"""
        sheets = self._read_file(file_path)
        
        total_rows = 0
        preview = {
            "sheets": list(sheets.keys()),
            "data": {}
        }
        
        for sheet_name, df in sheets.items():
            # 获取前10行数据进行预览
            preview_rows = min(10, len(df))
            total_rows += len(df)
            preview["data"][sheet_name] = {
                "columns": list(df.columns),
                "rows": preview_rows,
                "totalRows": len(df),
                "sampleData": df.head(preview_rows).fillna('').to_dict(orient='records')
            }
        
        preview["totalRows"] = total_rows
        return preview
    
    def parse_weekly_data(self, file_path: str, week_start: Optional[date] = None) -> Dict[str, Any]:
        sheets = self._read_file(file_path)
        
        results = {
            "products": [],
            "weekly_data": [],
            "actions": [],
            "errors": []
        }
        
        # 尝试多个可能的sheet名称
        possible_sheets = ["单品-新", "csv_data", "Sheet1", "sheet1"]
        target_sheet = None
        
        for sheet in possible_sheets:
            if sheet in sheets:
                target_sheet = sheet
                break
        
        if target_sheet:
            try:
                df = sheets[target_sheet]
                product_data = self._parse_product_sheet(df, week_start)
                results["products"].extend(product_data["products"])
                results["weekly_data"].extend(product_data["weekly_data"])
                results["actions"].extend(product_data["actions"])
            except Exception as e:
                results["errors"].append(f"解析{target_sheet}失败: {str(e)}")
        else:
            results["errors"].append(f"未找到有效的数据sheet，可用的sheet: {list(sheets.keys())}")
        
        return results
    
    def _parse_product_sheet(self, df: pd.DataFrame, week_start: Optional[date] = None) -> Dict[str, Any]:
        products = []
        weekly_data_list = []
        actions = []
        
        for _, row in df.iterrows():
            if pd.isna(row.get("商品ID")):
                continue
            
            product_id = str(row["商品ID"])
            
            product_data = {
                "product_id": product_id,
                "title": str(row.get("商品标题", "")),
                "category": str(row.get("商品类目", "")),
                "tier": str(row.get("分层", "")),
                "style": str(row.get("风格", "")),
                "scene": str(row.get("场景", "")),
            }
            
            list_date = row.get("上架时间")
            if pd.notna(list_date):
                if isinstance(list_date, datetime):
                    product_data["list_date"] = list_date.date()
                else:
                    try:
                        product_data["list_date"] = pd.to_datetime(list_date).date()
                    except:
                        pass
            
            products.append(product_data)
            
            history_data = {}
            for year in ["25", "26"]:
                for month in range(1, 13):
                    col_name = f"{year}年-{month}月"
                    if col_name in row:
                        val = row.get(col_name)
                        if pd.notna(val):
                            history_data[f"{year}_{month}"] = float(val) if val else 0
            
            week_data = {
                "product_id": product_id,
                "week_start": week_start or date.today(),
                "payment_amount": float(row.get("支付金额", 0)) or 0,
                "refund_amount": float(row.get("退款金额", 0)) or 0,
                "net_sales": float(row.get("净销售/GSV", 0)) or 0,
                "gsv_change": float(row.get("GSV环比", 0)) or 0,
                "ad_spend": float(row.get("总推广花费", 0)) or 0,
                "ad_spend_change": float(row.get("环比", 0)) or 0,
                "total_roi": float(row.get("总投产", 0)) or 0,
                "direct_roi": float(row.get("推广直接ROI", 0)) or 0,
                "direct_roi_change": float(row.get("直接ROI环比", 0)) or 0,
                "refund_ad_ratio": float(row.get("退款付费占比", 0)) or 0,
                "visitors": int(row.get("访客数", 0)) or 0,
                "uv_value": float(row.get("UV价值", 0)) or 0,
                "payment_conversion": float(row.get("支付转化率", 0)) or 0,
                "refund_rate": float(row.get("退款率", 0)) or 0,
                "cart_rate": float(row.get("加购率", 0)) or 0,
                "cart_qty": int(row.get("加购件数", 0)) or 0,
                "payment_users": int(row.get("支付人数", 0)) or 0,
                "avg_order_value": float(row.get("客单价", 0)) or 0,
                "lead_potential_ratio": float(row.get("引潜比", 0)) or 0,
                "new_customer_cost": float(row.get("拉新成本", 0)) or 0,
                "direct_cart_cost": float(row.get("直接加购成本", 0)) or 0,
                "total_cart_cost": float(row.get("总加购成本", 0)) or 0,
                "repurchase_rate": float(row.get("复购率", 0)) or 0,
                "cross_sell_rate": float(row.get("连带率", 0)) or 0,
                "category_width": int(row.get("叶子类目宽度", 0)) or 0,
                "click_rate": float(row.get("点击率", 0)) or 0,
                "history_data": history_data,
                "data_source": "excel_import"
            }
            
            weekly_data_list.append(week_data)
            
            action_417 = row.get("4.17动作")
            if pd.notna(action_417) and str(action_417).strip():
                actions.append({
                    "product_id": product_id,
                    "action_date": date(2026, 4, 17) if week_start and week_start.year == 2026 else date.today(),
                    "action_detail": str(action_417),
                    "action_type": "operation"
                })
            
            action_421 = row.get("4.21动作")
            if pd.notna(action_421) and str(action_421).strip():
                actions.append({
                    "product_id": product_id,
                    "action_date": date(2026, 4, 21) if week_start and week_start.year == 2026 else date.today(),
                    "action_detail": str(action_421),
                    "action_type": "operation"
                })
        
        return {
            "products": products,
            "weekly_data": weekly_data_list,
            "actions": actions
        }
    
    def save_to_db(self, parsed_data: Dict[str, Any]) -> Dict[str, Any]:
        saved_count = {
            "products": 0,
            "weekly_data": 0,
            "actions": 0
        }
        
        for product_data in parsed_data.get("products", []):
            existing = self.db.query(Product).filter(
                Product.product_id == product_data["product_id"]).first()
            if existing:
                for key, value in product_data.items():
                    if key != "product_id":
                        setattr(existing, key, value)
                existing.updated_at = datetime.now()
            else:
                new_product = Product(**product_data)
                self.db.add(new_product)
            saved_count["products"] += 1
        
        self.db.commit()
        
        for week_data in parsed_data.get("weekly_data", []):
            existing = self.db.query(WeeklyData).filter(
                WeeklyData.product_id == week_data["product_id"],
                WeeklyData.week_start == week_data["week_start"]
            ).first()
            if existing:
                for key, value in week_data.items():
                    if key not in ["product_id", "week_start"]:
                        setattr(existing, key, value)
            else:
                new_week_data = WeeklyData(**week_data)
                self.db.add(new_week_data)
            saved_count["weekly_data"] += 1
        
        self.db.commit()
        
        return saved_count
