(async function () {
  'use strict';

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
  };

  function $(sel) { return document.querySelector(sel); }
  function $$(sel) { return Array.from(document.querySelectorAll(sel)); }

  function fmtInt(v) {
    if (v == null || isNaN(v)) return '--';
    return Number(v).toLocaleString('zh-CN');
  }
  function fmtPct(v) {
    if (v == null || isNaN(v)) return '--';
    return (Number(v) * 100).toFixed(1) + '%';
  }
  function fmtWan(v) {
    if (v == null || isNaN(v)) return '--';
    const n = Number(v);
    if (n >= 10000) return (n / 10000).toFixed(1) + '万';
    return fmtInt(n);
  }

  // ===== 加载数据 =====
  async function loadSummary() {
    const r = await fetch(API_BASE + '/summary');
    const d = await r.json();
    if (!d.ok) throw new Error(d.message || '加载失败');
    state.summary = d.data;
    state.categories = d.data.categories.map(c => c.category);
    return d.data;
  }

  async function loadFilters() {
    const r = await fetch(API_BASE + '/filters');
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
    const r = await fetch(url);
    const d = await r.json();
    return d.ok ? d.data : [];
  }

  async function loadKeywords() {
    let url = API_BASE + '/keywords?';
    if (state.kwCategory) url += 'category=' + encodeURIComponent(state.kwCategory) + '&';
    if (state.kwType) url += 'keyword_type=' + encodeURIComponent(state.kwType) + '&';
    const r = await fetch(url);
    const d = await r.json();
    return d.ok ? d.data : [];
  }

  async function loadOverlapShops() {
    const r = await fetch(API_BASE + '/overlap-shops');
    const d = await r.json();
    return d.ok ? d.data : [];
  }

  // ===== 渲染指标卡片 =====
  function renderMetrics(summary) {
    $('[data-mr-period]').textContent = `${summary.period_start} ~ ${summary.period_end}`;
    $('[data-mr-cat-count]').textContent = summary.category_count;
    $('[data-mr-product-count]').textContent = fmtInt(summary.product_count);
    $('[data-mr-kw-count]').textContent = fmtInt(summary.keyword_count);
    $('[data-mr-overlap-count]').textContent = fmtInt(summary.overlap_shop_count);
  }

  // ===== 渲染类目对比 =====
  function renderCategoryComparison(categories) {
    const COLORS = { '中筒袜': '#4f46e5', '长筒袜': '#10b981' };

    // 店铺类型分布
    let shopHtml = '';
    categories.forEach(cat => {
      const total = cat.shop_tmall + cat.shop_taobao;
      const tmallPct = total ? (cat.shop_tmall / total * 100) : 0;
      shopHtml += `
        <div style="margin-bottom:12px">
          <div style="display:flex;justify-content:space-between;font-size:12px;margin-bottom:4px">
            <span style="font-weight:600;color:${COLORS[cat.category] || '#666'}">${cat.category}</span>
            <span style="color:var(--text-secondary)">天猫 ${tmallPct.toFixed(1)}% / 淘宝 ${(100-tmallPct).toFixed(1)}%</span>
          </div>
          <div style="display:flex;height:20px;border-radius:4px;overflow:hidden">
            <div style="width:${tmallPct}%;background:#3b82f6"></div>
            <div style="width:${100-tmallPct}%;background:#f59e0b"></div>
          </div>
          <div style="display:flex;justify-content:space-between;font-size:11px;color:var(--text-tertiary);margin-top:2px">
            <span>天猫 ${fmtInt(cat.shop_tmall)}</span>
            <span>淘宝 ${fmtInt(cat.shop_taobao)}</span>
          </div>
        </div>`;
    });
    $('[data-mr-shop-type]').innerHTML = shopHtml;

    // 排名趋势
    const trendLabels = ['上升', '下降', '持平', '新上榜', '跌出榜'];
    const trendKeys = ['trend_up', 'trend_down', 'trend_flat', 'trend_new', 'trend_out'];
    const trendColors = ['#10b981', '#ef4444', '#9ca3af', '#3b82f6', '#f59e0b'];
    let trendHtml = '';
    categories.forEach(cat => {
      trendHtml += `<div style="margin-bottom:8px"><span style="font-weight:600;font-size:12px;color:${COLORS[cat.category]}">${cat.category}</span></div>`;
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
    $('[data-mr-trend]').innerHTML = trendHtml;

    // 集中度
    let concHtml = '';
    categories.forEach(cat => {
      concHtml += `
        <div style="margin-bottom:16px">
          <div style="font-weight:600;font-size:12px;color:${COLORS[cat.category]};margin-bottom:6px">${cat.category}</div>
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
    $('[data-mr-concentration]').innerHTML = concHtml;

    // 总买家数
    let totalHtml = '';
    const maxTotal = Math.max(...categories.map(c => c.total_buyers || 0), 1);
    categories.forEach(cat => {
      const pct = (cat.total_buyers / maxTotal * 100);
      totalHtml += `
        <div style="margin-bottom:16px">
          <div style="display:flex;justify-content:space-between;margin-bottom:4px">
            <span style="font-weight:600;font-size:13px;color:${COLORS[cat.category]}">${cat.category}</span>
            <span style="font-family:var(--font-display);font-size:18px;font-weight:700">${fmtWan(cat.total_buyers)}</span>
          </div>
          <div style="height:24px;background:var(--surface-base);border-radius:4px;overflow:hidden">
            <div style="width:${pct}%;height:100%;background:${COLORS[cat.category]};border-radius:4px"></div>
          </div>
        </div>`;
    });
    $('[data-mr-total-buyers]').innerHTML = totalHtml;
  }

  // ===== 渲染筛选器 =====
  function renderFilters() {
    const catSel = $('[data-mr-filter-category]');
    catSel.innerHTML = '<option value="">全部类目</option>' +
      state.categories.map(c => `<option value="${c}">${c}</option>`).join('');

    const listSel = $('[data-mr-filter-list-type]');
    listSel.innerHTML = '<option value="">全部榜单</option>' +
      state.listTypes.map(t => `<option value="${t}">${t}</option>`).join('');

    const kwCatSel = $('[data-mr-kw-category]');
    kwCatSel.innerHTML = '<option value="">全部类目</option>' +
      state.categories.map(c => `<option value="${c}">${c}</option>`).join('');

    const kwTypeSel = $('[data-mr-kw-type]');
    kwTypeSel.innerHTML = '<option value="">全部类型</option>' +
      state.keywordTypes.map(t => `<option value="${t}">${t}</option>`).join('');
  }

  // ===== 渲染商品榜单 =====
  function renderProducts(products) {
    const tbody = $('[data-mr-products-body]');
    if (!products.length) {
      tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;color:var(--text-tertiary);padding:24px">没有符合条件的数据</td></tr>';
      return;
    }
    tbody.innerHTML = products.map(p => {
      const rankBadge = p.rank <= 3
        ? `<span class="badge badge--${p.rank === 1 ? 'danger' : p.rank === 2 ? 'warning' : 'success'}">${p.rank}</span>`
        : `<span class="badge badge--muted">${p.rank}</span>`;
      return `<tr>
        <td>${rankBadge}</td>
        <td><span class="badge badge--info">${p.category}</span></td>
        <td><span class="badge badge--muted">${p.list_type}</span></td>
        <td style="max-width:300px">${p.title || '-'}</td>
        <td style="color:var(--text-secondary)">${p.shop || '-'}</td>
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
      if (!list.length) return '<div style="color:var(--text-tertiary);text-align:center;padding:20px">暂无数据</div>';
      const max = Math.max(...list.map(k => k.count), 1);
      return list.map(k => `
        <div class="market-bar-row">
          <span class="market-bar-label" style="width:70px">${k.keyword}</span>
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
      container.innerHTML = '<span style="color:var(--text-tertiary)">暂无重叠店铺</span>';
      return;
    }
    container.innerHTML = shops.map(s => `<span class="market-overlap-tag">${s}</span>`).join('');
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
  async function init() {
    try {
      const [summary, filters] = await Promise.all([loadSummary(), loadFilters()]);
      renderMetrics(summary);
      renderCategoryComparison(summary.categories);
      renderFilters();
      bindEvents();

      const [products, keywords, overlapShops] = await Promise.all([
        loadProducts(), loadKeywords(), loadOverlapShops()
      ]);
      renderProducts(products);
      renderKeywords(keywords);
      renderOverlapShops(overlapShops);

      // 加载生意参谋数据
      loadSycmCategories();
      loadSycmItemRank();
      loadSycmSearchRank();

      window.lucide?.createIcons();
    } catch (e) {
      console.error('市场分析加载失败:', e);
      document.querySelector('.demo-page').innerHTML =
        `<div style="padding:40px;text-align:center;color:var(--danger)">加载失败：${e.message}</div>`;
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else { init(); }
})();
  // ===== 生意参谋数据 =====
  async function loadSycmCategories() {
    try {
      const r = await fetch('/api/sycm/market/categories');
      const d = await r.json();
      if (d.ok && d.data.categories) {
        const selects = document.querySelectorAll('[data-sycm-cate-filter], [data-sycm-kw-cate-filter]');
        selects.forEach(sel => {
          d.data.categories.forEach(cat => {
            const opt = document.createElement('option');
            opt.value = cat.cate_name;
            opt.textContent = cat.cate_name;
            sel.appendChild(opt);
          });
        });
      }
    } catch (e) {
      console.error('加载生意参谋类目失败:', e);
    }
  }

  async function loadSycmItemRank(cateName = '') {
    try {
      let url = '/api/sycm/market/item-rank?limit=50';
      if (cateName) url += '&cate_name=' + encodeURIComponent(cateName);
      const r = await fetch(url);
      const d = await r.json();
      const tbody = document.querySelector('[data-sycm-item-rank-body]');
      if (!tbody) return;
      if (!d.ok || !d.data.items.length) {
        tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;color:var(--text-tertiary);padding:24px">暂无数据</td></tr>';
        return;
      }
      tbody.innerHTML = d.data.items.map((item, idx) => `
        <tr>
          <td>${idx + 1}</td>
          <td>${item.cate_name}</td>
          <td>${item.title || '-'}</td>
          <td>${item.shop_name || '-'}</td>
          <td class="num">${fmtWan(item.uv)}</td>
          <td class="num">${fmtWan(item.pay_buyer_count)}</td>
          <td>${item.core_keyword || '-'}</td>
        </tr>
      `).join('');
    } catch (e) {
      console.error('加载生意参谋商品排行失败:', e);
    }
  }

  async function loadSycmSearchRank(cateName = '') {
    try {
      let url = '/api/sycm/market/search-rank?limit=50';
      if (cateName) url += '&cate_name=' + encodeURIComponent(cateName);
      const r = await fetch(url);
      const d = await r.json();
      const tbody = document.querySelector('[data-sycm-search-rank-body]');
      if (!tbody) return;
      if (!d.ok || !d.data.keywords.length) {
        tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;color:var(--text-tertiary);padding:24px">暂无数据</td></tr>';
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

  // 生意参谋筛选事件
  document.addEventListener('DOMContentLoaded', () => {
    setTimeout(() => {
      const cateFilter = document.querySelector('[data-sycm-cate-filter]');
      if (cateFilter) {
        cateFilter.addEventListener('change', e => loadSycmItemRank(e.target.value));
      }
      const kwCateFilter = document.querySelector('[data-sycm-kw-cate-filter]');
      if (kwCateFilter) {
        kwCateFilter.addEventListener('change', e => loadSycmSearchRank(e.target.value));
      }
    }, 1000);
  });
