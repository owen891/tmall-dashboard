from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from datetime import date, datetime
import os
from uuid import uuid4
import pandas as pd
from io import BytesIO

from app.core import get_db
from app.schemas import ResponseModel
from app.services import ExcelImportService
from app.models import ImportHistory

router = APIRouter(prefix="/import", tags=["import"])


@router.get("/template/{type}")
async def download_template(type: str = "weekly"):
    """下载导入模板"""
    if type == "weekly":
        # 创建周度数据模板
        df = pd.DataFrame({
            "商品ID": ["SPU001", "SPU002"],
            "商品标题": ["示例商品1", "示例商品2"],
            "商品类目": ["连衣裙", "T恤"],
            "分层": ["A", "B"],
            "风格": ["甜美", "休闲"],
            "场景": ["日常", "通勤"],
            "上架时间": ["2025-01-01", "2025-02-01"],
            "支付金额": [1000.0, 500.0],
            "退款金额": [50.0, 20.0],
            "净销售/GSV": [950.0, 480.0],
            "GSV环比": [0.1, -0.05],
            "总推广花费": [200.0, 100.0],
            "环比": [0.05, -0.02],
            "总投产": [4.75, 4.8],
            "推广直接ROI": [3.5, 3.0],
            "直接ROI环比": [0.1, -0.05],
            "退款付费占比": [0.05, 0.04],
            "访客数": [1000, 500],
            "UV价值": [0.95, 0.96],
            "支付转化率": [0.1, 0.12],
            "退款率": [0.05, 0.04],
            "加购率": [0.2, 0.25],
            "加购件数": [200, 125],
            "支付人数": [100, 60],
            "客单价": [9.5, 8.0],
            "引潜比": [1.5, 1.2],
            "拉新成本": [50.0, 40.0],
            "直接加购成本": [10.0, 8.0],
            "总加购成本": [15.0, 12.0],
            "复购率": [0.3, 0.25],
            "连带率": [1.5, 1.3],
            "叶子类目宽度": [2, 1],
            "点击率": [0.05, 0.06],
            "4.17动作": ["调整价格", "优化主图"],
            "4.21动作": ["增加推广", ""]
        })
        
        # 创建内存中的Excel文件
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name="单品-新", index=False)
        output.seek(0)
        
        # 保存到临时文件
        temp_path = "data/templates/weekly_template.xlsx"
        os.makedirs(os.path.dirname(temp_path), exist_ok=True)
        with open(temp_path, "wb") as f:
            f.write(output.getvalue())
        
        return FileResponse(
            path=temp_path,
            filename="周度数据导入模板.xlsx",
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    
    raise HTTPException(status_code=400, detail="不支持的模板类型")


@router.post("/preview", response_model=ResponseModel)
async def preview_excel(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """预览Excel数据"""
    if not file.filename.endswith(('.xlsx', '.xls', '.csv')):
        raise HTTPException(status_code=400, detail="只支持Excel或CSV文件")
    
    os.makedirs("data/raw", exist_ok=True)
    file_extension = os.path.splitext(file.filename)[1]
    temp_filename = f"{uuid4()}{file_extension}"
    temp_path = os.path.join("data/raw", temp_filename)
    
    try:
        content = await file.read()
        with open(temp_path, "wb") as f:
            f.write(content)
        
        service = ExcelImportService(db)
        preview_data = service.preview_data(temp_path)
        
        return ResponseModel(data=preview_data)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"预览失败: {str(e)}")
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass


@router.post("/validate", response_model=ResponseModel)
async def validate_excel(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """验证Excel数据格式和内容"""
    if not file.filename.endswith(('.xlsx', '.xls', '.csv')):
        raise HTTPException(status_code=400, detail="只支持Excel或CSV文件")
    
    os.makedirs("data/raw", exist_ok=True)
    file_extension = os.path.splitext(file.filename)[1]
    temp_filename = f"{uuid4()}{file_extension}"
    temp_path = os.path.join("data/raw", temp_filename)
    
    try:
        content = await file.read()
        with open(temp_path, "wb") as f:
            f.write(content)
        
        service = ExcelImportService(db)
        validation_result = service.validate_data(temp_path)
        
        return ResponseModel(data=validation_result)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"验证失败: {str(e)}")
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass


@router.post("/excel", response_model=ResponseModel)
async def import_excel(
    file: UploadFile = File(...),
    week_start: date = Query(None, description="周开始日期"),
    import_type: str = Query("weekly", description="导入类型"),
    force: bool = Query(False, description="强制覆盖已存在数据"),
    db: Session = Depends(get_db)
):
    if not file.filename.endswith(('.xlsx', '.xls', '.csv')):
        raise HTTPException(status_code=400, detail="只支持Excel或CSV文件")
    
    os.makedirs("data/raw", exist_ok=True)
    file_extension = os.path.splitext(file.filename)[1]
    temp_filename = f"{uuid4()}{file_extension}"
    temp_path = os.path.join("data/raw", temp_filename)
    
    try:
        content = await file.read()
        with open(temp_path, "wb") as f:
            f.write(content)
        
        service = ExcelImportService(db)
        parsed_data = service.parse_weekly_data(temp_path, week_start)
        
        if parsed_data.get("errors"):
            # 保存失败记录
            history = ImportHistory(
                file_name=file.filename,
                import_type=import_type,
                status="failed",
                error_message="; ".join(parsed_data["errors"]),
                created_at=datetime.now()
            )
            db.add(history)
            db.commit()
            return ResponseModel(code=400, message="解析出错", data={"errors": parsed_data["errors"]})
        
        saved = service.save_to_db(parsed_data, force=force)
        
        # 保存成功记录
        history = ImportHistory(
            file_name=file.filename,
            import_type=import_type,
            status="success",
            product_count=len(parsed_data.get("products", [])),
            data_count=len(parsed_data.get("weekly_data", [])),
            created_at=datetime.now()
        )
        db.add(history)
        db.commit()
        
        return ResponseModel(data={
            "message": "导入成功",
            "saved": saved,
            "parsed": {
                "products": len(parsed_data.get("products", [])),
                "weekly_data": len(parsed_data.get("weekly_data", [])),
                "actions": len(parsed_data.get("actions", []))
            },
            "history_id": history.id
        })
        
    except Exception as e:
        # 保存失败记录
        try:
            history = ImportHistory(
                file_name=file.filename,
                import_type=import_type,
                status="failed",
                error_message=str(e),
                created_at=datetime.now()
            )
            db.add(history)
            db.commit()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"导入失败: {str(e)}")
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass


@router.get("/history", response_model=ResponseModel)
async def get_import_history(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """获取导入历史记录"""
    query = db.query(ImportHistory).order_by(ImportHistory.created_at.desc())
    total = query.count()
    histories = query.offset(offset).limit(limit).all()
    
    return ResponseModel(data={
        "total": total,
        "items": [
            {
                "id": h.id,
                "file_name": h.file_name,
                "import_type": h.import_type,
                "status": h.status,
                "product_count": h.product_count,
                "data_count": h.data_count,
                "error_message": h.error_message,
                "created_at": h.created_at.isoformat() if h.created_at else None
            }
            for h in histories
        ]
    })
