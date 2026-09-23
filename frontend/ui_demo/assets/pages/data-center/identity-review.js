(function () {
  const root = document.querySelector('[data-identity-review]');
  if (!root) return;
  const rows = root.querySelector('[data-identity-rows]');
  const status = root.querySelector('[data-identity-status]');
  const refreshButton = root.querySelector('[data-identity-refresh]');
  const state = { identities: [], products: [], productQuery: '', productRequestId: 0 };
  const make = (tag, value, className) => {
    const node = document.createElement(tag);
    if (value !== undefined) node.textContent = value;
    if (className) node.className = className;
    return node;
  };
  const money = (value) => Number(value || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const renderState = (message) => {
    rows.replaceChildren();
    const row = make('tr');
    const cell = make('td', message);
    cell.colSpan = 8;
    row.append(cell);
    rows.append(row);
  };
  const loadProducts = async (query = '') => {
    const requestId = ++state.productRequestId;
    const params = new URLSearchParams({ dim: 'monthly', limit: '200' });
    if (query.trim()) params.set('search', query.trim());
    const response = await DemoApi.domainRequest(`/api/products?${params}`);
    if (requestId !== state.productRequestId) return;
    state.products = Array.isArray(response.data?.rows) ? response.data.rows : [];
  };
  const productOptions = (select, selectedId) => {
    select.replaceChildren(new Option('选择已有商品', ''));
    const products = [...state.products];
    if (selectedId && !products.some((item) => String(item.product_id) === String(selectedId))) {
      products.unshift({ product_id: selectedId, title: selectedId });
    }
    products.forEach((product) => {
      const label = `${product.title || product.product_id} (${product.product_id})`;
      select.add(new Option(label, product.product_id));
    });
    select.value = selectedId || '';
  };
  const renderRows = () => {
    if (!state.identities.length) return renderState('当前没有待确认的商品身份');
    rows.replaceChildren(...state.identities.map((item) => {
      const row = make('tr');
      row.append(
        make('td', item.external_product_id),
        make('td', item.display_title || item.external_product_id),
        make('td', `计划 ${item.evidence?.campaign_item_count || 0} / 素材 ${item.evidence?.creative_count || 0}`),
        make('td', `${item.first_seen_date || '--'} ~ ${item.last_seen_date || '--'} / ${item.fact_row_count || 0} 行`),
        make('td', money(item.ad_spend)),
      );
      const productCell = make('td');
      const productSelect = document.createElement('select');
      productSelect.className = 'select';
      productSelect.setAttribute('aria-label', `为 ${item.external_product_id} 选择已有商品`);
      productOptions(productSelect, '');
      productCell.append(productSelect);
      row.append(productCell);
      const reasonCell = make('td');
      const reason = document.createElement('input');
      reason.className = 'input';
      reason.placeholder = '填写审核依据';
      reason.setAttribute('aria-label', `填写 ${item.external_product_id} 的审核依据`);
      reasonCell.append(reason);
      row.append(reasonCell);
      const actionCell = make('td');
      const button = make('button', '确认绑定', 'ui-button ui-button--primary');
      button.type = 'button';
      button.addEventListener('click', async () => {
        if (!productSelect.value) return window.DemoShell?.showToast?.('请选择已有商品', { duration: 3000 });
        if (!reason.value.trim()) return window.DemoShell?.showToast?.('请填写审核原因', { duration: 3000 });
        button.disabled = true;
        try {
          await DemoApi.domainRequest(`/api/product-identities/${encodeURIComponent(item.external_product_id)}/resolve`, {
            method: 'POST',
            body: JSON.stringify({ canonical_product_id: productSelect.value, reason: reason.value.trim() }),
          });
          window.DemoShell?.showToast?.('商品身份已绑定并写入审计日志', { duration: 3500 });
          await load();
        } catch (error) {
          button.disabled = false;
          window.DemoShell?.showToast?.(error.message || '绑定失败', { duration: 4500 });
        }
      });
      actionCell.append(button);
      row.append(actionCell);
      return row;
    }));
    status.textContent = `待审核 ${state.identities.length} 个，接口总数 ${state.total || state.identities.length} 个`;
    window.lucide?.createIcons();
  };
  const load = async () => {
    refreshButton.disabled = true;
    status.textContent = '正在读取身份审核队列…';
    renderState('加载中…');
    try {
      const [identityResponse] = await Promise.all([
        DemoApi.domainRequest('/api/product-identities?status=unresolved&limit=100'),
        loadProducts(),
      ]);
      state.identities = Array.isArray(identityResponse.data?.items) ? identityResponse.data.items : [];
      state.total = identityResponse.data?.total || state.identities.length;
      renderRows();
    } catch (error) {
      renderState(error.message || '身份审核队列加载失败');
      status.textContent = '身份审核数据暂时不可用';
    } finally {
      refreshButton.disabled = false;
    }
  };
  refreshButton?.addEventListener('click', load);
  load();
})();

