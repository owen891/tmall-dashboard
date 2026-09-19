(async function () {
  'use strict';

  const API_BASE = '/api/sycm';

  const state = {
    summary: null,
    shops: [],
    filteredShops: [],
    items: [],
    activeTab: 'shops',
    sortKey: 'uv',
    sortDir: 'desc',
    filterType: '',
    searchText: '',
  };

  function $(sel) { return document.querySelector(sel); }
  function $$(sel) { return Array.from(document.querySelectorAll(sel)); }

  function fmtInt(v) {
    if (v == null || isNaN(v)) return '--';
    return Number(v).toLocaleString('zh-CN');
  }
  function fmtWan(v) {
    if (v == null || isNaN(v)) return '--';
    const n = Number(v);
    if (n >= 10000) return (n / 10000).toFixed(1) + '万';
    return fmtInt(n);
  }
  function fmtPct1(v) {
    if (v == null || isNaN(v)) return '--';
    return (Number(v) * 100).toFixed(1) + '%';
  }
  function escapeHtml(value) {
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }
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
    return d.data.items;
  }

  // 渲染指标卡片
  function renderMetrics() {
    const s = state.summary;
    $('[data-rival-date]').textContent = s.stat_date;
    $('[data-rival-total]').textContent = fmtInt(s.total_shops);
    $('[data-rival-avg-uv]').textContent = fmtWan(s.avg_uv);
    $('[data-rival-avg-buyers]').textContent = fmtWan(s.avg_pay_buyers);
    $('[data-rival-avg-rate]').textContent = fmtPct1(s.avg_pay_rate);
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

    if (!shops.length) {
      tbody.innerHTML = '<tr><td colspan="8" style="text-align:center;color:var(--text-tertiary);padding:24px">暂无符合条件的竞店</td></tr>';
      return;
    }

    const html = shops.map((shop, idx) => {
      const badge = shop.is_tmall
        ? '<span class="rival-badge rival-badge--tmall">天猫</span>'
        : '<span class="rival-badge rival-badge--taobao">淘宝</span>';
      const avgPrice = shop.pay_buyer_count > 0 ? (shop.uv * shop.pay_rate / shop.pay_buyer_count) * shop.pay_rate : 0;
      return `<tr>
        <td>${idx + 1}</td>
        <td><strong>${escapeHtml(shop.shop_name)}</strong></td>
        <td>${badge}</td>
        <td class="num">${fmtWan(shop.uv)}</td>
        <td class="num">${fmtWan(shop.pay_buyer_count)}</td>
        <td class="pct">${fmtPct1(shop.pay_rate)}</td>
        <td class="num">${fmtWan(shop.cart_buyer_count)}</td>
        <td class="num">${fmtWan(shop.collect_buyer_count)}</td>
      </tr>`;
    }).join('');
    tbody.innerHTML = html;

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
      container.innerHTML = '<div style="text-align:center;color:var(--text-tertiary);padding:24px">暂无数据</div>';
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
            <span>访客: ${fmtWan(item.uv)}</span>
            <span>支付买家: ${fmtWan(item.pay_buyer_count)}</span>
            ${detailUrl ? `<a href="${escapeHtml(detailUrl)}" target="_blank" rel="noopener noreferrer" style="color:var(--primary-color)">查看详情</a>` : ''}
          </div>
        </div>
      </div>`;
    }).join('');
    container.innerHTML = html;
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
          }, 100);
        }
      });
    });
  }

  // 排序和筛选事件
  function initSortAndFilter() {
    // 排序
    $$('[data-sort]').forEach(th => {
      th.addEventListener('click', () => {
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
    });
  }

  // 初始化
  async function init(detail) {
    try {
      const date = detail?.endDate || window.TmallDateRange?.getState?.().endDate || '';
      await Promise.all([loadSummary(date), loadShops(date), loadItems(date)]);
      renderMetrics();
      renderUvChart();
      renderBuyerChart();
      renderShopsTable();
      renderItemsList();
      initTabs();
      initSortAndFilter();
    } catch (err) {
      console.error('加载竞店竞品数据失败:', err);
      document.querySelectorAll('[data-rival-shops-body], [data-rival-items-list]').forEach(el => {
        el.innerHTML = `<div style="text-align:center;color:var(--text-danger);padding:24px">加载失败: ${escapeHtml(err.message)}</div>`;
      });
    }
  }

  window.addEventListener('tmall:date-range-change', (event) => init(event.detail));
  init(window.TmallDateRange?.getState?.());
})();
