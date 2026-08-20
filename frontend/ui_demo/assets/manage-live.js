(function () {
  const $ = (selector, root = document) => root.querySelector(selector);
  const state = { tasks: [], kpis: [], schedules: [], logs: [], capabilities: {}, token: 0, taskId: null, kpiId: null, scheduleId: null };
  const dialogReturnFocus = new WeakMap();
  const doneStates = new Set(['done', 'completed']);
  const statusLabels = { todo: '待处理', in_progress: '处理中', done: '已完成', completed: '已完成', active: '正常', running: '执行中', error: '异常' };
  const focusable = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

  const money = (value) => `¥${Number(value || 0).toLocaleString('zh-CN', { maximumFractionDigits: 2 })}`;
  const percent = (value) => `${(Number(value || 0) * 100).toFixed(1)}%`;
  const asArray = (payload, key) => Array.isArray(payload) ? payload : (Array.isArray(payload?.[key]) ? payload[key] : []);
  const json = (body, method = 'POST') => ({ method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  const toast = (message) => {
    if (window.DemoShell?.showToast) window.DemoShell.showToast(message);
    else window.alert(message);
  };
  const setStatus = (message) => { const target = $('[data-manage-status]'); if (target) target.textContent = message; window.DemoShell?.setStatus?.(message); };
  const badgeClass = (value) => value === 'error' ? 'badge--danger' : (doneStates.has(value) || value === 'active' ? 'badge--success' : (value === 'running' || value === 'in_progress' ? 'badge--warning' : 'badge--muted'));
  const period = () => String((window.TmallDateRange?.getState?.().endDate || new Date().toISOString()).slice(0, 7));
  const canManage = (name) => !Object.keys(state.capabilities).length || DemoApi.can({ capabilities: state.capabilities }, name);

  function tableMessage(selector, colspan, message) {
    const body = $(selector); body.replaceChildren();
    const row = document.createElement('tr'); const cell = row.insertCell(); cell.colSpan = colspan; cell.textContent = message; row.appendChild(cell); body.appendChild(row);
  }
  function appendCell(row, value, className) { const cell = row.insertCell(); if (className) cell.className = className; if (value instanceof Node) cell.appendChild(value); else cell.textContent = value; return cell; }
  function button(label, icon, handler, title) {
    const item = document.createElement('button'); item.type = 'button'; item.className = 'button button--ghost'; item.title = title || label; item.setAttribute('aria-label', title || label); item.textContent = label;
    if (window.lucide && icon) { item.textContent = ''; const mark = document.createElement('i'); mark.setAttribute('data-lucide', icon); item.appendChild(mark); }
    item.addEventListener('click', handler); return item;
  }
  function actionGroup(actions) { const wrap = document.createElement('div'); wrap.className = 'filter-group'; actions.forEach((action) => wrap.appendChild(action)); return wrap; }
  function badge(value, label) { const item = document.createElement('span'); const ratingClass = { A: 'badge--success', B: 'badge--info', C: 'badge--warning', D: 'badge--danger' }[value]; item.className = `badge ${ratingClass || badgeClass(value)}`; item.textContent = label || DemoLabels.label('status', value, statusLabels[value] || '--'); return item; }

  function renderMetrics() {
    const pending = state.tasks.filter((row) => !doneStates.has(row.status)).length;
    const done = state.tasks.filter((row) => doneStates.has(row.status)).length;
    const values = { tasks: state.tasks.length, pending, done, scheduled: state.schedules.filter((row) => Number(row.enabled) === 1).length };
    Object.entries(values).forEach(([key, value]) => { const target = $(`[data-manage-kpi="${key}"]`); if (target) target.textContent = Number(value).toLocaleString('zh-CN'); });
  }
  function renderTasks() {
    const body = $('[data-manage-tasks]'); body.replaceChildren();
    if (!state.tasks.length) return tableMessage('[data-manage-tasks]', 6, '暂无任务');
    state.tasks.forEach((item) => {
      const row = document.createElement('tr');
      const name = document.createElement('div'); name.className = 'table-name'; const title = document.createElement('strong'); title.textContent = item.title || '未命名任务'; const detail = document.createElement('span'); detail.textContent = item.description || '无任务说明'; name.append(title, detail);
      appendCell(row, name); appendCell(row, badge(item.status || 'todo')); appendCell(row, DemoLabels.label('priority', item.priority)); appendCell(row, item.assignee || '未分配'); appendCell(row, item.due_date || '--');
      appendCell(row, actionGroup([
        button('', 'pencil', () => openTask(item), '编辑任务'),
        button('', doneStates.has(item.status) ? 'rotate-ccw' : 'check', () => updateTaskStatus(item), doneStates.has(item.status) ? '标记待处理' : '标记完成'),
        button('', 'trash-2', () => removeTask(item), '删除任务'),
      ])); body.appendChild(row);
    });
  }
  function renderKpis() {
    const body = $('[data-manage-kpis]'); body.replaceChildren();
    if (!state.kpis.length) return tableMessage('[data-manage-kpis]', 6, `当前周期 ${period()} 暂无 KPI`);
    state.kpis.forEach((item) => {
      const row = document.createElement('tr'); appendCell(row, item.user_name || '--'); appendCell(row, money(item.target_gmv)); appendCell(row, money(item.actual_gmv)); appendCell(row, percent(item.achievement_rate)); appendCell(row, badge(item.rating || 'C', DemoLabels.label('rating', item.rating || 'C')));
      appendCell(row, actionGroup([button('', 'pencil', () => openKpi(item), '编辑 KPI'), button('', 'trash-2', () => removeKpi(item), '删除 KPI')])); body.appendChild(row);
    });
  }
  function renderSchedules() {
    const body = $('[data-manage-scheduled]'); body.replaceChildren();
    if (!state.schedules.length) return tableMessage('[data-manage-scheduled]', 5, '暂无文件夹扫描任务');
    state.schedules.forEach((item) => {
      const row = document.createElement('tr'); const title = document.createElement('div'); title.className = 'table-name'; const name = document.createElement('strong'); name.textContent = item.task_name || '未命名任务'; const pattern = document.createElement('span'); pattern.textContent = item.folder_path || item.file_pattern || '--'; title.append(name, pattern);
      const scheduleState = Number(item.enabled) === 1 ? (item.status || 'active') : 'disabled';
      appendCell(row, title); appendCell(row, item.cron_label || item.cron_expr || '--'); appendCell(row, scheduleState === 'disabled' ? '已停用' : badge(scheduleState)); appendCell(row, item.next_run || '--');
      appendCell(row, actionGroup([
        button('', 'pencil', () => openSchedule(item), '编辑扫描任务'),
        button('', Number(item.enabled) === 1 ? 'pause' : 'play', () => toggleSchedule(item), Number(item.enabled) === 1 ? '停用扫描' : '启用扫描'),
        button('', 'play-circle', () => runSchedule(item), '立即扫描'),
      ])); body.appendChild(row);
    });
  }
  function renderLogs() {
    const body = $('[data-manage-logs]'); body.replaceChildren();
    if (!state.logs.length) return tableMessage('[data-manage-logs]', 4, '暂无操作日志');
    state.logs.forEach((item) => { const row = document.createElement('tr'); appendCell(row, item.created_at || '--'); appendCell(row, item.action || '--'); appendCell(row, item.detail || '--'); appendCell(row, item.operator || '--'); body.appendChild(row); });
  }
  function renderAll() { renderMetrics(); renderTasks(); renderKpis(); renderSchedules(); renderLogs(); if (window.lucide) window.lucide.createIcons(); }

  async function load() {
    const token = ++state.token; const selectedPeriod = period();
    setStatus('正在加载管理工作台数据');
    try {
      const [tasks, kpis, schedules, logs] = await Promise.all([
        DemoApi.domainRequest('/api/manage/tasks'), DemoApi.domainRequest(`/api/manage/kpis?period=${encodeURIComponent(selectedPeriod)}`), DemoApi.domainRequest('/api/import-scans'), DemoApi.request('/api/logs?limit=20'),
      ]);
      if (token !== state.token) return;
      state.tasks = tasks.data || asArray(tasks); state.kpis = kpis.data || asArray(kpis); state.schedules = schedules.data || asArray(schedules); state.logs = asArray(logs); renderAll();
      $('[data-manage-kpi-period]').textContent = `当前周期：${selectedPeriod}`;
      setStatus('管理工作台数据已更新');
    } catch (error) {
      if (token !== state.token) return;
      tableMessage('[data-manage-tasks]', 6, '任务加载失败'); tableMessage('[data-manage-kpis]', 6, 'KPI 加载失败'); tableMessage('[data-manage-scheduled]', 5, '扫描任务加载失败'); tableMessage('[data-manage-logs]', 4, '操作日志加载失败');
      toast(error.message || '管理工作台数据加载失败'); setStatus('管理工作台数据加载失败');
    }
  }
  async function log(action, detail) { await DemoApi.request('/api/logs', json({ action, detail })); }
  async function mutate(action, detail, request) {
    if (!canManage('can_edit')) { setStatus('当前管理操作不可用'); return; }
    try {
      await request();
      let logFailed = false;
      try { await log(action, detail); } catch (_) { logFailed = true; }
      toast(logFailed ? `${action}成功，操作日志写入失败` : `${action}成功`);
      await load();
    } catch (error) { toast(error.message || `${action}失败`); setStatus(`${action}失败`); }
  }

  function formValues(form) { return Object.fromEntries(new FormData(form).entries()); }
  function resetDialog(dialog) { if (dialog.open) dialog.close(); dialog.hidden = true; }
  function showDialog(dialog) { dialogReturnFocus.set(dialog, document.activeElement); dialog.hidden = false; dialog.showModal(); window.setTimeout(() => dialog.querySelector(focusable)?.focus(), 0); }
  function restoreDialogFocus(dialog, kind) {
    const target = dialogReturnFocus.get(dialog);
    dialogReturnFocus.delete(dialog);
    const fallback = $(`[data-manage-create-${kind}]`);
    window.setTimeout(() => (target?.isConnected ? target : fallback)?.focus?.(), 0);
  }
  function bindDialog(dialog, kind) { dialog.addEventListener('close', () => { dialog.hidden = true; restoreDialogFocus(dialog, kind); }); dialog.addEventListener('cancel', () => window.setTimeout(() => { dialog.hidden = true; }, 0)); document.querySelectorAll(`[data-manage-dialog-close="${kind}"]`).forEach((item) => item.addEventListener('click', () => resetDialog(dialog))); }

  function openTask(item) {
    const dialog = $('[data-manage-task-dialog]'); const form = $('[data-manage-task-form]'); state.taskId = item?.id ?? null; form.reset();
    $('#manage-task-title').textContent = state.taskId ? '编辑任务' : '新建任务';
    if (item) ['title', 'description', 'status', 'priority', 'assignee', 'due_date'].forEach((key) => { if (form.elements[key]) form.elements[key].value = item[key] || ''; });
    showDialog(dialog);
  }
  function openKpi(item) {
    const dialog = $('[data-manage-kpi-dialog]'); const form = $('[data-manage-kpi-form]');
    state.kpiId = item?.id ?? null; form.reset(); form.elements.period.value = item?.period || period();
    $('#manage-kpi-title').textContent = state.kpiId ? '编辑 KPI' : '新增 KPI';
    if (item) ['user_name', 'period', 'target_gmv', 'actual_gmv', 'rating'].forEach((key) => { if (form.elements[key]) form.elements[key].value = item[key] ?? ''; });
    if (item && form.elements.achievement_rate) form.elements.achievement_rate.value = Number(item.achievement_rate || 0) * 100;
    showDialog(dialog);
  }
  function openSchedule(item) {
    const dialog = $('[data-manage-schedule-dialog]'); const form = $('[data-manage-schedule-form]'); state.scheduleId = item?.id ?? null; form.reset(); form.elements.file_pattern.value = '*.xlsx;*.xls;*.csv;*.zip'; form.elements.cron_expr.value = '0 8 * * *';
    $('#manage-schedule-title').textContent = state.scheduleId ? '编辑文件夹扫描' : '新增文件夹扫描';
    if (item) ['task_name', 'folder_path', 'cron_expr', 'file_pattern', 'source_type'].forEach((key) => { if (form.elements[key]) form.elements[key].value = item[key] || ''; });
    form.elements.enabled.checked = item ? Boolean(item.enabled) : true;
    showDialog(dialog);
  }
  function updateTaskStatus(item) { const next = doneStates.has(item.status) ? 'todo' : 'done'; mutate('更新任务状态', `${item.title || item.id}：${statusLabels[next]}`, () => DemoApi.domainRequest(`/api/manage/tasks/${Number(item.id)}`, json({ status: next, operator: '店长', reason: '更新任务状态' }, 'PUT'))); }
  function removeTask(item) { if (window.confirm(`删除任务“${item.title || item.id}”？`)) mutate('删除任务', item.title || String(item.id), () => DemoApi.domainRequest(`/api/manage/tasks/${Number(item.id)}`, { method: 'DELETE', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ operator: '店长', reason: '删除管理任务' }) })); }
  function removeKpi(item) { if (window.confirm(`删除 ${item.user_name || '该成员'} 的 KPI？`)) mutate('删除 KPI', item.user_name || String(item.id), () => DemoApi.domainRequest(`/api/manage/kpis/${Number(item.id)}`, { method: 'DELETE', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ operator: '店长', reason: '删除用户 KPI' }) })); }
  function toggleSchedule(item) { const enabled = Number(item.enabled) !== 1; mutate(enabled ? '启用扫描' : '停用扫描', item.task_name || String(item.id), () => DemoApi.domainRequest(`/api/import-scans/${Number(item.id)}`, json({ enabled }, 'PUT'))); }
  function runSchedule(item) { mutate('执行扫描', item.task_name || String(item.id), () => DemoApi.domainRequest(`/api/import-scans/${Number(item.id)}/run`, { method: 'POST' })); }

  function bindForms() {
    $('[data-manage-task-form]').addEventListener('submit', (event) => { event.preventDefault(); const values = formValues(event.currentTarget); const id = state.taskId; values.operator = '店长'; values.reason = id ? '编辑管理任务' : '创建管理任务'; mutate(id ? '更新任务' : '创建任务', values.title, async () => { await DemoApi.domainRequest(id ? `/api/manage/tasks/${Number(id)}` : '/api/manage/tasks', json(values, id ? 'PUT' : 'POST')); resetDialog($('[data-manage-task-dialog]')); }); });
    $('[data-manage-kpi-form]').addEventListener('submit', (event) => { event.preventDefault(); const values = formValues(event.currentTarget); ['target_gmv', 'actual_gmv'].forEach((key) => { values[key] = Number(values[key] || 0); }); values.achievement_rate = Number(values.achievement_rate || 0) / 100; const id = state.kpiId; values.operator = '店长'; values.reason = id ? '编辑用户 KPI' : '创建用户 KPI'; mutate(id ? '更新 KPI' : '创建 KPI', values.user_name, async () => { await DemoApi.domainRequest(id ? `/api/manage/kpis/${Number(id)}` : '/api/manage/kpis', json(values, id ? 'PUT' : 'POST')); resetDialog($('[data-manage-kpi-dialog]')); }); });
    $('[data-manage-schedule-form]').addEventListener('submit', (event) => { event.preventDefault(); const values = formValues(event.currentTarget); const id = state.scheduleId; values.enabled = event.currentTarget.elements.enabled.checked; mutate(id ? '更新扫描任务' : '创建扫描任务', values.task_name, async () => { await DemoApi.domainRequest(id ? `/api/import-scans/${Number(id)}` : '/api/import-scans', json(values, id ? 'PUT' : 'POST')); resetDialog($('[data-manage-schedule-dialog]')); }); });
  }
  function bind() {
    $('[data-manage-refresh]').addEventListener('click', load); $('[data-manage-create-task]').addEventListener('click', () => openTask()); $('[data-manage-create-kpi]').addEventListener('click', () => openKpi()); $('[data-manage-create-schedule]').addEventListener('click', () => openSchedule());
    const folderButton = $('[data-manage-select-scan-folder]'); const folderInput = $('[data-manage-schedule-form] [name="folder_path"]');
    if (window.tmallDesktop?.selectScanFolder) { folderButton.hidden = false; folderInput.readOnly = true; folderButton.addEventListener('click', async () => { const selected = await window.tmallDesktop.selectScanFolder(); if (selected) folderInput.value = selected; }); }
    bindDialog($('[data-manage-task-dialog]'), 'task'); bindDialog($('[data-manage-kpi-dialog]'), 'kpi'); bindDialog($('[data-manage-schedule-dialog]'), 'schedule'); bindForms();
    window.addEventListener('tmall:refresh', load); window.addEventListener('tmall:date-range-change', load);
  }
  bind(); load();
})();
