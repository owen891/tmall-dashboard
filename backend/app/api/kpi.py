from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from datetime import datetime, timedelta
from typing import Optional, List
from app.core.database import get_db
from app.models import DailyData, WeeklyData, MonthlyData, Product, Alert
from app.schemas.common import ResponseModel

router = APIRouter(prefix="/api/kpi", tags=["KPI分析"])


def calculate_change(current: float, previous: float) -> dict:
    """计算环比变化"""
    if previous == 0 or previous is None:
        return {"value": 0, "percent": 0, "status": "stable"}
    
    change = current - previous
    percent = (change / previous) * 100 if previous != 0 else 0
    
    if percent > 5:
        status = "up"
    elif percent < -5:
        status = "down"
    else:
        status = "stable"
    
    return {
        "value": change,
        "percent": round(percent, 2),
        "status": status
    }


def detect_anomaly(current: float, previous: float, threshold: float = 30) -> Optional[dict]:
    """检测异常"""
    if previous == 0 or previous is None:
        return None
    
    change_percent = abs((current - previous) / previous * 100) if previous != 0 else 0
    
    if change_percent > threshold:
        return {
            "type": "sharp_change",
            "change_percent": round(change_percent, 2),
            "direction": "up" if current > previous else "down"
        }
    
    return None


@router.get("/summary", response_model=ResponseModel)
def get_kpi_summary(
    dimension: str = Query("weekly", description="时间维度: daily/weekly/monthly"),
    period: Optional[str] = Query(None, description="指定周期，如: 2024-01-01"),
    db: Session = Depends(get_db)
):
    """获取KPI汇总数据（支持多维度+环比+异常检测）"""
    
    if dimension == "daily":
        if not period:
            latest = db.query(DailyData).order_by(desc(DailyData.date)).first()
            period = latest.date.isoformat() if latest else None
        
        if not period:
            return ResponseModel(data={"kpi": {}, "anomalies": [], "period": None})
        
        current_date = datetime.strptime(period, "%Y-%m-%d").date()
        prev_date = current_date - timedelta(days=1)
        
        current_data = db.query(
            func.coalesce(func.sum(DailyData.payment_amount), 0).label('total_gmv'),
            func.coalesce(func.sum(DailyData.net_sales), 0).label('net_sales'),
            func.coalesce(func.sum(DailyData.ad_spend), 0).label('ad_spend'),
            func.coalesce(func.sum(DailyData.ipv), 0).label('visitors'),
            func.coalesce(func.avg(DailyData.payment_conversion), 0).label('avg_conversion'),
            func.coalesce(func.avg(DailyData.ad_roi), 0).label('avg_roi'),
            func.coalesce(func.sum(DailyData.refund_amount), 0).label('refund')
        ).filter(DailyData.date == current_date).first()
        
        prev_data = db.query(
            func.coalesce(func.sum(DailyData.payment_amount), 0).label('total_gmv'),
            func.coalesce(func.sum(DailyData.net_sales), 0).label('net_sales'),
            func.coalesce(func.sum(DailyData.ad_spend), 0).label('ad_spend'),
            func.coalesce(func.sum(DailyData.ipv), 0).label('visitors'),
            func.coalesce(func.avg(DailyData.payment_conversion), 0).label('avg_conversion'),
            func.coalesce(func.avg(DailyData.ad_roi), 0).label('avg_roi'),
            func.coalesce(func.sum(DailyData.refund_amount), 0).label('refund')
        ).filter(DailyData.date == prev_date).first()
        
        date_col = DailyData.date
        model = DailyData
        
    elif dimension == "monthly":
        if not period:
            latest = db.query(MonthlyData).order_by(desc(MonthlyData.month)).first()
            period = latest.month if latest else None
        
        if not period:
            return ResponseModel(data={"kpi": {}, "anomalies": [], "period": None})
        
        year, month = period.split("-")
        prev_year, prev_month = int(year), int(month) - 1
        if prev_month == 0:
            prev_month, prev_year = 12, prev_year - 1
        prev_period = f"{prev_year}-{prev_month:02d}"
        
        current_data = db.query(
            func.coalesce(func.sum(MonthlyData.payment_amount), 0).label('total_gmv'),
            func.coalesce(func.sum(MonthlyData.net_sales), 0).label('net_sales'),
            func.coalesce(func.sum(MonthlyData.ad_spend), 0).label('ad_spend'),
            func.coalesce(func.sum(MonthlyData.visitors), 0).label('visitors'),
            func.coalesce(func.avg(MonthlyData.payment_conversion), 0).label('avg_conversion'),
            func.coalesce(func.avg(MonthlyData.ad_roi), 0).label('avg_roi'),
            func.coalesce(func.sum(MonthlyData.refund_amount), 0).label('refund')
        ).filter(MonthlyData.month == period).first()
        
        prev_data = db.query(
            func.coalesce(func.sum(MonthlyData.payment_amount), 0).label('total_gmv'),
            func.coalesce(func.sum(MonthlyData.net_sales), 0).label('net_sales'),
            func.coalesce(func.sum(MonthlyData.ad_spend), 0).label('ad_spend'),
            func.coalesce(func.sum(MonthlyData.visitors), 0).label('visitors'),
            func.coalesce(func.avg(MonthlyData.payment_conversion), 0).label('avg_conversion'),
            func.coalesce(func.avg(MonthlyData.ad_roi), 0).label('avg_roi'),
            func.coalesce(func.sum(MonthlyData.refund_amount), 0).label('refund')
        ).filter(MonthlyData.month == prev_period).first()
        
        date_col = MonthlyData.month
        model = MonthlyData
        
    else:
        dimension = "weekly"
        if not period:
            latest = db.query(WeeklyData).order_by(desc(WeeklyData.week_start)).first()
            period = latest.week_start.isoformat() if latest else None
        
        if not period:
            return ResponseModel(data={"kpi": {}, "anomalies": [], "period": None})
        
        current_date = datetime.strptime(period, "%Y-%m-%d").date()
        prev_date = current_date - timedelta(days=7)
        
        current_data = db.query(
            func.coalesce(func.sum(WeeklyData.payment_amount), 0).label('total_gmv'),
            func.coalesce(func.sum(WeeklyData.net_sales), 0).label('net_sales'),
            func.coalesce(func.sum(WeeklyData.ad_spend), 0).label('ad_spend'),
            func.coalesce(func.sum(WeeklyData.ipv), 0).label('visitors'),
            func.coalesce(func.avg(WeeklyData.payment_conversion), 0).label('avg_conversion'),
            func.coalesce(func.avg(WeeklyData.ad_roi), 0).label('avg_roi'),
            func.coalesce(func.sum(WeeklyData.refund_amount), 0).label('refund')
        ).filter(WeeklyData.week_start == current_date).first()
        
        prev_data = db.query(
            func.coalesce(func.sum(WeeklyData.payment_amount), 0).label('total_gmv'),
            func.coalesce(func.sum(WeeklyData.net_sales), 0).label('net_sales'),
            func.coalesce(func.sum(WeeklyData.ad_spend), 0).label('ad_spend'),
            func.coalesce(func.sum(WeeklyData.ipv), 0).label('visitors'),
            func.coalesce(func.avg(WeeklyData.payment_conversion), 0).label('avg_conversion'),
            func.coalesce(func.avg(WeeklyData.ad_roi), 0).label('avg_roi'),
            func.coalesce(func.sum(WeeklyData.refund_amount), 0).label('refund')
        ).filter(WeeklyData.week_start == prev_date).first()
        
        date_col = WeeklyData.week_start
        model = WeeklyData
    
    if not current_data or (current_data.total_gmv == 0 and current_data.ad_spend == 0):
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
    avg_roi = float(current_data.avg_roi or 0)
    prev_roi = float(prev_data.avg_roi or 0) if prev_data else 0
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
            "value": round(avg_conversion, 2),
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
    
    gmv_anomaly = detect_anomaly(total_gmv, prev_gmv, 20)
    if gmv_anomaly:
        anomalies.append({
            "metric": "GMV",
            "severity": "high" if abs(gmv_anomaly['change_percent']) > 30 else "medium",
            "detail": f"GMV环比变化 {gmv_anomaly['change_percent']}%",
            **gmv_anomaly
        })
    
    roi_anomaly = detect_anomaly(avg_roi, prev_roi, 25)
    if roi_anomaly:
        anomalies.append({
            "metric": "ROI",
            "severity": "high" if abs(roi_anomaly['change_percent']) > 40 else "medium",
            "detail": f"ROI环比变化 {roi_anomaly['change_percent']}%",
            **roi_anomaly
        })
    
    conversion_anomaly = detect_anomaly(avg_conversion, prev_conversion, 15)
    if conversion_anomaly:
        anomalies.append({
            "metric": "转化率",
            "severity": "medium",
            "detail": f"转化率环比变化 {conversion_anomaly['change_percent']}%",
            **conversion_anomaly
        })
    
    refund_anomaly = detect_anomaly(refund_rate, prev_refund_rate, 20)
    if refund_anomaly and refund_rate > 5:
        anomalies.append({
            "metric": "退款率",
            "severity": "high" if refund_rate > 10 else "medium",
            "detail": f"退款率过高: {refund_rate}%",
            "type": "high_refund",
            "direction": "up"
        })
    
    return ResponseModel(data={
        "kpi": kpi,
        "anomalies": anomalies,
        "period": period,
        "dimension": dimension,
        "product_count": db.query(Product).count(),
        "data_periods": {
            "daily": db.query(func.count(func.distinct(DailyData.date))).scalar(),
            "weekly": db.query(func.count(func.distinct(WeeklyData.week_start))).scalar(),
            "monthly": db.query(func.count(func.distinct(MonthlyData.month))).scalar()
        }
    })


@router.get("/product", response_model=ResponseModel)
def get_product_kpi(
    product_id: str,
    dimension: str = Query("weekly", description="时间维度: daily/weekly/monthly"),
    db: Session = Depends(get_db)
):
    """获取单个商品的KPI数据"""
    
    if dimension == "daily":
        data_list = db.query(DailyData).filter(
            DailyData.product_id == product_id
        ).order_by(desc(DailyData.date)).limit(14).all()
    elif dimension == "monthly":
        data_list = db.query(MonthlyData).filter(
            MonthlyData.product_id == product_id
        ).order_by(desc(MonthlyData.month)).limit(12).all()
    else:
        data_list = db.query(WeeklyData).filter(
            WeeklyData.product_id == product_id
        ).order_by(desc(WeeklyData.week_start)).limit(12).all()
    
    if not data_list:
        return ResponseModel(data={"kpi": {}, "trend": []})
    
    latest = data_list[0]
    previous = data_list[1] if len(data_list) > 1 else None
    
    if dimension == "daily":
        current_gmv = latest.payment_amount
        prev_gmv = previous.payment_amount if previous else 0
        current_visitors = latest.ipv
        prev_visitors = previous.ipv if previous else 0
        current_conversion = latest.payment_conversion
        prev_conversion = previous.payment_conversion if previous else 0
        current_roi = latest.ad_roi
        prev_roi = previous.ad_roi if previous else 0
        current_ad = latest.ad_spend
        prev_ad = previous.ad_spend if previous else 0
        period_label = latest.date.isoformat()
        prev_label = previous.date.isoformat() if previous else None
    elif dimension == "monthly":
        current_gmv = latest.payment_amount
        prev_gmv = previous.payment_amount if previous else 0
        current_visitors = latest.visitors
        prev_visitors = previous.visitors if previous else 0
        current_conversion = latest.payment_conversion
        prev_conversion = previous.payment_conversion if previous else 0
        current_roi = latest.ad_roi
        prev_roi = previous.ad_roi if previous else 0
        current_ad = latest.ad_spend
        prev_ad = previous.ad_spend if previous else 0
        period_label = latest.month
        prev_label = previous.month if previous else None
    else:
        current_gmv = latest.payment_amount
        prev_gmv = previous.payment_amount if previous else 0
        current_visitors = latest.ipv
        prev_visitors = previous.ipv if previous else 0
        current_conversion = latest.payment_conversion
        prev_conversion = previous.payment_conversion if previous else 0
        current_roi = latest.ad_roi
        prev_roi = previous.ad_roi if previous else 0
        current_ad = latest.ad_spend
        prev_ad = previous.ad_spend if previous else 0
        period_label = latest.week_start.isoformat()
        prev_label = previous.week_start.isoformat() if previous else None
    
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
            "value": round(current_conversion, 2),
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
        if dimension == "daily":
            trend.append({
                "period": data.date.isoformat(),
                "gmv": data.payment_amount,
                "visitors": data.ipv,
                "conversion": data.payment_conversion,
                "roi": data.ad_roi
            })
        elif dimension == "monthly":
            trend.append({
                "period": data.month,
                "gmv": data.payment_amount,
                "visitors": data.visitors,
                "conversion": data.payment_conversion,
                "roi": data.ad_roi
            })
        else:
            trend.append({
                "period": data.week_start.isoformat(),
                "gmv": data.payment_amount,
                "visitors": data.ipv,
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
        dimensions.append({
            "value": "daily",
            "label": "日报",
            "count": daily_count
        })
    if weekly_count > 0:
        dimensions.append({
            "value": "weekly",
            "label": "周报",
            "count": weekly_count
        })
    if monthly_count > 0:
        dimensions.append({
            "value": "monthly",
            "label": "月报",
            "count": monthly_count
        })
    
    return ResponseModel(data={"dimensions": dimensions})


@router.get("/anomalies", response_model=ResponseModel)
def get_anomaly_list(
    severity: Optional[str] = Query(None, description="告警级别: high/medium/low"),
    limit: int = Query(20, description="返回数量"),
    db: Session = Depends(get_db)
):
    """获取异常告警列表"""
    query = db.query(Alert).filter(Alert.dismissed == False)
    
    if severity:
        query = query.filter(Alert.severity == severity)
    
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
