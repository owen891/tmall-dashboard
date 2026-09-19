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

    // 加载已保存的分析
    loadSavedAnalysis();

    // 默认应用第一个模板
    applyTemplate('sales-trend');
  }

  function applyTemplate(name) {
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
    chartsContainer.innerHTML = '<div class="analysis-empty"><p>加载中…</p></div>';

    try {
      const data = await fetchAnalysisData(config);
      renderCharts(config, data);
    } catch (error) {
      chartsContainer.innerHTML = `<div class="analysis-empty"><p>加载失败：${error.message}</p></div>`;
    }
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
      chartsContainer.innerHTML = '<div class="analysis-empty"><p>暂无数据，请调整时间范围或指标</p></div>';
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
        <div class="data-table-wrap"><table class="data-table">
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
        <span class="badge badge--secondary">${chartTypeLabels[chartType]}</span>
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
    if (metric === 'payment_conversion_rate' || metric === 'expense_ratio') {
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
          <button class="button button--ghost button--sm" data-load="${item.id}">加载</button>
          <button class="button button--ghost button--sm" data-delete="${item.id}">删除</button>
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
