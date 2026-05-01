from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import func
from app.core.database import get_db
from app.models.product import Review, ReviewSummary, Product

router = APIRouter(prefix="/reviews", tags=["评价分析"])


class ReviewDetail(BaseModel):
    id: int
    product_id: int
    product_name: str
    review_date: str
    rating: float
    sentiment: str
    content: str
    reviewer_type: str
    keywords: Optional[str]
    is_anonymous: bool


class ReviewSummaryStat(BaseModel):
    product_id: int
    product_name: str
    total_reviews: int
    avg_rating: float
    positive_count: int
    negative_count: int
    neutral_count: int
    positive_rate: float
    keywords: List[str]


class SentimentTrend(BaseModel):
    date: str
    positive: int
    negative: int
    neutral: int
    avg_rating: float


class ReviewDimensionStat(BaseModel):
    dimension: str
    positive: int
    negative: int
    neutral: int
    total: int


class ReviewAnalysisResponse(BaseModel):
    summary: ReviewSummaryStat
    sentiment_trends: List[SentimentTrend]
    dimension_stats: List[ReviewDimensionStat]


@router.get("/summary", response_model=dict)
def get_review_summary(
    product_id: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
    db = next(get_db())
    try:
        query = db.query(Review)

        if product_id:
            query = query.filter(Review.product_id == product_id)
        if start_date:
            query = query.filter(Review.review_date >= start_date)
        if end_date:
            query = query.filter(Review.review_date <= end_date)

        reviews = query.all()

        total = len(reviews)
        if total == 0:
            return {"code": 200, "data": None}

        avg_rating = sum(r.rating for r in reviews) / total
        positive = sum(1 for r in reviews if r.sentiment == "positive")
        negative = sum(1 for r in reviews if r.sentiment == "negative")
        neutral = sum(1 for r in reviews if r.sentiment == "neutral")

        all_keywords = []
        for r in reviews:
            if r.keywords:
                all_keywords.extend(r.keywords.split(","))

        keyword_freq = {}
        for kw in all_keywords:
            kw = kw.strip()
            if kw:
                keyword_freq[kw] = keyword_freq.get(kw, 0) + 1

        top_keywords = sorted(keyword_freq.items(), key=lambda x: x[1], reverse=True)[:10]
        top_keywords = [kw for kw, _ in top_keywords]

        if product_id:
            product = db.query(Product).filter(Product.id == product_id).first()
            product_name = product.name if product else "未知商品"
        else:
            product_name = "全部商品"

        summary = ReviewSummaryStat(
            product_id=product_id or 0,
            product_name=product_name,
            total_reviews=total,
            avg_rating=round(avg_rating, 2),
            positive_count=positive,
            negative_count=negative,
            neutral_count=neutral,
            positive_rate=round(positive / total * 100, 2) if total > 0 else 0,
            keywords=top_keywords
        )

        return {"code": 200, "data": summary}

    finally:
        db.close()


@router.get("/trends", response_model=dict)
def get_review_trends(
    product_id: Optional[int] = None,
    dimension: str = Query("daily", description="时间维度: daily/weekly/monthly"),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
    db = next(get_db())
    try:
        query = db.query(Review)

        if product_id:
            query = query.filter(Review.product_id == product_id)
        if start_date:
            query = query.filter(Review.review_date >= start_date)
        if end_date:
            query = query.filter(Review.review_date <= end_date)

        reviews = query.order_by(Review.review_date).all()

        if dimension == "monthly":
            grouped = {}
            for r in reviews:
                month = r.review_date[:7] if r.review_date else ""
                if month not in grouped:
                    grouped[month] = {"positive": 0, "negative": 0, "neutral": 0, "total_rating": 0, "count": 0}
                grouped[month]["count"] += 1
                grouped[month]["total_rating"] += r.rating
                if r.sentiment == "positive":
                    grouped[month]["positive"] += 1
                elif r.sentiment == "negative":
                    grouped[month]["negative"] += 1
                else:
                    grouped[month]["neutral"] += 1

            trends = []
            for date in sorted(grouped.keys()):
                data = grouped[date]
                trends.append(SentimentTrend(
                    date=date,
                    positive=data["positive"],
                    negative=data["negative"],
                    neutral=data["neutral"],
                    avg_rating=round(data["total_rating"] / data["count"], 2) if data["count"] > 0 else 0
                ))
        else:
            grouped = {}
            for r in reviews:
                date = r.review_date[:10] if r.review_date else ""
                if date not in grouped:
                    grouped[date] = {"positive": 0, "negative": 0, "neutral": 0, "total_rating": 0, "count": 0}
                grouped[date]["count"] += 1
                grouped[date]["total_rating"] += r.rating
                if r.sentiment == "positive":
                    grouped[date]["positive"] += 1
                elif r.sentiment == "negative":
                    grouped[date]["negative"] += 1
                else:
                    grouped[date]["neutral"] += 1

            trends = []
            for date in sorted(grouped.keys()):
                data = grouped[date]
                trends.append(SentimentTrend(
                    date=date,
                    positive=data["positive"],
                    negative=data["negative"],
                    neutral=data["neutral"],
                    avg_rating=round(data["total_rating"] / data["count"], 2) if data["count"] > 0 else 0
                ))

        return {"code": 200, "data": trends}

    finally:
        db.close()


@router.get("/dimensions", response_model=dict)
def get_review_dimensions(
    product_id: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
    db = next(get_db())
    try:
        query = db.query(Review)

        if product_id:
            query = query.filter(Review.product_id == product_id)
        if start_date:
            query = query.filter(Review.review_date >= start_date)
        if end_date:
            query = query.filter(Review.review_date <= end_date)

        reviews = query.all()

        dimension_map = {
            "quality": ["质量", "品质", "材质", "做工", "面料"],
            "service": ["服务", "态度", "客服", "回复", "售后"],
            "logistics": ["物流", "快递", "发货", "配送", "速度"],
            "price": ["价格", "性价比", "便宜", "划算", "实惠"],
            "appearance": ["外观", "颜值", "包装", "设计", "好看"]
        }

        stats = {dim: {"positive": 0, "negative": 0, "neutral": 0, "total": 0} for dim in dimension_map.keys()}

        for r in reviews:
            content = r.content or ""
            for dim, keywords in dimension_map.items():
                if any(kw in content for kw in keywords):
                    stats[dim]["total"] += 1
                    if r.sentiment == "positive":
                        stats[dim]["positive"] += 1
                    elif r.sentiment == "negative":
                        stats[dim]["negative"] += 1
                    else:
                        stats[dim]["neutral"] += 1

        result = []
        for dim, data in stats.items():
            if data["total"] > 0:
                result.append(ReviewDimensionStat(
                    dimension=dim,
                    positive=data["positive"],
                    negative=data["negative"],
                    neutral=data["neutral"],
                    total=data["total"]
                ))

        return {"code": 200, "data": result}

    finally:
        db.close()


@router.get("/list", response_model=dict)
def get_review_list(
    product_id: Optional[int] = None,
    sentiment: Optional[str] = Query(None, description="情感: positive/negative/neutral"),
    rating: Optional[int] = Query(None, description="评分 1-5"),
    keyword: Optional[str] = Query(None, description="关键词搜索"),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    page: int = Query(1, description="页码"),
    page_size: int = Query(20, description="每页数量")
):
    db = next(get_db())
    try:
        query = db.query(Review)

        if product_id:
            query = query.filter(Review.product_id == product_id)
        if sentiment:
            query = query.filter(Review.sentiment == sentiment)
        if rating:
            query = query.filter(Review.rating == rating)
        if keyword:
            query = query.filter(Review.content.contains(keyword))
        if start_date:
            query = query.filter(Review.review_date >= start_date)
        if end_date:
            query = query.filter(Review.review_date <= end_date)

        total = query.count()
        offset = (page - 1) * page_size
        reviews = query.order_by(Review.review_date.desc()).offset(offset).limit(page_size).all()

        review_list = []
        for r in reviews:
            review_list.append(ReviewDetail(
                id=r.id,
                product_id=r.product_id,
                product_name=r.product_name or "",
                review_date=r.review_date or "",
                rating=r.rating,
                sentiment=r.sentiment,
                content=r.content,
                reviewer_type=r.reviewer_type or "normal",
                keywords=r.keywords,
                is_anonymous=r.is_anonymous
            ))

        return {
            "code": 200,
            "data": {
                "reviews": review_list,
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": (total + page_size - 1) // page_size
            }
        }

    finally:
        db.close()


@router.get("/product/{product_id}", response_model=dict)
def get_product_review_analysis(product_id: int):
    db = next(get_db())
    try:
        reviews = db.query(Review).filter(Review.product_id == product_id).all()

        total = len(reviews)
        if total == 0:
            return {"code": 200, "data": None}

        avg_rating = sum(r.rating for r in reviews) / total
        positive = sum(1 for r in reviews if r.sentiment == "positive")
        negative = sum(1 for r in reviews if r.sentiment == "negative")
        neutral = sum(1 for r in reviews if r.sentiment == "neutral")

        all_keywords = []
        for r in reviews:
            if r.keywords:
                all_keywords.extend(r.keywords.split(","))

        keyword_freq = {}
        for kw in all_keywords:
            kw = kw.strip()
            if kw:
                keyword_freq[kw] = keyword_freq.get(kw, 0) + 1

        top_keywords = sorted(keyword_freq.items(), key=lambda x: x[1], reverse=True)[:10]
        top_keywords = [kw for kw, _ in top_keywords]

        product = db.query(Product).filter(Product.id == product_id).first()

        summary = ReviewSummaryStat(
            product_id=product_id,
            product_name=product.name if product else "未知商品",
            total_reviews=total,
            avg_rating=round(avg_rating, 2),
            positive_count=positive,
            negative_count=negative,
            neutral_count=neutral,
            positive_rate=round(positive / total * 100, 2),
            keywords=top_keywords
        )

        return {"code": 200, "data": summary}

    finally:
        db.close()


@router.get("/sentiment-distribution", response_model=dict)
def get_sentiment_distribution(
    product_id: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
    db = next(get_db())
    try:
        query = db.query(Review)

        if product_id:
            query = query.filter(Review.product_id == product_id)
        if start_date:
            query = query.filter(Review.review_date >= start_date)
        if end_date:
            query = query.filter(Review.review_date <= end_date)

        reviews = query.all()
        total = len(reviews)

        positive = sum(1 for r in reviews if r.sentiment == "positive")
        negative = sum(1 for r in reviews if r.sentiment == "negative")
        neutral = sum(1 for r in reviews if r.sentiment == "neutral")

        distribution = {
            "positive": {
                "count": positive,
                "percentage": round(positive / total * 100, 2) if total > 0 else 0
            },
            "negative": {
                "count": negative,
                "percentage": round(negative / total * 100, 2) if total > 0 else 0
            },
            "neutral": {
                "count": neutral,
                "percentage": round(neutral / total * 100, 2) if total > 0 else 0
            }
        }

        return {"code": 200, "data": distribution}

    finally:
        db.close()


@router.get("/rating-distribution", response_model=dict)
def get_rating_distribution(
    product_id: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
    db = next(get_db())
    try:
        query = db.query(Review)

        if product_id:
            query = query.filter(Review.product_id == product_id)
        if start_date:
            query = query.filter(Review.review_date >= start_date)
        if end_date:
            query = query.filter(Review.review_date <= end_date)

        reviews = query.all()

        distribution = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        for r in reviews:
            if r.rating in distribution:
                distribution[r.rating] += 1

        total = len(reviews)
        result = []
        for rating in [5, 4, 3, 2, 1]:
            result.append({
                "rating": rating,
                "count": distribution[rating],
                "percentage": round(distribution[rating] / total * 100, 2) if total > 0 else 0
            })

        return {"code": 200, "data": result}

    finally:
        db.close()


@router.post("/", response_model=dict)
def create_review(
    product_id: int,
    product_name: str,
    review_date: str,
    rating: float,
    sentiment: str,
    content: str,
    reviewer_type: str = "normal",
    keywords: Optional[str] = None,
    is_anonymous: bool = False
):
    db = next(get_db())
    try:
        review = Review(
            product_id=product_id,
            product_name=product_name,
            review_date=review_date,
            rating=rating,
            sentiment=sentiment,
            content=content,
            reviewer_type=reviewer_type,
            keywords=keywords,
            is_anonymous=is_anonymous
        )
        db.add(review)
        db.commit()
        db.refresh(review)

        return {"code": 200, "message": "评价已添加", "data": {"id": review.id}}

    finally:
        db.close()


@router.delete("/{review_id}", response_model=dict)
def delete_review(review_id: int):
    db = next(get_db())
    try:
        review = db.query(Review).filter(Review.id == review_id).first()
        if not review:
            return {"code": 404, "message": "评价不存在"}

        db.delete(review)
        db.commit()
        return {"code": 200, "message": "评价已删除"}

    finally:
        db.close()
