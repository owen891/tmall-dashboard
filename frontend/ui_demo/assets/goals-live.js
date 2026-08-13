(function () {
  const form = document.querySelector('[data-goals-form]');
  const adjustForm = document.querySelector('[data-goals-adjust-form]');
  const status = document.querySelector('[data-goals-status]');
  const months = document.querySelector('[data-goals-months]');
  const levels = document.querySelector('[data-goals-levels]');
  const versionLabel = document.querySelector('[data-goals-version]');
  let current = null;

  function renderLevels(payload) {
    if (!levels) return;
    const actual = payload.actual || {};
    const locked = new Set((current?.locks || []).map((item) => `${item.period_type}:${item.period_key}`));
    const rows = Object.entries(payload.levels || {}).flatMap(([grain, values]) => grain === 'year'
      ? [[grain, String(payload.year), values]]
      : Object.entries(values).map(([key, amount]) => [grain, key, amount]));
    levels.replaceChildren(...rows.map(([grain, key, target]) => {
      const row = document.createElement('tr');
      const done = grain === 'year' ? Number(actual?.year || 0) : Number(actual?.[grain]?.[key] || 0);
      const rate = Number(target) ? `${(done / Number(target) * 100).toFixed(1)}%` : '--';
      [({year:'年',quarter:'季',month:'月',week:'周',date:'日'}[grain] || grain), key, Number(target).toFixed(2), done.toFixed(2), rate, locked.has(`${grain}:${key}`) ? '是' : '否'].forEach((value, index) => { const cell = row.insertCell(); cell.textContent = value; if (index > 1) cell.className = 'num'; });
      return row;
    }));
    if (!rows.length) levels.innerHTML = '<tr><td colspan="6">暂无目标数据</td></tr>';
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
    try {
      const response = await DemoApi.domainRequest(`/api/goals/${year}`);
      current = response.data;
      const periodResponse = await DemoApi.domainRequest(`/api/goals/${year}/periods`);
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
      months.innerHTML = '<tr><td colspan="3">该年度尚未创建目标</td></tr>';
      versionLabel.textContent = error.message; current = null;
    }
  }

  async function lockMonth(periodKey) {
    try { await DemoApi.domainRequest(`/api/goals/${current.year}/locks`, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({version: current.version, period_type: 'month', period_key: periodKey})}); await load(current.year); }
    catch (error) { status.textContent = error.message; }
  }

  form.addEventListener('submit', async (event) => {
    event.preventDefault(); const data = new FormData(form);
    const payload = {year: Number(data.get('year')), annual_target: Number(data.get('annual_target'))};
    if (current?.year === payload.year) payload.version = current.version;
    try { const response = await DemoApi.domainRequest('/api/goals', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)}); status.textContent = `已生成版本 ${response.data.version} 的日目标`; await load(payload.year); }
    catch (error) { status.textContent = error.message; }
  });

  adjustForm?.addEventListener('submit', async (event) => {
    event.preventDefault(); if (!current) return; const data = new FormData(adjustForm);
    try { const response = await DemoApi.domainRequest(`/api/goals/${current.year}/adjustments`, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({version: current.version, period_type: data.get('period_type') || 'date', period_key: data.get('period_key'), target_amount: Number(data.get('target_amount')), operator: data.get('operator'), reason: data.get('reason'), lock: data.get('lock') === 'on'})}); status.textContent = `调整已保存，版本 ${response.data.version}`; await load(current.year); }
    catch (error) { status.textContent = error.message; }
  });

  form.elements.year.addEventListener('change', () => load(Number(form.elements.year.value)));
  load(Number(form.elements.year.value));
})();
