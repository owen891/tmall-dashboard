"""Unified data-source registry for the project data collection center.

The registry deliberately separates capability readiness from collector runtime
status. A source can therefore be visible in the same operational view before
its connector exists (for example, 快麦 ERP or product-page reviews).
"""

from copy import deepcopy
from datetime import datetime


INTEGRATION_SOURCES = (
    # Tmall dashboard core sources
    {
        "key": "bi_daily", "domain": "tmall-dashboard", "name": "BI 商品总览",
        "content": "商品日度：访客、支付、加购、收藏、转化、新老客、复购、预售、搜索点击、关联销售",
        "frequency": "每日", "dependency": "Chrome 调试 + BI 登录",
        "readiness": "connected", "collector_key": "bi_daily",
    },
    {
        "key": "sycm_flow", "domain": "tmall-dashboard", "name": "生意参谋-店铺流量",
        "content": "三级渠道流量来源（第一次访问口径）", "frequency": "每日",
        "dependency": "Chrome 调试 + 生意参谋登录", "readiness": "connected", "collector_key": "sycm_flow",
    },
    {
        "key": "sycm_item_flow", "domain": "tmall-dashboard", "name": "生意参谋-单品流量",
        "content": "前 200 商品四级流量来源", "frequency": "每日",
        "dependency": "Chrome 调试 + 生意参谋登录", "readiness": "connected", "collector_key": "sycm_item_flow",
    },
    {
        "key": "sycm_trade", "domain": "tmall-dashboard", "name": "生意参谋-交易概览",
        "content": "店铺支付金额、买家、新老客", "frequency": "每日",
        "dependency": "Chrome 调试 + 生意参谋登录", "readiness": "planned",
        "blocker": "尚未登记独立交易概览采集器，当前可由店铺日度事实补充",
    },
    {
        "key": "sycm_market", "domain": "tmall-dashboard", "name": "生意参谋-市场排行",
        "content": "商品排行、搜索排行", "frequency": "每日",
        "dependency": "Chrome 调试 + 生意参谋登录", "readiness": "connected", "collector_key": "sycm_market",
    },
    {
        "key": "sycm_rival", "domain": "tmall-dashboard", "name": "生意参谋-竞店竞品",
        "content": "竞店分析、竞品对比", "frequency": "每日",
        "dependency": "Chrome 调试 + 生意参谋登录", "readiness": "manual",
        "blocker": "当前以页面分析能力为主，尚无独立日度采集表",
    },
    {
        "key": "wanxiangtai", "domain": "tmall-dashboard", "name": "万相台推广",
        "content": "渠道花费、点击、转化、成交、ROI", "frequency": "每日",
        "dependency": "Chrome 调试 + 万相台登录", "readiness": "connected", "collector_key": "wanxiangtai",
    },
    # Advertising creative assets
    {
        "key": "ad_creative_report", "domain": "ad-ctr-dashboard", "name": "万相台创意报表",
        "content": "广告创意素材点击率、消耗、转化", "frequency": "按需",
        "dependency": "CSV 导入 / 万相台后台", "readiness": "manual",
        "blocker": "待确认报表字段与素材 ID 的稳定映射",
    },
    {
        "key": "ad_creative_image", "domain": "ad-ctr-dashboard", "name": "素材高清图",
        "content": "广告创意素材图片下载", "frequency": "按需",
        "dependency": "素材 URL 爬取", "readiness": "planned",
        "blocker": "待建设素材 URL 归档和失效重试",
    },
    # Inventory and replenishment
    {
        "key": "inventory_eye", "domain": "inventory", "name": "库存慧眼",
        "content": "快麦 ERP 库存数量、库存周转、滞销品", "frequency": "每日",
        "dependency": "快麦 ERP 接口", "readiness": "blocked",
        "blocker": "快麦 ERP 库存接口尚未接入",
    },
    {
        "key": "replenishment_advisor", "domain": "inventory", "name": "补货顾问",
        "content": "实时库存 + SKU 销量（7 天/30 天加权）", "frequency": "每日",
        "dependency": "快麦 ERP + BI 数据", "readiness": "blocked",
        "blocker": "依赖快麦 ERP 库存和 SKU 级销量数据",
    },
    {
        "key": "sku_combination", "domain": "inventory", "name": "SKU 组合",
        "content": "SKU 颜色销售占比 + 历史组合数据", "frequency": "按需",
        "dependency": "BI + 飞书 API", "readiness": "manual",
        "blocker": "当前需要按需运行组合生成流程",
    },
    # Product and review analysis
    {
        "key": "taobao_reviews", "domain": "product-analysis", "name": "淘宝/天猫商品评价",
        "content": "好评、差评、质量问题、卖点", "frequency": "按需",
        "dependency": "商品 ID 列表 + 淘宝/天猫商品页", "readiness": "manual",
        "blocker": "评价采集尚未自动化",
    },
    {
        "key": "taobao_product_detail", "domain": "product-analysis", "name": "淘宝/天猫商品详情",
        "content": "标题、价格、SKU、图片、属性", "frequency": "按需",
        "dependency": "商品 ID 列表 + 淘宝/天猫商品页", "readiness": "manual",
        "blocker": "商品页采集连接器待开发",
    },
    # Market, AI shopkeeper and monthly review
    {
        "key": "market_research", "domain": "market", "name": "市场研究",
        "content": "淘宝/天猫/拼多多/抖音市场规模、竞品映射、定价、需求验证",
        "frequency": "按需", "dependency": "手动触发", "readiness": "manual",
    },
    {
        "key": "ai_shopkeeper", "domain": "market", "name": "AI 店长",
        "content": "多平台竞品监控、选品建议、每日数据分析", "frequency": "每日",
        "dependency": "多平台数据源", "readiness": "planned",
        "blocker": "尚未统一多平台数据接入和任务凭据",
    },
    {
        "key": "monthly_review", "domain": "review", "name": "月度复盘",
        "content": "多月累加 SQLite、品类分析、单品成长趋势、利润分析", "frequency": "每月",
        "dependency": "BI 日度数据", "readiness": "connected",
        "blocker": "利润分析仍依赖成本字段完整度",
    },
)


READINESS_LABELS = {
    "connected": "已接入",
    "manual": "人工/按需",
    "planned": "待接入",
    "blocked": "阻塞",
}


def _freshness(latest_date):
    if not latest_date:
        return "unknown", None
    try:
        parsed = datetime.strptime(str(latest_date)[:10], "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return "unknown", None
    age_days = max(0, (datetime.now().date() - parsed).days)
    if age_days == 0:
        return "today", age_days
    if age_days == 1:
        return "yesterday", age_days
    if age_days <= 3:
        return "recent", age_days
    return "stale", age_days


def build_integration_catalog(actual_sources):
    """Merge the static project registry with live collector status records."""
    actual_by_key = {item.get("key"): item for item in actual_sources or []}
    sources = []
    for definition in INTEGRATION_SOURCES:
        item = deepcopy(definition)
        live = actual_by_key.get(item.get("collector_key"))
        item["readiness_label"] = READINESS_LABELS[item["readiness"]]
        if live:
            item["runtime_status"] = live.get("status", "idle")
            item["run_status"] = live.get("run_status")
            item["run_id"] = live.get("run_id")
            item["latest_date"] = live.get("latest_date")
            item["record_count"] = live.get("record_count", 0)
            item["freshness"] = live.get("freshness") or _freshness(live.get("latest_date"))[0]
            item["age_days"] = _freshness(live.get("latest_date"))[1]
            item["last_run"] = live.get("last_run")
            if live.get("status") in {"failed", "partial", "error"}:
                item["operational_issue"] = live.get("last_run_record", {}).get("error_message") if live.get("last_run_record") else "最近一次采集未成功"
        else:
            item["runtime_status"] = "not_connected" if item["readiness"] in {"planned", "blocked"} else "manual"
            item["run_status"] = None
            item["freshness"] = "unknown"
            item["age_days"] = None
            item["latest_date"] = None
            item["record_count"] = None
            item["last_run"] = None
        sources.append(item)
    domains = []
    for source in sources:
        if source["domain"] not in domains:
            domains.append(source["domain"])
    summary = {
        "total": len(sources),
        "connected": sum(1 for item in sources if item["readiness"] == "connected"),
        "manual": sum(1 for item in sources if item["readiness"] == "manual"),
        "planned": sum(1 for item in sources if item["readiness"] == "planned"),
        "blocked": sum(1 for item in sources if item["readiness"] == "blocked"),
        "stale": sum(1 for item in sources if item.get("freshness") in {"recent", "yesterday", "stale"}),
    }
    return {"sources": sources, "domains": domains, "summary": summary, "version": "1"}
