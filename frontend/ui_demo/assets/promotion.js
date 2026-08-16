(() => {
  const views = ['products', 'keywords', 'audience', 'creative', 'content'];
  const viewLabels = { products: '推广商品', keywords: '投放关键词', audience: '人群分析', creative: '创意分析', content: '内容与地域' };
  const fieldCatalogs = {
    products: { subject: '商品主体', spend: '花费', revenue: '成交金额', roi: 'ROI', ctr: '点击率' },
    keywords: { keyword: '词 / 词包', spend: '花费', revenue: '成交金额', roi: 'ROI', action: '动作建议' },
    audience: { audience: '人群', spend: '花费', revenue: '成交金额', roi: 'ROI', action: '建议' },
    creative: { creative: '创意', spend: '花费', revenue: '成交金额', roi: 'ROI', ctr: '点击率' },
    content: { dimension: '内容 / 地域', type: '类型', spend: '花费', revenue: '成交金额', roi: 'ROI' },
  };
  const systemTemplates = {
    products: [template('product-diagnosis', '商品诊断', ['subject', 'spend', 'revenue', 'roi', 'ctr']), template('product-efficiency', '投产效率', ['subject', 'spend', 'roi']), template('product-transaction', '成交表现', ['subject', 'revenue', 'roi'])],
    keywords: [template('keyword-diagnosis', '词效诊断', ['keyword', 'spend', 'revenue', 'roi', 'action']), template('keyword-cost', '成本控制', ['keyword', 'spend', 'roi', 'action']), template('keyword-result', '成交结果', ['keyword', 'revenue', 'roi'])],
    audience: [template('audience-efficiency', '人群效率', ['audience', 'spend', 'revenue', 'roi', 'action']), template('audience-budget', '预算分配', ['audience', 'spend', 'roi']), template('audience-result', '成交贡献', ['audience', 'revenue', 'roi'])],
    creative: [template('creative-diagnosis', '素材诊断', ['creative', 'spend', 'revenue', 'roi', 'ctr']), template('creative-click', '点击表现', ['creative', 'ctr', 'spend']), template('creative-result', '成交表现', ['creative', 'revenue', 'roi'])],
    content: [template('content-region', '地域效率', ['dimension', 'type', 'spend', 'revenue', 'roi']), template('content-cost', '消耗分布', ['dimension', 'type', 'spend']), template('content-result', '成交贡献', ['dimension', 'type', 'revenue', 'roi'])],
  };
  const storageKey = 'demo_promotion_field_templates';
  const state = {
    activeView: 'products',
    dialogView: 'products',
    activeTemplate: Object.fromEntries(views.map((view) => [view, systemTemplates[view][0].id])),
    selectedFields: Object.fromEntries(views.map((view) => [view, [...systemTemplates[view][0].fields]])),
    customTemplates: loadJson(storageKey, Object.fromEntries(views.map((view) => [view, []]))),
  };

  function template(id, name, fields) { return { id, name, fields, system: true }; }
  function loadJson(key, fallback) { try { return JSON.parse(localStorage.getItem(key)) || fallback; } catch { return fallback; } }
  function saveFieldTemplates() { localStorage.setItem(storageKey, JSON.stringify(state.customTemplates)); }
  function allTemplates(view) { return [...systemTemplates[view], ...(state.customTemplates[view] || [])]; }
  function currentTemplate(view) { return allTemplates(view).find((item) => item.id === state.activeTemplate[view]); }
  function toast(message) {
    const node = document.querySelector('[data-promotion-toast]');
    node.textContent = message;
    node.classList.add('is-visible');
    clearTimeout(toast.timer);
    toast.timer = setTimeout(() => node.classList.remove('is-visible'), 2200);
  }
  function applyFields(view, fields, name) {
    const panel = document.querySelector(`[data-promotion-view="${view}"]`);
    if (!panel) return;
    panel.querySelectorAll('[data-field]').forEach((cell) => { cell.hidden = !fields.includes(cell.dataset.field); });
    const bar = panel.querySelector('[data-promotion-template-scope]');
    bar.querySelector('[data-active-field-template]').textContent = name;
    bar.querySelector('[data-visible-field-count]').textContent = `${fields.length} 个字段`;
    state.selectedFields[view] = [...fields];
  }
  function renderTemplateSelect(view) {
    const bar = document.querySelector(`[data-promotion-template-scope="${view}"]`);
    if (!bar) return;
    const select = bar.querySelector('[data-field-template-select]');
    select.innerHTML = allTemplates(view).map((item) => `<option value="${item.id}"${item.id === state.activeTemplate[view] ? ' selected' : ''}>${item.system ? '推荐 · ' : '我的 · '}${escapeHtml(item.name)}</option>`).join('');
  }
  function renderFieldDialog(view) {
    state.dialogView = view;
    const dialog = document.querySelector('[data-promotion-field-dialog]');
    dialog.querySelector('[data-field-dialog-scope-label]').textContent = `${viewLabels[view]} · 模板仅保存在当前视图`;
    dialog.querySelector('[data-promotion-field-options]').innerHTML = `<div class="field-group"><strong>可显示字段</strong>${Object.entries(fieldCatalogs[view]).map(([key, label]) => `<label><input type="checkbox" data-promotion-field-key="${key}"${state.selectedFields[view].includes(key) ? ' checked' : ''}>${label}</label>`).join('')}</div>`;
    const custom = state.customTemplates[view] || [];
    dialog.querySelector('[data-promotion-saved-templates]').innerHTML = custom.length ? custom.map((item) => `<span class="template-pill"><button type="button" data-use-promotion-template="${item.id}">${escapeHtml(item.name)}</button><button type="button" data-delete-promotion-template="${item.id}" aria-label="删除 ${escapeHtml(item.name)}"><i data-lucide="x"></i></button></span>`).join('') : '<span class="panel__hint">当前视图暂无自定义模板</span>';
    window.lucide?.createIcons();
  }
  function selectedDialogFields() { return [...document.querySelectorAll('[data-promotion-field-key]:checked')].map((item) => item.dataset.promotionFieldKey); }
  function bindFieldTemplates() {
    views.forEach((view) => {
      renderTemplateSelect(view);
      const first = systemTemplates[view][0];
      applyFields(view, first.fields, first.name);
    });
    document.querySelectorAll('[data-field-template-select]').forEach((select) => select.addEventListener('change', () => {
      const view = select.closest('[data-promotion-template-scope]').dataset.promotionTemplateScope;
      const chosen = allTemplates(view).find((item) => item.id === select.value);
      state.activeTemplate[view] = chosen.id;
      applyFields(view, chosen.fields, chosen.name);
    }));
    const dialog = document.querySelector('[data-promotion-field-dialog]');
    document.querySelectorAll('[data-manage-field-template]').forEach((button) => button.addEventListener('click', () => {
      const view = button.closest('[data-promotion-template-scope]').dataset.promotionTemplateScope;
      renderFieldDialog(view);
      dialog.showModal();
    }));
    document.querySelectorAll('[data-close-field-dialog]').forEach((button) => button.addEventListener('click', () => dialog.close()));
    dialog.querySelector('[data-apply-promotion-fields]').addEventListener('click', () => {
      const fields = selectedDialogFields();
      if (!fields.length) return toast('至少保留一个字段');
      state.activeTemplate[state.dialogView] = 'custom-selection';
      applyFields(state.dialogView, fields, '临时自定义');
      renderTemplateSelect(state.dialogView);
      dialog.close();
      toast(`已应用到${viewLabels[state.dialogView]}`);
    });
    dialog.querySelector('[data-save-promotion-template]').addEventListener('click', () => {
      const input = dialog.querySelector('[data-promotion-template-name]');
      const name = input.value.trim();
      const fields = selectedDialogFields();
      if (!name) return toast('请输入模板名称');
      if (!fields.length) return toast('至少保留一个字段');
      if (allTemplates(state.dialogView).some((item) => item.name === name)) return toast('当前视图已存在同名模板');
      const item = { id: uid(), name, fields, system: false };
      state.customTemplates[state.dialogView].push(item);
      state.activeTemplate[state.dialogView] = item.id;
      saveFieldTemplates();
      applyFields(state.dialogView, fields, name);
      renderTemplateSelect(state.dialogView);
      renderFieldDialog(state.dialogView);
      input.value = '';
      toast('字段模板已保存');
    });
    dialog.addEventListener('click', (event) => {
      const use = event.target.closest('[data-use-promotion-template]');
      if (use) {
        const item = allTemplates(state.dialogView).find((entry) => entry.id === use.dataset.usePromotionTemplate);
        state.activeTemplate[state.dialogView] = item.id;
        applyFields(state.dialogView, item.fields, item.name);
        renderTemplateSelect(state.dialogView);
        renderFieldDialog(state.dialogView);
      }
      const remove = event.target.closest('[data-delete-promotion-template]');
      if (remove && window.confirm('删除这个字段模板？')) {
        state.customTemplates[state.dialogView] = state.customTemplates[state.dialogView].filter((item) => item.id !== remove.dataset.deletePromotionTemplate);
        saveFieldTemplates();
        renderTemplateSelect(state.dialogView);
        renderFieldDialog(state.dialogView);
        toast('字段模板已删除');
      }
    });
  }

  const operatorLabels = { lt: '<', lte: '≤', gt: '>', gte: '≥', eq: '=', neq: '≠', between: '介于' };
  const alertFields = {
    roi: { label: '推广 ROI', type: 'number' }, spend: { label: '推广花费', type: 'currency' }, impressions: { label: '展现量', type: 'integer' }, clicks: { label: '点击量', type: 'integer' }, ctr: { label: '点击率', type: 'percent' }, cpc: { label: '平均点击花费', type: 'currency' }, transactionAmount: { label: '推广成交金额', type: 'currency' }, transactionCount: { label: '推广成交笔数', type: 'integer' }, conversionRate: { label: '商品支付转化率', type: 'percent' },
  };
  const operators = Object.keys(operatorLabels);
  const createCondition = (field = 'roi', operator = 'lt', value = '') => ({ id: uid(), type: 'condition', field, operator, value: String(value), secondValue: '' });
  const createGroup = (logic = 'and', children = [createCondition()]) => ({ id: uid(), type: 'group', logic, children });
  const presets = {
    'low-efficiency': () => createGroup('and', [createCondition('spend', 'gt', 1000), createCondition('roi', 'lt', 3)]),
    'click-no-conversion': () => createGroup('and', [createCondition('clicks', 'gt', 500), createCondition('conversionRate', 'lt', 2)]),
    'spend-no-order': () => createGroup('and', [createCondition('spend', 'gt', 1000), createCondition('transactionCount', 'eq', 0)]),
    'low-impression': () => createGroup('and', [createCondition('impressions', 'lt', 1000)]),
    'click-anomaly': () => { const condition = createCondition('ctr', 'between', 1); condition.secondValue = '12'; return createGroup('or', [condition, createCondition('clicks', 'gt', 5000)]); },
  };
  let ruleRoot = createGroup('and', [createCondition('roi', 'lt', 3), createGroup('or', [createCondition('clicks', 'gt', 500), createCondition('spend', 'gt', 1000)])]);
  let alertTemplates = loadJson('demo_promotion_alert_templates', []);

  function findNode(node, id) { if (node.id === id) return node; for (const child of node.children || []) { const found = findNode(child, id); if (found) return found; } return null; }
  function removeNode(node, id) { if (!node.children) return false; const index = node.children.findIndex((child) => child.id === id); if (index >= 0) { node.children.splice(index, 1); return true; } return node.children.some((child) => child.type === 'group' && removeNode(child, id)); }
  function renderCondition(condition) {
    const between = condition.operator === 'between';
    return `<div class="rule-condition" data-rule-condition="${condition.id}"><select class="select" data-rule-field aria-label="选择指标">${Object.entries(alertFields).map(([key, meta]) => `<option value="${key}"${key === condition.field ? ' selected' : ''}>${meta.label}</option>`).join('')}</select><select class="select" data-rule-operator aria-label="选择运算符">${operators.map((key) => `<option value="${key}"${key === condition.operator ? ' selected' : ''}>${operatorLabels[key]}</option>`).join('')}</select><input class="input" type="number" step="any" data-rule-value value="${escapeHtml(condition.value)}" aria-label="条件值"><input class="input" type="number" step="any" data-rule-second-value value="${escapeHtml(condition.secondValue)}" aria-label="区间结束值"${between ? '' : ' hidden'}><button class="button button--ghost rule-icon-button" type="button" data-delete-rule-node="${condition.id}" aria-label="删除条件"><i data-lucide="trash-2"></i></button></div>`;
  }
  function renderGroup(group, depth = 0) {
    return `<div class="rule-group" data-rule-group data-rule-group-id="${group.id}" style="--rule-depth:${depth}"><div class="rule-group__header"><div class="segmented" aria-label="条件组逻辑"><button type="button" data-rule-logic="and" aria-pressed="${group.logic === 'and'}">AND</button><button type="button" data-rule-logic="or" aria-pressed="${group.logic === 'or'}">OR</button></div>${depth ? `<button class="button button--ghost rule-icon-button" type="button" data-delete-rule-node="${group.id}" aria-label="删除条件组"><i data-lucide="trash-2"></i></button>` : ''}</div><div class="rule-group__children">${group.children.map((child) => child.type === 'group' ? renderGroup(child, depth + 1) : renderCondition(child)).join('')}</div><div class="rule-group__actions"><button class="button button--ghost" type="button" data-add-rule-condition><i data-lucide="plus"></i>条件</button><button class="button button--ghost" type="button" data-add-rule-group><i data-lucide="brackets"></i>条件组</button></div></div>`;
  }
  function summary(node) {
    if (node.type === 'condition') {
      const value = node.operator === 'between' ? `${node.value}~${node.secondValue}` : node.value || '?';
      return `${alertFields[node.field].label} ${operatorLabels[node.operator]} ${value}`;
    }
    return `${node === ruleRoot ? '' : '('}${node.children.map(summary).join(` ${node.logic.toUpperCase()} `)}${node === ruleRoot ? '' : ')'}`;
  }
  function validCondition(node) { return node.type === 'group' ? node.children.length > 0 && node.children.every(validCondition) : node.value !== '' && Number.isFinite(Number(node.value)) && (node.operator !== 'between' || (node.secondValue !== '' && Number.isFinite(Number(node.secondValue)))); }
  function renderRuleBuilder() {
    document.querySelector('[data-rule-builder]').innerHTML = renderGroup(ruleRoot);
    document.querySelector('[data-rule-summary]').textContent = summary(ruleRoot);
    const save = document.querySelector('[data-save-promotion-alert]');
    save.disabled = !validCondition(ruleRoot) || !document.querySelector('[data-alert-name]').value.trim();
    window.lucide?.createIcons();
  }
  function renderSavedAlerts() {
    const node = document.querySelector('[data-saved-alert-templates]');
    node.innerHTML = alertTemplates.length ? alertTemplates.map((item) => `<span class="template-pill"><button type="button" data-use-alert-template="${item.id}">${escapeHtml(item.name)}</button><button type="button" data-delete-alert-template="${item.id}" aria-label="删除 ${escapeHtml(item.name)}"><i data-lucide="x"></i></button></span>`).join('') : '<span class="panel__hint">暂无自定义预警模板</span>';
    window.lucide?.createIcons();
  }
  function bindAlertBuilder() {
    const builder = document.querySelector('[data-rule-builder]');
    builder.addEventListener('click', (event) => {
      const groupElement = event.target.closest('[data-rule-group-id]');
      const group = groupElement ? findNode(ruleRoot, groupElement.dataset.ruleGroupId) : null;
      const logic = event.target.closest('[data-rule-logic]');
      if (logic && group) group.logic = logic.dataset.ruleLogic;
      if (event.target.closest('[data-add-rule-condition]') && group) group.children.push(createCondition());
      if (event.target.closest('[data-add-rule-group]') && group) group.children.push(createGroup('and'));
      const remove = event.target.closest('[data-delete-rule-node]');
      if (remove) { removeNode(ruleRoot, remove.dataset.deleteRuleNode); if (!ruleRoot.children.length) ruleRoot.children.push(createCondition()); }
      renderRuleBuilder();
    });
    builder.addEventListener('input', (event) => {
      const row = event.target.closest('[data-rule-condition]');
      if (!row) return;
      const condition = findNode(ruleRoot, row.dataset.ruleCondition);
      if (event.target.matches('[data-rule-field]')) condition.field = event.target.value;
      if (event.target.matches('[data-rule-operator]')) condition.operator = event.target.value;
      if (event.target.matches('[data-rule-value]')) condition.value = event.target.value;
      if (event.target.matches('[data-rule-second-value]')) condition.secondValue = event.target.value;
      if (event.target.matches('select')) renderRuleBuilder(); else { document.querySelector('[data-rule-summary]').textContent = summary(ruleRoot); document.querySelector('[data-save-promotion-alert]').disabled = !validCondition(ruleRoot) || !document.querySelector('[data-alert-name]').value.trim(); }
    });
    document.querySelector('[data-alert-name]').addEventListener('input', renderRuleBuilder);
    document.querySelectorAll('[data-alert-preset]').forEach((button) => button.addEventListener('click', () => { ruleRoot = presets[button.dataset.alertPreset](); renderRuleBuilder(); toast(`已载入「${button.textContent}」`); }));
    document.querySelector('[data-save-alert-template]').addEventListener('click', () => {
      const input = document.querySelector('[data-alert-template-name]');
      const name = input.value.trim();
      if (!name) return toast('请输入预警模板名称');
      if (!validCondition(ruleRoot)) return toast('请先完成所有条件');
      if (alertTemplates.some((item) => item.name === name)) return toast('已存在同名预警模板');
      alertTemplates.push({ id: uid(), name, rule: structuredClone(ruleRoot) });
      localStorage.setItem('demo_promotion_alert_templates', JSON.stringify(alertTemplates));
      input.value = '';
      renderSavedAlerts();
      toast('预警模板已保存');
    });
    document.querySelector('[data-saved-alert-templates]').addEventListener('click', (event) => {
      const use = event.target.closest('[data-use-alert-template]');
      if (use) { ruleRoot = structuredClone(alertTemplates.find((item) => item.id === use.dataset.useAlertTemplate).rule); renderRuleBuilder(); toast('已载入自定义预警模板'); }
      const remove = event.target.closest('[data-delete-alert-template]');
      if (remove && window.confirm('删除这个预警模板？')) { alertTemplates = alertTemplates.filter((item) => item.id !== remove.dataset.deleteAlertTemplate); localStorage.setItem('demo_promotion_alert_templates', JSON.stringify(alertTemplates)); renderSavedAlerts(); toast('预警模板已删除'); }
    });
    document.querySelector('[data-save-promotion-alert]').addEventListener('click', () => {
      if (!validCondition(ruleRoot)) { document.querySelector('[data-rule-value][value=""]')?.focus(); return; }
      closeDrawer();
      toast('预警规则已保存并启用');
    });
    renderRuleBuilder();
    renderSavedAlerts();
  }

  const drawer = document.querySelector('[data-promotion-drawer]');
  const backdrop = document.querySelector('[data-promotion-backdrop]');
  function openDrawer() { drawer.classList.add('is-open'); backdrop.classList.add('is-open'); }
  function closeDrawer() { drawer.classList.remove('is-open'); backdrop.classList.remove('is-open'); }
  function bindDrawer() {
    document.querySelectorAll('[data-open-promotion-drawer]').forEach((button) => button.addEventListener('click', openDrawer));
    document.querySelectorAll('[data-close-promotion-drawer]').forEach((button) => button.addEventListener('click', closeDrawer));
    backdrop.addEventListener('click', closeDrawer);
  }
  function uid() { return globalThis.crypto?.randomUUID?.() || `id-${Date.now()}-${Math.random().toString(16).slice(2)}`; }
  function escapeHtml(value) { return String(value).replace(/[&<>'"]/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' })[char]); }

  window.addEventListener('load', () => {
    bindFieldTemplates();
    bindAlertBuilder();
    bindDrawer();
  });
})();
