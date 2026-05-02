from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Dict, Any

from app.core import get_db
from app.schemas import ResponseModel
from app.services import SettingService

router = APIRouter(prefix="/settings", tags=["settings"])


class SettingsUpdate(BaseModel):
    settings: Dict[str, Any]


@router.get("", response_model=ResponseModel)
async def get_settings(db: Session = Depends(get_db)):
    """获取所有设置"""
    service = SettingService(db)
    settings = service.get_all_settings()
    return ResponseModel(data=settings)


@router.get("/{key}", response_model=ResponseModel)
async def get_setting(key: str, db: Session = Depends(get_db)):
    """获取单个设置"""
    service = SettingService(db)
    value = service.get_setting(key)
    if value is None:
        raise HTTPException(status_code=404, detail="设置不存在")
    return ResponseModel(data={key: value})


@router.put("", response_model=ResponseModel)
async def update_settings(update: SettingsUpdate, db: Session = Depends(get_db)):
    """批量更新设置"""
    service = SettingService(db)
    service.set_settings(update.settings)
    return ResponseModel(data=update.settings, message="设置已保存")


@router.put("/{key}", response_model=ResponseModel)
async def update_setting(key: str, value: Any = Body(...), db: Session = Depends(get_db)):
    """更新单个设置"""
    service = SettingService(db)
    service.set_setting(key, value)
    return ResponseModel(data={key: value}, message="设置已保存")


@router.post("/initialize", response_model=ResponseModel)
async def initialize_settings(db: Session = Depends(get_db)):
    """初始化默认设置"""
    service = SettingService(db)
    service.initialize_default_settings()
    settings = service.get_all_settings()
    return ResponseModel(data=settings, message="默认设置已初始化")


@router.delete("/{key}", response_model=ResponseModel)
async def delete_setting(key: str, db: Session = Depends(get_db)):
    """删除设置"""
    service = SettingService(db)
    success = service.delete_setting(key)
    if not success:
        raise HTTPException(status_code=404, detail="设置不存在")
    return ResponseModel(message="设置已删除")
