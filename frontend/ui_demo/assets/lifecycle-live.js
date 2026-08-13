(function () {
  const $ = (selector, root = document) => root.querySelector(selector);
  const state = { summaries: [], rowsByProduct: new Map(), range: null, selectedId: '', previousFocus: null, requestId: 0, scaleChart: null, efficiencyChart: null, efficiencyMode: 'refundRate', page: 1 };
  const pageSize = 24;
  const money = (value) => `￥${Number(value || 0).toLocaleString('zh-CN', { maximumFractionDigits: 1 })}`;
  const count = (value) => Number(value || 0).toLocaleString('zh-CN', { maximumFractionDigits: 0 });
  const percent = (value) => `${(Number(value || 0) * 100).toFixed(1)}%`;
  const sum = (rows, field) => rows.reduce((total, row) => total + Number(row[field] || 0), 0);
  const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char]);
  const toast = (message) => {
    if (window.DemoShell?.showToast) window.DemoShell.showToast(message);
    else window.alert(message);
  };
  const setStatus = (message) => { const target = $('[data-lifecycle-status]'); if (target) target.textContent = message; window.DemoShell?.setStatus?.(message); };
  let assessments = [];
  const assessmentLabel = (value) => ({data_accumulating:'数据积累中',new:'新品期',growth:'成长期',breakout:'爆发期',mature:'成熟期',decline:'衰退期',clearance:'清退期'})[value] || value || '--';
  const renderAssessments = () => { const body = $('[data-lifecycle-assessments]'); if (!body) return; body.replaceChildren(...assessments.map((entry) => { const row = document.createElement('tr'); const history = entry.history || []; [entry.title || entry.product_id, assessmentLabel(entry.stage), entry.confidence || '--', entry.seasonal_attribute || '数据不足', `${entry.rationale || '--'}；上架 ${entry.listed_days == null ? '--' : `${entry.listed_days} 天`}；转化趋势 ${entry.conversion_trend?.recent == null ? '数据不足' : `${(entry.conversion_trend.recent * 100).toFixed(2)}%`}；推广依赖 ${entry.promotion_dependency == null ? '数据不足' : `${(entry.promotion_dependency * 100).toFixed(2)}%`}；下一节点 ${entry.next_key_date || '--'}；迁移 ${history.length} 次`].forEach((value) => { const cell = document.createElement('td'); cell.textContent = value; row.appendChild(cell); }); const cell = document.createElement('td'); const button = document.createElement('button'); button.type='button'; button.className='button button--ghost'; button.textContent=entry.locked ? '已锁定' : '调整'; button.addEventListener('click', () => openAssessmentEditor(entry)); cell.appendChild(button); row.appendChild(cell); return row; })); if (!assessments.length) body.innerHTML = '<tr><td colspan="6">暂无商品</td></tr>'; };
  const editDialog = $('[data-lifecycle-edit-dialog]'); let editingAssessment = null;
  function openAssessmentEditor(entry) { editingAssessment = entry; const form = $('[data-lifecycle-edit-form]'); form.elements.manual_stage.value = entry.manual_stage || ''; form.elements.seasonal_attribute.value = entry.seasonal_attribute || ''; form.elements.lock.checked = Boolean(entry.locked); $('[data-lifecycle-edit-status]').textContent = ''; editDialog.hidden = false; editDialog.showModal(); }
  const loadAssessments = async () => { assessments = (await DemoApi.domainRequest('/api/lifecycle/assessments')).data; renderAssessments(); };

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
      const image = record.image_url ? `<img src="${escapeHtml(record.image_url)}" alt="" referrerpolicy="no-referrer">` : '<span class="product-thumb" aria-hidden="true"></span>';
      const trend = growth === null ? '无环比' : `${growth >= 0 ? '上升' : '下降'} ${percent(Math.abs(growth))}`;
      card.innerHTML = `<span class="lifecycle-card__header">${image}<span><span class="lifecycle-card__title">${escapeHtml(record.title || '未命名商品')}</span><span class="lifecycle-card__meta"><span class="badge ${tierClass(record.tier)}">${escapeHtml(record.tier || '未分层')}</span><span class="badge badge--muted">${escapeHtml(record.style || '未分类')}</span></span></span></span><span class="lifecycle-card__stats"><span class="lifecycle-card__stat"><strong>${money(sum(rows, 'gsv'))}</strong><span>累计 GSV</span></span><span class="lifecycle-card__stat"><strong>${count(rows.length)}</strong><span>活跃月数</span></span><span class="lifecycle-card__stat"><strong class="lifecycle-card__trend ${growth > 0.05 ? 'is-up' : growth < -0.05 ? 'is-down' : ''}">${trend}</strong><span>最近月环比</span></span></span>`;
      card.addEventListener('click', () => openDetail(record.product_id, card));
      grid.appendChild(card);
    });
    $('[data-lifecycle-count]').textContent = records.length ? `共 ${count(records.length)} 款商品，第 ${state.page} / ${totalPages} 页` : '无匹配商品';
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
    const tiers = [...new Set(state.summaries.map((record) => record.tier).filter(Boolean))].sort();
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
    setStatus('正在加载生命周期数据');
    try {
      const summaries = await DemoApi.request('/api/lifecycle?limit=2000');
      if (token !== state.requestId) return;
      state.rowsByProduct.clear();
      const summaryRows = Array.isArray(summaries) ? summaries : [];
      state.summaries = summaryRows.map((summary) => ({ ...summary, rows: parseSummaryRows(summary) })).filter((record) => record.rows.length);
      await loadAssessments();
      fillTiers();
      const months = [...new Set(state.summaries.flatMap((record) => record.rows.map((row) => row.month)))].sort();
      $('[data-lifecycle-period]').textContent = months.length ? `数据库全周期 ${months[0]} 至 ${months.at(-1)}，按商品查看完整月度表现` : '数据库暂无生命周期记录';
      renderCards();
      setStatus(`已加载 ${count(state.summaries.length)} 款商品的真实月度记录`);
      if (state.selectedId) await refreshDetail(token);
    } catch (error) {
      if (token !== state.requestId) return;
      state.summaries = [];
      grid.replaceChildren(createMessage('生命周期数据加载失败，请刷新后重试', 'panel__hint is-down'));
      grid.setAttribute('aria-busy', 'false');
      updateKpis([]);
      setStatus(error.message || '生命周期数据加载失败');
      toast('生命周期数据加载失败');
    }
  }

  function chartOptions() {
    return { responsive: true, maintainAspectRatio: false, interaction: { mode: 'index', intersect: false }, plugins: { legend: { position: 'bottom', labels: { boxWidth: 10 } } }, scales: { x: { grid: { display: false }, ticks: { maxRotation: 0, maxTicksLimit: 8 } }, y: { beginAtZero: true } } };
  }

  function renderScaleChart(rows) {
    state.scaleChart?.destroy();
    state.scaleChart = new EChartCompat($('#lifecycleScaleChart'), { type: 'bar', data: { labels: rows.map((row) => row.month), datasets: [{ type: 'line', label: 'GSV（万元）', data: rows.map((row) => Number(row.gsv || 0) / 10000), borderColor: '#2563eb', backgroundColor: 'rgba(37,99,235,.12)', fill: true, tension: .3, yAxisID: 'y' }, { label: '支付件数', data: rows.map((row) => Number(row.payment_qty || 0)), backgroundColor: 'rgba(22,163,74,.52)', yAxisID: 'y1' }] }, options: { ...chartOptions(), scales: { ...chartOptions().scales, y1: { beginAtZero: true, position: 'right', grid: { drawOnChartArea: false } } } } });
  }

  function renderDetailTable(rows) {
    const body = $('[data-lifecycle-detail-body]');
    body.replaceChildren();
    rows.forEach((item) => {
      const row = body.insertRow();
      [item.month, money(item.gsv), count(item.payment_qty), money(item.refund_amount), money(item.ad_spend), Number(item.ad_roi || 0) ? Number(item.ad_roi).toFixed(2) : '--'].forEach((value, index) => {
        const cell = row.insertCell();
        cell.textContent = value;
        if (index > 0) cell.className = 'num';
      });
    });
  }

  function renderEfficiencyChart(rows) {
    state.efficiencyChart?.destroy();
    const refundMode = state.efficiencyMode === 'refundRate';
    state.efficiencyChart = new EChartCompat($('#lifecycleEfficiencyChart'), { type: 'bar', data: { labels: rows.map((row) => row.month), datasets: [{ label: '退款金额（万元）', data: rows.map((row) => Number(row.refund_amount || 0) / 10000), backgroundColor: 'rgba(220,38,38,.48)' }, { label: '推广花费（万元）', data: rows.map((row) => Number(row.ad_spend || 0) / 10000), backgroundColor: 'rgba(37,99,235,.42)' }, { type: 'line', label: refundMode ? '退款率' : 'ROI', data: rows.map((row) => refundMode ? (Number(row.gsv || 0) ? Number(row.refund_amount || 0) / Number(row.gsv) : 0) : Number(row.ad_roi || 0)), borderColor: refundMode ? '#dc2626' : '#d97706', tension: .3, yAxisID: 'y1' }] }, options: { ...chartOptions(), scales: { ...chartOptions().scales, y1: { beginAtZero: true, position: 'right', grid: { drawOnChartArea: false }, ticks: { callback: (value) => refundMode ? `${Number(value * 100).toFixed(0)}%` : Number(value).toFixed(1) } } } } });
  }

  function metric(label, value) { return `<div class="lifecycle-metric"><strong title="${escapeHtml(value)}">${escapeHtml(value)}</strong><span>${escapeHtml(label)}</span></div>`; }

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
    $('[data-detail-meta]').textContent = `${record.tier || '未分层'} · ${record.style || '未分类'} · ${rows.length} 个月度记录`;
    $('[data-detail-id]').textContent = `商品 ID ${record.product_id} · ${rows[0].month} 至 ${latest.month}`;
    const image = $('[data-detail-image]'); image.src = record.image_url || ''; image.alt = record.title || '';
    const assessment = assessments.find((item) => String(item.product_id) === String(record.product_id));
    $('[data-lifecycle-metrics]').innerHTML = [metric('累计 GSV', money(sum(rows, 'gsv'))), metric('累计支付件数', count(sum(rows, 'payment_qty'))), metric('最近月 GSV', money(latest.gsv)), metric('最近月环比', previous ? `${change >= 0 ? '+' : ''}${percent(change)}` : '--'), metric('最近月退款率', percent(refundRate)), metric('最近月 ROI', Number(latest.ad_roi || 0) ? Number(latest.ad_roi).toFixed(2) : '--'), metric('上架时长', assessment?.listed_days == null ? '--' : `${assessment.listed_days} 天`), metric('下一关键节点', assessment?.next_key_date || '--')].join('');
    const history = assessment?.history || [];
    $('[data-lifecycle-insights]').innerHTML = [['success', '经营规模', `${latest.month} GSV ${money(latest.gsv)}`], [refundRate <= .1 ? 'success' : 'danger', '退款率', `${percent(refundRate)}，退款金额 ${money(latest.refund_amount)}`], [Number(latest.ad_roi || 0) >= 3 ? 'success' : 'warning', '投放效率', Number(latest.ad_roi || 0) ? `ROI ${Number(latest.ad_roi).toFixed(2)}` : '当前月无推广数据'], [change >= 0 ? 'success' : 'danger', '月度趋势', previous ? `${change >= 0 ? '较上月增长' : '较上月下降'} ${percent(Math.abs(change))}` : '暂无上月对比'], ['info', '判断依据', `转化趋势 ${assessment?.conversion_trend?.recent == null ? '数据不足' : `${(assessment.conversion_trend.recent * 100).toFixed(2)}%`}；推广依赖 ${assessment?.promotion_dependency == null ? '数据不足' : `${(assessment.promotion_dependency * 100).toFixed(2)}%`}；阶段迁移 ${history.length} 次`]].map(([tone, title, text]) => `<div class="lifecycle-insight lifecycle-insight--${tone}"><strong>${title}</strong><span>${text}</span></div>`).join('');
    renderScaleChart(rows); renderEfficiencyChart(rows); renderDetailTable(rows);
    if (window.lucide) window.lucide.createIcons();
  }

  async function openDetail(productId, trigger) {
    state.selectedId = String(productId); state.previousFocus = trigger || document.activeElement;
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
    const rows = visibleRecords().flatMap((record) => selectedRows(record).map((row) => ({ '商品 ID': record.product_id, '商品名称': record.title || '', '商品分层': record.tier || '', 月份: row.month, GSV: row.gsv || 0, 支付件数: row.payment_qty || 0, 退款金额: row.refund_amount || 0, 推广花费: row.ad_spend || 0, ROI: row.ad_roi || 0 })));
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
  $('[data-lifecycle-back]').addEventListener('click', closeDetail);
  $('[data-lifecycle-detail]').addEventListener('cancel', (event) => { event.preventDefault(); closeDetail(); });
  $('[data-lifecycle-detail]').addEventListener('click', (event) => { if (event.target === event.currentTarget) closeDetail(); });
  $('[data-lifecycle-export]').addEventListener('click', exportCsv);
  $('[data-lifecycle-edit-close]')?.addEventListener('click', () => editDialog.close());
  $('[data-lifecycle-edit-form]')?.addEventListener('submit', async (event) => { event.preventDefault(); if (!editingAssessment) return; const data = new FormData(event.currentTarget); try { await DemoApi.domainRequest(`/api/lifecycle/${encodeURIComponent(editingAssessment.product_id)}`, {method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({version:editingAssessment.version,manual_stage:data.get('manual_stage') || null,seasonal_attribute:data.get('seasonal_attribute') || null,lock:data.get('lock') === 'on',reason:data.get('reason'),operator:data.get('operator')})}); editDialog.close(); await loadAssessments(); } catch(error) { $('[data-lifecycle-edit-status]').textContent = error.message; } });
  document.querySelectorAll('[data-efficiency-mode]').forEach((button) => button.addEventListener('click', () => { state.efficiencyMode = button.dataset.efficiencyMode; document.querySelectorAll('[data-efficiency-mode]').forEach((item) => item.setAttribute('aria-pressed', String(item === button))); const record = state.summaries.find((item) => String(item.product_id) === state.selectedId); if (record) renderEfficiencyChart(selectedRows(record)); }));
  window.addEventListener('tmall:refresh', () => load());
  load();
})();
