/* ================================================================
   模块: 数据复盘 — 周/月核心指标环比同比分析
================================================================ */

// 格式化工具
function _rvFormat(val, format) {
    if (val === null || val === undefined) return '--';
    if (format === 'money') return '¥' + (val >= 10000 ? (val / 10000).toFixed(1) + '万' : val.toFixed(0));
    if (format === 'percent') return (val * 100).toFixed(2) + '%';
    if (format === 'decimal') return val.toFixed(2);
    if (format === 'number') return val >= 10000 ? (val / 10000).toFixed(1) + '万' : Math.round(val).toLocaleString();
    return val;
}

function _rvChangeTag(change, lowerBetter) {
    if (change === null || change === undefined) return '';
    const isGood = lowerBetter ? change < 0 : change > 0;
    const color = Math.abs(change) < 1 ? 'var(--text-secondary)' : (isGood ? 'var(--success)' : 'var(--danger)');
    const arrow = change > 0 ? '↑' : change < 0 ? '↓' : '→';
    return `<span style="color:${color};font-size:13px;font-weight:600">${arrow}${Math.abs(change)}%</span>`;
}

async function loadPostmortem(dim, period) {
    const container = document.getElementById('postmortemContainer');
    if (!container) return;
    container.innerHTML = '<div class="loading-placeholder">加载中...</div>';

    try {
        const data = await apiFetch(`/api/review?dim=${dim}&period=${period}`);
        if (!data || !data.metrics) {
            container.innerHTML = '<div class="empty-state">暂无复盘数据</div>';
            return;
        }

        renderPostmortemMetrics(data);
        renderPostmortemTrend(data);
    } catch (e) {
        container.innerHTML = `<div class="empty-state">加载失败: ${e.message}</div>`;
    }
}

function renderPostmortemMetrics(data) {
    const { metrics, prev_period, yoy_period, period, dim } = data;
    const container = document.getElementById('postmortemContainer');

    // Period labels
    const dimLabel = dim === 'monthly' ? '月' : dim === 'weekly' ? '周' : '日';
    const prevLabel = prev_period || '上' + dimLabel;
    const yoyLabel = yoy_period || '去年同' + dimLabel;

    let html = `
    <div class="pm-header">
        <h3>📊 ${dimLabel}度复盘</h3>
        <div class="pm-period-info">
            <span class="pm-current-period">当前: ${period}</span>
            ${prev_period ? `<span class="pm-prev-period">环比: ${prev_period}</span>` : ''}
            ${yoy_period ? `<span class="pm-yoy-period">同比: ${yoy_period}</span>` : ''}
        </div>
    </div>

    <div class="pm-table-wrapper">
    <table class="pm-table">
        <thead>
            <tr>
                <th>指标</th>
                <th>本期</th>
                <th>${prevLabel}</th>
                <th>环比</th>
                ${yoy_period ? `<th>${yoyLabel}</th><th>同比</th>` : ''}
            </tr>
        </thead>
        <tbody>`;

    for (const m of metrics) {
        const valStr = _rvFormat(m.value, m.format);
        const prevStr = _rvFormat(m.prev_value, m.format);
        const momTag = _rvChangeTag(m.mom_change, m.lower_better);
        const yoyStr = _rvFormat(m.yoy_value, m.format);
        const yoyTag = _rvChangeTag(m.yoy_change, m.lower_better);

        // Highlight significant changes
        const momHighlight = m.mom_change !== undefined && Math.abs(m.mom_change) >= 20;
        const yoyHighlight = m.yoy_change !== undefined && Math.abs(m.yoy_change) >= 20;

        html += `<tr class="${momHighlight ? 'pm-highlight' : ''}">
            <td class="pm-metric-name">${m.icon} ${m.label}</td>
            <td class="pm-value">${valStr}</td>
            <td class="pm-prev">${prevStr}</td>
            <td class="pm-change">${momTag}</td>
            ${yoy_period ? `
            <td class="pm-prev">${yoyStr}</td>
            <td class="pm-change">${yoyTag}</td>` : ''}
        </tr>`;
    }

    html += `</tbody></table></div>
    <div id="pmTrendChart" style="height:320px;margin-top:20px;"></div>`;

    container.innerHTML = html;
}

function renderPostmortemTrend(data) {
    const { trend } = data;
    const chart = getChart('pmTrendChart');
    if (!chart || !trend || trend.length === 0) return;

    const periods = trend.map(t => t.period);
    const gsvData = trend.map(t => t.gsv || 0);
    const adData = trend.map(t => t.ad_spend || 0);
    const convData = trend.map(t => (t.conversion || 0) * 100);

    chart.setOption({
        backgroundColor: 'transparent',
        tooltip: { trigger: 'axis' },
        legend: { data: ['总销售额', '推广花费', '转化率'], textStyle: { color: '#94A3B8' } },
        grid: { left: 60, right: 60, top: 40, bottom: 30 },
        xAxis: { type: 'category', data: periods, axisLabel: { color: '#94A3B8' } },
        yAxis: [
            { type: 'value', name: '金额', axisLabel: { color: '#94A3B8', formatter: v => (v/10000).toFixed(0)+'万' } },
            { type: 'value', name: '转化率%', axisLabel: { color: '#94A3B8', formatter: v => v.toFixed(1)+'%' } },
        ],
        series: [
            {
                name: '总销售额', type: 'bar', data: gsvData,
                itemStyle: { color: '#06B6D4', borderRadius: [4,4,0,0] },
            },
            {
                name: '推广花费', type: 'bar', data: adData,
                itemStyle: { color: '#F59E0B', borderRadius: [4,4,0,0] },
            },
            {
                name: '转化率', type: 'line', yAxisIndex: 1, data: convData,
                itemStyle: { color: '#10B981' },
                lineStyle: { width: 2 },
            },
        ],
    }, true);
}
