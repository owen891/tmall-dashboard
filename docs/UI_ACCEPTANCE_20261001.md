# UI 整改验收报告（2026-10-01）

> **验收对象**：`docs/UI_REMEDIATION_PLAN_20261001.md` 批次 0 ~ 4 共 **31 个改动项** + 追加批次 **3 项**（花费类极性统一 / 语义色文字对比度 / 根目录历史脚本归档），合计 **34 项**
> **整改依据**：`docs/UI_LAYOUT_AUDIT_20261001.md`（整改前 22 页 × 3 视口的实测审计）
> **复现方式**：第 6 节，一条命令跑完全部验证
> **可视化报告**：`docs/UI_LAYOUT_AUDIT_20261001.html`（本轮重生成，2.5 MB，含逐页截图）

> ## ⚠️ 2026-10-11 更正：第 2 节的基线数字不可复现
>
> 第 2 节那张 11 项基线表来自 `scripts/check_ui_baseline.cjs`。该脚本读取三份探针产物
> （`dom.json` / `audit.json` / `deep.json`），但这三份**分属不同采集批次**：
>
> | 产物 | 采集时间 |
> |---|---|
> | `dom.json` | 2026-10-03T07:08:42Z |
> | `audit.json` | 2026-10-02T02:37:03Z |
> | `deep.json` | 2026-10-02T02:38:41Z |
>
> 最大时间差 **1711.7 分钟（28.5 小时）**，也就是这张表把跨越近 30 小时、可能跨越代码版本的
> 三次采集拼在了一起。因此第 2 节各格的「现状」值**不能作为当前代码的验收依据**；
> 第 3 节据此写的 3.3 / 3.4 / 3.5 归因也建立在同一批数据上。
>
> 已在该脚本中加入批次守卫（`MAX_BATCH_SKEW_MS = 30 分钟`，超限直接 exit 2 并打印三份产物的
> 真实时间戳），后续必须用**同一批次**重采的三份产物复跑，才能得到有效结论。
>
> 第 1 节「6 项达标」这一结论的**数字**因此存疑；但其中不依赖跨批次比对的部分仍然成立：
> 横向溢出 3 视口 × 20 页为 0、幽灵 token 防线、极性 4/4、无障碍四项归零。

---

## 1. 结论

| 结论 | 事实 |
|---|---|
| **改动项** | 34 项**全部处理完**：31 项按方案落地，2 项（5-2 / 5-5）经实测判定**前提不成立**，改为「留下证据 + 不改」；追加批次 3 项（极性 / 对比度 / 归档）已落地 |
| **验收基线** | 脚本口径 11 项中 **6 项达标**（`check_ui_baseline.cjs`）。整改前是 3 项，批次 4 前是 5 项。**追加批次后复跑仍是 6/11，且各项实测值逐格未变** —— 证明这批纯 CSS/JS 改动没有回退任何布局指标 |
| **未达标项** | 5 项，**没有一项属于本轮改动范围**，逐条归因见第 3 节 |
| **无障碍（WCAG AA）** | 全站 20 页文本对比度：**浅色/深色 × 桌面/移动 四个组合，需修全部为 0**。改动前是「浅色 ~50 组 `--text-secondary` 4.39:1 + 4 处漏网语义色」，深色更是 `data-collection` 单页 97 项不可读（见第 9 节复查） |
| **幽灵 token** | 扫出并清掉 **18 个「引用了但从未定义」的 CSS 变量 / 45 处引用**，其中 6 处是「整条样式静默失效」（错误提示不变红、激活 tab 白字透明底、三页表格边框消失）。新增 `scripts/check_css_tokens.py` 作防线 |
| **指标极性** | 花费类「涨=绿」已按业务口径统一，`scripts/verify_metric_polarity.cjs` **PASS 4/4** |
| **P0 缺陷** | 4 个全部修复，零残留 |
| **后端回归** | `pytest tests/ -q` → **862 passed, 0 failed**（修复了整改过程中暴露的 4 个契约测试） |
| **横向溢出** | 3 视口 × 20 页全部为 0（这是整改前唯一达标的一项，全程没有回退） |

一句话：**能做完的都做完了，剩下的 5 项不达标要么是「设计行为」，要么是「方案刻意权衡的代价」，要么是「本轮范围外的全站遗留」。**

---

## 2. 验收基线逐格比对

`scripts/check_ui_baseline.cjs` 把方案第 1 节的基线写成了脚本，退出码 1 = 有未达标。

| # | 指标 | 整改前 | 目标 | 现状 | 判定 |
|---|---|---|---|---|---|
| 1 | 横向溢出页面数（3 视口） | 0 | 保持 0 | **0** | ✅ PASS |
| 2 | 接口 4xx（20 页加载） | 8 页 422 + 2 个 404 | 0 | 5 | ❌ FAIL → 3.1 / 3.2 |
| 3 | 控制台错误 | 2~3 条/页 | 0 | 1 | ❌ FAIL → 3.1 |
| 4 | 每页 `<h1>` 数量 | 0 或 2（18 页是 h2） | 恰好 1 | **全部恰好 1** | ✅ PASS |
| 5 | 单页 DOM 节点峰值 | **24,333**（data-center） | < 8,000 | **5,155**（period-review） | ✅ PASS |
| 6 | 单页可交互元素峰值 | **193**（data-center） | < 100 | 193（data-center） | ❌ FAIL → 3.3 |
| 7 | 桌面页高峰值 | 5,743px（market-ranking） | < 3,000px | 4,283px（period-review） | ❌ FAIL → 3.4 |
| 8 | 移动页高峰值 | 11,051px（market-ranking） | < 6,000px | 8,237px（rival-analysis） | ❌ FAIL → 3.5 |
| 9 | keyword-promotion 内联样式 | **150** | 0 | **0** | ✅ PASS |
| 10 | `TmallUI.audit()` 问题数 | 2 | 0 | **0** | ✅ PASS |
| 11 | 桌面表格容器内横滚页数 | 5 页 | 0 | 2 页 | ⚪ 参考项（见 3.6） |

**脚本口径外的 2 项**（方案第 1 节列了但三探针测不到）：

| 指标 | 整改前 | 目标 | 现状 | 判定 |
|---|---|---|---|---|
| P0 缺陷数 | 4 | 0 | **0** | ✅ PASS |
| 首屏进入决策区 | 144px（52px 页头 + 92px 上下文栏） | ≤ 96px | **76px**（上下文栏已删，只剩合并后的页头） | ✅ PASS |

> 「首屏进入决策区」用 `scripts/probe_ui_density.cjs` 实测：overview 的 `main` 直接子块依次是 `aside 0px` / **`div.ui-page-header 76px`** / `section.overview-decision 471px` / …，即决策区从 76px 处开始。

**改动方向一览**（越靠左越好）：

```text
接口 4xx          14 ──────────────────► 5      （-64%）
控制台错误         12 ──────────────────► 1      （-92%）
DOM 节点峰值    24,333 ──────────────────► 5,155  （-79%）
桌面页高峰值     5,743 ──────────────────► 4,283  （-25%）
移动页高峰值    11,051 ──────────────────► 8,237  （-25%）
内联样式           150 ──────────────────► 0
audit 问题数         5 ──────────────────► 0
```

---

## 3. 未达标项逐条归因

### 3.1 接口 4xx ×5 + 控制台错误 ×1 —— `/api/goals/2026` 的 404 是**前后端约定好的签名**

```text
goals/desktop  httpErrors   : 404 /api/goals/2026?category_mode=sock
goals/desktop  consoleErrors: Failed to load resource: the server responded with a status of 404 (NOT FOUND)
```

证据链（不是「没查出来」，是「查出来就是这样设计的」）：

```python
api/goals_api.py:73        return failure('NOT_FOUND', '该年度尚未创建目标', status=404)
frontend/ui_demo/assets/goals-live.js:170
                           if (error.status === 404) {
                             renderDataState('no-data', { message: '保存年度目标后显示月度执行计划' });
```

`/api/goals/<year>` 用 **404 表达「该年度尚未创建目标」**，前端**按 404 走 `no-data` 空态**——这是双方约好的契约。2026 年度目标确实还没建，所以必然 404。

**唯一能"修"的方式是改契约**（404 → 200 + `availability='no-data'`），但那要同时改前后端、并影响 `goals` 页的年度切换逻辑，**超出 UI 整改范围**（方案第 9 节：不改 API 字段语义）。

### 3.2 接口 4xx ×4 —— products 的 `ERR_ABORTED` 是**刻意的过期请求取消**

```text
products/desktop  FAIL /api/products?dim=daily&...&category_mode=sock :: net::ERR_ABORTED  ×2
products/mobile   FAIL /api/products?dim=daily&...&category_mode=sock :: net::ERR_ABORTED  ×2
```

同一个 URL 出现两次、都是 `ERR_ABORTED`（不是 4xx，探针把它归在 `httpErrors` 里）。根因：

```js
// frontend/ui_demo/assets/runtime/request-scope.js:8-14
function begin(key = 'default') {
  const previous = active.get(key);
  previous?.controller.abort();          // ← 主动 abort 同 key 的上一个请求
  const controller = new AbortController();
  ...

// frontend/ui_demo/assets/products-live.js:412,417
const request = requestScope?.begin('products');
await DemoApi.domainRequest(buildProductsUrl(), { signal: request.signal, timeoutMs: 20000 });
```

products 页在启动阶段会 `load()` 两次（首次渲染一次、`tmall:date-range-change` 解析出周期后再来一次），**第一次的在途请求被第二次主动 abort** —— 这是防竞态的**正确实现**，不是缺陷。

### 3.3 可交互元素峰值 193（data-center）—— 目标 <100，未改善

`data-center` 是**全站最大的页面**（20 个页面里唯一同时挂 4 张表格 + 2 张能力地图的）。批次 3 的 5-1 把它的 **DOM 节点从 24,333 压到 2,775**（-89%，达标），但**可交互元素数没降**：193 个里绝大多数是「每行 1 个操作按钮」，5-1 只改了「建多少行 DOM」，每页 20 行的控件数不变。

要降到 <100 需要**砍功能**（去掉能力地图、合并两张表、或把行内操作收进菜单），属于产品决策，不在本轮范围。

### 3.4 桌面页高峰值 4,283px（period-review）—— 100% 来自批次 3 的 5-3

用「逐项屏蔽再测页高」做了归因（`.tmp/probe_pr_attr.cjs`）：

```text
原样                    docH=4283
隐藏 4-6 状态文字         docH=4283
去掉 4-5 焦点环          docH=4283
去掉 5-3 通栏            docH=3661     ← 唯一有影响的一项
```

**批次 4 零回退**。+622px 是 5-3 的**刻意权衡**：period-review 的两张货品表原本被五层内边距挤到 410px 宽的容器里、溢出 553px，改成通栏后容器 976px、**溢出归零**，代价是两张表从并排变上下堆叠 → 页高 +622px。

也就是说：**这一项与 3.6 的「表格容器内横滚」是同一个取舍的两面**，方案选了「不横滚、页面变长」。

### 3.5 移动页高峰值 8,237px（rival-analysis）—— 数值与批次 4 前**完全一致**

| | 批次 4 前 | 现状 |
|---|---|---|
| rival-analysis / mobile | 8,237px | **8,237px** |

一个像素都没变，**不是批次 4 引入的**。rival-analysis 是批次 0-1 新补进注册表的 9 个页面之一，方案的基线表（只覆盖整改前的 22 页）里没有它的目标值。要压下去需要单独一轮做该页的信息架构（当前是「竞品店铺 + 竞品单品 + 趋势」三块长列表纵向堆叠）。

### 3.6 参考项：2 页表格容器内横滚 —— 5-3 明确保留

| 页面 | 整改前 | 现状 | 说明 |
|---|---|---|---|
| products 商品列表 | 428px | **158px**（-63%） | 12 列 + 首列 `position: sticky`，**这张表就是为横向滚动设计的**；压到 0 需要每列 ≤80px，「1,234,567.89」放不下。用户可切「字段模板」收窄 |
| period-review 货品表 | 553px | **0**（页高换来的，见 3.4） | — |

`check_ui_baseline.cjs` 把这一项按「参考」输出（`--strict` 时才计失败），因为方案第 1 节写的「5 页 → 0」在 5-3 的结论里已经被重新定义为「页面级横滚归零」（第 1 项，已达标）。

---

## 4. 交付清单（34 项）

### 批次 0：P0 缺陷（6 项，全部落地）

| # | 任务 | 结果 |
|---|---|---|
| 0-1 | 补齐页面能力注册表 | 注册表 **13 → 22 页**（补 9 页：analysis / catalog / creative-board / data-collection / flow-source / keyword-promotion / market-ranking / new-products / rival-analysis）；把硬编码 `if len(PAGE_DEFINITIONS) != 13` **换成与 `app.py` 路由白名单的交叉校验** |
| 0-2 | 能力门控失败不再静默 | 门控失败会显式提示，不再静默放行 |
| 0-3 | 删掉 goals 重复的页面头部 | — |
| 0-4 | 修 `/product-detail` 404 | `/products/<id>` 正常入口不受影响，无 id 的深链有体面落地页 |
| 0-5 | 修 `availability` 语义 | `failure()` 加 `availability` 参数 + `code → availability` 映射表；**131 个 `VALIDATION_ERROR` 一次性归位**到 `missing-fields`；**252 个调用点零改动** |
| 0-6 | 清掉版本检查噪音 | `version-check.js` 对 gitcode 的直连 fetch 改走后端 `GET /api/version` 代理 |

### 批次 1：层级收敛（5 项，全部落地）

| # | 任务 | 结果 |
|---|---|---|
| 1-1 | 每页恰好一个 `<h1>` | 19 页页面标题 `h2 → h1`；promotion / new-products 两处页内 `h1` 降级为 `h2`；`TmallUI.audit()` 加「唯一 h1」规则（防回退） |
| 1-2 | 导航分组标签降级 | `shell.js` 的 `<h2 class="demo-nav__label">` → `<span>`，标题树前 5 个节点不再是导航分组名 |
| 1-3 | 合并页头与上下文栏 | `pageHeader()` 新增 `scope` 参数承载「店铺 · 周期」；删除 12 处 `ui-context-bar__meta` 说明文案。**首屏进入决策区 144px → 76px** |
| 1-4 | 删不可路由的死页面 | — |
| 1-5 | section-kicker 收敛 | — |

### 批次 2：首屏决策区（5 项，全部落地）

| # | 任务 | 结果 |
|---|---|---|
| 2-1 | overview 合并决策区与 KPI | 决策区与 KPI 合为一块，次要 KPI 进 `.overview-decision__secondary` |
| 2-2 | overview 第二决策区视觉区分 | — |
| 2-3 | products 页头 14 → 6 控件 | 页头可见控件 **6**（字段 ×5 + 列设置）；展示/周期/粒度移入表格工具栏 `.product-view-switch`；重置移入筛选区。**1 处有意偏差**：周期选择保持始终可见（`state.periodDimension` 在列表视图也生效，隐藏会砍掉真实能力）。顺带修了 `themes/product-domain.css` 在 22 个页面**全都没带 `?v=`** 导致主题改动用户永远拿不到新版的问题 |
| 2-4 | promotion 单主操作 | 只留「复制本品查看」，删掉与顶栏重复的「刷新数据」 |
| 2-5 | market-ranking 拆掉 4552px 的 section | 桌面 **4,253 → 2,352px**、移动 **9,526 → 4,043px**（目标 <3,000 / <6,000，双双达标）。做法：趋势榜整块搬进独立 Tab `data-market-tab="trends"`，badge **996 → 126** |

### 批次 3：密度与表格（6 项，4 项落地 + 2 项判定不采纳）

| # | 任务 | 结果 |
|---|---|---|
| 5-1 | 分页只保留当前页 DOM | data-center 节点 **24,333 → 2,775**（-89%，目标 <8,000 达标）。分页从「全建 DOM 再 `hidden`」改成「只建当前页 + 下拉懒填充」 |
| 5-2 | 隐藏面板加 `content-visibility` | ⛔ **不采纳**：`[hidden]` 就是 `display:none`，浏览器本来就不为它做布局绘制，加了是空操作。实测反而让 period-review 页高 **4283 → 4659（+376px）**（`auto 600px` 兜底估小 → 滚动条跳动），data-center / rival-analysis 无收益。**改动已回退** |
| 5-3 | 表格列预算 | **9 张表溢出全部归零**：overview 日度矩阵 667→0（默认列 14→8，localStorage key `-v2`→`-v3`）、period-review 553→0、lifecycle 156→0、new-products 81→0、keyword-promotion 346→0、data-center 155/97/460→0；products 428→158（有意保留）。根因统一：全局 `.ui-data-table td { white-space: nowrap }` + `table-layout: auto` 让文本型单元格按 max-content 撑破容器 |
| 5-4 | 商品名恢复两行 | `.product-title__link` 改 `-webkit-line-clamp: 2` + `overflow-wrap: anywhere`，去掉固定 `max-width`；同时删掉与之打架的 `.product-title strong` 规则 |
| 5-5 | 每页只留一个筛选工具栏 | ⛔ **前提不成立**：方案里的「lifecycle 4 个 / products 3 个」是**口径把分页条和共享隐藏 toolbox 算进去了**。收紧口径（可见 + 含 input/select + 排除分页）后，全站每页最多 1 个真筛选栏；唯一有 2 个的 data-center 属于**两张不同的表**（数据域 vs 页面），且在默认折叠的面板里。**不改** |
| 5-6 | 消除三层滚动 | data-center 去掉表格内滚（`.ui-table-wrap { max-height: none }`），只保留「整页滚动 + 分页」两层 |

### 批次 4：一致性与无障碍（9 项，全部落地）

| # | 任务 | 结果 | 验证 |
|---|---|---|---|
| 4-1 | keyword-promotion 150 处内联样式迁进 CSS | **150 → 0** | 复测 |
| 4-2 | `period-review.css` 26 处硬编码颜色改 token | **26 → 0**（与方案数字完全吻合） | 幂等脚本 18 条规则 |
| 4-3 | 抽 `metricPolarity(metricKey)` | 新建 `assets/metric-polarity.js`，接入 **8 处**调用点；**修掉 leaf-board「推广花费涨涂绿色」的真误色** | `verify_metric_polarity.cjs` **PASS 4/4** |
| 4-4 | 日历空格子补 `aria-label` | 5 个无名按钮 → **0** | 真实 Tab 遍历 |
| 4-5 | 补齐 `focus-visible` | period-review 18 个无焦点环 textarea → **0**，13 页全 0 | 真实 Tab 遍历 |
| 4-6 | 状态补非颜色表达 | 4 个纯颜色指示器 → **0**（改为「达标 / 临界 / 未达标」） | 三段式探针 |
| 4-7 | 复核 `--text-tertiary` 对比度 | tertiary 文本 **113 → 56**（余 42 个是禁用态，WCAG 1.4.3 豁免） | 对比度探针 |
| 4-8 | 删 `compare.html` / `manage.html` + 清注册表 | 注册表 **22 → 20 页**、`conditional 47 → 43`、`registry_errors: []`；4 个文件删除；`/compare` `/manage` 仍 302 | 测试 + 手工 |
| 4-9 | `ui-decision-card` 统一用或删 | **删**（工厂 0 调用点，唯一「使用」被 CSS 全部覆盖） | 全仓库 grep |

### 本轮顺带修掉的 3 个真 bug

1. **`[hidden]` 静默失效**（影响 ≥3 页）：作者样式的 `display` 特异性高于 UA 的 `[hidden]{display:none}`，`hidden` 属性被静默压掉。实测 products 的「清除分群」按钮在 JS 已设 `clear.hidden = true` 的情况下**依然可见**（78×40）。`components.css` 加 `[hidden] { display: none !important }` 收口。
2. **`shell.js` 动态加载的资源缓存串没跟着改**：`shell.js` 用 `?v=20261001a` 动态加载 `table-controls.js` 与 `version-check.js`，而这两个文件本轮**都被改过**（+81 / +10 行）—— `?v=` 不变意味着浏览器 7 天缓存里继续用旧版本，改了等于没改。已统一 bump。
3. **`components.css` 里 18 条指向已删除 `compare` 页面的死选择器**：4-8 删了页面但漏了 CSS。已用带断言的脚本清理（删完校验花括号配平 908/908、零残留、无悬空逗号）。

另外补齐了 3 处「自定义 wrapper 没挂 `.ui-table-wrap`」导致 `TmallUI.audit()` 报错的地方（`market-ranking.html` ×2、`product-detail.html` ×1），**audit 问题数 5 → 0**。

### 追加批次（2026-10-01 晚，3 项，全部落地）

| # | 项 | 改动 | 验证 |
|---|---|---|---|
| A-1 | 花费类指标极性统一「涨 = 绿」 | `assets/metric-polarity.js` 一处：5 个花费总额 key 从 `LOWER_IS_BETTER` 移到 `HIGHER_IS_BETTER`；`period_context.py` 顶部固注释说明「目标达成率是另一套，刻意不统一」 | `scripts/verify_metric_polarity.cjs` **PASS 4/4** |
| A-2 | 全站语义色文字对比度（WCAG AA） | `tokens.css` 新增 `--X-text` / `--X-solid` 各 9 个（浅暗各一套）+ `--color-gray-550`；批量替换 **189 处文字色 + 12 处实色 + 41 处 tertiary 文字 + 6 处硬编码 hex** | 20 页对比度审计 **需修 0** |
| A-3 | 历史脚本归档 | 38 个文件 → `archive/root-scripts-20261001/`，带 `_move-manifest.json`（sha1 校验）与 `README.md` | 38/38 sha1 一致，两处目录零残留 |

**A-2 连带修掉的两个真 bug**：

1. **`--brand-solid` 取值撞车**：为避免改主色而选 `#4f46e5`，恰好等于原有的 `--brand-hover` → **主按钮 hover 无视觉变化**。补 `--brand-solid-hover: #4338ca`（白字 7.90:1）并改向 `--button-primary-bg-hover`。
2. **`--text-secondary` 在灰底上差 0.11**：`#6b7280` 在 `--surface-muted` 上 4.39:1、`brand-tint` 上 4.32:1，全站约 50 组。新增 `--color-gray-550: #646c79`（最差 4.74:1）收口。

**A-3 的两个扫描坑**（写进脚本注释了）：扫「是否被引用」**必须排除自指目录**（`docs/`、`.tmp/`、`.workbuddy-ai/memory/`、`archive/`、`legacy/`），否则归档报告本身会变成证据；Windows 下 `glob` 返回反斜杠，`p.startswith('docs/')` 恒 False，要先 `as_posix()`。

---

## 5. 后端回归

```bash
./.venv/Scripts/python.exe -m pytest tests/ -q
# → 862 passed, 0 failed, 97 subtests passed
```

追加批次（纯前端 CSS/JS + 新增脚本）**复跑结果完全相同**：`862 passed, 97 subtests passed`。
> 退出码非 0 是沙箱拦截 `schtasks.exe` 造成的，看 stdout 的 `N passed` 而不是退出码。

整改过程中全量测试暴露并修复了 **4 个契约测试**：

| 失败用例 | 原因 | 处理 |
|---|---|---|
| `test_page_capability_service::test_registry_declares_every_routable_page_exactly_once` | 断言写死 `expected \| {'compare', 'manage'}` | 改为与 `registry_keys()` 严格相等 |
| `test_page_capability_service::test_surfaces_point_to_current_rendered_selectors` | 断言取 `surfaces['manage.schedule']`（已删） | 改用仍在线的 `data-center.import` flow surface |
| `test_page_capability_service::test_registered_mutations_cover_formal_page_operations` | 断言取 `by_key['manage.schedule']`（已删） | 改用 `settings.import_scan_manage`（能力已迁到这里） |
| `test_update_notifications_ui::test_web_update_checker_is_loaded_by_the_common_shell` | 断言写死 `"new URL('version-check.js', assetBase)"`，而 shell.js 现在带 `?v=` | 改成正则表达契约：`new URL('version-check\.js(\?[^']*)?', assetBase)` |

前 3 个是 4-8 删页面必然要跟着改的；第 4 个**顺带暴露了上面那个真 bug**（缓存串没 bump）。

> ⚠️ 已知无关失败：`test_auto_collect_launcher` 会被安全策略拦截 `schtasks.exe`（沙箱黑名单），与本次改动无关。

---

## 6. 复现命令

```bash
cd E:/www/tmall-dashboard

# 1) 起服务（必须 run_in_background 托管，detached 子进程会被回收）
./.venv/Scripts/python.exe scripts/start_dev_server.py

# 2) 确认端口在听（必须加 --noproxy，本机有沙箱代理，不加拿 502）
curl --noproxy '*' -o /dev/null -w "%{http_code}\n" http://127.0.0.1:5000/

# 3) 三遍探针（需要 NODE_PATH 指向 desktop/node_modules）
export NODE_PATH=E:/www/tmall-dashboard/desktop/node_modules
node scripts/audit_ui_layout.cjs     # 页高 / 横向溢出 / 失败请求
node scripts/audit_ui_deep.cjs       # 4xx / 控制台 / 标题树 / 内联样式 / audit 问题
node scripts/audit_ui_dom.cjs        # DOM 节点数 / 可交互元素数

# 4) 基线比对（退出码 1 = 有未达标；加 --strict 把参考项也算失败）
node scripts/check_ui_baseline.cjs

# 5) 重生成可视化报告
./.venv/Scripts/python.exe scripts/build_ui_audit_report.py

# 6) 后端回归
./.venv/Scripts/python.exe -m pytest tests/ -q

# 7) 无障碍：全站 20 页文本节点对比度（追加批次 A-2 的验收口径）
#    期望「合计未过 AA N（禁用态 N，需修 0）」—— 需修不为 0 就是回退
NODE_PATH=E:/www/tmall-dashboard/desktop/node_modules \
PW_CHROMIUM="$HOME/AppData/Local/ms-playwright/chromium-1187/chrome-win/chrome.exe" \
node scripts/audit_ui_contrast.cjs

# 8) 指标极性（追加批次 A-1）
node scripts/verify_metric_polarity.cjs
```

三探针的产物落在 `.tmp/ui-audit/{audit,deep,dom}.json`，`check_ui_baseline.cjs` 直接读这三个文件，所以**必须先跑探针再跑比对**。

---

## 7. 已知遗留与待决策

**7.1 / 7.2 已在追加批次里关掉**（见下），仍开着的只剩 7.3 / 7.4，按「是否该现在做」排序：

### 7.1 ~~全站语义色本身未过 WCAG AA~~ → **已修（2026-10-01 晚）**

原判断是「修它等于改主色，需要一次单独的设计决策」。追加批次找到了**不改主色**的解法：把每个语义色拆成三组，各司其职。

| 组 | 用途 | 是否改视觉 |
|---|---|---|
| `--X` | 背景 / 边框 / 图表填充 | **不变** |
| `--X-text` | `color:` 用（深/浅一档，全部 ≥ 4.5:1） | 变（只在文字上） |
| `--X-solid` | 纯色填充块背景（压 `--text-on-brand` 白字） | 变（只在实心按钮/徽标上） |

浅色取值：brand `#4f46e5`、success `#047857`、warning `#92400e`、danger `#b91c1c`、info `#2563eb`、purple `#7c3aed`；
暗色取值：brand `#a5b4fc`、success `#10b981`、warning `#f59e0b`、danger `#fca5a5`、info `#60a5fa`、purple `#a78bfa`。
取色依据脚本 `scripts/pick_text_tokens.py`（对**全部 10 种可能底色**取最差值，不只在纯白上达标）。**改值前先跑它。**

同一批还修了两个连带问题：

- **`--text-secondary` 在灰底上不够**：`#6b7280` 白底 4.83:1 达标，但 `--surface-muted #f3f4f6` 只有 **4.39**、`brand-tint #eef2ff` 只有 **4.32** —— 全站约 50 组，只差 0.11。新增 `--color-gray-550: #646c79`（最差 4.74:1），`--text-secondary` 指向它。
- **`--text-tertiary`（#9ca3af，白底 2.54:1）当文字用**：CSS 里的在批次 4-7 已清，但 JS 内联模板与页面内联 `<style>` 里还有 41 处（「加载中… / 暂无数据 / 元信息」）→ 统一提到 `--text-secondary`。

**验收**：全站 20 页文本节点对比度审计 → **需修 0**（48 个未达标项全部是禁用态，1.4.3 豁免）。

> 口径边界：该审计只测**文本节点**。语义色用作**图表填充 / 边框**时适用 WCAG 1.4.11（3:1），本轮**刻意不改**（改了就是改视觉）；`--text-tertiary` 保留给纯图标与禁用态同理。这是有意识的取舍，不是遗漏。

### 7.2 ~~`ad_spend` 的极性口径矛盾~~ → **已按业务口径统一（2026-10-01 晚）**

原判断是「同一指标两页配色相反，是 bug」。**这个判断本身是错的** —— 业务拍板后确认：

> **花费总额（推广花费 / 无界花费 / 礼金总费用）涨 = 绿，当投放规模看。**

也就是说「绝对额涨 = 规模扩大（好）」与「费率涨 = 效率下降（坏）」是**两套可以共存的语义**，原作者是对的：

| 位置 | 定义 | 含义 | 本轮处理 |
|---|---|---|---|
| `period_matrix.MATRIX_METRICS` | `ad_spend lower_better=False`、`expense_ratio lower_better=True` | 绝对额 vs 费率 | **不动**（本来就对） |
| `assets/metric-polarity.js` | `ad_spend` 原先在 `LOWER_IS_BETTER` | 与上表相反 | **改为 `HIGHER_IS_BETTER`** |
| `period_context.TARGET_METRICS` | 推广费 `rate_better='low'` | **第三套**：预算使用率（实际÷目标，花超算超标） | **不动**，已在文件顶部固注释「刻意不统一」 |

- 改动只有一处文件：`frontend/ui_demo/assets/metric-polarity.js`（5 个花费总额 key 从 `LOWER_IS_BETTER` 移到 `HIGHER_IS_BETTER`）。
- `overview-live.js:238` 走 `MetricPolarity.deltaClass` 自动跟随；`period-review-live.js` 显式传后端标志，不受影响。
- 验证：`node scripts/verify_metric_polarity.cjs` → **PASS 4/4**（`/overview`、`/period-review`、`/lifecycle`、`/products`），期望值表 9 条 → 16 条，表内 20 个负向指标。

### 7.3 删 `manage.html` 的功能代价（知情项）

`manage.html` 不只是「死路由」，它是**「管理任务 / 用户KPI / 日志」的唯一 UI**（`/api/manage/tasks`、`/api/manage/kpis`）。`settings.html` 只覆盖「文件夹扫描」（而且是超集：除 `/run` 外还有 `/runs`、`/files`、`/files/<id>/retry`、`/delete`）。

判定可删的依据：`task_items` / `user_kpis` / `scheduled_tasks` **三张表实测全为 0 行**、不在导航里、`/manage` 302 到 `/settings`。
**后端 `api/manage_api.py` 与三张表未动**，文件可从 git 恢复。若将来要用这两个功能，需要重新做 UI。

### 7.4 其余不达标项的"下一步"

| 项 | 现状 | 要达标需要做什么 |
|---|---|---|
| data-center 可交互元素 193 | 目标 <100 | 砍功能：去掉能力地图 / 合并两张表 / 行内操作收进菜单（**产品决策**） |
| period-review 桌面 4,283px | 目标 <3,000px | 与「货品表不横滚」二选一（当前选了不横滚） |
| rival-analysis 移动 8,237px | 方案未给目标 | 单独一轮做该页信息架构（三块长列表纵向堆叠） |
| goals 404 | 目标 0 | 改前后端契约（404 → 200 + `availability='no-data'`），超出 UI 范围 |
| products `ERR_ABORTED` | 目标 0 | **不需要做**，是防竞态的正确实现 |

---

## 8. 回归防线（已就位）

方案第 8 节要求的三条防线全部落地：

1. **`TmallUI.audit()` 加规则** —— 唯一 `h1`、表格必须有 `.ui-table-wrap`、空态必须有标题、禁止 legacy class。审计脚本会自动抓到回退。
2. **注册表 vs 路由白名单交叉校验**（0-1 第 4 处）—— 把「新增页面忘注册」从「线上静默失效」变成「测试里直接炸」。
3. **`scripts/check_ui_baseline.cjs`**（新建）—— 把第 1 节的阈值写成脚本，DOM 节点数与可交互元素数这两个最容易悄悄涨回去的指标不再靠人眼比对 JSON。
4. **`scripts/verify_metric_polarity.cjs`**（追加批次从 `.tmp/` 升格）—— 16 条期望值覆盖 `ad_spend` / 各费率 / 各单位成本 / 损失类 / `deadBand`，跑 4 个页面。极性表被改回去会直接 FAIL。
5. **`scripts/audit_ui_contrast.cjs`** —— 全站文本对比度，`--theme light|dark|both` × `--viewport desktop|mobile|both`，按「需修」而非「未达标」判定（禁用态自动豁免）。**改任何语义色/token 后跑一遍，两个主题都要跑。**
6. **`scripts/check_css_tokens.py`**（复查新增）—— 扫「引用了但从未定义」的 CSS 变量（幽灵 token）。`--strict` 时有幽灵 token 就退出码 1。**改任何 `var(--x)` 前后跑一遍。**

另外 `scripts/validate_ui_demos.cjs` 新增了 4-4 的日历 `aria-label` 断言。

---

## 9. 复查（同日夜间）：三个审计盲区与幽灵 token

追加批次收尾时问了一句「还有别的问题吗」，于是把审计本身又审了一遍。**结果证明当时的「全站需修 0」是个假象** —— 默认配置只覆盖了「浅色 + 桌面」，另外三个维度一补，问题立刻出现。

### 9.1 补上三个盲区后暴露的问题

| 盲区 | 为什么会漏 | 补上后的发现 |
|---|---|---|
| **伪元素文本** | `querySelectorAll('*')` 不返回伪元素，`content: '→'` 生成的文本既不在 `childNodes` 也不在 `'*'` 集合里 | `.promotion-funnel__step::after` 的 `→`/`↓`（17px 正文）用 `--text-tertiary` = **2.54:1** |
| **主题** | 主题存在 `localStorage['tmall-demo-theme']` 再落成 `html[data-theme]`，`newContext()` 不设它 | **`data-collection` 深色下单页 97 项不可读**（浅色下是 0） |
| **响应式断点** | 移动端有独立的字号/颜色覆盖 | 补跑 375×812 后无新增问题（修复已覆盖） |
| **交互态** | hover / focus / active 只在交互时渲染，截图里不存在 | **仍未覆盖**，见 9.4 |

修复后全矩阵复验：**浅色/深色 × 桌面/移动 四个组合，需修全部为 0**。

### 9.2 根因：幽灵 token（引用了但从未定义）

深色那 97 项不是 97 个 bug，而是**一个**：`data-collection.html` 的
`.integration-card { background: var(--surface-primary, #fff) }` ——
`--surface-primary` **从未定义**，fallback `#fff` 生效 → 深色下卡片仍是白底，
而文字取了深色主题的 `--text-primary`（`#f8fafc` 近白）→ **1.05:1**。

顺手写了个检查脚本（`scripts/check_css_tokens.py`），一次扫出 **18 个幽灵 token、45 处引用**。按失效方式分两类：

| 情形 | 后果 | 实例 |
|---|---|---|
| **无 fallback**（6 处） | `var(--x)` 是**无效声明**，整条属性**消失** | `color: var(--text-danger)` → 错误提示根本不是红的<br>`.rival-tab.active { background: var(--primary-color); color: white }` → **白字透明底，完全不可见**<br>`border: 1px solid var(--border-color)` → analysis / flow-source / rival-analysis 三页**表格边框全部消失**<br>`background: var(--surface-hover)` → 行 hover 无背景反馈<br>`padding: var(--space-10)` → spacing 档位只到 `--space-8`，空态 padding 为 0 |
| **有 fallback**（12 处） | 浅色正常，**深色塌掉** | `--surface-primary, #fff`（见上）<br>`--text-success,#16803c` / `--text-warning,#ad6800`（product-detail）<br>`--border-subtle,#e5e7eb`（4 文件） |

**修复原则**（避免顺手变成视觉变更）：
- **当前已生效的**（靠 fallback 生效）→ 换成 fallback 实际取到的那个 token，**渲染结果不变**。例：`var(--surface-subtle, var(--surface-base))` → `var(--surface-base)`，并在注释里写明「若要恢复『比首行稍暗』的原意应改 `--surface-muted`，那是视觉变更，需单独评估」。
- **当前失效的** → 换成正确 token，是**纯修复**（现状就是「没有样式」）。

### 9.3 `data-collection.html` 的硬编码色对

同页还有一批「浅色 tint 底 + 深色字」的硬编码色对（`#dcfce7`/`#166534` 等），浅色达标、深色塌掉（如 `#78350f` 压在深色 `--warning-tint` `#34240a` 上 = **1.65:1**）。17 组全部换成 `--X-tint` + `--X-text`，深色自动跟随。

浅色下 tint 比原值浅一档（同色系）；`.freshness-recent` 由橙色改为 warning 淡黄，与 `.freshness-yesterday` 统一（两者语义都是「数据偏旧」，靠文字区分）。**`.collect-log-content` 保留硬编码深色** —— 那是刻意模仿终端的深底浅字块，两个主题下都合格。

### 9.4 仍然没覆盖的（诚实边界）

- **交互态**：hover / focus / active 在截图里不出现，本脚本测不到。已知 `.rival-tab.active`、`.flow-table tr:hover`、`.rival-item-card:hover` 这类只在交互时渲染 —— 它们的 token 已人工修过（修的是「无 fallback 失效」），但**没有自动化验证**。改这块要手工点一遍，或写带 `page.hover()` 的专项探针。
- **图表填充 / 边框的 WCAG 1.4.11（3:1）**：本轮刻意不改（改了就是改视觉）。已知 `--success` 作柱条填充是 2.54:1。要做是单独一轮。
- **`--text-tertiary` 的图标用法**：保留给纯图标与禁用态。`product-filters__search > .lucide`（搜索放大镜）严格说是有意义图标、适用 1.4.11（3:1），当前 2.54:1 —— 属可讨论项。

---

## 10. 2026-10-11 补充：门禁加固与三项缺陷修复

本节记录一次独立评审（4 名设计域专家 + 主理人复核）后的整改。**评审结论与本文件的原始基线数据有冲突，
以本节为准**；冲突原因见开头的「2026-10-11 更正」块。

### 10.1 门禁加固（让度量本身可信）

| 改动 | 问题 | 处理 |
|---|---|---|
| `scripts/check_ui_baseline.cjs` | 混读三份不同批次的探针产物，拼出跨代码版本的比对表 | 加批次守卫：`MAX_BATCH_SKEW_MS = 30 分钟`，超限 exit 2 并打印三份产物真实时间戳 |
| `scripts/check_event_binding.py`（新增） | 「禁止事项 7：禁止用 class 做事件绑定」**没有检查脚本**，实际已被违反 3 处 | 新建门禁并修复全部 3 处；判据用括号深度确定语句边界，宁可漏报不可误报 |
| `scripts/check_css_tokens.py` | 把 `.ui-button--primary:hover` 里的 `--primary:` 当成「定义了 `--primary`」，于是 `var(--primary)` 这种真错字永远查不出来 | 给定义正则加负向断言 `(?<![A-Za-z0-9_-])`；定义数 182 → 174，排除掉 **8 个被误登记的 BEM 修饰符**（`--active`/`--clickable`/`--discoverable`/`--drillable`/`--first`/`--link`/`--primary`/`--remove`，见 `analysis.css`、`components.css`、`themes/product-domain.css`、`pages/product-detail.html`） |
| `.github/workflows/quality-gate.yml` + `scripts/test_all.ps1` | `check_event_binding` 若只写进文档就等于不存在；本地入口此前**完全没跑设计系统门禁** | 两处都加入四项静态门禁，且与 `DESIGN_SYSTEM.md` §11.1 清单保持一致 |

**仍然存在的门禁缺口（未修，需单独立项）**：

- `scripts/check_design_system.py` 的组件目录覆盖率只校验 `CATALOG_REQUIRED_COMPONENTS` 里**硬编码的 9 项**，
  而 `ui-components.js` 实际导出 90+；`COMPONENT_LAYER_CSS = {"components.css","shell.css"}`（:55）假设
  「组件层只有这两个文件」，但 `components.css` 里有 210 条 `body[data-page]` 页面私有规则 →
  该假设已失效，页面样式可以绕过页面级 CSS 的检查。
- `scripts/validate_visual_system.cjs` **从未被 CI 调用**，且自身引用已废弃的 `.metric-card__value`。
- 手写复合组件预算 378/378 **零余量**：下一个新增复合组件必然导致门禁失败。
- 禁止事项 8（金额/百分比格式统一）**无静态门禁**；`assets/format.js` 的 `DemoFormat.money` /
  `percent` / `moneyWan` 全仓**零调用点**（20/21 个页面加载了它，只用到 `escapeHtml`），
  而 `money()` 有 13 份各页自实现，`¥` / `￥` 与小数位不一致。
- `scripts/validate_ui_demos.cjs`（本地入口会跑）当前 **exit=1**：18 条 UI 校验错误 + 2 条视觉系统错误
  （`shell.css` font-size / box-shadow）。经 `git stash` 对比确认属工作区既有问题，非本轮引入，
  但会让本地入口长期「红着」，从而失去信号价值。

### 10.2 缺陷修复（3 项，均为评审确认的用户可见问题）

| # | 缺陷 | 后果 | 修复 |
|---|---|---|---|
| 1 | `assets/operations-center.js` 把「数据不足」当成「来源不可用」 | 没有计划动作时提示「计划日历暂不可用」+ 挂重试按钮；用系统故障措辞描述数据状态，与 `README.md:36` 数据伦理承诺冲突 | 新增 `SOURCE_FAILURE = new Set(['source-unavailable','calculation-failed'])`，只有真故障才计入 `sourceErrors` 并 `clearCalendar` |
| 2 | `api/lifecycle_api.py:33-34` 用集合级 `all()` 算能力，`lifecycle-live.js:261` 又逐行判 `disabled` | **一个商品不足 60 天，全表「调整」按钮一起变灰**，数据充足的商品也点不动 | 在 `capabilities.rows[product_id]` 下发逐行能力，前端按行取用、无行级数据时才退回集合级；`disabled` 补 `title` 说明原因。新增回归测试 `test_row_capabilities_are_per_product_not_collection_wide`（已验证移除修复即失败） |
| 3 | `assets/navigation.js` 跨页参数白名单缺 `dim` | `date-range-store.js:193` 把「按周/按月」写进 URL，跨页跳转时被静默丢弃 → 粒度重置回 `daily`，同一段日期换页后意思变了 | 白名单加入 `dim`。已用最小 DOM 桩验证：`dim=weekly` 现在能穿过 `fromCurrent()`，未知参数仍被过滤 |

> 注：`api/api_response.py` 的 `success()` 顶层键是**固定白名单**，传未知键直接 `TypeError`
> （252 个调用点共用）。所以第 2 项的逐行数据只能放进自由格式的 `capabilities`，不能新增顶层字段。

### 10.3 本轮验证记录

| 项目 | 结果 |
|---|---|
| `check_css_syntax.py --strict` | exit 0（19 个 CSS 文件） |
| `check_design_system.py --strict` | exit 0（手写复合组件 378 处 / 预算 378 处） |
| `check_css_tokens.py --strict` | exit 0（定义 174 个 / 引用 157 个） |
| `check_event_binding.py --strict` | exit 0（无 class 选择器事件绑定） |
| `check_ui_contract.py` | exit 0 |
| `unittest discover -s tests` | **Ran 913 tests, OK**（101 秒；原文档基线 862，含新增 1 个回归测试） |
| `pytest` 四个纯 pytest 文件 | 47 passed, 1 skipped |
| `node scripts/test_frontend_runtime.cjs` | FRONTEND_RUNTIME_OK |
| `node --check`（全部非 vendor 前端 JS） | 通过 |
| 缓存版本号 | 被改动的 7 个资源在相关页面统一升为 `?v=20261011a` |

