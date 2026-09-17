(function () {
  const root = document.querySelector('[data-overview-operations-center]');
  if (!root || !window.DemoApi) return;

  const $ = (selector) => root.querySelector(selector);
  const stateLabels = {
    draft: '草稿', pending_execution: '待执行', executing: '执行中', observing: '观察中',
    blocked: '阻塞', calculation_failed: '计算失败', pending_review: '待复盘', completed: '已完成', cancelled: '已取消',
  };
  const toneFor = (value) => ['blocked', 'calculation_failed'].includes(value) ? 'danger'
    : ['pending_review', 'pending_execution'].includes(value) ? 'warning'
      : ['completed', 'observing'].includes(value) ? 'success' : 'info';
  const actionType = (action) => window.DemoLabels?.label('action', action.action_type, action.action_type || '运营动作') || action.action_type || '运营动作';
  const formatDateTime = (value) => window.TmallUI?.formatDateTime ? window.TmallUI.formatDateTime(value) : String(value || '--').replace('T', ' ').slice(0, 16);
  const formatDate = (value) => String(value || '').slice(0, 10);
  const icon = (name) => window.TmallUI?.icon ? window.TmallUI.icon(name) : Object.assign(document.createElement('i'), { className: 'lucide' });
  const today = () => { const date = new Date(); return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`; };
  const parseDate = (value) => { const [year, month, day] = String(value).split('-').map(Number); return new Date(year, month - 1, day); };
  const monthRange = () => ({
    start: `${state.viewYear}-${String(state.viewMonth + 1).padStart(2, '0')}-01`,
    end: `${state.viewYear}-${String(state.viewMonth + 1).padStart(2, '0')}-${new Date(state.viewYear, state.viewMonth + 1, 0).getDate()}`,
  });
  const renderState = (container, message, retry) => {
    container.replaceChildren();
    if (window.DemoApi.renderDataState) window.DemoApi.renderDataState(container, message, retry ? { message: '', retry } : {});
    else container.textContent = message === 'loading' ? '加载中…' : '暂无记录';
  };
  const state = {
    filter: 'all',
    actions: [],
    todos: [],
    logs: [],
    anomalies: [],
    calendarActions: [],
    viewYear: new Date().getFullYear(),
    viewMonth: new Date().getMonth(),
    selectedDate: '',
    token: 0,
    sourceErrors: [],
  };

  function actionKey(action) { return action?.id == null ? '' : `action:${action.id}`; }
  function mergeActions(...groups) {
    const merged = new Map();
    groups.flat().forEach((action) => {
      const key = actionKey(action);
      if (!key) return;
      merged.set(key, { ...(merged.get(key) || {}), ...action });
    });
    return [...merged.values()];
  }
  function isPending(action) { return ['pending_review', 'blocked', 'pending_execution', 'executing'].includes(action.status); }
  function actionTitle(action) { return `${action.product_title || action.product_id || '商品'} · ${actionType(action)}`; }
  const deletableStatuses = new Set(['draft', 'pending_execution', 'blocked']);
  function actionDetail(action) { return action.action_detail || action.purpose_note || '已创建运营动作，等待后续处理。'; }
  function actionPurpose(action) { return action.purpose_note || '未填写动作目的'; }
  function actionMeta(action) {
    const parts = [`计划 ${formatDate(action.planned_at) || '--'}`, stateLabels[action.status] || action.status || '--'];
    if (action.assigned_to) parts.push(`负责人 ${action.assigned_to}`);
    if (action.observer_window_days) parts.push(`观察 ${action.observer_window_days} 天`);
    if (action.overdue) parts.push('已逾期');
    return parts.join(' · ');
  }
  async function deleteAction(action, button) {
    if (!deletableStatuses.has(action.status) || button.disabled) return;
    if (!window.confirm(`确认删除动作“${actionTitle(action)}”？删除后将从提醒列表和计划日历移除。`)) return;
    button.disabled = true;
    try {
      await DemoApi.domainRequest(`/api/actions/${encodeURIComponent(action.id)}`, {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ capability_key: 'overview.delete_action', version: action.version, operator: '店长', reason: '从概览删除运营动作' }),
      });
      window.DemoShell?.showToast?.('运营动作已删除');
      await load();
    } catch (error) {
      window.DemoShell?.showToast?.(error.message || '删除运营动作失败');
      button.disabled = false;
    }
  }
  function buildActionItem(action, compact = false) {
    const item = document.createElement('article');
    const tone = toneFor(action.status);
    item.className = `operations-center__item operations-center__item--${tone}${action.overdue ? ' is-overdue' : ''}`;
    item.setAttribute('role', 'listitem');
    const marker = document.createElement('span'); marker.className = 'operations-center__item-icon'; marker.appendChild(icon(action.status === 'completed' ? 'check-circle-2' : action.status === 'blocked' ? 'alert-triangle' : 'circle-dot'));
    const copy = document.createElement('div'); copy.className = 'operations-center__item-copy';
    const head = document.createElement('div'); head.className = 'operations-center__item-head';
    const title = document.createElement('strong'); title.textContent = actionTitle(action); head.appendChild(title);
    const source = document.createElement('span'); source.className = 'badge badge--info'; source.textContent = '运营动作'; head.appendChild(source);
    const meta = document.createElement('span'); meta.className = 'operations-center__item-meta'; meta.textContent = actionMeta(action);
    const purpose = document.createElement('p'); purpose.className = 'operations-center__item-purpose'; purpose.textContent = `目的：${actionPurpose(action)}`;
    const detail = document.createElement('p'); detail.className = 'operations-center__item-detail'; detail.textContent = `执行：${actionDetail(action)}`;
    copy.append(head, meta, purpose, detail);
    const status = document.createElement('span'); status.className = `badge badge--${tone}`; status.textContent = stateLabels[action.status] || action.status || '--';
    if (compact) head.appendChild(status); else item.append(marker, copy, status);
    if (!compact) {
      const actions = document.createElement('div'); actions.className = 'operations-center__item-actions';
      const link = document.createElement('a'); link.className = 'button button--ghost operations-center__item-link'; link.href = '/reviews'; link.textContent = '处理'; actions.appendChild(link);
      if (deletableStatuses.has(action.status)) {
        const remove = document.createElement('button'); remove.type = 'button'; remove.className = 'button button--ghost button--danger'; remove.dataset.actionDelete = action.id; remove.setAttribute('data-action-delete', action.id); remove.setAttribute('aria-label', `删除${actionTitle(action)}`); remove.innerHTML = '<i data-lucide="trash-2" aria-hidden="true"></i><span>删除</span>';
        remove.addEventListener('click', () => deleteAction(action, remove));
        actions.appendChild(remove);
      }
      copy.appendChild(actions);
    }
    if (compact) item.append(marker, copy);
    return item;
  }
  function buildAnomalyItem(anomaly) {
    const item = document.createElement('article');
    const severe = anomaly.severity === 'high';
    item.className = `operations-center__item operations-center__item--${severe ? 'danger' : 'warning'}`;
    item.setAttribute('role', 'listitem');
    const marker = document.createElement('span'); marker.className = 'operations-center__item-icon'; marker.appendChild(icon('triangle-alert'));
    const copy = document.createElement('div'); copy.className = 'operations-center__item-copy';
    const head = document.createElement('div'); head.className = 'operations-center__item-head';
    const title = document.createElement('strong'); title.textContent = anomaly.label || anomaly.metric || '指标异常';
    const source = document.createElement('span'); source.className = 'badge badge--warning'; source.textContent = '异常提醒'; head.append(title, source);
    const change = Number(anomaly.change || 0);
    const meta = document.createElement('span'); meta.className = 'operations-center__item-meta'; meta.textContent = `较上期 ${change > 0 ? '+' : ''}${change.toFixed(1)}% · 需要关注`;
    const detail = document.createElement('p'); detail.textContent = `当前值 ${Number(anomaly.current || 0).toLocaleString('zh-CN')}，建议进入经营复盘确认原因。`;
    copy.append(head, meta, detail); item.append(marker, copy);
    const status = document.createElement('span'); status.className = `badge badge--${severe ? 'danger' : 'warning'}`; status.textContent = severe ? '高风险' : '需关注'; item.appendChild(status);
    return item;
  }
  function buildLogItem(log) {
    const item = document.createElement('article'); item.className = 'operations-center__item operations-center__item--system'; item.setAttribute('role', 'listitem');
    const marker = document.createElement('span'); marker.className = 'operations-center__item-icon'; marker.appendChild(icon('history'));
    const copy = document.createElement('div'); copy.className = 'operations-center__item-copy';
    const head = document.createElement('div'); head.className = 'operations-center__item-head';
    const title = document.createElement('strong'); title.textContent = log.action || '系统操作';
    const source = document.createElement('span'); source.className = 'badge badge--info'; source.textContent = '系统通知'; head.append(title, source);
    const detail = document.createElement('p'); detail.textContent = log.detail || '--';
    const meta = document.createElement('span'); meta.className = 'operations-center__item-meta'; meta.textContent = `${log.operator || '系统'} · ${formatDateTime(log.created_at)}`;
    copy.append(head, detail, meta); item.append(marker, copy); return item;
  }
  function visibleItems() {
    const actions = state.actions.map((action) => ({ type: 'action', date: action.updated_at || action.planned_at || action.created_at, value: action }));
    const anomalies = state.anomalies.map((anomaly) => ({ type: 'anomaly', date: anomaly.detected_at || anomaly.period || '', value: anomaly }));
    const logs = state.logs.map((log) => ({ type: 'system', date: log.created_at, value: log }));
    return [...actions, ...anomalies, ...logs].filter((entry) => state.filter === 'todo'
      ? entry.type === 'action' && isPending(entry.value)
      : state.filter === 'anomaly'
        ? entry.type === 'anomaly'
        : state.filter === 'system'
          ? entry.type === 'system'
          : true)
      .sort((first, second) => String(second.date || '').localeCompare(String(first.date || '')));
  }
  function renderFeed() {
    const feed = $('[data-operations-feed]');
    const items = visibleItems();
    feed.replaceChildren();
    if (!items.length) {
      renderState(feed, 'no-data');
      $('[data-operations-feed-count]').textContent = '0';
      $('[data-operations-feed-status]').textContent = state.sourceErrors.length ? '提醒来源暂不可用' : '暂无提醒';
      return;
    }
    items.slice(0, 12).forEach((entry) => {
      feed.appendChild(entry.type === 'action' ? buildActionItem(entry.value) : entry.type === 'anomaly' ? buildAnomalyItem(entry.value) : buildLogItem(entry.value));
    });
    $('[data-operations-feed-count]').textContent = String(Math.min(items.length, 12));
    $('[data-operations-feed-status]').textContent = state.sourceErrors.length ? `部分来源加载失败 · 已显示 ${items.length} 条可用提醒` : `${items.length} 条提醒`;
    window.lucide?.createIcons?.();
    window.DemoApi.loadPageCapabilities?.().catch(() => {});
  }
  function renderCalendarDetails(date) {
    const rows = state.calendarActions.filter((action) => formatDate(action.planned_at) === date);
    $('[data-operations-calendar-date]').textContent = date || '选择日期';
    $('[data-operations-calendar-count]').textContent = `${rows.length} 项`;
    const target = $('[data-operations-calendar-details]'); target.replaceChildren();
    if (!rows.length) { const empty = document.createElement('div'); empty.className = 'empty-state'; empty.appendChild(Object.assign(document.createElement('span'), { textContent: '当天暂无运营动作' })); target.appendChild(empty); return; }
    rows.forEach((action) => target.appendChild(buildActionItem(action, true)));
    window.lucide?.createIcons?.();
  }
  function renderCalendar() {
    const month = new Date(state.viewYear, state.viewMonth, 1); const days = new Date(state.viewYear, state.viewMonth + 1, 0).getDate(); const first = month.getDay();
    const map = state.calendarActions.reduce((result, action) => { const key = formatDate(action.planned_at); if (key) (result[key] ||= []).push(action); return result; }, {});
    $('[data-operations-calendar-month]').textContent = `${state.viewYear}年${state.viewMonth + 1}月`;
    const grid = $('[data-operations-calendar-grid]'); const cells = [];
    for (let index = 0; index < first; index += 1) { const button = document.createElement('button'); button.type = 'button'; button.className = 'operations-center__calendar-day is-muted'; button.disabled = true; cells.push(button); }
    for (let day = 1; day <= days; day += 1) {
      const date = `${state.viewYear}-${String(state.viewMonth + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
      const button = document.createElement('button'); button.type = 'button'; button.className = 'operations-center__calendar-day'; button.dataset.operationsCalendarDate = date; if (date === today()) button.classList.add('is-today'); if (date === state.selectedDate) button.classList.add('is-selected');
      button.appendChild(Object.assign(document.createElement('span'), { className: 'operations-center__calendar-day-number', textContent: String(day) }));
      const count = (map[date] || []).length; if (count) { const marker = document.createElement('span'); marker.className = 'operations-center__calendar-day-count'; marker.textContent = String(count); marker.setAttribute('aria-label', `${count} 项运营动作`); button.appendChild(marker); } cells.push(button);
    }
    while (cells.length % 7) { const button = document.createElement('button'); button.type = 'button'; button.className = 'operations-center__calendar-day is-muted'; button.disabled = true; cells.push(button); }
    grid.replaceChildren(...cells); renderCalendarDetails(state.selectedDate || `${state.viewYear}-${String(state.viewMonth + 1).padStart(2, '0')}-01`); window.lucide?.createIcons?.();
  }
  function calendarMonthLabel() { return `${state.viewYear}年${state.viewMonth + 1}月`; }
  function calendarErrorMessage(error) {
    if (error?.status === 404) return '当前服务未部署计划日历接口';
    if (error?.status === 422 || error?.code === 'UNSUPPORTED_SCOPE' || error?.code === 'VALIDATION_ERROR') return error.message || '计划日历查询参数或店铺范围不允许';
    if (error?.status >= 500) return '计划日历服务异常，请稍后重试';
    return '计划日历服务不可达，请检查服务连接';
  }
  function clearCalendar(message, retry) {
    state.calendarActions = [];
    state.selectedDate = '';
    $('[data-operations-calendar-month]').textContent = calendarMonthLabel();
    $('[data-operations-calendar-status]').textContent = message;
    $('[data-operations-calendar-grid]').replaceChildren();
    $('[data-operations-calendar-date]').textContent = '选择日期';
    $('[data-operations-calendar-count]').textContent = '0 项';
    const target = $('[data-operations-calendar-details]');
    target.replaceChildren();
    const empty = document.createElement('div'); empty.className = 'empty-state';
    empty.appendChild(Object.assign(document.createElement('span'), { textContent: message }));
    if (retry) {
      const button = document.createElement('button');
      button.type = 'button'; button.className = 'button button--ghost'; button.textContent = '重试计划日历';
      button.addEventListener('click', retry); empty.appendChild(button);
    }
    target.appendChild(empty);
  }
  let calendarToken = 0;
  async function loadCalendar() {
    const token = ++calendarToken;
    const range = monthRange();
    clearCalendar('正在加载计划…');
    $('[data-operations-calendar-month]').textContent = calendarMonthLabel();
    $('[data-operations-calendar-status]').textContent = '正在加载计划…';
    try {
      const payload = await DemoApi.domainRequest(`/api/actions/calendar?start=${range.start}&end=${range.end}`);
      if (token !== calendarToken) return;
      state.sourceErrors = [...new Set(state.sourceErrors.filter((source) => source !== 'calendar'))];
      if (payload.availability !== 'available') {
        if (payload.availability !== 'no-data') state.sourceErrors = [...new Set([...state.sourceErrors, 'calendar'])];
        if (payload.availability === 'no-data') {
          state.calendarActions = [];
          state.selectedDate = '';
          $('[data-operations-calendar-status]').textContent = '当前月份暂无计划动作';
          renderCalendar();
        } else {
          clearCalendar('计划日历暂不可用', loadCalendar);
        }
        return;
      }
      state.calendarActions = Array.isArray(payload.data) ? payload.data : [];
      $('[data-operations-calendar-status]').textContent = state.calendarActions.length ? `${state.calendarActions.length} 项计划动作` : '当前月份暂无运营动作';
      renderCalendar();
    } catch (error) {
      if (token !== calendarToken) return;
      state.sourceErrors = [...new Set([...state.sourceErrors, 'calendar'])];
      clearCalendar(calendarErrorMessage(error), loadCalendar);
    }
  }
  async function load() {
    const token = ++state.token; state.sourceErrors = []; state.todos = []; state.actions = []; state.logs = []; state.anomalies = [];
    renderState($('[data-operations-feed]'), 'loading'); $('[data-operations-feed-status]').textContent = '正在加载提醒…';
    const results = await Promise.allSettled([
      DemoApi.domainRequest('/api/actions?limit=200'),
      DemoApi.request('/api/logs?limit=12'),
    ]);
    if (token !== state.token) return;
    const actions = results[0].status === 'fulfilled' ? results[0].value : null;
    const logs = results[1].status === 'fulfilled' ? results[1].value : null;
    if (!actions) state.sourceErrors.push('actions'); if (!logs) state.sourceErrors.push('logs');
    state.actions = mergeActions(Array.isArray(actions?.data) ? actions.data : [], state.todos);
    state.logs = Array.isArray(logs) ? logs : [];
    $('[data-operations-pending-count]').textContent = `待处理 ${state.actions.filter(isPending).length + state.anomalies.length}`;
    renderFeed(); await loadCalendar();
  }
  function applyOverviewTodos(todos) {
    state.todos = Array.isArray(todos) ? todos : [];
    state.actions = mergeActions(state.actions, state.todos);
    $('[data-operations-pending-count]').textContent = `待处理 ${state.actions.filter(isPending).length + state.anomalies.length}`;
    renderFeed();
  }
  function applyOverviewAnomalies(anomalies) {
    state.anomalies = Array.isArray(anomalies) ? anomalies : [];
    $('[data-operations-pending-count]').textContent = `待处理 ${state.actions.filter(isPending).length + state.anomalies.length}`;
    renderFeed();
  }
  function setFilter(filter) { state.filter = filter; root.querySelectorAll('[data-operations-filter]').forEach((button) => button.setAttribute('aria-selected', String(button.dataset.operationsFilter === filter))); renderFeed(); }
  root.querySelectorAll('[data-operations-filter]').forEach((button) => button.addEventListener('click', () => setFilter(button.dataset.operationsFilter)));
  window.addEventListener('tmall:overview-actions-ready', (event) => applyOverviewTodos(event.detail?.todos));
  window.addEventListener('tmall:overview-anomalies-ready', (event) => applyOverviewAnomalies(event.detail?.anomalies));
  $('[data-operations-refresh]')?.addEventListener('click', () => load().catch(() => renderState($('[data-operations-feed]'), 'calculation-failed', load)));
  $('[data-operations-calendar-prev]')?.addEventListener('click', () => { state.viewMonth -= 1; if (state.viewMonth < 0) { state.viewMonth = 11; state.viewYear -= 1; } state.selectedDate = ''; loadCalendar(); });
  $('[data-operations-calendar-next]')?.addEventListener('click', () => { state.viewMonth += 1; if (state.viewMonth > 11) { state.viewMonth = 0; state.viewYear += 1; } state.selectedDate = ''; loadCalendar(); });
  $('[data-operations-calendar-today]')?.addEventListener('click', () => { const date = parseDate(today()); state.viewYear = date.getFullYear(); state.viewMonth = date.getMonth(); state.selectedDate = today(); loadCalendar(); });
  $('[data-operations-calendar-grid]')?.addEventListener('click', (event) => { const day = event.target.closest('[data-operations-calendar-date]'); if (!day) return; state.selectedDate = day.dataset.operationsCalendarDate; renderCalendar(); });
  window.addEventListener('tmall:refresh', load);
  window.addEventListener('tmall:date-range-change', (event) => { const date = parseDate(event.detail?.endDate || today()); if (!Number.isNaN(date.getTime())) { state.viewYear = date.getFullYear(); state.viewMonth = date.getMonth(); state.selectedDate = ''; } load(); });
  window.TmallOperationsCenter = Object.freeze({ reload: load, getState: () => ({ filter: state.filter, actions: state.actions.slice(), logs: state.logs.slice(), anomalies: state.anomalies.slice(), calendarActions: state.calendarActions.slice() }) });
  load().catch((error) => { state.sourceErrors.push('all'); $('[data-operations-feed-status]').textContent = error.message || '提醒加载失败'; renderState($('[data-operations-feed]'), 'calculation-failed', load); });
})();
