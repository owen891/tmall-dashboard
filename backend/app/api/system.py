"""
系统监控 API
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.monitoring import metrics_collector, get_health_status
from app.core.logger import get_logger

router = APIRouter(prefix="/system", tags=["system"])
logger = get_logger(__name__)


@router.get("/health")
def system_health(db: Session = Depends(get_db)):
    """
    系统健康检查
    
    返回系统的整体健康状态，包括CPU、内存、磁盘等指标
    """
    logger.info("收到健康检查请求")
    try:
        health = get_health_status(db)
        return {
            "success": True,
            "data": health
        }
    except Exception as e:
        logger.error(f"健康检查失败: {e}")
        return {
            "success": False,
            "message": f"健康检查失败: {str(e)}"
        }


@router.get("/metrics")
def system_metrics():
    """
    系统指标
    
    返回完整的系统指标数据
    """
    logger.debug("收到指标请求")
    try:
        metrics = metrics_collector.get_all_metrics()
        return {
            "success": True,
            "data": metrics
        }
    except Exception as e:
        logger.error(f"获取指标失败: {e}")
        return {
            "success": False,
            "message": f"获取指标失败: {str(e)}"
        }


@router.get("/status")
def system_status(db: Session = Depends(get_db)):
    """
    系统状态概览
    
    快速查看系统状态的简化版本
    """
    logger.info("收到系统状态请求")
    try:
        health = get_health_status(db)
        return {
            "success": True,
            "data": {
                "status": health["status"],
                "uptime": health["metrics"]["uptime"],
                "cpu_usage": health["metrics"]["cpu"]["usage_percent"],
                "memory_usage": health["metrics"]["memory"]["percent"],
                "disk_usage": health["metrics"]["disk"]["percent"],
                "warnings": health["warnings"]
            }
        }
    except Exception as e:
        logger.error(f"获取系统状态失败: {e}")
        return {
            "success": False,
            "message": f"获取系统状态失败: {str(e)}"
        }
