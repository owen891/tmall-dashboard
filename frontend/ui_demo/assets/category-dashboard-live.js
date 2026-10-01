(function () {
  const $ = (id) => document.getElementById(id);
  const labels = { net_sales: '净销售额', payment_amount: '支付金额', payment_qty: '支付件数', visitors: '访客数', payment_conversion_rate: '支付转化率', average_order_value: '客单价', ad_spend: '推广花费', operating_profit: '经营利润', profit_rate: '利润率' };
  const money = (v) => v == null ? '--' : `¥${Number(v).toLocaleString('zh-CN', { maximumFractionDigits: 0 })}`;
  const number = (v) => v == null ? '--' : Number(v).toLocaleString('zh-CN', { maximumFractionDigits: 0 });
  const percent = (v) => v == null ? '--' : `${(Number(v) * 100).toFixed(2)}%`;
  const format = (v, metric) => metric === 'payment_conversion_rate' || metric === 'profit_rate' ? percent(v) : metric === 'payment_qty' || metric === 'visitors' ? number(v) : money(v);
  const COMPARE_LABELS = { yoy: '同比', previous: '环比', custom: '自定义对比', none: '无对比' };
  const PROFIT_ROWS = [['净销售额', 'net_sales'], ['净货品成本', 'product_cost'], ['销售费用', 'sales_cost'], ['自定义费用', 'custom_cost'], ['发货费用', 'logistics_cost'], ['其他费用', 'other_cost'], ['经营利润', 'operating_profit'], ['经营利润率', 'operating_profit_rate']];
  let mode = 'month';
  let requestId = 0;
  let serverToday = null;
  let trendChart = null;

  function iso(date) { return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`; }
  function addDays(date, days) { const next = new Date(date); next.setDate(next.getDate() + days); return next; }
  function shiftYear(date) { const next = new Date(date); next.setFullYear(next.getFullYear() - 1); return next; }
  function parseIso(value, fallback) { const parsed = value ? new Date(`${value}T00:00:00`) : null; return parsed && !Number.isNaN(parsed.getTime()) ? parsed : fallback; }
  // 必须归零到当天 00:00：否则 `end - start` 会带上时分秒，天数被
  // Math.round 向上取整，环比区间会多算一天（20 天周期算成 21 天）。
  function today() {
    const base = (serverToday && parseIso(serverToday, null)) || new Date();
    return new Date(base.getFullYear(), base.getMonth(), base.getDate());
  }
  function categoryMode() { return document.querySelector('[data-category-mode]')?.value || 'all'; }
  function selectedYears() { return ($('dashboardYears')?.value || '2024,2025,2026').split(',').map(Number); }
  function selectedMatrixMetrics() { const values = [...document.querySelectorAll('input[name="dashboardMatrixMetric"]:checked')].map((item) => item.value); return values.length ? values : ['net_sales']; }
  function compareMode() { return $('dashboardCompareMode')?.value || 'previous'; }

  function basePeriod() {
    const now = today();
    if (mode === 'custom') {
      return { start: parseIso($('dashboardStart').value, addDays(now, -29)), end: parseIso($('dashboardEnd').value, now) };
    }
    if (mode === 'week') {
      const weekday = now.getDay() || 7;
      return { start: addDays(now, 1 - weekday), end: now };
    }
    return { start: new Date(now.getFullYear(), now.getMonth(), 1), end: now };
  }

  function periods() {
    const { start, end } = basePeriod();
    const span = Math.max(1, Math.round((end - start) / 86400000) + 1);
    const choice = compareMode();
    let compareStart = null; let compareEnd = null;
    if (choice === 'yoy') { compareStart = shiftYear(start); compareEnd = shiftYear(end); }
    else if (choice === 'previous') { compareStart = addDays(start, -span); compareEnd = addDays(start, -1); }
    else if (choice === 'custom') {
      compareStart = parseIso($('dashboardCompareStart').value, addDays(start, -span));
      compareEnd = parseIso($('dashboardCompareEnd').value, addDays(start, -1));
      if (compareStart > compareEnd) { const swap = compareStart; compareStart = compareEnd; compareEnd = swap; }
    }
    return { start, end, compareStart, compareEnd, label: `${iso(start)} 至 ${iso(end)}` };
  }

  function setMode(nextMode) {
    mode = nextMode;
    document.querySelectorAll('[data-dashboard-mode]').forEach((button) => button.classList.toggle('is-active', button.dataset.dashboardMode === mode));
    const annual = mode === 'annual';
    document.querySelectorAll('.dashboard-custom-only').forEach((node) => { node.style.display = mode === 'custom' ? 'grid' : 'none'; });
    document.querySelectorAll('.dashboard-annual-only').forEach((node) => { node.style.display = annual ? 'grid' : 'none'; });
    document.querySelectorAll('.dashboard-compare-custom').forEach((node) => { node.style.display = !annual && compareMode() === 'custom' ? 'grid' : 'none'; });
    const compareControl = document.querySelector('.dashboard-compare-control');
    if (compareControl) { compareControl.style.display = annual ? 'none' : 'grid'; }
    document.querySelector('.dashboard-operating-view').style.display = annual ? 'none' : 'grid';
    $('dashboardAnnualView').style.display = annual ? 'block' : 'none';
    const categoryLabel = document.querySelector('[data-category-mode]')?.selectedOptions?.[0]?.textContent || '全部品类';
    const periodLabel = annual ? '年度复盘' : mode === 'week' ? '本周经营' : mode === 'custom' ? '自定义周期' : '本月经营';
    $('dashboardTitle').textContent = `${categoryLabel} · ${periodLabel}`;
    const context = $('categoryDashboardContext');
    if (context) context.textContent = `${categoryLabel} · ${periodLabel}`;
  }

  function basisText(basis) {
    if (basis === 'bi') return 'BI 支付预估';
    if (basis === 'derived') return '公式推导';
    return '不可用';
  }

  function profitBlocked(data) {
    const metric = data.metric;
    const breakdown = data.profit_breakdown || {};
    return (metric === 'operating_profit' || metric === 'profit_rate') && breakdown.operating_profit == null;
  }

  function renderKpis(data) {
    const current = data.current_period || {};
    const change = data.change || {};
    const metric = data.metric || 'net_sales';
    const breakdown = data.profit_breakdown || {};
    const missing = breakdown.missing_fields || [];
    const costLabels = data.cost_labels || {};
    const blocked = profitBlocked(data);
    const compared = COMPARE_LABELS[compareMode()] || '对比';
    const cards = [
      { title: '当前周期', value: blocked ? '不可用' : format(current.value, metric), note: blocked ? '成本项缺失，不展示利润数值' : `${format(change.amount, metric)} 变化` },
      { title: `${compared}变化`, value: (!blocked && data.compare_period) ? percent(change.rate) : '--', note: data.compare_period ? `${data.compare_period.start} 至 ${data.compare_period.end}` : '暂无对比数据' },
      { title: '日均表现', value: blocked ? '不可用' : format(current.daily_average, metric), note: `${current.days || '--'} 天` },
      { title: '利润口径', value: basisText(breakdown.basis), note: missing.length ? `缺少 ${missing.map((key) => costLabels[key] || key).join('、')}` : '成本项完整' }
    ];
    $('categoryDashboardKpis').innerHTML = cards.map((card) => `<div class="dashboard-kpi"><span>${card.title}</span><strong>${card.value}</strong><small>${card.note}</small></div>`).join('');
  }

  function renderInsight(data) {
    const breakdown = data.profit_breakdown || {};
    const costLabels = data.cost_labels || {};
    if (profitBlocked(data)) {
      const missing = (breakdown.missing_fields || []).map((key) => costLabels[key] || key).join('、');
      $('dashboardInsight').textContent = `该区间缺少成本数据（${missing || '未知'}），经营利润无法计算，已停止展示数值。请先补齐成本口径，避免把「净销售额 − 推广花费」误读成利润。`;
      return;
    }
    const rate = data.change?.rate;
    const direction = rate == null ? '暂无足够对比数据' : rate < 0 ? `当前${labels[data.metric] || data.metric}较对比周期下降 ${percent(Math.abs(rate))}` : `当前${labels[data.metric] || data.metric}较对比周期增长 ${percent(rate)}`;
    const down = data.contributors?.down?.slice(0, 2).map((row) => row.title || row.product_id).filter(Boolean).join('、');
    $('dashboardInsight').textContent = down ? `${direction}，主要拖累商品：${down}。` : `${direction}。请结合增长贡献和下滑拖累定位商品动作。`;
  }

  function renderTrend(data) {
    const node = $('categoryDashboardTrend');
    $('dashboardTrendMeta').textContent = `${data.current_period?.start || ''} 至 ${data.current_period?.end || ''} · ${labels[data.metric] || data.metric}`;
    if (!window.echarts || !data.trend?.length) {
      if (trendChart) { trendChart.dispose(); trendChart = null; }
      node.textContent = '暂无趋势数据';
      return;
    }
    if (trendChart) { trendChart.dispose(); }
    trendChart = window.echarts.init(node);
    const series = [{ name: '当前周期', type: 'line', smooth: true, data: data.trend.map((row) => row.value) }];
    if (data.compare_trend?.length) {
      series.push({ name: '对比周期', type: 'line', smooth: true, lineStyle: { type: 'dashed' }, data: data.compare_trend.map((row) => row.value) });
    }
    trendChart.setOption({
      tooltip: { trigger: 'axis' },
      legend: { show: series.length > 1, right: 8, top: 0 },
      grid: { left: 52, right: 18, top: series.length > 1 ? 36 : 20, bottom: 35 },
      xAxis: { type: 'category', data: data.trend.map((row) => row.period) },
      yAxis: { type: 'value' },
      series
    });
  }

  function renderProfit(data) {
    const breakdown = data.profit_breakdown || {};
    const costLabels = data.cost_labels || {};
    const missing = breakdown.missing_fields || [];
    $('dashboardProfitBadge').textContent = basisText(breakdown.basis);
    const rows = PROFIT_ROWS.map(([name, key]) => {
      const value = breakdown[key];
      const text = key === 'operating_profit_rate' ? percent(value) : money(value);
      const flagged = missing.includes(key) && value == null;
      return `<div><span>${name}</span><strong>${flagged ? '未接入' : text}</strong></div>`;
    }).join('');
    const notes = [];
    notes.push(breakdown.basis === 'bi'
      ? '口径：BI「利润(支付预估)」，扣减项与 BI 一致。'
      : breakdown.basis === 'derived'
        ? '口径：净销售额 − 净货品成本 − 销售费用 − 自定义费用 − 发货费用 − 其他费用。'
        : '成本项缺失，经营利润不可计算，已停止展示数值。');
    if (missing.length) { notes.push(`缺少成本项：${missing.map((key) => costLabels[key] || key).join('、')}`); }
    $('categoryDashboardProfit').innerHTML = rows + `<p class="dashboard-profit-note">${notes.join(' ')}</p>`;
  }

  function renderProducts(node, rows, metric) {
    $(node).innerHTML = rows?.length ? `<table><thead><tr><th>商品</th><th class="num">当前</th><th class="num">变化</th></tr></thead><tbody>${rows.map((row) => `<tr><td>${row.title || row.product_id || '--'}</td><td class="num">${format(row.current_value, metric)}</td><td class="num">${format(row.change, metric)}</td></tr>`).join('')}</tbody></table>` : '<span>暂无数据</span>';
  }

  function renderAnnual(data) {
    const metrics = data.metrics || selectedMatrixMetrics();
    $('categoryDashboardYearReview').innerHTML = metrics.map((metric) => {
      const item = data.series?.[metric];
      if (!item) return '';
      const years = data.years || [];
      return `<section class="dashboard-review-block"><header><strong>${labels[metric] || metric}</strong><span>${data.focus_year}年重点复盘</span></header><div class="dashboard-table"><table><thead><tr><th>月份</th>${years.map((year) => `<th class="num">${year}</th>`).join('')}<th class="num">同比</th></tr></thead><tbody>${item.matrix.map((row) => `<tr><th>${row.label}</th>${years.map((year) => `<td class="num">${format(row.values?.[String(year)], metric)}</td>`).join('')}<td class="num">${percent(row.yoy?.rate)}</td></tr>`).join('')}</tbody><tfoot><tr><th>年度累计</th>${years.map((year) => `<td class="num">${format(item.annual?.[String(year)], metric)}</td>`).join('')}<td class="num">--</td></tr></tfoot></table></div></section>`;
    }).join('');
  }

  async function load() {
    const token = ++requestId;
    const state = $('categoryDashboardState');
    state.className = 'dashboard-state';
    state.textContent = '加载中…';
    try {
      if (mode === 'annual') {
        const params = new URLSearchParams({ category_mode: categoryMode(), years: selectedYears().join(','), metric: 'net_sales', metrics: selectedMatrixMetrics().join(',') });
        const payload = await DemoApi.domainRequest(`/api/category-analysis/matrix?${params}`);
        if (token !== requestId) return;
        const annual = payload.data || {};
        if (annual.data_quality?.server_today) serverToday = annual.data_quality.server_today;
        renderAnnual(annual);
        state.textContent = `年度复盘数据已更新 · 数据截至 ${annual.data_quality?.coverage_end || '未知'}`;
        return;
      }
      const p = periods();
      const choice = compareMode();
      $('dashboardPeriodLabel').textContent = (p.compareStart && p.compareEnd)
        ? `${p.label} · ${COMPARE_LABELS[choice]} ${iso(p.compareStart)} 至 ${iso(p.compareEnd)}`
        : `${p.label} · 无对比`;
      const params = new URLSearchParams({ category_mode: categoryMode(), grain: mode === 'week' ? 'week' : 'day', metric: $('dashboardMetric').value, start: iso(p.start), end: iso(p.end), compare_mode: choice, top_n: '10' });
      if (p.compareStart && p.compareEnd) { params.set('compare_start', iso(p.compareStart)); params.set('compare_end', iso(p.compareEnd)); }
      const payload = await DemoApi.domainRequest(`/api/category-analysis/compare?${params}`);
      if (token !== requestId) return;
      const data = payload.data || {};
      if (data.data_quality?.server_today) serverToday = data.data_quality.server_today;
      renderKpis(data); renderInsight(data); renderTrend(data); renderProfit(data);
      renderProducts('categoryDashboardUp', data.contributors?.up, data.metric);
      renderProducts('categoryDashboardDown', data.contributors?.down, data.metric);
      const coverage = data.data_quality?.coverage_end;
      const suffix = data.data_quality?.availability === 'partial' ? ' · 部分口径' : '';
      state.textContent = coverage ? `数据截至 ${coverage}${suffix}` : '该区间没有数据';
    } catch (error) {
      if (token !== requestId) return;
      state.className = 'dashboard-state is-error';
      state.textContent = `加载失败：${error.message}`;
    }
  }

  function init() {
    const now = today();
    $('dashboardStart').value = iso(addDays(now, -29));
    $('dashboardEnd').value = iso(now);
    $('dashboardCompareStart').value = iso(addDays(now, -59));
    $('dashboardCompareEnd').value = iso(addDays(now, -30));
    document.querySelectorAll('[data-dashboard-mode]').forEach((button) => button.addEventListener('click', () => { setMode(button.dataset.dashboardMode); load(); }));
    ['dashboardMetric', 'dashboardStart', 'dashboardEnd', 'dashboardYears', 'dashboardCompareStart', 'dashboardCompareEnd'].forEach((id) => $(id)?.addEventListener('change', load));
    $('dashboardCompareMode')?.addEventListener('change', () => { setMode(mode); load(); });
    document.querySelectorAll('input[name="dashboardMatrixMetric"]').forEach((input) => input.addEventListener('change', load));
    document.querySelector('[data-category-mode]')?.addEventListener('change', load);
    $('categoryDashboardRefresh').addEventListener('click', load);
    window.addEventListener('resize', () => { if (trendChart) { trendChart.resize(); } });
    setMode('month');
    load();
  }
  document.addEventListener('DOMContentLoaded', init);
})();
