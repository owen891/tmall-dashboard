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
            ? `<div class="product-cell"><img src="${img}" alt="${title}" loading="lazy"><span class="title">${title}</span></div>`
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

        return `<tr class="${rowCls}" role="button" tabindex="0" aria-label="查看${title}健康度详情" onclick="showHealthDetail('${item.product_id}')" onkeydown="if(event.key==='Enter'||event.key===' '){event.preventDefault();showHealthDetail('${item.product_id}')}" style="cursor:pointer">
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
            ${product.image_url ? `<img src="${escapeHtml(product.image_url)}" alt="${escapeHtml(product.title || '')}" loading="lazy" style="width:48px;height:48px;border-radius:8px;object-fit:cover;background:#1E293B;">` : ''}
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
