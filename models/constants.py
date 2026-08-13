DIMENSION_MAP = {
    'monthly': {
        'table': 'monthly_data',
        'date_col': 'month',
        'visitors_col': 'visitors',
    },
    'weekly': {
        'table': 'weekly_data',
        'date_col': 'week_start',
        'visitors_col': 'ipv',
    },
    'daily': {
        'table': 'daily_data',
        'date_col': 'date',
        'visitors_col': 'ipv',
    },
}

ALLOWED_FIELDS = {'tier', 'style', 'scene', 'manager', 'remark'}

SORT_WHITELIST = {
    'payment_amount', 'net_sales', 'visitors', 'ipv',
    'payment_conversion', 'ad_spend', 'ad_roi', 'refund_rate',
    'avg_order_value', 'uv_value', 'cart_rate', 'fav_rate',
    'bounce_rate', 'score', 'buyers', 'search_ratio',
    'repurchase_rate', 'cross_sell_rate', 'title', 'product_id',
    'tier', 'style', 'manager',
}
