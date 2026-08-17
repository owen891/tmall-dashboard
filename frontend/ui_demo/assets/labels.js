(function () {
  const staticLabels = {
    status: { active: '在售', inactive: '下架', delisted: '下架', draft: '草稿', pending_execution: '待执行', executing: '执行中', observing: '观察中', blocked: '阻塞', calculation_failed: '计算失败', pending_review: '待复盘', completed: '已完成', cancelled: '已取消', error: '错误', running: '运行中', todo: '待处理', in_progress: '处理中', done: '已完成', disabled: '已停用' },
    confidence: { high: '高', medium: '中', low: '低' },
    source: { system: '系统', product: '商品数据', category: '类目数据', manual: '人工维护', recommended: '系统建议' },
    period: { day: '日度', week: '周度', month: '月度', date: '日期', quarter: '季度', year: '年度' },
    action: { increase_sales: '提升销售', optimize_roi: '优化投产', reduce_refund: '降低退款', increase_conversion: '提升转化' },
    priority: { P0: 'P0 · 紧急', P1: 'P1 · 高', P2: 'P2 · 中', P3: 'P3 · 低' },
    rating: { A: 'A · 优秀', B: 'B · 良好', C: 'C · 待提升', D: 'D · 未达标' },
    quality: { passed: '通过', failed: '未通过' },
    field: { product_id: '商品编号', product_name: '商品名称', date: '日期', payment_amount: '支付金额', successful_refund_amount: '成功退款金额', product_visitors: '商品访客数', payment_buyers: '支付买家数', returning_payment_buyers: '复购买家数', ad_spend: '推广花费', channel: '推广渠道', campaign_id: '推广计划', unit_id: '推广单元', attributed_payment_amount: '推广成交' },
    match: { empty: '空列', manual: '手动匹配', unmatched: '未匹配', template: '模板匹配', exact: '精确匹配', alias: '别名匹配', text: '文本', number: '数值', date: '日期' },
  };
  Object.assign(staticLabels.field, {
    payment_conversion_rate: '\u5546\u54c1\u652f\u4ed8\u8f6c\u5316\u7387', average_order_value: '\u5ba2\u5355\u4ef7', expense_ratio: '\u8d39\u6bd4',
    parent_product_id: '\u4e3b\u5546\u54c1ID', product_type: '\u5546\u54c1\u7c7b\u578b', sku_code: '\u8d27\u53f7',
    source_status: '\u5546\u54c1\u72b6\u6001', product_tags: '\u5546\u54c1\u6807\u7b7e', page_views: '\u5546\u54c1\u6d4f\u89c8\u91cf',
    avg_stay_duration: '\u5e73\u5747\u505c\u7559\u65f6\u957f', bounce_rate: '\u8df3\u51fa\u7387', favorite_users: '\u5546\u54c1\u6536\u85cf\u4eba\u6570',
    cart_items: '\u5546\u54c1\u52a0\u8d2d\u4ef6\u6570', cart_users: '\u5546\u54c1\u52a0\u8d2d\u4eba\u6570', order_buyers: '\u4e0b\u5355\u4e70\u5bb6\u6570',
    order_items: '\u4e0b\u5355\u4ef6\u6570', order_amount: '\u4e0b\u5355\u91d1\u989d', order_conversion: '\u4e0b\u5355\u8f6c\u5316\u7387',
    payment_items: '\u652f\u4ed8\u4ef6\u6570', payment_conversion: '\u5546\u54c1\u652f\u4ed8\u8f6c\u5316\u7387', new_payment_buyers: '\u652f\u4ed8\u65b0\u4e70\u5bb6\u6570',
    returning_payment_amount: '\u8001\u4e70\u5bb6\u652f\u4ed8\u91d1\u989d', juhuasuan_payment_amount: '\u805a\u5212\u7b97\u652f\u4ed8\u91d1\u989d',
    uv_value: '\u8bbf\u5ba2\u5e73\u5747\u4ef7\u503c', competitiveness_score: '\u7ade\u4e89\u529b\u8bc4\u5206',
    year_to_date_payment_amount: '\u5e74\u7d2f\u8ba1\u652f\u4ed8\u91d1\u989d', month_to_date_payment_amount: '\u6708\u7d2f\u8ba1\u652f\u4ed8\u91d1\u989d',
    month_to_date_payment_items: '\u6708\u7d2f\u8ba1\u652f\u4ed8\u4ef6\u6570', search_conversion: '\u641c\u7d22\u5f15\u5bfc\u652f\u4ed8\u8f6c\u5316\u7387',
    search_visitors: '\u641c\u7d22\u5f15\u5bfc\u8bbf\u5ba2\u6570', search_payment_buyers: '\u641c\u7d22\u5f15\u5bfc\u652f\u4ed8\u4e70\u5bb6\u6570',
    structured_detail_conversion: '\u7ed3\u6784\u5316\u8be6\u60c5\u5f15\u5bfc\u8f6c\u5316\u7387', structured_detail_payment_ratio: '\u7ed3\u6784\u5316\u8be6\u60c5\u5f15\u5bfc\u6210\u4ea4\u5360\u6bd4',
    product_growth_stage: '\u8d27\u54c1\u6210\u957f\u9636\u6bb5', paid_visitors: '\u8425\u9500\u63a8\u5e7fIPV',
    organic_visitors: '\u975e\u63a8\u5e7fIPV', recommend_visitors: '\u63a8\u8350IPV', ad_roi: '\u63a8\u5e7f ROI',
    favorite_cart_rate: '\u6536\u52a0\u7387', repurchase_rate: '\u590d\u8d2d\u7387', presale_amount: '\u9884\u552e\u652f\u4ed8\u91d1\u989d',
    presale_qty: '\u9884\u552e\u9500\u91cf', search_click_rate: '\u514d\u8d39\u641c\u7d22\u70b9\u51fb\u7387',
    payment_unit_price: '\u7b14\u5355\u4ef7', cross_sell_qty: '\u8fde\u5e26\u8d2d\u4e70\u91cf',
    cross_sell_rate: '\u8fde\u5e26\u8d2d\u4e70\u7387', cross_sell_categories: '\u8fde\u5e26\u8d2d\u4e70\u53f6\u5b50\u7c7b\u76ee\u5bbd\u5ea6',
    repurchase_users: '\u590d\u8d2d\u7528\u6237\u6570',
  });
  const fallbackDictionaries = {
    tiers: [], styles: [],
    lifecycle_stages: [
      ['data_accumulating', '数据积累中'], ['new', '新品期'], ['growth', '成长期'],
      ['breakout', '爆发期'], ['mature', '成熟期'], ['decline', '衰退期'], ['clearance', '清退期'],
    ],
    seasonal_attributes: [
      ['stable', '常年稳定型'], ['spring_summer', '春夏型'], ['autumn_winter', '秋冬型'],
      ['single_peak', '单峰季节型'], ['double_peak', '双峰季节型'],
      ['promotion_driven', '节日/大促驱动型'], ['manual', '人工维护'],
    ],
  };
  let dictionaries = Object.fromEntries(Object.entries(fallbackDictionaries).map(([key, items]) => [key, items.map(([value, label]) => ({ value, label, enabled: true, system: true }))]));
  let loading;

  const missingValues = new Set(['', 'nan', 'none', 'null', 'undefined', '--']);
  function clean(value, fallback) {
    const normalized = String(value ?? '').trim();
    return missingValues.has(normalized.toLowerCase()) ? (arguments.length > 1 ? fallback : '--') : normalized;
  }

  function setDictionaries(value) {
    if (value && typeof value === 'object') dictionaries = value;
    return dictionaries;
  }
  function classification(group, value, fallback) {
    const normalized = clean(value, '');
    const item = (dictionaries[group] || []).find((entry) => entry.value === normalized);
    return clean(item?.label, fallback || normalized);
  }
  function label(kind, value, fallback) {
    const normalized = clean(value, '');
    return staticLabels[kind]?.[normalized] || fallback || normalized || '--';
  }
  function enabled(group, includeValue) {
    return (dictionaries[group] || []).filter((item) => item.enabled || item.value === includeValue);
  }
  async function load() {
    if (!loading) loading = DemoApi.domainRequest('/api/settings')
      .then((response) => setDictionaries(response.data.classification_dictionaries))
      .catch(() => dictionaries);
    return loading;
  }
  window.DemoLabels = { clean, label, classification, enabled, load, setDictionaries, get dictionaries() { return dictionaries; } };
})();
