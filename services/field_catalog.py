"""Authoritative user-facing field metadata.

The API keeps legacy aliases at its adapters, while configuration surfaces use
these standard keys and labels.
"""


PROMOTION_FIELDS = (
    ('product', '商品主图 / 商品', '基础信息', 'text'),
    ('ad_spend', '推广花费', '投入与成交', 'money'),
    ('attributed_payment_amount', '推广成交', '投入与成交', 'money'),
    ('link_gsv', '链接 GSV', '投入与成交', 'money'),
    ('link_net_sales', '链接净销售', '投入与成交', 'money'),
    ('expense_ratio', '费比', '投入与成交', 'percent'),
    ('roi', '推广 ROI', '投入与成交', 'ratio'),
    ('impressions', '展现量', '流量与转化', 'number'),
    ('clicks', '点击量', '流量与转化', 'number'),
    ('ctr', '点击率', '流量与转化', 'percent'),
    ('cpm', '千次展现成本', '流量与转化', 'moneyNullable'),
    ('payment_buyers', '支付买家数', '流量与转化', 'number'),
    ('cvr', '支付转化率', '流量与转化', 'percent'),
    ('cpc', '平均点击花费', '流量与转化', 'moneyNullable'),
    ('cart_adds', '加购次数', '行为成本', 'numberNullable'),
    ('cart_rate', '加购率', '行为成本', 'percent'),
    ('cart_cost', '加购成本', '行为成本', 'moneyNullable'),
    ('new_buyers', '拉新买家数', '拉新经营', 'numberNullable'),
    ('new_buyer_ratio', '拉新占比', '拉新经营', 'percent'),
    ('new_customer_cost', '拉新成本', '拉新经营', 'moneyNullable'),
    ('total_orders', '推广订单数', '投入与成交', 'numberNullable'),
    ('favs', '收藏次数', '行为成本', 'numberNullable'),
    ('direct_cart_adds', '直接加购', '归因构成', 'numberNullable'),
    ('indirect_cart_adds', '间接加购', '归因构成', 'numberNullable'),
    ('direct_payment_amount', '直接成交', '归因构成', 'money'),
    ('indirect_payment_amount', '间接成交', '归因构成', 'money'),
    ('paid_share', '付费成交占比', '归因构成', 'percent'),
    ('spend', '花费', '月度汇总', 'money'),
    ('sales', '成交', '月度汇总', 'money'),
    ('visitors', '访客数', '月度汇总', 'number'),
    ('ppc', '平均点击花费', '月度汇总', 'moneyNullable'),
    ('action', '操作', '基础信息', 'action'),
)


PRODUCT_LABELS = {
    'product_id': '商品 ID', 'title': '商品', 'payment_amount': '销售额',
    'net_sales': '净销售额', 'refund_amount': '退款金额', 'refund_rate': '退款率',
    'conversion': '转化率', 'payment_conversion_rate': '支付转化率',
    'ad_spend': '推广花费', 'roi': 'ROI', 'overall_roi': '整体 ROI',
    'tier': '分层', 'style': '风格', 'lifecycle_stage': '生命周期阶段',
    'seasonality': '季节属性', 'status': '状态', 'manager': '负责人',
    'has_pending_action': '待办动作', 'expense_ratio': '费比', 'score': '评分',
}


PRODUCT_LABELS.update({
    'presale_amount': '\u9884\u552e\u652f\u4ed8\u91d1\u989d',
    'presale_qty': '\u9884\u552e\u9500\u91cf',
    'search_click_rate': '\u514d\u8d39\u641c\u7d22\u70b9\u51fb\u7387',
    'category_width': '\u8fde\u5e26\u8d2d\u4e70\u53f6\u5b50\u7c7b\u76ee\u5bbd\u5ea6',
})


def _product_fields():
    # Import lazily to keep settings_service and this module free of an import
    # cycle while retaining the existing literal VIEW_COLUMNS contract.
    from services.settings_service import VIEW_COLUMNS

    numeric = {
        'payment_amount', 'payment_count', 'net_sales', 'refund_amount',
        'refund_rate', 'conversion', 'payment_conversion_rate', 'ad_spend',
        'roi', 'overall_roi', 'paid_ratio', 'expense_ratio', 'score',
        'presale_amount', 'presale_qty', 'search_click_rate', 'category_width',
    }
    return [
        {
            'key': key,
            'label': PRODUCT_LABELS.get(key, key),
            'domain': 'products',
            'source_type': 'product_day',
            'group': '商品字段',
            'format': 'number' if key in numeric else 'text',
            'aliases': [],
        }
        for key in sorted(VIEW_COLUMNS | {'product_id', 'title'})
    ]


def get_field_catalog():
    return {
        'products': _product_fields(),
        'promotion': [
            {
                'key': key,
                'label': label,
                'domain': 'promotion',
                'source_type': 'promotion_daily',
                'group': group,
                'format': fmt,
                'aliases': [],
            }
            for key, label, group, fmt in PROMOTION_FIELDS
        ],
    }


def promotion_field_keys():
    return {key for key, *_ in PROMOTION_FIELDS}
