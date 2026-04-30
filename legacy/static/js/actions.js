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
