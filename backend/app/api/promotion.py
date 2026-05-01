from fastapi import APIRouter, Query
from datetime import datetime, timedelta
from typing import Optional
import random

router = APIRouter(prefix="/api/promotion", tags=["推广分析"])

@router.get("/plans")
async def get_promotion_plans(
    channel: Optional[str] = Query(None, description="渠道筛选"),
    status: Optional[str] = Query(None, description="状态筛选"),
    start_date: Optional[str] = Query(None, description="开始日期"),
    end_date: Optional[str] = Query(None, description="结束日期")
):
    plans = [
        {
            "id": 1,
            "name": "夏季新品推广计划",
            "channel": "直通车",
            "status": "运行中",
            "planId": "P202405001",
            "type": "标准计划",
            "cost": 12580,
            "revenue": 38650,
            "roi": 3.08,
            "avgCpc": 2.85,
            "clicks": 4414,
            "impressions": 89520,
            "conversionRate": 0.085,
            "createTime": "2024-05-01"
        },
        {
            "id": 2,
            "name": "爆款打造计划",
            "channel": "超级推荐",
            "status": "运行中",
            "planId": "P202405002",
            "type": "智能计划",
            "cost": 8920,
            "revenue": 25680,
            "roi": 2.88,
            "avgCpc": 1.95,
            "clicks": 4574,
            "impressions": 125680,
            "conversionRate": 0.072,
            "createTime": "2024-05-05"
        },
        {
            "id": 3,
            "name": "品牌推广计划",
            "channel": "钻展",
            "status": "暂停",
            "planId": "P202405003",
            "type": "品牌计划",
            "cost": 15600,
            "revenue": 42500,
            "roi": 2.72,
            "avgCpc": 4.20,
            "clicks": 3714,
            "impressions": 45800,
            "conversionRate": 0.091,
            "createTime": "2024-04-28"
        },
        {
            "id": 4,
            "name": "清仓促销计划",
            "channel": "直通车",
            "status": "运行中",
            "planId": "P202405004",
            "type": "标准计划",
            "cost": 4580,
            "revenue": 11200,
            "roi": 2.44,
            "avgCpc": 1.65,
            "clicks": 2776,
            "impressions": 58450,
            "conversionRate": 0.068,
            "createTime": "2024-05-10"
        },
        {
            "id": 5,
            "name": "新品测款计划",
            "channel": "超级推荐",
            "status": "运行中",
            "planId": "P202405005",
            "type": "智能计划",
            "cost": 6780,
            "revenue": 18950,
            "roi": 2.80,
            "avgCpc": 2.15,
            "clicks": 3153,
            "impressions": 78920,
            "conversionRate": 0.075,
            "createTime": "2024-05-12"
        }
    ]
    
    if channel and channel != "all":
        channel_map = {"taobao": "直通车", "tmall": "超级推荐", "jd": "钻展"}
        plans = [p for p in plans if p["channel"] == channel_map.get(channel, "")]
    
    if status and status != "all":
        plans = [p for p in plans if p["status"] == status]
    
    return {"plans": plans, "total": len(plans)}

@router.get("/search-efficiency")
async def get_search_efficiency(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None)
):
    return {
        "summary": {
            "totalSearches": 125680,
            "clickRate": 4.25,
            "conversionRate": 3.82,
            "growthRate": 12.5
        },
        "trend": [
            {"date": "5/1", "searches": 18500, "clicks": 820, "conversions": 32},
            {"date": "5/2", "searches": 21200, "clicks": 950, "conversions": 38},
            {"date": "5/3", "searches": 19800, "clicks": 880, "conversions": 35},
            {"date": "5/4", "searches": 23500, "clicks": 1050, "conversions": 42},
            {"date": "5/5", "searches": 22800, "clicks": 990, "conversions": 39},
            {"date": "5/6", "searches": 25600, "clicks": 1150, "conversions": 45},
            {"date": "5/7", "searches": 24200, "clicks": 1080, "conversions": 42}
        ],
        "keywordRanking": [
            {"rank": 1, "keyword": "夏季连衣裙", "searches": 25680, "clickRate": 5.82, "conversionRate": 4.25, "trend": 5.2},
            {"rank": 2, "keyword": "纯棉T恤", "searches": 18950, "clickRate": 4.56, "conversionRate": 3.88, "trend": 3.1},
            {"rank": 3, "keyword": "休闲短裤男", "searches": 15680, "clickRate": 3.95, "conversionRate": 3.25, "trend": -1.2},
            {"rank": 4, "keyword": "韩版女装", "searches": 12350, "clickRate": 4.12, "conversionRate": 3.65, "trend": 2.8},
            {"rank": 5, "keyword": "修身显瘦", "searches": 9850, "clickRate": 3.58, "conversionRate": 3.12, "trend": 1.5}
        ]
    }

@router.get("/products")
async def get_promotion_products():
    return {
        "products": [
            {"id": 1, "name": "夏季新款连衣裙", "sku": "SKU001"},
            {"id": 2, "name": "纯棉T恤短袖", "sku": "SKU002"},
            {"id": 3, "name": "休闲短裤男", "sku": "SKU003"}
        ]
    }
