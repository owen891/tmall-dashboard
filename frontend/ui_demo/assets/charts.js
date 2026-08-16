(function () {
  const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  const px = (name, fallback) => Number.parseFloat(css(name)) || fallback;
  const chartMetaSize = () => px('--font-size-meta', 12);
  const chartRadius = () => px('--chart-radius', 4);
  const chartLineWidth = () => px('--chart-line-width', 2);
  const chartPointRadius = () => px('--chart-point-radius', 3);
  const chartLegendBox = () => px('--chart-legend-box', 12);
  const chartLegendHeight = () => px('--chart-legend-height', 8);
  const reducedMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
  const instances = new WeakMap();

  function formatChartValue(value) {
    if (value == null || value === '') return '--';
    const numeric = Number(value);
    if (!Number.isFinite(numeric)) return '--';
    const normalized = Math.abs(numeric) < 0.005 ? 0 : numeric;
    return normalized.toLocaleString('zh-CN', { maximumFractionDigits: 2 });
  }

  function axisFromScale(scale = {}, fallbackPosition) {
    const ticks = scale.ticks || {};
    const grid = scale.grid || {};
    return { type: 'value', position: scale.position || fallbackPosition, min: scale.min, max: scale.max,
      axisLabel: { color: ticks.color || css('--text-muted'), fontSize: ticks.font?.size || chartMetaSize(), formatter: typeof ticks.callback === 'function' ? ticks.callback : formatChartValue },
      splitLine: { show: grid.display !== false, lineStyle: { color: grid.color || css('--border') } }, axisLine: { show: false }, axisTick: { show: false } };
  }

  function toEchartsOption(config) {
    const options = config.options || {};
    const plugins = options.plugins || {};
    const legendConfig = plugins.legend || {};
    const legendVisible = legendConfig.display !== false;
    const labels = config.data?.labels || [];
    const scales = options.scales || {};
    const horizontal = options.indexAxis === 'y';
    const datasets = config.data?.datasets || [];
    const yKeys = [...new Set(datasets.map((item) => item.yAxisID || 'y'))];
    const yAxis = yKeys.map((key, index) => axisFromScale(scales[key] || {}, index ? 'right' : 'left'));
    const legendPosition = legendConfig.position || 'bottom';
    const legendOffset = legendVisible && (legendPosition === 'bottom' || legendPosition === 'top') ? 34 : 0;
    return {
      animation: reducedMotion ? false : { duration: 220 }, tooltip: { trigger: 'axis', confine: true },
      legend: legendVisible ? { show: true, bottom: 4, top: legendPosition === 'top' ? 4 : undefined, left: legendPosition === 'left' ? 6 : legendPosition === 'right' ? undefined : 'center', right: legendPosition === 'right' ? 6 : undefined, textStyle: { color: legendConfig.labels?.color || css('--text-muted'), fontSize: legendConfig.labels?.font?.size || chartMetaSize() }, itemWidth: legendConfig.labels?.boxWidth || chartLegendBox(), itemHeight: chartLegendHeight(), type: 'scroll' } : { show: false },
      grid: { left: 56, right: yAxis.length > 1 ? 56 : 24, top: 20 + (legendPosition === 'top' ? legendOffset : 0), bottom: 30 + (legendPosition === 'bottom' ? legendOffset : 0), containLabel: true },
      xAxis: horizontal ? axisFromScale(scales.x || {}) : { type: 'category', data: labels, axisLabel: { color: scales.x?.ticks?.color || css('--text-muted'), fontSize: scales.x?.ticks?.font?.size || chartMetaSize(), hideOverlap: true }, splitLine: { show: false }, axisLine: { lineStyle: { color: css('--border') } }, axisTick: { show: false } },
      yAxis: horizontal ? { type: 'category', data: labels, axisLabel: { color: scales.y?.ticks?.color || css('--text-muted'), fontSize: scales.y?.ticks?.font?.size || chartMetaSize() }, splitLine: { show: false }, axisLine: { lineStyle: { color: css('--border') } }, axisTick: { show: false } } : yAxis,
      series: datasets.map((item) => {
        const axisKey = item.yAxisID || 'y';
        const axisFormatter = scales[axisKey]?.ticks?.callback;
        const valueFormatter = typeof item.valueFormatter === 'function'
          ? item.valueFormatter
          : typeof axisFormatter === 'function' ? axisFormatter : formatChartValue;
        return { name: item.label || '', type: item.type === 'line' ? 'line' : 'bar', data: item.data || [], yAxisIndex: Math.max(0, yKeys.indexOf(axisKey)), smooth: item.type === 'line' ? item.tension !== 0 : false, showSymbol: item.pointRadius !== 0, symbolSize: item.pointRadius || chartPointRadius(), lineStyle: { width: item.borderWidth || chartLineWidth(), color: item.borderColor, type: item.borderDash ? 'dashed' : 'solid' }, itemStyle: { color: item.backgroundColor || item.borderColor, borderRadius: item.borderRadius || 0 }, barMaxWidth: item.maxBarThickness || item.barThickness || 28, tooltip: { valueFormatter } };
      })
    };
  }

  function buildChart(node, config) {
    if (!node || !window.echarts) return null;
    instances.get(node)?.destroy();
    const chart = window.echarts.init(node);
    chart.setOption(toEchartsOption(config), true);
    const resize = () => chart.resize();
    const observer = window.ResizeObserver ? new ResizeObserver(resize) : null;
    observer?.observe(node);
    window.addEventListener('resize', resize, { passive: true });
    const api = { destroy() { observer?.disconnect(); window.removeEventListener('resize', resize); chart.dispose(); instances.delete(node); } };
    instances.set(node, api);
    return api;
  }

  const make = (id, config) => buildChart(document.getElementById(id), config);
  const trendPalette = ['--brand', '--info', '--success', '--warning', '--purple', '--danger'];
  if (!window.EChartCompat && window.echarts) window.EChartCompat = function CompatChart(context, config) { return buildChart(context?.canvas || context, config); };
  window.DemoCharts = {
    formatValue: formatChartValue,
    toEchartsOption,
    chartRadius,
    chartLineWidth,
    chartPointRadius,
    chartLegendBox,
    line: (id, labels, values, label = '指标') => make(id, { data: { labels, datasets: [{ label, type: 'line', data: values, borderColor: css('--brand'), backgroundColor: css('--brand'), tension: .35, pointRadius: chartPointRadius(), borderWidth: chartLineWidth() }] }, options: { plugins: { legend: { display: false } }, scales: { x: { grid: { display: false } }, y: { grid: { color: css('--border') } } } } }),
    lineMulti: (id, labels, datasets) => make(id, { data: { labels, datasets: datasets.map((item, index) => ({ label: item.label, type: 'line', data: item.data, borderColor: css(item.color || trendPalette[index % trendPalette.length]), backgroundColor: css(item.color || trendPalette[index % trendPalette.length]), tension: .35, pointRadius: chartPointRadius(), borderWidth: chartLineWidth() })) }, options: { plugins: { legend: { display: datasets.length > 1, position: 'bottom' } }, scales: { x: { grid: { display: false } }, y: { grid: { color: css('--border') } } } } }),
    bar: (id, labels, values, color = '--brand') => make(id, { data: { labels, datasets: [{ data: values, backgroundColor: css(color), borderRadius: chartRadius(), maxBarThickness: 24 }] }, options: { plugins: { legend: { display: false } }, scales: { x: { grid: { display: false } }, y: { grid: { color: css('--border') } } } } }),
    horizontalBar: (id, labels, values, color = '--brand') => make(id, { data: { labels, datasets: [{ data: values, backgroundColor: css(color), borderRadius: chartRadius(), barThickness: 16 }] }, options: { indexAxis: 'y', plugins: { legend: { display: false } }, scales: { x: { grid: { color: css('--border') } }, y: { grid: { display: false } } } } }),
    linePair: (id, labels, first, second, firstLabel = '本期', secondLabel = '对比期') => make(id, { data: { labels, datasets: [{ label: firstLabel, type: 'line', data: first, borderColor: css('--brand'), tension: .35, pointRadius: chartPointRadius(), borderWidth: chartLineWidth() }, { label: secondLabel, type: 'line', data: second, borderColor: css('--info'), tension: .35, pointRadius: chartPointRadius(), borderWidth: chartLineWidth(), borderDash: [5, 4] }] }, options: { plugins: { legend: { position: 'bottom' } }, scales: { x: { grid: { display: false } }, y: { grid: { color: css('--border') } } } } }),
    moneyRate: (id, labels, money, rate, moneyLabel = '金额', rateLabel = '比率') => make(id, { data: { labels, datasets: [{ label: moneyLabel, data: money, backgroundColor: css('--chart-brand-fill'), borderRadius: chartRadius(), yAxisID: 'y' }, { type: 'line', label: rateLabel, data: rate, borderColor: css('--warning'), tension: .35, pointRadius: chartPointRadius(), borderWidth: chartLineWidth(), yAxisID: 'y1' }] }, options: { plugins: { legend: { position: 'bottom' } }, scales: { x: { grid: { display: false } }, y: { grid: { color: css('--border') } }, y1: { position: 'right', grid: { display: false } } } } }),
    adTrend: (id, labels, spend, gmv, roi) => make(id, { data: { labels, datasets: [{ label: '推广花费', data: spend, backgroundColor: css('--chart-warning-fill'), borderRadius: chartRadius(), yAxisID: 'y' }, { label: '销售额', data: gmv, backgroundColor: css('--chart-info-fill'), borderRadius: chartRadius(), yAxisID: 'y' }, { type: 'line', label: '推广 ROI', data: roi, borderColor: css('--success'), tension: .35, pointRadius: chartPointRadius(), borderWidth: chartLineWidth(), yAxisID: 'y1' }] }, options: { plugins: { legend: { position: 'bottom' } }, scales: { x: { grid: { display: false } }, y: { grid: { color: css('--border') } }, y1: { position: 'right', grid: { display: false } } } } })
  };
})();
