(function () {
  const $ = (selector) => document.querySelector(selector);
  const $$ = (selector) => [...document.querySelectorAll(selector)];

  const metricLabels = {
    payment_amount: '支付金额', net_sales: '净销售额', product_visitors: '商品访客数',
    payment_conversion_rate: '支付转化率', ad_spend: '推广花费', expense_ratio: '费比',
    average_order_value: '客单价', payment_qty: '支付买家数',
  };

  const dimensionLabels = {
    date: '按日期', week: '按周', month: '按月', product: '按商品', category: '按类目',
  };

  const chartTypeLabels = { line: '折线图', bar: '柱状图', pie: '饼图', scatter: '散点图' };

  const templates = {
    'sales-trend': { metric: 'payment_amount', dimension: 'date', chartType: 'line', days: 30 },
    'traffic-source': { metric: 'product_visitors', dimension: 'date', chartType: 'bar', days: 30 },
    'conversion-funnel': { metric: 'payment_conversion_rate', dimension: 'date', chartType: 'line', days: 30 },
    'product-ranking': { metric: 'payment_amount', dimension: 'product', chartType: 'bar', days: 30 },
    'ad-performance': { metric: 'ad_spend', dimension: 'date', chartType: 'line', days: 30 },
    'category-period': { metric: 'payment_amount', grain: 'month', compareMode: 'yoy', days: 30 },
  };

  let currentConfig = null;
  let chartInstances = [];

  function syncDateInputs(range) {
    if (!range?.startDate || !range?.endDate) return;
    $('#startDate').value = range.startDate;
    $('#endDate').value = range.endDate;
    $('#startDate').max = range.endDate;
    $('#endDate').min = range.startDate;
  }

  function init() {
    // 日期由共享时间范围控制，避免分析页与顶部选择器各自维护一份状态。
    const today = new Date();
    const thirtyDaysAgo = new Date(today.getTime() - 30 * 24 * 60 * 60 * 1000);
    $('#endDate').value = today.toISOString().slice(0, 10);
    $('#startDate').value = thirtyDaysAgo.toISOString().slice(0, 10);
    syncDateInputs(window.TmallDateRange?.getState?.());
    window.TmallDateRange?.subscribe?.((range) => {
      syncDateInputs(range);
      if (currentConfig) runAnalysis();
    });
    ['startDate', 'endDate'].forEach((id) => {
      $(`#${id}`).addEventListener('change', () => {
        const start = $('#startDate').value;
        const end = $('#endDate').value;
        if (start && end) window.TmallDateRange?.setRange?.(start, end, 'custom');
      });
    });

    // 绑定模板切换
    $$('.analysis-template').forEach((tpl) => {
      tpl.addEventListener('click', () => {
        $$('.analysis-template').forEach((t) => t.classList.remove('analysis-template--active'));
        tpl.classList.add('analysis-template--active');
        applyTemplate(tpl.dataset.template);
      });
    });

    // 绑定生成按钮
    $('#runAnalysisBtn').addEventListener('click', runAnalysis);
    $('#saveAnalysisBtn').addEventListener('click', saveAnalysis);
    ['categorySelect', 'categoryGrainSelect', 'categoryMetricSelect', 'compareModeSelect', 'categoryStartDate', 'categoryEndDate', 'compareStartDate', 'compareEndDate'].forEach((id) => {
      $(`#${id}`)?.addEventListener('change', () => {
        if ($('#categoryAnalysisConfig') && !$('#categoryAnalysisConfig').hidden) {
          if (id === 'categoryStartDate' || id === 'categoryEndDate') {
            window.TmallDateRange?.setRange?.($('#categoryStartDate').value, $('#categoryEndDate').value, 'custom');
          }
          syncCategoryCompareDates();
          if (id !== 'compareStartDate' && id !== 'compareEndDate') runCategoryAnalysis();
        }
      });
    });
    loadCategoryModes();

    // 加载已保存的分析
    loadSavedAnalysis();

    // 默认应用第一个模板
    applyTemplate('sales-trend');
  }

  function applyTemplate(name) {
    const categoryPanel = $('#categoryAnalysisConfig');
    const legacyConfig = document.querySelector('.analysis-config');
    if (categoryPanel) categoryPanel.hidden = name !== 'category-period';
    if (legacyConfig) legacyConfig.hidden = name === 'category-period';
    if (name === 'category-period') {
      const tpl = templates[name];
      $('#categoryMetricSelect').value = tpl.metric;
      $('#categoryGrainSelect').value = tpl.grain;
      $('#compareModeSelect').value = tpl.compareMode;
      $('#categoryStartDate').value = $('#startDate').value;
      $('#categoryEndDate').value = $('#endDate').value;
      syncCategoryCompareDates();
      return;
    }
    const tpl = templates[name];
    if (!tpl) return;
    $('#metricSelect').value = tpl.metric;
    $('#dimensionSelect').value = tpl.dimension;
    $('#chartTypeSelect').value = tpl.chartType;
    const sharedRange = window.TmallDateRange?.getState?.();
    if (sharedRange?.startDate && sharedRange?.endDate) syncDateInputs(sharedRange);
    else {
      const today = new Date();
      const start = new Date(today.getTime() - tpl.days * 24 * 60 * 60 * 1000);
      syncDateInputs({ startDate: start.toISOString().slice(0, 10), endDate: today.toISOString().slice(0, 10) });
    }
  }

  async function runAnalysis() {
    if (document.querySelector('.analysis-template--active')?.dataset.template === 'category-period') {
      return runCategoryAnalysis();
    }
    const config = {
      metric: $('#metricSelect').value,
      dimension: $('#dimensionSelect').value,
      chartType: $('#chartTypeSelect').value,
      startDate: $('#startDate').value,
      endDate: $('#endDate').value,
      topN: parseInt($('#topNSelect').value),
    };
    currentConfig = config;

    const chartsContainer = $('#analysisCharts');
    DemoApi.renderDataState(chartsContainer, 'loading', { message: '正在计算经营分析…' });

    try {
      const data = await fetchAnalysisData(config);
      renderCharts(config, data);
    } catch (error) {
      DemoApi.renderDataState(chartsContainer, 'calculation-failed', { message: error.message, retry: () => runAnalysis() });
    }
  }

  function dateShift(date, years, days) {
    const value = new Date(`${date}T00:00:00`);
    value.setDate(value.getDate() + (days || 0));
    value.setFullYear(value.getFullYear() + (years || 0));
    return value.toISOString().slice(0, 10);
  }

  function syncCategoryCompareDates() {
    const mode = $('#compareModeSelect')?.value;
    const start = $('#categoryStartDate')?.value;
    const end = $('#categoryEndDate')?.value;
    const fields = $('#categoryCompareDates');
    if (!fields || !start || !end) return;
    fields.hidden = mode !== 'custom';
    if (mode === 'yoy') {
      $('#compareStartDate').value = dateShift(start, -1);
      $('#compareEndDate').value = dateShift(end, -1);
    } else if (mode === 'previous') {
      const span = Math.round((new Date(`${end}T00:00:00`) - new Date(`${start}T00:00:00`)) / 86400000) + 1;
      $('#compareEndDate').value = dateShift(start, 0, -1);
      $('#compareStartDate').value = dateShift(start, 0, -span);
    }
  }

  function categoryConfig() {
    const mode = $('#compareModeSelect').value;
    syncCategoryCompareDates();
    return {
      categoryMode: $('#categorySelect').value,
      grain: $('#categoryGrainSelect').value,
      metric: $('#categoryMetricSelect').value,
      compareMode: mode,
      startDate: $('#categoryStartDate').value,
      endDate: $('#categoryEndDate').value,
      compareStartDate: mode === 'none' ? '' : $('#compareStartDate').value,
      compareEndDate: mode === 'none' ? '' : $('#compareEndDate').value,
      topN: parseInt($('#topNSelect').value, 10),
    };
  }

  async function loadCategoryModes() {
    try {
      const payload = await DemoApi.domainRequest('/api/settings');
      const modes = payload?.data?.category_modes || payload?.data?.configured_category_modes || [];
      const select = $('#categorySelect');
      if (!select || !modes.length) return;
      const selected = select.value;
      select.innerHTML = modes.filter((item) => item && item.enabled !== false)
        .map((item) => `<option value="${String(item.value)}">${String(item.label)}</option>`).join('');
      if ([...select.options].some((option) => option.value === selected)) select.value = selected;
    } catch (_error) {
      // Keep built-in options available when settings are temporarily unavailable.
    }
  }

  async function runCategoryAnalysis() {
    const config = categoryConfig();
    currentConfig = { template: 'category-period', ...config };
    const container = $('#analysisCharts');
    DemoApi.renderDataState(container, 'loading', { message: '正在计算品类对比…' });
    try {
      const payload = await fetchCategoryAnalysis(config);
      renderCategoryAnalysis(config, payload?.data || payload || {});
    } catch (error) {
      DemoApi.renderDataState(container, 'calculation-failed', { message: error.message, retry: () => runCategoryAnalysis() });
    }
  }

  async function fetchCategoryAnalysis(config) {
    const params = new URLSearchParams({ category_mode: config.categoryMode, grain: config.grain, start: config.startDate, end: config.endDate, compare_mode: config.compareMode, metric: config.metric, top_n: config.topN });
    if (config.compareStartDate) params.set('compare_start', config.compareStartDate);
    if (config.compareEndDate) params.set('compare_end', config.compareEndDate);
    return DemoApi.domainRequest(`/api/category-analysis/compare?${params}`);
  }

  function renderCategoryAnalysis(config, data) {
    const container = $('#analysisCharts');
    container.innerHTML = '';
    const current = data.current_period || {};
    const compare = data.compare_period || {};
    const change = data.change || {};
    const quality = data.data_quality || {};
    const label = metricLabels[config.metric] || config.metric;
    const cards = document.createElement('div');
    cards.className = 'category-analysis-kpis';
    cards.innerHTML = [
      ['当前周期', current.value, current.daily_average],
      ['对比周期', compare.value, compare.daily_average],
      ['变化额', change.amount, null],
      ['增长率', change.rate, null],
    ].map(([title, value, daily]) => `<div class="category-analysis-kpi"><span>${title}</span><strong>${title === '增长率' ? formatValue(value, 'payment_conversion_rate') : formatValue(value, config.metric)}</strong>${daily != null ? `<small>日均 ${formatValue(daily, config.metric)}</small>` : ''}</div>`).join('');
    container.appendChild(cards);
    const trend = data.trend || [];
    if (trend.length) {
      const categories = trend.map((item) => item.period || item.date || item.label || '');
      const values = trend.map((item) => item.value ?? item[config.metric] ?? 0);
      container.appendChild(createChartCard(`${label}趋势`, 'line', categories, [values], [label]));
    }
    const breakdown = data.profit_breakdown;
    if (breakdown) {
      const card = document.createElement('div'); card.className = 'analysis-chart category-analysis-breakdown';
      // 与品类经营看板保持同一口径：利润取 BI「利润(支付预估)」，
      // 扣减项为 销售费用/自定义费用/净货品成本/发货费用/其他费用。
      const basisLabel = breakdown.basis === 'bi' ? 'BI 利润(支付预估)' : breakdown.basis === 'derived' ? '公式推导' : '成本口径不可用';
      const breakdownRows = [['净销售额', 'net_sales'], ['净货品成本', 'product_cost'], ['销售费用', 'sales_cost'], ['自定义费用', 'custom_cost'], ['发货费用', 'logistics_cost'], ['其他费用', 'other_cost'], ['经营利润', 'operating_profit']];
      card.innerHTML = `<div class="analysis-chart__header"><h3 class="analysis-chart__title">利润拆解</h3><span class="ui-badge ui-badge--secondary">${basisLabel}</span></div><div class="category-analysis-breakdown__list">${breakdownRows.map(([name, key]) => `<div><span>${name}</span><strong>${formatValue(breakdown[key], 'payment_amount')}</strong></div>`).join('')}</div>`;
      container.appendChild(card);
    }
    const qualityCard = document.createElement('div'); qualityCard.className = 'analysis-chart category-analysis-quality';
    qualityCard.innerHTML = `<div class="analysis-chart__header"><h3 class="analysis-chart__title">数据完整度</h3></div><p>${quality.is_partial_period ? '当前周期为部分周期。' : '当前周期完整。'} ${quality.missing_fields?.length ? `缺少字段：${quality.missing_fields.join('、')}` : '未发现缺失字段。'}</p><small>数据来源：${(quality.source_tables || []).join('、') || '接口聚合结果'}</small>`;
    container.appendChild(qualityCard);
    const contributors = data.contributors || {};
    [['增长商品', contributors.up], ['下滑商品', contributors.down]].forEach(([title, rows]) => {
      if (!rows?.length) return;
      const card = document.createElement('div'); card.className = 'analysis-chart';
      card.innerHTML = `<div class="analysis-chart__header"><h3 class="analysis-chart__title">${title}</h3></div><div class="ui-table-wrap"><table class="ui-data-table"><thead><tr><th>商品</th><th class="num">贡献金额</th><th class="num">贡献率</th></tr></thead><tbody>${rows.slice(0, config.topN).map((row) => `<tr><td>${row.title || row.name || row.product_name || '--'}</td><td class="num">${formatValue(row.amount ?? row.value, 'payment_amount')}</td><td class="num">${formatValue(row.rate, 'payment_conversion_rate')}</td></tr>`).join('')}</tbody></table></div>`;
      container.appendChild(card);
    });
  }

  async function fetchAnalysisData(config) {
    const params = new URLSearchParams({
      start: config.startDate,
      end: config.endDate,
      metric: config.metric,
      dimension: config.dimension,
      limit: config.topN,
    });

    // 优先使用自定义分析接口，如果没有则用趋势接口
    try {
      const resp = await DemoApi.domainRequest(`/api/analysis/custom?${params}`);
      if (resp && resp.data) return resp.data;
    } catch (e) {
      // 自定义接口不存在，使用趋势接口
    }

    // 回退到趋势接口
    const trendResp = await DemoApi.domainRequest(`/api/trend?${params}`);
    return trendResp?.data || trendResp || { series: [], categories: [] };
  }

  function renderCharts(config, data) {
    const chartsContainer = $('#analysisCharts');
    chartsContainer.innerHTML = '';

    // 销毁旧图表
    chartInstances.forEach((c) => c.dispose());
    chartInstances = [];

    const categories = data.categories || data.dates || [];
    const series = data.series || data.values || [];

    if (!categories.length && !series.length) {
      DemoApi.renderDataState(chartsContainer, 'no-data', { message: '请调整时间范围或指标' });
      return;
    }

    // 主图表
    const mainChart = createChartCard(
      `${metricLabels[config.metric]} · ${dimensionLabels[config.dimension]}`,
      config.chartType,
      categories,
      Array.isArray(series[0]) ? series : [series],
      [metricLabels[config.metric]]
    );
    chartsContainer.appendChild(mainChart);

    // 如果是按商品维度，额外显示 TOP N 表格
    if (config.dimension === 'product' && data.products) {
      const tableCard = document.createElement('div');
      tableCard.className = 'analysis-chart';
      tableCard.style.gridColumn = '1 / -1';
      tableCard.innerHTML = `
        <div class="analysis-chart__header"><h3 class="analysis-chart__title">商品明细 TOP ${config.topN}</h3></div>
        <div class="ui-table-wrap"><table class="ui-data-table">
          <thead><tr><th>排名</th><th>商品</th><th class="num">${metricLabels[config.metric]}</th><th class="num">占比</th></tr></thead>
          <tbody>${data.products.slice(0, config.topN).map((p, i) => `
            <tr><td>${i + 1}</td><td>${p.title || p.name || '--'}</td>
            <td class="num">${formatValue(p[config.metric], config.metric)}</td>
            <td class="num">${p.percent ? p.percent.toFixed(1) + '%' : '--'}</td></tr>
          `).join('')}</tbody>
        </table></div>
      `;
      chartsContainer.appendChild(tableCard);
    }
  }

  function createChartCard(title, chartType, categories, seriesData, seriesNames) {
    const card = document.createElement('div');
    card.className = 'analysis-chart';
    card.innerHTML = `
      <div class="analysis-chart__header">
        <h3 class="analysis-chart__title">${title}</h3>
        <span class="ui-badge ui-badge--secondary">${chartTypeLabels[chartType]}</span>
      </div>
      <div class="analysis-chart__canvas"></div>
    `;

    const canvas = card.querySelector('.analysis-chart__canvas');
    if (window.echarts) {
      const chart = echarts.init(canvas);
      const option = buildChartOption(chartType, categories, seriesData, seriesNames);
      chart.setOption(option);
      chartInstances.push(chart);
      window.addEventListener('resize', () => chart.resize());
    }

    return card;
  }

  function buildChartOption(chartType, categories, seriesData, seriesNames) {
    const baseOption = {
      tooltip: { trigger: 'axis' },
      legend: { data: seriesNames, top: 0 },
      grid: { left: 50, right: 20, top: 40, bottom: 40 },
      xAxis: { type: 'category', data: categories, axisLabel: { rotate: categories.length > 14 ? 45 : 0, fontSize: 10 } },
      yAxis: { type: 'value' },
    };

    if (chartType === 'pie') {
      return {
        tooltip: { trigger: 'item' },
        legend: { orient: 'vertical', left: 'left' },
        series: [{
          type: 'pie',
          radius: ['40%', '70%'],
          data: categories.map((cat, i) => ({ name: cat, value: seriesData[0]?.[i] || 0 })),
        }],
      };
    }

    if (chartType === 'scatter') {
      return {
        tooltip: { trigger: 'item' },
        grid: { left: 50, right: 20, top: 40, bottom: 40 },
        xAxis: { type: 'value', name: '索引' },
        yAxis: { type: 'value' },
        series: seriesData.map((data, i) => ({
          name: seriesNames[i],
          type: 'scatter',
          data: data.map((v, idx) => [idx, v]),
        })),
      };
    }

    return {
      ...baseOption,
      series: seriesData.map((data, i) => ({
        name: seriesNames[i],
        type: chartType,
        data: data,
        smooth: chartType === 'line',
        areaStyle: chartType === 'line' ? { opacity: 0.1 } : undefined,
      })),
    };
  }

  function formatValue(value, metric) {
    if (value == null) return '--';
    if (metric === 'payment_conversion_rate' || metric === 'expense_ratio' || metric === 'profit_rate') {
      return (value * 100).toFixed(2) + '%';
    }
    if (metric === 'payment_amount' || metric === 'net_sales' || metric === 'ad_spend' || metric === 'average_order_value') {
      return '¥' + Number(value).toLocaleString('zh-CN', { maximumFractionDigits: 2 });
    }
    return Number(value).toLocaleString('zh-CN');
  }

  function saveAnalysis() {
    const name = window.prompt('请输入分析名称：', `${metricLabels[currentConfig?.metric || 'payment_amount']}分析`);
    if (!name) return;

    const saved = JSON.parse(localStorage.getItem('tmall_analysis_saved') || '[]');
    saved.push({
      id: Date.now(),
      name,
      config: currentConfig,
      createdAt: new Date().toISOString(),
    });
    localStorage.setItem('tmall_analysis_saved', JSON.stringify(saved));
    loadSavedAnalysis();
    alert('分析已保存');
  }

  function loadSavedAnalysis() {
    const saved = JSON.parse(localStorage.getItem('tmall_analysis_saved') || '[]');
    const section = $('#savedAnalysisSection');
    const list = $('#savedAnalysisList');

    if (!saved.length) {
      section.style.display = 'none';
      return;
    }

    section.style.display = 'block';
    list.innerHTML = saved.map((item) => `
      <div class="analysis-saved__item">
        <div>
          <div class="analysis-saved__name">${item.name}</div>
          <div class="analysis-saved__meta">${metricLabels[item.config.metric]} · ${dimensionLabels[item.config.dimension]} · ${item.config.startDate} ~ ${item.config.endDate}</div>
        </div>
        <div class="analysis-saved__actions">
          <button class="ui-button ui-button--ghost ui-button--sm" data-load="${item.id}">加载</button>
          <button class="ui-button ui-button--ghost ui-button--sm" data-delete="${item.id}">删除</button>
        </div>
      </div>
    `).join('');

    list.querySelectorAll('[data-load]').forEach((btn) => {
      btn.addEventListener('click', () => {
        const item = saved.find((s) => s.id == btn.dataset.load);
        if (item) {
          $('#metricSelect').value = item.config.metric;
          $('#dimensionSelect').value = item.config.dimension;
          $('#chartTypeSelect').value = item.config.chartType;
          $('#startDate').value = item.config.startDate;
          $('#endDate').value = item.config.endDate;
          $('#topNSelect').value = item.config.topN;
          runAnalysis();
        }
      });
    });

    list.querySelectorAll('[data-delete]').forEach((btn) => {
      btn.addEventListener('click', () => {
        if (!confirm('确定删除这个分析？')) return;
        const saved = JSON.parse(localStorage.getItem('tmall_analysis_saved') || '[]');
        const filtered = saved.filter((s) => s.id != btn.dataset.delete);
        localStorage.setItem('tmall_analysis_saved', JSON.stringify(filtered));
        loadSavedAnalysis();
      });
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
