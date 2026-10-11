# 前端架构迁移评估报告

**项目**：天猫电商数据分析仪表盘（`E:\www\tmall-dashboard`）
**评估范围**：`frontend/ui_demo/` 前端层及其与 Flask 后端、Electron 桌面端、pytest/Playwright 测试体系的耦合
**评估日期**：2026-10-10
**数据口径**：所有数字均为本次评估实测，命令与依据见附录 A。基线为 git `HEAD` = `8b87318`，同时单独标注工作区未提交的在途改动。

---

## 0. 摘要

这份报告的核心结论只有一句：**这个前端的问题不是"用了原生 JS"，而是"组件契约只有一半"——有 class 契约、有 token 契约、有静态检查，但缺交互型原语、缺作用域、缺类型、且契约检查本身存在覆盖盲区。这四个缺口里有三个可以不动技术栈就补上。**

按实测数据，全量重写（React/Vue）的代价是：约 **24,200 行手写 JS + 458.8 KB CSS + 21 个页面 + 754 处手写 `ui-*` 类名**的等价迁移，同时会让**当前唯一能拦住 UI 回归的 6 个 CI 浏览器门禁中的 4 个失效**，而收益中的大部分（类型安全、组件复用）可以用远低成本在渐进路线上拿到。

因此推荐 **方案 C：保留原生技术栈，补齐交互原语 + 收紧契约 + 引入 JSDoc 类型检查**，并在 **方案 C 无法阻止"CSS 级联事故"复发时**升级为 **方案 D：引入页面级 CSS 作用域 + Web Components**。**不建议方案 A/B 全量重写**，理由是投入产出比与不可逆点风险均不可接受。

同时必须指出：**评估期间发现工作区正在被并发修改**，`ui-components.js` 在我读取过程中从 512 行变为 613 行，`popover` 原语已被新增（详见 §1.6）。这意味着本报告的"现状"是移动靶，部分痛点在评估期内已开始被修复。

---

## 1. 现状量化（实测）

### 1.1 你提供的事实核对

| 你的描述 | 实测结果 | 判定 |
|---|---|---|
| 21 个静态 HTML 页面 | 21 个，`frontend/ui_demo/pages/*.html`，合计 355.5 KB | ✅ 正确 |
| 19 个手写 CSS，约 459 KB | 19 个，**458.8 KB**，3,643 个规则块 | ✅ 正确 |
| 59 个手写 JS，约 1.4 MB | 59 个，**1,423.5 KB**（1.39 MB），**24,200 行** | ✅ 正确 |
| `tokens.css` 292 行、182 个 token | **292 行**；自定义属性声明 **212 处**，唯一 token 名 **171 个**（含 3 个主题块内的重定义） | ⚠️ 行数正确；**"182 个 token"未复现**，实测 171 个唯一名 / 212 处声明 |
| `ui-components.js` 513 行 | **HEAD 为 512 行**；工作区已变为 **613 行** | ⚠️ HEAD 是 512 不是 513；工作区已漂移 |
| `TmallUI.*` 全仓库 22 处调用 | **正确**。排除组件演示页与注释行后，HEAD 为 **21 处**可执行业务调用点，工作区为 **22 处** | ✅ 正确（误差 1，且工作区恰好为 22） |
| 手写 `ui-*` 类名 61/38/31 处（product-detail/promotion/products） | 实测（`class="..."` 属性内）：**product-detail 94 / promotion 72 / products 54**；21 页合计 **754 处** | ❌ **数字明显偏低**，实际手写量是描述值的 1.5 倍以上 |
| 30 个 UI 审计脚本 | `scripts/*.cjs` **35 个**；其中 **22 个**依赖 Playwright | ⚠️ 数量为 35，非 30 |
| 100+ pytest 测试文件 | **96 个** `tests/*.py`，但含 **951 个 test 函数** | ⚠️ "100+" 指文件数不成立（96）；指用例数则远超 |
| `ui-components.js` 完全没有 popover/dropdown/tooltip/picker | **HEAD 上成立**；**工作区已新增 `popover`（含视口约束/翻转/点外关闭/Esc/焦点返回）** | ❌ **评估期间已失效**，见 §1.6 |
| `DESIGN_SYSTEM.md` 30 KB | 30.2 KB，654 行，11 个一级章节 | ✅ 正确 |
| 无构建步骤 | 页面直接由 `send_from_directory` 返回；`frontend-build/` 仅用于预构建 echarts/lucide 两个 vendor 包，不参与页面构建 | ✅ 正确 |

**需要修正的关键一条**：`DESIGN_SYSTEM.md` §11.1 第 1328 行声称"历史页面中的 `.button`、`.panel` 等 class 由 `TmallUI.upgradeLegacy()` 自动映射到 `ui-*` canonical class"。**实测 `upgradeLegacy` 在整个仓库（含 `frontend/`、`desktop/`、`scripts/`）出现 0 次**。该 API 不存在。相应的，`tests/test_ui_system_contract.py:146` 有一个名为 `test_runtime_upgrade_shim_is_removed_and_audit_is_canonical` 的测试，断言 `ui-components.js` 中**不含** `legacyMap`、`new MutationObserver`——即"升级 shim 已被移除"是**有意为之**并被测试锁定。**结论：规范文档 §11.1 的这一句是过时残留，会误导新人以为存在自动迁移兜底。这是文档债务，不是代码缺陷。**

### 1.2 代码规模

**手写 JS（59 个文件 / 24,200 行 / 1,423.5 KB）**——已排除 4 个 vendor 包（`echarts-5.5.1.min.js` 1006.7 KB、`echarts-custom.min.js` 620.0 KB、`lucide-1.8.0.min.js` 388.1 KB、`lucide-custom.min.js` 14.4 KB，合计 2,029.3 KB）。

TOP 10 手写 JS：

| 文件 | 行数 | KB |
|---|---:|---:|
| `period-review-live.js` | 3,478 | 202.9 |
| `product-detail-dialog.js` | 1,422 | 86.8 |
| `promotion-live.js` | 1,404 | 83.3 |
| `shell.js` | 1,131 | 75.7 |
| `product-detail-live.js` | 923 | 66.2 |
| `market-ranking-live.js` | 1,083 | 62.3 |
| `lifecycle-live.js` | 851 | 55.6 |
| `settings-live.js` | 562 | 46.2 |
| `overview-live.js` | 786 | 45.6 |
| `products-live.js` | 752 | 43.1 |

单文件最大 `period-review-live.js` 3,478 行，是最小文件（`version.js` 7 行）的 497 倍。**前 3 个文件占手写 JS 总量的 26.1%**，说明复杂度高度集中，这对迁移是好消息（见 §3）。

**CSS（19 个文件 / 458.8 KB / 3,643 个规则块）**：

| 文件 | 规则块 | KB | 行数 |
|---|---:|---:|---:|
| `components.css` | 912 | 122.2 | 1,552 |
| `period-review.css` | 537 | 69.8 | 2,431 |
| `themes/product-domain.css` | 527 | 64.1 | 1,326 |
| `shell.css` | 367 | 45.8 | 596 |
| `themes/overview-domain.css` | 246 | 30.0 | 346 |
| 其余 14 个 | 1,054 | 127.1 | — |

`!important` 共 **183 处**。这是一个可量化的级联健康度指标：183 处说明存在约 183 个"必须靠提高优先级才能生效"的对抗点。

### 1.3 页面规模分布

单看 HTML 会严重低估复杂度——`core-product-analysis.html` 只有 570 行却占 64 KB（最长单行 1,524 字符），说明是高度压缩的单行标记。按**"HTML + 页面专属 CSS + 页面专属 JS"**总字节排名：

| 排名 | 页面 | HTML KB | 专属 CSS KB | 专属 JS KB | 合计 KB | 关联文件数 |
|---:|---|---:|---:|---:|---:|---:|
| 1 | **period-review** | 10.3 | 69.8 | 314.7 | **394.8** | 9 |
| 2 | **product-detail** | 33.2 | 0 | 153.0 | **186.2** | 2 |
| 3 | **promotion** | 22.6 | 26.3 | 113.3 | **162.2** | 5 |
| 4 | products | 19.6 | 0 | 115.8 | 135.4 | 7 |
| 5 | market-ranking | 28.9 | 12.3 | 62.3 | 103.5 | 2 |
| 6 | overview | 20.0 | 30.0 | 45.6 | 95.6 | 2 |
| 7 | lifecycle | 13.8 | 13.9 | 55.6 | 83.3 | 2 |
| 8 | settings | 18.2 | 17.0 | 46.2 | 81.4 | 3 |
| 9 | core-product-analysis | 64.0 | 0 | 1.7 | 65.7 | 1 |

**最大最复杂的 3 个页面：`period-review`（394.8 KB，9 个文件）、`product-detail`（186.2 KB）、`promotion`（162.2 KB）。**

三者合计 **743.2 KB，占全部页面专属资源的 39.4%**。其中 `period-review` 一个页面就是第二名的 2.1 倍，且它是唯一拥有独立子目录 `assets/pages/period-review/`（8 个模块）的页面——说明它是唯一已经开始做"按职责拆分"的页面，也是唯一有 17 个 `<script>` 标签的页面。

### 1.4 组件层采用率（这是最关键的量化）

**口径说明**：`TmallUI.` 字符串在 `frontend/ui_demo/` 下共出现 **39 处**，但其中混有组件演示页和注释。按"**可执行业务调用点**"（排除 `component-catalog.html`、排除 `//` 注释行）统计：

| 被调用 API | HEAD `8b87318` | 当前工作区 |
|---|---:|---:|
| `detailDrawer` | 12 | 12 |
| `fieldSelector` | 6 | 6 |
| `formatDateTime` | 1 | 1 |
| `icon` | 1 | 1 |
| `renderDataState` | 1 | 1 |
| `popover` | — | **1** |
| **可执行调用点合计** | **21** | **22** |

另有 `component-catalog.html` 内 **14 处**演示调用（`button`/`confirm`/`dataState`/`modal`/`fieldSelector`），以及 2 行 `shell.js:632`、`date-range-store.js:369` 的说明性注释。

**→ 你给出的"全仓库只有 22 处调用"是准确的**，实测工作区恰好 22 处、HEAD 21 处。

而 `ui-components.js` 导出的 API 面：**HEAD 为 29 个**，工作区新增 `popover` 后为 **30 个**（`text, create, clear, escape, formatDateTime, format, status, renderDataState, icon, button, badge, emptyState, dataState, metricCard, metricGrid, panel, pageHeader, filterToolbar, table, setState, contextBar, tableToolbar, detailDrawer, stickyActionBar, modal, confirm, enableLightDismiss, fieldSelector, audit`，工作区 + `popover`）。

**采用率结论（这是本报告最重要的一个数字）：**

- **被使用的 API（含演示页）：9 / 29 = 31.0%（HEAD）；10 / 30 = 33.3%（工作区）**
- **仅计业务代码实际调用的：6 / 29 = 20.7%（HEAD）**
- **完全零调用的 API：约 20 个**，其中包括最基础的 `panel`、`metricCard`、`metricGrid`、`table`、`badge`、`pageHeader`、`filterToolbar`、`contextBar`、`tableToolbar`、`emptyState`、`stickyActionBar`、`setState`、`format`
- 而与此同时，页面 HTML 里**手写 `ui-*` 类名 754 处**（仅 `class="..."` 属性内），其中 `product-detail` 单页 94 处

**你描述的"集中在 `detailDrawer` 和 `fieldSelector`"完全正确**：这两个 API 占了 22 处调用点中的 **18 处（81.8%）**。`detailDrawer` 12 处 + `fieldSelector` 6 处 = 18 处，其余 5 个 API 各只有 1 处。

**这组数字定义了问题的真实性质**：不是"组件库没写"，而是"**组件库写了但页面选择手写类名**"。`TmallUI.panel()` 存在，但 21 个页面里手写 `.ui-panel` 标记；`TmallUI.metricCard()` 存在，但 `overview.html` 手写 4 个 `.ui-metric-card` 按钮。`check_ui_contract.py` 会拦住**旧**类名（`.button`/`.panel`/`.metric-card`），但 `.ui-panel` 是**新**类名，完全合法——**契约门禁拦住了"用旧类名"，却没拦住"绕过工厂直接写新类名"**。

这是本报告认定的**头号架构问题**，也是方案选择的分水岭。

### 1.5 CSS 无作用域（已量化）

- 19 个 CSS 全部是全局级联，`components.css` 单文件 122.2 KB / 912 个规则块 / 1,552 行
- 全仓库 CSS 中 **distinct `.ui-*` 类 41 个**，`components.css` 内 **532 处 `.ui-*` 选择器**——即平均每个类被 13 个选择器覆盖，改一个类的风险面是 13 个选择器
- 页面通过 5–7 个 `<link>` 串行加载全局 CSS（`overview.html` 第 7–9 行一口气引了 7 个 CSS）
- 8 个页面还额外带 `<style>` 内联块（`analysis`、`data-center`、`data-collection`、`flow-source`、`market-ranking`、`product-detail`、`rival-analysis`），形成"全局 + 内联"双层覆盖

**这直接对应你说的痛点 3。** 事故机制已被在途脚本 `scripts/check_css_syntax.py` 的文档头精确复述：编辑时 `.demo-picker__backdrop { ... }` 覆盖掉了 `.demo-period__mode {` 这一行，后续声明体变成无选择器的孤立声明块，**浏览器从该点起连带吞掉后续规则**，包括 `.demo-picker__backdrop{position:fixed}`，于是弹窗以 `position:static` 渲染到文档流底部（top 2432px，视口 800px）。

关键点：**CSS 解析器对语法错误从不报错**。所以 console 干净、异常捕获为空、单测全绿，而页面表现是"点了没反应"。

### 1.6 评估期间发现的并发修改（重要）

评估过程中工作区正在被改动。`ui-components.js` 的 `LastWriteTime` 与我首次读取的时间差 **0.2 分钟**，行数从 512（HEAD）变为 613（工作区）。`git diff --stat HEAD` 显示：

```
frontend/ui_demo/assets/components.css             |   5 +
frontend/ui_demo/assets/overview-live.js           |   8 +-
frontend/ui_demo/assets/pages/period-review/product-columns.js | 30 +-
frontend/ui_demo/assets/period-review.css          |  34 +-
frontend/ui_demo/assets/runtime/date-range-store.js | 648 ++++++++++++++---
frontend/ui_demo/assets/shell.css                  | 237 +++++++-
frontend/ui_demo/assets/shell.js                   |  79 ++-
frontend/ui_demo/assets/ui-components.js           | 104 +++-
frontend/ui_demo/pages/period-review.html          |   4 +-
9 files changed, 1019 insertions(+), 130 deletions(-)
```

**在途改动已经在处理本报告的部分痛点：**

1. **`popover` 原语已新增**（`ui-components.js:333-434`，约 100 行）。它把定位、视口约束、空间不足自动翻转、左右/上下夹紧、点外关闭、Esc、焦点返回、resize/scroll 跟随、`aria-expanded` 管理、单浮层互斥全部收敛到一处。注释明确写着"真实事故：时间选择器浮层因一个 CSS 解析错误丢掉 position:fixed……把定位、视口约束、点外关闭、Esc、焦点返回、滚动跟随统一收在这里，页面不再各自实现，同类失效就不再可能"。
   → **这直接推翻了你描述的痛点 2（"完全没有 popover"）。在 HEAD 上该描述成立，在当前工作区已不成立。**

   **进一步：`popover` 已经落地了真实调用点。** 评估过程中 `runtime/date-range-store.js:373` 出现了 `pickerPopover = global.TmallUI.popover({...})`，把时间选择器浮层改走统一原语。**这恰好命中了本报告在阶段 0 提出的风险条件**——我原本担心 `popover` 会重演 `decisionCard`"建了但无人调用"的覆辙，实测团队已经把它接到了真实消费方。这是很强的正面信号。

2. **`scripts/check_css_syntax.py` 已新增**（149 行，未跟踪）。静态 CSS 结构门禁：剥离注释与字符串后校验花括号配对、禁止负深度、禁止深度 0 处的孤立声明块、校验注释与字符串闭合。**我实测运行通过（19 个 CSS 文件全部 OK，exit 0）。**

3. **`scripts/smoke_date_picker.cjs` 已新增**（235 行，未跟踪）。零依赖 CDP 浏览器冒烟门禁，判据直接来自事故症状：弹窗必须出现、必须在视口内且中心点命中测试落在内部、`position` 不能是 `static`、粒度按钮高亮互斥、无未捕获异常。

4. **`scripts/smoke_popover.cjs` 也已出现**（217 行，未跟踪）。说明浮层冒烟门禁正在从"时间选择器专用"泛化为"通用浮层门禁"——这正是本报告阶段 0 建议的第 3 项。

**评估结论：痛点 2 的"缺原语"和痛点 3 的"无法静态发现"已经在被修复，且方向与本报告推荐方案 C 完全一致。** 这既是好消息（证明渐进路线可行且团队已在走），也意味着本报告的基准线应明确锚定在 **HEAD `8b87318`**，并把这 4 项在途改动视为"方案 C 的第 0 阶段已完成约 80%"。

**唯一遗留的缺口**：`popover` 目前只有 **1 个**消费页面（`date-range-store.js`）。按仓库自定标准"新组件必须 ≥2 页复用才能进 `ui-components.js`"（`ui-components.js:240` 注释），以及 `decisionCard` 因"仅 1 处挂类名而未真正使用"被删除的先例，**建议再接入 ≥1 个真实消费方**，否则仍有被回滚的风险。

---

## 2. 候选方案对比

评估 5 个方案。所有工作量估算基于实测的 **24,200 行手写 JS + 458.8 KB CSS + 21 页面 + 754 处手写类名**，并按以下经验系数折算：

- 重写系数：**1.3–1.8×**（新框架需重新实现等价交互、状态、格式化、图表封装，且要重新踩一遍已踩过的坑）
- 人力基准：**1 人日 ≈ 150–250 行有效生产代码**（含自测、联调、修复回归）
- 审计脚本重建：每个 Playwright 脚本 **1.5–3 人日**（选择器、断言、等待策略全部要改）

---

### 方案 A：React 18 + Vite + Ant Design

**技术形态**：SPA 重写。React 18 + TypeScript + Vite + antd 5 + ECharts 5 + React Router。Flask 退化为纯 API 服务 + 一个 `index.html` 入口。

**迁移范围与工作量**：

| 工作项 | 规模 | 人日 |
|---|---|---:|
| 21 个页面组件化重写 | 等价于 24,200 行 JS + 355.5 KB HTML | 95–130 |
| 458.8 KB CSS → antd token 映射 | 3,643 规则块；其中 41 个 `.ui-*` 类需映射到 antd 组件 | 25–40 |
| 59 个 IIFE 模块 → ESM | 全局 `TmallUI`/`TmallRuntime`/`DemoApi` 需重设计为 hooks/context | 30–45 |
| 图表封装重写（`charts.js` + echarts-custom） | ECharts 封装 + 自定义 bundle 需重接 | 8–12 |
| `field-selector` / `detailDrawer` 等 9 个在用组件 | 已用 API 需 1:1 行为对齐（含焦点圈闭、滚动锁计数） | 10–15 |
| 35 个 cjs 审计脚本重建 | 22 个 Playwright 脚本选择器全改 | 35–65 |
| 11 个 UI 相关 pytest 文件改写 | 见下 | 15–25 |
| Electron 桌面端适配 | `desktop/src/main.ts:55` 用 `loadURL(url)`，改 SPA 后路由/深链/`/products/<id>` 需重做 | 5–8 |
| **合计** | | **223–340 人日** |

**对 30 个审计脚本、100+ 测试的影响（这是最被低估的代价）**：

实测的耦合面比"审计脚本要改"更严重：

- **CI 直接执行 6 个 cjs**（`.github/workflows/quality-gate.yml`）：`smoke_core_pages.cjs`、`browser_prd_gates.cjs`（跑两遍，含 `TMALL_CAPABILITY_ONLY=1`）、`audit_core_interactions.cjs`、`audit_ui_contrast.cjs --states`、`validate_ui_demos.cjs`
- **其中 4 个依赖真实 DOM 结构**：`smoke_core_pages`、`browser_prd_gates`、`audit_core_interactions`、`audit_ui_contrast`。React 渲染后 DOM 层级、class 名、`data-*` 属性全部改变，**这 4 个门禁在迁移期间会持续红**，而它们恰恰是当前唯一能拦住 UI 回归的防线
- **`audit_ui_contrast.cjs --states` 是最难的一个**：它遍历 7 种数据状态做 WCAG 对比度检查，依赖 `data-state` 属性约定。React 下这套约定需要重新建立
- **`validate_ui_demos.cjs` 会直接失败**：它断言 9 个页面 HTML 含 `data-page="<name>"`、`../assets/api.js`、`../assets/shell.js`、无内联 SVG。SPA 下没有这些页面文件
- **`test_ui_system_contract.py`（30 个 test）几乎全废**：它 `read_text` 直接读 `assets/*.css`、`assets/*.js`、`pages/*.html` 的**源码文本**做断言（例如断言 `components.css` 含 `.ui-panel__title`、断言 `ui-components.js` 含 `const legacyNames`）。源码一旦变成 TSX + 构建产物，**30 个测试需要重写而非修改**
- **`test_frontend_prd_contract.py`（96 个 test，1,178 行）风险最高**：它同时引用 `ui_demo` 和 `.cjs`，是最大的单个测试文件
- 其余 `test_category_mode.py`(22)、`test_products_prd.py`(13)、`test_navigation_contract.py`(8)、`test_update_notifications_ui.py`(7)、`test_desktop_packaging_contract.py`(5)、`test_overview_kpi_ui.py`(1)、`test_settings_scan_ui.py`(1) 也读 `ui_demo` 源码

**合计 11 个 pytest 文件（约 194 个 test 函数）与 UI 源码文本强耦合。**

**双轨并行期风险**：

1. **两套 UI 必须同时对同一批 API 正确**。后端有 951 个 test 函数，但前端 UI 契约测试无法同时服务两套渲染
2. **`/products/<product_id>`、`/product-detail`、`/pages/<path>` 三条路由被桌面端深链依赖**（`app.py:348-360`）。SPA 迁移期间这两套路由必须并存，`LEGACY_REDIRECT_PAGES` 与 `APPLICATION_PAGES`（`services/application_pages.py`）需要双份维护
3. **`shell.js` 的自动加载机制会成为双轨毒药**。实测 `shell.js:95-107` 会在运行时按 `document.body.dataset.page` 动态注入 `{page}-live.js`（8 个页面的映射表写死在 `liveAdapters`），并动态加载 `table-controls.js`、`ui-components.js`、`version-check.js`、`desktop-integration.js`。SPA 下这套机制与路由懒加载直接冲突，**且它是隐式的——不看 `shell.js` 根本不知道页面加载了什么**
4. **版本号漂移**：`ui-components.js` 同时被页面 HTML 和 `shell.js` 加载，注释明确要求"版本号需保持一致"（`shell.js:96`）。双轨期间这是高频冲突点

**不可逆点**：**引入 Vite 构建产物并由 Flask 返回 `dist/index.html` 的那一刻**。此后：
- 不再有"改一行 HTML 刷新即见"的能力，必须有构建步骤
- 21 个页面的源码文本从仓库消失，`test_ui_system_contract.py` 的 30 个源码断言同时失效
- 回滚需要同时回滚构建配置、产物、后端路由、CI —— 实际上等于二次迁移

**代价总结**：223–340 人日；4 个 CI 浏览器门禁在数月内失效；194 个 test 函数需重写；引入 Node 构建链到当前纯 Python + 预构建 vendor 的工程（`frontend-build/` 只产出 2 个 vendor bundle，且**未被任何脚本或 CI 调用**——实测 `esbuild`/`frontend-build` 在 `scripts/`、`packaging/`、`.github/` 中零引用）。**换来的收益中，类型安全和组件复用可以用方案 C 以 1/5 成本拿到。**

---

### 方案 B：Vue 3 + Element Plus

**技术形态**：SPA 重写。Vue 3 + TS + Vite + Element Plus + ECharts。**关键优势**：Vue 的 SFC `<style scoped>` 原生解决 CSS 作用域问题（痛点 3），且模板语法与现有 HTML 更接近，迁移心智负担低于 React/JSX。

**迁移范围与工作量**：与方案 A 同量级，**210–320 人日**。略低的原因：
- 模板语法接近现有 HTML，21 个页面的标记可直接搬进 `<template>`，省 10–15 人日
- `<style scoped>` 让 458.8 KB 全局 CSS 可以按页面切分而不必重写为 antd token，省 8–15 人日
- Element Plus 的 `el-table`/`el-dialog`/`el-popover` 覆盖面与现有需求匹配度略高于 antd（现有 `modal` 用的是原生 `<dialog>`，Element Plus 是 div 方案，反而需重做焦点圈闭逻辑，此项 +3 人日）

**对审计脚本与测试的影响**：与方案 A **完全相同**——6 个 CI cjs、194 个 test 函数的耦合不因框架选择而改变。这是重要认知：**这部分代价是"离开静态 HTML"造成的，不是"选错框架"造成的。**

**双轨并行期风险**：与方案 A 相同，另加一条：
- **`<style scoped>` 与现有 183 处 `!important` 冲突**。scoped 只加属性选择器提升特异性，但现有 CSS 里的 `!important` 仍会穿透 scoped 边界。迁移期间"Vue 组件内的 scoped 样式被旧的全局 `!important` 覆盖"会成为高频、难定位的问题

**不可逆点**：与方案 A 相同——**构建产物接管 `dist/index.html` 之时**。

**代价总结**：与 A 同质，仅框架红利差异（scoped 样式、模板亲和度）。**但同样付出了 4 个 CI 门禁失效 + 194 个 test 重写的代价，而这两个代价恰恰不是当前痛点所要求的。**

---

### 方案 C：保留原生技术栈，补齐交互原语 + 收紧契约 + JSDoc 类型检查 ⭐ **推荐**

**技术形态**：不引入框架，不引入构建步骤（或仅引入 `tsc --checkJs` 作为纯检查步骤，不产出运行时代码）。三项工作：

1. **补齐交互型原语**（popover/dropdown/tooltip/picker 统一到 `TmallUI`）
2. **收紧契约门禁**（堵住"绕过工厂手写 `ui-*` 类名"这条路）
3. **引入 JSDoc + `// @ts-check` 类型检查**（拿类型安全，不付构建代价）

**迁移范围与工作量**：

| 工作项 | 规模 | 人日 |
|---|---|---:|
| 交互原语：`popover` 已做（在途）；补 `dropdown`/`tooltip`/`picker` | 基于已有 `popover` 组合，每个 80–150 行 | 4–7 |
| 把 754 处手写 `ui-*` 类名收敛到工厂调用 | 按页面推进，21 页 | 30–50 |
| 契约门禁扩展：禁止新增手写 `ui-*` 组合类、要求交互元素走工厂 | `check_ui_contract.py` 扩展 | 3–5 |
| CSS 结构门禁纳入 CI | `check_css_syntax.py` 已写（在途），接线即可 | 0.5 |
| 浏览器可见性门禁纳入 CI | `smoke_date_picker.cjs` + `smoke_popover.cjs` 已写（在途），泛化为通用浮层门禁 | 2–3 |
| JSDoc 类型标注：24,200 行 JS 加 `@ts-check` | 分文件推进，优先 `ui-components.js`/`api.js`/`runtime/*` | 25–45 |
| `tsconfig.json` + `checkJs` 接线 CI | 纯检查，无产物 | 1–2 |
| 修复契约盲区（见下） | 6 个 theme CSS + 21 个子目录 JS 未被扫描 | 1–2 |
| **合计** | | **66–115 人日** |

**估算依据**：单页面类名收敛按每页 30–50 处手写类名、每处 5–10 分钟（含验证渲染无回归）计；JSDoc 按每 300–500 行/人日计（只标公共边界与状态对象，不追求全覆盖）。

**对 30 个审计脚本、100+ 测试的影响**：**几乎为零，这是本方案的核心优势。**

- 6 个 CI cjs **全部继续有效**，且新增 2 个门禁（CSS 结构 + 浮层可见性）后变强
- `validate_ui_demos.cjs` 断言的 `data-page`、`../assets/api.js`、`../assets/shell.js` 全部不变
- `audit_ui_contrast.cjs --states` 依赖的 `data-state` 约定不变
- `test_ui_system_contract.py` 的 30 个源码断言继续成立（但需**修正其中 1 个**，见风险清单）
- 194 个 UI 相关 test 函数**零重写**

**双轨并行期风险**：本方案**没有双轨期**——这是它相对 A/B 最大的结构优势。页面始终可运行，改造是逐页、可单独回滚的。

但仍有两个真实风险：
1. **类名收敛期间"新旧混用"**：一个页面里既有 `TmallUI.panel()` 生成的节点，又有手写 `.ui-panel`。若工厂输出的 DOM 结构与手写结构不完全一致，CSS 选择器会命中不同层级导致样式错位。**缓解**：每页收敛后立即跑 `audit_ui_contrast.cjs` + 截图对比
2. **JSDoc 是渐进式约束，不是强制的**：`// @ts-check` 只对加了注释的文件生效，未加的文件不受约束。**缓解**：在 CI 中对已标注文件清单做"只增不减"断言

**不可逆点**：**本方案没有不可逆点。** 每一页、每个文件都可以独立回滚。这是它最重要的性质——它保留了"改一行刷新即见"的能力，也保留了将来转向方案 A/B/D 的**全部选项**。

**代价总结**（必须说清）：
- **拿不到真正的类型安全**：JSDoc + `checkJs` 能查出参数类型错误、属性名拼写错误、`null` 未检查，但**查不出 React/Vue 生态那种组件 props 契约错误**，因为这里没有组件类型系统
- **CSS 无作用域问题只是被"监控"而非被"解决"**：`check_css_syntax.py` 能拦住孤立声明块这类**语法**错误，但拦不住"一个合法选择器意外命中了别的页面元素"这类**语义**级联错误。183 处 `!important` 依然存在
- **组件采用率需要人工推进**：754 处手写类名不会自己消失，靠契约门禁 + 逐页收敛，需要持续投入
- **不解决 24,200 行 JS 的模块化问题**：IIFE + 全局对象的结构保持不变，`shell.js` 的隐式动态加载机制继续存在

---

### 方案 D：页面级 CSS 作用域 + Web Components

**技术形态**：把 `TmallUI` 从"JS 工厂函数 + 全局 class"升级为 **Custom Elements**（`<tm-panel>`、`<tm-metric-card>`、`<tm-drawer>`），配合 Shadow DOM 或 `@scope` 实现真正的样式隔离。仍无框架、无构建（或仅用 esbuild 打包，已有 `frontend-build/` 基础设施）。

**迁移范围与工作量**：

| 工作项 | 规模 | 人日 |
|---|---|---:|
| 41 个 `.ui-*` 类 → Custom Elements（含 Shadow DOM 样式） | 已有工厂函数可复用逻辑 | 35–55 |
| 458.8 KB 全局 CSS 按组件切分 | 3,643 规则块需归类：哪些进 Shadow DOM、哪些留全局 | 20–35 |
| 754 处手写类名 → 自定义元素标签 | 比方案 C 的改造成本更高（标签结构变化，不只是调用方式） | 40–65 |
| 主题系统适配（`data-theme="dark"` 需穿透 Shadow DOM） | CSS 自定义属性可穿透，但 `:root[data-theme]` 选择器不能 | 6–10 |
| Lucide 图标在 Shadow DOM 内的 `createIcons()` 扫描 | `ui-components.js:94-106` 已有 `iconScanQueued` 排队逻辑，需重做 | 3–5 |
| 35 个 cjs 审计脚本适配 | 选择器从 `.ui-panel` 变为 `tm-panel`，`shadowRoot` 查询需 `>>>` 或 `evaluate` | 20–40 |
| 11 个 pytest 文件适配 | `test_ui_system_contract.py` 断言 `components.css` 含 `.ui-panel__title` → 失效 | 10–18 |
| **合计** | | **134–228 人日** |

**对审计脚本与测试的影响**：**比方案 A/B 轻，但比方案 C 重得多。**
- `audit_ui_contrast.cjs` **会被 Shadow DOM 直接击穿**：它遍历页面元素计算对比度，Playwright 的常规选择器无法穿透 `shadowRoot`。需改用 `page.evaluate` 递归遍历，或强制所有组件用 `open` 模式
- `test_ui_system_contract.py` 中大量"断言 CSS 文件含某个 `.ui-*` 选择器"的测试（如 `test_title_width_and_truncation_contract` 断言 `components.css` 含 `.ui-panel__title`、`.ui-metric-card__label`）需全部重写
- `validate_ui_demos.cjs` 的 `assert(!/<svg\b/i.test(html))` 类断言需重新审视

**双轨并行期风险**：
1. **Shadow DOM 的样式隔离是"一刀切"**：切进去容易，但一旦某组件需要被页面主题或布局微调（现有 183 处 `!important` 说明这种需求真实存在），就会陷入"要么暴露 CSS 变量、要么放弃隔离"的两难
2. **`@scope` 的浏览器支持**：若走 `@scope` 而非 Shadow DOM，需确认 Electron 42.3.0 内嵌 Chromium 版本支持（Electron 42 对应 Chromium 约 13x，支持 `@scope`，但需实测）
3. **表单元素跨 Shadow 边界的可访问性与焦点管理**：现有 `detailDrawer` 已实现完整的 Tab 圈闭 + 焦点归还（`ui-components.js:285-330`），Shadow DOM 下 `document.activeElement` 语义变化，**这段逻辑需重做且极易引入回归**

**不可逆点**：**第一个 Custom Element 上线并被 ≥2 个页面使用之时。** 此后：类名契约（`check_ui_contract.py` 的 26 个 legacy 类名清单）与元素契约两套体系并存，回滚需要同时回滚 CSS、JS、审计脚本、pytest 断言。

**代价总结**：134–228 人日；`audit_ui_contrast.cjs` 需重写；Shadow DOM 与现有主题系统、焦点管理、图标扫描三处深度冲突。**它的收益（真正的样式隔离）确实解决痛点 3，但成本是方案 C 的 2 倍以上，且引入了新的不可逆点。**

---

### 方案 E：微前端 / 模块联邦（如 qiankun / single-spa）

**技术形态**：把 21 个页面按域拆成独立子应用（商品域、推广域、复盘域），主应用负责 shell、导航、日期范围。

**评估结论：不推荐，且不建议进入详细评估。** 理由基于实测数据：

- **微前端的收益前提是"多团队独立发布"**。实测这个前端是 **59 个手写 JS 文件、24,200 行、单仓库、单一 `shell.js` 统一加载**，`period-review-live.js` 3,478 行是最大单文件。这更像 1–2 人维护的单体，**不存在微前端要解决的团队自治问题**
- **会直接破坏现有唯一有效的共享机制**：`shell.js:107` 的 `liveAdapters` 映射表 + `data-page` 驱动的自动加载 + `TmallRuntime.subscribeDateRange` 日期范围订阅（`assets/runtime/date-range-store.js` 683 行，在途已扩展到 648 行改动）。微前端下这些跨应用共享状态需要重新设计为事件总线/全局 store，**是从"能跑"退到"要重新设计"**
- **`data-range-store.js` 是跨页面共享状态的核心**，在途改动 +648 行说明它正在快速演进。微前端会要求它变成跨应用契约，**在演进期做这件事风险极高**

**工作量**：不作精确估算（估了也不会有决策价值），但量级不低于方案 A。**代价远大于收益，明确排除。**

---

### 方案对比总表

| 维度 | A. React+Vite+antd | B. Vue3+ElementPlus | **C. 原生+原语+契约** ⭐ | D. Web Components | E. 微前端 |
|---|---|---|---|---|---|
| 工作量（人日） | 223–340 | 210–320 | **66–115** | 134–228 | >250 |
| 6 个 CI cjs 门禁 | 4 个失效 | 4 个失效 | **全部保留 + 新增 2 个** | 3 个需改 | 大部分失效 |
| 194 个 UI test 函数 | 全部重写 | 全部重写 | **0 重写** | ~40 个重写 | 大部分重写 |
| 双轨并行期 | 有（数月） | 有（数月） | **无** | 有 | 有（最复杂） |
| 不可逆点 | 构建产物接管 | 构建产物接管 | **无** | 首个 CE 上线 | 主应用接管 |
| 解决 CSS 作用域 | ✅（重写） | ✅（scoped） | ⚠️ 监控非解决 | ✅ | ⚠️ |
| 解决缺交互原语 | ✅ | ✅ | ✅ | ✅ | ✅ |
| 解决组件绕过 | ✅（强制） | ✅（强制） | ⚠️ 靠契约约束 | ✅ | ✅ |
| 解决无类型 | ✅ | ✅ | ⚠️ 部分（JSDoc） | ⚠️ 部分 | ✅ |
| 引入构建步骤 | 是 | 是 | **否**（仅 tsc 检查） | 可选 | 是 |
| 保留"改一行刷新即见" | ❌ | ❌ | ✅ | ✅ | ❌ |

---

## 3. 分阶段迁移路径（方案 C）

设计原则：**每阶段独立可交付、独立可回滚、每阶段结束时系统都比上一阶段更强**。不设"大爆炸"节点。

### 阶段 0：止血与接线（已完成约 80%，在途）

**范围**：把评估期间已写好的 4 个在途产物收口并接入 CI。

**产出**：
1. `ui-components.js` 的 `popover` 原语（已在途，613 行版本）合并入主干
2. `scripts/check_css_syntax.py`（149 行，已在途）接入 `.github/workflows/quality-gate.yml`
3. `scripts/smoke_date_picker.cjs`（235 行，已在途）与 `scripts/smoke_popover.cjs`（217 行，已在途）泛化为通用浮层门禁并接入 CI
4. `git diff` 中 `runtime/date-range-store.js`（+648 行）的改动收口

**验收标准**：
- `python scripts/check_css_syntax.py --strict` 在 19 个 CSS 上 exit 0（**我实测当前为 exit 0**）
- `node scripts/smoke_date_picker.cjs` 与 `node scripts/smoke_popover.cjs` 在 CI 的真实 Chromium 上通过
- `popover` 有 ≥2 个真实消费页面（**当前已有 1 个**：`runtime/date-range-store.js:373` 的时间选择器，已满足"有调用点"但未满足"≥2 页复用"）

**退出条件**：3 个门禁在 `quality-gate.yml` 的 "Run real Chromium browser gates" 步骤中稳定通过 ≥3 次连续提交。

**风险**：`popover` 定义了但消费方不足会重演 `decisionCard` 的覆辙。`ui-components.js:235-240` 有一段非常诚实的注释记录了先例：`ui-decision-card` 工厂"自建出来就没有任何调用点"，唯一"使用"是 `promotion.html` 挂了个类名但被 `promotion-views.css` 立刻覆盖掉，最终按仓库自定标准"新组件必须 ≥2 页复用才能进 ui-components.js"被删除。**阶段 0 必须为 `popover` 找到 ≥2 个真实消费页面，否则不应合入。** 目前有 1 个（时间选择器），建议再接入 1 个（如 `field-selector.js` 或某个页面的下拉筛选）。

---

### 阶段 1：堵住契约盲区（3–6 人日）

**范围**：修复 `check_ui_contract.py` 的实测覆盖漏洞。

**实测发现的盲区**（这是本次评估的独立发现，你的描述中未提及）：

`check_ui_contract.py` 用的是 `ASSETS.glob("*.css")` 和 `ASSETS.glob("*.js")`——**只扫描 `assets/` 顶层，不递归**：

| 项 | 被扫描 | 实际存在 | **未被扫描** |
|---|---:|---:|---:|
| CSS | 13 | 19 | **6 个**（全部在 `assets/themes/`） |
| JS | 42 | 63 | **21 个**（在 `assets/pages/`、`assets/runtime/`） |

**即：6 个 theme CSS 和 21 个子目录 JS 从未被 legacy 类名契约检查覆盖。** 而 `themes/product-domain.css` 是 64.1 KB / 527 规则块的第四大 CSS 文件，`runtime/date-range-store.js` 是 683 行的核心状态模块。

**产出**：
1. `validate_styles()` 改为 `ASSETS.rglob("*.css")`，`validate_scripts()` 改为 `ASSETS.rglob("*.js")`
2. 修复因此暴露出的 legacy 类名违规
3. **新增规则：禁止在 HTML 中新增手写 `ui-*` 组合类**（对应 §1.4 的头号问题）
   - 实现方式：建立"允许手写"的类名白名单（布局类如 `ui-page-header__scope` 可留），其余要求走 `TmallUI.*` 工厂
   - 这是**唯一能真正提升 31% 采用率的机制**

**验收标准**：
- 扩展后的 `check_ui_contract.py` 在 19 个 CSS + 63 个 JS 上通过
- `tests/test_ui_system_contract.py` 的 `test_shared_contract_rejects_legacy_assets` 继续通过
- 新增 1 个测试：断言 `validate_styles`/`validate_scripts` 扫描的文件数 == 19/63（防止再次漏扫）

**退出条件**：CI 中 `check_ui_contract.py` 扫描数与文件系统实际数一致，且该一致性被测试锁定。

**风险**：扩大扫描范围后可能一次性暴露大量既有违规，导致"要么放宽规则、要么大改"的两难。**缓解**：先只加扫描、把新发现的违规记为警告（非失败），在阶段 2 逐页清理时再转为硬失败。

---

### 阶段 2：逐页收敛组件采用率（30–50 人日）

**范围**：按 §1.3 的复杂度排名，从低到高逐页把 754 处手写 `ui-*` 类名收敛到 `TmallUI.*` 工厂。

**排序依据**（实测）：先做 `core-product-analysis`（0 处手写 ui 类，最干净）、`category-dashboard`（2 处）、`analysis`（4 处），最后做 `product-detail`（94 处）、`promotion`（72 处）、`overview`（59 处）。

**产出**：每页一个独立可回滚的提交。

**验收标准**（每页）：
- 该页手写 `ui-*` 类名数量下降到白名单允许的范围
- `node scripts/audit_ui_contrast.cjs` 对该页通过（浅色 + 暗色）
- `node scripts/audit_core_interactions.cjs` 通过
- 该页在浅色/暗色两种主题下截图与改造前一致（像素级或人工确认）
- 无新增 `!important`

**退出条件**：754 处手写类名降到 ≤150 处（保留布局类），且 `TmallUI` 采用率从 **31.0%（9/29）提升到 ≥60%（≥18/29）**。

**风险**：
1. **工厂输出 DOM 与手写 DOM 结构不一致导致样式错位**——这是本阶段最高频的失败模式。**缓解**：每页改造前先记录该页所有 `ui-*` 选择器命中的元素层级，改造后逐一比对
2. **`period-review` 应放到最后**：它是 394.8 KB / 9 文件 / 17 个 `<script>` 标签的最大页面，且 `period-review-live.js` 3,478 行，改造风险集中。**建议单独排期，不与其他页面混做**

---

### 阶段 3：JSDoc 类型检查（25–45 人日）

**范围**：引入 `tsconfig.json` + `// @ts-check`，**只做检查、不产出运行时代码**。

**推进顺序**（按耦合度，从核心到外围）：
1. `ui-components.js`（613 行，公共 API 面 30 个）—— 收益最高
2. `assets/api.js`（199 行）—— 所有页面的数据入口
3. `assets/runtime/*.js`（4 个文件）—— 跨页面共享状态
4. `assets/format.js`、`labels.js`、`metric-polarity.js` —— 纯函数，最易标注
5. `{page}-live.js` —— 逐页推进

**产出**：
1. `tsconfig.json`，`checkJs: true`、`allowJs: true`、`noEmit: true`
2. 上述文件的 JSDoc 标注
3. CI 新增步骤：`npx tsc --noEmit`

**验收标准**：
- `npx tsc --noEmit` 在已标注文件清单上 exit 0
- 新增测试：断言"已标注文件清单只增不减"（防止类型覆盖退化）
- **不要求**：不追求 100% 覆盖；不引入 `tsc` 产出物

**退出条件**：`ui-components.js` + `api.js` + `runtime/*` + 5 个纯函数模块全部通过 `tsc --noEmit`，且类型检查在 CI 中稳定运行。

**风险**：
1. **`checkJs` 在 24,200 行存量代码上会产生海量报错**。**缓解**：用 `tsconfig.json` 的 `include` 白名单精确控制范围，不做全仓库检查
2. **JSDoc 会与现有注释风格冲突**：`tokens.css` 和 `ui-components.js` 里的注释是**中文业务说明**（记录事故原因、WCAG 计算依据、为什么删掉某个工厂），质量很高。**JSDoc 应补充而非替换这些注释**
3. **`tsc` 会引入 Node 工具链到 CI**。CI 已有 `node: ['24']` 和 `desktop/package-lock.json` 缓存，**成本可控**

---

### 阶段 4（条件触发）：CSS 作用域升级

**触发条件**（**必须全部满足才启动**，否则不启动）：
1. 阶段 0–3 全部完成
2. **`check_css_syntax.py` + 浏览器浮层门禁上线后，仍发生 ≥1 次"CSS 级联/作用域"类生产事故**
3. 团队规模增长到 ≥3 名前端，或页面数增长到 ≥30 个

**范围**：方案 D 的子集——**不做全量 Web Components**，只对**浮层类组件**（popover/dropdown/tooltip/picker/modal/drawer）引入 Shadow DOM 隔离，其余保持全局 CSS。

**理由**：实测显示事故集中在浮层（`position:fixed` 被吞导致渲染到文档流底部）。**用最小隔离面覆盖最高风险面**，避免方案 D 的全局改造代价。

**退出条件**：浮层组件在 Shadow DOM 下，`audit_ui_contrast.cjs` 与焦点管理测试全部通过。

---

### 路径总览

| 阶段 | 人日 | 可回滚 | 关键产出 |
|---|---:|---|---|
| 0. 止血与接线 | 2–4（在途，已完成 ~80%） | ✅ | popover + CSS 结构门禁 + 浮层冒烟门禁 |
| 1. 堵契约盲区 | 3–6 | ✅ | 递归扫描 + 禁止新增手写 ui 类 |
| 2. 逐页收敛 | 30–50 | ✅ 每页独立 | 采用率 31% → ≥60% |
| 3. JSDoc 类型 | 25–45 | ✅ | `tsc --noEmit` 通过核心模块 |
| 4. 作用域升级（条件） | 20–35 | ⚠️ | 浮层 Shadow DOM 隔离 |
| **合计** | **80–140** | | |

对比方案 A/B 的 223–340 人日，**方案 C 全路径约为其 1/3，且全程无不可逆点。**

---

## 4. 明确建议

### 推荐：方案 C（保留原生 + 补原语 + 收紧契约 + JSDoc 类型检查），按 §3 分阶段推进

**核心理由（按重要性排序）：**

**1. 痛点与方案错配——这是最重要的理由。**
你列出的 4 个痛点中：
- 痛点 1（组件层被绕过）→ 根因是**契约门禁只拦旧类名、不拦手写新类名**，是**治理问题**，不是技术栈问题。React 能强制解决，但方案 C 的契约扩展 + 逐页收敛同样能解决，成本低 5 倍
- 痛点 2（缺交互原语）→ **纯属补齐工作**，与框架无关。在途已用 ~100 行 `popover` 解决
- 痛点 3（CSS 无作用域）→ 这是**唯一真正指向技术栈**的痛点。但实测表明事故形态是"**语法错误导致规则被吞**"，而 `check_css_syntax.py` 已能静态拦住这一类（实测 exit 0）。剩下的"语义级联错误"风险，用阶段 4 的最小隔离面覆盖即可，**不需要为此重写 21 个页面**
- 痛点 4（无类型检查）→ **JSDoc + `checkJs` 可以拿到 80% 的收益**（参数类型、属性拼写、null 检查），成本是 TypeScript 全量迁移的 1/5

**四个痛点里三个可以在原生栈内解决，第四个可以部分解决。这是不重写的决定性论据。**

**2. 实测的"离开静态 HTML"代价远高于预期。**
这不是"审计脚本要改"，而是：
- CI 中 **4 个真实 Chromium 门禁会持续失效**——而它们是当前**唯一**能拦住 UI 回归的防线（`console` 无报错、单测全绿却渲染错位，这个项目已经吃过一次）
- **194 个 test 函数与 UI 源码文本强耦合**（`test_ui_system_contract.py` 的 30 个测试直接 `read_text` 断言 CSS/JS 源码字符串），需**重写而非修改**
- `validate_ui_demos.cjs` 的断言（`data-page`、`../assets/api.js`、无内联 SVG）在 SPA 下**结构性失效**

**在迁移期间失去唯一的 UI 回归防线，是这类项目最典型的翻车方式。**

**3. 方案 C 是唯一保留全部未来选项的路线。**
方案 A/B 的不可逆点（构建产物接管）一旦越过，回滚等于二次迁移。方案 C **无不可逆点**——它保留了"改一行刷新即见"，也保留了将来转向 A/B/D 的全部自由。**在痛点归因尚不完全清晰时，保留选项的价值高于提前优化。**

**4. 团队实际上已经在走这条路，且走对了。**
在途改动（`popover` + `check_css_syntax.py` + `smoke_date_picker.cjs` + `smoke_popover.cjs`）**正是方案 C 的阶段 0**，且 `check_css_syntax.py` 的文档头精确复述了事故机制、`smoke_date_picker.cjs` 的判据直接来自事故症状、`popover` 已接入真实消费方。**建议与既有的工程直觉一致，不需要团队转向。**

### 什么条件下应该改变这个建议

**改投方案 A/B（全量重写）的条件——需同时满足 ≥3 条：**
1. **团队规模 ≥5 名前端**，且明确要招聘 React/Vue 技能栈的人（重写的真正收益是"招人容易"，不是"代码更好"）
2. **产品进入功能冻结期**，有 3–6 个月可以承受 4 个 CI 门禁失效的窗口
3. **页面数从 21 增长到 ≥40**，手写类名从 754 增长到 ≥1,500（说明治理手段确实失效，靠人力收敛不可行）
4. **`period-review` 之外再出现 ≥3 个超过 300 KB 的页面**（说明复杂度失控，不是个案）
5. **CSS 作用域问题升级为每周 ≥1 次生产事故**，且阶段 4 的最小隔离面方案被验证无效

**改投方案 D（Web Components）的条件：**
1. 阶段 0–3 完成后，**仍发生 ≥2 次"CSS 语义级联"生产事故**（即 `check_css_syntax.py` 拦不住的那类）
2. 且事故集中在浮层以外的组件（若集中在浮层，走阶段 4 的最小隔离面即可）

**降级/收紧建议的条件：**
- 若阶段 2 的逐页收敛推进 ≥10 页后采用率仍未提升（说明契约门禁约束力不足），则应放弃"手工收敛"，改为**在 CI 中硬性禁止新增手写 `ui-*` 类 + 只做增量页面**，承认存量 754 处短期内无法清理

### 明确不推荐

- **方案 B（Vue3）**：相对方案 A 的框架红利（`<style scoped>`、模板亲和度）**不足以抵消它与方案 A 完全相同的 194 个 test 重写代价**，且 `<style scoped>` 与现有 183 处 `!important` 会冲突
- **方案 E（微前端）**：与实测的"59 个 JS 文件、单仓库、单一 shell"的工程形态**根本不匹配**，且会破坏 `shell.js` 的 `liveAdapters` 和 `date-range-store.js` 这两个正在快速演进的核心共享机制

---

## 5. 风险清单（按严重度排序）

### R1 — 严重 — 组件采用率仅 21%（业务代码），且契约门禁结构性拦不住绕过

**实测**：`TmallUI` 导出 29 个 API（HEAD），业务代码只用 6 个（20.7%）；含组件演示页也只用 9 个（31.0%）；约 20 个 API 零业务调用（含 `panel`/`metricCard`/`table`/`badge`/`pageHeader`）；同时页面手写 `ui-*` 类名 754 处。

**根因**：`check_ui_contract.py` 的 `LEGACY_ROOTS` 只含**旧**类名（`.button`/`.panel`/`.metric-card`），手写 `.ui-panel` 完全合法。**门禁拦住了"用旧类名"，却没拦住"绕过工厂"。**

**缓解措施**：
1. 阶段 1 新增规则：建立"允许手写 `ui-*` 类"白名单，其余必须走 `TmallUI.*` 工厂
2. 阶段 2 逐页收敛，目标 ≥60% 采用率
3. **参考仓库已有的自定标准**："新组件必须 ≥2 页复用才能进 `ui-components.js`"（`ui-components.js:240` 注释）——建议反向补充一条："**已有工厂的组件，页面不得手写**"
4. 为 `popover` 找到 ≥2 个真实消费页面后再合入，避免重演 `decisionCard` 被删的覆辙

---

### R2 — 严重 — 契约门禁存在覆盖盲区：6 个 CSS + 21 个 JS 从未被扫描

**实测**：`check_ui_contract.py` 用 `ASSETS.glob("*.css")` / `glob("*.js")`，**不递归**。被扫描 13 个 CSS / 42 个 JS；实际存在 **19 个 CSS / 63 个 JS**。**未覆盖：6 个 theme CSS（含 64.1 KB 的 `product-domain.css`）+ 21 个子目录 JS（含 683 行的 `date-range-store.js`）。**

**影响**：legacy 类名可能已在这 27 个文件中存在而无人知晓；"契约通过"这个信号的可信度被高估。

**缓解措施**：
1. 阶段 1 改为 `rglob`
2. 新增测试锁定扫描文件数（19 / 63），防止再次漏扫
3. 扩大扫描后若暴露大量违规，先降级为警告，阶段 2 逐步转硬失败

---

### R3 — 严重 — 文档与实现不一致，`upgradeLegacy()` 不存在

**实测**：`DESIGN_SYSTEM.md:1328` 声称"历史页面中的 `.button`、`.panel`、`.metric-card`、`.badge`、`.empty-state`、`.data-table` 等 class 由 `TmallUI.upgradeLegacy()` 自动映射到 `ui-*` canonical class"。**全仓库 `upgradeLegacy` 出现 0 次。** 且 `tests/test_ui_system_contract.py:146-152` 有测试断言 `ui-components.js` **不含** `legacyMap`、不含 `new MutationObserver`——即升级 shim 是**被有意移除并被测试锁定**的。

**影响**：新人读规范会以为存在自动迁移兜底，可能因此手写旧类名并期待自动升级，实际得到无样式节点。**这是会直接导致错误决策的文档债务。**

**缓解措施**：
1. 修订 `DESIGN_SYSTEM.md` §11.1 第 1328 行，删除 `upgradeLegacy()` 描述，改为明确"**不存在运行时类名升级；旧类名由 `check_ui_contract.py` 在提交前拦截**"
2. 增加一条测试：断言 `DESIGN_SYSTEM.md` 中提到的公共 API 名在 `ui-components.js` 的 `api` 对象中真实存在（防止文档再次漂移）

---

### R4 — 高 — CSS 语法错误静默吞掉后续规则，且无静态门禁（部分已缓解）

**实测**：`!important` 183 处；`components.css` 单文件 532 处 `.ui-*` 选择器 / 912 规则块；8 个页面另有内联 `<style>`；全局 CSS 与内联 CSS 双层覆盖。

**事故机制**（`check_css_syntax.py` 文档头记录）：`.demo-picker__backdrop { ... }` 覆盖掉 `.demo-period__mode {` 行 → 后续声明体成为孤立声明块 → **浏览器从该点起连带吞掉后续规则**，包括 `.demo-picker__backdrop{position:fixed}` → 弹窗以 `position:static` 渲染到 top 2432px（视口 800px）→ 表现为"点了没反应"，**console 无报错、异常捕获为空、单测全绿**。

**已缓解**：`scripts/check_css_syntax.py`（149 行，在途）能静态拦住这一类，**我实测在 19 个 CSS 上 exit 0**。

**残留风险**：该脚本**尚未接入 CI**（`.github/workflows/quality-gate.yml` 中无引用），且它只能拦**语法**错误，拦不住"合法选择器意外命中其他页面元素"的**语义**级联错误。

**缓解措施**：
1. **立即**把 `check_css_syntax.py --strict` 接入 `quality-gate.yml`（阶段 0，0.5 人日）
2. 保留并泛化 `smoke_date_picker.cjs` / `smoke_popover.cjs` 为通用浮层可见性门禁
3. 阶段 4 条件触发时，对浮层组件引入 Shadow DOM 隔离
4. 逐步削减 183 处 `!important`（可作为阶段 2 的副产物指标）

---

### R5 — 高 — 双轨并行期失去唯一的 UI 回归防线（仅方案 A/B 有此风险）

**实测**：CI 中 6 个 cjs 门禁，其中 **4 个依赖真实 DOM 结构**（`smoke_core_pages`、`browser_prd_gates`、`audit_core_interactions`、`audit_ui_contrast --states`）。`audit_ui_contrast.cjs --states` 遍历 7 种 `data-state` 做 WCAG 检查。`validate_ui_demos.cjs` 断言 9 个页面 HTML 含 `data-page`/`../assets/api.js`/`../assets/shell.js`、禁止内联 SVG——**SPA 下结构性失效**。

**影响**：迁移的数月内，UI 回归只能靠人工截图发现。**这个项目已经有过"console 无报错、单测全绿、页面却是坏的"的先例（R4），失去浏览器门禁等于回到那个状态。**

**缓解措施**（若最终选择方案 A/B）：
1. **先在旧栈上补齐 Playwright 门禁，再开始迁移**——不要在门禁失效的同时迁移
2. 为每个迁移完成的页面**同时**写新旧两套断言，直到旧栈下线
3. `audit_ui_contrast.cjs --states` 最后迁移（它最难重建）
4. **本报告推荐方案 C，正是为了完全规避这条风险**

---

### R6 — 中 — `shell.js` 隐式动态加载机制造成"加载了什么"不可静态推断

**实测**：`shell.js:95-107` 在运行时按 `document.body.dataset.page` 动态注入 `{page}-live.js`（`liveAdapters` 硬编码 8 个页面映射），并动态加载 `table-controls.js`、`ui-components.js`、`version-check.js`、`desktop-integration.js`。`ui-components.js` **同时**被页面 HTML 和 `shell.js` 加载，注释要求"版本号需保持一致"。

**影响**：读一个页面的 HTML 无法知道它实际加载了什么 JS；`ui-components.js` 的双重加载路径是版本漂移和重复初始化的隐患源（该文件已用 `data-light-dismiss-ready` 标记做了幂等保护，见 `ui-components.js:458-459`）。

**缓解措施**：
1. 阶段 3 的 JSDoc 工作中，为 `shell.js` 的加载机制补文档注释
2. 新增一个门禁：断言 `ui-components.js` 在页面 HTML 与 `shell.js` 中的版本号字符串一致
3. 中期考虑把 `liveAdapters` 从硬编码映射改为约定（但**不在本次范围**，避免扩大改动面）

---

### R7 — 中 — 复杂度高度集中，`period-review` 是单点风险

**实测**：`period-review` 页面合计 **394.8 KB / 9 个文件**，是第二名 `product-detail`（186.2 KB）的 2.1 倍。`period-review-live.js` **3,478 行**是最大单文件（是第二名的 2.4 倍）。该页有 **17 个 `<script>` 标签**。`period-review.css` 2,431 行 / 69.8 KB。

**影响**：任何针对该页的改造（无论方案）都是高风险、长周期、难以回滚的。且它是唯一拥有独立子目录 `assets/pages/period-review/`（8 个模块）的页面——说明拆分已开始但未完成。

**缓解措施**：
1. **方案 C 阶段 2 中把 `period-review` 单独排期，不与其他页面混做**
2. 优先完成 `assets/pages/period-review/` 的模块拆分（已有 8 个模块，继续拆 `period-review-live.js`）
3. 该页改造前必须有完整的浏览器门禁覆盖（`verify-period-review-*.cjs` 已有 4 个，可利用）

---

### R8 — 中 — 测试与源码文本强耦合，形成迁移阻力

**实测**：**11 个 pytest 文件、约 194 个 test 函数**与 `ui_demo` 源码文本耦合。其中 `test_ui_system_contract.py`（30 个 test）大量使用 `read_text()` 后断言字符串存在，例如断言 `components.css` 含 `.ui-panel__title`、`ui-components.js` 含 `const legacyNames`、`tokens.css` 含 `--title-width-sm`。`test_frontend_prd_contract.py` **1,178 行 / 96 个 test**，同时引用 `ui_demo` 和 `.cjs`，是最大单文件。

**影响**：这类测试在**方案 C 下是资产**（源码存在，断言继续有效），在**方案 A/B/D 下是负债**（源码形态改变，需重写）。这是本报告推荐方案 C 的量化依据之一。

**缓解措施**：
1. 方案 C 下：**修正**其中 1 个测试——`test_runtime_upgrade_shim_is_removed_and_audit_is_canonical` 断言 `"const legacyNames" in source`，而 `popover` 合入后该字符串仍在（`ui-components.js:480`），**当前仍通过**；但需注意它同时断言 `"new MutationObserver" not in source`，**新增代码不得引入 MutationObserver**
2. 逐步把"断言源码字符串"改为"断言运行时行为"（后者对任何方案都更稳健）
3. 若最终选方案 A/B，**必须先完成这批测试的重写，再开始页面迁移**

---

### R9 — 低 — 构建工具链已存在但未接线，存在"半成品基础设施"认知风险

**实测**：`frontend-build/` 含 `esbuild ^0.28.2`、`echarts ^5.5.1`、`lucide ^0.460.0`，产出 `echarts-custom.js`（862 B）和 `lucide-custom.js`（1,927 B）两个定制 bundle。但 **`esbuild` / `frontend-build` 在 `scripts/`、`packaging/`、`.github/` 中零引用**——它不参与 CI，也不参与页面构建。`desktop/package.json` 有独立的 `tsc` + `vitest` + `playwright` 工具链，`desktop/src/` 共 6 个 TS 文件 / 479 行。

**影响**：`frontend-build` 的存在容易让人误以为"已经有构建步骤了，加个 Vite 很自然"，从而低估方案 A/B 的不可逆点。**实际上当前前端页面完全无构建，`frontend-build` 只产出 2 个 vendor bundle。**

**缓解措施**：
1. 在 `README.md` 或 `DESIGN_SYSTEM.md` 中明确 `frontend-build` 的职责边界（仅 vendor bundle，不参与页面构建）
2. 若引入 `tsc --noEmit`（方案 C 阶段 3），**明确区分"检查工具链"与"构建工具链"**，避免滑向构建

---

### R10 — 低 — 评估期间工作区被并发修改，基准线漂移

**实测**：`ui-components.js` 在我读取过程中从 512 行变为 613 行（`LastWriteTime` 相差 0.2 分钟）。`git diff --stat HEAD` 显示 9 个文件、**+1,019 / -130 行**未提交改动。`popover` 原语（~100 行）、`check_css_syntax.py`（149 行）、`smoke_date_picker.cjs`（235 行）、`smoke_popover.cjs`（217 行）均为在途。`popover` 的调用点（`runtime/date-range-store.js:373`）也是在评估过程中才出现的。

**影响**：本报告的"现状"锚定在 `HEAD 8b87318`。若在途改动合入，§1.1 中"完全没有 popover"一条失效，§1.4 的采用率分子 +1（已实测：工作区 22 处 / 10 个 API）。

**缓解措施**：
1. 本报告明确标注基线为 `HEAD 8b87318`，并单列在途改动
2. 在途改动合入后**重跑 §1 的量化脚本**（附录 A），更新采用率
3. 评估类工作应**先锁定工作区或建 branch**，避免基准漂移

---

## 附录 A：实测命令与数据来源

所有数字均可通过以下命令复现（工作目录 `E:\www\tmall-dashboard`，基线 `HEAD 8b87318`）。

**规模统计**
```powershell
# 页面数 / 大小
Get-ChildItem frontend\ui_demo\pages\*.html | Measure-Object          # 21
# CSS：19 个 / 458.8 KB
Get-ChildItem frontend\ui_demo -Recurse -File -Include *.css | Measure-Object Length -Sum
# 手写 JS：59 个 / 1,423.5 KB（排除 4 个 echarts/lucide vendor）
Get-ChildItem frontend\ui_demo -Recurse -File -Include *.js |
  Where-Object { $_.Name -notmatch 'echarts|lucide' } | Measure-Object Length -Sum
# 手写 JS 总行数：24,200
Get-ChildItem frontend\ui_demo -Recurse -File -Include *.js |
  Where-Object { $_.Name -notmatch 'echarts|lucide' } |
  ForEach-Object { (Get-Content $_.FullName | Measure-Object -Line).Lines } | Measure-Object -Sum
# CSS 规则块：3,643；!important：183
```

**组件采用率**
```powershell
# TmallUI 可执行业务调用点：HEAD 21 处 / 工作区 22 处
# （排除 component-catalog.html 的 14 处演示调用与 // 注释行）
Get-ChildItem frontend\ui_demo -Recurse -File -Include *.js,*.html |
  Where-Object { $_.Name -ne 'component-catalog.html' } |
  Select-String -Pattern 'TmallUI\.' -AllMatches |
  Where-Object { $_.Line.Trim() -notmatch '^//' }
# 导出 API 面：HEAD 29 个 / 工作区 30 个（ui-components.js 的 const api = {...}）
# 手写 ui-* 类名（class 属性内）：754 处，21 页合计
```

**契约盲区**
```powershell
# 被扫描 13 CSS / 42 JS；实际 19 CSS / 63 JS → 6 + 21 未覆盖
Get-ChildItem frontend\ui_demo\assets -File -Filter *.css          # 13（glob 范围）
Get-ChildItem frontend\ui_demo\assets -Recurse -File -Filter *.css # 19（实际）
```

**测试与门禁**
```powershell
Get-ChildItem tests\*.py | Measure-Object                          # 96 个文件
# 951 个 test 函数；11 个文件耦合 ui_demo
Get-ChildItem scripts\*.cjs | Measure-Object                       # 35 个
# 22 个依赖 Playwright；6 个接入 CI
# CI 门禁见 .github\workflows\quality-gate.yml L67-76
```

**门禁实测运行结果**
```powershell
python scripts/check_ui_contract.py     # exit 0，20 项 OK（19 页 + shared assets）
python scripts/check_css_syntax.py      # exit 0，19 个 CSS 结构合法
```

**基线对照**
```powershell
git rev-parse HEAD                       # 8b87318
git show HEAD:frontend/ui_demo/assets/ui-components.js | Measure-Object -Line  # 512
git diff --stat HEAD -- frontend/ui_demo # 9 files, +1019 / -130
```

---

## 附录 B：本次评估未能验证的事项

以下事项**本报告未做验证**，在据此决策前需补充：

1. **未运行完整 pytest 套件**（951 个 test）。本报告只运行了 `check_ui_contract.py` 和 `check_css_syntax.py` 两个静态门禁，未执行 `python -W error::ResourceWarning -m unittest discover -s tests`。
2. **未运行 Playwright 浏览器门禁**。35 个 cjs 中 22 个需要 Playwright，实测 `desktop/node_modules/playwright` 与根 `node_modules/playwright` **均不存在**（`Test-Path` 返回 False），需先 `npm ci --prefix desktop && npx --prefix desktop playwright install`。因此**"当前 UI 门禁是否真的能拦住回归"未经验证**——这一点对 R5 的严重度判断有影响。
3. **未实测页面在浏览器中的真实渲染**。所有 CSS/JS 分析均为静态分析。
4. **未评估后端 API 契约对前端的约束**。`api/`、`services/`、`repos/` 未纳入本次范围。
5. **`frontend-build/` 产出的 2 个 vendor bundle 是否与 `assets/` 中现有版本一致，未验证**。
6. **Electron 桌面端的实际加载路径未完整追踪**。只确认 `desktop/src/main.ts:55` 使用 `window.loadURL(url)`，未追踪 `url` 的具体来源。
7. **工作量估算未与团队实际速率校准**。报告中的 150–250 行/人日、1.5–3 人日/审计脚本均为行业经验值，建议用团队过去 3 个月的交付数据校准后再用于排期。
