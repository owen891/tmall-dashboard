from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, case
from typing import Optional, List
from app.core.database import get_db
from app.core.utils import get_data_model, get_prev_period, get_latest_period, safe_float
from app.models import DailyData, WeeklyData, MonthlyData, ProductHealth, Product
from app.schemas.common import ResponseModel

router = APIRouter(prefix="/health", tags=["健康度分析"])

HEALTH_DIMENSIONS = [
    {'key': 'gmv_change_score', 'label': 'GSV环比', 'weight': 0.15},
    {'key': 'ad_spend_change_score', 'label': '总推广花费环比', 'weight': 0.08},
    {'key': 'roi_change_score', 'label': '直接ROI环比', 'weight': 0.10},
    {'key': 'refund_rate_score', 'label': '退款率', 'weight': 0.10},
    {'key': 'cart_rate_score', 'label': '加购率', 'weight': 0.08},
    {'key': 'search_ratio_score', 'label': '引潜比', 'weight': 0.07},
    {'key': 'new_customer_cost_score', 'label': '拉新成本', 'weight': 0.07},
    {'key': 'direct_cart_cost_score', 'label': '直接加购成本', 'weight': 0.05},
    {'key': 'total_cart_cost_score', 'label': '总加购成本', 'weight': 0.05},
    {'key': 'repurchase_rate_score', 'label': '复购率', 'weight': 0.08},
    {'key': 'cross_sell_rate_score', 'label': '连带率', 'weight': 0.07},
    {'key': 'search_ctr_vs_industry_score', 'label': '搜索点击率vs行业', 'weight': 0.10},
]


def calculate_health_score_12dim(current_data: dict, prev_data: dict = None) -> dict:
    scores = {}
    details = {}
    alerts = []
    
    gmv = current_data.get('payment_amount', 0) or 0
    refund = current_data.get('refund_amount', 0) or 0
    visitors = current_data.get('visitors', 0) or 0
    conversion = current_data.get('conversion', 0) or 0
    roi = current_data.get('roi', 0) or 0
    ad_spend = current_data.get('ad_spend', 0) or 0
    cart_count = current_data.get('cart_count', 0) or 0
    search_visitors = current_data.get('search_visitors', 0) or 0
    new_customers = current_data.get('new_customers', 0) or 0
    new_customer_cost = current_data.get('new_customer_cost', 0) or 0
    direct_cart_cost = current_data.get('direct_cart_cost', 0) or 0
    total_cart_cost = current_data.get('total_cart_cost', 0) or 0
    repurchase_rate = current_data.get('repurchase_rate', 0) or 0
    cross_sell_rate = current_data.get('cross_sell_rate', 0) or 0
    search_ctr = current_data.get('search_ctr', 0) or 0
    
    prev_gmv = prev_data.get('payment_amount', 0) or 0 if prev_data else 0
    prev_ad_spend = prev_data.get('ad_spend', 0) or 0 if prev_data else 0
    prev_roi = prev_data.get('roi', 0) or 0 if prev_data else 0
    
    if prev_gmv > 0:
        gmv_change = (gmv - prev_gmv) / prev_gmv * 100
        if gmv_change > 20:
            scores['gmv_change_score'] = 100
            details['gmv_change_score'] = f"GSV环比增长{gmv_change:.1f}%，优秀"
        elif gmv_change > 0:
            scores['gmv_change_score'] = 80
            details['gmv_change_score'] = f"GSV环比增长{gmv_change:.1f}%，良好"
        elif gmv_change > -10:
            scores['gmv_change_score'] = 60
            details['gmv_change_score'] = f"GSV环比下降{abs(gmv_change):.1f}%，需关注"
        else:
            scores['gmv_change_score'] = 30
            details['gmv_change_score'] = f"GSV环比下降{abs(gmv_change):.1f}%，严重"
            alerts.append({"dimension": "GSV环比", "level": "high", "message": f"GSV环比下降{abs(gmv_change):.1f}%，需立即分析原因"})
    else:
        scores['gmv_change_score'] = 50
        details['gmv_change_score'] = "无上期数据对比"
    
    if prev_ad_spend > 0:
        ad_change = (ad_spend - prev_ad_spend) / prev_ad_spend * 100
        if ad_change < 0:
            scores['ad_spend_change_score'] = 100
            details['ad_spend_change_score'] = f"推广花费下降{abs(ad_change):.1f}%，成本优化"
        elif ad_change < 10:
            scores['ad_spend_change_score'] = 80
            details['ad_spend_change_score'] = f"推广花费增长{ad_change:.1f}%，可控"
        elif ad_change < 30:
            scores['ad_spend_change_score'] = 60
            details['ad_spend_change_score'] = f"推广花费增长{ad_change:.1f}%，需关注ROI"
        else:
            scores['ad_spend_change_score'] = 30
            details['ad_spend_change_score'] = f"推广花费增长{ad_change:.1f}%，过高"
            alerts.append({"dimension": "推广花费", "level": "warning", "message": f"推广花费环比增长{ad_change:.1f}%，需关注效率"})
    else:
        scores['ad_spend_change_score'] = 50
        details['ad_spend_change_score'] = "无上期数据对比"
    
    if prev_roi > 0 and roi > 0:
        roi_change = (roi - prev_roi) / prev_roi * 100
        if roi_change > 20:
            scores['roi_change_score'] = 100
            details['roi_change_score'] = f"ROI环比增长{roi_change:.1f}%，优秀"
        elif roi_change > 0:
            scores['roi_change_score'] = 80
            details['roi_change_score'] = f"ROI环比增长{roi_change:.1f}%，良好"
        elif roi_change > -10:
            scores['roi_change_score'] = 60
            details['roi_change_score'] = f"ROI环比下降{abs(roi_change):.1f}%，需关注"
        else:
            scores['roi_change_score'] = 30
            details['roi_change_score'] = f"ROI环比下降{abs(roi_change):.1f}%，严重"
            alerts.append({"dimension": "ROI环比", "level": "high", "message": f"ROI环比下降{abs(roi_change):.1f}%，需优化投放"})
    else:
        scores['roi_change_score'] = 50
        details['roi_change_score'] = "无上期数据对比"
    
    refund_rate = refund / gmv if gmv > 0 else 0
    if refund_rate < 0.02:
        scores['refund_rate_score'] = 100
        details['refund_rate_score'] = f"退款率{refund_rate*100:.2f}%，优秀"
    elif refund_rate < 0.05:
        scores['refund_rate_score'] = 80
        details['refund_rate_score'] = f"退款率{refund_rate*100:.2f}%，良好"
    elif refund_rate < 0.10:
        scores['refund_rate_score'] = 60
        details['refund_rate_score'] = f"退款率{refund_rate*100:.2f}%，需关注"
        alerts.append({"dimension": "退款率", "level": "warning", "message": f"退款率{refund_rate*100:.2f}%偏高"})
    else:
        scores['refund_rate_score'] = 30
        details['refund_rate_score'] = f"退款率{refund_rate*100:.2f}%，严重"
        alerts.append({"dimension": "退款率", "level": "high", "message": f"退款率{refund_rate*100:.2f}%过高，需立即处理"})
    
    cart_rate = cart_count / visitors if visitors > 0 else 0
    if cart_rate > 0.15:
        scores['cart_rate_score'] = 100
        details['cart_rate_score'] = f"加购率{cart_rate*100:.2f}%，优秀"
    elif cart_rate > 0.08:
        scores['cart_rate_score'] = 80
        details['cart_rate_score'] = f"加购率{cart_rate*100:.2f}%，良好"
    elif cart_rate > 0.03:
        scores['cart_rate_score'] = 60
        details['cart_rate_score'] = f"加购率{cart_rate*100:.2f}%，一般"
    else:
        scores['cart_rate_score'] = 40
        details['cart_rate_score'] = f"加购率{cart_rate*100:.2f}%，需优化"
    
    search_ratio = search_visitors / visitors if visitors > 0 and search_visitors > 0 else 0.3
    if search_ratio > 0.5:
        scores['search_ratio_score'] = 100
        details['search_ratio_score'] = f"引潜比{search_ratio*100:.1f}%，搜索流量占比高"
    elif search_ratio > 0.3:
        scores['search_ratio_score'] = 80
        details['search_ratio_score'] = f"引潜比{search_ratio*100:.1f}%，良好"
    elif search_ratio > 0.15:
        scores['search_ratio_score'] = 60
        details['search_ratio_score'] = f"引潜比{search_ratio*100:.1f}%，一般"
    else:
        scores['search_ratio_score'] = 40
        details['search_ratio_score'] = f"引潜比{search_ratio*100:.1f}%，需提升搜索流量"
    
    if new_customers > 0 and ad_spend > 0:
        actual_new_customer_cost = ad_spend / new_customers
        if actual_new_customer_cost < 30:
            scores['new_customer_cost_score'] = 100
            details['new_customer_cost_score'] = f"拉新成本{actual_new_customer_cost:.1f}元，优秀"
        elif actual_new_customer_cost < 50:
            scores['new_customer_cost_score'] = 80
            details['new_customer_cost_score'] = f"拉新成本{actual_new_customer_cost:.1f}元，良好"
        elif actual_new_customer_cost < 80:
            scores['new_customer_cost_score'] = 60
            details['new_customer_cost_score'] = f"拉新成本{actual_new_customer_cost:.1f}元，一般"
        else:
            scores['new_customer_cost_score'] = 30
            details['new_customer_cost_score'] = f"拉新成本{actual_new_customer_cost:.1f}元，过高"
            alerts.append({"dimension": "拉新成本", "level": "warning", "message": f"拉新成本{actual_new_customer_cost:.1f}元过高"})
    else:
        scores['new_customer_cost_score'] = 50
        details['new_customer_cost_score'] = "暂无拉新数据"
    
    if direct_cart_cost > 0:
        if direct_cart_cost < 5:
            scores['direct_cart_cost_score'] = 100
            details['direct_cart_cost_score'] = f"直接加购成本{direct_cart_cost:.1f}元，优秀"
        elif direct_cart_cost < 10:
            scores['direct_cart_cost_score'] = 80
            details['direct_cart_cost_score'] = f"直接加购成本{direct_cart_cost:.1f}元，良好"
        elif direct_cart_cost < 20:
            scores['direct_cart_cost_score'] = 60
            details['direct_cart_cost_score'] = f"直接加购成本{direct_cart_cost:.1f}元，一般"
        else:
            scores['direct_cart_cost_score'] = 40
            details['direct_cart_cost_score'] = f"直接加购成本{direct_cart_cost:.1f}元，过高"
    else:
        scores['direct_cart_cost_score'] = 50
        details['direct_cart_cost_score'] = "暂无数据"
    
    if total_cart_cost > 0:
        if total_cart_cost < 8:
            scores['total_cart_cost_score'] = 100
            details['total_cart_cost_score'] = f"总加购成本{total_cart_cost:.1f}元，优秀"
        elif total_cart_cost < 15:
            scores['total_cart_cost_score'] = 80
            details['total_cart_cost_score'] = f"总加购成本{total_cart_cost:.1f}元，良好"
        elif total_cart_cost < 25:
            scores['total_cart_cost_score'] = 60
            details['total_cart_cost_score'] = f"总加购成本{total_cart_cost:.1f}元，一般"
        else:
            scores['total_cart_cost_score'] = 40
            details['total_cart_cost_score'] = f"总加购成本{total_cart_cost:.1f}元，过高"
    else:
        scores['total_cart_cost_score'] = 50
        details['total_cart_cost_score'] = "暂无数据"
    
    if repurchase_rate > 0:
        if repurchase_rate > 0.3:
            scores['repurchase_rate_score'] = 100
            details['repurchase_rate_score'] = f"复购率{repurchase_rate*100:.1f}%，优秀"
        elif repurchase_rate > 0.15:
            scores['repurchase_rate_score'] = 80
            details['repurchase_rate_score'] = f"复购率{repurchase_rate*100:.1f}%，良好"
        elif repurchase_rate > 0.05:
            scores['repurchase_rate_score'] = 60
            details['repurchase_rate_score'] = f"复购率{repurchase_rate*100:.1f}%，一般"
        else:
            scores['repurchase_rate_score'] = 40
            details['repurchase_rate_score'] = f"复购率{repurchase_rate*100:.1f}%，需提升"
    else:
        scores['repurchase_rate_score'] = 50
        details['repurchase_rate_score'] = "暂无复购数据"
    
    if cross_sell_rate > 0:
        if cross_sell_rate > 1.5:
            scores['cross_sell_rate_score'] = 100
            details['cross_sell_rate_score'] = f"连带率{cross_sell_rate:.2f}，优秀"
        elif cross_sell_rate > 1.2:
            scores['cross_sell_rate_score'] = 80
            details['cross_sell_rate_score'] = f"连带率{cross_sell_rate:.2f}，良好"
        elif cross_sell_rate > 1.0:
            scores['cross_sell_rate_score'] = 60
            details['cross_sell_rate_score'] = f"连带率{cross_sell_rate:.2f}，一般"
        else:
            scores['cross_sell_rate_score'] = 40
            details['cross_sell_rate_score'] = f"连带率{cross_sell_rate:.2f}，需提升"
    else:
        scores['cross_sell_rate_score'] = 50
        details['cross_sell_rate_score'] = "暂无连带数据"
    
    industry_ctr = 0.05
    if search_ctr > 0:
        ctr_ratio = search_ctr / industry_ctr
        if ctr_ratio > 1.5:
            scores['search_ctr_vs_industry_score'] = 100
            details['search_ctr_vs_industry_score'] = f"搜索CTR高于行业{((ctr_ratio-1)*100):.0f}%，优秀"
        elif ctr_ratio > 1.0:
            scores['search_ctr_vs_industry_score'] = 80
            details['search_ctr_vs_industry_score'] = f"搜索CTR高于行业{((ctr_ratio-1)*100):.0f}%，良好"
        elif ctr_ratio > 0.7:
            scores['search_ctr_vs_industry_score'] = 60
            details['search_ctr_vs_industry_score'] = f"搜索CTR低于行业{((1-ctr_ratio)*100):.0f}%，需优化"
        else:
            scores['search_ctr_vs_industry_score'] = 30
            details['search_ctr_vs_industry_score'] = f"搜索CTR低于行业{((1-ctr_ratio)*100):.0f}%，严重"
            alerts.append({"dimension": "搜索CTR", "level": "high", "message": "搜索点击率明显低于行业均值"})
    else:
        scores['search_ctr_vs_industry_score'] = 50
        details['search_ctr_vs_industry_score'] = "暂无搜索CTR数据"
    
    total_weight = sum(d['weight'] for d in HEALTH_DIMENSIONS)
    weighted_score = sum(scores.get(d['key'], 50) * d['weight'] for d in HEALTH_DIMENSIONS)
    total_score = weighted_score / total_weight if total_weight > 0 else 50
    
    if total_score >= 80:
        health_level = "优秀"
    elif total_score >= 60:
        health_level = "良好"
    elif total_score >= 40:
        health_level = "关注"
    else:
        health_level = "预警"
    
    alert_dimensions = []
    for dim in HEALTH_DIMENSIONS:
        score = scores.get(dim['key'], 50)
        if score < 40:
            alert_dimensions.append({
                "key": dim['key'],
                "label": dim['label'],
                "score": score
            })
    
    return {
        "total_score": round(total_score, 1),
        "health_level": health_level,
        "scores": scores,
        "details": details,
        "alerts": alerts,
        "alert_dimensions": alert_dimensions
    }


@router.get("/list", response_model=ResponseModel)
def get_health_list(
    dimension: str = Query("weekly", description="时间维度: daily/weekly/monthly"),
    period: Optional[str] = Query(None, description="指定周期"),
    health_level: Optional[str] = Query(None, description="健康等级筛选"),
    page: int = Query(1, description="页码"),
    page_size: int = Query(20, description="每页数量"),
    db: Session = Depends(get_db)
):
    Model, date_col, visitors_col = get_data_model(dimension)
    
    if not period:
        period = get_latest_period(Model, date_col, db)
    
    if not period:
        return ResponseModel(data={"products": [], "total": 0, "page": page, "page_size": page_size})
    
    prev_period = get_prev_period(str(period), dimension)
    
    filter_conditions = [getattr(Model, date_col) == period]
    if health_level:
        filter_conditions.append(Product.health_level == health_level)
    
    products_query = db.query(
        Model.product_id,
        Product.title.label('product_name'),
        Product.category,
        Product.tier,
        Product.style,
        func.sum(Model.payment_amount).label('payment_amount'),
        func.sum(Model.refund_amount).label('refund_amount'),
        func.sum(getattr(Model, visitors_col)).label('visitors'),
        func.avg(Model.payment_conversion).label('conversion'),
        func.sum(Model.ad_spend).label('ad_spend'),
        func.avg(Model.ad_roi).label('roi'),
        func.sum(Model.cart_count).label('cart_count'),
        func.sum(Model.search_visitors).label('search_visitors'),
        func.sum(Model.new_customers).label('new_customers'),
        func.avg(Model.new_customer_cost).label('new_customer_cost'),
        func.avg(Model.direct_cart_cost).label('direct_cart_cost'),
        func.avg(Model.total_cart_cost).label('total_cart_cost'),
        func.avg(Model.repurchase_rate).label('repurchase_rate'),
        func.avg(Model.cross_sell_rate).label('cross_sell_rate'),
        func.avg(Model.search_ctr).label('search_ctr'),
    ).join(Product, Model.product_id == Product.product_id).filter(*filter_conditions).group_by(
        Model.product_id,
        Product.title,
        Product.category,
        Product.tier,
        Product.style
    )
    
    total = products_query.count()
    products_data = products_query.offset((page - 1) * page_size).limit(page_size).all()
    
    prev_data_map = {}
    if prev_period:
        prev_query = db.query(
            Model.product_id,
            func.sum(Model.payment_amount).label('payment_amount'),
            func.sum(Model.ad_spend).label('ad_spend'),
            func.avg(Model.ad_roi).label('roi'),
        ).filter(getattr(Model, date_col) == prev_period).group_by(Model.product_id).all()
        
        for p in prev_query:
            prev_data_map[p.product_id] = {
                'payment_amount': p.payment_amount,
                'ad_spend': p.ad_spend,
                'roi': p.roi
            }
    
    products = []
    for p in products_data:
        current_data = {
            'payment_amount': safe_float(p.payment_amount),
            'refund_amount': safe_float(p.refund_amount),
            'visitors': int(safe_float(p.visitors)),
            'conversion': safe_float(p.conversion),
            'ad_spend': safe_float(p.ad_spend),
            'roi': safe_float(p.roi) if p.roi else 0,
            'cart_count': safe_float(p.cart_count),
            'search_visitors': safe_float(p.search_visitors),
            'new_customers': safe_float(p.new_customers),
            'new_customer_cost': safe_float(p.new_customer_cost),
            'direct_cart_cost': safe_float(p.direct_cart_cost),
            'total_cart_cost': safe_float(p.total_cart_cost),
            'repurchase_rate': safe_float(p.repurchase_rate),
            'cross_sell_rate': safe_float(p.cross_sell_rate),
            'search_ctr': safe_float(p.search_ctr),
        }
        
        prev_data = prev_data_map.get(p.product_id, {})
        
        health = calculate_health_score_12dim(current_data, prev_data)
        
        products.append({
            'product_id': p.product_id,
            'product_name': p.product_name,
            'category': p.category,
            'tier': p.tier,
            'style': p.style,
            'payment_amount': current_data['payment_amount'],
            'health_score': health['total_score'],
            'health_level': health['health_level'],
            'scores': health['scores'],
            'details': health['details'],
            'alerts': health['alerts'],
            'alert_dimensions': health['alert_dimensions']
        })
    
    products.sort(key=lambda x: x['health_score'])
    
    return ResponseModel(data={
        "products": products,
        "total": total,
        "page": page,
        "page_size": page_size,
        "period": str(period),
        "dimension": dimension,
        "dimensions": HEALTH_DIMENSIONS
    })


@router.get("/summary", response_model=ResponseModel)
def get_health_summary(
    dimension: str = Query("weekly", description="时间维度"),
    period: Optional[str] = Query(None, description="指定周期"),
    db: Session = Depends(get_db)
):
    Model, date_col, visitors_col = get_data_model(dimension)
    
    if not period:
        period = get_latest_period(Model, date_col, db)
    
    if not period:
        return ResponseModel(data={"summary": {}, "by_level": [], "dimensions": HEALTH_DIMENSIONS})
    
    prev_period = get_prev_period(str(period), dimension)
    
    filter_cond = getattr(Model, date_col) == period
    
    products_data = db.query(
        Model.product_id,
        func.sum(Model.payment_amount).label('payment_amount'),
        func.sum(Model.refund_amount).label('refund_amount'),
        func.sum(getattr(Model, visitors_col)).label('visitors'),
        func.avg(Model.payment_conversion).label('conversion'),
        func.sum(Model.ad_spend).label('ad_spend'),
        func.avg(Model.ad_roi).label('roi'),
        func.sum(Model.cart_count).label('cart_count'),
        func.sum(Model.search_visitors).label('search_visitors'),
        func.sum(Model.new_customers).label('new_customers'),
        func.avg(Model.new_customer_cost).label('new_customer_cost'),
        func.avg(Model.direct_cart_cost).label('direct_cart_cost'),
        func.avg(Model.total_cart_cost).label('total_cart_cost'),
        func.avg(Model.repurchase_rate).label('repurchase_rate'),
        func.avg(Model.cross_sell_rate).label('cross_sell_rate'),
        func.avg(Model.search_ctr).label('search_ctr'),
    ).filter(filter_cond).group_by(Model.product_id).all()
    
    prev_data_map = {}
    if prev_period:
        prev_query = db.query(
            Model.product_id,
            func.sum(Model.payment_amount).label('payment_amount'),
            func.sum(Model.ad_spend).label('ad_spend'),
            func.avg(Model.ad_roi).label('roi'),
        ).filter(getattr(Model, date_col) == prev_period).group_by(Model.product_id).all()
        
        for p in prev_query:
            prev_data_map[p.product_id] = {
                'payment_amount': p.payment_amount,
                'ad_spend': p.ad_spend,
                'roi': p.roi
            }
    
    level_counts = {"优秀": 0, "良好": 0, "关注": 0, "预警": 0}
    dimension_scores = {d['key']: 0 for d in HEALTH_DIMENSIONS}
    product_count = len(products_data)
    
    for p in products_data:
        current_data = {
            'payment_amount': safe_float(p.payment_amount),
            'refund_amount': safe_float(p.refund_amount),
            'visitors': int(safe_float(p.visitors)),
            'conversion': safe_float(p.conversion),
            'ad_spend': safe_float(p.ad_spend),
            'roi': safe_float(p.roi) if p.roi else 0,
            'cart_count': safe_float(p.cart_count),
            'search_visitors': safe_float(p.search_visitors),
            'new_customers': safe_float(p.new_customers),
            'new_customer_cost': safe_float(p.new_customer_cost),
            'direct_cart_cost': safe_float(p.direct_cart_cost),
            'total_cart_cost': safe_float(p.total_cart_cost),
            'repurchase_rate': safe_float(p.repurchase_rate),
            'cross_sell_rate': safe_float(p.cross_sell_rate),
            'search_ctr': safe_float(p.search_ctr),
        }
        
        prev_data = prev_data_map.get(p.product_id, {})
        health = calculate_health_score_12dim(current_data, prev_data)
        
        level_counts[health['health_level']] += 1
        for key, score in health['scores'].items():
            dimension_scores[key] += score
    
    avg_dimension_scores = {}
    if product_count > 0:
        for key in dimension_scores:
            avg_dimension_scores[key] = round(dimension_scores[key] / product_count, 1)
    
    by_level = [
        {"level": "excellent", "label": "优秀", "count": level_counts["优秀"], "percent": round(level_counts["优秀"] / product_count * 100, 1) if product_count > 0 else 0},
        {"level": "good", "label": "良好", "count": level_counts["良好"], "percent": round(level_counts["良好"] / product_count * 100, 1) if product_count > 0 else 0},
        {"level": "warning", "label": "关注", "count": level_counts["关注"], "percent": round(level_counts["关注"] / product_count * 100, 1) if product_count > 0 else 0},
        {"level": "danger", "label": "预警", "count": level_counts["预警"], "percent": round(level_counts["预警"] / product_count * 100, 1) if product_count > 0 else 0},
    ]
    
    return ResponseModel(data={
        "summary": {
            "product_count": product_count,
            "excellent_count": level_counts["优秀"],
            "good_count": level_counts["良好"],
            "warning_count": level_counts["关注"],
            "danger_count": level_counts["预警"],
            "dimension_avg_scores": avg_dimension_scores
        },
        "by_level": by_level,
        "period": str(period),
        "dimension": dimension,
        "dimensions": HEALTH_DIMENSIONS
    })


@router.get("/{product_id}", response_model=ResponseModel)
def get_product_health(
    product_id: str,
    dimension: str = Query("weekly", description="时间维度"),
    db: Session = Depends(get_db)
):
    Model, date_col, visitors_col = get_data_model(dimension)
    
    data_list = db.query(Model, Product.title.label('product_name'), Product.category).join(
        Product, Model.product_id == Product.product_id
    ).filter(
        Model.product_id == product_id
    ).order_by(desc(getattr(Model, date_col))).limit(12).all()
    
    if not data_list:
        return ResponseModel(data={"product": None, "trend": []})
    
    trend = []
    
    for item in reversed(data_list):
        data = item[0]
        data_product_name = item[1]
        data_category = item[2]
        period = None
        if date_col == 'month':
            period = data.month
        elif date_col == 'week_start':
            period = data.week_start.isoformat() if hasattr(data.week_start, 'isoformat') else str(data.week_start)
        else:
            period = data.date.isoformat() if hasattr(data.date, 'isoformat') else str(data.date)
        
        current_data = {
            'payment_amount': data.payment_amount or 0,
            'refund_amount': data.refund_amount or 0,
            'visitors': getattr(data, visitors_col) or 0,
            'conversion': data.payment_conversion or 0,
            'ad_spend': data.ad_spend or 0,
            'roi': data.ad_roi or 0,
            'cart_count': getattr(data, 'cart_count', 0) or 0,
            'search_visitors': getattr(data, 'search_visitors', 0) or 0,
            'new_customers': getattr(data, 'new_customers', 0) or 0,
            'new_customer_cost': getattr(data, 'new_customer_cost', 0) or 0,
            'direct_cart_cost': getattr(data, 'direct_cart_cost', 0) or 0,
            'total_cart_cost': getattr(data, 'total_cart_cost', 0) or 0,
            'repurchase_rate': getattr(data, 'repurchase_rate', 0) or 0,
            'cross_sell_rate': getattr(data, 'cross_sell_rate', 0) or 0,
            'search_ctr': getattr(data, 'search_ctr', 0) or 0,
        }
        
        health = calculate_health_score_12dim(current_data, None)
        
        trend.append({
            "period": period,
            **current_data,
            'health_score': health['total_score'],
            'health_level': health['health_level'],
            'scores': health['scores'],
        })
    
    return ResponseModel(data={
        "product": {
            "product_id": product_id,
            "product_name": data_product_name,
            "category": data_category,
            "current_health": trend[-1] if trend else None,
            "trend": trend
        },
        "dimension": dimension,
        "dimensions": HEALTH_DIMENSIONS
    })


@router.get("/alerts", response_model=ResponseModel)
def get_health_alerts(
    dimension: str = Query("weekly", description="时间维度"),
    period: Optional[str] = Query(None, description="指定周期"),
    level: Optional[str] = Query(None, description="告警级别: high/warning"),
    limit: int = Query(20, description="返回数量"),
    db: Session = Depends(get_db)
):
    Model, date_col, visitors_col = get_data_model(dimension)
    
    if not period:
        period = get_latest_period(Model, date_col, db)
    
    if not period:
        return ResponseModel(data={"alerts": []})
    
    prev_period = get_prev_period(str(period), dimension)
    
    filter_cond = getattr(Model, date_col) == period
    
    products_data = db.query(
        Model.product_id,
        Product.title.label('product_name'),
        func.sum(Model.payment_amount).label('payment_amount'),
        func.sum(Model.refund_amount).label('refund_amount'),
        func.sum(getattr(Model, visitors_col)).label('visitors'),
        func.avg(Model.payment_conversion).label('conversion'),
        func.sum(Model.ad_spend).label('ad_spend'),
        func.avg(Model.ad_roi).label('roi'),
    ).join(Product, Model.product_id == Product.product_id).filter(filter_cond).group_by(
        Model.product_id,
        Product.title
    ).all()
    
    prev_data_map = {}
    if prev_period:
        prev_query = db.query(
            Model.product_id,
            func.sum(Model.payment_amount).label('payment_amount'),
            func.sum(Model.ad_spend).label('ad_spend'),
            func.avg(Model.ad_roi).label('roi'),
        ).filter(getattr(Model, date_col) == prev_period).group_by(Model.product_id).all()
        
        for p in prev_query:
            prev_data_map[p.product_id] = {
                'payment_amount': p.payment_amount,
                'ad_spend': p.ad_spend,
                'roi': p.roi
            }
    
    all_alerts = []
    for p in products_data:
        current_data = {
            'payment_amount': safe_float(p.payment_amount),
            'refund_amount': safe_float(p.refund_amount),
            'visitors': int(safe_float(p.visitors)),
            'conversion': safe_float(p.conversion),
            'ad_spend': safe_float(p.ad_spend),
            'roi': safe_float(p.roi) if p.roi else 0,
        }
        
        prev_data = prev_data_map.get(p.product_id, {})
        health = calculate_health_score_12dim(current_data, prev_data)
        
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
