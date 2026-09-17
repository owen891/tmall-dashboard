(async function () {
  'use strict';

  const API_BASE = '/api/sycm';

  const state = {
    summary: null,
    shops: [],
    items: [],
    activeTab: 'shops',
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

  // 加载数据
  async function loadSummary() {
    const r = await fetch(API_BASE + '/rival-shops/summary');
    const d = await r.json();
    if (!d.ok) throw new Error(d.message || '加载失败');
    state.summary = d.data;
    return d.data;
  }

  async function loadShops() {
    const r = await fetch(API_BASE + '/rival-shops/list');
    const d = await r.json();
    if (!d.ok) throw new Error(d.message || '加载失败');
    state.shops = d.data.shops;
    return d.data.shops;
  }

  async function loadItems() {
    const r = await fetch(API_BASE + '/rival-items/list');
    const d = await r.json();
    if (!d.ok) throw new Error(d.message || '加载失败');
    state.items = d.data.items;
    return d.data.items;
  }

  // 渲染指标卡片
  function renderMetrics(summary) {
    $('[data-rival-date]').textContent = summary.stat_date;
    $('[data-rival-total]').textContent = fmtInt(summary.total_shops);
    $('[data-rival-avg-uv]').textContent = fmtWan(summary.avg_uv);
    $('[data-rival-avg-buyers]').textContent = fmtWan(summary.avg_pay_buyers);
    $('[data-rival-avg-rate]').textContent = fmtPct1(summary.avg_pay_rate);
  }

  // 渲染UV柱状图
  function renderUvChart() {
    const chart = echarts.init(document.getElementById('rivalUvChart'));
    const top10 = state.shops.slice(0, 10);
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
    const top10 = state.shops.slice(0, 10);
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

  // 渲染竞店表格
  function renderShopsTable() {
    const tbody = $('[data-rival-shops-body]');
    if (!state.shops.length) {
      tbody.innerHTML = '<tr><td colspan="8" style="text-align:center;color:var(--text-tertiary);padding:24px">暂无数据</td></tr>';
      return;
    }

    const html = state.shops.map((shop, idx) => {
      const badge = shop.is_tmall
        ? '<span class="rival-badge rival-badge--tmall">天猫</span>'
        : '<span class="rival-badge rival-badge--taobao">淘宝</span>';
      return `<tr>
        <td>${idx + 1}</td>
        <td><strong>${shop.shop_name}</strong></td>
        <td>${badge}</td>
        <td class="num">${fmtWan(shop.uv)}</td>
        <td class="num">${fmtWan(shop.pay_buyer_count)}</td>
        <td class="pct">${fmtPct1(shop.pay_rate)}</td>
        <td class="num">${fmtWan(shop.cart_buyer_count)}</td>
        <td class="num">${fmtWan(shop.collect_buyer_count)}</td>
      </tr>`;
    }).join('');
    tbody.innerHTML = html;
  }

  // 渲染竞品列表
  function renderItemsList() {
    const container = $('[data-rival-items-list]');
    if (!state.items.length) {
      container.innerHTML = '<div style="text-align:center;color:var(--text-tertiary);padding:24px">暂无数据</div>';
      return;
    }

    const html = state.items.map(item => {
      const img = item.pic_url
        ? `<img src="${item.pic_url}" alt="" onerror="this.style.display='none'">`
        : '';
      return `<div class="rival-item-card">
        <div class="rival-item-img">${img}</div>
        <div class="rival-item-info">
          <div class="rival-item-title">${item.title || '-'}</div>
          <div class="rival-item-meta">
            <span>访客: ${fmtWan(item.uv)}</span>
            <span>支付买家: ${fmtWan(item.pay_buyer_count)}</span>
            ${item.detail_url ? `<a href="${item.detail_url}" target="_blank" style="color:var(--primary-color)">查看详情</a>` : ''}
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

        // 重新渲染图表（解决隐藏时尺寸问题）
        if (target === 'shops') {
          setTimeout(() => {
            renderUvChart();
            renderBuyerChart();
          }, 100);
        }
      });
    });
  }

  // 初始化
  async function init() {
    try {
      await Promise.all([loadSummary(), loadShops(), loadItems()]);
      renderMetrics(state.summary);
      renderUvChart();
      renderBuyerChart();
      renderShopsTable();
      renderItemsList();
      initTabs();
    } catch (err) {
      console.error('加载竞店竞品数据失败:', err);
      document.querySelectorAll('[data-rival-shops-body], [data-rival-items-list]').forEach(el => {
        el.innerHTML = `<div style="text-align:center;color:var(--text-danger);padding:24px">加载失败: ${err.message}</div>`;
      });
    }
  }

  init();
})();
