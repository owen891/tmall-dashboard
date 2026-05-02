"""
通用工具函数模块
提取重复代码，提高可维护性
"""
from datetime import datetime, timedelta
from typing import Tuple, Any, Optional
from sqlalchemy import func, desc
from sqlalchemy.orm import Session

from app.models import DailyData, WeeklyData, MonthlyData


DIMENSION_MAP = {
    'monthly': {'table': 'monthly_data', 'date_col': 'month', 'visitors_col': 'visitors'},
    'weekly': {'table': 'weekly_data', 'date_col': 'week_start', 'visitors_col': 'ipv'},
    'daily': {'table': 'daily_data', 'date_col': 'date', 'visitors_col': 'ipv'},
}


def get_data_model(dimension: str) -> Tuple[Any, str, str]:
    """根据维度获取数据模型、日期字段、访客字段"""
    if dimension == "monthly":
        return MonthlyData, 'month', 'visitors'
    elif dimension == "daily":
        return DailyData, 'date', 'ipv'
    else:
        return WeeklyData, 'week_start', 'ipv'


def get_prev_period(period_str: str, dim: str) -> str:
    """获取上一个周期"""
    try:
        if dim == 'monthly':
            y, m = str(period_str).split('-')
            m = int(m) - 1
            if m == 0:
                m, y = 12, str(int(y) - 1)
            return f"{y}-{m:02d}"
        else:
            d = datetime.strptime(str(period_str), '%Y-%m-%d')
            if dim == 'weekly':
                prev = d - timedelta(days=7)
            else:
                prev = d - timedelta(days=1)
            return prev.strftime('%Y-%m-%d')
    except (ValueError, IndexError, TypeError, AttributeError):
        return period_str


def get_latest_period(Model, date_col: str, db: Session) -> Optional[str]:
    """获取最新周期"""
    latest = db.query(Model).order_by(desc(getattr(Model, date_col))).first()
    if latest:
        period = getattr(latest, date_col)
        if isinstance(period, datetime):
            return period.date().isoformat() if hasattr(period, 'date') else period.isoformat()
        return str(period)
    return None


def calculate_change(current: float, previous: float) -> dict:
    """计算环比变化"""
    if previous is None or previous == 0:
        return {"value": 0, "percent": 0, "status": "stable"}
    
    change = current - previous
    percent = (change / previous) * 100
    
    if percent > 5:
        status = "up"
    elif percent < -5:
        status = "down"
    else:
        status = "stable"
    
    return {
        "value": round(change, 2),
        "percent": round(percent, 1),
        "status": status
    }


def safe_float(value, default=0.0) -> float:
    """安全转换为浮点数"""
    if value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def safe_int(value, default=0) -> int:
    """安全转换为整数"""
    if value is None:
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default
