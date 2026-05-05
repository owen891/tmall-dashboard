from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
import os

from app.core import get_db
from app.schemas import ResponseModel
from app.services import SmartImportService

router = APIRouter(prefix="/smart-import", tags=["smart-import"])

ALLOWED_BASE_DIRS = [
    os.path.abspath("data/raw"),
    os.path.abspath("data"),
]


def validate_path(path: str) -> str:
    abs_path = os.path.abspath(path)
    for base_dir in ALLOWED_BASE_DIRS:
        if abs_path.startswith(base_dir):
            return abs_path
    raise HTTPException(
        status_code=403,
        detail="Access denied: path outside allowed directories"
    )


@router.post("/scan", response_model=ResponseModel)
async def scan_folder(
    folder_path: str = Query(..., description="要扫描的文件夹路径"),
    db: Session = Depends(get_db)
):
    """扫描文件夹，识别可导入的文件"""
    safe_path = validate_path(folder_path)
    if not os.path.exists(safe_path):
        raise HTTPException(status_code=400, detail="文件夹不存在")
    
    service = SmartImportService(db)
    files = service.scan_folder(safe_path)
    
    return ResponseModel(data={
        "folder": folder_path,
        "total": len(files),
        "files": files
    })


@router.post("/analyze/{file_id}", response_model=ResponseModel)
async def analyze_file(
    filepath: str,
    use_ai: bool = Query(True, description="是否使用AI分析"),
    db: Session = Depends(get_db)
):
    """深度分析文件"""
    safe_path = validate_path(filepath)
    if not os.path.exists(safe_path):
        raise HTTPException(status_code=404, detail="文件不存在")
    
    service = SmartImportService(db)
    
    result = service._analyze_file(safe_path)
    
    if use_ai:
        ai_result = service.ai_analyze_file(safe_path)
        result["ai_analysis"] = ai_result
    
    return ResponseModel(data=result)


@router.post("/import", response_model=ResponseModel)
async def smart_import_file(
    filepath: str = Query(..., description="文件路径"),
    file_type: Optional[str] = Query(None, description="文件类型（不指定则自动识别）"),
    week_start: Optional[str] = Query(None, description="周开始日期"),
    db: Session = Depends(get_db)
):
    """智能导入单个文件"""
    safe_path = validate_path(filepath)
    if not os.path.exists(safe_path):
        raise HTTPException(status_code=404, detail="文件不存在")
    
    service = SmartImportService(db)
    
    options = {}
    if week_start:
        options["week_start"] = week_start
    
    result = service.smart_import(safe_path, file_type, options)
    
    if result["success"]:
        return ResponseModel(data=result, message=result["message"])
    else:
        return ResponseModel(code=400, message=result["message"], data=result)


@router.post("/batch-import", response_model=ResponseModel)
async def batch_import_files(
    folder_path: str = Query(..., description="文件夹路径"),
    auto_confirm: bool = Query(False, description="是否自动确认导入"),
    db: Session = Depends(get_db)
):
    """批量导入文件夹中的所有文件"""
    safe_path = validate_path(folder_path)
    if not os.path.exists(safe_path):
        raise HTTPException(status_code=400, detail="文件夹不存在")
    
    service = SmartImportService(db)
    results = service.batch_import(safe_path, auto_confirm)
    
    success_count = sum(1 for r in results if r.get("success"))
    failed_count = len(results) - success_count
    
    return ResponseModel(data={
        "folder": folder_path,
        "total": len(results),
        "success_count": success_count,
        "failed_count": failed_count,
        "results": results
    })


@router.get("/supported-types", response_model=ResponseModel)
async def get_supported_types():
    """获取支持的数据类型"""
    return ResponseModel(data={
        "types": [
            {
                "id": "weekly_data",
                "name": "周度数据",
                "description": "商品周度运营数据",
                "key_columns": ["商品ID", "商品标题", "支付金额", "访客数", "支付转化率"]
            },
            {
                "id": "market_analysis",
                "name": "市场分析",
                "description": "市场关键词分析数据",
                "key_columns": ["关键词", "搜索人气", "点击率", "转化率"]
            },
            {
                "id": "reviews",
                "name": "评价数据",
                "description": "商品评价数据",
                "key_columns": ["评价内容", "评分", "评价时间"]
            },
            {
                "id": "orders",
                "name": "订单数据",
                "description": "订单交易数据",
                "key_columns": ["订单号", "订单金额", "下单时间"]
            },
            {
                "id": "products",
                "name": "商品数据",
                "description": "商品基础信息",
                "key_columns": ["商品ID", "商品标题", "商品类目"]
            }
        ]
    })
