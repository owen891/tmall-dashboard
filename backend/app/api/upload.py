from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import Optional, List

from app.core import get_db
from app.schemas import ResponseModel
from app.services import UploadService
from app.models import FileStorage

router = APIRouter(prefix="/upload", tags=["upload"])


@router.post("", response_model=ResponseModel)
async def upload_file(
    file: UploadFile = File(...),
    usage_type: str = Query("default", description="用途类型"),
    usage_id: Optional[int] = Query(None, description="关联ID"),
    created_by: Optional[str] = Query(None, description="创建者"),
    db: Session = Depends(get_db)
):
    """
    上传文件
    
    支持多种用途类型：
    - default: 默认（通用）
    - image: 图片
    - document: 文档
    - import: 导入文件
    """
    service = UploadService(db)
    file_storage = await service.upload_file(
        file=file,
        usage_type=usage_type,
        usage_id=usage_id,
        created_by=created_by
    )
    
    return ResponseModel(data=service.get_file_info(file_storage))


@router.post("/multiple", response_model=ResponseModel)
async def upload_multiple_files(
    files: List[UploadFile] = File(...),
    usage_type: str = Query("default", description="用途类型"),
    usage_id: Optional[int] = Query(None, description="关联ID"),
    created_by: Optional[str] = Query(None, description="创建者"),
    db: Session = Depends(get_db)
):
    """批量上传文件"""
    service = UploadService(db)
    results = []
    errors = []
    
    for file in files:
        try:
            file_storage = await service.upload_file(
                file=file,
                usage_type=usage_type,
                usage_id=usage_id,
                created_by=created_by
            )
            results.append(service.get_file_info(file_storage))
        except Exception as e:
            errors.append({
                "file_name": file.filename,
                "error": str(e)
            })
    
    return ResponseModel(data={
        "success": results,
        "errors": errors,
        "total": len(files),
        "success_count": len(results),
        "error_count": len(errors)
    })


@router.get("/{file_id}", response_model=ResponseModel)
async def get_file_info(
    file_id: int,
    db: Session = Depends(get_db)
):
    """获取文件信息"""
    service = UploadService(db)
    file_storage = service.get_file(file_id)
    
    if not file_storage:
        raise HTTPException(status_code=404, detail="文件不存在")
    
    return ResponseModel(data=service.get_file_info(file_storage))


@router.get("/download/{file_id}")
async def download_file(
    file_id: int,
    db: Session = Depends(get_db)
):
    """下载文件"""
    service = UploadService(db)
    file_storage = service.get_file(file_id)
    
    if not file_storage:
        raise HTTPException(status_code=404, detail="文件不存在")
    
    import os
    if not os.path.exists(file_storage.file_path):
        raise HTTPException(status_code=404, detail="文件已被删除")
    
    return FileResponse(
        path=file_storage.file_path,
        filename=file_storage.file_name,
        media_type=file_storage.mime_type or "application/octet-stream"
    )


@router.get("/list/{usage_type}", response_model=ResponseModel)
async def list_files(
    usage_type: str,
    usage_id: Optional[int] = Query(None, description="关联ID"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """获取文件列表"""
    service = UploadService(db)
    files = service.get_files_by_usage(usage_type, usage_id, limit, offset)
    
    return ResponseModel(data={
        "total": len(files),
        "items": [service.get_file_info(f) for f in files]
    })


@router.delete("/{file_id}", response_model=ResponseModel)
async def delete_file(
    file_id: int,
    delete_physical: bool = Query(True, description="是否删除物理文件"),
    db: Session = Depends(get_db)
):
    """删除文件"""
    service = UploadService(db)
    success = service.delete_file(file_id, delete_physical)
    
    if not success:
        raise HTTPException(status_code=404, detail="文件不存在")
    
    return ResponseModel(data={"message": "删除成功"})
