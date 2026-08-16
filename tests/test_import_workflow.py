import io
import json
import os
import sys
import tempfile
import unittest
import warnings
from pathlib import Path
from threading import Event
from unittest.mock import patch
from zipfile import ZipFile

from openpyxl import Workbook


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def workbook_bytes(headers, rows):
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(headers)
    for row in rows:
        sheet.append(row)
    output = io.BytesIO()
    workbook.save(output)
    output.seek(0)
    return output


class ImportWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix='tmall-dashboard-import-tests-')
        self.database_path = os.path.join(self.temp_dir.name, 'dashboard.db')
        from app import create_app
        from db import get_db

        self.app = create_app({'TESTING': True, 'DATABASE_PATH': self.database_path})
        self.client = self.app.test_client()
        self.get_db = get_db

    def tearDown(self):
        self.temp_dir.cleanup()

    def preview(self, headers, rows):
        response = self.client.post(
            '/api/imports/preview',
            data={'file': (workbook_bytes(headers, rows), 'product-daily.xlsx')},
            content_type='multipart/form-data',
        )
        payload = response.get_json()
        response.close()
        return response.status_code, payload

    def test_legacy_upload_preserves_the_original_xls_suffix(self):
        completed = Event()
        captured = []

        def fake_import(path):
            captured.append(path)
            completed.set()
            return {'total_rows': 0}

        with patch('scripts.import_data.import_excel_file', side_effect=fake_import):
            response = self.client.post(
                '/api/upload/data',
                data={'file': (io.BytesIO(b'legacy-xls-content'), 'business-report.xls')},
                content_type='multipart/form-data',
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(completed.wait(timeout=2))
        self.assertEqual(Path(captured[0]).suffix, '.xls')

    def test_legacy_import_reads_gb18030_html_export_with_an_xls_extension(self):
        from scripts.import_data import read_workbook_sheets

        html = '''<html><meta charset="gb18030"><table>
            <tr><th>product_id</th><th>payment_amount</th></tr>
            <tr><td>p-001</td><td>100</td></tr>
        </table></html>'''
        path = os.path.join(self.temp_dir.name, 'business-report.xls')
        with open(path, 'wb') as output:
            output.write(html.encode('gb18030'))

        sheets = read_workbook_sheets(path)

        self.assertEqual(len(sheets), 1)
        self.assertEqual(list(sheets[0][1].columns), ['product_id', 'payment_amount'])
        self.assertEqual(sheets[0][1].iloc[0]['product_id'], 'p-001')

    def test_csv_import_reads_gb18030_content(self):
        from scripts.import_data import read_workbook_sheets

        path = os.path.join(self.temp_dir.name, 'business-report.csv')
        with open(path, 'wb') as output:
            output.write('商品ID,支付金额\nP-CSV,100\n'.encode('gb18030'))

        sheets = read_workbook_sheets(path)

        self.assertEqual(sheets[0][1].iloc[0].tolist(), ['商品ID', '支付金额'])
        self.assertEqual(sheets[0][1].iloc[1].tolist(), ['P-CSV', '100'])

    def test_zip_import_reads_csv_and_excel_entries(self):
        from scripts.import_data import read_workbook_sheets

        path = os.path.join(self.temp_dir.name, 'business-reports.zip')
        with ZipFile(path, 'w') as archive:
            archive.writestr('daily.csv', 'product_id,payment_amount\nP-CSV,100\n'.encode('utf-8'))
            archive.writestr('monthly.xlsx', workbook_bytes(['product_id', 'payment_amount'], [['P-XLSX', 200]]).read())

        sheets = read_workbook_sheets(path)

        self.assertEqual([name for name, _ in sheets], ['daily.csv:Sheet1', 'monthly.xlsx:Sheet'])
        self.assertEqual(sheets[0][1].iloc[1].tolist(), ['P-CSV', '100'])
        self.assertEqual(sheets[1][1].iloc[1].tolist(), ['P-XLSX', 200])

    def test_upload_accepts_csv_and_zip_files(self):
        for filename in ('business-report.csv', 'business-reports.zip'):
            with self.subTest(filename=filename), patch('scripts.import_data.import_excel_file', return_value={'total_rows': 0}):
                response = self.client.post(
                    '/api/upload/data',
                    data={'file': (io.BytesIO(b'content'), filename)},
                    content_type='multipart/form-data',
                )
            self.assertEqual(response.status_code, 200)

    def test_data_center_preview_accepts_csv(self):
        content = (
            'date,product_id,payment_amount,successful_refund_amount,'
            'product_visitors,payment_buyers,ad_spend\n'
            '2026-08-11,csv-product,100,5,20,2,8\n'
        ).encode('utf-8')

        response = self.client.post(
            '/api/imports/preview',
            data={'file': (io.BytesIO(content), 'product-daily.csv')},
            content_type='multipart/form-data',
        )

        self.assertEqual(response.status_code, 200)
        preview = response.get_json()['data']
        self.assertEqual(preview['source_filename'], 'product-daily.csv')
        self.assertEqual(preview['valid_rows'], 1)
        self.assertEqual(preview['required_unmapped'], [])

    def test_data_center_preview_accepts_zip_with_one_supported_table(self):
        content = io.BytesIO()
        with ZipFile(content, 'w') as archive:
            archive.writestr(
                'product-daily.csv',
                (
                    'date,product_id,payment_amount,successful_refund_amount,'
                    'product_visitors,payment_buyers,ad_spend\n'
                    '2026-08-11,zip-product,200,10,40,4,16\n'
                ).encode('utf-8'),
            )
        content.seek(0)

        response = self.client.post(
            '/api/imports/preview',
            data={'file': (content, 'product-daily.zip')},
            content_type='multipart/form-data',
        )

        self.assertEqual(response.status_code, 200)
        preview = response.get_json()['data']
        self.assertEqual(preview['source_filename'], 'product-daily.zip')
        self.assertEqual(preview['valid_rows'], 1)
        self.assertEqual(preview['required_unmapped'], [])

    def test_data_center_preview_detects_business_advisor_header_and_formatted_numbers(self):
        workbook = Workbook()
        sheet = workbook.active
        for _ in range(4):
            sheet.append([])
        headers = [
            '统计日期', '商品ID', '商品名称', '主商品ID', '商品类型', '货号', '商品状态', '商品标签',
            '商品访客数', '商品浏览量', '平均停留时长', '商品详情页跳出率', '商品收藏人数',
            '商品加购件数', '商品加购人数', '下单买家数', '下单件数', '下单金额', '下单转化率',
            '支付买家数', '支付件数', '支付金额', '商品支付转化率', '支付新买家数',
            '支付老买家数', '老买家支付金额', '聚划算支付金额', '访客平均价值', '成功退款金额',
            '竞争力评分', '年累计支付金额', '月累计支付金额', '月累计支付件数',
            '搜索引导支付转化率', '搜索引导访客数', '搜索引导支付买家数',
            '结构化详情引导转化率', '结构化详情引导成交占比',
        ]
        sheet.append(headers)
        sheet.append([
            20260811, '737559603417', '测试商品', '737559603417', '主商品', 'SKU-001', '当前在线', '重点',
            '6,069', '9,116', '8.38', '89.45%', '13', '999', '940', '305', '325', '12,653.00', '5.03%',
            '295', '313', '12,186.70', '4.86%', '243', '52', '2,372.90', '0.00', '2.01', '328.77',
            '-', '265,603.67', '12,534.51', '320', '42.86%', '7', '3', '-', '-',
        ])
        content = io.BytesIO()
        workbook.save(content)
        content.seek(0)

        response = self.client.post(
            '/api/imports/preview',
            data={'file': (content, 'business-advisor.xlsx')},
            content_type='multipart/form-data',
        )

        self.assertEqual(response.status_code, 200)
        preview = response.get_json()['data']
        self.assertEqual(preview['required_unmapped'], [])
        self.assertEqual(preview['valid_rows'], 1)
        self.assertEqual(preview['date_range'], {'start': '2026-08-11', 'end': '2026-08-11'})
        self.assertEqual(len(preview['mapping']), len(headers))
        self.assertTrue(all(field['matched'] for field in preview['fields']))

        confirmed = self.client.post('/api/imports', json={
            'preview_id': preview['id'], 'mapping': preview['mapping'],
        })
        self.assertEqual(confirmed.status_code, 201)
        confirmed.close()
        with self.get_db(self.database_path) as connection:
            daily = connection.execute(
                '''SELECT pv, payment_qty, payment_conversion, bounce_rate, avg_stay_duration,
                          cart_qty, cart_users, fav_users, order_amount, returning_payment_amount,
                          search_conversion, search_visitors
                   FROM daily_data WHERE product_id = '737559603417' AND date = '2026-08-11' '''
            ).fetchone()
            product = connection.execute(
                '''SELECT parent_product_id, product_type, sku_code, source_status, product_tags
                   FROM products WHERE product_id = '737559603417' '''
            ).fetchone()
        self.assertEqual(tuple(daily[:2]), (9116, 313))
        self.assertEqual(tuple(daily[4:9]), (8.38, 999, 940, 13, 12653.0))
        self.assertEqual(tuple(daily[9:10] + daily[11:]), (2372.9, 7))
        self.assertAlmostEqual(daily[2], .048608, places=6)
        self.assertAlmostEqual(daily[3], .8945, places=6)
        self.assertAlmostEqual(daily[10], .4286, places=6)
        self.assertEqual(tuple(product), ('737559603417', '主商品', 'SKU-001', '当前在线', '重点'))

    def test_product_list_preview_maps_all_fields_and_skips_summary_row(self):
        headers = [
            '宝贝ID', '宝贝名称', '货品成长阶段', '日期', '支付金额', 'IPV',
            '营销推广IPV', '营销推广消耗', '营销推广ROI', '收加率', '支付转化率',
            '复购率', '预售支付金额', '预售销量', '非推广IPV', '搜索IPV',
            '推荐IPV', '免费搜索点击率', '笔单价', '连带购买量', '连带购买率',
            '连带购买叶子类目宽度', '复购用户数',
        ]
        rows = [
            ['总计', '', '', '', '678,493.08', '476,835', '164,979', '103,478.66',
             '2.86', '7.79%', '3.81%', '686.56%', '0.00', '0', '317,837',
             '69,533', '64,027', '3.15%', '37.32', '3,328', '26.23%', '228', '13,094'],
            ['737559603417', '测试商品', '成长期', 20260803, '12,186.70', '9,116', '74',
             '100.50', '2.86', '10.99%', '3.37%', '4.50%', '20.00', '2', '9,035',
             '33', '38', '5.76%', '39.70', '3', '1.25%', '2', '4'],
        ]

        response = self.client.post(
            '/api/imports/preview',
            data={'file': (workbook_bytes(headers, rows), 'full-store-product-list.xlsx')},
            content_type='multipart/form-data',
        )

        self.assertEqual(response.status_code, 200)
        preview = response.get_json()['data']
        response.close()
        self.assertEqual(preview['required_unmapped'], [])
        self.assertEqual(preview['total_rows'], 1)
        self.assertEqual(preview['valid_rows'], 1)
        self.assertEqual(preview['invalid_rows'], 0)
        self.assertEqual(len(preview['mapping']), len(headers))
        self.assertTrue(all(field['matched'] for field in preview['fields']))
        self.assertEqual(preview['mapping']['product_growth_stage'], '货品成长阶段')
        self.assertEqual(preview['mapping']['paid_visitors'], '营销推广IPV')
        self.assertEqual(preview['mapping']['favorite_cart_rate'], '收加率')
        self.assertEqual(preview['mapping']['payment_unit_price'], '笔单价')
        self.assertEqual(preview['mapping']['cross_sell_categories'], '连带购买叶子类目宽度')

    def test_product_list_confirm_preserves_unavailable_metrics_and_writes_available_fields(self):
        base_headers = ['日期', '商品ID', '商品名称', '支付金额', '退款金额', '商品访客数', '支付买家数']
        _, base_preview = self.preview(
            base_headers,
            [['2026-08-03', 'product-list-a', '旧名称', 100, 11, 20, 5]],
        )
        base_confirm = self.client.post('/api/imports', json={
            'preview_id': base_preview['data']['id'],
            'mapping': base_preview['data']['mapping'],
        })
        self.assertEqual(base_confirm.status_code, 201)
        base_confirm.close()

        headers = [
            '宝贝ID', '宝贝名称', '货品成长阶段', '日期', '支付金额', 'IPV',
            '营销推广IPV', '营销推广消耗', '营销推广ROI', '收加率', '支付转化率',
            '复购率', '预售支付金额', '预售销量', '非推广IPV', '搜索IPV',
            '推荐IPV', '免费搜索点击率', '笔单价', '连带购买量', '连带购买率',
            '连带购买叶子类目宽度', '复购用户数',
        ]
        row = [
            'product-list-a', '新名称', '成长期', 20260803, '12,186.70', '9,116', '74',
            '100.50', '2.86', '10.99%', '3.37%', '4.50%', '20.00', '2', '9,035',
            '33', '38', '5.76%', '39.70', '3', '1.25%', '2', '4',
        ]
        preview_response = self.client.post(
            '/api/imports/preview',
            data={'file': (workbook_bytes(headers, [row]), 'full-store-product-list.xlsx')},
            content_type='multipart/form-data',
        )
        preview = preview_response.get_json()['data']
        preview_response.close()
        confirmed = self.client.post('/api/imports', json={
            'preview_id': preview['id'], 'mapping': preview['mapping'],
        })

        self.assertEqual(confirmed.status_code, 201)
        confirmed.close()
        with self.get_db(self.database_path) as connection:
            daily = connection.execute(
                '''SELECT payment_amount, refund_amount, buyers, ipv, paid_ipv, organic_ipv,
                          search_visitors, recommend_ipv, ad_spend, ad_roi, favorite_cart_rate,
                          payment_conversion, repurchase_rate, presale_amount, presale_qty,
                          search_click_rate, avg_order_value, cross_sell_qty, cross_sell_rate,
                          cross_sell_categories, repurchase_users
                   FROM daily_data WHERE product_id = 'product-list-a' AND date = '2026-08-03' '''
            ).fetchone()
            product = connection.execute(
                "SELECT title, product_growth_stage FROM products WHERE product_id = 'product-list-a'"
            ).fetchone()
        # 生意参谋的支付金额/IPV保持主源；DMP 只补齐推广和流量拆分字段。
        self.assertEqual(tuple(daily[:8]), (100.0, 11.0, 5, 20, 74, 9035, 33, 38))
        self.assertEqual(tuple(daily[8:10]), (100.5, 2.86))
        self.assertAlmostEqual(daily[10], .1099, places=6)
        self.assertAlmostEqual(daily[11], .25, places=6)
        self.assertAlmostEqual(daily[12], .045, places=6)
        self.assertEqual(tuple(daily[13:16]), (20.0, 2, .0576))
        self.assertEqual(tuple(daily[16:]), (20.0, 3, .0125, 2, 4))
        self.assertEqual(tuple(product), ('旧名称', '成长期'))

    def test_dmp_confirm_skips_invalid_percentage_field_and_keeps_valid_metrics(self):
        headers = [
            'product_id', 'date', 'payment_amount', 'product_visitors',
            'presale_qty', 'favorite_cart_rate', 'paid_visitors',
        ]
        rows = [['dmp-warning', '2026-08-03', '100', '20', '2', '766.67%', '7']]
        response = self.client.post(
            '/api/imports/preview?source_type=dmp_product_day',
            data={'file': (workbook_bytes(headers, rows), 'dmp-warning.xlsx')},
            content_type='multipart/form-data',
        )
        self.assertEqual(response.status_code, 200)
        preview_payload = response.get_json()
        preview = preview_payload['data']
        response.close()
        self.assertEqual(preview_payload['availability'], 'partial')
        self.assertEqual(preview['invalid_rows'], 0)
        self.assertEqual(preview['invalid_field_count'], 1)
        self.assertEqual(preview['field_warnings'][0]['standard_field'], 'favorite_cart_rate')

        confirmed = self.client.post('/api/imports', json={
            'preview_id': preview['id'], 'mapping': preview['mapping'],
        })
        self.assertEqual(confirmed.status_code, 201)
        confirmed.close()
        with self.get_db(self.database_path) as connection:
            fact = connection.execute(
                "SELECT payment_amount, ipv, presale_qty, paid_ipv FROM daily_data WHERE product_id = 'dmp-warning'"
            ).fetchone()
            observation = connection.execute(
                "SELECT payload_json FROM daily_data_observations WHERE product_id = 'dmp-warning'"
            ).fetchone()[0]
            invalid_lineage = connection.execute(
                "SELECT COUNT(*) FROM fact_field_lineage WHERE product_id = 'dmp-warning' AND field_key = 'favorite_cart_rate'"
            ).fetchone()[0]
        self.assertEqual(tuple(fact), (100.0, 20, 2, 7))
        self.assertNotIn('favorite_cart_rate', observation)
        self.assertEqual(invalid_lineage, 0)

    def test_preview_does_not_write_and_identifies_unmapped_required_field(self):
        status, payload = self.preview(
            ['日期', '商品ID', '支付金额', '退款金额', '商品访客数', '支付买家数'],
            [['2026-04-01', 'import-a', 100, 10, 20, 3]],
        )

        self.assertEqual(status, 200)
        self.assertTrue(payload['ok'])
        self.assertEqual(payload['data']['source_type'], 'product_day')
        self.assertEqual(payload['data']['required_unmapped'], [])
        with self.get_db(self.database_path) as connection:
            facts = connection.execute('SELECT COUNT(*) FROM daily_data').fetchone()[0]
            batches = connection.execute('SELECT COUNT(*) FROM import_batches').fetchone()[0]
        self.assertEqual(facts, 0)
        self.assertEqual(batches, 0)

    def test_preview_applies_saved_mapping_template(self):
        response = self.client.post(
            '/api/imports/preview?source_type=product_day',
            data={
                'file': (workbook_bytes(['日期', '商品编号', '支付金额', '退款金额', '访客数', '买家数', '推广花费'], [['2026-04-01', 'template-p', 10, 1, 10, 2, 1]]), 'template.xlsx'),
                'mapping_template': '{"date":"日期","product_id":"商品编号","payment_amount":"支付金额","successful_refund_amount":"退款金额","product_visitors":"访客数","payment_buyers":"买家数","ad_spend":"推广花费"}',
            },
            content_type='multipart/form-data',
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()['data']
        self.assertEqual(data['required_unmapped'], [])
        self.assertTrue(all(field['match_status'] in {'template', 'exact'} for field in data['fields'] if field['standard_key']))
        self.assertTrue(all(field['inferred_type'] in {'date', 'integer', 'decimal', 'text', 'empty'} for field in data['fields']))
        self.assertTrue(all(key in data['invalid_details'][0] for key in ('row_number', 'standard_field', 'raw_value', 'reason')) if data['invalid_details'] else True)

    def test_preview_rejects_malformed_mapping_template(self):
        response = self.client.post(
            '/api/imports/preview',
            data={
                'file': (workbook_bytes(['date'], [['2026-04-01']]), 'invalid-template.xlsx'),
                'mapping_template': '{not-json',
            },
            content_type='multipart/form-data',
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.get_json()['code'], 'VALIDATION_ERROR')
        response.close()

    def test_confirm_works_after_import_service_is_recreated(self):
        from services.import_service import ImportService

        content = workbook_bytes(
            ['日期', '商品ID', '商品名称', '支付金额', '退款金额', '商品访客数', '支付买家数', '推广花费'],
            [['2026-08-12', 'DEMO-RESTART', '重启恢复商品', 1000, 50, 100, 10, 100]],
        ).read()
        with self.app.app_context():
            preview = ImportService().preview('restart.xlsx', content)
            result = ImportService().confirm(preview['id'], preview['mapping'])

        self.assertEqual(result['inserted_count'], 1)

    def test_import_service_preview_reads_gb18030_html_xls_exports(self):
        from services.import_service import ImportService

        html = '''<html><meta charset="gb18030"><table>
            <tr><th>date</th><th>product_id</th><th>payment_amount</th><th>product_visitors</th></tr>
            <tr><td>2026-08-01</td><td>html-xls</td><td>100</td><td>10</td></tr>
        </table></html>'''
        with self.app.app_context():
            preview = ImportService().preview('legacy-report.xls', html.encode('gb18030'))

        self.assertEqual(preview['source_type'], 'product_day')
        self.assertEqual(preview['valid_rows'], 1)
        self.assertEqual(preview['mapping']['product_id'], 'product_id')

    def test_confirm_requires_mapping_and_is_idempotent_by_business_key(self):
        headers = ['日期', '商品ID', '商品名称', '支付金额', '退款金额', '商品访客数', '支付买家数', '推广花费']
        rows = [['2026-04-01', 'import-a', '导入商品', 100, 10, 20, 3, 20]]
        status, preview = self.preview(headers, rows)
        self.assertEqual(status, 200)
        preview_id = preview['data']['id']

        missing_mapping = self.client.post('/api/imports', json={'preview_id': preview_id, 'mapping': {}})
        self.assertEqual(missing_mapping.status_code, 422)
        missing_mapping.close()

        first = self.client.post('/api/imports', json={
            'preview_id': preview_id,
            'mapping': preview['data']['mapping'],
        })
        first_payload = first.get_json()
        first.close()
        self.assertEqual(first.status_code, 201)
        self.assertTrue(first_payload['ok'])
        self.assertEqual(first_payload['data']['inserted_count'], 1)

        _, second_preview = self.preview(headers, [['2026-04-01', 'import-a', '导入商品', 120, 10, 20, 3, 30]])
        second = self.client.post('/api/imports', json={
            'preview_id': second_preview['data']['id'],
            'mapping': second_preview['data']['mapping'],
        })
        second_payload = second.get_json()
        second.close()
        self.assertEqual(second.status_code, 201)
        self.assertEqual(second_payload['data']['updated_count'], 1)

        with self.get_db(self.database_path) as connection:
            facts = connection.execute('SELECT COUNT(*) FROM daily_data').fetchone()[0]
            payment_amount = connection.execute(
                'SELECT payment_amount FROM daily_data WHERE product_id = ? AND date = ?',
                ('import-a', '2026-04-01'),
            ).fetchone()[0]
            batches = connection.execute("SELECT COUNT(*) FROM import_batches WHERE status = 'completed'").fetchone()[0]
        self.assertEqual(facts, 1)
        self.assertEqual(payment_amount, 120.0)
        self.assertEqual(batches, 2)

    def test_preview_accepts_explicit_mapping_and_batch_can_be_reverted(self):
        headers = ['统计日', '商品编号', '成交额', '退款额', '访客', '买家', '消耗']
        rows = [['2026-04-02', 'import-revert', 300, 30, 100, 10, 50]]
        response = self.client.post(
            '/api/imports/preview?source_type=product_day',
            data={'file': (workbook_bytes(headers, rows), 'custom.xlsx')},
            content_type='multipart/form-data',
        )
        preview = response.get_json()['data']
        response.close()
        mapping = {
            'date': '统计日', 'product_id': '商品编号', 'payment_amount': '成交额',
            'successful_refund_amount': '退款额', 'product_visitors': '访客',
            'payment_buyers': '买家', 'ad_spend': '消耗',
        }
        confirmed = self.client.post('/api/imports', json={'preview_id': preview['id'], 'mapping': mapping})
        batch_id = confirmed.get_json()['data']['id']
        confirmed.close()

        history = self.client.get('/api/imports')
        self.assertEqual(history.status_code, 200)
        self.assertEqual(history.get_json()['data'][0]['id'], batch_id)
        history.close()

        reverted = self.client.post(f'/api/imports/{batch_id}/revert')
        self.assertEqual(reverted.status_code, 200)
        self.assertTrue(reverted.get_json()['data']['reverted'])
        reverted.close()
        with self.get_db(self.database_path) as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM daily_data WHERE product_id = 'import-revert'").fetchone()[0], 0)

    def test_store_daily_source_is_imported_by_business_key(self):
        status, preview = self.preview(['日期', '支付金额', '退款金额', '商品访客数', '支付买家数'], [['2026-04-03', 500, 50, 100, 20]])
        self.assertEqual(status, 200)
        response = self.client.post('/api/imports/preview?source_type=store_day', data={'file': (workbook_bytes(['日期', '支付金额', '退款金额', '商品访客数', '支付买家数'], [['2026-04-03', 500, 50, 100, 20]]), 'store.xlsx')}, content_type='multipart/form-data')
        preview = response.get_json()['data']; response.close()
        confirmed = self.client.post('/api/imports', json={'preview_id': preview['id'], 'mapping': preview['mapping']})
        self.assertEqual(confirmed.status_code, 201); confirmed.close()
        with self.get_db(self.database_path) as connection:
            row = connection.execute("SELECT payment_amount, payment_buyers FROM store_daily_facts WHERE date = '2026-04-03'").fetchone()
        self.assertEqual(tuple(row), (500.0, 20))

    def test_promotion_and_customer_sources_use_their_own_required_fields_and_quality_keys(self):
        promotion = self.client.post(
            '/api/imports/preview?source_type=promotion_campaign_day',
            data={'file': (workbook_bytes(
                ['date', 'channel', 'campaign_id', 'ad_spend', 'attributed_payment_amount'],
                [['2026-04-05', 'search', 'campaign-a', 12, 60]],
            ), 'promotion.xlsx')}, content_type='multipart/form-data',
        )
        payload = promotion.get_json()['data']; promotion.close()
        self.assertEqual(payload['valid_rows'], 1)
        self.assertEqual(payload['invalid_rows'], 0)
        self.assertEqual(payload['required_unmapped'], [])
        self.assertIn('campaign_id', payload['mapping_schema']['required'])
        self.assertNotIn('product_id', payload['mapping_schema']['required'])

        confirmed = self.client.post('/api/imports', json={'preview_id': payload['id'], 'mapping': payload['mapping']})
        self.assertEqual(confirmed.status_code, 201); confirmed.close()
        with self.get_db(self.database_path) as connection:
            row = connection.execute(
                "SELECT channel, campaign_id, attributed_payment_amount FROM promotion_daily_facts"
            ).fetchone()
        self.assertEqual(tuple(row), ('search', 'campaign-a', 60.0))

    def test_promotion_observation_remains_primary_when_dmp_is_imported_afterwards(self):
        promotion = self.client.post(
            '/api/imports/preview?source_type=promotion_product_day',
            data={'file': (workbook_bytes(
                ['date', 'channel', 'product_id', 'ad_spend', 'attributed_payment_amount'],
                [['2026-04-05', 'search', 'promotion-primary', 12, 60]],
            ), 'promotion-product.xlsx')}, content_type='multipart/form-data',
        )
        promotion_preview = promotion.get_json()['data']; promotion.close()
        confirmed = self.client.post('/api/imports', json={
            'preview_id': promotion_preview['id'], 'mapping': promotion_preview['mapping'],
        })
        self.assertEqual(confirmed.status_code, 201); confirmed.close()

        dmp = self.client.post(
            '/api/imports/preview?source_type=dmp_product_day',
            data={'file': (workbook_bytes(
                ['product_id', 'date', 'payment_amount', 'product_visitors', 'ad_spend', 'ad_roi'],
                [['promotion-primary', '2026-04-05', 100, 10, 99, 9]],
            ), 'dmp-product.xlsx')}, content_type='multipart/form-data',
        )
        dmp_preview = dmp.get_json()['data']; dmp.close()
        confirmed = self.client.post('/api/imports', json={
            'preview_id': dmp_preview['id'], 'mapping': dmp_preview['mapping'],
        })
        self.assertEqual(confirmed.status_code, 201); confirmed.close()

        with self.get_db(self.database_path) as connection:
            row = connection.execute(
                "SELECT ad_spend, ad_roi FROM daily_data WHERE product_id = 'promotion-primary'"
            ).fetchone()
        self.assertEqual(tuple(row), (12.0, 5.0))

    def test_reverting_product_batch_removes_observations_and_lineage(self):
        status, preview = self.preview(
            ['product_id', 'date', 'payment_amount', 'product_visitors'],
            [['revert-observation', '2026-04-06', 100, 10]],
        )
        self.assertEqual(status, 200)
        confirmed = self.client.post('/api/imports', json={
            'preview_id': preview['data']['id'], 'mapping': preview['data']['mapping'],
        })
        self.assertEqual(confirmed.status_code, 201)
        batch_id = confirmed.get_json()['data']['id']; confirmed.close()
        reverted = self.client.post(f'/api/imports/{batch_id}/revert')
        self.assertEqual(reverted.status_code, 200); reverted.close()
        with self.get_db(self.database_path) as connection:
            self.assertEqual(connection.execute(
                'SELECT COUNT(*) FROM daily_data_observations WHERE source_batch_id = ?', (batch_id,)
            ).fetchone()[0], 0)
            self.assertEqual(connection.execute(
                "SELECT COUNT(*) FROM fact_field_lineage WHERE product_id = 'revert-observation'"
            ).fetchone()[0], 0)

    def test_confirm_rejects_duplicate_source_columns(self):
        status, preview = self.preview(
            ['product_id', 'date', 'value'],
            [['duplicate-column', '2026-04-07', 100]],
        )
        self.assertEqual(status, 200)
        response = self.client.post('/api/imports', json={
            'preview_id': preview['data']['id'],
            'mapping': {
                'product_id': 'product_id', 'date': 'date',
                'payment_amount': 'value', 'product_visitors': 'value',
            },
        })
        self.assertEqual(response.status_code, 422)

    def test_auto_preview_detects_tmall_campaign_report_and_imports_it(self):
        content = io.BytesIO()
        with ZipFile(content, 'w') as archive:
            archive.writestr(
                '计划报表.csv',
                (
                    '日期,场景ID,场景名字,计划ID,计划名字,展现量,点击量,花费,'
                    '直接成交金额,间接成交金额,总成交金额\n'
                    '2026-08-10,371,关键词推广,82520659557,测试计划,235,18,81.91,120,80,200\n'
                ).encode('utf-8'),
            )
        content.seek(0)
        response = self.client.post(
            '/api/imports/preview?source_type=auto',
            data={'file': (content, '计划报表_20260811_173656.zip')},
            content_type='multipart/form-data',
        )
        self.assertEqual(response.status_code, 200)
        preview = response.get_json()['data']
        response.close()
        self.assertEqual(preview['source_type'], 'promotion_campaign_day')
        self.assertEqual(preview['required_unmapped'], [])
        self.assertEqual(preview['valid_rows'], 1)
        self.assertEqual(preview['mapping']['channel'], '场景名字')
        self.assertEqual(preview['mapping']['attributed_payment_amount'], '总成交金额')

        confirmed = self.client.post('/api/imports', json={
            'preview_id': preview['id'],
            'mapping': preview['mapping'],
        })
        self.assertEqual(confirmed.status_code, 201)
        confirmed.close()
        with self.get_db(self.database_path) as connection:
            row = connection.execute(
                '''SELECT channel, campaign_id, ad_spend, attributed_payment_amount,
                          impressions, clicks, direct_payment_amount, indirect_payment_amount
                   FROM promotion_daily_facts'''
            ).fetchone()
        self.assertEqual(tuple(row), ('关键词推广', '82520659557', 81.91, 200.0, 235, 18, 120.0, 80.0))

    def test_invalid_generic_rows_are_reported_and_rejected_before_a_batch_is_written(self):
        response = self.client.post(
            '/api/imports/preview?source_type=customer_day',
            data={'file': (workbook_bytes(
                ['date', 'payment_buyers', 'returning_payment_buyers'],
                [['not-a-date', 10, 4]],
            ), 'customers.xlsx')}, content_type='multipart/form-data',
        )
        preview = response.get_json()['data']; response.close()
        self.assertEqual(preview['valid_rows'], 0)
        self.assertEqual(preview['invalid_rows'], 1)
        self.assertTrue(preview['invalid_details'])
        confirmed = self.client.post('/api/imports', json={'preview_id': preview['id'], 'mapping': preview['mapping']})
        self.assertEqual(confirmed.status_code, 422); confirmed.close()
        with self.get_db(self.database_path) as connection:
            self.assertEqual(connection.execute('SELECT COUNT(*) FROM import_batches').fetchone()[0], 0)

    def test_preview_reports_inferred_types_match_statuses_and_structured_invalid_details(self):
        rows = [
            ['not-a-date', f'bad-{index}', 'bad-number', 0, 10, 1, 2]
            for index in range(30)
        ]
        status, payload = self.preview(
            ['date', 'product_id', 'payment_amount', 'successful_refund_amount',
             'product_visitors', 'payment_buyers', 'ad_spend'],
            rows,
        )
        self.assertEqual(status, 200)
        data = payload['data']
        fields = {field['source_column']: field for field in data['fields']}
        self.assertEqual(fields['date']['match_status'], 'exact')
        self.assertEqual(fields['date']['inferred_type'], 'text')
        self.assertEqual(fields['product_visitors']['inferred_type'], 'integer')
        self.assertEqual(fields['ad_spend']['inferred_type'], 'integer')
        self.assertEqual(len(data['invalid_details']), 25)
        self.assertEqual(
            set(data['invalid_details'][0]),
            {'row_number', 'standard_field', 'raw_value', 'reason'},
        )
        self.assertEqual(data['invalid_details'][0]['row_number'], 2)
        self.assertEqual(data['invalid_details'][0]['standard_field'], 'date')
        self.assertEqual(data['invalid_details'][0]['raw_value'], 'not-a-date')

    def test_infer_type_handles_mixed_date_text_without_pandas_warning(self):
        import pandas as pd
        from services.import_service import ImportService

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            inferred = ImportService._infer_type(pd.Series(['2026年08月01日', '2026年08月02日']))

        self.assertEqual(inferred, 'text')
        self.assertFalse(
            any('Could not infer format' in str(item.message) for item in caught),
        )

    def test_expired_previews_are_removed_from_database_and_memory(self):
        from datetime import timedelta
        from services.import_service import ImportService

        with self.app.app_context():
            service = ImportService()
            service.previews['expired-memory'] = {'id': 'expired-memory'}
            with self.get_db(self.database_path) as connection:
                connection.execute(
                    '''INSERT INTO import_previews
                       (id, source_type, source_filename, source_hash, content, mapping_json, quality_summary, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now', '-2 hours'))''',
                    ('expired-db', 'product_day', 'expired.xlsx', 'hash', b'content', '{}', '{}'),
                )
                connection.commit()

            removed = service.cleanup_expired_previews(ttl_seconds=timedelta(hours=1).total_seconds())

            self.assertEqual(removed, 2)
            self.assertNotIn('expired-memory', service.previews)
            with self.get_db(self.database_path) as connection:
                self.assertIsNone(connection.execute('SELECT id FROM import_previews WHERE id = ?', ('expired-db',)).fetchone())

    def test_confirm_and_history_return_complete_result_report(self):
        headers = ['date', 'product_id', 'payment_amount', 'successful_refund_amount',
                   'product_visitors', 'payment_buyers', 'ad_spend']
        status, preview = self.preview(headers, [['2026-04-06', 'report-a', 100, 5, 20, 2, 8]])
        self.assertEqual(status, 200)
        confirmed = self.client.post('/api/imports', json={
            'preview_id': preview['data']['id'],
            'mapping': preview['data']['mapping'],
        })
        self.assertEqual(confirmed.status_code, 201)
        report = confirmed.get_json()['data']
        confirmed.close()
        expected = {
            'id', 'source_type', 'source_filename', 'source_hash', 'date_range',
            'inserted_count', 'updated_count', 'skipped_count', 'invalid_count',
            'quality_conclusion', 'completed_at', 'audit_url',
        }
        self.assertTrue(expected <= set(report))
        self.assertEqual(report['source_type'], 'product_day')
        self.assertEqual(report['source_filename'], 'product-daily.xlsx')
        self.assertEqual(len(report['source_hash']), 64)
        self.assertEqual(report['date_range'], {'start': '2026-04-06', 'end': '2026-04-06'})
        self.assertEqual(report['skipped_count'], 0)
        self.assertEqual(report['invalid_count'], 0)
        self.assertEqual(report['quality_conclusion'], 'passed')
        self.assertEqual(report['audit_url'], f"/api/imports/{report['id']}/audit")

        history = self.client.get('/api/imports').get_json()['data']
        self.assertTrue(expected <= set(history[0]))
        self.assertEqual(history[0]['id'], report['id'])

    def test_reverting_older_batch_skips_newer_fact_and_restores_uncovered_fact(self):
        headers = ['日期', '商品ID', '商品名称', '支付金额', '退款金额', '商品访客数', '支付买家数', '推广花费']
        def import_rows(rows):
            _, preview = self.preview(headers, rows)
            response = self.client.post('/api/imports', json={'preview_id': preview['data']['id'], 'mapping': preview['data']['mapping']})
            payload = response.get_json(); response.close(); return payload['data']['id']
        older = import_rows([
            ['2026-04-04', 'import-order', '顺序商品', 100, 0, 10, 2, 1],
            ['2026-04-04', 'import-uncovered', '未覆盖商品', 80, 0, 8, 1, 1],
        ])
        import_rows([['2026-04-04', 'import-order', '顺序商品', 200, 0, 10, 2, 1]])
        response = self.client.post(f'/api/imports/{older}/revert')
        self.assertEqual(response.status_code, 200)
        result = response.get_json()['data']
        self.assertEqual(result['restored_count'], 1)
        self.assertEqual(result['skipped_count'], 1)
        response.close()
        with self.get_db(self.database_path) as connection:
            self.assertEqual(connection.execute("SELECT payment_amount FROM daily_data WHERE product_id='import-order' AND date='2026-04-04'").fetchone()[0], 200.0)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM daily_data WHERE product_id='import-uncovered' AND date='2026-04-04'").fetchone()[0], 0)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM import_batch_changes WHERE batch_id = ?", (older,)).fetchone()[0], 2)
            audit = connection.execute(
                "SELECT action, operator, reason, before_value, after_value FROM audit_logs WHERE entity_type = 'import_batch' AND entity_id = ?",
                (older,),
            ).fetchone()
            self.assertEqual(audit[0], 'revert')
            self.assertEqual(audit[1], 'admin')
            self.assertIn('restored_count', audit[4])

    def test_revert_reopens_completed_action_without_erasing_result_or_review(self):
        headers = ['date', 'product_id', 'payment_amount', 'successful_refund_amount',
                   'product_visitors', 'payment_buyers', 'ad_spend']
        _, preview = self.preview(headers, [['2026-04-08', 'action-import', 300, 20, 100, 10, 30]])
        confirmed = self.client.post('/api/imports', json={
            'preview_id': preview['data']['id'], 'mapping': preview['data']['mapping'],
        })
        self.assertEqual(confirmed.status_code, 201)
        batch_id = confirmed.get_json()['data']['id']
        confirmed.close()

        with self.get_db(self.database_path) as connection:
            connection.execute(
                '''INSERT INTO product_actions
                   (id, product_id, purpose_type, purpose_note, action_type, action_detail,
                    target_metric, status, planned_at, before_metric_value, after_metric_value,
                    result_change, calculation_note, review_effective, review_reason,
                    review_conclusion, review_next_action, reviewed_by, reviewed_at,
                    observer_window_days, version)
                   VALUES ('revert-action', 'action-import', 'increase_sales', '验证撤销联动',
                    'image_change', '更换主图', 'payment_amount', 'completed', '2026-04-01',
                    100, 130, .3, '原计算说明', 1, '转化提升', '动作有效',
                    '继续放量', 'operator', '2026-04-10', 7, 7)'''
            )
            connection.commit()

        reverted = self.client.post(f'/api/imports/{batch_id}/revert')
        self.assertEqual(reverted.status_code, 200)
        reverted.close()
        with self.get_db(self.database_path) as connection:
            action = connection.execute(
                '''SELECT status, before_metric_value, after_metric_value, result_change,
                          review_effective, review_reason, review_conclusion, review_next_action,
                          reviewed_by, reviewed_at, version, calculation_note
                   FROM product_actions WHERE id = 'revert-action' '''
            ).fetchone()
            history = connection.execute(
                '''SELECT from_status, to_status, version FROM product_action_history
                   WHERE action_id = 'revert-action' ORDER BY id DESC LIMIT 1'''
            ).fetchone()
        self.assertEqual(action[0], 'pending_review')
        self.assertEqual(tuple(action[1:10]), (100.0, 130.0, .3, 1, '转化提升', '动作有效', '继续放量', 'operator', '2026-04-10'))
        self.assertEqual(action[10], 8)
        self.assertIn('原结果已失效', action[11])
        self.assertEqual(tuple(history), ('completed', 'pending_review', 8))

    def test_partial_revert_can_finish_after_newer_batch_is_reverted(self):
        headers = ['date', 'product_id', 'payment_amount', 'successful_refund_amount',
                   'product_visitors', 'payment_buyers', 'ad_spend']
        def import_row(amount):
            _, preview = self.preview(headers, [['2026-04-09', 'revert-chain', amount, 0, 10, 2, 1]])
            response = self.client.post('/api/imports', json={
                'preview_id': preview['data']['id'], 'mapping': preview['data']['mapping'],
            })
            batch_id = response.get_json()['data']['id']; response.close(); return batch_id

        older = import_row(100)
        newer = import_row(200)
        first = self.client.post(f'/api/imports/{older}/revert')
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.get_json()['data']['skipped_count'], 1)
        first.close()
        self.assertEqual(self.client.post(f'/api/imports/{newer}/revert').status_code, 200)
        second = self.client.post(f'/api/imports/{older}/revert')
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.get_json()['data']['restored_count'], 1)
        second.close()
        with self.get_db(self.database_path) as connection:
            self.assertEqual(connection.execute(
                "SELECT COUNT(*) FROM daily_data WHERE product_id='revert-chain'"
            ).fetchone()[0], 0)

    def test_revert_does_not_delete_value_owned_by_partially_reverted_newer_batch(self):
        headers = ['date', 'product_id', 'payment_amount', 'successful_refund_amount',
                   'product_visitors', 'payment_buyers', 'ad_spend']

        def import_row(amount):
            _, preview = self.preview(headers, [['2026-04-10', 'revert-owner', amount, 0, 10, 2, 1]])
            response = self.client.post('/api/imports', json={
                'preview_id': preview['data']['id'], 'mapping': preview['data']['mapping'],
            })
            batch_id = response.get_json()['data']['id']
            response.close()
            return batch_id

        oldest = import_row(100)
        middle = import_row(200)
        newest = import_row(300)
        self.assertEqual(self.client.post(f'/api/imports/{oldest}/revert').status_code, 200)
        self.assertEqual(self.client.post(f'/api/imports/{middle}/revert').status_code, 200)
        self.assertEqual(self.client.post(f'/api/imports/{newest}/revert').status_code, 200)

        retried = self.client.post(f'/api/imports/{oldest}/revert')
        self.assertEqual(retried.status_code, 200)
        self.assertEqual(retried.get_json()['data']['skipped_count'], 1)
        retried.close()
        with self.get_db(self.database_path) as connection:
            amount = connection.execute(
                "SELECT payment_amount FROM daily_data WHERE product_id = 'revert-owner' AND date = '2026-04-10'"
            ).fetchone()[0]
        self.assertEqual(amount, 200.0)

    def test_revert_only_reopens_actions_whose_observation_window_intersects(self):
        headers = ['date', 'product_id', 'payment_amount', 'successful_refund_amount',
                   'product_visitors', 'payment_buyers', 'ad_spend']
        _, preview = self.preview(headers, [['2026-04-08', 'window-product', 300, 0, 10, 2, 1]])
        response = self.client.post('/api/imports', json={
            'preview_id': preview['data']['id'], 'mapping': preview['data']['mapping'],
        })
        batch_id = response.get_json()['data']['id']; response.close()
        with self.get_db(self.database_path) as connection:
            for action_id, planned_at, status in (
                ('window-hit', '2026-04-01', 'completed'),
                ('window-miss', '2026-05-01', 'completed'),
                ('window-executing', '2026-04-01', 'executing'),
            ):
                connection.execute(
                    '''INSERT INTO product_actions
                       (id, product_id, purpose_type, purpose_note, action_type, action_detail,
                        target_metric, status, planned_at, observer_window_days, version)
                       VALUES (?, 'window-product', 'increase_sales', '窗口测试', 'image_change',
                        '更换主图', 'payment_amount', ?, ?, 14, 1)''',
                    (action_id, status, planned_at),
                )
            connection.commit()
        self.assertEqual(self.client.post(f'/api/imports/{batch_id}/revert').status_code, 200)
        with self.get_db(self.database_path) as connection:
            statuses = dict(connection.execute(
                "SELECT id, status FROM product_actions WHERE product_id='window-product'"
            ).fetchall())
        self.assertEqual(statuses['window-hit'], 'pending_review')
        self.assertEqual(statuses['window-miss'], 'completed')
        self.assertEqual(statuses['window-executing'], 'observing')

    def test_revert_reopens_action_when_fact_intersects_before_window(self):
        headers = ['date', 'product_id', 'payment_amount', 'successful_refund_amount',
                   'product_visitors', 'payment_buyers', 'ad_spend']
        _, preview = self.preview(headers, [['2026-03-30', 'before-window-product', 300, 0, 10, 2, 1]])
        response = self.client.post('/api/imports', json={
            'preview_id': preview['data']['id'], 'mapping': preview['data']['mapping'],
        })
        batch_id = response.get_json()['data']['id']
        response.close()
        with self.get_db(self.database_path) as connection:
            connection.execute(
                '''INSERT INTO product_actions
                   (id, product_id, purpose_type, purpose_note, action_type, action_detail,
                    target_metric, status, planned_at, executed_at, observer_window_days, version)
                   VALUES ('before-window-hit', 'before-window-product', 'increase_sales', '窗口测试',
                    'image_change', '更换主图', 'payment_amount', 'completed', '2026-04-01',
                    '2026-04-01', 14, 1)'''
            )
            connection.commit()

        self.assertEqual(self.client.post(f'/api/imports/{batch_id}/revert').status_code, 200)
        with self.get_db(self.database_path) as connection:
            action = connection.execute(
                "SELECT status, version FROM product_actions WHERE id = 'before-window-hit'"
            ).fetchone()
        self.assertEqual(tuple(action), ('pending_review', 2))

    def test_confirm_report_and_observation_keep_batch_quality_lineage(self):
        headers = [
            'date', 'product_id', 'payment_amount',
            'successful_refund_amount', 'product_visitors', 'payment_buyers',
        ]
        status, preview = self.preview(
            headers,
            [['2026-08-12', 'metadata-product', 123.4, 3.4, 20, 2]],
        )
        self.assertEqual(status, 200)

        response = self.client.post('/api/imports', json={
            'preview_id': preview['data']['id'],
            'mapping': preview['data']['mapping'],
        })
        self.assertEqual(response.status_code, 201)
        report = response.get_json()['data']
        response.close()

        self.assertEqual(report['source_type'], 'product_day')
        self.assertEqual(report['quality_conclusion'], 'passed')
        self.assertEqual(report['quality_summary']['total_rows'], 1)
        self.assertEqual(report['quality_summary']['valid_rows'], 1)
        self.assertEqual(report['quality_summary']['invalid_rows'], 0)
        self.assertEqual(report['quality_summary']['duplicate_keys'], 0)

        with self.get_db(self.database_path) as connection:
            observation = connection.execute(
                '''SELECT shop_id, product_id, date, source_type, source_batch_id,
                          payload_json
                   FROM daily_data_observations
                   WHERE product_id = 'metadata-product' '''
            ).fetchone()
        self.assertEqual(tuple(observation[:5]), (
            'default', 'metadata-product', '2026-08-12', 'product_day', report['id'],
        ))
        payload = json.loads(observation['payload_json'])
        self.assertEqual(payload['payment_amount'], 123.4)
        self.assertEqual(payload['successful_refund_amount'], 3.4)
        self.assertEqual(payload['product_visitors'], 20)

    def test_dmp_preview_comparisons_are_scoped_to_requested_shop(self):
        from services.source_resolution_service import record_daily_observation

        with self.app.app_context():
            with self.get_db(self.database_path) as connection:
                record_daily_observation(
                    connection,
                    {'product_id': 'scope-dmp', 'date': '2026-08-01',
                     'payment_amount': 100, 'product_visitors': 10},
                    source_type='product_day', source_batch_id='default-ba',
                    source_system='business_advisor', shop_id='default',
                )
                record_daily_observation(
                    connection,
                    {'product_id': 'scope-dmp', 'date': '2026-08-01',
                     'payment_amount': 200, 'product_visitors': 20},
                    source_type='product_day', source_batch_id='shop-a-ba',
                    source_system='business_advisor', shop_id='shop-a',
                )
                connection.commit()

        response = self.client.post(
            '/api/imports/preview?shop_id=shop-a&source_type=dmp_product_day',
            data={'file': (workbook_bytes(
                ['date', 'product_id', 'payment_amount', 'product_visitors', 'paid_visitors'],
                [['2026-08-01', 'scope-dmp', 50, 5, 2]],
            ), 'scope-dmp.xlsx')},
            content_type='multipart/form-data',
        )
        self.assertEqual(response.status_code, 200)
        preview = response.get_json()['data']
        response.close()

        comparisons = preview['source_resolution']['field_comparisons']
        payment = next(item for item in comparisons if item['field_key'] == 'payment_amount')
        self.assertEqual(payment['business_advisor_value'], 200)


if __name__ == '__main__':
    unittest.main(verbosity=2)
