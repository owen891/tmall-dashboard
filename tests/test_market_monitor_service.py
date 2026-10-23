"""市场监控深化计算（market_monitor_service）单元测试。

覆盖 XMind 市场监控缺口的五项能力：8大归类 / 蓝海机会词 / 趋势节点 /
竞店爆品排名变化 / 商品排行趋势市场。全部用合成数据驱动，不依赖采集库。
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
    blue_ocean_words,
    classify_keyword,
    keyword_insights,
    rival_item_moves,
    trend_items,
)

# 测试词典：归类逻辑用中性词自包含验证，不依赖私有运营词表
# （data/market_monitor_lexicon.json 随私人部署分发，公开环境词典为空）。
import services.market_monitor_service as _market_monitor

TEST_GENERIC_KEYWORDS = frozenset({'泛品', 'generic'})
TEST_KEYWORD_RULES = (
    ('brand', '品牌', ('甲牌',)),
    ('crowd', '人群', ('男款', '儿童款')),
    ('function', '功能', ('加压型',)),
    ('scene', '场景', ('秋冬季',)),
    ('style', '风格', ('褶饰款',)),
    ('attribute', '属性', ('纯麻质',)),
    ('price', '价格', ('特价',)),
    ('category', '类目', ('筒装式', '丝光款', '板式装')),
)
_market_monitor.GENERIC_KEYWORDS = TEST_GENERIC_KEYWORDS
_market_monitor.KEYWORD_RULES = TEST_KEYWORD_RULES
_market_monitor.KEYWORD_CATEGORY_LABELS = {
    key: label for key, label, _ in TEST_KEYWORD_RULES
} | {'other': '其他'}


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
            '甲牌筒装式': 'brand',
            '筒装式男款': 'crowd',
            '筒装式儿童款': 'crowd',
            '加压型': 'function',
            '秋冬季筒装式': 'scene',
            '褶饰款筒装式': 'style',
            '纯麻质筒装式': 'attribute',
            '特价团': 'price',
            '筒装式': 'category',
            '丝光款': 'category',
            '神秘词xyz': 'other',
        }
        for keyword, expected in cases.items():
            self.assertEqual(_classify_keyword(keyword), expected, keyword)


class KeywordInsightsTests(unittest.TestCase):
    def test_windows_classification_and_blue_ocean_filtering(self):
        # 30 天：steady 词每天热度 100；泛词「泛品」热度 1000（不得进蓝海）。
        def per_day(index):
            return [
                ('steady词', 100, 0.10),
                ('泛品', 1000, 0.20),
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
        self.assertNotIn('泛品', blue_keywords)
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


class BlueOceanFullTests(unittest.TestCase):
    def test_cover_per_10k_and_grade(self):
        """SKILL 完整口径：词根级覆盖（在榜 title 含词根）→ 每万覆盖分级。"""
        rows = [
            ('2026-09-28', '加压型', 500, 0.1, 0.2),
            ('2026-09-28', '加压型秋冬季新选', 300, 0.1, 0.2),
            ('2026-09-28', '泛品', 100000, 0.2, 0.3),
            ('2026-09-28', '低热词', 50, 0.1, 0.2),
        ]
        titles = ['加压型男', '加压型女', '无关商品']
        result = blue_ocean_words(rows, titles)

        self.assertTrue(result['available'])
        by_word = {item['keyword']: item for item in result['words']}
        # 泛词（泛品）与低热词剔除。
        self.assertNotIn('泛品', by_word)
        self.assertNotIn('低热词', by_word)
        # 长尾组合「加压型秋冬季新选」聚合到词根「加压型」：热度取代表词，
        # 覆盖按词根匹配（2 款在榜含「加压型」）。
        self.assertIn('加压型', by_word)
        self.assertEqual(by_word['加压型']['cover_count'], 2)
        self.assertEqual(by_word['加压型']['grade'], '供给偏多')

    def test_root_level_matching_not_full_keyword(self):
        """长尾组合词不单独算覆盖——在榜样本不会原样包含长尾词。"""
        rows = [('2026-09-28', '加压型男夏季薄款', 800, 0.1, 0.2)]
        titles = ['加压型男士透气', '加压型女', '运动款']
        result = blue_ocean_words(rows, titles)
        self.assertTrue(result['available'])
        word = result['words'][0]
        # 匹配单位是词根「加压型」，非完整长尾词（完整词匹配会得 0）。
        self.assertEqual(word['keyword'], '加压型')
        self.assertEqual(word['keyword_full'], '加压型男夏季薄款')
        self.assertEqual(word['cover_count'], 2)

    def test_zero_cover_is_pending_not_blue_ocean(self):
        """覆盖 0 **不等于**供给稀缺，必须记「待核」而不是「高潜蓝海」。

        事故背景：在榜样本只有最新日 600 款（5 类目 × top120），词根与标题用词
        不一致时（「加固词」「款型词」标题里基本没人这么写）覆盖也是 0。
        旧实现把 0 直接判「高潜蓝海」→ 实测 12 个词根里 8 个覆盖为 0、全判高潜蓝海，
        分级塌成一档，对运营是误导（会去追一个并不存在的蓝海）。
        """
        rows = [('2026-09-28', '板式装秋冬季', 200, 0.1, 0.2)]
        result = blue_ocean_words(rows, ['完全无关商品'])
        self.assertTrue(result['available'])
        word = result['words'][0]
        self.assertEqual(word['keyword'], '板式装')
        self.assertEqual(word['cover_count'], 0)
        self.assertEqual(word['cover_per_10k'], 0.0)
        self.assertEqual(word['grade'], '待核')
        self.assertIsNotNone(word['note'])

    def test_missing_titles_ranks_pending_and_reports_counts(self):
        """完全没有在榜 title 时，所有词根都不可判供给 → 全「待核」，且计数如实回报。"""
        rows = [('2026-09-28', '加压型', 500, 0.1, 0.2)]
        result = blue_ocean_words(rows, [])
        self.assertTrue(result['available'])
        word = result['words'][0]
        self.assertEqual(word['cover_count'], 0)
        self.assertEqual(word['grade'], '待核')
        self.assertEqual(result['graded_count'], 0)
        self.assertEqual(result['pending_count'], 1)

    def test_graded_words_rank_before_pending(self):
        """已分级词排在「待核」之前 —— 待核不是结论，不该占榜首。"""
        rows = [
            ('2026-09-28', '加压型', 5000, 0.1, 0.2),   # 有覆盖 → 已分级
            ('2026-09-28', '板式装', 500, 0.1, 0.2),    # 无覆盖 → 待核
        ]
        titles = ['加压型男', '加压型女', '加压型儿童款', '加压型冬款', '加压型夏款',
                  '加压型薄款', '加压型厚款', '加压型透气款', '加压型运动款', '加压型防臭款',
                  '加压型保暖款', '加压型抗菌款', '加压型加长款', '加压型短款', '加压型礼盒款']
        result = blue_ocean_words(rows, titles)
        grades = [item['grade'] for item in result['words']]
        self.assertEqual(grades[0], '供给偏多')
        self.assertEqual(grades[-1], '待核')
        self.assertEqual(result['pending_count'], 1)


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

    def test_rows_may_carry_pic_url_as_ninth_column(self):
        """repo 已把 pic_url 加到行尾；8 列旧行仍需可用（容错解包）。"""
        rows = [(row[0], row[1], row[2], row[3], row[4], row[5], row[6], row[7],
                 f'https://img.example/{row[1]}.jpg') for row in self._rows()]

        result = rival_item_moves('2026-09-01', '2026-09-14', rows)

        shop = next(item for item in result['shops'] if item['shop_name'] == '竞店甲')
        self.assertEqual(shop['rising'][0]['pic_url'], 'https://img.example/A.jpg')
        self.assertEqual(shop['new_items'][0]['pic_url'], 'https://img.example/C.jpg')
        self.assertEqual(shop['exit_items'][0]['pic_url'], 'https://img.example/D.jpg')

    def test_missing_pic_url_falls_back_to_empty_string(self):
        result = rival_item_moves('2026-09-01', '2026-09-14', self._rows())

        shop = next(item for item in result['shops'] if item['shop_name'] == '竞店甲')
        self.assertEqual(shop['rising'][0]['pic_url'], '')

    def test_movers_cover_every_changed_item_sorted_by_magnitude(self):
        """页面要列出窗口内全部变动商品，不能只给前 N 条（旧版写死 6 行）。"""
        start = date(2026, 9, 1)
        rows = []
        for index in range(30):
            item_id = f'I{index:02d}'
            # 首日排名 index+1、末日排名再下移 (index%5)+1 名 → 全部为下降，幅度各不相同。
            for offset in range(14):
                rank = index + 1 + ((index % 5) + 1 if offset >= 7 else 0)
                rows.append(((start + timedelta(days=offset)).isoformat(), item_id,
                             f'商品{index}', '竞店乙', rank, 0, 100, 10))

        result = rival_item_moves('2026-09-01', '2026-09-14', rows)

        shop = next(item for item in result['shops'] if item['shop_name'] == '竞店乙')
        self.assertEqual(shop['movers_total'], 30)
        self.assertEqual(len(shop['movers']), 30)
        magnitudes = [abs(item['rank_change']) for item in shop['movers']]
        self.assertEqual(magnitudes, sorted(magnitudes, reverse=True))

    def test_unchanged_items_reported_separately_not_dropped(self):
        """排名没变的在榜商品进 stable/unchanged_count，不再静默丢弃。"""
        start = date(2026, 9, 1)
        rows = []
        for offset in range(14):
            day = (start + timedelta(days=offset)).isoformat()
            rows.append((day, 'S', '持平商品', '竞店丙', 8, 0, 100, 10))
            rows.append((day, 'R', '上升商品', '竞店丙', 10 if offset < 7 else 4, 0, 100, 10))

        result = rival_item_moves('2026-09-01', '2026-09-14', rows)

        shop = next(item for item in result['shops'] if item['shop_name'] == '竞店丙')
        self.assertEqual(shop['item_count'], 2)
        self.assertEqual(shop['unchanged_count'], 1)
        self.assertEqual(shop['stable'][0]['item_id'], 'S')
        self.assertEqual(shop['movers_total'], 1)


class TrendItemsTests(unittest.TestCase):
    """商品排行·趋势市场：与 rival_item_moves 同源（首尾对比），聚合维度换成商品。"""

    def _rows(self):
        start = date(2026, 9, 1)
        def day(offset):
            return (start + timedelta(days=offset)).isoformat()
        rows = []
        for offset in range(14):
            rows.append((day(offset), 'A', '上升商品', '甲店', 10 if offset < 7 else 3, 0, 100, 10))
            rows.append((day(offset), 'B', '下降商品', '乙店', 3 if offset < 7 else 10, 0, 200, 20))
        rows.append((day(13), 'C', '新进榜商品', '丙店', 2, 0, 300, 30))
        for offset in range(14):
            rows.append((day(offset), 'E', '本店商品', '本店', 1, 1, 999, 999))
        return sorted(rows, key=lambda item: (item[0], item[4]))

    def test_rising_and_new_exclude_self(self):
        result = trend_items('2026-09-01', '2026-09-14', self._rows())

        self.assertTrue(result['available'])
        self.assertEqual(result['rising_total'], 1)
        self.assertEqual(result['new_total'], 1)
        rising = result['rising'][0]
        self.assertEqual(rising['item_id'], 'A')
        self.assertEqual(rising['first_rank'], 10)
        self.assertEqual(rising['last_rank'], 3)
        self.assertEqual(rising['rank_change'], 7)
        self.assertEqual(result['new_items'][0]['item_id'], 'C')
        # 下降商品不进上升榜；本店不进趋势市场。
        self.assertFalse(any(item['item_id'] == 'B' for item in result['rising']))
        self.assertFalse(any(item['item_id'] == 'E' for item in result['rising']))
        self.assertEqual(result['window']['day_count'], 14)

    def test_empty_rows_report_missing_inputs(self):
        result = trend_items('2026-09-01', '2026-09-14', [])
        self.assertFalse(result['available'])
        self.assertIn('sycm_market_item_rank', result['missing_inputs'])


class ClassifyKeywordTests(unittest.TestCase):
    """8 大归类口径必须只有一份：月复盘复用 classify_keyword，不能各写一套。"""

    def test_returns_key_and_label(self):
        self.assertEqual(classify_keyword('纯麻质筒装式'), ('attribute', '属性'))
        self.assertEqual(classify_keyword('褶饰款筒装式'), ('style', '风格'))
        self.assertEqual(classify_keyword('加压型'), ('function', '功能'))
        self.assertEqual(classify_keyword('筒装式'), ('category', '类目'))

    def test_unknown_keyword_falls_back_to_other(self):
        self.assertEqual(classify_keyword('zzz 无此词'), ('other', '其他'))
        self.assertEqual(classify_keyword(''), ('other', '其他'))


if __name__ == '__main__':
    unittest.main()
