import ast
import pathlib
import re
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class FrontendPrdContractTests(unittest.TestCase):
    def read(self, relative_path):
        return (ROOT / relative_path).read_text(encoding='utf-8')

    def read_global_styles(self):
        """全局样式库合并视图：components.css + themes/*-domain.css。

        域样式已按功能前缀迁入 themes/，断言不应绑定物理文件归属。"""
        parts = [self.read('frontend/ui_demo/assets/components.css')]
        for domain in ('product', 'promotion', 'overview', 'lifecycle', 'settings'):
            parts.append(self.read(f'frontend/ui_demo/assets/themes/{domain}-domain.css'))
        return '\n'.join(parts)

    def test_global_header_keeps_only_date_and_compare_controls(self):
        shell = self.read('frontend/ui_demo/assets/shell.js')
        self.assertIn('data-date-preset', shell)
        self.assertIn('data-compare-mode', shell)
        self.assertNotIn('data-global-product-id', shell)
        self.assertNotIn('data-global-tier', shell)
        self.assertNotIn('data-global-lifecycle-stage', shell)
        self.assertNotIn('data-global-promotion-channel', shell)
        self.assertNotIn('TmallFilters', shell)

    def test_period_review_diagnosis_clues_can_create_traceable_actions(self):
        clue = self.read('frontend/ui_demo/assets/pages/period-review/gap-attribution.js')
        live = self.read('frontend/ui_demo/assets/period-review-live.js')
        self.assertIn('function clueLine(text, section, anchorLabel, diagnosisSource)', clue)
        self.assertIn('text: ' + repr('转为动作'), clue)
        self.assertIn('window.periodReviewOpenActionFromDiagnosis?.(source)', clue)
        self.assertIn('clue: text', clue)
        self.assertIn('section,', clue)
        self.assertIn('impact: diagnosisSource?.impact', clue)
        self.assertIn('metric: diagnosisSource?.metric', clue)
        self.assertIn('window.periodReviewOpenActionFromDiagnosis = openDiagnosisAction', live)
        self.assertIn('function openProductDiagnosis(row, withDelta, diagnosisSource = null)', live)
        self.assertIn('source_period_type: state.mode', live)
        self.assertIn('source_period_key: state.context?.period?.key || currentPeriod()', live)
        self.assertIn('source_problem_key: diagnosisSource?.problemKey', live)
        self.assertIn('source_diagnosis_snapshot: JSON.stringify({', live)
        self.assertIn("product_id: String(data.get('product_id') || row.product_id || '').trim()", live)
        self.assertIn("!productId ? actionSelect('关联商品', 'product_id'", live)
        self.assertIn('不会自动虚构商品 ID', live)
        self.assertIn('await load();', live)
        # 计划字段必须由执行人确认：不把今天、7 天或“运营人员��伪装成已确认信息。
        self.assertIn("actionField('计划日期', 'planned_at', 'date', '', true)", live)
        self.assertIn("actionField('观察天数', 'observer_window_days', 'number', '', true)", live)
        self.assertIn("actionField('负责人', 'assigned_to', 'text', '')", live)
        self.assertNotIn("actionField('计划日期', 'planned_at', 'date', todayForAction(), true)", live)
        self.assertNotIn("actionField('观察天数', 'observer_window_days', 'number', '7', true)", live)
        self.assertNotIn("actionField('负责人', 'assigned_to', 'text', '运营人员')", live)

    def test_period_review_controls_are_single_row_and_category_switch_persists_compare(self):
        shell = self.read('frontend/ui_demo/assets/shell.js')
        styles = self.read('frontend/ui_demo/assets/period-review.css')
        page = self.read('frontend/ui_demo/pages/period-review.html')
        review_controls = shell[shell.index('const periodReviewControls ='):shell.index("header.innerHTML =", shell.index('const periodReviewControls ='))]
        self.assertIn('data-pr-period', review_controls)
        self.assertIn('data-pr-compare', review_controls)
        self.assertIn('data-pr-compare-period', review_controls)
        self.assertNotIn('data-pr-period-label', review_controls)
        self.assertIn('dashboard.categoryMode', shell)
        self.assertIn('window.location.reload()', shell)
        self.assertIn('categoryChangedByUser', shell)
        # 行为断言而非实现细节：类目切换回写 select + 跨页刷新，具体写法允许变。
        self.assertIn('categoryChangedByUser', shell)
        self.assertIn('readCategoryMode', shell)
        self.assertIn("if (currentPage !== 'period-review') window.location.reload();", shell)
        self.assertIn("document.querySelector('[data-pr-category]') || document.querySelector('[data-category-mode]')", self.read('frontend/ui_demo/assets/period-review-live.js'))
        self.assertIn('dashboard.periodReviewCompare', self.read('frontend/ui_demo/assets/period-review-live.js'))
        # 单行布局行为：不换行 + 横向滚动（具体声明顺序允许变）
        self.assertIn('nowrap', styles)
        self.assertIn('overflow-x', styles)
        # shell.js 引用必须带 cache-bust 版本参数（具体版本号不锁定）
        self.assertRegex(page, r'shell\.js\?v=\d{8}')

    def test_period_review_deterministic_draft_fills_empty_sections(self):
        """确定性初稿：生成器存在、入口在工具栏、回填只补空且不写本地草稿。"""
        page = self.read('frontend/ui_demo/pages/period-review.html')
        live = self.read('frontend/ui_demo/assets/period-review-live.js')
        draft = self.read('frontend/ui_demo/assets/pages/period-review/deterministic-draft.js')
        gap = self.read('frontend/ui_demo/assets/pages/period-review/gap-attribution.js')
        # 生成入口按钮 + 元信息条挂载点 + 生成器脚本引用（带版本参数）
        self.assertIn('data-pr-generate-draft', page)
        self.assertIn('data-pr-draft-meta', page)
        self.assertRegex(page, r'deterministic-draft\.js\?v=\d{8}')
        # 六段板块内联直编（不弹窗）：每段 = 板块数据 + 分析/根因/下一步；
        # 分日/分周指标只在品类汇总板块数据出现一次（驾驶舱下不再重复渲染 overview）。
        self.assertIn('data-pr-sections', page)
        self.assertNotIn('data-pr-sections-dialog', page)
        self.assertNotIn('data-pr-sections-preview', page)
        self.assertNotIn('data-pr-overview', page)
        # 工作区页签已撤：四个工作区平铺一页，导航统一走吸顶锚点 chips
        self.assertNotIn('data-pr-workbench-tab', page)
        self.assertIn('data-pr-section-nav', page)
        self.assertIn('observeReferencePanel', live)
        self.assertNotIn('sectionsDialog', live)
        self.assertNotIn('renderSectionsPreview', live)
        self.assertNotIn('renderOverview', live)
        # 板块数据置顶且默认展开（用户要求的「数据+分析+根因+下一步」顺序）；
        # metrics 不重复渲染——驾驶舱三卡就在同页上方。
        self.assertIn('板块数据', live)
        self.assertIn("key !== 'metrics' && key !== 'target_path'", live)
        self.assertIn("case 'breakdown':", live)
        # 拆因已并入结论段：货品/广告/市场/流量/归因明细 = 六段板块数据本身，
        # 不再另设拆因工作区（单一渲染点，双渲染即回归）。
        self.assertIn('case \'gap_attribution\':', live)
        self.assertIn('case \'traffic\':', live)
        self.assertIn('case \'promotion_channels\':', live)
        self.assertNotIn('data-pr-workbench-panel="diagnosis"', page)
        self.assertNotIn('data-pr-diagnosis-anchor', page)
        self.assertNotIn('evidenceDigest', live)
        self.assertIn("['promotion_channels', 'promotion_items']", self.read('services/period_templates.py'))
        self.assertIn("['metrics', 'target_path', 'gap_attribution', 'traffic', 'breakdown', 'linked_summaries']", self.read('services/period_templates.py'))
        # 长页导航与状态：吸顶锚点 chips + 段落完成徽章 + 输入框高度自适应
        self.assertIn('data-pr-section-nav', page)
        self.assertIn('renderSectionNav', live)
        self.assertIn('sectionFillState', live)
        self.assertIn('autoGrowTextarea', live)
        # live.js 接线：实例化生成器、按周期/对比口径缓存、元信息条渲染、按钮事件
        self.assertIn('global.createDeterministicDraft = createDeterministicDraft', draft)
        self.assertIn('createDeterministicDraft', live)
        self.assertIn('refreshGeneratedDraft', live)
        self.assertIn('renderDraftMeta', live)
        self.assertIn('regenerateDraft', live)
        # 三因子算术复用 gap-attribution 的 decompose，不在文案层复制一套算法
        self.assertIn('return { buildBody, decompose }', gap)
        self.assertIn('gapAttribution.decompose', live)
        # 生成内容只进 textarea，不写 localStorage 草稿（草稿只来自用户输入事件）
        self.assertNotIn('storeSectionDraft', draft)
        self.assertNotIn('localStorage.getItem', draft)
        self.assertNotIn('localStorage.setItem', draft)

    def test_period_review_schedule_css_selector_is_complete(self):
        """排期网格曾是缺选择器的孤立声明，锁回 .pr-schedule 规则。"""
        styles = self.read('frontend/ui_demo/assets/period-review.css')
        self.assertRegex(styles, r'\.pr-schedule\s*\{[^}]*display:\s*grid[^}]*\}')

    def test_quick_date_ranges_use_system_today_not_latest_imported_date(self):
        store = self.read('frontend/ui_demo/assets/runtime/date-range-store.js')
        # 行为断言：日期锚点取系统当天（写法允许变），且不从导入数据反推锚点。
        self.assertRegex(store, r'anchorDate\s*=\s*new Date\(')
        self.assertNotIn('anchorDate = parseDate(latest)', store)

    def test_overview_uses_server_side_matrix_export(self):
        overview = self.read('frontend/ui_demo/assets/overview-live.js')
        self.assertIn('/api/overview/daily-matrix/export', overview)
        export_handler = overview[overview.index("window.addEventListener('tmall:export'"):]
        self.assertNotIn("window.TmallFilters?.toQuery?.()", export_handler)
        self.assertIn("overviewPayload?.capabilities?.can_export === false", export_handler)

    def test_products_export_uses_current_period_range_and_filters(self):
        products = self.read('frontend/ui_demo/assets/products-live.js')
        self.assertIn('dim: state.periodDimension', products)
        self.assertIn('start,', products)
        self.assertIn('end,', products)
        self.assertIn("exportPayload.period = currentWeekPeriod()", products)
        self.assertIn("exportPayload.period = currentMonthPeriod()", products)
        self.assertNotIn('TmallFilters', products)
        self.assertIn('...filters(),', products)
        self.assertIn('star_only: state.starredOnly', products)

    def test_reviews_all_status_option_does_not_secretly_request_pending_review(self):
        reviews = self.read('frontend/ui_demo/assets/reviews-live.js')
        self.assertIn("DemoApi.domainRequest('/api/actions?limit=500')", reviews)
        # 行为断言：过滤在客户端做（不往请求里拼 status 参数）
        self.assertRegex(reviews, r"filter\?\.value \|\| ''")
        self.assertIn('item.status === selected', reviews)
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

    def test_overview_uses_generic_monthly_data_label(self):
        page = self.read('frontend/ui_demo/pages/overview.html')
        adapter = self.read('frontend/ui_demo/assets/overview-live.js')
        self.assertIn('按月度数据对比净销售额、支付金额和推广花费实际值', page)
        self.assertIn('当前导入为月度数据；补充日度导出后可按天查看', page)
        self.assertIn("grain === 'monthly' ? '月度数据' : '日度事实'", adapter)
        self.assertIn('当前未导入日度明细；月度数据已用于上方指标和趋势', adapter)
        self.assertNotIn('派米', page)
        self.assertNotIn('派米', adapter)
        self.assertNotIn('paimi', page.lower())
        self.assertNotIn('paimi', adapter.lower())

    def test_overview_scale_kpis_use_ten_thousand_unit(self):
        adapter = self.read('frontend/ui_demo/assets/overview-live.js')
        # 行为断言：KPI 有万元缩放助手（具体绑定写法允许变）
        self.assertRegex(adapter, r"moneyWan\s*=\s*\(.*\)\s*=>\s*wan\(value,\s*['\"]¥['\"]\)")
        self.assertRegex(adapter, r"numberWan\s*=\s*\(.*\)\s*=>\s*wan\(")
        for key in ('payment_amount', 'net_sales', 'visitors', 'ad_spend'):
            formatter = 'numberWan' if key == 'visitors' else 'moneyWan'
            self.assertIn(f"'{key}'", adapter)
            self.assertIn(formatter, adapter)

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
        # 5-3：默认列从 14 收成 8 列，存储 key 必须跟着从 -v2 提到 -v3，
        # 否则老用户 localStorage 里的 14 列会覆盖新默认（本断言原写死 -v2，已过期）。
        self.assertIn("tmall-overview-matrix-columns-v3", adapter)
        page = self.read('frontend/ui_demo/pages/overview.html')
        styles = self.read_global_styles()
        self.assertIn('overview-matrix-columns-dialog', page)
        self.assertIn('data-overview-matrix-columns-select-all', page)
        self.assertIn('data-overview-matrix-columns-clear-all', page)
        self.assertIn('data-overview-matrix-columns-reset', page)
        self.assertIn('overview-matrix-columns-dialog__body', page)
        self.assertIn('overview-matrix-columns-dialog__body', styles)
        # 行为断言：矩阵列弹层为双栏网格（具体轨道尺寸允许变）
        self.assertRegex(styles, r'grid-template-columns:\s*minmax\([^)]+\)[^;]*minmax\(')

    def test_overview_operations_center_aggregates_real_sources(self):
        page = self.read('frontend/ui_demo/pages/overview.html')
        adapter = self.read('frontend/ui_demo/assets/operations-center.js')
        self.assertIn('data-overview-operations-center', page)
        self.assertIn('../assets/operations-center.js', page)
        self.assertNotIn('../assets/action-calendar.js', page)
        self.assertNotIn('../assets/action-log.js', page)
        for hook in (
            'data-operations-feed', 'data-operations-filter', 'data-operations-refresh',
            'data-operations-calendar-grid', 'data-operations-calendar-prev',
            'data-operations-calendar-next', 'data-operations-calendar-today',
        ):
            self.assertIn(hook, page)
        for contract in ('/api/actions?limit=200', '/api/actions/calendar?', '/api/logs?limit=12', 'Promise.allSettled', 'mergeActions', 'calendarToken', 'buildAnomalyItem', 'tmall:overview-anomalies-ready', 'clearCalendar'):
            self.assertIn(contract, adapter)
        for marker in ('purpose_note', 'action_detail', 'data-action-delete', 'overview.delete_action', 'DELETE', '目的：', '执行：', '负责人', '观察'):
            self.assertIn(marker, adapter)
        self.assertIn("'暂无提醒'", adapter)
        capabilities = self.read('services/page_capability_service.py')
        self.assertIn("'overview.delete_action'", capabilities)
        overview_capabilities = capabilities.split("'key': 'products'", 1)[0]
        self.assertIn("'overview.delete_action'", overview_capabilities)
        self.assertIn("setAttribute('aria-label'", adapter)
        self.assertIn("addEventListener('tmall:overview-actions-ready'", adapter)
        self.assertIn("addEventListener('tmall:overview-anomalies-ready'", adapter)
        self.assertNotIn('data-overview-home-actions', self.read('frontend/ui_demo/assets/overview-live.js'))
        self.assertNotIn('data-overview-home-anomalies', page)

    def test_toolbox_import_supports_multiple_excel_files(self):
        shell = self.read('frontend/ui_demo/assets/shell.js')
        self.assertIn('data-import-file type="file" accept=".xlsx,.xls,.csv,.zip" multiple', shell)
        self.assertIn('Array.from(importFile.files || [])', shell)
        self.assertIn('for (const [index, file] of files.entries())', shell)

    def test_data_center_import_supports_multiple_table_files(self):
        page = self.read('frontend/ui_demo/pages/data-center.html')
        adapter = self.read('frontend/ui_demo/assets/pages/data-center/import-workflow.js')
        self.assertIn('accept=".xlsx,.xls,.csv,.zip" data-import-file multiple', page)
        self.assertIn('Array.from(fileInput.files || [])', adapter)
        self.assertIn('for (const [index, file] of selectedFiles.entries())', adapter)

    def test_data_center_defaults_to_automatic_report_type_detection(self):
        page = self.read('frontend/ui_demo/pages/data-center.html')
        adapter = self.read('frontend/ui_demo/assets/pages/data-center/import-workflow.js')
        self.assertIn('<option value="auto">自动识别</option>', page)
        self.assertLess(
            page.index('<option value="auto">自动识别</option>'),
            page.index('<option value="product_day">商品日度</option>'),
        )
        self.assertIn('sourceLabels[result.source_type]', adapter)

    def test_data_center_exposes_capability_map(self):
        page = self.read('frontend/ui_demo/pages/data-center.html')
        adapter = self.read('frontend/ui_demo/assets/pages/data-center/capability-map.js')
        for hook in (
            'data-capability-summary', 'data-capability-filter',
            'data-capability-table', 'data-capability-detail',
            'data-unsupported-capabilities',
        ):
            self.assertIn(hook, page)
        self.assertIn('data-modal-kind="detail"', page)
        self.assertIn("DemoApi.domainRequest('/api/data-capabilities')", adapter)
        self.assertIn('catalog.unsupported_capabilities', adapter)
        # 焦点还原已收敛到共享的 TmallUI.detailDrawer：open(trigger) 记录来源，
        # close() 里统一还原。页面适配器只负责把触发按钮传进去，不再自己 focus()。
        # （原断言写死适配器里的 trigger?.focus()，是重构前的旧契约，已过期。）
        self.assertIn('capabilityDrawer.open(trigger)', adapter)
        self.assertIn('restore.focus({ preventScroll: true })', self.read('frontend/ui_demo/assets/ui-components.js'))
        self.assertIn('returnFocusNode = trigger ||', self.read('frontend/ui_demo/assets/ui-components.js'))
        self.assertIn('domain.evidence_level', adapter)
        self.assertIn('domain.freshness', adapter)
        self.assertIn("DemoApi.domainRequest('/api/imports')",
                      self.read('frontend/ui_demo/assets/pages/data-center/import-workflow.js'))

    def test_data_center_exposes_page_capability_map(self):
        page = self.read('frontend/ui_demo/pages/data-center.html')
        adapter = self.read('frontend/ui_demo/assets/pages/data-center/page-capabilities.js')
        for hook in (
            'data-page-capability-summary', 'data-page-capability-filter',
            'data-page-capability-table', 'data-page-capability-detail',
        ):
            self.assertIn(hook, page)
        self.assertIn("DemoApi.domainRequest('/api/page-capabilities')", adapter)
        self.assertIn('data-modal-kind="detail"', page)
        # 同上：焦点还原在共享 detailDrawer 里，适配器只传触发按钮。
        self.assertIn('capabilityDrawer.open(button)', adapter)
        self.assertIn('restore.focus({ preventScroll: true })', self.read('frontend/ui_demo/assets/ui-components.js'))
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

    def test_page_capability_request_can_retry_after_a_transient_failure(self):
        api = self.read('frontend/ui_demo/assets/api.js')
        # 行为断言：能力请求失败后清理缓存以便重试（具体语句顺序允许变）
        self.assertRegex(api, r'const pending = domainRequest\(`/api/page-capabilities\$\{query\}`\);')
        self.assertIn('pageCapabilityCache.delete(pageKey)', api)

    def test_api_client_maps_business_actions_to_registry_keys(self):
        api = self.read('frontend/ui_demo/assets/api.js')
        for capability, selector in (
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
        self.assertIn('aria-label="新增运营动作"', shell)

    def test_refresh_handlers_capture_event_targets_before_async_cleanup(self):
        shell = self.read('frontend/ui_demo/assets/shell.js')
        self.assertGreaterEqual(shell.count('const refreshButton = event.currentTarget;'), 1)
        self.assertNotIn('setTimeout(() => event.currentTarget.classList.remove', shell)

    def test_scan_write_controls_guard_against_duplicate_submissions(self):
        shell = self.read('frontend/ui_demo/assets/shell.js')
        self.assertIn('if (button.disabled) return;', shell)
        self.assertIn('try { await handler(); } finally', shell)
        self.assertIn('const addScanButton = document.querySelector', shell)
        self.assertIn('finally { addScanButton.disabled = false; }', shell)

    def test_page_operations_reference_explicit_capability_contract(self):
        # products 的能力检查（DemoApi.can）随 star-button 渲染迁移到 table-render.js
        for script in (
            'overview-live.js', 'product-detail-live.js',
            'promotion-live.js', 'lifecycle-live.js', 'goals-live.js',
            'pages/data-center/import-workflow.js', 'reviews-live.js', 'settings-live.js',
        ):
            content = self.read(f'frontend/ui_demo/assets/{script}')
            self.assertIn('DemoApi.can(', content, script)
        products_table = self.read('frontend/ui_demo/assets/pages/products/table-render.js')
        self.assertIn('DemoApi.can(', products_table, 'pages/products/table-render.js')

    def test_formal_mutation_controls_use_registered_capabilities(self):
        overview = self.read('frontend/ui_demo/pages/overview.html')
        products = self.read('frontend/ui_demo/pages/products.html')
        api = self.read('frontend/ui_demo/assets/api.js')
        self.assertIn('data-capability-key="overview.create_action"', overview)
        self.assertIn('data-capability-key="products.catalog_edit"', products)
        self.assertIn('data-capability-key="products.list" data-products-batch-copy', products)
        self.assertIn('aria-label="复制选中商品 ID"', products)
        self.assertIn('overview.create_action', api)
        self.assertIn('products.catalog_edit', api)
        self.assertIn("['[data-products-batch-copy]', 'products.list']", api)

    def test_products_batch_copy_uses_selected_ids_without_write_api(self):
        # 复制商品 ID 随批量操作迁移到 batch-ops.js（products-live.js 拆分第四步）
        products = self.read('frontend/ui_demo/assets/products-live.js')
        batch = self.read('frontend/ui_demo/assets/pages/products/batch-ops.js')
        self.assertIn('async function copySelectedProductIds(button)', batch)
        self.assertIn('[...state.selected]', batch)
        self.assertIn("join('\\n')", batch)
        self.assertIn('navigator.clipboard?.writeText', batch)
        self.assertIn('copyWithFallback(text)', batch)
        self.assertIn("toast('请选择商品')", batch)
        self.assertIn("toast(`已复制 ${ids.length} 个商品 ID`)", batch)
        self.assertNotIn("'/api/products/batch-copy'", products)
        self.assertNotIn("'/api/products/batch-copy'", batch)

    def test_formal_pages_use_domain_mutation_endpoints(self):
        products = self.read('frontend/ui_demo/assets/products-live.js')
        products_batch = self.read('frontend/ui_demo/assets/pages/products/batch-ops.js')
        overview = self.read('frontend/ui_demo/assets/overview-live.js')
        # 行级编辑/收藏端点在主闭包，批量端点在 batch-ops.js
        self.assertIn('/api/products/${encodeURIComponent(id)}/metadata', products)
        self.assertIn('/api/products/${encodeURIComponent(id)}/star', products)
        self.assertIn("'/api/products/batch-update'", products_batch)
        self.assertIn("'/api/products/batch-tags'", products_batch)
        self.assertIn("'/api/actions'", overview)
        self.assertIn('capability_key: \'overview.create_action\'', overview)
        for content in (products, products_batch):
            self.assertNotIn("'/api/star'", content)
            self.assertNotIn("'/api/batch_update'", content)
            self.assertNotIn("'/api/batch_tags'", content)
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
        self.assertIn('SCAN_FOLDER_NOT_ALLOWED', shell)
        self.assertIn('TmallScanUi', shell)
        self.assertNotIn('/api/manage/schedules', shell)

    def test_folder_scan_uses_import_scans_domain_endpoints(self):
        # 4-8：manage.html / manage-live.js 已退役（/manage 302 → /settings，且不在导航里）。
        # 原先这条用例断言的是 manage 页面；文件夹扫描的完整实现在 settings 里（超集：
        # 除 /run 外还有 /runs、/files、/files/<id>/retry、/delete），断言随之迁移过来。
        settings = self.read('frontend/ui_demo/assets/settings-live.js')
        page = self.read('frontend/ui_demo/pages/settings.html')

        self.assertIn("DemoApi.domainRequest('/api/import-scans')", settings)
        self.assertIn('/api/import-scans/${Number(job.id)}', settings)
        self.assertIn('/api/import-scans/${Number(job.id)}/run', settings)
        self.assertIn('/api/import-scans/${Number(job.id)}/runs', settings)
        self.assertIn('/api/import-scans/${Number(job.id)}/files', settings)
        self.assertIn('JSON.stringify({ force: true })', settings)
        # 废弃的旧端点不得复活
        self.assertNotIn('/api/manage/schedules', settings)
        self.assertNotIn('/api/manage/schedules', page)
        self.assertIn('name="folder_path"', page)
        self.assertIn('name="source_type"', page)
        self.assertIn('data-settings-select-scan-folder', page)
        self.assertIn('IMPORT_SCAN_ALLOWED_ROOTS', page)
        self.assertIn('TmallScanUi', settings)

    def test_settings_manual_scan_forces_immediate_discovery(self):
        settings = self.read('frontend/ui_demo/assets/settings-live.js')
        page = self.read('frontend/ui_demo/pages/settings.html')
        self.assertIn('/api/import-scans/${Number(job.id)}/run', settings)
        self.assertIn('JSON.stringify({ force: true })', settings)
        self.assertIn("job.status === 'error' ? '配置异常'", settings)
        self.assertIn('runButton.disabled = !job.enabled', settings)
        self.assertIn('can_manage', settings)
        self.assertIn('scan_environment', settings)
        self.assertIn('TmallScanUi', settings)
        self.assertIn('data-settings-select-scan-folder', page)
        self.assertIn('IMPORT_SCAN_ALLOWED_ROOTS', page)
        self.assertIn('scan_environment', settings)
        self.assertIn('can_manage', settings)
        self.assertIn('data-scan-environment', page)
    def test_lifecycle_load_keeps_cards_available_when_assessments_fail(self):
        lifecycle = self.read('frontend/ui_demo/assets/lifecycle-live.js')
        self.assertIn("loadAssessments().catch", lifecycle)
        self.assertIn("生命周期评估加载失败，不影响月度表现", lifecycle)

    def test_overview_optional_panels_do_not_fail_the_whole_page(self):
        overview = self.read('frontend/ui_demo/assets/overview-live.js')

        self.assertIn("DemoApi.request(`/api/anomalies?", overview)
        self.assertIn(".catch((error) => { console.error(error); return { error: true }; })", overview)
        self.assertIn("window.dispatchEvent(new CustomEvent('tmall:overview-anomalies-ready'", overview)
        self.assertIn("{ detail: { anomalies: [] } }", overview)
        self.assertIn("const progressFor = (actualKey, targetKey, progress)", overview)
        self.assertIn("actualValue = (key, formatter)", overview)

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
        reviews = self.read('frontend/ui_demo/assets/reviews-live.js')
        data_center = self.read('frontend/ui_demo/assets/pages/data-center/import-workflow.js')

        for value, label in (
            ('delisted', '下架'), ('P0', '紧急'), ('A', '优秀'),
            ('passed', '通过'), ('failed', '未通过'),
        ):
            self.assertIn(value, labels)
            self.assertIn(label, labels)
        self.assertNotIn('服务器分页 limit', products)
        self.assertIn("DemoLabels.label('action'", overview)
        self.assertIn("DemoLabels.label('quality'", data_center)
        self.assertIn("todo.action_type || '运营动作'", overview)
        self.assertNotIn('value="operator"', reviews)

        for page in ('goals.html', 'reviews.html', 'lifecycle.html'):
            self.assertNotIn('value="operator"', self.read(f'frontend/ui_demo/pages/{page}'))

        # 4-8：原第二条是 manage.html（已退役），换成同样加载 labels.js 的 settings.html。
        for page in ('overview.html', 'settings.html'):
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

    def test_lifecycle_images_fall_back_when_external_urls_expire(self):
        adapter = self.read('frontend/ui_demo/assets/lifecycle-live.js')
        self.assertIn("const cardImage = card.querySelector('img');", adapter)
        self.assertIn("cardImage?.addEventListener('error'", adapter)
        self.assertIn("image.addEventListener('error'", adapter)
        self.assertNotIn('<img src="${thumbnailUrl}"', adapter)

    def test_lifecycle_editor_is_a_real_modal_and_closes_out_of_layout(self):
        page = self.read('frontend/ui_demo/pages/lifecycle.html')
        adapter = self.read('frontend/ui_demo/assets/lifecycle-live.js')
        styles = self.read_global_styles()
        self.assertIn('aria-labelledby="lifecycle-edit-title"', page)
        self.assertIn('data-lifecycle-edit-product', page)
        self.assertIn('data-lifecycle-edit-cancel', page)
        self.assertIn('.modal-form:not([open])', styles)
        self.assertIn('background: var(--surface-base)', styles)
        self.assertIn('editDialog.hidden = true', adapter)
        self.assertIn('editDialog.addEventListener(\'cancel\'', adapter)

    def test_data_center_revert_explains_impact_before_request(self):
        data_center = self.read('frontend/ui_demo/assets/pages/data-center/import-workflow.js')
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
        self.assertIn("setStatus('');", adapter)
        self.assertIn('saveMonth', adapter)
        self.assertIn('lockMonth', adapter)
        self.assertIn('/allocation-preview?annual_target=', adapter)
        self.assertIn('annualTargetDirty', adapter)
        self.assertNotIn('prepareMonthAdjustment', adapter)

    def test_reviews_expand_one_action_and_block_missing_observation(self):
        reviews = self.read('frontend/ui_demo/assets/reviews-live.js')
        self.assertIn("document.createElement('details')", reviews)
        self.assertIn('等待观察数据后再复盘', reviews)

    def test_settings_import_rules_are_the_only_settings_mapping_editor(self):
        page = self.read('frontend/ui_demo/pages/settings.html')
        settings = self.read('frontend/ui_demo/assets/settings-live.js')
        products = self.read('frontend/ui_demo/assets/pages/products/column-settings.js')
        self.assertIn('<span>导入规则</span>', page)
        self.assertIn('data-template-mappings', settings)
        self.assertIn('body: JSON.stringify({ mapping_templates: clone(templateDraft.mapping_templates) })', settings)
        for hook in ('data-template-default-view', 'data-template-add-view', 'data-settings-view-field-selector', 'data-template-views'):
            self.assertNotIn(hook, page)
            self.assertNotIn(hook, settings)
        for field in ('view_templates', 'product_view_template'):
            self.assertNotIn(field, settings)
        self.assertIn('data-products-template-select', products)
        self.assertIn('data-products-template-save', products)
        self.assertIn('async function updateProductTemplate', products)
        self.assertIn('async function deleteProductTemplate', products)

    def test_chart_adapter_preserves_page_chart_options(self):
        charts = self.read('frontend/ui_demo/assets/charts.js')
        self.assertIn('toEchartsOption', charts)
        self.assertIn('config.options', charts)
        self.assertIn('ResizeObserver', charts)

    def test_products_do_not_render_empty_image_elements(self):
        # 图像渲染逻辑迁移到 table-render.js（products-live.js 拆分第三步）
        products = self.read('frontend/ui_demo/assets/pages/products/table-render.js')
        image_block = products[products.index("const identity = document.createElement('div');"):products.index("const title = document.createElement('div');")]
        self.assertIn('if (item.image_url)', image_block)
        self.assertIn('product-thumb--placeholder', image_block)

    def test_products_column_dialog_supports_full_selection_and_custom_templates(self):
        page = self.read('frontend/ui_demo/pages/products.html')
        adapter = self.read('frontend/ui_demo/assets/pages/products/column-settings.js')
        # 列定义（columnGroups）仍在页面主脚本，弹层行为在 column-settings 模块
        main = self.read('frontend/ui_demo/assets/products-live.js')
        for hook in (
            'data-products-columns-select-all',
            'data-products-columns-clear-all',
            'data-products-template-select',
            'data-products-template-name',
            'data-products-template-save',
        ):
            self.assertIn(hook, page)
        for field in ('search_conversion', 'paid_ipv', 'direct_gmv', 'cart_cost', 'click_rate'):
            self.assertIn(f"key: '{field}'", main)
        self.assertIn('saveCustomTemplate', adapter)
        self.assertIn("'/api/settings'", adapter)

        column_definition = main[main.index('const columnGroups = ['):main.index('const columns =')]
        column_keys = re.findall(r"key: '([^']+)'", column_definition)
        self.assertEqual(len(column_keys), len(set(column_keys)), 'column settings must not render duplicate fields')
        self.assertEqual(adapter.count('function renderTemplateSelect('), 1)
        self.assertEqual(adapter.count('function saveCustomTemplate('), 1)
        selector = self.read('frontend/ui_demo/assets/field-selector.js')
        self.assertIn('button.title = `${name}${field.label}`', selector)
        self.assertIn('button.disabled = position + offset < 0 || position + offset >= selected.length', selector)
        self.assertIn('requiredKeys', selector)
        self.assertIn('input.disabled = field.required || field.locked', selector)
        self.assertIn('function removeField(position)', selector)
        self.assertIn("dataset.lucide = 'trash-2'", selector)
        # BI 字段目录分类逻辑在页面主脚本（products-live）
        self.assertIn('Number(field.nonempty_count || 0) > 0', main)
        self.assertIn('function classifyBiField(field)', main)
        self.assertIn("return '交易与收益'", main)
        self.assertIn("return '推广与投放'", main)
        self.assertIn("return '流量与转化'", main)
        self.assertIn("return '商品与库存'", main)
        self.assertIn("return '其他 BI 字段'", main)
        self.assertNotIn("columnGroups.push({ label: 'BI 数据源字段'", adapter)

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
        for page_name, script_path in (
            ('products', 'pages/products/column-settings.js'),
            ('promotion', 'promotion-live.js'),
            ('lifecycle', 'lifecycle-live.js'),
        ):
            page = self.read(f'frontend/ui_demo/pages/{page_name}.html')
            script = self.read(f'frontend/ui_demo/assets/{script_path}')
            self.assertIn('../assets/field-template-manager.js', page)
            self.assertIn('DemoFieldTemplateManager', script)
        self.assertIn("'/api/settings'", self.read('frontend/ui_demo/assets/products-live.js'))
        self.assertIn("'/api/settings'", self.read('frontend/ui_demo/assets/promotion-live.js'))
        promotion = self.read('frontend/ui_demo/assets/promotion-live.js')
        self.assertIn('template.name = persisted.label || template.name', promotion)
        self.assertIn('...persistedBuiltinTemplates, ...builtinTemplates, ...customTemplates', promotion)

    def test_products_field_selection_uses_a_separate_order_preview(self):
        page = self.read('frontend/ui_demo/pages/products.html')
        script = self.read('frontend/ui_demo/assets/pages/products/column-settings.js')
        selector = self.read('frontend/ui_demo/assets/field-selector.js')
        self.assertIn('data-products-field-selector', page)
        self.assertIn('TmallUI.fieldSelector', script)
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
        for page_name, script_path in (
            ('products', 'pages/products/column-settings.js'),
            ('promotion', 'promotion-live.js'),
        ):
            page = self.read(f'frontend/ui_demo/pages/{page_name}.html')
            script = self.read(f'frontend/ui_demo/assets/{script_path}')
            self.assertIn('../assets/field-selector.js', page)
            self.assertIn('TmallUI.fieldSelector', script)

    def test_creative_board_is_an_all_time_category_scoped_page(self):
        page = self.read('frontend/ui_demo/pages/creative-board.html')
        styles = self.read('frontend/ui_demo/assets/creative-board.css')
        adapter = self.read('frontend/ui_demo/assets/creative-board-live.js')
        shell = self.read('frontend/ui_demo/assets/shell.js')
        self.assertIn('<body data-page="creative-board">', page)
        self.assertIn('../assets/creative-board.css?', page)
        self.assertIn('../assets/creative-board-live.js?', page)
        self.assertIn("DemoApi.domainRequest('/api/creative-board'", adapter)
        self.assertIn("params.get('category')", adapter)
        self.assertIn("params.get('product_id')", adapter)
        self.assertIn("params.get('q')", adapter)
        self.assertIn("url.searchParams.set('q'", adapter)
        self.assertIn('data-cb-categories', page)
        self.assertIn('data-cb-search', page)
        self.assertIn('data-cb-category', adapter)
        self.assertIn('history.replaceState', adapter)
        self.assertNotIn('start:', adapter)
        self.assertNotIn('end:', adapter)
        self.assertIn("'creative-board'", shell)
        self.assertIn('body[data-page="creative-board"] .demo-period', styles)
        self.assertIn('body[data-page="creative-board"] .demo-category', styles)
        self.assertIn("pagesWithoutDateRange", shell)

    def test_promotion_outer_view_restores_products_without_confusing_inner_tab(self):
        page = self.read('frontend/ui_demo/pages/promotion.html')
        views = self.read('frontend/ui_demo/assets/promotion-views-live.js')
        product_adapter = self.read('frontend/ui_demo/assets/promotion-live.js')
        self.assertIn('data-promotion-view="products"', page)
        self.assertIn('data-promotion-view-panel="products"', page)
        self.assertNotIn('new-products', page)
        self.assertIn("new Set(['overview', 'plans', 'products']).has(storedView)", views)
        self.assertNotIn('newProduct', views)
        self.assertIn("initialPromotionParams.get('tab')", product_adapter)
        self.assertIn("data-promotion-tab=\"products\"", page)

    def test_new_products_is_a_standalone_promotion_page(self):
        page = self.read('frontend/ui_demo/pages/new-products.html')
        adapter = self.read('frontend/ui_demo/assets/new-products-live.js')
        shell = self.read('frontend/ui_demo/assets/shell.js')
        self.assertIn('data-page="new-products"', page)
        self.assertIn('../assets/new-products-live.js', page)
        for hook in ('data-promotion-new-funnel', 'data-promotion-new-kpi', 'data-promotion-new-launch-body', 'data-promotion-new-body', 'data-promotion-structure-template', 'data-new-products-image-dialog', 'data-new-products-image-preview'):
            self.assertIn(hook, page)
        self.assertIn('../assets/creative-board.css?', page)
        self.assertIn('/api/promotion/new-products?', adapter)
        self.assertIn('/api/creative-board?', adapter)
        self.assertIn('data-new-products-image', adapter)
        self.assertIn('renderCreativePanel', adapter)
        self.assertNotIn('window.location.href = `/creative-board?', adapter)
        self.assertIn("addEventListener('tmall:date-range-change'", adapter)
        self.assertIn("addEventListener('tmall:refresh'", adapter)
        self.assertIn('data-promotion-new-launch-toggle', page)
        self.assertIn('total_product_count', adapter)
        self.assertIn('promoted_product_count', adapter)
        self.assertIn('unpromoted_product_count', adapter)
        self.assertIn('promotion_coverage', adapter)
        self.assertIn('launchesExpanded', adapter)
        self.assertIn('cb-creative-table', adapter)
        self.assertIn('data-new-products-creative-sort', adapter)
        self.assertIn("creativeSort: { key: 'clicks', direction: 'desc' }", adapter)
        self.assertIn("direction === 'asc' ? 'arrow-up' : 'arrow-down'", adapter)
        self.assertIn("state.creativeSort.direction === 'desc' ? 'asc' : 'desc'", adapter)
        self.assertIn(".cb-creative-table", self.read('frontend/ui_demo/assets/creative-board.css'))
        self.assertIn(".cb-sort-button", self.read('frontend/ui_demo/assets/creative-board.css'))
        self.assertIn("['new-products', '新品推广', 'sparkles', 'new-products']", shell)


        page = self.read('frontend/ui_demo/pages/data-center.html')
        adapter = self.read('frontend/ui_demo/assets/pages/data-center/import-workflow.js')
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

    def test_template_configuration_keeps_product_templates_on_products_page(self):
        settings = self.read('frontend/ui_demo/assets/settings-live.js')
        products = self.read('frontend/ui_demo/assets/pages/products/column-settings.js')
        promotion = self.read('frontend/ui_demo/assets/promotion-live.js')
        self.assertIn('templateDraft.mapping_templates', settings)
        self.assertNotIn('templateDraft.view_templates', settings)
        self.assertNotIn('templateDraft.product_view_template', settings)
        self.assertIn("'/api/settings'", products)
        self.assertIn('view_templates', products)
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
        self.assertIn('../assets/product-detail-live.js', page)
        self.assertNotIn('../assets/product-detail-dialog.js', page)

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

    def test_product_detail_themes_keep_search_and_promotion_workbench_contract(self):
        page = self.read('frontend/ui_demo/pages/product-detail.html')
        component = self.read('frontend/ui_demo/assets/product-detail-live.js')
        for tab in ('search', 'promotion'):
            self.assertIn(f'data-product-detail-tab="{tab}"', page)
            self.assertIn(f'data-product-detail-panel="{tab}"', page)
        for marker in ('renderSearchAnalysis', 'renderPromotionAnalysis', 'loadTheme', 'themeCache', '/promotion?', '/api/promotion/campaign-detail'):
            self.assertIn(marker, component)
        self.assertIn('tmall:date-range-change', component)
        self.assertIn('themeCache.clear()', component)
        self.assertIn('data-product-promotion-campaigns', page)

    def test_product_detail_dialog_keeps_search_analysis_in_primary_detail_flow(self):
        component = self.read('frontend/ui_demo/assets/product-detail-dialog.js')
        styles = self.read_global_styles()
        self.assertIn("['search', '搜索分析']", component)
        self.assertIn('function renderSearch', component)
        self.assertIn("if (tab === 'search') panel.append(renderSearch(detail));", component)
        self.assertIn('search_visitors', component)
        self.assertIn('product-detail-search-metrics', styles)
        self.assertIn('商品级关键词归因', component)

    def test_product_detail_overview_has_linked_operating_trend(self):
        page = self.read('frontend/ui_demo/pages/products.html')
        component = self.read('frontend/ui_demo/assets/product-detail-dialog.js')
        styles = self.read_global_styles()
        self.assertIn('../assets/echarts-custom.min.js', page)
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

    def test_product_detail_dialog_promotion_campaigns_support_plan_drilldown(self):
        component = self.read('frontend/ui_demo/assets/product-detail-dialog.js')
        self.assertIn('loadPromotionCampaignDetail', component)
        self.assertIn('/api/promotion/campaign-detail?', component)
        self.assertIn('查看计划商品构成', component)
        self.assertIn('product-detail-promotion-campaign-detail', component)

    def test_centered_dialog_consolidation_removes_business_drawers(self):
        shell = self.read('frontend/ui_demo/assets/shell.js')
        promotion = self.read('frontend/ui_demo/pages/promotion.html')
        component = self.read('frontend/ui_demo/assets/product-detail-dialog.js')
        self.assertIn('<dialog class="toolbox-dialog" data-toolbox-dialog', shell)
        self.assertNotIn('toolbox-overlay', shell)
        self.assertNotIn('toolbox-drawer', shell)
        self.assertIn('<template data-promotion-dialog-template', promotion)
        self.assertNotIn('demo-drawer__backdrop', promotion)
        self.assertNotIn('data-promotion-drawer', promotion)
        self.assertIn("setAttribute('role', 'tablist')", component)
        self.assertIn('data-product-detail-tab="${id}"', component)
        # 详情面统一 NUI 抽屉：共享商品详情不再自建 <dialog>，锚定抽屉接入点。
        self.assertIn('window.TmallUI?.detailDrawer', component)
        self.assertIn("drawer.node.classList.add('product-detail-dialog')", component)
        self.assertIn('lifecycle-detail__image', component)
        self.assertIn('lifecycle-detail-tabs', component)
        for tab in ('overview', 'promotion', 'trend', 'flow-source', 'lifecycle', 'collaboration'):
            self.assertIn(f"['{tab}'", component)
        self.assertIn('../assets/ui-components.js', self.read('frontend/ui_demo/pages/products.html'))
        self.assertIn('../assets/promotion-field-definitions.js', self.read('frontend/ui_demo/pages/products.html'))
        self.assertIn('TmallUI?.table', component)
        self.assertIn('openPromotionFieldDialog', component)
        self.assertIn('DemoFieldTemplateManager', component)
        self.assertIn('function renderPromotion', component)
        self.assertIn('product-detail-promotion-grid', component)
        self.assertIn('加购成本', component)
        self.assertIn('拉新成本', component)
        self.assertIn('引导潜客占比', component)
        self.assertIn('.product-detail-promotion-metrics', self.read_global_styles())
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
        component_styles = self.read_global_styles()
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
        styles = self.read_global_styles()
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
        self.assertIn('.lifecycle-detail-panel > .ui-panel { min-width: 0; margin-bottom: 0; }', styles)

    def test_lifecycle_field_settings_cover_monthly_operating_sections(self):
        lifecycle = self.read('frontend/ui_demo/assets/lifecycle-live.js')
        settings = self.read('services/settings_service.py')
        styles = self.read_global_styles()
        for field in ('net_sales', 'visitors', 'payment_conversion', 'refund_rate', 'repurchase_rate', 'cross_sell_rate'):
            self.assertIn(field, lifecycle)
            self.assertIn(field, settings)
        self.assertIn("traffic:", lifecycle)
        self.assertIn("width: min(1120px", styles)
        self.assertIn("minmax(360px, .85fr)", styles)
        self.assertIn("grid-template-rows: minmax(220px, 1fr)", styles)

    def test_shared_typography_tokens_cover_detail_dialog_scales(self):
        tokens = self.read('frontend/ui_demo/assets/tokens.css')
        styles = self.read_global_styles()
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
        self.assertIn('.ui-panel > p:not(.panel__hint)', styles)

    def test_promotion_field_selection_uses_a_separate_order_preview(self):
        page = self.read('frontend/ui_demo/pages/promotion.html')
        script = self.read('frontend/ui_demo/assets/promotion-live.js')
        selector = self.read('frontend/ui_demo/assets/field-selector.js')
        self.assertIn('data-promotion-field-selector', page)
        self.assertIn('TmallUI.fieldSelector', script)
        self.assertIn("previewDataAttribute: 'data-promotion-preview-key'", script)
        self.assertIn('function renderPreview', selector)

    def test_promotion_tabs_do_not_fabricate_attribution_or_unnamed_products(self):
        adapter = self.read('frontend/ui_demo/assets/promotion-live.js')
        styles = self.read_global_styles()
        self.assertNotIn('推算归因成交', adapter)
        self.assertNotIn('未命名商品', adapter)
        self.assertIn("performance.data?.breakdowns", adapter)
        self.assertIn('.promotion-template-bar[hidden]', styles)

    def test_promotion_does_not_fabricate_breakdown_rows_when_api_has_no_data(self):
        adapter = self.read('frontend/ui_demo/assets/promotion-live.js')
        self.assertNotIn('demoBreakdowns', adapter)
        self.assertNotIn('demo-keyword-', adapter)

    def test_echarts_pages_use_block_containers_not_canvas_elements(self):
        # 4-8：compare.html 已退役。
        for page in ('overview.html', 'promotion.html', 'lifecycle.html'):
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
        adapter = self.read('frontend/ui_demo/assets/pages/data-center/import-workflow.js')
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

    def test_data_center_does_not_silently_drop_template_settings_failure(self):
        adapter = self.read('frontend/ui_demo/assets/pages/data-center/import-workflow.js')
        self.assertIn("renderDataState('source-unavailable'", adapter)
        self.assertIn('导入模板设置不可用', adapter)

    def test_overview_trend_has_an_explicit_empty_state(self):
        adapter = self.read('frontend/ui_demo/assets/overview-live.js')
        self.assertIn('当前周期暂无趋势数据', adapter)
        self.assertIn('if (!rows.length)', adapter)

    # 4-8：原 test_compare_page_explains_when_no_periods_are_available 随 compare.html /
    # compare-live.js 一起退役。该空态断言针对的是 compare 页独有的“无可对比周期”分支，
    # 没有可迁移的目标（overview 的对比模式走 /api/compare?dim=monthly，空态由
    # test_overview_trend_has_an_explicit_empty_state 覆盖）。

    def test_ui_audit_regressions_are_covered(self):
        shell = self.read('frontend/ui_demo/assets/shell.js')
        tokens = self.read('frontend/ui_demo/assets/tokens.css')
        lifecycle = self.read('frontend/ui_demo/assets/lifecycle-live.js')
        lifecycle_page = self.read('frontend/ui_demo/pages/lifecycle.html')
        products = self.read('frontend/ui_demo/assets/products-live.js')
        products_page = self.read('frontend/ui_demo/pages/products.html')
        components = self.read_global_styles()
        settings = self.read('frontend/ui_demo/assets/settings-live.js')

        self.assertIn('data-skip-link', shell)
        self.assertIn('closeMobileNavigation', shell)
        self.assertIn("event.key === 'Escape'", shell)
        self.assertIn('name="scan_name"', shell)
        self.assertIn('name="scan_folder"', shell)
        self.assertIn('color-scheme: light', tokens)
        self.assertIn('color-scheme: dark', tokens)
        self.assertIn('meta[name="theme-color"]', shell)
        self.assertIn('image.width = 42;', lifecycle)
        self.assertIn('image.height = 42;', lifecycle)
        self.assertIn("image.loading = 'lazy';", lifecycle)
        self.assertIn('window.ProductDetailDialog?.open({ productId: id', products)
        self.assertNotIn('data-product-drawer', products)
        self.assertIn('beforeunload', settings)
        self.assertIn('data-products-more-filters', products_page)
        self.assertIn('data-products-more-filters-toggle', products_page)
        self.assertIn('[data-products-more-filters][hidden] { display: none; }', components)
        self.assertIn('min-height: 40px', components)
        self.assertIn('min-height: 44px', components)
        self.assertIn('body[data-page="promotion"] .ui-metric-grid { grid-template-columns: repeat(12, minmax(0, 1fr)); }', components)
        self.assertIn('.field-order-preview__button { width: 44px; min-width: 44px; height: 44px; }', components)
        self.assertNotIn('<img data-detail-image', lifecycle_page)
        self.assertIn('new Image(52, 52)', lifecycle)
        self.assertIn("image.loading = 'lazy'", lifecycle)

    def test_business_details_use_centered_dialog_widths(self):
        shell = self.read('frontend/ui_demo/assets/shell.css')
        components = self.read_global_styles()

        self.assertIn('width: min(720px, calc(100vw - 32px))', shell)
        self.assertIn('width: min(680px, calc(100vw - 32px))', components)
        self.assertIn('max-height: calc(100dvh - 24px)', shell)
        self.assertIn('max-height: calc(100dvh - 24px)', components)
        self.assertNotIn('.demo-drawer {', shell)

    def test_settings_exposes_desktop_version_management(self):
        shell = self.read('frontend/ui_demo/assets/shell.js')
        adapter = self.read('frontend/ui_demo/assets/desktop-integration.js')
        version = self.read('frontend/ui_demo/assets/version.js')

        self.assertIn('data-sidebar-meta', shell)
        self.assertIn('data-sidebar-version', shell)
        self.assertIn('data-sidebar-check-update', shell)
        self.assertIn('demo-sidebar__meta-actions', shell)
        self.assertIn('GitHub 仓库', shell)
        self.assertIn('demo-sidebar__github-icon', shell)
        self.assertNotIn('data-lucide="github"', shell)
        self.assertIn('更新说明', shell)
        self.assertIn('desktop-integration.js', shell)
        self.assertIn('window.tmallDesktop', adapter)
        self.assertIn('panel.hidden = false', adapter)
        self.assertIn("client=web", adapter)
        self.assertIn('window.TMALL_WEB_VERSION', adapter)
        self.assertIn('latestReleaseApi', adapter)
        self.assertIn('checkRelease', adapter)
        self.assertIn('repository:', version)
        self.assertIn('https://gitcode.com/owen891/tmall-dashboard/releases', version)
        self.assertIn('https://gitcode.com/api/v5/repos/owen891/tmall-dashboard/releases/latest', version)
        self.assertIn('getVersion()', adapter)
        self.assertIn('checkForUpdates()', adapter)

    def test_write_operations_lock_controls_and_restore_failed_state(self):
        data_center = self.read('frontend/ui_demo/assets/pages/data-center/import-workflow.js')
        settings = self.read('frontend/ui_demo/assets/settings-live.js')
        promotion = self.read('frontend/ui_demo/assets/promotion-live.js')

        self.assertIn('button.disabled = true;', data_center)
        self.assertIn('批次撤销失败，请重试', data_center)
        self.assertIn('finally {', data_center)
        self.assertIn('const savingState = { core: false, templates: false, classification: false };', settings)
        self.assertIn('const setButtonBusy = (button, busy, idleLabel)', settings)
        self.assertIn("button.toggleAttribute('aria-busy', busy)", settings)
        self.assertIn('discard.disabled = !dirty || Boolean(savingState[domain])', settings)
        self.assertIn('savingState.templates = true;', settings)
        self.assertIn('finally { savingState.templates = false;', settings)
        self.assertIn("state.selectedFields[tab] = previousSelectedFields", promotion)
        self.assertIn("actionButton.setAttribute('aria-busy', 'true')", promotion)
        self.assertIn('await deletePromotionTemplate(remove.dataset.promotionDeleteTemplate)', promotion)

    def test_frontend_presentation_contract_keeps_shared_styles_and_resumable_views(self):
        promotion_page = self.read('frontend/ui_demo/pages/promotion.html')
        components = self.read_global_styles()
        products = self.read('frontend/ui_demo/assets/products-live.js')
        promotion = self.read('frontend/ui_demo/assets/promotion-live.js')
        lifecycle = self.read('frontend/ui_demo/assets/lifecycle-live.js')

        self.assertNotIn('<style', promotion_page)
        for selector in ('.promotion-command', '.promotion-board-grid', '.promotion-detail-table'):
            self.assertIn(selector, components)
        self.assertIn('restoreUrlState();', products)
        self.assertIn('syncUrlState();', products)
        self.assertIn('restorePromotionUrl();', promotion)
        self.assertIn('syncPromotionUrl();', promotion)
        self.assertIn('syncLifecycleUrl();', lifecycle)


if __name__ == '__main__':
    unittest.main()
