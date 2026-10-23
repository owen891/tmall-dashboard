// Shared promotion value semantics. Pure functions also run in Node contract tests.
(function (root) {
  const present = (value) => value !== null && value !== undefined && value !== '' && Number.isFinite(Number(value));
  const money = (value) => present(value) ? `￥${Number(value).toLocaleString('zh-CN', { maximumFractionDigits: 2 })}` : '--';
  const number = (value) => present(value) ? Number(value).toLocaleString('zh-CN') : '--';
  const ratio = (value) => present(value) ? Number(value).toFixed(2) : '--';
  const percent = (value) => present(value) ? `${(Number(value) * 100).toFixed(2)}%` : '--';
  function coverageLabel(coverage) {
    if (!coverage) return '';
    if (coverage.inputs) return Object.entries(coverage.inputs).map(([key, item]) => `${key} ${coverageLabel(item)}`).join('; ');
    if (coverage.sources) return coverage.sources.map(coverageLabel).join('; ');
    return `${coverage.observed_rows}/${coverage.expected_rows} ${coverage.source || ''}`.trim();
  }
  function format(row, key, kind = 'number') {
    const status = row.metric_availability?.[key];
    const value = row[key];
    const formatter = kind === 'money' || kind === 'moneyNullable' ? money : kind === 'ratio' ? ratio : kind === 'percent' ? percent : number;
    if (status === 'missing-fields') return '--（未提供）';
    if (status === 'insufficient-data') return '--（不可计算）';
    const display = formatter(value);
    return status === 'partial' ? `${display}（部分 ${coverageLabel(row.metric_coverage?.[key])}）` : display;
  }
  function exportValue(row, key) {
    const status = row.metric_availability?.[key];
    if (status === 'missing-fields') return '--（未提供）';
    if (status === 'insufficient-data') return '--（不可计算）';
    if (status === 'partial') return `${present(row[key]) ? row[key] : '--'}（部分 ${coverageLabel(row.metric_coverage?.[key])}）`;
    return present(row[key]) ? row[key] : '';
  }
  // Large values stay numeric; availability and full coverage are separate UI layers.
  // format()/exportValue() retain their original evidence-rich table/export contract.
  function valueText(row, key, kind = 'number') {
    const status = row.metric_availability?.[key];
    if (status === 'missing-fields' || status === 'insufficient-data') return '--';
    const formatter = kind === 'money' || kind === 'moneyNullable' ? money : kind === 'ratio' ? ratio : kind === 'percent' ? percent : number;
    return formatter(row[key]);
  }
  function statusLabel(row, key) {
    return ({ partial: '部分数据', 'missing-fields': '未提供', 'insufficient-data': '不可计算' })[row.metric_availability?.[key]] || '';
  }
  function compact(row, key, kind = 'number') {
    const label = statusLabel(row, key);
    return valueText(row, key, kind) + (label ? `（${label}）` : '');
  }
  function compactTitle(row, key, kind = 'number') {
    const detail = format(row, key, kind);
    return statusLabel(row, key) ? detail : '';
  }
  function chartValue(row, key) {
    return present(row[key]) && (!row.metric_availability?.[key] || row.metric_availability[key] === 'available') ? Number(row[key]) : null;
  }
  function summarize(rows) {
    const result = { metric_availability: {}, metric_coverage: {} };
    ['ad_spend', 'attributed_payment_amount', 'direct_payment_amount', 'indirect_payment_amount', 'impressions', 'clicks', 'payment_buyers', 'link_gsv'].forEach((key) => {
      const values = rows.filter((row) => present(row[key]));
      result[key] = values.length ? values.reduce((sum, row) => sum + Number(row[key]), 0) : null;
      const parts = rows.map((row) => row.metric_coverage?.[key]).filter(Boolean);
      const observed = parts.reduce((sum, c) => sum + Number(c.observed_rows || 0), 0);
      const expected = parts.reduce((sum, c) => sum + Number(c.expected_rows || 0), 0);
      result.metric_coverage[key] = { observed_rows: parts.length ? observed : values.length, expected_rows: parts.length ? expected : rows.length, source: parts[0]?.source || 'aggregate_rows' };
      result.metric_availability[key] = !values.length ? 'missing-fields' : values.length < rows.length || rows.some((row) => row.metric_availability?.[key] === 'partial') ? 'partial' : 'available';
    });
    [['roi', 'attributed_payment_amount', 'ad_spend'], ['ctr', 'clicks', 'impressions'], ['cvr', 'payment_buyers', 'clicks'], ['expense_ratio', 'ad_spend', 'link_gsv']].forEach(([key, numerator, denominator]) => {
      const states = [result.metric_availability[numerator], result.metric_availability[denominator]];
      const status = states.includes('missing-fields') ? 'missing-fields' : states.includes('partial') ? 'partial' : result[denominator] === 0 ? 'insufficient-data' : 'available';
      result[key] = status === 'available' ? result[numerator] / result[denominator] : null;
      result.metric_availability[key] = status;
      result.metric_coverage[key] = { inputs: { [numerator]: result.metric_coverage[numerator], [denominator]: result.metric_coverage[denominator] } };
    });
    // Preserve the command-board weighted paid-share formula, but only when
    // every input is known; missing rows must not become a zero contribution.
    const paidInputs = rows.map((row) => ({
      share: row.paid_share,
      amount: present(row.attributed_payment_amount) ? row.attributed_payment_amount : row.payment_amount,
      status: row.metric_availability?.paid_share,
      amountStatus: row.metric_availability?.attributed_payment_amount,
    }));
    const paidMissing = paidInputs.some((p) => !present(p.share) || !present(p.amount));
    const paidPartial = paidInputs.some((p) => p.status === 'partial' || p.amountStatus === 'partial');
    const paidTotal = paidInputs.reduce((sum, p) => sum + (present(p.amount) ? Number(p.amount) : 0), 0);
    result.metric_availability.paid_share = !rows.length || paidMissing ? (paidPartial ? 'partial' : 'missing-fields') : paidPartial ? 'partial' : paidTotal === 0 ? 'insufficient-data' : 'available';
    result.paid_share = result.metric_availability.paid_share === 'available'
      ? paidInputs.reduce((sum, p) => sum + Number(p.share) * Number(p.amount), 0) / paidTotal : null;
    result.metric_coverage.paid_share = { inputs: Object.fromEntries(rows.map((row, index) => [String(index), {
      inputs: { paid_share: row.metric_coverage?.paid_share, attributed_payment_amount: row.metric_coverage?.attributed_payment_amount },
    }])) };
    return result;
  }
  const api = { present, money, number, ratio, percent, format, exportValue, coverageLabel, summarize, chartValue, valueText, statusLabel, compact, compactTitle };
  root.TmallPromotionMetrics = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})(typeof window === 'undefined' ? globalThis : window);

(function () {
  if (typeof document === 'undefined') return;
  const promotionMetrics = window.TmallPromotionMetrics;
  const $ = (selector, root = document) => root.querySelector(selector);
  const promotionDetailTabs = ['overview', 'units'];
  const tabDefinitions = {
    products: {
      label: '商品表现',
      title: '商品推广表现',
      hint: '按商品 ID 唯一汇总，可与商品运营页交叉核对。',
      empty: '当前筛选范围没有商品推广数据。',
      columns: [
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
      ],
      templates: [
        { id: 'products-diagnosis', name: '经营诊断', fields: ['product', 'ad_spend', 'attributed_payment_amount', 'link_net_sales', 'expense_ratio', 'roi', 'ctr', 'cvr', 'cart_cost', 'new_customer_cost', 'action'] },
        { id: 'products-traffic', name: '流量转化', fields: ['product', 'impressions', 'clicks', 'ctr', 'cpm', 'payment_buyers', 'cvr', 'cart_adds', 'cart_rate', 'cart_cost'] },
        { id: 'products-acquisition', name: '拉新经营', fields: ['product', 'ad_spend', 'attributed_payment_amount', 'new_buyers', 'new_buyer_ratio', 'new_customer_cost', 'roi', 'paid_share'] },
        { id: 'products-attribution', name: '成交归因', fields: ['product', 'ad_spend', 'attributed_payment_amount', 'direct_payment_amount', 'indirect_payment_amount', 'direct_cart_adds', 'indirect_cart_adds', 'paid_share', 'roi'] },
        { id: 'products-complete', name: '完整明细', fields: ['product', 'ad_spend', 'attributed_payment_amount', 'link_gsv', 'link_net_sales', 'expense_ratio', 'roi', 'impressions', 'clicks', 'ctr', 'cpm', 'payment_buyers', 'cvr', 'cpc', 'cart_adds', 'cart_rate', 'cart_cost', 'new_buyers', 'new_buyer_ratio', 'new_customer_cost', 'total_orders', 'favs', 'direct_payment_amount', 'indirect_payment_amount', 'paid_share', 'action'] },
      ],
    },
    keywords: {
      label: '关键词汇总', title: '关键词月度汇总', hint: '来自商品月表的关键词汇总字段，不代表词级明细。', empty: '当前日期范围没有可用的关键词月度汇总数据。',
      columns: [
        { key: 'product', label: '关键词 / 商品', group: '基础信息' }, { key: 'spend', label: '推广花费', group: '投入与成交', format: 'money' },
        { key: 'sales', label: '推广成交', group: '投入与成交', format: 'money' }, { key: 'roi', label: '推广 ROI', group: '投入与成交', format: 'ratio' },
        { key: 'visitors', label: '访客数', group: '流量与转化', format: 'number' }, { key: 'ppc', label: '平均点击花费', group: '流量与转化', format: 'moneyNullable' },
      ],
      templates: [{ id: 'keywords-overview', name: '关键词概览', fields: ['product', 'spend', 'sales', 'roi', 'visitors', 'ppc'] }, { id: 'keywords-efficiency', name: '投产效率', fields: ['product', 'spend', 'sales', 'roi'] }],
    },
    crowd: {
      label: '人群汇总', title: '人群月度汇总', hint: '来自商品月表的人群汇总字段，不代表人群包级明细。', empty: '当前日期范围没有可用的人群月度汇总数据。',
      columns: [
        { key: 'product', label: '人群 / 商品', group: '基础信息' }, { key: 'spend', label: '推广花费', group: '投入与成交', format: 'money' },
        { key: 'sales', label: '推广成交', group: '投入与成交', format: 'money' }, { key: 'roi', label: '推广 ROI', group: '投入与成交', format: 'ratio' },
        { key: 'visitors', label: '访客数', group: '流量与转化', format: 'number' }, { key: 'ppc', label: '平均点击花费', group: '流量与转化', format: 'moneyNullable' },
      ],
      templates: [{ id: 'crowd-overview', name: '人群概览', fields: ['product', 'spend', 'sales', 'roi', 'visitors', 'ppc'] }, { id: 'crowd-efficiency', name: '投产效率', fields: ['product', 'spend', 'sales', 'roi'] }],
    },
    creative: {
      label: '创意汇总', title: '创意月度汇总', hint: '当前为演示创意聚合，不代表创意 ID 级明细。', empty: '当前日期范围没有可用的创意汇总数据。',
      columns: [
        { key: 'product', label: '创意 / 商品', group: '基础信息' }, { key: 'spend', label: '推广花费', group: '投入与成交', format: 'money' },
        { key: 'sales', label: '推广成交', group: '投入与成交', format: 'money' }, { key: 'roi', label: '推广 ROI', group: '投入与成交', format: 'ratio' },
        { key: 'visitors', label: '点击量', group: '流量与转化', format: 'number' }, { key: 'ppc', label: '平均点击花费', group: '流量与转化', format: 'moneyNullable' },
      ],
      templates: [{ id: 'creative-overview', name: '创意概览', fields: ['product', 'spend', 'sales', 'roi', 'visitors', 'ppc'] }, { id: 'creative-efficiency', name: '投产效率', fields: ['product', 'spend', 'sales', 'roi'] }],
    },
    site: {
      label: '站内渠道汇总', title: '站内渠道月度汇总', hint: '来自商品月表的站内渠道汇总字段，不代表资源位级明细。', empty: '当前日期范围没有可用的站内渠道月度汇总数据。',
      columns: [
        { key: 'product', label: '站内渠道 / 商品', group: '基础信息' }, { key: 'spend', label: '推广花费', group: '投入与成交', format: 'money' },
        { key: 'sales', label: '推广成交', group: '投入与成交', format: 'money' }, { key: 'roi', label: '推广 ROI', group: '投入与成交', format: 'ratio' },
        { key: 'visitors', label: '访客数', group: '流量与转化', format: 'number' }, { key: 'ppc', label: '平均点击花费', group: '流量与转化', format: 'moneyNullable' },
      ],
      templates: [{ id: 'site-overview', name: '渠道概览', fields: ['product', 'spend', 'sales', 'roi', 'visitors', 'ppc'] }, { id: 'site-efficiency', name: '投产效率', fields: ['product', 'spend', 'sales', 'roi'] }],
    },
  };
  const promotionTemplateOverrides = {
    products: [
      { id: 'products-diagnosis', name: '\u7ecf\u8425\u8bca\u65ad', fields: ['product', 'ad_spend', 'attributed_payment_amount', 'link_net_sales', 'expense_ratio', 'roi', 'ctr', 'cvr', 'cart_cost', 'new_customer_cost', 'action'] },
      { id: 'products-traffic', name: '\u6d41\u91cf\u8f6c\u5316', fields: ['product', 'impressions', 'clicks', 'ctr', 'cpm', 'payment_buyers', 'cvr', 'cart_adds', 'cart_rate', 'cart_cost'] },
      { id: 'products-acquisition', name: '\u62c9\u65b0\u7ecf\u8425', fields: ['product', 'ad_spend', 'attributed_payment_amount', 'new_buyers', 'new_buyer_ratio', 'new_customer_cost', 'roi', 'paid_share'] },
      { id: 'products-attribution', name: '\u6210\u4ea4\u5f52\u56e0', fields: ['product', 'ad_spend', 'attributed_payment_amount', 'direct_payment_amount', 'indirect_payment_amount', 'direct_cart_adds', 'indirect_cart_adds', 'paid_share', 'roi'] },
      { id: 'products-complete', name: '\u5b8c\u6574\u660e\u7ec6', fields: ['product', 'ad_spend', 'attributed_payment_amount', 'link_gsv', 'link_net_sales', 'expense_ratio', 'roi', 'impressions', 'clicks', 'ctr', 'cpm', 'payment_buyers', 'cvr', 'cpc', 'cart_adds', 'cart_rate', 'cart_cost', 'new_buyers', 'new_buyer_ratio', 'new_customer_cost', 'total_orders', 'favs', 'direct_payment_amount', 'indirect_payment_amount', 'paid_share', 'action'] },
      { id: 'products-efficiency', name: '\u6295\u653e\u6548\u7387', fields: ['product', 'ad_spend', 'attributed_payment_amount', 'link_gsv', 'link_net_sales', 'expense_ratio', 'roi', 'paid_share', 'cart_cost', 'new_customer_cost'] },
      { id: 'products-action', name: '\u4f18\u5316\u52a8\u4f5c', fields: ['product', 'roi', 'ctr', 'cvr', 'ad_spend', 'action'] },
    ],
    keywords: [
      { id: 'keywords-overview', name: '\u5173\u952e\u8bcd\u6982\u89c8', fields: ['product', 'spend', 'sales', 'roi', 'visitors', 'ppc'] },
      { id: 'keywords-efficiency', name: '\u5173\u952e\u8bcd\u6295\u4ea7', fields: ['product', 'spend', 'sales', 'roi'] },
      { id: 'keywords-traffic', name: '\u5173\u952e\u8bcd\u5f15\u6d41', fields: ['product', 'visitors', 'spend', 'ppc'] },
      { id: 'keywords-scale', name: '\u5173\u952e\u8bcd\u89c4\u6a21', fields: ['product', 'visitors', 'sales', 'roi'] },
    ],
    crowd: [
      { id: 'crowd-overview', name: '\u4eba\u7fa4\u6982\u89c8', fields: ['product', 'spend', 'sales', 'roi', 'visitors', 'ppc'] },
      { id: 'crowd-efficiency', name: '\u4eba\u7fa4\u6295\u4ea7', fields: ['product', 'spend', 'sales', 'roi'] },
      { id: 'crowd-reach', name: '\u4eba\u7fa4\u89e6\u8fbe', fields: ['product', 'visitors', 'spend', 'ppc'] },
      { id: 'crowd-value', name: '\u4eba\u7fa4\u4ef7\u503c', fields: ['product', 'sales', 'roi', 'ppc'] },
    ],
    creative: [
      { id: 'creative-overview', name: '\u521b\u610f\u6982\u89c8', fields: ['product', 'spend', 'sales', 'roi', 'visitors', 'ppc'] },
      { id: 'creative-efficiency', name: '\u521b\u610f\u6295\u4ea7', fields: ['product', 'spend', 'sales', 'roi'] },
      { id: 'creative-reach', name: '\u521b\u610f\u5f15\u6d41', fields: ['product', 'visitors', 'spend', 'ppc'] },
      { id: 'creative-test', name: '\u521b\u610f\u5bf9\u6bd4', fields: ['product', 'spend', 'sales', 'roi', 'visitors'] },
    ],
    site: [
      { id: 'site-overview', name: '\u6e20\u9053\u6982\u89c8', fields: ['product', 'spend', 'sales', 'roi', 'visitors', 'ppc'] },
      { id: 'site-efficiency', name: '\u6e20\u9053\u6295\u4ea7', fields: ['product', 'spend', 'sales', 'roi'] },
      { id: 'site-reach', name: '\u6e20\u9053\u5f15\u6d41', fields: ['product', 'visitors', 'spend', 'ppc'] },
      { id: 'site-cost', name: '\u6e20\u9053\u6210\u672c', fields: ['product', 'spend', 'sales', 'ppc'] },
    ],
  };
  Object.entries(promotionTemplateOverrides).forEach(([tab, templates]) => { tabDefinitions[tab].templates = templates; });
  if (window.DemoPromotionFields?.products) {
    tabDefinitions.products.columns = window.DemoPromotionFields.products.columns;
    tabDefinitions.products.templates = window.DemoPromotionFields.products.templates;
  }
  const promotionBuiltinTemplateIds = new Set(Object.values(promotionTemplateOverrides).flat().map((template) => template.id));

  const storageKey = 'tmall_promotion_field_templates_v1';
  const fieldPreferenceStorageKey = 'tmall_promotion_field_selection_v2';
  let fieldSelector = null;
  let templateManager = null;
  const loadCustomTemplates = () => {
    try {
      const value = JSON.parse(localStorage.getItem(storageKey) || '{}');
      return value && typeof value === 'object' ? value : {};
    } catch (_) { return {}; }
  };
  const loadFieldPreferences = () => {
    try {
      const value = JSON.parse(localStorage.getItem(fieldPreferenceStorageKey) || '{}');
      return value && typeof value === 'object' ? value : {};
    } catch (_) { return {}; }
  };
  const storedFieldPreferences = loadFieldPreferences();
  const initialPromotionParams = new URLSearchParams(window.location.search);
  const state = {
    period: '', rows: [], planRows: [], breakdowns: {}, alerts: [], availableGrains: [], activeTab: initialPromotionParams.get('tab') || 'products', dialogTab: 'products', promotionDetailTab: 'overview', promotionDetailProduct: null, promotionDetailUnits: [], promotionDetailSource: 'available', token: 0, promotionDetailRequest: 0,
    dialogReturnFocus: null, fieldDialogReturnFocus: null, chart: null, settings: null, capabilities: {}, customTemplates: loadCustomTemplates(),
    demoTabs: new Set(),
    selectedFields: Object.fromEntries(Object.entries(tabDefinitions).map(([key, definition]) => [key, [...definition.templates[0].fields]])),
    activeTemplate: Object.fromEntries(Object.entries(tabDefinitions).map(([key, definition]) => [key, definition.templates[0].id])),
  };
  Object.entries(tabDefinitions).forEach(([tab, definition]) => {
    const allowed = new Set(definition.columns.map((column) => column.key));
    const selected = Array.isArray(storedFieldPreferences.selectedFields?.[tab])
      ? [...new Set(storedFieldPreferences.selectedFields[tab].filter((key) => allowed.has(key)))]
      : [];
    if (!selected.length) return;
    state.selectedFields[tab] = selected;
    const templateId = storedFieldPreferences.activeTemplate?.[tab];
    const templateExists = [...definition.templates, ...(state.customTemplates[tab] || [])].some((template) => template.id === templateId);
    state.activeTemplate[tab] = templateExists ? templateId : 'custom';
  });
  function normalizeBreakdowns(raw) {
    const normalized = { ...(raw || {}) };
    state.demoTabs.clear();
    return normalized;
  }
  const money = promotionMetrics.money;
  const number = promotionMetrics.number;
  const numberNullable = (value) => value == null || value === '' ? '--' : number(value);
  const ratio = promotionMetrics.ratio;
  const toast = (message) => window.DemoShell?.showToast?.(message) || window.alert(message);
  const setStatus = (message) => window.DemoShell?.setStatus?.(message);
  const renderDataState = (state, details) => DemoApi.renderDataState($('[data-promotion-table-hint]'), state, details);
  const text = (value, fallback = '--') => String(value == null || value === '' ? fallback : value);
  const element = (tag, className, value) => {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (value != null) node.textContent = value;
    return node;
  };
  const promotionTable = (options = {}) => {
    const wrap = TmallUI.table(options);
    const table = wrap.querySelector('table');
    if (table) {
      table.dataset.promotionTable = '';
      table.querySelector('thead')?.setAttribute('data-promotion-head', '');
      table.querySelector('tbody')?.setAttribute('data-promotion-body', '');
    }
    return wrap;
  };
  const productId = (row) => String(row?.product_id || '');
  const productTitle = (row) => String(row?.title || '').trim() || (productId(row) ? `商品 ${productId(row)}` : '未关联商品');
  const overallRoi = (row) => row?.roi ?? row?.overall_roi ?? null;

  function getPeriod(detail) {
    const range = detail || window.TmallDateRange?.getState?.() || {};
    const value = range.endDate || range.startDate || new Date().toISOString().slice(0, 10);
    return String(value).slice(0, 7);
  }

  function promotionPath(detail, groupBy = 'product') {
    const range = detail || window.TmallDateRange?.getState?.() || {};
    const query = new URLSearchParams({
      start: range.startDate || `${state.period}-01`,
      end: range.endDate || `${state.period}-31`,
      group_by: groupBy,
    });
    [['channel', '[data-promotion-channel]'], ['campaign_id', '[data-promotion-campaign]'], ['unit_id', '[data-promotion-unit]'], ['product_id', '[data-promotion-product]']].forEach(([key, selector]) => {
      const value = $(selector)?.value.trim();
      if (value) query.set(key, value);
    });
    return query.toString();
  }

  function renderKpis(rows) {
    const summary = promotionMetrics.summarize(rows);
    [['spend', 'ad_spend', 'money'], ['gmv', 'attributed_payment_amount', 'money'],
      ['roi', 'roi', 'ratio'], ['expense_ratio', 'expense_ratio', 'percent'],
      ['ctr', 'ctr', 'percent'], ['cvr', 'cvr', 'percent'],
      ['direct', 'direct_payment_amount', 'money'], ['indirect', 'indirect_payment_amount', 'money']].forEach(([target, key, format]) => {
      $(`[data-promotion-kpi="${target}"]`).textContent = promotionMetrics.valueText(summary, key, format);
      const statusNode = $(`[data-promotion-kpi-status="${target}"]`);
      if (statusNode) {
        statusNode.textContent = promotionMetrics.statusLabel(summary, key);
        statusNode.hidden = !statusNode.textContent;
      }
    });
    $('[data-promotion-kpi="products"]').textContent = number(rows.length);
    $('[data-promotion-kpi-note]').textContent = `${state.period || '--'} 商品口径`;
    const fields = [['推广花费', 'ad_spend', 'money'], ['推广成交', 'attributed_payment_amount', 'money'], ['推广 ROI', 'roi', 'ratio'], ['费比', 'expense_ratio', 'percent'], ['点击率', 'ctr', 'percent'], ['商品支付转化率', 'cvr', 'percent'], ['直接付费成交', 'direct_payment_amount', 'money'], ['间接付费成交', 'indirect_payment_amount', 'money'], ['点击量', 'clicks', 'number'], ['展现量', 'impressions', 'number'], ['付费成交占比', 'paid_share', 'percent']];
    const issues = fields.filter(([, key]) => promotionMetrics.statusLabel(summary, key));
    const evidence = $('[data-promotion-quality]');
    if (evidence) {
      evidence.hidden = !issues.length;
      $('[data-promotion-quality-summary]').textContent = `${issues.length} 项指标需留意`;
      $('[data-promotion-quality-body]').textContent = issues.map(([label, key, kind]) => `${label}：${promotionMetrics.format(summary, key, kind)}`).join('\n');
    }
  }

  function renderCommandBoard(rows, alerts = []) {
    const list = Array.isArray(rows) ? rows : [];
    const quality = promotionMetrics.summarize(list);
    const roi = quality.roi;
    const cvr = quality.cvr;
    const paidShare = quality.paid_share;
    const badge = $('[data-promotion-health-badge]');
    const badgeText = badge?.querySelector('span');
    const insightTitle = $('[data-promotion-insight-title]');
    const insightCopy = $('[data-promotion-insight-copy]');
    const tone = roi == null ? 'muted' : roi >= 3 ? 'success' : roi >= 1.5 ? 'warning' : 'danger';
    const statusText = !list.length ? '暂无数据' : roi == null ? '数据未完整' : tone === 'success' ? '投产健康' : tone === 'warning' ? '需要关注' : '投产偏低';
    if (badge) {
      badge.dataset.tone = tone;
      badge.className = `promotion-command__status`;
      badge.dataset.tone = tone;
      const icon = tone === 'success' ? 'circle-check' : tone === 'warning' ? 'triangle-alert' : 'circle-alert';
      badge.innerHTML = `<i data-lucide="${icon}"></i><span>${statusText}</span>`;
    }
    const setValue = (key, value) => { const node = $(`[data-promotion-funnel="${key}"]`); if (node) node.textContent = value; };
    setValue('spend', promotionMetrics.valueText(quality, 'ad_spend', 'money'));
    setValue('clicks', promotionMetrics.valueText(quality, 'clicks', 'number'));
    setValue('gmv', promotionMetrics.valueText(quality, 'attributed_payment_amount', 'money'));
    [['spend', 'ad_spend'], ['clicks', 'clicks'], ['gmv', 'attributed_payment_amount']].forEach(([target, key]) => {
      const node = $(`[data-promotion-funnel-status="${target}"]`);
      if (node) { node.textContent = promotionMetrics.statusLabel(quality, key); node.hidden = !node.textContent; }
    });
    const clickMeta = $('[data-promotion-funnel-meta="clicks"]');
    const gmvMeta = $('[data-promotion-funnel-meta="gmv"]');
    if (clickMeta) clickMeta.textContent = `${promotionMetrics.compact(quality, 'impressions', 'number')} 次展现 · 点击率 ${promotionMetrics.compact(quality, 'ctr', 'percent')}`;
    if (gmvMeta) gmvMeta.textContent = `推广成交 · 推广 ROI ${promotionMetrics.compact(quality, 'roi', 'ratio')}`;
    const signals = {
      roi: promotionMetrics.valueText(quality, 'roi', 'ratio'),
      cvr: promotionMetrics.valueText(quality, 'cvr', 'percent'),
      paid_share: promotionMetrics.valueText(quality, 'paid_share', 'percent'),
      alerts: `${alerts.length} 条`,
    };
    Object.entries(signals).forEach(([key, value]) => { const node = $(`[data-promotion-signal="${key}"]`); if (node) node.textContent = value; });
    ['roi', 'cvr', 'paid_share'].forEach((key) => {
      const node = $(`[data-promotion-signal-status="${key}"]`);
      if (node) { node.textContent = promotionMetrics.statusLabel(quality, key); node.hidden = !node.textContent; }
    });
    const roiNode = $('[data-promotion-signal="roi"]');
    const cvrNode = $('[data-promotion-signal="cvr"]');
    const paidNode = $('[data-promotion-signal="paid_share"]');
    if (roiNode) roiNode.dataset.tone = tone;
    if (cvrNode) cvrNode.dataset.tone = cvr == null ? 'muted' : cvr >= .05 ? 'success' : cvr >= .025 ? 'warning' : 'danger';
    if (paidNode) paidNode.dataset.tone = paidShare == null ? 'muted' : paidShare >= .4 ? 'warning' : 'success';
    const alertNode = $('[data-promotion-signal="alerts"]');
    if (alertNode) alertNode.dataset.tone = alerts.length ? 'danger' : 'success';
    if (insightTitle && insightCopy) {
      if (!list.length) {
        insightTitle.textContent = '当前筛选范围暂无推广经营数据';
        insightCopy.textContent = '先导入对应日期的推广明细，再查看计划、商品和趋势判断。';
      } else if (roi == null) {
        insightTitle.textContent = '推广输入未完整，暂不判断投产高低';
        insightCopy.textContent = promotionMetrics.format(quality, 'roi', 'ratio');
      } else if (tone === 'success') {
        insightTitle.textContent = '整体投产达到健康区间，可继续观察高效计划';
        insightCopy.textContent = `当前推广 ROI ${roi.toFixed(2)}，优先关注计划与商品的效率差异，不把不同粒度重复相加。`;
      } else if (tone === 'warning') {
        insightTitle.textContent = '整体投产可用，但需要拆解低效计划';
        insightCopy.textContent = `当前推广 ROI ${roi.toFixed(2)}，建议先按计划定位花费集中处，再回到商品看推广依赖。`;
      } else {
        insightTitle.textContent = '整体投产偏低，先控制低效投入';
        insightCopy.textContent = `当前推广 ROI ${promotionMetrics.format(quality, 'roi', 'ratio')}，建议优先查看计划和商品明细中的低效项。`;
      }
    }
    window.lucide?.createIcons();
  }

  function renderSourceStatus(sourceBatches) {
    const demoBase = (sourceBatches || []).some((batch) => String(batch.source_filename || '').toLowerCase().startsWith('demo_'));
    const base = $('[data-promotion-source-base]');
    const note = $('[data-promotion-source-note]');
    if (base) {
      base.textContent = demoBase ? '演示：计划 + 商品（接口已接入）' : '真实：计划 + 商品';
      base.classList.toggle('promotion-source-strip__item--real', !demoBase);
      base.classList.toggle('promotion-source-strip__item--demo', demoBase);
    }
    if (note) note.textContent = demoBase
      ? '当前批次为演示种子数据；接口、计算和交互已接入，替换导入批次后自动切换。'
      : '演示数据只补齐页面能力，不参与 KPI、趋势和预警汇总。';
  }

  function renderProductBoard(rows) {
    const container = $('[data-promotion-product-board]');
    const count = $('[data-promotion-product-board-count]');
    if (!container) return;
    const visible = (rows || []).slice(0, 5);
    if (count) count.textContent = `${number(rows?.length || 0)} 个商品`;
    if (!visible.length) {
      container.innerHTML = '<div class="promotion-board-empty">当前范围没有商品推广数据</div>';
      return;
    }
    const table = TmallUI.table({
      caption: '商品推广榜',
      tableClass: 'promotion-board-table',
      tableControls: true,
      columns: [
        { key: 'product', label: '商品', render: (_value, row) => {
      const nameWrap = element('div', 'promotion-board-name');
      const nameCopy = element('div', 'promotion-board-name__copy');
      nameCopy.append(element('strong', '', text(row.title, productId(row) || '未关联商品')), element('span', '', text(productId(row), '无商品 ID')));
      nameWrap.append(productThumbnail(row), nameCopy);
          return nameWrap;
        } },
        ...[['ad_spend', '推广花费', 'money'], ['attributed_payment_amount', '推广成交', 'money'], ['link_net_sales', '链接净销售额', 'money'], ['expense_ratio', '费比', 'percent'], ['roi', '推广 ROI', 'ratio'], ['paid_share', '付费成交占比', 'percent']].map(([key, label, format]) => ({ key, label, numeric: true, render: (_value, row) => promotionMetrics.format(row, key, format) })),
      ],
      rows: visible,
    });
    container.replaceChildren(table);
  }

  function renderPlanBoard(rows) {
    const container = $('[data-promotion-plan-board]');
    const count = $('[data-promotion-plan-count]');
    if (!container) return;
    const visible = (rows || []).slice(0, 5);
    if (count) count.textContent = `${number(rows?.length || 0)} 个计划`;
    if (!visible.length) {
      container.innerHTML = '<div class="promotion-board-empty">当前范围没有计划推广数据</div>';
      return;
    }
    const table = TmallUI.table({
      caption: '计划推广榜',
      tableClass: 'promotion-board-table',
      tableControls: true,
      columns: [
        { key: 'campaign_id', label: '计划 / 渠道', render: (_value, row) => {
      const nameWrap = element('div', 'promotion-plan-name');
      nameWrap.append(element('strong', '', text(row.campaign_id, '未命名计划')), element('span', '', text(row.channel, '未命名渠道')));
          return nameWrap;
        } },
        ...[['ad_spend', '推广花费', 'money'], ['attributed_payment_amount', '推广成交', 'money'], ['roi', '推广 ROI', 'ratio'], ['ctr', '点击率', 'percent']].map(([key, label, format]) => ({ key, label, numeric: true, render: (_value, row) => promotionMetrics.format(row, key, format) })),
      ],
      rows: visible,
    });
    container.replaceChildren(table);
  }

  function destroyChart() {
    if (state.chart) {
      state.chart.destroy();
      state.chart = null;
    }
  }

  function renderTrend(rows) {
    destroyChart();
    const canvas = $('#promotionTrend');
    if (!canvas || !window.echarts || !window.EChartCompat) return;
    state.chart = new EChartCompat(canvas, {
      type: 'bar',
      data: {
        labels: rows.map((row) => row.period || row.date),
        datasets: [
          { type: 'bar', label: '推广花费', data: rows.map((row) => promotionMetrics.chartValue(row, 'ad_spend')), backgroundColor: getComputedStyle(document.documentElement).getPropertyValue('--chart-warning-fill').trim(), borderRadius: window.DemoCharts?.chartRadius?.() || 4, yAxisID: 'y' },
          { type: 'bar', label: '推广成交', data: rows.map((row) => promotionMetrics.chartValue(row, 'attributed_payment_amount')), backgroundColor: getComputedStyle(document.documentElement).getPropertyValue('--chart-info-fill').trim(), borderRadius: window.DemoCharts?.chartRadius?.() || 4, yAxisID: 'y' },
          { type: 'line', label: '推广 ROI', data: rows.map((row) => promotionMetrics.chartValue(row, 'roi')), borderColor: getComputedStyle(document.documentElement).getPropertyValue('--success').trim(), tension: .35, pointRadius: window.DemoCharts?.chartPointRadius?.() || 3, borderWidth: window.DemoCharts?.chartLineWidth?.() || 2, yAxisID: 'y1' }
        ]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { position: 'bottom', labels: { boxWidth: window.DemoCharts?.chartLegendBox?.() || 12 } } },
        scales: { x: { grid: { display: false } }, y: { beginAtZero: true }, y1: { position: 'right', grid: { drawOnChartArea: false }, beginAtZero: true } }
      }
    });
  }

  const PROMOTION_ALERT_PREVIEW_LIMIT = 5;

  function severityClass(severity) {
    return severity === 'danger' ? 'alert-list__item--danger' : '';
  }

  function createAlertItem(alert) {
    const item = element('div', `alert-list__item ${severityClass(alert.severity)}`.trim());
    const copy = element('div');
    copy.append(element('strong', '', text(alert.title, productId(alert) || '商品')), element('span', '', text(alert.message, '指标异常')));
    const button = element('button', 'ui-button ui-button--ghost', '查看商品');
    button.type = 'button';
    button.dataset.promotionDrill = productId(alert);
    button.addEventListener('click', () => openProductDetail(alert, button));
    item.append(copy, button);
    return item;
  }

  function renderAlertItems(container, rows, { emptyMessage = true } = {}) {
    container.replaceChildren();
    if (!rows.length) {
      if (!emptyMessage) return;
      const empty = element('div', 'ui-empty-state');
      empty.append(element('strong', '', '当前月份没有触发推广预警'), element('span', '', '预警由 API 按商品推广 ROI 与推广花费规则计算。'));
      container.appendChild(empty);
      return;
    }
    rows.forEach((alert) => container.appendChild(createAlertItem(alert)));
  }

  // 全部投放预警抽屉：modal-form__body 内的列表迁入抽屉 body，footer 晚挂载
  let promotionAlertsDrawer = null;

  function ensureAlertsDrawer() {
    if (promotionAlertsDrawer) return promotionAlertsDrawer;
    const template = $('[data-promotion-alert-dialog-template]');
    if (!template || !window.TmallUI?.detailDrawer) return null;
    promotionAlertsDrawer = window.TmallUI.detailDrawer({
      title: '全部投放预警',
      description: `${state.period || '--'} · 预警由 API 按商品推广 ROI 与推广花费规则计算`,
      size: 'md',
    });
    const content = template.content.cloneNode(true);
    const footerTemplate = content.querySelector('[data-promotion-alert-dialog-footer]');
    promotionAlertsDrawer.body.append(content);
    if (footerTemplate) promotionAlertsDrawer.ensureFooter().append(...footerTemplate.content.cloneNode(true).childNodes);
    promotionAlertsDrawer.node.querySelectorAll('[data-promotion-alert-dialog-close]').forEach((button) => button.addEventListener('click', closeAlertsDialog));
    window.lucide?.createIcons();
    return promotionAlertsDrawer;
  }

  function renderAlertDialog(rows) {
    const list = $('[data-promotion-alert-dialog-list]');
    const subtitle = promotionAlertsDrawer?.node.querySelector('.ui-drawer__copy p');
    if (!list) return;
    if (subtitle) subtitle.textContent = `${state.period || '--'} · 共 ${rows.length} 条投放预警`;
    renderAlertItems(list, rows);
  }

  function renderAlerts(rows) {
    const container = $('[data-promotion-alerts]');
    const count = $('[data-promotion-alert-count]');
    const moreButton = $('[data-promotion-alerts-more]');
    const alerts = Array.isArray(rows) ? rows : [];
    count.textContent = `${alerts.length} 条`;
    renderAlertItems(container, alerts.slice(0, PROMOTION_ALERT_PREVIEW_LIMIT));
    if (moreButton) {
      moreButton.hidden = alerts.length <= PROMOTION_ALERT_PREVIEW_LIMIT;
      moreButton.textContent = `查看全部 ${alerts.length} 条`;
    }
    const dialog = promotionAlertsDrawer?.node;
    if (dialog?.classList.contains('is-open')) renderAlertDialog(alerts);
  }

  function clearTable(message) {
    const root = $('[data-promotion-table-root]');
    if (!root) return;
    root.replaceChildren(promotionTable({
      caption: '推广数据',
      tableClass: 'promotion-table',
      columns: [{ key: 'message', label: '状态' }],
      rows: [],
      emptyMessage: message,
    }));
  }

  function activeDefinition(tab = state.activeTab) {
    return tabDefinitions[tab] || tabDefinitions.products;
  }

  function allTemplates(tab = state.activeTab) {
    return [...activeDefinition(tab).templates, ...(state.customTemplates[tab] || [])];
  }

  function normalizeTemplateFields(tab, fields) {
    const allowed = new Set((tabDefinitions[tab]?.columns || []).map((column) => column.key));
    return [...new Set((Array.isArray(fields) ? fields : []).filter((key) => allowed.has(key)))];
  }

  function selectedColumns(tab = state.activeTab) {
    const definition = activeDefinition(tab);
    const selected = normalizeTemplateFields(tab, state.selectedFields[tab] || definition.templates[0].fields);
    return selected.map((key) => definition.columns.find((column) => column.key === key)).filter(Boolean);
  }

  function formatField(value, format) {
    if (format === 'money') return money(value);
    if (format === 'moneyNullable') return value == null || value === '' ? '--' : money(value);
    if (format === 'number') return number(value);
    if (format === 'numberNullable') return numberNullable(value);
    if (format === 'percent') return value == null || value === '' ? '--' : `${(Number(value || 0) * 100).toFixed(2)}%`;
    if (format === 'ratio') return ratio(value);
    return text(value);
  }

  function productLabel(row) {
    return productTitle(row);
  }

  function fieldValue(row, column, tab) {
    if (column.key === 'product') return productLabel(row);
    if (column.key === 'action') return '';
    if (tab === 'products') return row[column.key];
    return row[column.key];
  }

  function productThumbnail(row) {
    const product = productId(row);
    const source = String(row?.image_url || '').trim();
    if (source) {
      const image = document.createElement('img');
      image.className = 'product-thumb';
      image.alt = `${productTitle(row)}主图`;
      image.loading = 'lazy';
      image.referrerPolicy = 'no-referrer';
      image.src = source;
      image.addEventListener('error', () => image.replaceWith(productThumbnailPlaceholder(row)), { once: true });
      return image;
    }
    return productThumbnailPlaceholder(row);
  }

  function productThumbnailPlaceholder(row) {
    const placeholder = element('span', 'product-thumb product-thumb--placeholder', productTitle(row).slice(0, 1) || '商');
    placeholder.setAttribute('aria-hidden', 'true');
    return placeholder;
  }

  function renderTemplateSelect() {
    const select = $('[data-promotion-template-select]');
    if (!select) return;
    const templates = [...allTemplates()];
    if (state.activeTemplate[state.activeTab] === 'custom') templates.unshift({ id: 'custom', name: '临时自定义', fields: state.selectedFields[state.activeTab] });
    select.replaceChildren(...templates.map((template) => {
      const option = document.createElement('option');
      option.value = template.id;
      option.textContent = template.name;
      return option;
    }));
    select.value = state.activeTemplate[state.activeTab] || templates[0]?.id || '';
    $('[data-promotion-active-template]').textContent = templates.find((template) => template.id === select.value)?.name || '自定义';
  }

  function renderSavedTemplates() {
    const root = $('[data-promotion-saved-templates]');
    if (!root) return;
    const templates = state.customTemplates[state.dialogTab] || [];
    root.replaceChildren();
    if (!templates.length) {
      root.appendChild(element('span', 'panel__hint', '当前 TAB 暂无自定义模板'));
      return;
    }
    templates.forEach((template) => {
      const pill = element('span', 'template-pill');
      const use = element('button', '', template.name);
      use.type = 'button';
      use.dataset.promotionUseTemplate = template.id;
      const remove = element('button');
      remove.type = 'button';
      remove.dataset.promotionDeleteTemplate = template.id;
      remove.setAttribute('aria-label', `删除模板 ${template.name}`);
      remove.title = `删除模板 ${template.name}`;
      const icon = document.createElement('i');
      icon.dataset.lucide = 'x';
      remove.appendChild(icon);
      pill.append(use, remove);
      root.appendChild(pill);
    });
    window.lucide?.createIcons();
  }

  function applyTemplate(templateId) {
    const template = allTemplates().find((item) => item.id === templateId);
    if (!template) return;
    state.selectedFields[state.activeTab] = normalizeTemplateFields(state.activeTab, template.fields);
    state.activeTemplate[state.activeTab] = template.id;
    saveFieldPreferences();
    renderTemplateSelect();
    renderActiveTable();
  }

  function promotionTemplatesPayload() {
    return Object.fromEntries(Object.entries(tabDefinitions).map(([tab]) => {
      const serverTemplates = state.settings?.promotion_view_templates?.[tab] || {};
      const builtinTemplates = Object.fromEntries((tabDefinitions[tab].templates || [])
        .map((template) => [template.id, { label: template.name, columns: normalizeTemplateFields(tab, template.fields) }]));
      const persistedBuiltinTemplates = Object.fromEntries(Object.entries(serverTemplates)
        .filter(([id, template]) => promotionBuiltinTemplateIds.has(id) && normalizeTemplateFields(tab, template?.columns).length)
        .map(([id, template]) => [id, { label: template.label, columns: normalizeTemplateFields(tab, template.columns) }]));
      const customTemplates = Object.fromEntries((state.customTemplates[tab] || [])
        .map((template) => [template, normalizeTemplateFields(tab, template.fields)])
        .filter(([template, fields]) => !promotionBuiltinTemplateIds.has(template.id) && fields.length)
        .map(([template, fields]) => [template.id, { label: template.name, columns: fields }]));
      return [tab, { ...persistedBuiltinTemplates, ...builtinTemplates, ...customTemplates }];
    }));
  }

  function ingestServerTemplates(settings) {
    state.settings = settings;
    Object.entries(tabDefinitions).forEach(([tab, definition]) => {
      const builtinIds = new Set(definition.templates.map((template) => template.id));
      const serverTemplates = settings?.promotion_view_templates?.[tab] || {};
      definition.templates.forEach((template) => {
        const persisted = serverTemplates[template.id];
        if (!persisted || !Array.isArray(persisted.columns)) return;
        const fields = normalizeTemplateFields(tab, persisted.columns);
        if (!fields.length) return;
        template.name = persisted.label || template.name;
        template.fields = fields;
      });
      state.customTemplates[tab] = Object.entries(settings?.promotion_view_templates?.[tab] || {})
        .filter(([id]) => !builtinIds.has(id))
        .map(([id, template]) => ({ id, name: template.label || id, fields: normalizeTemplateFields(tab, template.columns) }))
        .filter((template) => template.fields.length);
    });
  }

  function restoreActiveTemplatesFromPreferences() {
    Object.keys(tabDefinitions).forEach((tab) => {
      if (state.activeTemplate[tab] !== 'custom') return;
      const preferred = storedFieldPreferences.activeTemplate?.[tab];
      if (!preferred || !allTemplates(tab).some((template) => template.id === preferred)) return;
      state.activeTemplate[tab] = preferred;
    });
  }

  async function saveTemplates() {
    const response = await DemoApi.domainRequest('/api/settings', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ promotion_view_templates: promotionTemplatesPayload() }),
    });
    ingestServerTemplates(response.data);
    try { localStorage.removeItem(storageKey); } catch (_) {}
  }

  async function loadServerTemplates() {
    const legacy = structuredClone(state.customTemplates || {});
    const response = await DemoApi.domainRequest('/api/settings');
    ingestServerTemplates(response.data);
    restoreActiveTemplatesFromPreferences();
    let migrated = false;
    Object.entries(legacy).forEach(([tab, templates]) => {
      if (!tabDefinitions[tab] || !Array.isArray(templates)) return;
      const known = new Set(allTemplates(tab).map((template) => template.id));
      templates.forEach((template) => {
        if (!template?.id || known.has(template.id) || !Array.isArray(template.fields)) return;
        const fields = normalizeTemplateFields(tab, template.fields);
        if (!fields.length) return;
        state.customTemplates[tab].push({ ...template, fields });
        known.add(template.id);
        migrated = true;
      });
    });
    if (migrated) await saveTemplates();
  }

  function saveFieldPreferences() {
    try {
      localStorage.setItem(fieldPreferenceStorageKey, JSON.stringify({
        selectedFields: state.selectedFields,
        activeTemplate: state.activeTemplate,
      }));
    } catch (_) {}
  }

  function selectedDialogFields() {
    return fieldSelector?.getSelected() || [];
  }

  function updateFieldDialogStatus() {
    const selected = selectedDialogFields();
    $('[data-promotion-field-selection-count]').textContent = `${selected.length} 个字段`;
    $('[data-promotion-fields-apply]').disabled = selected.length === 0;
    $('[data-promotion-template-save]').disabled = selected.length === 0;
    $('[data-promotion-field-status]').textContent = selected.length ? '' : '至少保留一个字段';
  }

  function renderFieldOptions(selected = state.selectedFields[state.dialogTab]) {
    const definition = activeDefinition(state.dialogTab);
    const groups = [...new Set(definition.columns.map((column) => column.group || '字段'))].map((group) => ({
      label: group,
      fields: definition.columns.filter((column) => (column.group || '字段') === group),
    }));
    const config = { groups, selected };
    if (!fieldSelector) {
      fieldSelector = TmallUI.fieldSelector({
        root: $('[data-promotion-field-selector]'),
        ...config,
        availableTitleId: 'promotionAvailableFieldsTitle',
        previewTitleId: 'promotionFieldPreviewTitle',
        availableHint: '勾选当前 TAB 的字段',
        optionDataAttribute: 'data-promotion-field-key',
        previewDataAttribute: 'data-promotion-preview-key',
        onChange: updateFieldDialogStatus,
      });
    } else {
      fieldSelector.setConfig(config);
    }
    const tabTemplates = Object.fromEntries(allTemplates(state.dialogTab).map((template) => [template.id, {
      label: template.name,
      columns: [...template.fields],
    }]));
    if (!templateManager && window.DemoFieldTemplateManager) {
      templateManager = DemoFieldTemplateManager.create({
        root: $('[data-promotion-template-manager]'),
        builtinKeys: tabDefinitions[state.dialogTab].templates.map((template) => template.id),
        templates: tabTemplates,
        onChange: (event) => {
          if (event.type === 'use') {
            applyTemplate(event.key);
            renderFieldOptions(state.selectedFields[state.dialogTab]);
          }
        },
        onSave: (key, label) => updatePromotionTemplate(key, label),
        onDelete: (key) => deletePromotionTemplate(key),
      });
    }
    templateManager?.setBuiltinKeys(tabDefinitions[state.dialogTab].templates.map((template) => template.id));
    templateManager?.setTemplates(tabTemplates);
    $('[data-promotion-field-dialog-scope]').textContent = `${definition.label}字段`;
    updateFieldDialogStatus();
  }

  function selectAllFields() {
    fieldSelector?.selectAll();
  }

  function clearAllFields() {
    fieldSelector?.clear();
  }

  async function saveCustomTemplate() {
    const nameInput = $('[data-promotion-template-name]');
    const saveButton = $('[data-promotion-template-save]');
    if (saveButton?.disabled) return;
    const name = nameInput.value.trim();
    const fields = selectedDialogFields();
    if (!name) {
      $('[data-promotion-field-status]').textContent = '请输入模板名称';
      nameInput.focus();
      return;
    }
    if (!fields.length) return;
    const tab = state.dialogTab;
    if (allTemplates(tab).some((template) => template.name === name)) {
      $('[data-promotion-field-status]').textContent = '当前 TAB 已存在同名模板';
      return;
    }
    const previousSelectedFields = [...(state.selectedFields[tab] || [])];
    const previousActiveTemplate = state.activeTemplate[tab];
    const template = { id: `${tab}-custom-${Date.now()}`, name, fields };
    state.customTemplates[tab] = [...(state.customTemplates[tab] || []), template];
    state.selectedFields[tab] = fields;
    state.activeTemplate[tab] = template.id;
    $('[data-promotion-field-status]').textContent = '正在保存模板';
    if (saveButton) { saveButton.disabled = true; saveButton.setAttribute('aria-busy', 'true'); }
    try {
      await saveTemplates();
      saveFieldPreferences();
      nameInput.value = '';
      renderTemplateSelect();
      renderSavedTemplates();
      renderActiveTable();
      $('[data-promotion-field-status]').textContent = `模板“${name}”已保存`;
    } catch (error) {
      state.customTemplates[tab] = state.customTemplates[tab].filter((item) => item.id !== template.id);
      state.selectedFields[tab] = previousSelectedFields;
      state.activeTemplate[tab] = previousActiveTemplate;
      renderFieldOptions(previousSelectedFields);
      renderTemplateSelect();
      renderSavedTemplates();
      $('[data-promotion-field-status]').textContent = error.message || '模板保存失败';
    } finally {
      if (saveButton) { saveButton.disabled = false; saveButton.removeAttribute('aria-busy'); }
    }
  }

  async function updatePromotionTemplate(key, label) {
    const fields = selectedDialogFields();
    const template = allTemplates(state.dialogTab).find((item) => item.id === key);
    if (!template || !fields.length) return;
    const tab = state.dialogTab;
    const previous = {
      name: template.name,
      fields: [...template.fields],
      selectedFields: [...(state.selectedFields[tab] || [])],
      activeTemplate: state.activeTemplate[tab],
    };
    const actionButton = document.querySelector(`[data-field-template-save="${CSS.escape(key)}"]`);
    if (actionButton?.disabled) return;
    if (actionButton) { actionButton.disabled = true; actionButton.setAttribute('aria-busy', 'true'); }
    template.name = label;
    template.fields = [...fields];
    state.selectedFields[tab] = [...fields];
    state.activeTemplate[tab] = key;
    try {
      await saveTemplates();
      saveFieldPreferences();
      renderTemplateSelect();
      renderSavedTemplates();
      renderFieldOptions(fields);
      $('[data-promotion-field-status]').textContent = `模板“${label}”已更新`;
    } catch (error) {
      template.name = previous.name;
      template.fields = previous.fields;
      state.selectedFields[tab] = previous.selectedFields;
      state.activeTemplate[tab] = previous.activeTemplate;
      renderFieldOptions(previous.selectedFields);
      renderTemplateSelect();
      renderSavedTemplates();
      $('[data-promotion-field-status]').textContent = error.message || '模板更新失败';
    } finally {
      if (actionButton) { actionButton.disabled = false; actionButton.removeAttribute('aria-busy'); }
    }
  }

  async function deletePromotionTemplate(key) {
    const tab = state.dialogTab;
    if (promotionBuiltinTemplateIds.has(key)) return;
    const previous = [...(state.customTemplates[tab] || [])];
    const previousSelectedFields = [...(state.selectedFields[tab] || [])];
    const previousActiveTemplate = state.activeTemplate[tab];
    const actionButtons = [...document.querySelectorAll(`[data-field-template-delete="${CSS.escape(key)}"], [data-promotion-delete-template="${CSS.escape(key)}"]`)];
    if (actionButtons.some((button) => button.disabled)) return;
    state.customTemplates[tab] = previous.filter((item) => item.id !== key);
    if (state.activeTemplate[tab] === key) {
      state.activeTemplate[tab] = tabDefinitions[tab].templates[0]?.id || 'custom';
      state.selectedFields[tab] = [...(tabDefinitions[tab].templates[0]?.fields || [])];
    }
    actionButtons.forEach((button) => { button.disabled = true; button.setAttribute('aria-busy', 'true'); });
    try {
      await saveTemplates();
      saveFieldPreferences();
      renderFieldOptions(state.selectedFields[tab]);
      renderTemplateSelect();
      renderSavedTemplates();
      $('[data-promotion-field-status]').textContent = '模板已删除';
    } catch (error) {
      state.customTemplates[tab] = previous;
      state.selectedFields[tab] = previousSelectedFields;
      state.activeTemplate[tab] = previousActiveTemplate;
      renderFieldOptions(previousSelectedFields);
      renderTemplateSelect();
      renderSavedTemplates();
      $('[data-promotion-field-status]').textContent = error.message || '模板删除失败';
    } finally {
      actionButtons.forEach((button) => { button.disabled = false; button.removeAttribute('aria-busy'); });
    }
  }

  function renderFieldRows(tab, rows) {
    const columns = selectedColumns(tab);
    $('[data-promotion-visible-field-count]').textContent = `${columns.length} 个字段`;
    const root = $('[data-promotion-table-root]');
    if (!root) return;
    root.replaceChildren(promotionTable({
      caption: activeDefinition(tab).title,
      tableClass: 'promotion-table',
      columns: columns.map((column) => ({
        key: column.key,
        label: column.label,
        numeric: Boolean(column.format),
        className: column.format ? 'promotion-metric-cell' : '',
        render: (_value, row) => {
          if (column.key === 'product') return TmallUI.productIdentity({
            title: productTitle(row), id: productId(row), imageUrl: row.image_url,
            className: 'promotion-product-identity',
          });
          if (column.key === 'action') {
            const button = element('button', 'ui-button ui-button--ghost', '明细');
            button.type = 'button';
            button.dataset.promotionDrill = productId(row);
            button.addEventListener('click', () => openPromotionDetail(row, button));
            return button;
          }
          const value = column.format
            ? promotionMetrics.compact(row, column.key, column.format)
            : formatField(fieldValue(row, column, tab), column.format);
          const title = column.format ? promotionMetrics.compactTitle(row, column.key, column.format) : '';
          if (!title) return value;
          const metricNode = element('span', `promotion-metric-cell promotion-metric-cell--${row.metric_availability?.[column.key] || 'partial'}`, value);
          metricNode.title = title;
          return metricNode;
        },
      })),
      rows,
      emptyMessage: `${activeDefinition(tab).empty} 可调整日期范围，或先导入对应月度报表。`,
    }));
  }

  function renderProducts() {
    renderFieldRows('products', state.rows);
  }

  function renderAggregate(type) {
    const rows = Array.isArray(state.breakdowns[type]?.rows) ? state.breakdowns[type].rows : [];
    renderFieldRows(type, rows);
  }

  function renderUnavailable() {
    const root = $('[data-promotion-table-root]');
    if (!root) return;
    root.replaceChildren(promotionTable({
      caption: '未提供归因',
      tableClass: 'promotion-table',
      columns: [{ key: 'availability', label: '可用性说明' }],
      rows: [],
      emptyMessage: '当前数据库未提供计划、创意、地域或内容归因。页面不会用商品或渠道数据伪造这些层级。导入对应明细后再开放相关分析。',
    }));
  }

  function renderActiveTable() {
    const unavailable = state.activeTab === 'unavailable';
    const demo = state.demoTabs.has(state.activeTab);
    const definition = unavailable
      ? { title: '未提供归因', hint: '该数据源暂未提供计划、创意、地域、内容层级的可验证关联。' }
      : activeDefinition();
    const compactHint = unavailable
      ? '\u5f53\u524d\u6682\u65e0\u53ef\u9a8c\u8bc1\u7684\u5f52\u56e0\u5173\u8054\u3002'
      : ({
        products: '\u6309\u5546\u54c1 ID \u6c47\u603b\uff0c\u53ef\u4e0e\u5546\u54c1\u8fd0\u8425\u4ea4\u53c9\u6838\u5bf9\u3002',
        keywords: '\u5546\u54c1\u6708\u5ea6\u5173\u952e\u8bcd\u6c47\u603b\uff0c\u4e0d\u4ee3\u8868\u8bcd\u7ea7\u660e\u7ec6\u3002',
        crowd: '\u5546\u54c1\u6708\u5ea6\u4eba\u7fa4\u6c47\u603b\uff0c\u4e0d\u4ee3\u8868\u4eba\u7fa4\u5305\u660e\u7ec6\u3002',
        creative: '\u5f53\u524d\u4e3a\u6f14\u793a\u521b\u610f\u6c47\u603b\uff0c\u4e0d\u4ee3\u8868\u521b\u610f ID \u660e\u7ec6\u3002',
        site: '\u5546\u54c1\u6708\u5ea6\u7ad9\u5185\u6e20\u9053\u6c47\u603b\uff0c\u4e0d\u4ee3\u8868\u8d44\u6e90\u4f4d\u660e\u7ec6\u3002',
      }[state.activeTab] || definition.hint);
    $('[data-promotion-table-title]').textContent = demo ? `${definition.title} · 演示` : definition.title;
    $('[data-promotion-table-hint]').textContent = demo ? `演示数据：${definition.hint}，不参与 KPI、趋势和预警汇总。` : definition.hint;
    $('[data-promotion-grain]').textContent = demo ? `演示数据：${definition.hint}，不参与总盘汇总。` : definition.hint;
    const compactHintText = demo ? `\u6f14\u793a\u6570\u636e\uff1a${compactHint}` : compactHint;
    $('[data-promotion-table-hint]').textContent = compactHintText;
    $('[data-promotion-grain]').textContent = compactHintText;
    const rows = state.activeTab === 'products' ? state.rows : (state.breakdowns[state.activeTab]?.rows || []);
    $('[data-promotion-row-count]').textContent = unavailable ? '不可用' : `${demo ? '演示 ' : ''}${number(rows.length)} 个商品`;
    const mode = $('[data-promotion-data-mode]');
    if (mode) mode.hidden = !demo;
    $('[data-promotion-template-bar]').hidden = unavailable;
    if (state.activeTab === 'products') renderProducts();
    else if (state.activeTab === 'unavailable') renderUnavailable();
    else renderAggregate(state.activeTab);
    if (!unavailable) renderTemplateSelect();
  }

  function renderDrilldown(rows, level) {
    const labels = {channel:'渠道', campaign:'计划', unit:'单元', product:'商品'};
    $('[data-promotion-table-title]').textContent = `${labels[level]}下钻`;
    $('[data-promotion-table-hint]').textContent = '只展示已导入的同粒度推广事实；推广 ROI、点击率均按汇总后计算。';
    $('[data-promotion-grain]').textContent = $('[data-promotion-table-hint]').textContent;
    const drillHint = '\u5df2\u5bfc\u5165\u4e8b\u5b9e\u6c47\u603b\uff0c\u63a8\u5e7f ROI / \u70b9\u51fb\u7387 \u6309\u6c47\u603b\u540e\u8ba1\u7b97\u3002';
    $('[data-promotion-table-hint]').textContent = drillHint;
    $('[data-promotion-grain]').textContent = drillHint;
    const root = $('[data-promotion-table-root]');
    if (!root) return;
    const metricColumns = [
      ['ad_spend', '推广花费', 'money'], ['attributed_payment_amount', '推广成交', 'money'],
      ['direct_payment_amount', '直接付费成交', 'money'], ['indirect_payment_amount', '间接付费成交', 'money'],
      ['paid_share', '付费成交占比', 'percent'], ['roi', '推广 ROI', 'ratio'],
      ['ctr', '点击率', 'percent'], ['cvr', '商品支付转化率', 'percent'], ['cpc', '平均点击花费', 'money'],
    ];
    root.replaceChildren(promotionTable({
      caption: `${labels[level]}下钻`,
      tableClass: 'promotion-table promotion-drill-table',
      columns: [
        { key: 'identifier', label: labels[level], render: (_value, row) => {
          const identifier = level === 'channel' ? row.channel : level === 'campaign' ? `${row.channel} / ${row.campaign_id}` : level === 'unit' ? `${row.channel} / ${row.campaign_id} / ${row.unit_id}` : `${row.channel} / ${row.product_id}`;
          if (level !== 'product') return identifier;
          const button = element('button', 'promotion-drill-link', identifier);
          button.type = 'button';
          button.title = '打开推广明细';
          button.addEventListener('click', () => openPromotionDetail(row, button));
          return button;
        } },
        ...metricColumns.map(([key, label, format]) => ({ key, label, numeric: true, render: (_value, row) => promotionMetrics.format(row, key, format) })),
      ],
      rows,
      emptyMessage: '该筛选范围未导入对应粒度推广数据',
    }));
  }
  async function loadDrilldown() {
    const level = $('[data-promotion-drill-level]').value; const range = window.TmallDateRange?.getState?.() || {};
    if (Object.keys(state.capabilities).length && !DemoApi.can({ capabilities: state.capabilities }, 'can_drilldown')) return toast('当前数据不可下钻');
    if (!state.availableGrains.includes(level)) return toast('当前数据未导入该下钻粒度');
    const query = new URLSearchParams({start:range.startDate || `${state.period}-01`, end:range.endDate || `${state.period}-31`, group_by:level});
    [['channel','[data-promotion-channel]'],['campaign_id','[data-promotion-campaign]'],['unit_id','[data-promotion-unit]'],['product_id','[data-promotion-product]']].forEach(([key, selector]) => { const value = $(selector).value.trim(); if (value) query.set(key, value); });
    try { const response = await DemoApi.domainRequest(`/api/promotion?${query}`); renderDrilldown(Array.isArray(response.data?.rows) ? response.data.rows : [], level); } catch(error) { clearTable(error.message || '推广下钻加载失败'); }
  }

  function metric(label, value) {
    const item = element('div', 'detail-metric');
    item.append(element('span', '', label), element('strong', '', value));
    return item;
  }

  function promotionDetailQuery(row) {
    const range = window.TmallDateRange?.getState?.() || {};
    const query = new URLSearchParams({
      start: range.startDate || `${state.period}-01`,
      end: range.endDate || `${state.period}-31`,
      group_by: 'unit',
      product_id: productId(row),
    });
    return query.toString();
  }

  function updatePromotionDetailTabState(focus = false) {
    const tabs = [...document.querySelectorAll('[data-promotion-detail-tab]')];
    tabs.forEach((button) => {
      const active = button.dataset.promotionDetailTab === state.promotionDetailTab;
      button.setAttribute('aria-selected', String(active));
      button.tabIndex = active ? 0 : -1;
      if (active && focus) button.focus();
    });
    document.querySelectorAll('[data-promotion-detail-panel]').forEach((panel) => {
      panel.hidden = panel.dataset.promotionDetailPanel !== state.promotionDetailTab;
    });
  }

  function selectPromotionDetailTab(tab, focus = false) {
    if (!promotionDetailTabs.includes(tab)) return;
    state.promotionDetailTab = tab;
    updatePromotionDetailTabState(focus);
  }

  function renderPromotionDialogImage(product, icon = 'megaphone') {
    const imageRoot = $('[data-promotion-dialog-image]');
    if (!imageRoot) return;    imageRoot.replaceChildren();
    const thumbnailUrl = String(product?.image_url || '').trim();
    if (thumbnailUrl) {
      const image = new Image(52, 52);
      image.loading = 'lazy';
      image.src = thumbnailUrl;
      image.alt = productTitle(product) || '';
      imageRoot.removeAttribute('aria-hidden');
      image.addEventListener('error', () => {
        imageRoot.replaceChildren();
        imageRoot.setAttribute('aria-hidden', 'true');
        const placeholder = element('i');
        placeholder.setAttribute('data-lucide', icon);
        imageRoot.appendChild(placeholder);
        window.lucide?.createIcons();
      }, { once: true });
      imageRoot.appendChild(image);
      return;
    }
    imageRoot.setAttribute('aria-hidden', 'true');
    const placeholder = element('i');
    placeholder.setAttribute('data-lucide', icon);
    imageRoot.appendChild(placeholder);
  }

  function renderPromotionDetail(product, units, sourceState = 'available') {
    const body = $('[data-promotion-dialog-body]');
    const tabs = $('[data-promotion-dialog-tabs]');
    state.promotionDetailProduct = product;
    state.promotionDetailUnits = units;
    state.promotionDetailSource = sourceState;
    body.replaceChildren();
    tabs.hidden = sourceState !== 'available';
    if (sourceState !== 'available') {
      body.append(element('div', 'ui-empty-state', sourceState === 'loading' ? '正在加载推广明细…' : '推广明细加载失败，请稍后重试。'));
      return;
    }

    const overview = element('section', 'lifecycle-detail-panel promotion-detail-dialog__panel');
    overview.id = 'promotion-detail-panel-overview';
    overview.dataset.promotionDetailPanel = 'overview';
    overview.setAttribute('role', 'tabpanel');
    overview.setAttribute('aria-labelledby', 'promotion-detail-tab-overview');
    overview.tabIndex = 0;

    const summary = element('section', 'ui-panel promotion-detail-summary');
    const summaryHeader = element('div', 'panel__header');
    const summaryCopy = element('div');
    summaryCopy.append(element('h3', 'panel__title', '推广经营汇总'), element('p', 'promotion-detail-note', `${productTitle(product)} · ${state.period || '--'} 数据范围`));
    summaryHeader.appendChild(summaryCopy);
    summary.appendChild(summaryHeader);
    const metrics = element('div', 'detail-metrics promotion-detail-metrics');
    metrics.append(
      metric('推广花费', promotionMetrics.format(product, 'ad_spend', 'money')),
      metric('推广成交', promotionMetrics.format(product, 'attributed_payment_amount', 'money')),
      metric('链接净销售额', promotionMetrics.format(product, 'link_net_sales', 'money')),
      metric('费比', promotionMetrics.format(product, 'expense_ratio', 'percent')),
      metric('推广 ROI', promotionMetrics.format(product, 'roi', 'ratio')),
      metric('点击率 / 商品支付转化率', `${promotionMetrics.format(product, 'ctr', 'percent')} / ${promotionMetrics.format(product, 'cvr', 'percent')}`),
      metric('直接付费成交', promotionMetrics.format(product, 'direct_payment_amount', 'money')),
      metric('间接付费成交', promotionMetrics.format(product, 'indirect_payment_amount', 'money')),
    );
    summary.appendChild(metrics);

    const attribution = element('section', 'ui-panel');
    attribution.append(element('h3', 'panel__title', '归因构成'), element('p', 'promotion-detail-note', '推广成交按当前导入事实汇总，未提供的计划字段不会补造。'));
    const attributionList = element('div', 'status-list');
    [
      ['商品 ID', productId(product) || '未关联'],
      ['付费成交占比', promotionMetrics.format(product, 'paid_share', 'percent')],
      ['关联投放单元', `${units.length} 个`],
    ].forEach(([label, value]) => {
      const item = element('div', 'status-list__item');
      item.append(element('span', 'status-list__label', label), element('span', 'status-list__value', value));
      attributionList.appendChild(item);
    });
    attribution.appendChild(attributionList);
    overview.append(summary, attribution);

    const unitsPanel = element('section', 'lifecycle-detail-panel promotion-detail-dialog__panel');
    unitsPanel.id = 'promotion-detail-panel-units';
    unitsPanel.dataset.promotionDetailPanel = 'units';
    unitsPanel.setAttribute('role', 'tabpanel');
    unitsPanel.setAttribute('aria-labelledby', 'promotion-detail-tab-units');
    unitsPanel.tabIndex = 0;
    const detail = element('section', 'ui-panel');
    detail.append(element('h3', 'panel__title', '计划 / 单元明细'), element('p', 'promotion-detail-note', '按计划和单元粒度展示，不与上方商品汇总重复相加。'));
    const wrap = element('div', 'promotion-detail-table-wrap');
    if (!units.length) {
      wrap.appendChild(element('div', 'ui-empty-state', '当前商品没有可用的计划 / 单元明细。'));
    } else {
      const table = TmallUI.table({
        caption: '计划 / 单元明细',
        tableClass: 'promotion-detail-table',
        tableControls: true,
        columns: [
          { key: 'campaign_id', label: '计划 / 单元', render: (_value, unit) => {
        const identityWrap = element('div', 'promotion-detail-table__name');
        identityWrap.append(
          element('strong', '', `${text(unit.campaign_id, '未命名计划')} / ${text(unit.unit_id, '未命名单元')}`),
          element('span', '', text(unit.channel, '未命名渠道')),
        );
            return identityWrap;
          } },
          ...[['ad_spend', '推广花费', 'money'], ['attributed_payment_amount', '推广成交', 'money'], ['roi', '推广 ROI', 'ratio'], ['ctr', '点击率', 'percent'], ['cvr', '商品支付转化率', 'percent'], ['cpc', '平均点击花费', 'money']].map(([key, label, format]) => ({ key, label, numeric: true, render: (_value, unit) => promotionMetrics.format(unit, key, format) })),
        ],
        rows: units,
      });
      wrap.appendChild(table);
    }
    detail.appendChild(wrap);
    unitsPanel.appendChild(detail);
    body.append(overview, unitsPanel);
    updatePromotionDetailTabState();
  }

  // 详情面统一 NUI 抽屉：dialog 壳仅作内容来源，初始化时搬移进抽屉；
  // 头部（图片/标题/副标题/商品 ID）并入 body 顶部以承载动态填充。
  let promotionDetailDrawer = null;

  function ensurePromotionDetailDrawer() {
    if (promotionDetailDrawer) return promotionDetailDrawer;
    const template = $('[data-promotion-dialog-template]');
    if (!template || !window.TmallUI?.detailDrawer) return null;
    const header = document.createElement('div');
    header.className = 'lifecycle-detail__header promotion-detail-drawer__header';
    header.innerHTML = '<div class="lifecycle-detail__product"><span class="lifecycle-detail__image promotion-detail-dialog__image" data-promotion-dialog-image aria-hidden="true"><i data-lucide="megaphone"></i></span><div><h2 class="panel__title" data-promotion-dialog-title>推广明细</h2><p class="panel__hint" data-promotion-dialog-subtitle>--</p><div class="lifecycle-detail__id" data-promotion-dialog-id>--</div></div></div>';
    const content = template.content.cloneNode(true);
    // tablist 必须在 append 之前取：DocumentFragment 一旦被 append，子节点会被移走，
    // 之后再 querySelector 只会得到 null（曾导致 bindDialog 抛错、页面后续初始化全部中断）。
    const tablist = content.querySelector('[data-promotion-dialog-tabs]');
    const bodyWrap = document.createElement('div');
    bodyWrap.append(header, content);
    promotionDetailDrawer = window.TmallUI.detailDrawer({ title: '推广明细', size: 'lg' });
    promotionDetailDrawer.body.append(bodyWrap);
    tablist?.addEventListener('click', (event) => {
      const tab = event.target.closest('[data-promotion-detail-tab]');
      if (tab) selectPromotionDetailTab(tab.dataset.promotionDetailTab);
    });
    tablist?.addEventListener('keydown', (event) => {
      const tabs = [...tablist.querySelectorAll('[data-promotion-detail-tab]')];
      const index = tabs.indexOf(event.target.closest('[data-promotion-detail-tab]'));
      if (index < 0 || !['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
      event.preventDefault();
      const nextIndex = event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1 : (index + (event.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length;
      selectPromotionDetailTab(tabs[nextIndex].dataset.promotionDetailTab, true);
    });
    window.lucide?.createIcons();
    return promotionDetailDrawer;
  }

  async function openPromotionDetail(row, trigger) {
    const requestToken = ++state.promotionDetailRequest;
    const product = state.rows.find((item) => productId(item) === productId(row)) || row;
    state.promotionDetailTab = 'overview';
    if (!ensurePromotionDetailDrawerOpen(trigger)) return;
    $('[data-promotion-dialog-title]').textContent = productTitle(product) || '推广明细';
    $('[data-promotion-dialog-subtitle]').textContent = `推广明细 · ${state.period || '--'} 数据范围`;
    $('[data-promotion-dialog-id]').textContent = `商品 ID ${productId(product) || '未关联'}`;
    renderPromotionDialogImage(product);
    renderPromotionDetail(product, [], 'loading');
    try {
      const response = await DemoApi.domainRequest(`/api/promotion?${promotionDetailQuery(product)}`);
      if (requestToken !== state.promotionDetailRequest) return;
      const units = Array.isArray(response.data?.rows) ? response.data.rows : [];
      renderPromotionDetail(product, units, 'available');
    } catch (error) {
      if (requestToken !== state.promotionDetailRequest) return;
      renderPromotionDetail(product, [], 'error');
      const hint = $('[data-promotion-dialog-body] .ui-empty-state');
      if (hint) hint.appendChild(element('span', '', error.message || '接口暂时不可用。'));
    }
  }

  function openInfoDialog(trigger) {
    if (!ensurePromotionDetailDrawerOpen(trigger)) return;
    $('[data-promotion-dialog-title]').textContent = '数据口径说明';
    $('[data-promotion-dialog-subtitle]').textContent = `${state.period || '--'} 月度数据`;
    $('[data-promotion-dialog-id]').textContent = '推广分析 · 当前筛选范围';
    renderPromotionDialogImage({}, 'circle-help');
    $('[data-promotion-dialog-tabs]').hidden = true;
    const body = $('[data-promotion-dialog-body]');
    body.replaceChildren();
    const intro = element('section', 'ui-panel');
    intro.append(element('h3', 'panel__title', '如何使用本页数据'), element('p', 'panel__hint', '总览与趋势按商品级推广记录汇总。关键词、人群、站内渠道为同一商品记录上的不同投放字段，不能与总览相加。'));
    const list = element('div', 'status-list');
    [['商品表现', '可查看单商品推广花费、推广成交与推广 ROI。'], ['关键词 / 人群 / 站内渠道', '只展示已有月度聚合字段，不宣称词、计划或人群包级归因。'], ['未提供归因', '计划、创意、地域和内容数据未入库，因此保持不可用状态。']].forEach(([label, value]) => {
      const row = element('div', 'status-list__item');
      row.append(element('span', 'status-list__label', label), element('span', 'status-list__value', value));
      list.appendChild(row);
    });
    body.append(intro, list);
  }

  function openProductDetail(row, trigger) {
    const product = state.rows.find((item) => productId(item) === productId(row)) || row;
    window.ProductDetailDialog.open({
      productId: productId(product),
      title: productTitle(product),
      trigger,
      promotionContext: product,
      onChange: () => load(),
    });
  }

  function ensurePromotionDetailDrawerOpen(trigger) {
    const drawer = ensurePromotionDetailDrawer();
    if (!drawer) return false;
    drawer.open(trigger);
    return true;
  }

  function closeDialog() {
    state.promotionDetailRequest += 1;
    promotionDetailDrawer?.close();
  }

  function bindDialog() {
    ensurePromotionDetailDrawer();
  }

  function selectTab(tab) {
    if (!Object.prototype.hasOwnProperty.call(tabDefinitions, tab)) tab = 'products';
    state.activeTab = tab;
    syncPromotionUrl();
    document.querySelectorAll('[data-promotion-tab]').forEach((button) => {
      const active = button.dataset.promotionTab === tab;
      button.setAttribute('aria-selected', String(active));
      button.setAttribute('aria-pressed', String(active));
    });
    renderActiveTable();
  }

  function syncPromotionUrl() {
    const url = new URL(window.location.href);
    url.searchParams.set('tab', state.activeTab);
    [['channel', '[data-promotion-channel]'], ['campaign_id', '[data-promotion-campaign]'], ['unit_id', '[data-promotion-unit]'], ['product_id', '[data-promotion-product]']].forEach(([key, selector]) => {
      const value = $(selector)?.value.trim() || '';
      if (value) url.searchParams.set(key, value);
      else url.searchParams.delete(key);
    });
    history.replaceState(null, '', url);
  }

  function restorePromotionUrl() {
    [['channel', '[data-promotion-channel]'], ['campaign_id', '[data-promotion-campaign]'], ['unit_id', '[data-promotion-unit]'], ['product_id', '[data-promotion-product]']].forEach(([key, selector]) => {
      const input = $(selector);
      if (input) input.value = initialPromotionParams.get(key) || '';
    });
    if (!Object.prototype.hasOwnProperty.call(tabDefinitions, state.activeTab)) state.activeTab = 'products';
  }

  async function loadBoardOverview(detail, token) {
    try {
      const response = await DemoApi.domainRequest('/api/promotion?' + promotionPath(detail, 'campaign'));
      if (token !== state.token) return;
      state.planRows = Array.isArray(response.data?.rows) ? response.data.rows : [];
      renderPlanBoard(state.planRows);
    } catch (_) {
      if (token !== state.token) return;
      state.planRows = [];
      renderPlanBoard([]);
    }
  }

  async function load(detail) {
    const token = ++state.token;
    state.period = getPeriod(detail);
    const rangeNode = $('[data-promotion-range]');
    const rangeMetaNode = $('[data-promotion-range-meta]');
    if (rangeNode) rangeNode.textContent = `${state.period} 推广经营数据`;
    if (rangeMetaNode) rangeMetaNode.textContent = '店铺维度 · 含渠道 / 计划 / 商品三粒度';
    $('[data-promotion-period]').textContent = `${state.period} 商品推广趋势`;
    clearTable('加载推广数据中…');
    renderKpis([]);
    renderAlerts([]);
    renderCommandBoard([], []);
    destroyChart();
    renderDataState('loading');
    try {
      const performance = await DemoApi.domainRequest('/api/promotion?' + promotionPath(detail));
      if (token !== state.token) return;
      state.rows = Array.isArray(performance.data?.rows) ? performance.data.rows : [];
      state.capabilities = performance.capabilities || {};
      state.breakdowns = normalizeBreakdowns(performance.data?.breakdowns || {});
      state.alerts = Array.isArray(performance.data?.alerts) ? performance.data.alerts : [];
      state.availableGrains = Array.isArray(performance.data?.available_grains) ? performance.data.available_grains : [];
      const grainSelect = $('[data-promotion-drill-level]');
      const drillButton = $('[data-promotion-drill-load]');
      if (drillButton && Object.keys(state.capabilities).length) drillButton.disabled = !DemoApi.can(performance, 'can_drilldown');
      [...grainSelect.options].forEach((option) => { option.disabled = !state.availableGrains.includes(option.value); });
      if (!state.availableGrains.includes(grainSelect.value)) grainSelect.value = state.availableGrains[0] || 'channel';
      renderKpis(state.rows);
      renderProductBoard(state.rows);
      renderSourceStatus(performance.source_batches || []);
      renderTrend(Array.isArray(performance.data?.trend) ? performance.data.trend : []);
      renderAlerts(state.alerts);
      renderCommandBoard(state.rows, state.alerts);
      renderActiveTable();
      loadBoardOverview(detail, token);
      if (!state.rows.length) renderDataState('no-data', { message: '当前筛选范围未导入推广数据。' });
      else setStatus(`已加载 ${state.period} 推广数据`);
      window.lucide?.createIcons();
    } catch (error) {
      if (token !== state.token) return;
      state.rows = [];
      state.planRows = [];
      state.alerts = [];
      destroyChart();
      renderKpis([]);
      renderProductBoard([]);
      renderPlanBoard([]);
      renderAlerts([]);
      renderCommandBoard([], []);
      clearTable('推广数据加载失败');
      renderDataState('calculation-failed', { message: error.message || '推广数据加载失败', retry: () => load() });
      toast('推广数据加载失败');
    }
  }

  $('[data-promotion-tabs]').addEventListener('click', (event) => {
    const button = event.target.closest('[data-promotion-tab]');
    if (button) selectTab(button.dataset.promotionTab);
  });
  $('[data-promotion-info]').addEventListener('click', (event) => openInfoDialog(event.currentTarget));
  $('[data-promotion-drill-load]')?.addEventListener('click', loadDrilldown);

  function openFieldDialog(event) {
    state.dialogTab = state.activeTab;
    state.fieldDialogReturnFocus = event?.currentTarget || document.activeElement;
    renderFieldOptions(state.selectedFields[state.dialogTab] || []);
    renderSavedTemplates();
    const dialog = $('[data-promotion-field-dialog]');
    dialog.hidden = false;
    dialog.showModal();
    window.setTimeout(() => dialog.querySelector('input')?.focus(), 0);
  }

  function closeFieldDialog() {
    const dialog = $('[data-promotion-field-dialog]');
    if (dialog.open) dialog.close();
    dialog.hidden = true;
    state.fieldDialogReturnFocus?.focus?.();
    state.fieldDialogReturnFocus = null;
  }

  function openAlertsDialog(trigger) {
    const drawer = ensureAlertsDrawer();
    if (!drawer) return;
    renderAlertDialog(state.alerts || []);
    drawer.open(trigger);
    window.lucide?.createIcons();
  }

  function closeAlertsDialog() {
    promotionAlertsDrawer?.close();
  }

  function bindAlertsDialog() {
    if (!ensureAlertsDrawer()) return;
    $('[data-promotion-alerts-more]')?.addEventListener('click', (event) => openAlertsDialog(event.currentTarget));
  }

  function bindFieldSettings() {
    $('[data-promotion-template-select]')?.addEventListener('change', (event) => applyTemplate(event.target.value));
    $('[data-promotion-manage-fields]')?.addEventListener('click', openFieldDialog);
    $('[data-promotion-fields-select-all]')?.addEventListener('click', selectAllFields);
    $('[data-promotion-fields-clear-all]')?.addEventListener('click', clearAllFields);
    $('[data-promotion-template-save]')?.addEventListener('click', () => saveCustomTemplate());
    $('[data-promotion-saved-templates]')?.addEventListener('click', async (event) => {
      const use = event.target.closest('[data-promotion-use-template]');
      if (use) {
        const template = allTemplates(state.dialogTab).find((item) => item.id === use.dataset.promotionUseTemplate);
        if (template) renderFieldOptions(template.fields);
      }
      const remove = event.target.closest('[data-promotion-delete-template]');
      if (remove) {
        const tab = state.dialogTab;
        const previous = [...(state.customTemplates[tab] || [])];
        const template = previous.find((item) => item.id === remove.dataset.promotionDeleteTemplate);
        if (!template || !window.confirm(`删除字段模板“${template.name}”？`)) return;
        await deletePromotionTemplate(remove.dataset.promotionDeleteTemplate);
      }
    });
    $('[data-promotion-fields-apply]')?.addEventListener('click', () => {
      const selected = selectedDialogFields();
      if (!selected.length) return;
      state.selectedFields[state.dialogTab] = selected;
      state.activeTemplate[state.dialogTab] = 'custom';
      saveFieldPreferences();
      closeFieldDialog();
      renderTemplateSelect();
      renderActiveTable();
    });
    document.querySelectorAll('[data-promotion-fields-close]').forEach((button) => button.addEventListener('click', closeFieldDialog));
    $('[data-promotion-field-dialog]')?.addEventListener('cancel', (event) => { event.preventDefault(); closeFieldDialog(); });
  }

  function bindPageFilters() {
    ['[data-promotion-channel]', '[data-promotion-campaign]', '[data-promotion-unit]', '[data-promotion-product]'].forEach((selector) => {
      const input = $(selector);
      if (!input) return;
      let timer = null;
      input.addEventListener('input', () => {
        syncPromotionUrl();
        window.clearTimeout(timer);
        timer = window.setTimeout(() => load(), 260);
      });
      input.addEventListener('change', () => { syncPromotionUrl(); load(); });
    });
  }
  restorePromotionUrl();
  bindPageFilters();
  bindFieldSettings();
  bindAlertsDialog();
  bindDialog();
  selectTab(state.activeTab);
  loadServerTemplates()
    .catch((error) => toast(error.message || '字段模板加载失败'))
    .finally(() => renderTemplateSelect());
  window.addEventListener('tmall:date-range-change', (event) => load(event.detail));
  window.addEventListener('tmall:refresh', () => load());
  window.addEventListener('tmall:alert-rules-change', (event) => {
    if (!event.detail?.scope || event.detail.scope === 'promotion_product') load();
  });
  if (!window.TmallDateRange) load();
})();
