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
