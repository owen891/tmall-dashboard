/* ================================================================
   模块6: 退款售后
================================================================ */
async function loadRefundData(dim, period, start, end) {
    setLoading('loading-refund-trend', true);
    setLoading('loading-refund-alert', true);

    const [trendData, alertData] = await Promise.all([
        apiFetch(`/api/trend?dim=${dim}&start=${start}&end=${end}`),
        apiFetch(`/api/refund_alert?dim=${dim}&period=${period}&threshold=0.20`),
    ]);

    setLoading('loading-refund-trend', false);
    setLoading('loading-refund-alert', false);

    // --- 退款趋势双轴图 ---
    // 后端 /api/trend 返回原始数组 [{period, gmv, refund, net_sales, ...}, ...]
    if (trendData && Array.isArray(trendData) && trendData.length > 0) {
        const dates = trendData.map(d => d.period);
        const chart = getChart('chartRefundTrend');
        const opt = baseOption();
        opt.tooltip.trigger = 'axis';
        opt.legend.data = ['退款金额', '退款率'];
        opt.legend.top = 0;
        opt.grid.right = 80;
        opt.xAxis.data = dates;
        opt.yAxis = [
            {
                type: 'value', name: '退款金额',
                nameTextStyle: { color: '#94A3B8' },
                axisLabel: { color: '#94A3B8', formatter: v => (v / 10000).toFixed(0) + '万' },
            },
            {
                type: 'value', name: '退款率',
                nameTextStyle: { color: '#94A3B8' },
                axisLabel: { color: '#94A3B8', formatter: v => (v * 100).toFixed(1) + '%' },
                splitLine: { show: false },
            },
        ];
        opt.series = [
            {
                name: '退款金额', type: 'bar', yAxisIndex: 0,
                data: trendData.map(d => d.refund || 0),
                barWidth: '50%',
                itemStyle: {
                    color: 'rgba(239,68,68,0.6)', borderRadius: [4, 4, 0, 0],
                },
            },
            {
                name: '退款率', type: 'line', yAxisIndex: 1,
                data: trendData.map(d => {
                    if (d.gmv && d.gmv > 0) return d.refund / d.gmv;
                    return null;
                }),
                smooth: true, symbol: 'circle', symbolSize: 6,
                lineStyle: { width: 2, color: '#F59E0B' },
                itemStyle: { color: '#F59E0B' },
            },
        ];
        chart.setOption(opt, true);
        addChartSaveBtn(chart, 'chartRefundTrend');
    }

    // --- 高退款率商品预警列表 ---
    // 后端 /api/refund_alert 返回原始数组 [{product_id, title, refund_rate, ...}, ...]
    const listEl = document.getElementById('refundAlertList');
    if (!alertData || !Array.isArray(alertData) || alertData.length === 0) {
        listEl.innerHTML = '<div style="text-align:center;color:#64748B;padding:40px;">暂无预警数据</div>';
        return;
    }
    listEl.innerHTML = alertData.map(item => {
        const rate = item.refund_rate || 0;
        const cls = rate > 0.3 ? 'danger' : 'warning';
        return `<div class="alert-item">
            <span class="product-name">${item.title || '未知商品'}</span>
            <span class="refund-rate ${cls}">${fmtPct(rate)}</span>
        </div>`;
    }).join('');
}
