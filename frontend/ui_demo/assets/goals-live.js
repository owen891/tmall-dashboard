(function () {
  const form = document.querySelector('[data-goals-form]');
  const adjustForm = document.querySelector('[data-goals-adjust-form]');
  const status = document.querySelector('[data-goals-status]');
  const renderDataState = (state, details) => DemoApi.renderDataState(status, state, details);
  const months = document.querySelector('[data-goals-months]');
  const levels = document.querySelector('[data-goals-levels]');
  const versionLabel = document.querySelector('[data-goals-version]');
  const suggestButton = document.querySelector('[data-goals-suggest]');
  const levelFilter = document.querySelector('[data-goals-level-filter]');
  const periodPicker = document.querySelector('[data-goals-period-picker]');
  let current = null;
  let goalCapabilities = {};
  let loadToken = 0;

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
      [({year:'年',quarter:'季',month:'月',week:'周',date:'日'}[grain] || grain), key, Number(target).toFixed(2), done.toFixed(2), rate, locked.has(`${grain}:${key}`) ? '是' : '否'].forEach((value, index) => { const cell = row.insertCell(); cell.textContent = value; if (index > 1) cell.className = 'num'; });
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
    periodPicker.value = inputType === 'text' ? '' : periodPicker.value;
  }

  if (adjustForm && !adjustForm.elements.period_type) {
    const label = document.createElement('label');
    label.textContent = '周期';
    const select = document.createElement('select');
    select.className = 'select';
    select.name = 'period_type';
    [['date', '日'], ['week', '周'], ['month', '月'], ['quarter', '季'], ['year', '年']]
      .forEach(([value, text]) => select.add(new Option(text, value)));
    label.appendChild(select);
    adjustForm.prepend(label);
  }

  async function load(year) {
    const token = ++loadToken;
    renderDataState('loading');
    try {
      const response = await DemoApi.domainRequest(`/api/goals/${year}`);
      if (token !== loadToken) return;
      current = response.data;
      goalCapabilities = response.capabilities || {};
      const periodResponse = await DemoApi.domainRequest(`/api/goals/${year}/periods`);
      if (token !== loadToken) return;
      renderLevels(periodResponse.data);
      const locked = new Set(current.locks.filter((item) => item.period_type === 'month').map((item) => item.period_key));
      months.replaceChildren(...periodResponse.data.months.map((month) => {
        const row = document.createElement('tr');
        row.innerHTML = `<td>${month.period_key}</td><td class="num">${Number(month.target_amount).toFixed(2)}</td>`;
        const cell = row.insertCell();
        const button = document.createElement('button');
        button.className = 'button button--ghost'; button.type = 'button';
        button.textContent = locked.has(month.period_key) ? '已锁定' : '锁定';
        button.disabled = locked.has(month.period_key);
        button.addEventListener('click', () => lockMonth(month.period_key));
        cell.appendChild(button); return row;
      }));
      versionLabel.textContent = `版本 ${current.version}，年度合计 ${Number(current.annual_total).toFixed(2)} 元`;
      form.elements.annual_target.value = current.annual_total;
    } catch (error) {
      if (token !== loadToken) return;
      months.innerHTML = '<tr><td colspan="3">该年度尚未创建目标</td></tr>';
      versionLabel.textContent = error.message; current = null; renderDataState('no-data', { message: error.message });
    }
  }

  async function lockMonth(periodKey) {
    if (Object.keys(goalCapabilities).length && !DemoApi.can({ capabilities: goalCapabilities }, 'can_lock')) { status.textContent = '当前目标不允许锁定'; return; }
    try { await DemoApi.domainRequest(`/api/goals/${current.year}/locks`, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({version: current.version, period_type: 'month', period_key: periodKey})}); await load(current.year); }
    catch (error) { status.textContent = error.message; }
  }

  form.addEventListener('submit', async (event) => {
    event.preventDefault(); if (Object.keys(goalCapabilities).length && !DemoApi.can({ capabilities: goalCapabilities }, 'can_edit')) { status.textContent = '当前目标不允许修改'; return; } const data = new FormData(form);
    const payload = {year: Number(data.get('year')), annual_target: Number(data.get('annual_target')), growth_multiplier: Number(data.get('growth_multiplier'))};
    if (current?.year === payload.year) payload.version = current.version;
    try { const response = await DemoApi.domainRequest('/api/goals', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)}); status.textContent = `已生成版本 ${response.data.version} 的日目标`; await load(payload.year); }
    catch (error) { status.textContent = error.message; }
  });

  suggestButton?.addEventListener('click', async () => {
    try {
      const year = Number(form.elements.year.value);
      const multiplier = Number(form.elements.growth_multiplier.value);
      const response = await DemoApi.domainRequest(`/api/goals/${year}/suggestion?growth_multiplier=${multiplier}`);
      form.elements.suggested_annual_target.value = Number(response.data.suggested_annual_target).toFixed(2);
      form.elements.annual_target.value = response.data.suggested_annual_target;
      status.textContent = `去年净销售额 ${Number(response.data.prior_year_net_sales).toFixed(2)}，已生成建议目标`;
    } catch (error) { status.textContent = error.message; }
  });

  adjustForm?.addEventListener('submit', async (event) => {
    event.preventDefault(); if (!current) return; if (Object.keys(goalCapabilities).length && !DemoApi.can({ capabilities: goalCapabilities }, 'can_edit')) { status.textContent = '当前目标不允许调整'; return; } const data = new FormData(adjustForm);
    try { const response = await DemoApi.domainRequest(`/api/goals/${current.year}/adjustments`, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({version: current.version, period_type: data.get('period_type') || 'date', period_key: data.get('period_key'), target_amount: Number(data.get('target_amount')), operator: data.get('operator'), reason: data.get('reason'), lock: data.get('lock') === 'on'})}); status.textContent = `调整已保存，版本 ${response.data.version}`; await load(current.year); }
    catch (error) { status.textContent = error.message; }
  });

  form.elements.year.addEventListener('change', () => load(Number(form.elements.year.value)));
  levelFilter?.addEventListener('change', () => { if (current) load(current.year); });
  adjustForm?.elements.period_type.addEventListener('change', configurePeriodPicker);
  configurePeriodPicker();
  load(Number(form.elements.year.value));
})();
