const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.resolve(__dirname, '..', 'frontend', 'ui_demo', 'assets', 'charts.js'), 'utf8');
const window = {
  matchMedia: () => ({ matches: false }),
  addEventListener() {},
  removeEventListener() {},
  echarts: {},
};
const context = {
  window,
  document: { documentElement: {}, getElementById() { return null; } },
  getComputedStyle: () => ({ getPropertyValue: () => '#64748b' }),
  ResizeObserver: class { observe() {} disconnect() {} },
  WeakMap,
  Intl,
};
vm.runInNewContext(source, context, { filename: 'charts.js' });

assert.equal(window.DemoCharts.formatValue(12.013150999999999), '12.01');
assert.equal(window.DemoCharts.formatValue(1886), '1,886');
assert.equal(window.DemoCharts.formatValue(-0.0000001), '0');
assert.equal(window.DemoCharts.formatValue(null), '--');
assert.equal(window.DemoCharts.formatValue(Number.NaN), '--');
assert.equal(window.DemoCharts.formatValue(Number.POSITIVE_INFINITY), '--');

const option = window.DemoCharts.toEchartsOption({
  data: {
    labels: ['2025-05'],
    datasets: [
      { label: 'GSV（万元）', type: 'line', data: [12.013150999999999] },
      { label: '支付件数', data: [1886] },
    ],
  },
});

assert.equal(option.yAxis[0].axisLabel.formatter(12.013150999999999), '12.01');
assert.equal(option.series[0].tooltip.valueFormatter(12.013150999999999), '12.01');
assert.equal(option.series[1].tooltip.valueFormatter(1886), '1,886');

const percentOption = window.DemoCharts.toEchartsOption({
  data: {
    labels: ['2025-05'],
    datasets: [
      { label: '退款率', type: 'line', yAxisID: 'y1', data: [0.1903] },
      { label: 'ROI', type: 'line', yAxisID: 'y2', data: [3.1415926], valueFormatter: (value) => `${Number(value).toFixed(1)}x` },
    ],
  },
  options: {
    scales: {
      y1: { ticks: { callback: (value) => `${Number(value * 100).toFixed(0)}%` } },
      y2: {},
    },
  },
});

assert.equal(percentOption.series[0].tooltip.valueFormatter(0.1903), '19%');
assert.equal(percentOption.series[1].tooltip.valueFormatter(3.1415926), '3.1x');
console.log('chart formatter contract passed');
