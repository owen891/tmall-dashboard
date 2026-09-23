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
  function copyWithFallback(text) {
    const textarea = document.createElement('textarea');
    textarea.value = text;
    textarea.setAttribute('readonly', '');
    textarea.style.position = 'fixed';
    textarea.style.opacity = '0';
    document.body.appendChild(textarea);
    textarea.select();
    const copied = document.execCommand('copy');
    textarea.remove();
    if (!copied) throw new Error('当前浏览器不支持复制');
  }

  async function copySelectedProductIds(button) {
    if (state.copyingIds) return;
    const ids = [...state.selected].map((id) => String(id || '').trim()).filter(Boolean);
    if (!ids.length) {
      toast('请选择商品');
      return;
    }
    state.copyingIds = true;
    button.disabled = true;
    button.setAttribute('aria-busy', 'true');
    const text = ids.join('\n');
    try {
      if (navigator.clipboard?.writeText) {
        try {
          await navigator.clipboard.writeText(text);
        } catch (_) {
          copyWithFallback(text);
        }
      } else {
        copyWithFallback(text);
      }
      setStatus(`已复制 ${ids.length} 个商品 ID`);
      toast(`已复制 ${ids.length} 个商品 ID`);
    } catch (error) {
      setStatus(error.message || '复制商品 ID 失败，请重试');
      toast(error.message || '复制商品 ID 失败，请重试');
    } finally {
      state.copyingIds = false;
      button.removeAttribute('aria-busy');
      updateSelection();
    }
  }

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

  // missing facts are not zero: status and issue copy must stay explainable.
  function productHealth(item) {
    if (!Number(item?.has_data || 0)) return { label: '不可分析', tone: 'muted', reason: '缺少商品月度事实', sortValue: 2 };
    if (Number(item?.has_pending_action || 0)) return { label: '需处理', tone: 'warning', reason: '存在待执行运营动作', sortValue: 1 };
    return { label: '健康', tone: 'success', reason: '当前范围内暂无待处理规则', sortValue: 0 };
  }

  function renderRuleCards() {
    const root = $('[data-product-rule-groups]');
    const summary = $('[data-product-rule-summary]');
    const status = $('[data-product-rule-status]');
    const clear = $('[data-product-rule-clear]');
    if (!root) return;
    const toggle = $('[data-product-rule-toggle]');
    state.ruleBoardExpanded = Boolean(state.ruleKey) || state.ruleBoardExpanded;
    root.replaceChildren();
    root.hidden = !state.ruleBoardExpanded;
    if (summary) {
      summary.replaceChildren();
      state.rules.slice(0, 5).forEach((rule) => {
        const item = document.createElement('span');
        item.className = `product-rule-summary-item product-rule-summary-item--${rule.severity || 'info'}`;
        item.textContent = `${rule.name} ${number(rule.matched_count)}件`;
        summary.appendChild(item);
      });
      summary.hidden = state.ruleBoardExpanded || !state.rules.length;
    }
    if (toggle) {
      toggle.textContent = state.ruleBoardExpanded ? '收起分群详情' : '展开分群详情';
      toggle.setAttribute('aria-expanded', String(state.ruleBoardExpanded));
    }
    const groups = new Map();
    state.rules.forEach((rule) => {
      if (!groups.has(rule.group)) groups.set(rule.group, []);
      groups.get(rule.group).push(rule);
    });
    groups.forEach((rules, groupName) => {
      const section = document.createElement('section');
      section.className = 'product-rule-group';
      const heading = document.createElement('h4');
      heading.textContent = groupName;
      const cards = document.createElement('div');
      cards.className = 'product-rule-group__cards';
      rules.forEach((rule) => {
        const card = document.createElement('article');
        card.className = `product-rule-card product-rule-card--${rule.severity || 'info'}`;
        card.classList.toggle('is-active', state.ruleKey === rule.key);
        const title = document.createElement('strong');
        title.textContent = rule.name;
        const desc = document.createElement('span');
        desc.className = 'product-rule-card__description';
        desc.textContent = rule.description;
        const meta = document.createElement('span');
        meta.className = 'product-rule-card__meta';
        const share = rule.share == null ? '--' : `${(Number(rule.share) * 100).toFixed(1)}%`;
        meta.textContent = `${number(rule.matched_count)} 件 · ${share}`;
        const actions = document.createElement('div');
        actions.className = 'product-rule-card__actions';
        const apply = document.createElement('button');
        apply.type = 'button';
        apply.className = 'ui-button ui-button--small';
        apply.textContent = state.ruleKey === rule.key ? '取消筛选' : '查看商品';
        apply.setAttribute('aria-pressed', String(state.ruleKey === rule.key));
        apply.addEventListener('click', () => {
          state.ruleKey = state.ruleKey === rule.key ? '' : rule.key;
          state.page = 1;
          state.urlFilters = null;
          syncUrlState();
          renderRuleCards();
          load();
        });
        const inspect = document.createElement('button');
        inspect.type = 'button';
        inspect.className = 'ui-button ui-button--ghost ui-button--small';
        inspect.innerHTML = '<i data-lucide="file-search"></i><span>规则详情</span>';
        inspect.addEventListener('click', () => openRuleDetail(rule));
        actions.append(apply, inspect);
        card.append(title, desc, meta, actions);
        cards.appendChild(card);
      });
      section.append(heading, cards);
      root.appendChild(section);
    });
    if (!state.rules.length) root.innerHTML = '<p class="panel__hint">当前周期暂无可用经营分群</p>';
    if (clear) clear.hidden = !state.ruleKey;
    const active = state.rules.find((rule) => rule.key === state.ruleKey);
    if (status) status.textContent = active ? `已应用分群：${active.name} · ${active.description}` : '按当前周期经营事实识别需要关注的商品集合';
  }

  let selectedRuleDetail = null;
  function ruleConditionText(condition) {
    if (!condition) return '无额外条件';
    const value = condition.value == null ? '--' : condition.value;
    const displayValue = condition.unit === '%' && typeof condition.value === 'number'
      ? `${(condition.value * 100).toFixed(condition.value * 100 % 1 ? 1 : 0)}%`
      : `${value}${condition.unit === '元' || condition.unit === '人' ? condition.unit : ''}`;
    return `${condition.label || condition.field} ${condition.operator} ${displayValue}`;
  }

  function openRuleDetail(rule) {
    selectedRuleDetail = rule;
    const dialog = $('[data-product-rule-detail-dialog]');
    if (!dialog) return;
    $('[data-product-rule-detail-title]').textContent = `${rule.name} · 规则详情`;
    $('[data-product-rule-detail-description]').textContent = rule.description || '查看规则定义、字段口径和当前周期命中证据';
    const summary = $('[data-product-rule-detail-summary]');
    summary.replaceChildren(...[
      ['规则类型', ({ segmentation: '分群规则', alert: '预警规则', diagnosis: '诊断规则', recommendation: '动作建议规则' }[rule.rule_type] || '--')],
      ['规则版本', rule.version || '--'], ['统计周期', rule.period || '--'],
      ['命中商品', `${number(rule.matched_count)} 件`], ['覆盖占比', rule.share == null ? '--' : `${(Number(rule.share) * 100).toFixed(1)}%`],
    ].map(([label, value]) => {
      const item = document.createElement('div'); item.className = 'product-rule-detail-dialog__summary-item';
      const name = document.createElement('span'); name.textContent = label;
      const val = document.createElement('strong'); val.textContent = value;
      item.append(name, val); return item;
    }));
    const conditions = $('[data-product-rule-detail-conditions]');
    const conditionList = Array.isArray(rule.conditions) ? rule.conditions : [];
    conditions.replaceChildren(...(conditionList.length ? conditionList : [{ label: '规则条件', field: 'SQL', operator: '=', value: rule.condition || '--' }]).map((condition) => {
      const item = document.createElement('div'); item.className = 'product-rule-detail-dialog__condition';
      item.textContent = ruleConditionText(condition); return item;
    }));
    const evidence = $('[data-product-rule-detail-evidence]');
    const evidenceSummary = rule.evidence_summary || {};
    evidence.replaceChildren(...[
      ['来源表', evidenceSummary.source || 'monthly_data'], ['数据粒度', evidenceSummary.grain || 'product-month'],
      ['覆盖商品', number(evidenceSummary.eligible_product_count ?? rule.eligible_count)],
      ['命中集合', number(evidenceSummary.matched_product_count ?? rule.matched_count)],
      ['覆盖状态', evidenceSummary.coverage || rule.availability || '--'],
    ].map(([label, value]) => {
      const item = document.createElement('div'); item.className = 'status-list__item';
      const left = document.createElement('span'); left.className = 'status-list__label'; left.textContent = label;
      const right = document.createElement('span'); right.className = 'status-list__value'; right.textContent = value;
      item.append(left, right); return item;
    }));
    $('[data-product-rule-detail-query]').textContent = JSON.stringify({
      rule_key: rule.key, period: rule.period, category_mode: state.categoryMode || null,
      status: $('[data-products-status-filter]')?.value || 'active', matched_product_ids: rule.matched_product_ids || [],
    }, null, 2);
    dialog.hidden = false;
    dialog.showModal?.();
    window.lucide?.createIcons();
  }

  function closeRuleDetail() {
    const dialog = $('[data-product-rule-detail-dialog]');
    if (!dialog) return;
    dialog.close?.(); dialog.hidden = true; selectedRuleDetail = null;
  }

  async function loadRuleCards() {
    try {
      const params = new URLSearchParams({ period: currentMonthPeriod(), status: $('[data-products-status-filter]')?.value || 'active' });
      try { params.set('category_mode', localStorage.getItem('dashboard.categoryMode') || 'sock'); } catch (_) { params.set('category_mode', 'sock'); }
      const response = await DemoApi.domainRequest(`/api/product-overview/rule-results?${params}`);
      state.rules = Array.isArray(response.data?.rules) ? response.data.rules : [];
      renderRuleCards();
    } catch (error) {
      state.rules = [];
      renderRuleCards();
      const status = $('[data-product-rule-status]');
      if (status) status.textContent = error.message || '经营分群加载失败';
    }
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

  function setRowStatus(message) {
    const body = $('[data-products-body]');
    body.replaceChildren();
    const row = document.createElement('tr');
    const cell = row.insertCell();
    cell.colSpan = state.visibleColumns.length + 3;
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

  function metricBarValue(item, key) {
    const value = key === 'payment_amount' ? salesOf(item) : key === 'ad_spend' ? spendOf(item) : field(item, key);
    return Number.isFinite(value) && value > 0 ? value : 0;
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
    item.className = 'ui-badge ui-badge--muted';
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
      const updated = await updateField(productId(item), key, input.value.trim());
      if (updated) await rememberClassification(dictionaryGroup, input.value.trim());
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
      ['select', ''], ['title', '商品']
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
    if (state.displayMode === 'timeline') {
      const period = document.createElement('th');
      period.dataset.fieldKey = 'period';
      period.textContent = state.periodDimension === 'daily' ? '日期' : state.periodDimension === 'weekly' ? '周起始' : '月份';
      head.appendChild(period);
      const trend = document.createElement('th');
      trend.dataset.fieldKey = 'timeline-trend';
      trend.textContent = '环比';
      trend.className = 'num';
      head.appendChild(trend);
    }
    const displayColumns = state.displayMode === 'timeline' ? timelineColumns() : state.visibleColumns;
    displayColumns.forEach((key) => {
      if (state.displayMode === 'timeline' && key === 'trend_change') return;
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

  function updateTimelineControls() {
    document.body.dataset.productsDisplayMode = state.displayMode;
    const tools = $('[data-products-timeline-tools]');
    const fieldControls = document.querySelector('.product-control-group--fields');
    const columnsButton = $('[data-products-columns-open]');
    if (!tools) return;
    tools.hidden = state.displayMode !== 'timeline';
    if (fieldControls) fieldControls.hidden = state.displayMode === 'timeline';
    // Column settings apply to both list and timeline metrics.
    if (columnsButton) columnsButton.hidden = false;
    document.querySelectorAll('[data-products-timeline-limit]').forEach((button) => {
      button.setAttribute('aria-pressed', String(Number(button.dataset.productsTimelineLimit) === state.timelineLimit));
    });
  }

  function renderTable() {
    updateTimelineControls();
    if (state.displayMode === 'timeline') return renderTimelineTable();
    renderHeader();
    const body = $('[data-products-body]');
    body.replaceChildren();
    const rows = visibleRows();
    const metricMax = {};
    state.visibleColumns.forEach((key) => {
      const column = columnsByKey.get(key);
      if (column?.format) metricMax[key] = Math.max(...rows.map((item) => metricBarValue(item, key)), 0);
    });
    updateKpis(rows);
    if (!rows.length) {
      setRowStatus(state.starredOnly ? '当前页没有收藏商品' : '当前条件暂无商品');
      renderMobileSummary(rows);
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
      addCell(row, check, '', 'select');

      const identity = document.createElement('div');
      identity.className = 'product-identity';
      let thumbnail;
      const thumbnailUrl = String(item.image_url || '').trim();
      if (item.image_url) {
        thumbnail = document.createElement('img');
        thumbnail.className = 'product-thumb';
        thumbnail.alt = '';
        thumbnail.loading = 'lazy';
        thumbnail.referrerPolicy = 'no-referrer';
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
        thumbnail.referrerPolicy = 'no-referrer';
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
      titleButton.title = item.title || '未命名商品';
      titleButton.setAttribute('aria-label', `查看商品详情：${item.title || id || '未命名商品'}`);
      titleButton.addEventListener('click', () => openProductDetail(item, titleButton));
      const sub = document.createElement('div');
      sub.className = 'product-title__meta';
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
      const idLabel = document.createElement('span');
      idLabel.textContent = id || '--';
      title.append(titleButton, sub);
      sub.append(star, idLabel);
      identity.append(thumbnail, title);
      addCell(row, identity, '', 'title');

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
        else {
          const cell = addCell(row, formatColumnValue(item, column), column.format ? 'num metric-bar-cell' : '', key);
          if (column.format && metricMax[key] > 0) {
            cell.style.setProperty('--metric-fill', `${Math.round((metricBarValue(item, key) / metricMax[key]) * 100)}%`);
          }
        }
      });

      body.appendChild(row);
    });
    renderMobileSummary(rows);
    applyFieldView();
    updatePagination();
    updateSelection();
    window.lucide?.createIcons();
  }

  function timelineColumns() {
    const monthlyUnsupported = new Set(['paid_ipv', 'organic_ipv', 'search_ipv', 'recommend_ipv']);
    const selectedMetrics = state.visibleColumns.filter((key) => {
      const column = columnsByKey.get(key);
      return key !== 'trend_change'
        && Boolean(column?.format)
        && !(state.periodDimension === 'monthly' && monthlyUnsupported.has(key));
    });
    const fallback = ['payment_amount', 'net_sales', 'visitors', 'conversion', 'refund_rate', 'expense_ratio', 'ad_spend', 'roi', 'buyers', 'avg_order_value', 'repurchase_rate'];
    return [...new Set(selectedMetrics.length ? selectedMetrics : fallback)].filter((key) => columnsByKey.has(key));
  }

  function renderTimelineProductCells(row, item, rowSpan) {
    const id = productId(item);
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
    const selectCell = addCell(row, check, '', 'select');
    if (rowSpan > 1) selectCell.rowSpan = rowSpan;

    const identity = document.createElement('div');
    identity.className = 'product-identity';
    const thumbnailUrl = String(item.image_url || '').trim();
    const thumbnail = thumbnailUrl ? document.createElement('img') : makeProductPlaceholder(item, id);
    if (thumbnailUrl) {
      thumbnail.className = 'product-thumb';
      thumbnail.alt = '';
      thumbnail.loading = 'lazy';
      thumbnail.referrerPolicy = 'no-referrer';
      thumbnail.src = thumbnailUrl;
      thumbnail.addEventListener('error', () => thumbnail.replaceWith(makeProductPlaceholder(item, id)), { once: true });
    }
    const title = document.createElement('div');
    title.className = 'product-title';
    const titleButton = document.createElement('button');
    titleButton.type = 'button';
    titleButton.className = 'product-title__link';
    titleButton.textContent = item.title || '未命名商品';
    titleButton.title = item.title || '未命名商品';
    titleButton.setAttribute('aria-label', `查看商品详情：${item.title || id || '未命名商品'}`);
    titleButton.addEventListener('click', () => openProductDetail(item, titleButton));
    const sub = document.createElement('div');
    sub.className = 'product-title__meta';
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
    const idLabel = document.createElement('span');
    idLabel.textContent = id || '--';
    title.append(titleButton, sub);
    sub.append(star, idLabel);
    identity.append(thumbnail, title);
    const titleCell = addCell(row, identity, '', 'title');
    if (rowSpan > 1) titleCell.rowSpan = rowSpan;

  }

  function appendTimelineMetrics(row, item, detail, metricMax) {
    addCell(row, detail.period || '--', 'product-timeline-period', 'period');
    const trendCell = addCell(row, '', 'num product-timeline-trend', 'timeline-trend');
    const trend = detail.trend_change;
    if (trend == null || !Number.isFinite(Number(trend))) {
      trendCell.textContent = '--';
    } else {
      const value = Number(trend);
      const tone = value > 0 ? 'up' : value < 0 ? 'down' : 'flat';
      trendCell.classList.add(`product-timeline-trend--${tone}`);
      trendCell.innerHTML = `<i data-lucide="${tone === 'up' ? 'trending-up' : tone === 'down' ? 'trending-down' : 'minus'}"></i><span>${percent(value)}</span>`;
    }
    timelineColumns().forEach((key) => {
      const column = columnsByKey.get(key);
      if (!column || key === 'trend_change') return;
      const valueItem = { ...item, ...detail };
      const cell = addCell(row, formatColumnValue(valueItem, column), column.format ? 'num metric-bar-cell' : '', key);
      if (column.format && metricMax[key] > 0) {
        cell.style.setProperty('--metric-fill', `${Math.round((metricBarValue(valueItem, key) / metricMax[key]) * 100)}%`);
      }
    });
  }

  function renderTimelineTable() {
    renderHeader();
    const body = $('[data-products-body]');
    body.replaceChildren();
    const rows = visibleRows();
    const columns = timelineColumns();
    updateTimelineControls();
    updateKpis(rows);
    if (!rows.length) {
      setRowStatus(state.starredOnly ? '当前页没有收藏商品' : '当前条件暂无商品');
      renderMobileSummary(rows);
      applyFieldView();
      updatePagination();
      updateSelection();
      return;
    }
    const metricMax = {};
    columns.forEach((key) => {
      const column = columnsByKey.get(key);
      if (column?.format) {
        metricMax[key] = Math.max(...rows.flatMap((item) => state.timelineRows.get(productId(item)) || []).map((item) => metricBarValue(item, key)), 0);
      }
    });
    rows.forEach((item) => {
      const id = productId(item);
      const details = state.timelineRows.get(id) || [];
      const periods = details.length ? details : [{ product_id: id, period: '--' }];
      periods.forEach((detail, index) => {
        const row = document.createElement('tr');
        row.className = `product-timeline-row ${index === 0 ? 'product-timeline-row--first' : 'product-timeline-row--continuation'}`;
        row.dataset.productId = id;
        if (index === 0) renderTimelineProductCells(row, item, periods.length);
        appendTimelineMetrics(row, item, detail, metricMax);
        body.appendChild(row);
      });
    });
    renderMobileSummary(rows);
    applyFieldView();
    updatePagination();
    updateSelection();
    window.lucide?.createIcons();
  }

  async function loadTimelineRows(renderAfter = true) {
    const token = ++state.timelineToken;
    const ids = visibleRows().map(productId).filter(Boolean);
    state.timelineRows = new Map();
    if (!ids.length) return;
    const range = currentRange();
    const params = new URLSearchParams({
      dim: state.periodDimension,
      product_ids: ids.join(','),
      limit_periods: String(state.timelineLimit),
    });
    if (state.periodDimension !== 'monthly' && range.startDate) params.set('start', range.startDate);
    if (range.endDate) params.set('end', range.endDate);
    try {
      const response = await DemoApi.domainRequest(`/api/products/timeline?${params.toString()}`);
      if (token !== state.timelineToken) return;
      const grouped = new Map();
      asArray(response.data, 'rows').forEach((row) => {
        if (!grouped.has(String(row.product_id))) grouped.set(String(row.product_id), []);
        grouped.get(String(row.product_id)).push(row);
      });
      const maxPeriods = state.timelineLimit;
      grouped.forEach((items, id) => grouped.set(id, items.slice(0, maxPeriods)));
      state.timelineRows = grouped;
      if (renderAfter) renderTable();
    } catch (error) {
      if (token !== state.timelineToken) return;
      setStatus(error.message || '周期明细加载失败');
      if (renderAfter) renderTable();
    }
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
    const copyButton = $('[data-products-batch-copy]');
    if (copyButton) copyButton.disabled = state.selected.size === 0 || state.copyingIds;
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
      detail.className = 'ui-button ui-button--ghost';
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
      columnSelector = TmallUI.fieldSelector({
        root: $('[data-products-field-selector]'),
        ...config,
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
    const request = requestScope?.begin('products');
    currentRange(detail);
    renderDataState('loading');
    setRowStatus('加载中…');
    try {
      const response = await DemoApi.domainRequest(buildProductsUrl(), request ? { signal: request.signal, timeoutMs: 20000 } : undefined);
      const payload = response.data;
      state.capabilities = response.capabilities || {};
      state.availability = response.availability || 'calculation-failed';
      state.evidence = Array.isArray(response.evidence) ? response.evidence : [];
      if (token !== state.token || (request && !request.isCurrent())) return;
      state.rows = asArray(payload, 'rows');
      state.total = Number(payload?.total || state.rows.length);
      if (state.displayMode === 'timeline') await loadTimelineRows(false);
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
      renderTable();
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
      updateKpis([]);
      setRowStatus('商品数据加载失败');
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
      renderTable();
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
      renderTable();
      toast(item.starred ? '已收藏' : '已取消收藏');
    } finally {
      button.disabled = false;
    }
  }

  async function applyBatchField() {
    if (state.batchMutation) return;
    state.batchMutation = true;
    const ids = [...state.selected];
    const fieldName = $('[data-products-batch-field]').value;
    const value = $('[data-products-batch-value]').value.trim();
    if (!ids.length || !value) {
      toast('请选择商品并输入批量值');
      state.batchMutation = false;
      return;
    }
    try {
      await DemoApi.domainRequest('/api/products/batch-update', jsonOptions({ product_ids: ids, field: fieldName, value, operator: '商品运营', reason: `批量修改${fieldName}` }));
      await rememberClassification(fieldName === 'tier' ? 'tiers' : 'styles', value);
      toast(`已更新 ${ids.length} 件商品`);
      state.selected.clear();
      $('[data-products-batch-value]').value = '';
      await load();
    } finally { state.batchMutation = false; }
  }

  async function applyBatchTag() {
    if (state.batchMutation) return;
    state.batchMutation = true;
    const ids = [...state.selected];
    const tag = $('[data-products-batch-tag]').value.trim();
    if (!ids.length || !tag) {
      toast('请选择商品并输入标签');
      state.batchMutation = false;
      return;
    }
    try {
      await DemoApi.domainRequest('/api/products/batch-tags', jsonOptions({ product_ids: ids, tag, operator: '商品运营', reason: '批量添加商品标签' }));
      toast(`已为 ${ids.length} 件商品新增标签`);
      $('[data-products-batch-tag]').value = '';
      state.selected.clear();
      updateSelection();
    } finally { state.batchMutation = false; }
  }

  async function batchStar() {
    if (state.batchMutation) return;
    state.batchMutation = true;
    const ids = [...state.selected];
    if (!ids.length) {
      toast('请选择商品');
      state.batchMutation = false;
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
      state.batchMutation = false;
      return;
    }
    try {
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
    } finally { state.batchMutation = false; }
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
    renderRuleCards();
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
      renderTable();
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
      loadTimelineRows().catch((error) => toast(error.message || '周期明细加载失败'));
    }));
    $('[data-product-rule-clear]')?.addEventListener('click', () => {
      state.ruleKey = '';
      state.ruleBoardExpanded = false;
      state.page = 1;
      state.urlFilters = null;
      syncUrlState();
      renderRuleCards();
      load();
    });
    $('[data-product-rule-toggle]')?.addEventListener('click', () => {
      state.ruleBoardExpanded = !state.ruleBoardExpanded;
      renderRuleCards();
    });
    document.querySelectorAll('[data-product-rule-detail-close]').forEach((button) => button.addEventListener('click', closeRuleDetail));
    $('[data-product-rule-detail-apply]')?.addEventListener('click', () => {
      if (!selectedRuleDetail) return;
      state.ruleKey = selectedRuleDetail.key;
      state.page = 1;
      state.urlFilters = null;
      syncUrlState();
      closeRuleDetail();
      renderRuleCards();
      load();
    });
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
    $('[data-products-batch-apply]').addEventListener('click', () => applyBatchField().catch((error) => toast(error.message || '批量更新失败')));
    $('[data-products-batch-tag-apply]').addEventListener('click', () => applyBatchTag().catch((error) => toast(error.message || '批量打标失败')));
    $('[data-products-batch-star]').addEventListener('click', () => batchStar().catch((error) => toast(error.message || '批量收藏失败')));
    $('[data-products-batch-copy]').addEventListener('click', (event) => copySelectedProductIds(event.currentTarget));
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
      showToast('当前商品缺少商品 ID');
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
      ingestBiFieldCatalog(payload.data?.field_catalog?.products);
      const configuredDefault = payload.data?.product_view_template;
      ingestViewTemplates(payload.data);
      renderTemplateSelect(configuredDefault);
      return templates[configuredDefault] ? configuredDefault : null;
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
  updateTimelineControls();
  state.ruleKey = state.urlFilters?.rule_key || new URL(window.location.href).searchParams.get('rule_key') || '';
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
  const onDateRangeChange = (event) => {
    state.page = 1;
    dictionariesReady.then(() => { loadRuleCards(); load(event.detail); });
  };
  const onRefresh = () => dictionariesReady.then(() => { loadRuleCards(); load(); });
  if (eventScope) {
    eventScope.on(window, 'tmall:date-range-change', onDateRangeChange);
    eventScope.on(window, 'tmall:refresh', onRefresh);
  } else {
    window.addEventListener('tmall:date-range-change', onDateRangeChange);
    window.addEventListener('tmall:refresh', onRefresh);
  }
  dictionariesReady.then(() => { loadRuleCards(); load(); });
})();
