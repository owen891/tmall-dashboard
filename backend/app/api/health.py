from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import Optional, List
from app.core.database import get_db
from app.models import DailyData, WeeklyData, MonthlyData, ProductHealth, Product
from app.schemas.common import ResponseModel

router = APIRouter(prefix="/health", tags=["健康度分析"])

DIMENSION_MAP = {
    'monthly': {'table': 'monthly_data', 'date_col': 'month', 'visitors_col': 'visitors'},
    'weekly': {'table': 'weekly_data', 'date_col': 'week_start', 'visitors_col': 'ipv'},
    'daily': {'table': 'daily_data', 'date_col': 'date', 'visitors_col': 'ipv'},
}


def calculate_health_score(row: dict) -> dict:
    """计算健康度评分"""
    scores = {}
    details = {}
    alerts = []
    health_level = "excellent"
    
    gmv = row.get('payment_amount', 0)
    refund = row.get('refund_amount', 0)
    visitors = row.get('visitors', 0)
    conversion = row.get('conversion', 0)
    roi = row.get('roi', 0)
    ad_spend = row.get('ad_spend', 0)
    
    if gmv > 0:
        refund_rate = refund / gmv
    else:
        refund_rate = 0
    
    if visitors > 0:
        aov = gmv / visitors
    else:
        aov = 0
    
    if ad_spend > 0:
        ad_ratio = ad_spend / gmv
    else:
        ad_ratio = 0
    
    if gmv > 10000:
        scores['gmv'] = 100
        details['gmv'] = f"GMV {gmv:.0f}元，优秀"
    elif gmv > 5000:
        scores['gmv'] = 80
        details['gmv'] = f"GMV {gmv:.0f}元，良好"
    elif gmv > 1000:
        scores['gmv'] = 60
        details['gmv'] = f"GMV {gmv:.0f}元，一般"
    else:
        scores['gmv'] = 40
        details['gmv'] = f"GMV {gmv:.0f}元，需提升"
        alerts.append({"dimension": "gmv", "level": "warning", "message": "GMV偏低，需要提升销售额"})
    
    if refund_rate < 0.02:
        scores['refund'] = 100
        details['refund'] = f"退款率 {refund_rate*100:.2f}%，优秀"
    elif refund_rate < 0.05:
        scores['refund'] = 80
        details['refund'] = f"退款率 {refund_rate*100:.2f}%，良好"
    elif refund_rate < 0.10:
        scores['refund'] = 60
        details['refund'] = f"退款率 {refund_rate*100:.2f}%，需关注"
        alerts.append({"dimension": "refund", "level": "warning", "message": f"退款率偏高 ({refund_rate*100:.2f}%)"})
    else:
        scores['refund'] = 30
        details['refund'] = f"退款率 {refund_rate*100:.2f}%，严重"
        alerts.append({"dimension": "refund", "level": "high", "message": f"退款率过高 ({refund_rate*100:.2f}%)，需立即处理"})
    
    if conversion > 0.05:
        scores['conversion'] = 100
        details['conversion'] = f"转化率 {conversion*100:.2f}%，优秀"
    elif conversion > 0.02:
        scores['conversion'] = 80
        details['conversion'] = f"转化率 {conversion*100:.2f}%，良好"
    elif conversion > 0.01:
        scores['conversion'] = 60
        details['conversion'] = f"转化率 {conversion*100:.2f}%，需优化"
        alerts.append({"dimension": "conversion", "level": "warning", "message": "转化率偏低，需要优化"})
    else:
        scores['conversion'] = 40
        details['conversion'] = f"转化率 {conversion*100:.2f}%，严重"
        alerts.append({"dimension": "conversion", "level": "high", "message": "转化率过低，需要重点优化"})
    
    if roi > 5:
        scores['roi'] = 100
        details['roi'] = f"ROI {roi:.2f}，优秀"
    elif roi > 3:
        scores['roi'] = 80
        details['roi'] = f"ROI {roi:.2f}，良好"
    elif roi > 1:
        scores['roi'] = 60
        details['roi'] = f"ROI {roi:.2f}，需优化"
        alerts.append({"dimension": "roi", "level": "warning", "message": "ROI偏低，广告投放效率待提升"})
    else:
        scores['roi'] = 30
        details['roi'] = f"ROI {roi:.2f}，亏损"
        alerts.append({"dimension": "roi", "level": "high", "message": "ROI低于1，广告投放亏损"})
    
    if aov > 200:
        scores['aov'] = 100
        details['aov'] = f"客单价 {aov:.2f}元，优秀"
    elif aov > 100:
        scores['aov'] = 80
        details['aov'] = f"客单价 {aov:.2f}元，良好"
    elif aov > 50:
        scores['aov'] = 60
        details['aov'] = f"客单价 {aov:.2f}元，一般"
    else:
        scores['aov'] = 40
        details['aov'] = f"客单价 {aov:.2f}元，需提升"
    
    if ad_ratio < 0.1:
        scores['ad_ratio'] = 100
        details['ad_ratio'] = f"广告占比 {ad_ratio*100:.2f}%，优秀"
    elif ad_ratio < 0.2:
        scores['ad_ratio'] = 80
        details['ad_ratio'] = f"广告占比 {ad_ratio*100:.2f}%，良好"
    elif ad_ratio < 0.3:
        scores['ad_ratio'] = 60
        details['ad_ratio'] = f"广告占比 {ad_ratio*100:.2f}%，需控制"
        alerts.append({"dimension": "ad_ratio", "level": "warning", "message": "广告占比偏高"})
    else:
        scores['ad_ratio'] = 30
        details['ad_ratio'] = f"广告占比 {ad_ratio*100:.2f}%，过高"
        alerts.append({"dimension": "ad_ratio", "level": "high", "message": "广告占比过高，需控制成本"})
    
    total_score = sum(scores.values()) / len(scores)
    
    if total_score >= 90:
        health_level = "excellent"
    elif total_score >= 75:
        health_level = "good"
    elif total_score >= 60:
        health_level = "warning"
    else:
        health_level = "danger"
    
    return {
        "total_score": round(total_score, 1),
        "health_level": health_level,
        "scores": scores,
        "details": details,
        "alerts": alerts
    }


def get_prev_period(period_str: str, dim: str) -> str:
    """获取上一个周期"""
    from datetime import datetime, timedelta
    
    try:
        if dim == 'monthly':
            y, m = period_str.split('-')
            m = int(m) - 1
            if m == 0:
                m, y = 12, str(int(y) - 1)
            return f"{y}-{m:02d}"
        else:
            d = datetime.strptime(period_str, '%Y-%m-%d')
            if dim == 'weekly':
                prev = d - timedelta(days=7)
            else:
                prev = d - timedelta(days=1)
            return prev.strftime('%Y-%m-%d')
    except (ValueError, IndexError, TypeError, AttributeError):
        return period_str


@router.get("/list", response_model=ResponseModel)
def get_health_list(
    dimension: str = Query("weekly", description="时间维度: daily/weekly/monthly"),
    period: Optional[str] = Query(None, description="指定周期"),
    health_level: Optional[str] = Query(None, description="健康等级筛选"),
    page: int = Query(1, description="页码"),
    page_size: int = Query(20, description="每页数量"),
    db: Session = Depends(get_db)
):
    """获取商品健康度列表"""
    
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
    
    if not period:
        return ResponseModel(data={"products": [], "total": 0, "page": page, "page_size": page_size})
    
    filter_conditions = [getattr(Model, date_col) == period]
    if health_level:
        filter_conditions.append(Model.health_level == health_level)
    
    products_query = db.query(
        Model.product_id,
        Model.product_name,
        Model.category,
        func.sum(Model.payment_amount).label('payment_amount'),
        func.sum(Model.refund_amount).label('refund_amount'),
        func.sum(getattr(Model, visitors_col)).label('visitors'),
        func.avg(Model.payment_conversion).label('conversion'),
        func.sum(Model.ad_spend).label('ad_spend'),
        func.avg(Model.ad_roi).label('roi'),
    ).filter(*filter_conditions).group_by(
        Model.product_id,
        Model.product_name,
        Model.category
    )
    
    total = products_query.count()
    products_data = products_query.offset((page - 1) * page_size).limit(page_size).all()
    
    products = []
    for p in products_data:
        payment = float(p.payment_amount or 0)
        refund = float(p.refund_amount or 0)
        visitors = int(p.visitors or 0)
        conversion = float(p.conversion or 0)
        ad_spend = float(p.ad_spend or 0)
        roi = float(p.roi or 0) if p.roi else 0
        
        row_data = {
            'product_id': p.product_id,
            'product_name': p.product_name,
            'category': p.category,
            'payment_amount': payment,
            'refund_amount': refund,
            'visitors': visitors,
            'conversion': conversion,
            'ad_spend': ad_spend,
            'roi': roi,
        }
        
        health = calculate_health_score(row_data)
        
        products.append({
            **row_data,
            'health_score': health['total_score'],
            'health_level': health['health_level'],
            'scores': health['scores'],
            'details': health['details'],
            'alerts': health['alerts']
        })
    
    return ResponseModel(data={
        "products": products,
        "total": total,
        "page": page,
        "page_size": page_size,
        "period": str(period),
        "dimension": dimension
    })


@router.get("/summary", response_model=ResponseModel)
def get_health_summary(
    dimension: str = Query("weekly", description="时间维度"),
    period: Optional[str] = Query(None, description="指定周期"),
    db: Session = Depends(get_db)
):
    """获取健康度汇总"""
    
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
    
    if not period:
        return ResponseModel(data={"summary": {}, "by_level": []})
    
    filter_cond = getattr(Model, date_col) == period
    
    products_data = db.query(
        Model.product_id,
        func.sum(Model.payment_amount).label('payment_amount'),
        func.sum(Model.refund_amount).label('refund_amount'),
        func.sum(getattr(Model, visitors_col)).label('visitors'),
        func.avg(Model.payment_conversion).label('conversion'),
        func.sum(Model.ad_spend).label('ad_spend'),
        func.avg(Model.ad_roi).label('roi'),
    ).filter(filter_cond).group_by(Model.product_id).all()
    
    level_counts = {"excellent": 0, "good": 0, "warning": 0, "danger": 0}
    total_score = 0
    gmv_score = 0
    refund_score = 0
    conv_score = 0
    roi_score = 0
    product_count = len(products_data)
    
    for p in products_data:
        payment = float(p.payment_amount or 0)
        refund = float(p.refund_amount or 0)
        visitors = int(p.visitors or 0)
        conversion = float(p.conversion or 0)
        ad_spend = float(p.ad_spend or 0)
        roi = float(p.roi or 0) if p.roi else 0
        
        row_data = {
            'payment_amount': payment,
            'refund_amount': refund,
            'visitors': visitors,
            'conversion': conversion,
            'ad_spend': ad_spend,
            'roi': roi,
        }
        
        health = calculate_health_score(row_data)
        level_counts[health['health_level']] += 1
        total_score += health['total_score']
        gmv_score += health['scores'].get('gmv', 0)
        refund_score += health['scores'].get('refund', 0)
        conv_score += health['scores'].get('conversion', 0)
        roi_score += health['scores'].get('roi', 0)
    
    if product_count > 0:
        avg_total = total_score / product_count
        avg_gmv = gmv_score / product_count
        avg_refund = refund_score / product_count
        avg_conv = conv_score / product_count
        avg_roi = roi_score / product_count
    else:
        avg_total = avg_gmv = avg_refund = avg_conv = avg_roi = 0
    
    by_level = [
        {"level": "excellent", "label": "优秀", "count": level_counts["excellent"], "percent": round(level_counts["excellent"] / product_count * 100, 1) if product_count > 0 else 0},
        {"level": "good", "label": "良好", "count": level_counts["good"], "percent": round(level_counts["good"] / product_count * 100, 1) if product_count > 0 else 0},
        {"level": "warning", "label": "预警", "count": level_counts["warning"], "percent": round(level_counts["warning"] / product_count * 100, 1) if product_count > 0 else 0},
        {"level": "danger", "label": "危险", "count": level_counts["danger"], "percent": round(level_counts["danger"] / product_count * 100, 1) if product_count > 0 else 0},
    ]
    
    return ResponseModel(data={
        "summary": {
            "total_score": round(avg_total, 1),
            "gmv_score": round(avg_gmv, 1),
            "refund_score": round(avg_refund, 1),
            "conversion_score": round(avg_conv, 1),
            "roi_score": round(avg_roi, 1),
            "product_count": product_count,
            "excellent_count": level_counts["excellent"],
            "good_count": level_counts["good"],
            "warning_count": level_counts["warning"],
            "danger_count": level_counts["danger"],
        },
        "by_level": by_level,
        "period": str(period),
        "dimension": dimension
    })


@router.get("/{product_id}", response_model=ResponseModel)
def get_product_health(
    product_id: str,
    dimension: str = Query("weekly", description="时间维度"),
    db: Session = Depends(get_db)
):
    """获取单个商品健康度详情"""
    
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
        return ResponseModel(data={"product": None, "trend": []})
    
    product_info = data_list[0]
    trend = []
    
    for data in reversed(data_list):
        period = None
        if date_col == 'month':
            period = data.month
        elif date_col == 'week_start':
            period = data.week_start.isoformat() if hasattr(data.week_start, 'isoformat') else str(data.week_start)
        else:
            period = data.date.isoformat() if hasattr(data.date, 'isoformat') else str(data.date)
        
        payment = data.payment_amount or 0
        refund = data.refund_amount or 0
        visitors = getattr(data, visitors_col) or 0
        conversion = data.payment_conversion or 0
        ad_spend = data.ad_spend or 0
        roi = data.ad_roi or 0
        
        row_data = {
            'payment_amount': payment,
            'refund_amount': refund,
            'visitors': visitors,
            'conversion': conversion,
            'ad_spend': ad_spend,
            'roi': roi,
        }
        
        health = calculate_health_score(row_data)
        
        trend.append({
            "period": period,
            **row_data,
            'health_score': health['total_score'],
            'health_level': health['health_level'],
        })
    
    return ResponseModel(data={
        "product": {
            "product_id": product_id,
            "product_name": product_info.product_name,
            "category": product_info.category,
            "current_health": trend[-1] if trend else None,
            "trend": trend
        },
        "dimension": dimension
    })


@router.get("/alerts", response_model=ResponseModel)
def get_health_alerts(
    dimension: str = Query("weekly", description="时间维度"),
    period: Optional[str] = Query(None, description="指定周期"),
    level: Optional[str] = Query(None, description="告警级别: high/warning"),
    limit: int = Query(20, description="返回数量"),
    db: Session = Depends(get_db)
):
    """获取健康度告警列表"""
    
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
    
    if not period:
        return ResponseModel(data={"alerts": []})
    
    filter_cond = getattr(Model, date_col) == period
    
    products_data = db.query(
        Model.product_id,
        Model.product_name,
        func.sum(Model.payment_amount).label('payment_amount'),
        func.sum(Model.refund_amount).label('refund_amount'),
        func.sum(getattr(Model, visitors_col)).label('visitors'),
        func.avg(Model.payment_conversion).label('conversion'),
        func.sum(Model.ad_spend).label('ad_spend'),
        func.avg(Model.ad_roi).label('roi'),
    ).filter(filter_cond).group_by(
        Model.product_id,
        Model.product_name
    ).all()
    
    all_alerts = []
    for p in products_data:
        payment = float(p.payment_amount or 0)
        refund = float(p.refund_amount or 0)
        visitors = int(p.visitors or 0)
        conversion = float(p.conversion or 0)
        ad_spend = float(p.ad_spend or 0)
        roi = float(p.roi or 0) if p.roi else 0
        
        row_data = {
            'payment_amount': payment,
            'refund_amount': refund,
            'visitors': visitors,
            'conversion': conversion,
            'ad_spend': ad_spend,
            'roi': roi,
        }
        
        health = calculate_health_score(row_data)
        
        for alert in health['alerts']:
            if level and alert['level'] != level:
                continue
            all_alerts.append({
                "product_id": p.product_id,
                "product_name": p.product_name,
                "dimension": alert['dimension'],
                "level": alert['level'],
                "message": alert['message'],
                "health_score": health['total_score'],
                "period": str(period)
            })
    
    all_alerts.sort(key=lambda x: (0 if x['level'] == 'high' else 1, -x['health_score']))
    all_alerts = all_alerts[:limit]
    
    return ResponseModel(data={
        "alerts": all_alerts,
        "total": len(all_alerts),
        "period": str(period),
        "dimension": dimension
    })
