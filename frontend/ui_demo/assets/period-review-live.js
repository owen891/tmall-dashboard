(function () {
  'use strict';

  const PERIOD_TYPES = ['week', 'month'];
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
    overview: document.querySelector('[data-pr-overview]'),
    sections: document.querySelector('[data-pr-sections]'),
    commandCenter: document.querySelector('[data-pr-command-center]'),
    productAnalysis: document.querySelector('[data-pr-product-analysis]'),
    executionAnalysis: document.querySelector('[data-pr-execution-analysis]'),
    channelAnalysis: document.querySelector('[data-pr-channel-analysis]'),
    marketAnalysis: document.querySelector('[data-pr-market-analysis]'),
    promotionAnalysis: document.querySelector('[data-pr-promotion-analysis]'),
    matrix: document.querySelector('[data-pr-matrix]'),
    categoryBreakdown: document.querySelector('[data-pr-category-breakdown]'),
    history: document.querySelector('[data-pr-history]'),
    save: document.querySelector('[data-pr-save]'),
    refresh: document.querySelector('[data-pr-refresh]'),
  };

  const urlParams = new URLSearchParams(window.location.search);
  const state = {
    mode: PERIOD_TYPES.includes(urlParams.get('period_type')) ? urlParams.get('period_type') : 'week',
    selectedPeriodKey: urlParams.get('period_key') || '',
    periodOptions: { week: [], month: [] },
    template: [], templates: {}, categories: [], context: null, review: null, matrix: null,
    matrixError: null, categoryBreakdown: null, categoryError: null, leafBoard: null, leafBoardError: null,
  };
  let syncingReviewRange = false;
  let loadToken = 0;
  let saving = false;
  let actionSaving = false;
  let actionDialog = null;
  let actionReviewDialog = null;
  let actionDetailDialog = null;

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

  function readCompareChoice() {
    let stored = null;
    try { stored = JSON.parse(localStorage.getItem(COMPARE_KEY) || 'null'); } catch (_) { stored = null; }
    const mode = stored && COMPARE_MODES.includes(stored.mode) ? stored.mode : 'previous';
    return { mode, period: (stored && stored.period) || '' };
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
    const { mode, period } = readCompareChoice();
    if (mode === 'custom' && comparePeriodMatchesMode(period)) {
      return `?compare=custom&compare_period=${encodeURIComponent(period)}`;
    }
    // 自定义但周期缺失/类型不符时退回环比，避免发出不合法请求。
    return `?compare=${mode === 'custom' ? 'previous' : encodeURIComponent(mode)}`;
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
    const scope = state.mode === 'week' ? '按结束日期识别所在月内周（周不跨月）' : '按结束日期识别所在自然月';
    els.rangeHint.textContent = `顶栏时间范围 ${range.startDate} ~ ${range.endDate} · ${scope}；要换周期请在顶栏「统计时间」选择上周 / 上月或自定义。`;
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

  function todayForAction() {
    const date = new Date();
    return `${date.getFullYear()}-${pad2(date.getMonth() + 1)}-${pad2(date.getDate())}`;
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

  function openProductDiagnosis(row, withDelta) {
    if (!actionDialog) {
      actionDialog = h('dialog', { class: 'pr-action-dialog' });
      document.body.append(actionDialog);
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
      h('div', null, h('span', { text: '本期 GSV' }), h('strong', { text: safeMetric(row.gsv, 'money') })),
      h('div', null, h('span', { text: 'GSV 占比' }), h('strong', { text: share === null ? '不可判断' : `${(share * 100).toFixed(2)}%` })),
      h('div', null, h('span', { text: '净销售额' }), h('strong', { text: safeMetric(row.net_sales, 'money') })),
      withDelta ? h('div', null, h('span', { text: '上期 GSV' }), h('strong', { text: safeMetric(row.prev_gsv, 'money') })) : null,
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
        ? `系统依据：本期 GSV ${safeMetric(row.gsv, 'money')}，上期 GSV ${safeMetric(row.prev_gsv, 'money', '不可判断')}，变化比例 ${rate === null ? '不可判断' : `${(rate * 100).toFixed(2)}%`}`
        : `系统依据：本期 GSV ${safeMetric(row.gsv, 'money')}，在当前返回的销售 TOP 列表中排名靠前` }),
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
    form.append(
      actionField('动作目的', 'purpose_note', 'textarea', withDelta ? `${row.title || row.product_id} GSV 下滑，需制定恢复动作` : `${row.title || row.product_id} 销售贡献跟进`, true),
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
        actionField('计划日期', 'planned_at', 'date', todayForAction(), true),
        actionField('观察天数', 'observer_window_days', 'number', '7', true),
        actionField('负责人', 'assigned_to', 'text', '运营人员'),
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
        product_id: row.product_id,
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
        source_product_id: row.product_id,
        source_problem_key: (row.anomaly_tags || [])[0] || (withDelta ? 'product_decline' : 'product_top_sales'),
        source_diagnosis_snapshot: JSON.stringify({
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

  function deltaNode(item) {
    const wrap = h('div', { class: 'pr-kpi__delta' });
    const compare = (state.context && state.context.compare) || { mode: 'previous', short_label: '环比' };
    const build = (label, change) => {
      if (change === null || change === undefined) return null;
      const good = item.lower_better ? change < 0 : change > 0;
      const cls = change === 0 ? 'pr-delta' : `pr-delta ${good ? 'is-up' : 'is-down'}`;
      return h('span', { class: cls, text: `${label} ${change > 0 ? '+' : ''}${change}%` });
    };
    const nodes = [];
    if (compare.mode !== 'none') {
      const baseline = build(compare.short_label || '环比', item.mom_change);
      if (baseline) nodes.push(baseline);
    }
    // 对比基线本身就是同比时不再重复一行
    if (compare.mode !== 'yoy') {
      const yoy = build('同比', item.yoy_change);
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
  function renderOverview(context) {
    if (!els.overview) return;
    const period = context.period;
    const label = (context.category && context.category.label) || '全部品类';
    els.overview.hidden = false;
    els.overview.replaceChildren(
      h('div', { class: 'pr-overview__head' },
        h('h3', { text: '业绩全景' }),
        h('span', { text: `${period.label} · ${period.start} ~ ${period.end} · 品类：${label}` }),
      ),
      renderKpiGrid(context.metrics),
      targetCards.renderTarget(context.target_path),
      targetCards.renderTargetTable(context.target_path.targets, targetCards.targetTimeProgress(period)),
    );
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

  function renderCommandCenter(context) {
    if (!els.commandCenter) return;
    const current = context.metrics && context.metrics.current || {};
    const items = context.metrics && context.metrics.items || [];
    const dangerCount = (context.anomalies || []).filter((item) => item.level === 'danger' || item.level === 'warning').length;
    const blockedCount = (context.actions_blocked || []).length;
    const plannedCount = (context.actions_planned || []).length;
    const target = context.target_path || {};
    const gapText = target.target ? formatValue(target.gap, 'money') : '未设置';
    const summaryKind = context.metrics && context.metrics.has_data ? (dangerCount || blockedCount ? 'warning' : 'good') : 'muted';
    const summary = context.metrics && context.metrics.has_data
      ? `本期 GSV ${formatValue(current.gsv, 'money')}，${context.compare && context.compare.short_label || '环比'} ${signedPercent(items.find((item) => item.key === 'gsv')?.mom_change)}；当前优先关注 ${dangerCount + blockedCount} 个风险信号。`
      : '当前周期缺少可用经营事实，先补齐数据后再形成结论。';
    els.commandCenter.hidden = false;
    els.commandCenter.replaceChildren(
      h('div', { class: 'pr-command-center__head' },
        h('div', null, h('span', { class: 'section-kicker', text: '先看结论' }), h('h3', { text: '复盘驾驶舱' }), h('p', { text: summary })),
        stateTag(context.metrics && context.metrics.has_data ? (dangerCount || blockedCount ? '需要处理' : '运行稳定') : '数据不足', summaryKind),
      ),
      h('div', { class: 'pr-command-center__grid' },
        h('div', { class: 'pr-command-card pr-command-card--primary' },
          h('span', { text: '核心结果' }), h('strong', { text: formatValue(current.gsv, 'money') }),
          h('small', { text: `净销售 ${formatValue(current.net_sales, 'money')} · 支付买家 ${formatCompact(current.buyers)}` })),
        h('div', { class: 'pr-command-card' },
          h('span', { text: '目标差距' }), h('strong', { text: gapText }),
          h('small', { text: target.target ? `达成率 ${(Number(target.achieved_rate || 0) * 100).toFixed(1)}%` : '请在复盘设置中补充目标' })),
        h('div', { class: 'pr-command-card' },
          h('span', { text: '风险信号' }), h('strong', { text: String(dangerCount + blockedCount) }),
          h('small', { text: `异常 ${dangerCount} · 阻塞动作 ${blockedCount}` })),
        h('div', { class: 'pr-command-card' },
          h('span', { text: '待落地动作' }), h('strong', { text: String(plannedCount) }),
          h('small', { text: plannedCount ? '已有动作记录，可继续补充验收标准' : '当前没有待执行动作记录' })),
      ),
      h('div', { class: 'pr-command-center__links' },
        h('button', { type: 'button', class: 'pr-anchor-link', onclick: () => activateWorkbench('products'), text: '查看异常商品' }),
        h('button', { type: 'button', class: 'pr-anchor-link', onclick: () => activateWorkbench('execution'), text: '查看动作计划' }),
        h('button', { type: 'button', class: 'pr-anchor-link', onclick: () => activateWorkbench('market'), text: '查看市场竞争' }),
      ),
    );
  }

  function renderProductAnalysis(context) {
    if (!els.productAnalysis) return;
    productColumns.rememberContext(context);
    const products = context.products || {};
    els.productAnalysis.replaceChildren(
      productColumns.productTableToolbar(),
      analysisPanel('销售贡献 TOP10', '按本期 GSV 排序，先识别需要保住的核心商品。', productColumns.renderProductTable(products.top, false), '本期没有正向销售商品。'),
      analysisPanel('下滑商品 TOP10', '按相对上期的 GSV 变化排序，作为异常诊断入口。', productColumns.renderProductTable(products.decline, true), '缺少可比周期数据。'),
    );
  }

  function renderMarketAnalysis(context) {
    if (!els.marketAnalysis) return;
    const traffic = context.dimensions?.traffic || {};
    els.marketAnalysis.replaceChildren(
      analysisPanel('流量来源拆解', `流量覆盖 ${traffic.sample_days || 0}/${traffic.period_days || '--'} 天`, trafficTable(traffic), '暂无搜索、推荐、付费或自然流量拆解数据。'),
      analysisPanel('市场、竞店与竞品', '先看可复现事实，再看系统观察；价格、利润和评价结论仍需补证。', renderMarket(context.market), '暂无市场批次。'),
    );
  }

  function dimensionPercent(value) {
    return value === null || value === undefined ? '--' : `${(Number(value) * 100).toFixed(1)}%`;
  }

  function dimensionTable(items, type) {
    if (!items || !items.length) return null;
    const nameLabel = type === 'campaign' ? '计划' : '渠道';
    return h('div', { class: 'pr-breakdown-table-wrap' }, h('table', { class: 'pr-table pr-breakdown-table' },
      h('thead', null, h('tr', null,
        h('th', { text: nameLabel }), h('th', { class: 'num', text: '花费' }),
        h('th', { class: 'num', text: '归因成交' }), h('th', { class: 'num', text: 'ROI' }),
        h('th', { class: 'num', text: '点击率' }), h('th', { class: 'num', text: '成交变化' }),
      )),
      h('tbody', null, ...items.map((item) => h('tr', null,
        h('td', { title: item.name, text: item.name }),
        h('td', { class: 'num', text: formatValue(item.ad_spend, 'money') }),
        h('td', { class: 'num', text: formatValue(item.attributed_payment, 'money') }),
        h('td', { class: 'num', text: formatValue(item.roi, 'decimal') }),
        h('td', { class: 'num', text: dimensionPercent(item.ctr) }),
        h('td', { class: 'num', text: item.payment_change_rate === null || item.payment_change_rate === undefined
          ? '--' : `${item.payment_change_rate > 0 ? '+' : ''}${(item.payment_change_rate * 100).toFixed(1)}%` }),
      ))),
    ));
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

  function renderChannelAnalysis(context) {
    if (!els.channelAnalysis) return;
    const dimensions = context.dimensions || {};
    const promotion = dimensions.promotion || {};
    const channelView = promotion.channels || {};
    const campaignView = promotion.campaigns || {};
    const quality = [
      `渠道粒度 ${channelView.grain || '--'}`,
      `计划粒度 ${campaignView.grain || '--'}`,
    ].join(' · ');
    const promotionHint = (view, grainName) => view.missing_inputs?.includes('promotion_category_scope')
      ? `当前推广数据没有商品映射，无法按所选类目筛选${grainName}，避免混入全店数据。`
      : `按 ${view.grain || grainName} 粒度聚合；缺少数据时保持为空，不补 0。`;
    els.channelAnalysis.replaceChildren(
      analysisPanel('推广渠道拆解', promotionHint(channelView, 'channel'), dimensionTable(channelView.items, 'channel'), '暂无可按当前口径使用的渠道推广数据。'),
      analysisPanel('推广计划拆解', campaignView.comparison_available === false
        ? '本期有计划数据，但对比期缺少同粒度数据，暂不展示环比。'
        : promotionHint(campaignView, 'campaign'), dimensionTable(campaignView.items, 'campaign'), '暂无可按当前口径使用的计划推广数据。'),
    );
    if (els.promotionAnalysis) {
      els.promotionAnalysis.replaceChildren(
        analysisPanel('推广效率', '本期推广投入与效率变化，数据事实不代替原因判断。', renderAds(context.ads), '暂无推广数据。'),
      );
    }
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
    const lowerBetter = metric.lower_better;
    const good = lowerBetter ? change < 0 : change > 0;
    const kind = change === 0 ? 'neutral' : (good ? 'up' : 'down');
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
    // 预计算每列最大绝对值，用于数据条缩放
    const maxByColumn = {};
    columns.forEach((col) => {
      maxByColumn[col.key] = Math.max(...data.rows.map((row) => Math.abs((row.metrics[col.key] || {}).value || 0)), 0.0001);
    });

    const thead = h('thead', null, renderMatrixHeader(columns));
    const tbody = h('tbody', null, ...data.rows.map((row) => {
      const tr = h('tr', { class: `pr-matrix-row ${matrixStatusClass(row.status)}` });
      tr.append(h('td', { class: 'pr-matrix-cell--period' }, renderPeriodCellLabel(row.label)));
      tr.append(h('td', { class: 'pr-matrix-cell--status' }, h('span', { class: `pr-status-tag ${matrixStatusClass(row.status).replace('is-', '')}` }, matrixStatusLabel(row.status))));
      columns.forEach((col) => {
        tr.append(renderMatrixCell(row.metrics[col.key], maxByColumn[col.key], col.key));
      });
      return tr;
    }));
    return h('table', { class: 'pr-matrix-table' }, thead, tbody);
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


  // ------------------------------------------------- 叶子类目近3周对比看板
  // 格式化收敛到 DemoFormat（format.js 已在本页加载），无则本地兜底。
  const fmtWan = window.DemoFormat?.fmtWan
    || ((v) => v === null || v === undefined || Number.isNaN(Number(v)) ? '--' : (Math.abs(Number(v)) >= 10000 ? `${(Number(v) / 10000).toFixed(1)}万` : Number(v).toLocaleString('zh-CN', { maximumFractionDigits: 0 })));
  const fmtPct = (v, digits = 1) => (v === null || v === undefined || Number.isNaN(Number(v))
    ? '--'
    : `${(Number(v) * 100).toFixed(digits)}%`);
  const fmtNum = (v) => v === null || v === undefined || Number.isNaN(Number(v))
    ? '--'
    : Number(v).toLocaleString('zh-CN', { maximumFractionDigits: 0 });
  function deltaBadge(rate) {
    if (rate === null || rate === undefined || Number.isNaN(Number(rate))) return h('span', { class: 'lb-delta lb-delta--na', text: '--' });
    const n = Number(rate);
    const cls = n > 0.0001 ? 'is-up' : n < -0.0001 ? 'is-down' : 'is-flat';
    const sign = n > 0 ? '+' : '';
    return h('span', { class: `lb-delta ${cls}`, text: `${sign}${(n * 100).toFixed(1)}%` });
  }
  function ppBadge(pp) {
    if (pp === null || pp === undefined || Number.isNaN(Number(pp))) return h('span', { class: 'lb-delta lb-delta--na', text: '--' });
    const n = Number(pp);
    const cls = n > 0.0001 ? 'is-up' : n < -0.0001 ? 'is-down' : 'is-flat';
    const sign = n > 0 ? '+' : '';
    return h('span', { class: `lb-delta ${cls}`, text: `${sign}${(n * 100).toFixed(1)}pp` });
  }
  function lbCell(valueNode, changeNode, compareLabel) {
    return h('td', { class: 'lb-cell' },
      h('div', { class: 'lb-cell__value' }, valueNode),
      h('div', { class: 'lb-cell__delta' },
        compareLabel ? h('span', { class: 'lb-cell__comparison-label', text: compareLabel }) : null,
        changeNode || h('span', { class: 'lb-delta--na', text: '--' }),
      ),
    );
  }
  function renderLeafBoard(data, error, loading) {
    const root = els.categoryBreakdown;
    if (!root) return;
    // 新建一个独立的看板容器，不覆盖原有 category-breakdown 内容
    let board = document.getElementById('leaf-weekly-board');
    if (!board) {
      board = h('section', { id: 'leaf-weekly-board', class: 'leaf-board' });
      root.parentNode.insertBefore(board, root);
    }
    if (loading) {
      board.replaceChildren(h('div', { class: 'pr-load-failure' }, h('p', { text: '正在加载叶子类目近 3 周数据…' })));
      return;
    }
    if (error || !data) {
      const reason = describeRequestError(error);
      board.replaceChildren(
        h('article', { class: 'ui-panel pr-analysis-panel' },
          h('div', { class: 'panel__header' },
            h('div', null, h('h3', { class: 'panel__title', text: '叶子类目近 3 周对比看板' }),
              h('p', { class: 'panel__hint', text: '数据加载失败：' + reason }))),
          h('div', { class: 'ui-panel__body' },
            h('button', { type: 'button', class: 'ui-button ui-button--compact', onclick: () => loadLeafBoard(true), text: '重试' }))),
      );
      return;
    }
    const weeks = data.weeks || {};
    const totals = data.totals || {};
    const rows = data.rows || [];
    const compare = state.context?.compare || { mode: 'previous', short_label: '环比' };
    const baselineKey = compare.mode === 'yoy' ? 'y0' : compare.mode === 'previous' ? 'w1' : null;
    const compareLabel = compare.mode === 'yoy' ? '同比' : compare.mode === 'previous' ? '环比' : '';
    const w0 = totals.w0 || {};
    const baseline = baselineKey ? totals[baselineKey] || {} : {};
    const pctChange = (current, previous) => current != null && previous != null && previous !== 0
      ? (current - previous) / Math.abs(previous) : null;
    const ppChange = (current, previous) => current != null && previous != null ? current - previous : null;

    // KPI 行
    const kpis = [
      { label: '本周净销售', value: `¥${fmtWan(w0.net_sales)}`, delta: deltaBadge(pctChange(w0.net_sales, baseline.net_sales)) },
      { label: '本周推广花费', value: `¥${fmtWan(w0.ad_spend)}`, delta: deltaBadge(pctChange(w0.ad_spend, baseline.ad_spend)) },
      { label: '本周利润', value: `¥${fmtWan(w0.profit)}`, delta: deltaBadge(pctChange(w0.profit, baseline.profit)) },
      { label: '本周利润率', value: fmtPct(w0.profit_rate), delta: ppBadge(ppChange(w0.profit_rate, baseline.profit_rate)) },
      { label: '本周费比', value: fmtPct(w0.ad_ratio), delta: ppBadge(ppChange(w0.ad_ratio, baseline.ad_ratio)) },
    ];
    const kpiRow = h('div', { class: 'leaf-board__kpis' }, ...kpis.map((k) =>
      h('div', { class: 'leaf-board__kpi' },
        h('span', { class: 'leaf-board__kpi-label', text: k.label }),
        h('strong', { class: 'leaf-board__kpi-value', text: k.value }),
        h('span', { class: 'leaf-board__kpi-deltas' },
          compareLabel ? h('span', { class: 'lb-cell__comparison-label', text: compareLabel }) : null,
          k.delta || h('span', { class: 'lb-delta--na', text: '--' })))));

    // 4 周净销售对比条
    const chartData = [
      { key: 'w2', label: (weeks.w2 || {}).label, value: (totals.w2 || {}).net_sales || 0 },
      { key: 'w1', label: (weeks.w1 || {}).label, value: (totals.w1 || {}).net_sales || 0 },
      { key: 'w0', label: (weeks.w0 || {}).label, value: (totals.w0 || {}).net_sales || 0 },
      { key: 'y0', label: (weeks.y0 || {}).label, value: (totals.y0 || {}).net_sales || 0 },
    ];
    const maxV = Math.max(...chartData.map((c) => Math.abs(c.value)), 1);
    const bars = h('div', { class: 'leaf-board__bars' }, ...chartData.map((c) => {
      const barClass = 'leaf-board__bar ' + (c.key === 'y0' ? 'is-y0' : c.key === 'w0' ? 'is-w0' : '');
      const barWidth = (Math.abs(c.value) / maxV * 100).toFixed(1) + '%';
      return h('div', { class: 'leaf-board__bar-row' },
        h('span', { class: 'leaf-board__bar-label', text: c.label }),
        h('div', { class: 'leaf-board__bar-track' },
          h('div', { class: barClass, style: 'width:' + barWidth })),
        h('span', { class: 'leaf-board__bar-value', text: '¥' + fmtWan(c.value) }));
    }));
    const headRow = h('tr', null,
      h('th', { class: 'leaf-board__th leaf-board__th--leaf' }, '叶子类目'),
      h('th', { class: 'leaf-board__th' }, '标品在售链接数'),
      h('th', { class: 'leaf-board__th' }, '净销售'),
      h('th', { class: 'leaf-board__th' }, '退款率'),
      h('th', { class: 'leaf-board__th' }, '访客数'),
      h('th', { class: 'leaf-board__th' }, '转化率'),
      h('th', { class: 'leaf-board__th' }, '客单价'),
      h('th', { class: 'leaf-board__th' }, '加购率'),
      h('th', { class: 'leaf-board__th' }, '推广花费'),
      h('th', { class: 'leaf-board__th' }, '费比'),
      h('th', { class: 'leaf-board__th' }, '利润额'),
      h('th', { class: 'leaf-board__th' }, '利润率'));

    const bodyRows = rows.map((row) => {
      const wk = row.weeks || {};
      const w = wk.w0 || {};
      const baselineWeek = baselineKey ? wk[baselineKey] || {} : {};
      const cell = (field, fmt) => {
        const v = w[field];
        let display = '--';
        if (field === 'net_sales' || field === 'ad_spend' || field === 'profit') display = v != null ? `¥${fmtWan(v)}` : '--';
        else if (field === 'ipv') display = fmtNum(v);
        else if (field === 'links_active') display = fmtNum(w.links_active);
        else display = fmt(v);
        const previous = baselineWeek[field];
        const denominator = field === 'links_active' ? previous || 1 : Math.abs(previous || 1);
        const change = previous != null && previous !== 0 && v != null ? (v - previous) / denominator : null;
        return lbCell(display, deltaBadge(change), compareLabel);
      };
      // 占比类指标用百分点
      const ratioCell = (field) => lbCell(
        fmtPct(w[field]), ppBadge(ppChange(w[field], baselineWeek[field])), compareLabel);
      return h('tr', { class: 'leaf-board__row' },
        h('td', { class: 'leaf-board__td leaf-board__td--leaf' }, row.leaf),
        lbCell(fmtNum(row.links_on_sale), null, null),
        cell('net_sales'),
        cell('refund_rate', (v) => fmtPct(v)),
        cell('ipv', (v) => fmtNum(v)),
        cell('cvr', (v) => fmtPct(v)),
        cell('aov', (v) => v != null ? `¥${Number(v).toFixed(1)}` : '--'),
        cell('cart_rate', (v) => fmtPct(v)),
        cell('ad_spend'),
        ratioCell('ad_ratio'),
        cell('profit'),
        ratioCell('profit_rate'));
    });

    const table = h('table', { class: 'leaf-board__table' }, h('thead', null, headRow), h('tbody', null, ...bodyRows));

    const hint = h('p', { class: 'panel__hint leaf-board__hint' },
      `口径：周=周一至周日；本周=${(weeks.w0 || {}).start}~${(weeks.w0 || {}).end}（实际覆盖 ${(data.data_quality || {}).w0_covered_days || '?'} 天）；${baselineKey ? `${compareLabel}基线=${(weeks[baselineKey] || {}).label || '--'}；` : '当前未应用类目周对比；'}比例指标由聚合后分子/分母计算；净销售/推广/利润绝对值<¥100 的类目行已隐藏。`);

    board.replaceChildren(
      h('article', { class: 'ui-panel pr-analysis-panel' },
        h('div', { class: 'panel__header' },
          h('div', null, h('h3', { class: 'panel__title', text: '叶子类目近 3 周对比看板' }),
            h('p', { class: 'panel__hint', text: compare.mode === 'custom'
              ? '类目周看板暂不支持自定义基线，变化值已隐藏；主复盘指标仍按所选自定义周期计算。'
              : `仅统计标品袜子；变化值按当前选择的${compareLabel || '不对比'}口径展示；在售链接数为当前在售快照。` }))),
        h('div', { class: 'ui-panel__body' },
          kpiRow, bars, table, hint)));
  }

  async function loadLeafBoard(showLoading = false) {
    if (showLoading) {
      state.leafBoardError = null;
      renderLeafBoard(state.leafBoard, null, true);
    }
    try {
      const r = await DemoApi.domainRequest('/api/category-analysis/leaf-weekly-board');
      state.leafBoard = r.data;
      state.leafBoardError = null;
    } catch (error) {
      state.leafBoardError = error;
    }
    renderLeafBoard(state.leafBoard, state.leafBoardError, false);
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
    const maxByColumn = {};
    columns.forEach((col) => {
      maxByColumn[col.key] = Math.max(...breakdown.rows.map((row) => Math.abs((row.metrics[col.key] || {}).value || 0)), 0.0001);
    });

    const thead = h('thead', null,
      h('tr', null,
        h('th', { class: 'pr-matrix-cell--category' }, '所属类目'),
        h('th', { class: 'pr-matrix-cell--status' }, '状态'),
        ...columns.map((col) => h('th', { class: 'pr-matrix-cell--metric', title: col.label }, col.label)),
      ),
    );
    const tbody = h('tbody', null, ...breakdown.rows.map((row) => {
      const tr = h('tr', { class: `pr-matrix-row ${matrixStatusClass(row.status)}` });
      tr.append(h('td', { class: 'pr-matrix-cell--category' }, row.category));
      tr.append(h('td', { class: 'pr-matrix-cell--status' }, h('span', { class: `pr-status-tag ${matrixStatusClass(row.status).replace('is-', '')}` }, matrixStatusLabel(row.status))));
      columns.forEach((col) => {
        tr.append(renderMatrixCell(row.metrics[col.key], maxByColumn[col.key], col.key));
      });
      return tr;
    }));
    const table = h('table', { class: 'pr-matrix-table' }, thead, tbody);
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

  function openActionReview(row) {
    if (!actionReviewDialog) {
      actionReviewDialog = h('dialog', { class: 'pr-action-dialog' });
      document.body.append(actionReviewDialog);
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
        snapshot ? h('p', { class: 'pr-material__empty', text: `创建时诊断快照：GSV ${safeMetric(snapshot.gsv, 'money')} · 上期 ${safeMetric(snapshot.prev_gsv, 'money')} · 变化 ${safeMetric(snapshot.change_rate, 'percent')}` }) : null,
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

  function renderExecutionAnalysis(context) {
    if (!els.executionAnalysis) return;
    const blocked = context.actions_blocked || [];
    const planned = context.actions_planned || [];
    const review = context.actions_review || [];
    const verify = context.actions_to_verify || [];
    const done = context.actions_done || [];
    els.executionAnalysis.replaceChildren(
      analysisPanel('\u5df2\u5b8c\u6210\u52a8\u4f5c', '\u53ea\u5c55\u793a\u5df2\u901a\u8fc7\u590d\u76d8\u9a8c\u6536\u7684\u52a8\u4f5c\u3002', renderActionListWithControls(done), '\u672c\u671f\u6682\u65e0\u5df2\u5b8c\u6210\u52a8\u4f5c\u3002'),
      analysisPanel('\u6267\u884c\u4e2d\u4e0e\u89c2\u5bdf\u4e2d', '\u6309\u73b0\u6709\u72b6\u6001\u673a\u5236\u63a8\u8fdb\u6267\u884c\u3001\u89c2\u5bdf\u548c\u91cd\u7b97\u3002', renderActionListWithControls(planned), '\u5f53\u524d\u6ca1\u6709\u6267\u884c\u4e2d\u52a8\u4f5c\u3002'),
      analysisPanel('\u672c\u671f\u5f85\u9a8c\u8bc1', '\u6765\u81ea\u4e0a\u4e00\u5468\u6216\u4e0a\u4e00\u6708\u7684\u52a8\u4f5c\uff0c\u5728\u672c\u671f\u56de\u6d41\u7ed3\u679c\u3002', renderActionListWithControls(verify), '\u5f53\u524d\u6682\u65e0\u4e0a\u671f\u5f85\u9a8c\u8bc1\u52a8\u4f5c\u3002'),
      analysisPanel('\u5f85\u590d\u76d8\u9a8c\u6536', '\u89c2\u5bdf\u7a97\u53e3\u5b8c\u6210\u540e\uff0c\u5728\u8fd9\u91cc\u786e\u8ba4\u6709\u6548\u6027\u5e76\u56de\u6d41\u4e0b\u4e00\u6b65\u3002', renderActionListWithControls(review), '\u5f53\u524d\u6ca1\u6709\u5f85\u590d\u76d8\u52a8\u4f5c\u3002'),
      analysisPanel('\u963b\u585e\u4e0e\u5f85\u5904\u7406', '\u963b\u585e\u9879\u9700\u5728\u590d\u76d8\u7ed3\u8bba\u4e2d\u8bf4\u660e\u6240\u9700\u8d44\u6e90\u548c\u89e3\u9664\u6761\u4ef6\u3002', renderActionListWithControls(blocked), '\u5f53\u524d\u6ca1\u6709\u963b\u585e\u52a8\u4f5c\u3002'),
    );
  }

  function activateWorkbench(key) {
    // 切走货品页时字段设置浮层失去锚点，先收起。
    productColumns.closeProductFieldPopover();
    document.querySelectorAll('[data-pr-workbench-tab]').forEach((tab) => tab.classList.toggle('is-active', tab.dataset.prWorkbenchTab === key));
    document.querySelectorAll('[data-pr-workbench-panel]').forEach((panel) => panel.classList.toggle('is-active', panel.dataset.prWorkbenchPanel === key));
    // 矩阵 / 类目拆解若还没拿到数据（首次加载失败、或后端刚重启），
    // 切到这个页签时就地补拉一次，用户不必整页刷新。
    if (key === 'matrix' && !state.matrix) reloadMatrixPanels();
    if (key === 'category' && !state.categoryBreakdown) reloadMatrixPanels();
  }

  function renderWorkbench(context, review) {
    renderCommandCenter(context);
    renderProductAnalysis(context);
    renderExecutionAnalysis(context);
    renderChannelAnalysis(context);
    renderMarketAnalysis(context);
    renderMatrix(state.matrix, state.matrixError);
    renderCategoryBreakdown(state.categoryBreakdown, state.categoryError);
    renderOverview(context);
    renderSections(state.template, context, review);
  }

  function renderKpiGrid(metrics) {
    const grid = h('div', { class: 'pr-kpi-grid' });
    if (!metrics.items.length) {
      grid.append(h('p', { class: 'pr-material__empty', text: '本期暂无指标数据。' }));
      return grid;
    }
    metrics.items.forEach((item) => {
      grid.append(h('div', { class: 'pr-kpi' },
        h('div', { class: 'pr-kpi__label', text: item.label }),
        h('div', { class: 'pr-kpi__value', text: formatValue(item.value, item.format) }),
        deltaNode(item),
      ));
    });
    return grid;
  }

  // ------------------------------------------------------------- 素材渲染
  function materialBlock(title, bodyNode, emptyText) {
    const block = h('div', { class: 'pr-material' }, h('p', { class: 'pr-material__title', text: title }));
    if (bodyNode) block.append(bodyNode);
    else if (emptyText) block.append(h('p', { class: 'pr-material__empty', text: emptyText }));
    return block;
  }

  // ------------------------------------------------- 货品表格（列可配置）
  // 实现已拆至 pages/period-review/product-columns.js（deps 显式注入）：
  // 列定义 / 列开关 / 字段设置浮层的状态与行为都归该模块。
  const productColumns = window.createProductColumns({
    h, productShare, declineRate, safeMetric, openProductDiagnosis, renderProductAnalysis,
  });

  // 目标卡与「目标 vs 实际」表已拆至 pages/period-review/target-cards.js：
  // 输入口径换算、达成率配色、即时重算的状态与行为都归该模块。
  const targetCards = window.createTargetCards({ h, formatValue, state, els });

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
      wrap.append(materialBlock('市场事实：商品榜监控', h('table', { class: 'pr-table' }, h('thead', null, tr), h('tbody', null, ...body))));
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
      wrap.append(materialBlock('需求信号：搜索词监控', h('table', { class: 'pr-table' }, h('thead', null, tr), h('tbody', null, ...body))));
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
      const tr = h('tr', null, h('th', { text: '竞店' }), h('th', { class: 'num', text: '支付买家' }), h('th', { class: 'num', text: 'UV' }), h('th', { class: 'num', text: '支付率' }), h('th', { class: 'num', text: '支付买家变化' }), h('th', { text: '状态' }));
      const body = market.rivals.map((row) => h('tr', null,
        h('td', { text: row.shop_name || '--' }),
        h('td', { class: 'num', text: formatCompact(row.pay_buyer_count) }),
        h('td', { class: 'num', text: formatCompact(row.uv) }),
        h('td', { class: 'num', text: row.pay_rate === null || row.pay_rate === undefined ? '--' : `${(row.pay_rate * 100).toFixed(2)}%` }),
        h('td', { class: 'num', text: row.pay_buyer_change_rate === null || row.pay_buyer_change_rate === undefined ? '--' : `${row.pay_buyer_change_rate > 0 ? '+' : ''}${(row.pay_buyer_change_rate * 100).toFixed(1)}%` }),
        h('td', null, stateTag(row.status === 'rising' ? '增长' : row.status === 'falling' ? '下滑' : row.status === 'insufficient_coverage' ? '覆盖不足' : '稳定', row.status === 'rising' ? 'warning' : row.status === 'falling' ? 'good' : 'info')),
      ));
      wrap.append(materialBlock('竞店动态', h('table', { class: 'pr-table' }, h('thead', null, tr), h('tbody', null, ...body))));
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
    push('费比', formatValue(ads.current.ad_ratio, 'percent'));
    if (cmp && ads.delta && ads.delta.ad_spend_change !== undefined) push(`${cmp}花费变化`, `${ads.delta.ad_spend_change > 0 ? '+' : ''}${ads.delta.ad_spend_change}%`);
    if (cmp && ads.delta && ads.delta.ad_ratio_delta_pt !== undefined) push(`${cmp}费比变化`, `${ads.delta.ad_ratio_delta_pt > 0 ? '+' : ''}${ads.delta.ad_ratio_delta_pt}pt`);
    return h('div', { class: 'pr-materials' }, materialBlock('广告本期', h('div', { class: 'pr-target' }, ...items)));
  }

  function materialFor(key, context) {
    switch (key) {
      case 'products': {
        const wrap = h('div', { class: 'pr-materials' });
        const top = productColumns.renderProductTable(context.products && context.products.top, false);
        const decline = productColumns.renderProductTable(context.products && context.products.decline, true);
        wrap.append(materialBlock('GSV TOP10', top, '本期没有正向销售商品。'));
        wrap.append(materialBlock('环比下滑 TOP10', decline, '缺少上期可比数据。'));
        return wrap;
      }
      case 'market':
        return renderMarket(context.market);
      case 'ads':
        return renderAds(context.ads);
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
      default:
        return null;
    }
  }

  // --------------------------------------------------------------- 段落渲染
  function renderSections(template, context, review) {
    if (!els.sections) return;
    els.sections.replaceChildren(...template.map((section, index) => sectionNode(section, index, context, review)));
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
          section.required ? h('span', { class: 'pr-section__required', text: '必填' }) : null),
        h('p', { class: 'panel__hint', text: section.hint || '' }),
      ));

    const body = h('div', { class: 'ui-panel__body' });
    const materialKeys = (section.materials || []).filter((key) => key !== 'metrics' && key !== 'target_path');
    if (materialKeys.length) {
      const evidence = h('details', { class: 'pr-evidence' },
        h('summary', { text: `展开系统证据（${materialKeys.length} 个数据块）` }),
        h('div', { class: 'pr-evidence__body' }, ...materialKeys.map((key) => materialFor(key, context)).filter(Boolean)),
      );
      body.append(evidence);
    } else if ((section.materials || []).some((key) => key === 'metrics' || key === 'target_path')) {
      body.append(h('p', { class: 'pr-material__empty', text: '业绩与目标差距已在上方驾驶舱展示，这里只填写结论与达成路径。' }));
    }

    const textarea = h('textarea', {
      'data-pr-input': section.key,
      placeholder: section.placeholder || '',
      rows: 4,
    });
    textarea.value = saved.text || '';
    textarea.addEventListener('input', () => {
      textarea.classList.toggle('is-missing', Boolean(section.required) && !textarea.value.trim());
      updateStatusText();
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

    panel.append(header, body);
    return panel;
  }

  // ------------------------------------------------------------------ 状态
  function collectSections() {
    const sections = {};
    els.sections.querySelectorAll('[data-pr-input]').forEach((node) => {
      sections[node.dataset.prInput] = { text: node.value.trim() };
    });
    return sections;
  }

  function missingRequired() {
    return state.template
      .filter((section) => section.required)
      .filter((section) => {
        const node = els.sections.querySelector(`[data-pr-input="${section.key}"]`);
        return !node || !node.value.trim();
      })
      .map((section) => section.title);
  }

  function updateStatusText() {
    if (!els.statusText) return;
    const missing = missingRequired();
    const period = currentPeriod();
    els.statusText.textContent = missing.length
      ? `${period} · 还有 ${missing.length} 个必填段落未填写，可先存草稿。`
      : `${period} · 必填段落已完成，可保存。`;
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
    renderLeafBoard(state.leafBoard, state.leafBoardError, false);
    renderCategoryBreakdown(state.categoryBreakdown, state.categoryError);
  }

  function reloadMatrixPanels() {
    const periodKey = currentPeriod();
    if (!periodKey) return;
    loadMatrixPanels(periodKey, { showLoading: true });
  }

  async function load() {
    const token = ++loadToken;
    const periodKey = currentPeriod();
    if (!periodKey) return;
    stateBanner('加载中…', 'loading');
    if (els.save) els.save.disabled = true;

    try {
      await Promise.all([loadTemplates(), loadCategories(), loadPeriodOptions()]);
      if (state.selectedPeriodKey && !(state.periodOptions[state.mode] || [])
        .some((item) => item.key === state.selectedPeriodKey)) {
        state.selectedPeriodKey = '';
      }
      syncRangeToSelectedPeriod();
      state.template = state.templates[state.mode] || [];

      const [contextResponse, reviewResponse] = await Promise.all([
        DemoApi.domainRequest(`/api/period-reviews/${state.mode}/${encodeURIComponent(periodKey)}/context${compareQuery()}`),
        DemoApi.domainRequest(`/api/period-reviews/${state.mode}/${encodeURIComponent(periodKey)}`),
      ]);
      if (token !== loadToken) return;

      state.context = contextResponse.data.context;
      state.review = reviewResponse.data.review || null;

      if (!state.selectedPeriodKey) state.selectedPeriodKey = periodKey;
      renderPeriodPicker();
      updateReviewUrl();
      renderPeriodLabel(state.context.period);
      renderCompareControls(state.context);
      renderWorkbench(state.context, state.review);
      // 矩阵 / 类目拆解独立拉取：不阻塞上面的渲染，也不会被上面的失败带崩。
      loadMatrixPanels(periodKey);

      targetCards.fillTargetInputs(state.review);
      if (els.reviewer && state.review && state.review.reviewer) els.reviewer.value = state.review.reviewer;
      if (els.statusSelect && state.review && state.review.status) els.statusSelect.value = state.review.status;

      const missing = state.context.metrics.has_data ? [] : state.context.missing_inputs;
      const compareLabel = (state.context.compare && state.context.compare.label) || '不对比';
      stateBanner(
        missing.length
          ? `本期缺少数据源：${missing.join('、')}。仍可手动填写复盘结论。`
          : `素材已更新：${state.context.period.label}（${categoryLabelOf() || '全部品类'}）· 对比 ${compareLabel}。`,
        missing.length ? 'no-data' : '',
      );
      renderCategoryNote();
      const coverageText = coverageNotice(state.context);
      if (coverageText && els.state) stateBanner(`${els.state.textContent} \u00b7 ${coverageText}`, 'no-data');
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
          setMode(row.period_type);
          // 周期由顶栏范围决定，历史复盘只能提示它属于哪个周期，不能反向改写时间范围。
          if (row.period_key !== periodKeyFromRange()) {
            stateBanner(`该复盘属于 ${row.period_key}，请在上方顶栏「统计时间」切到对应周期查看。`, 'insufficient-data');
          }
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
      storeCompareChoice({ mode: 'previous', period: '' });
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

  document.querySelectorAll('[data-pr-workbench-tab]').forEach((tab) => {
    tab.addEventListener('click', () => activateWorkbench(tab.dataset.prWorkbenchTab));
  });

  els.modeButtons.forEach((button) => button.addEventListener('click', () => setMode(button.dataset.prMode)));
  els.period?.addEventListener('change', () => {
    const selected = (state.periodOptions[state.mode] || []).find((item) => item.key === els.period.value);
    if (!selected || !window.TmallDateRange?.setReviewRange) return;
    state.selectedPeriodKey = selected.key;
    syncRangeToSelectedPeriod();
    load();
  });
  els.refresh?.addEventListener('click', () => load());
  els.target?.addEventListener('input', targetCards.refreshTargetCard);
  [els.targetProfit, els.targetAdSpend, els.targetNetExpenseRatio]
    .forEach((input) => input?.addEventListener('input', targetCards.refreshTargetTable));
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
      storeCompareChoice({ mode: 'custom', period });
    } else {
      storeCompareChoice({ mode, period: '' });
    }
    load();
  });
  els.comparePeriod?.addEventListener('change', () => {
    storeCompareChoice({ mode: 'custom', period: els.comparePeriod.value });
    load();
  });
  els.save?.addEventListener('click', save);
  window.addEventListener('tmall:refresh', () => load());
  // 顶栏统一时间范围一变化，复盘周期随之重算
  window.addEventListener('tmall:date-range-change', () => {
    if (!syncingReviewRange) state.selectedPeriodKey = '';
    load();
  });

  updateModeUi();
  load();
  loadHistory();
})();
