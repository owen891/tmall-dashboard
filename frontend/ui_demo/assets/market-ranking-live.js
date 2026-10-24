(async function () {
  'use strict';
  const escapeHtml = window.DemoFormat?.escapeHtml
    ? window.DemoFormat.escapeHtml
    : (v) => String(v ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);

  const API_BASE = '/api/market-ranking';

  const state = {
    summary: null,
    categories: [],
    listTypes: [],
    keywordTypes: [],
    filterCategory: '',
    filterListType: '',
    kwCategory: '',
    kwType: '',
    trend: null,
    marketShops: [],
    marketItems: [],
    selectedMarketShop: '',
    selectedMarketItem: '',
    marketSnapshots: null,
    selectedSnapshotType: 'rival_shop',
    marketShopPage: 1,
    marketItemPage: 1,
    marketShopMode: 'hot',
    marketItemMode: 'hot',
    marketModalRequest: 0,
  };
  let marketTrendDrawer = null;

  function initMarketTrendDrawer() {
    if (marketTrendDrawer) return;
    const modal = $('[data-market-trend-modal]');
    const dialog = modal?.querySelector('.market-trend-modal__dialog');
    const header = dialog?.querySelector('.market-trend-modal__header');
    if (!window.TmallUI?.detailDrawer || !dialog || !header) return;
    const body = document.createElement('div');
    body.className = 'market-trend-modal__drawer-body';
    [...dialog.children].filter((node) => node !== header).forEach((node) => body.append(node));
    // 详情面统一 NUI 抽屉：dialog 壳仅作内容来源；壳上的 data-market-modal-*
    // 摘下挂到抽屉页眉，openMarketTrendModal 的标题/说明更新才能落到抽屉。
    marketTrendDrawer = window.TmallUI.detailDrawer({ title: '趋势详情', description: '正在读取…', body, size: 'lg' });
    marketTrendDrawer.node.setAttribute('data-modal-kind', 'detail');
    const legacyTitle = header.querySelector('[data-market-modal-title]');
    const legacyMeta = header.querySelector('[data-market-modal-meta]');
    legacyTitle?.removeAttribute('data-market-modal-title');
    legacyMeta?.removeAttribute('data-market-modal-meta');
    if (legacyTitle) legacyTitle.id = 'market-trend-modal-legacy-title';
    const drawerTitle = marketTrendDrawer.node.querySelector('h2');
    const drawerMeta = marketTrendDrawer.node.querySelector('.ui-drawer__copy p');
    if (drawerTitle) {
      drawerTitle.dataset.marketModalTitle = '';
      drawerTitle.id = 'market-trend-modal-title';
    }
    if (drawerMeta) drawerMeta.dataset.marketModalMeta = '';
  }

  function closeMarketTrendModal() {
    marketTrendDrawer?.close();
  }

  let initialized = false;
  const selectedDate = () => window.TmallDateRange?.getState?.().endDate || '';
  const withDate = (url) => {
    const date = selectedDate();
    return date ? `${url}${url.includes('?') ? '&' : '?'}analysis_date=${encodeURIComponent(date)}` : url;
  };
  const withSycmDate = (url) => {
    const date = selectedDate();
    return date ? `${url}${url.includes('?') ? '&' : '?'}date=${encodeURIComponent(date)}` : url;
  };

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
  const fmtPct = window.DemoFormat?.fmtPct1 || ((v) => v == null || isNaN(v) ? '--' : ((Number(v) * 100).toFixed(1) + '%'));
  const fmtWan = window.DemoFormat?.fmtWan || ((v) => v == null || isNaN(v) ? '--' : String(Number(v)));

  // ===== 加载数据 =====
  async function loadSummary() {
    const r = await fetch(withDate(API_BASE + '/summary'));
    const d = await r.json();
    if (!d.ok) throw new Error(d.message || '加载失败');
    state.summary = d.data;
    state.categories = d.data.categories.map(c => c.category);
    return d.data;
  }

  async function loadFilters() {
    const r = await fetch(withDate(API_BASE + '/filters'));
    const d = await r.json();
    if (!d.ok) throw new Error(d.message || '加载失败');
    state.listTypes = d.data.list_types;
    state.keywordTypes = d.data.keyword_types;
    return d.data;
  }

  async function loadProducts() {
    let url = API_BASE + '/products?';
    if (state.filterCategory) url += 'category=' + encodeURIComponent(state.filterCategory) + '&';
    if (state.filterListType) url += 'list_type=' + encodeURIComponent(state.filterListType) + '&';
    const r = await fetch(withDate(url));
    const d = await r.json();
    return d.ok ? d.data : [];
  }

  async function loadKeywords() {
    let url = API_BASE + '/keywords?';
    if (state.kwCategory) url += 'category=' + encodeURIComponent(state.kwCategory) + '&';
    if (state.kwType) url += 'keyword_type=' + encodeURIComponent(state.kwType) + '&';
    const r = await fetch(withDate(url));
    const d = await r.json();
    return d.ok ? d.data : [];
  }

  async function loadOverlapShops() {
    const r = await fetch(withDate(API_BASE + '/overlap-shops'));
    const d = await r.json();
    return d.ok ? d.data : [];
  }

  // ===== 渲染指标卡片 =====
  function renderMetrics(summary) {
    $('[data-mr-period]').textContent = `${summary.period_start} ~ ${summary.period_end}`;
    const freshness = $('[data-mr-freshness]');
    if (freshness) {
      const selected = selectedDate();
      const batchDate = summary.analysis_date || summary.period_end || '';
      if (selected && batchDate && selected !== batchDate) {
        freshness.textContent = `已回退最近批次：${batchDate}（当前选择 ${selected}）`;
        freshness.title = '当前选择日期暂无市场分析批次，页面展示不晚于该日期的最近批次。';
      } else if (batchDate) {
        freshness.textContent = `分析批次：${batchDate}`;
        freshness.title = '市场分析批次与当前选择日期一致。';
      } else {
        freshness.textContent = '批次日期未知';
      }
    }
    $('[data-mr-cat-count]').textContent = summary.category_count;
    $('[data-mr-product-count]').textContent = fmtInt(summary.product_count);
    $('[data-mr-kw-count]').textContent = fmtInt(summary.keyword_count);
    $('[data-mr-overlap-count]').textContent = fmtInt(summary.overlap_shop_count);
  }

  function renderCommandSummary(summary) {
    const structure = $('[data-mr-insight-structure]');
    const trend = $('[data-mr-insight-trend]');
    const opportunity = $('[data-mr-insight-opportunity]');
    const actualTrend = $('[data-mr-insight-actual-trend]');
    if (!structure || !trend || !opportunity) return;
    const categories = summary.categories || [];
    const concentrated = categories[0];
    structure.textContent = concentrated
      ? `${concentrated.category}当前样本最多，头部集中度 TOP10 为 ${fmtPct((concentrated.concentration_top10 || 0) / 100)}。`
      : '暂无足够数据判断市场集中度。';
    const marketTrend = state.trend;
    const itemCoverage = marketTrend ? `${marketTrend.item_observed_days || 0}/${marketTrend.expected_days || '--'}` : '--';
    const searchCoverage = marketTrend ? `${marketTrend.search_observed_days || 0}/${marketTrend.expected_days || '--'}` : '--';
    trend.textContent = marketTrend?.trend_comparable
      ? `商品榜覆盖 ${itemCoverage} 天、搜索榜覆盖 ${searchCoverage} 天；可看样本变化，不等同于行业全量成交额。`
      : `商品榜覆盖 ${itemCoverage} 天、搜索榜覆盖 ${searchCoverage} 天，至少一类覆盖不足，暂不判断市场趋势。`;
    opportunity.textContent = summary.keyword_count
      ? `当前只能形成候选线索；需再核对搜索热度连续变化、价格带和我方毛利，验证后再进入下月计划。`
      : '关键词样本不足，先补齐搜索排行数据再做机会判断。';
    if (actualTrend) {
      const daily = (marketTrend?.daily || []);
      const searchRows = daily.filter(row => row.avg_search_heat != null);
      const buyerRows = daily.filter(row => row.avg_item_buyers != null);
      const pctChange = (rows, field) => {
        if (rows.length < 2 || !rows[0][field] || rows[rows.length - 1][field] == null) return null;
        return ((Number(rows[rows.length - 1][field]) - Number(rows[0][field])) / Math.abs(Number(rows[0][field]))) * 100;
      };
      const heatChange = pctChange(searchRows, 'avg_search_heat');
      const buyerChange = pctChange(buyerRows, 'avg_item_buyers');
      const missingItemDates = daily.filter(row => row.item_count == null).map(row => row.stat_date.slice(5));
      const missingSearchDates = daily.filter(row => row.keyword_count == null).map(row => row.stat_date.slice(5));
      actualTrend.textContent = daily.length
        ? `${daily[0].stat_date} ~ ${daily[daily.length - 1].stat_date}；搜索热度${heatChange == null ? '变化待补' : `${heatChange >= 0 ? '+' : ''}${heatChange.toFixed(1)}%`}，榜内商品日均支付买家${buyerChange == null ? '变化待补' : `${buyerChange >= 0 ? '+' : ''}${buyerChange.toFixed(1)}%`}${missingItemDates.length ? `；商品榜缺 ${missingItemDates.join('、')}` : ''}${missingSearchDates.length ? `；搜索榜缺 ${missingSearchDates.join('、')}` : ''}。`
        : '当前选择范围暂无可用的市场日趋势数据。';
    }
  }

  async function loadMarketTrend() {
    const range = window.TmallDateRange?.getState?.() || {};
    const params = new URLSearchParams();
    if (range.startDate) params.set('start', range.startDate);
    if (range.endDate) params.set('end', range.endDate);
    const response = await fetch(`/api/sycm/market/trend?${params.toString()}`);
    const result = await response.json();
    state.trend = result.ok ? result.data : null;
    renderMarketTrend();
  }

  function renderMarketTrend() {
    const data = state.trend;
    const coverage = $('[data-mr-trend-coverage]');
    if (!data) {
      if (coverage) coverage.textContent = '所选日期范围暂无市场日趋势数据。';
      return;
    }
    const labels = data.daily.map(row => row.stat_date.slice(5));
    const rankedBuyers = data.daily.map(row => row.avg_item_buyers == null ? null : Number(row.avg_item_buyers));
    const searchHeat = data.daily.map(row => row.avg_search_heat == null ? null : Number(row.avg_search_heat));
    const payRate = data.daily.map(row => row.avg_pay_rate == null ? null : Number(row.avg_pay_rate) * 100);
    const productNode = $('[data-mr-product-trend]');
    const searchNode = $('[data-mr-search-trend]');
    if (typeof echarts !== 'undefined' && productNode && labels.length) {
      const productChart = echarts.init(productNode);
      productChart.setOption({
        tooltip: { trigger: 'axis' },
        grid: { left: '4%', right: '4%', bottom: '12%', containLabel: true },
        xAxis: { type: 'category', data: labels },
        yAxis: { type: 'value' },
        series: [{ type: 'line', smooth: true, connectNulls: false, data: rankedBuyers, name: '榜内商品日均支付买家', itemStyle: { color: '#2563eb' } }],
      });
      registerChart(productChart);
      const searchChart = echarts.init(searchNode);
      searchChart.setOption({
        tooltip: { trigger: 'axis' },
        legend: { bottom: 0 },
        grid: { left: '4%', right: '8%', top: '10%', bottom: '20%', containLabel: true },
        xAxis: { type: 'category', data: labels },
        yAxis: [{ type: 'value', name: '搜索热度' }, { type: 'value', name: '支付转化率%', axisLabel: { formatter: value => `${value}%` } }],
        series: [
          { type: 'line', smooth: true, connectNulls: false, data: searchHeat, name: '平均搜索热度', yAxisIndex: 0, itemStyle: { color: '#d97706' } },
          { type: 'line', smooth: true, connectNulls: false, data: payRate, name: '平均支付转化率', yAxisIndex: 1, itemStyle: { color: '#059669' } },
        ],
      });
      registerChart(searchChart);
    }
    if (coverage) {
      const itemCoverage = `${data.item_observed_days || 0}/${data.expected_days || '--'}`;
      const searchCoverage = `${data.search_observed_days || 0}/${data.expected_days || '--'}`;
      coverage.textContent = `商品榜覆盖 ${itemCoverage} 天，搜索榜覆盖 ${searchCoverage} 天。指标是所采集榜单样本均值，不代表市场全量成交；${data.trend_comparable ? '可观察区间变化。' : '至少一类覆盖不足，不下市场趋势结论。'}`;
    }
  }

  function entityRangeParams() {
    const range = window.TmallDateRange?.getState?.() || {};
    const params = new URLSearchParams();
    if (range.startDate) params.set('start', range.startDate);
    if (range.endDate) params.set('end', range.endDate);
    return params.toString();
  }

  async function loadMarketEntities() {
    const suffix = entityRangeParams();
    const [shopResponse, itemResponse] = await Promise.all([
      fetch(`/api/sycm/market/shops/entities?${suffix}`),
      fetch(`/api/sycm/market/items/entities?${suffix}`),
    ]);
    const [shopResult, itemResult] = await Promise.all([shopResponse.json(), itemResponse.json()]);
    state.marketShops = shopResult.ok ? (shopResult.data.entities || []) : [];
    state.marketItems = itemResult.ok ? (itemResult.data.entities || []) : [];
    renderMarketEntityLists();
  }

  function sparklineSvg(daily, field) {
    const values = (daily || []).map(row => row[field] == null || !Number.isFinite(Number(row[field])) ? null : Number(row[field]));
    const valid = values.filter(value => value != null);
    if (valid.length < 2) return '<svg class="market-entity-spark" viewBox="0 0 150 38" preserveAspectRatio="none"><polyline class="spark-empty" points="0,19 150,19"></polyline></svg>';
    const min = Math.min(...valid), max = Math.max(...valid), span = max - min || 1;
    const points = values.map((value, index) => value == null ? null : `${(index / Math.max(1, values.length - 1)) * 150},${34 - ((value - min) / span) * 30}`);
    const segments = [];
    let current = [];
    points.forEach(point => {
      if (point == null) {
        if (current.length) segments.push(current.join(' '));
        current = [];
      } else current.push(point);
    });
    if (current.length) segments.push(current.join(' '));
    return `<svg class="market-entity-spark" viewBox="0 0 150 38" preserveAspectRatio="none" aria-label="趋势小图">${segments.map(segment => `<polyline points="${segment}"></polyline>`).join('')}</svg>`;
  }
  function safeHttpUrl(value) {
    const url = String(value || '').trim();
    return /^https?:\/\//i.test(url) ? url : '';
  }

  function renderEntityList(kind) {
    const isShop = kind === 'shop';
    const entities = isShop ? state.marketShops : state.marketItems;
    const listNode = $(`[data-market-${kind}-list]`);
    const countNode = $(`[data-market-${kind}-count]`);
    const hintNode = $(`[data-market-${kind}-hint]`);
    const pagerNode = $(`[data-market-${kind}-pager]`);
    const mode = isShop ? state.marketShopMode : state.marketItemMode;
    const page = isShop ? state.marketShopPage : state.marketItemPage;
    const rangeEnd = window.TmallDateRange?.getState?.().endDate || '';
    const dateDaysAgo = (date, days) => {
      if (!date) return '';
      const [year, month, day] = date.split('-').map(Number);
      const value = new Date(Date.UTC(year, month - 1, day - days));
      return value.toISOString().slice(0, 10);
    };
    const samples = entity => [...(entity.daily || [])].sort((a, b) => a.stat_date.localeCompare(b.stat_date));
    const latestSample = entity => samples(entity).at(-1) || {};
    const changeRate = (entity, field) => {
      const daily = samples(entity);
      if (daily.length < 2) return null;
      const previousValue = daily.at(-2)[field];
      const latestValue = daily.at(-1)[field];
      if (previousValue == null || latestValue == null) return null;
      const previous = Number(previousValue);
      const latest = Number(latestValue);
      return Number.isFinite(previous) && previous > 0 && Number.isFinite(latest) ? (latest - previous) / previous : null;
    };
    const rankGain = entity => {
      const daily = samples(entity);
      if (daily.length < 2) return null;
      const previousRank = daily.at(-2).rank;
      const latestRank = daily.at(-1).rank;
      if (previousRank == null || latestRank == null) return null;
      const previous = Number(previousRank);
      const latest = Number(latestRank);
      return Number.isFinite(previous) && Number.isFinite(latest) ? previous - latest : null;
    };
    const itemSurgeScore = entity => {
      const gain = rankGain(entity);
      if (gain != null) return { type: 'rank', value: gain };
      return { type: 'uv', value: changeRate(entity, 'uv') };
    };
    const averageBuyers = entity => {
      const values = samples(entity).map(row => Number(row.pay_buyer_count)).filter(Number.isFinite);
      return values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : 0;
    };
    const firstSeen = entity => samples(entity)[0]?.stat_date || entity.first_seen || '';
    const compareNumber = (left, right) => (Number(right) || 0) - (Number(left) || 0);
    const recentStart = dateDaysAgo(rangeEnd, 6);
    const filtered = mode === 'new'
      ? entities.filter(entity => firstSeen(entity) && firstSeen(entity) >= recentStart && firstSeen(entity) <= rangeEnd)
      : mode === 'stable'
        ? entities.filter(entity => Number(entity.observed_days) >= 3)
        : mode === 'surge'
        ? entities.filter(entity => {
            const score = isShop ? changeRate(entity, 'uv') : itemSurgeScore(entity).value;
            return score != null && score > 0;
          })
          : entities;
    const sorted = [...filtered].sort((a, b) => {
      if (mode === 'hot') return compareNumber(latestSample(a).pay_buyer_count, latestSample(b).pay_buyer_count);
      if (mode === 'surge') {
        if (!isShop) {
          const left = itemSurgeScore(a), right = itemSurgeScore(b);
          if (left.type !== right.type) return left.type === 'rank' ? -1 : 1;
          return (Number(right.value) || 0) - (Number(left.value) || 0);
        }
        const left = changeRate(a, 'uv');
        const right = changeRate(b, 'uv');
        if (left == null && right != null) return 1;
        if (right == null && left != null) return -1;
        return (right || 0) - (left || 0) || compareNumber(latestSample(a).pay_buyer_count, latestSample(b).pay_buyer_count);
      }
      if (mode === 'new') return firstSeen(b).localeCompare(firstSeen(a)) || compareNumber(latestSample(a).pay_buyer_count, latestSample(b).pay_buyer_count);
      return compareNumber(a.observed_days, b.observed_days) || compareNumber(averageBuyers(a), averageBuyers(b));
    });
    const modeHints = {
      hot: '按最新采集支付买家排序',
      surge: isShop ? '按最近两次采集 UV 增幅；单次样本不参与' : '按最近两次排名提升；排名缺失时参考 UV 增幅',
      new: '首次出现在所选结束日前 7 天内',
      stable: '至少 3 天有采集，按覆盖天数、平均支付买家排序',
    };
    if (countNode) countNode.textContent = `${sorted.length} 个${isShop ? '店铺' : '单品'} · 点击行查看详情`;
    if (hintNode) hintNode.textContent = modeHints[mode];
    $$(`[data-market-mode-kind="${kind}"]`).forEach(button => {
      const active = button.dataset.marketMode === mode;
      button.classList.toggle('is-active', active);
      button.setAttribute('aria-pressed', String(active));
    });
    const pageSize = 20;
    const pages = Math.max(1, Math.ceil(sorted.length / pageSize));
    const currentPage = Math.min(page, pages);
    if (isShop) state.marketShopPage = currentPage; else state.marketItemPage = currentPage;
    const rows = sorted.slice((currentPage - 1) * pageSize, currentPage * pageSize);
    if (listNode) listNode.innerHTML = rows.length ? rows.map(entity => {
      const daily = samples(entity);
      const latest = daily.at(-1) || {};
      const name = entity.entity_name || entity.entity_id;
      const context = isShop ? `${entity.observed_days || 0}天覆盖 · ${entity.item_count || 0} 个商品` : `${entity.shop_name || '未知店铺'} · ${entity.observed_days || 0}天覆盖`;
      const shopChange = changeRate(entity, 'uv');
      const itemGain = rankGain(entity);
      const itemUvChange = changeRate(entity, 'uv');
      const reason = mode === 'surge'
        ? (isShop ? (shopChange == null ? '采集样本不足' : `UV ${shopChange >= 0 ? '+' : ''}${(shopChange * 100).toFixed(1)}%`) : (itemGain != null ? `排名${itemGain >= 0 ? '上升' : '下降'} ${Math.abs(itemGain)} 位` : itemUvChange == null ? '采集样本不足' : `UV ${itemUvChange >= 0 ? '+' : ''}${(itemUvChange * 100).toFixed(1)}%`))
        : mode === 'new' ? `新上榜 · ${firstSeen(entity) || '--'}`
          : mode === 'stable' ? `${entity.observed_days || 0}天有采集`
            : '';
      const sub = `${context}${reason ? ` · ${reason}` : ''}`;
      const imageUrl = isShop ? '' : safeHttpUrl(entity.pic_url);
      const image = isShop
        ? ''
        : `<span class="market-entity-thumb">${imageUrl ? `<img src="${escapeHtml(imageUrl)}" alt="" loading="lazy" onerror="this.parentElement.classList.add('is-empty');this.remove()">` : '<span class="market-entity-thumb__placeholder">图</span>'}</span>`;
      return `<button type="button" class="market-entity-row market-entity-row--${kind}" data-market-entity-kind="${kind}" data-market-entity-id="${escapeHtml(entity.entity_id)}">
        ${image}<span class="market-entity-name"><strong title="${escapeHtml(name)}">${escapeHtml(name)}</strong><small>${escapeHtml(sub)}</small></span>
        <span class="market-entity-stats">
          <span class="market-entity-stat"><small>UV</small>${fmtWan(latest.uv ?? entity.latest_uv)}</span>
          <span class="market-entity-stat"><small>支付买家</small>${fmtWan(latest.pay_buyer_count ?? entity.latest_pay_buyer_count)}</span>
          <span class="market-entity-stat"><small>${isShop ? '商品数' : '排名'}</small>${isShop ? fmtInt(latest.item_count ?? entity.item_count) : fmtInt(latest.rank)}</span>
        </span>
        <span class="market-entity-spark-wrap">${sparklineSvg(daily, 'uv')}</span></button>`;
    }).join('') : `<div class="market-list-empty">${mode === 'new' ? '所选范围内暂无新上榜实体' : mode === 'surge' ? '没有实体呈现可比较的上升变化' : mode === 'stable' ? '至少采集 3 天的实体不足' : '暂无可用趋势数据'}</div>`;
    if (pagerNode) {
      const visible = new Set([1, pages, currentPage - 1, currentPage, currentPage + 1].filter(value => value >= 1 && value <= pages));
      const pageItems = [...visible].sort((a, b) => a - b);
      let previous = 0;
      const pageButtons = pageItems.map(number => {
        const gap = number - previous > 1 ? '<span class="market-list-pager__ellipsis" aria-hidden="true">…</span>' : '';
        previous = number;
        return `${gap}<button type="button" class="${number === currentPage ? 'is-active' : ''}" data-market-page-kind="${kind}" data-market-page="${number}" ${number === currentPage ? 'aria-current="page"' : ''}>${number}</button>`;
      }).join('');
      pagerNode.innerHTML = pages > 1
        ? `<button type="button" aria-label="上一页" data-market-page-kind="${kind}" data-market-page="${currentPage - 1}" ${currentPage === 1 ? 'disabled' : ''}>‹</button>${pageButtons}<button type="button" aria-label="下一页" data-market-page-kind="${kind}" data-market-page="${currentPage + 1}" ${currentPage === pages ? 'disabled' : ''}>›</button>`
        : '';
    }
  }

  function renderMarketEntityLists() {
    renderEntityList('shop');
    renderEntityList('item');
  }

  async function openMarketTrendModal(kind, entityId) {
    const modal = $('[data-market-trend-modal]');
    const title = $('[data-market-modal-title]');
    const meta = $('[data-market-modal-meta]');
    const body = $('[data-market-modal-body]');
    const chartNode = $('[data-market-modal-chart]');
    const itemsPanel = $('[data-market-modal-items]');
    const itemsCount = $('[data-market-modal-items-count]');
    const itemsList = $('[data-market-modal-items-list]');
    const requestId = ++state.marketModalRequest;
    const endpoint = kind === 'shop' ? '/api/sycm/market/shops/entity-trend?shop_id=' : '/api/sycm/market/items/entity-trend?item_id=';
    if (!modal) return;
    marketTrendDrawer?.open();
    if (title) title.textContent = '趋势详情';
    if (meta) meta.textContent = '正在读取…';
    try {
      const result = await (await fetch(`${endpoint}${encodeURIComponent(entityId)}&${entityRangeParams()}`)).json();
      if (requestId !== state.marketModalRequest) return;
      if (!result.ok) throw new Error(result.message || '暂无趋势数据');
      const data = result.data;
      if (title) title.textContent = data.entity_name || data.title || entityId;
      if (meta) meta.textContent = `${kind === 'item' ? (data.shop_name || '未知店铺') : '市场店铺'} · 覆盖 ${data.observed_days}/${data.expected_days || '--'} 天${data.trend_comparable ? '，可观察区间变化' : '，覆盖不足不下趋势结论'}`;
      renderEntityChart(chartNode, data.daily, [
        { name: 'UV', data: data.daily.map(row => row.uv == null ? null : Number(row.uv)), itemStyle: { color: '#2563eb' } },
        { name: '支付买家', data: data.daily.map(row => row.pay_buyer_count == null ? null : Number(row.pay_buyer_count)), itemStyle: { color: '#059669' } },
        { name: '支付转化率', yAxisIndex: 1, data: data.daily.map(row => row.pay_rate == null ? null : Number(row.pay_rate) * 100), itemStyle: { color: '#d97706' } },
      ]);
      if (body) renderSharedTableBody(body, kind === 'shop' ? [
        { key: 'stat_date', label: '日期' },
        { key: 'item_count', label: '商品数', numeric: true, render: fmtInt },
        { key: 'uv', label: 'UV', numeric: true, render: fmtWan },
        { key: 'pay_buyer_count', label: '支付买家', numeric: true, render: fmtWan },
        { key: 'pay_rate', label: '支付转化率', numeric: true, render: fmtPct },
      ] : [
        { key: 'stat_date', label: '日期' },
        { key: 'uv', label: 'UV', numeric: true, render: fmtWan },
        { key: 'pay_buyer_count', label: '支付买家', numeric: true, render: fmtWan },
        { key: 'pay_rate', label: '支付转化率', numeric: true, render: fmtPct },
        { key: 'rank', label: '排名', numeric: true, render: fmtInt },
      ], data.daily);
      if (itemsPanel) itemsPanel.hidden = kind !== 'shop';
      if (kind === 'shop' && itemsList) {
        const items = data.items || [];
        if (itemsCount) itemsCount.textContent = `${items.length} 个商品`;
        itemsList.innerHTML = items.length ? items.map(item => {
          const imageUrl = /^https?:\/\//i.test(String(item.pic_url || '')) ? item.pic_url : '';
          const image = imageUrl
            ? `<img src="${escapeHtml(imageUrl)}" alt="" loading="lazy">`
            : '<span class="market-modal-item__placeholder">无图</span>';
          const title = escapeHtml(item.title || item.item_id);
          const href = /^https?:\/\//i.test(String(item.detail_url || '')) ? escapeHtml(item.detail_url) : '';
          return `<article class="market-modal-item">
            <span class="market-modal-item__image">${image}</span>
            <span class="market-modal-item__main">${href ? `<a href="${href}" target="_blank" rel="noopener">${title}</a>` : `<strong>${title}</strong>`}<small>${escapeHtml(item.item_id || '')} · ${escapeHtml(item.stat_date || '')}</small></span>
            <span class="market-modal-item__metric"><small>UV</small>${fmtWan(item.uv)}</span>
            <span class="market-modal-item__metric"><small>支付买家</small>${fmtWan(item.pay_buyer_count)}</span>
            <span class="market-modal-item__metric"><small>排名</small>${fmtInt(item.rank)}</span>
          </article>`;
        }).join('') : '<div class="market-list-empty">该店铺暂无商品明细</div>';
      } else if (itemsList) {
        itemsList.innerHTML = '';
      }
    } catch (error) {
      if (requestId !== state.marketModalRequest) return;
      if (meta) meta.textContent = error.message;
      if (body) renderSharedTableBody(body, [], [], '暂无趋势数据');
      if (itemsPanel) itemsPanel.hidden = true;
    }
  }

  function bindMarketEntityLists() {
    document.addEventListener('click', event => {
      const row = event.target.closest('[data-market-entity-kind]');
      if (row) openMarketTrendModal(row.dataset.marketEntityKind, row.dataset.marketEntityId);
      const pageButton = event.target.closest('[data-market-page-kind]');
      if (pageButton && !pageButton.disabled) {
        if (pageButton.dataset.marketPageKind === 'shop') state.marketShopPage = Number(pageButton.dataset.marketPage);
        else state.marketItemPage = Number(pageButton.dataset.marketPage);
        renderMarketEntityLists();
      }
    });
    document.addEventListener('keydown', event => {
      // 焦点在抽屉内时抽屉自会处理 Escape；这里兜住焦点落在抽屉外的情况。
      if (event.key === 'Escape' && marketTrendDrawer?.node && !marketTrendDrawer.node.hidden) closeMarketTrendModal();
    });
    $$('[data-market-mode-kind]').forEach(button => button.addEventListener('click', () => {
      const kind = button.dataset.marketModeKind;
      if (kind === 'shop') { state.marketShopMode = button.dataset.marketMode; state.marketShopPage = 1; }
      else { state.marketItemMode = button.dataset.marketMode; state.marketItemPage = 1; }
      renderEntityList(kind);
    }));
  }

  function renderEntityChart(node, daily, series) {
    if (!node || typeof echarts === 'undefined') return;
    const chart = echarts.getInstanceByDom(node) || echarts.init(node);
    chart.setOption({
      tooltip: { trigger: 'axis' },
      legend: { bottom: 0 },
      grid: { left: '4%', right: '5%', top: '8%', bottom: '22%', containLabel: true },
      xAxis: { type: 'category', data: daily.map(row => row.stat_date.slice(5)) },
      yAxis: [{ type: 'value' }, { type: 'value', axisLabel: { formatter: value => `${value}%` } }],
      series: series.map(item => ({ ...item, type: 'line', smooth: true, connectNulls: false })),
    }, true);
    registerChart(chart);
  }

  function renderSharedTableBody(body, columns, rows, emptyMessage = '暂无趋势数据') {
    const currentTable = body?.closest('table');
    if (!currentTable || !window.TmallUI?.table?.mount) return;
    const resolvedColumns = columns.length ? columns : [...currentTable.querySelectorAll('thead th')].map((cell, index) => ({
      key: `empty_${index}`,
      label: cell.textContent.trim(),
      numeric: cell.classList.contains('num'),
      className: cell.classList.contains('pct') ? 'pct' : '',
    }));
    window.TmallUI.table.mount(body, { columns: resolvedColumns, rows, emptyMessage });
  }

  async function loadMarketShopTrend(shopId) {
    const meta = $('[data-market-shop-meta]');
    const body = $('[data-market-shop-body]');
    if (!shopId) { if (meta) meta.textContent = '暂无可用店铺趋势数据。'; return; }
    try {
      const response = await fetch(`/api/sycm/market/shops/entity-trend?shop_id=${encodeURIComponent(shopId)}&${entityRangeParams()}`);
      const result = await response.json();
      if (!result.ok) throw new Error(result.message || '暂无数据');
      const data = result.data;
      renderEntityChart($('[data-market-shop-chart]'), data.daily, [
        { name: 'UV', data: data.daily.map(row => row.uv == null ? null : Number(row.uv)), itemStyle: { color: '#2563eb' } },
        { name: '支付买家', data: data.daily.map(row => row.pay_buyer_count == null ? null : Number(row.pay_buyer_count)), itemStyle: { color: '#059669' } },
        { name: '支付转化率', yAxisIndex: 1, data: data.daily.map(row => row.pay_rate == null ? null : Number(row.pay_rate) * 100), itemStyle: { color: '#d97706' } },
      ]);
      if (meta) meta.textContent = `${data.entity_name || shopId} · 覆盖 ${data.observed_days}/${data.expected_days || '--'} 天${data.trend_comparable ? '，可观察区间变化' : '，覆盖不足不下趋势结论'}`;
      if (body) renderSharedTableBody(body, [
        { key: 'stat_date', label: '日期' },
        { key: 'item_count', label: '商品数', numeric: true, render: fmtInt },
        { key: 'uv', label: 'UV', numeric: true, render: fmtWan },
        { key: 'pay_buyer_count', label: '支付买家', numeric: true, render: fmtWan },
        { key: 'pay_rate', label: '支付转化率', numeric: true, render: fmtPct },
      ], data.daily);
    } catch (error) {
      if (meta) meta.textContent = error.message;
      if (body) renderSharedTableBody(body, [
        { key: 'stat_date', label: '日期' },
        { key: 'item_count', label: '商品数', numeric: true, render: fmtInt },
        { key: 'uv', label: 'UV', numeric: true, render: fmtWan },
        { key: 'pay_buyer_count', label: '支付买家', numeric: true, render: fmtWan },
        { key: 'pay_rate', label: '支付转化率', numeric: true, render: fmtPct },
      ], [], '暂无趋势数据');
    }
  }

  async function loadMarketItemTrend(itemId) {
    const meta = $('[data-market-item-meta]');
    const body = $('[data-market-item-body]');
    if (!itemId) { if (meta) meta.textContent = '暂无可用单品趋势数据。'; return; }
    try {
      const response = await fetch(`/api/sycm/market/items/entity-trend?item_id=${encodeURIComponent(itemId)}&${entityRangeParams()}`);
      const result = await response.json();
      if (!result.ok) throw new Error(result.message || '暂无数据');
      const data = result.data;
      renderEntityChart($('[data-market-item-chart]'), data.daily, [
        { name: 'UV', data: data.daily.map(row => row.uv == null ? null : Number(row.uv)), itemStyle: { color: '#2563eb' } },
        { name: '支付买家', data: data.daily.map(row => row.pay_buyer_count == null ? null : Number(row.pay_buyer_count)), itemStyle: { color: '#059669' } },
        { name: '支付转化率', yAxisIndex: 1, data: data.daily.map(row => row.pay_rate == null ? null : Number(row.pay_rate) * 100), itemStyle: { color: '#d97706' } },
      ]);
      if (meta) meta.textContent = `${data.entity_name || itemId} · ${data.shop_name || '未知店铺'} · 覆盖 ${data.observed_days}/${data.expected_days || '--'} 天${data.trend_comparable ? '，可观察区间变化' : '，覆盖不足不下趋势结论'}`;
      if (body) renderSharedTableBody(body, [
        { key: 'stat_date', label: '日期' },
        { key: 'uv', label: 'UV', numeric: true, render: fmtWan },
        { key: 'pay_buyer_count', label: '支付买家', numeric: true, render: fmtWan },
        { key: 'pay_rate', label: '支付转化率', numeric: true, render: fmtPct },
        { key: 'rank', label: '排名', numeric: true, render: fmtInt },
      ], data.daily);
    } catch (error) {
      if (meta) meta.textContent = error.message;
      if (body) renderSharedTableBody(body, [
        { key: 'stat_date', label: '日期' },
        { key: 'uv', label: 'UV', numeric: true, render: fmtWan },
        { key: 'pay_buyer_count', label: '支付买家', numeric: true, render: fmtWan },
        { key: 'pay_rate', label: '支付转化率', numeric: true, render: fmtPct },
        { key: 'rank', label: '排名', numeric: true, render: fmtInt },
      ], [], '暂无趋势数据');
    }
  }

  function bindMarketEntityFilters() {
    const shopSelect = $('[data-market-shop-select]');
    const itemSelect = $('[data-market-item-select]');
    if (shopSelect && !shopSelect.dataset.bound) {
      shopSelect.dataset.bound = '1';
      shopSelect.addEventListener('change', event => { state.selectedMarketShop = event.target.value; loadMarketShopTrend(event.target.value); });
    }
    if (itemSelect && !itemSelect.dataset.bound) {
      itemSelect.dataset.bound = '1';
      itemSelect.addEventListener('change', event => { state.selectedMarketItem = event.target.value; loadMarketItemTrend(event.target.value); });
    }
  }

  function renderMarketSnapshot(type) {
    const meta = $('[data-market-snapshot-meta]');
    const body = $('[data-market-snapshot-body]');
    const chartNode = $('[data-market-snapshot-chart]');
    const comparison = state.marketSnapshots?.comparisons?.[type];
    const columns = [
      { key: 'entity_name', label: '店铺 / 单品 / 关键词', render: (value, row) => value || row.entity_id || '--' },
      { key: 'previous_metric', label: '前期估算', numeric: true, render: fmtWan },
      { key: 'current_metric', label: '本期估算', numeric: true, render: fmtWan },
      { key: 'delta_rate', label: '变化', numeric: true, render: value => value == null ? '--' : `${value >= 0 ? '+' : ''}${(value * 100).toFixed(1)}%` },
    ];
    if (!comparison || comparison.status !== 'comparable') {
      if (meta) meta.textContent = '该榜单目前只有一个可比较周期。';
      if (body) renderSharedTableBody(body, columns, [], '暂无可比较周期');
      if (chartNode && typeof echarts !== 'undefined' && echarts.getInstanceByDom(chartNode)) {
        echarts.getInstanceByDom(chartNode).clear();
      }
      return;
    }
    const labels = {
      item: '市场商品榜（30天与7天区间，不是周环比）',
      search: '搜索词榜（30天与7天区间，不是周环比）',
      rival_item: '竞品周榜',
      rival_shop: '竞店周榜',
    };
    if (meta) meta.textContent = `${labels[type]} · ${comparison.previous_period.start}~${comparison.previous_period.end} → ${comparison.current_period.start}~${comparison.current_period.end} · 同榜实体 ${comparison.shared_entity_count} 个 · 指标按区间中点估算`;
    const rows = comparison.rows || [];
    if (body) renderSharedTableBody(body, columns, rows, '没有跨周期重复实体');
    if (chartNode && typeof echarts !== 'undefined') {
      const chart = echarts.getInstanceByDom(chartNode) || echarts.init(chartNode);
      const plot = rows.slice(0, 12);
      chart.setOption({
        tooltip: { trigger: 'axis' },
        legend: { bottom: 0 },
        grid: { left: '4%', right: '5%', top: '8%', bottom: '22%', containLabel: true },
        xAxis: { type: 'category', data: plot.map(row => row.entity_name || row.entity_id), axisLabel: { interval: 0, rotate: 25 } },
        yAxis: { type: 'value' },
        series: [
          { name: '前期估算', type: 'bar', data: plot.map(row => row.previous_metric) },
          { name: '本期估算', type: 'bar', data: plot.map(row => row.current_metric) },
        ],
      }, true);
      registerChart(chart);
    }
  }

  async function loadMarketSnapshots() {
    const response = await fetch('/api/sycm/market/snapshots');
    const result = await response.json();
    state.marketSnapshots = result.ok ? result.data : null;
    const selector = $('[data-market-snapshot-type]');
    if (selector && !selector.dataset.bound) {
      selector.dataset.bound = '1';
      selector.addEventListener('change', event => {
        state.selectedSnapshotType = event.target.value;
        renderMarketSnapshot(event.target.value);
      });
    }
    renderMarketSnapshot(state.selectedSnapshotType);
  }

  function setMarketView(target) {
    $$('[data-market-tab]').forEach(tab => {
      const active = tab.dataset.marketTab === target;
      tab.classList.toggle('is-active', active);
      tab.setAttribute('aria-selected', String(active));
    });
    $$('[data-market-panel]').forEach(panel => { panel.hidden = panel.dataset.marketPanel !== target; });
    $$('[data-market-entry]').forEach(entry => {
      const active = entry.dataset.marketEntry === target;
      entry.classList.toggle('is-active', active);
      entry.setAttribute('aria-pressed', String(active));
    });
    window.lucide?.createIcons();
  }

  function bindWorkbench() {
    $$('[data-market-tab]').forEach(tab => tab.addEventListener('click', () => setMarketView(tab.dataset.marketTab)));
    $$('[data-market-entry]').forEach(entry => entry.addEventListener('click', () => setMarketView(entry.dataset.marketEntry)));
    setMarketView('overview');
  }

  // ===== 渲染类目对比 =====
  function renderCategoryComparison(categories) {
    // 类目配色按数据顺序分配，不在前端写死任何具体类目名。
    const COLORS = ['#4f46e5', '#10b981', '#9ca3af', '#3b82f6', '#f59e0b'];
    const TEXT_COLORS = ['var(--brand-text)', 'var(--success-text)', 'var(--text-secondary)', 'var(--info-text)', 'var(--warning-text)'];
    const catColor = (i) => COLORS[i % COLORS.length];
    const catTextColor = (i) => TEXT_COLORS[i % TEXT_COLORS.length];
    // 图表填充 / 柱条继续用原色；**文字**用深一档的 --*-text（原色当文字过不了 WCAG AA：success 2.54:1）。

    // 店铺类型分布
    let shopHtml = '';
    categories.forEach((cat, catIndex) => {
      const total = cat.shop_tmall + cat.shop_taobao;
      const tmallPct = total ? (cat.shop_tmall / total * 100) : 0;
      shopHtml += `
        <div style="margin-bottom:12px">
          <div style="display:flex;justify-content:space-between;font-size:12px;margin-bottom:4px">
            <span style="font-weight:600;color:${catTextColor(catIndex)}">${escapeHtml(cat.category)}</span>
            <span style="color:var(--text-secondary)">天猫 ${tmallPct.toFixed(1)}% / 淘宝 ${(100-tmallPct).toFixed(1)}%</span>
          </div>
          <div style="display:flex;height:20px;border-radius:4px;overflow:hidden">
            <div style="width:${tmallPct}%;background:#3b82f6"></div>
            <div style="width:${100-tmallPct}%;background:#f59e0b"></div>
          </div>
          <div style="display:flex;justify-content:space-between;font-size:11px;color:var(--text-secondary);margin-top:2px">
            <span>天猫 ${fmtInt(cat.shop_tmall)}</span>
            <span>淘宝 ${fmtInt(cat.shop_taobao)}</span>
          </div>
        </div>`;
    });
    const shopTypeNode = $('[data-mr-shop-type]');
    if (shopTypeNode) shopTypeNode.innerHTML = shopHtml;

    // 排名趋势
    const trendLabels = ['上升', '下降', '持平', '新上榜', '跌出榜'];
    const trendKeys = ['trend_up', 'trend_down', 'trend_flat', 'trend_new', 'trend_out'];
    const trendColors = ['#10b981', '#ef4444', '#9ca3af', '#3b82f6', '#f59e0b'];
    let trendHtml = '';
    categories.forEach((cat, catIndex) => {
      trendHtml += `<div style="margin-bottom:8px"><span style="font-weight:600;font-size:12px;color:${catColor(catIndex)}">${escapeHtml(cat.category)}</span></div>`;
      trendLabels.forEach((label, i) => {
        const val = cat[trendKeys[i]] || 0;
        const maxVal = Math.max(...categories.map(c => c[trendKeys[i]] || 0), 1);
        const pct = (val / maxVal * 100);
        trendHtml += `
          <div class="market-bar-row">
            <span class="market-bar-label">${label}</span>
            <div class="market-bar-track"><div class="market-bar-fill" style="width:${pct}%;background:${trendColors[i]}"></div></div>
            <span class="market-bar-value">${fmtInt(val)}</span>
          </div>`;
      });
      trendHtml += '<div style="height:8px"></div>';
    });
    const trendNode = $('[data-mr-trend]');
    if (trendNode) trendNode.innerHTML = trendHtml;

    // 集中度
    let concHtml = '';
    categories.forEach((cat, catIndex) => {
      concHtml += `
        <div style="margin-bottom:16px">
          <div style="font-weight:600;font-size:12px;color:${catTextColor(catIndex)};margin-bottom:6px">${escapeHtml(cat.category)}</div>
          <div class="market-bar-row">
            <span class="market-bar-label">TOP10</span>
            <div class="market-bar-track"><div class="market-bar-fill" style="width:${cat.concentration_top10 || 0}%;background:#4f46e5"></div></div>
            <span class="market-bar-value">${fmtPct(cat.concentration_top10 / 100)}</span>
          </div>
          <div class="market-bar-row">
            <span class="market-bar-label">TOP50</span>
            <div class="market-bar-track"><div class="market-bar-fill" style="width:${cat.concentration_top50 || 0}%;background:#818cf8"></div></div>
            <span class="market-bar-value">${fmtPct(cat.concentration_top50 / 100)}</span>
          </div>
        </div>`;
    });
    const concentrationNode = $('[data-mr-concentration]');
    if (concentrationNode) concentrationNode.innerHTML = concHtml;

    // 总买家数
    let totalHtml = '';
    const maxTotal = Math.max(...categories.map(c => c.total_buyers || 0), 1);
    categories.forEach((cat, catIndex) => {
      const pct = (cat.total_buyers / maxTotal * 100);
      totalHtml += `
        <div style="margin-bottom:16px">
          <div style="display:flex;justify-content:space-between;margin-bottom:4px">
            <span style="font-weight:600;font-size:13px;color:${catTextColor(catIndex)}">${escapeHtml(cat.category)}</span>
            <span style="font-family:var(--font-display);font-size:18px;font-weight:700">${fmtWan(cat.total_buyers)}</span>
          </div>
          <div style="height:24px;background:var(--surface-base);border-radius:4px;overflow:hidden">
            <div style="width:${pct}%;height:100%;background:${catColor(catIndex)};border-radius:4px"></div>
          </div>
        </div>`;
    });
    const totalBuyersNode = $('[data-mr-total-buyers]');
    if (totalBuyersNode) totalBuyersNode.innerHTML = totalHtml;
  }

  // ===== 渲染筛选器 =====
  function renderFilters() {
    const catSel = $('[data-mr-filter-category]');
    catSel.innerHTML = '<option value="">全部类目</option>' +
      state.categories.map(c => `<option value="${escapeHtml(c)}">${escapeHtml(c)}</option>`).join('');

    const listSel = $('[data-mr-filter-list-type]');
    listSel.innerHTML = '<option value="">全部榜单</option>' +
      state.listTypes.map(t => `<option value="${escapeHtml(t)}">${escapeHtml(t)}</option>`).join('');

    const kwCatSel = $('[data-mr-kw-category]');
    kwCatSel.innerHTML = '<option value="">全部类目</option>' +
      state.categories.map(c => `<option value="${escapeHtml(c)}">${escapeHtml(c)}</option>`).join('');

    const kwTypeSel = $('[data-mr-kw-type]');
    kwTypeSel.innerHTML = '<option value="">全部类型</option>' +
      state.keywordTypes.map(t => `<option value="${escapeHtml(t)}">${escapeHtml(t)}</option>`).join('');
  }

  // ===== 渲染商品榜单 =====
  function renderProducts(products) {
    const tbody = $('[data-mr-products-body]');
    const badge = (label, tone) => window.TmallUI?.badge
      ? window.TmallUI.badge(label || '-', tone)
      : document.createTextNode(label || '-');
    const rank = (value) => badge(value, value <= 3 ? (value === 1 ? 'danger' : value === 2 ? 'warning' : 'success') : 'muted');
    const change = (value, row) => {
      const node = document.createElement('span');
      node.style.fontFamily = 'var(--font-mono)';
      node.style.color = row.list_type === '下降榜' ? 'var(--text-secondary)' : 'var(--success-text)';
      node.textContent = value == null ? '-' : `${row.list_type === '下降榜' ? '↓' : '↑'}${Math.abs(value)}`;
      return node;
    };
    renderSharedTableBody(tbody, [
      { key: 'rank', label: '排名', numeric: true, render: rank },
      { key: 'category', label: '类目', render: value => badge(value, 'info') },
      { key: 'list_type', label: '榜单', render: value => badge(value, 'muted') },
      { key: 'title', label: '商品标题', render: value => value || '-' },
      { key: 'shop', label: '店铺', render: value => value || '-' },
      { key: 'rank_change', label: '变化', render: change },
      { key: 'buyers', label: '买家数', numeric: true, render: fmtInt },
      { key: 'visitors', label: '访客数', numeric: true, render: fmtInt },
    ], products, '没有符合条件的数据');
  }

  // ===== 渲染关键词 =====
  function renderKeywords(keywords) {
    const searchKw = keywords.filter(k => k.keyword_type === '搜索词').slice(0, 15);
    const titleKw = keywords.filter(k => k.keyword_type === '标题词').slice(0, 15);

    const renderBarList = (list, color) => {
      if (!list.length) return '<div class="ui-empty-state"><span>暂无数据</span></div>';
      const max = Math.max(...list.map(k => k.count), 1);
      return list.map(k => `
        <div class="market-bar-row">
            <span class="market-bar-label" style="width:70px">${escapeHtml(k.keyword)}</span>

          <div class="market-bar-track"><div class="market-bar-fill" style="width:${k.count / max * 100}%;background:${color}"></div></div>
          <span class="market-bar-value" style="width:40px">${fmtInt(k.count)}</span>
        </div>`).join('');
    };

    $('[data-mr-search-kw]').innerHTML = renderBarList(searchKw, '#4f46e5');
    $('[data-mr-title-kw]').innerHTML = renderBarList(titleKw, '#10b981');
  }

  // ===== 渲染重叠店铺 =====
  function renderOverlapShops(shops) {
    const container = $('[data-mr-overlap-list]');
    if (!shops.length) {
      container.innerHTML = '<span style="color:var(--text-secondary)">暂无重叠店铺</span>';
      return;
    }
    container.innerHTML = shops.map(s => `<span class="market-overlap-tag">${escapeHtml(s)}</span>`).join('');
  }

  // ===== 事件绑定 =====
  function bindEvents() {
    $('[data-mr-filter-category]').addEventListener('change', e => {
      state.filterCategory = e.target.value;
      loadProducts().then(renderProducts);
    });
    $('[data-mr-filter-list-type]').addEventListener('change', e => {
      state.filterListType = e.target.value;
      loadProducts().then(renderProducts);
    });
    $('[data-mr-kw-category]').addEventListener('change', e => {
      state.kwCategory = e.target.value;
      loadKeywords().then(renderKeywords);
    });
    $('[data-mr-kw-type]').addEventListener('change', e => {
      state.kwType = e.target.value;
      loadKeywords().then(renderKeywords);
    });
  }

  // ===== 初始化 =====

  // ===== 生意参谋数据 =====
  async function loadSycmCategories() {
    try {
      const r = await fetch(withSycmDate('/api/sycm/market/categories'));
      const d = await r.json();
      if (d.ok && d.data.categories) {
        $$('[data-sycm-date]').forEach((el) => { el.textContent = `数据日期 ${d.data.stat_date || selectedDate() || '--'}`; });
        const selects = document.querySelectorAll('[data-sycm-cate-filter], [data-sycm-kw-cate-filter]');
        selects.forEach(sel => {
          const currentValue = sel.value;
          sel.innerHTML = '<option value="">全部类目</option>';
          d.data.categories.forEach(cat => {
            const opt = document.createElement('option');
            opt.value = cat.cate_name;
            opt.textContent = cat.cate_name;
            sel.appendChild(opt);
          });
          if ([...sel.options].some(option => option.value === currentValue)) sel.value = currentValue;
        });
      }
    } catch (e) {
      console.error('加载生意参谋类目失败:', e);
    }
  }

  async function loadSycmItemRank(cateName = '') {
    try {
      let url = withSycmDate('/api/sycm/market/item-rank?limit=50');
      if (cateName) url += '&cate_name=' + encodeURIComponent(cateName);
      const r = await fetch(url);
      const d = await r.json();
      $$('[data-sycm-item-date]').forEach((el) => { el.textContent = `数据日期 ${d.data?.stat_date || selectedDate() || '--'}`; });
      const tbody = document.querySelector('[data-sycm-item-rank-body]');
      if (!tbody) return;
      const image = (value, item) => {
        if (!item.pic_url) {
          const placeholder = document.createElement('span');
          placeholder.className = 'sycm-item-rank-image-placeholder';
          placeholder.setAttribute('aria-hidden', 'true');
          placeholder.textContent = '暂无';
          return placeholder;
        }
        const img = document.createElement('img');
        img.loading = 'lazy';
        img.src = item.pic_url;
        img.alt = item.title || '商品图片';
        img.className = 'sycm-item-rank-image';
        img.addEventListener('error', () => { img.style.display = 'none'; }, { once: true });
        return img;
      };
      renderSharedTableBody(tbody, [
        { key: 'rank', label: '排名', numeric: true },
        { key: 'pic_url', label: '主图', render: image },
        { key: 'cate_name', label: '类目', render: value => value || '-' },
        { key: 'title', label: '商品标题', render: value => value || '-' },
        { key: 'shop_name', label: '店铺', render: value => value || '-' },
        { key: 'uv', label: '访客数', numeric: true, render: fmtWan },
        { key: 'pay_buyer_count', label: '支付买家', numeric: true, render: fmtWan },
        { key: 'core_keyword', label: '核心关键词', render: value => value || '-' },
      ], (d.ok ? (d.data.items || []) : []).map((item, index) => ({ ...item, rank: index + 1 })), '暂无数据');
    } catch (e) {
      console.error('加载生意参谋商品排行失败:', e);
    }
  }

  async function loadSycmSearchRank(cateName = '') {
    try {
      let url = withSycmDate('/api/sycm/market/search-rank?limit=50');
      if (cateName) url += '&cate_name=' + encodeURIComponent(cateName);
      const r = await fetch(url);
      const d = await r.json();
      $$('[data-sycm-search-date]').forEach((el) => { el.textContent = `数据日期 ${d.data?.stat_date || selectedDate() || '--'}`; });
      const tbody = document.querySelector('[data-sycm-search-rank-body]');
      if (!tbody) return;
      const keyword = value => {
        const node = document.createElement('strong');
        node.textContent = value || '-';
        return node;
      };
      renderSharedTableBody(tbody, [
        { key: 'rank', label: '排名', numeric: true },
        { key: 'cate_name', label: '类目', render: value => value || '-' },
        { key: 'keyword', label: '关键词', render: keyword },
        { key: 'search_heat', label: '搜索热度', numeric: true, render: fmtWan },
        { key: 'pay_rate', label: '支付转化率', numeric: true, render: fmtPct },
        { key: 'click_rate', label: '点击率', numeric: true, render: fmtPct },
        { key: 'free_click_rate', label: '免费点击占比', numeric: true, render: fmtPct },
      ], (d.ok ? (d.data.keywords || []) : []).map((item, index) => ({ ...item, rank: index + 1 })), '暂无数据');
    } catch (e) {
      console.error('加载生意参谋搜索排行失败:', e);
    }
  }

  // ===== 关键词洞察（8大归类 / 蓝海 / 趋势节点）与竞店爆品排名变化 =====
  // 对应后端 /api/sycm/market/keyword-insights 与 /api/sycm/market/rival-item-moves，
  // 补齐月复盘 XMind「市场监控」缺口：8大归类 / 词根需求 / 趋势节点 / 蓝海 / 竞店爆品。
  async function loadKeywordInsights() {
    try {
      const response = await fetch('/api/sycm/market/keyword-insights');
      const result = await response.json();
      renderKeywordInsights(result.ok ? result.data : null);
    } catch (e) {
      console.error('加载关键词洞察失败:', e);
      renderSharedTableBody(document.querySelector('[data-mr-kw-categories-body]'), [
        { key: 'label', label: '归类' },
        { key: 'keyword_count', label: '覆盖词数', numeric: true, render: fmtInt },
        { key: 'heat_share', label: '搜索热度占比', numeric: true, render: value => value == null ? '--' : `${(value * 100).toFixed(1)}%` },
        { key: 'top_keywords', label: '核心词根（热度 TOP3）' },
      ], [], '暂无数据');
      renderSharedTableBody(document.querySelector('[data-mr-blue-ocean-body]'), [
        { key: 'keyword', label: '关键词' },
        { key: 'search_heat', label: '搜索热度（近7天日均）', numeric: true, render: fmtInt },
        { key: 'pay_rate', label: '支付转化率', numeric: true, render: value => value == null ? '--' : `${(value * 100).toFixed(2)}%` },
        { key: 'score', label: '蓝海度', numeric: true, render: value => value == null ? '--' : Number(value).toFixed(3) },
        { key: 'grade', label: '供给分级' },
      ], [], '暂无数据');
    }
  }

  function renderKeywordInsights(data) {
    const meta = document.querySelector('[data-mr-kw-insights-meta]');
    if (meta) {
      meta.textContent = data && data.available
        ? `窗口 ${data.window.start} ~ ${data.window.end}（${data.window.day_count} 天）· 去重 ${data.unique_keyword_count} 词`
        : '暂无搜索榜数据（等待 sycm_market_search_rank 采集）';
    }
    const categoriesBody = document.querySelector('[data-mr-kw-categories-body]');
    const categoryColumns = [
      { key: 'label', label: '归类', render: value => {
        const cell = document.createElement('strong');
        cell.textContent = value || '--';
        return cell;
      } },
      { key: 'keyword_count', label: '覆盖词数', numeric: true, render: fmtInt },
      { key: 'heat_share', label: '搜索热度占比', numeric: true, render: value => value == null ? '--' : `${(value * 100).toFixed(1)}%` },
      { key: 'top_keywords', label: '核心词根（热度 TOP3）' },
    ];
    if (data && data.available && data.categories.length) {
      renderSharedTableBody(categoriesBody, categoryColumns, data.categories.map(cat => ({
        ...cat,
        top_keywords: cat.top_keywords.map(item => item.keyword).join('、'),
      })), '暂无数据');
    } else {
      renderSharedTableBody(categoriesBody, categoryColumns, [], '暂无数据');
    }
    const blueBody = document.querySelector('[data-mr-blue-ocean-body]');
    const blueColumns = [
      { key: 'keyword', label: '关键词' },
      { key: 'search_heat', label: '搜索热度（近7天日均）', numeric: true, render: fmtInt },
      { key: 'pay_rate', label: '支付转化率', numeric: true, render: value => value == null ? '--' : `${(value * 100).toFixed(2)}%` },
      { key: 'score', label: '蓝海度', numeric: true, render: value => value == null ? '--' : Number(value).toFixed(3) },
      { key: 'fullItem', label: '供给分级', numeric: true, render: (_, item) => {
        const fullItem = item.fullItem && item.fullItem.available !== false && item.fullItem.grade ? item.fullItem : null;
        const grade = fullItem ? fullItem.grade : '--';
        const coverText = fullItem ? `${fullItem.cover_count} 品 · ${fullItem.cover_per_10k}/万` : '--';
        const cell = document.createElement('span');
        cell.title = fullItem ? `词根「${fullItem.keyword}」每万搜索覆盖 ${fullItem.cover_per_10k}（在榜 ${fullItem.cover_count} 品含该词根）；代表搜索词：${fullItem.keyword_full || fullItem.keyword}` : '';
        const badge = document.createElement('span');
        badge.className = `ui-badge ${fullItem && fullItem.grade === '高潜蓝海' ? 'ui-badge--success' : 'ui-badge--muted'}`;
        badge.textContent = grade;
        const detail = document.createElement('small');
        detail.style.color = 'var(--text-secondary)';
        detail.textContent = coverText;
        cell.append(badge, document.createTextNode(' '), detail);
        return cell;
      } },
    ];
    if (data && data.available && data.blue_ocean.length) {
      // 完整口径（词根级每万覆盖）可用时以它为主行集；蓝海度/转化率从近似口径映射过来。
      // 两口径词集不同（近似=全量词、完整=细分词根），混排会出现主行无分级值的割裂。
      const full = data.blue_ocean_full || {};
      const approxMap = {};
      data.blue_ocean.forEach(item => { approxMap[item.keyword] = item; });
      const rowsSource = (full.available && full.words.length)
        ? full.words.map(item => ({
          keyword: item.keyword,
          search_heat: item.search_heat,
          pay_rate: item.pay_rate,
          score: (approxMap[item.keyword_full] || approxMap[item.keyword] || {}).score,
          fullItem: item,
        }))
        : data.blue_ocean.map(item => ({ ...item, fullItem: null }));
      renderSharedTableBody(blueBody, blueColumns, rowsSource, '暂无数据');
      const blueHint = document.querySelector('[data-mr-blue-ocean-hint]');
      if (blueHint) {
        blueHint.textContent = full && full.available
          ? `按每万搜索覆盖排序；${full.word_scope || ''}；覆盖=最新日在榜商品 title 含词根数，<5 高潜 / 5-10 中等 / >10 供给偏多；覆盖为 0 记「待核」（0 不代表供给稀缺，也可能是词根与标题用词不一致）`
          : '近 7 天日均搜索热度 × 支付转化率，剔除泛词；「每万供给覆盖」需在榜商品数据，缺失时仅按蓝海度排序';
      }
    } else {
      renderSharedTableBody(blueBody, blueColumns, [], '暂无数据');
    }
    const renderTrend = (selector, rows) => {
      const node = document.querySelector(selector);
      if (!node || !window.TmallUI?.table?.mount) return;
      window.TmallUI.table.mount(node, {
        columns: [
          { key: 'keyword', label: '关键词' },
          { key: 'recent_heat', label: '近7天', numeric: true, render: fmtInt },
          { key: 'baseline_heat', label: '前期', numeric: true, render: fmtInt },
          {
            key: 'growth', label: '增速', numeric: true,
            render: (value) => {
              const change = Number(value) || 0;
              const cell = document.createElement('span');
              cell.style.color = change > 0 ? 'var(--success-text)' : 'var(--danger-text)';
              cell.textContent = `${change > 0 ? '+' : ''}${(change * 100).toFixed(0)}%`;
              return cell;
            },
          },
        ],
        rows: data && data.available ? rows : [],
      });
    };
    const nodes = (data && data.available && data.trend_nodes) || {};
    renderTrend('[data-mr-rising-body]', nodes.rising || []);
    renderTrend('[data-mr-cooling-body]', nodes.cooling || []);
  }

  async function loadRivalItemMoves() {
    try {
      const response = await fetch('/api/sycm/market/rival-item-moves');
      const result = await response.json();
      renderRivalItemMoves(result.ok ? result.data : null);
    } catch (e) {
      console.error('加载竞店爆品变动失败:', e);
      const body = document.querySelector('[data-mr-rival-moves-body]');
      if (body) body.innerHTML = '<div class="market-list-empty">读取失败，请稍后重试</div>';
    }
  }

  function renderRivalItemMoves(data) {
    const meta = document.querySelector('[data-mr-rival-moves-meta]');
    const body = document.querySelector('[data-mr-rival-moves-body]');
    if (!meta || !body) return;
    if (!data || !data.available || !data.shops.length) {
      meta.textContent = '暂无商品榜数据（等待 sycm_market_item_rank 采集）';
      body.innerHTML = '<div class="market-list-empty">暂无数据</div>';
      return;
    }
    meta.textContent = `共 ${data.shop_count} 家店在榜，展示变动最活跃的 ${data.shops.length} 家`;
    const fmtRank = (value) => (value === null || value === undefined ? '--' : `#${value}`);
    // 每店窗口内**全部**在榜商品都要列出（不再截断），四类变动 + 持平各自带类型标签；
    // 排序沿用后端 movers 的绝对变动幅度，其后按排名接持平商品。
    const rowsOfShop = (shop) => {
      const decorate = (entry, kind, change, changeText) => ({ ...entry, _kind: kind, _change: change, _changeText: changeText });
      const rows = [];
      (shop.rising || []).forEach(entry => rows.push(decorate(entry, '上升', entry.rank_change, `${entry.rank_change > 0 ? '+' : ''}${entry.rank_change}`)));
      (shop.falling || []).forEach(entry => rows.push(decorate(entry, '下降', entry.rank_change, String(entry.rank_change))));
      (shop.new_items || []).forEach(entry => rows.push(decorate(entry, '新进榜', null, '新进榜')));
      (shop.exit_items || []).forEach(entry => rows.push(decorate(entry, '退出', null, '退出')));
      (shop.stable || []).forEach(entry => rows.push(decorate(entry, '持平', 0, '0')));
      rows.sort((first, second) => {
        const magnitude = (row) => (row._change === null || row._change === undefined ? -1 : Math.abs(row._change));
        return magnitude(second) - magnitude(first);
      });
      return rows;
    };
    const thumbnail = (_, item) => {
      const wrap = document.createElement('span');
      wrap.className = 'market-rival-thumb';
      const url = safeHttpUrl(item.pic_url);
      if (!url) {
        wrap.textContent = '图';
        wrap.setAttribute('aria-hidden', 'true');
        return wrap;
      }
      const img = document.createElement('img');
      img.loading = 'lazy';
      img.src = url;
      img.alt = item.title ? `${item.title} 主图` : '商品主图';
      img.addEventListener('error', () => {
        wrap.textContent = '图';
        wrap.setAttribute('aria-hidden', 'true');
      }, { once: true });
      wrap.append(img);
      return wrap;
    };
    body.innerHTML = data.shops.map(shop => {
      const rows = rowsOfShop(shop);
      const counts = `↑${shop.rising_count} ↓${shop.falling_count} 新进榜 ${shop.new_count} 退出 ${shop.exit_count} 持平 ${shop.unchanged_count ?? 0}`;
      const table = rows.length ? window.TmallUI.table({
        tableClass: 'market-entity-table',
        wrapClass: 'market-entity-table-wrap',
        columns: [
          { key: 'pic_url', label: '主图', render: thumbnail },
          {
            key: 'title', label: '商品',
            render: (value) => {
              const cell = document.createElement('span');
              cell.className = 'market-rival-title';
              cell.title = String(value || '');
              cell.textContent = value || '--';
              return cell;
            },
          },
          {
            key: '_kind', label: '变动',
            render: (value) => {
              const cell = document.createElement('span');
              cell.className = value === '上升' ? 'market-rival-change--up'
                : value === '下降' ? 'market-rival-change--down' : '';
              cell.textContent = value || '--';
              return cell;
            },
          },
          {
            key: '_change', label: '排名变化', numeric: true,
            render: (value, item) => {
              const cell = document.createElement('span');
              if (value === null || value === undefined) {
                cell.textContent = item._changeText || '--';
                return cell;
              }
              const change = Number(value) || 0;
              cell.className = change > 0 ? 'market-rival-change--up' : change < 0 ? 'market-rival-change--down' : '';
              cell.textContent = `${change > 0 ? '+' : ''}${change}`;
              cell.dataset.sortValue = String(change);
              return cell;
            },
          },
          {
            key: 'first_rank', label: '首日→末日', numeric: true,
            render: (_, item) => {
              if (item._kind === '新进榜') return `-- → ${fmtRank(item.rank)}`;
              if (item._kind === '退出') return `${fmtRank(item.rank)} → --`;
              return `${fmtRank(item.first_rank)} → ${fmtRank(item.last_rank)}`;
            },
          },
          { key: 'uv', label: '访客数', numeric: true, render: fmtInt },
          { key: 'pay_buyer_count', label: '支付买家', numeric: true, render: fmtInt },
        ],
        rows,
      }).outerHTML : '<div class="market-list-empty">该店窗口内无在榜商品变动</div>';
      return `
        <details class="market-rival-shop">
          <summary>
            ${escapeHtml(shop.shop_name)}
            <span class="market-rival-shop__summary-meta">${counts} · 在榜 ${shop.item_count} 品 · 列出 ${rows.length} 条（${shop.window.start} ~ ${shop.window.end}）</span>
          </summary>
          <div class="market-rival-shop__body">${table}</div>
        </details>`;
    }).join('');
  }

  function bindSycmFilters() {
    setTimeout(() => {
      const cateFilter = document.querySelector('[data-sycm-cate-filter]');
      if (cateFilter) {
        cateFilter.addEventListener('change', e => loadSycmItemRank(e.target.value));
      }
      const kwCateFilter = document.querySelector('[data-sycm-kw-cate-filter]');
      if (kwCateFilter) {
        kwCateFilter.addEventListener('change', e => loadSycmSearchRank(e.target.value));
      }
    }, 500);
  }

async function init() {
    try {
      const [summary, filters] = await Promise.all([loadSummary(), loadFilters(), loadMarketTrend()]);
      renderMetrics(summary);
      renderCommandSummary(summary);
      renderCategoryComparison(summary.categories);
      renderFilters();
      if (!initialized) {
        bindEvents();
        bindWorkbench();
      }

      const [products, keywords, overlapShops] = await Promise.all([
        loadProducts(), loadKeywords(), loadOverlapShops()
      ]);
      renderProducts(products);
      renderKeywords(keywords);
      renderOverlapShops(overlapShops);

      // 生意参谋证据跟随顶部统计日刷新，避免与主分析日期混用。
      await Promise.all([loadSycmCategories(), loadSycmItemRank(), loadSycmSearchRank()]);
      if (!initialized) {
        bindSycmFilters();
        bindMarketEntityFilters();
        bindMarketEntityLists();
        initialized = true;
      }

      await loadMarketEntities();
      await loadMarketSnapshots();
      // 关键词洞察与竞店爆品变动（XMind 市场监控缺口补齐）。
      await Promise.all([loadKeywordInsights(), loadRivalItemMoves()]);

      initMarketTrendDrawer();
      window.lucide?.createIcons();
    } catch (e) {
      console.error('市场分析加载失败:', e);
      // 4-3：整页错误态走共享渲染器（原手拼 div 还在用已废弃的 var(--danger)）。
      DemoApi.renderDataState(document.querySelector('.demo-page'), 'source-unavailable',
        { message: `市场分析加载失败：${e.message}`, retry: () => window.location.reload() });
}

  }

  window.addEventListener('tmall:date-range-change', () => {
    state.marketModalRequest += 1;
    closeMarketTrendModal();
    init();
  });

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else { init(); }
})();
