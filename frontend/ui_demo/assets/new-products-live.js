(function () {
  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));
  const money = (value) => { const num = Number(value); return Number.isFinite(num) ? `¥${num.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : '--'; };
  const moneyCompact = (value) => { const num = Number(value); return Number.isFinite(num) ? `¥${num.toLocaleString('zh-CN', { maximumFractionDigits: 0 })}` : '--'; };
  const percent = (value) => { if (value == null) return '--'; const num = Number(value); return Number.isFinite(num) ? `${(num * 100).toFixed(2)}%` : '--'; };
  const ratio = (value) => { if (value == null) return '--'; const num = Number(value); return Number.isFinite(num) ? num.toFixed(2) : '--'; };
  const count = (value) => { if (value == null) return '--'; const num = Number(value); return Number.isFinite(num) ? num.toLocaleString('zh-CN') : '--'; };
  const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (ch) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch]));
  const state = { rows: [], totals: null, launches: [], launchesExpanded: false, window: null, structureProduct: null, structureChart: null, creativeRequest: 0, creativeSort: { key: 'clicks', direction: 'desc' } };

  function range() {
    const current = window.TmallDateRange?.getState?.() || {};
    const period = current.endDate || current.startDate || new Date().toISOString().slice(0, 10);
    return { start: current.startDate || `${String(period).slice(0, 7)}-01`, end: current.endDate || `${String(period).slice(0, 7)}-31` };
  }
  function exportCsv(filename, headers, rows) {
    const cell = (value) => { const text = value == null ? '' : String(value); return /[",\n\r]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text; };
    const csv = `\ufeff${[headers, ...rows].map((row) => row.map(cell).join(',')).join('\r\n')}`;
    const link = document.createElement('a'); link.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' })); link.download = filename; link.click(); URL.revokeObjectURL(link.href);
  }
  function roiTone(value) { const num = Number(value); if (!Number.isFinite(num) || num <= 0) return 'muted'; if (num >= 3) return 'success'; if (num >= 1.5) return 'warning'; return 'danger'; }
  function setActionStatus(message) { const node = $('[data-promotion-new-action-status]'); if (node) node.textContent = message; }
  function exportNewProducts() {
    if (!state.rows.length) return false;
    const { start, end } = range();
    exportCsv(`新品推广_${start}_${end}.csv`, ['商品ID', '标题', '上架日期', '展现量', '点击量', '点击率', 'CPC', 'CPM', '推广花费', '推广成交', 'ROI', '支付买家', '转化率', '加购数', '加购率', '加购成本', '拉新买家', '新客占比', '销售额', '净销售额', '费比'], state.rows.map((row) => [row.product_id, row.title, row.list_date, row.impressions, row.clicks, row.ctr, row.cpc ?? (row.clicks ? Number(row.ad_spend || 0) / Number(row.clicks) : null), row.impressions ? Number(row.ad_spend || 0) * 1000 / Number(row.impressions) : null, row.ad_spend, row.attributed_payment_amount, row.roi, row.payment_buyers, row.cvr, row.cart_adds, row.cart_rate, row.cart_cost, row.new_buyers, row.payment_buyers ? Number(row.new_buyers || 0) / Number(row.payment_buyers) : null, row.link_gsv, row.link_net_sales, row.expense_ratio]));
    return true;
  }

  async function loadNewProducts() {
    const body = $('[data-promotion-new-body]');
    const { start, end } = range();
    setActionStatus('正在加载新品投放数据…');
    if (body) body.innerHTML = `<tr><td colspan="${productFields.length + 1}">加载中…</td></tr>`;
    try {
      const response = await DemoApi.domainRequest(`/api/promotion/new-products?${new URLSearchParams({ start, end })}`);
      state.rows = Array.isArray(response.data?.rows) ? response.data.rows : [];
      state.totals = response.data?.totals || null;
      state.launches = Array.isArray(response.data?.launches) ? response.data.launches : [];
      state.launchesExpanded = false;
      state.window = { windowDays: response.data?.window_days, newCutoff: response.data?.new_cutoff, start, end };
      renderBoard(); renderLaunches();
      setActionStatus(`已加载 ${state.rows.length} 个已投放新品，可导出明细。`);
    } catch (error) {
      setActionStatus(`新品数据加载失败：${error.message || '请稍后重试'}`);
      if (body) body.innerHTML = `<tr><td colspan="${productFields.length + 1}">${esc(error.message || '新品数据加载失败')}</td></tr>`;
      const launchBody = $('[data-promotion-new-launch-body]');
      if (launchBody) launchBody.innerHTML = `<tr><td colspan="8">${esc(error.message || '新品数据加载失败')}</td></tr>`;
    }
  }

  function renderBoard() {
    const totals = state.totals || {};
    const clicks = state.rows.reduce((sum, row) => sum + Number(row.clicks || 0), 0);
    const impressions = state.rows.reduce((sum, row) => sum + Number(row.impressions || 0), 0);
    const cartAdds = state.rows.reduce((sum, row) => sum + Number(row.cart_adds || 0), 0);
    const newBuyers = state.rows.reduce((sum, row) => sum + Number(row.new_buyers || 0), 0);
    const linkNetSales = state.rows.reduce((sum, row) => sum + Number(row.link_net_sales || 0), 0);
    $('[data-promotion-new-funnel="spend"]').textContent = moneyCompact(totals.ad_spend);
    $('[data-promotion-new-funnel="clicks"]').textContent = clicks.toLocaleString('zh-CN');
    $('[data-promotion-new-funnel="deal"]').textContent = moneyCompact(totals.attributed_payment_amount);
    $('[data-promotion-new-funnel-meta="spend"]').textContent = `新品推广花费 · 占全店 ${percent(totals.spend_share)}`;
    $('[data-promotion-new-funnel-meta="clicks"]').textContent = `点击量 / 展现量 ${impressions.toLocaleString('zh-CN')}`;
    $('[data-promotion-new-funnel-meta="deal"]').textContent = `推广成交 · 新品 ROI ${ratio(totals.roi)}`;
    $('[data-promotion-new-signal="products"]').textContent = `${totals.product_count ?? '--'} 个`;
    $('[data-promotion-new-signal="new_total"]').textContent = `${totals.new_total ?? '--'} 个`;
    $('[data-promotion-new-signal="spend_share"]').textContent = percent(totals.spend_share);
    $('[data-promotion-new-signal="deal_share"]').textContent = percent(totals.deal_share);
    const health = $('[data-promotion-new-health]');
    if (health) { health.dataset.tone = Number(totals.product_count || 0) > 0 ? 'success' : 'muted'; health.querySelector('span:last-child').textContent = Number(totals.product_count || 0) > 0 ? '新品数据正常' : '当前范围没有新品投放'; window.lucide?.createIcons(); }
    const values = { spend: moneyCompact(totals.ad_spend), deal: moneyCompact(totals.attributed_payment_amount), roi: ratio(totals.roi), expense_ratio: linkNetSales ? percent(Number(totals.ad_spend || 0) / linkNetSales) : '--', ctr: percent(impressions ? clicks / impressions : 0), cvr: percent(clicks ? state.rows.reduce((sum, row) => sum + Number(row.payment_buyers || 0), 0) / clicks : 0), cart_cost: cartAdds ? money(Number(totals.ad_spend || 0) / cartAdds) : '--', new_customer_cost: newBuyers ? money(Number(totals.ad_spend || 0) / newBuyers) : '--' };
    Object.entries(values).forEach(([key, value]) => { const node = $(`[data-promotion-new-kpi="${key}"]`); if (node) node.textContent = value; });
    const note = $('[data-promotion-new-kpi-note="spend"]'); if (note) note.textContent = `占全店推广花费 ${percent(totals.spend_share)}`;
    const insight = Number(totals.product_count || 0) ? (Number(totals.spend_share || 0) > 0.3 ? { title: `新品投放占全店 ${percent(totals.spend_share)}`, copy: `本期 ${totals.product_count} 个新品消耗 ${percent(totals.spend_share)} 的推广花费，ROI ${ratio(totals.roi)}。` } : { title: `新品花费占全店 ${percent(totals.spend_share)}`, copy: `本期 ${totals.product_count} 个新品投放，ROI ${ratio(totals.roi)}；可结合打爆阶段调整预算。` }) : { title: '当前范围没有新品投放', copy: '调整日期范围，或在商品页检查新品上架信息是否已维护。' };
    $('[data-promotion-new-insight-title]').textContent = insight.title; $('[data-promotion-new-insight-copy]').textContent = insight.copy;
    const scope = $('[data-promotion-new-scope]'); if (scope && state.window?.newCutoff) scope.textContent = `新品口径：${state.window.newCutoff} ~ 周期末（${state.window.windowDays || 60} 天内上架）`;
    renderProducts();
  }

  // 复用统一表格的列渲染与空状态，通过 mount 保留现有表头、表格类名和 data-* 查询入口。
  function replaceTableBody(target, columns, rows, emptyMessage) {
    if (!target || !window.TmallUI?.table?.mount) return target;
    const table = window.TmallUI.table.mount(target, { columns, rows, emptyMessage });
    return table?.querySelector('tbody') || target;
  }

  function renderLaunches() {
    const body = $('[data-promotion-new-launch-body]'); if (!body) return;
    const rows = state.launches;
    const visibleRows = state.launchesExpanded ? rows : rows.slice(0, 7);
    const toggle = $('[data-promotion-new-launch-toggle]');
    $('[data-promotion-new-launch-count]').textContent = `${rows.length} 个批次`;
    if (toggle) {
      toggle.hidden = rows.length <= 7;
      toggle.setAttribute('aria-expanded', String(state.launchesExpanded));
      toggle.textContent = state.launchesExpanded ? '收起批次' : `查看全部批次（${rows.length}）`;
    }
    const hint = $('[data-promotion-new-launch-hint]');
    if (hint) hint.textContent = `当前范围 ${state.window?.start || '--'} ~ ${state.window?.end || '--'}；共 ${rows.length} 个上架批次，默认显示最近 ${Math.min(7, rows.length)} 个。`;
    replaceTableBody(body, [
      { key: 'list_date', label: '上架日期' },
      { key: 'product_count', label: '上架新品数', numeric: true },
      { key: 'promotion_count', label: '已投放 / 未投放', numeric: true },
      { key: 'promotion_coverage', label: '投放覆盖率', numeric: true, render: percent },
      { key: 'ad_spend', label: '推广花费', numeric: true, render: money },
      { key: 'attributed_payment_amount', label: '推广成交', numeric: true, render: money },
      { key: 'roi', label: '批次 ROI', numeric: true, render: ratio },
      { key: 'link_gsv', label: '销售额', numeric: true, render: money },
    ], visibleRows.map((row) => ({
      list_date: row.list_date,
      product_count: row.total_product_count ?? row.product_count ?? 0,
      promotion_count: `${row.promoted_product_count ?? row.product_count ?? 0} / ${row.unpromoted_product_count ?? 0}`,
      promotion_coverage: row.promotion_coverage,
      ad_spend: row.ad_spend,
      attributed_payment_amount: row.attributed_payment_amount,
      roi: row.roi,
      link_gsv: row.link_gsv,
    })), '当前范围没有上架新品');
  }

  const newProductColumns = [
      { key: 'title', label: '商品 / 上架日', className: 'promotion-new-product-cell', render: (_value, row) => TmallUI.productIdentity({ title: row.title, id: row.product_id, imageUrl: row.image_url, className: 'promotion-new-product', metaText: `${row.list_date || '--'} 上架` }) },
      { key: 'days', label: '上架天数', numeric: true, render: (value) => value == null ? '--' : `${value} 天` },
      { key: 'impressions', label: '展现量', numeric: true, render: count },
      { key: 'clicks', label: '点击量', numeric: true, render: count },
      { key: 'ctr', label: '点击率', numeric: true, render: percent },
      { key: 'cpcValue', label: 'CPC', numeric: true, render: (value) => value != null ? money(value) : '--' },
      { key: 'cpmValue', label: 'CPM', numeric: true, render: (value) => value != null ? money(value) : '--' },
      { key: 'ad_spend', label: '推广花费', numeric: true, render: money },
      { key: 'attributed_payment_amount', label: '推广成交', numeric: true, render: money },
      { key: 'roi', label: 'ROI', numeric: true, render: (value) => { const cell = document.createElement('span'); cell.dataset.tone = roiTone(value); cell.textContent = ratio(value); return cell; } },
      { key: 'payment_buyers', label: '支付买家', numeric: true, render: count },
      { key: 'cvr', label: '转化率', numeric: true, render: percent },
      { key: 'cart_adds', label: '加购数', numeric: true, render: count },
      { key: 'cart_rate', label: '加购率', numeric: true, render: percent },
      { key: 'cart_cost', label: '加购成本', numeric: true, render: (value) => value != null ? money(value) : '--' },
      { key: 'new_buyers', label: '拉新买家', numeric: true, render: count },
      { key: 'newBuyerShare', label: '新客占比', numeric: true, render: percent },
      { key: 'link_gsv', label: '销售额', numeric: true, render: money },
      { key: 'link_net_sales', label: '净销售额', numeric: true, render: money },
      { key: 'expense_ratio', label: '费比', numeric: true, render: (value) => value != null ? percent(value) : '--' },
      { key: 'action', label: '操作', render: (_value, row) => { const button = document.createElement('button'); button.type = 'button'; button.className = 'ui-button ui-button--ghost'; button.dataset.promotionNewStructure = row.product_id || ''; button.textContent = '结构'; return button; } },
  ];

  const productFieldsStorageKey = 'tmall.new-products.columns.v1';
  const defaultProductFields = newProductColumns.filter((column) => column.key !== 'action').map((column) => column.key);
  function normalizeProductFields(value) {
    if (!Array.isArray(value)) return [...defaultProductFields];
    return ['title', ...[...new Set(value)].filter((key) => key !== 'title' && defaultProductFields.includes(key))];
  }
  function readProductFields() {
    try { const saved = localStorage.getItem(productFieldsStorageKey); return saved === null ? [...defaultProductFields] : normalizeProductFields(JSON.parse(saved)); }
    catch (_) { return [...defaultProductFields]; }
  }
  let productFields = readProductFields();

  function bindProductFields() {
    const trigger = $('[data-promotion-new-columns-open]');
    if (!trigger) return;
    const selectorRoot = document.createElement('div');
    const fieldGroups = [
      ['基础信息', ['title', 'days']],
      ['投放表现', ['impressions', 'clicks', 'ctr', 'cpcValue', 'cpmValue', 'ad_spend', 'attributed_payment_amount', 'roi']],
      ['转化拉新', ['payment_buyers', 'cvr', 'cart_adds', 'cart_rate', 'cart_cost', 'new_buyers', 'newBuyerShare']],
      ['销售联动', ['link_gsv', 'link_net_sales', 'expense_ratio']],
    ].map(([label, keys]) => ({ label, fields: keys.map((key) => ({ key, label: newProductColumns.find((column) => column.key === key).label, required: key === 'title' })) }));
    let draft = [...productFields];
    const selector = TmallUI.fieldSelector({ root: selectorRoot, groups: fieldGroups, selected: draft,
      optionDataAttribute: 'data-new-products-field-key', previewDataAttribute: 'data-new-products-field-preview',
      onChange: (next) => { draft = normalizeProductFields(next); } });
    const reset = TmallUI.button({ label: '恢复默认', variant: 'ghost' });
    const cancel = TmallUI.button({ label: '取消', variant: 'secondary' });
    const apply = TmallUI.button({ label: '应用', variant: 'primary' });
    const modal = TmallUI.modal({ title: '新品投放字段设置', description: '勾选字段并拖动或上移、下移调整顺序；商品信息固定在首列，操作固定在末列。设置保存在当前浏览器。', body: selectorRoot, footer: [reset, cancel, apply], size: 'lg' });
    modal.node.classList.add('ui-field-selector-dialog', 'new-products-fields-dialog');
    modal.node.dataset.modalKind = 'new-products-fields';
    trigger.setAttribute('aria-haspopup', 'dialog');
    trigger.addEventListener('click', () => { draft = [...productFields]; selector.setSelected(draft); modal.open(); });
    reset.addEventListener('click', () => { draft = [...defaultProductFields]; selector.setSelected(draft); });
    cancel.addEventListener('click', () => modal.close());
    apply.addEventListener('click', () => {
      productFields = normalizeProductFields(draft);
      let saved = true;
      try { localStorage.setItem(productFieldsStorageKey, JSON.stringify(productFields)); } catch (_) { saved = false; }
      renderProducts(); modal.close();
      setActionStatus(saved ? '新品投放字段设置已保存。' : '字段设置已应用；浏览器存储不可用，刷新后将恢复默认。');
    });
  }

  function renderProducts() {
    const body = $('[data-promotion-new-body]'); if (!body) return;
    const search = ($('[data-promotion-new-search]')?.value || '').trim().toLowerCase(); const sortKey = $('[data-promotion-new-sort]')?.value || 'ad_spend';
    let rows = state.rows.filter((row) => !search || `${row.product_id} ${row.title || ''}`.toLowerCase().includes(search));
    rows = [...rows].sort((a, b) => sortKey === 'list_date' ? String(b.list_date || '').localeCompare(String(a.list_date || '')) : (Number(b[sortKey] || 0) || 0) - (Number(a[sortKey] || 0) || 0));
    $('[data-promotion-new-row-count]').textContent = `${rows.length} 个新品`;
    const { end } = range();
    const tableRows = rows.map((row) => {
      const days = row.list_date && end ? Math.max(0, Math.round((new Date(end) - new Date(row.list_date)) / 86400000)) : null;
      const cpc = row.cpc ?? (row.clicks ? Number(row.ad_spend || 0) / Number(row.clicks) : null);
      const cpm = row.impressions ? Number(row.ad_spend || 0) * 1000 / Number(row.impressions) : null;
      const newBuyerShare = row.payment_buyers ? Number(row.new_buyers || 0) / Number(row.payment_buyers) : null;
      return { ...row, days, cpcValue: cpc, cpmValue: cpm, newBuyerShare };
    });
    // mount preserves old header attributes by position: discard stale column metadata after reordering.
    body.closest('table')?.tHead?.replaceChildren();
    const columns = [...productFields.map((key) => newProductColumns.find((column) => column.key === key)), newProductColumns.find((column) => column.key === 'action')];
    const nextBody = replaceTableBody(body, columns, tableRows, '当前范围没有新品投放数据');
    $$('button[data-promotion-new-structure]', nextBody || body).forEach((button) => {
      if (button.dataset.promotionNewBound) return;
      button.dataset.promotionNewBound = 'true';
      button.addEventListener('click', () => openStructureDialog(button.dataset.promotionNewStructure, button));
    });
  }

  function creativeRows(product) {
    const creatives = Array.isArray(product?.creatives) ? product.creatives : [];
    if (!creatives.length) return [];
    const withCtr = creatives.filter((item) => item.ctr != null && Number(item.clicks || 0) > 0);
    const withCvr = creatives.filter((item) => item.cvr != null && Number(item.clicks || 0) > 0);
    const withCart = creatives.filter((item) => item.cart_cost != null);
    const bestCtr = withCtr.length ? withCtr.reduce((a, b) => (Number(a.ctr) >= Number(b.ctr) ? a : b)) : null;
    const bestCvr = withCvr.length ? withCvr.reduce((a, b) => (Number(a.cvr) >= Number(b.cvr) ? a : b)) : null;
    const bestCart = withCart.length ? withCart.reduce((a, b) => (Number(a.cart_cost) <= Number(b.cart_cost) ? a : b)) : null;
    const { key, direction } = state.creativeSort;
    const sorted = [...creatives].sort((a, b) => {
      if (key === 'name') return direction === 'asc' ? String(a.creative_name || a.creative_id).localeCompare(String(b.creative_name || b.creative_id), 'zh-CN') : String(b.creative_name || b.creative_id).localeCompare(String(a.creative_name || a.creative_id), 'zh-CN');
      const left = Number(a[key]); const right = Number(b[key]);
      const leftValue = Number.isFinite(left) ? left : -Infinity; const rightValue = Number.isFinite(right) ? right : -Infinity;
      return direction === 'asc' ? leftValue - rightValue : rightValue - leftValue;
    });
    return sorted.map((creative) => {
      const badges = [];
      if (bestCtr?.creative_id === creative.creative_id) badges.push('<span class="cb-creative-row__badge">CTR最高</span>');
      if (bestCvr?.creative_id === creative.creative_id) badges.push('<span class="cb-creative-row__badge cb-creative-row__badge--cvr">CVR最高</span>');
      if (bestCart?.creative_id === creative.creative_id) badges.push('<span class="cb-creative-row__badge cb-creative-row__badge--cart">加购成本最低</span>');
      const image = creative.image_url
        ? `<button class="cb-creative-image" type="button" data-new-products-image="${esc(creative.image_url)}" aria-label="放大素材图片"><img class="cb-creative-row__thumb" src="${esc(creative.image_url)}" alt="" loading="lazy"></button>`
        : '<span class="cb-creative-row__thumb"></span>';
      return { creative, html: `<td class="cb-creative-table__asset">${image}<div class="cb-creative-table__identity"><strong title="${esc(creative.creative_name || creative.creative_id)}">${esc(creative.creative_name || creative.creative_id)}</strong><small>${creative.first_date ? `${esc(creative.first_date)} ~ ${esc(creative.last_date)} 有投放` : '暂无投放记录'}</small><span>${badges.join('')}</span></div></td><td class="num">${percent(creative.ctr)}</td><td class="num">${percent(creative.cvr)}</td><td class="num">${percent(creative.cart_rate)}</td><td class="num">${Number(creative.clicks || 0).toLocaleString('zh-CN')}</td><td class="num">${moneyCompact(creative.ad_spend)}</td><td class="num" data-tone="${roiTone(creative.roi)}">${ratio(creative.roi)}</td><td class="num">${creative.cart_cost != null ? moneyCompact(creative.cart_cost) : '--'}</td>` };
    });
  }

  function creativeSortButton(key, label) {
    const active = state.creativeSort.key === key;
    const icon = active ? (state.creativeSort.direction === 'asc' ? 'arrow-up' : 'arrow-down') : 'arrow-up-down';
    return `<button class="cb-sort-button${active ? ' is-active' : ''}" type="button" data-new-products-creative-sort="${key}" aria-label="按${label}排序" aria-pressed="${active}">${label}<i data-lucide="${icon}" aria-hidden="true"></i></button>`;
  }

  function renderCreativeContent(product) {
    const creatives = Array.isArray(product?.creatives) ? product.creatives : [];
    const body = $('[data-promotion-structure-body]');
    if (!body) return;
    const content = document.createElement('div');
    content.className = 'cb-detail-dialog__body';
    content.innerHTML = `<div class="cb-detail-summary"><span>点击率 <b>${percent(product?.ctr)}</b></span><span>加购率 <b>${percent(product?.cart_rate)}</b></span><span>累计花费 <b>${money(product?.ad_spend)}</b></span><span>整体 ROI <b data-tone="${roiTone(product?.roi)}">${ratio(product?.roi)}</b></span></div>`;
    const columns = [
      { key: 'asset', label: '素材', className: 'cb-creative-table__asset' },
      ...[['ctr', '点击率'], ['cvr', '转化率'], ['cart_rate', '加购率'], ['clicks', '点击量'], ['ad_spend', '花费'], ['roi', 'ROI'], ['cart_cost', '加购成本']].map(([key, label]) => ({
        key, label, numeric: true,
        renderHeader: () => {
          const button = document.createElement('button');
          button.className = `cb-sort-button${state.creativeSort.key === key ? ' is-active' : ''}`;
          button.type = 'button';
          button.dataset.newProductsCreativeSort = key;
          button.setAttribute('aria-label', `按${label}排序`);
          button.setAttribute('aria-pressed', String(state.creativeSort.key === key));
          button.append(document.createTextNode(label));
          const icon = document.createElement('i');
          icon.dataset.lucide = state.creativeSort.key === key ? (state.creativeSort.direction === 'asc' ? 'arrow-up' : 'arrow-down') : 'arrow-up-down';
          icon.setAttribute('aria-hidden', 'true');
          button.append(icon);
          return button;
        },
      })),
    ];
    const rows = creativeRows(product);
    const table = TmallUI.table({
      columns, rows, wrapClass: 'cb-detail-list cb-detail-list--table', tableClass: 'cb-creative-table',
      emptyMessage: '该商品暂无素材表现',
      renderRow: (row) => {
        const tr = document.createElement('tr');
        if (row) tr.innerHTML = row.html;
        else tr.innerHTML = '<td colspan="8"><div class="cb-empty">该商品暂无素材表现</div></td>';
        return tr;
      },
    });
    content.append(table);
    body.replaceChildren(content);
    body.querySelectorAll('[data-new-products-image]').forEach((button) => button.addEventListener('click', () => openCreativeImage(button.dataset.newProductsImage)));
    body.querySelectorAll('[data-new-products-creative-sort]').forEach((button) => button.addEventListener('click', () => {
      const key = button.dataset.newProductsCreativeSort;
      state.creativeSort = { key, direction: state.creativeSort.key === key && state.creativeSort.direction === 'desc' ? 'asc' : 'desc' };
      renderCreativeContent(product);
    }));
    window.lucide?.createIcons();
    if (!creatives.length) body.querySelector('.cb-empty')?.setAttribute('role', 'status');
  }

  function openCreativeImage(url) {
    const dialog = $('[data-new-products-image-dialog]');
    const image = $('[data-new-products-image-preview]');
    if (!dialog || !image || !url) return;
    image.src = url;
    dialog.showModal();
  }

  async function renderCreativePanel(productId) {
    const body = $('[data-promotion-structure-body]');
    if (!body || !productId) return;
    const requestId = ++state.creativeRequest;
    body.innerHTML = '<div class="ui-empty-state" role="status"><span>素材加载中…</span></div>';
    try {
      const response = await DemoApi.domainRequest(`/api/creative-board?${new URLSearchParams({ product_id: productId })}`);
      if (requestId !== state.creativeRequest || state.structureProduct !== productId) return;
      const product = Array.isArray(response.data?.products) ? response.data.products[0] : null;
      if (!product) {
        body.innerHTML = '<div class="ui-empty-state" role="status"><span>该商品暂无素材表现</span></div>';
        return;
      }
      renderCreativeContent(product);
    } catch (error) {
      if (requestId !== state.creativeRequest || state.structureProduct !== productId) return;
      body.innerHTML = `<div class="ui-empty-state" role="alert"><span>${esc(error.message || '素材数据加载失败')}</span></div>`;
    }
  }

  function bindCreativeImageDialog() {
    const dialog = $('[data-new-products-image-dialog]');
    if (!dialog) return;
    $('[data-new-products-image-close]')?.addEventListener('click', () => dialog.close());
    dialog.addEventListener('click', (event) => { if (event.target === dialog) dialog.close(); });
  }

  function chart(selector) { const canvas = $(selector); if (!canvas || !window.echarts) return null; return window.echarts.getInstanceByDom(canvas) || window.echarts.init(canvas); }

  let structureDrawer = null;

  function bindStructureDrawer() {
    const template = $('[data-promotion-structure-template]');
    if (!template || !window.TmallUI?.detailDrawer || structureDrawer) return;
    structureDrawer = window.TmallUI.detailDrawer({
      title: '商品推广结构',
      description: '查看渠道结构、计划与素材表现',
      size: 'lg',
      onClose: () => {
        state.structureRequest = (state.structureRequest || 0) + 1;
        state.creativeRequest = (state.creativeRequest || 0) + 1;
        const chartNode = structureDrawer.body.querySelector('#promotionStructureMix');
        if (chartNode) window.echarts?.getInstanceByDom(chartNode)?.dispose();
      },
    });
    structureDrawer.body.append(template.content.cloneNode(true));
    const tabs = $$('[data-promotion-structure-tab]', structureDrawer.node);
    tabs.forEach((button) => {
      button.addEventListener('click', () => {
        tabs.forEach((item) => item.setAttribute('aria-selected', String(item === button)));
        renderStructurePanel(button.dataset.promotionStructureTab);
      });
    });
  }

  function openStructureDialog(productId, trigger = null) {
    if (!structureDrawer || !productId) return;
    state.structureProduct = productId;
    state.creativeRequest += 1;
    const description = structureDrawer.node.querySelector('.ui-drawer__copy p');
    if (description) description.textContent = `商品 ID ${productId} · 渠道结构、计划与素材表现`;
    const tabs = $$('[data-promotion-structure-tab]', structureDrawer.node);
    tabs.forEach((button, index) => button.setAttribute('aria-selected', String(index === 0)));
    structureDrawer.open(trigger);
    renderStructurePanel('mix');
  }

  async function renderStructurePanel(tab) {
    const body = $('[data-promotion-structure-body]'); if (!body || !state.structureProduct) return; const { start, end } = range(); const productId = state.structureProduct;
    const requestId = state.structureRequest = (state.structureRequest || 0) + 1;
    state.creativeRequest = (state.creativeRequest || 0) + 1;
    const isCurrent = () => requestId === state.structureRequest && state.structureProduct === productId && !structureDrawer.node.hidden;
    const previousChart = body.querySelector('#promotionStructureMix');
    if (previousChart) window.echarts?.getInstanceByDom(previousChart)?.dispose();
    structureDrawer.body.scrollTop = 0;
    if (tab === 'creatives') { renderCreativePanel(productId); return; }
    if (tab === 'mix') {
      body.innerHTML = '<div class="chart-box chart-box--tall"><div id="promotionStructureMix" class="chart-canvas"></div></div>';
      try { const response = await DemoApi.domainRequest(`/api/promotion/product-detail?${new URLSearchParams({ start, end, product_id: productId })}`);
        if (!isCurrent()) return; const mix = Array.isArray(response.data?.channel_mix) ? response.data.channel_mix : []; if (!mix.length) { body.innerHTML = '<div class="ui-empty-state"><span>该商品暂无渠道归因数据</span></div>'; return; } const instance = chart('#promotionStructureMix'); instance?.setOption({ tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' }, legend: { bottom: 0, type: 'scroll' }, series: [{ type: 'pie', radius: ['38%', '60%'], center: ['32%', '46%'], label: { show: false }, data: mix.map((row) => ({ name: row.channel, value: Number(row.ad_spend || 0).toFixed(2) })) }, { type: 'pie', radius: ['38%', '60%'], center: ['74%', '46%'], label: { show: false }, data: mix.map((row) => ({ name: row.channel, value: Number(row.attributed_payment_amount || 0).toFixed(2) })) }] }); body.insertAdjacentHTML('beforeend', `<p class="promotion-channel-cards__footnote">左：各渠道花费占比；右：各渠道成交占比。${esc((response.limitations || []).join(' '))}</p>`); } catch (error) {
        if (!isCurrent()) return; body.innerHTML = `<div class="ui-empty-state"><span>${esc(error.message || '结构数据加载失败')}</span></div>`; }
    }
    if (tab === 'campaigns') {
      body.replaceChildren(renderCampaignTable([], '加载中…'));
      try {
        const response = await DemoApi.domainRequest(`/api/promotion/product-detail?${new URLSearchParams({ start, end, product_id: productId })}`);
        if (!isCurrent()) return;
        const campaigns = Array.isArray(response.data?.campaigns) ? response.data.campaigns : [];
        body.replaceChildren(renderCampaignTable(campaigns, '该商品暂无计划数据'));
      } catch (error) {
        if (!isCurrent()) return; body.innerHTML = `<div class="ui-empty-state"><span>${esc(error.message || '计划数据加载失败')}</span></div>`; }
    }
  }

  function renderCampaignTable(rows, emptyMessage) {
    return window.TmallUI.table({
      tableClass: 'promotion-campaign-table',
      columns: [
        { key: 'campaign_name', label: '计划', render: (value, row) => {
          const cell = document.createElement('span');
          cell.append(document.createTextNode(String(value || row.campaign_id || '--')));
          if (row.plan_type) {
            const badge = document.createElement('span');
            badge.className = `plan-type-badge plan-type-badge--${String(row.plan_type).replace(/[^\w-]/g, '')}`;
            badge.textContent = String(row.plan_type);
            cell.append(' ', badge);
          }
          return cell;
        } },
        { key: 'channel', label: '渠道', render: value => value || '--' },
        { key: 'ad_spend', label: '花费', numeric: true, render: money },
        { key: 'roi', label: 'ROI', numeric: true, render: ratio },
        { key: 'cart_cost', label: '加购成本', numeric: true, render: value => value == null ? '--' : money(value) },
      ],
      rows,
      emptyMessage,
    });
  }

  function bind() {
    $$('[data-promotion-new-refresh]').forEach((button) => button.addEventListener('click', loadNewProducts)); $('[data-promotion-new-search]')?.addEventListener('input', renderProducts); $('[data-promotion-new-sort]')?.addEventListener('change', renderProducts); $('[data-promotion-new-launch-toggle]')?.addEventListener('click', () => { state.launchesExpanded = !state.launchesExpanded; renderLaunches(); });
    bindCreativeImageDialog();
    bindStructureDrawer();
    bindProductFields();
    window.addEventListener('tmall:export', (event) => { if (!exportNewProducts()) return; event.preventDefault(); });
    $('[data-promotion-new-export]')?.addEventListener('click', () => { if (!exportNewProducts()) setActionStatus('当前范围没有可导出的新品投放明细。'); });
    window.addEventListener('tmall:date-range-change', loadNewProducts); window.addEventListener('tmall:refresh', loadNewProducts); loadNewProducts();
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', bind); else bind();
})();
