# -*- coding: utf-8 -*-
"""周/月/日复盘的段落模板（纯数据，无逻辑依赖）。"""

from __future__ import annotations

TEMPLATE_VERSION = 'v1'

WEEK_TEMPLATE = [
    {
        'key': 'performance',
        'title': '业绩全景及目标差距分析 & 达成路径',
        'hint': '先看本期业绩与目标差距，再写清楚差在哪、怎么补回来。',
        'materials': ['metrics', 'target_path'],
        'placeholder': '例：本期 GSV 完成 XX 万，距目标差 XX 万，主要缺口来自…；达成路径：加投 XX 渠道 / 提升 XX 商品转化…',
        'required': True,
    },
    {
        'key': 'market',
        'title': '市场分析（市场有什么变化、趋势、竞品有什么动作）？',
        'hint': '结合系统给的市场批次与竞店数据，写清市场端的变化和竞品动作。',
        'materials': ['market'],
        'placeholder': '例：类目整体需求上涨/下滑…；竞店 XX 在打价格战/上新…；我方需…',
        'required': False,
    },
    {
        'key': 'done',
        'title': '上周做了什么？',
        'hint': '列出本期实际完成的关键动作与结果，优先写有数据变化的。',
        'materials': ['actions_done'],
        'placeholder': '例：完成 XX 商品主图替换，点击率 +X%；调整 XX 计划出价，ROI 从 X 升到 X…',
        'required': True,
    },
    {
        'key': 'plan',
        'title': '下周计划做什么？',
        'hint': '每条计划都写清目标与验收标准，避免「持续优化」这类空话。',
        'materials': ['actions_planned'],
        'placeholder': '例：1) XX 商品补货并加投，目标 ROI≥X；2) 测试 XX 素材，目标点击率≥X%…',
        'required': True,
    },
    {
        'key': 'highlights',
        'title': '工作亮点、异常和卡点？',
        'hint': '亮点 / 异常 / 卡点分三类写；卡点要写清楚需要谁、什么资源。',
        'materials': ['anomalies', 'actions_blocked', 'alerts'],
        'placeholder': '亮点：…\n异常：…\n卡点：…（需要 XX 支持）',
        'required': True,
    },
]

MONTH_TEMPLATE = [
    {
        'key': 'category_summary',
        'title': '品类汇总与目标达成',
        'hint': '本月销售与利润总体结论、主要增长/下滑品类、需要优先处理的风险。',
        'materials': ['metrics', 'target_path'],
        'placeholder': '例：本月 GSV 完成 XX 万（达成率 XX%），利润率 X%；增长品类：…；下滑品类：…；优先风险：…',
        'required': True,
    },
    {
        'key': 'goods',
        'title': '货品复盘（爆款 / 利润款 / 新品 / 滞销与结构变化）',
        'hint': '爆款与利润款表现、新品测试结果、滞销与价格带问题、本月商品结构变化。',
        'materials': ['products'],
        'placeholder': '例：爆款 XX 贡献 XX 万；新品 XX 测试失败因…；滞销 XX 需清退；结构上…',
        'required': True,
    },
    {
        'key': 'ads',
        'title': '广告 / 推广复盘（渠道消耗、成交、ROI、费比）',
        'hint': '高效可扩大项、低效止损项及原因、素材/关键词/人群问题、费用是否在预算内。',
        'materials': ['ads'],
        'placeholder': '例：本月推广费 XX 万，费比 X%（环比 +Xpt），整体 ROI X；可扩大：…；需止损：…',
        'required': True,
    },
    {
        'key': 'campaign',
        'title': '活动复盘（目标 / 实际 / 利润费比 / 结论）',
        'hint': '活动的增量、对利润与价格体系的影响、下次继续或调整的动作。无活动可留空。',
        'materials': [],
        'placeholder': '例：XX 活动目标 XX，实际 XX，达成率 XX%；增量主要来自…；下次调整：…',
        'required': False,
    },
    {
        'key': 'market',
        'title': '市场监控（行业趋势 / 竞店动态 / 竞品动作）',
        'hint': '行业结论、增长需求与价格带机会、高竞争赛道、竞店与竞品的关键动作。',
        'materials': ['market'],
        'placeholder': '例：行业成交额环比 +X%，主流价格带下移；竞店 XX 主推…；竞品 XX 上新/调价…；我方应对：…',
        'required': False,
    },
    {
        'key': 'summary',
        'title': '本月总结（亮点 / 核心问题 / 未达成原因 / 需要的支持）',
        'hint': '亮点与核心问题各 3 条以内；未达成原因要区分「已验证」和「待验证假设」。',
        'materials': ['anomalies', 'alerts'],
        'placeholder': '亮点：1) … 2) …\n核心问题：1) … 2) …\n未达成原因（待验证）：…\n需要的支持：预算/货品/权限…',
        'required': True,
    },
    {
        'key': 'next_plan',
        'title': '下月计划（经营目标 / 品类货品计划 / 月度节奏 / 行动计划）',
        'hint': '目标要可验收；行动项必须有负责人、截止日期和验收方式。',
        'materials': ['actions_planned'],
        'placeholder': '目标：GSV XX 万 / 利润率 X%\n品类货品：…\n月度节奏：W1…W4…\n行动计划：P0 …（负责人 / 截止 / 验收）',
        'required': True,
    },
]

DAY_TEMPLATE = [
    {
        'key': 'performance',
        'title': '当日业绩与目标差距',
        'hint': '当日业绩结论、差距原因与补救动作。',
        'materials': ['metrics', 'target_path'],
        'placeholder': '例：当日 GSV XX，达成率 XX%，偏差来自…',
        'required': True,
    },
    {
        'key': 'anomaly',
        'title': '当日异常与卡点',
        'hint': '数据异常、执行卡点、需要支持的事项。',
        'materials': ['anomalies', 'alerts'],
        'placeholder': '异常：…\n卡点：…',
        'required': False,
    },
    {
        'key': 'plan',
        'title': '次日计划',
        'hint': '次日要做的关键动作与预期结果。',
        'materials': ['actions_planned'],
        'placeholder': '例：1) … 2) …',
        'required': False,
    },
]

TEMPLATES = {'day': DAY_TEMPLATE, 'week': WEEK_TEMPLATE, 'month': MONTH_TEMPLATE}
