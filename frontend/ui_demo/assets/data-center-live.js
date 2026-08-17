(function () {
  const showToast = (message, options) => window.DemoShell?.showToast?.(message, options);
  const fileInput = document.querySelector('[data-import-file]');
  const previewButton = document.querySelector('[data-import-preview]');
  const confirmButton = document.querySelector('[data-import-confirm]');
  const panel = document.querySelector('[data-import-preview-panel]');
  const status = document.querySelector('[data-import-status]');
  const historyStatus = document.querySelector('[data-import-history-status]');
  const fields = document.querySelector('[data-import-fields]');
  const quality = document.querySelector('[data-import-quality]');
  const sourceType = document.querySelector('[data-import-source-type]');
  const history = document.querySelector('[data-import-history]');
  let preview = null;
  let previewQueue = [];
  let previewErrors = [];
  let activePreviewIndex = 0;
  let settings = null;
  let importCapabilities = {};
  const text = (node, value) => { node.textContent = value; };
  const renderDataState = (state, details) => DemoApi.renderDataState(status, state, details);
  const sourceLabels = { product_day: '商品日度', dmp_product_day: 'DMP商品日度', store_day: '店铺日度', product_week: '商品周度', product_month: '商品月度', promotion_channel_day: '推广渠道日度', promotion_campaign_day: '推广计划日度', promotion_unit_day: '推广单元日度', promotion_product_day: '推广商品日度', refund_day: '退款日度', customer_day: '新老客日度' };
  const shortHash = (value) => value && value.length > 16 ? `${value.slice(0, 8)}...${value.slice(-6)}` : (value || '--');
  const loadSettings = async () => { try { settings = (await DemoApi.domainRequest('/api/settings')).data; } catch (_) { settings = null; } };
  const render = (result) => {
    preview = result;
    panel.hidden = false;
    if (result.invalid_field_count) {
      quality.title = `${result.invalid_field_count} field warnings; valid fields can still be imported`;
    } else {
      quality.removeAttribute('title');
    }
    const tabs = document.querySelector('[data-import-preview-tabs]');
    tabs?.replaceChildren(...previewQueue.map((item, index) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.role = 'tab';
      button.setAttribute('data-import-preview-file', String(index));
      button.setAttribute('aria-selected', String(index === activePreviewIndex));
      button.setAttribute('aria-controls', 'data-import-preview-tabpanel');
      button.tabIndex = index === activePreviewIndex ? 0 : -1;
      button.textContent = item.source_filename || `文件 ${index + 1}`;
      button.addEventListener('click', () => { activePreviewIndex = index; render(previewQueue[activePreviewIndex]); });
      button.addEventListener('keydown', (event) => {
        if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
        event.preventDefault();
        const tabs = [...document.querySelectorAll('[data-import-preview-file]')];
        const current = tabs.indexOf(event.currentTarget);
        const next = event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1 : (current + (event.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length;
        tabs[next]?.focus();
        tabs[next]?.click();
      });
      return button;
    }));
    const range = result.date_range?.start ? `；日期 ${result.date_range.start} 至 ${result.date_range.end}` : '';
    const estimate = result.estimated_changes?.available ? `；预计新增 ${result.estimated_changes.inserted} / 更新 ${result.estimated_changes.updated}` : '';
    const detectedSource = sourceLabels[result.source_type] || result.source_type || '未知报表';
    const governance = result.source_resolution ? `；字段治理：主源重叠 ${result.source_resolution.primary_overlap_fields?.length || 0}，DMP独有 ${result.source_resolution.dmp_unique_fields?.length || 0}，对比记录 ${result.source_resolution.field_comparisons?.length || 0}` : '';
    const excluded = result.excluded_summary_rows ? `；剔除汇总行 ${result.excluded_summary_rows}` : '';
    quality.textContent = `已识别为${detectedSource}；有效 ${result.valid_rows}/${result.total_rows} 行，商品 ${result.product_count} 个，重复业务键 ${result.duplicate_keys} 个${excluded}${range}${estimate}${governance}`;
    const details = (result.invalid_details || []).slice(0, 25).map((item) => `第 ${item.row_number || '--'} 行 · ${item.standard_field || '--'} · ${item.raw_value || '--'} · ${item.reason || item.message}`).join('；');
    if (details) quality.title = details;
    const detail = document.querySelector('[data-import-quality-detail]');
    if (detail && !(result.invalid_details || []).length && result.invalid_field_count) {
      detail.textContent = (result.field_warnings || []).slice(0, 25)
        .map((item) => `row ${item.row_number || '--'} / ${item.standard_field || '--'} / ${item.reason || 'invalid field'}`)
        .join('; ');
    }
    if (detail) detail.textContent = details || '未发现异常行';
    fields.replaceChildren(...result.fields.map((field) => {
      const row = document.createElement('tr');
      const source = document.createElement('td'); source.textContent = field.source_column; row.appendChild(source);
      const inferred = document.createElement('td'); inferred.textContent = DemoLabels.label('match', field.inferred_type || 'empty'); row.appendChild(inferred);
      const mapping = document.createElement('select'); mapping.className = 'select'; mapping.dataset.importMapping = field.source_column; mapping.setAttribute('aria-label', `字段映射：${field.source_column}`);
      ['', ...(preview.mapping_schema?.allowed || [])].forEach((key) => mapping.add(new Option(key ? DemoLabels.label('field', key, key) : '未映射', key)));
      mapping.value = field.standard_key || '';
      mapping.addEventListener('change', () => {
        Object.entries(result.mapping).forEach(([key, value]) => { if (value === field.source_column) delete result.mapping[key]; });
        if (mapping.value) result.mapping[mapping.value] = field.source_column;
        field.standard_key = mapping.value;
        field.match_status = mapping.value ? 'manual' : 'unmatched';
        result.required_unmapped = (result.mapping_schema?.required || []).filter((key) => !result.mapping[key]);
        text(status, result.required_unmapped.length ? `缺少必填映射：${result.required_unmapped.map((key) => DemoLabels.label('field', key, key)).join('、')}` : '映射完整，可以确认导入。');
      });
      const mapCell = document.createElement('td'); mapCell.appendChild(mapping); row.appendChild(mapCell);
      const matchCell = document.createElement('td'); matchCell.textContent = DemoLabels.label('match', field.match_status || 'unmatched'); row.appendChild(matchCell);
      const sample = document.createElement('td'); sample.textContent = field.sample_value || '--'; row.appendChild(sample);
      return row;
    }));
    if (result.required_unmapped.length) text(status, `缺少必填映射：${result.required_unmapped.map((key) => DemoLabels.label('field', key, key)).join('、')}`);
    else text(status, '预览通过，可以确认导入。');
    if (!result.required_unmapped.length && (result.invalid_rows || result.duplicate_keys)) {
      text(status, '质量校验未通过，请修正文件后重新预览。');
    }
  };
  previewButton?.addEventListener('click', async () => {
    const selectedFiles = Array.from(fileInput.files || []);
    if (!selectedFiles.length) return text(status, '请选择表格文件。');
    previewButton.disabled = true; text(status, '正在读取并校验文件…');
    try {
      previewQueue = [];
      previewErrors = [];
      activePreviewIndex = 0;
      for (const [index, file] of selectedFiles.entries()) {
        text(status, `正在预览 ${index + 1}/${selectedFiles.length}：${file.name}`);
        const body = new FormData(); body.append('file', file);
        const mapping = settings?.mapping_templates?.[sourceType.value];
        if (mapping) body.append('mapping_template', JSON.stringify(mapping));
        try {
          const response = await DemoApi.domainRequest(`/api/imports/preview?source_type=${encodeURIComponent(sourceType.value)}`, { method: 'POST', body });
          importCapabilities = response.capabilities || importCapabilities;
          previewQueue.push(response.data);
        } catch (error) {
          previewErrors.push(`${file.name}：${error.message || '预览失败'}`);
        }
      }
      preview = previewQueue[0] || null;
      if (preview) render(preview);
      else panel.hidden = true;
      const summary = `已预览 ${previewQueue.length}/${selectedFiles.length} 个文件`;
      text(status, previewErrors.length ? `${summary}；失败：${previewErrors.join('；')}` : `${summary}，确认后按顺序导入。`);
      showToast(previewErrors.length ? `预览完成：成功 ${previewQueue.length}/${selectedFiles.length} 个文件，失败 ${previewErrors.length} 个` : `预览完成：${previewQueue.length} 个文件，可确认导入`, { duration: 4500 });
    } catch (error) { text(status, error.message || '预览失败。'); showToast(`预览失败：${error.message || '请检查文件'}`, { duration: 5000 }); }
    finally { previewButton.disabled = false; }
  });
  confirmButton?.addEventListener('click', async () => {
    if (Object.keys(importCapabilities).length && !DemoApi.can({ capabilities: importCapabilities }, 'can_import')) return text(status, '当前数据源不允许导入');
    const pending = previewQueue.length ? previewQueue : (preview ? [preview] : []);
    if (pending.some((item) => item.invalid_rows || item.duplicate_keys)) return text(status, '质量校验未通过，请修正源文件后重新预览。');
    if (!pending.length || pending.some((item) => item.required_unmapped.length)) return text(status, '请先完成必填字段映射。');
    confirmButton.disabled = true; text(status, '正在事务导入…');
    const failures = [];
    const failedPreviews = [];
    try {
      const results = [];
      for (const [index, item] of pending.entries()) {
        text(status, `正在导入 ${index + 1}/${pending.length}：${item.source_filename || '表格文件'}`);
        try {
          const response = await DemoApi.domainRequest('/api/imports', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({preview_id: item.id, mapping: item.mapping}) });
          results.push(response.data);
        } catch (error) {
          failures.push(`${item.source_filename || '表格文件'}：${error.message || '导入失败'}`);
          failedPreviews.push(item);
        }
      }
      const inserted = results.reduce((sum, item) => sum + Number(item.inserted_count || 0), 0);
      const updated = results.reduce((sum, item) => sum + Number(item.updated_count || 0), 0);
      const resolution = results.reduce((sum, item) => {
        const current = item.source_resolution || {};
        return { fallback_filled: sum.fallback_filled + Number(current.fallback_filled || 0), reference_only: sum.reference_only + Number(current.reference_only || 0), conflicts: sum.conflicts + Number(current.conflicts || 0) };
      }, { fallback_filled: 0, reference_only: 0, conflicts: 0 });
      const summary = `已导入 ${results.length}/${pending.length} 个文件；新增 ${inserted}，更新 ${updated}；DMP补齐 ${resolution.fallback_filled}，参考 ${resolution.reference_only}，冲突 ${resolution.conflicts}${resolution.conflicts ? '（按主源保留，DMP值留痕）' : ''}`;
      text(status, failures.length ? `${summary}；失败：${failures.join('；')}` : `${summary}。`);
      showToast(failures.length ? `导入完成：成功 ${results.length}/${pending.length} 个文件，失败 ${failures.length} 个` : `导入完成：${results.length} 个文件，新增 ${inserted}，更新 ${updated}`, { duration: 5000 });
      previewQueue = failedPreviews;
      loadHistory();
      confirmButton.disabled = !failures.length;
    } catch (error) { text(status, error.message || '导入失败，未写入半成品。'); showToast(`导入失败：${error.message || '未写入半成品'}`, { duration: 5000 }); }
    finally { if (failures.length || status.textContent.includes('失败')) confirmButton.disabled = false; }
  });
  async function loadHistory() {
    if (historyStatus) text(historyStatus, '正在加载导入批次');
    try {
      const response = await DemoApi.domainRequest('/api/imports');
      importCapabilities = response.capabilities || importCapabilities;
      const batches = response.data;
      const summaryBatches = document.querySelector('[data-data-center-summary="batches"]');
      const summaryLatest = document.querySelector('[data-data-center-summary="latest"]');
      if (summaryBatches) summaryBatches.textContent = String(batches.length).padStart(2, '0');
      const latestDate = batches.map((batch) => batch.quality_summary?.date_range?.end).filter(Boolean).sort().pop();
      if (summaryLatest) summaryLatest.textContent = latestDate || '--';
      history.replaceChildren(...batches.map((batch) => {
        const row = document.createElement('tr');
        const range = batch.quality_summary?.date_range;
        const resolution = batch.quality_summary?.source_resolution || {};
        const qualityText = `${DemoLabels.label('quality', batch.quality_summary?.conclusion, batch.status === 'completed' ? '通过' : '--')} · 补齐 ${resolution.fallback_filled || 0} · 参考 ${resolution.reference_only || 0} · 冲突 ${resolution.conflicts || 0}${resolution.conflicts ? '（主源保留）' : ''} · 汇总剔除 ${batch.quality_summary?.excluded_summary_rows || 0}`;
        [batch.source_filename, sourceLabels[batch.source_type] || '其他报表', shortHash(batch.source_hash), range?.start && range?.end ? `${range.start} ~ ${range.end}` : '--', qualityText, `${batch.inserted_count || 0} / ${batch.updated_count || 0} / ${batch.invalid_rows || 0}`, batch.completed_at || '--'].forEach((value, index) => { const cell = document.createElement('td'); cell.textContent = value; if (index === 2) cell.title = batch.source_hash || ''; if (index === 4) cell.title = JSON.stringify(resolution); if (index === 5) cell.className = 'num'; row.appendChild(cell); });
        const cell = document.createElement('td'); const button = document.createElement('button'); button.className = 'button button--ghost'; button.type = 'button'; button.textContent = batch.status === 'completed' ? '撤销' : '已撤销'; button.disabled = batch.status !== 'completed' || (Object.keys(importCapabilities).length > 0 && !DemoApi.can({ capabilities: importCapabilities }, 'can_revert'));
        button.addEventListener('click', async () => {
          if (button.disabled) return;
          const impact = `影响：撤销 ${batch.source_filename}，恢复该批次覆盖前的数据；${batch.inserted_count || 0} 条新增记录将被移除，${batch.updated_count || 0} 条更新将回退。`;
          if (!window.confirm(`确认撤销该批次？\n${impact}`)) return;
          button.disabled = true;
          try {
            await DemoApi.domainRequest(`/api/imports/${encodeURIComponent(batch.id)}/revert`, { method: 'POST' });
            text(status, '批次已撤销。');
            showToast(`已撤销导入批次：${batch.source_filename}`, { duration: 4500 });
            await loadHistory();
          } catch (error) {
            text(status, error.message || '批次撤销失败，请重试。');
            showToast(`批次撤销失败：${error.message || '请重试'}`, { duration: 5000 });
          } finally {
            if (button.isConnected) button.disabled = false;
          }
        }); cell.appendChild(button); row.appendChild(cell); return row;
      }));
      if (historyStatus) text(historyStatus, batches.length ? `共 ${batches.length} 个批次` : '尚无导入批次');
      if (!batches.length) history.innerHTML = '<tr><td colspan="8">尚无导入批次</td></tr>';
    } catch (error) { history.innerHTML = '<tr><td colspan="8">导入历史加载失败</td></tr>'; if (historyStatus) text(historyStatus, error.message || '导入历史加载失败'); }
  }
  document.querySelector('[data-import-history-refresh]')?.addEventListener('click', loadHistory);
  loadSettings().finally(loadHistory);
})();

(function () {
  const map = document.querySelector('[data-capability-map]');
  if (!map) return;

  const table = document.querySelector('[data-capability-table]');
  const status = document.querySelector('[data-capability-status]');
  const unsupported = document.querySelector('[data-unsupported-capabilities]');
  const search = document.querySelector('[data-capability-filter="search"]');
  const availability = document.querySelector('[data-capability-filter="availability"]');
  const dialog = document.querySelector('[data-capability-detail]');
  const detailTitle = document.querySelector('#data-capability-detail-title');
  const detailSubtitle = document.querySelector('[data-capability-detail-subtitle]');
  const detailBody = document.querySelector('[data-capability-detail-body]');
  const closeButton = document.querySelector('[data-capability-detail-close]');
  let catalog = null;
  let trigger = null;

  const stateLabels = {
    available: '可用', partial: '部分可用', 'no-data': '暂无数据',
    'missing-fields': '字段缺失', 'source-unavailable': '来源不可用',
    'insufficient-data': '数据不足', 'calculation-failed': '计算失败'
  };
  const make = (tag, text, className) => {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    if (className) node.className = className;
    return node;
  };
  const listText = (items) => items?.length ? items.join(' / ') : '--';
  const coverageText = (coverage) => {
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
    detailTitle.textContent = domain.label;
    detailSubtitle.textContent = `${stateLabels[domain.availability] || domain.availability} · ${coverageText(domain.coverage)}`;
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
      detailSection('原始字段', domain.raw_fields.map((field) => `${field.label}: ${stateLabels[field.availability] || field.availability}`)),
      detailSection('派生指标', domain.derived_metrics.map((metric) => `${metric.label} = ${metric.formula} (${stateLabels[metric.availability] || metric.availability})`)),
      detailSection('消费页面', domain.consumer_pages),
      detailSection('限制', domain.limitations)
    );
    dialog.showModal();
    closeButton.focus();
  };
  const closeDetail = () => {
    if (dialog.open) dialog.close();
    trigger?.focus();
  };
  closeButton?.addEventListener('click', closeDetail);
  dialog?.addEventListener('cancel', (event) => { event.preventDefault(); closeDetail(); });
  dialog?.addEventListener('click', (event) => { if (event.target === dialog) closeDetail(); });

  const renderUnsupported = () => {
    unsupported.replaceChildren(make('h4', '当前明确不支持'));
    const list = make('div', undefined, 'unsupported-capabilities__list');
    catalog.unsupported_capabilities.forEach((item) => {
      const boundary = make('div', undefined, 'unsupported-capability');
      boundary.append(make('strong', item.label), make('span', `缺少前提：${item.prerequisite}`));
      list.append(boundary);
    });
    unsupported.append(list);
  };
  const renderRows = () => {
    const query = (search.value || '').trim().toLowerCase();
    const selected = availability.value;
    const domains = catalog.domains.filter((domain) => {
      const matchesQuery = !query || `${domain.key} ${domain.label} ${domain.consumer_pages.join(' ')}`.toLowerCase().includes(query);
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
        `${domain.raw_fields.filter((field) => field.availability === 'available').length}/${domain.raw_fields.length}`,
        `${domain.derived_metrics.filter((metric) => metric.availability === 'available').length}/${domain.derived_metrics.length}`,
        listText(domain.consumer_pages), listText(domain.limitations)
      ].forEach((value) => row.append(make('td', value)));
      const action = make('td');
      const button = make('button', '查看', 'button button--ghost');
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
    status.textContent = `显示 ${domains.length} / ${catalog.domains.length} 个数据域`;
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
      catalog = response.data;
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
      const button = make('button', '查看', 'button button--ghost');
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
      catalog = response.data;
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
