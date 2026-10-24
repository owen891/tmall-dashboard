"""潜客补数（promotion_lead_daily → 商品列表 guide_* 字段）的口径护栏。

覆盖：
- 占比必须用 SUM(潜客数)/SUM(入店访客) 重算，不能对日比率取平均；
- 窗口取交集，部分覆盖要如实披露，完全无交集不回填；
- 只填 NULL，不覆盖主源已有值；
- 行里没有的列不能凭空加键（导出只挑几列时会错位）。
"""

import sqlite3
import unittest

from services.lead_item_metrics_enrichment import (
    FILLABLE_FIELDS,
    enrich_rows,
    resolve_window,
    source_metadata,
)


DDL = '''
CREATE TABLE promotion_lead_daily (
    shop_id TEXT,
    date TEXT,
    product_id TEXT,
    inshop_uv INTEGER,
    potential_uv INTEGER,
    potential_uv_rate REAL,
    ad_spend REAL,
    ad_pv INTEGER,
    clicks INTEGER,
    payment_amount REAL,
    payment_orders INTEGER,
    cart_adds INTEGER,
    source_batch_id TEXT,
    fetched_at TEXT,
    PRIMARY KEY (shop_id, date, product_id)
)
'''


def _conn():
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    conn.execute(DDL)
    return conn


def _insert(conn, day, product_id, inshop_uv, potential_uv, rate=None):
    if rate is None and inshop_uv:
        rate = round(potential_uv / inshop_uv, 6)
    conn.execute(
        'INSERT INTO promotion_lead_daily '
        '(shop_id, date, product_id, inshop_uv, potential_uv, potential_uv_rate) '
        "VALUES ('default', ?, ?, ?, ?, ?)",
        (day, product_id, inshop_uv, potential_uv, rate),
    )


def _row(product_id, **overrides):
    """模拟 API 查询出来的行：guide_* 三列存在但为 NULL。"""
    row = {'product_id': product_id, 'guide_visitors': None,
           'guide_potential': None, 'guide_potential_ratio': None}
    row.update(overrides)
    return row


class LeadEnrichmentTest(unittest.TestCase):
    def test_ratio_uses_sum_of_numerator_over_sum_of_denominator(self):
        conn = _conn()
        # 两天日比率分别是 1.0 和 0.0，平均是 0.5；
        # 但正确口径是 (10+0)/(10+90) = 0.1。
        _insert(conn, '2026-10-12', 'p1', 10, 10)
        _insert(conn, '2026-10-13', 'p1', 90, 0)
        rows = [_row('p1')]
        result = enrich_rows(conn, rows, '2026-10-12', '2026-10-13')
        self.assertTrue(result['applied'])
        self.assertEqual(rows[0]['guide_visitors'], 100)
        self.assertEqual(rows[0]['guide_potential'], 10)
        self.assertAlmostEqual(rows[0]['guide_potential_ratio'], 0.1)

    def test_partial_window_is_reported(self):
        conn = _conn()
        _insert(conn, '2026-10-12', 'p1', 10, 2)
        window = resolve_window(conn, '2026-09-23', '2026-10-22')
        self.assertIsNotNone(window)
        self.assertFalse(window['full'])
        self.assertEqual(window['start'], '2026-10-12')
        self.assertEqual(window['end'], '2026-10-12')
        self.assertEqual(window['requested_days'], 30)
        self.assertEqual(window['covered_days'], 1)

    def test_no_overlap_does_not_enrich(self):
        conn = _conn()
        _insert(conn, '2026-10-12', 'p1', 10, 2)
        rows = [_row('p1')]
        result = enrich_rows(conn, rows, '2026-08-01', '2026-08-31')
        self.assertFalse(result['applied'])
        self.assertIsNone(rows[0]['guide_potential'])

    def test_only_fills_nulls(self):
        conn = _conn()
        _insert(conn, '2026-10-12', 'p1', 10, 2)
        rows = [_row('p1', guide_potential=999)]
        enrich_rows(conn, rows, '2026-10-12', '2026-10-12')
        self.assertEqual(rows[0]['guide_potential'], 999)

    def test_missing_column_is_not_added(self):
        conn = _conn()
        _insert(conn, '2026-10-12', 'p1', 10, 2)
        rows = [{'product_id': 'p1', 'guide_potential': None}]
        enrich_rows(conn, rows, '2026-10-12', '2026-10-12')
        self.assertNotIn('guide_visitors', rows[0])
        self.assertNotIn('guide_potential_ratio', rows[0])

    def test_product_without_lead_rows_stays_null(self):
        conn = _conn()
        _insert(conn, '2026-10-12', 'p1', 10, 2)
        rows = [_row('p1'), _row('p2')]
        enrich_rows(conn, rows, '2026-10-12', '2026-10-12')
        self.assertEqual(rows[0]['guide_potential'], 2)
        self.assertIsNone(rows[1].get('guide_potential'))

    def test_zero_denominator_yields_null_ratio(self):
        conn = _conn()
        _insert(conn, '2026-10-12', 'p1', 0, 0)
        rows = [_row('p1')]
        enrich_rows(conn, rows, '2026-10-12', '2026-10-12')
        self.assertEqual(rows[0]['guide_visitors'], 0)
        self.assertIsNone(rows[0]['guide_potential_ratio'])

    def test_source_metadata_discloses_window(self):
        conn = _conn()
        _insert(conn, '2026-10-12', 'p1', 10, 2)
        rows = [_row('p1')]
        result = enrich_rows(conn, rows, '2026-09-23', '2026-10-22')
        meta = source_metadata(result)
        self.assertEqual(meta['source'], 'promotion_lead_daily')
        self.assertEqual(meta['grain'], 'product_day')
        self.assertFalse(meta['full_window'])
        self.assertEqual(meta['covered_days'], 1)
        self.assertEqual(tuple(meta['fields']), FILLABLE_FIELDS)

    def test_missing_table_is_tolerated(self):
        conn = sqlite3.connect(':memory:')
        conn.row_factory = sqlite3.Row
        rows = [_row('p1')]
        result = enrich_rows(conn, rows, '2026-10-12', '2026-10-12')
        self.assertFalse(result['applied'])


if __name__ == '__main__':
    unittest.main()
