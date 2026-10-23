(function () {
  // 跨页参数白名单。新增键时必须同时确认「目标页会读它」——
  // 白名单里的键如果没人消费，就是一个只增不减的死契约（action_id 曾是这种状态）。
  const allowed = new Set([
    'start', 'end', 'preset', 'compare', 'product_id', 'tier',
    'lifecycle_stage', 'promotion_channel', 'action_id',
    // 时间颗粒度。date-range-store.js:108 会从 URL 读 dim 并据此恢复粒度，
    // :193 也会把 dim 写回地址栏；但这里漏了它，导致跨页跳转时
    // 用户选的「按周/按月」被静默重置回 daily——同一段日期换页后意思就变了。
    'dim',
  ]);

  function build(path, values = {}) {
    const url = new URL(path, window.location.origin);
    Object.entries(values).forEach(([key, value]) => {
      if (allowed.has(key) && value != null && value !== '') url.searchParams.set(key, value);
    });
    return `${url.pathname}${url.search}`;
  }

  function fromCurrent(path, extra = {}) {
    const params = new URLSearchParams(window.location.search);
    const values = Object.fromEntries(params.entries());
    return build(path, { ...values, ...extra });
  }

  window.DemoNavigation = { build, fromCurrent, allowed: [...allowed] };
})();
