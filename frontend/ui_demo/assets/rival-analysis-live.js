(async function () {
  'use strict';
  const escapeHtml = window.DemoFormat?.escapeHtml
    ? window.DemoFormat.escapeHtml
    : (v) => String(v ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);

  const API_BASE = '/api/sycm';

  const state = {
    summary: null,
    shops: [],
    filteredShops: [],
    items: [],
    excludedOwnItemCount: 0,
    shopTrend: null,
    itemTrend: null,
    shopEntities: [],
    itemEntities: [],
    shopEntityTrend: null,
    itemEntityTrend: null,
    activeTab: 'shops',
    dmp: { loaded: false, loading: false, summary: null, rivals: null, ad: null, shop: null },
    sortKey: 'uv',
    sortDir: 'desc',
    filterType: '',
    searchText: '',
  };
  let interactionsBound = false;

  function $(sel) { return document.querySelector(sel); }
  function $$(sel) { return Array.from(document.querySelectorAll(sel)); }

  const chartInstances = new Set();
  function syncChartTheme(chart) {
    if (!chart) return;
    const styles = getComputedStyle(document.documentElement);
    const textColor = styles.getPropertyValue('--text-secondary').trim() || '#64748b';
    const primaryColor = styles.getPropertyValue('--text-primary').trim() || '#111827';
    const borderColor = styles.getPropertyValue('--border-default').trim() || '#d1d5db';
    const option = chart.getOption ? chart.getOption() : {};
    const axes = (value) => (Array.isArray(value) ? value : value ? [value] : []).map((axis) => ({
      ...axis,
      axisLabel: { ...(axis.axisLabel || {}), color: textColor },
      axisLine: { ...(axis.axisLine || {}), lineStyle: { ...(axis.axisLine?.lineStyle || {}), color: borderColor } },
      splitLine: { ...(axis.splitLine || {}), lineStyle: { ...(axis.splitLine?.lineStyle || {}), color: borderColor } },
    }));
    const themed = { textStyle: { color: textColor }, tooltip: { backgroundColor: styles.getPropertyValue('--surface-base').trim(), borderColor, textStyle: { color: primaryColor } } };
    if (option.legend) themed.legend = (Array.isArray(option.legend) ? option.legend : [option.legend]).map((legend) => ({ ...legend, textStyle: { ...(legend.textStyle || {}), color: textColor } }));
    if (option.xAxis) themed.xAxis = axes(option.xAxis);
    if (option.yAxis) themed.yAxis = axes(option.yAxis);
    chart.setOption(themed);
  }
  function registerChart(chart) { if (chart) { chartInstances.add(chart); syncChartTheme(chart); } return chart; }
  new MutationObserver(() => chartInstances.forEach(syncChartTheme)).observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });

  function fmtInt(v) {
    if (v == null || isNaN(v)) return '--';
    return Number(v).toLocaleString('zh-CN');
  }
  const fmtWan = window.DemoFormat?.fmtWan || ((v) => v == null || isNaN(v) ? '--' : String(Number(v)));
  const fmtPct1 = window.DemoFormat?.fmtPct1 || ((v) => v == null || isNaN(v) ? '--' : ((Number(v) * 100).toFixed(1) + '%'));
  // 竞店/竞品字段来自外部抓取，仅接受 http(s) 链接，防止属性逃逸与 javascript: URL。
  function safeHttpUrl(value) {
    let url = String(value || '').trim();
    if (!url) return '';
    if (url.startsWith('//')) url = 'https:' + url;
    return /^https?:\/\//i.test(url) ? url : '';
  }

  // 加载数据
  async function loadSummary(date) {
    const query = date ? `?date=${encodeURIComponent(date)}` : '';
    const r = await fetch(API_BASE + '/rival-shops/summary' + query);
    const d = await r.json();
    if (!d.ok) throw new Error(d.message || '加载失败');
    state.summary = d.data;
    return d.data;
  }

  async function loadShops(date) {
    const query = date ? `?date=${encodeURIComponent(date)}` : '';
    const r = await fetch(API_BASE + '/rival-shops/list' + query);
    const d = await r.json();
    if (!d.ok) throw new Error(d.message || '加载失败');
    state.shops = d.data.shops;
    state.filteredShops = [...d.data.shops];
    return d.data.shops;
  }

  async function loadItems(date) {
    const query = date ? `?date=${encodeURIComponent(date)}` : '';
    const r = await fetch(API_BASE + '/rival-items/list' + query);
    const d = await r.json();
    if (!d.ok) throw new Error(d.message || '加载失败');
    state.items = d.data.items;
    state.excludedOwnItemCount = Number(d.data.excluded_own_count || 0);
    return d.data.items;
  }

  async function loadTrend(startDate, endDate) {
    const query = new URLSearchParams();
    if (startDate) query.set('start', startDate);
    if (endDate) query.set('end', endDate);
    const suffix = query.toString() ? `?${query.toString()}` : '';
    const [shopRes, itemRes, shopEntitiesRes, itemEntitiesRes] = await Promise.all([
      fetch(`${API_BASE}/rival-shops/trend${suffix}`),
      fetch(`${API_BASE}/rival-items/trend${suffix}`),
      fetch(`${API_BASE}/rival-shops/entities${suffix}`),
      fetch(`${API_BASE}/rival-items/entities${suffix}`),
    ]);
    const [shopJson, itemJson, shopEntitiesJson, itemEntitiesJson] = await Promise.all([
      shopRes.json(), itemRes.json(), shopEntitiesRes.json(), itemEntitiesRes.json(),
    ]);
    state.shopTrend = shopJson.ok ? shopJson.data : null;
    state.itemTrend = itemJson.ok ? itemJson.data : null;
    state.shopEntities = shopEntitiesJson.ok ? shopEntitiesJson.data.entities : [];
    state.itemEntities = itemEntitiesJson.ok ? itemEntitiesJson.data.entities : [];
  }

  function fillEntitySelect(selector, entities, selectedId, placeholder) {
    const select = $(selector);
    if (!select) return '';
    const ranked = [...entities].sort((a, b) => Number(b.observed_days || 0) - Number(a.observed_days || 0)
      || String(b.last_seen || '').localeCompare(String(a.last_seen || ''))
      || String(a.entity_name || '').localeCompare(String(b.entity_name || ''), 'zh-CN'));
    const options = ranked.map(entity => `<option value="${escapeHtml(entity.entity_id)}">${escapeHtml(entity.entity_name || entity.entity_id)} · ${entity.observed_days}天</option>`).join('');
    select.innerHTML = `<option value="">${escapeHtml(placeholder)}</option>${options}`;
    const selected = ranked.find(entity => String(entity.entity_id) === String(selectedId));
    const bestCoverage = Number(ranked[0]?.observed_days || 0);
    const next = selected && Number(selected.observed_days || 0) >= bestCoverage
      ? String(selected.entity_id)
      : String(ranked[0]?.entity_id || '');
    select.value = next;
    return next;
  }

  async function loadEntityTrend(kind, entityId) {
    const isShop = kind === 'shop';
    const range = window.TmallDateRange?.getState?.() || {};
    const query = new URLSearchParams({ [isShop ? 'shop_id' : 'item_id']: entityId });
    if (range.startDate) query.set('start', range.startDate);
    if (range.endDate) query.set('end', range.endDate);
    const response = await fetch(`${API_BASE}/${isShop ? 'rival-shops' : 'rival-items'}/entity-trend?${query}`);
    const result = await response.json();
    if (!result.ok) throw new Error(result.message || '加载单体趋势失败');
    if (isShop) state.shopEntityTrend = result.data;
    else state.itemEntityTrend = result.data;
    renderEntityTrend(kind, result.data);
  }

  function dateSequence(start, end) {
    if (!start || !end) return [];
    const from = new Date(`${start}T00:00:00`);
    const to = new Date(`${end}T00:00:00`);
    const dates = [];
    for (const cursor = new Date(from); cursor <= to; cursor.setDate(cursor.getDate() + 1)) {
      dates.push(`${cursor.getFullYear()}-${String(cursor.getMonth() + 1).padStart(2, '0')}-${String(cursor.getDate()).padStart(2, '0')}`);
    }
    return dates;
  }

  function renderEntityTrend(kind, trend) {
    const isShop = kind === 'shop';
    const chartNode = document.getElementById(isShop ? 'rivalShopDetailChart' : 'rivalItemDetailChart');
    const tbody = $(`[data-rival-${kind}-detail-body]`);
    const dates = dateSequence(trend.start_date, trend.end_date);
    const dailyByDate = new Map(trend.daily.map(row => [row.stat_date, row]));
    const rows = dates.map(date => dailyByDate.get(date) || null);
    const observed = rows.filter(Boolean).length;
    const missing = dates.length - observed;
    const notice = isShop ? $('[data-rival-trend-notice]') : $('[data-rival-item-trend-notice]');
    if (notice) {
      notice.textContent = `${trend.entity_name || trend.entity_id}：采集 ${observed}/${dates.length} 天，覆盖 ${(trend.coverage_rate * 100).toFixed(0)}%${missing ? `，缺失 ${missing} 天` : ''}。折线空点表示当天未采到，不代表 0。`;
    }
    const firstObserved = rows.findIndex(Boolean);
    const lastObserved = firstObserved >= 0 ? rows.length - 1 - [...rows].reverse().findIndex(Boolean) : -1;
    const chartRows = firstObserved >= 0 ? rows.slice(firstObserved, lastObserved + 1) : [];
    const chartDates = firstObserved >= 0 ? dates.slice(firstObserved, lastObserved + 1) : [];
    const chartSeries = field => chartRows.map(row => row && row[field] != null ? Number(row[field]) : null);
    if (chartNode && typeof echarts !== 'undefined') {
      const chart = echarts.getInstanceByDom(chartNode) || echarts.init(chartNode);
      chart.resize();
      chart.setOption({
        tooltip: { trigger: 'axis', valueFormatter: value => value == null ? '未采集' : fmtInt(value) },
        legend: { bottom: 0 },
        grid: { left: '5%', right: '7%', top: '8%', bottom: '18%', containLabel: true },
        xAxis: { type: 'category', data: chartDates.map(date => date.slice(5)), boundaryGap: false },
        yAxis: [
          { type: 'value', name: 'UV / 支付买家' },
          { type: 'value', name: '支付转化率', axisLabel: { formatter: value => `${value}%` } },
        ],
        series: [
          { name: 'UV', type: 'line', connectNulls: false, data: chartSeries('uv'), itemStyle: { color: '#2563eb' } },
          { name: '支付买家', type: 'line', connectNulls: false, data: chartSeries('pay_buyer_count'), itemStyle: { color: '#d97706' } },
          { name: '支付转化率', type: 'line', yAxisIndex: 1, connectNulls: false, data: chartSeries('pay_rate').map(value => value == null ? null : value * 100), itemStyle: { color: '#059669' } },
        ],
      }, true);
      registerChart(chart);
    }
    if (tbody) renderSharedTableBody(tbody, [
      { key: 'stat_date', label: '日期' },
      { key: 'uv', label: 'UV', numeric: true, render: (value, row) => row.observed ? fmtWan(value) : '--' },
      { key: 'pay_buyer_count', label: '支付买家', numeric: true, render: (value, row) => row.observed ? fmtWan(value) : '--' },
      { key: 'pay_rate', label: '支付转化率', numeric: true, className: 'pct', render: (value, row) => row.observed ? fmtPct1(value) : '--' },
      { key: 'observed', label: '采集状态', render: value => value ? '已采集' : '未采集' },
    ], dates.map((date, index) => ({ stat_date: date, ...(rows[index] || {}), observed: Boolean(rows[index]) })));
  }

  function renderSharedTableBody(body, columns, rows, emptyMessage = '暂无数据') {
    if (!body || !window.TmallUI?.table?.mount) return;
    window.TmallUI.table.mount(body, { columns, rows, emptyMessage });
  }

  function renderTableError(body, columnCount, message) {
    const columns = Array.from({ length: columnCount }, (_, index) => ({
      key: `error_${index}`,
      label: '',
      render: (_, row) => {
        if (index !== 0) return '';
        const cell = document.createElement('span');
        cell.style.color = 'var(--danger-text)';
        cell.textContent = row.message;
        return cell;
      },
    }));
    renderSharedTableBody(body, columns, [{ message }], '');
  }

  async function initEntityTrends() {
    const shopSelect = $('[data-rival-shop-select]');
    const itemSelect = $('[data-rival-item-select]');
    const shopId = fillEntitySelect('[data-rival-shop-select]', state.shopEntities, shopSelect?.value, '选择竞店');
    const itemId = fillEntitySelect('[data-rival-item-select]', state.itemEntities, itemSelect?.value, '选择竞品单品');
    if (shopId) await loadEntityTrend('shop', shopId);
    if (itemId) await loadEntityTrend('item', itemId);
  }

  function bindEntitySelectors() {
    $('[data-rival-shop-select]')?.addEventListener('change', event => {
      if (event.target.value) loadEntityTrend('shop', event.target.value).catch(error => console.error(error));
    });
    $('[data-rival-item-select]')?.addEventListener('change', event => {
      if (event.target.value) loadEntityTrend('item', event.target.value).catch(error => console.error(error));
    });
  }

  // 渲染指标卡片
  function renderMetrics() {
    const s = state.summary;
    $('[data-rival-date]').textContent = `统计日 ${s.stat_date} · 单日观察`;
    const context = $('[data-rival-context]');
    const range = window.TmallDateRange?.getState?.() || {};
    if (context) context.textContent = range.startDate && range.endDate
      ? `${range.startDate} ~ ${range.endDate} · 统计日 ${s.stat_date}`
      : `统计日 ${s.stat_date}`;
    $('[data-rival-total]').textContent = fmtInt(s.total_shops);
    $('[data-rival-avg-uv]').textContent = fmtWan(s.avg_uv);
    $('[data-rival-avg-buyers]').textContent = fmtWan(s.avg_pay_buyers);
    $('[data-rival-avg-rate]').textContent = fmtPct1(s.avg_pay_rate);
  }

  function renderCommandSummary() {
    const leading = $('[data-rival-leading]');
    const efficiency = $('[data-rival-efficiency]');
    const opportunity = $('[data-rival-opportunity]');
    if (!leading || !efficiency || !opportunity) return;
    const shops = state.shops || [];
    const topUv = [...shops].sort((a, b) => (b.uv || 0) - (a.uv || 0))[0];
    const topRate = [...shops].sort((a, b) => (b.pay_rate || 0) - (a.pay_rate || 0))[0];
    const trend = state.shopTrend;
    const coverage = trend ? `${trend.observed_days}/${trend.expected_days || '--'} 天，覆盖率 ${((trend.coverage_rate || 0) * 100).toFixed(0)}%` : '暂无周期数据';
    leading.textContent = topUv ? `${topUv.shop_name}当前统计日访客最多（${fmtWan(topUv.uv)}）；周期覆盖 ${coverage}。` : '暂无可判断的竞店数据。';
    efficiency.textContent = topRate ? `当前统计日 ${topRate.shop_name}支付转化率最高（${fmtPct1(topRate.pay_rate)}）；${trend?.trend_comparable ? '可结合周期日均复核。' : '覆盖不足，暂不下趋势结论。'}` : '暂无足够数据判断竞店效率。';
    opportunity.textContent = trend?.trend_comparable
      ? '周期数据可用于筛选持续增长竞店；仍需补充价格、SKU、商品变更和流量来源后再决定跟进动作。'
      : '当前先定位复查对象；周期覆盖不足，不输出增长、跟价或复制打法结论。';
  }

  function renderTrendNotice() {
    const existing = document.querySelector('[data-rival-trend-notice]');
    if (!existing) return;
    const trend = state.shopTrend;
    if (!trend) {
      existing.textContent = '暂无所选范围的竞店趋势数据。';
      return;
    }
    existing.textContent = `周期覆盖 ${trend.observed_days}/${trend.expected_days || '--'} 天，竞店日均 UV ${fmtWan(trend.totals.avg_uv_per_day)}，日均支付买家 ${fmtWan(trend.totals.avg_pay_buyers_per_day)}；${trend.trend_comparable ? '可用于趋势观察。' : '覆盖不足，不能用于增长结论。'}`;
    const itemNotice = document.querySelector('[data-rival-item-trend-notice]');
    if (itemNotice) {
      const itemTrend = state.itemTrend;
      itemNotice.textContent = itemTrend
        ? `竞品样本覆盖 ${itemTrend.observed_days}/${itemTrend.expected_days || '--'} 天；${itemTrend.trend_comparable ? '可观察样本效率变化，不能单独解释增长原因。' : '覆盖不足，不输出竞品增长结论。'}`
        : '暂无所选范围的竞品趋势数据。';
    }
  }

  function renderPeriodCharts() {
    if (!state.shopTrend?.daily?.length || typeof echarts === 'undefined') return;
    const labels = state.shopTrend.daily.map(row => row.stat_date.slice(5));
    const buyers = state.shopTrend.daily.map(row => row.pay_buyer_count || 0);
    const itemDaily = state.itemTrend?.daily || [];
    const rateLabels = itemDaily.map(row => row.stat_date.slice(5));
    const rates = itemDaily.map(row => row.pay_rate == null ? null : Number(row.pay_rate) * 100);
    const buyerNode = document.getElementById('rivalPeriodBuyerChart');
    const rateNode = document.getElementById('rivalPeriodRateChart');
    if (buyerNode) {
      const chart = echarts.init(buyerNode);
      chart.setOption({
        tooltip: { trigger: 'axis' },
        grid: { left: '4%', right: '4%', bottom: '12%', containLabel: true },
        xAxis: { type: 'category', data: labels },
        yAxis: { type: 'value', axisLabel: { formatter: v => v >= 10000 ? `${(v / 10000).toFixed(1)}万` : v } },
        series: [{ type: 'line', smooth: true, data: buyers, itemStyle: { color: '#2563eb' }, areaStyle: { opacity: 0.08 } }],
      });
      registerChart(chart);
    }
    if (rateNode) {
      const chart = echarts.init(rateNode);
      chart.setOption({
        tooltip: { trigger: 'axis', valueFormatter: value => value == null ? '--' : `${Number(value).toFixed(2)}%` },
        grid: { left: '4%', right: '4%', bottom: '12%', containLabel: true },
        xAxis: { type: 'category', data: rateLabels.length ? rateLabels : labels },
        yAxis: { type: 'value', axisLabel: { formatter: v => `${v}%` } },
        series: [{ type: 'line', smooth: true, connectNulls: false, data: rates, itemStyle: { color: '#059669' } }],
      });
      registerChart(chart);
    }
  }

  // 渲染UV柱状图
  function renderUvChart() {
    const chart = echarts.init(document.getElementById('rivalUvChart'));
    const top10 = [...state.filteredShops].sort((a, b) => (b.uv || 0) - (a.uv || 0)).slice(0, 10);
    const names = top10.map(s => s.shop_name.length > 6 ? s.shop_name.slice(0, 6) + '...' : s.shop_name);
    const data = top10.map(s => s.uv || 0);
    chart.setOption({
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
      grid: { left: '3%', right: '4%', bottom: '15%', containLabel: true },
      xAxis: { type: 'category', data: names, axisLabel: { fontSize: 10, rotate: 30 } },
      yAxis: { type: 'value', axisLabel: { formatter: function(v) { return v >= 10000 ? (v/10000).toFixed(0) + '万' : v; } } },
      series: [{
        type: 'bar',
        data: data,
        itemStyle: { color: '#3b82f6', borderRadius: [4, 4, 0, 0] },
        barWidth: '50%',
      }],
    });
    registerChart(chart);
  }

  // 渲染支付买家柱状图
  function renderBuyerChart() {
    const chart = echarts.init(document.getElementById('rivalBuyerChart'));
    const top10 = [...state.filteredShops].sort((a, b) => (b.pay_buyer_count || 0) - (a.pay_buyer_count || 0)).slice(0, 10);
    const names = top10.map(s => s.shop_name.length > 6 ? s.shop_name.slice(0, 6) + '...' : s.shop_name);
    const data = top10.map(s => s.pay_buyer_count || 0);
    chart.setOption({
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
      grid: { left: '3%', right: '4%', bottom: '15%', containLabel: true },
      xAxis: { type: 'category', data: names, axisLabel: { fontSize: 10, rotate: 30 } },
      yAxis: { type: 'value', axisLabel: { formatter: function(v) { return v >= 10000 ? (v/10000).toFixed(0) + '万' : v; } } },
      series: [{
        type: 'bar',
        data: data,
        itemStyle: { color: '#22c55e', borderRadius: [4, 4, 0, 0] },
        barWidth: '50%',
      }],
    });
    registerChart(chart);
  }

  // 筛选和排序
  function applyFilters() {
    let result = [...state.shops];

    // 类型筛选
    if (state.filterType === 'tmall') {
      result = result.filter(s => s.is_tmall);
    } else if (state.filterType === 'taobao') {
      result = result.filter(s => !s.is_tmall);
    }

    // 搜索筛选
    if (state.searchText) {
      const q = state.searchText.toLowerCase();
      result = result.filter(s => s.shop_name.toLowerCase().includes(q));
    }

    // 排序
    result.sort((a, b) => {
      let va = a[state.sortKey] || 0;
      let vb = b[state.sortKey] || 0;
      if (typeof va === 'string') va = va.toLowerCase();
      if (typeof vb === 'string') vb = vb.toLowerCase();
      if (va < vb) return state.sortDir === 'asc' ? -1 : 1;
      if (va > vb) return state.sortDir === 'asc' ? 1 : -1;
      return 0;
    });

    state.filteredShops = result;
    return result;
  }

  // 渲染竞店表格
  function renderShopsTable() {
    const shops = applyFilters();
    const tbody = $('[data-rival-shops-body]');
    const filteredCount = $('[data-rival-filtered-count]');
    if (filteredCount) filteredCount.textContent = shops.length;

    const badge = (shop) => {
      const node = document.createElement('span');
      node.className = `rival-badge ${shop.is_tmall ? 'rival-badge--tmall' : 'rival-badge--taobao'}`;
      node.textContent = shop.is_tmall ? '天猫' : '淘宝';
      return node;
    };
    const name = (value) => {
      const node = document.createElement('strong');
      node.textContent = value || '--';
      return node;
    };
    const renderBody = (body, columns, rows, emptyMessage) => {
      if (!body || !window.TmallUI?.table?.mount) return;
      window.TmallUI.table.mount(body, { columns, rows, emptyMessage });
    };
    renderBody(tbody, [
      { key: 'rank', label: '排名', numeric: true },
      { key: 'shop_name', label: '店铺', render: name },
      { key: 'is_tmall', label: '类型', render: (_, shop) => badge(shop) },
      { key: 'uv', label: '访客数', numeric: true, render: fmtWan },
      { key: 'pay_buyer_count', label: '支付买家', numeric: true, render: fmtWan },
      { key: 'pay_rate', label: '支付转化率', numeric: true, className: 'pct', render: fmtPct1 },
      { key: 'cart_buyer_count', label: '加购人数', numeric: true, render: fmtWan },
      { key: 'collect_buyer_count', label: '收藏人数', numeric: true, render: fmtWan },
    ], shops.map((shop, index) => ({ ...shop, rank: index + 1 })), '暂无符合条件的竞店');

    // 更新排序图标
    $$('[data-sort]').forEach(th => {
      th.classList.remove('sort-asc', 'sort-desc');
      if (th.dataset.sort === state.sortKey) {
        th.classList.add(state.sortDir === 'asc' ? 'sort-asc' : 'sort-desc');
      }
    });
  }

  // 渲染竞品列表
  function renderItemsList() {
    const container = $('[data-rival-items-list]');
    if (!state.items.length) {
      const message = state.excludedOwnItemCount
        ? `已排除 ${state.excludedOwnItemCount} 个自家商品；当前日期的推荐竞品数据里没有外部商品。`
        : '当前日期暂无外部竞品商品数据。';
      DemoApi.renderDataState(container, 'no-data', { message });
      return;
    }

    const html = state.items.map(item => {
      const picUrl = safeHttpUrl(item.pic_url);
      const img = picUrl
        ? `<img loading="lazy" src="${escapeHtml(picUrl)}" alt="" onerror="this.style.display='none'">`
        : '';
      const detailUrl = safeHttpUrl(item.detail_url);
      return `<div class="rival-item-card">
        <div class="rival-item-img">${img}</div>
        <div class="rival-item-info">
          <div class="rival-item-title">${escapeHtml(item.title || '-')}</div>
          <div class="rival-item-meta">
            ${item.shop_name ? `<span>店铺: ${escapeHtml(item.shop_name)}</span>` : ''}
            <span>访客: ${fmtWan(item.uv)}</span>
            <span>支付买家: ${fmtWan(item.pay_buyer_count)}</span>
            ${detailUrl ? `<a href="${escapeHtml(detailUrl)}" target="_blank" rel="noopener noreferrer" style="color:var(--brand-text)">查看详情</a>` : ''}
          </div>
        </div>
      </div>`;
    }).join('');
    container.innerHTML = html;
  }

  // ---- 达摩盘竞争视角（数据源：达摩盘-竞争分析，双窗口快照，与上方单日观察口径不同） ----
  function dmpBucket(share) {
    const v = share && share.controlRatio;
    return v ? String(v) : '--';
  }

  function renderDmp() {
    const s = state.dmp;
    const hint = $('[data-dmp-window]');
    if (s.summary && s.summary.available) {
      hint.textContent = `竞争窗口 ${s.summary.end_date} vs ${s.summary.peer_end_date}（达摩盘双窗口快照，T-1/T-2 收口）。`;
      $('[data-dmp-kpi="monitored"]').textContent = fmtInt(s.summary.monitored_cnt);
      $('[data-dmp-kpi="day-cost"]').textContent = fmtWan(s.summary.own_day_cost);
      $('[data-dmp-kpi="detected"]').textContent = fmtInt(s.summary.detected_cnt);
      $('[data-dmp-kpi="window"]').textContent = `${s.summary.end_date} vs ${s.summary.peer_end_date}`;
    } else {
      hint.textContent = '暂无竞争分析数据——请先运行 dmp_competition 源采集。';
    }
    if (s.summary && s.summary.top_detected) {
      $('[data-dmp-detect-hint]').textContent =
        `竞对探测最高分：${s.summary.top_detected.name}（竞争分 ${fmtPct1(s.summary.top_detected.score)}）。` +
        '完整候选列表见 /api/dmp/competition/detection。';
    }

    const tbody = $('[data-dmp-rivals-body]');
    if (!tbody) return;
    renderSharedTableBody(tbody, [
      { key: 'index', label: '排名', numeric: true },
      { key: 'competitor_name', label: '竞对店铺', render: (value, row) => {
        const cell = document.createElement('span');
        cell.textContent = `${value || '--'}${row.attention_status ? '' : '（未关注）'}`;
        if (!row.attention_status) cell.style.color = 'var(--text-secondary)';
        return cell;
      } },
      { key: 'intersection_click_uv', label: '人群争夺交集UV', numeric: true, render: value => value == null ? '--' : fmtWan(value) },
      { key: 'intersection_rate', label: '交集环比', numeric: true, className: 'pct', render: fmtPct1 },
      { key: 'day_cost', label: '我方日消耗', numeric: true, render: value => value == null ? '--' : fmtWan(value) },
      { key: 'day_cost_rate', label: '消耗环比', numeric: true, className: 'pct', render: fmtPct1 },
      { key: 'alipay_share', label: '支付份额变化', numeric: true, className: 'pct', render: dmpBucket },
      { key: 'ipv_share', label: 'IPV份额变化', numeric: true, className: 'pct', render: dmpBucket },
      { key: 'cart_share', label: '加购份额变化', numeric: true, className: 'pct', render: dmpBucket },
    ], (s.rivals || []).map((row, index) => ({ ...row, index: index + 1 })), '暂无竞对监控数据（需先在达摩盘建立竞对监控）');
  }

  function renderDmpAd(items) {
    const box = $('[data-dmp-ad-list]');
    if (!box) return;
    if (!items || !items.length) {
      DemoApi.renderDataState(box, 'no-data', { message: '暂无投放借鉴数据（需先跑 dmp_shop 源取得 TOP 单品）' });
      return;
    }
    box.innerHTML = items.map((it) => {
      const meta = [
        it.similarity_score != null ? `相似度 ${it.similarity_score}` : '',
        it.cate_name || '',
        it.price_scope ? `价格带 ${it.price_scope}` : '',
        it.wj_amt_scope || '',
      ].filter(Boolean).join(' · ');
      const lessons = (it.lessons || []).map((l) => {
        const ch = (l.channels || []).map(c => `${escapeHtml(c.name || '')}${c.rate != null ? Math.round(c.rate * 100) + '%' : ''}`).filter(Boolean).join('/');
        const crowds = (l.crowds || []).slice(0, 3).map(c => c.replace(/^自定义竞争店铺：/, '竞店:').replace(/^达摩盘平台精选：/, '精选:')).join('、');
        const kws = (l.keywords || []).slice(0, 5).join('/');
        const parts = [];
        if (ch) parts.push(`渠道 ${ch}`);
        if (l.campaign) parts.push(`计划 ${escapeHtml(l.campaign)}`);
        if (crowds) parts.push(`圈人 ${escapeHtml(crowds)}`);
        if (kws) parts.push(`词 ${escapeHtml(kws)}`);
        if (l.roi || l.click) parts.push(`簇均 ROI ${l.roi || '--'} / 点击 ${l.click || '--'}`);
        return `<li style="margin:2px 0">${parts.join(' · ')}</li>`;
      }).join('');
      return `<div style="border:1px solid var(--border-default);border-radius:var(--radius-sm);padding:10px 12px;margin-bottom:var(--space-3)">
        <div style="font-weight:600;margin-bottom:4px">${escapeHtml(it.item_title || it.item_id)}</div>
        <div style="font-size:var(--font-size-meta);color:var(--text-secondary);margin-bottom:6px">${escapeHtml(meta)}</div>
        <ul style="margin:0;padding-left:18px;font-size:var(--font-size-meta)">${lessons || '<li>无策略簇</li>'}</ul>
      </div>`;
    }).join('');
  }

  // ---- 达摩盘全店洞察：本店 vs 同行同层（近30天窗口，同行 GMV/IPV 仅分档口径） ----
  function fmtGrowth(v) {
    if (v == null || isNaN(v)) return '--';
    return (Number(v) >= 0 ? '+' : '') + (Number(v) * 100).toFixed(1) + '%';
  }

  function renderDmpShop() {
    const s = state.dmp.shop;
    const cards = $('[data-dmp-shop-cards]');
    if (!cards) return;
    if (!s || !s.available) {
      DemoApi.renderDataState(cards, 'no-data', { message: '暂无全店洞察数据（请在采集中心运行 dmp_shop 源）' });
      const st = $('[data-dmp-shop-structure]');
      if (st) st.textContent = '';
      return;
    }
    $('[data-dmp-shop-date]').textContent = s.end_date || '--';
    $('[data-dmp-shop-period]').textContent = s.period || '30';
    const own = s.own || {};
    const peer = s.peer || {};
    const cell = (label, ownV, peerV) =>
      `<div style="flex:1;min-width:150px;border:1px solid var(--border-default);border-radius:var(--radius-sm);padding:10px 12px">
        <div style="font-size:var(--font-size-meta);color:var(--text-secondary)">${label}</div>
        <div style="font-size:20px;font-family:var(--font-mono)">${ownV}</div>
        <div style="font-size:var(--font-size-meta);color:var(--text-secondary)">同行同层 ${peerV}</div>
      </div>`;
    const struct = (o) => `爆品 ${o.hotCount ?? '--'}品/${fmtPct1(o.hotGmvContriRate)} · 新品 ${o.newCount ?? '--'}/${fmtPct1(o.newGmvContriRate)} · 成长 ${o.potentialCount ?? '--'}/${fmtPct1(o.potentialGmvContriRate)} · 平销 ${o.tailCount ?? '--'}/${fmtPct1(o.tailGmvContriRate)}`;
    cards.innerHTML = [
      cell('GMV增速', fmtGrowth(own.gmvGrowthRate), fmtGrowth(peer.gmvGrowthRate)),
      cell('支付金额', own.gmv != null ? fmtWan(own.gmv) : '--', peer.gmv != null ? fmtWan(peer.gmv) : '平台仅分档'),
      cell('支付转化率', own.paidCvr != null ? fmtPct1(own.paidCvr) : (own.generalizedPaidCvr || '--'), peer.generalizedPaidCvr || '--'),
      cell('IPV', own.ipv != null ? fmtWan(own.ipv) : '--', peer.generalizedIpv || '--'),
      cell('支付买家数', fmtInt(own.alipayCnt), fmtInt(peer.alipayCnt)),
      cell('在售商品数', fmtInt(own.itemCount), fmtInt(peer.itemCount)),
    ].join('');
    const st = $('[data-dmp-shop-structure]');
    if (st) st.textContent = `货品结构（数量/GMV占比）— 本店: ${struct(own)} ｜ 同行同层: ${struct(peer)}`;
  }

  async function loadDmp(force) {
    const dmp = state.dmp;
    if (dmp.loading || (dmp.loaded && !force)) return;
    dmp.loading = true;
    const tbody = $('[data-dmp-rivals-body]');
    try {
      const [summaryRes, rivalsRes, adRes, shopRes] = await Promise.all([
        fetch('/api/dmp/competition/summary'),
        fetch('/api/dmp/competition/rivals'),
        fetch('/api/dmp/competition/ad-strategy'),
        fetch('/api/dmp/shop/summary'),
      ]);
      const summary = await summaryRes.json();
      const rivals = await rivalsRes.json();
      const ad = await adRes.json();
      const shop = await shopRes.json();
      if (summary.ok && summary.data && summary.data.available) dmp.summary = summary.data;
      else dmp.summary = { available: false };
      dmp.rivals = (rivals.ok && rivals.data && rivals.data.available) ? rivals.data.rivals : [];
      dmp.ad = (ad.ok && ad.data && ad.data.available) ? ad.data.items : [];
      dmp.shop = (shop.ok && shop.data && shop.data.available) ? shop.data : { available: false };
      dmp.loaded = true;
      renderDmp();
      renderDmpAd(dmp.ad);
      renderDmpShop();
    } catch (err) {
      console.error('加载达摩盘竞争数据失败:', err);
      if (tbody) {
        renderTableError(tbody, 9, `加载失败: ${err.message}`);
      }
    } finally {
      dmp.loading = false;
    }
  }

  // 标签切换
  function initTabs() {
    $$('[data-rival-tab]').forEach(tab => {
      tab.addEventListener('click', () => {
        const target = tab.dataset.rivalTab;
        state.activeTab = target;

        $$('[data-rival-tab]').forEach(t => t.classList.remove('active'));
        tab.classList.add('active');

        $$('[data-rival-panel]').forEach(p => {
          p.style.display = p.dataset.rivalPanel === target ? '' : 'none';
        });

        if (target === 'shops') {
          setTimeout(() => {
            renderUvChart();
            renderBuyerChart();
            if (state.shopEntityTrend) renderEntityTrend('shop', state.shopEntityTrend);
          }, 100);
        } else if (target === 'items') {
          setTimeout(() => {
            if (state.itemEntityTrend) renderEntityTrend('item', state.itemEntityTrend);
          }, 100);
        } else if (target === 'dmp') {
          if (!state.dmp.loaded) loadDmp();
        }
      });
    });
    $$('[data-dmp-refresh]').forEach(btn => btn.addEventListener('click', () => loadDmp(true)));
    $$('[data-rival-entry]').forEach(entry => {
      entry.addEventListener('click', () => {
        const target = entry.dataset.rivalEntry;
        const tab = $(`[data-rival-tab="${target}"]`);
        tab?.click();
        $$('[data-rival-entry]').forEach(item => item.classList.toggle('is-active', item === entry));
      });
    });
  }

  // 排序和筛选事件
  function initSortAndFilter() {
    // 排序：监听稳定的表格容器，避免共享表格替换 table 节点后丢失监听器。
    const sortTable = $('[data-rival-shops-body]')?.closest('table');
    const sortRoot = sortTable?.parentElement;
    sortRoot?.addEventListener('click', (event) => {
      const th = event.target.closest?.('th[data-sort]');
      if (!th || !th.dataset.sort || !sortRoot.contains(th)) return;
      const key = th.dataset.sort;
      if (state.sortKey === key) {
        state.sortDir = state.sortDir === 'asc' ? 'desc' : 'asc';
      } else {
        state.sortKey = key;
        state.sortDir = 'desc';
      }
      renderShopsTable();
      renderUvChart();
      renderBuyerChart();
    });

    // 类型筛选
    const shopType = $('[data-rival-shop-type]');
    if (shopType) shopType.addEventListener('change', e => {
      state.filterType = e.target.value;
      renderShopsTable();
      renderUvChart();
      renderBuyerChart();
    });

    // 搜索筛选
    const shopSearch = $('[data-rival-shop-search]');
    if (shopSearch) shopSearch.addEventListener('input', e => {
      state.searchText = e.target.value;
      renderShopsTable();
      renderUvChart();
      renderBuyerChart();
    });
  }

  // F3.2：单店逐日趋势折叠。桌面默认展开（保持原信息架构不变），移动端收起
  // 把页面高度从 ~8,300px 压回 6,000px 内。展开瞬间要唤醒裸 echarts 实例
  // （初始化在收起态里拿到 0×0 容器，echarts 自己不会监听尺寸恢复）。
  const trendFold = $('[data-rival-trend-fold]');
  if (trendFold) {
    if (window.matchMedia('(min-width: 901px)').matches) trendFold.open = true;
    trendFold.addEventListener('toggle', () => {
      if (!trendFold.open) return;
      ['rivalShopDetailChart'].forEach((id) => {
        const node = document.getElementById(id);
        if (node && window.echarts?.getInstanceByDom(node)) window.echarts.getInstanceByDom(node).resize();
      });
    });
  }

  // 初始化
  async function init(detail) {
    try {
    const range = detail || window.TmallDateRange?.getState?.() || {};
      const date = range.endDate || '';
      await Promise.all([loadSummary(date), loadShops(date), loadItems(date), loadTrend(range.startDate || date, date)]);
      const rangeLabel = range.startDate && date && range.startDate !== date
        ? `当前接口按统计日展示；选择范围 ${range.startDate} ~ ${date}`
        : '单日观察，不代表周期趋势';
      const dateBadge = $('[data-rival-date]');
      if (dateBadge) dateBadge.title = rangeLabel;
      renderMetrics();
      renderCommandSummary();
      renderTrendNotice();
      renderPeriodCharts();
      renderUvChart();
      renderBuyerChart();
      renderShopsTable();
      renderItemsList();
      await initEntityTrends();
      if (!interactionsBound) {
        initTabs();
        initSortAndFilter();
        bindEntitySelectors();
        interactionsBound = true;
      }
    } catch (err) {
      console.error('加载竞店竞品数据失败:', err);
      // 4-3：表格体保持 <td> 占位语义；卡片列表这类区域状态走共享渲染器。
      document.querySelectorAll('[data-rival-shops-body]').forEach((body) => {
        renderTableError(body, 8, `加载失败: ${err.message}`);
      });
      document.querySelectorAll('[data-rival-items-list]').forEach((list) => {
        DemoApi.renderDataState(list, 'calculation-failed', { message: err.message, retry: () => window.location.reload() });
      });
    }
  }

  // 订阅样板收敛到 TmallRuntime.subscribeDateRange（runtime/date-range-scope.js）
  window.TmallRuntime?.subscribeDateRange
    ? window.TmallRuntime.subscribeDateRange((detail) => init(detail))
    : (window.addEventListener('tmall:date-range-change', (event) => init(event.detail)),
       init(window.TmallDateRange?.getState?.()));
})();
