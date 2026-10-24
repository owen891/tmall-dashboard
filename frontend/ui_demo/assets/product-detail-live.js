(function () {
  // `/products/<product_id>` carries the id as the last segment. `/product-detail`
  // is the id-less deep link: its last segment is the route name itself, so it
  // must not be mistaken for a product id. 静态文件路径（`/pages/product-detail.html`，
  // 含桌面端 file:// 场景）带 .html 后缀，同样不是 id —— 否则会去请求
  // `/api/products/product-detail.html/detail` 并报 404。
  const segments = location.pathname.split('/');
  const lastSegment = segments[segments.length - 1] || '';
  const id = lastSegment && lastSegment !== 'product-detail' && !/\.html?$/i.test(lastSegment) ? decodeURIComponent(lastSegment) : '';
  const $ = (selector) => document.querySelector(selector);
  const $$ = (selector) => [...document.querySelectorAll(selector)];
  const setText = (selector, value) => $$(selector).forEach((node) => { node.textContent = value ?? '--'; });
  // 流量来源渠道名来自生意参谋采集数据，会同时插进 HTML 属性值与文本节点，
  // 必须转义——否则渠道名里的双引号/尖括号会闭合属性或注入标签。
  const escapeHtml = window.DemoFormat?.escapeHtml
    ? window.DemoFormat.escapeHtml
    : (v) => String(v ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
  const money = (value) => value == null ? '--' : `¥${Number(value).toLocaleString('zh-CN', { maximumFractionDigits: 2 })}`;
  const percent = (value) => value == null ? '--' : `${(Number(value) * 100).toFixed(2)}%`;
  const pct = (value) => value == null ? '--' : `${Number(value).toFixed(1)}%`;
  const actionStatusLabels = { draft: '草稿', pending_execution: '待执行', executing: '执行中', observing: '观察中', pending_review: '待复盘', blocked: '阻塞', calculation_failed: '计算失败', completed: '已完成', cancelled: '已取消' };
  const actionStatus = (value) => actionStatusLabels[value] || value || '--';
  const mutationError = (error, fallback = '操作失败，请重试') => {
    const status = $('[data-product-detail-action-status]') || $('[data-product-detail-status]');
    if (status) status.textContent = error?.message || fallback;
  };
  const detailMetricKeys = new Set(['payment_qty', 'search_visitors', 'paid_ipv', 'organic_ipv', 'presale_amount', 'presale_qty', 'data_source']);
  const row = (label, value) => { const node = document.createElement('div'); node.className = 'status-list__item'; const left = document.createElement('span'); left.className = 'status-list__label'; left.textContent = label; const right = document.createElement('span'); right.className = 'status-list__value'; right.textContent = value ?? '--'; node.append(left, right); return node; };
  const transitions = { draft: ['pending_execution', 'cancelled'], pending_execution: ['executing', 'blocked', 'cancelled'], executing: ['observing', 'blocked', 'cancelled'], observing: ['pending_review', 'blocked', 'calculation_failed'], pending_review: ['blocked'], blocked: ['pending_execution', 'cancelled'], calculation_failed: ['observing', 'blocked'], completed: ['pending_review'] };
  let detailPayload = null;
  let selectedRange = {};
  const detailTabs = new Set(['overview', 'trend', 'flow-source', 'search', 'trade', 'promotion', 'granular', 'lifecycle', 'actions', 'evidence']);

  // 单品流量来源树形展开状态
  const itemFlowExpanded = new Set();
  const themeLoaded = new Set();
  const themeCache = new Map();

  const themeAvailabilityLabels = {
    available: '数据可用',
    partial: '部分可用',
    'no-data': '暂无数据',
    'missing-fields': '字段缺失',
    'source-unavailable': '来源不可用',
    'calculation-failed': '计算失败',
  };

  function number(value, digits = 0) {
    return value == null ? '--' : Number(value).toLocaleString('zh-CN', { maximumFractionDigits: digits });
  }

  function replaceTableBody(target, columns, rows, emptyMessage, renderRow = null) {
    if (!target || !window.TmallUI?.table?.mount) return;
    window.TmallUI.table.mount(target, { columns, rows, emptyMessage, renderRow });
  }

  function themeRange() {
    const state = window.TmallDateRange?.getState?.() || {};
    const rows = Array.isArray(detailPayload?.data?.daily_trend) ? detailPayload.data.daily_trend : [];
    const coverage = detailPayload?.data?.evidence_summary?.coverage || {};
    const startDate = selectedRange.startDate || state.startDate || coverage.start || rows[0]?.date || detailPayload?.data?.summary?.data_cutoff_date || '';
    const endDate = selectedRange.endDate || state.endDate || coverage.end || rows.at(-1)?.date || detailPayload?.data?.summary?.data_cutoff_date || startDate;
    return { startDate, endDate };
  }

  function themeRangeKey() {
    const range = themeRange();
    return `${range.startDate}|${range.endDate}`;
  }

  function setThemeStatus(selector, availability, fallback = '--') {
    const node = $(selector);
    if (!node) return;
    node.textContent = themeAvailabilityLabels[availability] || fallback;
  }

  function renderSearchAnalysis(data) {
    const summary = data?.summary || {};
    const rows = Array.isArray(data?.daily_trend) ? data.daily_trend : [];
    const hasSearchFact = summary.search_visitors != null || rows.some((item) => item.search_visitors != null);
    setThemeStatus('[data-product-search-status]', hasSearchFact ? 'available' : 'missing-fields');
    const values = {
      search_visitors: summary.search_visitors,
      search_ratio: summary.search_ratio,
      search_conversion: summary.search_conversion,
      search_click_rate: summary.search_click_rate,
    };
    const formatters = {
      search_visitors: (value) => number(value),
      search_ratio: percent,
      search_conversion: percent,
      search_click_rate: percent,
    };
    Object.entries(values).forEach(([key, value]) => setText(`[data-product-search-kpi="${key}"]`, formatters[key](value)));

    const target = $('[data-product-search-trend]');
    if (target) {
      replaceTableBody(target, [
        { key: 'date', label: '日期' }, { key: 'search_visitors', label: '搜索访客', numeric: true },
        { key: 'search_ratio', label: '搜索占比', numeric: true }, { key: 'search_conversion', label: '搜索转化率', numeric: true },
        { key: 'search_click_rate', label: '搜索点击率', numeric: true },
      ], rows.map((item) => {
        const searchVisitors = item.search_visitors;
        const itemVisitors = item.product_visitors;
        return { date: item.date, search_visitors: number(searchVisitors), search_ratio: percent(item.search_ratio ?? (searchVisitors != null && itemVisitors ? searchVisitors / itemVisitors : null)), search_conversion: percent(item.search_conversion), search_click_rate: percent(item.search_click_rate) };
      }), '暂无可展示的搜索日度数据');
    }

    const keywords = $('[data-product-search-keywords]');
    if (keywords) {
      keywords.textContent = hasSearchFact
        ? '当前数据源提供商品级搜索汇总，但没有可验证的商品级关键词归因，暂不展示关键词排名或标题建议。'
        : '当前数据源没有可验证的商品级搜索字段，暂不展示搜索指标、关键词排名或标题建议。';
    }
  }

  function renderPromotionAnalysis(payload) {
    const data = payload?.data || {};
    const summary = data.summary || {};
    setThemeStatus('[data-product-promotion-status]', payload?.availability || (data.campaigns?.length || data.channel_mix?.length ? 'available' : 'no-data'));
    const values = {
      ad_spend: summary.ad_spend,
      attributed_payment_amount: summary.attributed_payment_amount,
      roi: summary.roi,
      cvr: summary.cvr,
    };
    const formatters = { ad_spend: money, attributed_payment_amount: money, roi: (value) => value == null ? '--' : Number(value).toFixed(2), cvr: percent };
    Object.entries(values).forEach(([key, value]) => setText(`[data-product-promotion-kpi="${key}"]`, formatters[key](value)));

    const channels = $('[data-product-promotion-channels]');
    const channelRows = Array.isArray(data.channel_mix) ? data.channel_mix : [];
    if (channels) {
      replaceTableBody(channels, [
        { key: 'channel', label: '渠道' }, { key: 'ad_spend', label: '推广花费', numeric: true },
        { key: 'attributed_payment_amount', label: '推广成交', numeric: true }, { key: 'spend_share', label: '花费占比', numeric: true },
        { key: 'roi', label: 'ROI', numeric: true }, { key: 'ctr', label: '点击率', numeric: true }, { key: 'cvr', label: '转化率', numeric: true },
      ], channelRows.map((item) => ({ channel: item.channel || '--', ad_spend: money(item.ad_spend), attributed_payment_amount: money(item.attributed_payment_amount), spend_share: percent(item.spend_share), roi: item.roi == null ? '--' : Number(item.roi).toFixed(2), ctr: percent(item.ctr), cvr: percent(item.cvr) })), '暂无推广渠道数据');
    }

    const campaigns = $('[data-product-promotion-campaigns]');
    const campaignRows = Array.isArray(data.campaigns) ? data.campaigns : [];
    if (campaigns) {
      replaceTableBody(campaigns, [
        { key: 'campaign', label: '计划' }, { key: 'channel', label: '渠道' }, { key: 'plan_type', label: '计划类型' },
        { key: 'ad_spend', label: '推广花费', numeric: true }, { key: 'attributed_payment_amount', label: '推广成交', numeric: true },
        { key: 'roi', label: 'ROI', numeric: true }, { key: 'clicks', label: '点击量', numeric: true }, { key: 'cvr', label: '转化率', numeric: true },
      ], campaignRows, '暂无可下钻的推广计划', (item) => {
        const tr = document.createElement('tr');
        const name = document.createElement('td');
        const button = document.createElement('button'); button.type = 'button'; button.className = 'ui-button ui-button--link'; button.textContent = item.campaign_name || item.campaign_id || '--'; button.addEventListener('click', () => loadCampaignDetail(item.campaign_id));
        name.appendChild(button); tr.appendChild(name);
        [item.channel || '--', item.plan_type || '--', money(item.ad_spend), money(item.attributed_payment_amount), item.roi == null ? '--' : Number(item.roi).toFixed(2), number(item.clicks), percent(item.cvr)].forEach((value, index) => { const td = document.createElement('td'); td.textContent = value; if (index >= 2) td.className = 'num'; tr.appendChild(td); });
        return tr;
      });
    }

    const limitations = $('[data-product-promotion-limitations]');
    if (limitations) limitations.textContent = (data.limitations || []).join('；') || '当前日期范围内未发现额外限制。';
    const detail = $('[data-product-promotion-campaign-detail]');
    if (detail && !campaignRows.length) detail.replaceChildren(row('计划下钻', '暂无可下钻计划'));
  }

  function renderTradeAnalysis(payload) {
    const data = payload?.data || {};
    const summary = data.summary || {};
    const availability = payload?.availability || 'no-data';
    setThemeStatus('[data-product-trade-status]', availability);
    const values = {
      payment_amount: summary.payment_amount,
      refund_amount: summary.refund_amount,
      refund_rate: summary.refund_rate,
      net_sales: summary.net_sales,
    };
    const formatters = { payment_amount: money, refund_amount: money, refund_rate: percent, net_sales: money };
    Object.entries(values).forEach(([key, value]) => setText(`[data-product-trade-kpi="${key}"]`, formatters[key](value)));

    const target = $('[data-product-trade-trend]');
    const rows = Array.isArray(data.trend) ? data.trend : [];
    if (target) {
      replaceTableBody(target, [
        { key: 'date', label: '日期' }, { key: 'payment_amount', label: '支付金额', numeric: true }, { key: 'refund_amount', label: '退款金额', numeric: true },
        { key: 'refund_rate', label: '退款率', numeric: true }, { key: 'net_sales', label: '净销售额', numeric: true }, { key: 'buyers', label: '支付买家', numeric: true }, { key: 'payment_qty', label: '支付件数', numeric: true },
      ], rows.map((item) => ({ date: item.date, payment_amount: money(item.payment_amount), refund_amount: money(item.refund_amount), refund_rate: percent(item.refund_rate), net_sales: money(item.net_sales), buyers: number(item.buyers), payment_qty: number(item.payment_qty) })), '当前日期范围没有商品交易事实');
    }

    const limitations = $('[data-product-trade-limitations]');
    if (limitations) {
      limitations.replaceChildren(
        row('数据状态', themeAvailabilityLabels[availability] || availability),
        row('覆盖范围', `${payload?.freshness?.start || '--'} 至 ${payload?.freshness?.end || '--'}`),
        row('数据来源', (payload?.source_batches || []).map((item) => `${item.source}: ${item.row_count}`).join('、') || 'daily_data'),
        row('不可推断项', '当前没有订单明细、SKU、区域或小时粒度事实，相关主题不会被估算。'),
      );
    }
  }

  function renderGranularCapabilities(payload) {
    const themes = Array.isArray(payload?.data?.themes) ? payload.data.themes : [];
    const target = $('[data-product-granular-themes]');
    const limitations = $('[data-product-granular-limitations]');
    setThemeStatus('[data-product-granular-status]', payload?.availability || 'no-data');
    const labels = { available: '数据可用', partial: '部分可用', 'no-data': '暂无数据', 'missing-fields': '字段缺失', 'source-unavailable': '来源不可用' };
    const capabilityLabels = { sku_ranking: 'SKU 排名', sku_contribution: 'SKU 贡献', region_ranking: '地域排名', region_conversion: '地域转化', hourly_trend: '小时趋势', peak_periods: '高峰时段', export: '导出' };
    const readinessLabels = { sku_ranking: 'SKU 排名', sku_contribution: 'SKU 贡献', region_ranking: '地域排名', region_conversion: '地域转化', hourly_trend: '小时趋势', peak_periods: '高峰时段', export: '导出' };
    const cards = themes.map((theme) => {
      const card = document.createElement('article');
      card.className = 'product-granular-card';
      const header = document.createElement('div'); header.className = 'product-granular-card__header';
      const title = document.createElement('h3'); title.textContent = theme.label || theme.key;
      const badge = document.createElement('span'); badge.className = 'ui-badge'; badge.textContent = labels[theme.availability] || theme.availability || '--';
      header.append(title, badge);
      const meta = document.createElement('p'); meta.className = 'product-granular-card__meta'; meta.textContent = `粒度：${(theme.grain || []).join(' × ')} · 来源：${theme.source_table || '--'}`;
      const coverage = document.createElement('p'); coverage.className = 'product-granular-card__coverage';
      if (theme.coverage?.row_count) {
        const dimension = theme.coverage.dimension_count == null ? '' : ` · ${number(theme.coverage.dimension_count)} 个维度值`;
        coverage.textContent = `覆盖 ${number(theme.coverage.row_count)} 行${dimension} · ${theme.coverage.start || '--'} 至 ${theme.coverage.end || '--'} · 更新 ${theme.coverage.latest_update || '未提供'}`;
      } else coverage.textContent = '当前商品暂无可用事实行';
      const list = document.createElement('div'); list.className = 'product-granular-card__capabilities';
      (theme.capabilities || []).forEach((key) => { const chip = document.createElement('span'); chip.className = 'ui-badge'; chip.textContent = capabilityLabels[key] || key; list.appendChild(chip); });
      if (!theme.capabilities?.length) { const chip = document.createElement('span'); chip.className = 'product-granular-card__muted'; chip.textContent = '当前不开放分析能力'; list.appendChild(chip); }
      const readiness = document.createElement('div'); readiness.className = 'product-granular-card__readiness';
      (theme.capability_readiness || []).forEach((item) => {
        const line = document.createElement('p');
        line.className = item.available ? 'is-ready' : 'is-blocked';
        line.textContent = `${readinessLabels[item.key] || item.key}：${item.available ? '字段满足' : `缺少 ${item.missing_columns.join('、')}`}`;
        readiness.appendChild(line);
      });
      if (theme.missing_inputs?.length) {
        const missing = document.createElement('p'); missing.className = 'product-granular-card__missing';
        missing.textContent = `接入条件：${theme.missing_inputs.join('、')}`;
        readiness.appendChild(missing);
      }
      const canAnalyze = (theme.capabilities || []).some((key) => key !== 'export');
      if (canAnalyze) {
        const actions = document.createElement('div'); actions.className = 'product-granular-card__actions';
        const button = document.createElement('button'); button.type = 'button'; button.className = 'ui-button ui-button--ghost'; button.dataset.productGranularOpen = ''; button.dataset.themeKey = theme.key;
        const icon = document.createElement('i'); icon.dataset.lucide = 'bar-chart-3'; const label = document.createElement('span'); label.textContent = '查看下钻'; button.append(icon, label); actions.appendChild(button); card.appendChild(actions);
      }
      card.append(header, meta, coverage, list, readiness);
      return card;
    });
    if (target) target.replaceChildren(...(cards.length ? cards : [Object.assign(document.createElement('div'), { className: 'product-theme-unavailable', textContent: '未返回粒度能力状态。' })]));
    $$('[data-product-granular-open]').forEach((button) => button.addEventListener('click', () => loadGranularAnalysis(button.dataset.themeKey)));
    window.lucide?.createIcons();
    if (limitations) limitations.replaceChildren(
      row('证据等级', payload?.evidence_level || 'insufficient'),
      row('查询范围', `${payload?.filters?.start || '--'} 至 ${payload?.filters?.end || '--'}`),
      row('缺少输入', (payload?.missing_inputs || []).join('、') || '无'),
      row('限制说明', (payload?.limitations || []).join('；') || '无'),
    );
    renderGranularAnalysis(payload?.data?.analysis || null);
  }

  function renderGranularAnalysis(analysis) {
    const panel = $('[data-product-granular-analysis]');
    const title = $('[data-product-granular-analysis-title]');
    const status = $('[data-product-granular-analysis-status]');
    const head = $('[data-product-granular-analysis-head]');
    const body = $('[data-product-granular-analysis-body]');
    if (!panel || !head || !body) return;
    if (!analysis) {
      panel.hidden = true;
      return;
    }
    panel.hidden = false;
    title.textContent = `${analysis.label || analysis.key || '主题'}下钻`;
    status.textContent = themeAvailabilityLabels[analysis.availability] || analysis.availability || '--';
    const columnMap = {
      sku: [['dimension_value', 'SKU'], ['sku_name', 'SKU名称'], ['sku_properties', '规格'], ['payment_amount', '支付金额'], ['payment_quantity', '支付件数'], ['buyers', '买家数'], ['refund_amount', '退款金额']],
      region: [['dimension_value', '地域'], ['region_name', '地域名称'], ['visitors', '访客数'], ['buyers', '买家数'], ['payment_amount', '支付金额'], ['conversion_rate', '转化率']],
      hour: [['dimension_value', '小时'], ['visitors', '访客数'], ['buyers', '买家数'], ['payment_amount', '支付金额'], ['ad_spend', '推广花费'], ['conversion_rate', '转化率']],
    };
    const rows = Array.isArray(analysis.rows) ? analysis.rows : [];
    const keys = new Set(['dimension_value', ...(analysis.analysis_fields || []), 'conversion_rate']);
    const columns = (columnMap[analysis.key] || []).filter(([key]) => keys.has(key) && (key === 'dimension_value' || rows.some((item) => item[key] != null)));
    if (window.TmallUI?.table?.mount) window.TmallUI.table.mount(body, {
      caption: `${analysis.label || analysis.key || '主题'}下钻结果`,
      columns: columns.map(([key, label]) => ({
        key,
        label,
        numeric: ['payment_amount', 'refund_amount', 'ad_spend', 'payment_quantity', 'buyers', 'visitors', 'conversion_rate'].includes(key),
        render: (value) => value == null ? '--' : key === 'payment_amount' || key === 'refund_amount' || key === 'ad_spend' ? money(value) : key === 'conversion_rate' ? percent(value) : key === 'payment_quantity' || key === 'buyers' || key === 'visitors' ? number(value) : String(value),
      })),
      rows,
      emptyMessage: analysis.coverage?.row_count ? '当前字段条件下暂无可展示的下钻行' : '当前主题没有真实事实行',
    });
  }

  async function loadGranularCapabilities() {
    const range = themeRange();
    const cacheKey = `granular|${id}|${range.startDate}|${range.endDate}`;
    if (themeCache.has(cacheKey)) { renderGranularCapabilities(themeCache.get(cacheKey)); return; }
    setThemeStatus('[data-product-granular-status]', 'loading', '加载中…');
    try {
      const query = new URLSearchParams();
      if (range.startDate) query.set('start', range.startDate);
      if (range.endDate) query.set('end', range.endDate);
      const payload = await DemoApi.domainRequest(`/api/products/${encodeURIComponent(id)}/granular-capabilities?${query}`);
      themeCache.set(cacheKey, payload); themeLoaded.add('granular'); renderGranularCapabilities(payload);
    } catch (error) {
      setThemeStatus('[data-product-granular-status]', 'calculation-failed');
      $('[data-product-granular-limitations]')?.replaceChildren(row('粒度能力', error.message || '加载失败，请重试。'));
    }
  }

  async function loadGranularAnalysis(themeKey) {
    const range = themeRange();
    const panel = $('[data-product-granular-analysis]');
    const status = $('[data-product-granular-analysis-status]');
    if (panel) panel.hidden = false;
    if (status) status.textContent = '加载中…';
    try {
      const query = new URLSearchParams({ theme: themeKey, limit: '100' });
      if (range.startDate) query.set('start', range.startDate);
      if (range.endDate) query.set('end', range.endDate);
      const payload = await DemoApi.domainRequest(`/api/products/${encodeURIComponent(id)}/granular-capabilities?${query}`);
      renderGranularAnalysis(payload?.data?.analysis || null);
      panel?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    } catch (error) {
      if (status) status.textContent = '加载失败';
      const body = $('[data-product-granular-analysis-body]');
      if (body) body.innerHTML = `<tr><td>下钻失败：${escapeHtml(error.message || '请重试')}</td></tr>`;
    }
  }

  async function loadCampaignDetail(campaignId) {
    const target = $('[data-product-promotion-campaign-detail]');
    if (!campaignId || !target) return;
    const range = themeRange();
    target.replaceChildren(row('计划下钻', '加载中…'));
    try {
      const query = new URLSearchParams({ start: range.startDate, end: range.endDate, campaign_id: campaignId });
      const payload = await DemoApi.domainRequest(`/api/promotion/campaign-detail?${query}`);
      const data = payload.data || {};
      const summary = data.summary || {};
      target.replaceChildren(
        row('计划', summary.campaign_name || campaignId),
        row('投放方式', summary.plan_type || '--'),
        row('花费 / 成交', `${money(summary.ad_spend)} / ${money(summary.attributed_payment_amount)}`),
        row('ROI / 点击转化率', `${summary.roi == null ? '--' : Number(summary.roi).toFixed(2)} / ${percent(summary.cvr)}`),
        row('覆盖商品', number((data.products || []).length)),
      );
    } catch (error) {
      target.replaceChildren(row('计划下钻', error.message || '计划详情加载失败'));
    }
  }

  async function loadTheme(theme) {
    if (theme === 'search') {
      if (detailPayload?.data) renderSearchAnalysis(detailPayload.data);
      return;
    }
    if (theme === 'trade') {
      const range = themeRange();
      if (!range.startDate || !range.endDate) {
        setThemeStatus('[data-product-trade-status]', 'missing-fields');
        return;
      }
      const cacheKey = `trade|${id}|${range.startDate}|${range.endDate}`;
      if (themeCache.has(cacheKey)) {
        renderTradeAnalysis(themeCache.get(cacheKey));
        return;
      }
      setThemeStatus('[data-product-trade-status]', 'loading', '加载中…');
      try {
        const query = new URLSearchParams({ start: range.startDate, end: range.endDate });
        const payload = await DemoApi.domainRequest(`/api/products/${encodeURIComponent(id)}/trade?${query}`);
        themeCache.set(cacheKey, payload);
        themeLoaded.add('trade');
        renderTradeAnalysis(payload);
      } catch (error) {
        setThemeStatus('[data-product-trade-status]', 'calculation-failed');
        $('[data-product-trade-limitations]')?.replaceChildren(row('交易主题', error.message || '交易分析加载失败，请重试。'));
      }
      return;
    }
    if (theme !== 'promotion') return;
    const range = themeRange();
    if (!range.startDate || !range.endDate) {
      setThemeStatus('[data-product-promotion-status]', 'missing-fields');
      $('[data-product-promotion-limitations]')?.replaceChildren(document.createTextNode('当前未取得完整日期范围，无法请求推广计划明细。'));
      return;
    }
    const cacheKey = `promotion|${id}|${range.startDate}|${range.endDate}`;
    if (themeCache.has(cacheKey)) {
      renderPromotionAnalysis(themeCache.get(cacheKey));
      return;
    }
    setThemeStatus('[data-product-promotion-status]', 'loading', '加载中…');
    try {
      const query = new URLSearchParams({ start: range.startDate, end: range.endDate });
      const payload = await DemoApi.domainRequest(`/api/products/${encodeURIComponent(id)}/promotion?${query}`);
      themeCache.set(cacheKey, payload);
      themeLoaded.add('promotion');
      renderPromotionAnalysis(payload);
    } catch (error) {
      setThemeStatus('[data-product-promotion-status]', 'calculation-failed');
      $('[data-product-promotion-limitations]')?.replaceChildren(document.createTextNode(error.message || '推广分析加载失败，请重试。'));
      const channels = $('[data-product-promotion-channels]');
      const campaigns = $('[data-product-promotion-campaigns]');
      if (channels) channels.innerHTML = '<tr><td colspan="7">推广分析加载失败</td></tr>';
      if (campaigns) campaigns.innerHTML = '<tr><td colspan="8">推广分析加载失败</td></tr>';
    }
  }

  function selectDetailTab(tab, { updateHash = true, focus = false } = {}) {
    const active = detailTabs.has(tab) ? tab : 'overview';
    $$('[data-product-detail-tab]').forEach((button) => {
      const selected = button.dataset.productDetailTab === active;
      button.setAttribute('aria-selected', String(selected));
      button.tabIndex = selected ? 0 : -1;
      if (selected && focus) button.focus();
    });
    $$('[data-product-detail-panel]').forEach((panel) => {
      panel.hidden = panel.dataset.productDetailPanel !== active;
    });
    if (updateHash) history.replaceState(null, '', `${location.pathname}${location.search}#${active}`);
    if (active === 'search' || active === 'trade' || active === 'promotion') loadTheme(active);
    if (active === 'granular') loadGranularCapabilities();
  }

  function bindWorkbenchNavigation() {
    $$('[data-product-detail-tab]').forEach((button) => {
      button.addEventListener('click', () => selectDetailTab(button.dataset.productDetailTab));
      button.addEventListener('keydown', (event) => {
        if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
        const tabs = $$('[data-product-detail-tab]');
        const index = tabs.indexOf(button);
        const nextIndex = event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1 : (index + (event.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length;
        event.preventDefault();
        selectDetailTab(tabs[nextIndex].dataset.productDetailTab, { focus: true });
      });
    });
    const back = $('[data-product-detail-back]');
    const source = new URLSearchParams(location.search);
    const backQuery = new URLSearchParams();
    ['rule_key', 'category_mode', 'period', 'page', 'page_size', 'starred', 'search', 'tier', 'style', 'product_type', 'product_time_node', 'product_growth_stage', 'status', 'sort', 'order', 'lifecycle_stage', 'seasonality', 'has_pending_action'].forEach((key) => { if (source.get(key)) backQuery.set(key, source.get(key)); });
    if (back && backQuery.toString()) back.href = `/products?${backQuery}`;
    const referrer = document.referrer;
    let cameFromProducts = false;
    try { cameFromProducts = referrer && new URL(referrer).origin === window.location.origin && new URL(referrer).pathname === '/products'; } catch (_) { cameFromProducts = false; }
    back?.addEventListener('click', (event) => {
      if (!cameFromProducts) return;
      event.preventDefault();
      window.history.back();
    });
    selectDetailTab(location.hash.slice(1), { updateHash: false });
    window.addEventListener('hashchange', () => selectDetailTab(location.hash.slice(1), { updateHash: false }));
  }
  const requestAction = (action, suffix, body) => DemoApi.domainRequest(`/api/actions/${encodeURIComponent(action.id)}${suffix}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  function actionCard(action) {
    const card = document.createElement('div'); card.className = 'status-list__item';
    const content = document.createElement('div'); content.className = 'status-list__value';
    const title = document.createElement('strong'); title.textContent = `${action.planned_at || '--'} · ${action.action_type || '--'} · ${actionStatus(action.status)}`;
    const detail = document.createElement('div'); detail.textContent = `目的：${action.purpose_note || '--'}；动作：${action.action_detail || '--'}；结果：${action.calculation_note || '--'}；复盘：${action.review_conclusion || '--'}；历史：${(action.history || []).length} 条`;
    content.append(title, detail);
    const controls = document.createElement('div'); controls.className = 'button-row';
    (transitions[action.status] || []).forEach((target) => {
      const button = document.createElement('button'); button.type = 'button'; button.className = 'ui-button ui-button--ghost'; button.textContent = `转为${actionStatus(target)}`;
      button.addEventListener('click', async () => {
        const body = { capability_key: 'product-detail.review_action', status: target, version: action.version };
        if (target === 'blocked') { body.blocked_reason = window.prompt('请输入阻塞原因') || ''; body.expected_recovery_at = window.prompt('请输入预计恢复日期（YYYY-MM-DD）') || ''; if (!body.blocked_reason || !body.expected_recovery_at) return; }
        button.disabled = true;
        try { await requestAction(action, '/transition', body); await load(); } catch (error) { mutationError(error, '更新运营动作状态失败，请重试'); } finally { if (button.isConnected) button.disabled = false; }
      }); controls.appendChild(button);
    });
    if (action.status === 'observing') {
      const button = document.createElement('button'); button.type = 'button'; button.className = 'ui-button ui-button--ghost'; button.textContent = '重新计算观察窗口';
      button.addEventListener('click', async () => { button.disabled = true; try { await DemoApi.domainRequest('/api/actions/recalculate', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ capability_key: 'product-detail.review_action' }) }); await load(); } catch (error) { mutationError(error, '重新计算观察窗口失败，请重试'); } finally { if (button.isConnected) button.disabled = false; } }); controls.appendChild(button);
    }
    if (action.status === 'pending_review') {
      const form = document.createElement('form'); form.className = 'modal-form__body';
      form.innerHTML = '<label>是否有效<select class="select" name="effective" aria-label="复盘结论是否有效"><option value="true">有效</option><option value="false">无效</option></select></label><label>变更原因<input class="input" name="reason" required></label><label>复盘结论<input class="input" name="conclusion" required></label><label>后续动作<input class="input" name="next_action" required></label><label>复盘人<input class="input" name="reviewer" value="运营人员" required></label><button class="ui-button ui-button--primary" type="submit">提交复盘</button>';
      form.addEventListener('submit', async (event) => { event.preventDefault(); const values = Object.fromEntries(new FormData(form)); const submit = form.querySelector('button[type="submit"]'); if (submit) submit.disabled = true; try { await requestAction(action, '/review', { ...values, capability_key: 'product-detail.review_action', effective: values.effective === 'true', version: action.version }); await load(); } catch (error) { mutationError(error, '提交复盘失败，请重试'); } finally { if (submit?.isConnected) submit.disabled = false; } }); content.appendChild(form);
    }
    card.append(content, controls); return card;
  }
  function renderHistory(rows) {
    const target = $('[data-product-detail-lifecycle-history]'); if (!target) return;
    replaceTableBody(target, [
      { key: 'created_at', label: '时间' }, { key: 'recommended_stage', label: '系统阶段' }, { key: 'manual_stage', label: '人工阶段' },
      { key: 'reason', label: '原因' }, { key: 'operator', label: '操作人' }, { key: 'version', label: '版本', numeric: true },
    ], (rows || []).map((item) => ({ created_at: item.created_at || '--', recommended_stage: item.recommended_stage || '--', manual_stage: item.manual_stage || '--', reason: item.reason || '--', operator: item.operator || '--', version: item.version || '--' })), '暂无生命周期历史');
  }
  function renderComparison(rows, contributions) {
    const target = $('[data-product-detail-period-comparison]');
    if (target) replaceTableBody(target, [
      { key: 'month', label: '月份' }, { key: 'net_sales', label: '净销售额', numeric: true }, { key: 'sales_change', label: '销售额变化', numeric: true },
      { key: 'visitor_change', label: '访客变化', numeric: true }, { key: 'anomalies', label: '异常' },
    ], (rows || []).map((item) => { const metrics = item.metrics || {}; return { month: item.month || '--', net_sales: metrics.net_sales?.current == null ? '--' : money(metrics.net_sales.current), sales_change: pct(metrics.net_sales?.change_pct), visitor_change: pct(metrics.product_visitors?.change_pct), anomalies: item.anomalies?.join('、') || '无明显变化' }; }), '暂无周期对比数据');
    const summary = $('[data-product-detail-contribution]'); if (summary) { const latest = (contributions || []).at(-1); summary.replaceChildren(latest ? row('贡献分析（非因果）', latest.drivers.map((driver) => `${driver.metric}: ${driver.delta == null ? '--' : Number(driver.delta).toFixed(2)}`).join('、')) : row('贡献分析', '暂无可比较周期')); }
  }
  function renderEvidence(summary) { const target = $('[data-product-detail-evidence]'); if (!target) return; const coverage = summary?.coverage || {}; target.replaceChildren(row('证据等级', summary?.level || '--'), row('覆盖范围', `${coverage.start || '--'} 至 ${coverage.end || '--'}（${coverage.days || 0} 天）`), row('数据来源', (summary?.sources || []).map((source) => `${source.source}: ${source.row_count}`).join('、') || '--'), row('缺失字段', (summary?.missing_fields || []).join('、') || '无'), row('限制说明', (summary?.unknowns || []).join('、') || '暂不支持严格因果归因')); }
  function renderProblemContext(context) {
    const panel = $('[data-product-problem-context]');
    if (!panel) return;
    if (!context) { panel.hidden = true; return; }
    panel.hidden = false;
    const statusLabels = { matched: '当前命中', 'not-matched': '当前未命中', 'not-computable': '当前不可计算' };
    const statusNode = document.createElement('span');
    statusNode.className = `product-problem-context__status--${context.status || 'not-computable'}`;
    statusNode.textContent = statusLabels[context.status] || context.status || '--';
    const summary = $('[data-product-problem-summary]');
    summary.replaceChildren(
      row('来源分群', context.rule_name || context.rule_key || '--'),
      row('当前状态', statusNode.textContent),
      row('当前周期', context.period || '--'),
      row('品类范围', context.category_mode || 'all'),
      row('证据范围', `${context.evidence?.coverage_start || '--'} 至 ${context.evidence?.coverage_end || '--'}（${context.evidence?.fact_days || 0} 天）`),
      row('缺少输入', (context.missing_fields || []).join('、') || '无'),
    );
    const checks = $('[data-product-problem-checks]');
    const checkRows = Array.isArray(context.checks) ? context.checks : [];
    checks.replaceChildren(...checkRows.map((item) => {
      const node = document.createElement('div');
      node.className = 'product-problem-context__item';
      const label = document.createElement('strong');
      label.textContent = item.label || item.key || '--';
      const value = document.createElement('small');
      const actual = item.value == null ? '--' : (String(item.key).includes('rate') || String(item.key).includes('ratio') || String(item.key).includes('conversion') ? percent(item.value) : Number(item.value).toLocaleString('zh-CN', { maximumFractionDigits: 2 }));
      const threshold = item.threshold == null ? '--' : (String(item.key).includes('rate') || String(item.key).includes('ratio') || String(item.key).includes('conversion') ? percent(item.threshold) : Number(item.threshold).toLocaleString('zh-CN', { maximumFractionDigits: 2 }));
      value.textContent = `${actual} ${item.operator || ''} ${threshold} · ${item.matched ? '满足' : '未满足'}`;
      node.append(label, value);
      return node;
    }));
    if (!checkRows.length) checks.appendChild(row('命中依据', context.matched ? '规则无需额外指标' : '暂无可展示的规则条件'));
    const suggestions = $('[data-product-problem-suggestions]');
    suggestions.replaceChildren(...(context.suggested_actions || []).map((item, index) => {
      const node = document.createElement('div');
      node.className = 'product-problem-context__item';
      node.textContent = `${index + 1}. ${item}`;
      return node;
    }));
    if (!(context.suggested_actions || []).length) suggestions.appendChild(row('建议动作', '暂无建议动作'));
  }
  function formatDetailMetric(metric) {
    if (metric?.value == null || metric.value === '') return '--';
    if (metric.unit === 'currency') return money(metric.value);
    if (metric.unit === 'ratio') return percent(metric.value);
    if (metric.unit === 'number') return Number(metric.value).toLocaleString('zh-CN', { maximumFractionDigits: 0 });
    return String(metric.value);
  }
  // 利润色块（与商品列表 .profit-block 同语义：红=盈利、绿=亏损、灰=空）
  function profitBlockNode(value) {
    const block = document.createElement('span');
    block.className = 'profit-block';
    const num = Number(value);
    if (value === null || value === undefined || value === '' || !Number.isFinite(num)) {
      block.classList.add('profit-block--empty');
      block.textContent = '--';
      return block;
    }
    if (num > 0) block.classList.add('profit-block--positive');
    else if (num < 0) block.classList.add('profit-block--negative');
    else block.classList.add('profit-block--zero');
    block.textContent = `${num > 0 ? '+' : ''}${Math.round(num).toLocaleString('zh-CN')}`;
    return block;
  }

  // 目标达成率：净销售额卡底部显示「目标达成 xx%」（product_targets，当月口径）
  async function loadTargetAchievement(summary) {
    const hint = document.querySelector('[data-product-detail-target-rate]');
    if (!hint || !id) return;
    const period = (summary?.data_cutoff_date || '').slice(0, 7) || new Date().toISOString().slice(0, 7);
    try {
      const payload = await DemoApi.domainRequest(`/api/products/${encodeURIComponent(id)}/targets`);
      const current = (payload.data || []).find((row) => row.period === period);
      if (current && current.achievement_rate != null) {
        hint.textContent = `月目标达成 ${percent(current.achievement_rate)}（${period}）`;
      } else if (current) {
        hint.textContent = `${period} 月已设目标，暂无经实数据`;
      } else {
        hint.textContent = `${period} 月未设目标 · 列表页可设置`;
      }
    } catch (_) { /* 目标服务不可用时保留原提示 */ }
  }

  // 成本结构（利润瀑布原料）：文字版一行，缺项跳过
  function renderCostStructure(structure) {
    const target = document.querySelector('[data-product-detail-info]');
    if (!target || !structure) return;
    const items = [
      ['货品成本', structure.product_cost], ['销售成本', structure.sales_cost],
      ['定制成本', structure.custom_cost], ['物流成本', structure.logistics_cost],
      ['平台花费', structure.platform_fee], ['售后损耗', structure.after_sales_loss],
      ['其他成本', structure.other_cost], ['推广花费(账单)', structure.ad_spend],
    ].filter(([, value]) => value != null && Number(value) !== 0);
    if (!items.length) return;
    const parts = items.map(([label, value]) => `${label} ${money(value)}`).join(' · ');
    const line = row('成本结构(支付)', `${parts} ⇒ 利润 ${money(structure.operating_profit)}`);
    target.appendChild(line);
  }

  // 真缺失字段的「数据获取路径」提示（对齐 BI：缺数据的地方给入口，不静默 --）。
  // 依据 2026-10-24 全列 nz 审计：这些列全表无非零值，属「未采集」而非「被屏蔽」。
  const FIELD_SOURCE_HINTS = {
    paid_ipv: '未采集 · 源在达摩盘单品洞察（与生意参谋访客口径不一致，未混排）',
    organic_ipv: '未采集 · 源在达摩盘单品洞察',
    recommend_ipv: '未采集 · 源在达摩盘单品洞察',
    repurchase_users: '未采集 · 需 BI 商品总览复购列',
    repurchase_rate: '未采集 · 需 BI 商品总览复购列',
    presale_amount: '未采集 · 需 BI 预售报表',
    presale_qty: '未采集 · 需 BI 预售报表',
    cross_sell_qty: '未采集 · 需关联销售报表',
    cross_sell_rate: '未采集 · 需关联销售报表',
    cross_sell_categories: '未采集 · 需关联销售报表',
    order_amount: '未采集 · 需订单明细报表',
    order_conversion: '未采集 · 需订单明细报表',
    returning_payment_amount: '未采集 · 需订单明细报表',
    search_click_rate: '未采集 · 源在达摩盘搜索点击',
  };

  function renderDetailMetrics(metrics) {
    const target = $('[data-product-detail-detail-metrics]');
    if (!target) return;
    target.replaceChildren(...(metrics || []).filter((metric) => metric?.key && (detailMetricKeys.has(metric.key) || metric.value !== undefined)).map((metric) => {
      const card = document.createElement('article');
      card.className = `product-detail-metric${metric.value == null ? ' is-missing' : ''}`;
      const label = document.createElement('span'); label.className = 'product-detail-metric__label'; label.textContent = metric.label || metric.key;
      const value = document.createElement('strong'); value.className = 'product-detail-metric__value';
      if (metric.key === 'operating_profit' && metric.value != null) value.appendChild(profitBlockNode(metric.value));
      else value.textContent = formatDetailMetric(metric);
      const source = document.createElement('small'); source.className = 'product-detail-metric__source';
      if (metric.value != null) source.textContent = '当前日期范围';
      else {
        const hint = FIELD_SOURCE_HINTS[metric.key];
        source.textContent = hint || '字段缺失';
        if (hint) { source.classList.add('product-detail-metric__source--hint'); card.title = hint; }
      }
      card.append(label, value, source); return card;
    }));
  }

  // 加载单品流量来源数据（树形折叠展开）
  async function loadItemFlowSource(itemId, range = {}) {
    try {
      const rangeQuery = new URLSearchParams();
      if (range.startDate) rangeQuery.set('start', range.startDate);
      if (range.endDate) rangeQuery.set('end', range.endDate);
      const requestFor = (belong) => fetch(`/api/sycm/item-flow/summary?item_id=${encodeURIComponent(itemId)}&belong=${belong}${rangeQuery.toString() ? `&${rangeQuery}` : ''}`);
      // 优先「全程来源」（有层级树可展开），没有数据时回退「第一次访问来源」
      let d = await (await requestFor('all')).json();
      if (d.ok && !((d.data || {}).channels || []).length) {
        const fallback = await (await requestFor('farthest')).json();
        if (fallback.ok) d = fallback;
      }
      if (!d.ok) {
        const tbody = document.querySelector('[data-item-flow-table]');
        if (tbody) tbody.innerHTML = `<tr><td colspan="11" style="text-align:center;color:var(--text-secondary);padding:24px">${escapeHtml(d.message || '暂无流量来源数据')}</td></tr>`;
        return;
      }
      const data = d.data;
      const channels = data.channels || [];
      const totalUv = data.total_uv || 0;
      const totalPay = data.total_pay_amount || 0;

      // 根层渠道：parent_channel 指不到任何渠道的即为根层（两个口径通用）
      const channelNames = new Set(channels.map(ch => ch.channel_name));
      const level0 = channels.filter(ch => !ch.parent_channel || !channelNames.has(ch.parent_channel));
      const childrenMap = {};
      channels.forEach(ch => {
        const parent = ch.parent_channel || '';
        if (parent && channelNames.has(parent)) {
          if (!childrenMap[parent]) childrenMap[parent] = [];
          childrenMap[parent].push(ch);
        }
      });

      function buildTree(node, level) {
        const treeNode = { ...node, level: level, children: [] };
        const children = childrenMap[node.channel_name] || [];
        children.forEach(child => {
          treeNode.children.push(buildTree(child, level + 1));
        });
        treeNode.children.sort((a, b) => (b.uv || 0) - (a.uv || 0));
        return treeNode;
      }

      const tree = level0.map(ch => buildTree(ch, 1));
      tree.sort((a, b) => (b.uv || 0) - (a.uv || 0));
      tree.forEach(node => itemFlowExpanded.add(node.channel_name));

      const setText2 = (sel, val) => { const el = document.querySelector(sel); if (el) el.textContent = val; };
      // 卡片一律用商品维度去重值（渠道合计会把同一访客重复计入，与商品口径不可比）
      const totals = data.product_totals || null;
      const periodText = data.data_days > 1 ? `${data.start_date} ~ ${data.end_date}` : (data.start_date || '--');
      const compactMoney = (value) => '¥' + (value >= 10000 ? (value / 10000).toFixed(1) + '万' : value.toFixed(0));
      setText2('[data-item-flow-date]', periodText);
      setText2('[data-item-flow-total-uv]', totals ? totals.visitors.toLocaleString('zh-CN') : '--');
      setText2('[data-item-flow-total-pay]', totals ? compactMoney(totals.payment_amount) : '--');
      setText2('[data-item-flow-total-buyers]', totals ? totals.buyers.toLocaleString('zh-CN') : '--');
      setText2('[data-item-flow-channel-count]', level0.length);

      const tbody = document.querySelector('[data-item-flow-table]');
      if (!tbody) return;
      if (!tree.length) {
        tbody.innerHTML = '<tr><td colspan="11" style="text-align:center;color:var(--text-secondary);padding:24px">暂无流量来源数据</td></tr>';
        return;
      }

      // 渲染树形表格
      function renderNode(node) {
        const isExpanded = itemFlowExpanded.has(node.channel_name);
        const hasChildren = node.children.length > 0;
        const indent = (node.level - 1) * 20;

        const toggleBtn = hasChildren
          ? `<span class="toggle-btn" data-item-flow-toggle="${escapeHtml(node.channel_name)}">${isExpanded ? '−' : '+'}</span>`
          : `<span class="toggle-btn toggle-btn--empty">·</span>`;

        const uvPct = totalUv > 0 ? (node.uv / totalUv * 100).toFixed(1) + '%' : '--';
        const rate = node.pay_rate != null ? (node.pay_rate * 100).toFixed(2) + '%' : '--';
        const uvValue = node.uv > 0 && node.pay_amount != null ? '¥' + (node.pay_amount / node.uv).toFixed(2) : '--';

        let html = `<tr class="level-${node.level}">
          <td>
            <div class="channel-cell" style="padding-left:${indent}px">
              ${toggleBtn}
              <span class="channel-name ${hasChildren ? 'channel-name--clickable' : ''}" data-item-flow-channel="${escapeHtml(node.channel_name)}">${escapeHtml(node.channel_name)}</span>
            </div>
          </td>
          <td class="num">${(node.uv || 0).toLocaleString('zh-CN')}</td>
          <td class="num">${uvPct}</td>
          <td class="num">¥${node.pay_amount != null ? (node.pay_amount >= 10000 ? (node.pay_amount/10000).toFixed(1) + '万' : node.pay_amount.toFixed(0)) : '--'}</td>
          <td class="num">${(node.pay_buyer_count || 0).toLocaleString('zh-CN')}</td>
          <td class="num">${rate}</td>
          <td class="num">${uvValue}</td>
          <td class="num">${(node.cart_buyer_count || 0).toLocaleString('zh-CN')}</td>
          <td class="num">${node.uv > 0 && node.cart_buyer_count != null ? (node.cart_buyer_count / node.uv * 100).toFixed(2) + '%' : '--'}</td>
          <td class="num">${(node.collect_item_count || 0).toLocaleString('zh-CN')}</td>
          <td class="num">${(node.new_uv || 0).toLocaleString('zh-CN')}</td>
        </tr>`;

        if (isExpanded && hasChildren) {
          node.children.forEach(child => {
            html += renderNode(child);
          });
        }
        return html;
      }

      function renderTable() {
        let html = '';
        tree.forEach(node => { html += renderNode(node); });
        tbody.innerHTML = html;
        bindEvents();
      }

      function bindEvents() {
        tbody.querySelectorAll('[data-item-flow-toggle]').forEach(el => {
          el.addEventListener('click', (e) => {
            e.stopPropagation();
            const name = el.dataset.itemFlowToggle;
            if (itemFlowExpanded.has(name)) {
              itemFlowExpanded.delete(name);
            } else {
              itemFlowExpanded.add(name);
            }
            renderTable();
          });
        });
        tbody.querySelectorAll('[data-item-flow-channel]').forEach(el => {
          el.addEventListener('click', () => {
            const name = el.dataset.itemFlowChannel;
            if (itemFlowExpanded.has(name)) {
              itemFlowExpanded.delete(name);
            } else {
              itemFlowExpanded.add(name);
            }
            renderTable();
          });
        });
      }

      renderTable();

      // 渲染图表（用一级渠道）
      if (window.echarts && tree.length) {
        // 饼图
        const pieEl = document.getElementById('itemFlowPieChart');
        if (pieEl) {
          const pieChart = echarts.init(pieEl);
          const pieData = tree.slice(0, 8).map(ch => ({ name: ch.channel_name, value: ch.uv || 0 }));
          if (tree.length > 8) {
            const otherUv = tree.slice(8).reduce((s, ch) => s + (ch.uv || 0), 0);
            pieData.push({ name: '其他', value: otherUv });
          }
          pieChart.setOption({
            tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
            legend: { bottom: 0, textStyle: { fontSize: 10 } },
            series: [{
              type: 'pie',
              radius: ['35%', '65%'],
              center: ['50%', '42%'],
              itemStyle: { borderRadius: 4, borderColor: '#fff', borderWidth: 2 },
              label: { show: false },
              emphasis: { label: { show: true, fontSize: 12, fontWeight: 'bold' } },
              data: pieData,
            }],
            color: ['#3b82f6', '#ef4444', '#22c55e', '#f59e0b', '#8b5cf6', '#06b6d4', '#ec4899', '#84cc16', '#94a3b8'],
          });
        }

        // 柱状图
        const barEl = document.getElementById('itemFlowBarChart');
        if (barEl) {
          const barChart = echarts.init(barEl);
          const top10 = [...tree].sort((a, b) => (b.pay_amount || 0) - (a.pay_amount || 0)).slice(0, 10);
          const names = top10.map(ch => ch.channel_name.length > 5 ? ch.channel_name.slice(0, 5) + '...' : ch.channel_name);
          const barData = top10.map(ch => ch.pay_amount || 0);
          barChart.setOption({
            tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
            grid: { left: '3%', right: '4%', bottom: '15%', containLabel: true },
            xAxis: { type: 'category', data: names, axisLabel: { fontSize: 9, rotate: 30 } },
            yAxis: { type: 'value', axisLabel: { formatter: function(v) { return v >= 10000 ? (v/10000).toFixed(0) + '万' : v; } } },
            series: [{
              type: 'bar',
              data: barData,
              itemStyle: { color: '#22c55e', borderRadius: [3, 3, 0, 0] },
              barWidth: '50%',
            }],
          });
        }
      }
    } catch (err) {
      console.error('加载单品流量来源失败:', err);
    }
  }

  function renderProductImage(product) {
    const image = document.querySelector('[data-product-detail-image]');
    if (!image) return;
    const url = typeof product.image_url === 'string' ? product.image_url.trim() : '';
    image.alt = `${product.title || '商品'} 主图`;
    // Keep an already loaded image steady when the date range refreshes.
    if (url && image.getAttribute('src') === url && image.complete && image.naturalWidth > 0) {
      image.hidden = false;
      return;
    }
    image.hidden = true;
    image.removeAttribute('src');
    image.onload = () => { image.hidden = false; };
    image.onerror = () => { image.hidden = true; image.removeAttribute('src'); };
    if (url) image.src = url;
  }

  async function load(range) {
    // No product id: `/product-detail` was opened directly. Say how to get here
    // rather than requesting `/api/products//detail` and reporting that as a
    // calculation failure.
    if (!id) {
      DemoApi.renderDataState($('[data-product-detail-status]'), 'no-data', {
        message: '请从商品列表进入详情',
        retry: null,
      });
      return;
    }
    try {
      const previousRangeKey = `${selectedRange.startDate || ''}|${selectedRange.endDate || ''}`;
      selectedRange = range || window.TmallDateRange?.getState?.() || selectedRange || {};
      const nextRangeKey = `${selectedRange.startDate || ''}|${selectedRange.endDate || ''}`;
      if (previousRangeKey !== nextRangeKey) {
        themeCache.clear();
        themeLoaded.clear();
      }
      const query = new URLSearchParams(); if (selectedRange.startDate) query.set('start', selectedRange.startDate); if (selectedRange.endDate) query.set('end', selectedRange.endDate);
      const sourceParams = new URLSearchParams(location.search);
      ['rule_key', 'category_mode', 'period'].forEach((key) => { if (sourceParams.get(key)) query.set(key, sourceParams.get(key)); });
      const payload = await DemoApi.domainRequest(`/api/products/${encodeURIComponent(id)}/detail${query.toString() ? `?${query}` : ''}`); detailPayload = payload; const data = payload.data;
      setText('[data-product-detail-title]', data.product.title || id);
      renderProductImage(data.product);
      setText('[data-product-detail-meta]', `商品 ${id} · 数据截止 ${data.summary.data_cutoff_date || '--'}`);
      setText('[data-product-detail-breadcrumb]', `商品经营 / 商品列表 / ${data.product.title || id}`);
      $('[data-product-detail-meta]').textContent = `商品 ${id} · 数据截止 ${data.summary.data_cutoff_date || '--'}`;
      $('[data-product-detail-status]').textContent = `${DemoLabels.label('status', data.product.status, data.product.status || '--')} · ${data.product.manager || '未分配'}`;
      if (payload.availability === 'no-data') $('[data-product-detail-status]').textContent = '当前日期范围无商品日度数据 · 请调整日期范围或检查导入';
      $('[data-product-detail-info]').replaceChildren(row('分层 / 风格', `${DemoLabels.classification('tiers', data.product.tier, '--')} / ${DemoLabels.classification('styles', data.product.style, '--')}`), row('类目 / 场景', `${DemoLabels.clean(data.product.category, '--')} / ${DemoLabels.clean(data.product.scene, '--')}`), row('上架日期', DemoLabels.clean(data.product.list_date, '--')), row('商品负责人', DemoLabels.clean(data.product.manager, '--')), row('商品状态', DemoLabels.label('status', data.product.status, '--')), row('数据来源', data.summary.data_source || '--'), row('最后导入', data.summary.imported_at || '--'), row('数据截止', data.summary.data_cutoff_date || '--'));
      renderDetailMetrics(data.detail_metrics);
      [['payment_amount', money], ['net_sales', money], ['payment_conversion_rate', percent], ['expense_ratio', percent], ['average_order_value', money]].forEach(([key, format]) => { setText(`[data-product-detail-kpi="${key}"]`, format(data.summary[key])); });
      // 利润卡：色块语义（红盈绿亏）与商品列表一致；利润率写进卡底说明
      const profitNode = document.querySelector('[data-product-detail-kpi="operating_profit"]');
      if (profitNode) {
        profitNode.replaceChildren();
        profitNode.appendChild(profitBlockNode(data.summary.operating_profit));
      }
      setText('[data-product-detail-profit-rate]', data.summary.profit_rate != null ? `利润率 ${percent(data.summary.profit_rate)}` : '支付口径利润链');
      loadTargetAchievement(data.summary);
      renderCostStructure(data.summary.cost_structure);
      setText('[data-product-detail-stage]', data.lifecycle?.stage_label || data.lifecycle?.stage || '--');
      setText('[data-product-detail-days]', data.lifecycle?.continuous_valid_days ?? '--');
      setText('[data-product-detail-confidence]', `置信度：${DemoLabels.label('confidence', data.lifecycle?.confidence)} · ${data.lifecycle?.locked ? '人工' : '系统'}`);
      setText('[data-product-detail-rationale]', data.lifecycle?.rationale || '暂无判断依据');
      renderProblemContext(data.problem_context);
      const workbenchExportQuery = new URLSearchParams({ capability_key: 'product-detail.export' });
      if (selectedRange.startDate) workbenchExportQuery.set('start', selectedRange.startDate);
      if (selectedRange.endDate) workbenchExportQuery.set('end', selectedRange.endDate);
      ['rule_key', 'category_mode', 'period'].forEach((key) => { if (sourceParams.get(key)) workbenchExportQuery.set(key, sourceParams.get(key)); });
      $$('[data-product-detail-export]').forEach((link) => { link.href = `/api/products/${encodeURIComponent(id)}/detail/export?${workbenchExportQuery}`; });
      $('[data-product-detail-stage]').textContent = data.lifecycle?.stage_label || data.lifecycle?.stage || '--'; $('[data-product-detail-days]').textContent = data.lifecycle?.continuous_valid_days ?? '--'; $('[data-product-detail-confidence]').textContent = `置信度：${DemoLabels.label('confidence', data.lifecycle?.confidence)} · ${data.lifecycle?.locked ? '人工' : '系统'}`; $('[data-product-detail-rationale]').textContent = data.lifecycle?.rationale || '暂无判断依据';
      const trendRows = Array.isArray(data.daily_trend) ? data.daily_trend : [];
      const trend = $('[data-product-detail-trend]');
      replaceTableBody(trend, [
        { key: 'date', label: '日期' }, { key: 'payment_amount', label: '支付金额(支付)', numeric: true }, { key: 'net_sales', label: '净销售额(支付)', numeric: true },
        { key: 'operating_profit', label: '利润(支付预估)', numeric: true },
        { key: 'product_visitors', label: '商品访客', numeric: true }, { key: 'ad_spend', label: '推广花费(账单)', numeric: true },
      ], trendRows.map((item) => ({ date: item.date, payment_amount: money(item.payment_amount), net_sales: money(item.net_sales), operating_profit: item.operating_profit != null ? `${item.operating_profit > 0 ? '+' : ''}${Math.round(item.operating_profit).toLocaleString('zh-CN')}` : '--', product_visitors: item.product_visitors ?? '--', ad_spend: money(item.ad_spend) })), '暂无日度数据');
      const actions = $('[data-product-detail-actions]'); const actionRows = Array.isArray(data.actions) ? data.actions : []; actions.replaceChildren(...actionRows.map(actionCard)); if (!actionRows.length) actions.textContent = '暂无运营动作'; renderHistory(data.lifecycle_history); renderComparison(data.period_comparison, data.contribution_analysis); renderEvidence(data.evidence_summary);
      const exportLink = $('[data-product-detail-export]'); if (exportLink) { const exportQuery = new URLSearchParams({ capability_key: 'product-detail.export' }); if (selectedRange.startDate) exportQuery.set('start', selectedRange.startDate); if (selectedRange.endDate) exportQuery.set('end', selectedRange.endDate); ['rule_key', 'category_mode', 'period'].forEach((key) => { if (sourceParams.get(key)) exportQuery.set(key, sourceParams.get(key)); }); exportLink.href = `/api/products/${encodeURIComponent(id)}/detail/export?${exportQuery}`; }
      loadItemFlowSource(id, selectedRange);
      const activeTheme = location.hash.slice(1);
      if (activeTheme === 'search' || activeTheme === 'trade' || activeTheme === 'promotion') loadTheme(activeTheme);
      if (activeTheme === 'granular') loadGranularCapabilities();
    } catch (error) { DemoApi.renderDataState($('[data-product-detail-status]'), 'calculation-failed', { message: error.message, retry: load }); }
  }
  $('[data-product-detail-action-form]').addEventListener('submit', async (event) => { event.preventDefault(); if (Object.keys(detailPayload?.capabilities || {}).length && !DemoApi.can(detailPayload, 'can_create_action')) { $('[data-product-detail-action-status]').textContent = '当前数据条件不满足创建运营动作'; return; } const formElement = event.currentTarget; const form = new FormData(formElement); const source = detailPayload?.data?.problem_context || {}; const submit = formElement.querySelector('button[type="submit"]'); if (submit) { submit.disabled = true; submit.setAttribute('aria-busy', 'true'); } try { await DemoApi.domainRequest('/api/actions', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ capability_key: 'product-detail.create_action', product_id: id, purpose_type: 'increase_sales', purpose_note: form.get('purpose_note'), action_type: form.get('action_type'), action_detail: form.get('action_detail'), target_metric: form.get('target_metric'), planned_at: form.get('planned_at'), observer_window_days: Number(form.get('observer_window_days')), assigned_to: 'operator', source_rule_key: source.rule_key, source_rule_name: source.rule_name, source_period: source.period, source_category_mode: source.category_mode, source_period_type: source.period_type, source_period_key: source.period_key, source_product_id: id, source_problem_key: source.rule_key }) }); $('[data-product-detail-action-status]').textContent = '运营动作草稿已创建'; await load(); } catch (error) { mutationError(error, '创建运营动作失败，请重试'); } finally { if (submit?.isConnected) { submit.disabled = false; submit.removeAttribute('aria-busy'); } } });
  bindWorkbenchNavigation();
  window.addEventListener('tmall:date-range-change', (event) => load(event.detail));
  DemoLabels.load().finally(load);

  // ========== KPI 数据下钻 ==========
  const drillMetricLabels = { net_sales: '净销售额', payment_amount: '支付金额', payment_conversion_rate: '支付转化率', expense_ratio: '费比', average_order_value: '客单价' };
  const drillMetricFormat = { net_sales: money, payment_amount: money, payment_conversion_rate: percent, expense_ratio: percent, average_order_value: money };
  let drillCurrentMetric = null, drillCurrentPeriod = 'daily', drillChart = null;
  let drillDrawer = null;

  // Prefer the shared NUI drawer while keeping the legacy modal as a fallback.
  function initDrillDrawer() {
    const modal = document.querySelector('[data-drill-modal]');
    const body = modal?.querySelector('.drill-modal__body');
    const legacyTitle = modal?.querySelector('.drill-modal__header [data-drill-title]');
    const legacyDialog = modal?.querySelector('.drill-modal__dialog');
    if (!window.TmallUI?.detailDrawer || !body) return;
    drillDrawer = window.TmallUI.detailDrawer({
      title: '指标下钻',
      body,
      size: 'lg',
      onClose: disposeDrillChart,
    });
    if (legacyTitle) {
      legacyTitle.removeAttribute('data-drill-title');
      legacyTitle.id = 'drill-modal-legacy-title';
    }
    if (legacyDialog) legacyDialog.setAttribute('aria-labelledby', 'drill-modal-legacy-title');
    const heading = drillDrawer.node.querySelector('h2');
    if (heading) {
      heading.dataset.drillTitle = '';
      heading.id = 'drill-modal-title';
    }
  }

  function disposeDrillChart() {
    if (drillChart) {
      drillChart.dispose();
      drillChart = null;
    }
  }

  function getDrillValue(item, metric) {
    if (metric === 'net_sales') return item.net_sales;
    if (metric === 'payment_amount') return item.payment_amount;
    if (metric === 'payment_conversion_rate') { const v = item.product_visitors || item.paid_ipv || 0; const b = item.payment_qty || item.paid_buyers || 0; return v > 0 ? b / v : null; }
    if (metric === 'expense_ratio') { const p = item.payment_amount || 0; const s = item.ad_spend || 0; return p > 0 ? s / p : null; }
    if (metric === 'average_order_value') { const q = item.payment_qty || item.paid_buyers || 0; const p = item.payment_amount || 0; return q > 0 ? p / q : null; }
    return item[metric];
  }

  function aggregateDrillData(rows, period) {
    if (period === 'daily') return rows;
    const groups = {};
    rows.forEach((item) => {
      const d = new Date(item.date);
      let key = period === 'weekly' ? (() => { const w = new Date(d); w.setDate(d.getDate() - d.getDay()); return w.toISOString().slice(0, 10); })() : item.date.slice(0, 7);
      if (!groups[key]) groups[key] = { date: key, payment_amount: 0, net_sales: 0, product_visitors: 0, ad_spend: 0, payment_qty: 0 };
      groups[key].payment_amount += Number(item.payment_amount) || 0;
      groups[key].net_sales += Number(item.net_sales) || 0;
      groups[key].product_visitors += Number(item.product_visitors) || 0;
      groups[key].ad_spend += Number(item.ad_spend) || 0;
      groups[key].payment_qty += Number(item.payment_qty) || 0;
    });
    return Object.values(groups).sort((a, b) => a.date.localeCompare(b.date));
  }

  function renderDrillContent() {
    const metric = drillCurrentMetric, period = drillCurrentPeriod;
    const trendRows = Array.isArray(detailPayload && detailPayload.daily_trend) ? detailPayload.daily_trend : [];
    const data = aggregateDrillData(trendRows, period);
    const format = drillMetricFormat[metric] || ((v) => v == null ? '--' : v);
    const values = data.map((item) => getDrillValue(item, metric)).filter((v) => v != null && !isNaN(v));
    const stats = document.querySelector('[data-drill-stats]');
    if (values.length) {
      const avg = values.reduce((a, b) => a + b, 0) / values.length, max = Math.max(...values), min = Math.min(...values), latest = values[values.length - 1];
      stats.innerHTML = '<div class="drill-modal__stat"><div class="drill-modal__stat-label">最新值</div><div class="drill-modal__stat-value">' + format(latest) + '</div></div><div class="drill-modal__stat"><div class="drill-modal__stat-label">平均值</div><div class="drill-modal__stat-value">' + format(avg) + '</div></div><div class="drill-modal__stat"><div class="drill-modal__stat-label">最高值</div><div class="drill-modal__stat-value">' + format(max) + '</div></div><div class="drill-modal__stat"><div class="drill-modal__stat-label">最低值</div><div class="drill-modal__stat-value">' + format(min) + '</div></div>';
    } else {
      stats.innerHTML = '<div class="drill-modal__stat" style="grid-column:1/-1;text-align:center;color:var(--text-secondary);">暂无数据</div>';
    }
    const chartEl = document.querySelector('[data-drill-chart]');
    disposeDrillChart();
    if (window.echarts && data.length) {
      drillChart = echarts.init(chartEl);
      drillChart.setOption({
        tooltip: { trigger: 'axis', formatter: function(params) { var p = params[0]; return p.name + '<br/>' + drillMetricLabels[metric] + ': ' + format(p.value); } },
        grid: { left: 50, right: 20, top: 20, bottom: 40 },
        xAxis: { type: 'category', data: data.map(function(d) { return d.date; }), axisLabel: { rotate: data.length > 14 ? 45 : 0, fontSize: 10 } },
        yAxis: { type: 'value', axisLabel: { formatter: function(v) { return (metric === 'payment_conversion_rate' || metric === 'expense_ratio') ? (v * 100).toFixed(1) + '%' : (v >= 10000 ? (v / 10000).toFixed(1) + '万' : v.toFixed(0)); } } },
        series: [{ name: drillMetricLabels[metric], type: 'line', smooth: true, data: data.map(function(d) { return getDrillValue(d, metric); }), areaStyle: { opacity: 0.1 }, lineStyle: { width: 2 }, itemStyle: { color: '#3b82f6' } }],
      });
    } else {
      chartEl.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:var(--text-secondary);">暂无趋势数据</div>';
    }
    const table = document.querySelector('[data-drill-table]');
    const rows = data.map(function(item, idx) {
      const val = getDrillValue(item, metric);
      const prev = idx > 0 ? getDrillValue(data[idx - 1], metric) : null;
      const change = (prev != null && prev !== 0 && val != null) ? ((val - prev) / prev * 100) : null;
      return {
        date: item.date,
        value: format(val),
        change: change != null ? `${change > 0 ? '+' : ''}${change.toFixed(1)}%` : '--',
        changeValue: change,
      };
    });
    replaceTableBody(table, [
      { key: 'date', label: '周期' },
      { key: 'value', label: '数值', numeric: true },
      { key: 'change', label: '环比', numeric: true, render: (value, row) => {
        const cell = document.createElement('span');
        cell.textContent = value;
        if (row.changeValue != null) cell.style.color = row.changeValue > 0 ? 'var(--success-text)' : 'var(--danger-text)';
        return cell;
      } },
    ], rows, '暂无数据');
  }

  function renderDrillModal(metric) {
    drillCurrentMetric = metric;
    const title = (drillMetricLabels[metric] || metric) + ' · 趋势下钻';
    const titleNode = document.querySelector('[data-drill-title]');
    if (titleNode) titleNode.textContent = title;
    if (drillDrawer) {
      const drawerTitle = drillDrawer.node.querySelector('h2');
      if (drawerTitle) drawerTitle.textContent = title;
      drillDrawer.open();
    } else {
      const modal = document.querySelector('[data-drill-modal]');
      if (modal) modal.hidden = false;
    }
    renderDrillContent();
  }
  function closeDrillModal() {
    if (drillDrawer) drillDrawer.close();
    const modal = document.querySelector('[data-drill-modal]');
    if (modal) modal.hidden = true;
    disposeDrillChart();
  }

  initDrillDrawer();
  document.querySelectorAll('[data-drill-metric]').forEach(function(card) { card.addEventListener('click', function() { renderDrillModal(card.dataset.drillMetric); }); });
  var closeBtn = document.querySelector('[data-drill-close]'); if (closeBtn) closeBtn.addEventListener('click', closeDrillModal);
  var modal = document.querySelector('[data-drill-modal]'); if (modal) modal.addEventListener('click', function(e) { if (e.target.dataset.drillModal !== undefined || e.target.dataset.drillOverlay !== undefined) closeDrillModal(); });
  document.addEventListener('keydown', function(e) {
    const legacyModal = document.querySelector('[data-drill-modal]');
    const drawerOpen = Boolean(drillDrawer?.node && !drillDrawer.node.hidden);
    if (e.key === 'Escape' && (drawerOpen || (legacyModal && !legacyModal.hidden))) closeDrillModal();
  });
  document.querySelectorAll('[data-drill-period]').forEach(function(tab) { tab.addEventListener('click', function() {
    document.querySelectorAll('[data-drill-period]').forEach(function(t) { t.classList.remove('drill-modal__tab--active'); });
    tab.classList.add('drill-modal__tab--active');
    drillCurrentPeriod = tab.dataset.drillPeriod;
    renderDrillContent();
  }); });
  window.addEventListener('resize', function() { if (drillChart) drillChart.resize(); });
})();
