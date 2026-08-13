(function () {
  const fileInput = document.querySelector('[data-import-file]');
  const previewButton = document.querySelector('[data-import-preview]');
  const confirmButton = document.querySelector('[data-import-confirm]');
  const panel = document.querySelector('[data-import-preview-panel]');
  const status = document.querySelector('[data-import-status]');
  const fields = document.querySelector('[data-import-fields]');
  const quality = document.querySelector('[data-import-quality]');
  const sourceType = document.querySelector('[data-import-source-type]');
  const history = document.querySelector('[data-import-history]');
  let preview = null;
  const text = (node, value) => { node.textContent = value; };
  const render = (result) => {
    panel.hidden = false;
    const range = result.date_range?.start ? `；日期 ${result.date_range.start} 至 ${result.date_range.end}` : '';
    const estimate = result.estimated_changes?.available ? `；预计新增 ${result.estimated_changes.inserted} / 更新 ${result.estimated_changes.updated}` : '';
    quality.textContent = `有效 ${result.valid_rows}/${result.total_rows} 行，商品 ${result.product_count} 个，重复业务键 ${result.duplicate_keys} 个${range}${estimate}`;
    const details = (result.invalid_details || []).slice(0, 3).map((item) => `Row ${item.row_number || '--'}: ${item.message}`).join('; ');
    if (details) quality.title = details;
    const detail = document.querySelector('[data-import-quality-detail]');
    if (detail) detail.textContent = details || '未发现异常行';
    fields.replaceChildren(...result.fields.map((field) => {
      const row = document.createElement('tr');
      const source = document.createElement('td'); source.textContent = field.source_column; row.appendChild(source);
      const mapping = document.createElement('select'); mapping.className = 'select'; mapping.dataset.importMapping = field.source_column;
      ['', ...(preview.mapping_schema?.allowed || [])].forEach((key) => mapping.add(new Option(key || '未映射', key)));
      mapping.value = field.standard_key || '';
      mapping.addEventListener('change', () => {
        Object.entries(preview.mapping).forEach(([key, value]) => { if (value === field.source_column) delete preview.mapping[key]; });
        if (mapping.value) preview.mapping[mapping.value] = field.source_column;
        preview.required_unmapped = (preview.mapping_schema?.required || []).filter((key) => !preview.mapping[key]);
        text(status, preview.required_unmapped.length ? `缺少必填映射：${preview.required_unmapped.join('、')}` : '映射完整，可以确认导入。');
      });
      const mapCell = document.createElement('td'); mapCell.appendChild(mapping); row.appendChild(mapCell);
      const sample = document.createElement('td'); sample.textContent = field.sample_value || '--'; row.appendChild(sample);
      return row;
    }));
    if (result.required_unmapped.length) text(status, `缺少必填映射：${result.required_unmapped.join('、')}`);
    else text(status, '预览通过，可以确认导入。');
    if (!result.required_unmapped.length && (result.invalid_rows || result.duplicate_keys)) {
      text(status, 'Quality validation failed. Fix the source file and preview again.');
    }
  };
  previewButton?.addEventListener('click', async () => {
    const file = fileInput.files?.[0];
    if (!file) return text(status, '请选择 Excel 文件。');
    previewButton.disabled = true; text(status, '正在读取并校验文件…');
    try {
      const body = new FormData(); body.append('file', file);
      const response = await DemoApi.domainRequest(`/api/imports/preview?source_type=${encodeURIComponent(sourceType.value)}`, { method: 'POST', body });
      preview = response.data; render(preview);
    } catch (error) { text(status, error.message || '预览失败。'); }
    finally { previewButton.disabled = false; }
  });
  confirmButton?.addEventListener('click', async () => {
    if (preview && (preview.invalid_rows || preview.duplicate_keys)) return text(status, 'Quality validation failed. Fix the source file and preview again.');
    if (!preview || preview.required_unmapped.length) return text(status, '请先完成必填字段映射。');
    confirmButton.disabled = true; text(status, '正在事务导入…');
    try {
      const response = await DemoApi.domainRequest('/api/imports', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({preview_id: preview.id, mapping: preview.mapping}) });
      text(status, `导入完成：新增 ${response.data.inserted_count} 行，更新 ${response.data.updated_count} 行。批次 ${response.data.id}`);
      loadHistory();
      confirmButton.disabled = true;
    } catch (error) { text(status, error.message || '导入失败，未写入半成品。'); }
    finally { if (status.textContent.includes('失败')) confirmButton.disabled = false; }
  });
  async function loadHistory() {
    try {
      const response = await DemoApi.domainRequest('/api/imports');
      const batches = response.data;
      history.replaceChildren(...batches.map((batch) => {
        const row = document.createElement('tr');
        [batch.source_filename, batch.status, `${batch.inserted_count} / ${batch.updated_count}`, batch.completed_at || '--'].forEach((value, index) => { const cell = document.createElement('td'); cell.textContent = value; if (index === 2) cell.className = 'num'; row.appendChild(cell); });
        const cell = document.createElement('td'); const button = document.createElement('button'); button.className = 'button button--ghost'; button.type = 'button'; button.textContent = batch.status === 'completed' ? '撤销' : '已撤销'; button.disabled = batch.status !== 'completed';
        button.addEventListener('click', async () => { await DemoApi.domainRequest(`/api/imports/${encodeURIComponent(batch.id)}/revert`, {method:'POST'}); text(status, '批次已撤销。'); loadHistory(); }); cell.appendChild(button); row.appendChild(cell); return row;
      }));
      if (!batches.length) history.innerHTML = '<tr><td colspan="5">尚无导入批次</td></tr>';
    } catch (error) { history.innerHTML = '<tr><td colspan="5">导入历史加载失败</td></tr>'; }
  }
  document.querySelector('[data-import-history-refresh]')?.addEventListener('click', loadHistory);
  loadHistory();
})();
