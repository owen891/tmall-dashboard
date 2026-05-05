from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import Optional, List
from datetime import datetime
from app.core.database import get_db
from app.models import ProductTrafficDetail, MonthlyPlanning, Product, TrafficSource
from app.schemas.common import ResponseModel
from app.models.alerts import Alert

router = APIRouter(prefix="/smart-alerts", tags=["智能预警"])


def check_and_create_alert(db: Session, product_id: str, product_name: str, alert_type: str, severity: str, metric: str, current_value: float, threshold: float, message: str) -> bool:
    """Check if alert already exists and create if not"""
    existing = db.query(Alert).filter(
        Alert.product_id == int(product_id) if product_id.isdigit() else None,
        Alert.status == "unresolved",
        Alert.metric == metric,
        Alert.alert_type == alert_type,
    ).first()
    if existing:
        return False
    new_alert = Alert(
        product_id=int(product_id) if product_id.isdigit() else None,
        product_name=product_name,
        alert_type=alert_type,
        severity=severity,
        metric=metric,
        current_value=current_value,
        threshold=threshold,
        message=message,
        status="unresolved",
    )
    db.add(new_alert)
    return True


@router.post("/auto-generate", response_model=ResponseModel)
def auto_generate_alerts(
    start_date: Optional[str] = Query(None, description="开始日期"),
    end_date: Optional[str] = Query(None, description="结束日期"),
    db: Session = Depends(get_db)
):
    """自动扫描数据并生成智能预警"""
    products_data = db.query(
        ProductTrafficDetail.product_id,
        func.count().label('days'),
        func.sum(ProductTrafficDetail.visitors).label('visitors'),
        func.sum(ProductTrafficDetail.payment_amount).label('payment'),
        func.sum(ProductTrafficDetail.ad_spend).label('ad_spend'),
        func.avg(ProductTrafficDetail.conversion_rate).label('conversion'),
        func.avg(ProductTrafficDetail.ad_roi).label('ad_roi'),
        func.avg(ProductTrafficDetail.cart_rate).label('cart_rate'),
        func.avg(ProductTrafficDetail.fav_rate).label('fav_rate'),
        func.avg(ProductTrafficDetail.refund_rate).label('refund_rate'),
        func.avg(ProductTrafficDetail.bounce_rate).label('bounce_rate'),
        func.sum(ProductTrafficDetail.search_visitors).label('search_visitors'),
        func.sum(ProductTrafficDetail.recommend_visitors).label('recommend_visitors'),
    ).filter(
        ProductTrafficDetail.date >= (start_date or "2000-01-01"),
        ProductTrafficDetail.date <= (end_date or "2099-12-31"),
    ).group_by(ProductTrafficDetail.product_id).all()
    
    new_alerts = []
    total_products = len(products_data)
    
    for p in products_data:
        product = db.query(Product).filter(Product.product_id == p.product_id).first()
        product_name = product.title if product else p.product_id
        plan = db.query(MonthlyPlanning).filter(
            MonthlyPlanning.product_id == p.product_id
        ).order_by(MonthlyPlanning.plan_month.desc()).first()
        
        total_visitors = p.visitors or 0
        total_payment = p.payment or 0
        total_ad_spend = p.ad_spend or 0
        avg_conversion = p.conversion or 0
        avg_ad_roi = p.ad_roi or 0
        avg_cart_rate = p.cart_rate or 0
        avg_fav_rate = p.fav_rate or 0
        avg_refund_rate = p.refund_rate or 0
        avg_bounce_rate = p.bounce_rate or 0
        
        total_search = p.search_visitors or 0
        total_recommend = p.recommend_visitors or 0
        search_ratio = total_search / max(total_visitors, 1)
        
        target_achievement = 0
        if plan and plan.gsv_target and plan.gsv_target > 0:
            target_achievement = (total_payment / plan.gsv_target * 100)
        
        ad_ratio = (total_ad_spend / total_payment * 100) if total_payment > 0 else 0
        
        if check_and_create_alert(db, p.product_id, product_name, "conversion", "critical", "低转化率", 
                                   avg_conversion, 0.02, f"{product_name} 转化率仅 {round(avg_conversion*100, 2)}%，低于2%警戒线"):
            new_alerts.append({"product_id": p.product_id, "type": "低转化率"})
        
        if avg_refund_rate and avg_refund_rate > 0.20:
            if check_and_create_alert(db, p.product_id, product_name, "refund", "critical", "高退款率",
                                       avg_refund_rate, 0.20, f"{product_name} 退款率高达 {round(avg_refund_rate*100, 1)}%，超过20%"):
                new_alerts.append({"product_id": p.product_id, "type": "高退款率"})
        
        if avg_bounce_rate and avg_bounce_rate > 0.65:
            if check_and_create_alert(db, p.product_id, product_name, "traffic", "warning", "高跳失率",
                                       avg_bounce_rate, 0.65, f"{product_name} 跳失率 {round(avg_bounce_rate*100, 1)}%，超过65%"):
                new_alerts.append({"product_id": p.product_id, "type": "高跳失率"})
        
        if avg_ad_roi and avg_ad_roi < 1.0 and total_ad_spend > 0:
            if check_and_create_alert(db, p.product_id, product_name, "ad", "critical", "广告亏损",
                                       avg_ad_roi, 1.0, f"{product_name} 广告ROI仅 {round(avg_ad_roi, 2)}，投放亏损"):
                new_alerts.append({"product_id": p.product_id, "type": "广告亏损"})
        
        if ad_ratio > 40 and total_ad_spend > 0:
            if check_and_create_alert(db, p.product_id, product_name, "ad", "warning", "付费占比过高",
                                       ad_ratio, 40, f"{product_name} 付费占比 {round(ad_ratio, 1)}%，超过40%"):
                new_alerts.append({"product_id": p.product_id, "type": "付费占比过高"})
        
        if target_achievement and target_achievement < 80 and plan:
            if check_and_create_alert(db, p.product_id, product_name, "target", "warning", "目标未达成",
                                       target_achievement, 80, f"{product_name} 目标达成率 {round(target_achievement, 1)}%，低于80%"):
                new_alerts.append({"product_id": p.product_id, "type": "目标未达成"})
        
        if search_ratio < 0.25 and total_visitors > 100:
            if check_and_create_alert(db, p.product_id, product_name, "traffic", "warning", "搜索流量不足",
                                       search_ratio * 100, 25, f"{product_name} 搜索流量占比 {round(search_ratio*100, 1)}%，低于25%"):
                new_alerts.append({"product_id": p.product_id, "type": "搜索流量不足"})
        
        if avg_cart_rate and avg_cart_rate < 0.03 and total_visitors > 100:
            if check_and_create_alert(db, p.product_id, product_name, "engagement", "warning", "加购率偏低",
                                       avg_cart_rate, 0.03, f"{product_name} 加购率仅 {round(avg_cart_rate*100, 1)}%"):
                new_alerts.append({"product_id": p.product_id, "type": "加购率偏低"})
    
    db.commit()
    
    return ResponseModel(data={
        "new_alerts": len(new_alerts),
        "products_scanned": total_products,
        "alerts": new_alerts[:20],
        "message": f"扫描 {total_products} 个商品，发现 {len(new_alerts)} 个新问题",
    })


@router.get("/summary", response_model=ResponseModel)
def get_alert_summary(
    days: int = Query(30, description="统计天数"),
    db: Session = Depends(get_db)
):
    """获取智能预警汇总"""
    total = db.query(func.count(Alert.id)).scalar() or 0
    unresolved = db.query(func.count(Alert.id)).filter(Alert.status == "unresolved").scalar() or 0
    critical = db.query(func.count(Alert.id)).filter(
        Alert.status == "unresolved",
        Alert.severity == "critical",
    ).scalar() or 0
    warning = db.query(func.count(Alert.id)).filter(
        Alert.status == "unresolved",
        Alert.severity == "warning",
    ).scalar() or 0
    
    by_type = db.query(
        Alert.alert_type,
        func.count(Alert.id).label("count"),
    ).filter(Alert.status == "unresolved").group_by(Alert.alert_type).all()
    
    by_product = db.query(
        Alert.product_name,
        func.count(Alert.id).label("count"),
    ).filter(Alert.status == "unresolved").group_by(Alert.product_name).order_by(desc(func.count(Alert.id))).limit(10).all()
    
    return ResponseModel(data={
        "total": total,
        "unresolved": unresolved,
        "critical": critical,
        "warning": warning,
        "by_type": {t.alert_type: t.count for t in by_type},
        "by_product": [{"name": p.product_name, "count": p.count} for p in by_product],
    })
