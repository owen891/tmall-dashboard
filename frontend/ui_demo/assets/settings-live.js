(function () {
  const form = document.querySelector('[data-settings-form]');
  const status = document.querySelector('[data-settings-status]');
  const sourceLabels = { product_day: '商品日度', store_day: '店铺日度', product_week: '商品周度', product_month: '商品月度', promotion_channel_day: '推广渠道日度', promotion_campaign_day: '推广计划日度', promotion_unit_day: '推广单元日度', promotion_product_day: '推广商品日度', refund_day: '退款日度', customer_day: '新老客日度' };
  const fieldLabels = { date: '日期', product_id: '商品编号', product_name: '商品名称', payment_amount: '支付金额', successful_refund_amount: '成功退款金额', product_visitors: '商品访客数', payment_buyers: '支付买家数', returning_payment_buyers: '复购买家数', ad_spend: '推广花费', channel: '推广渠道', campaign_id: '推广计划', unit_id: '推广单元', attributed_payment_amount: '推广成交' };
  const columnLabels = { product_id: '商品编号', title: '商品名称', tier: '商品分层', style: '经营类型', status: '在售状态', payment_amount: '支付金额', net_sales: '净销售额', conversion: '商品支付转化率', refund_amount: '退款金额', refund_rate: '退款率', ad_spend: '推广花费', roi: '推广 ROI', overall_roi: '整体 ROI', paid_ratio: '付费占比', score: '综合评分', lifecycle_stage: '生命周期阶段', seasonality: '季节性', has_pending_action: '待办动作' };
  const builtInViews = new Set(['operate', 'select', 'paid', 'refund', 'lifecycle']);
  const templateState = { mapping_templates: {}, view_templates: {}, classification_dictionaries: { tiers: [], styles: [], lifecycle_stages: [], seasonal_attributes: [] } };
  const dictionaryLabels = { tiers: '商品分层', styles: '商品风格', lifecycle_stages: '生命周期', seasonal_attributes: '季节属性' };
  const dictionaryRoot = document.querySelector('[data-classification-dictionaries]');
  const dirtyStatus = document.querySelector('[data-settings-dirty]');
  const discardButton = document.querySelector('[data-settings-discard]');
  let isDirty = false;
  let settingsPayload = { capabilities: {} };
  const setDirty = (value) => {
    isDirty = Boolean(value);
    if (dirtyStatus) dirtyStatus.textContent = isDirty ? '有未保存修改' : '已保存';
    if (discardButton) discardButton.disabled = !isDirty;
    document.querySelector('[data-settings-savebar]')?.classList.toggle('is-dirty', isDirty);
  };
  const markDirty = () => setDirty(true);
  const tabLinks = [...document.querySelectorAll('[data-settings-tab]')];
  const tabPanels = [...document.querySelectorAll('[data-settings-tab-panel]')];
  function selectSettingsTab(tab, updateHash = true) {
    const activeTab = tabLinks.some((link) => link.dataset.settingsTab === tab) ? tab : 'store';
    tabLinks.forEach((link) => {
      const active = link.dataset.settingsTab === activeTab;
      link.setAttribute('aria-current', String(active));
    });
    tabPanels.forEach((panel) => { panel.hidden = panel.dataset.settingsTabPanel !== activeTab; });
    if (updateHash) history.replaceState(null, '', `#settings-${activeTab}`);
  }
  tabLinks.forEach((link) => link.addEventListener('click', (event) => { event.preventDefault(); selectSettingsTab(link.dataset.settingsTab); }));
  selectSettingsTab(window.location.hash === '#settings-goals' ? 'goals' : 'store', false);
  window.addEventListener('beforeunload', (event) => { if (isDirty) { event.preventDefault(); event.returnValue = ''; } });

  function renderDictionaries() {
    dictionaryRoot.replaceChildren(...Object.entries(dictionaryLabels).map(([group, title]) => {
      const section = document.createElement('section'); section.className = 'classification-group';
      const heading = document.createElement('div'); heading.className = 'classification-group__header';
      const name = document.createElement('h4'); name.textContent = title;
      const add = document.createElement('button'); add.type = 'button'; add.className = 'button button--ghost'; add.textContent = '新增';
      add.addEventListener('click', () => { markDirty(); templateState.classification_dictionaries[group].push({ value: '', label: '', enabled: true, system: false }); renderDictionaries(); section.querySelector('.classification-row:last-child input')?.focus(); });
      heading.append(name, add); section.appendChild(heading);
      const rows = document.createElement('div'); rows.className = 'classification-group__rows';
      (templateState.classification_dictionaries[group] || []).forEach((item, index) => {
        const row = document.createElement('div'); row.className = 'classification-row';
        const label = document.createElement('input'); label.className = 'input'; label.value = item.label || ''; label.placeholder = '中文名称'; label.setAttribute('aria-label', `${title}中文名称`); label.addEventListener('input', () => { markDirty(); item.label = label.value; });
        const enabled = document.createElement('label'); enabled.className = 'classification-row__toggle'; const checkbox = document.createElement('input'); checkbox.type = 'checkbox'; checkbox.checked = item.enabled !== false; checkbox.addEventListener('change', () => { markDirty(); item.enabled = checkbox.checked; }); enabled.append(checkbox, document.createTextNode('启用'));
        row.append(label, enabled);
        if (item.system) { const badge = document.createElement('span'); badge.className = 'badge'; badge.textContent = '内置'; row.appendChild(badge); }
        else { const remove = document.createElement('button'); remove.type = 'button'; remove.className = 'button button--ghost'; remove.textContent = '移除'; remove.addEventListener('click', () => { markDirty(); templateState.classification_dictionaries[group].splice(index, 1); renderDictionaries(); }); row.appendChild(remove); }
        rows.appendChild(row);
      });
      if (!rows.children.length) { const empty = document.createElement('p'); empty.className = 'panel__hint'; empty.textContent = '暂无分类，点击新增开始维护。'; rows.appendChild(empty); }
      section.appendChild(rows); return section;
    }));
  }
  const templatePanel = document.createElement('section');
  templatePanel.className = 'plain-panel panel settings-template-panel';
  templatePanel.id = 'settings-templates';
  templatePanel.innerHTML = `
    <div class="panel__header"><div><h3 class="panel__title">导入与视图模板</h3><p class="panel__hint">将常用报表列和商品视图保存为业务模板。</p></div></div>
    <div class="settings-template-grid">
      <div><h4>报表字段映射</h4><div class="filter-group"><select class="select" data-template-source aria-label="报表类型"></select><select class="select" data-template-map-key aria-label="业务字段"></select><input class="input" data-template-map-column placeholder="报表中的列名" aria-label="报表中的列名"><button class="button" type="button" data-template-add-map>添加</button></div><div data-template-mappings></div></div>
      <div><h4>商品视图</h4><div class="filter-group"><input class="input" data-template-view-label placeholder="新视图名称" aria-label="新视图名称"><select class="select" data-template-view-columns multiple size="5" aria-label="显示字段"></select><button class="button" type="button" data-template-add-view>保存视图</button></div><div data-template-views></div></div>
    </div>`;
  const templateHost = form.closest('.settings-main') || form.parentElement;
  templateHost.appendChild(templatePanel);
  const templateHeader = templatePanel.querySelector('.panel__header');
  const templateGrid = templatePanel.querySelector('.settings-template-grid');
  const templateToggle = document.createElement('button');
  templateToggle.type = 'button';
  templateToggle.className = 'button button--ghost';
  templateToggle.textContent = '展开模板';
  templateToggle.setAttribute('aria-expanded', 'false');
  templateHeader.appendChild(templateToggle);
  templateGrid.hidden = true;
  templateToggle.addEventListener('click', () => {
    const expanded = templateGrid.hidden;
    templateGrid.hidden = !expanded;
    templateToggle.textContent = expanded ? '收起模板' : '展开模板';
    templateToggle.setAttribute('aria-expanded', String(expanded));
  });
  const sourceSelect = templatePanel.querySelector('[data-template-source]');
  Object.entries(sourceLabels).forEach(([key, label]) => sourceSelect.add(new Option(label, key)));
  const mappingKeySelect = templatePanel.querySelector('[data-template-map-key]');
  Object.entries(fieldLabels).forEach(([key, label]) => mappingKeySelect.add(new Option(label, key)));
  const mappingColumnInput = templatePanel.querySelector('[data-template-map-column]');
  const viewColumnsSelect = templatePanel.querySelector('[data-template-view-columns]');
  Object.entries(columnLabels).forEach(([key, label]) => viewColumnsSelect.add(new Option(label, key)));
  const listRow = (copy, locked, remove) => { const row = document.createElement('div'); row.className = 'status-list__item'; const label = document.createElement('span'); label.className = 'status-list__label'; label.textContent = copy; row.appendChild(label); if (locked) { const badge = document.createElement('span'); badge.className = 'badge'; badge.textContent = '内置'; row.appendChild(badge); } else if (remove) { const button = document.createElement('button'); button.type = 'button'; button.className = 'button button--ghost'; button.textContent = '移除'; button.addEventListener('click', () => { markDirty(); remove(); }); row.appendChild(button); } return row; };
  function renderTemplates() {
    const mappings = templatePanel.querySelector('[data-template-mappings]');
    const mapRows = Object.entries(templateState.mapping_templates).flatMap(([source, mapping]) => Object.entries(mapping).map(([key, column]) => listRow(`${sourceLabels[source] || '其他报表'}: ${fieldLabels[key] || '其他字段'} → ${column}`, false, () => { delete templateState.mapping_templates[source][key]; renderTemplates(); })));
    mappings.replaceChildren(...(mapRows.length ? mapRows : [listRow('尚未保存字段映射') ]));
    const views = templatePanel.querySelector('[data-template-views]');
    const viewRows = Object.entries(templateState.view_templates).map(([key, view]) => listRow(`${view.label || '未命名视图'}：${(view.columns || []).map((column) => columnLabels[column] || column).join('、')}`, builtInViews.has(key), () => { delete templateState.view_templates[key]; renderTemplates(); }));
    views.replaceChildren(...(viewRows.length ? viewRows : [listRow('尚未保存商品视图') ]));
  }
  function renderProductViewOptions(data) {
    const select = form.elements.product_view_template;
    const templates = data.view_templates || {};
    select.replaceChildren(...Object.entries(templates).map(([key, view]) => new Option(view.label || key, key)));
    select.value = templates[data.product_view_template] ? data.product_view_template : Object.keys(templates)[0] || '';
  }
  templatePanel.querySelector('[data-template-add-map]').addEventListener('click', () => { const source = sourceSelect.value; const key = mappingKeySelect.value; const column = mappingColumnInput.value.trim(); if (!column) return; markDirty(); templateState.mapping_templates[source] ||= {}; templateState.mapping_templates[source][key] = column; mappingColumnInput.value = ''; renderTemplates(); });
  templatePanel.querySelector('[data-template-add-view]').addEventListener('click', () => { const label = templatePanel.querySelector('[data-template-view-label]').value.trim(); const columns = [...viewColumnsSelect.selectedOptions].map((option) => option.value); if (!label || !columns.length) return; markDirty(); const key = `custom_${Date.now()}`; templateState.view_templates[key] = { label, columns }; templatePanel.querySelector('[data-template-view-label]').value = ''; [...viewColumnsSelect.options].forEach((option) => { option.selected = false; }); renderTemplates(); });
  const set = (data) => { renderProductViewOptions(data); Object.entries(data).forEach(([key, value]) => { if (form.elements[key] && value !== null && typeof value !== 'object') form.elements[key].value = value; }); const thresholds = data.lifecycle_thresholds || {}; form.elements.continuous_days.value = thresholds.continuous_days ?? 60; form.elements.seasonal_months.value = thresholds.seasonal_months ?? 12; templateState.mapping_templates = data.mapping_templates || {}; templateState.view_templates = data.view_templates || {}; templateState.classification_dictionaries = structuredClone(data.classification_dictionaries || templateState.classification_dictionaries); DemoLabels.setDictionaries(templateState.classification_dictionaries); renderTemplates(); renderDictionaries(); setDirty(false); const summary = (key) => document.querySelector(`[data-settings-summary="${key}"]`); if (summary('status')) summary('status').textContent = '已保存'; if (summary('annual_target')) summary('annual_target').textContent = `¥${Number(data.annual_target_default || 0).toLocaleString('zh-CN')}`; if (summary('view')) summary('view').textContent = data.product_view_template || 'operate'; };
  const clearStatus = () => { status.replaceChildren(); status.classList.remove('data-state'); };
  const renderState = (state, details = {}) => DemoApi.renderDataState(status, state, { retry: load, ...details });
  const load = async () => { renderState('loading'); try { settingsPayload = await DemoApi.domainRequest('/api/settings'); set(settingsPayload.data); clearStatus(); } catch (error) { renderState('source-unavailable', { message: error.message || '设置加载失败' }); } };
  discardButton?.addEventListener('click', () => { if (!isDirty) return; set(settingsPayload.data || settingsPayload); status.textContent = '已放弃未保存修改'; });
  form.addEventListener('submit', async (event) => { event.preventDefault(); if (Object.keys(settingsPayload.capabilities || {}).length > 0 && !DemoApi.can(settingsPayload, 'can_edit')) { status.textContent = '当前设置不可修改'; return; } const data = new FormData(form); renderState('loading'); try { const response = await DemoApi.domainRequest('/api/settings', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ shop_name: data.get('shop_name'), timezone: data.get('timezone'), currency: data.get('currency'), week_starts_on: data.get('week_starts_on'), annual_target_default: Number(data.get('annual_target_default') || 0), growth_multiplier: Number(data.get('growth_multiplier') || 1), overachievement_threshold: Number(data.get('overachievement_threshold') || 1), lifecycle_thresholds: { continuous_days: Number(data.get('continuous_days') || 60), seasonal_months: Number(data.get('seasonal_months') || 12) }, mapping_templates: templateState.mapping_templates, view_templates: templateState.view_templates, classification_dictionaries: templateState.classification_dictionaries, product_view_template: data.get('product_view_template') }) }); settingsPayload = response; set(response.data); clearStatus(); status.textContent = '设置已保存'; } catch (error) { renderState('calculation-failed', { message: error.message || '保存失败' }); } });
  form.addEventListener('input', markDirty);
  form.addEventListener('change', markDirty);
  const scanState = { jobs: [], editingId: null };
  const scanBody = document.querySelector('[data-scan-jobs]');
  const scanStatus = document.querySelector('[data-scan-status]');
  const scanDialog = document.querySelector('[data-scan-dialog]');
  const scanForm = document.querySelector('[data-scan-form]');
  const scanDetailDialog = document.querySelector('[data-scan-detail-dialog]');
  const scanSourceLabels = { auto: '自动识别', product_day: '商品日度', dmp_product_day: 'DMP 商品日度', store_day: '店铺日度', refund_day: '退款日度', customer_day: '客户日度', product_week: '商品周度', product_month: '商品月度', promotion_channel_day: '推广渠道日度', promotion_campaign_day: '推广计划日度', promotion_unit_day: '推广单元日度', promotion_product_day: '推广商品日度' };
  const setScanStatus = (message) => { if (scanStatus) scanStatus.textContent = message || ''; };
  const appendTextCell = (row, value) => { const cell = document.createElement('td'); cell.textContent = value ?? '--'; row.appendChild(cell); return cell; };
  const scanAction = (icon, label, handler) => {
    const button = document.createElement('button'); button.type = 'button'; button.className = 'button button--ghost'; button.title = label; button.setAttribute('aria-label', label);
    const glyph = document.createElement('i'); glyph.dataset.lucide = icon; button.appendChild(glyph); button.addEventListener('click', handler); return button;
  };
  const formatScanTime = (value) => value ? String(value).replace('T', ' ').replace('+00:00', '') : '--';
  function renderScanJobs() {
    if (!scanBody) return;
    scanBody.replaceChildren();
    if (!scanState.jobs.length) { const row = document.createElement('tr'); const cell = appendTextCell(row, '暂无扫描任务'); cell.colSpan = 6; scanBody.appendChild(row); return; }
    scanState.jobs.forEach((job) => {
      const row = document.createElement('tr');
      const task = document.createElement('td'); const name = document.createElement('strong'); name.textContent = job.task_name || '未命名任务'; const folder = document.createElement('div'); folder.className = 'panel__hint'; folder.textContent = job.folder_path || '--'; task.append(name, folder); row.appendChild(task);
      appendTextCell(row, scanSourceLabels[job.source_type] || job.source_type);
      appendTextCell(row, job.cron_expr || '--');
      appendTextCell(row, job.enabled ? (job.status === 'active' ? '已启用' : job.status) : '已停用');
      appendTextCell(row, formatScanTime(job.last_run));
      const actions = document.createElement('td'); actions.className = 'table-actions';
      actions.append(
        scanAction('play', '立即扫描', () => runScanJob(job)),
        scanAction('history', '查看记录', () => openScanDetails(job)),
        scanAction('pencil', '编辑任务', () => openScanDialog(job)),
        scanAction(job.enabled ? 'power-off' : 'power', job.enabled ? '停用任务' : '启用任务', () => toggleScanJob(job)),
      );
      row.appendChild(actions); scanBody.appendChild(row);
    });
    window.lucide?.createIcons();
  }
  async function loadScanJobs() {
    if (!scanBody) return;
    const loading = document.createElement('tr'); const cell = appendTextCell(loading, '正在加载扫描任务'); cell.colSpan = 6; scanBody.replaceChildren(loading);
    try { const response = await DemoApi.domainRequest('/api/import-scans'); scanState.jobs = response.data || []; renderScanJobs(); setScanStatus(''); }
    catch (error) { scanState.jobs = []; renderScanJobs(); setScanStatus(error.message || '扫描任务加载失败'); }
  }
  function openScanDialog(job = null) {
    scanState.editingId = job?.id ?? null; scanForm.reset(); scanForm.elements.file_pattern.value = job?.file_pattern || '*.xlsx;*.xls;*.csv;*.zip'; scanForm.elements.cron_expr.value = job?.cron_expr || '* * * * *'; scanForm.elements.source_type.value = job?.source_type || 'auto'; scanForm.elements.enabled.checked = job ? Boolean(job.enabled) : true;
    if (job) { scanForm.elements.task_name.value = job.task_name || ''; scanForm.elements.folder_path.value = job.folder_path || ''; }
    document.querySelector('#scanDialogTitle').textContent = job ? '编辑扫描任务' : '新增扫描任务'; scanDialog.showModal(); scanForm.elements.task_name.focus();
  }
  async function mutateScan(message, operation) {
    setScanStatus(message);
    try { await operation(); await loadScanJobs(); }
    catch (error) { setScanStatus(error.message || '扫描任务操作失败'); }
  }
  function runScanJob(job) { mutateScan(`正在扫描 ${job.task_name}…`, () => DemoApi.domainRequest(`/api/import-scans/${Number(job.id)}/run`, { method: 'POST' })); }
  function toggleScanJob(job) {
    if (job.enabled) return mutateScan('正在停用任务…', () => DemoApi.domainRequest(`/api/import-scans/${Number(job.id)}`, { method: 'DELETE' }));
    return mutateScan('正在启用任务…', () => DemoApi.domainRequest(`/api/import-scans/${Number(job.id)}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ enabled: true }) }));
  }
  const renderScanDetailRows = (selector, rows, columns, emptyText) => {
    const body = document.querySelector(selector); body.replaceChildren();
    if (!rows.length) { const row = document.createElement('tr'); const cell = appendTextCell(row, emptyText); cell.colSpan = columns.length; body.appendChild(row); return; }
    rows.slice(0, 20).forEach((item) => { const row = document.createElement('tr'); columns.forEach((column) => appendTextCell(row, column(item))); body.appendChild(row); });
  };
  async function openScanDetails(job) {
    document.querySelector('#scanDetailTitle').textContent = `${job.task_name || '扫描任务'}记录`; scanDetailDialog.showModal();
    renderScanDetailRows('[data-scan-runs]', [], Array.from({ length: 5 }, () => () => ''), '加载中'); renderScanDetailRows('[data-scan-files]', [], Array.from({ length: 4 }, () => () => ''), '加载中');
    try {
      const [runs, files] = await Promise.all([DemoApi.domainRequest(`/api/import-scans/${Number(job.id)}/runs`), DemoApi.domainRequest(`/api/import-scans/${Number(job.id)}/files`)]);
      renderScanDetailRows('[data-scan-runs]', runs.data || [], [(item) => formatScanTime(item.started_at), (item) => item.status, (item) => item.imported_count, (item) => item.blocked_count, (item) => item.failed_count], '暂无运行记录');
      renderScanDetailRows('[data-scan-files]', files.data || [], [(item) => item.source_filename, (item) => item.status, (item) => item.batch_id || '--', (item) => formatScanTime(item.updated_at)], '暂无文件记录');
    } catch (error) { setScanStatus(error.message || '扫描记录加载失败'); }
  }
  document.querySelector('[data-scan-create]')?.addEventListener('click', () => openScanDialog());
  document.querySelectorAll('[data-scan-close]').forEach((button) => button.addEventListener('click', () => scanDialog.close()));
  document.querySelectorAll('[data-scan-detail-close]').forEach((button) => button.addEventListener('click', () => scanDetailDialog.close()));
  scanForm?.addEventListener('submit', (event) => {
    event.preventDefault(); const data = new FormData(scanForm); const payload = { task_name: data.get('task_name'), folder_path: data.get('folder_path'), file_pattern: data.get('file_pattern'), source_type: data.get('source_type'), cron_expr: data.get('cron_expr'), enabled: data.get('enabled') === 'on' }; const jobId = scanState.editingId;
    mutateScan(jobId ? '正在更新任务…' : '正在创建任务…', async () => { await DemoApi.domainRequest(jobId ? `/api/import-scans/${Number(jobId)}` : '/api/import-scans', { method: jobId ? 'PUT' : 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) }); scanDialog.close(); });
  });
  load();
  loadScanJobs();
})();
