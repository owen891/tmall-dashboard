# UI 优化方案（整改版）

> 版本：v1.0
> 日期：2026-10-01
> 依据：`docs/UI_LAYOUT_AUDIT_20261001.md`（22 页 × 3 视口实测）
> **落地状态：批次 0 ~ 4 共 31 项 + 追加批次 3 项（极性统一 / 语义色对比度 / 根目录归档）已全部处理完，验收结论见 `docs/UI_ACCEPTANCE_20261001.md`**
> 与既有文档的关系：`UI_OPTIMIZATION_IMPLEMENTATION_PLAN.md` 定方向，`UI_OPTIMIZATION_NUI_REVIEW.md` 审方向，**本方案把审计出来的问题拆成可执行、可验证、可回滚的批次**
> 原则：**先修 bug，再收层级，最后清密度**；每批独立上线、独立回滚

---

## 0. 怎么用这份方案

- 每个任务都带 **审计编号**（P0-x / P1-x / P2-x），可以直接回 `UI_LAYOUT_AUDIT_20261001.md` 查证据。
- 每个任务都带 **文件:行号**。没有行号的条目说明还没定位到实现层，不要开工。
- 每个批次结束都要跑 **第 7 节的验证命令**，拿数字和基线表（第 1 节）比对，不是靠肉眼看。
- **不做的事写在第 9 节**。这一轮最大的风险不是做得不够，而是顺手把指标口径和 340 个 CSS 类一起改了。

---

## 1. 目标与验收基线

| 指标 | 现状 | 目标 | 验证方式 |
|---|---|---|---|
| 横向溢出页面数（3 视口） | 0 | **保持 0** | `audit_ui_layout.cjs` |
| P0 缺陷 | 4 | 0 | 见批次 0 |
| 接口 4xx（22 页加载） | 8 页 422 + 2 个 404 | 0 | `audit_ui_deep.cjs` 的 `httpErrors` |
| 控制台错误 / 页 | 2~3 条 | 0 | `audit_ui_deep.cjs` 的 `consoleErrors` |
| 每页 `<h1>` 数量 | 0 或 2（18 页是 h2） | **恰好 1** | `audit_ui_deep.cjs` 的 `headings` |
| 首屏进入决策区 | 144px | ≤ 96px | `probe_ui_density.cjs` 的 `main` 子块高度 |
| 单页 DOM 节点峰值 | **24,333**（data-center） | < 8,000 | `audit_ui_dom.cjs` |
| 单页可交互元素峰值 | **193**（data-center） | < 100 | `audit_ui_dom.cjs` |
| 桌面页高峰值 | 5,743px（market-ranking） | < 3,000px | `audit_ui_layout.cjs` |
| 移动页高峰值 | 11,051px（market-ranking） | < 6,000px | `audit_ui_layout.cjs` |
| 1440 下需横滚的表格 | 5 页 | 0 | `audit_ui_deep.cjs` 的 `scrollers` |
| keyword-promotion 内联样式 | 150 | 0 | `audit_ui_deep.cjs` 的 `inlineStyled` |
| `TmallUI.audit()` 问题数 | 2 | 0 | `audit_ui_deep.cjs` 的 `auditIssues` |

**验收方式**：批次 3 完成后重跑三遍探针，逐格比对；不达标就不进下一批。

---

## 2. 批次 0：P0 缺陷（约半天）

> 这一批全是 bug，不含任何设计决策，可以先做、可以独立上线。

### 0-1 补齐页面能力注册表（P0-2）—— **4 处联动改，不是加 8 行那么简单**

**为什么不能只加 8 条**：`services/page_capability_service.py:269` 有一句硬断言

```python
if len(PAGE_DEFINITIONS) != 13:
    errors.append('expected thirteen page definitions')
```

`validate_registry()` 被 `build_page_catalog()`（:404）调用，而 `can_release = not registry['errors'] and ...`（:445）。所以只加页面不加断言，会直接把 `can_release` 打成 `False`，数据中心的能力地图会标红。

**要改的 4 处**：

| # | 位置 | 改法 |
|---|---|---|
| 1 | `services/page_capability_service.py:12-95` `PAGE_DEFINITIONS` | 补 8 条：`analysis` / `keyword-promotion` / `new-products` / `market-ranking` / `flow-source` / `rival-analysis` / `data-collection` / `catalog` |
| 2 | `services/page_capability_service.py:173-191` `_PAGE_TARGET_FILES` | 为这 8 页各补 `(page.html, xxx-live.js)`；**漏了会被 `_enrich_registry_metadata` 填成空元组，触发 `missing page metadata`** |
| 3 | `services/page_capability_service.py` `CAPABILITY_DEFINITIONS` | 为 8 页各补能力条目（每个 `capability_keys` 都要有对应定义），否则 :288 报 `unknown page capabilities` |
| 4 | `services/page_capability_service.py:269` | **把 `!= 13` 换成与 `app.py` 路由白名单的交叉校验** |
| 5 | `tests/test_page_capability_service.py:26-27` | 同步更新断言 |

第 4 处是**根治**，值得单独说。现在的写法是"数量必须等于 13"，这个数字和 `app.py:307` 的路由白名单是两份手工维护的清单，必然漂移。改成：

```python
# services/page_capability_service.py
# 由 app.py 的页面白名单推导，避免两处手工清单漂移
from app import APPLICATION_PAGES          # 见 0-1b：把 app.py:307 的集合提成模块级常量

registered = {item['key'] for item in PAGE_DEFINITIONS}
missing = sorted(APPLICATION_PAGES - registered - {'compare', 'manage'})
extra = sorted(registered - APPLICATION_PAGES)
if missing:
    errors.append(f'unregistered pages: {", ".join(missing)}')
if extra:
    errors.append(f'registered but not routable: {", ".join(extra)}')
```

**0-1b**：`app.py:307` 的白名单现在写在函数体里的 set 字面量，提成模块级常量 `APPLICATION_PAGES = frozenset({...})`，让注册表校验能引用它。（`compare`/`manage` 是 302 跳转页，从集合里排除。）

**验证**：
```bash
curl --noproxy '*' "http://127.0.0.1:5000/api/page-capabilities?page=analysis&category_mode=sock"   # 期望 200
./.venv/Scripts/python.exe -m pytest tests/test_page_capability_service.py -q
```

**风险**：`CAPABILITY_DEFINITIONS` 每条都要求 `mode` ∈ `CAPABILITY_MODES`、`support_level` ∈ `SUPPORT_LEVELS`、`data_domains` ⊆ `DOMAIN_DEFINITIONS`（:299-305）。新条目必须用已有枚举值，别自造。

---

### 0-2 能力门控失败不再静默（P0-2 配套）

`frontend/ui_demo/assets/api.js:195`

```js
loadPageCapabilities().catch(() => {});     // ← 静默吞掉，8 个页面的门控失效了没人知道
```

改成：

```js
loadPageCapabilities().catch((error) => {
  window.DemoApi.lastCapabilityError = { page: document.body?.dataset.page, message: error?.message || String(error) };
  console.warn('[tmall] page capabilities unavailable:', window.DemoApi.lastCapabilityError);
});
```

并把 `lastCapabilityError` 暴露给数据中心的「页面能力地图」（`assets/pages/data-center/capability-map.js`）标红。这样以后再漂移，页面上能看见。

**验证**：`audit_ui_deep.cjs` 里 `consoleErrors` 不再含 422，且 `data-center` 的能力地图没有异常标记。

---

### 0-3 删掉 goals 重复的页面头部（P0-3）

`frontend/ui_demo/pages/goals.html:5` —— 整行删除（与第 4 行完全重复）。

**验证**：`audit_ui_deep.cjs` 里 goals 的 `componentUse["ui-page-header"]` 从 2 变 1。

---

### 0-4 修 `/product-detail` 404（P0-1）

`app.py:307` 的白名单加 `'product-detail'`。

配套：`frontend/ui_demo/pages/product-detail.html` 在没有 `product_id` 时渲染空态而不是空白。`product-detail-live.js:799` 已有 `DemoApi.renderDataState(...)` 的用法，照抄：

```js
// product-detail-live.js 取数入口处
if (!id) {
  DemoApi.renderDataState($('[data-product-detail-status]'), 'no-data', {
    message: '请从商品列表进入详情',
    retry: null,
  });
  return;
}
```

**注意**：`/products/<product_id>`（`app.py:311`）仍然是正常入口，不用改；`/product-detail` 只是给无 id 的深链一个体面的落地页。

**验证**：
```bash
curl --noproxy '*' -o /dev/null -w "%{http_code}\n" http://127.0.0.1:5000/product-detail   # 期望 200
```

---

### 0-5 修 availability 语义（P0-4）—— **影响面比审计报告里写的大得多**

**先看实测**（审计时抓到的那个 422，可随时复现）：

```bash
curl --noproxy '*' "http://127.0.0.1:5000/api/overview"
# {"code":"VALIDATION_ERROR","message":"缺少参数 start","availability":"calculation-failed",
#  "evidence_level":"insufficient","limitations":["缺少参数 start"], ...}
```

一个纯粹的**参数缺失**，被报成「计算失败」。

**根因不在 `goals_api`，在 `api/api_response.py:91`** —— `failure()` 把 availability **硬编码**了，函数根本没有这个参数：

```python
def failure(code, message, details=None, status=400):
    return jsonify({
        ...
        'availability': 'calculation-failed',   # ← 硬编码
```

**全仓 252 个 `return failure(...)` 调用点，没有任何一个传过 `availability`**（实测 `grep -rn "failure(" api/ services/ | grep availability` 为空）。所以**整个应用的所有错误响应都自称「计算失败」**：

| code | 调用点数 | 语义上应该是什么 |
|---|---:|---|
| `VALIDATION_ERROR` | **131** | `missing-fields` |
| `NO_DATA` | 24 | `no-data` |
| `NOT_FOUND` | 24 | `no-data` |
| `UNSUPPORTED_SCOPE` | 8 | `missing-fields` |
| `CONFLICT` / `FORBIDDEN` / 其余 20 种 | 65 | 保持 `calculation-failed` / `source-unavailable` |

**同一个语义条件，仓库里已经有一处做对了** —— 都在 `api/goals_api.py`，相隔 40 行：

| 位置 | 场景 | 现状 | 前端看到 |
|---|---|---|---|
| `:73` `get_goals` | 该年度无目标 | `failure('NOT_FOUND', ...)` | ❌「计算失败」 |
| `:109-115` `goal_periods` | **完全同一条件** | `success(..., availability='no-data')` | ✅「暂无数据」 |

这不是"某个接口写错了"，是**错误响应的契约层漏了一个维度**。

**改法**（三步，缺一不可）：

1. **给 `failure()` 加参数**：`api/api_response.py:83` → `def failure(code, message, details=None, status=400, *, availability=None)`，`availability is None` 时走第 2 步。默认行为不变 → 252 个调用点零改动、零风险。
2. **加 `code → availability` 映射表**（根治）：
   ```python
   CODE_AVAILABILITY = {
       'NO_DATA': 'no-data', 'NOT_FOUND': 'no-data',
       'VALIDATION_ERROR': 'missing-fields', 'UNSUPPORTED_SCOPE': 'missing-fields',
       'DATA_CAPABILITY_ERROR': 'missing-fields',
       'ENVIRONMENT_ERROR': 'source-unavailable', 'FORBIDDEN': 'source-unavailable',
       'TOOL_NOT_AVAILABLE': 'source-unavailable',
   }
   # 未命中 → 保持 'calculation-failed'
   ```
   这一步一次性把 131 个 `VALIDATION_ERROR` 全部归位，是这批里**单位代码量收益最高的一处**。
3. **非法值降级加日志**：`api/api_response.py:58-59`（`success()` 里）同样有一处静默降级，两处都加 `current_app.logger.warning`。否则以后还会有人把 `calculation-failed` 当"万能兜底值"。

**前端不用改**：`frontend/ui_demo/assets/api.js:89` 的客户端白名单与服务端 `AVAILABILITY_VALUES`（`api_response.py:7-10`）**完全一致**，都是那 7 个值。修完服务端不会触发客户端降级。

**⚠️ 有一处前端行为会变，需手工确认**：`frontend/ui_demo/assets/operations-center.js:238-240`

```js
if (payload.availability !== 'available') {
  if (payload.availability !== 'no-data') state.sourceErrors = [...new Set([...state.sourceErrors, 'calendar'])];
  if (payload.availability === 'no-data') { ... }
}
```

运营中心**明确区分** `no-data` 与其他非 available 状态。日历接口的空月份响应现在被误判成"数据源错误"（进 `state.sourceErrors`），修完会变成正常的"暂无数据"。这是**修正**，但属于可见的行为变化 —— 改完手工点一遍运营中心日历，确认空月份表现符合预期。

**验证**：
```bash
curl --noproxy '*' "http://127.0.0.1:5000/api/goals/2026" | grep -o '"availability":"[^"]*"'   # 期望 no-data
curl --noproxy '*' "http://127.0.0.1:5000/api/overview" | grep -o '"availability":"[^"]*"'   # 期望 missing-fields
```


---

### 0-6 清掉版本检查噪音（P2-7）

`frontend/ui_demo/assets/version-check.js` 里对 `https://gitcode.com/api/v5/.../releases/latest` 的直接 fetch 改走后端代理——`GET /api/version`（`app.py:328`）已经存在，让它顺带返回最新版本。

这一条不修的话，后面每一轮验证都要在 63 条噪音里挑真问题。

**验证**：`audit_ui_layout.cjs` 的 `failedRequests` 里 gitcode 条目为 0。

---

## 3. 批次 1：层级收敛（1~2 天）

> 依赖：无。可与批次 0 并行（不同文件）。批次 2 依赖本批。

### 1-1 全局统一：每页有且仅有一个 `<h1>`（P1-1）

三个动作：

1. **组件层**：`frontend/ui_demo/assets/ui-components.js:156`
   ```js
   copy.append(create('h2', '', title));   // → create('h1', '', title)
   ```
2. **静态页面**：19 个页面的页面标题 `<h2>` → `<h1>`。逐个确认是"页面标题"那个，不是区块标题。
3. **降级两个页内 h1**：
   - `pages/promotion.html` 的 `<h1 id="promotionCommandTitle">推广经营看板</h1>` → `<h2>`
   - `pages/new-products.html` 的 `<h1 id="promotionNewConclusionTitle">新品投放经营看板</h1>` → `<h2>`
4. **`ui-components.js:audit()` 加规则**（:440 那个函数）：
   ```js
   if (document.querySelectorAll('h1').length !== 1) {
     issues.push({ node: document.body, message: `页面应有且仅有一个 h1，当前 ${document.querySelectorAll('h1').length} 个` });
   }
   ```
   这条规则会进 `TmallUI.audit()`，也就能被审计脚本自动抓到，防止回退。

**验证**：`audit_ui_deep.cjs` 每页 `headings` 里 h1 恰好 1 个。

### 1-2 导航分组标签降级（P1-2）

`frontend/ui_demo/assets/shell.js:254` 的模板串里 `<h2 class="demo-nav__label">${group.label}</h2>` → `<span class="demo-nav__label">${group.label}</span>`。

先确认 `shell.css` 里没有 `h2.demo-nav__label` 这类元素选择器（`grep -n "demo-nav__label" assets/shell.css`），只有类选择器的话改标签不影响样式。

**验证**：每页标题树的前 5 个节点不再是"店铺/商品/付费/市场/工具"。

### 1-3 合并页头与上下文栏（P1-3）

**现状**：`pages/overview.html:19-32` 是 52px 页头 + 92px 上下文栏，两块文案同义重复。

**改法**：
1. `ui-components.js:208` 的 `contextBar()` 保留（数据中心等页面还用），但把 19 个页面的 `ui-context-bar` 从页头正下方删掉，`value`（店铺 · 周期）合并进 `pageHeader()` 的一个新参数：
   ```js
   const pageHeader = ({ title, description = '', scope = '', actions = null } = {}) => {
     const node = create('header', 'ui-page-header');
     const copy = create('div', 'ui-page-header__copy');
     copy.append(create('h1', '', title));
     if (description) copy.append(create('p', '', description));
     if (scope) copy.append(create('span', 'ui-page-header__scope', scope));   // 店铺 · 周期 · 数据截止
     node.append(copy);
     if (actions) node.append(actions);
     return node;
   };
   ```
2. 删掉 12 处 `ui-context-bar__meta` 说明文案（"先…再…"那些）。它们是操作说明，不是数据。要留就进 `title` 属性或帮助浮层。
3. `data-center` 的 `ui-context-bar` 里"数据来源：店透视市场排行…"这类**元信息**保留，它是证据不是说明。

**验证**：`probe_ui_density.cjs` 里 overview 的 `main` 子块里 `ui-page-header` 高度 + 决策区 `top` ≤ 96px。

### 1-4 删不可路由的死页面（P2-6 的一部分）

只删 **`frontend/ui_demo/pages/period-review-redesign.html`**（2030 行，`app.py:307` 白名单里没有 `period-review-redesign`，完全不可达，零依赖）。

**`compare.html` / `manage.html` 本批不动**——删它们要连带改 `PAGE_DEFINITIONS`、`CAPABILITY_DEFINITIONS`、`_PAGE_TARGET_FILES` 三处注册表，放到批次 4 和 0-1 的注册表改造一起做，避免半途状态。

### 1-5 section-kicker 收敛（P1-3）

现状 18 处（`pages/data-center.html` 3 / `data-collection.html` 3 / `market-ranking.html` 4 / `new-products.html` 4 / `overview.html` 3 / `period-review.html` 1）。

**只保留有真实步骤语义的**：`goals.html` 的"第一步/第二步/第三步"、`data-center.html` 的"配置与导入"。其余（"先看经营判断" / "数据证据" / "运营协同" / "当前状态"）全删——它们和紧跟着的 `<h3>` 说的是同一件事。

---

## 4. 批次 2：首屏决策区（2~3 天）

> 依赖批次 1（页头结构变了才好挪控件）。

### 2-1 overview：合并决策区与 KPI（P1-4）

**现状**（`pages/overview.html:34-77`）：

```text
决策区 overview-decision (334px, 4 个指标 + 优先动作)
→ 4 张 KPI 卡 overview-v2-kpis (148px)
→ 折叠的 4 张次级 KPI overview-v2-secondary-kpis (40px)
→ sr-only 的补充指标
→ 图表区 (388px) → 运营中心 (809px) → 日度矩阵 (556px)
```

净销售额出现 **3 次**（决策区 `data-overview-summary="net_sales"` / KPI 卡 `data-overview-kpi="net_sales"` / 日度矩阵列），目标完成度 2 次。

**改法**：
- 4 张 KPI 卡（净销售额/支付金额/转化率/访客数）作为决策区的**支撑行**并入 `overview-decision`，不再单独成段；
- 删 `overview-v2-secondary-kpis` 折叠层（推广花费/ROI/退款率/费比 直接进决策区次级行）；
- 日度矩阵里的净销售额列**保留**（那是证据层，性质不同），KPI 卡里的那份去掉；
- 目标：首屏（900px 内）只剩「决策区 + 图表区顶部」。

### 2-2 overview：第二决策区做视觉区分（P1-4）

`operations-center`（"异常与行动"，809px）本质是第二个决策区，但现在和第一决策区一样是白底 `ui-panel`，视觉权重相同。

改：给 `operations-center__panel` 换成"左边框色条 + 无背景"或降低标题字号，让它明显是"待办"而不是"结论"。

### 2-3 products：页头 14 个控件 → ≤ 6（P1-5）

**现状**（`pages/products.html:24-40`）：

```text
当前视图(eyebrow)
  展示：普通列表 / 周期视图          (2)
  周期：日 / 周 / 月                 (3)
  粒度：data-products-timeline-limit (3 个 select)
  字段：经营 / 选款 / 投放 / 退款 / 生命周期 (5)
  列设置                             (1)
```

**改法**（按"页面方向 vs 数据集筛选"重新分配）：

| 控件 | 归属 | 理由 |
|---|---|---|
| 字段（经营/选款/投放/退款/生命周期） | **留页头**，改成 segmented | 这是"看哪一类商品"的页面方向 |
| 列设置 | **留页头** | 页面级配置 |
| 展示（普通列表/周期视图） | 移入**表格工具栏** | 属于数据呈现方式 |
| 周期（日/周/月）+ 粒度 | 移入**表格工具栏**，且只在"周期视图"下显示 | 属于数据集筛选 |

目标页头控件 ≤ 6。

**落地结果（2026-10-01）**：页头可见控件 **6**（字段 ×5 + 列设置），达到目标。

| 控件 | 落点 | 说明 |
|---|---|---|
| 字段 ×5 | `.ui-page-header .product-field-controls` | 唯一保留在页头的控件组 |
| 列设置 | 同上 | 页面级配置 |
| 展示 ×2 + 周期 ×3 + 粒度 ×3 | `.product-filters` 新增首行 `.product-view-switch`（`grid-column: 1 / -1`） | 表格工具栏「呈现方式」行 |
| 重置 | `.product-filters__actions`（更多筛选 / 当前页收藏 之后） | 语义上属筛选，与「筛选与排序」同区 |

**与原方案的一处偏差（有意）**：原文写「周期（日/周/月）+ 粒度…只在周期视图下显示」，但 `state.periodDimension` 在**列表视图也生效**（`products-live.js:340` 用它构造 `/api/products?dim=`），隐藏会砍掉真实能力。因此改为：**周期始终可见，只有粒度（3/6/12 期）保持"仅周期视图"**（原有行为）。这也更贴合该行自己的理由「属于数据集筛选」。

**验证**：`scripts/verify_products_header.cjs`（PASS）——1440/390 两档、列表/周期两视图，页头控件 6 / 1，工具栏 5 / 8，无横向溢出、无 pageerror；截图 `scripts/shot_products_header.cjs` → `.tmp/ui-audit/products-*.png`。

**顺带修的缓存问题**：`themes/product-domain.css` 之前在所有 22 个页面都是**无 `?v=`** 引用，而 `app.py:366` 给 CSS 打 7 天缓存 —— 改主题样式用户永远拿不到新版。已统一补 `?v=20261001a`。

### 2-4 promotion：单主操作（P1-5）

`pages/promotion.html` 页头现在有「复制本品查看」（主色）+「刷新数据」两个按钮，页内还有一个 `<h1>`。

改：保留「复制本品查看」为唯一主操作；「刷新数据」降为图标按钮（顶栏已有 `data-demo-refresh`，可直接删）；页内 h1 按 1-1 降为 h2。

### 2-5 market-ranking：拆掉 4552px 的 section（P1-6）

现状 `main` 只有 6 个直接子块，但其中一个 `market-section` 就是 4552px（占整页 79%），里面塞了图表 + 双列列表 + 表格。

改：首屏只留「类目对比 + Top10 榜单」，热卖趋势明细进 Tab 或抽屉（`ui-components.js` 的 `detailDrawer` 已有）。

**目标**：桌面页高从 5,743px 降到 < 3,000px；移动从 11,051px 降到 < 6,000px。

**落地结果（2026-10-01）**：达标。

实测（改前 → 改后）：

| 断点 | 改前 | 改后 | 目标 |
|---|---|---|---|
| 1440px | 4,253 | **2,352** | < 3,000 |
| 390px | 9,526 | **4,043** | < 6,000 |

改法：把 `market-entity-grid market-entity-lists`（桌面 1,885px / 移动 5,467px，是首屏唯一的大块）从 `data-market-panel="overview"` 里**整体搬到新 Tab `data-market-tab="trends"`「店铺/单品趋势」**，`overview` 只留类目对比 + 4 张图表 + 重叠店铺。

- Tab 顺序：市场总览 / **店铺/单品趋势** / 周期快照 / 商品机会 / 关键词机会 / 生意参谋证据。
- 不需要懒加载：`setMarketView()` 本来就只是切 `hidden`，趋势列表是纯 DOM + 内联 `viewBox` SVG（`sparklineSvg`），隐藏时渲染不会失真；实测切过去 20 行店铺 + 20 行单品都在，分页 `‹12…29›` 正常。
- 注意 `.market-entity-grid` 的 `display:grid` 写在本页内联 `<style>`（`market-ranking.html:44`），新面板用 `.market-section` 包一层，`[hidden]` 才能生效。

**验证**：`scripts/verify_market_ranking_tabs.cjs`（PASS）；分块高度探针 `scripts/probe_page_blocks.cjs`。

---

## 5. 批次 3：密度与表格（2~3 天）

> 依赖：无（可与批次 2 并行）。这批改的是数据量最大的几页，改完必须重跑三遍探针。

### 5-1 分页从"隐藏行"改成"只保留当前页 DOM"（P2-1）

**根因**：`frontend/ui_demo/assets/table-controls.js:258`

```js
row.hidden = index < (state.page - 1) * state.pageSize || index >= state.page * state.pageSize;
```

**所有行都建了 DOM，再靠 `hidden` 隐藏**。`PAGE_SIZES = [20, 50, 100, 200]`，而 data-center 的 `/api/imports` 返回全部 100 个批次（`api/imports_api.py:97` 的 `list_imports()` 没有 limit），于是 4 张表各 100 行 × 8 列 + 每行 1 个按钮 ≈ 24,333 个节点。

**改法（保守版优先）**：
1. **先做保守版**：给 `table-controls.js` 加"初始最多渲染 `pageSize × 2` 行"，超出部分进 detached 容器，翻页时按需 append。改动局限在 `updatePagination` / `rowsFor`，风险可控。
2. **再考虑彻底版**：`sortRows`（:181）改为操作 state 里保留的行数组而不是 tbody 顺序。

⚠️ **风险点**：`getStickyViewport` / `makeStickyHeader`（:267-287）依赖 tbody 行顺序和可见性，`sortRows` 也是。**排序 + 粘性表头 + 分页三者耦合**，必须一起验证。所以先上保守版，跑通再全量。

**验证**：`audit_ui_dom.cjs` 里 data-center 的 `allEl` 从 24,333 降到 < 8,000；`audit_ui_layout.cjs` 里表格排序/分页仍可用（手工点一遍）。

### 5-2 隐藏面板加 content-visibility（P2-1）

`market-ranking` 有 996 个 `.ui-badge`，其中 930 个藏在 `display:none` 的 `<tr>` 里、63 个藏在隐藏 `ui-panel` 里——**所有 Tab 内容一次性渲染再 CSS 隐藏**。

低风险第一步：给隐藏容器加
```css
.market-section[hidden], .ui-panel[hidden] { content-visibility: auto; contain-intrinsic-size: auto 600px; }
```
第二步再考虑改成"切 Tab 才建 DOM"。

#### 落地结果（2026-10-01）：**不采纳，前提不成立**

`[hidden]` 就是 `display: none`（而且本轮刚在 `components.css` 顶部加了 `[hidden] { display: none !important }` 兜底），
浏览器**本来就不为 display:none 的元素做布局和绘制**，再叠 `content-visibility` 不省任何东西 —— 空操作。

真正能省的只有"已显示但在视口外"的内容。实测（`.tmp/probe_perf.cjs`，1440×1000）：

| 页面 | 加之前 docH | 加之后 docH | 结论 |
|---|---:|---:|---|
| period-review | 4283 | **4659（+376）** | `auto 600px` 兜底估小了；该页 `.pr-section` 实际高度在 300~2500px 之间，首帧必然少算 → **滚动条跳动** |
| data-center | 3904 | 3904 | 高度不变，但 DCL 无可测改善（76~159ms 噪声区间） |
| rival-analysis | 3018 | 3018 | 同上 |

净效果是「有跳动、无收益」，故**不加**（改动已回退，docH 复原）。

**P2-1 的目标实际由别处达成**：
- 5-1：data-center 节点 **24,333 → 2,775**（分页只保留当前页 DOM + 下拉懒填充）
- 2-5：market-ranking badge **996 → 126**（趋势榜整块搬进独立 Tab）

如果将来仍要压首屏成本，正确的方向是方案里的**第二步**（切 Tab 才建 DOM），而不是给 `[hidden]` 加 `content-visibility`。

### 5-3 表格列预算（P1-7）

| 页面 | 超宽 | 处理 |
|---|---:|---|
| overview 日度矩阵 | 667px（14 列） | 默认显示 8 列，其余走字段设置（`ui-field-selector` 已有） |
| period-review | 553px | 列宽收紧 + 默认隐藏低频列 |
| products | 428px | 见 5-4 |
| lifecycle | 156px | 列宽收紧 |
| new-products | 81px | 列宽收紧 |

原则：关键列给 `<th>` 显式 `width`，弹性列吃剩余。项目记忆里已经踩过——`table-layout: auto` + `width:100%` 会把富余宽度按内容长度比例分给最长列。

#### 落地结果（2026-10-01，桌面 1440px）

探针：`scripts/probe_table_overflow.cjs`（报每张 `table.ui-data-table` 的 表宽 / 容器宽 / 溢出 + 逐列宽）；
窄容器里的表格用 `.tmp/probe_scroll.cjs`（报所有 `overflow-x` 容器的溢出）+ `.tmp/probe_ancestors.cjs`（追祖先链宽度）。

| 页面 / 表 | 基线溢出 | 现在 | 做法 |
|---|---:|---:|---|
| overview 日度矩阵 | 667px（14 列） | **0** | 默认列 14 → 8（`DEFAULT_MATRIX_COLUMNS`），localStorage key `-v2` → `-v3`（不换 key 老用户存的 14 列不会让新默认生效）；`.overview-home-matrix .ui-data-table` `min-width` 1120 → 960 |
| period-review 货品表 ×2 | 553px | **0** | 见下（不是列宽问题） |
| products 商品列表 | 428px | **158px** | 指标列 120 → 96、表头放行换行（nowrap 来自 `.table-sort-button`）、`.product-table` `min-width` 1280 → 1080 |
| lifecycle 生命周期评估 | 156px | **0** | 放行「商品」「判断依据」两列换行 + 六列显式百分比 |
| new-products 新品投放明细 | 81px | **0** | 放行换行 + `.promotion-new-product__title` `max-width` 260 → 190 |
| keyword-promotion 推广商品列表 | 346px | **0** | 复用 `.product-table` 但无列宽规则，纯内容定宽；放行换行即回到容器内 |
| data-center 商品身份审核 | 155px | **0** | 放行换行 + `table-layout: fixed` + 八列百分比（「审核原因」是 `<input>`，固有尺寸会把列顶到 225px，auto 布局压不下来） |
| data-center 导入批次 | 97px | **0** | 同上（放行换行） |
| data-center 数据能力地图 | 460px | **0** | `.data-capability-table` 放行换行 + 八列百分比，`min-width` 1180 → 780 |

**根因统一**：全局 `.ui-data-table td { white-space: nowrap }`（`components.css:194`）+ `table-layout: auto`，
让「多行堆叠 / 长文本 / 列表」型单元格按 **max-content** 决定列宽，整表被撑出容器。
凡是文本型表格，放行换行 + 给 `<th>` 显式预算即可；数值型密集表（products）才需要真压列宽。

**period-review 的 553px 不是列宽问题**：两张 963px 的货品表原本落在 `550px` 的两列网格里，
被 `panel__body → subsections → subsection → details → materials` 五层内边距一路收到 **410px**，
即使把默认列砍到 3 列也放不下（132+260+110=502 > 410）。
按本文件既有先例（`[data-pr-product-analysis] > .pr-analysis-panel:first-child`、
`[data-pr-workbench-panel="reference"] .pr-analysis-grid`）把宽表所在区块改成通栏：

```css
[data-pr-sections] > .pr-section[data-section-key="goods"] { grid-column: 1 / -1; }
/* 通栏后 .pr-subsections 的 auto-fit 会自己拆成 4 列（每列 268px），反而更窄 —— 强制单列 */
[data-pr-sections] > .pr-section[data-section-key="goods"] .pr-subsections { grid-template-columns: minmax(0, 1fr); }
```

改完容器 976px，表 976px，**溢出 0**。附带修了 `.pr-section__title` 被 `.panel__title` 的
`max-width: var(--title-width-lg)`（360px）截掉 40~46px 的问题（`max-width: none`）。

**有意偏差**：
- **products 保留 158px 横向滚动**（基线 428px，降 63%）。这张表 12 列 + 首列 `position: sticky`
  是**为横向滚动设计的**（`product-domain.css:43-51` 有 sticky select/star/title），压到 0 需要每列 ≤80px，
  「1,234,567.89」放不下。用户可切「字段模板」收窄。
- **period-review 的 `.pr-table__title-text`**（`max-width: 262px` + ellipsis + tooltip）是**设计内截断**，
  不是溢出缺陷，不动。

### 5-4 商品名恢复两行（P1-8）

`frontend/ui_demo/assets/themes/product-domain.css:164`

```css
.product-title__link { max-width: 240px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; ... }
```

改成两行 + 去掉固定 max-width：

```css
.product-title__link {
  min-width: 0; overflow: hidden; text-align: left;
  display: -webkit-box; -webkit-box-orient: vertical; -webkit-line-clamp: 2;
  overflow-wrap: anywhere;
}
```

同时删掉 `.product-title strong`（:163）的 `line-clamp: 2` —— 两条规则打架，`__link` 是实际渲染的那个。

`title` 属性和 `aria-label` 已经在 `pages/products/table-render.js:264-265` 写好了，不用动。

### 5-5 每页只留一个筛选工具栏（P2-2）

`ui-filter-toolbar` 现在：lifecycle **4 个**、products / data-center / keyword-promotion 各 3 个、market-ranking / rival-analysis / compare / creative-board 各 2 个。

改：每页只保留一个 `ui-table-toolbar`（搜索 + 核心筛选 + 更多筛选 + 字段设置 + 结果数 + 导出），页面级的范围筛选进 `ui-page-header__scope`。section 级的筛选收进各自的 section 标题右侧的"更多筛选"。

#### 落地结果（2026-10-01）：**前提不成立，不改**

探针：`.tmp/probe_toolbars.cjs`（宽口径，复现方案里的计数）、`.tmp/probe_filterbars.cjs`（收紧口径：只算**可见且含 input/select** 的筛选栏）。

按宽口径复现方案的数字，然后逐个查它们是什么：

| 页面 | 宽口径计数 | 逐个拆开 |
|---|---:|---|
| products | 3 | `product-filters`（真筛选栏，12 个 input）+ `table-controls`（**分页条**，含每页条数 select）+ `toolbox-import-actions`（**共享隐藏 toolbox**，h=0） |
| lifecycle | 4 | `lifecycle-list__toolbar`（卡片列表筛选）+ `table-controls`（**卡片列表分页**）+ `lifecycle-assessment-pagination`（**评估表分页**）+ 共享 toolbox |
| data-center | 3 | `数据能力地图` 筛选栏 + `页面能力地图` 筛选栏 + 共享 toolbox |
| keyword-promotion / rival-analysis / compare / creative-board / new-products | 2~3 | 同上：1 个真筛选栏 + 分页条 + 共享 toolbox |

**两个计数虚高来源**：
1. **`toolbox-import-actions` 是全站共享、默认隐藏在 `<details>` 里的「导入经营数据」面板**（h=0，14 个页面每页都有 1 个）。宽口径把它算成页面自己的工具栏，直接把绝大多数页面从 1 顶到 2。
2. **`table-controls` / `*-pagination` 是分页条，不是筛选栏**（只有每页条数一个 select）。

收紧口径（可见 + 含 input/select + 排除分页）后的真实结果：

| 页面 | 真筛选栏 | 说明 |
|---|---:|---|
| overview / period-review / promotion / market-ranking / goals / settings | 0 | 筛选在页头 `demo-period` / 共享顶栏，不占表格工具栏 |
| products / keyword-promotion | 1 | `product-filters`（分页条不计） |
| lifecycle | 1 | `lifecycle-list__toolbar`（卡片列表）；评估表自己的 `lifecycle-assessment-toolbar` 缺 `ui-filter-toolbar` 类，宽口径漏算 |
| new-products / rival-analysis / compare / creative-board | 1 | 各自唯一 |
| **data-center** | **2** | `数据能力地图` 与 `页面能力地图`，**属于两张不同的表**，且在默认折叠的「数据治理与能力说明」里；两者筛选语义不同（数据域 vs 页面），合并反而更难用 |

**结论**：没有任何页面存在「同一数据区叠了两个冗余筛选栏」。方案里"lifecycle 4 个 / products 3 个"是**口径把分页条和共享隐藏 toolbox 算进去了**。
唯一有 2 个筛选栏的 data-center 属于两个不同面板，保留。

顺带确认「页面级范围筛选是否与工具栏重复」：products / keyword-promotion 的页头是「店铺 + 日期 + 分类」，工具栏是「搜索 + 分层/标签 + 状态 + 排序」，**职责不重叠**，不需要下沉到 `ui-page-header__scope`。

> 若将来真要收敛，方向是给共享的「导入经营数据」toolbox 加 `data-shared-toolbox` 之类的标记，
> 让审计脚本能排除它，而不是改页面结构。

### 5-6 消除三层滚动（P2-1）

`data-center` 同时有：整页滚动 + 4 个表格内滚（裁剪 975 / 975 / 1496 / 1083px）+ 分页（每页 20 行）。

改：去掉表格内滚（`max-height` + `overflow-y`），只保留"整页滚动 + 分页"两层。

---

## 6. 批次 4：一致性与无障碍（1~2 天）

> 依赖批次 0（注册表改造完成后才能安全删 compare/manage）。

| # | 任务 | 位置 | 审计编号 |
|---|---|---|---|
| 4-1 | keyword-promotion 的 150 处内联样式迁进 CSS | `assets/keyword-promotion.css` | P2-3 |
| 4-2 | `period-review.css` 的 26 处硬编码颜色改 token | `assets/period-review.css` | P2-3 |
| 4-3 | 抽 `metricPolarity(metricKey)`，所有涨跌配色走它 | 新增 `assets/metric-polarity.js`，改 `pages/period-review/product-columns.js:169,187` | P2-4 |
| 4-4 | 日历空格子补 `aria-label` | `assets/operations-center.js` 的 `operations-center__calendar-day` | P2-5 |
| 4-5 | 补齐 `focus-visible` | `components.css` / `themes/*.css` | P2-5 |
| 4-6 | 状态补非颜色表达（箭头/文字） | `.delta--*` / `.ui-badge--*` / `.metric-card__meta.is-up/down` | P2-5 |
| 4-7 | 复核 `--text-tertiary` (#9ca3af) 对比度，12px meta 文本改用 `--text-secondary` | `tokens.css:84` | P2-5 |
| 4-8 | 删 `compare.html` / `manage.html` + 清理注册表三处引用 | `pages/`、`PAGE_DEFINITIONS`、`CAPABILITY_DEFINITIONS`、`_PAGE_TARGET_FILES`、`app.py:303-306` | P2-6 |
| 4-9 | `ui-decision-card` 统一用或删（现在只有 promotion 用） | `ui-components.js` | P2-2 |

4-8 的顺序很重要：**先删注册表条目 → 跑测试确认 → 再删 HTML 文件**。反过来会出现"注册表指向不存在的文件"。

### 批次 4 落地结果（2026-10-01）

9 项全部处理完：8 项按方案改，1 项（4-9）判定为「删」。

| # | 任务 | 结果 | 验证 |
|---|---|---|---|
| 4-1 | keyword-promotion 150 处内联样式迁进 CSS | **150 → 0** | `.tmp/probe_inline.cjs` 复测 |
| 4-2 | `period-review.css` 26 处硬编码颜色改 token | **26 → 0** | `.tmp/fix_pr_colors.py`（幂等，18 条规则） |
| 4-3 | 抽 `metricPolarity(metricKey)` | 新建 `assets/metric-polarity.js`，接入 **8 处**调用点 | `scripts/verify_metric_polarity.cjs` **PASS 4/4** |
| 4-4 | 日历空格子补 `aria-label` | **5 个无名按钮 → 0** | `.tmp/probe_focus.cjs`；`validate_ui_demos.cjs` 已加断言 |
| 4-5 | 补齐 `focus-visible` | period-review **18 个 textarea 无焦点环 → 0**；13 页全 0 | `.tmp/probe_focus.cjs`（真实按 Tab 遍历） |
| 4-6 | 状态补非颜色表达 | **4 个纯颜色指示器 → 0** | `.tmp/probe_state3.cjs` |
| 4-7 | 复核 `--text-tertiary` 对比度 | tertiary 文本节点 **113 → 56**（余 42 个是禁用态，WCAG 1.4.3 豁免） | `.tmp/probe_contrast.cjs` |
| 4-8 | 删 compare/manage + 清注册表三处 | 注册表三处已清 + 4 个文件删除 | `page_count 22→20`、`conditional 47→43`、`registry_errors: []` |
| 4-9 | `ui-decision-card` 统一用或删 | **删**（工厂 0 调用点） | 全仓库 grep 无调用点 |

#### 逐项说明

**4-1（P2-3）** 150 处不是 150 种样式，是 **3 组 × 50 行**（`img` 缩略图 / `code` 货号 / `a` 标题链接）。在 `keyword-promotion.css` 追加 `.kp-thumb` / `.kp-thumb--empty` / `.kp-title-link` / `.kp-pid` / `.kp-error` 五个类，改 `keyword-promotion-live.js` 三处 `case` 与一处错误分支。`<th style="min-width:…">` **保留** —— 那是 45 列的列宽数据，不是视觉样式，搬进 CSS 等于把同一份数字维护两遍，且不在审计口径内。
顺手修掉两个**不存在的 token**：`--surface-2`（→ `--surface-muted`）。

**4-2（P2-3）** 与方案数字完全吻合。逐条查上下文后发现多数是 `var(--token, #fallback)` 的**冗余回退**，且 `--surface-default` 这个 token **根本不存在**（`#fff` 一直在生效）。改为 `var(--surface-base)`；`#3b82f6`/`#b45309`/`#d97706`/`#16a34a`/`#dc2626` 等 fallback 与真实 token 值不一致，一并去掉；6 处矩阵行状态色 `rgba(...)` → `color-mix(in srgb, var(--success|--warning|--danger) N%, transparent)`，顺带修掉暗色模式不跟随。

**4-3（P2-4）** 改造前全站有 **7 处各自为政**的极性逻辑（`overview-live.js` 的 `isCostMetric` 硬编码、`metric-cards.js` 的 `lowerBetter`、`period-review-live.js` 的 `item.lower_better`、`gap-attribution.js` 与 `leaf-board.js` 的「正=绿」、`product-columns.js` 只看正负）。新模块 `assets/metric-polarity.js` 挂 `window.MetricPolarity`，导出 `isLowerBetter / isGood / deltaClass`，支持 `lowerBetter` 显式覆盖与 `deadBand` 阈值。**接入过程中修掉一个真实误色**：`leaf-board.js` 的 `deltaBadge`/`ppBadge` 原来只看正负，推广花费涨、费比涨会被涂成绿色。

- ⚠️ **发现一处口径矛盾，未擅自改**：`ad_spend` 在 `services/period_matrix.py:MATRIX_METRICS` 标 `lower_better=False`（涨=绿），但 `overview-live.js` 一直当成本处理（涨=红），`period_context.TARGET_METRICS` 里推广费也是 `rate_better='low'`。**同一指标两页配色相反**。实现按「显式标志优先 + 模块表兜底」，并在 `metric-polarity.js` 头部注释里记录，待业务确认后统一。

**4-4（P2-5）** 月初/月末的补位格子是 `<button disabled>` 且**既无文本也无 aria-label**，读屏只能念出「按钮」。补上名称 + `aria-hidden`（纯视觉占位，对读屏没有信息量，避免一周里连播 6 个）。同时给真实日期格子补完整名称（`2026-10-01，3 项运营动作`）—— 原来只读一个「1」脱离上下文没有意义。

**4-5（P2-5）** 用**真实 Tab 键**遍历（程序化 `el.focus()` 不会让 button 命中 `:focus-visible`，必须真按）。13 页里唯一失败的是 period-review：**18 个 textarea 全部 `outline 0px/none`**。根因是本文件 4 处 `:focus { outline: none }`（`.pr-subsection textarea` / `.pr-field input+select` / `.pr-action-field input+textarea` / `.pr-input textarea`）—— 原意是「鼠标点进来不要焦点环」，但特异性 0,2,1 **压过了**全局 `textarea:focus-visible`（components.css:200，0,1,1），把键盘焦点环一起关掉了。修法：保留 `:focus` 的 `outline:none`，在文件**末尾**补 `:focus-visible` 还原（与那些 `:focus` 规则特异性相同，靠源码顺序取胜）。改完 13 页缺焦点环元素 **0**。

**4-6（P2-5）** 先扫「方向类」元素（`is-up`/`is-down`/`delta--*`）：**61 个全部已带 `+`/`−` 符号或 `↑`/`↓` 箭头**（`overview-live.js:247` 本来就用箭头），`.ui-badge--*` 也都承载文字 —— **这部分前提不成立**。真正「无文本 / 无 aria / 无图标、只靠颜色」的只有 **4 个 `.pr-metric-card__status-dot`**（7×7 圆点，period-review 的完成率卡）。改为「圆点 + 文字」：`达标` / `临界` / `未达标`，圆点降级为装饰。改完纯颜色指示器 **0**。

**4-7（P2-5）** 先算真实对比度：`--text-tertiary`（`#9ca3af`）在白底 **2.54:1**、在 `--surface-muted` 上 **2.31:1**，远低于 AA 的 4.5:1。实测 13 页共 **113 个** tertiary 文本节点**全部未过 AA**（其中 65 个是侧边栏导航标签）。
改法：`color: var(--text-tertiary)` 中**承载文本**的 **48 条**声明改为 `--text-secondary`（`#6b7280`，白底 4.83:1）；**保留 10 条** —— 禁用态（`:disabled` / `.is-muted`，1.4.3 明确豁免「非活动的用户界面组件」）、纯装饰图标（大号空态图标、搜索框内图标、版本弹窗箭头）、排序字形 `.table-sort-button__icon`（列头已有文字标签，加深会给每一列都加噪声）、`::after` 装饰箭头。另修 `.pr-material__empty` 的 `--text-soft`（`--text-tertiary` 的别名，全站唯一一处用法）。
结果：**113 → 56**，剩余 56 个里 **42 个是禁用态按钮**（豁免），另有 7 个 `.pr-material__empty` 与 7 个匿名节点在改 `--text-soft` 后归零。

- ⚠️ **顺带发现一个更大的系统性问题，本轮未改**：全站文本对比度审计（`scripts/audit_ui_contrast.cjs`）显示，**语义色本身就不达标** —— `--success`(#10b981) 在白底 2.54:1、在 `--success-tint` 上 2.41:1；`--warning`(#f59e0b) 1.95~2.15:1；`--brand`(#6366f1) 4.47:1、在 `--brand-tint` 上 3.99:1。受影响的是全部 `ui-badge--success/warning`、`.pr-status-tag`、`.pr-delta.is-up`、`.metric-card__meta` 等。**修它等于改主色/语义色，第 9 节明确不做**，因此只记录不改，待单独一轮决策（可行方向：拆出 `--success-text` 之类的「文字专用深色」token，背景/图表继续用 `--success`）。

**4-8（P2-6）** 严格按方案顺序：**先删注册表条目 → 跑测试 → 再删文件**。
- 注册表：`services/page_capability_service.py` 四处删除（`PAGE_DEFINITIONS` 的 compare/manage、`CAPABILITY_DEFINITIONS` 的 `compare.view`/`compare.export`/`manage.view`/`manage.schedule`、`SURFACE_DEFINITIONS` 的 `manage.schedule`、`_PAGE_TARGET_FILES` 的两条）。实测 `page_count 22 → 20`、`conditional 47 → 43`、`registry_errors: []`。
- `services/application_pages.py:53-54` 的 `LEGACY_REDIRECT_PAGES` **保留**，`/compare` → `/reviews`、`/manage` → `/settings` 仍是 302，旧书签不会 404（实测确认）。
- 删除 4 个文件：`pages/compare.html`、`pages/manage.html`、`assets/compare-live.js`、`assets/manage-live.js`。
- 连带更新：`scripts/validate_ui_demos.cjs`（摘掉 compare 断言、删 `compare-live.js` 的 date-range 循环）、`tests/test_frontend_prd_contract.py`（4 处）、三个审计探针与 `build_ui_audit_report.py` 的页面清单（22 → 19，否则会拿 404 空页面参与峰值统计）。
- ⚠️ **一个必须知情的代价**：`manage.html` 不只是「死路由」，它是**「管理任务 / 用户KPI / 日志」的唯一 UI**（`/api/manage/tasks`、`/api/manage/kpis`）。`settings.html` 只覆盖了「文件夹扫描」（而且是超集：除 `/run` 外还有 `/runs`、`/files`、`/files/<id>/retry`、`/delete`）。判定为可删的依据是：**`task_items` / `user_kpis` / `scheduled_tasks` 三张表实测全为 0 行**、不在导航里、`/manage` 302。后端 `api/manage_api.py` 与三张表**未动**，文件可从 git 恢复。若将来要用这两个功能，需要重新做 UI。

**4-9（P2-2）** 判定为**删**：`decisionCard` 工厂**没有任何调用点**（全仓库 grep 只有定义处与 `export` 列表），唯一「使用」是 `promotion.html` 的 `<article class="ui-decision-card promotion-decision-card">`，而 `promotion-views.css` 立刻用 `.promotion-decision-card.ui-decision-card { padding:0; border:0; background:transparent }` 把组件样式**全部覆盖掉** —— 等于挂了个类名却不用组件。按仓库自定标准「新组件必须 ≥2 页复用才能进 `ui-components.js`」，删掉工厂 + CSS 块 + promotion 上的类名 + 那条覆盖规则。

#### 批次 4 顺带修掉的真 bug

**1) `[hidden]` 静默失效**（在 5-2 排查时发现，影响 ≥3 页）：作者样式里的 `display`（`.ui-button{inline-flex}`、`section{grid}`、`.pr-field{flex}`…）特异性都高于 UA 的 `[hidden]{display:none}`，于是 `hidden` 属性被静默压掉。实测 `products` 的「清除分群」按钮在 `rule-board.js:145` 已设 `clear.hidden = true` 的情况下**依然可见**（78×40）。修法：`components.css` 顶部加 `[hidden] { display: none !important; }`（全站现有 27 条 `[hidden]` 规则清一色 `display:none`，含 1 条 `!important`，不会误伤）。修完全站 hidden 失效元素归零。

**2) `shell.js` 动态加载的资源版本号没跟着改**（全量回归时由 `test_update_notifications_ui` 暴露）：`shell.js:93,96` 用 `?v=20261001a` 动态加载 `table-controls.js` 与 `version-check.js`，而这两个文件本轮**都被改过**（+81 / +10 行）—— `?v=` 不变就意味着浏览器 7 天缓存里继续用旧版本，改了等于没改。统一提到 `?v=20261001g`。
顺带把该测试的断言从字面量 `"new URL('version-check.js', assetBase)"` 改成 `re.search(r"new URL\('version-check\.js(?:\?[^']*)?', assetBase\)", shell)` —— 契约是「用 `new URL(name, assetBase)` 加载这两个脚本」，带不带缓存串是实现细节，写死字面量会让每次 bump 都误报。

**3) 审计里 3 处「数据表缺少 ui-table-wrap 容器」**：`market-ranking.html:204,224` 的 `.market-entity-table-wrap` 与 `product-detail.html:246` 的 `.drill-modal__table-wrap` 都是页面内联自定义 wrapper（自己写了 `overflow-x/overflow-y:auto`），没挂共享的 `.ui-table-wrap` 类，于是 `TmallUI.audit()`（`ui-components.js:456` 用 `closest('.ui-table-wrap')`）判定失败。两个类**完全兼容**（`.ui-table-wrap{max-width:100%;overflow-x:auto}`，页面里已有 `ui-table-wrap sycm-item-rank-wrap` 的混用先例），直接补上类名即可。补完 `TmallUI.audit()` 问题数 **5 → 0**，基线 6/11。

**4) `components.css` 里 18 条指向已删除 `compare` 页面的死选择器**：4-8 删了页面、清了注册表，但漏了 CSS —— 8 个逗号选择器列表的最后一项 + 10 条独立规则（移动端整块 533-545、1490s 的 sticky 表头块）。
清理脚本（`.tmp/clean_compare_css.py`）踩了两个坑，都写进注释了：① `re.sub` **不重叠扫描**，模式若把「前导换行」一起吃掉，紧挨着的下一条规则就找不到前导换行而被跳过（表现为**隔一条删一条**）→ 改用 `(?<=\n)` 后顾断言；② 本文件是**纯 CRLF**，`read_text` 归一成 `\n`、`write_text` 再转回 `os.linesep`，两者抵消，不会把整文件行尾改掉。
删完断言：18 条全删、零残留、花括号配平 919→**908**、无悬空逗号（`,\s*\n\s*\{`）。重跑三遍探针**数字与清理前完全一致**，证明这 18 条确实是语义惰性的。

#### 批次 4 的验证

```bash
NODE_PATH=E:/www/tmall-dashboard/desktop/node_modules node scripts/audit_ui_dom.cjs
NODE_PATH=E:/www/tmall-dashboard/desktop/node_modules node scripts/audit_ui_layout.cjs
NODE_PATH=E:/www/tmall-dashboard/desktop/node_modules node scripts/audit_ui_deep.cjs
NODE_PATH=E:/www/tmall-dashboard/desktop/node_modules node scripts/check_ui_baseline.cjs   # ← 新增，见第 8 节
```

`check_ui_baseline.cjs` 把第 1 节的基线写成脚本，输出 PASS/FAIL（退出码 1 = 有未达标）。批次 4 后：**6/11 达标**（批次 4 前是 3/11、批次 4 首轮 5/11，最后一项是收尾清掉 3 处未挂 `.ui-table-wrap` 的 wrapper 后 `TmallUI.audit()` 归零拿到的），且**未达标项没有一项属于批次 4 范围**（逐条归因见验收报告 `docs/UI_ACCEPTANCE_20261001.md`）。

**版本号**：本轮改了 12 个 CSS + 9 个 JS，且历史上相当一部分引用（`tokens.css`、`analysis.css`、`navigation.js`…）**根本没带 `?v=`**，逐个手改容易漏。统一刷了一遍：`pages/*.html` 里 **380 处** `../assets/*.css|js` 引用 + `shell.js` 里 2 处动态加载串，全部 → `?v=20261001g`（会话中途曾到 `f`，因 `shell.js` 在 bump 之后又被改过一次，最终统一提到 `g`），校验后无漏版本引用、无 `f` 残留。

---

### 追加批次（2026-10-01 晚，3 项）

批次 4 收尾时验收报告留了 3 个「建议单独一轮」的遗留项，当轮直接做完了。版本号再 bump 一次：`?v=20261001g` → **`?v=20261001i`**（21 个文件 / 382 处）。

#### A) 花费类指标极性统一（对应验收报告 7.2）

业务拍板：**「推广花费 / 无界花费 / 礼金总费用」这类花费总额，涨 = 绿（当投放规模看）**。

只需改一处：`frontend/ui_demo/assets/metric-polarity.js` —— 把 `ad_spend`、`wujie_spend`、`brand_marketing_spend`、`gift_cost`、`product_sitewide_spend` 从 `LOWER_IS_BETTER` 移到 `HIGHER_IS_BETTER`。

- `overview-live.js:238` 走 `MetricPolarity.deltaClass`，自动跟着变；`period-review-live.js` 显式传后端标志，**不受影响**。
- **修正了我原来的判断**：这不是 bug。绝对额涨（投放规模扩大）与费率涨（效率下降）是**两套语义，可以共存**，原作者是对的 —— `period_matrix.MATRIX_METRICS` 里 `ad_spend lower_better=False` / `expense_ratio lower_better=True` 就是照这个写的。
- `period_context.TARGET_METRICS` 里推广费 `rate_better='low'` 是**第三套**（预算使用率，实际÷目标，花超算超标），**刻意不统一**，已在 `period_context.py` 顶部固注释。
- 验证脚本从 `.tmp/` 升格进 `scripts/verify_metric_polarity.cjs`，期望值表 9 条 → **16 条**。实测 **PASS 4/4**（`/overview`、`/period-review`、`/lifecycle`、`/products`），表内 20 个负向指标。

#### B) 全站语义色文字对比度（对应验收报告 7.1）

原判断是「修它等于改主色」，所以留了一轮。解法是**拆三组、主色一个都不动**：

| 组 | 用途 | 浅色取值 | 暗色取值 |
|---|---|---|---|
| `--X` | 背景 / 边框 / 图表填充（**保持原色，视觉不变**） | 原值 | 原值 |
| `--X-text` | `color:` 用（深/浅一档，全部 ≥ 4.5:1） | brand `#4f46e5`、success `#047857`、warning `#92400e`、danger `#b91c1c`、info `#2563eb`、purple `#7c3aed` | brand `#a5b4fc`、success `#10b981`、warning `#f59e0b`、danger `#fca5a5`、info `#60a5fa`、purple `#a78bfa` |
| `--X-solid` | 纯色填充块背景（上面压 `--text-on-brand` 白字） | brand `#4f46e5`、danger `#b91c1c` | 同浅色 |

取值依据：`scripts/pick_text_tokens.py`（WCAG 相对亮度，对**全部 10 种可能底色**取最差值，所以不只在纯白上达标）。**改值前先跑它。**

落地过程与踩的坑：

1. **批量替换 189 处文字色 + 12 处实色**（`.tmp/apply_text_tokens.py`，17 个文件），两条规则 + 三重断言。
2. ⚠️ **`border-color: var(--X)` 里含 `color: var(--X)` 子串** —— 不做后顾断言会虚高 44 处。必须用 `(?<![-\w])color:`。
3. ⚠️ **`--brand-solid` 一开始取 `#4f46e5`，正好等于原有的 `--brand-hover`** → 主按钮 hover 无视觉变化。补 `--brand-solid-hover: #4338ca`（白字 7.90:1），并改 `--button-primary-bg-hover` 与 `analysis.css` 的 hover 规则。
4. ⚠️ **grep 的 `\s` 不生效**：BSD/GNU grep 的 BRE/ERE 不支持 `\s` —— `grep -n "color:\s*var(--success)"` 返回 0，换成字面量空格返回 11。批量脚本用 Python `re`（支持 `\s`），命令行排查用 `[[:space:]]`。
5. **第二遍审计暴露两类漏网**（第一版脚本只匹配 `var(--X)` 形式）：
   - **带 fallback** 的写法，如 `period-review.css:1003` 的 `.pr-chip.is-info { color: var(--info, var(--brand)); }`；
   - **写死 hex** 的，如 `rival-analysis.html` 的 `.rival-badge--*`、`flow-source.html` 的 `.flow-badge--*`、JS 内联模板里的 `#ef4444`。
   补脚本 `.tmp/fix_tertiary_inline.py`：`color: var(--text-tertiary)`（#9ca3af，白底 2.54:1）用在**文字**上的 41 处 → `--text-secondary`；硬编码 hex 文字色 6 处 → token。**不动** `components.css` 里 5 处 `:disabled` / 纯图标（1.4.3 豁免 / 1.4.11 另算）。
6. **`--text-secondary` 本身在灰底上不够**：`#6b7280` 白底 4.83:1 达标，但在 `--surface-muted #f3f4f6`（**4.39**）和 `brand-tint #eef2ff`（**4.32**）上掉线 —— 这是**全站约 50 组**的系统性问题，且只差 0.11。新增一档 `--color-gray-550: #646c79`（最差 4.74:1 @ brand-tint），`--text-secondary` 指向它。观感变化极小（约 4% 变深），三级灰的层级不受影响。

**结果：全站 20 页对比度审计「需修 0」。** 48 个未达标项**全部是禁用态** —— WCAG 1.4.3 明确豁免「非活动用户界面组件」。

> 口径说明：该审计只测**文本节点**。语义色用作**图表填充 / 边框**时适用 WCAG 1.4.11（3:1），本轮**刻意不改**（改了就是改视觉）；`--text-tertiary` 保留给纯图标与禁用态同理。

#### C) 根目录历史脚本归档

38 个文件（仓库根 31 个：`_probe_*.cjs`、`_verify_*.cjs`、`_smoke_out.*`、`app_stderr.log`、`pelican-*.html`、`combos_*.json` …；另 7 个在 `frontend/ui_demo/` 根 —— 那是 Flask 静态根，会被直接服务出去）→ **`archive/root-scripts-20261001/`**，带 `_move-manifest.json`（original / archived_to / sha1 / bytes）与 `README.md`。

判据是**三重证据**扫描（`scripts/classify_root.py` → `.tmp/root-classification.json`）：package.json scripts 引用 / 被 import·require·subprocess 调用 / 文档提及（**必须读上下文** —— 出现「不要运行 / 已弃用 / 已迁移 / 历史」不算证据）。**31 个全部零证据**，且 `.gitignore` 本就声明它们不入库（`*.log`、`/*.json`、`pelican-*.html`），`git status` 里一直是 `??`。

两个坑：

- ⚠️ 扫「是否被引用」时**必须排除自指目录**（`docs/`、`.tmp/`、`.workbuddy-ai/memory/`、`archive/`、`legacy/`），否则「归档报告里提到了探针名」会被当成证据，判据全废。
- ⚠️ Windows 下 `glob` 返回**反斜杠**，`p.startswith('docs/')` 恒 False —— 先 `p.relative_to(ROOT).as_posix()`。

全部是**同盘 rename，没有删除**，`_move-manifest.json` 可逐条校验、原样移回。

#### D) 复查（同日夜间）：三个审计盲区与幽灵 token

收尾时把**审计本身**又审了一遍，发现追加批次的「全站需修 0」是个**假象** —— 默认配置只覆盖「浅色 + 桌面」。

**补上三个盲区**：

| 盲区 | 为什么会漏 | 补上后的发现 |
|---|---|---|
| **伪元素文本** | `querySelectorAll('*')` 不返回伪元素，`content: '→'` 生成的文本既不在 `childNodes` 也不在 `'*'` 集合里 | `.promotion-funnel__step::after` 的 `→`/`↓`（17px 正文）用 `--text-tertiary` = **2.54:1** |
| **主题** | 主题存 `localStorage['tmall-demo-theme']` 再落成 `html[data-theme]`，`newContext()` 不设它 | **`data-collection` 深色下单页 97 项不可读**（浅色下是 0） |
| **响应式断点** | 移动端有独立的字号/颜色覆盖 | 补跑 375×812 后无新增问题 |

`scripts/audit_ui_contrast.cjs` 现在支持 `--theme light|dark|both` × `--viewport desktop|mobile|both`。修复后全矩阵复验：**四个组合需修全部为 0**。

**根因是「幽灵 token」—— 引用了但从未定义的 CSS 变量。** 深色那 97 项不是 97 个 bug，而是一个：

```css
.integration-card { background: var(--surface-primary, #fff); }   /* --surface-primary 从未定义 */
```
→ fallback `#fff` 生效 → 深色下卡片仍是白底，而文字取了深色的 `--text-primary`（`#f8fafc` 近白）→ **1.05:1**。

顺手写了 `scripts/check_css_tokens.py`，一次扫出 **18 个幽灵 token / 45 处引用**，其中 **6 处是「整条样式静默失效」**（不是降级，是消失）：

| 无 fallback 的实例 | 实际后果 |
|---|---|
| `color: var(--text-danger)` ×2 | 错误提示**根本不是红的**（继承父级色） |
| `.rival-tab.active { background: var(--primary-color); color: white }` | **白字透明底，完全不可见** |
| `border: 1px solid var(--border-color)` ×10 | analysis / flow-source / rival-analysis 三页**表格边框全部消失** |
| `background: var(--surface-hover)` ×3 | 行 hover **无背景反馈** |
| `padding: var(--space-10)` | spacing 档位只到 `--space-8` → 空态 padding 为 0 |

**修复原则（关键，否则会顺手变成视觉变更）**：
- **当前已生效的**（靠 fallback 生效）→ 换成 fallback 实际取到的那个 token，**渲染结果不变**。
  例：`var(--surface-subtle, var(--surface-base))` → `var(--surface-base)`，并注明「若要恢复『比首行稍暗』的原意应改 `--surface-muted`，那是视觉变更，需单独评估」。
- **当前失效的** → 换成正确 token，是**纯修复**。

**同一页还有一批硬编码色对**：`data-collection.html` 的 `.freshness-*` / `.integration-badge--*` / `.collect-deps` 是「浅色 tint 底 + 深色字」，浅色达标、深色塌掉（`#78350f` 压深色 `--warning-tint` `#34240a` = **1.65:1**）。17 组全换成 `--X-tint` + `--X-text`。`.collect-log-content` 保留硬编码深色（刻意模仿终端的深底浅字块，两主题都合格）。

**仍然没覆盖的（诚实边界）**：
- **交互态**（hover / focus / active）在截图里不出现，脚本测不到 —— 相关 token 已人工修过，但没有自动化验证。
- **图表填充/边框的 WCAG 1.4.11（3:1）**：本轮刻意不改（改了就是改视觉）。
- `--text-tertiary` 用于**有意义图标**时（如搜索框放大镜）严格说适用 1.4.11，当前 2.54:1，属可讨论项。

---

## 7. 每批的验证流程

```bash
# 1) 起服务（必须用 run_in_background 托管，detached 会被回收）
cd E:/www/tmall-dashboard
./.venv/Scripts/python.exe scripts/start_dev_server.py

# 2) 确认端口在听（必须加 --noproxy，环境有沙箱代理）
curl --noproxy '*' -o /dev/null -w "%{http_code}\n" http://127.0.0.1:5000/

# 3) 三遍探针
NODE_PATH=E:/www/tmall-dashboard/desktop/node_modules node scripts/audit_ui_layout.cjs
NODE_PATH=E:/www/tmall-dashboard/desktop/node_modules node scripts/audit_ui_deep.cjs
NODE_PATH=E:/www/tmall-dashboard/desktop/node_modules node scripts/audit_ui_dom.cjs

# 4) 重生成可视化报告
./.venv/Scripts/python.exe scripts/build_ui_audit_report.py

# 5) 后端回归
./.venv/Scripts/python.exe -m pytest tests/ -q
```

**建议新增一个基线比对脚本** `scripts/check_ui_baseline.cjs`：读 `.tmp/ui-audit/dom.json`，对照第 1 节的目标值输出 PASS/FAIL。这样"有没有变好"不靠人眼。

**已知无关失败**：`tests/test_auto_collect_launcher`（schtasks 被安全策略拦截）。跑它会顺手重启看板服务，所以整轮测试后 5000 端口的 PID 会变，别拿跑测试前的 PID 判断代码新旧。

---

## 8. 回归防线（防止改回去）

1. **`TmallUI.audit()` 加规则**：唯一 h1（1-1）、表格必须有 `ui-table-wrap`（已有）、空态必须有标题（已有）、禁止 legacy class（已有）。加完这条，审计脚本会自动抓回退。
2. **注册表 vs 路由白名单交叉校验**（0-1 第 4 处）。这是这批里最值钱的一条——它把"新增页面忘注册"从"线上静默失效"变成"测试里直接炸"。
3. **把阈值写成脚本**（第 7 节的 `check_ui_baseline.cjs`）。DOM 节点数和可交互元素数是最容易悄悄涨回去的两个指标。

---

## 9. 明确不做

这一轮**不做**以下事项，做了大概率要回滚：

- 不引入 React / Vue / TypeScript / Vite / 状态管理框架
- 不改 API 字段语义、指标计算口径、数据库结构
- **不合并 `expense_ratio` 的两处定义**（`metric_definitions` 与 `category_analysis_service`）——会连带改掉很多页面数字
- 不做视觉美化（换主色、加阴影、加圆角、加动效）
- 不重构 `components.css` 的 340 个类（它的 token 纪律是 0 硬编码颜色，动它收益低风险高）
- 不重写 `promotion` / `market-ranking` 的表格结构（只做列预算和 Tab 懒渲染）
- 不为每个页面单独设计组件；新组件必须 ≥2 页复用才能进 `ui-components.js`（`ui-decision-card` 只 1 页用，要么推广要么删）
- 不动 `themes/` 与页面 CSS 的边界划分（2054 行，单独一轮再做）

---

## 10. 排期与依赖

```text
批次 0（P0 缺陷，半天）
   ├── 与批次 1 并行（文件不重叠）
   └── 是批次 4-8 的前置（注册表改造）

批次 1（层级收敛，1~2 天）
   └── 是批次 2 的前置（页头结构先定，才好挪控件）

批次 2（首屏决策区，2~3 天）
批次 3（密度与表格，2~3 天）  ← 与批次 2 可并行

批次 4（一致性与无障碍，1~2 天）
   └── 依赖批次 0 的注册表改造
```

**验收节奏**：每批结束跑第 7 节流程，逐格比对第 1 节基线表。不达标不进下一批——尤其是批次 3，它是唯一可能把表格排序/粘性表头改坏的一批。

---

## 11. 时间不够就按这个顺序做

按「收益 ÷ 工作量」排序，前两项是唯一的真 bug，其余都是体验问题：

1. **0-5 修 `failure()` 的 availability** —— 改 **1 个文件约 20 行**，一次性修正全应用 **252 个错误响应**的语义（131 个「参数缺失」不再报成「计算失败」）。杠杆最高，风险最低（默认行为不变）。
2. **0-1 补齐页面能力注册表** —— 8 个页面的能力门控现在是**静默失效**的，这是唯一的"功能性缺陷"。（注意 `services/page_capability_service.py:269` 的 `!= 13` 硬断言，要 4 处联动改。）
3. **1-1 + 1-2 唯一 h1 + 导航分组降级** —— 半小时工作量，一次性解决整个项目的标题层级和文档大纲污染。
4. **3-1 分页改真分页** —— 单页 24,333 个 DOM 节点是这批里最伤性能的一项，但也是**风险最高**的一项（排序 / 粘性表头 / 分页三者耦合），放最后做。

> 第 1 项之所以排第 1：它是**纯契约修复**，不碰任何视觉、不碰任何指标口径、不需要设计决策，改完前后端行为可预测。而 0-1 虽然更"功能"，但要动注册表三处 + 测试断言，返工面更大。
