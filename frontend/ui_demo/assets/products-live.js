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
  const columns = [];
  const columnsByKey = new Map();
  function rebuildColumns() {
    const uniqueColumns = [...new Map(columnGroups.flatMap((group) => group.columns).map((column) => [column.key, column])).values()];
    columns.splice(0, columns.length, ...uniqueColumns);
    columnsByKey.clear();
    columns.forEach((column) => columnsByKey.set(column.key, column));
  }
  function classifyBiField(field) {
    const group = String(field.group || '').trim();
    if (group && group !== 'BI 数据源字段') return group;
    const text = `${field.label || ''} ${field.key || ''}`.toLowerCase();
    if (/(销售|成交|支付|订单|买家|退款|利润|毛利|成本|客单)/.test(text)) return '交易与收益';
    if (/(推广|广告|投放|花费|费用|点击|展现|曝光|roi|cpc|cpm)/.test(text)) return '推广与投放';
    if (/(访客|流量|转化|访问|浏览|收藏|加购|搜索|uv|pv)/.test(text)) return '流量与转化';
    if (/(库存|商品|款式|尺码|颜色|供应|采购)/.test(text)) return '商品与库存';
    return '其他 BI 字段';
  }

  function ingestBiFieldCatalog(catalog) {
    const dynamic = Array.isArray(catalog)
      ? catalog.filter((field) => field && field.source_type === 'bi_monthly_overview' && field.key && field.label && Number(field.nonempty_count || 0) > 0)
      : [];
    if (!dynamic.length) return;
    const known = new Set(columnGroups.flatMap((group) => group.columns.map((column) => column.key)));
    const grouped = new Map();
    dynamic
      .filter((field) => !known.has(field.key))
      .forEach((field) => {
        const group = classifyBiField(field);
        if (!grouped.has(group)) grouped.set(group, []);
        grouped.get(group).push({ key: field.key, label: field.label, format: field.format || 'text' });
      });
    grouped.forEach((columns, label) => {
      const group = columnGroups.find((item) => item.label === label);
      if (group) group.columns.push(...columns);
      else columnGroups.push({ label, columns });
    });
    rebuildColumns();
  }
  rebuildColumns();
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
    // 默认列 = operate 模板首版字面量；列设置模块创建后由 init 流程校正
    visibleColumns: ['tier', 'style', 'product_type', 'product_time_node', 'status', 'payment_amount', 'net_sales', 'conversion', 'refund_rate', 'ad_spend', 'roi', 'paid_ipv', 'organic_ipv', 'search_ipv', 'recommend_ipv', 'repurchase_rate'],
    serverDefaultView: null,
    searchTimer: null,
    facets: { tiers: [], styles: [], statuses: [], product_types: [], product_time_nodes: [], product_growth_stages: [] },
    settings: null,
    capabilities: {},
    availability: 'calculation-failed',
    evidence: [],
    urlFilters: null,
    ruleKey: '',
    rules: [],
    ruleBoardExpanded: false,
    copyingIds: false,
    periodDimension: 'daily',
    displayMode: 'list',
    timelineLimit: 3,
    timelineRows: new Map(),
    timelineToken: 0,
  };

  const isMissing = (value) => value === null || value === undefined || value === '';
  const numeric = (value) => isMissing(value) ? null : Number(value);
  const money = (value) => isMissing(value) ? '--' : `¥${Number(value).toLocaleString('zh-CN', { maximumFractionDigits: 2 })}`;
  const number = (value) => isMissing(value) ? '--' : Number(value).toLocaleString('zh-CN');
  const percent = (value) => isMissing(value) ? '--' : `${(Number(value) * 100).toFixed(2)}%`;
  const decimal = (value) => isMissing(value) ? '--' : Number(value).toLocaleString('zh-CN', { maximumFractionDigits: 2 });
  const field = (item, name) => numeric(item?.[name]);
  const productId = (item) => String(item?.product_id || '');
  const salesOf = (item) => numeric(item?.payment_amount) ?? numeric(item?.total_gmv) ?? 0;
  const spendOf = (item) => numeric(item?.ad_spend) ?? numeric(item?.cost) ?? numeric(item?.total_cost) ?? 0;
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
  const filterKeys = ['search', 'tier', 'style', 'product_type', 'product_time_node', 'product_growth_stage', 'status', 'sort', 'order', 'lifecycle_stage', 'seasonality', 'has_pending_action', 'rule_key'];
  const productsQuery = window.TmallRuntime?.createProductsQuery?.({ filterKeys });
  const requestScope = window.TmallRuntime?.createRequestScope?.();
  const eventScope = window.TmallRuntime?.createEventScope?.();
  const filterSelectors = {
    search: '[data-products-search]', tier: '[data-products-tier]', style: '[data-products-style]',
    product_type: '[data-products-type]', product_time_node: '[data-products-time-node]',
    product_growth_stage: '[data-products-growth-stage]', status: '[data-products-status-filter]',
    sort: '[data-products-sort]', order: '[data-products-order]', lifecycle_stage: '[data-products-lifecycle-stage]',
    seasonality: '[data-products-seasonality]', has_pending_action: '[data-products-pending-action]',
  };
  const restoreUrlState = () => {
    const restored = productsQuery?.readUrl?.() || {};
    state.urlFilters = restored.filters || {};
    if (restored.page) state.page = restored.page;
    if (restored.pageSize) state.pageSize = restored.pageSize;
    state.starredOnly = Boolean(restored.starredOnly);
    if (restored.displayMode) state.displayMode = restored.displayMode;
    if (restored.dimension) state.periodDimension = restored.dimension;
  };
  const syncUrlState = () => {
    const url = new URL(window.location.href);
    const current = filters();
    if (productsQuery?.syncUrl) {
      history.replaceState(null, '', productsQuery.syncUrl(url, {
        filters: current,
        page: state.page,
        pageSize: state.pageSize,
        starredOnly: state.starredOnly,
        displayMode: state.displayMode,
        dimension: state.periodDimension,
        timelineLimit: state.timelineLimit,
      }));
      return;
    }
    filterKeys.forEach((key) => {
      if (current[key]) url.searchParams.set(key, current[key]);
      else url.searchParams.delete(key);
    });
    url.searchParams.set('page', String(state.page));
    url.searchParams.set('page_size', String(state.pageSize));
    if (state.starredOnly) url.searchParams.set('starred', '1');
    else url.searchParams.delete('starred');
    url.searchParams.set('product_view', state.displayMode);
    url.searchParams.set('product_dim', state.periodDimension);
    history.replaceState(null, '', url);
  };

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
      ['category_mode', 'period', 'page', 'page_size', 'starred'].forEach((key) => {
        const value = currentUrl.searchParams.get(key);
        if (value) url.searchParams.set(key, value);
      });
      if (!url.searchParams.get('category_mode')) {
        try { url.searchParams.set('category_mode', localStorage.getItem('dashboard.categoryMode') || 'sock'); } catch (_) {}
      }
      if (!url.searchParams.get('period')) url.searchParams.set('period', currentMonthPeriod());
    const currentFilters = filters();
    ['tier', 'lifecycle_stage'].forEach((key) => {
      if (currentFilters[key]) url.searchParams.set(key, currentFilters[key]);
    });
    ['search', 'style', 'product_type', 'product_time_node', 'product_growth_stage', 'status', 'sort', 'order', 'seasonality', 'has_pending_action', 'rule_key'].forEach((key) => {
      if (currentFilters[key]) url.searchParams.set(key, currentFilters[key]);
    });
    return `${url.pathname}${url.search}`;
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

  function currentWeekPeriod() {
    const range = currentRange();
    const raw = range.endDate || range.startDate || new Date().toISOString().slice(0, 10);
    const date = new Date(`${String(raw).slice(0, 10)}T00:00:00`);
    const day = date.getDay();
    date.setDate(date.getDate() - ((day + 6) % 7));
    return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
  }

  // 判断当前日期范围是否应该使用日度数据（单日范围使用日度，其他使用月度）
  function shouldUseDailyData() {
    const range = currentRange();
    if (!range.startDate || !range.endDate) return false;
    return range.startDate === range.endDate;
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
    const current = {
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
      rule_key: state.ruleKey || '',
    };
    if (state.urlFilters) filterKeys.forEach((key) => {
      if (state.urlFilters[key] !== undefined) current[key] = state.urlFilters[key];
    });
    return current;
  }

  function buildProductsUrl() {
    if (productsQuery?.buildApiUrl) {
      const dimension = state.periodDimension;
      return productsQuery.buildApiUrl({
        range: currentRange(),
        page: state.page,
        pageSize: state.pageSize,
        filters: filters(),
        dimension,
        period: dimension === 'weekly' ? currentWeekPeriod() : dimension === 'monthly' ? currentMonthPeriod() : '',
      });
    }
    // 单日范围使用日度数据，其他使用月度数据
    const useDaily = shouldUseDailyData();
    const dim = useDaily ? 'daily' : 'monthly';

    const params = new URLSearchParams({ dim, limit: String(state.pageSize), offset: String((state.page - 1) * state.pageSize) });
    if (useDaily) {
      const range = currentRange();
      if (range.startDate) params.set('start', range.startDate);
      if (range.endDate) params.set('end', range.endDate);
    } else {
      params.set('period', currentMonthPeriod());
    }
    const current = filters();
    filterKeys.forEach((key) => {
      if (current[key]) params.set(key, current[key]);
    });
    return `/api/products?${params.toString()}`;
  }

  async function rememberClassification(group, value) {
    if (!value || DemoLabels.dictionaries[group]?.some((item) => item.value === value)) return;
    const response = await DemoApi.domainRequest('/api/settings');
    const dictionaries = structuredClone(response.data.classification_dictionaries);
    dictionaries[group].push({ value, label: value, enabled: true, system: false });
    await DemoApi.domainRequest('/api/settings', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ classification_dictionaries: dictionaries }) });
    DemoLabels.setDictionaries(dictionaries);
  }

  const columnsDialog = $('[data-products-columns-dialog]');
  // 表格渲染/时间线/移动端摘要/分页选择模块（从本闭包切出，依赖显式注入）
  const tableRender = window.TmallProducts?.createTableRender
    ? window.TmallProducts.createTableRender({
        state, $, number, money, percent, decimal, field,
        productId, salesOf, spendOf, columnsByKey, makeProductPlaceholder,
        openProductDetail, toggleStar, updateField, rememberClassification,
        classificationValues, setStatus, asArray, currentRange,
      })
    : null;
  // 列设置/模板模块（从本闭包切出，依赖显式注入）
  const columnSettings = window.TmallProducts?.createColumnSettings
    ? window.TmallProducts.createColumnSettings({
        state, columns, columnsByKey, columnGroups,
        storageKeys: { view: storageKey, columns: columnsStorageKey, preference: columnsPreferenceStorageKey },
        $, number, toast, jsonOptions, renderTable: tableRender?.renderTable, columnsDialog,
      })
    : null;
  // 经营分群看板/规则详情模块（从本闭包切出，依赖显式注入）
  const ruleBoard = window.TmallProducts?.createRuleBoard
    ? window.TmallProducts.createRuleBoard({
        state, $, number, currentMonthPeriod, syncUrlState, load,
      })
    : null;
  // 货品矩阵地图模块（XMind：产品分层；费比口径=花费÷GSV，2026-10-02 拍板）
  const matrixBoard = window.createProductMatrixBoard
    ? window.createProductMatrixBoard({
        renderDataState: (node, stateName, details) => DemoApi.renderDataState(node, stateName, details),
      })
    : null;
  if (matrixBoard) {
    matrixBoard.bind();
    matrixBoard.load();
    matrixBoard.loadProfitStructure();
    if (eventScope) {
      eventScope.on(window, 'tmall:date-range-change', () => { matrixBoard.load(); matrixBoard.loadProfitStructure(); });
      eventScope.on(window, 'tmall:refresh', () => { matrixBoard.load(); matrixBoard.loadProfitStructure(); });
    } else {
      window.addEventListener('tmall:date-range-change', () => { matrixBoard.load(); matrixBoard.loadProfitStructure(); });
      window.addEventListener('tmall:refresh', () => { matrixBoard.load(); matrixBoard.loadProfitStructure(); });
    }
  }
  // 批量操作/复制选中模块（从本闭包切出，依赖显式注入）
  const batchOps = window.TmallProducts?.createBatchOps
    ? window.TmallProducts.createBatchOps({
        state, $, toast, setStatus, jsonOptions, productId,
        classificationValues, rememberClassification, load,
        renderTable: tableRender?.renderTable, updateSelection: tableRender?.updateSelection,
      })
    : null;
  async function load(detail) {
    const token = ++state.token;
    const request = requestScope?.begin('products');
    currentRange(detail);
    renderDataState('loading');
    tableRender?.setRowStatus('加载中…');
    try {
      const response = await DemoApi.domainRequest(buildProductsUrl(), request ? { signal: request.signal, timeoutMs: 20000 } : undefined);
      const payload = response.data;
      state.capabilities = response.capabilities || {};
      state.availability = response.availability || 'calculation-failed';
      state.evidence = Array.isArray(response.evidence) ? response.evidence : [];
      if (token !== state.token || (request && !request.isCurrent())) return;
      state.rows = asArray(payload, 'rows');
      state.total = Number(payload?.total || state.rows.length);
      if (state.displayMode === 'timeline') await tableRender?.loadTimelineRows(false);
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
      if (state.urlFilters) {
        Object.entries(state.urlFilters).forEach(([key, value]) => {
          const select = $(filterSelectors[key]);
          if (!select) return;
          if (select.tagName === 'SELECT' && [...select.options].some((option) => option.value === value)) select.value = value;
          if (select.tagName !== 'SELECT') select.value = value;
        });
        state.urlFilters = null;
      }
      const pageSizeSelect = $('[data-products-page-size]');
      if (pageSizeSelect) pageSizeSelect.value = String(state.pageSize);
      $('[data-products-starred]')?.setAttribute('aria-pressed', String(state.starredOnly));
      tableRender?.renderTable();
      if (!state.rows.length) renderDataState('no-data', { message: '当前筛选条件没有商品。' });
      else {
        const dimLabel = ({ daily: '日', weekly: '周', monthly: '月' })[state.periodDimension] || '日';
        const periodInfo = state.periodDimension === 'daily'
          ? `${currentRange().startDate} ~ ${currentRange().endDate}`
          : state.periodDimension === 'weekly' ? currentWeekPeriod() : currentMonthPeriod();
        setStatus(`已按${dimLabel}视图加载 ${state.rows.length} 件商品 · ${periodInfo} · 每页 ${state.pageSize} 件`);
      }
    } catch (error) {
      if (error?.name === 'AbortError' || (error?.code === 'REQUEST_TIMEOUT' && request && !request.isCurrent())) return;
      if (token !== state.token || (request && !request.isCurrent())) return;
      state.rows = [];
      state.total = 0;
      state.availability = 'calculation-failed';
      state.evidence = [];
      tableRender?.updateKpis([]);
      tableRender?.setRowStatus('商品数据加载失败');
      renderDataState('calculation-failed', { message: error.message || '商品数据加载失败', retry: () => load() });
      toast('商品数据加载失败');
    }
    request?.finish();
    if (window.lucide) window.lucide.createIcons();
  }

  async function updateField(id, key, value) {
    setStatus('正在写入商品字段');
    try {
      await DemoApi.domainRequest(`/api/products/${encodeURIComponent(id)}/metadata`, jsonOptions({ field: key, value, operator: '商品运营', reason: `编辑商品${key}` }, 'PUT'));
      const item = state.rows.find((row) => productId(row) === id);
      if (item) item[key] = value;
      tableRender?.renderTable();
      toast('字段已更新');
      return true;
    } catch (error) {
      setStatus(error.message || '商品字段更新失败，请重试');
      toast(error.message || '商品字段更新失败');
      return false;
    }
  }

  async function toggleStar(item, button) {
    const id = productId(item);
    button.disabled = true;
    try {
      const payload = await DemoApi.domainRequest(`/api/products/${encodeURIComponent(id)}/star`, jsonOptions({ product_id: id, operator: '商品运营', reason: '切换商品收藏' }));
      item.starred = Number(payload.data?.starred || 0);
      tableRender?.renderTable();
      toast(item.starred ? '已收藏' : '已取消收藏');
    } finally {
      button.disabled = false;
    }
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
    const lifecycleFilter = $('[data-products-lifecycle-stage]');
    const seasonalityFilter = $('[data-products-seasonality]');
    const pendingActionFilter = $('[data-products-pending-action]');
    if (lifecycleFilter) lifecycleFilter.value = '';
    if (seasonalityFilter) seasonalityFilter.value = '';
    if (pendingActionFilter) pendingActionFilter.value = '';
    state.starredOnly = false;
    state.ruleKey = '';
    state.page = 1;
    $('[data-products-starred]').setAttribute('aria-pressed', 'false');
    ruleBoard?.renderRuleCards();
    state.urlFilters = null;
    syncUrlState();
    load();
  }

  function firstPageLoad() {
    state.page = 1;
    load();
  }

  function bindFilters() {
    $('[data-products-search]').addEventListener('input', () => {
      state.urlFilters = null;
      state.page = 1;
      syncUrlState();
      window.clearTimeout(state.searchTimer);
      state.searchTimer = window.setTimeout(firstPageLoad, 300);
    });
    ['[data-products-tier]', '[data-products-style]', '[data-products-type]', '[data-products-time-node]', '[data-products-growth-stage]', '[data-products-status-filter]', '[data-products-sort]', '[data-products-order]', '[data-products-lifecycle-stage]', '[data-products-seasonality]', '[data-products-pending-action]'].forEach((selector) => {
      $(selector).addEventListener('change', () => { state.urlFilters = null; state.page = 1; syncUrlState(); firstPageLoad(); });
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
      state.urlFilters = null;
      syncUrlState();
      event.currentTarget.setAttribute('aria-pressed', String(state.starredOnly));
      tableRender?.renderTable();
      setStatus(state.starredOnly ? '当前页收藏过滤已开启' : '当前页收藏过滤已关闭');
    });
    $('[data-products-reset]').addEventListener('click', resetFilters);
    document.querySelectorAll('[data-products-period]').forEach((button) => button.addEventListener('click', () => {
      const next = button.dataset.productsPeriod;
      if (!['daily', 'weekly', 'monthly'].includes(next) || state.periodDimension === next) return;
      state.periodDimension = next;
      state.page = 1;
      document.querySelectorAll('[data-products-period]').forEach((item) => item.setAttribute('aria-pressed', String(item.dataset.productsPeriod === next)));
      syncUrlState();
      load();
    }));
    document.querySelectorAll('[data-products-mode]').forEach((button) => button.addEventListener('click', () => {
      const next = button.dataset.productsMode;
      if (!['list', 'timeline'].includes(next) || state.displayMode === next) return;
      state.displayMode = next;
      state.page = 1;
      state.timelineRows = new Map();
      try { localStorage.setItem('tmall-products-display-mode', next); } catch {}
      document.querySelectorAll('[data-products-mode]').forEach((item) => item.setAttribute('aria-pressed', String(item.dataset.productsMode === next)));
      syncUrlState();
      load();
    }));
    document.querySelectorAll('[data-products-timeline-limit]').forEach((button) => button.addEventListener('click', () => {
      const next = Number(button.dataset.productsTimelineLimit);
      if (![3, 6, 12].includes(next) || state.timelineLimit === next) return;
      state.timelineLimit = next;
      syncUrlState();
      tableRender?.loadTimelineRows().catch((error) => toast(error.message || '周期明细加载失败'));
    }));
    $('[data-products-prev]').addEventListener('click', () => {
      if (state.page > 1) {
        state.page -= 1;
        syncUrlState();
        load();
      }
    });
    $('[data-products-next]').addEventListener('click', () => {
      if (state.page < Math.ceil(state.total / state.pageSize)) {
        state.page += 1;
        syncUrlState();
        load();
      }
    });
    $('[data-products-page-size]')?.addEventListener('change', (event) => {
      const nextSize = Number(event.currentTarget.value);
      if (![20, 50, 100, 200].includes(nextSize)) return;
      state.pageSize = nextSize;
      state.page = 1;
      state.urlFilters = null;
      syncUrlState();
      load();
    });
    $('[data-products-batch-apply]').addEventListener('click', () => batchOps?.applyBatchField().catch((error) => toast(error.message || '批量更新失败')));
    $('[data-products-batch-tag-apply]').addEventListener('click', () => batchOps?.applyBatchTag().catch((error) => toast(error.message || '批量打标失败')));
    $('[data-products-batch-star]').addEventListener('click', () => batchOps?.batchStar().catch((error) => toast(error.message || '批量收藏失败')));
    $('[data-products-batch-copy]').addEventListener('click', (event) => batchOps?.copySelectedProductIds(event.currentTarget));
    document.querySelectorAll('[data-products-view]').forEach((button) => button.addEventListener('click', () => {
      state.view = button.dataset.productsView || 'operate';
      try { localStorage.setItem(storageKey, state.view); } catch {}
      columnSettings.applyColumns(columnSettings.templates[state.view] || columnSettings.templates.operate, state.view);
    }));
  }

  async function exportAllProducts() {
    const range = currentRange();
    const start = range.startDate || '';
    const end = range.endDate || '';
    const exportPayload = {
      type: 'products',
      dim: state.periodDimension,
      period: '',
      start,
      end,
      category_mode: (() => { try { return localStorage.getItem('dashboard.categoryMode') || 'sock'; } catch { return 'sock'; } })(),
      columns: ['title', 'product_id', ...state.visibleColumns],
      star_only: state.starredOnly,
      ...filters(),
    };
    if (state.periodDimension === 'weekly') {
      exportPayload.period = currentWeekPeriod();
      exportPayload.start = '';
      exportPayload.end = '';
    } else if (state.periodDimension === 'monthly') {
      exportPayload.period = currentMonthPeriod();
      exportPayload.start = '';
      exportPayload.end = '';
    }
    const response = await fetch('/api/export', jsonOptions(exportPayload));
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
    if (!id) {
      toast('当前商品缺少商品 ID');
      return;
    }
    const sourceRule = state.rules.find((rule) => rule.key === state.ruleKey);
    window.ProductDetailDialog?.open({ productId: id,
      title: item?.title || id,
      workbenchUrl: buildProductDetailUrl(item),
      sourceRule: sourceRule ? { key: sourceRule.key, name: sourceRule.name, period: sourceRule.period } : null,
      trigger: trigger || document.activeElement,
    });
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
        state.view = columnSettings.templates[preference.view] ? preference.view : 'custom';
      } else {
        if (preference && !preferenceMatchesDefault) {
          localStorage.removeItem(columnsPreferenceStorageKey);
          localStorage.removeItem(columnsStorageKey);
          localStorage.removeItem(storageKey);
        }
        state.view = configuredDefault && columnSettings.templates[configuredDefault] ? configuredDefault : 'operate';
        state.view = columnSettings.templates[state.view] ? state.view : 'operate';
        state.visibleColumns = [...(columnSettings.templates[state.view] || columnSettings.templates.operate)];
      }
    } catch {}
    tableRender?.applyFieldView();
  }

  async function loadServerTemplates() {
    try {
      const payload = await DemoApi.domainRequest('/api/settings');
      DemoLabels.setDictionaries(payload.data?.classification_dictionaries);
      ingestBiFieldCatalog(payload.data?.field_catalog?.products);
      const configuredDefault = payload.data?.product_view_template;
      columnSettings.ingestViewTemplates(payload.data);
      columnSettings.renderTemplateSelect(configuredDefault);
      return columnSettings.templates[configuredDefault] ? configuredDefault : null;
    } catch (_) { return null; }
  }

  restoreUrlState();
  const initialDimension = new URL(window.location.href).searchParams.get('product_dim');
  const initialDisplayMode = new URL(window.location.href).searchParams.get('product_view');
  if (['list', 'timeline'].includes(initialDisplayMode)) state.displayMode = initialDisplayMode;
  else {
    try {
      const savedDisplayMode = localStorage.getItem('tmall-products-display-mode');
      if (['list', 'timeline'].includes(savedDisplayMode)) state.displayMode = savedDisplayMode;
    } catch {}
  }
  if (['daily', 'weekly', 'monthly'].includes(initialDimension)) state.periodDimension = initialDimension;
  const initialTimelineLimit = new URL(window.location.href).searchParams.get('timeline_limit');
  if ([3, 6, 12].includes(Number(initialTimelineLimit))) state.timelineLimit = Number(initialTimelineLimit);
  else if (productsQuery?.readUrl?.().timelineLimit) state.timelineLimit = productsQuery.readUrl().timelineLimit;
  document.querySelectorAll('[data-products-mode]').forEach((button) => button.setAttribute('aria-pressed', String(button.dataset.productsMode === state.displayMode)));
  document.querySelectorAll('[data-products-period]').forEach((button) => button.setAttribute('aria-pressed', String(button.dataset.productsPeriod === state.periodDimension)));
  document.querySelectorAll('[data-products-timeline-limit]').forEach((button) => button.setAttribute('aria-pressed', String(Number(button.dataset.productsTimelineLimit) === state.timelineLimit)));
  tableRender?.updateTimelineControls();
  state.ruleKey = state.urlFilters?.rule_key || new URL(window.location.href).searchParams.get('rule_key') || '';
  bindFilters();
  $('[data-products-batch-field]').addEventListener('change', () => batchOps?.fillBatchOptions());
  batchOps?.fillBatchOptions();
  columnSettings.bindColumnSettings();
  ruleBoard?.bindRuleBoard();
  document.querySelector('[data-demo-export]')?.addEventListener('click', (event) => {
    event.stopImmediatePropagation();
    exportAllProducts().catch((error) => toast(error.message));
  }, true);
  const dictionariesReady = loadServerTemplates().then((configuredDefault) => {
    initView(configuredDefault);
    return configuredDefault;
  });
  const onDateRangeChange = (event) => {
    state.page = 1;
    dictionariesReady.then(() => { ruleBoard?.loadRuleCards(); load(event.detail); });
  };
  const onRefresh = () => dictionariesReady.then(() => { ruleBoard?.loadRuleCards(); load(); });
  if (eventScope) {
    eventScope.on(window, 'tmall:date-range-change', onDateRangeChange);
    eventScope.on(window, 'tmall:refresh', onRefresh);
  } else {
    window.addEventListener('tmall:date-range-change', onDateRangeChange);
    window.addEventListener('tmall:refresh', onRefresh);
  }
  dictionariesReady.then(() => { ruleBoard?.loadRuleCards(); load(); });
})();
