"""
报告自动生成 API
自动生成日报/周报，支持推送到钉钉/企微
"""
from fastapi import APIRouter, Depends, Query, Body
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import Optional, List
from datetime import datetime, timedelta
from app.core.database import get_db
from app.core.utils import get_data_model, get_prev_period, get_latest_period, safe_float, calculate_change
from app.models import DailyData, WeeklyData, MonthlyData, Product, OperationAction, ShopTarget
from app.schemas.common import ResponseModel

router = APIRouter(prefix="/reports", tags=["报告生成"])


@router.get("/daily", response_model=ResponseModel)
def generate_daily_report(
    date: Optional[str] = Query(None, description="日期 YYYY-MM-DD"),
    db: Session = Depends(get_db)
):
    """生成日报"""
    
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")
    
    Model = DailyData
    date_col = 'date'
    
    data = db.query(
        func.sum(Model.payment_amount).label('gmv'),
        func.sum(Model.refund_amount).label('refund'),
        func.sum(Model.ipv).label('visitors'),
        func.avg(Model.payment_conversion).label('conversion'),
        func.sum(Model.ad_spend).label('ad_spend'),
        func.count(Model.product_id.distinct()).label('product_count'),
    ).filter(getattr(Model, date_col) == date).first()
    
    gmv = safe_float(data.gmv) if data else 0
    refund = safe_float(data.refund) if data else 0
    visitors = safe_float(data.visitors) if data else 0
    conversion = safe_float(data.conversion) if data else 0
    ad_spend = safe_float(data.ad_spend) if data else 0
    product_count = data.product_count if data else 0
    
    net_sales = gmv - refund
    roi = (net_sales / ad_spend * 100) if ad_spend > 0 else 0
    
    prev_date = (datetime.strptime(date, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
    
    prev_data = db.query(
        func.sum(Model.payment_amount).label('gmv'),
        func.sum(Model.ipv).label('visitors'),
    ).filter(getattr(Model, date_col) == prev_date).first()
    
    prev_gmv = safe_float(prev_data.gmv) if prev_data else 0
    prev_visitors = safe_float(prev_data.visitors) if prev_data else 0
    
    gmv_change = calculate_change(gmv, prev_gmv)
    visitors_change = calculate_change(visitors, prev_visitors)
    
    top_products = db.query(
        Model.product_id,
        Product.title,
        func.sum(Model.payment_amount).label('gmv'),
    ).join(Product, Model.product_id == Product.product_id).filter(
        getattr(Model, date_col) == date
    ).group_by(Model.product_id, Product.title).order_by(desc('gmv')).limit(5).all()
    
    operations = db.query(OperationAction).filter(
        OperationAction.action_date == date
    ).all()
    
    report = {
        "report_type": "daily",
        "date": date,
        "generated_at": datetime.now().isoformat(),
        "summary": {
            "gmv": {"value": round(gmv, 2), "change": gmv_change},
            "net_sales": round(net_sales, 2),
            "visitors": {"value": int(visitors), "change": visitors_change},
            "conversion": round(conversion * 100, 2),
            "ad_spend": round(ad_spend, 2),
            "roi": round(roi, 2),
            "refund_rate": round(refund / gmv * 100, 2) if gmv > 0 else 0,
        },
        "highlights": [],
        "top_products": [
            {"rank": i + 1, "product_id": p.product_id, "title": p.title, "gmv": round(safe_float(p.gmv), 2)}
            for i, p in enumerate(top_products)
        ],
        "operations": [
            {"type": op.action_type, "detail": op.action_detail, "product_id": op.product_id}
            for op in operations
        ],
        "alerts": [],
        "suggestions": []
    }
    
    if gmv_change.get("status") == "down":
        report["highlights"].append(f"GMV环比下降 {abs(gmv_change.get('percent', 0))}%")
    
    if visitors > 0 and conversion < 0.02:
        report["alerts"].append("转化率偏低，建议检查详情页质量")
    
    if ad_spend > 0 and roi < 2:
        report["alerts"].append(f"ROI仅为 {roi:.1f}，广告效率需要优化")
    
    return ResponseModel(data=report)


@router.get("/weekly", response_model=ResponseModel)
def generate_weekly_report(
    week_start: Optional[str] = Query(None, description="周开始日期"),
    db: Session = Depends(get_db)
):
    """生成周报"""
    
    Model = WeeklyData
    date_col = 'week_start'
    
    if not week_start:
        period = get_latest_period(Model, date_col, db)
        if period:
            week_start = str(period)
    
    if not week_start:
        return ResponseModel(data={"error": "无数据"})
    
    data = db.query(
        func.sum(Model.payment_amount).label('gmv'),
        func.sum(Model.refund_amount).label('refund'),
        func.sum(Model.ipv).label('visitors'),
        func.avg(Model.payment_conversion).label('conversion'),
        func.sum(Model.ad_spend).label('ad_spend'),
        func.count(Model.product_id.distinct()).label('product_count'),
    ).filter(getattr(Model, date_col) == week_start).first()
    
    gmv = safe_float(data.gmv) if data else 0
    refund = safe_float(data.refund) if data else 0
    visitors = safe_float(data.visitors) if data else 0
    conversion = safe_float(data.conversion) if data else 0
    ad_spend = safe_float(data.ad_spend) if data else 0
    
    net_sales = gmv - refund
    roi = (net_sales / ad_spend * 100) if ad_spend > 0 else 0
    aov = gmv / visitors if visitors > 0 else 0
    
    targets = db.query(ShopTarget).filter(
        ShopTarget.year == datetime.now().year
    ).all()
    
    target_gmv = sum(safe_float(t.gmv_target) for t in targets) / 52 if targets else 0
    target_progress = (gmv / target_gmv * 100) if target_gmv > 0 else 0
    
    prev_week = get_prev_period(week_start, 'weekly')
    
    prev_data = db.query(
        func.sum(Model.payment_amount).label('gmv'),
        func.sum(Model.ipv).label('visitors'),
    ).filter(getattr(Model, date_col) == prev_week).first()
    
    prev_gmv = safe_float(prev_data.gmv) if prev_data else 0
    prev_visitors = safe_float(prev_data.visitors) if prev_data else 0
    
    gmv_change = calculate_change(gmv, prev_gmv)
    
    top_products = db.query(
        Model.product_id,
        Product.title,
        Product.tier,
        func.sum(Model.payment_amount).label('gmv'),
        func.sum(Model.ipv).label('visitors'),
    ).join(Product, Model.product_id == Product.product_id).filter(
        getattr(Model, date_col) == week_start
    ).group_by(Model.product_id, Product.title, Product.tier).order_by(desc('gmv')).limit(10).all()
    
    operations = db.query(OperationAction).filter(
        OperationAction.action_date >= week_start,
        OperationAction.action_date <= datetime.strptime(week_start, "%Y-%m-%d").date() + timedelta(days=6)
    ).all()
    
    report = {
        "report_type": "weekly",
        "week_start": week_start,
        "generated_at": datetime.now().isoformat(),
        "summary": {
            "gmv": {"value": round(gmv, 2), "change": gmv_change},
            "net_sales": round(net_sales, 2),
            "visitors": int(visitors),
            "conversion": round(conversion * 100, 2),
            "ad_spend": round(ad_spend, 2),
            "roi": round(roi, 2),
            "aov": round(aov, 2),
            "refund_rate": round(refund / gmv * 100, 2) if gmv > 0 else 0,
        },
        "target_progress": {
            "target": round(target_gmv, 2),
            "actual": round(gmv, 2),
            "progress": round(target_progress, 1),
            "status": "on_track" if target_progress >= 90 else "behind"
        },
        "top_products": [
            {
                "rank": i + 1,
                "product_id": p.product_id,
                "title": p.title,
                "tier": p.tier,
                "gmv": round(safe_float(p.gmv), 2),
                "visitors": int(safe_float(p.visitors))
            }
            for i, p in enumerate(top_products)
        ],
        "operations_summary": {
            "total": len(operations),
            "by_type": {}
        },
        "highlights": [],
        "alerts": [],
        "next_week_focus": []
    }
    
    for op in operations:
        action_type = op.action_type or "other"
        report["operations_summary"]["by_type"][action_type] = report["operations_summary"]["by_type"].get(action_type, 0) + 1
    
    if gmv_change.get("percent", 0) > 10:
        report["highlights"].append(f"GMV环比增长 {gmv_change['percent']}%，表现优异")
    elif gmv_change.get("percent", 0) < -10:
        report["alerts"].append(f"GMV环比下降 {abs(gmv_change['percent'])}%，需要关注")
    
    if target_progress < 80:
        report["alerts"].append(f"目标完成率仅 {target_progress:.0f}%，需要加速")
    
    report["next_week_focus"].extend([
        "关注低ROI计划的优化",
        "检查高退款率商品",
        "准备下周活动"
    ])
    
    return ResponseModel(data=report)


@router.get("/monthly", response_model=ResponseModel)
def generate_monthly_report(
    month: Optional[str] = Query(None, description="月份 YYYY-MM"),
    db: Session = Depends(get_db)
):
    """生成月报"""
    
    Model = MonthlyData
    date_col = 'month'
    
    if not month:
        period = get_latest_period(Model, date_col, db)
        if period:
            month = str(period)
    
    if not month:
        return ResponseModel(data={"error": "无数据"})
    
    data = db.query(
        func.sum(Model.payment_amount).label('gmv'),
        func.sum(Model.refund_amount).label('refund'),
        func.sum(Model.visitors).label('visitors'),
        func.avg(Model.payment_conversion).label('conversion'),
        func.sum(Model.ad_spend).label('ad_spend'),
    ).filter(getattr(Model, date_col) == month).first()
    
    gmv = safe_float(data.gmv) if data else 0
    refund = safe_float(data.refund) if data else 0
    visitors = safe_float(data.visitors) if data else 0
    conversion = safe_float(data.conversion) if data else 0
    ad_spend = safe_float(data.ad_spend) if data else 0
    
    net_sales = gmv - refund
    roi = (net_sales / ad_spend * 100) if ad_spend > 0 else 0
    
    targets = db.query(ShopTarget).filter(
        ShopTarget.year == int(month.split('-')[0])
    ).all()
    
    target_gmv = sum(safe_float(t.gmv_target) for t in targets) / 12 if targets else 0
    target_progress = (gmv / target_gmv * 100) if target_gmv > 0 else 0
    
    prev_month = get_prev_period(month, 'monthly')
    
    prev_data = db.query(
        func.sum(Model.payment_amount).label('gmv'),
    ).filter(getattr(Model, date_col) == prev_month).first()
    
    prev_gmv = safe_float(prev_data.gmv) if prev_data else 0
    yoy_change = calculate_change(gmv, prev_gmv)
    
    report = {
        "report_type": "monthly",
        "month": month,
        "generated_at": datetime.now().isoformat(),
        "summary": {
            "gmv": round(gmv, 2),
            "net_sales": round(net_sales, 2),
            "visitors": int(visitors),
            "conversion": round(conversion * 100, 2),
            "ad_spend": round(ad_spend, 2),
            "roi": round(roi, 2),
            "refund_rate": round(refund / gmv * 100, 2) if gmv > 0 else 0,
        },
        "target_progress": {
            "target": round(target_gmv, 2),
            "actual": round(gmv, 2),
            "progress": round(target_progress, 1),
        },
        "yoy_comparison": {
            "prev_month": prev_month,
            "prev_gmv": round(prev_gmv, 2),
            "change": yoy_change
        },
        "highlights": [],
        "alerts": [],
        "recommendations": []
    }
    
    if target_progress >= 100:
        report["highlights"].append(f"目标达成率 {target_progress:.0f}%，超额完成")
    elif target_progress < 80:
        report["alerts"].append(f"目标完成率仅 {target_progress:.0f}%")
    
    report["recommendations"].extend([
        "复盘本月高ROI策略，下月复制",
        "优化低效推广计划",
        "关注退款率高的商品"
    ])
    
    return ResponseModel(data=report)


@router.post("/export", response_model=ResponseModel)
def export_report(
    report_type: str = Body("daily", description="报告类型: daily/weekly/monthly"),
    format: str = Body("markdown", description="导出格式: markdown/json"),
    date: Optional[str] = Body(None, description="日期"),
    db: Session = Depends(get_db)
):
    """导出报告"""
    
    if report_type == "daily":
        res = generate_daily_report(date, db)
    elif report_type == "weekly":
        res = generate_weekly_report(date, db)
    else:
        res = generate_monthly_report(date, db)
    
    report_data = res.data
    
    if format == "markdown":
        md_content = generate_markdown_report(report_data, report_type)
        return ResponseModel(data={
            "format": "markdown",
            "content": md_content
        })
    
    return ResponseModel(data={
        "format": "json",
        "content": report_data
    })


def generate_markdown_report(data: dict, report_type: str) -> str:
    """生成 Markdown 格式报告"""
    
    lines = []
    
    type_labels = {"daily": "日报", "weekly": "周报", "monthly": "月报"}
    
    lines.append(f"# 运营{type_labels.get(report_type, '报告')}")
    lines.append(f"\n**生成时间**: {data.get('generated_at', '')}")
    lines.append("")
    
    if "summary" in data:
        lines.append("## 核心指标\n")
        summary = data["summary"]
        lines.append(f"- GMV: ¥{summary.get('gmv', {}).get('value', 0):,.0f}" if isinstance(summary.get('gmv'), dict) else f"- GMV: ¥{summary.get('gmv', 0):,.0f}")
        lines.append(f"- 净销售额: ¥{summary.get('net_sales', 0):,.0f}")
        lines.append(f"- 访客数: {summary.get('visitors', 0):,}")
        lines.append(f"- 转化率: {summary.get('conversion', 0)}%")
        lines.append(f"- 广告消耗: ¥{summary.get('ad_spend', 0):,.0f}")
        lines.append(f"- ROI: {summary.get('roi', 0)}")
        lines.append("")
    
    if "top_products" in data and data["top_products"]:
        lines.append("## TOP 商品\n")
        for p in data["top_products"][:5]:
            lines.append(f"{p.get('rank', '')}. {p.get('title', '')} - ¥{p.get('gmv', 0):,.0f}")
        lines.append("")
    
    if "alerts" in data and data["alerts"]:
        lines.append("## 预警提示\n")
        for alert in data["alerts"]:
            lines.append(f"- ⚠️ {alert}")
        lines.append("")
    
    if "recommendations" in data and data["recommendations"]:
        lines.append("## 下期建议\n")
        for rec in data["recommendations"]:
            lines.append(f"- {rec}")
        lines.append("")
    
    return "\n".join(lines)
