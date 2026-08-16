(function () {
  const $ = (selector) => document.querySelector(selector);
  const money = (value) => `¥${Number(value || 0).toLocaleString('zh-CN', { maximumFractionDigits: 0 })}`;
  const number = (value) => Number(value || 0).toLocaleString('zh-CN');
  const percent = (value) => `${(Number(value || 0) * 100).toFixed(1)}%`;
  const metricDefs = [
    ['支付金额', 'gmv', money, true],
    ['净销售额', 'net_sales', money, true],
    ['商品访客数', 'visitors', number, true],
    ['客单价', 'aov', money, true],
    ['推广花费', 'ad_spend', money, false],
    ['推广 ROI', 'roi', (value) => Number(value || 0).toFixed(2), true],
    ['商品支付转化率', 'conversion', percent, true],
    ['退款率', 'refund_rate', percent, false]
  ];
  const trendLabels = { gmv: 'GMV', visitors: '访客', net_sales: '净销售' };
  const currentKey = 'period_b';
  const baselineKey = 'period_a';
  let periods = [];
  let trendRows = [];
  let activeMetric = 'gmv';
  let trendChart = null;
  let initToken = 0;
  let runToken = 0;
  let pendingDateState = null;

  const text = (node, value) => { if (node) node.textContent = value == null || value === '' ? '--' : String(value); };
  const cell = (value, className) => { const node = document.createElement('td'); if (className) node.className = className; text(node, value); return node; };
  const option = (value) => { const node = document.createElement('option'); node.value = value; text(node, value); return node; };

  function normalizeRows(payload) {
    if (Array.isArray(payload)) return payload;
    if (Array.isArray(payload?.data)) return payload.data;
    if (Array.isArray(payload?.value)) return payload.value;
    return [];
  }
  function previousMonth(period, count = 1) {
    const [year, month] = String(period || '').split('-').map(Number);
    if (!year || !month) return '';
    const date = new Date(year, month - 1 - count, 1);
    return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`;
  }
  function setPeriodFromDate(detail) {
    if (!detail?.endDate) return false;
    if (!periods.length) {
      pendingDateState = detail;
      return false;
    }
    const target = detail.endDate.slice(0, 7);
    if (periods.includes(target)) $('[data-compare-a]').value = target;
    const fallback = detail.compareMode === 'year_over_year' ? previousMonth(target, 12) : previousMonth(target, 1);
    if (periods.includes(fallback)) $('[data-compare-b]').value = fallback;
    pendingDateState = null;
    return true;
  }
  function deltaText(kpi) {
    return kpi?.change_pct == null ? '--' : `${kpi.change_pct > 0 ? '+' : ''}${kpi.change_pct}%`;
  }
  function judgement(key, change, positiveGood) {
    if (change == null) return '缺少对比基数';
    if (Math.abs(change) < 0.5) return '基本持平';
    const up = change > 0;
    if ((up && positiveGood) || (!up && !positiveGood)) return `${trendLabels[key] || '指标'}改善`;
    return `${trendLabels[key] || '指标'}承压`;
  }
  function updateKpi(k) {
    [['gmv', money], ['visitors', number], ['refund_rate', percent], ['aov', money]].forEach(([key, format]) => {
      text($(`[data-compare-kpi="${key}"]`), format(k[key]?.[currentKey]));
      text($(`[data-compare-delta="${key}"]`), `对比期 ${format(k[key]?.[baselineKey])} · ${deltaText(k[key])}`);
    });
  }
  function renderTable(k) {
    const body = $('[data-compare-body]');
    body.replaceChildren(...metricDefs.map(([label, key, format, positiveGood]) => {
      const row = document.createElement('tr');
      const change = k[key]?.change_pct;
      row.append(cell(label), cell(format(k[key]?.[currentKey]), 'num'), cell(format(k[key]?.[baselineKey]), 'num'), cell(deltaText(k[key]), 'num'), cell(judgement(key, change, positiveGood)));
      return row;
    }));
  }
  function renderSummary(k) {
    const usable = metricDefs
      .map(([label, key, format, positiveGood]) => ({ label, key, format, positiveGood, data: k[key] }))
      .filter((entry) => entry.data?.change_pct != null)
      .sort((a, b) => Math.abs(b.data.change_pct) - Math.abs(a.data.change_pct))
      .slice(0, 4);
    const items = usable.length ? usable : metricDefs.slice(0, 2).map(([label, key, format, positiveGood]) => ({ label, key, format, positiveGood, data: k[key] || {} }));
    $('[data-compare-summary]').replaceChildren(...items.map((entry) => {
      const row = document.createElement('div');
      row.className = 'status-list__item';
      const label = document.createElement('span'); label.className = 'status-list__label';
      text(label, `${entry.label}：${entry.format(entry.data?.[currentKey])}，较对比期 ${deltaText(entry.data)}`);
      const value = document.createElement('span'); value.className = 'status-list__value';
      text(value, judgement(entry.key, entry.data?.change_pct, entry.positiveGood));
      row.append(label, value);
      return row;
    }));
  }
  function trendWindow(period) {
    const index = trendRows.findIndex((row) => row.period === period);
    if (index < 0) return [];
    return trendRows.slice(Math.max(0, index - 2), Math.min(trendRows.length, index + 3));
  }
  function renderTrend(periodA, periodB) {
    if (!window.DemoCharts || !$('#compareTrend')) return;
    const rowsA = trendWindow(periodA);
    const rowsB = trendWindow(periodB);
    const length = Math.max(rowsA.length, rowsB.length);
    const labels = Array.from({ length }, (_, index) => `T${index - Math.floor(length / 2)}`);
    const first = Array.from({ length }, (_, index) => Number(rowsA[index]?.[activeMetric] || 0));
    const second = Array.from({ length }, (_, index) => Number(rowsB[index]?.[activeMetric] || 0));
    if (trendChart?.destroy) trendChart.destroy();
    trendChart = DemoCharts.linePair('compareTrend', labels, first, second, `${periodA} ${trendLabels[activeMetric]}`, `${periodB} ${trendLabels[activeMetric]}`);
  }
  async function run() {
    const token = ++runToken;
    const a = $('[data-compare-a]').value;
    const b = $('[data-compare-b]').value;
    if (!a || !b) return;
    text($('[data-compare-periods]'), `${a} vs ${b}`);
    const apiPeriods = compareApiPeriods(a, b);
    const data = await DemoApi.request(`/api/compare?dim=monthly&period_a=${encodeURIComponent(apiPeriods.period_a)}&period_b=${encodeURIComponent(apiPeriods.period_b)}`);
    if (token !== runToken) return;
    const k = data.kpi_compare || {};
    updateKpi(k);
    renderTable(k);
    renderSummary(k);
    renderTrend(a, b);
  }
  function compareApiPeriods(currentPeriod, comparePeriod) {
    return { period_a: comparePeriod, period_b: currentPeriod };
  }
  function clearCompareState(message) {
    text($('[data-compare-periods]'), '数据加载失败');
    ['gmv', 'visitors', 'refund_rate', 'aov'].forEach((key) => {
      text($(`[data-compare-kpi="${key}"]`), '--');
      text($(`[data-compare-delta="${key}"]`), '--');
    });
    if (trendChart?.destroy) trendChart.destroy();
    trendChart = null;
    const body = $('[data-compare-body]');
    const row = document.createElement('tr');
    const td = cell(message);
    td.colSpan = 5;
    row.appendChild(td);
    body.replaceChildren(row);
    const summary = document.createElement('div');
    summary.className = 'empty-state';
    summary.appendChild(document.createTextNode(message));
    $('[data-compare-summary]').replaceChildren(summary);
  }
  function fail(error, token) {
    if (token && token !== runToken) return;
    clearCompareState('数据加载失败');
    console.error(error);
  }
  function guardedRun() {
    if (!periods.length) return;
    const expectedToken = runToken + 1;
    run().catch((error) => fail(error, expectedToken));
  }
  async function init() {
    const token = ++initToken;
    const payload = await DemoApi.request('/api/trend?dim=monthly');
    if (token !== initToken) return;
    trendRows = normalizeRows(payload).sort((a, b) => String(a.period).localeCompare(String(b.period)));
    periods = trendRows.map((row) => row.period).reverse();
    $('[data-compare-a]').replaceChildren(...periods.map(option));
    $('[data-compare-b]').replaceChildren(...periods.map(option));
    if (periods[1]) $('[data-compare-b]').value = periods[1];
    setPeriodFromDate(pendingDateState || window.TmallDateRange?.getState());
    await run();
  }
  function guardedInit() {
    init().catch((error) => { clearCompareState('数据加载失败'); console.error(error); });
  }

  $('[data-compare-run]')?.addEventListener('click', guardedRun);
  document.querySelectorAll('[data-compare-metric]').forEach((button) => {
    button.addEventListener('click', () => {
      activeMetric = button.dataset.compareMetric;
      document.querySelectorAll('[data-compare-metric]').forEach((node) => node.setAttribute('aria-pressed', String(node === button)));
      renderTrend($('[data-compare-a]').value, $('[data-compare-b]').value);
    });
  });
  window.addEventListener('tmall:date-range-change', (event) => { if (setPeriodFromDate(event.detail)) guardedRun(); });
  window.addEventListener('tmall:refresh', guardedRun);
  guardedInit();
})();
