from sqlalchemy import Column, Integer, String, Float, Date, Text, Boolean, DateTime, JSON, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base


class WxtCampaign(Base):
    """万相台投放计划"""
    __tablename__ = "wxt_campaigns"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    campaign_name = Column(String, nullable=False)
    platform = Column(String, default="wxt")
    campaign_type = Column(String, nullable=True)
    status = Column(String, default="active")
    
    start_date = Column(String, nullable=True)
    end_date = Column(String, nullable=True)
    budget = Column(Float, default=0)
    actual_spend = Column(Float, default=0)
    
    target_roi = Column(Float, nullable=True)
    target_cpa = Column(Float, nullable=True)
    target_cpc = Column(Float, nullable=True)
    
    manager = Column(String, nullable=True)
    remark = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class WxtDailyMetrics(Base):
    """万相台每日投放数据"""
    __tablename__ = "wxt_daily_metrics"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    campaign_id = Column(Integer, ForeignKey("wxt_campaigns.id"), index=True, nullable=False)
    date = Column(String, nullable=False, index=True)
    
    impressions = Column(Integer, default=0)
    clicks = Column(Integer, default=0)
    cost = Column(Float, default=0)
    ctr = Column(Float, default=0)
    cpc = Column(Float, default=0)
    cpm = Column(Float, default=0)
    
    direct_gmv = Column(Float, default=0)
    indirect_gmv = Column(Float, default=0)
    total_gmv = Column(Float, default=0)
    direct_orders = Column(Integer, default=0)
    indirect_orders = Column(Integer, default=0)
    total_orders = Column(Integer, default=0)
    roi = Column(Float, default=0)
    
    new_customers = Column(Integer, default=0)
    new_customer_gmv = Column(Float, default=0)
    new_customer_cost = Column(Float, default=0)
    new_customer_cpa = Column(Float, default=0)
    
    cart_adds = Column(Integer, default=0)
    cart_cost = Column(Float, default=0)
    cart_rate = Column(Float, default=0)
    
    imported_at = Column(DateTime, default=func.now())


class DmpCrowd(Base):
    """达摩盘人群包"""
    __tablename__ = "dmp_crowds"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    crowd_name = Column(String, nullable=False)
    crowd_code = Column(String, unique=True, nullable=True)
    crowd_type = Column(String, nullable=True)
    tier = Column(String, default="B")
    scale = Column(Integer, default=0)
    description = Column(Text, nullable=True)
    
    is_active = Column(Boolean, default=True)
    suggested_bid_ratio = Column(Float, default=1.0)
    actual_bid_ratio = Column(Float, default=1.0)
    
    tags = Column(JSON, nullable=True)
    attributes = Column(JSON, nullable=True)
    
    manager = Column(String, nullable=True)
    remark = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class DmpCampaignLink(Base):
    """人群包与投放计划关联"""
    __tablename__ = "dmp_campaign_links"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    crowd_id = Column(Integer, ForeignKey("dmp_crowds.id"), index=True, nullable=False)
    campaign_id = Column(Integer, ForeignKey("wxt_campaigns.id"), index=True, nullable=False)
    bid_ratio = Column(Float, default=1.0)
    status = Column(String, default="active")
    remark = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.now())


class CrowdAssetStats(Base):
    """人群资产ROI统计"""
    __tablename__ = "crowd_asset_stats"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    crowd_id = Column(Integer, ForeignKey("dmp_crowds.id"), index=True, nullable=False)
    period = Column(String, nullable=False)  # 7d/30d/90d
    
    awareness_increase = Column(Integer, default=0)  # A
    interest_increase = Column(Integer, default=0)   # I
    purchase_increase = Column(Integer, default=0)   # P
    loyalty_increase = Column(Integer, default=0)    # L
    
    total_cost = Column(Float, default=0)
    total_gmv = Column(Float, default=0)
    asset_roi = Column(Float, default=0)
    
    water_capacity_score = Column(Float, default=0)  # 蓄水能力评分
    harvest_capacity_score = Column(Float, default=0)  # 收割能力评分
    
    efficiency_matrix = Column(JSON, nullable=True)
    
    created_at = Column(DateTime, default=func.now())


class ABTest(Base):
    """A/B测试实验"""
    __tablename__ = "ab_tests"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    test_name = Column(String, nullable=False)
    test_type = Column(String, nullable=True)  # creative/title/crowd/bid/price
    description = Column(Text, nullable=True)
    
    start_date = Column(String, nullable=False)
    end_date = Column(String, nullable=True)
    status = Column(String, default="draft")  # draft/running/finished
    significance_level = Column(Float, default=0.95)
    
    created_by = Column(String, nullable=True)
    reviewed_by = Column(String, nullable=True)
    conclusion = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class ABTestVariant(Base):
    """A/B测试变体"""
    __tablename__ = "ab_test_variants"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    test_id = Column(Integer, ForeignKey("ab_tests.id"), index=True, nullable=False)
    variant_name = Column(String, nullable=False)  # A/B/C
    is_control = Column(Boolean, default=False)
    
    traffic_ratio = Column(Float, default=0.5)
    
    config = Column(JSON, nullable=True)
    remark = Column(Text, nullable=True)


class ABTestMetrics(Base):
    """A/B测试结果数据"""
    __tablename__ = "ab_test_metrics"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    test_id = Column(Integer, ForeignKey("ab_tests.id"), index=True, nullable=False)
    variant_id = Column(Integer, ForeignKey("ab_test_variants.id"), index=True, nullable=False)
    date = Column(String, nullable=False, index=True)
    
    visitors = Column(Integer, default=0)
    clicks = Column(Integer, default=0)
    ctr = Column(Float, default=0)
    orders = Column(Integer, default=0)
    conversion_rate = Column(Float, default=0)
    gmv = Column(Float, default=0)
    roi = Column(Float, default=0)
    cart_adds = Column(Integer, default=0)
    cart_rate = Column(Float, default=0)
    
    custom_metrics = Column(JSON, nullable=True)


class ABTestAnalysis(Base):
    """A/B测试分析结果"""
    __tablename__ = "ab_test_analysis"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    test_id = Column(Integer, ForeignKey("ab_tests.id"), index=True, nullable=False)
    
    winner_variant = Column(String, nullable=True)
    is_significant = Column(Boolean, default=False)
    confidence_level = Column(Float, default=0)
    uplift_percent = Column(Float, default=0)
    
    analysis_data = Column(JSON, nullable=True)
    recommendations = Column(Text, nullable=True)
    conclusion = Column(Text, nullable=True)
    
    analyzed_at = Column(DateTime, default=func.now())


class SOPTemplate(Base):
    """SOP模板库"""
    __tablename__ = "sop_templates"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    template_name = Column(String, nullable=False)
    template_type = Column(String, nullable=True)  # promotion/launch/optimization/normal
    category = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    content = Column(Text, nullable=True)
    
    use_count = Column(Integer, default=0)
    avg_effectiveness = Column(Float, default=0)
    is_recommended = Column(Boolean, default=False)
    
    tags = Column(JSON, nullable=True)
    steps = Column(JSON, nullable=True)
    attachments = Column(JSON, nullable=True)
    
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class CampaignProject(Base):
    """营销活动项目"""
    __tablename__ = "campaign_projects"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    project_name = Column(String, nullable=False)
    project_type = Column(String, default="normal")
    description = Column(Text, nullable=True)
    
    start_date = Column(String, nullable=False)
    end_date = Column(String, nullable=True)
    status = Column(String, default="planning")
    
    target_gmv = Column(Float, default=0)
    target_budget = Column(Float, default=0)
    actual_gmv = Column(Float, default=0)
    actual_spend = Column(Float, default=0)
    
    owner = Column(String, nullable=True)
    members = Column(JSON, nullable=True)
    
    used_sop_id = Column(Integer, nullable=True)
    sop_feedback = Column(Text, nullable=True)
    effectiveness_score = Column(Float, default=0)
    
    timeline = Column(JSON, nullable=True)
    key_decisions = Column(JSON, nullable=True)
    summary = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class TaskItem(Base):
    """任务管理"""
    __tablename__ = "task_items"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    task_title = Column(String, nullable=False)
    task_type = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    
    project_id = Column(Integer, ForeignKey("campaign_projects.id"), nullable=True)
    parent_task_id = Column(Integer, nullable=True)
    
    assignee = Column(String, nullable=True)
    reporter = Column(String, nullable=True)
    
    priority = Column(String, default="medium")
    status = Column(String, default="todo")  # todo/in_progress/done/blocked
    
    due_date = Column(String, nullable=True)
    start_date = Column(String, nullable=True)
    actual_date = Column(String, nullable=True)
    
    deliverable = Column(Text, nullable=True)
    result = Column(Text, nullable=True)
    
    tags = Column(JSON, nullable=True)
    checklists = Column(JSON, nullable=True)
    
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class UserKPI(Base):
    """用户个人KPI"""
    __tablename__ = "user_kpis"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String, nullable=False, index=True)
    period = Column(String, nullable=False)  # YYYY-MM
    
    responsibility_description = Column(Text, nullable=True)
    
    target_gmv = Column(Float, default=0)
    target_roi = Column(Float, default=0)
    target_task_count = Column(Integer, default=0)
    target_operation_count = Column(Integer, default=0)
    
    actual_gmv = Column(Float, default=0)
    actual_roi = Column(Float, default=0)
    actual_task_count = Column(Integer, default=0)
    actual_operation_count = Column(Integer, default=0)
    
    gmv_progress = Column(Float, default=0)
    roi_progress = Column(Float, default=0)
    task_progress = Column(Float, default=0)
    operation_progress = Column(Float, default=0)
    
    custom_kpis = Column(JSON, nullable=True)
    performance_rating = Column(String, nullable=True)
    comment = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class SmartAlertRule(Base):
    """智能告警规则"""
    __tablename__ = "smart_alert_rules"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    rule_name = Column(String, nullable=False)
    rule_type = Column(String, nullable=True)
    
    product_id = Column(String, nullable=True)
    product_ids = Column(JSON, nullable=True)
    metric = Column(String, nullable=False)
    metric_label = Column(String, nullable=True)
    
    condition_type = Column(String, default="threshold")
    operator = Column(String, default=">")
    threshold = Column(Float, default=0)
    
    window_type = Column(String, default="consecutive")
    window_size = Column(Integer, default=2)
    
    compared_period = Column(String, nullable=True)
    change_percent_threshold = Column(Float, default=20)
    
    level = Column(String, default="warning")
    severity = Column(String, default="medium")
    enabled = Column(Boolean, default=True)
    is_active = Column(Boolean, default=True)
    
    notify_channels = Column(JSON, default=["in_app"])
    notify_users = Column(JSON, nullable=True)
    notify_webhook = Column(String, nullable=True)
    
    tags = Column(JSON, nullable=True)
    remark = Column(Text, nullable=True)
    
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class SmartAlert(Base):
    """智能告警记录"""
    __tablename__ = "smart_alerts"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    rule_id = Column(Integer, ForeignKey("smart_alert_rules.id"), nullable=True)
    
    alert_type = Column(String, nullable=True)
    title = Column(String, nullable=False)
    detail = Column(Text, nullable=True)
    
    product_id = Column(String, nullable=True)
    product_title = Column(String, nullable=True)
    metric = Column(String, nullable=True)
    metric_label = Column(String, nullable=True)
    
    current_value = Column(Float, default=0)
    threshold_value = Column(Float, default=0)
    compared_value = Column(Float, default=0)
    change_percent = Column(Float, default=0)
    
    period = Column(String, nullable=True)
    alert_date = Column(String, nullable=True)
    
    level = Column(String, default="warning")
    severity = Column(String, default="medium")
    
    dismissed = Column(Boolean, default=False)
    dismissed_by = Column(String, nullable=True)
    dismissed_at = Column(DateTime, nullable=True)
    dismiss_note = Column(Text, nullable=True)
    
    action_taken = Column(Text, nullable=True)
    resolved = Column(Boolean, default=False)
    resolved_at = Column(DateTime, nullable=True)
    
    analysis_result = Column(JSON, nullable=True)
    recommendations = Column(JSON, nullable=True)
    
    created_at = Column(DateTime, default=func.now())


class SupplyChainData(Base):
    """供应链数据"""
    __tablename__ = "supply_chain_data"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(String, nullable=False, index=True)
    date = Column(String, nullable=False, index=True)
    
    current_stock = Column(Integer, default=0)
    on_order_qty = Column(Integer, default=0)
    available_qty = Column(Integer, default=0)
    
    safety_stock = Column(Integer, default=0)
    days_in_stock = Column(Float, default=0)
    predicted_out_of_stock_date = Column(String, nullable=True)
    
    sell_through_rate = Column(Float, default=0)
    turnover_rate = Column(Float, default=0)
    
    lead_time = Column(Integer, default=0)
    vendor_name = Column(String, nullable=True)
    purchase_price = Column(Float, default=0)
    
    data_source = Column(String, nullable=True)
    imported_at = Column(DateTime, default=func.now())


class InventoryAlert(Base):
    """库存告警"""
    __tablename__ = "inventory_alerts"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(String, nullable=False, index=True)
    alert_type = Column(String, nullable=False)  # out_of_stock/low_stock/slow_moving/overstock
    
    title = Column(String, nullable=True)
    detail = Column(Text, nullable=True)
    
    current_stock = Column(Integer, default=0)
    recommended_action = Column(Text, nullable=True)
    action_taken = Column(Text, nullable=True)
    
    level = Column(String, default="warning")
    status = Column(String, default="pending")
    
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class CampaignProjectSOPLink(Base):
    """项目与SOP模板关联"""
    __tablename__ = "campaign_project_sop_links"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("campaign_projects.id"), index=True, nullable=False)
    sop_template_id = Column(Integer, ForeignKey("sop_templates.id"), index=True, nullable=False)
    adaptation_note = Column(Text, nullable=True)
    effectiveness_rating = Column(Integer, default=0)
    created_at = Column(DateTime, default=func.now())


class UserDailyPerformance(Base):
    """用户每日绩效"""
    __tablename__ = "user_daily_performance"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String, nullable=False, index=True)
    date = Column(String, nullable=False, index=True)
    
    gmv = Column(Float, default=0)
    order_count = Column(Integer, default=0)
    operation_count = Column(Integer, default=0)
    task_completed = Column(Integer, default=0)
    time_spent = Column(Float, default=0)
    
    metrics = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=func.now())

