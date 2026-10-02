"""市场监控深化计算（market_monitor_service）单元测试。

覆盖 XMind 市场监控缺口的四项能力：8大归类 / 蓝海机会词 / 趋势节点 / 竞店爆品排名变化。
全部用合成数据驱动，不依赖采集库。
"""
import os
import sys
import unittest
from datetime import date, timedelta

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from services.market_monitor_service import (
    _classify_keyword,
    keyword_insights,
    rival_item_moves,
)


def _rows(days, per_day):
    """构造 [(stat_date, keyword, search_heat, pay_rate, click_rate)] 升序行。"""
    start = date(2026, 9, 1)
    rows = []
    for index in range(days):
        stat_date = (start + timedelta(days=index)).isoformat()
        for keyword, heat, pay_rate in per_day(index):
            rows.append((stat_date, keyword, heat, pay_rate, 0.1))
    return rows


class KeywordClassificationTests(unittest.TestCase):
    def test_eight_categories_and_fallback(self):
        cases = {
            '蕉内袜子': 'brand',
            '袜子男款': 'crowd',
            '儿童袜': 'crowd',
            '压力袜': 'function',
            '秋冬袜子': 'scene',
            '堆堆袜': 'style',
            '纯棉袜子': 'attribute',
            '特价团': 'price',
            '中筒袜': 'category',
            '黑丝': 'category',
            '神秘词xyz': 'other',
        }
        for keyword, expected in cases.items():
            self.assertEqual(_classify_keyword(keyword), expected, keyword)


class KeywordInsightsTests(unittest.TestCase):
    def test_windows_classification_and_blue_ocean_filtering(self):
        # 30 天：steady 词每天热度 100；泛词「袜子」热度 1000（不得进蓝海）。
        def per_day(index):
            return [
                ('steady词', 100, 0.10),
                ('袜子', 1000, 0.20),
                ('无转化词', 500, None),
            ]
        rows = _rows(30, per_day)
        result = keyword_insights('2026-09-01', '2026-09-30', rows)

        self.assertTrue(result['available'])
        self.assertEqual(result['window']['day_count'], 30)
        self.assertEqual(result['recent_window']['day_count'], 7)
        self.assertEqual(result['baseline_window']['day_count'], 23)

        # 归类：全量关键词都应归入 8 大类或其他，占比合计≈1。
        share_sum = sum(cat['heat_share'] for cat in result['categories'])
        self.assertAlmostEqual(share_sum, 1.0, places=4)
        labels = {cat['label'] for cat in result['categories']}
        self.assertIn('其他', labels)

        # 蓝海：泛词剔除；无转化率的词剔除。
        blue_keywords = [item['keyword'] for item in result['blue_ocean']]
        self.assertIn('steady词', blue_keywords)
        self.assertNotIn('袜子', blue_keywords)
        self.assertNotIn('无转化词', blue_keywords)
        # limitation 必须说明供给覆盖未采集（SKILL 完整口径的差距）。
        self.assertTrue(any('供给覆盖' in item for item in result['limitations']))

    def test_trend_nodes_detect_rising_and_cooling(self):
        # 前 23 天热度 100，近 7 天：起势词 300（+200%）、退势词 20（-80%）、平稳词 105。
        def per_day(index):
            if index < 23:
                return [('起势词', 100, 0.1), ('退势词', 100, 0.1), ('平稳词', 100, 0.1)]
            return [('起势词', 300, 0.1), ('退势词', 20, 0.1), ('平稳词', 105, 0.1)]
        rows = _rows(30, per_day)
        result = keyword_insights('2026-09-01', '2026-09-30', rows)

        rising = {item['keyword']: item['growth'] for item in result['trend_nodes']['rising']}
        cooling = {item['keyword']: item['growth'] for item in result['trend_nodes']['cooling']}
        self.assertAlmostEqual(rising['起势词'], 2.0, places=2)
        self.assertAlmostEqual(cooling['退势词'], -0.8, places=2)
        self.assertNotIn('平稳词', rising)
        self.assertNotIn('平稳词', cooling)

    def test_empty_rows_report_missing_inputs(self):
        result = keyword_insights('2026-09-01', '2026-09-30', [])
        self.assertFalse(result['available'])
        self.assertIn('sycm_market_search_rank', result['missing_inputs'])
        self.assertEqual(result['categories'], [])


class RivalItemMovesTests(unittest.TestCase):
    def _rows(self):
        start = date(2026, 9, 1)
        def day(offset):
            return (start + timedelta(days=offset)).isoformat()
        rows = []
        # 上升：前 7 天 #10、后 7 天 #5；下降：前 7 天 #5、后 7 天 #10。
        for offset in range(14):
            rows.append((day(offset), 'A', '上升商品', '竞店甲', 10 if offset < 7 else 5, 0, 100, 10))
            rows.append((day(offset), 'B', '下降商品', '竞店甲', 5 if offset < 7 else 10, 0, 200, 20))
        rows.append((day(13), 'C', '新进榜商品', '竞店甲', 3, 0, 300, 30))
        rows.append((day(0), 'D', '退出商品', '竞店甲', 7, 0, 50, 5))
        # 自家商品不计入竞店口径。
        for offset in range(14):
            rows.append((day(offset), 'E', '本店商品', '本店', 1, 1, 999, 999))
        return sorted(rows, key=lambda item: (item[0], item[4]))

    def test_moves_classification_excludes_self_and_unseen_shops(self):
        result = rival_item_moves('2026-09-01', '2026-09-14', self._rows())

        self.assertTrue(result['available'])
        shop = next(item for item in result['shops'] if item['shop_name'] == '竞店甲')
        self.assertEqual(shop['item_count'], 4)
        self.assertEqual(shop['rising_count'], 1)
        self.assertEqual(shop['falling_count'], 1)
        self.assertEqual(shop['new_count'], 1)
        self.assertEqual(shop['exit_count'], 1)
        self.assertEqual(shop['rising'][0]['rank_change'], 5)
        self.assertEqual(shop['falling'][0]['rank_change'], -5)
        self.assertEqual(shop['new_items'][0]['rank'], 3)
        self.assertEqual(shop['exit_items'][0]['rank'], 7)
        # 本店商品不在竞店名单里。
        self.assertFalse(any(item['shop_name'] == '本店' for item in result['shops']))

    def test_empty_rows_report_missing_inputs(self):
        result = rival_item_moves('2026-09-01', '2026-09-14', [])
        self.assertFalse(result['available'])
        self.assertIn('sycm_market_item_rank', result['missing_inputs'])


if __name__ == '__main__':
    unittest.main()
