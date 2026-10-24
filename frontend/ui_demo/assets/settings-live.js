(function () {
  const form = document.querySelector('[data-settings-form]');
  const formPanel = document.querySelector('[data-settings-form-panel]');
  const coreStatus = document.querySelector('[data-settings-status="core"]');
  const templateStatus = document.querySelector('[data-settings-status="templates"]');
  const classificationStatus = document.querySelector('[data-settings-status="classification"]');
  const sourceLabels = { product_day: '商品日度', dmp_product_day: 'DMP 商品日度', store_day: '店铺日度', product_week: '商品周度', product_month: '商品月度', promotion_channel_day: '推广渠道日度', promotion_campaign_day: '推广计划日度', promotion_unit_day: '推广单元日度', promotion_product_day: '推广商品日度', refund_day: '退款日度', customer_day: '新老客日度' };
  const fieldLabels = { date: '日期', product_id: '商品编号', product_name: '商品名称', payment_amount: '支付金额', successful_refund_amount: '成功退款金额', product_visitors: '商品访客数', payment_buyers: '支付买家数', returning_payment_buyers: '复购买家数', ad_spend: '推广花费', channel: '推广渠道', campaign_id: '推广计划', unit_id: '推广单元', attributed_payment_amount: '推广成交' };
  const dictionaryLabels = { tiers: '商品分层', styles: '商品风格', lifecycle_stages: '生命周期', seasonal_attributes: '季节属性' };
  const dictionaryRoot = document.querySelector('[data-classification-dictionaries]');
  const categoryRoot = document.querySelector('[data-category-modes]');
  const templatePanel = document.querySelector('[data-settings-template-panel]');
  const coreSaveButton = form?.querySelector('[data-settings-save="core"]');
  const coreDiscardButton = document.querySelector('[data-settings-discard="core"]');
  const classificationSaveButton = document.querySelector('[data-settings-save="classification"]');
  const classificationDiscardButton = document.querySelector('[data-settings-discard="classification"]');
  const dirtyState = { core: false, templates: false, classification: false };
  const savingState = { core: false, templates: false, classification: false };
  let isDirty = false;
  let saving = false;
  let settingsPayload = { capabilities: {} };
  let coreSnapshot = null;
  let templateSnapshot = null;
  let classificationSnapshot = null;
  const templateDraft = { mapping_templates: {} };
  const classificationDraft = { classification_dictionaries: { tiers: [], styles: [], lifecycle_stages: [], seasonal_attributes: [] }, category_modes: [], category_mode_default: 'sock' };
  const clone = (value) => structuredClone(value);
  const same = (left, right) => JSON.stringify(left) === JSON.stringify(right);
  const anyDirty = () => Object.values(dirtyState).some(Boolean);
  const updateDirtyUi = () => {
    isDirty = anyDirty();
    Object.entries(dirtyState).forEach(([domain, dirty]) => {
      const label = document.querySelector(`[data-settings-dirty="${domain}"]`);
      const bar = document.querySelector(`[data-settings-savebar="${domain}"]`);
      const discard = document.querySelector(`[data-settings-discard="${domain}"]`);
      if (label) label.textContent = dirty ? '有未保存修改' : '已保存';
      if (discard) discard.disabled = !dirty || Boolean(savingState[domain]);
      bar?.classList.toggle('is-dirty', dirty);
    });
    const pill = document.querySelector('[data-settings-save-pill]');
    if (pill) {
      pill.dataset.tone = isDirty ? 'warning' : 'success';
      pill.replaceChildren(document.createElement('i'), document.createTextNode(isDirty ? '未保存' : '已保存'));
      const glyph = pill.querySelector('i');
      if (glyph) { glyph.dataset.lucide = isDirty ? 'pencil' : 'check'; window.lucide?.createIcons(); }
    }
  };
  const setDomainDirty = (domain, value = true) => {
    dirtyState[domain] = Boolean(value);
    updateDirtyUi();
  };
  const setDirty = (value) => setDomainDirty('core', value);
  const markDirty = () => setDirty(true);
  const markTemplateDirty = () => setDomainDirty('templates', true);
  const markClassificationDirty = () => setDomainDirty('classification', true);
  const coreFormValue = () => {
    if (!form) return {};
    const data = new FormData(form);
    return {
      shop_name: data.get('shop_name') || '', timezone: data.get('timezone') || 'Asia/Shanghai',
      currency: data.get('currency') || 'CNY', week_starts_on: data.get('week_starts_on') || 'monday',
      annual_target_default: data.get('annual_target_default') || '', growth_multiplier: data.get('growth_multiplier') || '',
      overachievement_threshold: data.get('overachievement_threshold') || '',
      continuous_days: data.get('continuous_days') || '60', seasonal_months: data.get('seasonal_months') || '12',
    };
  };
  const syncCoreDirty = () => setDirty(!same(coreFormValue(), coreSnapshot));

  const renderCategoryModes = () => {
    if (!categoryRoot) return;
    categoryRoot.replaceChildren(...(classificationDraft.category_modes || []).map((item, index) => {
      const row = document.createElement('div'); row.className = 'settings-category-row';
      const value = document.createElement('input'); value.className = 'input'; value.value = item.value || ''; value.placeholder = '编码'; value.disabled = Boolean(item.system); value.setAttribute('aria-label', '品类编码');
      value.addEventListener('input', () => {
        const previous = item.value;
        item.value = value.value.trim();
        if (classificationDraft.category_mode_default === previous) classificationDraft.category_mode_default = item.value;
        markClassificationDirty();
      });
      const label = document.createElement('input'); label.className = 'input'; label.value = item.label || ''; label.placeholder = '显示名称'; label.setAttribute('aria-label', '品类名称');
      label.addEventListener('input', () => { item.label = label.value; markClassificationDirty(); });
      const mapping = document.createElement('input'); mapping.className = 'input'; mapping.value = item.shop_label || ''; mapping.placeholder = item.value === 'all' ? '不筛选' : '商品标签'; mapping.disabled = item.value === 'all' || item.value === 'sock'; mapping.setAttribute('aria-label', '商品标签映射');
      mapping.addEventListener('input', () => { item.shop_label = mapping.value; markClassificationDirty(); });
      const enabledLabel = document.createElement('label'); enabledLabel.className = 'classification-row__toggle';
      const enabled = document.createElement('input'); enabled.type = 'checkbox'; enabled.checked = item.enabled !== false;
      enabled.addEventListener('change', () => {
        item.enabled = enabled.checked;
        if (!enabled.checked && classificationDraft.category_mode_default === item.value) {
          classificationDraft.category_mode_default = classificationDraft.category_modes.find((candidate) => candidate.enabled !== false && candidate.value !== item.value)?.value || 'all';
        }
        markClassificationDirty(); renderCategoryModes();
      });
      enabledLabel.append(enabled, document.createTextNode('启用'));
      const defaultLabel = document.createElement('label'); defaultLabel.className = 'classification-row__toggle';
      const radio = document.createElement('input'); radio.type = 'radio'; radio.name = 'category_mode_default'; radio.checked = classificationDraft.category_mode_default === item.value; radio.disabled = item.enabled === false;
      radio.addEventListener('change', () => { if (radio.checked) { classificationDraft.category_mode_default = item.value; markClassificationDirty(); renderCategoryModes(); } });
      defaultLabel.append(radio, document.createTextNode('默认'));
      row.append(value, label, mapping, enabledLabel, defaultLabel);
      if (item.system) { const badge = document.createElement('span'); badge.className = 'ui-badge'; badge.textContent = '内置'; row.appendChild(badge); }
      else {
        const remove = document.createElement('button'); remove.type = 'button'; remove.className = 'ui-button ui-button--ghost'; remove.textContent = '移除';
        remove.addEventListener('click', () => { classificationDraft.category_modes.splice(index, 1); if (classificationDraft.category_mode_default === item.value) classificationDraft.category_mode_default = 'all'; markClassificationDirty(); renderCategoryModes(); });
        row.appendChild(remove);
      }
      return row;
    }));
    window.lucide?.createIcons();
  };
  document.querySelector('[data-category-add]')?.addEventListener('click', () => {
    const item = { value: `custom_${Date.now()}`, label: '', shop_label: '', enabled: true, system: false };
    classificationDraft.category_modes.push(item); markClassificationDirty(); renderCategoryModes(); categoryRoot?.lastElementChild?.querySelector('input')?.focus();
  });
  const tabLinks = [...document.querySelectorAll('[data-settings-tab]')];
  const tabPanels = [...document.querySelectorAll('[data-settings-tab-panel]')];
  const SETTINGS_TABS = ['store', 'goals', 'templates', 'classification', 'alerts', 'scans'];
  const FORM_TABS = new Set(['store', 'goals']);
  const HASH_ALIASES = { '#settings-import-scans': 'scans' };
  const tabDomain = (tab) => tab === 'templates' ? 'templates' : tab === 'classification' ? 'classification' : FORM_TABS.has(tab) ? 'core' : null;
  let activeTab = 'store';
  function selectSettingsTab(tab, updateHash = true, force = false) {
    const nextTab = SETTINGS_TABS.includes(tab) ? tab : 'store';
    const domain = tabDomain(activeTab);
    if (!force && nextTab !== activeTab && domain && dirtyState[domain]) {
      const label = domain === 'templates' ? '模板' : domain === 'classification' ? '分类' : '店铺/目标';
      if (!window.confirm(`${label}设置有未保存修改，切换后草稿仍会保留。确定切换吗？`)) return false;
    }
    activeTab = nextTab;
    tabLinks.forEach((link) => {
      const active = link.dataset.settingsTab === activeTab;
      link.setAttribute('aria-current', String(active));
      if (link.tagName === 'BUTTON') link.setAttribute('aria-pressed', String(active));
    });
    tabPanels.forEach((panel) => { panel.hidden = panel.dataset.settingsTabPanel !== activeTab; });
    if (formPanel) formPanel.hidden = !FORM_TABS.has(activeTab);
    if (updateHash) history.replaceState(null, '', `#settings-${activeTab}`);
    return true;
  }
  tabLinks.forEach((link) => link.addEventListener('click', (event) => { event.preventDefault(); selectSettingsTab(link.dataset.settingsTab); }));
  document.querySelectorAll('[data-settings-tab-goto]').forEach((button) => {
    button.addEventListener('click', () => selectSettingsTab(button.dataset.settingsTabGoto));
  });
  document.querySelectorAll('[data-settings-dialog-open]').forEach((button) => {
    button.addEventListener('click', () => {
      document.querySelector(`dialog[data-settings-dialog="${button.dataset.settingsDialogOpen}"]`)?.showModal();
    });
  });
  document.querySelectorAll('[data-settings-dialog-close]').forEach((button) => {
    button.addEventListener('click', () => button.closest('dialog')?.close());
  });
  const initialHash = window.location.hash;
  const initialTab = HASH_ALIASES[initialHash]
    || SETTINGS_TABS.find((name) => initialHash === `#settings-${name}`)
    || (initialHash === '#settings-goals' ? 'goals' : null);
  selectSettingsTab(initialTab || 'store', false, true);
  window.addEventListener('hashchange', () => {
    const requested = HASH_ALIASES[window.location.hash] || SETTINGS_TABS.find((name) => window.location.hash === `#settings-${name}`) || 'store';
    selectSettingsTab(requested, false);
  });
  window.addEventListener('beforeunload', (event) => { if (isDirty) { event.preventDefault(); event.returnValue = ''; } });

  function renderDictionaries() {
    if (!dictionaryRoot) return;
    dictionaryRoot.replaceChildren(...Object.entries(dictionaryLabels).map(([group, title]) => {
      const section = document.createElement('section'); section.className = 'classification-group';
      const heading = document.createElement('div'); heading.className = 'classification-group__header';
      const name = document.createElement('h4'); name.textContent = title;
      const add = document.createElement('button'); add.type = 'button'; add.className = 'ui-button ui-button--ghost'; add.textContent = '新增';
      add.addEventListener('click', () => { classificationDraft.classification_dictionaries[group].push({ value: '', label: '', enabled: true, system: false }); markClassificationDirty(); renderDictionaries(); section.querySelector('.classification-row:last-child input')?.focus(); });
      heading.append(name, add); section.appendChild(heading);
      const rows = document.createElement('div'); rows.className = 'classification-group__rows';
      (classificationDraft.classification_dictionaries[group] || []).forEach((item, index) => {
        const row = document.createElement('div'); row.className = 'classification-row';
        const code = document.createElement('input'); code.className = 'input'; code.value = item.value || ''; code.placeholder = '编码（可留空自动生成）'; code.disabled = Boolean(item.system); code.setAttribute('aria-label', `${title}编码`);
        code.addEventListener('input', () => { item.value = code.value.trim(); markClassificationDirty(); });
        const label = document.createElement('input'); label.className = 'input'; label.value = item.label || ''; label.placeholder = '中文名称'; label.setAttribute('aria-label', `${title}中文名称`); label.addEventListener('input', () => { item.label = label.value; markClassificationDirty(); });
        const enabled = document.createElement('label'); enabled.className = 'classification-row__toggle'; const checkbox = document.createElement('input'); checkbox.type = 'checkbox'; checkbox.checked = item.enabled !== false; checkbox.addEventListener('change', () => { item.enabled = checkbox.checked; markClassificationDirty(); }); enabled.append(checkbox, document.createTextNode('启用'));
        row.append(code, label, enabled);
        if (item.system) { const badge = document.createElement('span'); badge.className = 'ui-badge'; badge.textContent = '内置'; row.appendChild(badge); }
        else { const remove = document.createElement('button'); remove.type = 'button'; remove.className = 'ui-button ui-button--ghost'; remove.textContent = '移除'; remove.addEventListener('click', () => { classificationDraft.classification_dictionaries[group].splice(index, 1); markClassificationDirty(); renderDictionaries(); }); row.appendChild(remove); }
        rows.appendChild(row);
      });
      if (!rows.children.length) { const empty = document.createElement('p'); empty.className = 'panel__hint'; empty.textContent = '暂无分类，点击新增开始维护。'; rows.appendChild(empty); }
      section.appendChild(rows); return section;
    }));
  }
  if (templatePanel) templatePanel.innerHTML = `
    <div class="panel__header"><div><h3 class="panel__title">导入规则</h3><p class="panel__hint">维护手动导入使用的报表字段映射；商品列表字段模板统一在商品运营页管理。</p></div></div>
    <div class="settings-template-grid">
      <div><h4>报表字段映射</h4><div class="filter-group"><select class="select" data-template-source aria-label="报表类型"></select><select class="select" data-template-map-key aria-label="业务字段"></select><input class="input" data-template-map-column placeholder="报表中的列名" aria-label="报表中的列名"><button class="ui-button" type="button" data-template-add-map>添加</button></div><div data-template-mappings></div></div>
      <div class="set-card set-card--link"><div><h4>商品字段模板</h4><p>商品列表的内置模板、自定义模板和默认视图只在商品运营页维护。</p></div><a class="ui-button ui-button--ghost" href="/products"><i data-lucide="arrow-right"></i>打开商品运营</a></div>
    </div>
    <div class="settings-savebar" data-settings-savebar="templates"><span class="settings-savebar__dirty" data-settings-dirty="templates" role="status" aria-live="polite">已保存</span><button class="ui-button ui-button--ghost" type="button" data-settings-discard="templates" disabled>放弃修改</button><button class="ui-button ui-button--primary" type="button" data-settings-save="templates">保存导入规则</button><p data-settings-status="templates" role="status" aria-live="polite"></p></div>`;
  const templateSaveButton = templatePanel?.querySelector('[data-settings-save="templates"]');
  const templateDiscardButton = templatePanel?.querySelector('[data-settings-discard="templates"]');
  const sourceSelect = templatePanel?.querySelector('[data-template-source]');
  Object.entries(sourceLabels).forEach(([key, label]) => sourceSelect?.add(new Option(label, key)));
  const mappingKeySelect = templatePanel?.querySelector('[data-template-map-key]');
  Object.entries(fieldLabels).forEach(([key, label]) => mappingKeySelect?.add(new Option(label, key)));
  const mappingColumnInput = templatePanel?.querySelector('[data-template-map-column]');
  const listRow = (copy, locked, remove) => {
    const row = document.createElement('div'); row.className = 'status-list__item';
    const label = document.createElement('span'); label.className = 'status-list__label'; label.textContent = copy; row.appendChild(label);
    if (locked) { const badge = document.createElement('span'); badge.className = 'ui-badge'; badge.textContent = '内置'; row.appendChild(badge); }
    else if (remove) { const button = document.createElement('button'); button.type = 'button'; button.className = 'ui-button ui-button--ghost'; button.textContent = '移除'; button.addEventListener('click', remove); row.appendChild(button); }
    return row;
  };
  function renderTemplates() {
    if (!templatePanel) return;
    const mappings = templatePanel.querySelector('[data-template-mappings]');
    const mapRows = Object.entries(templateDraft.mapping_templates || {}).flatMap(([source, mapping]) => Object.entries(mapping).map(([key, column]) => listRow(`${sourceLabels[source] || '其他报表'}: ${fieldLabels[key] || key} → ${column}`, false, () => { delete templateDraft.mapping_templates[source][key]; if (!Object.keys(templateDraft.mapping_templates[source]).length) delete templateDraft.mapping_templates[source]; markTemplateDirty(); renderTemplates(); })));
    mappings?.replaceChildren(...(mapRows.length ? mapRows : [listRow('尚未保存字段映射', true)]));
  }
  templatePanel?.querySelector('[data-template-add-map]')?.addEventListener('click', () => {
    const source = sourceSelect?.value; const key = mappingKeySelect?.value; const column = mappingColumnInput?.value.trim();
    if (!source || !key || !column) return;
    templateDraft.mapping_templates[source] ||= {}; templateDraft.mapping_templates[source][key] = column;
    if (mappingColumnInput) mappingColumnInput.value = '';
    markTemplateDirty(); renderTemplates();
  });
  const resetTemplateBuilder = () => { if (mappingColumnInput) mappingColumnInput.value = ''; };
  const setDomainStatus = (domain, message = '') => {
    const node = document.querySelector(`[data-settings-status="${domain}"]`);
    if (node) { node.textContent = message; node.classList.remove('data-state'); }
  };
  const renderState = (state, details = {}) => {
    if (coreStatus) DemoApi.renderDataState(coreStatus, state, { retry: load, ...details });
  };
  const canEditSettings = () => {
    if (!settingsPayload.capabilities || !Object.keys(settingsPayload.capabilities).length) return true;
    return DemoApi.can(settingsPayload, 'can_edit');
  };
  const updateCoreForm = (data) => {
    if (!form) return;
    const scalarKeys = ['shop_name', 'timezone', 'currency', 'week_starts_on', 'annual_target_default', 'growth_multiplier', 'overachievement_threshold'];
    scalarKeys.forEach((key) => { if (form.elements[key] && data[key] !== null && data[key] !== undefined) form.elements[key].value = data[key]; });
    const thresholds = data.lifecycle_thresholds || {};
    form.elements.continuous_days.value = thresholds.continuous_days ?? 60;
    form.elements.seasonal_months.value = thresholds.seasonal_months ?? 12;
  };
  const resetTemplateDraft = (data) => {
    templateSnapshot = {
      mapping_templates: clone(data.mapping_templates || {}),
    };
    Object.assign(templateDraft, clone(templateSnapshot));
    renderTemplates();
    resetTemplateBuilder();
  };
  const resetClassificationDraft = (data) => {
    classificationSnapshot = {
      classification_dictionaries: clone(data.classification_dictionaries || { tiers: [], styles: [], lifecycle_stages: [], seasonal_attributes: [] }),
      category_modes: clone(data.configured_category_modes || data.category_modes || []),
      category_mode_default: data.category_mode_default || 'sock',
    };
    Object.assign(classificationDraft, clone(classificationSnapshot));
    DemoLabels.setDictionaries(classificationDraft.classification_dictionaries);
    renderDictionaries();
    renderCategoryModes();
  };
  const resetCoreSnapshot = (data) => {
    updateCoreForm(data);
    coreSnapshot = clone(coreFormValue());
  };
  const applyLoadedSettings = (data, resetAll = true) => {
    settingsPayload.data = data;
    if (resetAll) {
      resetCoreSnapshot(data);
      resetTemplateDraft(data);
      resetClassificationDraft(data);
      setDomainDirty('core', false); setDomainDirty('templates', false); setDomainDirty('classification', false);
    }
    document.querySelector('[data-settings-shop-scope]')?.replaceChildren(document.createTextNode(data.shop_scope?.shop_id || 'default'));
    const heroName = document.querySelector('[data-settings-hero-name]'); if (heroName) heroName.textContent = data.shop_name || '未命名店铺';
    const heroScope = document.querySelector('[data-settings-hero-scope]'); if (heroScope) heroScope.textContent = `scope ${data.shop_scope?.shop_id || 'default'}`;
  };
  const mergeResponse = (response, domain) => {
    settingsPayload = response;
    const data = response.data || {};
    if (domain === 'core') { resetCoreSnapshot(data); setDomainDirty('core', false); }
    if (domain === 'templates') { resetTemplateDraft(data); setDomainDirty('templates', false); }
    if (domain === 'classification') { resetClassificationDraft(data); setDomainDirty('classification', false); }
    updateDirtyUi();
  };
  const load = async () => {
    renderState('loading');
    try {
      settingsPayload = await DemoApi.domainRequest('/api/settings');
      applyLoadedSettings(settingsPayload.data || {}, true);
      setDomainStatus('core', ''); setDomainStatus('templates', ''); setDomainStatus('classification', '');
    } catch (error) {
      renderState('source-unavailable', { message: error.message || '设置加载失败' });
    }
  };
  const setButtonBusy = (button, busy, idleLabel) => {
    if (!button) return;
    button.disabled = busy; button.toggleAttribute('aria-busy', busy); button.textContent = busy ? '保存中…' : idleLabel;
    if (busy) button.setAttribute('data-settings-saving', 'true'); else button.removeAttribute('data-settings-saving');
  };
  const setCoreButtonBusy = (busy) => {
    if (!coreSaveButton) return;
    if (busy) coreSaveButton.setAttribute('aria-busy', 'true'); else coreSaveButton.removeAttribute('aria-busy');
    setButtonBusy(coreSaveButton, busy, '保存设置');
  };
  const saveCore = async (event) => {
    event?.preventDefault();
    if (savingState.core || !canEditSettings()) { if (!canEditSettings()) setDomainStatus('core', '当前设置不可修改'); return; }
    const data = new FormData(form);
    savingState.core = true; setCoreButtonBusy(true); updateDirtyUi(); setDomainStatus('core', '正在保存…');
    try {
      const response = await DemoApi.domainRequest('/api/settings', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({
        shop_name: data.get('shop_name'), timezone: data.get('timezone'), currency: data.get('currency'), week_starts_on: data.get('week_starts_on'),
        annual_target_default: Number(data.get('annual_target_default') || 0), growth_multiplier: Number(data.get('growth_multiplier') || 1), overachievement_threshold: Number(data.get('overachievement_threshold') || 1),
        lifecycle_thresholds: { continuous_days: Number(data.get('continuous_days') || 60), seasonal_months: Number(data.get('seasonal_months') || 12) },
      }) });
      mergeResponse(response, 'core'); setDomainStatus('core', '店铺与目标设置已保存');
    } catch (error) { setDomainStatus('core', error.message || '保存失败'); }
    finally { savingState.core = false; setCoreButtonBusy(false); updateDirtyUi(); }
  };
  const validateClassification = () => {
    const modes = classificationDraft.category_modes || [];
    if (modes.some((item) => !String(item.value || '').trim() || !String(item.label || '').trim())) return '请补全品类编码和名称';
    if (new Set(modes.map((item) => item.value)).size !== modes.length) return '品类编码不能重复';
    if (!modes.some((item) => item.enabled !== false)) return '至少需要启用一个品类';
    if (!modes.some((item) => item.value === classificationDraft.category_mode_default && item.enabled !== false)) return '默认品类必须引用已启用的品类';
    return '';
  };
  const saveTemplates = async () => {
    if (savingState.templates || !canEditSettings()) { if (!canEditSettings()) setDomainStatus('templates', '当前设置不可修改'); return; }
    savingState.templates = true; setButtonBusy(templateSaveButton, true, '保存导入规则'); updateDirtyUi(); setDomainStatus('templates', '正在保存…');
    try {
      const response = await DemoApi.domainRequest('/api/settings', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ mapping_templates: clone(templateDraft.mapping_templates) }) });
      mergeResponse(response, 'templates'); setDomainStatus('templates', '导入规则已保存');
    } catch (error) { setDomainStatus('templates', error.message || '保存失败'); }
    finally { savingState.templates = false; setButtonBusy(templateSaveButton, false, '保存导入规则'); updateDirtyUi(); }
  };
  const saveClassification = async () => {
    if (savingState.classification || !canEditSettings()) { if (!canEditSettings()) setDomainStatus('classification', '当前设置不可修改'); return; }
    const validationError = validateClassification(); if (validationError) { setDomainStatus('classification', validationError); return; }
    savingState.classification = true; setButtonBusy(classificationSaveButton, true, '保存分类设置'); updateDirtyUi(); setDomainStatus('classification', '正在保存…');
    try {
      const response = await DemoApi.domainRequest('/api/settings', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ classification_dictionaries: clone(classificationDraft.classification_dictionaries), category_modes: clone(classificationDraft.category_modes), category_mode_default: classificationDraft.category_mode_default }) });
      mergeResponse(response, 'classification'); setDomainStatus('classification', '分类设置已保存');
    } catch (error) { setDomainStatus('classification', error.message || '保存失败'); }
    finally { savingState.classification = false; setButtonBusy(classificationSaveButton, false, '保存分类设置'); updateDirtyUi(); }
  };
  const discardCore = () => {
    if (!dirtyState.core || !coreSnapshot) return;
    updateCoreForm(settingsPayload.data || {});
    const values = coreSnapshot;
    form.elements.shop_name.value = values.shop_name;
    form.elements.timezone.value = values.timezone;
    form.elements.currency.value = values.currency;
    form.elements.week_starts_on.value = values.week_starts_on;
    form.elements.annual_target_default.value = values.annual_target_default;
    form.elements.growth_multiplier.value = values.growth_multiplier;
    form.elements.overachievement_threshold.value = values.overachievement_threshold;
    form.elements.continuous_days.value = values.continuous_days;
    form.elements.seasonal_months.value = values.seasonal_months;
    setDomainDirty('core', false); setDomainStatus('core', '已放弃未保存修改');
  };
  const discardTemplates = () => { if (!dirtyState.templates || !templateSnapshot) return; Object.assign(templateDraft, clone(templateSnapshot)); renderTemplates(); resetTemplateBuilder(); setDomainDirty('templates', false); setDomainStatus('templates', '已放弃未保存修改'); };
  const discardClassification = () => { if (!dirtyState.classification || !classificationSnapshot) return; Object.assign(classificationDraft, clone(classificationSnapshot)); DemoLabels.setDictionaries(classificationDraft.classification_dictionaries); renderDictionaries(); renderCategoryModes(); setDomainDirty('classification', false); setDomainStatus('classification', '已放弃未保存修改'); };
  form?.addEventListener('submit', saveCore);
  form?.addEventListener('input', syncCoreDirty);
  form?.addEventListener('change', syncCoreDirty);
  coreDiscardButton?.addEventListener('click', discardCore);
  templateSaveButton?.addEventListener('click', saveTemplates);
  templateDiscardButton?.addEventListener('click', discardTemplates);
  classificationSaveButton?.addEventListener('click', saveClassification);
  classificationDiscardButton?.addEventListener('click', discardClassification);

  const scanState = { jobs: [], editingId: null, environment: null };
  let scanLoadToken = 0;
  let scanMutationBusy = false;
  const scanBody = document.querySelector('[data-scan-jobs]');
  const scanStatus = document.querySelector('[data-scan-status]');
  const showToast = (message, options) => window.DemoShell?.showToast?.(message, options);
  const scanDialog = document.querySelector('[data-scan-dialog]');
  const scanForm = document.querySelector('[data-scan-form]');
  const scanFormStatus = document.querySelector('[data-scan-form-status]');
  const scanDetailDialog = document.querySelector('[data-scan-detail-dialog]');
  const scanSourceLabels = { auto: '自动识别', product_day: '商品日度', dmp_product_day: 'DMP 商品日度', store_day: '店铺日度', refund_day: '退款日度', customer_day: '客户日度', product_week: '商品周度', product_month: '商品月度', promotion_channel_day: '推广渠道日度', promotion_campaign_day: '推广计划日度', promotion_unit_day: '推广单元日度', promotion_product_day: '推广商品日度' };
  const renderScanEnvironment = (environment) => {
    const target = document.querySelector('[data-scan-environment]');
    if (!target || !environment) return;
    const roots = (environment.allowed_roots || []).join('、') || '未配置';
    const mode = environment.mode === 'desktop' ? '桌面模式' : 'Web 服务模式';
    target.textContent = `${mode} · 允许目录 ${roots} · 支持 ${environment.supported_suffixes?.join('、') || '--'} · 计划时区 ${environment.cron_timezone || 'Asia/Shanghai'}`;
  };
  const setScanStatus = (message) => { if (scanStatus) scanStatus.textContent = message || ''; };
  const setScanCapabilityState = () => {
    const enabled = scanState.environment?.can_manage !== false;
    document.querySelectorAll('[data-scan-create], [data-scan-form] button[type="submit"], [data-settings-select-scan-folder]').forEach((element) => {
      element.disabled = !enabled;
      element.toggleAttribute('aria-disabled', !enabled);
    });
  };
  const setScanFormStatus = (message) => { if (scanFormStatus) scanFormStatus.textContent = message || ''; };
  const formatScanFormError = (error) => {
    if (window.TmallScanUi?.errorMessage) return window.TmallScanUi.errorMessage(error);
    const message = error?.message || '保存扫描任务失败';
    if (message.includes('outside IMPORT_SCAN_ALLOWED_ROOTS')) return '该文件夹不在允许扫描目录中。请使用已配置的数据源目录，或联系管理员将此目录加入允许列表。';
    if (message.includes('must be an existing directory')) return '文件夹不存在。请检查路径是否为本机已有的绝对路径。';
    if (message.includes('cron_expr')) return '扫描计划格式不正确。请使用 5 段 cron 表达式，例如：0 8 * * *。';
    return message;
  };
  const appendTextCell = (row, value) => { const cell = document.createElement('td'); cell.textContent = value ?? '--'; row.appendChild(cell); return cell; };
  const replaceTableBody = (target, columns, rows, emptyMessage) => {
    if (!target || !window.TmallUI?.table?.mount) return;
    window.TmallUI.table.mount(target, { columns, rows, emptyMessage });
  };
  const scanAction = (icon, label, handler) => {
    const button = document.createElement('button'); button.type = 'button'; button.className = 'ui-button ui-button--ghost'; button.title = label; button.setAttribute('aria-label', label);
    const glyph = document.createElement('i'); glyph.dataset.lucide = icon; button.appendChild(glyph); button.addEventListener('click', handler); return button;
  };
  const formatScanTime = (value) => value ? new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium', timeStyle: 'medium', hour12: false, timeZone: 'Asia/Shanghai' }).format(new Date(value)) : '--';
  // 常见 cron 表达式的人话说明；解析不了就不显示提示。
  const WEEKDAY_NAMES = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'];
  const humanizeCron = (expr) => {
    const parts = String(expr || '').trim().split(/\s+/);
    if (parts.length !== 5) return '';
    const [minute, hour, dayOfMonth, month, weekday] = parts;
    const pad = (value) => String(value).padStart(2, '0');
    if (/^\d+$/.test(minute) && /^\d+$/.test(hour) && dayOfMonth === '*' && month === '*' && weekday === '*') {
      return `每天 ${pad(hour)}:${pad(minute)}`;
    }
    if (minute.startsWith('*/') && hour === '*' && dayOfMonth === '*' && month === '*' && weekday === '*') {
      return `每 ${minute.slice(2)} 分钟`;
    }
    if (/^\d+$/.test(minute) && /^\d+$/.test(hour) && dayOfMonth === '*' && month === '*' && /^\d+$/.test(weekday)) {
      return `每${WEEKDAY_NAMES[Number(weekday)] || '周'} ${pad(hour)}:${pad(minute)}`;
    }
    if (/^\d+$/.test(minute) && /^\d+$/.test(hour) && /^\d+$/.test(dayOfMonth) && month === '*' && weekday === '*') {
      return `每月 ${Number(dayOfMonth)} 日 ${pad(hour)}:${pad(minute)}`;
    }
    return '';
  };
  const updateScanBadges = (jobs) => {
    const headerBadge = document.querySelector('[data-scan-count]');
    if (headerBadge) headerBadge.textContent = `${jobs.length} 个任务`;
  };
  function renderScanJobs() {
    if (!scanBody) return;
    replaceTableBody(scanBody, [
      { key: 'task', label: '任务', render: (_, job) => { const task = document.createElement('div'); const name = document.createElement('strong'); name.textContent = job.task_name || '未命名任务'; const folder = document.createElement('div'); folder.className = 'panel__hint'; folder.textContent = job.folder_path || '--'; task.append(name, folder); return task; } },
      { key: 'source', label: '来源', render: (_, job) => scanSourceLabels[job.source_type] || job.source_type || '--' },
      { key: 'cron', label: '计划', render: (_, job) => { const cell = document.createElement('div'); cell.appendChild(document.createTextNode(job.cron_expr || '--')); const cronHint = humanizeCron(job.cron_expr); if (cronHint) { const hint = document.createElement('div'); hint.className = 'scan-cron-hint'; hint.textContent = cronHint; cell.appendChild(hint); } return cell; } },
      { key: 'status', label: '状态', render: (_, job) => job.status === 'error' ? '配置异常' : (job.enabled ? (job.status === 'active' ? '已启用' : job.status) : '已停用') },
      { key: 'last_run', label: '最近运行', render: (value) => formatScanTime(value) },
      { key: 'actions', label: '操作', render: (_, job) => {
        const actions = document.createElement('div'); actions.className = 'table-actions';
      const canManage = scanState.environment?.can_manage !== false;
      const runButton = scanAction('play', job.enabled ? '立即扫描' : '请先启用任务', () => runScanJob(job));
      runButton.disabled = !job.enabled || !canManage;
      const detailButton = scanAction('history', '查看记录', () => openScanDetails(job));
      const editButton = scanAction('pencil', '编辑任务', () => openScanDialog(job));
      const toggleButton = scanAction(job.enabled ? 'power-off' : 'power', job.enabled ? '停用任务' : '启用任务', () => toggleScanJob(job));
      const deleteButton = scanAction('trash-2', '删除任务', () => deleteScanJob(job));
      [editButton, toggleButton, deleteButton].forEach((button) => { button.disabled = !canManage; button.toggleAttribute('aria-disabled', !canManage); });
      actions.append(runButton, detailButton, editButton, toggleButton, deleteButton);
        return actions;
      } },
    ], scanState.jobs, '暂无扫描任务');
    window.lucide?.createIcons();
  }
  async function loadScanJobs() {
    if (!scanBody) return;
    const token = ++scanLoadToken;
    const loading = document.createElement('tr'); const cell = appendTextCell(loading, '正在加载扫描任务…'); cell.colSpan = 6; scanBody.replaceChildren(loading);
    try { const response = await DemoApi.domainRequest('/api/import-scans'); if (token !== scanLoadToken) return; scanState.environment = response.scan_environment || null; renderScanEnvironment(scanState.environment); setScanCapabilityState(); scanState.jobs = Array.isArray(response.data) ? response.data.filter((job) => job && typeof job === 'object') : []; renderScanJobs(); updateScanBadges(scanState.jobs); setScanStatus(''); }
    catch (error) { if (token !== scanLoadToken) return; scanState.jobs = []; renderScanJobs(); updateScanBadges(scanState.jobs); setScanStatus(formatScanFormError(error)); }
  }
  function openScanDialog(job = null) {
    scanState.editingId = job?.id ?? null; scanForm.reset(); scanForm.elements.file_pattern.value = job?.file_pattern || '*.xlsx;*.xls;*.csv;*.zip'; scanForm.elements.cron_expr.value = job?.cron_expr || '* * * * *'; scanForm.elements.source_type.value = job?.source_type || 'auto'; scanForm.elements.enabled.checked = job ? Boolean(job.enabled) : true;
    setScanFormStatus('');
    if (job) { scanForm.elements.task_name.value = job.task_name || ''; scanForm.elements.folder_path.value = job.folder_path || ''; }
    document.querySelector('#scanDialogTitle').textContent = job ? '编辑扫描任务' : '新增扫描任务'; scanDialog.showModal(); scanForm.elements.task_name.focus();
  }
  async function mutateScan(message, operation, handleError = (error) => setScanStatus(formatScanFormError(error))) {
    if (scanMutationBusy) return;
    scanMutationBusy = true;
    setScanStatus(message);
    try { const result = await operation(); await loadScanJobs(); return result; }
    catch (error) { handleError(error); }
    finally { scanMutationBusy = false; }
  }
  function runScanJob(job) {
    showToast(`已启动扫描：${job.task_name}`, { duration: 3000 });
    mutateScan(`正在扫描 ${job.task_name}…`, () => DemoApi.domainRequest(`/api/import-scans/${Number(job.id)}/run`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ force: true }) })).then((response) => {
      const result = response?.data;
      if (!result) return;
      const summary = `扫描完成：发现 ${result.discovered_count || 0}，导入 ${result.imported_count || 0}，阻塞 ${result.blocked_count || 0}，失败 ${result.failed_count || 0}`;
      showToast(summary, { duration: result.failed_count || result.blocked_count ? 6000 : 4500 });
    });
  }
  function toggleScanJob(job) {
    if (job.enabled) return mutateScan('正在停用任务…', () => DemoApi.domainRequest(`/api/import-scans/${Number(job.id)}`, { method: 'DELETE' })).then((response) => { if (response) showToast(`已停用扫描任务：${job.task_name}`); });
    return mutateScan('正在启用任务…', () => DemoApi.domainRequest(`/api/import-scans/${Number(job.id)}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ enabled: true }) })).then((response) => { if (response) showToast(`已启用扫描任务：${job.task_name}`); });
  }
  function deleteScanJob(job) {
    if (!window.confirm(`确定删除扫描任务“${job.task_name || '未命名任务'}”？相关扫描记录也会删除。`)) return;
    mutateScan('正在删除任务…', () => DemoApi.domainRequest(`/api/import-scans/${Number(job.id)}/delete`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({}) })).then((response) => { if (response) showToast(`已删除扫描任务：${job.task_name || '未命名任务'}`); });
  }
  const renderScanDetailRows = (selector, rows, columns, emptyText) => {
    const body = document.querySelector(selector); body.replaceChildren();
    const tableColumns = columns.map((column, index) => ({ key: `column_${index}`, label: '', render: (_, row) => column(row.item) }));
    replaceTableBody(body, tableColumns, rows.slice(0, 20).map((item) => ({ item })), emptyText);
  };
  async function loadScanDetails(job) {
    renderScanDetailRows('[data-scan-runs]', [], Array.from({ length: 5 }, () => () => ''), '加载中…'); renderScanDetailRows('[data-scan-files]', [], Array.from({ length: 5 }, () => () => ''), '加载中…');
    try {
      const [runs, files] = await Promise.all([DemoApi.domainRequest(`/api/import-scans/${Number(job.id)}/runs`), DemoApi.domainRequest(`/api/import-scans/${Number(job.id)}/files`)]);
      renderScanDetailRows('[data-scan-runs]', runs.data || [], [(item) => formatScanTime(item.started_at), (item) => item.status, (item) => item.imported_count, (item) => item.blocked_count, (item) => item.failed_count], '暂无运行记录');
      const body = document.querySelector('[data-scan-files]');
      replaceTableBody(body, [
        { key: 'source_filename', label: '文件' },
        { key: 'status', label: '状态' },
        { key: 'batch_id', label: '批次', render: (value) => value || '--' },
        { key: 'updated_at', label: '更新时间', render: (value) => formatScanTime(value) },
        { key: 'actions', label: '操作', render: (_, item) => {
          const actions = document.createElement('div'); actions.className = 'table-actions';
        if (['blocked', 'failed'].includes(item.status)) {
          const retryButton = scanAction('rotate-ccw', '重新排队', async () => {
            try { await DemoApi.domainRequest(`/api/import-scans/${Number(job.id)}/files/${Number(item.id)}/retry`, { method: 'POST' }); setScanStatus('文件已重新排队'); showToast(`文件已重新排队：${item.source_filename}`); await loadScanDetails(job); await loadScanJobs(); }
            catch (error) { setScanStatus(formatScanFormError(error)); }
          });
          const canManage = scanState.environment?.can_manage !== false;
          retryButton.disabled = !canManage;
          retryButton.toggleAttribute('aria-disabled', !canManage);
          actions.append(retryButton);
        }
          return actions;
        } },
      ], (files.data || []).slice(0, 20), '暂无文件记录');
      window.lucide?.createIcons();
    } catch (error) { setScanStatus(formatScanFormError(error)); }
  }
  async function openScanDetails(job) {
    document.querySelector('#scanDetailTitle').textContent = `${job.task_name || '扫描任务'}记录`; scanDetailDialog.showModal();
    await loadScanDetails(job);
  }
  document.querySelector('[data-scan-create]')?.addEventListener('click', () => { if (scanState.environment?.can_manage === false) return; openScanDialog(); });
  const settingsScanFolderButton = document.querySelector('[data-settings-select-scan-folder]');
  if (window.tmallDesktop?.selectScanFolder && settingsScanFolderButton) {
    settingsScanFolderButton.hidden = false;
    settingsScanFolderButton.addEventListener('click', async () => {
      const selected = await window.tmallDesktop.selectScanFolder();
      if (selected) scanForm.elements.folder_path.value = selected;
    });
  }
  document.querySelectorAll('[data-scan-close]').forEach((button) => button.addEventListener('click', () => scanDialog.close()));
  document.querySelectorAll('[data-scan-detail-close]').forEach((button) => button.addEventListener('click', () => scanDetailDialog.close()));
  scanForm?.addEventListener('submit', (event) => {
    event.preventDefault(); const data = new FormData(scanForm); const payload = { task_name: data.get('task_name'), folder_path: data.get('folder_path'), file_pattern: data.get('file_pattern'), source_type: data.get('source_type'), cron_expr: data.get('cron_expr'), enabled: data.get('enabled') === 'on' }; const jobId = scanState.editingId;
    setScanFormStatus('');
    mutateScan(jobId ? '正在更新任务…' : '正在创建任务…', async () => { const response = await DemoApi.domainRequest(jobId ? `/api/import-scans/${Number(jobId)}` : '/api/import-scans', { method: jobId ? 'PUT' : 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) }); scanDialog.close(); return response; }, (error) => { setScanStatus(''); setScanFormStatus(formatScanFormError(error)); }).then((response) => { if (response) showToast(jobId ? `扫描任务已更新：${payload.task_name}` : `扫描任务已创建：${payload.task_name}`); });
  });
  load();
  loadScanJobs();
})();
