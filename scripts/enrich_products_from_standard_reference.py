#!/usr/bin/env python3
"""Enrich dashboard products from the 标品货品 reference workbook.

The workbook provides direct 标品/非标 labels in 数据 (2) and direct
货品成长阶段 values in DMP. Classification is deliberately conservative:
direct Excel labels are authoritative, a small auditable keyword rule is used
only for very explicit titles, and the rest is marked 待复核 rather than being
presented as a fact. Style attributes and the YYYY春夏/秋冬款 node are derived
from title/category/list date and are recorded as rule-based fields.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import re
import shutil
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

from openpyxl import load_workbook

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = PROJECT_ROOT / 'data' / 'demo' / 'dashboard.db'
DEFAULT_WORKBOOK = Path(r'E:\桌面\0817\标品货品0817.xlsx')
DEFAULT_REPORT = PROJECT_ROOT / 'data' / 'product_classification_report.json'
AS_OF_DATE = dt.date(2026, 8, 17)

DIRECT_TYPE_MAP = {
    '标品袜子': '标品',
    '标品': '标品',
    '非标': '非标品',
    '非标品': '非标品',
}
REFERENCE_SHEET_NAMES = ('数据 (2)', '单品', '汇总')


def clean(value: Any) -> str:
    if value is None:
        return ''
    if isinstance(value, dt.datetime):
        return value.date().isoformat()
    if isinstance(value, dt.date):
        return value.isoformat()
    return str(value).strip()


def normalise_id(value: Any) -> str:
    raw = clean(value)
    if not raw:
        return ''
    if re.fullmatch(r'\d+\.0+', raw):
        return raw.split('.', 1)[0]
    return raw


def parse_date(value: Any) -> dt.date | None:
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    text = clean(value)
    if not text:
        return None
    match = re.search(r'(20\d{2})[-/年](\d{1,2})[-/月](\d{1,2})', text)
    if not match:
        return None
    try:
        return dt.date(*(int(part) for part in match.groups()))
    except ValueError:
        return None


def get_sheet(workbook, name: str):
    if name in workbook.sheetnames:
        return workbook[name]
    raise KeyError(f'工作簿中未找到工作表：{name}；实际：{workbook.sheetnames}')


def get_first_sheet(workbook, names: Iterable[str]):
    for name in names:
        if name in workbook.sheetnames:
            return workbook[name]
    raise KeyError(f'工作簿中未找到参考分类表（候选：{list(names)}）；实际：{workbook.sheetnames}')


def header_index(row: Iterable[Any]) -> dict[str, int]:
    return {clean(value): index for index, value in enumerate(row) if clean(value)}


def rows_after_header(sheet, required: Iterable[str], scan_limit: int = 8):
    """Find a header row without assuming whether the sheet has a title row."""
    rows = sheet.iter_rows(values_only=True)
    required_names = set(required)
    for row_number, row in enumerate(rows, start=1):
        headers = header_index(row)
        if required_names.issubset(headers):
            return headers, rows
        if row_number >= scan_limit:
            break
    raise ValueError(f'{sheet.title} 缺少字段：{sorted(required_names)}')


def cell(row: list[Any] | tuple[Any, ...], index: int | None) -> Any:
    return row[index] if index is not None and index < len(row) else None


def read_reference(workbook_path: Path):
    workbook = load_workbook(workbook_path, read_only=True, data_only=True)
    classifications: dict[str, dict[str, str]] = {}
    growth_values: dict[str, Counter[str]] = defaultdict(Counter)

    # Older references use 数据 (2), while the refreshed 0817 workbook
    # stores the same direct labels in 单品.  Both are direct user-maintained
    # classifications, so there is no inference step here.
    data_sheet = get_first_sheet(workbook, REFERENCE_SHEET_NAMES)
    required = ['商品ID', '商品标题', '归类', '商品类目', '上架时间']
    headers, rows = rows_after_header(data_sheet, required)
    for raw in rows:
        product_id = normalise_id(cell(raw, headers['商品ID']))
        raw_type = clean(cell(raw, headers['归类']))
        product_type = DIRECT_TYPE_MAP.get(raw_type)
        if not product_id or not product_type:
            continue
        classifications[product_id] = {
            'product_type': product_type,
            'title': clean(cell(raw, headers['商品标题'])),
            'category': clean(cell(raw, headers['商品类目'])),
            'list_date': clean(cell(raw, headers['上架时间'])),
            'classification_source': 'Excel原始归类',
        }

    dmp_sheet = get_sheet(workbook, 'DMP')
    dmp_headers, dmp_rows = rows_after_header(dmp_sheet, ['宝贝ID', '货品成长阶段'])
    for raw in dmp_rows:
        product_id = normalise_id(cell(raw, dmp_headers['宝贝ID']))
        growth_stage = clean(cell(raw, dmp_headers['货品成长阶段']))
        if product_id and product_id != '总计' and growth_stage:
            growth_values[product_id][growth_stage] += 1
    growth = {
        product_id: counts.most_common(1)[0][0]
        for product_id, counts in growth_values.items()
    }
    workbook.close()
    return classifications, growth


def normalise_text(title: str, category: str = '') -> str:
    text = f'{title} {category}'.lower()
    return re.sub(r'[^0-9a-z\u4e00-\u9fff]+', '', text)


def char_features(title: str, category: str = '') -> set[str]:
    text = normalise_text(title, category)
    if not text:
        return {'__empty__'}
    padded = f'^{text}$'
    features = set()
    for n in (1, 2, 3):
        features.update(padded[index:index + n] for index in range(max(0, len(padded) - n + 1)))
    return features


class BinaryNgramNaiveBayes:
    """Minimal binary Naive-Bayes classifier with balanced class priors."""

    def __init__(self) -> None:
        self.class_docs: Counter[str] = Counter()
        self.feature_docs: dict[str, Counter[str]] = defaultdict(Counter)
        self.vocabulary: set[str] = set()

    def fit(self, rows: Iterable[dict[str, str]]) -> None:
        for row in rows:
            label = row['product_type']
            self.class_docs[label] += 1
            features = char_features(row.get('title', ''), row.get('category', ''))
            self.vocabulary.update(features)
            for feature in features:
                self.feature_docs[label][feature] += 1
        if len(self.class_docs) != 2:
            raise ValueError(f'训练数据需要两类，实际：{dict(self.class_docs)}')

    def predict(self, title: str, category: str = '') -> tuple[str, float]:
        features = char_features(title, category)
        labels = sorted(self.class_docs)
        vocabulary_size = max(1, len(self.vocabulary))
        # Balanced priors stop the workbook's large 非标 class from swallowing
        # every otherwise-neutral title.
        scores: dict[str, float] = {}
        for label in labels:
            doc_count = self.class_docs[label]
            present = self.feature_docs[label]
            score = math.log(1 / len(labels))
            denominator = doc_count + 2
            for feature in features:
                score += math.log((present[feature] + 1) / denominator)
            scores[label] = score
        max_score = max(scores.values())
        exp_scores = {label: math.exp(score - max_score) for label, score in scores.items()}
        total = sum(exp_scores.values())
        winner = max(exp_scores, key=exp_scores.get)
        return winner, exp_scores[winner] / total if total else 0.5


def evaluate_model(rows: list[dict[str, str]]) -> dict[str, Any]:
    train: list[dict[str, str]] = []
    test: list[dict[str, str]] = []
    for row in rows:
        bucket = int(hashlib.sha1(row['product_id'].encode('utf-8')).hexdigest(), 16) % 5
        (test if bucket == 0 else train).append(row)
    model = BinaryNgramNaiveBayes()
    model.fit(train)
    matrix: dict[str, Counter[str]] = defaultdict(Counter)
    for row in test:
        prediction, _ = model.predict(row['title'], row['category'])
        matrix[row['product_type']][prediction] += 1
    total = sum(sum(counts.values()) for counts in matrix.values())
    correct = sum(matrix[label][label] for label in matrix)
    recalls = []
    for label in sorted(model.class_docs):
        actual = sum(matrix[label].values())
        recalls.append(matrix[label][label] / actual if actual else 0.0)
    return {
        'train_rows': len(train),
        'test_rows': len(test),
        'accuracy': round(correct / total, 4) if total else None,
        'balanced_accuracy': round(sum(recalls) / len(recalls), 4) if recalls else None,
        'confusion_matrix': {actual: dict(predicted) for actual, predicted in matrix.items()},
    }


def first_match(text: str, patterns: list[tuple[str, tuple[str, ...]]], default: str) -> str:
    for value, terms in patterns:
        if any(term in text for term in terms):
            return value
    return default


def derive_style(title: str, category: str) -> tuple[str, list[str]]:
    text = normalise_text(title, category)
    length = first_match(text, [
        ('连裤/打底', ('连裤', '打底裤', '踩脚')), ('过膝', ('过膝', '膝上', '大腿袜')),
        ('长筒', ('长筒', '高筒', '小腿袜', '压力袜')), ('中筒', ('中筒', '堆堆', '袜套')),
        ('船袜/隐形', ('船袜', '隐形', '浅口', '硅胶防滑')), ('短筒', ('短筒', '短袜')),
        ('五指袜', ('五指',)),
    ], '待补充')
    # 类目路径包含“女士内衣/男士内衣”等通用层级，性别/儿童不应由该
    # 路径触发；这些标签仅从商品标题判断。
    title_text = normalise_text(title)
    if any(term in title_text for term in ('儿童', '宝宝', '婴儿', '卡通', '亲子', '小孩')):
        style = '儿童卡通'
    elif any(term in title_text for term in ('商务', '正装', '男袜', '男款')):
        style = '商务基础'
    else:
        style = first_match(text, [
            ('运动机能', ('运动', '跑步', '网球', '骑行', '健身', '瑜伽', '羽毛球', '登山', '压力袜', '篮球', '足球')),
            ('甜美芭蕾', ('芭蕾', 'miu', '蝴蝶结', '蕾丝', '花边', '木耳', '爱心', '波点', '公主')),
            ('学院复古', ('学院', 'jk', '英伦', '复古', '日系', '韩系')),
            ('保暖家居', ('加绒', '保暖', '羊毛', '毛圈', '毛巾袜', '发热', '家居', '睡眠', '秋冬')),
            ('潮流设计', ('撞色', '彩色', '涂鸦', '字母', '网红', 'ins', '潮牌')),
        ], '基础通勤')
    season = first_match(text, [
        ('秋冬主推', ('秋冬', '冬季', '保暖', '加绒', '羊毛', '毛圈', '发热')),
        ('春夏主推', ('夏季', '夏天', '薄款', '冰丝', '网眼', '透气', '凉感', '防晒')),
    ], '四季基础')
    if any(term in title_text for term in ('儿童', '宝宝', '婴儿', '亲子', '小孩')):
        audience = '儿童'
    elif any(term in title_text for term in ('男女', '男/女', '男女士')):
        audience = '通用'
    else:
        audience = first_match(title_text, [
            ('男士', ('男士', '男袜', '男款', '青年男')),
            ('女士', ('女士', '女款', '女生', '女袜', '孕妇', '月子')),
        ], '通用')
    return style, [f'袜长:{length}', f'季节属性:{season}', f'人群:{audience}']


def derive_time_node(value: Any) -> str:
    date_value = parse_date(value)
    if not date_value:
        return '上架时间待补充'
    suffix = '春夏款' if 1 <= date_value.month <= 7 else '秋冬款'
    return f'{date_value.year}{suffix}'


def get_products(connection: sqlite3.Connection) -> list[dict[str, str]]:
    rows = connection.execute(
        'SELECT product_id, title, category, list_date, product_type, product_tags FROM products'
    ).fetchall()
    return [dict(row) for row in rows]


def classification_tag(product_type: str) -> str:
    return f'分类标签:{product_type}' if product_type in {'标品', '非标品'} else ''


def merge_tags(existing: str, additions: Iterable[str]) -> str:
    # Keep user-entered and existing style tags.  Replace only the managed
    # classification tag so re-running the sync remains idempotent.
    parts = [part.strip() for part in re.split(r'[｜|]', clean(existing)) if part.strip()]
    parts = [part for part in parts if not part.startswith('分类标签:')]
    for tag in additions:
        if tag and tag not in parts:
            parts.append(tag)
    return '｜'.join(parts)


def is_placeholder(value: Any) -> bool:
    return clean(value) in {'', '-', '—', '--', '暂无', '未知', '待补充'}


EXPLICIT_NONSTANDARD_TERMS = (
    # These terms are retained only where the reference workbook showed a
    # consistently non-standard label; broader fashion/season words are not
    # strong enough and therefore remain 待复核.
    '卡通', '亲子', '儿童', '宝宝', '婴儿', '压力袜', '蛇年', '礼盒', '结婚',
    '新年', '涂鸦', '毛巾袜', '潮牌',
)
EXPLICIT_STANDARD_TERMS = ('商务',)
SOCK_TERMS = ('袜', '袜子', '短袜', '中筒袜', '船袜', '隐形袜', '男袜', '女袜')



def derive_type_without_reference(title: str, category: str) -> tuple[str, str, float]:
    """Return only high-precision rule results; otherwise leave for review."""
    text = normalise_text(title, category)
    if not text or text in {'-', '--'}:
        return '待复核', '待人工复核', 0.0
    nonstandard = [term for term in EXPLICIT_NONSTANDARD_TERMS if term in text]
    if nonstandard:
        return '非标品', '标题规则高置信', 0.9
    standard = [term for term in EXPLICIT_STANDARD_TERMS if term in text]
    if standard and any(term in text for term in SOCK_TERMS):
        return '标品', '标题规则高置信', 0.85
    return '待复核', '待人工复核', 0.0


def build_enrichment(products: list[dict[str, str]], direct: dict[str, dict[str, str]], growth: dict[str, str]):
    updates = []
    provenance = Counter()
    type_counts = Counter()
    style_counts = Counter()
    time_counts = Counter()
    growth_counts = Counter()
    confidence_buckets = Counter()
    date_filled_count = 0
    for product in products:
        product_id = normalise_id(product['product_id'])
        source = direct.get(product_id)
        title = clean(product.get('title'))
        category = clean(product.get('category'))
        list_date = clean(product.get('list_date'))
        if source:
            product_type = source['product_type']
            classification_source = source['classification_source']
            confidence = 1.0
            if is_placeholder(category) and not is_placeholder(source.get('category')):
                category = source.get('category', '')
            if is_placeholder(list_date) and not is_placeholder(source.get('list_date')):
                list_date = source.get('list_date', '')
                date_filled_count += 1
        else:
            # The user requires this field to follow the Excel labels directly.
            # Products absent from the reference must not be guessed from title
            # keywords; retain their existing classification (or 待复核).
            product_type = clean(product.get('product_type')) or '待复核'
            classification_source = '保留原有分类' if product_type != '待复核' else '待人工复核'
            confidence = 1.0 if classification_source == '保留原有分类' else 0.0
        style, attribute_tags = derive_style(title, category)
        time_node = derive_time_node(list_date)
        growth_stage = growth.get(product_id, '')
        tags = [classification_tag(product_type), f'归类来源:{classification_source}', *attribute_tags]
        if classification_source == '待人工复核':
            tags.append('标品/非标品:待人工复核')
        elif classification_source == '标题规则高置信':
            tags.append('规则依据:标题/类目关键词')
        tags.append('款式属性来源:标题规则')
        updates.append({
            'product_id': product_id,
            'product_type': product_type,
            'style': style,
            'product_time_node': time_node,
            'product_growth_stage': growth_stage,
            'product_tags': merge_tags(clean(product.get('product_tags')), tags),
            'list_date': list_date,
            'category': category,
            'classification_source': classification_source,
            'confidence': round(confidence, 4),
        })
        provenance[classification_source] += 1
        type_counts[product_type] += 1
        style_counts[style] += 1
        time_counts[time_node] += 1
        growth_counts[growth_stage or '未获取DMP成长阶段'] += 1
        if source:
            confidence_buckets['Excel直接值'] += 1
        elif classification_source == '保留原有分类':
            confidence_buckets['保留原有分类'] += 1
        else:
            confidence_buckets['待人工复核'] += 1
    return updates, {
        'product_type_counts': dict(type_counts),
        'style_counts': dict(style_counts),
        'time_node_counts': dict(time_counts),
        'growth_stage_counts': dict(growth_counts),
        'classification_source_counts': dict(provenance),
        'confidence_buckets': dict(confidence_buckets),
        'reference_date_filled_count': date_filled_count,
        'model_validation': None,
    }


def ensure_schema(connection: sqlite3.Connection) -> None:
    columns = {row['name'] for row in connection.execute('PRAGMA table_info(products)').fetchall()}
    if 'product_time_node' not in columns:
        connection.execute("ALTER TABLE products ADD COLUMN product_time_node TEXT DEFAULT ''")
    connection.execute('CREATE INDEX IF NOT EXISTS idx_products_product_type ON products(product_type)')
    connection.execute('CREATE INDEX IF NOT EXISTS idx_products_product_time_node ON products(product_time_node)')
    connection.execute('CREATE INDEX IF NOT EXISTS idx_products_product_growth_stage ON products(product_growth_stage)')


def apply_updates(connection: sqlite3.Connection, updates: list[dict[str, Any]]) -> int:
    connection.executemany("""
        UPDATE products
           SET product_type = ?,
               style = ?,
               product_time_node = ?,
               product_growth_stage = ?,
               product_tags = ?,
               list_date = CASE WHEN TRIM(COALESCE(list_date, '')) IN ('', '-', '—', '--', '暂无', '未知', '待补充') THEN ? ELSE list_date END,
               category = CASE WHEN TRIM(COALESCE(category, '')) IN ('', '-', '—', '--', '暂无', '未知', '待补充') THEN ? ELSE category END,
               updated_at = CURRENT_TIMESTAMP
         WHERE product_id = ?
    """, [
        (row['product_type'], row['style'], row['product_time_node'], row['product_growth_stage'],
         row['product_tags'], row['list_date'], row['category'], row['product_id'])
        for row in updates
    ])
    return len(updates)


def main() -> int:
    parser = argparse.ArgumentParser(description='用标品货品参考表补充商品分类、款式和款期')
    parser.add_argument('--workbook', type=Path, default=DEFAULT_WORKBOOK)
    parser.add_argument('--database', type=Path, default=DEFAULT_DB)
    parser.add_argument('--report', type=Path, default=DEFAULT_REPORT)
    parser.add_argument('--apply', action='store_true', help='实际写入数据库；默认仅生成预览报告')
    args = parser.parse_args()
    if not args.workbook.exists():
        raise FileNotFoundError(f'参考文件不存在：{args.workbook}')
    if not args.database.exists():
        raise FileNotFoundError(f'数据库不存在：{args.database}')

    direct, growth = read_reference(args.workbook)
    connection = sqlite3.connect(args.database)
    connection.row_factory = sqlite3.Row
    try:
        products = get_products(connection)
        updates, summary = build_enrichment(products, direct, growth)
        database_ids = {normalise_id(product['product_id']) for product in products}
        direct_match_ids = set(direct) & database_ids
        growth_match_ids = set(growth) & database_ids
        summary.update({
            'generated_at': dt.datetime.now().isoformat(timespec='seconds'),
            'as_of_date': AS_OF_DATE.isoformat(),
            'workbook': str(args.workbook),
            'database': str(args.database),
            'database_product_count': len(products),
            'excel_direct_type_rows': len(direct),
            'excel_direct_type_matched': len(direct_match_ids),
            'excel_direct_type_unmatched': len(set(direct) - database_ids),
            'excel_dmp_growth_rows': len(growth),
            'excel_dmp_growth_matched': len(growth_match_ids),
            'write_mode': 'apply' if args.apply else 'dry-run',
            'field_rules': {
                'product_type': '仅同步 Excel 分类表（数据 (2)、单品或汇总）中的归类；未匹配商品保留原有分类，空值才标为待复核，不使用标题关键词猜测。',
                'style': '标题/类目关键词推断的主风格。',
                'product_time_node': '按上架时间分为 YYYY春夏款（1-7月）或 YYYY秋冬款（8-12月）。',
                'product_growth_stage': '仅写入 Excel DMP 的原始货品成长阶段；无对应 DMP 记录则保持为空。',
                'product_tags': '写入可见的 分类标签:标品 / 分类标签:非标品，并保留原有标签、补充袜长、季节属性、人群和归类来源。',
            },
            'sample': updates[:10],
        })
        if args.apply:
            backup_dir = args.database.parent.parent / 'backups'
            backup_dir.mkdir(parents=True, exist_ok=True)
            stamp = dt.datetime.now().strftime('%Y%m%d-%H%M%S')
            backup_path = backup_dir / f'{args.database.stem}-before-product-classification-{stamp}{args.database.suffix}'
            connection.close()
            shutil.copy2(args.database, backup_path)
            connection = sqlite3.connect(args.database)
            connection.row_factory = sqlite3.Row
            ensure_schema(connection)
            written = apply_updates(connection, updates)
            connection.commit()
            summary['backup'] = str(backup_path)
            summary['updated_rows'] = written
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    finally:
        connection.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())