(function (global) {
  'use strict';

  /** 日期范围订阅收敛：页面不再各自复制
   *  init(window.TmallDateRange?.getState?.()) +
   *  addEventListener('tmall:date-range-change', ...) 样板。
   *
   *  subscribeDateRange(handler, { immediate = true }) 会在当前已有范围时
   *  立即以 getState() 的快照调用一次（immediate），并在每次范围变化时以
   *  event.detail 调用；返回退订函数。handler 收到的 payload 与
   *  TmallDateRange.dispatchRange 派发的 detail 保持同一结构。 */

  function subscribeDateRange(handler, options = {}) {
    if (typeof handler !== 'function') return () => {};
    const { immediate = true } = options;
    const onChange = (event) => handler(event.detail);
    global.addEventListener('tmall:date-range-change', onChange);
    if (immediate && global.TmallDateRange?.getState) {
      const state = global.TmallDateRange.getState();
      if (state && state.startDate && state.endDate) {
        try { handler({ ...state }); } catch (error) { console.error('日期范围订阅回调失败', error); }
      }
    }
    return () => global.removeEventListener('tmall:date-range-change', onChange);
  }

  function getDateRange() {
    return global.TmallDateRange?.getState?.() || {};
  }

  global.TmallRuntime = global.TmallRuntime || {};
  global.TmallRuntime.subscribeDateRange = subscribeDateRange;
  global.TmallRuntime.getDateRange = getDateRange;
})(window);
