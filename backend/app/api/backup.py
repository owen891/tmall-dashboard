from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.schemas.common import ResponseModel
import os
import shutil
import sqlite3
from datetime import datetime
import json
import io

router = APIRouter(prefix="/backup", tags=["数据备份"])

BACKUP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "backups")

@router.get("/status", response_model=ResponseModel)
def get_backup_status():
    """获取备份状态"""
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR, exist_ok=True)
        return ResponseModel(data={
            "backup_dir": BACKUP_DIR,
            "backups": [],
            "total_count": 0
        })
    
    backups = []
    for filename in os.listdir(BACKUP_DIR):
        filepath = os.path.join(BACKUP_DIR, filename)
        if os.path.isfile(filepath):
            stat = os.stat(filepath)
            backups.append({
                "filename": filename,
                "size": stat.st_size,
                "size_formatted": format_size(stat.st_size),
                "created_at": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat()
            })
    
    backups.sort(key=lambda x: x["modified_at"], reverse=True)
    
    return ResponseModel(data={
        "backup_dir": BACKUP_DIR,
        "backups": backups,
        "total_count": len(backups)
    })


@router.post("/create", response_model=ResponseModel)
def create_backup(db: Session = Depends(get_db)):
    """创建数据库备份"""
    try:
        if not os.path.exists(BACKUP_DIR):
            os.makedirs(BACKUP_DIR, exist_ok=True)
        
        db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "products.db")
        
        if not os.path.exists(db_path):
            raise HTTPException(status_code=404, detail="数据库文件不存在")
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"backup_{timestamp}.db"
        backup_path = os.path.join(BACKUP_DIR, backup_filename)
        
        shutil.copy2(db_path, backup_path)
        
        table_counts = {}
        tables = db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        for table in tables:
            table_name = table[0]
            count = db.execute(f"SELECT COUNT(*) FROM {table_name}").scalar()
            table_counts[table_name] = count
        
        metadata = {
            "created_at": datetime.now().isoformat(),
            "db_path": db_path,
            "tables": table_counts,
            "version": "2.0.0"
        }
        
        meta_filename = backup_filename.replace(".db", "_meta.json")
        meta_path = os.path.join(BACKUP_DIR, meta_filename)
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        
        return ResponseModel(data={
            "message": "备份创建成功",
            "backup_file": backup_filename,
            "metadata_file": meta_filename,
            "size": os.path.getsize(backup_path),
            "size_formatted": format_size(os.path.getsize(backup_path)),
            "tables": table_counts
        })
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"备份失败: {str(e)}")


@router.get("/download/{filename}", response_model=ResponseModel)
def download_backup(filename: str):
    """下载备份文件"""
    if ".." in filename or "/" in filename:
        raise HTTPException(status_code=400, detail="无效的文件名")
    
    backup_path = os.path.join(BACKUP_DIR, filename)
    
    if not os.path.exists(backup_path):
        raise HTTPException(status_code=404, detail="备份文件不存在")
    
    def iterfile():
        with open(backup_path, 'rb') as f:
            while chunk := f.read(8192):
                yield chunk
    
    return StreamingResponse(
        iterfile(),
        media_type='application/octet-stream',
        headers={
            'Content-Disposition': f'attachment; filename="{filename}"',
            'Access-Control-Expose-Headers': 'Content-Disposition'
        }
    )


@router.delete("/delete/{filename}", response_model=ResponseModel)
def delete_backup(filename: str):
    """删除备份文件"""
    if ".." in filename or "/" in filename:
        raise HTTPException(status_code=400, detail="无效的文件名")
    
    backup_path = os.path.join(BACKUP_DIR, filename)
    meta_path = backup_path.replace(".db", "_meta.json")
    
    deleted = []
    if os.path.exists(backup_path):
        os.remove(backup_path)
        deleted.append(filename)
    
    if os.path.exists(meta_path):
        os.remove(meta_path)
        deleted.append(os.path.basename(meta_path))
    
    if not deleted:
        raise HTTPException(status_code=404, detail="备份文件不存在")
    
    return ResponseModel(data={
        "message": "删除成功",
        "deleted_files": deleted
    })


@router.post("/restore/{filename}", response_model=ResponseModel)
def restore_backup(filename: str, db: Session = Depends(get_db)):
    """恢复备份"""
    if ".." in filename or "/" in filename:
        raise HTTPException(status_code=400, detail="无效的文件名")
    
    backup_path = os.path.join(BACKUP_DIR, filename)
    
    if not os.path.exists(backup_path):
        raise HTTPException(status_code=404, detail="备份文件不存在")
    
    try:
        conn = sqlite3.connect(backup_path)
        cursor = conn.cursor()
        
        tables = cursor.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        table_info = {}
        for table in tables:
            table_name = table[0]
            count = cursor.execute(f"SELECT COUNT(*) FROM {table_name}").scalar()
            table_info[table_name] = count
        
        conn.close()
        
        return ResponseModel(data={
            "message": "备份文件验证成功",
            "filename": filename,
            "tables": table_info,
            "note": "实际恢复功能需要在服务器上手动执行"
        })
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"验证备份失败: {str(e)}")


@router.post("/export-config", response_model=ResponseModel)
def export_config():
    """导出系统配置"""
    config_data = {
        "exported_at": datetime.now().isoformat(),
        "version": "2.0.0",
        "settings": {
            "system": {
                "name": "数据仪表盘",
                "timezone": "Asia/Shanghai"
            },
            "features": [
                "dashboard", "products", "import", "kpi", "trends",
                "ads", "health", "operations", "refunds", "alerts",
                "reviews", "market", "quadrant", "targets", "lifecycle",
                "compare", "recommendation", "report", "prediction",
                "data-quality", "settings"
            ]
        }
    }
    
    output = io.BytesIO()
    output.write(json.dumps(config_data, ensure_ascii=False, indent=2).encode('utf-8'))
    output.seek(0)
    
    filename = f"config_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    return StreamingResponse(
        output,
        media_type='application/json',
        headers={
            'Content-Disposition': f'attachment; filename="{filename}"',
            'Access-Control-Expose-Headers': 'Content-Disposition'
        }
    )


def format_size(size_bytes):
    """格式化文件大小"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"
