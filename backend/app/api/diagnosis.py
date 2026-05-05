from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import Optional, List
from app.core.database import get_db
from app.models import ProductTrafficDetail, MonthlyPlanning, Product, ProductLifecycle
from app.schemas.common import ResponseModel

router = APIRouter(prefix="/diagnosis", tags=["商品诊断报告"])

def diagnose_traffic(visitors, page_views, bounce_rate=None, avg_stay=None):
    """流量诊断"""
    issues = []
    suggestions = []
    if visitors < 100:
        issues.append("流量偏低")
        suggestions.append("增加关键词推广和全站推广投入，优化商品标题和主图提升自然搜索曝光")
    if page_views / max(visitors, 1) < 1.5:
        issues.append("访问深度不足")
        suggestions.append("优化详情页布局，增加关联推荐和搭配商品展示")
    if bounce_rate and bounce_rate > 0.7:
        issues.append("跳失率过高")
        suggestions.append("优化主图和详情页首屏，确保卖点突出、价格竞争力")
    if avg_stay and avg_stay < 15:
        issues.append("停留时间偏短")
        suggestions.append("增加视频/动图、买家秀、使用场景等富媒体内容")
    return issues, suggestions

def diagnose_conversion(conversion_rate, payment_conversion=None, target_conversion=None):
    """转化诊断"""
    issues = []
    suggestions = []
    cvr = payment_conversion if payment_conversion is not None else conversion_rate
    if cvr is not None:
        if cvr < 0.02:
            issues.append("转化率偏低")
            suggestions.append("检查价格竞争力、评价质量、详情页说服力，考虑增加促销活动")
        if cvr < 0.01:
            issues.append("转化率严重不足")
            suggestions.append("建议优化主图、评价管理、增加买家秀和问大家互动")
    if target_conversion and cvr and cvr < target_conversion:
        issues.append("未达转化目标")
        gap = round((target_conversion - cvr) * 100, 2)
        suggestions.append(f"转化率与目标差距 {gap}%，建议优化详情页和优化评价")
    return issues, suggestions

def diagnose_traffic_sources(search_visitors, recommend_visitors, total_visitors, search_payment=None, recommend_payment=None):
    """流量结构诊断"""
    issues = []
    suggestions = []
    if total_visitors > 0:
        search_ratio = search_visitors / total_visitors
        recommend_ratio = recommend_visitors / total_visitors
        if search_ratio < 0.3:
            issues.append("搜索流量占比低")
            suggestions.append("优化关键词推广和商品标题SEO，提升搜索排名")
        if recommend_ratio < 0.15:
            issues.append("推荐流量不足")
            suggestions.append("优化商品标签和类目属性，提升猜你喜欢等推荐流量获取能力")
        if search_ratio > 0.8 and recommend_ratio < 0.05:
            issues.append("流量来源过于单一")
            suggestions.append("建议多元化流量获取，增加内容营销和推荐流量")
    return issues, suggestions

def diagnose_ad_efficiency(ad_spend, ad_roi, keyword_roi=None, audience_roi=None, 
                           scene_roi=None, full_site_roi=None, ad_ratio=None):
    """广告效率诊断"""
    issues = []
    suggestions = []
    if ad_spend > 0:
        if ad_roi and ad_roi < 1.5:
            issues.append("广告ROI偏低")
            suggestions.append("优化推广计划出价策略和人群定向，降低无效点击")
        if ad_roi and ad_roi < 1.0:
            issues.append("广告亏损")
            suggestions.append("暂停低效推广词/人群，集中预算到高转化渠道")
        if ad_ratio and ad_ratio > 0.4:
            issues.append("付费占比过高")
            suggestions.append("需要提升自然流量获取能力，降低对付费流量的依赖")
        
        if keyword_roi and audience_roi and keyword_roi > audience_roi * 1.5:
            issues.append("人群推广ROI偏低")
            suggestions.append("优化人群定向，排除低转化人群包")
        if scene_roi and scene_roi < 1.0:
            issues.append("场景推广ROI偏低")
            suggestions.append("优化场景创意和投放时段")
        if full_site_roi and full_site_roi > 0 and full_site_roi < 1.5:
            issues.append("全站推广效率待提升")
            suggestions.append("优化全站推广预算分配和出价")
    return issues, suggestions

def diagnose_inventory_and_cart(cart_rate, fav_rate, payment_conversion, cart_conversion=None):
    """加购收藏诊断"""
    issues = []
    suggestions = []
    if cart_rate and cart_rate < 0.05:
        issues.append("加购率偏低")
        suggestions.append("优化价格策略，增加限时优惠和满减活动促进加购")
    if fav_rate and fav_rate < 0.03:
        issues.append("收藏率偏低")
        suggestions.append("优化主图和价格展示，增加收藏引导")
    if cart_rate and cart_rate > 0.15 and payment_conversion and payment_conversion < 0.05:
        issues.append("加购到支付转化低")
        suggestions.append("检查支付流程是否顺畅，考虑发送优惠券促转化")
    return issues, suggestions

def diagnose_vs_target(actual_payment, target_payment, actual_roi=None, target_roi=None):
    """目标达成诊断"""
    issues = []
    suggestions = []
    if target_payment and target_payment > 0:
        achievement = (actual_payment / target_payment * 100) if actual_payment else 0
        if achievement < 80:
            issues.append(f"目标达成率偏低 ({round(achievement, 1)}%)")
            suggestions.append("需要加大推广力度或调整销售策略")
        elif achievement < 95:
            issues.append(f"目标达成接近但仍有差距 ({round(achievement, 1)}%)")
            suggestions.append("继续保持当前策略，关注关键指标提升")
        else:
            suggestions.append(f"目标达成良好 ({round(achievement, 1)}%)")
    if actual_roi and target_roi and actual_roi < target_roi:
        issues.append("广告ROI未达目标")
        gap = round(target_roi - actual_roi, 2)
        suggestions.append(f"ROI差距 {gap}，需要优化推广策略")
    return issues, suggestions

def calculate_health_score(visitors=0, conversion=0, ad_roi=0, achievement=0, 
                           cart_rate=0, search_ratio=0):
    """计算商品健康评分 (0-100)"""
    score = 0
    weights = {
        'conversion': 25,
        'traffic': 20,
        'roi': 20,
        'achievement': 20,
        'engagement': 15,
    }
    
    if conversion >= 0.05:
        score += weights['conversion']
    elif conversion >= 0.03:
        score += weights['conversion'] * 0.7
    elif conversion >= 0.02:
        score += weights['conversion'] * 0.5
    elif conversion > 0:
        score += weights['conversion'] * 0.3
    
    if visitors >= 500:
        score += weights['traffic']
    elif visitors >= 200:
        score += weights['traffic'] * 0.7
    elif visitors >= 50:
        score += weights['traffic'] * 0.4
    
    if ad_roi >= 3.0:
        score += weights['roi']
    elif ad_roi >= 2.0:
        score += weights['roi'] * 0.7
    elif ad_roi >= 1.0:
        score += weights['roi'] * 0.4
    
    if achievement >= 100:
        score += weights['achievement']
    elif achievement >= 80:
        score += weights['achievement'] * 0.7
    elif achievement >= 60:
        score += weights['achievement'] * 0.4
    
    if cart_rate >= 0.10:
        score += weights['engagement']
    elif cart_rate >= 0.05:
        score += weights['engagement'] * 0.6
    
    return round(min(score, 100), 1)

def generate_report_label(score):
    """根据评分生成报告标签"""
    if score >= 85:
        return "优秀"
    elif score >= 70:
        return "良好"
    elif score >= 50:
        return "需改进"
    else:
        return "急需优化"


@router.get("/product/{product_id}", response_model=ResponseModel)
def get_product_diagnosis(
    product_id: str,
    start_date: Optional[str] = Query(None, description="开始日期"),
    end_date: Optional[str] = Query(None, description="结束日期"),
    db: Session = Depends(get_db)
):
    """获取单个商品的完整诊断报告"""
    query = db.query(ProductTrafficDetail).filter(
        ProductTrafficDetail.product_id == product_id,
        ProductTrafficDetail.date >= (start_date or "2000-01-01"),
        ProductTrafficDetail.date <= (end_date or "2099-12-31"),
    )
    rows = query.all()
    
    if not rows:
        return ResponseModel(data={"error": "未找到商品流量数据", "product_id": product_id})
    
    product = db.query(Product).filter(Product.product_id == product_id).first()
    plan = db.query(MonthlyPlanning).filter(
        MonthlyPlanning.product_id == product_id
    ).order_by(MonthlyPlanning.plan_month.desc()).first()
    
    total_visitors = sum(r.visitors or 0 for r in rows)
    total_payment = sum(r.payment_amount or 0 for r in rows)
    total_ad_spend = sum(r.ad_spend or 0 for r in rows)
    total_search_visitors = sum(r.search_visitors or 0 for r in rows)
    total_recommend_visitors = sum(r.recommend_visitors or 0 for r in rows)
    avg_conversion = sum(r.conversion_rate or 0 for r in rows) / len(rows) if rows else 0
    
    avg_ad_roi = sum(r.ad_roi or 0 for r in rows) / len(rows) if rows else 0
    avg_keyword_roi = sum(r.keyword_ad_roi or 0 for r in rows) / len(rows) if rows else 0
    avg_audience_roi = sum(r.audience_ad_roi or 0 for r in rows) / len(rows) if rows else 0
    avg_scene_roi = sum(r.scene_ad_roi or 0 for r in rows) / len(rows) if rows else 0
    avg_full_site_roi = sum(r.full_site_ad_roi or 0 for r in rows) / len(rows) if rows else 0
    
    avg_cart_rate = sum(r.cart_rate or 0 for r in rows) / len(rows) if rows else 0
    avg_fav_rate = sum(r.fav_rate or 0 for r in rows) / len(rows) if rows else 0
    avg_bounce_rate = sum(r.bounce_rate or 0 for r in rows) / len(rows) if rows else 0
    avg_stay = sum(r.avg_stay_duration or 0 for r in rows) / len(rows) if rows else 0
    
    all_issues = []
    all_suggestions = []
    
    i, s = diagnose_traffic(total_visitors, sum(r.page_views or 0 for r in rows), avg_bounce_rate, avg_stay)
    all_issues.extend(i); all_suggestions.extend(s)
    
    i, s = diagnose_conversion(avg_conversion, avg_conversion, 
                               (plan.daily_conversion_target / 100) if plan and plan.daily_conversion_target else None)
    all_issues.extend(i); all_suggestions.extend(s)
    
    i, s = diagnose_traffic_sources(total_search_visitors, total_recommend_visitors, total_visitors)
    all_issues.extend(i); all_suggestions.extend(s)
    
    ad_ratio = (total_ad_spend / total_payment * 100) if total_payment > 0 else 0
    i, s = diagnose_ad_efficiency(total_ad_spend, avg_ad_roi, avg_keyword_roi, avg_audience_roi, avg_scene_roi, avg_full_site_roi, ad_ratio / 100)
    all_issues.extend(i); all_suggestions.extend(s)
    
    i, s = diagnose_inventory_and_cart(avg_cart_rate, avg_fav_rate, avg_conversion)
    all_issues.extend(i); all_suggestions.extend(s)
    
    target_achievement = (total_payment / plan.gsv_target * 100) if plan and plan.gsv_target else 100
    i, s = diagnose_vs_target(total_payment, plan.gsv_target if plan else None, 
                              avg_ad_roi, plan.ad_roi if plan else None)
    all_issues.extend(i); all_suggestions.extend(s)
    
    score = calculate_health_score(
        visitors=total_visitors,
        conversion=avg_conversion,
        ad_roi=avg_ad_roi,
        achievement=target_achievement,
        cart_rate=avg_cart_rate,
        search_ratio=(total_search_visitors / total_visitors) if total_visitors > 0 else 0,
    )
    
    report_label = generate_report_label(score)
    
    return ResponseModel(data={
        "product_id": product_id,
        "product_name": product.title if product else "",
        "health_score": score,
        "report_label": report_label,
        "summary": {
            "total_visitors": total_visitors,
            "total_payment": round(total_payment, 2),
            "total_ad_spend": round(total_ad_spend, 2),
            "avg_conversion": round(avg_conversion * 100, 2),
            "avg_ad_roi": round(avg_ad_roi, 2),
            "target_achievement": round(target_achievement, 1),
            "days_analyzed": len(rows),
        },
        "issues": all_issues,
        "suggestions": all_suggestions,
        "detail": {
            "traffic": {
                "total_visitors": total_visitors,
                "search_visitors": total_search_visitors,
                "recommend_visitors": total_recommend_visitors,
                "search_ratio": round(total_search_visitors / max(total_visitors, 1) * 100, 1),
                "recommend_ratio": round(total_recommend_visitors / max(total_visitors, 1) * 100, 1),
            },
            "conversion": {
                "avg_rate": round(avg_conversion * 100, 2),
                "avg_cart_rate": round(avg_cart_rate * 100, 2),
                "avg_fav_rate": round(avg_fav_rate * 100, 2),
            },
            "ads": {
                "total_spend": round(total_ad_spend, 2),
                "avg_roi": round(avg_ad_roi, 2),
                "ad_ratio": round(ad_ratio, 1),
                "keyword_roi": round(avg_keyword_roi, 2),
                "audience_roi": round(avg_audience_roi, 2),
                "scene_roi": round(avg_scene_roi, 2),
                "full_site_roi": round(avg_full_site_roi, 2),
            },
            "target": {
                "achievement": round(target_achievement, 1),
                "gsv_target": plan.gsv_target if plan else None,
                "actual": round(total_payment, 2),
            },
        },
    })


@router.get("/all", response_model=ResponseModel)
def get_all_products_diagnosis(
    start_date: Optional[str] = Query(None, description="开始日期"),
    end_date: Optional[str] = Query(None, description="结束日期"),
    limit: int = Query(50, description="返回数量"),
    sort_by: str = Query("score", description="排序字段: score/payment/visitors/roi"),
    db: Session = Depends(get_db)
):
    """获取所有商品诊断排名"""
    products = db.query(
        ProductTrafficDetail.product_id,
        func.count().label('days'),
        func.sum(ProductTrafficDetail.visitors).label('visitors'),
        func.sum(ProductTrafficDetail.payment_amount).label('payment'),
        func.sum(ProductTrafficDetail.ad_spend).label('ad_spend'),
        func.avg(ProductTrafficDetail.conversion_rate).label('conversion'),
        func.avg(ProductTrafficDetail.ad_roi).label('ad_roi'),
        func.avg(ProductTrafficDetail.cart_rate).label('cart_rate'),
        func.sum(ProductTrafficDetail.search_visitors).label('search_visitors'),
    ).filter(
        ProductTrafficDetail.date >= (start_date or "2000-01-01"),
        ProductTrafficDetail.date <= (end_date or "2099-12-31"),
    ).group_by(
        ProductTrafficDetail.product_id
    ).all()
    
    results = []
    for p in products:
        target_achievement = 100
        plan = db.query(MonthlyPlanning).filter(
            MonthlyPlanning.product_id == p.product_id
        ).order_by(MonthlyPlanning.plan_month.desc()).first()
        if plan and plan.gsv_target and plan.gsv_target > 0:
            target_achievement = p.payment / plan.gsv_target * 100
        
        search_ratio = p.search_visitors / max(p.visitors, 1)
        score = calculate_health_score(
            visitors=p.visitors or 0,
            conversion=p.conversion or 0,
            ad_roi=p.ad_roi or 0,
            achievement=target_achievement,
            cart_rate=p.cart_rate or 0,
            search_ratio=search_ratio,
        )
        
        product = db.query(Product).filter(Product.product_id == p.product_id).first()
        
        results.append({
            "product_id": p.product_id,
            "product_name": product.title if product else "",
            "health_score": score,
            "report_label": generate_report_label(score),
            "visitors": p.visitors or 0,
            "payment": round(p.payment or 0, 2),
            "ad_spend": round(p.ad_spend or 0, 2),
            "ad_roi": round(p.ad_roi or 0, 2),
            "conversion": round((p.conversion or 0) * 100, 2),
            "target_achievement": round(target_achievement, 1),
        })
    
    sort_map = {
        "score": lambda x: x["health_score"],
        "payment": lambda x: x["payment"],
        "visitors": lambda x: x["visitors"],
        "roi": lambda x: x["ad_roi"],
    }
    results.sort(key=sort_map.get(sort_by, sort_map["score"]), reverse=True)
    
    return ResponseModel(data={
        "products": results[:limit],
        "total": len(results),
        "avg_score": round(sum(r["health_score"] for r in results) / max(len(results), 1), 1),
    })
