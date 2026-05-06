/* ================================================================
   模块2: 销售趋势图（双Y轴）
================================================================ */
let _trendCache = null;
async function _fetchTrend(dim, start, end) {
    const key = `${dim}_${start}_${end}`;
    if (_trendCache && _trendCache.key === key) return _trendCache.data;
    const data = await apiFetch(`/api/trend?dim=${dim}&start=${start}&end=${end}`);
    _trendCache = { key, data };
    return data;
}

async function loadSalesTrend(dim, start, end) {
    setLoading('loading-trend', true);
    const data = await _fetchTrend(dim, start, end);
    setLoading('loading-trend', false);
    // 后端返回原始数组 [{period, gmv, refund, net_sales, visitors, ad_spend, conversion}, ...]
    if (!data || !Array.isArray(data) || data.length === 0) { showChartEmpty('chartSalesTrend'); return; }

    // 从数组中提取各字段
    const dates = data.map(d => d.period);
    const paymentAmount = data.map(d => d.gmv || 0);
    const netSales = data.map(d => d.net_sales || 0);

    const chart = getChart('chartSalesTrend');
    const opt = baseOption();
    opt.tooltip.trigger = 'axis';
    opt.legend.data = ['支付金额', '净销售额', '支付件数'];
    opt.legend.top = 0;
    opt.grid.right = 80;
    opt.dataZoom = [
        { type: 'inside', start: 0, end: 100 },
        { type: 'slider', start: 0, end: 100, height: 20, bottom: 5,
          borderColor: '#334155', fillerColor: 'rgba(59,130,246,0.15)',
          handleStyle: { color: '#3B82F6' },
          textStyle: { color: '#94A3B8' },
        },
    ];
    opt.xAxis.data = dates;
    opt.yAxis = [
        {
            type: 'value', name: '金额(元)',
            nameTextStyle: { color: '#94A3B8' },
            axisLabel: { color: '#94A3B8', formatter: v => (v / 10000).toFixed(0) + '万' },
        },
        {
            type: 'value', name: '件数',
            nameTextStyle: { color: '#94A3B8' },
            axisLabel: { color: '#94A3B8' },
            splitLine: { show: false },
        },
    ];
    opt.series = [
        {
            name: '支付金额', type: 'line', yAxisIndex: 0,
            data: paymentAmount,
            smooth: true, symbol: 'circle', symbolSize: 6,
            lineStyle: { width: 2, color: '#3B82F6' },
            itemStyle: { color: '#3B82F6' },
            areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                { offset: 0, color: 'rgba(59,130,246,0.3)' },
                { offset: 1, color: 'rgba(59,130,246,0.02)' },
            ])},
        },
        {
            name: '净销售额', type: 'line', yAxisIndex: 0,
            data: netSales,
            smooth: true, symbol: 'circle', symbolSize: 6,
            lineStyle: { width: 2, color: '#10B981' },
            itemStyle: { color: '#10B981' },
            areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                { offset: 0, color: 'rgba(16,185,129,0.2)' },
                { offset: 1, color: 'rgba(16,185,129,0.02)' },
            ])},
        },
        {
            name: '支付件数', type: 'bar', yAxisIndex: 1,
            data: data.map(d => d.payment_count || 0),
            barWidth: '40%',
            itemStyle: { color: 'rgba(251,191,36,0.6)', borderRadius: [4, 4, 0, 0] },
        },
    ];
    chart.setOption(opt, true);
    addChartSaveBtn(chart, 'chartSalesTrend');

    // 加载事件标注
    loadChartEvents('chartSalesTrend', dates);

    // 添加点击事件：点击趋势图上的点显示该周期详情 + 联动筛选商品表格
    chart.off('click');
    chart.on('click', (params) => {
        if (params.componentType === 'series') {
            const period = params.name;
            showPeriodDetail(period, params.event.event);
            // 联动筛选：切换到商品运营Tab并设置周期
            STATE.period = period;
            STATE.page = 1;
            // 更新周期选择器的值
            const periodSelect = document.getElementById('periodSelect');
            if (periodSelect) {
                periodSelect.value = period;
            }
            // 切换到商品运营Tab并重新加载商品表格
            switchTab('tab-ops');
            if (typeof loadProducts === 'function') {
                loadProducts(STATE.dim, STATE.period);
            }
            showToast('已切换到 ' + period + ' 的商品数据', 'info');
        }
    });
}

/* ================================================================
   趋势图点击：显示周期详情弹窗
================================================================ */
function showPeriodDetail(period, mouseEvent) {
    // 移除已有的弹窗
    const existing = document.getElementById('periodDetailPopup');
    if (existing) existing.remove();

    // 创建弹窗
    const popup = document.createElement('div');
    popup.className = 'period-detail-popup';
    popup.id = 'periodDetailPopup';
    popup.innerHTML = `<div class="period-detail-title">${escapeHtml(period)} KPI 详情</div>
        <div class="period-detail-grid" id="periodDetailGrid">
            <div style="text-align:center;color:#64748B;padding:12px;grid-column:1/-1;">加载中...</div>
        </div>`;
    document.body.appendChild(popup);

    // 定位弹窗（靠近点击位置）
    if (mouseEvent) {
        let x = mouseEvent.clientX + 16;
        let y = mouseEvent.clientY - 20;
        // 防止超出视口
        if (x + 280 > window.innerWidth) x = mouseEvent.clientX - 296;
        if (y + 300 > window.innerHeight) y = window.innerHeight - 310;
        if (y < 10) y = 10;
        popup.style.left = x + 'px';
        popup.style.top = y + 'px';
    } else {
        popup.style.left = '50%';
        popup.style.top = '50%';
        popup.style.transform = 'translate(-50%, -50%)';
    }
    popup.classList.add('open');

    // 获取该周期的 KPI 数据
    apiFetch(`/api/kpi?dim=${STATE.dim}&period=${period}`)
        .then(data => {
            if (!data || !data.current) {
                document.getElementById('periodDetailGrid').innerHTML =
                    '<div style="text-align:center;color:#64748B;padding:12px;grid-column:1/-1;">暂无数据</div>';
                return;
            }
            const c = data.current;
            const items = [
                { label: '总销售额', value: fmtWan(c.gmv) },
                { label: '净销售额', value: fmtWan(c.net_sales) },
                { label: '访客数', value: fmtNum(c.visitors) },
                { label: '客单价', value: c.aov != null ? '¥' + Number(c.aov).toFixed(0) : '--' },
                { label: '转化率', value: fmtPct(c.conversion) },
                { label: '退款率', value: fmtPct(c.refund_rate) },
                { label: '推广花费', value: fmtWan(c.ad_spend) },
                { label: 'ROI', value: c.roi != null ? Number(c.roi).toFixed(2) : '--' },
            ];
            document.getElementById('periodDetailGrid').innerHTML = items.map(m => `
                <div class="period-detail-item">
                    <div class="period-detail-label">${m.label}</div>
                    <div class="period-detail-value">${m.value}</div>
                </div>
            `).join('');
        })
        .catch(() => {
            document.getElementById('periodDetailGrid').innerHTML =
                '<div style="text-align:center;color:#EF4444;padding:12px;grid-column:1/-1;">加载失败</div>';
        });

    // 点击其他地方关闭弹窗
    setTimeout(() => {
        const closeHandler = (e) => {
            if (!popup.contains(e.target)) {
                popup.remove();
                document.removeEventListener('click', closeHandler);
            }
        };
        document.addEventListener('click', closeHandler);
    }, 100);
}

/* ================================================================
   模块3: 流量与转化分析
================================================================ */
async function loadTrafficAndConv(dim, start, end) {
    setLoading('loading-uv', true);
    setLoading('loading-conv', true);
    const data = await _fetchTrend(dim, start, end);
    setLoading('loading-uv', false);
    setLoading('loading-conv', false);
    // 后端返回原始数组 [{period, gmv, refund, net_sales, visitors, ad_spend, conversion}, ...]
    if (!data || !Array.isArray(data) || data.length === 0) { showChartEmpty('chartUVTrend'); showChartEmpty('chartConvTrend'); return; }

    // 从数组中提取各字段
    const dates = data.map(d => d.period);

    // --- 访客数趋势 ---
    const uvChart = getChart('chartUVTrend');
    const uvOpt = baseOption();
    uvOpt.tooltip.trigger = 'axis';
    uvOpt.xAxis.data = dates;
    uvOpt.yAxis.name = '访客数';
    uvOpt.yAxis.nameTextStyle = { color: '#94A3B8' };
    uvOpt.yAxis.axisLabel = { color: '#94A3B8', formatter: v => v >= 10000 ? (v / 10000).toFixed(0) + '万' : v };
    uvOpt.series = [{
        name: '访客数(UV)', type: 'line',
        data: data.map(d => d.visitors || 0),
        smooth: true, symbol: 'circle', symbolSize: 6,
        lineStyle: { width: 2, color: '#8B5CF6' },
        itemStyle: { color: '#8B5CF6' },
        areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(139,92,246,0.3)' },
            { offset: 1, color: 'rgba(139,92,246,0.02)' },
        ])},
    }];
    uvChart.setOption(uvOpt, true);
    addChartSaveBtn(uvChart, 'chartUVTrend');

    // --- 转化率趋势（含行业CTR基准线） ---
    const convChart = getChart('chartConvTrend');
    const convOpt = baseOption();
    convOpt.tooltip.trigger = 'axis';
    convOpt.legend.data = ['支付转化率', '加购率', '收藏率', '行业均值'];
    convOpt.legend.top = 0;
    convOpt.xAxis.data = dates;
    convOpt.yAxis.name = '比率';
    convOpt.yAxis.nameTextStyle = { color: '#94A3B8' };
    convOpt.yAxis.axisLabel = { color: '#94A3B8', formatter: v => (v * 100).toFixed(1) + '%' };
    convOpt.series = [
        {
            name: '支付转化率', type: 'line',
            data: data.map(d => d.conversion != null ? +(d.conversion * 100).toFixed(2) : null),
            smooth: true, symbol: 'circle', symbolSize: 6,
            lineStyle: { width: 2, color: '#3B82F6' },
            itemStyle: { color: '#3B82F6' },
        },
        {
            name: '加购率', type: 'line',
            data: data.map(d => d.cart_rate != null ? +(d.cart_rate * 100).toFixed(2) : null),
            smooth: true, symbol: 'circle', symbolSize: 6,
            lineStyle: { width: 2, color: '#F59E0B' },
            itemStyle: { color: '#F59E0B' },
        },
        {
            name: '收藏率', type: 'line',
            data: data.map(d => d.fav_rate != null ? +(d.fav_rate * 100).toFixed(2) : null),
            smooth: true, symbol: 'circle', symbolSize: 6,
            lineStyle: { width: 2, color: '#EC4899' },
            itemStyle: { color: '#EC4899' },
        },
    ];
    convChart.setOption(convOpt, true);
    addChartSaveBtn(convChart, 'chartConvTrend');

    // 加载行业基准对比数据，叠加到转化率趋势图
    loadIndustryBenchmark(dim, end);
}

/* ================================================================
   行业基准对比（叠加到转化率趋势图）
================================================================ */
async function loadIndustryBenchmark(dim, period) {
    const data = await apiFetch(`/api/industry_benchmark?dim=${dim}&period=${period}`);
    if (!data) return;

    const trend = data.trend || [];
    if (trend.length === 0) return;

    const chart = getChart('chartConvTrend');
    if (!chart) return;

    // 在现有图表上叠加行业均值虚线
    const periods = trend.map(t => t.period);
    const industryData = trend.map(t => t.industry_ctr != null ? +(t.industry_ctr * 100).toFixed(2) : null);

    // 获取当前图表的xAxis数据，对齐行业数据
    const currentOpt = chart.getOption();
    if (!currentOpt || !currentOpt.xAxis || !currentOpt.xAxis[0]) return;
    const currentDates = currentOpt.xAxis[0].data || [];

    // 对齐：将行业数据映射到当前x轴
    const alignedIndustry = currentDates.map(d => {
        const idx = periods.indexOf(d);
        return idx >= 0 ? industryData[idx] : null;
    });

    chart.setOption({
        legend: {
            data: (currentOpt.legend[0].data || []).concat(['行业均值']),
        },
        series: [
            ...currentOpt.series.filter(s => s.name !== '行业均值'),
            {
                name: '行业均值', type: 'line',
                data: alignedIndustry,
                smooth: true, symbol: 'diamond', symbolSize: 6,
                lineStyle: { width: 2, color: '#94A3B8', type: 'dashed' },
                itemStyle: { color: '#94A3B8' },
            },
        ],
    });

    // 添加差距标注（在图表右上角）
    const gapPct = data.gap_pct || 0;
    const gapText = gapPct >= 0
        ? '高于行业均值 ' + gapPct.toFixed(1) + '%'
        : '低于行业均值 ' + Math.abs(gapPct).toFixed(1) + '%';
    const gapColor = gapPct >= 0 ? '#10B981' : '#EF4444';

    chart.setOption({
        graphic: [{
            type: 'text',
            right: 60,
            top: 30,
            style: {
                text: gapText,
                fill: gapColor,
                fontSize: 12,
                fontWeight: 600,
            },
        }],
    });
}

/* ================================================================
   数据异常事件标注
================================================================ */
async function loadChartEvents(chartId, dates) {
    const events = await apiFetch('/api/chart_events?chart_type=sales');
    if (!events || !Array.isArray(events) || events.length === 0) return;

    const chart = CHARTS[chartId];
    if (!chart) return;

    // 构建 markPoint 数据
    const markPointData = [];
    events.forEach(e => {
        // 匹配事件日期到图表数据索引
        const idx = dates.indexOf(e.event_date);
        if (idx >= 0) {
            markPointData.push({
                coord: [idx, null],
                name: e.title,
                value: e.title,
                itemStyle: { color: e.color || '#EF4444' },
                label: {
                    show: true,
                    formatter: e.title,
                    fontSize: 10,
                    color: '#fff',
                    textBorderColor: e.color || '#EF4444',
                    textBorderWidth: 1,
                },
                symbolSize: 40,
                symbol: 'pin',
            });
        }
    });

    if (markPointData.length > 0) {
        // 添加到第一个 series
        chart.setOption({
            series: [{
                markPoint: {
                    data: markPointData,
                    animation: true,
                },
            }],
        });
    }
}

function openEventFormModal() {
    const modal = document.getElementById('eventFormModal');
    if (modal) {
        modal.style.display = 'flex';
        // 设置默认日期为今天
        const today = new Date().toISOString().split('T')[0];
        document.getElementById('eventDateInput').value = today;
    }
}

function closeEventFormModal() {
    const modal = document.getElementById('eventFormModal');
    if (modal) modal.style.display = 'none';
}

async function submitChartEvent() {
    const event_date = document.getElementById('eventDateInput').value;
    const title = document.getElementById('eventTitleInput').value.trim();
    const description = document.getElementById('eventDescInput').value.trim();
    const color = document.getElementById('eventColorInput').value;

    if (!event_date || !title) {
        showToast('请填写日期和标题', 'warning');
        return;
    }

    const result = await apiFetch('/api/chart_events', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ event_date, title, description, color, chart_type: 'sales' }),
    });

    if (result && result.success) {
        showToast('标注已添加', 'success');
        closeEventFormModal();
        // 清空表单
        document.getElementById('eventTitleInput').value = '';
        document.getElementById('eventDescInput').value = '';
        // 重新加载趋势图
        const { dim, periods, period } = STATE;
        const start = periods.length > 0 ? periods[periods.length - 1] : '';
        _trendCache = null; // 清除缓存
        loadSalesTrend(dim, start, period);
    } else {
        showToast('添加标注失败', 'error');
    }
}
