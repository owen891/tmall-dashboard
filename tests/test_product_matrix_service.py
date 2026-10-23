"""货品矩阵地图（product_matrix_service）单元测试。

口径（2026-10-02 用户拍板）：费比=推广花费÷GSV；引流款费比≥30%、利润款>0
且费比<10%、动销款有动销无花费；亏损与角色正交（loss 标志）；分层写回
products.tier 仅覆盖空值或算法自填行。
"""
import os
import sys
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from services.product_matrix_service import _classify, apply_tier_writeback


def _row(spend=0.0, gsv=0.0, profit=None):
    return {'ad_spend': spend, 'gsv': gsv, 'operating_profit': profit}


class ClassifyTests(unittest.TestCase):
    def test_three_segments_by_promotion_role(self):
        # 引流款：有花费且费比≥30%（XMind：付费主投）
        self.assertEqual(_classify(_row(35, 100, -10))[0], '引流款')
        # 利润款：利润>0 且费比<10%（低价扫流）
        self.assertEqual(_classify(_row(5, 100, 20))[0], '利润款')
        # 动销款：有动销无花费（不推广）
        self.assertEqual(_classify(_row(0, 100, 10))[0], '动销款')

    def test_loss_does_not_swallow_role(self):
        # 主力引流款亏损仍应显示引流角色（亏损与角色正交，用户 8 月案例）。
        label, _ = _classify(_row(60, 100, -30))
        self.assertEqual(label, '引流款')

    def test_loss_observation_when_no_role_matches(self):
        # 有花费但费比 10-30% 且亏损：不满足引流/利润/动销 → 亏损观察。
        self.assertEqual(_classify(_row(20, 100, -5))[0], '亏损观察')
        # 同样花费但盈利 → 未分层（花得不多又不亏，不强行归类）。
        self.assertEqual(_classify(_row(20, 100, 5))[0], '未分层')

    def test_profit_missing_treated_as_no_role(self):
        # profit 为 None（未回填）不能当 0 参与利润款判定。
        self.assertEqual(_classify(_row(5, 100, None))[0], '未分层')


def _row(spend, gsv, profit):
    return {'ad_spend': spend, 'gsv': gsv, 'operating_profit': profit}


class ApplyTierWritebackTests(unittest.TestCase):

    def test_locked_rows_never_overwritten(self):
        rows = {
            'A': {'tier': '', 'tier_source': ''},               # 空 → 写
            'B': {'tier': '爆款', 'tier_source': 'manual'},      # 人工锁定 → 跳过
            'C': {'tier': '引流款', 'tier_source': 'matrix-auto'},  # 算法自填 → 可更新
        }
        conn = self._make_conn(rows)
        matrix = {'available': True, 'items': [
            {'product_id': 'A', 'segment': '引流款'},
            {'product_id': 'B', 'segment': '引流款'},
            {'product_id': 'C', 'segment': '利润款'},
            {'product_id': 'D', 'segment': '未分层'},  # 不可写标签
            {'product_id': 'E', 'segment': '亏损观察'},  # 不可写标签
        ]}
        result = apply_tier_writeback(conn, matrix)
        self.assertEqual(result['updated'], 2)   # A 写入 + C 更新
        self.assertEqual(result['skipped_locked'], 1)

    def _make_conn(self, rows):
        class Conn:
            def __init__(self, rows):
                self._rows = rows
                self.updates = []

            def execute(self, sql, params=()):
                if sql.startswith('PRAGMA'):
                    class R:
                        def fetchall(self):
                            return [(0, 'product_id'), (1, 'tier'), (2, 'tier_source')]
                    return R()
                if sql.startswith('SELECT'):
                    class Row:
                        def __init__(self, data):
                            self._d = data
                        def __getitem__(self, key):
                            return self._d[key]
                    class Cursor:
                        def __init__(self, data):
                            self._d = data
                        def fetchone(self):
                            return Row(self._d)
                    return Cursor(self._rows.get(params[0], {'tier': '', 'tier_source': ''}))
                self.updates.append(params)
                return None
        return Conn(rows)

    def test_no_data_is_noop(self):
        result = apply_tier_writeback(self._make_conn({}), {'available': False})
        self.assertEqual(result.get('updated'), 0)

    def test_tier_with_blank_source_is_locked(self):
        """有档位但来源为空 → 锁定，不许覆盖。

        2026-10-22 修正前这里是放行的（`if current_source and ...`），
        而 scripts/sync_five_dim_tier.is_locked 判为锁定；同一个空值
        两个算法一边保护一边覆盖，谁后跑谁说了算。现在两处统一走
        services.tier_source.is_tier_locked，空来源一律视为人工赋值。
        """
        rows = {'F': {'tier': '利润款', 'tier_source': ''}}
        conn = self._make_conn(rows)
        result = apply_tier_writeback(conn, {
            'available': True,
            'items': [{'product_id': 'F', 'segment': '引流款'}],
        })
        self.assertEqual(result['updated'], 0)
        self.assertEqual(result['skipped_locked'], 1)
        self.assertEqual(conn.updates, [])   # 一次 UPDATE 都不能发出去

    def test_blank_tier_still_writable(self):
        """档位为空 → 可写（算法照样填新品的空档）。"""
        conn = self._make_conn({'G': {'tier': '', 'tier_source': ''}})
        result = apply_tier_writeback(conn, {
            'available': True,
            'items': [{'product_id': 'G', 'segment': '动销款'}],
        })
        self.assertEqual(result['updated'], 1)
        self.assertEqual(result['skipped_locked'], 0)


if __name__ == '__main__':
    unittest.main()
