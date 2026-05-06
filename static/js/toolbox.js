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
