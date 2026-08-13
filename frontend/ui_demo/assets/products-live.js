(function () {
  const limit = 20;
  const storageKey = 'tmall-products-field-view';
  const columnsStorageKey = 'tmall-products-visible-columns';
  const columnGroups = [
    { label: '基础信息', columns: [
      { key: 'tier', label: '分层' }, { key: 'style', label: '风格' }, { key: 'status', label: '状态' }
    ] },
    { label: '流量与转化', columns: [
      { key: 'visitors', label: '访客', format: 'number' }, { key: 'conversion', label: '支付转化率', format: 'percent' },
      { key: 'search_ratio', label: '搜索占比', format: 'percent' }, { key: 'search_conversion', label: '搜索转化率', format: 'percent' },
      { key: 'cart_rate', label: '加购率', format: 'percent' }, { key: 'fav_rate', label: '收藏率', format: 'percent' }
    ] },
    { label: '交易与退款', columns: [
      { key: 'payment_amount', label: '销售额', format: 'money' }, { key: 'payment_count', label: '支付件数', format: 'number' },
      { key: 'buyers', label: '支付买家数', format: 'number' }, { key: 'avg_order_value', label: '客单价', format: 'money' },
      { key: 'net_sales', label: '净销售额', format: 'money' }, { key: 'refund_amount', label: '退款金额', format: 'money' },
      { key: 'refund_rate', label: '退款率', format: 'percent' }
    ] },
    { label: '推广与付费', columns: [
      { key: 'ad_spend', label: '推广花费', format: 'money' }, { key: 'roi', label: 'ROI', format: 'decimal' },
      { key: 'paid_ratio', label: '付费占比', format: 'percent' }, { key: 'keyword_spend', label: '关键词花费', format: 'money' },
      { key: 'keyword_roi', label: '关键词 ROI', format: 'decimal' }, { key: 'crowd_spend', label: '人群花费', format: 'money' },
      { key: 'crowd_roi', label: '人群 ROI', format: 'decimal' }, { key: 'impressions', label: '展现量', format: 'number' },
      { key: 'ctr', label: '点击率', format: 'percent' }
    ] }
  ];
  const columns = columnGroups.flatMap((group) => group.columns);
  const columnsByKey = new Map(columns.map((column) => [column.key, column]));
  const templates = {
    operate: ['tier', 'style', 'status', 'payment_amount', 'visitors', 'conversion', 'refund_rate', 'ad_spend', 'roi'],
    select: ['tier', 'style', 'status', 'visitors', 'conversion', 'search_ratio', 'cart_rate', 'fav_rate', 'payment_amount', 'buyers', 'avg_order_value', 'refund_amount'],
    paid: ['status', 'ad_spend', 'roi', 'paid_ratio', 'keyword_spend', 'keyword_roi', 'crowd_spend', 'crowd_roi', 'impressions', 'ctr']
  };
  const focusableSelector = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';
  const $ = (selector, root = document) => root.querySelector(selector);
  const state = {
    rows: [],
    total: 0,
    page: 1,
    token: 0,
    drawerToken: 0,
    selected: new Set(),
    currentProduct: null,
    dateRange: null,
    starredOnly: false,
    view: 'operate',
    visibleColumns: [...templates.operate],
    searchTimer: null,
    facets: { tiers: [], styles: [], statuses: [] },
  };

  const money = (value) => `¥${Number(value || 0).toLocaleString('zh-CN', { maximumFractionDigits: 2 })}`;
  const number = (value) => Number(value || 0).toLocaleString('zh-CN');
  const percent = (value) => `${(Number(value || 0) * 100).toFixed(2)}%`;
  const decimal = (value) => Number(value || 0).toLocaleString('zh-CN', { maximumFractionDigits: 2 });
  const field = (item, name) => Number(item?.[name] || 0);
  const productId = (item) => String(item?.product_id || '');
  const salesOf = (item) => field(item, 'payment_amount') || field(item, 'total_gmv');
  const spendOf = (item) => field(item, 'ad_spend') || field(item, 'cost') || field(item, 'total_cost');
  const toast = (message) => window.DemoShell?.showToast ? window.DemoShell.showToast(message) : window.alert(message);
  const setStatus = (message) => {
    const status = $('[data-products-status]');
    if (status) status.textContent = message;
    window.DemoShell?.setStatus?.(message);
  };
  const jsonOptions = (body, method = 'POST') => ({
    method,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const asArray = (payload, key = 'data') => Array.isArray(payload) ? payload : (Array.isArray(payload?.[key]) ? payload[key] : []);

  function currentRange(detail) {
    const next = detail || window.TmallDateRange?.getState?.() || state.dateRange || {};
    state.dateRange = next;
    return next;
  }

  function currentMonthPeriod() {
    const range = currentRange();
    const raw = range.endDate || range.startDate || new Date().toISOString().slice(0, 10);
    return String(raw).slice(0, 7);
  }

  function setRowStatus(message) {
    const body = $('[data-products-body]');
    body.replaceChildren();
    const row = document.createElement('tr');
    const cell = row.insertCell();
    cell.colSpan = state.visibleColumns.length + 4;
    cell.textContent = message;
    row.appendChild(cell);
    body.appendChild(row);
  }

  function optionValues(key) {
    const facetKey = key === 'tier' ? 'tiers' : key === 'style' ? 'styles' : 'statuses';
    return [...new Set((state.facets[facetKey] || []).map((item) => String(item || '').trim()).filter(Boolean))].sort();
  }

  function fillSelect(selector, values, firstLabel) {
    const select = $(selector);
    const previous = select.value;
    select.replaceChildren();
    const first = document.createElement('option');
    first.value = '';
    first.textContent = firstLabel;
    select.appendChild(first);
    values.forEach((value) => {
      const option = document.createElement('option');
      option.value = value;
      option.textContent = value;
      select.appendChild(option);
    });
    if ([...select.options].some((option) => option.value === previous)) select.value = previous;
  }

  function filters() {
    return {
      search: $('[data-products-search]').value.trim(),
      tier: $('[data-products-tier]').value,
      style: $('[data-products-style]').value,
      status: $('[data-products-status-filter]').value,
      sort: $('[data-products-sort]').value || 'payment_amount',
      order: $('[data-products-order]').value || 'desc',
    };
  }

  function buildProductsUrl() {
    const params = new URLSearchParams({ dim: 'daily', limit: String(limit), offset: String((state.page - 1) * limit) });
    const range = currentRange();
    if (range.startDate) params.set('start', range.startDate);
    if (range.endDate) params.set('end', range.endDate);
    const current = filters();
    ['search', 'tier', 'style', 'status', 'sort', 'order'].forEach((key) => {
      if (current[key]) params.set(key, current[key]);
    });
    return `/api/products?${params.toString()}`;
  }

  function visibleRows() {
    return state.starredOnly ? state.rows.filter((item) => Number(item.starred || 0) === 1) : state.rows;
  }

  function updateKpis(rows) {
    const sales = rows.reduce((sum, item) => sum + salesOf(item), 0);
    const spend = rows.reduce((sum, item) => sum + spendOf(item), 0);
    $('[data-products-kpi="total"]').textContent = number(state.total);
    $('[data-products-kpi="sales"]').textContent = money(sales);
    $('[data-products-kpi="spend"]').textContent = money(spend);
    $('[data-products-kpi="roi"]').textContent = spend ? (sales / spend).toFixed(2) : '--';
  }

  function metric(label, value) {
    const item = document.createElement('div');
    item.className = 'drawer-metric';
    const labelEl = document.createElement('span');
    labelEl.textContent = label;
    const valueEl = document.createElement('strong');
    valueEl.textContent = value;
    item.append(labelEl, valueEl);
    return item;
  }

  function badge(value, fallback) {
    const item = document.createElement('span');
    item.className = 'badge badge--muted';
    item.textContent = value || fallback || '--';
    return item;
  }

  function editableSelect(item, key) {
    const select = document.createElement('select');
    select.className = 'select';
    select.setAttribute('aria-label', key === 'tier' ? '修改分层' : '修改风格');
    const current = String(item[key] || '');
    const values = [...new Set([current, ...optionValues(key)])].filter(Boolean);
    const empty = document.createElement('option');
    empty.value = '';
    empty.textContent = key === 'tier' ? '未分层' : '未分类';
    select.appendChild(empty);
    values.forEach((value) => {
      const option = document.createElement('option');
      option.value = value;
      option.textContent = value;
      select.appendChild(option);
    });
    select.value = current;
    select.addEventListener('change', async () => {
      await updateField(productId(item), key, select.value);
    });
    return select;
  }

  function addCell(row, content, className, fieldKey) {
    const cell = row.insertCell();
    if (className) cell.className = className;
    if (fieldKey) cell.dataset.fieldKey = fieldKey;
    if (content instanceof Node) cell.appendChild(content);
    else cell.textContent = content;
    return cell;
  }

  function formatColumnValue(item, column) {
    const value = column.key === 'payment_amount' ? salesOf(item) : column.key === 'ad_spend' ? spendOf(item) : field(item, column.key);
    if (column.format === 'money') return money(value);
    if (column.format === 'number') return number(value);
    if (column.format === 'percent') return percent(value);
    if (column.format === 'decimal') return decimal(value);
    return String(item[column.key] || '--');
  }

  function renderHeader() {
    const head = $('[data-products-head]');
    head.replaceChildren();
    const fixed = [
      ['select', ''], ['star', '收藏'], ['title', '商品']
    ];
    fixed.forEach(([key, label]) => {
      const th = document.createElement('th');
      th.dataset.fieldKey = key;
      if (key === 'select') {
        const check = document.createElement('input');
        check.type = 'checkbox';
        check.setAttribute('data-products-select-all', '');
        check.setAttribute('aria-label', '选择当前页商品');
        check.addEventListener('change', toggleSelectAll);
        th.appendChild(check);
      } else th.textContent = label;
      head.appendChild(th);
    });
    state.visibleColumns.forEach((key) => {
      const column = columnsByKey.get(key);
      if (!column) return;
      const th = document.createElement('th');
      th.dataset.fieldKey = key;
      th.textContent = column.label;
      if (column.format) th.className = 'num';
      head.appendChild(th);
    });
    const action = document.createElement('th');
    action.dataset.fieldKey = 'action';
    action.textContent = '操作';
    head.appendChild(action);
  }

  function toggleSelectAll(event) {
    visibleRows().forEach((item) => {
      const id = productId(item);
      if (event.currentTarget.checked) state.selected.add(id);
      else state.selected.delete(id);
    });
    renderTable();
  }

  function renderTable() {
    renderHeader();
    const body = $('[data-products-body]');
    body.replaceChildren();
    const rows = visibleRows();
    updateKpis(rows);
    if (!rows.length) {
      setRowStatus(state.starredOnly ? '当前页没有收藏商品' : '当前条件暂无商品');
      applyFieldView();
      updatePagination();
      updateSelection();
      return;
    }
    rows.forEach((item) => {
      const id = productId(item);
      const row = document.createElement('tr');
      row.dataset.productId = id;

      const check = document.createElement('input');
      check.type = 'checkbox';
      check.value = id;
      check.checked = state.selected.has(id);
      check.setAttribute('aria-label', `选择商品 ${id}`);
      check.addEventListener('change', () => {
        if (check.checked) state.selected.add(id);
        else state.selected.delete(id);
        updateSelection();
      });
      addCell(row, check);

      const star = document.createElement('button');
      star.type = 'button';
      star.className = 'star-button';
      star.textContent = Number(item.starred || 0) === 1 ? '★' : '☆';
      star.setAttribute('aria-label', Number(item.starred || 0) === 1 ? '取消收藏' : '收藏');
      star.addEventListener('click', async () => toggleStar(item, star));
      addCell(row, star);

      const identity = document.createElement('div');
      identity.className = 'product-identity';
      const img = document.createElement('img');
      img.className = 'product-thumb';
      img.alt = '';
      img.loading = 'lazy';
      if (item.image_url) img.src = item.image_url;
      const title = document.createElement('div');
      title.className = 'product-title';
      const strong = document.createElement('strong');
      strong.textContent = item.title || '未命名商品';
      const sub = document.createElement('span');
      sub.textContent = id || '--';
      title.append(strong, sub);
      identity.append(img, title);
      addCell(row, identity);

      state.visibleColumns.forEach((key) => {
        const column = columnsByKey.get(key);
        if (!column) return;
        if (key === 'tier' || key === 'style') addCell(row, editableSelect(item, key), '', key);
        else if (key === 'status') addCell(row, badge(item.status, '未知'), '', key);
        else addCell(row, formatColumnValue(item, column), 'num', key);
      });

      const open = document.createElement('button');
      open.type = 'button';
      open.className = 'button button--ghost';
      open.textContent = '详情';
      open.addEventListener('click', () => openDrawer(item, open));
      addCell(row, open);
      body.appendChild(row);
    });
    applyFieldView();
    updatePagination();
    updateSelection();
  }

  function updatePagination() {
    const totalPages = Math.max(1, Math.ceil(state.total / limit));
    $('[data-products-page-summary]').textContent = `第 ${state.page} / ${totalPages} 页，共 ${number(state.total)} 件；每页 ${limit} 件${state.starredOnly ? '；当前页收藏过滤' : ''}`;
    $('[data-products-prev]').disabled = state.page <= 1;
    $('[data-products-next]').disabled = state.page >= totalPages;
  }

  function updateSelection() {
    const visibleIds = visibleRows().map(productId);
    const selectedVisible = visibleIds.filter((id) => state.selected.has(id));
    const all = $('[data-products-select-all]');
    all.checked = visibleIds.length > 0 && selectedVisible.length === visibleIds.length;
    all.indeterminate = selectedVisible.length > 0 && selectedVisible.length < visibleIds.length;
    $('[data-products-selected]').textContent = `已选 ${state.selected.size} 件`;
    $('[data-products-batch]').classList.toggle('is-active', state.selected.size > 0);
  }

  function applyFieldView() {
    const view = state.view;
    document.querySelectorAll('[data-products-view]').forEach((button) => {
      button.setAttribute('aria-pressed', String(button.dataset.productsView === view));
    });
    renderHeader();
  }

  const columnsDialog = $('[data-products-columns-dialog]');
  let columnsReturnFocus = null;

  function selectedDialogColumns() {
    return [...columnsDialog.querySelectorAll('[data-products-column-key]:checked')].map((input) => input.dataset.productsColumnKey);
  }

  function updateColumnsDialogStatus() {
    const selected = selectedDialogColumns();
    $('[data-products-visible-count]').textContent = number(selected.length);
    $('[data-products-columns-status]').textContent = selected.length ? '' : '至少保留一个可见字段';
    $('[data-products-columns-apply]').disabled = selected.length === 0;
  }

  function renderColumnOptions(selected = state.visibleColumns) {
    const root = $('[data-products-column-options]');
    root.replaceChildren(...columnGroups.map((group) => {
      const section = document.createElement('section');
      section.className = 'field-group';
      const heading = document.createElement('strong');
      heading.textContent = group.label;
      section.appendChild(heading);
      group.columns.forEach((column) => {
        const label = document.createElement('label');
        const input = document.createElement('input');
        input.type = 'checkbox';
        input.dataset.productsColumnKey = column.key;
        input.checked = selected.includes(column.key);
        input.addEventListener('change', updateColumnsDialogStatus);
        label.append(input, document.createTextNode(column.label));
        section.appendChild(label);
      });
      return section;
    }));
    updateColumnsDialogStatus();
  }

  function openColumnsDialog(event) {
    columnsReturnFocus = event.currentTarget;
    renderColumnOptions();
    columnsDialog.hidden = false;
    columnsDialog.showModal();
    window.setTimeout(() => columnsDialog.querySelector('input')?.focus(), 0);
  }

  function closeColumnsDialog() {
    if (columnsDialog.open) columnsDialog.close();
    columnsDialog.hidden = true;
    columnsReturnFocus?.focus?.();
    columnsReturnFocus = null;
  }

  function saveColumns() {
    try { localStorage.setItem(columnsStorageKey, JSON.stringify(state.visibleColumns)); } catch {}
  }

  function applyColumns(selected, view = 'custom') {
    const valid = columns.filter((column) => selected.includes(column.key)).map((column) => column.key);
    if (!valid.length) return;
    state.visibleColumns = valid;
    state.view = view;
    saveColumns();
    renderTable();
  }

  function bindColumnSettings() {
    $('[data-products-columns-open]').addEventListener('click', openColumnsDialog);
    document.querySelectorAll('[data-products-columns-close]').forEach((button) => button.addEventListener('click', closeColumnsDialog));
    $('[data-products-columns-reset]').addEventListener('click', () => renderColumnOptions(templates.operate));
    $('[data-products-columns-apply]').addEventListener('click', () => {
      const selected = selectedDialogColumns();
      if (!selected.length) return;
      applyColumns(selected);
      closeColumnsDialog();
      toast(`已应用 ${selected.length} 个字段`);
    });
    columnsDialog.addEventListener('cancel', (event) => { event.preventDefault(); closeColumnsDialog(); });
    columnsDialog.addEventListener('close', () => {
      columnsDialog.hidden = true;
      columnsReturnFocus?.focus?.();
      columnsReturnFocus = null;
    });
  }

  async function load(detail) {
    const token = ++state.token;
    currentRange(detail);
    setStatus('商品数据加载中');
    setRowStatus('加载中');
    try {
      const payload = await DemoApi.request(buildProductsUrl());
      if (token !== state.token) return;
      state.rows = asArray(payload);
      state.total = Number(payload?.total || state.rows.length);
      state.facets = payload?.facets || { tiers: [], styles: [], statuses: [] };
      state.selected.clear();
      fillSelect('[data-products-tier]', optionValues('tier'), '全部分层');
      fillSelect('[data-products-style]', optionValues('style'), '全部风格');
      fillSelect('[data-products-status-filter]', optionValues('status'), '全部状态');
      const statusSelect = $('[data-products-status-filter]');
      const allOption = statusSelect.options[0];
      allOption.value = 'all';
      allOption.textContent = '全部状态';
      if (!statusSelect.dataset.initialized) {
        statusSelect.value = 'active';
        statusSelect.dataset.initialized = 'true';
      }
      renderTable();
      setStatus(`已加载 ${state.rows.length} 件商品，服务器分页 limit ${limit}`);
    } catch (error) {
      if (token !== state.token) return;
      state.rows = [];
      state.total = 0;
      updateKpis([]);
      setRowStatus('商品数据加载失败');
      setStatus(error.message || '商品数据加载失败');
      toast('商品数据加载失败');
    }
    if (window.lucide) window.lucide.createIcons();
  }

  async function updateField(id, key, value) {
    setStatus('正在写入商品字段');
    await DemoApi.request(`/api/products/${encodeURIComponent(id)}/field`, jsonOptions({ field: key, value }, 'PUT'));
    const item = state.rows.find((row) => productId(row) === id);
    if (item) item[key] = value;
    renderTable();
    toast('字段已更新');
  }

  async function toggleStar(item, button) {
    const id = productId(item);
    button.disabled = true;
    try {
      const payload = await DemoApi.request('/api/star', jsonOptions({ product_id: id }));
      item.starred = Number(payload.starred || 0);
      renderTable();
      toast(item.starred ? '已收藏' : '已取消收藏');
    } finally {
      button.disabled = false;
    }
  }

  async function applyBatchField() {
    const ids = [...state.selected];
    const fieldName = $('[data-products-batch-field]').value;
    const value = $('[data-products-batch-value]').value.trim();
    if (!ids.length || !value) {
      toast('请选择商品并输入批量值');
      return;
    }
    await DemoApi.request('/api/batch_update', jsonOptions({ product_ids: ids, field: fieldName, value }));
    toast(`已更新 ${ids.length} 件商品`);
    state.selected.clear();
    $('[data-products-batch-value]').value = '';
    await load();
  }

  async function applyBatchTag() {
    const ids = [...state.selected];
    const tag = $('[data-products-batch-tag]').value.trim();
    if (!ids.length || !tag) {
      toast('请选择商品并输入标签');
      return;
    }
    await DemoApi.request('/api/batch_tags', jsonOptions({ product_ids: ids, tag }));
    toast(`已为 ${ids.length} 件商品新增标签`);
    $('[data-products-batch-tag]').value = '';
    state.selected.clear();
    updateSelection();
  }

  async function batchStar() {
    const ids = [...state.selected];
    if (!ids.length) {
      toast('请选择商品');
      return;
    }
    const targets = ids.filter((id) => {
      const row = state.rows.find((item) => productId(item) === id);
      return row && Number(row.starred || 0) !== 1;
    });
    if (!targets.length) {
      state.selected.clear();
      renderTable();
      toast('选中商品已全部收藏，已跳过');
      return;
    }
    const results = await Promise.allSettled(targets.map((id) => DemoApi.request('/api/star', jsonOptions({ product_id: id, starred: 1 }))));
    const ok = results.filter((item) => item.status === 'fulfilled').length;
    const fail = results.length - ok;
    results.forEach((result, index) => {
      if (result.status !== 'fulfilled') return;
      const row = state.rows.find((item) => productId(item) === targets[index]);
      if (row) row.starred = Number(result.value?.starred || 0);
    });
    state.selected.clear();
    renderTable();
    toast(`批量收藏完成：成功 ${ok}，失败 ${fail}，跳过 ${ids.length - targets.length}`);
  }

  function resetFilters() {
    $('[data-products-search]').value = '';
    $('[data-products-tier]').value = '';
    $('[data-products-style]').value = '';
    $('[data-products-status-filter]').value = 'active';
    $('[data-products-sort]').value = 'payment_amount';
    $('[data-products-order]').value = 'desc';
    state.starredOnly = false;
    state.page = 1;
    $('[data-products-starred]').setAttribute('aria-pressed', 'false');
    load();
  }

  function firstPageLoad() {
    state.page = 1;
    load();
  }

  function bindFilters() {
    $('[data-products-search]').addEventListener('input', () => {
      window.clearTimeout(state.searchTimer);
      state.searchTimer = window.setTimeout(firstPageLoad, 300);
    });
    ['[data-products-tier]', '[data-products-style]', '[data-products-status-filter]', '[data-products-sort]', '[data-products-order]'].forEach((selector) => {
      $(selector).addEventListener('change', firstPageLoad);
    });
    $('[data-products-starred]').addEventListener('click', (event) => {
      state.starredOnly = !state.starredOnly;
      event.currentTarget.setAttribute('aria-pressed', String(state.starredOnly));
      renderTable();
      setStatus(state.starredOnly ? '当前页收藏过滤已开启' : '当前页收藏过滤已关闭');
    });
    $('[data-products-reset]').addEventListener('click', resetFilters);
    $('[data-products-refresh]').addEventListener('click', () => load());
    $('[data-products-prev]').addEventListener('click', () => {
      if (state.page > 1) {
        state.page -= 1;
        load();
      }
    });
    $('[data-products-next]').addEventListener('click', () => {
      if (state.page < Math.ceil(state.total / limit)) {
        state.page += 1;
        load();
      }
    });
    $('[data-products-batch-apply]').addEventListener('click', () => applyBatchField().catch((error) => toast(error.message || '批量更新失败')));
    $('[data-products-batch-tag-apply]').addEventListener('click', () => applyBatchTag().catch((error) => toast(error.message || '批量打标失败')));
    $('[data-products-batch-star]').addEventListener('click', () => batchStar().catch((error) => toast(error.message || '批量收藏失败')));
    document.querySelectorAll('[data-products-view]').forEach((button) => button.addEventListener('click', () => {
      state.view = button.dataset.productsView || 'operate';
      try { localStorage.setItem(storageKey, state.view); } catch {}
      applyColumns(templates[state.view] || templates.operate, state.view);
    }));
  }

  const drawer = $('[data-product-drawer]');
  const backdrop = $('[data-product-drawer-backdrop]');
  let drawerReturnFocus = null;

  function visibleFocusables() {
    return Array.from(drawer.querySelectorAll(focusableSelector)).filter((element) => {
      if (element.closest('[hidden]')) return false;
      const style = window.getComputedStyle(element);
      const rect = element.getBoundingClientRect();
      return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0;
    });
  }

  function renderDrawerSummary(item) {
    const summary = $('[data-product-drawer-summary]');
    summary.replaceChildren(
      metric('销售额', money(salesOf(item))),
      metric('访客', number(field(item, 'visitors'))),
      metric('转化', percent(field(item, 'conversion'))),
      metric('ROI', spendOf(item) ? (salesOf(item) / spendOf(item)).toFixed(2) : '--')
    );
  }

  function renderList(container, rows, emptyText, renderer) {
    container.replaceChildren();
    if (!rows.length) {
      const item = document.createElement('div');
      item.className = 'status-list__item';
      item.textContent = emptyText;
      container.appendChild(item);
      return;
    }
    rows.forEach((row) => container.appendChild(renderer(row)));
  }

  async function loadDrawerData(item) {
    const drawerToken = ++state.drawerToken;
    const id = productId(item);
    const period = currentMonthPeriod();
    const notesEl = $('[data-product-notes]');
    const tagsEl = $('[data-product-tags]');
    const actionsEl = $('[data-product-actions]');
    notesEl.textContent = '备注加载中';
    tagsEl.textContent = '标签加载中';
    actionsEl.textContent = '动作加载中';
    const [notes, tagPayload, actionPayload] = await Promise.all([
      DemoApi.request(`/api/notes/${encodeURIComponent(id)}`),
      DemoApi.request(`/api/product_tags?dim=monthly&period=${encodeURIComponent(period)}`),
      DemoApi.domainRequest(`/api/actions?product_id=${encodeURIComponent(id)}&limit=500`),
    ]);
    if (drawerToken !== state.drawerToken || productId(state.currentProduct) !== id) return;

    renderList(notesEl, asArray(notes, 'notes'), '暂无备注', (note) => {
      const wrap = document.createElement('div');
      wrap.className = 'status-list__item';
      const text = document.createElement('span');
      text.textContent = note.note || '';
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'button button--ghost';
      button.textContent = '删除';
      button.addEventListener('click', async () => {
        await DemoApi.request(`/api/notes/${Number(note.id)}`, { method: 'DELETE' });
        await loadDrawerData(item);
      });
      wrap.append(text, button);
      return wrap;
    });

    const matchedTags = asArray(tagPayload).find((row) => String(row.product_id) === id)?.tags || [];
    tagsEl.replaceChildren();
    if (!matchedTags.length) {
      const empty = document.createElement('span');
      empty.className = 'chip';
      empty.textContent = '暂无标签';
      tagsEl.appendChild(empty);
    } else {
      matchedTags.forEach((tag) => {
        const chip = document.createElement('span');
        chip.className = 'chip';
        chip.textContent = tag;
        tagsEl.appendChild(chip);
      });
    }

    const actions = asArray(actionPayload?.data || actionPayload);
    renderList(actionsEl, actions, '暂无运营动作', (action) => {
      const wrap = document.createElement('div');
      wrap.className = 'status-list__item';
      const text = document.createElement('span');
      text.textContent = `${action.planned_at || action.action_date || '--'} ${action.action_type || '--'} ${action.action_detail || ''}（${action.status || 'draft'}）`.trim();
      wrap.appendChild(text);
      return wrap;
    });
  }

  async function openDrawer(item, trigger) {
    state.drawerToken += 1;
    state.currentProduct = item;
    drawerReturnFocus = trigger || document.activeElement;
    $('[data-product-drawer-title]').textContent = item.title || '未命名商品';
    $('[data-product-drawer-subtitle]').textContent = productId(item);
    const detailLink = $('[data-product-detail-link]');
    if (detailLink) detailLink.href = `/products/${encodeURIComponent(productId(item))}`;
    renderDrawerSummary(item);
    drawer.removeAttribute('inert');
    drawer.setAttribute('aria-hidden', 'false');
    drawer.classList.add('is-open');
    backdrop.classList.add('is-open');
    document.body.classList.add('demo-scroll-lock');
    window.setTimeout(() => (visibleFocusables()[0] || drawer).focus(), 0);
    try {
      await loadDrawerData(item);
    } catch (error) {
      toast(error.message || '详情加载失败');
    }
  }

  function closeDrawer() {
    if (!drawer.classList.contains('is-open')) return;
    state.drawerToken += 1;
    state.currentProduct = null;
    drawer.classList.remove('is-open');
    backdrop.classList.remove('is-open');
    drawer.setAttribute('aria-hidden', 'true');
    drawer.setAttribute('inert', '');
    document.body.classList.remove('demo-scroll-lock');
    if (drawerReturnFocus && typeof drawerReturnFocus.focus === 'function') drawerReturnFocus.focus();
    drawerReturnFocus = null;
  }

  function bindDrawer() {
    $('[data-product-drawer-close]').addEventListener('click', closeDrawer);
    backdrop.addEventListener('click', closeDrawer);
    drawer.addEventListener('keydown', (event) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        closeDrawer();
        return;
      }
      if (event.key !== 'Tab') return;
      const items = visibleFocusables();
      if (!items.length) {
        event.preventDefault();
        drawer.focus();
        return;
      }
      const first = items[0];
      const last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    });
    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape') closeDrawer();
    });
    $('[data-product-note-add]').addEventListener('click', async () => {
      const item = state.currentProduct;
      const input = $('[data-product-note-input]');
      const note = input.value.trim();
      if (!item || !note) return;
      await DemoApi.request('/api/notes', jsonOptions({ product_id: productId(item), note }));
      input.value = '';
      await loadDrawerData(item);
      toast('备注已新增');
    });
    $('[data-product-tag-add]').addEventListener('click', async () => {
      const item = state.currentProduct;
      const input = $('[data-product-tag-input]');
      const tag = input.value.trim();
      if (!item || !tag) return;
      await DemoApi.request('/api/product_tags', jsonOptions({ product_id: productId(item), tag }));
      input.value = '';
      await loadDrawerData(item);
      toast('标签已新增');
    });
    $('[data-product-action-add]').addEventListener('click', async () => {
      const item = state.currentProduct;
      const type = $('[data-product-action-type]').value.trim();
      const detail = $('[data-product-action-detail]').value.trim();
      if (!item || !type) {
        toast('请输入动作类型');
        return;
      }
      await DemoApi.domainRequest('/api/actions', jsonOptions({
        product_id: productId(item),
        purpose_type: 'increase_sales',
        purpose_note: detail || type,
        action_type: type,
        action_detail: detail,
        target_metric: 'payment_amount',
        planned_at: new Date().toISOString().slice(0, 10),
        observer_window_days: 7,
        assigned_to: 'operator',
      }));
      $('[data-product-action-type]').value = '';
      $('[data-product-action-detail]').value = '';
      await loadDrawerData(item);
      toast('运营动作已新增');
    });
  }

  function initView() {
    try {
      const stored = localStorage.getItem(storageKey);
      if (['operate', 'select', 'paid'].includes(stored)) state.view = stored;
      const storedColumns = JSON.parse(localStorage.getItem(columnsStorageKey) || 'null');
      if (Array.isArray(storedColumns) && storedColumns.some((key) => columnsByKey.has(key))) {
        state.visibleColumns = columns.filter((column) => storedColumns.includes(column.key)).map((column) => column.key);
        if (!Object.values(templates).some((template) => template.join('|') === state.visibleColumns.join('|'))) state.view = 'custom';
      } else state.visibleColumns = [...(templates[state.view] || templates.operate)];
    } catch {}
    applyFieldView();
  }

  bindFilters();
  bindDrawer();
  bindColumnSettings();
  initView();
  window.addEventListener('tmall:date-range-change', (event) => {
    state.page = 1;
    load(event.detail);
  });
  window.addEventListener('tmall:refresh', () => load());
  if (!window.TmallDateRange) load();
})();
