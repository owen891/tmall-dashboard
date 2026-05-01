from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import func
from app.core.database import get_db
from app.models.product import MarketAnalysis, MarketKeywordOpportunity, Product

router = APIRouter(prefix="/market", tags=["市场分析"])


class KeywordTrend(BaseModel):
    keyword: str
    search_volume: int
    competition: float
    click_rate: float
    conversion_rate: float
    trend: str


class MarketOpportunity(BaseModel):
    id: int
    keyword: str
    category: str
    search_volume: int
    competition: float
    opportunity_score: float
    potential: str
    recommendation: str


class CategoryAnalysis(BaseModel):
    category: str
    product_count: int
    total_gmv: float
    avg_price: float
    avg_roi: float
    market_share: float


class CompetitorAnalysis(BaseModel):
    product_id: int
    product_name: str
    gmv: float
    market_share: float
    rank: int
    price_range: str


class MarketOverview(BaseModel):
    total_products: int
    total_gmv: float
    avg_price: float
    avg_roi: float
    top_category: str
    market_trend: str


class KeywordData(BaseModel):
    id: int
    keyword: str
    category: str
    search_volume: int
    competition: float
    click_rate: float
    conversion_rate: float
    avg_price: float
    trend_30d: float
    created_at: str


@router.get("/overview", response_model=dict)
def get_market_overview():
    db = next(get_db())
    try:
        products = db.query(Product).all()

        total_products = len(products)
        total_gmv = sum(p.gmv for p in products if p.gmv)
        prices = [p.price for p in products if p.price]
        avg_price = sum(prices) / len(prices) if prices else 0
        rois = [p.total_roi for p in products if p.total_roi]
        avg_roi = sum(rois) / len(rois) if rois else 0

        category_map = {}
        for p in products:
            cat = getattr(p, "category", None) or "其他"
            if cat not in category_map:
                category_map[cat] = {"count": 0, "gmv": 0}
            category_map[cat]["count"] += 1
            category_map[cat]["gmv"] += p.gmv or 0

        top_category = max(category_map.items(), key=lambda x: x[1]["gmv"])[0] if category_map else "其他"

        recent_products = [p for p in products if p.gmv and p.gmv > 0]
        if len(recent_products) >= 2:
            market_trend = "增长" if recent_products[0].gmv > recent_products[-1].gmv else "下降"
        else:
            market_trend = "稳定"

        overview = MarketOverview(
            total_products=total_products,
            total_gmv=round(total_gmv, 2),
            avg_price=round(avg_price, 2),
            avg_roi=round(avg_roi, 2),
            top_category=top_category,
            market_trend=market_trend
        )

        return {"code": 200, "data": overview}

    finally:
        db.close()


@router.get("/keywords", response_model=dict)
def get_keywords(
    category: Optional[str] = None,
    sort_by: str = Query("search_volume", description="排序: search_volume/competition/opportunity"),
    page: int = Query(1),
    page_size: int = Query(50)
):
    db = next(get_db())
    try:
        query = db.query(MarketKeywordOpportunity)

        if category:
            query = query.filter(MarketKeywordOpportunity.category == category)

        if sort_by == "competition":
            query = query.order_by(MarketKeywordOpportunity.competition.asc())
        elif sort_by == "opportunity":
            query = query.order_by(MarketKeywordOpportunity.opportunity_score.desc())
        else:
            query = query.order_by(MarketKeywordOpportunity.search_volume.desc())

        total = query.count()
        offset = (page - 1) * page_size
        keywords = query.offset(offset).limit(page_size).all()

        keyword_list = []
        for kw in keywords:
            keyword_list.append(KeywordData(
                id=kw.id,
                keyword=kw.keyword,
                category=kw.category or "",
                search_volume=kw.search_volume,
                competition=kw.competition,
                click_rate=kw.click_rate,
                conversion_rate=kw.conversion_rate,
                avg_price=kw.avg_price,
                trend_30d=kw.trend_30d,
                created_at=kw.created_at.isoformat() if kw.created_at else ""
            ))

        return {
            "code": 200,
            "data": {
                "keywords": keyword_list,
                "total": total,
                "page": page,
                "page_size": page_size
            }
        }

    finally:
        db.close()


@router.get("/keywords/trends", response_model=dict)
def get_keyword_trends(
    keyword: Optional[str] = None,
    days: int = Query(30, description="天数")
):
    db = next(get_db())
    try:
        query = db.query(MarketKeywordOpportunity)

        if keyword:
            query = query.filter(MarketKeywordOpportunity.keyword.contains(keyword))

        keywords = query.all()

        trends = []
        for kw in keywords:
            trend_direction = "上升" if kw.trend_30d > 0 else ("下降" if kw.trend_30d < 0 else "平稳")
            trends.append(KeywordTrend(
                keyword=kw.keyword,
                search_volume=kw.search_volume,
                competition=kw.competition,
                click_rate=kw.click_rate,
                conversion_rate=kw.conversion_rate,
                trend=trend_direction
            ))

        return {"code": 200, "data": trends}

    finally:
        db.close()


@router.get("/opportunities", response_model=dict)
def get_opportunities(
    min_score: float = Query(0, description="最低机会分数"),
    category: Optional[str] = None,
    limit: int = Query(20)
):
    db = next(get_db())
    try:
        query = db.query(MarketKeywordOpportunity).filter(
            MarketKeywordOpportunity.opportunity_score >= min_score
        )

        if category:
            query = query.filter(MarketKeywordOpportunity.category == category)

        opportunities = query.order_by(MarketKeywordOpportunity.opportunity_score.desc()).limit(limit).all()

        result = []
        for o in opportunities:
            potential = "高" if o.opportunity_score > 80 else ("中" if o.opportunity_score > 50 else "低")

            recommendations = {
                "高": f"关键词'{o.keyword}'市场机会大，建议重点投入",
                "中": f"关键词'{o.keyword}'有一定机会，可考虑测试投放",
                "低": f"关键词'{o.keyword}'竞争激烈，建议观望"
            }

            result.append(MarketOpportunity(
                id=o.id,
                keyword=o.keyword,
                category=o.category or "",
                search_volume=o.search_volume,
                competition=o.competition,
                opportunity_score=o.opportunity_score,
                potential=potential,
                recommendation=recommendations[potential]
            ))

        return {"code": 200, "data": result}

    finally:
        db.close()


@router.get("/categories", response_model=dict)
def get_category_analysis():
    db = next(get_db())
    try:
        products = db.query(Product).all()

        category_map = {}
        for p in products:
            cat = getattr(p, "category", None) or "其他"
            if cat not in category_map:
                category_map[cat] = {"count": 0, "gmv": 0, "prices": [], "rois": []}
            category_map[cat]["count"] += 1
            category_map[cat]["gmv"] += p.gmv or 0
            if p.price:
                category_map[cat]["prices"].append(p.price)
            if p.total_roi:
                category_map[cat]["rois"].append(p.total_roi)

        total_gmv = sum(c["gmv"] for c in category_map.values())

        categories = []
        for cat, data in category_map.items():
            avg_price = sum(data["prices"]) / len(data["prices"]) if data["prices"] else 0
            avg_roi = sum(data["rois"]) / len(data["rois"]) if data["rois"] else 0
            market_share = (data["gmv"] / total_gmv * 100) if total_gmv > 0 else 0

            categories.append(CategoryAnalysis(
                category=cat,
                product_count=data["count"],
                total_gmv=round(data["gmv"], 2),
                avg_price=round(avg_price, 2),
                avg_roi=round(avg_roi, 2),
                market_share=round(market_share, 2)
            ))

        categories.sort(key=lambda x: x.total_gmv, reverse=True)

        return {"code": 200, "data": categories}

    finally:
        db.close()


@router.get("/competitors", response_model=dict)
def get_competitor_analysis(limit: int = Query(20)):
    db = next(get_db())
    try:
        products = db.query(Product).order_by(Product.gmv.desc()).limit(limit).all()

        total_gmv = sum(p.gmv for p in db.query(Product).all() if p.gmv)

        competitors = []
        for i, p in enumerate(products):
            market_share = (p.gmv / total_gmv * 100) if total_gmv > 0 and p.gmv else 0

            if p.price:
                if p.price < 50:
                    price_range = "0-50"
                elif p.price < 100:
                    price_range = "50-100"
                elif p.price < 200:
                    price_range = "100-200"
                elif p.price < 500:
                    price_range = "200-500"
                else:
                    price_range = "500+"
            else:
                price_range = "未知"

            competitors.append(CompetitorAnalysis(
                product_id=p.id,
                product_name=p.name,
                gmv=p.gmv or 0,
                market_share=round(market_share, 2),
                rank=i + 1,
                price_range=price_range
            ))

        return {"code": 200, "data": competitors}

    finally:
        db.close()


@router.post("/keywords", response_model=dict)
def create_keyword(
    keyword: str,
    category: str,
    search_volume: int = 0,
    competition: float = 0,
    click_rate: float = 0,
    conversion_rate: float = 0,
    avg_price: float = 0,
    trend_30d: float = 0
):
    db = next(get_db())
    try:
        opportunity_score = calculate_opportunity_score(search_volume, competition, conversion_rate)

        kw = MarketKeywordOpportunity(
            keyword=keyword,
            category=category,
            search_volume=search_volume,
            competition=competition,
            click_rate=click_rate,
            conversion_rate=conversion_rate,
            avg_price=avg_price,
            trend_30d=trend_30d,
            opportunity_score=opportunity_score
        )
        db.add(kw)
        db.commit()
        db.refresh(kw)

        return {"code": 200, "message": "关键词已添加", "data": {"id": kw.id}}

    finally:
        db.close()


@router.delete("/keywords/{keyword_id}", response_model=dict)
def delete_keyword(keyword_id: int):
    db = next(get_db())
    try:
        kw = db.query(MarketKeywordOpportunity).filter(MarketKeywordOpportunity.id == keyword_id).first()
        if not kw:
            return {"code": 404, "message": "关键词不存在"}

        db.delete(kw)
        db.commit()
        return {"code": 200, "message": "关键词已删除"}

    finally:
        db.close()


@router.get("/trends/sharing", response_model=dict)
def get_market_share_trends():
    db = next(get_db())
    try:
        products = db.query(Product).all()

        total_gmv = sum(p.gmv for p in products if p.gmv)

        category_map = {}
        for p in products:
            cat = getattr(p, "category", None) or "其他"
            if cat not in category_map:
                category_map[cat] = 0
            category_map[cat] += p.gmv or 0

        trends = []
        for cat, gmv in category_map.items():
            share = (gmv / total_gmv * 100) if total_gmv > 0 else 0
            trends.append({
                "category": cat,
                "gmv": round(gmv, 2),
                "share": round(share, 2)
            })

        trends.sort(key=lambda x: x["gmv"], reverse=True)

        return {"code": 200, "data": trends}

    finally:
        db.close()


@router.get("/price-distribution", response_model=dict)
def get_price_distribution():
    db = next(get_db())
    try:
        products = db.query(Product).filter(Product.price.isnot(None)).all()

        ranges = {
            "0-50": {"count": 0, "gmv": 0},
            "50-100": {"count": 0, "gmv": 0},
            "100-200": {"count": 0, "gmv": 0},
            "200-500": {"count": 0, "gmv": 0},
            "500+": {"count": 0, "gmv": 0}
        }

        for p in products:
            price = p.price
            if price < 50:
                ranges["0-50"]["count"] += 1
                ranges["0-50"]["gmv"] += p.gmv or 0
            elif price < 100:
                ranges["50-100"]["count"] += 1
                ranges["50-100"]["gmv"] += p.gmv or 0
            elif price < 200:
                ranges["100-200"]["count"] += 1
                ranges["100-200"]["gmv"] += p.gmv or 0
            elif price < 500:
                ranges["200-500"]["count"] += 1
                ranges["200-500"]["gmv"] += p.gmv or 0
            else:
                ranges["500+"]["count"] += 1
                ranges["500+"]["gmv"] += p.gmv or 0

        distribution = []
        for range_name, data in ranges.items():
            distribution.append({
                "range": range_name,
                "count": data["count"],
                "gmv": round(data["gmv"], 2)
            })

        return {"code": 200, "data": distribution}

    finally:
        db.close()


def calculate_opportunity_score(search_volume: int, competition: float, conversion_rate: float) -> float:
    volume_score = min(search_volume / 10000 * 30, 30)
    competition_score = (1 - competition) * 30 if competition <= 1 else 0
    conversion_score = conversion_rate * 40 if conversion_rate <= 1 else conversion_rate * 40 / 100

    return round(volume_score + competition_score + conversion_score, 2)


@router.post("/analysis", response_model=dict)
def create_market_analysis(
    analysis_type: str,
    product_id: Optional[int] = None,
    category: Optional[str] = None,
    keyword: Optional[str] = None,
    data: Optional[str] = None
):
    db = next(get_db())
    try:
        analysis = MarketAnalysis(
            analysis_type=analysis_type,
            product_id=product_id,
            category=category,
            keyword=keyword,
            data=data
        )
        db.add(analysis)
        db.commit()
        db.refresh(analysis)

        return {"code": 200, "message": "分析记录已创建", "data": {"id": analysis.id}}

    finally:
        db.close()


@router.get("/analysis/history", response_model=dict)
def get_analysis_history(
    analysis_type: Optional[str] = None,
    limit: int = Query(50)
):
    db = next(get_db())
    try:
        query = db.query(MarketAnalysis)

        if analysis_type:
            query = query.filter(MarketAnalysis.analysis_type == analysis_type)

        history = query.order_by(MarketAnalysis.created_at.desc()).limit(limit).all()

        result = []
        for h in history:
            result.append({
                "id": h.id,
                "analysis_type": h.analysis_type,
                "product_id": h.product_id,
                "category": h.category,
                "keyword": h.keyword,
                "data": h.data,
                "created_at": h.created_at.isoformat() if h.created_at else ""
            })

        return {"code": 200, "data": result}

    finally:
        db.close()
