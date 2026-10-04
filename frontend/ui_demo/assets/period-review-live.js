(function () {
  'use strict';

  const PERIOD_TYPES = ['day', 'week', 'month'];
  // 兼容旧模板：复盘控件已由 shell 注入顶部筛选栏，移除页面内残留节点。
  document.querySelector('.pr-control-strip')?.remove();

  const reviewControlRoot = document.querySelector('[data-shell-header]') || document;
  const els = {
    modeButtons: Array.from(reviewControlRoot.querySelectorAll('[data-pr-mode]')),
    period: reviewControlRoot.querySelector('[data-pr-period]'),
    periodLabel: reviewControlRoot.querySelector('[data-pr-period-label]'),
    rangeHint: document.querySelector('[data-pr-range-hint]'),
    target: document.querySelector('[data-pr-target]'),
    targetProfit: document.querySelector('[data-pr-target-profit]'),
    targetAdSpend: document.querySelector('[data-pr-target-ad-spend]'),
    targetNetExpenseRatio: document.querySelector('[data-pr-target-net-expense-ratio]'),
    reviewer: document.querySelector('[data-pr-reviewer]'),
    statusSelect: document.querySelector('[data-pr-status]'),
    statusText: document.querySelector('[data-pr-status-text]'),
    category: document.querySelector('[data-pr-category]') || document.querySelector('[data-category-mode]'),
    categoryNote: document.querySelector('[data-pr-category-note]'),
    compare: reviewControlRoot.querySelector('[data-pr-compare]'),
    comparePeriod: reviewControlRoot.querySelector('[data-pr-compare-period]'),
    comparePeriodField: reviewControlRoot.querySelector('[data-pr-compare-period-field]'),
    state: document.querySelector('[data-pr-state]'),
    actionSummary: document.querySelector('[data-pr-action-summary]'),
    draftMeta: document.querySelector('[data-pr-draft-meta]'),
    generateDraft: document.querySelector('[data-pr-generate-draft]'),
    sectionNav: document.querySelector('[data-pr-section-nav]'),
    sections: document.querySelector('[data-pr-sections]'),
    commandCenter: document.querySelector('[data-pr-command-center]'),
    settingsSummary: document.querySelector('[data-pr-settings-summary]'),
    settingsOpen: document.querySelector('[data-pr-settings-open]'),
    settingsDialog: document.querySelector('[data-pr-settings-dialog]'),
    settingsClose: document.querySelector('[data-pr-settings-close]'),
    settingsCancel: document.querySelector('[data-pr-settings-cancel]'),
    settingsApply: document.querySelector('[data-pr-settings-apply]'),
    executionAnalysis: document.querySelector('[data-pr-execution-analysis]'),
    matrix: document.querySelector('[data-pr-matrix]'),
    categoryBreakdown: document.querySelector('[data-pr-category-breakdown]'),
    history: document.querySelector('[data-pr-history]'),
    save: document.querySelector('[data-pr-save]'),
    refresh: document.querySelector('[data-pr-refresh]'),
    export: document.querySelector('[data-pr-export]'),
  };

  const urlParams = new URLSearchParams(window.location.search);
  const state = {
    mode: PERIOD_TYPES.includes(urlParams.get('period_type')) ? urlParams.get('period_type') : 'week',
    // 当 URL 同时给出 start/end 时，以显式日期范围为权威；period_key 仅作展示/历史复盘入口，避免两套口径不一致。
    selectedPeriodKey: (urlParams.has('start') && urlParams.has('end')) ? '' : (urlParams.get('period_key') || ''),
    periodOptions: { day: [], week: [], month: [] },
    template: [], templates: {}, categories: [], context: null, review: null, matrix: null,
    generatedDraft: null,
    matrixError: null, categoryBreakdown: null, categoryError: null, leafBoard: null, leafBoardError: null,
  };
  let syncingReviewRange = false;
  let loadToken = 0;
  let saving = false;
  let actionSaving = false;
  let actionDialog = null;
  let actionReviewDialog = null;
  let actionDetailDialog = null;
  let settingsSnapshot = null;
  let settingsApplied = false;

  // 品类口径与全站统一：读写同一个 localStorage key，顶栏「品类模式」下拉与本页选择器互为镜像。
  const CATEGORY_KEY = 'dashboard.categoryMode';
  const CATEGORY_FALLBACK = 'sock';

  function readCategoryMode() {
    try {
      const stored = localStorage.getItem(CATEGORY_KEY);
      if (stored) return stored;
    } catch (_) { /* localStorage 不可用时退回默认品类 */ }
    return CATEGORY_FALLBACK;
  }

  function storeCategoryMode(value) {
    try { localStorage.setItem(CATEGORY_KEY, value); } catch (_) { /* 忽略写入失败 */ }
  }

  function syncTopbarCategory(value) {
    const topbar = document.querySelector('[data-category-mode]');
    if (topbar && topbar.value !== value) topbar.value = value;
  }

  function categoryLabelOf() {
    return (state.context && state.context.category && state.context.category.label) || null;
  }

  // ------------------------------------------------------ 对比周期（可自选）
  const COMPARE_KEY = 'dashboard.periodReviewCompare';
  const COMPARE_MODES = ['previous', 'yoy', 'custom', 'none'];
  let compareChoiceOverride = null;

  function readCompareChoice() {
    if (compareChoiceOverride) return compareChoiceOverride;
    const urlMode = new URLSearchParams(window.location.search).get('compare');
    // URL 明确指定对比口径时优先，保证分享/回放出来的页面和原页面同一基线；
    // 用户在页内再选择时仍会写入 localStorage，后续普通访问沿用最近偏好。
    if (COMPARE_MODES.includes(urlMode)) {
      const period = urlMode === 'custom' ? urlParams.get('compare_period') || '' : '';
      return { mode: urlMode, period, source: 'url' };
    }
    let stored = null;
    try { stored = JSON.parse(localStorage.getItem(COMPARE_KEY) || 'null'); } catch (_) { stored = null; }
    const mode = stored && COMPARE_MODES.includes(stored.mode) ? stored.mode : 'previous';
    return { mode, period: (stored && stored.period) || '', source: 'stored' };
  }

  function storeCompareChoice(choice) {
    try { localStorage.setItem(COMPARE_KEY, JSON.stringify(choice)); } catch (_) { /* 忽略写入失败 */ }
  }

  // 自定义对比周期必须与当前周期类型一致（周键不能用于月复盘），否则请求会被拒。
  function comparePeriodMatchesMode(period) {
    if (!period) return false;
    if (state.mode === 'week') return /^(?:\d{4}-\d{2}-W\d|\d{4}-W\d{2})$/.test(period);
    if (state.mode === 'month') return /^\d{4}-\d{2}$/.test(period);
    return /^\d{4}-\d{2}-\d{2}$/.test(period);
  }

  function compareQuery() {
    const choice = readCompareChoice();
    const mode = choice.mode;
    const period = choice.period;
    if (mode === 'custom' && comparePeriodMatchesMode(period)) {
      return `?compare=custom&compare_period=${encodeURIComponent(period)}`;
    }
    // 自定义但周期缺失/类型不符时退回环比，避免发出不合法请求。
    const fallbackMode = mode === 'custom' ? 'previous' : mode;
    return `?compare=${encodeURIComponent(fallbackMode)}`;
  }

  function compareShortLabel() {
    const compare = state.context && state.context.compare;
    return (compare && compare.short_label) || '';
  }

  // ------------------------------------------------------------------ utils
  function h(tag, attrs, ...children) {
    const node = document.createElement(tag);
    if (attrs) {
      Object.entries(attrs).forEach(([key, value]) => {
        if (value === null || value === undefined || value === false) return;
        if (key === 'class') node.className = value;
        else if (key === 'text') node.textContent = value;
        else if (key.startsWith('on') && typeof value === 'function') node.addEventListener(key.slice(2).toLowerCase(), value);
        else node.setAttribute(key, value);
      });
    }
    children.flat().forEach((child) => {
      if (child === null || child === undefined || child === false) return;
      node.append(child instanceof Node ? child : document.createTextNode(String(child)));
    });
    return node;
  }

  const pad2 = (value) => String(value).padStart(2, '0');

  // 点击遮罩关闭统一走公共实现（ui-components.js）：先派发 cancel 让弹窗既有的
  // 取消逻辑接管（如复盘设置回滚草稿），无人处理时再兜底 close()；
  // 并打上标记，避免文档级委托重复处理。
  const enableLightDismiss = (dialog) => window.TmallUI?.enableLightDismiss?.(dialog);

  const isoDate = (date) => `${date.getFullYear()}-${pad2(date.getMonth() + 1)}-${pad2(date.getDate())}`;

  function todayIso() {
    const now = new Date();
    return isoDate(new Date(now.getFullYear(), now.getMonth(), now.getDate()));
  }

  // 复盘周期不再由页内输入框决定，而是跟随顶栏统一时间范围推导，
  // 因此页面与全站共用同一个时间选择器，不再出现两套不一致的控件。
  function sharedRange() {
    const shared = window.TmallDateRange && window.TmallDateRange.getState
      ? window.TmallDateRange.getState()
      : null;
    if (shared && shared.startDate && shared.endDate) return shared;
    const fallback = todayIso();
    return { startDate: fallback, endDate: fallback, preset: 'custom' };
  }

  // 月内分周：返回 YYYY-MM-WN 格式的周期键。
  // 规则与后端 _month_bounded_weeks 一致：
  // W1 从 1 号到第一个周日，中间周周一到周日，最后一周到月末。
  function monthWeekKey(dateString) {
    const base = new Date(`${dateString}T00:00:00`);
    const year = base.getFullYear();
    const month = base.getMonth() + 1;
    const lastDay = new Date(year, month, 0).getDate();
    const weeks = [];
    // W1：1 号到第一个周日
    const firstDay = new Date(year, month - 1, 1);
    const firstSunday = new Date(firstDay);
    firstSunday.setDate(1 + ((7 - firstDay.getDay()) % 7));
    let wk1End = firstSunday.getDate();
    if (wk1End > lastDay) wk1End = lastDay;
    weeks.push({ num: 1, start: 1, end: wk1End });
    // 中间周和最后一周
    let cur = wk1End + 1;
    while (cur <= lastDay) {
      const wStart = cur;
      let wEnd = cur + 6;
      if (wEnd > lastDay) wEnd = lastDay;
      weeks.push({ num: weeks.length + 1, start: wStart, end: wEnd });
      cur = wEnd + 1;
    }
    // 找到 dateString 落在第几周
    const day = base.getDate();
    for (const w of weeks) {
      if (day >= w.start && day <= w.end) {
        return `${year}-${pad2(month)}-W${w.num}`;
      }
    }
    return `${year}-${pad2(month)}-W1`;
  }

  /** 顶栏范围的结束日期落在哪个周 / 月，就用哪个周期。 */
  function periodKeyFromRange() {
    const end = sharedRange().endDate || todayIso();
    if (state.mode === 'day') return end;
    return state.mode === 'week' ? monthWeekKey(end) : end.slice(0, 7);
  }

  function currentPeriod() {
    return state.selectedPeriodKey || periodKeyFromRange();
  }

  function renderPeriodLabel(period) {
    if (els.periodLabel) {
      els.periodLabel.textContent = period ? period.label : '—';
    }
    if (!els.rangeHint) return;
    const range = sharedRange();
    const scope = state.mode === 'day'
      ? '按结束日期识别自然日'
      : (state.mode === 'week' ? '按结束日期识别所在月内周（周不跨月）' : '按结束日期识别所在自然月');
    els.rangeHint.textContent = `顶栏时间范围 ${range.startDate} ~ ${range.endDate} · ${scope}；要换周期请在顶栏「统计时间」选择对应日期 / 周期或自定义。`;
  }

  async function loadPeriodOptions() {
    const response = await DemoApi.domainRequest(
      `/api/period-reviews/period-options?period_type=${state.mode}&limit=240`,
    );
    state.periodOptions[state.mode] = response.data?.options || [];
  }

  function updateReviewUrl() {
    const url = new URL(window.location.href);
    url.searchParams.set('period_type', state.mode);
    url.searchParams.set('period_key', currentPeriod());
    const compare = new URLSearchParams(compareQuery());
    url.searchParams.set('compare', compare.get('compare'));
    const comparePeriod = compare.get('compare_period');
    if (comparePeriod) url.searchParams.set('compare_period', comparePeriod);
    else url.searchParams.delete('compare_period');
    history.replaceState(null, '', url);
  }

  function renderPeriodPicker() {
    if (!els.period) return;
    const options = state.periodOptions[state.mode] || [];
    els.period.replaceChildren(...options.map((item) => h('option', {
      value: item.key,
      text: item.label,
    })));
    if (!options.length) {
      els.period.append(h('option', { value: '', text: '暂无可用周期' }));
      els.period.disabled = true;
      return;
    }
    els.period.disabled = false;
    const currentKey = currentPeriod();
    if (!options.some((item) => item.key === currentKey) && state.context?.period) {
      options.unshift({
        key: state.context.period.key,
        label: state.context.period.label,
        start: state.context.period.start,
        end: state.context.period.end,
      });
      els.period.replaceChildren(...options.map((item) => h('option', {
        value: item.key,
        text: item.label,
      })));
    }
    els.period.value = currentKey;
  }

  function syncRangeToSelectedPeriod() {
    const selected = (state.periodOptions[state.mode] || [])
      .find((item) => item.key === state.selectedPeriodKey);
    if (!selected || !window.TmallDateRange?.setReviewRange) return;
    const range = sharedRange();
    if (range.startDate === selected.start && range.endDate === selected.end) return;
    syncingReviewRange = true;
    window.TmallDateRange.setReviewRange(selected.start, selected.end);
    syncingReviewRange = false;
  }

  function formatValue(value, format) {
    if (value === null || value === undefined || Number.isNaN(Number(value))) return '--';
    const num = Number(value);
    if (format === 'money') {
      // 负数金额写成 -¥1,638.34，比 ¥-1,638.34 更符合财务读法。
      const text = Math.abs(num).toLocaleString('zh-CN', { maximumFractionDigits: 2 });
      return `${num < 0 ? '-' : ''}¥${text}`;
    }
    if (format === 'percent') return `${(num * 100).toFixed(2)}%`;
    if (format === 'decimal') return num.toFixed(2);
    return num.toLocaleString('zh-CN', { maximumFractionDigits: 2 });
  }

  function formatCompact(value) {
    if (value === null || value === undefined) return '--';
    const num = Number(value);
    if (Math.abs(num) >= 10000) return `${(num / 10000).toFixed(1)}万`;
    return num.toLocaleString('zh-CN', { maximumFractionDigits: 0 });
  }

  function missingText(value, reason = '暂无数据') {
    return value === null || value === undefined || Number.isNaN(Number(value)) ? reason : null;
  }

  function safeMetric(value, format = 'decimal', reason = '暂无数据') {
    const missing = missingText(value, reason);
    return missing || formatValue(value, format);
  }

  function productShare(row) {
    const total = Number(state.context?.metrics?.current?.gsv);
    if (!Number.isFinite(total) || total <= 0 || row.gsv === null || row.gsv === undefined) return null;
    return Number(row.gsv) / total;
  }

  function actionMetricFormat(metric) {
    if (metric === 'payment_amount' || metric === 'aov') return 'money';
    if (metric === 'conversion' || metric === 'refund_rate') return 'percent';
    if (metric === 'visitors') return 'number';
    return 'decimal';
  }

  function declineRate(row) {
    if (row.delta === null || row.delta === undefined || row.prev_gsv === null || row.prev_gsv === undefined || !Number(row.prev_gsv)) return null;
    return Number(row.delta) / Number(row.prev_gsv);
  }

  function actionField(label, name, type = 'text', value = '', required = false) {
    const input = h(type === 'textarea' ? 'textarea' : 'input', {
      name, required, placeholder: required ? '必填' : '可选',
      ...(type !== 'textarea' ? { type, value } : {}),
    });
    if (type === 'textarea') input.value = value;
    return h('label', { class: 'pr-action-field' }, h('span', { text: `${label}${required ? ' *' : ''}` }), input);
  }

  function actionSelect(label, name, value, options, required = false) {
    const select = h('select', { name, required }, ...options.map(([optionValue, optionLabel]) =>
      h('option', { value: optionValue, text: optionLabel }),
    ));
    select.value = value;
    return h('label', { class: 'pr-action-field' }, h('span', { text: `${label}${required ? ' *' : ''}` }), select);
  }

  function diagnosisProductOptions() {
    const products = state.context?.products || {};
    const buckets = Object.values(products).flatMap((value) => {
      if (Array.isArray(value)) return value;
      if (Array.isArray(value?.items)) return value.items;
      return [];
    });
    const seen = new Set();
    return buckets.reduce((options, item) => {
      const productId = String(item?.product_id || '').trim();
      if (!productId || seen.has(productId)) return options;
      seen.add(productId);
      options.push([productId, `${item.title || productId} · ${productId}`]);
      return options;
    }, []);
  }

  function openProductDiagnosis(row, withDelta, diagnosisSource = null) {
    if (!actionDialog) {
      actionDialog = h('dialog', { class: 'pr-action-dialog' });
      document.body.append(actionDialog);
      enableLightDismiss(actionDialog);
    }
    const share = productShare(row);
    const rate = withDelta ? declineRate(row) : null;
    const tags = [];
    if (withDelta) tags.push('下滑商品');
    else tags.push('销售 TOP');
    if (row.tags) tags.push(...String(row.tags).split(',').map((item) => item.trim()).filter(Boolean));
    if (withDelta && rate === null) tags.push('对比数据不足');
    const metricPair = (label, current, previous, format = 'decimal') => h('div', null,
      h('span', { text: label }),
      h('strong', { text: safeMetric(current, format, '\u4e0d\u53ef\u5224\u65ad') }),
      previous !== null && previous !== undefined
        ? h('small', { text: `\u5bf9\u6bd4 ${safeMetric(previous, format, '\u4e0d\u53ef\u5224\u65ad')}` })
        : null,
    );
    (row.anomaly_tags || []).forEach((tag) => {
      if (!tags.includes(tag)) tags.push(tag);
    });
    const facts = h('div', { class: 'pr-diagnostic-facts' },
      h('div', null, h('span', { text: '本期销售额' }), h('strong', { text: safeMetric(row.gsv, 'money') })),
      h('div', null, h('span', { text: '销售额占比' }), h('strong', { text: share === null ? '不可判断' : `${(share * 100).toFixed(2)}%` })),
      h('div', null, h('span', { text: '净销售额' }), h('strong', { text: safeMetric(row.net_sales, 'money') })),
      withDelta ? h('div', null, h('span', { text: '上期销售额' }), h('strong', { text: safeMetric(row.prev_gsv, 'money') })) : null,
      withDelta ? h('div', null, h('span', { text: '变化金额' }), h('strong', { text: safeMetric(row.delta, 'money', '不可判断') })) : null,
      withDelta ? h('div', null, h('span', { text: '变化比例' }), h('strong', { text: rate === null ? '不可判断' : `${(rate * 100).toFixed(2)}%` })) : null,
    );
    facts.append(
      metricPair('\u8bbf\u5ba2\u6570', row.visitors, row.prev_visitors, 'number'),
      metricPair('\u652f\u4ed8\u8f6c\u5316\u7387', row.conversion, row.prev_conversion, 'percent'),
      metricPair('\u5ba2\u5355\u4ef7', row.aov, row.prev_aov, 'money'),
      metricPair('\u63a8\u5e7f\u82b1\u8d39', row.ad_spend, row.prev_ad_spend, 'money'),
      metricPair('\u9000\u6b3e\u7387', row.refund_rate, row.prev_refund_rate, 'percent'),
    );
    const evidence = h('ul', { class: 'pr-diagnostic-evidence' },
      h('li', { text: withDelta
        ? `系统依据：本期销售额 ${safeMetric(row.gsv, 'money')}，上期销售额 ${safeMetric(row.prev_gsv, 'money', '不可判断')}，变化比例 ${rate === null ? '不可判断' : `${(rate * 100).toFixed(2)}%`}`
        : `系统依据：本期销售额 ${safeMetric(row.gsv, 'money')}，在当前返回的销售 TOP 列表中排名靠前` }),
      h('li', { text: '当前上下文未提供完整的访客、转化、客单价拆解，系统不直接推断具体原因。' }),
    );
    const evidenceItems = evidence.querySelectorAll('li');
    if (evidenceItems[1]) {
      evidenceItems[1].textContent = '\u5df2\u5c55\u793a\u5ba2\u6237\u3001\u8f6c\u5316\u3001\u5ba2\u5355\u3001\u6295\u653e\u4e0e\u9000\u6b3e\u5b57\u6bb5\uff1b\u5177\u4f53\u539f\u56e0\u4ecd\u9700\u7ed3\u5408\u4e1a\u52a1\u786e\u8ba4\u3002';
    }
    const diagnosticList = (title, values, emptyText) => h('div', { class: 'pr-diagnostic-block' },
      h('h4', { text: title }),
      h('ul', { class: 'pr-diagnostic-evidence' },
        ...(values && values.length
          ? values.map((value) => h('li', { text: String(value) }))
          : [h('li', { text: emptyText })]),
      ),
    );
    const systemFacts = diagnosticList('事实证据', row.system_facts || [], '当前没有可展示的事实快照。');
    const unknownFacts = diagnosticList('待补充数据', row.unknowns || [], '当前没有待补充数据。');
    const form = h('form', { class: 'pr-action-form' });
    const productId = row.product_id || '';
    const productOptions = diagnosisProductOptions();
    form.append(
      !productId ? actionSelect('关联商品', 'product_id', '', [['', '请选择真实商品'], ...productOptions], true) : null,
      !productId ? h('p', { class: 'pr-action-form__hint', text: productOptions.length ? '拆因线索是流量/付费层级事实，请选择要落地的真实商品；系统不会自动虚构商品 ID。' : '当前没有可选商品，暂不能创建商品级动作。' }) : null,
      actionField('动作目的', 'purpose_note', 'textarea', diagnosisSource?.clue || (withDelta ? `${row.title || row.product_id} 销售额下滑，需制定恢复动作` : `${row.title || row.product_id} 销售贡献跟进`), true),
      actionField('动作类型', 'action_type', 'text', withDelta ? '排查并改善商品表现' : '维护销售表现', true),
      actionField('动作详情', 'action_detail', 'textarea', '', true),
      h('div', { class: 'pr-action-form__grid' },
        actionSelect('\u76ee\u6807\u6307\u6807', 'target_metric', 'payment_amount', [
          ['payment_amount', '\u652f\u4ed8\u91d1\u989d'], ['visitors', '\u8bbf\u5ba2\u6570'], ['conversion', '\u8f6c\u5316\u7387'],
          ['aov', '\u5ba2\u5355\u4ef7'], ['ad_roi', '\u6295\u653e ROI'], ['refund_rate', '\u9000\u6b3e\u7387'],
        ], true),
        actionField('\u76ee\u6807\u503c', 'target_value', 'number', ''),
        actionField('\u9884\u671f\u53d8\u5316', 'expected_change', 'number', ''),
        actionField('\u9a8c\u6536\u6807\u51c6', 'acceptance_criteria', 'textarea', ''),
        // 计划信息必须由执行人确认，不能用今天/默认负责人伪造已确定的排期。
        actionField('计划日期', 'planned_at', 'date', '', true),
        actionField('观察天数', 'observer_window_days', 'number', '', true),
        actionField('负责人', 'assigned_to', 'text', ''),
      ),
      h('p', { class: 'pr-action-form__status', 'data-pr-action-status': '' }),
      h('div', { class: 'pr-action-dialog__actions' },
        h('button', { type: 'button', class: 'ui-button', onclick: () => actionDialog.close(), text: '取消' }),
        h('button', { type: 'submit', class: 'ui-button ui-button--primary', text: '创建运营动作' }),
      ),
    );
    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      if (actionSaving) return;
      const data = new FormData(form);
      const payload = {
        capability_key: 'overview.create_action',
        product_id: String(data.get('product_id') || row.product_id || '').trim(),
        purpose_type: 'increase_sales',
        purpose_note: String(data.get('purpose_note') || '').trim(),
        action_type: String(data.get('action_type') || '').trim(),
        action_detail: String(data.get('action_detail') || '').trim(),
        target_metric: String(data.get('target_metric') || 'payment_amount').trim(),
        target_value: data.get('target_value') === '' ? null : Number(data.get('target_value')),
        expected_change: data.get('expected_change') === '' ? null : Number(data.get('expected_change')),
        acceptance_criteria: String(data.get('acceptance_criteria') || '').trim() || null,
        planned_at: data.get('planned_at'),
        observer_window_days: Number(data.get('observer_window_days')),
        assigned_to: String(data.get('assigned_to') || '').trim() || null,
        source_period: state.context?.period?.key || currentPeriod(),
        source_category_mode: readCategoryMode(),
        source_period_type: state.mode,
        source_period_key: state.context?.period?.key || currentPeriod(),
        source_compare_mode: state.context?.compare?.mode || 'previous',
        source_compare_period_key: state.context?.compare?.period_key || null,
        ...(String(data.get('product_id') || row.product_id || '').trim() ? { source_product_id: String(data.get('product_id') || row.product_id || '').trim() } : {}),
        source_problem_key: diagnosisSource?.problemKey || (row.anomaly_tags || [])[0] || (withDelta ? 'product_decline' : 'product_top_sales'),
        source_diagnosis_snapshot: JSON.stringify({
          ...(diagnosisSource || {}),
          gsv: row.gsv,
          prev_gsv: row.prev_gsv,
          delta: row.delta,
          change_rate: row.change_rate,
          anomaly_tags: row.anomaly_tags || [],
          unknowns: row.unknowns || [],
        }),
      };
      const status = form.querySelector('[data-pr-action-status]');
      actionSaving = true;
      form.querySelector('button[type="submit"]').disabled = true;
      if (status) status.textContent = '创建中…';
      try {
        await DemoApi.domainRequest('/api/actions', {
          method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
        });
        actionDialog.close();
        await load();
        stateBanner('运营动作已创建，当前复盘上下文已刷新。', '');
      } catch (error) {
        if (status) status.textContent = error.message || '创建失败，请检查必填项后重试。';
      } finally {
        actionSaving = false;
        const submit = form.querySelector('button[type="submit"]');
        if (submit) submit.disabled = false;
      }
    });
    actionDialog.replaceChildren(
      h('div', { class: 'pr-action-dialog__head' }, h('div', null, h('span', { class: 'section-kicker', text: '商品诊断' }), h('h3', { text: row.title || row.product_id }), h('p', { text: `商品 ID：${row.product_id}` })), h('button', { type: 'button', class: 'pr-dialog-close', 'aria-label': '关闭', onclick: () => actionDialog.close(), text: '×' })),
      h('div', { class: 'pr-chip-row' }, ...tags.map((tag) => h('span', { class: 'pr-chip is-warning', text: tag }))),
      facts,
      systemFacts,
      unknownFacts,
      h('div', { class: 'pr-diagnostic-block' }, h('h4', { text: '系统判断依据' }), evidence),
      h('div', { class: 'pr-diagnostic-block' }, h('h4', { text: '创建运营动作' }), form),
    );
    if (!actionDialog.open) actionDialog.showModal();
  }

  // 拆因线索复用同一套动作表单：不伪造商品 ID，保留负责人/目标/计划日期等现有校验。
  function openDiagnosisAction(diagnosisSource) {
    const source = diagnosisSource || {};
    openProductDiagnosis({
      title: '拆因线索动作',
      product_id: source.product_id || null,
      gsv: null, prev_gsv: null, delta: null, change_rate: null,
      anomaly_tags: [], unknowns: [], system_facts: [source.clue || '未命名拆因线索'],
    }, false, source);
  }
  window.periodReviewOpenActionFromDiagnosis = openDiagnosisAction;

  function deltaNode(item) {
    const wrap = h('div', { class: 'pr-kpi__delta' });
    const compare = (state.context && state.context.compare) || { mode: 'previous', short_label: '环比' };
    const build = (label, change, comparable) => {
      // 基线不可比（后端 comparability.comparable=false）时显示「不可比」，
      // 而不是把窗口错配的极端百分比（如 4 天 vs 整月 → -98%）当事实展示。
      if (comparable === false) {
        return h('span', { class: 'pr-delta pr-delta--na', text: `${label} 不可比` });
      }
      if (change === null || change === undefined) return null;
      const good = MetricPolarity.isGood(item.key, change, { lowerBetter: item.lower_better });
      const cls = good === null ? 'pr-delta' : `pr-delta ${good ? 'is-up' : 'is-down'}`;
      return h('span', { class: cls, text: `${label} ${change > 0 ? '+' : ''}${change}%` });
    };
    const nodes = [];
    if (compare.mode !== 'none') {
      const baseline = build(compare.short_label || '环比', item.mom_change, item.mom_comparable);
      if (baseline) nodes.push(baseline);
    }
    // 对比基线本身就是同比时不再重复一行
    if (compare.mode !== 'yoy') {
      const yoy = build('同比', item.yoy_change, item.yoy_comparable);
      if (yoy) nodes.push(yoy);
    }
    wrap.append(...nodes);
    if (!nodes.length) {
      wrap.append(h('span', {
        class: 'pr-delta',
        text: compare.mode === 'none' ? '未开启对比' : '对比周期在该口径下无数据',
      }));
    }
    return wrap;
  }

  function updateSettingsSummary() {
    if (!els.settingsSummary) return;
    const targetInputs = [els.target, els.targetProfit, els.targetAdSpend, els.targetNetExpenseRatio];
    const targetCount = targetInputs.filter((input) => input && String(input.value).trim() !== '').length;
    const reviewer = els.reviewer && els.reviewer.value.trim();
    const status = els.statusSelect && els.statusSelect.value === 'final' ? '已定稿' : '草稿';
    els.settingsSummary.textContent = `${targetCount}/4 项目标 · ${reviewer || '运营人员'} · ${status}`;
  }

  function settingsValues() {
    return {
      target: els.target ? els.target.value : '',
      targetProfit: els.targetProfit ? els.targetProfit.value : '',
      targetAdSpend: els.targetAdSpend ? els.targetAdSpend.value : '',
      targetNetExpenseRatio: els.targetNetExpenseRatio ? els.targetNetExpenseRatio.value : '',
      reviewer: els.reviewer ? els.reviewer.value : '',
      status: els.statusSelect ? els.statusSelect.value : 'draft',
      targetPath: state.context && state.context.target_path
        ? JSON.parse(JSON.stringify(state.context.target_path)) : null,
    };
  }

  function restoreSettingsValues(values) {
    if (!values) return;
    if (els.target) els.target.value = values.target;
    if (els.targetProfit) els.targetProfit.value = values.targetProfit;
    if (els.targetAdSpend) els.targetAdSpend.value = values.targetAdSpend;
    if (els.targetNetExpenseRatio) els.targetNetExpenseRatio.value = values.targetNetExpenseRatio;
    if (els.reviewer) els.reviewer.value = values.reviewer;
    if (els.statusSelect) els.statusSelect.value = values.status;
    if (state.context && values.targetPath) state.context.target_path = values.targetPath;
    updateSettingsSummary();
    if (state.context) renderCommandCenter(state.context);
  }

  function validateSettings() {
    const ratio = els.targetNetExpenseRatio && String(els.targetNetExpenseRatio.value).trim();
    if (ratio !== '') {
      const value = Number(ratio);
      if (!Number.isFinite(value) || value < 0 || value > 100) {
        return '净费比目标请按 0–100 的百分数填写，例如 23.70 表示 23.70%。';
      }
    }
    return '';
  }

  function closeSettingsDialog(restore = false) {
    if (restore) restoreSettingsValues(settingsSnapshot);
    settingsSnapshot = null;
    settingsApplied = false;
    if (els.settingsDialog?.open) els.settingsDialog.close();
  }

  function openSettingsDialog() {
    settingsSnapshot = settingsValues();
    settingsApplied = false;
    if (els.settingsDialog && !els.settingsDialog.open) els.settingsDialog.showModal();
  }

  function applySettingsDialog() {
    const error = validateSettings();
    if (error) {
      stateBanner(error, 'insufficient-data');
      els.targetNetExpenseRatio?.focus();
      return;
    }
    settingsApplied = true;
    updateSettingsSummary();
    if (state.context) {
      targetCards.refreshTargetCard();
      renderCommandCenter(state.context);
    }
    closeSettingsDialog();
  }

  function bindSettingsDialog() {
    // 与页内其它弹窗保持一致：点击遮罩（backdrop）关闭复盘设置。
    // close 事件里会把未应用的改动回滚，等价于「取消」，不会丢已保存内容。
    enableLightDismiss(els.settingsDialog);
    els.settingsOpen?.addEventListener('click', openSettingsDialog);
    els.settingsClose?.addEventListener('click', () => closeSettingsDialog(true));
    els.settingsCancel?.addEventListener('click', () => closeSettingsDialog(true));
    els.settingsApply?.addEventListener('click', applySettingsDialog);
    els.settingsDialog?.addEventListener('cancel', (event) => {
      event.preventDefault();
      closeSettingsDialog(true);
    });
    els.settingsDialog?.addEventListener('close', () => {
      if (!settingsApplied && settingsSnapshot) restoreSettingsValues(settingsSnapshot);
      settingsSnapshot = null;
      settingsApplied = false;
    });
    [els.target, els.targetProfit, els.targetAdSpend, els.targetNetExpenseRatio, els.reviewer, els.statusSelect]
      .forEach((input) => input?.addEventListener('input', updateSettingsSummary));
    els.statusSelect?.addEventListener('change', updateSettingsSummary);
    updateSettingsSummary();
  }

  function stateBanner(text, kind) {
    if (!els.state) return;
    els.state.dataset.state = kind || '';
    els.state.textContent = text || '';
  }

  function coverageNotice(context) {
    const coverage = context?.metrics?.coverage;
    if (!coverage || coverage.status !== 'partial') return '';
    const observed = Number(coverage.observed_days || 0);
    const expected = Number(coverage.expected_days || 0);
    const latest = coverage.observed_end || '--';
    return `\u4e8b\u5b9e\u8986\u76d6\u4e0d\u5b8c\u6574\uff1a\u5df2\u8986\u76d6 ${observed}/${expected} \u5929\uff0c\u6700\u65b0\u6570\u636e ${latest}`;
  }

  // ------------------------------------------------------- 业绩全景 / 目标
  // 周期内分解表（月复盘=月内分周，周复盘=期内按日），来自用户月复盘框架：
  // 品类汇总的销售/利润指标要有周维度表格方便对比。
  const BREAKDOWN_COLUMNS = [
    ['net_sales', '净销售额', 'money'],
    ['profit', '利润', 'money'],
    ['visitors', '访客', 'number'],
    ['conversion', '转化率', 'percent'],
    ['ad_spend', '推广花费', 'money'],
    ['ad_ratio', '费比', 'percent'],
  ];

  function breakdownTable(breakdown) {
    if (!breakdown || !breakdown.rows || !breakdown.rows.length) return null;
    const thead = h('thead', null, h('tr', null,
      h('th', { text: breakdown.grain === 'week' ? '周' : '日期' }),
      ...BREAKDOWN_COLUMNS.map(([key, label]) => h('th', { class: 'num', text: label }))));
    const tbody = h('tbody', null, ...breakdown.rows.map((row) => h('tr', null,
      h('td', { text: row.label }),
      ...BREAKDOWN_COLUMNS.map(([key, , format]) => h('td', {
        class: 'num',
        text: safeMetric((row.metrics || {})[key], format),
      })))));
    return h('div', { class: 'pr-breakdown-table-wrap' },
      h('table', { class: 'pr-table pr-breakdown-table' }, thead, tbody));
  }


  function metricValue(metrics, key) {
    const item = (metrics && metrics.items || []).find((entry) => entry.key === key || entry.metric === key);
    if (item) return item;
    const current = metrics && metrics.current ? metrics.current[key] : null;
    return { value: current, label: key, format: key.includes('ratio') || key.includes('rate') ? 'percent' : key === 'roi' ? 'decimal' : 'money' };
  }

  function signedPercent(value) {
    if (value === null || value === undefined || Number.isNaN(Number(value))) return '--';
    return `${Number(value) > 0 ? '+' : ''}${Number(value).toFixed(1)}%`;
  }

  function stateTag(text, kind) {
    return h('span', { class: `pr-status-tag ${kind || 'info'}`, text });
  }

  function insightLine(label, value, detail, kind) {
    return h('div', { class: 'pr-insight-line' },
      h('span', { class: 'pr-insight-line__label', text: label }),
      h('strong', { class: kind ? `is-${kind}` : '', text: value }),
      detail ? h('small', { text: detail }) : null,
    );
  }

  // 复盘状态只在需要用户处理时提示；周期、品类和对比口径统一由顶栏承载。
  function renderReviewScope(context) {
    const missing = (context && context.missing_inputs) || [];
    if (!els.actionSummary) return;
    els.actionSummary.textContent = missing.length
      ? `缺少数据源：${missing.join('、')}`
      : '';
  }

  // ---------------------------------------------- 顶部统一「数据状态」（P0 #3）
  // 原则：**不是一盏灯，而是「一盏灯 + 触发原因清单」**。
  // 只说「部分数据」读者无法行动——必须能一眼看到哪块降级、为什么、影响什么。
  // severity 两档：warning=数字不可全信；info=口径有边界（已在各块就地标注）。
  const DATA_STATUS_SEVERITY_LABEL = { warning: '影响可信度', info: '口径边界' };

  function dataStatusNode(context) {
    const status = context && context.data_status;
    if (!status) return null;
    const degradations = status.degradations || [];
    const level = status.level || 'partial';
    const tone = status.usable ? 'good' : (level === 'no-data' ? 'empty' : 'warning');
    const summary = h('summary', null,
      h('span', { class: 'pr-data-status__dot', 'aria-hidden': 'true' }),
      h('span', { class: 'pr-data-status__label', text: status.label || '数据状态' }),
      degradations.length
        ? h('span', { class: 'pr-data-status__count', text: '详情 ▾' })
        : null);
    const body = [];
    // 数据区间/进行中说明：读者判断「这份数据到哪一天」的最短路径。
    const fresh = status.freshness || {};
    const freshText = fresh.observed_start && fresh.observed_end
      ? `数据区间 ${fresh.observed_start} ~ ${fresh.observed_end}`
        + (fresh.is_ongoing
          ? `（本期进行中，已过 ${fresh.elapsed_days}/${fresh.total_days} 天）`
          : `（共 ${fresh.total_days} 天）`)
      : null;
    if (freshText) body.push(h('p', { class: 'pr-data-status__fresh', text: freshText }));
    if (status.summary) body.push(h('p', { class: 'pr-data-status__summary', text: status.summary }));
    // 按 severity 分组，warning 在前——影响可信度的必须先看到。
    ['warning', 'info'].forEach((severity) => {
      const group = degradations.filter((item) => item.severity === severity);
      if (!group.length) return;
      body.push(h('p', { class: `pr-data-status__group is-${severity}`, text: DATA_STATUS_SEVERITY_LABEL[severity] }));
      body.push(h('ul', { class: 'pr-data-status__list' }, ...group.map((item) =>
        h('li', { class: `is-${severity}` },
          h('strong', { text: item.label }),
          h('span', { text: `：${item.detail}` })))));
    });
    return h('details', { class: `pr-data-status is-${tone}`, open: false },
      summary,
      h('div', { class: 'pr-data-status__body' }, ...body));
  }

  // 首屏三句结论：把“数据事实 → 最大问题 → 下一步机会”从长页正文前置，
  // 让负责人不用先翻到拆因明细才知道本期重点。所有结论都基于已返回字段，缺数据时明确降级。
  function reviewScopeBar(context) {
    const period = context?.period || {};
    const category = context?.category || {};
    const compare = context?.compare || {};
    const coverage = context?.metrics?.coverage || {};
    const freshness = context?.data_status?.freshness || {};
    const periodTypeLabel = { day: '自然日', week: '周', month: '月' }[state.mode] || state.mode;
    const periodText = period.label || period.key || '--';
    const rangeText = period.start && period.end ? `${period.start} ~ ${period.end}` : '日期待定';
    const compareText = compare.mode === 'none' || compare.available === false
      ? '不对比'
      : (compare.label ? `${compare.short_label || '对比'}：${compare.label}` : '对比周期待定');
    const categoryText = category.label || (category.mode === 'all' ? '全部品类' : category.mode || '全部品类');
    const observedDays = Number(coverage.observed_days ?? freshness.elapsed_days ?? 0);
    const expectedDays = Number(coverage.expected_days ?? freshness.total_days ?? 0);
    const observedEnd = freshness.observed_end || coverage.observed_end;
    const hasData = context?.metrics?.has_data === true;
    const coverageText = observedDays > 0 && expectedDays > 0
      ? `已覆盖 ${observedDays}/${expectedDays} 天${observedEnd ? `，数据至 ${observedEnd}` : ''}`
      : (hasData && observedEnd
        ? `数据至 ${observedEnd}`
        : (expectedDays > 0 && freshness.is_ongoing
          ? `暂无本期数据，周期已过 ${freshness.elapsed_days || 0}/${expectedDays} 天`
          : '暂无本期数据'));
    return h('div', { class: 'pr-command-center__scope', 'aria-label': '复盘口径' },
      h('span', { class: 'pr-scope-pill', text: `${periodTypeLabel} · ${periodText}` }),
      h('span', { class: 'pr-scope-pill', text: rangeText }),
      h('span', { class: 'pr-scope-pill', text: `品类：${categoryText}` }),
      h('span', { class: 'pr-scope-pill', text: `对比：${compareText}` }),
      h('span', { class: `pr-scope-pill ${observedDays > 0 && expectedDays > 0 && observedDays < expectedDays ? 'is-partial' : ''}`, text: coverageText }));
  }

  function reviewInsightCards(context) {
    const current = context?.metrics?.current || {};
    const previous = context?.metrics?.prev || {};
    const has = (value) => value !== null && value !== undefined && Number.isFinite(Number(value));
    const change = (key) => has(current[key]) && has(previous[key]) && Number(previous[key])
      ? (Number(current[key]) - Number(previous[key])) / Math.abs(Number(previous[key]))
      : null;
    const salesChange = change('net_sales');
    const profitChange = change('profit');
    const anomalies = (context?.anomalies || []).filter((item) => item.level === 'danger' || item.level === 'warning');
    const adAnomaly = anomalies.find((item) => /费比|投放|推广/.test(String(item.label || '')));
    const products = context?.products || {};
    const listOf = (...keys) => keys.flatMap((key) => {
      const value = products[key];
      return Array.isArray(value) ? value : (Array.isArray(value?.items) ? value.items : []);
    });
    const issueProduct = listOf('problem_items', 'decline', 'loss', 'paid', 'new_paid')[0];
    const ads = context?.ads || {};
    const directRoi = ads.direct_roi ?? ads.current?.direct_roi;
    const adRatioDelta = ads.delta?.ad_ratio_delta_pt;
    const build = (label, title, detail, tone, action) => h('article', { class: `pr-insight-card is-${tone || 'neutral'}` },
      h('div', { class: 'pr-insight-card__head' }, h('span', { class: 'pr-insight-card__label', text: label }),
        tone && tone !== 'neutral' ? stateTag(tone === 'danger' ? '需处理' : tone === 'good' ? '机会' : '关注', tone === 'danger' ? 'warning' : tone) : null),
      h('strong', { class: 'pr-insight-card__title', text: title }),
      h('p', { class: 'pr-insight-card__detail', text: detail }),
      action ? h('button', { type: 'button', class: 'pr-insight-card__action', text: action.label, onclick: action.onclick }) : null);

    const conclusion = salesChange === null
      ? (has(current.net_sales) ? `本期净销售额 ${formatValue(current.net_sales, 'money')}` : '本期核心业绩暂无可用数据')
      : `净销售额${salesChange >= 0 ? '增长' : '下滑'} ${Math.abs(salesChange * 100).toFixed(1)}%`;
    const conclusionDetail = profitChange === null
      ? '利润环比暂不可比，建议先确认成本与利润口径。'
      : `净利润${profitChange >= 0 ? '增长' : '下滑'} ${Math.abs(profitChange * 100).toFixed(1)}%${has(current.profit) ? `，本期 ${formatValue(current.profit, 'money')}` : ''}。`;
    const problemTitle = anomalies[0]?.label || (issueProduct ? `优先检查：${issueProduct.title || issueProduct.product_id || '问题商品'}` : '暂未识别高优先级问题');
    const problemDetail = anomalies[0]?.detail || (issueProduct
      ? `问题商品${issueProduct.change_rate !== undefined ? `变化 ${formatValue(issueProduct.change_rate, 'percent')}` : ''}，进入货品明细确认流量、转化和投放原因。`
      : '建议生成初稿并补充人工判断，避免只看指标不落结论。');
    const adOpportunity = has(directRoi) && Number(directRoi) >= 2;
    const adProblem = has(directRoi) && Number(directRoi) < 1;
    const opportunityTitle = adOpportunity ? '投放具备放量机会' : adProblem ? '投放优先降费复核' : '先验证再调整预算';
    const opportunityDetail = has(directRoi)
      ? `直接投产 ${formatValue(directRoi, 'decimal')}${has(adRatioDelta) ? `，费比环比 ${adRatioDelta > 0 ? '+' : ''}${Number(adRatioDelta).toFixed(2)}pt` : ''}。`
      : '推广效率数据不足，先补齐渠道或单品归因后再做预算动作。';
    // 最大问题的证据来源不同，跳转也应不同：优先广告/货品对应板块；
    // 只有没有明确对象时才回退到拆因总览。
    const primaryAnomaly = anomalies[0];
    const problemIsAd = (primaryAnomaly && adAnomaly === primaryAnomaly)
      || (!primaryAnomaly && !issueProduct && adProblem);
    const problemAction = problemIsAd
      ? { label: '查看广告', onclick: () => scrollToSection('ads') }
      : (!primaryAnomaly && issueProduct
        ? { label: '查看货品', onclick: () => scrollToSection('products') }
        : { label: '查看拆因', onclick: () => scrollToSection('summary') });
    return h('div', { class: 'pr-command-center__insights', 'aria-label': '本期复盘重点' },
      build('本期结论', conclusion, conclusionDetail, salesChange !== null && salesChange < 0 ? 'warning' : 'good', { label: '查看指标', onclick: () => scrollToSection('summary') }),
      build('最大问题', problemTitle, problemDetail, anomalies.length || issueProduct ? 'danger' : 'neutral', problemAction),
      build('最大机会', opportunityTitle, opportunityDetail, adOpportunity ? 'good' : adProblem ? 'danger' : 'neutral', { label: '查看广告', onclick: () => scrollToSection('ads') }),
    );
  }

  function renderCommandCenter(context) {
    renderReviewScope(context);
    if (!els.commandCenter) return;
    const dangerCount = (context.anomalies || []).filter((item) => item.level === 'danger' || item.level === 'warning').length;
    const blockedCount = (context.actions_blocked || []).length;
    const plannedCount = (context.actions_planned || []).length;
    els.commandCenter.hidden = false;
    // 顶部数据状态统一条（P0 #3）：取代原先只说「数据已就绪 · 覆盖 2/3 天」的裸文案。
    const statusNode = dataStatusNode(context);
    els.commandCenter.replaceChildren(
      h('div', { class: 'pr-command-center__head' },
        h('h3', { text: '复盘结论' }),
        statusNode),
      reviewScopeBar(context),
      // 三大指标完成率卡（对齐月复盘 XMind「完成情况分析」）：
      // 净销售额 / 净利润 / 净费比，口径与复盘设置目标同源。
      metricCards.renderMetricCards(),
      reviewInsightCards(context),
      // 紧凑状态条：风险与执行信号一行带过，点击直达对应工作区。
      h('div', { class: 'pr-command-center__strip' },
        h('button', { type: 'button', class: 'pr-strip-item', onclick: () => scrollToSection('summary') },
          stateTag(dangerCount + blockedCount ? '需关注' : '正常', dangerCount + blockedCount ? 'warning' : 'good'),
          h('span', { text: `风险 ${dangerCount + blockedCount}（异常 ${dangerCount} · 阻塞 ${blockedCount}）` })),
        h('button', { type: 'button', class: 'pr-strip-item', onclick: () => activateWorkbench('execution') },
          stateTag(plannedCount ? '进行中' : '空闲', plannedCount ? 'info' : 'good'),
          h('span', { text: `待落地动作 ${plannedCount}` })),
      ),
    );
  }

  // ------------------------------------------------- 单品周趋势预览（弹窗）
  // 点击货品榜「趋势」按钮：近 8 周指标 SVG 折线，无图表库依赖。
  // 字段集对齐后端 _product_trend 周序列（XMind「点击字段指标 → 周维度折线」）：
  // 弹窗顶部以字段 chips 切换，默认展示净销售额。
  let trendDialog = null;
  let trendMetricKey = 'net_sales';
  let trendCache = null; // {productId, data}——同一商品切字段不重复请求。
  const TREND_METRICS = [
    ['net_sales', '净销售额（元）', 'money'],
    ['gsv', '销售额（元）', 'money'],
    ['visitors', '访客数', 'number'],
    ['buyers', '支付买家数', 'number'],
    ['payment_qty', '销售件数', 'number'],
    ['conversion', '支付转化率', 'percent'],
    ['aov', '客单价（元）', 'money'],
    ['refund_rate', '退款率', 'percent'],
    ['ad_spend', '推广花费（元）', 'money'],
    ['ad_ratio', '费比', 'percent'],
    ['operating_profit', '经营利润（元）', 'money'],
    ['profit_rate', '利润率', 'percent'],
  ];

  // 点标签用紧凑数值（金额 ≥1万 折算万），精确值走 min/max 轴与悬停 title。
  function trendLabel(value, format) {
    if (format === 'percent') return `${(value * 100).toFixed(1)}%`;
    if (format === 'decimal') return value.toFixed(2);
    if (format === 'money') {
      if (Math.abs(value) >= 10000) return `${(value / 10000).toFixed(2)}万`;
      return Math.round(value).toLocaleString('zh-CN');
    }
    return Math.round(value).toLocaleString('zh-CN');
  }

  // 「2026-09 第3周」→「9月W3」：横轴要能看出是哪个月的第几周，不是匿名 W1~W8。
  function shortWeekLabel(week) {
    const match = String(week.label || '').match(/^(\d{4})-(\d{2})\s*第(\d+)周$/);
    if (match) return `${Number(match[2])}月W${match[3]}`;
    if (week.start) {
      const parts = week.start.split('-');
      return `${Number(parts[1])}月${Number(parts[2])}日`;
    }
    return '';
  }

  // 月度轴标签工厂：同一年显示「4月」，跨年显示「2025-12」避免不同年同月名歧义。
  function monthAxisLabeler(rows) {
    const years = new Set(rows.map((row) => String(row.label || row.start || '').slice(0, 4)));
    const sameYear = years.size === 1;
    return (row) => {
      const match = String(row.label || row.start || '').match(/^(\d{4})-(\d{2})/);
      if (!match) return row.start || '';
      return sameYear ? `${Number(match[2])}月` : `${match[1]}-${match[2]}`;
    };
  }

  function trendSvg(rows, key, format, labelFn = shortWeekLabel) {
    const values = rows.map((row) => (row[key] === null || row[key] === undefined ? null : Number(row[key])));
    const valid = values.filter((value) => value !== null);
    if (valid.length < 2) return h('p', { class: 'pr-material__empty', text: '该指标可用数据点不足，无法画趋势。' });
    const width = 640;
    const height = 170;
    const pad = 34;
    const min = Math.min(...valid);
    const max = Math.max(...valid);
    const span = (max - min) || 1;
    const stepX = (width - pad * 2) / (values.length - 1);
    // y 轴留 12% 上下边距，避免线贴边。
    const scaleY = (value) => height - pad - ((value - min) / span) * (height - pad * 2) - (height - pad * 2) * 0.06;
    const points = values
      .map((value, index) => (value === null ? null : `${pad + index * stepX},${scaleY(value)}`))
      .filter(Boolean);
    const baseline = min === 0 && max === 0 ? 1 : 0; // 全 0 数据画平线
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
    svg.setAttribute('class', 'pr-trend-svg');
    const polyline = document.createElementNS('http://www.w3.org/2000/svg', 'polyline');
    polyline.setAttribute('points', points.join(' '));
    polyline.setAttribute('fill', 'none');
    polyline.setAttribute('stroke', 'currentColor');
    polyline.setAttribute('stroke-width', '2');
    svg.append(polyline);
    values.forEach((value, index) => {
      if (value === null) return;
      const cx = pad + index * stepX;
      const cy = scaleY(value) + baseline;
      const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
      circle.setAttribute('cx', String(cx));
      circle.setAttribute('cy', String(cy));
      circle.setAttribute('r', '3');
      svg.append(circle);
      // 每个点直接标数值；贴近顶边的点标签放点下方，其余放上方。
      const label = document.createElementNS('http://www.w3.org/2000/svg', 'text');
      const below = cy < pad + 6;
      label.setAttribute('x', String(cx));
      label.setAttribute('y', String(below ? cy + 16 : cy - 8));
      label.setAttribute('text-anchor', 'middle');
      label.setAttribute('class', 'pr-trend-point-label');
      label.textContent = trendLabel(value, format);
      svg.append(label);
      const tip = document.createElementNS('http://www.w3.org/2000/svg', 'title');
      tip.textContent = `${labelFn(rows[index]) || `#${index + 1}`}（${rows[index].start} ~ ${rows[index].end}）：${formatValue(value, format)}`;
      circle.append(tip);
    });
    // 每个点已自带数值标签，min/max 轴会与之重复且易误读为日期，不再渲染。
    return h('div', { class: 'pr-trend-chart' }, svg);
  }

  async function openProductTrend(row, metricKey) {
    if (metricKey) trendMetricKey = metricKey;
    // 粒度跟随复盘模式：周复盘看近 8 周（月内分周），月复盘看近 8 个完整月。
    const grain = state.mode === 'month' ? 'month' : 'week';
    if (!trendDialog) {
      trendDialog = h('dialog', { class: 'pr-action-dialog pr-trend-dialog' });
      document.body.append(trendDialog);
      enableLightDismiss(trendDialog);
    }
    trendDialog.replaceChildren(
      h('div', { class: 'pr-action-dialog__head' },
        h('div', null,
          h('span', { class: 'section-kicker', text: grain === 'month' ? '月度趋势' : '周维度趋势' }),
          h('h3', { text: row.title || row.product_id }),
          h('p', { text: `商品 ID：${row.product_id} · ${grain === 'month' ? '近 8 个完整月（自然月口径）' : '近 8 周（月内分周口径）'}` })),
        h('button', { type: 'button', class: 'pr-dialog-close', 'aria-label': '关闭', onclick: () => trendDialog.close(), text: '×' })),
      h('div', { class: 'pr-diagnostic-block', 'data-pr-trend-loading': '' },
        h('p', { class: 'pr-material__empty', text: '正在读取趋势…' })),
    );
    if (!trendDialog.open) trendDialog.showModal();

    let data = null;
    let error = null;
    // 缓存键带粒度：周/月复盘切换后不串序列。
    if (trendCache && trendCache.productId === row.product_id && trendCache.grain === grain) {
      data = trendCache.data;
    } else {
      try {
        const response = await DemoApi.domainRequest(
          `/api/period-reviews/product-trend/${encodeURIComponent(row.product_id)}?weeks=8&grain=${grain}`);
        data = response.data;
        trendCache = { productId: row.product_id, grain, data };
      } catch (err) { error = err; }
    }

    const loading = trendDialog.querySelector('[data-pr-trend-loading]');
    const points = data && data.points ? data.points : [];
    const labelFn = grain === 'month' && points.length ? monthAxisLabeler(points) : shortWeekLabel;
    const body = error || !data || !data.available || !points.length
      ? h('div', { class: 'pr-diagnostic-block' },
        h('p', { class: 'pr-material__empty', text: error ? `趋势读取失败：${describeRequestError(error)}` : '该商品近期没有日数据，无法生成趋势。' }))
      : (() => {
        // 「点击字段指标看折线」：字段 chips 即点即换；无数据点的字段禁用。
        const active = TREND_METRICS.find(([key]) => key === trendMetricKey) || TREND_METRICS[0];
        const hasPoints = (key) => points.some((point) => point[key] !== null && point[key] !== undefined);
        const chips = TREND_METRICS.map(([key, label]) => h('button', {
          type: 'button',
          class: `pr-chip pr-trend-chip${key === active[0] ? ' is-active' : ''}`,
          disabled: !hasPoints(key),
          text: label.replace(/（元）$/, ''),
          onclick: () => { trendMetricKey = key; openProductTrend(row, key); },
        }));
        const spanText = `${labelFn(points[0])} ~ ${labelFn(points[points.length - 1])}`;
        const noteText = grain === 'month'
          ? `统计区间 ${spanText}（自然月口径，取自 BI 月度快照，与生命周期同源）；悬停可见具体月份；当月进行中数据不纳入。`
          : `统计区间 ${spanText}（月内分周口径）；悬停可见具体日期区间；比率列按周总量重推，与榜单口径一致；本周为进行中数据不纳入。`;
        return h('div', { class: 'pr-diagnostic-block' },
          h('div', { class: 'pr-chip-row pr-trend-chips' }, ...chips),
          h('div', { class: 'pr-trend-metric' },
            h('h4', { text: active[1] }),
            trendSvg(points, active[0], active[2], labelFn),
            h('div', { class: 'pr-trend-labels' },
              ...points.map((point, index) => h('span', { text: labelFn(point) || `#${index + 1}`, title: `${point.label}（${point.start} ~ ${point.end}）` }))),
          ),
          h('p', { class: 'pr-material__empty', text: noteText }));
      })();
    if (loading) loading.replaceWith(body);
  }

  /** 问题单品聚合清单（对齐 XMind「问题单品分析」）：
   *  跨榜去重（下滑/亏损/高费比），每行标注来源榜单，可直接生成运营动作。
   */
  function problemItemsPanel(problemItems) {
    const items = problemItems || [];
    if (!items.length) {
      return analysisPanel('问题单品清单', '跨榜合并去重（下滑 / 亏损 / 高费比且 销售额占比>1%），从看数到生成动作的最短路径。',
        null, '本期没有命中问题条件的商品。');
    }
    const rows = items.map((row) => {
      const sources = (row.problem_sources || []).map((source) => h('span', { class: 'pr-chip is-warning', text: source }));
      const share = productShare(row);
      const actionBtn = h('button', {
        type: 'button',
        class: 'ui-button ui-button--ghost ui-button--compact',
        text: '生成运营动作',
        onclick: () => openProductDiagnosis(row, (row.problem_sources || []).includes('下滑榜')),
      });
      return h('tr', null,
        h('td', { class: 'pr-table__title', title: row.title || row.product_id },
          row.image_url ? h('img', { src: row.image_url, alt: '', loading: 'lazy' }) : null,
          h('span', { class: 'pr-table__title-text', text: row.title || row.product_id })),
        h('td', null, h('div', { class: 'pr-chip-row' }, ...sources)),
        h('td', { class: 'num', text: safeMetric(row.gsv, 'money') }),
        h('td', { class: 'num', text: share === null ? '--' : `${(share * 100).toFixed(1)}%` }),
        h('td', { class: 'num', text: safeMetric(row.operating_profit, 'money') }),
        h('td', { class: 'num', text: safeMetric(row.ad_spend, 'money') }),
        h('td', { class: 'num', text: row.gsv && row.ad_spend ? safeMetric(row.ad_spend / row.gsv, 'percent') : '--' }),
        h('td', { class: 'pr-table__action' }, actionBtn),
      );
    });
    const table = h('div', { class: 'pr-breakdown-table-wrap' }, h('table', { class: 'pr-table pr-breakdown-table' },
      h('thead', null, h('tr', null,
        h('th', { text: '商品' }),
        h('th', { text: '问题来源' }),
        h('th', { class: 'num', text: '销售额' }),
        h('th', { class: 'num', text: '销售额占比' }),
        h('th', { class: 'num', text: '经营利润' }),
        h('th', { class: 'num', text: '推广花费' }),
        h('th', { class: 'num', text: '费比' }),
        h('th', { text: '操作' }),
      )),
      h('tbody', null, ...rows)));
    // 宽表（8 列 + 长标题）包横向滚动，避免在两列网格的窄栏里被挤成竖排。
    const scroll = h('div', { class: 'pr-table-scroll' }, table);
    return analysisPanel('问题单品清单',
      `跨榜合并去重（下滑 / 亏损 / 费比>30% 且 销售额占比>1%），共 ${items.length} 个商品待处理。`,
      scroll, null);
  }

  /** 口径降级徽标。放在数据块标题上，避免「数字看着正常、口径藏在脚注里」。
   *  与 §data_status 的两档 severity 同构：warning=数字不可全信，info=口径有边界。 */
  function caliberBadge(text, severity) {
    return h('span', {
      class: `pr-caliber-badge is-${severity || 'info'}`,
      text,
      title: text,
    });
  }

  /** 利润是否部分口径：以后端 identity.ok 为唯一判据（恒等式不平＝费用列不全）。
   *  实测所有口径下都不平（残差来自「利润未回填」的补采哨兵行），故必须常标。 */
  function profitIsPartial(structure) {
    return Boolean(structure && structure.available
      && structure.identity && structure.identity.ok === false);
  }

  /** 利润结构块（利润瀑布，对齐 BI 派米恒等口径）：
   *  净销 → 销售费用/自定义费用/货本/发货/其他 → 利润，横向占比条 + 环比。
   *  费用缺失（补采哨兵）显示「缺失」不按 0；identity note 说明残差来源。
   */
  function profitStructureBlock(structure) {
    if (!structure || !structure.available) return null;
    const net = structure.net_sales || 0;
    const barRows = (structure.rows || []).map((row) => {
      const share = row.share_of_net === null || row.share_of_net === undefined ? null : row.share_of_net * 100;
      const isProfit = row.key === 'operating_profit';
      const valueText = row.value === null || row.value === undefined ? '缺失' : formatValue(row.value, 'money');
      const shareText = share === null ? '' : `${share.toFixed(1)}%`;
      const change = row.change_rate === null || row.change_rate === undefined
        ? '' : ` · ${(row.change_rate > 0 ? '+' : '')}${(row.change_rate * 100).toFixed(1)}%`;
      const width = Math.min(Math.abs(row.share_of_net || 0) * 100, 100);
      const color = isProfit ? (row.value < 0 ? 'var(--danger-text, #dc2626)' : 'var(--success-text, #059669)') : 'var(--brand-text, #4f46e5)';
      return h('div', { class: 'pr-profit-row' },
        h('span', { class: 'pr-profit-row__label', text: row.label }),
        h('div', { class: 'pr-profit-row__bar' },
          h('div', { class: 'pr-profit-row__fill', style: `width:${(width * 100).toFixed(1)}%;background:${color}` })),
        h('span', { class: 'num pr-profit-row__value', text: `${valueText} · ${shareText}${change}` }));
    });
    const note = (structure.identity && structure.identity.note) || null;
    const customNote = (structure.caliber && structure.caliber.custom_cost_note) || '';
    // P0 #4：利润恒等式不平 → 利润是**部分口径**，必须在标题上标出来。
    // 不标的话，读者会把「利润 -29,377」当成准确值，而它其实含 155 行未回填。
    const partial = profitIsPartial(structure);
    return materialBlock('利润结构（利润瀑布）',
      h('div', { class: 'pr-profit-structure' },
        h('p', { class: 'pr-profit-structure__net', text: `净销售额 ${formatValue(net, 'money')}${structure.compare ? `（对比期 ${structure.compare.start} ~ ${structure.compare.end}）` : ''}` }),
        ...barRows,
        customCostNote(customNote),
        note ? h('p', { class: 'pr-material__empty', text: note }) : null,
      ),
      null, null,
      partial ? [caliberBadge('部分口径', 'warning')] : null);
  }

  function customCostNote(text) {
    return text ? h('p', { class: 'pr-material__empty', text }) : null;
  }

  /** 货品汇总卡（对齐 XMind「货品-汇总」）：在架/动销/动销率 + 60 天新品动销 + 类目结构。 */
  function goodsSummaryPanel(summary, profitStructure) {
    const info = summary && (summary.sold_count !== undefined) ? summary : null;
    if (!info) return null;
    const items = [];
    const push = (label, value) => items.push(h('div', { class: 'pr-target__item' }, h('span', { text: label }), h('strong', { text: value })));
    push('在架商品', info.listed_count === null || info.listed_count === undefined ? '不可判断' : formatValue(info.listed_count, 'number'));
    push('本期动销', formatValue(info.sold_count, 'number'));
    push('动销率', info.sell_through_rate === null || info.sell_through_rate === undefined ? '不可判断' : `${(info.sell_through_rate * 100).toFixed(2)}%`);
    push('60天新品动销', formatValue(info.new_sold_count, 'number'));
    const categoryStructure = (info.category_structure || []).filter((row) => row.net_sales !== null);
    const structureBody = categoryStructure.length
      ? h('ul', { class: 'pr-linked-list' }, ...categoryStructure.map((row) => h('li', { class: 'pr-linked-item' },
        h('span', { class: 'pr-table__title-text', title: row.category, text: row.category || '未分类' }),
        h('span', { class: 'num', text: `${formatValue(row.net_sales, 'money')}${row.share === null || row.share === undefined ? '' : ` · ${(row.share * 100).toFixed(1)}%`}` }))))
      : null;
    // 产品分层汇总（XMind「产品分层」）：引流/利润/动销，完整矩阵在 products 页。
    // 提示口径粒度=本复盘周期，避免与矩阵页（完整自然月）数字对不上被误解。
    const segments = (info.segment_stats || []).filter((row) => row.count);
    const segmentsBody = segments.length
      ? h('ul', { class: 'pr-linked-list' }, ...segments.map((row) => h('li', { class: 'pr-linked-item' },
        h('span', { text: `${row.segment} · ${row.count} 款` }),
        h('span', { class: 'num', text: `销售额 ${formatValue(row.gsv, 'money')}${row.gsv_share === null || row.gsv_share === undefined ? '' : ` · ${(row.gsv_share * 100).toFixed(1)}%`}` }))))
      : null;
    return analysisPanel('货品汇总',
      '先看规模、分层和类目结构；完整矩阵保留在商品专页。',
      h('div', { class: 'pr-materials' },
        materialBlock('货品规模', h('div', { class: 'pr-target' }, ...items)),
        segmentsBody ? materialBlock('产品分层（本期）', segmentsBody) : null,
        structureBody ? materialBlock('净销售额结构 TOP5', structureBody) : materialBlock('净销售额结构 TOP5', null, '本期没有类目可归的数据。'),
        profitStructureBlock(profitStructure),
      ), null);
  }

  function dimensionPercent(value) {
    return value === null || value === undefined ? '--' : `${(Number(value) * 100).toFixed(1)}%`;
  }

  function dimensionTable(items, type) {
    if (!items || !items.length) return null;
    const nameLabel = type === 'campaign' ? '计划' : '渠道';
    // 渠道视图对齐「渠道拆分」的完整指标列；计划视图维持精简列（计划级口径已单独成表）。
    const channelCols = [
      ['spend_share', '花费占比', (item) => dimensionPercent(item.spend_share)],
      ['direct_roi', '直接投产', (item) => formatValue(item.direct_roi, 'decimal')],
      ['cart_rate', '加购率', (item) => formatValue(item.cart_rate, 'percent')],
      ['cart_cost', '加购成本', (item) => formatValue(item.cart_cost, 'money')],
      ['new_cost', '拉新成本', (item) => formatValue(item.new_cost, 'money')],
      ['new_buyer_share', '新客成交占比', (item) => dimensionPercent(item.new_buyer_share)],
    ];
    const extraCols = type === 'channel' ? channelCols : [];
    const cells = (item, keys) => keys.map(([, , render]) => h('td', { class: 'num', text: render(item) }));
    return h('div', { class: 'pr-breakdown-table-wrap' }, h('table', { class: 'pr-table pr-breakdown-table' },
      h('thead', null, h('tr', null,
        h('th', { text: nameLabel }), h('th', { class: 'num', text: '花费' }),
        ...extraCols.slice(0, 1).map(([, label]) => h('th', { class: 'num', text: label })),
        h('th', { class: 'num', text: '归因成交' }), h('th', { class: 'num', text: 'ROI' }),
        ...extraCols.slice(1).map(([, label]) => h('th', { class: 'num', text: label })),
        h('th', { class: 'num', text: '点击率' }), h('th', { class: 'num', text: '成交变化' }),
      )),
      h('tbody', null, ...items.map((item) => h('tr', null,
        h('td', { title: item.name, text: item.name }),
        h('td', { class: 'num', text: formatValue(item.ad_spend, 'money') }),
        ...cells(item, extraCols.slice(0, 1)),
        h('td', { class: 'num', text: formatValue(item.attributed_payment, 'money') }),
        h('td', { class: 'num', text: formatValue(item.roi, 'decimal') }),
        ...cells(item, extraCols.slice(1)),
        h('td', { class: 'num', text: dimensionPercent(item.ctr) }),
        h('td', { class: 'num', text: item.payment_change_rate === null || item.payment_change_rate === undefined
          ? '--' : `${item.payment_change_rate > 0 ? '+' : ''}${(item.payment_change_rate * 100).toFixed(1)}%` }),
      ))),
    ));
  }

  // -------------------------------------------- 推广计划 → 商品归因表
  // 对齐 XMind「推广计划拆解」：计划级花费/成交 + 归因方式。
  // 归因只做「计划只绑 1 个商品」的精确归因，**不做均摊**（按商品数摊花费=凭空造数），
  // 多商品计划标「多商品」并只在计划级展示。必须把口径写在明面上。
  function campaignAttributionTable(attr) {
    const items = (attr && attr.items) || [];
    if (!items.length) return null;
    const share = attr.exact_share;
    const head = h('tr', null,
      h('th', { text: '计划' }), h('th', { text: '渠道' }),
      h('th', { class: 'num', text: '花费' }), h('th', { class: 'num', text: '归因成交' }),
      h('th', { class: 'num', text: 'ROI' }), h('th', { class: 'num', text: '商品数' }),
      h('th', { text: '归因' }), h('th', { text: '归因商品' }));
    const rows = items.map((item) => {
      const exact = item.attribution === 'exact';
      return h('tr', null,
        h('td', { class: 'pr-table__title', title: item.name, text: item.name }),
        h('td', { text: item.channel || '--' }),
        h('td', { class: 'num', text: formatValue(item.ad_spend, 'money') }),
        h('td', { class: 'num', text: formatValue(item.attributed_payment, 'money') }),
        h('td', { class: 'num', text: formatValue(item.roi, 'decimal') }),
        h('td', { class: 'num', text: item.product_count == null ? '--' : String(item.product_count) }),
        h('td', null, h('span', {
          class: `pr-chip is-${exact ? 'info' : 'warning'}`,
          text: exact ? '精确' : '多商品',
        })),
        h('td', { class: 'pr-table__title', title: item.product_title || '', text: item.product_title || (exact ? '' : '不拆分') }));
    });
    const note = (attr.attribution_note || '')
      + (share == null ? '' : ` 本期可精确归因的计划花费占比 ${(share * 100).toFixed(1)}%。`);
    return materialBlock('推广计划拆解（计划 → 商品归因）',
      h('div', { class: 'pr-breakdown-table-wrap' },
        h('table', { class: 'pr-table pr-breakdown-table' },
          h('thead', null, head), h('tbody', null, ...rows))),
      null, note);
  }

  function trafficTable(traffic) {
    if (!traffic || !traffic.items || !traffic.items.length) return null;
    const labels = { search: '搜索', recommend: '推荐', paid: '付费', organic: '自然' };
    return h('div', { class: 'pr-breakdown-table-wrap' }, h('table', { class: 'pr-table pr-breakdown-table' },
      h('thead', null, h('tr', null,
        h('th', { text: '来源' }), h('th', { class: 'num', text: '访客' }),
        h('th', { class: 'num', text: '占比' }), h('th', { class: 'num', text: '环比' }),
      )),
      h('tbody', null, ...traffic.items.map((item) => h('tr', null,
        h('td', { text: labels[item.key] || item.key }),
        h('td', { class: 'num', text: formatCompact(item.value) }),
        h('td', { class: 'num', text: dimensionPercent(item.share_of_visitors) }),
        h('td', { class: 'num', text: item.change_rate === null || item.change_rate === undefined
          ? '--' : `${item.change_rate > 0 ? '+' : ''}${(item.change_rate * 100).toFixed(1)}%` }),
      ))),
    ));
  }

  // ------------------------------------------------- 广告单品 TOP 消耗表
  // 每个渠道分组 6 列：花费 / 总投产 / 直接投产 / 加购成本 / 拉新成本 / 加购率。
  // 商品×渠道粒度数据源未提供商品映射时整组列不渲染，并给出说明。
  const PROMO_ITEM_CHANNEL_COLS = [
    ['ad_spend', '花费', 'money'],
    ['roi', '总投产', 'decimal'],
    ['direct_roi', '直接投产', 'decimal'],
    ['cart_cost', '加购成本', 'money'],
    ['new_cost', '拉新成本', 'money'],
    ['cart_rate', '加购率', 'percent'],
  ];

  function renderPromotionItems(promotionItems) {
    if (!els.promotionAnalysis) return null;
    const data = promotionItems || {};
    const items = data.items || [];
    if (!items.length) {
      return analysisPanel('广告单品 TOP20 消耗', '按推广花费排序的商品级投放指标。', null, '本期没有商品级推广数据。');
    }
    const groups = (data.channel_groups || []).filter(
      (name) => items.some((item) => (item.channels || {})[name]),
    );
    const noChannelScope = (data.missing_inputs || []).includes('promotion_product_channel_scope');
    const head1 = [h('th', { rowspan: '2', text: '商品' }), h('th', { rowspan: '2', class: 'num', text: '花费' }), h('th', { rowspan: '2', class: 'num', text: '费比' })];
    const head2 = [];
    groups.forEach((name) => head1.push(h('th', { colspan: '6', text: name })));
    groups.forEach(() => {
      PROMO_ITEM_CHANNEL_COLS.forEach(([, label]) => head2.push(h('th', { class: 'num', text: label })));
    });
    const cell = (value, format) => h('td', { class: 'num', text: safeMetric(value, format) });
    const body = items.map((item) => {
      const tr = h('tr', null,
        h('td', { class: 'pr-table__title' },
          item.image_url ? h('img', {
            src: item.image_url,
            alt: '',
            loading: 'lazy',
            onerror: (event) => { event.currentTarget.hidden = true; },
          }) : null,
          h('span', { class: 'pr-table__title-text', title: item.title || item.product_id, text: item.title || item.product_id })),
        cell(item.totals && item.totals.ad_spend, 'money'),
        cell(item.totals && item.totals.ad_ratio, 'percent'),
      );
      groups.forEach((name) => {
        const group = (item.channels || {})[name];
        PROMO_ITEM_CHANNEL_COLS.forEach(([key, , format]) => {
          tr.append(cell(group ? group[key] : null, format));
        });
      });
      return tr;
    });
    const table = h('div', { class: 'pr-breakdown-table-wrap' },
      h('table', { class: 'pr-table pr-breakdown-table' },
        h('thead', null, h('tr', null, ...head1), h('tr', null, ...head2)),
        h('tbody', null, ...body)));
    const hint = noChannelScope && !groups.length
      ? '本期没有「商品×渠道」明细（商品×渠道采集自 2026-08-20 起），因此只展示商品级合计；渠道拆分见上方「推广渠道拆解」。'
      : '按推广花费排序的商品级投放指标；费比 = 花费 ÷ 归因成交，拉新成本 = 花费 ÷ 成交新客。';
    return analysisPanel('广告单品 TOP20 消耗', hint, table, null);
  }

  // ------------------------------------------------------- 指标矩阵 / 类目拆解
  function matrixMetricColumns(columns) {
    if (!columns || !columns.length) return [];
    return columns.map((col) => ({ key: col[0], label: col[1], format: col[2], lower_better: col[3] }));
  }

  // 若某列在所有行都没有数值（例如当前周期 BI 未导出「无界」相关列），
  // 整列渲染出来只有一片 "--"，属于噪声，直接隐藏该列。
  function visibleMatrixColumns(columns, rows) {
    if (!columns.length || !rows || !rows.length) return columns;
    return columns.filter((col) => rows.some((row) => {
      const metric = (row.metrics || {})[col.key];
      return !!metric && metric.value !== null && metric.value !== undefined;
    }));
  }

  // 与列过滤对称：整行所有指标都为空（如 daily_data 只覆盖 3 个月时矩阵前排的
  // 「2026年2月 · 无数据」行）直接隐藏，首屏第一行应该是有数据的周期。
  function visibleMatrixRows(rows, columns) {
    if (!rows || !rows.length || !columns.length) return rows || [];
    const dataRows = rows.filter((row) => columns.some((col) => {
      const metric = (row.metrics || {})[col.key];
      return !!metric && metric.value !== null && metric.value !== undefined;
    }));
    // 极端情况：所有行都无数据时保留原行，让空态说明可见，而不是渲染一张空表。
    return dataRows.length ? dataRows : rows;
  }

  function matrixValue(metric) {
    if (!metric || metric.value === null || metric.value === undefined) {
      return { text: '--', kind: 'missing', ratio: 0 };
    }
    const num = Number(metric.value);
    const fmt = metric.format;
    let text;
    if (fmt === 'money') text = formatCompact(num);
    else if (fmt === 'percent') text = `${(num * 100).toFixed(1)}%`;
    else if (fmt === 'decimal') text = num.toFixed(2);
    else text = num.toLocaleString('zh-CN');
    return { text, kind: 'value', ratio: 0, raw: num };
  }

  function matrixDelta(metric) {
    if (!metric || metric.change_rate === null || metric.change_rate === undefined) return null;
    const change = Number(metric.change_rate);
    // 4-3：极性判断统一走 MetricPolarity（这里显式传后端下发的 lower_better）。
    const good = MetricPolarity.isGood(metric.key, change, { lowerBetter: metric.lower_better });
    const kind = good === null ? 'neutral' : (good ? 'up' : 'down');
    const sign = change > 0 ? '+' : '';
    const text = `${sign}${(change * 100).toFixed(1)}%`;
    return { text, kind };
  }

  function matrixStatusClass(status) {
    return ({ success: 'is-success', warning: 'is-warning', danger: 'is-danger', unknown: 'is-unknown' })[status] || 'is-normal';
  }

  function matrixStatusLabel(status) {
    return ({ success: '增长', warning: '预警', danger: '风险', normal: '正常', unknown: '无数据' })[status] || status;
  }

  function renderMatrixCell(metric, maxAbs, colIndex) {
    const val = matrixValue(metric);
    const delta = matrixDelta(metric);
    const ratio = maxAbs > 0 && val.raw !== undefined ? Math.min(Math.abs(val.raw) / maxAbs, 1) : 0;
    const barColor = val.raw !== undefined && val.raw < 0 ? 'var(--danger-tint, rgba(239,68,68,0.15))' : 'var(--brand-tint, rgba(59,130,246,0.18))';
    const cell = h('td', { class: 'pr-matrix-cell' });
    cell.style.backgroundImage = `linear-gradient(to right, ${barColor} 0%, ${barColor} ${ratio * 100}%, transparent ${ratio * 100}%)`;
    // 注意：Element.append(null) 会把 null 转成字符串 "null"，必须先过滤再追加。
    const parts = [h('div', { class: 'pr-matrix-cell__value' }, val.text)];
    if (delta) {
      const kindClass = delta.kind === 'up' ? 'is-up' : delta.kind === 'down' ? 'is-down' : 'is-neutral';
      parts.push(h('div', { class: `pr-matrix-cell__delta ${kindClass}` }, delta.text));
    }
    cell.append(...parts);
    return cell;
  }

  function renderMatrixHeader(columns) {
    const headerCells = [h('th', { class: 'pr-matrix-cell--period' }, '周期'), h('th', { class: 'pr-matrix-cell--status' }, '状态')];
    columns.forEach((col) => {
      headerCells.push(h('th', { class: 'pr-matrix-cell--metric', title: col.label }, col.label));
    });
    return h('tr', null, ...headerCells);
  }

  function renderPeriodCellLabel(label) {
    const text = String(label || '').trim();
    const match = text.match(/^(.*?)[\uFF08(](.*?)[\uFF09)]$/);
    if (!match) return h('span', { class: 'pr-period-label__main', text: text || '--' });
    return h('span', { class: 'pr-period-label' },
      h('span', { class: 'pr-period-label__main', text: match[1] }),
      h('span', { class: 'pr-period-label__range', text: `（${match[2]}）` }),
    );
  }

  function renderMatrixTable(data) {
    if (!data.rows || !data.rows.length) {
      return h('p', { class: 'pr-material__empty', text: '暂无指标矩阵数据。' });
    }
    const columns = visibleMatrixColumns(matrixMetricColumns(data.columns), data.rows);
    const rows = visibleMatrixRows(data.rows, columns);
    // 预计算每列最大绝对值，用于数据条缩放
    const maxByColumn = {};
    columns.forEach((col) => {
      maxByColumn[col.key] = Math.max(...rows.map((row) => Math.abs((row.metrics[col.key] || {}).value || 0)), 0.0001);
    });

    const thead = h('thead', null, renderMatrixHeader(columns));
    const tbody = h('tbody', null, ...rows.map((row) => {
      const tr = h('tr', { class: `pr-matrix-row ${matrixStatusClass(row.status)}` });
      tr.append(h('td', { class: 'pr-matrix-cell--period' }, renderPeriodCellLabel(row.label)));
      tr.append(h('td', { class: 'pr-matrix-cell--status' }, h('span', { class: `pr-status-tag ${matrixStatusClass(row.status).replace('is-', '')}` }, matrixStatusLabel(row.status))));
      columns.forEach((col) => {
        tr.append(renderMatrixCell(row.metrics[col.key], maxByColumn[col.key], col.key));
      });
      return tr;
    }));
    // 17 列宽表包横向滚动：窄栏里不挤压列，溢出交由滚动条。
    return h('div', { class: 'pr-table-scroll' }, h('table', { class: 'pr-matrix-table' }, thead, tbody));
  }

  // 加载失败时的面板：给出具体原因 + 就地重试按钮，
  // 不再是一句「加载失败或后端接口未就绪」让人只能整页刷新。
  function matrixFailurePanel(title, hint, error, loading) {
    return h('article', { class: 'ui-panel pr-analysis-panel' },
      h('div', { class: 'panel__header' },
        h('div', null, h('h3', { class: 'panel__title', text: title }), h('p', { class: 'panel__hint', text: hint }))),
      h('div', { class: 'ui-panel__body' },
        h('div', { class: 'pr-load-failure' },
          h('p', { class: 'pr-material__empty', text: loading ? '重新加载中…' : `加载失败：${describeRequestError(error)}` }),
          h('button', {
            type: 'button',
            class: 'ui-button ui-button--ghost ui-button--compact',
            text: '重新加载',
            disabled: !!loading,
            onclick: reloadMatrixPanels,
          }))));
  }

  function renderMatrix(matrix, error, loading) {
    if (!els.matrix) return;
    if (!matrix || !matrix.rows) {
      if (loading || error) {
        els.matrix.replaceChildren(matrixFailurePanel(
          '指标矩阵', '按周期展示核心经营指标与环比变化。', error, loading));
        return;
      }
      els.matrix.replaceChildren(analysisPanel(
        '指标矩阵', '按周期展示核心经营指标与环比变化。', null, '暂无矩阵数据。'));
      return;
    }
    els.matrix.replaceChildren(
      analysisPanel('指标矩阵', '最近周期核心指标与环比变化；背景条表示该列绝对值大小，全空的指标列自动隐藏。', renderMatrixTable(matrix), '暂无矩阵数据。'),
    );
  }


  function renderCategoryBreakdown(breakdown, error, loading) {
    if (!els.categoryBreakdown) return;
    if (!breakdown || !breakdown.rows) {
      if (loading || error) {
        els.categoryBreakdown.replaceChildren(matrixFailurePanel(
          '类目拆解', '当前周期按 products.category 拆分的指标。', error, loading));
        return;
      }
      els.categoryBreakdown.replaceChildren(analysisPanel(
        '类目拆解', '当前周期按 products.category 拆分的指标。', null, '暂无类目数据。'));
      return;
    }
    const columns = visibleMatrixColumns(matrixMetricColumns(breakdown.columns), breakdown.rows);
    const catRows = visibleMatrixRows(breakdown.rows, columns);
    const maxByColumn = {};
    columns.forEach((col) => {
      maxByColumn[col.key] = Math.max(...catRows.map((row) => Math.abs((row.metrics[col.key] || {}).value || 0)), 0.0001);
    });

    const thead = h('thead', null,
      h('tr', null,
        h('th', { class: 'pr-matrix-cell--category' }, '所属类目'),
        h('th', { class: 'pr-matrix-cell--status' }, '状态'),
        ...columns.map((col) => h('th', { class: 'pr-matrix-cell--metric', title: col.label }, col.label)),
      ),
    );
    const tbody = h('tbody', null, ...catRows.map((row) => {
      const tr = h('tr', { class: `pr-matrix-row ${matrixStatusClass(row.status)}` });
      tr.append(h('td', { class: 'pr-matrix-cell--category' }, row.category));
      tr.append(h('td', { class: 'pr-matrix-cell--status' }, h('span', { class: `pr-status-tag ${matrixStatusClass(row.status).replace('is-', '')}` }, matrixStatusLabel(row.status))));
      columns.forEach((col) => {
        tr.append(renderMatrixCell(row.metrics[col.key], maxByColumn[col.key], col.key));
      });
      return tr;
    }));
    const table = h('div', { class: 'pr-table-scroll' }, h('table', { class: 'pr-matrix-table' }, thead, tbody));
    els.categoryBreakdown.replaceChildren(
      analysisPanel('类目拆解', `${breakdown.period.label} · 按 products.category 聚合；无数据的指标列会自动隐藏。`, table, '暂无类目数据。'),
    );
  }

  function analysisPanel(title, hint, body, emptyText) {
    const bodyNode = body || h('p', { class: 'pr-material__empty', text: emptyText || '暂无数据。' });
    return h('article', { class: 'ui-panel pr-analysis-panel' },
      h('div', { class: 'panel__header' }, h('div', null, h('h3', { class: 'panel__title', text: title }), h('p', { class: 'panel__hint', text: hint }))),
      h('div', { class: 'ui-panel__body' }, bodyNode),
    );
  }

  function workflowButton(label, onclick) {
    return h('button', {
      type: 'button',
      class: 'ui-button ui-button--ghost ui-button--compact',
      text: label,
      onclick,
    });
  }

  async function transitionReviewAction(row, target, extra = {}) {
    if (actionSaving) return;
    actionSaving = true;
    try {
      await DemoApi.domainRequest(`/api/actions/${encodeURIComponent(row.id)}/transition`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          capability_key: 'product-detail.review_action',
          status: target,
          version: row.version,
          ...extra,
        }),
      });
      await load();
      stateBanner('\u52a8\u4f5c\u72b6\u6001\u5df2\u66f4\u65b0\uff0c\u8bf7\u7ee7\u7eed\u8865\u5145\u89c2\u5bdf\u7ed3\u679c\u3002', '');
    } catch (error) {
      stateBanner(error.message || '\u52a8\u4f5c\u72b6\u6001\u66f4\u65b0\u5931\u8d25\uff0c\u8bf7\u5148\u5237\u65b0\u3002', 'calculation-failed');
    } finally {
      actionSaving = false;
    }
  }

  async function recalculateReviewActions() {
    if (actionSaving) return;
    actionSaving = true;
    try {
      await DemoApi.domainRequest('/api/actions/recalculate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ capability_key: 'product-detail.review_action' }),
      });
      await load();
      stateBanner('\u89c2\u5bdf\u7ed3\u679c\u5df2\u91cd\u7b97\uff0c\u8bf7\u5728\u5f85\u590d\u76d8\u9a8c\u6536\u4e2d\u786e\u8ba4\u3002', '');
    } catch (error) {
      stateBanner(error.message || '\u89c2\u5bdf\u7ed3\u679c\u91cd\u7b97\u5931\u8d25\u3002', 'calculation-failed');
    } finally {
      actionSaving = false;
    }
  }

  // ------------------------------------------------- 标记阻塞 / 取消动作
  let blockDialog = null;

  function openActionBlock(row) {
    if (!blockDialog) {
      blockDialog = h('dialog', { class: 'pr-action-dialog' });
      document.body.append(blockDialog);
      enableLightDismiss(blockDialog);
    }
    const form = h('form', { class: 'pr-action-form' });
    form.append(
      actionField('阻塞原因', 'blocked_reason', 'textarea', '', true),
      actionField('需要谁/什么资源', 'resource_note', 'textarea', ''),
      actionField('预计恢复日期', 'expected_recovery_at', 'date', '', true),
      h('p', { class: 'pr-action-form__status', 'data-pr-block-status': '' }),
      h('div', { class: 'pr-action-dialog__actions' },
        h('button', { type: 'button', class: 'ui-button', onclick: () => blockDialog.close(), text: '取消' }),
        h('button', { type: 'submit', class: 'ui-button ui-button--primary', text: '标记阻塞' }),
      ),
    );
    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      if (actionSaving) return;
      const data = new FormData(form);
      const reason = String(data.get('blocked_reason') || '').trim();
      const resource = String(data.get('resource_note') || '').trim();
      const recovery = String(data.get('expected_recovery_at') || '').trim();
      const status = form.querySelector('[data-pr-block-status]');
      if (!reason || !recovery) {
        if (status) status.textContent = '阻塞原因与预计恢复日期为必填。';
        return;
      }
      // 资源需求并进阻塞原因，后端只有一个 blocked_reason 字段。
      const mergedReason = resource ? `${reason}（需支持：${resource}）` : reason;
      actionSaving = true;
      if (status) status.textContent = '提交中…';
      try {
        await transitionReviewAction(row, 'blocked', {
          blocked_reason: mergedReason,
          expected_recovery_at: recovery,
        });
        blockDialog.close();
      } catch (error) {
        if (status) status.textContent = error.message || '标记阻塞失败，请重试。';
        actionSaving = false;
      }
    });
    blockDialog.replaceChildren(
      h('div', { class: 'pr-action-dialog__head' },
        h('div', null,
          h('span', { class: 'section-kicker', text: '标记阻塞' }),
          h('h3', { text: row.product_title || row.product_id }),
          h('p', { text: `${row.action_type || '运营动作'} · 阻塞后需说明资源与恢复条件，复盘时可追溯。` }),
        ),
        h('button', { type: 'button', class: 'pr-dialog-close', 'aria-label': '关闭', onclick: () => blockDialog.close(), text: '×' }),
      ),
      form,
    );
    if (!blockDialog.open) blockDialog.showModal();
  }

  async function cancelReviewAction(row) {
    if (actionSaving) return;
    const label = `${row.product_title || row.product_id} · ${row.action_type || '动作'}`;
    if (!window.confirm(`确定取消该动作吗？\n\n${label}\n取消后动作进入「已取消」，不可再推进（可删除）。`)) return;
    await transitionReviewAction(row, 'cancelled', { reason: '复盘页手动取消' });
  }

  function openActionReview(row) {
    if (!actionReviewDialog) {
      actionReviewDialog = h('dialog', { class: 'pr-action-dialog' });
      document.body.append(actionReviewDialog);
      enableLightDismiss(actionReviewDialog);
    }
    const form = h('form', { class: 'pr-action-form' });
    const effective = h('select', { name: 'effective', required: true },
      h('option', { value: 'true', text: '\u6709\u6548\uff0c\u4fdd\u7559\u52a8\u4f5c' }),
      h('option', { value: 'false', text: '\u65e0\u6548\uff0c\u9700\u8c03\u6574' }),
    );
    form.append(
      actionField('\u662f\u5426\u6709\u6548', 'effective', 'text', '', true),
    );
    form.querySelector('[name="effective"]').replaceWith(effective);
    form.append(
      actionField('\u590d\u76d8\u539f\u56e0', 'reason', 'textarea', '', true),
      actionField('\u590d\u76d8\u7ed3\u8bba', 'conclusion', 'textarea', '', true),
      actionField('\u4e0b\u4e00\u6b65', 'next_action', 'textarea', '', true),
      actionField('\u590d\u76d8\u4eba', 'reviewer', 'text', els.reviewer?.value || '\u8fd0\u8425\u4eba\u5458', true),
      h('p', { class: 'pr-action-form__status', 'data-pr-action-review-status': '' }),
      h('div', { class: 'pr-action-dialog__actions' },
        h('button', { type: 'button', class: 'ui-button', onclick: () => actionReviewDialog.close(), text: '\u53d6\u6d88' }),
        h('button', { type: 'submit', class: 'ui-button ui-button--primary', text: '\u63d0\u4ea4\u590d\u76d8\u9a8c\u6536' }),
      ),
    );
    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      if (actionSaving) return;
      const data = new FormData(form);
      actionSaving = true;
      const status = form.querySelector('[data-pr-action-review-status]');
      try {
        await DemoApi.domainRequest(`/api/actions/${encodeURIComponent(row.id)}/review`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            capability_key: 'product-detail.review_action',
            version: row.version,
            effective: data.get('effective') === 'true',
            reason: String(data.get('reason') || '').trim(),
            conclusion: String(data.get('conclusion') || '').trim(),
            next_action: String(data.get('next_action') || '').trim(),
            reviewer: String(data.get('reviewer') || '').trim(),
          }),
        });
        actionReviewDialog.close();
        await load();
        stateBanner('\u52a8\u4f5c\u5df2\u5b8c\u6210\u590d\u76d8\u9a8c\u6536\uff0c\u7ed3\u679c\u5df2\u56de\u6d41\u3002', '');
      } catch (error) {
        if (status) status.textContent = error.message || '\u590d\u76d8\u63d0\u4ea4\u5931\u8d25\uff0c\u8bf7\u68c0\u67e5\u540e\u91cd\u8bd5\u3002';
      } finally {
        actionSaving = false;
      }
    });
    actionReviewDialog.replaceChildren(
      h('div', { class: 'pr-action-dialog__head' },
        h('div', null,
          h('span', { class: 'section-kicker', text: '\u52a8\u4f5c\u9a8c\u6536' }),
          h('h3', { text: row.product_title || row.product_id }),
          h('p', { text: `${row.action_type || '\u8fd0\u8425\u52a8\u4f5c'} \u00b7 ${row.product_id}` }),
        ),
        h('button', { type: 'button', class: 'pr-dialog-close', 'aria-label': '\u5173\u95ed', onclick: () => actionReviewDialog.close(), text: '\u00d7' }),
      ),
      h('div', { class: 'pr-diagnostic-block' },
        h('h4', { text: '\u89c2\u5bdf\u7ed3\u679c' }),
        h('p', { class: 'pr-material__empty', text: `\u76ee\u6807 ${row.target_value === null || row.target_value === undefined ? '\u5f85\u8865\u5145' : safeMetric(row.target_value, actionMetricFormat(row.target_metric))} \u00b7 \u6267\u884c\u524d ${safeMetric(row.before_metric_value, actionMetricFormat(row.target_metric), '\u5f85\u91cd\u7b97')} \u00b7 \u6267\u884c\u540e ${safeMetric(row.after_metric_value, actionMetricFormat(row.target_metric), '\u5f85\u91cd\u7b97')} \u00b7 \u53d8\u5316 ${safeMetric(row.result_change, actionMetricFormat(row.target_metric), '\u5f85\u91cd\u7b97')}` }),
        row.acceptance_criteria ? h('p', { class: 'pr-material__empty', text: `\u9a8c\u6536\u6807\u51c6\uff1a${row.acceptance_criteria}` }) : null,
      ),
      form,
    );
    if (!actionReviewDialog.open) actionReviewDialog.showModal();
  }

  function actionStatusLabel(status) {
    return ({
      draft: '草稿', pending_execution: '待执行', executing: '执行中',
      observing: '观察中', pending_review: '待复盘', completed: '已完成',
      blocked: '已阻塞', calculation_failed: '计算失败', cancelled: '已取消',
    })[status] || status || '--';
  }

  async function openActionDetails(row) {
    if (!actionDetailDialog) {
      actionDetailDialog = h('dialog', { class: 'pr-action-dialog' });
      document.body.append(actionDetailDialog);
      enableLightDismiss(actionDetailDialog);
    }
    actionDetailDialog.replaceChildren(
      h('div', { class: 'pr-action-dialog__head' },
        h('div', null,
          h('span', { class: 'section-kicker', text: '动作追踪' }),
          h('h3', { text: row.product_title || row.product_id }),
          h('p', { text: `${row.action_type || '运营动作'} · ${actionStatusLabel(row.status)}` }),
        ),
        h('button', { type: 'button', class: 'pr-dialog-close', 'aria-label': '关闭', onclick: () => actionDetailDialog.close(), text: '×' }),
      ),
      h('div', { class: 'pr-diagnostic-block', 'data-pr-action-detail-loading': '' },
        h('p', { class: 'pr-material__empty', text: '正在读取动作证据链…' }),
      ),
    );
    if (!actionDetailDialog.open) actionDetailDialog.showModal();

    let history = [];
    try {
      const response = await DemoApi.domainRequest(`/api/actions/${encodeURIComponent(row.id)}/history`);
      history = Array.isArray(response.data) ? response.data : [];
    } catch (error) {
      history = [];
    }

    const sourcePeriod = row.source_period_key || row.source_period || '--';
    const verificationPeriod = row.verification_period_key || '--';
    const snapshot = (() => {
      try { return row.source_diagnosis_snapshot ? JSON.parse(row.source_diagnosis_snapshot) : null; } catch (_) { return null; }
    })();
    const historyList = history.length
      ? h('ol', { class: 'pr-action-history' }, ...history.map((item) => h('li', null,
        h('strong', { text: `${actionStatusLabel(item.from_status)} → ${actionStatusLabel(item.to_status)}` }),
        h('span', { text: ` · ${item.created_at || '--'} · ${item.operator || '系统'}` }),
        item.detail ? h('small', { text: item.detail }) : null,
      )))
      : h('p', { class: 'pr-material__empty', text: '暂无状态变更记录。' });

    const detail = h('div', null,
      h('div', { class: 'pr-diagnostic-block' },
        h('h4', { text: '动作口径' }),
        h('div', { class: 'pr-diagnostic-facts' },
          h('div', null, h('span', { text: '动作目的' }), h('strong', { text: row.purpose_note || '--' })),
          h('div', null, h('span', { text: '目标指标' }), h('strong', { text: row.target_metric || '--' })),
          h('div', null, h('span', { text: '\u76ee\u6807\u503c' }), h('strong', { text: row.target_value === null || row.target_value === undefined ? '--' : String(row.target_value) })),
          h('div', null, h('span', { text: '\u9a8c\u6536\u6807\u51c6' }), h('strong', { text: row.acceptance_criteria || '--' })),
          h('div', null, h('span', { text: '观察窗口' }), h('strong', { text: row.observer_window_days ? `${row.observer_window_days} 天` : '--' })),
          h('div', null, h('span', { text: '负责人' }), h('strong', { text: row.assigned_to || '--' })),
        ),
      ),
      h('div', { class: 'pr-diagnostic-block' },
        h('h4', { text: '来源与验证周期' }),
        h('div', { class: 'pr-diagnostic-facts' },
          h('div', null, h('span', { text: '来源复盘' }), h('strong', { text: sourcePeriod })),
          h('div', null, h('span', { text: '来源问题' }), h('strong', { text: row.source_problem_key || '--' })),
          h('div', null, h('span', { text: '验证复盘' }), h('strong', { text: verificationPeriod })),
          h('div', null, h('span', { text: '执行日期' }), h('strong', { text: row.executed_at || '--' })),
        ),
        snapshot ? h('p', { class: 'pr-material__empty', text: `创建时诊断快照：销售额 ${safeMetric(snapshot.gsv, 'money')} · 上期 ${safeMetric(snapshot.prev_gsv, 'money')} · 变化 ${safeMetric(snapshot.change_rate, 'percent')}` }) : null,
      ),
      h('div', { class: 'pr-diagnostic-block' },
        h('h4', { text: '观察结果' }),
        h('p', { class: 'pr-material__empty', text: `执行前 ${safeMetric(row.before_metric_value, 'money', '待计算')} · 执行后 ${safeMetric(row.after_metric_value, 'money', '待计算')} · 变化 ${safeMetric(row.result_change, 'money', '待计算')}` }),
        row.calculation_note ? h('p', { class: 'pr-material__empty', text: row.calculation_note }) : null,
        row.review_conclusion ? h('p', { class: 'pr-material__empty', text: `复盘结论：${row.review_conclusion}` }) : null,
        row.review_next_action ? h('p', { class: 'pr-material__empty', text: `下一步：${row.review_next_action}` }) : null,
      ),
      h('div', { class: 'pr-diagnostic-block' }, h('h4', { text: '状态历史' }), historyList),
    );
    const loading = actionDetailDialog.querySelector('[data-pr-action-detail-loading]');
    if (loading) loading.replaceWith(detail);
  }

  function renderActionListWithControls(rows) {
    if (!rows || !rows.length) return null;
    return h('ul', { class: 'pr-actions-list' }, ...rows.map((row) => {
      const controls = [workflowButton('查看链路', () => openActionDetails(row))];
      if (row.status === 'draft') controls.push(workflowButton('\u8fdb\u5165\u6267\u884c', () => transitionReviewAction(row, 'pending_execution')));
      if (row.status === 'pending_execution') controls.push(workflowButton('\u5f00\u59cb\u6267\u884c', () => transitionReviewAction(row, 'executing')));
      if (row.status === 'executing') controls.push(workflowButton('\u5f00\u59cb\u89c2\u5bdf', () => transitionReviewAction(row, 'observing', { executed_at: row.executed_at || row.planned_at })));
      if (row.status === 'observing') controls.push(workflowButton('\u91cd\u7b97\u89c2\u5bdf', recalculateReviewActions));
      if (row.status === 'pending_review') controls.push(workflowButton('\u63d0\u4ea4\u590d\u76d8', () => openActionReview(row)));
      if (row.status === 'blocked') controls.push(workflowButton('\u89e3\u9664\u963b\u585e', () => transitionReviewAction(row, 'pending_execution')));
      // 标记阻塞：除 blocked 自身与终态外都可阻塞（与后端 TRANSITIONS 一致）。
      if (['draft', 'pending_execution', 'executing', 'observing', 'pending_review', 'calculation_failed'].includes(row.status)) {
        controls.push(workflowButton('标记阻塞', () => openActionBlock(row)));
      }
      // 取消：终态（completed/cancelled）外都允许。
      if (!['completed', 'cancelled'].includes(row.status)) {
        controls.push(workflowButton('取消动作', () => cancelReviewAction(row)));
      }
      const resultText = row.status === 'pending_review' || row.status === 'completed'
        ? `\u00b7 \u6267\u884c\u524d ${safeMetric(row.before_metric_value, 'money', '\u5f85\u8ba1\u7b97')} \u00b7 \u6267\u884c\u540e ${safeMetric(row.after_metric_value, 'money', '\u5f85\u8ba1\u7b97')}`
        : '';
      return h('li', null,
        h('div', { class: 'pr-action-row' },
          h('div', null,
            h('b', { text: `${row.product_title || row.product_id} \u00b7 ${row.action_type || '\u52a8\u4f5c'}` }),
            h('span', { text: ` \u00b7 ${actionStatusLabel(row.status)} \u00b7 \u8ba1\u5212 ${row.planned_at || '--'}${row.executed_at ? ` \u00b7 \u6267\u884c ${row.executed_at}` : ''}${row.verification_period_key ? ` \u00b7 \u9a8c\u8bc1 ${row.verification_period_key}` : ''}${resultText}` }),
            row.purpose_note ? h('small', { text: row.purpose_note }) : null,
            row.blocked_reason ? h('small', { text: `\u963b\u585e\uff1a${row.blocked_reason}\uff1b\u9884\u8ba1\u6062\u590d ${row.expected_recovery_at || '--'}` }) : null,
            row.review_next_action ? h('small', { text: `\u4e0b\u4e00\u6b65\uff1a${row.review_next_action}` }) : null,
          ),
          controls.length ? h('div', { class: 'pr-action-row__controls' }, ...controls) : null,
        ),
      );
    }));
  }

  /** 排期时间轴（对齐 XMind「任务时间节点排期」）：
   *  月复盘按月内周 W1–W5 落位、周复盘按日落位，动作按 planned_at 归位。
   *  数据全部来自动作状态机（actions_planned），不新建任务体系；
   *  点击动作打开既有链路弹窗。
   */
  function renderScheduleTimeline(context) {
    const period = context.period || {};
    const actions = [
      ...(context.actions_planned || []),
      ...(context.actions_blocked || []),
      ...(context.actions_review || []),
    ];
    // 没有动作时不渲染空日历；动作状态区会提供唯一空态。
    if (!actions.length) return null;

    // 周期内的桶：月=月内周，周=按日（口径与后端 _breakdown_block 一致）。
    let buckets = [];
    if (state.mode === 'month') {
      const key = period.key || '';
      const year = Number(key.slice(0, 4));
      const month = Number(key.slice(5, 7));
      if (year && month) {
        const lastDay = new Date(year, month, 0).getDate();
        const firstDow = new Date(year, month - 1, 1).getDay();
        const w1End = Math.min(1 + ((7 - firstDow) % 7), lastDay);
        buckets = [{ label: 'W1', start: `${key}-01`, end: `${key}-${String(w1End).padStart(2, '0')}` }];
        let cur = w1End + 1;
        while (cur <= lastDay) {
          const wEnd = Math.min(cur + 6, lastDay);
          buckets.push({ label: `W${buckets.length + 1}`, start: `${key}-${String(cur).padStart(2, '0')}`, end: `${key}-${String(wEnd).padStart(2, '0')}` });
          cur = wEnd + 1;
        }
      }
    } else {
      const start = period.start || '';
      const end = period.end || '';
      if (start && end) {
        const s = new Date(`${start}T00:00:00`);
        const e = new Date(`${end}T00:00:00`);
        for (let d = new Date(s); d <= e; d.setDate(d.getDate() + 1)) {
          // 本地日期格式化：toISOString 是 UTC，东八区 0-8 点会算成前一天，动作会落错桶。
          const iso = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
          buckets.push({ label: String(Number(iso.slice(8, 10))), start: iso, end: iso });
        }
      }
    }
    if (!buckets.length) return null;

    const byBucket = new Map(buckets.map((b) => [b.label, []]));
    actions.forEach((row) => {
      const planned = row.planned_at || row.executed_at || '';
      const bucket = buckets.find((b) => planned >= b.start && planned <= b.end);
      if (bucket) byBucket.get(bucket.label).push(row);
    });
    // 只保留有动作的周期桶，避免空日期重复占用纵向空间。
    const activeBuckets = buckets.filter((bucket) => (byBucket.get(bucket.label) || []).length);
    if (!activeBuckets.length) return null;
    const timeline = h('div', { class: 'pr-schedule' }, ...activeBuckets.map((b) => {
      const items = byBucket.get(b.label) || [];
      const itemNodes = items.slice(0, 6).map((row) => h('li', null,
        h('button', {
          type: 'button',
          class: 'pr-schedule__item',
          title: `${row.action_type || '动作'} · ${actionStatusLabel(row.status)}`,
          onclick: () => openActionDetails(row),
          text: `${row.product_title || row.product_id}`,
        }),
        h('small', { text: actionStatusLabel(row.status) })));
      return h('div', { class: 'pr-schedule__bucket has-items' },
        h('div', { class: 'pr-schedule__bucket-head' },
          h('span', { class: 'pr-schedule__bucket-label', text: state.mode === 'month' ? b.label : `${b.label}号` }),
          h('small', { text: `${b.start.slice(5)} ~ ${b.end.slice(5)}` })),
        h('ul', { class: 'pr-schedule__items' }, ...itemNodes));
    }));
    return analysisPanel(
      state.mode === 'month' ? '本月任务排期（有动作的周）' : '本周任务排期（有动作的日期）',
      '只显示已有计划日期的动作；点击动作打开执行链路。',
      timeline,
      null,
    );
  }

  function renderExecutionEmpty() {
    return h('div', { class: 'pr-execution-empty' },
      h('p', { class: 'pr-execution-empty__title', text: '当前周期还没有动作' }),
      h('p', { class: 'pr-execution-empty__hint', text: '先在复盘结论的板块数据中确认问题，再生成动作草案并进入执行状态机。' }));
  }

  function renderExecutionAnalysis(context) {
    if (!els.executionAnalysis) return;
    const groups = [
      ['执行中与观察中', '按现有状态机推进执行、观察和重算。', context.actions_planned || [], '当前没有执行中动作。'],
      ['本期待验证', '来自上一周或上一个月的动作，在本期回流结果。', context.actions_to_verify || [], '当前暂无上期待验证动作。'],
      ['待复盘验收', '观察窗口完成后，在这里确认有效性并回流下一步。', context.actions_review || [], '当前没有待复盘动作。'],
      ['阻塞与待处理', '阻塞项需在复盘结论中说明所需资源和解除条件。', context.actions_blocked || [], '当前没有阻塞动作。'],
      ['已完成动作', '只展示已通过复盘验收的动作。', context.actions_done || [], '本期暂无已完成动作。'],
    ];
    const activeGroups = groups.filter(([, , rows]) => rows.length);
    const timeline = renderScheduleTimeline(context);
    const panels = activeGroups.length
      ? activeGroups.map(([title, hint, rows, emptyText]) => analysisPanel(title, hint, renderActionListWithControls(rows), emptyText))
      : [analysisPanel('动作状态', '确认问题后，动作会在这里跟踪执行、观察和验收。', renderExecutionEmpty(), null)];
    els.executionAnalysis.replaceChildren(...(timeline ? [timeline, ...panels] : panels));
  }

  // ------------------------------------------------------ 板块数据抽屉
  // 六段的「板块数据」全量明细收进右侧抽屉，段落内只留一行入口。
  // 背景：拆因工作区撤销后明细并入六段，六段证据合计约 7200px，默认展开会把
  // 写作区推到 12 屏外（docs/PERIOD_REVIEW_REDESIGN_20261002.md 的 P2 数据抽屉）。
  // 非模态（无遮罩）——左侧写作区仍可读，不做焦点陷阱；Esc / 点外部 / 关闭按钮收起。
  const drawerEl = document.querySelector('[data-pr-drawer]');
  let drawerReturnFocus = null;
  const isDrawerOpen = () => Boolean(drawerEl && drawerEl.classList.contains('is-open'));

  function scrollDrawerTo(sectionKey) {
    drawerEl?.querySelector(`[data-pr-drawer-section="${sectionKey}"]`)
      ?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  function openDiagnosisDrawer(sectionKey) {
    if (!drawerEl) return;
    // 已开时只做锚点定位，避免把 returnFocus 覆盖成抽屉内元素。
    if (isDrawerOpen()) {
      if (sectionKey) scrollDrawerTo(sectionKey);
      return;
    }
    drawerReturnFocus = document.activeElement;
    drawerEl.classList.add('is-open');
    document.body.classList.add('pr-drawer-open');
    if (sectionKey) window.setTimeout(() => scrollDrawerTo(sectionKey), 80);
    drawerEl.querySelector('[data-pr-drawer-close]')?.focus({ preventScroll: true });
  }

  function closeDiagnosisDrawer() {
    if (!isDrawerOpen()) return;
    drawerEl.classList.remove('is-open');
    document.body.classList.remove('pr-drawer-open');
    const restore = drawerReturnFocus;
    drawerReturnFocus = null;
    if (restore?.isConnected) restore.focus({ preventScroll: true });
  }

  /** 把六段材料按段渲染进抽屉，顶部生成同序锚点。 */
  function renderDiagnosisDrawer(context) {
    const body = drawerEl?.querySelector('[data-pr-drawer-body]');
    const nav = drawerEl?.querySelector('[data-pr-drawer-nav]');
    if (!body || !nav) return;
    const entries = (state.template || []).map((section, index) => {
      const keys = (section.materials || []).filter((key) => key !== 'metrics' && key !== 'target_path');
      const blocks = keys.map((key) => materialFor(key, context)).filter(Boolean);
      if (!blocks.length) return null;
      const title = section.title || section.key;
      return {
        key: section.key,
        title,
        index,
        node: h('section', { class: 'pr-drawer__section', 'data-pr-drawer-section': section.key },
          h('h3', { class: 'pr-diagnosis__heading', text: title }), ...blocks),
      };
    }).filter(Boolean);
    body.replaceChildren(...entries.map((entry) => entry.node));
    nav.replaceChildren(...entries.map((entry) => h('button', {
      type: 'button',
      class: 'pr-drawer__nav-chip',
      text: `${entry.index + 1} ${String(entry.title).split('（')[0]}`,
      onclick: () => scrollDrawerTo(entry.key),
    })));
  }

  function bindDiagnosisDrawer() {
    if (!drawerEl) return;
    drawerEl.querySelector('[data-pr-drawer-close]')?.addEventListener('click', closeDiagnosisDrawer);
    // Esc：弹窗（字段设置 / 动作 / 趋势）打开时优先让弹窗处理，不抢关闭。
    document.addEventListener('keydown', (event) => {
      if (event.key !== 'Escape' || !isDrawerOpen()) return;
      if (document.querySelector('dialog[open]')) return;
      closeDiagnosisDrawer();
    });
    // 非模态面板没有遮罩，用 document 点击判断「点到了外面」。
    // 排除抽屉自身、弹窗内部（字段设置从抽屉里开出来的）、以及触发按钮（它自己开）。
    document.addEventListener('click', (event) => {
      if (!isDrawerOpen()) return;
      const target = event.target;
      if (!target || typeof target.closest !== 'function') return;
      if (drawerEl.contains(target)) return;
      if (target.closest('dialog[open]')) return;
      if (target.closest('.pr-evidence__open-drawer')) return;
      closeDiagnosisDrawer();
    });
  }

  // 页签已撤：工作区平铺一页，「切换」就是滚动定位到对应区块。
  function activateWorkbench(key, { focus = false } = {}) {
    // 切走货品区时字段设置对话框失去锚点，先收起。
    productColumns.closeProductFieldPopover();
    const panel = document.querySelector(`[data-pr-workbench-panel="${key}"]`);
    if (!panel) return;
    if (key === 'reference' && (!state.matrix || !state.categoryBreakdown)) reloadMatrixPanels();
    panel.scrollIntoView({ behavior: 'smooth', block: 'start' });
    void focus;
  }

  /** 滚动定位到某个结论段（归因线索等从总览直达对应段落）。 */
  function scrollToSection(sectionKey) {
    els.sections?.querySelector(`[data-section-key="${sectionKey}"]`)
      ?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  function renderWorkbench(context, review) {
    renderCommandCenter(context);
    renderExecutionAnalysis(context);
    // 登记 context：字段设置改列后 product-columns 要据此重渲染（refreshProductTables）。
    // 原先这步在被删掉的 renderProductAnalysis 里，删除后无人调用 → 改列不再生效。
    productColumns.rememberContext(context);
    renderSections(state.template, context, review);
    // 抽屉内容与段落同步重建（同一份 context 与列配置），保证「在右侧展开」看到的是最新数据。
    renderDiagnosisDrawer(context);
  }

  function renderKpiGrid(metrics) {
    const grid = h('div', { class: 'pr-kpi-grid' });
    if (!metrics.items.length) {
      grid.append(h('p', { class: 'pr-material__empty', text: '本期暂无指标数据。' }));
      return grid;
    }
    // 核心指标前置（结果 + 流量转化），其余收进「更多指标」：
    // 14 项 KPI 墙会把六段复盘挤到三屏外，复盘页的首要动作是写结论不是看遍指标。
    const CORE_KEYS = ['gsv', 'net_sales', 'visitors', 'conversion', 'buyers', 'aov', 'ad_spend', 'ad_ratio'];
    const core = metrics.items.filter((item) => CORE_KEYS.includes(item.key));
    const rest = metrics.items.filter((item) => !CORE_KEYS.includes(item.key));
    core.forEach((item) => {
      grid.append(h('div', { class: 'pr-kpi' },
        h('div', { class: 'pr-kpi__label', text: item.label }),
        h('div', { class: 'pr-kpi__value', text: formatValue(item.value, item.format) }),
        deltaNode(item),
      ));
    });
    if (rest.length) {
      grid.append(h('details', { class: 'pr-kpi-more' },
        h('summary', { text: `更多指标（${rest.length}）` }),
        h('div', { class: 'pr-kpi-grid pr-kpi-grid--rest' },
          ...rest.map((item) => h('div', { class: 'pr-kpi' },
            h('div', { class: 'pr-kpi__label', text: item.label }),
            h('div', { class: 'pr-kpi__value', text: formatValue(item.value, item.format) }),
            deltaNode(item),
          )))));
    }
    return grid;
  }

  // ------------------------------------------------------------- 素材渲染
  // badges：可选，标题右侧的徽标节点（如「部分口径」）。用于在**数据块标题上**
  // 就地标明口径降级，读者不必先读脚注才知道这个数不能全信。
  function materialBlock(title, bodyNode, emptyText, hint, badges) {
    const titleNode = h('p', { class: 'pr-material__title', text: title });
    (badges || []).filter(Boolean).forEach((badge) => titleNode.append(badge));
    const block = h('div', { class: 'pr-material' }, titleNode);
    if (bodyNode) block.append(bodyNode);
    else if (emptyText) block.append(h('p', { class: 'pr-material__empty', text: emptyText }));
    if (hint) block.append(h('p', { class: 'pr-material__hint', text: hint }));
    return block;
  }

  // ------------------------------------------------- 货品表格（列可配置）
  // 实现已拆至 pages/period-review/product-columns.js（deps 显式注入）：
  // 列定义 / 列开关 / 字段设置浮层的状态与行为都归该模块。
  const productColumns = window.createProductColumns({
    h, productShare, declineRate, safeMetric, openProductDiagnosis, openProductTrend,
    // 货品明细已并入六段（materialFor case 'products'），不再有独立货品工作区。
    // 此前这里直接传 renderProductAnalysis，但该函数已随拆因工作区一起删除，
    // 未定义引用 → ReferenceError 打断整个 IIFE → 六段全部不渲染（2026-10-03 修）。
    // 列变更后重渲染六段即可，语义与原「重渲染货品区」等价。
    renderProductAnalysis: () => { if (state.context) renderSections(state.template, state.context, state.review); },
  });

  // 目标卡与「目标 vs 实际」表已拆至 pages/period-review/target-cards.js：
  // 输入口径换算、达成率配色、即时重算的状态与行为都归该模块。
  const targetCards = window.createTargetCards({ h, formatValue, state, els, onTargetsChanged });

  // 三大指标完成率卡（净销售额/净利润/净费比）已拆至 pages/period-review/metric-cards.js：
  // 口径与复盘设置目标同源，完成率与配色方向沿用后端 _target_rows。
  const metricCards = window.createMetricCards({ h, state });

  // 复盘导出 Markdown 已拆至 pages/period-review/review-export.js：
  // 组装三大指标 + 六段三段式 + 问题单品 + 动作清单，纯前端 Blob 下载。
  const reviewExport = window.createReviewExport({ h, state });

  // 目标差距归因已拆至 pages/period-review/gap-attribution.js：
  // 三因子连环替代分解（流量×转化×客单）+ 归因线索，回答「目标为啥没完成」。
  const gapAttribution = window.createGapAttribution({ h, state, formatValue, scrollToSection });

  // 确定性初稿生成器（pages/period-review/deterministic-draft.js）：
  // 把 context 数据事实组织成六段正文；三因子算术直接复用 gapAttribution.decompose。
  const deterministicDraft = window.createDeterministicDraft({
    formatValue, decompose: gapAttribution.decompose,
  });

  // 目标输入变化时的可见反馈出口：归因摘要里的完成率即时重算。
  // 驾驶舱三卡由外层 renderCommandCenter 整块重建，不在这里重复刷。
  // 目标输入即时联动：target-cards 把输入换算回写 context.target_path，
  // 归因摘要嵌在品类汇总段板块数据里，重渲染段落即刷新完成率。
  function onTargetsChanged() {
    if (!state.context) return;
    renderSections(state.template, state.context, state.review);
    refreshGeneratedDraft();
  }

  // 叶子类目近 3 周对比看板已拆至 pages/period-review/leaf-board.js：
  // 看板自建 #leaf-weekly-board 节点，格式化助手与加载器都归该模块。
  const leafBoard = window.createLeafBoard({ h, state, els, describeRequestError });

  function renderActionListLegacy(rows) {
    if (!rows || !rows.length) return null;
    return h('ul', { class: 'pr-actions-list' }, ...rows.map((row) => h('li', null,
      h('b', { text: `${row.product_id} · ${row.action_type || '动作'}` }),
      ` · ${row.status} · 计划 ${row.planned_at || '--'}`,
      row.executed_at ? ` · 执行 ${row.executed_at}` : '',
      row.purpose_note ? ` · ${row.purpose_note}` : '',
      row.blocked_reason ? ` · 阻塞：${row.blocked_reason}` : '',
    )));
  }

  /** 竞店行展开的日趋势块：逐日 UV / 支付买家两根迷你 SVG 折线（无图表库依赖）。 */
  function rivalTrendBlock(row) {
    const trend = row.daily_trend || [];
    const sparkline = (values, color) => {
      const nums = values.map((v) => (v === null || v === undefined ? null : Number(v)));
      const valid = nums.filter((v) => v !== null);
      if (valid.length < 2) return null;
      const width = 460;
      const height = 60;
      const pad = 6;
      const min = Math.min(...valid);
      const max = Math.max(...valid);
      const span = (max - min) || 1;
      const stepX = (width - pad * 2) / (nums.length - 1);
      const scaleY = (v) => height - pad - ((v - min) / span) * (height - pad * 2);
      const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
      svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
      svg.setAttribute('class', 'pr-trend-svg');
      const polyline = document.createElementNS('http://www.w3.org/2000/svg', 'polyline');
      polyline.setAttribute('points', nums
        .map((v, i) => (v === null ? null : `${pad + i * stepX},${scaleY(v)}`))
        .filter(Boolean).join(' '));
      polyline.setAttribute('fill', 'none');
      polyline.setAttribute('stroke', color);
      polyline.setAttribute('stroke-width', '2');
      svg.append(polyline);
      return svg;
    };
    const block = h('div', { class: 'pr-rival-trend' });
    const uvLine = sparkline(trend.map((d) => d.uv), 'var(--brand, #3b82f6)');
    const buyerLine = sparkline(trend.map((d) => d.buyers), 'var(--success, #16a34a)');
    // 区间标签：min≠max 显示区间；全等（采集快照常见）显示单值，避免「37.5万 ~ 37.5万」误导。
    const rangeLabel = (values, name) => {
      const nums = values.map((v) => Number(v) || 0);
      const min = Math.min(...nums);
      const max = Math.max(...nums);
      return min === max ? `${name}（${formatCompact(min)}，逐日持平）` : `${name}（${formatCompact(min)} ~ ${formatCompact(max)}）`;
    };
    if (uvLine) block.append(h('div', { class: 'pr-rival-trend__item' },
      h('span', { text: rangeLabel(trend.map((d) => d.uv), 'UV') }), uvLine));
    if (buyerLine) block.append(h('div', { class: 'pr-rival-trend__item' },
      h('span', { text: rangeLabel(trend.map((d) => d.buyers), '支付买家') }), buyerLine));
    if (!block.childElementCount) block.append(h('p', { class: 'pr-material__empty', text: '该店本期日数据不足，无法画趋势。' }));
    return block;
  }

  // 蓝海分级 → 标签样式。「待核」是「无法判定」而非结论，用中性色，别当机会色。
  const BLUE_OCEAN_GRADE_KIND = { '高潜蓝海': 'good', '中等': 'info', '供给偏多': 'warning', '待核': 'info' };

  function renderMarket(market) {
    const wrap = h('div', { class: 'pr-materials' });
    if (!market || !market.available) {
      wrap.append(materialBlock('市场批次', null, '尚未导入市场分析批次（市场分析页导入后可自动汇总）。'));
      return wrap;
    }
    const run = market.run || {};
    if (market.run_alignment === 'stale') {
      wrap.append(materialBlock('\u6570\u636e\u72b6\u6001', null, '\u5f53\u524d\u5e02\u573a\u6279\u6b21\u65e9\u4e8e\u590d\u76d8\u5468\u671f\uff0c\u4ec5\u4f5c\u5386\u53f2\u53c2\u8003\uff1b\u7ade\u5e97\u4e0e\u7ade\u54c1\u4ecd\u6309\u590d\u76d8\u533a\u95f4\u6c47\u603b\u3002'));
    }
    const sourceDates = market.source_dates || {};
    const itemSource = sourceDates.sycm_market_item_rank || {};
    const keywordSource = sourceDates.sycm_market_search_rank || {};
    wrap.append(materialBlock('市场批次',
      h('p', { class: 'pr-material__empty', text: itemSource.last_date
        ? `生意参谋日快照 · 覆盖 ${itemSource.first_date || '--'} ~ ${itemSource.last_date || '--'}${run ? ` · 历史批次 ${run.analysis_date || '--'}` : ''}`
        : `${run.source || '市场数据'} · 分析日 ${run.analysis_date || '--'} · 覆盖 ${run.period_start || '--'} ~ ${run.period_end || '--'}` })));
    wrap.append(materialBlock('市场数据状态', h('div', { class: 'pr-target' },
      h('div', { class: 'pr-target__item' }, h('span', { text: '商品榜覆盖' }), h('strong', { text: `${itemSource.sample_days || 0} 天` }), h('small', { text: `${itemSource.first_date || '--'} ~ ${itemSource.last_date || '--'}` })),
      h('div', { class: 'pr-target__item' }, h('span', { text: '搜索词覆盖' }), h('strong', { text: `${keywordSource.sample_days || 0} 天` }), h('small', { text: `${keywordSource.first_date || '--'} ~ ${keywordSource.last_date || '--'}` })),
      h('div', { class: 'pr-target__item' }, h('span', { text: '结论边界' }), h('strong', { text: '趋势/排名' }), h('small', { text: '不含价格、毛利、评价' })),
    )));

    // 商品榜/搜索词两张 6 列监控表并排两列（半栏刚好），其余块保持通栏；
    // 只有任一表有数据才建两列容器，否则退回逐块堆叠。
    const monitorPair = h('div', { class: 'pr-market-pair' });
    let hasMonitor = false;

    if (market.market_signals && market.market_signals.length) {
      const tr = h('tr', null,
        h('th', { text: '类目' }), h('th', { class: 'num', text: '样本天数' }),
        h('th', { class: 'num', text: '平均UV' }), h('th', { class: 'num', text: '平均支付买家' }),
        h('th', { class: 'num', text: 'UV变化' }), h('th', { class: 'num', text: '支付买家变化' }));
      const body = market.market_signals.map((row) => h('tr', null,
        h('td', { text: row.category || '--' }),
        h('td', { class: 'num', text: String(row.sample_days ?? '--') }),
        h('td', { class: 'num', text: formatCompact(row.avg_uv) }),
        h('td', { class: 'num', text: formatCompact(row.avg_pay_buyer_count) }),
        h('td', { class: 'num', text: signedPercent(row.avg_uv_change_rate === null || row.avg_uv_change_rate === undefined ? null : row.avg_uv_change_rate * 100) }),
        h('td', { class: 'num', text: signedPercent(row.avg_pay_buyer_change_rate === null || row.avg_pay_buyer_change_rate === undefined ? null : row.avg_pay_buyer_change_rate * 100) }),
      ));
      monitorPair.append(materialBlock('市场事实：商品榜监控', h('table', { class: 'pr-table' }, h('thead', null, tr), h('tbody', null, ...body))));
      hasMonitor = true;
    }

    if (market.keyword_signals && market.keyword_signals.length) {
      const tr = h('tr', null,
        h('th', { text: '关键词' }), h('th', { class: 'num', text: '平均搜索热度' }),
        h('th', { class: 'num', text: '支付率' }), h('th', { class: 'num', text: '点击率' }),
        h('th', { class: 'num', text: '热度变化' }), h('th', { text: '信号' }));
      const body = market.keyword_signals.slice(0, 12).map((row) => h('tr', null,
        h('td', { text: row.keyword || '--' }),
        h('td', { class: 'num', text: formatCompact(row.avg_search_heat) }),
        h('td', { class: 'num', text: row.avg_pay_rate === null || row.avg_pay_rate === undefined ? '--' : `${(Number(row.avg_pay_rate) * 100).toFixed(2)}%` }),
        h('td', { class: 'num', text: row.avg_click_rate === null || row.avg_click_rate === undefined ? '--' : `${(Number(row.avg_click_rate) * 100).toFixed(2)}%` }),
        h('td', { class: 'num', text: signedPercent(row.search_heat_change_rate === null || row.search_heat_change_rate === undefined ? null : row.search_heat_change_rate * 100) }),
        h('td', null, stateTag(row.status === 'demand_up' ? '需求上升' : row.status === 'demand_down' ? '需求下降' : row.status === 'efficiency_up' ? '支付率改善' : row.status === 'efficiency_down' ? '支付率下降' : '稳定', row.status === 'demand_up' || row.status === 'efficiency_up' ? 'good' : row.status === 'demand_down' || row.status === 'efficiency_down' ? 'warning' : 'info')),
      ));
      monitorPair.append(materialBlock('需求信号：搜索词监控', h('table', { class: 'pr-table' }, h('thead', null, tr), h('tbody', null, ...body))));
      hasMonitor = true;
    }

    if (hasMonitor) {
      wrap.append(monitorPair);
    }

    if (market.decision_hints && market.decision_hints.length) {
      wrap.append(materialBlock('系统观察（不代替经营结论）', h('ul', { class: 'pr-actions-list' }, ...market.decision_hints.map((hint) => h('li', null,
        stateTag(hint.status === 'alert' ? '预警' : '观察', hint.status === 'alert' ? 'warning' : 'info'),
        h('b', { text: ` ${hint.title}` }), `：${hint.detail} · 置信度 ${hint.confidence}`,
      )))));
    }

    if (market.categories && market.categories.length) {
      const tr = h('tr', null,
        h('th', { text: '类目' }), h('th', { class: 'num', text: '买家数' }),
        h('th', { class: 'num', text: '上升' }), h('th', { class: 'num', text: '下降' }),
        h('th', { class: 'num', text: '新进' }), h('th', { class: 'num', text: 'TOP10 集中度' }));
      const body = market.categories.map((row) => h('tr', null,
        h('td', { text: row.category || '--' }),
        h('td', { class: 'num', text: formatCompact(row.total_buyers) }),
        h('td', { class: 'num', text: String(row.trend_up ?? '--') }),
        h('td', { class: 'num', text: String(row.trend_down ?? '--') }),
        h('td', { class: 'num', text: String(row.trend_new ?? '--') }),
        h('td', { class: 'num', text: row.concentration_top10 === null || row.concentration_top10 === undefined ? '--' : `${Number(row.concentration_top10).toFixed(1)}%` }),
      ));
      wrap.append(materialBlock('类目趋势', h('table', { class: 'pr-table' }, h('thead', null, tr), h('tbody', null, ...body))));
    }

    if (market.categories && market.categories.length) {
      const categoryChanges = market.categories
        .filter((row) => row.buyers_change_rate !== null && row.buyers_change_rate !== undefined)
        .map((row) => `${row.category || '--'} ${row.buyers_change_rate > 0 ? '+' : ''}${(row.buyers_change_rate * 100).toFixed(1)}%`)
        .join(' · ');
      if (categoryChanges) wrap.append(materialBlock('\u5e02\u573a\u73af\u6bd4', h('p', { class: 'pr-material__empty', text: categoryChanges })));
    }
    if (market.rivals && market.rivals.length) {
      const tr = h('tr', null, h('th', { text: '竞店' }), h('th', { class: 'num', text: '支付买家' }), h('th', { class: 'num', text: 'UV' }), h('th', { class: 'num', text: '支付率' }), h('th', { class: 'num', text: '支付买家变化' }), h('th', { text: '状态' }), h('th', { text: '日趋势' }), h('th', { text: '深度分析' }));
      const period = (state.context && state.context.period) || {};
      const body = market.rivals.map((row) => {
        const main = h('tr', { class: 'pr-rival-row' },
          h('td', { text: row.shop_name || '--' }),
          h('td', { class: 'num', text: formatCompact(row.pay_buyer_count) }),
          h('td', { class: 'num', text: formatCompact(row.uv) }),
          h('td', { class: 'num', text: row.pay_rate === null || row.pay_rate === undefined ? '--' : `${(row.pay_rate * 100).toFixed(2)}%` }),
          h('td', { class: 'num', text: row.pay_buyer_change_rate === null || row.pay_buyer_change_rate === undefined ? '--' : `${row.pay_buyer_change_rate > 0 ? '+' : ''}${(row.pay_buyer_change_rate * 100).toFixed(1)}%` }),
          h('td', null, stateTag(row.status === 'rising' ? '增长' : row.status === 'falling' ? '下滑' : row.status === 'insufficient_coverage' ? '覆盖不足' : '稳定', row.status === 'rising' ? 'warning' : row.status === 'falling' ? 'good' : 'info')),
          // 日趋势展开：该店本期逐日 UV/买家迷你折线（数据源无爆品/趋势品映射时的
          // 可用替代），点击行展开/收起。
          h('td', null, (row.daily_trend || []).length >= 2
            ? h('button', {
              type: 'button',
              class: 'pr-anchor-link',
              text: `${row.daily_trend.length} 天 ↕`,
              onclick: (event) => {
                // tr[hidden] 在部分表格布局下取消后高度仍为 0，改用 class 切换显示。
                const detailRow = event.target.closest('tr').nextElementSibling;
                if (detailRow && detailRow.classList.contains('pr-rival-detail')) {
                  detailRow.classList.toggle('is-collapsed');
                }
              },
            })
            : h('span', { text: '--' })),
          // 深链到竞店竞品专页（带复盘区间日期），复盘页只做摘要，深度分析不重建。
          h('td', null, h('a', {
            class: 'pr-anchor-link',
            href: `/rival-analysis?start=${period.start || ''}&end=${period.end || ''}`,
            text: '查看 →',
          })),
        );
        const detail = (row.daily_trend || []).length >= 2
          ? h('tr', { class: 'pr-rival-detail is-collapsed' },
            h('td', { colspan: '8' }, rivalTrendBlock(row)))
          : null;
        return detail ? [main, detail] : [main];
      });
      wrap.append(materialBlock('竞店动态', h('table', { class: 'pr-table' }, h('thead', null, tr), h('tbody', null, ...body.flat()))));
    }
    if (market.competitor_items && market.competitor_items.length) {
      const tr = h('tr', null, h('th', { text: '竞品商品' }), h('th', { class: 'num', text: '市场排名' }), h('th', { class: 'num', text: '排名变化' }), h('th', { class: 'num', text: '支付买家' }), h('th', { class: 'num', text: 'UV' }), h('th', { class: 'num', text: '支付买家变化' }), h('th', { text: '状态' }));
      const body = market.competitor_items.map((row) => h('tr', null,
        h('td', { text: `${row.priority || (row.comparison_basis ? 'P2' : '待验证')} · ${row.title || row.item_id || '--'}` }),
        h('td', { class: 'num', text: row.market_rank === null || row.market_rank === undefined ? '--' : `第${row.market_rank}名` }),
        h('td', { class: 'num', text: row.market_rank_change === null || row.market_rank_change === undefined ? '--' : `${row.market_rank_change > 0 ? '+' : ''}${row.market_rank_change}` }),
        h('td', { class: 'num', text: formatCompact(row.pay_buyer_count) }),
        h('td', { class: 'num', text: formatCompact(row.uv) }),
        h('td', { class: 'num', text: row.pay_buyer_change_rate === null || row.pay_buyer_change_rate === undefined ? '--' : `${row.pay_buyer_change_rate > 0 ? '+' : ''}${(row.pay_buyer_change_rate * 100).toFixed(1)}%` }),
        h('td', null, stateTag(row.status === 'rising' ? '上升' : row.status === 'falling' ? '下滑' : row.status === 'insufficient_coverage' ? '覆盖不足' : '稳定', row.status === 'rising' ? 'warning' : row.status === 'falling' ? 'good' : 'info')),
      ));
      wrap.append(materialBlock('竞品商品对标', h('table', { class: 'pr-table' }, h('thead', null, tr), h('tbody', null, ...body))));
    }
    if (market.competitor_items && market.competitor_items.length) {
      const priorityCounts = market.competitor_items.reduce((counts, row) => {
        const priority = row.priority || (row.comparison_basis ? 'P2' : '待验证');
        counts[priority] = (counts[priority] || 0) + 1;
        return counts;
      }, {});
      const priorityText = Object.entries(priorityCounts).map(([key, value]) => `${key} ${value}项`).join(' · ');
      wrap.append(materialBlock('\u7ade\u54c1\u5dee\u8ddd\u5206\u7ea7', h('p', { class: 'pr-material__empty', text: priorityText })));
    }
    // ---- XMind「市场监控-行业」：8大归类 / 词根需求 / 趋势节点 / 趋势市场 / 蓝海市场 ----
    // 口径与「市场排行」页共用同一后端算法（services/market_monitor_service），
    // 这里只负责呈现，绝不重算 —— 否则两页会漂移出两套结论。
    const insights = market.keyword_insights || {};
    if (insights.categories && insights.categories.length) {
      const tr = h('tr', null,
        h('th', { text: '归类' }), h('th', { class: 'num', text: '词数' }),
        h('th', { class: 'num', text: '搜索热度' }), h('th', { class: 'num', text: '热度占比' }),
        h('th', { text: 'TOP 词根' }));
      const body = insights.categories.map((row) => h('tr', null,
        h('td', { text: row.label || '--' }),
        h('td', { class: 'num', text: String(row.keyword_count ?? '--') }),
        h('td', { class: 'num', text: formatCompact(row.search_heat) }),
        h('td', { class: 'num', text: row.heat_share === null || row.heat_share === undefined ? '--' : `${(row.heat_share * 100).toFixed(1)}%` }),
        h('td', { text: (row.top_keywords || []).map((item) => item.keyword).join('、') || '--' }),
      ));
      wrap.append(materialBlock('关键词洞察 · 8 大归类',
        h('table', { class: 'pr-table' }, h('thead', null, tr), h('tbody', null, ...body)),
        null,
        insights.window
          ? `窗口 ${insights.window.start} ~ ${insights.window.end}（${insights.window.day_count} 天）· 共 ${insights.unique_keyword_count || 0} 个搜索词；按规则词典先命中先归类，未命中记「其他」。`
          : null));
    }

    const trendNodes = insights.trend_nodes || {};
    if ((trendNodes.rising || []).length || (trendNodes.cooling || []).length) {
      const nodeRows = [];
      (trendNodes.rising || []).slice(0, 6).forEach((row) => nodeRows.push(['起势', row]));
      (trendNodes.cooling || []).slice(0, 6).forEach((row) => nodeRows.push(['退势', row]));
      const tr = h('tr', null, h('th', { text: '方向' }), h('th', { text: '搜索词' }), h('th', { text: '归类' }),
        h('th', { class: 'num', text: '近 7 天热度' }), h('th', { class: 'num', text: '基线日均' }), h('th', { class: 'num', text: '增速' }));
      const body = nodeRows.map(([direction, row]) => h('tr', null,
        h('td', null, stateTag(direction, direction === '起势' ? 'good' : 'warning')),
        h('td', { text: row.keyword || '--' }),
        h('td', { text: row.category_label || '--' }),
        h('td', { class: 'num', text: formatCompact(row.recent_heat) }),
        h('td', { class: 'num', text: formatCompact(row.baseline_heat) }),
        h('td', { class: 'num', text: signedPercent(row.growth === null || row.growth === undefined ? null : row.growth * 100) }),
      ));
      const threshold = Number(trendNodes.threshold ?? 0.5) * 100;
      wrap.append(materialBlock('趋势节点分析',
        h('table', { class: 'pr-table' }, h('thead', null, tr), h('tbody', null, ...body)),
        null,
        `近 7 天日均热度 vs 前置基线（至多 23 天），增速 ≥ ${threshold.toFixed(0)}% 判起势 / ≤ -${threshold.toFixed(0)}% 判退势。`));
    } else if (market.grading && market.grading.trend_node_available === false) {
      wrap.append(materialBlock('趋势节点分析', null, '当前基线数据不足（市场表覆盖天数不够「近 7 天 + 前置窗口」两段），起势 / 退势不可判。'));
    }

    const supply = market.blue_ocean_supply || {};
    if (supply.words && supply.words.length) {
      const tr = h('tr', null, h('th', { text: '词根' }), h('th', { text: '代表搜索词' }),
        h('th', { class: 'num', text: '日均热度' }), h('th', { class: 'num', text: '在榜覆盖' }),
        h('th', { class: 'num', text: '每万覆盖' }), h('th', { text: '分级' }));
      const body = supply.words.map((row) => h('tr', null,
        h('td', { text: row.keyword || '--' }),
        h('td', { text: row.keyword_full || '--' }),
        h('td', { class: 'num', text: formatCompact(row.search_heat) }),
        h('td', { class: 'num', text: `${row.cover_count ?? '--'} 品` }),
        h('td', { class: 'num', text: row.cover_per_10k === null || row.cover_per_10k === undefined ? '--' : String(row.cover_per_10k) }),
        h('td', null, stateTag(row.grade || '--', BLUE_OCEAN_GRADE_KIND[row.grade] || 'info')),
      ));
      const hintParts = [];
      if (supply.word_scope) hintParts.push(`${supply.word_scope}；`);
      hintParts.push('每万覆盖 = 在榜覆盖 ÷ (日均热度 / 万)：<5 高潜蓝海、5-10 中等、>10 供给偏多。');
      if (supply.pending_count) hintParts.push(`覆盖为 0 的 ${supply.pending_count} 个词根记「待核」—— 0 不代表供给稀缺，也可能只是词根与标题用词不一致，需人工核。`);
      wrap.append(materialBlock('蓝海市场 · 低供给词根',
        h('table', { class: 'pr-table' }, h('thead', null, tr), h('tbody', null, ...body)),
        null, hintParts.join('')));
    }

    const trendItems = market.trend_items || {};
    if ((trendItems.rising || []).length || (trendItems.new_items || []).length) {
      const itemRows = [];
      (trendItems.rising || []).slice(0, 6).forEach((row) => itemRows.push(['上升', row]));
      (trendItems.new_items || []).slice(0, 6).forEach((row) => itemRows.push(['新进榜', row]));
      const tr = h('tr', null, h('th', { text: '类型' }), h('th', { text: '商品' }), h('th', { text: '店铺' }),
        h('th', { class: 'num', text: '排名变化' }), h('th', { class: 'num', text: 'UV' }), h('th', { class: 'num', text: '支付买家' }));
      const body = itemRows.map(([kind, row]) => h('tr', null,
        h('td', null, stateTag(kind, kind === '上升' ? 'good' : 'info')),
        h('td', { text: row.title || row.item_id || '--' }),
        h('td', { text: row.shop_name || '--' }),
        h('td', { class: 'num', text: kind === '新进榜' ? `第 ${row.rank ?? '--'} 名` : `${row.first_rank} → ${row.last_rank}` }),
        h('td', { class: 'num', text: formatCompact(row.uv) }),
        h('td', { class: 'num', text: formatCompact(row.pay_buyer_count) }),
      ));
      const window = trendItems.window || {};
      wrap.append(materialBlock('商品排行 · 趋势市场',
        h('table', { class: 'pr-table' }, h('thead', null, tr), h('tbody', null, ...body)),
        null,
        `窗口 ${window.start || '--'} ~ ${window.end || '--'}（${window.day_count || 0} 天）首尾排名对比：上升 ${trendItems.rising_total || 0} 个 / 新进榜 ${trendItems.new_total || 0} 个（在榜 ${trendItems.item_count || 0} 个商品）。`));
    }

    const moves = market.rival_moves || {};
    if (moves.shops && moves.shops.length) {
      const tr = h('tr', null, h('th', { text: '竞店' }), h('th', { class: 'num', text: '在榜商品' }),
        h('th', { class: 'num', text: '上升' }), h('th', { class: 'num', text: '下降' }),
        h('th', { class: 'num', text: '新进榜' }), h('th', { class: 'num', text: '退出' }),
        h('th', { text: '变动最大' }));
      const body = moves.shops.map((row) => h('tr', null,
        h('td', { text: row.shop_name || '--' }),
        h('td', { class: 'num', text: String(row.item_count ?? '--') }),
        h('td', { class: 'num', text: String(row.rising_count ?? '--') }),
        h('td', { class: 'num', text: String(row.falling_count ?? '--') }),
        h('td', { class: 'num', text: String(row.new_count ?? '--') }),
        h('td', { class: 'num', text: String(row.exit_count ?? '--') }),
        h('td', { text: (row.movers || []).slice(0, 2).map((item) => `${item.title}(${item.rank_change > 0 ? '+' : ''}${item.rank_change})`).join('；') || '--' }),
      ));
      wrap.append(materialBlock('竞店爆品排名变化',
        h('table', { class: 'pr-table' }, h('thead', null, tr), h('tbody', null, ...body)),
        null,
        `窗口首尾排名对比；全市场共 ${moves.shop_count || 0} 家在榜，按变动活跃度取前 ${moves.shops.length} 家。`));
    }

    const grading = market.grading || {};
    if (grading.limitations && grading.limitations.length) {
      wrap.append(materialBlock('市场分级口径边界', h('ul', { class: 'pr-actions-list' },
        ...grading.limitations.map((text) => h('li', null, stateTag('口径', 'info'), h('span', { text: ` ${text}` }))))));
    }

    if (market.missing_inputs && market.missing_inputs.length) {
      wrap.append(materialBlock('数据状态', h('p', { class: 'pr-material__empty', text: `待验证：${market.missing_inputs.join('、')}` })));
    }
    return wrap;
  }

  function renderAds(ads) {
    if (!ads || !ads.current) return null;
    const items = [];
    const cmp = compareShortLabel();
    const push = (label, value) => items.push(h('div', { class: 'pr-target__item' }, h('span', { text: label }), h('strong', { text: value })));
    push('推广花费', formatValue(ads.current.ad_spend, 'money'));
    push('投产比', formatValue(ads.current.roi, 'decimal'));
    // 汇总层直接 ROI（XMind「广告-汇总：增加直接 ROI」）：直接成交 ÷ 花费，同源口径。
    push('直接投产', formatValue(ads.direct_roi, 'decimal'));
    push('费比', formatValue(ads.current.ad_ratio, 'percent'));
    if (cmp && ads.delta && ads.delta.ad_spend_change !== undefined) push(`${cmp}花费变化`, `${ads.delta.ad_spend_change > 0 ? '+' : ''}${ads.delta.ad_spend_change}%`);
    if (cmp && ads.delta && ads.delta.direct_roi_delta !== undefined) push(`${cmp}直接投产变化`, `${ads.delta.direct_roi_delta > 0 ? '+' : ''}${ads.delta.direct_roi_delta}`);
    if (cmp && ads.delta && ads.delta.ad_ratio_delta_pt !== undefined) push(`${cmp}费比变化`, `${ads.delta.ad_ratio_delta_pt > 0 ? '+' : ''}${ads.delta.ad_ratio_delta_pt}pt`);
    const directRoi = ads.direct_roi ?? ads.current.direct_roi;
    const adRatioDelta = ads.delta && ads.delta.ad_ratio_delta_pt;
    let decisionTone = 'neutral';
    let decisionTitle = '先验证再调整预算';
    let decisionDetail = '当前推广效率数据不足，先补齐渠道或单品归因。';
    if (directRoi !== null && directRoi !== undefined && Number.isFinite(Number(directRoi))) {
      if (Number(directRoi) < 1) {
        decisionTone = 'danger';
        decisionTitle = '建议优先降费 / 收缩低效投放';
        decisionDetail = `直接投产 ${formatValue(directRoi, 'decimal')}，先检查低效计划与高费比单品；预算调整需结合库存和毛利确认。`;
      } else if (Number(directRoi) >= 2 && !(Number(adRatioDelta) > 0.03)) {
        decisionTone = 'good';
        decisionTitle = '可从高效计划中小步放量';
        decisionDetail = `直接投产 ${formatValue(directRoi, 'decimal')}，建议优先放量高直接投产计划，观察转化与费比变化。`;
      } else {
        decisionTone = 'warning';
        decisionTitle = '保持投放，先做结构优化';
        decisionDetail = `直接投产 ${formatValue(directRoi, 'decimal')}${adRatioDelta !== undefined ? `，费比变化 ${Number(adRatioDelta) > 0 ? '+' : ''}${Number(adRatioDelta).toFixed(2)}pt` : ''}，先优化计划结构再扩预算。`;
      }
    }
    const blocks = [
      materialBlock('广告本期', h('div', { class: 'pr-target' }, ...items)),
      materialBlock('投放判断', h('div', { class: `pr-ad-decision is-${decisionTone}` },
        h('strong', { text: decisionTitle }), h('p', { text: decisionDetail }))),
    ];
    // 三渠道推广成交金额合计（XMind「推广成交金额增加三渠道金额」）。
    const channelTotals = ads.channel_totals;
    const scopeMissing = channelTotals && (channelTotals.missing_inputs || []).includes('promotion_category_scope');
    const channelPartial = channelTotals && channelTotals.partial;
    if (scopeMissing) {
      blocks.push(materialBlock('推广成交金额 · 渠道拆分', null,
        '渠道数据来自计划粒度，不带商品映射，无法按当前品类过滤；切回「全部品类」可查看全店渠道拆分。'));
    } else if (channelTotals && channelTotals.groups && channelTotals.groups.length) {
      const shareText = (value) => (value === null || value === undefined ? '--' : `${(value * 100).toFixed(1)}%`);
      // 指标列对齐 XMind「渠道拆解」：花费占比/投产/直接投产/加购/拉新/新客占比。
      const cols = [
        ['spend_share', '花费占比', (group) => shareText(group.spend_share)],
        ['attributed_payment', '推广成交金额', (group) => formatValue(group.attributed_payment, 'money')],
        ['payment_share', '成交占比', (group) => shareText(group.payment_share)],
        ['roi', 'ROI', (group) => formatValue(group.roi, 'decimal')],
        ['direct_roi', '直接投产', (group) => formatValue(group.direct_roi, 'decimal')],
        ['cart_rate', '加购率', (group) => formatValue(group.cart_rate, 'percent')],
        ['cart_cost', '加购成本', (group) => formatValue(group.cart_cost, 'money')],
        ['new_cost', '拉新成本', (group) => formatValue(group.new_cost, 'money')],
        ['new_buyer_share', '新客成交占比', (group) => shareText(group.new_buyer_share)],
      ];
      const table = h('div', { class: 'pr-breakdown-table-wrap' }, h('table', { class: 'pr-table pr-breakdown-table' },
        h('thead', null, h('tr', null,
          h('th', { text: '渠道' }),
          h('th', { class: 'num', text: '花费' }),
          ...cols.map(([, label]) => h('th', { class: 'num', text: label })),
        )),
        h('tbody', null, ...channelTotals.groups.map((group) => h('tr', null,
          h('td', { text: group.name }),
          h('td', { class: 'num', text: formatValue(group.ad_spend, 'money') }),
          ...cols.map(([, , render]) => h('td', { class: 'num', text: render(group) })),
        )))));
      // 按品类口径的全站推广只含「计划只绑 1 个商品」的精确归因部分（多商品计划无
      // 商品级明细）→ 成交占比不适用，必须说明，别让「--」被当成 0。
      const sourceNote = channelPartial
        ? `按品类口径，覆盖 ${channelTotals.groups.map((g) => g.name).join(' / ')}；全站推广仅含「计划只绑 1 个商品」的精确归因部分，成交占比不适用（切「全部品类」看全店口径）。`
        : channelTotals.source === 'campaign_month'
          ? '渠道行来自月度汇总（该周期没有日粒度渠道数据）。'
          : `渠道行覆盖 ${channelTotals.sample_days} 天日粒度数据。`;
      blocks.push(materialBlock('推广成交金额 · 渠道拆分', h('div', null, table,
        h('p', { class: 'pr-material__empty', text: sourceNote }))));
    }
    return h('div', { class: 'pr-materials' }, ...blocks);
  }

  /** 周月互汇素材块：月复盘显示本月各周结论，周复盘显示上月月复盘根因参考。
   *  每期收全部有内容的段落（不只品类汇总），条目头 = 周期跳转 + 状态徽章 + 元信息分行。
   */
  function renderLinkedSummaries(linked) {
    if (!linked || !linked.kind || linked.kind === 'none') return null;
    const wrap = h('div', { class: 'pr-materials' });
    const title = linked.kind === 'weekly' ? '本月各周复盘结论（自动汇入）' : '上月月复盘根因（对照参考）';
    const items = linked.items || [];
    if (!items.length) {
      wrap.append(materialBlock(title, null, linked.missing_hint || '暂无关联周期复盘。'));
      return wrap;
    }
    // 段落短标题：去「本月/本周」前缀和括号说明，列表里够认即可。
    const shortTitle = (key) => {
      const t = (state.template.find((s) => s.key === key) || {}).title || key;
      return t.replace(/^(本月|本周)/, '').split('（')[0];
    };
    const body = h('ul', { class: 'pr-actions-list pr-linked-list' }, ...items.map((item) => {
      const sections = Array.isArray(item.sections) && item.sections.length
        ? item.sections
        : (item.analysis ? [{ key: 'category_summary', text: item.analysis }] : []);
      return h('li', { class: 'pr-linked-item' },
        h('div', { class: 'pr-linked-item__head' },
          h('button', {
            type: 'button',
            class: 'pr-anchor-link',
            onclick: () => {
              const isWeek = /W\d+$/.test(item.period_key);
              setMode(isWeek ? 'week' : 'month');
              if (!isWeek) {
                stateBanner(`该复盘属于 ${item.period_key}，请在顶栏「统计时间」切到对应月份查看。`, 'insufficient-data');
              }
              window.location.search = `?period_type=${isWeek ? 'week' : 'month'}&period_key=${encodeURIComponent(item.period_key)}`;
            },
            text: `${item.period_key} →`,
          }),
          stateTag(item.status === 'final' ? '已定稿' : '草稿', item.status === 'final' ? 'good' : 'info'),
          h('small', { class: 'pr-linked-item__meta', text: `${item.reviewer || '--'} · ${item.updated_at || '--'}` })),
        sections.length
          ? h('div', { class: 'pr-linked-item__body' }, ...sections.map((s) => h('div', { class: 'pr-linked-item__section' },
            h('b', { text: shortTitle(s.key) }),
            h('p', { text: s.text }))))
          : h('small', { class: 'pr-linked-item__empty', text: '该期已保存但还没有填写任何段落内容。' }),
      );
    }));
    wrap.append(materialBlock(title, body, null));
    return wrap;
  }

  // 广告单品「渠道×商品」明细子表（有数据时才渲染，无数据整列不出现）。
  // 渠道明细子表。sources 标明每组数据的来源，便于审计（尤其全站推广靠计划精确归因）：
  // creative=创意级事实；campaign_exact=计划→商品 1:1 精确归因；product_grain=商品级历史行。
  const CHANNEL_SOURCE_LABELS = {
    creative: '创意级',
    campaign_exact: '计划精确归因',
    product_grain: '商品级历史',
    mixed: '混合来源',
  };

  function channelsTable(channels, sources) {
    const groups = Object.keys(channels || {});
    if (!groups.length) return h('span', { class: 'pr-material__empty', text: '无渠道明细' });
    const cols = [
      ['ad_spend', '花费', 'money'],
      ['attributed_payment', '成交', 'money'],
      ['ad_ratio', '费比', 'percent'],
      ['roi', '总投产', 'decimal'],
      ['direct_roi', '直接投产', 'decimal'],
      ['cart_cost', '加购成本', 'money'],
      ['new_cost', '拉新成本', 'money'],
      ['cart_rate', '加购率', 'percent'],
    ];
    return h('table', { class: 'pr-table' },
      h('thead', null, h('tr', null, h('th', { text: '渠道' }),
        ...cols.map(([, label]) => h('th', { class: 'num', text: label })),
        h('th', { text: '来源' }))),
      h('tbody', null, ...groups.map((name) => {
        const totals = channels[name] || {};
        const source = (sources || {})[name];
        return h('tr', null, h('td', { text: name }),
          ...cols.map(([key, , format]) => h('td', { class: 'num', text: safeMetric(totals[key], format) })),
          h('td', { text: CHANNEL_SOURCE_LABELS[source] || '--' }));
      })));
  }

  function materialFor(key, context) {
    switch (key) {
      // —— 拆因明细并入结论段（板块数据 = 完整明细，不再另设拆因工作区）：
      // 品类汇总段看目标差距归因 + 流量来源；货品/广告/市场段各嵌完整明细。
      case 'gap_attribution': {
        if (!gapAttribution) return null;
        return materialBlock('目标差距归因（流量 × 转化 × 净销售客单）', gapAttribution.buildBody(context), null);
      }
      case 'traffic': {
        const traffic = context.dimensions?.traffic || {};
        const covered = `流量覆盖 ${traffic.sample_days || 0}/${traffic.period_days || '--'} 天`;
        return materialBlock('流量来源拆解', trafficTable(traffic), '暂无流量来源数据。', covered);
      }
      case 'products': {
        const products = context.products || {};
        const compare = context.compare || {};
        const comparisonAvailable = compare.mode !== 'none' && compare.available !== false;
        const comparableProblemItems = comparisonAvailable
          ? (products.problem_items || [])
          : (products.problem_items || []).filter((row) => {
            const sources = Array.isArray(row.problem_sources) ? row.problem_sources : [];
            return sources.some((source) => source !== '下滑榜');
          });
        const declineItems = comparisonAvailable ? (products.decline || []) : [];
        const board = productColumns.productBoardPanel;
        const wrap = h('div', { class: 'pr-materials' });
        wrap.append(goodsSummaryPanel(products.summary, context.profit_structure) || materialBlock('货品汇总', null, '本期暂无货品数据。'));
        wrap.append(problemItemsPanel(comparableProblemItems));
        wrap.append(board('净销售额 TOP10', '按本期净销售额排序，先识别需要保住的核心商品。', products.top, 'top', '本期没有正向销售商品。'));
        wrap.append(board('下滑商品 TOP10', comparisonAvailable ? '按相对对比周期销售额变化排序，作为异常诊断入口。' : '当前未选择对比周期，不展示下滑判断。', declineItems, 'decline', '缺少可比周期数据。'));
        wrap.append(h('details', { class: 'pr-analysis-more' },
          h('summary', { class: 'pr-analysis-more__summary' },
            h('span', { text: '其他货品榜' }),
            h('small', { text: '付费、盈利、亏损、新品' })),
          h('div', { class: 'pr-analysis-more__body' },
            board('付费单品 TOP10', '按推广花费排序。', products.paid, 'paid', '本期没有推广花费记录。'),
            board('盈利 TOP10', '按经营利润排序。', products.profit, 'profit', '本期没有正利润商品。'),
            board('亏损 TOP10', '按经营利润倒序，优先排查亏损原因。', products.loss, 'loss', '本期没有亏损商品。'),
            board('新品 · 净销售额 TOP10', '最近 60 天上架商品按净销售额排序。', products.new, 'new', '最近 60 天上架的商品暂无销售。'),
            board('新品 · 付费 TOP10', '最近 60 天上架商品按推广花费排序。', products.new_paid, 'new_paid', '最近 60 天上架的商品暂无推广花费。'))));
        return wrap;
      }
      case 'promotion_channels': {
        const dimensions = context.dimensions || {};
        const promotion = dimensions.promotion || {};
        const channelView = promotion.channels || {};
        const campaignView = promotion.campaigns || {};
        const promotionHint = (view, grainName) => view.partial
          ? '按品类口径聚合，覆盖有商品映射的渠道（关键词/人群等）；全站推广仅「计划只绑 1 个商品」的计划可精确归因，切「全部品类」可看全店口径。'
          : view.missing_inputs?.includes('promotion_category_scope')
            ? `当前推广数据没有商品映射，无法按所选类目筛选${grainName}，避免混入全店数据。`
            : `按 ${view.grain || grainName} 粒度聚合；缺少数据时保持为空，不补 0。`;
        const wrap = h('div', { class: 'pr-materials' });
        wrap.append(materialBlock('推广效率（本期投入与投产变化）', renderAds(context.ads), '暂无推广数据。'));
        wrap.append(materialBlock('推广渠道拆解',
          dimensionTable(channelView.items, 'channel'), '暂无可按当前口径使用的渠道推广数据。', promotionHint(channelView, 'channel')));
        wrap.append(materialBlock('推广计划拆解',
          dimensionTable(campaignView.items, 'campaign'), '暂无可按当前口径使用的计划推广数据。',
          campaignView.comparison_available === false
            ? '本期有计划数据，但对比期缺少同粒度数据，暂不展示环比。'
            : promotionHint(campaignView, 'campaign')));
        // 计划 → 商品归因：计划级花费 + 归因方式（精确 / 多商品不拆分）。
        // 这是商品级「全站推广」的唯一来源（creative 表不含该场景）。
        const attributionBlock = campaignAttributionTable(context.campaign_attribution);
        if (attributionBlock) wrap.append(attributionBlock);
        return wrap;
      }
      case 'market':
        return renderMarket(context.market);
      case 'promotion_items': {
        const block = context.promotion_items || {};
        const items = block.items || [];
        if (!items.length) return materialBlock('广告单品 TOP20 消耗', null, '本期没有商品级推广数据。');
        // 列对齐 XMind「广告-单品」：花费 / 费比 / 总投产 / 直接投产 / 加购成本 / 拉新成本 / 加购率。
        const cols = [
          ['ad_spend', '花费', 'money'],
          ['ad_ratio', '费比', 'percent'],
          ['roi', '总投产', 'decimal'],
          ['direct_roi', '直接投产', 'decimal'],
          ['cart_cost', '加购成本', 'money'],
          ['new_cost', '拉新成本', 'money'],
          ['cart_rate', '加购率', 'percent'],
        ];
        const hasChannels = items.some((item) => item.channels && Object.keys(item.channels).length);
        const head = h('tr', null,
          h('th', { text: '商品' }),
          ...cols.map(([, label]) => h('th', { class: 'num', text: label })),
          hasChannels ? h('th', { text: '渠道' }) : null);
        const rows = items.slice(0, 20).map((item) => {
          const totals = item.totals || {};
          const name = item.title || item.product_id;
          const titleCell = h('td', { class: 'pr-table__title', title: name },
            item.image_url ? h('img', {
              src: item.image_url,
              alt: '',
              loading: 'lazy',
              onerror: (event) => { event.currentTarget.hidden = true; },
            }) : null,
            h('span', { class: 'pr-table__title-text', text: name }));
          const main = h('tr', null,
            titleCell,
            ...cols.map(([key, , format]) => h('td', { class: 'num', text: safeMetric(totals[key], format) })),
            hasChannels
              ? h('td', null, item.channels && Object.keys(item.channels).length
                ? h('button', {
                  type: 'button', class: 'pr-anchor-link', text: '展开 ↕',
                  onclick: (event) => {
                    const detail = event.target.closest('tr').nextElementSibling;
                    if (detail && detail.classList.contains('pr-promo-item__channels')) {
                      detail.classList.toggle('is-collapsed');
                    }
                  },
                })
                : h('span', { text: '--' }))
              : null);
          if (!hasChannels) return [main];
          return [main, h('tr', { class: 'pr-promo-item__channels is-collapsed' },
            h('td', { colspan: String(cols.length + 2) }, channelsTable(item.channels, item.channel_sources)))];
        });
        // 渠道明细是部分口径（全站推广无商品级明细），必须显式提示，别让人把渠道加总当 100%。
        const hint = block.channels_note
          || ((block.missing_inputs || []).includes('promotion_product_channel_scope')
            ? '商品×渠道明细尚未接入，此处暂为商品合计口径。'
            : null);
        return materialBlock('广告单品 TOP20 消耗',
          h('div', { class: 'pr-table-wrap' },
            h('table', { class: 'pr-table' }, h('thead', null, head), h('tbody', null, ...rows.flat()))),
          null, hint);
      }
      case 'actions_done':
        return materialBlock('本期已完成动作（来自动作状态机）', renderActionListLegacy(context.actions_done), '本期没有已完成的运营动作。');
      case 'actions_planned':
        return materialBlock('待执行 / 执行中动作', renderActionListLegacy(context.actions_planned), '当前没有待执行动作。');
      case 'actions_blocked':
        return materialBlock('阻塞中的动作', renderActionListLegacy(context.actions_blocked), '当前没有阻塞动作。');
      case 'alerts':
        return materialBlock('告警', context.alerts && context.alerts.length
          ? h('ul', { class: 'pr-list' }, ...context.alerts.map((row) => h('li', null,
            h('strong', { text: `${row.alert_date || ''} ${row.title || row.alert_type || '告警'}` }),
            row.detail ? ` · ${row.detail}` : '')))
          : null, '当前没有未处理告警。');
      case 'anomalies':
        return materialBlock('异常检测', context.anomalies && context.anomalies.length
          ? h('div', { class: 'pr-chips' }, ...context.anomalies.map((row) => h('span', {
            class: `pr-chip is-${row.level || 'info'}`,
            text: `${row.label}：${row.detail}`,
          })))
          : null, '本期未检测到明显异常。');
      case 'metrics':
        return materialBlock('本期核心指标', renderKpiGrid(context.metrics || { items: [] }));
      case 'breakdown':
        return materialBlock(
          context.breakdown && context.breakdown.grain === 'week' ? '月内分周指标' : '期内按日指标',
          breakdownTable(context.breakdown),
        );
      case 'linked_summaries':
        return renderLinkedSummaries(context.linked_summaries);
      default:
        return null;
    }
  }

  // --------------------------------------------------------------- 段落渲染
  // 段落草稿防丢：输入即暂存 localStorage（按周期类型+周期键+段落 key），
  // 切周期/误刷新后恢复；保存成功后清除，避免已保存内容盖住新编辑。
  const SECTION_DRAFT_KEY = 'dashboard.periodReviewSectionDrafts';

  function sectionDraftId() {
    return `${state.mode}:${currentPeriod()}`;
  }

  function readSectionDrafts() {
    try {
      const stored = JSON.parse(localStorage.getItem(SECTION_DRAFT_KEY) || '{}');
      return stored && typeof stored === 'object' ? stored : {};
    } catch (_) { return {}; }
  }

  function readSectionDraft(sectionKey) {
    return (readSectionDrafts()[sectionDraftId()] || {})[sectionKey] || '';
  }

  function storeSectionDraft(sectionKey, text) {
    try {
      const all = readSectionDrafts();
      const periodDrafts = all[sectionDraftId()] || {};
      if (text) periodDrafts[sectionKey] = text;
      else delete periodDrafts[sectionKey];
      if (Object.keys(periodDrafts).length) all[sectionDraftId()] = periodDrafts;
      else delete all[sectionDraftId()];
      // 容量保护：最多留 40 个周期的草稿，超出丢最旧的。
      const ids = Object.keys(all);
      if (ids.length > 40) ids.sort().slice(0, ids.length - 40).forEach((id) => delete all[id]);
      localStorage.setItem(SECTION_DRAFT_KEY, JSON.stringify(all));
    } catch (_) { /* 存储满/不可用时静默放弃，不影响输入 */ }
  }

  function clearSectionDrafts() {
    try {
      const all = readSectionDrafts();
      delete all[sectionDraftId()];
      localStorage.setItem(SECTION_DRAFT_KEY, JSON.stringify(all));
    } catch (_) { /* 忽略 */ }
  }

  // ------------------------------------------------------- 确定性初稿（自动正文）
  // 缓存键随 周期类型+周期键+对比口径 变化：切周期/切对比后自动重算；
  // 「重新生成」按钮强制重算。生成结果只填空输入框，绝不覆盖人工内容。
  function generatedDraftKey() {
    return `${state.mode}:${currentPeriod()}:${compareQuery()}`;
  }

  function refreshGeneratedDraft(force = false) {
    if (!state.context || !deterministicDraft) return null;
    const key = generatedDraftKey();
    if (force || !state.generatedDraft || state.generatedDraft.key !== key) {
      const built = deterministicDraft.buildDraft(state.context);
      state.generatedDraft = { key, ...built };
    }
    return state.generatedDraft;
  }

  function generatedTextFor(sectionKey, subKey) {
    const draft = state.generatedDraft;
    if (!draft || !draft.sections) return '';
    const entry = draft.sections[sectionKey];
    if (!entry) return '';
    return (subKey ? entry[subKey] : entry.text) || '';
  }

  /** 生成元信息条：时间 / 周期 / 对比口径 / 覆盖率。只展示，不含操作入口。 */
  /** 初稿元信息：导航行右侧的小字（周期/对比口径在顶栏已有，这里只留时间·口径·覆盖）。 */
  function renderDraftMeta() {
    if (!els.draftMeta) return;
    const draft = state.generatedDraft;
    if (!draft || !draft.meta) {
      els.draftMeta.hidden = true;
      els.draftMeta.replaceChildren();
      return;
    }
    const meta = draft.meta;
    els.draftMeta.hidden = false;
    els.draftMeta.replaceChildren(
      // 悬停可见完整说明；导航行窄，不放长文案。
      h('span', {
        class: 'pr-draft-meta__text',
        title: `初稿生成于 ${meta.generatedAt}；系统只填数据事实，业务原因需人工确认；已填写内容不会被覆盖。`,
        text: `初稿 ${meta.generatedAt} · ${meta.compareLabel} · 覆盖 ${meta.coverage}`,
      }),
    );
  }

  function regenerateDraft() {
    if (!state.context) return;
    refreshGeneratedDraft(true);
    renderSections(state.template, state.context, state.review);
    renderDraftMeta();
    stateBanner('已重新生成初稿；只补空输入框，不覆盖已填写内容。', '');
  }

  function renderSections(template, context, review) {
    if (!els.sections) return;
    refreshGeneratedDraft();
    renderDraftMeta();
    renderSectionNav(template, review);
    els.sections.replaceChildren(...template.map((section, index) => sectionNode(section, index, context, review)));
    // 自适应高度必须在挂载后量（未挂载时 scrollHeight=0）；字体布局稳定后再补一次。
    els.sections.querySelectorAll('textarea').forEach(autoGrowTextarea);
    requestAnimationFrame(() => els.sections.querySelectorAll('textarea').forEach(autoGrowTextarea));
  }

  // 结论区锚点导航：六段各一枚 chip（短标题 + 完成状态点），吸顶常驻，
  // 解决六段×(数据+三输入)10 屏长页的定位问题。
  const CN_NUMERALS = ['①', '②', '③', '④', '⑤', '⑥', '⑦', '⑧'];

  function sectionFillState(section, review) {
    const saved = (review && review.sections && review.sections[section.key]) || {};
    const savedSubs = (saved.subsections && typeof saved.subsections === 'object') ? saved.subsections : {};
    const subs = section.subsections || [];
    if (!subs.length) {
      const filled = String(readSectionDraft(section.key) || saved.text || generatedTextFor(section.key, '')).trim().length > 0;
      return section.required ? (filled ? 'done' : 'missing') : 'done';
    }
    let filled = 0;
    let requiredMissing = 0;
    subs.forEach((sub) => {
      const text = String(readSectionDraft(`${section.key}:${sub.key}`)
        || savedSubs[sub.key]
        || generatedTextFor(section.key, sub.key) || '');
      if (text.trim()) filled += 1;
      else if (sub.required) requiredMissing += 1;
    });
    return requiredMissing > 0 ? 'missing' : (filled > 0 ? 'done' : 'empty');
  }

  function renderSectionNav(template, review) {
    if (!els.sectionNav) return;
    if (!template.length) {
      els.sectionNav.hidden = true;
      els.sectionNav.replaceChildren();
      return;
    }
    els.sectionNav.hidden = false;
    const chips = template.map((section, index) => {
      const stateKind = sectionFillState(section, review);
      const label = (section.title || section.key).split('（')[0].replace(/^(本周|本月)/, '');
      return h('button', {
        type: 'button',
        class: `pr-section-nav__chip is-${stateKind}`,
        onclick: () => {
          const target = els.sections.querySelector(`[data-section-key="${section.key}"]`);
          target?.scrollIntoView({ behavior: 'smooth', block: 'start' });
        },
      },
        h('span', { class: 'pr-section-nav__dot', 'aria-hidden': 'true' }),
        h('span', { text: `${CN_NUMERALS[index] || index + 1} ${label}` }));
    });
    // 支撑工作区锚点（页签撤除后平铺一页，从导航行直达）。
    const panelChips = [
      ['execution', '⑦ 计划与动作'],
      ['reference', '⑧ 数据参考'],
    ].map(([key, label]) => h('button', {
      type: 'button',
      class: 'pr-section-nav__chip',
      onclick: () => activateWorkbench(key),
    },
      h('span', { class: 'pr-section-nav__dot', 'aria-hidden': 'true' }),
      h('span', { text: label })));
    // 元信息节点常驻 nav 内（右侧小字），重建 chips 时必须带回去。
    els.sectionNav.replaceChildren(...chips, ...panelChips);
    if (els.draftMeta) els.sectionNav.append(els.draftMeta);
  }

  // 输入框高度随内容生长：内联直编的核心体验——写多长框就多高，不再滚动条内写作。
  function autoGrowTextarea(textarea) {
    textarea.style.height = 'auto';
    textarea.style.height = `${textarea.scrollHeight + 2}px`;
  }

  // 输入变化后同步导航 chip 的完成状态点（节流到动画帧，避免高频输入重排）。
  let sectionNavRefreshQueued = false;
  function refreshSectionNav() {
    if (sectionNavRefreshQueued || !els.sectionNav) return;
    sectionNavRefreshQueued = true;
    requestAnimationFrame(() => {
      sectionNavRefreshQueued = false;
      renderSectionNav(state.template, state.review);
    });
  }

  function sectionNode(section, index, context, review) {
    const saved = (review && review.sections && review.sections[section.key]) || {};
    const panel = h('article', { class: 'ui-panel pr-section' });
    panel.dataset.sectionKey = section.key;

    const header = h('div', { class: 'panel__header' },
      h('div', null,
        h('h3', { class: 'panel__title pr-section__title' },
          h('span', { class: 'pr-section__index', text: String(index + 1) }),
          h('span', { text: section.title }),
          section.required ? h('span', { class: 'pr-section__required', text: '必填' }) : null,
          (() => {
            // 段落完成状态：不用滚动就能看出哪段还没写。
            const kind = sectionFillState(section, review);
            const text = kind === 'missing' ? '缺必填' : (kind === 'done' ? '已填写' : '未填写');
            return h('span', { class: `pr-section__state is-${kind}`, text });
          })()),
        h('p', { class: 'panel__hint', text: section.hint || '' }),
      ));

    const body = h('div', { class: 'ui-panel__body' });
    // 板块数据（materials）渲染在三段输入之前：先看数，再下结论。
    // metrics/target_path 不重复渲染——驾驶舱三卡就在同页上方，一块数字看两遍是噪音。
    const materialKeys = (section.materials || []).filter((key) => key !== 'metrics' && key !== 'target_path');
    // 系统证据节点：板块数据置顶展示，点数据块标题可收起。
    let evidenceNode = null;
    if (materialKeys.length) {
      // 默认收起：证据是全量明细（六段合计约 7200px，货品段一段就 3261px），
      // 默认展开会把写作区推到 12 屏外——正是文档 P4「表格墙」的形态。
      // 细看走右侧抽屉（「在右侧展开 →」）；想就地看也能展开本段。
      evidenceNode = h('details', { class: 'pr-evidence' },
        h('summary', null,
          h('span', { class: 'pr-evidence__label', text: `板块数据（${materialKeys.length} 个数据块）` }),
          h('button', {
            type: 'button',
            class: 'pr-evidence__open-drawer',
            text: '在右侧展开 →',
            onclick: (event) => {
              event.preventDefault(); // 别顺带把本段 details 也展开/收起
              openDiagnosisDrawer(section.key);
            },
          })),
        h('div', { class: 'pr-evidence__body' }, ...materialKeys.map((key) => materialFor(key, context)).filter(Boolean)),
      );
    } else if ((section.materials || []).some((key) => key === 'metrics' || key === 'target_path')) {
      evidenceNode = h('p', { class: 'pr-material__empty', text: '业绩与目标差距已在上方驾驶舱展示，这里只填写结论与达成路径。' });
    }

    // v3 三段式：模板带 subsections 定义时渲染「分析/根因/下一步」三个子输入框，
    // 保存为 subsections 结构；无定义时保持单框（day 模板与未知段落兼容）。
    const subDefs = section.subsections || [];
    if (subDefs.length) {
      const savedSubs = (saved.subsections && typeof saved.subsections === 'object') ? saved.subsections : {};
      const wrap = h('div', { class: 'pr-subsections' });
      let anyDraftRestored = false;
      subDefs.forEach((sub) => {
        const draftKey = `${section.key}:${sub.key}`;
        const draft = readSectionDraft(draftKey);
        // 老复盘（无 subsections 结构）时，analysis 子段回填原 text 做只读迁移；
        // 但其他子段已有内容时不能用 text 兜底——text 是三段拼接串，
        // analysis 一旦清空就会显示成「根因+下一步」的拼接。
        const hasSubContent = Object.values(savedSubs).some((entry) => String(entry || '').trim());
        const savedText = savedSubs[sub.key]
          || (sub.key === 'analysis' && !hasSubContent ? (saved.text || '') : '');
        // 回填优先级：本地未保存编辑 > 服务端已保存 > 系统生成的初稿。
        const value = draft || savedText || generatedTextFor(section.key, sub.key);
        if (draft && draft !== savedText) anyDraftRestored = true;
        const textarea = h('textarea', {
          'data-pr-input': section.key,
          'data-pr-subsection': sub.key,
          placeholder: section.placeholder || '',
          rows: 3,
        });
        textarea.value = value;
        textarea.addEventListener('input', () => {
          autoGrowTextarea(textarea);
          textarea.classList.toggle('is-missing', Boolean(sub.required) && !textarea.value.trim());
          updateStatusText();
          storeSectionDraft(draftKey, textarea.value);
          refreshSectionNav();
        });
        if (sub.required && !value.trim()) textarea.classList.add('is-missing');
        const subWrap = h('div', { class: 'pr-subsection' },
          h('label', { class: 'pr-subsection__label' },
            h('span', { text: sub.title }),
            sub.required ? h('em', { text: '必填' }) : null),
          textarea);
        wrap.append(subWrap);
      });
      if (anyDraftRestored) {
        body.append(h('p', { class: 'pr-toolbar__status pr-draft-note', role: 'status', text: '已恢复未保存的本地草稿；保存复盘后将清除。' }));
      }
      // 板块数据在三段输入之前：先看数，再写分析/根因/下一步。
      if (evidenceNode) body.append(evidenceNode);
      body.append(wrap);
    } else {
      // 单框段落（day 模板等）：证据保持挂在段落顶部。
      if (evidenceNode) body.append(evidenceNode);
      const textarea = h('textarea', {
        'data-pr-input': section.key,
        placeholder: section.placeholder || '',
        rows: 4,
      });
      // 回填优先级：本地未保存编辑 > 服务端已保存 > 系统生成的初稿。
      // （草稿是用户最新的未保存编辑，必须最优先，否则刷新即丢编辑。）
      const draft = readSectionDraft(section.key);
      const savedText = saved.text || '';
      textarea.value = draft || savedText || generatedTextFor(section.key, '');
      if (draft && draft !== savedText) {
        body.append(h('p', { class: 'pr-toolbar__status pr-draft-note', role: 'status', text: '已恢复未保存的本地草稿；保存复盘后将清除。' }));
      }
      textarea.addEventListener('input', () => {
        autoGrowTextarea(textarea);
        textarea.classList.toggle('is-missing', Boolean(section.required) && !textarea.value.trim());
        updateStatusText();
        storeSectionDraft(section.key, textarea.value);
      });
      if (section.required && !textarea.value.trim()) textarea.classList.add('is-missing');

      body.append(h('div', { class: 'pr-input' },
        textarea,
        h('div', { class: 'pr-input__meta' },
          h('span', { text: section.required ? '必填段落' : '选填段落' }),
          h('span', { text: `${textarea.value.length} 字` }),
        )));

      const counter = body.querySelector('.pr-input__meta span:last-child');
      textarea.addEventListener('input', () => { if (counter) counter.textContent = `${textarea.value.length} 字`; });
    }

    panel.append(header, body);
    return panel;
  }

  // ------------------------------------------------------------------ 状态
  function collectSections() {
    const sections = {};
    els.sections.querySelectorAll('[data-pr-input]').forEach((node) => {
      const key = node.dataset.prInput;
      const subKey = node.dataset.prSubsection;
      if (subKey) {
        // 三段式：聚合成 {text 拼接, subsections}，text 由后端拼接回写兜底。
        const entry = sections[key] || { subsections: {} };
        entry.subsections[subKey] = node.value.trim();
        sections[key] = entry;
      } else {
        sections[key] = { text: node.value.trim() };
      }
    });
    // 补三段拼接 text：老版本读 text 不丢内容（后端也会拼，这里前端先行，
    // 保证「保存后立即整页刷新前的本地渲染」同样可读）。
    Object.entries(sections).forEach(([key, entry]) => {
      if (entry.subsections) {
        const joined = Object.values(entry.subsections).filter(Boolean).join('\n\n');
        if (joined) entry.text = joined;
      }
    });
    return sections;
  }

  function missingRequired() {
    const missing = [];
    state.template.forEach((section) => {
      if (!section.required) return;
      const subDefs = section.subsections || [];
      if (subDefs.length) {
        const emptySubs = subDefs.filter((sub) => {
          if (!sub.required) return false;
          const node = els.sections.querySelector(`[data-pr-input="${section.key}"][data-pr-subsection="${sub.key}"]`);
          return !node || !node.value.trim();
        });
        if (emptySubs.length) missing.push(`${section.title}（${emptySubs.map((s) => s.title).join('/')}）`);
      } else {
        const node = els.sections.querySelector(`[data-pr-input="${section.key}"]:not([data-pr-subsection])`);
        if (!node || !node.value.trim()) missing.push(section.title);
      }
    });
    return missing;
  }

  function updateStatusText() {
    if (!els.statusText) return;
    const missing = missingRequired();
    const period = currentPeriod();
    els.statusText.textContent = missing.length
      ? `${period} · 还有 ${missing.length} 个必填段落未填写，可先存草稿。`
      : '';
  }

  // ------------------------------------------------------------------ 加载
  async function loadTemplates() {
    if (state.template.length) return;
    const response = await DemoApi.domainRequest('/api/period-reviews/templates');
    state.templates = response.data.templates || {};
  }

  async function loadCategories() {
    if (state.categories.length) return;
    try {
      const response = await DemoApi.domainRequest('/api/period-reviews/categories');
      const modes = (response.data && response.data.categories) || [];
      state.categories = modes.filter((item) => item && item.enabled !== false);
    } catch (_) {
      // 品类选项拉取失败不应让整页不可用（例如后端仍是旧版本），退回系统品类继续。
      state.categories = [
        { value: 'all', label: '全部品类', enabled: true },
        { value: 'sock', label: '标品袜子', enabled: true },
      ];
    }
    if (!state.categories.length) return;
    const current = readCategoryMode();
    const values = state.categories.map((item) => String(item.value));
    if (els.category) {
      els.category.replaceChildren(...state.categories.map((item) => h('option', {
        value: String(item.value), text: String(item.label || item.value),
      })));
    }
    // 存储的模式若已不可用，退回标品袜子而不是静默变成第一个选项。
    const resolved = values.includes(current) ? current
      : (values.includes(CATEGORY_FALLBACK) ? CATEGORY_FALLBACK : values[0] || current);
    if (els.category) els.category.value = resolved;
    storeCategoryMode(resolved);
    syncTopbarCategory(resolved);
  }

  // 已保存复盘的口径与当前所选不一致时提示，避免把两个品类的结论混在一期里。
  function renderCategoryNote() {
    if (!els.categoryNote) return;
    const savedMode = state.review && state.review.category_mode;
    const currentMode = readCategoryMode();
    if (!savedMode || savedMode === currentMode) {
      els.categoryNote.textContent = '';
      return;
    }
    const savedLabel = (state.categories.find((item) => String(item.value) === savedMode) || {}).label || savedMode;
    const currentLabel = (els.category && els.category.selectedOptions && els.category.selectedOptions[0]
      && els.category.selectedOptions[0].textContent) || categoryLabelOf() || '全部品类';
    els.categoryNote.textContent = `注意：本期已保存的复盘是按「${savedLabel}」写的，当前显示的是「${currentLabel}」口径。`;
  }

  // 对比方式 + 自定义对比周期下拉；选项来自当前上下文的可选周期列表。
  function renderCompareControls(context) {
    const compare = context.compare || {};
    if (els.compare) els.compare.value = compare.mode || 'previous';
    const showCustom = compare.mode === 'custom';
    if (els.comparePeriodField) els.comparePeriodField.hidden = !showCustom;
    if (!els.comparePeriod || !showCustom) return;

    const currentKey = context.period && context.period.key;
    const options = (context.compare_options || []).filter((item) => item.key !== currentKey);
    els.comparePeriod.replaceChildren(...options.map((item) => h('option', {
      value: item.key, text: item.label,
    })));
    if (compare.period_key && options.some((item) => item.key === compare.period_key)) {
      els.comparePeriod.value = compare.period_key;
    }
  }

  // ------------------------------------------- 指标矩阵 / 类目拆解的数据拉取
  // 这两个面板的数据必须与主 load() 解耦：
  //   - 主请求（context/review）失败时，它们不该被一起清空；
  //   - 它们自己失败时（例如后端重启窗口期的 404），要能单独重拉，
  //     而不是让用户看到「加载失败」后再也没救、只能整页刷新。
  let matrixFetchToken = 0;

  function describeRequestError(error) {
    if (!error) return '未知错误';
    if (error.code === 'REQUEST_TIMEOUT') return '请求超时，后端可能正在重启或负载过高';
    if (error.status === 404) return '接口不存在（HTTP 404），后端进程可能仍是旧代码，需要重启服务';
    if (error.status === 422) return `参数不合法（HTTP 422）：${error.message || '该周期键无效'}`;
    if (error.status) return `HTTP ${error.status} · ${error.message || '请求失败'}`;
    return error.message || '网络异常，请检查后端服务是否在运行';
  }

  async function loadMatrixPanels(periodKey, { showLoading = false } = {}) {
    const token = ++matrixFetchToken;
    if (showLoading) {
      renderMatrix(state.matrix, state.matrixError, true);
      renderCategoryBreakdown(state.categoryBreakdown, state.categoryError, true);
    }
    const base = `/api/period-reviews/${state.mode}/${encodeURIComponent(periodKey)}`;
    // 两个接口各自结算，一个失败不影响另一个。
    const [matrixResult, breakdownResult, leafResult] = await Promise.all([
      DemoApi.domainRequest(`${base}/matrix`).then((r) => ({ data: r.data })).catch((error) => ({ error })),
      DemoApi.domainRequest(`${base}/category-breakdown`).then((r) => ({ data: r.data })).catch((error) => ({ error })),
      DemoApi.domainRequest('/api/category-analysis/leaf-weekly-board').then((r) => ({ data: r.data })).catch((error) => ({ error })),
    ]);
    if (token !== matrixFetchToken) return;
    state.matrix = matrixResult.data || null;
    state.matrixError = matrixResult.error || null;
    state.categoryBreakdown = breakdownResult.data || null;
    state.categoryError = breakdownResult.error || null;
    if (leafResult.data) { state.leafBoard = leafResult.data; state.leafBoardError = null; }
    else if (leafResult.error && !state.leafBoard) { state.leafBoardError = leafResult.error; }
    renderMatrix(state.matrix, state.matrixError);
    leafBoard.renderLeafBoard(state.leafBoard, state.leafBoardError, false);
    renderCategoryBreakdown(state.categoryBreakdown, state.categoryError);
  }

  // 数据参考懒加载：面板滚进可视区才拉矩阵/类目/叶子看板；已加载且未换周期时不重复拉。
  let referenceObserver = null;
  function observeReferencePanel() {
    const panel = document.querySelector('[data-pr-workbench-panel="reference"]');
    if (!panel || typeof IntersectionObserver === 'undefined') return;
    if (!referenceObserver) {
      referenceObserver = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting && (!state.matrix || !state.categoryBreakdown)) {
            reloadMatrixPanels();
          }
        });
      }, { rootMargin: '240px' });
    }
    referenceObserver.disconnect();
    referenceObserver.observe(panel);
  }

  function reloadMatrixPanels() {
    const periodKey = currentPeriod();
    if (!periodKey) return;
    loadMatrixPanels(periodKey, { showLoading: true });
  }

  async function load() {
    const token = ++loadToken;
    const requestedPeriodKey = currentPeriod();
    if (!requestedPeriodKey) return;
    // 加载新的周期前先清掉上一周期上下文，避免异步时序下页面短暂渲染旧周期。
    state.context = null;
    state.review = null;
    stateBanner('加载中…', 'loading');
    if (els.save) els.save.disabled = true;

    try {
      await Promise.all([loadTemplates(), loadCategories(), loadPeriodOptions()]);
      if (state.selectedPeriodKey && !(state.periodOptions[state.mode] || [])
        .some((item) => item.key === state.selectedPeriodKey)) {
        state.selectedPeriodKey = '';
      }
      syncRangeToSelectedPeriod();
      // 周期选项加载后才能拿到周期的真实起止日期。此处必须重新结算周期键：
      // 如果 URL 带了一个数据里不存在/未来周期，selectedPeriodKey 会被清空，
      // 后续周期必须改由顶栏 start/end 推导，不能继续沿用旧 requestedPeriodKey。
      const periodKey = state.selectedPeriodKey || periodKeyFromRange();
      if (!periodKey) return;
      updateReviewUrl();
      state.template = state.templates[state.mode] || [];

      const [contextResponse, reviewResponse] = await Promise.all([
        DemoApi.domainRequest(`/api/period-reviews/${state.mode}/${encodeURIComponent(periodKey)}/context${compareQuery()}`),
        DemoApi.domainRequest(`/api/period-reviews/${state.mode}/${encodeURIComponent(periodKey)}`),
      ]);
      if (token !== loadToken) return;

      state.context = contextResponse.data.context;
      state.review = reviewResponse.data.review || null;
      state.matrix = null;
      state.matrixError = null;
      state.categoryBreakdown = null;
      state.categoryError = null;

      if (!state.selectedPeriodKey) state.selectedPeriodKey = periodKey;
      renderPeriodPicker();
      updateReviewUrl();
      renderPeriodLabel(state.context.period);
      renderCompareControls(state.context);
      renderWorkbench(state.context, state.review);
      // 数据参考已平铺进页面：滚到可视区才拉矩阵/类目/叶子看板（懒加载）。
      observeReferencePanel();

      targetCards.fillTargetInputs(state.review);
      if (els.reviewer && state.review && state.review.reviewer) els.reviewer.value = state.review.reviewer;
      if (els.statusSelect && state.review && state.review.status) els.statusSelect.value = state.review.status;
      updateSettingsSummary();

      const missing = state.context.metrics.has_data ? [] : state.context.missing_inputs;
      stateBanner(
        missing.length
          ? `本期缺少数据源：${missing.join('、')}。仍可手动填写复盘结论。`
          : '',
        missing.length ? 'no-data' : '',
      );
      renderCategoryNote();
      updateStatusText();
    } catch (error) {
      if (token !== loadToken) return;
      if (els.periodLabel && els.periodLabel.textContent.includes('正在读取')) els.periodLabel.textContent = '—';
      // 404 基本都是后端进程还停留在旧代码（本服务无自动重载），直接给出可执行提示。
      const missingEndpoint = error.status === 404 || error.code === 'NOT_FOUND';
      stateBanner(
        missingEndpoint
          ? '接口不存在：后端服务可能仍是旧代码，重启 dev server 后再刷新本页。'
          : (error.message || '复盘素材加载失败，请重试。'),
        'calculation-failed',
      );
    } finally {
      if (token === loadToken && els.save) els.save.disabled = false;
    }
  }

  // ------------------------------------------------------------------ 保存
  async function save() {
    if (saving) return;
    const periodKey = currentPeriod();
    if (!periodKey) return;
    const missing = missingRequired();
    const status = els.statusSelect ? els.statusSelect.value : 'draft';
    if (status === 'final' && missing.length) {
      stateBanner(`无法定稿：以下必填段落还没有内容 —— ${missing.join('；')}`, 'insufficient-data');
      return;
    }

    saving = true;
    if (els.save) els.save.disabled = true;
    stateBanner('保存中…', 'loading');
    try {
      await DemoApi.domainRequest(
        `/api/period-reviews/${state.mode}/${encodeURIComponent(periodKey)}`,
        {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            reviewer: els.reviewer ? els.reviewer.value.trim() || '运营人员' : '运营人员',
            status,
            ...targetCards.collectTargetInputs(),
            category_mode: readCategoryMode(),
            sections: collectSections(),
          }),
        },
      );
      stateBanner(`已保存 ${periodKey} 复盘。`, '');
      // 保存成功即清本周期草稿：load() 重渲染段落时优先取已保存内容。
      clearSectionDrafts();
      await load();
      await loadHistory();
      // load() 会用素材状态覆盖提示，因此成功提示必须最后写。
      stateBanner(`已保存 ${periodKey} 复盘。`, '');
    } catch (error) {
      stateBanner(error.message || '保存失败，请重试。', 'calculation-failed');
    } finally {
      saving = false;
      if (els.save) els.save.disabled = false;
    }
  }

  // ------------------------------------------------------------------ 历史
  async function loadHistory() {
    if (!els.history) return;
    try {
      const response = await DemoApi.domainRequest('/api/period-reviews');
      const rows = Array.isArray(response.data) ? response.data : [];
      if (!rows.length) {
        els.history.textContent = '还没有历史复盘。';
        return;
      }
      els.history.replaceChildren(...rows.slice(0, 40).map((row) => h('button', {
        type: 'button',
        class: 'pr-history__item',
        onclick: () => {
          if (!PERIOD_TYPES.includes(row.period_type)) return;
          // 历史复盘本身携带完整周期键，直接切换模式、周期并加载，不再要求用户回顶栏手动查找。
          state.mode = row.period_type;
          state.selectedPeriodKey = row.period_key;
          updateModeUi();
          syncRangeToSelectedPeriod();
          load();
        },
      },
      h('strong', { text: `${row.period_type === 'week' ? '周' : row.period_type === 'month' ? '月' : '日'} · ${row.period_key}` }),
      h('span', { text: `${row.status === 'final' ? '已定稿' : '草稿'} · ${row.reviewer || '--'} · ${(row.updated_at || '').slice(0, 16)}` }),
      )));
    } catch (error) {
      els.history.textContent = error.message || '历史复盘加载失败。';
    }
  }

  // ------------------------------------------------------------------ 交互
  function setMode(mode) {
    if (!PERIOD_TYPES.includes(mode) || mode === state.mode) {
      updateModeUi();
      return;
    }
    state.mode = mode;
    state.selectedPeriodKey = '';
    // 自定义对比周期与周期类型绑定，切模式时重置，避免持有非法周期键。
    const choice = readCompareChoice();
    if (choice.mode === 'custom' && !comparePeriodMatchesMode(choice.period)) {
      const fallback = { mode: 'previous', period: '' };
      compareChoiceOverride = fallback;
      storeCompareChoice(fallback);
    }
    updateModeUi();
    load();
  }

  function updateModeUi() {
    els.modeButtons.forEach((button) => {
      const active = button.dataset.prMode === state.mode;
      button.classList.toggle('is-active', active);
      button.setAttribute('aria-selected', String(active));
    });
  }

  els.modeButtons.forEach((button) => button.addEventListener('click', () => setMode(button.dataset.prMode)));
  bindSettingsDialog();
  bindDiagnosisDrawer();
  els.period?.addEventListener('change', () => {
    const selected = (state.periodOptions[state.mode] || []).find((item) => item.key === els.period.value);
    if (!selected || !window.TmallDateRange?.setReviewRange) return;
    state.selectedPeriodKey = selected.key;
    syncRangeToSelectedPeriod();
    load();
  });
  els.refresh?.addEventListener('click', () => load());
  // 生成/重新生成初稿：强制重算并重渲染段落，只补空输入框，不覆盖人工内容。
  els.generateDraft?.addEventListener('click', regenerateDraft);
  // 目标输入即时联动：target-cards 把输入换算回写 context.target_path（会顺带
  // 触发归因摘要刷新），再整块重建驾驶舱让三卡完成率「填了立刻有反应」。
  const refreshTargetPanels = () => {
    targetCards.refreshTargetCard();
    if (state.context) renderCommandCenter(state.context);
  };
  const refreshTargetTablePanels = () => {
    targetCards.refreshTargetTable();
    if (state.context) renderCommandCenter(state.context);
  };
  els.target?.addEventListener('input', refreshTargetPanels);
  [els.targetProfit, els.targetAdSpend, els.targetNetExpenseRatio]
    .forEach((input) => input?.addEventListener('input', refreshTargetTablePanels));
  // 品类切换即写全局模式：api.js 会给所有 GET 自动带上 category_mode，因此无需整页刷新。
  els.category?.addEventListener('change', () => {
    storeCategoryMode(els.category.value);
    syncTopbarCategory(els.category.value);
    load();
  });
  // 对比方式 / 对比周期：写 localStorage 后重载，KPI 的对比列随之改基线。
  els.compare?.addEventListener('change', () => {
    const mode = els.compare.value;
    if (mode === 'custom') {
      const options = (state.context && state.context.compare_options) || [];
      const currentKey = state.context && state.context.period && state.context.period.key;
      const fallback = options.find((item) => item.key !== currentKey) || options[0] || {};
      const period = (els.comparePeriod && els.comparePeriod.value) || fallback.key || '';
      compareChoiceOverride = { mode: 'custom', period };
    } else {
      compareChoiceOverride = { mode, period: '' };
    }
    storeCompareChoice(compareChoiceOverride);
    load();
  });
  els.comparePeriod?.addEventListener('change', () => {
    compareChoiceOverride = { mode: 'custom', period: els.comparePeriod.value };
    storeCompareChoice(compareChoiceOverride);
    load();
  });
  els.save?.addEventListener('click', save);
  // 导出反馈：成功/素材未加载都写状态条，与其他操作一致（IAB 里 download 可能被拦，
  // 用户需要知道点击是否生效）。
  els.export?.addEventListener('click', () => {
    const ok = reviewExport.exportMarkdown();
    stateBanner(ok
      ? `已导出 ${currentPeriod()} 复盘 Markdown；若浏览器拦截了下载，请检查下载设置。`
      : '素材尚未加载完成，稍后再试。', ok ? '' : 'insufficient-data');
  });
  window.addEventListener('tmall:refresh', () => load());
  // 顶栏统一时间范围一变化，复盘周期随之重算
  window.addEventListener('tmall:date-range-change', () => {
    // setReviewRange 触发的事件由调用方继续 load，这里不能再额外启动一次加载，
    // 否则旧请求/新请求交叉时容易把 period_key 和顶栏日期写成两套口径。
    if (syncingReviewRange) return;
    state.selectedPeriodKey = '';
    load();
  });

  updateModeUi();
  load();
  loadHistory();
})();
