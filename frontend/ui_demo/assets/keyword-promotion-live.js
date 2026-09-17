(async function () {
  'use strict';

  const API_BASE = '/api/keyword-promotion';
  const STORAGE_KEY = 'tmall-kp-visible-columns';

  // ===== 字段定义（分组） =====
  const FIELD_GROUPS = [
    {
      label: '基础信息',
      columns: [
        { key: 'image', label: '主图', sortable: false, width: '56px' },
        { key: 'title', label: '商品标题', sortable: false, width: '100px' },
        { key: 'product_id', label: '商品ID', sortable: false, width: '100px' },
      ],
    },
    {
      label: '商品属性',
      columns: [
        { key: 'category', label: '品类', sortable: false, width: '90px' },
        { key: 'gender', label: '性别', sortable: false, width: '60px' },
        { key: 'season', label: '季节', sortable: false, width: '60px' },
        { key: 'material', label: '材质', sortable: false, width: '100px' },
        { key: 'scene', label: '场景', sortable: false, width: '120px' },
        { key: 'thickness', label: '厚度', sortable: false, width: '70px' },
        { key: 'style', label: '风格', sortable: false, width: '80px' },
      ],
    },
    {
      label: '推广效果',
      columns: [
        { key: 'total_score', label: '综合分', sortable: true, width: '70px' },
        { key: 'score_grade', label: '评级', sortable: false, width: '60px' },
        { key: 'roi', label: 'ROI', sortable: true, width: '70px' },
        { key: 'ad_spend', label: '推广花费', sortable: true, width: '80px' },
        { key: 'payment_amount', label: '推广成交', sortable: true, width: '80px' },
        { key: 'cvr', label: '推广转化率', sortable: true, width: '90px' },
        { key: 'ctr', label: '点击率', sortable: true, width: '70px' },
        { key: 'cart_rate', label: '加购率', sortable: true, width: '70px' },
        { key: 'cpc', label: '点击单价', sortable: false, width: '80px' },
        { key: 'cpm', label: '千次展现花费', sortable: false, width: '100px' },
        { key: 'cart_adds', label: '加购数', sortable: false, width: '70px' },
        { key: 'fav_items', label: '收藏数', sortable: false, width: '70px' },
        { key: 'fav_rate', label: '收藏率', sortable: false, width: '70px' },
        { key: 'total_fav_cart', label: '收藏加购总数', sortable: false, width: '100px' },
        { key: 'total_fav_cart_cost', label: '收藏加购成本', sortable: false, width: '100px' },
        { key: 'cart_cost', label: '加购成本', sortable: false, width: '80px' },
      ],
    },
    {
      label: '成交明细',
      columns: [
        { key: 'payment_buyers', label: '成交人数', sortable: false, width: '80px' },
        { key: 'payment_orders', label: '成交笔数', sortable: false, width: '80px' },
        { key: 'avg_payment_per_buyer', label: '人均成交金额', sortable: false, width: '100px' },
        { key: 'direct_payment_amount', label: '直接成交金额', sortable: false, width: '100px' },
        { key: 'indirect_payment_amount', label: '间接成交金额', sortable: false, width: '100px' },
        { key: 'direct_payment_orders', label: '直接成交笔数', sortable: false, width: '100px' },
        { key: 'indirect_payment_orders', label: '间接成交笔数', sortable: false, width: '100px' },
        { key: 'payment_cost', label: '成交成本', sortable: false, width: '80px' },
        { key: 'roi_with_presale', label: '含预售ROI', sortable: false, width: '80px' },
      ],
    },
    {
      label: '访问/新客',
      columns: [
        { key: 'impressions', label: '展现量', sortable: false, width: '80px' },
        { key: 'clicks', label: '点击量', sortable: false, width: '70px' },
        { key: 'guide_visits', label: '引导访问量', sortable: false, width: '90px' },
        { key: 'guide_visitors', label: '引导访问人数', sortable: false, width: '100px' },
        { key: 'guide_visit_rate', label: '引导访问率', sortable: false, width: '90px' },
        { key: 'deep_visits', label: '深度访问量', sortable: false, width: '90px' },
        { key: 'avg_pages', label: '平均访问页面数', sortable: false, width: '110px' },
        { key: 'new_buyers', label: '成交新客数', sortable: false, width: '90px' },
        { key: 'new_buyer_ratio', label: '新客占比', sortable: false, width: '80px' },
        { key: 'member_signups', label: '入会量', sortable: false, width: '70px' },
        { key: 'member_signup_rate', label: '入会率', sortable: false, width: '70px' },
      ],
    },
    {
      label: '自然流量',
      columns: [
        { key: 'organic_visitors', label: '总访客数', sortable: true, width: '80px' },
        { key: 'organic_payment', label: '整体支付', sortable: true, width: '90px' },
        { key: 'organic_payment_qty', label: '支付件数', sortable: false, width: '80px' },
        { key: 'organic_buyers', label: '买家数', sortable: false, width: '70px' },
        { key: 'organic_cvr', label: '整体转化率', sortable: false, width: '90px' },
        { key: 'organic_uv_value', label: '访客价值', sortable: false, width: '80px' },
        { key: 'organic_cart_qty', label: '加购件数', sortable: false, width: '80px' },
        { key: 'organic_fav_users', label: '收藏人数', sortable: false, width: '80px' },
        { key: 'organic_traffic_payment', label: '自然流量转化金额', sortable: false, width: '120px' },
        { key: 'organic_traffic_impressions', label: '自然流量曝光量', sortable: false, width: '110px' },
        { key: 'platform_boost_payment', label: '平台助推成交', sortable: false, width: '100px' },
      ],
    },
    {
      label: '互动/其他',
      columns: [
        { key: 'coupon_received', label: '优惠券领取量', sortable: false, width: '100px' },
        { key: 'wangwang_consult', label: '旺旺咨询量', sortable: false, width: '90px' },
        { key: 'item_fav_cart_count', label: '宝贝收藏加购数', sortable: false, width: '110px' },
        { key: 'suggested_action', label: '建议动作', sortable: false, width: '120px' },
      ],
    },
  ];

  const ALL_COLUMNS = FIELD_GROUPS.flatMap(g => g.columns);
  const COLUMN_MAP = new Map(ALL_COLUMNS.map(c => [c.key, c]));

  // 字段模板
  const TEMPLATES = {
    promotion: ['image', 'product_id', 'title', 'total_score', 'score_grade', 'roi', 'ad_spend', 'payment_amount', 'cvr', 'ctr', 'cart_rate', 'suggested_action'],
    attribute: ['image', 'title', 'category', 'gender', 'season', 'material', 'scene', 'thickness', 'style'],
    full: ALL_COLUMNS.map(c => c.key),
  };

  // ===== 状态 =====
  const state = {
    filters: { shop_label: '标品袜子', min_spend: '5' },
    sortBy: 'total_score',
    sortOrder: 'desc',
    page: 1,
    pageSize: 50,
    total: 0,
    visibleColumns: loadVisibleColumns(),
  };

  // ===== 工具函数 =====
  function $(sel, root = document) { return root.querySelector(sel); }
  function $$(sel, root = document) { return [...root.querySelectorAll(sel)]; }

  function fmtMoney(v) {
    if (v == null || isNaN(v)) return '--';
    return Number(v).toLocaleString('zh-CN', { maximumFractionDigits: 0 });
  }
  function fmtPct(v) {
    if (v == null || isNaN(v)) return '--';
    return (Number(v) * 100).toFixed(1) + '%';
  }
  function fmtNum(v, digits = 2) {
    if (v == null || isNaN(v)) return '--';
    return Number(v).toFixed(digits);
  }
  function fmtInt(v) {
    if (v == null || isNaN(v)) return '--';
    return Number(v).toLocaleString('zh-CN', { maximumFractionDigits: 0 });
  }
  function gradeBadge(grade) {
    if (!grade) return '<span class="kp-badge kp-badge--data">--</span>';
    const cls = grade.startsWith('S') ? 'kp-badge--s' : grade.startsWith('A') ? 'kp-badge--a' : grade.startsWith('B') ? 'kp-badge--b' : grade.startsWith('C') ? 'kp-badge--c' : 'kp-badge--data';
    return `<span class="kp-badge ${cls}">${grade.split('-')[0] || grade}</span>`;
  }
  function roiClass(roi) {
    if (roi == null) return '';
    return roi >= 1 ? 'kp-roi-good' : 'kp-roi-bad';
  }

  // ===== 列设置持久化 =====
  function loadVisibleColumns() {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) {
        const arr = JSON.parse(saved);
        const valid = arr.filter(k => COLUMN_MAP.has(k));
        if (valid.length) return valid;
      }
    } catch (e) { }
    return [...TEMPLATES.promotion];
  }
  function saveVisibleColumns() {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(state.visibleColumns)); } catch (e) { }
  }

  // ===== 渲染表头 =====
  function renderHead() {
    const tr = $('[data-kp-head]');
    tr.innerHTML = state.visibleColumns.map(key => {
      const col = COLUMN_MAP.get(key);
      if (!col) return '';
      const sortIcon = col.sortable ? `<span class="sort-icon${state.sortBy === key ? ' sort-icon--active' : ''}"></span>` : '';
      return `<th data-sort="${col.sortable ? key : ''}" style="min-width:${col.width || 'auto'}">${col.label}${sortIcon}</th>`;
    }).join('');
  }

  // ===== 渲染单元格 =====
  function renderCell(row, key) {
    const v = row[key];
    switch (key) {
      case 'image':
        return row.image_url
          ? `<a href="https://detail.tmall.com/item.htm?id=${row.product_id}" target="_blank"><img src="${row.image_url}" alt="" style="width:40px;height:40px;object-fit:cover;border-radius:4px;"></a>`
          : `<a href="https://detail.tmall.com/item.htm?id=${row.product_id}" target="_blank"><div style="width:40px;height:40px;background:var(--surface-2);border-radius:4px;display:flex;align-items:center;justify-content:center;font-size:10px;color:var(--text-tertiary);">无图</div></a>`;
      case 'title':
        return `<a href="https://detail.tmall.com/item.htm?id=${row.product_id}" target="_blank" title="${row.title || ''}" style="color:inherit;text-decoration:none;display:-webkit-box;-webkit-line-clamp:1;-webkit-box-orient:vertical;overflow:hidden;">${row.title || '--'}</a>`;
      case 'product_id':
        return `<code style="font-size:11px;">${row.product_id || '--'}</code>`;
      case 'total_score':
        return `<strong>${fmtNum(v, 1)}</strong>`;
      case 'score_grade':
        return gradeBadge(v);
      case 'roi':
        return `<span class="${roiClass(v)}">${fmtNum(v)}</span>`;
      case 'ad_spend':
      case 'payment_amount':
      case 'organic_payment':
      case 'organic_uv_value':
      case 'cpc':
      case 'cpm':
      case 'total_fav_cart_cost':
      case 'cart_cost':
      case 'avg_payment_per_buyer':
      case 'direct_payment_amount':
      case 'indirect_payment_amount':
      case 'payment_cost':
      case 'organic_traffic_payment':
      case 'platform_boost_payment':
        return fmtMoney(v);
      case 'cvr':
      case 'ctr':
      case 'cart_rate':
      case 'organic_cvr':
      case 'fav_rate':
      case 'guide_visit_rate':
      case 'new_buyer_ratio':
      case 'member_signup_rate':
        return fmtPct(v);
      case 'organic_visitors':
      case 'organic_payment_qty':
      case 'organic_buyers':
      case 'organic_cart_qty':
      case 'organic_fav_users':
      case 'cart_adds':
      case 'fav_items':
      case 'total_fav_cart':
      case 'item_fav_cart_count':
      case 'payment_buyers':
      case 'payment_orders':
      case 'direct_payment_orders':
      case 'indirect_payment_orders':
      case 'impressions':
      case 'clicks':
      case 'guide_visits':
      case 'guide_visitors':
      case 'deep_visits':
      case 'new_buyers':
      case 'member_signups':
      case 'organic_traffic_impressions':
      case 'coupon_received':
      case 'wangwang_consult':
        return fmtInt(v);
      case 'avg_pages':
      case 'roi_with_presale':
        return fmtNum(v, 2);
      case 'scene':
        return (v || '').split(/[、,，]/).slice(0, 2).map(s => `<span class="kp-tag">${s.trim()}</span>`).join('') || '--';
      case 'material':
        return (v || '').split(/[,，]/).slice(0, 2).map(s => `<span class="kp-tag">${s.trim()}</span>`).join('') || '--';
      case 'suggested_action':
        return v ? `<span class="kp-tag kp-tag--action">${v}</span>` : '--';
      default:
        return v != null && v !== '' ? v : '--';
    }
  }

  // ===== 渲染表格 =====
  function renderTable(rows) {
    const tbody = $('[data-kp-body]');
    const colCount = state.visibleColumns.length;
    if (!rows.length) {
      tbody.innerHTML = `<tr><td colspan="${colCount}">没有符合条件的商品</td></tr>`;
      return;
    }
    tbody.innerHTML = rows.map(row => {
      const tds = state.visibleColumns.map(key => `<td>${renderCell(row, key)}</td>`).join('');
      return `<tr>${tds}</tr>`;
    }).join('');
  }

  // ===== 加载筛选器选项 =====
  async function loadFilterOptions() {
    try {
      const res = await fetch(`${API_BASE}/filters`);
      const data = await res.json();
      if (!data.ok) return;
      const opts = data.data || {};

      const fillSelect = (sel, values) => {
        if (!sel) return;
        const current = sel.value;
        const opts = (values || []).map(v => typeof v === 'object' && v !== null ? v.value : v).filter(Boolean);
        sel.innerHTML = '<option value="">全部</option>' + opts.map(v => `<option value="${v}">${v}</option>`).join('');
        if (current && opts.includes(current)) sel.value = current;
      };

      fillSelect($('[data-kp-category]'), opts.category || []);
      fillSelect($('[data-kp-gender]'), opts.gender || []);
      fillSelect($('[data-kp-season]'), opts.season || []);
      fillSelect($('[data-kp-grade]'), opts.score_grade || []);
      fillSelect($('[data-kp-material]'), opts.material || []);
      fillSelect($('[data-kp-scene]'), opts.scene || []);
      fillSelect($('[data-kp-thickness]'), opts.thickness || []);
      fillSelect($('[data-kp-style]'), opts.style || []);
      fillSelect($('[data-kp-action]'), opts.suggested_action || []);
    } catch (e) {
      console.error('加载筛选选项失败', e);
    }
  }

  // ===== 构建筛选参数 =====
  function buildFilters() {
    const f = {};
    const map = {
      'data-kp-search': 'keyword',
      'data-kp-shop-label': 'shop_label',
      'data-kp-category': 'category',
      'data-kp-gender': 'gender',
      'data-kp-season': 'season',
      'data-kp-material': 'material',
      'data-kp-scene': 'scene',
      'data-kp-thickness': 'thickness',
      'data-kp-style': 'style',
      'data-kp-grade': 'score_grade',
      'data-kp-action': 'suggested_action',
    };
    Object.entries(map).forEach(([attr, key]) => {
      const el = $(`[${attr}]`);
      if (el && el.value) f[key] = el.value;
    });
    const minSpend = $('[data-kp-min-spend]').value;
    if (minSpend) f.min_spend = minSpend;
    const minRoi = $('[data-kp-min-roi]').value;
    if (minRoi) f.min_roi = minRoi;
    return f;
  }

  // ===== 加载汇总 =====
  async function loadSummary() {
    try {
      const params = new URLSearchParams(state.filters);
      const res = await fetch(`${API_BASE}/summary?${params}`);
      const data = await res.json();
      if (!data.ok) return;
      const s = data.data;
      const set = (key, val) => { const el = $(`[data-kp-kpi="${key}"]`); if (el) el.textContent = val; };
      set('count', s.product_count || 0);
      set('spend', fmtMoney(s.total_spend) + ' 元');
      set('payment', fmtMoney(s.total_payment) + ' 元');
      set('roi', fmtNum(s.overall_roi));
      set('cvr', fmtPct(s.avg_cvr));
      set('roi_ok', `${s.roi_qualified || 0} / ${s.product_count || 0}`);
    } catch (e) {
      console.error('加载汇总失败', e);
    }
  }

  // ===== 加载商品列表 =====
  async function loadProducts() {
    const tbody = $('[data-kp-body]');
    const colCount = state.visibleColumns.length;
    tbody.innerHTML = `<tr><td colspan="${colCount}">加载中…</td></tr>`;

    try {
      const params = new URLSearchParams({
        ...state.filters,
        sort_by: state.sortBy,
        sort_order: state.sortOrder,
        page: state.page,
        page_size: state.pageSize,
      });
      const res = await fetch(`${API_BASE}/products?${params}`);
      const data = await res.json();
      if (!data.ok) throw new Error(data.error || '加载失败');

      const result = data.data;
      state.total = result.total;
      renderTable(result.rows);
      updatePagination();
      $('[data-kp-status]').textContent = `共 ${result.total} 个商品，当前第 ${state.page} 页`;
    } catch (e) {
      console.error('加载商品列表失败', e);
      tbody.innerHTML = `<tr><td colspan="${colCount}" style="color:#dc2626">加载失败: ${e.message || e}</td></tr>`;
    }
  }

  // ===== 分页 =====
  function updatePagination() {
    const totalPages = Math.ceil(state.total / state.pageSize) || 1;
    $('[data-kp-page-summary]').textContent = `第 ${state.page} / ${totalPages} 页，共 ${state.total} 条`;
    $('[data-kp-prev]').disabled = state.page <= 1;
    $('[data-kp-next]').disabled = state.page >= totalPages;
  }

  function reload() {
    state.page = 1;
    loadSummary();
    loadProducts();
  }

  // ===== 列设置弹窗 =====
  let columnSelector = null;
  let columnsReturnFocus = null;
  const TEMPLATE_STORAGE_KEY = 'tmall-kp-custom-templates';

  function loadCustomTemplates() {
    try {
      return JSON.parse(localStorage.getItem(TEMPLATE_STORAGE_KEY) || '{}');
    } catch (e) { return {}; }
  }
  function saveCustomTemplates(templates) {
    try { localStorage.setItem(TEMPLATE_STORAGE_KEY, JSON.stringify(templates)); } catch (e) { }
  }
  function getAllTemplates() {
    return { ...TEMPLATES, ...loadCustomTemplates() };
  }

  function selectedDialogColumns() {
    return columnSelector ? columnSelector.getSelected() : [...state.visibleColumns];
  }

  function updateColumnsDialogStatus() {
    const selected = selectedDialogColumns();
    $('[data-kp-visible-count]').textContent = selected.length;
    $('[data-kp-columns-apply]').disabled = selected.length === 0;
    $('[data-kp-template-save]').disabled = selected.length === 0;
    $('[data-kp-columns-status]').textContent = selected.length ? '' : '至少保留一个可见字段';
  }

  function renderColumnOptions(selected = state.visibleColumns) {
    const config = {
      groups: FIELD_GROUPS.map(g => ({ label: g.label, fields: g.columns })),
      selected,
    };
    if (!columnSelector && window.DemoFieldSelector) {
      columnSelector = DemoFieldSelector.create({
        root: $('[data-kp-field-selector]'),
        ...config,
        className: 'products-field-selection-layout',
        availableTitleId: 'kpAvailableFieldsTitle',
        previewTitleId: 'kpFieldPreviewTitle',
        optionDataAttribute: 'data-kp-column-key',
        previewDataAttribute: 'data-kp-preview-key',
        onChange: updateColumnsDialogStatus,
      });
    } else if (columnSelector) {
      columnSelector.setConfig(config);
    } else {
      // 降级：简单checkbox
      const container = $('[data-kp-field-selector]');
      container.innerHTML = FIELD_GROUPS.map(group => `
        <div class="kp-field-group">
          <div class="kp-field-group__title">${group.label}</div>
          <div class="kp-field-group__items">
            ${group.columns.map(col => `
              <label class="kp-field-item">
                <input type="checkbox" value="${col.key}" ${selected.includes(col.key) ? 'checked' : ''}>
                <span>${col.label}</span>
              </label>
            `).join('')}
          </div>
        </div>
      `).join('');
      container.querySelectorAll('input[type="checkbox"]').forEach(cb => {
        cb.addEventListener('change', () => {
          let cur = selectedDialogColumns();
          if (cb.checked) { if (!cur.includes(cb.value)) cur.push(cb.value); }
          else { cur = cur.filter(k => k !== cb.value); }
          updateColumnsDialogStatus();
        });
      });
    }
    renderTemplateSelect();
    renderTemplateManager();
    updateColumnsDialogStatus();
    window.lucide?.createIcons();
  }

  function renderTemplateSelect(activeKey) {
    const select = $('[data-kp-template-select]');
    if (!select) return;
    const templates = getAllTemplates();
    const current = select.value;
    select.innerHTML = Object.entries(templates).map(([key, cols]) =>
      `<option value="${key}" ${key === activeKey || key === current ? 'selected' : ''}>${key === 'promotion' ? '推广效果' : key === 'attribute' ? '商品属性' : key === 'full' ? '全字段' : key}</option>`
    ).join('');
  }

  function renderTemplateManager() {
    const container = $('[data-kp-template-manager]');
    if (!container) return;
    const custom = loadCustomTemplates();
    const keys = Object.keys(custom);
    if (!keys.length) { container.innerHTML = ''; return; }
    container.innerHTML = keys.map(key => `
      <div class="field-template-manager__item">
        <span>${key} (${custom[key].length}个字段)</span>
        <div>
          <button class="button button--ghost" type="button" data-kp-template-load="${key}">应用</button>
          <button class="button button--ghost" type="button" data-kp-template-delete="${key}"><i data-lucide="trash-2"></i></button>
        </div>
      </div>
    `).join('');
    container.querySelectorAll('[data-kp-template-load]').forEach(btn => {
      btn.addEventListener('click', () => {
        const tpl = loadCustomTemplates()[btn.dataset.kpTemplateLoad];
        if (tpl) renderColumnOptions(tpl);
      });
    });
    container.querySelectorAll('[data-kp-template-delete]').forEach(btn => {
      btn.addEventListener('click', () => {
        const tpls = loadCustomTemplates();
        delete tpls[btn.dataset.kpTemplateDelete];
        saveCustomTemplates(tpls);
        renderTemplateSelect();
        renderTemplateManager();
        $('[data-kp-columns-status]').textContent = '模板已删除';
      });
    });
  }

  function openColumnsDialog(event) {
    columnsReturnFocus = event.currentTarget;
    renderColumnOptions();
    $('[data-kp-columns-dialog]').hidden = false;
    $('[data-kp-columns-dialog]').showModal();
    window.setTimeout(() => $('[data-kp-columns-dialog]').querySelector('input')?.focus(), 0);
  }
  function closeColumnsDialog() {
    const dlg = $('[data-kp-columns-dialog]');
    if (dlg.open) dlg.close();
    dlg.hidden = true;
    columnsReturnFocus?.focus?.();
    columnsReturnFocus = null;
  }

  function applyColumns() {
    const selected = selectedDialogColumns();
    if (selected.length === 0) return;
    state.visibleColumns = ALL_COLUMNS.map(c => c.key).filter(k => selected.includes(k));
    saveVisibleColumns();
    renderHead();
    loadProducts();
    closeColumnsDialog();
  }

  function saveCustomTemplate() {
    const input = $('[data-kp-template-name]');
    const name = input.value.trim();
    if (!name) { $('[data-kp-columns-status]').textContent = '请输入模板名称'; input.focus(); return; }
    const selected = selectedDialogColumns();
    const tpls = loadCustomTemplates();
    tpls[name] = selected;
    saveCustomTemplates(tpls);
    renderTemplateSelect(name);
    renderTemplateManager();
    input.value = '';
    $('[data-kp-columns-status]').textContent = `模板"${name}"已保存`;
  }

  function applyTemplate(name) {
    state.visibleColumns = [...TEMPLATES[name]];
    saveVisibleColumns();
    renderHead();
    loadProducts();
    $$('[data-kp-view]').forEach(btn => {
      btn.setAttribute('aria-pressed', btn.dataset.kpView === name ? 'true' : 'false');
    });
  }

  // ===== 事件绑定 =====
  function bindEvents() {
    // 搜索回车
    $('[data-kp-search]').addEventListener('keydown', e => {
      if (e.key === 'Enter') { state.filters = buildFilters(); reload(); }
    });

    // 筛选器变化
    ['data-kp-shop-label', 'data-kp-category', 'data-kp-gender', 'data-kp-season',
     'data-kp-material', 'data-kp-scene', 'data-kp-thickness', 'data-kp-style',
     'data-kp-grade', 'data-kp-action'].forEach(attr => {
      const el = $(`[${attr}]`);
      if (el) el.addEventListener('change', () => { state.filters = buildFilters(); reload(); });
    });

    // 排序
    $('[data-kp-sort]').addEventListener('change', () => {
      state.sortBy = $('[data-kp-sort]').value;
      state.sortOrder = $('[data-kp-order]').value;
      loadProducts();
    });
    $('[data-kp-order]').addEventListener('change', () => {
      state.sortOrder = $('[data-kp-order]').value;
      loadProducts();
    });

    // 表头点击排序
    $('[data-kp-head]').addEventListener('click', e => {
      const th = e.target.closest('th[data-sort]');
      if (!th || !th.dataset.sort) return;
      const col = th.dataset.sort;
      if (state.sortBy === col) {
        state.sortOrder = state.sortOrder === 'desc' ? 'asc' : 'desc';
      } else {
        state.sortBy = col;
        state.sortOrder = 'desc';
      }
      $('[data-kp-sort]').value = col;
      $('[data-kp-order]').value = state.sortOrder;
      loadProducts();
    });

    // 更多筛选
    $('[data-kp-more-toggle]').addEventListener('click', () => {
      const panel = $('[data-kp-more-filters]');
      const btn = $('[data-kp-more-toggle]');
      panel.hidden = !panel.hidden;
      btn.setAttribute('aria-expanded', !panel.hidden);
    });

    // 最低花费/ROI
    $('[data-kp-min-spend]').addEventListener('change', () => { state.filters = buildFilters(); reload(); });
    $('[data-kp-min-roi]').addEventListener('change', () => { state.filters = buildFilters(); reload(); });

    // 分页
    $('[data-kp-prev]').addEventListener('click', () => { if (state.page > 1) { state.page--; loadProducts(); } });
    $('[data-kp-next]').addEventListener('click', () => { state.page++; loadProducts(); });
    $('[data-kp-page-size]').addEventListener('change', () => {
      state.pageSize = parseInt($('[data-kp-page-size]').value);
      state.page = 1;
      loadProducts();
    });

    // 重置
    $('[data-kp-reset]').addEventListener('click', () => {
      $('[data-kp-search]').value = '';
      $('[data-kp-shop-label]').value = '标品袜子';
      ['data-kp-category', 'data-kp-gender', 'data-kp-season', 'data-kp-material',
       'data-kp-scene', 'data-kp-thickness', 'data-kp-style', 'data-kp-grade', 'data-kp-action'].forEach(attr => {
        const el = $(`[${attr}]`); if (el) el.value = '';
      });
      $('[data-kp-min-spend]').value = '5';
      $('[data-kp-min-roi]').value = '';
      $('[data-kp-sort]').value = 'total_score';
      $('[data-kp-order]').value = 'desc';
      state.sortBy = 'total_score';
      state.sortOrder = 'desc';
      state.filters = buildFilters();
      reload();
    });

    // 字段模板切换
    $$('[data-kp-view]').forEach(btn => {
      btn.addEventListener('click', () => applyTemplate(btn.dataset.kpView));
    });

    // 列设置
    $('[data-kp-columns-open]').addEventListener('click', openColumnsDialog);
    $$('[data-kp-columns-close]').forEach(btn => btn.addEventListener('click', closeColumnsDialog));
    $('[data-kp-columns-apply]').addEventListener('click', applyColumns);
    $('[data-kp-columns-select-all]').addEventListener('click', () => renderColumnOptions(ALL_COLUMNS.map(c => c.key)));
    $('[data-kp-columns-clear-all]').addEventListener('click', () => renderColumnOptions([]));
    $('[data-kp-columns-reset]').addEventListener('click', () => renderColumnOptions([...TEMPLATES.promotion]));
    $('[data-kp-template-apply]').addEventListener('click', () => {
      const key = $('[data-kp-template-select]').value;
      const tpl = getAllTemplates()[key];
      if (tpl) renderColumnOptions(tpl);
    });
    $('[data-kp-template-save]').addEventListener('click', saveCustomTemplate);

    // 弹窗取消
    $('[data-kp-columns-dialog]').addEventListener('cancel', e => { e.preventDefault(); closeColumnsDialog(); });
    $('[data-kp-columns-dialog]').addEventListener('close', () => {
      $('[data-kp-columns-dialog]').hidden = true;
      columnsReturnFocus?.focus?.();
      columnsReturnFocus = null;
    });
  }

  // ===== 初始化 =====
  async function init() {
    renderHead();
    bindEvents();
    await loadFilterOptions();
    state.filters = buildFilters();
    loadSummary();
    loadProducts();
    if (window.lucide) lucide.createIcons();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
