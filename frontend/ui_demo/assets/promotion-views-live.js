// 推广分析视图扩展：总览（渠道效率 / 投放方式）、计划看板、商品结构抽屉。
// 数据来自推广域 API 的计划/创意维度报表（万相台无界），商品行不带渠道归属。
(function () {
  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));
  const money = (value) => {
    const num = Number(value);
    if (!Number.isFinite(num)) return '--';
    return `¥${num.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  };
  const moneyCompact = (value) => {
    const num = Number(value);
    if (!Number.isFinite(num)) return '--';
    return `¥${num.toLocaleString('zh-CN', { maximumFractionDigits: 0 })}`;
  };
  const percent = (value) => {
    const num = Number(value);
    if (!Number.isFinite(num) || num === null) return '--';
    return `${(num * 100).toFixed(2)}%`;
  };
  const ratio = (value) => {
    const num = Number(value);
    if (!Number.isFinite(num) || num === null) return '--';
    return num.toFixed(2);
  };
  const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (ch) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[ch]));

  const storedView = sessionStorage.getItem('promotion.view');
  const state = {
    view: new Set(['overview', 'plans', 'products']).has(storedView) ? storedView : 'overview',
    channelRows: [],
    planTypeRows: [],
    campaignRows: [],
    structureProduct: null,
    charts: [],
  };

  function range() {
    const rangeState = window.TmallDateRange?.getState?.() || {};
    const period = rangeState.endDate || rangeState.startDate || new Date().toISOString().slice(0, 10);
    return {
      start: rangeState.startDate || `${String(period).slice(0, 7)}-01`,
      end: rangeState.endDate || `${String(period).slice(0, 7)}-31`,
    };
  }

  function chart(key) {
    const canvas = $(key);
    if (!canvas || !window.echarts) return null;
    let instance = window.echarts.getInstanceByDom(canvas);
    if (!instance) instance = window.echarts.init(canvas);
    return instance;
  }

  function disposeCharts() {
    state.charts.forEach((instance) => instance?.dispose?.());
    state.charts = [];
  }

  function roiTone(roi) {
    if (!Number.isFinite(Number(roi)) || Number(roi) <= 0) return 'muted';
    if (Number(roi) >= 3) return 'success';
    if (Number(roi) >= 1.5) return 'warning';
    return 'danger';
  }


  function exportCsv(filename, headers, rows) {
    const escapeCell = (value) => {
      const text = value == null ? '' : String(value);
      return /[",\n\r]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
    };
    const csv = `\ufeff${[headers, ...rows].map((row) => row.map(escapeCell).join(',')).join('\r\n')}`;
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = filename;
    link.click();
    URL.revokeObjectURL(link.href);
  }

  // ── 视图切换 ────────────────────────────────────────────────────────────

  function switchView(view) {
    disposeCharts();
    state.view = view;
    sessionStorage.setItem('promotion.view', view);
    $$('[data-promotion-view]').forEach((button) => {
      button.setAttribute('aria-pressed', String(button.dataset.promotionView === view));
    });
    $$('[data-promotion-view-panel]').forEach((panel) => {
      panel.hidden = panel.dataset.promotionViewPanel !== view;
    });
    if (view === 'overview') loadOverview();
    if (view === 'plans') loadCampaigns();
  }

  function bindViewTabs() {
    $$('[data-promotion-view]').forEach((button) => {
      button.addEventListener('click', () => switchView(button.dataset.promotionView));
    });
    $('[data-promotion-campaign-search]')?.addEventListener('input', () => { renderCampaignTable(); });
    $('[data-promotion-campaign-sort]')?.addEventListener('change', () => { renderCampaignTable(); });
    $('[data-promotion-campaign-plan-type]')?.addEventListener('change', () => { renderCampaignTable(); });
    $('[data-promotion-campaign-channel]')?.addEventListener('change', () => { renderCampaignTable(); });
    $('[data-promotion-campaigns-refresh]')?.addEventListener('click', loadCampaigns);
    window.addEventListener('tmall:export', (event) => {
      const { start, end } = range();
      if (state.view === 'plans' && state.campaignRows.length) {
        event.preventDefault();
        exportCsv(`推广计划_${start}_${end}.csv`,
          ['计划ID', '计划名', '投放方式', '渠道', '推广花费', '推广成交', '总ROI', '点击率', '转化率', '加购次数', '加购成本', '拉新买家数', '拉新成本'],
          state.campaignRows.map((row) => [
            row.campaign_id, row.campaign_name, row.plan_type, row.channel,
            row.ad_spend, row.attributed_payment_amount, row.roi, row.ctr, row.cvr,
            row.cart_adds, row.cart_cost, row.new_buyers, row.new_customer_cost,
          ]));
      }
    });
  }

  // ── 总览：渠道效率卡 + 散点 + 环形 + 投放方式 ──────────────────────────

  async function loadOverview() {
    disposeCharts();
    const { start, end } = range();
    const query = new URLSearchParams({ start, end, group_by: 'channel' });
    try {
      const [channelResponse, planTypeResponse] = await Promise.all([
        DemoApi.domainRequest(`/api/promotion?${query}`),
        DemoApi.domainRequest(`/api/promotion/plan-types?${new URLSearchParams({ start, end })}`),
      ]);
      state.channelRows = Array.isArray(channelResponse.data?.rows) ? channelResponse.data.rows : [];
      state.planTypeRows = Array.isArray(planTypeResponse.data?.rows) ? planTypeResponse.data.rows : [];
      renderChannelCards();
      renderChannelCharts();
      renderPlanTypes();
    } catch (error) {
      const cards = $('[data-promotion-channel-cards]');
      if (cards) cards.innerHTML = `<div class="ui-empty-state"><span>${esc(error.message || '渠道数据加载失败')}</span></div>`;
    }
  }

  function renderChannelCards() {
    const wrap = $('[data-promotion-channel-cards]');
    if (!wrap) return;
    const rows = state.channelRows.filter((row) => Number(row.ad_spend || 0) > 0);
    const countBadge = $('[data-promotion-channel-cards-count]');
    if (countBadge) countBadge.textContent = `${rows.length} 个渠道`;
    if (!rows.length) {
      wrap.innerHTML = '<div class="ui-empty-state"><span>当前范围没有渠道推广数据</span></div>';
      const note = $('[data-promotion-channel-cards-note]');
      if (note) note.textContent = '';
      return;
    }
    wrap.innerHTML = rows.map((row) => {
      const spend = Number(row.ad_spend || 0);
      const cartAdd = Number(row.cart_adds || 0);
      const newBuyers = Number(row.new_buyers || 0);
      return `
        <article class="promotion-channel-card" data-tone="${roiTone(row.roi)}">
          <div class="promotion-channel-card__name"><span>${esc(row.channel || '未标注')}</span><span class="promotion-channel-card__roi">${ratio(row.roi)}</span></div>
          <div class="promotion-channel-card__metrics">
            <span>花费 <b>${moneyCompact(spend)}</b></span>
            <span>直接ROI <b>${ratio(row.direct_roi)}</b></span>
            <span>点击率 <b>${percent(row.ctr)}</b></span>
            <span>转化率 <b>${percent(row.cvr)}</b></span>
            <span>加购率 <b>${percent(row.cart_rate)}</b></span>
            <span>加购成本 <b>${cartAdd ? money(row.cart_cost) : '--'}</b></span>
            <span>拉新成本 <b>${newBuyers ? money(row.new_customer_cost) : '--'}</b></span>
            <span>拉新占比 <b>${percent(row.new_buyer_ratio)}</b></span>
          </div>
        </article>`;
    }).join('');
    const withCart = rows.filter((row) => Number(row.cart_adds || 0) > 0);
    const withNew = rows.filter((row) => Number(row.new_buyers || 0) > 0);
    const notes = [];
    if (withCart.length) {
      const best = withCart.reduce((a, b) => (Number(a.cart_cost || 0) <= Number(b.cart_cost || 0) ? a : b));
      notes.push(`加购成本最低：${best.channel} ${money(best.cart_cost)}`);
    }
    if (withNew.length) {
      const best = withNew.reduce((a, b) => (Number(a.new_customer_cost || 0) <= Number(b.new_customer_cost || 0) ? a : b));
      notes.push(`拉新成本最低：${best.channel} ${money(best.new_customer_cost)}`);
    }
    const note = $('[data-promotion-channel-cards-note]');
    if (note) note.textContent = notes.join(' · ');
  }

  function renderChannelCharts() {
    const rows = state.channelRows.filter((row) => Number(row.ad_spend || 0) > 0);
    const scatter = chart('#promotionChannelScatter');
    if (scatter) {
      state.charts.push(scatter);
      const points = rows.map((row) => ({
        name: row.channel,
        value: [Number(row.cart_cost || 0), Number(row.roi || 0), Number(row.ad_spend || 0)],
      }));
      scatter.setOption({
        tooltip: {
          formatter: (params) => `${esc(params.name)}<br>加购成本：${money(params.value[0])}<br>ROI：${ratio(params.value[1])}<br>花费：${money(params.value[2])}`,
        },
        grid: { left: 56, right: 24, top: 24, bottom: 36 },
        xAxis: { type: 'value', name: '加购成本', axisLabel: { formatter: (v) => `¥${v}` } },
        yAxis: { type: 'value', name: 'ROI' },
        series: [{
          type: 'scatter',
          data: points,
          symbolSize: (value) => Math.max(10, Math.min(52, Math.sqrt(Number(value[2] || 0)) / 4)),
          itemStyle: { opacity: 0.78 },
          label: { show: true, position: 'top', formatter: (params) => params.name, fontSize: 11 },
        }],
      });
    }
    const donut = chart('#promotionChannelDonut');
    if (donut) {
      state.charts.push(donut);
      donut.setOption({
        tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
        legend: { bottom: 0, type: 'scroll' },
        series: [{
          type: 'pie',
          radius: ['42%', '70%'],
          center: ['50%', '44%'],
          itemStyle: { borderRadius: 4 },
          label: { show: false },
          data: rows.map((row) => ({ name: row.channel, value: Number(row.ad_spend || 0).toFixed(2) })),
        }],
      });
    }
  }

  function renderPlanTypes() {
    const body = $('[data-promotion-plan-types-body]');
    if (!body) return;
    const rows = state.planTypeRows;
    const countBadge = $('[data-promotion-plan-types-count]');
    if (countBadge) countBadge.textContent = `${rows.length} 类`;
    if (!rows.length) {
      body.innerHTML = '<tr><td colspan="8">当前范围没有计划数据</td></tr>';
      const note = $('[data-promotion-plan-types-note]');
      if (note) note.textContent = '';
      return;
    }
    // “最佳”标注只在解析出投放方式的桶之间比较，未标注桶不参与
    const labeled = rows.filter((row) => row.plan_type && row.plan_type !== '未标注');
    const withRoi = labeled.filter((row) => row.roi != null);
    const withCtr = labeled.filter((row) => row.ctr != null);
    const bestRoi = withRoi.length ? withRoi.reduce((a, b) => (a.roi >= b.roi ? a : b)) : null;
    const bestCtr = withCtr.length ? withCtr.reduce((a, b) => (a.ctr >= b.ctr ? a : b)) : null;
    body.innerHTML = rows.map((row) => `
      <tr>
        <td><span class="plan-type-badge plan-type-badge--${esc(row.plan_type)}">${esc(row.plan_type)}</span>${bestRoi && row === bestRoi ? ' <span class="ui-badge ui-badge--success">ROI 最高</span>' : ''}${bestCtr && row === bestCtr ? ' <span class="ui-badge ui-badge--info">CTR 最高</span>' : ''}</td>
        <td>${row.plan_count}</td>
        <td>${money(row.ad_spend)}</td>
        <td>${money(row.attributed_payment_amount)}</td>
        <td>${ratio(row.roi)}</td>
        <td>${percent(row.ctr)}</td>
        <td>${percent(row.cvr)}</td>
        <td>${row.cart_cost != null ? money(row.cart_cost) : '--'}</td>
      </tr>`).join('');
    const note = $('[data-promotion-plan-types-note]');
    if (note) note.textContent = bestRoi ? `「${bestRoi.plan_type}」总 ROI 最高（${ratio(bestRoi.roi)}）` : '';
  }

  // ── 计划看板 ───────────────────────────────────────────────────────────

  async function loadCampaigns() {
    const body = $('[data-promotion-campaigns-body]');
    if (!body) return;
    const { start, end } = range();
    const query = new URLSearchParams({ start, end, group_by: 'campaign' });
    body.innerHTML = '<tr><td colspan="9">加载中…</td></tr>';
    try {
      const response = await DemoApi.domainRequest(`/api/promotion?${query}`);
      state.campaignRows = Array.isArray(response.data?.rows) ? response.data.rows : [];
      fillCampaignFilters();
      renderCampaignTable();
    } catch (error) {
      body.innerHTML = `<tr><td colspan="9">${esc(error.message || '计划数据加载失败')}</td></tr>`;
    }
  }

  function fillCampaignFilters() {
    const channels = [...new Set(state.campaignRows.map((row) => row.channel).filter(Boolean))];
    const channelSelect = $('[data-promotion-campaign-channel]');
    if (channelSelect && channelSelect.options.length <= 1) {
      channels.sort().forEach((channel) => {
        const option = document.createElement('option');
        option.value = channel;
        option.textContent = channel;
        channelSelect.appendChild(option);
      });
    }
    const types = [...new Set(state.campaignRows.map((row) => row.plan_type).filter(Boolean))];
    const typeSelect = $('[data-promotion-campaign-plan-type]');
    if (typeSelect && typeSelect.options.length <= 1) {
      types.sort().forEach((type) => {
        const option = document.createElement('option');
        option.value = type;
        option.textContent = type;
        typeSelect.appendChild(option);
      });
    }
  }

  function renderCampaignTable() {
    const body = $('[data-promotion-campaigns-body]');
    if (!body) return;
    const channelFilter = $('[data-promotion-campaign-channel]')?.value || '';
    const typeFilter = $('[data-promotion-campaign-plan-type]')?.value || '';
    const sortKey = $('[data-promotion-campaign-sort]')?.value || 'ad_spend';
    const search = ($('[data-promotion-campaign-search]')?.value || '').trim().toLowerCase();
    let rows = state.campaignRows.filter((row) => {
      if (channelFilter && row.channel !== channelFilter) return false;
      if (typeFilter && row.plan_type !== typeFilter) return false;
      if (search) {
        const haystack = `${row.campaign_id} ${row.campaign_name || ''}`.toLowerCase();
        if (!haystack.includes(search)) return false;
      }
      return true;
    });
    rows = [...rows].sort((a, b) => (Number(b[sortKey] || 0) || 0) - (Number(a[sortKey] || 0) || 0));
    const countBadge = $('[data-promotion-campaigns-count]');
    if (countBadge) countBadge.textContent = `${rows.length} 个计划`;
    if (!rows.length) {
      body.innerHTML = '<tr><td colspan="9">当前筛选范围没有计划数据</td></tr>';
      return;
    }
    body.innerHTML = rows.map((row, index) => `
      <tr class="promotion-campaign-row" data-campaign-id="${esc(row.campaign_id || '')}">
        <td class="t-clamp" title="${esc(row.campaign_name || row.campaign_id || '')}"><button type="button" class="promotion-campaign-toggle" aria-expanded="false" aria-controls="promotion-campaign-detail-${index}" data-campaign-toggle><strong>${esc(row.campaign_name || `计划 ${row.campaign_id || ''}`)}</strong> ${row.plan_type ? `<span class="plan-type-badge plan-type-badge--${esc(row.plan_type)}">${esc(row.plan_type)}</span>` : ''}</button></td>
        <td>${esc(row.channel || '--')}</td>
        <td>${money(row.ad_spend)}</td>
        <td>${money(row.attributed_payment_amount)}</td>
        <td>${ratio(row.roi)}</td>
        <td>${percent(row.ctr)}</td>
        <td>${percent(row.cvr)}</td>
        <td>${row.cart_cost != null ? money(row.cart_cost) : '--'}</td>
        <td>${row.new_customer_cost != null ? money(row.new_customer_cost) : '--'}</td>
      </tr>`).join('');
    $$('tr.promotion-campaign-row', body).forEach((row) => {
      const toggle = $('[data-campaign-toggle]', row);
      toggle?.addEventListener('click', () => toggleCampaignDetail(row));
    });
    // 分页/排序由共享 table-controls 组件接管(自动挂载)
  }

  async function toggleCampaignDetail(row) {
    const toggle = $('[data-campaign-toggle]', row);
    const existing = row.nextElementSibling;
    if (existing?.classList.contains('promotion-campaign-row__detail')) {
      existing.remove();
      toggle?.setAttribute('aria-expanded', 'false');
      return;
    }
    const campaignId = row.dataset.campaignId;
    if (!campaignId) return;
    const detail = document.createElement('tr');
    detail.className = 'promotion-campaign-row__detail';
    const detailId = toggle?.getAttribute('aria-controls');
    if (detailId) detail.id = detailId;
    toggle?.setAttribute('aria-expanded', 'true');
    detail.innerHTML = '<td colspan="9">正在加载计划明细…</td>';
    row.after(detail);
    const { start, end } = range();
    try {
      const response = await DemoApi.domainRequest(`/api/promotion/campaign-detail?${new URLSearchParams({ start, end, campaign_id: campaignId })}`);
      const products = Array.isArray(response.data?.products) ? response.data.products : [];
      detail.innerHTML = `<td colspan="9">${products.length ? `<div class="promotion-campaign-products">${products.map((product) => `
        <div class="promotion-campaign-product">
          ${product.image_url ? `<img src="${esc(product.image_url)}" alt="" loading="lazy">` : ''}
          <div class="promotion-campaign-product__meta">
            <div class="promotion-campaign-product__name">${esc(product.title || product.product_name || product.product_id)}</div>
            <div class="promotion-campaign-product__sub">素材 ${product.creative_count || 0} 个</div>
          </div>
        </div>`).join('')}</div>` : '该计划没有关联商品映射'}</td>`;
    } catch (error) {
      detail.innerHTML = `<td colspan="9">${esc(error.message || '计划明细加载失败')}</td>`;
    }
  }


  // ── 商品推广结构抽屉 ───────────────────────────────────────────────────

  function bindStructureDialog() {
    const dialog = $('[data-promotion-structure-dialog]');
    if (!dialog) return;
    $('[data-promotion-structure-close]')?.addEventListener('click', () => dialog.close());
    $$('[data-promotion-structure-tab]').forEach((button) => {
      button.addEventListener('click', () => {
        $$('[data-promotion-structure-tab]').forEach((item) => {
          item.setAttribute('aria-selected', String(item === button));
        });
        renderStructurePanel(button.dataset.promotionStructureTab);
      });
    });
    // 在引擎渲染的商品表"明细"按钮旁追加"结构"入口（不改引擎渲染逻辑）
    const tableBody = $('#promotionTable tbody');
    if (!tableBody) return;
    const addStructureButtons = () => {
      $$('#promotionTable tbody button[data-promotion-drill]').forEach((button) => {
        const productId = button.dataset.promotionDrill;
        if (!productId || button.nextElementSibling?.dataset.promotionStructure) return;
        const structureButton = document.createElement('button');
        structureButton.className = 'ui-button ui-button--ghost';
        structureButton.type = 'button';
        structureButton.dataset.promotionStructure = productId;
        structureButton.textContent = '结构';
        structureButton.title = '查看该商品的渠道结构与计划';
        structureButton.addEventListener('click', (event) => {
          event.stopPropagation();
          openStructureDialog(productId);
        });
        button.after(structureButton);
      });
    };
    new MutationObserver(addStructureButtons).observe(tableBody, { childList: true, subtree: true });
    addStructureButtons();
  }

  function openStructureDialog(productId) {
    const dialog = $('[data-promotion-structure-dialog]');
    if (!dialog || !productId) return;
    state.structureProduct = productId;
    dialog.showModal();
    $$('[data-promotion-structure-tab]').forEach((item, index) => {
      item.setAttribute('aria-selected', String(index === 0));
    });
    renderStructurePanel('mix');
  }

  async function renderStructurePanel(tab) {
    const body = $('[data-promotion-structure-body]');
    if (!body || !state.structureProduct) return;
    const { start, end } = range();
    const productId = state.structureProduct;
    if (tab === 'mix') {
      body.innerHTML = '<div class="chart-box chart-box--tall"><div id="promotionStructureMix" class="chart-canvas"></div></div>';
      try {
        const response = await DemoApi.domainRequest(`/api/promotion/product-detail?${new URLSearchParams({ start, end, product_id: productId })}`);
        const mix = Array.isArray(response.data?.channel_mix) ? response.data.channel_mix : [];
        const instance = chart('#promotionStructureMix');
        if (!mix.length) {
          body.innerHTML = '<div class="ui-empty-state"><span>该商品暂无渠道归因数据</span></div>';
          return;
        }
        instance.setOption({
          tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
          legend: { bottom: 0, type: 'scroll' },
          series: [
            { type: 'pie', radius: ['38%', '60%'], center: ['32%', '46%'], label: { show: false }, data: mix.map((row) => ({ name: row.channel, value: Number(row.ad_spend || 0).toFixed(2) })) },
            { type: 'pie', radius: ['38%', '60%'], center: ['74%', '46%'], label: { show: false }, data: mix.map((row) => ({ name: row.channel, value: Number(row.attributed_payment_amount || 0).toFixed(2) })) },
          ],
        });
        body.insertAdjacentHTML('beforeend', `<p class="promotion-channel-cards__footnote">左：各渠道花费占比；右：各渠道成交占比。${esc((response.limitations || []).join(' '))}</p>`);
      } catch (error) {
        body.innerHTML = `<div class="ui-empty-state"><span>${esc(error.message || '结构数据加载失败')}</span></div>`;
      }
    }
    if (tab === 'campaigns') {
      body.innerHTML = '<div class="ui-table-wrap"><table class="ui-data-table"><thead><tr><th>计划</th><th>渠道</th><th>花费</th><th>ROI</th><th>加购成本</th></tr></thead><tbody><tr><td>加载中…</td></tr></tbody></table></div>';
      try {
        const response = await DemoApi.domainRequest(`/api/promotion/product-detail?${new URLSearchParams({ start, end, product_id: productId })}`);
        const campaigns = Array.isArray(response.data?.campaigns) ? response.data.campaigns : [];
        const tbody = $('tbody', body);
        if (!campaigns.length) {
          tbody.innerHTML = '<tr><td>该商品暂无计划数据</td></tr>';
          return;
        }
        tbody.innerHTML = campaigns.map((row) => `
          <tr>
            <td>${esc(row.campaign_name || row.campaign_id)} ${row.plan_type ? `<span class="plan-type-badge plan-type-badge--${esc(row.plan_type)}">${esc(row.plan_type)}</span>` : ''}</td>
            <td>${esc(row.channel || '--')}</td>
            <td>${money(row.ad_spend)}</td>
            <td>${ratio(row.roi)}</td>
            <td>${row.cart_cost != null ? money(row.cart_cost) : '--'}</td>
          </tr>`).join('');
      } catch (error) {
        body.innerHTML = `<div class="ui-empty-state"><span>${esc(error.message || '计划数据加载失败')}</span></div>`;
      }
    }
    if (tab === 'creatives') {
      // 素材表现已拆到独立看板页,带商品 ID 跳转
      dialog.close();
      window.location.href = `/creative-board?product_id=${encodeURIComponent(state.structureProduct || '')}`;
    }
  }

  // ── 启动 ───────────────────────────────────────────────────────────────

  function boot() {
    bindViewTabs();
    bindStructureDialog();
    switchView(state.view);
    window.addEventListener('tmall:date-range-change', () => {
      if (state.view === 'overview') loadOverview();
      if (state.view === 'plans') loadCampaigns();
    });
    window.addEventListener('tmall:refresh', () => switchView(state.view));
    if (!window.TmallDateRange) switchView(state.view);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
