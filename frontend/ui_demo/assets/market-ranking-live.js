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
      echarts.init(productNode).setOption({
        tooltip: { trigger: 'axis' },
        grid: { left: '4%', right: '4%', bottom: '12%', containLabel: true },
        xAxis: { type: 'category', data: labels },
        yAxis: { type: 'value' },
        series: [{ type: 'line', smooth: true, connectNulls: false, data: rankedBuyers, name: '榜内商品日均支付买家', itemStyle: { color: '#2563eb' } }],
      });
      echarts.init(searchNode).setOption({
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
    const head = $('[data-market-modal-head]');
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
      if (head) head.innerHTML = kind === 'shop' ? '<th>日期</th><th>商品数</th><th>UV</th><th>支付买家</th><th>支付转化率</th>' : '<th>日期</th><th>UV</th><th>支付买家</th><th>支付转化率</th><th>排名</th>';
      if (body) body.innerHTML = data.daily.map(row => kind === 'shop'
        ? `<tr><td>${escapeHtml(row.stat_date)}</td><td class="num">${fmtInt(row.item_count)}</td><td class="num">${fmtWan(row.uv)}</td><td class="num">${fmtWan(row.pay_buyer_count)}</td><td class="num">${fmtPct(row.pay_rate)}</td></tr>`
        : `<tr><td>${escapeHtml(row.stat_date)}</td><td class="num">${fmtWan(row.uv)}</td><td class="num">${fmtWan(row.pay_buyer_count)}</td><td class="num">${fmtPct(row.pay_rate)}</td><td class="num">${fmtInt(row.rank)}</td></tr>`).join('');
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
      if (body) body.innerHTML = '<tr><td colspan="5" style="text-align:center;padding:18px;color:var(--text-secondary)">暂无趋势数据</td></tr>';
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
      if (body) body.innerHTML = data.daily.map(row => `<tr><td>${escapeHtml(row.stat_date)}</td><td class="num">${fmtInt(row.item_count)}</td><td class="num">${fmtWan(row.uv)}</td><td class="num">${fmtWan(row.pay_buyer_count)}</td><td class="num">${fmtPct(row.pay_rate)}</td></tr>`).join('');
    } catch (error) {
      if (meta) meta.textContent = error.message;
      if (body) body.innerHTML = '<tr><td colspan="5" style="text-align:center;color:var(--text-secondary);padding:18px">暂无趋势数据</td></tr>';
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
      if (body) body.innerHTML = data.daily.map(row => `<tr><td>${escapeHtml(row.stat_date)}</td><td class="num">${fmtWan(row.uv)}</td><td class="num">${fmtWan(row.pay_buyer_count)}</td><td class="num">${fmtPct(row.pay_rate)}</td><td class="num">${fmtInt(row.rank)}</td></tr>`).join('');
    } catch (error) {
      if (meta) meta.textContent = error.message;
      if (body) body.innerHTML = '<tr><td colspan="5" style="text-align:center;color:var(--text-secondary);padding:18px">暂无趋势数据</td></tr>';
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
    if (!comparison || comparison.status !== 'comparable') {
      if (meta) meta.textContent = '该榜单目前只有一个可比较周期。';
      if (body) body.innerHTML = '<tr><td colspan="4" style="text-align:center;color:var(--text-secondary);padding:18px">暂无可比较周期</td></tr>';
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
    if (body) body.innerHTML = rows.map(row => `<tr><td>${escapeHtml(row.entity_name || row.entity_id)}</td><td class="num">${fmtWan(row.previous_metric)}</td><td class="num">${fmtWan(row.current_metric)}</td><td class="num">${row.delta_rate == null ? '--' : `${row.delta_rate >= 0 ? '+' : ''}${(row.delta_rate * 100).toFixed(1)}%`}</td></tr>`).join('') || '<tr><td colspan="4" style="text-align:center;color:var(--text-secondary);padding:18px">没有跨周期重复实体</td></tr>';
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
    const COLORS = { '中筒袜': '#4f46e5', '长筒袜': '#10b981' };
    // 图表填充 / 柱条继续用原色；**文字**用深一档的 --*-text（原色当文字过不了 WCAG AA：success 2.54:1）。
    const TEXT_COLORS = { '中筒袜': 'var(--brand-text)', '长筒袜': 'var(--success-text)' };

    // 店铺类型分布
    let shopHtml = '';
    categories.forEach(cat => {
      const total = cat.shop_tmall + cat.shop_taobao;
      const tmallPct = total ? (cat.shop_tmall / total * 100) : 0;
      shopHtml += `
        <div style="margin-bottom:12px">
          <div style="display:flex;justify-content:space-between;font-size:12px;margin-bottom:4px">
            <span style="font-weight:600;color:${TEXT_COLORS[cat.category] || 'var(--text-secondary)'}">${escapeHtml(cat.category)}</span>
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
    categories.forEach(cat => {
      trendHtml += `<div style="margin-bottom:8px"><span style="font-weight:600;font-size:12px;color:${COLORS[cat.category]}">${escapeHtml(cat.category)}</span></div>`;
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
    categories.forEach(cat => {
      concHtml += `
        <div style="margin-bottom:16px">
          <div style="font-weight:600;font-size:12px;color:${TEXT_COLORS[cat.category]};margin-bottom:6px">${escapeHtml(cat.category)}</div>
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
    categories.forEach(cat => {
      const pct = (cat.total_buyers / maxTotal * 100);
      totalHtml += `
        <div style="margin-bottom:16px">
          <div style="display:flex;justify-content:space-between;margin-bottom:4px">
            <span style="font-weight:600;font-size:13px;color:${TEXT_COLORS[cat.category]}">${escapeHtml(cat.category)}</span>
            <span style="font-family:var(--font-display);font-size:18px;font-weight:700">${fmtWan(cat.total_buyers)}</span>
          </div>
          <div style="height:24px;background:var(--surface-base);border-radius:4px;overflow:hidden">
            <div style="width:${pct}%;height:100%;background:${COLORS[cat.category]};border-radius:4px"></div>
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
    if (!products.length) {
      tbody.innerHTML = '<tr><td colspan="8" style="text-align:center;color:var(--text-secondary);padding:24px">没有符合条件的数据</td></tr>';
      return;
    }
    tbody.innerHTML = products.map(p => {
      const rankBadge = p.rank <= 3
        ? `<span class="ui-badge ui-badge--${p.rank === 1 ? 'danger' : p.rank === 2 ? 'warning' : 'success'}">${p.rank}</span>`
        : `<span class="ui-badge ui-badge--muted">${p.rank}</span>`;
      const changeBadge = p.rank_change == null
        ? '<span style="color:var(--text-secondary)">-</span>'
        : `<span style="font-family:var(--font-mono);color:var(${p.list_type === '下降榜' ? '--text-secondary' : '--success-text'})">${p.list_type === '下降榜' ? '↓' : '↑'}${Math.abs(p.rank_change)}</span>`;
      return `<tr>
        <td>${rankBadge}</td>
        <td><span class="ui-badge ui-badge--info">${escapeHtml(p.category)}</span></td>
        <td><span class="ui-badge ui-badge--muted">${escapeHtml(p.list_type)}</span></td>
        <td style="max-width:300px">${escapeHtml(p.title || '-')}</td>
        <td style="color:var(--text-secondary)">${escapeHtml(p.shop || '-')}</td>
        <td>${changeBadge}</td>
        <td style="font-family:var(--font-mono)">${fmtInt(p.buyers)}</td>
        <td style="font-family:var(--font-mono)">${fmtInt(p.visitors)}</td>
      </tr>`;
    }).join('');
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
      if (!d.ok || !d.data.items.length) {
        tbody.innerHTML = '<tr><td colspan="8" style="text-align:center;color:var(--text-secondary);padding:24px">暂无数据</td></tr>';
        return;
      }
      tbody.innerHTML = d.data.items.map((item, idx) => {
        const img = item.pic_url
          ? `<img loading="lazy" src="${escapeHtml(item.pic_url)}" alt="${escapeHtml(item.title || '商品图片')}" class="sycm-item-rank-image" onerror="this.style.display='none'">`
          : '<span class="sycm-item-rank-image-placeholder" aria-hidden="true">暂无</span>';
        return `<tr>
          <td>${idx + 1}</td>
          <td>${img}</td>
          <td><span class="sycm-item-rank-category">${escapeHtml(item.cate_name || '-')}</span></td>
          <td class="sycm-item-rank-title" title="${escapeHtml(item.title || '-')}" >${escapeHtml(item.title || '-')}</td>
          <td class="sycm-item-rank-shop" title="${escapeHtml(item.shop_name || '-')}" >${escapeHtml(item.shop_name || '-')}</td>
          <td class="num">${fmtWan(item.uv)}</td>
          <td class="num">${fmtWan(item.pay_buyer_count)}</td>
          <td class="sycm-item-rank-keyword" title="${escapeHtml(item.core_keyword || '-')}" >${escapeHtml(item.core_keyword || '-')}</td>
        </tr>`;
      }).join('');
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
      if (!d.ok || !d.data.keywords.length) {
        tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;color:var(--text-secondary);padding:24px">暂无数据</td></tr>';
        return;
      }
      tbody.innerHTML = d.data.keywords.map((kw, idx) => `
        <tr>
          <td>${idx + 1}</td>
          <td>${kw.cate_name}</td>
          <td><strong>${kw.keyword}</strong></td>
          <td class="num">${fmtWan(kw.search_heat)}</td>
          <td class="num">${fmtPct(kw.pay_rate)}</td>
          <td class="num">${fmtPct(kw.click_rate)}</td>
          <td class="num">${fmtPct(kw.free_click_rate)}</td>
        </tr>
      `).join('');
    } catch (e) {
      console.error('加载生意参谋搜索排行失败:', e);
    }
  }

  // ===== 关键词洞察（8大归类 / 蓝海 / 趋势节点）与竞店爆品排名变化 =====
  // 对应后端 /api/sycm/market/keyword-insights 与 /api/sycm/market/rival-item-moves，
  // 补齐月复盘 XMind「市场监控」缺口：8大归类 / 词根需求 / 趋势节点 / 蓝海 / 竞店爆品。
  function setTableRows(node, colspan, html) {
    if (!node) return;
    node.innerHTML = html || `<tr><td colspan="${colspan}" style="text-align:center;color:var(--text-secondary);padding:14px">暂无数据</td></tr>`;
  }

  async function loadKeywordInsights() {
    try {
      const response = await fetch('/api/sycm/market/keyword-insights');
      const result = await response.json();
      renderKeywordInsights(result.ok ? result.data : null);
    } catch (e) {
      console.error('加载关键词洞察失败:', e);
      setTableRows(document.querySelector('[data-mr-kw-categories-body]'), 4, '');
      setTableRows(document.querySelector('[data-mr-blue-ocean-body]'), 4, '');
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
    if (data && data.available && data.categories.length) {
      setTableRows(categoriesBody, 4, data.categories.map(cat => `
        <tr>
          <td style="font-weight:600">${escapeHtml(cat.label)}</td>
          <td class="num">${fmtInt(cat.keyword_count)}</td>
          <td class="num">${cat.heat_share === null || cat.heat_share === undefined ? '--' : (cat.heat_share * 100).toFixed(1) + '%'}</td>
          <td>${escapeHtml(cat.top_keywords.map(item => item.keyword).join('、'))}</td>
        </tr>`).join(''));
    } else {
      setTableRows(categoriesBody, 4, '');
    }
    const blueBody = document.querySelector('[data-mr-blue-ocean-body]');
    if (data && data.available && data.blue_ocean.length) {
      setTableRows(blueBody, 4, data.blue_ocean.map(item => `
        <tr>
          <td>${escapeHtml(item.keyword)}</td>
          <td class="num">${fmtInt(item.search_heat)}</td>
          <td class="num">${(item.pay_rate * 100).toFixed(2)}%</td>
          <td class="num">${item.score.toFixed(3)}</td>
        </tr>`).join(''));
    } else {
      setTableRows(blueBody, 4, '');
    }
    const renderTrend = (selector, rows) => {
      const node = document.querySelector(selector);
      if (data && data.available && rows.length) {
        setTableRows(node, 4, rows.map(item => `
          <tr>
            <td>${escapeHtml(item.keyword)}</td>
            <td class="num">${fmtInt(item.recent_heat)}</td>
            <td class="num">${fmtInt(item.baseline_heat)}</td>
            <td class="num" style="color:${item.growth > 0 ? 'var(--success-text)' : 'var(--danger-text)'}">${item.growth > 0 ? '+' : ''}${(item.growth * 100).toFixed(0)}%</td>
          </tr>`).join(''));
      } else {
        setTableRows(node, 4, '');
      }
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
    body.innerHTML = data.shops.map(shop => {
      const movers = (shop.movers || []).slice(0, 6);
      const counts = `↑${shop.rising_count} ↓${shop.falling_count} 新进榜 ${shop.new_count} 退出 ${shop.exit_count}`;
      const table = movers.length ? `
        <div class="ui-table-wrap"><table class="ui-data-table market-entity-table">
          <thead><tr><th>商品</th><th class="num">排名变化</th><th class="num">首日→末日</th><th class="num">访客数</th><th class="num">支付买家</th></tr></thead>
          <tbody>${movers.map(item => `
            <tr>
              <td style="max-width:420px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${escapeHtml(item.title)}">${escapeHtml(item.title)}</td>
              <td class="num" style="color:${item.rank_change > 0 ? 'var(--success-text)' : 'var(--danger-text)'}">${item.rank_change > 0 ? '+' : ''}${item.rank_change}</td>
              <td class="num">${fmtRank(item.first_rank)} → ${fmtRank(item.last_rank)}</td>
              <td class="num">${fmtInt(item.uv)}</td>
              <td class="num">${fmtInt(item.pay_buyer_count)}</td>
            </tr>`).join('')}</tbody>
        </table></div>` : '<div class="market-list-empty">该店窗口内无在榜商品变动</div>';
      return `
        <details class="market-rival-shop" style="margin-bottom:8px;border:1px solid var(--border-subtle,#e5e7eb);border-radius:8px;padding:8px 12px">
          <summary style="cursor:pointer;font-weight:600">
            ${escapeHtml(shop.shop_name)}
            <span style="font-weight:400;color:var(--text-secondary);margin-left:8px">${counts} · 在榜 ${shop.item_count} 品（${shop.window.start} ~ ${shop.window.end}）</span>
          </summary>
          <div style="margin-top:8px">${table}</div>
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
