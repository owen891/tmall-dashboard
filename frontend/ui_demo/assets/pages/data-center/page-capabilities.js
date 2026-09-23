(function () {
  const map = document.querySelector('[data-page-capability-map]');
  if (!map) return;

  const table = document.querySelector('[data-page-capability-table]');
  const status = document.querySelector('[data-page-capability-status]');
  const search = document.querySelector('[data-page-capability-filter="search"]');
  const support = document.querySelector('[data-page-capability-filter="support"]');
  const dialog = document.querySelector('[data-page-capability-detail]');
  const detailTitle = document.querySelector('#page-capability-detail-title');
  const detailSubtitle = document.querySelector('[data-page-capability-detail-subtitle]');
  const detailBody = document.querySelector('[data-page-capability-detail-body]');
  const closeButton = document.querySelector('[data-page-capability-detail-close]');
  const labels = { supported: '可用', conditional: '受条件限制', unsupported: '明确不支持', unclassified: '未分类' };
  let catalog = null;
  let pageCapabilityTrigger = null;

  const make = (tag, value, className) => {
    const node = document.createElement(tag);
    if (value !== undefined) node.textContent = value;
    if (className) node.className = className;
    return node;
  };
  const list = (items) => Array.isArray(items) && items.length ? items.join(' / ') : '--';
  const capabilityRows = () => (catalog?.pages || []).flatMap((page) =>
    (page.capabilities || []).map((capability) => ({ page, capability }))
  );
  const closeDetail = () => {
    if (dialog?.open) dialog.close();
    pageCapabilityTrigger?.focus();
  };
  const openDetail = (page, capability, button) => {
    pageCapabilityTrigger = button;
    detailTitle.textContent = `${page.label} · ${capability.label}`;
    detailSubtitle.textContent = `${labels[capability.support_level] || capability.support_level} · ${capability.interaction_state === 'enabled' ? '当前可执行' : '当前不可执行'}`;
    const sections = [
      ['证据等级', [capability.evidence_level || 'insufficient']],
      ['数据新鲜度', [
        `覆盖范围: ${capability.freshness?.start || '--'} ~ ${capability.freshness?.end || '--'}`,
        `最近更新: ${capability.freshness?.latest_update || '--'}`,
      ]],
      ['数据依赖', capability.data_domains],
      ['指标', capability.metric_keys],
      ['正式 API', capability.api_endpoints],
      ['缺失前提', capability.missing_prerequisites],
      ['限制', capability.limitations],
      ['关联弹窗', (catalog.surfaces || []).filter((surface) => surface.trigger_capability === capability.key).map((surface) => `${surface.label} (${surface.modal_kind})`)],
    ];
    detailBody.replaceChildren(...sections.map(([title, values]) => {
      const section = make('section', undefined, 'capability-detail-section');
      section.append(make('h4', title), make('p', list(values), 'panel__hint'));
      return section;
    }));
    dialog.showModal();
    closeButton.focus();
  };
  const renderRows = () => {
    const query = (search?.value || '').trim().toLowerCase();
    const selected = support?.value || '';
    const rows = capabilityRows().filter(({ page, capability }) => {
      const matchesQuery = !query || `${page.label} ${page.key} ${capability.label} ${capability.key}`.toLowerCase().includes(query);
      return matchesQuery && (!selected || capability.support_level === selected);
    });
    table.replaceChildren(...rows.map(({ page, capability }) => {
      const row = document.createElement('tr');
      const pageCell = make('td');
      const name = make('div', undefined, 'table-name');
      name.append(make('strong', page.label), make('span', page.key));
      pageCell.append(name);
      row.append(pageCell, make('td', page.core_question), make('td', capability.label));
      row.append(make('td', `${labels[capability.support_level] || capability.support_level} / ${capability.interaction_state === 'enabled' ? '可执行' : '不可执行'}`));
      row.append(make('td', list(capability.data_domains)));
      const surfaceCount = (catalog.surfaces || []).filter((surface) => surface.trigger_capability === capability.key).length;
      row.append(make('td', surfaceCount ? `${surfaceCount} 个` : '--'));
      const action = make('td');
      const button = make('button', '查看', 'ui-button ui-button--ghost');
      button.type = 'button';
      button.addEventListener('click', () => openDetail(page, capability, button));
      action.append(button); row.append(action);
      return row;
    }));
    if (!rows.length) {
      const row = document.createElement('tr');
      const cell = make('td', '没有符合当前筛选的页面能力');
      cell.colSpan = 7; row.append(cell); table.append(row);
    }
    status.textContent = `显示 ${rows.length} / ${capabilityRows().length} 项能力`;
  };
  const render = () => {
    const summary = catalog.summary || {};
    const counts = { pages: summary.page_count, supported: summary.supported, conditional: summary.conditional, unsupported: summary.unsupported };
    Object.entries(counts).forEach(([key, value]) => {
      const node = document.querySelector(`[data-page-capability-count="${key}"]`);
      if (node) node.textContent = value ?? 0;
    });
    renderRows();
  };
  const load = async () => {
    DemoApi.renderDataState(status, 'loading');
    try {
      const response = await DemoApi.domainRequest('/api/page-capabilities');
      const source = response.data || {};
      catalog = {
        ...source,
        summary: source.summary || {},
        pages: (Array.isArray(source.pages) ? source.pages : []).map((page) => ({
          ...page,
          capabilities: Array.isArray(page.capabilities) ? page.capabilities : [],
        })),
        surfaces: Array.isArray(source.surfaces) ? source.surfaces : [],
      };
      render();
    } catch (error) {
      table.replaceChildren();
      DemoApi.renderDataState(status, 'source-unavailable', { message: error.message, retry: load });
    }
  };
  closeButton?.addEventListener('click', closeDetail);
  dialog?.addEventListener('cancel', (event) => { event.preventDefault(); closeDetail(); });
  dialog?.addEventListener('click', (event) => { if (event.target === dialog) closeDetail(); });
  search?.addEventListener('input', () => catalog && renderRows());
  support?.addEventListener('change', () => catalog && renderRows());
  load();
})();
