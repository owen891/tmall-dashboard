"""
系统监控模块
提供系统指标和健康检查
"""
import time
import psutil
import os
import gc
from datetime import datetime
from typing import Dict, Any
from sqlalchemy.orm import Session
from app.core.logger import get_logger

logger = get_logger(__name__)

class SystemMetrics:
    """系统指标收集器"""

    def __init__(self):
        self.start_time = time.time()

    def get_uptime(self) -> float:
        """获取系统运行时间"""
        return time.time() - self.start_time

    def get_cpu_metrics(self) -> Dict[str, Any]:
        """获取CPU指标"""
        try:
            return {
                "usage_percent": psutil.cpu_percent(interval=0.1),
                "count": psutil.cpu_count(),
                "count_logical": psutil.cpu_count(logical=True)
            }
        except Exception as e:
            logger.error(f"获取CPU指标失败: {e}")
            return {
                "usage_percent": 0,
                "count": 0,
                "count_logical": 0
            }

    def get_memory_metrics(self) -> Dict[str, Any]:
        """获取内存指标"""
        try:
            memory = psutil.virtual_memory()
            return {
                "total": memory.total,
                "available": memory.available,
                "used": memory.used,
                "percent": memory.percent
            }
        except Exception as e:
            logger.error(f"获取内存指标失败: {e}")
            return {
                "total": 0,
                "available": 0,
                "used": 0,
                "percent": 0
            }

    def get_disk_metrics(self) -> Dict[str, Any]:
        """获取磁盘指标"""
        try:
            disk = psutil.disk_usage('/')
            return {
                "total": disk.total,
                "used": disk.used,
                "free": disk.free,
                "percent": disk.percent
            }
        except Exception as e:
            logger.error(f"获取磁盘指标失败: {e}")
            return {
                "total": 0,
                "used": 0,
                "free": 0,
                "percent": 0
            }

    def get_network_metrics(self) -> Dict[str, Any]:
        """获取网络指标"""
        try:
            net_io = psutil.net_io_counters()
            return {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_sent": net_io.packets_sent,
                "packets_recv": net_io.packets_recv
            }
        except Exception as e:
            logger.error(f"获取网络指标失败: {e}")
            return {
                "bytes_sent": 0,
                "bytes_recv": 0,
                "packets_sent": 0,
                "packets_recv": 0
            }

    def get_process_metrics(self) -> Dict[str, Any]:
        """获取进程指标"""
        try:
            current_process = psutil.Process()
            return {
                "pid": current_process.pid,
                "memory_usage": current_process.memory_info().rss,
                "cpu_percent": current_process.cpu_percent(),
                "thread_count": current_process.num_threads(),
                "fd_count": current_process.num_fds() if hasattr(current_process, 'num_fds') else 0
            }
        except Exception as e:
            logger.error(f"获取进程指标失败: {e}")
            return {
                "pid": 0,
                "memory_usage": 0,
                "cpu_percent": 0,
                "thread_count": 0,
                "fd_count": 0
            }

    def get_all_metrics(self) -> Dict[str, Any]:
        """获取所有指标"""
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "uptime": self.get_uptime(),
            "cpu": self.get_cpu_metrics(),
            "memory": self.get_memory_metrics(),
            "disk": self.get_disk_metrics(),
            "network": self.get_network_metrics(),
            "process": self.get_process_metrics()
        }


# 全局指标收集器
metrics_collector = SystemMetrics()


def get_health_status(db: Session) -> Dict[str, Any]:
    """
    获取系统健康状态
    
    Args:
        db: 数据库会话
        
    Returns:
        健康状态字典
    """
    metrics = metrics_collector.get_all_metrics()

    # 健康检查逻辑
    health_status = "healthy"
    warnings = []

    # CPU检查
    if metrics["cpu"]["usage_percent"] > 80:
        warnings.append("CPU使用率过高")
        health_status = "warning"

    # 内存检查
    if metrics["memory"]["percent"] > 85:
        warnings.append("内存使用率过高")
        health_status = "warning"

    # 磁盘检查
    if metrics["disk"]["percent"] > 90:
        warnings.append("磁盘空间不足")
        health_status = "critical"

    return {
        "status": health_status,
        "warnings": warnings,
        "metrics": metrics
    }
