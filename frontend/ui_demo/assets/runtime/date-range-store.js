(function (global) {
  'use strict';

  /** 日期范围状态仓：统一时间选择器（粒度 + 预设 + 日期 + 对比单入口弹层）。
   *
   *  本模块拥有日期范围的全部状态与行为：时间粒度切换（按日/按周/按月，
   *  对齐 weekly_data / monthly_data 聚合）、快捷预设（滚动与自然周期分组）、
   *  自定义日期输入 + 双月日历（悬停预览 / 年份快跳）、
   *  草稿确认（点「应用」才生效）、数据截止置灰说明、对比方式并入弹层、
   *  URL 同步（searchParams start/end/preset/compare/dim + popstate 恢复）、
   *  tmall:date-range-change / tmall:date-range-ready 两个全局事件。
   *  shell.js 与页面适配器经 window.TmallDateRange 消费，订阅收敛见
   *  runtime/date-range-scope.js。
   *
   *  deps 契约（由 shell.js 提供）：
   *  - header             顶栏元素（含 demo-period 结构）
   *  - currentPage        当前页面 key（无日期范围页不写 URL 参数）
   *  - apiReady           Promise<DemoApi>，仅显示 /api/periods 数据新鲜度
   *  - pagesWithoutDateRange Set<string>，不参与 URL 同步的页面集合
   */

  function createDateRangeStore(deps) {
    const { header, currentPage, apiReady, pagesWithoutDateRange } = deps;

    const trigger = header.querySelector('[data-date-trigger]');
    const popover = header.querySelector('[data-period-popover]');
    const elPreset = header.querySelector('[data-period-preset]');
    const elRange = header.querySelector('[data-period-range]');
    const elLegacyPreset = header.querySelector('[data-period-legacy-preset]');
    const elLegacyRange = header.querySelector('[data-period-legacy-range]');
    const elCompareBadge = header.querySelector('[data-period-compare]');
    const chipsEl = header.querySelector('[data-period-chips]');
    const modeBtns = Array.prototype.slice.call(popover.querySelectorAll('[data-period-mode]'));
    const inlinePresetBtns = Array.prototype.slice.call(header.querySelectorAll('[data-inline-preset]'));
    const inlineGrainBtns = Array.prototype.slice.call(header.querySelectorAll('[data-inline-grain]'));
    const inlineCustomBtn = header.querySelector('[data-inline-custom]');
    const inlineNavBtns = Array.prototype.slice.call(header.querySelectorAll('[data-inline-nav]'));
    const customPanel = popover.querySelector('[data-period-custom-panel]');
    const grainBtns = Array.prototype.slice.call(popover.querySelectorAll('[data-grain]'));
    const inputStart = header.querySelector('[data-period-start]');
    const inputEnd = header.querySelector('[data-period-end]');
    const yearSel = header.querySelector('[data-period-year]');
    const monthEls = [popover.querySelector('[data-calendar-month="0"]'), popover.querySelector('[data-calendar-month="1"]')];
    const footerRange = popover.querySelector('[data-period-footer-range]');
    const footerDays = popover.querySelector('[data-period-footer-days]');
    const footerAnchor = popover.querySelector('[data-period-anchor]');
    const compareBtns = Array.prototype.slice.call(popover.querySelectorAll('[data-compare-value]'));
    const btnApply = popover.querySelector('[data-period-apply]');
    const btnCancel = popover.querySelector('[data-period-cancel]');
    const btnSwap = popover.querySelector('[data-period-swap]');

    // event.target 的静态类型是 EventTarget，没有 closest；统一在这里收窄一次，
    // 避免每个事件处理器各写一遍类型断言。
    /**
     * @param {Event} event
     * @param {string} selector
     * @returns {HTMLElement | null}
     */
    const closestFrom = (event, selector) => {
      const node = /** @type {Element | null} */ (event.target);
      return node && typeof node.closest === 'function' ? /** @type {HTMLElement | null} */ (node.closest(selector)) : null;
    };
    // 只有可见元素才能当浮层锚点：隐藏元素（hidden / display:none）的
    // getBoundingClientRect() 全为 0，会让浮层退化到视口左上角。
    const isVisibleElement = (node) => Boolean(
      node && node.nodeType === 1 && node.getClientRects().length
      && getComputedStyle(node).visibility !== 'hidden'
    );
    const isIsoDate = (value) => {      if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
      const [year, month, day] = value.split('-').map(Number);
      const date = new Date(year, month - 1, day);
      return date.getFullYear() === year && date.getMonth() === month - 1 && date.getDate() === day;
    };
    const parseDate = (value) => {
      if (!isIsoDate(value)) return new Date(NaN);
      const [year, month, day] = value.split('-').map(Number);
      return new Date(year, month - 1, day);
    };
    const formatDate = (date) => `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
    const formatShort = (date) => `${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
    const shiftDays = (date, amount) => { const next = new Date(date); next.setDate(next.getDate() + amount); return next; };
    const startOfWeek = (date) => shiftDays(date, -((date.getDay() + 6) % 7));
    const daysBetween = (a, b) => Math.round((b - a) / 86400000) + 1;

    const PRESET_LABELS = {
      today: '今日', yesterday: '昨日', '7d': '近7天', '14d': '近14天', '30d': '近30天',
      '60d': '近60天', '90d': '近90天', '180d': '近180天',
      this_week: '本周', last_week: '上周', this_month: '本月', last_month: '上月', custom: '自定义',
    };
    // 快捷预设分组：滚动（相对锚点）与自然周期。去掉 14d/60d 等与 7d/30d/90d 语义交叉的档位，
    // 分组标签让"近7天（滚动）vs 本周（自然周）"一目了然，消除原 12 chip 的交叉重复感。
    const PRESET_GROUPS = [
      { label: '滚动', keys: ['today', 'yesterday', '7d', '30d', '90d', '180d'] },
      { label: '自然周期', keys: ['this_week', 'last_week', 'this_month', 'last_month'] },
    ];
    const DIM_LABELS = { daily: '按日', weekly: '按周', monthly: '按月', yearly: '按年' };
    const COMPARE_LABELS = { none: '不对比', previous_period: '环比', year_over_year: '同比' };
    const weekdayNames = ['日', '一', '二', '三', '四', '五', '六'];

    const params = new URLSearchParams(global.location.search);
    const anchorDate = new Date();
    anchorDate.setHours(0, 0, 0, 0);
    let calendarBase = new Date(anchorDate.getFullYear(), anchorDate.getMonth() - 1, 1);
    let draft = null;
    let state = {
      startDate: '', endDate: '', preset: params.get('preset') || '30d',
      compareMode: params.get('compare') || 'none',
      dim: ['daily', 'weekly', 'monthly', 'yearly'].includes(params.get('dim')) ? params.get('dim') : 'daily',
      origin: 'preset',
    };
    let rangeReadyDispatched = false;
    const rangeSubscribers = new Set();

    const rangeForPreset = (preset) => {
      const offsets = { today: 0, yesterday: 0, '7d': 6, '14d': 13, '30d': 29, '60d': 59, '90d': 89, '180d': 179 };
      if (preset === 'this_week') return { start: startOfWeek(anchorDate), end: new Date(anchorDate) };
      if (preset === 'last_week') {
        const end = shiftDays(startOfWeek(anchorDate), -1);
        return { start: shiftDays(end, -6), end };
      }
      if (preset === 'this_month') return { start: new Date(anchorDate.getFullYear(), anchorDate.getMonth(), 1), end: new Date(anchorDate) };
      if (preset === 'last_month') return { start: new Date(anchorDate.getFullYear(), anchorDate.getMonth() - 1, 1), end: new Date(anchorDate.getFullYear(), anchorDate.getMonth(), 0) };
      const end = preset === 'yesterday' ? shiftDays(anchorDate, -1) : new Date(anchorDate);
      return { start: shiftDays(end, -(offsets[preset] || 0)), end };
    };
    const anchorIso = () => formatDate(anchorDate);
    const clampEnd = (iso) => (iso && iso > anchorIso() ? anchorIso() : iso);
    const normalizeRange = (s, e) => {
      let start = isIsoDate(s) ? s : '';
      let end = isIsoDate(e) ? clampEnd(e) : '';
      if (start && start > anchorIso()) start = anchorIso();
      if (start && end && start > end) { const t = start; start = end; end = t; }
      return { start, end };
    };

    // 顶栏高亮必须由状态派生：dispatchRange 是唯一的状态出口。
    // 参考图同一时刻只有一处高亮：预设 / 粒度 / 自定义 三者互斥，取决于最近一次选择来源。
    const renderInlineActive = () => {
      const origin = state.origin || 'preset';
      inlinePresetBtns.forEach((btn) => btn.classList.toggle('is-active', origin === 'preset' && btn.dataset.inlinePreset === state.preset));
      inlineGrainBtns.forEach((btn) => {
        const active = origin === 'grain' && btn.dataset.inlineGrain === state.dim;
        btn.classList.toggle('is-active', active);
        btn.setAttribute('aria-pressed', String(active));
      });
      if (inlineCustomBtn) inlineCustomBtn.classList.toggle('is-active', origin === 'custom');
    };
    // 顶栏使用紧凑点分日期；跨年时补全两端年份，单日只显示一次。
    const formatRangeLabel = (startIso, endIso) => {
      if (!startIso || !endIso) return '--';
      const s = parseDate(startIso);
      const e = parseDate(endIso);
      if (Number.isNaN(s.getTime()) || Number.isNaN(e.getTime())) return '--';
      const sameYear = s.getFullYear() === e.getFullYear();
      const startText = `${s.getFullYear()}.${s.getMonth() + 1}.${s.getDate()}`;
      const endText = sameYear
        ? `${e.getMonth() + 1}.${e.getDate()}`
        : `${e.getFullYear()}.${e.getMonth() + 1}.${e.getDate()}`;
      return startIso === endIso ? startText : `${startText}-${endText}`;
    };
    const dispatchRange = (writeHistory = true) => {
      renderInlineActive();
      const dimLabel = DIM_LABELS[state.dim] || '按日';
      const presetLabel = PRESET_LABELS[state.preset] || '自定义';
      // 参考图只在括号里显示日期范围；预设词与右侧 7天/30天 按钮高亮重复，故不再单独展示。
      if (elPreset) {
        elPreset.textContent = '';
        elPreset.hidden = true;
      }
      if (elLegacyPreset) elLegacyPreset.textContent = `${presetLabel} · ${dimLabel}`;
      const rangeText = formatRangeLabel(state.startDate, state.endDate);
      if (elRange) {
        elRange.textContent = rangeText;
        elRange.title = `${state.startDate} 至 ${state.endDate}`;
        elRange.setAttribute('aria-label', elRange.title);
      }
      if (elLegacyRange) elLegacyRange.textContent = rangeText;
      if (state.compareMode === 'none') elCompareBadge.hidden = true;
      else {
        elCompareBadge.hidden = false;
        elCompareBadge.textContent = COMPARE_LABELS[state.compareMode] || '对比';
      }
      const url = new URL(global.location.href);
      if (pagesWithoutDateRange.has(currentPage)) {
        url.searchParams.delete('start');
        url.searchParams.delete('end');
        url.searchParams.delete('preset');
        url.searchParams.delete('compare');
        url.searchParams.delete('dim');
      } else {
        url.searchParams.set('start', state.startDate);
        url.searchParams.set('end', state.endDate);
        url.searchParams.set('preset', state.preset);
        url.searchParams.set('compare', state.compareMode);
        url.searchParams.set('dim', state.dim);
      }
      if (writeHistory) history.pushState(null, '', url);
      global.dispatchEvent(new CustomEvent('tmall:date-range-change', { detail: { ...state } }));
      rangeSubscribers.forEach((subscriber) => {
        try { subscriber({ ...state }); } catch (error) { console.error('日期范围订阅回调失败', error); }
      });
      if (!rangeReadyDispatched) {
        rangeReadyDispatched = true;
        global.dispatchEvent(new CustomEvent('tmall:date-range-ready', { detail: { ...state } }));
      }
    };
    const applyRange = (start, end, preset = 'custom', allowFuture = false) => {
      if (!(start instanceof Date) || !(end instanceof Date) || Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) return false;
      start.setHours(0, 0, 0, 0);
      end.setHours(0, 0, 0, 0);
      if (start > end || (!allowFuture && end > anchorDate)) return false;
      state = { ...state, startDate: formatDate(start), endDate: formatDate(end), preset };
      dispatchRange();
      return true;
    };

    /* ============ 渲染 ============ */
    const renderChips = () => {
      chipsEl.innerHTML = PRESET_GROUPS.map((group) =>
        `<div class="demo-period__chip-group"><span class="demo-period__chip-group-label">${group.label}</span><div class="demo-period__chips-row">` +
        group.keys.map((key) =>
          `<button type="button" class="demo-period__chip${draft && draft.preset === key ? ' is-active' : ''}" data-chip="${key}">${PRESET_LABELS[key]}</button>`
        ).join('') +
        `</div></div>`
      ).join('');
    };
    const renderGrain = () => {
      const dim = (draft && draft.dim) || state.dim || 'daily';
      grainBtns.forEach((btn) => btn.classList.toggle('is-active', btn.dataset.grain === dim));
    };
    const renderInputs = () => {
      inputStart.value = (draft && draft.startDate) || '';
      inputEnd.value = (draft && draft.endDate) || '';
      inputStart.max = anchorIso();
      inputEnd.max = anchorIso();
    };
    const renderCalendar = (previewDate) => {
      yearSel.value = calendarBase.getFullYear();
      const dStart = draft && draft.startDate ? parseDate(draft.startDate) : null;
      const dEnd = draft && draft.endDate ? parseDate(draft.endDate) : null;
      const preview = previewDate || null;
      const anchorIsoValue = anchorIso();
      [0, 1].forEach((offset) => {
        const month = new Date(calendarBase.getFullYear(), calendarBase.getMonth() + offset, 1);
        const firstDay = month.getDay();
        const total = new Date(month.getFullYear(), month.getMonth() + 1, 0).getDate();
        const cells = [];
        for (let i = 0; i < firstDay; i += 1) cells.push('<span class="demo-calendar__blank"></span>');
        for (let day = 1; day <= total; day += 1) {
          const date = new Date(month.getFullYear(), month.getMonth(), day);
          const value = formatDate(date);
          const future = value > anchorIsoValue;
          const classes = ['demo-calendar__day'];
          let inRange = false;
          let isStart = false;
          let isEnd = false;
          let isPreview = false;
          if (!future && dStart && dEnd) {
            const lo = dStart < dEnd ? formatDate(dStart) : formatDate(dEnd);
            const hi = dStart < dEnd ? formatDate(dEnd) : formatDate(dStart);
            inRange = value >= lo && value <= hi;
            isStart = value === lo;
            isEnd = value === hi;
          } else if (!future && dStart && !dEnd && preview) {
            const a = formatDate(dStart);
            const b = formatDate(preview);
            const lo = a < b ? a : b;
            const hi = a < b ? b : a;
            isPreview = value >= lo && value <= hi;
            isStart = value === lo;
            isEnd = value === hi;
          }
          if (inRange || isPreview) classes.push('is-in-range');
          if (isStart) classes.push('is-start', 'is-selected');
          if (isEnd) classes.push('is-end', 'is-selected');
          if (isPreview && !isStart && !isEnd) classes.push('is-preview');
          if (value === anchorIsoValue) classes.push('is-anchor');
          cells.push(
            `<button type="button" class="${classes.join(' ')}" data-date="${value}"${future ? ` disabled title="未来日期（系统当日 ${anchorIsoValue}）"` : ''}>${day}${future ? '<span class="demo-period__fut">止</span>' : ''}</button>`
          );
        }
        monthEls[offset].innerHTML =
          `<div class="demo-period__month-head"><h3>${month.getFullYear()}年${month.getMonth() + 1}月</h3>` +
          `<div class="demo-period__month-nav"><button type="button" data-nav="-1" aria-label="上一月"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6"/></svg></button>` +
          `<button type="button" data-nav="1" aria-label="下一月"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"/></svg></button></div></div>` +
          `<div class="demo-calendar__week">${weekdayNames.map((w) => `<span>${w}</span>`).join('')}</div>` +
          `<div class="demo-calendar__grid">${cells.join('')}</div>`;
      });
    };
    const renderFooter = () => {
      const d = draft || state;
      if (d.startDate && d.endDate) {
        footerRange.textContent = `${d.startDate} ~ ${d.endDate}`;
        const spanDays = daysBetween(parseDate(d.startDate), parseDate(d.endDate));
        const dim = (draft && draft.dim) || state.dim || 'daily';
        if (dim === 'monthly') {
          const monthSpan = (parseDate(d.endDate).getFullYear() - parseDate(d.startDate).getFullYear()) * 12
            + (parseDate(d.endDate).getMonth() - parseDate(d.startDate).getMonth()) + 1;
          footerDays.textContent = `覆盖 ${monthSpan} 月`;
        } else if (dim === 'weekly') {
          footerDays.textContent = `覆盖约 ${Math.max(1, Math.ceil(spanDays / 7))} 周`;
        } else {
          footerDays.textContent = `覆盖 ${spanDays} 天`;
        }
      } else {
        footerRange.textContent = '未选择';
        footerDays.textContent = '';
      }
      footerAnchor.textContent = anchorIso();
      compareBtns.forEach((b) => b.classList.toggle('is-active', b.dataset.compareValue === d.compareMode));
      const dirty = JSON.stringify({ startDate: d.startDate, endDate: d.endDate, preset: d.preset, compareMode: d.compareMode, dim: d.dim })
        !== JSON.stringify({ startDate: state.startDate, endDate: state.endDate, preset: state.preset, compareMode: state.compareMode, dim: state.dim });
      btnApply.classList.toggle('demo-period__apply-pulse', dirty);
      btnApply.textContent = dirty ? '应用更改' : '应用';
    };
    const renderMode = () => {
      const custom = Boolean(draft && draft.preset === 'custom');
      modeBtns.forEach((btn) => {
        const active = (custom ? 'custom' : 'quick') === btn.dataset.periodMode;
        btn.classList.toggle('is-active', active);
        btn.setAttribute('aria-selected', String(active));
      });
      renderInlineActive();
      customPanel.hidden = !custom;
      chipsEl.hidden = custom;
    };
    const renderAll = () => { renderMode(); renderChips(); renderGrain(); renderInputs(); renderCalendar(); renderFooter(); };

    /* ============ 弹层开关 / 草稿 ============ */
    const setOpen = (open) => {
      popover.toggleAttribute('hidden', !open);
      trigger.setAttribute('aria-expanded', String(open));
      if (open) {
        draft = {
          startDate: state.startDate, endDate: state.endDate, preset: state.preset,
          compareMode: state.compareMode, dim: state.dim,
        };
        renderAll();
      }
    };
    const commitDraft = () => {
      state = {
        startDate: draft.startDate, endDate: draft.endDate, preset: draft.preset,
        compareMode: draft.compareMode, dim: draft.dim,
        // 保留来源标记：草稿不带 origin，直接覆盖会让顶栏高亮失去依据。
        origin: draft.origin || state.origin,
      };
      dispatchRange();
    };
    const closePopover = (resetDraft = false) => {
      if (resetDraft) draft = null;
      setOpen(false);
    };

    let pickerDialog = null;
    let pickerPopover = null;
    let pickerCursor = null;
    const closePicker = () => {
      // 优先走浮层原语的关闭（它负责焦点返回与事件解绑）；
      // 原语不可用时回退到直接移除节点。
      if (pickerPopover) { pickerPopover.close(); pickerPopover = null; }
      pickerDialog?.remove();
      pickerDialog = null;
    };
    const pickerButton = (label, action, extra = '') => `<button type="button" class="demo-picker__button ${extra}" data-picker-action="${action}">${label}</button>`;
    const openPicker = (mode, anchorEl = null) => {
      closePicker();
      // 锚点必须是"用户实际点击且可见"的元素。此前的 trigger 被 shell.js 设为 hidden，
      // 隐藏元素 getBoundingClientRect() 全为 0，浮层会退化到视口左上角。
      const anchorNode = (isVisibleElement(anchorEl) && anchorEl)
        || (isVisibleElement(trigger) && trigger)
        || document.querySelector('.demo-period__inline');
      const focusDate = parseDate(state.endDate) || new Date(anchorDate);
      // 弹窗定位跟随当前粒度：月弹窗落在当前月，年弹窗落在当前年，避免跨粒度时跳回旧位置。
      if (mode === 'monthly') pickerCursor = new Date(focusDate.getFullYear(), focusDate.getMonth(), 1);
      else if (mode === 'yearly') pickerCursor = new Date(focusDate.getFullYear(), 0, 1);
      else if (mode === 'custom') {
        // 双月日历从区间起点所在月展开：一打开就看到当前选中范围，不用先翻月找自己选在哪。
        const rangeStart = parseDate(state.startDate);
        const base = Number.isNaN(rangeStart.getTime()) ? focusDate : rangeStart;
        pickerCursor = new Date(base.getFullYear(), base.getMonth(), 1);
      } else pickerCursor = focusDate;
      const titles = { daily: '选择日期', weekly: '选择周', monthly: '选择月份', yearly: '选择年份', custom: '自定义日期范围' };
      const section = document.createElement('section');
      // 自定义弹窗按参考稿用更宽的两列表单；其余粒度保持紧凑单月网格，
      // 因为粒度弹窗必须紧贴被点击的按钮（smoke_date_picker.cjs 断言锚定偏移 <= 24px），
      // 加宽会让贴边的「年」按钮被视口夹紧后失去锚定关系。
      section.className = mode === 'custom' ? 'demo-picker demo-picker--custom' : 'demo-picker';
      section.setAttribute('role', 'dialog');
      section.setAttribute('aria-label', titles[mode]);
      // custom 的区间读数放标题行中间：这样「当前选了什么」有一处权威显示，
      // 而不用在正文里再占一整行（改前正文里读数、输入框、日历把同一区间显示了三遍）。
      section.innerHTML = `<header class="demo-picker__header"><strong>${titles[mode]}</strong>${mode === 'custom' ? '<span class="demo-picker__range-readout"></span>' : ''}<button type="button" class="demo-picker__close" data-picker-action="close" aria-label="关闭">×</button></header><div class="demo-picker__body"></div>`;
      // 浮层统一走 TmallUI.popover（定位/视口约束/点外关闭/Esc/焦点返回）。
      // 此前每个浮层各自写定位，一旦定位样式被 CSS 解析错误吞掉就会渲染到文档流底部，
      // 表现为「点了没反应」。原语不可用时才回退到旧的 backdrop 结构。
      if (typeof global.TmallUI?.popover === 'function') {
        pickerPopover = global.TmallUI.popover({
          anchor: anchorNode,
          content: section,
          placement: 'bottom',
          onClose: () => { pickerPopover = null; pickerDialog = null; },
        });
        pickerDialog = pickerPopover.node;
      } else {
        pickerDialog = document.createElement('div');
        pickerDialog.className = 'demo-picker__backdrop';
        pickerDialog.appendChild(section);
        document.body.appendChild(pickerDialog);
      }
      const body = section.querySelector('.demo-picker__body');
      // custom 模式的草稿状态：日历点击/输入框改动只写草稿，点「应用」才落到全局范围。
      // 这样「取消不会改变当前范围」是真实行为，而不是一句文案承诺。
      let customStart = isIsoDate(state.startDate) ? state.startDate : '';
      let customEnd = isIsoDate(state.endDate) ? state.endDate : '';
      let customHover = '';
      // 双月骨架只在首次渲染时构建，之后每次交互只做原地更新。
      // 改前每点一下/悬停一格都整块重写 body.innerHTML，两个原生 <input type="date">
      // 连同 42 个日期格一起被销毁重建，浏览器要重新挂载控件，视觉上就是「点一下闪一下」。
      let customShellBuilt = false;
      let customMonthKey = '';
      // 草稿的派生值集中在一处算：骨架、格子、读数、输入框读同一份，
      // 避免各处重复推导后显示与草稿不一致。
      const customDraft = () => {
        const draftEnd = customEnd || customHover;
        const lo = customStart && draftEnd ? (customStart <= draftEnd ? customStart : draftEnd) : customStart;
        const hi = customStart && draftEnd ? (customStart <= draftEnd ? draftEnd : customStart) : customStart;
        return { draftEnd, lo, hi, single: Boolean(lo) && lo === hi, span: lo && hi ? daysBetween(parseDate(lo), parseDate(hi)) : 0 };
      };
      // 日期格类名只写一份：首次构建（innerHTML）与后续原地更新（classList）都走这里，
      // 否则两处逻辑会慢慢漂移，出现「点了没高亮」这类只在一侧生效的 bug。
      const customDayClasses = (value, isOutside, lo, hi, single, anchor) => {
        const inRange = !isOutside && Boolean(lo) && Boolean(hi) && value >= lo && value <= hi;
        const isStart = inRange && value === lo;
        const isEnd = inRange && value === hi;
        const classes = ['demo-picker__day'];
        if (isOutside) classes.push('demo-picker__day--outside');
        if (inRange) classes.push('is-in-range');
        if (inRange && !single) {
          if (isStart) classes.push('is-start');
          if (isEnd) classes.push('is-end');
        }
        if (isStart || isEnd) classes.push('is-selected');
        if (value === anchor) classes.push('is-anchor');
        return classes;
      };
      // 双月格子：只重建 .demo-picker__dual 这一层，绝不碰输入框与按钮。
      const renderCustomMonths = () => {
        const dual = body.querySelector('.demo-picker__dual');
        if (!dual) return;
        const { lo, hi, single } = customDraft();
        const anchor = anchorIso();
        // 翻页按钮并进月份标题行：左月「«‹ 2026年9月」、右月「2026年10月 ›»」。
        // 改前它们是独立的一行，加上标题行一共两行才说清「现在看的是哪两个月」。
        const renderMonth = (cursor, nav) => {
          const y = cursor.getFullYear();
          const m = cursor.getMonth();
          const monthTotal = new Date(y, m + 1, 0).getDate();
          const monthOffset = (new Date(y, m, 1).getDay() + 6) % 7;
          const monthTrailing = (7 - ((monthOffset + monthTotal) % 7)) % 7;
          const cells = [];
          for (let day = 1 - monthOffset; day <= monthTotal + monthTrailing; day += 1) {
            const date = new Date(y, m, day);
            const value = formatDate(date);
            const dayNum = date.getDate();
            const isOutside = day < 1 || day > monthTotal;
            // 双月视图里相邻月的补齐格是纯装饰：那个月已经完整渲染在隔壁面板了。
            // 所以补齐格不参与区间着色、也不可点——否则区间端点会在同一屏出现
            // 两个实心圆点，而且用户在「10月」面板里点到的其实是 9月30日。
            const classes = customDayClasses(value, isOutside, lo, hi, single, anchor);
            cells.push(`<button type="button" class="${classes.join(' ')}" data-picker-date="${value}" aria-label="${y}年${m + 1}月${dayNum}日"${value === anchor ? ' aria-current="date"' : ''}${(value > anchor || isOutside) ? ' disabled' : ''}><span class="demo-picker__day-num">${dayNum}</span></button>`);
          }
          const head = nav === 'prev'
            ? `${pickerButton('«', 'year-prev')}${pickerButton('‹', 'month-prev')}<strong class="demo-picker__month-head">${y}年${m + 1}月</strong>`
            : `<strong class="demo-picker__month-head">${y}年${m + 1}月</strong>${pickerButton('›', 'month-next')}${pickerButton('»', 'year-next')}`;
          return `<div class="demo-picker__month"><div class="demo-picker__month-head-row">${head}</div><div class="demo-picker__week"><span>一</span><span>二</span><span>三</span><span>四</span><span>五</span><span>六</span><span>日</span></div><div class="demo-picker__calendar">${cells.join('')}</div></div>`;
        };
        dual.innerHTML = renderMonth(new Date(pickerCursor.getFullYear(), pickerCursor.getMonth(), 1), 'prev')
          + renderMonth(new Date(pickerCursor.getFullYear(), pickerCursor.getMonth() + 1, 1), 'next');
        customMonthKey = `${pickerCursor.getFullYear()}-${pickerCursor.getMonth()}`;
      };
      // 区间高亮原地切换：只改 classList，不重建任何节点——
      // 这是消除悬停/点击闪烁的关键一步。
      const syncCustomDays = () => {
        const { lo, hi, single } = customDraft();
        const anchor = anchorIso();
        body.querySelectorAll('[data-picker-date]').forEach((btn) => {
          if (!(btn instanceof HTMLElement)) return;
          const isOutside = btn.classList.contains('demo-picker__day--outside');
          const classes = customDayClasses(btn.dataset.pickerDate, isOutside, lo, hi, single, anchor);
          btn.classList.remove('is-in-range', 'is-start', 'is-end', 'is-selected', 'is-anchor');
          classes.slice(1).forEach((name) => {
            if (name !== 'demo-picker__day--outside') btn.classList.add(name);
          });
        });
      };
      // 读数/说明：值一致就不写，避免无谓重绘。
      const syncCustomChrome = () => {
        const { lo, hi, span } = customDraft();
        const readout = section.querySelector('.demo-picker__range-readout');
        if (readout) {
          const text = lo ? (hi && hi !== lo ? `${lo} ~ ${hi}` : lo) : '请选择日期';
          if (readout.textContent !== text) readout.textContent = text;
        }
        const hint = body.querySelector('.demo-picker__hint');
        if (hint) {
          const text = `* 最少选择 1 天，最多选择 31 天${span ? ` · 已选 ${span} 天` : ''}`;
          if (hint.textContent !== text) hint.textContent = text;
        }
      };
      const render = () => {
        const year = pickerCursor.getFullYear();
        const month = pickerCursor.getMonth();
        if (mode === 'custom') {
          // 参考稿：双月并排区间日历。左月=区间起点月，右月=次月，一次能看到跨月区间全貌。
          if (!customShellBuilt) {
            // 骨架只留三块：双月网格 / 说明 / 操作。区间读数在标题行，翻页按钮在月份标题行，
            // 改前那行「起止日期输入框」与「独立读数行」说的是同一件事，白占 128px。
            body.innerHTML = `<div class="demo-picker__dual"></div><p class="demo-picker__hint"></p><div class="demo-picker__actions">${pickerButton('取消', 'close')}${pickerButton('应用', 'custom-apply', 'is-primary')}</div>`;
            customShellBuilt = true;
            customMonthKey = '';
          }
          // 只有翻月/翻年才重建格子；纯高亮变化走 syncCustomDays 原地改类名。
          const monthKey = `${pickerCursor.getFullYear()}-${pickerCursor.getMonth()}`;
          if (monthKey !== customMonthKey) renderCustomMonths();
          else syncCustomDays();
          syncCustomChrome();
          return;
        }
        if (mode === 'monthly') {
          // 高亮按"范围落在该月"判断，避免因数据截止日截断（如 10-01~10-09）而丢失选中态。
          const months = Array.from({ length: 12 }, (_, index) => {
            const start = new Date(year, index, 1);
            const end = new Date(year, index + 1, 0);
            const active = state.startDate >= formatDate(start) && state.startDate <= formatDate(end);
            return `<button type="button" class="demo-picker__tile${active ? ' is-active' : ''}" data-picker-month="${index}">${index + 1}月</button>`;
          }).join('');
          body.innerHTML = `<div class="demo-picker__toolbar">${pickerButton('‹', 'year-prev') }<strong>${year}年</strong>${pickerButton('›', 'year-next')}</div><div class="demo-picker__grid demo-picker__grid--months">${months}</div>`;
          return;
        }
        if (mode === 'yearly') {
          const base = year - (year % 10);
          const years = Array.from({ length: 12 }, (_, index) => {
            const value = base + index;
            const active = state.startDate >= `${value}-01-01` && state.startDate <= `${value}-12-31`;
            return `<button type="button" class="demo-picker__tile${active ? ' is-active' : ''}" data-picker-year="${value}">${value}年</button>`;
          }).join('');
          body.innerHTML = `<div class="demo-picker__toolbar">${pickerButton('‹', 'decade-prev')}<strong>${base}年 - ${base + 11}年</strong>${pickerButton('›', 'decade-next')}</div><div class="demo-picker__grid demo-picker__grid--years">${years}</div>`;
          return;
        }
        const first = new Date(year, month, 1);
        const total = new Date(year, month + 1, 0).getDate();
        const offset = (first.getDay() + 6) % 7;
        const rangeStart = state.startDate;
        const rangeEnd = state.endDate;
        const anchor = anchorIso();
        const hasRange = Boolean(rangeStart) && Boolean(rangeEnd);
        const isSingleDay = rangeStart === rangeEnd;
        // 相邻月补齐：月初/月末用上/下月日期灰字填满整周（参考稿效果）。
        // 这样跨月的区间带能连续铺过去，不会在月边界被硬切断——
        // 默认 30 天区间横跨两个月，单月渲染时用户看不出选中了多长。
        const trailing = (7 - ((offset + total) % 7)) % 7;
        const cells = [];
        for (let day = 1 - offset; day <= total + trailing; day += 1) {
          const date = new Date(year, month, day);
          const value = formatDate(date);
          const dayNum = date.getDate();
          const isOutside = day < 1 || day > total;
          const disabled = value > anchor;
          let selected = false;
          let inRange = false;
          let isStart = false;
          let isEnd = false;
          if (mode === 'weekly') {
            // 周粒度：整周铺底高亮（周首~周末），而不是只点亮周首那一天，
            // 否则数据截止日截断时（如 10-05~10-09）整周看起来像没选中。
            const weekStart = formatDate(startOfWeek(date));
            const weekEnd = formatDate(shiftDays(startOfWeek(date), 6));
            inRange = state.dim === 'weekly' && rangeStart <= weekEnd && rangeEnd >= weekStart;
            isStart = inRange && value === weekStart;
            isEnd = inRange && value === weekEnd;
            selected = isStart;
          } else if (hasRange && value >= rangeStart && value <= rangeEnd) {
            // 日粒度：区间内统一铺淡色底，起止两端加实心圆点。
            // 改前只高亮 endDate 一天（`active = value === state.endDate`），
            // 用户完全看不出选了多长的区间——这是「高亮效果不好」的根因。
            inRange = true;
            isStart = value === rangeStart;
            isEnd = value === rangeEnd;
            selected = isStart || isEnd;
          }
          const isAnchor = value === anchor;
          const classes = ['demo-picker__day'];
          if (isOutside) classes.push('demo-picker__day--outside');
          if (inRange) classes.push('is-in-range');
          if (inRange && !isSingleDay) {
            if (isStart) classes.push('is-start');
            if (isEnd) classes.push('is-end');
          }
          if (selected) classes.push('is-selected');
          if (isAnchor) classes.push('is-anchor');
          cells.push(`<button type="button" class="${classes.join(' ')}" data-picker-date="${value}" aria-label="${date.getFullYear()}年${date.getMonth() + 1}月${dayNum}日"${isAnchor ? ' aria-current="date"' : ''}${disabled ? ' disabled' : ''}><span class="demo-picker__day-num">${dayNum}</span></button>`);
        }
        body.innerHTML = `<div class="demo-picker__toolbar">${pickerButton('‹', 'month-prev')}<strong>${year}年${month + 1}月</strong>${pickerButton('›', 'month-next')}</div><div class="demo-picker__week"><span>一</span><span>二</span><span>三</span><span>四</span><span>五</span><span>六</span><span>日</span></div><div class="demo-picker__calendar">${cells.join('')}</div>`;
      };
      // 事件绑在 section 上：无论走原语还是回退结构，section 都是稳定的内容根。
      /** @param {MouseEvent} event */
      section.addEventListener('click', (event) => {
        const action = closestFrom(event, '[data-picker-action]')?.dataset.pickerAction;
        if (action === 'close') return closePicker();
        if (action === 'month-prev') pickerCursor = new Date(pickerCursor.getFullYear(), pickerCursor.getMonth() - 1, 1);
        if (action === 'month-next') pickerCursor = new Date(pickerCursor.getFullYear(), pickerCursor.getMonth() + 1, 1);
        if (action === 'year-prev') pickerCursor = new Date(pickerCursor.getFullYear() - 1, pickerCursor.getMonth(), 1);
        if (action === 'year-next') pickerCursor = new Date(pickerCursor.getFullYear() + 1, pickerCursor.getMonth(), 1);
        if (action === 'decade-prev') pickerCursor = new Date(pickerCursor.getFullYear() - 10, pickerCursor.getMonth(), 1);
        if (action === 'decade-next') pickerCursor = new Date(pickerCursor.getFullYear() + 10, pickerCursor.getMonth(), 1);
        if (action === 'custom-apply') {
          // 读草稿而不是直接读 DOM：输入框与日历共用同一份草稿，
          // 用户「先在日历点一下、再手改输入框」时两边不会打架。
          const start = customStart;
          const end = customEnd || customStart;
          if (setSharedRange(start, end, 'custom')) closePicker();
          return;
        }
        const dateButton = closestFrom(event, '[data-picker-date]');
        if (dateButton) {
          const selected = parseDate(dateButton.dataset.pickerDate);
          if (mode === 'custom') {
            // 两段式区间选择：第一次点定起点，第二次点定终点；再点则重新开始。
            // 反向选择（先点后面的日期）自动交换，不让用户为顺序买单。
            if (!customStart || (customStart && customEnd)) {
              customStart = dateButton.dataset.pickerDate;
              customEnd = '';
            } else if (dateButton.dataset.pickerDate < customStart) {
              customEnd = customStart;
              customStart = dateButton.dataset.pickerDate;
            } else {
              customEnd = dateButton.dataset.pickerDate;
            }
            customHover = '';
            // 参考稿约束「最多 31 天」：超出时把远端截断到起点后第 30 天，
            // 而不是静默接受一个 200 天的区间。
            if (customStart && customEnd && daysBetween(parseDate(customStart), parseDate(customEnd)) > 31) {
              const from = customStart <= customEnd ? customStart : customEnd;
              customStart = from;
              customEnd = formatDate(shiftDays(parseDate(from), 30));
            }
            render();
            return;
          }
          if (mode === 'daily') { state = { ...state, dim: 'daily', preset: 'custom', origin: 'grain' }; applyRange(selected, selected, 'custom'); closePicker(); return; }
          const weekStart = startOfWeek(selected);
          const weekEnd = shiftDays(weekStart, 6);
          state = { ...state, dim: 'weekly', preset: 'custom', origin: 'grain' };
          applyRange(weekStart, weekEnd > anchorDate ? new Date(anchorDate) : weekEnd, 'custom');
          closePicker();
          return;
        }
        const monthButton = closestFrom(event, '[data-picker-month]');
        if (monthButton) {
          const selected = Number(monthButton.dataset.pickerMonth);
          // 用 pickerCursor 取年份，而不是 render() 内的局部 year：
          // 点击处理器在 render() 作用域之外，引用 year 会抛 ReferenceError，
          // 导致选月份静默失败（选 3 月却停在当前月）。
          const selectedYear = pickerCursor.getFullYear();
          state = { ...state, dim: 'monthly', preset: 'custom', origin: 'grain' };
          const monthEnd = new Date(selectedYear, selected + 1, 0);
          applyRange(new Date(selectedYear, selected, 1), monthEnd > anchorDate ? new Date(anchorDate) : monthEnd, 'custom');
          closePicker();
          return;
        }
        const yearButton = closestFrom(event, '[data-picker-year]');
        if (yearButton) {
          const selected = Number(yearButton.dataset.pickerYear);
          state = { ...state, dim: 'yearly', preset: 'custom', origin: 'grain' };
          const yearEnd = new Date(selected, 11, 31);
          applyRange(new Date(selected, 0, 1), yearEnd > anchorDate ? new Date(anchorDate) : yearEnd, 'custom');
          closePicker();
          return;
        }
        render();
      });
      // 悬停预览：定好起点后，鼠标扫过哪里就实时预演到哪里的区间带，
      // 用户在下决心点第二下之前就能看到结果，不用靠想象。
      section.addEventListener('mouseover', (event) => {
        if (mode !== 'custom' || !customStart || customEnd) return;
        const hovered = closestFrom(event, '[data-picker-date]');
        if (!(hovered instanceof HTMLButtonElement) || hovered.disabled) return;
        const value = hovered.dataset.pickerDate;
        if (value === customHover) return;
        customHover = value;
        render();
      });
      // 手改输入框的路径已随「去冗余」移除：区间只能从日历点选，
      // 保证读数、日历高亮、落库范围三者永远同源，不会出现手打值与点选值打架。
      render();
      // Keyboard entry: hand focus to the selected date (or first enabled action).
      // Escape and the popover close path already restore focus to the visible trigger.
      const initialFocus = /** @type {HTMLButtonElement | null} */ (section.querySelector('button.is-selected:not([disabled]), button.is-active:not([disabled]), button[aria-current="date"]:not([disabled])')
        || section.querySelector('button:not([disabled])'));
      if (global.matchMedia('(min-width: 960px)').matches) initialFocus?.focus({ preventScroll: true });
      // End keyboard entry.
    }; 

    /* ============ 事件绑定 ============ */
    trigger.addEventListener('click', (event) => openPicker(state.dim === 'yearly' ? 'yearly' : state.dim === 'monthly' ? 'monthly' : state.dim === 'weekly' ? 'weekly' : 'daily', event.currentTarget));
    inlinePresetBtns.forEach((btn) => btn.addEventListener('click', () => {
      closePicker();
      const next = rangeForPreset(btn.dataset.inlinePreset);
      state = { ...state, origin: 'preset' };
      applyRange(next.start, next.end, btn.dataset.inlinePreset);
      closePopover(true);
    }));
    // 粒度入口语义：点击后立即把当前范围折算到该粒度并清掉预设，
    // 保证顶栏文案与真实范围一致（不再出现「近30天 · 按年」），随后打开弹窗微调。
    const snapRangeToGrain = (grain, focusIso) => {
      const focus = parseDate(focusIso) || parseDate(state.endDate) || new Date(anchorDate);
      if (grain === 'daily') return { start: focus, end: focus, preset: 'custom' };
      if (grain === 'weekly') {
        const start = startOfWeek(focus);
        const end = shiftDays(start, 6);
        return { start, end: end > anchorDate ? new Date(anchorDate) : end, preset: 'custom' };
      }
      if (grain === 'monthly') {
        const start = new Date(focus.getFullYear(), focus.getMonth(), 1);
        const end = new Date(focus.getFullYear(), focus.getMonth() + 1, 0);
        return { start, end: end > anchorDate ? new Date(anchorDate) : end, preset: 'custom' };
      }
      const start = new Date(focus.getFullYear(), 0, 1);
      const end = new Date(focus.getFullYear(), 11, 31);
      return { start, end: end > anchorDate ? new Date(anchorDate) : end, preset: 'custom' };
    };
    inlineGrainBtns.forEach((btn) => btn.addEventListener('click', (event) => {
      const grain = ['daily', 'weekly', 'monthly', 'yearly'].includes(btn.dataset.inlineGrain) ? btn.dataset.inlineGrain : 'daily';
      const snapped = snapRangeToGrain(grain, state.endDate);
      state = { ...state, dim: grain, preset: snapped.preset, origin: 'grain' };
      applyRange(snapped.start, snapped.end, snapped.preset);
      openPicker(grain, event.currentTarget);
    }));
    // 左右箭头：按当前粒度前后移动一个周期，不改变粒度。
    // 向前越界时按数据截止日截断（而不是整体拒绝），保证箭头始终可用。
    inlineNavBtns.forEach((btn) => btn.addEventListener('click', () => {
      const direction = Number(btn.dataset.inlineNav) || 1;
      const start = parseDate(state.startDate);
      const end = parseDate(state.endDate);
      if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) return;
      let nextStart;
      let nextEnd;
      if (state.dim === 'yearly') {
        nextStart = new Date(start.getFullYear() + direction, 0, 1);
        nextEnd = new Date(start.getFullYear() + direction, 11, 31);
      } else if (state.dim === 'monthly') {
        nextStart = new Date(start.getFullYear(), start.getMonth() + direction, 1);
        nextEnd = new Date(nextStart.getFullYear(), nextStart.getMonth() + 1, 0);
      } else if (state.dim === 'weekly') {
        nextStart = shiftDays(start, 7 * direction);
        nextEnd = shiftDays(nextStart, 6);
      } else {
        nextStart = shiftDays(start, direction);
        nextEnd = shiftDays(end, direction);
      }
      // 前进越界：把起点回退到"恰好容纳到截止日"的位置，而不是整块拒绝。
      if (nextStart > anchorDate) return;
      if (nextEnd > anchorDate) nextEnd = new Date(anchorDate);
      state = { ...state, origin: 'grain' };
      applyRange(nextStart, nextEnd, state.preset);
    }));
    inlineCustomBtn?.addEventListener('click', (event) => {
      openPicker('custom', event.currentTarget);
    });
    modeBtns.forEach((btn) => btn.addEventListener('click', () => {
      if (btn.dataset.periodMode === 'custom') {
        draft.preset = 'custom';
      } else if (draft.preset === 'custom') {
        draft.preset = state.preset === 'custom' ? '30d' : state.preset;
      }
      renderAll();
    }));
    chipsEl.addEventListener('click', (event) => {
      const chip = closestFrom(event, '[data-chip]');
      if (!chip) return;
      const next = rangeForPreset(chip.dataset.chip);
      draft = { startDate: formatDate(next.start), endDate: formatDate(next.end), preset: chip.dataset.chip, compareMode: draft.compareMode, dim: draft.dim };
      commitDraft();
      closePopover(true);
    });
    btnCancel.addEventListener('click', () => closePopover(true));
    btnApply.addEventListener('click', () => {
      if (!draft || !draft.startDate || !draft.endDate) return;
      commitDraft();
      closePopover(true);
    });
    btnSwap.addEventListener('click', () => {
      const t = draft.startDate;
      draft.startDate = draft.endDate;
      draft.endDate = t;
      renderInputs(); renderCalendar(); renderFooter();
    });
    grainBtns.forEach((btn) => btn.addEventListener('click', () => {
      draft.dim = btn.dataset.grain;
      renderGrain(); renderFooter();
    }));
    yearSel.addEventListener('change', () => {
      calendarBase = new Date(Number(yearSel.value), calendarBase.getMonth(), 1);
      renderCalendar();
    });
    inputStart.addEventListener('change', () => {
      if (!inputStart.value) return;
      const n = normalizeRange(inputStart.value, draft.endDate);
      draft.startDate = n.start; draft.endDate = n.end; draft.preset = 'custom';
      renderCalendar(); renderFooter();
    });
    inputEnd.addEventListener('change', () => {
      if (!inputEnd.value) return;
      const n = normalizeRange(draft.startDate, inputEnd.value);
      draft.startDate = n.start; draft.endDate = n.end; draft.preset = 'custom';
      renderCalendar(); renderFooter();
    });
    popover.addEventListener('click', (event) => {
      const nav = closestFrom(event, '[data-nav]');
      if (nav) {
        event.stopPropagation();
        calendarBase = new Date(calendarBase.getFullYear(), calendarBase.getMonth() + Number(nav.dataset.nav), 1);
        renderCalendar();
        return;
      }
      const day = closestFrom(event, '[data-date]');
      if (!day) return;
      event.stopPropagation();
      const value = day.dataset.date;
      if (!draft.startDate || (draft.startDate && draft.endDate)) {
        draft.startDate = value; draft.endDate = ''; draft.preset = 'custom';
        renderInputs(); renderCalendar(); renderFooter();
      } else {
        const n = normalizeRange(draft.startDate, value);
        draft.startDate = n.start; draft.endDate = n.end; draft.preset = 'custom';
        renderInputs(); renderCalendar(); renderFooter();
      }
    });
    popover.addEventListener('mouseover', (event) => {
      const day = /** @type {HTMLButtonElement | null} */ (closestFrom(event, '[data-date]'));
      if (day && !day.disabled && draft && draft.startDate && !draft.endDate) renderCalendar(parseDate(day.dataset.date));
    });
    popover.addEventListener('mouseout', (event) => {
      if (closestFrom(event, '[data-date]')) renderCalendar();
    });
    compareBtns.forEach((btn) => btn.addEventListener('click', () => {
      draft.compareMode = btn.dataset.compareValue;
      renderFooter();
    }));
    document.addEventListener('click', (event) => {
      if (!popover.hasAttribute('hidden') && !popover.contains(event.target) && !trigger.contains(event.target)) closePopover(true);
    });
    document.addEventListener('keydown', (event) => {
      if (event.key !== 'Escape') return;
      if (pickerDialog) { closePicker(); return; }
      if (popover.hasAttribute('hidden')) return;
      event.preventDefault();
      event.stopPropagation();
      closePopover(true);
      trigger.focus();
    });

    /* ============ 公开 API（供页面适配器 / setReviewRange） ============ */
    const setSharedRange = (startValue, endValue, preset = 'custom') => {
      if (!isIsoDate(startValue) || !isIsoDate(endValue)) return false;
      const start = parseDate(startValue);
      const end = parseDate(endValue);
      state = { ...state, origin: preset === 'custom' ? 'custom' : 'preset' };
      return applyRange(start, end, preset);
    };
    const setReviewRange = (startValue, endValue) => {
      if (!isIsoDate(startValue) || !isIsoDate(endValue)) return false;
      const start = parseDate(startValue);
      const end = parseDate(endValue);
      return applyRange(start, end, 'custom', true);
    };

    /* ============ URL 恢复 / 锚点校准 ============ */
    const restoreRangeFromUrl = () => {
      const currentParams = new URLSearchParams(global.location.search);
      const requestedPreset = currentParams.get('preset') || '30d';
      const preset = Object.prototype.hasOwnProperty.call(PRESET_LABELS, requestedPreset) ? requestedPreset : '30d';
      const startParam = currentParams.get('start');
      const endParam = currentParams.get('end');
      const normalized = normalizeRange(startParam, endParam);
      const hasValidExplicitRange = Boolean(normalized.start && normalized.end);
      // 两条来源返回的类型不同：normalizeRange 给 ISO 字符串，rangeForPreset 给 Date 对象。
      // 必须在这里统一成 ISO，否则 Date 分支会被 parseDate 当成非法字符串，
      // 结果 formatDate 输出 NaN-NaN-NaN（数据源为空时最容易被看到）。
      let startIso;
      let endIso;
      if (hasValidExplicitRange) {
        startIso = normalized.start;
        endIso = normalized.end;
      } else {
        const next = rangeForPreset(preset);
        startIso = formatDate(next.start);
        endIso = formatDate(next.end);
      }
      const compare = currentParams.get('compare');
      const dim = currentParams.get('dim');
      state = {
        ...state,
        preset: hasValidExplicitRange ? 'custom' : preset,
        compareMode: Object.prototype.hasOwnProperty.call(COMPARE_LABELS, compare) ? compare : 'none',
        dim: ['daily', 'weekly', 'monthly', 'yearly'].includes(dim) ? dim : 'daily',
        startDate: startIso,
        endDate: endIso,
      };
      dispatchRange(false);
    };
    global.addEventListener('popstate', restoreRangeFromUrl);
    // 立即初始化日期范围，不依赖 API 返回（restoreRangeFromUrl 只从 URL/默认预设计算日期）
    calendarBase = new Date(anchorDate.getFullYear(), anchorDate.getMonth() - 1, 1);
    restoreRangeFromUrl();
    // 年份快跳选项
    for (let y = 2021; y <= anchorDate.getFullYear(); y += 1) {
      const opt = document.createElement('option');
      opt.value = String(y);
      opt.textContent = `${y} 年`;
      yearSel.appendChild(opt);
    }
    // 数据截止只描述 freshness，不改变系统日历、已提交范围、URL 或打开的草稿。
    apiReady.then((DemoApi) => DemoApi.request('/api/periods?dim=daily')).then((periods) => {
      const freshness = header.querySelector('[data-period-freshness]');
      if (!freshness) return;
      const latest = Array.isArray(periods) ? periods.map((row) => row && row.period).filter(isIsoDate).sort().pop() : null;
      freshness.textContent = latest ? `数据截至 ${latest}` : '数据截至未知';
      freshness.hidden = false;
    }).catch(() => { /* 失败保留未知说明，不影响日期选择 */ });

    return {
      getState: () => ({ ...state }),
      subscribe: (subscriber, immediate = true) => {
        if (typeof subscriber !== 'function') return () => {};
        rangeSubscribers.add(subscriber);
        if (immediate && state.startDate && state.endDate) {
          try { subscriber({ ...state }); } catch (error) { console.error('日期范围订阅回调失败', error); }
        }
        return () => rangeSubscribers.delete(subscriber);
      },
      setRange: setSharedRange,
      setReviewRange,
    };
  }

  global.TmallRuntime = global.TmallRuntime || {};
  global.TmallRuntime.createDateRangeStore = createDateRangeStore;
})(window);
