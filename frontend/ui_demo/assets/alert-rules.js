(function () {
  const apiPath = '/api/alert-rules';
  const scopeLabels = { store: '店铺', promotion_product: '推广商品' };
  const metricLabels = {
    gmv: '支付金额', net_sales: '净销售额', visitors: '商品访客数', conversion: '商品支付转化率',
    refund_rate: '退款率', roi: '推广 ROI', ad_spend: '推广花费',
    attributed_payment_amount: '推广成交', impressions: '展现量', clicks: '点击量',
    ctr: '点击率', payment_buyers: '支付买家数', cvr: '商品支付转化率', cpc: '平均点击花费',
    direct_payment_amount: '直接付费成交', indirect_payment_amount: '间接付费成交', paid_share: '付费成交占比',
  };
  const metricsByScope = {
    store: ['gmv', 'net_sales', 'visitors', 'conversion', 'refund_rate', 'roi', 'ad_spend'],
    promotion_product: ['roi', 'ad_spend', 'attributed_payment_amount', 'impressions', 'clicks', 'ctr', 'payment_buyers', 'cvr', 'cpc', 'direct_payment_amount', 'indirect_payment_amount', 'paid_share'],
  };
  const operatorLabels = { gt: '大于', lt: '小于', gte: '大于等于', lte: '小于等于' };
  const levelLabels = { info: '提示', warning: '警告', danger: '严重' };
  const roots = [...document.querySelectorAll('[data-alert-rules-root]')];
  let dialog = null;
  let form = null;
  let returnFocus = null;
  let editingId = null;

  function createDialog() {
    dialog = document.createElement('dialog');
    dialog.className = 'modal-form alert-rules-dialog';
    dialog.hidden = true;
    dialog.setAttribute('data-modal-kind', 'config');
    dialog.setAttribute('aria-labelledby', 'alertRuleDialogTitle');
    dialog.innerHTML = `
      <form method="dialog" data-alert-rule-form>
        <div class="modal-form__header"><div><h3 id="alertRuleDialogTitle">预警规则</h3><p class="panel__hint">保存后立即影响对应业务页面。</p></div><button class="button button--ghost" type="button" data-alert-rule-close aria-label="关闭预警规则"><i data-lucide="x"></i></button></div>
        <div class="modal-form__body alert-rule-grid">
          <label>规则名称<input class="input" name="name" required maxlength="60"></label>
          <label>作用域<select class="select" name="scope" required><option value="store">店铺</option><option value="promotion_product">推广商品</option></select></label>
          <label>指标<select class="select" name="metric" required></select></label>
          <label>运算符<select class="select" name="operator" required><option value="lt">小于</option><option value="lte">小于等于</option><option value="gt">大于</option><option value="gte">大于等于</option></select></label>
          <label>阈值<input class="input" name="threshold" type="number" step="any" required></label>
          <label>级别<select class="select" name="level" required><option value="warning">警告</option><option value="danger">严重</option><option value="info">提示</option></select></label>
          <label class="alert-rule-enabled"><input name="enabled" type="checkbox" checked>启用规则</label>
          <p class="modal-form__status" data-alert-rule-status role="status"></p>
        </div>
        <div class="modal-form__footer"><button class="button" type="button" data-alert-rule-close>取消</button><button class="button button--primary" type="submit"><i data-lucide="save"></i>保存规则</button></div>
      </form>`;
    document.body.appendChild(dialog);
    form = dialog.querySelector('[data-alert-rule-form]');
    form.elements.scope.addEventListener('change', renderMetricOptions);
    form.addEventListener('submit', saveRule);
    dialog.querySelectorAll('[data-alert-rule-close]').forEach((button) => button.addEventListener('click', closeDialog));
    dialog.addEventListener('cancel', (event) => { event.preventDefault(); closeDialog(); });
    dialog.addEventListener('close', () => { dialog.hidden = true; returnFocus?.focus?.(); returnFocus = null; });
  }

  function renderMetricOptions() {
    const scope = form.elements.scope.value;
    const current = form.elements.metric.value;
    form.elements.metric.replaceChildren(...(metricsByScope[scope] || []).map((metric) => new Option(metricLabels[metric] || metric, metric)));
    if ([...form.elements.metric.options].some((option) => option.value === current)) form.elements.metric.value = current;
  }

  function openDialog(trigger, rule = null) {
    if (!dialog) createDialog();
    returnFocus = trigger;
    editingId = rule?.id || null;
    form.reset();
    form.elements.scope.value = rule?.scope || trigger?.dataset.alertRulesScope || 'store';
    renderMetricOptions();
    ['name', 'metric', 'operator', 'threshold', 'level'].forEach((key) => {
      if (rule?.[key] !== undefined) form.elements[key].value = rule[key];
    });
    form.elements.enabled.checked = rule?.enabled !== false;
    dialog.querySelector('[data-alert-rule-status]').textContent = '';
    dialog.hidden = false;
    dialog.showModal();
    window.lucide?.createIcons();
    window.setTimeout(() => form.elements.name.focus(), 0);
  }

  function closeDialog() {
    if (dialog?.open) dialog.close();
  }

  async function saveRule(event) {
    event.preventDefault();
    const data = new FormData(form);
    const payload = {
      name: data.get('name'), scope: data.get('scope'), metric: data.get('metric'),
      operator: data.get('operator'), threshold: Number(data.get('threshold')),
      level: data.get('level'), enabled: form.elements.enabled.checked,
    };
    const submit = form.querySelector('[type="submit"]');
    const status = dialog.querySelector('[data-alert-rule-status]');
    submit.disabled = true;
    status.textContent = '正在保存';
    try {
      await DemoApi.domainRequest(editingId ? `${apiPath}/${editingId}` : apiPath, {
        method: editingId ? 'PUT' : 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
      });
      closeDialog();
      await refreshAll();
      window.dispatchEvent(new CustomEvent('tmall:alert-rules-change', { detail: { scope: payload.scope } }));
    } catch (error) {
      status.textContent = error.message || '规则保存失败';
    } finally {
      submit.disabled = false;
    }
  }

  function ruleRow(rule, root) {
    const row = document.createElement('div');
    row.className = 'alert-rule-row';
    const copy = document.createElement('div');
    const title = document.createElement('strong');
    title.textContent = rule.name;
    const detail = document.createElement('span');
    detail.textContent = `${scopeLabels[rule.scope] || rule.scope} · ${metricLabels[rule.metric] || rule.metric} ${operatorLabels[rule.operator] || rule.operator} ${rule.threshold}`;
    copy.append(title, detail);
    const badges = document.createElement('div');
    badges.className = 'alert-rule-row__actions';
    const level = document.createElement('span');
    level.className = `badge badge--${rule.level === 'danger' ? 'danger' : rule.level === 'warning' ? 'warning' : 'info'}`;
    level.textContent = rule.enabled ? levelLabels[rule.level] : '已停用';
    const edit = document.createElement('button');
    edit.type = 'button'; edit.className = 'button button--ghost'; edit.textContent = '编辑';
    edit.addEventListener('click', () => openDialog(edit, rule));
    const remove = document.createElement('button');
    remove.type = 'button'; remove.className = 'button button--ghost'; remove.textContent = '删除';
    remove.addEventListener('click', async () => {
      if (!window.confirm(`确认删除规则“${rule.name}”？`)) return;
      try {
        await DemoApi.domainRequest(`${apiPath}/${rule.id}`, { method: 'DELETE' });
        await refreshAll();
        window.dispatchEvent(new CustomEvent('tmall:alert-rules-change', { detail: { scope: rule.scope } }));
      } catch (error) {
        const list = root.querySelector('[data-alert-rules-list]');
        list.textContent = error.message || '规则删除失败';
      }
    });
    badges.append(level, edit, remove);
    row.append(copy, badges);
    return row;
  }

  async function renderRoot(root) {
    const list = root.querySelector('[data-alert-rules-list]');
    if (!list) return;
    list.textContent = '正在加载规则';
    try {
      const scope = root.dataset.alertRulesScope;
      const response = await DemoApi.domainRequest(apiPath + (scope ? `?scope=${encodeURIComponent(scope)}` : ''));
      const rules = response.data || [];
      list.replaceChildren(...(rules.length ? rules.map((rule) => ruleRow(rule, root)) : [Object.assign(document.createElement('p'), { className: 'panel__hint', textContent: '暂无预警规则' })]));
    } catch (error) {
      list.replaceChildren();
      const message = document.createElement('p');
      message.className = 'panel__hint';
      message.textContent = error.message || '规则加载失败';
      const retry = document.createElement('button');
      retry.type = 'button';
      retry.className = 'button button--ghost';
      retry.setAttribute('data-alert-rules-retry', 'true');
      retry.textContent = '重试';
      retry.addEventListener('click', () => renderRoot(root));
      list.append(message, retry);
    }
  }

  async function refreshAll() {
    await Promise.all(roots.map(renderRoot));
  }

  document.querySelectorAll('[data-alert-rules-open]').forEach((button) => button.addEventListener('click', () => openDialog(button)));
  refreshAll().then(() => {
    const count = document.querySelectorAll('[data-alert-rules-list] .alert-rule-row').length;
    const summary = document.querySelector('[data-settings-summary="rules"]');
    if (summary) summary.textContent = String(count);
  });
})();
