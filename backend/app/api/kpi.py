from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import Optional, List
import traceback
from app.core.database import get_db
from app.core.utils import get_data_model, get_prev_period, get_latest_period, calculate_change, safe_float
from app.models import DailyData, WeeklyData, MonthlyData, Product, Alert, MonthlyPlanning
from app.schemas.common import ResponseModel
from app.core.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/kpi", tags=["KPI分析"])


@router.get("", response_model=ResponseModel)
def get_kpi(
    dim: str = Query("weekly", alias="dim", description="时间维度: daily/weekly/monthly"),
    period: Optional[str] = Query(None, description="指定周期"),
    prev_period: Optional[str] = Query(None, description="上一周期"),
    db: Session = Depends(get_db)
):
    """获取KPI数据（兼容老版本）"""
    try:
        dimension = dim
        Model, date_col, visitors_col = get_data_model(dimension)
        
        if not period:
            period = get_latest_period(Model, date_col, db)
        
        if not period:
            return ResponseModel(data={"kpi": {}, "trends": []})
        
        if not prev_period:
            prev_period = get_prev_period(str(period), dimension)
        
        curr_data = db.query(
            func.sum(Model.payment_amount).label('payment'),
            func.sum(Model.refund_amount).label('refund'),
            func.sum(getattr(Model, visitors_col)).label('visitors'),
            func.avg(Model.payment_conversion).label('conversion'),
            func.sum(Model.ad_spend).label('ad_spend'),
        ).filter(getattr(Model, date_col) == period).first()
        
        prev_data = db.query(
            func.sum(Model.payment_amount).label('payment'),
            func.sum(Model.refund_amount).label('refund'),
            func.sum(getattr(Model, visitors_col)).label('visitors'),
            func.avg(Model.payment_conversion).label('conversion'),
            func.sum(Model.ad_spend).label('ad_spend'),
        ).filter(getattr(Model, date_col) == prev_period).first()
        
        if not prev_data or not prev_data.payment:
            from sqlalchemy import desc as sql_desc
            all_periods = db.query(getattr(Model, date_col)).distinct().order_by(sql_desc(getattr(Model, date_col))).all()
            all_periods = [str(p[0]) for p in all_periods if str(p[0]) != str(period)]
            if all_periods:
                actual_prev = all_periods[0]
                prev_data = db.query(
                    func.sum(Model.payment_amount).label('payment'),
                    func.sum(Model.refund_amount).label('refund'),
                    func.sum(getattr(Model, visitors_col)).label('visitors'),
                    func.avg(Model.payment_conversion).label('conversion'),
                    func.sum(Model.ad_spend).label('ad_spend'),
                ).filter(getattr(Model, date_col) == actual_prev).first()
                prev_period = actual_prev
        
        curr_payment = safe_float(curr_data.payment) if curr_data else 0
        prev_payment = safe_float(prev_data.payment) if prev_data else 0
        curr_visitors = safe_float(curr_data.visitors) if curr_data else 0
        prev_visitors = safe_float(prev_data.visitors) if prev_data else 0
        curr_conversion = safe_float(curr_data.conversion) if curr_data else 0
        prev_conversion = safe_float(prev_data.conversion) if prev_data else 0
        curr_ad_spend = safe_float(curr_data.ad_spend) if curr_data else 0
        prev_ad_spend = safe_float(prev_data.ad_spend) if prev_data else 0
        
        payment_change = calculate_change(curr_payment, prev_payment)
        visitors_change = calculate_change(curr_visitors, prev_visitors)
        conversion_change = calculate_change(curr_conversion, prev_conversion)
        
        roi = (curr_payment / curr_ad_spend) if curr_ad_spend > 0 else 0
        prev_roi = (prev_payment / prev_ad_spend) if prev_ad_spend > 0 else 0
        roi_change = calculate_change(roi, prev_roi)
        
        refund_rate = (safe_float(curr_data.refund) / curr_payment * 100) if curr_payment > 0 else 0
        prev_refund_rate = (safe_float(prev_data.refund) / prev_payment * 100) if prev_payment > 0 else 0
        refund_change = calculate_change(refund_rate, prev_refund_rate)
        
        kpi = {
            "total_gmv": {
                "value": round(curr_payment, 2),
                "percent": payment_change["percent"],
                "status": payment_change["status"]
            },
            "visitors": {
                "value": int(curr_visitors),
                "percent": visitors_change["percent"],
                "status": visitors_change["status"]
            },
            "conversion": {
                "value": round(curr_conversion * 100, 2),
                "percent": conversion_change["percent"],
                "status": conversion_change["status"]
            },
            "roi": {
                "value": round(roi, 2),
                "percent": roi_change["percent"],
                "status": roi_change["status"]
            },
            "refund_rate": {
                "value": round(refund_rate, 2),
                "percent": refund_change["percent"],
                "status": refund_change["status"]
            },
            "ad_spend": {"value": round(curr_ad_spend, 2)},
        }
        
        return ResponseModel(data={
            "kpi": kpi,
            "dimension": dimension,
            "period": str(period),
            "prev_period": str(prev_period)
        })
    except Exception as e:
        logger.error(f"KPI查询失败: {e}")
        logger.error(traceback.format_exc())
        raise


@router.get("/summary", response_model=ResponseModel)
def get_kpi_summary(
    dimension: str = Query("weekly", description="时间维度"),
    period: Optional[str] = Query(None, description="指定周期"),
    db: Session = Depends(get_db)
):
    """获取KPI汇总（新版前端用）"""
    Model, date_col, visitors_col = get_data_model(dimension)
    
    if not period:
        period = get_latest_period(Model, date_col, db)
    
    if not period:
        return ResponseModel(data={"kpi": {}, "dimension": dimension})
    
    prev_period = get_prev_period(str(period), dimension)
    
    data = db.query(
        func.sum(Model.payment_amount).label('payment'),
        func.sum(Model.refund_amount).label('refund'),
        func.sum(getattr(Model, visitors_col)).label('visitors'),
        func.avg(Model.payment_conversion).label('conversion'),
        func.sum(Model.ad_spend).label('ad_spend'),
    ).filter(getattr(Model, date_col) == period).first()
    
    prev_data = db.query(
        func.sum(Model.payment_amount).label('payment'),
        func.sum(Model.refund_amount).label('refund'),
        func.sum(getattr(Model, visitors_col)).label('visitors'),
        func.avg(Model.payment_conversion).label('conversion'),
        func.sum(Model.ad_spend).label('ad_spend'),
    ).filter(getattr(Model, date_col) == prev_period).first()
    
    curr_payment = safe_float(data.payment) if data else 0
    prev_payment = safe_float(prev_data.payment) if prev_data else 0
    curr_visitors = safe_float(data.visitors) if data else 0
    prev_visitors = safe_float(prev_data.visitors) if prev_data else 0
    curr_conversion = safe_float(data.conversion) if data else 0
    prev_conversion = safe_float(prev_data.conversion) if prev_data else 0
    curr_ad_spend = safe_float(data.ad_spend) if data else 0
    prev_ad_spend = safe_float(prev_data.ad_spend) if prev_data else 0
    curr_refund = safe_float(data.refund) if data else 0
    
    net_sales = curr_payment - curr_refund
    roi = (net_sales / curr_ad_spend * 100) if curr_ad_spend > 0 else 0
    prev_roi = ((prev_payment - safe_float(prev_data.refund)) / prev_ad_spend * 100) if prev_ad_spend > 0 else 0
    
    kpi = {
        "total_gmv": {
            "value": round(curr_payment, 2),
            "change": round(curr_payment - prev_payment, 2),
            "change_percent": round((curr_payment - prev_payment) / prev_payment * 100, 1) if prev_payment > 0 else 0
        },
        "visitors": {
            "value": int(curr_visitors),
            "change": int(curr_visitors - prev_visitors),
            "change_percent": round((curr_visitors - prev_visitors) / prev_visitors * 100, 1) if prev_visitors > 0 else 0
        },
        "conversion": {
            "value": round(curr_conversion * 100, 2),
            "change": round((curr_conversion - prev_conversion) * 100, 2),
            "change_percent": round((curr_conversion - prev_conversion) / prev_conversion * 100, 1) if prev_conversion > 0 else 0
        },
        "roi": {
            "value": round(roi, 2),
            "change": round(roi - prev_roi, 2),
            "change_percent": round((roi - prev_roi) / prev_roi * 100, 1) if prev_roi > 0 else 0
        },
        "ad_spend": {
            "value": round(curr_ad_spend, 2),
            "change": round(curr_ad_spend - prev_ad_spend, 2),
            "change_percent": round((curr_ad_spend - prev_ad_spend) / prev_ad_spend * 100, 1) if prev_ad_spend > 0 else 0
        },
        "net_sales": {
            "value": round(net_sales, 2)
        }
    }
    
    return ResponseModel(data={
        "kpi": kpi,
        "dimension": dimension,
        "period": str(period),
        "prev_period": str(prev_period)
    })


@router.get("/dimensions", response_model=ResponseModel)
def get_kpi_dimensions(db: Session = Depends(get_db)):
    """获取可用的时间维度及其最新数据"""
    dimensions = []
    
    for dim in ['daily', 'weekly', 'monthly']:
        Model, date_col, visitors_col = get_data_model(dim)
        
        try:
            latest = get_latest_period(Model, date_col, db)
            count = 0
            if latest:
                count = db.query(Model).filter(getattr(Model, date_col) == latest).count()
            
            dimensions.append({
                "value": dim,
                "label": {"daily": "按日", "weekly": "按周", "monthly": "按月"}[dim],
                "latest_period": latest,
                "data_count": count
            })
        except Exception:
            dimensions.append({
                "value": dim,
                "label": {"daily": "按日", "weekly": "按周", "monthly": "按月"}[dim],
                "latest_period": None,
                "data_count": 0
            })
    
    return ResponseModel(data={"dimensions": dimensions})


@router.get("/planning", response_model=ResponseModel)
def get_planning_data(
    plan_month: Optional[str] = Query(None, description="月份, 如 5月"),
    product_id: Optional[str] = Query(None, description="商品ID"),
    db: Session = Depends(get_db)
):
    """获取月度规划/KPI目标数据"""
    query = db.query(MonthlyPlanning)
    if plan_month:
        query = query.filter(MonthlyPlanning.plan_month == plan_month)
    if product_id:
        query = query.filter(MonthlyPlanning.product_id == product_id)
    
    rows = query.order_by(MonthlyPlanning.product_id).all()
    
    plans = []
    for r in rows:
        plans.append({
            "plan_month": r.plan_month,
            "product_id": r.product_id,
            "product_title": r.product_title,
            "category": r.category,
            "tier": r.tier,
            "manager": r.manager,
            "new_old": r.new_old,
            "gsv_target": r.gsv_target,
            "net_sales_target": r.net_sales_target,
            "target_score": r.target_score,
            "daily_target": r.daily_target,
            "daily_target_ad": r.daily_target_ad,
            "daily_target_ad_ratio": r.daily_target_ad_ratio,
            "payment_amount": r.payment_amount,
            "refund_amount": r.refund_amount,
            "net_sales": r.net_sales,
            "ad_spend": r.ad_spend,
            "ad_roi": r.ad_roi,
            "ad_ratio": r.ad_ratio,
            "visitors": r.visitors,
            "uv_value": r.uv_value,
            "payment_conversion": r.payment_conversion,
            "refund_rate": r.refund_rate,
            "cart_rate": r.cart_rate,
            "fav_rate": r.fav_rate,
            "score": r.score,
            "keyword_ad_spend": r.keyword_ad_spend,
            "keyword_ad_roi": r.keyword_ad_roi,
            "audience_ad_spend": r.audience_ad_spend,
            "audience_ad_roi": r.audience_ad_roi,
            "full_site_ad_spend": r.full_site_ad_spend,
            "full_site_ad_roi": r.full_site_ad_roi,
            "impressions": r.impressions,
            "clicks": r.clicks,
            "ctr": r.ctr,
        })
    
    totals = db.query(
        func.sum(MonthlyPlanning.gsv_target).label('gsv_target'),
        func.sum(MonthlyPlanning.net_sales_target).label('net_sales_target'),
        func.sum(MonthlyPlanning.payment_amount).label('payment_amount'),
        func.sum(MonthlyPlanning.net_sales).label('net_sales'),
        func.sum(MonthlyPlanning.ad_spend).label('ad_spend'),
        func.avg(MonthlyPlanning.ad_roi).label('ad_roi'),
        func.sum(MonthlyPlanning.visitors).label('visitors'),
    ).filter(
        MonthlyPlanning.plan_month == plan_month if plan_month else True,
        MonthlyPlanning.product_id == product_id if product_id else True,
    ).first()
    
    return ResponseModel(data={
        "plans": plans,
        "totals": {
            "gsv_target": round(totals.gsv_target or 0, 2),
            "net_sales_target": round(totals.net_sales_target or 0, 2),
            "payment_amount": round(totals.payment_amount or 0, 2),
            "net_sales": round(totals.net_sales or 0, 2),
            "ad_spend": round(totals.ad_spend or 0, 2),
            "ad_roi": round(totals.ad_roi or 0, 2),
            "visitors": totals.visitors or 0,
        },
        "count": len(plans),
    })


@router.get("/planning/targets-vs-actual", response_model=ResponseModel)
def get_targets_vs_actual(
    plan_month: Optional[str] = Query(None, description="月份"),
    db: Session = Depends(get_db)
):
    """获取目标与实际对比"""
    plans = db.query(MonthlyPlanning).filter(
        MonthlyPlanning.plan_month == plan_month if plan_month else True,
    ).all()
    
    comparison = []
    for p in plans:
        target = p.gsv_target or 0
        actual = p.payment_amount or 0
        achievement = round((actual / target * 100), 1) if target > 0 else 0
        comparison.append({
            "product_id": p.product_id,
            "product_title": p.product_title,
            "category": p.category,
            "tier": p.tier,
            "target": target,
            "actual": round(actual, 2),
            "achievement": achievement,
            "gap": round(actual - target, 2),
        })
    
    return ResponseModel(data={"comparison": comparison, "count": len(comparison)})
