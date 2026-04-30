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
