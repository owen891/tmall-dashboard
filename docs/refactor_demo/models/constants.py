"""
常量定义 — 安全白名单、维度映射等。

从 data_api.py 提取，保持原有安全设计不变。
所有 SQL 拼接仅使用此文件中的硬编码值，不接受用户输入。
"""

# 维度映射：dim 参数 → 表名、日期列、访客列
# 安全设计：仅允许这三个值，防止 SQL 注入
DIMENSION_MAP = {
    'monthly': {'table': 'monthly_data', 'date_col': 'month', 'visitors_col': 'visitors'},
    'weekly':  {'table': 'weekly_data',  'date_col': 'week_start', 'visitors_col': 'ipv'},
    'daily':   {'table': 'daily_data',   'date_col': 'date', 'visitors_col': 'ipv'},
}

# 允许行内编辑的字段白名单
ALLOWED_FIELDS = {'tier', 'style', 'scene', 'manager', 'remark'}

# 允许排序的字段白名单
SORT_WHITELIST = {
    'payment_amount', 'net_sales', 'visitors', 'ipv', 'payment_conversion',
    'ad_spend', 'ad_roi', 'refund_rate', 'avg_order_value', 'uv_value',
    'cart_rate', 'fav_rate', 'bounce_rate', 'score', 'buyers',
    'search_ratio', 'repurchase_rate', 'cross_sell_rate',
    'title', 'product_id', 'tier', 'style', 'manager',
}
