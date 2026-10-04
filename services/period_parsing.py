# -*- coding: utf-8 -*-
"""周期键解析：日历定位、周键生成、周期标签。"""

from __future__ import annotations

import calendar
import re
from datetime import date, datetime, timedelta

from db import get_db

PERIOD_TYPES = ('day', 'week', 'month')

_ISO_WEEK_KEY_RE = re.compile(r'^\d{4}-W\d{2}$')
_MONTH_WEEK_KEY_RE = re.compile(r'^(\d{4})-(\d{2})-W(\d)$')


# ---------------------------------------------------------------------------
# 周期解析
# ---------------------------------------------------------------------------


def _month_bounded_weeks(year, month):
    """计算某年某月的月内分周列表。

    返回 [(week_num, start_date, end_date), ...]，周不跨月：
    - 第 1 周：从 1 号到第一个周日
    - 中间周：周一到周日
    - 最后一周：从最后一个周一到月末
    """
    first_day = date(year, month, 1)
    last_day_num = calendar.monthrange(year, month)[1]
    last_day = date(year, month, last_day_num)

    weeks = []
    # 第 1 周：1 号到第一个周日
    first_sunday = first_day + timedelta(days=(6 - first_day.weekday()) % 7)
    if first_sunday > last_day:
        first_sunday = last_day
    weeks.append((1, first_day, first_sunday))

    # 中间周和最后一周
    current = first_sunday + timedelta(days=1)
    while current <= last_day:
        week_start = current
        week_end = current + timedelta(days=6)
        if week_end > last_day:
            week_end = last_day
        weeks.append((len(weeks) + 1, week_start, week_end))
        current = week_end + timedelta(days=1)

    return weeks


def _month_time_progress(end):
    """月内时间进度 = 周期结束日 / 当月天数（对齐用户「经营目标」表）。

    用户表实测：9 月 W1(9/1-6)=6/30=20.00%、W2(9/7-13)=13/30=43%、
    W3(9/14-20)=20/30=67%、W4(9/21-27)=27/30=90%、W5(9/28-30)=30/30=100%。
    它只跟**结束日**有关，所以月复盘恒为 100%、在途周也照常给值（用户表同样如此）。
    """
    days_in_month = calendar.monthrange(end.year, end.month)[1]
    return end.day / days_in_month


def resolve_period(period_type, period_key, today=None):
    """把周期键解析为起止日期、环比区间、同比区间与展示标签。"""
    today = today or date.today()
    if period_type == 'day':
        start = end = date.fromisoformat(period_key)
        prev_start = prev_end = start - timedelta(days=1)
        try:
            yoy_start = yoy_end = start.replace(year=start.year - 1)
        except ValueError:  # 2 月 29 日
            yoy_start = yoy_end = start.replace(year=start.year - 1, day=28)
    elif period_type == 'week':
        mb = _MONTH_WEEK_KEY_RE.match(period_key)
        if mb:
            # 月内分周：YYYY-MM-WN
            year, month, week_num = int(mb.group(1)), int(mb.group(2)), int(mb.group(3))
            weeks = _month_bounded_weeks(year, month)
            if week_num < 1 or week_num > len(weeks):
                raise ValueError(f'周数超出范围（1-{len(weeks)}）')
            _, start, end = weeks[week_num - 1]
            # 环比上一期：同月则取上一周，跨月则取上月最后一周
            if week_num > 1:
                _, prev_start, prev_end = weeks[week_num - 2]
            else:
                prev_year, prev_month = (year - 1, 12) if month == 1 else (year, month - 1)
                prev_weeks = _month_bounded_weeks(prev_year, prev_month)
                _, prev_start, prev_end = prev_weeks[-1]
            # 同比去年同期同月同周
            yoy_weeks = _month_bounded_weeks(year - 1, month)
            if week_num <= len(yoy_weeks):
                _, yoy_start, yoy_end = yoy_weeks[week_num - 1]
            else:
                _, yoy_start, yoy_end = yoy_weeks[-1]
        else:
            # 兼容 ISO 周：YYYY-WNN
            year, week = int(period_key[:4]), int(period_key[-2:])
            start = date.fromisocalendar(year, week, 1)
            end = start + timedelta(days=6)
            prev_start, prev_end = start - timedelta(days=7), end - timedelta(days=7)
            try:
                yoy_start = date.fromisocalendar(year - 1, week, 1)
            except ValueError:  # 去年没有第 53 周
                yoy_start = start - timedelta(days=364)
            yoy_end = yoy_start + timedelta(days=6)
    elif period_type == 'month':
        year, month = int(period_key[:4]), int(period_key[5:7])
        start = date(year, month, 1)
        end = date(year, month, calendar.monthrange(year, month)[1])
        prev_last = start - timedelta(days=1)
        prev_start = prev_last.replace(day=1)
        prev_end = prev_last
        yoy_start = start.replace(year=year - 1)
        yoy_end = end.replace(year=year - 1)
    else:
        raise ValueError('周期类型必须为 day、week 或 month')

    total_days = (end - start).days + 1
    if today < start:
        elapsed_days = 0
    elif today > end:
        elapsed_days = total_days
    else:
        elapsed_days = (today - start).days + 1

    return {
        'type': period_type,
        'key': period_key,
        'start': start.isoformat(),
        'end': end.isoformat(),
        'label': _period_label(period_type, period_key, start, end),
        'total_days': total_days,
        'elapsed_days': elapsed_days,
        'remaining_days': max(total_days - elapsed_days, 0),
        # 月内时间进度 = 本周期结束日 / 当月天数（对齐用户「经营目标」表）。
        # 用户表里这是**每个周期一个值**（跨 4 行合并单元格），不是逐指标算的：
        # 9 月 W1=6/30=20.00%、W2=13/30=43%、W3=20/30=67%、W4=27/30=90%、W5=30/30=100%。
        # 注意它按周期**结束日**算，不看 today，所以在途周期也有值。
        'time_progress': _month_time_progress(end),
        'is_ongoing': start <= today <= end,
        'prev': {'start': prev_start.isoformat(), 'end': prev_end.isoformat()},
        'yoy': {'start': yoy_start.isoformat(), 'end': yoy_end.isoformat()},
        'prev_key': _key_for(period_type, prev_start),
        'yoy_key': _key_for(period_type, yoy_start),
        'prev_label': _period_label(period_type, _key_for(period_type, prev_start), prev_start, prev_end),
        'yoy_label': _period_label(period_type, _key_for(period_type, yoy_start), yoy_start, yoy_end),
    }


def _key_for(period_type, day):
    """把某个日期折算成同类型的周期键（用于环比/同比/自定义对比）。"""
    if period_type == 'day':
        return day.isoformat()
    if period_type == 'week':
        # 月内分周：YYYY-MM-WN
        weeks = _month_bounded_weeks(day.year, day.month)
        for week_num, start, end in weeks:
            if start <= day <= end:
                return f'{day.year:04d}-{day.month:02d}-W{week_num}'
        return f'{day.year:04d}-{day.month:02d}-W1'
    return f'{day.year:04d}-{day.month:02d}'


_WEEKDAY_CN = ('周一', '周二', '周三', '周四', '周五', '周六', '周日')


def _period_label(period_type, period_key, start, end):
    if period_type == 'day':
        return f'{start.isoformat()}（{_WEEKDAY_CN[start.weekday()]}）'
    if period_type == 'week':
        if _MONTH_WEEK_KEY_RE.match(period_key):
            month = int(period_key[5:7])
            week_num = int(period_key[-1])
            return f'{start.year}年{month}月第{week_num}周（{start.strftime("%m-%d")} ~ {end.strftime("%m-%d")}）'
        return f'{period_key[:4]}年第{int(period_key[-2:])}周（{start.strftime("%m-%d")} ~ {end.strftime("%m-%d")}）'
    return f'{start.year}年{start.month}月'

# ---------------------------------------------------------------------------
# 对比周期
# ---------------------------------------------------------------------------

COMPARE_MODES = ('previous', 'yoy', 'custom', 'none')


def resolve_compare(period, compare_mode=None, compare_period_key=None):
    """解析对比周期。

    previous -> 环比上一期（默认）
    yoy      -> 同比去年同期
    custom   -> 调用方指定的同类型周期键（可自选对比周期）
    none     -> 不对比
    对比区间与主周期走完全相同的聚合口径，保证可比性。
    """
    mode = compare_mode if compare_mode in COMPARE_MODES else 'previous'

    if mode == 'none':
        return {'mode': 'none', 'available': False, 'short_label': '',
                'period_key': None, 'label': None, 'start': None, 'end': None}

    def comparable_range(start, end):
        """Limit an in-progress review baseline to the same elapsed days."""
        start_date = date.fromisoformat(start)
        end_date = date.fromisoformat(end)
        elapsed_days = max(1, int(period.get('elapsed_days') or period.get('total_days') or 1))
        span_days = (end_date - start_date).days + 1
        end_date = min(end_date, start_date + timedelta(days=min(elapsed_days, span_days) - 1))
        return start, end_date.isoformat()

    if mode == 'custom':
        key = str(compare_period_key or '').strip()
        if key:
            span = resolve_period(period['type'], key)
            start, end = comparable_range(span['start'], span['end'])
            return {'mode': 'custom', 'available': True, 'short_label': '对比',
                    'period_key': key, 'label': span['label'],
                    'start': start, 'end': end}
        # 只给了 custom 但没给周期键时退回环比，避免静默给出错误的基线。
        mode = 'previous'

    if mode == 'yoy':
        start, end = comparable_range(period['yoy']['start'], period['yoy']['end'])
        return {'mode': 'yoy', 'available': True, 'short_label': '同比',
                'period_key': period['yoy_key'], 'label': period['yoy_label'],
                'start': start, 'end': end}

    start, end = comparable_range(period['prev']['start'], period['prev']['end'])
    return {'mode': 'previous', 'available': True, 'short_label': '环比',
            'period_key': period['prev_key'], 'label': period['prev_label'],
            'start': start, 'end': end}


def recent_periods(period_type, period_key, limit=18):
    """当前周期往前若干期，供「自定义对比周期」下拉选择。"""
    options = []
    key = period_key
    for _ in range(max(1, limit)):
        span = resolve_period(period_type, key)
        options.append({'key': key, 'label': span['label'], 'start': span['start'], 'end': span['end']})
        key = span['prev_key']
    return options


def available_periods(period_type, limit=120):
    """Return selectable review periods covered by the daily facts."""
    if period_type not in ('day', 'week', 'month'):
        return []
    with get_db() as conn:
        rows = conn.execute(
            'SELECT DISTINCT date FROM daily_data WHERE date IS NOT NULL ORDER BY date DESC'
        ).fetchall()

    options = {}
    for row in rows:
        raw_date = str(row['date'] or '')
        try:
            period_key = _key_for(period_type, date.fromisoformat(raw_date))
            if period_key in options:
                continue
            span = resolve_period(period_type, period_key)
            options[period_key] = {
                'key': period_key,
                'label': span['label'],
                'start': span['start'],
                'end': span['end'],
            }
            if len(options) >= max(1, int(limit or 120)):
                break
        except (TypeError, ValueError):
            continue
    return list(options.values())
