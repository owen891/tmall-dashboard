from collections import Counter

from services.data_capability_service import DOMAIN_DEFINITIONS, build_catalog


PAGE_TYPES = {'primary', 'context', 'admin'}
SUPPORT_LEVELS = {'supported', 'conditional', 'unsupported', 'unclassified'}
CAPABILITY_MODES = {'observe', 'analyze', 'export', 'mutate', 'configure', 'workflow'}
MODAL_KINDS = {'detail', 'edit', 'config', 'flow'}


PAGE_DEFINITIONS = (
    {
        'key': 'overview', 'label': '数据概览', 'page_type': 'primary', 'route': '/',
        'core_question': '店铺最近发生了什么',
        'data_domains': ('store_daily', 'goals', 'actions'),
        'capability_keys': (
            'overview.view_kpis', 'overview.view_trend', 'overview.view_matrix',
            'overview.compare', 'overview.view_goal_progress', 'overview.view_customer_mix',
            'overview.view_funnel', 'overview.export', 'overview.event_edit',
        ),
    },
    {
        'key': 'products', 'label': '商品经营', 'page_type': 'primary', 'route': '/products',
        'core_question': '哪些商品需要处理',
        'data_domains': ('product_master', 'product_daily', 'actions'),
        'capability_keys': ('products.list', 'products.export', 'products.create_action', 'products.catalog_edit'),
    },
    {
        'key': 'promotion', 'label': '推广分析', 'page_type': 'primary', 'route': '/promotion',
        'core_question': '推广费用花在哪里，是否有效',
        'data_domains': ('promotion_daily', 'product_master'),
        'capability_keys': ('promotion.view', 'promotion.drilldown', 'promotion.export', 'promotion.contribution_analysis'),
    },
    {
        'key': 'lifecycle', 'label': '生命周期', 'page_type': 'primary', 'route': '/lifecycle',
        'core_question': '商品处于什么阶段',
        'data_domains': ('lifecycle', 'product_monthly'),
        'capability_keys': ('lifecycle.assessment', 'lifecycle.history', 'lifecycle.edit_stage'),
    },
    {
        'key': 'reviews', 'label': '经营复盘', 'page_type': 'primary', 'route': '/reviews',
        'core_question': '哪个动作是否有效',
        'data_domains': ('actions', 'product_weekly'),
        'capability_keys': ('reviews.list_actions', 'reviews.review_action', 'reviews.period_compare'),
    },
    {
        'key': 'data-center', 'label': '数据中心', 'page_type': 'primary', 'route': '/data-center',
        'core_question': '数据是否可信、是否可用',
        'data_domains': ('imports',),
        'capability_keys': ('data-center.view_catalog', 'data-center.import', 'data-center.revert'),
    },
    {
        'key': 'settings', 'label': '设置', 'page_type': 'primary', 'route': '/settings',
        'core_question': '业务口径如何管理',
        'data_domains': ('product_master',),
        'capability_keys': ('settings.view', 'settings.configure_templates', 'settings.configure_alerts'),
    },
    {
        'key': 'product-detail', 'label': '商品详情', 'page_type': 'context', 'route': '/products/:product_id',
        'core_question': '单个商品为什么变化',
        'data_domains': ('product_master', 'product_daily', 'promotion_daily', 'reviews', 'lifecycle', 'actions'),
        'capability_keys': ('product-detail.view', 'product-detail.create_action', 'product-detail.review_action', 'product-detail.export'),
    },
    {
        'key': 'goals', 'label': '经营目标', 'page_type': 'context', 'route': '/goals',
        'core_question': '目标是否按计划推进',
        'data_domains': ('goals', 'store_daily'),
        'capability_keys': ('goals.view', 'goals.adjust', 'goals.lock'),
    },
    {
        'key': 'compare', 'label': '周期对比', 'page_type': 'context', 'route': '/compare',
        'core_question': '两个周期差异在哪里',
        'data_domains': ('product_weekly',),
        'capability_keys': ('compare.view', 'compare.export'),
    },
    {
        'key': 'manage', 'label': '管理工作台', 'page_type': 'admin', 'route': '/manage',
        'core_question': '谁负责什么、何时执行',
        'data_domains': ('actions', 'imports'),
        'capability_keys': ('manage.view', 'manage.schedule'),
    },
)


CAPABILITY_DEFINITIONS = (
    {'key': 'overview.view_kpis', 'page_key': 'overview', 'label': '查看经营指标', 'mode': 'observe', 'support_level': 'supported', 'data_domains': ('store_daily',), 'metric_keys': ('net_sales', 'refund_rate'), 'api_endpoints': ('GET /api/overview',)},
    {'key': 'overview.view_trend', 'page_key': 'overview', 'label': '查看经营趋势', 'mode': 'analyze', 'support_level': 'supported', 'data_domains': ('store_daily',), 'metric_keys': ('net_sales',), 'api_endpoints': ('GET /api/overview/daily-matrix',)},
    {'key': 'overview.view_matrix', 'page_key': 'overview', 'label': '查看日度经营矩阵', 'mode': 'observe', 'support_level': 'conditional', 'data_domains': ('store_daily',), 'metric_keys': ('net_sales',), 'api_endpoints': ('GET /api/overview/daily-matrix',)},
    {'key': 'overview.compare', 'page_key': 'overview', 'label': '比较经营周期', 'mode': 'analyze', 'support_level': 'conditional', 'data_domains': ('store_daily',), 'metric_keys': ('net_sales',), 'api_endpoints': ('GET /api/compare',)},
    {'key': 'overview.view_goal_progress', 'page_key': 'overview', 'label': '查看目标进度', 'mode': 'observe', 'support_level': 'conditional', 'data_domains': ('goals',), 'metric_keys': (), 'api_endpoints': ('GET /api/target_progress',)},
    {'key': 'overview.view_customer_mix', 'page_key': 'overview', 'label': '查看客户构成', 'mode': 'analyze', 'support_level': 'conditional', 'data_domains': ('store_daily',), 'metric_keys': ('returning_buyer_ratio',), 'api_endpoints': ('GET /api/customer_analysis',)},
    {'key': 'overview.view_funnel', 'page_key': 'overview', 'label': '查看经营漏斗', 'mode': 'analyze', 'support_level': 'conditional', 'data_domains': ('store_daily',), 'metric_keys': ('payment_conversion_rate',), 'api_endpoints': ('GET /api/funnel',)},
    {'key': 'overview.export', 'page_key': 'overview', 'label': '导出经营矩阵', 'mode': 'export', 'support_level': 'conditional', 'data_domains': ('store_daily',), 'metric_keys': (), 'api_endpoints': ('GET /api/overview/daily-matrix',)},
    {'key': 'overview.event_edit', 'page_key': 'overview', 'label': '编辑经营事件标注', 'mode': 'mutate', 'support_level': 'conditional', 'data_domains': ('store_daily',), 'metric_keys': (), 'api_endpoints': ('GET /api/overview/events', 'POST /api/overview/events', 'DELETE /api/overview/events/:event_id')},
    {'key': 'products.list', 'page_key': 'products', 'label': '查看和筛选商品', 'mode': 'observe', 'support_level': 'supported', 'data_domains': ('product_master',), 'metric_keys': (), 'api_endpoints': ('GET /api/products',)},
    {'key': 'products.export', 'page_key': 'products', 'label': '导出商品结果', 'mode': 'export', 'support_level': 'conditional', 'data_domains': ('product_master',), 'metric_keys': (), 'api_endpoints': ('GET /api/products',)},
    {'key': 'products.create_action', 'page_key': 'products', 'label': '创建经营动作', 'mode': 'mutate', 'support_level': 'conditional', 'data_domains': ('product_master', 'actions'), 'metric_keys': (), 'api_endpoints': ('POST /api/actions',)},
    {'key': 'products.catalog_edit', 'page_key': 'products', 'label': '编辑商品分类与收藏', 'mode': 'mutate', 'support_level': 'conditional', 'data_domains': ('product_master',), 'metric_keys': (), 'api_endpoints': ('PUT /api/products/:product_id/metadata', 'POST /api/products/:product_id/star', 'POST /api/products/batch-update', 'POST /api/products/batch-tags', 'DELETE /api/products/batch-tags')},
    {'key': 'promotion.view', 'page_key': 'promotion', 'label': '查看推广表现', 'mode': 'observe', 'support_level': 'supported', 'data_domains': ('promotion_daily',), 'metric_keys': ('ad_roi',), 'api_endpoints': ('GET /api/promotion',)},
    {'key': 'promotion.drilldown', 'page_key': 'promotion', 'label': '推广粒度下钻', 'mode': 'analyze', 'support_level': 'conditional', 'data_domains': ('promotion_daily',), 'metric_keys': ('ad_roi',), 'api_endpoints': ('GET /api/promotion',)},
    {'key': 'promotion.export', 'page_key': 'promotion', 'label': '导出推广结果', 'mode': 'export', 'support_level': 'conditional', 'data_domains': ('promotion_daily',), 'metric_keys': (), 'api_endpoints': ('GET /api/promotion',)},
    {'key': 'promotion.contribution_analysis', 'page_key': 'promotion', 'label': '推广贡献分析', 'mode': 'analyze', 'support_level': 'conditional', 'data_domains': ('promotion_daily',), 'metric_keys': ('ad_roi',), 'api_endpoints': ('GET /api/promotion',)},
    {'key': 'lifecycle.assessment', 'page_key': 'lifecycle', 'label': '查看生命周期评估', 'mode': 'observe', 'support_level': 'conditional', 'data_domains': ('lifecycle', 'product_monthly'), 'metric_keys': (), 'api_endpoints': ('GET /api/lifecycle/assessments',)},
    {'key': 'lifecycle.history', 'page_key': 'lifecycle', 'label': '查看生命周期历史', 'mode': 'observe', 'support_level': 'conditional', 'data_domains': ('lifecycle',), 'metric_keys': (), 'api_endpoints': ('GET /api/lifecycle/:product_id/history',)},
    {'key': 'lifecycle.edit_stage', 'page_key': 'lifecycle', 'label': '调整生命周期阶段', 'mode': 'mutate', 'support_level': 'conditional', 'data_domains': ('lifecycle',), 'metric_keys': (), 'api_endpoints': ('PUT /api/lifecycle/:product_id',)},
    {'key': 'reviews.list_actions', 'page_key': 'reviews', 'label': '查看待复盘动作', 'mode': 'observe', 'support_level': 'supported', 'data_domains': ('actions',), 'metric_keys': (), 'api_endpoints': ('GET /api/actions/pending-review',)},
    {'key': 'reviews.review_action', 'page_key': 'reviews', 'label': '完成动作复盘', 'mode': 'workflow', 'support_level': 'conditional', 'data_domains': ('actions', 'product_weekly'), 'metric_keys': (), 'api_endpoints': ('POST /api/actions/:id/review',)},
    {'key': 'reviews.period_compare', 'page_key': 'reviews', 'label': '查看周期复盘', 'mode': 'analyze', 'support_level': 'conditional', 'data_domains': ('product_weekly',), 'metric_keys': (), 'api_endpoints': ('GET /api/period-reviews',)},
    {'key': 'data-center.view_catalog', 'page_key': 'data-center', 'label': '查看数据能力目录', 'mode': 'observe', 'support_level': 'supported', 'data_domains': ('imports',), 'metric_keys': (), 'api_endpoints': ('GET /api/data-capabilities',)},
    {'key': 'data-center.import', 'page_key': 'data-center', 'label': '预览与确认导入', 'mode': 'workflow', 'support_level': 'supported', 'data_domains': ('imports',), 'metric_keys': (), 'api_endpoints': ('POST /api/imports/preview', 'POST /api/imports')},
    {'key': 'data-center.revert', 'page_key': 'data-center', 'label': '撤销导入批次', 'mode': 'workflow', 'support_level': 'conditional', 'data_domains': ('imports',), 'metric_keys': (), 'api_endpoints': ('POST /api/imports/:id/revert',)},
    {'key': 'settings.view', 'page_key': 'settings', 'label': '查看设置', 'mode': 'observe', 'support_level': 'supported', 'data_domains': (), 'metric_keys': (), 'api_endpoints': ('GET /api/settings',)},
    {'key': 'settings.configure_templates', 'page_key': 'settings', 'label': '配置字段和视图模板', 'mode': 'configure', 'support_level': 'supported', 'data_domains': (), 'metric_keys': (), 'api_endpoints': ('PUT /api/settings',)},
    {'key': 'settings.configure_alerts', 'page_key': 'settings', 'label': '配置预警规则', 'mode': 'configure', 'support_level': 'supported', 'data_domains': (), 'metric_keys': (), 'api_endpoints': ('GET /api/alert-rules', 'POST /api/alert-rules', 'PUT /api/alert-rules/:rule_id', 'DELETE /api/alert-rules/:rule_id')},
    {'key': 'product-detail.view', 'page_key': 'product-detail', 'label': '查看商品详情', 'mode': 'observe', 'support_level': 'supported', 'data_domains': ('product_master', 'product_daily'), 'metric_keys': ('net_sales', 'ad_roi'), 'api_endpoints': ('GET /api/products/:product_id/detail',)},
    {'key': 'product-detail.create_action', 'page_key': 'product-detail', 'label': '从详情创建动作', 'mode': 'mutate', 'support_level': 'conditional', 'data_domains': ('product_master', 'actions'), 'metric_keys': (), 'api_endpoints': ('POST /api/actions',)},
    {'key': 'product-detail.review_action', 'page_key': 'product-detail', 'label': '从详情完成复盘', 'mode': 'workflow', 'support_level': 'conditional', 'data_domains': ('actions',), 'metric_keys': (), 'api_endpoints': ('POST /api/actions/:id/review',)},
    {'key': 'product-detail.export', 'page_key': 'product-detail', 'label': '导出商品详情', 'mode': 'export', 'support_level': 'conditional', 'data_domains': ('product_master', 'product_daily', 'actions'), 'metric_keys': (), 'api_endpoints': ('GET /api/products/:product_id/detail/export',)},
    {'key': 'goals.view', 'page_key': 'goals', 'label': '查看目标进度', 'mode': 'observe', 'support_level': 'supported', 'data_domains': ('goals',), 'metric_keys': (), 'api_endpoints': ('GET /api/goals/:year',)},
    {'key': 'goals.adjust', 'page_key': 'goals', 'label': '调整经营目标', 'mode': 'workflow', 'support_level': 'conditional', 'data_domains': ('goals',), 'metric_keys': (), 'api_endpoints': ('POST /api/goals/:year/adjustments',)},
    {'key': 'goals.lock', 'page_key': 'goals', 'label': '锁定经营目标', 'mode': 'workflow', 'support_level': 'conditional', 'data_domains': ('goals',), 'metric_keys': (), 'api_endpoints': ('POST /api/goals/:year/locks',)},
    {'key': 'compare.view', 'page_key': 'compare', 'label': '比较两个周期', 'mode': 'analyze', 'support_level': 'conditional', 'data_domains': ('product_weekly',), 'metric_keys': ('net_sales',), 'api_endpoints': ('GET /api/period-reviews',)},
    {'key': 'compare.export', 'page_key': 'compare', 'label': '导出周期比较', 'mode': 'export', 'support_level': 'conditional', 'data_domains': ('product_weekly',), 'metric_keys': (), 'api_endpoints': ('GET /api/period-reviews',)},
    {'key': 'manage.view', 'page_key': 'manage', 'label': '查看管理任务', 'mode': 'observe', 'support_level': 'conditional', 'data_domains': ('actions',), 'metric_keys': (), 'api_endpoints': ('GET /api/manage/tasks', 'GET /api/manage/kpis')},
    {'key': 'manage.schedule', 'page_key': 'manage', 'label': '执行调度流程', 'mode': 'workflow', 'support_level': 'conditional', 'data_domains': ('imports',), 'metric_keys': (), 'api_endpoints': ('GET /api/manage/schedules', 'POST /api/manage/schedules', 'PUT /api/manage/schedules/:task_id', 'DELETE /api/manage/schedules/:task_id', 'POST /api/manage/schedules/:task_id/run')},
    {'key': 'overview.industry_benchmark', 'page_key': 'overview', 'label': '行业基准对比', 'mode': 'analyze', 'support_level': 'unsupported', 'data_domains': (), 'metric_keys': (), 'api_endpoints': ('GET /api/industry_benchmark',)},
    {'key': 'promotion.causal_attribution', 'page_key': 'promotion', 'label': '严格因果归因', 'mode': 'analyze', 'support_level': 'unsupported', 'data_domains': (), 'metric_keys': (), 'api_endpoints': ()},
)


SURFACE_DEFINITIONS = (
    {'key': 'overview.event-edit', 'page_key': 'overview', 'label': '经营事件编辑', 'modal_kind': 'edit', 'trigger_capability': 'overview.event_edit', 'selector': '[data-overview-event-dialog]'},
    {'key': 'products.column-config', 'page_key': 'products', 'label': '商品列设置', 'modal_kind': 'config', 'trigger_capability': 'products.list', 'selector': '[data-products-columns-dialog]'},
    {'key': 'promotion.drilldown-detail', 'page_key': 'promotion', 'label': '推广下钻详情', 'modal_kind': 'detail', 'trigger_capability': 'promotion.drilldown', 'selector': '[data-promotion-dialog]'},
    {'key': 'lifecycle.edit-stage', 'page_key': 'lifecycle', 'label': '生命周期人工调整', 'modal_kind': 'edit', 'trigger_capability': 'lifecycle.edit_stage', 'selector': '[data-lifecycle-edit-dialog]'},
    {'key': 'reviews.action-review', 'page_key': 'reviews', 'label': '动作复盘', 'modal_kind': 'flow', 'trigger_capability': 'reviews.review_action', 'selector': '[data-reviews-list]'},
    {'key': 'data-center.import', 'page_key': 'data-center', 'label': '导入确认', 'modal_kind': 'flow', 'trigger_capability': 'data-center.import', 'selector': '[data-import-confirm]'},
    {'key': 'settings.alert-rule', 'page_key': 'settings', 'label': '预警规则编辑', 'modal_kind': 'config', 'trigger_capability': 'settings.configure_alerts', 'selector': '.alert-rules-dialog'},
    {'key': 'product-detail.dialog', 'page_key': 'product-detail', 'label': '共享商品详情', 'modal_kind': 'detail', 'trigger_capability': 'product-detail.view', 'selector': '[data-modal-kind="detail"]'},
    {'key': 'goals.adjust', 'page_key': 'goals', 'label': '目标调整', 'modal_kind': 'flow', 'trigger_capability': 'goals.adjust', 'selector': '[data-goals-adjust-form]'},
    {'key': 'manage.schedule', 'page_key': 'manage', 'label': '调度任务', 'modal_kind': 'flow', 'trigger_capability': 'manage.schedule', 'selector': '[data-manage-schedule-dialog]'},
)


_REGISTRY_OWNER = 'tm-dashboard'
_PAGE_TARGET_FILES = {
    'overview': ('frontend/ui_demo/pages/overview.html', 'frontend/ui_demo/assets/overview-live.js'),
    'products': ('frontend/ui_demo/pages/products.html', 'frontend/ui_demo/assets/products-live.js'),
    'promotion': ('frontend/ui_demo/pages/promotion.html', 'frontend/ui_demo/assets/promotion-live.js'),
    'lifecycle': ('frontend/ui_demo/pages/lifecycle.html', 'frontend/ui_demo/assets/lifecycle-live.js'),
    'reviews': ('frontend/ui_demo/pages/reviews.html', 'frontend/ui_demo/assets/reviews-live.js'),
    'data-center': ('frontend/ui_demo/pages/data-center.html', 'frontend/ui_demo/assets/data-center-live.js'),
    'settings': ('frontend/ui_demo/pages/settings.html', 'frontend/ui_demo/assets/settings-live.js'),
    'product-detail': ('frontend/ui_demo/pages/product-detail.html', 'frontend/ui_demo/assets/product-detail-dialog.js'),
    'goals': ('frontend/ui_demo/pages/goals.html', 'frontend/ui_demo/assets/goals-live.js'),
    'compare': ('frontend/ui_demo/pages/compare.html', 'frontend/ui_demo/assets/compare-live.js'),
    'manage': ('frontend/ui_demo/pages/manage.html', 'frontend/ui_demo/assets/manage-live.js'),
}


def _target_files(page_key):
    return _PAGE_TARGET_FILES.get(page_key, ())


def _acceptance_selector(page_key):
    return (f'body[data-page="{page_key}"]',)


def _enrich_registry_metadata():
    """Attach the delivery metadata required by the PRD registry contract."""
    global PAGE_DEFINITIONS, CAPABILITY_DEFINITIONS, SURFACE_DEFINITIONS
    PAGE_DEFINITIONS = tuple({
        **item,
        'owner': item.get('owner') or _REGISTRY_OWNER,
        'target_files': tuple(item.get('target_files') or _target_files(item['key'])),
        'acceptance_selectors': tuple(item.get('acceptance_selectors') or _acceptance_selector(item['key'])),
        'navigation_params': tuple(item.get('navigation_params') or ('start', 'end', 'product_id', 'promotion_channel')),
        'entry_points': tuple(item.get('entry_points') or (item['page_type'],)),
        'exit_points': tuple(item.get('exit_points') or ()),
    } for item in PAGE_DEFINITIONS)
    CAPABILITY_DEFINITIONS = tuple({
        **item,
        'owner': item.get('owner') or _REGISTRY_OWNER,
        'target_files': tuple(item.get('target_files') or _target_files(item['page_key'])),
        'acceptance_selectors': tuple(item.get('acceptance_selectors') or _acceptance_selector(item['page_key'])),
        'navigation_params': tuple(item.get('navigation_params') or ('start', 'end', 'product_id', 'promotion_channel')),
        'required_domain_capabilities': tuple(item.get('required_domain_capabilities') or item.get('data_domains') or ()),
    } for item in CAPABILITY_DEFINITIONS)
    SURFACE_DEFINITIONS = tuple({
        **item,
        'owner': item.get('owner') or _REGISTRY_OWNER,
        'target_files': tuple(item.get('target_files') or _target_files(item['page_key'])),
        'acceptance_selectors': tuple(item.get('acceptance_selectors') or (item['selector'],)),
        'navigation_params': tuple(item.get('navigation_params') or ('start', 'end', 'product_id', 'promotion_channel')),
        'read_only': item.get('read_only', item['modal_kind'] == 'detail'),
        'impact_scope': item.get('impact_scope') or ('none' if item['modal_kind'] == 'detail' else 'page-state'),
        'reversible': item.get('reversible', item['modal_kind'] in {'detail', 'edit', 'config', 'flow'}),
    } for item in SURFACE_DEFINITIONS)


_enrich_registry_metadata()


def _route_path_from_declaration(path):
    """Convert the registry's stable `:param` notation to Flask's rule form."""
    parts = []
    for segment in path.split('/'):
        parts.append(f'<{segment[1:]}>' if segment.startswith(':') else segment)
    return '/'.join(parts) or '/'


def _route_shape(path):
    return '/'.join('<>' if segment.startswith('<') and segment.endswith('>') else segment for segment in path.split('/')) or '/'


def _declared_endpoint_exists(app, declaration):
    method, _, path = declaration.partition(' ')
    if not method or not path:
        return False
    expected_path = _route_shape(_route_path_from_declaration(path))
    for rule in app.url_map.iter_rules():
        actual_path = str(rule)
        # Registry intentionally omits converter and parameter names; compare shape.
        actual_path = _route_shape(actual_path)
        if actual_path != expected_path:
            continue
        if method.upper() in {item.upper() for item in rule.methods}:
            return True
    return False


def validate_registry(app=None):
    errors = []
    page_keys = [item['key'] for item in PAGE_DEFINITIONS]
    capability_keys = [item['key'] for item in CAPABILITY_DEFINITIONS]
    surface_keys = [item['key'] for item in SURFACE_DEFINITIONS]
    if len(PAGE_DEFINITIONS) != 11:
        errors.append('expected eleven page definitions')
    for label, keys in (('page', page_keys), ('capability', capability_keys), ('surface', surface_keys)):
        duplicates = sorted(key for key, count in Counter(keys).items() if count > 1)
        if duplicates:
            errors.append(f'duplicate {label} keys: {", ".join(duplicates)}')
    for page in PAGE_DEFINITIONS:
        if page['page_type'] not in PAGE_TYPES:
            errors.append(f"invalid page type: {page['key']}")
        for metadata_key in ('owner', 'target_files', 'acceptance_selectors', 'navigation_params'):
            if not page.get(metadata_key):
                errors.append(f'missing page metadata: {page["key"]}.{metadata_key}')
        unknown_domains = sorted(set(page['data_domains']) - set(DOMAIN_DEFINITIONS))
        if unknown_domains:
            errors.append(f"unknown page domains: {page['key']}={','.join(unknown_domains)}")
    known_pages = set(page_keys)
    known_capabilities = set(capability_keys)
    for page in PAGE_DEFINITIONS:
        unknown_page_capabilities = sorted(set(page.get('capability_keys', ())) - known_capabilities)
        if unknown_page_capabilities:
            errors.append(
                f"unknown page capabilities: {page['key']}={','.join(unknown_page_capabilities)}"
            )
    for capability in CAPABILITY_DEFINITIONS:
        for metadata_key in ('owner', 'target_files', 'acceptance_selectors', 'navigation_params'):
            if not capability.get(metadata_key):
                errors.append(f'missing capability metadata: {capability["key"]}.{metadata_key}')
        if capability['page_key'] not in known_pages:
            errors.append(f"unknown capability page: {capability['key']}")
        if capability['support_level'] not in SUPPORT_LEVELS:
            errors.append(f"invalid support level: {capability['key']}")
        if capability['mode'] not in CAPABILITY_MODES:
            errors.append(f"invalid capability mode: {capability['key']}")
        unknown_domains = sorted(set(capability['data_domains']) - set(DOMAIN_DEFINITIONS))
        if unknown_domains:
            errors.append(f"unknown capability domains: {capability['key']}={','.join(unknown_domains)}")
        if app is not None:
            missing_endpoints = [
                endpoint for endpoint in capability['api_endpoints']
                if not _declared_endpoint_exists(app, endpoint)
            ]
            if missing_endpoints:
                errors.append(
                    f"missing capability endpoints: {capability['key']}={','.join(missing_endpoints)}"
                )
    for surface in SURFACE_DEFINITIONS:
        for metadata_key in ('owner', 'target_files', 'acceptance_selectors', 'navigation_params'):
            if not surface.get(metadata_key):
                errors.append(f'missing surface metadata: {surface["key"]}.{metadata_key}')
        if surface['page_key'] not in known_pages:
            errors.append(f"unknown surface page: {surface['key']}")
        if surface['trigger_capability'] not in known_capabilities:
            errors.append(f"unknown surface capability: {surface['key']}")
        if surface['modal_kind'] not in MODAL_KINDS:
            errors.append(f"invalid modal kind: {surface['key']}")
    return {'errors': errors}


def _availability_for_domains(domain_catalog, keys):
    if not keys:
        return 'available', []
    states = [domain_catalog.get(key, 'source-unavailable') for key in keys]
    if all(state == 'available' for state in states):
        return 'available', []
    if any(state in {'no-data', 'source-unavailable'} for state in states):
        return 'no-data', [key for key in keys if domain_catalog.get(key) in {'no-data', 'source-unavailable'}]
    if any(state in {'partial', 'missing-fields', 'insufficient-data'} for state in states):
        return 'partial', [key for key in keys if domain_catalog.get(key) != 'available']
    return 'calculation-failed', list(keys)


def _resolved_capability(definition, domain_catalog, domain_details=None):
    availability, missing_domains = _availability_for_domains(domain_catalog, definition['data_domains'])
    declared_support = definition['support_level']
    if declared_support == 'unsupported':
        support_level = 'unsupported'
        interaction_state = 'hidden'
    elif availability == 'available':
        support_level = declared_support
        interaction_state = 'enabled'
    else:
        support_level = 'conditional'
        interaction_state = 'disabled'
    domain_details = domain_details or {}
    details = [domain_details.get(key, {}) for key in definition['data_domains']]
    starts = [item.get('freshness', {}).get('start') for item in details if item.get('freshness', {}).get('start')]
    ends = [item.get('freshness', {}).get('end') for item in details if item.get('freshness', {}).get('end')]
    updates = [item.get('freshness', {}).get('latest_update') for item in details if item.get('freshness', {}).get('latest_update')]
    evidence_level = 'full' if availability == 'available' else 'insufficient' if availability in {'no-data', 'source-unavailable'} else 'partial'
    limitations = sorted({
        limitation
        for item in details
        for limitation in item.get('limitations', [])
    })
    if availability != 'available':
        limitations = sorted(set(limitations) | {
            f'前置数据域不可用: {key}' for key in missing_domains
        })
    return {
        **definition,
        'availability': availability,
        'support_level': support_level,
        'interaction_state': interaction_state,
        'missing_domains': missing_domains,
        'missing_prerequisites': [f'数据域不可用: {key}' for key in missing_domains],
        'evidence_level': evidence_level,
        'limitations': limitations,
        'freshness': {
            'start': min(starts) if starts else None,
            'end': max(ends) if ends else None,
            'latest_update': max(updates) if updates else None,
        },
    }


def build_page_catalog(db_path=None, *, page=None, domain=None, support_level=None, modal_kind=None, app=None):
    filters = {
        'page': page,
        'domain': domain,
        'support_level': support_level,
        'modal_kind': modal_kind,
    }
    invalid = {
        'page': set(item['key'] for item in PAGE_DEFINITIONS),
        'domain': set(DOMAIN_DEFINITIONS),
        'support_level': SUPPORT_LEVELS,
        'modal_kind': MODAL_KINDS,
    }
    for key, accepted in invalid.items():
        if filters[key] is not None and filters[key] not in accepted:
            raise ValueError(f'unknown {key}: {filters[key]}')
    domain_result = build_catalog(db_path)
    domain_catalog = {item['key']: item['availability'] for item in domain_result['domains']}
    domain_details = {item['key']: item for item in domain_result['domains']}
    registry = validate_registry(app)
    capabilities_by_page = {}
    for definition in CAPABILITY_DEFINITIONS:
        resolved = _resolved_capability(definition, domain_catalog, domain_details)
        if domain is not None and domain not in resolved['data_domains']:
            continue
        if support_level is not None and support_level != resolved['support_level']:
            continue
        capabilities_by_page.setdefault(resolved['page_key'], []).append(resolved)
    pages = []
    for definition in PAGE_DEFINITIONS:
        if page is not None and definition['key'] != page:
            continue
        page_capabilities = capabilities_by_page.get(definition['key'], [])
        if domain is not None and not page_capabilities:
            continue
        pages.append({**definition, 'capabilities': page_capabilities})
    visible_pages = {item['key'] for item in pages}
    visible_capabilities = {
        item['key'] for page_item in pages for item in page_item['capabilities']
    }
    surfaces = [
        dict(surface)
        for surface in SURFACE_DEFINITIONS
        if surface['page_key'] in visible_pages
        and surface['trigger_capability'] in visible_capabilities
        and (modal_kind is None or surface['modal_kind'] == modal_kind)
    ]
    resolved_capabilities = [
        item for page_item in pages for item in page_item['capabilities']
    ]
    summary = Counter(item['support_level'] for item in resolved_capabilities)
    endpoint_missing = [
        item['key'] for item in resolved_capabilities
        if item['support_level'] != 'unsupported' and not item['api_endpoints']
    ]
    blocked_capabilities = [
        item['key'] for item in resolved_capabilities
        if item['support_level'] != 'unsupported'
        and item['interaction_state'] != 'enabled'
    ]
    can_release = (
        not registry['errors']
        and not summary['unclassified']
        and not endpoint_missing
        and not blocked_capabilities
    )
    return {
        'summary': {
            'page_count': len(pages),
            'capability_count': len(resolved_capabilities),
            'surface_count': len(surfaces),
            'supported': summary['supported'],
            'conditional': summary['conditional'],
            'unsupported': summary['unsupported'],
            'unclassified': summary['unclassified'],
            'can_release': can_release,
        },
        'pages': pages,
        'surfaces': surfaces,
        'registry_errors': registry['errors'],
        'endpoint_missing': endpoint_missing,
        'blocked_capabilities': blocked_capabilities,
        'unsupported_capabilities': [
            item for item in resolved_capabilities
            if item['support_level'] == 'unsupported'
        ],
    }
