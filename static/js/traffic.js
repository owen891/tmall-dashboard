/* ================================================================
   流量结构分析
================================================================ */
async function loadTrafficStructure(dim, period) {
    const container = document.getElementById('trafficContainer');
    const loading = document.getElementById('trafficLoading');
    if (!container) return;

    try {
        const data = await apiFetch(`/api/traffic_structure?dim=${dim}&period=${period}`);
        if (loading) loading.style.display = 'none';
        container.style.display = 'grid';
        if (!data || !data.structure || !data.structure.total_val) {
            container.innerHTML = '<div class="empty-state" style="grid-column:1/-1;">暂无流量数据</div>';
            return;
        }
        renderTrafficPie(data);
        renderTrafficTrend(data);
    } catch (e) {
        if (loading) loading.style.display = 'none';
        container.style.display = 'grid';
        container.innerHTML = `<div class="empty-state" style="grid-column:1/-1;">加载失败: ${e.message}</div>`;
    }
}

function renderTrafficPie(data) {
    const chart = getChart('chartTrafficPie');
    if (!chart || !data.structure) return;
    const s = data.structure;
    
    chart.setOption({
        backgroundColor: 'transparent',
        tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
        legend: { orient: 'vertical', right: 20, top: 'center', textStyle: { color: '#94A3B8', fontSize: 13 } },
        series: [{
            type: 'pie',
            radius: ['45%', '70%'],
            center: ['35%', '50%'],
            avoidLabelOverlap: true,
            itemStyle: { borderRadius: 6, borderColor: '#0B0F19', borderWidth: 2 },
            label: { show: false },
            emphasis: { label: { show: true, fontSize: 14, fontWeight: 'bold' } },
            data: [
                { value: s.search_val, name: `搜索 ${s.search}%`, itemStyle: { color: '#06B6D4' } },
                { value: s.recommend_val, name: `推荐 ${s.recommend}%`, itemStyle: { color: '#8B5CF6' } },
                { value: s.paid_val, name: `付费 ${s.paid}%`, itemStyle: { color: '#F59E0B' } },
                { value: s.organic_val, name: `其他 ${s.organic}%`, itemStyle: { color: '#64748B' } },
            ],
        }],
    }, true);
    addChartSaveBtn(chart, 'chartTrafficPie');
}

function renderTrafficTrend(data) {
    const chart = getChart('chartTrafficTrend');
    if (!chart || !data.trend || data.trend.length === 0) return;
    
    const periods = data.trend.map(t => t.period);
    chart.setOption({
        backgroundColor: 'transparent',
        tooltip: { trigger: 'axis' },
        legend: { data: ['搜索', '推荐', '付费', '其他'], textStyle: { color: '#94A3B8' } },
        grid: { left: 50, right: 20, top: 40, bottom: 30 },
        xAxis: { type: 'category', data: periods, axisLabel: { color: '#94A3B8' } },
        yAxis: { type: 'value', name: '占比%', axisLabel: { color: '#94A3B8', formatter: '{value}%' } },
        series: [
            { name: '搜索', type: 'line', stack: 'total', areaStyle: { opacity: 0.3 }, data: data.trend.map(t => t.search_pct || 0), itemStyle: { color: '#06B6D4' }, smooth: true },
            { name: '推荐', type: 'line', stack: 'total', areaStyle: { opacity: 0.3 }, data: data.trend.map(t => t.recommend_pct || 0), itemStyle: { color: '#8B5CF6' }, smooth: true },
            { name: '付费', type: 'line', stack: 'total', areaStyle: { opacity: 0.3 }, data: data.trend.map(t => t.paid_pct || 0), itemStyle: { color: '#F59E0B' }, smooth: true },
            { name: '其他', type: 'line', stack: 'total', areaStyle: { opacity: 0.3 }, data: data.trend.map(t => t.organic_pct || 0), itemStyle: { color: '#64748B' }, smooth: true },
        ],
    }, true);
    addChartSaveBtn(chart, 'chartTrafficTrend');
}
