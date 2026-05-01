from datetime import datetime, timedelta
from typing import Optional, List, Dict
from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import func
from app.core.database import get_db
from app.models.product import Product, DailyData, ProductNote

router = APIRouter(prefix="/toolbox", tags=["运营工具箱"])


class ProductAnalysis(BaseModel):
    product_id: int
    product_name: str
    health_score: float
    lifecycle_stage: str
    roi_trend: str
    conversion_trend: str
    refund_risk: str
    recommendations: List[str]


class PriceRecommendation(BaseModel):
    product_id: int
    product_name: str
    current_price: float
    recommended_price: float
    price_range_min: float
    price_range_max: float
    reason: str


class InventoryAlert(BaseModel):
    product_id: int
    product_name: str
    current_stock: int
    daily_sales: float
    days_remaining: float
    urgency: str
    recommendation: str


class SalesForecast(BaseModel):
    product_id: int
    product_name: str
    period: str
    forecast_gmv: float
    forecast_sales: int
    confidence: float
    factors: List[str]


class CompetitorComparison(BaseModel):
    product_id: int
    product_name: str
    your_price: float
    avg_competitor_price: float
    price_diff: float
    your_roi: float
    avg_competitor_roi: float
    recommendation: str


class BulkPricingRule(BaseModel):
    id: int
    name: str
    min_price: float
    max_price: float
    adjustment_type: str
    adjustment_value: float
    enabled: bool


class ToolExecuteRequest(BaseModel):
    tool_name: str
    params: Dict


class ToolExecuteResponse(BaseModel):
    tool_name: str
    result: Dict
    execution_time: float


@router.get("/analysis/product/{product_id}", response_model=dict)
def analyze_product(product_id: int):
    db = next(get_db())
    try:
        product = db.query(Product).filter(Product.id == product_id).first()
        if not product:
            return {"code": 404, "message": "商品不存在"}

        recommendations = []

        gmv = product.gmv or 0
        roi = product.total_roi or 0
        conversion = product.conversion or 0
        refund_rate = getattr(product, "refund_rate", 0) or 0
        visitors = product.visitors or 0

        if roi < 1:
            recommendations.append(f"ROI({roi:.2f})低于1，建议优化广告投放策略或调整出价")
        elif roi > 3:
            recommendations.append(f"ROI({roi:.2f})表现优秀，可考虑适当增加投放")

        if conversion < 2:
            recommendations.append(f"转化率({conversion}%)偏低，建议优化详情页或主图")
        elif conversion > 5:
            recommendations.append(f"转化率({conversion}%)优秀，继续保持")

        if refund_rate > 5:
            recommendations.append(f"退款率({refund_rate}%)偏高，建议关注产品质量")
        elif refund_rate < 2:
            recommendations.append(f"退款率({refund_rate}%)控制良好")

        if visitors > 0:
            potential_gmv = visitors * conversion / 100 * (product.price or 0)
            if gmv < potential_gmv * 0.5:
                recommendations.append("访客转化存在较大提升空间，建议优化客服响应或促销活动")

        daily_data = db.query(DailyData).filter(
            DailyData.product_id == product_id
        ).order_by(DailyData.date.desc()).limit(14).all()

        lifecycle_stage = "新品"
        roi_trend = "稳定"
        conversion_trend = "稳定"
        refund_risk = "低"

        if len(daily_data) >= 7:
            recent_7 = daily_data[:7]
            older_7 = daily_data[7:14] if len(daily_data) >= 14 else []

            if older_7:
                recent_roi = sum(d.gmv / d.ad_spend if d.ad_spend else 0 for d in recent_7) / 7
                older_roi = sum(d.gmv / d.ad_spend if d.ad_spend else 0 for d in older_7) / 7

                if recent_roi > older_roi * 1.1:
                    roi_trend = "上升"
                elif recent_roi < older_roi * 0.9:
                    roi_trend = "下降"

                recent_conv = sum(d.conversion for d in recent_7) / 7
                older_conv = sum(d.conversion for d in older_7) / 7

                if recent_conv > older_conv * 1.1:
                    conversion_trend = "上升"
                elif recent_conv < older_conv * 0.9:
                    conversion_trend = "下降"

            recent_gmv = sum(d.gmv for d in recent_7)
            if recent_gmv < 1000:
                lifecycle_stage = "新品"
            elif recent_gmv < 5000:
                lifecycle_stage = "成长期"
            elif recent_gmv < 20000:
                lifecycle_stage = "稳定期"
            else:
                lifecycle_stage = "成熟期"

        avg_refund = sum(d.refund_rate for d in daily_data) / len(daily_data) if daily_data else 0
        if avg_refund > 5:
            refund_risk = "高"
        elif avg_refund > 3:
            refund_risk = "中"
        else:
            refund_risk = "低"

        health_score = calculate_health_score(product)

        analysis = ProductAnalysis(
            product_id=product_id,
            product_name=product.name,
            health_score=health_score,
            lifecycle_stage=lifecycle_stage,
            roi_trend=roi_trend,
            conversion_trend=conversion_trend,
            refund_risk=refund_risk,
            recommendations=recommendations
        )

        return {"code": 200, "data": analysis}

    finally:
        db.close()


@router.get("/price/recommendation/{product_id}", response_model=dict)
def get_price_recommendation(product_id: int):
    db = next(get_db())
    try:
        product = db.query(Product).filter(Product.id == product_id).first()
        if not product:
            return {"code": 404, "message": "商品不存在"}

        current_price = product.price or 0
        roi = product.total_roi or 0
        conversion = product.conversion or 0
        gmv = product.gmv or 0
        visitors = product.visitors or 0

        price_range_min = current_price * 0.85
        price_range_max = current_price * 1.15
        recommended_price = current_price

        reason_parts = []

        if roi < 1:
            recommended_price = current_price * 0.95
            reason_parts.append("ROI偏低，建议适当降价提升竞争力")
        elif roi > 5:
            recommended_price = current_price * 1.05
            reason_parts.append("ROI表现优秀，可考虑小幅提价")

        if conversion < 2 and current_price > 50:
            recommended_price = min(recommended_price, current_price * 0.9)
            reason_parts.append("转化率偏低，考虑降价促销")

        if visitors > 1000 and conversion > 5:
            recommended_price = current_price * 1.03
            reason_parts.append("访客和转化率都较高，可适当提价")

        if not reason_parts:
            reason_parts.append("当前价格处于合理区间")

        recommendation = PriceRecommendation(
            product_id=product_id,
            product_name=product.name,
            current_price=current_price,
            recommended_price=round(recommended_price, 2),
            price_range_min=round(price_range_min, 2),
            price_range_max=round(price_range_max, 2),
            reason="; ".join(reason_parts)
        )

        return {"code": 200, "data": recommendation}

    finally:
        db.close()


@router.get("/inventory/alerts", response_model=dict)
def get_inventory_alerts(days_threshold: int = Query(7, description="库存预警天数阈值")):
    db = next(get_db())
    try:
        daily_data = db.query(
            DailyData.product_id,
            func.avg(DailyData.sales).label("avg_daily_sales")
        ).group_by(DailyData.product_id).all()

        products = db.query(Product).all()
        product_map = {p.id: p for p in products}

        alerts = []
        for data in daily_data:
            product = product_map.get(data.product_id)
            if not product:
                continue

            stock = getattr(product, "stock", None)
            if stock is None:
                continue

            avg_sales = data.avg_daily_sales or 0
            if avg_sales <= 0:
                continue

            days_remaining = stock / avg_sales
            urgency = "high" if days_remaining < days_threshold else ("medium" if days_remaining < days_threshold * 2 else "low")

            recommendation = ""
            if days_remaining < days_threshold:
                recommendation = f"紧急补货，建议补货量覆盖{days_threshold * 2}天销售"
            elif days_remaining < days_threshold * 2:
                recommendation = "库存偏低，建议近期安排补货"

            alerts.append(InventoryAlert(
                product_id=product.id,
                product_name=product.name,
                current_stock=stock,
                daily_sales=round(avg_sales, 2),
                days_remaining=round(days_remaining, 1),
                urgency=urgency,
                recommendation=recommendation
            ))

        alerts.sort(key=lambda x: x.days_remaining)

        return {"code": 200, "data": alerts}

    finally:
        db.close()


@router.get("/forecast/{product_id}", response_model=dict)
def get_sales_forecast(
    product_id: int,
    period: str = Query("7d", description="预测周期: 7d/14d/30d")
):
    db = next(get_db())
    try:
        product = db.query(Product).filter(Product.id == product_id).first()
        if not product:
            return {"code": 404, "message": "商品不存在"}

        daily_data = db.query(DailyData).filter(
            DailyData.product_id == product_id
        ).order_by(DailyData.date.desc()).limit(30).all()

        if len(daily_data) < 3:
            return {"code": 200, "data": SalesForecast(
                product_id=product_id,
                product_name=product.name,
                period=period,
                forecast_gmv=product.gmv or 0,
                forecast_sales=int(product.sales or 0),
                confidence=0.3,
                factors=["数据不足", "使用当前值作为预测"]
            )}

        avg_gmv = sum(d.gmv for d in daily_data) / len(daily_data)
        avg_sales = sum(d.sales for d in daily_data) / len(daily_data)

        if len(daily_data) >= 7:
            recent_7 = daily_data[:7]
            older = daily_data[7:]
            trend = sum(d.gmv for d in recent_7) / 7 / (sum(d.gmv for d in older) / len(older) if older else 1)
        else:
            trend = 1.0

        period_days = {"7d": 7, "14d": 14, "30d": 30}.get(period, 7)
        forecast_gmv = avg_gmv * period_days * min(trend, 1.2)
        forecast_sales = int(avg_sales * period_days * min(trend, 1.2))

        confidence = min(0.5 + len(daily_data) / 100, 0.95)

        factors = []
        if trend > 1.1:
            factors.append("销售呈上升趋势")
        elif trend < 0.9:
            factors.append("销售呈下降趋势，需关注")

        if len(daily_data) >= 14:
            factors.append(f"基于{len(daily_data)}天历史数据")
        else:
            factors.append("数据较少，预测置信度较低")

        if product.ad_spend and product.ad_spend > 0:
            factors.append("考虑广告投放因素")

        forecast = SalesForecast(
            product_id=product_id,
            product_name=product.name,
            period=period,
            forecast_gmv=round(forecast_gmv, 2),
            forecast_sales=forecast_sales,
            confidence=round(confidence, 2),
            factors=factors
        )

        return {"code": 200, "data": forecast}

    finally:
        db.close()


@router.get("/competitor/compare/{product_id}", response_model=dict)
def compare_with_competitors(product_id: int):
    db = next(get_db())
    try:
        product = db.query(Product).filter(Product.id == product_id).first()
        if not product:
            return {"code": 404, "message": "商品不存在"}

        price = product.price or 0
        roi = product.total_roi or 0

        similar_products = db.query(Product).filter(
            Product.id != product_id,
            Product.price.between(price * 0.7, price * 1.3) if price > 0 else True
        ).limit(10).all()

        if not similar_products:
            return {"code": 200, "data": CompetitorComparison(
                product_id=product_id,
                product_name=product.name,
                your_price=price,
                avg_competitor_price=price,
                price_diff=0,
                your_roi=roi,
                avg_competitor_roi=roi,
                recommendation="缺乏相似商品对比数据"
            )}

        avg_competitor_price = sum(p.price for p in similar_products if p.price) / max(sum(1 for p in similar_products if p.price), 1)
        avg_competitor_roi = sum(p.total_roi for p in similar_products if p.total_roi) / max(sum(1 for p in similar_products if p.total_roi), 1)

        price_diff = ((price - avg_competitor_price) / avg_competitor_price * 100) if avg_competitor_price > 0 else 0

        recommendation = ""
        if price_diff > 20:
            recommendation = "您的价格明显高于竞品，建议考虑降价提升竞争力"
        elif price_diff < -20:
            recommendation = "您的价格明显低于竞品，可考虑适当提价提升利润"
        elif roi > avg_competitor_roi * 1.2:
            recommendation = "您的ROI优于竞品，保持当前策略"
        elif roi < avg_competitor_roi * 0.8:
            recommendation = "您的ROI低于竞品，建议优化广告或调整定价"

        if not recommendation:
            recommendation = "价格和ROI与竞品处于相近水平"

        comparison = CompetitorComparison(
            product_id=product_id,
            product_name=product.name,
            your_price=price,
            avg_competitor_price=round(avg_competitor_price, 2),
            price_diff=round(price_diff, 2),
            your_roi=round(roi, 2),
            avg_competitor_roi=round(avg_competitor_roi, 2),
            recommendation=recommendation
        )

        return {"code": 200, "data": comparison}

    finally:
        db.close()


@router.post("/bulk/pricing", response_model=dict)
def apply_bulk_pricing(
    min_price: float,
    max_price: float,
    adjustment_type: str,
    adjustment_value: float
):
    db = next(get_db())
    try:
        query = db.query(Product)

        if min_price > 0:
            query = query.filter(Product.price >= min_price)
        if max_price > 0:
            query = query.filter(Product.price <= max_price)

        products = query.all()

        updated_count = 0
        for p in products:
            if adjustment_type == "percentage":
                new_price = p.price * (1 + adjustment_value / 100)
            elif adjustment_type == "fixed":
                new_price = p.price + adjustment_value
            else:
                continue

            if new_price > 0:
                p.price = round(new_price, 2)
                updated_count += 1

        db.commit()

        return {"code": 200, "message": f"已更新 {updated_count} 个商品的价格"}

    finally:
        db.close()


@router.get("/tips/daily", response_model=dict)
def get_daily_tips():
    db = next(get_db())
    try:
        products = db.query(Product).all()

        tips = []

        low_roi_products = [p for p in products if (p.total_roi or 0) < 1]
        if low_roi_products:
            tips.append({
                "type": "warning",
                "category": "roi",
                "title": "ROI优化提醒",
                "content": f"有{len(low_roi_products)}个商品ROI低于1，建议优化广告投放"
            })

        high_refund_products = [p for p in products if (getattr(p, 'refund_rate', 0) or 0) > 5]
        if high_refund_products:
            tips.append({
                "type": "warning",
                "category": "refund",
                "title": "退款率预警",
                "content": f"有{len(high_refund_products)}个商品退款率超过5%，建议关注"
            })

        no_sales_products = [p for p in products if not p.sales or p.sales == 0]
        if no_sales_products:
            tips.append({
                "type": "info",
                "category": "sales",
                "title": "零销量商品",
                "content": f"有{len(no_sales_products)}个商品本周无销量，考虑优化或下架"
            })

        top_products = sorted(products, key=lambda x: x.gmv or 0, reverse=True)[:3]
        if top_products:
            tips.append({
                "type": "success",
                "category": "top",
                "title": "爆款商品",
                "content": f"当前GMV前三: {', '.join(p.name for p in top_products)}"
            })

        if not tips:
            tips.append({
                "type": "success",
                "category": "general",
                "title": "运营良好",
                "content": "当前各项指标正常，继续保持"
            })

        return {"code": 200, "data": tips}

    finally:
        db.close()


@router.get("/auto-optimize/{product_id}", response_model=dict)
def get_auto_optimization(product_id: int):
    db = next(get_db())
    try:
        product = db.query(Product).filter(Product.id == product_id).first()
        if not product:
            return {"code": 404, "message": "商品不存在"}

        optimizations = []

        roi = product.total_roi or 0
        if roi < 1:
            optimizations.append({
                "action": "reduce_ad_spend",
                "target": "ad_spend",
                "value": 0.8,
                "reason": "ROI低于1，建议降低广告出价20%"
            })
        elif roi > 3:
            optimizations.append({
                "action": "increase_ad_spend",
                "target": "ad_spend",
                "value": 1.2,
                "reason": "ROI表现优秀，可增加广告投放20%"
            })

        conversion = product.conversion or 0
        if conversion < 2:
            optimizations.append({
                "action": "optimize_listing",
                "target": "conversion",
                "value": 1.5,
                "reason": "转化率偏低，建议优化主图和详情页"
            })

        refund_rate = getattr(product, "refund_rate", 0) or 0
        if refund_rate > 5:
            optimizations.append({
                "action": "improve_quality",
                "target": "refund_rate",
                "value": 0.5,
                "reason": "退款率偏高，建议关注产品质量"
            })

        visitors = product.visitors or 0
        if visitors > 0 and conversion > 3:
            optimizations.append({
                "action": "increase_price",
                "target": "price",
                "value": 1.05,
                "reason": "高转化高流量，可考虑小幅提价"
            })

        return {"code": 200, "data": {
            "product_id": product_id,
            "product_name": product.name,
            "optimizations": optimizations
        }}

    finally:
        db.close()


def calculate_health_score(product: Product) -> float:
    score = 100.0

    roi = product.total_roi or 0
    if roi < 1:
        score -= 30
    elif roi < 2:
        score -= 15
    elif roi > 5:
        score += 10

    conversion = product.conversion or 0
    if conversion < 1:
        score -= 25
    elif conversion < 2:
        score -= 10
    elif conversion > 5:
        score += 10

    refund_rate = getattr(product, "refund_rate", 0) or 0
    if refund_rate > 5:
        score -= 30
    elif refund_rate > 3:
        score -= 15
    elif refund_rate < 2:
        score += 10

    gmv = product.gmv or 0
    if gmv == 0:
        score -= 20
    elif gmv < 1000:
        score -= 10

    visitors = product.visitors or 0
    if visitors == 0:
        score -= 15
    elif visitors < 100:
        score -= 5

    return max(0, min(100, round(score, 1)))
