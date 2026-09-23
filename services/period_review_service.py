# -*- coding: utf-8 -*-
"""经营周期复盘（周/月）服务——门面模块。

实现已按职责拆分：
- period_templates：周/月/日段落模板（纯数据）
- period_parsing：周期键解析 / 对比周期 / 可选周期
- period_context：素材聚合（业绩全景/目标路径/货品/市场/动作/告警/异常）
- period_matrix：指标矩阵 / 类目拆解

设计约束（随实现迁移）：
- 只读、幂等，不写入任何业务表。
- 缺失数据一律显式标记（None / 空列表），绝不把缺失当零值。
- 周/月复盘都以 daily_data 为主口径，weekly_data 为空时也能正常工作。

本模块保留原公共面（reviews_service.X 属性访问与既有 import 路径），
消费方（api/period_reviews_api.py、tests）无需改动。
"""

from __future__ import annotations

from services.period_parsing import (  # noqa: F401
    PERIOD_TYPES,
    COMPARE_MODES,
    resolve_period,
    resolve_compare,
    recent_periods,
    available_periods,
    _month_bounded_weeks,
)
from services.period_templates import (  # noqa: F401
    TEMPLATE_VERSION,
    TEMPLATES,
    WEEK_TEMPLATE,
    MONTH_TEMPLATE,
    DAY_TEMPLATE,
)
from services.period_context import (  # noqa: F401
    _daily_scope,
    _totals_for_range,
    _goal_target,
    _target_path,
    _target_rows,
    _products_block,
    _ads_block,
    _traffic_dimension,
    _promotion_dimension,
    _market_block,
    _actions_block,
    _alerts_block,
    _anomalies_block,
    template_for,
    build_context,
    legacy_fields_from_sections,
)
from services.period_matrix import (  # noqa: F401
    MATRIX_METRICS,
    build_metrics_matrix,
    build_category_breakdown,
)
