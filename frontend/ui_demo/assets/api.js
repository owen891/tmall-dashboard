(function () {
  async function request(path, options = {}) {
    const response = await fetch(path, {
      headers: { Accept: 'application/json', ...(options.headers || {}) },
      ...options
    });
    if (!response.ok) {
      const raw = await response.text();
      let payload = null;
      try { payload = raw ? JSON.parse(raw) : null; } catch (_) {}
      const error = new Error(payload?.message || payload?.error || raw || `HTTP ${response.status}: ${path}`);
      error.status = response.status;
      error.code = payload?.code;
      error.details = payload?.details || {};
      throw error;
    }
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
    const allowed = ['available', 'no-data', 'insufficient-data', 'missing-fields', 'calculation-failed', 'source-unavailable', 'partial'];
    if (payload.availability && !allowed.includes(payload.availability)) payload.availability = 'calculation-failed';
    const normalized = context(payload);
    payload.availability = normalized.availability;
    payload.capabilities = normalized.capabilities;
    payload.filters = normalized.filters;
    payload.missing_fields = normalized.missingFields;
    payload.missing_ranges = normalized.missingRanges;
    payload.source_batches = normalized.sourceBatches;
    return payload;
  }

  function context(payload = {}) {
    return {
      availability: payload.availability || 'calculation-failed',
      capabilities: payload.capabilities || {},
      filters: payload.filters || {},
      missingFields: payload.missing_fields || [],
      missingRanges: payload.missing_ranges || [],
      sourceBatches: payload.source_batches || [],
    };
  }

  const legacyCapabilityMap = {
    overview: { can_export: 'overview.export', can_drilldown: 'overview.view_trend', can_create_action: 'overview.view_kpis' },
    products: { can_edit: 'products.catalog_edit', can_create_action: 'products.create_action' },
    promotion: { can_export: 'promotion.export', can_drilldown: 'promotion.drilldown' },
    lifecycle: { can_export: 'lifecycle.assessment', can_edit_stage: 'lifecycle.edit_stage' },
    reviews: { can_transition: 'reviews.review_action', can_recalculate: 'reviews.review_action' },
    'data-center': { can_import: 'data-center.import', can_revert: 'data-center.revert' },
    settings: { can_edit: 'settings.configure_templates' },
    goals: { can_edit: 'goals.adjust', can_lock: 'goals.lock' },
    manage: { can_schedule: 'manage.schedule' },
    'product-detail': { can_create_action: 'product-detail.create_action', can_review_action: 'product-detail.review_action' },
  };

  function can(payload, name) {
    const pageKey = document.body?.dataset.page;
    const mappedKey = legacyCapabilityMap[pageKey]?.[name];
    if (mappedKey && pageCapabilityCache.has(pageKey)) return canPage(pageKey, mappedKey);
    return payload?.capabilities?.[name] === true;
  }

  const pageCapabilityCache = new Map();
  const pageCapabilityTargets = {
    overview: [['[data-overview-report-refresh]', 'overview.view_kpis'], ['[data-overview-event-open]', 'overview.event_edit']],
    products: [['[data-products-reset]', 'products.list'], ['[data-demo-refresh]', 'products.list'], ['[data-products-starred]', 'products.catalog_edit'], ['[data-products-batch-apply]', 'products.catalog_edit'], ['[data-products-batch-tag-apply]', 'products.catalog_edit'], ['[data-products-batch-star]', 'products.catalog_edit']],
    promotion: [['[data-demo-refresh]', 'promotion.view'], ['[data-promotion-info]', 'promotion.drilldown']],
    lifecycle: [['[data-lifecycle-export]', 'lifecycle.assessment']],
    reviews: [['[data-reviews-refresh]', 'reviews.list_actions'], ['[data-actions-recalculate]', 'reviews.review_action']],
    settings: [['[data-settings-form]', 'settings.configure_templates'], ['[data-alert-rules-open]', 'settings.configure_alerts']],
    goals: [['[data-goals-form]', 'goals.view'], ['[data-goals-adjust-form]', 'goals.adjust']],
    manage: [['[data-manage-create-task]', 'manage.view'], ['[data-manage-create-schedule]', 'manage.schedule']],
    'data-center': [['[data-import-confirm]', 'data-center.import'], ['[data-import-preview]', 'data-center.import']],
    'product-detail': [['[data-product-detail-action-form]', 'product-detail.create_action']],
  };
  const applyPageCapabilityGates = (payload) => {
    const pageKey = payload?.filters?.page || document.body?.dataset.page;
    (pageCapabilityTargets[pageKey] || []).forEach(([selector, key]) => {
      document.querySelectorAll(selector).forEach((element) => element.dataset.capabilityKey = key);
    });
    const byKey = new Map((payload?.data?.pages || []).flatMap((page) =>
      (page.capabilities || []).map((capability) => [capability.key, capability]))
    );
    document.querySelectorAll('[data-capability-key]').forEach((element) => {
      const key = element.dataset.capabilityKey;
      const capability = byKey.get(key);
      if (!capability) return;
      const enabled = capability.interaction_state === 'enabled';
      const hidden = capability.interaction_state === 'hidden';
      element.hidden = hidden;
      if ('disabled' in element) element.disabled = !enabled;
      element.toggleAttribute('aria-disabled', !enabled && !hidden);
      if (!enabled && !hidden) {
        element.title = capability.missing_prerequisites?.join('；') || '当前数据条件不足';
      }
    });
    return payload;
  };
  async function loadPageCapabilities(pageKey = document.body?.dataset.page) {
    if (!pageKey) return null;
    if (!pageCapabilityCache.has(pageKey)) {
      const query = `?page=${encodeURIComponent(pageKey)}`;
      pageCapabilityCache.set(pageKey, domainRequest(`/api/page-capabilities${query}`));
    }
    const payload = await pageCapabilityCache.get(pageKey);
    return applyPageCapabilityGates(payload);
  }
  function canPage(pageKey, capabilityKey) {
    const cached = pageCapabilityCache.get(pageKey);
    const pages = cached?.data?.pages || [];
    const capability = pages.flatMap((page) => page.capabilities || []).find((item) => item.key === capabilityKey);
    return capability?.interaction_state === 'enabled';
  }

  const stateLabels = {
    loading: '加载中', 'no-data': '暂无数据', 'insufficient-data': '数据积累中',
    'missing-fields': '缺少必要字段', 'calculation-failed': '指标计算失败',
    'source-unavailable': '数据来源不可用', partial: '部分数据可用',
  };
  function renderDataState(container, state, details = {}) {
    if (!container) return;
    const key = stateLabels[state] ? state : 'calculation-failed';
    container.replaceChildren();
    container.classList.add('data-state');
    container.setAttribute('role', 'status');
    container.setAttribute('aria-live', 'polite');
    const title = document.createElement('strong'); title.textContent = stateLabels[key];
    const body = document.createElement('span'); body.textContent = details.message || details.reason || '';
    container.append(title, body);
    if (details.retry) { const button = document.createElement('button'); button.type = 'button'; button.className = 'button button--ghost'; button.textContent = '重试'; button.addEventListener('click', details.retry); container.appendChild(button); }
  }
  window.DemoApi = { request, domainRequest, optional, context, can, loadPageCapabilities, canPage, renderDataState };
  loadPageCapabilities().catch(() => {});
})();
