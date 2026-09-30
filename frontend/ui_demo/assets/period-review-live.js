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
    trafficAnalysis: document.querySelector('[data-pr-traffic-analysis]'),
    promotionAnalysis: document.querySelector('[data-pr-promotion-analysis]'),
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
    form.append(
      actionField('动作目的', 'purpose_note', 'textarea', withDelta ? `${row.title || row.product_id} 销售额下滑，需制定恢复动作` : `${row.title || row.product_id} 销售贡献跟进`, true),
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
  // 周期内分解表（月复盘=月内分周，周复盘=期内按日），来自用户月复盘框架：
  // 品类汇总的销售/利润指标要有周维度表格方便对比。
  const BREAKDOWN_COLUMNS = [
    ['gsv', '销售额', 'money'],
    ['net_sales', '净销售额', 'money'],
    ['profit', '利润', 'money'],
    ['visitors', '访客', 'number'],
    ['conversion', '转化率', 'percent'],
    ['aov', '客单价', 'money'],
    ['cart_rate', '加购率', 'percent'],
    ['ad_spend', '推广花费', 'money'],
    ['ad_ratio', '费比', 'percent'],
    ['roi', 'ROI', 'decimal'],
    ['paid_cpc', '付费访客成本', 'money'],
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

  function renderOverview(context) {
    if (!els.overview) return;
    const period = context.period;
    const label = (context.category && context.category.label) || '全部品类';
    els.overview.hidden = false;
    const breakdown = context.breakdown;
    const breakdownTitle = breakdown && breakdown.grain === 'week' ? '月内分周指标' : '期内按日指标';
    els.overview.replaceChildren(
      h('div', { class: 'pr-overview__head' },
        h('h3', { text: '业绩全景' }),
        h('span', { text: `${period.label} · ${period.start} ~ ${period.end} · 品类：${label}` }),
      ),
      renderKpiGrid(context.metrics),
      targetCards.renderTarget(context.target_path),
      targetCards.renderTargetTable(context.target_path.targets, targetCards.targetTimeProgress(period)),
      breakdown && breakdown.rows && breakdown.rows.length
        ? h('div', { class: 'pr-overview__breakdown' },
          h('h4', { text: breakdownTitle }),
          h('p', { class: 'pr-material__empty', text: breakdown.grain === 'week'
            ? '按月内分周汇总（W1 从 1 号到第一个周日）；缺失的天不补 0。'
            : '按天汇总；缺数据的天不显示。' }),
          breakdownTable(breakdown))
        : null,
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
    const dangerCount = (context.anomalies || []).filter((item) => item.level === 'danger' || item.level === 'warning').length;
    const blockedCount = (context.actions_blocked || []).length;
    const plannedCount = (context.actions_planned || []).length;
    els.commandCenter.hidden = false;
    els.commandCenter.replaceChildren(
      // 三大指标完成率卡（对齐月复盘 XMind「完成情况分析」）：
      // 净销售额 / 净利润 / 净费比，口径与复盘设置目标同源。
      metricCards.renderMetricCards(),
      // 紧凑状态条：风险与执行信号一行带过，点击直达对应工作区。
      h('div', { class: 'pr-command-center__strip' },
        h('button', { type: 'button', class: 'pr-strip-item', onclick: () => activateWorkbench('diagnosis') },
          stateTag(dangerCount + blockedCount ? '需关注' : '正常', dangerCount + blockedCount ? 'warning' : 'good'),
          h('span', { text: `风险 ${dangerCount + blockedCount}（异常 ${dangerCount} · 阻塞 ${blockedCount}）` })),
        h('button', { type: 'button', class: 'pr-strip-item', onclick: () => activateWorkbench('execution') },
          stateTag(plannedCount ? '进行中' : '空闲', plannedCount ? 'info' : 'good'),
          h('span', { text: `待落地动作 ${plannedCount}` })),
        h('button', { type: 'button', class: 'pr-strip-item', onclick: () => activateWorkbench('diagnosis') },
          h('span', { text: '拆因分析 →' })),
      ),
    );
    // 周期摘要写到页头说明位，替代驾驶舱内部标题区，减少一层重复信息。
    const headSummary = document.querySelector('.pr-page-header p');
    if (headSummary && context.period && context.period.start) {
      headSummary.textContent = context.metrics && context.metrics.has_data
        ? `${context.period.label}（${context.period.start} ~ ${context.period.end}）· 先看三大指标完成情况，再定位商品、推广与执行问题。`
        : '当前周期缺少可用经营事实，先补齐数据后再形成结论。';
    }
  }

  // ------------------------------------------------- 单品周趋势预览（弹窗）
  // 点击货品榜「趋势」按钮：近 8 周销售额/访客/转化 SVG 折线，无图表库依赖。
  let trendDialog = null;
  const TREND_METRICS = [
    ['gsv', '销售额（元）', 'money'],
    ['visitors', '访客数', 'number'],
    ['conversion', '转化率', 'percent'],
  ];

  function trendSvg(rows, key, format) {
    const values = rows.map((row) => (row[key] === null || row[key] === undefined ? null : Number(row[key])));
    const valid = values.filter((value) => value !== null);
    if (valid.length < 2) return h('p', { class: 'pr-material__empty', text: '该指标可用数据点不足，无法画趋势。' });
    const width = 560;
    const height = 150;
    const pad = 28;
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
      const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
      circle.setAttribute('cx', String(pad + index * stepX));
      circle.setAttribute('cy', String(scaleY(value) + baseline));
      circle.setAttribute('r', '3');
      svg.append(circle);
    });
    const wrap = h('div', { class: 'pr-trend-chart' }, svg,
      h('div', { class: 'pr-trend-axis' },
        h('span', { text: formatValue(min, format) }),
        h('span', { text: formatValue(max, format) })));
    return wrap;
  }

  async function openProductTrend(row) {
    if (!trendDialog) {
      trendDialog = h('dialog', { class: 'pr-action-dialog pr-trend-dialog' });
      document.body.append(trendDialog);
    }
    trendDialog.replaceChildren(
      h('div', { class: 'pr-action-dialog__head' },
        h('div', null,
          h('span', { class: 'section-kicker', text: '周维度趋势' }),
          h('h3', { text: row.title || row.product_id }),
          h('p', { text: `商品 ID：${row.product_id} · 近 8 周（月内分周口径）` })),
        h('button', { type: 'button', class: 'pr-dialog-close', 'aria-label': '关闭', onclick: () => trendDialog.close(), text: '×' })),
      h('div', { class: 'pr-diagnostic-block', 'data-pr-trend-loading': '' },
        h('p', { class: 'pr-material__empty', text: '正在读取周趋势…' })),
    );
    if (!trendDialog.open) trendDialog.showModal();

    let data = null;
    let error = null;
    try {
      const response = await DemoApi.domainRequest(
        `/api/period-reviews/product-trend/${encodeURIComponent(row.product_id)}?weeks=8`);
      data = response.data;
    } catch (err) { error = err; }

    const loading = trendDialog.querySelector('[data-pr-trend-loading]');
    const body = error || !data || !data.available || !data.weeks.length
      ? h('div', { class: 'pr-diagnostic-block' },
        h('p', { class: 'pr-material__empty', text: error ? `趋势读取失败：${describeRequestError(error)}` : '该商品近 8 周没有日数据，无法生成趋势。' }))
      : h('div', { class: 'pr-diagnostic-block' },
        ...TREND_METRICS.map(([key, label, format]) => h('div', { class: 'pr-trend-metric' },
          h('h4', { text: label }),
          trendSvg(data.weeks, key, format),
          h('div', { class: 'pr-trend-labels' },
            ...data.weeks.map((week, index) => h('span', { text: `W${index + 1}`, title: `${week.label}（${week.start} ~ ${week.end}）` }))),
        )),
        h('p', { class: 'pr-material__empty', text: '横轴 W1→W8 为最近 8 个完整月内周，悬停可见具体周区间；本周为进行中数据不纳入。' }));
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

  function renderProductAnalysis(context) {
    if (!els.productAnalysis) return;
    productColumns.rememberContext(context);
    const products = context.products || {};
    // 每张榜单一份字段设置工具栏：列开关按榜独立（默认列随榜单定位差异化）。
    const board = productColumns.productBoardPanel;
    els.productAnalysis.replaceChildren(
      problemItemsPanel(products.problem_items),
      board('销售贡献 TOP10', '按本期销售额 排序，先识别需要保住的核心商品。', products.top, 'top', '本期没有正向销售商品。'),
      board('下滑商品 TOP10', '按相对上期的销售额变化排序，作为异常诊断入口。', products.decline, 'decline', '缺少可比周期数据。'),
      board('付费单品 TOP10', '按本期推广花费排序，看钱主要花在哪些商品上（广告-单品维度入口）。', products.paid, 'paid', '本期没有推广花费记录。'),
      board('盈利 TOP10', '按本期经营利润（支付预估）排序的赚钱商品。', products.profit, 'profit', '本期没有正利润商品。'),
      board('亏损 TOP10', '按本期经营利润倒序，优先排查亏损原因。', products.loss, 'loss', '本期没有亏损商品。'),
      board('新品 · 净销售额 TOP10', '最近 60 天上架的商品按净销售额排序（新品定义=周期结束日前 60 天内上架）。', products.new, 'new', '最近 60 天上架的商品暂无销售。'),
      board('新品 · 付费 TOP10', '最近 60 天上架的商品按推广花费排序。', products.new_paid, 'new_paid', '最近 60 天上架的商品暂无推广花费。'),
    );
  }

  /** 流量来源拆解（自家店铺流量诊断）——与市场监控（外部行业/竞对）分节渲染。 */
  function renderTrafficAnalysis(context) {
    if (!els.trafficAnalysis) return;
    const traffic = context.dimensions?.traffic || {};
    els.trafficAnalysis.replaceChildren(
      analysisPanel('流量来源拆解', `流量覆盖 ${traffic.sample_days || 0}/${traffic.period_days || '--'} 天`, trafficTable(traffic), '暂无搜索、推荐、付费或自然流量拆解数据。'),
    );
  }

  function renderMarketAnalysis(context) {
    if (!els.marketAnalysis) return;
    const period = context.period || {};
    // 行业深链入口（XMind：趋势市场 / 蓝海市场 / 8 大归类 / 词根需求在专页）：
    // 复盘页只做摘要，深度分析跳市场分析页（带复盘区间日期）。
    const marketLink = h('p', { class: 'pr-market-links' },
      h('a', { class: 'pr-anchor-link', href: `/market-ranking?start=${period.start || ''}&end=${period.end || ''}`, text: '行业趋势 / 蓝海市场 →' }),
      h('a', { class: 'pr-anchor-link', href: `/keyword-promotion?start=${period.start || ''}&end=${period.end || ''}`, text: '关键词归类 / 词根需求 →' }));
    els.marketAnalysis.replaceChildren(
      analysisPanel('市场监控（摘要 + 深链）', '先看可复现事实，再看系统观察；价格、利润和评价结论仍需补证。', h('div', null, marketLink, renderMarket(context.market)), '暂无市场批次。'),
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
          item.image_url ? h('img', { src: item.image_url, alt: '', loading: 'lazy' }) : null,
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
      ? '当前推广数据源没有「商品×渠道」粒度（渠道行不带商品映射），因此只展示商品级合计；渠道拆分见上方「推广渠道拆解」。'
      : '按推广花费排序的商品级投放指标；费比 = 花费 ÷ 归因成交，拉新成本 = 花费 ÷ 成交新客。';
    return analysisPanel('广告单品 TOP20 消耗', hint, table, null);
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
        renderPromotionItems(context.promotion_items),
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
    const timeline = h('div', { class: 'pr-schedule' }, ...buckets.map((b) => {
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
      return h('div', { class: `pr-schedule__bucket ${items.length ? 'has-items' : ''}`.trim() },
        h('div', { class: 'pr-schedule__bucket-head' },
          h('span', { class: 'pr-schedule__bucket-label', text: state.mode === 'month' ? b.label : `${b.label}号` }),
          h('small', { text: `${b.start.slice(5)} ~ ${b.end.slice(5)}` })),
        items.length
          ? h('ul', { class: 'pr-schedule__items' }, ...itemNodes)
          : h('p', { class: 'pr-schedule__empty', text: '无排期动作' }));
    }));
    return analysisPanel(
      state.mode === 'month' ? '本月任务排期（按周）' : '本周任务排期（按日）',
      '动作按计划日期落位；点击动作打开执行链路。数据来自动作状态机，不另建任务体系。',
      timeline,
      null,
    );
  }

  function renderExecutionAnalysis(context) {
    if (!els.executionAnalysis) return;
    const blocked = context.actions_blocked || [];
    const planned = context.actions_planned || [];
    const review = context.actions_review || [];
    const verify = context.actions_to_verify || [];
    const done = context.actions_done || [];
    els.executionAnalysis.replaceChildren(
      renderScheduleTimeline(context) || null,
      analysisPanel('\u5df2\u5b8c\u6210\u52a8\u4f5c', '\u53ea\u5c55\u793a\u5df2\u901a\u8fc7\u590d\u76d8\u9a8c\u6536\u7684\u52a8\u4f5c\u3002', renderActionListWithControls(done), '\u672c\u671f\u6682\u65e0\u5df2\u5b8c\u6210\u52a8\u4f5c\u3002'),
      analysisPanel('\u6267\u884c\u4e2d\u4e0e\u89c2\u5bdf\u4e2d', '\u6309\u73b0\u6709\u72b6\u6001\u673a\u5236\u63a8\u8fdb\u6267\u884c\u3001\u89c2\u5bdf\u548c\u91cd\u7b97\u3002', renderActionListWithControls(planned), '\u5f53\u524d\u6ca1\u6709\u6267\u884c\u4e2d\u52a8\u4f5c\u3002'),
      analysisPanel('\u672c\u671f\u5f85\u9a8c\u8bc1', '\u6765\u81ea\u4e0a\u4e00\u5468\u6216\u4e0a\u4e00\u6708\u7684\u52a8\u4f5c\uff0c\u5728\u672c\u671f\u56de\u6d41\u7ed3\u679c\u3002', renderActionListWithControls(verify), '\u5f53\u524d\u6682\u65e0\u4e0a\u671f\u5f85\u9a8c\u8bc1\u52a8\u4f5c\u3002'),
      analysisPanel('\u5f85\u590d\u76d8\u9a8c\u6536', '\u89c2\u5bdf\u7a97\u53e3\u5b8c\u6210\u540e\uff0c\u5728\u8fd9\u91cc\u786e\u8ba4\u6709\u6548\u6027\u5e76\u56de\u6d41\u4e0b\u4e00\u6b65\u3002', renderActionListWithControls(review), '\u5f53\u524d\u6ca1\u6709\u5f85\u590d\u76d8\u52a8\u4f5c\u3002'),
      analysisPanel('\u963b\u585e\u4e0e\u5f85\u5904\u7406', '\u963b\u585e\u9879\u9700\u5728\u590d\u76d8\u7ed3\u8bba\u4e2d\u8bf4\u660e\u6240\u9700\u8d44\u6e90\u548c\u89e3\u9664\u6761\u4ef6\u3002', renderActionListWithControls(blocked), '\u5f53\u524d\u6ca1\u6709\u963b\u585e\u52a8\u4f5c\u3002'),
    );
  }

  function activateWorkbench(key) {
    // 切走货品区时字段设置对话框失去锚点，先收起。
    productColumns.closeProductFieldPopover();
    document.querySelectorAll('[data-pr-workbench-tab]').forEach((tab) => tab.classList.toggle('is-active', tab.dataset.prWorkbenchTab === key));
    document.querySelectorAll('[data-pr-workbench-panel]').forEach((panel) => panel.classList.toggle('is-active', panel.dataset.prWorkbenchPanel === key));
    // 数据参考区（矩阵 / 类目拆解）若还没拿到数据（首次加载失败、或后端刚重启），
    // 切到这个页签时就地补拉一次，用户不必整页刷新。
    if (key === 'reference' && (!state.matrix || !state.categoryBreakdown)) reloadMatrixPanels();
  }

  function renderWorkbench(context, review) {
    renderCommandCenter(context);
    renderProductAnalysis(context);
    renderExecutionAnalysis(context);
    renderChannelAnalysis(context);
    renderTrafficAnalysis(context);
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
    h, productShare, declineRate, safeMetric, openProductDiagnosis, openProductTrend, renderProductAnalysis,
  });

  // 目标卡与「目标 vs 实际」表已拆至 pages/period-review/target-cards.js：
  // 输入口径换算、达成率配色、即时重算的状态与行为都归该模块。
  const targetCards = window.createTargetCards({ h, formatValue, state, els });

  // 三大指标完成率卡（净销售额/净利润/净费比）已拆至 pages/period-review/metric-cards.js：
  // 口径与复盘设置目标同源，完成率与配色方向沿用后端 _target_rows。
  const metricCards = window.createMetricCards({ h, state });

  // 复盘导出 Markdown 已拆至 pages/period-review/review-export.js：
  // 组装三大指标 + 六段三段式 + 问题单品 + 动作清单，纯前端 Blob 下载。
  const reviewExport = window.createReviewExport({ h, state });

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

  function materialFor(key, context) {
    switch (key) {
      case 'products': {
        const wrap = h('div', { class: 'pr-materials' });
        const top = productColumns.renderProductTable(context.products && context.products.top, false);
        const decline = productColumns.renderProductTable(context.products && context.products.decline, true);
        wrap.append(materialBlock('销售额 TOP10', top, '本期没有正向销售商品。'));
        wrap.append(materialBlock('环比下滑 TOP10', decline, '缺少上期可比数据。'));
        return wrap;
      }
      case 'market':
        return renderMarket(context.market);
      case 'ads':
        return renderAds(context.ads);
      case 'promotion_items': {
        const items = (context.promotion_items && context.promotion_items.items) || [];
        return materialBlock('广告单品 TOP20 消耗（摘要）', items.length
          ? h('ul', { class: 'pr-list' }, ...items.slice(0, 10).map((item) => h('li', null,
            h('strong', { text: `${item.title || item.product_id} · 花费 ${safeMetric(item.totals && item.totals.ad_spend, 'money')}` }),
            ` · ROI ${safeMetric(item.totals && item.totals.roi, 'decimal')} · 直接投产 ${safeMetric(item.totals && item.totals.direct_roi, 'decimal')} · 拉新成本 ${safeMetric(item.totals && item.totals.new_cost, 'money')}`)))
          : null, '本期没有商品级推广数据。');
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
    // 系统证据节点：三段式段落挂进「根因」子段（写根因时证据就在手边），
    // 单框段落（day 模板）保持挂在段落顶部。
    let evidenceNode = null;
    if (materialKeys.length) {
      evidenceNode = h('details', { class: 'pr-evidence' },
        h('summary', { text: `展开系统证据（${materialKeys.length} 个数据块）` }),
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
        // 老复盘无 subsections 时，analysis 子段回填原 text（只读迁移，不覆盖库）。
        const savedText = savedSubs[sub.key]
          || (sub.key === 'analysis' ? (saved.text || '') : '');
        const value = draft || savedText;
        if (draft && draft !== savedText) anyDraftRestored = true;
        const textarea = h('textarea', {
          'data-pr-input': section.key,
          'data-pr-subsection': sub.key,
          placeholder: section.placeholder || '',
          rows: 3,
        });
        textarea.value = value;
        textarea.addEventListener('input', () => {
          textarea.classList.toggle('is-missing', Boolean(sub.required) && !textarea.value.trim());
          updateStatusText();
          storeSectionDraft(draftKey, textarea.value);
        });
        if (sub.required && !value.trim()) textarea.classList.add('is-missing');
        const subWrap = h('div', { class: 'pr-subsection' },
          h('label', { class: 'pr-subsection__label' },
            h('span', { text: sub.title }),
            sub.required ? h('em', { text: '必填' }) : null),
          textarea);
        // 根因子段内嵌系统证据：写根因时证据就在手边，不用折叠区来回对照。
        if (sub.key === 'root_cause' && evidenceNode) subWrap.append(evidenceNode);
        wrap.append(subWrap);
      });
      if (anyDraftRestored) {
        body.append(h('p', { class: 'pr-toolbar__status pr-draft-note', role: 'status', text: '已恢复未保存的本地草稿；保存复盘后将清除。' }));
      }
      body.append(wrap);
    } else {
      // 单框段落（day 模板等）：证据保持挂在段落顶部。
      if (evidenceNode) body.append(evidenceNode);
      const textarea = h('textarea', {
        'data-pr-input': section.key,
        placeholder: section.placeholder || '',
        rows: 4,
      });
      // 恢复顺序：已保存内容 > 本地草稿（未保存的编辑在切周期/刷新后不丢）。
      const draft = readSectionDraft(section.key);
      const savedText = saved.text || '';
      textarea.value = draft || savedText;
      if (draft && draft !== savedText) {
        body.append(h('p', { class: 'pr-toolbar__status pr-draft-note', role: 'status', text: '已恢复未保存的本地草稿；保存复盘后将清除。' }));
      }
      textarea.addEventListener('input', () => {
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
    leafBoard.renderLeafBoard(state.leafBoard, state.leafBoardError, false);
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
      // 复盘设置折叠面板：任何目标未录时保持展开（引导补录），全录则收起减噪。
      const settingsPanel = document.querySelector('[data-pr-settings]');
      if (settingsPanel) {
        const anyTargetEmpty = [els.target, els.targetProfit, els.targetAdSpend, els.targetNetExpenseRatio]
          .some((input) => !input || !String(input.value).trim());
        settingsPanel.open = anyTargetEmpty;
      }

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

  // 拆因分析长页（约 13 屏）的分节锚点：点击滚到对应分节，免得手滚找市场监控。
  document.querySelectorAll('[data-pr-diagnosis-anchor]').forEach((chip) => {
    chip.addEventListener('click', () => {
      const heading = document.querySelector(`[data-pr-diagnosis-section="${chip.dataset.prDiagnosisAnchor}"]`);
      if (heading) heading.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
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
  // 目标输入即时联动：先更新 target-cards 的目标卡/表（会回写 context.target_path.targets），
  // 再重渲染驾驶舱三大指标卡，让完成率「填了立刻有反应」。
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
    if (!syncingReviewRange) state.selectedPeriodKey = '';
    load();
  });

  updateModeUi();
  load();
  loadHistory();
})();
