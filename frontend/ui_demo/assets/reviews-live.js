(function () {
  const list = document.querySelector('[data-reviews-list]');
  const status = document.querySelector('[data-reviews-status]');
  const filter = document.querySelector('[data-actions-status-filter]');
  const labels = { draft: '草稿', pending_execution: '待执行', executing: '执行中', observing: '观察中', blocked: '阻塞', calculation_failed: '计算失败', pending_review: '待复盘', completed: '已完成', cancelled: '已取消' };
  const nextStatus = { draft: 'pending_execution', pending_execution: 'executing', executing: 'observing', observing: 'pending_review', blocked: 'pending_execution', calculation_failed: 'observing' };
  const json = (body) => ({ method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });

  async function load() {
    status.textContent = '加载中…';
    try {
      const response = await DemoApi.domainRequest('/api/actions?limit=500');
      const selected = filter?.value || '';
      const actions = response.data.filter((item) => !selected || item.status === selected);
      if (!actions.length) { list.textContent = selected ? '当前状态没有动作。' : '当前没有动作。'; status.textContent = '数据已更新'; return; }
      list.replaceChildren(...actions.map((action) => {
        const form = document.createElement('form'); form.className = 'modal-form__body';
        const heading = document.createElement('h3'); heading.textContent = `${action.product_id} · ${action.action_type}`;
        const state = document.createElement('p'); state.textContent = `状态：${labels[action.status] || action.status || '--'} · 版本：${action.version}`;
        const purpose = document.createElement('p'); purpose.textContent = `目的：${action.purpose_note || '--'}`;
        const result = document.createElement('p'); result.textContent = `观察结果：${action.before_metric_value ?? '--'} → ${action.after_metric_value ?? '--'}（变化 ${action.result_change ?? '--'}）`;
        form.append(heading, state, purpose, result);
        if (action.status === 'pending_review') {
          form.insertAdjacentHTML('beforeend', '<label>是否有效<select class="select" name="effective"><option value="true">有效</option><option value="false">无效</option></select></label><label>原因<textarea class="input" name="reason" required></textarea></label><label>结论<textarea class="input" name="conclusion" required></textarea></label><label>后续动作<input class="input" name="next_action" required></label><label>复盘人<input class="input" name="reviewer" value="operator" required></label><button class="button button--primary" type="submit">完成复盘</button><p role="status"></p>');
          form.addEventListener('submit', async (event) => { event.preventDefault(); const data = new FormData(form); const message = form.querySelector('[role=status]'); try { await DemoApi.domainRequest(`/api/actions/${action.id}/review`, json({ version: action.version, effective: data.get('effective') === 'true', reason: data.get('reason'), conclusion: data.get('conclusion'), next_action: data.get('next_action'), reviewer: data.get('reviewer') })); message.textContent = '已完成复盘'; load(); } catch (error) { message.textContent = error.message; } });
        } else if (nextStatus[action.status]) {
          const button = document.createElement('button'); button.type = 'button'; button.className = 'button'; button.textContent = `转为${labels[nextStatus[action.status]]}`;
          button.addEventListener('click', async () => { const payload = { version: action.version, status: nextStatus[action.status] }; try { await DemoApi.domainRequest(`/api/actions/${action.id}/transition`, json(payload)); load(); } catch (error) { status.textContent = error.message; } }); form.appendChild(button);
        }
        return form;
      }));
      status.textContent = `共 ${actions.length} 条动作`;
    } catch (error) { list.textContent = '动作数据加载失败。'; status.textContent = error.message; }
  }
  document.querySelector('[data-reviews-refresh]')?.addEventListener('click', load);
  filter?.addEventListener('change', load);
  document.querySelector('[data-actions-recalculate]')?.addEventListener('click', async () => { try { await DemoApi.domainRequest('/api/actions/recalculate', { method: 'POST' }); load(); } catch (error) { status.textContent = error.message; } });
  window.addEventListener('tmall:refresh', load); load();
  const periodForm = document.querySelector('[data-period-review-form]'); const periodStatus = document.querySelector('[data-period-review-status]'); const periodList = document.querySelector('[data-period-review-list]');
  async function loadPeriodReviews() { try { const rows = (await DemoApi.domainRequest('/api/period-reviews')).data; periodList.replaceChildren(...rows.map((row) => { const item = document.createElement('div'); item.className = 'status-list__item'; item.append(Object.assign(document.createElement('strong'), { textContent: `${row.period_type} · ${row.period_key}` }), Object.assign(document.createElement('span'), { textContent: row.summary })); return item; })); if (!rows.length) periodList.textContent = '尚无周期复盘。'; } catch (error) { periodList.textContent = error.message; } }
  periodForm?.addEventListener('submit', async (event) => { event.preventDefault(); const data = new FormData(periodForm); try { await DemoApi.domainRequest(`/api/period-reviews/${data.get('period_type')}/${encodeURIComponent(data.get('period_key'))}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(Object.fromEntries(data)) }); periodStatus.textContent = '周期复盘已保存。'; loadPeriodReviews(); } catch (error) { periodStatus.textContent = error.message; } }); loadPeriodReviews();
})();
