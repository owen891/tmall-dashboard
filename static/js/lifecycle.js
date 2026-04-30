/* ================================================================
   模块: 生命周期管理
================================================================ */

let _lifecycleSearchTimer = null;

async function loadLifecycleData() {
    const grid = document.getElementById('lifecycleGrid');
    const detail = document.getElementById('lifecycleDetail');
    const search = document.getElementById('lifecycleSearch');
    const tierFilter = document.getElementById('lifecycleTierFilter');

    if (!grid) return;

    // 显示列表，隐藏详情
    grid.style.display = '';
    detail.style.display = 'none';

    grid.innerHTML = '<div class="loading-placeholder">加载中...</div>';

    const data = await apiFetch('/api/lifecycle?limit=50');
    if (!data || !Array.isArray(data) || data.length === 0) {
        grid.innerHTML = '<div style="text-align:center;color:#64748B;padding:40px;">暂无生命周期数据</div>';
        return;
    }

    // 客户端过滤
    let filtered = data;
    const searchVal = (search ? search.value : '').trim().toLowerCase();
    const tierVal = tierFilter ? tierFilter.value : '';

    if (searchVal) {
        filtered = filtered.filter(p => (p.title || '').toLowerCase().includes(searchVal));
    }
    if (tierVal) {
        filtered = filtered.filter(p => p.tier === tierVal);
    }

    if (filtered.length === 0) {
        grid.innerHTML = '<div style="text-align:center;color:#64748B;padding:40px;">无匹配商品</div>';
        return;
    }

    grid.innerHTML = filtered.map(p => {
        const img = p.image_url || '';
        const title = escapeHtml(p.title || '--');
        const tier = escapeHtml(p.tier || '');
        const style = escapeHtml(p.style || '');
        const totalGsv = p.total_gsv || 0;
        const activeMonths = p.active_months || 0;
        const firstMonth = p.first_month || '';
        const lastMonth = p.last_month || '';

        // 解析 gsv_series 绘制迷你趋势
        const series = (p.gsv_series || '').split(',').map(s => {
            const parts = s.split(':');
            return { month: parts[0], gsv: parseFloat(parts[1]) || 0 };
        });

        // 计算趋势方向
        let trendIcon = '&#8212;'; // -
        if (series.length >= 2) {
            const last = series[series.length - 1].gsv;
            const prev = series[series.length - 2].gsv;
            if (prev > 0) {
                const change = (last - prev) / prev;
                if (change > 0.05) trendIcon = '&#9650;'; // up
                else if (change < -0.05) trendIcon = '&#9660;'; // down
            }
        }

        const tierColors = {
            '引流款': '#3B82F6',
            '利润款': '#10B981',
            '爆款': '#F59E0B',
            '形象款': '#8B5CF6',
        };
        const tierColor = tierColors[tier] || '#64748B';

        return `<div class="lifecycle-card" onclick="showLifecycleDetail('${p.product_id}')">
            <div class="lifecycle-card-header">
                ${img ? `<img class="lifecycle-card-img" src="${img}" alt="">` : '<div class="lifecycle-card-img" style="display:flex;align-items:center;justify-content:center;color:#475569;font-size:1.2rem;">&#128230;</div>'}
                <div>
                    <div class="lifecycle-card-title">${title}</div>
                    <div class="lifecycle-card-meta">
                        ${tier ? `<span style="color:${tierColor};font-weight:600;">${tier}</span>` : ''}
                        ${style ? ` &middot; ${style}` : ''}
                    </div>
                </div>
            </div>
            <div class="lifecycle-card-stats">
                <div class="lifecycle-stat">
                    <div class="lifecycle-stat-value">${fmtWan(totalGsv)}</div>
                    <div class="lifecycle-stat-label">累计GSV</div>
                </div>
                <div class="lifecycle-stat">
                    <div class="lifecycle-stat-value">${activeMonths}</div>
                    <div class="lifecycle-stat-label">活跃月数</div>
                </div>
                <div class="lifecycle-stat">
                    <div class="lifecycle-stat-value" style="font-size:0.85rem;">${firstMonth}~${lastMonth}</div>
                    <div class="lifecycle-stat-label">周期</div>
                </div>
            </div>
        </div>`;
    }).join('');
}

function debounceLifecycleSearch() {
    if (_lifecycleSearchTimer) clearTimeout(_lifecycleSearchTimer);
    _lifecycleSearchTimer = setTimeout(() => {
        loadLifecycleData();
    }, 300);
}

async function showLifecycleDetail(product_id) {
    const grid = document.getElementById('lifecycleGrid');
    const detail = document.getElementById('lifecycleDetail');

    if (!grid || !detail) return;

    grid.style.display = 'none';
    detail.style.display = '';

    const infoEl = document.getElementById('lifecycleDetailInfo');
    infoEl.innerHTML = '<div class="loading-placeholder">加载中...</div>';

    const data = await apiFetch(`/api/lifecycle?product_id=${product_id}`);
    if (!data || !Array.isArray(data) || data.length === 0) {
        infoEl.innerHTML = '<div style="color:#64748B;">无数据</div>';
        return;
    }

    const p = data[0];
    const img = p.image_url || '';
    const title = escapeHtml(p.title || '--');
    const tier = escapeHtml(p.tier || '');
    const style = escapeHtml(p.style || '');

    infoEl.innerHTML = `<div style="display:flex;align-items:center;gap:12px;">
        ${img ? `<img src="${img}" style="width:48px;height:48px;border-radius:8px;object-fit:cover;background:#1E293B;">` : ''}
        <div>
            <div style="font-size:1rem;font-weight:600;color:#F1F5F9;">${title}</div>
            <div style="font-size:0.8rem;color:#64748B;">${tier} &middot; ${style} &middot; ${data.length}个月数据</div>
        </div>
    </div>`;

    renderLifecycleChart(data);
    renderLifecycleMetrics(data);
}

function closeLifecycleDetail() {
    const grid = document.getElementById('lifecycleGrid');
    const detail = document.getElementById('lifecycleDetail');
    if (grid) grid.style.display = '';
    if (detail) detail.style.display = 'none';
}

function renderLifecycleChart(data) {
    const chart = getChart('chartLifecycle');
    const months = data.map(d => d.month);
    const gsvValues = data.map(d => d.gsv || 0);
    const qtyValues = data.map(d => d.payment_qty || 0);
    const refundValues = data.map(d => d.refund_amount || 0);

    const opt = baseOption();
    opt.tooltip.trigger = 'axis';
    opt.tooltip.formatter = function(params) {
        let tip = `<div style="font-weight:600;margin-bottom:6px;">${params[0].axisValue}</div>`;
        params.forEach(p => {
            const val = p.seriesName === 'GSV' ? fmtWan(p.value) : fmtNum(p.value);
            tip += `<div style="display:flex;align-items:center;gap:6px;margin:2px 0;">
                <span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${p.color};"></span>
                ${p.seriesName}: <strong>${val}</strong>
            </div>`;
        });
        return tip;
    };
    opt.legend = {
        data: ['GSV', '销量', '退款额'],
        top: 0,
        textStyle: { color: '#94A3B8' },
    };
    opt.grid = { left: 60, right: 60, top: 40, bottom: 30 };
    opt.xAxis.data = months;
    opt.yAxis = [
        {
            type: 'value',
            name: '金额',
            axisLine: { lineStyle: { color: '#334155' } },
            axisLabel: { color: '#94A3B8', formatter: v => (v / 10000).toFixed(0) + '万' },
            splitLine: { lineStyle: { color: '#1E293B', type: 'dashed' } },
        },
        {
            type: 'value',
            name: '件数',
            axisLine: { lineStyle: { color: '#334155' } },
            axisLabel: { color: '#94A3B8' },
            splitLine: { show: false },
        },
    ];
    opt.series = [
        {
            name: 'GSV',
            type: 'line',
            data: gsvValues,
            smooth: true,
            symbol: 'circle',
            symbolSize: 6,
            lineStyle: { width: 3, color: '#3B82F6' },
            itemStyle: { color: '#3B82F6' },
            areaStyle: {
                color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                    { offset: 0, color: 'rgba(59,130,246,0.3)' },
                    { offset: 1, color: 'rgba(59,130,246,0.02)' },
                ]),
            },
        },
        {
            name: '销量',
            type: 'bar',
            yAxisIndex: 1,
            data: qtyValues,
            barWidth: '30%',
            itemStyle: { color: 'rgba(16,185,129,0.6)', borderRadius: [4, 4, 0, 0] },
        },
        {
            name: '退款额',
            type: 'line',
            data: refundValues,
            smooth: true,
            symbol: 'diamond',
            symbolSize: 6,
            lineStyle: { width: 2, color: '#EF4444', type: 'dashed' },
            itemStyle: { color: '#EF4444' },
        },
    ];

    chart.setOption(opt, true);
    addChartSaveBtn(chart, 'chartLifecycle');
}

function renderLifecycleMetrics(data) {
    const el = document.getElementById('lifecycleMetrics');
    if (!el || !data || data.length === 0) return;

    // 计算汇总指标
    const totalGsv = data.reduce((s, d) => s + (d.gsv || 0), 0);
    const totalQty = data.reduce((s, d) => s + (d.payment_qty || 0), 0);
    const totalRefund = data.reduce((s, d) => s + (d.refund_amount || 0), 0);
    const totalAdSpend = data.reduce((s, d) => s + (d.ad_spend || 0), 0);
    const totalVisitors = data.reduce((s, d) => s + (d.visitors || 0), 0);
    const avgConversion = data.reduce((s, d) => s + (d.payment_conversion || 0), 0) / data.length;
    const avgRoi = data.reduce((s, d) => s + (d.ad_roi || 0), 0) / data.length;
    const refundRate = totalGsv > 0 ? totalRefund / totalGsv : 0;

    const metrics = [
        { label: '累计GSV', value: fmtWan(totalGsv) },
        { label: '累计销量', value: fmtNum(totalQty) + '件' },
        { label: '退款率', value: fmtPct(refundRate) },
        { label: '平均转化率', value: fmtPct(avgConversion) },
        { label: '累计访客', value: fmtNum(totalVisitors) },
        { label: '累计推广费', value: fmtWan(totalAdSpend) },
        { label: '平均ROI', value: avgRoi.toFixed(2) },
        { label: '数据月数', value: data.length + '个月' },
    ];

    el.innerHTML = metrics.map(m => `
        <div class="lifecycle-metric">
            <div class="lifecycle-metric-value">${m.value}</div>
            <div class="lifecycle-metric-label">${m.label}</div>
        </div>
    `).join('');
}
