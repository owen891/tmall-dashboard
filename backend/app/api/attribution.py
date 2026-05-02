"""
异动归因下钻分析 API
自动定位数据异动的根本原因
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from app.core.database import get_db
from app.core.utils import get_data_model, get_prev_period, get_latest_period, safe_float, calculate_change
from app.models import DailyData, WeeklyData, MonthlyData, Product, OperationAction
from app.schemas.common import ResponseModel

router = APIRouter(prefix="/attribution", tags=["归因分析"])


def detect_anomalies(current: float, previous: float, threshold: float = 0.15) -> dict:
    """检测异动"""
    if previous == 0:
        return {"is_anomaly": False, "change_pct": 0, "severity": "none"}
    
    change_pct = (current - previous) / previous
    
    if abs(change_pct) >= threshold:
        severity = "high" if abs(change_pct) >= 0.3 else "medium" if abs(change_pct) >= 0.15 else "low"
        return {
            "is_anomaly": True,
            "change_pct": round(change_pct * 100, 1),
            "severity": severity,
            "direction": "up" if change_pct > 0 else "down"
        }
    
    return {"is_anomaly": False, "change_pct": round(change_pct * 100, 1), "severity": "none"}


def analyze_product_contribution(db: Session, Model, date_col: str, period: str, 
                                  prev_period: str, metric: str) -> List[dict]:
    """分析商品贡献度"""
    
    current_data = db.query(
        Model.product_id,
        func.sum(getattr(Model, metric)).label('value')
    ).filter(getattr(Model, date_col) == period).group_by(Model.product_id).all()
    
    prev_data = db.query(
        Model.product_id,
        func.sum(getattr(Model, metric)).label('value')
    ).filter(getattr(Model, date_col) == prev_period).group_by(Model.product_id).all()
    
    prev_map = {p.product_id: safe_float(p.value) for p in prev_data}
    
    contributions = []
    total_current = sum(safe_float(c.value) for c in current_data)
    total_prev = sum(prev_map.values())
    total_change = total_current - total_prev
    
    for c in current_data:
        product_id = c.product_id
        current_val = safe_float(c.value)
        prev_val = prev_map.get(product_id, 0)
        change = current_val - prev_val
        
        product = db.query(Product).filter(Product.product_id == product_id).first()
        
        contribution_pct = (change / total_change * 100) if total_change != 0 else 0
        
        contributions.append({
            "product_id": product_id,
            "title": product.title if product else "",
            "tier": product.tier if product else "",
            "current_value": round(current_val, 2),
            "prev_value": round(prev_val, 2),
            "change": round(change, 2),
            "change_pct": round((change / prev_val * 100) if prev_val > 0 else 0, 1),
            "contribution_pct": round(contribution_pct, 1),
            "impact": "positive" if change > 0 else "negative" if change < 0 else "neutral"
        })
    
    contributions.sort(key=lambda x: abs(x["contribution_pct"]), reverse=True)
    
    return contributions[:20]


@router.get("/detect", response_model=ResponseModel)
def detect_all_anomalies(
    dimension: str = Query("weekly", description="时间维度"),
    period: Optional[str] = Query(None, description="指定周期"),
    threshold: float = Query(0.15, description="异动阈值"),
    db: Session = Depends(get_db)
):
    """检测所有指标异动"""
    
    Model, date_col, visitors_col = get_data_model(dimension)
    
    if not period:
        period = get_latest_period(Model, date_col, db)
    
    if not period:
        return ResponseModel(data={"anomalies": [], "period": None})
    
    prev_period = get_prev_period(str(period), dimension)
    
    metrics = [
        ("payment_amount", "GMV", "销售额"),
        (visitors_col, "Visitors", "访客数"),
        ("payment_conversion", "Conversion", "转化率"),
        ("ad_spend", "AdSpend", "广告消耗"),
        ("ad_roi", "ROI", "投产比"),
        ("refund_amount", "Refund", "退款额"),
    ]
    
    anomalies = []
    
    for metric, name, label in metrics:
        current = db.query(func.sum(getattr(Model, metric))).filter(
            getattr(Model, date_col) == period
        ).scalar() or 0
        
        previous = db.query(func.sum(getattr(Model, metric))).filter(
            getattr(Model, date_col) == prev_period
        ).scalar() or 0
        
        current = safe_float(current)
        previous = safe_float(previous)
        
        anomaly = detect_anomalies(current, previous, threshold)
        
        if anomaly["is_anomaly"]:
            anomalies.append({
                "metric": metric,
                "name": name,
                "label": label,
                "current": round(current, 2),
                "previous": round(previous, 2),
                "change": round(current - previous, 2),
                **anomaly
            })
    
    anomalies.sort(key=lambda x: abs(x["change_pct"]), reverse=True)
    
    return ResponseModel(data={
        "dimension": dimension,
        "period": str(period),
        "prev_period": str(prev_period),
        "anomalies": anomalies,
        "total_anomalies": len(anomalies),
        "high_severity": len([a for a in anomalies if a["severity"] == "high"])
    })


@router.get("/drilldown", response_model=ResponseModel)
def drilldown_analysis(
    metric: str = Query("payment_amount", description="分析指标"),
    dimension: str = Query("weekly", description="时间维度"),
    period: Optional[str] = Query(None, description="指定周期"),
    db: Session = Depends(get_db)
):
    """下钻分析 - 定位异动来源"""
    
    Model, date_col, visitors_col = get_data_model(dimension)
    
    if not period:
        period = get_latest_period(Model, date_col, db)
    
    if not period:
        return ResponseModel(data={"contributions": [], "summary": {}})
    
    prev_period = get_prev_period(str(period), dimension)
    
    contributions = analyze_product_contribution(db, Model, date_col, str(period), prev_period, metric)
    
    positive_contributions = [c for c in contributions if c["impact"] == "positive"]
    negative_contributions = [c for c in contributions if c["impact"] == "negative"]
    
    total_positive = sum(c["change"] for c in positive_contributions)
    total_negative = sum(c["change"] for c in negative_contributions)
    
    return ResponseModel(data={
        "metric": metric,
        "dimension": dimension,
        "period": str(period),
        "prev_period": str(prev_period),
        "contributions": contributions,
        "summary": {
            "total_products": len(contributions),
            "positive_count": len(positive_contributions),
            "negative_count": len(negative_contributions),
            "total_positive_change": round(total_positive, 2),
            "total_negative_change": round(total_negative, 2),
            "net_change": round(total_positive + total_negative, 2)
        },
        "top_positive": positive_contributions[:5],
        "top_negative": negative_contributions[:5]
    })


@router.get("/root-cause", response_model=ResponseModel)
def analyze_root_cause(
    product_id: str = Query(..., description="商品ID"),
    dimension: str = Query("weekly", description="时间维度"),
    period: Optional[str] = Query(None, description="指定周期"),
    db: Session = Depends(get_db)
):
    """根因分析 - 分析商品异动原因"""
    
    Model, date_col, visitors_col = get_data_model(dimension)
    
    if not period:
        period = get_latest_period(Model, date_col, db)
    
    if not period:
        return ResponseModel(data={"root_causes": []})
    
    prev_period = get_prev_period(str(period), dimension)
    
    current = db.query(Model).filter(
        Model.product_id == product_id,
        getattr(Model, date_col) == period
    ).first()
    
    previous = db.query(Model).filter(
        Model.product_id == product_id,
        getattr(Model, date_col) == prev_period
    ).first()
    
    if not current or not previous:
        return ResponseModel(data={"root_causes": [], "message": "数据不足"})
    
    root_causes = []
    
    gmv_change = detect_anomalies(
        safe_float(current.payment_amount),
        safe_float(previous.payment_amount)
    )
    if gmv_change["is_anomaly"]:
        visitors_change = detect_anomalies(
            safe_float(getattr(current, visitors_col)),
            safe_float(getattr(previous, visitors_col))
        )
        conversion_change = detect_anomalies(
            safe_float(current.payment_conversion),
            safe_float(previous.payment_conversion)
        )
        aov_change = detect_anomalies(
            safe_float(current.payment_amount) / max(1, safe_float(getattr(current, visitors_col))) if current else 0,
            safe_float(previous.payment_amount) / max(1, safe_float(getattr(previous, visitors_col))) if previous else 0
        )
        
        if visitors_change["is_anomaly"] and visitors_change["direction"] == gmv_change["direction"]:
            root_causes.append({
                "factor": "traffic",
                "label": "流量变化",
                "description": f"访客数{'增加' if visitors_change['direction'] == 'up' else '减少'}{abs(visitors_change['change_pct'])}%，是GMV变化的主要原因",
                "severity": visitors_change["severity"],
                "suggestion": "检查推广渠道、搜索排名、活动曝光" if visitors_change["direction"] == "down" else "继续保持当前引流策略"
            })
        
        if conversion_change["is_anomaly"]:
            root_causes.append({
                "factor": "conversion",
                "label": "转化率变化",
                "description": f"转化率{'提升' if conversion_change['direction'] == 'up' else '下降'}{abs(conversion_change['change_pct'])}%，需要关注详情页质量",
                "severity": conversion_change["severity"],
                "suggestion": "检查详情页、评价、价格竞争力" if conversion_change["direction"] == "down" else "分析成功因素并复制"
            })
        
        if aov_change["is_anomaly"]:
            root_causes.append({
                "factor": "aov",
                "label": "客单价变化",
                "description": f"客单价{'提升' if aov_change['direction'] == 'up' else '下降'}{abs(aov_change['change_pct'])}%",
                "severity": aov_change["severity"],
                "suggestion": "检查关联销售、促销力度" if aov_change["direction"] == "down" else "继续保持连带销售策略"
            })
    
    refund_change = detect_anomalies(
        safe_float(current.refund_amount),
        safe_float(previous.refund_amount)
    )
    if refund_change["is_anomaly"] and refund_change["direction"] == "up":
        root_causes.append({
            "factor": "refund",
            "label": "退款增加",
            "description": f"退款额增加{abs(refund_change['change_pct'])}%，需要关注商品质量或描述准确性",
            "severity": refund_change["severity"],
            "suggestion": "检查退款原因、商品质量、物流时效"
        })
    
    roi_change = detect_anomalies(
        safe_float(current.ad_roi),
        safe_float(previous.ad_roi)
    )
    if roi_change["is_anomaly"]:
        root_causes.append({
            "factor": "ad_roi",
            "label": "广告效率变化",
            "description": f"ROI{'提升' if roi_change['direction'] == 'up' else '下降'}{abs(roi_change['change_pct'])}%",
            "severity": roi_change["severity"],
            "suggestion": "优化投放策略、调整出价、筛选人群" if roi_change["direction"] == "down" else "继续保持当前投放策略"
        })
    
    operations = db.query(OperationAction).filter(
        OperationAction.product_id == product_id,
        OperationAction.action_date >= prev_period,
        OperationAction.action_date <= period
    ).order_by(OperationAction.action_date).all()
    
    if operations:
        for op in operations:
            root_causes.append({
                "factor": "operation",
                "label": f"运营动作: {op.action_type}",
                "description": op.action_detail or f"在{op.action_date}执行了{op.action_type}操作",
                "severity": "info",
                "effect_score": op.effect_score,
                "suggestion": "效果评分: " + (f"{op.effect_score}/10" if op.effect_score else "未评估")
            })
    
    root_causes.sort(key=lambda x: {"high": 0, "medium": 1, "low": 2, "info": 3}.get(x["severity"], 4))
    
    return ResponseModel(data={
        "product_id": product_id,
        "period": str(period),
        "prev_period": str(prev_period),
        "root_causes": root_causes,
        "metrics_comparison": {
            "gmv": {"current": safe_float(current.payment_amount), "previous": safe_float(previous.payment_amount)},
            "visitors": {"current": safe_float(getattr(current, visitors_col)), "previous": safe_float(getattr(previous, visitors_col))},
            "conversion": {"current": safe_float(current.payment_conversion), "previous": safe_float(previous.payment_conversion)},
            "roi": {"current": safe_float(current.ad_roi), "previous": safe_float(previous.ad_roi)},
        }
    })


@router.get("/funnel-drop", response_model=ResponseModel)
def analyze_funnel_drop(
    product_id: Optional[str] = Query(None, description="商品ID"),
    dimension: str = Query("weekly", description="时间维度"),
    period: Optional[str] = Query(None, description="指定周期"),
    db: Session = Depends(get_db)
):
    """漏斗流失分析 - 定位流失最严重的环节"""
    
    Model, date_col, visitors_col = get_data_model(dimension)
    
    if not period:
        period = get_latest_period(Model, date_col, db)
    
    if not period:
        return ResponseModel(data={"funnel": [], "drop_analysis": {}})
    
    query = db.query(
        func.sum(getattr(Model, visitors_col)).label('visitors'),
        func.sum(Model.cart_qty).label('cart'),
        func.sum(Model.payment_qty).label('orders'),
        func.sum(Model.payment_amount).label('gmv'),
    ).filter(getattr(Model, date_col) == period)
    
    if product_id:
        query = query.filter(Model.product_id == product_id)
    
    data = query.first()
    
    if not data:
        return ResponseModel(data={"funnel": [], "drop_analysis": {}})
    
    visitors = safe_float(data.visitors) or 1
    cart = safe_float(data.cart) or 0
    orders = safe_float(data.orders) or 0
    gmv = safe_float(data.gmv) or 0
    
    funnel = [
        {"stage": "访客", "value": int(visitors), "rate": 100},
        {"stage": "加购", "value": int(cart), "rate": round(cart / visitors * 100, 1) if visitors > 0 else 0},
        {"stage": "下单", "value": int(orders), "rate": round(orders / visitors * 100, 1) if visitors > 0 else 0},
        {"stage": "支付", "value": int(orders), "rate": round(orders / visitors * 100, 1) if visitors > 0 else 0},
    ]
    
    drops = []
    for i in range(len(funnel) - 1):
        drop_rate = funnel[i]["rate"] - funnel[i + 1]["rate"]
        drop_count = funnel[i]["value"] - funnel[i + 1]["value"]
        drops.append({
            "from_stage": funnel[i]["stage"],
            "to_stage": funnel[i + 1]["stage"],
            "drop_count": int(drop_count),
            "drop_rate": round(drop_rate, 1),
            "severity": "high" if drop_rate > 50 else "medium" if drop_rate > 30 else "low"
        })
    
    max_drop = max(drops, key=lambda x: x["drop_rate"]) if drops else None
    
    return ResponseModel(data={
        "product_id": product_id,
        "period": str(period),
        "funnel": funnel,
        "drops": drops,
        "max_drop": max_drop,
        "suggestions": generate_funnel_suggestions(max_drop) if max_drop else []
    })


def generate_funnel_suggestions(max_drop: dict) -> List[str]:
    """生成漏斗优化建议"""
    suggestions = []
    
    if max_drop["from_stage"] == "访客" and max_drop["to_stage"] == "加购":
        suggestions.extend([
            "优化商品主图，提升点击吸引力",
            "检查价格竞争力，考虑促销活动",
            "优化详情页首屏内容，快速传达卖点"
        ])
    elif max_drop["from_stage"] == "加购" and max_drop["to_stage"] == "下单":
        suggestions.extend([
            "设置加购提醒或优惠券",
            "优化购物车页面，减少流失",
            "提供限时优惠促进下单"
        ])
    elif max_drop["from_stage"] == "下单" and max_drop["to_stage"] == "支付":
        suggestions.extend([
            "优化支付流程，减少步骤",
            "提供多种支付方式",
            "检查支付页面加载速度"
        ])
    
    return suggestions
