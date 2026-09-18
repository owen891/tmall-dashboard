(async function () {
  'use strict';

  const API_BASE = '/api/sycm';

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
  async function loadAllChannels() {
    const r = await fetch(API_BASE + '/flow-source/detail');
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
    $('[data-flow-date]').textContent = summary.stat_date;
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
  }

  // 渲染树形表格
  function renderTreeTable() {
    const tbody = $('[data-flow-table-body]');
    const totalUv = state.summary.total_uv || 0;

    if (!state.tree.length) {
      tbody.innerHTML = '<tr><td colspan="14" style="text-align:center;color:var(--text-tertiary);padding:24px">暂无数据</td></tr>';
      return;
    }

    let html = '';

    function renderNode(node, totalUv) {
      const isExpanded = state.expanded.has(node.channel_name);
      const hasChildren = node.children.length > 0;
      const indent = (node.level - 1) * 20;

      const toggleBtn = hasChildren
        ? `<span class="toggle-btn" data-toggle="${node.channel_name}">${isExpanded ? '−' : '+'}</span>`
        : `<span class="toggle-btn toggle-btn--empty">·</span>`;

      const uvPct = totalUv > 0 ? (node.uv / totalUv) : 0;
      const avgPrice = node.pay_buyer_count > 0 ? node.pay_amount / node.pay_buyer_count : 0;

      html += `<tr class="level-${node.level}">
        <td>
          <div class="channel-cell" style="padding-left:${indent}px">
            ${toggleBtn}
            <span class="channel-name ${hasChildren ? 'channel-name--clickable' : ''}" data-channel="${node.channel_name}">${node.channel_name}</span>
          </div>
        </td>
        <td>${getChannelBadge(node.channel_name)}</td>
        <td class="num">${fmtInt(node.uv)}</td>
        <td class="pct">${fmtPct1(uvPct)}</td>
        <td class="num">¥${fmtMoney(node.pay_amount)}</td>
        <td class="num">${fmtInt(node.pay_buyer_count)}</td>
        <td class="pct">${fmtPct2(node.pay_rate)}</td>
        <td class="num">¥${avgPrice.toFixed(0)}</td>
        <td class="num">¥${(node.uv_value || 0).toFixed(2)}</td>
        <td class="num">${fmtInt(node.cart_buyer_count)}</td>
        <td class="pct">${node.uv > 0 ? fmtPct2(node.cart_buyer_count / node.uv) : "--"}</td>
        <td class="num">${fmtInt(node.collect_item_count)}</td>
        <td class="num">${fmtInt(node.new_uv)}</td>
        <td class="num">${fmtInt(node.ad_click_count)}</td>
        <td class="num">¥${fmtMoney(node.ad_pay_amount)}</td>
      </tr>`;

      // 如果展开了，渲染子节点
      if (isExpanded && hasChildren) {
        node.children.forEach(child => renderNode(child, totalUv));
      }
    }

    state.tree.forEach(node => renderNode(node, totalUv));
    tbody.innerHTML = html;

    // 绑定折叠/展开事件
    tbody.querySelectorAll('[data-toggle]').forEach(el => {
      el.addEventListener('click', (e) => {
        e.stopPropagation();
        const name = el.dataset.toggle;
        if (state.expanded.has(name)) {
          state.expanded.delete(name);
        } else {
          state.expanded.add(name);
        }
        renderTreeTable();
      });
    });

    // 绑定渠道名称点击事件（也能触发展开/折叠）
    tbody.querySelectorAll('.channel-name--clickable').forEach(el => {
      el.addEventListener('click', () => {
        const name = el.dataset.channel;
        if (state.expanded.has(name)) {
          state.expanded.delete(name);
        } else {
          state.expanded.add(name);
        }
        renderTreeTable();
      });
    });
  }

  // 渲染统计
  function renderStats() {
    const counts = countLevels(state.tree);
    $('[data-flow-l1-count]').textContent = counts.l1;
    $('[data-flow-l2-count]').textContent = counts.l2;
    $('[data-flow-l3-count]').textContent = counts.l3;
  }

  // 初始化
  async function init() {
    try {
      // 加载汇总数据
      const r = await fetch(API_BASE + '/flow-source/summary');
      const d = await r.json();
      if (!d.ok) throw new Error(d.message || '加载失败');
      state.summary = d.data;

      // 加载所有渠道数据
      await loadAllChannels();

      // 构建树形结构
      state.tree = buildTree();

      // 默认展开一级渠道
      state.tree.forEach(node => state.expanded.add(node.channel_name));

      // 渲染
      renderMetrics();
      renderPieChart();
      renderBarChart();
      renderStats();
      renderTreeTable();
    } catch (err) {
      console.error('加载流量来源数据失败:', err);
      $('[data-flow-table-body]').innerHTML = `<tr><td colspan="14" style="text-align:center;color:var(--text-danger);padding:24px">加载失败: ${err.message}</td></tr>`;
    }
  }

  init();
})();
