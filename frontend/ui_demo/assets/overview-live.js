(function () {
  const $ = (selector) => document.querySelector(selector);
  const money = (value) => `¥${Number(value || 0).toLocaleString('zh-CN', { maximumFractionDigits: 0 })}`;
  const number = (value) => Number(value || 0).toLocaleString('zh-CN');
  const percent = (value) => `${(Number(value || 0) * 100).toFixed(1)}%`;
  const text = (node, value) => { if (node) node.textContent = value == null || value === '' ? '--' : String(value); };
  const list = (node, values) => { if (node) node.replaceChildren(...values); };
  const item = (tag, value, className) => { const node = document.createElement(tag); if (className) node.className = className; text(node, value); return node; };
  let trendChart = null;
  let activePeriod = '';
  let requestToken = 0;
  let dialogReturnFocus = null;

  function formatLocalDate(date = new Date()) {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
  }

  function previousMonth(period) {
    const [year, month] = String(period || '').split('-').map(Number);
    if (!year || !month) return '';
    const date = new Date(year, month - 2, 1);
    return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`;
  }
  function resolveMonthlyPeriod(state, monthlyRows) {
    const target = String(state?.endDate || formatLocalDate()).slice(0, 7);
    const months = monthlyRows.map((row) => row.period).filter(Boolean).sort();
    return months.filter((period) => period <= target).pop() || months.at(-1) || target;
  }
  function setStatus(selector, message, kind) {
    const node = $(selector);
    if (!node) return;
    node.replaceChildren();
    const wrap = document.createElement('div');
    wrap.className = `empty-state${kind === 'error' ? ' is-error' : ''}`;
    wrap.appendChild(item('span', message));
    node.appendChild(wrap);
  }
  function setTableStatus(body, message, colspan) {
    if (!body) return;
    const row = document.createElement('tr');
    const cellNode = document.createElement('td');
    cellNode.colSpan = colspan;
    text(cellNode, message);
    row.appendChild(cellNode);
    body.replaceChildren(row);
  }
  function queryRange(state) {
    return state?.startDate ? `&start=${encodeURIComponent(state.startDate)}&end=${encodeURIComponent(state.endDate)}` : '';
  }
  function unwrap(payload, key) {
    if (Array.isArray(payload)) return payload;
    return Array.isArray(payload?.[key]) ? payload[key] : [];
  }

  function renderKpis(overview) {
    const metrics = [
      ['payment_amount', money],
      ['net_sales', money],
      ['refund_rate', percent],
      ['expense_ratio', percent]
    ];
    metrics.forEach(([key, formatter]) => {
      const availability = overview.metric_availability?.[key];
      const value = overview[key];
      text($(`[data-overview-kpi="${key}"]`), value == null ? '--' : formatter(value));
      text(
        $(`[data-overview-kpi-meta="${key}"]`),
        availability === 'missing-fields' ? '字段缺失，暂不可计算' : `数据截至 ${overview.data_cutoff_date || '--'}`,
      );
    });
  }
  function renderContext(overview) {
    const context = overview.context || {}; const batch = context.latest_import;
    text($('[data-overview-context]'), batch ? `数据覆盖 ${context.start_date || '--'} 至 ${context.end_date || '--'}；最近导入 ${batch.source_filename}（${batch.completed_at || '--'}）` : '当前没有成功导入批次。');
    const todos = overview.action_todos || [];
    list($('[data-overview-action-todos]'), todos.length ? todos.map((todo) => { const row = document.createElement('div'); row.className = 'status-list__item'; row.append(item('span', `${todo.product_id} · ${todo.action_type}${todo.overdue ? ' · 已逾期' : ''}`, 'status-list__label'), item('span', `${todo.status} · ${todo.planned_at}`, 'status-list__value')); return row; }) : [item('div', '当前没有待办动作', 'empty-state')]);
  }

  function renderTrend(rows) {
    if (!window.DemoCharts || !$('#overviewTrend')) return;
    if (trendChart?.destroy) trendChart.destroy();
    trendChart = DemoCharts.line('overviewTrend', rows.map((row) => row.period), rows.map((row) => Number(row.gmv || 0)), '支付金额');
  }

  function renderTargets(data) {
    const target = data?.target || {};
    const actual = data?.actual || {};
    const values = [
      ['支付金额', `${money(actual.gsv)} / ${money(target.target_gsv)}`, data?.gsv_progress],
      ['推广花费', `${money(actual.ad_spend)} / ${money(target.target_ad_spend)}`, data?.ad_progress],
      ['净销售额', money(actual.net_sales), null],
      ['访客数', number(actual.visitors), null]
    ];
    list($('[data-overview-targets]'), values.map(([label, value, progress]) => {
      const row = document.createElement('div');
      row.className = 'status-list__item';
      const left = document.createElement('span'); left.className = 'status-list__label'; text(left, label);
      const right = document.createElement('span'); right.className = 'status-list__value'; text(right, progress == null ? value : `${value} · ${progress}%`);
      row.append(left, right);
      return row;
    }));
  }

  function isoWeekKey(value) {
    const date = new Date(`${value}T00:00:00`);
    const day = date.getDay() || 7;
    date.setDate(date.getDate() + 4 - day);
    const yearStart = new Date(date.getFullYear(), 0, 1);
    const week = Math.ceil((((date - yearStart) / 86400000) + 1) / 7);
    return `${date.getFullYear()}-W${String(week).padStart(2, '0')}`;
  }

  async function loadGoalLayers(state) {
    const year = Number(String(state?.endDate || formatLocalDate()).slice(0, 4));
    const targetRoot = $('[data-overview-targets]');
    try {
      const response = await DemoApi.domainRequest(`/api/goals/${year}/periods`);
      const payload = response.data || {};
      const levels = payload.levels || {};
      const dateKey = String(state?.endDate || formatLocalDate());
      const keys = [['年', 'year', String(year)], ['季', 'quarter', `${year}-Q${Math.floor((Number(dateKey.slice(5, 7)) - 1) / 3) + 1}`], ['月', 'month', dateKey.slice(0, 7)], ['周', 'week', isoWeekKey(dateKey)], ['日', 'date', dateKey]];
      const actual = payload.actual || {};
      const rows = keys.map(([label, grain, key]) => {
        const target = grain === 'year' ? levels.year : levels[grain]?.[key];
        const done = grain === 'year' ? actual.year : actual[grain]?.[key];
        if (target == null) return item('div', `${label} · ${key} · 尚未创建目标`, 'status-list__item');
        const rate = Number(target) ? `${(Number(done || 0) / Number(target) * 100).toFixed(1)}%` : '--';
        const row = document.createElement('div'); row.className = 'status-list__item';
        row.append(item('span', `${label} · ${key}`, 'status-list__label'), item('span', `${money(done)} / ${money(target)} · ${rate}`, 'status-list__value'));
        return row;
      });
      targetRoot.replaceChildren(...rows);
    } catch (error) {
      targetRoot.replaceChildren(item('div', '当前年度尚未创建目标', 'empty-state'));
    }
  }

  function renderAnomalies(data) {
    const anomalies = unwrap(data, 'anomalies');
    if (!anomalies.length) return setStatus('[data-overview-anomalies]', '当前周期未发现明显异常');
    list($('[data-overview-anomalies]'), anomalies.map((entry) => {
      const row = document.createElement('div');
      row.className = `alert-list__item${entry.severity === 'high' ? ' alert-list__item--danger' : ''}`;
      const copy = document.createElement('div');
      copy.append(item('strong', entry.label || entry.metric || '指标异常'), item('span', `较上期 ${Number(entry.change || 0).toFixed(1)}%`));
      row.appendChild(copy);
      return row;
    }));
  }

  function renderCustomers(data) {
    const values = [
      ['新客', data?.new_buyers, data?.new_ratio],
      ['老客', data?.returning_buyers, data?.returning_ratio]
    ];
    list($('[data-overview-customers]'), values.map(([label, count, ratio]) => {
      const row = document.createElement('div'); row.className = 'mini-bars__row';
      row.append(item('span', label, 'mini-bars__label'));
      const bar = document.createElement('div'); bar.className = 'progress'; const fill = document.createElement('span'); fill.style.width = `${Math.min(100, Number(ratio || 0) * 100)}%`; bar.appendChild(fill);
      row.appendChild(bar); row.append(item('span', `${number(count)} · ${percent(ratio)}`, 'mini-bars__value'));
      return row;
    }));
  }

  function renderFunnel(data) {
    const steps = unwrap(data, 'steps');
    if (!steps.length) return setStatus('[data-overview-funnel]', '当前月暂无漏斗数据');
    const max = Math.max(...steps.map((step) => Number(step.value || 0)), 1);
    list($('[data-overview-funnel]'), steps.map((step) => {
      const row = document.createElement('div'); row.className = 'funnel__row';
      row.append(item('span', step.name, 'mini-bars__label'));
      const bar = document.createElement('div'); bar.className = 'funnel__bar'; const fill = document.createElement('span'); fill.style.width = `${Number(step.value || 0) / max * 100}%`; bar.appendChild(fill);
      row.appendChild(bar); row.append(item('span', number(step.value), 'mini-bars__value'));
      return row;
    }));
  }

  function renderBenchmark(data) {
    const values = [['店铺 CTR', percent(data?.shop_ctr)], ['行业 CTR', percent(data?.industry_ctr)], ['差值', `${Number(data?.gap_pct || 0).toFixed(1)}%`]];
    list($('[data-overview-benchmark]'), values.map(([label, value]) => {
      const row = document.createElement('div'); row.className = 'status-list__item';
      row.append(item('span', label, 'status-list__label'), item('span', value, 'status-list__value')); return row;
    }));
  }

  function renderProducts(payload) {
    const products = unwrap(payload, 'data').slice(0, 5);
    const body = $('[data-overview-products]');
    if (!products.length) return setTableStatus(body, '当前日期范围暂无数据', 4);
    body.replaceChildren(...products.map((product) => {
      const row = document.createElement('tr');
      const title = product.title || product.product_id || '--';
      [title, money(product.payment_amount || product.total_gmv), number(product.payment_count || product.total_orders), percent(product.refund_rate)].forEach((value, index) => {
        const cell = document.createElement('td'); if (index) cell.className = 'num'; text(cell, value); row.appendChild(cell);
      });
      return row;
    }));
  }

  function renderEvents(events) {
    if (!events.length) return setStatus('[data-overview-events]', '暂无图表事件');
    list($('[data-overview-events]'), events.map((event) => {
      const row = document.createElement('div'); row.className = 'timeline__item';
      row.append(item('span', event.event_date, 'timeline__date'), item('strong', event.title, 'timeline__title'), item('span', event.description || '无说明', 'timeline__desc'));
      const button = document.createElement('button'); button.type = 'button'; button.className = 'button button--ghost'; button.setAttribute('aria-label', '删除图表事件'); button.appendChild(document.createElement('i')); button.firstChild.setAttribute('data-lucide', 'trash-2'); button.addEventListener('click', () => removeEvent(event.id));
      row.appendChild(button); return row;
    }));
    window.lucide?.createIcons();
  }

  function renderMatrix(rows) {
    const body = $('[data-overview-matrix]');
    if (!body) return;
    if (!rows.length) return setTableStatus(body, '当前日期范围暂无日度事实', 12);
    const money2 = (value) => value == null ? '不可计算' : money(value);
    const num2 = (value) => value == null ? '不可计算' : number(value);
    const pct2 = (value) => value == null ? '不可计算' : percent(value);
    body.replaceChildren(...rows.map((row) => {
      const tr = document.createElement('tr');
      const values = [row.date, money2(row.net_sales), money2(row.payment_amount), money2(row.successful_refund_amount), pct2(row.refund_rate), num2(row.visitors), num2(row.buyers), pct2(row.payment_conversion_rate), money2(row.ad_spend), pct2(row.expense_ratio), money2(row.average_order_value), row.data_source || '未知来源'];
      values.forEach((value, index) => { const td = document.createElement('td'); td.textContent = value; if (index > 0 && index < 11) td.className = 'num'; tr.appendChild(td); });
      return tr;
    }));
  }

  function parseReport(source) {
    const result = { period: activePeriod || '--', generated: '', metrics: [], products: [], risks: [] };
    let section = '';
    let currentProduct = null;
    String(source || '').split(/\r?\n/).forEach((rawLine) => {
      const line = rawLine.trim();
      if (!line) return;
      const periodMatch = line.match(/报告周期[：:]\s*([^（(]+)/);
      const generatedMatch = line.match(/生成时间[：:]\s*(.+)$/);
      if (periodMatch) { result.period = periodMatch[1].trim(); return; }
      if (generatedMatch) { result.generated = generatedMatch[1].trim(); return; }
      if (line.includes('核心指标')) { section = 'metrics'; return; }
      if (line.includes('销售TOP5') || line.includes('销售 TOP5')) { section = 'products'; return; }
      if (line.includes('异常指标')) { section = 'risks'; return; }
      if (section === 'metrics') {
        const match = line.match(/^[-–]\s*([^：:]+)[：:]\s*(.+)$/);
        if (match) result.metrics.push({ label: match[1].trim(), value: match[2].trim() });
        return;
      }
      if (section === 'products') {
        const titleMatch = line.match(/^(\d+)[.、]\s*(.+)$/);
        if (titleMatch) {
          currentProduct = { rank: Number(titleMatch[1]), title: titleMatch[2].trim(), sales: '--', visitors: '--', conversion: '--' };
          result.products.push(currentProduct);
          return;
        }
        const detailMatch = line.match(/销售额[：:]\s*(\S+)\s+访客[：:]\s*([\d,]+)\s+转化率[：:]\s*(\S+)/);
        if (detailMatch && currentProduct) [currentProduct.sales, currentProduct.visitors, currentProduct.conversion] = detailMatch.slice(1);
        return;
      }
      if (section === 'risks') {
        const match = line.match(/^[-–]\s*(.+)$/);
        if (match) result.risks.push(match[1].trim());
      }
    });
    return result;
  }

  function renderReport(source) {
    const report = parseReport(source);
    const root = $('[data-overview-report]');
    root?.setAttribute('aria-busy', 'false');
    text($('[data-overview-report-period]'), report.period);
    text($('[data-overview-report-time]'), report.generated ? `生成于 ${report.generated}` : '生成时间未知');
    const metricTone = (label) => label.includes('退款') ? 'danger' : label.includes('ROI') || label.includes('转化') ? 'success' : 'neutral';
    list($('[data-overview-report-kpis]'), report.metrics.map((metric) => {
      const card = document.createElement('article');
      card.className = `overview-report-kpi overview-report-kpi--${metricTone(metric.label)}`;
      card.append(item('span', metric.label), item('strong', metric.value));
      return card;
    }));
    const productRows = report.products.map((product) => {
      const row = document.createElement('div'); row.className = 'overview-report-product';
      const rank = item('span', product.rank, 'overview-report-product__rank');
      const copy = document.createElement('div'); copy.className = 'overview-report-product__copy'; copy.append(item('strong', product.title), item('span', `访客 ${product.visitors} · 转化 ${product.conversion}`));
      row.append(rank, copy, item('strong', product.sales, 'overview-report-product__value'));
      return row;
    });
    if (productRows.length) list($('[data-overview-report-products]'), productRows);
    else setStatus('[data-overview-report-products]', '暂无商品排行');
    const riskRows = report.risks.map((risk) => {
      const row = document.createElement('div'); row.className = `overview-report-risk${risk.includes('退款率') ? ' overview-report-risk--danger' : ''}`;
      const icon = document.createElement('i'); icon.setAttribute('data-lucide', risk.includes('退款率') ? 'shield-alert' : 'trending-down');
      row.append(icon, item('span', risk)); return row;
    });
    if (riskRows.length) list($('[data-overview-report-risks]'), riskRows);
    else setStatus('[data-overview-report-risks]', '本期未识别到异常指标');
    window.lucide?.createIcons();
  }

  async function loadReport(period) {
    const token = ++requestToken;
    const report = await DemoApi.request(`/api/report?dim=monthly&period=${encodeURIComponent(period)}`);
    if (token !== requestToken) return;
    renderReport(report?.report || '');
  }

  async function load(detail) {
    const token = ++requestToken;
    const state = detail || window.TmallDateRange?.getState() || {};
    const monthlyTrend = normalizeMonthlyTrend(await DemoApi.request('/api/trend?dim=monthly'));
    if (token !== requestToken) return;
    const period = resolveMonthlyPeriod(state, monthlyTrend);
    const prev = previousMonth(period);
    activePeriod = period;
    text($('[data-overview-period]'), state.startDate ? `${state.startDate} ~ ${state.endDate} · 月度口径 ${period}` : `月度口径 ${period}`);
    text($('[data-overview-month]'), `${period} / 上期 ${prev}`);
    const range = queryRange(state);
    const overviewParams = new URLSearchParams({ start: state.startDate, end: state.endDate });
    const requests = [
      DemoApi.domainRequest('/api/overview?' + overviewParams.toString()),
      DemoApi.request(`/api/trend?dim=daily${range}`),
      DemoApi.request(`/api/products?dim=daily&limit=5&sort=payment_amount&order=desc${range}`),
      DemoApi.request(`/api/target_progress?dim=monthly&period=${encodeURIComponent(period)}`),
      DemoApi.request(`/api/anomalies?dim=monthly&period=${encodeURIComponent(period)}&prev_period=${encodeURIComponent(prev)}`),
      DemoApi.request(`/api/customer_analysis?dim=monthly&period=${encodeURIComponent(period)}`),
      DemoApi.request(`/api/funnel?dim=monthly&period=${encodeURIComponent(period)}`),
      DemoApi.request(`/api/industry_benchmark?dim=monthly&period=${encodeURIComponent(period)}`),
      DemoApi.request(`/api/chart_events?chart_type=sales`)
    ];
    const [overviewResponse, trend, products, targets, anomalies, customers, funnel, benchmark, events] = await Promise.all(requests);
    let matrix = { data: { rows: [] } };
    try { matrix = await DemoApi.domainRequest('/api/overview/daily-matrix?' + overviewParams.toString()); } catch (error) { setTableStatus($('[data-overview-matrix]'), '日度矩阵加载失败', 12); }
    if (token !== requestToken) return;
    const rows = unwrap(trend, 'data');
    renderKpis(overviewResponse.data); renderContext(overviewResponse.data); renderTrend(rows); renderProducts(products); renderTargets(targets); await loadGoalLayers(state); renderAnomalies(anomalies); renderCustomers(customers); renderFunnel(funnel); renderBenchmark(benchmark); renderEvents(unwrap(events, 'events')); renderMatrix(matrix.data?.rows || []);
    const report = await DemoApi.request(`/api/report?dim=monthly&period=${encodeURIComponent(period)}`);
    if (token !== requestToken) return;
    renderReport(report?.report || '');
  }

  function guardedLoad(detail) {
    const expectedToken = requestToken + 1;
    load(detail).catch((error) => showError(error, expectedToken));
  }
  function guardedReportLoad() {
    const expectedToken = requestToken + 1;
    loadReport(activePeriod).catch((error) => showError(error, expectedToken));
  }

  function showError(error, token) {
    if (token && token !== requestToken) return;
    ['payment_amount', 'net_sales', 'refund_rate', 'expense_ratio'].forEach((key) => text($(`[data-overview-kpi="${key}"]`), '--'));
    ['[data-overview-targets]', '[data-overview-anomalies]', '[data-overview-funnel]', '[data-overview-customers]', '[data-overview-benchmark]', '[data-overview-events]'].forEach((selector) => setStatus(selector, '数据加载失败', 'error'));
    setTableStatus($('[data-overview-products]'), '数据加载失败', 4);
    $('[data-overview-report]')?.setAttribute('aria-busy', 'false');
    setStatus('[data-overview-report-kpis]', '报告加载失败', 'error');
    setStatus('[data-overview-report-products]', '报告加载失败', 'error');
    setStatus('[data-overview-report-risks]', '报告加载失败', 'error');
    console.error(error);
  }
  async function removeEvent(id) { await DemoApi.request(`/api/chart_events/${encodeURIComponent(id)}`, { method: 'DELETE' }); guardedLoad(); }
  async function submitEvent(form) {
    const data = new FormData(form);
    const submit = $('[data-overview-event-submit]');
    const status = $('[data-overview-event-status]');
    submit.disabled = true;
    text(status, '正在保存事件');
    try {
      await DemoApi.request('/api/chart_events', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ event_date: data.get('event_date'), title: String(data.get('title') || '').trim(), description: String(data.get('description') || '').trim(), color: data.get('color'), chart_type: 'sales' }) });
      $('[data-overview-event-dialog]').close(); form.reset(); window.DemoShell?.showToast?.('图表事件已保存'); guardedLoad();
    } catch (error) {
      text(status, error.message || '保存失败，请稍后重试');
    } finally { submit.disabled = false; }
  }
  const dialog = $('[data-overview-event-dialog]');
  function hideDialog() { dialog.hidden = true; $('[data-overview-event-status]').textContent = ''; dialogReturnFocus?.focus?.(); dialogReturnFocus = null; }
  function showDialog(event) { dialogReturnFocus = event?.currentTarget || document.activeElement; dialog.hidden = false; $('#overview-event-date').value = formatLocalDate(); $('[data-overview-event-status]').textContent = ''; dialog.showModal(); window.setTimeout(() => $('#overview-event-title-input').focus(), 0); }
  $('[data-overview-event-open]')?.addEventListener('click', showDialog);
  dialog?.addEventListener('close', hideDialog);
  dialog?.addEventListener('cancel', () => window.setTimeout(hideDialog, 0));
  document.querySelectorAll('[data-overview-event-close]').forEach((button) => button.addEventListener('click', () => dialog.close()));
  $('[data-overview-event-form]')?.addEventListener('submit', (event) => { event.preventDefault(); if (!event.currentTarget.reportValidity()) return; submitEvent(event.currentTarget); });
  $('[data-overview-report-refresh]')?.addEventListener('click', guardedReportLoad);
  $('[data-overview-matrix-refresh]')?.addEventListener('click', () => guardedLoad());
  window.addEventListener('tmall:date-range-change', (event) => guardedLoad(event.detail));
  window.addEventListener('tmall:refresh', () => guardedLoad());
  if (!window.TmallDateRange) guardedLoad();
  function normalizeMonthlyTrend(payload) { return unwrap(payload, 'data'); }
})();
