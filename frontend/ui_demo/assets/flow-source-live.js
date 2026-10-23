(async function () {
  'use strict';
  const escapeHtml = window.DemoFormat?.escapeHtml
    ? window.DemoFormat.escapeHtml
    : (v) => String(v ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);

  const API_BASE = '/api/sycm';

  const chartInstances = new Set();
  function syncChartTheme(chart) {
    if (!chart) return;
    const styles = getComputedStyle(document.documentElement);
    const textColor = styles.getPropertyValue('--text-secondary').trim() || '#64748b';
    const primaryColor = styles.getPropertyValue('--text-primary').trim() || '#111827';
    const borderColor = styles.getPropertyValue('--border-default').trim() || '#d1d5db';
    chart.setOption({
      textStyle: { color: textColor },
      legend: { textStyle: { color: textColor } },
      xAxis: { axisLabel: { color: textColor }, axisLine: { lineStyle: { color: borderColor } } },
      yAxis: { axisLabel: { color: textColor }, axisLine: { lineStyle: { color: borderColor } }, splitLine: { lineStyle: { color: borderColor } } },
      tooltip: { backgroundColor: styles.getPropertyValue('--surface-base').trim(), borderColor, textStyle: { color: primaryColor } },
    });
  }
  function registerChart(chart) { if (chart) { chartInstances.add(chart); syncChartTheme(chart); } return chart; }
  new MutationObserver(() => chartInstances.forEach(syncChartTheme)).observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });

  const state = {
    summary: null,
    allChannels: [],
    tree: [], // 树形结构
    expanded: new Set(), // 展开的渠道名称集合
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
  function fmtPct1(v) {
    if (v == null || isNaN(v)) return '--';
    return (Number(v) * 100).toFixed(1) + '%';
  }
  function fmtPct2(v) {
    if (v == null || isNaN(v)) return '--';
    return (Number(v) * 100).toFixed(2) + '%';
  }


  // 渠道类型判断
  function getChannelType(name) {
    const paid = ['效果广告', '付费', '直通车', '超级推荐', '品销宝', '钻展', '万相台', '引力魔方', '站外广告', '内容广告', '品牌广告', '关键词推广', '人群推广', '智能场景', '超级直播', '超级短视频', '超级全域通', '竞争卡位', '品牌定制', '流量宝', '淘宝客'];
    const free = ['手淘搜索', '手淘推荐', '购物车', '我的淘宝', '直接访问', '自然', '免费', '淘宝直播', '关注', '淘内待分类', '淘外网站', '手淘拍立淘', '淘金币', '一淘', '天猫APP', '手淘旺信', '手淘问大家', '百亿补贴', '手淘其他店铺', '手淘消息中心', '日常营销', '淘口令', '天猫榜单', '芭芭农场', '淘宝秒杀', '淘宝特价版', '红包省钱卡', '大促会场', '88VIP', '手机浏览器', '逛逛', '闲鱼', '天猫超市', '手淘充值', '手淘确认订单', '首页推荐', '购后推荐', '购中推荐', '店铺超链', '其他猜你喜欢'];
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

  // 加载所有渠道数据
  async function loadAllChannels(startDate, endDate) {
    const params = new URLSearchParams();
    if (startDate) params.set('start', startDate);
    if (endDate) params.set('end', endDate);
    const query = params.toString() ? `?${params.toString()}` : '';
    const r = await fetch(API_BASE + '/flow-source/detail' + query);
    const d = await r.json();
    if (!d.ok) throw new Error(d.message || '加载失败');
    state.allChannels = d.data.channels;
    return d.data.channels;
  }

  // 构建树形结构
  function buildTree() {
    const level1 = state.summary.level1_channels || [];
    const all = state.allChannels;

    // 按parent_channel分组
    const childrenMap = {};
    all.forEach(ch => {
      const parent = ch.parent_channel || '';
      if (!childrenMap[parent]) childrenMap[parent] = [];
      childrenMap[parent].push(ch);
    });

    // 递归构建树
    function buildNode(channel, level) {
      const node = {
        ...channel,
        level: level,
        children: [],
      };
      const children = childrenMap[channel.channel_name] || [];
      children.forEach(child => {
        node.children.push(buildNode(child, level + 1));
      });
      // 按访客数排序
      node.children.sort((a, b) => (b.uv || 0) - (a.uv || 0));
      return node;
    }

    const tree = level1.map(ch => buildNode(ch, 1));
    tree.sort((a, b) => (b.uv || 0) - (a.uv || 0));
    return tree;
  }

  // 统计各层级渠道数
  function countLevels(tree) {
    let l1 = 0, l2 = 0, l3 = 0;
    function traverse(nodes) {
      nodes.forEach(node => {
        if (node.level === 1) l1++;
        else if (node.level === 2) l2++;
        else if (node.level === 3) l3++;
        if (node.children.length) traverse(node.children);
      });
    }
    traverse(tree);
    return { l1, l2, l3 };
  }

  // 渲染指标卡片
  function renderMetrics() {
    const summary = state.summary;
    const startDate = summary.start_date || summary.stat_date;
    const endDate = summary.end_date || summary.stat_date;
    $('[data-flow-date]').textContent = startDate === endDate
      ? `统计日 ${endDate}`
      : `统计范围 ${startDate} ~ ${endDate}`;
    $('[data-flow-total-uv]').textContent = fmtInt(summary.total_uv);
    $('[data-flow-total-pay]').textContent = '¥' + fmtMoney(summary.total_pay_amount);

    let totalBuyers = 0;
    state.summary.level1_channels.forEach(ch => { totalBuyers += ch.pay_buyer_count || 0; });
    $('[data-flow-total-buyers]').textContent = fmtInt(totalBuyers);

    const rate = summary.total_uv > 0 ? totalBuyers / summary.total_uv : 0;
    $('[data-flow-total-rate]').textContent = fmtPct1(rate);
  }

  // 渲染饼图（一级渠道）
  function renderPieChart() {
    const chart = echarts.init(document.getElementById('flowPieChart'));
    const channels = state.tree;
    const data = channels.map(ch => ({
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
      color: ['#3b82f6', '#ef4444', '#22c55e', '#f59e0b', '#8b5cf6', '#06b6d4', '#ec4899', '#84cc16', '#f97316', '#14b8a6'],
    });
    registerChart(chart);
  }

  // 渲染柱状图（一级渠道TOP10）
  function renderBarChart() {
    const chart = echarts.init(document.getElementById('flowBarChart'));
    const topChannels = state.tree.slice(0, 10);
    const names = topChannels.map(ch => ch.channel_name.length > 6 ? ch.channel_name.slice(0, 6) + '...' : ch.channel_name);
    const payData = topChannels.map(ch => ch.pay_amount || 0);
    chart.setOption({
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
      grid: { left: '3%', right: '4%', bottom: '15%', containLabel: true },
      xAxis: { type: 'category', data: names, axisLabel: { fontSize: 10, rotate: 30 } },
      yAxis: { type: 'value', axisLabel: { formatter: function(v) { return v >= 10000 ? (v/10000).toFixed(0) + '万' : v; } } },
      series: [{
        type: 'bar',
        data: payData,
        itemStyle: { color: '#3b82f6', borderRadius: [4, 4, 0, 0] },
        barWidth: '50%',
      }],
    });
    registerChart(chart);
  }

  // Render the two tables that the current page exposes.
  function renderTreeTable() {
    const level1Body = $('[data-flow-level1-body]');
    const level2Body = $('[data-flow-level2-body]');
    const parentFilter = $('[data-flow-parent-filter]');
    const totalUv = state.summary.total_uv || 0;
    const level1 = state.tree;
    const selectedParent = parentFilter?.value || '';
    const level2 = level1.flatMap((parent) => {
      if (selectedParent && selectedParent !== parent.channel_name) return [];
      return parent.children.map((child) => ({ ...child, parent_channel: parent.channel_name }));
    });

    if (parentFilter && !parentFilter.dataset.ready) {
      parentFilter.replaceChildren(new Option('全部一级渠道', ''));
      level1.forEach((node) => parentFilter.add(new Option(node.channel_name, node.channel_name)));
      parentFilter.dataset.ready = 'true';
      parentFilter.addEventListener('change', renderTreeTable);
    }

    const replaceTableBody = (body, columns, rows, emptyMessage) => {
      if (!body || !window.TmallUI?.table?.mount) return;
      window.TmallUI.table.mount(body, { columns, rows, emptyMessage });
    };

    const level1Columns = [
      { key: 'channel_name', label: '渠道名称', render: (value) => {
        const cell = document.createElement('div');
        cell.className = 'channel-cell';
        const name = document.createElement('span');
        name.className = 'channel-name';
        name.textContent = value || '--';
        cell.append(name);
        return cell;
      } },
      { key: 'channel_name', label: '类型', render: getChannelBadge },
      { key: 'uv', label: '访客数', numeric: true, render: fmtInt },
      { key: 'uv_pct', label: '访客占比', numeric: true, className: 'pct', render: fmtPct1 },
      { key: 'pay_amount', label: '支付金额', numeric: true, render: (value) => `¥${fmtMoney(value)}` },
      { key: 'pay_buyer_count', label: '支付买家', numeric: true, render: fmtInt },
      { key: 'pay_rate', label: '支付转化率', numeric: true, className: 'pct', render: fmtPct2 },
      { key: 'avg_price', label: '客单价', numeric: true, render: (value) => `¥${Number(value || 0).toFixed(0)}` },
      { key: 'uv_value', label: 'UV价值', numeric: true, render: (value) => `¥${Number(value || 0).toFixed(2)}` },
      { key: 'cart_buyer_count', label: '加购人数', numeric: true, render: fmtInt },
      { key: 'new_uv', label: '新访客', numeric: true, render: fmtInt },
    ];
    const level2Columns = [
      { key: 'channel_name', label: '子渠道', render: (value) => {
        const cell = document.createElement('span');
        cell.className = 'channel-name';
        cell.textContent = value || '--';
        return cell;
      } },
      { key: 'parent_channel', label: '所属渠道' },
      { key: 'uv', label: '访客数', numeric: true, render: fmtInt },
      { key: 'uv_pct', label: '访客占比', numeric: true, className: 'pct', render: fmtPct1 },
      { key: 'pay_amount', label: '支付金额', numeric: true, render: (value) => `¥${fmtMoney(value)}` },
      { key: 'pay_buyer_count', label: '支付买家', numeric: true, render: fmtInt },
      { key: 'pay_rate', label: '支付转化率', numeric: true, className: 'pct', render: fmtPct2 },
      { key: 'uv_value', label: 'UV价值', numeric: true, render: (value) => `¥${Number(value || 0).toFixed(2)}` },
      { key: 'cart_buyer_count', label: '加购人数', numeric: true, render: fmtInt },
      { key: 'new_uv', label: '新访客', numeric: true, render: fmtInt },
    ];

    const level1Rows = level1.map((node) => ({
      ...node,
      uv_pct: totalUv > 0 ? (node.uv / totalUv) : 0,
      avg_price: node.pay_buyer_count > 0 ? node.pay_amount / node.pay_buyer_count : 0,
    }));
    const level2Rows = level2.map((node) => ({
      ...node,
      uv_pct: totalUv > 0 ? (node.uv / totalUv) : 0,
    }));
    replaceTableBody(level1Body, level1Columns, level1Rows, '暂无数据');
    replaceTableBody(level2Body, level2Columns, level2Rows, level1.length ? '暂无子渠道数据' : '暂无数据');
    return;
  }

  // 渲染统计
  function renderStats() {
    const counts = countLevels(state.tree);
    const l1 = $('[data-flow-l1-count]');
    const l2 = $('[data-flow-l2-count]');
    const l3 = $('[data-flow-l3-count]');
    if (l1) l1.textContent = counts.l1;
    if (l2) l2.textContent = counts.l2;
    if (l3) l3.textContent = counts.l3;
    const topShare = $('[data-flow-top-share]');
    if (topShare) {
      const totalUv = state.summary?.total_uv || 0;
      const topUv = state.tree.slice(0, 3).reduce((sum, node) => sum + (node.uv || 0), 0);
      topShare.textContent = totalUv ? fmtPct1(topUv / totalUv) : '--';
    }
  }

  function renderCommandSummary() {
    const leading = $('[data-flow-leading]');
    const efficiency = $('[data-flow-efficiency]');
    const opportunity = $('[data-flow-opportunity]');
    if (!leading || !efficiency || !opportunity) return;
    const channels = [...state.tree];
    const totalUv = state.summary?.total_uv || 0;
    const byUv = [...channels].sort((a, b) => (b.uv || 0) - (a.uv || 0));
    const byRate = [...channels].sort((a, b) => (b.pay_rate || 0) - (a.pay_rate || 0));
    const lead = byUv[0];
    const best = byRate[0];
    leading.textContent = lead
      ? `${lead.channel_name}贡献访客最多，占整体 ${fmtPct1(totalUv ? lead.uv / totalUv : 0)}。`
      : '暂无可判断的渠道数据。';
    efficiency.textContent = best
      ? `${best.channel_name}支付转化率最高，为 ${fmtPct2(best.pay_rate)}，建议关注其流量质量是否可复制。`
      : '暂无足够数据判断渠道效率。';
    opportunity.textContent = lead && best && lead.channel_name !== best.channel_name
      ? `规模主力与效率主力不一致，优先拆解 ${lead.channel_name} 的二级渠道，寻找低效入口。`
      : '优先从头部渠道的二级入口开始，核对访客、支付买家与 UV 价值。';
  }

  // 初始化
  async function init(detail) {
    try {
      const range = detail || window.TmallDateRange?.getState?.() || {};
      const startDate = range.startDate || range.endDate || '';
      const endDate = range.endDate || range.startDate || '';
      const params = new URLSearchParams();
      if (startDate) params.set('start', startDate);
      if (endDate) params.set('end', endDate);
      const query = params.toString() ? `?${params.toString()}` : '';
      // 加载汇总数据
      const r = await fetch(API_BASE + '/flow-source/summary' + query);
      const d = await r.json();
      if (!d.ok) throw new Error(d.message || '加载失败');
      state.summary = d.data;

      // 加载所有渠道数据
      await loadAllChannels(startDate, endDate);

      // 构建树形结构
      state.tree = buildTree();

      // 默认展开一级渠道
      state.tree.forEach(node => state.expanded.add(node.channel_name));

      // 渲染
      renderMetrics();
      renderPieChart();
      renderBarChart();
      renderStats();
      renderCommandSummary();
      renderTreeTable();
    } catch (err) {
      console.error('加载流量来源数据失败:', err);
      const bodies = ['[data-flow-level1-body]', '[data-flow-level2-body]', '[data-flow-table-body]']
        .map((selector) => $(selector))
        .filter(Boolean);
      bodies.forEach((body) => {
        body.innerHTML = `<tr><td colspan="14" style="text-align:center;color:var(--danger-text);padding:24px">加载失败: ${escapeHtml(err.message)}</td></tr>`;
      });
    }
  }

  // 订阅样板收敛到 TmallRuntime.subscribeDateRange（runtime/date-range-scope.js）
  window.TmallRuntime?.subscribeDateRange
    ? window.TmallRuntime.subscribeDateRange((detail) => init(detail))
    : (window.addEventListener('tmall:date-range-change', (event) => init(event.detail)),
       init(window.TmallDateRange?.getState?.()));
})();
