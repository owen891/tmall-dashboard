// 素材点击率看板:默认只看单品,点击单品后在弹窗中查看素材明细。
(function () {
  const $ = (selector, root = document) => root.querySelector(selector);
  const money = (value) => { const num = Number(value); return Number.isFinite(num) ? `¥${num.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : '--'; };
  const moneyCompact = (value) => { const num = Number(value); return Number.isFinite(num) ? `¥${num.toLocaleString('zh-CN', { maximumFractionDigits: 0 })}` : '--'; };
  const percent = (value) => { const num = Number(value); return Number.isFinite(num) ? `${(num * 100).toFixed(2)}%` : '--'; };
  const ratio = (value) => { const num = Number(value); return Number.isFinite(num) ? num.toFixed(2) : '--'; };
  const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (ch) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch]));
  const params = new URLSearchParams(window.location.search);
  const categoryFilterAttribute = 'data-cb-category';
  const columns = [
    { key: 'product', label: '单品', required: true },
    { key: 'image', label: '主图' },
    { key: 'category', label: '品类' },
    { key: 'creative_count', label: '素材数' },
    { key: 'ad_spend', label: '累计花费' },
    { key: 'attributed_payment_amount', label: '累计成交' },
    { key: 'ctr', label: '点击率' },
    { key: 'cart_rate', label: '加购率' },
    { key: 'roi', label: '整体 ROI' },
    { key: 'clicks', label: '点击量' },
    { key: 'impressions', label: '展现量' },
    { key: 'cvr', label: '转化率' },
    { key: 'cart_cost', label: '加购成本' },
    { key: 'payment_buyers', label: '支付买家数' },
    { key: 'direct_payment_amount', label: '直接成交' },
    { key: 'new_buyers', label: '新客数' },
    { key: 'first_date', label: '首次投放日期' },
    { key: 'last_date', label: '最近投放日期' },
  ];
  const state = { products: [], categories: [], totals: {}, category: params.get('category') || '全部', productId: params.get('product_id') || '', search: params.get('q') || '', visibleColumns: ['product', 'image', 'category', 'creative_count', 'ad_spend', 'ctr', 'roi'] };
  const roiTone = (roi) => { const num = Number(roi); if (!Number.isFinite(num) || num <= 0) return ''; return num >= 3 ? 'success' : num >= 1.5 ? 'warning' : 'danger'; };

  function renderSummary() {
    const set = (key, value) => { const node = $(`[data-cb-summary="${key}"]`); if (node) node.textContent = value; };
    set('products', state.totals.product_count ?? '--'); set('creatives', state.totals.creative_count ?? '--'); set('spend', moneyCompact(state.totals.ad_spend)); set('clicks', Number(state.totals.clicks || 0).toLocaleString('zh-CN'));
  }

  function syncUrl() {
    const url = new URL(window.location.href);
    if (state.category === '全部') url.searchParams.delete('category'); else url.searchParams.set('category', state.category);
    if (state.productId) url.searchParams.set('product_id', state.productId); else url.searchParams.delete('product_id');
    if (state.search.trim()) url.searchParams.set('q', state.search.trim()); else url.searchParams.delete('q');
    history.replaceState(null, '', url);
  }

  function filteredProducts() {
    const term = state.search.trim().toLowerCase();
    return state.products.filter((product) => { if (state.category && state.category !== '全部' && product.shop_label !== state.category) return false; if (state.productId && String(product.product_id) !== state.productId) return false; return !term || `${product.product_id} ${product.title || ''}`.toLowerCase().includes(term); });
  }

  function renderProducts() {
    const host = $('[data-cb-products]'); const currentTable = host?.closest('table');
    if (!host || !currentTable || !window.TmallUI?.table?.mount) return;
    const visible = state.visibleColumns
      .filter((key) => key !== 'image' || !state.visibleColumns.includes('product'))
      .map((key) => columns.find((column) => column.key === key)).filter(Boolean);
    const products = filteredProducts();
    const numericKeys = new Set(['creative_count', 'ad_spend', 'attributed_payment_amount', 'ctr', 'cart_rate', 'roi', 'clicks', 'impressions', 'cvr', 'cart_cost', 'payment_buyers', 'direct_payment_amount', 'new_buyers']);
    const tableColumns = visible.map((column) => ({
      key: column.key,
      label: column.label,
      numeric: numericKeys.has(column.key),
      className: `cb-col--${column.key}`,
      render: (value, product) => {
        if (column.key === 'product') return TmallUI.productIdentity({
          title: product.title, id: product.product_id,
          imageUrl: state.visibleColumns.includes('image') ? product.image_url : '',
          showThumbnail: state.visibleColumns.includes('image'),
          className: 'cb-product-identity',
        });
        if (column.key === 'image') {
          if (!product.image_url) return '--';
          const image = document.createElement('img'); image.className = 'cb-image-cell__image'; image.src = product.image_url; image.alt = ''; image.loading = 'lazy'; image.addEventListener('error', () => image.remove(), { once: true }); return image;
        }
        if (column.key === 'category') return product.shop_label || '未分类';
        if (column.key === 'creative_count') return product.creatives?.length || 0;
        if (column.key === 'ad_spend' || column.key === 'attributed_payment_amount' || column.key === 'cart_cost' || column.key === 'direct_payment_amount') return moneyCompact(value);
        if (column.key === 'ctr' || column.key === 'cart_rate' || column.key === 'cvr') return percent(value);
        if (column.key === 'roi') { const node = document.createElement('span'); node.dataset.tone = roiTone(value); node.textContent = ratio(value); return node; }
        if (column.key === 'clicks' || column.key === 'impressions' || column.key === 'payment_buyers' || column.key === 'new_buyers') return Number(value || 0).toLocaleString('zh-CN');
        if (column.key === 'first_date' || column.key === 'last_date') return value || '--';
        return value ?? '--';
      },
    }));
    const table = TmallUI.table.mount(host, { caption: '单品列表', columns: tableColumns, rows: products, emptyMessage: '当前筛选条件没有单品', rowClassName: 'cb-product-row' });
    const nextBody = table?.querySelector('tbody');
    if (!nextBody) return;
    [...nextBody.querySelectorAll('tr')].forEach((row, index) => {
      const product = products[index];
      if (!product) return;
      row.dataset.cbOpen = String(product.product_id || ''); row.tabIndex = 0; row.setAttribute('aria-label', `查看${product.title || product.product_id}的素材明细`);
    });
    window.lucide?.createIcons();
  }

  function setupColumns() {
    const dialog = $('[data-cb-columns-dialog]'); const selectorRoot = $('[data-cb-field-selector]'); if (!dialog || !selectorRoot || !window.TmallUI?.fieldSelector) return;
    let selector = null; let draft = [...state.visibleColumns];
    const open = () => { draft = [...state.visibleColumns]; selector = selector || TmallUI.fieldSelector({ root: selectorRoot, groups: [{ label: '单品字段', fields: columns }], selected: draft, availableTitle: '可选字段', availableHint: '勾选要展示的字段', previewTitle: '字段预览', previewHint: '按表格列顺序展示', optionDataAttribute: 'data-cb-field-key', previewDataAttribute: 'data-cb-field-preview', onChange: (next) => { draft = next; } }); if (selector) selector.setSelected(draft); dialog.hidden = false; dialog.showModal(); };
    const close = () => { if (dialog.open) dialog.close(); dialog.hidden = true; };
    $('[data-cb-columns-open]')?.addEventListener('click', open); dialog.querySelectorAll('[data-cb-columns-close]').forEach((button) => button.addEventListener('click', close));
    $('[data-cb-columns-apply]')?.addEventListener('click', () => { if (!draft.length) { $('[data-cb-columns-status]').textContent = '至少保留一个字段'; return; } state.visibleColumns = draft; try { localStorage.setItem('creative-board-columns', JSON.stringify(draft)); } catch {} renderProducts(); close(); });
    dialog.addEventListener('cancel', (event) => { event.preventDefault(); close(); }); dialog.addEventListener('close', () => { dialog.hidden = true; });
    try { const saved = JSON.parse(localStorage.getItem('creative-board-columns') || 'null'); if (Array.isArray(saved) && saved.length) state.visibleColumns = saved.filter((key) => columns.some((column) => column.key === key)); } catch {}
  }

  function creativeRows(product) {
    const creatives = product.creatives || []; if (!creatives.length) return '<div class="cb-empty">该单品暂无人工素材</div>';
    const withCtr = creatives.filter((item) => item.ctr != null && item.clicks > 0); const withCvr = creatives.filter((item) => item.cvr != null && item.clicks > 0); const withCart = creatives.filter((item) => item.cart_cost != null);
    const bestCtr = withCtr.length ? withCtr.reduce((a, b) => (a.ctr >= b.ctr ? a : b)) : null; const bestCvr = withCvr.length ? withCvr.reduce((a, b) => (a.cvr >= b.cvr ? a : b)) : null; const bestCart = withCart.length ? withCart.reduce((a, b) => (a.cart_cost <= b.cart_cost ? a : b)) : null;
    return creatives.map((creative) => { const badges = []; if (bestCtr?.creative_id === creative.creative_id) badges.push('<span class="cb-creative-row__badge">CTR最高</span>'); if (bestCvr?.creative_id === creative.creative_id) badges.push('<span class="cb-creative-row__badge cb-creative-row__badge--cvr">CVR最高</span>'); if (bestCart?.creative_id === creative.creative_id) badges.push('<span class="cb-creative-row__badge cb-creative-row__badge--cart">加购成本最低</span>'); return `<div class="cb-creative-row">${creative.image_url ? `<button class="cb-creative-image" type="button" data-cb-image="${esc(creative.image_url)}" aria-label="放大素材图片"><img class="cb-creative-row__thumb" src="${esc(creative.image_url)}" alt="" loading="lazy"></button>` : '<span class="cb-creative-row__thumb"></span>'}<div class="cb-creative-row__identity"><strong title="${esc(creative.creative_name || creative.creative_id)}">${esc(creative.creative_name || creative.creative_id)}</strong><small>${creative.first_date ? `${creative.first_date} ~ ${creative.last_date} 有投放` : '暂无投放记录'}</small><span>${badges.join('')}</span></div><div class="cb-creative-row__stats"><div class="num">点击率<b>${percent(creative.ctr)}</b></div><div class="num">转化率<b>${percent(creative.cvr)}</b></div><div class="num">加购率<b>${percent(creative.cart_rate)}</b></div><div class="num">点击量<b>${Number(creative.clicks || 0).toLocaleString('zh-CN')}</b></div><div class="num">花费<b>${moneyCompact(creative.ad_spend)}</b></div><div class="num">ROI<b data-tone="${roiTone(creative.roi)}">${ratio(creative.roi)}</b></div></div></div>`; }).join('');
  }

  let detailDrawer = null;

  function bindDetailDrawer() {
    const template = $('[data-cb-detail-template]');
    if (!template || !window.TmallUI?.detailDrawer || detailDrawer) return;
    detailDrawer = window.TmallUI.detailDrawer({ title: '素材明细', size: 'lg' });
    detailDrawer.body.append(template.content.cloneNode(true));
  }

  function openDetail(productId) {
    const product = state.products.find((item) => String(item.product_id) === String(productId));
    if (!product || !detailDrawer) return;
    detailDrawer.node.querySelector('.ui-drawer__copy h2').textContent = product.title || product.product_id;
    const description = detailDrawer.node.querySelector('.ui-drawer__copy p');
    if (description) description.textContent = `${product.product_id} · ${product.shop_label || '未分类'} · ${product.creatives?.length || 0} 个素材`;
    $('[data-cb-detail-summary]', detailDrawer.node).innerHTML = `<span>点击率 <b>${percent(product.ctr)}</b></span><span>加购率 <b>${percent(product.cart_rate)}</b></span><span>累计花费 <b>${money(product.ad_spend)}</b></span><span>整体 ROI <b data-tone="${roiTone(product.roi)}">${ratio(product.roi)}</b></span>`;
    $('[data-cb-detail-rows]', detailDrawer.node).innerHTML = creativeRows(product);
    detailDrawer.open();
    window.lucide?.createIcons();
  }

  async function load() {
    // tbody 里只能放 <tr>：<div> 会被浏览器丢弃，空态/加载态必须用行承载。
    const host = $('[data-cb-products]'); if (!host) return;
    const stateRow = (message) => `<tr class="ui-table-state-row"><td colspan="8"><div class="ui-empty-state"><span>${message}</span></div></td></tr>`;
    host.innerHTML = stateRow('加载中…');
    try {
      const query = new URLSearchParams();
      if (state.productId) query.set('product_id', state.productId);
      const response = await DemoApi.domainRequest('/api/creative-board' + (query.toString() ? `?${query}` : ''));
      state.products = Array.isArray(response.data?.products) ? response.data.products : []; state.categories = Array.isArray(response.data?.categories) ? response.data.categories : []; state.totals = response.data?.totals || {}; renderSummary(); renderProducts();
    } catch (error) { host.innerHTML = stateRow(esc(error.message || '素材数据加载失败')); }
  }

  function boot() {
    const search = $('[data-cb-search]');
    if (search) {
      search.value = state.search;
      search.addEventListener('input', (event) => { state.search = event.target.value; renderProducts(); syncUrl(); });
    }
    $('[data-cb-products]')?.addEventListener('click', (event) => { const row = event.target.closest('[data-cb-open]'); if (row) openDetail(row.dataset.cbOpen); }); $('[data-cb-products]')?.addEventListener('keydown', (event) => { const row = event.target.closest('[data-cb-open]'); if (row && (event.key === 'Enter' || event.key === ' ')) { event.preventDefault(); openDetail(row.dataset.cbOpen); } });
    bindDetailDrawer();
    const imageDialog = $('[data-cb-image-dialog]'); imageDialog?.querySelector('[data-cb-image-close]')?.addEventListener('click', () => imageDialog.close()); imageDialog?.addEventListener('click', (event) => { if (event.target === imageDialog) imageDialog.close(); });
    document.addEventListener('click', (event) => { const button = event.target.closest('[data-cb-image]'); if (!button || !imageDialog) return; $('[data-cb-image-preview]').src = button.dataset.cbImage; imageDialog.showModal(); });
    setupColumns(); load(); window.addEventListener('tmall:refresh', () => load());
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot); else boot();
})();
