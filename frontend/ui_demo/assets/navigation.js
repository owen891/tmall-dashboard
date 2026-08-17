(function () {
  const allowed = new Set([
    'start', 'end', 'preset', 'compare', 'product_id', 'tier',
    'lifecycle_stage', 'promotion_channel', 'action_id',
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
