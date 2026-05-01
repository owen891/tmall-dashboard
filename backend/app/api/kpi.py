from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from datetime import datetime, timedelta
from typing import Optional, List
from app.core.database import get_db
from app.models import DailyData, WeeklyData, MonthlyData, Product, Alert
from app.schemas.common import ResponseModel

router = APIRouter(prefix="/kpi", tags=["KPI分析"])

DIMENSION_MAP = {
    'monthly': {'table': 'monthly_data', 'date_col': 'month', 'visitors_col': 'visitors'},
    'weekly': {'table': 'weekly_data', 'date_col': 'week_start', 'visitors_col': 'ipv'},
    'daily': {'table': 'daily_data', 'date_col': 'date', 'visitors_col': 'ipv'},
}


def get_prev_period(period: str, dim: str) -> str:
    """获取上一个周期"""
    try:
        if dim == 'monthly':
            y, m = period.split('-')
            m = int(m) - 1
            if m == 0:
                m, y = 12, str(int(y) - 1)
            return f"{y}-{m:02d}"
        elif dim == 'weekly':
            d = datetime.strptime(period, '%Y-%m-%d')
            prev = d - timedelta(days=7)
            return prev.strftime('%Y-%m-%d')
        else:
            d = datetime.strptime(period, '%Y-%m-%d')
            prev = d - timedelta(days=1)
            return prev.strftime('%Y-%m-%d')
    except (ValueError, IndexError, TypeError, AttributeError):
        return period


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


def calculate_change_rate(current: float, previous: float) -> Optional[float]:
    """计算百分比变化（用于退款率等）"""
    if previous is None or previous == 0:
        return None
    return round((current - previous) * 100, 1)


@router.get("", response_model=ResponseModel)
def get_kpi(
    dim: str = Query("weekly", alias="dim", description="时间维度: daily/weekly/monthly"),
    period: Optional[str] = Query(None, description="指定周期"),
    prev_period: Optional[str] = Query(None, description="上一周期"),
    db: Session = Depends(get_db)
):
    """获取KPI数据（兼容老版本）"""
    
    dimension = dim
    dim_cfg = DIMENSION_MAP.get(dimension, DIMENSION_MAP['weekly'])
    visitors_col = dim_cfg['visitors_col']
    date_col = dim_cfg['date_col']
    
    if dimension == "monthly":
        Model = MonthlyData
    elif dimension == "daily":
        Model = DailyData
    else:
        Model = WeeklyData
    
    if not period:
        latest = db.query(Model).order_by(desc(getattr(Model, date_col))).first()
        period = getattr(latest, date_col) if latest else None
        if isinstance(period, datetime):
            period = period.date() if hasattr(period, 'date') else period.isoformat()
    
    if not period:
        return ResponseModel(data={"current": None, "previous": None, "changes": {}, "anomalies": []})
    
    if not prev_period:
        prev_period = get_prev_period(str(period), dimension)
    
    def query_period(p):
        if not p:
            return None
        filter_cond = getattr(Model, date_col) == p
        row = db.query(
            func.coalesce(func.sum(Model.payment_amount), 0).label('gmv'),
            func.coalesce(func.sum(Model.refund_amount), 0).label('refund_amount'),
            (func.coalesce(func.sum(Model.payment_amount), 0) - func.coalesce(func.sum(Model.refund_amount), 0)).label('net_sales'),
            func.coalesce(func.sum(getattr(Model, visitors_col)), 0).label('visitors'),
            (func.coalesce(func.sum(Model.payment_amount), 0) / func.nullif(func.sum(getattr(Model, visitors_col)), 0)).label('aov'),
            (func.coalesce(func.sum(Model.refund_amount), 0) / func.nullif(func.coalesce(func.sum(Model.payment_amount), 0), 0)).label('refund_rate'),
            func.coalesce(func.sum(Model.ad_spend), 0).label('ad_spend'),
            (func.coalesce(func.sum(Model.payment_amount), 0) / func.nullif(func.coalesce(func.sum(Model.ad_spend), 0), 0)).label('roi'),
            func.avg(Model.payment_conversion).label('conversion')
        ).filter(filter_cond).first()
        
        if row:
            result = {
                'gmv': float(row.gmv or 0),
                'refund_amount': float(row.refund_amount or 0),
                'net_sales': float(row.net_sales or 0),
                'visitors': int(row.visitors or 0),
                'aov': float(row.aov or 0) if row.aov else 0,
                'refund_rate': float(row.refund_rate or 0) if row.refund_rate else 0,
                'ad_spend': float(row.ad_spend or 0),
                'roi': float(row.roi or 0) if row.roi else 0,
                'conversion': float(row.conversion or 0) if row.conversion else 0,
            }
            return result
        return None
    
    current = query_period(period)
    previous = query_period(prev_period) if prev_period != period else None
    
    changes = {}
    anomalies = []
    anomaly_threshold = 0.20
    
    if current and previous:
        for key in ['gmv', 'net_sales', 'visitors', 'aov', 'ad_spend', 'roi', 'conversion']:
            prev_val = previous.get(key) or 0
            curr_val = current.get(key) or 0
            if prev_val > 0:
                changes[key] = round(((curr_val - prev_val) / prev_val) * 100, 1)
            else:
                changes[key] = None
        
        prev_refund = previous.get('refund_rate') or 0
        curr_refund = current.get('refund_rate') or 0
        changes['refund_rate'] = calculate_change_rate(curr_refund, prev_refund)
        
        metric_labels = {'gmv': '总GMV', 'net_sales': '净销售额', 'visitors': '总访客', 'aov': '客单价'}
        for key in ['gmv', 'net_sales', 'visitors', 'aov']:
            change_val = changes.get(key)
            if change_val is not None and change_val < 0 and abs(change_val) > anomaly_threshold * 100:
                severity = 'high' if abs(change_val) > 40 else 'warning'
                anomalies.append({
                    'metric': key,
                    'label': metric_labels.get(key, key),
                    'change': change_val,
                    'current': current.get(key, 0),
                    'previous': previous.get(key, 0),
                    'direction': 'decline',
                    'severity': severity
                })
    
    return ResponseModel(data={
        'current': current,
        'previous': previous,
        'changes': changes,
        'anomalies': anomalies,
        'period': period,
        'prev_period': prev_period,
        'dimension': dimension,
    })


@router.get("/summary", response_model=ResponseModel)
def get_kpi_summary(
    dimension: str = Query("weekly", description="时间维度: daily/weekly/monthly"),
    period: Optional[str] = Query(None, description="指定周期"),
    db: Session = Depends(get_db)
):
    """获取KPI汇总数据（兼容新版前端）"""
    
    dim_cfg = DIMENSION_MAP.get(dimension, DIMENSION_MAP['weekly'])
    visitors_col = dim_cfg['visitors_col']
    date_col = dim_cfg['date_col']
    
    if dimension == "monthly":
        Model = MonthlyData
    elif dimension == "daily":
        Model = DailyData
    else:
        Model = WeeklyData
    
    if not period:
        latest = db.query(Model).order_by(desc(getattr(Model, date_col))).first()
        period = getattr(latest, date_col) if latest else None
        if isinstance(period, datetime):
            period = period.date() if hasattr(period, 'date') else period.isoformat()
    
    if not period:
        return ResponseModel(data={"kpi": {}, "anomalies": [], "period": None})
    
    prev_period = get_prev_period(str(period), dimension)
    
    filter_cond = getattr(Model, date_col) == period
    prev_filter_cond = getattr(Model, date_col) == prev_period
    
    current_data = db.query(
        func.coalesce(func.sum(Model.payment_amount), 0).label('total_gmv'),
        (func.coalesce(func.sum(Model.payment_amount), 0) - func.coalesce(func.sum(Model.refund_amount), 0)).label('net_sales'),
        func.coalesce(func.sum(Model.ad_spend), 0).label('ad_spend'),
        func.coalesce(func.sum(getattr(Model, visitors_col)), 0).label('visitors'),
        func.avg(Model.payment_conversion).label('avg_conversion'),
        func.avg(Model.ad_roi).label('avg_roi'),
        func.coalesce(func.sum(Model.refund_amount), 0).label('refund')
    ).filter(filter_cond).first()
    
    prev_data = db.query(
        func.coalesce(func.sum(Model.payment_amount), 0).label('total_gmv'),
        (func.coalesce(func.sum(Model.payment_amount), 0) - func.coalesce(func.sum(Model.refund_amount), 0)).label('net_sales'),
        func.coalesce(func.sum(Model.ad_spend), 0).label('ad_spend'),
        func.coalesce(func.sum(getattr(Model, visitors_col)), 0).label('visitors'),
        func.avg(Model.payment_conversion).label('avg_conversion'),
        func.avg(Model.ad_roi).label('avg_roi'),
        func.coalesce(func.sum(Model.refund_amount), 0).label('refund')
    ).filter(prev_filter_cond).first()
    
    if not current_data:
        return ResponseModel(data={"kpi": {}, "anomalies": [], "period": period})
    
    total_gmv = float(current_data.total_gmv or 0)
    prev_gmv = float(prev_data.total_gmv or 0) if prev_data else 0
    net_sales = float(current_data.net_sales or 0)
    prev_net = float(prev_data.net_sales or 0) if prev_data else 0
    ad_spend = float(current_data.ad_spend or 0)
    prev_ad = float(prev_data.ad_spend or 0) if prev_data else 0
    visitors = int(current_data.visitors or 0)
    prev_visitors = int(prev_data.visitors or 0) if prev_data else 0
    avg_conversion = float(current_data.avg_conversion or 0)
    prev_conversion = float(prev_data.avg_conversion or 0) if prev_data else 0
    avg_roi = float(current_data.avg_roi or 0) if current_data.avg_roi else 0
    prev_roi = float(prev_data.avg_roi or 0) if prev_data and prev_data.avg_roi else 0
    refund = float(current_data.refund or 0)
    prev_refund = float(prev_data.refund or 0) if prev_data else 0
    
    ad_ratio = (ad_spend / total_gmv * 100) if total_gmv != 0 else 0
    prev_ad_ratio = (prev_ad / prev_gmv * 100) if prev_gmv != 0 else 0
    refund_rate = (refund / total_gmv * 100) if total_gmv != 0 else 0
    prev_refund_rate = (prev_refund / prev_gmv * 100) if prev_gmv != 0 else 0
    uv_value = (total_gmv / visitors) if visitors != 0 else 0
    prev_uv_value = (prev_gmv / prev_visitors) if prev_visitors != 0 else 0
    
    kpi = {
        "total_gmv": {
            "value": round(total_gmv, 2),
            "change": calculate_change(total_gmv, prev_gmv),
            "label": "总GMV"
        },
        "net_sales": {
            "value": round(net_sales, 2),
            "change": calculate_change(net_sales, prev_net),
            "label": "净销售额"
        },
        "ad_spend": {
            "value": round(ad_spend, 2),
            "change": calculate_change(ad_spend, prev_ad),
            "label": "广告支出"
        },
        "ad_ratio": {
            "value": round(ad_ratio, 2),
            "change": calculate_change(ad_ratio, prev_ad_ratio),
            "label": "广告占比",
            "unit": "%"
        },
        "visitors": {
            "value": visitors,
            "change": calculate_change(visitors, prev_visitors),
            "label": "访客数"
        },
        "uv_value": {
            "value": round(uv_value, 2),
            "change": calculate_change(uv_value, prev_uv_value),
            "label": "UV价值"
        },
        "avg_conversion": {
            "value": round(avg_conversion * 100, 2) if avg_conversion < 1 else round(avg_conversion, 2),
            "change": calculate_change(avg_conversion, prev_conversion),
            "label": "平均转化率",
            "unit": "%"
        },
        "avg_roi": {
            "value": round(avg_roi, 2),
            "change": calculate_change(avg_roi, prev_roi),
            "label": "平均ROI"
        },
        "refund": {
            "value": round(refund, 2),
            "change": calculate_change(refund, prev_refund),
            "label": "退款金额"
        },
        "refund_rate": {
            "value": round(refund_rate, 2),
            "change": calculate_change(refund_rate, prev_refund_rate),
            "label": "退款率",
            "unit": "%"
        }
    }
    
    anomalies = []
    if prev_gmv > 0:
        gmv_change_pct = abs((total_gmv - prev_gmv) / prev_gmv * 100)
        if gmv_change_pct > 20:
            anomalies.append({
                "metric": "GMV",
                "severity": "high" if gmv_change_pct > 30 else "medium",
                "detail": f"GMV环比变化 {gmv_change_pct:.1f}%"
            })
    
    return ResponseModel(data={
        "kpi": kpi,
        "anomalies": anomalies,
        "period": period,
        "dimension": dimension,
        "product_count": db.query(Product).count(),
    })


@router.get("/product", response_model=ResponseModel)
def get_product_kpi(
    product_id: str,
    dimension: str = Query("weekly", description="时间维度: daily/weekly/monthly"),
    db: Session = Depends(get_db)
):
    """获取单个商品的KPI数据"""
    
    dim_cfg = DIMENSION_MAP.get(dimension, DIMENSION_MAP['weekly'])
    visitors_col = dim_cfg['visitors_col']
    date_col = dim_cfg['date_col']
    
    if dimension == "monthly":
        Model = MonthlyData
    elif dimension == "daily":
        Model = DailyData
    else:
        Model = WeeklyData
    
    data_list = db.query(Model).filter(
        Model.product_id == product_id
    ).order_by(desc(getattr(Model, date_col))).limit(12).all()
    
    if not data_list:
        return ResponseModel(data={"kpi": {}, "trend": []})
    
    latest = data_list[0]
    previous = data_list[1] if len(data_list) > 1 else None
    
    current_gmv = latest.payment_amount or 0
    prev_gmv = previous.payment_amount if previous else 0
    current_visitors = getattr(latest, visitors_col) or 0
    prev_visitors = getattr(previous, visitors_col) if previous else 0
    current_conversion = latest.payment_conversion or 0
    prev_conversion = previous.payment_conversion if previous else 0
    current_roi = latest.ad_roi or 0
    prev_roi = previous.ad_roi if previous else 0
    current_ad = latest.ad_spend or 0
    prev_ad = previous.ad_spend if previous else 0
    
    if date_col == 'month':
        period_label = latest.month
        prev_label = previous.month if previous else None
    elif date_col == 'week_start':
        period_label = latest.week_start.isoformat() if hasattr(latest.week_start, 'isoformat') else str(latest.week_start)
        prev_label = previous.week_start.isoformat() if previous and hasattr(previous.week_start, 'isoformat') else None
    else:
        period_label = latest.date.isoformat() if hasattr(latest.date, 'isoformat') else str(latest.date)
        prev_label = previous.date.isoformat() if previous and hasattr(previous.date, 'isoformat') else None
    
    ad_ratio = (current_ad / current_gmv * 100) if current_gmv != 0 else 0
    prev_ad_ratio = (prev_ad / prev_gmv * 100) if prev_gmv != 0 else 0
    
    kpi = {
        "gmv": {
            "value": round(current_gmv, 2),
            "change": calculate_change(current_gmv, prev_gmv),
            "prev_value": round(prev_gmv, 2) if prev_gmv else None
        },
        "visitors": {
            "value": current_visitors,
            "change": calculate_change(current_visitors, prev_visitors),
            "prev_value": prev_visitors if prev_visitors else None
        },
        "conversion": {
            "value": round(current_conversion * 100, 2) if current_conversion < 1 else round(current_conversion, 2),
            "change": calculate_change(current_conversion, prev_conversion),
            "unit": "%"
        },
        "roi": {
            "value": round(current_roi, 2),
            "change": calculate_change(current_roi, prev_roi)
        },
        "ad_spend": {
            "value": round(current_ad, 2),
            "change": calculate_change(current_ad, prev_ad)
        },
        "ad_ratio": {
            "value": round(ad_ratio, 2),
            "change": calculate_change(ad_ratio, prev_ad_ratio),
            "unit": "%"
        }
    }
    
    trend = []
    for data in reversed(data_list):
        period = None
        if date_col == 'month':
            period = data.month
        elif date_col == 'week_start':
            period = data.week_start.isoformat() if hasattr(data.week_start, 'isoformat') else str(data.week_start)
        else:
            period = data.date.isoformat() if hasattr(data.date, 'isoformat') else str(data.date)
        
        trend.append({
            "period": period,
            "gmv": data.payment_amount,
            "visitors": getattr(data, visitors_col),
            "conversion": data.payment_conversion,
            "roi": data.ad_roi
        })
    
    return ResponseModel(data={
        "product_id": product_id,
        "kpi": kpi,
        "trend": trend,
        "period": period_label,
        "prev_period": prev_label,
        "dimension": dimension
    })


@router.get("/dimensions", response_model=ResponseModel)
def get_available_dimensions(db: Session = Depends(get_db)):
    """获取可用的时间维度"""
    daily_count = db.query(func.count(func.distinct(DailyData.date))).scalar()
    weekly_count = db.query(func.count(func.distinct(WeeklyData.week_start))).scalar()
    monthly_count = db.query(func.count(func.distinct(MonthlyData.month))).scalar()
    
    dimensions = []
    if daily_count > 0:
        dimensions.append({"value": "daily", "label": "日报", "count": daily_count})
    if weekly_count > 0:
        dimensions.append({"value": "weekly", "label": "周报", "count": weekly_count})
    if monthly_count > 0:
        dimensions.append({"value": "monthly", "label": "月报", "count": monthly_count})
    
    return ResponseModel(data={"dimensions": dimensions})


@router.get("/anomalies", response_model=ResponseModel)
def get_anomaly_list(
    dimension: str = Query("weekly", description="时间维度"),
    period: Optional[str] = Query(None, description="指定周期"),
    severity: Optional[str] = Query(None, description="告警级别: high/medium/low"),
    limit: int = Query(20, description="返回数量"),
    db: Session = Depends(get_db)
):
    """获取异常告警列表"""
    query = db.query(Alert).filter(Alert.dismissed == False)
    
    if severity:
        query = query.filter(Alert.severity == severity)
    if period:
        query = query.filter(Alert.period == period)
    
    alerts = query.order_by(desc(Alert.created_at)).limit(limit).all()
    
    return ResponseModel(data={
        "alerts": [
            {
                "id": a.id,
                "alert_date": a.alert_date.isoformat() if a.alert_date else None,
                "alert_type": a.alert_type,
                "severity": a.severity,
                "title": a.title,
                "detail": a.detail,
                "metric_name": a.metric_name,
                "current_value": a.current_value,
                "target_value": a.target_value,
                "period": a.period
            }
            for a in alerts
        ],
        "count": len(alerts)
    })


@router.post("/anomalies/{alert_id}/dismiss", response_model=ResponseModel)
def dismiss_anomaly(alert_id: int, db: Session = Depends(get_db)):
    """标记告警为已处理"""
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        return ResponseModel(data={"message": "告警不存在"})
    
    alert.dismissed = True
    db.commit()
    
    return ResponseModel(data={"message": "告警已标记为已处理"})
