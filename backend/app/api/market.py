from fastapi import APIRouter, Query
from typing import Optional
from datetime import datetime

router = APIRouter(prefix="/api/market", tags=["市场分析"])

@router.get("/trends")
async def get_market_trends(category: Optional[str] = Query(None)):
    categories = ['女装', '男装', '鞋靴', '箱包', '配饰', '美妆', '母婴', '数码']
    
    if category and category != 'all':
        categories = [category]
    
    return {
        "categories": categories,
        "trends": [
            {
                "category": cat,
                "gmv": 2500000 + hash(cat) % 1000000,
                "growth": round((hash(cat) % 30) - 10, 2),
                "conversion": round(0.03 + (hash(cat) % 7) / 100, 4),
                "compete_index": round(50 + hash(cat) % 50, 1)
            }
            for cat in categories
        ]
    }

@router.get("/price-distribution")
async def get_price_distribution(category: Optional[str] = Query(None)):
    return {
        "distribution": [
            {"range": "0-50", "percentage": 25},
            {"range": "50-100", "percentage": 35},
            {"range": "100-200", "percentage": 25},
            {"range": "200+", "percentage": 15}
        ],
        "recommendation": {
            "low_price": {"strategy": "低价引流", "risk": "高", "profit": "低"},
            "mid_price": {"strategy": "性价比", "risk": "中", "profit": "中"},
            "high_price": {"strategy": "品质路线", "risk": "中", "profit": "高"}
        }
    }

@router.get("/top-brands")
async def get_top_brands(category: Optional[str] = Query(None)):
    return {
        "brands": [
            {"rank": i+1, "name": f"品牌{i+1}", "market_share": round(15 - i*2.5, 2), "growth": round(5 + i*2, 2)}
            for i in range(6)
        ]
    }

@router.get("/competition")
async def get_competition_analysis(category: Optional[str] = Query(None)):
    return {
        "total_merchants": 12580,
        "new_merchants": 1258,
        "avg_conversion": 4.52,
        "hot_keywords": [
            {"keyword": "夏季新款", "search_index": 25680, "competition": "高"},
            {"keyword": "韩版", "search_index": 18950, "competition": "高"},
            {"keyword": "简约", "search_index": 15680, "competition": "中"},
            {"keyword": "复古", "search_index": 12350, "competition": "中"},
            {"keyword": "运动", "search_index": 9850, "competition": "低"}
        ]
    }
