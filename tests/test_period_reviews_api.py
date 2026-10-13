import os
import sys
import tempfile
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class PeriodReviewsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='tmall-dashboard-period-review-tests-')
        from app import create_app
        self.app = create_app({'TESTING': True, 'DATABASE_PATH': os.path.join(self.temp.name, 'dashboard.db')})
        self.client = self.app.test_client()

    def tearDown(self): self.temp.cleanup()

    def test_daily_weekly_monthly_reviews_are_persisted(self):
        response = self.client.put('/api/period-reviews/month/2026-04', json={
            'summary':'月度回顾', 'conclusions':'转化改善', 'next_actions':'保持素材', 'reviewer':'operator',
        })
        self.assertEqual(response.status_code, 200); response.close()
        response = self.client.get('/api/period-reviews?period_type=month')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['data'][0]['period_key'], '2026-04')
        self.assertIn('created_at', response.get_json()['data'][0])
        self.assertIn('updated_at', response.get_json()['data'][0])
        response.close()

    def test_period_options_are_built_from_daily_data_and_return_full_spans(self):
        from db import get_db

        with get_db(self.app.config['DATABASE_PATH']) as connection:
            connection.executemany(
                'INSERT INTO daily_data (product_id, date) VALUES (?, ?)',
                [
                    ('period-options-a', '2026-09-14'),
                    ('period-options-b', '2026-09-20'),
                    ('period-options-c', '2026-09-21'),
                    ('period-options-d', '2026-08-31'),
                ],
            )
            connection.commit()

        weeks = self.client.get('/api/period-reviews/period-options?period_type=week').get_json()['data']['options']
        months = self.client.get('/api/period-reviews/period-options?period_type=month').get_json()['data']['options']
        self.assertEqual(weeks[0], {
            'key': '2026-09-W4',
            'label': '2026年9月第4周（09-21 ~ 09-27）',
            'start': '2026-09-21',
            'end': '2026-09-27',
        })
        self.assertIn('2026-09-W3', [item['key'] for item in weeks])
        self.assertEqual(months[0]['key'], '2026-09')
        self.assertEqual(months[0]['start'], '2026-09-01')
        self.assertEqual(months[0]['end'], '2026-09-30')

    def test_week_and_month_context_return_only_their_verification_actions(self):
        from db import get_db

        with get_db(self.app.config['DATABASE_PATH']) as connection:
            connection.execute("INSERT INTO products (product_id, title) VALUES ('verify-product', '验证商品')")
            connection.executemany(
                '''INSERT INTO product_actions (
                       id, product_id, purpose_type, purpose_note, action_type, action_detail,
                       target_metric, status, planned_at, observer_window_days,
                       source_period_type, source_period_key, verification_period_type, verification_period_key,
                       source_problem_key, version
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                [
                    ('verify-week', 'verify-product', 'increase_sales', '周来源', 'image_change', '周动作',
                     'payment_amount', 'pending_review', '2026-09-14', 7, 'week', '2026-09-W3', 'week', '2026-09-W4', 'product_decline', 1),
                    ('verify-month', 'verify-product', 'increase_sales', '月来源', 'image_change', '月动作',
                     'payment_amount', 'pending_review', '2026-08-31', 7, 'month', '2026-08', 'month', '2026-09', 'product_decline', 1),
                ],
            )
            connection.commit()

        week = self.client.get('/api/period-reviews/week/2026-09-W4/context').get_json()['data']['context']
        month = self.client.get('/api/period-reviews/month/2026-09/context').get_json()['data']['context']
        self.assertEqual([row['id'] for row in week['actions_to_verify']], ['verify-week'])
        self.assertEqual([row['id'] for row in month['actions_to_verify']], ['verify-month'])

    def test_period_context_does_not_mix_future_or_other_source_actions(self):
        from db import get_db

        with get_db(self.app.config['DATABASE_PATH']) as connection:
            connection.execute("INSERT INTO products (product_id, title) VALUES ('scope-product', '范围商品')")
            connection.executemany(
                '''INSERT INTO product_actions (
                       id, product_id, purpose_type, purpose_note, action_type, action_detail,
                       target_metric, status, planned_at, observer_window_days,
                       source_period_type, source_period_key, verification_period_type, verification_period_key,
                       version
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                [
                    ('scope-current', 'scope-product', 'increase_sales', '本期', 'image_change', '本期动作',
                     'payment_amount', 'pending_execution', '2026-09-18', 7, 'week', '2026-09-W3', None, None, 1),
                    ('scope-future', 'scope-product', 'increase_sales', '未来', 'image_change', '未来动作',
                     'payment_amount', 'pending_execution', '2026-09-21', 7, 'week', '2026-09-W4', None, None, 1),
                    ('scope-wrong-date', 'scope-product', 'increase_sales', '错期', 'image_change', '错期动作',
                     'payment_amount', 'pending_execution', '2026-09-18', 7, 'month', '2026-09', None, None, 1),
                ],
            )
            connection.commit()

        context = self.client.get('/api/period-reviews/week/2026-09-W3/context').get_json()['data']['context']
        self.assertEqual([row['id'] for row in context['actions_planned']], ['scope-current'])

    def test_period_context_keeps_source_bound_action_planned_after_period_end(self):
        from db import get_db

        with get_db(self.app.config['DATABASE_PATH']) as connection:
            connection.execute("INSERT INTO products (product_id, title) VALUES ('late-plan-product', '延后计划商品')")
            connection.execute(
                '''INSERT INTO product_actions (
                       id, product_id, purpose_type, purpose_note, action_type, action_detail,
                       target_metric, status, planned_at, observer_window_days,
                       source_period_type, source_period_key, version
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                ('late-plan', 'late-plan-product', 'increase_sales', '复盘来源', 'image_change', '复盘后执行',
                 'payment_amount', 'pending_execution', '2026-09-22', 7, 'week', '2026-09-W3', 1),
            )
            connection.commit()

        context = self.client.get('/api/period-reviews/week/2026-09-W3/context').get_json()['data']['context']
        self.assertEqual([row['id'] for row in context['actions_planned']], ['late-plan'])

    def test_created_review_action_flows_into_next_week_verification_context(self):
        from db import get_db

        with get_db(self.app.config['DATABASE_PATH']) as connection:
            connection.execute("INSERT INTO products (product_id, title, shop_label) VALUES ('flow-product', '闭环商品', '标品袜子')")
            connection.commit()

        created = self.client.post('/api/actions', json={
            'product_id': 'flow-product',
            'purpose_type': 'increase_sales',
            'purpose_note': '复盘下滑商品恢复动作',
            'action_type': 'image_change',
            'action_detail': '更新主图并观察转化',
            'target_metric': 'payment_amount',
            'planned_at': '2026-09-22',
            'observer_window_days': 7,
            'source_period_type': 'week',
            'source_period_key': '2026-09-W3',
            'source_compare_mode': 'previous',
            'source_compare_period_key': '2026-09-W2',
            'source_product_id': 'flow-product',
            'source_problem_key': 'product_decline',
        })
        self.assertEqual(created.status_code, 201)
        action = created.get_json()['data']
        self.assertEqual(action['verification_period_key'], '2026-09-W4')

        for status in ('pending_execution', 'executing', 'observing'):
            transitioned = self.client.post(
                f"/api/actions/{action['id']}/transition",
                json={'status': status, 'version': action['version'], **({'executed_at': '2026-09-22'} if status == 'observing' else {})},
            )
            self.assertEqual(transitioned.status_code, 200)
            action = transitioned.get_json()['data']

        context = self.client.get('/api/period-reviews/week/2026-09-W4/context').get_json()['data']['context']
        self.assertEqual([row['id'] for row in context['actions_to_verify']], [action['id']])

    def test_month_action_full_loop_returns_target_and_review_result_in_next_month(self):
        from db import get_db

        with get_db(self.app.config['DATABASE_PATH']) as connection:
            connection.execute("INSERT INTO products (product_id, title) VALUES ('month-flow', '月度闭环商品')")
            connection.executemany(
                '''INSERT INTO daily_data (product_id, date, payment_amount, payment_conversion)
                   VALUES (?, ?, ?, ?)''',
                [
                    ('month-flow', '2026-08-29', 100, 0.05),
                    ('month-flow', '2026-08-30', 100, 0.07),
                    ('month-flow', '2026-09-01', 100, 0.11),
                    ('month-flow', '2026-09-02', 100, 0.13),
                ],
            )
            connection.commit()

        created = self.client.post('/api/actions', json={
            'product_id': 'month-flow', 'purpose_type': 'increase_conversion',
            'purpose_note': '月度转化恢复', 'action_type': 'detail_change',
            'action_detail': '优化首屏卖点', 'target_metric': 'conversion',
            'target_value': 0.12, 'acceptance_criteria': '执行后平均转化率达到 12%',
            'planned_at': '2026-09-01', 'observer_window_days': 2,
            'source_period_type': 'month', 'source_period_key': '2026-08',
        })
        self.assertEqual(created.status_code, 201)
        action = created.get_json()['data']
        self.assertEqual(action['verification_period_key'], '2026-09')
        for status in ('pending_execution', 'executing', 'observing'):
            response = self.client.post(
                f"/api/actions/{action['id']}/transition",
                json={'status': status, 'version': action['version'], **({'executed_at': '2026-08-31'} if status == 'observing' else {})},
            )
            self.assertEqual(response.status_code, 200)
            action = response.get_json()['data']

        context = self.client.get('/api/period-reviews/month/2026-09/context').get_json()['data']['context']
        self.assertEqual([row['id'] for row in context['actions_to_verify']], [action['id']])
        self.assertEqual(context['actions_to_verify'][0]['target_metric'], 'conversion')
        self.assertEqual(context['actions_to_verify'][0]['target_value'], 0.12)
        self.assertEqual(context['actions_to_verify'][0]['acceptance_criteria'], '执行后平均转化率达到 12%')

        calculated = self.client.post('/api/actions/recalculate')
        self.assertEqual(calculated.status_code, 200)
        action = calculated.get_json()['data']['actions'][0]
        self.assertEqual(action['status'], 'pending_review')
        reviewed = self.client.post(f"/api/actions/{action['id']}/review", json={
            'version': action['version'], 'effective': True, 'reason': '达到目标',
            'conclusion': '转化率提升', 'next_action': '继续观察', 'reviewer': 'operator',
        })
        self.assertEqual(reviewed.status_code, 200)
        self.assertEqual(reviewed.get_json()['data']['status'], 'completed')

        next_context = self.client.get('/api/period-reviews/month/2026-09/context').get_json()['data']['context']
        verification = next_context['actions_to_verify']
        self.assertEqual([row['id'] for row in verification], [action['id']])
        self.assertEqual(verification[0]['status'], 'completed')
        self.assertEqual(verification[0]['review_conclusion'], '转化率提升')

    def test_invalid_period_keys_are_rejected(self):
        for path in ('/api/period-reviews/day/2026-02-30', '/api/period-reviews/month/2026-13', '/api/period-reviews/week/2026-W99'):
            response = self.client.put(path, json={
                'summary': 'x', 'conclusions': 'x', 'next_actions': 'x', 'reviewer': 'operator',
            })
            self.assertEqual(response.status_code, 422)
            self.assertEqual(response.get_json()['code'], 'VALIDATION_ERROR')
        response = self.client.get('/api/period-reviews?period_type=invalid')
        self.assertEqual(response.status_code, 422)

    def test_weekly_and_monthly_templates_follow_business_review_sections(self):
        response = self.client.get('/api/period-reviews/templates')
        self.assertEqual(response.status_code, 200)
        payload = response.get_json(); response.close()

        self.assertEqual(payload['data']['template_version'], 'v3')
        week = [section['key'] for section in payload['data']['templates']['week']]
        month = [section['key'] for section in payload['data']['templates']['month']]
        # v2：周/月统一为同一套板块（对齐用户的月复盘 XMind 框架），
        # 段落 key 同构，保存与展示共用结构；旧 v1 key 由迁移层承接。
        self.assertEqual(
            week,
            ['category_summary', 'goods', 'ads', 'market', 'summary', 'next_plan'],
        )
        self.assertEqual(week, month)
        # v3：每段带「分析/根因/下一步」三段式子段定义，周月同构同能。
        for section in payload['data']['templates']['week']:
            subs = [sub['key'] for sub in section.get('subsections') or []]
            self.assertEqual(subs, ['analysis', 'root_cause', 'next_step'])

    def test_structured_review_saves_subsections_and_backfills_text(self):
        """v3 三段式保存：subsections 白名单校验通过后，text 由后端拼接回写。"""
        response = self.client.put('/api/period-reviews/week/2026-09-W3', json={
            'reviewer': 'operator',
            'sections': {
                'category_summary': {
                    'subsections': {
                        'analysis': '净销售完成 80%',
                        'root_cause': '访客下滑 30%',
                        'next_step': '下周补投引流款',
                    },
                },
            },
        })
        self.assertEqual(response.status_code, 200)
        payload = response.get_json(); response.close()
        saved = payload['data']['review']['sections']['category_summary']
        self.assertEqual(saved['subsections']['analysis'], '净销售完成 80%')
        self.assertEqual(saved['subsections']['root_cause'], '访客下滑 30%')
        # text 是三段拼接（顺序 = 模板定义顺序），老版本前端/导出可读。
        self.assertEqual(saved['text'], '净销售完成 80%\n\n访客下滑 30%\n\n下周补投引流款')

    def test_structured_review_rejects_unknown_subsection_keys(self):
        """未知子段 key 返回 422，白名单生效。"""
        response = self.client.put('/api/period-reviews/week/2026-09-W3', json={
            'reviewer': 'operator',
            'sections': {
                'category_summary': {
                    'subsections': {'analysis': 'ok', 'hack': 'x'},
                },
            },
        })
        self.assertEqual(response.status_code, 422)
        payload = response.get_json(); response.close()
        self.assertEqual(payload['code'], 'VALIDATION_ERROR')

    def test_structured_review_round_trips_sections_and_legacy_columns(self):
        response = self.client.put('/api/period-reviews/week/2026-09-W3', json={
            'reviewer': 'operator',
            'target_amount': 1000000,
            'sections': {
                'performance': {'text': '本期差距主要来自加投不足'},
                'done': {'text': '完成 3 款主图替换'},
                'plan': {'text': '加投关键词渠道，目标 ROI≥4'},
                'highlights': {'text': '亮点：转化提升；卡点：缺货'},
                'goods': {'text': 'TOP10 占比 53%，新品贡献不足'},
                'ads': {'text': '费比 20%，全站占比过高'},
            },
        })
        self.assertEqual(response.status_code, 200)
        payload = response.get_json(); response.close()

        self.assertEqual(payload['data']['missing_required_sections'], [])
        stored = payload['data']['review']
        self.assertEqual(stored['status'], 'final')
        self.assertEqual(stored['target_amount'], 1000000)
        # 旧 v1 key 保存时被迁移到 v2 key，库里不存双份。
        self.assertEqual(
            set(stored['sections']),
            {'category_summary', 'goods', 'ads', 'summary', 'next_plan'},
        )
        # 结构化段落必须同时回填历史字段，旧查询/旧页面才不会读到空值。
        self.assertIn('加投不足', stored['summary'])
        self.assertIn('加投关键词', stored['next_actions'])
        self.assertIn('亮点', stored['conclusions'])

        detail = self.client.get('/api/period-reviews/week/2026-09-W3')
        self.assertEqual(detail.status_code, 200)
        detail_payload = detail.get_json(); detail.close()
        # 合并段 summary 同时保留 v1 done 与 highlights 的内容
        merged_summary = detail_payload['data']['review']['sections']['summary']['text']
        self.assertIn('完成 3 款主图替换', merged_summary)
        self.assertIn('亮点：转化提升', merged_summary)
        self.assertEqual(detail_payload['data']['template'][0]['key'], 'category_summary')

    def test_four_indicator_targets_round_trip_and_drive_achievement_rates(self):
        """复盘目标不止销售额：利润 / 推广费 / 净费比也要能设，且达成率口径正确。

        达成率必须是「净销售额 ÷ 目标」，不是 GSV ÷ 目标；净费比是反向指标，
        达成率 = 目标 ÷ 实际。
        """
        from db import get_db

        with get_db(self.app.config['DATABASE_PATH']) as connection:
            connection.execute(
                "INSERT INTO products (product_id, title) VALUES ('target-row-product', '目标口径商品')"
            )
            connection.execute(
                '''INSERT INTO daily_data
                       (product_id, date, payment_amount, refund_amount, net_sales, ad_spend, operating_profit)
                   VALUES (?, ?, ?, ?, ?, ?, ?)''',
                ('target-row-product', '2026-09-14', 1200, 200, 1000, 250, 120),
            )
            connection.commit()

        response = self.client.put('/api/period-reviews/week/2026-09-W3', json={
            'reviewer': 'operator',
            'target_amount': 2000,
            'target_profit': 100,
            'target_ad_spend': 500,
            'target_net_expense_ratio': 0.2,
            'sections': {
                'performance': {'text': '目标口径校验'},
                'done': {'text': '完成校验'},
                'plan': {'text': '继续校验'},
                'highlights': {'text': '亮点与卡点'},
            },
        })
        self.assertEqual(response.status_code, 200)
        stored = response.get_json()['data']['review']; response.close()
        self.assertEqual(stored['target_amount'], 2000)
        self.assertEqual(stored['target_profit'], 100)
        self.assertEqual(stored['target_ad_spend'], 500)
        self.assertAlmostEqual(stored['target_net_expense_ratio'], 0.2, places=6)

        context = self.client.get(
            '/api/period-reviews/week/2026-09-W3/context?category_mode=all'
        ).get_json()['data']['context']
        target_path = context['target_path']

        # 达成率按净销售额算：1000 / 2000 = 0.5。若误用 GSV 会得到 1200 / 2000 = 0.6。
        self.assertEqual(target_path['metric'], 'net_sales')
        self.assertAlmostEqual(target_path['actual'], 1000, places=2)
        self.assertAlmostEqual(target_path['achieved_rate'], 0.5, places=6)

        rows = {row['key']: row for row in target_path['targets']}
        self.assertEqual(
            [row['key'] for row in target_path['targets']],
            ['net_sales', 'profit', 'ad_spend', 'net_expense_ratio'],
        )
        self.assertAlmostEqual(rows['net_sales']['achieved_rate'], 0.5, places=6)
        # 净利润额：120 / 100 = 1.2
        self.assertAlmostEqual(rows['profit']['achieved_rate'], 1.2, places=6)
        # 推广费：用户表里是「预算使用率」= 实际 ÷ 目标 = 250 / 500 = 0.5（不是倒数！）
        self.assertAlmostEqual(rows['ad_spend']['achieved_rate'], 0.5, places=6)
        # 净费比：实际 250 / 1000 = 0.25，反向 → 0.2 / 0.25 = 0.8
        self.assertAlmostEqual(rows['net_expense_ratio']['actual'], 0.25, places=6)
        self.assertAlmostEqual(rows['net_expense_ratio']['achieved_rate'], 0.8, places=6)

        # 达成率算法方向（reverse_rate）与配色方向（rate_better）是两件事，必须分开：
        # 推广费的达成率是正向算的，但「花得少」仍是好事，所以配色方向是 low。
        self.assertEqual(
            {key: (row['reverse_rate'], row['rate_better']) for key, row in rows.items()},
            {
                'net_sales': (False, 'high'),
                'profit': (False, 'high'),
                'ad_spend': (False, 'low'),
                'net_expense_ratio': (True, 'high'),
            },
        )

        # 时间进度 = 周期结束日 / 当月天数：W3 结束于 9/20，9 月 30 天 → 20/30。
        self.assertAlmostEqual(context['period']['time_progress'], 20 / 30, places=6)

    def test_month_time_progress_matches_excel_weeks(self):
        """时间进度按「周期结束日 / 当月天数」算（用户经营目标表实测口径）。"""
        expected = {
            '2026-09-W1': 6 / 30,
            '2026-09-W2': 13 / 30,
            '2026-09-W3': 20 / 30,
            '2026-09-W4': 27 / 30,
            '2026-09-W5': 30 / 30,
        }
        for period_key, want in expected.items():
            context = self.client.get(
                f'/api/period-reviews/week/{period_key}/context?category_mode=all'
            ).get_json()['data']['context']
            self.assertAlmostEqual(
                context['period']['time_progress'], want, places=6, msg=period_key,
            )

    def test_partial_save_keeps_existing_targets(self):
        """只改段落文字的局部保存不能把已录入的目标清空。"""
        first = self.client.put('/api/period-reviews/week/2026-09-W5', json={
            'reviewer': 'operator',
            'target_amount': 111,
            'target_profit': 22,
            'target_ad_spend': 33,
            'target_net_expense_ratio': 0.44,
        })
        # 只带目标的保存以前会被「周期复盘字段不完整」422 拒掉，这里必须显式断言，
        # 否则失败是静默的（后续断言只会报 None != 111，指向错误的地方）。
        self.assertEqual(first.status_code, 200)
        first.close()

        response = self.client.put('/api/period-reviews/week/2026-09-W5', json={
            'reviewer': 'operator',
            'sections': {'performance': {'text': '只更新段落'}},
        })
        self.assertEqual(response.status_code, 200)
        stored = response.get_json()['data']['review']; response.close()
        self.assertEqual(stored['target_amount'], 111)
        self.assertEqual(stored['target_profit'], 22)
        self.assertEqual(stored['target_ad_spend'], 33)
        self.assertAlmostEqual(stored['target_net_expense_ratio'], 0.44, places=6)

    def test_target_only_save_preserves_existing_sections(self):
        """反向：只录目标的保存不能把已经写好的段落清掉。"""
        written = self.client.put('/api/period-reviews/week/2026-09-W3', json={
            'reviewer': 'operator',
            'sections': {
                'performance': {'text': '业绩结论'},
                'done': {'text': '已完成事项'},
                'plan': {'text': '下一步'},
                'highlights': {'text': '风险'},
                'goods': {'text': '货品结论'},
                'ads': {'text': '广告结论'},
            },
        })
        self.assertEqual(written.status_code, 200); written.close()

        response = self.client.put('/api/period-reviews/week/2026-09-W3', json={
            'reviewer': 'operator',
            'target_amount': 500,
        })
        self.assertEqual(response.status_code, 200)
        stored = response.get_json()['data']['review']; response.close()
        self.assertEqual(stored['target_amount'], 500)
        # v1 performance 保存时迁移到 v2 category_summary，读取按新 key。
        self.assertEqual(stored['sections']['category_summary']['text'], '业绩结论')
        # 段落齐全时不应因为「只存目标」而把状态退回 draft
        self.assertEqual(stored['status'], 'final')

    def test_empty_target_is_stored_as_null_not_zero(self):
        """没填的目标要存 NULL，否则会被当成 0 目标算出无穷大达成率。"""
        response = self.client.put('/api/period-reviews/week/2026-08-W5', json={
            'reviewer': 'operator',
            'target_amount': '',
            'target_profit': None,
            'target_ad_spend': '',
            'target_net_expense_ratio': '',
        })
        self.assertEqual(response.status_code, 200)
        stored = response.get_json()['data']['review']; response.close()
        self.assertIsNone(stored['target_amount'])
        self.assertIsNone(stored['target_profit'])
        self.assertIsNone(stored['target_ad_spend'])
        self.assertIsNone(stored['target_net_expense_ratio'])

    def test_review_status_is_draft_when_required_sections_are_missing(self):
        response = self.client.put('/api/period-reviews/week/2026-09-W4', json={
            'reviewer': 'operator',
            'sections': {'performance': {'text': '只写了业绩结论'}},
        })
        self.assertEqual(response.status_code, 200)
        payload = response.get_json(); response.close()
        self.assertEqual(payload['data']['review']['status'], 'draft')
        self.assertIn('goods', payload['data']['missing_required_sections'])
        self.assertTrue(payload['unknowns'])

    def test_unknown_sections_are_rejected_and_legacy_put_preserves_sections(self):
        saved = self.client.put('/api/period-reviews/month/2026-08', json={
            'reviewer': 'operator',
            'sections': {'category_summary': {'text': '8 月达成率 92%'}},
        })
        self.assertEqual(saved.status_code, 200); saved.close()

        rejected = self.client.put('/api/period-reviews/month/2026-08', json={
            'reviewer': 'operator',
            'sections': {'not_a_section': {'text': 'x'}},
        })
        self.assertEqual(rejected.status_code, 422)
        self.assertEqual(rejected.get_json()['details']['sections'], ['not_a_section'])
        rejected.close()

        # 旧表单只提交摘要字段时，不能清空已保存的结构化段落。
        legacy = self.client.put('/api/period-reviews/month/2026-08', json={
            'summary': 's', 'conclusions': 'c', 'next_actions': 'n', 'reviewer': 'operator',
        })
        self.assertEqual(legacy.status_code, 200); legacy.close()
        detail = self.client.get('/api/period-reviews/month/2026-08')
        stored = detail.get_json()['data']['review']; detail.close()
        self.assertEqual(stored['sections']['category_summary']['text'], '8 月达成率 92%')

    def test_review_context_degrades_without_period_facts(self):
        response = self.client.get('/api/period-reviews/week/2026-09-W3/context')
        self.assertEqual(response.status_code, 200)
        payload = response.get_json(); response.close()

        self.assertTrue(payload['ok'])
        self.assertEqual(payload['availability'], 'no-data')
        self.assertEqual(payload['evidence_level'], 'insufficient')
        self.assertIn('daily_data', payload['missing_inputs'])
        context = payload['data']['context']
        self.assertFalse(context['metrics']['has_data'])
        self.assertEqual(context['period']['start'], '2026-09-14')
        self.assertEqual(context['period']['end'], '2026-09-20')
        self.assertIsNone(context['target_path']['target'])
        self.assertEqual(context['products']['top'], [])
        self.assertEqual(context['alerts'], [])

    def test_market_competitor_trends_use_daily_averages_and_require_comparable_coverage(self):
        from db import get_db

        with get_db(self.app.config['DATABASE_PATH']) as connection:
            connection.execute('''CREATE TABLE IF NOT EXISTS sycm_market_rival_shop (
                stat_date TEXT NOT NULL, shop_id TEXT, shop_name TEXT, shop_url TEXT,
                is_tmall INTEGER, uv REAL, pay_buyer_count REAL, cart_buyer_count REAL,
                collect_buyer_count REAL, pay_rate REAL)''')
            connection.execute('''CREATE TABLE IF NOT EXISTS sycm_market_rival_item (
                stat_date TEXT NOT NULL, item_id TEXT, title TEXT, uv REAL,
                pay_buyer_count REAL, pic_url TEXT, detail_url TEXT)''')
            connection.executemany(
                '''INSERT INTO sycm_market_rival_shop
                   (stat_date, shop_id, shop_name, uv, pay_buyer_count, pay_rate)
                   VALUES (?, 'shop-1', '核心竞店', 100, 10, 0.1)''',
                [(f'2026-09-{day:02d}',) for day in range(14, 19)]
                + [(f'2026-09-{day:02d}',) for day in range(7, 14)],
            )
            connection.commit()

        context = self.client.get(
            '/api/period-reviews/week/2026-09-W3/context?category_mode=all'
        ).get_json()['data']['context']
        rival = next(row for row in context['market']['rivals'] if row['shop_name'] == '核心竞店')
        self.assertEqual(rival['sample_days'], 5)
        self.assertEqual(rival['avg_uv_per_day'], 100)
        self.assertEqual(rival['avg_pay_buyers_per_day'], 10)
        self.assertFalse(rival['trend_comparable'])
        self.assertEqual(rival['status'], 'insufficient_coverage')
        self.assertIsNone(rival['pay_buyer_change_rate'])

    def test_market_block_exposes_grading_and_is_json_serializable(self):
        """月复盘市场段必须复用市场排行页的分级算法，且响应可 JSON 序列化。

        锁三件事：
        ① 8大归类 / 趋势节点 / 蓝海供给 / 竞店爆品 / 商品趋势 五项都真的进了响应；
        ② `grading` 集中声明窗口与口径边界（前端不再各自拼「有效期」）；
        ③ **整条响应能 json.dumps** —— 元组 key / datetime 这类不可序列化对象
           只有走到 API 层才暴露，单测直接调函数抓不到。
        """
        import json

        from db import get_db

        with get_db(self.app.config['DATABASE_PATH']) as connection:
            connection.execute('''CREATE TABLE IF NOT EXISTS sycm_market_item_rank (
                id INTEGER PRIMARY KEY AUTOINCREMENT, stat_date TEXT NOT NULL, cate_id TEXT,
                cate_name TEXT, item_id TEXT, title TEXT, shop_name TEXT, shop_id TEXT,
                uv REAL, pay_buyer_count REAL, core_keyword TEXT, rank INTEGER,
                is_self INTEGER, created_at TEXT, pic_url TEXT)''')
            connection.execute('''CREATE TABLE IF NOT EXISTS sycm_market_search_rank (
                id INTEGER PRIMARY KEY AUTOINCREMENT, stat_date TEXT NOT NULL, cate_id TEXT,
                cate_name TEXT, keyword TEXT, search_heat REAL, pay_rate REAL,
                free_click_rate REAL, click_rate REAL, rank INTEGER, created_at TEXT)''')
            # 12 天窗口：够「近 7 天 + 前置基线」两段，趋势节点才可判。
            days = [f'2026-09-{day:02d}' for day in range(14, 26)]
            item_rows, keyword_rows = [], []
            for index, stat_date in enumerate(days):
                # 竞店甲：A 商品排名 10 → 3（上升）；B 商品 3 → 10（下降）。
                rank_a = 10 if index < 6 else 3
                item_rows.append((stat_date, 'cate', '中筒袜', 'A', '压力袜男士透气款',
                                  '竞店甲', 'shop-a', 100.0, 10.0, 1, rank_a, 0))
                item_rows.append((stat_date, 'cate', '中筒袜', 'B', '压力袜女士薄款',
                                  '竞店甲', 'shop-a', 200.0, 20.0, 1, 13 - rank_a, 0))
                # 搜索词：压力袜有覆盖（title 含该词根），冷门词无覆盖。
                keyword_rows.append((stat_date, 'cate', '中筒袜', '压力袜', 5000.0, 0.2, 0.1, 0.3, 1))
                keyword_rows.append((stat_date, 'cate', '中筒袜', '毛巾袜', 500.0, 0.1, 0.1, 0.2, 2))
            connection.executemany(
                '''INSERT INTO sycm_market_item_rank
                   (stat_date, cate_id, cate_name, item_id, title, shop_name, shop_id,
                    uv, pay_buyer_count, core_keyword, rank, is_self)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                item_rows,
            )
            connection.executemany(
                '''INSERT INTO sycm_market_search_rank
                   (stat_date, cate_id, cate_name, keyword, search_heat, pay_rate,
                    free_click_rate, click_rate, rank)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                keyword_rows,
            )
            connection.commit()

        payload = self.client.get(
            '/api/period-reviews/month/2026-09/context?category_mode=all'
        ).get_json()
        # ③ 序列化：不过 json.dumps 就说明有非 JSON 值混进了响应。
        json.dumps(payload)
        market = payload['data']['context']['market']

        insights = market['keyword_insights']
        self.assertTrue(insights['available'])
        # 「压力袜」先命中「功能」词典（规则表有序，先命中先归类），「毛巾袜」命中「属性」。
        labels = {row['label'] for row in insights['categories']}
        self.assertEqual(labels, {'功能', '属性'})
        for row in insights['categories']:
            self.assertIn('keyword_count', row)
            self.assertIn('heat_share', row)
            self.assertIsInstance(row['top_keywords'], list)

        supply = market['blue_ocean_supply']
        self.assertTrue(supply['available'])
        by_root = {row['keyword']: row for row in supply['words']}
        # 有覆盖 → 参与分级；无覆盖 → 待核（不能判「高潜蓝海」）。
        self.assertNotEqual(by_root['压力袜']['grade'], '待核')
        self.assertEqual(by_root['毛巾袜']['grade'], '待核')
        self.assertEqual(supply['pending_count'], 1)

        moves = market['rival_moves']
        self.assertTrue(moves['available'])
        shop = next(row for row in moves['shops'] if row['shop_name'] == '竞店甲')
        self.assertEqual(shop['rising_count'], 1)
        self.assertEqual(shop['falling_count'], 1)

        trend_items = market['trend_items']
        self.assertTrue(trend_items['available'])
        self.assertEqual(trend_items['rising'][0]['item_id'], 'A')
        self.assertEqual(trend_items['rising'][0]['rank_change'], 7)

        grading = market['grading']
        self.assertIn('keyword_window', grading)
        self.assertIn('item_window', grading)
        self.assertIsInstance(grading['limitations'], list)
        # 复盘周期 09-01~09-30 但市场表只到 09-25 → 必须如实声明窗口缺口。
        self.assertTrue(any('仅覆盖' in text for text in grading['limitations']))

    def test_review_context_aggregates_period_facts_when_daily_data_exists(self):
        from db import get_db

        with get_db(self.app.config['DATABASE_PATH']) as connection:
            connection.executemany(
                '''INSERT INTO daily_data
                       (product_id, date, payment_amount, net_sales, refund_amount,
                        ad_spend, ipv, buyers, payment_conversion)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                [
                    ('P-1', '2026-09-14', 1000, 900, 100, 200, 500, 50, 0.1),
                    ('P-1', '2026-09-15', 2000, 1800, 100, 200, 500, 100, 0.2),
                    ('P-1', '2026-09-07', 500, 450, 50, 100, 250, 25, 0.1),
                ],
            )
            connection.commit()

        response = self.client.get('/api/period-reviews/week/2026-09-W3/context')
        self.assertEqual(response.status_code, 200)
        payload = response.get_json(); response.close()

        self.assertEqual(payload['availability'], 'partial')
        self.assertEqual(payload['evidence_level'], 'partial')
        context = payload['data']['context']
        self.assertTrue(context['metrics']['has_data'])
        self.assertEqual(context['metrics']['coverage']['status'], 'partial')
        self.assertEqual(context['metrics']['coverage']['observed_days'], 2)
        self.assertEqual(context['metrics']['coverage']['expected_days'], 7)
        self.assertEqual(context['metrics']['current']['gsv'], 3000)
        self.assertEqual(context['metrics']['current']['visitors'], 1000)
        self.assertAlmostEqual(context['metrics']['current']['conversion'], 0.15)
        self.assertEqual(context['metrics']['current']['ad_spend'], 400)
        self.assertIsNotNone(context['metrics']['current']['roi'])
        # 上期只有一天数据，环比仍应可比较。
        self.assertIsNotNone(context['metrics']['prev'])
        self.assertEqual(context['products']['top'][0]['product_id'], 'P-1')
        # 目标未配置时必须显式标记为 none，而不是把缺失当零。
        self.assertEqual(context['target_path']['source'], 'none')
        self.assertIsNone(context['target_path']['achieved_rate'])
        metric_keys = {item['key'] for item in context['metrics']['items']}
        self.assertIn('gsv', metric_keys)
        self.assertIn('ad_ratio', metric_keys)

    def test_category_breakdown_and_matrix_endpoints_return_rows(self):
        """回归：period_matrix 拆分后曾漏 import date，两个端点在真实库上集体 500。"""
        from db import get_db

        with get_db(self.app.config['DATABASE_PATH']) as connection:
            connection.execute(
                "INSERT INTO products (product_id, title, category) VALUES ('breakdown-product', '类目商品', '袜子')")
            connection.executemany(
                '''INSERT INTO daily_data
                   (product_id, date, payment_amount, ipv, buyers)
                   VALUES (?, ?, ?, ?, ?)''',
                [
                    ('breakdown-product', '2026-09-14', 1000, 500, 50),
                    ('breakdown-product', '2026-09-15', 2000, 800, 80),
                ],
            )
            connection.commit()

        for query in ('', '?category_mode=sock'):
            for endpoint in ('category-breakdown', 'matrix'):
                response = self.client.get(f'/api/period-reviews/week/2026-09-W3/{endpoint}{query}')
                self.assertEqual(response.status_code, 200, f'{endpoint}{query}')
                payload = response.get_json(); response.close()
                self.assertIn('rows', payload['data'], f'{endpoint}{query}')

    def test_traffic_prefers_dmp_snapshot_when_window_matches(self):
        """达摩盘单品快照能按品类给出搜索/推荐/付费/其他自然四行访客；
        窗口精确对齐时优先于 daily_data，四行互斥、占比合计 100%。"""
        import json as _json
        from db import get_db

        with get_db(self.app.config['DATABASE_PATH']) as connection:
            # dmp_shop_items 由采集器 DDL 建表（非迁移），测试库需自建。
            connection.execute(
                '''CREATE TABLE IF NOT EXISTS dmp_shop_items (
                       id INTEGER PRIMARY KEY AUTOINCREMENT,
                       run_id INTEGER NOT NULL, end_date TEXT NOT NULL, period INTEGER NOT NULL,
                       item_id TEXT, title TEXT, life_cycle TEXT, listed_days INTEGER,
                       cate_rank_html TEXT,
                       row_json TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP)'''
            )
            connection.executemany(
                'INSERT INTO products (product_id, title, shop_label) VALUES (?, ?, ?)',
                [('dmp-in', 'DMP 标品', '标品袜子'), ('dmp-out', 'DMP 非标', '非标袜子女')],
            )
            # daily_data 有数据，但 DMP 快照对齐时应当胜出。
            connection.execute(
                '''INSERT INTO daily_data (product_id, date, payment_amount, ipv, buyers, search_ipv)
                   VALUES (?, ?, ?, ?, ?, ?)''',
                ('dmp-in', '2026-09-14', 1000, 100, 10, 40),
            )
            rows = [
                # 标品：ipv=1000，搜索300 推荐200 付费250 → 其他自然 250
                ('dmp-in', {'ipv': 1000, 'searchFreeIpv': 300, 'recommendFreeIpv': 200,
                            'paidIpv': 250, 'freeIpv': 700}),
                # 非标：不应计入标品口径
                ('dmp-out', {'ipv': 9999, 'searchFreeIpv': 9999, 'recommendFreeIpv': 0,
                             'paidIpv': 0, 'freeIpv': 9999}),
            ]
            connection.executemany(
                '''INSERT INTO dmp_shop_items (run_id, end_date, period, item_id, title, row_json)
                   VALUES (1, ?, 7, ?, ?, ?)''',
                [('2026-09-20', pid, pid, _json.dumps(payload)) for pid, payload in rows],
            )
            connection.commit()

        context = self.client.get(
            '/api/period-reviews/week/2026-09-W3/context?category_mode=sock'
        ).get_json()['data']['context']
        traffic = context['dimensions']['traffic']
        self.assertEqual(traffic['source'], 'dmp_shop_items')
        self.assertEqual(traffic['snapshot_end_date'], '2026-09-20')
        by_key = {item['key']: item for item in traffic['items']}
        self.assertEqual(by_key['search']['value'], 300)
        self.assertEqual(by_key['recommend']['value'], 200)
        self.assertEqual(by_key['paid']['value'], 250)
        # 其他自然 = 总访客 − 搜索 − 推荐 − 付费（非标商品已按品类排除）。
        self.assertEqual(by_key['organic_other']['value'], 250)
        shares = sum(item['share_of_visitors'] for item in traffic['items'])
        self.assertAlmostEqual(shares, 1.0, places=6)

    def test_traffic_falls_back_when_dmp_window_misaligned(self):
        """DMP 快照末日与本期末日不一致时必须回退 daily_data——
        宁可三行为空，也不能拿错位窗口的数据冒充本期。"""
        import json as _json
        from db import get_db

        with get_db(self.app.config['DATABASE_PATH']) as connection:
            connection.execute(
                '''CREATE TABLE IF NOT EXISTS dmp_shop_items (
                       id INTEGER PRIMARY KEY AUTOINCREMENT,
                       run_id INTEGER NOT NULL, end_date TEXT NOT NULL, period INTEGER NOT NULL,
                       item_id TEXT, title TEXT, life_cycle TEXT, listed_days INTEGER,
                       cate_rank_html TEXT,
                       row_json TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP)'''
            )
            connection.execute("INSERT INTO products (product_id, title) VALUES ('dmp-mis', 'DMP Mis')")
            connection.execute(
                '''INSERT INTO daily_data (product_id, date, payment_amount, ipv, buyers, search_ipv)
                   VALUES (?, ?, ?, ?, ?, ?)''',
                ('dmp-mis', '2026-09-14', 1000, 100, 10, 40),
            )
            # 7 天窗口但 end_date=09-17 ≠ 本周末日 09-20 → 不可用。
            connection.execute(
                '''INSERT INTO dmp_shop_items (run_id, end_date, period, item_id, title, row_json)
                   VALUES (1, ?, 7, ?, ?, ?)''',
                ('2026-09-17', 'dmp-mis', 'DMP Mis',
                 _json.dumps({'ipv': 1000, 'searchFreeIpv': 300, 'recommendFreeIpv': 200,
                              'paidIpv': 250, 'freeIpv': 700})),
            )
            connection.commit()

        context = self.client.get(
            '/api/period-reviews/week/2026-09-W3/context?category_mode=sock'
        ).get_json()['data']['context']
        traffic = context['dimensions']['traffic']
        self.assertEqual(traffic['source'], 'daily_data')

    def test_review_context_exposes_traffic_and_promotion_dimensions(self):
        from db import get_db

        with get_db(self.app.config['DATABASE_PATH']) as connection:
            connection.execute("INSERT INTO products (product_id, title) VALUES ('dimension-product', 'Dimension Product')")
            connection.executemany(
                '''INSERT INTO daily_data
                   (product_id, date, payment_amount, ipv, buyers,
                    search_ipv, recommend_ipv, paid_ipv, organic_ipv)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                [
                    ('dimension-product', '2026-09-14', 1000, 1000, 50, 400, 300, 200, 100),
                    ('dimension-product', '2026-09-07', 800, 800, 40, 200, 300, 200, 100),
                ],
            )
            connection.executemany(
                '''INSERT INTO promotion_daily_facts
                   (date, channel, campaign_id, campaign_name, grain,
                    ad_spend, attributed_payment_amount, impressions, clicks, payment_buyers)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                [
                    ('2026-09-14', 'search', 'channel-search', 'Search', 'channel', 100, 400, 10000, 500, 40),
                    ('2026-09-14', 'display', 'channel-display', 'Display', 'channel', 50, 100, 5000, 100, 8),
                    ('2026-09-14', 'search', 'c1', 'Search Plan', 'campaign', 100, 400, 10000, 500, 40),
                    ('2026-09-14', 'display', 'c2', 'Display Plan', 'campaign', 50, 100, 5000, 100, 8),
                    ('2026-09-07', 'search', 'channel-search', 'Search', 'channel', 80, 320, 8000, 400, 32),
                    ('2026-09-07', 'search', 'c1', 'Search Plan', 'campaign', 80, 320, 8000, 400, 32),
                ],
            )
            connection.commit()

        context = self.client.get('/api/period-reviews/week/2026-09-W3/context').get_json()['data']['context']
        traffic = context['dimensions']['traffic']
        self.assertTrue(traffic['available'])
        self.assertEqual(traffic['sample_days'], 1)
        self.assertEqual(next(item for item in traffic['items'] if item['key'] == 'search')['value'], 400)

        promotion = context['dimensions']['promotion']
        self.assertTrue(promotion['available'])
        self.assertEqual(promotion['channels']['grain'], 'channel')
        self.assertEqual(promotion['campaigns']['grain'], 'campaign')
        search_channel = next(item for item in promotion['channels']['items'] if item['name'] == 'search')
        self.assertEqual(search_channel['ad_spend'], 100)
        self.assertAlmostEqual(search_channel['roi'], 4)

    def test_traffic_dimension_reports_residual_and_missing_sources(self):
        """流量来源占比必须能合计到 100%：四来源只覆盖全店访客的一部分，
        残差行「未归类来源」补齐差额，缺失来源清单解释哪几行为空。

        背景：BI 日快照不给 recommend/paid/organic 赋值（留 NULL），
        若只列四行、表头写「占比」，读者会误以为四行合计即全量。
        """
        from db import get_db

        with get_db(self.app.config['DATABASE_PATH']) as connection:
            connection.execute("INSERT INTO products (product_id, title) VALUES ('traffic-residual', 'Traffic Residual')")
            connection.executemany(
                '''INSERT INTO daily_data
                   (product_id, date, payment_amount, ipv, buyers,
                    search_ipv, recommend_ipv, paid_ipv, organic_ipv)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                [
                    # 全店访客 1000，仅搜索 400 有值 → 未归类残差 600（60%）。
                    ('traffic-residual', '2026-09-14', 1000, 1000, 50, 400, None, None, None),
                    ('traffic-residual', '2026-09-15', 1000, 1000, 50, 600, None, None, None),
                ],
            )
            connection.commit()

        context = self.client.get(
            '/api/period-reviews/week/2026-09-W3/context'
        ).get_json()['data']['context']
        traffic = context['dimensions']['traffic']

        # 缺失来源清单点明是口径缺口，而非当天无流量。
        self.assertEqual(sorted(traffic['missing_sources']), ['organic', 'paid', 'recommend'])
        residual = traffic['unclassified']
        self.assertIsNotNone(residual)
        self.assertAlmostEqual(residual['value'], 1000)  # (1000-400) + (1000-600)
        self.assertAlmostEqual(residual['share_of_visitors'], 0.5)

        # 已归类 + 未归类 = 100%，占比列可校验。
        known = sum((item['share_of_visitors'] or 0) for item in traffic['items'])
        self.assertAlmostEqual(known + residual['share_of_visitors'], 1.0, places=6)

    def test_traffic_residual_omitted_when_sources_are_complete(self):
        """四来源齐备且与全店访客恒等时，不造一个 0 值的「未归类来源」行。"""
        from db import get_db

        with get_db(self.app.config['DATABASE_PATH']) as connection:
            connection.execute("INSERT INTO products (product_id, title) VALUES ('traffic-complete', 'Traffic Complete')")
            connection.execute(
                '''INSERT INTO daily_data
                   (product_id, date, payment_amount, ipv, buyers,
                    search_ipv, recommend_ipv, paid_ipv, organic_ipv)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                ('traffic-complete', '2026-09-14', 1000, 1000, 50, 400, 300, 200, 100),
            )
            connection.commit()

        context = self.client.get(
            '/api/period-reviews/week/2026-09-W3/context'
        ).get_json()['data']['context']
        traffic = context['dimensions']['traffic']
        self.assertEqual(traffic['missing_sources'], [])
        self.assertIsNone(traffic['unclassified'])
        known = sum((item['share_of_visitors'] or 0) for item in traffic['items'])
        self.assertAlmostEqual(known, 1.0, places=6)

    def test_breakdown_exposes_coverage_for_missing_days(self):
        """缺天跳过不补 0 是对的，但必须回传覆盖元数据，前端才能提示「仅含 N/M 天」。"""
        from db import get_db

        with get_db(self.app.config['DATABASE_PATH']) as connection:
            connection.execute("INSERT INTO products (product_id, title) VALUES ('breakdown-gap', 'Breakdown Gap')")
            connection.executemany(
                '''INSERT INTO daily_data (product_id, date, payment_amount, net_sales, ipv, buyers)
                   VALUES (?, ?, ?, ?, ?, ?)''',
                [
                    ('breakdown-gap', '2026-09-14', 1000, 900, 100, 10),
                    # 缺 09-15 与 09-16（周内后两天）。
                ],
            )
            connection.commit()

        context = self.client.get(
            '/api/period-reviews/week/2026-09-W3/context'
        ).get_json()['data']['context']
        breakdown = context['breakdown']
        self.assertEqual(breakdown['grain'], 'day')
        self.assertEqual(breakdown['expected_count'], 7)
        self.assertEqual(breakdown['observed_count'], 1)
        self.assertEqual([row['label'] for row in breakdown['rows']], ['2026-09-14'])
        self.assertIn('2026-09-15', breakdown['missing_labels'])
        self.assertEqual(len(breakdown['missing_labels']), 6)

    def test_summary_block_aggregates_base_and_channels(self):
        """本期汇总把基础数据一次算全（比率由聚合后分子/分母现算，非逐行平均），
        并把缺失列显式列出——缺列保持 -- 而不是补 0。"""
        from db import get_db

        with get_db(self.app.config['DATABASE_PATH']) as connection:
            connection.execute("INSERT INTO products (product_id, title) VALUES ('summary-p', 'Summary P')")
            # 显式写 NULL：这两列 schema 默认值是 0，省略不写会变成「真 0」而不是
            # 缺失（source_resolution 对 BI 快照正是显式置 NULL），必须与生产一致。
            connection.executemany(
                '''INSERT INTO daily_data
                   (product_id, date, payment_amount, refund_amount, net_sales, ipv, buyers,
                    cart_users, search_ipv, new_payment_buyers, search_payment_buyers)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL)''',
                [
                    ('summary-p', '2026-09-14', 1000, 100, 900, 500, 50, 80, 200),
                    ('summary-p', '2026-09-15', 2000, 200, 1800, 700, 70, 120, 300),
                ],
            )
            connection.commit()

        context = self.client.get(
            '/api/period-reviews/week/2026-09-W3/context'
        ).get_json()['data']['context']
        summary = context['summary']
        base = summary['base']
        # 比率必须由「先汇总再算」得出，而不是逐日平均：
        # 退款率 = (100+200)/(1000+2000) = 10%
        self.assertAlmostEqual(base['refund_ratio'], 0.1, places=6)
        # UV价值 = 成交金额/访客 = 3000/1200 = 2.5
        self.assertAlmostEqual(base['uv_value'], 2.5, places=6)
        # 加购率 = 加购人数/访客 = 200/1200
        self.assertAlmostEqual(base['cart_rate'], 200 / 1200, places=6)
        self.assertEqual(base['visitors'], 1200)
        self.assertEqual(base['buyers'], 120)
        # 这两列该 fixture 未写入 → 缺失且不补 0；派生比率同样为 None。
        self.assertIn('new_buyers', summary['base_missing'])
        self.assertIsNone(base['new_buyers'])
        self.assertIsNone(base['new_buyer_share'])
        # 列清单与缺失清单一致可对账。
        column_keys = [col['key'] for col in summary['base_columns']]
        self.assertIn('uv_value', column_keys)
        self.assertTrue(set(summary['base_missing']).issubset(set(column_keys)))
        # 段标题含「利润」，汇总必须自包含利润与费比，不能只靠下方 KPI 网格。
        self.assertIn('profit', column_keys)
        self.assertIn('ad_ratio', column_keys)

    def test_summary_ad_channel_spend_reconciles_to_bill_total(self):
        """广告汇总渠道行只覆盖有计划级明细的推广，账单口径总花费更大；
        必须回传「未归因」残差，读者才能把渠道行 + 未归因对账到总花费，
        而不是把渠道加总误当成总推广花费。"""
        from db import get_db

        with get_db(self.app.config['DATABASE_PATH']) as connection:
            connection.execute("INSERT INTO products (product_id, title) VALUES ('ads-recon', 'Ads Recon')")
            # 账单口径总花费（daily_data.ad_spend）= 1000。
            connection.execute(
                '''INSERT INTO daily_data
                   (product_id, date, payment_amount, net_sales, ipv, buyers, ad_spend)
                   VALUES (?, ?, ?, ?, ?, ?, ?)''',
                ('ads-recon', '2026-09-14', 5000, 4500, 500, 50, 1000),
            )
            # 渠道级明细只有关键词 400（计划级），缺口应为 600。
            connection.execute(
                '''INSERT INTO promotion_daily_facts
                   (date, channel, campaign_id, campaign_name, grain, ad_spend,
                    attributed_payment_amount, impressions, clicks, payment_buyers)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                ('2026-09-14', '关键词推广', 'c1', 'KW', 'campaign', 400, 800, 1000, 100, 20),
            )
            connection.commit()

        context = self.client.get(
            '/api/period-reviews/week/2026-09-W3/context'
        ).get_json()['data']['context']
        summary = context['summary']
        self.assertAlmostEqual(summary['ads_total_spend'], 1000, places=2)
        channel_sum = sum(group['ad_spend'] for group in summary['ads_channels'])
        self.assertAlmostEqual(channel_sum, 400, places=2)
        # 未归因 = 1000 − 400，且渠道合计 + 未归因 = 总花费（可对账）。
        self.assertAlmostEqual(summary['ads_unattributed'], 600, places=2)
        self.assertAlmostEqual(channel_sum + summary['ads_unattributed'],
                               summary['ads_total_spend'], places=2)

    def test_summary_channel_conversion_uses_clicks_not_visitors(self):
        """渠道「点击转化率」分母是广告点击，与基础数据「转化率（访客）」不同源。
        两者若同名会被横向比较，这里锁住渠道侧的口径（buyers/clicks）。"""
        from db import get_db

        with get_db(self.app.config['DATABASE_PATH']) as connection:
            connection.execute("INSERT INTO products (product_id, title) VALUES ('conv-p', 'Conv P')")
            connection.execute(
                '''INSERT INTO daily_data
                   (product_id, date, payment_amount, net_sales, ipv, buyers, ad_spend)
                   VALUES (?, ?, ?, ?, ?, ?, ?)''',
                ('conv-p', '2026-09-14', 5000, 4500, 1000, 100, 500),
            )
            connection.execute(
                '''INSERT INTO promotion_daily_facts
                   (date, channel, campaign_id, campaign_name, grain, ad_spend,
                    attributed_payment_amount, impressions, clicks, payment_buyers)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                ('2026-09-14', '关键词推广', 'c1', 'KW', 'campaign', 500, 800, 5000, 200, 40),
            )
            connection.commit()

        context = self.client.get(
            '/api/period-reviews/week/2026-09-W3/context'
        ).get_json()['data']['context']
        summary = context['summary']
        kw = next(g for g in summary['traffic_channels'] if g['name'] == '关键词')
        # 渠道转化率 = 40/200（点击），不是 40/1000（访客）。
        self.assertAlmostEqual(kw['conversion'], 40 / 200, places=6)
        # 基础数据转化率 = 100/1000（访客）——两者确实不同源。
        self.assertAlmostEqual(summary['base']['conversion'], 100 / 1000, places=6)

    def test_summary_block_absent_when_period_has_no_data(self):
        """本期无日数据时返回 None，前端才能走空态，而不是渲染一张全 -- 的表。"""
        context = self.client.get(
            '/api/period-reviews/week/2026-09-W3/context'
        ).get_json()['data']['context']
        self.assertIsNone(context['summary'])

    def _seed_category_data(self):
        from db import get_db

        with get_db(self.app.config['DATABASE_PATH']) as connection:
            connection.executemany(
                'INSERT INTO products (product_id, title, image_url, shop_label) VALUES (?, ?, ?, ?)',
                [
                    ('P-SOCK', '标品袜子A', '', '标品袜子'),
                    ('P-MULTI', '标品袜子B', '', '标品袜子,平销商品'),
                    ('P-OTHER', '非标袜子女C', '', '非标袜子女'),
                ],
            )
            connection.executemany(
                '''INSERT INTO daily_data
                       (product_id, date, payment_amount, net_sales, refund_amount,
                        ad_spend, ipv, buyers, payment_conversion)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                [
                    ('P-SOCK', '2026-09-14', 1000, 900, 50, 100, 400, 40, 0.1),
                    ('P-MULTI', '2026-09-14', 300, 280, 10, 30, 120, 12, 0.1),
                    ('P-OTHER', '2026-09-14', 500, 460, 20, 60, 200, 20, 0.1),
                ],
            )
            connection.commit()

    def test_review_context_filters_by_selected_category(self):
        """品类口径必须真实过滤：标品袜子只算自己的商品，全部品类才算全店。"""
        self._seed_category_data()

        sock = self.client.get(
            '/api/period-reviews/week/2026-09-W3/context?category_mode=sock'
        ).get_json()
        self.assertEqual(sock['data']['context']['category']['label'], '标品袜子')
        self.assertTrue(sock['data']['context']['category']['filtered'])
        # 1000 + 300（多标签值 '标品袜子,平销商品' 也要按 token 命中）
        self.assertEqual(sock['data']['context']['metrics']['current']['gsv'], 1300)
        self.assertEqual(sock['data']['context']['metrics']['current']['product_count'], 2)
        self.assertEqual(sock['filters']['category_label'], '标品袜子')
        self.assertIn('标品袜子', ' '.join(sock['assumptions']))

        everything = self.client.get(
            '/api/period-reviews/week/2026-09-W3/context?category_mode=all'
        ).get_json()
        self.assertIsNone(everything['data']['context']['category']['label'])
        self.assertFalse(everything['data']['context']['category']['filtered'])
        self.assertEqual(everything['data']['context']['metrics']['current']['gsv'], 1800)
        self.assertEqual(everything['data']['context']['metrics']['current']['product_count'], 3)

        # 只有非标商品的品类必须算不到标品商品
        other = self.client.get(
            '/api/period-reviews/week/2026-09-W3/context?category_mode=非标袜子女'
        ).get_json()
        self.assertEqual(other['data']['context']['metrics']['current']['gsv'], 500)

    def test_category_options_always_expose_system_modes(self):
        payload = self.client.get('/api/period-reviews/categories').get_json()
        self.assertTrue(payload['ok'])
        values = [item['value'] for item in payload['data']['categories']]
        # 设置尚未初始化时下拉也不能为空，且系统品类恒在前
        self.assertEqual(values[:2], ['all', 'sock'])
        self.assertEqual(payload['data']['default_mode'], 'sock')

    def test_review_records_and_keeps_category_scope(self):
        saved = self.client.put('/api/period-reviews/week/2026-09-W3?category_mode=sock', json={
            'reviewer': 'operator',
            'sections': {'performance': {'text': '标品袜子口径'}},
        })
        self.assertEqual(saved.status_code, 200)
        self.assertEqual(saved.get_json()['data']['category']['label'], '标品袜子')
        saved.close()

        detail = self.client.get('/api/period-reviews/week/2026-09-W3').get_json()
        self.assertEqual(detail['data']['review']['category_mode'], 'sock')

        # 未显式传品类时沿用该期已保存的口径，不会被静默改成 all
        again = self.client.put('/api/period-reviews/week/2026-09-W3', json={
            'reviewer': 'operator',
            'summary': 's', 'conclusions': 'c', 'next_actions': 'n',
        })
        self.assertEqual(again.status_code, 200)
        self.assertEqual(again.get_json()['data']['review']['category_mode'], 'sock')
        again.close()

    def test_store_level_goal_target_flags_scope_mismatch_under_category_filter(self):
        from db import get_db

        with get_db(self.app.config['DATABASE_PATH']) as connection:
            connection.execute(
                "INSERT INTO daily_goals (year, goal_date, target_amount, source, version) VALUES (?, ?, ?, ?, ?)",
                (2026, '2026-09-14', 5000, 'recommended', 1),
            )
            connection.commit()
        self._seed_category_data()

        context = self.client.get(
            '/api/period-reviews/week/2026-09-W3/context?category_mode=sock'
        ).get_json()['data']['context']
        self.assertEqual(context['target_path']['target'], 5000)
        self.assertEqual(context['target_path']['source'], 'daily_goals')
        # 目标表无品类维度，按品类复盘时必须提示口径不一致
        self.assertTrue(context['target_path']['scope_mismatch'])

        widened = self.client.get(
            '/api/period-reviews/week/2026-09-W3/context?category_mode=all'
        ).get_json()['data']['context']
        self.assertFalse(widened['target_path']['scope_mismatch'])


    def _seed_three_periods(self):
        """W38 本期 / W37 环比 / W35 自定义对比，各一条，便于核对基线来源。"""
        from db import get_db

        with get_db(self.app.config['DATABASE_PATH']) as connection:
            connection.execute(
                "INSERT INTO products (product_id, title, image_url, shop_label) VALUES ('P-1', '标品袜子', '', '标品袜子')"
            )
            connection.executemany(
                'INSERT INTO daily_data (product_id, date, payment_amount, ipv, buyers) VALUES (?, ?, ?, ?, ?)',
                [
                    ('P-1', '2026-09-14', 1000, 100, 10),   # 2026-09-W3 本期
                    ('P-1', '2026-09-07', 500, 100, 10),    # 2026-09-W2 上一期
                    ('P-1', '2026-08-24', 200, 100, 10),    # 2026-08-W5 自定义对比
                ],
            )
            connection.commit()

    def _gsv_item(self, query=''):
        url = '/api/period-reviews/week/2026-09-W3/context?category_mode=sock' + query
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200, response.get_json())
        payload = response.get_json(); response.close()
        context = payload['data']['context']
        return context, next(item for item in context['metrics']['items'] if item['key'] == 'gsv')

    def test_compare_mode_selects_baseline_and_custom_period(self):
        """对比周期必须真的可换：默认环比、可换同比、可自选任一周期、也可不对比。"""
        self._seed_three_periods()

        context, gsv = self._gsv_item()
        self.assertEqual(context['compare']['mode'], 'previous')
        self.assertEqual(context['compare']['period_key'], '2026-09-W2')
        self.assertEqual(context['compare']['short_label'], '环比')
        self.assertEqual(gsv['prev_value'], 500)
        self.assertEqual(gsv['mom_change'], 100.0)
        self.assertEqual(len(context['compare_options']), 18)
        # 后端返回最近 18 期（含当前期），前端渲染下拉时会剔除当前期。
        self.assertEqual(context['compare_options'][0]['key'], '2026-09-W3')
        self.assertEqual(context['compare_options'][1]['key'], '2026-09-W2')

        # 同比：基线换成去年同周（本例无数据，必须为空而不是 0）
        context, gsv = self._gsv_item('&compare=yoy')
        self.assertEqual(context['compare']['mode'], 'yoy')
        self.assertEqual(context['compare']['period_key'], '2025-09-W3')
        self.assertIsNone(context['metrics']['prev'])
        self.assertFalse(context['compare']['has_data'])
        self.assertIsNone(gsv.get('prev_value'))
        self.assertIsNone(gsv.get('mom_change'))

        # 自定义对比周期：基线取自指定周
        context, gsv = self._gsv_item('&compare=custom&compare_period=2026-08-W5')
        self.assertEqual(context['compare']['mode'], 'custom')
        self.assertEqual(context['compare']['period_key'], '2026-08-W5')
        self.assertEqual(context['compare']['short_label'], '对比')
        self.assertEqual(gsv['prev_value'], 200)
        self.assertEqual(gsv['mom_change'], 400.0)

    def test_in_progress_period_comparisons_use_equal_elapsed_days(self):
        from datetime import date
        from services.period_review_service import resolve_period, resolve_compare

        current = resolve_period('week', '2026-09-W4', today=date(2026, 9, 23))
        previous = resolve_compare(current, 'previous')
        yoy = resolve_compare(current, 'yoy')
        custom = resolve_compare(current, 'custom', '2026-09-W3')
        self.assertEqual((previous['start'], previous['end']), ('2026-09-14', '2026-09-16'))
        self.assertEqual((yoy['start'], yoy['end']), ('2025-09-22', '2025-09-24'))
        self.assertEqual((custom['start'], custom['end']), ('2026-09-14', '2026-09-16'))

        completed = resolve_period('week', '2026-09-W3', today=date(2026, 9, 23))
        full_previous = resolve_compare(completed, 'previous')
        self.assertEqual((full_previous['start'], full_previous['end']), ('2026-09-07', '2026-09-13'))

        # 不对比：没有基线，但仍然保留同比供参考
        context, gsv = self._gsv_item('&compare=none')
        self.assertEqual(context['compare']['mode'], 'none')
        self.assertFalse(context['compare']['available'])
        self.assertIsNone(context['metrics']['prev'])
        self.assertIsNone(gsv.get('mom_change'))

    def test_invalid_compare_parameters_are_rejected(self):
        cases = (
            ('&compare=unknown', 422),
            ('&compare=custom', 422),
            ('&compare=custom&compare_period=2026-07', 422),
            ('&compare=custom&compare_period=2026-W99', 422),
            ('&compare=custom&compare_period=2026-09-W6', 422),
            ('&compare=yoy&compare_period=2026-08-W5', 422),
        )
        for query, status in cases:
            with self.subTest(query=query):
                response = self.client.get(
                    '/api/period-reviews/week/2026-09-W3/context?category_mode=sock' + query
                )
                self.assertEqual(response.status_code, status)
                self.assertEqual(response.get_json()['code'], 'VALIDATION_ERROR')
                response.close()

    def test_compare_baseline_drives_declining_products_ranking(self):
        """下滑榜必须跟随所选对比周期，否则指标与榜单口径会自相矛盾。"""
        from db import get_db

        with get_db(self.app.config['DATABASE_PATH']) as connection:
            connection.executemany(
                "INSERT INTO products (product_id, title, image_url, shop_label) VALUES (?, ?, '', '标品袜子')",
                [('P-A', 'A'), ('P-B', 'B')],
            )
            connection.executemany(
                'INSERT INTO daily_data (product_id, date, payment_amount, ipv, buyers) VALUES (?, ?, ?, ?, ?)',
                [
                    ('P-A', '2026-09-14', 100, 100, 10),
                    ('P-B', '2026-09-14', 100, 100, 10),
                    ('P-A', '2026-09-07', 50, 100, 10),    # 环比：A 增长
                    ('P-B', '2026-09-07', 300, 100, 10),   # 环比：B 下滑
                    ('P-A', '2026-08-24', 400, 100, 10),   # 自定义 W35：A 下滑
                    ('P-B', '2026-08-24', 90, 100, 10),
                ],
            )
            connection.commit()

        previous = self.client.get(
            '/api/period-reviews/week/2026-09-W3/context?category_mode=sock&compare=previous'
        ).get_json()['data']['context']
        self.assertEqual([row['product_id'] for row in previous['products']['decline']], ['P-B'])

        custom = self.client.get(
            '/api/period-reviews/week/2026-09-W3/context?category_mode=sock&compare=custom&compare_period=2026-08-W5'
        ).get_json()['data']['context']
        self.assertEqual([row['product_id'] for row in custom['products']['decline']], ['P-A'])

    # ------------------------------------------------ v2 框架新增能力
    def _seed_v2_framework_data(self):
        """覆盖 v2 框架：分解表 / 货品多榜单 / 广告单品 / 付费访客成本。"""
        from db import get_db

        with get_db(self.app.config['DATABASE_PATH']) as connection:
            connection.executemany(
                'INSERT INTO products (product_id, title, shop_label, list_date) VALUES (?, ?, ?, ?)',
                [
                    # 老品：三个榜单主力
                    ('V-TOP', '销售冠军', '标品袜子', '2025-01-01'),
                    ('V-PAID', '付费大户', '标品袜子', '2025-01-01'),
                    ('V-LOSS', '亏损款', '标品袜子', '2025-01-01'),
                    # 新品：上架在周期结束日前 60 天内
                    ('V-NEW', '新品A', '标品袜子', '2026-08-20'),
                    # 新品但上架超 60 天，不算新品
                    ('V-OLDNEW', '旧上架', '标品袜子', '2026-06-01'),
                ],
            )
            # 2026-09-W3 = 09-14 ~ 09-20；两天数据保证周内分解表有行
            connection.executemany(
                '''INSERT INTO daily_data
                       (product_id, date, payment_amount, net_sales, ad_spend,
                        operating_profit, ipv, buyers, paid_ipv, cart_rate)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                [
                    ('V-TOP', '2026-09-14', 5000, 4500, 100, 800, 1000, 100, 0, 0.2),
                    ('V-TOP', '2026-09-15', 3000, 2700, 50, 400, 600, 60, 0, 0.2),
                    ('V-PAID', '2026-09-14', 800, 700, 900, -50, 300, 20, 0, 0.1),
                    ('V-LOSS', '2026-09-14', 600, 500, 80, -300, 200, 15, 0, 0.1),
                    ('V-NEW', '2026-09-14', 1200, 1000, 200, 150, 400, 30, 0, 0.15),
                    ('V-OLDNEW', '2026-09-14', 900, 800, 10, 50, 200, 10, 0, 0.1),
                ],
            )
            # 万相台商品级事实：channel='全部'/grain='product'（付费访客成本兜底口径）
            connection.executemany(
                '''INSERT INTO promotion_daily_facts
                       (shop_id, date, channel, grain, product_id, ad_spend,
                        attributed_payment_amount, direct_payment_amount,
                        cart_adds, new_buyers, clicks)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                [
                    ('default', '2026-09-14', '全部', 'product', 'V-TOP',
                     150, 4500, 2000, 90, 15, 300),
                    ('default', '2026-09-14', '全部', 'product', 'V-PAID',
                     900, 800, 300, 45, 9, 180),
                ],
            )
            connection.commit()

    def test_v2_breakdown_and_paid_cpc_fallback(self):
        self._seed_v2_framework_data()

        week = self.client.get(
            '/api/period-reviews/week/2026-09-W3/context?category_mode=sock'
        ).get_json()['data']['context']
        # 周复盘分解 = 期内按日
        self.assertEqual(week['breakdown']['grain'], 'day')
        self.assertEqual([row['label'] for row in week['breakdown']['rows']],
                         ['2026-09-14', '2026-09-15'])
        day1 = week['breakdown']['rows'][0]['metrics']
        self.assertAlmostEqual(day1['gsv'], 8500, places=2)
        # daily_data.paid_ipv 为 0 时，付费访客成本退回万相台点击口径：
        # (150+900) / (300+180) = 2.1875
        self.assertIsNone(week['metrics']['current'].get('paid_ipv') or None)
        self.assertAlmostEqual(day1['paid_cpc'], 1050 / 480, places=6)
        self.assertEqual(week['metrics']['paid_cpc_source'], 'promotion_clicks')

        # 月复盘分解 = 月内分周（与 _month_bounded_weeks 同口径）
        month = self.client.get(
            '/api/period-reviews/month/2026-09/context?category_mode=sock'
        ).get_json()['data']['context']
        self.assertEqual(month['breakdown']['grain'], 'week')
        week_labels = [row['label'] for row in month['breakdown']['rows']]
        self.assertEqual(len(week_labels), 1)  # 只有 W3 有数据
        self.assertIn('第3周', week_labels[0])

    def test_month_breakdown_does_not_repeat_monthly_fallback_for_each_week(self):
        """月表回退只用于整月指标，不能把整月值伪装成每个缺日周的数据。"""
        from db import get_db

        with get_db(self.app.config['DATABASE_PATH']) as connection:
            connection.execute(
                "INSERT INTO products (product_id, title, shop_label) VALUES ('monthly-only-review', '月表商品', '标品袜子')"
            )
            connection.execute(
                '''INSERT INTO monthly_data
                   (product_id, month, payment_amount, net_sales, visitors, buyers)
                   VALUES (?, ?, ?, ?, ?, ?)''',
                ('monthly-only-review', '2026-09', 9000, 8100, 900, 90),
            )
            connection.commit()

        context = self.client.get(
            '/api/period-reviews/month/2026-09/context?category_mode=sock'
        ).get_json()['data']['context']
        self.assertEqual(context['metrics']['current']['gsv'], 9000)
        self.assertEqual(context['breakdown']['grain'], 'week')
        self.assertEqual(context['breakdown']['rows'], [])

        self._seed_v2_framework_data()

        context = self.client.get(
            '/api/period-reviews/week/2026-09-W3/context?category_mode=sock'
        ).get_json()['data']['context']
        products = context['products']
        # 付费 TOP：V-PAID(900) > V-NEW(200) > V-TOP(150) > V-LOSS(80) > V-OLDNEW(10)
        self.assertEqual([row['product_id'] for row in products['paid']],
                         ['V-PAID', 'V-NEW', 'V-TOP', 'V-LOSS', 'V-OLDNEW'])
        # 盈利 TOP：V-TOP(1200) > V-NEW(150) > V-OLDNEW(50)
        self.assertEqual([row['product_id'] for row in products['profit']],
                         ['V-TOP', 'V-NEW', 'V-OLDNEW'])
        # 亏损 TOP：V-LOSS(-300) > V-PAID(-50)
        self.assertEqual([row['product_id'] for row in products['loss']],
                         ['V-LOSS', 'V-PAID'])
        # 新品 = 周期结束日(09-20)前 60 天内上架：只有 V-NEW（V-OLDNEW 超期）
        self.assertEqual([row['product_id'] for row in products['new']], ['V-NEW'])
        self.assertEqual([row['product_id'] for row in products['new_paid']], ['V-NEW'])

    def test_v2_promotion_items_block_from_product_grain(self):
        self._seed_v2_framework_data()

        context = self.client.get(
            '/api/period-reviews/week/2026-09-W3/context?category_mode=sock'
        ).get_json()['data']['context']
        items = context['promotion_items']
        self.assertTrue(items['available'])
        self.assertEqual(len(items['items']), 2)
        top = items['items'][0]
        self.assertEqual(top['product_id'], 'V-PAID')
        self.assertAlmostEqual(top['totals']['ad_spend'], 900, places=4)
        # 总投产 = 800/900；直接投产 = 300/900；费比 = 900/800
        self.assertAlmostEqual(top['totals']['roi'], 800 / 900, places=4)
        self.assertAlmostEqual(top['totals']['direct_roi'], 300 / 900, places=4)
        self.assertAlmostEqual(top['totals']['ad_ratio'], 900 / 800, places=6)
        # 加购成本 = 900/45 = 20；拉新成本 = 900/9 = 100；加购率 = 45/180 = 0.25
        self.assertAlmostEqual(top['totals']['cart_cost'], 20, places=4)
        self.assertAlmostEqual(top['totals']['new_cost'], 100, places=4)
        self.assertAlmostEqual(top['totals']['cart_rate'], 0.25, places=6)
        # 渠道×商品粒度当前没有数据源，必须显式标注而不是伪造 0
        self.assertIn('promotion_product_channel_scope', items['missing_inputs'])
        self.assertEqual(top['channels'], {})

    def test_data_status_separates_coverage_level_from_metric_usability(self):
        """P0 #3：顶部数据状态 = 「灯 + 原因清单」，且 level 与 usable 必须分离。

        关键回归：**连完整月也可能 usable=False**。实测 `month/2026-09`（覆盖 30/30 天）
        因「利润恒等式不平 + 市场未对齐」带 2 项 warning —— 那是**结构性**的，
        不是临时故障。若只给一盏永远为黄的灯，读者会直接忽略它，等于没做。
        """
        from services.period_context import _data_status

        period = {'is_ongoing': False, 'elapsed_days': 30, 'total_days': 30}
        base_coverage = {'status': 'complete', 'expected_days': 30, 'observed_days': 30,
                         'missing_days': 0, 'observed_start': '2026-09-01', 'observed_end': '2026-09-30'}

        # ① 覆盖完整 + 有 warning（利润不平 / 同比不可比）→ level=complete 但 usable=False
        metrics = {
            'has_data': True,
            'coverage': dict(base_coverage),
            'comparability': {
                'mom': {'comparable': True, 'reason': None},
                'yoy': {'comparable': False, 'reason': 'baseline_grain_mismatch'},
            },
        }
        blocks = {
            'profit_structure': {'available': True, 'sentinel_rows': 155,
                                 'identity': {'ok': False, 'gap': 682843.86, 'note': '恒等残差说明'}},
            'ads': {'channel_totals': {'partial': True}},
            'missing_inputs': [],
        }
        status = _data_status(period, metrics, blocks)
        keys = {item['key'] for item in status['degradations']}
        self.assertIn('profit_identity', keys)
        self.assertIn('comparability_yoy', keys)
        self.assertIn('ads_channel_scope', keys)
        # 覆盖完整 → level=complete；但有 warning → 数字不可直接用
        self.assertEqual(status['level'], 'complete')
        self.assertFalse(status['usable'])
        self.assertEqual(status['warning_count'], 2)   # 利润 + 同比
        self.assertEqual(status['info_count'], 1)      # 按品类渠道缺全站
        self.assertIn('2 项影响可信度', status['label'])
        # 可比性原因必须翻成人话，不能把内部枚举直接抛给读者
        yoy = next(item for item in status['degradations'] if item['key'] == 'comparability_yoy')
        self.assertNotIn('baseline_grain_mismatch', yoy['detail'])
        # 利润项要带上未回填行数与残差，读者才能判断影响面
        profit = next(item for item in status['degradations'] if item['key'] == 'profit_identity')
        self.assertIn('155', profit['detail'])

        # ② 只有 info（口径边界）→ usable=True，措辞不能吓人
        clean_metrics = {
            'has_data': True,
            'coverage': dict(base_coverage),
            'comparability': {'mom': {'comparable': True}, 'yoy': {'comparable': True}},
        }
        info_only = _data_status(period, clean_metrics, {
            'ads': {'channel_totals': {'partial': True}}, 'missing_inputs': [],
        })
        self.assertEqual(info_only['level'], 'complete')
        self.assertTrue(info_only['usable'])
        self.assertEqual(info_only['warning_count'], 0)
        self.assertIn('数据可用', info_only['label'])

        # ③ 覆盖不足 → level=partial + coverage 降级，且说明缺几天
        partial_metrics = {
            'has_data': True,
            'coverage': {'status': 'partial', 'expected_days': 3, 'observed_days': 2,
                         'missing_days': 1, 'observed_end': '2026-10-02'},
            'comparability': {'mom': {'comparable': True}, 'yoy': {'comparable': True}},
        }
        partial = _data_status({'is_ongoing': True, 'elapsed_days': 3, 'total_days': 31},
                               partial_metrics, {'missing_inputs': []})
        self.assertEqual(partial['level'], 'partial')
        self.assertFalse(partial['usable'])
        cov = next(item for item in partial['degradations'] if item['key'] == 'coverage')
        self.assertIn('2/3', cov['detail'])
        self.assertTrue(partial['freshness']['is_ongoing'])

        # ④ 完全无数据 → no-data，不列一堆无意义的降级项
        empty = _data_status(period, {'has_data': False, 'coverage': {'status': 'no-data'}}, {})
        self.assertEqual(empty['level'], 'no-data')
        self.assertFalse(empty['usable'])
        self.assertIn('暂无数据', empty['label'])

    def test_context_exposes_data_status_payload(self):
        """data_status 必须真的进 API 响应（含 list 结构，且可 JSON 序列化）。"""
        self._seed_category_data()
        payload = self.client.get(
            '/api/period-reviews/week/2026-09-W3/context?category_mode=sock'
        ).get_json()
        status = payload['data']['context']['data_status']
        for key in ('level', 'usable', 'label', 'summary', 'coverage', 'freshness',
                    'comparability', 'degradations', 'degradation_count',
                    'warning_count', 'info_count'):
            self.assertIn(key, status)
        self.assertIsInstance(status['degradations'], list)
        self.assertIn(status['level'], ('complete', 'partial', 'no-data'))

    def test_data_status_flags_products_with_sales_but_no_label(self):
        """在卖但未打品类标签的商品必须进数据状态（BI 接口无标签字段，
        新品漂移要当期可见，而不是月底对账才发现——2026-09 实测 1,488 款）。"""
        from db import get_db

        self._seed_category_data()
        with get_db(self.app.config['DATABASE_PATH']) as connection:
            connection.execute(
                'INSERT INTO products (product_id, title, shop_label) VALUES (?, ?, ?)',
                ('P-UNLABELED', '新品未分类', ''),
            )
            connection.execute(
                '''INSERT INTO daily_data
                       (product_id, date, payment_amount, net_sales, refund_amount,
                        ad_spend, ipv, buyers, payment_conversion)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                ('P-UNLABELED', '2026-09-14', 800, 700, 40, 50, 200, 20, 0.1),
            )
            connection.commit()

        payload = self.client.get(
            '/api/period-reviews/week/2026-09-W3/context?category_mode=all'
        ).get_json()
        entry = next(
            (item for item in payload['data']['context']['data_status']['degradations']
             if item['key'] == 'unlabeled_products'),
            None,
        )
        self.assertIsNotNone(entry)
        self.assertEqual(entry['severity'], 'info')
        self.assertIn('1 款', entry['detail'])
        self.assertIn('700', entry['detail'])
        # 删除未分类商品后，该条目不应再出现
        from db import get_db as _get_db
        with _get_db(self.app.config['DATABASE_PATH']) as connection:
            connection.execute("DELETE FROM daily_data WHERE product_id = 'P-UNLABELED'")
            connection.execute("DELETE FROM products WHERE product_id = 'P-UNLABELED'")
            connection.commit()
        payload_after = self.client.get(
            '/api/period-reviews/week/2026-09-W3/context?category_mode=all'
        ).get_json()
        self.assertFalse(
            any(item['key'] == 'unlabeled_products'
                for item in payload_after['data']['context']['data_status']['degradations'])
        )

    def test_campaign_attribution_is_exact_only_and_fills_all_site_channel(self):
        """计划→商品归因：只对 1:1 计划精确归因（不摊），并补商品级「全站推广」。

        回归三个既有缺口：
        ① 商品级「全站推广」2026-08-20 后无来源（promotion_creative_daily 不含该场景）；
        ② 品类模式下「推广计划拆解」恒空；
        ③ 归因绝不用「按商品数均摊」凭空造数——多商品计划只在计划级展示。
        """
        from db import get_db

        with get_db(self.app.config['DATABASE_PATH']) as connection:
            connection.executemany(
                'INSERT INTO products (product_id, title, image_url, shop_label) VALUES (?, ?, ?, ?)',
                [
                    ('A-1', '标品袜子A', '', '标品袜子'),
                    ('B-1', '标品袜子B', '', '标品袜子'),
                    ('C-1', '非标袜子女C', '', '非标袜子女'),
                ],
            )
            # 商品级合计（channel='全部'）决定 TOP 榜顺序与「合计」列
            connection.executemany(
                '''INSERT INTO promotion_daily_facts
                   (date, channel, campaign_id, product_id, grain, ad_spend,
                    attributed_payment_amount, direct_payment_amount, cart_adds, new_buyers, clicks)
                   VALUES (?, ?, '', ?, 'product', ?, ?, ?, 0, 0, 0)''',
                [
                    ('2026-09-14', '全部', 'A-1', 100, 500, 400),
                    ('2026-09-14', '全部', 'B-1', 60, 240, 200),
                    ('2026-09-14', '全部', 'C-1', 40, 80, 60),
                ],
            )
            # 计划级事实（grain='campaign'）
            connection.executemany(
                '''INSERT INTO promotion_daily_facts
                   (date, channel, campaign_id, campaign_name, grain, ad_spend,
                    attributed_payment_amount, direct_payment_amount, clicks, impressions)
                   VALUES (?, ?, ?, ?, 'campaign', ?, ?, ?, 0, 0)''',
                [
                    ('2026-09-14', '货品全站推广', 'C-EXACT', '全站_A1', 100, 500, 400),
                    ('2026-09-14', '货品全站推广', 'C-OTHER', '全站_C1', 40, 80, 60),
                    ('2026-09-14', '关键词推广', 'C-SHARED', '关键词_多商品', 60, 240, 200),
                ],
            )
            connection.executemany(
                '''INSERT INTO promotion_campaign_items
                   (campaign_id, product_id, campaign_name, product_name, image_url, channel)
                   VALUES (?, ?, ?, ?, ?, ?)''',
                [
                    ('C-EXACT', 'A-1', '全站_A1', '标品袜子A', 'https://img.example.com/a-1.jpg', '货品全站推广'),
                    ('C-OTHER', 'C-1', '全站_C1', '非标袜子女C', '', '货品全站推广'),
                    ('C-SHARED', 'A-1', '关键词_多商品', '标品袜子A', '', '关键词推广'),
                    ('C-SHARED', 'B-1', '关键词_多商品', '标品袜子B', '', '关键词推广'),
                ],
            )
            connection.commit()

        context = self.client.get(
            '/api/period-reviews/week/2026-09-W3/context?category_mode=all'
        ).get_json()['data']['context']
        attr = context['campaign_attribution']
        self.assertTrue(attr['available'])
        self.assertIn('非均摊', attr['attribution_note'])
        self.assertEqual(context['promotion_items']['attribution']['method'], 'exact_1to1_campaign')
        by_id = {item['campaign_id']: item for item in attr['items']}
        self.assertEqual(by_id['C-EXACT']['attribution'], 'exact')
        self.assertEqual(by_id['C-EXACT']['product_id'], 'A-1')
        self.assertEqual(by_id['C-SHARED']['attribution'], 'shared')
        self.assertIsNone(by_id['C-SHARED']['product_id'])
        self.assertEqual(by_id['C-SHARED']['product_count'], 2)
        # 精确归因花费 (100+40) / 总花费 200 = 0.7；shared 的 60 不计入分子
        self.assertAlmostEqual(attr['exact_share'], 0.7, places=4)

        # ① 商品级「全站推广」被补上（此前该渠道在 2026-08-20 后恒空）
        items = {item['product_id']: item for item in context['promotion_items']['items']}
        self.assertIn('全站', items['A-1']['channels'])
        self.assertAlmostEqual(items['A-1']['channels']['全站']['ad_spend'], 100, places=4)
        self.assertEqual(items['A-1']['channel_sources']['全站'], 'campaign_exact')
        # 广告单品明细使用推广商品表图片兜底，周/月复盘都必须返回主图。
        self.assertEqual(items['A-1']['image_url'], 'https://img.example.com/a-1.jpg')
        month = self.client.get(
            '/api/period-reviews/month/2026-09/context?category_mode=all'
        ).get_json()['data']['context']
        month_items = {item['product_id']: item for item in month['promotion_items']['items']}
        self.assertEqual(month_items['A-1']['image_url'], 'https://img.example.com/a-1.jpg')
        # ③ 多商品计划不摊到任何商品：B-1 只有 shared 计划的曝光，不得凭空得到花费
        self.assertNotIn('全站', items['B-1']['channels'])
        self.assertEqual(items['B-1']['channels'], {})

        # ② 品类模式下「推广计划拆解」不再为空，且按品类真实过滤
        sock = self.client.get(
            '/api/period-reviews/week/2026-09-W3/context?category_mode=sock'
        ).get_json()['data']['context']
        campaigns = sock['dimensions']['promotion']['campaigns']
        self.assertTrue(campaigns['available'])
        names = [item['name'] for item in campaigns['items']]
        self.assertIn('全站_A1', names)
        self.assertNotIn('全站_C1', names)      # 唯一商品在品类外 → 精确排除
        self.assertIn('关键词_多商品', names)     # 有本品类商品 → 保留但标 partial
        self.assertTrue(campaigns['partial'])
        # 分母必须与分子同口径：只算通过品类过滤的计划 100/160，而不是全店 200
        self.assertAlmostEqual(sock['campaign_attribution']['exact_share'], 100 / 160, places=4)

        # ④ 渠道拆分（ads.channel_totals）与「推广渠道拆解」（promotion.channels）
        #    在品类口径下也要有全站行（1:1 精确归因补全），并带完整派生指标。
        groups = {group['name']: group for group in sock['ads']['channel_totals']['groups']}
        self.assertIn('全站', groups)
        self.assertAlmostEqual(groups['全站']['ad_spend'], 100, places=4)
        # creative 未覆盖的渠道（人群等）不凭空出现；全店口径则含 C-OTHER 的 40。
        self.assertNotIn('人群', groups)
        all_groups = {group['name']: group for group in context['ads']['channel_totals']['groups']}
        self.assertAlmostEqual(all_groups['全站']['ad_spend'], 140, places=4)
        # 派生指标：直接投产 = 直接成交 ÷ 花费 = 400/100；花费占比分母 = 品类商品级花费 160。
        self.assertAlmostEqual(groups['全站']['direct_roi'], 4.0, places=4)
        self.assertAlmostEqual(groups['全站']['spend_share'], 100 / 160, places=4)
        # 多商品全站计划无明细 → 成交占比分母不全，必须保持 None（partial）。
        self.assertIsNone(groups['全站']['payment_share'])
        sock_channels = sock['dimensions']['promotion']['channels']
        channel_names = [item['name'] for item in sock_channels['items']]
        self.assertIn('货品全站推广', channel_names)
        sitewide_row = next(item for item in sock_channels['items'] if item['name'] == '货品全站推广')
        self.assertAlmostEqual(sitewide_row['ad_spend'], 100, places=4)
        self.assertAlmostEqual(sitewide_row['spend_share'], 100 / 160, places=4)

    def test_v2_legacy_sections_are_migrated_on_read(self):
        # 直接按 v1 周 key 写库（绕过 PUT 迁移），验证读取侧迁移。
        from db import get_db

        with get_db(self.app.config['DATABASE_PATH']) as connection:
            connection.execute(
                """INSERT INTO period_reviews
                       (period_type, period_key, reviewer, summary, conclusions, next_actions,
                        status, template_version, sections)
                   VALUES ('week', '2026-08-W1', 'operator', 's', 'c', 'n', 'final', 'v1', ?)""",
                ('{"performance": {"text": "v1业绩"}, "done": {"text": "v1做了什么"},'
                 ' "highlights": {"text": "v1亮点"}, "plan": {"text": "v1计划"}}',),
            )
            connection.commit()

        detail = self.client.get('/api/period-reviews/week/2026-08-W1').get_json()['data']
        sections = detail['review']['sections']
        self.assertEqual(sections['category_summary']['text'], 'v1业绩')
        # 合并段拼接 done + highlights
        self.assertEqual(sections['summary']['text'], 'v1做了什么\n\nv1亮点')
        self.assertEqual(sections['next_plan']['text'], 'v1计划')

    def test_v2_product_trend_endpoint(self):
        """货品榜「趋势」按钮的后端：近 N 个完整月内周的指标序列。"""
        from db import get_db

        with get_db(self.app.config['DATABASE_PATH']) as connection:
            connection.executemany(
                'INSERT INTO daily_data (product_id, date, payment_amount, ipv, buyers, net_sales) VALUES (?, ?, ?, ?, ?, ?)',
                [
                    # 本周（测试跑在任意日期）只保证历史周稳定：
                    # 2026-01 与 2026-02 各铺两周完整数据
                    ('V-TREND', '2026-01-05', 100, 1000, 50, 90),
                    ('V-TREND', '2026-01-12', 200, 1500, 90, 180),
                    ('V-TREND', '2026-02-02', 300, 2000, 100, 270),
                ],
            )
            connection.commit()

        response = self.client.get('/api/period-reviews/product-trend/V-TREND?weeks=4')
        self.assertEqual(response.status_code, 200)
        payload = response.get_json(); response.close()
        self.assertTrue(payload['ok'])
        self.assertEqual(payload['data']['grain'], 'week')
        weeks = payload['data']['points']
        # 只要有日数据就返回序列；至少覆盖铺过的周
        self.assertTrue(len(weeks) >= 2)
        # 每行字段齐全，转化率 = buyers / visitors
        first = weeks[0]
        for key in ('label', 'start', 'end', 'gsv', 'net_sales', 'visitors', 'buyers', 'conversion'):
            self.assertIn(key, first)
        jan_row = next((row for row in weeks if row['start'].startswith('2026-01')), None)
        if jan_row:
            self.assertAlmostEqual(jan_row['conversion'], 50 / 1000, places=6)

        # 非法参数：weeks 夹紧而不是报错；空 ID 422
        clamped = self.client.get('/api/period-reviews/product-trend/V-TREND?weeks=999')
        self.assertEqual(clamped.status_code, 200); clamped.close()
        bad = self.client.get('/api/period-reviews/product-trend/%20')
        self.assertEqual(bad.status_code, 422); bad.close()

    def test_v2_product_trend_month_grain_links_to_month_review(self):
        """月复盘联动：grain=month 读 monthly_data 快照（生命周期同源，历史长于日导入）。"""
        from db import get_db

        with get_db(self.app.config['DATABASE_PATH']) as connection:
            connection.executemany(
                '''INSERT INTO monthly_data (product_id, month, payment_amount, visitors, buyers,
                   payment_conversion, net_sales, ad_spend) VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                [
                    ('V-TREND-M', '2026-05', 205435.0, 20000, 1000, 0.05, 180000.0, 30000.0),
                    ('V-TREND-M', '2026-06', 137752.0, 15000, 800, 0.0533, 120000.0, 20000.0),
                ],
            )
            connection.commit()

        monthly = self.client.get('/api/period-reviews/product-trend/V-TREND-M?weeks=4&grain=month')
        self.assertEqual(monthly.status_code, 200)
        payload = monthly.get_json(); monthly.close()
        self.assertTrue(payload['ok'])
        self.assertEqual(payload['data']['grain'], 'month')
        points = payload['data']['points']
        # 只返回快照里已结束的月份，按时间升序
        self.assertEqual([p['label'] for p in points], ['2026-05', '2026-06'])
        june = points[-1]
        self.assertAlmostEqual(june['gsv'], 137752.0, places=2)
        self.assertAlmostEqual(june['conversion'], 0.0533, places=6)
        # 快照没有 ad_ratio 列，费比由花费 ÷ 销售额重推
        self.assertAlmostEqual(june['ad_ratio'], 20000.0 / 137752.0, places=6)

        bad_grain = self.client.get('/api/period-reviews/product-trend/V-TREND-M?grain=quarter')
        self.assertEqual(bad_grain.status_code, 422); bad_grain.close()

    def test_problem_items_aggregate_across_boards_with_sources(self):
        """P2 问题单品聚合：下滑榜/亏损榜/高费比跨榜去重并标注来源。"""
        from db import get_db

        with get_db(self.app.config['DATABASE_PATH']) as connection:
            connection.executemany(
                '''INSERT INTO daily_data (product_id, date, payment_amount, ad_spend, operating_profit)
                   VALUES (?, ?, ?, ?, ?)''',
                [
                    # problem-decline：GSV 大幅下滑（上期 10000 → 本期 2000），命中下滑榜
                    ('problem-decline', '2026-09-21', 2000, 100, -50),
                    ('problem-decline', '2026-09-14', 10000, 100, 100),
                    # problem-loss：本期利润为负，命中亏损榜
                    ('problem-loss', '2026-09-21', 3000, 100, -200),
                    # problem-ratio：费比 50%（阈值 30%）且 GSV 占比 >1%
                    ('problem-ratio', '2026-09-21', 1500, 750, 50),
                ],
            )
            connection.commit()

        context = self.client.get('/api/period-reviews/week/2026-09-W4/context').get_json()['data']['context']
        problems = context['products']['problem_items']
        by_id = {row['product_id']: row for row in problems}
        self.assertIn('problem-decline', by_id)
        self.assertIn('下滑榜', by_id['problem-decline']['problem_sources'])
        self.assertIn('problem-loss', by_id)
        self.assertIn('亏损榜', by_id['problem-loss']['problem_sources'])
        self.assertIn('problem-ratio', by_id)
        self.assertIn('高费比', by_id['problem-ratio']['problem_sources'])
        # 正常商品不在问题清单
        self.assertNotIn('period-options-a', by_id)

    def test_problem_items_ratio_only_product_gets_meta(self):
        """纯「高费比」来源的问题单品往往不进任何 TOP 榜，必须照样拿到标题/主图。

        回归 2026-10-W1：meta 只查各榜单 ID 集合，高费比小商品在问题清单里
        裸露商品ID、无主图。
        """
        from db import get_db

        with get_db(self.app.config['DATABASE_PATH']) as connection:
            connection.execute(
                'INSERT INTO products (product_id, title, image_url) VALUES (?, ?, ?)',
                ('problem-meta-small', '高费比小商品', 'https://img.example.com/small.jpg'),
            )
            rows = [
                # 11 个大商品占满 GSV/花费/利润 TOP10，把小商品挤出所有榜单
                (f'big-{index:02d}', '2026-09-22', 10000, 2000, 100)
                for index in range(11)
            ]
            # 小商品：费比 50%（>30% 阈值）、GSV 占比 2000/112000≈1.8%（>1%），
            # 但不亏损、不下滑、进不了任何 TOP10 → 纯高费比来源
            rows.append(('problem-meta-small', '2026-09-22', 2000, 1000, 50))
            connection.executemany(
                '''INSERT INTO daily_data (product_id, date, payment_amount, ad_spend, operating_profit)
                   VALUES (?, ?, ?, ?, ?)''',
                rows,
            )
            connection.commit()

        context = self.client.get('/api/period-reviews/week/2026-09-W4/context').get_json()['data']['context']
        entry = next(
            (row for row in context['products']['problem_items']
             if row['product_id'] == 'problem-meta-small'),
            None,
        )
        self.assertIsNotNone(entry)
        self.assertEqual(entry['problem_sources'], ['高费比'])
        self.assertEqual(entry['title'], '高费比小商品')
        self.assertEqual(entry['image_url'], 'https://img.example.com/small.jpg')

    def test_linked_summaries_month_reads_weeks_and_week_reads_prev_month(self):
        """P2 周月互汇：月复盘汇入本月各周结论，周复盘读上月月复盘。"""
        # 先存本月两个周复盘 + 上月一个月复盘（subsections 结构）
        self.client.put('/api/period-reviews/week/2026-09-W1', json={
            'reviewer': 'operator',
            'status': 'final',
            'sections': {'category_summary': {'subsections': {
                'analysis': 'W1 净销售达成 90%', 'root_cause': '流量下滑'}}},
        })
        self.client.put('/api/period-reviews/week/2026-09-W2', json={
            'reviewer': 'operator',
            'status': 'final',
            'sections': {'category_summary': {'text': 'W2 纯文本老结构结论'}},
        })
        self.client.put('/api/period-reviews/week/2026-09-W4', json={
            'reviewer': 'operator',
            'sections': {'category_summary': {'text': 'W4 草稿不应汇入月复盘'}},
        })
        self.client.put('/api/period-reviews/month/2026-08', json={
            'reviewer': 'operator',
            'status': 'final',
            'sections': {'category_summary': {'subsections': {
                'analysis': '8月净销售 71.9 万', 'root_cause': '访客下滑 30%+，调价影响人群池'}}},
        })

        month = self.client.get('/api/period-reviews/month/2026-09/context').get_json()['data']['context']
        linked = month['linked_summaries']
        self.assertEqual(linked['kind'], 'weekly')
        keys = [item['period_key'] for item in linked['items']]
        self.assertEqual(keys, ['2026-09-W1', '2026-09-W2'])
        w1 = linked['items'][0]
        self.assertIn('W1 净销售达成 90%', w1['analysis'])
        self.assertIn('root_cause: 流量下滑', w1['analysis'])
        # 纯 text 老结构也能读到
        self.assertIn('W2 纯文本老结构结论', linked['items'][1]['analysis'])

        week = self.client.get('/api/period-reviews/week/2026-09-W3/context').get_json()['data']['context']
        linked_w = week['linked_summaries']
        self.assertEqual(linked_w['kind'], 'monthly')
        self.assertEqual(linked_w['items'][0]['period_key'], '2026-08')
        self.assertIn('访客下滑 30%+', linked_w['items'][0]['analysis'])


if __name__ == '__main__': unittest.main(verbosity=2)
