(function () {
  const makeProductPlaceholder = (item, productId) => {
    const placeholder = document.createElement('span');
    placeholder.className = 'product-thumb product-thumb--placeholder';
    placeholder.setAttribute('aria-hidden', 'true');
    placeholder.textContent = String(item.title || productId || '商品').trim().slice(0, 1);
    return placeholder;
  };
  const storageKey = 'tmall-products-field-view';
  const columnsStorageKey = 'tmall-products-visible-columns';
  const columnsPreferenceStorageKey = 'tmall-products-field-preference-v1';
  const columnGroups = [
    { label: '基础信息', columns: [
      { key: 'tier', label: '分层' }, { key: 'style', label: '风格' }, { key: 'product_type', label: '标品属性' },
      { key: 'product_time_node', label: '款期' }, { key: 'product_growth_stage', label: '成长阶段' }, { key: 'status', label: '状态' },
      { key: 'category', label: '类目' }, { key: 'list_date', label: '上架日期' },
      { key: 'scene', label: '场景' }, { key: 'product_tags', label: '款式属性' }, { key: 'manager', label: '负责人' }, { key: 'remark', label: '备注' }
    ] },
    { label: '流量与转化', columns: [
      { key: 'visitors', label: '商品访客数', format: 'number' }, { key: 'conversion', label: '商品支付转化率', format: 'percent' },
      { key: 'search_ratio', label: '搜索占比', format: 'percent' }, { key: 'search_conversion', label: '搜索转化率', format: 'percent' },
      { key: 'search_visitors', label: '搜索访客', format: 'number' }, { key: 'page_views', label: '浏览量', format: 'number' },
      { key: 'uv_value', label: '访客价值', format: 'money' }, { key: 'cart_rate', label: '加购率', format: 'percent' },
      { key: 'fav_rate', label: '收藏率', format: 'percent' }, { key: 'bounce_rate', label: '跳出率', format: 'percent' },
      { key: 'avg_stay_duration', label: '平均停留时长', format: 'decimal' }, { key: 'paid_ipv', label: '付费访客', format: 'number' },
      { key: 'organic_ipv', label: '自然访客', format: 'number' }, { key: 'search_ipv', label: '搜索访客数', format: 'number' },
      { key: 'recommend_ipv', label: '推荐访客', format: 'number' }, { key: 'cart_users', label: '加购人数', format: 'number' },
      { key: 'fav_users', label: '收藏人数', format: 'number' }, { key: 'click_rate', label: '商品点击率', format: 'percent' }
    ] },
    { label: '交易与退款', columns: [
      { key: 'payment_amount', label: '支付金额', format: 'money' }, { key: 'payment_count', label: '支付件数', format: 'number' },
      { key: 'buyers', label: '支付买家数', format: 'number' }, { key: 'avg_order_value', label: '客单价', format: 'money' },
      { key: 'net_sales', label: '净销售额', format: 'money' }, { key: 'refund_amount', label: '退款金额', format: 'money' },
      { key: 'refund_rate', label: '退款率', format: 'percent' }, { key: 'trend_change', label: '销售趋势变化', format: 'percent' },
      { key: 'cart_qty', label: '加购件数', format: 'number' }, { key: 'score', label: '综合评分', format: 'decimal' },
      { key: 'new_buyers', label: '新买家数', format: 'number' }, { key: 'new_buyer_ratio', label: '新买家占比', format: 'percent' },
      { key: 'repurchase_users', label: '复购人数', format: 'number' }, { key: 'repurchase_rate', label: '复购率', format: 'percent' },
      { key: 'cross_sell_qty', label: '连带件数', format: 'number' }, { key: 'cross_sell_categories', label: '连带类目数', format: 'number' },
      { key: 'cross_sell_rate', label: '连带率', format: 'percent' }, { key: 'guide_visits', label: '引导访问', format: 'number' },
      { key: 'guide_visitors', label: '引导访客', format: 'number' }, { key: 'guide_potential', label: '引导潜客', format: 'number' },
      { key: 'guide_potential_ratio', label: '引导潜客占比', format: 'percent' }
    ] },
    { label: '推广与付费', columns: [
      { key: 'ad_spend', label: '推广花费', format: 'money' }, { key: 'expense_ratio', label: '费比', format: 'percent' }, { key: 'roi', label: '推广 ROI', format: 'decimal' },
      { key: 'paid_ratio', label: '付费占比', format: 'percent' }, { key: 'keyword_spend', label: '关键词花费', format: 'money' },
      { key: 'keyword_roi', label: '关键词 ROI', format: 'decimal' }, { key: 'crowd_spend', label: '人群花费', format: 'money' },
      { key: 'crowd_roi', label: '人群 ROI', format: 'decimal' }, { key: 'impressions', label: '展现量', format: 'number' },
      { key: 'ctr', label: '点击率', format: 'percent' }, { key: 'overall_roi', label: '整体 ROI', format: 'decimal' },
      { key: 'refund_paid_ratio', label: '退款付费占比', format: 'percent' }, { key: 'keyword_sales', label: '关键词成交额', format: 'money' },
      { key: 'keyword_visitors', label: '关键词访客', format: 'number' }, { key: 'keyword_ppc', label: '关键词点击单价', format: 'money' },
      { key: 'crowd_sales', label: '人群成交额', format: 'money' }, { key: 'crowd_visitors', label: '人群访客', format: 'number' },
      { key: 'crowd_ppc', label: '人群点击单价', format: 'money' }, { key: 'site_spend', label: '站外花费', format: 'money' },
      { key: 'site_sales', label: '站外成交额', format: 'money' }, { key: 'site_roi', label: '站外 ROI', format: 'decimal' },
      { key: 'site_visitors', label: '站外访客', format: 'number' }, { key: 'site_ppc', label: '站外点击单价', format: 'money' },
      { key: 'clicks', label: '点击量', format: 'number' }, { key: 'cost', label: '点击花费', format: 'money' },
      { key: 'cpc', label: '平均点击花费', format: 'money' }, { key: 'cpm', label: '千次展现花费', format: 'money' },
      { key: 'direct_gmv', label: '直接成交额', format: 'money' }, { key: 'indirect_gmv', label: '间接成交额', format: 'money' },
      { key: 'total_gmv', label: '总成交额', format: 'money' }, { key: 'total_orders', label: '总订单数', format: 'number' },
      { key: 'direct_orders', label: '直接订单数', format: 'number' }, { key: 'indirect_orders', label: '间接订单数', format: 'number' },
      { key: 'click_conversion', label: '点击转化率', format: 'percent' }, { key: 'presale_roi', label: '预售 ROI', format: 'decimal' },
      { key: 'total_cost', label: '总花费', format: 'money' }, { key: 'cart_adds', label: '加购次数', format: 'number' },
      { key: 'direct_cart_adds', label: '直接加购', format: 'number' }, { key: 'indirect_cart_adds', label: '间接加购', format: 'number' },
      { key: 'favs', label: '收藏次数', format: 'number' }, { key: 'store_favs', label: '店铺收藏', format: 'number' },
      { key: 'store_fav_cost', label: '店铺收藏成本', format: 'money' }, { key: 'total_fav_cart', label: '收藏加购总数', format: 'number' },
      { key: 'total_fav_cart_cost', label: '收藏加购成本', format: 'money' }, { key: 'item_fav_cart', label: '商品收藏加购', format: 'number' },
      { key: 'item_fav_cart_cost', label: '商品收藏加购成本', format: 'money' }, { key: 'total_favs', label: '总收藏数', format: 'number' },
      { key: 'item_fav_cost', label: '商品收藏成本', format: 'money' }, { key: 'item_fav_rate', label: '商品收藏率', format: 'percent' },
      { key: 'cart_cost', label: '加购成本', format: 'money' }, { key: 'industry_ctr', label: '行业点击率', format: 'percent' }
    ] },
    { label: '生命周期与协作', columns: [
      { key: 'lifecycle_stage', label: '生命周期阶段' },
      { key: 'seasonality', label: '季节属性' },
      { key: 'has_pending_action', label: '待办动作' }
    ] }
  ];
  columnGroups[1].columns.push(
    { key: 'presale_amount', label: '\u9884\u552e\u652f\u4ed8\u91d1\u989d', format: 'money' },
    { key: 'presale_qty', label: '\u9884\u552e\u9500\u91cf', format: 'number' },
    { key: 'search_click_rate', label: '\u514d\u8d39\u641c\u7d22\u70b9\u51fb\u7387', format: 'percent' },
    { key: 'category_width', label: '\u8fde\u5e26\u8d2d\u4e70\u53f6\u5b50\u7c7b\u76ee\u5bbd\u5ea6', format: 'number' },
  );
  const columns = [...new Map(columnGroups.flatMap((group) => group.columns).map((column) => [column.key, column])).values()];
  const columnsByKey = new Map(columns.map((column) => [column.key, column]));
  const templates = {
    operate: ['tier', 'style', 'product_type', 'product_time_node', 'status', 'payment_amount', 'net_sales', 'conversion', 'refund_rate', 'ad_spend', 'roi', 'paid_ipv', 'organic_ipv', 'search_ipv', 'recommend_ipv', 'repurchase_rate'],
    select: ['tier', 'style', 'product_type', 'product_time_node', 'category', 'status', 'visitors', 'conversion', 'cart_rate', 'fav_rate', 'payment_amount', 'buyers', 'avg_order_value', 'score'],
    paid: ['status', 'ad_spend', 'expense_ratio', 'roi', 'paid_ratio', 'keyword_spend', 'keyword_roi', 'crowd_spend', 'crowd_roi', 'impressions', 'clicks', 'ctr'],
    refund: ['status', 'payment_amount', 'net_sales', 'refund_amount', 'refund_rate', 'buyers', 'avg_order_value', 'new_buyers', 'new_buyer_ratio', 'repurchase_users', 'repurchase_rate', 'score'],
    lifecycle: ['lifecycle_stage', 'seasonality', 'has_pending_action', 'list_date', 'tier', 'style', 'product_type', 'product_time_node', 'product_growth_stage', 'status', 'payment_amount', 'trend_change'],
    traffic: ['tier', 'style', 'visitors', 'page_views', 'uv_value', 'paid_ipv', 'organic_ipv', 'conversion', 'cart_rate', 'fav_rate', 'bounce_rate', 'avg_stay_duration', 'click_rate'],
    transaction: ['tier', 'style', 'payment_amount', 'payment_count', 'buyers', 'avg_order_value', 'net_sales', 'refund_amount', 'refund_rate', 'trend_change', 'cart_qty', 'score'],
    promotion: ['status', 'ad_spend', 'expense_ratio', 'roi', 'paid_ratio', 'keyword_spend', 'keyword_roi', 'crowd_spend', 'crowd_roi', 'site_spend', 'site_sales', 'site_roi']
  };
  const templateLabels = {
    operate: '经营', select: '选款', paid: '投放', refund: '退款', lifecycle: '生命周期'
  };
  Object.assign(templateLabels, {
    operate: '\u7ecf\u8425\u603b\u89c8',
    select: '\u9009\u6b3e\u5206\u6790',
    paid: '\u6295\u653e\u6548\u7387',
    refund: '\u9000\u6b3e\u590d\u8d2d',
    lifecycle: '\u751f\u547d\u5468\u671f',
    traffic: '\u6d41\u91cf\u8f6c\u5316',
    transaction: '\u4ea4\u6613\u4e0e\u9000\u6b3e',
    promotion: '\u63a8\u5e7f\u4e0e\u8d39\u7528',
  });
  const builtinTemplateKeys = new Set(Object.keys(templates));
  const focusableSelector = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';
  const $ = (selector, root = document) => root.querySelector(selector);
  const state = {
    rows: [],
    total: 0,
    page: 1,
    pageSize: 20,
    token: 0,
    selected: new Set(),
    dateRange: null,
    starredOnly: false,
    view: 'operate',
    visibleColumns: [...templates.operate],
    serverDefaultView: null,
    searchTimer: null,
    facets: { tiers: [], styles: [], statuses: [], product_types: [], product_time_nodes: [], product_growth_stages: [] },
    settings: null,
    capabilities: {},
    availability: 'calculation-failed',
    evidence: [],
  };

  const money = (value) => `¥${Number(value || 0).toLocaleString('zh-CN', { maximumFractionDigits: 2 })}`;
  const number = (value) => Number(value || 0).toLocaleString('zh-CN');
  const percent = (value) => `${(Number(value || 0) * 100).toFixed(2)}%`;
  const decimal = (value) => Number(value || 0).toLocaleString('zh-CN', { maximumFractionDigits: 2 });
  const field = (item, name) => Number(item?.[name] || 0);
  const productId = (item) => String(item?.product_id || '');
  const salesOf = (item) => field(item, 'payment_amount') || field(item, 'total_gmv');
  const spendOf = (item) => field(item, 'ad_spend') || field(item, 'cost') || field(item, 'total_cost');
  const toast = (message) => window.DemoShell?.showToast ? window.DemoShell.showToast(message) : window.alert(message);
  const setStatus = (message) => {
    const status = $('[data-products-status]');
    if (status) status.textContent = message;
    window.DemoShell?.setStatus?.(message);
  };
  const renderDataState = (state, details) => DemoApi.renderDataState($('[data-products-status]'), state, details);
  const jsonOptions = (body, method = 'POST') => ({
    method,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const asArray = (payload, key = 'data') => Array.isArray(payload) ? payload : (Array.isArray(payload?.[key]) ? payload[key] : []);

  // missing facts are not zero: status and issue copy must stay explainable.
  function productHealth(item) {
    if (!Number(item?.has_data || 0)) return { label: '不可分析', tone: 'muted', reason: '缺少商品月度事实', sortValue: 2 };
    if (Number(item?.has_pending_action || 0)) return { label: '需处理', tone: 'warning', reason: '存在待执行运营动作', sortValue: 1 };
    return { label: '健康', tone: 'success', reason: '当前范围内暂无待处理规则', sortValue: 0 };
  }

  function buildProductDetailUrl(item) {
    const id = encodeURIComponent(productId(item));
    const url = new URL(`/products/${id}`, window.location.origin);
    const currentUrl = new URL(window.location.href);
    const range = currentRange();
    if (range.startDate) url.searchParams.set('start', range.startDate);
    if (range.endDate) url.searchParams.set('end', range.endDate);
    ['preset', 'promotion_channel'].forEach((key) => {
      const value = currentUrl.searchParams.get(key);
      if (value) url.searchParams.set(key, value);
    });
    const currentFilters = filters();
    ['tier', 'lifecycle_stage'].forEach((key) => {
      if (currentFilters[key]) url.searchParams.set(key, currentFilters[key]);
    });
    return `${url.pathname}${url.search}`;
  }

  function renderOperationsSummary(rows) {
    const alertTitle = $('[data-products-alert-title]');
    const alertMessage = $('[data-products-alert-message]');
    const alertAction = $('[data-products-alert-action]');
    const issueCount = $('[data-products-action]');
    const issueList = $('[data-products-issues-list]');
    const coverageList = $('[data-products-coverage-list]');
    if (!alertTitle || !issueList || !coverageList) return;
    const pending = rows.filter((item) => Number(item.has_pending_action || 0));
    const missing = rows.filter((item) => !Number(item.has_data || 0));
    const totalIssues = pending.length + missing.length;
    alertTitle.textContent = totalIssues ? `${totalIssues} 个商品需要关注` : '当前筛选范围暂无待处理事项';
    alertMessage.textContent = totalIssues
      ? `${pending.length} 个有待办动作 · ${missing.length} 个缺少商品月度事实`
      : '商品主档和当前事实覆盖没有触发可解释规则。';
    issueCount.textContent = totalIssues ? `${totalIssues} 项` : '无事项';
    alertAction.hidden = !totalIssues;
    alertAction.onclick = () => issueList.closest('.products-issues')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    issueList.replaceChildren();
    const issues = [...pending.map((item) => ({ item, label: '待执行动作', reason: '存在待执行运营动作', tone: 'warning' })), ...missing.map((item) => ({ item, label: '数据覆盖不足', reason: '缺少商品月度事实，指标不参与判断', tone: 'muted' }))].slice(0, 3);
    if (!issues.length) {
      const empty = document.createElement('p');
      empty.className = 'panel__hint';
      empty.textContent = '暂无需要处理的事项';
      issueList.appendChild(empty);
    } else issues.forEach(({ item, label, reason, tone }) => {
      const row = document.createElement('div');
      row.className = 'products-issue';
      const copy = document.createElement('div');
      const title = document.createElement('strong');
      title.textContent = item.title || productId(item) || '未命名商品';
      const detail = document.createElement('span');
      detail.textContent = `${label} · ${reason}`;
      copy.append(title, detail);
      const action = document.createElement('button');
      action.type = 'button'; action.className = 'button button--ghost'; action.textContent = '查看详情';
      action.addEventListener('click', () => openProductDetail(item, action));
      row.append(copy, action);
      issueList.appendChild(row);
    });
    const evidence = state.evidence?.[0] || {};
    const observed = Number(evidence.observed_fact_rows || rows.filter((item) => Number(item.has_data || 0)).length);
    const total = Number(evidence.row_count || rows.length);
    coverageList.replaceChildren();
    [['商品主档', total ? 100 : 0, '已加载商品'], ['商品月度事实', total ? observed / total * 100 : 0, `${observed} / ${total || 0} 件可分析`], ['推广日事实', null, '当前接口未提供覆盖证据']].forEach(([label, ratio, note]) => {
      const item = document.createElement('div'); item.className = 'products-coverage__item';
      const line = document.createElement('div'); line.className = 'products-coverage__line';
      const title = document.createElement('strong'); title.textContent = label;
      const value = document.createElement('span'); value.textContent = ratio == null ? '不可用' : `${ratio.toFixed(1)}%`;
      line.append(title, value);
      const track = document.createElement('div'); track.className = 'products-coverage__track';
      const bar = document.createElement('i'); bar.style.width = `${Math.max(0, Math.min(100, ratio || 0))}%`; track.appendChild(bar);
      const hint = document.createElement('small'); hint.textContent = note;
      item.append(line, track, hint); coverageList.appendChild(item);
    });
  }

  function currentRange(detail) {
    const next = detail || window.TmallDateRange?.getState?.() || state.dateRange || {};
    state.dateRange = next;
    return next;
  }

  function currentMonthPeriod() {
    const range = currentRange();
    const raw = range.endDate || range.startDate || new Date().toISOString().slice(0, 10);
    return String(raw).slice(0, 7);
  }

  function setRowStatus(message) {
    const body = $('[data-products-body]');
    body.replaceChildren();
    const row = document.createElement('tr');
    const cell = row.insertCell();
    cell.colSpan = state.visibleColumns.length + 4;
    cell.textContent = message;
    row.appendChild(cell);
    body.appendChild(row);
  }

  function optionValues(key) {
    const facetKey = ({ tier: 'tiers', style: 'styles', status: 'statuses', product_type: 'product_types', product_time_node: 'product_time_nodes', product_growth_stage: 'product_growth_stages' })[key] || `${key}s`;
    return [...new Set((state.facets[facetKey] || []).map((item) => DemoLabels.clean(item, '')).filter(Boolean))].sort();
  }

  function classificationValues(key) {
    const group = key === 'tier' ? 'tiers' : key === 'style' ? 'styles' : null;
    const configured = (DemoLabels.dictionaries?.[group] || []).map((item) => DemoLabels.clean(item.value, ''));
    return [...new Set([...configured, ...optionValues(key)])]
      .filter(Boolean)
      .sort((first, second) => first.localeCompare(second, 'zh-CN', { numeric: true }));
  }

  function fillSelect(selector, values, firstLabel) {
    const select = $(selector);
    const previous = select.value;
    select.replaceChildren();
    const first = document.createElement('option');
    first.value = '';
    first.textContent = firstLabel;
    select.appendChild(first);
    values.forEach((value) => {
      const option = document.createElement('option');
      option.value = value;
      const group = selector.includes('lifecycle-stage') ? 'lifecycle_stages' : selector.includes('seasonality') ? 'seasonal_attributes' : null;
      option.textContent = group ? DemoLabels.classification(group, value, value) : selector.includes('status') ? DemoLabels.label('status', value, value) : value;
      select.appendChild(option);
    });
    if ([...select.options].some((option) => option.value === previous)) select.value = previous;
  }

  function filters() {
    return {
      search: $('[data-products-search]').value.trim(),
      tier: $('[data-products-tier]').value,
      style: $('[data-products-style]').value,
      product_type: $('[data-products-type]')?.value || '',
      product_time_node: $('[data-products-time-node]')?.value || '',
      product_growth_stage: $('[data-products-growth-stage]')?.value || '',
      status: $('[data-products-status-filter]').value,
      sort: $('[data-products-sort]').value || 'payment_amount',
      order: $('[data-products-order]').value || 'desc',
      lifecycle_stage: $('[data-products-lifecycle-stage]')?.value || '',
      seasonality: $('[data-products-seasonality]')?.value || '',
      has_pending_action: $('[data-products-pending-action]')?.value || '',
    };
  }

  function buildProductsUrl() {
    // 当前导入源是商品月度事实，商品页按月度口径读取，避免日表为空时整页指标变成 0。
    const params = new URLSearchParams({ dim: 'monthly', limit: String(state.pageSize), offset: String((state.page - 1) * state.pageSize) });
    params.set('period', currentMonthPeriod());
    const current = filters();
    ['search', 'tier', 'style', 'product_type', 'product_time_node', 'product_growth_stage', 'status', 'sort', 'order', 'lifecycle_stage', 'seasonality', 'has_pending_action'].forEach((key) => {
      if (current[key]) params.set(key, current[key]);
    });
    return `/api/products?${params.toString()}`;
  }

  function visibleRows() {
    return state.starredOnly ? state.rows.filter((item) => Number(item.starred || 0) === 1) : state.rows;
  }

  function updateKpis(rows) {
    const sales = rows.reduce((sum, item) => sum + salesOf(item), 0);
    const spend = rows.reduce((sum, item) => sum + spendOf(item), 0);
    $('[data-products-kpi="total"]').textContent = number(state.total);
    $('[data-products-kpi="sales"]').textContent = money(sales);
    $('[data-products-kpi="spend"]').textContent = money(spend);
    $('[data-products-kpi="roi"]').textContent = spend ? (sales / spend).toFixed(2) : '--';
  }

  function metric(label, value) {
    const item = document.createElement('div');
    item.className = 'detail-metric';
    const labelEl = document.createElement('span');
    labelEl.textContent = label;
    const valueEl = document.createElement('strong');
    valueEl.textContent = value;
    item.append(labelEl, valueEl);
    return item;
  }

  function badge(value, fallback) {
    const item = document.createElement('span');
    item.className = 'badge badge--muted';
    item.textContent = value || fallback || '--';
    return item;
  }

  function editableSelect(item, key) {
    const wrap = document.createElement('div'); wrap.className = 'editable-classification';
    const input = document.createElement('input');
    const listId = `product-${key}-options-${productId(item).replace(/[^a-zA-Z0-9_-]/g, '_')}`;
    input.className = 'input'; input.setAttribute('list', listId);
    input.disabled = Object.keys(state.capabilities).length > 0 && !DemoApi.can({ capabilities: state.capabilities }, 'can_edit');
    input.setAttribute('aria-label', key === 'tier' ? '修改分层' : '修改风格');
    const current = DemoLabels.clean(item[key], '');
    input.value = current; input.placeholder = key === 'tier' ? '未分层' : '未分类';
    const list = document.createElement('datalist'); list.id = listId;
    const dictionaryGroup = key === 'tier' ? 'tiers' : 'styles';
    const values = [...new Set([current, ...classificationValues(key)])].filter(Boolean);
    values.forEach((value) => {
      const option = document.createElement('option');
      option.value = value;
      list.appendChild(option);
    });
    input.addEventListener('change', async () => {
      await updateField(productId(item), key, input.value.trim());
      await rememberClassification(dictionaryGroup, input.value.trim());
    });
    input.addEventListener('input', () => {
      const cell = wrap.closest('td');
      if (cell) cell.dataset.sortValue = input.value.trim();
    });
    wrap.dataset.sortValue = current;
    wrap.append(input, list); return wrap;
  }

  async function rememberClassification(group, value) {
    if (!value || DemoLabels.dictionaries[group]?.some((item) => item.value === value)) return;
    const response = await DemoApi.domainRequest('/api/settings');
    const dictionaries = structuredClone(response.data.classification_dictionaries);
    dictionaries[group].push({ value, label: value, enabled: true, system: false });
    await DemoApi.domainRequest('/api/settings', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ classification_dictionaries: dictionaries }) });
    DemoLabels.setDictionaries(dictionaries);
  }

  function fillBatchOptions() {
    const fieldName = $('[data-products-batch-field]').value;
    $('[data-products-batch-value]').setAttribute('list', `products-${fieldName}-options`);
    const list = $('[data-products-batch-options]'); list.id = `products-${fieldName}-options`;
    list.replaceChildren(...classificationValues(fieldName).map((value) => new Option('', value)));
  }

  function addCell(row, content, className, fieldKey) {
    const cell = row.insertCell();
    if (className) cell.className = className;
    if (fieldKey) cell.dataset.fieldKey = fieldKey;
    if (content instanceof Node) cell.appendChild(content);
    else cell.textContent = content;
    return cell;
  }

  function formatColumnValue(item, column) {
    const value = column.key === 'payment_amount' ? salesOf(item) : column.key === 'ad_spend' ? spendOf(item) : field(item, column.key);
    if (column.format === 'money') return money(value);
    if (column.format === 'number') return number(value);
    if (column.format === 'percent') return percent(value);
    if (column.format === 'decimal') return decimal(value);
    return String(item[column.key] || '--');
  }

  function renderHeader() {
    const head = $('[data-products-head]');
    head.replaceChildren();
    const fixed = [
      ['select', ''], ['star', '收藏'], ['title', '商品'], ['health', '健康状态']
    ];
    fixed.forEach(([key, label]) => {
      const th = document.createElement('th');
      th.dataset.fieldKey = key;
      if (key === 'select') {
        const check = document.createElement('input');
        check.type = 'checkbox';
        check.setAttribute('data-products-select-all', '');
        check.setAttribute('aria-label', '选择当前页商品');
        check.addEventListener('change', toggleSelectAll);
        th.appendChild(check);
      } else th.textContent = label;
      head.appendChild(th);
    });
    state.visibleColumns.forEach((key) => {
      const column = columnsByKey.get(key);
      if (!column) return;
      const th = document.createElement('th');
      th.dataset.fieldKey = key;
      th.textContent = column.label;
      if (column.format) th.className = 'num';
      head.appendChild(th);
    });
  }

  function toggleSelectAll(event) {
    visibleRows().forEach((item) => {
      const id = productId(item);
      if (event.currentTarget.checked) state.selected.add(id);
      else state.selected.delete(id);
    });
    renderTable();
  }

  function renderTable() {
    renderHeader();
    const body = $('[data-products-body]');
    body.replaceChildren();
    const rows = visibleRows();
    updateKpis(rows);
    if (!rows.length) {
      setRowStatus(state.starredOnly ? '当前页没有收藏商品' : '当前条件暂无商品');
      renderMobileSummary(rows);
      renderOperationsSummary(rows);
      applyFieldView();
      updatePagination();
      updateSelection();
      return;
    }
    rows.forEach((item) => {
      const id = productId(item);
      const row = document.createElement('tr');
      row.dataset.productId = id;

      const check = document.createElement('input');
      check.type = 'checkbox';
      check.value = id;
      check.checked = state.selected.has(id);
      check.setAttribute('aria-label', `选择商品 ${id}`);
      check.addEventListener('change', () => {
        if (check.checked) state.selected.add(id);
        else state.selected.delete(id);
        updateSelection();
      });
      addCell(row, check);

      const star = document.createElement('button');
      star.type = 'button';
      star.className = 'star-button';
      star.dataset.capabilityKey = 'products.catalog_edit';
      star.disabled = Object.keys(state.capabilities).length > 0 && !DemoApi.can({ capabilities: state.capabilities }, 'can_edit');
      star.classList.toggle('is-active', Number(item.starred || 0) === 1);
      star.innerHTML = '<i data-lucide="star"></i>';
      star.setAttribute('aria-label', Number(item.starred || 0) === 1 ? '取消收藏' : '收藏');
      star.setAttribute('aria-pressed', String(Number(item.starred || 0) === 1));
      star.addEventListener('click', async () => toggleStar(item, star));
      addCell(row, star);

      const identity = document.createElement('div');
      identity.className = 'product-identity';
      let thumbnail;
      const thumbnailUrl = String(item.image_url || '').trim();
      if (item.image_url) {
        thumbnail = document.createElement('img');
        thumbnail.className = 'product-thumb';
        thumbnail.alt = '';
        thumbnail.loading = 'lazy';
        thumbnail.src = item.image_url;
        thumbnail.addEventListener('error', () => {
          thumbnail.replaceWith(makeProductPlaceholder(item, id));
        }, { once: true });
      }
      else if (thumbnailUrl) {
        thumbnail = document.createElement('img');
        thumbnail.className = 'product-thumb';
        thumbnail.alt = '';
        thumbnail.loading = 'lazy';
        thumbnail.src = thumbnailUrl;
        thumbnail.addEventListener('error', () => {
          const placeholder = document.createElement('span');
          placeholder.className = 'product-thumb product-thumb--placeholder';
          placeholder.setAttribute('aria-hidden', 'true');
          placeholder.textContent = String(item.title || id || '商品').trim().slice(0, 1);
          thumbnail.replaceWith(placeholder);
        }, { once: true });
      } else {
        thumbnail = document.createElement('span');
        thumbnail.className = 'product-thumb product-thumb--placeholder';
        thumbnail.setAttribute('aria-hidden', 'true');
        thumbnail.textContent = String(item.title || id || '商品').trim().slice(0, 1);
      }
      const title = document.createElement('div');
      title.className = 'product-title';
      const titleButton = document.createElement('button');
      titleButton.type = 'button';
      titleButton.className = 'product-title__link';
      titleButton.textContent = item.title || '未命名商品';
      titleButton.setAttribute('aria-label', `查看商品详情：${item.title || id || '未命名商品'}`);
      titleButton.addEventListener('click', () => openProductDetail(item, titleButton));
      const sub = document.createElement('span');
      sub.textContent = id || '--';
      title.append(titleButton, sub);
      identity.append(thumbnail, title);
      addCell(row, identity);

      const health = productHealth(item);
      const healthCell = document.createElement('div');
      healthCell.className = 'products-health-cell';
      const healthBadge = badge(health.label, health.label);
      healthBadge.classList.remove('badge--muted');
      healthBadge.classList.add(`badge--${health.tone}`);
      healthCell.appendChild(healthBadge);
       const healthTableCell = addCell(row, healthCell, '', 'health');
       healthTableCell.dataset.sortValue = String(health.sortValue);

       state.visibleColumns.forEach((key) => {
        const column = columnsByKey.get(key);
        if (!column) return;
         if (key === 'tier' || key === 'style') {
           const classificationCell = addCell(row, editableSelect(item, key), '', key);
           classificationCell.dataset.sortValue = DemoLabels.clean(item[key], '');
         }
        else if (key === 'product_type') addCell(row, badge(item.product_type || '待复核', item.product_type || '待复核'), '', key);
         else if (key === 'product_growth_stage') addCell(row, item.product_growth_stage || '--', '', key);
         else if (key === 'product_time_node') addCell(row, item.product_time_node || '--', '', key);
         else if (key === 'status') addCell(row, badge(DemoLabels.label('status', item.status, item.status), '未知'), '', key);
        else if (key === 'lifecycle_stage') addCell(row, DemoLabels.classification('lifecycle_stages', item.lifecycle_stage, item.lifecycle_stage || '--'), '', key);
        else if (key === 'seasonality') addCell(row, DemoLabels.classification('seasonal_attributes', item.seasonality, item.seasonality || '--'), '', key);
        else if (key === 'has_pending_action') addCell(row, badge(item.has_pending_action ? '有待办' : '无待办', '无待办'), '', key);
        else addCell(row, formatColumnValue(item, column), column.format ? 'num' : '', key);
      });

      body.appendChild(row);
    });
    renderMobileSummary(rows);
    renderOperationsSummary(rows);
    applyFieldView();
    updatePagination();
    updateSelection();
    window.lucide?.createIcons();
  }

  function updatePagination() {
    const totalPages = Math.max(1, Math.ceil(state.total / state.pageSize));
    $('[data-products-page-size]').value = String(state.pageSize);
    $('[data-products-page-summary]').textContent = `第 ${state.page} / ${totalPages} 页，共 ${number(state.total)} 件；每页 ${state.pageSize} 件${state.starredOnly ? '；当前页收藏过滤' : ''}`;
    $('[data-products-prev]').disabled = state.page <= 1;
    $('[data-products-next]').disabled = state.page >= totalPages;
  }

  function updateSelection() {
    const visibleIds = visibleRows().map(productId);
    const selectedVisible = visibleIds.filter((id) => state.selected.has(id));
    const all = $('[data-products-select-all]');
    all.checked = visibleIds.length > 0 && selectedVisible.length === visibleIds.length;
    all.indeterminate = selectedVisible.length > 0 && selectedVisible.length < visibleIds.length;
    $('[data-products-selected]').textContent = `已选 ${state.selected.size} 件`;
    $('[data-products-batch]').classList.toggle('is-active', state.selected.size > 0);
  }

  function renderMobileSummary(rows) {
    const root = $('[data-products-mobile-summary]');
    if (!root) return;
    root.hidden = false;
    root.replaceChildren();
    if (!rows.length) {
      const empty = document.createElement('p');
      empty.className = 'panel__hint';
      empty.textContent = state.starredOnly ? '当前页没有收藏商品' : '当前条件暂无商品';
      root.appendChild(empty);
      return;
    }
    rows.forEach((item) => {
      const id = productId(item);
      const card = document.createElement('article');
      card.className = 'products-mobile-summary__item';
      const header = document.createElement('div');
      header.className = 'products-mobile-summary__header';
      const identity = document.createElement('div');
      identity.className = 'products-mobile-summary__identity';
      const title = document.createElement('strong');
      title.textContent = item.title || '未命名商品';
      const code = document.createElement('span');
      code.textContent = id || '--';
      identity.append(title, code);
      const detail = document.createElement('button');
      detail.type = 'button';
      detail.className = 'button button--ghost';
      detail.textContent = '详情';
      detail.addEventListener('click', () => openProductDetail(item, detail));
      header.append(identity, detail);
      const metrics = document.createElement('dl');
      metrics.className = 'products-mobile-summary__metrics';
      [['payment_amount', '支付金额', money(item.payment_amount)], ['net_sales', '净销售额', money(item.net_sales)], ['roi', '推广 ROI', decimal(item.roi)], ['has_pending_action', '待办', item.has_pending_action ? '有待办' : '无待办']].forEach(([key, label, value]) => {
        const term = document.createElement('dt');
        term.textContent = label;
        term.dataset.fieldKey = key;
        const valueNode = document.createElement('dd');
        valueNode.textContent = value;
        metrics.append(term, valueNode);
      });
      card.append(header, metrics);
      root.appendChild(card);
    });
  }

  function applyFieldView() {
    const view = state.view;
    document.querySelectorAll('[data-products-view]').forEach((button) => {
      button.setAttribute('aria-pressed', String(button.dataset.productsView === view));
    });
    renderHeader();
  }

  const columnsDialog = $('[data-products-columns-dialog]');
  let columnsReturnFocus = null;
  let columnSelector = null;
  let templateManager = null;

  const productTemplateRecords = () => Object.fromEntries(Object.entries(templates).map(([key, columnsList]) => [key, {
    label: templateLabels[key] || key,
    columns: [...columnsList],
  }]));

  function selectedDialogColumns() {
    return columnSelector?.getSelected() || [];
  }

  function updateColumnsDialogStatus() {
    const selected = selectedDialogColumns();
    $('[data-products-visible-count]').textContent = number(selected.length);
    $('[data-products-columns-status]').textContent = selected.length ? '' : '至少保留一个可见字段';
    $('[data-products-columns-apply]').disabled = selected.length === 0;
    $('[data-products-template-save]').disabled = selected.length === 0;
  }

  function renderTemplateSelect(selectedKey = state.view) {
    const select = $('[data-products-template-select]');
    select.replaceChildren(...Object.keys(templates).map((key) => {
      const option = document.createElement('option');
      option.value = key;
      option.textContent = templateLabels[key] || key;
      return option;
    }));
    if ([...select.options].some((option) => option.value === selectedKey)) select.value = selectedKey;
  }

  function renderColumnOptions(selected = state.visibleColumns) {
    const config = {
      groups: columnGroups.map((group) => ({ label: group.label, fields: group.columns })),
      selected,
    };
    if (!columnSelector) {
      columnSelector = DemoFieldSelector.create({
        root: $('[data-products-field-selector]'),
        ...config,
        className: 'products-field-selection-layout',
        availableTitleId: 'productsAvailableFieldsTitle',
        previewTitleId: 'productsFieldPreviewTitle',
        optionDataAttribute: 'data-products-column-key',
        previewDataAttribute: 'data-products-preview-key',
        onChange: updateColumnsDialogStatus,
      });
    } else {
      columnSelector.setConfig(config);
    }
    if (!templateManager && window.DemoFieldTemplateManager) {
      templateManager = DemoFieldTemplateManager.create({
        root: $('[data-products-template-manager]'),
        builtinKeys: [...builtinTemplateKeys],
        templates: productTemplateRecords(),
        onChange: (event) => {
          if (event.type === 'use') {
            const selectedTemplate = templates[event.key];
            if (selectedTemplate) renderColumnOptions(selectedTemplate);
            renderTemplateSelect(event.key);
          }
        },
        onSave: (key, label) => updateProductTemplate(key, label),
        onDelete: (key) => deleteProductTemplate(key),
      });
    }
    templateManager?.setTemplates(productTemplateRecords());
    renderTemplateSelect();
    updateColumnsDialogStatus();
    window.lucide?.createIcons();
  }

  function openColumnsDialog(event) {
    columnsReturnFocus = event.currentTarget;
    renderColumnOptions();
    columnsDialog.hidden = false;
    columnsDialog.showModal();
    window.setTimeout(() => columnsDialog.querySelector('input')?.focus(), 0);
  }

  function closeColumnsDialog() {
    if (columnsDialog.open) columnsDialog.close();
    columnsDialog.hidden = true;
    columnsReturnFocus?.focus?.();
    columnsReturnFocus = null;
  }

  function saveColumns() {
    try {
      localStorage.setItem(storageKey, state.view);
      localStorage.setItem(columnsStorageKey, JSON.stringify(state.visibleColumns));
      localStorage.setItem(columnsPreferenceStorageKey, JSON.stringify({
        view: state.view,
        columns: state.visibleColumns,
        serverDefaultView: state.serverDefaultView,
      }));
    } catch {}
  }

  function applyColumns(selected, view = 'custom') {
    const valid = selected.filter((key) => columnsByKey.has(key));
    if (!valid.length) return;
    state.visibleColumns = valid;
    state.view = view;
    saveColumns();
    renderTable();
  }

  function ingestViewTemplates(settings) {
    state.settings = settings;
    Object.keys(templates).forEach((key) => {
      if (!builtinTemplateKeys.has(key)) delete templates[key];
    });
    Object.keys(templateLabels).forEach((key) => {
      if (!builtinTemplateKeys.has(key)) delete templateLabels[key];
    });
    Object.entries(settings?.view_templates || {}).forEach(([key, value]) => {
      const columnsList = Array.isArray(value) ? value : value?.columns;
      if (!Array.isArray(columnsList)) return;
      const valid = columnsList.filter((column) => columnsByKey.has(column));
      if (!valid.length) return;
      templates[key] = valid;
      templateLabels[key] = Array.isArray(value) ? key : (value.label || key);
    });
    templateManager?.setTemplates(productTemplateRecords());
  }

  async function updateProductTemplate(key, label) {
    const selected = selectedDialogColumns();
    if (!selected.length || !templates[key]) return;
    const viewTemplates = { ...(state.settings?.view_templates || {}), ...productTemplateRecords() };
    viewTemplates[key] = { label, columns: selected };
    try {
      const response = await DemoApi.domainRequest('/api/settings', jsonOptions({ view_templates: viewTemplates }, 'PUT'));
      ingestViewTemplates(response.data);
      applyColumns(selected, key);
      renderColumnOptions(selected);
      $('[data-products-columns-status]').textContent = `模板“${label}”已更新`;
    } catch (error) {
      $('[data-products-columns-status]').textContent = error.message || '模板更新失败';
    }
  }

  async function deleteProductTemplate(key) {
    if (builtinTemplateKeys.has(key)) return;
    const viewTemplates = { ...(state.settings?.view_templates || {}) };
    delete viewTemplates[key];
    const payload = { view_templates: viewTemplates };
    if (state.settings?.product_view_template === key) payload.product_view_template = 'operate';
    try {
      const response = await DemoApi.domainRequest('/api/settings', jsonOptions(payload, 'PUT'));
      ingestViewTemplates(response.data);
      const fallback = templates.operate;
      if (state.view === key) applyColumns(fallback, 'operate');
      renderColumnOptions(state.view === 'operate' ? fallback : state.visibleColumns);
      $('[data-products-columns-status]').textContent = '模板已删除';
    } catch (error) {
      $('[data-products-columns-status]').textContent = error.message || '模板删除失败';
    }
  }

  async function saveCustomTemplate() {
    const input = $('[data-products-template-name]');
    const name = input.value.trim();
    const selected = selectedDialogColumns();
    if (!name) {
      $('[data-products-columns-status]').textContent = '请输入模板名称';
      input.focus();
      return;
    }
    if (!selected.length) return;
    const key = `custom_${Date.now()}`;
    const viewTemplates = { ...(state.settings?.view_templates || {}) };
    viewTemplates[key] = { label: name, columns: selected };
    const button = $('[data-products-template-save]');
    button.disabled = true;
    $('[data-products-columns-status]').textContent = '正在保存模板';
    try {
      const response = await DemoApi.domainRequest('/api/settings', jsonOptions({ view_templates: viewTemplates }, 'PUT'));
      ingestViewTemplates(response.data);
      input.value = '';
      applyColumns(selected, key);
      renderTemplateSelect(key);
      $('[data-products-columns-status]').textContent = `模板“${name}”已保存`;
      toast(`已保存模板“${name}”`);
    } catch (error) {
      $('[data-products-columns-status]').textContent = error.message || '模板保存失败';
    } finally {
      button.disabled = false;
    }
  }

  function bindColumnSettings() {
    $('[data-products-columns-open]').addEventListener('click', openColumnsDialog);
    document.querySelectorAll('[data-products-columns-close]').forEach((button) => button.addEventListener('click', closeColumnsDialog));
    $('[data-products-columns-reset]').addEventListener('click', () => renderColumnOptions(templates.operate));
    $('[data-products-columns-select-all]').addEventListener('click', () => renderColumnOptions(columns.map((column) => column.key)));
    $('[data-products-columns-clear-all]').addEventListener('click', () => renderColumnOptions([]));
    $('[data-products-template-apply]').addEventListener('click', () => {
      const key = $('[data-products-template-select]').value;
      renderColumnOptions(templates[key] || templates.operate);
      renderTemplateSelect(key);
    });
    $('[data-products-template-save]').addEventListener('click', () => saveCustomTemplate());
    $('[data-products-columns-apply]').addEventListener('click', () => {
      const selected = selectedDialogColumns();
      if (!selected.length) return;
      applyColumns(selected);
      closeColumnsDialog();
      toast(`已应用 ${selected.length} 个字段`);
    });
    columnsDialog.addEventListener('cancel', (event) => { event.preventDefault(); closeColumnsDialog(); });
    columnsDialog.addEventListener('close', () => {
      columnsDialog.hidden = true;
      columnsReturnFocus?.focus?.();
      columnsReturnFocus = null;
    });
  }

  async function load(detail) {
    const token = ++state.token;
    currentRange(detail);
    renderDataState('loading');
    setRowStatus('加载中');
    try {
      const response = await DemoApi.domainRequest(buildProductsUrl());
      const payload = response.data;
      state.capabilities = response.capabilities || {};
      state.availability = response.availability || 'calculation-failed';
      state.evidence = Array.isArray(response.evidence) ? response.evidence : [];
      if (token !== state.token) return;
      state.rows = asArray(payload, 'rows');
      state.total = Number(payload?.total || state.rows.length);
      state.facets = payload?.facets || { tiers: [], styles: [], statuses: [] };
      state.selected.clear();
       fillSelect('[data-products-tier]', classificationValues('tier'), '全部分层');
       fillSelect('[data-products-style]', classificationValues('style'), '全部风格');
      fillSelect('[data-products-status-filter]', optionValues('status'), '全部状态');
      fillSelect('[data-products-lifecycle-stage]', DemoLabels.enabled('lifecycle_stages').map((item) => item.value), '全部生命周期');
      fillSelect('[data-products-seasonality]', DemoLabels.enabled('seasonal_attributes').map((item) => item.value), '全部季节属性');
      const statusSelect = $('[data-products-status-filter]');
      const allOption = statusSelect.options[0];
      allOption.value = 'all';
      allOption.textContent = '全部状态';
      if (!statusSelect.dataset.initialized) {
        statusSelect.value = 'active';
        statusSelect.dataset.initialized = 'true';
      }
      renderTable();
      if (!state.rows.length) renderDataState('no-data', { message: '当前筛选条件没有商品。' });
      else setStatus(`已按月度口径加载 ${state.rows.length} 件商品，每页 ${state.pageSize} 件${payload?.period ? `；数据月份 ${payload.period}` : ''}`);
    } catch (error) {
      if (token !== state.token) return;
      state.rows = [];
      state.total = 0;
      state.availability = 'calculation-failed';
      state.evidence = [];
      renderOperationsSummary([]);
      updateKpis([]);
      setRowStatus('商品数据加载失败');
      renderDataState('calculation-failed', { message: error.message || '商品数据加载失败', retry: () => load() });
      toast('商品数据加载失败');
    }
    if (window.lucide) window.lucide.createIcons();
  }

  async function updateField(id, key, value) {
    setStatus('正在写入商品字段');
    await DemoApi.domainRequest(`/api/products/${encodeURIComponent(id)}/metadata`, jsonOptions({ field: key, value, operator: '商品运营', reason: `编辑商品${key}` }, 'PUT'));
    const item = state.rows.find((row) => productId(row) === id);
    if (item) item[key] = value;
    renderTable();
    toast('字段已更新');
  }

  async function toggleStar(item, button) {
    const id = productId(item);
    button.disabled = true;
    try {
      const payload = await DemoApi.domainRequest(`/api/products/${encodeURIComponent(id)}/star`, jsonOptions({ product_id: id, operator: '商品运营', reason: '切换商品收藏' }));
      item.starred = Number(payload.data?.starred || 0);
      renderTable();
      toast(item.starred ? '已收藏' : '已取消收藏');
    } finally {
      button.disabled = false;
    }
  }

  async function applyBatchField() {
    const ids = [...state.selected];
    const fieldName = $('[data-products-batch-field]').value;
    const value = $('[data-products-batch-value]').value.trim();
    if (!ids.length || !value) {
      toast('请选择商品并输入批量值');
      return;
    }
    await DemoApi.domainRequest('/api/products/batch-update', jsonOptions({ product_ids: ids, field: fieldName, value, operator: '商品运营', reason: `批量修改${fieldName}` }));
    await rememberClassification(fieldName === 'tier' ? 'tiers' : 'styles', value);
    toast(`已更新 ${ids.length} 件商品`);
    state.selected.clear();
    $('[data-products-batch-value]').value = '';
    await load();
  }

  async function applyBatchTag() {
    const ids = [...state.selected];
    const tag = $('[data-products-batch-tag]').value.trim();
    if (!ids.length || !tag) {
      toast('请选择商品并输入标签');
      return;
    }
    await DemoApi.domainRequest('/api/products/batch-tags', jsonOptions({ product_ids: ids, tag, operator: '商品运营', reason: '批量添加商品标签' }));
    toast(`已为 ${ids.length} 件商品新增标签`);
    $('[data-products-batch-tag]').value = '';
    state.selected.clear();
    updateSelection();
  }

  async function batchStar() {
    const ids = [...state.selected];
    if (!ids.length) {
      toast('请选择商品');
      return;
    }
    const targets = ids.filter((id) => {
      const row = state.rows.find((item) => productId(item) === id);
      return row && Number(row.starred || 0) !== 1;
    });
    if (!targets.length) {
      state.selected.clear();
      renderTable();
      toast('选中商品已全部收藏，已跳过');
      return;
    }
    const results = await Promise.allSettled(targets.map((id) => DemoApi.domainRequest(`/api/products/${encodeURIComponent(id)}/star`, jsonOptions({ product_id: id, starred: 1, operator: '商品运营', reason: '批量收藏商品' }))));
    const ok = results.filter((item) => item.status === 'fulfilled').length;
    const fail = results.length - ok;
    results.forEach((result, index) => {
      if (result.status !== 'fulfilled') return;
      const row = state.rows.find((item) => productId(item) === targets[index]);
      if (row) row.starred = Number(result.value?.data?.starred || 0);
    });
    state.selected.clear();
    renderTable();
    toast(`批量收藏完成：成功 ${ok}，失败 ${fail}，跳过 ${ids.length - targets.length}`);
  }

  function resetFilters() {
    $('[data-products-search]').value = '';
    $('[data-products-tier]').value = '';
    $('[data-products-style]').value = '';
    if ($('[data-products-type]')) $('[data-products-type]').value = '';
    if ($('[data-products-time-node]')) $('[data-products-time-node]').value = '';
    if ($('[data-products-growth-stage]')) $('[data-products-growth-stage]').value = '';
    $('[data-products-status-filter]').value = 'active';
    $('[data-products-sort]').value = 'payment_amount';
    $('[data-products-order]').value = 'desc';
    state.starredOnly = false;
    state.page = 1;
    $('[data-products-starred]').setAttribute('aria-pressed', 'false');
    load();
  }

  function firstPageLoad() {
    state.page = 1;
    load();
  }

  function bindFilters() {
    $('[data-products-search]').addEventListener('input', () => {
      window.clearTimeout(state.searchTimer);
      state.searchTimer = window.setTimeout(firstPageLoad, 300);
    });
    ['[data-products-tier]', '[data-products-style]', '[data-products-type]', '[data-products-time-node]', '[data-products-growth-stage]', '[data-products-status-filter]', '[data-products-sort]', '[data-products-order]', '[data-products-lifecycle-stage]', '[data-products-seasonality]', '[data-products-pending-action]'].forEach((selector) => {
      $(selector).addEventListener('change', firstPageLoad);
    });
    const moreFilters = $('[data-products-more-filters]');
    const moreFiltersToggle = $('[data-products-more-filters-toggle]');
    if (moreFilters && moreFiltersToggle) {
      moreFiltersToggle.addEventListener('click', () => {
        const expanded = moreFilters.hasAttribute('hidden');
        moreFilters.toggleAttribute('hidden', !expanded);
        moreFiltersToggle.setAttribute('aria-expanded', String(expanded));
      });
    }
    $('[data-products-starred]').addEventListener('click', (event) => {
      state.starredOnly = !state.starredOnly;
      event.currentTarget.setAttribute('aria-pressed', String(state.starredOnly));
      renderTable();
      setStatus(state.starredOnly ? '当前页收藏过滤已开启' : '当前页收藏过滤已关闭');
    });
    $('[data-products-reset]').addEventListener('click', resetFilters);
    $('[data-products-prev]').addEventListener('click', () => {
      if (state.page > 1) {
        state.page -= 1;
        load();
      }
    });
    $('[data-products-next]').addEventListener('click', () => {
      if (state.page < Math.ceil(state.total / state.pageSize)) {
        state.page += 1;
        load();
      }
    });
    $('[data-products-page-size]')?.addEventListener('change', (event) => {
      const nextSize = Number(event.currentTarget.value);
      if (![20, 50, 100, 200].includes(nextSize)) return;
      state.pageSize = nextSize;
      state.page = 1;
      load();
    });
    $('[data-products-batch-apply]').addEventListener('click', () => applyBatchField().catch((error) => toast(error.message || '批量更新失败')));
    $('[data-products-batch-tag-apply]').addEventListener('click', () => applyBatchTag().catch((error) => toast(error.message || '批量打标失败')));
    $('[data-products-batch-star]').addEventListener('click', () => batchStar().catch((error) => toast(error.message || '批量收藏失败')));
    document.querySelectorAll('[data-products-view]').forEach((button) => button.addEventListener('click', () => {
      state.view = button.dataset.productsView || 'operate';
      try { localStorage.setItem(storageKey, state.view); } catch {}
      applyColumns(templates[state.view] || templates.operate, state.view);
    }));
  }

  async function exportAllProducts() {
    const range = currentRange();
    const start = range.startDate || '';
    const end = range.endDate || '';
    const response = await fetch('/api/export', jsonOptions({
      type: 'products',
      dim: 'daily',
      start,
      end,
      columns: ['title', 'product_id', ...state.visibleColumns],
      star_only: state.starredOnly,
      ...filters(),
    }));
    if (!response.ok) throw new Error(`导出失败 (${response.status})`);
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url; link.download = `products-${end || start || 'all'}.xlsx`;
    document.body.appendChild(link); link.click(); link.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 0);
    toast('已导出全部当前筛选结果');
  }


  function openProductDetail(item, trigger = null) {
    const id = productId(item);
    window.ProductDetailDialog?.open({ productId: id, title: item?.title || id, trigger: trigger || document.activeElement });
  }

  function initView(configuredDefault = null) {
    state.serverDefaultView = configuredDefault;
    try {
      const preference = JSON.parse(localStorage.getItem(columnsPreferenceStorageKey) || 'null');
      const preferenceMatchesDefault = preference?.serverDefaultView === configuredDefault;
      const storedColumns = preferenceMatchesDefault && Array.isArray(preference?.columns)
        ? preference.columns.filter((key) => columnsByKey.has(key))
        : [];
      if (storedColumns.length) {
        state.visibleColumns = [...new Set(storedColumns)];
        state.view = templates[preference.view] ? preference.view : 'custom';
      } else {
        if (preference && !preferenceMatchesDefault) {
          localStorage.removeItem(columnsPreferenceStorageKey);
          localStorage.removeItem(columnsStorageKey);
          localStorage.removeItem(storageKey);
        }
        state.view = configuredDefault && templates[configuredDefault] ? configuredDefault : 'operate';
        state.visibleColumns = [...(templates[state.view] || templates.operate)];
      }
    } catch {}
    applyFieldView();
  }

  async function loadServerTemplates() {
    try {
      const payload = await DemoApi.domainRequest('/api/settings');
      DemoLabels.setDictionaries(payload.data?.classification_dictionaries);
      const configuredDefault = payload.data?.product_view_template;
      ingestViewTemplates(payload.data);
      renderTemplateSelect(configuredDefault);
      return templates[configuredDefault] ? configuredDefault : null;
    } catch (_) { return null; }
  }

  bindFilters();
  $('[data-products-batch-field]').addEventListener('change', fillBatchOptions);
  fillBatchOptions();
  bindColumnSettings();
  document.querySelector('[data-demo-export]')?.addEventListener('click', (event) => {
    event.stopImmediatePropagation();
    exportAllProducts().catch((error) => toast(error.message));
  }, true);
  const dictionariesReady = loadServerTemplates().then((configuredDefault) => {
    initView(configuredDefault);
    return configuredDefault;
  });
  window.addEventListener('tmall:date-range-change', (event) => {
    state.page = 1;
    dictionariesReady.then(() => load(event.detail));
  });
  window.addEventListener('tmall:refresh', () => dictionariesReady.then(() => load()));
  if (!window.TmallDateRange) dictionariesReady.then(() => load());
})();
