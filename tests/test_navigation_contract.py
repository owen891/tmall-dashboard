import pathlib
import re
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class NavigationContractTests(unittest.TestCase):
    def read(self, relative_path):
        return (ROOT / relative_path).read_text(encoding='utf-8')

    def test_navigation_helper_serializes_supported_context_only(self):
        content = self.read('frontend/ui_demo/assets/navigation.js')
        self.assertIn('window.DemoNavigation', content)
        self.assertIn("'product_id'", content)
        self.assertIn("'lifecycle_stage'", content)
        self.assertIn("'promotion_channel'", content)
        self.assertIn('function build(', content)

    def test_all_dialogs_and_drawers_declare_modal_kind(self):
        allowed = {'detail', 'edit', 'config', 'flow'}
        for page in (ROOT / 'frontend/ui_demo/pages').glob('*.html'):
            content = page.read_text(encoding='utf-8')
            for match in re.finditer(r'<(?:dialog|aside)\b[^>]*(?:role="dialog"|class="[^"]*(?:drawer|dialog)[^"]*")[^>]*>', content):
                kind = re.search(r'data-modal-kind="([^"]+)"', match.group(0))
                self.assertIsNotNone(kind, f'{page.name}: {match.group(0)}')
                self.assertIn(kind.group(1), allowed, page.name)

    def test_shell_and_context_pages_load_navigation_helper(self):
        self.assertIn('DemoNavigation', self.read('frontend/ui_demo/assets/shell.js'))
        for page in ('overview.html', 'products.html', 'product-detail.html', 'promotion.html', 'lifecycle.html', 'goals.html', 'reviews.html'):
            self.assertIn('../assets/navigation.js', self.read(f'frontend/ui_demo/pages/{page}'))

    def test_product_list_detail_action_navigates_to_workbench_and_keeps_preview_dialog(self):
        products = self.read('frontend/ui_demo/assets/products-live.js')
        products_page = self.read('frontend/ui_demo/pages/products.html')
        dialog = self.read('frontend/ui_demo/assets/product-detail-dialog.js')
        self.assertIn("new URL(`/products/${id}`, window.location.origin)", products)
        self.assertIn("['preset', 'promotion_channel']", products)
        self.assertIn("['tier', 'lifecycle_stage']", products)
        self.assertIn('../assets/product-detail-dialog.js', products_page)
        self.assertIn('window.ProductDetailDialog = { open, close }', dialog)

    def test_products_page_declares_operations_regions(self):
        page = self.read('frontend/ui_demo/pages/products.html')
        for hook in ('data-products-alert', 'data-products-coverage', 'data-products-issues', 'data-products-health', 'data-products-action'):
            self.assertIn(hook, page)

    def test_product_detail_page_declares_workbench_regions(self):
        page = self.read('frontend/ui_demo/pages/product-detail.html')
        self.assertIn('data-product-detail-tab', page)
        self.assertIn('data-product-detail-panel', page)
        self.assertIn('data-product-detail-back', page)
        self.assertIn('../assets/navigation.js', page)


if __name__ == '__main__':
    unittest.main()
