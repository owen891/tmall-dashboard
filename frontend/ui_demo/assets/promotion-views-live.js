// 推广分析视图扩展：总览（渠道效率 / 投放方式）、计划看板、商品结构抽屉。
// 数据来自推广域 API 的计划/创意维度报表（万相台无界），商品行不带渠道归属。
(function () {
  const promotionMetrics = window.TmallPromotionMetrics;
  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));
  const money = (value) => {
    if (value === null || value === undefined || value === '') return '--';
    const num = Number(value);
    if (!Number.isFinite(num)) return '--';
    return `¥${num.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  };
  const moneyCompact = (value) => {
    if (value === null || value === undefined || value === '') return '--';
    const num = Number(value);
    if (!Number.isFinite(num)) return '--';
    return `¥${num.toLocaleString('zh-CN', { maximumFractionDigits: 0 })}`;
  };
  const percent = (value) => {
    if (value === null || value === undefined || value === '') return '--';
    const num = Number(value);
    if (!Number.isFinite(num) || num === null) return '--';
    return `${(num * 100).toFixed(2)}%`;
  };
  const ratio = (value) => {
    if (value === null || value === undefined || value === '') return '--';
    const num = Number(value);
    if (!Number.isFinite(num) || num === null) return '--';
    return num.toFixed(2);
  };
  const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (ch) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[ch]));
  const metric = (row, key, kind) => {
    const status = row.metric_availability?.[key];
    const title = promotionMetrics.compactTitle(row, key, kind);
    const label = promotionMetrics.statusLabel(row, key);
    const value = promotionMetrics.valueText(row, key, kind);
    return `<span class="promotion-metric${status ? ` promotion-metric--${esc(status)}` : ''}"${title ? ` title="${esc(title)}"` : ''}>${esc(value)}${label ? `<span class="promotion-metric__status">${esc(label)}</span>` : ''}</span>`;
  };
  const metricElement = (row, key, kind) => {
    const status = row.metric_availability?.[key];
    const node = document.createElement('span');
    node.className = 'promotion-metric';
    if (status) node.classList.add(`promotion-metric--${String(status).replace(/[^\w-]/g, '')}`);
    node.title = promotionMetrics.compactTitle(row, key, kind) || '';
    node.append(document.createTextNode(promotionMetrics.valueText(row, key, kind)));
    const label = promotionMetrics.statusLabel(row, key);
    if (label) {
      const statusNode = document.createElement('span');
      statusNode.className = 'promotion-metric__status';
      statusNode.textContent = label;
      node.append(statusNode);
    }
    return node;
  };

  const storedView = sessionStorage.getItem('promotion.view');
  const state = {
    view: new Set(['overview', 'plans', 'products']).has(storedView) ? storedView : 'overview',
    channelRows: [],
    planTypeRows: [],
    campaignRows: [],
    structureProduct: null,
    charts: [],
  };

  const chartInstances = new Set();
  function syncChartTheme(instance) {
    if (!instance) return;
    if (instance.isDisposed?.()) { chartInstances.delete(instance); return; }
    const styles = getComputedStyle(document.documentElement);
    const textColor = styles.getPropertyValue('--text-secondary').trim() || '#64748b';
    const primaryColor = styles.getPropertyValue('--text-primary').trim() || '#111827';
    const borderColor = styles.getPropertyValue('--border-default').trim() || '#d1d5db';
    const option = (instance.getOption ? instance.getOption() : {}) || {};
    const axes = (value) => (Array.isArray(value) ? value : value ? [value] : []).map((axis) => ({
      ...axis,
      nameTextStyle: { ...(axis.nameTextStyle || {}), color: textColor },
      axisLabel: { ...(axis.axisLabel || {}), color: textColor },
      axisLine: { ...(axis.axisLine || {}), lineStyle: { ...(axis.axisLine?.lineStyle || {}), color: borderColor } },
      splitLine: { ...(axis.splitLine || {}), lineStyle: { ...(axis.splitLine?.lineStyle || {}), color: borderColor } },
    }));
    const themed = { textStyle: { color: textColor }, tooltip: { backgroundColor: styles.getPropertyValue('--surface-base').trim(), borderColor, textStyle: { color: primaryColor } } };
    if (option.legend) themed.legend = (Array.isArray(option.legend) ? option.legend : [option.legend]).map((legend) => ({ ...legend, textStyle: { ...(legend.textStyle || {}), color: textColor } }));
    if (option.xAxis) themed.xAxis = axes(option.xAxis);
    if (option.yAxis) themed.yAxis = axes(option.yAxis);
    try { instance.setOption(themed); } catch (_) { chartInstances.delete(instance); }
  }
  function registerChart(instance) { if (instance) { chartInstances.add(instance); syncChartTheme(instance); } return instance; }
  new MutationObserver(() => chartInstances.forEach(syncChartTheme)).observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });

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
    return registerChart(instance);
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
          ['计划ID', '计划名', '投放方式', '渠道', '推广花费', '推广成交', '总ROI', '点击率', '转化率', '加购次数', '加购成本', '拉新买家数', '拉新成本', '直接付费成交', '间接付费成交'],
          state.campaignRows.map((row) => [
            row.campaign_id, row.campaign_name, row.plan_type, row.channel,
            promotionMetrics.exportValue(row, 'ad_spend'), promotionMetrics.exportValue(row, 'attributed_payment_amount'), promotionMetrics.exportValue(row, 'roi'), promotionMetrics.exportValue(row, 'ctr'), promotionMetrics.exportValue(row, 'cvr'),
            promotionMetrics.exportValue(row, 'cart_adds'), promotionMetrics.exportValue(row, 'cart_cost'), promotionMetrics.exportValue(row, 'new_buyers'), promotionMetrics.exportValue(row, 'new_customer_cost'),
            promotionMetrics.exportValue(row, 'direct_payment_amount'), promotionMetrics.exportValue(row, 'indirect_payment_amount'),
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
    const rows = state.channelRows; // Fact presence, not positive spend, determines card presence.
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
          <div class="promotion-channel-card__name"><span>${esc(row.channel || '未标注')}</span><span class="promotion-channel-card__roi">${metric(row, 'roi', 'ratio')}</span></div>
          <div class="promotion-channel-card__metrics">
            <div class="promotion-channel-card__metric"><span class="promotion-channel-card__label">花费</span><span class="promotion-channel-card__value">${metric(row, 'ad_spend', 'money')}</span></div>
            <div class="promotion-channel-card__metric"><span class="promotion-channel-card__label">直接 ROI</span><span class="promotion-channel-card__value">${metric(row, 'direct_roi', 'ratio')}</span></div>
            <div class="promotion-channel-card__metric"><span class="promotion-channel-card__label">点击率</span><span class="promotion-channel-card__value">${metric(row, 'ctr', 'percent')}</span></div>
            <div class="promotion-channel-card__metric"><span class="promotion-channel-card__label">转化率</span><span class="promotion-channel-card__value">${metric(row, 'cvr', 'percent')}</span></div>
            <div class="promotion-channel-card__metric"><span class="promotion-channel-card__label">加购率</span><span class="promotion-channel-card__value">${metric(row, 'cart_rate', 'percent')}</span></div>
            <div class="promotion-channel-card__metric"><span class="promotion-channel-card__label">加购成本</span><span class="promotion-channel-card__value">${metric(row, 'cart_cost', 'money')}</span></div>
            <div class="promotion-channel-card__metric"><span class="promotion-channel-card__label">拉新成本</span><span class="promotion-channel-card__value">${metric(row, 'new_customer_cost', 'money')}</span></div>
            <div class="promotion-channel-card__metric"><span class="promotion-channel-card__label">拉新占比</span><span class="promotion-channel-card__value">${metric(row, 'new_buyer_ratio', 'percent')}</span></div>
          </div>
        </article>`;
    }).join('');
    const withCart = rows.filter((row) => row.cart_cost != null && row.metric_availability?.cart_cost !== 'partial');
    const withNew = rows.filter((row) => row.new_customer_cost != null && row.metric_availability?.new_customer_cost !== 'partial');
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
      const points = rows.filter((row) => row.cart_cost != null && row.roi != null).map((row) => ({
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
    const root = $('[data-promotion-plan-types-root]');
    if (!root) return;
    const rows = state.planTypeRows;
    const countBadge = $('[data-promotion-plan-types-count]');
    if (countBadge) countBadge.textContent = `${rows.length} 类`;
    if (!rows.length) {
      const table = window.TmallUI.table({
        caption: '投放方式效果对比',
        tableClass: 'promotion-plan-types-table',
        columns: [{ key: 'message', label: '状态' }],
        rows: [],
        emptyMessage: '当前范围没有计划数据',
      });
      table.querySelector('table')?.setAttribute('data-promotion-plan-types-table', '');
      table.querySelector('tbody')?.setAttribute('data-promotion-plan-types-body', '');
      root.replaceChildren(table);
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
    const table = window.TmallUI.table({
      caption: '投放方式效果对比',
      tableClass: 'promotion-plan-types-table',
      columns: [
        { key: 'plan_type', label: '投放方式', render: (value, row) => {
          const wrap = document.createElement('div');
          const badge = document.createElement('span');
          badge.className = `plan-type-badge plan-type-badge--${String(value || '').replace(/[^\w-]/g, '')}`;
          badge.textContent = value || '未标注';
          wrap.appendChild(badge);
          if (bestRoi && row === bestRoi) wrap.appendChild(window.TmallUI.badge('ROI 最高', 'success'));
          if (bestCtr && row === bestCtr) wrap.appendChild(window.TmallUI.badge('CTR 最高', 'info'));
          return wrap;
        } },
        { key: 'plan_count', label: '计划数', numeric: true },
        ...[['ad_spend', '推广花费', 'money'], ['attributed_payment_amount', '推广成交', 'money'], ['roi', '总 ROI', 'ratio'], ['ctr', '点击率', 'percent'], ['cvr', '转化率', 'percent'], ['cart_cost', '加购成本', 'money']]
          .map(([key, label, kind]) => ({ key, label, numeric: true, render: (_value, row) => metricElement(row, key, kind) })),
      ],
      rows,
      emptyMessage: '当前范围没有计划数据',
    });
    table.querySelector('table')?.setAttribute('data-promotion-plan-types-table', '');
    table.querySelector('tbody')?.setAttribute('data-promotion-plan-types-body', '');
    root.replaceChildren(table);
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
        <td>${metric(row, 'ad_spend', 'money')}</td>
        <td>${metric(row, 'attributed_payment_amount', 'money')}</td>
        <td>${metric(row, 'roi', 'ratio')}</td>
        <td>${metric(row, 'ctr', 'percent')}</td>
        <td>${metric(row, 'cvr', 'percent')}</td>
        <td>${metric(row, 'cart_cost', 'money')}</td>
        <td>${metric(row, 'new_customer_cost', 'money')}</td>
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
            <div class="promotion-campaign-product__sub">${esc(product.product_id || '--')} · 素材 ${product.creative_count || 0} 个</div>
          </div>
        </div>`).join('')}</div>` : '该计划没有关联商品映射'}</td>`;
    } catch (error) {
      detail.innerHTML = `<td colspan="9">${esc(error.message || '计划明细加载失败')}</td>`;
    }
  }


  // ── 商品推广结构抽屉 ───────────────────────────────────────────────────

  let structureDrawer = null;

  function bindStructureDialog() {
    const template = $('[data-promotion-structure-template]');
    if (!template || !window.TmallUI?.detailDrawer) return;
    structureDrawer = window.TmallUI.detailDrawer({
      title: '商品推广结构',
      description: '查看渠道结构、计划与素材表现',
      size: 'lg',
      onClose: () => {
        state.structureRequest = (state.structureRequest || 0) + 1;
        state.creativeRequest = (state.creativeRequest || 0) + 1;
        const chartNode = structureDrawer.body.querySelector('#promotionStructureMix');
        if (chartNode) window.echarts?.getInstanceByDom(chartNode)?.dispose();
      },
    });
    structureDrawer.body.append(template.content.cloneNode(true));
    const tabs = $$('[data-promotion-structure-tab]', structureDrawer.node);
    tabs.forEach((button) => {
      button.addEventListener('click', () => {
        tabs.forEach((item) => item.setAttribute('aria-selected', String(item === button)));
        renderStructurePanel(button.dataset.promotionStructureTab);
      });
    });
    // 在引擎渲染的商品表"明细"按钮旁追加"结构"入口（不改引擎渲染逻辑）
    const tableRoot = $('#promotionTable');
    if (!tableRoot) return;
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
          openStructureDialog(productId, structureButton);
        });
        button.after(structureButton);
      });
    };
    new MutationObserver(addStructureButtons).observe(tableRoot, { childList: true, subtree: true });
    addStructureButtons();
  }

  function openStructureDialog(productId, trigger = null) {
    if (!structureDrawer || !productId) return;
    state.structureProduct = productId;
    const title = structureDrawer.node.querySelector('.ui-drawer__copy h2');
    const description = structureDrawer.node.querySelector('.ui-drawer__copy p');
    if (title) title.textContent = '商品推广结构';
    if (description) description.textContent = `商品 ID ${productId} · 渠道结构、计划与素材表现`;
    const tabs = $$('[data-promotion-structure-tab]', structureDrawer.node);
    tabs.forEach((item, index) => item.setAttribute('aria-selected', String(index === 0)));
    structureDrawer.open(trigger);
    renderStructurePanel('mix');
  }

  async function renderStructurePanel(tab) {
    const body = $('[data-promotion-structure-body]');
    if (!body || !state.structureProduct) return;
    const { start, end } = range();
    const productId = state.structureProduct;
    const requestId = state.structureRequest = (state.structureRequest || 0) + 1;
    state.creativeRequest = (state.creativeRequest || 0) + 1;
    const isCurrent = () => requestId === state.structureRequest && state.structureProduct === productId && !structureDrawer.node.hidden;
    const previousChart = body.querySelector('#promotionStructureMix');
    if (previousChart) window.echarts?.getInstanceByDom(previousChart)?.dispose();
    structureDrawer.body.scrollTop = 0;
    if (tab === 'mix') {
      body.innerHTML = '<div class="chart-box chart-box--tall"><div id="promotionStructureMix" class="chart-canvas"></div></div>';
      try {
        const response = await DemoApi.domainRequest(`/api/promotion/product-detail?${new URLSearchParams({ start, end, product_id: productId })}`);
        if (!isCurrent()) return;
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
        if (!isCurrent()) return;
        body.innerHTML = `<div class="ui-empty-state"><span>${esc(error.message || '结构数据加载失败')}</span></div>`;
      }
    }
    if (tab === 'campaigns') {
      body.replaceChildren(renderCampaignDetailTable([], '加载中…'));
      try {
        const response = await DemoApi.domainRequest(`/api/promotion/product-detail?${new URLSearchParams({ start, end, product_id: productId })}`);
        if (!isCurrent()) return;
        const campaigns = Array.isArray(response.data?.campaigns) ? response.data.campaigns : [];
        body.replaceChildren(renderCampaignDetailTable(campaigns, '该商品暂无计划数据'));
      } catch (error) {
        if (!isCurrent()) return;
        body.innerHTML = `<div class="ui-empty-state"><span>${esc(error.message || '计划数据加载失败')}</span></div>`;
      }
    }
    if (tab === 'creatives') {
      // 素材表现已拆到独立看板页,带商品 ID 跳转
      structureDrawer?.close();
      window.location.href = `/creative-board?product_id=${encodeURIComponent(state.structureProduct || '')}`;
    }
  }

  function renderCampaignDetailTable(rows, emptyMessage) {
    return window.TmallUI.table({
      tableClass: 'promotion-campaign-table',
      columns: [
        { key: 'campaign_name', label: '计划', render: (value, row) => {
          const cell = document.createElement('span');
          cell.append(document.createTextNode(String(value || row.campaign_id || '--')));
          if (row.plan_type) {
            const badge = document.createElement('span');
            badge.className = `plan-type-badge plan-type-badge--${String(row.plan_type).replace(/[^\w-]/g, '')}`;
            badge.textContent = String(row.plan_type);
            cell.append(' ', badge);
          }
          return cell;
        } },
        { key: 'channel', label: '渠道', render: value => value || '--' },
        { key: 'ad_spend', label: '花费', numeric: true, render: (value, row) => metricElement(row, 'ad_spend', 'money') },
        { key: 'roi', label: 'ROI', numeric: true, render: (value, row) => metricElement(row, 'roi', 'ratio') },
        { key: 'cart_cost', label: '加购成本', numeric: true, render: (value, row) => metricElement(row, 'cart_cost', 'money') },
      ],
      rows,
      emptyMessage,
    });
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
