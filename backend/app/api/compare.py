from fastapi import APIRouter, Query
from datetime import datetime, timedelta
from typing import Optional

router = APIRouter(prefix="/api/compare", tags=["周期对比"])

@router.get("/summary")
async def get_compare_summary(
    compare_type: Optional[str] = Query("week"),
    base_date: Optional[str] = Query(None),
    compare_date: Optional[str] = Query(None)
):
    return {
        "base": {
            "gmv": 2856000,
            "orders": 12580,
            "visitors": 156800,
            "conversion": 8.02
        },
        "compare": {
            "gmv": 3189000,
            "orders": 14250,
            "visitors": 175200,
            "conversion": 8.13
        },
        "change": {
            "gmv": 11.66,
            "orders": 13.28,
            "visitors": 11.73,
            "conversion": 1.37
        }
    }

@router.get("/detail")
async def get_compare_detail():
    return {
        "data": [
            {"index": 1, "name": "GMV", "baseValue": "¥2,856,000", "compareValue": "¥3,189,000", "change": 11.66},
            {"index": 2, "name": "订单数", "baseValue": "12,580", "compareValue": "14,250", "change": 13.28},
            {"index": 3, "name": "访客数", "baseValue": "156,800", "compareValue": "175,200", "change": 11.73},
            {"index": 4, "name": "转化率", "baseValue": "8.02%", "compareValue": "8.13%", "change": 1.37},
            {"index": 5, "name": "客单价", "baseValue": "¥227", "compareValue": "¥224", "change": -1.32},
            {"index": 6, "name": "退款率", "baseValue": "2.35%", "compareValue": "2.18%", "change": -7.23},
            {"index": 7, "name": "好评率", "baseValue": "96.8%", "compareValue": "97.2%", "change": 0.41},
            {"index": 8, "name": "广告花费", "baseValue": "¥156,000", "compareValue": "¥178,000", "change": 14.10},
            {"index": 9, "name": "ROI", "baseValue": "3.25", "compareValue": "3.42", "change": 5.23},
            {"index": 10, "name": "库存周转", "baseValue": "15.6天", "compareValue": "14.2天", "change": -9.0}
        ]
    }

@router.get("/trend")
async def get_compare_trend(
    compare_type: Optional[str] = Query("week"),
    metric: Optional[str] = Query("gmv")
):
    labels = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"] if compare_type == "day" else \
             ["第1周", "第2周", "第3周", "第4周"] if compare_type == "week" else \
             ["1月", "2月", "3月"]
    
    base_data = {
        "gmv": [220, 280, 250, 310, 290, 350, 320],
        "orders": [150, 180, 165, 200, 185, 220, 205],
        "visitors": [1800, 2200, 2000, 2400, 2250, 2600, 2450],
        "conversion": [7.2, 7.8, 7.5, 8.2, 8.0, 8.5, 8.3]
    }
    
    compare_data = {
        "gmv": [245, 310, 280, 345, 320, 385, 355],
        "orders": [168, 200, 182, 225, 208, 248, 230],
        "visitors": [2000, 2450, 2220, 2680, 2500, 2900, 2720],
        "conversion": [7.5, 8.2, 7.8, 8.6, 8.4, 8.8, 8.5]
    }
    
    return {
        "labels": labels,
        "base": base_data.get(metric, base_data["gmv"]),
        "compare": compare_data.get(metric, compare_data["gmv"])
    }
