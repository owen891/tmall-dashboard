from flask import current_app, request
import os, uuid, threading, calendar, math, time
import pandas as pd
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
from db import get_db
from api.api_response import failure
from utils.cache import cache as _ttl_cache, read_mutation_generation


# 获取项目根目录的绝对路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 安全设计：以下白名单确保table/date_col/visitors_col不会被SQL注入
# 所有SQL拼接仅使用此字典中的硬编码值，不接受用户输入
DIMENSION_MAP = {
    'monthly': {'table': 'monthly_data', 'date_col': 'month', 'visitors_col': 'visitors'},
    'weekly':  {'table': 'weekly_data',  'date_col': 'week_start', 'visitors_col': 'ipv'},
    'daily':   {'table': 'daily_data',   'date_col': 'date', 'visitors_col': 'ipv'},
}

def _request_cache_key(prefix):
    """生成基于请求路径和查询参数的缓存 key

    键里带上库内 mutation generation：后台扫描进程直接调 ImportService.confirm
    写库，不会触发 Web 进程的 cache.clear()，只有 generation 变了旧键才失效，
    否则首页会继续返回 30~60 秒的旧数据（CACHE-01）。
    """
    params = sorted(request.args.items())
    param_str = "&".join(f"{k}={v}" for k, v in params)
    shop_id = getattr(getattr(__import__('flask').g, 'shop_id', None), '__str__', lambda: 'default')()
    generation = read_mutation_generation()
    return f"{prefix}:{request.path}:{shop_id}:{param_str}:g{generation}"


def cached_api(prefix, ttl=60):
    """API 缓存装饰器：缓存成功的 JSON 响应，ttl 秒"""
    def decorator(f):
        def wrapped(*args, **kwargs):
            key = _request_cache_key(prefix)
            cached = _ttl_cache.get(key)
            if cached is not None:
                from flask import jsonify as _jsonify
                return _jsonify(cached)
            result = f(*args, **kwargs)
            try:
                if hasattr(result, 'status_code') and result.status_code == 200 and hasattr(result, 'get_json'):
                    data = result.get_json()
                    if data is not None:
                        # 读取 generation 失败时不要写入缓存：键里没有有效的
                        # generation，写入就等于放弃了跨进程失效能力。
                        if read_mutation_generation() is not None:
                            _ttl_cache.set(key, data, ttl)
            except Exception:
                # 缓存存储失败不影响主流程响应
                pass
            return result
        wrapped.__name__ = getattr(f, '__name__', 'wrapped')
        wrapped.__doc__ = getattr(f, '__doc__', '')
        return wrapped
    return decorator


def _validate_period_arg(dimension, value, field='period'):
    """Reject malformed explicit period values before querying legacy facts."""
    if not value:
        return None
    period_format = '%Y-%m' if dimension == 'monthly' else '%Y-%m-%d'
    try:
        parsed = datetime.strptime(value, period_format)
    except (TypeError, ValueError):
        return failure(
            'VALIDATION_ERROR',
            f'{field} must use {period_format.replace("%Y", "YYYY").replace("%m", "MM").replace("%d", "DD")}',
            {'dim': dimension, field: value},
            status=422,
        )
    if parsed.strftime(period_format) != value:
        return failure(
            'VALIDATION_ERROR',
            f'{field} must use {period_format.replace("%Y", "YYYY").replace("%m", "MM").replace("%d", "DD")}',
            {'dim': dimension, field: value},
            status=422,
        )
    return None

UPLOAD_FOLDER = os.path.join(project_root, 'data/uploads/')


def _upload_folder():
    """Resolve uploads from the active app while keeping legacy patch hooks."""
    configured = current_app.config.get('UPLOAD_FOLDER') if current_app else None
    return os.path.abspath(configured or UPLOAD_FOLDER)


def _reject_legacy_shop_scope(dimension):
    # Legacy period tables share the canonical single-shop scope guard.
    if dimension in {'weekly', 'monthly'}:
        from services.shop_scope_service import reject_legacy_shop_scope
        return reject_legacy_shop_scope(dimension)
    return None


def _validate_file_pattern(pattern):
    value = str(pattern or '*.xlsx').strip()
    normalized = value.replace('\\', '/')
    if not value or ntpath.isabs(value) or any(part == '..' for part in normalized.split('/')):
        raise ValueError('file_pattern 只能匹配 data/uploads 内的相对路径')
    return value


def _scheduled_matches(pattern):
    safe_pattern = _validate_file_pattern(pattern)
    upload_root = _upload_folder()
    matches = _glob.glob(os.path.join(upload_root, safe_pattern))
    return [
        path for path in matches
        if os.path.commonpath([upload_root, os.path.abspath(path)]) == upload_root
    ]




def _aov_expression(dimension):
    """Return the canonical AOV formula for a legacy dimension endpoint."""
    if dimension == 'weekly':
        # weekly_data predates the canonical buyer field; retain its imported
        # AOV rather than dividing GMV by visitors.
        return 'AVG(avg_order_value)'
    return (
        'CASE WHEN SUM(buyers) > 0 '
        'THEN SUM(payment_amount) * 1.0 / SUM(buyers) ELSE NULL END'
    )


def get_prev_period(period, dim):
    """获取上一个周期的值"""
    try:
        if dim == 'monthly':
            y, m = period.split('-')
            m = int(m) - 1
            if m == 0:
                m, y = 12, str(int(y) - 1)
            return f"{y}-{m:02d}"
        elif dim == 'weekly':
            d = datetime.strptime(period, '%Y-%m-%d')
            prev = d - timedelta(days=7)
            return prev.strftime('%Y-%m-%d')
        else:  # daily
            d = datetime.strptime(period, '%Y-%m-%d')
            prev = d - timedelta(days=1)
            return prev.strftime('%Y-%m-%d')
    except (ValueError, IndexError, TypeError, AttributeError):
        return period



def calc_score(row):
    """计算商品综合评分（0-100分）"""
    score = 50  # 基础分
    # 转化率加分（越高越好，上限+20）
    conv = row.get('conversion') or 0
    score += min(conv * 5, 20)
    # ROI加分（越高越好，上限+15）
    roi = row.get('overall_roi') or 0
    score += min(roi * 1.5, 15)
    # 退款率扣分（越低越好，上限-20）
    refund = row.get('refund_rate') or 0
    score -= min(refund * 1.5, 20)
    # UV价值加分（越高越好，上限+10）
    uv = row.get('uv_value') or 0
    score += min(uv * 0.5, 10)
    # 搜索占比加分（上限+5）
    search = row.get('search_ratio') or 0
    score += min(search * 5, 5)
    return round(max(0, min(100, score)), 1)

# 预留接口：数据备份（前端暂未调用）

# ==================== 任务看板 API ====================

def _legacy_task_payload(row):
    item = dict(row)
    if item.get('status') == 'in_progress':
        item['status'] = 'doing'
    return item

# ==================== 搜索词效能 API ====================




# 预留接口：异常检测（前端暂未调用）

# ==================== 目标管理 API ====================

def _get_prev_month(period):
    """获取上一个自然月"""
    try:
        parts = period.split('-')
        year, month = int(parts[0]), int(parts[1])
        month -= 1
        if month == 0:
            month = 12
            year -= 1
        return f"{year}-{month:02d}"
    except (ValueError, IndexError, TypeError):
        return None


# 预留接口：商品分层目标进度（前端暂未调用）

# 预留接口：手动设置店铺目标（前端暂未调用）


# ==================== Feature 8: 智能数据导入调度 ====================
# 内存中的调度器状态
_scheduler_lock = threading.Lock()
_scheduler_running = False


def _parse_cron_expr(cron_expr):
    """解析简单 cron 表达式，返回下次运行时间"""
    try:
        parts = cron_expr.strip().lower().split()
        if not parts:
            return None
        now = datetime.now()

        if parts[0] == 'daily':
            # daily HH:MM
            time_str = parts[1] if len(parts) > 1 else '08:00'
            h, m = map(int, time_str.split(':'))
            next_run = now.replace(hour=h, minute=m, second=0, microsecond=0)
            if next_run <= now:
                next_run += timedelta(days=1)
            return next_run

        elif parts[0] == 'weekly':
            # weekly day HH:MM
            day_map = {'mon': 0, 'tue': 1, 'wed': 2, 'thu': 3, 'fri': 4, 'sat': 5, 'sun': 6}
            day_name = parts[1] if len(parts) > 1 else 'mon'
            time_str = parts[2] if len(parts) > 2 else '08:00'
            h, m = map(int, time_str.split(':'))
            target_day = day_map.get(day_name, 0)
            next_run = now.replace(hour=h, minute=m, second=0, microsecond=0)
            days_ahead = (target_day - now.weekday()) % 7
            if days_ahead == 0 and next_run <= now:
                days_ahead = 7
            next_run += timedelta(days=days_ahead)
            return next_run

        elif parts[0] == 'monthly':
            # monthly DD HH:MM
            dom = int(parts[1]) if len(parts) > 1 else 1
            time_str = parts[2] if len(parts) > 2 else '08:00'
            h, m = map(int, time_str.split(':'))
            try:
                next_run = now.replace(day=dom, hour=h, minute=m, second=0, microsecond=0)
            except ValueError:
                # 处理月末日期（如31号在某些月份不存在）
                last_day = _calendar.monthrange(now.year, now.month)[1]
                dom = min(dom, last_day)
                next_run = now.replace(day=dom, hour=h, minute=m, second=0, microsecond=0)
            if next_run <= now:
                if now.month == 12:
                    next_run = next_run.replace(year=now.year + 1, month=1)
                else:
                    next_run = next_run.replace(month=now.month + 1)
            return next_run

    except Exception:
        # cron 表达式解析失败时返回 None，由调用方处理
        pass
    return None


def _cron_to_label(cron_expr):
    """将 cron 表达式转为可读中文标签"""
    try:
        parts = cron_expr.strip().lower().split()
        if parts[0] == 'daily':
            time_str = parts[1] if len(parts) > 1 else '08:00'
            return f"每天 {time_str}"
        elif parts[0] == 'weekly':
            day_names = {'mon': '周一', 'tue': '周二', 'wed': '周三', 'thu': '周四', 'fri': '周五', 'sat': '周六', 'sun': '周日'}
            day_name = day_names.get(parts[1] if len(parts) > 1 else 'mon', '周一')
            time_str = parts[2] if len(parts) > 2 else '08:00'
            return f"每{day_name} {time_str}"
        elif parts[0] == 'monthly':
            dom = parts[1] if len(parts) > 1 else '1'
            time_str = parts[2] if len(parts) > 2 else '08:00'
            return f"每月{dom}号 {time_str}"
    except Exception:
        # cron 表达式描述解析失败时返回原始表达式
        pass
    return cron_expr




