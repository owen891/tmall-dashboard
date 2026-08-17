(function () {
  const $ = (selector) => document.querySelector(selector);
  const money = (value) => `¥${Number(value || 0).toLocaleString('zh-CN', { maximumFractionDigits: 0 })}`;
  const number = (value) => Number(value || 0).toLocaleString('zh-CN');
  const percent = (value) => `${(Number(value || 0) * 100).toFixed(1)}%`;
  const text = (node, value) => { if (node) node.textContent = value == null || value === '' ? '--' : String(value); };
  const textAll = (selector, value) => document.querySelectorAll(selector).forEach((node) => text(node, value));
  const list = (node, values) => { if (node) node.replaceChildren(...values); };
  const item = (tag, value, className) => { const node = document.createElement(tag); if (className) node.className = className; text(node, value); return node; };
  let trendCharts = [];
  let latestTrendRows = [];
  let activePeriod = '';
  let requestToken = 0;
  let dialogReturnFocus = null;
  let overviewPayload = null;
  let latestMatrix = { rows: [] };
  const matrixColumns = Object.freeze([
    { key: 'date', label: '日期', format: 'text', required: true },
    { key: 'net_sales', label: '净销售额', format: 'money' },
    { key: 'payment_amount', label: '支付金额', format: 'money' },
    { key: 'successful_refund_amount', label: '成功退款金额', format: 'money' },
    { key: 'refund_rate', label: '退款率', format: 'percent' },
    { key: 'visitors', label: '商品访客数', format: 'number' },
    { key: 'buyers', label: '买家数', format: 'number' },
    { key: 'payment_conversion_rate', label: '商品支付转化率', format: 'percent' },
    { key: 'ad_spend', label: '推广花费', format: 'money' },
    { key: 'expense_ratio', label: '费比', format: 'percent' },
    { key: 'average_order_value', label: '客单价', format: 'money' },
    { key: 'returning_buyer_ratio', label: '老客成交占比', format: 'percent' },
    { key: 'source_batch_id', label: '来源批次', format: 'source' },
    { key: 'data_source', label: '数据来源', format: 'source' },
  ]);
  const matrixColumnsByKey = new Map(matrixColumns.map((column) => [column.key, column]));
  const matrixColumnsStorageKey = 'tmall-overview-matrix-columns-v2';
  let matrixVisibleColumns = loadMatrixColumns();
  let matrixColumnSelector = null;
  let matrixColumnsReturnFocus = null;
  const overviewEventsEndpoint = '/api/overview/events?chart_type=sales';
  const trendMetricLabels = Object.freeze({
    net_sales: '净销售额', payment_amount: '支付金额', visitors: '商品访客数',
    payment_conversion_rate: '商品支付转化率', ad_spend: '推广花费', ad_roi: '推广 ROI',
    refund_rate: '退款率', expense_ratio: '费比'
  });
  let homeTrendModes = ['net_sales', 'payment_amount', 'ad_spend'];

  function formatLocalDate(date = new Date()) {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
  }

  function previousMonth(period, offset = 1) {
    const [year, month] = String(period || '').split('-').map(Number);
    if (!year || !month) return '';
    const date = new Date(year, month - 1 - offset, 1);
    return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`;
  }
  function resolveMonthlyPeriod(state, monthlyRows) {
    const target = String(state?.endDate || formatLocalDate()).slice(0, 7);
    const months = monthlyRows.map((row) => row.period).filter(Boolean).sort();
    return months.filter((period) => period <= target).pop() || months.at(-1) || target;
  }
  function setStatus(selector, message, kind, retry) {
    const node = $(selector);
    if (!node) return;
    node.replaceChildren();
    const wrap = document.createElement('div');
    wrap.className = `empty-state${kind === 'error' ? ' is-error' : ''}`;
    wrap.appendChild(item('span', message));
    if (retry) {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'button button--ghost';
      button.setAttribute('data-overview-retry', 'true');
      button.textContent = '重试';
      button.addEventListener('click', retry);
      wrap.appendChild(button);
    }
    node.appendChild(wrap);
  }
  function setTableStatus(body, message, colspan, retry) {
    if (!body) return;
    const row = document.createElement('tr');
    const cellNode = document.createElement('td');
    cellNode.colSpan = colspan;
    text(cellNode, message);
    if (retry) {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'button button--ghost';
      button.setAttribute('data-overview-retry', 'true');
      button.textContent = '重试';
      button.addEventListener('click', retry);
      cellNode.appendChild(document.createTextNode(' '));
      cellNode.appendChild(button);
    }
    row.appendChild(cellNode);
    body.replaceChildren(row);
  }
  function queryRange(state) {
    return state?.startDate ? `&start=${encodeURIComponent(state.startDate)}&end=${encodeURIComponent(state.endDate)}` : '';
  }
  function unwrap(payload, key) {
    if (Array.isArray(payload)) return payload;
    if (Array.isArray(payload?.[key])) return payload[key];
    if (Array.isArray(payload?.[key]?.rows)) return payload[key].rows;
    if (Array.isArray(payload?.data?.[key])) return payload.data[key];
    if (Array.isArray(payload?.data?.rows)) return payload.data.rows;
    return [];
  }

  function normalizeMatrixColumns(columns) {
    const selected = [...new Set((columns || []).map(String).filter((key) => matrixColumnsByKey.has(key)))];
    return ['date', ...selected.filter((key) => key !== 'date')];
  }

  function loadMatrixColumns() {
    try {
      const stored = JSON.parse(localStorage.getItem(matrixColumnsStorageKey));
      return Array.isArray(stored) && stored.length ? normalizeMatrixColumns(stored) : matrixColumns.map((column) => column.key);
    } catch (_) { return matrixColumns.map((column) => column.key); }
  }

  function saveMatrixColumns() {
    try { localStorage.setItem(matrixColumnsStorageKey, JSON.stringify(matrixVisibleColumns)); } catch (_) {}
  }

  function renderMatrixHeader() {
    const head = $('[data-overview-matrix-head]');
    if (!head) return;
    head.replaceChildren(...matrixVisibleColumns.map((key) => {
      const column = matrixColumnsByKey.get(key);
      const th = document.createElement('th');
      th.dataset.fieldKey = key;
      th.textContent = column.label;
      if (column.format !== 'text' && column.format !== 'source') th.className = 'num';
      return th;
    }));
  }

  function matrixValue(row, column) {
    const source = row.source_detail || row;
    const value = column.key === 'source_batch_id'
      ? source.source_filename || source.source_batch_id || row.source_batch_id
      : column.key === 'data_source'
        ? row.data_source || source.data_source
        : row[column.key];
    if (value == null || value === '') {
      if (['average_order_value', 'returning_buyer_ratio'].includes(column.key) && Number(row.buyers || 0) === 0) return '--';
      return '不可计算';
    }
    if (column.format === 'money') return money(value);
    if (column.format === 'number') return number(value);
    if (column.format === 'percent') return percent(value);
    return String(value);
  }

  function deriveKpiFallback(matrix) {
    const rows = Array.isArray(matrix?.rows) ? matrix.rows : [];
    let visitors = 0;
    let buyers = 0;
    let visitorsSeen = false;
    let buyersSeen = false;
    rows.forEach((row) => {
      if (row.visitors != null && row.visitors !== '') { visitors += Number(row.visitors) || 0; visitorsSeen = true; }
      if (row.buyers != null && row.buyers !== '') { buyers += Number(row.buyers) || 0; buyersSeen = true; }
    });
    return { visitors: visitorsSeen ? visitors : null, payment_conversion_rate: visitorsSeen && buyersSeen && visitors > 0 ? buyers / visitors : null };
  }

  function renderKpis(overview, comparison, matrix) {
    const fallback = deriveKpiFallback(matrix);
    const metrics = [
      ['payment_amount', money],
      ['net_sales', money],
      ['visitors', number],
      ['ad_spend', money],
      ['ad_roi', (value) => Number(value || 0).toFixed(2)],
      ['refund_rate', percent],
      ['expense_ratio', percent],
      ['payment_conversion_rate', percent],
      ['average_order_value', money],
      ['returning_buyer_ratio', percent]
    ];
    metrics.forEach(([key, formatter]) => {
      const fallbackValue = key === 'visitors' ? fallback.visitors : key === 'payment_conversion_rate' ? fallback.payment_conversion_rate : null;
      const availability = overview.metric_availability?.[key] === 'missing-fields' && fallbackValue != null ? 'available' : overview.metric_availability?.[key];
      const value = key === 'visitors' ? (overview.visitors ?? overview.product_visitors ?? fallback.visitors) : key === 'payment_conversion_rate' ? (overview.payment_conversion_rate ?? fallback.payment_conversion_rate) : key === 'ad_roi' && overview.ad_roi == null
        ? (Number(overview.ad_spend) > 0 ? Number(overview.payment_amount || 0) / Number(overview.ad_spend) : null)
        : overview[key];
      textAll(`[data-overview-kpi="${key}"]`, value == null ? '--' : formatter(value));
      const compareKey = { payment_amount: 'gmv', net_sales: 'net_sales', visitors: 'visitors', ad_spend: 'ad_spend', ad_roi: 'roi', refund_rate: 'refund_rate', payment_conversion_rate: 'conversion', expense_ratio: 'expense_ratio' }[key];
      const change = compareKey && comparison?.kpi_compare?.[compareKey];
      const direction = Number(change?.change_pct || 0);
      const delta = key === 'refund_rate' || key === 'payment_conversion_rate'
        ? Number((Number(change?.period_b || 0) - Number(change?.period_a || 0)) * 100).toFixed(1)
        : key === 'ad_roi'
          ? Number(Number(change?.period_b || 0) - Number(change?.period_a || 0)).toFixed(2)
          : Number(direction).toFixed(1);
      const isCostMetric = ['ad_spend', 'refund_rate', 'expense_ratio'].includes(key);
      const trendClass = direction === 0 ? '' : ((direction > 0) !== isCostMetric ? 'is-up' : 'is-down');
      const metaNodes = [...document.querySelectorAll(`[data-overview-kpi-meta="${key}"]`)];
      metaNodes.forEach((node) => {
        node.classList.toggle('is-up', trendClass === 'is-up');
        node.classList.toggle('is-down', trendClass === 'is-down');
        node.textContent = availability === 'missing-fields'
          ? '字段缺失，暂不可计算'
          : change?.change_pct == null
            ? `数据截至 ${overview.data_cutoff_date || '--'}`
            : `${direction >= 0 ? '↑' : '↓'} ${key === 'refund_rate' || key === 'payment_conversion_rate' ? Math.abs(Number(delta)).toFixed(1) + 'pp' : Math.abs(Number(delta)).toFixed(key === 'ad_roi' ? 2 : 1) + (key === 'ad_roi' ? '' : '%')} 较上期`;
      });
    });
    const netSales = overview.net_sales;
    text($('[data-overview-summary="net_sales"]'), netSales == null ? '--' : money(netSales));
    text($('[data-overview-summary-meta="net_sales"]'), overview.data_cutoff_date ? `数据截至 ${overview.data_cutoff_date}` : '等待加载');
    text($('[data-overview-cutoff]'), overview.data_cutoff_date ? `数据截至 ${overview.data_cutoff_date}` : '数据截至 --');
    const freshness = overview.context?.latest_import?.completed_at || overview.data_cutoff_date;
    text($('[data-overview-summary="freshness"]'), freshness ? (String(freshness).slice(0, 10) === String(overview.data_cutoff_date || '').slice(0, 10) ? '98%' : '已更新') : '--');
    text($('[data-overview-summary-meta="freshness"]'), freshness ? `最近导入 ${String(freshness).slice(0, 16)}` : '最近导入');
    const delta = comparison?.kpi_compare?.net_sales?.change_pct;
    const deltaNode = $('[data-overview-summary-delta]');
    text(deltaNode, delta == null ? '较上期 --' : `较上期 ${delta >= 0 ? '+' : ''}${Number(delta).toFixed(1)}%`);
    deltaNode?.classList.toggle('delta--positive', delta != null && delta >= 0);
    deltaNode?.classList.toggle('delta--negative', delta != null && delta < 0);
  }
  function renderContext(overview) {
    const context = overview.context || {}; const batch = context.latest_import;
    const missing_date_ranges = overview.missing_date_ranges || [];
    const source_batches = overview.source_batches || [];
    const changes = overview.changes || [];
    const grain = overview.data_grain || context.data_grain;
    const grainLabel = grain === 'monthly' ? '月度派米数据' : '日度事实';
    text($('[data-overview-context]'), batch ? `${grainLabel}覆盖 ${context.start_date || '--'} 至 ${context.end_date || '--'}；最近导入 ${batch.source_filename}（${batch.completed_at || '--'}）` : `当前没有导入的${grainLabel}。`);
    const start = context.start_date;
    const end = context.end_date;
    const coverage = start && end ? (grain === 'monthly' ? Math.max(1, (new Date(`${end}-01T00:00:00`).getFullYear() - new Date(`${start}-01T00:00:00`).getFullYear()) * 12 + new Date(`${end}-01T00:00:00`).getMonth() - new Date(`${start}-01T00:00:00`).getMonth() + 1) : Math.max(1, Math.round((new Date(`${end}T00:00:00`) - new Date(`${start}T00:00:00`)) / 86400000) + 1)) : null;
    text($('[data-overview-coverage]'), coverage ? `覆盖 ${coverage} ${grain === 'monthly' ? '个月' : '天'}` : `覆盖 -- ${grain === 'monthly' ? '个月' : '天'}`);
    const todos = overview.action_todos || [];
    const rows = todos.length ? todos.map((todo) => {
      const row = document.createElement('div'); row.className = 'status-list__item';
      const value = item('span', `${DemoLabels.label('status', todo.status, '待处理')} · ${todo.planned_at}`, 'status-list__value');
      if (['blocked', 'calculation_failed'].includes(todo.status)) value.classList.add('status-list__value--danger');
      else if (['pending_review', 'pending_execution'].includes(todo.status)) value.classList.add('status-list__value--warning');
      else if (['completed', 'observing'].includes(todo.status)) value.classList.add('status-list__value--success');
      row.append(item('span', `${todo.product_title || todo.product_id} · ${DemoLabels.label('action', todo.action_type, todo.action_type || '运营动作')}${todo.overdue ? ' · 已逾期' : ''}`, 'status-list__label'), value);
      return row;
    }) : [item('div', '当前没有待办动作', 'empty-state')];
    list($('[data-overview-home-actions]'), rows.map((node) => node.cloneNode(true)));
    const pending = todos.filter((todo) => ['pending_review', 'blocked', 'pending_execution', 'executing'].includes(todo.status)).length;
    textAll('[data-overview-summary="actions"]', String(pending).padStart(2, '0'));
  }

  function renderTrend(rows) {
    if (!window.DemoCharts) return;
    latestTrendRows = rows;
    trendCharts.forEach((chart) => chart?.destroy?.());
    trendCharts = [];
    const periods = rows.map((row) => row.period);
    const valueFor = (row, mode) => {
      const paymentAmount = Number(row.gmv ?? row.payment_amount ?? 0);
      const adSpend = Number(row.ad_spend ?? 0);
      const refund = Number(row.refund ?? row.refund_amount ?? 0);
      return {
        net_sales: row.net_sales,
        payment_amount: paymentAmount,
        visitors: row.visitors,
        ad_spend: adSpend,
        payment_conversion_rate: row.conversion ?? row.payment_conversion_rate,
        expense_ratio: paymentAmount > 0 ? adSpend / paymentAmount : null,
        refund_rate: paymentAmount > 0 ? refund / paymentAmount : null,
        ad_roi: adSpend > 0 ? paymentAmount / adSpend : null,
      }[mode];
    };
    const modes = homeTrendModes.length ? homeTrendModes : ['net_sales'];
    const compare = modes.length > 1;
    const normalize = (values) => { const base = values.find((value) => Number.isFinite(value) && value !== 0); return base ? values.map((value) => Number(((value / base) * 100).toFixed(1))) : values; };
    const datasets = modes.map((mode) => { const values = rows.map((row) => Number(valueFor(row, mode) ?? 0)); return { label: trendMetricLabels[mode] || mode, data: compare ? normalize(values) : values }; });
    const target = $('#overviewHomeTrend');
    if (!target) return;
    [target].forEach((node) => {
      const chart = DemoCharts.lineMulti
        ? DemoCharts.lineMulti(node.id, periods, datasets)
        : DemoCharts.line(node.id, periods, datasets[0].data, datasets[0].label);
      trendCharts.push(chart);
    });
  }

  function renderTargets(data) {
    const target = data?.target || {};
    const actual = data?.actual || {};
    const values = [
      ['支付金额', `${money(actual.gsv)} / ${money(target.target_gsv)}`, data?.gsv_progress],
      ['推广花费', `${money(actual.ad_spend)} / ${money(target.target_ad_spend)}`, data?.ad_progress],
      ['净销售额', money(actual.net_sales), null],
      ['商品访客数', number(actual.visitors), null]
    ];
    const renderRows = () => values.map(([label, value, progress]) => {
      const row = document.createElement('div');
      row.className = 'status-list__item';
      const left = document.createElement('span'); left.className = 'status-list__label'; text(left, label);
      const right = document.createElement('span'); right.className = 'status-list__value'; text(right, progress == null ? value : `${value} · ${progress}%`);
      row.append(left, right);
      return row;
    });
    list($('[data-overview-home-targets]'), renderRows());
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
    const targetRoots = [$('[data-overview-home-targets]')].filter(Boolean);
    try {
      const response = await DemoApi.domainRequest(`/api/goals/${year}/periods`);
      const payload = response.data || {};
      const levels = payload.levels || {};
      const dateKey = String(state?.endDate || formatLocalDate());
      const keys = [['年', 'year', String(year)], ['季', 'quarter', `${year}-Q${Math.floor((Number(dateKey.slice(5, 7)) - 1) / 3) + 1}`], ['月', 'month', dateKey.slice(0, 7)], ['周', 'week', isoWeekKey(dateKey)], ['日', 'date', dateKey]];
      const actual = payload.actual || {};
      const homeKeys = [keys[3], keys[2], keys[1], keys[0]];
      const rows = homeKeys.map(([label, grain, key]) => {
        const target = grain === 'year' ? levels.year : levels[grain]?.[key];
        const done = grain === 'year' ? actual.year : actual[grain]?.[key];
        if (target == null) return item('div', `${label} · ${key} · 尚未创建目标`, 'status-list__item');
        const rate = Number(target) ? `${(Number(done || 0) / Number(target) * 100).toFixed(1)}%` : '--';
        const row = document.createElement('div'); row.className = 'status-list__item';
        row.append(item('span', `${label} · ${key}`, 'status-list__label'), item('span', `${money(done)} / ${money(target)} · ${rate}`, 'status-list__value'));
        return row;
      });
      targetRoots.forEach((root) => root.replaceChildren(...rows.map((row) => row.cloneNode(true))));
      adaptHomeTargets();
      const annual = levels.year;
      const annualActual = actual.year;
      textAll('[data-overview-summary="target"]', annual == null ? '--' : `${Number(annual) ? (Number(annualActual || 0) / Number(annual) * 100).toFixed(1) : 0}%`);
    } catch (error) {
      targetRoots.forEach((root) => root.replaceChildren(item('div', '当前年度尚未创建目标', 'empty-state')));
      textAll('[data-overview-summary="target"]', '--');
    }
  }

  function adaptHomeTargets() {
    const root = $('[data-overview-home-targets]');
    if (!root) return;
      const cards = [...root.querySelectorAll('.status-list__item')].slice(0, 4).map((source, index) => {
        const row = document.createElement('div'); row.className = 'overview-v2-target';
        const label = source.querySelector('.status-list__label')?.textContent || source.textContent || '--';
        const homeLabel = { '周': '本周净销售目标', '月': '本月净销售目标', '季': '季度净销售目标', '年': '年度净销售目标' }[label.charAt(0)] || label;
        const value = source.querySelector('.status-list__value')?.textContent || '';
        const rate = value.match(/([\d.]+)%/)?.[1] || '--';
        const head = document.createElement('div'); head.className = 'overview-v2-target__head'; head.append(item('span', homeLabel), item('strong', rate === '--' ? '--' : `${rate}%`));
      const progress = document.createElement('div'); progress.className = `overview-v2-progress overview-v2-progress--${['warning', 'success', 'info', 'brand'][index] || 'brand'}`; const fill = document.createElement('span'); fill.style.width = `${Math.min(100, Number(rate) || 0)}%`; progress.appendChild(fill);
      row.append(head, progress, item('div', value || '尚未创建目标', 'overview-v2-target__meta')); return row;
    });
    root.className = 'overview-v2-targets';
    root.replaceChildren(...(cards.length ? cards : [item('div', '当前年度尚未创建目标', 'empty-state')]));
  }

  function renderAnomalies(data) {
    const anomalies = unwrap(data, 'anomalies');
    if (!anomalies.length) return setStatus('[data-overview-home-anomalies]', '当前周期未发现明显异常');
    const rows = anomalies.map((entry) => {
      const row = document.createElement('div');
      row.className = `alert-list__item${entry.severity === 'high' ? ' alert-list__item--danger' : ''}`;
      const copy = document.createElement('div');
      copy.append(item('strong', entry.label || entry.metric || '指标异常'), item('span', `较上期 ${Number(entry.change || 0).toFixed(1)}%`));
      row.appendChild(copy);
      return row;
    });
    list($('[data-overview-home-anomalies]'), anomalies.map((entry) => {
      const row = document.createElement('div'); row.className = `overview-v2-alert${entry.severity === 'high' ? ' overview-v2-alert--danger' : ''}`;
      const copy = document.createElement('div'); copy.append(item('strong', entry.label || entry.metric || '指标异常'), item('span', `较上期 ${Number(entry.change || 0).toFixed(1)}%`)); row.append(copy, item('b', `${Number(entry.current || 0).toLocaleString('zh-CN')}`)); return row;
    }));
  }

  function renderHomeProducts(payload) {
    const products = unwrap(payload, 'data').slice(0, 5);
    const root = $('[data-overview-home-products]');
    if (!root) return;
    if (!products.length) return setStatus('[data-overview-home-products]', '当前日期范围暂无商品数据');
    root.replaceChildren(...products.map((product, index) => {
      const row = document.createElement('div'); row.className = 'overview-v2-report__row';
      const thumbnailUrl = String(product.image_url || '').trim();
      const image = thumbnailUrl ? document.createElement('img') : document.createElement('span'); image.className = 'overview-v2-product-image';
      if (thumbnailUrl) { image.src = thumbnailUrl; image.alt = product.title || product.product_id || ''; image.loading = 'eager'; image.decoding = 'async'; }
      else { image.classList.add('overview-v2-product-image--placeholder'); image.setAttribute('aria-hidden', 'true'); image.textContent = String(product.title || product.product_id || '商品').trim().slice(0, 1); }
      image.addEventListener('error', () => {
        const placeholder = document.createElement('span');
        placeholder.className = 'overview-v2-product-image overview-v2-product-image--placeholder';
        placeholder.setAttribute('aria-hidden', 'true');
        placeholder.textContent = String(product.title || product.product_id || '商品').trim().slice(0, 1);
        image.replaceWith(placeholder);
      });
      const rank = item('span', index + 1, 'overview-v2-report__rank');
      const copy = document.createElement('div'); copy.className = 'overview-v2-report__copy';
      const title = document.createElement('strong'); text(title, product.title || product.product_id || '--'); title.appendChild(item('small', ` · ID ${product.product_id || '--'}`, 'overview-v2-product-id'));
      const metrics = document.createElement('span'); metrics.className = 'overview-v2-product-metrics is-expanded';
      [['商品支付转化率', product.payment_conversion ?? product.conversion], ['客单价', product.avg_order_value], ['推广花费', product.ad_spend], ['费比', product.expense_ratio], ['推广 ROI', product.ad_roi], ['退款率', product.refund_rate]].forEach(([label, value]) => { const metric = document.createElement('span'); metric.append(item('span', label), item('b', label === '推广 ROI' ? Number(value || 0).toFixed(2) : label.includes('率') ? percent(value) : money(value))); metrics.appendChild(metric); });
      const toggle = document.createElement('button'); toggle.type = 'button'; toggle.className = 'overview-v2-metrics-toggle'; toggle.textContent = '−'; toggle.setAttribute('aria-expanded', 'true'); toggle.setAttribute('aria-label', '收起更多指标'); toggle.addEventListener('click', () => { const expanded = metrics.classList.toggle('is-expanded'); metrics.classList.toggle('is-collapsed', !expanded); toggle.textContent = expanded ? '−' : '+3'; toggle.setAttribute('aria-expanded', String(expanded)); }); metrics.appendChild(toggle);
      copy.append(title, metrics); row.append(image, rank, copy, item('strong', money(product.payment_amount || product.total_gmv), 'overview-v2-report__value')); return row;
    }));
  }

  function renderHomeMatrix(matrix) {
    const body = $('[data-overview-home-matrix]');
    if (!body) return;
    latestMatrix = matrix || { rows: [] };
    const rows = [...(matrix?.rows || [])].reverse();
    renderMatrixHeader();
    if (!rows.length) return setTableStatus(body, '当前未导入日度明细；月度派米数据已用于上方指标和趋势', matrixVisibleColumns.length);
    body.replaceChildren(...rows.map((row) => {
      const tr = document.createElement('tr');
      matrixVisibleColumns.forEach((key) => {
        const column = matrixColumnsByKey.get(key);
        const td = document.createElement('td');
        td.dataset.fieldKey = key;
        td.textContent = matrixValue(row, column);
        if (column.format !== 'text' && column.format !== 'source') td.className = 'num';
        tr.appendChild(td);
      });
      return tr;
    }));
    window.TmallTableControls?.refresh?.();
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

  function renderHomeReport(source) {
    const root = $('[data-overview-home-report]');
    if (!root) return;
    const report = parseReport(source);
    text($('[data-overview-home-report-period]'), report.period);
    const rows = [];
    if (report.metrics[0]) rows.push(['规模', report.metrics[0].value, false]);
    if (report.risks[0]) rows.push(['风险', report.risks[0], true]);
    if (report.products.length) rows.push(['下一步', `重点商品 ${report.products.length} 款，优先处理待复盘动作`, false]);
    root.replaceChildren(...(rows.length ? rows : [['经营状态', '本期暂无可展示的经营报告', false]]).map(([title, detail, danger]) => {
      const row = document.createElement('div'); row.className = `overview-v2-alert${danger ? ' overview-v2-alert--danger' : ''}`;
      const copy = document.createElement('div'); copy.append(item('strong', title), item('span', detail)); row.appendChild(copy); return row;
    }));
  }

  async function load(detail) {
    const token = ++requestToken;
    const state = detail || window.TmallDateRange?.getState() || {};
    const monthlyTrend = normalizeMonthlyTrend(await DemoApi.request('/api/trend?dim=monthly'));
    if (token !== requestToken) return;
    const period = resolveMonthlyPeriod(state, monthlyTrend);
    const prev = previousMonth(period);
    const comparePeriod = state.compareMode === 'year_over_year' ? previousMonth(period, 12) : prev;
    activePeriod = period;
    text($('[data-overview-period]'), state.startDate ? `${state.startDate} ~ ${state.endDate} · 月度口径 ${period}` : `月度口径 ${period}`);
    text($('[data-overview-month]'), `${period} / 上期 ${prev}`);
    const range = queryRange(state);
    const overviewParams = new URLSearchParams({ start: state.startDate, end: state.endDate });
    const requests = [
      DemoApi.domainRequest('/api/overview?' + overviewParams.toString()),
      Promise.resolve(monthlyTrend),
      DemoApi.request(`/api/products?dim=monthly&period=${encodeURIComponent(period)}&limit=5&sort=payment_amount&order=desc`),
      DemoApi.request(`/api/target_progress?dim=monthly&period=${encodeURIComponent(period)}`),
      DemoApi.request(`/api/anomalies?dim=monthly&period=${encodeURIComponent(period)}&prev_period=${encodeURIComponent(prev)}`)
        .catch((error) => { console.error(error); return []; }),
      DemoApi.request(`/api/compare?dim=monthly&period_a=${encodeURIComponent(comparePeriod)}&period_b=${encodeURIComponent(period)}`),
    ];
    const [overviewResponse, trend, products, targets, anomalies, comparison] = await Promise.all(requests);
    overviewPayload = overviewResponse;
    let matrix = { data: { rows: [] } };
    try { matrix = await DemoApi.domainRequest('/api/overview/daily-matrix?' + overviewParams.toString()); } catch (error) { setTableStatus($('[data-overview-home-matrix]'), '日度矩阵暂无数据；请导入日度明细后重试', 9, () => guardedLoad(state)); }
    if (token !== requestToken) return;
    const rows = unwrap(trend, 'data');
    renderKpis(overviewResponse.data, comparison, matrix.data); renderContext(overviewResponse.data); renderTrend(rows); renderHomeProducts(products); renderTargets(targets); await loadGoalLayers(state); renderAnomalies(anomalies); renderHomeMatrix(matrix.data || {});
    const report = await DemoApi.request(`/api/report?dim=monthly&period=${encodeURIComponent(period)}`)
      .catch((error) => { console.error(error); return { report: '' }; });
    if (token !== requestToken) return;
    renderHomeReport(report?.report || '');
  }

  function guardedLoad(detail) {
    const expectedToken = requestToken + 1;
    load(detail).catch((error) => showError(error, expectedToken));
  }
  function showError(error, token) {
    if (token && token !== requestToken) return;
    ['payment_amount', 'net_sales', 'refund_rate', 'expense_ratio'].forEach((key) => textAll(`[data-overview-kpi="${key}"]`, '--'));
    ['[data-overview-home-targets]', '[data-overview-home-anomalies]', '[data-overview-home-actions]', '[data-overview-home-report]'].forEach((selector) => setStatus(selector, '数据加载失败', 'error', () => guardedLoad()));
    setTableStatus($('[data-overview-home-matrix]'), '数据加载失败', 9, () => guardedLoad());
    DemoApi.renderDataState($('[data-overview-context]'), 'calculation-failed', { message: error.message });
    console.error(error);
  }
  async function removeEvent(id) { await DemoApi.domainRequest(`/api/overview/events/${encodeURIComponent(id)}`, { method: 'DELETE', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ operator: '店长', reason: '移除经营事件' }) }); guardedLoad(); }
  async function submitEvent(form) {
    const data = new FormData(form);
    const submit = $('[data-overview-event-submit]');
    const status = $('[data-overview-event-status]');
    submit.disabled = true;
    text(status, '正在保存事件');
    try {
      await DemoApi.domainRequest('/api/overview/events', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ event_date: data.get('event_date'), title: String(data.get('title') || '').trim(), description: String(data.get('description') || '').trim(), color: data.get('color'), chart_type: 'sales', operator: '店长', reason: '记录经营事件' }) });
      $('[data-overview-event-dialog]').close(); form.reset(); window.DemoShell?.showToast?.('图表事件已保存'); guardedLoad();
    } catch (error) {
      text(status, error.message || '保存失败，请稍后重试');
    } finally { submit.disabled = false; }
  }
  const dialog = $('[data-overview-event-dialog]');
  function hideDialog() { dialog.hidden = true; $('[data-overview-event-status]').textContent = ''; dialogReturnFocus?.focus?.(); dialogReturnFocus = null; }
  function showDialog(event) {
    dialogReturnFocus = event?.currentTarget || document.activeElement;
    dialog.hidden = false;
    $('#overview-event-date').value = formatLocalDate();
    $('[data-overview-event-status]').textContent = '';
    dialog.showModal();
    $('#overview-event-title-input')?.focus({ preventScroll: true });
  }
  $('[data-overview-event-open]')?.addEventListener('click', showDialog);
  dialog?.addEventListener('close', hideDialog);
  dialog?.addEventListener('cancel', () => window.setTimeout(hideDialog, 0));
  document.querySelectorAll('[data-overview-event-close]').forEach((button) => button.addEventListener('click', () => dialog.close()));
  $('[data-overview-event-form]')?.addEventListener('submit', (event) => { event.preventDefault(); if (!event.currentTarget.reportValidity()) return; submitEvent(event.currentTarget); });
  const matrixColumnsDialog = $('[data-overview-matrix-columns-dialog]');
  function updateMatrixColumnsStatus(selected = matrixColumnSelector?.getSelected() || matrixVisibleColumns) {
    const normalized = normalizeMatrixColumns(selected);
    $('[data-overview-matrix-columns-status]').textContent = `当前展示 ${normalized.length} 个字段；日期固定保留为首列`;
    $('[data-overview-matrix-columns-apply]').disabled = normalized.length < 2;
  }
  function renderMatrixColumnSelector(selected = matrixVisibleColumns) {
    const config = { groups: [{ label: '日度经营指标', fields: matrixColumns }], selected: normalizeMatrixColumns(selected) };
    if (!matrixColumnSelector) {
      matrixColumnSelector = DemoFieldSelector.create({
        root: $('[data-overview-matrix-field-selector]'),
        ...config,
        className: 'overview-matrix-field-selection',
        availableTitleId: 'overviewMatrixAvailableFieldsTitle',
        previewTitleId: 'overviewMatrixPreviewFieldsTitle',
        optionDataAttribute: 'data-overview-matrix-field-key',
        previewDataAttribute: 'data-overview-matrix-preview-key',
        onChange: updateMatrixColumnsStatus,
      });
    } else matrixColumnSelector.setConfig(config);
    updateMatrixColumnsStatus(config.selected);
  }
  function closeMatrixColumnsDialog() {
    if (matrixColumnsDialog?.open) matrixColumnsDialog.close();
    if (matrixColumnsDialog) matrixColumnsDialog.hidden = true;
    matrixColumnsReturnFocus?.focus?.();
    matrixColumnsReturnFocus = null;
  }
  $('[data-overview-matrix-columns-open]')?.addEventListener('click', (event) => {
    matrixColumnsReturnFocus = event.currentTarget;
    renderMatrixColumnSelector();
    matrixColumnsDialog.hidden = false;
    matrixColumnsDialog.showModal();
  });
  document.querySelectorAll('[data-overview-matrix-columns-close]').forEach((button) => button.addEventListener('click', closeMatrixColumnsDialog));
  $('[data-overview-matrix-columns-apply]')?.addEventListener('click', () => {
    matrixVisibleColumns = normalizeMatrixColumns(matrixColumnSelector?.getSelected());
    saveMatrixColumns();
    renderHomeMatrix(latestMatrix);
    closeMatrixColumnsDialog();
    window.DemoShell?.showToast?.(`已应用 ${matrixVisibleColumns.length} 个日度字段`);
  });
  matrixColumnsDialog?.addEventListener('cancel', (event) => { event.preventDefault(); closeMatrixColumnsDialog(); });
  matrixColumnsDialog?.addEventListener('close', () => { matrixColumnsDialog.hidden = true; });
  function updateTrendCopy() {
    const labels = homeTrendModes.map((mode) => trendMetricLabels[mode] || mode);
    const single = labels.length === 1;
    text($('[data-overview-trend-title]'), single ? `${labels[0]} · 趋势` : '指标对比 · 趋势');
    text($('[data-overview-trend-hint]'), single ? `按日查看${labels[0]}变化` : `按日对比${labels.join('、')}（起始值=100）`);
    const triggerLabel = single ? labels[0] : `已选 ${labels.length} 项`;
    text($('[data-overview-trend-selection]'), triggerLabel);
    $('[data-overview-home-trend]')?.setAttribute('aria-label', single ? `${labels[0]}趋势` : '指标对比趋势');
  }
  function selectTrendModes(modes) {
    const next = [...new Set(modes)].filter((mode) => trendMetricLabels[mode]).slice(0, 3);
    homeTrendModes = next.length ? next : ['net_sales'];
    document.querySelectorAll('[data-overview-trend-mode]').forEach((item) => {
      item.checked = homeTrendModes.includes(item.value || item.dataset.overviewTrendMode);
    });
    document.querySelectorAll('[data-overview-kpi-select]').forEach((item) => item.classList.toggle('is-selected', homeTrendModes.length === 1 && item.dataset.overviewKpiSelect === homeTrendModes[0]));
    updateTrendCopy();
    if (latestTrendRows.length) renderTrend(latestTrendRows);
  }
  document.querySelectorAll('[data-overview-trend-mode]').forEach((input) => input.addEventListener('change', () => {
    const mode = input.value || input.dataset.overviewTrendMode;
    const next = homeTrendModes.filter((item) => item !== mode);
    if (input.checked) next.push(mode);
    if (input.checked && next.length > 3) {
      input.checked = false;
      window.DemoShell?.showToast?.('最多同时对比 3 个指标');
      return;
    }
    selectTrendModes(next);
  }));
  const trendTrigger = $('[data-overview-trend-trigger]');
  const trendMenu = $('[data-overview-trend-menu]');
  trendTrigger?.addEventListener('click', () => {
    const open = trendMenu?.hidden;
    if (trendMenu) trendMenu.hidden = !open;
    trendTrigger.setAttribute('aria-expanded', String(Boolean(open)));
  });
  document.addEventListener('click', (event) => {
    if (!trendMenu || trendMenu.hidden || trendMenu.closest('[data-overview-trend-control]')?.contains(event.target)) return;
    trendMenu.hidden = true;
    trendTrigger?.setAttribute('aria-expanded', 'false');
  });
  document.querySelectorAll('[data-overview-kpi-select]').forEach((card) => {
    const activate = () => selectTrendModes([card.dataset.overviewKpiSelect]);
    card.addEventListener('click', activate);
    card.addEventListener('keydown', (event) => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); activate(); } });
  });
  selectTrendModes(homeTrendModes);
  $('[data-overview-matrix-export]')?.addEventListener('click', () => {
    window.dispatchEvent(new CustomEvent('tmall:export', { cancelable: true }));
  });
  window.addEventListener('tmall:export', (event) => {
    event.preventDefault();
    // The overview response is the source of truth for this export. Page-level
    // capability metadata may be cached or describe a different interaction.
    const pageCanExport = DemoApi.can(overviewPayload, 'can_export');
    if (overviewPayload?.capabilities?.can_export === false || (overviewPayload?.capabilities?.can_export == null && !pageCanExport)) {
      window.DemoShell?.showToast?.('当前数据不可导出');
      return;
    }
    const range = window.TmallDateRange?.getState?.() || {};
    const query = new URLSearchParams();
    query.set('start', range.startDate || '');
    query.set('end', range.endDate || '');
    const link = document.createElement('a');
    link.href = `/api/overview/daily-matrix/export?${query}`;
    link.download = '';
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.DemoShell?.showToast?.('正在导出完整日度矩阵');
  });
  window.addEventListener('tmall:date-range-change', (event) => guardedLoad(event.detail));
  window.addEventListener('tmall:refresh', () => guardedLoad());
  if (!window.TmallDateRange) guardedLoad();
  function normalizeMonthlyTrend(payload) { return unwrap(payload, 'data'); }
})();

