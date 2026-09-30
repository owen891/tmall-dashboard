(function () {
  const columns = [
    { key: 'product', label: '商品主图 / 商品', group: '基础信息' },
    { key: 'ad_spend', label: '推广花费', group: '投入与成交', format: 'money' },
    { key: 'attributed_payment_amount', label: '推广成交', group: '投入与成交', format: 'money' },
    { key: 'link_gsv', label: '链接销售额', group: '投入与成交', format: 'money' },
    { key: 'link_net_sales', label: '链接净销售额', group: '投入与成交', format: 'money' },
    { key: 'expense_ratio', label: '费比', group: '投入与成交', format: 'percent' },
    { key: 'roi', label: '推广 ROI', group: '投入与成交', format: 'ratio' },
    { key: 'impressions', label: '展现量', group: '流量与转化', format: 'number' },
    { key: 'clicks', label: '点击量', group: '流量与转化', format: 'number' },
    { key: 'ctr', label: '点击率', group: '流量与转化', format: 'percent' },
    { key: 'cpm', label: '千次展现成本', group: '流量与转化', format: 'moneyNullable' },
    { key: 'payment_buyers', label: '支付买家数', group: '流量与转化', format: 'number' },
    { key: 'cvr', label: '商品支付转化率', group: '流量与转化', format: 'percent' },
    { key: 'cpc', label: '平均点击花费', group: '流量与转化', format: 'moneyNullable' },
    { key: 'cart_adds', label: '加购次数', group: '行为成本', format: 'numberNullable' },
    { key: 'cart_rate', label: '加购率', group: '行为成本', format: 'percent' },
    { key: 'cart_cost', label: '加购成本', group: '行为成本', format: 'moneyNullable' },
    { key: 'new_buyers', label: '拉新买家数', group: '拉新经营', format: 'numberNullable' },
    { key: 'new_buyer_ratio', label: '拉新占比', group: '拉新经营', format: 'percent' },
    { key: 'new_customer_cost', label: '拉新成本', group: '拉新经营', format: 'moneyNullable' },
    { key: 'total_orders', label: '推广订单数', group: '投入与成交', format: 'numberNullable' },
    { key: 'favs', label: '收藏次数', group: '行为成本', format: 'numberNullable' },
    { key: 'direct_cart_adds', label: '直接加购', group: '归因构成', format: 'numberNullable' },
    { key: 'indirect_cart_adds', label: '间接加购', group: '归因构成', format: 'numberNullable' },
    { key: 'direct_payment_amount', label: '直接付费成交', group: '归因构成', format: 'money' },
    { key: 'indirect_payment_amount', label: '间接付费成交', group: '归因构成', format: 'money' },
    { key: 'paid_share', label: '付费成交占比', group: '归因构成', format: 'percent' },
    { key: 'action', label: '操作', group: '基础信息' },
  ];
  const templates = [
    { id: 'products-diagnosis', name: '经营诊断', fields: ['product', 'ad_spend', 'attributed_payment_amount', 'link_net_sales', 'expense_ratio', 'roi', 'ctr', 'cvr', 'cart_cost', 'new_customer_cost', 'action'] },
    { id: 'products-traffic', name: '流量转化', fields: ['product', 'impressions', 'clicks', 'ctr', 'cpm', 'payment_buyers', 'cvr', 'cart_adds', 'cart_rate', 'cart_cost'] },
    { id: 'products-acquisition', name: '拉新经营', fields: ['product', 'ad_spend', 'attributed_payment_amount', 'new_buyers', 'new_buyer_ratio', 'new_customer_cost', 'roi', 'paid_share'] },
    { id: 'products-attribution', name: '成交归因', fields: ['product', 'ad_spend', 'attributed_payment_amount', 'direct_payment_amount', 'indirect_payment_amount', 'direct_cart_adds', 'indirect_cart_adds', 'paid_share', 'roi'] },
    { id: 'products-complete', name: '完整明细', fields: ['product', 'ad_spend', 'attributed_payment_amount', 'link_gsv', 'link_net_sales', 'expense_ratio', 'roi', 'impressions', 'clicks', 'ctr', 'cpm', 'payment_buyers', 'cvr', 'cpc', 'cart_adds', 'cart_rate', 'cart_cost', 'new_buyers', 'new_buyer_ratio', 'new_customer_cost', 'total_orders', 'favs', 'direct_payment_amount', 'indirect_payment_amount', 'paid_share', 'action'] },
    { id: 'products-efficiency', name: '投放效率', fields: ['product', 'ad_spend', 'attributed_payment_amount', 'link_gsv', 'link_net_sales', 'expense_ratio', 'roi', 'paid_share', 'cart_cost', 'new_customer_cost'] },
    { id: 'products-action', name: '优化动作', fields: ['product', 'roi', 'ctr', 'cvr', 'ad_spend', 'action'] },
  ];
  window.DemoPromotionFields = Object.freeze({ products: Object.freeze({
    label: '商品表现', title: '商品推广表现', columns: Object.freeze(columns), templates: Object.freeze(templates),
  }) });
})();
