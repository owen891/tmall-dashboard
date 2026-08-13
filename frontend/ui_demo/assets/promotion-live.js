(function () {
  const $ = (selector, root = document) => root.querySelector(selector);
  const focusableSelector = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';
  const state = { period: '', rows: [], alerts: [], activeTab: 'products', token: 0, drawerReturnFocus: null, chart: null };
  const money = (value) => `￥${Number(value || 0).toLocaleString('zh-CN', { maximumFractionDigits: 2 })}`;
  const number = (value) => Number(value || 0).toLocaleString('zh-CN');
  const ratio = (value) => Number(value || 0) > 0 ? Number(value).toFixed(2) : '--';
  const toast = (message) => window.DemoShell?.showToast?.(message) || window.alert(message);
  const setStatus = (message) => window.DemoShell?.setStatus?.(message);
  const text = (value, fallback = '--') => String(value == null || value === '' ? fallback : value);
  const element = (tag, className, value) => {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (value != null) node.textContent = value;
    return node;
  };
  const productId = (row) => String(row?.product_id || '');
  const overallRoi = (row) => Number(row?.overall_roi || 0) || (Number(row?.ad_spend || 0) ? Number(row?.payment_amount || 0) / Number(row.ad_spend) : 0);
  const drillRows = [];

  function getPeriod(detail) {
    const range = detail || window.TmallDateRange?.getState?.() || {};
    const value = range.endDate || range.startDate || new Date().toISOString().slice(0, 10);
    return String(value).slice(0, 7);
  }

  function requestPath(path) {
    return `${path}${path.includes('?') ? '&' : '?'}dim=monthly&period=${encodeURIComponent(state.period)}`;
  }

  function renderKpis(rows) {
    const spend = rows.reduce((total, row) => total + Number(row.ad_spend || 0), 0);
    const gmv = rows.reduce((total, row) => total + Number(row.payment_amount || 0), 0);
    $('[data-promotion-kpi="spend"]').textContent = money(spend);
    $('[data-promotion-kpi="gmv"]').textContent = money(gmv);
    $('[data-promotion-kpi="roi"]').textContent = spend ? (gmv / spend).toFixed(2) : '--';
    $('[data-promotion-kpi="products"]').textContent = number(rows.length);
    $('[data-promotion-kpi-note]').textContent = `${state.period || '--'} 商品口径`;
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
        labels: rows.map((row) => row.period),
        datasets: [
          { type: 'bar', label: '推广花费', data: rows.map((row) => Number(row.ad_spend || 0)), backgroundColor: 'rgb(217 119 6 / .62)', borderRadius: 4, yAxisID: 'y' },
          { type: 'bar', label: '成交金额', data: rows.map((row) => Number(row.gmv || 0)), backgroundColor: 'rgb(37 99 235 / .58)', borderRadius: 4, yAxisID: 'y' },
          { type: 'line', label: 'ROI', data: rows.map((row) => Number(row.overall_roi || 0)), borderColor: getComputedStyle(document.documentElement).getPropertyValue('--success').trim(), tension: .35, pointRadius: 3, borderWidth: 2, yAxisID: 'y1' }
        ]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { position: 'bottom', labels: { boxWidth: 12 } } },
        scales: { x: { grid: { display: false } }, y: { beginAtZero: true }, y1: { position: 'right', grid: { drawOnChartArea: false }, beginAtZero: true } }
      }
    });
  }

  function severityClass(severity) {
    return severity === 'danger' ? 'alert-list__item--danger' : '';
  }

  function renderAlerts(rows) {
    const container = $('[data-promotion-alerts]');
    const count = $('[data-promotion-alert-count]');
    container.replaceChildren();
    count.textContent = `${rows.length} 条`;
    if (!rows.length) {
      const empty = element('div', 'empty-state');
      empty.append(element('strong', '', '当前月份没有触发推广预警'), element('span', '', '预警由 API 按商品 ROI 与花费规则计算。'));
      container.appendChild(empty);
      return;
    }
    rows.forEach((alert) => {
      const item = element('div', `alert-list__item ${severityClass(alert.severity)}`.trim());
      const copy = element('div');
      copy.append(element('strong', '', text(alert.title, '未命名商品')), element('span', '', text(alert.message, '指标异常')));
      const button = element('button', 'button button--ghost', '查看商品');
      button.type = 'button';
      button.dataset.promotionDrill = productId(alert);
      button.addEventListener('click', () => openProductDrawer(alert, button));
      item.append(copy, button);
      container.appendChild(item);
    });
  }

  function clearTable(message) {
    const head = $('[data-promotion-head]');
    const body = $('[data-promotion-body]');
    head.replaceChildren();
    body.replaceChildren();
    const row = body.insertRow();
    const cell = row.insertCell();
    cell.textContent = message;
    cell.colSpan = 6;
  }

  function addHeaders(labels) {
    const head = $('[data-promotion-head]');
    head.replaceChildren();
    const row = document.createElement('tr');
    labels.forEach((label, index) => {
      const th = element('th', index > 0 ? 'num' : '', label);
      row.appendChild(th);
    });
    head.appendChild(row);
  }

  function addCell(row, value, className) {
    const cell = element('td', className || '', value);
    row.appendChild(cell);
    return cell;
  }

  function aggregate(type) {
    const map = {
      keywords: { label: '关键词汇总', spend: 'keyword_spend', roi: 'keyword_roi', ppc: 'keyword_ppc', description: '各商品的关键词推广字段汇总，不含词级明细。' },
      crowd: { label: '人群汇总', spend: 'crowd_spend', roi: 'crowd_roi', ppc: 'crowd_ppc', description: '各商品的人群推广字段汇总，不含人群包明细。' },
      site: { label: '站内渠道汇总', spend: 'site_spend', roi: 'site_roi', ppc: 'site_ppc', description: '各商品的站内渠道推广字段汇总，不含计划或资源位明细。' }
    }[type];
    const rows = state.rows.filter((row) => Number(row[map.spend] || 0) > 0);
    const spend = rows.reduce((total, row) => total + Number(row[map.spend] || 0), 0);
    const attributedGmv = rows.reduce((total, row) => total + Number(row[map.spend] || 0) * Number(row[map.roi] || 0), 0);
    const clicks = rows.reduce((total, row) => {
      const ppc = Number(row[map.ppc] || 0);
      return total + (ppc > 0 ? Number(row[map.spend] || 0) / ppc : 0);
    }, 0);
    return { ...map, sourceCount: rows.length, spend, attributedGmv, roi: spend ? attributedGmv / spend : 0, ppc: clicks ? spend / clicks : 0 };
  }

  function renderProducts() {
    addHeaders(['商品', '推广花费', '成交金额', '整体 ROI', '推广 ROI', '操作']);
    const body = $('[data-promotion-body]');
    body.replaceChildren();
    if (!state.rows.length) return clearTable('当前月份没有推广商品数据');
    state.rows.forEach((row) => {
      const tr = document.createElement('tr');
      const name = element('div', 'table-name');
      name.append(element('strong', '', text(row.title, '未命名商品')), element('span', '', productId(row)));
      const nameCell = document.createElement('td');
      nameCell.appendChild(name);
      tr.appendChild(nameCell);
      addCell(tr, money(row.ad_spend), 'num');
      addCell(tr, money(row.payment_amount), 'num');
      addCell(tr, ratio(overallRoi(row)), 'num');
      addCell(tr, ratio(row.ad_roi), 'num');
      const action = document.createElement('td');
      const button = element('button', 'button button--ghost', '明细');
      button.type = 'button';
      button.dataset.promotionDrill = productId(row);
      button.addEventListener('click', () => openProductDrawer(row, button));
      action.appendChild(button);
      tr.appendChild(action);
      body.appendChild(tr);
    });
  }

  function renderAggregate(type) {
    const data = aggregate(type);
    addHeaders(['口径', '推广花费', '推算归因成交', '加权 ROI', '加权 PPC', '覆盖商品']);
    const body = $('[data-promotion-body]');
    body.replaceChildren();
    const row = document.createElement('tr');
    addCell(row, data.label);
    addCell(row, money(data.spend), 'num');
    addCell(row, money(data.attributedGmv), 'num');
    addCell(row, ratio(data.roi), 'num');
    addCell(row, money(data.ppc), 'num');
    addCell(row, number(data.sourceCount), 'num');
    body.appendChild(row);
  }

  function renderUnavailable() {
    addHeaders(['可用性说明']);
    const body = $('[data-promotion-body]');
    body.replaceChildren();
    const row = document.createElement('tr');
    const cell = row.insertCell();
    cell.colSpan = 1;
    const empty = element('div', 'empty-state');
    empty.append(element('strong', '', '当前数据库未提供计划、创意、地域或内容归因'), element('span', '', '页面不会用商品或渠道数据伪造这些层级。导入对应明细后再开放相关分析。'));
    cell.appendChild(empty);
    body.appendChild(row);
  }

  function renderActiveTable() {
    const definitions = {
      products: ['商品推广表现', '商品级月度记录。可打开商品明细，数据可与商品运营页交叉核对。'],
      keywords: ['关键词汇总', '关键词字段仅以商品级月度汇总提供；归因成交按花费乘对应商品 ROI 推算。'],
      crowd: ['人群汇总', '人群字段仅以商品级月度汇总提供；归因成交按花费乘对应商品 ROI 推算。'],
      site: ['站内渠道汇总', '站内渠道字段仅以商品级月度汇总提供；归因成交按花费乘对应商品 ROI 推算。'],
      unavailable: ['未提供归因', '该数据源暂未提供计划、创意、地域、内容层级的可验证关联。']
    };
    const [title, hint] = definitions[state.activeTab];
    $('[data-promotion-table-title]').textContent = title;
    $('[data-promotion-table-hint]').textContent = hint;
    $('[data-promotion-grain]').textContent = hint;
    const count = state.activeTab === 'products' ? state.rows.length : state.activeTab === 'unavailable' ? 0 : aggregate(state.activeTab).sourceCount;
    $('[data-promotion-row-count]').textContent = state.activeTab === 'unavailable' ? '不可用' : `${number(count)} 个商品`;
    if (state.activeTab === 'products') renderProducts();
    else if (state.activeTab === 'unavailable') renderUnavailable();
    else renderAggregate(state.activeTab);
  }

  function renderDrilldown(rows, level) {
    const labels = {channel:'渠道', campaign:'计划', unit:'单元', product:'商品'};
    $('[data-promotion-table-title]').textContent = `${labels[level]}下钻`;
    $('[data-promotion-table-hint]').textContent = '只展示已导入的同粒度推广事实；ROI、CTR 均按汇总后计算。';
    $('[data-promotion-grain]').textContent = $('[data-promotion-table-hint]').textContent;
    addHeaders([labels[level], '推广花费', '推广成交', '直接成交', '间接成交', '付费占比', 'ROI', 'CTR', 'CVR', 'CPC']);
    const body = $('[data-promotion-body]'); body.replaceChildren();
    if (!rows.length) return clearTable('该筛选范围未导入对应粒度推广数据');
    rows.forEach((row) => { const tr = document.createElement('tr'); const identifier = level === 'channel' ? row.channel : level === 'campaign' ? `${row.channel} / ${row.campaign_id}` : level === 'unit' ? `${row.channel} / ${row.campaign_id} / ${row.unit_id}` : `${row.channel} / ${row.product_id}`; const values = [identifier, money(row.ad_spend), money(row.attributed_payment_amount), money(row.direct_payment_amount), money(row.indirect_payment_amount), row.paid_share == null ? '--' : `${(row.paid_share * 100).toFixed(2)}%`, ratio(row.roi), row.ctr == null ? '--' : `${(row.ctr * 100).toFixed(2)}%`, row.cvr == null ? '--' : `${(row.cvr * 100).toFixed(2)}%`, row.cpc == null ? '--' : money(row.cpc)]; values.forEach((value, index) => { const cell = addCell(tr, value, index ? 'num' : ''); if (level === 'product' && index === 0) { cell.tabIndex = 0; cell.role = 'link'; cell.title = '打开商品详情'; cell.addEventListener('click', () => { const range = window.TmallDateRange?.getState?.() || {}; const query = new URLSearchParams({start: range.startDate || '', end: range.endDate || '', source: 'promotion'}); location.href = `/products/${encodeURIComponent(row.product_id)}?${query}`; }); }}); body.appendChild(tr); });
  }
  async function loadDrilldown() {
    const level = $('[data-promotion-drill-level]').value; const range = window.TmallDateRange?.getState?.() || {};
    const query = new URLSearchParams({start:range.startDate || `${state.period}-01`, end:range.endDate || `${state.period}-31`, group_by:level});
    [['channel','[data-promotion-channel]'],['campaign_id','[data-promotion-campaign]'],['unit_id','[data-promotion-unit]']].forEach(([key, selector]) => { const value = $(selector).value.trim(); if (value) query.set(key, value); });
    try { const response = await DemoApi.domainRequest(`/api/promotion?${query}`); renderDrilldown(response.data.rows, level); } catch(error) { clearTable(error.message || '推广下钻加载失败'); }
  }

  function metric(label, value) {
    const item = element('div', 'drawer-metric');
    item.append(element('span', '', label), element('strong', '', value));
    return item;
  }

  function openInfoDrawer(trigger) {
    $('[data-promotion-drawer-title]').textContent = '数据口径说明';
    $('[data-promotion-drawer-subtitle]').textContent = `${state.period || '--'} 月度数据`;
    const body = $('[data-promotion-drawer-body]');
    body.replaceChildren();
    const intro = element('section', 'plain-panel panel');
    intro.append(element('h3', 'panel__title', '如何使用本页数据'), element('p', 'panel__hint', '总览与趋势按商品级推广记录汇总。关键词、人群、站内渠道为同一商品记录上的不同投放字段，不能与总览相加。'));
    const list = element('div', 'status-list');
    [['商品表现', '可查看单商品推广花费、成交与 ROI。'], ['关键词 / 人群 / 站内渠道', '只展示已有月度聚合字段，不宣称词、计划或人群包级归因。'], ['未提供归因', '计划、创意、地域和内容数据未入库，因此保持不可用状态。']].forEach(([label, value]) => {
      const row = element('div', 'status-list__item');
      row.append(element('span', 'status-list__label', label), element('span', 'status-list__value', value));
      list.appendChild(row);
    });
    body.append(intro, list);
    openDrawer(trigger);
  }

  function openProductDrawer(row, trigger) {
    const product = state.rows.find((item) => productId(item) === productId(row)) || row;
    $('[data-promotion-drawer-title]').textContent = text(product.title, '推广商品详情');
    $('[data-promotion-drawer-subtitle]').textContent = `商品 ID：${productId(product)} · ${state.period}`;
    const body = $('[data-promotion-drawer-body]');
    body.replaceChildren();
    const summary = element('div', 'drawer-metrics');
    summary.append(metric('推广花费', money(product.ad_spend)), metric('成交金额', money(product.payment_amount)), metric('整体 ROI', ratio(overallRoi(product))), metric('推广 ROI', ratio(product.ad_roi)), metric('关键词花费', money(product.keyword_spend)), metric('人群花费', money(product.crowd_spend)), metric('站内渠道花费', money(product.site_spend)), metric('退款支付占比', `${(Number(product.refund_paid_ratio || 0) * 100).toFixed(2)}%`));
    const source = element('section', 'plain-panel panel');
    source.append(element('h3', 'panel__title', '口径与关联'), element('p', 'panel__hint', '该抽屉只展示当前商品同一月份的数据库字段。关键词、人群与站内渠道均是该商品下的聚合指标。'));
    body.append(summary, source);
    openDrawer(trigger);
  }

  function visibleFocusables() {
    const drawer = $('[data-promotion-drawer]');
    return Array.from(drawer.querySelectorAll(focusableSelector)).filter((item) => {
      const rect = item.getBoundingClientRect();
      const style = window.getComputedStyle(item);
      return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0;
    });
  }

  function openDrawer(trigger) {
    const drawer = $('[data-promotion-drawer]');
    const backdrop = $('[data-promotion-backdrop]');
    state.drawerReturnFocus = trigger || document.activeElement;
    drawer.removeAttribute('inert');
    drawer.setAttribute('aria-hidden', 'false');
    drawer.classList.add('is-open');
    backdrop.classList.add('is-open');
    document.body.classList.add('demo-scroll-lock');
    window.setTimeout(() => (visibleFocusables()[0] || drawer).focus(), 0);
    window.lucide?.createIcons();
  }

  function closeDrawer() {
    const drawer = $('[data-promotion-drawer]');
    if (!drawer.classList.contains('is-open')) return;
    drawer.classList.remove('is-open');
    $('[data-promotion-backdrop]').classList.remove('is-open');
    drawer.setAttribute('aria-hidden', 'true');
    drawer.setAttribute('inert', '');
    document.body.classList.remove('demo-scroll-lock');
    state.drawerReturnFocus?.focus?.();
    state.drawerReturnFocus = null;
  }

  function bindDrawer() {
    const drawer = $('[data-promotion-drawer]');
    $('[data-promotion-drawer-close]').addEventListener('click', closeDrawer);
    $('[data-promotion-backdrop]').addEventListener('click', closeDrawer);
    drawer.addEventListener('keydown', (event) => {
      if (event.key === 'Escape') { event.preventDefault(); closeDrawer(); return; }
      if (event.key !== 'Tab') return;
      const items = visibleFocusables();
      if (!items.length) { event.preventDefault(); drawer.focus(); return; }
      const first = items[0];
      const last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    });
    document.addEventListener('keydown', (event) => { if (event.key === 'Escape') closeDrawer(); });
  }

  function selectTab(tab) {
    state.activeTab = tab;
    document.querySelectorAll('[data-promotion-tab]').forEach((button) => {
      const active = button.dataset.promotionTab === tab;
      button.setAttribute('aria-selected', String(active));
      button.setAttribute('aria-pressed', String(active));
    });
    renderActiveTable();
  }

  async function load(detail) {
    const token = ++state.token;
    state.period = getPeriod(detail);
    $('[data-promotion-period]').textContent = `${state.period} 商品推广趋势`;
    clearTable('加载推广数据中');
    renderKpis([]);
    renderAlerts([]);
    destroyChart();
    setStatus('推广数据加载中');
    try {
      const [performance, alerts, trend] = await Promise.all([
        DemoApi.request(requestPath('/api/ad_performance')),
        DemoApi.request(requestPath('/api/ad_alerts')),
        DemoApi.request(`${requestPath('/api/ad_trend')}&count=6`),
      ]);
      if (token !== state.token) return;
      state.rows = Array.isArray(performance) ? performance : [];
      state.alerts = Array.isArray(alerts) ? alerts : [];
      renderKpis(state.rows);
      renderTrend(Array.isArray(trend) ? trend : []);
      renderAlerts(state.alerts);
      renderActiveTable();
      setStatus(`已加载 ${state.period} 推广数据`);
      window.lucide?.createIcons();
    } catch (error) {
      if (token !== state.token) return;
      state.rows = [];
      state.alerts = [];
      destroyChart();
      renderKpis([]);
      renderAlerts([]);
      clearTable('推广数据加载失败');
      setStatus(error.message || '推广数据加载失败');
      toast('推广数据加载失败');
    }
  }

  $('[data-promotion-tabs]').addEventListener('click', (event) => {
    const button = event.target.closest('[data-promotion-tab]');
    if (button) selectTab(button.dataset.promotionTab);
  });
  $('[data-promotion-info]').addEventListener('click', (event) => openInfoDrawer(event.currentTarget));
  $('[data-promotion-refresh]').addEventListener('click', () => load());
  $('[data-promotion-drill-load]')?.addEventListener('click', loadDrilldown);
  bindDrawer();
  window.addEventListener('tmall:date-range-change', (event) => load(event.detail));
  window.addEventListener('tmall:refresh', () => load());
  if (!window.TmallDateRange) load();
})();
