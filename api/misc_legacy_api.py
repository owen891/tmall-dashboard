from datetime import datetime
"""Misc Legacy API - 杂项接口（旧版）

从 data_api.py 拆分出来的最后一批接口，包含：
- 商品字段更新/批量更新
- 市场汇总
- 上传复盘/数据
- 导入进度
- 报告生成
- 批量标签
"""

import io
import os
import tempfile
import threading
import time
import uuid
from api.data_api import DIMENSION_MAP, _aov_expression, _cleanup_upload_paths, _fmt_wan, _get_import_progress, _set_import_progress, _unique_upload_path, _upload_folder, _validate_period_arg, cached_api, get_prev_period

import pandas as pd
from flask import Blueprint, current_app, jsonify, request

from db import get_db, get_shop_id, load_config
from api.api_response import failure, json_object, success
from repos.audit_repo import AuditRepo


misc_legacy_bp = Blueprint('misc_legacy', __name__)


@misc_legacy_bp.route('/api/products/<product_id>/field', methods=['PUT'])  # 已迁移到 misc_legacy_api.py
def update_product_field(product_id):
    """行内快速编辑商品字段"""
    data = json_object(request)
    field = str(data.get('field') or '').strip()
    value = str(data.get('value') or '').strip()

    # 安全设计：字段白名单防止SQL注入，仅允许以下字段通过f-string拼入SQL
    ALLOWED_FIELDS = ('tier', 'style', 'scene', 'manager', 'remark')
    if field not in ALLOWED_FIELDS:
        return failure('VALIDATION_ERROR', f'不允许修改字段「{field}」', status=422)
    if not product_id:
        return failure('VALIDATION_ERROR', '缺少 product_id', status=422)

    with get_db() as conn:
        # 检查商品是否存在
        row = conn.execute('SELECT product_id FROM products WHERE product_id = ?', (product_id,)).fetchone()
        if not row:
            return failure('NOT_FOUND', '商品不存在', status=404)

        # 获取旧值用于日志
        old_row = conn.execute(f'SELECT {field} FROM products WHERE product_id = ?', (product_id,)).fetchone()
        old_value = old_row[0] if old_row else ''

        # 更新字段
        conn.execute(
            f'UPDATE products SET {field} = ?, updated_at = CURRENT_TIMESTAMP WHERE product_id = ?',
            (value, product_id)
        )
        conn.execute(
            'INSERT INTO operation_logs (action, detail, operator) VALUES (?, ?, ?)',
            (f'修改{field}', f'商品 {product_id}: {field}「{old_value}」→「{value}」', 'admin')
        )
        AuditRepo.record(
            'product', product_id, 'update_field', data.get('operator') or 'admin',
            data.get('reason') or f'修改商品{field}', {field: old_value}, {field: value},
            connection=conn,
        )
        conn.commit()

    return jsonify({'success': True, 'field': field, 'value': value})

# ==================== 批量更新 ====================
#

@misc_legacy_bp.route('/api/batch_update', methods=['POST'])  # 已迁移到 misc_legacy_api.py
def batch_update():
    data = json_object(request)
    field = str(data.get('field') or '').strip()
    value = str(data.get('value') or '').strip()
    ids = [str(item).strip() for item in (data.get('product_ids') or []) if str(item).strip()] if isinstance(data.get('product_ids'), list) else []
    if field not in ('tier', 'style') or not value or not ids:
        return failure('VALIDATION_ERROR', '商品字段、批量值和商品ID列表不能为空', status=422)
    with get_db() as conn:
        placeholders = ','.join(['?'] * len(ids))
        conn.execute(f"UPDATE products SET {field} = ?, updated_at = CURRENT_TIMESTAMP WHERE product_id IN ({placeholders})", [value] + ids)
        conn.commit()
        # 记录操作日志
        conn.execute(
            'INSERT INTO operation_logs (action, detail, operator) VALUES (?, ?, ?)',
            (f'批量修改{field}', f'将 {len(ids)} 件商品的{field}修改为「{value}」', 'admin')
        )
        conn.commit()
    return jsonify({'success': True, 'updated': len(ids)})

# ==================== 周期对比分析 API ====================

#

@misc_legacy_bp.route('/api/market/summary', methods=['GET'])  # 已迁移到 misc_legacy_api.py
@cached_api('get_market_summary', ttl=30)
def get_market_summary():
    """获取市场分析摘要"""
    category = request.args.get('category', '')
    report_id = request.args.get('report_id', '')

    with get_db() as conn:
        query = 'SELECT * FROM market_analysis WHERE 1=1'
        params = []
        if category:
            query += ' AND category_path = ?'
            params.append(category)
        if report_id:
            query += ' AND id = ?'
            params.append(report_id)
        query += ' ORDER BY analysis_date DESC LIMIT 1'

        row = conn.execute(query, params).fetchone()

    if not row:
        return jsonify({'meta': None, 'summary': {}, 'keywords_count': 0, 'empty': True})

    data = dict(row)
    return jsonify({
        'meta': {
            'category_path': data['category_path'],
            'category_short': data['category_short'],
            'period_30d': data['period_30d'],
            'period_7d': data['period_7d'],
            'period_trend': data['period_trend'],
            'total_keywords': data['total_keywords'],
            'avg_ctr_7d': data['avg_ctr_7d'],
            'avg_cvr_30d': data['avg_cvr_30d'],
            'top5_keywords': json.loads(data['top5_keywords']) if data['top5_keywords'] else [],
        },
        'summary': json.loads(data['summary_data']) if data['summary_data'] else {},
        'keywords_count': data['total_keywords'],
    })


#

@misc_legacy_bp.route('/api/upload/reviews', methods=['POST'])  # 已迁移到 misc_legacy_api.py
def upload_reviews():
    """上传评价数据文件"""
    if 'file' not in request.files:
        return failure('VALIDATION_ERROR', '未上传文件', status=422)

    file = request.files['file']
    if not file.filename.lower().endswith(('.xlsx', '.xls', '.csv')):
        return failure('UNSUPPORTED_FILE_TYPE', '仅支持 Excel 或 CSV 文件', {'extensions': ['.xlsx', '.xls', '.csv']}, status=422)

    filepath = None
    try:
        upload_root = _upload_folder()
        os.makedirs(upload_root, exist_ok=True)
        filename, filepath = _unique_upload_path(file.filename)
        file.save(filepath)

        # 解析并导入
        from scripts.import_data import import_reviews_from_file
        count = import_reviews_from_file(filepath)
        return jsonify({'success': True, 'count': count, 'filename': filename})
    except Exception:
        current_app.logger.exception('Review upload failed')
        return failure('IMPORT_FAILED', '评价文件解析或导入失败，请检查文件内容', status=500)
    finally:
        if filepath:
            _cleanup_upload_paths([filepath])

#

@misc_legacy_bp.route('/api/upload/data', methods=['POST'])  # 已迁移到 misc_legacy_api.py
def upload_business_data():
    """上传核心业务数据Excel文件"""
    if 'file' not in request.files:
        return failure('VALIDATION_ERROR', '未上传文件', status=422)

    file = request.files['file']
    suffix = os.path.splitext(file.filename or '')[1].lower()
    if suffix not in {'.xlsx', '.xls', '.csv', '.zip'}:
        return failure('UNSUPPORTED_FILE_TYPE', '仅支持 .xlsx、.xls、.csv 和 .zip 文件', {'extensions': ['.xlsx', '.xls', '.csv', '.zip']}, status=422)

    import tempfile
    from scripts.import_data import import_excel_file

    # 保存到临时文件
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        file.save(tmp.name)
        tmp_path = tmp.name

    task_id = str(uuid.uuid4())[:8]
    filename = file.filename
    request_app = current_app._get_current_object()
    request_shop_id = get_shop_id()

    def _do_import(task_id, file_path, filename, app, shop_id):
        """后台线程执行导入，更新进度"""
        try:
            _set_import_progress(task_id, {
                'status': 'processing', 'progress': 10,
                'message': '正在解析文件...', 'started_at': time.time()
            })

            # Recreate the request scope captured at submission time so the
            # canonical importer uses the same app config, database, and shop.
            with app.app_context(), app.test_request_context(
                '/api/upload/data', query_string={'shop_id': shop_id}
            ):
                result = import_excel_file(file_path)

            _set_import_progress(task_id, {
                'status': 'completed', 'progress': 100,
                'message': f'导入完成，共 {result.get("total_rows", 0)} 行数据',
                'result': result, 'finished_at': time.time(),
            })
        except Exception as error:
            app.logger.exception('Business data import failed: %s', task_id)
            _set_import_progress(task_id, {
                'status': 'error', 'progress': 0,
                'message': '导入失败，请检查文件格式和数据内容',
                'error': str(error), 'finished_at': time.time(),
            })
        finally:
            try:
                os.unlink(file_path)
            except Exception as _e:
                current_app.logger.warning(f'清理临时文件失败: {_e}')

    threading.Thread(
        target=_do_import,
        args=(task_id, tmp_path, filename, request_app, request_shop_id),
        daemon=True,
    ).start()
    return jsonify({'success': True, 'task_id': task_id, 'message': '导入任务已提交'})


#

@misc_legacy_bp.route('/api/import_progress/<task_id>', methods=['GET'])  # 已迁移到 misc_legacy_api.py
def get_import_progress(task_id):
    """获取导入任务进度"""
    progress = _get_import_progress(task_id)
    if progress is None:
        return failure('NOT_FOUND', '导入任务不存在或已过期', {'task_id': task_id}, status=404)
    return jsonify(progress)

#

@misc_legacy_bp.route('/api/report', methods=['GET'])  # 已迁移到 misc_legacy_api.py
def generate_report():
    """生成文本格式的数据摘要报告"""
    dim = request.args.get('dim', 'monthly')
    period = request.args.get('period', '')
    if not period:
        return jsonify({'error': 'period required'}), 400

    dim_cfg = DIMENSION_MAP.get(dim)
    if not dim_cfg:
        return failure('VALIDATION_ERROR', 'invalid dimension', {'dim': dim}, status=422)
    invalid = _validate_period_arg(dim, period)
    if invalid:
        return invalid
    table = dim_cfg['table']
    date_col = dim_cfg['date_col']
    visitors_col = dim_cfg['visitors_col']

    with get_db() as conn:
        has_period_rows = conn.execute(
            f'SELECT 1 FROM {table} WHERE {date_col} = ? LIMIT 1',
            (period,),
        ).fetchone()
        if not has_period_rows:
            return jsonify({'error': 'no data for period'}), 404

        # 1. KPI汇总
        kpi_row = conn.execute(f'''
            SELECT
                COALESCE(SUM(payment_amount),0) as gmv,
                COALESCE(SUM(refund_amount),0) as refund_amount,
                COALESCE(SUM(payment_amount),0) - COALESCE(SUM(refund_amount),0) as net_sales,
                COALESCE(SUM({visitors_col}),0) as visitors,
                {_aov_expression(dim)} as aov,
                CASE WHEN SUM(payment_amount) > 0 THEN SUM(refund_amount) * 1.0 / SUM(payment_amount) ELSE 0 END as refund_rate,
                COALESCE(SUM(ad_spend),0) as ad_spend,
                CASE WHEN SUM(ad_spend) > 0 THEN SUM(payment_amount) * 1.0 / SUM(ad_spend) ELSE 0 END as roi,
                AVG(payment_conversion) as conversion
            FROM {table} WHERE {date_col} = ?
        ''', (period,)).fetchone()

        if not kpi_row:
            return jsonify({'error': 'no data for period'}), 404

        kpi = dict(kpi_row)
        gmv = kpi['gmv']
        net_sales = kpi['net_sales']
        visitors = kpi['visitors']
        conv_rate = kpi['conversion'] * 100 if kpi['conversion'] else 0
        ad_cost = kpi['ad_spend']
        roi = kpi['roi']
        refund_rate = kpi['refund_rate'] * 100 if kpi['refund_rate'] else 0
        aov = kpi['aov']
        aov_text = f'¥{aov:.1f}' if aov is not None else '--'

        # 2. Top5商品（按销售额）
        top5_rows = conn.execute(f'''
            SELECT p.title, d.payment_amount, d.{visitors_col} as visitors, d.payment_conversion, d.ad_spend, d.ad_roi
            FROM products p
            JOIN {table} d ON p.product_id = d.product_id AND d.{date_col} = ?
            WHERE p.status = 'active'
            ORDER BY d.payment_amount DESC
            LIMIT 5
        ''', (period,)).fetchall()

        top5_text = ''
        for i, r in enumerate(top5_rows, 1):
            rd = dict(r)
            top5_text += f"  {i}. {rd['title'][:30]}\n"
            visitors = rd.get('visitors') or 0
            conversion = rd.get('payment_conversion') or 0
            top5_text += f"     销售额: {_fmt_wan(rd['payment_amount'])}  访客: {visitors:,}  转化率: {conversion * 100:.1f}%\n"

        if not top5_text:
            top5_text = '  暂无商品数据\n'

        # 3. 异常指标
        alerts_text = ''
        config = load_config()
        anomaly_decline = config.get('thresholds', {}).get('anomaly_decline', 0.20)

        # 查询上期数据做环比
        prev_period = get_prev_period(period, dim)
        prev_row = None
        if prev_period != period:
            prev_row = conn.execute(f'''
                SELECT
                    COALESCE(SUM(payment_amount),0) as gmv,
                    COALESCE(SUM(refund_amount),0) as refund_amount,
                    COALESCE(SUM(payment_amount),0) - COALESCE(SUM(refund_amount),0) as net_sales,
                    COALESCE(SUM({visitors_col}),0) as visitors,
                    CASE WHEN SUM(ad_spend) > 0 THEN SUM(payment_amount) * 1.0 / SUM(ad_spend) ELSE 0 END as roi,
                    AVG(payment_conversion) as conversion
                FROM {table} WHERE {date_col} = ?
            ''', (prev_period,)).fetchone()

        if prev_row:
            prev = dict(prev_row)
            metric_labels = {
                'gmv': '总销售额', 'net_sales': '净销售额',
                'visitors': '总访客', 'conversion': '转化率', 'roi': 'ROI'
            }
            for key, label in metric_labels.items():
                curr_val = kpi.get(key, 0) or 0
                prev_val = prev.get(key, 0) or 0
                if prev_val > 0:
                    change_pct = (curr_val - prev_val) / prev_val * 100
                    if change_pct < 0 and abs(change_pct) > anomaly_decline * 100:
                        alerts_text += f"  - {label}: 环比下降 {abs(change_pct):.1f}% (上期: {_fmt_wan(prev_val)}, 本期: {_fmt_wan(curr_val)})\n"

        # 退款率异常
        if refund_rate > 15:
            alerts_text += f"  - 退款率偏高: {refund_rate:.1f}%\n"

        if not alerts_text:
            alerts_text = '  各项指标正常\n'

        # 4. 生成报告文本
        report = f"""📊 天猫数据报告
📅 报告周期：{period}（{dim}）
⏰ 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}

📈 核心指标
- 总销售额：{_fmt_wan(gmv)}
- 净销售额：{_fmt_wan(net_sales)}
- 总访客：{visitors:,}
- 整体转化率：{conv_rate:.1f}%
- 推广花费：{_fmt_wan(ad_cost)}
- 综合ROI：{roi:.2f}
- 退款率：{refund_rate:.1f}%
- 客单价：{aov_text}

🏆 销售TOP5
{top5_text}
⚠️ 异常指标
{alerts_text}"""

    return jsonify({'report': report})


# ==================== Feature 4: 多周期趋势叠加 ====================
#

@misc_legacy_bp.route('/api/batch_tags', methods=['POST'])  # 已迁移到 misc_legacy_api.py
def batch_add_tags():
    """批量添加商品标签"""
    data = json_object(request)
    product_ids = data.get('product_ids', [])
    tag = str(data.get('tag') or '').strip()

    if not isinstance(product_ids, list) or not product_ids or not tag:
        return failure('VALIDATION_ERROR', '商品ID列表和标签不能为空', status=422)

    product_ids = list(dict.fromkeys(str(pid).strip() for pid in product_ids if str(pid).strip()))
    if not product_ids:
        return failure('VALIDATION_ERROR', '商品ID列表和标签不能为空', status=422)

    with get_db() as conn:
        placeholders = ','.join(['?'] * len(product_ids))
        existing = {
            row['product_id'] for row in conn.execute(
                f'SELECT product_id FROM products WHERE product_id IN ({placeholders})', product_ids
            ).fetchall()
        }
        count = 0
        for pid in existing:
            cursor = conn.execute(
                'INSERT OR IGNORE INTO product_tags (product_id, tag) VALUES (?, ?)', (pid, tag)
            )
            count += int(cursor.rowcount > 0)
        conn.commit()
    missing = len(set(product_ids) - existing)
    duplicate = len(existing) - count
    details = []
    if missing:
        details.append(f'{missing} 件商品不存在')
    if duplicate:
        details.append(f'{duplicate} 件商品已有该标签')
    msg = f'已为 {count} 件商品添加标签 "{tag}"'
    if details:
        msg += '，' + '，'.join(details)
    return jsonify({
        'success': True,
        'message': msg,
        'added': count,
        'missing': missing,
        'duplicates': duplicate,
    })


#

@misc_legacy_bp.route('/api/batch_tags', methods=['DELETE'])  # 已迁移到 misc_legacy_api.py
def batch_remove_tags():
    """批量移除商品标签"""
    data = json_object(request)
    product_ids = data.get('product_ids', [])
    tag = str(data.get('tag') or '').strip()

    if not isinstance(product_ids, list) or not product_ids or not tag:
        return failure('VALIDATION_ERROR', '商品ID列表和标签不能为空', status=422)
    product_ids = list(dict.fromkeys(str(pid).strip() for pid in product_ids if str(pid).strip()))
    if not product_ids:
        return failure('VALIDATION_ERROR', '商品ID列表和标签不能为空', status=422)

    with get_db() as conn:
        placeholders = ','.join(['?'] * len(product_ids))
        cursor = conn.execute(
            f'DELETE FROM product_tags WHERE product_id IN ({placeholders}) AND tag = ?',
            product_ids + [tag]
        )
        deleted_count = cursor.rowcount
        conn.commit()
    return jsonify({'success': True, 'message': f'已移除标签 "{tag}"', 'deleted': deleted_count})



# ==================== 新老客分析 API ====================

#

