(function () {
  const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  const chartPointRadius = () => window.DemoCharts?.chartPointRadius?.() || 3;
  const chartLineWidth = () => window.DemoCharts?.chartLineWidth?.() || 2;
  let dialog = null;
  let body = null;
  let returnFocus = null;
  let current = null;
  let token = 0;
  let overviewTrendChart = null;
  const localThumbnailIds = new Set(['DEMO-003', 'DEMO-004', 'DEMO-005', 'DEMO-006', 'DEMO-007']);
  const localThumbnailUrl = (productId) => localThumbnailIds.has(String(productId)) ? `/assets/product-thumbs/${encodeURIComponent(productId)}.jpg` : '';
  const detailTabs = [
    ['overview', '经营概览'],
    ['trend', '日趋势'],
    ['lifecycle', '生命周期'],
    ['collaboration', '协作记录'],
  ];

  const money = (value) => `¥${Number(value || 0).toLocaleString('zh-CN', { maximumFractionDigits: 2 })}`;
  const number = (value) => Number(value || 0).toLocaleString('zh-CN');
  const percent = (value) => value == null ? '--' : `${(Number(value) * 100).toFixed(2)}%`;
  const text = (value, fallback = '--') => value == null || value === '' ? fallback : String(value);
  const statusLabel = (value) => window.DemoLabels?.label?.('status', value, value) || text(value);
  const jsonOptions = (payload, method = 'POST') => ({ method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });

  function node(tag, className, copy) {
    const item = document.createElement(tag);
    if (className) item.className = className;
    if (copy != null) item.textContent = copy;
    return item;
  }

  function ensureDialog() {
    if (dialog) return;
    dialog = document.createElement('dialog');
    dialog.className = 'lifecycle-detail product-detail-dialog';
    dialog.setAttribute('data-modal-kind', 'detail');
    dialog.setAttribute('aria-labelledby', 'sharedProductDetailTitle');
    dialog.innerHTML = `
      <div class="product-detail-dialog__shell">
        <div class="lifecycle-detail__header product-detail-dialog__header"><div class="lifecycle-detail__product"><span class="lifecycle-detail__image product-detail-dialog__image" data-shared-product-image aria-hidden="true"><i data-lucide="image"></i></span><div><h2 id="sharedProductDetailTitle" class="panel__title" data-shared-product-title>商品详情</h2><p class="panel__hint" data-shared-product-meta data-shared-product-subtitle>--</p><div class="lifecycle-detail__id" data-shared-product-id>--</div></div></div><button class="button button--ghost" type="button" data-shared-product-close aria-label="关闭商品详情"><i data-lucide="x"></i><span>关闭</span></button></div>
        <div class="product-detail-dialog__body" data-shared-product-body>
          <div class="lifecycle-detail-tabs product-detail-dialog__tabs" role="tablist" aria-label="商品详情分组">
            ${detailTabs.map(([id, label], index) => `<button class="lifecycle-detail-tab product-detail-dialog__tab" id="product-detail-tab-${id}" role="tab" type="button" data-product-detail-tab="${id}" aria-selected="${index === 0}" aria-controls="product-detail-panel-${id}" tabindex="${index === 0 ? 0 : -1}">${label}</button>`).join('')}
          </div>
          <div class="product-detail-dialog__panels" data-shared-product-panels></div>
        </div>
      </div>`;
    document.body.appendChild(dialog);
    body = dialog.querySelector('[data-shared-product-panels]');
    const workbench = node('a', 'button button--ghost', '打开完整工作台');
    workbench.setAttribute('data-shared-product-workbench', '');
    workbench.setAttribute('aria-label', '打开完整商品详情工作台');
    workbench.href = '/products/';
    dialog.querySelector('.product-detail-dialog__header').insertBefore(workbench, dialog.querySelector('[data-shared-product-close]'));
    dialog.querySelector('[data-shared-product-close]').addEventListener('click', close);
    dialog.addEventListener('cancel', (event) => { event.preventDefault(); close(); });
    dialog.addEventListener('click', (event) => { if (event.target === dialog) close(); });
    dialog.querySelector('[role="tablist"]').addEventListener('click', (event) => {
      const tab = event.target.closest('[data-product-detail-tab]');
      if (tab) selectTab(tab.dataset.productDetailTab, false);
    });
    dialog.querySelector('[role="tablist"]').addEventListener('keydown', (event) => {
      const tabs = [...dialog.querySelectorAll('[data-product-detail-tab]')];
      const index = tabs.indexOf(event.target.closest('[data-product-detail-tab]'));
      if (index < 0 || !['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
      event.preventDefault();
      const nextIndex = event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1 : (index + (event.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length;
      selectTab(tabs[nextIndex].dataset.productDetailTab, true);
    });
    dialog.addEventListener('close', () => {
      document.body.classList.remove('demo-scroll-lock');
      returnFocus?.focus?.();
      returnFocus = null;
    });
  }

  function metric(label, value) {
    const item = node('div', 'detail-metric');
    item.append(node('span', '', label), node('strong', '', value));
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
    const wrapper = node('section', 'plain-panel panel product-detail-section');
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
    dialog.querySelector('[data-shared-product-workbench]').href = `/products/${encodeURIComponent(product.product_id || current.productId)}`;
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

  function renderMetrics(detail, promotion) {
    const summary = detail.summary || {};
    const wrapper = section('经营与推广指标', '同一弹窗内同时核对经营表现和当前推广上下文。');
    const grid = node('div', 'detail-metrics product-detail-metrics');
    grid.append(
      metric('销售额', money(summary.payment_amount)), metric('净销售额', money(summary.net_sales)),
      metric('退款金额', money(summary.refund_amount)), metric('商品访客数', number(summary.product_visitors)),
      metric('商品支付转化率', percent(summary.payment_conversion_rate)), metric('客单价', money(summary.average_order_value)),
      metric('推广花费', money(promotion?.ad_spend ?? summary.ad_spend)),
      metric('推广成交', money(promotion?.attributed_payment_amount)),
      metric('推广 ROI', promotion?.roi == null ? '--' : Number(promotion.roi).toFixed(2)),
      metric('CTR / CVR', promotion ? `${percent(promotion.ctr)} / ${percent(promotion.cvr)}` : '--')
    );
    wrapper.append(metricGroups(grid));
    return wrapper;
  }

  function renderOverviewTrend(rows) {
    const wrapper = node('article', 'chart-panel panel lifecycle-chart-panel product-detail-overview-trend');
    const header = node('div', 'panel__header product-detail-overview-trend__header');
    const copy = node('div');
    copy.append(node('h4', 'panel__title', '经营走势'), node('p', 'panel__hint', '与上方经营与推广指标同源，按月聚合查看销售、净销售与推广花费。'));
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
    const chart = dialog?.querySelector('[data-product-overview-trend]');
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
    const tableWrap = node('div', 'data-table-wrap');
    const table = node('table', 'data-table');
    table.innerHTML = '<thead><tr><th>日期</th><th class="num">支付金额</th><th class="num">净销售额</th><th class="num">成功退款金额</th><th class="num">商品访客数</th><th class="num">推广花费</th></tr></thead>';
    const tbody = document.createElement('tbody');
    rows.slice(-31).reverse().forEach((row) => {
      const tr = document.createElement('tr');
      [row.date, money(row.payment_amount), money(row.net_sales), money(row.refund_amount), number(row.product_visitors), money(row.ad_spend)].forEach((value, index) => {
        const td = node('td', index ? 'num' : '', value); tr.appendChild(td);
      });
      tbody.appendChild(tr);
    });
    table.appendChild(tbody); tableWrap.appendChild(table); wrapper.appendChild(tableWrap);
    return wrapper;
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

  function renderNotes(notes) {
    const wrapper = section('备注');
    const list = node('div', 'status-list');
    if (!notes.length) list.append(node('p', 'panel__hint', '暂无备注'));
    notes.forEach((note) => {
      const row = node('div', 'status-list__item');
      row.append(node('span', 'status-list__label', note.note || ''));
      const remove = node('button', 'button button--ghost', '删除'); remove.type = 'button';
      remove.addEventListener('click', async () => {
        if (!window.confirm('删除备注后无法恢复，确定删除吗？')) return;
        await DemoApi.request(`/api/notes/${Number(note.id)}`, { method: 'DELETE' });
        await reload();
      });
      row.appendChild(remove); list.appendChild(row);
    });
    const form = node('div', 'filter-group');
    const input = node('input', 'input'); input.placeholder = '新增备注'; input.setAttribute('aria-label', '新增备注');
    const add = node('button', 'button', '新增'); add.type = 'button';
    add.addEventListener('click', async () => { const note = input.value.trim(); if (!note) return; await DemoApi.request('/api/notes', jsonOptions({ product_id: current.productId, note })); input.value = ''; await reload(); });
    form.append(input, add); wrapper.append(list, form); return wrapper;
  }

  function renderTags(payload) {
    const wrapper = section('标签');
    const tags = (Array.isArray(payload) ? payload : []).find((row) => String(row.product_id) === current.productId)?.tags || [];
    const list = node('div', 'chip-list');
    (tags.length ? tags : ['暂无标签']).forEach((tag) => list.append(node('span', 'chip', tag)));
    const form = node('div', 'filter-group');
    const input = node('input', 'input'); input.placeholder = '新增标签'; input.setAttribute('aria-label', '新增标签');
    const add = node('button', 'button', '新增'); add.type = 'button';
    add.addEventListener('click', async () => { const tag = input.value.trim(); if (!tag) return; await DemoApi.request('/api/product_tags', jsonOptions({ product_id: current.productId, tag })); input.value = ''; await reload(); });
    form.append(input, add); wrapper.append(list, form); return wrapper;
  }

  function renderActions(payload) {
    const wrapper = section('运营动作');
    const actions = Array.isArray(payload?.data) ? payload.data : Array.isArray(payload) ? payload : [];
    const list = node('div', 'status-list');
    if (!actions.length) list.append(node('p', 'panel__hint', '暂无运营动作'));
    actions.forEach((action) => {
      const row = node('div', 'status-list__item');
      row.append(node('span', 'status-list__label', `${text(action.planned_at || action.action_date)} ${text(action.action_type)} ${text(action.action_detail, '')}`.trim()), node('span', 'badge', text(action.status)));
      list.appendChild(row);
    });
    const form = node('div', 'product-detail-action-form');
    const type = node('input', 'input'); type.placeholder = '动作类型'; type.setAttribute('aria-label', '动作类型');
    const detail = node('input', 'input'); detail.placeholder = '动作说明'; detail.setAttribute('aria-label', '动作说明');
    const add = node('button', 'button button--primary', '新增动作'); add.type = 'button';
    add.setAttribute('data-capability-key', 'product-detail.create_action');
    const canCreateAction = window.DemoApi?.canPage?.('product-detail', 'product-detail.create_action') === true;
    add.disabled = !canCreateAction;
    if (!canCreateAction) add.title = '当前数据条件不满足创建运营动作';
    add.addEventListener('click', async () => {
      if (window.DemoApi?.canPage?.('product-detail', 'product-detail.create_action') !== true) return;
      if (!type.value.trim()) return type.focus();
      await DemoApi.domainRequest('/api/actions', jsonOptions({ capability_key: 'product-detail.create_action', product_id: current.productId, purpose_type: 'increase_sales', purpose_note: detail.value.trim() || type.value.trim(), action_type: type.value.trim(), action_detail: detail.value.trim(), target_metric: 'payment_amount', planned_at: new Date().toISOString().slice(0, 10), observer_window_days: 7, assigned_to: '运营人员' }));
      type.value = ''; detail.value = ''; await reload();
    });
    form.append(type, detail, add); wrapper.append(list, form); return wrapper;
  }

  function updateTabState(focus = false) {
    if (!dialog || !current) return;
    dialog.querySelectorAll('[data-product-detail-tab]').forEach((button) => {
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
      overviewLayout.append(renderMetrics(detail, current.promotionContext), renderOverviewTrend(detail.daily_trend), renderIdentity(detail));
      panel.appendChild(overviewLayout);
    }
    if (tab === 'trend') panel.append(renderTrend(detail.daily_trend));
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

  function selectTab(tab, focus = false) {
    if (!current || !detailTabs.some(([id]) => id === tab)) return;
    current.activeTab = tab;
    updateTabState(focus);
    if (current.view) {
      renderCurrentPanel();
    }
  }

  async function load() {
    const loadToken = ++token;
    destroyOverviewTrendChart();
    body.replaceChildren(node('div', 'empty-state', '正在加载完整商品详情'));
    const range = window.TmallDateRange?.getState?.() || {};
    const period = String(range.endDate || range.startDate || new Date().toISOString().slice(0, 10)).slice(0, 7);
    const id = encodeURIComponent(current.productId);
    const rangeQuery = selectedRangeQuery();
    const detailUrl = `/api/products/${id}/detail${rangeQuery ? `?${rangeQuery}` : ''}`;
    const results = await Promise.allSettled([
      DemoApi.domainRequest(detailUrl),
      DemoApi.request(`/api/notes/${id}`),
      DemoApi.request(`/api/product_tags?dim=monthly&period=${encodeURIComponent(period)}`),
      DemoApi.domainRequest(`/api/actions?product_id=${id}&limit=500`),
      DemoApi.loadPageCapabilities('product-detail'),
    ]);
    if (loadToken !== token || !current) return;
    const [detailResult, notesResult, tagsResult, actionsResult, capabilityResult] = results;
    if (detailResult.status !== 'fulfilled') {
      body.replaceChildren(node('div', 'empty-state', detailResult.reason?.message || '商品详情加载失败'));
      return;
    }
    const detail = detailResult.value.data || {};
    const product = detail.product || {};
    dialog.querySelector('[data-shared-product-title]').textContent = product.title || current.title || '商品详情';
    dialog.querySelector('[data-shared-product-meta]').textContent = [product.category, product.style, statusLabel(product.status)].filter(Boolean).join(' · ') || '--';
    const selectedRange = range.startDate && range.endDate ? `${range.startDate} ~ ${range.endDate}` : '全量数据';
    dialog.querySelector('[data-shared-product-id]').textContent = `商品 ID ${product.product_id || current.productId} · 当前范围 ${selectedRange} · 数据截止 ${text(detail.summary?.data_cutoff_date)}`;
    const imageRoot = dialog.querySelector('[data-shared-product-image]');
    imageRoot.replaceChildren();
    const thumbnailUrl = localThumbnailUrl(product.product_id || current.productId);
    if (thumbnailUrl) {
      const image = new Image(52, 52);
      image.loading = 'lazy';
      image.src = thumbnailUrl;
      image.alt = product.title || '';
      imageRoot.removeAttribute('aria-hidden');
      image.addEventListener('error', () => {
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
    current.view = {
      detail,
      notes: notesResult.status === 'fulfilled' ? (notesResult.value || []) : [],
      tags: tagsResult.status === 'fulfilled' ? (tagsResult.value || []) : [],
      actions: actionsResult.status === 'fulfilled' ? actionsResult.value : [],
      notesError: notesResult.status !== 'fulfilled',
      tagsError: tagsResult.status !== 'fulfilled',
      actionsError: actionsResult.status !== 'fulfilled',
      capabilityError: capabilityResult.status !== 'fulfilled',
    };
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
    current = { ...options, productId: String(options.productId), activeTab: 'overview', view: null };
    returnFocus = options.trigger || document.activeElement;
    dialog.showModal();
    document.body.classList.add('demo-scroll-lock');
    load().catch((error) => body.replaceChildren(node('div', 'empty-state', error.message || '商品详情加载失败')));
    window.lucide?.createIcons();
  }

  window.addEventListener('tmall:date-range-change', () => {
    if (!current || !dialog?.open) return;
    load().catch((error) => body.replaceChildren(node('div', 'empty-state', error.message || '商品详情加载失败')));
  });

  function close() {
    token += 1;
    current = null;
    destroyOverviewTrendChart();
    if (dialog?.open) dialog.close();
  }

  window.ProductDetailDialog = { open, close };
})();
