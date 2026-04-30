/* ================================================================
   周期对比分析模块 (Tab 版本)
================================================================ */

function initCompareTab() {
    if (!STATE.periods || STATE.periods.length === 0) return;
    const selA = document.getElementById('comparePeriodA');
    const selB = document.getElementById('comparePeriodB');
    if (!selA || !selB) return;
    selA.innerHTML = '';
    selB.innerHTML = '';
    STATE.periods.forEach(p => {
        const optA = document.createElement('option');
        optA.value = p; optA.textContent = p;
        selA.appendChild(optA);
        const optB = document.createElement('option');
        optB.value = p; optB.textContent = p;
        selB.appendChild(optB);
    });
    // 默认选中：A = 最新周期，B = 上一周期
    if (STATE.period) {
        selA.value = STATE.period;
    } else if (STATE.periods.length > 0) {
        selA.value = STATE.periods[0];
    }
    if (STATE.prevPeriod) {
        selB.value = STATE.prevPeriod;
    } else if (STATE.periods.length > 1) {
        selB.value = STATE.periods[1];
    }
    // 显示空状态
    const emptyEl = document.getElementById('emptyCompare');
    const resultsEl = document.getElementById('compareResults');
    if (emptyEl) emptyEl.style.display = 'flex';
    if (resultsEl) resultsEl.style.display = 'none';

    // 初始化多周期趋势叠加
    initMultiTrendSection();
}

async function runComparison() {
    const periodA = document.getElementById('comparePeriodA').value;
    const periodB = document.getElementById('comparePeriodB').value;
    if (!periodA || !periodB) {
        showToast('请选择两个周期', 'error');
        return;
    }
    if (periodA === periodB) {
        showToast('请选择不同的周期', 'error');
        return;
    }

    const emptyEl = document.getElementById('emptyCompare');
    const resultsEl = document.getElementById('compareResults');
    if (emptyEl) emptyEl.style.display = 'none';
    if (resultsEl) {
        resultsEl.style.display = 'flex';
        resultsEl.innerHTML = '<div style="text-align:center;color:#64748B;padding:40px;">加载中...</div>';
    }

    const data = await apiFetch(`/api/compare?dim=${STATE.dim}&period_a=${periodA}&period_b=${periodB}`);
    if (!data || data.error) {
        if (resultsEl) resultsEl.innerHTML = '<div style="text-align:center;color:#EF4444;padding:40px;">加载失败</div>';
        return;
    }

    renderCompareResults(data);
}

function renderCompareResults(data) {
    const { period_a, period_b, kpi_compare, product_changes } = data;

    // 清除旧的 ECharts 实例，避免 DOM 重建后引用失效
    if (CHARTS['chartCompareTrend']) {
        CHARTS['chartCompareTrend'].dispose();
        delete CHARTS['chartCompareTrend'];
    }

    // 重建结果区域结构
    const resultsEl = document.getElementById('compareResults');
    if (!resultsEl) return;
    resultsEl.style.display = 'flex';
    resultsEl.innerHTML = `
        <div class="compare-section">
            <h3 class="compare-section-title">KPI 对比</h3>
            <div class="compare-table-wrap">
                <table class="compare-table" id="compareKPITable">
                    <thead><tr><th>指标</th><th>${period_a}</th><th>${period_b}</th><th>变化</th></tr></thead>
                    <tbody></tbody>
                </table>
            </div>
        </div>
        <div class="compare-section">
            <h3 class="compare-section-title">商品排名变化</h3>
            <div id="compareProductChanges"></div>
        </div>
        <div class="compare-section">
            <h3 class="compare-section-title">趋势对比</h3>
            <div class="chart-box" id="chartCompareTrend"></div>
        </div>
    `;

    // 填充 KPI 对比表格
    const kpiBody = document.querySelector('#compareKPITable tbody');
    if (kpiBody) {
        const metricLabels = {
            'gmv': '总GMV', 'net_sales': '净销售额', 'visitors': '总访客',
            'aov': '客单价', 'ad_spend': '推广花费', 'roi': '综合ROI',
            'conversion': '转化率', 'refund_rate': '退款率',
        };

        for (const [key, label] of Object.entries(metricLabels)) {
            const kpi = kpi_compare[key];
            if (!kpi) continue;

            let valA, valB;
            if (key === 'conversion' || key === 'refund_rate') {
                valA = (kpi.period_a * 100).toFixed(1) + '%';
                valB = (kpi.period_b * 100).toFixed(1) + '%';
            } else if (key === 'roi') {
                valA = kpi.period_a.toFixed(2);
                valB = kpi.period_b.toFixed(2);
            } else {
                valA = fmtWan(kpi.period_a);
                valB = fmtWan(kpi.period_b);
            }

            const change = kpi.change_pct;
            let changeClass = 'change-flat';
            let changeText = '--';
            if (change !== null && change !== undefined) {
                if (key === 'refund_rate' || key === 'ad_spend') {
                    changeClass = change < 0 ? 'change-up' : change > 0 ? 'change-down' : 'change-flat';
                } else {
                    changeClass = change > 0 ? 'change-up' : change < 0 ? 'change-down' : 'change-flat';
                }
                changeText = (change > 0 ? '+' : '') + change + '%';
            }

            const tr = document.createElement('tr');
            tr.innerHTML = `<td>${label}</td><td>${valA}</td><td>${valB}</td><td class="${changeClass}">${changeText}</td>`;
            kpiBody.appendChild(tr);
        }
    }

    // 填充商品排名变化
    const productEl = document.getElementById('compareProductChanges');
    if (productEl) {
        if (product_changes && product_changes.length > 0) {
            let html = '<table class="compare-table"><thead><tr>';
            html += '<th>商品</th>';
            html += `<th>排名(${period_a})</th>`;
            html += `<th>排名(${period_b})</th>`;
            html += '<th>变化</th>';
            html += `<th>销售额(${period_a})</th>`;
            html += `<th>销售额(${period_b})</th>`;
            html += '</tr></thead><tbody>';

            product_changes.forEach(p => {
                let statusText = '';
                let statusClass = 'change-flat';
                if (p.status === 'up') {
                    statusText = `+${p.rank_diff}`;
                    statusClass = 'change-up';
                } else if (p.status === 'down') {
                    statusText = `${p.rank_diff}`;
                    statusClass = 'change-down';
                } else if (p.status === 'new') {
                    statusText = 'NEW';
                    statusClass = 'change-up';
                } else if (p.status === 'exit') {
                    statusText = 'EXIT';
                    statusClass = 'change-down';
                } else {
                    statusText = '--';
                }

                html += `<tr>`;
                html += `<td style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${escapeHtml(p.title || '--')}</td>`;
                html += `<td>${p.rank_a != null ? p.rank_a : '--'}</td>`;
                html += `<td>${p.rank_b != null ? p.rank_b : '--'}</td>`;
                html += `<td class="${statusClass}" style="font-weight:600;">${statusText}</td>`;
                html += `<td>${fmtWan(p.amount_a)}</td>`;
                html += `<td>${fmtWan(p.amount_b)}</td>`;
                html += `</tr>`;
            });

            html += '</tbody></table>';
            productEl.innerHTML = html;
        } else {
            productEl.innerHTML = '<div style="text-align:center;color:#64748B;padding:20px;">暂无商品排名变化数据</div>';
        }
    }

    // 渲染趋势对比图表
    renderCompareTrendChart(data);
}

function renderCompareTrendChart(data) {
    const chartEl = document.getElementById('chartCompareTrend');
    if (!chartEl) return;

    const chart = getChart('chartCompareTrend');
    if (!chart) return;

    const trend = data.trend_compare;
    if (!trend || !trend.labels || trend.labels.length === 0) {
        chartEl.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:#64748B;font-size:0.85rem;">暂无趋势数据</div>';
        return;
    }

    const option = {
        ...baseOption(),
        legend: {
            ...baseOption().legend,
            data: [data.period_a, data.period_b],
            top: 5,
        },
        tooltip: {
            ...baseOption().tooltip,
            trigger: 'axis',
        },
        xAxis: {
            ...baseOption().xAxis,
            type: 'category',
            data: trend.labels,
        },
        yAxis: {
            ...baseOption().yAxis,
            type: 'value',
        },
        series: [
            {
                name: data.period_a,
                type: 'line',
                data: trend.series_a || [],
                smooth: true,
                lineStyle: { color: '#3B82F6', width: 2 },
                itemStyle: { color: '#3B82F6' },
                areaStyle: { color: 'rgba(59,130,246,0.1)' },
            },
            {
                name: data.period_b,
                type: 'line',
                data: trend.series_b || [],
                smooth: true,
                lineStyle: { color: '#F59E0B', width: 2 },
                itemStyle: { color: '#F59E0B' },
                areaStyle: { color: 'rgba(245,158,11,0.1)' },
            },
        ],
    };

    chart.setOption(option, true);
    addChartSaveBtn(chart, 'chartCompareTrend');
    chart.resize();
}

/* ================================================================
   多周期趋势叠加
================================================================ */
function initMultiTrendSection() {
    if (!STATE.periods || STATE.periods.length === 0) return;

    // 填充周期复选框（最近6个月）
    const container = document.getElementById('multiTrendPeriods');
    if (!container) return;
    container.innerHTML = '';

    const recentPeriods = STATE.periods.slice(0, 6);
    recentPeriods.forEach(p => {
        const label = document.createElement('label');
        label.className = 'period-tag';
        label.innerHTML = `<input type="checkbox" value="${p}" onchange="updateMultiTrendSelection()"> ${p}`;
        container.appendChild(label);
    });
}

function updateMultiTrendSelection() {
    // 更新已选标签样式
    document.querySelectorAll('#multiTrendPeriods .period-tag').forEach(tag => {
        const cb = tag.querySelector('input[type="checkbox"]');
        tag.classList.toggle('selected', cb.checked);
    });
}

async function loadMultiTrend() {
    const checkboxes = document.querySelectorAll('#multiTrendPeriods input[type="checkbox"]:checked');
    const periods = Array.from(checkboxes).map(cb => cb.value);
    const metric = document.getElementById('multiTrendMetric').value;

    if (periods.length === 0) {
        showToast('请至少选择一个周期', 'warning');
        return;
    }

    const chartEl = document.getElementById('chartMultiTrend');
    if (!chartEl) return;
    chartEl.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:#64748B;font-size:0.85rem;">加载中...</div>';

    const data = await apiFetch(`/api/multi_trend?dim=${STATE.dim}&periods=${periods.join(',')}&metric=${metric}`);
    if (!data || !data.periods || data.periods.length === 0) {
        chartEl.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:#64748B;font-size:0.85rem;">暂无数据</div>';
        return;
    }

    // 颜色列表
    const colors = ['#3B82F6', '#F59E0B', '#10B981', '#EF4444', '#8B5CF6', '#EC4899'];
    const metricLabels = {
        'payment_amount': 'GMV',
        'visitors': '访客数',
        'conversion': '转化率',
        'refund_rate': '退款率',
    };

    // 收集所有日期标签（取最长的那组）
    let allDates = [];
    data.periods.forEach(p => {
        if (p.data.length > allDates.length) {
            allDates = p.data.map(d => d.date);
        }
    });

    const series = data.periods.map((p, i) => ({
        name: p.period,
        type: 'line',
        data: p.data.map(d => d.value),
        smooth: true,
        lineStyle: { color: colors[i % colors.length], width: 2 },
        itemStyle: { color: colors[i % colors.length] },
        symbol: 'circle',
        symbolSize: 6,
    }));

    const option = {
        ...baseOption(),
        legend: {
            ...baseOption().legend,
            data: data.periods.map(p => p.period),
            top: 5,
        },
        tooltip: {
            ...baseOption().tooltip,
            trigger: 'axis',
        },
        title: {
            text: `${metricLabels[metric] || metric} - 多周期趋势叠加`,
            left: 'center',
            textStyle: { color: baseOption().title.textStyle.color, fontSize: 14 },
        },
        xAxis: {
            ...baseOption().xAxis,
            type: 'category',
            data: allDates,
        },
        yAxis: {
            ...baseOption().yAxis,
            type: 'value',
            name: metricLabels[metric] || metric,
        },
        series: series,
    };

    const chart = getChart('chartMultiTrend');
    if (!chart) return;
    chart.setOption(option, true);
    chart.resize();
}
