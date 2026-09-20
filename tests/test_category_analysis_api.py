# -*- coding: utf-8 -*-
"""Contract tests for the category period analysis API.

These tests intentionally describe the v1 contract from
CATEGORY_ANALYSIS_IMPLEMENTATION.md.  They use an isolated SQLite database and
do not depend on production data or frontend code.
"""
import os
import sys
import tempfile
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class CategoryAnalysisApiContractTests(unittest.TestCase):
    endpoint = "/api/category-analysis/compare"

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="tmall-dashboard-category-analysis-")
        from app import create_app
        from db import get_db

        self.database_path = os.path.join(self.temp.name, "dashboard.db")
        self.app = create_app({"TESTING": True, "DATABASE_PATH": self.database_path})
        self.client = self.app.test_client()

        with get_db(self.database_path) as db:
            db.executemany(
                "INSERT INTO products (product_id, title, status, shop_label) VALUES (?, ?, ?, ?)",
                [
                    ("sock-a", "Sock A", "active", "标品袜子"),
                    ("sock-b", "Sock B", "active", "标品袜子,畅销商品"),
                    ("other-a", "Other A", "active", "内裤"),
                ],
            )
            # Daily facts cover arbitrary ranges, partial periods, and cross-year
            # comparisons.  Values are deliberately asymmetric for aggregation checks.
            db.executemany(
                """INSERT INTO daily_data
                   (product_id, date, payment_amount, refund_amount, net_sales,
                    payment_qty, ipv, buyers, ad_spend)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    ("sock-a", "2025-12-31", 100, 10, 90, 2, 10, 1, 5),
                    ("sock-a", "2026-01-01", 200, 20, 180, 4, 20, 2, 10),
                    ("sock-b", "2026-01-02", 300, 30, 270, 6, 30, 3, 15),
                    ("sock-a", "2026-09-14", 400, 40, 360, 8, 40, 4, 20),
                    ("sock-b", "2026-09-15", 600, 60, 540, 12, 60, 6, 30),
                    ("sock-a", "2025-09-15", 250, 25, 225, 5, 25, 2, 12),
                    ("sock-b", "2025-09-16", 350, 35, 315, 7, 35, 3, 18),
                    ("other-a", "2026-09-15", 999, 0, 999, 9, 90, 9, 0),
                ],
            )
            # Monthly and weekly rows ensure the contract accepts all supported
            # grains even when an implementation chooses native rollups.
            db.executemany(
                "INSERT INTO monthly_data (product_id, month, payment_amount, refund_amount, net_sales, visitors, buyers, ad_spend) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    ("sock-a", "2025-09", 250, 25, 225, 25, 2, 12),
                    ("sock-b", "2025-09", 350, 35, 315, 35, 3, 18),
                    ("sock-a", "2026-09", 1000, 100, 900, 100, 10, 50),
                ],
            )
            db.executemany(
                "INSERT INTO weekly_data (product_id, week_start, payment_amount, refund_amount, net_sales, ipv, ad_spend) VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    ("sock-a", "2025-09-15", 250, 25, 225, 25, 12),
                    ("sock-b", "2025-09-15", 350, 35, 315, 35, 18),
                    ("sock-a", "2026-09-14", 400, 40, 360, 40, 20),
                    ("sock-b", "2026-09-14", 600, 60, 540, 60, 30),
                ],
            )
            db.commit()

    def tearDown(self):
        self.temp.cleanup()

    def get_json(self, query):
        response = self.client.get(f"{self.endpoint}?{query}")
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        payload = response.get_json()
        self.assertIn("data", payload)
        return payload["data"]

    def test_day_grain_supports_custom_range_and_category_filter(self):
        data = self.get_json(
            "category_mode=sock&grain=day&start=2026-01-01&end=2026-01-02&metric=payment_amount"
        )
        self.assertEqual(data["grain"], "day")
        self.assertEqual(data["category"]["value"], "sock")
        self.assertEqual(data["current_period"]["value"], 500)
        self.assertEqual(data["current_period"]["days"], 2)

    def test_week_grain_normalizes_to_monday_sunday_and_returns_partial_status(self):
        data = self.get_json(
            "category_mode=sock&grain=week&start=2026-09-14&end=2026-09-20&metric=payment_amount"
        )
        self.assertEqual(data["grain"], "week")
        self.assertEqual(data["current_period"]["start"], "2026-09-14")
        self.assertEqual(data["current_period"]["end"], "2026-09-20")
        self.assertTrue(data["data_quality"]["is_partial_period"])

    def test_month_grain_supports_year_over_year_comparison(self):
        data = self.get_json(
            "category_mode=sock&grain=month&start=2026-09-01&end=2026-09-30&"
            "compare_mode=yoy&compare_start=2025-09-01&compare_end=2025-09-30&metric=payment_amount"
        )
        self.assertEqual(data["grain"], "month")
        self.assertEqual(data["current_period"]["value"], 1000)
        self.assertEqual(data["compare_period"]["value"], 600)
        self.assertEqual(data["change"]["amount"], 400)
        self.assertAlmostEqual(data["change"]["rate"], 2 / 3)

    def test_custom_comparison_exposes_mom_and_cross_year_periods(self):
        data = self.get_json(
            "category_mode=sock&grain=day&start=2026-01-01&end=2026-01-02&"
            "compare_mode=custom&compare_start=2025-12-31&compare_end=2025-12-31&metric=net_sales"
        )
        self.assertEqual(data["current_period"]["value"], 450)
        self.assertEqual(data["compare_period"]["value"], 90)
        self.assertEqual(data["change"]["amount"], 360)
        self.assertEqual(data["current_period"]["daily_average"], 225)

    def test_missing_period_is_null_not_zero_and_reports_partial_availability(self):
        data = self.get_json(
            "category_mode=sock&grain=day&start=2099-01-01&end=2099-01-02&"
            "compare_mode=custom&compare_start=2026-01-01&compare_end=2026-01-02&metric=payment_amount"
        )
        self.assertIsNone(data["current_period"]["value"])
        self.assertEqual(data["data_quality"]["availability"], "partial")

    def test_zero_baseline_is_not_divided_by(self):
        data = self.get_json(
            "category_mode=sock&grain=day&start=2026-01-01&end=2026-01-01&"
            "compare_mode=custom&compare_start=2025-01-01&compare_end=2025-01-01&metric=payment_amount"
        )
        self.assertIsNone(data["change"]["rate"])

    def test_profit_metric_returns_breakdown_and_missing_fields(self):
        data = self.get_json(
            "category_mode=sock&grain=day&start=2026-01-01&end=2026-01-02&metric=operating_profit"
        )
        self.assertIn("profit_breakdown", data)
        self.assertIn("operating_profit", data["profit_breakdown"])
        self.assertEqual(data["data_quality"]["availability"], "partial")
        self.assertIn("product_cost", data["data_quality"]["missing_fields"])

    def test_all_category_mode_includes_other_products(self):
        data = self.get_json(
            "category_mode=all&grain=day&start=2026-09-15&end=2026-09-15&metric=payment_amount"
        )
        # 2026-09-15 contains sock-b (600) and other-a (999); sock-a has no
        # fact on that date, so the all-category total is 1599.
        self.assertEqual(data["current_period"]["value"], 1599)

    def test_invalid_grain_metric_category_and_dates_are_rejected(self):
        queries = [
            "grain=quarter&start=2026-01-01&end=2026-01-02",
            "grain=day&metric=not_a_metric&start=2026-01-01&end=2026-01-02",
            "grain=day&compare_mode=not-a-mode&start=2026-01-01&end=2026-01-02",
            "grain=day&start=2026-02-30&end=2026-03-01",
            "grain=day&start=2026-01-03&end=2026-01-02",
        ]
        for query in queries:
            with self.subTest(query=query):
                response = self.client.get(f"{self.endpoint}?{query}")
                self.assertEqual(response.status_code, 422, response.get_data(as_text=True))
                self.assertEqual(response.get_json()["code"], "VALIDATION_ERROR")

    def test_compare_period_requires_valid_order_and_dates(self):
        response = self.client.get(
            f"{self.endpoint}?grain=day&start=2026-01-01&end=2026-01-02&"
            "compare_mode=custom&compare_start=2026-01-03&compare_end=2026-01-02"
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.get_json()["code"], "VALIDATION_ERROR")

    def test_matrix_returns_multi_year_month_rows_and_product_titles(self):
        response = self.client.get(
            f"{self.endpoint.replace('/compare', '/matrix')}?category_mode=sock&"
            "years=2025,2026&metric=payment_amount"
        )
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        data = response.get_json()["data"]
        self.assertEqual(data["years"], [2025, 2026])
        january = next(row for row in data["matrix"] if row["month"] == 1)
        self.assertEqual(january["values"]["2026"], 500)
        self.assertEqual(january["values"]["2025"], None)
        self.assertEqual(data["annual"]["2026"], 1500)

        comparison = self.get_json(
            "category_mode=sock&grain=month&start=2026-01-01&end=2026-01-02&"
            "compare_mode=custom&compare_start=2025-12-31&compare_end=2025-12-31&metric=payment_amount"
        )
        self.assertEqual(comparison["contributors"]["up"][0]["title"], "Sock B")


class CategoryCostContractTests(unittest.TestCase):
    """成本/利润口径契约。

    回归背景：成本列（product_cost / sales_cost / custom_cost / logistics_cost /
    other_cost）缺失时，旧实现把它们按 0 累加，「经营利润」退化成
    净销售额 − 推广花费，把亏损品类显示成 76% 利润率的品类。
    """

    endpoint = "/api/category-analysis/compare"

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="tmall-dashboard-category-cost-")
        from app import create_app
        from db import get_db

        self.database_path = os.path.join(self.temp.name, "dashboard.db")
        self.app = create_app({"TESTING": True, "DATABASE_PATH": self.database_path})
        self.client = self.app.test_client()

        with get_db(self.database_path) as db:
            db.executemany(
                "INSERT INTO products (product_id, title, status, shop_label) VALUES (?, ?, ?, ?)",
                [("cost-bi", "Cost BI", "active", "标品袜子"),
                 ("cost-derived", "Cost Derived", "active", "标品袜子"),
                 ("cost-none", "Cost None", "active", "标品袜子")],
            )
            # 三个商品刻意分在三天，便于按日隔离断言。
            # cost-bi：成本齐全 + BI 利润列存在（460），且与公式推导值(450)不同，
            #          用来证明 BI 列优先。
            db.execute(
                """INSERT INTO daily_data
                   (shop_id, product_id, date, payment_amount, net_sales, ipv, buyers, ad_spend,
                    product_cost, sales_cost, custom_cost, logistics_cost, other_cost,
                    operating_profit, profit_rate)
                   VALUES ('3828498662', 'cost-bi', '2026-08-10', 1200, 1000, 100, 10, 200,
                           300, 150, 50, 40, 10, 460, 0.46)"""
            )
            # cost-derived：成本齐全但没有 BI 利润列，应由公式推导出 450。
            db.execute(
                """INSERT INTO daily_data
                   (shop_id, product_id, date, payment_amount, net_sales, ipv, buyers, ad_spend,
                    product_cost, sales_cost, custom_cost, logistics_cost, other_cost)
                   VALUES ('3828498662', 'cost-derived', '2026-08-11', 1200, 1000, 100, 10, 200,
                           300, 150, 50, 40, 10)"""
            )
            # cost-none：完全没有成本数据。
            db.execute(
                """INSERT INTO daily_data
                   (shop_id, product_id, date, payment_amount, net_sales, ipv, buyers, ad_spend)
                   VALUES ('3828498662', 'cost-none', '2026-08-12', 1200, 1000, 100, 10, 200)"""
            )
            db.commit()

    def tearDown(self):
        self.temp.cleanup()

    def data(self, query):
        response = self.client.get(f"{self.endpoint}?{query}")
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        return response.get_json()["data"]

    def test_bi_profit_column_wins_over_derived_formula(self):
        data = self.data("category_mode=sock&grain=day&start=2026-08-10&end=2026-08-10&metric=operating_profit")
        self.assertEqual(data["profit_breakdown"]["basis"], "bi")
        self.assertEqual(data["profit_breakdown"]["operating_profit"], 460)
        self.assertEqual(data["current_period"]["value"], 460)

    def test_verified_formula_derives_profit_when_bi_column_absent(self):
        data = self.data("category_mode=sock&grain=day&start=2026-08-11&end=2026-08-11&metric=operating_profit")
        self.assertEqual(data["profit_breakdown"]["basis"], "derived")
        # 1000 − 300 − 150 − 50 − 40 − 10
        self.assertEqual(data["profit_breakdown"]["operating_profit"], 450)

    def test_missing_cost_never_degrades_into_net_sales_minus_ad_spend(self):
        data = self.data("category_mode=sock&grain=day&start=2026-08-12&end=2026-08-12&metric=operating_profit")
        self.assertIsNone(data["profit_breakdown"]["operating_profit"])
        self.assertIsNone(data["profit_breakdown"]["operating_profit_rate"])
        self.assertIsNone(data["current_period"]["value"])
        self.assertIsNone(data["profit_breakdown"]["basis"])
        # 这正是旧实现会返回的假利润，必须不再出现。
        self.assertNotEqual(data["current_period"]["value"], 1000 - 200)
        self.assertIn("product_cost", data["profit_breakdown"]["missing_fields"])

    def test_breakdown_reports_basis_and_missing_fields_for_frontend(self):
        data = self.data("category_mode=sock&grain=day&start=2026-08-12&end=2026-08-12&metric=net_sales")
        self.assertFalse(data["profit_breakdown"]["is_complete"])
        self.assertIn("product_cost", data["cost_labels"])
        self.assertEqual(data["cost_labels"]["product_cost"], "净货品成本")

    def test_data_quality_exposes_coverage_end_and_server_today(self):
        data = self.data("category_mode=sock&grain=day&start=2026-08-01&end=2026-08-31&metric=net_sales")
        quality = data["data_quality"]
        # 请求区间右端晚于库内最新数据，必须收敛到真实最后一天。
        self.assertEqual(quality["coverage_end"], "2026-08-12")
        self.assertEqual(quality["requested_end"], "2026-08-31")
        self.assertIsNotNone(quality["server_today"])

    def test_compare_trend_is_returned_for_the_compare_period(self):
        data = self.data(
            "category_mode=sock&grain=day&start=2026-08-12&end=2026-08-12&"
            "compare_mode=custom&compare_start=2026-08-10&compare_end=2026-08-10&metric=net_sales"
        )
        self.assertEqual(len(data["trend"]), 1)
        self.assertEqual(len(data["compare_trend"]), 1)
        self.assertEqual(data["compare_trend"][0]["value"], 1000)


if __name__ == "__main__":
    unittest.main(verbosity=2)
