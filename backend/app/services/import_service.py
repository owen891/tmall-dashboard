import pandas as pd
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, date
from sqlalchemy.orm import Session
from app.models import Product, WeeklyData, ProductLifecycle, ProductLifecycleMeta, ImportHistory
import os


class DataValidationError(Exception):
    def __init__(self, message: str, row: int = None, column: str = None):
        self.message = message
        self.row = row
        self.column = column
        super().__init__(message)


class ImportResult:
    def __init__(self):
        self.success_count = {"products": 0, "weekly_data": 0, "actions": 0, "lifecycle": 0}
        self.error_count = 0
        self.errors: List[Dict[str, Any]] = []
        self.warnings: List[Dict[str, Any]] = []
        self.validation_errors: List[Dict[str, Any]] = []
        self.skipped_count = 0

    def add_error(self, message: str, row: int = None, column: str = None):
        self.errors.append({"message": message, "row": row, "column": column})
        self.error_count += 1

    def add_warning(self, message: str, row: int = None):
        self.warnings.append({"message": message, "row": row})

    def add_validation_error(self, message: str, row: int = None, column: str = None, value: Any = None):
        self.validation_errors.append({
            "message": message,
            "row": row,
            "column": column,
            "value": str(value)[:50] if value else None
        })


class ExcelImportService:
    def __init__(self, db: Session):
        self.db = db
        self.result = ImportResult()

    def _read_file(self, file_path: str) -> Dict[str, pd.DataFrame]:
        file_ext = os.path.splitext(file_path)[1].lower()

        if file_ext in ['.xlsx', '.xls']:
            xl = pd.ExcelFile(file_path)
            return {sheet: pd.read_excel(file_path, sheet_name=sheet) for sheet in xl.sheet_names}
        elif file_ext == '.csv':
            return {'csv_data': pd.read_csv(file_path)}
        else:
            raise ValueError(f"不支持的文件格式: {file_ext}")

    def preview_data(self, file_path: str) -> Dict[str, Any]:
        sheets = self._read_file(file_path)

        total_rows = 0
        preview = {
            "sheets": list(sheets.keys()),
            "data": {},
            "validation": {"valid": True, "errors": []}
        }

        for sheet_name, df in sheets.items():
            preview_rows = min(10, len(df))
            total_rows += len(df)

            validation_result = self._validate_dataframe(df, sheet_name)

            preview["data"][sheet_name] = {
                "columns": list(df.columns),
                "rows": preview_rows,
                "totalRows": len(df),
                "sampleData": df.head(preview_rows).fillna('').to_dict(orient='records'),
                "validation": validation_result
            }

            if validation_result["errors"]:
                preview["validation"]["valid"] = False
                preview["validation"]["errors"].extend(validation_result["errors"])

        preview["totalRows"] = total_rows
        return preview

    def _validate_dataframe(self, df: pd.DataFrame, sheet_name: str) -> Dict[str, Any]:
        errors = []

        if '商品ID' not in df.columns:
            errors.append("缺少必要列: 商品ID")

        if len(df) == 0:
            errors.append("文件为空，无数据行")
            return {"valid": False, "errors": errors}

        sample_size = min(20, len(df))
        invalid_ids = []
        for idx in range(sample_size):
            product_id = df.iloc[idx].get('商品ID')
            if pd.isna(product_id) or str(product_id).strip() == '':
                invalid_ids.append(idx + 1)

        if invalid_ids:
            errors.append(f"发现 {len(invalid_ids)} 行缺少商品ID（前{sample_size}行中）")

        numeric_columns = ['支付金额', '退款金额', '访客数', '支付转化率']
        for col in numeric_columns:
            if col in df.columns:
                invalid_values = []
                for idx in range(sample_size):
                    val = df.iloc[idx].get(col)
                    if pd.notna(val):
                        try:
                            float(val)
                        except (ValueError, TypeError):
                            invalid_values.append({'row': idx + 1, 'value': str(val)[:20]})

                if invalid_values:
                    errors.append(f"列 '{col}' 包含非数字值: {invalid_values[:3]}")

        return {"valid": len(errors) == 0, "errors": errors}

    def validate_data(self, file_path: str) -> Dict[str, Any]:
        preview = self.preview_data(file_path)
        return {
            "valid": preview["validation"]["valid"],
            "total_rows": preview["totalRows"],
            "errors": preview["validation"]["errors"],
            "sheets": preview["sheets"],
            "preview": {sheet: data["sampleData"] for sheet, data in preview["data"].items()}
        }

    def parse_weekly_data(self, file_path: str, week_start: Optional[date] = None) -> Dict[str, Any]:
        self.result = ImportResult()
        sheets = self._read_file(file_path)

        results = {
            "products": [],
            "weekly_data": [],
            "actions": [],
            "lifecycle": [],
            "lifecycle_meta": [],
            "errors": [],
            "warnings": []
        }

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
                results["lifecycle"].extend(product_data["lifecycle"])
                results["lifecycle_meta"].extend(product_data["lifecycle_meta"])
            except Exception as e:
                self.result.add_error(f"解析{target_sheet}失败: {str(e)}")
        else:
            self.result.add_error(f"未找到有效的数据sheet，可用的sheet: {list(sheets.keys())}")

        results["errors"] = self.result.errors
        results["warnings"] = self.result.warnings
        return results

    def _parse_product_sheet(self, df: pd.DataFrame, week_start: Optional[date] = None) -> Dict[str, Any]:
        products = []
        weekly_data_list = []
        actions = []
        lifecycle_list = []
        lifecycle_meta_list = []

        for idx, row in df.iterrows():
            row_num = idx + 2

            if pd.isna(row.get("商品ID")):
                self.result.add_warning(f"第 {row_num} 行缺少商品ID，跳过", row=row_num)
                continue

            product_id = str(row["商品ID"]).strip()

            product_data = {
                "product_id": product_id,
                "title": str(row.get("商品标题", "")),
                "category": str(row.get("商品类目", "")),
                "tier": str(row.get("分层", "")),
                "style": str(row.get("风格", "")),
                "scene": str(row.get("场景", "")),
                "manager": str(row.get("负责人", "")),
            }

            list_date = row.get("上架时间")
            if pd.notna(list_date):
                if isinstance(list_date, datetime):
                    product_data["list_date"] = list_date.date()
                else:
                    try:
                        product_data["list_date"] = pd.to_datetime(list_date).date()
                    except (ValueError, TypeError):
                        self.result.add_warning(f"第 {row_num} 行上架时间格式不正确", row=row_num)

            image_url = row.get("图片链接")
            if pd.notna(image_url):
                product_data["image_url"] = str(image_url)

            products.append(product_data)

            gsv_25_total = 0
            gsv_26_total = 0
            monthly_gsv_records = []

            for month in range(1, 13):
                col_25 = f"25年-{month}月"
                col_26 = f"26年-{month}月"

                if col_25 in row:
                    val = row.get(col_25)
                    if pd.notna(val):
                        try:
                            gsv_val = float(val) if val else 0
                            monthly_gsv_records.append({"year": 25, "month": month, "gsv": gsv_val})
                            gsv_25_total += gsv_val
                        except (ValueError, TypeError):
                            self.result.add_validation_error(
                                f"列 '{col_25}' 值无效", row=row_num, column=col_25, value=val
                            )

                if col_26 in row:
                    val = row.get(col_26)
                    if pd.notna(val):
                        try:
                            gsv_val = float(val) if val else 0
                            monthly_gsv_records.append({"year": 26, "month": month, "gsv": gsv_val})
                            gsv_26_total += gsv_val
                        except (ValueError, TypeError):
                            self.result.add_validation_error(
                                f"列 '{col_26}' 值无效", row=row_num, column=col_26, value=val
                            )

            if monthly_gsv_records:
                lifecycle_list.append({
                    "product_id": product_id,
                    "records": monthly_gsv_records
                })
                lifecycle_meta_list.append({
                    "product_id": product_id,
                    "gsv_25_total": gsv_25_total,
                    "gsv_26_total": gsv_26_total
                })

            history_data = {}
            for year in ["25", "26"]:
                for month in range(1, 13):
                    col_name = f"{year}年-{month}月"
                    if col_name in row:
                        val = row.get(col_name)
                        if pd.notna(val):
                            try:
                                history_data[f"{year}_{month}"] = float(val) if val else 0
                            except (ValueError, TypeError):
                                pass

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
            "actions": actions,
            "lifecycle": lifecycle_list,
            "lifecycle_meta": lifecycle_meta_list
        }

    def save_to_db(self, parsed_data: Dict[str, Any], force: bool = False) -> Dict[str, Any]:
        saved_count = {
            "products": 0,
            "weekly_data": 0,
            "actions": 0,
            "lifecycle": 0
        }
        skipped_count = 0

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

        self.db.flush()

        weekly_records_to_check = []
        for week_data in parsed_data.get("weekly_data", []):
            weekly_records_to_check.append((week_data["product_id"], week_data["week_start"]))

        if weekly_records_to_check and not force:
            existing_weekly = self.db.query(WeeklyData).filter(
                WeeklyData.product_id.in_([r[0] for r in weekly_records_to_check]),
                WeeklyData.week_start.in_([r[1] for r in weekly_records_to_check])
            ).all()

            existing_keys = set()
            for ew in existing_weekly:
                existing_keys.add((ew.product_id, ew.week_start.isoformat()))

            new_weekly_list = []
            for week_data in parsed_data.get("weekly_data", []):
                key = (week_data["product_id"], week_data["week_start"].isoformat())
                if key in existing_keys:
                    existing_record = self.db.query(WeeklyData).filter(
                        WeeklyData.product_id == week_data["product_id"],
                        WeeklyData.week_start == week_data["week_start"]
                    ).first()
                    if existing_record:
                        for key_field, value in week_data.items():
                            if key_field not in ["product_id", "week_start"]:
                                setattr(existing_record, key_field, value)
                        existing_record.updated_at = datetime.now()
                        saved_count["weekly_data"] += 1
                        skipped_count += 1
                        continue

                new_weekly_list.append(week_data)

            for week_data in new_weekly_list:
                new_week_data = WeeklyData(**week_data)
                self.db.add(new_week_data)
                saved_count["weekly_data"] += 1
        else:
            for week_data in parsed_data.get("weekly_data", []):
                existing = self.db.query(WeeklyData).filter(
                    WeeklyData.product_id == week_data["product_id"],
                    WeeklyData.week_start == week_data["week_start"]
                ).first()
                if existing:
                    for key, value in week_data.items():
                        if key not in ["product_id", "week_start"]:
                            setattr(existing, key, value)
                    existing.updated_at = datetime.now()
                else:
                    new_week_data = WeeklyData(**week_data)
                    self.db.add(new_week_data)
                saved_count["weekly_data"] += 1

        self.db.flush()

        for lifecycle_data in parsed_data.get("lifecycle", []):
            product_id = lifecycle_data["product_id"]
            records = lifecycle_data["records"]

            for record in records:
                existing = self.db.query(ProductLifecycle).filter(
                    ProductLifecycle.product_id == product_id,
                    ProductLifecycle.year == record["year"],
                    ProductLifecycle.month == record["month"]
                ).first()

                if existing:
                    existing.gsv = record["gsv"]
                    existing.updated_at = datetime.now()
                else:
                    new_lifecycle = ProductLifecycle(
                        product_id=product_id,
                        year=record["year"],
                        month=record["month"],
                        gsv=record["gsv"]
                    )
                    self.db.add(new_lifecycle)
                saved_count["lifecycle"] += 1

        for meta_data in parsed_data.get("lifecycle_meta", []):
            product_id = meta_data["product_id"]

            existing_meta = self.db.query(ProductLifecycleMeta).filter(
                ProductLifecycleMeta.product_id == product_id
            ).first()

            if existing_meta:
                existing_meta.gsv_25_total = meta_data["gsv_25_total"]
                existing_meta.gsv_26_total = meta_data["gsv_26_total"]
                existing_meta.updated_at = datetime.now()
            else:
                new_meta = ProductLifecycleMeta(
                    product_id=product_id,
                    gsv_25_total=meta_data["gsv_25_total"],
                    gsv_26_total=meta_data["gsv_26_total"]
                )
                self.db.add(new_meta)

        self.db.commit()

        return {
            "saved_count": saved_count,
            "skipped_count": skipped_count,
            "total": sum(saved_count.values())
        }
