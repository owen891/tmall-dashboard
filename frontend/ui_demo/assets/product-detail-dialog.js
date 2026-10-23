(function () {
  const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  const chartPointRadius = () => window.DemoCharts?.chartPointRadius?.() || 3;
  const chartLineWidth = () => window.DemoCharts?.chartLineWidth?.() || 2;
  let drawer = null;
  let body = null;
  let current = null;
  let token = 0;
  let overviewTrendChart = null;
  let drawerTitle = null;
  let drawerMeta = null;
  let drawerId = null;
  let drawerImage = null;
  let drawerWorkbench = null;
  const detailTabs = [
    ['overview', '经营概览'],
    ['trend', '日趋势'],
    ['flow-source', '流量结构'],
    ['search', '搜索分析'],
    ['promotion', '付费推广'],
    ['lifecycle', '生命周期'],
    ['collaboration', '协作记录'],
  ];
  const promotionTableDefinitions = {
    channel: {
      label: '渠道汇总',
      columns: [
        { key: 'channel', label: '渠道', group: '基础信息' },
        { key: 'ad_spend', label: '推广花费', group: '投入与成交', format: 'money', shared: true },
        { key: 'attributed_payment_amount', label: '推广成交', group: '投入与成交', format: 'money', shared: true },
        { key: 'spend_share', label: '花费占比', group: '投入与成交', format: 'percent' },
        { key: 'roi', label: 'ROI', group: '投入与成交', format: 'ratio', shared: true },
        { key: 'impressions', label: '展现量', group: '流量与转化', format: 'number', shared: true },
        { key: 'clicks', label: '点击量', group: '流量与转化', format: 'number', shared: true },
        { key: 'ctr', label: '点击率', group: '流量与转化', format: 'percent', shared: true },
        { key: 'cpm', label: '千次展现成本', group: '流量与转化', format: 'moneyNullable', shared: true },
        { key: 'payment_buyers', label: '支付买家数', group: '流量与转化', format: 'number', shared: true },
        { key: 'cvr', label: '商品支付转化率', group: '流量与转化', format: 'percent', shared: true },
        { key: 'cpc', label: '平均点击花费', group: '流量与转化', format: 'moneyNullable', shared: true },
        { key: 'cart_adds', label: '加购次数', group: '行为成本', format: 'numberNullable', shared: true },
        { key: 'cart_rate', label: '加购率', group: '行为成本', format: 'percent', shared: true },
        { key: 'cart_cost', label: '加购成本', group: '行为成本', format: 'moneyNullable', shared: true },
        { key: 'new_buyers', label: '拉新买家数', group: '拉新经营', format: 'numberNullable', shared: true },
        { key: 'new_buyer_ratio', label: '拉新占比', group: '拉新经营', format: 'percent', shared: true },
        { key: 'new_customer_cost', label: '拉新成本', group: '拉新经营', format: 'moneyNullable', shared: true },
        { key: 'direct_payment_amount', label: '直接付费成交', group: '归因构成', format: 'money', shared: true },
        { key: 'indirect_payment_amount', label: '间接付费成交', group: '归因构成', format: 'money', shared: true },
        { key: 'paid_share', label: '付费成交占比', group: '归因构成', format: 'percent', shared: true },
      ],
      templates: [
        { id: 'detail-channel-overview', name: '渠道概览', fields: ['channel', 'ad_spend', 'attributed_payment_amount', 'spend_share', 'roi', 'paid_share'] },
        { id: 'detail-channel-traffic', name: '渠道流量转化', fields: ['channel', 'impressions', 'clicks', 'ctr', 'cpm', 'payment_buyers', 'cvr', 'cpc'] },
        { id: 'detail-channel-efficiency', name: '渠道效率', fields: ['channel', 'ad_spend', 'attributed_payment_amount', 'roi', 'cart_adds', 'cart_rate', 'cart_cost', 'new_buyers', 'new_buyer_ratio', 'new_customer_cost'] },
        { id: 'detail-channel-complete', name: '渠道完整明细', fields: ['channel', 'ad_spend', 'attributed_payment_amount', 'spend_share', 'roi', 'impressions', 'clicks', 'ctr', 'cpm', 'payment_buyers', 'cvr', 'cpc', 'cart_adds', 'cart_rate', 'cart_cost', 'new_buyers', 'new_buyer_ratio', 'new_customer_cost', 'direct_payment_amount', 'indirect_payment_amount', 'paid_share'] },
      ],
      defaultPageSize: 20,
    },
    campaign: {
      label: '计划汇总',
      columns: [
        { key: 'campaign_name', label: '计划', group: '基础信息' },
        { key: 'channel', label: '渠道', group: '基础信息' },
        { key: 'plan_type', label: '投放方式', group: '基础信息' },
        { key: 'ad_spend', label: '推广花费', group: '投入与成交', format: 'money', shared: true },
        { key: 'attributed_payment_amount', label: '推广成交', group: '投入与成交', format: 'money', shared: true },
        { key: 'roi', label: 'ROI', group: '投入与成交', format: 'ratio', shared: true },
        { key: 'impressions', label: '展现量', group: '流量与转化', format: 'number', shared: true },
        { key: 'clicks', label: '点击量', group: '流量与转化', format: 'number', shared: true },
        { key: 'ctr', label: '点击率', group: '流量与转化', format: 'percent', shared: true },
        { key: 'cpm', label: '千次展现成本', group: '流量与转化', format: 'moneyNullable', shared: true },
        { key: 'payment_buyers', label: '支付买家数', group: '流量与转化', format: 'number', shared: true },
        { key: 'cvr', label: '商品支付转化率', group: '流量与转化', format: 'percent', shared: true },
        { key: 'cpc', label: '平均点击花费', group: '流量与转化', format: 'moneyNullable', shared: true },
        { key: 'cart_adds', label: '加购次数', group: '行为成本', format: 'numberNullable', shared: true },
        { key: 'cart_rate', label: '加购率', group: '行为成本', format: 'percent', shared: true },
        { key: 'cart_cost', label: '加购成本', group: '行为成本', format: 'moneyNullable', shared: true },
        { key: 'new_buyers', label: '拉新买家数', group: '拉新经营', format: 'numberNullable', shared: true },
        { key: 'new_buyer_ratio', label: '拉新占比', group: '拉新经营', format: 'percent', shared: true },
        { key: 'new_customer_cost', label: '拉新成本', group: '拉新经营', format: 'moneyNullable', shared: true },
        { key: 'direct_payment_amount', label: '直接付费成交', group: '归因构成', format: 'money', shared: true },
        { key: 'indirect_payment_amount', label: '间接付费成交', group: '归因构成', format: 'money', shared: true },
        { key: 'paid_share', label: '付费成交占比', group: '归因构成', format: 'percent', shared: true },
      ],
      templates: [
        { id: 'detail-campaign-overview', name: '计划概览', fields: ['campaign_name', 'channel', 'plan_type', 'ad_spend', 'attributed_payment_amount', 'roi', 'paid_share'] },
        { id: 'detail-campaign-traffic', name: '计划流量转化', fields: ['campaign_name', 'channel', 'impressions', 'clicks', 'ctr', 'cpm', 'payment_buyers', 'cvr', 'cpc'] },
        { id: 'detail-campaign-efficiency', name: '计划效率', fields: ['campaign_name', 'channel', 'ad_spend', 'attributed_payment_amount', 'roi', 'cart_adds', 'cart_rate', 'cart_cost', 'new_buyers', 'new_buyer_ratio', 'new_customer_cost'] },
        { id: 'detail-campaign-complete', name: '计划完整明细', fields: ['campaign_name', 'channel', 'plan_type', 'ad_spend', 'attributed_payment_amount', 'roi', 'impressions', 'clicks', 'ctr', 'cpm', 'payment_buyers', 'cvr', 'cpc', 'cart_adds', 'cart_rate', 'cart_cost', 'new_buyers', 'new_buyer_ratio', 'new_customer_cost', 'direct_payment_amount', 'indirect_payment_amount', 'paid_share'] },
      ],
      defaultPageSize: 20,
    },
  };
  let promotionFieldDialog = null;
  const promotionFieldSelectors = {};
  let promotionTemplateManager = null;
  let promotionFieldDialogKind = null;
  let promotionFieldDialogDraft = [];
  const promotionFieldStorageKey = 'tmall_product_detail_promotion_fields_v1';
  const promotionFieldState = {
    channel: { page: 1, selected: null, customTemplates: {} },
    campaign: { page: 1, selected: null, customTemplates: {} },
  };
  const sharedPromotionColumns = () => window.DemoPromotionFields?.products?.columns || [];
  const promotionDefinition = (kind) => promotionTableDefinitions[kind] || promotionTableDefinitions.channel;
  const promotionColumns = (kind) => promotionDefinition(kind).columns.map((column) => {
    if (!column.shared) return column;
    const shared = sharedPromotionColumns().find((item) => item.key === column.key);
    return shared ? { ...column, label: shared.label, format: shared.format || column.format, group: shared.group || column.group } : column;
  });
  const readPromotionFieldState = () => {
    try {
      const saved = JSON.parse(localStorage.getItem(promotionFieldStorageKey) || '{}');
      ['channel', 'campaign'].forEach((kind) => {
        const allowed = new Set(promotionColumns(kind).map((column) => column.key));
        if (Array.isArray(saved?.[kind]?.selected)) promotionFieldState[kind].selected = [...new Set(saved[kind].selected.filter((key) => allowed.has(key)))];
        if (saved?.[kind]?.customTemplates && typeof saved[kind].customTemplates === 'object') promotionFieldState[kind].customTemplates = saved[kind].customTemplates;
      });
    } catch (_) {}
  };
  const savePromotionFieldState = () => {
    try { localStorage.setItem(promotionFieldStorageKey, JSON.stringify(promotionFieldState)); } catch (_) {}
  };
  readPromotionFieldState();

  const money = (value) => `¥${Number(value || 0).toLocaleString('zh-CN', { maximumFractionDigits: 2 })}`;
  const number = (value) => Number(value || 0).toLocaleString('zh-CN');
  const percent = (value) => value == null ? '--' : `${(Number(value) * 100).toFixed(2)}%`;
  const text = (value, fallback = '--') => value == null || value === '' ? fallback : String(value);
  const statusLabel = (value) => window.DemoLabels?.label?.('status', value, value) || text(value);
  const jsonOptions = (payload, method = 'POST') => ({ method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
  const showToast = (message, options) => window.DemoShell?.showToast?.(message, options);
  const reportMutationError = (error, fallback) => showToast(error?.message || fallback, { duration: 5000 });

  function node(tag, className, copy) {
    const item = document.createElement(tag);
    if (className) item.className = className;
    if (copy != null) item.textContent = copy;
    return item;
  }

  function ensureDialog() {
    if (drawer || !window.TmallUI?.detailDrawer) return;
    // 详情面统一 NUI 抽屉：不再自建 <dialog>。焦点圈闭/焦点归还/Escape/背板/
    // 滚动锁全部由 detailDrawer 提供，这里只负责内容、页签与页眉同步。
    drawer = window.TmallUI.detailDrawer({ title: '商品详情', description: '--', size: 'lg', onClose: resetSession });
    drawer.node.classList.add('product-detail-dialog');
    drawer.node.setAttribute('data-modal-kind', 'detail');
    drawerTitle = drawer.node.querySelector('.ui-drawer__copy h2');
    drawerMeta = drawer.node.querySelector('.ui-drawer__copy p');
    drawerMeta.setAttribute('data-shared-product-meta', '');
    drawerMeta.setAttribute('data-shared-product-subtitle', '');
    const intro = document.createElement('div');
    intro.className = 'product-detail-dialog__intro';
    intro.innerHTML = `<span class="lifecycle-detail__image product-detail-dialog__image" data-shared-product-image aria-hidden="true"><i data-lucide="image"></i></span><div class="lifecycle-detail__id" data-shared-product-id>--</div>`;
    drawerImage = intro.querySelector('[data-shared-product-image]');
    drawerId = intro.querySelector('[data-shared-product-id]');
    drawerWorkbench = node('a', 'ui-button ui-button--ghost product-detail-dialog__workbench', '打开完整工作台');
    drawerWorkbench.setAttribute('data-shared-product-workbench', '');
    drawerWorkbench.setAttribute('aria-label', '打开完整商品详情工作台');
    drawerWorkbench.setAttribute('aria-disabled', 'true');
    drawerWorkbench.tabIndex = -1;
    intro.append(drawerWorkbench);
    const tablist = document.createElement('div');
    tablist.className = 'lifecycle-detail-tabs product-detail-dialog__tabs';
    tablist.setAttribute('role', 'tablist');
    tablist.setAttribute('aria-label', '商品详情分组');
    tablist.innerHTML = detailTabs.map(([id, label], index) => `<button class="lifecycle-detail-tab product-detail-dialog__tab" id="product-detail-tab-${id}" role="tab" type="button" data-product-detail-tab="${id}" aria-selected="${index === 0}" aria-controls="product-detail-panel-${id}" tabindex="${index === 0 ? 0 : -1}">${label}</button>`).join('');
    body = node('div', 'product-detail-dialog__panels');
    body.setAttribute('data-shared-product-panels', '');
    tablist.addEventListener('click', (event) => {
      const tab = event.target.closest('[data-product-detail-tab]');
      if (tab) selectTab(tab.dataset.productDetailTab, false);
    });
    tablist.addEventListener('keydown', (event) => {
      const tabs = [...tablist.querySelectorAll('[data-product-detail-tab]')];
      const index = tabs.indexOf(event.target.closest('[data-product-detail-tab]'));
      if (index < 0 || !['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
      event.preventDefault();
      const nextIndex = event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1 : (index + (event.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length;
      selectTab(tabs[nextIndex].dataset.productDetailTab, true);
    });
    drawer.body.append(intro, tablist, body);
  }

  function metric(label, value, hint = '') {
    const item = node('div', 'detail-metric');
    item.append(node('span', '', label), node('strong', '', value));
    if (hint) item.append(node('small', 'panel__hint', hint));
    return item;
  }

  function metricGroups(grid) {
    const items = [...grid.children];
    const groups = node('div', 'product-detail-metric-groups');
    [
      ['\u6838\u5fc3\u7ecf\u8425', items.slice(0, 6)],
      ['\u63a8\u5e7f\u6548\u7387', items.slice(6)],
    ].forEach(([title, groupItems]) => {
      const group = node('section', 'product-detail-metric-group');
      group.appendChild(node('h4', 'product-detail-metric-group__title', title));
      const groupGrid = node('div', 'detail-metrics product-detail-metric-group__grid');
      groupItems.forEach((item) => groupGrid.appendChild(item));
      group.appendChild(groupGrid);
      groups.appendChild(group);
    });
    return groups;
  }

  function section(title, hint = '') {
    const wrapper = node('section', 'ui-panel product-detail-section');
    const header = node('div', 'panel__header');
    const copy = node('div');
    copy.append(node('h3', 'panel__title', title));
    if (hint) copy.append(node('p', 'panel__hint', hint));
    header.appendChild(copy);
    wrapper.appendChild(header);
    return wrapper;
  }

  function renderIdentity(detail) {
    const product = detail.product || {};
    const workbench = drawerWorkbench;
    const productId = product.product_id || current.productId;
    if (productId) {
      workbench.href = `/products/${encodeURIComponent(productId)}`;
      workbench.removeAttribute('aria-disabled');
      workbench.tabIndex = 0;
    } else {
      workbench.removeAttribute('href');
      workbench.setAttribute('aria-disabled', 'true');
      workbench.tabIndex = -1;
    }
    const wrapper = section('商品信息');
    const grid = node('dl', 'product-detail-meta');
    [
      ['商品 ID', product.product_id], ['类目', product.category], ['分层', product.tier],
      ['风格', product.style], ['场景', product.scene], ['状态', statusLabel(product.status)],
      ['上架日期', product.list_date], ['备注', product.remark],
    ].forEach(([label, value]) => {
      const item = node('div'); item.append(node('dt', '', label), node('dd', '', text(value))); grid.appendChild(item);
    });
    wrapper.appendChild(grid);
    return wrapper;
  }

  // promotion 走的是「推广计划」口径（/api/promotion/product-detail）：
  // 商品详情的 summary 只带 ad_spend / ad_roi（ad_roi 实为销售额÷花费，不是推广归因），
  // 推广成交 / ROI / CTR / CVR 只有推广明细接口才有，所以这四个指标统一取推广口径。
  // 没有推广数据时一律显示 '--'，不要用 money(undefined)=¥0 冒充"真的是 0"。
  function renderMetrics(detail, promotion) {
    const summary = detail.summary || {};
    const wrapper = section('经营与推广指标', '同一弹窗内同时核对经营表现和当前推广上下文。');
    const grid = node('div', 'detail-metrics product-detail-metrics');
    const promo = promotion || null;
    // 没有推广数据时接口回的是全 0（不是 null）：0 不能冒充"真的是 0"，一律显示 '--'
    const hasPromo = Boolean(promo) && (Number(promo.ad_spend || 0) > 0
      || Number(promo.attributed_payment_amount || 0) > 0 || Number(promo.roi || 0) > 0);
    const spend = promo?.ad_spend ?? summary.ad_spend;
    grid.append(
      metric('销售额', money(summary.payment_amount)), metric('净销售额', money(summary.net_sales)),
      metric('退款金额', money(summary.refund_amount)), metric('商品访客数', number(summary.product_visitors)),
      metric('商品支付转化率', percent(summary.payment_conversion_rate)), metric('客单价', money(summary.average_order_value)),
      metric('推广花费', hasPromo ? money(spend) : '--', hasPromo ? '推广计划口径' : ''),
      metric('推广成交', hasPromo ? money(promo.attributed_payment_amount) : '--', hasPromo ? '计划归因' : ''),
      metric('推广 ROI', hasPromo && promo.roi != null ? Number(promo.roi).toFixed(2) : '--', hasPromo ? '推广成交 ÷ 推广花费' : ''),
      metric('CTR / CVR', hasPromo && (promo.ctr != null || promo.cvr != null) ? `${percent(promo.ctr)} / ${percent(promo.cvr)}` : '--')
    );
    wrapper.append(metricGroups(grid));
    if (hasPromo) {
      wrapper.append(node('p', 'panel__hint',
        `推广指标为「推广计划」口径（多商品计划会整体计入），与「付费推广」标签页同源；`
        + `商品口径的商品花费为 ${money(summary.ad_spend)}，两者口径不同、不要直接相减。`));
    }
    return wrapper;
  }

  function renderOverviewTrend(rows) {
    const wrapper = node('article', 'chart-panel ui-panel lifecycle-chart-panel product-detail-overview-trend');
    const header = node('div', 'panel__header product-detail-overview-trend__header');
    const copy = node('div');
    copy.append(node('h4', 'panel__title', '经营走势'), node('p', 'panel__hint', '与上方经营与推广指标同源，按月聚合查看销售、净销售额与推广花费。'));
    header.appendChild(copy);
    wrapper.appendChild(header);
    if (!rows?.length) {
      wrapper.appendChild(node('p', 'panel__hint', '暂无可绘制的日度经营数据'));
      return wrapper;
    }
    const chart = node('div', 'chart-canvas product-detail-overview-chart');
    chart.dataset.productOverviewTrend = 'true';
    chart.setAttribute('role', 'img');
    chart.setAttribute('aria-label', '商品月度经营走势，包含销售额、净销售额与推广花费');
    const chartBox = node('div', 'chart-box lifecycle-chart-box product-detail-overview-chart-box');
    chartBox.appendChild(chart);
    wrapper.appendChild(chartBox);
    return wrapper;
  }

  function destroyOverviewTrendChart() {
    overviewTrendChart?.destroy?.();
    overviewTrendChart = null;
  }

  function groupOverviewTrendByMonth(rows) {
    const grouped = new Map();
    (rows || []).forEach((row) => {
      const month = String(row.date || '').slice(0, 7);
      if (!/^\d{4}-\d{2}$/.test(month)) return;
      const point = grouped.get(month) || { month, payment_amount: 0, net_sales: 0, ad_spend: 0 };
      point.payment_amount += Number(row.payment_amount || 0);
      point.net_sales += Number(row.net_sales || 0);
      point.ad_spend += Number(row.ad_spend || 0);
      grouped.set(month, point);
    });
    return [...grouped.values()].sort((first, second) => first.month.localeCompare(second.month));
  }

  function mountOverviewTrendChart(rows) {
    const chart = drawer?.node.querySelector('[data-product-overview-trend]');
    const points = groupOverviewTrendByMonth(rows);
    if (!chart || !points.length || !window.EChartCompat) return;
    const moneyAxis = (value) => money(Number(value || 0));
    overviewTrendChart = new window.EChartCompat(chart, {
      data: {
        labels: points.map((point) => point.month),
        datasets: [
          { type: 'line', label: '销售额', data: points.map((point) => point.payment_amount), borderColor: css('--brand'), tension: .32, pointRadius: chartPointRadius(), borderWidth: chartLineWidth(), yAxisID: 'y' },
          { type: 'line', label: '净销售额', data: points.map((point) => point.net_sales), borderColor: css('--info'), tension: .32, pointRadius: chartPointRadius(), borderWidth: chartLineWidth(), yAxisID: 'y' },
          { type: 'line', label: '推广花费', data: points.map((point) => point.ad_spend), borderColor: css('--success'), tension: .32, pointRadius: chartPointRadius(), borderWidth: chartLineWidth(), yAxisID: 'y1' },
        ],
      },
      options: {
        plugins: { legend: { position: 'top' } },
        scales: {
          x: { grid: { display: false } },
          y: { ticks: { callback: moneyAxis }, grid: { color: css('--border') } },
          y1: { position: 'right', ticks: { callback: moneyAxis }, grid: { display: false } },
        },
      },
    });
  }

  function renderTrend(rows) {
    const wrapper = section('日趋势', '展示已入库的商品日度经营数据。');
    if (!rows?.length) { wrapper.append(node('p', 'panel__hint', '暂无日趋势数据')); return wrapper; }
    const data = rows.slice(-31).reverse();
    wrapper.appendChild(window.TmallUI.table({
      columns: [
        { key: 'date', label: '日期' },
        { key: 'payment', label: '支付金额', numeric: true },
        { key: 'netSales', label: '净销售额', numeric: true },
        { key: 'refund', label: '成功退款金额', numeric: true },
        { key: 'visitors', label: '商品访客数', numeric: true },
        { key: 'adSpend', label: '推广花费', numeric: true },
      ],
      rows: data.map((row) => ({
        date: row.date,
        payment: money(row.payment_amount),
        netSales: money(row.net_sales),
        refund: money(row.refund_amount),
        visitors: number(row.product_visitors),
        adSpend: money(row.ad_spend),
      })),
    }));
    return wrapper;
  }

  function renderSearch(detail) {
    const summary = detail?.summary || {};
    const rows = Array.isArray(detail?.daily_trend) ? detail.daily_trend : [];
    const hasSearchFact = summary.search_visitors != null || rows.some((row) => row.search_visitors != null);
    const wrapper = section('搜索分析', '使用商品经营事实中的搜索字段；没有商品级关键词归因时不补造关键词明细。');
    const metrics = node('div', 'detail-metrics product-detail-search-metrics');
    const ratio = summary.search_ratio;
    metrics.append(
      metric('搜索访客', hasSearchFact ? number(summary.search_visitors) : '--', '当前日期范围'),
      metric('搜索占比', hasSearchFact ? percent(ratio) : '--', '搜索访客 ÷ 商品访客'),
      metric('搜索转化率', summary.search_conversion == null ? '--' : percent(summary.search_conversion), '搜索访客到支付'),
      metric('搜索点击率', summary.search_click_rate == null ? '--' : percent(summary.search_click_rate), '来源字段可用时展示'),
    );
    wrapper.appendChild(metrics);

    const status = node('p', 'panel__hint', hasSearchFact
      ? '搜索汇总字段可用；当前数据源未提供可验证的商品级关键词归因'
      : '当前日期范围没有可用的商品级搜索字段，以下搜索指标显示为 --');
    wrapper.appendChild(status);
    if (rows.length) {
      const data = rows.slice(-31).reverse().map((row) => {
        const searchVisitors = row.search_visitors;
        const searchRatio = row.search_ratio ?? (searchVisitors != null && row.product_visitors ? searchVisitors / row.product_visitors : null);
        return {
          date: row.date,
          visitors: searchVisitors == null ? '--' : number(searchVisitors),
          share: percent(searchRatio),
          conversion: percent(row.search_conversion),
          clickRate: percent(row.search_click_rate),
        };
      });
      wrapper.appendChild(window.TmallUI.table({
        columns: [
          { key: 'date', label: '日期' },
          { key: 'visitors', label: '搜索访客', numeric: true },
          { key: 'share', label: '搜索占比', numeric: true },
          { key: 'conversion', label: '搜索转化率', numeric: true },
          { key: 'clickRate', label: '搜索点击率', numeric: true },
        ],
        rows: data,
      }));
    }

    const keywords = section('关键词明细', '只有存在商品级关键词与商品 ID 关联事实时才开放。');
    keywords.appendChild(node('div', 'product-theme-unavailable', hasSearchFact
      ? '当前数据源提供商品级搜索汇总，但没有可验证的商品级关键词归因，暂不展示关键词排名或标题建议。'
      : '当前数据源没有可验证的商品级搜索字段，暂不展示搜索指标、关键词排名或标题建议。'));
    wrapper.appendChild(keywords);
    return wrapper;
  }

  // ===== 流量结构：可配置字段 =====
  // 接口返回的渠道指标有 15 个，但表格原先写死 7 列。这里把列做成可配置，
  // 与「付费推广」共用同一套字段设置交互（分组勾选 + 拖动排序 + 模板 + 本地记忆）。
  const flowFieldDefinitions = [
    { key: 'channel_name', label: '渠道名称', group: '基础信息', locked: true },
    { key: 'channel_type', label: '渠道类型', group: '基础信息' },
    { key: 'uv', label: '访客数', group: '流量', format: 'number' },
    { key: 'uv_share', label: '访客占比', group: '流量', format: 'percent' },
    { key: 'pv', label: '浏览量', group: '流量', format: 'number' },
    { key: 'new_uv', label: '新访客数', group: '流量', format: 'number' },
    { key: 'pay_amount', label: '支付金额', group: '成交', format: 'money' },
    { key: 'pay_buyer_count', label: '支付买家数', group: '成交', format: 'number' },
    { key: 'pay_rate', label: '支付转化率', group: '成交', format: 'percent' },
    { key: 'deal_buyer_count', label: '成交买家数', group: '成交', format: 'number' },
    { key: 'pay_item_count', label: '支付件数', group: '成交', format: 'number' },
    { key: 'uv_value', label: 'UV价值', group: '成交效率', format: 'money' },
    { key: 'customer_price', label: '客单价', group: '成交效率', format: 'money' },
    { key: 'cart_buyer_count', label: '加购人数', group: '互动', format: 'number' },
    { key: 'collect_item_count', label: '收藏商品数', group: '互动', format: 'number' },
  ];
  const flowFieldTemplates = [
    { id: 'flow-core', name: '核心概览', fields: ['channel_name', 'uv', 'uv_share', 'pay_amount', 'pay_buyer_count', 'pay_rate', 'uv_value'] },
    { id: 'flow-traffic', name: '流量明细', fields: ['channel_name', 'channel_type', 'uv', 'uv_share', 'pv', 'new_uv'] },
    { id: 'flow-deal', name: '成交明细', fields: ['channel_name', 'uv', 'pay_amount', 'pay_buyer_count', 'pay_rate', 'deal_buyer_count', 'pay_item_count', 'customer_price'] },
    { id: 'flow-engage', name: '互动行为', fields: ['channel_name', 'uv', 'cart_buyer_count', 'collect_item_count'] },
    { id: 'flow-all', name: '全部字段', fields: flowFieldDefinitions.map((column) => column.key) },
  ];
  const flowFieldStorageKey = 'tmall_product_detail_flow_fields_v1';
  const flowFieldState = { selected: null, customTemplates: {} };
  const flowFieldKeys = () => flowFieldDefinitions.map((column) => column.key);
  const flowTemplateList = () => [
    ...flowFieldTemplates,
    ...Object.entries(flowFieldState.customTemplates || {}).map(([id, template]) => ({ id, ...template })),
  ];
  const flowSelectedFields = () => {
    const allowed = new Set(flowFieldKeys());
    const selected = flowFieldState.selected?.filter((key) => allowed.has(key));
    return selected?.length ? selected : [...flowFieldTemplates[0].fields];
  };
  const flowGroups = () => {
    const groups = new Map();
    flowFieldDefinitions.forEach((column) => {
      const group = column.group || '字段';
      if (!groups.has(group)) groups.set(group, []);
      groups.get(group).push(column);
    });
    return [...groups.entries()].map(([label, fields]) => ({ label, fields }));
  };
  const readFlowFieldState = () => {
    try {
      const saved = JSON.parse(localStorage.getItem(flowFieldStorageKey) || '{}');
      const allowed = new Set(flowFieldKeys());
      if (Array.isArray(saved?.selected)) flowFieldState.selected = [...new Set(saved.selected.map(String).filter((key) => allowed.has(key)))];
      if (saved?.customTemplates && typeof saved.customTemplates === 'object') flowFieldState.customTemplates = saved.customTemplates;
    } catch (_) {}
  };
  const saveFlowFieldState = () => {
    try { localStorage.setItem(flowFieldStorageKey, JSON.stringify(flowFieldState)); } catch (_) {}
  };
  readFlowFieldState();

  let flowFieldDialog = null;
  let flowFieldSelector = null;
  let flowFieldTemplateManager = null;
  let flowFieldDraft = [];

  function ensureFlowFieldDialog() {
    if (flowFieldDialog) return flowFieldDialog;
    flowFieldDialog = document.createElement('dialog');
    flowFieldDialog.className = 'modal-form ui-field-selector-dialog product-detail-promotion-field-dialog';
    flowFieldDialog.setAttribute('data-modal-kind', 'config');
    flowFieldDialog.setAttribute('aria-labelledby', 'productDetailFlowFieldTitle');
    flowFieldDialog.innerHTML = `
      <div class="modal-form__header"><div><h3 id="productDetailFlowFieldTitle">流量结构字段设置</h3><p data-flow-field-scope>选择流量结构表格需要展示的字段，渠道名称固定展示</p></div><button class="ui-button ui-button--ghost" type="button" data-flow-field-close aria-label="关闭字段设置"><i data-lucide="x"></i></button></div>
      <div class="modal-form__body"><div class="field-template-bar"><div>当前显示 <strong data-flow-field-count>--</strong> 个字段</div><div class="field-template-bar__controls"><select class="select" data-flow-template-select aria-label="选择字段模板"></select><button class="ui-button" type="button" data-flow-template-apply>使用模板</button><button class="ui-button" type="button" data-flow-field-reset>恢复默认</button></div></div><div data-flow-field-selector></div><div class="saved-template-list field-template-manager" data-flow-template-manager aria-label="流量结构字段模板管理"></div><div class="filter-group"><input class="input" data-flow-template-name placeholder="自定义模板名称" aria-label="自定义模板名称"><button class="ui-button" type="button" data-flow-template-save>保存为模板</button></div><p class="modal-form__status" data-flow-field-status aria-live="polite"></p></div>
      <div class="modal-form__footer"><button class="ui-button" type="button" data-flow-field-cancel>取消</button><button class="ui-button ui-button--primary" type="button" data-flow-field-apply>应用字段</button></div>`;
    document.body.appendChild(flowFieldDialog);
    flowFieldDialog.querySelector('[data-flow-field-close]').addEventListener('click', () => flowFieldDialog.close());
    flowFieldDialog.querySelector('[data-flow-field-cancel]').addEventListener('click', () => flowFieldDialog.close());
    flowFieldDialog.addEventListener('cancel', (event) => { event.preventDefault(); flowFieldDialog.close(); });
    flowFieldDialog.addEventListener('click', (event) => { if (event.target === flowFieldDialog) flowFieldDialog.close(); });
    return flowFieldDialog;
  }

  function updateFlowFieldDialog(draft) {
    const dialogNode = ensureFlowFieldDialog();
    const selected = draft || flowSelectedFields();
    const count = dialogNode.querySelector('[data-flow-field-count]');
    if (count) count.textContent = String(selected.length);
    const status = dialogNode.querySelector('[data-flow-field-status]');
    if (status) status.textContent = selected.length ? '' : '至少保留一个字段';
    const apply = dialogNode.querySelector('[data-flow-field-apply]');
    if (apply) apply.disabled = !selected.length;
  }

  function openFlowFieldDialog() {
    const dialogNode = ensureFlowFieldDialog();
    flowFieldDraft = [...flowSelectedFields()];
    const config = {
      root: dialogNode.querySelector('[data-flow-field-selector]'),
      groups: flowGroups(),
      selected: flowFieldDraft,
      availableTitle: '可选字段',
      availableHint: '勾选要展示的字段',
      previewTitle: '字段预览',
      previewHint: '按表格列顺序展示，可拖动调整顺序',
      optionDataAttribute: 'data-flow-field-key',
      previewDataAttribute: 'data-flow-field-preview',
      onChange: (next) => { flowFieldDraft = next; updateFlowFieldDialog(next); },
    };
    if (!flowFieldSelector) flowFieldSelector = window.TmallUI?.fieldSelector?.(config);
    else flowFieldSelector.setConfig(config);
    flowFieldSelector?.setSelected(flowFieldDraft);

    const select = dialogNode.querySelector('[data-flow-template-select]');
    select.replaceChildren();
    flowTemplateList().forEach((template) => {
      const option = document.createElement('option'); option.value = template.id; option.textContent = template.name; select.appendChild(option);
    });
    select.value = flowFieldTemplates[0].id;

    const managerRoot = dialogNode.querySelector('[data-flow-template-manager]');
    const templates = Object.fromEntries(flowTemplateList().map((template) => [template.id, { label: template.name, columns: [...template.fields] }]));
    if (!flowFieldTemplateManager) {
      flowFieldTemplateManager = window.DemoFieldTemplateManager?.create({
        root: managerRoot,
        builtinKeys: flowFieldTemplates.map((template) => template.id),
        templates,
        onChange: (event) => {
          if (event.type !== 'use') return;
          const picked = flowTemplateList().find((template) => template.id === event.key);
          if (!picked) return;
          flowFieldDraft = [...picked.fields];
          flowFieldSelector?.setSelected(flowFieldDraft);
          updateFlowFieldDialog(flowFieldDraft);
        },
        onDelete: async (key) => {
          delete flowFieldState.customTemplates[key];
          saveFlowFieldState();
          openFlowFieldDialog();
        },
      });
    } else {
      flowFieldTemplateManager.setBuiltinKeys(flowFieldTemplates.map((template) => template.id));
      flowFieldTemplateManager.setTemplates(templates);
    }

    dialogNode.querySelector('[data-flow-template-apply]').onclick = () => {
      const template = flowTemplateList().find((item) => item.id === select.value);
      if (!template) return;
      flowFieldDraft = [...template.fields];
      flowFieldSelector?.setSelected(flowFieldDraft);
      updateFlowFieldDialog(flowFieldDraft);
    };
    dialogNode.querySelector('[data-flow-field-reset]').onclick = () => {
      flowFieldDraft = [...flowFieldTemplates[0].fields];
      flowFieldSelector?.setSelected(flowFieldDraft);
      updateFlowFieldDialog(flowFieldDraft);
    };
    dialogNode.querySelector('[data-flow-template-save]').onclick = () => {
      const nameInput = dialogNode.querySelector('[data-flow-template-name]');
      const name = nameInput.value.trim();
      if (!name || !flowFieldDraft.length) return;
      const id = `flow-${Date.now()}`;
      flowFieldState.customTemplates[id] = { name, fields: [...flowFieldDraft] };
      nameInput.value = '';
      saveFlowFieldState();
      openFlowFieldDialog();
    };
    dialogNode.querySelector('[data-flow-field-apply]').onclick = () => {
      if (!flowFieldDraft.length) return;
      flowFieldState.selected = [...flowFieldDraft];
      saveFlowFieldState();
      dialogNode.close();
      renderCurrentPanel();
    };
    updateFlowFieldDialog(flowFieldDraft);
    if (!dialogNode.open) dialogNode.showModal();
    window.lucide?.createIcons();
  }

  // 流量结构的「内容体」：指标卡 + 口径说明 + 可折叠展开的树形表格。
  // 单独拆出来，是为了让「第一次访问来源」和「全程来源」两个口径共用一个板块
  // （见 renderFlowSourceTab），而不是并排铺出两个都叫「流量结构」的板块。
  function renderFlowSourceBody(flowData) {
    const wrapper = node('div', 'product-detail-flow-body');
    const allChannels = (flowData && flowData.channels) || [];
    if (!allChannels.length) {
      wrapper.append(node('p', 'panel__hint', '暂无流量来源数据'));
      return wrapper;
    }
    const productTotals = flowData.product_totals || null;
    const channelTotals = flowData.channel_totals || {
      uv: flowData.total_uv || 0,
      pay_amount: flowData.total_pay_amount || 0,
      pay_buyer_count: allChannels.reduce((sum, ch) => sum + (ch.pay_buyer_count || 0), 0),
    };
    const days = flowData.data_days || 1;
    const periodLabel = days > 1 ? `${flowData.start_date} ~ ${flowData.end_date}` : flowData.start_date;

    // 父子关系一律以 parent_channel 为准：父级不存在的视为根层。
    // 「第一次访问来源」口径没有父子信息，会自然退化成单层列表。
    const knownNames = new Set(allChannels.map(ch => ch.channel_name));
    const childrenOf = new Map();
    allChannels.forEach(ch => {
      const parent = ch.parent_channel || '';
      if (!parent || !knownNames.has(parent)) return;
      if (!childrenOf.has(parent)) childrenOf.set(parent, []);
      childrenOf.get(parent).push(ch);
    });
    const sortByUv = (a, b) => (b.uv || 0) - (a.uv || 0);
    const roots = allChannels
      .filter(ch => !ch.parent_channel || !knownNames.has(ch.parent_channel))
      .sort(sortByUv);

    // 商品维度是去重后的真实值；渠道合计含跨渠道重叠，两者不能混用，分开列示
    const metricsGrid = node('div', 'detail-metrics product-detail-metrics');
    metricsGrid.append(
      metric('商品访客数', productTotals ? number(productTotals.visitors) : '--', '商品口径 · 已去重'),
      metric('商品支付金额', productTotals ? money(productTotals.payment_amount) : '--', '商品口径'),
      metric('支付买家数', productTotals ? number(productTotals.buyers) : '--', '商品口径'),
      metric('渠道数', number(roots.length), '根层渠道'),
    );
    wrapper.append(metricsGrid);
    wrapper.append(node('p', 'panel__hint', [
      `渠道合计：访客 ${number(channelTotals.uv)}、支付 ${money(channelTotals.pay_amount)}、买家 ${number(channelTotals.pay_buyer_count)}`,
      '（同一访客可能来自多个渠道，渠道相加会高于商品去重值，只用于看结构）',
      `统计区间 ${periodLabel || '--'}（${days} 天）`,
    ].join('；')));
    if (flowData.hierarchy_source === 'shop_tree') {
      wrapper.append(node('p', 'panel__hint',
        '父级分组（平台流量 / 广告流量…）由店铺渠道树上溯推导——单品「第一次访问来源」接口只返回平铺一层，'
        + '要看接口原生的多级渠道请切到上面的「全程来源」。'));
    }

    // 折叠展开的树形表格：父子关系一律以 parent_channel 为准，父级不在返回集里的当根层。
    // 默认只展开根层（露出第一级渠道），更深的层级点 +/− 手动展开——
    // 层级多的时候全展开会把一屏铺满，折叠起来更清爽。
    // 展示哪些列由「字段设置」决定；渠道名称是结构列，恒排在最前。
    const orderedKeys = flowSelectedFields();
    const nameIndex = orderedKeys.indexOf('channel_name');
    if (nameIndex > 0) orderedKeys.unshift(...orderedKeys.splice(nameIndex, 1));
    const columns = orderedKeys
      .map((key) => flowFieldDefinitions.find((column) => column.key === key))
      .filter(Boolean);
    const expandedNames = new Set(roots.map(ch => ch.channel_name));
    const rootTotalUv = roots.reduce((sum, ch) => sum + (ch.uv || 0), 0);
    const tableContainer = node('div');

    const flowCellText = (column, ch) => {
      switch (column.key) {
        case 'channel_name': return ch.channel_name;
        case 'channel_type': return text(ch.channel_type);
        case 'uv_share': return rootTotalUv > 0 ? `${((ch.uv || 0) / rootTotalUv * 100).toFixed(1)}%` : '--';
        case 'uv_value': return ch.uv > 0 && ch.pay_amount != null ? money(ch.pay_amount / ch.uv) : '--';
        case 'customer_price': return ch.pay_buyer_count > 0 && ch.pay_amount != null ? money(ch.pay_amount / ch.pay_buyer_count) : '--';
        default:
          if (column.format === 'money') return ch[column.key] == null ? '--' : money(ch[column.key]);
          if (column.format === 'percent') return percent(ch[column.key]);
          if (column.format === 'number') return number(ch[column.key]);
          return text(ch[column.key]);
      }
    };

    function renderTable() {
      tableContainer.replaceChildren();
      const tableWrap = node('div', 'ui-table-wrap');
      const table = node('table', 'ui-data-table');
      const head = document.createElement('tr');
      columns.forEach((column) => head.appendChild(node('th', column.format ? 'num' : '', column.label)));
      const thead = document.createElement('thead');
      thead.appendChild(head);
      table.appendChild(thead);
      const tbody = document.createElement('tbody');
      let visible = 0;

      const appendRow = (ch, depth) => {
        visible += 1;
        const kids = childrenOf.get(ch.channel_name) || [];
        const isExpanded = kids.length > 0 && expandedNames.has(ch.channel_name);
        const tr = document.createElement('tr');

        const toggleNode = () => {
          if (expandedNames.has(ch.channel_name)) expandedNames.delete(ch.channel_name);
          else expandedNames.add(ch.channel_name);
          renderTable();
        };

        columns.forEach((column) => {
          if (column.key !== 'channel_name') {
            tr.appendChild(node('td', 'num', flowCellText(column, ch)));
            return;
          }
          const cell = node('div', 'channel-cell');
          cell.style.paddingLeft = `${depth * 20}px`;
          const toggle = node('span', kids.length ? 'toggle-btn' : 'toggle-btn toggle-btn--empty',
            kids.length ? (isExpanded ? '−' : '+') : '·');
          toggle.setAttribute('aria-label', `${isExpanded ? '收起' : '展开'}${ch.channel_name}`);
          if (kids.length) toggle.addEventListener('click', (event) => { event.stopPropagation(); toggleNode(); });

          const label = node('span', kids.length ? 'channel-name channel-name--clickable' : 'channel-name', ch.channel_name);
          label.title = kids.length ? `${ch.channel_name}（点击${isExpanded ? '收起' : '展开'} ${kids.length} 个下级渠道）` : ch.channel_name;
          if (kids.length) label.addEventListener('click', toggleNode);

          cell.append(toggle, label);
          const nameTd = node('td');
          nameTd.appendChild(cell);
          tr.appendChild(nameTd);
        });

        tbody.appendChild(tr);
        if (isExpanded) kids.forEach(kid => appendRow(kid, depth + 1));
      };

      roots.forEach(ch => appendRow(ch, 0));
      if (!visible) {
        tbody.innerHTML = `<tr><td colspan="${columns.length}" style="text-align:center;color:var(--text-secondary);padding:16px;">暂无渠道数据</td></tr>`;
      }
      table.appendChild(tbody);
      tableWrap.appendChild(table);
      tableContainer.appendChild(tableWrap);
    }

    wrapper.append(tableContainer);
    renderTable();
    return wrapper;
  }

  const flowBelongLabel = (data) => (data?.belong === 'all' ? '全程来源' : '第一次访问来源');
  const flowRangeLabel = (data) => {
    const days = data?.data_days || 1;
    const start = data?.start_date || '--';
    return days > 1 ? `${start}~${data.end_date}（${days} 天）` : `${start}（1 天）`;
  };

  function attachFlowFieldButton(sectionWrapper) {
    const tools = node('div', 'panel__actions');
    const button = node('button', 'ui-button ui-button--ghost', '字段设置');
    button.type = 'button';
    button.setAttribute('aria-label', '流量结构字段设置');
    button.addEventListener('click', () => openFlowFieldDialog());
    tools.appendChild(button);
    sectionWrapper.querySelector('.panel__header')?.appendChild(tools);
    return sectionWrapper;
  }

  // 单口径：整块就是一个「流量结构」板块（只有一个口径有数据时走这里）
  function renderFlowSource(flowData, options = {}) {
    const wrapper = section(options.title || '流量结构',
      `生意参谋 · ${flowBelongLabel(flowData)}口径 · 渠道层级可折叠展开 · 列可在「字段设置」里配置`);
    if (options.note) wrapper.append(node('p', 'panel__hint', options.note));
    wrapper.append(renderFlowSourceBody(flowData));
    return attachFlowFieldButton(wrapper);
  }

  // 双口径：同属一个「流量结构」板块，用分段控件切换。
  // 早先是并排铺两块（「流量结构」+「流量结构 · 全程来源」），标题重名、数值区间又不同，很容易被当成重复数据。
  function renderFlowSourceTab(primary, secondary) {
    if (!secondary) return renderFlowSource(primary);
    const datasets = [primary, secondary];
    const wrapper = section('流量结构', '生意参谋 · 渠道层级可折叠展开 · 列可在「字段设置」里配置');
    const switcher = node('div', 'segmented');
    switcher.setAttribute('role', 'group');
    switcher.setAttribute('aria-label', '流量来源口径');
    const buttons = datasets.map((data, index) => {
      const button = node('button', '', `${flowBelongLabel(data)} · ${flowRangeLabel(data)}`);
      button.type = 'button';
      button.setAttribute('aria-pressed', index === 0 ? 'true' : 'false');
      switcher.appendChild(button);
      return button;
    });
    const bar = node('div', '');
    bar.style.cssText = 'display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:12px;';
    bar.append(switcher, node('span', 'panel__hint',
      '两种口径统计区间不同（按钮上已标注）。「全程来源」自带原始多级渠道，但目前只采到部分日期。'));
    const body = node('div', '');
    const show = (index) => {
      buttons.forEach((button, i) => button.setAttribute('aria-pressed', i === index ? 'true' : 'false'));
      body.replaceChildren(renderFlowSourceBody(datasets[index]));
      window.lucide?.createIcons();
    };
    buttons.forEach((button, index) => button.addEventListener('click', () => show(index)));
    wrapper.append(bar, body);
    show(0);
    return attachFlowFieldButton(wrapper);
  }

  function renderLifecycle(lifecycle) {
    const wrapper = section('生命周期');
    if (!lifecycle) { wrapper.append(node('p', 'panel__hint', '暂无生命周期评估')); return wrapper; }
    const list = node('div', 'status-list');
    [['阶段', lifecycle.stage || lifecycle.lifecycle_stage], ['季节属性', lifecycle.seasonality], ['判定依据', lifecycle.reason || lifecycle.evidence], ['建议', lifecycle.recommendation]].forEach(([label, value]) => {
      const row = node('div', 'status-list__item'); row.append(node('span', 'status-list__label', label), node('span', 'status-list__value', text(value))); list.appendChild(row);
    });
    wrapper.appendChild(list); return wrapper;
  }

  function promotionFormat(value, format) {
    if (format === 'money') return value == null || value === '' ? '--' : money(value);
    if (format === 'moneyNullable') return value == null || value === '' ? '--' : money(value);
    if (format === 'number') return number(value);
    if (format === 'numberNullable') return value == null || value === '' ? '--' : number(value);
    if (format === 'percent') return value == null || value === '' ? '--' : percent(value);
    if (format === 'ratio') return value == null || value === '' ? '--' : Number(value).toFixed(2);
    return text(value);
  }

  function promotionTemplateList(kind) {
    const definition = promotionDefinition(kind);
    return [...definition.templates, ...Object.entries(promotionFieldState[kind].customTemplates || {}).map(([id, template]) => ({ id, ...template }))];
  }

  function promotionSelectedFields(kind) {
    const definition = promotionDefinition(kind);
    const allowed = new Set(promotionColumns(kind).map((column) => column.key));
    const selected = promotionFieldState[kind].selected?.filter((key) => allowed.has(key));
    return selected?.length ? selected : [...definition.templates[0].fields];
  }

  function promotionGroups(kind) {
    const groups = new Map();
    promotionColumns(kind).forEach((column) => {
      const group = column.group || '字段';
      if (!groups.has(group)) groups.set(group, []);
      groups.get(group).push(column);
    });
    return [...groups.entries()].map(([label, fields]) => ({ label, fields }));
  }

  function ensurePromotionFieldDialog() {
    if (promotionFieldDialog) return promotionFieldDialog;
    promotionFieldDialog = document.createElement('dialog');
    promotionFieldDialog.className = 'modal-form ui-field-selector-dialog product-detail-promotion-field-dialog';
    promotionFieldDialog.setAttribute('data-modal-kind', 'config');
    promotionFieldDialog.setAttribute('aria-labelledby', 'productDetailPromotionFieldTitle');
    promotionFieldDialog.innerHTML = `
      <div class="modal-form__header"><div><h3 id="productDetailPromotionFieldTitle">推广字段设置</h3><p data-product-detail-field-scope>选择当前表格需要展示的字段</p></div><button class="ui-button ui-button--ghost" type="button" data-product-detail-fields-close aria-label="关闭字段设置"><i data-lucide="x"></i></button></div>
      <div class="modal-form__body"><div class="field-template-bar"><div>当前显示 <strong data-product-detail-field-count>--</strong> 个字段</div><div class="field-template-bar__controls"><select class="select" data-product-detail-template-select aria-label="选择字段模板"></select><button class="ui-button" type="button" data-product-detail-template-apply>使用模板</button><button class="ui-button" type="button" data-product-detail-fields-reset>恢复默认</button></div></div><div data-product-detail-field-selector></div><div class="saved-template-list field-template-manager" data-product-detail-template-manager aria-label="推广字段模板管理"></div><div class="filter-group"><input class="input" data-product-detail-template-name placeholder="自定义模板名称" aria-label="自定义模板名称"><button class="ui-button" type="button" data-product-detail-template-save>保存为模板</button></div><p class="modal-form__status" data-product-detail-field-status aria-live="polite"></p></div>
      <div class="modal-form__footer"><button class="ui-button" type="button" data-product-detail-fields-cancel>取消</button><button class="ui-button ui-button--primary" type="button" data-product-detail-fields-apply>应用字段</button></div>`;
    document.body.appendChild(promotionFieldDialog);
    promotionFieldDialog.querySelector('[data-product-detail-fields-close]').addEventListener('click', () => promotionFieldDialog.close());
    promotionFieldDialog.querySelector('[data-product-detail-fields-cancel]').addEventListener('click', () => promotionFieldDialog.close());
    promotionFieldDialog.addEventListener('cancel', (event) => { event.preventDefault(); promotionFieldDialog.close(); });
    promotionFieldDialog.addEventListener('click', (event) => { if (event.target === promotionFieldDialog) promotionFieldDialog.close(); });
    return promotionFieldDialog;
  }

  function updatePromotionFieldDialog(kind, draft) {
    const dialogNode = ensurePromotionFieldDialog();
    const definition = promotionDefinition(kind);
    const selected = draft || promotionSelectedFields(kind);
    const count = dialogNode.querySelector('[data-product-detail-field-count]');
    if (count) count.textContent = String(selected.length);
    const scope = dialogNode.querySelector('[data-product-detail-field-scope]');
    if (scope) scope.textContent = `${definition.label}字段，可拖动调整顺序`;
    const status = dialogNode.querySelector('[data-product-detail-field-status]');
    if (status) status.textContent = selected.length ? '' : '至少保留一个字段';
    const apply = dialogNode.querySelector('[data-product-detail-fields-apply]');
    if (apply) apply.disabled = !selected.length;
  }

  function openPromotionFieldDialog(kind) {
    const dialogNode = ensurePromotionFieldDialog();
    const definition = promotionDefinition(kind);
    promotionFieldDialogKind = kind;
    promotionFieldDialogDraft = [...promotionSelectedFields(kind)];
    let draft = promotionFieldDialogDraft;
    const selectorRoot = dialogNode.querySelector('[data-product-detail-field-selector]');
    const config = {
      root: selectorRoot,
      groups: promotionGroups(kind),
      selected: draft,
      availableTitle: '可选字段',
      availableHint: '勾选要展示的字段',
      previewTitle: '字段预览',
      previewHint: '按表格列顺序展示',
      optionDataAttribute: 'data-product-detail-field-key',
      previewDataAttribute: 'data-product-detail-field-preview',
      onChange: (next) => { promotionFieldDialogDraft = next; updatePromotionFieldDialog(kind, next); },
    };
    if (!promotionFieldSelectors[kind]) promotionFieldSelectors[kind] = window.TmallUI?.fieldSelector?.(config);
    else promotionFieldSelectors[kind].setConfig(config);
    promotionFieldSelectors[kind]?.setSelected(draft);
    const select = dialogNode.querySelector('[data-product-detail-template-select]');
    select.replaceChildren();
    promotionTemplateList(kind).forEach((template) => {
      const option = document.createElement('option'); option.value = template.id; option.textContent = template.name; select.appendChild(option);
    });
    select.value = promotionFieldState[kind].activeTemplate || definition.templates[0].id;
    const managerRoot = dialogNode.querySelector('[data-product-detail-template-manager]');
    const templates = Object.fromEntries(promotionTemplateList(kind).map((template) => [template.id, { label: template.name, columns: [...template.fields] }]));
    if (!promotionTemplateManager) {
      promotionTemplateManager = window.DemoFieldTemplateManager?.create({
        root: managerRoot,
        builtinKeys: definition.templates.map((template) => template.id),
        templates,
        onChange: (event) => {
          const activeKind = promotionFieldDialogKind || kind;
          const activeTemplates = Object.fromEntries(promotionTemplateList(activeKind).map((template) => [template.id, { label: template.name, columns: [...template.fields] }]));
          if (event.type === 'use') {
            promotionFieldDialogDraft = [...(activeTemplates[event.key]?.columns || [])];
            promotionFieldSelectors[activeKind]?.setSelected(promotionFieldDialogDraft);
            updatePromotionFieldDialog(activeKind, promotionFieldDialogDraft);
          }
        },
        onDelete: async (key) => {
          const activeKind = promotionFieldDialogKind || kind;
          delete promotionFieldState[activeKind].customTemplates[key];
          savePromotionFieldState();
          openPromotionFieldDialog(activeKind);
        },
      });
    } else {
      promotionTemplateManager.setBuiltinKeys(definition.templates.map((template) => template.id));
      promotionTemplateManager.setTemplates(templates);
    }
    dialogNode.querySelector('[data-product-detail-template-apply]').onclick = () => {
      const template = promotionTemplateList(kind).find((item) => item.id === select.value);
      if (!template) return;
      promotionFieldDialogDraft = [...template.fields]; promotionFieldSelectors[kind]?.setSelected(promotionFieldDialogDraft); updatePromotionFieldDialog(kind, promotionFieldDialogDraft);
    };
    dialogNode.querySelector('[data-product-detail-fields-reset]').onclick = () => {
      promotionFieldDialogDraft = [...definition.templates[0].fields]; promotionFieldSelectors[kind]?.setSelected(promotionFieldDialogDraft); updatePromotionFieldDialog(kind, promotionFieldDialogDraft);
    };
    dialogNode.querySelector('[data-product-detail-template-save]').onclick = () => {
      const nameInput = dialogNode.querySelector('[data-product-detail-template-name]');
      const name = nameInput.value.trim();
      if (!name || !promotionFieldDialogDraft.length) return;
      const id = `detail-${kind}-${Date.now()}`;
      promotionFieldState[kind].customTemplates[id] = { name, fields: [...promotionFieldDialogDraft] };
      nameInput.value = ''; savePromotionFieldState(); openPromotionFieldDialog(kind);
    };
    dialogNode.querySelector('[data-product-detail-fields-apply]').onclick = () => {
      if (!promotionFieldDialogDraft.length) return;
      promotionFieldState[kind].selected = [...promotionFieldDialogDraft]; promotionFieldState[kind].page = 1; savePromotionFieldState(); dialogNode.close(); renderCurrentPanel();
    };
    updatePromotionFieldDialog(kind, draft);
    if (!dialogNode.open) dialogNode.showModal();
    window.lucide?.createIcons();
  }

  // 这张表自己分页 + 排序，排序必须作用在**全量**行上再切片。
  // 早先是交给全局 table-controls 排序，而它只排 DOM 里已经切好的当前页，
  // 点表头排序的结果是错的（只在当前 20 行内乱序）。会话级状态，不落 localStorage。
  const promotionTableSort = {
    channel: { key: '', direction: '' },
    campaign: { key: '', direction: '' },
  };
  let promotionCampaignDetailState = { campaignId: '', loading: false, payload: null, error: '' };

  function renderPromotionCampaignDetail(target) {
    if (!target) return;
    target.replaceChildren();
    const state = promotionCampaignDetailState;
    if (!state.campaignId) {
      target.appendChild(node('p', 'panel__hint', '点击推广计划名称查看计划构成与汇总证据。'));
      return;
    }
    if (state.loading) {
      target.appendChild(node('p', 'panel__hint', '正在加载计划下钻…'));
      return;
    }
    if (state.error) {
      target.appendChild(node('p', 'panel__hint', state.error));
      return;
    }
    const data = state.payload?.data || {};
    const summary = data.summary || {};
    const heading = node('h4', 'product-detail-promotion-block__title', `计划下钻：${summary.campaign_name || state.campaignId}`);
    const hint = node('p', 'panel__hint', `${summary.channel || '--'} · ${summary.plan_type || '--'} · 覆盖 ${number(data.products?.length || 0)} 个商品`);
    const list = node('div', 'status-list');
    list.append(
      node('div', 'status-list__item', `花费 / 成交：${promotionFormat(summary.ad_spend, 'money')} / ${promotionFormat(summary.attributed_payment_amount, 'money')}`),
      node('div', 'status-list__item', `ROI / 点击转化率：${summary.roi == null ? '--' : Number(summary.roi).toFixed(2)} / ${promotionFormat(summary.cvr, 'percent')}`),
    );
    target.append(heading, hint, list);
    const products = Array.isArray(data.products) ? data.products : [];
    if (!products.length) {
      target.appendChild(node('p', 'panel__hint', '当前计划没有可验证的商品映射。'));
      return;
    }
    target.appendChild(window.TmallUI.table({
      columns: [
        { key: 'title', label: '商品' },
        { key: 'productId', label: '商品 ID' },
        { key: 'creativeCount', label: '创意数', numeric: true },
      ],
      rows: products.map((product) => ({
        title: product.title || product.product_name || '--',
        productId: product.product_id || '--',
        creativeCount: number(product.creative_count),
      })),
    }));
  }

  async function loadPromotionCampaignDetail(campaignId) {
    if (!current || !campaignId) return;
    const range = window.TmallDateRange?.getState?.() || {};
    const session = current;
    const requestToken = token;
    const pendingState = { campaignId: String(campaignId), loading: true, payload: null, error: '' };
    promotionCampaignDetailState = pendingState;
    renderCurrentPanel();
    try {
      const query = new URLSearchParams({ campaign_id: String(campaignId) });
      if (range.startDate) query.set('start', range.startDate);
      if (range.endDate) query.set('end', range.endDate);
      const payload = await DemoApi.domainRequest(`/api/promotion/campaign-detail?${query}`);
      if (current !== session || token !== requestToken || promotionCampaignDetailState !== pendingState) return;
      promotionCampaignDetailState = { campaignId: String(campaignId), loading: false, payload, error: '' };
    } catch (error) {
      if (current !== session || token !== requestToken || promotionCampaignDetailState !== pendingState) return;
      promotionCampaignDetailState = { campaignId: String(campaignId), loading: false, payload: null, error: error.message || '计划下钻加载失败，请重试。' };
    }
    renderCurrentPanel();
  }

  function promotionSortValue(row, column) {
    const raw = column.key === 'campaign_name' ? (row.campaign_name || row.campaign_id) : row[column.key];
    if (raw == null || raw === '') return null;
    return typeof raw === 'number' ? raw : String(raw);
  }

  function sortedPromotionRows(kind, rows) {
    const sort = promotionTableSort[kind];
    if (!sort?.key || !sort.direction) return rows;
    const column = promotionColumns(kind).find((item) => item.key === sort.key);
    if (!column) return rows;
    const factor = sort.direction === 'desc' ? -1 : 1;
    return [...rows].sort((first, second) => {
      const left = promotionSortValue(first, column);
      const right = promotionSortValue(second, column);
      if (left === null && right === null) return 0;
      if (left === null) return 1;
      if (right === null) return -1;
      if (typeof left === 'number' && typeof right === 'number') return (left - right) * factor;
      return String(left).localeCompare(String(right), 'zh-CN', { numeric: true }) * factor;
    });
  }

  function renderPromotionTable(kind, rows) {
    const definition = promotionDefinition(kind);
    const state = promotionFieldState[kind];
    const columns = promotionColumns(kind).filter((column) => promotionSelectedFields(kind).includes(column.key));
    const pageSize = definition.defaultPageSize;
    const allRows = sortedPromotionRows(kind, rows);
    const totalPages = Math.max(1, Math.ceil(allRows.length / pageSize));
    state.page = Math.min(state.page, totalPages);
    const start = (state.page - 1) * pageSize;
    const visibleRows = allRows.slice(start, start + pageSize);
    const tableRows = visibleRows.map((row) => Object.fromEntries(columns.map((column) => {
      const raw = column.key === 'campaign_name' ? (row.campaign_name || row.campaign_id) : row[column.key];
      return [column.key, promotionFormat(raw, column.format)];
    })));
    const table = window.TmallUI?.table?.({ caption: definition.label, className: 'product-detail-promotion-table', columns: columns.map((column) => ({ key: column.key, label: column.label, numeric: Boolean(column.format) })), rows: tableRows });
    if (table) {
      // 这张表自带分页（即下方 controls），要告诉全局表格增强不要再挂一套分页器，
      // 否则会出现两个分页条，而且全局那条按「已切片的行」统计，显示成"共 5 行"。
      const inner = table.querySelector('table.ui-data-table');
      if (inner) {
        inner.setAttribute('data-table-pagination', 'server');
        // 全局排序只作用于当前页，这里关掉它，换成本表的表头按钮在全量数据上排
        const sort = promotionTableSort[kind];
        [...inner.querySelectorAll('thead th')].forEach((cell, index) => {
          const column = columns[index];
          cell.dataset.sortable = 'false';
          if (!column) return;
          const active = sort.key === column.key ? sort.direction : '';
          const arrow = active === 'asc' ? ' ↑' : active === 'desc' ? ' ↓' : '';
          const button = node('button', 'promotion-sort-button', `${column.label}${arrow}`);
          button.type = 'button';
          button.setAttribute('aria-label', `${column.label}，${active === 'asc' ? '当前升序，点击切换降序'
            : active === 'desc' ? '当前降序，点击切换升序' : '点击升序排序'}`);
          button.addEventListener('click', () => {
            if (sort.key !== column.key) { sort.key = column.key; sort.direction = 'asc'; }
            else sort.direction = sort.direction === 'asc' ? 'desc' : 'asc';
            state.page = 1;
            renderCurrentPanel();
          });
          cell.replaceChildren(button);
        });
        if (kind === 'campaign') {
          const campaignColumnIndex = columns.findIndex((column) => column.key === 'campaign_name');
          if (campaignColumnIndex >= 0) {
            [...inner.querySelectorAll('tbody tr')].forEach((rowNode, index) => {
              const rowData = visibleRows[index];
              const cell = rowNode.children[campaignColumnIndex];
              if (!cell || !rowData) return;
              const drill = node('button', 'ui-button ui-button--link', rowData.campaign_name || rowData.campaign_id || '--');
              drill.type = 'button';
              drill.title = '查看计划商品构成';
              drill.addEventListener('click', () => loadPromotionCampaignDetail(rowData.campaign_id));
              cell.replaceChildren(drill);
            });
          }
        }
      }
      const controls = node('div', 'product-detail-promotion-pagination');
      const summary = node('span', 'panel__hint', `${rows.length} 条 · 第 ${state.page}/${totalPages} 页`);
      const previous = node('button', 'ui-button ui-button--ghost', '上一页'); previous.type = 'button'; previous.disabled = state.page <= 1; previous.addEventListener('click', () => { state.page -= 1; renderCurrentPanel(); });
      const next = node('button', 'ui-button ui-button--ghost', '下一页'); next.type = 'button'; next.disabled = state.page >= totalPages; next.addEventListener('click', () => { state.page += 1; renderCurrentPanel(); });
      controls.append(summary, previous, next); table.appendChild(controls); return table;
    }
    return node('p', 'panel__hint', '表格组件尚未加载');
  }


  // 空数据的正确表达：接口会明确回 availability='no-data'，
  // 早先这里照样渲染成一片 ¥0/--（money(undefined) 就是 ¥0），
  // 让人误以为"付费数据丢了"，其实只是这个区间没有数据。
  function promotionEmptyState(payload) {
    const range = window.TmallDateRange?.getState?.() || {};
    const cutoff = current?.view?.detail?.summary?.data_cutoff_date;
    const period = range.startDate && range.endDate ? `${range.startDate} ~ ${range.endDate}` : '当前范围';
    const wrapper = section('付费推广', '当前日期范围内，渠道在上、计划在下；字段可按推广分析页习惯配置。');
    const box = node('div', 'ui-empty-state');
    box.append(node('p', '', `所选区间 ${period} 没有推广数据。`));
    box.append(node('p', 'panel__hint', cutoff
      ? `商品数据截止 ${cutoff}，把日期范围的结束日调到该日或更早，就能看到推广数据。`
      : '该区间既没有推广计划事实、也没有商品花费记录。若正在导入/采集，请稍后点右上角刷新重试。'));
    if (Array.isArray(payload.limitations) && payload.limitations.length) {
      box.append(node('p', 'panel__hint', payload.limitations.join(' ')));
    }
    wrapper.appendChild(box);
    return wrapper;
  }

  function renderPromotion(promotion) {
    const payload = promotion || {};
    const summary = payload.summary || {};
    const channelRows = Array.isArray(payload.channel_mix) ? payload.channel_mix : [];
    const campaignRows = Array.isArray(payload.campaigns) ? payload.campaigns : [];
    // 无数据时接口回的是全 0（不是 null），所以零值也要当"没有数据"，
    // 否则又会渲染成一片 ¥0/--。
    const hasRows = channelRows.length > 0 || campaignRows.length > 0;
    const hasSpend = Number(summary.ad_spend || 0) > 0;
    if (!hasRows && !hasSpend) return promotionEmptyState(payload);
    const wrapper = section('付费推广', '当前日期范围内，渠道在上、计划在下；字段可按推广分析页习惯配置。');
    const metrics = node('div', 'detail-metrics product-detail-promotion-metrics');
    const value = (raw, format) => (raw == null ? '--' : format(raw));
    [
      ['推广花费', value(summary.ad_spend, money)],
      ['推广成交', value(summary.attributed_payment_amount, money)],
      ['推广 ROI', summary.roi == null ? '--' : Number(summary.roi).toFixed(2)],
      ['展现量', value(summary.impressions, number)],
      ['点击量', value(summary.clicks, number)],
      ['支付买家', value(summary.payment_buyers, number)],
      ['CTR / CVR', summary.ctr == null && summary.cvr == null ? '--' : `${percent(summary.ctr)} / ${percent(summary.cvr)}`],
      ['加购成本', value(summary.cart_cost, money)],
      ['拉新成本', value(summary.new_customer_cost, money)],
      ['引导潜客占比', value(summary.guide_potential_ratio, percent)],
    ].forEach(([label, text]) => metrics.appendChild(metric(label, text)));
    wrapper.appendChild(metrics);

    const body = node('div', 'product-detail-promotion-grid');
    const addBlock = (kind, title, rows, emptyMessage) => {
      const block = node('section', 'product-detail-promotion-block');
      const header = node('div', 'panel__header');
      const copy = node('div'); copy.append(node('h4', 'product-detail-promotion-block__title', title), node('p', 'panel__hint', `${rows.length} 条记录，可通过字段设置调整列`));
      const tools = node('div', 'panel__actions');
      const fields = node('button', 'ui-button ui-button--ghost', '字段设置'); fields.type = 'button'; fields.dataset.productDetailFieldsOpen = kind; fields.setAttribute('aria-label', `${title}字段设置`); fields.addEventListener('click', () => openPromotionFieldDialog(kind));
      tools.appendChild(fields); header.append(copy, tools); block.appendChild(header);
      if (!rows.length) block.appendChild(node('p', 'panel__hint', emptyMessage));
      else block.appendChild(renderPromotionTable(kind, rows));
      if (kind === 'campaign') {
        const detail = node('div', 'product-detail-promotion-campaign-detail');
        detail.dataset.productDetailPromotionCampaignDetail = '';
        renderPromotionCampaignDetail(detail);
        block.appendChild(detail);
      }
      return block;
    };
    body.append(addBlock('channel', '推广渠道汇总', Array.isArray(payload.channel_mix) ? payload.channel_mix : [], '当前日期范围暂无渠道推广数据'));
    body.append(addBlock('campaign', '推广计划汇总', Array.isArray(payload.campaigns) ? payload.campaigns : [], '当前日期范围暂无推广计划数据'));
    if (Array.isArray(payload.limitations) && payload.limitations.length) wrapper.appendChild(node('p', 'panel__hint product-detail-promotion-note', payload.limitations.join(' ')));
    wrapper.appendChild(body);
    return wrapper;
  }
  function renderNotes(notes) {
    const wrapper = section('备注');
    const list = node('div', 'status-list');
    if (!notes.length) list.append(node('p', 'panel__hint', '暂无备注'));
    notes.forEach((note) => {
      const row = node('div', 'status-list__item');
      row.append(node('span', 'status-list__label', note.note || ''));
      const remove = node('button', 'ui-button ui-button--ghost', '删除'); remove.type = 'button';
      remove.addEventListener('click', async () => {
        if (!window.confirm('删除备注后无法恢复，确定删除吗？')) return;
        remove.disabled = true;
        try {
          await DemoApi.request(`/api/notes/${Number(note.id)}`, { method: 'DELETE' });
          await reload();
        } catch (error) {
          reportMutationError(error, '删除备注失败，请重试');
        } finally {
          if (remove.isConnected) remove.disabled = false;
        }
      });
      row.appendChild(remove); list.appendChild(row);
    });
    const form = node('div', 'filter-group');
    const input = node('input', 'input'); input.placeholder = '新增备注'; input.setAttribute('aria-label', '新增备注');
    const add = node('button', 'ui-button', '新增'); add.type = 'button';
    add.addEventListener('click', async () => {
      const note = input.value.trim();
      if (!note) return;
      add.disabled = true;
      try {
        await DemoApi.request('/api/notes', jsonOptions({ product_id: current.productId, note }));
        input.value = '';
        await reload();
      } catch (error) {
        reportMutationError(error, '新增备注失败，请重试');
      } finally {
        if (add.isConnected) add.disabled = false;
      }
    });
    form.append(input, add); wrapper.append(list, form); return wrapper;
  }

  function renderTags(payload) {
    const wrapper = section('标签');
    const tags = (Array.isArray(payload) ? payload : []).find((row) => String(row.product_id) === current.productId)?.tags || [];
    const list = node('div', 'chip-list');
    (tags.length ? tags : ['暂无标签']).forEach((tag) => list.append(node('span', 'chip', tag)));
    const form = node('div', 'filter-group');
    const input = node('input', 'input'); input.placeholder = '新增标签'; input.setAttribute('aria-label', '新增标签');
    const add = node('button', 'ui-button', '新增'); add.type = 'button';
    add.addEventListener('click', async () => {
      const tag = input.value.trim();
      if (!tag) return;
      add.disabled = true;
      try {
        await DemoApi.request('/api/product_tags', jsonOptions({ product_id: current.productId, tag }));
        input.value = '';
        await reload();
      } catch (error) {
        reportMutationError(error, '新增标签失败，请重试');
      } finally {
        if (add.isConnected) add.disabled = false;
      }
    });
    form.append(input, add); wrapper.append(list, form); return wrapper;
  }

  function renderActions(payload) {
    const wrapper = section('运营动作');
    const actions = Array.isArray(payload?.data) ? payload.data : Array.isArray(payload) ? payload : [];
    const list = node('div', 'status-list');
    if (!actions.length) list.append(node('p', 'panel__hint', '暂无运营动作'));
    actions.forEach((action) => {
      const row = node('div', 'status-list__item');
      row.append(node('span', 'status-list__label', `${text(action.planned_at || action.action_date)} ${text(action.action_type)} ${text(action.action_detail, '')}`.trim()), node('span', 'ui-badge', text(action.status)));
      list.appendChild(row);
    });
    const form = node('div', 'product-detail-action-form');
    const type = node('input', 'input'); type.placeholder = '动作类型'; type.setAttribute('aria-label', '动作类型');
    const detail = node('input', 'input'); detail.placeholder = '动作说明'; detail.setAttribute('aria-label', '动作说明');
    const add = node('button', 'ui-button ui-button--primary', '新增动作'); add.type = 'button';
    add.setAttribute('data-capability-key', 'product-detail.create_action');
    const canCreateAction = window.DemoApi?.canPage?.('product-detail', 'product-detail.create_action') === true;
    add.disabled = !canCreateAction;
    if (!canCreateAction) add.title = '当前数据条件不满足创建运营动作';
    add.addEventListener('click', async () => {
      if (window.DemoApi?.canPage?.('product-detail', 'product-detail.create_action') !== true) return;
      if (!type.value.trim()) return type.focus();
      add.disabled = true;
      try {
        await DemoApi.domainRequest('/api/actions', jsonOptions({ capability_key: 'product-detail.create_action', product_id: current.productId, purpose_type: 'increase_sales', purpose_note: detail.value.trim() || type.value.trim(), action_type: type.value.trim(), action_detail: detail.value.trim(), target_metric: 'payment_amount', planned_at: new Date().toISOString().slice(0, 10), observer_window_days: 7, assigned_to: '运营人员' }));
        type.value = ''; detail.value = '';
        await reload();
      } catch (error) {
        reportMutationError(error, '新增运营动作失败，请重试');
      } finally {
        if (add.isConnected) add.disabled = !canCreateAction;
      }
    });
    form.append(type, detail, add); wrapper.append(list, form); return wrapper;
  }

  function updateTabState(focus = false) {
    if (!drawer || !current) return;
    drawer.node.querySelectorAll('[data-product-detail-tab]').forEach((button) => {
      const active = button.dataset.productDetailTab === current.activeTab;
      button.setAttribute('aria-selected', String(active));
      button.tabIndex = active ? 0 : -1;
      if (active && focus) button.focus();
    });
  }

  function renderActivePanel() {
    const tab = current.activeTab;
    const view = current.view || {};
    const panel = node('section', 'lifecycle-detail-panel product-detail-tabpanel');
    panel.id = `product-detail-panel-${tab}`;
    panel.dataset.productDetailPanel = tab;
    panel.setAttribute('role', 'tabpanel');
    panel.setAttribute('aria-labelledby', `product-detail-tab-${tab}`);
    panel.tabIndex = 0;
    const detail = view.detail || {};
    if (tab === 'overview') {
      const overviewLayout = node('div', 'product-detail-overview-layout');
      overviewLayout.append(renderMetrics(detail, view.promotionSummary), renderOverviewTrend(detail.daily_trend), renderIdentity(detail));
      panel.appendChild(overviewLayout);
    }
    if (tab === 'promotion') panel.append(view.promotionError ? section('付费推广', '推广数据加载失败，不影响其他详情') : renderPromotion(view.promotion));
    if (tab === 'trend') panel.append(renderTrend(detail.daily_trend));
    if (tab === 'search') panel.append(renderSearch(detail));
    if (tab === 'flow-source') {
      panel.append(view.flowSourceError && !view.flowSource
        ? section('流量结构', '流量来源加载失败，不影响其他详情')
        : renderFlowSourceTab(view.flowSource, view.flowAllSource));
    }
    if (tab === 'lifecycle') panel.append(renderLifecycle(detail.lifecycle));
    if (tab === 'collaboration') {
      panel.append(
        view.notesError ? section('备注', '备注加载失败，不影响其他详情') : renderNotes(view.notes || []),
        view.tagsError ? section('标签', '标签加载失败，不影响其他详情') : renderTags(view.tags || []),
        view.actionsError ? section('运营动作', '运营动作加载失败，不影响其他详情') : renderActions(view.actions),
      );
    }
    return panel;
  }

  function renderCurrentPanel() {
    destroyOverviewTrendChart();
    body.replaceChildren(renderActivePanel());
    if (current?.activeTab === 'overview') mountOverviewTrendChart(current.view?.detail?.daily_trend || []);
    window.lucide?.createIcons();
  }

  function selectedRangeQuery() {
    const range = window.TmallDateRange?.getState?.() || {};
    const params = new URLSearchParams();
    if (range.startDate) params.set('start', range.startDate);
    if (range.endDate) params.set('end', range.endDate);
    return params.toString();
  }

  // 流量来源要显式声明口径：all=全程来源（有层级树），farthest=第一次访问来源（扁平渠道）
  function itemFlowQuery(id, belong) {
    const range = window.TmallDateRange?.getState?.() || {};
    const params = new URLSearchParams({ item_id: id, belong });
    if (range.startDate && range.endDate) {
      params.set('start', range.startDate);
      params.set('end', range.endDate);
    }
    return params.toString();
  }

  function selectTab(tab, focus = false) {
    if (!current || !detailTabs.some(([id]) => id === tab)) return;
    current.activeTab = tab;
    updateTabState(focus);
    if (current.view) {
      renderCurrentPanel();
    }
  }

  function renderDrawerImage(product) {
    const imageRoot = drawerImage;
    if (!imageRoot) return;
    const thumbnailUrl = String(product.image_url || '').trim();
    const existing = imageRoot.querySelector('img');
    if (thumbnailUrl && existing?.getAttribute('src') === thumbnailUrl) { existing.alt = product.title || ''; return; }
    imageRoot.replaceChildren();
    if (thumbnailUrl) {
      const image = new Image(52, 52);
      image.loading = 'lazy';
      image.src = thumbnailUrl;
      image.alt = product.title || '';
      imageRoot.removeAttribute('aria-hidden');
      image.addEventListener('error', () => {
        if (image.parentNode !== imageRoot) return;
        imageRoot.replaceChildren();
        imageRoot.setAttribute('aria-hidden', 'true');
        const placeholder = node('i');
        placeholder.setAttribute('data-lucide', 'image');
        imageRoot.appendChild(placeholder);
        window.lucide?.createIcons?.({ attrs: { 'stroke-width': 1.75 } });
      }, { once: true });
      imageRoot.appendChild(image);
    } else {
      imageRoot.setAttribute('aria-hidden', 'true');
      const placeholder = node('i');
      placeholder.setAttribute('data-lucide', 'image');
      imageRoot.appendChild(placeholder);
    }
  }

  async function load() {
    const loadToken = ++token;
    promotionCampaignDetailState = { campaignId: '', loading: false, payload: null, error: '' };
    destroyOverviewTrendChart();
    body.replaceChildren(node('div', 'ui-empty-state', '正在加载完整商品详情…'));
    const range = window.TmallDateRange?.getState?.() || {};
    const period = String(range.endDate || range.startDate || new Date().toISOString().slice(0, 10)).slice(0, 7);
    const id = encodeURIComponent(current.productId);
    const rangeQuery = selectedRangeQuery();
    const detailUrl = `/api/products/${id}/detail${rangeQuery ? `?${rangeQuery}` : ''}`;
    const results = await Promise.allSettled([
      DemoApi.domainRequest(detailUrl),
      DemoApi.domainRequest(`/api/promotion/product-detail?${new URLSearchParams({ start: range.startDate || `${period}-01`, end: range.endDate || `${period}-31`, product_id: current.productId })}`),
      DemoApi.loadPageCapabilities('product-detail'),
      DemoApi.request(`/api/notes/${id}`),
      DemoApi.request(`/api/product_tags?dim=monthly&period=${encodeURIComponent(period)}`),
      DemoApi.domainRequest(`/api/actions?product_id=${id}&limit=500`),
      // 主口径：第一次访问来源（每天都有数据，覆盖完整）
      DemoApi.domainRequest(`/api/sycm/item-flow/summary?${itemFlowQuery(current.productId, 'farthest')}`),
      // 补充口径：全程来源（接口自带原始多级渠道，但目前只有个别日期采到）
      DemoApi.domainRequest(`/api/sycm/item-flow/summary?${itemFlowQuery(current.productId, 'all')}`),
    ]);
    if (loadToken !== token || !current) return;
    const [detailResult, promotionResult, capabilityResult, notesResult, tagsResult, actionsResult, flowResult, flowAllResult] = results;
    if (detailResult.status !== 'fulfilled') {
      body.replaceChildren(node('div', 'ui-empty-state', detailResult.reason?.message || '商品详情加载失败'));
      return;
    }
    const detail = detailResult.value.data || {};
    const product = detail.product || {};
    drawerTitle.textContent = product.title || current.title || '商品详情';
    const sourceMeta = current.sourceRule?.name
      ? `来源分群：${current.sourceRule.name}${current.sourceRule.period ? ` · ${current.sourceRule.period}` : ''}`
      : '';
    drawerMeta.textContent = [product.category, product.style, statusLabel(product.status), sourceMeta].filter(Boolean).join(' · ') || '--';
    const selectedRange = range.startDate && range.endDate ? `${range.startDate} ~ ${range.endDate}` : '全量数据';
    drawerId.textContent = `商品 ID ${product.product_id || current.productId} · 当前范围 ${selectedRange} · 数据截止 ${text(detail.summary?.data_cutoff_date)}`;
    renderDrawerImage(product);
    const unwrap = (result) => (result && result.status === 'fulfilled'
      ? (result.value?.data || result.value) : null);
    const promotion = unwrap(promotionResult) || {};
    let flowSource = unwrap(flowResult);
    let flowAllSource = unwrap(flowAllResult);
    if (flowAllSource && !(flowAllSource.channels || []).length) flowAllSource = null;
    const maxLevel = (data) => Math.max(...(data?.levels || [0]), 0);
    if (flowAllSource && flowSource) {
      // 补充块只有在「层级更深」或「时间窗不同」时才有存在意义，否则是重复内容
      const sameWindow = JSON.stringify(flowAllSource.data_dates) === JSON.stringify(flowSource.data_dates);
      if (sameWindow && maxLevel(flowAllSource) <= maxLevel(flowSource)) flowAllSource = null;
    }
    if (!flowSource || !(flowSource.channels || []).length) {
      // 主口径没数据时才有必要用全程来源顶上，避免流量结构整块空白
      if (flowAllSource) {
        flowSource = flowAllSource;
        flowAllSource = null;
      }
    }
    current.view = {
      detail,
      promotion,
      // 概览页的推广四件套取这里（商品详情 summary 里没有推广归因成交/ROI/CTR/CVR）
      promotionSummary: promotion?.summary || null,
      promotionError: promotionResult.status !== 'fulfilled',
      capabilityError: capabilityResult.status !== 'fulfilled',
      notes: notesResult.status === 'fulfilled' ? (Array.isArray(notesResult.value) ? notesResult.value : notesResult.value?.data || []) : [],
      tags: tagsResult.status === 'fulfilled' ? (Array.isArray(tagsResult.value) ? tagsResult.value : tagsResult.value?.data || []) : [],
      actions: actionsResult.status === 'fulfilled' ? (actionsResult.value.data || actionsResult.value) : [],
      flowSource,
      flowAllSource,
      notesError: notesResult.status !== 'fulfilled',
      tagsError: tagsResult.status !== 'fulfilled',
      actionsError: actionsResult.status !== 'fulfilled',
      flowSourceError: flowResult.status !== 'fulfilled',
    };
    current.flowSource = current.view.flowSource;
    updateTabState();
    renderCurrentPanel();
  }

  async function reload() {
    await load();
    current?.onChange?.();
  }

  function open(options) {
    if (!options?.productId) return;
    ensureDialog();
    if (!drawer) return;
    current = { ...options, productId: String(options.productId), activeTab: 'overview', view: null };
    updateTabState();
    drawer.body.scrollTop = 0;
    // Identity is already known from the list; never show the previous product while loading.
    drawerTitle.textContent = current.title || '商品详情';
    drawerMeta.textContent = '正在读取商品信息…';
    drawerId.textContent = `商品 ID ${current.productId}`;
    renderDrawerImage({ title: current.title, image_url: current.imageUrl });
    promotionCampaignDetailState = { campaignId: '', loading: false, payload: null, error: '' };
    drawerWorkbench.href = current.workbenchUrl || `/products/${encodeURIComponent(current.productId)}`;
    if (!current.workbenchUrl && current.sourceRule?.key) drawerWorkbench.href += `?rule_key=${encodeURIComponent(current.sourceRule.key)}`;
    drawerWorkbench.removeAttribute('aria-disabled');
    drawerWorkbench.tabIndex = 0;
    // 触发器焦点归还由抽屉记录（open(trigger)），不再手工保存 returnFocus。
    drawer.open(options.trigger || null);
    load().catch((error) => body.replaceChildren(node('div', 'ui-empty-state', error.message || '商品详情加载失败')));
    window.lucide?.createIcons();
  }

  window.addEventListener('tmall:date-range-change', () => {
    if (!current || !drawer || drawer.node.hidden) return;
    load().catch((error) => body.replaceChildren(node('div', 'ui-empty-state', error.message || '商品详情加载失败')));
  });

  // Both the public close() and the shared shell's ESC/backdrop/close button end
  // this product session, so pending responses cannot render into a closed view.
  function resetSession() {
    token += 1;
    current = null;
    destroyOverviewTrendChart();
  }

  function close() {
    if (drawer && !drawer.node.hidden) drawer.close();
    else resetSession();
  }

  window.ProductDetailDialog = { open, close };
})();
