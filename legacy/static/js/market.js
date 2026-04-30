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
