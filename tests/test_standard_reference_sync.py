import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook

from scripts.enrich_products_from_standard_reference import build_enrichment, read_reference


class StandardReferenceSyncTests(unittest.TestCase):
    def test_single_product_sheet_directly_syncs_type_and_classification_tag(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            workbook_path = Path(temp_dir) / 'reference.xlsx'
            workbook = Workbook()
            default = workbook.active
            default.title = '单品'
            default.append([])
            default.append(['商品ID', '商品标题', '商品类目', '归类', '上架时间'])
            default.append([1001, '基础袜', '袜子', '标品袜子', '2026-05-01'])
            default.append([1002, '创意袜', '袜子', '非标', '2026-08-01'])
            dmp = workbook.create_sheet('DMP')
            dmp.append(['宝贝ID', '货品成长阶段'])
            dmp.append([1001, '成长期'])
            workbook.save(workbook_path)

            direct, growth = read_reference(workbook_path)
            updates, _ = build_enrichment([
                {'product_id': '1001', 'title': '基础袜', 'category': '袜子', 'list_date': '2026-05-01', 'product_type': '', 'product_tags': '手工标签'},
                {'product_id': '1002', 'title': '创意袜', 'category': '袜子', 'list_date': '2026-08-01', 'product_type': '', 'product_tags': ''},
                {'product_id': '9999', 'title': '未知商品', 'category': '', 'list_date': '', 'product_type': '非标品', 'product_tags': '已有标签'},
            ], direct, growth)

        rows = {row['product_id']: row for row in updates}
        self.assertEqual(rows['1001']['product_type'], '标品')
        self.assertIn('分类标签:标品', rows['1001']['product_tags'])
        self.assertIn('手工标签', rows['1001']['product_tags'])
        self.assertEqual(rows['1001']['product_growth_stage'], '成长期')
        self.assertEqual(rows['1002']['product_type'], '非标品')
        self.assertIn('分类标签:非标品', rows['1002']['product_tags'])
        self.assertEqual(rows['9999']['product_type'], '非标品')
        self.assertIn('分类标签:非标品', rows['9999']['product_tags'])


if __name__ == '__main__':
    unittest.main()
