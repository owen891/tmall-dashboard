// 核心单品九维分析：静态精选内容（月度复盘沉淀，人工核准），本文件只负责周度趋势图表。
// 数据口径见页面头说明；后续如需活数据化，逐维接 /api/products/<id>/detail|trade|promotion。
(function () {
  function initCharts() {
    document.querySelectorAll('.ninedim .chart').forEach(function (el) {
      if (typeof echarts === 'undefined') {
        el.textContent = '周度趋势图暂不可用（图表库加载失败）';
        el.style.display = 'flex';
        el.style.alignItems = 'center';
        el.style.justifyContent = 'center';
        el.style.color = 'var(--text-tertiary)';
        el.style.fontSize = '12px';
        return;
      }
      var gsv = JSON.parse(el.dataset.gsv || '[]');
      var prof = JSON.parse(el.dataset.prof || '[]');
      var labels = JSON.parse(el.dataset.labels || '["W1","W2","W3","W4","W5"]');
      var c = echarts.init(el);
      c.setOption({
        tooltip: { trigger: 'axis' },
        legend: { data: ['GSV(万)', '利润(万)'], top: 0, textStyle: { fontSize: 11 } },
        grid: { left: 40, right: 16, top: 28, bottom: 24 },
        xAxis: { type: 'category', data: labels, axisLabel: { fontSize: 11 } },
        yAxis: { type: 'value', axisLabel: { fontSize: 11 } },
        series: [
          { name: 'GSV(万)', type: 'bar', data: gsv, itemStyle: { color: '#4f46e5' }, barWidth: '45%' },
          { name: '利润(万)', type: 'line', data: prof, itemStyle: { color: '#ef4444' }, lineStyle: { width: 2 } }
        ]
      });
      window.addEventListener('resize', function () { c.resize(); });
    });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initCharts);
  else initCharts();
})();
