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
    refreshAll();
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
    document.getElementById('themeToggle').textContent = isLight ? '☀️' : '🌙';
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
        if (btn) btn.textContent = '☀️';
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
/* ================================================================
   模块4: 商品分析
================================================================ */

// All available columns definition
const ALL_COLUMNS = [
    // 基础信息
    { key: 'image', label: '商品图', type: 'image', group: '基础信息', defaultVisible: true },
    { key: 'title', label: '商品标题', type: 'text', group: '基础信息', defaultVisible: true },
    { key: 'product_id', label: '商品ID', type: 'text', group: '基础信息', defaultVisible: false },
    { key: 'category', label: '商品类目', type: 'text', group: '基础信息', defaultVisible: false },
    { key: 'tier', label: '分层', type: 'text', group: '基础信息', defaultVisible: true },
    { key: 'style', label: '风格', type: 'text', group: '基础信息', defaultVisible: true },
    { key: 'scene', label: '场景', type: 'text', group: '基础信息', defaultVisible: false },
    { key: 'status', label: '商品状态', type: 'status', group: '基础信息', defaultVisible: true },
    { key: 'list_date', label: '上架时间', type: 'text', group: '基础信息', defaultVisible: false },
    { key: 'manager', label: '负责人', type: 'text', group: '基础信息', defaultVisible: false },
    { key: 'action', label: '运营动作', type: 'action', group: '基础信息', defaultVisible: true },
    // 流量指标
    { key: 'visitors', label: '访客数', type: 'number', group: '流量指标', defaultVisible: true },
    { key: 'page_views', label: '浏览量', type: 'number', group: '流量指标', defaultVisible: false },
    { key: 'search_visitors', label: '搜索访客', type: 'number', group: '流量指标', defaultVisible: false },
    { key: 'search_ratio', label: '搜索占比', type: 'percent', group: '流量指标', defaultVisible: false },
    { key: 'search_ipv', label: '搜索IPV', type: 'number', group: '流量指标', defaultVisible: false },
    { key: 'recommend_ipv', label: '推荐IPV', type: 'number', group: '流量指标', defaultVisible: false },
    { key: 'paid_ipv', label: '营销推广IPV', type: 'number', group: '流量指标', defaultVisible: false },
    { key: 'organic_ipv', label: '非推广IPV', type: 'number', group: '流量指标', defaultVisible: false },
    { key: 'uv_value', label: '客单价值', type: 'money', group: '流量指标', defaultVisible: false },
    { key: 'avg_stay_duration', label: '平均停留时长', type: 'decimal', group: '流量指标', defaultVisible: false },
    { key: 'bounce_rate', label: '跳出率', type: 'percent', group: '流量指标', defaultVisible: false },
    // 转化指标
    { key: 'conversion', label: '支付转化率', type: 'percent', group: '转化指标', defaultVisible: true },
    { key: 'search_conversion', label: '搜索转化率', type: 'percent', group: '转化指标', defaultVisible: false },
    { key: 'cart_rate', label: '加购率', type: 'percent', group: '转化指标', defaultVisible: false },
    { key: 'fav_rate', label: '收藏率', type: 'percent', group: '转化指标', defaultVisible: false },
    { key: 'click_rate', label: '点击率', type: 'percent', group: '转化指标', defaultVisible: false },
    // 交易指标
    { key: 'payment_amount', label: '支付金额', type: 'money', group: '交易指标', defaultVisible: true },
    { key: 'payment_count', label: '支付件数', type: 'number', group: '交易指标', defaultVisible: true },
    { key: 'buyers', label: '支付买家数', type: 'number', group: '交易指标', defaultVisible: false },
    { key: 'avg_order_value', label: '笔单价', type: 'money', group: '交易指标', defaultVisible: false },
    { key: 'net_sales', label: '净销售额', type: 'money', group: '交易指标', defaultVisible: false },
    { key: 'cart_qty', label: '加购件数', type: 'number', group: '交易指标', defaultVisible: false },
    { key: 'cart_users', label: '商品加购人数', type: 'number', group: '交易指标', defaultVisible: false },
    { key: 'fav_users', label: '收藏人数', type: 'number', group: '交易指标', defaultVisible: false },
    // 退款指标
    { key: 'refund_amount', label: '退款金额', type: 'money', group: '退款指标', defaultVisible: false },
    { key: 'refund_rate', label: '退款率', type: 'percent', group: '退款指标', defaultVisible: true },
    { key: 'refund_paid_ratio', label: '退款退货率', type: 'percent', group: '退款指标', defaultVisible: false },
    // 推广指标
    { key: 'ad_spend', label: '推广花费', type: 'money', group: '推广指标', defaultVisible: true },
    { key: 'roi', label: '推广ROI', type: 'decimal', group: '推广指标', defaultVisible: true },
    { key: 'overall_roi', label: '全店ROI', type: 'decimal', group: '推广指标', defaultVisible: false },
    { key: 'paid_ratio', label: '付费占比', type: 'percent', group: '推广指标', defaultVisible: false },
    { key: 'keyword_spend', label: '直通车花费', type: 'money', group: '推广指标', defaultVisible: false },
    { key: 'keyword_sales', label: '直通车成交', type: 'money', group: '推广指标', defaultVisible: false },
    { key: 'keyword_roi', label: '直通车ROI', type: 'decimal', group: '推广指标', defaultVisible: false },
    { key: 'keyword_visitors', label: '直通车访客', type: 'number', group: '推广指标', defaultVisible: false },
    { key: 'keyword_ppc', label: '直通车PPC', type: 'money', group: '推广指标', defaultVisible: false },
    { key: 'crowd_spend', label: '人群推广花费', type: 'money', group: '推广指标', defaultVisible: false },
    { key: 'crowd_sales', label: '人群推广成交', type: 'money', group: '推广指标', defaultVisible: false },
    { key: 'crowd_roi', label: '人群推广ROI', type: 'decimal', group: '推广指标', defaultVisible: false },
    { key: 'crowd_visitors', label: '人群推广访客', type: 'number', group: '推广指标', defaultVisible: false },
    { key: 'crowd_ppc', label: '人群推广PPC', type: 'money', group: '推广指标', defaultVisible: false },
    { key: 'site_spend', label: '定向推广花费', type: 'money', group: '推广指标', defaultVisible: false },
    { key: 'site_sales', label: '定向推广成交', type: 'money', group: '推广指标', defaultVisible: false },
    { key: 'site_roi', label: '定向推广ROI', type: 'decimal', group: '推广指标', defaultVisible: false },
    { key: 'site_visitors', label: '定向推广访客', type: 'number', group: '推广指标', defaultVisible: false },
    { key: 'site_ppc', label: '定向推广PPC', type: 'money', group: '推广指标', defaultVisible: false },
    // 付费报表
    { key: 'impressions', label: '展现量', type: 'number', group: '付费报表', defaultVisible: false },
    { key: 'clicks', label: '点击量', type: 'number', group: '付费报表', defaultVisible: false },
    { key: 'cost', label: '花费', type: 'money', group: '付费报表', defaultVisible: false },
    { key: 'ctr', label: '点击率', type: 'percent', group: '付费报表', defaultVisible: false },
    { key: 'cpc', label: '平均点击花费', type: 'money', group: '付费报表', defaultVisible: false },
    { key: 'cpm', label: '千次展现花费', type: 'money', group: '付费报表', defaultVisible: false },
    { key: 'direct_gmv', label: '直接成交金额', type: 'money', group: '付费报表', defaultVisible: false },
    { key: 'indirect_gmv', label: '间接成交金额', type: 'money', group: '付费报表', defaultVisible: false },
    { key: 'total_gmv', label: '总成交金额', type: 'money', group: '付费报表', defaultVisible: false },
    { key: 'total_orders', label: '总成交笔数', type: 'number', group: '付费报表', defaultVisible: false },
    { key: 'direct_orders', label: '直接成交笔数', type: 'number', group: '付费报表', defaultVisible: false },
    { key: 'indirect_orders', label: '间接成交笔数', type: 'number', group: '付费报表', defaultVisible: false },
    { key: 'click_conversion', label: '点击转化率', type: 'percent', group: '付费报表', defaultVisible: false },
    { key: 'presale_roi', label: '含预售投产比', type: 'decimal', group: '付费报表', defaultVisible: false },
    { key: 'total_cost', label: '总成交成本', type: 'money', group: '付费报表', defaultVisible: false },
    { key: 'cart_adds', label: '总购物车数', type: 'number', group: '付费报表', defaultVisible: false },
    { key: 'direct_cart_adds', label: '直接购物车数', type: 'number', group: '付费报表', defaultVisible: false },
    { key: 'indirect_cart_adds', label: '间接购物车数', type: 'number', group: '付费报表', defaultVisible: false },
    { key: 'favs', label: '收藏宝贝数', type: 'number', group: '付费报表', defaultVisible: false },
    { key: 'store_favs', label: '收藏店铺数', type: 'number', group: '付费报表', defaultVisible: false },
    { key: 'store_fav_cost', label: '店铺收藏成本', type: 'money', group: '付费报表', defaultVisible: false },
    { key: 'total_fav_cart', label: '总收藏加购数', type: 'number', group: '付费报表', defaultVisible: false },
    { key: 'total_fav_cart_cost', label: '总收藏加购成本', type: 'money', group: '付费报表', defaultVisible: false },
    { key: 'item_fav_cart', label: '宝贝收藏加购数', type: 'number', group: '付费报表', defaultVisible: false },
    { key: 'item_fav_cart_cost', label: '宝贝收藏加购成本', type: 'money', group: '付费报表', defaultVisible: false },
    { key: 'total_favs', label: '总收藏数', type: 'number', group: '付费报表', defaultVisible: false },
    { key: 'item_fav_cost', label: '宝贝收藏成本', type: 'money', group: '付费报表', defaultVisible: false },
    { key: 'item_fav_rate', label: '宝贝收藏率', type: 'percent', group: '付费报表', defaultVisible: false },
    { key: 'cart_cost', label: '加购成本', type: 'money', group: '付费报表', defaultVisible: false },
    // 客户指标
    { key: 'repurchase_rate', label: '复购率', type: 'percent', group: '客户指标', defaultVisible: false },
    { key: 'cross_sell_rate', label: '连带购买率', type: 'percent', group: '客户指标', defaultVisible: false },
    { key: 'cross_sell_qty', label: '连带购买量', type: 'number', group: '客户指标', defaultVisible: false },
    { key: 'cross_sell_categories', label: '连带购买叶子类目宽度', type: 'number', group: '客户指标', defaultVisible: false },
    { key: 'repurchase_users', label: '复购用户数', type: 'number', group: '客户指标', defaultVisible: false },
    { key: 'new_buyers', label: '成交新客数', type: 'number', group: '客户指标', defaultVisible: false },
    { key: 'new_buyer_ratio', label: '成交新客占比', type: 'percent', group: '客户指标', defaultVisible: false },
    // 引潜指标
    { key: 'guide_visits', label: '引导访问量', type: 'number', group: '引潜指标', defaultVisible: false },
    { key: 'guide_visitors', label: '引导访问人数', type: 'number', group: '引潜指标', defaultVisible: false },
    { key: 'guide_potential', label: '引导访问潜客数', type: 'number', group: '引潜指标', defaultVisible: false },
    { key: 'guide_potential_ratio', label: '引导访问潜客占比', type: 'percent', group: '引潜指标', defaultVisible: false },
    // 评分
    { key: 'score', label: '综合评分', type: 'decimal', group: '评分', defaultVisible: false },
];

// Current column config (loaded from localStorage or defaults)
let columnConfig = {
    visible: ALL_COLUMNS.filter(c => c.defaultVisible).map(c => c.key),
    sortKey: 'payment_amount',
    sortOrder: 'desc',
};

// 指标分组视图定义
const METRIC_VIEWS = {
    basic: {
        label: '基础信息',
        groups: ['基础信息', '流量指标', '交易指标', '转化指标', '退款指标', '推广指标'],
        columns: ['image', 'title', 'action', 'tier', 'style', 'status', 'list_date',
                  'visitors', 'uv_value', 'search_visitors', 'search_ratio', 'bounce_rate', 'avg_stay_duration',
                  'payment_amount', 'payment_count', 'net_sales',
                  'conversion', 'cart_rate',
                  'refund_rate',
                  'ad_spend', 'roi']
    },
    selection: {
        label: '选款指标',
        groups: ['转化指标', '交易指标', '退款指标', '评分'],
        columns: ['image', 'title', 'action', 'conversion', 'search_conversion', 'cart_rate', 'fav_rate',
                  'payment_amount', 'payment_count', 'buyers', 'avg_order_value', 'net_sales',
                  'refund_amount', 'refund_rate', 'score']
    },
    transaction: {
        label: '成交与付费',
        groups: ['推广指标', '付费报表'],
        columns: ['image', 'title', 'action', 'ad_spend', 'roi', 'paid_ratio',
                  'keyword_spend', 'keyword_roi', 'keyword_visitors',
                  'crowd_spend', 'crowd_roi', 'crowd_visitors',
                  'site_spend', 'site_roi', 'site_visitors',
                  'impressions', 'clicks', 'ctr', 'cpc', 'direct_gmv', 'indirect_gmv']
    }
};

let currentMetricView = 'basic';

// Load config from localStorage
const COL_CONFIG_VERSION = 4;
function loadColumnConfig() {
    const saved = localStorage.getItem('product_col_config');
    if (saved) {
        try {
            const parsed = JSON.parse(saved);
            // Version check: reset if schema changed
            if (parsed.version === COL_CONFIG_VERSION) {
                columnConfig = parsed;
            }
        } catch(e) {}
    }
    // Sync sort config to STATE
    STATE.sortKey = columnConfig.sortKey || 'payment_amount';
    STATE.sortOrder = columnConfig.sortOrder || 'desc';
}

// Save config to localStorage
function saveColumnConfig() {
    columnConfig.version = COL_CONFIG_VERSION;
    localStorage.setItem('product_col_config', JSON.stringify(columnConfig));
}

// Toggle column config panel
function toggleColConfig() {
    const panel = document.getElementById('colConfigPanel');
    panel.classList.toggle('open');
    if (panel.classList.contains('open')) {
        renderColConfigList();
    }
}

// Render column checkboxes grouped by category
function renderColConfigList() {
    const groups = {};
    ALL_COLUMNS.forEach(col => {
        if (!groups[col.group]) groups[col.group] = [];
        groups[col.group].push(col);
    });

    let html = '';
    for (const [groupName, cols] of Object.entries(groups)) {
        html += `<div class="col-config-group-title">${groupName}</div>`;
        cols.forEach(col => {
            html += `<label class="col-config-item">
                <input type="checkbox" ${columnConfig.visible.includes(col.key) ? 'checked' : ''}
                       onchange="toggleColumn('${col.key}')">
                <span>${col.label}</span>
            </label>`;
        });
    }
    document.getElementById('colConfigList').innerHTML = html;
}

// Toggle column visibility
function toggleColumn(key) {
    const idx = columnConfig.visible.indexOf(key);
    if (idx >= 0) columnConfig.visible.splice(idx, 1);
    else columnConfig.visible.push(key);
    saveColumnConfig();
    // Re-render table with current STATE.productData
    if (STATE.productData && STATE.productData.length > 0) {
        renderProductTable();
    }
}

// Save template
function saveTemplate() {
    document.getElementById('templateSaveForm').style.display = 'flex';
    document.getElementById('templateMenu').style.display = 'none';
    document.getElementById('templateName').value = '';
    document.getElementById('templateName').focus();
}

function confirmSaveTemplate() {
    const name = document.getElementById('templateName').value.trim();
    if (!name) return;
    const templates = getTemplates();
    templates[name] = {
        visible: [...columnConfig.visible],
        sortKey: columnConfig.sortKey,
        sortOrder: columnConfig.sortOrder,
    };
    localStorage.setItem('product_templates', JSON.stringify(templates));
    document.getElementById('templateSaveForm').style.display = 'none';
    showToast(`模板"${name}"已保存`, 'success');
}

function cancelSaveTemplate() {
    document.getElementById('templateSaveForm').style.display = 'none';
}

// Load template menu
function loadTemplateMenu() {
    const menu = document.getElementById('templateMenu');
    const templates = getTemplates();
    if (Object.keys(templates).length === 0) {
        menu.innerHTML = '<div style="padding:12px;color:#64748B;font-size:0.82rem;">暂无保存的模板</div>';
    } else {
        menu.innerHTML = Object.entries(templates).map(([name, config]) => `
            <div class="template-item">
                <span onclick="applyTemplate('${name.replace(/'/g, "\\'")}')">${name}</span>
                <button onclick="deleteTemplate('${name.replace(/'/g, "\\'")}')">✕</button>
            </div>
        `).join('');
    }
    menu.style.display = menu.style.display === 'none' ? 'block' : 'none';
    document.getElementById('templateSaveForm').style.display = 'none';
}

function getTemplates() {
    try { return JSON.parse(localStorage.getItem('product_templates') || '{}'); }
    catch(e) { return {}; }
}

function applyTemplate(name) {
    const templates = getTemplates();
    const config = templates[name];
    if (!config) return;
    columnConfig = { ...config };
    saveColumnConfig();
    STATE.sortKey = config.sortKey || 'payment_amount';
    STATE.sortOrder = config.sortOrder || 'desc';
    renderColConfigList();
    if (STATE.productData && STATE.productData.length > 0) {
        renderProductTable();
    }
    document.getElementById('templateMenu').style.display = 'none';
    showToast(`已应用模板"${name}"`, 'success');
}

function deleteTemplate(name) {
    const templates = getTemplates();
    delete templates[name];
    localStorage.setItem('product_templates', JSON.stringify(templates));
    loadTemplateMenu();
    showToast(`模板"${name}"已删除`, 'info');
}

// Get visible columns array
function getVisibleColumns() {
    // 如果当前有指标视图，使用视图定义的列
    const view = METRIC_VIEWS[currentMetricView];
    if (view) {
        return view.columns
            .map(key => ALL_COLUMNS.find(c => c.key === key))
            .filter(Boolean);
    }
    return ALL_COLUMNS.filter(col => columnConfig.visible.includes(col.key));
}

// 切换指标分组视图
function switchMetricView(viewName) {
    currentMetricView = viewName;
    // 更新Tab样式
    document.querySelectorAll('.metric-tab').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.view === viewName);
    });
    STATE.page = 1;
    renderProductTable();
}

// Format cell value based on column type
function formatCellValue(col, product) {
    const val = product[col.key];
    switch (col.type) {
        case 'image':
            if (!val) return '';
            const safeUrl = String(val).replace(/["<>]/g, '');
            return `<img src="${safeUrl}" alt="" loading="lazy" onerror="this.style.display='none'">`;
        case 'money':
            if (val === 0) return '-';
            return fmtWan(val);
        case 'number':
            if (val === 0) return '-';
            return fmtNum(val);
        case 'percent':
            return fmtPct(val);
        case 'decimal':
            if (val == null || isNaN(val)) return '--';
            return Number(val).toFixed(2);
        case 'status':
            const statusMap = {'active': '在售', 'inactive': '下架', 'draft': '草稿'};
            const cls = val === 'active' ? 'status-active' : val === 'inactive' ? 'status-inactive' : 'status-draft';
            return `<span class="status-badge ${cls}">${statusMap[val] || val || '--'}</span>`;
        case 'text':
        default:
            if (val === 'nan' || val === 'null' || val === 'None') return '--';
            return val || '--';
    }
}

// Get cell style based on column type and value
function getCellStyle(col, product) {
    const raw = product[col.key];
    if (col.key === 'bounce_rate' && raw != null && Number(raw) > 0.8) return 'color:var(--danger);font-weight:600';
    if (col.key === 'conversion' && raw != null && Number(raw) < 0.03) return 'color:var(--danger);font-weight:600';
    if (col.key === 'search_ratio' && raw != null && Number(raw) < 0.2) return 'color:var(--warning)';
    if (col.key === 'refund_rate' && raw != null && Number(raw) > 0.2) return 'color:var(--danger);font-weight:600';
    return '';
}

async function loadProducts(dim, period) {
    setLoading('loading-table', true);
    const sort = STATE.sortKey || 'payment_amount';
    const order = STATE.sortOrder || 'desc';
    const offset = (STATE.page - 1) * STATE.pageSize;
    const res = await apiFetch(`/api/products?dim=${dim}&period=${period}&limit=${STATE.pageSize}&offset=${offset}&sort=${sort}&order=${order}`);
    setLoading('loading-table', false);
    // 兼容新旧响应格式：旧格式为数组，新格式为 {data, total}
    const data = Array.isArray(res) ? res : (res.data || []);
    const total = res.total || data.length;
    STATE.totalProducts = total;
    if (!data || data.length === 0) { return; }

    STATE.productData = data;

    // 填充风格筛选下拉
    populateStyleFilter(data);

    // 预加载每个商品的最近运营动作
    loadProductActions(data);

    // --- 商品表格 ---
    renderProductTable();
    syncURL();

    // 加载商品画像标签
    loadProductTags();
}

// 预加载商品运营动作（批量获取）
async function loadProductActions(products) {
    const data = await apiFetch(`/api/actions?dim=${STATE.dim}&period=${STATE.period}&limit=200`);
    if (!data || !Array.isArray(data)) return;

    // 按 product_id 分组，取每个商品最近一条
    const actionMap = {};
    data.forEach(a => {
        const pid = a.product_id;
        if (!pid) return;
        if (!actionMap[pid] || (a.action_date || '') > (actionMap[pid].date || '')) {
            actionMap[pid] = {
                type: a.action_type || '--',
                date: a.action_date || '--',
                detail: a.action_detail || '',
                score: a.effectiveness_score,
                id: a.id,
            };
        }
    });

    // 将最近动作附加到商品数据
    products.forEach(p => {
        p._last_action = actionMap[p.product_id] || null;
    });
}

// 点击"添加动作"→ 变成下拉（预设+自定义），选中即保存
// 点击"✎"→ 编辑已有动作（可改类型、备注、删除）
function startEditAction(productId, isEdit) {
    const tr = document.querySelector(`#productTableBody tr[data-pid="${productId}"]`);
    if (!tr) return;
    const td = tr.querySelector('.td-action');
    if (!td) return;
    const div = td.querySelector('.inline-action');
    if (!div) return;

    const product = (STATE.productData || []).find(p => p.product_id === productId);
    const lastAction = product ? product._last_action : null;
    const editType = (isEdit && lastAction) ? lastAction.type : '';
    const editDetail = (isEdit && lastAction) ? (lastAction.detail || '') : '';

    div.innerHTML = `
        <div class="action-edit-row">
            <select class="action-quick-select" id="aq-sel-${productId}" onchange="onActionSelect('${productId}')">
                <option value="">选择动作...</option>
                <option value="加价" ${editType==='加价'?'selected':''}>加价</option>
                <option value="减价" ${editType==='减价'?'selected':''}>减价</option>
                <option value="换图" ${editType==='换图'?'selected':''}>换图</option>
                <option value="换标题" ${editType==='换标题'?'selected':''}>换标题</option>
                <option value="加SKU" ${editType==='加SKU'?'selected':''}>加SKU</option>
                <option value="优化主图" ${editType==='优化主图'?'selected':''}>优化主图</option>
                <option value="优化详情" ${editType==='优化详情'?'selected':''}>优化详情</option>
                <option value="报名活动" ${editType==='报名活动'?'selected':''}>报名活动</option>
                <option value="__custom__" ${editType && !['加价','减价','换图','换标题','加SKU','优化主图','优化详情','报名活动'].includes(editType)?'selected':''}>自定义...</option>
            </select>
            <input type="text" class="action-custom-input" id="aq-custom-${productId}"
                placeholder="输入自定义动作"
                value="${editType && !['加价','减价','换图','换标题','加SKU','优化主图','优化详情','报名活动'].includes(editType) ? editType : ''}"
                style="display:${editType && !['加价','减价','换图','换标题','加SKU','优化主图','优化详情','报名活动'].includes(editType) ? 'inline-block' : 'none'}">
        </div>
        <div class="action-edit-row" style="margin-top:4px;">
            <input type="text" class="action-detail-input" id="aq-detail-${productId}"
                placeholder="备注（可选）" value="${editDetail}">
            <button class="action-btn save" onclick="saveActionEdit('${productId}')">保存</button>
            <button class="action-btn cancel" onclick="cancelEditAction('${productId}')">取消</button>
            ${isEdit && lastAction && lastAction.id ? `<button class="action-btn del" onclick="deleteAction('${productId}', ${lastAction.id})" title="删除">删除</button>` : ''}
        </div>
    `;
    div.querySelector('.action-quick-select').focus();
}

// 选"自定义..."时显示输入框
function onActionSelect(productId) {
    const sel = document.getElementById(`aq-sel-${productId}`);
    const custom = document.getElementById(`aq-custom-${productId}`);
    if (sel.value === '__custom__') {
        custom.style.display = 'inline-block';
        custom.focus();
    } else {
        custom.style.display = 'none';
    }
}

// 保存动作
async function saveActionEdit(productId) {
    const sel = document.getElementById(`aq-sel-${productId}`);
    const custom = document.getElementById(`aq-custom-${productId}`);
    const detail = document.getElementById(`aq-detail-${productId}`);

    let type = sel.value;
    if (type === '__custom__') {
        type = (custom.value || '').trim();
        if (!type) { showToast('请输入自定义动作', 'error'); custom.focus(); return; }
    }
    if (!type) { showToast('请选择动作类型', 'error'); sel.focus(); return; }

    const payload = {
        product_id: productId,
        action_date: new Date().toISOString().split('T')[0],
        action_type: type,
        action_detail: (detail.value || '').trim() || null,
    };

    try {
        const resp = await fetch('/api/actions', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const result = await resp.json();
        showToast(`${type} 已记录`, 'success');
        // 局部更新：只更新该商品的_last_action，不重建整个表格
        const product = (STATE.productData || []).find(p => p.product_id === productId);
        if (product) {
            product._last_action = {
                type: type,
                date: payload.action_date,
                detail: payload.action_detail || '',
                score: null,
                id: result.id,
            };
        }
        updateActionCell(productId);
    } catch (e) {
        showToast('保存失败: ' + e.message, 'error');
    }
}

// 删除动作
async function deleteAction(productId, actionId) {
    try {
        const resp = await fetch(`/api/actions/${actionId}`, { method: 'DELETE' });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        showToast('动作已删除', 'success');
        // 局部更新：清除该商品的_last_action
        const product = (STATE.productData || []).find(p => p.product_id === productId);
        if (product) product._last_action = null;
        updateActionCell(productId);
    } catch (e) {
        showToast('删除失败: ' + e.message, 'error');
    }
}

// 局部更新单个商品的动作单元格（不重建整个表格）
function updateActionCell(productId) {
    const product = (STATE.productData || []).find(p => p.product_id === productId);
    if (!product) return;
    const lastAction = product._last_action;
    const tr = document.querySelector(`#productTableBody tr[data-pid="${productId}"]`);
    if (!tr) return;
    const td = tr.querySelector('.td-action');
    if (!td) return;
    const div = td.querySelector('.inline-action');
    if (!div) return;

    if (lastAction) {
        const scoreBadge = lastAction.score != null
            ? `<span class="action-score ${lastAction.score > 60 ? 'high' : lastAction.score >= 30 ? 'medium' : 'low'}">${lastAction.score.toFixed(0)}</span>`
            : '';
        div.innerHTML = `<div class="inline-action-summary">
            <span class="action-type-tag">${lastAction.type}</span>
            <span class="action-date">${lastAction.date}</span>
            ${scoreBadge}
            <span class="action-change" onclick="event.stopPropagation();startEditAction('${productId}', true)" title="编辑动作">✎</span>
        </div>`;
    } else {
        div.innerHTML = `<div class="inline-action-empty" onclick="startEditAction('${productId}')">
            <span class="action-add-icon">＋</span> 添加动作
        </div>`;
    }
}

// 合计行
function renderSummaryRow(pageData, visibleCols) {
    const existing = document.querySelector('.tfoot-summary');
    if (existing) existing.remove();
    if (!pageData || pageData.length === 0) return;

    const metricCols = visibleCols.filter(c => c.key !== 'image' && c.key !== 'title');
    const sums = {};
    metricCols.forEach(col => {
        if (col.type === 'number' || col.type === 'money') {
            sums[col.key] = pageData.reduce((s, p) => s + (Number(p[col.key]) || 0), 0);
        }
    });

    const fmt = (v) => {
        if (v == null || isNaN(v)) return '--';
        if (Math.abs(v) >= 10000) return (v / 10000).toFixed(1) + '万';
        return v.toLocaleString('zh-CN', { maximumFractionDigits: 0 });
    };

    let cells = '<td></td><td>合计 (' + pageData.length + '款)</td>';
    metricCols.forEach(col => {
        if (sums[col.key] !== undefined) {
            cells += `<td class="text-right">${fmt(sums[col.key])}</td>`;
        } else {
            cells += '<td></td>';
        }
    });

    const tbody = document.getElementById('productTableBody');
    const tfoot = document.createElement('tfoot');
    tfoot.className = 'tfoot-summary';
    tfoot.innerHTML = `<tr>${cells}</tr>`;
    tbody.parentNode.appendChild(tfoot);
}

// 重置筛选
function resetFilters() {
    document.getElementById('productSearch').value = '';
    document.getElementById('productTierFilter').value = '';
    document.getElementById('productStyleFilter').value = '';
    document.getElementById('productStatusFilter').value = '';
    STATE.searchText = '';
    STATE.tierFilter = '';
    STATE.styleFilter = '';
    STATE.statusFilter = '';
    updateFilterChips();
    applyTableFilters();
}

// 筛选条件Chips
function updateFilterChips() {
    const container = document.getElementById('filterChips');
    if (!container) return;
    const chips = [];
    const search = document.getElementById('productSearch').value.trim();
    const tier = document.getElementById('productTierFilter').value;
    const style = document.getElementById('productStyleFilter').value;
    const status = document.getElementById('productStatusFilter').value;

    if (search) chips.push({ label: '搜索:' + search, clear: () => { document.getElementById('productSearch').value = ''; STATE.searchText = ''; } });
    if (tier) chips.push({ label: '分层:' + tier, clear: () => { document.getElementById('productTierFilter').value = ''; STATE.tierFilter = ''; } });
    if (style) chips.push({ label: '风格:' + style, clear: () => { document.getElementById('productStyleFilter').value = ''; STATE.styleFilter = ''; } });
    if (status) {
        const statusLabel = status === 'active' ? '在售' : '下架';
        chips.push({ label: '状态:' + statusLabel, clear: () => { document.getElementById('productStatusFilter').value = ''; STATE.statusFilter = ''; } });
    }

    if (chips.length === 0) {
        container.style.display = 'none';
        return;
    }
    container.style.display = 'flex';
    container.innerHTML = chips.map((c, i) =>
        `<span class="filter-chip">${c.label}<span class="chip-remove" onclick="clearFilterChip(${i})">x</span></span>`
    ).join('');
    // 存储clear函数
    container._chips = chips;
}

function clearFilterChip(idx) {
    const container = document.getElementById('filterChips');
    if (container && container._chips && container._chips[idx]) {
        container._chips[idx].clear();
        updateFilterChips();
        applyTableFilters();
    }
}

// 星标收藏
async function toggleStar(productId, el) {
    const res = await apiFetch('/api/star', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ product_id: productId })
    });
    if (res && res.starred !== undefined) {
        if (res.starred) {
            el.className = 'star-btn starred';
            el.innerHTML = '&#9733;';
            el.title = '取消收藏';
            showToast('已收藏', 'success', 1500);
        } else {
            el.className = 'star-btn';
            el.innerHTML = '&#9734;';
            el.title = '收藏';
            showToast('已取消收藏', 'info', 1500);
        }
        if (STATE.productData) {
            const item = STATE.productData.find(p => p.product_id === productId);
            if (item) item.starred = res.starred;
        }
    }
}

// 空数据列自动隐藏
function autoHideEmptyColumns(pageData, visibleCols) {
    if (!pageData || pageData.length === 0) return;
    const metricCols = visibleCols.filter(c => c.key !== 'image' && c.key !== 'title' && c.key !== 'rank' && c.key !== 'action');
    metricCols.forEach(col => {
        const allEmpty = pageData.every(p => {
            const v = p[col.key];
            return v === null || v === undefined || v === 0 || v === '0' || v === '--' || v === 'nan';
        });
        const ths = document.querySelectorAll(`th[data-col="${col.key}"]`);
        ths.forEach(th => th.style.display = allEmpty ? 'none' : '');
        const tds = document.querySelectorAll(`td[data-col="${col.key}"]`);
        tds.forEach(td => td.style.display = allEmpty ? 'none' : '');
    });
}

// 批量勾选
function toggleSelectAll(checked) {
    document.querySelectorAll('.row-check').forEach(cb => cb.checked = checked);
    updateBatchBar();
}

function updateSelectAll() {
    const all = document.querySelectorAll('.row-check');
    const checked = document.querySelectorAll('.row-check:checked');
    const selectAll = document.getElementById('selectAll');
    if (selectAll) selectAll.checked = all.length > 0 && all.length === checked.length;
    updateBatchBar();
}

function getSelectedIds() {
    return Array.from(document.querySelectorAll('.row-check:checked')).map(cb => cb.value);
}

function updateBatchBar() {
    const ids = getSelectedIds();
    const bar = document.getElementById('batchBar');
    if (!bar) return;
    if (ids.length === 0) {
        bar.style.display = 'none';
    } else {
        bar.style.display = 'flex';
        bar.querySelector('.batch-count').textContent = `已选 ${ids.length} 项`;
    }
}

function batchStar() {
    const ids = getSelectedIds();
    if (ids.length === 0) return;
    Promise.all(ids.map(pid =>
        apiFetch('/api/star', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ product_id: pid })
        })
    )).then(() => {
        if (STATE.productData) {
            STATE.productData.forEach(p => {
                if (ids.includes(p.product_id)) p.starred = 1;
            });
        }
        applyTableFilters();
        document.querySelectorAll('.row-check').forEach(cb => cb.checked = false);
        updateBatchBar();
        showToast(`已收藏 ${ids.length} 件商品`, 'success', 2000);
    }).catch(function(e) {
        showToast('批量收藏失败: ' + (e.message || '未知错误'), 'error');
    });
}

function batchEditField(field) {
    const ids = getSelectedIds();
    if (ids.length === 0) { showToast('请先勾选商品', 'warning'); return; }
    const options = field === 'tier'
        ? ['利润款', '引流款', '新品', '新品主推']
        : ['中古风', 'IP', '乔迁', '奶油', '轻奢'];
    const label = field === 'tier' ? '分层' : '风格';
    // 创建内联选择弹窗
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.style.display = 'flex';
    overlay.innerHTML = `
        <div style="background:var(--bg-card);border-radius:12px;padding:24px;min-width:300px;box-shadow:0 8px 32px rgba(0,0,0,0.4);">
            <h3 style="margin-bottom:16px;color:var(--text-primary);">批量修改${label}（${ids.length}件）</h3>
            <select id="batchEditSelect" style="width:100%;padding:8px 12px;border-radius:6px;border:1px solid var(--border);background:var(--bg-elevated);color:var(--text-primary);font-size:0.9rem;margin-bottom:16px;">
                <option value="">请选择${label}</option>
                ${options.map(o => `<option value="${o}">${o}</option>`).join('')}
            </select>
            <div style="display:flex;gap:8px;justify-content:flex-end;">
                <button onclick="this.closest('.modal-overlay').remove()" style="padding:6px 16px;border-radius:6px;border:1px solid var(--border);background:transparent;color:var(--text-secondary);cursor:pointer;">取消</button>
                <button onclick="confirmBatchEdit('${field}', ${JSON.stringify(ids)})" style="padding:6px 16px;border-radius:6px;border:none;background:var(--accent);color:#fff;cursor:pointer;">确认</button>
            </div>
        </div>
    `;
    document.body.appendChild(overlay);
}

async function confirmBatchEdit(field, ids) {
    const val = document.getElementById('batchEditSelect').value;
    if (!val) { showToast('请选择一个值', 'warning'); return; }
    const res = await apiFetch('/api/batch_update', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ field, value: val, product_ids: ids })
    });
    if (res && res.success) {
        showToast(`已更新 ${ids.length} 件商品`, 'success');
        document.querySelector('.modal-overlay')?.remove();
        loadProducts(STATE.dim, STATE.period);
    } else {
        showToast('更新失败', 'error');
    }
}

// 只看收藏筛选
function toggleStarFilter() {
    STATE.starFilter = !STATE.starFilter;
    const btn = document.getElementById('starFilterBtn');
    if (STATE.starFilter) {
        btn.classList.add('active');
        btn.innerHTML = '&#9733; 只看收藏';
    } else {
        btn.classList.remove('active');
        btn.innerHTML = '&#9734; 只看收藏';
    }
    applyTableFilters();
}

// 取消编辑
function cancelEditAction(productId) {
    const product = (STATE.productData || []).find(p => p.product_id === productId);
    const lastAction = product ? product._last_action : null;
    const div = document.querySelector(`#productTableBody tr .td-action .inline-action`);
    if (!div) return;

    if (lastAction) {
        const scoreBadge = lastAction.score != null
            ? `<span class="action-score ${lastAction.score > 60 ? 'high' : lastAction.score >= 30 ? 'medium' : 'low'}">${lastAction.score.toFixed(0)}</span>`
            : '';
        div.innerHTML = `<div class="inline-action-summary">
            <span class="action-type-tag">${lastAction.type}</span>
            <span class="action-date">${lastAction.date}</span>
            ${scoreBadge}
            <span class="action-change" onclick="event.stopPropagation();startEditAction('${productId}', true)" title="编辑动作">✎</span>
        </div>`;
    } else {
        div.innerHTML = `<div class="inline-action-empty" onclick="startEditAction('${productId}')">
            <span class="action-add-icon">＋</span> 添加动作
        </div>`;
    }
}

// 行展开详情
function toggleRowDetail(pid, tr) {
    const detail = document.getElementById('detail-' + pid);
    if (!detail) return;
    const isVisible = detail.style.display !== 'none';
    // 关闭所有其他详情行
    document.querySelectorAll('.detail-row').forEach(r => r.style.display = 'none');
    if (!isVisible) {
        detail.style.display = 'table-row';
        // 加载备注
        loadProductNotes(pid);
    }
}

async function loadProductNotes(productId) {
    const listEl = document.getElementById('notes-list-' + productId);
    if (!listEl) return;
    try {
        const notes = await apiFetch(`/api/notes/${productId}`);
        if (!notes || !Array.isArray(notes)) {
            listEl.innerHTML = '<div style="color:var(--text-muted);font-size:0.8rem;">暂无备注</div>';
            return;
        }
        if (notes.length === 0) {
            listEl.innerHTML = '<div style="color:var(--text-muted);font-size:0.8rem;">暂无备注</div>';
            return;
        }
        listEl.innerHTML = notes.map(n => `
            <div class="note-item">
                <span class="note-text">${escapeHtml(n.note)}</span>
                <span class="note-time">${n.created_at || ''}</span>
                <span class="note-delete" onclick="event.stopPropagation();deleteProductNote(${n.id},'${productId}')" title="删除">&times;</span>
            </div>
        `).join('');
    } catch (e) {
        listEl.innerHTML = '<div style="color:var(--text-muted);font-size:0.8rem;">加载失败</div>';
    }
}

async function addProductNote(productId) {
    const input = document.getElementById('note-input-' + productId);
    if (!input) return;
    const text = input.value.trim();
    if (!text) return;
    const res = await apiFetch('/api/notes', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ product_id: productId, note: text })
    });
    if (res && res.success) {
        input.value = '';
        loadProductNotes(productId);
    } else {
        showToast('添加备注失败', 'error');
    }
}

async function deleteProductNote(noteId, productId) {
    const res = await apiFetch(`/api/notes/${noteId}`, { method: 'DELETE' });
    if (res && res.success) {
        loadProductNotes(productId);
    } else {
        showToast('删除备注失败', 'error');
    }
}

function buildRowDetailContent(p) {
    const items = [
        { label: '支付金额', value: fmtWan(p.payment_amount) },
        { label: '支付件数', value: fmtNum(p.payment_count) },
        { label: '访客数', value: fmtNum(p.visitors) },
        { label: '转化率', value: fmtPct(p.conversion) },
        { label: '客单价', value: fmtWan(p.avg_order_value) },
        { label: 'ROI', value: p.roi != null ? Number(p.roi).toFixed(2) : '--' },
        { label: '推广花费', value: fmtWan(p.ad_spend) },
        { label: '退款率', value: fmtPct(p.refund_rate) },
        { label: '退款金额', value: fmtWan(p.refund_amount) },
        { label: '加购率', value: fmtPct(p.cart_rate) },
        { label: '收藏率', value: fmtPct(p.fav_rate) },
        { label: '搜索占比', value: fmtPct(p.search_ratio) },
        { label: '浏览量', value: fmtNum(p.page_views) },
        { label: '净销售额', value: fmtWan(p.net_sales) },
        { label: '分层', value: p.tier || '--' },
        { label: '风格', value: p.style || '--' },
    ];
    const metricsHtml = items.map(item =>
        `<div class="row-detail-item"><span class="row-detail-label">${item.label}</span><span class="row-detail-value">${item.value}</span></div>`
    ).join('');

    // 备注区域
    const notesHtml = `
        <div class="product-notes-section" style="grid-column: 1 / -1; border-top: 1px solid var(--border); padding-top: 12px; margin-top: 4px;">
            <div style="font-size: 0.85rem; font-weight: 600; color: var(--text-primary); margin-bottom: 8px;">商品备注</div>
            <div id="notes-list-${p.product_id}" class="notes-list">
                <div style="color:var(--text-muted);font-size:0.8rem;">加载中...</div>
            </div>
            <div class="note-input-row">
                <input type="text" id="note-input-${p.product_id}" placeholder="添加备注..." onkeydown="if(event.key==='Enter')addProductNote('${p.product_id}')">
                <button onclick="addProductNote('${p.product_id}')" style="padding:4px 12px;border-radius:4px;border:none;background:var(--accent);color:#fff;cursor:pointer;font-size:0.8rem;">添加</button>
            </div>
        </div>
    `;

    return metricsHtml + notesHtml;
}

/**
 * 构建单行商品表格行 HTML
 * @param {Object} p - 商品数据对象
 * @param {number} rank - 当前排名序号
 * @param {Array} metricCols - 指标列配置数组
 * @param {Array} visibleCols - 可见列配置数组（保留参数，便于扩展）
 * @returns {string} <tr>...</tr> HTML 字符串
 */
function buildProductRow(p, rank, metricCols, visibleCols) {
    // Top3色标
    let rankHtml;
    if (rank === 1) rankHtml = '<span class="rank-badge rank-1">1</span>';
    else if (rank === 2) rankHtml = '<span class="rank-badge rank-2">2</span>';
    else if (rank === 3) rankHtml = '<span class="rank-badge rank-3">3</span>';
    else rankHtml = `<span class="rank-badge rank-normal">${rank}</span>`;

    const imgUrl = p.image_url || '';
    const title = escapeHtml(p.title || '--');
    const shortTitle = title.length > 14 ? title.substring(0, 14) + '...' : title;
    const pid = (p.product_id || '').replace(/'/g, "\\'");
    const isStarred = p.starred == 1;
    const starIcon = isStarred ? '<span class="star-btn starred" onclick="event.stopPropagation();toggleStar(\'' + pid + '\',this)" title="取消收藏">&#9733;</span>' : '<span class="star-btn" onclick="event.stopPropagation();toggleStar(\'' + pid + '\',this)" title="收藏">&#9734;</span>';
    // 商品画像标签
    const tagColors = {'爆款':'#EF4444','潜力款':'#3B82F6','衰退款':'#F59E0B','滞销款':'#6B7280','高退款':'#DC2626','高ROI':'#10B981'};
    const tags = p._tags || [];
    const tagBadges = tags.map(t => {
        const c = tagColors[t] || '#8B5CF6';
        return `<span class="tag-badge" style="background:${c}">${t}</span>`;
    }).join('');
    const addTagBtn = `<span class="tag-add-btn" onclick="event.stopPropagation();showAddTagDialog('${pid}')" title="添加标签">+</span>`;
    const tagsHtml = tagBadges ? `<div class="tag-badges-row">${tagBadges}${addTagBtn}</div>` : `<div class="tag-badges-row">${addTagBtn}</div>`;
    const productCell = `<td class="td-product"><div class="product-cell-inner">${starIcon}${imgUrl ? `<img src="${imgUrl}" alt="" loading="lazy" onerror="this.style.display='none'">` : '<div class="product-img-placeholder">📦</div>'}<div class="product-info"><span class="product-title-text" title="${title}">${shortTitle}</span><span class="product-id-text">${escapeHtml(p.product_id || '--')}</span>${tagsHtml}</div></div></td>`;

    const cells = metricCols.map(col => {
        const style = getCellStyle(col, p);
        const value = formatCellValue(col, p);
        const rawVal = p[col.key];
        const alignCls = (col.type === 'money' || col.type === 'number' || col.type === 'percent' || col.type === 'decimal') ? ' text-right' : '';
        // 运营动作列：点击即编辑，一步保存
        if (col.key === 'action') {
            const lastAction = p._last_action || null;
            let actionHtml = '<td class="td-action"><div class="inline-action">';
            if (lastAction) {
                const scoreBadge = lastAction.score != null
                    ? `<span class="action-score ${lastAction.score > 60 ? 'high' : lastAction.score >= 30 ? 'medium' : 'low'}">${lastAction.score.toFixed(0)}</span>`
                    : '';
                actionHtml += `<div class="inline-action-summary">
                    <span class="action-type-tag">${lastAction.type}</span>
                    <span class="action-date">${lastAction.date}</span>
                    ${scoreBadge}
                    <span class="action-change" onclick="event.stopPropagation();startEditAction('${pid}')" title="更换动作">✎</span>
                </div>`;
            } else {
                actionHtml += `<div class="inline-action-empty" onclick="event.stopPropagation();startEditAction('${pid}')">
                    <span class="action-add-icon">＋</span> 添加动作
                </div>`;
            }
            actionHtml += '</div></td>';
            return actionHtml;
        }
        // 评分列用圆形徽章（综合评分0-100）
        if (col.key === 'score' && rawVal != null && !isNaN(rawVal)) {
            const scoreVal = Number(rawVal);
            const badgeColor = scoreVal >= 80 ? '#22C55E' : scoreVal >= 60 ? '#3B82F6' : scoreVal >= 40 ? '#F59E0B' : '#EF4444';
            return `<td class="text-right"><span class="score-badge-circle" style="background:${badgeColor}">${scoreVal}</span></td>`;
        }
        // 百分比列用迷你进度条
        if (col.type === 'percent' && rawVal != null && !isNaN(rawVal)) {
            const pctVal = Number(rawVal) * 100;
            const barColor = pctVal > 10 ? '#22C55E' : pctVal > 3 ? '#3B82F6' : pctVal > 0 ? '#F59E0B' : '#475569';
            let cellHtml = `<td class="text-right"><div class="cell-with-bar"><span>${value}</span><div class="mini-bar"><div class="mini-bar-fill" style="width:${Math.min(pctVal, 100)}%;background:${barColor}"></div></div></div>`;
            // 月度维度下显示环比变化
            if (STATE.dim === 'monthly' && p.changes) {
                const changeKeyMap = { 'payment_amount': 'payment_amount', 'visitors': 'visitors', 'conversion': 'payment_conversion', 'refund_rate': 'refund_rate', 'uv_value': 'uv_value' };
                const changeKey = changeKeyMap[col.key];
                if (changeKey) {
                    const changeVal = p.changes[changeKey];
                    if (changeVal !== null && changeVal !== undefined) {
                        const cls = changeVal > 0 ? 'change-up' : changeVal < 0 ? 'change-down' : 'change-flat';
                        const arrow = changeVal > 0 ? '\u2191' : changeVal < 0 ? '\u2193' : '\u2192';
                        cellHtml += `<span class="change-tag ${cls}">${arrow}${Math.abs(changeVal)}%</span>`;
                    }
                }
            }
            cellHtml += '</div></td>';
            return cellHtml;
        }
        // 通用单元格：月度维度下为关键指标添加环比变化
        let cellContent = value;
        if (STATE.dim === 'monthly' && p.changes) {
            const changeKeyMap = { 'payment_amount': 'payment_amount', 'visitors': 'visitors', 'conversion': 'payment_conversion', 'refund_rate': 'refund_rate', 'uv_value': 'uv_value' };
            const changeKey = changeKeyMap[col.key];
            if (changeKey) {
                const changeVal = p.changes[changeKey];
                if (changeVal !== null && changeVal !== undefined) {
                    const cls = changeVal > 0 ? 'change-up' : changeVal < 0 ? 'change-down' : 'change-flat';
                    const arrow = changeVal > 0 ? '\u2191' : changeVal < 0 ? '\u2193' : '\u2192';
                    cellContent += `<span class="change-tag ${cls}">${arrow}${Math.abs(changeVal)}%</span>`;
                }
            }
        }
        return `<td class="${alignCls}" data-col="${col.key}" style="${style}">${cellContent}</td>`;
    }).join('');

    return `<tr data-pid="${p.product_id}" onclick="toggleRowDetail('${p.product_id}', this)" style="cursor:pointer"><td class="td-rank">${rankHtml}<input type="checkbox" class="row-check" value="${p.product_id}" onchange="updateSelectAll()" onclick="event.stopPropagation()"></td>${productCell}${cells}</tr>` +
        `<tr class="detail-row" id="detail-${p.product_id}" style="display:none"><td colspan="99"><div class="row-detail-content">${buildRowDetailContent(p)}</div></td></tr>`;
}

function normalizeProductTableHeader(visibleCols) {
    const table = document.getElementById('productTable');
    const thead = document.getElementById('productTableHead');
    if (!table || !thead) return;

    const rows = thead.querySelectorAll('tr');
    if (rows.length < 2) return;
    const groupRow = rows[0];
    const headerRow = rows[1];
    const frozenGroupCells = Array.from(groupRow.children).slice(0, 2);
    const frozenHeaderCells = Array.from(headerRow.children).slice(0, 2);

    // The first two cells are structural columns, so they must span both rows.
    frozenGroupCells.forEach((cell, index) => {
        cell.rowSpan = 2;
        cell.dataset.col = index === 0 ? 'rank' : 'product';
        if (frozenHeaderCells[index]) {
            const checkbox = frozenHeaderCells[index].querySelector('input');
            if (checkbox && index === 0 && !cell.querySelector('input')) cell.appendChild(checkbox);
            frozenHeaderCells[index].remove();
        }
    });

    const metricCols = visibleCols.filter(col => col.key !== 'image' && col.key !== 'title');
    const oldColgroup = table.querySelector(':scope > colgroup');
    if (oldColgroup) oldColgroup.remove();
    const colgroup = document.createElement('colgroup');
    const rankCol = document.createElement('col');
    rankCol.className = 'col-rank';
    rankCol.style.width = 'var(--product-rank-width)';
    const productCol = document.createElement('col');
    productCol.className = 'col-product';
    productCol.style.width = 'var(--product-info-width)';
    colgroup.append(rankCol, productCol);
    metricCols.forEach(col => {
        const metricCol = document.createElement('col');
        metricCol.dataset.col = col.key;
        metricCol.style.width = col.key === 'action' ? '190px' : '108px';
        colgroup.appendChild(metricCol);
    });
    table.insertBefore(colgroup, thead);
}

function renderProductTable() {
    const { productData, sortKey, sortOrder, page, pageSize } = STATE;
    const visibleCols = getVisibleColumns();

    // 服务端分页：数据已经是当前页的数据，无需客户端排序/切片
    const total = STATE.totalProducts || productData.length;
    const totalPages = Math.max(1, Math.ceil(total / pageSize));
    const startIdx = (page - 1) * pageSize;
    const pageData = productData;

    // ---- 双层表头 ----
    const thead = document.getElementById('productTableHead');
    if (thead) {
        // 分组色带行 + 列头行
        const groupColors = {
            '基础信息': 'rgba(148,163,184,0.08)',
            '流量指标': 'rgba(236,72,153,0.08)',
            '转化指标': 'rgba(236,72,153,0.12)',
            '交易指标': 'rgba(59,130,246,0.08)',
            '退款指标': 'rgba(239,68,68,0.08)',
            '推广指标': 'rgba(59,130,246,0.12)',
            '付费报表': 'rgba(99,102,241,0.08)',
            '客户指标': 'rgba(16,185,129,0.08)',
            '引潜指标': 'rgba(245,158,11,0.08)',
            '评分': 'rgba(139,92,246,0.08)',
        };

        // 构建分组行和列头行
        let groupRowHtml = '<th class="th-rank th-sticky-left-1">全选</th><th class="th-product th-sticky-left-2">商品信息</th>';
        let headerRowHtml = '<th class="th-sticky-left-1"><input type="checkbox" id="selectAll" onchange="toggleSelectAll(this.checked)" title="全选"></th><th class="th-sticky-left-2"></th>';
        let currentGroup = '';
        let groupSpan = 0;

        // 跳过 image 和 title 列（已合并到"商品信息"列）
        const metricCols = visibleCols.filter(c => c.key !== 'image' && c.key !== 'title');

        metricCols.forEach((col, idx) => {
            const isSorted = sortKey === col.key;
            const arrow = isSorted ? (sortOrder === 'asc' ? '▲' : '▼') : '▲▼';
            const sortedCls = isSorted ? ' sorted' : '';
            const alignCls = (col.type === 'money' || col.type === 'number' || col.type === 'percent' || col.type === 'decimal') ? ' text-right' : '';

            // 分组行
            if (col.group !== currentGroup) {
                if (currentGroup && groupSpan > 0) {
                    groupRowHtml += `<th colspan="${groupSpan}" class="th-group" style="background:${groupColors[currentGroup] || 'transparent'}">${currentGroup}</th>`;
                }
                currentGroup = col.group;
                groupSpan = 1;
            } else {
                groupSpan++;
            }

            // 列头行（带排序和筛选图标）
            const filterIcon = (col.type === 'text' && col.key !== 'image') ? '<span class="col-filter-icon" onclick="event.stopPropagation();toggleColFilter(\'' + col.key + '\')">▾</span>' : '';
            headerRowHtml += `<th class="th-col${alignCls}${sortedCls}" data-key="${col.key}" data-col="${col.key}" onclick="sortTable('${col.key}')" style="${currentGroup ? 'border-top:2px solid ' + (groupColors[currentGroup] ? groupColors[currentGroup].replace(/[\d.]+\)$/, '0.25)') : 'transparent') : ''}">${col.label} <span class="sort-arrows">${arrow}</span>${filterIcon}</th>`;
        });
        // 最后一个分组
        if (currentGroup && groupSpan > 0) {
            groupRowHtml += `<th colspan="${groupSpan}" class="th-group" style="background:${groupColors[currentGroup] || 'transparent'}">${currentGroup}</th>`;
        }

        thead.innerHTML = `<tr class="group-row">${groupRowHtml}</tr><tr class="header-row">${headerRowHtml}</tr>`;
        normalizeProductTableHeader(visibleCols);
    }

    // ---- 渲染行 ----
    const tbody = document.getElementById('productTableBody');
    const metricCols = visibleCols.filter(c => c.key !== 'image' && c.key !== 'title');
    tbody.innerHTML = pageData.map((p, i) => {
        const rank = startIdx + i + 1;
        return buildProductRow(p, rank, metricCols, visibleCols);
    }).join('');

    // 合计行
    renderSummaryRow(pageData, visibleCols);

    // 空数据列自动隐藏
    // Keep the configured view grid intact. Hiding individual cells leaves
    // colgroup tracks behind and makes a fixed-layout table misalign.

    // 加载更多按钮（追加到表格底部）
    if (page * pageSize < total) {
        var loadMoreRow = document.createElement('tr');
        loadMoreRow.innerHTML = '<td colspan="99" style="text-align:center;padding:12px;"><button class="load-more-btn" onclick="loadMoreProducts()">加载更多（剩余 ' + (total - page * pageSize) + ' 件）</button></td>';
        tbody.appendChild(loadMoreRow);
    }

    // 显示商品总数
    var totalEl = document.getElementById('productTotal');
    if (totalEl) totalEl.textContent = '共 ' + total + ' 件商品';

    // 翻页控件
    const pagEl = document.getElementById('tablePagination');
    pagEl.innerHTML = `
        <button ${page <= 1 ? 'disabled' : ''} onclick="goPage(${page - 1})">上一页</button>
        <span class="page-info">${page} / ${totalPages}（共${total}条）</span>
        <input type="number" class="page-jump" min="1" max="${totalPages}" placeholder="跳转" onkeydown="if(event.key==='Enter')goPage(Math.max(1,Math.min(${totalPages},Number(this.value))))" style="width:52px;padding:3px 6px;border-radius:4px;border:1px solid var(--border);background:var(--bg-card);color:var(--text-primary);font-size:0.78rem;text-align:center;">
        <button ${page >= totalPages ? 'disabled' : ''} onclick="goPage(${page + 1})">下一页</button>
    `;

    // 更新排序箭头样式
    document.querySelectorAll('#productTable .header-row th').forEach(th => {
        const key = th.dataset.key;
        const arrows = th.querySelector('.sort-arrows');
        if (!arrows) return;
        if (key === sortKey) {
            th.classList.add('sorted');
            arrows.innerHTML = sortOrder === 'asc' ? '<span class="arrow-active asc">▲</span><span>▼</span>' : '<span>▲</span><span class="arrow-active desc">▼</span>';
        } else {
            th.classList.remove('sorted');
            arrows.innerHTML = '<span>▲</span><span>▼</span>';
        }
    });

    // 初始化列宽拖拽
    initColumnResize();
    // 绑定行内编辑事件
    bindInlineEditEvents();
    // 更新横向滚动指示器
    updateScrollIndicators();
}

// 列筛选弹窗
function toggleColFilter(key) {
    // 收集该列所有唯一值
    const vals = new Set();
    (STATE.productData || []).forEach(p => {
        const v = p[key];
        if (v != null && v !== '') vals.add(v);
    });
    const sorted = [...vals].sort();

    // 移除已有弹窗
    const existing = document.getElementById('colFilterPopup');
    if (existing) existing.remove();

    const th = document.querySelector(`th[data-key="${key}"]`);
    if (!th) return;
    const rect = th.getBoundingClientRect();
    const wrapper = document.querySelector('.table-wrapper');
    const wrapperRect = wrapper.getBoundingClientRect();

    const popup = document.createElement('div');
    popup.id = 'colFilterPopup';
    popup.className = 'col-filter-popup';
    popup.innerHTML = `
        <div class="col-filter-header">
            <input type="text" class="col-filter-search" placeholder="搜索..." oninput="filterColFilterOptions(this.value)">
            <button class="col-filter-clear" onclick="clearColFilter('${key}')">清除筛选</button>
        </div>
        <div class="col-filter-options">
            <label class="col-filter-option"><input type="checkbox" checked onchange="applyColFilter('${key}')"> 全部</label>
            ${sorted.slice(0, 50).map(v => `<label class="col-filter-option"><input type="checkbox" value="${String(v).replace(/"/g, '&quot;')}" onchange="applyColFilter('${key}')"> ${v}</label>`).join('')}
            ${sorted.length > 50 ? `<div style="color:#64748B;font-size:0.75rem;padding:4px 8px;">仅显示前50项...</div>` : ''}
        </div>
    `;
    popup.style.left = (rect.left - wrapperRect.left) + 'px';
    popup.style.top = (rect.bottom - wrapperRect.top + 4) + 'px';
    wrapper.style.position = 'relative';
    wrapper.appendChild(popup);

    // 点击外部关闭
    setTimeout(() => {
        document.addEventListener('click', function closeFilter(e) {
            if (!popup.contains(e.target) && !th.contains(e.target)) {
                popup.remove();
                document.removeEventListener('click', closeFilter);
            }
        });
    }, 10);
}

function filterColFilterOptions(query) {
    const options = document.querySelectorAll('#colFilterPopup .col-filter-option');
    options.forEach(opt => {
        const text = opt.textContent.toLowerCase();
        opt.style.display = text.includes(query.toLowerCase()) ? '' : 'none';
    });
}

function applyColFilter(key) {
    const popup = document.getElementById('colFilterPopup');
    if (!popup) return;
    const checkboxes = popup.querySelectorAll('.col-filter-options input[type="checkbox"]:checked');
    const allCheckbox = popup.querySelector('.col-filter-options input[type="checkbox"]:first-child');
    const values = [];
    checkboxes.forEach(cb => { if (cb !== allCheckbox) values.push(cb.value); });

    if (allCheckbox && allCheckbox.checked) {
        STATE.colFilters = STATE.colFilters || {};
        delete STATE.colFilters[key];
    } else {
        STATE.colFilters = STATE.colFilters || {};
        STATE.colFilters[key] = values;
    }
    STATE.page = 1;
    applyTableFilters();
    popup.remove();
}

function clearColFilter(key) {
    STATE.colFilters = STATE.colFilters || {};
    delete STATE.colFilters[key];
    STATE.page = 1;
    applyTableFilters();
    const popup = document.getElementById('colFilterPopup');
    if (popup) popup.remove();
}

function applyTableFilters() {
    let data = STATE.productData || [];
    const filters = STATE.colFilters || {};
    for (const [key, values] of Object.entries(filters)) {
        if (values && values.length > 0) {
            data = data.filter(p => values.includes(String(p[key] ?? '')));
        }
    }
    // 星标过滤
    if (STATE.starFilter) {
        data = data.filter(p => p.starred == 1);
    }
    updateFilterChips();
    // 重新排序和分页渲染（不重新请求API）
    const { sortKey, sortOrder, page, pageSize } = STATE;
    const sorted = [...data].sort((a, b) => {
        let va = a[sortKey], vb = b[sortKey];
        if (va == null) va = 0;
        if (vb == null) vb = 0;
        if (typeof va === 'string') return sortOrder === 'asc' ? va.localeCompare(vb) : vb.localeCompare(va);
        return sortOrder === 'asc' ? va - vb : vb - va;
    });
    const total = sorted.length;
    const totalPages = Math.max(1, Math.ceil(total / pageSize));
    const startIdx = (Math.min(page, totalPages) - 1) * pageSize;
    const pageData = sorted.slice(startIdx, startIdx + pageSize);

    const visibleCols = getVisibleColumns();
    const metricCols = visibleCols.filter(c => c.key !== 'image' && c.key !== 'title');
    const tbody = document.getElementById('productTableBody');
    tbody.innerHTML = pageData.map((p, i) => {
        const rank = startIdx + i + 1;
        return buildProductRow(p, rank, metricCols, visibleCols);
    }).join('');

    renderSummaryRow(pageData, visibleCols);

    const pagEl = document.getElementById('tablePagination');
    pagEl.innerHTML = `
        <button ${page <= 1 ? 'disabled' : ''} onclick="goPage(${page - 1})">上一页</button>
        <span class="page-info">${Math.min(page, totalPages)} / ${totalPages}（共${total}条）</span>
        <button ${page >= totalPages ? 'disabled' : ''} onclick="goPage(${page + 1})">下一页</button>
    `;
}

function sortTable(key) {
    if (STATE.sortKey === key) {
        STATE.sortOrder = STATE.sortOrder === 'asc' ? 'desc' : 'asc';
    } else {
        STATE.sortKey = key;
        STATE.sortOrder = key === 'title' || key === 'style' ? 'asc' : 'desc';
    }
    // Sync to columnConfig
    columnConfig.sortKey = STATE.sortKey;
    columnConfig.sortOrder = STATE.sortOrder;
    saveColumnConfig();
    STATE.page = 1;
    // 服务端排序：重新请求数据
    loadProducts(STATE.dim, STATE.period);
}

function goPage(p) {
    var total = STATE.totalProducts || 0;
    var totalPages = Math.ceil(total / STATE.pageSize);
    if (p < 1) p = 1;
    if (totalPages > 0 && p > totalPages) p = totalPages;
    STATE.page = p;
    loadProducts(STATE.dim, STATE.period);
}

// 加载更多商品（追加到当前表格）
async function loadMoreProducts() {
    STATE.page++;
    var dim = STATE.dim;
    var period = STATE.period;
    var sort = STATE.sortKey || 'payment_amount';
    var order = STATE.sortOrder || 'desc';
    var offset = (STATE.page - 1) * STATE.pageSize;

    var url = '/api/products?dim=' + dim + '&period=' + period + '&limit=' + STATE.pageSize + '&offset=' + offset + '&sort=' + sort + '&order=' + order;
    // 添加现有筛选条件
    var tier = document.getElementById('productTierFilter') ? document.getElementById('productTierFilter').value : '';
    var style = document.getElementById('productStyleFilter') ? document.getElementById('productStyleFilter').value : '';
    var search = document.getElementById('productSearch') ? document.getElementById('productSearch').value : '';
    var status = document.getElementById('productStatusFilter') ? document.getElementById('productStatusFilter').value : '';
    if (tier && tier !== '全部') url += '&tier=' + encodeURIComponent(tier);
    if (style && style !== '全部') url += '&style=' + encodeURIComponent(style);
    if (search) url += '&search=' + encodeURIComponent(search);
    if (status) url += '&status=' + encodeURIComponent(status);

    try {
        var res = await apiFetch(url);
        var data = Array.isArray(res) ? res : (res.data || []);
        // 追加行到现有表格
        var tbody = document.querySelector('#productTableBody');
        if (tbody && data.length > 0) {
            // 移除加载更多按钮行
            var loadMoreBtn = tbody.querySelector('.load-more-btn');
            if (loadMoreBtn) loadMoreBtn.closest('tr').remove();

            var startRank = offset + 1;
            var visibleCols = getVisibleColumns();
            var metricCols = visibleCols.filter(function(c) { return c.key !== 'image' && c.key !== 'title'; });
            data.forEach(function(p, i) {
                var html = buildProductRow(p, startRank + i, metricCols, visibleCols);
                tbody.insertAdjacentHTML('beforeend', html);
            });
            // 追加到 STATE.productData
            STATE.productData = STATE.productData.concat(data);
            bindInlineEditEvents();
            showToast('已加载 ' + data.length + ' 件商品', 'info');

            // 如果还有更多数据，继续显示加载更多按钮
            var total = STATE.totalProducts || 0;
            if (STATE.page * STATE.pageSize < total) {
                var newLoadMoreRow = document.createElement('tr');
                newLoadMoreRow.innerHTML = '<td colspan="99" style="text-align:center;padding:12px;"><button class="load-more-btn" onclick="loadMoreProducts()">加载更多（剩余 ' + (total - STATE.page * STATE.pageSize) + ' 件）</button></td>';
                tbody.appendChild(newLoadMoreRow);
            }
            // 更新翻页控件
            var totalPages = Math.max(1, Math.ceil(total / STATE.pageSize));
            var pagEl = document.getElementById('tablePagination');
            pagEl.innerHTML = '<button disabled>上一页</button><span class="page-info">已加载 ' + STATE.productData.length + ' / ' + total + ' 条</span><button disabled>下一页</button>';
        } else {
            showToast('没有更多数据了', 'info');
        }
    } catch(e) {
        console.error('加载更多失败:', e);
        showToast('加载失败', 'error');
    }
}

/* ================================================================
   商品搜索/筛选
================================================================ */
let _searchTimer = null;

function debounceSearch() {
    const val = document.getElementById('productSearch').value;
    const clearBtn = document.getElementById('searchClear');
    if (clearBtn) clearBtn.style.display = val ? 'flex' : 'none';
    clearTimeout(_searchTimer);
    _searchTimer = setTimeout(() => filterProducts(), 300);
}

function clearSearch() {
    const input = document.getElementById('productSearch');
    input.value = '';
    const clearBtn = document.getElementById('searchClear');
    if (clearBtn) clearBtn.style.display = 'none';
    filterProducts();
}

function filterProducts() {
    const search = document.getElementById('productSearch').value.trim();
    const tier = document.getElementById('productTierFilter').value;
    const style = document.getElementById('productStyleFilter').value;
    const status = document.getElementById('productStatusFilter').value;
    STATE.page = 1;
    loadFilteredProducts(search, tier, style, status);
    syncURL();
}

async function loadFilteredProducts(search, tier, style, status) {
    setLoading('loading-table', true);

    const sort = STATE.sortKey || 'payment_amount';
    const order = STATE.sortOrder || 'desc';
    const offset = (STATE.page - 1) * STATE.pageSize;
    let url = `/api/products?dim=${STATE.dim}&period=${STATE.period}&limit=${STATE.pageSize}&offset=${offset}&sort=${sort}&order=${order}`;
    if (search) url += `&search=${encodeURIComponent(search)}`;
    if (tier) url += `&tier=${encodeURIComponent(tier)}`;
    if (style) url += `&style=${encodeURIComponent(style)}`;
    if (status) url += `&status=${encodeURIComponent(status)}`;

    const res = await apiFetch(url);
    setLoading('loading-table', false);

    // 兼容新旧响应格式
    const data = Array.isArray(res) ? res : (res.data || []);
    const total = res.total || data.length;
    STATE.totalProducts = total;

    if (!data || data.length === 0) {
        STATE.productData = [];
        renderProductTable();
        return;
    }

    STATE.productData = data;
    loadProductActions(data);
    renderProductTable();
}

function populateStyleFilter(data) {
    const styles = new Set();
    const tiers = new Set();
    (data || []).forEach(p => {
        if (p.style) styles.add(p.style);
        if (p.tier) tiers.add(p.tier);
    });

    // 填充分层筛选
    const tierSel = document.getElementById('productTierFilter');
    if (tierSel) {
        const current = tierSel.value;
        tierSel.innerHTML = '<option value="">全部分层</option>';
        [...tiers].filter(t => t && t !== 'nan' && t !== 'null' && t !== 'None').sort().forEach(t => {
            const opt = document.createElement('option');
            opt.value = t;
            opt.textContent = t;
            tierSel.appendChild(opt);
        });
        tierSel.value = current;
    }

    // 填充风格筛选
    const sel = document.getElementById('productStyleFilter');
    if (!sel) return;
    const current = sel.value;
    sel.innerHTML = '<option value="">全部风格</option>';
    [...styles].filter(s => s && s !== 'nan' && s !== 'null' && s !== 'None' && s !== '--').sort().forEach(s => {
        const opt = document.createElement('option');
        opt.value = s;
        opt.textContent = s;
        sel.appendChild(opt);
    });
    sel.value = current;
}

/* ================================================================
   初始化: 加载列配置
================================================================ */
// Call loadColumnConfig on script load so config is ready before first render
loadColumnConfig();

/* ================================================================
   商品详情弹窗
================================================================ */
function showProductDetail(product) {
    const popup = document.getElementById('productDetailPopup');
    const imgEl = document.getElementById('detailProductImg');
    const nameEl = document.getElementById('detailProductName');
    const metricsEl = document.getElementById('detailProductMetrics');

    if (!popup) return;

    // 设置图片和名称
    imgEl.src = product.image_url || '';
    imgEl.style.display = product.image_url ? 'block' : 'none';
    nameEl.textContent = product.title || '未知商品';

    // 设置指标
    const metrics = [
        { label: '支付金额', value: fmtWan(product.payment_amount) },
        { label: '支付件数', value: fmtNum(product.payment_count) },
        { label: '访客数', value: fmtNum(product.visitors) },
        { label: '转化率', value: fmtPct(product.conversion) },
        { label: '推广花费', value: fmtWan(product.ad_spend) },
        { label: 'ROI', value: product.roi != null ? Number(product.roi).toFixed(2) : '--' },
        { label: '退款率', value: fmtPct(product.refund_rate) },
        { label: '退款金额', value: fmtWan(product.refund_amount) },
    ];

    metricsEl.innerHTML = metrics.map(m => `
        <div class="detail-metric">
            <div class="detail-metric-label">${m.label}</div>
            <div class="detail-metric-value">${m.value}</div>
        </div>
    `).join('');

    popup.classList.add('open');
}

function closeProductDetail() {
    const popup = document.getElementById('productDetailPopup');
    if (popup) popup.classList.remove('open');
}

/* ================================================================
   批量打标签
================================================================ */
function openBatchTagPopover() {
    const ids = getSelectedIds();
    if (ids.length === 0) { showToast('请先勾选商品', 'warning'); return; }

    const popover = document.getElementById('batchTagPopover');
    if (popover) {
        popover.style.display = 'block';
        // 加载已有标签
        loadExistingTags(ids);
    }
}

function closeBatchTagPopover() {
    const popover = document.getElementById('batchTagPopover');
    if (popover) popover.style.display = 'none';
}

async function loadExistingTags(productIds) {
    const existingSection = document.getElementById('batchTagExisting');
    const tagList = document.getElementById('batchTagList');
    if (!existingSection || !tagList) return;

    const tags = await apiFetch(`/api/product_tags?product_ids=${productIds.join(',')}`);
    if (!tags || !Array.isArray(tags) || tags.length === 0) {
        existingSection.style.display = 'none';
        return;
    }

    // 去重
    const uniqueTags = [...new Set(tags.map(t => t.tag))];
    existingSection.style.display = 'block';
    tagList.innerHTML = uniqueTags.map(tag => `
        <span class="period-tag selected" style="cursor:pointer;margin:2px;" onclick="batchRemoveTag('${escapeHtml(tag)}')">${escapeHtml(tag)} &times;</span>
    `).join('');
}

async function batchAddTag() {
    const ids = getSelectedIds();
    if (ids.length === 0) return;

    const tagInput = document.getElementById('batchTagName');
    const tag = tagInput.value.trim();
    if (!tag) { showToast('请输入标签名称', 'warning'); return; }

    const result = await apiFetch('/api/batch_tags', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ product_ids: ids, tag: tag }),
    });

    if (result && result.success) {
        showToast(result.message, 'success');
        tagInput.value = '';
        loadExistingTags(ids);
    } else {
        showToast('添加标签失败', 'error');
    }
}

async function batchRemoveTag(tag) {
    const ids = getSelectedIds();
    if (ids.length === 0) return;

    const result = await apiFetch('/api/batch_tags', {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ product_ids: ids, tag: tag }),
    });

    if (result && result.success) {
        showToast(result.message, 'success');
        loadExistingTags(ids);
    } else {
        showToast('移除标签失败', 'error');
    }
}

/* ================================================================
   Feature 10: 表格列宽拖拽
================================================================ */
function initColumnResize() {
    const table = document.getElementById('productTable');
    if (!table) return;

    // 恢复已保存的列宽
    const savedWidths = {};
    try {
        const saved = JSON.parse(localStorage.getItem('colWidths') || '{}');
        Object.assign(savedWidths, saved);
    } catch (e) {}

    // 应用已保存的列宽
    if (Object.keys(savedWidths).length > 0) {
        const ths = table.querySelectorAll('.header-row th[data-key]');
        ths.forEach(th => {
            const key = th.dataset.key;
            if (savedWidths[key]) {
                th.style.width = savedWidths[key] + 'px';
                th.style.minWidth = savedWidths[key] + 'px';
            }
        });
    }

    // 为每个表头添加拖拽手柄
    const headerThs = table.querySelectorAll('.header-row th[data-key]');
    headerThs.forEach(th => {
        // 避免重复添加
        if (th.querySelector('.th-resize-handle')) return;

        const handle = document.createElement('div');
        handle.className = 'th-resize-handle';
        th.appendChild(handle);

        handle.addEventListener('mousedown', function(e) {
            e.preventDefault();
            e.stopPropagation();

            const startX = e.clientX;
            const startWidth = th.offsetWidth;
            const key = th.dataset.key;

            th.classList.add('resizing');
            handle.classList.add('resizing');

            // 禁用文本选择
            document.body.style.userSelect = 'none';
            document.body.style.cursor = 'col-resize';

            function onMouseMove(e) {
                const diff = e.clientX - startX;
                const newWidth = Math.max(60, startWidth + diff);
                th.style.width = newWidth + 'px';
                th.style.minWidth = newWidth + 'px';
            }

            function onMouseUp() {
                document.removeEventListener('mousemove', onMouseMove);
                document.removeEventListener('mouseup', onMouseUp);
                th.classList.remove('resizing');
                handle.classList.remove('resizing');
                document.body.style.userSelect = '';
                document.body.style.cursor = '';

                // 保存列宽
                savedWidths[key] = th.offsetWidth;
                try {
                    localStorage.setItem('colWidths', JSON.stringify(savedWidths));
                } catch (e) {}
            }

            document.addEventListener('mousemove', onMouseMove);
            document.addEventListener('mouseup', onMouseUp);
        });
    });
}

/* ================================================================
   Feature 11: 表格行内快速编辑
================================================================ */
function startInlineEdit(td, productId, field) {
    // 如果已经在编辑中，不重复创建
    if (td.querySelector('.inline-edit-input') || td.querySelector('.inline-edit-select')) return;

    const currentValue = td.textContent.trim() || '';
    const originalHtml = td.innerHTML;

    if (field === 'tier') {
        // 分层下拉
        const select = document.createElement('select');
        select.className = 'inline-edit-select';
        ['S', 'A', 'B', 'C'].forEach(opt => {
            const option = document.createElement('option');
            option.value = opt;
            option.textContent = opt;
            if (currentValue === opt) option.selected = true;
            select.appendChild(option);
        });
        td.innerHTML = '';
        td.appendChild(select);
        select.focus();

        async function save() {
            const newValue = select.value;
            if (newValue !== currentValue) {
                const ok = await saveInlineEdit(productId, field, newValue);
                if (ok) {
                    td.textContent = newValue;
                    // 同步更新STATE中的数据
                    const product = (STATE.productData || []).find(p => p.product_id === productId);
                    if (product) product[field] = newValue;
                } else {
                    td.innerHTML = originalHtml;
                }
            } else {
                td.innerHTML = originalHtml;
            }
        }

        select.addEventListener('change', save);
        select.addEventListener('blur', function() {
            setTimeout(save, 100);
        });
        select.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') { td.innerHTML = originalHtml; }
        });
    } else if (field === 'style') {
        // 风格下拉（从已有数据中收集）
        const styles = new Set();
        (STATE.productData || []).forEach(p => {
            if (p.style && p.style !== 'nan' && p.style !== 'null' && p.style !== 'None') {
                styles.add(p.style);
            }
        });
        const styleList = [...styles].sort();

        const select = document.createElement('select');
        select.className = 'inline-edit-select';
        const defaultOpt = document.createElement('option');
        defaultOpt.value = '';
        defaultOpt.textContent = '-- 请选择 --';
        select.appendChild(defaultOpt);
        styleList.forEach(s => {
            const option = document.createElement('option');
            option.value = s;
            option.textContent = s;
            if (currentValue === s) option.selected = true;
            select.appendChild(option);
        });
        // 允许自定义输入
        const customOpt = document.createElement('option');
        customOpt.value = '__custom__';
        customOpt.textContent = '+ 自定义输入';
        select.appendChild(customOpt);

        td.innerHTML = '';
        td.appendChild(select);
        select.focus();

        select.addEventListener('change', function() {
            if (select.value === '__custom__') {
                // 切换为文本输入
                const input = document.createElement('input');
                input.type = 'text';
                input.className = 'inline-edit-input';
                input.value = currentValue;
                td.innerHTML = '';
                td.appendChild(input);
                input.focus();
                input.select();
                bindInputEvents(input, td, productId, field, originalHtml);
            } else {
                const newValue = select.value;
                if (newValue !== currentValue) {
                    saveInlineEdit(productId, field, newValue).then(ok => {
                        if (ok) {
                            td.textContent = newValue;
                            const product = (STATE.productData || []).find(p => p.product_id === productId);
                            if (product) product[field] = newValue;
                        } else {
                            td.innerHTML = originalHtml;
                        }
                    });
                } else {
                    td.innerHTML = originalHtml;
                }
            }
        });
        select.addEventListener('blur', function() {
            if (select.value !== '__custom__') {
                setTimeout(() => {
                    const newValue = select.value;
                    if (newValue !== currentValue) {
                        saveInlineEdit(productId, field, newValue).then(ok => {
                            if (ok) {
                                td.textContent = newValue;
                                const product = (STATE.productData || []).find(p => p.product_id === productId);
                                if (product) product[field] = newValue;
                            } else {
                                td.innerHTML = originalHtml;
                            }
                        });
                    } else {
                        td.innerHTML = originalHtml;
                    }
                }, 100);
            }
        });
        select.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') { td.innerHTML = originalHtml; }
        });
    } else {
        // 文本输入（scene, manager, remark）
        const input = document.createElement('input');
        input.type = 'text';
        input.className = 'inline-edit-input';
        input.value = currentValue;
        td.innerHTML = '';
        td.appendChild(input);
        input.focus();
        input.select();
        bindInputEvents(input, td, productId, field, originalHtml);
    }
}

function bindInputEvents(input, td, productId, field, originalHtml) {
    const currentValue = input.value;

    async function save() {
        const newValue = input.value.trim();
        if (newValue !== currentValue) {
            const ok = await saveInlineEdit(productId, field, newValue);
            if (ok) {
                td.textContent = newValue;
                const product = (STATE.productData || []).find(p => p.product_id === productId);
                if (product) product[field] = newValue;
            } else {
                td.innerHTML = originalHtml;
            }
        } else {
            td.innerHTML = originalHtml;
        }
    }

    input.addEventListener('keydown', function(e) {
        if (e.key === 'Enter') { e.preventDefault(); save(); }
        if (e.key === 'Escape') { td.innerHTML = originalHtml; }
    });
    input.addEventListener('blur', function() {
        setTimeout(save, 100);
    });
}

async function saveInlineEdit(productId, field, value) {
    try {
        const resp = await fetch('/api/products/' + encodeURIComponent(productId) + '/field', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ field: field, value: value })
        });
        if (!resp.ok) {
            showToast('保存失败: ' + resp.statusText, 'error');
            return false;
        }
        const data = await resp.json();
        if (data && data.success) {
            showToast('已更新「' + field + '」', 'success');
            return true;
        } else {
            showToast('保存失败: ' + (data.error || '未知错误'), 'error');
            return false;
        }
    } catch (e) {
        showToast('保存失败: ' + e.message, 'error');
        return false;
    }
}

// 为可编辑单元格绑定双击事件
function bindInlineEditEvents() {
    const editableFields = ['tier', 'style', 'scene', 'manager'];
    const tbody = document.getElementById('productTableBody');
    if (!tbody) return;

    tbody.querySelectorAll('tr[data-pid]').forEach(tr => {
        const productId = tr.dataset.pid;
        const metricCols = getVisibleColumns().filter(c => c.key !== 'image' && c.key !== 'title');
        const tds = tr.querySelectorAll('td');
        // 跳过前两个td（排名和商品信息）
        metricCols.forEach((col, idx) => {
            if (editableFields.includes(col.key) && tds[idx + 2]) {
                const td = tds[idx + 2];
                td.classList.add('editable-cell');
                td.title = '双击编辑';
                td.addEventListener('dblclick', function(e) {
                    e.stopPropagation();
                    startInlineEdit(td, productId, col.key);
                });
            }
        });
    });
}

/* ================================================================
   Feature 14: 数据表格横向滚动提示
================================================================ */
function updateScrollIndicators() {
    const wrapper = document.querySelector('.table-wrapper');
    if (!wrapper) return;

    // 确保滚动指示器元素存在
    let leftIndicator = wrapper.querySelector('.scroll-indicator-left');
    let rightIndicator = wrapper.querySelector('.scroll-indicator-right');

    if (!leftIndicator || !rightIndicator) {
        if (!leftIndicator) {
            leftIndicator = document.createElement('div');
            leftIndicator.className = 'scroll-indicator-left';
            wrapper.appendChild(leftIndicator);
        }
        if (!rightIndicator) {
            rightIndicator = document.createElement('div');
            rightIndicator.className = 'scroll-indicator-right';
            wrapper.appendChild(rightIndicator);
        }
    }

    function checkScroll() {
        const hasOverflow = wrapper.scrollWidth > wrapper.clientWidth;
        if (!hasOverflow) {
            leftIndicator.classList.remove('visible');
            rightIndicator.classList.remove('visible');
            return;
        }
        const scrollLeft = wrapper.scrollLeft;
        const maxScroll = wrapper.scrollWidth - wrapper.clientWidth;
        leftIndicator.classList.toggle('visible', scrollLeft > 5);
        rightIndicator.classList.toggle('visible', scrollLeft < maxScroll - 5);
    }

    // 初始检查
    checkScroll();

    // 监听滚动事件
    wrapper.removeEventListener('scroll', checkScroll);
    wrapper.addEventListener('scroll', checkScroll);

    // 监听窗口大小变化
    window.removeEventListener('resize', checkScroll);
    window.addEventListener('resize', checkScroll);
}

/* ================================================================
   商品画像标签
================================================================ */
// 标签数据缓存
let _productTagsMap = {};

async function loadProductTags() {
    const data = await apiFetch(`/api/product_tags?dim=${STATE.dim}&period=${STATE.period}`);
    if (!data || !Array.isArray(data)) return;

    // 构建标签映射
    _productTagsMap = {};
    data.forEach(item => {
        _productTagsMap[item.product_id] = item.tags || [];
    });

    // 将标签附加到商品数据
    (STATE.productData || []).forEach(p => {
        p._tags = _productTagsMap[p.product_id] || [];
    });

    // 重新渲染表格
    renderProductTable();
}

// 显示添加自定义标签对话框
function showAddTagDialog(productId) {
    // 移除已有弹窗
    const existing = document.getElementById('addTagDialog');
    if (existing) existing.remove();

    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.id = 'addTagDialog';
    overlay.style.display = 'flex';
    overlay.innerHTML = `
        <div style="background:var(--bg-card);border-radius:12px;padding:20px;width:320px;box-shadow:var(--shadow-lg);">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
                <span style="font-size:0.95rem;font-weight:600;color:var(--text-primary);">添加自定义标签</span>
                <button onclick="document.getElementById('addTagDialog').remove()" style="background:none;border:none;color:var(--text-muted);cursor:pointer;font-size:1.2rem;">&times;</button>
            </div>
            <div style="margin-bottom:12px;">
                <span style="font-size:0.82rem;color:var(--text-muted);">商品ID: ${productId}</span>
            </div>
            <div style="margin-bottom:12px;">
                <input type="text" id="customTagInput" placeholder="输入标签名称" maxlength="10"
                    style="width:100%;padding:8px 12px;border-radius:6px;border:1px solid var(--border);background:var(--bg-elevated);color:var(--text-primary);font-size:0.85rem;"
                    onkeydown="if(event.key==='Enter')saveCustomTag('${productId}')">
            </div>
            <div style="display:flex;gap:8px;justify-content:flex-end;">
                <button onclick="document.getElementById('addTagDialog').remove()" style="padding:6px 14px;border-radius:6px;border:1px solid var(--border);background:transparent;color:var(--text-secondary);cursor:pointer;font-size:0.82rem;">取消</button>
                <button onclick="saveCustomTag('${productId}')" style="padding:6px 14px;border-radius:6px;border:none;background:var(--accent);color:#fff;cursor:pointer;font-size:0.82rem;">保存</button>
            </div>
        </div>
    `;
    document.body.appendChild(overlay);

    // 聚焦输入框
    setTimeout(() => {
        const input = document.getElementById('customTagInput');
        if (input) input.focus();
    }, 100);

    // 点击遮罩关闭
    overlay.addEventListener('click', (e) => {
        if (e.target === overlay) overlay.remove();
    });
}

async function saveCustomTag(productId) {
    const input = document.getElementById('customTagInput');
    if (!input) return;
    const tag = input.value.trim();
    if (!tag) {
        showToast('请输入标签名称', 'error');
        return;
    }

    const res = await apiFetch('/api/product_tags', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ product_id: productId, tag: tag }),
    });

    if (res && res.success) {
        showToast('标签已添加', 'success');
        document.getElementById('addTagDialog').remove();
        // 重新加载标签
        loadProductTags();
    } else {
        showToast('添加标签失败', 'error');
    }
}

async function deleteProductTag(tagId) {
    const res = await apiFetch(`/api/product_tags/${tagId}`, { method: 'DELETE' });
    if (res && res.success) {
        showToast('标签已删除', 'success');
        loadProductTags();
    } else {
        showToast('删除标签失败', 'error');
    }
}
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
/* ================================================================
   模块7: 运营动作效果追踪
================================================================ */
async function loadActionStats(dim, period) {
    setLoading('loading-action-stats', true);
    const data = await apiFetch(`/api/action_stats?dim=${dim}&period=${period}`);
    setLoading('loading-action-stats', false);
    // 后端返回原始数组 [{action_type, count, avg_score, ...}, ...]
    if (!data || !Array.isArray(data) || data.length === 0) { showChartEmpty('chartActionStats'); return; }

    const chart = getChart('chartActionStats');
    // 按平均效果评分排序（升序，让最高的在最上面）
    const sorted = [...data].sort((a, b) => (a.avg_score || 0) - (b.avg_score || 0));
    const names = sorted.map(d => d.action_type || '未知').reverse();
    const scores = sorted.map(d => d.avg_score || 0).reverse();

    const opt = baseOption();
    opt.tooltip.trigger = 'axis';
    opt.tooltip.axisPointer = { type: 'shadow' };
    opt.tooltip.formatter = params => {
        const p = params[0];
        return `${p.name}<br/>平均效果评分：${p.value.toFixed(1)}`;
    };
    opt.grid = { left: 120, right: 60, top: 10, bottom: 20 };
    opt.xAxis = {
        type: 'value', min: 0, max: 100,
        name: '平均效果评分',
        nameTextStyle: { color: '#94A3B8' },
        axisLabel: { color: '#94A3B8' },
        splitLine: { lineStyle: { color: '#1E293B', type: 'dashed' } },
    };
    opt.yAxis = {
        type: 'category', data: names,
        axisLabel: { color: '#CBD5E1', fontSize: 12 },
        axisLine: { lineStyle: { color: '#334155' } },
    };
    opt.series = [{
        type: 'bar', data: scores,
        barWidth: '55%',
        itemStyle: {
            borderRadius: [0, 4, 4, 0],
            color: params => {
                const v = params.value;
                if (v > 60) return '#10B981';
                if (v >= 30) return '#F59E0B';
                return '#EF4444';
            },
        },
        label: {
            show: true, position: 'right',
            color: '#94A3B8', fontSize: 12,
            formatter: p => p.value.toFixed(1),
        },
    }];
    chart.setOption(opt, true);
}

async function loadActions(dim, period) {
    setLoading('loading-actions', true);
    const data = await apiFetch(`/api/actions?dim=${dim}&period=${period}`);
    setLoading('loading-actions', false);
    // 后端返回原始数组 [{action_date, product_id, action_type, ...}, ...]
    if (!data || !Array.isArray(data) || data.length === 0) {
        document.getElementById('actionTableWrapper').innerHTML =
            '<div style="text-align:center;color:#64748B;padding:40px;">暂无数据</div>';
        return;
    }

    const wrapperEl = document.getElementById('actionTableWrapper');
    wrapperEl.innerHTML = `<table class="action-table">
        <thead>
            <tr>
                <th>日期</th>
                <th>商品名</th>
                <th>动作类型</th>
                <th>动作详情</th>
                <th>效果评分</th>
                <th>操作</th>
            </tr>
        </thead>
        <tbody id="actionTableBody"></tbody>
    </table>`;

    const tbody = document.getElementById('actionTableBody');
    tbody.innerHTML = data.map(item => {
        const date = item.action_date || '--';
        const title = item.title || '--';
        const img = item.image_url || '';
        const actionType = item.action_type || '--';
        const detail = item.action_detail || '--';
        const score = item.effectiveness_score != null ? item.effectiveness_score : null;
        const actionId = item.id;

        let scoreBadge = '--';
        if (score != null) {
            let cls = 'low';
            if (score > 60) cls = 'high';
            else if (score >= 30) cls = 'medium';
            scoreBadge = `<span class="score-badge ${cls}">${score.toFixed(1)}</span>`;
        }

        const productCell = img
            ? `<div class="product-cell"><img src="${img}" alt=""><span class="title">${title}</span></div>`
            : `<span>${title}</span>`;

        return `<tr>
            <td>${date}</td>
            <td>${productCell}</td>
            <td>${actionType}</td>
            <td style="white-space:normal;max-width:200px;">${detail}</td>
            <td>${scoreBadge}</td>
            <td>
                <div class="action-row-actions">
                    <button class="action-row-btn" onclick='openActionForm(${JSON.stringify(item).replace(/'/g, "&#39;")})'>编辑</button>
                    <button class="action-row-btn delete" onclick="deleteAction(${actionId})">删除</button>
                </div>
            </td>
        </tr>`;
    }).join('');
}

/* ================================================================
   运营动作 CRUD
================================================================ */
function openActionForm(action) {
    const modal = document.getElementById('actionFormModal');
    const titleEl = document.getElementById('actionFormTitle');
    const form = document.getElementById('actionForm');

    // Reset form
    form.reset();
    document.getElementById('actionFormId').value = '';

    if (action && action.id) {
        // Edit mode
        titleEl.textContent = '编辑运营动作';
        document.getElementById('actionFormId').value = action.id;
        document.getElementById('actionFormProductId').value = action.product_id || '';
        document.getElementById('actionFormDate').value = action.action_date || '';
        document.getElementById('actionFormType').value = action.action_type || '';
        document.getElementById('actionFormDetail').value = action.action_detail || '';
        document.getElementById('actionFormPayment').value = action.before_payment || '';
        document.getElementById('actionFormVisitors').value = action.before_visitors || '';
        document.getElementById('actionFormConversion').value = action.before_conversion || '';
        document.getElementById('actionFormRoi').value = action.before_roi || '';
    } else {
        // Add mode - default date to today
        titleEl.textContent = '添加运营动作';
        document.getElementById('actionFormDate').value = new Date().toISOString().split('T')[0];
    }

    modal.classList.add('open');
}

function closeActionForm() {
    const modal = document.getElementById('actionFormModal');
    modal.classList.remove('open');
}

async function saveAction(event) {
    event.preventDefault();

    const id = document.getElementById('actionFormId').value;
    const payload = {
        product_id: document.getElementById('actionFormProductId').value.trim(),
        action_date: document.getElementById('actionFormDate').value,
        action_type: document.getElementById('actionFormType').value,
        action_detail: document.getElementById('actionFormDetail').value.trim(),
        before_payment: document.getElementById('actionFormPayment').value ? parseFloat(document.getElementById('actionFormPayment').value) : null,
        before_visitors: document.getElementById('actionFormVisitors').value ? parseInt(document.getElementById('actionFormVisitors').value) : null,
        before_conversion: document.getElementById('actionFormConversion').value ? parseFloat(document.getElementById('actionFormConversion').value) : null,
        before_roi: document.getElementById('actionFormRoi').value ? parseFloat(document.getElementById('actionFormRoi').value) : null,
    };

    try {
        let url, method;
        if (id) {
            url = `/api/actions/${id}`;
            method = 'PUT';
        } else {
            url = '/api/actions';
            method = 'POST';
        }

        const resp = await fetch(url, {
            method: method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });

        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const result = await resp.json();

        closeActionForm();
        showToast(id ? '动作已更新' : '动作已创建', 'success');
        // Reload actions list
        loadActions(STATE.dim, STATE.period);
    } catch (e) {
        console.error('Save action error:', e);
        showToast('保存失败: ' + e.message, 'error');
    }
}

async function deleteAction(actionId) {
    if (!actionId) return;
    if (!confirm('确定要删除这条运营动作吗？')) return;

    try {
        const resp = await fetch(`/api/actions/${actionId}`, { method: 'DELETE' });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const result = await resp.json();

        showToast('动作已删除', 'success');
        // Reload actions list
        loadActions(STATE.dim, STATE.period);
    } catch (e) {
        console.error('Delete action error:', e);
        showToast('删除失败: ' + e.message, 'error');
    }
}
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
/* ================================================================
   模块: 商品健康度看板（12维度）
================================================================ */

// 12维度定义
const HEALTH_DIMENSIONS = [
    { key: 'gmv_change_score', label: 'GSV环比', weight: '15%' },
    { key: 'ad_spend_change_score', label: '总推广花费环比', weight: '8%' },
    { key: 'roi_change_score', label: '直接ROI环比', weight: '10%' },
    { key: 'refund_rate_score', label: '退款率', weight: '10%' },
    { key: 'cart_rate_score', label: '加购率', weight: '8%' },
    { key: 'search_ratio_score', label: '引潜比', weight: '7%' },
    { key: 'new_customer_cost_score', label: '拉新成本', weight: '7%' },
    { key: 'direct_cart_cost_score', label: '直接加购成本', weight: '5%' },
    { key: 'total_cart_cost_score', label: '总加购成本', weight: '5%' },
    { key: 'repurchase_rate_score', label: '复购率', weight: '8%' },
    { key: 'cross_sell_rate_score', label: '连带率', weight: '7%' },
    { key: 'search_ctr_vs_industry_score', label: '搜索点击率vs行业', weight: '10%' },
];

// 模块级缓存，避免重复API调用
let _healthCache = null;

async function loadHealthDashboard(period) {
    setLoading('loading-health-pie', true);
    setLoading('loading-health-table', true);

    // 只发一次请求，前端过滤预警商品
    const statsData = await apiFetch(`/api/health?period=${period}`);
    _healthCache = statsData;

    setLoading('loading-health-pie', false);
    setLoading('loading-health-table', false);

    // --- 健康等级分布饼图 ---
    const pieChart = getChart('chartHealthPie');
    const statsArr = (statsData && Array.isArray(statsData.stats)) ? statsData.stats : [];
    const statsMap = {};
    let total = 0;
    statsArr.forEach(s => {
        statsMap[s.health_level] = s.count;
        total += s.count;
    });

    const pieData = [
        { name: '优秀', value: statsMap['优秀'] || 0, itemStyle: { color: '#10B981' } },
        { name: '良好', value: statsMap['良好'] || 0, itemStyle: { color: '#3B82F6' } },
        { name: '关注', value: statsMap['关注'] || 0, itemStyle: { color: '#F59E0B' } },
        { name: '预警', value: statsMap['预警'] || 0, itemStyle: { color: '#EF4444' } },
    ].filter(d => d.value > 0);

    const pieOpt = baseOption();
    pieOpt.tooltip.trigger = 'item';
    pieOpt.tooltip.formatter = '{b}: {c} 件 ({d}%)';
    pieOpt.legend = {
        orient: 'horizontal',
        bottom: 0,
        textStyle: { color: '#94A3B8', fontSize: 12 },
    };
    pieOpt.graphic = total > 0 ? [{
        type: 'text',
        left: 'center',
        top: '42%',
        style: {
            text: total + '',
            fontSize: 28,
            fontWeight: 700,
            fill: '#F1F5F9',
            textAlign: 'center',
        },
    }, {
        type: 'text',
        left: 'center',
        top: '54%',
        style: {
            text: '总商品数',
            fontSize: 12,
            fill: '#94A3B8',
            textAlign: 'center',
        },
    }] : [];
    pieOpt.series = [{
        type: 'pie',
        radius: ['45%', '70%'],
        center: ['50%', '48%'],
        data: pieData.length > 0 ? pieData : [{ name: '暂无数据', value: 1, itemStyle: { color: '#334155' } }],
        label: { show: false },
        emphasis: {
            label: { show: true, color: '#F1F5F9', fontSize: 13 },
            itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0,0,0,0.5)' },
        },
        itemStyle: { borderRadius: 6, borderColor: '#1E293B', borderWidth: 2 },
    }];
    pieChart.setOption(pieOpt, true);
    addChartSaveBtn(pieChart, 'chartHealthPie');

    // --- 预警商品列表（12维度） ---
    const allProducts = (statsData && statsData.products) || [];
    const alertProducts = allProducts.filter(p => p.health_level === '预警');
    const wrapperEl = document.getElementById('healthTableWrapper');
    if (alertProducts.length === 0) {
        wrapperEl.innerHTML = '<div style="text-align:center;color:#64748B;padding:40px;">暂无预警商品</div>';
        return;
    }

    const sorted = [...alertProducts].sort((a, b) => (a.health_score || 0) - (b.health_score || 0));

    // 构建表头：商品 + 健康分 + 12维度 + 等级
    const dimHeaders = HEALTH_DIMENSIONS.map(d => `<th>${d.label}</th>`).join('');

    wrapperEl.innerHTML = `<table class="health-table">
        <thead>
            <tr>
                <th>商品</th>
                <th>健康分</th>
                ${dimHeaders}
                <th>预警维度</th>
                <th>等级</th>
            </tr>
        </thead>
        <tbody id="healthTableBody"></tbody>
    </table>`;

    const tbody = document.getElementById('healthTableBody');
    tbody.innerHTML = sorted.map(item => {
        const img = item.image_url || '';
        const title = item.title || '--';
        const score = item.health_score || 0;

        let scoreCls = 'score-excellent';
        if (score < 40) scoreCls = 'score-danger';
        else if (score < 60) scoreCls = 'score-warning';
        else if (score < 80) scoreCls = 'score-good';

        let rowCls = '';
        if (score < 40) rowCls = 'row-danger';
        else if (score < 60) rowCls = 'row-warning';

        const productCell = img
            ? `<div class="product-cell"><img src="${img}" alt=""><span class="title">${title}</span></div>`
            : `<div class="product-cell"><span class="title">${title}</span></div>`;

        // 12维度得分单元格
        const dimCells = HEALTH_DIMENSIONS.map(d => {
            const val = item[d.key] != null ? item[d.key].toFixed(0) : '--';
            const numVal = item[d.key] || 50;
            let cls = '';
            if (numVal < 20) cls = 'color:#EF4444;font-weight:700;';
            else if (numVal < 40) cls = 'color:#F59E0B;';
            else if (numVal >= 80) cls = 'color:#10B981;';
            return `<td style="${cls}">${val}</td>`;
        }).join('');

        // 预警维度标签
        const alertDims = item.alert_dimensions || [];
        const alertTags = alertDims.map(ad =>
            `<span style="display:inline-block;padding:1px 6px;border-radius:3px;font-size:0.68rem;background:rgba(239,68,68,0.15);color:#FCA5A5;margin:1px;">${ad.label}</span>`
        ).join('');

        const level = item.health_level || '预警';
        let levelCls = 'level-alert';
        if (level === '优秀') levelCls = 'level-excellent';
        else if (level === '良好') levelCls = 'level-good';
        else if (level === '关注') levelCls = 'level-watch';

        return `<tr class="${rowCls}" onclick="showHealthDetail('${item.product_id}')" style="cursor:pointer">
            <td>${productCell}</td>
            <td><span class="health-score-badge ${scoreCls}">${score.toFixed(0)}</span></td>
            ${dimCells}
            <td style="max-width:160px;white-space:normal;">${alertTags || '<span style="color:#64748B;">--</span>'}</td>
            <td><span class="health-level-tag ${levelCls}">${level}</span></td>
        </tr>`;
    }).join('');
}

/* ================================================================
   健康度详情弹窗：12轴雷达图
================================================================ */
function showHealthDetail(product_id) {
    // 从缓存中查找，避免重复API调用
    if (!_healthCache || !_healthCache.products) return;
    const product = _healthCache.products.find(p => p.product_id === product_id);
    if (!product) return;

    // 创建或复用弹窗
    let popup = document.getElementById('healthDetailPopup');
    if (!popup) {
        popup = document.createElement('div');
        popup.id = 'healthDetailPopup';
        popup.className = 'product-detail-popup';
        popup.innerHTML = `
                <div class="product-detail-card" style="max-width:700px;">
                    <button class="product-detail-close" onclick="closeHealthDetail()">&times;</button>
                    <div id="healthDetailContent"></div>
                </div>
            `;
        popup.addEventListener('click', function(e) {
            if (e.target === popup) closeHealthDetail();
        });
        document.body.appendChild(popup);
    }

    const content = document.getElementById('healthDetailContent');
    const score = product.health_score || 0;
    const level = product.health_level || '--';

    let scoreCls = 'score-excellent';
    if (score < 40) scoreCls = 'score-danger';
    else if (score < 60) scoreCls = 'score-warning';
    else if (score < 80) scoreCls = 'score-good';

    // 维度得分列表
    const dimRows = HEALTH_DIMENSIONS.map(d => {
            const val = product[d.key] != null ? product[d.key].toFixed(0) : '--';
            const numVal = product[d.key] || 50;
            let barColor = '#3B82F6';
            if (numVal < 20) barColor = '#EF4444';
            else if (numVal < 40) barColor = '#F59E0B';
            else if (numVal >= 80) barColor = '#10B981';
            return `<div style="display:flex;align-items:center;gap:8px;margin-bottom:6px;">
                <span style="min-width:110px;font-size:0.78rem;color:#CBD5E1;text-align:right;">${d.label}</span>
                <div style="flex:1;height:8px;background:#0F172A;border-radius:4px;overflow:hidden;">
                    <div style="height:100%;width:${numVal}%;background:${barColor};border-radius:4px;transition:width 0.6s;"></div>
                </div>
                <span style="min-width:32px;font-size:0.78rem;font-weight:600;color:#F1F5F9;text-align:right;">${val}</span>
                <span style="min-width:30px;font-size:0.68rem;color:#64748B;">${d.weight}</span>
            </div>`;
        }).join('');

    // 预警维度
    const alertDims = product.alert_dimensions || [];
    const alertHtml = alertDims.length > 0
        ? alertDims.map(ad => `<span style="display:inline-block;padding:2px 8px;border-radius:4px;font-size:0.72rem;background:rgba(239,68,68,0.15);color:#FCA5A5;margin:2px;">${ad.label} (${ad.score})</span>`).join('')
        : '<span style="color:#10B981;font-size:0.8rem;">无预警维度</span>';

    content.innerHTML = `
        <div style="display:flex;align-items:center;gap:12px;margin-bottom:20px;">
            ${product.image_url ? `<img src="${escapeHtml(product.image_url)}" style="width:48px;height:48px;border-radius:8px;object-fit:cover;background:#1E293B;">` : ''}
            <div style="flex:1;">
                <div style="font-size:1rem;font-weight:600;color:#F1F5F9;">${escapeHtml(product.title || '--')}</div>
                <div style="font-size:0.8rem;color:#64748B;">${escapeHtml(product.tier || '')} &middot; ${escapeHtml(product.style || '')}</div>
            </div>
            <div style="text-align:center;">
                <div class="health-score-badge ${scoreCls}" style="font-size:1.2rem;padding:4px 14px;">${score.toFixed(0)}</div>
                <div style="font-size:0.75rem;color:#64748B;margin-top:4px;">${level}</div>
            </div>
        </div>
        <div style="margin-bottom:16px;">
            <div style="font-size:0.85rem;font-weight:600;color:#F1F5F9;margin-bottom:10px;">12维度评分</div>
            ${dimRows}
        </div>
        <div>
            <div style="font-size:0.85rem;font-weight:600;color:#F1F5F9;margin-bottom:8px;">预警维度 (bottom 20%)</div>
            ${alertHtml}
        </div>
    `;

    popup.classList.add('open');
}

function closeHealthDetail() {
    const popup = document.getElementById('healthDetailPopup');
    if (popup) popup.classList.remove('open');
}
/* ================================================================
   模块9: 评价分析
================================================================ */
const REVIEW_STATE = {
    productId: '',
    sentiment: '',
};

async function loadReviewSummary() {
    setLoading('loading-rv-sentiment', true);
    setLoading('loading-rv-rating', true);
    setLoading('loading-rv-pos-dim', true);
    setLoading('loading-rv-neg-dim', true);
    setLoading('loading-rv-words', true);
    setLoading('loading-rv-scenes', true);

    const url = REVIEW_STATE.productId
        ? `/api/reviews/summary?product_id=${encodeURIComponent(REVIEW_STATE.productId)}`
        : `/api/reviews/summary`;
    const data = await apiFetch(url);

    setLoading('loading-rv-sentiment', false);
    setLoading('loading-rv-rating', false);
    setLoading('loading-rv-pos-dim', false);
    setLoading('loading-rv-neg-dim', false);
    setLoading('loading-rv-words', false);
    setLoading('loading-rv-scenes', false);

    if (!data || !data.stats) return;

    // 更新统计卡片
    const stats = data.stats;
    const total = stats.total || 0;
    document.getElementById('rv-stat-total').textContent = fmtNum(total);
    document.getElementById('rv-stat-pos-rate').textContent = total > 0
        ? (stats.positive / total * 100).toFixed(1) + '%' : '--';
    document.getElementById('rv-stat-neg-rate').textContent = total > 0
        ? (stats.negative / total * 100).toFixed(1) + '%' : '--';
    document.getElementById('rv-stat-avg-rating').textContent = stats.avg_rating != null
        ? stats.avg_rating.toFixed(1) : '--';
    document.getElementById('rv-stat-with-image').textContent = fmtNum(stats.with_image || 0);
    document.getElementById('rv-stat-effective').textContent = total > 0
        ? (stats.effective / total * 100).toFixed(1) + '%' : '--';

    renderReviewCharts(data);
}

async function loadReviewProducts() {
    const data = await apiFetch('/api/reviews/products');
    if (!data || !Array.isArray(data)) return;

    const sel = document.getElementById('reviewProductSelect');
    sel.innerHTML = '<option value="">全部商品</option>';
    data.forEach(p => {
        const opt = document.createElement('option');
        opt.value = p.product_id || '';
        opt.textContent = `${p.title || '未知商品'} (${p.review_count || 0}条, ${p.avg_rating != null ? p.avg_rating.toFixed(1) : '--'}分)`;
        sel.appendChild(opt);
    });
}

async function loadReviewList(product_id, sentiment) {
    let url = `/api/reviews/list?limit=50&offset=0`;
    if (product_id) url += `&product_id=${encodeURIComponent(product_id)}`;
    if (sentiment) url += `&sentiment=${encodeURIComponent(sentiment)}`;

    const data = await apiFetch(url);
    if (!data || !Array.isArray(data)) {
        document.getElementById('reviewListPanel').innerHTML =
            '<div style="text-align:center;color:#64748B;padding:40px;">暂无评价数据</div>';
        return;
    }

    renderReviewList(data);
}

async function uploadReviewFile(file) {
    if (!file) return;
    const formData = new FormData();
    formData.append('file', file);

    try {
        const resp = await fetch('/api/upload/reviews', { method: 'POST', body: formData });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const result = await resp.json();
        if (result.success) {
            showToast(`上传成功，共导入 ${result.count} 条评价`, 'success');
            // 刷新评价数据
            loadReviewSummary();
            loadReviewProducts();
            loadReviewList(REVIEW_STATE.productId, REVIEW_STATE.sentiment);
        } else {
            showToast('上传失败：' + (result.error || '未知错误'), 'error');
        }
    } catch (e) {
        console.error('Upload error:', e);
        showToast('上传失败：' + e.message, 'error');
    }
}

function renderReviewCharts(data) {
    const stats = data.stats || {};
    const total = stats.total || 0;

    // --- 情感分布环形图 ---
    const sentimentChart = getChart('chartReviewSentiment');
    const sentimentData = [
        { name: '好评', value: stats.positive || 0, itemStyle: { color: '#10B981' } },
        { name: '中评', value: stats.neutral || 0, itemStyle: { color: '#F59E0B' } },
        { name: '差评', value: stats.negative || 0, itemStyle: { color: '#EF4444' } },
    ].filter(d => d.value > 0);

    const sentimentOpt = baseOption();
    sentimentOpt.tooltip.trigger = 'item';
    sentimentOpt.tooltip.formatter = '{b}: {c} ({d}%)';
    sentimentOpt.legend = {
        orient: 'horizontal', bottom: 0,
        textStyle: { color: '#94A3B8', fontSize: 12 },
    };
    sentimentOpt.graphic = total > 0 ? [{
        type: 'text', left: 'center', top: '40%',
        style: { text: total + '', fontSize: 24, fontWeight: 700, fill: '#F1F5F9', textAlign: 'center' },
    }, {
        type: 'text', left: 'center', top: '54%',
        style: { text: '总评价', fontSize: 11, fill: '#94A3B8', textAlign: 'center' },
    }] : [];
    sentimentOpt.series = [{
        type: 'pie', radius: ['42%', '68%'], center: ['50%', '46%'],
        data: sentimentData.length > 0 ? sentimentData : [{ name: '暂无数据', value: 1, itemStyle: { color: '#334155' } }],
        label: { show: false },
        emphasis: {
            label: { show: true, color: '#F1F5F9', fontSize: 13 },
            itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0,0,0,0.5)' },
        },
        itemStyle: { borderRadius: 6, borderColor: '#1E293B', borderWidth: 2 },
    }];
    sentimentChart.setOption(sentimentOpt, true);
    addChartSaveBtn(sentimentChart, 'chartReviewSentiment');

    // --- 评分分布柱状图 ---
    const ratingChart = getChart('chartReviewRating');
    const ratingDist = data.rating_dist || [];
    const ratingLabels = ratingDist.map(d => d.rating + '星');
    const ratingValues = ratingDist.map(d => d.count || 0);

    const ratingOpt = baseOption();
    ratingOpt.tooltip.trigger = 'axis';
    ratingOpt.tooltip.axisPointer = { type: 'shadow' };
    ratingOpt.tooltip.formatter = params => `${params[0].name}<br/>数量：${fmtNum(params[0].value)}`;
    ratingOpt.grid = { left: 50, right: 20, top: 10, bottom: 24 };
    ratingOpt.xAxis = {
        type: 'category', data: ratingLabels,
        axisLabel: { color: '#CBD5E1', fontSize: 11 },
    };
    ratingOpt.yAxis = {
        type: 'value',
        axisLabel: { color: '#94A3B8' },
        splitLine: { lineStyle: { color: '#1E293B', type: 'dashed' } },
    };
    ratingOpt.series = [{
        type: 'bar', data: ratingValues,
        barWidth: '50%',
        itemStyle: {
            borderRadius: [4, 4, 0, 0],
            color: params => {
                const colors = ['#EF4444', '#F97316', '#F59E0B', '#84CC16', '#10B981'];
                return colors[params.dataIndex] || '#3B82F6';
            },
        },
        label: {
            show: true, position: 'top',
            color: '#94A3B8', fontSize: 10,
            formatter: p => fmtNum(p.value),
        },
    }];
    ratingChart.setOption(ratingOpt, true);
    addChartSaveBtn(ratingChart, 'chartReviewRating');

    // --- 好评维度条形 ---
    const posDims = data.positive_dims || [];
    const posContainer = document.getElementById('reviewPositiveDims');
    if (posDims.length === 0) {
        posContainer.innerHTML = '<div style="text-align:center;color:#64748B;padding:20px;">暂无数据</div>';
    } else {
        const maxPos = Math.max(...posDims.map(d => d.count), 1);
        posContainer.innerHTML = posDims.slice(0, 8).map(d => {
            const pct = (d.count / maxPos * 100).toFixed(1);
            return `<div class="review-dim-bar">
                <span class="dim-label" title="${d.value}">${d.value}</span>
                <div class="dim-track"><div class="dim-fill positive" style="width:${pct}%"></div></div>
                <span class="dim-count">${d.count}</span>
            </div>`;
        }).join('');
    }

    // --- 差评维度条形 ---
    const negDims = data.negative_dims || [];
    const negContainer = document.getElementById('reviewNegativeDims');
    if (negDims.length === 0) {
        negContainer.innerHTML = '<div style="text-align:center;color:#64748B;padding:20px;">暂无数据</div>';
    } else {
        const maxNeg = Math.max(...negDims.map(d => d.count), 1);
        negContainer.innerHTML = negDims.slice(0, 8).map(d => {
            const pct = (d.count / maxNeg * 100).toFixed(1);
            return `<div class="review-dim-bar">
                <span class="dim-label" title="${d.value}">${d.value}</span>
                <div class="dim-track"><div class="dim-fill negative" style="width:${pct}%"></div></div>
                <span class="dim-count">${d.count}</span>
            </div>`;
        }).join('');
    }

    // --- 高频词水平柱状图 ---
    const wordsChart = getChart('chartReviewWords');
    const topWords = (data.top_words || []).slice(0, 20);
    const wordLabels = topWords.map(w => w[0]).reverse();
    const wordValues = topWords.map(w => w[1]).reverse();

    const wordsOpt = baseOption();
    wordsOpt.tooltip.trigger = 'axis';
    wordsOpt.tooltip.axisPointer = { type: 'shadow' };
    wordsOpt.tooltip.formatter = params => `${params[0].name}<br/>出现次数：${fmtNum(params[0].value)}`;
    wordsOpt.grid = { left: 80, right: 40, top: 10, bottom: 20 };
    wordsOpt.xAxis = {
        type: 'value',
        axisLabel: { color: '#94A3B8' },
        splitLine: { lineStyle: { color: '#1E293B', type: 'dashed' } },
    };
    wordsOpt.yAxis = {
        type: 'category', data: wordLabels,
        axisLabel: { color: '#CBD5E1', fontSize: 12 },
        axisLine: { lineStyle: { color: '#334155' } },
    };
    wordsOpt.series = [{
        type: 'bar', data: wordValues,
        barWidth: '55%',
        itemStyle: {
            borderRadius: [0, 4, 4, 0],
            color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
                { offset: 0, color: '#3B82F6' },
                { offset: 1, color: '#60A5FA' },
            ]),
        },
        label: {
            show: true, position: 'right',
            color: '#94A3B8', fontSize: 11,
            formatter: p => fmtNum(p.value),
        },
    }];
    wordsChart.setOption(wordsOpt, true);
    addChartSaveBtn(wordsChart, 'chartReviewWords');

    // --- 场景分布标签 ---
    const scenes = data.scenes || [];
    const sceneContainer = document.getElementById('reviewSceneTags');
    if (scenes.length === 0) {
        sceneContainer.innerHTML = '<span style="color:#64748B;font-size:0.85rem;">暂无数据</span>';
    } else {
        sceneContainer.innerHTML = scenes.map(s =>
            `<span class="review-scene-tag">${s.value} <span class="scene-count">${s.count}</span></span>`
        ).join('');
    }
}

function renderReviewList(reviews) {
    const panel = document.getElementById('reviewListPanel');
    if (!reviews || reviews.length === 0) {
        panel.innerHTML = '<div style="text-align:center;color:#64748B;padding:40px;">暂无评价数据</div>';
        return;
    }

    panel.innerHTML = reviews.map(r => {
        const sentiment = r.sentiment || 'neutral';
        const sentimentLabel = sentiment === 'positive' ? '好评' : sentiment === 'negative' ? '差评' : '中评';
        const sentimentCls = 'tag-' + sentiment;
        const rating = r.rating || 0;
        const stars = renderStars(rating);
        const content = escapeHtml(r.content || '（无评价内容）');
        const productTitle = escapeHtml(r.product_title || r.title || '--');
        const date = escapeHtml(r.date || r.review_date || '--');

        return `<div class="review-item sentiment-${sentimentCls}">
            <div class="review-header">
                <span class="review-stars">${stars}</span>
                <span class="review-sentiment-tag ${sentimentCls}">${sentimentLabel}</span>
                <span class="review-product-tag" title="${productTitle}">${productTitle}</span>
                <span class="review-date">${date}</span>
            </div>
            <div class="review-content">${content}</div>
            <div class="review-footer">
                ${r.has_image ? '<span style="font-size:0.78rem;color:#64748B;">&#128247; 带图</span>' : ''}
            </div>
        </div>`;
    }).join('');
}

function renderStars(rating) {
    let html = '';
    for (let i = 1; i <= 5; i++) {
        html += i <= Math.round(rating) ? '&#9733;' : '&#9734;';
    }
    return html;
}

function filterReviewByProduct(product_id) {
    REVIEW_STATE.productId = product_id;
    loadReviewSummary();
    loadReviewList(product_id, REVIEW_STATE.sentiment);
}

function filterReviewBySentiment(sentiment) {
    REVIEW_STATE.sentiment = sentiment;
    // 更新按钮状态
    document.querySelectorAll('.review-sentiment-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.sentiment === sentiment);
    });
    loadReviewList(REVIEW_STATE.productId, sentiment);
}

function setupReviewUpload() {
    const uploadArea = document.getElementById('reviewUploadArea');
    const fileInput = document.getElementById('reviewFileInput');

    if (!uploadArea || !fileInput) return;

    // 点击上传
    uploadArea.addEventListener('click', () => fileInput.click());

    fileInput.addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (file) {
            uploadReviewFile(file);
            fileInput.value = '';
        }
    });

    // 拖拽上传
    uploadArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadArea.classList.add('dragover');
    });
    uploadArea.addEventListener('dragleave', (e) => {
        e.preventDefault();
        uploadArea.classList.remove('dragover');
    });
    uploadArea.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadArea.classList.remove('dragover');
        const file = e.dataTransfer.files[0];
        if (file) uploadReviewFile(file);
    });
}
/* ================================================================
   模块10: 市场分析 (P4)
================================================================ */
const MARKET_STATE = {
    activeTab: 'keywords',
    activeRankingTab: 'growth',
    selectedReport: '',
    sortKey: 'rank',
    sortOrder: 'asc',
    allKeywords: [],
};

// 机会分类颜色映射
const OPP_CATEGORY_COLORS = {
    '行业必争词': { cls: 'opp-red', color: '#EF4444' },
    '供给不足蓝海词': { cls: 'opp-green', color: '#10B981' },
    '小众高意向蓝海词': { cls: 'opp-blue', color: '#3B82F6' },
    '需要关注词': { cls: 'opp-yellow', color: '#F59E0B' },
    '常规词': { cls: 'opp-gray', color: '#94A3B8' },
};

// 需求维度颜色映射
const NEED_DIM_COLORS = {
    '品类需求': '#7B3FF2',
    '适用场景需求': '#1890ff',
    '风格需求': '#fa8c16',
    '属性需求': '#52c41a',
    '其它定制需求': '#f5222d',
    '人群需求': '#eb2f96',
    '功能属性需求': '#13c2c2',
    '品牌需求': '#2f54eb',
};

async function loadMarketSummary(reportId) {
    let url = '/api/market/summary';
    if (reportId) url += '?report_id=' + encodeURIComponent(reportId);
    const data = await apiFetch(url);
    if (!data || !data.meta) {
        document.getElementById('marketUploadArea').style.display = '';
        document.getElementById('marketReportSelector').style.display = 'none';
        document.getElementById('marketSummaryRow').style.display = 'none';
        document.getElementById('marketTabs').style.display = 'none';
        return;
    }

    // 隐藏加载占位符
    const marketLoading = document.getElementById('marketSummaryLoading');
    if (marketLoading) marketLoading.style.display = 'none';

    const meta = data.meta;
    const summary = data.summary || {};

    // 显示数据区域，隐藏上传区域
    document.getElementById('marketUploadArea').style.display = 'none';
    document.getElementById('marketReportSelector').style.display = '';
    document.getElementById('marketSummaryRow').style.display = '';
    document.getElementById('marketTabs').style.display = '';

    // 填充概览卡片
    document.getElementById('ms-total-keywords').textContent = fmtNum(meta.total_keywords);
    document.getElementById('ms-growing').textContent = fmtNum(summary.growing_count || 0);
    document.getElementById('ms-declining').textContent = fmtNum(summary.declining_count || 0);
    document.getElementById('ms-main-dim').textContent = summary.main_dimension || '--';
    document.getElementById('ms-main-dim-count').textContent = summary.main_dim_count ? `${summary.main_dim_count} 个关键词` : '';
    document.getElementById('ms-top-keyword').textContent = summary.top_keyword ? `TOP: ${summary.top_keyword} (${fmtNum(summary.top_pop)})` : '';
    document.getElementById('ms-periods').textContent = `${meta.period_30d || ''} / ${meta.period_7d || ''}`;
    document.getElementById('ms-top5-keywords').textContent = meta.top5_keywords ? `TOP5: ${meta.top5_keywords}` : '';
    document.getElementById('marketCategoryInfo').textContent = meta.category_path ? `${meta.category_short || meta.category_path}` : '';

    // 加载报告列表
    loadMarketReports();

    // 加载各tab数据
    loadMarketKeywords();
    loadMarketNeedStats();
    loadMarketRankings(MARKET_STATE.activeRankingTab);
    loadMarketHistograms();
    loadMarketTabOpportunities();
}

async function loadMarketKeywords() {
    const data = await apiFetch('/api/market/keywords?limit=50');
    if (!data || !data.keywords) return;
    MARKET_STATE.allKeywords = data.keywords;
    renderMarketKeywordTable(data.keywords);
}

async function loadMarketNeedStats() {
    const data = await apiFetch('/api/market/need_stats');
    if (!data) return;

    // 渲染饼图
    const needStats = data.need_stats || {};
    const pieData = Object.entries(needStats).map(([name, info]) => ({
        name: name,
        value: info.count || 0,
        itemStyle: { color: NEED_DIM_COLORS[name] || '#64748B' },
    }));

    const pieChart = getChart('chartMarketNeedPie');
    const pieOpt = baseOption();
    pieOpt.tooltip.trigger = 'item';
    pieOpt.tooltip.formatter = '{b}: {c} ({d}%)';
    pieOpt.legend = {
        orient: 'horizontal', bottom: 0,
        textStyle: { color: '#94A3B8', fontSize: 11 },
        type: 'scroll',
    };
    pieOpt.series = [{
        type: 'pie', radius: ['35%', '65%'], center: ['50%', '45%'],
        data: pieData.length > 0 ? pieData : [{ name: '暂无数据', value: 1, itemStyle: { color: '#334155' } }],
        label: { show: false },
        emphasis: {
            label: { show: true, color: '#F1F5F9', fontSize: 12 },
            itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0,0,0,0.5)' },
        },
        itemStyle: { borderRadius: 6, borderColor: '#1E293B', borderWidth: 2 },
    }];
    pieChart.setOption(pieOpt, true);
    addChartSaveBtn(pieChart, 'chartMarketNeedPie');

    // 渲染维度列表
    renderMarketDimensionList(data.dimension_details || {});
}

async function loadMarketRankings(type) {
    const data = await apiFetch(`/api/market/rankings?ranking_type=${type}`);
    if (!data || !data.rankings) return;
    const products = data.rankings[type] || [];
    renderMarketRankingCards(products, type);
}

async function loadMarketHistograms() {
    const data = await apiFetch('/api/market/histograms');
    if (!data || !data.histograms) return;
    renderMarketHistograms(data.histograms);
}

async function loadMarketTabOpportunities() {
    const data = await apiFetch('/api/market/opportunities');
    if (!data || !data.opportunities) return;

    const container = document.getElementById('marketOpportunityList');
    if (data.opportunities.length === 0) {
        container.innerHTML = '<div class="market-no-data">暂无蓝海机会词</div>';
        return;
    }

    container.innerHTML = data.opportunities.map(opp => {
        const catInfo = OPP_CATEGORY_COLORS[opp.opportunity_category] || OPP_CATEGORY_COLORS['常规词'];
        const tags = (opp.need_tags || []).map(t => {
            const dimColor = NEED_DIM_COLORS[t.dim] || '#64748B';
            return `<span class="market-tag" style="background:${dimColor}22;color:${dimColor};">${t.dim}</span>`;
        }).join('');
        return `<div class="market-opportunity-item">
            <span class="opp-keyword">${opp.keyword}</span>
            <span class="opp-stats">
                <span>人气: ${fmtNum(opp.pop_30d)}</span>
                <span>点击率: ${opp.ctr_7d != null ? (opp.ctr_7d * 100).toFixed(1) + '%' : '--'}</span>
                <span>转化率: ${opp.cvr_30d != null ? (opp.cvr_30d * 100).toFixed(1) + '%' : '--'}</span>
            </span>
            ${tags}
            <span class="market-tag ${catInfo.cls}">${opp.opportunity_category}</span>
            <span class="opp-score" style="color:${catInfo.color};">${opp.opportunity_score != null ? opp.opportunity_score.toFixed(1) : '--'}</span>
        </div>`;
    }).join('');
}

async function loadMarketReports() {
    const data = await apiFetch('/api/market/reports');
    if (!data || !data.reports) return;

    const select = document.getElementById('marketReportSelect');
    select.innerHTML = '<option value="">选择分析报告...</option>';
    data.reports.forEach(r => {
        const opt = document.createElement('option');
        opt.value = r.id;
        opt.textContent = `${r.analysis_date || r.created_at} - ${r.category_path} (${r.total_keywords}词)`;
        select.appendChild(opt);
    });
}

function switchMarketTab(tabName) {
    MARKET_STATE.activeTab = tabName;

    // 更新tab按钮状态
    document.querySelectorAll('.market-tab-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.tab === tabName);
    });

    // 更新tab内容显示
    document.querySelectorAll('.market-tab-content').forEach(content => {
        content.classList.toggle('active', content.id === 'marketTab-' + tabName);
    });

    // 切换到榜单tab时重新加载
    if (tabName === 'rankings') {
        loadMarketRankings(MARKET_STATE.activeRankingTab);
    }
}

function switchRankingTab(type) {
    MARKET_STATE.activeRankingTab = type;

    document.querySelectorAll('.market-ranking-tab-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.rank === type);
    });

    loadMarketRankings(type);
}

async function uploadMarketFiles(files) {
    if (!files || files.length === 0) return;

    const formData = new FormData();
    for (let i = 0; i < files.length; i++) {
        formData.append('files', files[i]);
    }

    try {
        const resp = await fetch('/api/upload/market', { method: 'POST', body: formData });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const result = await resp.json();
        if (result.success) {
            showToast(`上传成功，共导入 ${result.count} 条数据`, 'success');
            loadMarketSummary();
        } else {
            showToast('上传失败：' + (result.message || result.error || '未知错误'), 'error');
        }
    } catch (e) {
        console.error('Market upload error:', e);
        showToast('上传失败：' + e.message, 'error');
    }
}

function setupMarketUpload() {
    const uploadArea = document.getElementById('marketUploadArea');
    const fileInput = document.getElementById('marketFileInput');

    if (!uploadArea || !fileInput) return;

    uploadArea.addEventListener('click', () => fileInput.click());

    fileInput.addEventListener('change', (e) => {
        const files = Array.from(e.target.files);
        if (files.length > 0) {
            uploadMarketFiles(files);
            fileInput.value = '';
        }
    });

    uploadArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadArea.classList.add('dragover');
    });
    uploadArea.addEventListener('dragleave', (e) => {
        e.preventDefault();
        uploadArea.classList.remove('dragover');
    });
    uploadArea.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadArea.classList.remove('dragover');
        const files = Array.from(e.dataTransfer.files);
        if (files.length > 0) uploadMarketFiles(files);
    });
}

function triggerMarketReUpload() {
    const fileInput = document.getElementById('marketFileInput');
    if (fileInput) fileInput.click();
}

function onMarketReportChange(reportId) {
    if (reportId) {
        loadMarketSummary(reportId);
    }
}

function renderMarketKeywordTable(keywords) {
    const tbody = document.getElementById('marketKeywordBody');
    if (!keywords || keywords.length === 0) {
        tbody.innerHTML = '<tr><td colspan="9" class="market-no-data">暂无数据</td></tr>';
        return;
    }

    // 排序
    const sorted = [...keywords].sort((a, b) => {
        let va = a[MARKET_STATE.sortKey];
        let vb = b[MARKET_STATE.sortKey];
        if (typeof va === 'string') {
            return MARKET_STATE.sortOrder === 'asc' ? va.localeCompare(vb) : vb.localeCompare(va);
        }
        va = va || 0;
        vb = vb || 0;
        return MARKET_STATE.sortOrder === 'asc' ? va - vb : vb - va;
    });

    tbody.innerHTML = sorted.map(kw => {
        // 变化趋势
        const change = kw.change_pct;
        let changeHtml = '--';
        if (change != null) {
            const cls = change > 0 ? 'market-change-up' : change < 0 ? 'market-change-down' : 'market-change-flat';
            const arrow = change > 0 ? '&#9650;' : change < 0 ? '&#9660;' : '&#8212;';
            changeHtml = `<span class="${cls}">${arrow} ${Math.abs(change).toFixed(1)}%</span>`;
        }

        // 需求标签
        const tags = (kw.need_tags || []).map(t => {
            const dimColor = NEED_DIM_COLORS[t.dim] || '#64748B';
            return `<span class="market-tag" style="background:${dimColor}22;color:${dimColor};">${t.dim}</span>`;
        }).join('');

        // 机会分类
        const catInfo = OPP_CATEGORY_COLORS[kw.opportunity_category] || OPP_CATEGORY_COLORS['常规词'];
        const oppBadge = `<span class="market-tag ${catInfo.cls}">${kw.opportunity_category || '常规词'}</span>`;

        return `<tr>
            <td>${kw.rank != null ? kw.rank : '--'}</td>
            <td style="font-weight:500;color:#F1F5F9;">${kw.keyword}</td>
            <td>${fmtNum(kw.pop_30d)}</td>
            <td>${fmtNum(kw.pop_7d)}</td>
            <td>${changeHtml}</td>
            <td>${kw.ctr_7d != null ? (kw.ctr_7d * 100).toFixed(1) + '%' : '--'}</td>
            <td>${kw.cvr_30d != null ? (kw.cvr_30d * 100).toFixed(1) + '%' : '--'}</td>
            <td>${tags || '<span style="color:#64748B;">--</span>'}</td>
            <td>${oppBadge}</td>
        </tr>`;
    }).join('');

    // 更新表头排序图标
    document.querySelectorAll('.market-keyword-table thead th[data-key]').forEach(th => {
        const key = th.dataset.key;
        th.classList.toggle('sorted', key === MARKET_STATE.sortKey);
        const icon = th.querySelector('.sort-icon');
        if (icon) {
            if (key === MARKET_STATE.sortKey) {
                icon.textContent = MARKET_STATE.sortOrder === 'asc' ? '&#9650;' : '&#9660;';
            } else {
                icon.textContent = '--';
            }
        }
    });
}

function sortMarketTable(key) {
    if (MARKET_STATE.sortKey === key) {
        MARKET_STATE.sortOrder = MARKET_STATE.sortOrder === 'asc' ? 'desc' : 'asc';
    } else {
        MARKET_STATE.sortKey = key;
        MARKET_STATE.sortOrder = key === 'rank' ? 'asc' : 'desc';
    }
    renderMarketKeywordTable(MARKET_STATE.allKeywords);
}

function renderMarketRankingCards(products, type) {
    const container = document.getElementById('marketRankingCards');
    if (!products || products.length === 0) {
        container.innerHTML = '<div class="market-no-data" style="grid-column:1/-1;">暂无数据</div>';
        return;
    }

    const scoreLabels = {
        growth: { label: '增长潜力', key: 'growth', color: '#10B981' },
        overall: { label: '综合实力', key: 'overall', color: '#3B82F6' },
        top: { label: '头部精选', key: 'top_score', color: '#F59E0B' },
        stab: { label: '稳定表现', key: 'stab_score', color: '#8B5CF6' },
    };

    container.innerHTML = products.slice(0, 20).map((prod, idx) => {
        const imgSrc = prod.img_url || '';
        const imgHtml = imgSrc
            ? `<img class="prod-img" src="${imgSrc}" alt="${prod.name}" onerror="this.style.display='none';this.nextElementSibling.style.display='flex';"><div style="display:none;width:80px;height:80px;border-radius:8px;background:#334155;align-items:center;justify-content:center;color:#64748B;font-size:1.5rem;flex-shrink:0;">&#128722;</div>`
            : `<div style="width:80px;height:80px;border-radius:8px;background:#334155;display:flex;align-items:center;justify-content:center;color:#64748B;font-size:1.5rem;flex-shrink:0;">&#128722;</div>`;

        const completeness = prod.completeness || 0;
        const compCls = completeness >= 80 ? 'high' : completeness >= 50 ? 'medium' : 'low';

        const scoreBars = Object.values(scoreLabels).map(s => {
            const val = prod[s.key] || 0;
            return `<div class="score-row">
                <span class="score-label">${s.label}</span>
                <div class="score-track"><div class="score-fill" style="width:${val}%;background:${s.color};"></div></div>
                <span class="score-val">${val.toFixed(0)}</span>
            </div>`;
        }).join('');

        const kwTags = (prod.kw_tags || []).slice(0, 3).map(t =>
            `<span class="market-tag" style="background:#334155;color:#94A3B8;">${t}</span>`
        ).join('');

        return `<div class="market-ranking-card">
            ${imgHtml}
            <div class="prod-info">
                <div class="prod-name" title="${prod.name || ''}">${idx + 1}. ${prod.name || '--'}</div>
                <div class="prod-shop">${prod.shop_name || '--'}</div>
                ${scoreBars}
                <div class="prod-stats">
                    <span class="prod-stat">买家: <span>${fmtNum(prod.total_buyers || prod.buyers)}</span></span>
                    <span class="prod-stat">访客: <span>${fmtNum(prod.total_visitors || prod.visitors)}</span></span>
                    <span class="completeness ${compCls}">完整度 ${completeness.toFixed(0)}%</span>
                </div>
                ${kwTags ? `<div style="margin-top:6px;">${kwTags}</div>` : ''}
            </div>
        </div>`;
    }).join('');
}

function renderMarketDimensionList(details) {
    const container = document.getElementById('marketDimensionList');
    if (!details || Object.keys(details).length === 0) {
        container.innerHTML = '<div class="market-no-data">暂无数据</div>';
        return;
    }

    // 找出最大人气值用于进度条比例
    let maxPop = 0;
    Object.values(details).forEach(dim => {
        (dim.keywords || []).forEach(kw => {
            if (kw.pop > maxPop) maxPop = kw.pop;
        });
    });
    maxPop = Math.max(maxPop, 1);

    container.innerHTML = Object.entries(details).map(([dimName, dimInfo]) => {
        const color = NEED_DIM_COLORS[dimName] || '#64748B';
        const keywords = (dimInfo.keywords || []).slice(0, 10);
        const kwRows = keywords.map(kw => {
            const pct = (kw.pop / maxPop * 100).toFixed(1);
            return `<div class="kw-row">
                <span class="kw-name" title="${kw.keyword}">${kw.keyword}</span>
                <div class="kw-bar-track"><div class="kw-bar-fill" style="width:${pct}%;background:${color};"></div></div>
                <span class="kw-pop">${fmtNum(kw.pop)}</span>
            </div>`;
        }).join('');

        return `<div class="market-dimension-item">
            <div class="dim-header" onclick="this.parentElement.classList.toggle('expanded')">
                <span class="dim-name">
                    <span class="dim-dot" style="background:${color};"></span>
                    ${dimName}
                </span>
                <span class="dim-count">${dimInfo.count || 0} 词 / 人气 ${fmtNum(dimInfo.total_pop || 0)}</span>
            </div>
            <div class="dim-keywords">${kwRows}</div>
        </div>`;
    }).join('');
}

function renderMarketHistograms(histograms) {
    const configs = [
        { id: 'chartMarketHistPop', key: 'pop', label: '搜索人气' },
        { id: 'chartMarketHistCtr', key: 'ctr', label: '点击率' },
        { id: 'chartMarketHistCvr', key: 'cvr', label: '转化率' },
        { id: 'chartMarketHistPrice', key: 'price', label: '价格' },
    ];

    configs.forEach(cfg => {
        const hist = histograms[cfg.key];
        if (!hist || !hist.labels || !hist.hist) return;

        const chart = getChart(cfg.id);
        const opt = baseOption();
        opt.tooltip.trigger = 'axis';
        opt.tooltip.axisPointer = { type: 'shadow' };
        opt.tooltip.formatter = params => `${params[0].name}<br/>数量：${fmtNum(params[0].value)}`;
        opt.grid = { left: 40, right: 10, top: 5, bottom: 20 };
        opt.xAxis = {
            type: 'category', data: hist.labels,
            axisLabel: { color: '#CBD5E1', fontSize: 10, rotate: hist.labels.length > 10 ? 30 : 0 },
        };
        opt.yAxis = {
            type: 'value',
            axisLabel: { color: '#94A3B8', fontSize: 10 },
            splitLine: { lineStyle: { color: '#1E293B', type: 'dashed' } },
        };
        opt.series = [{
            type: 'bar', data: hist.hist,
            barWidth: '70%',
            itemStyle: {
                borderRadius: [3, 3, 0, 0],
                color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                    { offset: 0, color: '#3B82F6' },
                    { offset: 1, color: '#1E40AF' },
                ]),
            },
        }];
        chart.setOption(opt, true);
        addChartSaveBtn(chart, cfg.id);
    });
}
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
        ${img ? `<img src="${img}" alt="${title}" loading="lazy" style="width:48px;height:48px;border-radius:8px;object-fit:cover;background:var(--bg-elevated);">` : ''}
        <div>
            <div style="font-size:1rem;font-weight:600;color:var(--text-primary);">${title}</div>
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
    const isLight = document.documentElement.classList.contains('light');
    const chartText = isLight ? '#526579' : '#94A3B8';
    const chartAxis = isLight ? '#8FA2B5' : '#334155';
    const chartGrid = isLight ? '#D9E2EA' : '#1E293B';
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
        textStyle: { color: chartText },
    };
    opt.grid = { left: 60, right: 60, top: 40, bottom: 30 };
    opt.xAxis.data = months;
    opt.yAxis = [
        {
            type: 'value',
            name: '金额',
            axisLine: { lineStyle: { color: chartAxis } },
            axisLabel: { color: '#94A3B8', formatter: v => (v / 10000).toFixed(0) + '万' },
            splitLine: { lineStyle: { color: chartGrid, type: 'dashed' } },
        },
        {
            type: 'value',
            name: '件数',
            axisLine: { lineStyle: { color: chartAxis } },
            axisLabel: { color: chartText },
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
            'gmv': '总销售额', 'net_sales': '净销售额', 'visitors': '总访客',
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
        'payment_amount': '总销售额',
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
/* ================================================================
   模块12: 运营工具箱
================================================================ */
let TOOL_LIST = [];
let CURRENT_TOOL = null;
let _importPollTimer = null; // 导入进度轮询定时器

/* ================================================================
   Feature 6: 导入进度轮询
================================================================ */
function pollImportProgress(taskId) {
    var progressBar = document.getElementById('importProgressBar');
    var progressText = document.getElementById('importProgressText');
    var progressContainer = document.getElementById('importProgressContainer');

    if (progressContainer) progressContainer.style.display = 'block';

    // 清理旧的轮询定时器
    if (_importPollTimer) clearInterval(_importPollTimer);
    _importPollTimer = setInterval(async function() {
        try {
            var res = await apiFetch('/api/import_progress/' + taskId);
            if (!res || !res.status) return;

            if (res.status === 'completed') {
                clearInterval(_importPollTimer);
                _importPollTimer = null;
                if (progressBar) progressBar.style.width = '100%';
                if (progressText) progressText.textContent = '导入完成！';
                showToast('✅ ' + res.message, 'success');

                // 渲染导入结果
                var resultArea = document.getElementById('toolResultArea');
                if (resultArea && res.result) {
                    renderImportResult(resultArea, res.result);
                }

                setTimeout(function() {
                    if (progressContainer) progressContainer.style.display = 'none';
                    refreshAll();
                }, 1500);
            } else if (res.status === 'error') {
                clearInterval(_importPollTimer);
                _importPollTimer = null;
                if (progressText) progressText.textContent = '导入失败: ' + res.message;
                showToast('❌ ' + res.message, 'error');

                var resultArea = document.getElementById('toolResultArea');
                if (resultArea) {
                    resultArea.innerHTML = '<div class="tool-result-msg error">❌ 导入失败：' + escapeHtml(res.message) + '</div>';
                }
            } else {
                if (progressBar) progressBar.style.width = res.progress + '%';
                if (progressText) progressText.textContent = res.message + ' (' + res.progress + '%)';
            }
        } catch(e) {
            console.error('进度查询失败:', e);
        }
    }, 1000);
}

function openToolbox() {
    document.getElementById('toolboxDrawer').classList.add('open');
    document.getElementById('toolboxOverlay').classList.add('open');
}

function closeToolbox() {
    document.getElementById('toolboxDrawer').classList.remove('open');
    document.getElementById('toolboxOverlay').classList.remove('open');
    // 清理导入进度轮询
    if (_importPollTimer) {
        clearInterval(_importPollTimer);
        _importPollTimer = null;
    }
}

async function loadToolList() {
    try {
        const data = await apiFetch('/api/tools/list');
        if (!data || !data.tools) return;
        TOOL_LIST = data.tools;

        const grid = document.getElementById('toolGridPanel');
        grid.innerHTML = '';

        data.tools.forEach(tool => {
        const isDisabled = tool.status === 'coming_soon';
        const paramLabels = (tool.params || []).map(p => p.label).join('、');
        const card = document.createElement('div');
        card.className = 'tool-card' + (isDisabled ? ' disabled' : '');
        card.innerHTML = `
            <div class="tool-card-header">
                <span class="tool-card-icon">${tool.icon}</span>
                <span class="tool-card-name">${tool.name}</span>
            </div>
            <div class="tool-card-desc">${tool.desc}</div>
            ${isDisabled ? '<span class="tool-card-status">即将上线</span>' : ''}
            ${paramLabels ? `<div class="tool-card-params">需要：${paramLabels}</div>` : ''}
        `;
        if (!isDisabled) {
            card.addEventListener('click', () => selectTool(tool.id));
        }
        grid.appendChild(card);
    });
    } catch (e) {
        // /api/tools/list not available - toolbox feature not implemented yet
        const grid = document.getElementById('toolGridPanel');
        if (grid) grid.innerHTML = '<div class="tool-card disabled"><div class="tool-card-desc">工具箱功能开发中...</div></div>';
    }
}

function selectTool(toolId) {
    const tool = TOOL_LIST.find(t => t.id === toolId);
    if (!tool) return;
    CURRENT_TOOL = tool;

    document.getElementById('toolExecTitle').textContent = tool.icon + ' ' + tool.name;
    document.getElementById('toolExecDesc').textContent = tool.desc;

    // Build param form
    const form = document.getElementById('toolParamForm');
    form.innerHTML = '';
    (tool.params || []).forEach(param => {
        const group = document.createElement('div');
        group.className = 'tool-param-group';
        if (param.type === 'file') {
            group.innerHTML = `
                <label class="tool-param-label">${param.label}</label>
                <input type="file" class="tool-param-input" data-key="${param.key}"
                    accept=".xlsx,.xls" />
                <div class="tool-param-hint">支持 .xlsx / .xls 格式，可包含多个Sheet（生意参谋、全店单品、付费报表、DMP等）</div>
            `;
        } else if (param.type === 'select') {
            const options = (param.options || []).map(o =>
                `<option value="${escapeHtml(o.value)}">${escapeHtml(o.label)}</option>`
            ).join('');
            group.innerHTML = `
                <label class="tool-param-label">${param.label}</label>
                <select class="tool-param-input" data-key="${param.key}">
                    ${options}
                </select>
            `;
        } else if (param.type === 'textarea') {
            group.innerHTML = `
                <label class="tool-param-label">${param.label}</label>
                <textarea class="tool-param-input tool-param-textarea" data-key="${param.key}"
                    placeholder="${param.placeholder || ''}" rows="4"></textarea>
            `;
        } else {
            group.innerHTML = `
                <label class="tool-param-label">${param.label}</label>
                <input type="${param.type || 'text'}" class="tool-param-input" data-key="${param.key}"
                    placeholder="${param.placeholder || ''}" />
            `;
        }
        form.appendChild(group);
    });

    // Reset result area
    document.getElementById('toolResultArea').innerHTML =
        '<div class="tool-result-placeholder">执行结果将显示在这里</div>';

    // Show exec panel, hide grid
    document.getElementById('toolGridPanel').classList.add('hidden');
    document.getElementById('toolExecPanel').classList.add('active');
}

function backToToolList() {
    CURRENT_TOOL = null;
    document.getElementById('toolGridPanel').classList.remove('hidden');
    document.getElementById('toolExecPanel').classList.remove('active');
}

async function executeCurrentTool() {
    if (!CURRENT_TOOL) return;

    const form = document.getElementById('toolParamForm');
    const inputs = form.querySelectorAll('.tool-param-input');
    const params = {};
    inputs.forEach(input => {
        const key = input.dataset.key;
        if (input.type === 'file') {
            params[key] = input.files[0] || null;
        } else {
            params[key] = input.value.trim();
        }
    });

    const resultArea = document.getElementById('toolResultArea');
    resultArea.innerHTML = '<div class="tool-result-placeholder">⏳ 执行中，请稍候...</div>';

    try {
        // data_import 工具直接调用 /api/upload/data
        if (CURRENT_TOOL.id === 'data_import') {
            const file = params.file;
            if (!file) {
                resultArea.innerHTML = '<div class="tool-result-msg error">请先选择Excel文件</div>';
                return;
            }

            const fd = new FormData();
            fd.append('file', file);

            const resp = await fetch('/api/upload/data', { method: 'POST', body: fd });
            if (!resp.ok) {
                resultArea.innerHTML = '<div class="tool-result-msg error">❌ 导入请求失败: HTTP ' + resp.status + '</div>';
                return;
            }
            const data = await resp.json();

            if (data.error) {
                resultArea.innerHTML = `<div class="tool-result-msg error">❌ 导入失败：${data.error}</div>`;
            } else if (data.task_id) {
                // 使用进度轮询追踪导入任务
                resultArea.innerHTML = '<div class="tool-result-placeholder">⏳ 已提交导入任务，正在处理中...</div>';
                pollImportProgress(data.task_id);
            } else if (data.success) {
                renderImportResult(resultArea, data);
            } else {
                resultArea.innerHTML = '<div class="tool-result-msg error">未知错误</div>';
            }
            return;
        }

        // 其他工具走通用 execute 接口
        const hasFile = Object.values(params).some(v => v instanceof File);
        let resp;
        if (hasFile) {
            const fd = new FormData();
            fd.append('tool_id', CURRENT_TOOL.id);
            Object.entries(params).forEach(([k, v]) => { if (v instanceof File) fd.append(k, v); else fd.append(k, v); });
            resp = await fetch('/api/tools/execute', { method: 'POST', body: fd });
        } else {
            resp = await fetch('/api/tools/execute', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ tool_id: CURRENT_TOOL.id, params }),
            });
        }
        if (!resp.ok) {
            const errText = await resp.text().catch(() => '');
            resultArea.innerHTML = `<div class="tool-result-msg error">❌ 执行失败 (${resp.status}): ${escapeHtml(errText || resp.statusText)}</div>`;
            return;
        }
        const data = await resp.json();

        if (data.error) {
            // 检查 result 中是否包含 error（工具执行返回的）
            if (data.result && data.result.error) {
                resultArea.innerHTML = `<div class="tool-result-msg error">${escapeHtml(data.result.error)}</div>`;
            } else {
                resultArea.innerHTML = `<div class="tool-result-msg error">${escapeHtml(data.message || '执行失败')}</div>`;
            }
        } else if (data.result) {
            // 根据工具类型分发渲染
            if (CURRENT_TOOL.id === 'main_image_suggest') {
                renderMainImageSuggestResult(resultArea, data.result);
            } else if (CURRENT_TOOL.id === 'review_reply') {
                renderReviewReplyResult(resultArea, data.result);
            } else if (CURRENT_TOOL.id === 'product_diagnose') {
                renderProductDiagnoseResult(resultArea, data.result);
            } else {
                resultArea.innerHTML = '<div class="tool-result-msg success">执行完成</div>';
            }
        } else {
            resultArea.innerHTML = '<div class="tool-result-msg info">执行完成</div>';
        }
    } catch (e) {
        resultArea.innerHTML = `<div class="tool-result-msg error">请求失败: ${escapeHtml(e.message)}</div>`;
    }
}

/* ================================================================
   Feature 15: 评价生成主图建议 - 结果渲染
================================================================ */
function renderMainImageSuggestResult(container, result) {
    const suggestions = result.suggestions || {};
    const reviewCount = result.review_count || 0;
    const summary = result.analysis_summary || '';
    const corePoints = suggestions.core_selling_points || [];
    const scenes = suggestions.scene_suggestions || [];
    const keywords = suggestions.keyword_suggestions || [];
    const directions = suggestions.optimization_directions || [];

    // 核心卖点标签
    let coreHtml = '';
    if (corePoints.length > 0) {
        coreHtml = corePoints.map(p =>
            `<span class="tool-tag tool-tag-primary">${escapeHtml(p.name)} <span class="tool-tag-count">${p.count}</span></span>`
        ).join('');
    } else {
        coreHtml = '<span style="color:var(--text-muted);font-size:0.82rem;">暂无数据</span>';
    }

    // 场景建议列表
    let sceneHtml = '';
    if (scenes.length > 0) {
        sceneHtml = scenes.map(s =>
            `<div class="tool-scene-item">
                <span class="tool-scene-dot"></span>
                <span class="tool-scene-name">${escapeHtml(s.name)}</span>
                <span class="tool-scene-count">${s.count}次提及</span>
            </div>`
        ).join('');
    } else {
        sceneHtml = '<span style="color:var(--text-muted);font-size:0.82rem;">暂无数据</span>';
    }

    // 关键词建议
    let keywordHtml = '';
    if (keywords.length > 0) {
        keywordHtml = keywords.map(k =>
            `<span class="tool-keyword-chip">${escapeHtml(k.word)} <span class="tool-tag-count">${k.count}</span></span>`
        ).join('');
    } else {
        keywordHtml = '<span style="color:var(--text-muted);font-size:0.82rem;">暂无数据</span>';
    }

    // 优化方向
    let dirHtml = '';
    if (directions.length > 0) {
        dirHtml = directions.map((d, i) =>
            `<div class="tool-action-item">
                <span class="tool-action-num">${i + 1}</span>
                <span class="tool-action-text">${escapeHtml(d)}</span>
            </div>`
        ).join('');
    } else {
        dirHtml = '<span style="color:var(--text-muted);font-size:0.82rem;">暂无建议</span>';
    }

    container.innerHTML = `
        <div class="tool-result-section">
            <div class="tool-summary-card">
                <div class="tool-summary-icon">📊</div>
                <div class="tool-summary-info">
                    <div class="tool-summary-title">分析概览</div>
                    <div class="tool-summary-desc">共分析 <strong>${reviewCount}</strong> 条好评数据</div>
                </div>
            </div>
            <div class="tool-analysis-summary">${escapeHtml(summary)}</div>
        </div>

        <div class="tool-result-section">
            <div class="tool-section-title">🎯 核心卖点</div>
            <div class="tool-tags-container">${coreHtml}</div>
        </div>

        <div class="tool-result-section">
            <div class="tool-section-title">📍 场景建议</div>
            <div class="tool-scenes-list">${sceneHtml}</div>
        </div>

        <div class="tool-result-section">
            <div class="tool-section-title">🔑 关键词建议</div>
            <div class="tool-tags-container">${keywordHtml}</div>
        </div>

        <div class="tool-result-section">
            <div class="tool-section-title">💡 主图优化方向</div>
            <div class="tool-actions-list">${dirHtml}</div>
        </div>
    `;
}

/* ================================================================
   Feature 16: 评价仿写助手 - 结果渲染
================================================================ */
function renderReviewReplyResult(container, result) {
    const replies = result.replies || [];
    const sentiment = result.detected_sentiment || 'positive';
    const sentimentLabel = result.detected_sentiment_label || '未知';

    // 情感标签颜色映射
    const sentimentColors = {
        'positive': 'var(--success)',
        'neutral': 'var(--warning)',
        'negative': 'var(--danger)',
        'logistics': '#3B82F6',
        'quality': '#8B5CF6',
    };
    const sentimentColor = sentimentColors[sentiment] || 'var(--text-muted)';

    let repliesHtml = '';
    if (replies.length > 0) {
        repliesHtml = replies.map((r, i) =>
            `<div class="tool-reply-card">
                <div class="tool-reply-header">
                    <span class="tool-reply-label">${escapeHtml(r.style)}</span>
                    <button class="tool-copy-btn" onclick="copyReplyText(this, ${i})">复制</button>
                </div>
                <div class="tool-reply-content" id="reply-text-${i}">${escapeHtml(r.content)}</div>
            </div>`
        ).join('');
    }

    container.innerHTML = `
        <div class="tool-result-section">
            <div class="tool-sentiment-row">
                <span style="color:var(--text-secondary);font-size:0.85rem;">检测到的评价类型：</span>
                <span class="tool-sentiment-tag" style="border-color:${sentimentColor};color:${sentimentColor};">
                    ${escapeHtml(sentimentLabel)}
                </span>
            </div>
        </div>
        <div class="tool-replies-container">${repliesHtml}</div>
    `;
}

function copyReplyText(btn, index) {
    const textEl = document.getElementById('reply-text-' + index);
    if (!textEl) return;
    const text = textEl.textContent;
    navigator.clipboard.writeText(text).then(() => {
        btn.textContent = '已复制';
        btn.classList.add('copied');
        showToast('已复制到剪贴板', 'success');
        setTimeout(() => {
            btn.textContent = '复制';
            btn.classList.remove('copied');
        }, 2000);
    }).catch(() => {
        showToast('复制失败，请手动复制', 'error');
    });
}

/* ================================================================
   Feature 17: 商品详情页诊断 - 结果渲染
================================================================ */
function renderProductDiagnoseResult(container, result) {
    const productInfo = result.product_info || {};
    const diagnostics = result.diagnostics || [];
    const overallScore = result.overall_score || 0;
    const priorityActions = result.priority_actions || [];

    // 综合评分颜色
    let scoreColor = 'var(--success)';
    let scoreLevel = '优秀';
    if (overallScore < 40) { scoreColor = 'var(--danger)'; scoreLevel = '需改进'; }
    else if (overallScore < 60) { scoreColor = 'var(--warning)'; scoreLevel = '待优化'; }
    else if (overallScore < 80) { scoreColor = '#3B82F6'; scoreLevel = '良好'; }

    // 雷达图数据
    const radarLabels = diagnostics.map(d => d.area);
    const radarValues = diagnostics.map(d => d.score);

    // 诊断卡片
    const levelColors = {
        '优秀': 'var(--success)',
        '良好': '#3B82F6',
        '待优化': 'var(--warning)',
        '需改进': 'var(--danger)',
    };

    let diagCardsHtml = diagnostics.map(d => {
        const color = levelColors[d.level] || 'var(--text-muted)';
        return `<div class="tool-diag-card">
            <div class="tool-diag-card-header">
                <span class="tool-diag-area">${escapeHtml(d.area)}</span>
                <span class="tool-diag-level" style="color:${color};border-color:${color};">${escapeHtml(d.level)}</span>
            </div>
            <div class="tool-diag-score-bar">
                <div class="tool-diag-score-fill" style="width:${d.score}%;background:${color};"></div>
                <span class="tool-diag-score-num">${d.score}</span>
            </div>
            <div class="tool-diag-metric">${escapeHtml(d.metric || '')}</div>
            <div class="tool-diag-suggestion">${escapeHtml(d.suggestion || '')}</div>
        </div>`;
    }).join('');

    // 优先行动
    let priorityHtml = '';
    if (priorityActions.length > 0) {
        priorityHtml = priorityActions.map((p, i) =>
            `<div class="tool-priority-item">
                <span class="tool-priority-rank">${i + 1}</span>
                <div class="tool-priority-content">
                    <div class="tool-priority-area">${escapeHtml(p.area)}</div>
                    <div class="tool-priority-action">${escapeHtml(p.action)}</div>
                </div>
            </div>`
        ).join('');
    }

    container.innerHTML = `
        <div class="tool-result-section">
            <div class="tool-diag-header">
                <div class="tool-diag-product">
                    <div class="tool-diag-product-name">${escapeHtml(productInfo.title || '未知商品')}</div>
                    <div class="tool-diag-product-meta">
                        ${escapeHtml(productInfo.category || '-')} / ${escapeHtml(productInfo.tier || '-')}
                    </div>
                </div>
                <div class="tool-diag-overall" style="color:${scoreColor};">
                    <div class="tool-diag-overall-score">${overallScore}</div>
                    <div class="tool-diag-overall-label">${scoreLevel}</div>
                </div>
            </div>
        </div>

        <div class="tool-result-section">
            <div class="tool-section-title">📊 维度评分</div>
            <div class="tool-radar-chart" id="diagRadarChart" style="width:100%;height:280px;"></div>
        </div>

        <div class="tool-result-section">
            <div class="tool-section-title">📋 详细诊断</div>
            <div class="tool-diag-cards">${diagCardsHtml}</div>
        </div>

        <div class="tool-result-section">
            <div class="tool-section-title">🚀 优先行动</div>
            <div class="tool-priority-list">${priorityHtml}</div>
        </div>
    `;

    // 渲染雷达图
    _renderRadarChart('diagRadarChart', radarLabels, radarValues);
}

function _renderRadarChart(containerId, labels, values) {
    const container = document.getElementById(containerId);
    if (!container || typeof echarts === 'undefined') return;

    const chart = getOrCreateChart(containerId);
    if (!chart) return;
    const option = {
        tooltip: {
            trigger: 'item',
            formatter: function(params) {
                return params.name + ': ' + params.value + '分';
            }
        },
        radar: {
            indicator: labels.map(name => ({ name: name, max: 100 })),
            shape: 'polygon',
            splitNumber: 4,
            axisName: {
                color: '#9CA3AF',
                fontSize: 11,
            },
            splitLine: {
                lineStyle: { color: 'rgba(99,102,241,0.15)' }
            },
            splitArea: {
                areaStyle: { color: ['rgba(99,102,241,0.02)', 'rgba(99,102,241,0.05)'] }
            },
            axisLine: {
                lineStyle: { color: 'rgba(99,102,241,0.2)' }
            },
        },
        series: [{
            type: 'radar',
            data: [{
                value: values,
                name: '诊断评分',
                areaStyle: {
                    color: 'rgba(99,102,241,0.2)',
                },
                lineStyle: {
                    color: '#6366F1',
                    width: 2,
                },
                itemStyle: {
                    color: '#6366F1',
                },
                symbol: 'circle',
                symbolSize: 6,
            }]
        }]
    };
    chart.setOption(option);

    // 监听窗口大小变化
    const resizeHandler = () => chart.resize();
    window.addEventListener('resize', resizeHandler);
    // 在抽屉关闭时移除监听
    const observer = new MutationObserver(() => {
        if (!document.getElementById('toolboxDrawer').classList.contains('open')) {
            window.removeEventListener('resize', resizeHandler);
            chart.dispose();
            observer.disconnect();
        }
    });
    observer.observe(document.getElementById('toolboxDrawer'), { attributes: true, attributeFilter: ['class'] });
}

/* ================================================================
   通用: 数据导入结果渲染
================================================================ */
function renderImportResult(container, data) {
    const details = data.details || [];
    const totalRows = data.total_rows || 0;

    let detailHtml = '';
    if (details.length > 0) {
        detailHtml = '<div class="import-detail-list">';
        details.forEach(d => {
            let statusIcon, statusClass;
            if (d.status === 'success') {
                statusIcon = '[OK]';
                statusClass = 'success';
            } else if (d.status === 'skipped') {
                statusIcon = '[-]';
                statusClass = 'skipped';
            } else if (d.status === 'warning') {
                statusIcon = '[!]';
                statusClass = 'warning';
            } else {
                statusIcon = '[X]';
                statusClass = 'error';
            }

            const rowInfo = d.rows ? `（${d.rows} 行）` : '';
            const reason = d.reason ? ` — ${d.reason}` : '';
            detailHtml += `<div class="import-detail-item ${statusClass}">
                ${statusIcon} <strong>${d.sheet}</strong> ${rowInfo}${reason}
            </div>`;
        });
        detailHtml += '</div>';
    }

    container.innerHTML = `
        <div class="tool-result-msg success">
            ✅ 导入完成！共导入 <strong>${totalRows}</strong> 行数据
        </div>
        ${detailHtml}
        <div class="import-result-actions">
            <button class="tool-execute-btn" onclick="afterImportRefresh()" style="margin-top:8px;font-size:13px;">
                🔄 刷新仪表盘数据
            </button>
        </div>
    `;
}

async function afterImportRefresh() {
    closeToolbox();
    await refreshAll();
}

function initToolbox() {
    loadToolList();
    loadScheduledTasks();
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') closeToolbox();
    });
}

/* ================================================================
   定时任务管理
================================================================ */
function updateScheduleExpr() {
    const type = document.getElementById('scheduleType').value;
    const dayOfWeek = document.getElementById('scheduleDayOfWeek');
    const dayOfMonth = document.getElementById('scheduleDayOfMonth');
    dayOfWeek.style.display = type === 'weekly' ? 'block' : 'none';
    dayOfMonth.style.display = type === 'monthly' ? 'block' : 'none';
}

function _buildCronExpr() {
    const type = document.getElementById('scheduleType').value;
    const time = document.getElementById('scheduleTime').value || '08:00';
    if (type === 'daily') return `daily ${time}`;
    if (type === 'weekly') {
        const day = document.getElementById('scheduleDayOfWeek').value;
        return `weekly ${day} ${time}`;
    }
    if (type === 'monthly') {
        const dom = document.getElementById('scheduleDayOfMonth').value || '1';
        return `monthly ${dom} ${time}`;
    }
    return `daily ${time}`;
}

async function loadScheduledTasks() {
    const listEl = document.getElementById('scheduleList');
    if (!listEl) return;

    const tasks = await apiFetch('/api/scheduled_tasks');
    if (!tasks || !Array.isArray(tasks)) {
        listEl.innerHTML = '<div style="text-align:center;color:var(--text-muted);padding:16px;font-size:0.82rem;">暂无定时任务</div>';
        return;
    }

    if (tasks.length === 0) {
        listEl.innerHTML = '<div style="text-align:center;color:var(--text-muted);padding:16px;font-size:0.82rem;">暂无定时任务</div>';
        return;
    }

    listEl.innerHTML = tasks.map(t => {
        const statusDot = t.status === 'active' ? '<span style="color:#22C55E;">&#9679;</span>' :
                          t.status === 'running' ? '<span style="color:#3B82F6;">&#9679;</span>' :
                          '<span style="color:#EF4444;">&#9679;</span>';
        const enabledText = t.enabled ? '已启用' : '已停用';
        const lastRunText = t.last_run ? t.last_run : '从未运行';
        const nextRunText = t.next_run ? t.next_run : '--';

        return `
            <div class="schedule-item ${t.enabled ? '' : 'disabled'}">
                <div class="schedule-item-header">
                    <span class="schedule-item-name">${escapeHtml(t.task_name)}</span>
                    <span class="cron-badge">${escapeHtml(t.cron_label || t.cron_expr)}</span>
                    ${statusDot}
                </div>
                <div class="schedule-item-meta">
                    <span>上次运行: ${escapeHtml(lastRunText)}</span>
                    <span>下次运行: ${escapeHtml(nextRunText)}</span>
                </div>
                <div class="schedule-item-actions">
                    <button class="schedule-action-btn" onclick="toggleScheduledTask(${t.id}, ${!t.enabled})" title="${t.enabled ? '停用' : '启用'}">${t.enabled ? '&#9632; 停用' : '&#9654; 启用'}</button>
                    <button class="schedule-action-btn" onclick="runScheduledTaskNow(${t.id})" title="立即运行">&#9654; 立即运行</button>
                    <button class="schedule-action-btn danger" onclick="deleteScheduledTask(${t.id})" title="删除">&#128465; 删除</button>
                </div>
            </div>
        `;
    }).join('');
}

async function addScheduledTask() {
    const taskName = document.getElementById('scheduleTaskName').value.trim();
    if (!taskName) {
        showToast('请输入任务名称', 'warning');
        return;
    }

    const cronExpr = _buildCronExpr();
    const filePattern = document.getElementById('scheduleFilePattern').value.trim() || '*.xlsx';

    const result = await apiFetch('/api/scheduled_tasks', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task_name: taskName, cron_expr: cronExpr, file_pattern: filePattern }),
    });

    if (result && result.success) {
        showToast('任务已创建', 'success');
        document.getElementById('scheduleTaskName').value = '';
        loadScheduledTasks();
    } else {
        showToast('创建任务失败', 'error');
    }
}

async function toggleScheduledTask(id, enabled) {
    const result = await apiFetch(`/api/scheduled_tasks/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled: enabled }),
    });

    if (result && result.success) {
        showToast(enabled ? '任务已启用' : '任务已停用', 'success');
        loadScheduledTasks();
    } else {
        showToast('操作失败', 'error');
    }
}

async function deleteScheduledTask(id) {
    if (!confirm('确定要删除此任务吗？')) return;

    const result = await apiFetch(`/api/scheduled_tasks/${id}`, {
        method: 'DELETE',
    });

    if (result && result.success) {
        showToast('任务已删除', 'success');
        loadScheduledTasks();
    } else {
        showToast('删除失败', 'error');
    }
}

async function runScheduledTaskNow(id) {
    showToast('正在执行任务...', 'info');
    const result = await apiFetch(`/api/scheduled_tasks/${id}/run`, {
        method: 'POST',
    });

    if (result && result.success) {
        showToast(result.message || '任务执行完成', 'success');
        loadScheduledTasks();
    } else {
        showToast('执行失败', 'error');
    }
}
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
/* ================================================================
   搜索词效能矩阵
================================================================ */

let KW_STATE = { date: '', category: '', search: '', sort: 'efficacy', order: 'desc', page: 1 };

async function loadKeywords() {
    const container = document.getElementById('keywordsContainer');
    if (!container) return;

    const params = new URLSearchParams(KW_STATE);
    try {
        const data = await apiFetch(`/api/keywords?${params}`);
        renderKeywordsSummary(data);
        renderKeywordsTable(data);
    } catch (e) {
        container.innerHTML = `<div class="empty-state">加载失败: ${e.message}</div>`;
    }
}

function renderKeywordsSummary(data) {
    const el = document.getElementById('kwSummary');
    if (!el || !data.summary) return;
    const s = data.summary;
    el.innerHTML = `
        <div class="kw-stat-card">
            <div class="kw-stat-value">${s.total || 0}</div>
            <div class="kw-stat-label">总词数</div>
        </div>
        <div class="kw-stat-card kw-blue">
            <div class="kw-stat-value">${s.blue_ocean || 0}</div>
            <div class="kw-stat-label">🌊 蓝海词</div>
        </div>
        <div class="kw-stat-card kw-traffic">
            <div class="kw-stat-value">${s.traffic || 0}</div>
            <div class="kw-stat-label">⚔️ 流量词</div>
        </div>
        <div class="kw-stat-card kw-dead">
            <div class="kw-stat-value">${s.dead || 0}</div>
            <div class="kw-stat-label">📉 废词</div>
        </div>
        <div class="kw-stat-card">
            <div class="kw-stat-value">${s.total_cost ? '¥' + (s.total_cost/10000).toFixed(1) + '万' : '--'}</div>
            <div class="kw-stat-label">总花费</div>
        </div>
        <div class="kw-stat-card">
            <div class="kw-stat-value">${s.total_gmv ? '¥' + (s.total_gmv/10000).toFixed(1) + '万' : '--'}</div>
            <div class="kw-stat-label">总成交</div>
        </div>
        <div class="kw-stat-card">
            <div class="kw-stat-value">${s.avg_roi ? s.avg_roi.toFixed(2) : '--'}</div>
            <div class="kw-stat-label">平均ROI</div>
        </div>
    `;
}

function renderKeywordsTable(data) {
    const el = document.getElementById('kwTableBody');
    const pagination = document.getElementById('kwPagination');
    if (!el) return;

    if (!data.items || data.items.length === 0) {
        el.innerHTML = '<tr><td colspan="8" style="text-align:center;padding:40px;color:var(--text-secondary);">暂无搜索词数据，请先上传搜索词报表</td></tr>';
        if (pagination) pagination.innerHTML = '';
        return;
    }

    const categoryColors = { '蓝海词': 'var(--success)', '流量词': 'var(--warning)', '废词': 'var(--danger)' };
    const categoryIcons = { '蓝海词': '🌊', '流量词': '⚔️', '废词': '📉' };

    el.innerHTML = data.items.map(kw => `
        <tr>
            <td class="kw-keyword">${kw.keyword}</td>
            <td>
                <span class="kw-category-tag" style="background:${categoryColors[kw.category]}20;color:${categoryColors[kw.category]};border:1px solid ${categoryColors[kw.category]}40">
                    ${categoryIcons[kw.category]} ${kw.category}
                </span>
            </td>
            <td>${kw.popularity ? kw.popularity.toLocaleString() : '--'}</td>
            <td>${kw.impressions ? kw.impressions.toLocaleString() : '--'}</td>
            <td>${kw.clicks ? kw.clicks.toLocaleString() : '--'}</td>
            <td>${kw.ctr ? (kw.ctr * 100).toFixed(2) + '%' : '--'}</td>
            <td>${kw.cvr ? (kw.cvr * 100).toFixed(2) + '%' : '--'}</td>
            <td>${kw.cost ? '¥' + kw.cost.toFixed(0) : '--'}</td>
            <td>${kw.gmv ? '¥' + kw.gmv.toFixed(0) : '--'}</td>
            <td style="font-weight:700;color:${kw.roi >= 3 ? 'var(--success)' : kw.roi >= 1 ? 'var(--warning)' : 'var(--danger)'}">${kw.roi ? kw.roi.toFixed(2) : '--'}</td>
            <td style="font-weight:700;color:${kw.efficacy >= 1.2 ? 'var(--success)' : kw.efficacy >= 0.8 ? 'var(--accent)' : 'var(--danger)'}">${kw.efficacy ? kw.efficacy.toFixed(2) : '--'}</td>
        </tr>
    `).join('');

    // Pagination
    if (pagination) {
        const totalPages = Math.ceil(data.total / data.per_page);
        if (totalPages <= 1) {
            pagination.innerHTML = `<span style="color:var(--text-secondary);font-size:13px;">共 ${data.total} 条</span>`;
        } else {
            let pages = '';
            for (let i = 1; i <= Math.min(totalPages, 10); i++) {
                const active = i === data.page ? 'active' : '';
                pages += `<button class="kw-page-btn ${active}" onclick="KW_STATE.page=${i};loadKeywords()">${i}</button>`;
            }
            pagination.innerHTML = `<span style="color:var(--text-secondary);font-size:13px;">共 ${data.total} 条</span>${pages}`;
        }
    }
}

// Upload handler
function handleKeywordUpload() {
    const input = document.getElementById('kwFileInput');
    if (!input || !input.files[0]) return;

    const formData = new FormData();
    formData.append('file', input.files[0]);

    const btn = document.getElementById('kwUploadBtn');
    if (btn) { btn.disabled = true; btn.textContent = '导入中...'; }

    fetch('/api/upload/keywords', { method: 'POST', body: formData })
        .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
        .then(data => {
            if (data.success) {
                showToast(`✅ 导入成功: ${data.rows_imported} 条搜索词 (${data.date})`, 'success');
                KW_STATE.date = data.date;
                loadKeywords();
            } else {
                showToast(`❌ 导入失败: ${data.error}`, 'error');
            }
        })
        .catch(e => showToast(`❌ 导入失败: ${e.message}`, 'error'))
        .finally(() => {
            if (btn) { btn.disabled = false; btn.textContent = '📤 上传搜索词报表'; }
            if (input) input.value = '';
        });
}
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
/* ================================================================
   任务看板 + 用户KPI
================================================================ */
let TASK_STATE = { status: '', priority: '' };

async function loadTasks() {
    const container = document.getElementById('taskBoardContainer');
    if (!container) return;
    try {
        const params = new URLSearchParams(TASK_STATE);
        const tasks = await apiFetch(`/api/tasks?${params}`);
        renderTaskBoard(tasks);
    } catch (e) {
        container.innerHTML = `<div class="empty-state">加载失败</div>`;
    }
}

function renderTaskBoard(tasks) {
    const el = document.getElementById('taskList');
    if (!el) return;
    if (!tasks || tasks.length === 0) {
        el.innerHTML = '<div style="text-align:center;padding:30px;color:var(--text-secondary);">暂无任务</div>';
        return;
    }
    
    const statusIcons = { todo: '⬜', doing: '🔄', done: '✅', cancelled: '❌' };
    const statusLabels = { todo: '待办', doing: '进行中', done: '已完成', cancelled: '已取消' };
    const priorityColors = { P0: 'var(--danger)', P1: 'var(--warning)', P2: 'var(--accent)', P3: 'var(--text-secondary)' };
    
    el.innerHTML = tasks.map(t => `
        <div class="task-item" style="border-left:3px solid ${priorityColors[t.priority] || 'var(--border)'}">
            <div style="display:flex;justify-content:space-between;align-items:start;gap:8px;">
                <div style="flex:1;">
                    <div style="display:flex;align-items:center;gap:8px;">
                        <span style="font-size:11px;padding:2px 6px;border-radius:4px;background:${priorityColors[t.priority]}20;color:${priorityColors[t.priority]};font-weight:600;">${t.priority}</span>
                        <span style="font-weight:600;color:var(--text-primary);${t.status==='done'?'text-decoration:line-through;opacity:0.6;':''}">${t.title}</span>
                    </div>
                    ${t.description ? `<div style="font-size:12px;color:var(--text-secondary);margin-top:4px;">${t.description}</div>` : ''}
                    <div style="font-size:11px;color:var(--text-secondary);margin-top:6px;display:flex;gap:12px;">
                        ${t.assignee ? `<span>👤 ${t.assignee}</span>` : ''}
                        ${t.due_date ? `<span>📅 ${t.due_date}</span>` : ''}
                    </div>
                </div>
                <div style="display:flex;gap:4px;align-items:center;">
                    <select onchange="updateTaskStatus(${t.id}, this.value)" style="padding:2px 6px;border-radius:4px;border:1px solid var(--border);background:var(--card);color:var(--text-primary);font-size:11px;">
                        <option value="todo" ${t.status==='todo'?'selected':''}>待办</option>
                        <option value="doing" ${t.status==='doing'?'selected':''}>进行中</option>
                        <option value="done" ${t.status==='done'?'selected':''}>已完成</option>
                        <option value="cancelled" ${t.status==='cancelled'?'selected':''}>取消</option>
                    </select>
                    <button onclick="deleteTask(${t.id})" style="padding:2px 6px;border:none;background:transparent;color:var(--danger);cursor:pointer;font-size:14px;" title="删除">×</button>
                </div>
            </div>
        </div>
    `).join('');
}

function updateTaskStatus(id, status) {
    apiFetch(`/api/tasks/${id}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ status }) })
        .then(() => loadTasks())
        .catch(e => showToast('更新失败', 'error'));
}

function deleteTask(id) {
    if (!confirm('确定删除此任务？')) return;
    apiFetch(`/api/tasks/${id}`, { method: 'DELETE' })
        .then(() => loadTasks())
        .catch(e => showToast('删除失败', 'error'));
}

function addTask() {
    const title = document.getElementById('newTaskTitle').value.trim();
    if (!title) { showToast('请输入任务标题', 'error'); return; }
    const priority = document.getElementById('newTaskPriority').value;
    const assignee = document.getElementById('newTaskAssignee').value.trim();
    const due_date = document.getElementById('newTaskDue').value;
    
    apiFetch('/api/tasks', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title, priority, assignee, due_date })
    }).then(() => {
        document.getElementById('newTaskTitle').value = '';
        document.getElementById('newTaskAssignee').value = '';
        document.getElementById('newTaskDue').value = '';
        loadTasks();
        showToast('✅ 任务已创建', 'success');
    }).catch(e => showToast('创建失败', 'error'));
}

// User KPI
async function loadUserKPIs() {
    const el = document.getElementById('kpiTableBody');
    if (!el) return;
    try {
        const kpis = await apiFetch('/api/user_kpis');
        if (!kpis || kpis.length === 0) {
            el.innerHTML = '<tr><td colspan="6" style="text-align:center;padding:30px;color:var(--text-secondary);">暂无KPI数据</td></tr>';
            return;
        }
        const ratingColors = { A: 'var(--success)', B: 'var(--accent)', C: 'var(--warning)', D: 'var(--danger)' };
        el.innerHTML = kpis.map(k => `
            <tr>
                <td style="font-weight:600;">${k.user_name}</td>
                <td>${k.period || '--'}</td>
                <td>¥${(k.target_gmv/10000).toFixed(1)}万</td>
                <td>¥${(k.actual_gmv/10000).toFixed(1)}万</td>
                <td style="font-weight:700;color:${k.achievement_rate>=100?'var(--success)':'var(--danger)'}">${k.achievement_rate.toFixed(1)}%</td>
                <td><span style="padding:2px 8px;border-radius:4px;background:${ratingColors[k.rating]||'var(--text-secondary)'}20;color:${ratingColors[k.rating]||'var(--text-secondary)'};font-weight:600;">${k.rating}</span></td>
            </tr>
        `).join('');
    } catch (e) {
        el.innerHTML = '<tr><td colspan="6" style="text-align:center;color:var(--danger);">加载失败</td></tr>';
    }
}
