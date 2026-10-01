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
    const host = $('[data-cb-products]'); const head = $('[data-cb-table-head]'); if (!host || !head) return;
    const visible = state.visibleColumns.map((key) => columns.find((column) => column.key === key)).filter(Boolean);
    head.innerHTML = visible.map((column) => `<th>${column.label}</th>`).join('');
    const products = filteredProducts();
    host.innerHTML = products.length ? products.map((product) => `<tr data-cb-open="${esc(product.product_id)}" tabindex="0" aria-label="查看${esc(product.title || product.product_id)}的素材明细">${visible.map((column) => {
      if (column.key === 'product') return `<td class="cb-product-cell"><strong>${esc(product.title || product.product_id)}</strong><small>${esc(product.product_id)}</small></td>`;
      if (column.key === 'image') return `<td class="cb-image-cell">${product.image_url ? `<img src="${esc(product.image_url)}" alt="" loading="lazy">` : '<span>--</span>'}</td>`;
      if (column.key === 'category') return `<td>${esc(product.shop_label || '未分类')}</td>`;
      if (column.key === 'creative_count') return `<td class="num">${product.creatives?.length || 0}</td>`;
      if (column.key === 'ad_spend' || column.key === 'attributed_payment_amount') return `<td class="num">${moneyCompact(product[column.key])}</td>`;
      if (column.key === 'ctr' || column.key === 'cart_rate') return `<td class="num">${percent(product[column.key])}</td>`;
      if (column.key === 'cvr') return `<td class="num">${percent(product.cvr)}</td>`;
      if (column.key === 'roi') return `<td class="num" data-tone="${roiTone(product.roi)}">${ratio(product.roi)}</td>`;
      if (column.key === 'clicks' || column.key === 'impressions' || column.key === 'payment_buyers' || column.key === 'new_buyers') return `<td class="num">${Number(product[column.key] || 0).toLocaleString('zh-CN')}</td>`;
      if (column.key === 'cart_cost' || column.key === 'direct_payment_amount') return `<td class="num">${moneyCompact(product[column.key])}</td>`;
      if (column.key === 'first_date' || column.key === 'last_date') return `<td>${esc(product[column.key] || '--')}</td>`;
      return '<td>--</td>';
    }).join('')}</tr>`).join('') : `<tr><td colspan="${visible.length}"><div class="ui-empty-state"><span>当前筛选条件没有单品</span></div></td></tr>`;
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

  function openDetail(productId) {
    const product = state.products.find((item) => String(item.product_id) === String(productId)); const dialog = $('[data-cb-detail-dialog]'); if (!product || !dialog) return;
    $('[data-cb-detail-title]').textContent = product.title || product.product_id; $('[data-cb-detail-subtitle]').textContent = `${product.product_id} · ${product.shop_label || '未分类'} · ${product.creatives?.length || 0} 个素材`; $('[data-cb-detail-summary]').innerHTML = `<span>点击率 <b>${percent(product.ctr)}</b></span><span>加购率 <b>${percent(product.cart_rate)}</b></span><span>累计花费 <b>${money(product.ad_spend)}</b></span><span>整体 ROI <b data-tone="${roiTone(product.roi)}">${ratio(product.roi)}</b></span>`; $('[data-cb-detail-rows]').innerHTML = creativeRows(product); dialog.showModal(); window.lucide?.createIcons();
  }

  async function load() {
    const host = $('[data-cb-products]'); if (!host) return; host.innerHTML = '<div class="ui-empty-state"><span>加载中…</span></div>';
    try {
      const query = new URLSearchParams();
      if (state.productId) query.set('product_id', state.productId);
      const response = await DemoApi.domainRequest('/api/creative-board' + (query.toString() ? `?${query}` : ''));
      state.products = Array.isArray(response.data?.products) ? response.data.products : []; state.categories = Array.isArray(response.data?.categories) ? response.data.categories : []; state.totals = response.data?.totals || {}; renderSummary(); renderProducts();
    } catch (error) { host.innerHTML = `<div class="ui-empty-state"><span>${esc(error.message || '素材数据加载失败')}</span></div>`; }
  }

  function boot() {
    const search = $('[data-cb-search]');
    if (search) {
      search.value = state.search;
      search.addEventListener('input', (event) => { state.search = event.target.value; renderProducts(); syncUrl(); });
    }
    $('[data-cb-products]')?.addEventListener('click', (event) => { const row = event.target.closest('[data-cb-open]'); if (row) openDetail(row.dataset.cbOpen); }); $('[data-cb-products]')?.addEventListener('keydown', (event) => { const row = event.target.closest('[data-cb-open]'); if (row && (event.key === 'Enter' || event.key === ' ')) { event.preventDefault(); openDetail(row.dataset.cbOpen); } });
    const dialog = $('[data-cb-detail-dialog]'); dialog?.querySelectorAll('[data-cb-detail-close]').forEach((button) => button.addEventListener('click', () => dialog.close())); dialog?.addEventListener('click', (event) => { if (event.target === dialog) dialog.close(); });
    const imageDialog = $('[data-cb-image-dialog]'); imageDialog?.querySelector('[data-cb-image-close]')?.addEventListener('click', () => imageDialog.close()); imageDialog?.addEventListener('click', (event) => { if (event.target === imageDialog) imageDialog.close(); });
    document.addEventListener('click', (event) => { const button = event.target.closest('[data-cb-image]'); if (!button || !imageDialog) return; $('[data-cb-image-preview]').src = button.dataset.cbImage; imageDialog.showModal(); });
    setupColumns(); load(); window.addEventListener('tmall:refresh', () => load());
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot); else boot();
})();
