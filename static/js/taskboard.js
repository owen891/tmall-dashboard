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
                <td style="font-weight:700;color:${k.achievement_rate>=1?'var(--success)':'var(--danger)'}">${(k.achievement_rate * 100).toFixed(1)}%</td>
                <td><span style="padding:2px 8px;border-radius:4px;background:${ratingColors[k.rating]||'var(--text-secondary)'}20;color:${ratingColors[k.rating]||'var(--text-secondary)'};font-weight:600;">${k.rating}</span></td>
            </tr>
        `).join('');
    } catch (e) {
        el.innerHTML = '<tr><td colspan="6" style="text-align:center;color:var(--danger);">加载失败</td></tr>';
    }
}
