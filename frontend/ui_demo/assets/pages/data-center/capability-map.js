(function () {
  const map = document.querySelector('[data-capability-map]');
  if (!map) return;

  const table = document.querySelector('[data-capability-table]');
  const status = document.querySelector('[data-capability-status]');
  const unsupported = document.querySelector('[data-unsupported-capabilities]');
  const search = document.querySelector('[data-capability-filter="search"]');
  const availability = document.querySelector('[data-capability-filter="availability"]');
  const capabilityDrawer = (() => {
    const template = document.querySelector('[data-capability-detail]');
    if (!template || !window.TmallUI?.detailDrawer) return null;
    const drawer = window.TmallUI.detailDrawer({ title: '数据域详情', description: '证据等级、新鲜度、来源与限制', size: 'md' });
    drawer.body.append(template.content.cloneNode(true));
    return drawer;
  })();
  const detailTitle = capabilityDrawer?.node.querySelector('.ui-drawer__copy h2');
  const detailSubtitle = capabilityDrawer?.node.querySelector('.ui-drawer__copy p');
  const detailBody = capabilityDrawer?.node.querySelector('[data-capability-detail-body]');
  let catalog = null;
  let trigger = null;

  const availabilityLabel = (value) => window.DemoLabels?.label('availability', value, value);
  const make = (tag, text, className) => {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    if (className) node.className = className;
    return node;
  };
  const listText = (items) => items?.length ? items.join(' / ') : '--';
  const coverageText = (coverage = {}) => {
    const range = coverage.start && coverage.end ? `${coverage.start} ~ ${coverage.end}` : '无日期范围';
    return `${coverage.row_count} 行 · ${coverage.entity_count} 个实体 · ${range}`;
  };
  const detailSection = (title, values) => {
    const section = make('section', undefined, 'capability-detail-section');
    section.append(make('h4', title));
    const list = make('div', undefined, 'chip-list');
    (values?.length ? values : ['--']).forEach((value) => list.append(make('span', value, 'chip')));
    section.append(list);
    return section;
  };
  const openDetail = (domain, button) => {
    trigger = button;
    if (!capabilityDrawer) return;
    detailTitle.textContent = domain.label;
    detailSubtitle.textContent = `${availabilityLabel(domain.availability)} · ${coverageText(domain.coverage)}`;
    detailBody.replaceChildren(
      detailSection('证据等级', [domain.evidence_level || 'insufficient']),
      detailSection('数据新鲜度', [
        `覆盖范围: ${domain.freshness?.start || '--'} ~ ${domain.freshness?.end || '--'}`,
        `最近更新: ${domain.freshness?.latest_update || '--'}`,
      ]),
      detailSection('来源表', domain.source_tables),
      detailSection('逐表覆盖', (domain.source_coverage || []).map((item) => `${item.table}: ${coverageText(item.coverage)}`)),
      detailSection('粒度', domain.grain),
      detailSection('来源批次', domain.source_batches),
      detailSection('原始字段', domain.raw_fields.map((field) => `${field.label}: ${availabilityLabel(field.availability)}`)),
      detailSection('派生指标', domain.derived_metrics.map((metric) => `${metric.label} = ${metric.formula} (${availabilityLabel(metric.availability)})`)),
      detailSection('消费页面', domain.consumer_pages),
      detailSection('限制', domain.limitations)
    );
    capabilityDrawer.open(trigger);
  };
  const closeDetail = () => capabilityDrawer?.close();

  const renderUnsupported = () => {
    unsupported.replaceChildren(make('h4', '当前明确不支持'));
    const list = make('div', undefined, 'unsupported-capabilities__list');
    (catalog.unsupported_capabilities || []).forEach((item) => {
      const boundary = make('div', undefined, 'unsupported-capability');
      boundary.append(make('strong', item.label), make('span', `缺少前提：${item.prerequisite}`));
      list.append(boundary);
    });
    unsupported.append(list);
  };
  const renderRows = () => {
    const query = (search.value || '').trim().toLowerCase();
    const selected = availability.value;
    const domains = (catalog.domains || []).filter((domain) => {
      const matchesQuery = !query || `${domain.key} ${domain.label} ${(domain.consumer_pages || []).join(' ')}`.toLowerCase().includes(query);
      return matchesQuery && (!selected || domain.availability === selected);
    });
    table.replaceChildren(...domains.map((domain) => {
      const row = document.createElement('tr');
      const name = make('td');
      const nameWrap = make('div', undefined, 'table-name');
      nameWrap.append(make('strong', domain.label), make('span', domain.key));
      name.append(nameWrap);
      row.append(name);
      [
        listText(domain.grain), coverageText(domain.coverage),
        `${(domain.raw_fields || []).filter((field) => field.availability === 'available').length}/${(domain.raw_fields || []).length}`,
        `${(domain.derived_metrics || []).filter((metric) => metric.availability === 'available').length}/${(domain.derived_metrics || []).length}`,
        listText(domain.consumer_pages), listText(domain.limitations)
      ].forEach((value) => row.append(make('td', value)));
      const action = make('td');
      const button = make('button', '查看', 'ui-button ui-button--ghost');
      button.type = 'button';
      button.dataset.capabilityDomain = domain.key;
      button.addEventListener('click', () => openDetail(domain, button));
      action.append(button); row.append(action);
      return row;
    }));
    if (!domains.length) {
      const row = document.createElement('tr'); const cell = make('td', '没有符合当前筛选的数据域');
      cell.colSpan = 8; row.append(cell); table.append(row);
    }
    status.textContent = `显示 ${domains.length} / ${(catalog.domains || []).length} 个数据域`;
  };
  const renderCatalog = () => {
    ['available', 'partial', 'no_data', 'source_unavailable'].forEach((key) => {
      const node = document.querySelector(`[data-capability-count="${key}"]`);
      if (node) node.textContent = catalog.summary[key] ?? 0;
      const summaryNode = document.querySelector(`[data-data-center-summary="${key}"]`);
      if (summaryNode) summaryNode.textContent = catalog.summary[key] ?? 0;
    });
    renderUnsupported();
    renderRows();
    window.lucide?.createIcons();
  };
  const loadCatalog = async () => {
    DemoApi.renderDataState(status, 'loading');
    try {
      const response = await DemoApi.domainRequest('/api/data-capabilities');
      const source = response.data || {};
      catalog = {
        ...source,
        summary: source.summary || {},
        domains: (Array.isArray(source.domains) ? source.domains : []).map((domain) => ({
          ...domain,
          coverage: domain.coverage || {},
          source_tables: Array.isArray(domain.source_tables) ? domain.source_tables : [],
          source_coverage: Array.isArray(domain.source_coverage) ? domain.source_coverage : [],
          source_batches: Array.isArray(domain.source_batches) ? domain.source_batches : [],
          raw_fields: Array.isArray(domain.raw_fields) ? domain.raw_fields : [],
          derived_metrics: Array.isArray(domain.derived_metrics) ? domain.derived_metrics : [],
          consumer_pages: Array.isArray(domain.consumer_pages) ? domain.consumer_pages : [],
          limitations: Array.isArray(domain.limitations) ? domain.limitations : [],
        })),
        unsupported_capabilities: Array.isArray(source.unsupported_capabilities) ? source.unsupported_capabilities : [],
      };
      renderCatalog();
    } catch (error) {
      table.replaceChildren();
      DemoApi.renderDataState(status, 'source-unavailable', { message: error.message, retry: loadCatalog });
    }
  };
  search?.addEventListener('input', () => catalog && renderRows());
  availability?.addEventListener('change', () => catalog && renderRows());
  loadCatalog();
})();

