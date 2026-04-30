from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import date
import os
from uuid import uuid4

from app.core import get_db
from app.schemas import ResponseModel
from app.services import ExcelImportService

router = APIRouter(prefix="/import", tags=["import"])


@router.post("/excel", response_model=ResponseModel)
async def import_excel(
    file: UploadFile = File(...),
    week_start: date = Query(None, description="周开始日期"),
    db: Session = Depends(get_db)
):
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="只支持Excel文件")
    
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
            return ResponseModel(code=400, message="解析出错", data={"errors": parsed_data["errors"]})
        
        saved = service.save_to_db(parsed_data)
        
        return ResponseModel(data={
            "message": "导入成功",
            "saved": saved,
            "parsed": {
                "products": len(parsed_data.get("products", [])),
                "weekly_data": len(parsed_data.get("weekly_data", [])),
                "actions": len(parsed_data.get("actions", []))
            }
        })
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导入失败: {str(e)}")
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except:
                pass
