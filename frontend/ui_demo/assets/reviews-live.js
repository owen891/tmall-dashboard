(function () {
  const list = document.querySelector('[data-reviews-list]');
  const status = document.querySelector('[data-reviews-status]');
  let actionPayload = { capabilities: {} };
  const filter = document.querySelector('[data-actions-status-filter]');
  const labels = { draft: '草稿', pending_execution: '待执行', executing: '执行中', observing: '观察中', blocked: '阻塞', calculation_failed: '计算失败', pending_review: '待复盘', completed: '已完成', cancelled: '已取消' };
  const nextStatus = { draft: 'pending_execution', pending_execution: 'executing', executing: 'observing', observing: 'pending_review', blocked: 'pending_execution', calculation_failed: 'observing' };
  const json = (body) => ({ method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  const renderDataState = (state, details) => DemoApi.renderDataState(status, state, details);
  let loadToken = 0;
  const pendingMutations = new Set();
  const renderSummary = (actions) => {
    const counts = actions.reduce((result, action) => {
      const key = action.status || 'unknown';
      result[key] = (result[key] || 0) + 1;
      return result;
    }, {});
    document.querySelectorAll('[data-reviews-summary]').forEach((node) => {
      node.textContent = String(counts[node.dataset.reviewsSummary] || 0).padStart(2, '0');
    });
  };

  async function load() {
    const token = ++loadToken;
    renderDataState('loading');
    try {
      const query = filter?.value ? `?limit=500&status=${encodeURIComponent(filter.value)}` : '?limit=500';
      const response = await DemoApi.domainRequest(`/api/actions${query}`);
      if (token !== loadToken) return;
      actionPayload = response;
      const allActions = Array.isArray(response.data) ? response.data : [];
      renderSummary(allActions);
      const selected = filter?.value || '';
      const actions = allActions.filter((item) => item && (!selected || item.status === selected));
      if (!actions.length) { list.textContent = selected ? '当前状态没有动作。' : '当前没有动作。'; renderDataState('no-data', { message: selected ? '当前状态没有动作。' : '当前没有动作。' }); return; }
      list.replaceChildren(...actions.map((action) => {
        const container = document.createElement('details'); container.className = 'plain-panel panel';
        const cardSummary = document.createElement('summary'); cardSummary.textContent = `${action.product_id} · ${DemoLabels.label('action', action.action_type, action.action_type)} · ${labels[action.status] || action.status || '--'}`;
        const form = document.createElement('form'); form.className = 'modal-form__body';
        const heading = document.createElement('h3'); heading.textContent = `${action.product_id} · ${DemoLabels.label('action', action.action_type, action.action_type)}`;
        const state = document.createElement('p'); state.textContent = `状态：${labels[action.status] || action.status || '--'} · 版本：${action.version}`;
        const purpose = document.createElement('p'); purpose.textContent = `目的：${action.purpose_note || '--'}`;
        const detail = document.createElement('p'); detail.textContent = `动作详情：${action.action_detail || '--'}`;
        const history = document.createElement('details'); const summary = document.createElement('summary'); summary.textContent = `历史记录（${(action.history || []).length}）`; history.appendChild(summary);
        (action.history || []).forEach((entry) => { const item = document.createElement('p'); item.textContent = `${entry.created_at || '--'} ${entry.from_status ? DemoLabels.label('status', entry.from_status, entry.from_status) : '—'} → ${DemoLabels.label('status', entry.to_status, entry.to_status)} · ${entry.detail || ''}`; history.appendChild(item); });
        const result = document.createElement('p'); result.textContent = `观察结果：${action.before_metric_value ?? '--'} → ${action.after_metric_value ?? '--'}（变化 ${action.result_change ?? '--'}）`;
        form.append(heading, state, purpose, detail, result, history);
        const hasObservation = action.before_metric_value != null && action.after_metric_value != null;
        if (action.status === 'pending_review' && hasObservation) {
          form.insertAdjacentHTML('beforeend', '<label>是否有效<select class="select" name="effective"><option value="true">有效</option><option value="false">无效</option></select></label><label>原因<textarea class="input" name="reason" required></textarea></label><label>结论<textarea class="input" name="conclusion" required></textarea></label><label>后续动作<input class="input" name="next_action" required></label><label>复盘人<input class="input" name="reviewer" value="运营人员" required></label><button class="button button--primary" type="submit">完成复盘</button><p role="status"></p>');
          form.addEventListener('submit', async (event) => { event.preventDefault(); const data = new FormData(form); const message = form.querySelector('[role=status]'); const submit = form.querySelector('button[type="submit"]'); const key = `review:${action.id}`; if (pendingMutations.has(key)) return; pendingMutations.add(key); if (submit) submit.disabled = true; try { await DemoApi.domainRequest(`/api/actions/${action.id}/review`, json({ version: action.version, effective: data.get('effective') === 'true', reason: data.get('reason'), conclusion: data.get('conclusion'), next_action: data.get('next_action'), reviewer: data.get('reviewer') })); message.textContent = '已完成复盘'; await load(); } catch (error) { message.textContent = error.message || '复盘提交失败，请重试'; } finally { pendingMutations.delete(key); if (submit?.isConnected) submit.disabled = false; } });
        } else if (action.status === 'pending_review') {
          const waiting = document.createElement('p'); waiting.className = 'panel__hint'; waiting.textContent = '等待观察数据后再复盘'; form.appendChild(waiting);
        } else if (nextStatus[action.status]) {
          const button = document.createElement('button'); button.type = 'button'; button.className = 'button'; button.textContent = `转为${labels[nextStatus[action.status]]}`;
          button.disabled = Object.keys(actionPayload.capabilities || {}).length > 0 && !DemoApi.can(actionPayload, 'can_transition');
          button.addEventListener('click', async () => { if (Object.keys(actionPayload.capabilities || {}).length > 0 && !DemoApi.can(actionPayload, 'can_transition')) return; const key = `transition:${action.id}`; if (pendingMutations.has(key)) return; pendingMutations.add(key); button.disabled = true; const payload = { version: action.version, status: nextStatus[action.status] }; try { await DemoApi.domainRequest(`/api/actions/${action.id}/transition`, json(payload)); await load(); } catch (error) { status.textContent = error.message || '状态更新失败，请重试'; } finally { pendingMutations.delete(key); if (button.isConnected) button.disabled = false; } }); form.appendChild(button);
        }
        container.append(cardSummary, form);
        return container;
      }));
      status.textContent = `共 ${actions.length} 条动作`;
    } catch (error) { list.textContent = '动作数据加载失败。'; renderDataState('calculation-failed', { message: error.message, retry: load }); }
  }
  document.querySelector('[data-reviews-refresh]')?.addEventListener('click', load);
  filter?.addEventListener('change', load);
  document.querySelector('[data-actions-recalculate]')?.addEventListener('click', async (event) => { if (Object.keys(actionPayload.capabilities || {}).length > 0 && !DemoApi.can(actionPayload, 'can_recalculate')) return; const button = event.currentTarget; const key = 'actions:recalculate'; if (pendingMutations.has(key)) return; pendingMutations.add(key); button.disabled = true; try { await DemoApi.domainRequest('/api/actions/recalculate', { method: 'POST' }); await load(); } catch (error) { status.textContent = error.message || '重新计算失败，请重试'; } finally { pendingMutations.delete(key); if (button.isConnected) button.disabled = false; } });
  window.addEventListener('tmall:refresh', load); load();
  const periodForm = document.querySelector('[data-period-review-form]'); const periodStatus = document.querySelector('[data-period-review-status]'); const periodList = document.querySelector('[data-period-review-list]');
  const periodKey = document.querySelector('[data-period-review-key]');
  const syncPeriodKey = (range = window.TmallDateRange?.getState?.()) => {
    if (!periodKey) return;
    const type = periodForm?.elements?.period_type?.value || 'month';
    const fallback = new Date().toISOString().slice(0, type === 'month' ? 7 : 10);
    periodKey.value = type === 'month' ? (range?.endDate || fallback).slice(0, 7) : (range?.endDate || fallback);
  };
  async function loadPeriodReviews() { try { const response = await DemoApi.domainRequest('/api/period-reviews'); const rows = Array.isArray(response.data) ? response.data : []; if (!periodList) return; periodList.replaceChildren(...rows.filter((row) => row && typeof row === 'object').map((row) => { const item = document.createElement('div'); item.className = 'status-list__item'; item.append(Object.assign(document.createElement('strong'), { textContent: `${DemoLabels.label('period', row.period_type, row.period_type)} · ${row.period_key}` }), Object.assign(document.createElement('span'), { textContent: row.summary || '--' })); return item; })); if (!rows.length) periodList.textContent = '尚无周期复盘。'; } catch (error) { if (periodList) periodList.textContent = error.message || '周期复盘加载失败'; } }
  periodForm?.addEventListener('submit', async (event) => { event.preventDefault(); const data = new FormData(periodForm); const submit = periodForm.querySelector('button[type="submit"]'); if (submit?.disabled) return; if (submit) submit.disabled = true; try { await DemoApi.domainRequest(`/api/period-reviews/${data.get('period_type')}/${encodeURIComponent(data.get('period_key'))}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(Object.fromEntries(data)) }); periodStatus.textContent = '周期复盘已保存。'; await loadPeriodReviews(); } catch (error) { periodStatus.textContent = error.message || '周期复盘保存失败，请重试'; } finally { if (submit?.isConnected) submit.disabled = false; } });
  periodForm?.elements?.period_type?.addEventListener('change', () => syncPeriodKey());
  window.addEventListener('tmall:date-range-change', (event) => { syncPeriodKey(event.detail); loadPeriodReviews(); });
  syncPeriodKey();
  loadPeriodReviews();
})();
