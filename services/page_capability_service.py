from collections import Counter
from pathlib import Path

from services.application_pages import LEGACY_REDIRECT_PAGES, registry_keys
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
            'overview.compare', 'overview.view_goal_progress',
            'overview.export', 'overview.create_action', 'overview.delete_action',
        ),
    },
    {
        'key': 'category-dashboard', 'label': '品类经营看板', 'page_type': 'primary', 'route': '/category-dashboard',
        'core_question': '品类规模、趋势和利润如何变化',
        'data_domains': ('product_master', 'product_daily', 'product_weekly', 'product_monthly'),
        'capability_keys': ('category-dashboard.view', 'category-dashboard.filter', 'category-dashboard.export'),
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
        'capability_keys': ('lifecycle.assessment', 'lifecycle.history', 'lifecycle.edit_stage', 'lifecycle.export'),
    },
    {
        'key': 'reviews', 'label': '经营复盘', 'page_type': 'primary', 'route': '/reviews',
        'core_question': '哪个动作是否有效',
        'data_domains': ('actions',),
        'capability_keys': ('reviews.list_actions', 'reviews.review_action', 'reviews.period_compare'),
    },
    {
        'key': 'period-review', 'label': '周期复盘', 'page_type': 'primary', 'route': '/period-review',
        'core_question': '本周/本月业绩差在哪、怎么补，做了什么、接下来做什么',
        'data_domains': ('product_daily', 'goals', 'actions', 'market'),
        'capability_keys': ('period-review.view', 'period-review.briefing', 'period-review.save'),
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
        'capability_keys': ('settings.view', 'settings.configure_templates', 'settings.configure_alerts', 'settings.import_scan_view', 'settings.import_scan_manage'),
    },
    {
        'key': 'product-detail', 'label': '商品详情', 'page_type': 'context', 'route': '/products/:product_id',
        'core_question': '单个商品为什么变化',
        'data_domains': ('product_master', 'product_daily', 'promotion_daily', 'product_sku_daily', 'product_region_daily', 'product_hourly', 'reviews', 'lifecycle', 'actions'),
        'capability_keys': ('product-detail.view', 'product-detail.granular_analysis', 'product-detail.create_action', 'product-detail.review_action', 'product-detail.export'),
    },
    {
        'key': 'goals', 'label': '经营目标', 'page_type': 'context', 'route': '/goals',
        'core_question': '目标是否按计划推进',
        'data_domains': ('goals', 'store_daily'),
        'capability_keys': ('goals.view', 'goals.bootstrap', 'goals.adjust', 'goals.lock'),
    },
    # 4-8：compare / manage 已退役（页面文件删除，/compare 与 /manage 保留为
    # 重定向到 /reviews 与 /settings，见 services/application_pages.LEGACY_REDIRECT_PAGES）。
    # 它们不再是可路由页面，因此也不再登记为 page / capability / surface。
    # The pages below were routable in `app.py` but missing from this registry,
    # so `/api/page-capabilities?page=<key>` answered 422 and the front-end gate
    # silently never applied. `services/application_pages.py` is now the single
    # source of truth and `validate_registry()` fails when the two drift.
    {
        'key': 'analysis', 'label': '经营分析', 'page_type': 'primary', 'route': '/analysis',
        'core_question': '经营指标之间如何相互影响',
        'data_domains': ('store_daily', 'product_daily', 'product_weekly'),
        'capability_keys': ('analysis.view', 'analysis.compare'),
    },
    {
        'key': 'keyword-promotion', 'label': '关键词推广', 'page_type': 'primary', 'route': '/keyword-promotion',
        'core_question': '哪些关键词值得继续投入',
        'data_domains': ('promotion_daily', 'product_master'),
        'capability_keys': ('keyword-promotion.view', 'keyword-promotion.products', 'keyword-promotion.export'),
    },
    {
        'key': 'new-products', 'label': '新品投放', 'page_type': 'primary', 'route': '/new-products',
        'core_question': '新品投放是否跑出效果',
        'data_domains': ('promotion_daily', 'product_daily', 'product_master'),
        'capability_keys': ('new-products.view', 'new-products.product_detail'),
    },
    {
        'key': 'promotion-matrix', 'label': '推广矩阵', 'page_type': 'primary', 'route': '/promotion-matrix',
        'core_question': '新老品在各渠道的投放效率如何、哪些单品该放大或优化',
        'data_domains': ('promotion_daily', 'product_daily', 'product_master'),
        'capability_keys': ('promotion-matrix.view',),
    },
    {
        'key': 'market-ranking', 'label': '市场排行', 'page_type': 'primary', 'route': '/market-ranking',
        'core_question': '市场大盘与竞品处于什么位置',
        'data_domains': ('market',),
        'capability_keys': ('market-ranking.view', 'market-ranking.drilldown'),
    },
    {
        'key': 'flow-source', 'label': '流量来源', 'page_type': 'primary', 'route': '/flow-source',
        'core_question': '流量从哪里来、质量如何',
        'data_domains': ('market',),
        'capability_keys': ('flow-source.view', 'flow-source.item_flow'),
    },
    {
        'key': 'rival-analysis', 'label': '竞品分析', 'page_type': 'primary', 'route': '/rival-analysis',
        'core_question': '竞品在卖什么、怎么卖',
        'data_domains': ('market', 'dmp_competition', 'dmp_shop'),
        'capability_keys': ('rival-analysis.view', 'rival-analysis.trend', 'rival-analysis.dmp_competition'),
    },
    {
        'key': 'data-collection', 'label': '数据采集', 'page_type': 'admin', 'route': '/data-collection',
        'core_question': '采集链路是否正常',
        'data_domains': ('imports',),
        'capability_keys': ('data-collection.view', 'data-collection.trigger'),
    },
    {
        'key': 'catalog', 'label': '组件目录', 'page_type': 'admin', 'route': '/component-catalog',
        'core_question': '设计系统提供了哪些组件',
        # A static design-system showcase: it renders without any business data
        # domain, so its gate is always satisfiable.
        'data_domains': (),
        'capability_keys': ('catalog.view',),
    },
    {
        'key': 'creative-board', 'label': '创意看板', 'page_type': 'primary', 'route': '/creative-board',
        'core_question': '投放创意表现如何',
        'data_domains': (),
        'capability_keys': ('creative-board.view',),
    },
    {
        # 核心单品九维分析：月度复盘沉淀的静态精选页（人工核准内容），
        # 配色统一走 themes/core-product-domain.css；内容不查库，
        # data_domains 留空（与 catalog 同理，门禁恒可满足）；
        # api_endpoints 挂 /api/version 是 catalog 先例：空端点会进 endpoint_missing 阻断 release。
        'key': 'core-product-analysis', 'label': '核心单品九维分析', 'page_type': 'primary', 'route': '/core-product-analysis',
        'core_question': '核心单品在九个经营维度上的完整表现与下一步',
        'data_domains': (),
        'capability_keys': ('core-product-analysis.view',),
    },
)


CAPABILITY_DEFINITIONS = (
    {'key': 'product-detail.granular_analysis', 'page_key': 'product-detail', 'label': 'View SKU, region, and hourly grain capability', 'mode': 'analyze', 'support_level': 'conditional', 'data_domains': ('product_sku_daily', 'product_region_daily', 'product_hourly'), 'metric_keys': (), 'api_endpoints': ('GET /api/products/:product_id/granular-capabilities',)},
    {'key': 'overview.view_kpis', 'page_key': 'overview', 'label': '查看经营指标', 'mode': 'observe', 'support_level': 'supported', 'data_domains': ('store_daily',), 'metric_keys': ('net_sales', 'refund_rate'), 'api_endpoints': ('GET /api/overview',)},
    {'key': 'overview.view_trend', 'page_key': 'overview', 'label': '查看经营趋势', 'mode': 'analyze', 'support_level': 'supported', 'data_domains': ('store_daily',), 'metric_keys': ('net_sales',), 'api_endpoints': ('GET /api/overview/daily-matrix',)},
    {'key': 'overview.view_matrix', 'page_key': 'overview', 'label': '查看日度经营矩阵', 'mode': 'observe', 'support_level': 'conditional', 'data_domains': ('store_daily',), 'metric_keys': ('net_sales',), 'api_endpoints': ('GET /api/overview/daily-matrix',)},
    {'key': 'overview.compare', 'page_key': 'overview', 'label': '比较经营周期', 'mode': 'analyze', 'support_level': 'conditional', 'data_domains': ('store_daily',), 'metric_keys': ('net_sales',), 'api_endpoints': ('GET /api/compare',)},
    {'key': 'overview.view_goal_progress', 'page_key': 'overview', 'label': '查看目标进度', 'mode': 'observe', 'support_level': 'conditional', 'data_domains': ('goals',), 'metric_keys': (), 'api_endpoints': ('GET /api/target_progress',)},
    {'key': 'overview.export', 'page_key': 'overview', 'label': '导出经营矩阵', 'mode': 'export', 'support_level': 'conditional', 'data_domains': ('store_daily',), 'metric_keys': (), 'api_endpoints': ('GET /api/overview/daily-matrix',)},
    {'key': 'overview.create_action', 'page_key': 'overview', 'label': '创建运营动作', 'mode': 'mutate', 'support_level': 'conditional', 'data_domains': ('product_master',), 'metric_keys': (), 'api_endpoints': ('POST /api/actions',)},
    {'key': 'overview.delete_action', 'page_key': 'overview', 'label': '删除运营动作', 'mode': 'mutate', 'support_level': 'conditional', 'data_domains': ('actions',), 'metric_keys': (), 'api_endpoints': ('DELETE /api/actions/:id',)},
    {'key': 'category-dashboard.view', 'page_key': 'category-dashboard', 'label': '查看品类经营看板', 'mode': 'observe', 'support_level': 'conditional', 'data_domains': ('product_master', 'product_daily', 'product_weekly', 'product_monthly'), 'metric_keys': ('net_sales', 'payment_conversion_rate', 'average_order_value', 'expense_ratio'), 'api_endpoints': ('GET /api/category-analysis/matrix', 'GET /api/category-analysis/compare')},
    {'key': 'category-dashboard.filter', 'page_key': 'category-dashboard', 'label': '筛选品类和分析周期', 'mode': 'analyze', 'support_level': 'conditional', 'data_domains': ('product_master', 'product_daily', 'product_weekly', 'product_monthly'), 'metric_keys': ('net_sales', 'payment_conversion_rate', 'average_order_value', 'expense_ratio'), 'api_endpoints': ('GET /api/category-analysis/matrix', 'GET /api/category-analysis/compare')},
    {'key': 'category-dashboard.export', 'page_key': 'category-dashboard', 'label': '导出品类看板结果', 'mode': 'export', 'support_level': 'unsupported', 'data_domains': ('product_daily', 'product_weekly', 'product_monthly'), 'metric_keys': (), 'api_endpoints': ()},
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
    {'key': 'lifecycle.export', 'page_key': 'lifecycle', 'label': '导出生命周期数据', 'mode': 'export', 'support_level': 'conditional', 'data_domains': ('lifecycle', 'product_monthly'), 'metric_keys': (), 'api_endpoints': ('GET /api/lifecycle/assessments',)},
    {'key': 'reviews.list_actions', 'page_key': 'reviews', 'label': '查看待复盘动作', 'mode': 'observe', 'support_level': 'supported', 'data_domains': ('actions',), 'metric_keys': (), 'api_endpoints': ('GET /api/actions/pending-review',)},
    # Weekly facts are not required to advance or review a formal action.
    {'key': 'reviews.review_action', 'page_key': 'reviews', 'label': '完成动作复盘', 'mode': 'workflow', 'support_level': 'conditional', 'data_domains': ('actions',), 'metric_keys': (), 'api_endpoints': ('POST /api/actions/:id/review',)},
    # Period reviews are human-entered records and can be viewed and saved
    # without weekly source facts.
    {'key': 'reviews.period_compare', 'page_key': 'reviews', 'label': '查看周期复盘', 'mode': 'analyze', 'support_level': 'supported', 'data_domains': (), 'metric_keys': (), 'api_endpoints': ('GET /api/period-reviews',)},
    {'key': 'period-review.view', 'page_key': 'period-review', 'label': '查看周期复盘', 'mode': 'observe', 'support_level': 'supported', 'data_domains': (), 'metric_keys': (), 'api_endpoints': ('GET /api/period-reviews/templates', 'GET /api/period-reviews/:period_type/:period_key')},
    # 复盘素材由系统聚合，缺失数据域时降级为「可手动填写」而不是阻断页面。
    {'key': 'period-review.briefing', 'page_key': 'period-review', 'label': '查看复盘素材聚合', 'mode': 'analyze', 'support_level': 'conditional', 'data_domains': ('product_daily', 'goals', 'actions', 'market'), 'metric_keys': ('net_sales', 'ad_roi', 'payment_conversion_rate'), 'api_endpoints': ('GET /api/period-reviews/:period_type/:period_key/context',)},
    # 复盘结论为人工录入记录，不依赖任何周期源事实即可保存。
    {'key': 'period-review.save', 'page_key': 'period-review', 'label': '保存周期复盘', 'mode': 'mutate', 'support_level': 'supported', 'data_domains': (), 'metric_keys': (), 'api_endpoints': ('PUT /api/period-reviews/:period_type/:period_key',)},
    {'key': 'data-center.view_catalog', 'page_key': 'data-center', 'label': '查看数据能力目录', 'mode': 'observe', 'support_level': 'supported', 'data_domains': ('imports',), 'metric_keys': (), 'api_endpoints': ('GET /api/data-capabilities',)},
    {'key': 'data-center.import', 'page_key': 'data-center', 'label': '预览与确认导入', 'mode': 'workflow', 'support_level': 'supported', 'data_domains': ('imports',), 'metric_keys': (), 'api_endpoints': ('POST /api/imports/preview', 'POST /api/imports')},
    {'key': 'data-center.revert', 'page_key': 'data-center', 'label': '撤销导入批次', 'mode': 'workflow', 'support_level': 'conditional', 'data_domains': ('imports',), 'metric_keys': (), 'api_endpoints': ('POST /api/imports/:id/revert',)},
    {'key': 'settings.view', 'page_key': 'settings', 'label': '查看设置', 'mode': 'observe', 'support_level': 'supported', 'data_domains': (), 'metric_keys': (), 'api_endpoints': ('GET /api/settings',)},
    {'key': 'settings.configure_templates', 'page_key': 'settings', 'label': '配置字段和视图模板', 'mode': 'configure', 'support_level': 'supported', 'data_domains': (), 'metric_keys': (), 'api_endpoints': ('PUT /api/settings',)},
    {'key': 'settings.configure_alerts', 'page_key': 'settings', 'label': '配置预警规则', 'mode': 'configure', 'support_level': 'supported', 'data_domains': (), 'metric_keys': (), 'api_endpoints': ('GET /api/alert-rules', 'POST /api/alert-rules', 'PUT /api/alert-rules/:rule_id', 'DELETE /api/alert-rules/:rule_id')},
    {'key': 'settings.import_scan_view', 'page_key': 'settings', 'label': '查看本地扫描任务', 'mode': 'observe', 'support_level': 'supported', 'data_domains': (), 'metric_keys': (), 'api_endpoints': ('GET /api/import-scans',)},
    {'key': 'settings.import_scan_manage', 'page_key': 'settings', 'label': '管理本地扫描任务', 'mode': 'configure', 'support_level': 'supported', 'data_domains': (), 'metric_keys': (), 'api_endpoints': ('POST /api/import-scans', 'PUT /api/import-scans/:job_id', 'DELETE /api/import-scans/:job_id', 'POST /api/import-scans/:job_id/run')},
    {'key': 'product-detail.view', 'page_key': 'product-detail', 'label': '查看商品详情', 'mode': 'observe', 'support_level': 'supported', 'data_domains': ('product_master', 'product_daily'), 'metric_keys': ('net_sales', 'ad_roi'), 'api_endpoints': ('GET /api/products/:product_id/detail',)},
    {'key': 'product-detail.create_action', 'page_key': 'product-detail', 'label': '从详情创建动作', 'mode': 'mutate', 'support_level': 'conditional', 'data_domains': ('product_master', 'actions'), 'metric_keys': (), 'api_endpoints': ('POST /api/actions',)},
    {'key': 'product-detail.review_action', 'page_key': 'product-detail', 'label': '从详情完成复盘', 'mode': 'workflow', 'support_level': 'conditional', 'data_domains': ('actions',), 'metric_keys': (), 'api_endpoints': ('POST /api/actions/:id/review',)},
    {'key': 'product-detail.export', 'page_key': 'product-detail', 'label': '导出商品详情', 'mode': 'export', 'support_level': 'conditional', 'data_domains': ('product_master', 'product_daily', 'actions'), 'metric_keys': (), 'api_endpoints': ('GET /api/products/:product_id/detail/export',)},
    {'key': 'goals.view', 'page_key': 'goals', 'label': '查看目标进度', 'mode': 'observe', 'support_level': 'supported', 'data_domains': ('goals',), 'metric_keys': (), 'api_endpoints': ('GET /api/goals/:year',)},
    {'key': 'goals.bootstrap', 'page_key': 'goals', 'label': '创建首个年度目标', 'mode': 'workflow', 'support_level': 'supported', 'data_domains': (), 'metric_keys': (), 'api_endpoints': ('POST /api/goals',)},
    {'key': 'goals.adjust', 'page_key': 'goals', 'label': '调整经营目标', 'mode': 'workflow', 'support_level': 'conditional', 'data_domains': ('goals',), 'metric_keys': (), 'api_endpoints': ('POST /api/goals/:year/adjustments',)},
    {'key': 'goals.lock', 'page_key': 'goals', 'label': '锁定经营目标', 'mode': 'workflow', 'support_level': 'conditional', 'data_domains': ('goals',), 'metric_keys': (), 'api_endpoints': ('POST /api/goals/:year/locks',)},
    {'key': 'promotion.causal_attribution', 'page_key': 'promotion', 'label': '严格因果归因', 'mode': 'analyze', 'support_level': 'unsupported', 'data_domains': (), 'metric_keys': (), 'api_endpoints': ()},
    # Capabilities for the pages added in 0-1. Every non-`unsupported` entry must
    # declare at least one endpoint that really exists in the Flask url map, or
    # `build_page_catalog()` reports it in `endpoint_missing` and blocks release.
    {'key': 'analysis.view', 'page_key': 'analysis', 'label': '查看经营分析', 'mode': 'observe', 'support_level': 'supported', 'data_domains': ('store_daily',), 'metric_keys': ('net_sales',), 'api_endpoints': ('GET /api/trend',)},
    {'key': 'analysis.compare', 'page_key': 'analysis', 'label': '比较品类周期', 'mode': 'analyze', 'support_level': 'conditional', 'data_domains': ('product_daily', 'product_weekly'), 'metric_keys': ('net_sales',), 'api_endpoints': ('GET /api/category-analysis/compare',)},
    {'key': 'keyword-promotion.view', 'page_key': 'keyword-promotion', 'label': '查看关键词推广', 'mode': 'observe', 'support_level': 'supported', 'data_domains': ('promotion_daily',), 'metric_keys': ('ad_roi',), 'api_endpoints': ('GET /api/keyword-promotion/summary',)},
    {'key': 'keyword-promotion.products', 'page_key': 'keyword-promotion', 'label': '下钻关键词商品', 'mode': 'analyze', 'support_level': 'conditional', 'data_domains': ('promotion_daily',), 'metric_keys': ('ad_roi',), 'api_endpoints': ('GET /api/keyword-promotion/products',)},
    {'key': 'keyword-promotion.export', 'page_key': 'keyword-promotion', 'label': '导出关键词结果', 'mode': 'export', 'support_level': 'conditional', 'data_domains': ('promotion_daily',), 'metric_keys': (), 'api_endpoints': ('GET /api/keyword-promotion/products',)},
    {'key': 'new-products.view', 'page_key': 'new-products', 'label': '查看新品投放', 'mode': 'observe', 'support_level': 'supported', 'data_domains': ('promotion_daily',), 'metric_keys': ('ad_roi',), 'api_endpoints': ('GET /api/promotion/new-products',)},
    {'key': 'new-products.product_detail', 'page_key': 'new-products', 'label': '下钻单品投放', 'mode': 'analyze', 'support_level': 'conditional', 'data_domains': ('product_daily',), 'metric_keys': ('net_sales',), 'api_endpoints': ('GET /api/promotion/product-detail',)},
    {'key': 'promotion-matrix.view', 'page_key': 'promotion-matrix', 'label': '查看推广矩阵', 'mode': 'observe', 'support_level': 'supported', 'data_domains': ('promotion_daily', 'product_daily', 'product_master'), 'metric_keys': ('ad_roi', 'expense_ratio'), 'api_endpoints': ('GET /api/promotion/matrix',)},
    {'key': 'market-ranking.view', 'page_key': 'market-ranking', 'label': '查看市场排行', 'mode': 'observe', 'support_level': 'conditional', 'data_domains': ('market',), 'metric_keys': (), 'api_endpoints': ('GET /api/market-ranking/summary',)},
    {'key': 'market-ranking.drilldown', 'page_key': 'market-ranking', 'label': '市场排行下钻', 'mode': 'analyze', 'support_level': 'conditional', 'data_domains': ('market',), 'metric_keys': (), 'api_endpoints': ('GET /api/market-ranking/products', 'GET /api/sycm/market/item-rank')},
    {'key': 'flow-source.view', 'page_key': 'flow-source', 'label': '查看流量来源', 'mode': 'observe', 'support_level': 'conditional', 'data_domains': ('market',), 'metric_keys': (), 'api_endpoints': ('GET /api/sycm/flow-source/summary',)},
    {'key': 'flow-source.item_flow', 'page_key': 'flow-source', 'label': '查看单品流量构成', 'mode': 'analyze', 'support_level': 'conditional', 'data_domains': ('market',), 'metric_keys': (), 'api_endpoints': ('GET /api/sycm/item-flow/summary', 'GET /api/sycm/item-flow/top-items')},
    {'key': 'rival-analysis.view', 'page_key': 'rival-analysis', 'label': '查看竞品分析', 'mode': 'observe', 'support_level': 'conditional', 'data_domains': ('market',), 'metric_keys': (), 'api_endpoints': ('GET /api/sycm/rival-shops/summary',)},
    {'key': 'rival-analysis.trend', 'page_key': 'rival-analysis', 'label': '竞品趋势对比', 'mode': 'analyze', 'support_level': 'conditional', 'data_domains': ('market',), 'metric_keys': (), 'api_endpoints': ('GET /api/sycm/rival-shops/trend', 'GET /api/sycm/rival-items/trend')},
    {'key': 'rival-analysis.dmp_competition', 'page_key': 'rival-analysis', 'label': '达摩盘竞争视角', 'mode': 'observe', 'support_level': 'supported', 'data_domains': ('dmp_competition', 'dmp_shop'), 'metric_keys': (), 'api_endpoints': ('GET /api/dmp/competition/summary', 'GET /api/dmp/competition/rivals', 'GET /api/dmp/competition/detection', 'GET /api/dmp/competition/ad-strategy', 'GET /api/dmp/shop/summary')},
    {'key': 'data-collection.view', 'page_key': 'data-collection', 'label': '查看采集状态', 'mode': 'observe', 'support_level': 'supported', 'data_domains': ('imports',), 'metric_keys': (), 'api_endpoints': ('GET /api/collect/status',)},
    {'key': 'data-collection.trigger', 'page_key': 'data-collection', 'label': '触发采集任务', 'mode': 'workflow', 'support_level': 'conditional', 'data_domains': ('imports',), 'metric_keys': (), 'api_endpoints': ('POST /api/collect/trigger', 'POST /api/collect/prepare')},
    # The catalog page is a static design-system showcase; `/api/version` is the
    # only endpoint its bundle calls, and it keeps the release gate satisfiable
    # without pretending a business data domain exists.
    {'key': 'catalog.view', 'page_key': 'catalog', 'label': '查看组件目录', 'mode': 'observe', 'support_level': 'supported', 'data_domains': (), 'metric_keys': (), 'api_endpoints': ('GET /api/version',)},
    {'key': 'creative-board.view', 'page_key': 'creative-board', 'label': '查看创意看板', 'mode': 'observe', 'support_level': 'supported', 'data_domains': (), 'metric_keys': (), 'api_endpoints': ('GET /api/creative-board',)},
    {'key': 'core-product-analysis.view', 'page_key': 'core-product-analysis', 'label': '查看核心单品九维分析', 'mode': 'observe', 'support_level': 'supported', 'data_domains': (), 'metric_keys': (), 'api_endpoints': ('GET /api/version',)},
)


SURFACE_DEFINITIONS = (
    {'key': 'overview.action-create', 'page_key': 'overview', 'label': '运营动作创建', 'modal_kind': 'edit', 'trigger_capability': 'overview.create_action', 'selector': '[data-overview-action-dialog]'},
    {'key': 'products.column-config', 'page_key': 'products', 'label': '商品列设置', 'modal_kind': 'config', 'trigger_capability': 'products.list', 'selector': '[data-products-columns-dialog]'},
    {'key': 'promotion.drilldown-detail', 'page_key': 'promotion', 'label': '推广下钻详情', 'modal_kind': 'detail', 'trigger_capability': 'promotion.drilldown', 'selector': '[data-promotion-dialog]'},
    {'key': 'lifecycle.edit-stage', 'page_key': 'lifecycle', 'label': '生命周期人工调整', 'modal_kind': 'edit', 'trigger_capability': 'lifecycle.edit_stage', 'selector': '[data-lifecycle-edit-dialog]'},
    {'key': 'reviews.action-review', 'page_key': 'reviews', 'label': '动作复盘', 'modal_kind': 'flow', 'trigger_capability': 'reviews.review_action', 'selector': '[data-reviews-list]'},
    {'key': 'data-center.import', 'page_key': 'data-center', 'label': '导入确认', 'modal_kind': 'flow', 'trigger_capability': 'data-center.import', 'selector': '[data-import-confirm]'},
    {'key': 'settings.alert-rule', 'page_key': 'settings', 'label': '预警规则编辑', 'modal_kind': 'config', 'trigger_capability': 'settings.configure_alerts', 'selector': '.alert-rules-dialog'},
    {'key': 'product-detail.dialog', 'page_key': 'product-detail', 'label': '共享商品详情', 'modal_kind': 'detail', 'trigger_capability': 'product-detail.view', 'selector': '[data-modal-kind="detail"]', 'target_files': ('frontend/ui_demo/pages/product-detail.html', 'frontend/ui_demo/assets/product-detail-dialog.js')},
    {'key': 'goals.adjust', 'page_key': 'goals', 'label': '目标调整', 'modal_kind': 'flow', 'trigger_capability': 'goals.adjust', 'selector': '[data-goals-months]'},
)


_REGISTRY_OWNER = 'tm-dashboard'
_PAGE_TARGET_FILES = {
    'overview': ('frontend/ui_demo/pages/overview.html', 'frontend/ui_demo/assets/overview-live.js'),
    'category-dashboard': ('frontend/ui_demo/pages/category-dashboard.html', 'frontend/ui_demo/assets/category-dashboard-live.js'),
    'products': ('frontend/ui_demo/pages/products.html', 'frontend/ui_demo/assets/products-live.js'),
    'promotion': ('frontend/ui_demo/pages/promotion.html', 'frontend/ui_demo/assets/promotion-live.js'),
    'lifecycle': ('frontend/ui_demo/pages/lifecycle.html', 'frontend/ui_demo/assets/lifecycle-live.js'),
    'reviews': ('frontend/ui_demo/pages/reviews.html', 'frontend/ui_demo/assets/reviews-live.js'),
    'period-review': ('frontend/ui_demo/pages/period-review.html', 'frontend/ui_demo/assets/period-review-live.js'),
    'data-center': ('frontend/ui_demo/pages/data-center.html',
                  'frontend/ui_demo/assets/pages/data-center/import-workflow.js',
                  'frontend/ui_demo/assets/pages/data-center/identity-review.js',
                  'frontend/ui_demo/assets/pages/data-center/capability-map.js',
                  'frontend/ui_demo/assets/pages/data-center/page-capabilities.js'),
    'settings': ('frontend/ui_demo/pages/settings.html', 'frontend/ui_demo/assets/settings-live.js'),
    'product-detail': ('frontend/ui_demo/pages/product-detail.html', 'frontend/ui_demo/assets/product-detail-live.js'),
    'goals': ('frontend/ui_demo/pages/goals.html', 'frontend/ui_demo/assets/goals-live.js'),
    'analysis': ('frontend/ui_demo/pages/analysis.html', 'frontend/ui_demo/assets/analysis-live.js'),
    'keyword-promotion': ('frontend/ui_demo/pages/keyword-promotion.html', 'frontend/ui_demo/assets/keyword-promotion-live.js'),
    'new-products': ('frontend/ui_demo/pages/new-products.html', 'frontend/ui_demo/assets/new-products-live.js'),
    'promotion-matrix': ('frontend/ui_demo/pages/promotion-matrix.html', 'frontend/ui_demo/assets/promotion-matrix-live.js'),
    'market-ranking': ('frontend/ui_demo/pages/market-ranking.html', 'frontend/ui_demo/assets/market-ranking-live.js'),
    'flow-source': ('frontend/ui_demo/pages/flow-source.html', 'frontend/ui_demo/assets/flow-source-live.js'),
    'rival-analysis': ('frontend/ui_demo/pages/rival-analysis.html', 'frontend/ui_demo/assets/rival-analysis-live.js'),
    'data-collection': ('frontend/ui_demo/pages/data-collection.html', 'frontend/ui_demo/assets/data-collection-live.js'),
    # The catalog renders from ui-components.js only — it has no page adapter.
    'catalog': ('frontend/ui_demo/pages/component-catalog.html', 'frontend/ui_demo/assets/ui-components.js'),
    'creative-board': ('frontend/ui_demo/pages/creative-board.html', 'frontend/ui_demo/assets/creative-board-live.js'),
    'core-product-analysis': ('frontend/ui_demo/pages/core-product-analysis.html', 'frontend/ui_demo/assets/core-product-analysis-live.js'),
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
    # The routable page set and this registry used to be two hand-maintained
    # lists, and they drifted: nine routable pages were missing here, so
    # `/api/page-capabilities?page=<key>` answered 422 and the front-end gate
    # silently never applied. Derive the expectation from the single source of
    # truth instead of asserting a magic count.
    expected_pages = registry_keys()
    registered_pages = set(page_keys)
    missing_pages = sorted(expected_pages - registered_pages)
    if missing_pages:
        errors.append(f'unregistered pages: {", ".join(missing_pages)}')
    unknown_pages = sorted(registered_pages - expected_pages - set(LEGACY_REDIRECT_PAGES))
    if unknown_pages:
        errors.append(f'registered but not routable: {", ".join(unknown_pages)}')
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
    project_root = Path(__file__).resolve().parents[1]
    for definition in PAGE_DEFINITIONS:
        if page is not None and definition['key'] != page:
            continue
        # Private-edition pages (e.g. the collector console) exist only when
        # their files ship with the deployment; a public checkout does not
        # carry them, so they drop out of the catalog — and the nav hides
        # entries that the catalog does not return.
        target_files = _target_files(definition['key'])
        if target_files and not (project_root / target_files[0]).is_file():
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
