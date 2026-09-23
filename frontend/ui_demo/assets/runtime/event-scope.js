(function (global) {
  'use strict';

  function createEventScope() {
    const listeners = [];

    function on(target, type, handler, options) {
      if (!target?.addEventListener) return () => {};
      target.addEventListener(type, handler, options);
      const remove = () => target.removeEventListener(type, handler, options);
      listeners.push(remove);
      return remove;
    }

    function destroy() {
      while (listeners.length) listeners.pop()();
    }

    return Object.freeze({ on, destroy });
  }

  global.TmallRuntime = global.TmallRuntime || {};
  global.TmallRuntime.createEventScope = createEventScope;
})(window);
