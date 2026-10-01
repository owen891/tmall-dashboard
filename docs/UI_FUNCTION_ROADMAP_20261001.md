# UI 功能改进路线（2026-10-01）

> 本文件只覆盖 **UI 功能层**（交互一致性、详情面、信息架构、功能缺口、契约语义）。
> 视觉 / 布局 / 无障碍已由 `UI_REMEDIATION_PLAN_20261001.md` + `UI_ACCEPTANCE_20261001.md`
> 收口（34 项整改、全站对比度需修 0、6 条回归防线），**本文不重复**。
> 所有现状均经代码级核验（文件:行号 / grep 证据）。

## 0. 定位：功能层是下一战场

上一轮把「像素、层级、对比度、DOM 密度」这些**呈现层**问题基本清零了。
剩下的不达标项和真正的体验短板，根子都在**功能组织**：详情面各页各写一套、
一个页面塞了过多可交互控件、删页面连带删掉了后端还在的功能、用 HTTP 404 表达「暂无数据」。
这些不是再改几行 CSS 能解决的，需要按功能维度单独规划。

## 1. 功能层实测现状

### 1.1 详情面统一化（NUI 抽屉）—— 进行中，未收口

当前分支 `codex/nui-ui-optimization` 正在把各页「详情弹窗」统一到共享组件
`ui-components.js:242 detailDrawer`。已落地（git log 实证）：

| 已统一到 detailDrawer | 提交 |
|---|---|
| 推广结构详情 | 1104744 |
| lifecycle 商品详情 | 26dae31 |
| creative-board 素材明细 | ac7aa5b |
| products 经营规则详情 | 42c43bd |
| data-center 数据域/页面能力详情 | 5304f7b |

**仍是旧实现（未统一）**：

| 位置 | 现状 | 性质 |
|---|---|---|
| `market-ranking-live.js` | 自定义 `drill-modal` | 详情面，应统一 |
| `product-detail-live.js` + `product-detail-dialog.js` | 独立 dialog 模块 | 详情面，应统一 |

> 注意区分：`alert-rules.js` / `settings-live.js` / `data-collection-live.js` /
> `overview-live.js` 里的 `modal`/`confirm` 多数是**表单/确认弹窗**，本就该用
> `ui-components.js` 的 `modal`/`confirm` 工厂，**不在「详情面统一」范围内**。
> 别把表单 modal 也改成抽屉——那是过度统一。

**且这批工作有 102 个文件未提交**（含 NUI 改造 + `compare-live.js`/`manage-live.js` 删除）。

### 1.2 功能回归：manage 后端在、UI 已删

批次 4-8 删掉了 `manage.html` / `manage-live.js`，但：

- `api/manage_api.py` **仍有 8 条路由**（`/api/manage/tasks`、`/api/manage/kpis` 等）在线；
- `task_items` / `user_kpis` / `scheduled_tasks` 三张表**实测全 0 行**；
- `/manage` 302 跳 `/settings`，但 `settings.html` 只覆盖「文件夹扫描」，
  **不含任务/KPI/日志管理**。

即「管理任务 / 用户 KPI / 日志」这块功能**前端已无入口、后端仍挂着**。
这是一个悬空状态：既没正式下线，也没 UI 可用。

### 1.3 功能过载：data-center 可交互元素 193（目标 <100）

`data-center` 是全站唯一同时挂 **4 张表 + 2 张能力地图**的页面。
上一轮把 DOM 节点从 24,333 压到 2,775（达标），但**可交互元素数没降**——
193 个里绝大多数是「每行 1 个操作按钮」。要降到 <100 只能**砍功能或收纳**
（能力地图折叠、行内操作收进「更多」菜单、两张表合并），属产品决策。

### 1.4 契约语义：goals 用 404 表达「暂无数据」

```python
api/goals_api.py:73   return failure('NOT_FOUND', '该年度尚未创建目标', status=404)
```
```js
goals-live.js:170     if (error.status === 404) { renderDataState('no-data', ...) }
```

「某年度还没建目标」是**正常业务空态**，却用 HTTP 404 表达，前端硬编码 404 分支兜。
后果：`audit_ui_deep.cjs` 永远把 goals 记成 1 个 httpError + 1 个 consoleError，
真实报错被这条「设计内的 404」淹没。上一轮 0-5 已给 `failure()` 加了
`code → availability` 映射，但 goals 这条是**故意走 404**，没被覆盖。

### 1.5 信息架构：两个长页

- **rival-analysis 移动端 8,237px**（全站最高）：竞品店铺 + 竞品单品 + 趋势
  三块长列表纵向堆叠，方案基线里都没给它目标值。
- **period-review 桌面 4,283px**：上一轮为消除货品表横滚，把两张表从并排改通栏堆叠，
  页高 +622px 是**刻意权衡**（不横滚 vs 页面变长，二选一）。

### 1.6 无障碍功能盲区：交互态无自动化验证

上一轮对比度审计只测**静态文本节点**。`hover` / `focus` / `active` 态
（`.rival-tab.active`、`.flow-table tr:hover`、`.rival-item-card:hover`）在截图里不出现，
脚本测不到——token 已人工修过，但**没有回归防线**。图表填充/边框的 WCAG 1.4.11（3:1）
也刻意未做。

## 2. 改进原则

1. **详情面统一 ≠ 全部改抽屉**：只有「查看某对象详情」的面才统一到 `detailDrawer`；
   表单/确认继续用 `modal`/`confirm`。
2. **删功能要连后端一起决策**：不接受「前端删了、后端悬空」的中间态。
3. **契约优先于兜底**：能用正确的 HTTP 语义 + `availability` 表达的，不让前端硬编码状态码分支。
4. **每批可独立回滚 + 回归防线随批落地**：延续上一轮 `check_ui_baseline.cjs` /
   `audit_ui_contrast.cjs` / `verify_metric_polarity.cjs` 的做法。

## 3. 分阶段计划

### F0 —— 提交 NUI WIP（硬前提，立即）

| 项 | 动作 | 验收 |
|---|---|---|
| F0.1 | 把 102 个未提交变更按主题分批提交（NUI 抽屉统一 / compare·manage 删除 / 对比度 token / 其余），每批跑三探针 + `pytest` | 工作树干净；`check_ui_baseline.cjs` 不回退；`pytest` 862 绿 |
| F0.2 | 提交后跑 `release_audit.py --strict` | audit 绿 |

> 与主路线 P0 是同一件事——102 文件里既有 UI 功能改造也有删除，必须先落地。

### F1 —— 详情面统一化收尾（1-2 天，低风险）

| 项 | 动作 | 说明 |
|---|---|---|
| F1.1 | `market-ranking-live.js` 的 `drill-modal` → `detailDrawer` | 复用已统一的 5 处同款焦点圈闭/归还、Escape/背板 |
| F1.2 | `product-detail-dialog.js` + `product-detail-live.js` 的 dialog → `detailDrawer` | 商品详情是高频入口，统一后焦点管理一致 |
| F1.3 | 统一后删除各页残留的自定义 modal CSS 与 DOM 模板 | 净行数为负 |
| F1.4 | `browser_prd_gates.cjs` 的「详情面分类」断言扩到这两页 | 防回退 |

验收：全站「查看详情」类面 100% 走 `detailDrawer`；`TmallUI.audit()` 0 问题；
真机 Tab 遍历焦点归还正常。

### F2 —— manage 功能处置（需决策，代码量取决于选择）

**二选一，不接受继续悬空：**

- **方案 A（正式下线）**：确认任务/KPI/日志三功能不再需要 → 删 `api/manage_api.py`
  8 条路由 + 三张表（走归档，不直接 drop）+ 相关测试 + `/manage` 302 保留。
  收益：清掉一整套僵尸后端。
- **方案 B（重做 UI）**：三功能仍要 → 在 `settings.html` 或新页补最小可用 UI，
  接回 `/api/manage/tasks`、`/api/manage/kpis`。成本较高（等于新做一个页面）。

判据：三张表**全 0 行**、不在导航、`/manage` 已 302——倾向 **方案 A**，但需用户拍板。

### F3 —— 信息架构减负（中风险，需产品判断）

| 项 | 动作 | 目标 |
|---|---|---|
| F3.1 | data-center 减负：能力地图默认折叠 / 行内操作收进「更多」菜单 / 评估两表合并 | 可交互元素 193 → <100 |
| F3.2 | rival-analysis 移动端 IA：三块长列表改 Tab 或折叠（复用 market-ranking 2-5 的 Tab 化手法） | 移动页高 8,237 → <6,000 |
| F3.3 | period-review 通栏 vs 横滚**复评**：上一轮选了通栏（页高换不横滚），若用户更在意页高可回退 | 按用户偏好定 |

验收：`audit_ui_dom.cjs` / `audit_ui_layout.cjs` 对应指标达标且不回退其他项。

### F4 —— 契约与一致性（低风险，高杠杆）

| 项 | 动作 | 收益 |
|---|---|---|
| F4.1 | goals 契约修正：`/api/goals/<year>` 无目标时返回 **200 + `availability='no-data'`** 而非 404；前端删掉 `error.status === 404` 硬编码分支，统一走 `renderDataState` | 消除常驻的 1 个假 httpError + 1 个假 consoleError；空态语义正确 |
| F4.2 | 交互态无障碍探针：给 `audit_ui_contrast.cjs` 加 `page.hover()` / `focus()` 专项，覆盖 `.rival-tab.active`、表格行 hover、卡片 hover | 补上上一轮的诚实盲区 |
| F4.3 | 空态/错误态/加载态渲染巡检：确认全站统一走 `DemoApi.renderDataState` / `TmallUI.dataState`，无页面手拼「暂无数据」字符串 | 一致性 |

验收：`audit_ui_deep.cjs` 的 httpErrors 只剩真实错误；新增交互态探针纳入 CI 门禁。

## 4. 执行顺序总览

```
F0  提交 102 个 WIP + 三探针不回退 + audit 绿     ← 硬前提，与主路线 P0 同步
F1  详情面统一化收尾（market-ranking / product-detail）  ← 低风险，接着当前分支做
F4.1 goals 404 契约修正                            ← 高杠杆，可与 F1 并行
F2  manage 功能处置（下线 or 重做）                 ← 需用户拍板
F3  信息架构减负（data-center / rival-analysis）    ← 需产品判断
F4.2/F4.3 交互态探针 + 空态巡检                    ← 补防线
```

## 5. 需用户拍板的决策项

1. **F2 manage 功能**：正式下线后端（推荐，三表全 0 行）还是重做 UI？
2. **F3.1 data-center 减负**：能力地图默认折叠 / 行内操作收进菜单，哪个可接受？
   （降到 <100 必须砍或收纳一部分控件）
3. **F3.3 period-review**：维持「通栏不横滚、页面长」，还是回退到「并排、货品表横滚」？

## 6. 明确不做（延续上一轮边界）

- 不引入 React / Vue / TypeScript / Vite / 状态管理框架。
- 不改指标计算口径、数据库结构。
- 不把表单/确认 `modal` 也改成抽屉（过度统一）。
- 不做视觉美化（换主色、加阴影/圆角/动效）。
- 图表填充/边框的 WCAG 1.4.11（3:1）仍是单独一轮，本文只补**交互态文本**探针。

## 7. 风险清单

| 风险 | 等级 | 缓解 |
|---|---|---|
| NUI WIP 拆分提交混入无关改动 | 中 | 按主题分批，提交信息注明混入内容 |
| 详情面统一改坏焦点管理 | 中 | 复用已验证的 5 处同款实现；真机 Tab 遍历 + `browser_prd_gates.cjs` 断言 |
| goals 契约改动影响年度切换逻辑 | 中 | 前后端同一提交改；补 API 回归测试 |
| manage 下线误删仍需的后端 | 中 | 先确认三表 0 行 + 无调用方；走归档不 drop；文件可从 git 恢复 |
| data-center 减负砍掉用户在用的能力 | 中 | F3.1 前先拍板收纳方式，不擅自删功能 |

---

> 净效果：详情面全站统一到一套抽屉组件、消除 manage 悬空后端、goals 空态契约正确、
> data-center/rival-analysis 信息架构减负、交互态无障碍纳入自动化防线。
> 均为低风险、可回滚、不碰指标口径与 schema 的功能层改进。
