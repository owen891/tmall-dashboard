(function () {
  const form = document.querySelector('[data-goals-form]');
  const status = document.querySelector('[data-goals-status]');
  const previewBody = document.querySelector('[data-goals-allocation-preview]');
  const monthsBody = document.querySelector('[data-goals-months]');
  const versionLabel = document.querySelector('[data-goals-version]');
  const previewBasis = document.querySelector('[data-goals-allocation-basis]');
  const suggestButton = document.querySelector('[data-goals-suggest]');
  let current = null;
  let capabilities = {};
  let settings = { annual_target_default: 0, growth_multiplier: 1.1 };
  let previewToken = 0;
  let previewTimer = null;
  let annualTargetDirty = false;

  const money = (value) => Number(value || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const setStatus = (message) => {
    status.classList.remove('data-state');
    status.textContent = message || '';
  };
  const renderDataState = (state, details = {}) => DemoApi.renderDataState(status, state, details);
  const setTableMessage = (body, colspan, message) => { body.replaceChildren(); const row = body.insertRow(); const cell = row.insertCell(); cell.colSpan = colspan; cell.textContent = message; };
  const canEdit = () => !Object.keys(capabilities).length || DemoApi.can({ capabilities }, 'can_edit');
  const canLock = () => !Object.keys(capabilities).length || DemoApi.can({ capabilities }, 'can_lock');

  function makeIconButton(icon, label, action) {
    const button = document.createElement('button');
    button.className = 'button button--ghost button--icon';
    button.type = 'button';
    button.title = label;
    button.setAttribute('aria-label', label);
    button.innerHTML = `<i data-lucide="${icon}"></i>`;
    button.addEventListener('click', action);
    return button;
  }

  function renderPreview(data) {
    const basis = data.allocation_basis || '等待年度目标';
    previewBasis.textContent = basis;
    previewBasis.className = `badge ${basis === '去年同期销售占比' ? 'badge--success' : 'badge--muted'}`;
    previewBody.replaceChildren(...(data.months || []).map((month) => {
      const row = document.createElement('tr');
      [month.period_key, money(month.prior_year_net_sales), month.allocation_ratio == null ? '--' : `${(month.allocation_ratio * 100).toFixed(2)}%`, money(month.suggested_target)]
        .forEach((value, index) => { const cell = row.insertCell(); cell.textContent = value; if (index > 0) cell.className = 'num'; });
      return row;
    }));
    if (!data.months?.length) setTableMessage(previewBody, 4, '没有可用于预览的月份');
  }

  async function loadPreview() {
    const annualTarget = Number(form.elements.annual_target.value);
    const year = Number(form.elements.year.value);
    if (!Number.isFinite(annualTarget) || annualTarget < 0 || !Number.isInteger(year)) {
      previewBasis.textContent = '等待年度目标';
      previewBasis.className = 'badge badge--muted';
      setTableMessage(previewBody, 4, '输入年度总目标后显示分配预览');
      return;
    }
    const token = ++previewToken;
    setTableMessage(previewBody, 4, '正在计算分配预览');
    try {
      const response = await DemoApi.domainRequest(`/api/goals/${year}/allocation-preview?annual_target=${encodeURIComponent(annualTarget)}`);
      if (token !== previewToken) return;
      renderPreview(response.data);
    } catch (error) {
      if (token !== previewToken) return;
      previewBasis.textContent = '预览失败';
      previewBasis.className = 'badge badge--danger';
      setTableMessage(previewBody, 4, error.message || '分配预览失败');
    }
  }

  function queuePreview() {
    window.clearTimeout(previewTimer);
    previewTimer = window.setTimeout(loadPreview, 180);
  }

  function renderMonths(periods) {
    const locked = new Set(periods.locked_months || []);
    monthsBody.replaceChildren(...(periods.months || []).map((month) => {
      const row = document.createElement('tr');
      const completeLocked = locked.has(month.period_key);
      const monthCell = row.insertCell(); monthCell.textContent = month.period_key;
      const targetCell = row.insertCell(); targetCell.className = 'num';
      const input = document.createElement('input');
      input.className = 'input goals-month-target';
      input.name = 'target_amount';
      input.type = 'number';
      input.min = '0';
      input.step = '0.01';
      input.inputMode = 'decimal';
      input.value = Number(month.target_amount).toFixed(2);
      input.setAttribute('data-goals-month-target', month.period_key);
      input.disabled = completeLocked || !canEdit();
      input.setAttribute('aria-label', `${month.period_key}月度目标`);
      targetCell.append(input);
      const sourceCell = row.insertCell();
      const source = document.createElement('span');
      source.className = `badge ${month.source === 'manual' ? 'badge--warning' : 'badge--muted'}`;
      source.textContent = month.source === 'manual' ? '手动调整' : '自动分配';
      sourceCell.append(source);
      const stateCell = row.insertCell();
      const state = document.createElement('span');
      state.className = `badge ${completeLocked ? 'badge--muted' : 'badge--success'}`;
      state.textContent = completeLocked ? '已锁定' : '可编辑';
      stateCell.append(state);
      const actionsCell = row.insertCell();
      if (completeLocked) {
        actionsCell.textContent = '--';
      } else {
        const actions = document.createElement('div'); actions.className = 'goals-month-actions';
        const save = makeIconButton('save', '保存本月目标', () => saveMonth(month.period_key, input));
        const lock = makeIconButton('lock', '锁定本月目标', () => lockMonth(month.period_key));
        save.disabled = !canEdit();
        lock.disabled = !canLock();
        actions.append(save, lock); actionsCell.append(actions);
      }
      return row;
    }));
    if (!periods.months?.length) setTableMessage(monthsBody, 5, '该年度尚未创建目标');
    window.lucide?.createIcons();
  }

  async function load(year, replaceAnnualTarget = false) {
    renderDataState('loading', { message: '正在加载年度目标' });
    setTableMessage(monthsBody, 5, '正在加载月度执行计划');
    try {
      const goal = await DemoApi.domainRequest(`/api/goals/${year}`);
      current = goal.data;
      capabilities = goal.capabilities || {};
      const periods = await DemoApi.domainRequest(`/api/goals/${year}/periods`);
      renderMonths(periods.data);
      versionLabel.textContent = `当前版本 ${current.version}，年度合计 ¥${money(current.annual_total)}`;
      if (replaceAnnualTarget || !annualTargetDirty) form.elements.annual_target.value = Number(current.annual_total).toFixed(2);
      queuePreview();
    } catch (error) {
      current = null; capabilities = {};
      versionLabel.textContent = '该年度尚未创建目标';
      if (error.status === 404) {
        renderDataState('no-data', { message: '保存年度目标后显示月度执行计划' });
        setTableMessage(monthsBody, 5, '保存年度目标后显示月度执行计划');
      } else {
        renderDataState('calculation-failed', { message: error.message || '目标加载失败', retry: () => load(year, replaceAnnualTarget) });
        setTableMessage(monthsBody, 5, error.message || '目标加载失败');
      }
      queuePreview();
    }
  }

  async function saveMonth(periodKey, input) {
    if (!current || input.disabled) return;
    const targetAmount = Number(input.value);
    if (!Number.isFinite(targetAmount) || targetAmount < 0) { setStatus('请输入有效的月度目标金额'); input.focus(); return; }
    input.disabled = true;
    try {
      const response = await DemoApi.domainRequest(`/api/goals/${current.year}/adjustments`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ version: current.version, period_type: 'month', period_key: periodKey, target_amount: targetAmount, operator: '运营人员', reason: `月度目标调整：${periodKey}` }),
      });
      setStatus(`已保存 ${periodKey}，当前版本 ${response.data.version}`);
      await load(current.year);
    } catch (error) { input.disabled = false; setStatus(error.message || '月度目标保存失败'); }
  }

  async function lockMonth(periodKey) {
    if (!current || !canLock()) { setStatus('当前目标不允许锁定'); return; }
    try {
      const response = await DemoApi.domainRequest(`/api/goals/${current.year}/locks`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ version: current.version, period_type: 'month', period_key: periodKey }),
      });
      setStatus(`已锁定 ${periodKey}，当前版本 ${response.data.version}`);
      await load(current.year);
    } catch (error) { setStatus(error.message || '月份锁定失败'); }
  }

  async function loadSettings() {
    try {
      const response = await DemoApi.domainRequest('/api/settings');
      settings = { ...settings, ...(response.data || {}) };
    } catch (_) { setStatus('未能读取设置默认值，已使用页面默认值'); }
    form.elements.growth_multiplier.value = Number(settings.growth_multiplier || 1.1).toFixed(2);
    if (!form.elements.annual_target.value && Number(settings.annual_target_default) > 0) form.elements.annual_target.value = settings.annual_target_default;
  }

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const year = Number(form.elements.year.value);
    const annualTarget = Number(form.elements.annual_target.value);
    if (!Number.isFinite(annualTarget) || annualTarget < 0) { setStatus('请输入有效的年度总目标'); return; }
    const payload = { year, annual_target: annualTarget, growth_multiplier: Number(form.elements.growth_multiplier.value), operator: '运营人员', reason: '按去年同期销售占比生成年度目标' };
    if (current?.year === year) payload.version = current.version;
    try {
      const response = await DemoApi.domainRequest('/api/goals', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
      setStatus(`年度目标已保存，当前版本 ${response.data.version}`);
      annualTargetDirty = false;
      await load(year, true);
    } catch (error) { setStatus(error.message || '年度目标保存失败'); }
  });

  suggestButton.addEventListener('click', async () => {
    const year = Number(form.elements.year.value);
    const multiplier = Number(form.elements.growth_multiplier.value);
    try {
      const response = await DemoApi.domainRequest(`/api/goals/${year}/suggestion?growth_multiplier=${encodeURIComponent(multiplier)}`);
      form.elements.suggested_annual_target.value = Number(response.data.suggested_annual_target).toFixed(2);
      form.elements.annual_target.value = Number(response.data.suggested_annual_target).toFixed(2);
      annualTargetDirty = true;
      document.querySelector('[data-goals-suggestion-source]').textContent = `去年净销售额 ¥${money(response.data.prior_year_net_sales)} × ${multiplier.toFixed(2)} 倍`;
      queuePreview();
    } catch (error) { setStatus(error.message || '建议值生成失败'); }
  });

  form.elements.year.addEventListener('change', () => { annualTargetDirty = false; load(Number(form.elements.year.value)); });
  form.elements.annual_target.addEventListener('input', () => { annualTargetDirty = true; queuePreview(); });
  form.elements.growth_multiplier.addEventListener('change', () => { form.elements.suggested_annual_target.value = ''; });
  loadSettings().finally(() => { window.lucide?.createIcons(); load(Number(form.elements.year.value)); });
})();
