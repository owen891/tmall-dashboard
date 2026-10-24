// 推广矩阵：新老品 × 渠道投放效率 + 单品效率结论。
// 结构全部由 TmallUI 工厂生成（panel / metricGrid / tableToolbar / table），
// HTML 只留挂载点，避免手写复合组件与工厂输出漂移。
// 数据全部来自 /api/promotion/matrix；判定阈值（花费/成交下限、基准倍数）
// 由接口的 baseline_rule 下发，页面不写死。
(function () {
  const $ = (selector, root = document) => root.querySelector(selector);
  const F = window.DemoFormat;
  const money = (value) => (F ? F.moneyWan(value) : '--');
  const percent = (value, digits = 2) => (F ? F.percent(value, digits) : '--');
  const ratio = (value) => {
    const num = Number(value);
    return Number.isFinite(num) && value !== null && value !== '' ? num.toFixed(2) : '--';
  };
  const count = (value) => {
    const num = Number(value);
    return Number.isFinite(num) ? num.toLocaleString('zh-CN') : '--';
  };

  // 与推广分析页同一个 ROI 分档：≥3 优秀、≥1.5 一般、其余偏弱。
  const roiTone = (value) => {
    const num = Number(value);
    if (!Number.isFinite(num) || num <= 0) return 'muted';
    if (num >= 3) return 'success';
    if (num >= 1.5) return 'warning';
    return 'danger';
  };

  const VERDICTS = [
    { key: 'all', label: '全部', tone: 'muted' },
    { key: 'scale', label: '可放大', tone: 'success' },
    { key: 'steady', label: '持平', tone: 'muted' },
    { key: 'optimize', label: '需优化', tone: 'danger' },
    { key: 'insufficient', label: '样本不足', tone: 'muted' },
  ];
  const VERDICT_MAP = new Map(VERDICTS.map((item) => [item.key, item]));
  const STAGE_LABEL = { new: '新品', old: '老品', unknown: '未匹配' };
  // 新老品筛选：直接用接口下发的 stage 字段，不在这里重算日期口径。
  const STAGES = [
    { key: 'all', label: '全部' },
    { key: 'new', label: '新品' },
    { key: 'old', label: '老品' },
    { key: 'unknown', label: '未匹配' },
  ];

  const state = { data: null, stage: 'all', verdict: 'all', search: '' };
  const els = { kpi: {}, kpiMeta: {}, baseline: null, matrixHost: null, productsHost: null, fieldTrigger: null, stageFilter: null, filter: null, search: null, rowCount: null, coverage: null, notes: null, window: null, minSpend: null, minPayment: null, stageButtons: new Map(), filterButtons: new Map() };

  function range(detail) {
    const current = detail || window.TmallDateRange?.getState?.() || {};
    const period = current.endDate || current.startDate || new Date().toISOString().slice(0, 10);
    const month = String(period).slice(0, 7);
    return { start: current.startDate || `${month}-01`, end: current.endDate || `${month}-31` };
  }

  function toneCell(tone, text) {
    const cell = document.createElement('span');
    cell.dataset.tone = tone;
    cell.textContent = text;
    return cell;
  }

  function small(text, extra = '') {
    const node = document.createElement('span');
    node.className = ['pm-note', extra].filter(Boolean).join(' ');
    node.textContent = text;
    return node;
  }

  function hintNode(text) {
    const node = document.createElement('p');
    node.className = 'ui-panel__hint';
    node.textContent = text;
    return node;
  }

  // 两组筛选各带一个短标签，避免两排 segmented 并排时分不清哪组管什么。
  function filterGroup(label, control) {
    const group = document.createElement('div');
    group.className = 'pm-filter-group';
    const text = document.createElement('span');
    text.className = 'pm-filter-label';
    text.textContent = label;
    group.append(text, control);
    return group;
  }

  // 面板工具位：字段设置按钮。按钮走 TmallUI 工厂，新页面不手写复合组件。
  function fieldTools() {
    const wrap = document.createElement('div');
    wrap.className = 'panel__tools';
    els.fieldTrigger = window.TmallUI.button({ label: '字段设置', variant: 'secondary', ariaLabel: '设置单品表显示字段' });
    els.fieldTrigger.setAttribute('aria-haspopup', 'dialog');
    wrap.append(els.fieldTrigger);
    return wrap;
  }

  function buildPage() {
    const host = $('[data-pm-page]');
    if (!host || !window.TmallUI?.metricGrid || !window.TmallUI?.panel) return false;

    const header = window.TmallUI.pageHeader({
      title: '推广矩阵',
      description: '只看新老品在各渠道的投放效率。上架 60 天内算新品；单品是否可放大，按它的 ROI 与同渠道基准比。',
    });

    const cards = [
      ['spend', '商品级推广花费'],
      ['payment', '商品级推广成交'],
      ['roi', '整体 ROI'],
      ['coverage', '明细覆盖率'],
    ].map(([key, label]) => {
      const card = window.TmallUI.metricCard({ label, value: '--' });
      els.kpi[key] = card.querySelector('.ui-metric-card__value');
      els.kpiMeta[key] = card.querySelector('.ui-metric-card__meta');
      return card;
    });
    const summary = window.TmallUI.metricGrid(cards, 'pm-summary');

    els.baseline = small('', 'pm-baseline-note');
    const matrixPanel = window.TmallUI.panel({
      title: '新老品 × 渠道',
      hint: '同样的渠道，新品和老品的投产差多少；合计列同时包含无法匹配到商品的少量花费。',
      tools: els.baseline,
      className: 'pm-panel--table pm-matrix-panel',
    });
    els.matrixHost = document.createElement('div');
    els.matrixHost.className = 'pm-table-host';
    matrixPanel.querySelector('.ui-panel__body').append(els.matrixHost);

    const productsPanel = window.TmallUI.panel({
      title: '单品效率结论',
      // 阈值文案在 renderDisclosure 里用接口下发的值替换。
      hint: '',
      // 字段设置放在面板工具位，和推广分析/新品的字段设置位置一致。
      tools: fieldTools(),
      className: 'pm-panel--table pm-products-panel',
    });
    els.minSpend = document.createElement('span');
    els.minPayment = document.createElement('span');
    const productsHint = productsPanel.querySelector('.ui-panel__hint');
    if (productsHint) {
      productsHint.append('花费 ≥ ', els.minSpend, ' 元且成交 ≥ ', els.minPayment, ' 元才给结论，避免小样本 ROI 失真。');
    }
    const productsBody = productsPanel.querySelector('.ui-panel__body');

    els.stageFilter = document.createElement('div');
    els.stageFilter.className = 'segmented';
    els.stageFilter.setAttribute('role', 'group');
    els.stageFilter.setAttribute('aria-label', '按新老品筛选');
    els.filter = document.createElement('div');
    els.filter.className = 'segmented';
    els.filter.setAttribute('role', 'group');
    els.filter.setAttribute('aria-label', '按效率结论筛选');
    els.search = document.createElement('input');
    els.search.className = 'input pm-search';
    els.search.type = 'search';
    els.search.placeholder = '搜索商品名或 ID';
    els.search.setAttribute('aria-label', '搜索商品');
    const toolbar = window.TmallUI.tableToolbar({
      filters: [
        filterGroup('新老', els.stageFilter),
        filterGroup('效率', els.filter),
        els.search,
      ],
      summary: '加载中…',
    });
    els.rowCount = toolbar.querySelector('.ui-table-toolbar__summary');
    productsBody.append(toolbar);

    els.productsHost = document.createElement('div');
    els.productsHost.className = 'pm-table-host';
    productsBody.append(els.productsHost);

    const disclosure = window.TmallUI.panel({
      title: '口径与覆盖',
      hint: '',
      className: 'pm-disclosure',
    });
    els.window = disclosure.querySelector('.ui-panel__hint');
    els.coverage = document.createElement('dl');
    els.coverage.className = 'pm-coverage';
    els.notes = document.createElement('ul');
    els.notes.className = 'pm-notes';
    disclosure.querySelector('.ui-panel__body').append(els.coverage, els.notes);

    host.replaceChildren(header, summary, matrixPanel, productsPanel, disclosure);
    return true;
  }

  function renderSummary(data) {
    const totals = data.totals || {};
    const coverage = data.coverage || {};
    const set = (key, value) => { if (els.kpi[key]) els.kpi[key].textContent = value; };
    const setMeta = (key, value) => { if (els.kpiMeta[key]) els.kpiMeta[key].textContent = value; };
    set('spend', money(totals.ad_spend));
    set('payment', money(totals.attributed_payment));
    set('roi', ratio(totals.roi));
    set('coverage', percent(coverage.spend_coverage, 1));
    setMeta('spend', `${count(totals.product_count)} 个商品 · 费比 ${percent(totals.expense_ratio)}`);
    setMeta('payment', `其中直接成交 ${money(totals.direct_payment)}`);
    setMeta('roi', `加购成本 ${money(totals.cart_cost)} · CPC ${money(totals.cpc)}`);
    setMeta('coverage', `未归因 ${money(coverage.unattributed_spend)}（多商品计划，不做均摊）`);
  }

  function renderBaselineNote(data) {
    if (!els.baseline) return;
    const baseline = data.baseline || {};
    const parts = Object.entries(baseline)
      .filter(([, value]) => value != null)
      .map(([channel, value]) => `${channel} ${ratio(value)}`);
    els.baseline.textContent = parts.length ? `同渠道基准 ROI：${parts.join(' · ')}` : '';
  }

  function renderMatrix(data) {
    if (!els.matrixHost || !window.TmallUI?.table) return;
    const groups = Array.isArray(data.groups) ? data.groups : [];
    const channels = Array.isArray(data.channels) ? data.channels : [];
    if (!channels.length) {
      els.matrixHost.replaceChildren(window.TmallUI.emptyState('当前范围没有可归因到商品的推广花费'));
      return;
    }
    const groupsOf = (key) => groups.find((group) => group.key === key) || null;
    const stages = { new: groupsOf('new'), old: groupsOf('old') };
    const cellOf = (stageKey, channel) => (stages[stageKey]?.cells || []).find((cell) => cell.channel === channel) || null;

    const rows = channels.map((channel) => ({
      label: channel.label,
      newCell: cellOf('new', channel.channel),
      oldCell: cellOf('old', channel.channel),
      total: channel,
    }));

    const amount = (cell) => (cell ? money(cell.ad_spend) : '--');
    const payment = (cell) => (cell ? money(cell.attributed_payment) : '--');
    const roi = (cell) => (cell && cell.roi != null ? toneCell(roiTone(cell.roi), ratio(cell.roi)) : '--');

    const columns = [
      { key: 'label', label: '渠道', rowHeader: true, render: (_value, row) => row.label },
      { key: 'newSpend', label: '新品花费', numeric: true, render: (_value, row) => amount(row.newCell) },
      { key: 'newPayment', label: '新品成交', numeric: true, render: (_value, row) => payment(row.newCell) },
      { key: 'newRoi', label: '新品 ROI', numeric: true, render: (_value, row) => roi(row.newCell) },
      { key: 'oldSpend', label: '老品花费', numeric: true, render: (_value, row) => amount(row.oldCell) },
      { key: 'oldPayment', label: '老品成交', numeric: true, render: (_value, row) => payment(row.oldCell) },
      { key: 'oldRoi', label: '老品 ROI', numeric: true, render: (_value, row) => roi(row.oldCell) },
      { key: 'totalSpend', label: '合计花费', numeric: true, render: (_value, row) => money(row.total.ad_spend) },
      { key: 'share', label: '花费占比', numeric: true, render: (_value, row) => percent(row.total.spend_share, 1) },
    ];

    const footer = {
      label: '合计',
      newCell: stages.new?.totals || null,
      oldCell: stages.old?.totals || null,
      // 合计行的渠道占比恒为 100%：各渠道 share 之和就是全量，不必再算一次。
      total: { ...(data.totals || {}), spend_share: 1 },
    };

    const matrixScroll = window.TmallUI.table({
      caption: '新老品 × 渠道投放效率',
      columns,
      rows,
      footerRows: [footer],
      tableClass: 'pm-matrix-table',
      rowClassName: 'pm-matrix-row',
      emptyMessage: '当前范围没有可归因到商品的推广花费',
    });
    els.matrixHost.replaceChildren(decorateSortValues(matrixScroll, rows, columns, (row, column) => {
      // 矩阵列的值藏在 cell 对象里，不是行字段，按列显式取原始数值。
      switch (column.key) {
        case 'newSpend': return row.newCell?.ad_spend;
        case 'newPayment': return row.newCell?.attributed_payment;
        case 'newRoi': return row.newCell?.roi;
        case 'oldSpend': return row.oldCell?.ad_spend;
        case 'oldPayment': return row.oldCell?.attributed_payment;
        case 'oldRoi': return row.oldCell?.roi;
        case 'totalSpend': return row.total?.ad_spend;
        case 'share': return row.total?.spend_share;
        default: return null;
      }
    }, (column) => Boolean(column.numeric)));
  }

  function renderStageFilter(data) {
    if (!els.stageFilter) return;
    const rows = Array.isArray(data.products) ? data.products : [];
    const counts = { all: rows.length, new: 0, old: 0, unknown: 0 };
    rows.forEach((row) => {
      const key = STAGE_LABEL[row.stage] ? row.stage : 'unknown';
      counts[key] = (counts[key] || 0) + 1;
    });
    // 选中的新老品在当前区间没数据时回落到「全部」，否则表格会静默变空。
    if (state.stage !== 'all' && !counts[state.stage]) state.stage = 'all';
    els.stageButtons.clear();
    els.stageFilter.replaceChildren();
    STAGES.filter((item) => item.key !== 'unknown' || counts.unknown > 0).forEach((item) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.setAttribute('aria-pressed', String(state.stage === item.key));
      button.textContent = `${item.label} ${count(counts[item.key] || 0)}`;
      els.stageButtons.set(item.key, button);
      els.stageFilter.append(button);
    });
  }

  // 结论计数只统计当前新老品范围内的商品，这样筛「新品」时按钮上的数字也对得上。
  function verdictCounts() {
    const rows = (state.data?.products || []).filter((row) => state.stage === 'all' || row.stage === state.stage);
    const counts = { scale: 0, steady: 0, optimize: 0, insufficient: 0 };
    rows.forEach((row) => {
      if (counts[row.verdict] != null) counts[row.verdict] += 1;
    });
    return { total: rows.length, counts };
  }

  function renderVerdictFilter() {
    if (!els.filter) return;
    const { total, counts } = verdictCounts();
    els.filterButtons.clear();
    // 先清空再重建：日期切换会重新渲染筛选条，直接 append 会让按钮越叠越多。
    els.filter.replaceChildren();
    VERDICTS.forEach((item) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.setAttribute('aria-pressed', String(state.verdict === item.key));
      button.textContent = `${item.label} ${count(item.key === 'all' ? total : counts[item.key] || 0)}`;
      els.filterButtons.set(item.key, button);
      els.filter.append(button);
    });
  }

  function productIdentityCell(row) {
    return window.TmallUI.productIdentity({
      title: row.title,
      id: row.product_id,
      imageUrl: row.image_url,
      className: 'pm-product',
      metaText: row.list_date ? `${row.list_date} 上架` : '上架日期缺失',
    });
  }

  function verdictBadge(row) {
    const meta = VERDICT_MAP.get(row.verdict) || VERDICT_MAP.get('insufficient');
    const badge = window.TmallUI.badge(meta.label, meta.tone);
    badge.title = row.verdict_reason || meta.label;
    return badge;
  }

  // 单品表的全部候选列 = 接口 products[] 的字段；字段设置只切换显示，不改取数。
  const productColumns = [
    { key: 'title', label: '商品 / 上架日', className: 'pm-product-cell', render: (_value, row) => productIdentityCell(row) },
    {
      key: 'stage', label: '新老',
      render: (_value, row) => window.TmallUI.badge(STAGE_LABEL[row.stage] || '未匹配', row.stage === 'new' ? 'brand' : 'muted'),
    },
    { key: 'ad_spend', label: '花费', numeric: true, render: (value) => money(value) },
    { key: 'attributed_payment', label: '成交', numeric: true, render: (value) => money(value) },
    { key: 'roi', label: 'ROI', numeric: true, render: (value) => (value != null ? toneCell(roiTone(value), ratio(value)) : '--') },
    { key: 'expected_roi', label: '同渠道基准', numeric: true, render: (value) => ratio(value) },
    {
      key: 'roi_vs_baseline', label: '相对基准', numeric: true,
      render: (value, row) => (value != null
        ? toneCell(row.verdict === 'scale' ? 'success' : row.verdict === 'optimize' ? 'danger' : 'muted', `${Number(value).toFixed(2)}×`)
        : '--'),
    },
    { key: 'expense_ratio', label: '费比', numeric: true, render: (value) => (value != null ? percent(value) : '--') },
    { key: 'cart_cost', label: '加购成本', numeric: true, render: (value) => (value != null ? money(value) : '--') },
    { key: 'cpc', label: 'CPC', numeric: true, render: (value) => (value != null ? money(value) : '--') },
    { key: 'ctr', label: '点击率', numeric: true, render: (value) => (value != null ? percent(value) : '--') },
    { key: 'direct_payment', label: '直接成交', numeric: true, render: (value) => (value != null ? money(value) : '--') },
    { key: 'link_net_sales', label: '净销售额', numeric: true, render: (value) => (value != null ? money(value) : '--') },
    { key: 'cart_adds', label: '加购数', numeric: true, render: (value) => (value != null ? count(value) : '--') },
    { key: 'payment_buyers', label: '支付买家', numeric: true, render: (value) => (value != null ? count(value) : '--') },
    { key: 'new_buyers', label: '拉新买家', numeric: true, render: (value) => (value != null ? count(value) : '--') },
    { key: 'impressions', label: '展现量', numeric: true, render: (value) => (value != null ? count(value) : '--') },
    { key: 'clicks', label: '点击量', numeric: true, render: (value) => (value != null ? count(value) : '--') },
    { key: 'verdict', label: '结论', render: (_value, row) => verdictBadge(row) },
  ];

  const FIELD_STORAGE_KEY = 'tmall.promotion-matrix.columns.v1';
  const DEFAULT_FIELDS = ['title', 'stage', 'ad_spend', 'attributed_payment', 'roi', 'expected_roi', 'roi_vs_baseline', 'expense_ratio', 'cart_cost', 'verdict'];
  const FIELD_KEYS = productColumns.map((column) => column.key);
  const FIELD_LABEL = new Map(productColumns.map((column) => [column.key, column.label]));

  // 商品列固定第一列（它是行身份），其余字段顺序完全按用户拖动后的顺序。
  function normalizeFields(value) {
    if (!Array.isArray(value)) return [...DEFAULT_FIELDS];
    return ['title', ...[...new Set(value)].filter((key) => key !== 'title' && FIELD_KEYS.includes(key))];
  }

  function readFields() {
    try {
      const saved = localStorage.getItem(FIELD_STORAGE_KEY);
      return saved === null ? [...DEFAULT_FIELDS] : normalizeFields(JSON.parse(saved));
    } catch (_) {
      return [...DEFAULT_FIELDS];
    }
  }

  state.fields = readFields();

  function visibleColumns() {
    return state.fields.map((key) => productColumns.find((column) => column.key === key)).filter(Boolean);
  }

  // table-controls 排序读单元格文本，会把「¥1.3万」当成 1.3、把「1.3万」排到「¥1.35」后面。
  // 数字列统一补 data-sort-value（原始值），显示格式怎么变都不影响排序。
  const SORT_NUMERIC_KEYS = new Set([
    'ad_spend', 'attributed_payment', 'roi', 'expected_roi', 'roi_vs_baseline',
    'expense_ratio', 'cart_cost', 'cpc', 'ctr', 'direct_payment', 'link_net_sales',
    'cart_adds', 'payment_buyers', 'new_buyers', 'impressions', 'clicks',
  ]);

  function decorateSortValues(tableNode, rows, columns, valueOf = (row, column) => row?.[column.key], numericTest = (column) => SORT_NUMERIC_KEYS.has(column.key)) {
    const table = tableNode?.querySelector?.('table');
    if (!table) return tableNode;
    const numericIndexes = columns
      .map((column, index) => (numericTest(column) ? index : -1))
      .filter((index) => index >= 0);
    if (!numericIndexes.length) return tableNode;
    [...table.tBodies].forEach((body) => {
      [...body.rows].forEach((tr, rowIndex) => {
        const row = rows[rowIndex];
        if (!row) return;
        numericIndexes.forEach((cellIndex) => {
          const cell = tr.cells[cellIndex];
          const value = valueOf(row, columns[cellIndex]);
          if (cell && value != null && value !== '') cell.dataset.sortValue = String(value);
        });
      });
    });
    return tableNode;
  }

  function visibleProducts() {
    const rows = Array.isArray(state.data?.products) ? state.data.products : [];
    const keyword = state.search.trim().toLowerCase();
    return rows.filter((row) => {
      if (state.stage !== 'all' && row.stage !== state.stage) return false;
      if (state.verdict !== 'all' && row.verdict !== state.verdict) return false;
      if (!keyword) return true;
      return `${row.product_id || ''} ${row.title || ''}`.toLowerCase().includes(keyword);
    });
  }

  function renderProducts() {
    if (!els.productsHost || !window.TmallUI?.table) return;
    const rows = visibleProducts();
    // 分母跟着新老品筛选走：筛「新品」时显示 12 / 85，而不是 12 / 210。
    const stageAll = (state.data?.products || []).filter((row) => state.stage === 'all' || row.stage === state.stage).length;
    if (els.rowCount) els.rowCount.textContent = rows.length === stageAll ? `共 ${count(stageAll)} 个商品` : `${count(rows.length)} / ${count(stageAll)} 个商品`;
    els.productsHost.replaceChildren(decorateSortValues(window.TmallUI.table({
      caption: '单品效率结论',
      columns: visibleColumns(),
      rows,
      tableClass: 'pm-products-table',
      wrapClass: 'pm-products-scroll',
      rowClassName: (row) => `pm-row pm-row--${row.verdict}`,
      emptyMessage: state.data?.availability === 'available' ? '当前筛选条件下没有商品' : '当前范围没有可归因到商品的推广花费',
    }), rows, visibleColumns()));
  }

  function renderDisclosure(data) {
    const windowInfo = data.window || {};
    const rule = data.baseline_rule || {};
    const coverage = data.coverage || {};
    if (els.minSpend) els.minSpend.textContent = String(rule.min_spend ?? 100);
    if (els.minPayment) els.minPayment.textContent = String(rule.min_payment ?? 500);
    if (els.window) {
      els.window.textContent = windowInfo.new_cutoff
        ? `新品口径：${windowInfo.new_cutoff} ~ ${data.period?.end || '当前周期'} 上架（${windowInfo.window_days || 60} 天内），与新品看板一致。`
        : '';
    }
    if (els.coverage) {
      const items = [
        ['账单口径花费', money(coverage.bill_spend)],
        ['商品级已覆盖', money(coverage.covered_spend)],
        ['花费覆盖率', percent(coverage.spend_coverage, 1)],
        ['成交覆盖率', percent(coverage.payment_coverage, 1)],
        ['未归因差额', money(coverage.unattributed_spend)],
        ['有数据天数', `${count(coverage.sample_days)} 天`],
      ];
      els.coverage.replaceChildren(...items.map(([label, value]) => {
        const wrap = document.createElement('div');
        const dt = document.createElement('dt');
        dt.textContent = label;
        const dd = document.createElement('dd');
        dd.textContent = value;
        wrap.append(dt, dd);
        return wrap;
      }));
    }
    if (els.notes) {
      const limitations = Array.isArray(data.limitations) ? data.limitations : [];
      els.notes.replaceChildren(...limitations.map((text) => {
        const item = document.createElement('li');
        item.textContent = text;
        return item;
      }));
    }
  }

  function render(data) {
    state.data = data;
    renderSummary(data);
    renderBaselineNote(data);
    renderMatrix(data);
    renderStageFilter(data);
    renderVerdictFilter();
    renderProducts();
    renderDisclosure(data);
    window.lucide?.createIcons?.();
  }

  function renderFailure(message) {
    const state_ = window.TmallUI?.emptyState ? window.TmallUI.emptyState(message) : null;
    if (state_ && els.matrixHost) els.matrixHost.replaceChildren(state_.cloneNode(true));
    if (state_ && els.productsHost) els.productsHost.replaceChildren(state_);
    if (els.rowCount) els.rowCount.textContent = '加载失败';
  }

  async function load(detail) {
    const { start, end } = range(detail);
    try {
      const response = await window.DemoApi.domainRequest(`/api/promotion/matrix?${new URLSearchParams({ start, end })}`);
      render(response.data || {});
    } catch (error) {
      console.error('[tmall] promotion matrix unavailable', error);
      renderFailure(`投放矩阵加载失败：${error.message || '请稍后重试'}`);
    }
  }

  // 字段设置：弹窗 + 字段选择器，选择结果存 localStorage，只影响显示列。
  function bindFieldSettings() {
    const trigger = els.fieldTrigger;
    // DemoFieldSelector 由 field-selector.js 提供；脚本缺失时静默跳过，不影响表格渲染。
    if (!trigger || !window.TmallUI?.fieldSelector || !window.DemoFieldSelector) return;
    const selectorRoot = document.createElement('div');
    const fieldGroups = [
      ['商品与结论', ['title', 'stage', 'verdict']],
      ['投产效率', ['ad_spend', 'attributed_payment', 'roi', 'expected_roi', 'roi_vs_baseline', 'expense_ratio', 'cart_cost', 'cpc', 'ctr']],
      ['量级与人群', ['direct_payment', 'link_net_sales', 'cart_adds', 'payment_buyers', 'new_buyers', 'impressions', 'clicks']],
    ].map(([label, keys]) => ({
      label,
      fields: keys.map((key) => ({ key, label: FIELD_LABEL.get(key) || key, required: key === 'title' })),
    }));
    let draft = [...state.fields];
    const selector = window.TmallUI.fieldSelector({
      root: selectorRoot,
      groups: fieldGroups,
      selected: draft,
      optionDataAttribute: 'data-pm-field-key',
      previewDataAttribute: 'data-pm-field-preview',
      onChange: (next) => { draft = normalizeFields(next); },
    });
    const reset = window.TmallUI.button({ label: '恢复默认', variant: 'ghost' });
    const cancel = window.TmallUI.button({ label: '取消', variant: 'secondary' });
    const apply = window.TmallUI.button({ label: '应用', variant: 'primary' });
    const modal = window.TmallUI.modal({
      title: '单品表字段设置',
      description: '勾选字段并拖动或上移、下移调整顺序；商品信息固定首列。设置保存在当前浏览器，只改显示列，不改取数口径。来源没回传的指标（如部分渠道的加购、买家、直接成交）显示 --，不补零估算。',
      body: selectorRoot,
      footer: [reset, cancel, apply],
      size: 'lg',
    });
    modal.node.classList.add('ui-field-selector-dialog', 'pm-fields-dialog');
    trigger.addEventListener('click', () => {
      draft = [...state.fields];
      selector.setSelected(draft);
      modal.open();
    });
    reset.addEventListener('click', () => {
      draft = [...DEFAULT_FIELDS];
      selector.setSelected(draft);
    });
    cancel.addEventListener('click', () => modal.close());
    apply.addEventListener('click', () => {
      state.fields = normalizeFields(draft);
      try {
        localStorage.setItem(FIELD_STORAGE_KEY, JSON.stringify(state.fields));
      } catch (_) {
        // 浏览器存储不可用时本次仍生效，刷新后回到默认列。
      }
      renderProducts();
      modal.close();
    });
  }

  function bindFilters() {
    els.stageFilter?.addEventListener('click', (event) => {
      const button = event.target.closest('button');
      if (!button) return;
      const entry = [...els.stageButtons.entries()].find(([, node]) => node === button);
      if (!entry) return;
      state.stage = entry[0];
      els.stageButtons.forEach((node, key) => node.setAttribute('aria-pressed', String(key === state.stage)));
      renderVerdictFilter();
      renderProducts();
    });
    els.filter?.addEventListener('click', (event) => {
      const button = event.target.closest('button');
      if (!button) return;
      const entry = [...els.filterButtons.entries()].find(([, node]) => node === button);
      if (!entry) return;
      state.verdict = entry[0];
      els.filterButtons.forEach((node, key) => node.setAttribute('aria-pressed', String(key === state.verdict)));
      renderProducts();
    });
    els.search?.addEventListener('input', (event) => {
      state.search = event.target.value || '';
      renderProducts();
    });
  }

  // shell 的日期控件挂载时会先给默认区间、再恢复 URL/localStorage 区间，
  // 两次都会触发事件。这里合并成一次请求：后到的区间直接顶掉待发的区间，
  // 避免同一页面连续打两次矩阵接口、把筛选条渲染两遍。
  let pendingRange = null;
  let loadTimer = 0;

  function scheduleLoad(detail) {
    pendingRange = detail;
    if (loadTimer) clearTimeout(loadTimer);
    loadTimer = setTimeout(() => {
      loadTimer = 0;
      load(pendingRange);
    }, 150);
  }

  function boot(detail) {
    if (!state.booted) {
      if (!buildPage()) return;
      bindFilters();
      bindFieldSettings();
      state.booted = true;
    }
    scheduleLoad(detail);
  }

  // 日期范围由 shell 的全局控件驱动：按当前区间渲染一次，之后跟着变化重载。
  window.addEventListener('tmall:date-range-change', (event) => boot(event.detail));
  window.addEventListener('tmall:refresh', () => boot(window.TmallDateRange?.getState?.()));
  boot(window.TmallDateRange?.getState?.());
})();
