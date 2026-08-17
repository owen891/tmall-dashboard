(function () {
  const form = document.querySelector('[data-goals-form]');
  const adjustForm = document.querySelector('[data-goals-adjust-form]');
  const status = document.querySelector('[data-goals-status]');
  const months = document.querySelector('[data-goals-months]');
  const levels = document.querySelector('[data-goals-levels]');
  const versionLabel = document.querySelector('[data-goals-version]');
  const suggestButton = document.querySelector('[data-goals-suggest]');
  const levelFilter = document.querySelector('[data-goals-level-filter]');
  const periodPicker = document.querySelector('[data-goals-period-picker]');
  const adjustGate = document.querySelector('[data-goals-adjust-gate]');
  const adjustHelp = document.querySelector('[data-goals-adjust-help]');
  const suggestionSource = document.querySelector('[data-goals-suggestion-source]');
  let current = null;
  let goalCapabilities = {};
  let settings = { annual_target_default: 0, growth_multiplier: 1.1 };
  let loadToken = 0;

  const money = (value) => Number(value || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const setStatus = (message) => { if (status) status.textContent = message || ''; };
  const renderDataState = (state, details = {}) => DemoApi.renderDataState(status, state, details);

  function renderSettingsSummary() {
    const configuredTarget = Number(settings.annual_target_default || 0);
    document.querySelector('[data-goals-settings-summary="annual_target"]')?.replaceChildren(document.createTextNode(configuredTarget > 0 ? `¥${money(configuredTarget)}` : '未配置'));
    document.querySelector('[data-goals-settings-summary="growth_multiplier"]')?.replaceChildren(document.createTextNode(`${Number(settings.growth_multiplier || 1).toFixed(2)} 倍`));
  }

  function setAdjustEnabled(enabled) {
    adjustForm?.querySelectorAll('input, select, button').forEach((control) => { control.disabled = !enabled; });
    if (adjustGate) { adjustGate.textContent = enabled ? '可调整' : '等待年度目标'; adjustGate.className = `badge ${enabled ? 'badge--success' : 'badge--muted'}`; }
    if (adjustHelp) adjustHelp.textContent = enabled ? '调整只会重新分配未锁定日期' : '请先生成该年度目标';
  }

  function renderLevels(payload) {
    if (!levels) return;
    const actual = payload.actual || {};
    const locked = new Set((current?.locks || []).map((item) => `${item.period_type}:${item.period_key}`));
    const selectedGrain = levelFilter?.value || 'month';
    const rows = Object.entries(payload.levels || {}).flatMap(([grain, values]) => grain === 'year'
      ? [[grain, String(payload.year), values]]
      : Object.entries(values).map(([key, amount]) => [grain, key, amount])).filter(([grain]) => grain === selectedGrain);
    levels.replaceChildren(...rows.map(([grain, key, target]) => {
      const row = document.createElement('tr');
      const done = grain === 'year' ? Number(actual?.year || 0) : Number(actual?.[grain]?.[key] || 0);
      const rate = Number(target) ? `${(done / Number(target) * 100).toFixed(1)}%` : '--';
      [({ year: '年', quarter: '季', month: '月', week: '周', date: '日' }[grain] || grain), key, money(target), money(done), rate, locked.has(`${grain}:${key}`) ? '是' : '否']
        .forEach((value, index) => { const cell = row.insertCell(); cell.textContent = value; if (index > 1) cell.className = 'num'; });
      return row;
    }));
    if (!rows.length) levels.innerHTML = '<tr><td colspan="6">暂无目标数据</td></tr>';
  }

  function configurePeriodPicker() {
    if (!periodPicker || !adjustForm) return;
    const type = adjustForm.elements.period_type.value;
    const inputType = { date: 'date', week: 'week', month: 'month' }[type] || 'text';
    periodPicker.type = inputType;
    periodPicker.placeholder = inputType === 'text' ? (type === 'quarter' ? 'YYYY-Qn，例如 2026-Q3' : 'YYYY，例如 2026') : '';
    periodPicker.pattern = type === 'quarter' ? '\\d{4}-Q[1-4]' : type === 'year' ? '\\d{4}' : '';
    periodPicker.value = '';
  }

  function prepareMonthAdjustment(month) {
    if (!adjustForm || !current) return;
    adjustForm.elements.period_type.value = 'month';
    configurePeriodPicker();
    periodPicker.value = month.period_key;
    adjustForm.elements.target_amount.value = Number(month.target_amount).toFixed(2);
    adjustForm.scrollIntoView({ behavior: 'smooth', block: 'center' });
    adjustForm.elements.target_amount.focus();
  }

  async function loadSettings() {
    try {
      const response = await DemoApi.domainRequest('/api/settings');
      settings = { ...settings, ...(response.data || {}) };
    } catch (error) {
      setStatus(`设置默认值加载失败，已使用页面默认值：${error.message}`);
    }
    form.elements.growth_multiplier.value = settings.growth_multiplier || 1.1;
    if (!form.elements.annual_target.value && Number(settings.annual_target_default) > 0) form.elements.annual_target.value = settings.annual_target_default;
    renderSettingsSummary();
  }

  async function load(year) {
    const token = ++loadToken;
    setAdjustEnabled(false);
    renderDataState('loading');
    try {
      const response = await DemoApi.domainRequest(`/api/goals/${year}`);
      if (token !== loadToken) return;
      current = response.data;
      goalCapabilities = response.capabilities || {};
      const periodResponse = await DemoApi.domainRequest(`/api/goals/${year}/periods`);
      if (token !== loadToken) return;
      const availability = response.availability || periodResponse.availability || 'available';
      if (availability !== 'available') renderDataState(availability, { message: '部分目标数据不可用，请检查目标来源和周期配置。' });
      renderLevels(periodResponse.data);
      const locked = new Set(current.locks.filter((item) => item.period_type === 'month').map((item) => item.period_key));
      months.replaceChildren(...periodResponse.data.months.map((month) => {
        const row = document.createElement('tr');
        row.innerHTML = `<td>${month.period_key}</td><td class="num">${money(month.target_amount)}</td>`;
        const cell = row.insertCell();
        if (locked.has(month.period_key)) {
          const badge = document.createElement('span'); badge.className = 'badge badge--muted'; badge.textContent = '已锁定'; cell.appendChild(badge);
        } else {
          const actions = document.createElement('div'); actions.className = 'goals-month-actions';
          const editButton = document.createElement('button'); editButton.className = 'button button--ghost'; editButton.type = 'button'; editButton.textContent = '调整'; editButton.addEventListener('click', () => prepareMonthAdjustment(month));
          const lockButton = document.createElement('button'); lockButton.className = 'button button--ghost'; lockButton.type = 'button'; lockButton.textContent = '锁定'; lockButton.addEventListener('click', () => lockMonth(month.period_key));
          actions.append(editButton, lockButton); cell.appendChild(actions);
        }
        return row;
      }));
      versionLabel.textContent = `版本 ${current.version}，年度合计 ¥${money(current.annual_total)}`;
      form.elements.annual_target.value = current.annual_total;
      setAdjustEnabled(true);
      if (availability === 'available') setStatus('');
    } catch (error) {
      if (token !== loadToken) return;
      current = null; goalCapabilities = {};
      months.innerHTML = '<tr><td colspan="3">该年度尚未创建目标</td></tr>';
      levels.innerHTML = '<tr><td colspan="6">生成年度目标后显示周期目标</td></tr>';
      versionLabel.textContent = '该年度尚未创建目标';
      renderDataState(error.status === 404 ? 'no-data' : 'calculation-failed', {
        message: error.message || '目标加载失败',
        retry: () => load(Number(form.elements.year.value)),
      });
    }
  }

  async function lockMonth(periodKey) {
    if (!current) return;
    if (Object.keys(goalCapabilities).length && !DemoApi.can({ capabilities: goalCapabilities }, 'can_lock')) { setStatus('当前目标不允许锁定'); return; }
    try {
      await DemoApi.domainRequest(`/api/goals/${current.year}/locks`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ version: current.version, period_type: 'month', period_key: periodKey }) });
      await load(current.year);
    } catch (error) { setStatus(error.message); }
  }

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (Object.keys(goalCapabilities).length && !DemoApi.can({ capabilities: goalCapabilities }, 'can_edit')) { setStatus('当前目标不允许修改'); return; }
    const data = new FormData(form);
    const payload = { year: Number(data.get('year')), annual_target: Number(data.get('annual_target')), growth_multiplier: Number(data.get('growth_multiplier')), operator: '运营人员', reason: '按年度配置生成目标' };
    if (current?.year === payload.year) payload.version = current.version;
    try {
      const response = await DemoApi.domainRequest('/api/goals', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
      setStatus(`已生成版本 ${response.data.version}，按去年同期销售占比拆解到日`);
      await load(payload.year);
    } catch (error) { setStatus(error.message); }
  });

  suggestButton?.addEventListener('click', async () => {
    try {
      const year = Number(form.elements.year.value);
      const multiplier = Number(form.elements.growth_multiplier.value);
      const response = await DemoApi.domainRequest(`/api/goals/${year}/suggestion?growth_multiplier=${multiplier}`);
      form.elements.suggested_annual_target.value = Number(response.data.suggested_annual_target).toFixed(2);
      form.elements.annual_target.value = response.data.suggested_annual_target;
      if (suggestionSource) suggestionSource.textContent = `去年净销售额 ¥${money(response.data.prior_year_net_sales)} × ${multiplier.toFixed(2)} 倍`;
      setStatus('建议值已带入年度目标，请确认后生成');
    } catch (error) { setStatus(error.message); }
  });

  adjustForm?.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (!current) { setStatus('请先生成该年度目标'); return; }
    if (Object.keys(goalCapabilities).length && !DemoApi.can({ capabilities: goalCapabilities }, 'can_edit')) { setStatus('当前目标不允许调整'); return; }
    const data = new FormData(adjustForm);
    try {
      const response = await DemoApi.domainRequest(`/api/goals/${current.year}/adjustments`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ version: current.version, period_type: data.get('period_type'), period_key: data.get('period_key'), target_amount: Number(data.get('target_amount')), operator: data.get('operator'), reason: data.get('reason'), lock: data.get('lock') === 'on' }) });
      setStatus(`调整已保存，版本 ${response.data.version}`);
      await load(current.year);
    } catch (error) { setStatus(error.message); }
  });

  form.elements.year.addEventListener('change', () => load(Number(form.elements.year.value)));
  levelFilter?.addEventListener('change', () => { if (current) load(current.year); });
  adjustForm?.elements.period_type.addEventListener('change', configurePeriodPicker);
  configurePeriodPicker();
  setAdjustEnabled(false);
  loadSettings().finally(() => load(Number(form.elements.year.value)));
})();
