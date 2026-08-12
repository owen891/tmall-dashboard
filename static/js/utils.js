/* ================================================================
   全局状态
================================================================ */
const STATE = {
    dim: 'monthly',          // 当前维度
    period: '',              // 当前周期
    prevPeriod: '',          // 上一周期
    periods: [],             // 可选周期列表
    productData: [],         // 商品原始数据
    sortKey: 'payment_amount',
    sortOrder: 'desc',
    page: 1,
    pageSize: 10,
};

// ECharts 实例缓存
let CHARTS = {};

/* ================================================================
   首次访问引导 (Onboarding)
================================================================ */
function checkOnboarding() {
    const hasVisited = localStorage.getItem('dashboard_visited');
    if (!hasVisited && !_hasData) {
        document.getElementById('onboardingOverlay').style.display = 'flex';
    }
}

function closeOnboarding() {
    const dontShow = document.getElementById('dontShowAgain').checked;
    if (dontShow) {
        localStorage.setItem('dashboard_visited', 'true');
    }
    document.getElementById('onboardingOverlay').style.display = 'none';
}

/* ================================================================
   空状态管理
================================================================ */
let _hasData = true; // 默认有数据，避免闪烁

async function checkDataStatus() {
    const data = await apiFetch('/api/status');
    if (data && typeof data.has_data !== 'undefined') {
        _hasData = data.has_data;
    }
    return _hasData;
}

function showEmptyState(tabId) {
    const emptyEl = document.getElementById('emptyState' + capitalize(tabId.replace('tab-', '')));
    if (emptyEl) emptyEl.style.display = 'flex';
}

function hideAllEmptyStates() {
    document.querySelectorAll('.empty-state').forEach(el => {
        el.style.display = 'none';
    });
}

function capitalize(str) {
    return str.charAt(0).toUpperCase() + str.slice(1);
}

/* ================================================================
   工具函数
================================================================ */
// 格式化金额为万元
function fmtWan(val) {
    if (val == null || isNaN(val)) return '--';
    const n = Number(val);
    if (n === 0) return '0';
    if (Math.abs(n) < 10000) return n.toLocaleString('zh-CN', { maximumFractionDigits: 0 });
    return (n / 10000).toFixed(1) + '万';
}

// 格式化数字（带千分位）
function fmtNum(val) {
    if (val == null || isNaN(val)) return '--';
    return Number(val).toLocaleString('zh-CN');
}

// 格式化百分比
function fmtPct(val) {
    if (val == null || isNaN(val)) return '--';
    return (val * 100).toFixed(1) + '%';
}

// 显示/隐藏 loading
function setLoading(id, show) {
    const el = document.getElementById(id);
    if (el) el.classList.toggle('show', show);
}

// 通用 fetch 封装
async function apiFetch(url, options = {}) {
    try {
        const resp = await fetch(url, options);
        if (!resp.ok) {
            let errorMsg = '请求失败';
            try {
                const errData = await resp.json();
                errorMsg = errData.error || errData.message || errorMsg;
            } catch (e) {
                errorMsg = `HTTP ${resp.status}`;
            }
            showToast('\u274C ' + errorMsg, 'error');
            return null;
        }
        return await resp.json();
    } catch (e) {
        console.error('API Error:', url, e);
        showToast('\u274C 网络请求异常: ' + e.message, 'error');
        return null;
    }
}

// 创建或获取图表实例（自动清理旧实例防止内存泄漏）
function getOrCreateChart(id) {
    if (CHARTS[id]) {
        try { CHARTS[id].dispose(); } catch(e) {}
    }
    var dom = document.getElementById(id);
    if (!dom) return null;
    CHARTS[id] = echarts.init(dom);
    return CHARTS[id];
}

// 兼容别名：保持旧代码无需修改即可使用新的安全创建逻辑
function getChart(id) {
    return getOrCreateChart(id);
}

// ECharts 通用主题配置（自动适配亮/暗色）
function baseOption() {
    const isLight = document.documentElement.classList.contains('light');
    const textMain = isLight ? '#374151' : '#94A3B8';
    const textTitle = isLight ? '#111827' : '#F1F5F9';
    const tooltipBg = isLight ? '#FFFFFF' : '#1E293B';
    const tooltipBorder = isLight ? '#E5E7EB' : '#334155';
    const axisLine = isLight ? '#D1D5DB' : '#334155';
    const splitLine = isLight ? '#F3F4F6' : '#1E293B';
    return {
        backgroundColor: 'transparent',
        textStyle: { color: textMain, fontFamily: 'inherit' },
        title: { textStyle: { color: textTitle } },
        legend: { textStyle: { color: textMain } },
        tooltip: {
            backgroundColor: tooltipBg,
            borderColor: tooltipBorder,
            textStyle: { color: textTitle, fontSize: 12 },
        },
        grid: {
            left: 60, right: 60, top: 50, bottom: 40,
            containLabel: true,
        },
        xAxis: {
            axisLine: { lineStyle: { color: axisLine } },
            axisLabel: { color: textMain },
            splitLine: { show: false },
        },
        yAxis: {
            axisLine: { lineStyle: { color: axisLine } },
            axisLabel: { color: textMain },
            splitLine: { lineStyle: { color: splitLine, type: 'dashed' } },
        },
    };
}

function showChartEmpty(chartId) {
    if (CHARTS[chartId]) {
        CHARTS[chartId].dispose();
        delete CHARTS[chartId];
    }
    const el = document.getElementById(chartId);
    if (el) el.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:#64748B;font-size:0.85rem;">暂无数据</div>';
}

/* ================================================================
   维度 & 周期切换
================================================================ */
function switchDimension(dim) {
    STATE.dim = dim;
    // 更新按钮状态
    document.querySelectorAll('.dim-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.dim === dim);
    });
    // 更新ARIA属性
    document.querySelectorAll('.dim-btn').forEach(b => {
        b.setAttribute('aria-checked', b.classList.contains('active') ? 'true' : 'false');
    });
    // 目标进度模块只在月度维度下显示
    const targetSection = document.getElementById('targetProgressSection');
    if (targetSection) {
        targetSection.classList.toggle('hidden', dim !== 'monthly');
    }
    loadPeriods();
}

function onPeriodChange() {
    const sel = document.getElementById('periodSelect');
    STATE.period = sel.value;
    // 计算上一周期
    const idx = STATE.periods.indexOf(STATE.period);
    STATE.prevPeriod = idx < STATE.periods.length - 1 ? STATE.periods[idx + 1] : '';
    STATE.page = 1;
    updateTimeControl();
    syncURL();
    refreshAll();
}

function updateTimeControl() {
    const label = document.getElementById('timeRangeLabel');
    if (label) label.textContent = STATE.period || '--';
    document.querySelectorAll('.time-quick').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.preset === ({ daily: 'yesterday', weekly: 'seven', monthly: 'thirty' }[STATE.dim] || ''));
    });
}

function selectTimePreset(preset) {
    const dim = { yesterday: 'daily', seven: 'weekly', thirty: 'monthly', sixty: 'monthly' }[preset];
    if (!dim) return;
    document.querySelectorAll('.time-quick').forEach(btn => btn.classList.toggle('active', btn.dataset.preset === preset));
    if (STATE.dim === dim) {
        loadPeriods();
    } else {
        switchDimension(dim);
    }
}

function openCustomPeriod(event) {
    const select = document.getElementById('periodSelect');
    const popover = document.getElementById('timeCustomPopover');
    const button = event?.currentTarget || document.querySelector('.time-custom-btn');
    if (!select || !popover) return;
    popover.hidden = !popover.hidden;
    if (button) button.setAttribute('aria-expanded', popover.hidden ? 'false' : 'true');
    if (!popover.hidden) select.focus();
}

function closeCustomPeriod() {
    const popover = document.getElementById('timeCustomPopover');
    const button = document.querySelector('.time-custom-btn');
    if (popover) popover.hidden = true;
    if (button) button.setAttribute('aria-expanded', 'false');
}

function applyCustomPeriod() {
    onPeriodChange();
    closeCustomPeriod();
}

function shiftPeriod(direction) {
    if (!STATE.periods || STATE.periods.length < 2) return;
    const index = STATE.periods.indexOf(STATE.period);
    const nextIndex = Math.max(0, Math.min(STATE.periods.length - 1, index - direction));
    const select = document.getElementById('periodSelect');
    if (!select || nextIndex === index) return;
    select.value = STATE.periods[nextIndex];
    onPeriodChange();
}

async function loadPeriods() {
    const data = await apiFetch(`/api/periods?dim=${STATE.dim}`);
    if (!data) return;
    // 兼容：API 可能返回数组或 {periods:[...]}
    const periods = Array.isArray(data) ? data.map(p => p.period) : (data.periods || []);
    if (periods.length === 0) return;
    STATE.periods = periods;
    const sel = document.getElementById('periodSelect');
    sel.innerHTML = '';
    periods.forEach(p => {
        const opt = document.createElement('option');
        opt.value = p; opt.textContent = p;
        sel.appendChild(opt);
    });
    // 默认选中最近一个周期
    STATE.period = periods[0];
    STATE.prevPeriod = periods.length > 1 ? periods[1] : '';
    sel.value = STATE.period;
    updateTimeControl();
    syncURL();
    refreshAll();
}

/* ================================================================
   刷新所有模块
================================================================ */
// 每个Tab对应的加载函数
const TAB_LOADERS = {
    'tab-overview': (dim, period, prevPeriod, start, end) => [
        loadKPI(dim, period, prevPeriod),
        loadTargetProgress(period),
        loadAlerts(period),
        loadSalesTrend(dim, start, end),
        loadTrafficAndConv(dim, start, end),
        loadCustomerAnalysis(),
        loadFunnelAnalysis(),
    ],
    'tab-ops': (dim, period) => [
        loadProducts(dim, period),
        loadAdPerformance(dim, period),
        loadAdTrend(dim, period),
    ],
    'tab-health': (dim, period) => [
        loadHealthDashboard(period),
    ],
    'tab-review': () => { var p = []; if(typeof loadReviewList==='function') p.push(loadReviewList('','')); p.push(loadReviewSummary(), loadReviewProducts()); return p; },
    'tab-market': () => [
        loadMarketOpportunities(),
        loadMarketSummary(),
    ],
    'tab-lifecycle': () => { if(typeof loadLifecycleData==='function') return [loadLifecycleData()]; return []; },
    'tab-compare': () => { if(typeof initCompareTab==='function') initCompareTab(); return []; },
    'tab-postmortem': (dim, period) => [
        loadPostmortem(dim, period),
    ],
    'tab-keywords': (dim, period) => [
        loadKeywords(dim, period),
    ],
    'tab-traffic': (dim, period) => [
        loadTrafficStructure(dim, period),
    ],
    'tab-manage': () => [
        loadTasks(),
        loadUserKPIs(),
    ],
};

// 获取当前活跃Tab
function getActiveTab() {
    const el = document.querySelector('.tab-content.active');
    return el ? el.id : 'tab-overview';
}

async function refreshAll() {
    const { dim, period, prevPeriod, periods } = STATE;
    if (!period) return;

    // 先检查是否有数据
    const hasData = await checkDataStatus();
    hideAllEmptyStates();
    if (!hasData) {
        const activeTab = document.querySelector('.tab-content.active');
        if (activeTab) showEmptyState(activeTab.id);
        return;
    }

    // 计算趋势图的起止时间
    const start = periods.length > 0 ? periods[periods.length - 1] : '';
    const end = period;

    // 只加载当前Tab需要的数据
    const tabId = getActiveTab();
    if (!STATE._loadedTabs) STATE._loadedTabs = {};
    STATE._loadedTabs[tabId] = true;
    const loader = TAB_LOADERS[tabId];
    const promises = loader ? loader(dim, period, prevPeriod, start, end) : [];
    await Promise.allSettled(promises);
    updateTimestamp();
}

// 切换Tab时按需加载（如果该Tab还没加载过数据）
async function switchTab(tabId) {
    STATE._currentTab = tabId;
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.tab === tabId);
    });
    // 更新ARIA属性
    document.querySelectorAll('.tab-btn').forEach(b => {
        b.setAttribute('aria-selected', b.classList.contains('active') ? 'true' : 'false');
    });

    // Tab切换动画：先隐藏旧Tab，再显示新Tab
    const oldContent = document.querySelector('.tab-content.active');
    const newContent = document.getElementById(tabId);
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.remove('active', 'tab-active');
    });
    if (newContent) {
        newContent.classList.add('tab-entering', 'active');
        requestAnimationFrame(() => {
            requestAnimationFrame(() => {
                newContent.classList.remove('tab-entering');
                newContent.classList.add('tab-active');
            });
        });
    }

    if (!_hasData) {
        hideAllEmptyStates();
        showEmptyState(tabId);
    }
    // 按需加载该Tab的数据
    if (_hasData && !STATE._loadedTabs) STATE._loadedTabs = {};
    if (_hasData && !STATE._loadedTabs[tabId]) {
        STATE._loadedTabs[tabId] = true;
        const { dim, period, prevPeriod, periods } = STATE;
        const start = periods.length > 0 ? periods[periods.length - 1] : '';
        const end = period;
        const loader = TAB_LOADERS[tabId];
        if (loader) {
            const promises = loader(dim, period, prevPeriod, start, end);
            await Promise.allSettled(promises);
        }
    }
    setTimeout(() => {
        Object.values(CHARTS).forEach(c => { try { c.resize(); } catch(e) {} });
    }, 200);
    setTimeout(() => {
        Object.values(CHARTS).forEach(c => { try { c.resize(); } catch(e) {} });
    }, 400);
    try { localStorage.setItem('dashboard_active_tab', tabId); } catch(e) {}
    syncURL();
}

// Tab键盘导航：左右箭头切换Tab
document.addEventListener('keydown', function(e) {
    if (!document.querySelector('.tab-btn:focus')) return;
    const tabs = Array.from(document.querySelectorAll('.tab-btn'));
    const idx = tabs.indexOf(document.activeElement);
    if (idx === -1) return;
    if (e.key === 'ArrowRight') {
        e.preventDefault();
        const next = tabs[(idx + 1) % tabs.length];
        next.focus();
        next.click();
    } else if (e.key === 'ArrowLeft') {
        e.preventDefault();
        const prev = tabs[(idx - 1 + tabs.length) % tabs.length];
        prev.focus();
        prev.click();
    }
});

/* ================================================================
   数据导出
================================================================ */
async function exportData(type) {
    try {
        const payload = {
            type: type,
            period: STATE.period,
            dim: STATE.dim,
        };
        // 商品导出：支持筛选后导出
        if (type === 'products') {
            const search = document.getElementById('productSearch')?.value?.trim() || '';
            const tier = document.getElementById('productTierFilter')?.value || '';
            const style = document.getElementById('productStyleFilter')?.value || '';
            const status = document.getElementById('productStatusFilter')?.value || '';
            const starOnly = document.getElementById('starFilterBtn')?.classList.contains('active') || false;
            if (search) payload.search = search;
            if (tier) payload.tier = tier;
            if (style) payload.style = style;
            if (status) payload.status = status;
            if (starOnly) payload.star_only = true;
            // 传入当前可见列
            if (STATE._visibleCols) {
                payload.columns = STATE._visibleCols.map(c => c.key);
            }
        }
        const resp = await fetch('/api/export', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const blob = await resp.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${type}_${STATE.period || 'all'}.xlsx`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
        showToast(`导出${type}数据成功`, 'success');
    } catch (e) {
        console.error('Export error:', e);
        showToast(`导出失败: ${e.message}`, 'error');
    }
}

/* ================================================================
   全屏看板模式
================================================================ */
function toggleFullscreen() {
    var el = document.documentElement;
    if (!document.fullscreenElement) {
        if (el.requestFullscreen) el.requestFullscreen();
        else if (el.webkitRequestFullscreen) el.webkitRequestFullscreen();
        else if (el.msRequestFullscreen) el.msRequestFullscreen();
    } else {
        if (document.exitFullscreen) document.exitFullscreen();
        else if (document.webkitExitFullscreen) document.webkitExitFullscreen();
    }
}

/* ================================================================
   刷新机制
================================================================ */
let _autoRefreshTimer = null;

// 主题切换
function toggleTheme() {
    const isLight = document.documentElement.classList.toggle('light');
    localStorage.setItem('theme', isLight ? 'light' : 'dark');
    const themeButton = document.getElementById('themeToggle');
    if (themeButton) {
        themeButton.setAttribute('aria-pressed', String(isLight));
        themeButton.setAttribute('aria-label', isLight ? '切换到深色主题' : '切换到浅色主题');
    }
    // 重新加载当前Tab以刷新图表颜色
    if (STATE._currentTab) {
        STATE._loadedTabs = {}; // 清除缓存强制重绘
        switchTab(STATE._currentTab);
    }
}
// 初始化主题
(function() {
    const saved = localStorage.getItem('theme');
    if (saved === 'light') {
        document.documentElement.classList.add('light');
        const btn = document.getElementById('themeToggle');
        if (btn) {
            btn.setAttribute('aria-pressed', 'true');
            btn.setAttribute('aria-label', '切换到深色主题');
        }
    }
})();

function manualRefresh() {
    const btn = document.getElementById('refreshBtn');
    if (btn) btn.classList.add('spinning');
    refreshAll().then(() => {
        updateTimestamp();
        if (btn) btn.classList.remove('spinning');
    });
}

function updateTimestamp() {
    const el = document.getElementById('lastUpdate');
    if (el) {
        const now = new Date();
        const h = String(now.getHours()).padStart(2, '0');
        const m = String(now.getMinutes()).padStart(2, '0');
        const s = String(now.getSeconds()).padStart(2, '0');
        el.textContent = `最后更新: ${h}:${m}:${s}`;
    }
}

function toggleAutoRefresh() {
    const btn = document.getElementById('autoRefreshBtn');
    const isActive = _autoRefreshTimer !== null;
    if (isActive) {
        clearInterval(_autoRefreshTimer);
        _autoRefreshTimer = null;
        if (btn) btn.classList.remove('active');
        try { localStorage.setItem('dashboard_auto_refresh', 'off'); } catch(e) {}
    } else {
        _autoRefreshTimer = setInterval(() => {
            manualRefresh();
        }, 5 * 60 * 1000); // 5分钟
        if (btn) btn.classList.add('active');
        try { localStorage.setItem('dashboard_auto_refresh', 'on'); } catch(e) {}
    }
}

function restoreAutoRefresh() {
    const saved = localStorage.getItem('dashboard_auto_refresh');
    if (saved === 'on') {
        _autoRefreshTimer = setInterval(() => {
            manualRefresh();
        }, 5 * 60 * 1000);
        const btn = document.getElementById('autoRefreshBtn');
        if (btn) btn.classList.add('active');
    }
}

// 页面卸载时清理定时器和所有图表实例
window.addEventListener('beforeunload', function() {
    if (window._autoRefreshTimer) {
        clearInterval(window._autoRefreshTimer);
        window._autoRefreshTimer = null;
    }
    // 清理所有ECharts实例防止内存泄漏
    Object.keys(CHARTS).forEach(function(id) {
        try { CHARTS[id].dispose(); } catch(e) {}
    });
    CHARTS = {};
});

function restoreTab() {
    const saved = localStorage.getItem('dashboard_active_tab');
    if (saved) switchTab(saved);
}

/* ================================================================
   图表保存为图片
================================================================ */
function saveChartAsImage(chartInstance, filename) {
    if (!chartInstance) return;
    try {
        var url = chartInstance.getDataURL({
            type: 'png',
            pixelRatio: 2,
            backgroundColor: '#fff'
        });
        var a = document.createElement('a');
        a.href = url;
        a.download = (filename || 'chart') + '.png';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        showToast('图表已保存为图片', 'success');
    } catch (e) {
        console.error('保存图表失败:', e);
        showToast('保存图表失败', 'error');
    }
}

// 为图表容器添加保存按钮
function addChartSaveBtn(chartInstance, chartId) {
    var dom = document.getElementById(chartId);
    if (!dom || dom.querySelector('.chart-save-btn')) return;
    dom.style.position = 'relative';
    var saveBtn = document.createElement('button');
    saveBtn.className = 'chart-save-btn';
    saveBtn.textContent = '\uD83D\uDCF7';
    saveBtn.title = '保存为图片';
    saveBtn.onclick = function(e) {
        e.stopPropagation();
        saveChartAsImage(chartInstance, chartId);
    };
    dom.appendChild(saveBtn);
}

/* ================================================================
   Toast 通知
================================================================ */
function showToast(message, type = 'info', duration = 3000) {
    const container = document.getElementById('toastContainer');
    if (!container) return;
    const colors = {
        info: 'var(--accent)',
        success: '#22C55E',
        warning: '#F59E0B',
        error: '#EF4444'
    };
    const icons = {
        info: 'ℹ',
        success: '✓',
        warning: '⚠',
        error: '✕'
    };
    const toast = document.createElement('div');
    toast.style.cssText = `
        display:flex;align-items:center;gap:8px;
        padding:10px 16px;border-radius:8px;
        background:var(--bg-elevated);color:var(--text-primary);
        border-left:3px solid ${colors[type] || colors.info};
        box-shadow:0 4px 12px rgba(0,0,0,0.4);
        font-size:0.85rem;min-width:200px;max-width:360px;
        transform:translateX(120%);transition:transform 0.3s ease;
    `;
    toast.innerHTML = `<span style="color:${colors[type]};font-weight:bold;">${icons[type] || icons.info}</span><span>${message}</span>`;
    container.appendChild(toast);
    requestAnimationFrame(() => { toast.style.transform = 'translateX(0)'; });
    setTimeout(() => {
        toast.style.transform = 'translateX(120%)';
        setTimeout(() => toast.remove(), 300);
    }, duration);
}

/* ================================================================
   操作日志面板
================================================================ */
function _escapeHtml(str) {
    if (typeof escapeHtml === 'function') return escapeHtml(str);
    const div = document.createElement('div');
    div.textContent = str || '';
    return div.innerHTML;
}

function toggleLogPanel() {
    const panel = document.getElementById('logPanel');
    if (!panel) return;
    const isVisible = panel.style.display !== 'none';
    panel.style.display = isVisible ? 'none' : 'block';
    if (!isVisible) loadLogs();
}

async function loadLogs() {
    const listEl = document.getElementById('logList');
    if (!listEl) return;
    try {
        const logs = await apiFetch('/api/logs?limit=50');
        if (!logs || !Array.isArray(logs) || logs.length === 0) {
            listEl.innerHTML = '<div style="text-align:center;color:var(--text-muted);padding:20px;font-size:0.82rem;">暂无操作记录</div>';
            return;
        }
        listEl.innerHTML = logs.map(log => `
            <div class="log-entry">
                <span class="log-time">${_escapeHtml(log.created_at || '--')}</span>
                <span class="log-action">${_escapeHtml(log.action || '')}</span>
                <span class="log-detail">${_escapeHtml(log.detail || '')}</span>
                <span style="color:var(--text-muted);font-size:0.72rem;white-space:nowrap;">${_escapeHtml(log.operator || 'admin')}</span>
            </div>
        `).join('');
    } catch (e) {
        listEl.innerHTML = '<div style="text-align:center;color:var(--text-muted);padding:20px;font-size:0.82rem;">加载失败</div>';
    }
}

/* ================================================================
   URL 分享：同步/恢复筛选状态
================================================================ */
function syncURL() {
    const params = new URLSearchParams();
    if (STATE._currentTab) params.set('tab', STATE._currentTab.replace('tab-', ''));
    if (STATE.period) params.set('period', STATE.period);
    if (STATE.dim) params.set('dim', STATE.dim);
    // 搜索
    const search = document.getElementById('productSearch')?.value?.trim();
    if (search) params.set('search', search);
    // 筛选
    const tier = document.getElementById('productTierFilter')?.value;
    if (tier && tier !== '全部') params.set('tier', tier);
    const style = document.getElementById('productStyleFilter')?.value;
    if (style && style !== '全部') params.set('style', style);
    const status = document.getElementById('productStatusFilter')?.value;
    if (status && status !== '全部') params.set('status', status);
    // 排序
    if (STATE.sortKey) params.set('sort', STATE.sortKey);
    if (STATE.sortOrder) params.set('order', STATE.sortOrder);

    const qs = params.toString();
    const url = qs ? window.location.pathname + '?' + qs : window.location.pathname;
    window.history.replaceState(null, '', url);
}

function restoreFromURL() {
    const params = new URLSearchParams(window.location.search);
    if (params.get('tab')) {
        const tabId = 'tab-' + params.get('tab');
        // 延迟切换Tab
        setTimeout(() => switchTab(tabId), 100);
    }
    if (params.get('period')) STATE.period = params.get('period');
    if (params.get('dim')) STATE.dim = params.get('dim');
    if (params.get('sort')) STATE.sortKey = params.get('sort');
    if (params.get('order')) STATE.sortOrder = params.get('order');
    // 恢复筛选器值
    if (params.get('search')) {
        const el = document.getElementById('productSearch');
        if (el) el.value = params.get('search');
    }
    if (params.get('tier')) {
        const el = document.getElementById('productTierFilter');
        if (el) el.value = params.get('tier');
    }
    if (params.get('style')) {
        const el = document.getElementById('productStyleFilter');
        if (el) el.value = params.get('style');
    }
    if (params.get('status')) {
        const el = document.getElementById('productStatusFilter');
        if (el) el.value = params.get('status');
    }
}

/* ================================================================
   窗口自适应
================================================================ */
// 防抖处理窗口resize，避免频繁触发图表重绘
let _resizeTimer = null;
window.addEventListener('resize', () => {
    if (_resizeTimer) clearTimeout(_resizeTimer);
    _resizeTimer = setTimeout(() => {
        Object.values(CHARTS).forEach(c => { try { c.resize(); } catch(e) {} });
    }, 200);
});

/* ================================================================
   键盘快捷键
================================================================ */
document.addEventListener('keydown', (e) => {
    const tag = (document.activeElement && document.activeElement.tagName) || '';
    const isInputFocused = tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT';

    // Ctrl+K / Cmd+K 聚焦搜索框
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        // 如果不在商品运营Tab则先切换过去
        if (!document.getElementById('tab-ops').classList.contains('active')) {
            switchTab('tab-ops');
        }
        setTimeout(() => {
            const search = document.getElementById('productSearch');
            if (search) search.focus();
        }, 300);
        return;
    }

    // / 聚焦搜索框
    if (e.key === '/' && !e.ctrlKey && !e.metaKey) {
        const search = document.getElementById('productSearch');
        if (search && document.activeElement !== search) {
            e.preventDefault();
            search.focus();
        }
    }

    // 左右箭头翻页（焦点不在输入框时）
    if (!isInputFocused && !e.ctrlKey && !e.metaKey && !e.altKey) {
        if (e.key === 'ArrowLeft') {
            e.preventDefault();
            if (typeof goPage === 'function' && STATE.page > 1) {
                goPage(STATE.page - 1);
            }
            return;
        }
        if (e.key === 'ArrowRight') {
            e.preventDefault();
            if (typeof goPage === 'function') {
                goPage(STATE.page + 1);
            }
            return;
        }
    }

    // Esc 关闭弹窗/取消搜索
    if (e.key === 'Escape') {
        const search = document.getElementById('productSearch');
        if (search && document.activeElement === search) {
            search.blur();
            return;
        }
        // 关闭 .modal-overlay 弹窗
        const modalOverlay = document.querySelector('.modal-overlay');
        if (modalOverlay) {
            modalOverlay.style.display = 'none';
            return;
        }
        // 关闭 #productDetailModal
        const detailModal = document.getElementById('productDetailModal');
        if (detailModal && detailModal.style.display !== 'none') {
            detailModal.style.display = 'none';
            return;
        }
        // 关闭列筛选弹窗
        const colFilterPopup = document.getElementById('colFilterPopup');
        if (colFilterPopup) {
            colFilterPopup.remove();
            return;
        }
        // 关闭列配置面板
        const panel = document.getElementById('colConfigPanel');
        if (panel && panel.style.display !== 'none') {
            panel.style.display = 'none';
            return;
        }
        // 关闭周期详情弹窗
        const periodDetail = document.getElementById('periodDetailPopup');
        if (periodDetail) {
            periodDetail.remove();
            return;
        }
        // 关闭工具箱
        if (typeof closeToolbox === 'function') closeToolbox();
    }
});

/* ================================================================
   数据报告生成
================================================================ */
function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str || '';
    return div.innerHTML;
}

async function generateReport() {
    showToast('正在生成报告...', 'info');
    const resp = await apiFetch(`/api/report?dim=${STATE.dim}&period=${STATE.period}`);
    if (resp && resp.report) {
        const overlay = document.createElement('div');
        overlay.className = 'modal-overlay';
        overlay.style.display = 'flex';
        overlay.innerHTML = `
            <div style="background:var(--bg-card);border-radius:16px;padding:24px;max-width:600px;width:90vw;max-height:80vh;overflow-y:auto;box-shadow:var(--shadow-lg);">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
                    <h3 style="color:var(--text-primary);margin:0;">数据报告</h3>
                    <div style="display:flex;gap:8px;">
                        <button onclick="copyReport()" style="padding:6px 12px;border-radius:6px;border:1px solid var(--border);background:transparent;color:var(--text-secondary);cursor:pointer;font-size:0.8rem;">📋 复制</button>
                        <button onclick="this.closest('.modal-overlay').remove()" style="padding:6px 12px;border-radius:6px;border:none;background:var(--text-muted);color:#fff;cursor:pointer;font-size:0.8rem;">✕ 关闭</button>
                    </div>
                </div>
                <pre id="reportContent" style="white-space:pre-wrap;font-family:inherit;font-size:0.85rem;line-height:1.6;color:var(--text-primary);background:var(--bg-elevated);padding:16px;border-radius:8px;">${escapeHtml(resp.report)}</pre>
            </div>
        `;
        document.body.appendChild(overlay);
    } else {
        showToast('生成报告失败', 'error');
    }
}

function copyReport() {
    const text = document.getElementById('reportContent')?.textContent;
    if (!text) return;
    if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(text).then(() => showToast('已复制到剪贴板', 'success'))
            .catch(() => fallbackCopy(text));
    } else {
        fallbackCopy(text);
    }
}

function fallbackCopy(text) {
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.style.cssText = 'position:fixed;left:-9999px;';
    document.body.appendChild(ta);
    ta.select();
    try {
        document.execCommand('copy');
        showToast('已复制到剪贴板', 'success');
    } catch (e) {
        showToast('复制失败，请手动复制', 'error');
    }
    document.body.removeChild(ta);
}
