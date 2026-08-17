/* ================================================================
   模块1: KPI 卡片
================================================================ */

/* ---------- KPI 自定义看板：localStorage 存储 ---------- */
const DEFAULT_KPI_ORDER = ['gmv','net_sales','visitors','conv_rate','ad_cost','roi','refund_rate','aov'];
const KPI_LABELS = {
    gmv: '总销售额', net_sales: '净销售额', visitors: '总访客',
    conv_rate: '整体转化率', ad_cost: '推广花费', roi: '综合ROI',
    refund_rate: '退款率', aov: '客单价'
};

function getKPIOrder() {
    try { return JSON.parse(localStorage.getItem('kpi_order')) || DEFAULT_KPI_ORDER; }
    catch { return DEFAULT_KPI_ORDER; }
}
function setKPIOrder(order) {
    localStorage.setItem('kpi_order', JSON.stringify(order));
}

/* ---------- KPI 自定义面板 UI ---------- */
function toggleKPICustomize() {
    const panel = document.getElementById('kpiCustomizePanel');
    if (!panel) return;
    const isVisible = panel.style.display !== 'none';
    panel.style.display = isVisible ? 'none' : 'block';
    if (!isVisible) renderKPICustomizePanel();
}

function renderKPICustomizePanel() {
    const panel = document.getElementById('kpiCustomizePanel');
    if (!panel) return;
    const order = getKPIOrder();
    panel.innerHTML = `
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
            <span style="font-size:0.9rem;font-weight:600;color:var(--text-primary);">自定义KPI卡片</span>
            <button onclick="toggleKPICustomize()" style="background:none;border:none;color:var(--text-muted);cursor:pointer;font-size:1rem;">&times;</button>
        </div>
        <div id="kpiCustomizeList">
            ${order.map((key, idx) => `
                <div class="kpi-customize-item" data-key="${key}">
                    <div class="move-btns">
                        <button class="move-btn" onclick="moveKPI('${key}',-1)" title="上移" ${idx === 0 ? 'disabled' : ''}>&#9650;</button>
                        <button class="move-btn" onclick="moveKPI('${key}',1)" title="下移" ${idx === order.length - 1 ? 'disabled' : ''}>&#9660;</button>
                    </div>
                    <label>
                        <input type="checkbox" checked onchange="toggleKPIVisibility('${key}', this.checked)" style="margin-right:6px;accent-color:var(--accent);">
                        ${KPI_LABELS[key] || key}
                    </label>
                </div>
            `).join('')}
        </div>
        <div style="margin-top:12px;display:flex;gap:8px;justify-content:flex-end;">
            <button onclick="resetKPIOrder()" style="padding:6px 14px;border-radius:6px;border:1px solid var(--border);background:transparent;color:var(--text-secondary);cursor:pointer;font-size:0.82rem;">恢复默认</button>
            <button onclick="saveKPIOrder()" style="padding:6px 14px;border-radius:6px;border:none;background:var(--accent);color:#fff;cursor:pointer;font-size:0.82rem;">保存</button>
        </div>
    `;
}

function moveKPI(key, direction) {
    const order = getKPIOrder();
    const idx = order.indexOf(key);
    if (idx < 0) return;
    const newIdx = idx + direction;
    if (newIdx < 0 || newIdx >= order.length) return;
    [order[idx], order[newIdx]] = [order[newIdx], order[idx]];
    setKPIOrder(order);
    renderKPICustomizePanel();
}

function toggleKPIVisibility(key, visible) {
    const order = getKPIOrder();
    if (visible && !order.includes(key)) {
        order.push(key);
    } else if (!visible) {
        const idx = order.indexOf(key);
        if (idx >= 0) order.splice(idx, 1);
    }
    setKPIOrder(order);
}

function saveKPIOrder() {
    // order is already saved in localStorage via moveKPI/toggleKPIVisibility
    showToast('KPI配置已保存', 'success');
    toggleKPICustomize();
    // 重新渲染KPI卡片
    if (STATE.period) {
        loadKPI(STATE.dim, STATE.period, STATE.prevPeriod);
    }
}

function resetKPIOrder() {
    localStorage.removeItem('kpi_order');
    renderKPICustomizePanel();
    showToast('已恢复默认KPI配置', 'info');
}

/* ---------- 修改 loadKPI 以支持自定义顺序和隐藏 ---------- */
async function loadKPI(dim, period, prevPeriod) {
    const data = await apiFetch(`/api/kpi?dim=${dim}&period=${period}&prev_period=${prevPeriod}`);
    if (!data) return;

    // 隐藏加载占位符和骨架屏
    const kpiLoading = document.getElementById('kpiLoading');
    if (kpiLoading) kpiLoading.style.display = 'none';
    const kpiSkeleton = document.getElementById('kpiSkeleton');
    if (kpiSkeleton) kpiSkeleton.style.display = 'none';

    // 后端返回 {current: {gmv, net_sales, visitors, ...}, previous: {...}, changes: {gmv: pct, ...}, anomalies: [...]}
    const current = data.current || {};
    const changes = data.changes || {};

    const kpiMap = {
        gmv:          { label: '总销售额',     fmt: v => fmtWan(v),     key: 'gmv' },
        net_sales:    { label: '净销售额',   fmt: v => fmtWan(v),     key: 'net_sales' },
        visitors:     { label: '总访客',     fmt: v => fmtNum(v),     key: 'visitors' },
        conv_rate:    { label: '整体转化率', fmt: v => fmtPct(v),     key: 'conversion' },
        ad_cost:      { label: '推广花费',   fmt: v => fmtWan(v),     key: 'ad_spend' },
        roi:          { label: '综合ROI',    fmt: v => v != null ? v.toFixed(2) : '--', key: 'roi' },
        refund_rate:  { label: '退款率',     fmt: v => fmtPct(v),     key: 'refund_rate' },
        aov:          { label: '客单价',     fmt: v => '¥' + (v || 0).toFixed(0), key: 'aov' },
    };

    // 先清除所有卡片的异常状态、警告图标和预警指示器
    Object.keys(kpiMap).forEach(key => {
        const cardEl = document.getElementById(`kpi-${key}`);
        if (cardEl) {
            cardEl.classList.remove('alert');
            // 移除已有的警告图标
            const existingIcon = cardEl.querySelector('.anomaly-icon');
            if (existingIcon) existingIcon.remove();
            // 移除已有的预警指示器
            const existingIndicator = cardEl.querySelector('.alert-indicator');
            if (existingIndicator) existingIndicator.remove();
        }
    });

    Object.keys(kpiMap).forEach(key => {
        const cfg = kpiMap[key];
        const val = current[cfg.key];
        const valEl = document.getElementById(`kpi-${key}-val`);
        const chgEl = document.getElementById(`kpi-${key}-chg`);
        const cardEl = document.getElementById(`kpi-${key}`);

        if (valEl) valEl.textContent = cfg.fmt(val);

        // 环比变化：后端 changes 里 key 与 kpiMap 的 key 对应
        const changeVal = changes[cfg.key];
        if (chgEl && changeVal != null) {
            // changes 里的值已经是百分比数值（如 -25.3 表示下降25.3%）
            const isUp = changeVal >= 0;
            const pct = Math.abs(changeVal).toFixed(1);
            // 退款率是"越低越好"的指标，下降是好事，颜色逻辑反转
            const isLowerBetter = (key === 'refund_rate');
            const colorClass = isLowerBetter
                ? (isUp ? 'down' : 'up')   // 退款率下降=绿色(好)，上升=红色(差)
                : (isUp ? 'up' : 'down');  // 其他指标上升=绿色(好)，下降=红色(差)
            chgEl.className = 'kpi-change ' + colorClass;
            chgEl.innerHTML = `<span class="arrow">${isUp ? '↑' : '↓'}</span> ${pct}%`;

            // 环比下降超过20%标红背景（退款率上升超过20%才标红，因为退款率上升是坏事）
            const alertThreshold = isLowerBetter ? 20 : -20;
            const shouldAlert = isLowerBetter ? (changeVal > alertThreshold) : (changeVal < alertThreshold);
            if (shouldAlert) {
                cardEl.classList.add('alert');
            }
        }
    });

    // 处理 anomalies 数组：标记异常卡片 + 渲染异常横幅
    const anomalies = data.anomalies || [];
    const bannerEl = document.getElementById('anomalyBanner');
    const bannerListEl = document.getElementById('anomalyBannerList');

    if (anomalies.length === 0) {
        bannerEl.classList.remove('show');
    } else {
        // 标记异常卡片：红色边框 + 警告图标
        anomalies.forEach(a => {
            const cardEl = document.getElementById(`kpi-${a.metric}`);
            if (cardEl) {
                cardEl.classList.add('alert');
                // 在 kpi-label 中添加警告图标
                const labelEl = cardEl.querySelector('.kpi-label');
                if (labelEl && !labelEl.querySelector('.anomaly-icon')) {
                    const icon = document.createElement('span');
                    icon.className = 'anomaly-icon';
                    icon.textContent = ' \u26A0\uFE0F';
                    icon.style.marginLeft = '4px';
                    labelEl.appendChild(icon);
                }
            }
        });

        // 渲染异常横幅
        bannerEl.classList.add('show');
        bannerListEl.innerHTML = anomalies.map(a => {
            const severityCls = a.severity === 'high' ? 'high' : 'warning';
            const changePct = a.change != null ? (a.change >= 0 ? '+' : '') + a.change.toFixed(1) + '%' : '--';
            const arrow = a.change < 0 ? '↓' : '↑';
            return `<span class="anomaly-tag ${severityCls}">
                ${a.label || a.metric}
                <span class="change-val">${arrow}${changePct}</span>
            </span>`;
        }).join('');
    }

    // 加载预警规则检查结果，在KPI卡片上显示预警指示器
    loadAlertIndicators(dim, period);

    // 按自定义顺序排列KPI卡片，隐藏被移除的卡片
    reorderKPICards();

    // 添加 KPI 卡片点击跳转
    setupKPIClickHandlers();
}

/* ---------- 按自定义顺序重排KPI卡片 DOM ---------- */
function reorderKPICards() {
    const grid = document.getElementById('kpiGrid');
    if (!grid) return;
    const order = getKPIOrder();
    // 先显示所有卡片
    order.forEach(key => {
        const card = document.getElementById(`kpi-${key}`);
        if (card) card.style.display = '';
    });
    // 隐藏不在 order 中的卡片
    const allKeys = DEFAULT_KPI_ORDER;
    allKeys.forEach(key => {
        if (!order.includes(key)) {
            const card = document.getElementById(`kpi-${key}`);
            if (card) card.style.display = 'none';
        }
    });
    // 按 order 顺序重排 DOM
    order.forEach(key => {
        const card = document.getElementById(`kpi-${key}`);
        if (card) grid.appendChild(card);
    });
}

/* ================================================================
   预警指示器
================================================================ */
async function loadAlertIndicators(dim, period) {
    try {
        const alerts = await apiFetch(`/api/alert_checks?dim=${dim}&period=${period}`);
        if (!alerts || !Array.isArray(alerts) || alerts.length === 0) return;

        // 指标名到KPI卡片ID的映射
        const metricToCard = {
            'gmv': 'gmv', 'net_sales': 'net_sales', 'visitors': 'visitors',
            'conversion': 'conv_rate', 'refund_rate': 'refund_rate',
            'roi': 'roi', 'ad_spend': 'ad_cost', 'aov': 'aov'
        };

        alerts.forEach(alert => {
            const cardId = metricToCard[alert.metric];
            if (!cardId) return;
            const cardEl = document.getElementById(`kpi-${cardId}`);
            if (!cardEl) return;
            // 避免重复添加
            if (cardEl.querySelector('.alert-indicator')) return;
            const indicator = document.createElement('span');
            indicator.className = `alert-indicator ${alert.level}`;
            indicator.title = `${alert.label} 触发预警: 当前值 ${alert.current_value} ${alert.operator} ${alert.threshold}`;
            cardEl.style.position = 'relative';
            cardEl.appendChild(indicator);
        });
    } catch (e) {
        // 静默失败
    }
}

/* ================================================================
   预警规则管理
================================================================ */
async function loadAlertRules() {
    const rules = await apiFetch('/api/alert_rules');
    if (!rules || !Array.isArray(rules)) return;
    const listEl = document.getElementById('alertRulesList');
    if (!listEl) return;
    if (rules.length === 0) {
        listEl.innerHTML = '<div style="color:var(--text-muted);font-size:0.82rem;padding:8px 0;">暂无预警规则</div>';
        return;
    }
    const opLabels = { 'gt': '>', 'lt': '<', 'gte': '>=', 'lte': '<=' };
    const levelLabels = { 'info': '提示', 'warning': '警告', 'danger': '危险' };
    const levelColors = { 'info': 'var(--accent)', 'warning': 'var(--warning)', 'danger': 'var(--danger)' };
    const metricLabels = {
        'gmv': '总销售额', 'net_sales': '净销售额', 'visitors': '总访客',
        'conversion': '转化率', 'refund_rate': '退款率', 'roi': 'ROI', 'ad_spend': '推广花费'
    };
    listEl.innerHTML = rules.map(r => `
        <div class="alert-rule-item">
            <span class="alert-rule-level" style="color:${levelColors[r.level] || 'var(--text-muted)'}">${levelLabels[r.level] || r.level}</span>
            <span class="alert-rule-text">${metricLabels[r.metric] || r.metric} ${opLabels[r.operator] || r.operator} ${r.threshold}</span>
            <span class="alert-rule-delete" onclick="deleteAlertRule(${r.id})" title="删除">&times;</span>
        </div>
    `).join('');
}

async function addAlertRule() {
    const metric = document.getElementById('alertRuleMetric').value;
    const operator = document.getElementById('alertRuleOperator').value;
    const threshold = parseFloat(document.getElementById('alertRuleThreshold').value);
    const level = document.getElementById('alertRuleLevel').value;
    if (!metric || !operator || isNaN(threshold)) {
        showToast('请填写完整的规则参数', 'error');
        return;
    }
    const res = await apiFetch('/api/alert_rules', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ metric, operator, threshold, level })
    });
    if (res && res.success) {
        showToast('规则已添加', 'success');
        document.getElementById('alertRuleThreshold').value = '';
        loadAlertRules();
        // 重新检查预警
        loadAlertIndicators(STATE.dim, STATE.period);
    } else {
        showToast('添加失败', 'error');
    }
}

async function deleteAlertRule(id) {
    const res = await apiFetch(`/api/alert_rules/${id}`, { method: 'DELETE' });
    if (res && res.success) {
        showToast('规则已删除', 'success');
        loadAlertRules();
        loadAlertIndicators(STATE.dim, STATE.period);
    }
}

function toggleAlertRulesPanel() {
    const panel = document.getElementById('alertRulesPanel');
    if (!panel) return;
    const isVisible = panel.style.display !== 'none';
    panel.style.display = isVisible ? 'none' : 'block';
    if (!isVisible) {
        loadAlertRules();
    }
}

/* ================================================================
   KPI 卡片点击下钻到商品运营Tab
================================================================ */
// KPI指标到商品排序字段的映射
const KPI_DRILL_MAP = {
    'gmv':         { sortKey: 'payment_amount',    sortOrder: 'desc' },
    'net_sales':   { sortKey: 'net_sales',         sortOrder: 'desc' },
    'visitors':    { sortKey: 'visitors',          sortOrder: 'desc' },
    'conv_rate':   { sortKey: 'payment_conversion', sortOrder: 'desc' },
    'ad_cost':     { sortKey: 'ad_spend',          sortOrder: 'desc' },
    'roi':         { sortKey: 'overall_roi',       sortOrder: 'desc' },
    'refund_rate': { sortKey: 'refund_rate',       sortOrder: 'desc' },
    'aov':         { sortKey: 'avg_order_value',   sortOrder: 'desc' },
};

function drillDown(metric) {
    const cfg = KPI_DRILL_MAP[metric];
    if (!cfg) return;
    // 设置排序
    STATE.sortKey = cfg.sortKey;
    STATE.sortOrder = cfg.sortOrder;
    STATE.page = 1;
    // 切换到商品运营Tab
    switchTab('tab-ops');
    // 重新加载商品表格
    if (typeof loadProducts === 'function') {
        loadProducts(STATE.dim, STATE.period);
    }
    // 显示联动提示
    const metricLabel = KPI_LABELS[metric] || metric;
    showToast('已按「' + metricLabel + '」降序排列商品', 'info');
}

function setupKPIClickHandlers() {
    document.querySelectorAll('.kpi-card').forEach(card => {
        card.style.cursor = 'pointer';
        // 移除旧的点击事件（通过克隆节点）
        const newCard = card.cloneNode(true);
        card.parentNode.replaceChild(newCard, card);
        newCard.addEventListener('click', () => {
            const metric = newCard.dataset.metric;
            if (metric) drillDown(metric);
        });
    });
}

/* ================================================================
   新老客分析
================================================================ */
async function loadCustomerAnalysis() {
    const data = await apiFetch(`/api/customer_analysis?dim=${STATE.dim}&period=${STATE.period}`);
    if (!data) return;

    // 填充统计卡片
    const newEl = document.getElementById('customerNewVal');
    const retEl = document.getElementById('customerReturnVal');
    if (newEl) newEl.textContent = fmtNum(data.new_buyers);
    if (retEl) retEl.textContent = fmtNum(data.returning_buyers);

    // 占比
    const newRatioEl = document.getElementById('customerNewRatio');
    const retRatioEl = document.getElementById('customerReturnRatio');
    if (newRatioEl) newRatioEl.textContent = '占比 ' + (data.new_ratio * 100).toFixed(1) + '%';
    if (retRatioEl) retRatioEl.textContent = '占比 ' + (data.returning_ratio * 100).toFixed(1) + '%';

    // 环比变化
    const newChgEl = document.getElementById('customerNewChg');
    const retChgEl = document.getElementById('customerReturnChg');
    if (newChgEl && data.prev_new_ratio != null) {
        const diff = (data.new_ratio - data.prev_new_ratio) * 100;
        const isUp = diff >= 0;
        newChgEl.className = 'customer-stat-change ' + (isUp ? 'up' : 'down');
        newChgEl.innerHTML = `<span class="arrow">${isUp ? '↑' : '↓'}</span> 环比 ${Math.abs(diff).toFixed(1)}%`;
    }
    if (retChgEl && data.prev_returning_ratio != null) {
        const diff = (data.returning_ratio - data.prev_returning_ratio) * 100;
        const isUp = diff >= 0;
        retChgEl.className = 'customer-stat-change ' + (isUp ? 'up' : 'down');
        retChgEl.innerHTML = `<span class="arrow">${isUp ? '↑' : '↓'}</span> 环比 ${Math.abs(diff).toFixed(1)}%`;
    }

    // 堆叠面积图
    const trend = data.trend || [];
    if (trend.length === 0) { showChartEmpty('chartCustomerTrend'); return; }

    const chart = getChart('chartCustomerTrend');
    const opt = baseOption();
    opt.tooltip.trigger = 'axis';
    opt.legend.data = ['新客', '老客'];
    opt.legend.top = 0;
    opt.xAxis.data = trend.map(t => t.period);
    opt.yAxis.name = '人数';
    opt.yAxis.nameTextStyle = { color: '#94A3B8' };
    opt.yAxis.axisLabel = { color: '#94A3B8', formatter: v => v >= 10000 ? (v / 10000).toFixed(0) + '万' : v };
    opt.series = [
        {
            name: '新客', type: 'line', stack: 'customer',
            data: trend.map(t => t.new_buyers),
            smooth: true, symbol: 'circle', symbolSize: 6,
            lineStyle: { width: 2, color: '#3B82F6' },
            itemStyle: { color: '#3B82F6' },
            areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                { offset: 0, color: 'rgba(59,130,246,0.4)' },
                { offset: 1, color: 'rgba(59,130,246,0.05)' },
            ])},
        },
        {
            name: '老客', type: 'line', stack: 'customer',
            data: trend.map(t => t.returning_buyers),
            smooth: true, symbol: 'circle', symbolSize: 6,
            lineStyle: { width: 2, color: '#F59E0B' },
            itemStyle: { color: '#F59E0B' },
            areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                { offset: 0, color: 'rgba(245,158,11,0.4)' },
                { offset: 1, color: 'rgba(245,158,11,0.05)' },
            ])},
        },
    ];
    chart.setOption(opt, true);
}

/* ================================================================
   加购→支付漏斗分析
================================================================ */
async function loadFunnelAnalysis() {
    const data = await apiFetch(`/api/funnel?dim=${STATE.dim}&period=${STATE.period}`);
    if (!data) return;

    const steps = data.steps || [];
    const prevSteps = data.prev_steps || [];

    if (steps.length === 0) {
        showChartEmpty('chartFunnel');
        document.getElementById('funnelRatesContent').innerHTML = '<div style="text-align:center;color:var(--text-muted);padding:20px;">暂无数据</div>';
        return;
    }

    // 漏斗图
    const chart = getChart('chartFunnel');
    const opt = baseOption();
    opt.tooltip.trigger = 'item';
    opt.tooltip.formatter = function(params) {
        return `${params.name}: ${fmtNum(params.value)}`;
    };
    opt.legend = { show: false };
    const colors = ['#6366F1', '#3B82F6', '#F59E0B', '#EC4899', '#10B981'];
    opt.series = [{
        type: 'funnel',
        left: '10%',
        top: 20,
        bottom: 20,
        width: '80%',
        sort: 'descending',
        gap: 4,
        label: {
            show: true,
            position: 'inside',
            formatter: function(params) {
                return params.name + '\n' + fmtNum(params.value);
            },
            color: '#fff',
            fontSize: 13,
        },
        itemStyle: {
            borderColor: 'transparent',
        },
        data: steps.map((s, i) => ({
            name: s.name,
            value: s.value,
            itemStyle: { color: colors[i] || colors[colors.length - 1] },
        })),
    }];
    chart.setOption(opt, true);

    // 步骤转化率条
    const contentEl = document.getElementById('funnelRatesContent');
    if (!contentEl) return;

    let html = '';
    for (let i = 1; i < steps.length; i++) {
        const rate = (steps[i].rate * 100).toFixed(1);
        const prevRate = prevSteps && prevSteps[i] && prevSteps[i].rate != null ? (prevSteps[i].rate * 100).toFixed(1) : null;
        const barWidth = Math.min(parseFloat(rate), 100);
        const barColor = barWidth >= 50 ? '#10B981' : barWidth >= 20 ? '#F59E0B' : '#EF4444';
        let changeHtml = '';
        if (prevRate !== null) {
            const diff = (parseFloat(rate) - parseFloat(prevRate)).toFixed(1);
            const isUp = diff >= 0;
            changeHtml = `<span class="funnel-rate-change ${isUp ? 'up' : 'down'}">${isUp ? '↑' : '↓'}${Math.abs(diff)}% 环比</span>`;
        }
        html += `
            <div class="funnel-rate-row">
                <div class="funnel-rate-label">${steps[i - 1].name} → ${steps[i].name}</div>
                <div class="funnel-rate-bar-track">
                    <div class="funnel-rate-bar-fill" style="width:${barWidth}%;background:${barColor};"></div>
                </div>
                <div class="funnel-rate-value">${rate}%</div>
                ${changeHtml}
            </div>
        `;
    }
    contentEl.innerHTML = html;
}
