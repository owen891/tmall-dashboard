from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime
import os
import shutil
from typing import List, Optional

from app.core.database import get_db

router = APIRouter(prefix="/backup", tags=["backup"])

BACKUP_DIR = "data/backups"
DATABASE_PATH = "data/dashboard.db"

class BackupInfo(BaseModel):
    id: int
    file_name: str
    file_path: str
    file_size: int
    created_at: datetime
    backup_type: str
    note: Optional[str] = None

class BackupCreate(BaseModel):
    note: Optional[str] = None
    backup_type: str = "manual"

class BackupRestore(BaseModel):
    backup_id: int

@router.get("/list")
async def list_backups(db: Session = Depends(get_db)):
    """获取备份列表"""
    try:
        if not os.path.exists(BACKUP_DIR):
            os.makedirs(BACKUP_DIR)
        
        backups = []
        if os.path.exists(BACKUP_DIR):
            files = sorted(
                os.listdir(BACKUP_DIR),
                key=lambda x: os.path.getmtime(os.path.join(BACKUP_DIR, x)),
                reverse=True
            )
            
            for idx, file in enumerate(files):
                if file.endswith('.db'):
                    file_path = os.path.join(BACKUP_DIR, file)
                    stat = os.stat(file_path)
                    
                    backups.append({
                        "id": idx + 1,
                        "file_name": file,
                        "file_path": file_path,
                        "file_size": stat.st_size,
                        "created_at": datetime.fromtimestamp(stat.st_mtime),
                        "backup_type": "manual" if "manual" in file else "auto",
                        "note": None
                    })
        
        return {
            "code": 200,
            "message": "success",
            "data": {
                "backups": backups,
                "total": len(backups)
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/create")
async def create_backup(
    backup_data: BackupCreate,
    db: Session = Depends(get_db)
):
    """创建备份"""
    try:
        if not os.path.exists(BACKUP_DIR):
            os.makedirs(BACKUP_DIR)
        
        if not os.path.exists(DATABASE_PATH):
            raise HTTPException(status_code=404, detail="数据库文件不存在")
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_type = backup_data.backup_type or "manual"
        backup_file = f"dashboard_{backup_type}_{timestamp}.db"
        backup_path = os.path.join(BACKUP_DIR, backup_file)
        
        shutil.copy2(DATABASE_PATH, backup_path)
        
        stat = os.stat(backup_path)
        
        return {
            "code": 200,
            "message": "备份创建成功",
            "data": {
                "file_name": backup_file,
                "file_path": backup_path,
                "file_size": stat.st_size,
                "created_at": datetime.now(),
                "backup_type": backup_type,
                "note": backup_data.note
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/restore/{backup_id}")
async def restore_backup(
    backup_id: int,
    db: Session = Depends(get_db)
):
    """恢复备份"""
    try:
        if not os.path.exists(BACKUP_DIR):
            raise HTTPException(status_code=404, detail="备份目录不存在")
        
        files = sorted(
            os.listdir(BACKUP_DIR),
            key=lambda x: os.path.getmtime(os.path.join(BACKUP_DIR, x)),
            reverse=True
        )
        
        if backup_id < 1 or backup_id > len(files):
            raise HTTPException(status_code=404, detail="备份文件不存在")
        
        backup_file = files[backup_id - 1]
        backup_path = os.path.join(BACKUP_DIR, backup_file)
        
        if not os.path.exists(DATABASE_PATH):
            raise HTTPException(status_code=404, detail="数据库文件不存在")
        
        current_backup = f"dashboard_before_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        current_backup_path = os.path.join(BACKUP_DIR, current_backup)
        shutil.copy2(DATABASE_PATH, current_backup_path)
        
        shutil.copy2(backup_path, DATABASE_PATH)
        
        return {
            "code": 200,
            "message": "备份恢复成功",
            "data": {
                "restored_from": backup_file,
                "current_backup": current_backup
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{backup_id}")
async def delete_backup(
    backup_id: int,
    db: Session = Depends(get_db)
):
    """删除备份"""
    try:
        if not os.path.exists(BACKUP_DIR):
            raise HTTPException(status_code=404, detail="备份目录不存在")
        
        files = sorted(
            os.listdir(BACKUP_DIR),
            key=lambda x: os.path.getmtime(os.path.join(BACKUP_DIR, x)),
            reverse=True
        )
        
        if backup_id < 1 or backup_id > len(files):
            raise HTTPException(status_code=404, detail="备份文件不存在")
        
        backup_file = files[backup_id - 1]
        backup_path = os.path.join(BACKUP_DIR, backup_file)
        
        os.remove(backup_path)
        
        return {
            "code": 200,
            "message": "备份删除成功"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/download/{backup_id}")
async def download_backup(
    backup_id: int,
    db: Session = Depends(get_db)
):
    """下载备份"""
    try:
        if not os.path.exists(BACKUP_DIR):
            raise HTTPException(status_code=404, detail="备份目录不存在")
        
        files = sorted(
            os.listdir(BACKUP_DIR),
            key=lambda x: os.path.getmtime(os.path.join(BACKUP_DIR, x)),
            reverse=True
        )
        
        if backup_id < 1 or backup_id > len(files):
            raise HTTPException(status_code=404, detail="备份文件不存在")
        
        backup_file = files[backup_id - 1]
        backup_path = os.path.join(BACKUP_DIR, backup_file)
        
        from fastapi.responses import FileResponse
        
        return FileResponse(
            backup_path,
            media_type='application/octet-stream',
            filename=backup_file
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/auto-backup")
async def auto_backup(db: Session = Depends(get_db)):
    """自动备份（定时任务调用）"""
    try:
        if not os.path.exists(BACKUP_DIR):
            os.makedirs(BACKUP_DIR)
        
        if not os.path.exists(DATABASE_PATH):
            return {"code": 404, "message": "数据库文件不存在"}
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = f"dashboard_auto_{timestamp}.db"
        backup_path = os.path.join(BACKUP_DIR, backup_file)
        
        shutil.copy2(DATABASE_PATH, backup_path)
        
        files = sorted(os.listdir(BACKUP_DIR))
        auto_backups = [f for f in files if f.startswith("dashboard_auto_")]
        
        if len(auto_backups) > 30:
            for old_file in auto_backups[:-30]:
                os.remove(os.path.join(BACKUP_DIR, old_file))
        
        return {
            "code": 200,
            "message": "自动备份成功",
            "data": {
                "file_name": backup_file,
                "created_at": datetime.now()
            }
        }
    except Exception as e:
        return {"code": 500, "message": str(e)}
