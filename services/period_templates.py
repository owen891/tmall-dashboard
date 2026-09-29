# -*- coding: utf-8 -*-
"""周/月/日复盘的段落模板（纯数据，无逻辑依赖）。

v2：周/月统一为同一套板块结构，对齐用户的月复盘 XMind 框架：
    品类汇总 / 货品 / 广告 / 市场监控 / 本期总结 / 下期规划。
周与月共用段落 key（保存与展示同构），仅提示文案随周期粒度变化。

v3：段落升级为「分析 / 根因 / 下一步规划」三段式（subsections），
对齐 XMind 每个板块总结的固定结构。周月同构同能——subsections 定义
完全一致，仅 placeholder 文案随周期粒度微调。
保存结构：sections[key] = {text, subsections: {analysis|root_cause|next_step}}。
text 永久保留（老复盘兼容 + 三段拼接回写 + 旧前端可读）。

旧模板（v1 周：performance/market/done/plan/highlights；
v1 月：category_summary/goods/ads/campaign/market/summary/next_plan）
通过 LEGACY_SECTION_ALIASES 只读迁移，老复盘内容不丢。
"""

from __future__ import annotations

TEMPLATE_VERSION = 'v3'

# 三段式子段定义（XMind：分析 → 根因 → 下一步规划）。
# 有根因树的板块三段全配；总结段沿用户既有「做了什么/亮点/卡点」习惯。
SUBSECTION_DEFS = {
    'triple': [
        {'key': 'analysis', 'title': '分析', 'required': True},
        {'key': 'root_cause', 'title': '根因', 'required': True},
        {'key': 'next_step', 'title': '下一步规划', 'required': False},
    ],
    'summary': [
        {'key': 'analysis', 'title': '做了什么 / 亮点', 'required': True},
        {'key': 'root_cause', 'title': '核心问题 / 根因', 'required': True},
        {'key': 'next_step', 'title': '卡点与所需支持', 'required': False},
    ],
    'plan': [
        {'key': 'analysis', 'title': '目标', 'required': True},
        {'key': 'root_cause', 'title': '达成路径', 'required': True},
        {'key': 'next_step', 'title': '任务排期', 'required': False},
    ],
}


def _template(noun):
    """noun 为 '本周'/'本月'，用于生成同一结构下的文案变体。"""
    next_noun = '下周' if noun == '本周' else '下月'
    return [
        {
            'key': 'category_summary',
            'title': f'{noun}品类汇总（销售与利润指标 / 完成情况分析 / 根因）',
            'hint': '先看三大指标（净销售 / 净利润 / 净费比）完成情况，再拆基础数据（访客、转化、客单、加购率、付费访客成本）定位根因。',
            'materials': ['metrics', 'target_path', 'breakdown'],
            'subsections': SUBSECTION_DEFS['triple'],
            'placeholder': '例：净销售完成 XX 万（达成率 XX%，环比 X%，同比 X%）；净利润 X 万；净费比 X%。',
            'required': True,
        },
        {
            'key': 'goods',
            'title': f'{noun}货品复盘（top单品 / 新品 / 问题单品 / 结构变化）',
            'hint': '结合净销售 TOP、付费 TOP、盈利/亏损 TOP 与新品榜，写货品结构与问题单品结论。',
            'materials': ['products'],
            'subsections': SUBSECTION_DEFS['triple'],
            'placeholder': '例：TOP10 占比 X%；持续下滑单品占比高；男款费比高款式少；新品上架 X 个贡献 X；需补充…',
            'required': True,
        },
        {
            'key': 'ads',
            'title': f'{noun}广告复盘（渠道与单品消耗 / 投产 / 费比）',
            'hint': '渠道维度看花费与投产，单品维度看 TOP 消耗商品的直接投产、加购成本、拉新成本。',
            'materials': ['ads', 'promotion_items'],
            'subsections': SUBSECTION_DEFS['triple'],
            'placeholder': '例：推广费 X 万，净费比 X%（环比 +Xpt），整体 ROI X；可扩大：…；需止损：…；渠道预算调整：全站 → 直通车/人群/内容…',
            'required': True,
        },
        {
            'key': 'market',
            'title': '市场监控（行业趋势 / 竞店动态 / 竞品动作）',
            'hint': '行业结论、增长需求与价格带机会、竞店与竞品的关键动作。',
            'materials': ['market'],
            'subsections': SUBSECTION_DEFS['triple'],
            'placeholder': '例：行业成交额环比 +X%，主流价格带下移；竞店 XX 主推…；竞品 XX 上新/调价…；我方应对：…',
            'required': False,
        },
        {
            'key': 'summary',
            'title': f'{noun}总结（做了什么 / 亮点 / 核心问题 / 卡点）',
            'hint': '先写本期实际完成的关键动作与结果，再写亮点与核心问题；卡点要写清楚需要谁、什么资源。',
            'materials': ['anomalies', 'alerts', 'actions_done'],
            'subsections': SUBSECTION_DEFS['summary'],
            'placeholder': '做了什么：完成 XX 主图替换，点击率 +X%…\n亮点：…\n核心问题：…\n卡点：…（需要 XX 支持）',
            'required': True,
        },
        {
            'key': 'next_plan',
            'title': f'{next_noun}规划（目标与达成路径 / 品类货品计划 / 任务排期）',
            'hint': '目标要可验收；写清基于目标要怎么达成；行动项必须有负责人、时间节点和验收方式。',
            'materials': ['actions_planned'],
            'subsections': SUBSECTION_DEFS['plan'],
            'placeholder': '目标：净销售 XX 万 / 利润率 X%；达成路径：加投 XX 渠道 / 提升 XX 转化…\n任务排期：W1…W4…\n行动计划：P0 …（负责人 / 截止 / 验收）',
            'required': True,
        },
    ]


WEEK_TEMPLATE = _template('本周')
MONTH_TEMPLATE = _template('本月')

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

# 旧模板 key → 新统一 key 的别名表（顺序即拼接顺序，新 key 自身最优先）。
# 用于读取历史复盘时把 v1 段落内容映射到 v2 段落下展示，写库仍存新 key。
# summary 是合并段（做了什么/亮点/卡点），v1 的 done/highlights/campaign 都归入。
LEGACY_SECTION_ALIASES = {
    'category_summary': ('performance',),
    'goods': (),
    'ads': (),
    'market': (),
    'summary': ('done', 'highlights', 'campaign'),
    'next_plan': ('plan',),
}


def _text_of(entry):
    if isinstance(entry, dict):
        return str(entry.get('text') or '').strip()
    return str(entry or '').strip()


def migrate_sections(period_type, sections):
    """把旧模板 key 的段落内容迁移到新统一 key（只读、幂等）。

    - 新 key 已有内容时保留，不与旧别名合并；
    - 旧别名按 LEGACY_SECTION_ALIASES 顺序拼接（summary 合并 done/highlights/campaign），
      避免合并段丢掉其中一部分内容；
    - 不在任何别名表里的 key 原样保留（day 模板不受影响）。
    """
    if not isinstance(sections, dict) or not sections:
        return sections
    if period_type == 'day':
        return sections
    migrated = dict(sections)
    for new_key, aliases in LEGACY_SECTION_ALIASES.items():
        if _text_of(migrated.get(new_key)):
            continue
        parts, sources = [], []
        for alias in aliases:
            text = _text_of(migrated.get(alias))
            if text:
                parts.append(text)
                sources.append(alias)
        if parts:
            migrated[new_key] = {
                'text': '\n\n'.join(parts),
                'migrated_from': ','.join(sources),
            }
    return migrated
