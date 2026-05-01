from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import Optional, List
from datetime import datetime, timedelta
from app.core.database import get_db
from app.models import DailyData, WeeklyData, MonthlyData, Product
from app.schemas.common import ResponseModel

router = APIRouter(prefix="/lifecycle", tags=["生命周期"])

DIMENSION_MAP = {
    'monthly': {'table': 'monthly_data', 'date_col': 'month', 'visitors_col': 'visitors'},
    'weekly': {'table': 'weekly_data', 'date_col': 'week_start', 'visitors_col': 'ipv'},
    'daily': {'table': 'daily_data', 'date_col': 'date', 'visitors_col': 'ipv'},
}


def get_prev_periods(period_str: str, dim: str, count: int) -> List[str]:
    """获取多个历史周期"""
    periods = []
    current = period_str
    for _ in range(count):
        current = get_prev_period(current, dim)
        periods.append(current)
    periods.reverse()
    return periods


def get_prev_period(period_str: str, dim: str) -> str:
    """获取上一个周期"""
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


def get_latest_period(Model, date_col, db):
    """获取最新周期"""
    latest = db.query(Model).order_by(desc(getattr(Model, date_col))).first()
    if latest:
        return getattr(latest, date_col)
    return None


def determine_lifecycle_stage(data_points: List[dict]) -> tuple:
    """
    判断商品生命周期阶段
    返回: (stage, reason, growth_rate)
    """
    if len(data_points) < 2:
        return "new", "数据不足，无法判断", 0
    
    gmv_values = [d.get('payment_amount', 0) for d in data_points]
    
    if gmv_values[-1] < 100:
        return "new", "销售额较低，处于新品期", 0
    
    recent_avg = sum(gmv_values[-4:]) / min(4, len(gmv_values))
    earlier_avg = sum(gmv_values[:4]) / min(4, len(gmv_values)) if len(gmv_values) >= 4 else gmv_values[0]
    
    if earlier_avg > 0:
        growth_rate = ((recent_avg - earlier_avg) / earlier_avg) * 100
    else:
        growth_rate = 0
    
    if len(data_points) <= 2:
        return "new", "新品上架不久，尚未稳定", growth_rate
    
    if growth_rate > 30:
        return "growth", f"销售额增长{abs(growth_rate):.1f}%，处于上升期", growth_rate
    
    if growth_rate > 10:
        return "growth", f"销售额增长{abs(growth_rate):.1f}%，处于增长期", growth_rate
    
    if growth_rate >= -10:
        if recent_avg > 5000:
            return "stable", f"销售额稳定在较高水平，近{growth_rate:.1f}%", growth_rate
        else:
            return "stable", f"销售额基本稳定，波动{abs(growth_rate):.1f}%", growth_rate
    
    if growth_rate >= -30:
        return "decline", f"销售额下降{abs(growth_rate):.1f}%，需关注", growth_rate
    
    return "serious_decline", f"销售额大幅下降{abs(growth_rate):.1f}%，需立即干预", growth_rate


def generate_lifecycle_recommendations(stage: str, data: dict) -> List[dict]:
    """根据生命周期阶段生成运营建议"""
    recommendations = []
    
    stage_labels = {
        "new": "新品期",
        "growth": "增长期",
        "stable": "稳定期",
        "decline": "下滑期",
        "serious_decline": "严重下滑"
    }
    
    recommendations.append({
        "type": "stage",
        "priority": "info",
        "title": f"当前处于{stage_labels.get(stage, stage)}",
        "action": "continue"
    })
    
    if stage == "new":
        recommendations.extend([
            {
                "type": "traffic",
                "priority": "high",
                "title": "提升流量曝光",
                "detail": "新品期需要更多曝光，建议加大推广力度",
                "action": "increase_traffic"
            },
            {
                "type": "review",
                "priority": "high",
                "title": "积累好评",
                "detail": "积极引导买家好评，提升店铺评分",
                "action": "encourage_review"
            },
            {
                "type": "price",
                "priority": "medium",
                "title": "优化价格策略",
                "detail": "考虑设置新用户优惠或首单优惠",
                "action": "optimize_price"
            }
        ])
    
    elif stage == "growth":
        recommendations.extend([
            {
                "type": "inventory",
                "priority": "high",
                "title": "保障库存充足",
                "detail": "增长期注意备货，避免断货",
                "action": "ensure_inventory"
            },
            {
                "type": "conversion",
                "priority": "high",
                "title": "优化转化率",
                "detail": "流量增长时同步优化详情页，提升转化",
                "action": "optimize_conversion"
            },
            {
                "type": "roi",
                "priority": "medium",
                "title": "关注ROI",
                "detail": "增长期可适当增加广告投入但需监控ROI",
                "action": "monitor_roi"
            }
        ])
    
    elif stage == "stable":
        recommendations.extend([
            {
                "type": "upgrade",
                "priority": "medium",
                "title": "产品升级迭代",
                "detail": "稳定期考虑产品升级或差异化",
                "action": "product_upgrade"
            },
            {
                "type": "bundle",
                "priority": "medium",
                "title": "捆绑销售",
                "detail": "考虑关联销售，提升客单价",
                "action": "bundle_sales"
            },
            {
                "type": "cost",
                "priority": "low",
                "title": "控制成本",
                "detail": "稳定期注重成本控制",
                "action": "cost_control"
            }
        ])
    
    elif stage == "decline":
        recommendations.extend([
            {
                "type": "analysis",
                "priority": "high",
                "title": "分析下滑原因",
                "detail": "排查是市场因素、竞品冲击还是自身问题",
                "action": "analyze_decline"
            },
            {
                "type": "promotion",
                "priority": "high",
                "title": "促销激活",
                "detail": "考虑限时优惠激活销售",
                "action": "promotion"
            },
            {
                "type": "market",
                "priority": "medium",
                "title": "市场调研",
                "detail": "了解市场需求变化和竞品动态",
                "action": "market_research"
            }
        ])
    
    elif stage == "serious_decline":
        recommendations.extend([
            {
                "type": "urgent",
                "priority": "urgent",
                "title": "紧急干预",
                "detail": "立即分析问题根源并制定复苏计划",
                "action": "urgent_action"
            },
            {
                "type": "review",
                "priority": "urgent",
                "title": "检查评价",
                "detail": "排查是否有大量差评影响转化",
                "action": "check_reviews"
            },
            {
                "type": "reposition",
                "priority": "high",
                "title": "考虑重新定位",
                "detail": "可能需要重新定位产品或调整目标人群",
                "action": "reposition"
            }
        ])
    
    return recommendations


@router.get("/list", response_model=ResponseModel)
def get_lifecycle_list(
    dimension: str = Query("weekly", description="时间维度"),
    period: Optional[str] = Query(None, description="指定周期"),
    stage: Optional[str] = Query(None, description="生命周期阶段筛选"),
    page: int = Query(1, description="页码"),
    page_size: int = Query(20, description="每页数量"),
    db: Session = Depends(get_db)
):
    """获取商品生命周期列表"""
    
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
        period = get_latest_period(Model, date_col, db)
    
    if not period:
        return ResponseModel(data={"products": [], "total": 0, "summary": {}})
    
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
    ).filter(
        getattr(Model, date_col) == period
    ).group_by(
        Model.product_id,
        Model.product_name,
        Model.category
    )
    
    all_products = products_query.all()
    
    product_lifecycles = []
    stage_counts = {"new": 0, "growth": 0, "stable": 0, "decline": 0, "serious_decline": 0}
    
    for p in all_products:
        data_points = db.query(Model).filter(
            Model.product_id == p.product_id
        ).order_by(desc(getattr(Model, date_col))).limit(8).all()
        
        data_list = []
        for d in reversed(data_points):
            period_val = getattr(d, date_col)
            if hasattr(period_val, 'isoformat'):
                period_str = period_val.isoformat()
            else:
                period_str = str(period_val)
            
            data_list.append({
                "period": period_str,
                "payment_amount": d.payment_amount or 0,
                "visitors": getattr(d, visitors_col) or 0,
                "conversion": d.payment_conversion or 0
            })
        
        stage, reason, growth_rate = determine_lifecycle_stage(data_list)
        
        if stage not in stage_counts:
            stage_counts[stage] = 0
        stage_counts[stage] += 1
        
        payment = float(p.payment_amount or 0)
        refund = float(p.refund_amount or 0)
        visitors = int(p.visitors or 0)
        
        product_lifecycles.append({
            "product_id": p.product_id,
            "product_name": p.product_name,
            "category": p.category,
            "stage": stage,
            "reason": reason,
            "growth_rate": round(growth_rate, 1),
            "payment_amount": round(payment, 2),
            "net_sales": round(payment - refund, 2),
            "visitors": visitors,
            "conversion": round(float(p.conversion or 0) * 100, 2) if p.conversion else 0,
            "ad_spend": round(float(p.ad_spend or 0), 2),
            "roi": round(float(p.roi or 0), 2) if p.roi else 0,
            "recent_data": data_list[-4:] if len(data_list) >= 4 else data_list
        })
    
    if stage:
        product_lifecycles = [p for p in product_lifecycles if p['stage'] == stage]
    
    total = len(product_lifecycles)
    paginated = product_lifecycles[(page - 1) * page_size: page * page_size]
    
    return ResponseModel(data={
        "products": paginated,
        "total": total,
        "summary": {
            "new": stage_counts["new"],
            "growth": stage_counts["growth"],
            "stable": stage_counts["stable"],
            "decline": stage_counts["decline"],
            "serious_decline": stage_counts["serious_decline"]
        },
        "period": str(period),
        "dimension": dimension
    })


@router.get("/summary", response_model=ResponseModel)
def get_lifecycle_summary(
    dimension: str = Query("weekly", description="时间维度"),
    period: Optional[str] = Query(None, description="指定周期"),
    db: Session = Depends(get_db)
):
    """获取生命周期汇总"""
    
    dim_cfg = DIMENSION_MAP.get(dimension, DIMENSION_MAP['weekly'])
    date_col = dim_cfg['date_col']
    
    if dimension == "monthly":
        Model = MonthlyData
    elif dimension == "daily":
        Model = DailyData
    else:
        Model = WeeklyData
    
    if not period:
        period = get_latest_period(Model, date_col, db)
    
    if not period:
        return ResponseModel(data={"summary": {}, "distribution": []})
    
    products = db.query(
        Model.product_id
    ).filter(
        getattr(Model, date_col) == period
    ).group_by(Model.product_id).all()
    
    product_ids = [p.product_id for p in products]
    
    stage_counts = {"new": 0, "growth": 0, "stable": 0, "decline": 0, "serious_decline": 0}
    
    for pid in product_ids:
        data_points = db.query(Model).filter(
            Model.product_id == pid
        ).order_by(desc(getattr(Model, date_col))).limit(8).all()
        
        data_list = []
        for d in reversed(data_points):
            data_list.append({
                "payment_amount": d.payment_amount or 0
            })
        
        stage, _, _ = determine_lifecycle_stage(data_list)
        if stage in stage_counts:
            stage_counts[stage] += 1
    
    total = len(product_ids)
    distribution = []
    
    stage_labels = {
        "new": "新品期",
        "growth": "增长期",
        "stable": "稳定期",
        "decline": "下滑期",
        "serious_decline": "严重下滑"
    }
    
    for stage, count in stage_counts.items():
        distribution.append({
            "stage": stage,
            "label": stage_labels.get(stage, stage),
            "count": count,
            "percent": round(count / total * 100, 1) if total > 0 else 0
        })
    
    return ResponseModel(data={
        "summary": {
            "total_products": total,
            "stages": stage_counts
        },
        "distribution": distribution,
        "period": str(period),
        "dimension": dimension
    })


@router.get("/{product_id}", response_model=ResponseModel)
def get_product_lifecycle(
    product_id: str,
    dimension: str = Query("weekly", description="时间维度"),
    db: Session = Depends(get_db)
):
    """获取单个商品的生命周期详情"""
    
    dim_cfg = DIMENSION_MAP.get(dimension, DIMENSION_MAP['weekly'])
    visitors_col = dim_cfg['visitors_col']
    date_col = dim_cfg['date_col']
    
    if dimension == "monthly":
        Model = MonthlyData
    elif dimension == "daily":
        Model = DailyData
    else:
        Model = WeeklyData
    
    data_points = db.query(Model).filter(
        Model.product_id == product_id
    ).order_by(desc(getattr(Model, date_col))).limit(12).all()
    
    if not data_points:
        return ResponseModel(data={"product": None})
    
    product_info = data_points[0]
    data_list = []
    
    for d in reversed(data_points):
        period_val = getattr(d, date_col)
        if hasattr(period_val, 'isoformat'):
            period_str = period_val.isoformat()
        else:
            period_str = str(period_val)
        
        data_list.append({
            "period": period_str,
            "payment_amount": d.payment_amount or 0,
            "refund_amount": d.refund_amount or 0,
            "visitors": getattr(d, visitors_col) or 0,
            "conversion": d.payment_conversion or 0,
            "ad_spend": d.ad_spend or 0,
            "roi": d.ad_roi or 0
        })
    
    stage, reason, growth_rate = determine_lifecycle_stage(data_list)
    recommendations = generate_lifecycle_recommendations(stage, {
        "data": data_list,
        "current_payment": data_list[-1]['payment_amount'] if data_list else 0
    })
    
    return ResponseModel(data={
        "product": {
            "product_id": product_id,
            "product_name": product_info.product_name,
            "category": product_info.category,
            "stage": stage,
            "reason": reason,
            "growth_rate": round(growth_rate, 1),
            "data": data_list,
            "recommendations": recommendations
        },
        "dimension": dimension
    })


@router.get("/trend/{product_id}", response_model=ResponseModel)
def get_lifecycle_trend(
    product_id: str,
    dimension: str = Query("weekly", description="时间维度"),
    db: Session = Depends(get_db)
):
    """获取商品生命周期趋势"""
    
    dim_cfg = DIMENSION_MAP.get(dimension, DIMENSION_MAP['weekly'])
    visitors_col = dim_cfg['visitors_col']
    date_col = dim_cfg['date_col']
    
    if dimension == "monthly":
        Model = MonthlyData
    elif dimension == "daily":
        Model = DailyData
    else:
        Model = WeeklyData
    
    data_points = db.query(Model).filter(
        Model.product_id == product_id
    ).order_by(desc(getattr(Model, date_col))).limit(12).all()
    
    if not data_points:
        return ResponseModel(data={"trend": []})
    
    trend = []
    for d in reversed(data_points):
        period_val = getattr(d, date_col)
        if hasattr(period_val, 'isoformat'):
            period_str = period_val.isoformat()
        else:
            period_str = str(period_val)
        
        trend.append({
            "period": period_str,
            "payment_amount": d.payment_amount or 0,
            "visitors": getattr(d, visitors_col) or 0
        })
    
    return ResponseModel(data={
        "product_id": product_id,
        "trend": trend,
        "dimension": dimension
    })
