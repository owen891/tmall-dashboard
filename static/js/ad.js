/* ================================================================
   模块5: 推广分析
================================================================ */
async function loadAdPerformance(dim, period) {
    setLoading('loading-scatter', true);
    setLoading('loading-adbar', true);
    const data = await apiFetch(`/api/ad_performance?dim=${dim}&period=${period}`);
    setLoading('loading-scatter', false);
    setLoading('loading-adbar', false);
    // 后端返回原始数组 [{product_id, title, ad_spend, ad_roi, overall_roi, ...}, ...]
    if (!data || !Array.isArray(data) || data.length === 0) { showChartEmpty('chartAdScatter'); showChartEmpty('chartAdCompare'); return; }

    // --- 散点图：花费 vs ROI，气泡大小=销售额 ---
    const scatterChart = getChart('chartAdScatter');
    const scatterData = data.map(item => ({
        name: item.title || '未知',
        value: [item.ad_spend || 0, item.overall_roi || item.ad_roi || 0, item.payment_amount || 0],
    }));

    const scatterOpt = baseOption();
    scatterOpt.tooltip.trigger = 'item';
    scatterOpt.tooltip.formatter = p => {
        const d = p.data;
        return `${d.name}<br/>推广花费：${fmtWan(d.value[0])}<br/>ROI：${d.value[1].toFixed(2)}<br/>销售额：${fmtWan(d.value[2])}`;
    };
    scatterOpt.xAxis.name = '推广花费(元)';
    scatterOpt.xAxis.nameTextStyle = { color: '#94A3B8' };
    scatterOpt.xAxis.axisLabel = { color: '#94A3B8', formatter: v => (v / 10000).toFixed(0) + '万' };
    scatterOpt.yAxis.name = 'ROI';
    scatterOpt.yAxis.nameTextStyle = { color: '#94A3B8' };
    scatterOpt.yAxis.axisLabel = { color: '#94A3B8', formatter: v => v.toFixed(1) };
    scatterOpt.series = [{
        type: 'scatter', data: scatterData,
        symbolSize: d => Math.max(8, Math.min(50, Math.sqrt(d.value[2] / 10000) * 3)),
        itemStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 1, 1, [
                { offset: 0, color: '#3B82F6' },
                { offset: 1, color: '#8B5CF6' },
            ]),
            opacity: 0.75,
        },
        emphasis: { itemStyle: { opacity: 1, borderColor: '#fff', borderWidth: 1 } },
    }];
    scatterChart.setOption(scatterOpt, true);
    addChartSaveBtn(scatterChart, 'chartAdScatter');

    // 推广散点图点击联动：跳转到商品运营Tab并搜索该商品
    scatterChart.off('click');
    scatterChart.on('click', function(params) {
        if (params.data && params.data.name) {
            switchTab('tab-ops');
            // 设置搜索框内容并触发筛选
            var searchInput = document.getElementById('productSearch');
            if (searchInput) {
                searchInput.value = params.data.name;
                if (typeof filterProducts === 'function') {
                    filterProducts();
                }
            }
            showToast('已搜索商品：' + params.data.name, 'info');
        }
    });

    // --- 推广方式花费对比柱状图 ---
    const barChart = getChart('chartAdCompare');
    // 后端返回每行含 keyword_spend, crowd_spend, site_spend，聚合为渠道
    const channels = {
        '直通车(关键词)': data.reduce((s, d) => s + (d.keyword_spend || 0), 0),
        '人群推广': data.reduce((s, d) => s + (d.crowd_spend || 0), 0),
        '定向推广': data.reduce((s, d) => s + (d.site_spend || 0), 0),
    };
    const channelNames = Object.keys(channels);
    const channelValues = channelNames.map(k => channels[k]);

    const barOpt = baseOption();
    barOpt.tooltip.trigger = 'axis';
    barOpt.tooltip.axisPointer = { type: 'shadow' };
    barOpt.tooltip.formatter = params => `${params[0].name}<br/>花费：${fmtWan(params[0].value)}`;
    barOpt.xAxis = {
        type: 'category', data: channelNames,
        axisLabel: { color: '#CBD5E1', fontSize: 12 },
    };
    barOpt.yAxis = {
        type: 'value', name: '花费(元)',
        nameTextStyle: { color: '#94A3B8' },
        axisLabel: { color: '#94A3B8', formatter: v => (v / 10000).toFixed(0) + '万' },
    };
    barOpt.series = [{
        type: 'bar', data: channelValues,
        barWidth: '50%',
        itemStyle: {
            borderRadius: [6, 6, 0, 0],
            color: params => {
                const colors = ['#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6', '#EC4899'];
                return colors[params.dataIndex % colors.length];
            },
        },
        label: {
            show: true, position: 'top',
            color: '#94A3B8', fontSize: 11,
            formatter: p => fmtWan(p.value),
        },
    }];
    barChart.setOption(barOpt, true);
    addChartSaveBtn(barChart, 'chartAdCompare');
}

/* ================================================================
   联动②: 蓝海关键词推荐
================================================================ */
async function loadMarketOpportunities() {
    const data = await apiFetch('/api/market/opportunities');
    const row = document.getElementById('marketOpportunityRow');
    const list = document.getElementById('opsOpportunityList');
    if (!data || !data.opportunities || data.opportunities.length === 0) {
        if (row) row.style.display = 'none';
        return;
    }
    if (row) row.style.display = '';
    const oppColors = {
        '供给不足蓝海词': '#10B981',
        '小众高意向蓝海词': '#3B82F6',
    };
    list.innerHTML = data.opportunities.slice(0, 20).map(item => {
        const color = oppColors[item.opportunity_category] || '#64748B';
        const catTag = `<span style="display:inline-block;padding:1px 8px;border-radius:4px;font-size:0.7rem;font-weight:600;background:${color}22;color:${color};border:1px solid ${color}44;margin-left:8px;">${item.opportunity_category || '机会词'}</span>`;
        const ctr = item.ctr_7d != null ? (item.ctr_7d * 100).toFixed(1) + '%' : '--';
        const cvr = item.cvr_30d != null ? (item.cvr_30d * 100).toFixed(1) + '%' : '--';
        return `<div style="display:flex;align-items:center;justify-content:space-between;padding:6px 12px;border-bottom:1px solid #334155;">
            <div style="display:flex;align-items:center;gap:8px;">
                <span style="color:#F1F5F9;font-size:0.85rem;font-weight:500;">${escapeHtml(item.keyword || '--')}</span>
                ${catTag}
            </div>
            <div style="display:flex;gap:16px;font-size:0.78rem;color:#94A3B8;">
                <span>人气 ${fmtNum(item.pop_30d)}</span>
                <span>CTR ${ctr}</span>
                <span>CVR ${cvr}</span>
            </div>
        </div>`;
    }).join('');
}

/* ================================================================
   推广效果预警
================================================================ */
async function loadAdAlerts(dim, period) {
    const container = document.getElementById('adAlertsContainer');
    if (!container) return;
    
    try {
        const alerts = await apiFetch(`/api/ad_alerts?dim=${dim}&period=${period}`);
        if (!alerts || alerts.length === 0) {
            container.innerHTML = '<div style="text-align:center;color:var(--text-secondary);padding:16px;">✅ 当前周期无推广预警</div>';
            return;
        }
        
        const severityColors = { danger: 'var(--danger)', warning: 'var(--warning)', info: 'var(--accent)' };
        const severityIcons = { danger: '🔴', warning: '🟡', info: '🔵' };
        
        container.innerHTML = `
            <div style="margin-bottom:8px;font-weight:600;color:var(--text-primary);">⚠️ 推广预警 (${alerts.length}条)</div>
            ${alerts.map(a => `
                <div class="ad-alert-item" style="border-left:3px solid ${severityColors[a.severity]};padding:10px 14px;margin-bottom:8px;border-radius:0 8px 8px 0;background:var(--card);">
                    <div style="display:flex;justify-content:space-between;align-items:center;">
                        <span style="font-weight:600;color:var(--text-primary);font-size:13px;">${severityIcons[a.severity]} ${a.title}</span>
                        <span style="font-size:11px;color:${severityColors[a.severity]};font-weight:600;text-transform:uppercase;">${a.severity}</span>
                    </div>
                    <div style="font-size:12px;color:var(--text-secondary);margin-top:4px;">${a.message}</div>
                </div>
            `).join('')}
        `;
    } catch (e) {
        container.innerHTML = '<div style="color:var(--danger);padding:16px;">加载推广预警失败</div>';
    }
}

/* ================================================================
   推广趋势分析
================================================================ */
async function loadAdTrend(dim, period) {
    const chart = getChart('chartAdTrend');
    if (!chart) return;
    
    try {
        const data = await apiFetch(`/api/ad_trend?dim=${dim}&period=${period}&count=6`);
        if (!data || data.length === 0) {
            chart.setOption({ title: { text: '暂无推广趋势数据', left: 'center', top: 'center', textStyle: { color: '#64748B' } } }, true);
            return;
        }
        
        const periods = data.map(d => d.period);
        const adSpend = data.map(d => d.ad_spend || 0);
        const gmv = data.map(d => d.gmv || 0);
        const roi = data.map(d => d.overall_roi || 0);
        
        chart.setOption({
            backgroundColor: 'transparent',
            tooltip: { trigger: 'axis' },
            legend: { data: ['推广花费', '销售额', '投产比'], textStyle: { color: '#94A3B8' } },
            grid: { left: 60, right: 60, top: 45, bottom: 30 },
            xAxis: { type: 'category', data: periods, axisLabel: { color: '#94A3B8', fontSize: 11 } },
            yAxis: [
                { type: 'value', name: '金额', axisLabel: { color: '#94A3B8', formatter: v => (v/10000).toFixed(0)+'万' } },
                { type: 'value', name: 'ROI', axisLabel: { color: '#94A3B8', formatter: v => v.toFixed(1) } },
            ],
            series: [
                {
                    name: '推广花费', type: 'bar', data: adSpend,
                    itemStyle: { color: '#F59E0B', borderRadius: [4,4,0,0] },
                },
                {
                    name: '销售额', type: 'bar', data: gmv,
                    itemStyle: { color: '#06B6D4', borderRadius: [4,4,0,0] },
                },
                {
                    name: '投产比', type: 'line', yAxisIndex: 1, data: roi,
                    itemStyle: { color: '#10B981' },
                    lineStyle: { width: 2 },
                    label: { show: true, position: 'top', color: '#10B981', fontSize: 10, formatter: p => p.value.toFixed(1) },
                },
            ],
        }, true);
        addChartSaveBtn(chart, 'chartAdTrend');
    } catch (e) {
        console.error('加载推广趋势失败:', e);
    }
}
