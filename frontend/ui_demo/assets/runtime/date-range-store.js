(function (global) {
  'use strict';

  /** 日期范围状态仓：从 shell.js 单闭包切出的 date-range-store。
   *
   *  本模块拥有日期范围的全部状态与行为：预设快捷范围、自定义日历弹层、
   *  URL 同步（start/end/preset/compare）、popstate 恢复、以及
   *  tmall:date-range-change / tmall:date-range-ready 两个全局事件。
   *  shell.js 与页面适配器经 window.TmallDateRange 消费，订阅收敛见
   *  runtime/date-range-scope.js。
   *
   *  deps 契约（由 shell.js 提供）：
   *  - header             顶栏元素（含 demo-period 结构）
   *  - currentPage        当前页面 key（无日期范围页不写 URL 参数）
   *  - apiReady           Promise<DemoApi>，用于 /api/periods 锚点校准
   *  - pagesWithoutDateRange Set<string>，不参与 URL 同步的页面集合
   */

  function createDateRangeStore(deps) {
    const { header, currentPage, apiReady, pagesWithoutDateRange } = deps;

    const range = header.querySelector('[data-period-range]');
    const presetSelect = header.querySelector('[data-date-preset]');
    const compareSelect = header.querySelector('[data-compare-mode]');
    const trigger = header.querySelector('[data-date-trigger]');
    const popover = header.querySelector('[data-period-popover]');
    const parseDate = (value) => { const [year, month, day] = value.split('-').map(Number); return new Date(year, month - 1, day); };
    const formatDate = (date) => `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
    const shiftDays = (date, amount) => { const next = new Date(date); next.setDate(next.getDate() + amount); return next; };
    const params = new URLSearchParams(global.location.search);
    let anchorDate = new Date();
    let calendarBase = new Date(anchorDate.getFullYear(), anchorDate.getMonth() - 1, 1);
    let draftStart = null;
    let state = { startDate: '', endDate: '', preset: params.get('preset') || '30d', compareMode: params.get('compare') || 'none' };
    let rangeReadyDispatched = false;
    const rangeSubscribers = new Set();

    const rangeForPreset = (preset) => {
      const offsets = { today: 0, yesterday: 0, '7d': 6, '30d': 29, '90d': 89 };
      const startOfWeek = (date) => shiftDays(date, -((date.getDay() + 6) % 7));
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
    const dispatchRange = (writeHistory = true) => {
      range.textContent = `${state.startDate} ~ ${state.endDate}`;
      const url = new URL(global.location.href);
      if (pagesWithoutDateRange.has(currentPage)) {
        url.searchParams.delete('start');
        url.searchParams.delete('end');
        url.searchParams.delete('preset');
        url.searchParams.delete('compare');
      } else {
        url.searchParams.set('start', state.startDate);
        url.searchParams.set('end', state.endDate);
        url.searchParams.set('preset', state.preset);
        url.searchParams.set('compare', state.compareMode);
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
      if (!allowFuture && end > anchorDate) return false;
      state = { ...state, startDate: formatDate(start), endDate: formatDate(end), preset };
      presetSelect.value = preset;
      dispatchRange();
      return true;
    };
    const renderCalendar = () => {
      const startValue = draftStart ? formatDate(draftStart) : state.startDate;
      const endValue = draftStart ? '' : state.endDate;
      [0, 1].forEach((offset) => {
        const month = new Date(calendarBase.getFullYear(), calendarBase.getMonth() + offset, 1);
        const year = month.getFullYear();
        const monthIndex = month.getMonth();
        const firstDay = new Date(year, monthIndex, 1).getDay();
        const total = new Date(year, monthIndex + 1, 0).getDate();
        const cells = Array(firstDay).fill('<span class="demo-calendar__blank"></span>');
        for (let day = 1; day <= total; day += 1) {
          const date = new Date(year, monthIndex, day);
          const value = formatDate(date);
          const inRange = startValue && endValue && value >= startValue && value <= endValue;
          const selected = value === startValue || value === endValue;
          cells.push(`<button type="button" data-calendar-date="${value}" class="${inRange ? 'is-in-range' : ''} ${selected ? 'is-selected' : ''}" ${date > anchorDate ? 'disabled' : ''}>${day}</button>`);
        }
        popover.querySelector(`[data-calendar-month="${offset}"]`).innerHTML = `<h3>${year}年${monthIndex + 1}月</h3><div class="demo-calendar__week"><span>日</span><span>一</span><span>二</span><span>三</span><span>四</span><span>五</span><span>六</span></div><div class="demo-calendar__grid">${cells.join('')}</div>`;
      });
    };
    const setPopover = (open) => {
      popover.toggleAttribute('hidden', !open);
      trigger.setAttribute('aria-expanded', String(open));
      if (open) renderCalendar();
    };
    const setCalendarHelp = () => {
      popover.querySelector('[data-calendar-help]').textContent = state.startDate && state.endDate
        ? `当前范围：${state.startDate} ~ ${state.endDate}；点击任意日期重新选择`
        : '请选择开始日期';
    };
    const resetDraftRange = () => {
      draftStart = null;
      setCalendarHelp();
    };
    const closePopover = (resetDraft = false) => {
      if (resetDraft) {
        resetDraftRange();
        presetSelect.value = state.preset;
      }
      setPopover(false);
    };
    const openPopover = () => {
      resetDraftRange();
      setPopover(true);
    };
    const selectPreset = (preset) => {
      if (preset === 'custom') { openPopover(); return; }
      closePopover(true);
      const next = rangeForPreset(preset);
      applyRange(next.start, next.end, preset);
    };
    trigger.addEventListener('click', () => {
      if (popover.hasAttribute('hidden')) openPopover();
      else closePopover(true);
    });
    presetSelect.addEventListener('change', () => selectPreset(presetSelect.value));
    compareSelect?.addEventListener('change', () => { state.compareMode = compareSelect.value; dispatchRange(); });
    popover.querySelector('[data-calendar-cancel]').addEventListener('click', () => closePopover(true));
    popover.querySelectorAll('[data-calendar-nav]').forEach((button) => button.addEventListener('click', () => {
      calendarBase = new Date(calendarBase.getFullYear(), calendarBase.getMonth() + Number(button.dataset.calendarNav) * 2, 1);
      renderCalendar();
    }));
    popover.addEventListener('click', (event) => {
      const button = event.target.closest('[data-calendar-date]');
      if (!button) return;
      event.stopPropagation();
      const chosen = parseDate(button.dataset.calendarDate);
      if (!draftStart) {
        draftStart = chosen;
        popover.querySelector('[data-calendar-help]').textContent = `${formatDate(chosen)}，请选择结束日期`;
        renderCalendar();
        return;
      }
      const start = chosen < draftStart ? chosen : draftStart;
      const end = chosen < draftStart ? draftStart : chosen;
      draftStart = null;
      applyRange(start, end, 'custom');
      closePopover(false);
    });
    document.addEventListener('click', (event) => {
      if (!popover.hasAttribute('hidden') && !popover.contains(event.target) && !trigger.contains(event.target) && event.target !== presetSelect) closePopover(true);
    });
    document.addEventListener('keydown', (event) => {
      if (event.key !== 'Escape' || popover.hasAttribute('hidden')) return;
      event.preventDefault();
      event.stopPropagation();
      closePopover(true);
      trigger.focus();
    });
    if (compareSelect) compareSelect.value = state.compareMode;
    const setSharedRange = (startValue, endValue, preset = 'custom') => {
      if (!startValue || !endValue || !/^\d{4}-\d{2}-\d{2}$/.test(startValue) || !/^\d{4}-\d{2}-\d{2}$/.test(endValue)) return false;
      const start = parseDate(startValue);
      const end = parseDate(endValue);
      if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime()) || start > end || end > anchorDate) return false;
      applyRange(start, end, preset);
      return true;
    };
    const setReviewRange = (startValue, endValue) => {
      if (!startValue || !endValue || !/^\d{4}-\d{2}-\d{2}$/.test(startValue) || !/^\d{4}-\d{2}-\d{2}$/.test(endValue)) return false;
      const start = parseDate(startValue);
      const end = parseDate(endValue);
      if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime()) || start > end) return false;
      return applyRange(start, end, 'custom', true);
    };
    const restoreRangeFromUrl = () => {
      const currentParams = new URLSearchParams(global.location.search);
      let preset = currentParams.get('preset') || '30d';
      const start = currentParams.get('start');
      const end = currentParams.get('end');
      if (start && end) preset = 'custom';
      state = { ...state, preset, compareMode: currentParams.get('compare') || 'none' };
      if (start && end) {
        state.startDate = start;
        state.endDate = end;
      } else {
        const next = rangeForPreset(preset);
        state.startDate = formatDate(next.start);
        state.endDate = formatDate(next.end);
      }
      presetSelect.value = state.preset;
      if (compareSelect) compareSelect.value = state.compareMode;
      dispatchRange(false);
    };
    global.addEventListener('popstate', restoreRangeFromUrl);
    // 立即初始化日期范围，不依赖 API 返回（restoreRangeFromUrl 只从 URL/默认预设计算日期）
    calendarBase = new Date(anchorDate.getFullYear(), anchorDate.getMonth() - 1, 1);
    restoreRangeFromUrl();
    // /api/periods 仅用于后续校准日历基准月份，失败不影响日期初始化
    apiReady.then((DemoApi) => DemoApi.request('/api/periods?dim=daily')).then((periods) => {
      if (Array.isArray(periods) && periods.length && periods[0].period) {
        const latest = new Date(periods[0].period + 'T00:00:00');
        if (!isNaN(latest.getTime())) {
          anchorDate = latest;
          calendarBase = new Date(latest.getFullYear(), latest.getMonth() - 1, 1);
          // 如果当前是动态预设（非custom），基于最新数据日期重新计算日期范围
          if (state.preset !== 'custom') {
            const next = rangeForPreset(state.preset);
            state.startDate = formatDate(next.start);
            state.endDate = formatDate(next.end);
            dispatchRange(false);
          }
        }
      }
    }).catch(() => { /* 静默忽略，日期已在上方初始化 */ });

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
