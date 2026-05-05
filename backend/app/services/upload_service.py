import os
import mimetypes
from uuid import uuid4
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from fastapi import UploadFile, HTTPException

from app.models import FileStorage


class UploadService:
    """通用文件上传服务"""
    
    # 允许的文件扩展名（按用途分类）
    ALLOWED_EXTENSIONS = {
        "default": [".jpg", ".jpeg", ".png", ".gif", ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".csv", ".txt"],
        "image": [".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg"],
        "document": [".pdf", ".doc", ".docx", ".xls", ".xlsx", ".csv", ".txt", ".ppt", ".pptx"],
        "import": [".xls", ".xlsx", ".csv"],
    }
    
    # 最大文件大小（字节）- 默认50MB
    MAX_FILE_SIZE = {
        "default": 50 * 1024 * 1024,  # 50MB
        "image": 10 * 1024 * 1024,  # 10MB
        "document": 100 * 1024 * 1024,  # 100MB
        "import": 50 * 1024 * 1024,  # 50MB
    }
    
    def __init__(self, db: Session):
        self.db = db
    
    def _get_storage_dir(self, usage_type: str = "default") -> str:
        """获取存储目录"""
        date_str = datetime.now().strftime("%Y/%m/%d")
        base_dir = f"data/uploads/{usage_type}/{date_str}"
        os.makedirs(base_dir, exist_ok=True)
        return base_dir
    
    def _validate_file(self, file: UploadFile, usage_type: str = "default") -> None:
        """验证文件"""
        max_size = self.MAX_FILE_SIZE.get(usage_type, self.MAX_FILE_SIZE["default"])
        
        file_ext = os.path.splitext(file.filename)[1].lower() if file.filename else ""
        allowed_extensions = self.ALLOWED_EXTENSIONS.get(usage_type, self.ALLOWED_EXTENSIONS["default"])
        
        if file_ext not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"不支持的文件格式，仅支持：{', '.join(allowed_extensions)}"
            )
        
        MAGIC_BYTES = {
            '.xlsx': [b'PK\x03\x04'],
            '.xls': [b'\xd0\xcf\x11\xe0'],
            '.csv': [],
            '.pdf': [b'%PDF'],
            '.png': [b'\x89PNG'],
            '.jpg': [b'\xff\xd8\xff'],
            '.jpeg': [b'\xff\xd8\xff'],
        }
        
        if file_ext in MAGIC_BYTES and MAGIC_BYTES[file_ext]:
            self._pending_magic_check = (file_ext, MAGIC_BYTES[file_ext])
        else:
            self._pending_magic_check = None
    
    def _validate_magic_bytes(self, content: bytes, file_ext: str) -> None:
        MAGIC_BYTES = {
            '.xlsx': [b'PK\x03\x04'],
            '.xls': [b'\xd0\xcf\x11\xe0'],
            '.pdf': [b'%PDF'],
            '.png': [b'\x89PNG'],
            '.jpg': [b'\xff\xd8\xff'],
            '.jpeg': [b'\xff\xd8\xff'],
        }
        
        if file_ext in MAGIC_BYTES and MAGIC_BYTES[file_ext]:
            valid = any(content.startswith(sig) for sig in MAGIC_BYTES[file_ext])
            if not valid:
                raise HTTPException(
                    status_code=400,
                    detail=f"文件内容与扩展名不匹配，可能存在安全风险"
                )
    
    async def upload_file(
        self,
        file: UploadFile,
        usage_type: str = "default",
        usage_id: Optional[int] = None,
        created_by: Optional[str] = None,
        keep_original: bool = False
    ) -> FileStorage:
        """
        上传文件
        
        Args:
            file: 上传的文件
            usage_type: 用途类型
            usage_id: 关联ID
            created_by: 创建者
            keep_original: 是否保留原始文件（不自动删除）
            
        Returns:
            FileStorage对象
        """
        # 验证文件
        self._validate_file(file, usage_type)
        
        # 生成存储文件名
        file_ext = os.path.splitext(file.filename)[1].lower() if file.filename else ""
        storage_name = f"{uuid4()}{file_ext}"
        
        # 获取存储目录
        storage_dir = self._get_storage_dir(usage_type)
        file_path = os.path.join(storage_dir, storage_name)
        
        # 保存文件
        content = await file.read()
        
        # 验证文件大小
        max_size = self.MAX_FILE_SIZE.get(usage_type, self.MAX_FILE_SIZE["default"])
        if len(content) > max_size:
            raise HTTPException(
                status_code=400,
                detail=f"文件大小超过限制（最大{max_size / 1024 / 1024:.1f}MB）"
            )
        
        # 验证文件内容（magic bytes）
        self._validate_magic_bytes(content, file_ext)
        
        with open(file_path, "wb") as f:
            f.write(content)
        
        # 获取MIME类型
        mime_type, _ = mimetypes.guess_type(file.filename or "")
        
        # 创建文件记录
        file_storage = FileStorage(
            file_name=file.filename or "unknown",
            storage_name=storage_name,
            file_path=file_path,
            file_size=len(content),
            mime_type=mime_type,
            file_extension=file_ext,
            usage_type=usage_type,
            usage_id=usage_id,
            created_by=created_by
        )
        
        self.db.add(file_storage)
        self.db.commit()
        self.db.refresh(file_storage)
        
        return file_storage
    
    def get_file(self, file_id: int) -> Optional[FileStorage]:
        """获取文件记录"""
        return self.db.query(FileStorage).filter(FileStorage.id == file_id).first()
    
    def get_files_by_usage(
        self,
        usage_type: str,
        usage_id: Optional[int] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[FileStorage]:
        """按用途获取文件列表"""
        query = self.db.query(FileStorage).filter(FileStorage.usage_type == usage_type)
        
        if usage_id is not None:
            query = query.filter(FileStorage.usage_id == usage_id)
        
        return query.order_by(FileStorage.created_at.desc()).offset(offset).limit(limit).all()
    
    def delete_file(self, file_id: int, delete_physical: bool = True) -> bool:
        """
        删除文件
        
        Args:
            file_id: 文件ID
            delete_physical: 是否删除物理文件
            
        Returns:
            是否成功
        """
        file_storage = self.get_file(file_id)
        if not file_storage:
            return False
        
        # 删除物理文件
        if delete_physical and os.path.exists(file_storage.file_path):
            try:
                os.remove(file_storage.file_path)
            except OSError:
                pass
        
        # 删除数据库记录
        self.db.delete(file_storage)
        self.db.commit()
        
        return True
    
    def get_file_info(self, file_storage: FileStorage) -> Dict[str, Any]:
        """获取文件信息字典"""
        return {
            "id": file_storage.id,
            "file_name": file_storage.file_name,
            "storage_name": file_storage.storage_name,
            "file_path": file_storage.file_path,
            "file_size": file_storage.file_size,
            "file_size_human": self._format_file_size(file_storage.file_size),
            "mime_type": file_storage.mime_type,
            "file_extension": file_storage.file_extension,
            "usage_type": file_storage.usage_type,
            "usage_id": file_storage.usage_id,
            "created_by": file_storage.created_by,
            "created_at": file_storage.created_at.isoformat() if file_storage.created_at else None,
            "updated_at": file_storage.updated_at.isoformat() if file_storage.updated_at else None
        }
    
    def _format_file_size(self, size: int) -> str:
        """格式化文件大小为人类可读格式"""
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"
