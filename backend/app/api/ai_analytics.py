from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime
from app.core.database import get_db
from app.schemas.common import ResponseModel

router = APIRouter(prefix="/ai-analytics", tags=["AI智能分析"])


class ReportRequest(BaseModel):
    report_type: str = "summary"
    period: Optional[str] = None
    dimension: str = "weekly"
    focus_areas: Optional[List[str]] = None


class QueryRequest(BaseModel):
    query: str
    context: Optional[dict] = None


# 临时存储报告历史
REPORT_HISTORY = []
REPORT_ID_COUNTER = 1


@router.post("/report", response_model=ResponseModel)
def generate_report(
    request: ReportRequest,
    db: Session = Depends(get_db)
):
    """生成AI分析报告"""
    global REPORT_ID_COUNTER

    report_id = REPORT_ID_COUNTER
    REPORT_ID_COUNTER += 1

    report = {
        "id": report_id,
        "report_type": request.report_type,
        "period": request.period,
        "dimension": request.dimension,
        "focus_areas": request.focus_areas or [],
        "status": "completed",
        "created_at": datetime.now().isoformat(),
        "summary": "基于当前数据的智能分析总结...",
        "insights": [
            {
                "title": "销售趋势分析",
                "content": "近期销售呈现稳定增长态势，建议继续保持当前运营策略。",
                "confidence": 0.85
            },
            {
                "title": "转化率优化建议",
                "content": "详情页跳出率略高，建议优化商品主图和卖点描述。",
                "confidence": 0.78
            }
        ],
        "recommendations": [
            "加大高转化商品的推广力度",
            "优化低转化商品的详情页内容",
            "关注竞品动态，及时调整定价策略"
        ]
    }

    REPORT_HISTORY.append(report)

    return ResponseModel(data={
        "report_id": report_id,
        "status": "completed",
        "summary": report["summary"],
        "insights": report["insights"],
        "recommendations": report["recommendations"]
    })


@router.post("/query", response_model=ResponseModel)
def execute_query(
    request: QueryRequest,
    db: Session = Depends(get_db)
):
    """执行AI数据查询"""
    query = request.query.lower()

    response = {
        "query": request.query,
        "answer": "根据您的查询，我为您分析如下：",
        "data": {},
        "suggestions": []
    }

    if "销售" in query or "gmv" in query or "支付" in query:
        response["answer"] = "近期整体销售表现良好，周环比增长约12%。TOP3品类贡献了60%的销售额。"
        response["data"] = {
            "total_gmv": 1258000,
            "growth": 12.5,
            "top_category": "家居用品"
        }
    elif "转化" in query:
        response["answer"] = "当前整体转化率为3.2%，较上月提升0.3个百分点。详情页优化效果显著。"
        response["data"] = {
            "conversion_rate": 3.2,
            "change": 0.3
        }
    elif "广告" in query or "投放" in query:
        response["answer"] = "广告ROI目前为2.8，建议在关键词广告上增加预算，当前ROI为3.5。"
        response["data"] = {
            "overall_roi": 2.8,
            "keyword_roi": 3.5
        }
    else:
        response["answer"] = "我已收到您的问题，正在为您分析相关数据。请稍候或尝试更具体的查询。"
        response["suggestions"] = [
            "最近销售情况如何？",
            "转化率有什么变化？",
            "广告投放效果如何？"
        ]

    return ResponseModel(data=response)


@router.get("/reports", response_model=ResponseModel)
def get_report_history(
    limit: int = Query(20, description="返回数量"),
    db: Session = Depends(get_db)
):
    """获取报告历史"""
    reports = sorted(REPORT_HISTORY, key=lambda x: x["id"], reverse=True)[:limit]
    return ResponseModel(data={
        "reports": reports,
        "total": len(REPORT_HISTORY)
    })


@router.get("/reports/{report_id}", response_model=ResponseModel)
def get_report_detail(
    report_id: int,
    db: Session = Depends(get_db)
):
    """获取报告详情"""
    report = next((r for r in REPORT_HISTORY if r["id"] == report_id), None)
    if not report:
        return ResponseModel(code=404, message="报告不存在")

    return ResponseModel(data=report)
