# Tmall Dashboard UI 布局深度审计（NUI）

> 审计日期：2026-10-01
> 审计对象：`E:\www\tmall-dashboard\frontend\ui_demo`（23 个页面 / 22 个可路由）
> 审计方式：真实浏览器渲染 + DOM 量化（22 页 × 3 视口 = 66 次加载），配合源码静态核对
> 审计原则：NUI（NexusAI + AntV + Ant Design）——先产品含义，再证据，再表达
> 只读审计，未改动任何业务代码与数据

---

## 0. 方法与口径

| 项目 | 说明 |
|---|---|
| 视口 | 1440×900（desktop）、768×1024（compact）、390×844（mobile） |
| 采样 | `waitUntil: networkidle` + 2.2~2.5s 稳定等待，每页独立 context |
| 度量 | 横向溢出、内容裁剪、横/纵向滚动容器、卡片与控件密度、标题层级、接口 4xx、控制台错误、DOM 节点数 |
| 复现脚本 | `scripts/audit_ui_layout.cjs`、`scripts/audit_ui_deep.cjs`、`scripts/audit_ui_dom.cjs`、`scripts/probe_ui_density.cjs` |
| 原始数据 | `.tmp/ui-audit/audit.json`、`deep.json`、`dom.json`、`shots/`（66 张全页截图） |

所有数字均在 2026-10-01 当天多次复测，可复现。

---

## 1. 结论摘要

**好的部分先说清楚**——这个项目的 UI 底子比"待重构"要好得多：

- **零横向溢出**：22 页 × 3 视口，`documentElement.scrollWidth` 全部等于 `clientWidth`，没有任何一页把内容挤出视口。
- **token 纪律极强**：`components.css`（120KB / 340 个类）与 `shell.css` 硬编码颜色 **0 处**，全部走 `var(--*)`；`tokens.css` 已经是完整的 primitive → semantic → component 三层结构，含亮/暗两套与图表色板。
- **壳层收敛已完成**：侧栏 + 顶栏 + `main.demo-page`（`max-width: 1680px`）统一由 `shell.js` 注入，导航分组、品类模式、时间范围、复盘周期控件都有唯一归属，没有出现"壳层和页面各放一套时间筛选"的重复（`period-review` 还专门用 CSS 隐藏了顶栏的通用时间控件）。
- **组件层已落地且超出计划**：`ui-components.js` 已导出 20+ 个组件（`pageHeader` / `contextBar` / `dataState` / `metricCard` / `metricGrid` / `panel` / `tableToolbar` / `detailDrawer` / `stickyActionBar` / `decisionCard` / `modal` …），并自带 `TmallUI.audit()` 自查。实测 22 页跑下来只有 **2 处** "数据表缺少 ui-table-wrap 容器"。
- **断点覆盖真实**：1450 / 1180 / 760 三个断点确实在起作用，移动端表格有明确的横向滚动容器，移动端触控目标升到 44px。

**问题集中在四类**，都不在"美化"层面：

```text
① 页面级缺陷（路由 404、接口 422、页面头部重复）—— 该修的 bug
② 信息层级没收敛（首屏先讲说明文字，不先给结论；主操作不唯一）
③ 密度失衡（一页 193 个可交互元素、996 个徽标、24333 个 DOM 节点）
④ 组件建了但没统一用（同一种筛选栏一页出现 3~4 次，各写各的）
```

严重度分布：

| 级别 | 数量 | 说明 |
|---|---|---|
| P0 | 4 | 路由 404、接口 422、页面头部整块重复、错误状态语义错 |
| P1 | 8 | 标题层级、首屏层级、主操作唯一性、长页面、表格横滚、内容硬裁 |
| P2 | 9 | DOM 卫生、组件复用不均、内联样式、可访问性、死路由 |

---

## 2. 现状快照（量化）

### 2.1 逐页核心指标（1440×900）

| 页面 | DOM 节点 | 卡片 | `.ui-button` 总数/可见 | 徽标 总/可见 | 可交互元素 | 横向裁剪 | 纵向滚动容器 | 桌面高度 | 移动高度 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| overview | 1,789 | 12 | 38 / 12 | 9 / 5 | 102 | 14 | 1 | 2,655 | 3,846 |
| category-dashboard | 733 | 0 | 18 / 1 | 4 / – | 35 | 0 | 1 | 1,705 | – |
| goals | 828 | 3 | 23 / 4 | 5 / – | 43 | 0 | 2 | 1,720 | – |
| reviews | 679 | 6 | 20 / 3 | 4 / – | 36 | 0 | 1 | 1,244 | – |
| **period-review** | **5,146** | 9 | **224 / 43** | 4 / 0 | **118** | **23** | **5** | 3,661 | **7,687** |
| products | 1,806 | 5 | 76 / 8 | 4 / 0 | 125 | 20 | 2 | 1,314 | 5,652 |
| lifecycle | 1,628 | 5 | 59 / 27 | **53 / 49** | 87 | **24** | 2 | 2,487 | **7,055** |
| keyword-promotion | 2,050 | 7 | 30 / 5 | 4 / 0 | **157** | 0 | 2 | 1,149 | – |
| promotion | 1,335 | 14 | 40 / 6 | 13 / 6 | 46 | 0 | 1 | 2,823 | 5,488 |
| new-products | 2,249 | 8 | 97 / 31 | 5 / 0 | 81 | 20 | 1 | 3,172 | – |
| creative-board | 747 | 5 | 25 / 3 | 4 / – | 38 | 0 | 1 | 900 | – |
| flow-source | 1,227 | 8 | 17 / **0** | 7 / – | 29 | 0 | 2 | 1,824 | – |
| rival-analysis | 3,609 | 8 | 17 / **0** | 7 / – | 35 | 0 | 3 | 2,994 | – |
| **market-ranking** | **7,927** | 11 | 28 / 2 | **996 / 2** | 102 | 0 | 2 | **5,743** | **11,051** |
| analysis | 720 | 0 | 19 / 2 | 4 / – | 36 | 0 | 1 | 900 | – |
| data-collection | 1,150 | 22 | 39 / 18 | 5 / 0 | 46 | 0 | 1 | **3,547** | **7,874** |
| **data-center** | **24,333** | 17 | **300 / 87** | 4 / 0 | **193** | 0 | **5** | 1,925 | 4,517 |
| settings | 1,525 | 1 | 85 / 4 | 24 / – | 43 | 0 | 1 | 1,120 | – |
| component-catalog | 706 | 7 | 31 / 14 | 11 / – | 46 | 0 | 1 | 1,661 | – |
| compare → /reviews | 679 | 6 | 20 / 3 | 4 / – | 36 | 0 | 1 | 1,244 | – |
| manage → /settings | 1,525 | 1 | 85 / 4 | 24 / – | 43 | 0 | 1 | 1,120 | – |

**读法**：`.ui-button 总数 / 可见数` 的差值就是藏在 `dialog[hidden]` 与折叠区里的控件；`横向裁剪` 是 `overflow-x: hidden` 且内容比容器宽 > 8px 的容器数（内容静默丢失）；`纵向滚动容器` 是页面内又套了一层可纵向滚动的容器。

### 2.2 接口与控制台健康

66 次加载里，控制台错误的构成：

| 次数 | 内容 | 判定 |
|---:|---|---|
| 63 | `gitcode.com/api/v5/.../releases/latest` 被 CORS 拦截（`ERR_FAILED`） | 每个页面加载必发 2 条噪音错误 |
| 24 | `422 UNPROCESSABLE ENTITY` | **真缺陷**，见 P0-2 |
| 6 | `404 NOT FOUND` | `/api/goals/2026` + `/product-detail` |

4xx 明细（去重后）：

```text
422  /api/page-capabilities?page=analysis
422  /api/page-capabilities?page=market-ranking
422  /api/page-capabilities?page=data-collection
422  /api/page-capabilities?page=keyword-promotion
422  /api/page-capabilities?page=new-products
422  /api/page-capabilities?page=flow-source
422  /api/page-capabilities?page=rival-analysis
422  /api/page-capabilities?page=catalog
404  /api/goals/2026
404  /product-detail
```

页面级 JS 异常（`pageerror`）**0 个**——没有未捕获异常。

---

## 3. P0：页面级缺陷

### P0-1 `/product-detail` 路由 404

`app.py:301` 的 `/<page>` 白名单（19 个页面）**不含 `product-detail`**，且没有独立的 `/product-detail` 路由；商品详情只能通过 `/products/<product_id>`（`app.py:311`）到达。但：

- `frontend/ui_demo/pages/product-detail.html` 存在（317 行）；
- `shell.js:207` 的 `activePageMap` 专门为 `'product-detail'` 写了 `→ 'products'` 的映射；
- `services/page_capability_service.py:72` 把 `product-detail` 当作正式页面（`route: '/products/:product_id'`）。

**影响**：任何指向 `/product-detail` 的深链、书签或外部跳转直接 404。实测 `curl /product-detail` → 404。

**建议**：二选一——(a) 把 `product-detail` 加进白名单并让它自己处理"缺 product_id"的空态；(b) 明确它只是 `/products/:id` 的模板，删掉 `activePageMap` 里的映射并在页面内加 302。倾向前者（保留可分享的详情 URL 形态）。

### P0-2 8 个页面的 `/api/page-capabilities` 恒定 422

`assets/api.js:195` 在**每个页面**加载时都会调 `loadPageCapabilities()`（只有 `creative-board` 被显式跳过），pageKey 取 `document.body.dataset.page`。

而 `services/page_capability_service.py` 的 `PAGE_DEFINITIONS` 只登记了 **13 个页面**：

```text
overview / category-dashboard / products / promotion / lifecycle / reviews /
period-review / data-center / settings / product-detail / goals / compare / manage
```

实际存在的页面多了 8 个，于是这 8 页每次加载都发一个注定 422 的请求：

```text
analysis  keyword-promotion  new-products  market-ranking
flow-source  rival-analysis  data-collection  catalog(component-catalog)
```

后端返回 `{"code":"VALIDATION_ERROR","message":"unknown page capability filter","details":{"field":"page","value":"analysis"}}`。

**影响**：`api.js:195` 用的是 `.catch(() => {})`，所以错误被静默吞掉——这 8 页的 `data-capability-key` 门控**完全失效**（该禁用的按钮不会禁用）。当前这 8 页的静态 HTML 里恰好没有 `data-capability-key`，所以还没暴露出业务后果，但 JS 动态生成的元素（如 `products/table-render.js:272`）一旦落到这些页面就会失守。同时每页白送 1 条控制台错误。

**建议**：把 `PAGE_DEFINITIONS` 补齐到实际页面集合（8 条定义），并给 `loadPageCapabilities` 的失败加可见降级（至少 `console.warn` 一次 + 在数据中心的能力地图上标红），不要再静默。

### P0-3 `goals.html` 页面头部整块复制两份

`frontend/ui_demo/pages/goals.html` 第 4、5 行：

```html
<div class="ui-page-header"><div><h2>经营目标</h2><p>先设定年度总额，再按去年同期净销售额占比拆分；月度目标可直接编辑，始终保持年度总额不变。</p></div></div>
<div class="ui-page-header"><div><h2>经营目标</h2><p>先设定年度总额，再按去年同期净销售额占比拆分；月度目标可直接编辑，始终保持年度总额不变。</p></div></div>
```

实测 `goals` 页 `ui-page-header` 计数 = **2**（其他页面都是 1）。`component-catalog.html` 也有 2 个（其中一个是组件目录里的"页面标题"样例，属正常）。goals 这个是纯复制粘贴事故，页面上会看到两遍标题和两遍说明。

### P0-4 错误状态语义错位

- `GET /api/goals/2026` 返回 `404 {"code":"NOT_FOUND","message":"该年度尚未创建目标"}`，但响应里的 `availability` 字段是 `"calculation-failed"`。"该年度尚未创建目标"是**正常的空态**，不是计算失败。前端把它当异常渲染，用户看到的是"指标计算失败"而不是"去创建 2026 年目标"。
- 同类问题：`/api/page-capabilities` 的 422 响应里 `availability` 也是 `"calculation-failed"`。

**建议**：`availability` 取值要与业务含义对齐——`not-created` / `no-data` / `unavailable` / `partial` / `error` 分开。这也正好对上 `UI_OPTIMIZATION_NUI_REVIEW.md` 3.2 节的意见：**UI 语言可以收敛成三类，数据语义不能被压扁**。

---

## 4. P1：信息层级与结构

### 4.1 页面标题层级不统一（18 个 `<h2>` vs 4 个 `<h1>`，还有 2 页同时有）

| 形态 | 页面 |
|---|---|
| 页面标题用 `<h2>` | overview、category-dashboard、goals、reviews、period-review、products、lifecycle、keyword-promotion、market-ranking、data-center、data-collection、settings、flow-source、rival-analysis、creative-board、reviews、compare、manage（18 个） |
| 页面标题用 `<h1>` | analysis（`自定义分析`）、category-dashboard（`默认品类 · 本月经营`）、product-detail（`商品详情`）、period-review-redesign（`月度复盘`） |
| **同时有两个标题** | **promotion**：`<h2>推广分析</h2>`（页面头部）+ `<h1 id="promotionCommandTitle">推广经营看板</h1>`（页内）；**new-products**：`<h2>新品推广看板</h2>` + `<h1 id="promotionNewConclusionTitle">新品投放经营看板</h1>` |
| 页面标题重复 | goals（见 P0-3） |

**影响**：屏幕阅读器与大纲导航拿不到稳定的页面标题；promotion / new-products 出现"两个一级标题"，用户也会困惑"这页到底叫什么"。

**建议**：定一条硬规则——**每页有且只有一个 `<h1>`，就是页面标题**（`ui-page-header` 里的那个），页内区块一律从 `<h2>` 起。`ui-components.js:pageHeader()` 应直接产出 `<h1>`，并在 `TmallUI.audit()` 里加一条"页面必须有且仅有一个 h1"的检查。

### 4.2 侧边导航分组名污染文档大纲

`shell.js:254` 把导航分组标签渲染成 `<h2>`：

```html
<h2 class="demo-nav__label">店铺</h2>  <h2>商品</h2>  <h2>付费</h2>  <h2>市场</h2>  <h2>工具</h2>
```

实测每页标题树的前 5 个节点永远是这 5 个分组名，排在真正的页面标题之前：

```text
h2 店铺 / h2 商品 / h2 付费 / h2 市场 / h2 工具
h2 数据概览            ← 真正的页面标题排第 6
```

**建议**：导航分组标签改成 `<span>` 或 `<h2>` 之外的语义（如 `<div role="presentation">`），或给 `<nav>` 加 `aria-label` 后把分组标签降为 `<span>`。这是零成本、零风险的改动。

### 4.3 首屏被"说明书"占掉 —— 页面头部 + 上下文栏 = 144px 无数据

19 个页面有 `ui-context-bar`，实测高度 **92px**；它上面还有 52px 的 `ui-page-header`。**首屏前 144px（900px 视口的 16%）没有任何数据**，而且两块的文案高度重复：

```text
ui-page-header  <p>先看当前经营结果，再处理目标差额与待办动作。</p>
ui-context-bar  <strong>当前店铺 · 当前经营周期</strong>
                <span>先看经营判断，再处理目标差额与异常动作。</span>   ← 同义重复
```

12 个页面的 `ui-context-bar__meta` 都是这种"先…再…"的操作说明：

```text
先选择配置，再执行唯一主操作"生成图表"。
先处理待办任务，再维护人员目标和自动扫描，操作日志统一放在末尾。
先看渠道规模与效率，再进入一级、二级渠道明细。
先看推广效率，再通过筛选定位值得继续投放或需要收敛的商品。
先处理店铺身份与采集能力，再进入导入规则、预警和指标口径。
...
```

另有 18 处 `section-kicker`（`第一步` / `第二步` / `第三步` / `先看经营判断` / `数据证据` / `运营协同` / `当前状态` / `配置与导入`）。

**问题**：NUI 要求的首屏顺序是 `Orientation → Decision → Evidence → Exploration`。现在 `Orientation` 被撑成两块同义文案，`Decision` 被推到 144px 之后。**说明文字在教用户怎么用页面，而不是给用户结论。**

**建议**：
1. 合并 `ui-page-header` 与 `ui-context-bar` 为**一个** Orientation 区：一行标题 + 一行范围（店铺/周期/数据截止）。
2. 把"先…再…"的说明文字降级成 `title` 提示或帮助浮层，或直接删掉——`ui-context-bar__meta` 全项目 12 处，大部分没有信息增量。
3. `section-kicker` 只在真正有步骤语义时保留（data-center 的"配置与导入"、goals 的"第一步/第二步/第三步"是合理的），其余删掉。

### 4.4 首屏没有单一主决策区

实测 overview 首屏（900px 内）有：

```text
79 个文本节点 · 102 个可交互元素 · 10 个 main 直接子块
子块高度：52(页头) 92(上下文栏) 334(决策区) 148(指标) 40(更多指标) 1(sr-only) 388(图表区) 809(运营中心) 556(矩阵)
```

`overview-decision`（334px，4 个决策指标 + 优先动作）**确实在正确的位置**，方向是对的。但它下面紧接着又来了 4 张 KPI 卡 + 折叠的 4 张次级 KPI + 388px 的"指标对比·趋势 + 目标进度" + 809px 的"异常与行动（提醒列表 + 计划日历）" + 556px 的"日度经营矩阵"。

**同一页里 `净销售额` 出现了 3 次**（决策区、KPI 卡、日度矩阵），`目标完成度` 出现 2 次（决策区、目标进度面板）。NUI 的非协商项写着"不要把每个区块都做成卡片，不要每张卡等权重"——现在决策区、KPI 卡、图表面板、运营中心、矩阵在视觉上是同一档权重。

**建议**：
- 决策区保留并加强（这是这页最有价值的部分）；
- 4 张 KPI 卡降级为决策区的支撑行（或并入决策区做对比条），去掉"更多经营指标"折叠层；
- "指标对比·趋势"和"目标进度"必须回答一个具体问题并写进标题（现在是"按月度数据对比净销售额、支付金额和推广花费实际值"——这是描述不是问题）；
- "异常与行动"是这页的第二决策区（待办），应保留但要和第一决策区在视觉上区分（现在是同样的 `ui-panel` 白卡）。

### 4.5 主操作不唯一

| 页面 | 页头/页内控件数 | 现象 |
|---|---:|---|
| products | 16 | `当前视图 / 展示 / 普通列表 / 周期视图 / 周期 / 日 / 周 / 月 / 字段 / 经营 / 选款 / 投放 / 退款 / 生命周期 / 列设置 / 重置` 挤在一行，与"商品运营"标题同级 |
| promotion | 2 主按钮 + 1 个页内 h1 | `复制本品查看`（主色）+ `刷新数据` + `<h1>推广经营看板</h1>` |
| market-ranking | 顶栏 6 个 + 页内多个 | 顶栏 `品类 / 时间预设 / 日期范围 / 刷新 / 导出` |
| data-center | 193 个可交互元素 | 见 4.6 |

products 那一行是典型的"能力清单式工具栏"：把 `经营/选款/投放/退款/生命周期` 五个业务视图、`日/周/月` 三个周期、`普通列表/周期视图` 两个形态、`字段/列设置/重置` 三个配置项平铺在同一视觉层级。NUI 的原则是"每个决策区一个主动作，其余降级"。

**建议**：把 `经营/选款/投放/退款/生命周期` 收成一个 segmented（主决策：看哪一类商品）；`日/周/月` 收进周期 segmented；`字段/列设置/重置` 收进一个"列设置"按钮的下拉。目标是把这一行从 16 个降到 ≤6 个。

### 4.6 长页面无收敛

| 页面 | 桌面高度 | ≈屏数 | 移动高度 | ≈屏数 |
|---|---:|---:|---:|---:|
| market-ranking | 5,743 | 6.4 | **11,051** | **13.1** |
| period-review | 3,661 | 4.1 | 7,687 | 9.1 |
| data-collection | 3,547 | 3.9 | 7,874 | 9.3 |
| new-products | 3,172 | 3.5 | – | – |
| rival-analysis | 2,994 | 3.3 | – | – |
| promotion | 2,823 | 3.1 | 5,488 | 6.5 |
| overview | 2,655 | 3.0 | 3,846 | 4.6 |
| lifecycle | 2,487 | 2.8 | 7,055 | 8.4 |
| products | 1,314 | 1.5 | 5,652 | 6.7 |

`market-ranking` 的 `main` 只有 6 个直接子块，但其中**一个 section 就 4,552px**（占整页 79%）——它是"类目排行 + 热卖趋势"把图表、双列列表、表格全塞进一个 section 的结果。`data-collection` 有一个 `ui-panel` 是 **2,169px**。

**建议**：给页面设"首屏必须给出结论、详情进抽屉或 Tab"的约束（这正是 `UI_OPTIMIZATION_IMPLEMENTATION_PLAN.md` 第 7 节已经写下的目标，但目前只有 promotion / period-review 部分做到）。具体到 market-ranking：把"热卖趋势"明细收进 Tab 或抽屉，首屏只留"类目对比 + 一个榜单 Top10"。

### 4.7 表格在 1440 宽屏下仍需横向滚动

| 页面 | 表格容器超出宽度 |
|---|---:|
| overview（日度经营矩阵） | 667px |
| period-review | 553px |
| products | 428px |
| lifecycle | 156px |
| new-products | 81px |

`overview` 的日度矩阵有 **14 列**、`data-center` 的导入批次表 **8 列 × 100 行**、`products` **12 列**。1440px 宽的屏幕还要横滚，说明列宽预算分配不合理——而与此同时商品名却被硬裁到 230–280px（见 4.8）。

**建议**：
1. 表格默认列数上限（如 ≤8 列），超出走"字段设置"（`ui-field-selector` 已有）；
2. 把"宽度按内容长度比例分配"改成"关键列固定宽 + 弹性列吃掉剩余"，NUI 项目记忆里已经踩过这个坑（`table-layout: auto` + `width:100%` 会把富余宽度按内容比例分给最长列）；
3. 横滚容器要有可见的滚动提示（`ui-table-wrap--discoverable` 已经有了，确认在 1440 下也生效）。

### 4.8 长商品名被硬裁 130–210px

实测 `overflow-x: hidden` 且内容明显超宽的容器（同一类元素重复出现）：

| 页面 | 元素 | 容器宽 | 内容宽 | 被裁 |
|---|---|---:|---:|---:|
| lifecycle | `.lifecycle-card__title` | 186px | 395px | **209px** |
| products | `.product-title__link` | 182px | 395px | **213px** |
| new-products | `.promotion-new-product__title` | 260px | 436px | 176px |
| period-review | `.pr-table__title-text` | 262px | 393px | 131px |
| overview | （无类名容器） | 190px | 428px | **238px** |

`products` 的 `.product-title__link` 有 `title` 属性 + `aria-label`（`pages/products/table-render.js:264-265`），鼠标悬停可看全——**这一点做得对**。但：

- `max-width` 是硬编码的 230 / 240 / 280px（`themes/product-domain.css:164, 833, 862`），在 1440px 屏幕上把 12 列的表挤到要横滚，同时把商品名裁掉 54%；
- `.product-title strong` 用 `-webkit-line-clamp: 2`（两行），而 `.product-title__link` 用 `white-space: nowrap`（一行）——两条规则打架，实际生效的是一行，`line-clamp` 是死代码；
- overview 那个 238px 被裁的容器**没有类名**，无法定位，需要排查。

**建议**：允许商品名两行（用回 `line-clamp: 2`，删掉 `nowrap`），并给商品列一个"占剩余空间"的弹性宽度，而不是固定 240px。

---

## 5. P2：密度、DOM 卫生与一致性

### 5.1 控件与 DOM 密度失衡

| 页面 | DOM 节点 | 可交互元素 | `.ui-button` 总/可见 | 徽标 总/可见 |
|---|---:|---:|---:|---:|
| **data-center** | **24,333** | **193** | **300 / 87** | 4 / 0 |
| **market-ranking** | **7,927** | 102 | 28 / 2 | **996 / 2** |
| **period-review** | 5,146 | 118 | **224 / 43** | 4 / 0 |
| rival-analysis | 3,609 | 35 | 17 / 0 | 7 / – |
| new-products | 2,249 | 81 | 97 / 31 | 5 / 0 |
| keyword-promotion | 2,050 | **157** | 30 / 5 | 4 / 0 |

两个最刺眼的：

**data-center = 24,333 个 DOM 节点。** 拆开看：`商品身份审核` 表 100 行、`导入批次` 表 100 行（还有 2 张 16/51 行的表），每行都带 1 个按钮；3 个 `ui-metric-grid` 共 12 张指标卡；7 个 `ui-table-wrap`。而且它有 **5 个纵向滚动容器**，其中 4 个是表格内滚：

```text
ui-table-wrap--discoverable  裁剪 975px  可视高 380px
ui-table-wrap                裁剪 975px  可视高 380px
ui-table-wrap--discoverable  裁剪 1496px 可视高 432px
ui-table-wrap--discoverable  裁剪 1083px 可视高 432px
```

于是这一页同时存在**三层滚动**：整页滚动 + 表格内滚 + 分页（每页 20 行）。截图里能看到"商品身份审核"表格最后一行被切掉一半。NUI 的非协商项第 6 条要求"关键图表值要有相邻的文字/表格/详情路径"，但没要求三层滚动。

**market-ranking = 996 个 `.ui-badge`，只有 2 个可见。** 隐藏位置分布：

```text
930 个藏在 <tr>（display:none）
 63 个藏在 section.ui-panel（隐藏面板）
  1 个藏在 dialog.toolbox-dialog
```

也就是说，这页把所有 Tab/榜单的内容一次性全渲染进 DOM，再靠 CSS 隐藏。7,927 个节点里有 7,000+ 是"当前不可见但已构建"的。

**period-review = 224 个 `.ui-button`（43 可见）**、5 个纵向滚动容器，DOM 5,146 节点。

**建议**：
- 表格分页改成"真分页"（只渲染当前页 20 行），现在 DOM 里有 100 行；
- Tab 内容改成按需渲染（切到才建 DOM），或至少 `content-visibility: auto`；
- 一个页面内不要出现"整页滚动 + 表格内滚 + 分页"三层，选两层。

### 5.2 组件建了但复用不均

`ui-components.js` 导出的组件在 22 页的实际使用：

| 组件 | 使用页面数 | 备注 |
|---|---:|---|
| `ui-context-bar` | 19 | 覆盖率最高，但内容各写各的（见 4.3） |
| `ui-page-header` | 19 | goals / component-catalog 各 2 个 |
| `ui-filter-toolbar` | 18 | **lifecycle 4 个、products 3 个、data-center 3 个、keyword-promotion 3 个** |
| `ui-metric-card` | 17 | |
| `ui-table-wrap` / `ui-data-table` | 19 | `TmallUI.audit()` 报了 2 处缺 wrap |
| `ui-table-toolbar` | 6 | reviews / products / lifecycle / keyword-promotion / promotion(×2) / new-products / rival-analysis / market-ranking / data-collection / data-center(×2) / compare |
| `ui-decision-card` | **1**（promotion） | 建了基本没用起来 |
| `ui-sticky-action-bar` | **2**（period-review、new-products） | |

**同一个"筛选栏"在一页里出现 3~4 次**，说明筛选没有统一入口，而是散在各个 section 里。这正是 `UI_OPTIMIZATION_IMPLEMENTATION_PLAN.md` Task 2 想解决的问题，但实测还没有收敛。

**建议**：
- 每页只允许**一个** `ui-table-toolbar`（搜索 + 核心筛选 + 更多筛选 + 字段设置 + 结果数 + 导出），页面级的范围筛选进 `ui-context-bar`；
- `ui-decision-card` 要么在 overview / period-review / promotion 三个决策页统一起用，要么删掉（只被 1 页用不符合"至少两个页面复用"的自定标准）。

### 5.3 内联样式与 CSS 体量

| 页面 | 内联样式元素数（含 color/background/border/font-size/margin/padding） |
|---|---:|
| keyword-promotion | **150** |
| market-ranking | **45** |
| data-collection | 13 |
| rival-analysis | 12 |
| promotion | 9 |
| flow-source | 7 |
| overview | 3 |
| category-dashboard | 3 |

`keyword-promotion` 的 150 处内联样式基本等于"这一页的样式没进 CSS"。这直接违反 NUI 的"使用语义 token，不散落硬编码视觉"。

CSS 侧：

| 文件 | 体积 | 硬编码颜色 | `var()` 引用 |
|---|---:|---:|---:|
| `components.css` | 120KB / 340 个类 | 0 | 1,080 |
| `shell.css` | 31KB | 0 | 407 |
| `period-review.css` | 55KB | **26** | 368 |
| `market-ranking.css` | 13KB | 2 | 103 |
| `themes/product-domain.css` | 1262 行 | – | – |
| `themes/*.css` 合计 | 2054 行 / 5 个文件 | – | – |

`period-review.css` 的 26 处硬编码颜色是唯一的 token 破口。`themes/` 目录 2054 行是"页面专属规则"的另一个家，与 `UI_OPTIMIZATION_IMPLEMENTATION_PLAN.md` 6.3 节"页面专属规则继续放在页面对应 CSS 中"的约定存在两套并存。

### 5.4 涨跌配色：大部分对，但有一处按方向而非按语义

`components.css`：

```css
.delta--positive { color: var(--success); }   /* 绿 */
.delta--negative { color: var(--danger); }    /* 红 */
.metric-card__meta.is-up { color: var(--success); }
.metric-card__meta.is-down { color: var(--danger); }
```

方向本身是"好=绿、坏=红"（业务看板语义，符合 NUI 的 "green = healthy / red = failure"）。

**关键是有没有按指标语义反转**。实测：

- ✅ `overview-live.js:232` 正确：`const trendClass = direction === 0 ? '' : ((direction > 0) !== isCostMetric ? 'is-up' : 'is-down');`——成本类指标（推广花费、费比）上升判为坏。
- ✅ `period-review-live.js:495`、`pages/period-review/metric-cards.js:83` 用 `good` 变量判断，方向正确。
- ⚠️ `pages/period-review/product-columns.js:169`：`rate < 0 ? 'is-down' : 'is-up'`；`:187`：`Number(value) < 0 ? 'is-down' : 'is-up'`——**只看正负，不看指标语义**。退款率、费比这类"越低越好"的指标在问题单品表里会被涂成绿色（表示"好"），实际是变差。

**建议**：把"指标方向"抽成一个共享的 `metricPolarity(metricKey)`（哪些是越低越好），所有配色走它，不要在页面里各写 `> 0 / < 0`。

### 5.5 可访问性

- **无名按钮 5 个**（overview）：`<button class="operations-center__calendar-day is-muted" disabled>`——计划日历里的空格子没有 `aria-label`，读屏只能念出"按钮"。这是唯一被检出的无名可交互元素，其余 21 页为 0，底子不错。
- **`focus-visible` 覆盖偏少**：`components.css` 4 处、`shell.css` 4 处。`product-title__link:focus-visible` 是写对的，但按钮/表格行/卡片这类可点元素的焦点态需要抽样验证。
- **颜色是唯一状态表达的地方**：`.delta--*`、`.ui-badge--*`、`.metric-card__meta.is-up/is-down` 都只有颜色。NUI 要求"状态不只依靠颜色表达"——至少要配 `↑/↓` 箭头或文字（`overview-live.js` 的趋势文本里已有趋势描述，确认徽标类也补上）。
- **对比度**：`--text-tertiary: #9ca3af` 在白底上对比度约 2.5:1，用于 12px 的 meta 文本时偏低。

### 5.6 死路由与死页面

| 路径 | 行为 | 页面文件 | 判定 |
|---|---|---|---|
| `/compare` | 302 → `/reviews` | `compare.html` 存在（72 行） | 死页面，建议删 |
| `/manage` | 302 → `/settings` | `manage.html` 存在（112 行） | 死页面，建议删 |
| `/product-detail` | **404** | `product-detail.html` 存在（317 行） | 见 P0-1 |
| `period-review-redesign.html` | 不可路由 | **2030 行** | 死页面（占了 pages 总行数的 36%） |

`pages/` 目录 23 个 HTML 共 5,599 行，其中 `period-review-redesign.html` 一个就 2,030 行且完全不可达。`compare.html` + `manage.html` 也是纯负担。

### 5.7 外部版本检查产生固定噪音

每个页面加载都会请求 `https://gitcode.com/api/v5/repos/owen891/tmall-dashboard/releases/latest`，被 CORS 拦截（`ERR_FAILED`），66 次加载里产生 **63 条**控制台错误。这是全项目最大宗的错误噪音，会淹没真实问题。

**建议**：改到后端代理（`/api/version` 已经存在，让它顺带返回最新版本），或至少捕获并静默。

---

## 6. 修复优先级与批次

严格按"先修 bug、再收层级、最后清密度"排。

### 批次 0：P0 缺陷（半天内可完成）

| # | 动作 | 文件 |
|---|---|---|
| 0-1 | `PAGE_DEFINITIONS` 补齐 8 个页面 | `services/page_capability_service.py` |
| 0-2 | `loadPageCapabilities` 失败不再静默 | `frontend/ui_demo/assets/api.js:195` |
| 0-3 | 删掉 goals 重复的页面头部 | `frontend/ui_demo/pages/goals.html:5` |
| 0-4 | `/product-detail` 路由补齐（或明确 302） | `app.py:301-313` |
| 0-5 | `availability` 语义拆分（not-created / no-data / error） | `api/api_response.py`、`services/*` |
| 0-6 | 版本检查改走后端代理 | `frontend/ui_demo/assets/version-check.js` + `app.py` |

### 批次 1：层级收敛（1~2 天）

| # | 动作 |
|---|---|
| 1-1 | 全局统一：每页有且仅有一个 `<h1>` = 页面标题；`pageHeader()` 改产 `<h1>`；`TmallUI.audit()` 加"唯一 h1"检查 |
| 1-2 | 导航分组标签 `h2` → `span`（`shell.js:254`） |
| 1-3 | 合并 `ui-page-header` + `ui-context-bar` 为一个 Orientation 区（目标：首屏 96px 内进入决策区）；删除 12 处 `ui-context-bar__meta` 说明文案 |
| 1-4 | `section-kicker` 只保留有真实步骤语义的（goals 三步、data-center 配置导入），其余删除 |
| 1-5 | promotion / new-products 页内 `<h1>` 降为 `<h2>` 区块标题 |
| 1-6 | 删除 `compare.html` / `manage.html` / `period-review-redesign.html` |

### 批次 2：首屏决策区（2~3 天）

| # | 动作 |
|---|---|
| 2-1 | overview：合并"决策区 + 4 KPI"，去掉"更多经营指标"折叠层，消除净销售额重复 3 次 |
| 2-2 | overview："异常与行动"作为第二决策区，与第一决策区在视觉上区分（不要同为白卡） |
| 2-3 | products：页头 16 控件 → ≤6（业务视图 segmented + 周期 segmented + 列设置菜单） |
| 2-4 | promotion：页头只留一个主操作 |
| 2-5 | market-ranking：首屏只留"类目对比 + Top10 榜单"，4552px 那个 section 拆开 |

### 批次 3：密度与表格（2~3 天）

| # | 动作 |
|---|---|
| 3-1 | 表格真分页（只渲染当前页行），data-center 从 24,333 节点降下来 |
| 3-2 | Tab 内容按需渲染；至少给隐藏面板加 `content-visibility: auto` |
| 3-3 | 表格列数上限 + 关键列固定宽；1440 下消除 overview(667px) / period-review(553px) / products(428px) 的横滚 |
| 3-4 | 商品名恢复两行（`line-clamp: 2`，删 `nowrap`），列宽改弹性 |
| 3-5 | 每页只允许一个 `ui-table-toolbar`；`ui-decision-card` 统一用或删 |
| 3-6 | 消除三层滚动（整页 + 内滚 + 分页），选两层 |

### 批次 4：一致性与无障碍（1~2 天）

| # | 动作 |
|---|---|
| 4-1 | `keyword-promotion` 150 处内联样式迁进 CSS；`period-review.css` 26 处硬编码颜色改 token |
| 4-2 | 抽 `metricPolarity()`，修 `product-columns.js` 的按方向配色 |
| 4-3 | 日历空格子补 `aria-label` |
| 4-4 | 状态补非颜色表达（箭头/文字），检查 `--text-tertiary` 对比度 |
| 4-5 | 补齐 `focus-visible` 到所有可交互元素 |

---

## 7. NUI 验收清单（改完后逐条核）

**含义与层级**
- [ ] 每页有且仅有一个 `<h1>`，就是页面标题
- [ ] 文档大纲里页面标题排第一（导航分组不再用标题标签）
- [ ] 首屏 96px 内进入决策区（无数据高度 ≤ 一个页头）
- [ ] 每页一个主要决策区；该区内一个主动作，其余降级
- [ ] 同一指标不在同页出现两次以上
- [ ] 每个图表标题是一个问题，不是一句描述

**数据**
- [ ] 真实 0 / 无记录 / 未创建 / 不可用 / 过期 / 部分 / 失败 七态可区分
- [ ] 金额、比例、数量都有单位；关键数字不依赖 hover
- [ ] 每页显示数据截止时间与来源

**视觉**
- [ ] 无硬编码颜色（含内联样式）
- [ ] 静态内容用间距和边框建立层级，不靠阴影
- [ ] 390 / 768 / 1280 / 1440 全部无横向溢出（当前已达标，改完需保持）
- [ ] 无内容被 `overflow:hidden` 静默裁掉（除刻意单行截断且带 title）
- [ ] 灰度下仍可读出状态

**交互与无障碍**
- [ ] 所有可交互元素有可访问名称
- [ ] 抽屉/弹窗焦点管理正确，Esc 可关
- [ ] 状态不只靠颜色
- [ ] 对比度达标

**工程**
- [ ] 路由、API、导出、计算、权限未被破坏
- [ ] 每页 DOM 节点数 < 8,000（data-center 从 24,333 降下来）
- [ ] 每页可交互元素 < 100
- [ ] 控制台无新增错误（gitcode 噪音清零）
- [ ] `TmallUI.audit()` 返回 0 问题

---

## 8. 与现有文档的关系

本次审计是 `docs/UI_OPTIMIZATION_NUI_REVIEW.md` 里**"批次 0：现状快照"**的正式交付——那份审查意见明确要求"禁止在没有快照的情况下直接重排页面"，本文就是那份快照。

三份文档的分工：

```text
UI_OPTIMIZATION_IMPLEMENTATION_PLAN.md   ← 方向（做什么）
UI_OPTIMIZATION_NUI_REVIEW.md            ← 对方向的审查（怎么改才对）
UI_LAYOUT_AUDIT_20261001.md（本文）      ← 现状证据（现在到底什么样）  ← 新增
```

审查意见里 8 条"必须修正"中有 6 条在实测中被证实是真实存在的（页面契约缺失、数据语义被压扁、图表表达无规则、token 映射不完整、响应式验收不具体、无障碍未纳入），2 条（"一个主要操作"过死、"数据中心不宜套队列"）本次实测未发现被误用——data-center 没有用队列布局，方向是对的。

**唯一需要修正审查意见的地方**：它建议的公共组件是 6 个，但 `ui-components.js` 实际已经导出 20+ 个，其中 `decisionCard`（1 页用）和 `stickyActionBar`（2 页用）不满足"至少两个页面复用"的自定标准。组件数量不是问题，**复用率才是**——建议改为"每个导出组件必须 ≥2 页使用，否则删"。

---

## 9. 附：审计产物

```text
scripts/audit_ui_layout.cjs     22 页 × 3 视口：溢出/卡片/标题/表格/控制台
scripts/audit_ui_deep.cjs       22 页 × 2 视口：接口 4xx/裁剪/横滚/组件使用/audit
scripts/audit_ui_dom.cjs        22 页 × 1440：DOM 节点/控件/徽标/卡片
scripts/probe_ui_density.cjs     7 页定点：控件密度/无名按钮/被裁表格/main 子块

.tmp/ui-audit/audit.json        第一遍原始数据
.tmp/ui-audit/deep.json         第二遍原始数据
.tmp/ui-audit/dom.json          第三遍原始数据
.tmp/ui-audit/shots/*.png       66 张全页截图（22 页 × 3 视口）
```
