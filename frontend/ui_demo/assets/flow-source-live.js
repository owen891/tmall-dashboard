(async function () {
  'use strict';

  const API_BASE = '/api/sycm';

  const state = {
    summary: null,
    level1: [],
    level2: [],
    parentFilter: '',
  };

  function $(sel) { return document.querySelector(sel); }
  function $$(sel) { return Array.from(document.querySelectorAll(sel)); }

  function fmtInt(v) {
    if (v == null || isNaN(v)) return '--';
    return Number(v).toLocaleString('zh-CN');
  }
  function fmtMoney(v) {
    if (v == null || isNaN(v)) return '--';
    const n = Number(v);
    if (n >= 10000) return (n / 10000).toFixed(1) + '万';
    return n.toFixed(0);
  }
  function fmtPct(v) {
    if (v == null || isNaN(v)) return '--';
    return (Number(v) * 100).toFixed(2) + '%';
  }
  function fmtPct1(v) {
    if (v == null || isNaN(v)) return '--';
    return (Number(v) * 100).toFixed(1) + '%';
  }

  // 渠道类型判断
  function getChannelType(name) {
    const paid = ['效果广告', '付费', '直通车', '超级推荐', '品销宝', '钻展', '万相台', '引力魔方'];
    const free = ['手淘搜索', '手淘推荐', '购物车', '我的淘宝', '直接访问', '自然', '免费'];
    if (paid.some(p => name.includes(p))) return 'paid';
    if (free.some(f => name.includes(f))) return 'free';
    return 'other';
  }

  function getChannelBadge(name) {
    const type = getChannelType(name);
    if (type === 'paid') return '<span class="flow-badge flow-badge--paid">付费</span>';
    if (type === 'free') return '<span class="flow-badge flow-badge--free">免费</span>';
    return '<span class="flow-badge flow-badge--other">其他</span>';
  }

  // 加载数据
  async function loadSummary() {
    const r = await fetch(API_BASE + '/flow-source/summary');
    const d = await r.json();
    if (!d.ok) throw new Error(d.message || '加载失败');
    state.summary = d.data;
    state.level1 = d.data.level1_channels;
    return d.data;
  }

  async function loadDetail(parent = '') {
    let url = API_BASE + '/flow-source/detail?';
    if (parent) url += 'parent=' + encodeURIComponent(parent);
    const r = await fetch(url);
    const d = await r.json();
    if (!d.ok) throw new Error(d.message || '加载失败');
    state.level2 = d.data.channels;
    return d.data.channels;
  }

  // 渲染指标卡片
  function renderMetrics(summary) {
    $('[data-flow-date]').textContent = summary.stat_date;
    $('[data-flow-total-uv]').textContent = fmtInt(summary.total_uv);
    $('[data-flow-total-pay]').textContent = '¥' + fmtMoney(summary.total_pay_amount);

    let totalBuyers = 0;
    state.level1.forEach(ch => { totalBuyers += ch.pay_buyer_count || 0; });
    $('[data-flow-total-buyers]').textContent = fmtInt(totalBuyers);

    const rate = summary.total_uv > 0 ? totalBuyers / summary.total_uv : 0;
    $('[data-flow-total-rate]').textContent = fmtPct1(rate);
  }

  // 渲染饼图
  function renderPieChart() {
    const chart = echarts.init(document.getElementById('flowPieChart'));
    const data = state.level1.map(ch => ({
      name: ch.channel_name,
      value: ch.uv || 0,
    }));
    chart.setOption({
      tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
      legend: { bottom: 0, textStyle: { fontSize: 11 } },
      series: [{
        type: 'pie',
        radius: ['40%', '70%'],
        center: ['50%', '45%'],
        avoidLabelOverlap: true,
        itemStyle: { borderRadius: 6, borderColor: '#fff', borderWidth: 2 },
        label: { show: false },
        emphasis: { label: { show: true, fontSize: 14, fontWeight: 'bold' } },
        data: data,
      }],
      color: ['#3b82f6', '#ef4444', '#22c55e', '#f59e0b', '#8b5cf6', '#06b6d4', '#ec4899'],
    });
  }

  // 渲染柱状图
  function renderBarChart() {
    const chart = echarts.init(document.getElementById('flowBarChart'));
    const names = state.level1.map(ch => ch.channel_name);
    const payData = state.level1.map(ch => ch.pay_amount || 0);
    chart.setOption({
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
      grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
      xAxis: { type: 'category', data: names, axisLabel: { fontSize: 11, rotate: 0 } },
      yAxis: { type: 'value', axisLabel: { formatter: function(v) { return v >= 10000 ? (v/10000).toFixed(0) + '万' : v; } } },
      series: [{
        type: 'bar',
        data: payData,
        itemStyle: { color: '#3b82f6', borderRadius: [4, 4, 0, 0] },
        barWidth: '50%',
      }],
    });
  }

  // 渲染一级渠道表格
  function renderLevel1Table() {
    const tbody = $('[data-flow-level1-body]');
    if (!state.level1.length) {
      tbody.innerHTML = '<tr><td colspan="11" style="text-align:center;color:var(--text-tertiary);padding:24px">暂无数据</td></tr>';
      return;
    }

    const totalUv = state.summary.total_uv;
    const html = state.level1.map(ch => {
      const uvPct = totalUv > 0 ? (ch.uv / totalUv) : 0;
      const avgPrice = ch.pay_buyer_count > 0 ? ch.pay_amount / ch.pay_buyer_count : 0;
      return `<tr>
        <td><strong>${ch.channel_name}</strong></td>
        <td>${getChannelBadge(ch.channel_name)}</td>
        <td class="num">${fmtInt(ch.uv)}</td>
        <td class="pct">${fmtPct1(uvPct)}</td>
        <td class="num">¥${fmtMoney(ch.pay_amount)}</td>
        <td class="num">${fmtInt(ch.pay_buyer_count)}</td>
        <td class="pct">${fmtPct1(ch.pay_rate)}</td>
        <td class="num">¥${avgPrice.toFixed(0)}</td>
        <td class="num">¥${(ch.uv_value || 0).toFixed(2)}</td>
        <td class="num">${fmtInt(ch.cart_buyer_count)}</td>
        <td class="num">${fmtInt(ch.new_uv)}</td>
      </tr>`;
    }).join('');
    tbody.innerHTML = html;
  }

  // 渲染二级渠道表格
  function renderLevel2Table() {
    const tbody = $('[data-flow-level2-body]');
    let channels = state.level2;
    if (state.parentFilter) {
      channels = channels.filter(ch => ch.parent_channel === state.parentFilter);
    }

    if (!channels.length) {
      tbody.innerHTML = '<tr><td colspan="10" style="text-align:center;color:var(--text-tertiary);padding:24px">暂无数据</td></tr>';
      return;
    }

    const totalUv = channels.reduce((s, ch) => s + (ch.uv || 0), 0);
    const html = channels.map(ch => {
      const uvPct = totalUv > 0 ? (ch.uv / totalUv) : 0;
      return `<tr>
        <td>${ch.channel_name}</td>
        <td><span style="color:var(--text-secondary)">${ch.parent_channel || '-'}</span></td>
        <td class="num">${fmtInt(ch.uv)}</td>
        <td class="pct">${fmtPct1(uvPct)}</td>
        <td class="num">¥${fmtMoney(ch.pay_amount)}</td>
        <td class="num">${fmtInt(ch.pay_buyer_count)}</td>
        <td class="pct">${fmtPct1(ch.pay_rate)}</td>
        <td class="num">¥${(ch.uv_value || 0).toFixed(2)}</td>
        <td class="num">${fmtInt(ch.cart_buyer_count)}</td>
        <td class="num">${fmtInt(ch.new_uv)}</td>
      </tr>`;
    }).join('');
    tbody.innerHTML = html;
  }

  // 初始化筛选器
  function initFilters() {
    const select = $('[data-flow-parent-filter]');
    state.level1.forEach(ch => {
      const opt = document.createElement('option');
      opt.value = ch.channel_name;
      opt.textContent = ch.channel_name;
      select.appendChild(opt);
    });
    select.addEventListener('change', (e) => {
      state.parentFilter = e.target.value;
      renderLevel2Table();
    });
  }

  // 初始化
  async function init() {
    try {
      await loadSummary();
      await loadDetail();
      renderMetrics(state.summary);
      renderPieChart();
      renderBarChart();
      renderLevel1Table();
      renderLevel2Table();
      initFilters();
    } catch (err) {
      console.error('加载流量来源数据失败:', err);
      document.querySelectorAll('[data-flow-level1-body], [data-flow-level2-body]').forEach(el => {
        el.innerHTML = `<tr><td colspan="11" style="text-align:center;color:var(--text-danger);padding:24px">加载失败: ${err.message}</td></tr>`;
      });
    }
  }

  init();
})();
