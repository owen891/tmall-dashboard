(function (global) {
  'use strict';

  function createRequestScope() {
    const active = new Map();
    let sequence = 0;

    function begin(key = 'default') {
      const previous = active.get(key);
      previous?.controller.abort();
      const controller = new AbortController();
      const token = ++sequence;
      const entry = { controller, token };
      active.set(key, entry);
      return {
        token,
        signal: controller.signal,
        isCurrent: () => active.get(key)?.token === token,
        finish: () => {
          if (active.get(key)?.token === token) active.delete(key);
        },
      };
    }

    function cancel(key = 'default') {
      const entry = active.get(key);
      if (!entry) return;
      entry.controller.abort();
      active.delete(key);
    }

    function cancelAll() {
      active.forEach((entry) => entry.controller.abort());
      active.clear();
    }

    return Object.freeze({ begin, cancel, cancelAll });
  }

  global.TmallRuntime = global.TmallRuntime || {};
  global.TmallRuntime.createRequestScope = createRequestScope;
})(window);
