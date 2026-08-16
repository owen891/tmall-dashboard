# TM 1.0 PRD 差距收口实施规划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 保留现有 Flask + SQLite + 原生 HTML/CSS/JavaScript 架构，只实施当前代码相对 `docs/PRD_KEEP_EXISTING_ARCHITECTURE.md` 的 6 类真实缺口，并以自动化测试和隔离恢复演练证明交付结果。

**Architecture:** `frontend/ui_demo/` 继续作为正式工作台，`frontend/ui_demo/assets/shell.js` 维护共享筛选状态，现有 Flask blueprint 维护 HTTP 契约，业务计算进入现有 service/repository。设置模板通过 `/api/settings` 持久化并被商品页、数据中心真实消费；缺失数据统一使用标准 availability 状态，禁止补零或 mock。

**Tech Stack:** Python 3.14, Flask, SQLite, Waitress, 原生 JavaScript/CSS, ECharts, unittest, Node `--check`。

---

## 现状基线

2026-08-13 在当前工作区重新验证：

- `py -3 -m unittest discover -s tests -v`：148 项通过。
- 16 个 `frontend/ui_demo/assets/*.js`：`node --check` 全部通过。
- `node scripts/validate_ui_demos.cjs`：7 个正式页面通过。
- `py -3 scripts/production_preflight.py`：隔离数据库 integrity 为 `ok`，38 张表，健康检查和正式路由均为 HTTP 200。

以上只证明现有契约未回归。已确认完成且本规划不重复实施：五层目标、动作状态机与回算、周期复盘、推广下钻、生命周期门槛与人工锁定、事务/幂等导入、批次撤销、审计、Waitress 启动与备份。

## 版本边界

- **1.0 收口必做：** 全局筛选、商品经营完整规格、设置模板真实接入、数据中心字段识别、总览日度矩阵。
- **1.0 发布门禁：** 统一状态契约、`right-rail` 骨架、桌面与 390px 冒烟、隔离恢复演练。
- **1.1 候选：** 新增算法或新分析模块；不混入本轮 1.0 收口。
- **1.2 候选：** 不影响 1.0 使用的性能与长期维护重构；不阻塞本轮发布。

## Task 1: 建立 PRD 差距回归测试

**Files:**
- Create: `tests/test_prd_gap_contract.py`
- Modify: `scripts/validate_ui_demos.cjs`
- Modify: `README.md`

- [ ] **Step 1: 写失败测试，锁定 6 类缺口**

在 `tests/test_prd_gap_contract.py` 增加契约测试：全局筛选能序列化商品/分层/生命周期/渠道；商品 API 支持新增筛选与排序；导入预览字段包含 `inferred_type` 和 `match_status`；日度矩阵包含 `returning_buyer_ratio`、环比、缺失范围和来源批次。

- [ ] **Step 2: 扩充静态校验**

在 `scripts/validate_ui_demos.cjs` 断言七个正式页面包含 `data-right-rail`，`shell.js` 暴露共享筛选 API，商品页和数据中心均调用 `/api/settings`，状态渲染覆盖 `loading/no-data/insufficient-data/missing-fields/calculation-failed/source-unavailable/partial`。

- [ ] **Step 3: 验证测试先失败**

Run: `py -3 -m unittest tests.test_prd_gap_contract -v`

Run: `node scripts/validate_ui_demos.cjs`

Expected: 因新增契约尚未实现而失败；不得出现导入错误或测试自身语法错误。

- [ ] **Step 4: 修正 README 完成状态**

将“已完成”拆为“已验证完成”和“待收口”，逐条列出本规划 6 类缺口，删除“148 项测试等于全部 PRD 完成”的暗示。

- [ ] **Step 5: Commit**

`git commit -m "test: lock remaining TM 1.0 PRD gaps"`

## Task 2: 完成共享筛选与下钻继承

**Files:**
- Modify: `frontend/ui_demo/assets/shell.js`
- Modify: `frontend/ui_demo/assets/shell.css`
- Modify: `frontend/ui_demo/assets/products-live.js`
- Modify: `frontend/ui_demo/assets/promotion-live.js`
- Modify: `frontend/ui_demo/assets/lifecycle-live.js`
- Modify: `frontend/ui_demo/assets/goals-live.js`
- Modify: `frontend/ui_demo/assets/overview-live.js`
- Test: `tests/test_prd_gap_contract.py`
- Test: `scripts/validate_ui_demos.cjs`

- [ ] **Step 1: 定义共享状态契约**

在 `shell.js` 的现有 `TmallDateRange` 旁新增 `window.TmallFilters`，固定字段为 `startDate`、`endDate`、`productId`、`tier`、`lifecycleStage`、`promotionChannel`、`compareMode`。状态从 URL 查询参数恢复，变更后写回 URL，并派发 `tmall:filters-change`。

- [ ] **Step 2: 默认日期使用数据库锚点**

继续使用 `/api/periods?dim=daily` 的最新日期作为 `anchorDate`；仅在接口没有可用日期时回退浏览器当天。为这一优先级增加静态断言和浏览器级验证。

- [ ] **Step 3: 渲染共享筛选控件**

在顶栏增加商品、分层、生命周期、推广渠道控件；选项来自现有 `/api/products` facets、`/api/lifecycle/assessments` 和 `/api/promotion` 返回的数据，不写死业务值。

- [ ] **Step 4: 页面消费统一筛选**

商品、推广、生命周期、总览请求继承支持的查询参数；下钻链接调用 `TmallFilters.toQuery()`。目标页遇到不支持的 `lifecycleStage` 或 `promotionChannel` 时移除参数，并通过共享 toast 明确提示被移除的条件。

- [ ] **Step 5: 验证**

Run: `py -3 -m unittest tests.test_prd_gap_contract -v`

Run: `node --check frontend/ui_demo/assets/shell.js`

Run: `node scripts/validate_ui_demos.cjs`

Expected: 共享筛选序列化、数据库日期锚点、下钻继承和不支持筛选提示全部通过。

- [ ] **Step 6: Commit**

`git commit -m "feat: share filters across dashboard pages"`

## Task 3: 补齐商品经营规格

**Files:**
- Modify: `api/data_api.py` (`get_products` 现有入口，不新建重复 blueprint)
- Modify: `frontend/ui_demo/pages/products.html`
- Modify: `frontend/ui_demo/assets/products-live.js`
- Modify: `frontend/ui_demo/assets/components.css`
- Create: `tests/test_products_prd.py`
- Modify: `scripts/validate_ui_demos.cjs`

- [ ] **Step 1: 写商品 API 失败测试**

覆盖 `lifecycle_stage`、`seasonality`、`has_pending_action` 筛选；覆盖 `net_sales`、`expense_ratio`、`payment_amount_change` 排序；断言分页总数与相同 WHERE 条件一致，未知排序字段回退安全白名单。

- [ ] **Step 2: 扩展现有商品查询**

在 `get_products()` 的主查询和 count 查询中加入生命周期评估及未完成动作的 `EXISTS` 条件；新增 `expense_ratio` 和趋势变化的可排序派生列。比率继续 `sum_then_derive`，不得平均每日比率。

- [ ] **Step 3: 增加筛选和正式模板**

商品页增加生命周期、季节属性、待办筛选；模板固定包含 `operate/select/paid/refund/lifecycle`，其中退款售后和生命周期必须展示真实字段，不可用字段展示 availability 原因。

- [ ] **Step 4: 支持列顺序调整**

列设置对话框提供上移/下移按钮，移动的是 `visibleColumns` 中的真实顺序；表头和行按同一数组渲染，移动后不得丢字段。

- [ ] **Step 5: 导出全部筛选结果**

新增商品页专用导出流程：按当前筛选重复请求 `/api/products`，使用服务端总数分页拉取全部结果，导出当前列顺序。不得继续依赖 `shell.js` 的“仅可见 DOM 表格”导出。

- [ ] **Step 6: 验证**

Run: `py -3 -m unittest tests.test_products_prd -v`

Run: `node --check frontend/ui_demo/assets/products-live.js`

Run: `node scripts/validate_ui_demos.cjs`

Expected: 新筛选、排序、列顺序、五个模板和全量筛选导出契约通过。

- [ ] **Step 7: Commit**

`git commit -m "feat: complete product operations workspace"`

## Task 4: 让设置模板真正驱动业务页面

**Files:**
- Modify: `services/settings_service.py`
- Modify: `api/settings_api.py`
- Modify: `frontend/ui_demo/pages/settings.html`
- Modify: `frontend/ui_demo/assets/settings-live.js`
- Modify: `frontend/ui_demo/assets/products-live.js`
- Modify: `frontend/ui_demo/assets/data-center-live.js`
- Modify: `tests/test_settings_api.py`
- Create: `tests/test_template_integration.py`

- [ ] **Step 1: 写模板校验与集成失败测试**

覆盖映射模板按 `source_type` 保存/读取，商品模板列必须来自白名单，默认模板必须存在，非法列和非法来源返回 422；静态测试断言商品页和导入页在初始化时调用 `/api/settings`。

- [ ] **Step 2: 收紧服务端 schema**

`mapping_templates` 使用 `{source_type: {standard_key: source_column}}`；`view_templates` 使用 `{template_key: {label, columns}}`。服务层验证来源、标准字段、列键、非空名称和默认模板引用。

- [ ] **Step 3: 替换 JSON 文本框**

设置页改为模板列表、名称输入、来源选择、字段映射行、商品列多选和删除/设为默认命令；JSON 仅作为 API 传输格式，不让用户直接编辑。

- [ ] **Step 4: 商品页应用服务端模板**

初始化先加载 `/api/settings`，合并内置五模板和用户模板；服务端默认优先于 `localStorage`，本地仅缓存当前会话未保存改动。保存后重新加载可恢复列集合与顺序。

- [ ] **Step 5: 数据中心应用来源映射**

选择来源或完成预览时应用对应 `mapping_templates[source_type]`；模板字段与文件列不匹配时保留自动识别结果，并明确提示未应用项，不得静默覆盖。

- [ ] **Step 6: 验证**

Run: `py -3 -m unittest tests.test_settings_api tests.test_template_integration -v`

Run: `node --check frontend/ui_demo/assets/settings-live.js`

Run: `node --check frontend/ui_demo/assets/products-live.js`

Run: `node --check frontend/ui_demo/assets/data-center-live.js`

Expected: 模板可视化管理、服务端校验、跨刷新恢复和两业务页消费全部通过。

- [ ] **Step 7: Commit**

`git commit -m "feat: connect saved templates to import and products"`

## Task 5: 完成数据中心字段识别与结果报告

**Files:**
- Modify: `services/import_service.py`
- Modify: `api/imports_api.py`
- Modify: `frontend/ui_demo/pages/data-center.html`
- Modify: `frontend/ui_demo/assets/data-center-live.js`
- Modify: `tests/test_import_workflow.py`
- Modify: `scripts/validate_ui_demos.cjs`

- [ ] **Step 1: 写导入预览失败测试**

断言每个字段返回 `source_column`、`standard_key`、`sample_value`、`inferred_type`、`match_status`；`match_status` 只允许 `exact/alias/template/manual/unmatched`。确认结果必须返回质量摘要和可定位的异常行。

- [ ] **Step 2: 推断字段类型和匹配来源**

依据 pandas dtype 与非空样例推断 `date/integer/decimal/text/empty`；区分标准键精确匹配、别名匹配、保存模板匹配和未匹配。用户手工修改后前端标记为 `manual`。

- [ ] **Step 3: 扩展预览表与异常明细**

字段表改为“源列、类型、标准字段、匹配状态、样例”；质量区展示所有异常的总数，明细支持展开前 25 条，不再只把前三条塞进 title，也不再显示英文错误文案。

- [ ] **Step 4: 提供最终结果报告**

导入成功后展示批次 ID、来源、文件 hash 摘要、新增/更新/跳过、日期范围、质量结论；失败保持事务回滚并显示结构化错误。

- [ ] **Step 5: 验证**

Run: `py -3 -m unittest tests.test_import_workflow -v`

Run: `node --check frontend/ui_demo/assets/data-center-live.js`

Run: `node scripts/validate_ui_demos.cjs`

Expected: 字段类型、五类匹配状态、模板应用、异常明细和最终报告通过。

- [ ] **Step 6: Commit**

`git commit -m "feat: disclose import field matching and quality results"`

## Task 6: 补齐总览日度矩阵

**Files:**
- Modify: `repos/metrics_repo.py`
- Modify: `services/metrics_service.py`
- Modify: `api/overview_api.py`
- Modify: `frontend/ui_demo/pages/overview.html`
- Modify: `frontend/ui_demo/assets/overview-live.js`
- Modify: `tests/test_api_contract.py`
- Modify: `tests/test_closed_loop_e2e.py`

- [ ] **Step 1: 写精确结果失败测试**

使用固定 fixture 断言老客占比为 `sum(returning_payment_buyers) / sum(payment_buyers)`，每日环比基于前一个有数据日，缺失范围返回具体日期段，来源包含 `source_batch_id`；无分母时返回 `None` 和原因。

- [ ] **Step 2: 扩展 repository 查询**

店铺日事实优先，返回 `returning_payment_buyers`、`source_batch_id` 和数据覆盖日期；商品回退不得把商品级买家相加伪造成店铺老客。没有店铺级新老客数据时标记 `missing-fields`。

- [ ] **Step 3: 生成矩阵状态和环比**

逐日生成 payment、net sales、refund、expense、conversion、AOV、returning ratio，并附每项 availability、前日环比、缺失日期范围和来源批次链接信息。

- [ ] **Step 4: 完成矩阵交互**

增加老客占比列、文字加图标的环比、缺失范围提示、来源批次详情入口；总览专用导出按当前共享筛选请求完整矩阵，不依赖当前 DOM 可见行。

- [ ] **Step 5: 验证**

Run: `py -3 -m unittest tests.test_api_contract tests.test_closed_loop_e2e -v`

Run: `node --check frontend/ui_demo/assets/overview-live.js`

Expected: 固定数值、缺失范围、来源批次、环比和完整导出契约通过。

- [ ] **Step 6: Commit**

`git commit -m "feat: complete overview daily matrix contract"`

## Task 7: 统一页面骨架与状态契约

**Files:**
- Modify: `api/api_response.py`
- Modify: `frontend/ui_demo/assets/api.js`
- Modify: `frontend/ui_demo/assets/shell.js`
- Modify: `frontend/ui_demo/assets/components.css`
- Modify: `frontend/ui_demo/pages/overview.html`
- Modify: `frontend/ui_demo/pages/products.html`
- Modify: `frontend/ui_demo/pages/promotion.html`
- Modify: `frontend/ui_demo/pages/lifecycle.html`
- Modify: `frontend/ui_demo/pages/reviews.html`
- Modify: `frontend/ui_demo/pages/data-center.html`
- Modify: `frontend/ui_demo/pages/settings.html`
- Modify: `tests/test_api_contract.py`
- Modify: `scripts/validate_ui_demos.cjs`

- [ ] **Step 1: 固定七状态枚举**

统一为 `loading`、`no-data`、`insufficient-data`、`missing-fields`、`calculation-failed`、`source-unavailable`、`partial`；成功有数据不使用状态占位。API 对未知 availability 值拒绝或归一为 `calculation-failed`。

- [ ] **Step 2: 建立共享状态渲染器**

在 `api.js` 暴露 `renderDataState(container, state, details)`，所有正式页用同一 DOM 结构、中文文案、重试按钮和 `aria-live`；删除页面各自的普通空态/加载失败合并逻辑。

- [ ] **Step 3: 增加 right-rail 骨架**

七个页面主内容采用 `main-content + aside[data-right-rail]` 结构；无右侧内容时 `aside` 保留语义标识并隐藏，不制造空白栏。桌面宽度受 grid 约束，390px 下折叠到主内容之后。

- [ ] **Step 4: 验证状态和响应式**

Run: `py -3 -m unittest tests.test_api_contract -v`

Run: `node scripts/validate_ui_demos.cjs`

Run: `Get-ChildItem frontend/ui_demo/assets -Filter *.js | ForEach-Object { node --check $_.FullName }`

Expected: 七状态、七页 right-rail、焦点与 390px 无横向溢出全部通过；保留截图证据。

- [ ] **Step 5: Commit**

`git commit -m "feat: unify page states and right rail structure"`

## Task 8: 全量回归、发布说明与隔离回滚

**Files:**
- Modify: `README.md`
- Create: `docs/RELEASE_NOTES.md`
- Modify: `scripts/production_preflight.py`（仅在验证缺口需要时）

- [ ] **Step 1: 运行完整自动化门禁**

Run: `py -3 -m unittest discover -s tests -v`

Run: `Get-ChildItem frontend/ui_demo/assets -Filter *.js | ForEach-Object { node --check $_.FullName }`

Run: `node scripts/validate_ui_demos.cjs`

Run: `py -3 scripts/production_preflight.py`

Expected: 全部退出码为 0；测试总数不得低于基线 148，并包含本规划新增测试。

- [ ] **Step 2: 固定数据集验算**

用测试 fixture 精确核对净销售额、费比、ROI、老客占比、跨月周目标、导入撤销前后指标、锁定生命周期不被导入覆盖。结果写入发布说明，不以页面“看起来正常”替代数值断言。

- [ ] **Step 3: 隔离恢复演练**

复制 `data/dashboard.db` 到临时目录，在副本上先执行 `PRAGMA integrity_check` 验证原样恢复，再执行 `db.init_db()` 验证迁移后启动。禁止覆盖工作区正在使用的数据库；记录备份 SHA-256 和两个阶段结果。

- [ ] **Step 4: 桌面与移动冒烟**

逐页验证 1440x900 和 390x844：无横向溢出、文字不遮挡、筛选可操作、抽屉/对话框可关闭、状态可读、right-rail 正确折叠。保存 7 页关键截图。

- [ ] **Step 5: 更新发布状态**

只有对应自动化与视觉证据齐全的条款才能在 README 标记“已验证完成”；未覆盖项保留“待验证/待实施”，不得用测试总数概括 PRD 完成度。

- [ ] **Step 6: Commit**

`git commit -m "docs: publish verified TM 1.0 completion status"`

## 最终验收

- [ ] 6 类差距均有对应测试、实现和证据。
- [ ] 新增筛选下钻保持上下文，不支持的筛选被显式移除并提示。
- [ ] 商品模板与导入映射模板跨刷新生效，而不是只存储。
- [ ] 商品与矩阵导出包含全部当前筛选结果，而不是当前 DOM 页。
- [ ] 七类数据状态和 `right-rail` 覆盖七个正式页面。
- [ ] 当前用户改动和 `data/dashboard.db` 不被回滚演练覆盖。
- [ ] 1.1/1.2 候选没有混入 1.0 完成条件。
