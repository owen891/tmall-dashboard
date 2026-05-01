from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, and_, or_
from typing import Optional, List
from collections import Counter
from app.core.database import get_db
from app.models import Review
from app.schemas.common import ResponseModel

router = APIRouter(prefix="/reviews", tags=["评价分析"])


def extract_keywords(text_list: List[str], top_n: int = 20) -> List[str]:
    """提取关键词（简化版，不依赖jieba）"""
    stopwords = set([
        '的', '了', '是', '在', '我', '有', '和', '就', '不', '人', '都', '一', '一个',
        '上', '也', '很', '到', '说', '要', '去', '你', '会', '着', '没有', '看', '好',
        '自己', '这', '个', '吗', '啊', '吧', '呢', '哦', '嗯', '哈', '呀', '哪', '那个',
        '这个', '什么', '怎么', '为什么', '可以', '没有', '还是', '但是', '所以', '因为',
        '如果', '虽然', '然后', '而且', '或者', '以及', '已经', '比较', '非常', '特别',
        '真的', '确实', '感觉', '觉得', '应该', '可能', '大概', '应该', '一样', '一直'
    ])
    
    words = []
    for text in text_list:
        if not text:
            continue
        text = text.replace(' ', '').replace('\n', '')
        i = 0
        while i < len(text):
            if i + 2 < len(text):
                words.append(text[i:i+2])
            i += 1
    
    word_counts = Counter(words)
    for sw in stopwords:
        del word_counts[sw]
    
    return [word for word, count in word_counts.most_common(top_n) if len(word) >= 2]


def analyze_sentiment(text: str) -> str:
    """简单情感分析"""
    positive_words = ['好', '棒', '优', '喜欢', '满意', '赞', '值', '推荐', '漂亮', '舒服', '不错', '超', '非常']
    negative_words = ['差', '坏', '烂', '失望', '后悔', '糟', '坑', '假', '骗', '垃圾', '烂', '难用', '退货']
    
    text_lower = text.lower()
    pos_count = sum(1 for w in positive_words if w in text)
    neg_count = sum(1 for w in negative_words if w in text)
    
    if pos_count > neg_count:
        return 'positive'
    elif neg_count > pos_count:
        return 'negative'
    else:
        return 'neutral'


@router.get("/summary", response_model=ResponseModel)
def get_review_summary(
    dimension: Optional[str] = Query(None, description="时间维度"),
    period: Optional[str] = Query(None, description="指定周期"),
    db: Session = Depends(get_db)
):
    """获取评价汇总数据"""
    
    query = db.query(Review)
    
    if period:
        query = query.filter(Review.review_date.startswith(period))
    
    reviews = query.all()
    
    if not reviews:
        return ResponseModel(data={
            "total_reviews": 0,
            "avg_rating": 0,
            "positive_rate": 0,
            "positive_count": 0,
            "negative_count": 0,
            "neutral_count": 0,
            "keywords": []
        })
    
    total = len(reviews)
    ratings = [r.rating for r in reviews if r.rating]
    avg_rating = sum(ratings) / len(ratings) if ratings else 0
    
    sentiments = [analyze_sentiment(r.content) if r.content else 'neutral' for r in reviews]
    positive_count = sentiments.count('positive')
    negative_count = sentiments.count('negative')
    neutral_count = sentiments.count('neutral')
    positive_rate = (positive_count / total * 100) if total > 0 else 0
    
    content_list = [r.content for r in reviews if r.content]
    keywords = extract_keywords(content_list)
    
    return ResponseModel(data={
        "total_reviews": total,
        "avg_rating": round(avg_rating, 2),
        "positive_rate": round(positive_rate, 1),
        "positive_count": positive_count,
        "negative_count": negative_count,
        "neutral_count": neutral_count,
        "keywords": keywords[:20],
        "period": period,
        "dimension": dimension
    })


@router.get("/sentiment-distribution", response_model=ResponseModel)
def get_sentiment_distribution(
    dimension: Optional[str] = Query(None, description="时间维度"),
    period: Optional[str] = Query(None, description="指定周期"),
    db: Session = Depends(get_db)
):
    """获取情感分布"""
    
    query = db.query(Review)
    
    if period:
        query = query.filter(Review.review_date.startswith(period))
    
    reviews = query.all()
    
    if not reviews:
        return ResponseModel(data={
            "positive": {"count": 0, "percent": 0},
            "negative": {"count": 0, "percent": 0},
            "neutral": {"count": 0, "percent": 0}
        })
    
    total = len(reviews)
    sentiments = [analyze_sentiment(r.content) if r.content else 'neutral' for r in reviews]
    
    positive_count = sentiments.count('positive')
    negative_count = sentiments.count('negative')
    neutral_count = sentiments.count('neutral')
    
    return ResponseModel(data={
        "positive": {
            "count": positive_count,
            "percent": round(positive_count / total * 100, 1)
        },
        "negative": {
            "count": negative_count,
            "percent": round(negative_count / total * 100, 1)
        },
        "neutral": {
            "count": neutral_count,
            "percent": round(neutral_count / total * 100, 1)
        }
    })


@router.get("/rating-distribution", response_model=ResponseModel)
def get_rating_distribution(
    dimension: Optional[str] = Query(None, description="时间维度"),
    period: Optional[str] = Query(None, description="指定周期"),
    db: Session = Depends(get_db)
):
    """获取评分分布"""
    
    query = db.query(Review).filter(Review.rating.isnot(None))
    
    if period:
        query = query.filter(Review.review_date.startswith(period))
    
    reviews = query.all()
    
    distribution = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    for r in reviews:
        if r.rating in distribution:
            distribution[r.rating] += 1
    
    result = [
        {"rating": rating, "count": count}
        for rating, count in sorted(distribution.items(), reverse=True)
    ]
    
    return ResponseModel(data=result)


@router.get("/list", response_model=ResponseModel)
def get_review_list(
    sentiment: Optional[str] = Query(None, description="情感筛选: positive/negative/neutral"),
    rating: Optional[int] = Query(None, description="评分筛选"),
    product_id: Optional[str] = Query(None, description="商品ID"),
    period: Optional[str] = Query(None, description="指定周期"),
    page: int = Query(1, description="页码"),
    page_size: int = Query(20, description="每页数量"),
    db: Session = Depends(get_db)
):
    """获取评价列表"""
    
    query = db.query(Review)
    
    if sentiment:
        sentiment_filter = []
        for r in db.query(Review).all():
            if r.content:
                analyzed = analyze_sentiment(r.content)
                if analyzed == sentiment:
                    sentiment_filter.append(r.id)
        query = query.filter(Review.id.in_(sentiment_filter))
    
    if rating:
        query = query.filter(Review.rating == rating)
    
    if product_id:
        query = query.filter(Review.product_id == product_id)
    
    if period:
        query = query.filter(Review.review_date.startswith(period))
    
    total = query.count()
    reviews = query.order_by(desc(Review.review_date)).offset((page - 1) * page_size).limit(page_size).all()
    
    review_list = []
    for r in reviews:
        sentiment = analyze_sentiment(r.content) if r.content else 'neutral'
        review_list.append({
            "id": r.id,
            "review_date": r.review_date,
            "product_id": r.product_id,
            "product_name": r.product_name or r.product_id,
            "rating": r.rating,
            "sentiment": sentiment,
            "content": r.content,
            "reviewer_type": r.reviewer_type or "普通买家"
        })
    
    return ResponseModel(data={
        "reviews": review_list,
        "total": total,
        "page": page,
        "page_size": page_size
    })


@router.get("/keywords", response_model=ResponseModel)
def get_review_keywords(
    dimension: Optional[str] = Query(None, description="时间维度"),
    period: Optional[str] = Query(None, description="指定周期"),
    sentiment: Optional[str] = Query(None, description="情感筛选"),
    top_n: int = Query(30, description="返回数量"),
    db: Session = Depends(get_db)
):
    """获取评价关键词"""
    
    query = db.query(Review.content).filter(Review.content.isnot(None))
    
    if period:
        reviews_in_period = db.query(Review).filter(Review.review_date.startswith(period)).all()
        review_ids = [r.id for r in reviews_in_period]
        query = db.query(Review.content).filter(Review.id.in_(review_ids), Review.content.isnot(None))
    
    contents = [c[0] for c in query.all() if c[0]]
    
    if sentiment:
        filtered = []
        for c in contents:
            analyzed = analyze_sentiment(c)
            if analyzed == sentiment:
                filtered.append(c)
        contents = filtered
    
    keywords = extract_keywords(contents, top_n)
    
    return ResponseModel(data={
        "keywords": keywords,
        "period": period,
        "sentiment": sentiment
    })


@router.get("/dimensions", response_model=ResponseModel)
def get_review_dimensions(
    dimension: Optional[str] = Query(None, description="时间维度"),
    period: Optional[str] = Query(None, description="指定周期"),
    db: Session = Depends(get_db)
):
    """获取评价维度分析（好评维度、差评维度、典型场景）"""
    
    query = db.query(Review)
    
    if period:
        query = query.filter(Review.review_date.startswith(period))
    
    reviews = query.all()
    
    positive_dims = {
        "质量": 0, "价格": 0, "服务": 0, "物流": 0, "外观": 0,
        "口感": 0, "功效": 0, "包装": 0, "性价比": 0, "推荐": 0
    }
    
    negative_dims = {
        "质量": 0, "价格": 0, "服务": 0, "物流": 0, "外观": 0,
        "口感": 0, "功效": 0, "包装": 0, "描述不符": 0, "退货": 0
    }
    
    scenes = []
    
    for r in reviews:
        content = r.content or ""
        sentiment = analyze_sentiment(content)
        
        if sentiment == 'positive':
            for dim in positive_dims:
                if dim in content:
                    positive_dims[dim] += 1
        elif sentiment == 'negative':
            for dim in negative_dims:
                if dim in content:
                    negative_dims[dim] += 1
        
        if '回购' in content or '再次' in content:
            scenes.append('回购意愿')
        if '送人' in content or '礼物' in content:
            scenes.append('送礼场景')
        if '囤货' in content or '囤' in content:
            scenes.append('囤货场景')
    
    scene_counts = Counter(scenes)
    top_scenes = [{"scene": s, "count": c} for s, c in scene_counts.most_common(5)]
    
    return ResponseModel(data={
        "positive_dims": [{"dimension": k, "count": v} for k, v in sorted(positive_dims.items(), key=lambda x: x[1], reverse=True) if v > 0],
        "negative_dims": [{"dimension": k, "count": v} for k, v in sorted(negative_dims.items(), key=lambda x: x[1], reverse=True) if v > 0],
        "scenes": top_scenes,
        "period": period
    })


@router.get("/product/{product_id}", response_model=ResponseModel)
def get_product_reviews(
    product_id: str,
    page: int = Query(1, description="页码"),
    page_size: int = Query(20, description="每页数量"),
    db: Session = Depends(get_db)
):
    """获取指定商品的评论"""
    
    query = db.query(Review).filter(Review.product_id == product_id)
    
    total = query.count()
    reviews = query.order_by(desc(Review.review_date)).offset((page - 1) * page_size).limit(page_size).all()
    
    review_list = []
    for r in reviews:
        sentiment = analyze_sentiment(r.content) if r.content else 'neutral'
        review_list.append({
            "id": r.id,
            "review_date": r.review_date,
            "product_name": r.product_name or r.product_id,
            "rating": r.rating,
            "sentiment": sentiment,
            "content": r.content,
            "reviewer_type": r.reviewer_type or "普通买家"
        })
    
    return ResponseModel(data={
        "product_id": product_id,
        "reviews": review_list,
        "total": total,
        "page": page,
        "page_size": page_size
    })
