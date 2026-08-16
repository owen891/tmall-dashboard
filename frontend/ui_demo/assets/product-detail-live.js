(function () {
  const id = decodeURIComponent(location.pathname.split('/').pop());
  const $ = (selector) => document.querySelector(selector);
  const $$ = (selector) => [...document.querySelectorAll(selector)];
  const setText = (selector, value) => $$(selector).forEach((node) => { node.textContent = value ?? '--'; });
  const money = (value) => value == null ? '--' : `¥${Number(value).toLocaleString('zh-CN', { maximumFractionDigits: 2 })}`;
  const percent = (value) => value == null ? '--' : `${(Number(value) * 100).toFixed(2)}%`;
  const pct = (value) => value == null ? '--' : `${Number(value).toFixed(1)}%`;
  const actionStatusLabels = { draft: '草稿', pending_execution: '待执行', executing: '执行中', observing: '观察中', pending_review: '待复盘', blocked: '阻塞', calculation_failed: '计算失败', completed: '已完成', cancelled: '已取消' };
  const actionStatus = (value) => actionStatusLabels[value] || value || '--';
  const row = (label, value) => { const node = document.createElement('div'); node.className = 'status-list__item'; const left = document.createElement('span'); left.className = 'status-list__label'; left.textContent = label; const right = document.createElement('span'); right.className = 'status-list__value'; right.textContent = value ?? '--'; node.append(left, right); return node; };
  const transitions = { draft: ['pending_execution', 'cancelled'], pending_execution: ['executing', 'blocked', 'cancelled'], executing: ['observing', 'blocked', 'cancelled'], observing: ['pending_review', 'blocked', 'calculation_failed'], pending_review: ['blocked'], blocked: ['pending_execution', 'cancelled'], calculation_failed: ['observing', 'blocked'], completed: ['pending_review'] };
  let detailPayload = null;
  let selectedRange = {};
  const detailTabs = new Set(['overview', 'trend', 'lifecycle', 'actions', 'evidence']);

  function selectDetailTab(tab, { updateHash = true, focus = false } = {}) {
    const active = detailTabs.has(tab) ? tab : 'overview';
    $$('[data-product-detail-tab]').forEach((button) => {
      const selected = button.dataset.productDetailTab === active;
      button.setAttribute('aria-selected', String(selected));
      button.tabIndex = selected ? 0 : -1;
      if (selected && focus) button.focus();
    });
    $$('[data-product-detail-panel]').forEach((panel) => {
      panel.hidden = panel.dataset.productDetailPanel !== active;
    });
    if (updateHash) history.replaceState(null, '', `${location.pathname}${location.search}#${active}`);
  }

  function bindWorkbenchNavigation() {
    $$('[data-product-detail-tab]').forEach((button) => {
      button.addEventListener('click', () => selectDetailTab(button.dataset.productDetailTab));
      button.addEventListener('keydown', (event) => {
        if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
        const tabs = $$('[data-product-detail-tab]');
        const index = tabs.indexOf(button);
        const nextIndex = event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1 : (index + (event.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length;
        event.preventDefault();
        selectDetailTab(tabs[nextIndex].dataset.productDetailTab, { focus: true });
      });
    });
    const back = $('[data-product-detail-back]');
    const referrer = document.referrer;
    let cameFromProducts = false;
    try { cameFromProducts = referrer && new URL(referrer).origin === window.location.origin && new URL(referrer).pathname === '/products'; } catch (_) { cameFromProducts = false; }
    back?.addEventListener('click', (event) => {
      if (!cameFromProducts) return;
      event.preventDefault();
      window.history.back();
    });
    selectDetailTab(location.hash.slice(1), { updateHash: false });
  }
  const requestAction = (action, suffix, body) => DemoApi.domainRequest(`/api/actions/${encodeURIComponent(action.id)}${suffix}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  function actionCard(action) {
    const card = document.createElement('div'); card.className = 'status-list__item';
    const content = document.createElement('div'); content.className = 'status-list__value';
    const title = document.createElement('strong'); title.textContent = `${action.planned_at || '--'} · ${action.action_type || '--'} · ${actionStatus(action.status)}`;
    const detail = document.createElement('div'); detail.textContent = `目的：${action.purpose_note || '--'}；动作：${action.action_detail || '--'}；结果：${action.calculation_note || '--'}；复盘：${action.review_conclusion || '--'}；历史：${(action.history || []).length} 条`;
    content.append(title, detail);
    const controls = document.createElement('div'); controls.className = 'button-row';
    (transitions[action.status] || []).forEach((target) => {
      const button = document.createElement('button'); button.type = 'button'; button.className = 'button button--ghost'; button.textContent = `转为${actionStatus(target)}`;
      button.addEventListener('click', async () => {
        const body = { capability_key: 'product-detail.review_action', status: target, version: action.version };
        if (target === 'blocked') { body.blocked_reason = window.prompt('请输入阻塞原因') || ''; body.expected_recovery_at = window.prompt('请输入预计恢复日期（YYYY-MM-DD）') || ''; if (!body.blocked_reason || !body.expected_recovery_at) return; }
        try { await requestAction(action, '/transition', body); await load(); } catch (error) { window.alert(error.message); }
      }); controls.appendChild(button);
    });
    if (action.status === 'observing') {
      const button = document.createElement('button'); button.type = 'button'; button.className = 'button button--ghost'; button.textContent = '重新计算观察窗口';
      button.addEventListener('click', async () => { try { await DemoApi.domainRequest('/api/actions/recalculate', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ capability_key: 'product-detail.review_action' }) }); await load(); } catch (error) { window.alert(error.message); } }); controls.appendChild(button);
    }
    if (action.status === 'pending_review') {
      const form = document.createElement('form'); form.className = 'modal-form__body';
      form.innerHTML = '<label>是否有效<select class="select" name="effective" aria-label="复盘结论是否有效"><option value="true">有效</option><option value="false">无效</option></select></label><label>变更原因<input class="input" name="reason" required></label><label>复盘结论<input class="input" name="conclusion" required></label><label>后续动作<input class="input" name="next_action" required></label><label>复盘人<input class="input" name="reviewer" value="运营人员" required></label><button class="button button--primary" type="submit">提交复盘</button>';
      form.addEventListener('submit', async (event) => { event.preventDefault(); const values = Object.fromEntries(new FormData(form)); try { await requestAction(action, '/review', { ...values, capability_key: 'product-detail.review_action', effective: values.effective === 'true', version: action.version }); await load(); } catch (error) { window.alert(error.message); } }); content.appendChild(form);
    }
    card.append(content, controls); return card;
  }
  function renderHistory(rows) { const target = $('[data-product-detail-lifecycle-history]'); if (!target) return; target.replaceChildren(...(rows || []).map((item) => { const tr = document.createElement('tr'); [item.created_at, item.recommended_stage, item.manual_stage, item.reason, item.operator, item.version].forEach((value, index) => { const td = document.createElement('td'); td.textContent = value == null || value === '' ? '--' : String(value); if (index === 5) td.className = 'num'; tr.appendChild(td); }); return tr; })); if (!rows?.length) target.innerHTML = '<tr><td colspan="6">暂无生命周期历史</td></tr>'; }
  function renderComparison(rows, contributions) { const target = $('[data-product-detail-period-comparison]'); if (target) { target.replaceChildren(...(rows || []).map((item) => { const tr = document.createElement('tr'); const metrics = item.metrics || {}; [item.month, metrics.net_sales?.current, pct(metrics.net_sales?.change_pct), pct(metrics.product_visitors?.change_pct), item.anomalies?.join('、') || '无明显变化'].forEach((value, index) => { const td = document.createElement('td'); td.textContent = value == null ? '--' : (index === 1 ? money(value) : String(value)); if (index > 0 && index < 4) td.className = 'num'; tr.appendChild(td); }); return tr; })); if (!rows?.length) target.innerHTML = '<tr><td colspan="5">暂无周期对比数据</td></tr>'; } const summary = $('[data-product-detail-contribution]'); if (summary) { const latest = (contributions || []).at(-1); summary.replaceChildren(latest ? row('贡献分析（非因果）', latest.drivers.map((driver) => `${driver.metric}: ${driver.delta == null ? '--' : Number(driver.delta).toFixed(2)}`).join('、')) : row('贡献分析', '暂无可比较周期')); } }
  function renderEvidence(summary) { const target = $('[data-product-detail-evidence]'); if (!target) return; const coverage = summary?.coverage || {}; target.replaceChildren(row('证据等级', summary?.level || '--'), row('覆盖范围', `${coverage.start || '--'} 至 ${coverage.end || '--'}（${coverage.days || 0} 天）`), row('数据来源', (summary?.sources || []).map((source) => `${source.source}: ${source.row_count}`).join('、') || '--'), row('缺失字段', (summary?.missing_fields || []).join('、') || '无'), row('限制说明', (summary?.unknowns || []).join('、') || '暂不支持严格因果归因')); }
  async function load(range) {
    try {
      selectedRange = range || window.TmallDateRange?.getState?.() || selectedRange || {};
      const query = new URLSearchParams(); if (selectedRange.startDate) query.set('start', selectedRange.startDate); if (selectedRange.endDate) query.set('end', selectedRange.endDate);
      const payload = await DemoApi.domainRequest(`/api/products/${encodeURIComponent(id)}/detail${query.toString() ? `?${query}` : ''}`); detailPayload = payload; const data = payload.data;
      setText('[data-product-detail-title]', data.product.title || id);
      setText('[data-product-detail-meta]', `商品 ${id} · 数据截止 ${data.summary.data_cutoff_date || '--'}`);
      setText('[data-product-detail-breadcrumb]', `商品经营 / 商品列表 / ${data.product.title || id}`);
      $('[data-product-detail-meta]').textContent = `商品 ${id} · 数据截止 ${data.summary.data_cutoff_date || '--'}`;
      $('[data-product-detail-status]').textContent = `${DemoLabels.label('status', data.product.status, data.product.status || '--')} · ${data.product.manager || '未分配'}`;
      $('[data-product-detail-info]').replaceChildren(row('分层 / 风格', `${DemoLabels.classification('tiers', data.product.tier, '--')} / ${DemoLabels.classification('styles', data.product.style, '--')}`), row('类目 / 场景', `${DemoLabels.clean(data.product.category, '--')} / ${DemoLabels.clean(data.product.scene, '--')}`), row('上架日期', DemoLabels.clean(data.product.list_date, '--')));
      [['payment_amount', money], ['net_sales', money], ['payment_conversion_rate', percent], ['expense_ratio', percent], ['average_order_value', money]].forEach(([key, format]) => { setText(`[data-product-detail-kpi="${key}"]`, format(data.summary[key])); });
      setText('[data-product-detail-stage]', data.lifecycle?.stage_label || data.lifecycle?.stage || '--');
      setText('[data-product-detail-days]', data.lifecycle?.continuous_valid_days ?? '--');
      setText('[data-product-detail-confidence]', `置信度：${DemoLabels.label('confidence', data.lifecycle?.confidence)} · ${data.lifecycle?.locked ? '人工' : '系统'}`);
      setText('[data-product-detail-rationale]', data.lifecycle?.rationale || '暂无判断依据');
      const workbenchExportQuery = new URLSearchParams({ capability_key: 'product-detail.export' });
      if (selectedRange.startDate) workbenchExportQuery.set('start', selectedRange.startDate);
      if (selectedRange.endDate) workbenchExportQuery.set('end', selectedRange.endDate);
      $$('[data-product-detail-export]').forEach((link) => { link.href = `/api/products/${encodeURIComponent(id)}/detail/export?${workbenchExportQuery}`; });
      $('[data-product-detail-stage]').textContent = data.lifecycle?.stage_label || data.lifecycle?.stage || '--'; $('[data-product-detail-days]').textContent = data.lifecycle?.continuous_valid_days ?? '--'; $('[data-product-detail-confidence]').textContent = `置信度：${DemoLabels.label('confidence', data.lifecycle?.confidence)} · ${data.lifecycle?.locked ? '人工' : '系统'}`; $('[data-product-detail-rationale]').textContent = data.lifecycle?.rationale || '暂无判断依据';
      const trend = $('[data-product-detail-trend]'); trend.replaceChildren(...data.daily_trend.map((item) => { const tr = document.createElement('tr'); [item.date, money(item.payment_amount), money(item.net_sales), item.product_visitors ?? '--', money(item.ad_spend)].forEach((value, index) => { const td = document.createElement('td'); td.textContent = value; if (index) td.className = 'num'; tr.appendChild(td); }); return tr; })); if (!data.daily_trend.length) trend.innerHTML = '<tr><td colspan="5">暂无日度数据</td></tr>';
      const actions = $('[data-product-detail-actions]'); actions.replaceChildren(...data.actions.map(actionCard)); if (!data.actions.length) actions.textContent = '暂无运营动作'; renderHistory(data.lifecycle_history); renderComparison(data.period_comparison, data.contribution_analysis); renderEvidence(data.evidence_summary);
      const exportLink = $('[data-product-detail-export]'); if (exportLink) { const exportQuery = new URLSearchParams({ capability_key: 'product-detail.export' }); if (selectedRange.startDate) exportQuery.set('start', selectedRange.startDate); if (selectedRange.endDate) exportQuery.set('end', selectedRange.endDate); exportLink.href = `/api/products/${encodeURIComponent(id)}/detail/export?${exportQuery}`; }
    } catch (error) { DemoApi.renderDataState($('[data-product-detail-status]'), 'calculation-failed', { message: error.message, retry: load }); }
  }
  $('[data-product-detail-action-form]').addEventListener('submit', async (event) => { event.preventDefault(); if (Object.keys(detailPayload?.capabilities || {}).length && !DemoApi.can(detailPayload, 'can_create_action')) { $('[data-product-detail-action-status]').textContent = '当前数据条件不满足创建运营动作'; return; } const form = new FormData(event.currentTarget); try { await DemoApi.domainRequest('/api/actions', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ capability_key: 'product-detail.create_action', product_id: id, purpose_type: 'increase_sales', purpose_note: form.get('purpose_note'), action_type: form.get('action_type'), action_detail: form.get('action_detail'), target_metric: 'payment_amount', planned_at: form.get('planned_at'), observer_window_days: 7, assigned_to: 'operator' }) }); $('[data-product-detail-action-status]').textContent = '运营动作草稿已创建'; load(); } catch (error) { $('[data-product-detail-action-status]').textContent = error.message; } });
  bindWorkbenchNavigation();
  window.addEventListener('tmall:date-range-change', (event) => load(event.detail));
  DemoLabels.load().finally(load);
})();
