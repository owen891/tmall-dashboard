from datetime import date
import re

from flask import Blueprint, request

from api.api_response import evidence_level_for, failure, json_object, limitations_for, success
from repos.period_reviews_repo import PeriodReviewsRepo
from services import period_review_service as reviews_service
from services.category_mode_service import available_labels, mode_to_label, requested_category_mode


period_reviews_bp = Blueprint('period_reviews', __name__)

PERIOD_TYPES = ('day', 'week', 'month')


def _validate_period_key(period_type, period_key):
    key = str(period_key or '')
    try:
        if period_type == 'day':
            date.fromisoformat(key)
        elif period_type == 'month':
            parsed = date.fromisoformat(f'{key}-01')
            if key != f'{parsed.year:04d}-{parsed.month:02d}':
                raise ValueError
        elif period_type == 'week':
            # 月内分周（YYYY-MM-WN）或 ISO 周（YYYY-WNN）均可
            if re.fullmatch(r'\d{4}-\d{2}-W\d', key):
                year, month = int(key[:4]), int(key[5:7])
                week_num = int(key[-1])
                date(year, month, 1)  # 校验年月合法
                weeks = reviews_service._month_bounded_weeks(year, month)
                if week_num < 1 or week_num > len(weeks):
                    raise ValueError(f'周数超出范围（1-{len(weeks)}）')
            elif re.fullmatch(r'\d{4}-W\d{2}', key):
                date.fromisocalendar(int(key[:4]), int(key[-2:]), 1)
            else:
                raise ValueError
        else:
            raise ValueError
    except (TypeError, ValueError):
        raise ValueError('周期键格式不合法')


def _parse_period(period_type, period_key):
    """校验路径参数，返回 (period_type, period_key) 或抛出 ValueError。"""
    if period_type not in PERIOD_TYPES:
        raise ValueError('周期类型必须为 day、week 或 month')
    _validate_period_key(period_type, period_key)
    return period_type, period_key


def _review_evidence(period_type, period_key, action='read', row_count=1):
    return [{
        'source': 'period_reviews', 'period_type': period_type,
        'period_key': period_key, 'row_count': row_count, 'action': action,
    }]


@period_reviews_bp.route('/api/period-reviews')
def list_period_reviews():
    period_type = request.args.get('period_type')
    if period_type and period_type not in PERIOD_TYPES:
        return failure('VALIDATION_ERROR', '周期类型必须为 day、week 或 month', status=422)
    rows = PeriodReviewsRepo.list(period_type)
    availability = 'available' if rows else 'no-data'
    missing_inputs = [] if rows else ['period_reviews']
    return success(
        rows,
        availability=availability,
        evidence_level=evidence_level_for(availability, missing_inputs=missing_inputs),
        missing_inputs=missing_inputs,
        limitations=limitations_for(availability, missing_inputs=missing_inputs),
        evidence=_review_evidence(period_type or 'all', '*', row_count=len(rows)),
    )


@period_reviews_bp.route('/api/period-reviews/templates')
def period_review_templates():
    templates = {period: reviews_service.template_for(period) for period in PERIOD_TYPES}
    return success(
        {'template_version': reviews_service.TEMPLATE_VERSION, 'templates': templates},
        evidence_level='full',
        evidence=[{'source': 'period_review_templates', 'row_count': sum(len(v or []) for v in templates.values())}],
    )


@period_reviews_bp.route('/api/period-reviews/period-options')
def period_review_period_options():
    period_type = (request.args.get('period_type') or 'week').strip()
    if period_type not in ('day', 'week', 'month'):
        return failure('VALIDATION_ERROR', 'period_type must be day, week or month', status=422)
    limit = max(1, min(request.args.get('limit', 120, type=int) or 120, 240))
    options = reviews_service.available_periods(period_type, limit=limit)
    availability = 'available' if options else 'no-data'
    return success(
        {'period_type': period_type, 'options': options},
        availability=availability,
        evidence_level=evidence_level_for(availability, missing_inputs=[] if options else ['daily_data']),
        missing_inputs=[] if options else ['daily_data'],
        evidence=[{'source': 'daily_data', 'period_type': period_type, 'row_count': len(options)}],
    )


SYSTEM_CATEGORIES = (
    {'value': 'all', 'label': '全部品类', 'shop_label': None, 'enabled': True, 'system': True},
    {'value': 'sock', 'label': '标品袜子', 'shop_label': '标品袜子', 'enabled': True, 'system': True},
)


def _category_options():
    """系统品类恒可用；其后合并配置项与数据中发现的标签，避免设置未初始化时下拉为空。"""
    options = [dict(item) for item in SYSTEM_CATEGORIES]
    seen = {item['value'] for item in options}
    for item in available_labels():
        value = item.get('value')
        if not value or value in seen:
            continue
        options.append(item)
        seen.add(value)
    return options


@period_reviews_bp.route('/api/period-reviews/categories')
def period_review_categories():
    modes = _category_options()
    return success(
        {'categories': modes, 'default_mode': 'sock'},
        evidence_level='full',
        evidence=[{'source': 'category_modes', 'row_count': len(modes)}],
    )


@period_reviews_bp.route('/api/period-reviews/product-trend/<product_id>')
def period_review_product_trend(product_id):
    """单商品近 N 个周期的趋势序列（grain=week 周复盘 / month 月复盘联动）。只读。"""
    from services.period_context import _product_trend
    from db import get_db

    product_id = str(product_id or '').strip()
    if not product_id or len(product_id) > 64:
        return failure('VALIDATION_ERROR', '商品ID不合法', status=422)
    grain = request.args.get('grain', 'week')
    if grain not in ('week', 'month'):
        return failure('VALIDATION_ERROR', 'grain 只支持 week 或 month', status=422)
    weeks = request.args.get('weeks', 8, type=int)
    weeks = max(1, min(int(weeks or 8), 26))
    category_mode = requested_category_mode()
    category_label = mode_to_label(category_mode) if category_mode else None
    with get_db() as conn:
        data = _product_trend(conn, product_id, weeks=weeks, category_label=category_label, grain=grain)
    availability = 'available' if data['available'] else 'no-data'
    missing_inputs = [] if data['available'] else ['daily_data']
    return success(
        data,
        availability=availability,
        evidence_level=evidence_level_for(availability, missing_inputs=missing_inputs),
        missing_inputs=missing_inputs,
        limitations=limitations_for(availability, missing_inputs=missing_inputs),
        filters={'category_mode': category_mode or 'all', 'category_label': category_label, 'grain': grain},
        evidence=[{'source': 'daily_data', 'product_id': product_id, 'row_count': len(data['points'])}],
    )


@period_reviews_bp.route('/api/period-reviews/<period_type>/<period_key>')
def get_period_review(period_type, period_key):
    try:
        period_type, period_key = _parse_period(period_type, period_key)
    except ValueError as error:
        return failure('VALIDATION_ERROR', str(error), status=422)

    row = PeriodReviewsRepo.get(period_type, period_key)
    if row is not None and isinstance(row.get('sections'), dict):
        # 旧模板 key（v1 周/月）只读迁移到 v2 统一 key，前端按新模板渲染。
        row['sections'] = reviews_service.migrate_sections(period_type, row['sections'])
    template = reviews_service.template_for(period_type)
    payload = {'template': template, 'template_version': reviews_service.TEMPLATE_VERSION, 'review': row}
    if row is None:
        missing_inputs = ['period_reviews']
        return success(
            payload,
            availability='no-data',
            evidence_level=evidence_level_for('no-data', missing_inputs=missing_inputs),
            missing_inputs=missing_inputs,
            limitations=limitations_for('no-data', missing_inputs=missing_inputs),
            freshness={'period_type': period_type, 'period_key': period_key},
            evidence=_review_evidence(period_type, period_key, row_count=0),
        )
    return success(
        payload,
        freshness={'period_type': period_type, 'period_key': period_key},
        evidence=_review_evidence(period_type, period_key),
    )


@period_reviews_bp.route('/api/period-reviews/<period_type>/<period_key>/context')
def period_review_context(period_type, period_key):
    try:
        period_type, period_key = _parse_period(period_type, period_key)
    except ValueError as error:
        return failure('VALIDATION_ERROR', str(error), status=422)

    saved = PeriodReviewsRepo.get(period_type, period_key)
    saved_target = saved.get('target_amount') if saved else None
    # category_mode 由前端 api.js 自动附加（读全局品类模式），因此页面默认与全站口径联动。
    category_mode = requested_category_mode() or (saved.get('category_mode') if saved else None)

    compare_mode = (request.args.get('compare') or 'previous').strip() or 'previous'
    if compare_mode not in reviews_service.COMPARE_MODES:
        return failure(
            'VALIDATION_ERROR', '对比方式必须为 previous、yoy、custom 或 none',
            {'compare': compare_mode}, status=422,
        )
    compare_period_key = (request.args.get('compare_period') or '').strip()
    if compare_period_key:
        if compare_mode != 'custom':
            return failure(
                'VALIDATION_ERROR', '只有对比方式为 custom 时才能指定对比周期',
                {'compare': compare_mode, 'compare_period': compare_period_key}, status=422,
            )
        try:
            _validate_period_key(period_type, compare_period_key)
        except ValueError as error:
            return failure(
                'VALIDATION_ERROR', f'对比周期不合法：{error}',
                {'compare_period': compare_period_key}, status=422,
            )
    elif compare_mode == 'custom':
        return failure(
            'VALIDATION_ERROR', '对比方式为 custom 时必须提供 compare_period',
            {'compare': compare_mode}, status=422,
        )

    context = reviews_service.build_context(
        period_type, period_key, saved_target=saved_target, category_mode=category_mode,
        compare_mode=compare_mode, compare_period_key=compare_period_key or None,
        saved_review=saved,
    )

    has_data = context['metrics']['has_data']
    coverage_status = context['metrics'].get('coverage', {}).get('status')
    availability = 'no-data' if not has_data else ('partial' if coverage_status == 'partial' else 'available')
    missing_inputs = list(context.get('missing_inputs') or [])
    category_label = context['category'].get('label')
    if category_label and not has_data:
        missing_inputs = [f'{category_label} 品类日数据']
    return success(
        {'context': context, 'template': reviews_service.template_for(period_type),
         'template_version': reviews_service.TEMPLATE_VERSION},
        availability=availability,
        evidence_level=evidence_level_for(availability, missing_inputs=list(context.get('missing_inputs') or [])),
        missing_inputs=missing_inputs,
        limitations=limitations_for(availability, missing_inputs=missing_inputs),
        filters={'category_mode': context['category']['mode'], 'category_label': category_label,
                 'compare': context['compare']['mode'], 'compare_period': context['compare']['period_key']},
        freshness={'period_type': period_type, 'period_key': period_key,
                   'start': context['period']['start'], 'end': context['period']['end'],
                   'category_label': category_label,
                   'compare_period': context['compare']['period_key']},
        evidence=[{
            'source': 'daily_data', 'period_type': period_type, 'period_key': period_key,
            'start': context['period']['start'], 'end': context['period']['end'],
            'category_label': category_label,
            'row_count': context['metrics']['current'].get('day_count', 0),
        }],
        assumptions=[
            '复盘素材为系统聚合的经营事实，结论与判断由复盘人填写',
            f'当前口径：{category_label or "全部品类"}',
            f'对比基线：{context["compare"]["label"] or "不对比"}',
        ] + (['经营目标没有品类维度，目标为店铺级，与品类口径可能不一致'] if context['target_path'].get('scope_mismatch') else [])
        + (['所选对比周期在该口径下没有数据，环比变化不可用'] if context['compare']['available'] and not context['compare']['has_data'] else []),
    )


@period_reviews_bp.route('/api/period-reviews/<period_type>/<period_key>', methods=['PUT'])
def save_period_review(period_type, period_key):
    try:
        period_type, period_key = _parse_period(period_type, period_key)
    except ValueError as error:
        return failure('VALIDATION_ERROR', str(error), status=422)

    payload = json_object(request)
    reviewer = str(payload.get('reviewer') or '').strip()
    sections = payload.get('sections')
    structured = isinstance(sections, dict) and bool(sections)

    existing = PeriodReviewsRepo.get(period_type, period_key)
    # 品类口径：显式传入 > 全局 category_mode > 该期已保存的口径。写盘后复盘自带口径，
    # 之后换品类查看时能明确提示"这期是按哪个品类写的"。
    category_mode = (
        str(payload.get('category_mode') or '').strip()
        or requested_category_mode()
        or str((existing or {}).get('category_mode') or '')
    )

    template = reviews_service.template_for(period_type) or []
    valid_keys = {section['key'] for section in template}
    unknown_sections = []
    missing_required = []

    # 「只录目标」的局部保存：带了目标字段，但既没有结构化段落，也没有旧摘要三件套。
    # 目标与段落是两件独立的事，只改一个不该要求另一个必填——否则复盘设置里单独
    # 保存目标会被 422 拒掉，前端看起来像「保存没生效」。
    target_only = (
        not structured
        and any(key in payload for key in PeriodReviewsRepo.TARGET_FIELDS)
        and not any(str(payload.get(key) or '').strip()
                    for key in ('summary', 'conclusions', 'next_actions'))
    )

    if structured:
        # 旧客户端可能仍提交 v1 段落 key（周 performance/done/…），先迁移再校验，
        # 避免升级窗口期保存被 422 拒掉。迁移后剥离旧别名 key，
        # 库里只存 v2 key，不出现同一内容双份。
        sections = reviews_service.migrate_sections(period_type, sections)
        legacy_alias_keys = {
            alias
            for aliases in reviews_service.LEGACY_SECTION_ALIASES.values()
            for alias in aliases
        } if period_type != 'day' else set()
        sections = {key: value for key, value in sections.items() if key not in legacy_alias_keys}
        unknown_sections = sorted(key for key in sections if key not in valid_keys)
        if unknown_sections:
            return failure(
                'VALIDATION_ERROR', '存在未知的复盘段落', {'sections': unknown_sections}, status=422,
            )
        # v3 subsections 白名单校验 + text 回写：
        # 子段 key 必须在该段 subsections 定义内；text 存三段拼接，
        # 保证老版本前端/导出/legacy 摘要仍能从 text 读到完整内容。
        for section in template:
            entry = sections.get(section['key'])
            if not isinstance(entry, dict):
                continue
            subs = entry.get('subsections')
            allowed = {sub['key'] for sub in section.get('subsections') or []}
            if not allowed:
                if subs:
                    return failure(
                        'VALIDATION_ERROR', '该段落不支持子段',
                        {'sections': [section['key']], 'subsections': sorted(subs) if isinstance(subs, dict) else []},
                        status=422,
                    )
                continue
            if isinstance(subs, dict):
                unknown_subs = sorted(k for k in subs if k not in allowed)
                if unknown_subs:
                    return failure(
                        'VALIDATION_ERROR', '存在未知的段落子项',
                        {'sections': [section['key']], 'subsections': unknown_subs}, status=422,
                    )
                joined = '\n\n'.join(
                    str(subs.get(sub['key']) or '').strip()
                    for sub in section['subsections'] if str(subs.get(sub['key']) or '').strip()
                )
                if joined:
                    entry['text'] = joined
        missing_required = [
            section['key'] for section in template
            if section.get('required') and not str((sections.get(section['key']) or {}).get('text') or '').strip()
        ]
        if not reviewer:
            return failure('VALIDATION_ERROR', '复盘人不能为空', status=422)
        legacy = reviews_service.legacy_fields_from_sections(period_type, sections)
    elif target_only:
        if not reviewer:
            return failure('VALIDATION_ERROR', '复盘人不能为空', status=422)
        # 沿用已保存的摘要与段落，只覆盖目标字段（这三列 NOT NULL，缺省补空串）。
        previous = existing or {}
        legacy = {
            'summary': previous.get('summary') or '',
            'conclusions': previous.get('conclusions') or '',
            'next_actions': previous.get('next_actions') or '',
        }
        sections = previous.get('sections') or None
        # 状态按已保存段落重算，避免「只存目标」把还没写完的草稿误标成 final。
        saved_sections = previous.get('sections') or {}
        missing_required = [
            section['key'] for section in template
            if section.get('required') and not str((saved_sections.get(section['key']) or {}).get('text') or '').strip()
        ]
    else:
        if any(not payload.get(key) for key in ('summary', 'conclusions', 'next_actions', 'reviewer')):
            return failure('VALIDATION_ERROR', '周期复盘字段不完整', status=422)
        legacy = {
            'summary': payload['summary'],
            'conclusions': payload['conclusions'],
            'next_actions': payload['next_actions'],
        }
        # 旧表单只写摘要字段时保留已保存的结构化段落，避免互相覆盖。
        sections = (existing or {}).get('sections') or None

    # 目标字段：payload 未提供时沿用已保存值。
    # 否则「只改段落文字」的局部保存会把已录入的目标一起清空。
    targets = {
        key: (payload[key] if key in payload else (existing or {}).get(key))
        for key in PeriodReviewsRepo.TARGET_FIELDS
    }

    stored = PeriodReviewsRepo.upsert(period_type, period_key, {
        **legacy,
        **targets,
        'reviewer': reviewer,
        'sections': sections,
        'category_mode': category_mode,
        'status': payload.get('status') or ('draft' if missing_required else 'final'),
        'template_version': reviews_service.TEMPLATE_VERSION,
        'reason': payload.get('reason'),
    })

    category_label = mode_to_label(category_mode)
    return success(
        {
            'period_type': period_type,
            'period_key': period_key,
            'review': stored,
            'missing_required_sections': missing_required,
            'category': {'mode': category_mode, 'label': category_label},
        },
        evidence_level='full',
        freshness={'period_type': period_type, 'period_key': period_key, 'category_label': category_label},
        filters={'category_mode': category_mode, 'category_label': category_label},
        evidence=_review_evidence(period_type, period_key, action='upsert'),
        assumptions=['复盘内容是人工结论，不替代经营事实和指标证据'],
        unknowns=(
            [f"未填写的必填段落: {', '.join(missing_required)}"] if missing_required else None
        ),
    )


@period_reviews_bp.route('/api/period-reviews/<period_type>/<period_key>/matrix')
def get_period_review_matrix(period_type, period_key):
    """最近 N 期指标矩阵，用于复盘页「指标矩阵」表格。"""
    try:
        period_type, period_key = _parse_period(period_type, period_key)
    except ValueError as error:
        return failure('VALIDATION_ERROR', str(error), status=422)

    category_mode = requested_category_mode()
    limit = request.args.get('limit', 8, type=int)
    # 复盘表格不需要无限长的历史，夹紧到 1~26 期避免被拿来当全量导出。
    limit = max(1, min(int(limit or 8), 26))
    data = reviews_service.build_metrics_matrix(period_type, period_key, category_mode=category_mode, limit=limit)
    has_data = any(row['metrics']['net_sales']['value'] is not None for row in data['rows'])
    availability = 'available' if has_data else 'no-data'
    missing_inputs = [] if has_data else ['daily_data']
    return success(
        data,
        availability=availability,
        evidence_level=evidence_level_for(availability, missing_inputs=missing_inputs),
        missing_inputs=missing_inputs,
        limitations=limitations_for(availability, missing_inputs=missing_inputs),
        filters={'category_mode': data['category']['mode'], 'category_label': data['category']['label']},
        freshness={'period_type': period_type, 'period_key': period_key,
                   'category_label': data['category']['label']},
        evidence=[
            {'source': 'daily_data', 'period_type': period_type, 'period_key': period_key,
             'row_count': len(data['rows'])},
            # 无界花费/成交不在 BI 日度导出里（「万相台」列整列为 '--'），
            # 实际取自万相台后台采集表。
            {'source': 'promotion_daily_facts', 'period_type': period_type, 'period_key': period_key,
             'grain': 'product', 'channel': '全部'},
        ],
    )


@period_reviews_bp.route('/api/period-reviews/<period_type>/<period_key>/category-breakdown')
def get_period_review_category_breakdown(period_type, period_key):
    """当前周期按 products.category 拆解，用于复盘页「类目拆解」表格。"""
    try:
        period_type, period_key = _parse_period(period_type, period_key)
    except ValueError as error:
        return failure('VALIDATION_ERROR', str(error), status=422)

    category_mode = requested_category_mode()
    data = reviews_service.build_category_breakdown(period_type, period_key, category_mode=category_mode)
    has_data = any(row['metrics']['net_sales']['value'] is not None for row in data['rows'])
    availability = 'available' if has_data else 'no-data'
    missing_inputs = [] if has_data else ['daily_data']
    return success(
        data,
        availability=availability,
        evidence_level=evidence_level_for(availability, missing_inputs=missing_inputs),
        missing_inputs=missing_inputs,
        limitations=limitations_for(availability, missing_inputs=missing_inputs),
        filters={'category_mode': data['category']['mode'], 'category_label': data['category']['label']},
        freshness={'period_type': period_type, 'period_key': period_key,
                   'category_label': data['category']['label']},
        evidence=[{'source': 'daily_data', 'period_type': period_type, 'period_key': period_key,
                   'row_count': len(data['rows'])}],
    )
