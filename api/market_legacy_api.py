from datetime import date
"""Market Legacy API - 市场分析相关接口（旧版）

从 data_api.py 拆分出来的独立模块，包含：
- 关键词上传/查询
- 市场数据上传
- 市场关键词/需求统计/排名/直方图/机会/报告
- 行业基准
"""

import io
import os
from api.data_api import DIMENSION_MAP, _cleanup_upload_paths, _parse_keyword_date, _parse_keyword_number, _unique_upload_path, _upload_folder, _validate_period_arg

import pandas as pd
from flask import Blueprint, current_app, g, jsonify, request

from db import get_db
from api.api_response import evidence_level_for, failure, limitations_for, success


market_legacy_bp = Blueprint('market_legacy', __name__)


def _request_cache_key(prefix):
    params = sorted(request.args.items())
    param_str = "&".join(f"{k}={v}" for k, v in params)
    from flask import g
    shop_id = getattr(getattr(g, 'shop_id', None), '__str__', lambda: 'default')()
    return f"{prefix}:{request.path}:{shop_id}:{param_str}"


def cached_api(prefix, ttl=60):
    from utils.cache import cache as _ttl_cache
    def decorator(f):
        def wrapped(*args, **kwargs):
            key = _request_cache_key(prefix)
            cached = _ttl_cache.get(key)
            if cached is not None:
                return jsonify(cached)
            result = f(*args, **kwargs)
            try:
                if hasattr(result, 'status_code') and result.status_code == 200 and hasattr(result, 'get_json'):
                    data = result.get_json()
                    if data is not None:
                        _ttl_cache.set(key, data, ttl)
            except Exception:
                pass
            return result
        wrapped.__name__ = getattr(f, '__name__', 'wrapped')
        wrapped.__doc__ = getattr(f, '__doc__', '')
        return wrapped
    return decorator


@market_legacy_bp.route('/api/upload/keywords', methods=['POST'])
def upload_keywords():
    """上传搜索词数据Excel"""
    if 'file' not in request.files:
        return failure('VALIDATION_ERROR', '未上传文件', status=422)
    file = request.files['file']
    if not file.filename.lower().endswith(('.xlsx', '.xls')):
        return failure('UNSUPPORTED_FILE_TYPE', '仅支持 Excel 文件', {'extensions': ['.xlsx', '.xls']}, status=422)
    
    import pandas as pd
    from db import init_db, get_db
    
    init_db()
    
    try:
        df = pd.read_excel(file)
        if df.empty or len(df.columns) == 0:
            return failure('INVALID_DATA', '文件没有可导入的数据行', status=422)
        df.columns = [str(c).strip().lower() for c in df.columns]
        
        # Column mapping (生意参谋 common column names)
        col_map = {
            '搜索词': 'keyword', '关键词': 'keyword', 'keyword': 'keyword',
            '日期': 'date', 'date': 'date', '统计日期': 'date',
            '搜索人气': 'popularity', '人气': 'popularity', 'popularity': 'popularity',
            '展现量': 'impressions', '展现': 'impressions', 'impressions': 'impressions',
            '点击量': 'clicks', '点击': 'clicks', 'clicks': 'clicks',
            '点击率': 'ctr', 'ctr': 'ctr',
            '花费': 'cost', '消耗': 'cost', 'cost': 'cost',
            '支付金额': 'gmv', '成交金额': 'gmv', 'gmv': 'gmv',
            '转化率': 'cvr', '支付转化率': 'cvr', 'cvr': 'cvr',
            '投入产出比': 'roi', 'roi': 'roi', '投产比': 'roi',
            '点击单价': 'cpc', 'cpc': 'cpc',
            '支付买家数': 'conversion', '成交笔数': 'conversion', 'conversion': 'conversion',
        }
        
        renamed = {}
        for cn, en in col_map.items():
            if cn in df.columns:
                renamed[cn] = en
        
        if 'keyword' not in renamed.values():
            # Try to find keyword column by common patterns
            for c in df.columns:
                if '词' in c or 'keyword' in c:
                    renamed[c] = 'keyword'
                    break
        
        if 'keyword' not in renamed.values():
            return failure('MISSING_REQUIRED_FIELD', '未找到搜索词列，请确认表头包含"搜索词"或"关键词"', status=422)
        if 'date' not in renamed.values():
            return failure('MISSING_REQUIRED_FIELD', '未找到日期列，关键词文件必须包含「日期」或「统计日期」', status=422)
        if len(set(renamed.values())) != len(renamed.values()):
            return failure('VALIDATION_ERROR', '文件包含重复的关键词字段映射', status=422)

        df = df.rename(columns=renamed)

        try:
            df['date'] = df['date'].map(_parse_keyword_date)
        except ValueError as error:
            return failure('INVALID_DATA', str(error), status=422)

        # Validate every supplied numeric cell; never coerce invalid values to zero.
        numeric_columns = [
            'popularity', 'impressions', 'clicks', 'ctr', 'cost', 'gmv',
            'cvr', 'roi', 'cpc', 'conversion',
        ]
        try:
            for numeric_column in numeric_columns:
                if numeric_column in df.columns:
                    df[numeric_column] = [
                        _parse_keyword_number(value, numeric_column, index + 2)
                        for index, value in enumerate(df[numeric_column])
                    ]
        except ValueError as error:
            return failure('INVALID_DATA', str(error), status=422)

        date_str = str(df['date'].iloc[0]) if not df.empty else None
        if not date_str:
            return failure('INVALID_DATA', '文件没有可导入的数据行', status=422)

        # Calculate derived metrics
        if 'ctr' not in df.columns and 'clicks' in df.columns and 'impressions' in df.columns:
            df['ctr'] = df.apply(lambda r: r['clicks'] / r['impressions'] if r.get('impressions', 0) > 0 else 0, axis=1)
        if 'cpc' not in df.columns and 'cost' in df.columns and 'clicks' in df.columns:
            df['cpc'] = df.apply(lambda r: r['cost'] / r['clicks'] if r.get('clicks', 0) > 0 else 0, axis=1)
        if 'roi' not in df.columns and 'gmv' in df.columns and 'cost' in df.columns:
            df['roi'] = df.apply(lambda r: r['gmv'] / r['cost'] if r.get('cost', 0) > 0 else 0, axis=1)
        if 'cvr' not in df.columns and 'conversion' in df.columns and 'clicks' in df.columns:
            df['cvr'] = df.apply(lambda r: r['conversion'] / r['clicks'] if r.get('clicks', 0) > 0 else 0, axis=1)

        # Calculate efficacy (词效能)
        with get_db() as conn:
            avg_ctr = df['ctr'].mean() if 'ctr' in df.columns else 0
            avg_cvr = df['cvr'].mean() if 'cvr' in df.columns else 0
            
            count = 0
            for _, row in df.iterrows():
                kw = str(row.get('keyword', '')).strip()
                if not kw or kw.lower() in {'nan', 'none', 'null', '--'}:
                    continue
                
                ctr_val = float(row.get('ctr', 0) or 0)
                cvr_val = float(row.get('cvr', 0) or 0)
                
                # Efficacy = (CTR / avg_CTR) * (CVR / avg_CVR)
                if avg_ctr > 0 and avg_cvr > 0:
                    efficacy = (ctr_val / avg_ctr) * (cvr_val / avg_cvr)
                else:
                    efficacy = 0
                
                # Category
                if efficacy >= 1.2:
                    category = '蓝海词'
                elif efficacy >= 0.8:
                    category = '流量词'
                else:
                    category = '废词'
                
                conn.execute('''
                    INSERT INTO keyword_metrics
                    (date, keyword, popularity, impressions, clicks, ctr, cost, gmv, cvr, roi, cpc, conversion, efficacy, category)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(date, keyword) DO UPDATE SET
                        popularity=excluded.popularity, impressions=excluded.impressions,
                        clicks=excluded.clicks, ctr=excluded.ctr, cost=excluded.cost,
                        gmv=excluded.gmv, cvr=excluded.cvr, roi=excluded.roi,
                        cpc=excluded.cpc, conversion=excluded.conversion,
                        efficacy=excluded.efficacy, category=excluded.category
                ''', (
                    str(row.get('date')),
                    kw,
                    int(row.get('popularity', 0) or 0),
                    int(row.get('impressions', 0) or 0),
                    int(row.get('clicks', 0) or 0),
                    float(ctr_val),
                    float(row.get('cost', 0) or 0),
                    float(row.get('gmv', 0) or 0),
                    float(cvr_val),
                    float(row.get('roi', 0) or 0),
                    float(row.get('cpc', 0) or 0),
                    int(row.get('conversion', 0) or 0),
                    float(efficacy),
                    category
                ))
                count += 1
            
            conn.commit()
        
        return jsonify({'success': True, 'rows_imported': count, 'date': date_str})
    except (ValueError, TypeError, ImportError) as error:
        current_app.logger.warning('Keyword upload validation failed: %s', error)
        return failure('INVALID_DATA', '文件格式或数据无效，请检查表头、日期和数值', status=422)
    except Exception:
        current_app.logger.exception('Keyword upload failed')
        return failure('IMPORT_FAILED', '文件解析或导入失败，请检查表格格式和数据内容', status=500)

@market_legacy_bp.route('/api/keywords', methods=['GET'])
def get_keywords():
    """搜索词效能列表"""
    date = request.args.get('date', '')
    category = request.args.get('category', '')
    search = request.args.get('search', '')
    sort = request.args.get('sort', 'efficacy')
    order = request.args.get('order', 'desc')
    try:
        raw_page = request.args.get('page', '1')
        raw_per_page = request.args.get('per_page', '50')
        page = int(raw_page)
        per_page = int(raw_per_page)
    except (TypeError, ValueError):
        return failure('VALIDATION_ERROR', 'page 和 per_page 必须是正整数', status=422)
    if page < 1 or per_page < 1 or per_page > 200:
        return failure('VALIDATION_ERROR', 'page 和 per_page 必须是正整数，per_page 最大为 200', status=422)
    
    with get_db() as conn:
        # Get available dates
        dates = [r[0] for r in conn.execute('SELECT DISTINCT date FROM keyword_metrics ORDER BY date DESC').fetchall()]
        if not date and dates:
            date = dates[0]
        
        where_clauses = ['1=1']
        params = []
        if date:
            where_clauses.append('date = ?')
            params.append(date)
        if category:
            where_clauses.append('category = ?')
            params.append(category)
        if search:
            where_clauses.append('keyword LIKE ?')
            params.append(f'%{search}%')
        
        where_sql = ' AND '.join(where_clauses)
        
        # Count
        total = conn.execute(f'SELECT COUNT(*) FROM keyword_metrics WHERE {where_sql}', params).fetchone()[0]
        
        # Sort whitelist
        sort_whitelist = ['efficacy', 'popularity', 'impressions', 'clicks', 'ctr', 'cost', 'gmv', 'roi', 'cvr', 'cpc', 'keyword']
        if sort not in sort_whitelist:
            sort = 'efficacy'
        order_sql = 'DESC' if order.lower() == 'desc' else 'ASC'
        
        # Query
        offset = (page - 1) * per_page
        rows = [dict(r) for r in conn.execute(f'''
            SELECT * FROM keyword_metrics WHERE {where_sql}
            ORDER BY {sort} {order_sql}
            LIMIT ? OFFSET ?
        ''', params + [per_page, offset]).fetchall()]
        
        # Summary stats
        summary = {}
        if date:
            s = conn.execute('''
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN category='蓝海词' THEN 1 ELSE 0 END) as blue_ocean,
                    SUM(CASE WHEN category='流量词' THEN 1 ELSE 0 END) as traffic,
                    SUM(CASE WHEN category='废词' THEN 1 ELSE 0 END) as dead,
                    AVG(ctr) as avg_ctr,
                    AVG(cvr) as avg_cvr,
                    AVG(roi) as avg_roi,
                    SUM(cost) as total_cost,
                    SUM(gmv) as total_gmv
                FROM keyword_metrics WHERE date = ?
            ''', (date,)).fetchone()
            if s:
                summary = dict(s)
    
    return jsonify({
        'items': rows,
        'total': total,
        'page': page,
        'per_page': per_page,
        'dates': dates,
        'date': date,
        'summary': summary,
        'availability': 'available' if total else 'no-data',
    })

# ==================== 市场分析 API ====================

@market_legacy_bp.route('/api/upload/market', methods=['POST'])
def upload_market():
    """上传市场分析数据文件"""
    files = request.files.getlist('files')
    if not files:
        return failure('VALIDATION_ERROR', '未上传文件', status=422)

    upload_root = _upload_folder()
    os.makedirs(upload_root, exist_ok=True)
    saved_paths = []
    try:
        for file in files:
            if not file.filename:
                continue
            filename, filepath = _unique_upload_path(file.filename)
            file.save(filepath)
            saved_paths.append(filepath)

        if len(saved_paths) < 3:
            return failure('VALIDATION_ERROR', '需要至少 3 个文件（30 天搜索、7 天搜索、趋势分析）', status=422)

        from scripts.import_market import identify_market_files, import_market_data
        identified = identify_market_files(saved_paths)

        if not identified['f30'] or not identified['f7'] or not identified['ft']:
            return failure(
                'UNRECOGNIZED_FILES',
                '无法识别文件类型，请确保文件名包含"搜索排行"和"趋势分析"',
                {'identified': identified},
                status=422,
            )

        count = import_market_data(identified['f30'], identified['f7'], identified['ft'])
        return jsonify({
            'success': True,
            'count': count,
            'message': '市场分析数据导入成功，共处理 %d 个关键词' % count
        })
    except Exception:
        current_app.logger.exception('Market data upload failed')
        return failure('IMPORT_FAILED', '市场数据解析或导入失败，请检查文件内容', status=500)
    finally:
        _cleanup_upload_paths(saved_paths)

@market_legacy_bp.route('/api/market/keywords', methods=['GET'])
@cached_api('get_market_keywords', ttl=30)
def get_market_keywords():
    """获取关键词分析数据"""
    category = request.args.get('category', '')
    limit = max(1, min(request.args.get('limit', 50, type=int) or 50, 200))
    opportunity = request.args.get('opportunity', '')

    with get_db() as conn:
        query = 'SELECT * FROM market_analysis WHERE 1=1'
        params = []
        if category:
            query += ' AND category_path = ?'
            params.append(category)
        query += ' ORDER BY analysis_date DESC LIMIT 1'

        row = conn.execute(query, params).fetchone()

    if not row:
        return jsonify({'error': 'no data'}), 404

    data = dict(row)
    keywords = json.loads(data['keywords_data']) if data['keywords_data'] else []

    # 按机会类别过滤
    if opportunity:
        keywords = [kw for kw in keywords if kw.get('opportunity_category') == opportunity]

    total = len(keywords)
    keywords = keywords[:limit]

    return jsonify({
        'keywords': keywords,
        'total': total,
    })

@market_legacy_bp.route('/api/market/need_stats', methods=['GET'])
def get_market_need_stats():
    """获取8维度需求统计"""
    category = request.args.get('category', '')

    with get_db() as conn:
        query = 'SELECT * FROM market_analysis WHERE 1=1'
        params = []
        if category:
            query += ' AND category_path = ?'
            params.append(category)
        query += ' ORDER BY analysis_date DESC LIMIT 1'

        row = conn.execute(query, params).fetchone()

    if not row:
        return jsonify({'error': 'no data'}), 404

    data = dict(row)
    return jsonify({
        'need_stats': json.loads(data['need_stats_data']) if data['need_stats_data'] else {},
        'dimension_details': json.loads(data['dimension_details']) if data['dimension_details'] else {},
    })

@market_legacy_bp.route('/api/market/rankings', methods=['GET'])
@cached_api('get_market_rankings', ttl=30)
def get_market_rankings():
    """获取商品排名数据"""
    category = request.args.get('category', '')
    ranking_type = request.args.get('ranking_type', '')

    with get_db() as conn:
        query = 'SELECT * FROM market_analysis WHERE 1=1'
        params = []
        if category:
            query += ' AND category_path = ?'
            params.append(category)
        query += ' ORDER BY analysis_date DESC LIMIT 1'

        row = conn.execute(query, params).fetchone()

    if not row:
        return jsonify({'error': 'no data'}), 404

    data = dict(row)
    rankings = json.loads(data['rankings_data']) if data['rankings_data'] else {}

    # 按排名类型过滤
    if ranking_type and ranking_type in rankings:
        rankings = {ranking_type: rankings[ranking_type]}

    return jsonify({
        'rankings': rankings,
    })

@market_legacy_bp.route('/api/market/histograms', methods=['GET'])
def get_market_histograms():
    """获取直方图数据"""
    category = request.args.get('category', '')

    with get_db() as conn:
        query = 'SELECT * FROM market_analysis WHERE 1=1'
        params = []
        if category:
            query += ' AND category_path = ?'
            params.append(category)
        query += ' ORDER BY analysis_date DESC LIMIT 1'

        row = conn.execute(query, params).fetchone()

    if not row:
        return jsonify({'error': 'no data'}), 404

    data = dict(row)
    return jsonify({
        'histograms': json.loads(data['histograms_data']) if data['histograms_data'] else {},
    })

@market_legacy_bp.route('/api/market/opportunities', methods=['GET'])
def get_market_opportunities():
    """获取关键词机会（跨Skill联动）"""
    analysis_date = request.args.get('analysis_date', '')

    with get_db() as conn:

        if analysis_date:
            query = '''
                SELECT * FROM market_keyword_opportunities
                WHERE analysis_date = ?
                  AND opportunity_category IN ('供给不足蓝海词', '小众高意向蓝海词')
                ORDER BY opportunity_score DESC
            '''
            params = [analysis_date]
        else:
            query = '''
                SELECT * FROM market_keyword_opportunities
                WHERE analysis_date = (
                    SELECT MAX(analysis_date) FROM market_keyword_opportunities
                )
                  AND opportunity_category IN ('供给不足蓝海词', '小众高意向蓝海词')
                ORDER BY opportunity_score DESC
            '''
            params = []

        rows = [dict(r) for r in conn.execute(query, params).fetchall()]

    # 解析 need_tags JSON
    for row in rows:
        if row.get('need_tags'):
            try:
                row['need_tags'] = json.loads(row['need_tags'])
            except (json.JSONDecodeError, TypeError):
                row['need_tags'] = []

    return jsonify({
        'opportunities': rows,
    })

@market_legacy_bp.route('/api/market/reports', methods=['GET'])
def get_market_reports():
    """获取所有市场分析报告列表"""
    with get_db() as conn:
        rows = [dict(r) for r in conn.execute('''
            SELECT id, analysis_date, category_path, total_keywords, created_at
            FROM market_analysis
            ORDER BY analysis_date DESC
        ''').fetchall()]
    return jsonify({
        'reports': rows,
    })

@market_legacy_bp.route('/api/industry_benchmark', methods=['GET'])
@cached_api('get_industry_benchmark', ttl=120)
def get_industry_benchmark():
    """Return conditional benchmark evidence without inventing zero values."""
    dim = request.args.get('dim', 'monthly')
    period = request.args.get('period', '')
    dim_cfg = DIMENSION_MAP.get(dim)
    if not dim_cfg:
        return failure('VALIDATION_ERROR', 'invalid dimension', {'dim': dim}, status=422)
    invalid = _validate_period_arg(dim, period)
    if invalid:
        return invalid
    table = dim_cfg['table']
    date_col = dim_cfg['date_col']
    shop_ctr_expr = 'click_rate' if dim == 'monthly' else 'search_click_rate'
    industry_ctr_expr = 'industry_ctr'

    with get_db() as conn:
        table_columns = {row['name'] for row in conn.execute(f'PRAGMA table_info("{table}")')}
        shop_available = shop_ctr_expr in table_columns
        industry_available = industry_ctr_expr in table_columns
        shop_sql = f'NULLIF({shop_ctr_expr}, 0)' if shop_available else 'NULL'
        industry_sql = f'NULLIF({industry_ctr_expr}, 0)' if industry_available else 'NULL'
        row = conn.execute(f'''
            SELECT COUNT(*) AS row_count,
                   AVG({industry_sql}) AS industry_ctr,
                   AVG({shop_sql}) AS shop_ctr
            FROM {table} WHERE {date_col} = ?
        ''', (period,)).fetchone()
        row_count = int(row['row_count'] or 0) if row else 0
        shop_ctr = row['shop_ctr'] if row else None
        industry_ctr = row['industry_ctr'] if row else None
        missing_inputs = ['industry_benchmark'] if row_count == 0 else []
        if row_count and (not shop_available or shop_ctr is None):
            missing_inputs.append('shop_ctr')
        if row_count and (not industry_available or industry_ctr is None):
            missing_inputs.append('industry_ctr')
        gap = shop_ctr - industry_ctr if not missing_inputs else None
        gap_pct = gap / industry_ctr * 100 if gap is not None and industry_ctr else None
        trend_rows = conn.execute(f'''
            SELECT {date_col} AS period,
                   AVG({shop_sql}) AS shop_ctr,
                   AVG({industry_sql}) AS industry_ctr
            FROM {table} WHERE {date_col} <= ?
            GROUP BY {date_col} ORDER BY {date_col} DESC LIMIT 6
        ''', (period,)).fetchall()
        trend = [
            {'period': item['period'], 'shop_ctr': item['shop_ctr'], 'industry_ctr': item['industry_ctr']}
            for item in reversed(trend_rows)
            if item['shop_ctr'] is not None and item['industry_ctr'] is not None
        ]

    availability = 'no-data' if row_count == 0 else 'available' if not missing_inputs else 'missing-fields'
    return success(
        {
            'shop_ctr': round(shop_ctr, 6) if shop_ctr is not None else None,
            'industry_ctr': round(industry_ctr, 6) if industry_ctr is not None else None,
            'gap': round(gap, 6) if gap is not None else None,
            'gap_pct': round(gap_pct, 2) if gap_pct is not None else None,
            'trend': trend,
        },
        availability=availability,
        capabilities={'can_view': availability == 'available'},
        filters={'dim': dim, 'period': period},
        missing_inputs=missing_inputs,
        limitations=limitations_for(availability, missing_inputs=missing_inputs),
        freshness={'period': period, 'latest_period': trend[-1]['period'] if trend else None},
        evidence=[{'source': table, 'row_count': row_count}],
        evidence_level=evidence_level_for(availability, missing_inputs=missing_inputs),
    )


# ==================== 商品画像标签 API ====================

