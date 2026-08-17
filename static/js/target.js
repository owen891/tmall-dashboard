/* ================================================================
   模块: 目标完成进度
================================================================ */
async function loadTargetProgress(period) {
    const dim = STATE.dim || 'monthly';

    // 隐藏加载占位符
    const targetLoading = document.getElementById('targetLoading');
    if (targetLoading) targetLoading.style.display = 'none';

    const data = await apiFetch(`/api/target_progress?dim=${dim}&period=${period}`);
    const placeholder = document.getElementById('noTargetPlaceholder');
    const cardRow = document.getElementById('progressCardRow');
    const predictRow = document.querySelector('.predict-alert-row');

    // 后端返回 {target: {target_gsv, target_ad_spend, target_ad_ratio}, actual: {gsv, ad_spend, ...}, ...}
    const target = data && data.target ? data.target : null;
    const actual = data && data.actual ? data.actual : {};

    // 无目标数据时显示占位提示
    if (!target || !target.target_gsv || target.target_gsv === 0) {
        if (placeholder) placeholder.style.display = 'block';
        if (cardRow) cardRow.style.display = 'none';
        if (predictRow) predictRow.style.display = 'none';
        return;
    }

    if (placeholder) placeholder.style.display = 'none';
    if (cardRow) cardRow.style.display = '';
    if (predictRow) predictRow.style.display = '';

    const gsvActual = actual.gsv || 0;
    const gsvTarget = target.target_gsv || 0;
    const gsvPct = gsvTarget > 0 ? Math.min((gsvActual / gsvTarget) * 100, 100) : 0;

    const budgetActual = actual.ad_spend || 0;
    const budgetTarget = target.target_ad_spend || 0;
    const budgetPct = budgetTarget > 0 ? Math.min((budgetActual / budgetTarget) * 100, 100) : 0;

    const actualFeeRatio = data.actual_ad_ratio || 0;
    const targetFeeRatio = target.target_ad_ratio || 0;

    // --- GSV 环形进度图 ---
    const gsvChart = getChart('gaugeGSV');
    gsvChart.setOption({
        backgroundColor: 'transparent',
        series: [{
            type: 'gauge',
            startAngle: 90,
            endAngle: -270,
            pointer: { show: false },
            progress: {
                show: true,
                overlap: false,
                roundCap: true,
                clip: false,
                itemStyle: {
                    color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
                        { offset: 0, color: '#10B981' },
                        { offset: 1, color: '#3B82F6' },
                    ]),
                },
            },
            axisLine: {
                lineStyle: {
                    width: 12,
                    color: [[1, '#334155']],
                },
            },
            splitLine: { show: false },
            axisTick: { show: false },
            axisLabel: { show: false },
            data: [{ value: gsvPct.toFixed(1), name: '' }],
            detail: {
                fontSize: 28,
                fontWeight: 700,
                color: '#F1F5F9',
                offsetCenter: [0, 0],
                formatter: '{value}%',
            },
            title: { show: false },
        }],
    }, true);

    document.getElementById('gsvDetail').textContent =
        `已完成 ${fmtWan(gsvActual)} / 目标 ${fmtWan(gsvTarget)}`;

    // --- 费用预算环形进度图 ---
    const budgetChart = getChart('gaugeBudget');
    const budgetColor = budgetPct > 90 ? '#EF4444' : budgetPct > 70 ? '#F59E0B' : '#10B981';
    budgetChart.setOption({
        backgroundColor: 'transparent',
        series: [{
            type: 'gauge',
            startAngle: 90,
            endAngle: -270,
            pointer: { show: false },
            progress: {
                show: true,
                overlap: false,
                roundCap: true,
                clip: false,
                itemStyle: { color: budgetColor },
            },
            axisLine: {
                lineStyle: {
                    width: 12,
                    color: [[1, '#334155']],
                },
            },
            splitLine: { show: false },
            axisTick: { show: false },
            axisLabel: { show: false },
            data: [{ value: budgetPct.toFixed(1), name: '' }],
            detail: {
                fontSize: 28,
                fontWeight: 700,
                color: '#F1F5F9',
                offsetCenter: [0, 0],
                formatter: '{value}%',
            },
            title: { show: false },
        }],
    }, true);

    document.getElementById('budgetDetail').textContent =
        `已花费 ${fmtWan(budgetActual)} / 预算 ${fmtWan(budgetTarget)}`;

    // --- 费比仪表盘 ---
    const feeChart = getChart('gaugeFeeRatio');
    const feeMax = Math.max(actualFeeRatio * 1.5, targetFeeRatio * 1.5, 0.5);
    feeChart.setOption({
        backgroundColor: 'transparent',
        graphic: [{
            type: 'text',
            left: 'center',
            bottom: 10,
            style: {
                text: '目标 ' + (targetFeeRatio * 100).toFixed(1) + '%',
                fill: '#3B82F6',
                fontSize: 11,
            },
        }],
        series: [{
            type: 'gauge',
            startAngle: 200,
            endAngle: -20,
            min: 0,
            max: feeMax,
            pointer: {
                icon: 'path://M12.8,0.7l12,40.1H0.7L12.8,0.7z',
                length: '55%',
                width: 8,
                offsetCenter: [0, '-10%'],
                itemStyle: { color: '#F59E0B' },
            },
            axisLine: {
                lineStyle: {
                    width: 12,
                    color: [
                        [0.3, '#10B981'],
                        [0.7, '#F59E0B'],
                        [1, '#EF4444'],
                    ],
                },
            },
            splitLine: { show: false },
            axisTick: { show: false },
            axisLabel: {
                color: '#94A3B8',
                fontSize: 10,
                distance: -40,
                formatter: v => (v * 100).toFixed(0) + '%',
            },
            data: [{ value: actualFeeRatio, name: '' }],
            detail: {
                fontSize: 20,
                fontWeight: 700,
                color: actualFeeRatio > targetFeeRatio ? '#EF4444' : '#10B981',
                offsetCenter: [0, '30%'],
                formatter: (v) => (v * 100).toFixed(1) + '%',
            },
            title: { show: false },
        }],
    }, true);

    document.getElementById('feeRatioDetail').textContent =
        `实际 ${(actualFeeRatio * 100).toFixed(1)}% / 目标 ${(targetFeeRatio * 100).toFixed(1)}%`;

    // --- 时间进度 ---
    const timePct = (data.time_progress || 0) / 100;
    document.getElementById('timeProgressPct').textContent = (timePct * 100).toFixed(0) + '%';
    document.getElementById('timeProgressBar').style.width = (timePct * 100).toFixed(1) + '%';

    // --- 智能预测 ---
    const predictedGSV = data.gsv_forecast || 0;
    const gap = data.forecast_gap || 0;
    const isOnTrack = gap >= 0;

    const predictValueEl = document.getElementById('predictValue');
    const forecastLabel = data.forecast_label || '预计月底GSV';
    predictValueEl.textContent = `${forecastLabel} ${fmtWan(predictedGSV)}`;
    predictValueEl.className = 'predict-value ' + (isOnTrack ? 'on-track' : 'off-track');

    const predictGapEl = document.getElementById('predictGap');
    if (gap >= 0) {
        predictGapEl.textContent = `超额 ${fmtWan(gap)}`;
        predictGapEl.className = 'predict-gap positive';
    } else {
        predictGapEl.textContent = `缺口 ${fmtWan(Math.abs(gap))}`;
        predictGapEl.className = 'predict-gap negative';
    }
}

/* ================================================================
   模块: 预警通知列表
================================================================ */
async function loadAlerts(period) {
    const dim = STATE.dim || 'monthly';
    const data = await apiFetch(`/api/alerts?dim=${dim}&period=${period}`);
    const listBody = document.getElementById('alertListBody');
    const countEl = document.getElementById('alertCount');

    // 后端返回原始数组 [{alert_date, alert_type, severity, title, detail, ...}, ...]
    if (!data || !Array.isArray(data) || data.length === 0) {
        listBody.innerHTML = '<div style="text-align:center;color:#64748B;padding:20px;">暂无预警</div>';
        if (countEl) countEl.textContent = '';
        return;
    }

    if (countEl) countEl.textContent = `${data.length} 条`;

    const severityIcons = {
        critical: '\u{1F534}',
        high: '\u{1F7E0}',
        warning: '\u{1F7E1}',
    };

    listBody.innerHTML = data.map((a, idx) => {
        const cls = a.severity || 'warning';
        const icon = severityIcons[cls] || '\u26A0\uFE0F';
        return `<div class="alert-entry ${cls}" data-id="${a.id}" data-idx="${idx}">
            <span class="alert-icon">${icon}</span>
            <div class="alert-content">
                <div class="alert-title">${a.title || '预警'}</div>
                <div class="alert-detail">${a.detail || ''}</div>
            </div>
            <button class="alert-close" onclick="dismissAlert(this)" title="关闭">&times;</button>
        </div>`;
    }).join('');
}

function dismissAlert(btn) {
    const entry = btn.closest('.alert-entry');
    if (entry) {
        const alertId = entry.dataset.id;
        if (alertId) {
            fetch(`/api/alerts/${alertId}/dismiss`, { method: 'POST' }).catch(() => {});
        }
        entry.style.transition = 'opacity 0.3s, max-height 0.3s';
        entry.style.opacity = '0';
        entry.style.maxHeight = '0';
        entry.style.overflow = 'hidden';
        entry.style.marginBottom = '0';
        entry.style.padding = '0';
        setTimeout(() => entry.remove(), 300);
    }
    // 更新计数
    const remaining = document.querySelectorAll('#alertListBody .alert-entry').length;
    const countEl = document.getElementById('alertCount');
    if (countEl) countEl.textContent = remaining > 0 ? `${remaining} 条` : '';
    if (remaining === 0) {
        document.getElementById('alertListBody').innerHTML =
            '<div style="text-align:center;color:#64748B;padding:20px;">暂无预警</div>';
    }
}
