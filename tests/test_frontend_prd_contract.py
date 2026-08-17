import ast
import pathlib
import re
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class FrontendPrdContractTests(unittest.TestCase):
    def read(self, relative_path):
        return (ROOT / relative_path).read_text(encoding='utf-8')

    def test_global_header_keeps_only_date_and_compare_controls(self):
        shell = self.read('frontend/ui_demo/assets/shell.js')
        self.assertIn('data-date-preset', shell)
        self.assertIn('data-compare-mode', shell)
        self.assertNotIn('data-global-product-id', shell)
        self.assertNotIn('data-global-tier', shell)
        self.assertNotIn('data-global-lifecycle-stage', shell)
        self.assertNotIn('data-global-promotion-channel', shell)
        self.assertNotIn('TmallFilters', shell)

    def test_quick_date_ranges_use_system_today_not_latest_imported_date(self):
        shell = self.read('frontend/ui_demo/assets/shell.js')
        self.assertIn('let anchorDate = new Date();', shell)
        self.assertNotIn('anchorDate = parseDate(latest)', shell)

    def test_overview_uses_server_side_matrix_export(self):
        overview = self.read('frontend/ui_demo/assets/overview-live.js')
        self.assertIn('/api/overview/daily-matrix/export', overview)
        export_handler = overview[overview.index("window.addEventListener('tmall:export'"):]
        self.assertNotIn("window.TmallFilters?.toQuery?.()", export_handler)
        self.assertIn("overviewPayload?.capabilities?.can_export === false", export_handler)

    def test_products_export_uses_current_daily_range_and_filters(self):
        products = self.read('frontend/ui_demo/assets/products-live.js')
        self.assertIn("dim: 'daily'", products)
        self.assertIn('start,', products)
        self.assertIn('end,', products)
        self.assertNotIn('TmallFilters', products)
        self.assertIn('...filters(),', products)
        self.assertIn('star_only: state.starredOnly', products)

    def test_reviews_all_status_option_does_not_secretly_request_pending_review(self):
        reviews = self.read('frontend/ui_demo/assets/reviews-live.js')
        self.assertIn("const query = filter?.value ? `?limit=500&status=${encodeURIComponent(filter.value)}` : '?limit=500';", reviews)
        self.assertNotIn("'?limit=500&status=pending_review'", reviews)

    def test_overview_renders_all_seven_core_kpis_and_matrix_context(self):
        page = self.read('frontend/ui_demo/pages/overview.html')
        adapter = self.read('frontend/ui_demo/assets/overview-live.js')
        for key in ('payment_amount', 'net_sales', 'refund_rate', 'payment_conversion_rate',
                    'expense_ratio', 'average_order_value', 'returning_buyer_ratio'):
            self.assertIn(f'data-overview-kpi="{key}"', page)
            self.assertIn(f"['{key}',", adapter)
        self.assertIn('missing_date_ranges', adapter)
        self.assertIn('source_batches', adapter)
        self.assertIn('changes', adapter)

    def test_overview_matrix_field_selector_covers_export_schema(self):
        adapter = self.read('frontend/ui_demo/assets/overview-live.js')
        matrix_block = adapter[adapter.index('const matrixColumns ='):adapter.index('const matrixColumnsByKey')]
        keys = re.findall(r"key: '([^']+)'", matrix_block)
        export_columns = (
            'date', 'net_sales', 'payment_amount', 'successful_refund_amount',
            'refund_rate', 'visitors', 'buyers', 'payment_conversion_rate',
            'ad_spend', 'expense_ratio', 'average_order_value',
            'returning_buyer_ratio', 'source_batch_id', 'data_source',
        )
        self.assertEqual(set(keys), set(export_columns))
        self.assertEqual(len(keys), len(export_columns))
        self.assertIn("tmall-overview-matrix-columns-v2", adapter)

    def test_required_viewports_are_smoked(self):
        smoke = self.read('scripts/smoke_core_pages.cjs')
        for width in (1366, 1920, 1024, 390):
            self.assertIn(f'width: {width}', smoke)

    def test_toolbox_import_supports_multiple_excel_files(self):
        shell = self.read('frontend/ui_demo/assets/shell.js')
        self.assertIn('data-import-file type="file" accept=".xlsx,.xls,.csv,.zip" multiple', shell)
        self.assertIn('Array.from(importFile.files || [])', shell)
        self.assertIn('for (const [index, file] of files.entries())', shell)

    def test_data_center_import_supports_multiple_table_files(self):
        page = self.read('frontend/ui_demo/pages/data-center.html')
        adapter = self.read('frontend/ui_demo/assets/data-center-live.js')
        self.assertIn('accept=".xlsx,.xls,.csv,.zip" data-import-file multiple', page)
        self.assertIn('Array.from(fileInput.files || [])', adapter)
        self.assertIn('for (const [index, file] of selectedFiles.entries())', adapter)

    def test_data_center_defaults_to_automatic_report_type_detection(self):
        page = self.read('frontend/ui_demo/pages/data-center.html')
        adapter = self.read('frontend/ui_demo/assets/data-center-live.js')
        self.assertIn('<option value="auto">自动识别</option>', page)
        self.assertLess(
            page.index('<option value="auto">自动识别</option>'),
            page.index('<option value="product_day">商品日度</option>'),
        )
        self.assertIn('sourceLabels[result.source_type]', adapter)

    def test_data_center_exposes_capability_map(self):
        page = self.read('frontend/ui_demo/pages/data-center.html')
        adapter = self.read('frontend/ui_demo/assets/data-center-live.js')
        for hook in (
            'data-capability-summary', 'data-capability-filter',
            'data-capability-table', 'data-capability-detail',
            'data-unsupported-capabilities',
        ):
            self.assertIn(hook, page)
        self.assertIn('data-modal-kind="detail"', page)
        self.assertIn("DemoApi.domainRequest('/api/data-capabilities')", adapter)
        self.assertIn('catalog.unsupported_capabilities', adapter)
        self.assertIn('trigger?.focus()', adapter)
        self.assertIn('domain.evidence_level', adapter)
        self.assertIn('domain.freshness', adapter)
        self.assertIn("DemoApi.domainRequest('/api/imports')", adapter)

    def test_data_center_exposes_page_capability_map(self):
        page = self.read('frontend/ui_demo/pages/data-center.html')
        adapter = self.read('frontend/ui_demo/assets/data-center-live.js')
        for hook in (
            'data-page-capability-summary', 'data-page-capability-filter',
            'data-page-capability-table', 'data-page-capability-detail',
        ):
            self.assertIn(hook, page)
        self.assertIn("DemoApi.domainRequest('/api/page-capabilities')", adapter)
        self.assertIn('data-modal-kind="detail"', page)
        self.assertIn('pageCapabilityTrigger?.focus()', adapter)
        self.assertIn('capability.evidence_level', adapter)
        self.assertIn('capability.limitations', adapter)
        self.assertIn('capability.freshness', adapter)

    def test_api_client_surfaces_server_error_messages(self):
        api = self.read('frontend/ui_demo/assets/api.js')
        self.assertIn('await response.text()', api)
        self.assertIn('payload?.message || payload?.error', api)

    def test_api_client_exposes_capability_context_helpers(self):
        api = self.read('frontend/ui_demo/assets/api.js')
        self.assertIn('function context(', api)
        self.assertIn('function can(', api)
        self.assertIn('function loadPageCapabilities(', api)
        self.assertIn('function canPage(', api)
        self.assertIn('legacyCapabilityMap', api)
        self.assertIn('overview.view_trend', api)
        self.assertIn('goals.adjust', api)
        self.assertIn('DemoApi = { request, domainRequest, optional, context, can, loadPageCapabilities, canPage, renderDataState }', api)

    def test_api_client_maps_business_actions_to_registry_keys(self):
        api = self.read('frontend/ui_demo/assets/api.js')
        for capability, selector in (
            ('overview.view_kpis', '[data-overview-report-refresh]'),
            ('products.list', '[data-demo-refresh]'),
            ('promotion.view', '[data-demo-refresh]'),
            ('lifecycle.assessment', '[data-lifecycle-export]'),
            ('reviews.list_actions', '[data-reviews-refresh]'),
            ('settings.configure_templates', '[data-settings-form]'),
            ('goals.view', '[data-goals-form]'),
            ('manage.view', '[data-manage-create-task]'),
        ):
            self.assertIn(capability, api)
            self.assertIn(selector, api)

    def test_collapsed_overview_actions_keep_accessible_names(self):
        shell = self.read('frontend/ui_demo/assets/shell.js')
        self.assertIn('aria-label="刷新报告"', shell)
        self.assertIn('aria-label="新增事件"', shell)

    def test_refresh_handlers_capture_event_targets_before_async_cleanup(self):
        shell = self.read('frontend/ui_demo/assets/shell.js')
        self.assertGreaterEqual(shell.count('const refreshButton = event.currentTarget;'), 2)
        self.assertNotIn('setTimeout(() => event.currentTarget.classList.remove', shell)

    def test_scan_write_controls_guard_against_duplicate_submissions(self):
        shell = self.read('frontend/ui_demo/assets/shell.js')
        self.assertIn('if (button.disabled) return;', shell)
        self.assertIn('try { await handler(); } finally', shell)
        self.assertIn('const addScanButton = document.querySelector', shell)
        self.assertIn('finally { addScanButton.disabled = false; }', shell)

    def test_page_operations_reference_explicit_capability_contract(self):
        for script in (
            'overview-live.js', 'products-live.js', 'product-detail-live.js',
            'promotion-live.js', 'lifecycle-live.js', 'goals-live.js',
            'data-center-live.js', 'reviews-live.js', 'settings-live.js', 'manage-live.js',
        ):
            content = self.read(f'frontend/ui_demo/assets/{script}')
            self.assertIn('DemoApi.can(', content, script)

    def test_formal_mutation_controls_use_registered_capabilities(self):
        overview = self.read('frontend/ui_demo/pages/overview.html')
        products = self.read('frontend/ui_demo/pages/products.html')
        api = self.read('frontend/ui_demo/assets/api.js')
        self.assertIn('data-capability-key="overview.event_edit"', overview)
        self.assertIn('data-capability-key="products.catalog_edit"', products)
        self.assertIn('overview.event_edit', api)
        self.assertIn('products.catalog_edit', api)

    def test_formal_pages_use_domain_mutation_endpoints(self):
        products = self.read('frontend/ui_demo/assets/products-live.js')
        overview = self.read('frontend/ui_demo/assets/overview-live.js')
        for endpoint in (
            '/api/products/${encodeURIComponent(id)}/metadata',
            '/api/products/${encodeURIComponent(id)}/star',
            "'/api/products/batch-update'",
            "'/api/products/batch-tags'",
        ):
            self.assertIn(endpoint, products)
        self.assertIn("'/api/overview/events'", overview)
        self.assertIn('/api/overview/events?chart_type=sales', overview)
        self.assertNotIn("'/api/star'", products)
        self.assertNotIn("'/api/batch_update'", products)
        self.assertNotIn("'/api/batch_tags'", products)
        self.assertNotIn("'/api/chart_events'", overview)

    def test_toolbox_uses_folder_scan_jobs(self):
        shell = self.read('frontend/ui_demo/assets/shell.js')

        self.assertIn('文件夹扫描任务', shell)
        for hook in (
            'data-scan-folder', 'data-scan-pattern', 'data-scan-source',
            'data-scan-frequency', 'data-scan-time', 'data-scan-enabled',
            'data-select-scan-folder', 'data-scan-list',
        ):
            self.assertIn(hook, shell)
        self.assertIn("requestDomainApi('/api/import-scans'", shell)
        self.assertIn('/api/import-scans/${Number(job.id)}/run', shell)
        self.assertIn('JSON.stringify({ force: true })', shell)
        self.assertIn('未发现可导入的新文件', shell)
        self.assertIn('发现 ${discovered} 个文件，导入 ${imported} 个', shell)
        self.assertIn('按主源保留，DMP值留痕', shell)
        self.assertNotIn('/api/manage/schedules', shell)

    def test_manage_uses_folder_scan_domain_endpoints(self):
        manage = self.read('frontend/ui_demo/assets/manage-live.js')
        page = self.read('frontend/ui_demo/pages/manage.html')

        self.assertIn("DemoApi.domainRequest('/api/import-scans')", manage)
        self.assertIn('/api/import-scans/${Number(item.id)}', manage)
        self.assertIn('/api/import-scans/${Number(item.id)}/run', manage)
        self.assertNotIn('/api/manage/schedules', manage)
        self.assertIn('name="folder_path"', page)
        self.assertIn('name="source_type"', page)
        self.assertIn('data-manage-select-scan-folder', page)
        self.assertNotIn("'/api/scheduled_tasks'", manage)
        self.assertIn("DemoApi.domainRequest('/api/manage/tasks')", manage)
        self.assertIn("DemoApi.domainRequest(`/api/manage/kpis?period=", manage)
        self.assertNotIn("'/api/tasks'", manage)
        self.assertNotIn("'/api/user_kpis'", manage)

    def test_lifecycle_load_keeps_cards_available_when_assessments_fail(self):
        lifecycle = self.read('frontend/ui_demo/assets/lifecycle-live.js')
        self.assertIn("loadAssessments().catch", lifecycle)
        self.assertIn("生命周期评估加载失败，不影响月度表现", lifecycle)

    def test_overview_optional_panels_do_not_fail_the_whole_page(self):
        overview = self.read('frontend/ui_demo/assets/overview-live.js')

        self.assertIn("DemoApi.request(`/api/anomalies?", overview)
        self.assertIn(".catch((error) => { console.error(error); return []; })", overview)
        self.assertIn("DemoApi.request(`/api/report?", overview)
        self.assertIn(".catch((error) => { console.error(error); return { report: '' }; })", overview)

    def test_settings_does_not_expose_raw_json_editors(self):
        page = self.read('frontend/ui_demo/pages/settings.html')
        self.assertNotIn('生命周期阈值（JSON）', page)
        self.assertNotIn('字段映射模板（JSON）', page)
        self.assertNotIn('导入映射模板（JSON）', page)
        self.assertNotIn('商品视图模板配置（JSON）', page)

    def test_settings_contains_product_classification_dictionary_editor(self):
        page = self.read('frontend/ui_demo/pages/settings.html')
        adapter = self.read('frontend/ui_demo/assets/settings-live.js')
        self.assertIn('商品分类字典', page)
        self.assertIn('data-classification-dictionaries', page)
        self.assertIn('classification_dictionaries', adapter)
        self.assertNotIn("document.createElement('code')", adapter)
        for group in ('tiers', 'styles', 'lifecycle_stages', 'seasonal_attributes'):
            self.assertIn(group, adapter)

    def test_user_facing_enum_pages_load_shared_chinese_labels(self):
        for page in ('products.html', 'product-detail.html', 'lifecycle.html', 'reviews.html', 'data-center.html'):
            content = self.read(f'frontend/ui_demo/pages/{page}')
            self.assertIn('../assets/labels.js', content)
        labels = self.read('frontend/ui_demo/assets/labels.js')
        for value, label in (
            ('active', '在售'), ('growth', '成长期'), ('low', '低'),
            ('pending_execution', '待执行'), ('product_id', '商品编号'),
            ('unmatched', '未匹配'), ('month', '月度'),
        ):
            self.assertIn(value, labels)
            self.assertIn(label, labels)
        self.assertIn('missingValues', labels)
        self.assertIn("DemoLabels.classification('tiers'", self.read('frontend/ui_demo/assets/lifecycle-live.js'))
        self.assertIn("DemoLabels.classification('styles'", self.read('frontend/ui_demo/assets/product-detail-live.js'))

    def test_remaining_user_facing_codes_are_localized(self):
        labels = self.read('frontend/ui_demo/assets/labels.js')
        products = self.read('frontend/ui_demo/assets/products-live.js')
        overview = self.read('frontend/ui_demo/assets/overview-live.js')
        manage = self.read('frontend/ui_demo/assets/manage-live.js')
        manage_page = self.read('frontend/ui_demo/pages/manage.html')
        reviews = self.read('frontend/ui_demo/assets/reviews-live.js')
        data_center = self.read('frontend/ui_demo/assets/data-center-live.js')

        for value, label in (
            ('delisted', '下架'), ('P0', '紧急'), ('A', '优秀'),
            ('passed', '通过'), ('failed', '未通过'),
        ):
            self.assertIn(value, labels)
            self.assertIn(label, labels)
        self.assertNotIn('服务器分页 limit', products)
        self.assertIn("DemoLabels.label('action'", overview)
        self.assertIn("DemoLabels.label('priority'", manage)
        self.assertIn("DemoLabels.label('rating'", manage)
        self.assertIn("DemoLabels.label('quality'", data_center)
        self.assertIn("todo.action_type || '运营动作'", overview)
        self.assertNotIn('>P0</option>', manage_page)
        self.assertNotIn('>A</option>', manage_page)
        self.assertNotIn('value="operator"', reviews)

        for page in ('goals.html', 'reviews.html', 'lifecycle.html'):
            self.assertNotIn('value="operator"', self.read(f'frontend/ui_demo/pages/{page}'))

        for page in ('overview.html', 'manage.html'):
            self.assertIn('../assets/labels.js', self.read(f'frontend/ui_demo/pages/{page}'))

    def test_lifecycle_editor_options_are_generated_from_settings_dictionary(self):
        page = self.read('frontend/ui_demo/pages/lifecycle.html')
        adapter = self.read('frontend/ui_demo/assets/lifecycle-live.js')
        self.assertIn('data-lifecycle-stage-options', page)
        self.assertIn('data-lifecycle-season-options', page)
        self.assertNotIn('<option value="growth">', page)
        self.assertIn("DemoLabels.enabled('lifecycle_stages')", adapter)
        self.assertIn("DemoLabels.enabled('seasonal_attributes')", adapter)

    def test_lifecycle_assessments_are_paginated_and_actionable_first(self):
        page = self.read('frontend/ui_demo/pages/lifecycle.html')
        adapter = self.read('frontend/ui_demo/assets/lifecycle-live.js')
        for hook in (
            'data-lifecycle-assessment-search',
            'data-lifecycle-assessment-stage',
            'data-lifecycle-assessment-count',
            'data-lifecycle-assessment-prev',
            'data-lifecycle-assessment-next',
        ):
            self.assertIn(hook, page)
        self.assertIn('const assessmentPageSize = 20', adapter)
        self.assertIn('visibleAssessments()', adapter)
        self.assertIn('assessmentPriority', adapter)
        self.assertIn('data-lifecycle-assessment-evidence', adapter)

    def test_lifecycle_editor_is_a_real_modal_and_closes_out_of_layout(self):
        page = self.read('frontend/ui_demo/pages/lifecycle.html')
        adapter = self.read('frontend/ui_demo/assets/lifecycle-live.js')
        styles = self.read('frontend/ui_demo/assets/components.css')
        self.assertIn('aria-labelledby="lifecycle-edit-title"', page)
        self.assertIn('data-lifecycle-edit-product', page)
        self.assertIn('data-lifecycle-edit-cancel', page)
        self.assertIn('.modal-form:not([open])', styles)
        self.assertIn('background: var(--surface-base)', styles)
        self.assertIn('editDialog.hidden = true', adapter)
        self.assertIn('editDialog.addEventListener(\'cancel\'', adapter)

    def test_data_center_revert_explains_impact_before_request(self):
        data_center = self.read('frontend/ui_demo/assets/data-center-live.js')
        self.assertIn('确认撤销该批次', data_center)
        self.assertIn('影响', data_center)

    def test_goals_page_uses_three_stage_monthly_editing(self):
        page = self.read('frontend/ui_demo/pages/goals.html')
        adapter = self.read('frontend/ui_demo/assets/goals-live.js')
        self.assertIn('年度配置', page)
        self.assertIn('自动分配依据', page)
        self.assertIn('月度执行', page)
        self.assertIn('data-goals-allocation-preview', page)
        self.assertIn('data-goals-months', page)
        self.assertNotIn('data-goals-adjust-form', page)
        self.assertIn('data-goals-month-target', adapter)
        self.assertIn('saveMonth', adapter)
        self.assertIn('lockMonth', adapter)
        self.assertIn('/allocation-preview?annual_target=', adapter)
        self.assertIn('annualTargetDirty', adapter)
        self.assertNotIn('prepareMonthAdjustment', adapter)

    def test_reviews_expand_one_action_and_block_missing_observation(self):
        reviews = self.read('frontend/ui_demo/assets/reviews-live.js')
        self.assertIn("document.createElement('details')", reviews)
        self.assertIn('等待观察数据后再复盘', reviews)

    def test_settings_view_selector_uses_persisted_template_keys(self):
        page = self.read('frontend/ui_demo/pages/settings.html')
        for key in ('value="operate"', 'value="select"', 'value="paid"', 'value="refund"', 'value="lifecycle"'):
            self.assertIn(key, page)

    def test_chart_adapter_preserves_page_chart_options(self):
        charts = self.read('frontend/ui_demo/assets/charts.js')
        self.assertIn('toEchartsOption', charts)
        self.assertIn('config.options', charts)
        self.assertIn('ResizeObserver', charts)

    def test_products_do_not_render_empty_image_elements(self):
        products = self.read('frontend/ui_demo/assets/products-live.js')
        image_block = products[products.index("const identity = document.createElement('div');"):products.index("const title = document.createElement('div');")]
        self.assertIn('if (item.image_url)', image_block)
        self.assertIn('product-thumb--placeholder', image_block)

    def test_products_column_dialog_supports_full_selection_and_custom_templates(self):
        page = self.read('frontend/ui_demo/pages/products.html')
        adapter = self.read('frontend/ui_demo/assets/products-live.js')
        for hook in (
            'data-products-columns-select-all',
            'data-products-columns-clear-all',
            'data-products-template-select',
            'data-products-template-name',
            'data-products-template-save',
        ):
            self.assertIn(hook, page)
        for field in ('search_conversion', 'paid_ipv', 'direct_gmv', 'cart_cost', 'click_rate'):
            self.assertIn(f"key: '{field}'", adapter)
        self.assertIn('saveCustomTemplate', adapter)
        self.assertIn("'/api/settings'", adapter)

        column_definition = adapter[adapter.index('const columnGroups = ['):adapter.index('const columns =')]
        column_keys = re.findall(r"key: '([^']+)'", column_definition)
        self.assertEqual(len(column_keys), len(set(column_keys)), 'column settings must not render duplicate fields')
        self.assertEqual(adapter.count('function renderTemplateSelect('), 1)
        self.assertEqual(adapter.count('function saveCustomTemplate('), 1)
        selector = self.read('frontend/ui_demo/assets/field-selector.js')
        self.assertIn('button.title = `${name}${field.label}`', selector)
        self.assertIn('button.disabled = position + offset < 0 || position + offset >= selected.length', selector)
        self.assertIn('requiredKeys', selector)
        self.assertIn('input.disabled = field.required || field.locked', selector)

        settings_tree = ast.parse(self.read('services/settings_service.py'))
        view_columns_node = next(
            node.value for node in settings_tree.body
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == 'VIEW_COLUMNS' for target in node.targets)
        )
        view_columns = ast.literal_eval(view_columns_node)
        self.assertEqual(view_columns, set(column_keys) | {'product_id', 'title'})

    def test_field_template_dialogs_manage_templates_inline(self):
        manager = self.read('frontend/ui_demo/assets/field-template-manager.js')
        self.assertIn('window.DemoFieldTemplateManager', manager)
        self.assertIn('data-field-template-edit', manager)
        self.assertIn('data-field-template-delete', manager)
        for page_name, script_name in (
            ('products', 'products-live.js'),
            ('promotion', 'promotion-live.js'),
            ('lifecycle', 'lifecycle-live.js'),
        ):
            page = self.read(f'frontend/ui_demo/pages/{page_name}.html')
            script = self.read(f'frontend/ui_demo/assets/{script_name}')
            self.assertIn('../assets/field-template-manager.js', page)
            self.assertIn('DemoFieldTemplateManager', script)
        self.assertIn("'/api/settings'", self.read('frontend/ui_demo/assets/products-live.js'))
        self.assertIn("'/api/settings'", self.read('frontend/ui_demo/assets/promotion-live.js'))
        promotion = self.read('frontend/ui_demo/assets/promotion-live.js')
        self.assertIn('template.name = persisted.label || template.name', promotion)
        self.assertIn('...persistedBuiltinTemplates, ...builtinTemplates, ...customTemplates', promotion)

    def test_products_field_selection_uses_a_separate_order_preview(self):
        page = self.read('frontend/ui_demo/pages/products.html')
        script = self.read('frontend/ui_demo/assets/products-live.js')
        selector = self.read('frontend/ui_demo/assets/field-selector.js')
        self.assertIn('data-products-field-selector', page)
        self.assertIn('DemoFieldSelector.create', script)
        self.assertIn("previewDataAttribute: 'data-products-preview-key'", script)
        self.assertIn('function renderPreview', selector)
        options_block = script[script.index('function renderColumnOptions('):script.index('function openColumnsDialog(')]
        self.assertNotIn("[['arrow-up', -1, '上移'], ['arrow-down', 1, '下移']]", options_block)

    def test_field_settings_use_one_shared_selector_component(self):
        component_path = ROOT / 'frontend/ui_demo/assets/field-selector.js'
        self.assertTrue(component_path.exists(), 'field settings must be implemented by one shared component')
        component = component_path.read_text(encoding='utf-8')
        self.assertIn('window.DemoFieldSelector', component)
        self.assertIn('function create', component)
        for page_name, script_name in (('products', 'products-live.js'), ('promotion', 'promotion-live.js')):
            page = self.read(f'frontend/ui_demo/pages/{page_name}.html')
            script = self.read(f'frontend/ui_demo/assets/{script_name}')
            self.assertIn('../assets/field-selector.js', page)
            self.assertIn('DemoFieldSelector.create', script)

    def test_import_history_uses_its_own_status_region_and_shortens_hashes(self):
        page = self.read('frontend/ui_demo/pages/data-center.html')
        adapter = self.read('frontend/ui_demo/assets/data-center-live.js')
        self.assertIn('data-import-history-status', page)
        self.assertIn('historyStatus', adapter)
        self.assertIn('shortHash', adapter)

    def test_advanced_header_filters_are_collapsed_until_requested(self):
        shell_css = self.read('frontend/ui_demo/assets/shell.css')
        self.assertNotIn('.demo-period__advanced', shell_css)

    def test_promotion_page_filters_apply_to_the_full_page_query(self):
        promotion = self.read('frontend/ui_demo/assets/promotion-live.js')
        self.assertIn("['channel', '[data-promotion-channel]']", promotion)
        self.assertIn("['campaign_id', '[data-promotion-campaign]']", promotion)
        self.assertIn("['unit_id', '[data-promotion-unit]']", promotion)
        self.assertIn('bindPageFilters', promotion)
        self.assertIn("addEventListener('input'", promotion)

    def test_promotion_tabs_support_complete_field_settings_and_custom_templates(self):
        page = self.read('frontend/ui_demo/pages/promotion.html')
        adapter = self.read('frontend/ui_demo/assets/promotion-live.js')
        for hook in (
            'data-promotion-template-select',
            'data-promotion-manage-fields',
            'data-promotion-field-dialog',
            'data-promotion-fields-select-all',
            'data-promotion-fields-clear-all',
            'data-promotion-template-name',
            'data-promotion-template-save',
        ):
            self.assertIn(hook, page)
        for tab in ('products', 'keywords', 'crowd', 'site'):
            self.assertIn(f"{tab}: {{", adapter)
        for field in ('impressions', 'clicks', 'ctr', 'payment_buyers', 'cvr', 'cpc', 'direct_payment_amount', 'indirect_payment_amount', 'paid_share'):
            self.assertIn(f"key: '{field}'", adapter)
        self.assertIn('saveCustomTemplate', adapter)
        self.assertIn('selectAllFields', adapter)
        self.assertIn('clearAllFields', adapter)
        self.assertIn('restoreActiveTemplatesFromPreferences', adapter)
        self.assertIn('ingestServerTemplates(response.data);\n    restoreActiveTemplatesFromPreferences();', adapter)
        self.assertIn('const builtinTemplates = Object.fromEntries', adapter)
        self.assertIn('promotionBuiltinTemplateIds.has(id)', adapter)

    def test_template_configuration_uses_server_as_the_single_source(self):
        settings = self.read('frontend/ui_demo/assets/settings-live.js')
        promotion = self.read('frontend/ui_demo/assets/promotion-live.js')
        self.assertIn('renderProductViewOptions', settings)
        self.assertIn("data.view_templates", settings)
        self.assertIn("'/api/settings'", promotion)
        self.assertIn('promotion_view_templates', promotion)
        self.assertNotIn("localStorage.setItem(storageKey", promotion)

    def test_shell_discloses_page_unsupported_filters(self):
        shell = self.read('frontend/ui_demo/assets/shell.js')
        self.assertIn('unsupportedFiltersByPage', shell)
        self.assertIn("goals: ['promotion_channel']", shell)

    def test_settings_and_promotion_share_the_alert_rule_editor(self):
        component = self.read('frontend/ui_demo/assets/alert-rules.js')
        settings = self.read('frontend/ui_demo/pages/settings.html')
        promotion = self.read('frontend/ui_demo/pages/promotion.html')
        for page in (settings, promotion):
            self.assertIn('../assets/alert-rules.js', page)
        self.assertIn('data-alert-rules-root', settings)
        self.assertIn('data-alert-rules-open', promotion)
        self.assertIn("'/api/alert-rules'", component)
        for field in ('name', 'scope', 'metric', 'operator', 'threshold', 'level', 'enabled'):
            self.assertIn(field, component)

    def test_products_use_shared_preview_and_promotion_keeps_product_preview(self):
        component = self.read('frontend/ui_demo/assets/product-detail-dialog.js')
        products_page = self.read('frontend/ui_demo/pages/products.html')
        promotion_page = self.read('frontend/ui_demo/pages/promotion.html')
        products = self.read('frontend/ui_demo/assets/products-live.js')
        promotion = self.read('frontend/ui_demo/assets/promotion-live.js')
        self.assertIn('../assets/product-detail-dialog.js', products_page)
        self.assertIn('../assets/product-detail-dialog.js', promotion_page)
        self.assertIn('window.ProductDetailDialog?.open({ productId: id', products)
        self.assertIn('ProductDetailDialog.open', promotion)
        self.assertIn('/api/products/', component)
        self.assertIn('/detail', component)
        self.assertNotIn('data-product-detail-link', products_page)
        self.assertNotIn('打开完整详情页', products_page)
        self.assertNotIn('location.href = `/products/', promotion)
        smoke = self.read('scripts/smoke_core_pages.cjs')
        self.assertIn('.product-detail-dialog', smoke)
        self.assertIn('.alert-rules-dialog', smoke)

    def test_product_detail_page_uses_context_capability_key(self):
        page = self.read('frontend/ui_demo/pages/product-detail.html')
        self.assertIn('<body data-page="product-detail">', page)

    def test_product_detail_live_has_no_mojibake_copy(self):
        component = self.read('frontend/ui_demo/assets/product-detail-live.js')
        for marker in ('鍟嗗搧', '缁忚惀', '缃俊搴', '鏆傛棤鍒ゆ柇'):
            self.assertNotIn(marker, component)
        self.assertIn('商品经营 / 商品列表 /', component)
        self.assertIn('置信度：', component)
        self.assertIn('暂无判断依据', component)

    def test_product_detail_smoke_covers_compatibility_route(self):
        smoke = self.read('scripts/smoke_core_pages.cjs')
        self.assertIn('/products/', smoke)

    def test_product_detail_exposes_source_fields_and_dense_metric_grid(self):
        page = self.read('frontend/ui_demo/pages/product-detail.html')
        component = self.read('frontend/ui_demo/assets/product-detail-live.js')
        self.assertIn('data-product-detail-detail-metrics', page)
        self.assertIn('data-product-detail-info', page)
        self.assertIn('data-product-detail-detail-metrics', component)
        self.assertIn('当前日期范围无商品日度数据', component)
        for key in ('payment_qty', 'search_visitors', 'paid_ipv', 'organic_ipv', 'presale_amount', 'presale_qty', 'data_source'):
            self.assertIn(key, component)

    def test_product_detail_overview_has_linked_operating_trend(self):
        page = self.read('frontend/ui_demo/pages/products.html')
        component = self.read('frontend/ui_demo/assets/product-detail-dialog.js')
        styles = self.read('frontend/ui_demo/assets/components.css')
        self.assertIn('../assets/echarts-5.5.1.min.js', page)
        self.assertIn('../assets/charts.js', page)
        self.assertIn('function renderOverviewTrend', component)
        self.assertIn('function groupOverviewTrendByMonth', component)
        self.assertIn('data-product-overview-trend', component)
        self.assertIn('detail.daily_trend', component)
        self.assertIn('row.payment_amount', component)
        self.assertIn('row.net_sales', component)
        self.assertIn('row.ad_spend', component)
        self.assertIn('.product-detail-overview-trend', styles)
        self.assertIn('.product-detail-overview-chart', styles)
        self.assertIn('function metricGroups', component)
        self.assertIn('product-detail-overview-layout', component)
        self.assertIn('.product-detail-metric-groups', styles)
        self.assertIn('.product-detail-overview-layout', styles)

    def test_product_detail_dialog_uses_global_date_range(self):
        component = self.read('frontend/ui_demo/assets/product-detail-dialog.js')
        self.assertIn('function selectedRangeQuery', component)
        self.assertIn("params.set('start'", component)
        self.assertIn("params.set('end'", component)
        self.assertIn("tmall:date-range-change", component)

    def test_centered_dialog_consolidation_removes_business_drawers(self):
        shell = self.read('frontend/ui_demo/assets/shell.js')
        promotion = self.read('frontend/ui_demo/pages/promotion.html')
        component = self.read('frontend/ui_demo/assets/product-detail-dialog.js')
        self.assertIn('<dialog class="toolbox-dialog" data-toolbox-dialog', shell)
        self.assertNotIn('toolbox-overlay', shell)
        self.assertNotIn('toolbox-drawer', shell)
        self.assertIn('<dialog class="promotion-dialog" data-promotion-dialog', promotion)
        self.assertNotIn('demo-drawer__backdrop', promotion)
        self.assertNotIn('data-promotion-drawer', promotion)
        self.assertIn('role="tablist"', component)
        self.assertIn('data-product-detail-tab="${id}"', component)
        self.assertIn("dialog.className = 'lifecycle-detail product-detail-dialog'", component)
        self.assertIn('lifecycle-detail__header', component)
        self.assertIn('lifecycle-detail-tabs', component)
        for tab in ('overview', 'trend', 'lifecycle', 'collaboration'):
            self.assertIn(f"['{tab}'", component)
        self.assertIn("setAttribute('role', 'tabpanel')", component)

    def test_dynamic_dialogs_declare_registered_modal_kinds(self):
        product_detail = self.read('frontend/ui_demo/assets/product-detail-dialog.js')
        alert_rules = self.read('frontend/ui_demo/assets/alert-rules.js')
        self.assertIn("setAttribute('data-modal-kind', 'detail')", product_detail)
        self.assertIn("setAttribute('data-modal-kind', 'config')", alert_rules)

    def test_product_detail_actions_use_context_capability_gate(self):
        component = self.read('frontend/ui_demo/assets/product-detail-dialog.js')
        self.assertIn("loadPageCapabilities('product-detail')", component)
        self.assertIn("data-capability-key", component)
        self.assertIn("canPage?.('product-detail', 'product-detail.create_action')", component)

    def test_shared_product_detail_dialog_links_to_full_workbench(self):
        component = self.read('frontend/ui_demo/assets/product-detail-dialog.js')
        self.assertIn('data-shared-product-workbench', component)
        self.assertIn("/products/${encodeURIComponent", component)

    def test_open_dialogs_lock_the_document_scroll_root(self):
        shell_styles = self.read('frontend/ui_demo/assets/shell.css')
        component_styles = self.read('frontend/ui_demo/assets/components.css')
        self.assertIn('html:has(dialog[open])', shell_styles)
        self.assertIn('overscroll-behavior: none', shell_styles)
        self.assertIn('.modal-form__body', component_styles)
        self.assertIn('overscroll-behavior: contain', component_styles)

    def test_sticky_table_header_tolerates_transient_empty_headers(self):
        controls = self.read('frontend/ui_demo/assets/table-controls.js')
        self.assertIn('const headerRow = currentHeaderRow(table);', controls)
        self.assertIn('if (!headerRow) return;', controls)
        self.assertIn('[...headerRow.cells]', controls)

    def test_lifecycle_detail_uses_tabbed_centered_panels(self):
        lifecycle = self.read('frontend/ui_demo/assets/lifecycle-live.js')
        page = self.read('frontend/ui_demo/pages/lifecycle.html')
        styles = self.read('frontend/ui_demo/assets/components.css')
        self.assertIn("detailTab: 'overview'", lifecycle)
        self.assertIn('detailTabUI', lifecycle)
        self.assertIn('dataset.lifecycleDetailTab', lifecycle)
        self.assertIn('dataset.lifecycleDetailPanel', lifecycle)
        self.assertIn('lifecycle-detail-tabs', styles)
        self.assertIn('lifecycle-detail-panel', styles)
        self.assertIn('data-lifecycle-detail', page)
        for tab in ('overview', 'efficiency', 'table'):
            self.assertIn(f"['{tab}'", lifecycle)
        self.assertIn('grid-template-columns: minmax(0, 1fr)', styles)
        self.assertIn('.lifecycle-detail__header { position: sticky; top: 0; z-index: 3; display: flex; min-width: 0', styles)
        self.assertIn('.lifecycle-detail__product { display: flex; min-width: 0; flex: 1 1 auto', styles)
        self.assertIn('.lifecycle-detail-panel > .plain-panel { min-width: 0; margin-bottom: 0; }', styles)

    def test_lifecycle_field_settings_cover_monthly_operating_sections(self):
        lifecycle = self.read('frontend/ui_demo/assets/lifecycle-live.js')
        settings = self.read('services/settings_service.py')
        styles = self.read('frontend/ui_demo/assets/components.css')
        for field in ('net_sales', 'visitors', 'payment_conversion', 'refund_rate', 'repurchase_rate', 'cross_sell_rate'):
            self.assertIn(field, lifecycle)
            self.assertIn(field, settings)
        self.assertIn("traffic:", lifecycle)
        self.assertIn("width: min(1120px", styles)
        self.assertIn("minmax(360px, .85fr)", styles)
        self.assertIn("grid-template-rows: minmax(220px, 1fr)", styles)

    def test_shared_typography_tokens_cover_detail_dialog_scales(self):
        tokens = self.read('frontend/ui_demo/assets/tokens.css')
        styles = self.read('frontend/ui_demo/assets/components.css')
        self.assertIn('--font-size-meta: 11px', tokens)
        self.assertIn('--font-size-secondary: 12px', tokens)
        self.assertIn('--font-size-body: 13px', tokens)
        self.assertIn('--space-1: 4px', tokens)
        self.assertIn('--space-5: 20px', tokens)
        self.assertIn('--text-primary: var(--color-gray-900)', tokens)
        self.assertIn('.product-detail-meta dt', styles)
        self.assertIn('.product-detail-meta dd', styles)
        self.assertIn('font-size: var(--font-size-secondary); line-height: var(--line-height-body)', styles)
        self.assertIn('.alert-rule-row > div:first-child strong', styles)
        self.assertIn('.plain-panel > p:not(.panel__hint)', styles)

    def test_promotion_field_selection_uses_a_separate_order_preview(self):
        page = self.read('frontend/ui_demo/pages/promotion.html')
        script = self.read('frontend/ui_demo/assets/promotion-live.js')
        selector = self.read('frontend/ui_demo/assets/field-selector.js')
        self.assertIn('data-promotion-field-selector', page)
        self.assertIn('DemoFieldSelector.create', script)
        self.assertIn("previewDataAttribute: 'data-promotion-preview-key'", script)
        self.assertIn('function renderPreview', selector)

    def test_promotion_tabs_do_not_fabricate_attribution_or_unnamed_products(self):
        adapter = self.read('frontend/ui_demo/assets/promotion-live.js')
        styles = self.read('frontend/ui_demo/assets/components.css')
        self.assertNotIn('推算归因成交', adapter)
        self.assertNotIn('未命名商品', adapter)
        self.assertIn("performance.data?.breakdowns", adapter)
        self.assertIn('.promotion-template-bar[hidden]', styles)

    def test_echarts_pages_use_block_containers_not_canvas_elements(self):
        for page in ('overview.html', 'promotion.html', 'lifecycle.html', 'compare.html'):
            content = self.read(f'frontend/ui_demo/pages/{page}')
            self.assertNotIn('<canvas id=', content)
            self.assertIn('class="chart-canvas"', content)

    def test_overview_compare_mode_requests_compare_api_and_is_scoped_to_supported_page(self):
        shell = self.read('frontend/ui_demo/assets/shell.js')
        overview = self.read('frontend/ui_demo/assets/overview-live.js')
        self.assertIn("currentPage === 'overview'", shell)
        self.assertIn("/api/compare?dim=monthly", overview)
        self.assertIn('compareMode', overview)
        self.assertIn('comparison', overview)

    def test_multi_file_import_exposes_each_preview_mapping(self):
        adapter = self.read('frontend/ui_demo/assets/data-center-live.js')
        self.assertIn('data-import-preview-tabs', adapter)
        self.assertIn('activePreviewIndex', adapter)
        self.assertIn('render(previewQueue[activePreviewIndex])', adapter)
        self.assertIn('data-import-preview-file', adapter)
        self.assertIn('field.standard_key = mapping.value', adapter)

    def test_toolbox_import_uses_preview_mapping_and_confirm_flow(self):
        shell = self.read('frontend/ui_demo/assets/shell.js')
        self.assertIn('data-import-preview', shell)
        self.assertIn('data-import-confirm', shell)
        self.assertIn('data-import-preview-panel', shell)
        self.assertIn("/api/imports/preview?source_type=auto", shell)
        self.assertIn("domainRequest('/api/imports'", shell)
        self.assertNotIn("domainRequest('/api/upload/data'", shell)

    def test_settings_uses_shared_state_renderer_with_retry(self):
        adapter = self.read('frontend/ui_demo/assets/settings-live.js')
        self.assertIn('DemoApi.renderDataState', adapter)
        self.assertIn("'source-unavailable'", adapter)
        self.assertIn('retry: load', adapter)

    def test_ui_audit_regressions_are_covered(self):
        shell = self.read('frontend/ui_demo/assets/shell.js')
        tokens = self.read('frontend/ui_demo/assets/tokens.css')
        lifecycle = self.read('frontend/ui_demo/assets/lifecycle-live.js')
        lifecycle_page = self.read('frontend/ui_demo/pages/lifecycle.html')
        products = self.read('frontend/ui_demo/assets/products-live.js')
        products_page = self.read('frontend/ui_demo/pages/products.html')
        components = self.read('frontend/ui_demo/assets/components.css')
        settings = self.read('frontend/ui_demo/assets/settings-live.js')

        self.assertIn('data-skip-link', shell)
        self.assertIn('closeMobileNavigation', shell)
        self.assertIn("event.key === 'Escape'", shell)
        self.assertIn('name="scan_name"', shell)
        self.assertIn('name="scan_folder"', shell)
        self.assertIn('color-scheme: light', tokens)
        self.assertIn('color-scheme: dark', tokens)
        self.assertIn('meta[name="theme-color"]', shell)
        self.assertIn('width="42" height="42" loading="lazy"', lifecycle)
        self.assertIn('window.ProductDetailDialog?.open({ productId: id', products)
        self.assertNotIn('data-product-drawer', products)
        self.assertIn('beforeunload', settings)
        self.assertIn('data-products-more-filters', products_page)
        self.assertIn('data-products-more-filters-toggle', products_page)
        self.assertIn('[data-products-more-filters][hidden] { display: none; }', components)
        self.assertIn('min-height: 40px', components)
        self.assertIn('min-height: 44px', components)
        self.assertIn('body[data-page="promotion"] .metric-grid { grid-template-columns: repeat(12, minmax(0, 1fr)); }', components)
        self.assertIn('.field-order-preview__button { width: 44px; min-width: 44px; height: 44px; }', components)
        self.assertNotIn('<img data-detail-image', lifecycle_page)
        self.assertIn('new Image(52, 52)', lifecycle)
        self.assertIn("image.loading = 'lazy'", lifecycle)

    def test_business_details_use_centered_dialog_widths(self):
        shell = self.read('frontend/ui_demo/assets/shell.css')
        components = self.read('frontend/ui_demo/assets/components.css')

        self.assertIn('width: min(720px, calc(100vw - 32px))', shell)
        self.assertIn('width: min(680px, calc(100vw - 32px))', components)
        self.assertIn('max-height: calc(100dvh - 24px)', shell)
        self.assertIn('max-height: calc(100dvh - 24px)', components)
        self.assertNotIn('.demo-drawer {', shell)

    def test_settings_exposes_desktop_version_management(self):
        page = self.read('frontend/ui_demo/pages/settings.html')
        adapter = self.read('frontend/ui_demo/assets/desktop-integration.js')

        self.assertIn('data-desktop-settings', page)
        self.assertIn('data-desktop-version', page)
        self.assertIn('data-desktop-check-update', page)
        self.assertIn('data-desktop-update-status', page)
        self.assertIn('desktop-integration.js', page)
        self.assertIn('window.tmallDesktop', adapter)
        self.assertIn('panel.hidden = false', adapter)
        self.assertIn('getVersion()', adapter)
        self.assertIn('checkForUpdates()', adapter)

    def test_write_operations_lock_controls_and_restore_failed_state(self):
        data_center = self.read('frontend/ui_demo/assets/data-center-live.js')
        settings = self.read('frontend/ui_demo/assets/settings-live.js')
        promotion = self.read('frontend/ui_demo/assets/promotion-live.js')

        self.assertIn('button.disabled = true;', data_center)
        self.assertIn('批次撤销失败，请重试', data_center)
        self.assertIn('finally {', data_center)
        self.assertIn('let saving = false;', settings)
        self.assertIn("saveButton.setAttribute('aria-busy', 'true')", settings)
        self.assertIn('discardButton.disabled = !isDirty', settings)
        self.assertIn("state.selectedFields[tab] = previousSelectedFields", promotion)
        self.assertIn("actionButton.setAttribute('aria-busy', 'true')", promotion)
        self.assertIn('await deletePromotionTemplate(remove.dataset.promotionDeleteTemplate)', promotion)


if __name__ == '__main__':
    unittest.main()
