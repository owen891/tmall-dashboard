(function () {
  async function request(path, options = {}) {
    const response = await fetch(path, {
      headers: { Accept: 'application/json', ...(options.headers || {}) },
      ...options
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}: ${path}`);
    return response.json();
  }

  async function optional(path, fallback, options) {
    try {
      return await request(path, options);
    } catch (_) {
      return typeof fallback === 'function' ? fallback() : fallback;
    }
  }

  async function domainRequest(path, options) {
    const payload = await request(path, options);
    if (!payload || payload.ok !== true) {
      const error = new Error(payload?.message || '接口响应格式错误');
      error.code = payload?.code || 'INVALID_RESPONSE';
      error.details = payload?.details || {};
      throw error;
    }
    return payload;
  }

  window.DemoApi = { request, domainRequest, optional };
})();
