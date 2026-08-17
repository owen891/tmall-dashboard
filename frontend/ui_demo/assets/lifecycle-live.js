(function () {
  const $ = (selector, root = document) => root.querySelector(selector);
  const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  const lifecycleDetailFieldGroups = [
    { label: '\u57fa\u7840\u4fe1\u606f', fields: [{ key: 'month', label: '\u6708\u4efd' }] },
    { label: '\u7ecf\u8425\u89c4\u6a21', fields: [
      { key: 'gsv', label: 'GSV' }, { key: 'net_sales', label: '\u51c0\u9500\u552e\u989d' },
      { key: 'payment_qty', label: '\u652f\u4ed8\u4ef6\u6570' }, { key: 'buyers', label: '\u652f\u4ed8\u4e70\u5bb6\u6570' },
      { key: 'avg_order_value', label: '\u5ba2\u5355\u4ef7' },
    ] },
    { label: '\u6d41\u91cf\u8f6c\u5316', fields: [
      { key: 'visitors', label: '\u8bbf\u5ba2\u6570' }, { key: 'payment_conversion', label: '\u652f\u4ed8\u8f6c\u5316\u7387' },
      { key: 'cart_rate', label: '\u52a0\u8d2d\u7387' }, { key: 'fav_rate', label: '\u6536\u85cf\u7387' },
      { key: 'bounce_rate', label: '\u8df3\u51fa\u7387' }, { key: 'avg_stay_duration', label: '\u5e73\u5747\u505c\u7559\u65f6\u957f' },
      { key: 'uv_value', label: '\u8bbf\u5ba2\u4ef7\u503c' }, { key: 'search_visitors', label: '\u641c\u7d22\u8bbf\u5ba2\u6570' },
      { key: 'search_ratio', label: '\u641c\u7d22\u5360\u6bd4' },
    ] },
    { label: '\u552e\u540e\u590d\u8d2d', fields: [
      { key: 'refund_amount', label: '\u9000\u6b3e\u91d1\u989d' }, { key: 'refund_rate', label: '\u9000\u6b3e\u7387' },
      { key: 'repurchase_rate', label: '\u590d\u8d2d\u7387' }, { key: 'cross_sell_rate', label: '\u8fde\u5e26\u7387' },
    ] },
    { label: '\u6295\u653e\u6548\u7387', fields: [
      { key: 'ad_spend', label: '\u63a8\u5e7f\u82b1\u8d39' }, { key: 'ad_roi', label: '\u63a8\u5e7f ROI' },
    ] },
  ];
  const lifecycleDetailColumns = [
    { key: 'month', label: '\u6708\u4efd', value: (item) => item.month, numeric: false },
    { key: 'gsv', label: 'GSV', value: (item) => money(item.gsv), numeric: true },
    { key: 'net_sales', label: '\u51c0\u9500\u552e\u989d', value: (item) => money(item.net_sales), numeric: true },
    { key: 'payment_qty', label: '\u652f\u4ed8\u4ef6\u6570', value: (item) => count(item.payment_qty), numeric: true },
    { key: 'buyers', label: '\u652f\u4ed8\u4e70\u5bb6\u6570', value: (item) => count(item.buyers), numeric: true },
    { key: 'avg_order_value', label: '\u5ba2\u5355\u4ef7', value: (item) => money(item.avg_order_value), numeric: true },
    { key: 'visitors', label: '\u8bbf\u5ba2\u6570', value: (item) => count(item.visitors), numeric: true },
    { key: 'payment_conversion', label: '\u652f\u4ed8\u8f6c\u5316\u7387', value: (item) => rate(item.payment_conversion), numeric: true },
    { key: 'cart_rate', label: '\u52a0\u8d2d\u7387', value: (item) => rate(item.cart_rate), numeric: true },
    { key: 'fav_rate', label: '\u6536\u85cf\u7387', value: (item) => rate(item.fav_rate), numeric: true },
    { key: 'bounce_rate', label: '\u8df3\u51fa\u7387', value: (item) => rate(item.bounce_rate), numeric: true },
    { key: 'avg_stay_duration', label: '\u5e73\u5747\u505c\u7559\u65f6\u957f', value: (item) => decimal(item.avg_stay_duration, 1), numeric: true },
    { key: 'uv_value', label: '\u8bbf\u5ba2\u4ef7\u503c', value: (item) => money(item.uv_value), numeric: true },
    { key: 'search_visitors', label: '\u641c\u7d22\u8bbf\u5ba2\u6570', value: (item) => count(item.search_visitors), numeric: true },
    { key: 'search_ratio', label: '\u641c\u7d22\u5360\u6bd4', value: (item) => rate(item.search_ratio), numeric: true },
    { key: 'refund_amount', label: '\u9000\u6b3e\u91d1\u989d', value: (item) => money(item.refund_amount), numeric: true },
    { key: 'refund_rate', label: '\u9000\u6b3e\u7387', value: (item) => ratio(item.refund_amount, item.gsv), numeric: true },
    { key: 'repurchase_rate', label: '\u590d\u8d2d\u7387', value: (item) => rate(item.repurchase_rate), numeric: true },
    { key: 'cross_sell_rate', label: '\u8fde\u5e26\u7387', value: (item) => rate(item.cross_sell_rate), numeric: true },
    { key: 'ad_spend', label: '\u63a8\u5e7f\u82b1\u8d39', value: (item) => money(item.ad_spend), numeric: true },
    { key: 'ad_roi', label: '\u63a8\u5e7f ROI', value: (item) => Number(item.ad_roi || 0) ? Number(item.ad_roi).toFixed(2) : '--', numeric: true },
  ];
  const lifecycleDetailColumnMap = new Map(lifecycleDetailColumns.map((column) => [column.key, column]));
  const lifecycleDetailStorageKey = 'tmall-lifecycle-detail-fields';
  const defaultLifecycleDetailFields = lifecycleDetailColumns.map((column) => column.key);
  const legacyLifecycleDetailFields = ['month', 'gsv', 'payment_qty', 'refund_amount', 'ad_spend', 'ad_roi'];
  const lifecycleDetailTemplates = {
    complete: defaultLifecycleDetailFields,
    scale: ['month', 'gsv', 'net_sales', 'payment_qty', 'buyers', 'avg_order_value'],
    traffic: ['month', 'visitors', 'payment_conversion', 'cart_rate', 'fav_rate', 'bounce_rate', 'uv_value', 'search_visitors', 'search_ratio'],
    afterSales: ['month', 'refund_amount', 'refund_rate', 'repurchase_rate', 'cross_sell_rate'],
    efficiency: ['month', 'gsv', 'net_sales', 'ad_spend', 'ad_roi'],
  };
  const lifecycleDetailTemplateLabels = {
    complete: '\u5b8c\u6574\u6708\u5ea6\u660e\u7ec6',
    scale: '\u7ecf\u8425\u89c4\u6a21',
    traffic: '\u6d41\u91cf\u8f6c\u5316',
    efficiency: '\u6295\u653e\u6548\u7387',
    afterSales: '\u552e\u540e\u590d\u8d2d',
  };
  const lifecycleTemplateStorageKey = 'tmall-lifecycle-detail-templates';
  const lifecycleBuiltinTemplateKeys = Object.keys(lifecycleDetailTemplates);
  try {
    const storedTemplates = JSON.parse(window.localStorage.getItem(lifecycleTemplateStorageKey) || 'null');
    if (storedTemplates?.templates && typeof storedTemplates.templates === 'object') Object.assign(lifecycleDetailTemplates, storedTemplates.templates);
    if (storedTemplates?.labels && typeof storedTemplates.labels === 'object') Object.assign(lifecycleDetailTemplateLabels, storedTemplates.labels);
  } catch (_) {}
  const normalizeLifecycleDetailFields = (fields) => {
    const selected = [...new Set((fields || []).map(String).filter((key) => lifecycleDetailColumnMap.has(key)))];
    return ['month', ...selected.filter((key) => key !== 'month')];
  };
  const loadLifecycleDetailFields = () => {
    try {
      const stored = JSON.parse(window.localStorage.getItem(lifecycleDetailStorageKey) || 'null');
      if (!Array.isArray(stored)) return defaultLifecycleDetailFields;
      const normalized = normalizeLifecycleDetailFields(stored);
      return JSON.stringify(normalized) === JSON.stringify(legacyLifecycleDetailFields) ? defaultLifecycleDetailFields : normalized;
    } catch (error) {
      return defaultLifecycleDetailFields;
    }
  };
  const lifecycleTemplateId = (fields) => Object.entries(lifecycleDetailTemplates).find(([, selected]) => JSON.stringify(selected) === JSON.stringify(normalizeLifecycleDetailFields(fields)))?.[0] || 'custom';
  const state = { summaries: [], rowsByProduct: new Map(), range: null, selectedId: '', previousFocus: null, requestId: 0, scaleChart: null, efficiencyChart: null, efficiencyMode: 'refundRate', detailTab: 'overview', detailFields: loadLifecycleDetailFields(), page: 1 };
  const detailTabUI = (() => {
    const dialog = $('[data-lifecycle-detail]');
    if (!dialog) return null;
    const metrics = $('[data-lifecycle-metrics]', dialog);
    const chartGrid = $('.lifecycle-chart-grid', dialog);
    const insights = $('[data-lifecycle-insights]', dialog);
    const table = [...dialog.children].find((item) => item.matches('article.plain-panel'));
    const scaleChart = chartGrid?.querySelector('.lifecycle-chart-panel:first-child');
    const efficiencyChart = chartGrid?.querySelector('.lifecycle-chart-panel:nth-child(2)');
    if (!metrics || !chartGrid || !insights || !table || !scaleChart || !efficiencyChart) return null;
    const panel = (id, children) => {
      const element = document.createElement('section');
      element.className = 'lifecycle-detail-panel';
      element.dataset.lifecycleDetailPanel = id;
      element.id = `lifecycle-detail-panel-${id}`;
      element.setAttribute('role', 'tabpanel');
      element.setAttribute('aria-labelledby', `lifecycle-detail-tab-${id}`);
      element.tabIndex = 0;
      children.forEach((child) => element.appendChild(child));
      return element;
    };
    const panels = {
      overview: panel('overview', [metrics, scaleChart]),
      efficiency: panel('efficiency', [efficiencyChart, insights]),
      table: panel('table', [table]),
    };
    const tabList = document.createElement('div');
    tabList.className = 'lifecycle-detail-tabs';
    tabList.setAttribute('role', 'tablist');
    tabList.setAttribute('aria-label', '\u751f\u547d\u5468\u671f\u8be6\u60c5\u5206\u7ec4');
    const tabs = [
      ['overview', '\u6982\u89c8'],
      ['efficiency', '\u6548\u7387\u4e0e\u6295\u653e'],
      ['table', '\u6708\u5ea6\u660e\u7ec6'],
    ].map(([id, label], index) => {
      const button = document.createElement('button');
      button.className = 'lifecycle-detail-tab';
      button.type = 'button';
      button.id = `lifecycle-detail-tab-${id}`;
      button.dataset.lifecycleDetailTab = id;
      button.setAttribute('role', 'tab');
      button.setAttribute('aria-controls', `lifecycle-detail-panel-${id}`);
      button.setAttribute('aria-selected', String(index === 0));
      button.tabIndex = index === 0 ? 0 : -1;
      button.textContent = label;
      tabList.appendChild(button);
      return button;
    });
    dialog.querySelector('.lifecycle-detail__header')?.after(tabList);
    chartGrid.remove();
    Object.values(panels).forEach((element) => dialog.appendChild(element));
    return { dialog, tabs, panels };
  })();
  const lifecycleColumnsDialog = $('[data-lifecycle-columns-dialog]');
  let lifecycleColumnSelector = null;
  let lifecycleTemplateManager = null;
  let lifecycleSettings = null;
  let lifecycleColumnsReturnFocus = null;
  const pageSize = 24;
  const money = (value) => `￥${Number(value || 0).toLocaleString('zh-CN', { maximumFractionDigits: 1 })}`;
  const count = (value) => Number(value || 0).toLocaleString('zh-CN', { maximumFractionDigits: 0 });
  const percent = (value) => `${(Number(value || 0) * 100).toFixed(1)}%`;
  const rate = (value) => value == null || value === '' ? '--' : percent(value);
  const ratio = (numerator, denominator) => Number(denominator || 0) ? percent(Number(numerator || 0) / Number(denominator)) : '--';
  const decimal = (value, digits = 2) => value == null || value === '' ? '--' : Number(value).toFixed(digits);
  const sum = (rows, field) => rows.reduce((total, row) => total + Number(row[field] || 0), 0);
  const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char]);
  const toast = (message) => {
    if (window.DemoShell?.showToast) window.DemoShell.showToast(message);
    else window.alert(message);
  };
  const setStatus = (message) => { const target = $('[data-lifecycle-status]'); if (target) target.textContent = message; window.DemoShell?.setStatus?.(message); };
  const renderDataState = (state, details) => DemoApi.renderDataState($('[data-lifecycle-status]'), state, details);
  let assessments = [];
  let assessmentPayload = { capabilities: {} };
  let assessmentPage = 1;
  const assessmentPageSize = 20;
  const assessmentLabel = (value) => DemoLabels.classification('lifecycle_stages', value, value || '--');
  const seasonalLabel = (value) => DemoLabels.classification('seasonal_attributes', value, value ? value : '数据不足');
  const assessmentPriority = (entry) => {
    if (entry.locked || entry.manual_stage) return 0;
    if (entry.stage && entry.stage !== 'data_accumulating') return 1;
    if (Number(entry.continuous_valid_days || 0) > 0) return 2;
    return 3;
  };
  function visibleAssessments() {
    const query = $('[data-lifecycle-assessment-search]')?.value.trim().toLowerCase() || '';
    const stage = $('[data-lifecycle-assessment-stage]')?.value || '';
    return assessments.filter((entry) => {
      const identity = `${DemoLabels.clean(entry.title, '')} ${DemoLabels.clean(entry.product_id, '')}`.toLowerCase();
      return (!query || identity.includes(query)) && (!stage || entry.stage === stage);
    }).sort((a, b) => assessmentPriority(a) - assessmentPriority(b)
      || Number(b.continuous_valid_days || 0) - Number(a.continuous_valid_days || 0)
      || String(a.title || a.product_id).localeCompare(String(b.title || b.product_id), 'zh-CN'));
  }
  function assessmentEvidence(entry) {
    const evidence = document.createElement('div');
    evidence.className = 'lifecycle-assessment-evidence';
    evidence.setAttribute('data-lifecycle-assessment-evidence', '');
    const primary = document.createElement('strong');
    const secondary = document.createElement('span');
    const history = entry.history || [];
    if (entry.stage === 'data_accumulating') {
      primary.textContent = `连续有效日 ${Number(entry.continuous_valid_days || 0)}/60`;
      secondary.textContent = '数据尚不足，暂不输出阶段和季节性结论';
    } else {
      primary.textContent = entry.rationale || '基于连续经营数据与趋势评估';
      const facts = [];
      if (entry.conversion_trend?.recent != null) facts.push(`转化 ${(entry.conversion_trend.recent * 100).toFixed(2)}%`);
      if (entry.promotion_dependency != null) facts.push(`推广依赖 ${(entry.promotion_dependency * 100).toFixed(2)}%`);
      if (entry.next_key_date) facts.push(`下一节点 ${entry.next_key_date}`);
      if (history.length) facts.push(`人工调整 ${history.length} 次`);
      secondary.textContent = facts.join(' · ') || '暂无补充指标';
    }
    evidence.append(primary, secondary);
    return evidence;
  }
  function appendAssessmentCell(row, content, className = '') {
    const cell = document.createElement('td');
    if (className) cell.className = className;
    if (content instanceof Node) cell.appendChild(content); else cell.textContent = content;
    row.appendChild(cell);
  }
  function renderAssessments() {
    const body = $('[data-lifecycle-assessments]');
    if (!body) return;
    const records = visibleAssessments();
    const totalPages = Math.max(1, Math.ceil(records.length / assessmentPageSize));
    assessmentPage = Math.min(assessmentPage, totalPages);
    const pageRows = records.slice((assessmentPage - 1) * assessmentPageSize, assessmentPage * assessmentPageSize);
    body.replaceChildren();
    pageRows.forEach((entry) => {
      const row = document.createElement('tr');
      const identity = document.createElement('div');
      identity.className = 'lifecycle-assessment-product';
      const title = document.createElement('strong');
      title.textContent = DemoLabels.clean(entry.title, '') || '未命名商品';
      const productId = document.createElement('span');
      productId.textContent = `ID ${DemoLabels.clean(entry.product_id, '--')}`;
      identity.append(title, productId);
      appendAssessmentCell(row, identity);
      appendAssessmentCell(row, entry.stage_label || assessmentLabel(entry.stage));
      appendAssessmentCell(row, DemoLabels.label('confidence', entry.confidence, '低'));
      appendAssessmentCell(row, entry.seasonal_label || seasonalLabel(entry.seasonal_attribute));
      appendAssessmentCell(row, assessmentEvidence(entry));
      const action = document.createElement('button');
      action.type = 'button';
      action.className = 'button button--ghost';
      action.textContent = entry.locked ? '查看调整' : '调整';
      action.disabled = Object.keys(assessmentPayload.capabilities || {}).length > 0 && !DemoApi.can(assessmentPayload, 'can_edit_stage');
      action.addEventListener('click', () => openAssessmentEditor(entry));
      appendAssessmentCell(row, action);
      body.appendChild(row);
    });
    if (!pageRows.length) {
      const row = body.insertRow();
      const cell = row.insertCell();
      cell.colSpan = 6;
      cell.textContent = assessments.length ? '没有匹配的生命周期评估' : '暂无生命周期评估';
    }
    $('[data-lifecycle-assessment-count]').textContent = records.length ? `共 ${count(records.length)} 条，第 ${assessmentPage} / ${totalPages} 页` : '无匹配结果';
    $('[data-lifecycle-assessment-prev]').disabled = assessmentPage <= 1;
    $('[data-lifecycle-assessment-next]').disabled = assessmentPage >= totalPages;
    window.lucide?.createIcons();
  }
  const editDialog = $('[data-lifecycle-edit-dialog]'); let editingAssessment = null;
  let assessmentPreviousFocus = null;
  function fillAssessmentOptions() {
    const stage = $('[data-lifecycle-stage-options]'); const season = $('[data-lifecycle-season-options]');
    stage.replaceChildren(new Option('使用系统建议', ''), ...DemoLabels.enabled('lifecycle_stages').filter((item) => item.value !== 'data_accumulating').map((item) => new Option(item.label, item.value)));
    season.replaceChildren(new Option('不覆盖', ''), ...DemoLabels.enabled('seasonal_attributes').map((item) => new Option(item.label, item.value)));
    const filter = $('[data-lifecycle-assessment-stage]');
    filter.replaceChildren(new Option('全部阶段', ''), ...DemoLabels.enabled('lifecycle_stages').map((item) => new Option(item.label, item.value)));
  }
  function openAssessmentEditor(entry) {
    editingAssessment = entry;
    assessmentPreviousFocus = document.activeElement;
    const form = $('[data-lifecycle-edit-form]');
    form.reset();
    form.elements.manual_stage.value = entry.manual_stage || '';
    form.elements.seasonal_attribute.value = entry.seasonal_attribute || '';
    form.elements.lock.checked = Boolean(entry.locked);
    $('[data-lifecycle-edit-product]').textContent = `${DemoLabels.clean(entry.title, '') || '未命名商品'} · ID ${DemoLabels.clean(entry.product_id, '--')}`;
    $('[data-lifecycle-edit-status]').textContent = '';
    editDialog.hidden = false;
    if (!editDialog.open) editDialog.showModal();
    form.elements.manual_stage.focus();
  }
  function closeAssessmentEditor() {
    if (editDialog.open) editDialog.close();
    editDialog.hidden = true;
  }
  const loadAssessments = async () => {
    assessmentPayload = await DemoApi.domainRequest('/api/lifecycle/assessments');
    const data = assessmentPayload.data;
    assessments = Array.isArray(data) ? data.filter((entry) => DemoLabels.clean(entry.product_id, '')) : [];
    assessmentPage = 1;
    renderAssessments();
  };

  function rangeFrom(detail) {
    state.range = detail || window.TmallDateRange?.getState?.() || state.range || {};
    return state.range;
  }

  function parseSummaryRows(summary) {
    return String(summary.gsv_series || '').split(',').map((item) => {
      const separator = item.indexOf(':');
      if (separator < 0) return null;
      return { month: item.slice(0, separator), gsv: Number(item.slice(separator + 1) || 0) };
    }).filter((row) => row?.month).sort((a, b) => a.month.localeCompare(b.month));
  }

  function selectedRows(record) { return record.rows; }

  function visibleRecords() {
    const query = $('[data-lifecycle-search]').value.trim().toLowerCase();
    const tier = $('[data-lifecycle-tier]').value;
    return state.summaries.filter((record) => {
      const matches = !query || `${record.title} ${record.product_id}`.toLowerCase().includes(query);
      return matches && (!tier || record.tier === tier) && selectedRows(record).length;
    }).sort((a, b) => sum(selectedRows(b), 'gsv') - sum(selectedRows(a), 'gsv'));
  }

  function createMessage(message, className = 'panel__hint') {
    const item = document.createElement('p');
    item.className = className;
    item.textContent = message;
    return item;
  }

  function tierClass(tier) {
    return ({ '利润款': 'badge--success', '引流款': 'badge--info', '爆款': 'badge--warning', '形象款': 'badge--purple' })[tier] || 'badge--muted';
  }

  function renderCards() {
    const grid = $('[data-lifecycle-grid]');
    const records = visibleRecords();
    const totalPages = Math.max(1, Math.ceil(records.length / pageSize));
    state.page = Math.min(state.page, totalPages);
    const pageRows = records.slice((state.page - 1) * pageSize, state.page * pageSize);
    grid.replaceChildren();
    grid.setAttribute('aria-busy', 'false');
    if (!records.length) grid.appendChild(createMessage('当前筛选范围没有生命周期记录'));
    pageRows.forEach((record) => {
      const rows = selectedRows(record);
      const latest = rows.at(-1);
      const previous = rows.at(-2);
      const growth = previous?.gsv ? (Number(latest.gsv || 0) - Number(previous.gsv || 0)) / Number(previous.gsv) : null;
      const card = document.createElement('button');
      card.type = 'button';
      card.className = 'lifecycle-card';
      card.dataset.lifecycleCard = record.product_id;
      card.setAttribute('aria-label', `查看 ${record.title || record.product_id} 的生命周期详情`);
      const thumbnailUrl = String(record.image_url || '').trim();
      const image = thumbnailUrl ? `<img src="${thumbnailUrl}" alt="" width="42" height="42" loading="lazy">` : '<span class="product-thumb product-thumb--placeholder" aria-hidden="true"><i data-lucide="image"></i></span>';
      const trend = growth === null ? '无环比' : `${growth >= 0 ? '上升' : '下降'} ${percent(Math.abs(growth))}`;
      card.innerHTML = `<span class="lifecycle-card__header">${image}<span><span class="lifecycle-card__title">${escapeHtml(record.title || '未命名商品')}</span><span class="lifecycle-card__meta"><span class="badge ${tierClass(record.tier)}">${escapeHtml(DemoLabels.classification('tiers', record.tier, '未分层'))}</span><span class="badge badge--muted">${escapeHtml(DemoLabels.classification('styles', record.style, '未分类'))}</span></span></span></span><span class="lifecycle-card__stats"><span class="lifecycle-card__stat"><strong>${money(sum(rows, 'gsv'))}</strong><span>累计 GSV</span></span><span class="lifecycle-card__stat"><strong>${count(rows.length)}</strong><span>活跃月数</span></span><span class="lifecycle-card__stat"><strong class="lifecycle-card__trend ${growth > 0.05 ? 'is-up' : growth < -0.05 ? 'is-down' : ''}">${trend}</strong><span>最近月环比</span></span></span>`;
      card.addEventListener('click', () => openDetail(record.product_id, card));
      grid.appendChild(card);
    });
    $('[data-lifecycle-count]').textContent = records.length ? `共 ${count(records.length)} 款商品` : '无匹配商品';
    $('[data-lifecycle-page-summary]').textContent = records.length ? `第 ${state.page} / ${totalPages} 页，共 ${count(records.length)} 件` : '暂无可分页数据';
    $('[data-lifecycle-prev]').disabled = state.page <= 1;
    $('[data-lifecycle-next]').disabled = state.page >= totalPages;
    updateKpis(records);
    if (window.lucide) window.lucide.createIcons();
  }

  function updateKpis(records) {
    const rows = records.flatMap(selectedRows);
    const months = [...new Set(rows.map((row) => row.month))].sort();
    const growing = records.filter((record) => { const rowsForRecord = selectedRows(record); const latest = rowsForRecord.at(-1); const previous = rowsForRecord.at(-2); return previous?.gsv && Number(latest.gsv || 0) > Number(previous.gsv || 0) * 1.05; }).length;
    $('[data-lifecycle-kpi="products"]').textContent = count(records.length);
    $('[data-lifecycle-kpi="gsv"]').textContent = money(sum(rows, 'gsv'));
    $('[data-lifecycle-kpi="average"]').textContent = records.length ? (rows.length / records.length).toFixed(1) : '--';
    $('[data-lifecycle-kpi="growing"]').textContent = count(growing);
    $('[data-lifecycle-records]').textContent = `${count(rows.length)} 条月度记录`;
    $('[data-lifecycle-months]').textContent = months.length ? `覆盖 ${months.length} 个月` : '无月度记录';
    $('[data-lifecycle-growth-period]').textContent = months.at(-1) ? `${months.at(-1)} 环比增长超过 5%` : '无可比较周期';
  }

  function fillTiers() {
    const select = $('[data-lifecycle-tier]');
    const current = select.value;
    const tiers = [...new Set(state.summaries.map((record) => DemoLabels.clean(record.tier, '')).filter(Boolean))].sort();
    select.replaceChildren(new Option('全部分层', ''));
    tiers.forEach((tier) => select.add(new Option(tier, tier)));
    select.value = tiers.includes(current) ? current : '';
  }

  async function loadRows(productId, token) {
    if (state.rowsByProduct.has(productId)) return state.rowsByProduct.get(productId);
    const payload = await DemoApi.request(`/api/lifecycle?product_id=${encodeURIComponent(productId)}`);
    if (token !== state.requestId) return [];
    const rows = Array.isArray(payload) ? payload.map((row) => ({ ...row, month: String(row.month || '') })).filter((row) => row.month) : [];
    state.rowsByProduct.set(productId, rows);
    return rows;
  }

  async function load(detail) {
    const token = ++state.requestId;
    rangeFrom(detail);
    const grid = $('[data-lifecycle-grid]');
    grid.replaceChildren(createMessage('生命周期数据加载中'));
    grid.setAttribute('aria-busy', 'true');
    renderDataState('loading');
    try {
      const settingsResponse = await DemoApi.domainRequest('/api/settings');
      lifecycleSettings = settingsResponse.data;
      const serverTemplates = lifecycleSettings?.lifecycle_view_templates;
      if (serverTemplates && typeof serverTemplates === 'object') {
        Object.keys(lifecycleDetailTemplates).forEach((key) => delete lifecycleDetailTemplates[key]);
        Object.keys(lifecycleDetailTemplateLabels).forEach((key) => delete lifecycleDetailTemplateLabels[key]);
        Object.entries(serverTemplates).forEach(([key, value]) => {
          lifecycleDetailTemplates[key] = normalizeLifecycleDetailFields(value?.columns);
          lifecycleDetailTemplateLabels[key] = value?.label || key;
        });
        state.detailFields = normalizeLifecycleDetailFields(state.detailFields);
      }
      const summaries = await DemoApi.request('/api/lifecycle?limit=2000');
      if (token !== state.requestId) return;
      state.rowsByProduct.clear();
      const summaryRows = Array.isArray(summaries) ? summaries : [];
      state.summaries = summaryRows.map((summary) => ({ ...summary, rows: parseSummaryRows(summary) })).filter((record) => record.rows.length);
      fillTiers();
      const months = [...new Set(state.summaries.flatMap((record) => record.rows.map((row) => row.month)))].sort();
      $('[data-lifecycle-period]').textContent = months.length ? `数据库全周期 ${months[0]} 至 ${months.at(-1)}，按商品查看完整月度表现` : '数据库暂无生命周期记录';
      renderCards();
      if (!state.summaries.length) renderDataState('no-data', { message: '当前筛选范围没有生命周期记录。' });
      else setStatus(`已加载 ${count(state.summaries.length)} 款商品的真实月度记录`);
      if (state.selectedId) await refreshDetail(token);
      loadAssessments().catch(() => {
        if (token === state.requestId) setStatus(`已加载 ${count(state.summaries.length)} 款商品的真实月度记录；生命周期评估加载失败，不影响月度表现`);
      });
    } catch (error) {
      if (token !== state.requestId) return;
      state.summaries = [];
      grid.replaceChildren(createMessage('生命周期数据加载失败，请刷新后重试', 'panel__hint is-down'));
      grid.setAttribute('aria-busy', 'false');
      updateKpis([]);
      renderDataState('calculation-failed', { message: error.message || '生命周期数据加载失败', retry: () => load() });
      toast('生命周期数据加载失败');
    }
  }

  function chartOptions() {
    return { responsive: true, maintainAspectRatio: false, interaction: { mode: 'index', intersect: false }, plugins: { legend: { position: 'bottom', labels: { boxWidth: window.DemoCharts?.chartLegendBox?.() || 12 } } }, scales: { x: { grid: { display: false }, ticks: { maxRotation: 0, maxTicksLimit: 8 } }, y: { beginAtZero: true } } };
  }

  function renderScaleChart(rows) {
    state.scaleChart?.destroy();
    state.scaleChart = new EChartCompat($('#lifecycleScaleChart'), { type: 'bar', data: { labels: rows.map((row) => row.month), datasets: [{ type: 'line', label: 'GSV（万元）', data: rows.map((row) => Number(row.gsv || 0) / 10000), borderColor: css('--info'), backgroundColor: css('--chart-info-fill'), fill: true, tension: .3, yAxisID: 'y' }, { label: '支付件数', data: rows.map((row) => Number(row.payment_qty || 0)), backgroundColor: css('--chart-success-fill'), yAxisID: 'y1' }] }, options: { ...chartOptions(), scales: { ...chartOptions().scales, y1: { beginAtZero: true, position: 'right', grid: { drawOnChartArea: false } } } } });
  }

  function updateLifecycleColumnsDialogStatus(selected = lifecycleColumnSelector?.getSelected() || state.detailFields) {
    const normalized = normalizeLifecycleDetailFields(selected);
    const countElement = $('[data-lifecycle-visible-count]');
    const status = $('[data-lifecycle-columns-status]');
    if (countElement) countElement.textContent = String(normalized.length);
    if (status) status.textContent = normalized.length ? '' : '至少保留月份字段';
    const applyButton = $('[data-lifecycle-columns-apply]');
    if (applyButton) applyButton.disabled = !normalized.length;
  }

  function renderLifecycleTemplateSelect(selected = state.detailFields) {
    const select = $('[data-lifecycle-template-select]');
    if (!select) return;
    const selectedKey = lifecycleTemplateId(selected);
    select.replaceChildren(...Object.entries(lifecycleDetailTemplateLabels).map(([key, label]) => {
      const option = document.createElement('option');
      option.value = key;
      option.textContent = label;
      return option;
    }), (() => {
      const option = document.createElement('option');
      option.value = 'custom';
      option.textContent = '\u81ea\u5b9a\u4e49';
      return option;
    })());
    select.value = selectedKey;
  }

  function renderLifecycleColumnSelector(selected = state.detailFields) {
    if (!lifecycleColumnsDialog || !window.DemoFieldSelector) return;
    const config = {
      groups: lifecycleDetailFieldGroups,
      selected: normalizeLifecycleDetailFields(selected),
    };
    if (!lifecycleColumnSelector) {
      lifecycleColumnSelector = DemoFieldSelector.create({
        root: $('[data-lifecycle-field-selector]'),
        ...config,
        className: 'lifecycle-field-selection-layout',
        availableTitleId: 'lifecycleAvailableFieldsTitle',
        previewTitleId: 'lifecycleFieldPreviewTitle',
        optionDataAttribute: 'data-lifecycle-field-key',
        previewDataAttribute: 'data-lifecycle-preview-key',
        onChange: (nextSelected) => {
          const normalized = normalizeLifecycleDetailFields(nextSelected);
          if (JSON.stringify(normalized) !== JSON.stringify(nextSelected)) lifecycleColumnSelector.setSelected(normalized, { notify: false });
          updateLifecycleColumnsDialogStatus(normalized);
          renderLifecycleTemplateSelect(normalized);
        },
      });
    } else {
      lifecycleColumnSelector.setConfig(config);
    }
    const lifecycleTemplateRecords = Object.fromEntries(Object.entries(lifecycleDetailTemplates).map(([key, fields]) => [key, {
      label: lifecycleDetailTemplateLabels[key] || key,
      columns: normalizeLifecycleDetailFields(fields),
    }]));
    if (!lifecycleTemplateManager && window.DemoFieldTemplateManager) {
      lifecycleTemplateManager = DemoFieldTemplateManager.create({
        root: $('[data-lifecycle-template-manager]'),
        builtinKeys: Object.keys(lifecycleDetailTemplates),
        templates: lifecycleTemplateRecords,
        onChange: (event) => {
          if (event.type === 'use') renderLifecycleColumnSelector(lifecycleDetailTemplates[event.key]);
        },
        onSave: async (key, label) => {
          const selectedFields = normalizeLifecycleDetailFields(lifecycleColumnSelector?.getSelected());
          if (!selectedFields.length || !lifecycleDetailTemplates[key]) return;
          const previousFields = [...lifecycleDetailTemplates[key]];
          const previousLabel = lifecycleDetailTemplateLabels[key];
          lifecycleDetailTemplates[key] = selectedFields;
          lifecycleDetailTemplateLabels[key] = label;
          try { window.localStorage.setItem(lifecycleTemplateStorageKey, JSON.stringify({ templates: lifecycleDetailTemplates, labels: lifecycleDetailTemplateLabels })); } catch (_) {}
          lifecycleTemplateManager.setTemplates(Object.fromEntries(Object.entries(lifecycleDetailTemplates).map(([templateKey, fields]) => [templateKey, { label: lifecycleDetailTemplateLabels[templateKey] || templateKey, columns: fields }])));
          try {
            await persistLifecycleTemplates();
          } catch (_) {
            lifecycleDetailTemplates[key] = previousFields;
            lifecycleDetailTemplateLabels[key] = previousLabel;
            lifecycleTemplateManager.setTemplates(Object.fromEntries(Object.entries(lifecycleDetailTemplates).map(([templateKey, fields]) => [templateKey, { label: lifecycleDetailTemplateLabels[templateKey] || templateKey, columns: fields }])));
            return;
          }
          renderLifecycleTemplateSelect(selectedFields);
          $('[data-lifecycle-columns-status]').textContent = `模板“${label}”已更新`;
        },
        onDelete: (key) => deleteLifecycleTemplate(key),
      });
    }
    lifecycleTemplateManager?.setTemplates(lifecycleTemplateRecords);
    updateLifecycleColumnsDialogStatus(config.selected);
    renderLifecycleTemplateSelect(config.selected);
    window.lucide?.createIcons();
  }

  function lifecycleTemplatesPayload() {
    return Object.fromEntries(Object.entries(lifecycleDetailTemplates).map(([key, fields]) => [key, {
      label: lifecycleDetailTemplateLabels[key] || key,
      columns: normalizeLifecycleDetailFields(fields),
    }]));
  }

  async function persistLifecycleTemplates() {
    try {
      const response = await DemoApi.domainRequest('/api/settings', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ lifecycle_view_templates: lifecycleTemplatesPayload() }) });
      lifecycleSettings = response.data;
    } catch (error) {
      setStatus(error.message || '模板保存失败');
      throw error;
    }
  }

  async function deleteLifecycleTemplate(key) {
    if (lifecycleBuiltinTemplateKeys.includes(key)) return;
    const previous = { templates: { ...lifecycleDetailTemplates }, labels: { ...lifecycleDetailTemplateLabels }, fields: [...state.detailFields] };
    delete lifecycleDetailTemplates[key];
    delete lifecycleDetailTemplateLabels[key];
    if (lifecycleTemplateId(state.detailFields) === key) state.detailFields = normalizeLifecycleDetailFields(lifecycleDetailTemplates.complete);
    try {
      await persistLifecycleTemplates();
      renderLifecycleColumnSelector(state.detailFields);
      window.localStorage.setItem(lifecycleDetailStorageKey, JSON.stringify(state.detailFields));
    } catch (_) {
      Object.assign(lifecycleDetailTemplates, previous.templates);
      Object.assign(lifecycleDetailTemplateLabels, previous.labels);
      state.detailFields = previous.fields;
      renderLifecycleColumnSelector(state.detailFields);
    }
  }

  function openLifecycleColumnsDialog(event) {
    if (!lifecycleColumnsDialog) return;
    lifecycleColumnsReturnFocus = event.currentTarget;
    renderLifecycleColumnSelector(state.detailFields);
    lifecycleColumnsDialog.hidden = false;
    lifecycleColumnsDialog.showModal();
    window.setTimeout(() => lifecycleColumnsDialog.querySelector('input')?.focus(), 0);
  }

  function closeLifecycleColumnsDialog() {
    if (!lifecycleColumnsDialog) return;
    if (lifecycleColumnsDialog.open) lifecycleColumnsDialog.close();
    lifecycleColumnsDialog.hidden = true;
    lifecycleColumnsReturnFocus?.focus?.();
    lifecycleColumnsReturnFocus = null;
  }

  function applyLifecycleTemplate() {
    const key = $('[data-lifecycle-template-select]')?.value;
    if (!key || key === 'custom') return;
    renderLifecycleColumnSelector(lifecycleDetailTemplates[key]);
  }

  function applyLifecycleColumns() {
    const selected = normalizeLifecycleDetailFields(lifecycleColumnSelector?.getSelected());
    if (!selected.length) return;
    state.detailFields = selected;
    try {
      window.localStorage.setItem(lifecycleDetailStorageKey, JSON.stringify(selected));
    } catch (error) {
      // Local persistence is optional in demo mode.
    }
    const record = state.summaries.find((item) => String(item.product_id) === state.selectedId);
    if (record) renderDetailTable(selectedRows(record));
    closeLifecycleColumnsDialog();
    toast(`已应用 ${selected.length} 个字段`);
  }

  function renderDetailTable(rows) {
    const head = $('[data-lifecycle-detail-head]');
    const body = $('[data-lifecycle-detail-body]');
    if (!head || !body) return;
    const columns = normalizeLifecycleDetailFields(state.detailFields).map((key) => lifecycleDetailColumnMap.get(key)).filter(Boolean);
    head.replaceChildren();
    columns.forEach((column) => {
      const cell = document.createElement('th');
      cell.textContent = column.label;
      if (column.numeric) cell.className = 'num';
      head.appendChild(cell);
    });
    body.replaceChildren();
    rows.forEach((item) => {
      const row = body.insertRow();
      columns.forEach((column) => {
        const cell = row.insertCell();
        cell.textContent = column.value(item);
        if (column.numeric) cell.className = 'num';
      });
    });
  }

  function renderEfficiencyChart(rows) {
    state.efficiencyChart?.destroy();
    const refundMode = state.efficiencyMode === 'refundRate';
    state.efficiencyChart = new EChartCompat($('#lifecycleEfficiencyChart'), { type: 'bar', data: { labels: rows.map((row) => row.month), datasets: [{ label: '退款金额（万元）', data: rows.map((row) => Number(row.refund_amount || 0) / 10000), backgroundColor: css('--chart-danger-fill') }, { label: '推广花费（万元）', data: rows.map((row) => Number(row.ad_spend || 0) / 10000), backgroundColor: css('--chart-info-fill') }, { type: 'line', label: refundMode ? '退款率' : '推广 ROI', data: rows.map((row) => refundMode ? (Number(row.gsv || 0) ? Number(row.refund_amount || 0) / Number(row.gsv) : 0) : Number(row.ad_roi || 0)), borderColor: refundMode ? css('--danger') : css('--warning'), tension: .3, yAxisID: 'y1' }] }, options: { ...chartOptions(), scales: { ...chartOptions().scales, y1: { beginAtZero: true, position: 'right', grid: { drawOnChartArea: false }, ticks: { callback: (value) => refundMode ? `${Number(value * 100).toFixed(0)}%` : Number(value).toFixed(1) } } } } });
  }

  function metric(label, value) { return `<div class="lifecycle-metric"><strong title="${escapeHtml(value)}">${escapeHtml(value)}</strong><span>${escapeHtml(label)}</span></div>`; }

  function setDetailTab(tab, focus = false) {
    if (!detailTabUI || !detailTabUI.panels[tab]) return;
    state.detailTab = tab;
    detailTabUI.tabs.forEach((button) => {
      const active = button.dataset.lifecycleDetailTab === tab;
      button.setAttribute('aria-selected', String(active));
      button.tabIndex = active ? 0 : -1;
      if (active && focus) button.focus();
    });
    Object.entries(detailTabUI.panels).forEach(([id, panel]) => {
      panel.hidden = id !== tab;
    });
    if (tab === 'efficiency' && state.selectedId) {
      const record = state.summaries.find((item) => String(item.product_id) === state.selectedId);
      if (record) renderEfficiencyChart(selectedRows(record));
    }
  }

  detailTabUI?.tabs.forEach((button, index) => {
    button.addEventListener('click', () => setDetailTab(button.dataset.lifecycleDetailTab));
    button.addEventListener('keydown', (event) => {
      if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
      event.preventDefault();
      const next = event.key === 'Home' ? 0 : event.key === 'End' ? detailTabUI.tabs.length - 1 : (index + (event.key === 'ArrowRight' ? 1 : -1) + detailTabUI.tabs.length) % detailTabUI.tabs.length;
      setDetailTab(detailTabUI.tabs[next].dataset.lifecycleDetailTab, true);
    });
  });

  async function refreshDetail(token = state.requestId) {
    const record = state.summaries.find((item) => String(item.product_id) === state.selectedId);
    if (!record || token !== state.requestId) return;
    const rows = selectedRows(record);
    if (!rows.length) { closeDetail(); toast('当前日期范围没有该商品的生命周期记录'); return; }
    const latest = rows.at(-1);
    const previous = rows.at(-2);
    const refundRate = Number(latest.gsv || 0) ? Number(latest.refund_amount || 0) / Number(latest.gsv) : 0;
    const change = previous?.gsv ? (Number(latest.gsv || 0) - Number(previous.gsv || 0)) / Number(previous.gsv) : 0;
    $('[data-detail-title]').textContent = record.title || '未命名商品';
    $('[data-detail-meta]').textContent = `${DemoLabels.classification('tiers', record.tier, '未分层')} · ${DemoLabels.classification('styles', record.style, '未分类')} · ${rows.length} 个月度记录`;
    $('[data-detail-id]').textContent = `商品 ID ${record.product_id} · ${rows[0].month} 至 ${latest.month}`;
    const imageRoot = $('[data-detail-image]');
    imageRoot.replaceChildren();
    const thumbnailUrl = String(record.image_url || '').trim();
    if (thumbnailUrl) {
      const image = new Image(52, 52);
      image.loading = 'lazy';
      image.src = thumbnailUrl;
      image.alt = record.title || '';
      imageRoot.removeAttribute('aria-hidden');
      imageRoot.appendChild(image);
    } else {
      imageRoot.setAttribute('aria-hidden', 'true');
      imageRoot.innerHTML = '<i data-lucide="image"></i>';
    }
    const assessment = assessments.find((item) => String(item.product_id) === String(record.product_id));
    $('[data-lifecycle-metrics]').innerHTML = [metric('累计 GSV', money(sum(rows, 'gsv'))), metric('累计支付件数', count(sum(rows, 'payment_qty'))), metric('最近月 GSV', money(latest.gsv)), metric('最近月环比', previous ? `${change >= 0 ? '+' : ''}${percent(change)}` : '--'), metric('最近月退款率', percent(refundRate)), metric('最近月推广 ROI', Number(latest.ad_roi || 0) ? Number(latest.ad_roi).toFixed(2) : '--'), metric('上架时长', assessment?.listed_days == null ? '--' : `${assessment.listed_days} 天`), metric('下一关键节点', assessment?.next_key_date || '--')].join('');
    const history = assessment?.history || [];
    $('[data-lifecycle-insights]').innerHTML = [['success', '经营规模', `${latest.month} GSV ${money(latest.gsv)}`], [refundRate <= .1 ? 'success' : 'danger', '退款率', `${percent(refundRate)}，退款金额 ${money(latest.refund_amount)}`], [Number(latest.ad_roi || 0) >= 3 ? 'success' : 'warning', '投放效率', Number(latest.ad_roi || 0) ? `推广 ROI ${Number(latest.ad_roi).toFixed(2)}` : '当前月无推广数据'], [change >= 0 ? 'success' : 'danger', '月度趋势', previous ? `${change >= 0 ? '较上月增长' : '较上月下降'} ${percent(Math.abs(change))}` : '暂无上月对比'], ['info', '判断依据', `转化趋势 ${assessment?.conversion_trend?.recent == null ? '数据不足' : `${(assessment.conversion_trend.recent * 100).toFixed(2)}%`}；推广依赖 ${assessment?.promotion_dependency == null ? '数据不足' : `${(assessment?.promotion_dependency * 100).toFixed(2)}%`}；阶段迁移 ${history.length} 次`]].map(([tone, title, text]) => `<div class="lifecycle-insight lifecycle-insight--${tone}"><strong>${title}</strong><span>${text}</span></div>`).join('');
    renderScaleChart(rows); renderDetailTable(rows); setDetailTab(state.detailTab);
    if (window.lucide) window.lucide.createIcons();
  }

  async function openDetail(productId, trigger) {
    state.selectedId = String(productId); state.previousFocus = trigger || document.activeElement;
    state.detailTab = 'overview';
    const record = state.summaries.find((item) => String(item.product_id) === state.selectedId);
    if (record) {
      const rows = await loadRows(state.selectedId, state.requestId);
      if (state.selectedId !== String(productId) || !rows.length) return;
      record.rows = rows;
    }
    const dialog = $('[data-lifecycle-detail]');
    dialog.hidden = false;
    if (!dialog.open) dialog.showModal();
    await refreshDetail();
    $('[data-lifecycle-back]').focus();
  }

  function closeDetail() {
    state.selectedId = '';
    const dialog = $('[data-lifecycle-detail]');
    if (dialog.open) dialog.close();
    dialog.hidden = true;
    state.scaleChart?.destroy(); state.scaleChart = null; state.efficiencyChart?.destroy(); state.efficiencyChart = null;
    state.previousFocus?.focus?.();
    state.previousFocus = null;
  }

  function exportCsv() {
    const columns = normalizeLifecycleDetailFields(state.detailFields).map((key) => lifecycleDetailColumnMap.get(key)).filter(Boolean);
    const rows = visibleRecords().flatMap((record) => selectedRows(record).map((row) => {
      const output = { '商品 ID': record.product_id, '商品名称': record.title || '', '商品分层': DemoLabels.classification('tiers', record.tier, '') };
      columns.forEach((column) => {
        output[column.label] = column.key === 'refund_rate'
          ? (Number(row.gsv || 0) ? Number(row.refund_amount || 0) / Number(row.gsv) : 0)
          : row[column.key] ?? '';
      });
      return output;
    }));
    if (!rows.length) return toast('当前筛选范围没有可导出的生命周期数据');
    const headers = Object.keys(rows[0]);
    const quote = (value) => {
      const raw = String(value ?? '');
      const safe = /^[=+\-@]/.test(raw) ? `'${raw}` : raw;
      return `"${safe.replace(/"/g, '""')}"`;
    };
    const csv = `\uFEFF${[headers.join(','), ...rows.map((row) => headers.map((header) => quote(row[header])).join(','))].join('\r\n')}`;
    const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
    const link = document.createElement('a'); link.href = url; link.download = 'lifecycle.csv'; link.click(); URL.revokeObjectURL(url);
    toast(`已导出 ${count(rows.length)} 条生命周期记录`);
  }

  $('[data-lifecycle-search]').addEventListener('input', () => { state.page = 1; renderCards(); });
  $('[data-lifecycle-tier]').addEventListener('change', () => { state.page = 1; renderCards(); });
  $('[data-lifecycle-prev]').addEventListener('click', () => { if (state.page > 1) { state.page -= 1; renderCards(); window.scrollTo({ top: 0, behavior: 'smooth' }); } });
  $('[data-lifecycle-next]').addEventListener('click', () => { const pages = Math.max(1, Math.ceil(visibleRecords().length / pageSize)); if (state.page < pages) { state.page += 1; renderCards(); window.scrollTo({ top: 0, behavior: 'smooth' }); } });
  $('[data-lifecycle-assessment-search]').addEventListener('input', () => { assessmentPage = 1; renderAssessments(); });
  $('[data-lifecycle-assessment-stage]').addEventListener('change', () => { assessmentPage = 1; renderAssessments(); });
  $('[data-lifecycle-assessment-prev]').addEventListener('click', () => { if (assessmentPage > 1) { assessmentPage -= 1; renderAssessments(); } });
  $('[data-lifecycle-assessment-next]').addEventListener('click', () => { const pages = Math.max(1, Math.ceil(visibleAssessments().length / assessmentPageSize)); if (assessmentPage < pages) { assessmentPage += 1; renderAssessments(); } });
  $('[data-lifecycle-back]').addEventListener('click', closeDetail);
  $('[data-lifecycle-detail]').addEventListener('cancel', (event) => { event.preventDefault(); closeDetail(); });
  $('[data-lifecycle-detail]').addEventListener('click', (event) => { if (event.target === event.currentTarget) closeDetail(); });
  $('[data-lifecycle-columns-open]')?.addEventListener('click', openLifecycleColumnsDialog);
  document.querySelectorAll('[data-lifecycle-columns-close]').forEach((button) => button.addEventListener('click', closeLifecycleColumnsDialog));
  $('[data-lifecycle-template-apply]')?.addEventListener('click', applyLifecycleTemplate);
  $('[data-lifecycle-template-save]')?.addEventListener('click', async () => {
    const input = $('[data-lifecycle-template-name]');
    const label = input?.value.trim();
    const fields = normalizeLifecycleDetailFields(lifecycleColumnSelector?.getSelected());
    if (!label || !fields.length) return;
    const key = `custom_${Date.now()}`;
    lifecycleDetailTemplates[key] = fields;
    lifecycleDetailTemplateLabels[key] = label;
    try {
      await persistLifecycleTemplates();
      input.value = '';
      state.detailFields = fields;
      renderLifecycleColumnSelector(fields);
    } catch (_) {
      delete lifecycleDetailTemplates[key];
      delete lifecycleDetailTemplateLabels[key];
    }
  });
  $('[data-lifecycle-columns-select-all]')?.addEventListener('click', () => renderLifecycleColumnSelector(defaultLifecycleDetailFields));
  $('[data-lifecycle-columns-clear-all]')?.addEventListener('click', () => renderLifecycleColumnSelector(['month']));
  $('[data-lifecycle-columns-reset]')?.addEventListener('click', () => renderLifecycleColumnSelector(defaultLifecycleDetailFields));
  $('[data-lifecycle-columns-apply]')?.addEventListener('click', applyLifecycleColumns);
  lifecycleColumnsDialog?.addEventListener('cancel', (event) => { event.preventDefault(); closeLifecycleColumnsDialog(); });
  lifecycleColumnsDialog?.addEventListener('close', () => {
    lifecycleColumnsDialog.hidden = true;
    lifecycleColumnsReturnFocus?.focus?.();
    lifecycleColumnsReturnFocus = null;
  });
  $('[data-lifecycle-export]').addEventListener('click', exportCsv);
  $('[data-lifecycle-edit-close]')?.addEventListener('click', closeAssessmentEditor);
  $('[data-lifecycle-edit-cancel]')?.addEventListener('click', closeAssessmentEditor);
  editDialog.addEventListener('cancel', (event) => { event.preventDefault(); closeAssessmentEditor(); });
  editDialog.addEventListener('click', (event) => { if (event.target === editDialog) closeAssessmentEditor(); });
  editDialog.addEventListener('close', () => {
    editDialog.hidden = true;
    editingAssessment = null;
    assessmentPreviousFocus?.focus?.();
    assessmentPreviousFocus = null;
  });
  $('[data-lifecycle-edit-form]')?.addEventListener('submit', async (event) => { event.preventDefault(); if (!editingAssessment) return; if (Object.keys(assessmentPayload.capabilities || {}).length && !DemoApi.can(assessmentPayload, 'can_edit_stage')) { $('[data-lifecycle-edit-status]').textContent = '当前数据不足，暂不能调整阶段'; return; } const data = new FormData(event.currentTarget); try { await DemoApi.domainRequest(`/api/lifecycle/${encodeURIComponent(editingAssessment.product_id)}`, {method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({version:editingAssessment.version,manual_stage:data.get('manual_stage') || null,seasonal_attribute:data.get('seasonal_attribute') || null,lock:data.get('lock') === 'on',reason:data.get('reason'),operator:data.get('operator')})}); closeAssessmentEditor(); await loadAssessments(); } catch(error) { $('[data-lifecycle-edit-status]').textContent = error.message; } });
  document.querySelectorAll('[data-efficiency-mode]').forEach((button) => button.addEventListener('click', () => { state.efficiencyMode = button.dataset.efficiencyMode; document.querySelectorAll('[data-efficiency-mode]').forEach((item) => item.setAttribute('aria-pressed', String(item === button))); const record = state.summaries.find((item) => String(item.product_id) === state.selectedId); if (record) renderEfficiencyChart(selectedRows(record)); }));
  window.addEventListener('tmall:refresh', () => load());
  DemoLabels.load().then(() => { fillAssessmentOptions(); load(); });
})();

