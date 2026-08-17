import sys
import os
import json
import glob
import shutil
import io
from html.parser import HTMLParser
from zipfile import ZipFile
from datetime import datetime
import pandas as pd
import sqlite3
import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db import get_connection, get_db_path, init_db
from scripts.utils import clean_percentage, clean_number, clean_int, clean_month, parse_date_range, is_valid_row, classify_action
from services.source_resolution_service import record_daily_observation
from services.import_service import import_service


def _legacy_optional(cleaner, value):
    """Keep legacy blank cells missing instead of manufacturing zero observations."""
    if value is None or pd.isna(value) or str(value).strip() in {'', '-', '--', 'nan', 'None'}:
        return None
    return cleaner(value)

# 使用绝对路径
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMPORT_LOG = os.path.join(PROJECT_ROOT, 'data/import_log.json')

def log_import(filename, status, rows=0, details=''):
    os.makedirs(os.path.dirname(IMPORT_LOG), exist_ok=True)
    logs = []
    if os.path.exists(IMPORT_LOG):
        with open(IMPORT_LOG, 'r', encoding='utf-8') as f:
            logs = json.load(f)
    logs.append({
        'file': filename,
        'status': status,
        'rows': rows,
        'details': details,
        'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })
    with open(IMPORT_LOG, 'w', encoding='utf-8') as f:
        json.dump(logs, f, ensure_ascii=False, indent=2)

def upsert_product(conn, product_id, title='', category='', tier='', style='', scene='',
                   status='active', remark='', image_url='', manager='', list_date=''):
    conn.execute('''
        INSERT INTO products (product_id, title, category, tier, style, scene, status, remark, image_url, manager, list_date, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(product_id) DO UPDATE SET
            title=COALESCE(NULLIF(?, ''), title),
            category=COALESCE(NULLIF(?, ''), category),
            tier=COALESCE(NULLIF(?, ''), tier),
            style=COALESCE(NULLIF(?, ''), style),
            scene=COALESCE(NULLIF(?, ''), scene),
            status=COALESCE(NULLIF(?, ''), status),
            remark=COALESCE(NULLIF(?, ''), remark),
            image_url=COALESCE(NULLIF(?, ''), image_url),
            manager=COALESCE(NULLIF(?, ''), manager),
            list_date=COALESCE(NULLIF(?, ''), list_date),
            updated_at=CURRENT_TIMESTAMP
    ''', (product_id, title, category, tier, style, scene, status, remark, image_url, manager, list_date,
          title, category, tier, style, scene, status, remark, image_url, manager, list_date))

def find_header_row(df, max_rows=10):
    """查找表头行（第一行包含'商品ID'或'宝贝ID'或'主体ID'）"""
    for i in range(min(max_rows, len(df))):
        row_str = ' '.join(str(v) for v in df.iloc[i] if pd.notna(v))
        if '商品ID' in row_str or '宝贝ID' in row_str or '主体ID' in row_str:
            return i
    return 0

def find_id_col(df):
    """查找ID列名"""
    for col in df.columns:
        if ('商品' in str(col) and 'ID' in str(col)) or '宝贝ID' in str(col) or '主体ID' in str(col):
            return col
    return None

def extract_week_start_from_paid(xls):
    """从付费-源 Sheet 提取周起始日期"""
    try:
        for sheet_name in xls.sheet_names:
            if '付费' in sheet_name:
                df = pd.read_excel(xls, sheet_name=sheet_name, header=None, nrows=5)
                for i in range(min(5, len(df))):
                    for v in df.iloc[i]:
                        if pd.notna(v):
                            parsed = parse_date_range(str(v))
                            if parsed:
                                return parsed[0]
    except Exception:
        pass
    return None


SUPPORTED_IMPORT_SUFFIXES = {'.xlsx', '.xls', '.csv', '.zip'}


def find_id_col(df):
    """Recognize both legacy mojibake headers and native Chinese exports."""
    headers = {'\u5546\u54c1ID', '\u5b9d\u8d1dID', '\u4e3b\u4f53ID', 'product_id'}
    for column in df.columns:
        text = str(column).strip()
        if text in headers or ('\u5546\u54c1' in text and 'ID' in text) or ('鍟嗗搧' in text and 'ID' in text):
            return column
    return None


def _prepare_dmp_daily_frame(raw_frame):
    """Return a normalized daily DMP frame when the export uses a non-DMP sheet name."""
    required = {'\u5b9d\u8d1dID', '\u65e5\u671f', '\u652f\u4ed8\u91d1\u989d', 'IPV', '\u8425\u9500\u63a8\u5e7fIPV'}
    for index in range(min(12, len(raw_frame))):
        headers = [str(value).strip() for value in raw_frame.iloc[index].tolist()]
        if required.issubset(set(headers)):
            frame = raw_frame.iloc[index + 1:].copy()
            frame.columns = headers
            return frame.reset_index(drop=True)
    return None


def _is_dmp_daily_frame(df):
    headers = {str(column).strip() for column in df.columns}
    return {'\u5b9d\u8d1dID', '\u65e5\u671f', '\u652f\u4ed8\u91d1\u989d', 'IPV', '\u8425\u9500\u63a8\u5e7fIPV'}.issubset(headers)


def _dmp_date(value):
    if pd.isna(value):
        return ''
    text = str(value).strip()
    if text.endswith('.0'):
        text = text[:-2]
    if len(text) == 8 and text.isdigit():
        return f'{text[:4]}-{text[4:6]}-{text[6:8]}'
    try:
        return pd.to_datetime(value).date().isoformat()
    except (TypeError, ValueError):
        return ''


def _read_excel_sheets(source):
    workbook = pd.ExcelFile(source)
    return [(sheet_name, pd.read_excel(workbook, sheet_name=sheet_name, header=None))
            for sheet_name in workbook.sheet_names]


def _read_csv_sheets(content):
    for encoding in ('utf-8-sig', 'gb18030', 'gbk'):
        try:
            return [('Sheet1', pd.read_csv(io.BytesIO(content), header=None, dtype=object, encoding=encoding))]
        except UnicodeDecodeError:
            continue
    raise ValueError('CSV 文件编码无法识别')


def _read_html_export_sheets(content, excel_error):
    for encoding in ('utf-8-sig', 'gb18030', 'gbk'):
        try:
            tables = _read_html_tables(content.decode(encoding))
        except (UnicodeDecodeError, ValueError):
            continue
        if tables:
            return [(f'Sheet{index + 1}', table) for index, table in enumerate(tables)]
    raise excel_error


def _read_sheets_from_bytes(filename, content):
    suffix = os.path.splitext(filename)[1].lower()
    if suffix == '.csv':
        return _read_csv_sheets(content)
    if suffix not in {'.xlsx', '.xls'}:
        raise ValueError(f'压缩包内不支持 {filename} 文件')
    try:
        return _read_excel_sheets(io.BytesIO(content))
    except (UnicodeDecodeError, ValueError) as error:
        if suffix == '.xls':
            return _read_html_export_sheets(content, error)
        raise


def _read_zip_sheets(filepath):
    sheets = []
    with ZipFile(filepath) as archive:
        entries = [entry for entry in archive.infolist()
                   if not entry.is_dir() and os.path.splitext(entry.filename)[1].lower() in SUPPORTED_IMPORT_SUFFIXES - {'.zip'}]
        if not entries:
            raise ValueError('ZIP 压缩包中没有 .xlsx、.xls 或 .csv 文件')
        for entry in entries:
            for sheet_name, frame in _read_sheets_from_bytes(entry.filename, archive.read(entry)):
                sheets.append((f'{entry.filename}:{sheet_name}', frame))
    return sheets


def _open_excel_for_metadata(filepath):
    if os.path.splitext(filepath)[1].lower() not in {'.xlsx', '.xls'}:
        return None
    try:
        return pd.ExcelFile(filepath)
    except (UnicodeDecodeError, ValueError):
        return None


def read_workbook_sheets(filepath):
    """Read Excel, CSV, and ZIP archives containing supported table files."""
    suffix = os.path.splitext(filepath)[1].lower()
    if suffix == '.csv':
        with open(filepath, 'rb') as source:
            return _read_csv_sheets(source.read())
    if suffix == '.zip':
        return _read_zip_sheets(filepath)
    try:
        return _read_excel_sheets(filepath)
    except (UnicodeDecodeError, ValueError) as excel_error:
        if suffix != '.xls':
            raise

        with open(filepath, 'rb') as source:
            raw = source.read()
        return _read_html_export_sheets(raw, excel_error)


class _HtmlTableParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tables = []
        self.table = None
        self.row = None
        self.cell = None

    def handle_starttag(self, tag, attrs):
        if tag == 'table':
            self.table = []
        elif tag == 'tr' and self.table is not None:
            self.row = []
        elif tag in {'td', 'th'} and self.row is not None:
            self.cell = []

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if tag in {'td', 'th'} and self.cell is not None:
            self.row.append(''.join(self.cell).strip())
            self.cell = None
        elif tag == 'tr' and self.row is not None:
            self.table.append(self.row)
            self.row = None
        elif tag == 'table' and self.table is not None:
            if self.table:
                self.tables.append(self.table)
            self.table = None


def _read_html_tables(content):
    parser = _HtmlTableParser()
    parser.feed(content)
    frames = []
    for rows in parser.tables:
        header, *data = rows
        if header:
            frames.append(pd.DataFrame(data, columns=header))
    return frames

def backup_database():
    """自动备份数据库"""
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config.yaml')
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    db_path = get_db_path()
    backup_dir = config['data'].get('backup_folder', 'data/backups/')
    if not os.path.isabs(backup_dir):
        backup_dir = os.path.join(PROJECT_ROOT, backup_dir)
    max_backups = config['data'].get('max_backups', 30)

    os.makedirs(backup_dir, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = os.path.join(backup_dir, f'dashboard_{timestamp}.db')

    source_conn = sqlite3.connect(db_path)
    backup_conn = sqlite3.connect(backup_path)
    try:
        source_conn.backup(backup_conn)
    finally:
        backup_conn.close()
        source_conn.close()

    # 校验备份
    test_conn = sqlite3.connect(backup_path)
    result = test_conn.execute("PRAGMA integrity_check").fetchone()[0]
    test_conn.close()

    if result != 'ok':
        os.remove(backup_path)
        print(f"  WARNING: Backup failed integrity check, removed {backup_path}")
        return False

    # 清理旧备份
    backups = sorted(glob.glob(os.path.join(backup_dir, 'dashboard_*.db')))
    while len(backups) > max_backups:
        os.remove(backups.pop(0))

    print(f"  Backup: {backup_path}")
    return True

def _legacy_import_excel_file_entry(filepath):
    """Retained only as a rollback reference for one release."""
    from services.legacy_import_adapter import import_file_legacy_response
    return import_file_legacy_response(filepath)


def _legacy_import_excel_file(filepath):
    """通过Web上传导入Excel文件，返回导入结果摘要"""
    init_db()
    conn = get_connection()
    total_rows = 0
    results = []

    try:
        sheets = read_workbook_sheets(filepath)
        xls = _open_excel_for_metadata(filepath)
        sheet_names = [name for name, _ in sheets]

        # 尝试从付费-源 Sheet 提取周起始日期
        default_week_start = extract_week_start_from_paid(xls) if xls is not None else None

        for sheet, df in sheets:
            if df.empty or len(df) < 2:
                results.append({'sheet': sheet, 'status': 'skipped', 'reason': '空表或行数不足'})
                continue

            # 查找表头行
            header_row = find_header_row(df)
            df.columns = df.iloc[header_row].astype(str)
            df = df.iloc[header_row + 1:].reset_index(drop=True)

            # 查找ID列
            id_col = find_id_col(df)
            if id_col is None:
                results.append({'sheet': sheet, 'status': 'skipped', 'reason': '未找到ID列'})
                continue

            # 过滤无效行
            df = df[df.apply(lambda r: is_valid_row(r, id_col), axis=1)]
            if df.empty:
                results.append({'sheet': sheet, 'status': 'skipped', 'reason': '无有效数据行'})
                continue

            rows_imported = process_sheet(conn, df, sheet, id_col, os.path.basename(filepath), default_week_start)
            total_rows += rows_imported
            results.append({'sheet': sheet, 'status': 'success', 'rows': rows_imported})

        conn.commit()
        log_import(os.path.basename(filepath), 'success', total_rows)

        # 自动备份
        try:
            backup_database()
        except Exception as e:
            results.append({'sheet': '_backup', 'status': 'warning', 'reason': str(e)})

        # 回算运营动作效果
        try:
            recalc_action_effects()
        except Exception as e:
            results.append({'sheet': '_recalc', 'status': 'warning', 'reason': str(e)})

    except Exception as e:
        conn.rollback()
        log_import(os.path.basename(filepath), 'failed', 0, str(e))
        raise
    finally:
        conn.close()

    return {
        'success': True,
        'total_rows': total_rows,
        'details': results
    }

def import_excel_file(filepath):
    """Keep the historical file-entry API on the canonical import path."""
    from services.legacy_import_adapter import import_file_legacy_response
    return import_file_legacy_response(filepath)
    # The rollback implementation below remains in this file for one release.
    filename = os.path.basename(filepath)
    with open(filepath, 'rb') as source:
        content = source.read()

    try:
        preview = import_service.preview(filename, content, source_type='auto')
        if preview.get('required_unmapped'):
            raise ValueError('缺少必要字段映射: ' + ', '.join(preview['required_unmapped']))
        report = import_service.confirm(preview['id'], preview['mapping'])
        total_rows = int(report.get('total_rows') or 0)
        results = [{'sheet': 'canonical', 'status': 'success', 'rows': total_rows}]
        log_import(filename, 'success', total_rows)
    except Exception as error:
        log_import(filename, 'failed', 0, str(error))
        raise

    try:
        backup_database()
    except Exception as error:
        results.append({'sheet': '_backup', 'status': 'warning', 'reason': str(error)})
    try:
        recalc_action_effects()
    except Exception as error:
        results.append({'sheet': '_recalc', 'status': 'warning', 'reason': str(error)})

    return {
        'success': True,
        'total_rows': total_rows,
        'details': results,
        'batch_id': report.get('id'),
        'source_type': report.get('source_type'),
        'source_filename': report.get('source_filename'),
        'quality_summary': report.get('quality_summary', {}),
    }


def import_single_file(filepath):
    """导入单个Excel文件"""
    filename = os.path.basename(filepath)
    print(f"\n{'='*60}")
    print(f"Importing: {filename}")
    print(f"{'='*60}")

    init_db()
    conn = get_connection()
    total_rows = 0

    try:
        sheets = read_workbook_sheets(filepath)
        xls = _open_excel_for_metadata(filepath)
        sheet_names = [name for name, _ in sheets]

        # 尝试从付费-源 Sheet 提取周起始日期（供没有日期列的 Sheet 使用）
        default_week_start = extract_week_start_from_paid(xls) if xls is not None else None
        if default_week_start:
            print(f"  Detected week start from paid sheet: {default_week_start}")

        for sheet, df in sheets:
            if df.empty or len(df) < 2:
                continue

            dmp_frame = _prepare_dmp_daily_frame(df)
            if dmp_frame is not None:
                rows_imported = import_dmp_daily(conn, dmp_frame, filename)
                total_rows += rows_imported
                print(f"  Sheet '{sheet}': {rows_imported} DMP daily rows imported")
                continue

            # 查找表头行
            header_row = find_header_row(df)

            df.columns = df.iloc[header_row].astype(str)
            df = df.iloc[header_row + 1:].reset_index(drop=True)

            # 查找ID列
            id_col = find_id_col(df)
            if id_col is None:
                print(f"  Sheet '{sheet}': skipped (no ID column found)")
                continue

            # 过滤无效行
            df = df[df.apply(lambda r: is_valid_row(r, id_col), axis=1)]
            if df.empty:
                print(f"  Sheet '{sheet}': skipped (no valid rows)")
                continue

            rows_imported = process_sheet(conn, df, sheet, id_col, filename, default_week_start)
            total_rows += rows_imported
            print(f"  Sheet '{sheet}': {rows_imported} rows imported")

        conn.commit()
        log_import(filename, 'success', total_rows)
        print(f"Total: {total_rows} rows imported from {filename}")

        # 自动备份
        try:
            backup_database()
        except Exception as e:
            print(f"  WARNING: Backup failed: {e}")

        # 回算运营动作效果
        try:
            recalc_action_effects()
        except Exception as e:
            print(f"  WARNING: recalc_action_effects failed: {e}")

    except Exception as e:
        conn.rollback()
        log_import(filename, 'failed', 0, str(e))
        print(f"ERROR: {e}")
        raise
    finally:
        conn.close()

def process_sheet(conn, df, sheet_name, id_col, filename, default_week_start=None):
    """根据Sheet类型处理数据"""
    rows = 0

    if '单品总表' in sheet_name:
        rows = import_monthly(conn, df, id_col)
    if any(pd.isna(column) for column in df.columns) and not _is_dmp_daily_frame(df):
        return 0
    if _is_dmp_daily_frame(df):
        rows = import_dmp_daily(conn, df, filename)
    elif 'DMP' in sheet_name:
        rows = import_weekly_dmp(conn, df, id_col, default_week_start)
    elif '付费' in sheet_name:
        rows = import_paid_detail(conn, df, id_col)
    elif sheet_name == 'Sheet2' or '备注' in sheet_name:
        rows = import_product_remarks(conn, df, id_col)
    elif '生意参谋' in sheet_name:
        rows = import_shengyi_canmou(conn, df, id_col, filename)
    elif '单品' in sheet_name:
        rows = import_weekly(conn, df, id_col, default_week_start)
    elif '目标' in sheet_name or 'target' in sheet_name.lower():
        rows = import_targets(conn, df, sheet_name)
    else:
        # 尝试按文件名判断日度/周度
        if '日' in filename:
            rows = import_daily(conn, df, id_col, filename)
        else:
            rows = import_weekly(conn, df, id_col, default_week_start)

    return rows

def import_monthly(conn, df, id_col):
    """导入月度数据（单品总表-源）"""
    rows = 0
    for _, row in df.iterrows():
        pid = str(row[id_col]).strip()
        month = clean_month(row.get('月份'))
        if not pid or not month:
            continue

        upsert_product(conn, pid,
            title=str(row.get('商品标题', '')).strip(),
            category=str(row.get('商品类目', '')).strip(),
            image_url=str(row.get('图片链接', '')).strip()
        )

        conn.execute('''
            INSERT INTO monthly_data (product_id, month, payment_amount, refund_amount, net_sales,
                visitors, page_views, uv_value, search_visitors, search_ratio,
                payment_conversion, search_conversion, cart_rate, fav_rate, bounce_rate, avg_stay_duration,
                ad_spend, ad_roi, overall_roi, paid_ratio, refund_paid_ratio,
                keyword_spend, keyword_sales, keyword_roi, keyword_visitors, keyword_ppc,
                crowd_spend, crowd_sales, crowd_roi, crowd_visitors, crowd_ppc,
                site_spend, site_sales, site_roi, site_visitors, site_ppc,
                refund_rate, repurchase_rate, cross_sell_rate,
                buyers, avg_order_value, payment_qty, cart_qty, fav_users, click_rate, score,
                data_source)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(product_id, month) DO UPDATE SET
                payment_amount=excluded.payment_amount, refund_amount=excluded.refund_amount,
                net_sales=excluded.net_sales, visitors=excluded.visitors, page_views=excluded.page_views,
                uv_value=excluded.uv_value, search_visitors=excluded.search_visitors,
                payment_conversion=excluded.payment_conversion, ad_spend=excluded.ad_spend,
                ad_roi=excluded.ad_roi, overall_roi=excluded.overall_roi,
                paid_ratio=excluded.paid_ratio, refund_paid_ratio=excluded.refund_paid_ratio,
                keyword_spend=excluded.keyword_spend, keyword_sales=excluded.keyword_sales,
                refund_rate=excluded.refund_rate, buyers=excluded.buyers,
                avg_order_value=excluded.avg_order_value, payment_qty=excluded.payment_qty,
                data_source=excluded.data_source
        ''', (
            pid, month,
            clean_number(row.get('支付金额')), clean_number(row.get('退款金额')),
            clean_number(row.get('退款后销售额')),
            clean_int(row.get('访客数')), clean_int(row.get('浏览量')),
            clean_number(row.get('UV价值')),
            clean_int(row.get('搜索人数')), clean_percentage(row.get('搜索占比')),
            clean_percentage(row.get('支付转化率')), clean_percentage(row.get('搜索支付转化率')),
            clean_percentage(row.get('加购率')), clean_percentage(row.get('访客收藏率')),
            clean_percentage(row.get('跳失率')), clean_number(row.get('平均停留时长')),
            clean_number(row.get('总推广花费')), clean_number(row.get('推广直接ROI')),
            clean_number(row.get('总投产')),
            clean_percentage(row.get('付费占比')), clean_percentage(row.get('退款付费占比')),
            clean_number(row.get('关键词推广花费')), clean_number(row.get('关键词推广销售额')),
            clean_number(row.get('关键词推广投产')), clean_int(row.get('关键词推广访客数')),
            clean_number(row.get('关键词推广PPC')),
            clean_number(row.get('人群推广花费')), clean_number(row.get('人群推广销售额')),
            clean_number(row.get('人群推广投产')), clean_int(row.get('人群推广访客数')),
            clean_number(row.get('人群推广PPC')),
            clean_number(row.get('货品全站推广花费')), clean_number(row.get('货品全站推广销售额')),
            clean_number(row.get('货品全站推广投产')), clean_int(row.get('货品全站推广访客数')),
            clean_number(row.get('货品全站推广PPC')),
            clean_percentage(row.get('退款率')),
            clean_percentage(row.get('复购率')), clean_percentage(row.get('连带率')),
            clean_int(row.get('支付人数')), clean_number(row.get('客单价')),
            clean_int(row.get('支付件数')), clean_int(row.get('加购件数')),
            clean_int(row.get('收藏人数')), clean_percentage(row.get('总点击率')),
            clean_int(row.get('评分')),
            '单品总表-源'
        ))
        rows += 1
    return rows

def import_weekly(conn, df, id_col, default_week_start=None):
    """导入周度数据（单品-新）"""
    rows = 0
    for _, row in df.iterrows():
        pid = str(row[id_col]).strip()
        if not pid:
            continue

        upsert_product(conn, pid,
            title=str(row.get('商品标题', '')).strip(),
            category=str(row.get('商品类目', '')).strip(),
            tier=str(row.get('分层', '')).strip(),
            style=str(row.get('风格', '')).strip(),
            scene=str(row.get('场景', '')).strip()
        )

        # 尝试提取周起始日期
        week_start = None
        for col in df.columns:
            if '周' in col and ('起始' in col or '开始' in col or '日期' in col):
                val = row.get(col)
                if pd.notna(val):
                    week_start = str(val).strip()
                    break
        if not week_start:
            week_start = default_week_start
        if not week_start:
            continue

        # 运营动作 - 查找包含"动作"的列
        action_1 = None
        action_2 = None
        action_cols = [col for col in df.columns if '动作' in col]
        for col in action_cols:
            val = row.get(col)
            if pd.notna(val) and str(val).strip():
                if action_1 is None:
                    action_1 = str(val).strip()
                elif action_2 is None:
                    action_2 = str(val).strip()

        conn.execute('''
            INSERT INTO weekly_data (product_id, week_start, payment_amount, refund_amount, net_sales,
                ipv, pv, payment_conversion, cart_rate, fav_rate, bounce_rate, avg_stay_duration,
                ad_spend, ad_roi, avg_order_value, action_1, action_2, data_source)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(product_id, week_start) DO UPDATE SET
                payment_amount=excluded.payment_amount, refund_amount=excluded.refund_amount,
                net_sales=excluded.net_sales, ipv=excluded.ipv, pv=excluded.pv,
                payment_conversion=excluded.payment_conversion, ad_spend=excluded.ad_spend,
                ad_roi=excluded.ad_roi, action_1=excluded.action_1, action_2=excluded.action_2,
                data_source=excluded.data_source
        ''', (
            pid, week_start,
            clean_number(row.get('支付金额')), clean_number(row.get('退款金额')),
            clean_number(row.get('净销售/GSV')),
            clean_int(row.get('访客数')), clean_int(row.get('浏览量')),
            clean_percentage(row.get('支付转化率')),
            clean_percentage(row.get('加购率')), clean_percentage(row.get('收藏率')),
            clean_percentage(row.get('跳失率')), clean_number(row.get('平均停留时长')),
            clean_number(row.get('总推广花费')), clean_number(row.get('推广直接ROI')),
            clean_number(row.get('客单价')),
            action_1, action_2, '单品-新'
        ))

        # 提取运营动作写入 operation_actions 表
        before_payment = clean_number(row.get('支付金额'))
        before_visitors = clean_int(row.get('访客数'))
        before_conversion = clean_percentage(row.get('支付转化率'))
        before_roi = clean_number(row.get('推广直接ROI'))

        for action_text in [action_1, action_2]:
            if action_text:
                action_type, action_detail = classify_action(action_text)
                if action_type:
                    conn.execute('''
                        INSERT OR REPLACE INTO operation_actions
                            (product_id, action_date, action_type, action_detail,
                             before_payment, before_visitors, before_conversion, before_roi)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (pid, week_start, action_type, action_detail,
                          before_payment, before_visitors, before_conversion, before_roi))

        rows += 1
    return rows

def _record_legacy_daily_observation(conn, row, product_id, date_value, source_filename, business=False):
    def value(*names):
        for name in names:
            if name in row:
                return row.get(name)
        return None

    payment = _legacy_optional(clean_number, value('\u652f\u4ed8\u91d1\u989d'))
    refund = _legacy_optional(clean_number, value('\u6210\u529f\u9000\u6b3e\u91d1\u989d', '\u9000\u6b3e\u91d1\u989d'))
    observation = {
        'product_id': product_id, 'date': date_value,
        'payment_amount': payment, 'successful_refund_amount': refund,
        'payment_items': _legacy_optional(clean_int, value('\u652f\u4ed8\u4ef6\u6570')),
        'product_visitors': _legacy_optional(clean_int, value('\u5546\u54c1\u8bbf\u5ba2\u6570', '\u8bbf\u5ba2\u6570')),
        'page_views': _legacy_optional(clean_int, value('\u5546\u54c1\u6d4f\u89c8\u91cf', '\u6d4f\u89c8\u91cf')),
        'payment_conversion': _legacy_optional(clean_percentage, value('\u5546\u54c1\u652f\u4ed8\u8f6c\u5316\u7387', '\u652f\u4ed8\u8f6c\u5316\u7387')),
        'favorite_cart_rate': _legacy_optional(clean_percentage, value('\u5546\u54c1\u52a0\u8d2d\u7387', '\u52a0\u8d2d\u7387')),
        'bounce_rate': _legacy_optional(clean_percentage, value('\u5546\u54c1\u8be6\u60c5\u9875\u8df3\u51fa\u7387', '\u8df3\u5931\u7387')),
        'avg_stay_duration': _legacy_optional(clean_number, value('\u5e73\u5747\u505c\u7559\u65f6\u957f')),
        'payment_buyers': _legacy_optional(clean_int, value('\u652f\u4ed8\u4e70\u5bb6\u6570', '\u652f\u4ed8\u4eba\u6570')),
        'payment_unit_price': _legacy_optional(clean_number, value('\u5ba2\u5355\u4ef7')),
    }
    if business:
        observation.update({
            'uv_value': _legacy_optional(clean_number, value('\u8bbf\u5ba2\u5e73\u5747\u4ef7\u503c')),
            'cart_items': _legacy_optional(clean_int, value('\u5546\u54c1\u52a0\u8d2d\u4ef6\u6570')),
            'favorite_users': _legacy_optional(clean_int, value('\u5546\u54c1\u6536\u85cf\u4eba\u6570')),
            'search_conversion': _legacy_optional(clean_percentage, value('\u641c\u7d22\u5f15\u5bfc\u652f\u4ed8\u8f6c\u5316\u7387')),
            'search_visitors': _legacy_optional(clean_int, value('\u641c\u7d22\u5f15\u5bfc\u652f\u4ed8\u4e70\u5bb6\u6570')),
            'cart_users': _legacy_optional(clean_int, value('\u5546\u54c1\u52a0\u8d2d\u4eba\u6570')),
        })
    if payment is not None and refund is not None:
        observation['net_sales'] = payment - refund
    record_daily_observation(conn, observation, source_type='product_day',
                             source_filename=source_filename, source_batch_id=source_filename)


def import_daily(conn, df, id_col, source_filename='legacy-daily'):
    """导入日度数据"""
    rows = 0
    for _, row in df.iterrows():
        pid = str(row[id_col]).strip()
        if not pid:
            continue

        date_val = None
        for col in df.columns:
            if '日期' in col or '时间' in col:
                val = row.get(col)
                if pd.notna(val):
                    date_val = str(val).strip()
                    break
        if not date_val:
            continue

        _record_legacy_daily_observation(conn, row, pid, date_val, source_filename, business=False)
        rows += 1
        continue
        """

        payment = _legacy_optional(clean_number, row.get('鏀粯閲戦'))
        refund = _legacy_optional(clean_number, row.get('閫€娆鹃噾棰?))
        observation = {
            'product_id': pid, 'date': date_val,
            'payment_amount': payment, 'successful_refund_amount': refund,
            'payment_items': _legacy_optional(clean_int, row.get('鏀粯浠舵暟')),
            'product_visitors': _legacy_optional(clean_int, row.get('璁垮鏁?)),
            'page_views': _legacy_optional(clean_int, row.get('娴忚閲?)),
            'payment_conversion': _legacy_optional(clean_percentage, row.get('鏀粯杞寲鐜?)),
            'favorite_cart_rate': _legacy_optional(clean_percentage, row.get('鍔犺喘鐜?)),
            'bounce_rate': _legacy_optional(clean_percentage, row.get('璺冲け鐜?)),
            'avg_stay_duration': _legacy_optional(clean_number, row.get('骞冲潎鍋滅暀鏃堕暱')),
            'ad_spend': _legacy_optional(clean_number, row.get('钀ラ攢鎺ㄥ箍娑堣€?)),
            'ad_roi': _legacy_optional(clean_number, row.get('钀ラ攢鎺ㄥ箍ROI')),
            'payment_buyers': _legacy_optional(clean_int, row.get('鏀粯浜烘暟')),
            'payment_unit_price': _legacy_optional(clean_number, row.get('瀹㈠崟浠?)),
        }
        if payment is not None and refund is not None:
            observation['net_sales'] = payment - refund
        record_daily_observation(conn, observation, source_type='product_day',
                                 source_filename=source_filename, source_batch_id=source_filename)
        rows += 1
        continue

        conn.execute('''
            INSERT INTO daily_data (product_id, date, payment_amount, refund_amount, net_sales,
                payment_qty, ipv, pv, payment_conversion, cart_rate, fav_rate, bounce_rate,
                avg_stay_duration, ad_spend, ad_roi, buyers, avg_order_value, data_source)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(shop_id, product_id, date) DO UPDATE SET
                payment_amount=excluded.payment_amount, refund_amount=excluded.refund_amount,
                ipv=excluded.ipv, payment_conversion=excluded.payment_conversion,
                ad_spend=excluded.ad_spend, ad_roi=excluded.ad_roi,
                data_source=excluded.data_source
        ''', (
            pid, date_val,
            clean_number(row.get('支付金额')), clean_number(row.get('退款金额')),
            clean_number(row.get('净销售')), clean_int(row.get('支付件数')),
            clean_int(row.get('访客数')), clean_int(row.get('浏览量')),
            clean_percentage(row.get('支付转化率')),
            clean_percentage(row.get('加购率')), clean_percentage(row.get('收藏率')),
            clean_percentage(row.get('跳失率')), clean_number(row.get('平均停留时长')),
            clean_number(row.get('营销推广消耗')), clean_number(row.get('营销推广ROI')),
            clean_int(row.get('支付人数')), clean_number(row.get('客单价')),
            '日度数据'
        ))
        rows += 1
        """
    return rows

def import_dmp_daily(conn, df, source_filename='DMP-daily', source_batch_id='legacy-dmp-daily'):
    """Import the daily DMP product-list export into the daily fact table."""
    columns = {
        'product_id': '\u5b9d\u8d1dID', 'title': '\u5b9d\u8d1d\u540d\u79f0', 'date': '\u65e5\u671f',
        'growth_stage': '\u8d27\u54c1\u6210\u957f\u9636\u6bb5', 'payment_amount': '\u652f\u4ed8\u91d1\u989d',
        'ipv': 'IPV', 'paid_ipv': '\u8425\u9500\u63a8\u5e7fIPV', 'ad_spend': '\u8425\u9500\u63a8\u5e7f\u6d88\u8017',
        'ad_roi': '\u8425\u9500\u63a8\u5e7fROI', 'fav_rate': '\u6536\u85cf\u7387',
        'payment_conversion': '\u652f\u4ed8\u8f6c\u5316\u7387', 'repurchase_rate': '\u590d\u8d2d\u7387',
        'presale_amount': '\u9884\u552e\u652f\u4ed8\u91d1\u989d', 'presale_qty': '\u9884\u552e\u9500\u91cf',
        'organic_ipv': '\u975e\u63a8\u5e7fIPV', 'search_ipv': '\u641c\u7d22IPV',
        'recommend_ipv': '\u63a8\u8350IPV', 'search_click_rate': '\u514d\u8d39\u641c\u7d22\u70b9\u51fb\u7387',
        'avg_order_value': '\u7b14\u5355\u4ef7', 'cross_sell_qty': '\u8fde\u5e26\u8d2d\u4e70\u91cf',
        'cross_sell_rate': '\u8fde\u5e26\u8d2d\u4e70\u7387', 'category_width': '\u8fde\u5e26\u8d2d\u4e70\u53f6\u5b50\u7c7b\u76ee\u5bbd\u5ea6',
        'repurchase_users': '\u590d\u8d2d\u7528\u6237\u6570',
    }
    required = {columns[key] for key in ('product_id', 'date', 'payment_amount', 'ipv')}
    if not required.issubset(set(df.columns)):
        return 0
    rows = 0
    for _, source in df.iterrows():
        pid = str(source.get(columns['product_id'], '')).strip()
        if not pid or pid in {'\u603b\u8ba1', '\u5408\u8ba1'}:
            continue
        date_value = _dmp_date(source.get(columns['date']))
        if not date_value:
            continue
        title = str(source.get(columns['title'], '')).strip()
        conn.execute('''
            INSERT INTO products (product_id, title, status, updated_at)
            VALUES (?, ?, 'active', CURRENT_TIMESTAMP)
            ON CONFLICT(product_id) DO UPDATE SET
                title=COALESCE(NULLIF(excluded.title, ''), products.title), updated_at=CURRENT_TIMESTAMP
        ''', (pid, title))
        number = lambda key: _legacy_optional(clean_number, source.get(columns[key])) if columns[key] in source else None
        integer = lambda key: _legacy_optional(clean_int, source.get(columns[key])) if columns[key] in source else None
        percent = lambda key: _legacy_optional(clean_percentage, source.get(columns[key])) if columns[key] in source else None
        record_daily_observation(
            conn,
            {
                'product_id': pid,
                'date': date_value,
                'payment_amount': number('payment_amount'),
                'product_visitors': integer('ipv'),
                'paid_visitors': integer('paid_ipv'),
                'organic_visitors': integer('organic_ipv'),
                'search_visitors': integer('search_ipv'),
                'recommend_visitors': integer('recommend_ipv'),
                'payment_conversion': percent('payment_conversion'),
                'favorite_cart_rate': percent('fav_rate'),
                'repurchase_rate': percent('repurchase_rate'),
                'presale_amount': number('presale_amount'),
                'presale_qty': integer('presale_qty'),
                'search_click_rate': percent('search_click_rate'),
                'payment_unit_price': number('avg_order_value'),
                'cross_sell_qty': integer('cross_sell_qty'),
                'cross_sell_rate': percent('cross_sell_rate'),
                'category_width': integer('category_width'),
                'repurchase_users': integer('repurchase_users'),
                'ad_spend': number('ad_spend'),
                'ad_roi': number('ad_roi'),
            },
            source_type='dmp_product_day',
            source_filename=source_filename,
            source_batch_id=source_batch_id,
        )
        rows += 1
    return rows


def import_weekly_dmp(conn, df, id_col, default_week_start=None):
    """导入DMP周度数据"""
    rows = 0
    for _, row in df.iterrows():
        pid = str(row[id_col]).strip()
        if not pid:
            continue

        # DMP-源 没有周日期列，使用默认值
        week_start = default_week_start
        if not week_start:
            continue

        conn.execute('''
            INSERT INTO weekly_data (product_id, week_start, payment_amount, ipv, pv, search_ipv, recommend_ipv,
                paid_ipv, organic_ipv, payment_conversion, cart_rate,
                bounce_rate, avg_stay_duration, repurchase_rate, cross_sell_rate,
                presale_amount, presale_qty, avg_order_value, category_width, repurchase_users,
                ad_spend, ad_roi, search_click_rate, industry_ctr, cross_sell_qty, data_source)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(product_id, week_start) DO UPDATE SET
                payment_amount=excluded.payment_amount,
                ipv=excluded.ipv, pv=excluded.pv,
                search_ipv=excluded.search_ipv, recommend_ipv=excluded.recommend_ipv,
                paid_ipv=excluded.paid_ipv, organic_ipv=excluded.organic_ipv,
                payment_conversion=excluded.payment_conversion,
                cart_rate=excluded.cart_rate,
                bounce_rate=excluded.bounce_rate,
                avg_stay_duration=excluded.avg_stay_duration,
                repurchase_rate=excluded.repurchase_rate,
                cross_sell_rate=excluded.cross_sell_rate,
                presale_amount=excluded.presale_amount,
                presale_qty=excluded.presale_qty,
                avg_order_value=excluded.avg_order_value,
                category_width=excluded.category_width,
                repurchase_users=excluded.repurchase_users,
                ad_spend=excluded.ad_spend, ad_roi=excluded.ad_roi,
                search_click_rate=excluded.search_click_rate,
                industry_ctr=excluded.industry_ctr,
                cross_sell_qty=excluded.cross_sell_qty,
                data_source=excluded.data_source
        ''', (
            pid, week_start,
            clean_number(row.get('支付金额')),
            clean_int(row.get('IPV')), clean_int(row.get('PV')),
            clean_int(row.get('搜索IPV')), clean_int(row.get('推荐IPV')),
            clean_int(row.get('营销推广IPV')), clean_int(row.get('非推广IPV')),
            clean_percentage(row.get('支付转化率')), clean_percentage(row.get('收加率')),
            clean_percentage(row.get('跳失率')), clean_number(row.get('平均停留时长')),
            clean_percentage(row.get('复购率')), clean_percentage(row.get('连带购买率')),
            clean_number(row.get('预售支付金额')), clean_int(row.get('预售销量')),
            clean_number(row.get('笔单价')), clean_int(row.get('连带购买叶子类目宽度')),
            clean_int(row.get('复购用户数')),
            clean_number(row.get('消耗/花费')), clean_number(row.get('ROI')),
            clean_percentage(row.get('免费搜索点击率')),
            clean_percentage(row.get('行业点击率')),
            clean_int(row.get('连带购买量')),
            'DMP-源'
        ))
        rows += 1
    return rows

def import_paid_detail(conn, df, id_col):
    """导入付费推广明细"""
    rows = 0
    for _, row in df.iterrows():
        pid = str(row[id_col]).strip()
        if not pid:
            continue
        date_range = None
        for col in df.columns:
            if '日期' in col or '时间' in col or '范围' in col:
                val = row.get(col)
                if pd.notna(val):
                    parsed = parse_date_range(str(val))
                    if parsed:
                        date_range = f"{parsed[0]}~{parsed[1]}"
                    else:
                        date_range = str(val).strip()
                    break
        if not date_range:
            continue

        conn.execute('''
            INSERT INTO paid_detail (product_id, date_range, impressions, clicks, cost,
                ctr, cpc, cpm, total_gmv, total_orders, direct_gmv, indirect_gmv,
                roi, cart_adds, cart_rate, favs, new_buyers, members_gmv,
                direct_orders, indirect_orders, click_conversion, presale_roi,
                total_cost, direct_cart_adds, indirect_cart_adds,
                store_favs, store_fav_cost, total_fav_cart, total_fav_cart_cost,
                item_fav_cart, item_fav_cart_cost, total_favs,
                item_fav_cost, item_fav_rate, cart_cost)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(product_id, date_range) DO UPDATE SET
                impressions=excluded.impressions, clicks=excluded.clicks,
                cost=excluded.cost, roi=excluded.roi,
                direct_orders=excluded.direct_orders, indirect_orders=excluded.indirect_orders,
                click_conversion=excluded.click_conversion, presale_roi=excluded.presale_roi,
                total_cost=excluded.total_cost, direct_cart_adds=excluded.direct_cart_adds,
                indirect_cart_adds=excluded.indirect_cart_adds,
                store_favs=excluded.store_favs, store_fav_cost=excluded.store_fav_cost,
                total_fav_cart=excluded.total_fav_cart, total_fav_cart_cost=excluded.total_fav_cart_cost,
                item_fav_cart=excluded.item_fav_cart, item_fav_cart_cost=excluded.item_fav_cart_cost,
                total_favs=excluded.total_favs, item_fav_cost=excluded.item_fav_cost,
                item_fav_rate=excluded.item_fav_rate, cart_cost=excluded.cart_cost
        ''', (
            pid, date_range,
            clean_int(row.get('展现量')), clean_int(row.get('点击量')),
            clean_number(row.get('花费')), clean_percentage(row.get('点击率')),
            clean_number(row.get('平均点击花费')), clean_number(row.get('千次展现花费')),
            clean_number(row.get('总成交金额')), clean_int(row.get('总成交笔数')),
            clean_number(row.get('直接成交金额')), clean_number(row.get('间接成交金额')),
            clean_number(row.get('投入产出比')),
            clean_int(row.get('总购物车数')), clean_percentage(row.get('加购率')),
            clean_int(row.get('收藏宝贝数')), clean_int(row.get('成交新客数')),
            clean_number(row.get('会员成交金额')),
            clean_int(row.get('直接成交笔数')), clean_int(row.get('间接成交笔数')),
            clean_percentage(row.get('点击转化率')), clean_number(row.get('含预售投产比')),
            clean_number(row.get('总成交成本')),
            clean_int(row.get('直接购物车数')), clean_int(row.get('间接购物车数')),
            clean_int(row.get('收藏店铺数')), clean_number(row.get('店铺收藏成本')),
            clean_int(row.get('总收藏加购数')), clean_number(row.get('总收藏加购成本')),
            clean_int(row.get('宝贝收藏加购数')), clean_number(row.get('宝贝收藏加购成本')),
            clean_int(row.get('总收藏数')),
            clean_number(row.get('宝贝收藏成本')), clean_percentage(row.get('宝贝收藏率')),
            clean_number(row.get('加购成本'))
        ))
        rows += 1
    return rows

def import_product_remarks(conn, df, id_col):
    """导入商品备注（Sheet2）"""
    rows = 0
    for _, row in df.iterrows():
        pid = str(row[id_col]).strip()
        if not pid:
            continue
        remark = str(row.get('备注', '')).strip() if pd.notna(row.get('备注')) else ''
        style = str(row.get('风格', '')).strip() if pd.notna(row.get('风格')) else ''
        scene = str(row.get('场景', '')).strip() if pd.notna(row.get('场景')) else ''
        status = 'delisted' if '下架' in remark else 'active'
        upsert_product(conn, pid, status=status, remark=remark, style=style, scene=scene)
        rows += 1
    return rows

def import_targets(conn, df, sheet_name):
    """导入目标数据"""
    rows = 0
    # 检测是否为店铺级目标（没有商品ID列）或商品级目标（有商品ID列）
    id_col = None
    for col in df.columns:
        if '商品' in col and 'ID' in col:
            id_col = col
            break

    # 查找月份列
    month_col = None
    for col in df.columns:
        if '月' in col:
            month_col = col
            break

    if month_col is None:
        # 尝试用文件名中的月份
        return 0

    for _, row in df.iterrows():
        month = clean_month(row.get(month_col))
        if not month:
            continue

        if id_col is None:
            # 店铺级目标
            conn.execute('''
                INSERT OR REPLACE INTO shop_targets (period, target_gsv, target_ad_spend, target_ad_ratio, target_conversion, target_refund_rate)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                month,
                clean_number(row.get('GSV目标', row.get('目标GSV', row.get('目标销售额')))),
                clean_number(row.get('费用预算', row.get('推广预算', row.get('目标花费')))),
                clean_percentage(row.get('费比目标', row.get('目标费比'))),
                clean_percentage(row.get('转化率目标')),
                clean_percentage(row.get('退款率上限', row.get('目标退款率')))
            ))
        else:
            # 商品/分层级目标
            pid = str(row[id_col]).strip()
            if not pid:
                continue
            conn.execute('''
                INSERT OR REPLACE INTO product_targets (product_id, tier, period, target_gsv, target_ad_spend, target_ad_ratio)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                pid,
                str(row.get('分层', '')).strip(),
                month,
                clean_number(row.get('GSV目标', row.get('目标GSV'))),
                clean_number(row.get('费用预算', row.get('推广预算'))),
                clean_percentage(row.get('费比目标', row.get('目标费比')))
            ))
        rows += 1
    return rows

def import_shengyi_canmou(conn, df, id_col, source_filename='business-advisor-daily'):
    """导入生意参谋数据（日度）"""
    rows = 0
    for _, row in df.iterrows():
        pid = str(row[id_col]).strip()
        if not pid:
            continue

        date_val = None
        for col in df.columns:
            if '统计日期' in col or '日期' in col:
                val = row.get(col)
                if pd.notna(val):
                    date_val = str(val).strip()
                    # 处理 datetime 格式
                    if '00:00:00' in date_val:
                        date_val = date_val.split(' ')[0]
                    break
        if not date_val:
            continue

        _record_legacy_daily_observation(conn, row, pid, date_val, source_filename, business=True)
        rows += 1
        continue
        """

        payment = _legacy_optional(clean_number, row.get('鏀粯閲戦'))
        refund = _legacy_optional(clean_number, row.get('鎴愬姛閫€娆鹃噾棰?))
        observation = {
            'product_id': pid, 'date': date_val,
            'payment_amount': payment, 'successful_refund_amount': refund,
            'payment_items': _legacy_optional(clean_int, row.get('鏀粯浠舵暟')),
            'product_visitors': _legacy_optional(clean_int, row.get('鍟嗗搧璁垮鏁?)),
            'page_views': _legacy_optional(clean_int, row.get('鍟嗗搧娴忚閲?)),
            'payment_conversion': _legacy_optional(clean_percentage, row.get('鍟嗗搧鏀粯杞寲鐜?)),
            'favorite_cart_rate': _legacy_optional(clean_percentage, row.get('鍟嗗搧鍔犺喘鐜?)),
            'bounce_rate': _legacy_optional(clean_percentage, row.get('鍟嗗搧璇︽儏椤佃烦鍑虹巼')),
            'avg_stay_duration': _legacy_optional(clean_number, row.get('骞冲潎鍋滅暀鏃堕暱')),
            'payment_buyers': _legacy_optional(clean_int, row.get('鏀粯涔板鏁?)),
            'payment_unit_price': _legacy_optional(clean_number, row.get('瀹㈠崟浠?)),
            'uv_value': _legacy_optional(clean_number, row.get('璁垮骞冲潎浠峰€?)),
            'cart_items': _legacy_optional(clean_int, row.get('鍟嗗搧鍔犺喘浠舵暟')),
            'favorite_users': _legacy_optional(clean_int, row.get('鍟嗗搧鏀惰棌浜烘暟')),
            'search_conversion': _legacy_optional(clean_percentage, row.get('鎼滅储寮曞鏀粯杞寲鐜?)),
            'search_visitors': _legacy_optional(clean_int, row.get('鎼滅储寮曞鏀粯涔板鏁?)),
            'cart_users': _legacy_optional(clean_int, row.get('鍟嗗搧鍔犺喘浜烘暟')),
        }
        if payment is not None and refund is not None:
            observation['net_sales'] = payment - refund
        record_daily_observation(conn, observation, source_type='product_day',
                                 source_filename=source_filename, source_batch_id=source_filename)
        rows += 1
        continue

        conn.execute('''
            INSERT INTO daily_data (product_id, date, payment_amount, refund_amount, net_sales,
                payment_qty, ipv, pv, payment_conversion, cart_rate, fav_rate, bounce_rate,
                avg_stay_duration, buyers, avg_order_value, uv_value, cart_qty, fav_users,
                search_conversion, search_visitors, cart_users, data_source)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(shop_id, product_id, date) DO UPDATE SET
                payment_amount=excluded.payment_amount, refund_amount=excluded.refund_amount,
                ipv=excluded.ipv, payment_conversion=excluded.payment_conversion,
                uv_value=excluded.uv_value, cart_qty=excluded.cart_qty,
                fav_users=excluded.fav_users, search_conversion=excluded.search_conversion,
                search_visitors=excluded.search_visitors, cart_users=excluded.cart_users,
                data_source=excluded.data_source
        ''', (
            pid, date_val,
            clean_number(row.get('支付金额')), clean_number(row.get('成功退款金额')),
            clean_number(row.get('支付金额')) - clean_number(row.get('成功退款金额')),
            clean_int(row.get('支付件数')),
            clean_int(row.get('商品访客数')), clean_int(row.get('商品浏览量')),
            clean_percentage(row.get('商品支付转化率')),
            clean_percentage(row.get('商品加购率')),
            clean_percentage(row.get('商品收藏率')),
            clean_percentage(row.get('商品详情页跳出率')),
            clean_number(row.get('平均停留时长')),
            clean_int(row.get('支付买家数')), clean_number(row.get('客单价')),
            clean_number(row.get('访客平均价值')),
            clean_int(row.get('商品加购件数')),
            clean_int(row.get('商品收藏人数')),
            clean_percentage(row.get('搜索引导支付转化率')),
            clean_int(row.get('搜索引导支付买家数')),
            clean_int(row.get('商品加购人数')),
            '生意参谋'
        ))
        rows += 1
        """
    return rows

def import_reviews_from_file(filepath):
    """从文件导入评价数据"""
    conn = get_connection()
    count = 0

    if filepath.endswith('.csv'):
        df = pd.read_csv(filepath)
    else:
        df = pd.read_excel(filepath)

    # 自动检测列名
    content_col = None
    product_col = None
    rating_col = None
    date_col = None

    for col in df.columns:
        col_lower = str(col).lower()
        if any(k in col_lower for k in ['评价', '评论', '内容', 'content', 'review']):
            content_col = col
        if any(k in col_lower for k in ['商品', '宝贝', 'product']):
            product_col = col
        if any(k in col_lower for k in ['评分', '星级', 'rating', 'score']):
            rating_col = col
        if any(k in col_lower for k in ['日期', '时间', 'date', 'time']):
            date_col = col

    if not content_col:
        raise ValueError("未找到评价内容列")

    import jieba
    import jieba.analyse

    # 简单情感词典
    positive_words = ['好', '棒', '喜欢', '满意', '漂亮', '不错', '精致', '方便', '实用', '质量好',
                       '推荐', '值得', '大气', '上档次', '好看', '合适', '完美', '优秀', '舒适',
                       '清晰', '牢固', '厚实', '细腻', '光滑', '整洁', '美观', '高档', '精致']
    negative_words = ['差', '烂', '垃圾', '退货', '退款', '不好', '失望', '假', '骗', '破损',
                       '掉色', '变形', '异味', '小', '薄', '短', '漏', '裂', '坏', '难看',
                       '粗糙', '廉价', '不好用', '不推荐', '不值', '踩坑', '上当', '差评']

    # 场景词
    scene_words = ['玄关', '客厅', '卧室', '厨房', '阳台', '书房', '卫生间', '儿童房',
                   '餐厅', '办公室', '出租房', '新家', '新房', '入户', '门口', '鞋柜',
                   '电视柜', '茶几', '餐桌', '床头', '窗台', '酒柜', '梳妆台']

    for _, row in df.iterrows():
        content = str(row.get(content_col, '')).strip()
        if not content or content == 'nan':
            continue

        pid = str(row.get(product_col, '')).strip() if product_col else ''
        rating = int(row.get(rating_col, 5)) if rating_col else 5
        review_date = str(row.get(date_col, '')).strip() if date_col else ''

        # 情感分析
        pos_count = sum(1 for w in positive_words if w in content)
        neg_count = sum(1 for w in negative_words if w in content)

        if pos_count > neg_count * 2:
            sentiment = 'positive'
        elif neg_count > pos_count * 2:
            sentiment = 'negative'
        else:
            sentiment = 'neutral'

        # 提取正面/负面维度（基于关键词匹配）
        pos_dims = []
        neg_dims = []
        dim_keywords = {
            '外观颜值': ['好看', '漂亮', '美观', '精致', '大气', '上档次', '高档', '质感'],
            '容量收纳': ['大', '能装', '容量', '收纳', '放', '储物', '空间'],
            '材质品质': ['质量', '材质', '做工', '厚实', '结实', '牢固', '耐用'],
            '性价比': ['划算', '值得', '便宜', '实惠', '超值', '物有所值', '性价比'],
            '尺寸合适': ['合适', '刚好', '大小合适', '尺寸合适', '正合适'],
            '安装方便': ['安装', '组装', '简单', '方便', '容易', '好装'],
            '颜色准确': ['颜色', '色差', '色', '跟图片一样', '实物一致'],
            '物流服务': ['物流', '快递', '发货', '包装', '客服', '服务'],
        }

        for dim, keywords in dim_keywords.items():
            if any(k in content for k in keywords):
                if sentiment == 'positive':
                    pos_dims.append(dim)
                elif sentiment == 'negative':
                    neg_dims.append(dim)

        # 提取场景
        scenes = [s for s in scene_words if s in content]

        # 判断是否有效评价（长度>10字）
        is_effective = 1 if len(content) > 10 else 0

        # 是否有图
        has_image = 0  # CSV/Excel中通常无法判断

        conn.execute('''
            INSERT INTO reviews (product_id, review_date, content, rating, sentiment,
                positive_dims, negative_dims, scenes, is_effective, has_image, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (pid, review_date, content, rating, sentiment,
              json.dumps(pos_dims, ensure_ascii=False),
              json.dumps(neg_dims, ensure_ascii=False),
              json.dumps(scenes, ensure_ascii=False),
              is_effective, has_image, os.path.basename(filepath)))
        count += 1

    conn.commit()

    # 回写 review_summary 表
    if product_col:
        for pid in df[product_col].dropna().unique():
            pid = str(pid).strip()
            if not pid:
                continue
            summary = conn.execute('''
                SELECT
                    COUNT(*) as total,
                    AVG(rating) as avg_rating,
                    SUM(CASE WHEN sentiment='positive' THEN 1 ELSE 0 END) as positive,
                    SUM(CASE WHEN sentiment='negative' THEN 1 ELSE 0 END) as negative,
                    SUM(is_effective) as effective
                FROM reviews WHERE product_id = ?
            ''', (pid,)).fetchone()

            if summary and summary[0] > 0:
                total = summary[0]
                pos_rate = summary[2] / total if total > 0 else 0
                neg_rate = summary[3] / total if total > 0 else 0
                eff_rate = summary[4] / total if total > 0 else 0

                # Top 正面维度
                top_pos = conn.execute('''
                    SELECT value, COUNT(*) as c FROM reviews, json_each(positive_dims)
                    WHERE product_id = ? GROUP BY value ORDER BY c DESC LIMIT 3
                ''', (pid,)).fetchall()

                # Top 负面维度
                top_neg = conn.execute('''
                    SELECT value, COUNT(*) as c FROM reviews, json_each(negative_dims)
                    WHERE product_id = ? GROUP BY value ORDER BY c DESC LIMIT 3
                ''', (pid,)).fetchall()

                # Top 场景
                top_scenes = conn.execute('''
                    SELECT value, COUNT(*) as c FROM reviews, json_each(scenes)
                    WHERE product_id = ? GROUP BY value ORDER BY c DESC LIMIT 3
                ''', (pid,)).fetchall()

                conn.execute('''
                    INSERT OR REPLACE INTO review_summary
                        (product_id, analysis_date, total_reviews, positive_rate, negative_rate,
                         effective_rate, top_positive_dims, top_negative_dims, top_scenes)
                    VALUES (?, date('now'), ?, ?, ?, ?, ?, ?, ?)
                ''', (pid, total, pos_rate, neg_rate, eff_rate,
                      json.dumps([r[0] for r in top_pos], ensure_ascii=False),
                      json.dumps([r[0] for r in top_neg], ensure_ascii=False),
                      json.dumps([r[0] for r in top_scenes], ensure_ascii=False)))

    conn.commit()
    conn.close()
    return count

def recalc_action_effects():
    """回算运营动作效果：查找每个动作的下一周数据，计算变化率和效果评分"""
    conn = get_connection()
    try:
        # 获取所有需要回算的动作（after_payment 为 0 的）
        actions = conn.execute('''
            SELECT id, product_id, action_date,
                   before_payment, before_visitors, before_conversion, before_roi
            FROM operation_actions
            WHERE after_payment = 0 OR after_payment IS NULL
        ''').fetchall()

        updated = 0
        for action in actions:
            action_id = action['id']
            product_id = action['product_id']
            action_date = action['action_date']

            # 查找该商品下一周的数据
            next_week = conn.execute('''
                SELECT payment_amount, ipv, payment_conversion, ad_roi
                FROM weekly_data
                WHERE product_id = ? AND week_start > ?
                ORDER BY week_start ASC LIMIT 1
            ''', (product_id, action_date)).fetchone()

            if next_week:
                after_payment = next_week['payment_amount'] or 0
                after_visitors = next_week['ipv'] or 0
                after_conversion = next_week['payment_conversion'] or 0
                after_roi = next_week['ad_roi'] or 0

                before_payment = action['before_payment'] or 0
                before_conversion = action['before_conversion'] or 0
                before_roi = action['before_roi'] or 0

                # 计算变化率
                payment_change = round((after_payment - before_payment) / before_payment * 100, 1) if before_payment > 0 else 0
                conversion_change = round((after_conversion - before_conversion) / before_conversion * 100, 1) if before_conversion > 0 else 0
                roi_change = round((after_roi - before_roi) / before_roi * 100, 1) if before_roi > 0 else 0

                # 效果评分：综合支付变化、转化变化、ROI变化的加权平均
                effectiveness_score = round(
                    payment_change * 0.4 + conversion_change * 0.3 + roi_change * 0.3, 1
                )

                conn.execute('''
                    UPDATE operation_actions SET
                        after_payment = ?,
                        after_visitors = ?,
                        after_conversion = ?,
                        after_roi = ?,
                        payment_change = ?,
                        conversion_change = ?,
                        roi_change = ?,
                        effectiveness_score = ?
                    WHERE id = ?
                ''', (after_payment, after_visitors, after_conversion, after_roi,
                      payment_change, conversion_change, roi_change, effectiveness_score,
                      action_id))
                updated += 1

        conn.commit()
        print(f"  Action effects recalculated: {updated} actions updated")
        return updated
    except Exception as e:
        conn.rollback()
        print(f"  ERROR: recalc_action_effects failed: {e}")
        raise
    finally:
        conn.close()

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python import_data.py <file.xlsx> [file2.xlsx ...]")
        print("       python import_data.py --batch <folder>")
        sys.exit(1)

    if sys.argv[1] == '--batch':
        folder = sys.argv[2] if len(sys.argv) > 2 else '.'
        files = sorted(glob.glob(os.path.join(folder, '*.xlsx')))
        if not files:
            print(f"No .xlsx files found in {folder}")
            sys.exit(1)
        for f in files:
            import_single_file(f)
    else:
        for f in sys.argv[1:]:
            import_single_file(f)
