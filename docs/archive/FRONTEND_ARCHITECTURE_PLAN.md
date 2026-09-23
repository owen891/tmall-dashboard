# 前端架构渐进式重构实施方案

> **执行版修订（2026-09-20）**
>
> 本文以“先降低耦合，再决定是否引入构建工具”为准。原文中关于第一阶段直接引入 Vite、先迁移数据中心的安排调整为后文的执行顺序；具体实施时以本节和“最终执行顺序”为准。

## 0. 执行版总纲

### 0.1 现实判断

当前项目是 Flask 多页面 + 原生 JavaScript + Electron，本身没有必须通过 SPA 或 React 才能解决的问题。当前最急迫的问题是：

- `shell.js` 成为所有页面依赖的超大公共控制器。
- `products-live.js`、`promotion-live.js` 等页面脚本同时承担请求、状态、渲染和事件处理。
- API、URL、数据状态和权限逻辑散落在页面脚本中。
- 现有测试大量绑定旧文件，直接迁移目录会造成不必要的回归。

因此第一阶段只做代码边界重构，不做框架迁移，不改变 Flask 路由、API 协议和 Electron 主进程。

### 0.2 采用的路线

```text
冻结行为基线
  -> 拆公共 API / 状态 / 事件模块
  -> 商品页模块化样板
  -> 产品详情抽离
  -> 数据中心模块化
  -> 推广分析模块化
  -> 概览和其他页面迁移
  -> 评估是否需要 Vite
```

### 0.3 暂缓事项

以下事项不作为第一阶段前置条件：

- Vite
- React/Vue
- TypeScript 全量迁移
- `frontend/src` 全量目录搬迁
- 所有 HTML 统一模板化
- Electron 主进程重构

如果后续页面模块已经稳定、脚本数量继续增加，再单独评估 Vite。Vite 是后置工具，不是本次重构的目标。

### 0.4 目标

重构完成后应达到：

```text
页面 HTML
  -> 页面入口
      -> 页面状态
      -> 页面领域 API
      -> 页面渲染器
      -> 页面事件
          -> 公共 UI
          -> 公共运行时
```

旧文件在迁移期间保留为兼容入口，确保每个页面可以单独回滚。

## 1. 结论

当前项目不适合直接迁移 React/Vue，也不适合一次性重写。

推荐路线：

1. 保留 Flask 多页面路由和现有 HTML 页面。
2. 保留原生 JavaScript 和现有 CSS 设计系统。
3. 引入 ES Modules + Vite，仅作为构建和依赖管理工具。
4. 将全局脚本逐步拆成公共基础层、页面模块和业务服务。
5. 按页面逐步迁移，迁移期间保持旧页面可以运行。

目标不是把项目改成 SPA，而是让每个页面具备清晰的边界：

```text
页面 HTML
  -> 页面入口模块
      -> 页面状态
      -> 页面 API
      -> 页面渲染器
      -> 页面交互
          -> 公共 UI 组件
          -> 公共运行时服务
```

## 2. 当前实际问题

### 2.1 公共壳层职责过多

`frontend/ui_demo/assets/shell.js` 当前同时负责：

- 公共导航
- 顶部日期范围
- URL 状态
- 主题切换
- 导出
- 导入工具箱
- 错误上报
- 权限能力门禁
- 弹窗管理
- 页面状态渲染
- 事件广播

文件约 1100 行，已经成为所有页面的隐式依赖中心。

### 2.2 页面脚本是“大型控制器”

当前主要页面脚本规模较大：

- `products-live.js` 约 1300 行
- `promotion-live.js` 约 1500 行
- `product-detail-dialog.js` 约 1200 行
- `lifecycle-live.js` 约 875 行

请求、状态、DOM 查询、HTML 拼接、事件绑定、格式化和业务判断混在同一文件内。

### 2.3 全局对象和脚本顺序耦合

当前依赖：

- `window.DemoApi`
- `window.TmallUI`
- `window.DemoNavigation`
- `window.TmallDateRange`
- `window.DemoFieldSelector`

部分页面还存在不同的脚本引入顺序和缓存版本号。脚本缺失时，错误可能延迟到用户操作后才暴露。

### 2.4 页面资源管理缺少统一入口

每个 HTML 页面自己维护公共 CSS 和 JS 引入，导致：

- 公共资源版本号不统一
- 页面依赖关系分散在 HTML 中
- 很难做按页面加载和构建校验
- 后续引入模块时需要同时维护旧脚本和新脚本

### 2.5 测试已经比较完整，但测试绑定了文件实现

当前测试和脚本门禁大量直接读取：

- `shell.js`
- `api.js`
- `products-live.js`
- 页面 HTML

因此重构时不能直接删除旧文件，必须先迁移测试契约，或者保留兼容入口。

## 3. 不做的事情

本轮架构重构不做以下事情：

- 不改 Flask 路由
- 不改 API URL 和响应协议
- 不改数据库结构
- 不把全部页面改成 SPA
- 不引入 Redux、Pinia 等大型状态管理器
- 不把所有 HTML 改成 JSX
- 不在架构重构期间重新设计视觉系统
- 不同时重写 Electron 主进程

这样可以把风险控制在前端资源和页面行为范围内。

## 4. 目标架构

### 4.1 建议目录

新增 `frontend/src` 作为源代码目录，保留 `frontend/ui_demo` 作为 Flask 和桌面端可访问的构建输出目录。

```text
frontend/
  src/
    runtime/
      bootstrap.js
      event-bus.js
      error-reporter.js
      page-context.js
      capability-gate.js
    api/
      http-client.js
      domain-client.js
      response-normalizer.js
    state/
      date-range-store.js
      page-store.js
      storage.js
    ui/
      components/
        data-state.js
        modal.js
        confirm.js
        table.js
        filter-toolbar.js
        field-selector.js
        metric-card.js
      formatters/
        number.js
        money.js
        percent.js
        date.js
    shell/
      shell.js
      navigation.js
      topbar.js
      sidebar.js
      toolbox.js
      theme.js
    pages/
      overview/
        index.js
        api.js
        state.js
        render.js
        events.js
      products/
        index.js
        api.js
        state.js
        render.js
        events.js
      promotion/
        index.js
        api.js
        state.js
        render.js
        events.js
      data-center/
        index.js
        api.js
        state.js
        render.js
        events.js
  styles/
    tokens.css
    shell.css
    components.css
    pages/
      overview.css
      products.css
      promotion.css
      data-center.css
  entrypoints/
    overview.js
    products.js
    promotion.js
    data-center.js
```

### 4.2 运行时边界

每个页面入口只做四件事：

```js
const page = createProductsPage({
  api: productsApi,
  state: createProductsState(),
  render: createProductsRenderer(),
});

page.mount(document);
```

页面入口不得直接承担：

- 通用日期处理
- 通用弹窗实现
- 通用 API 错误转换
- 通用数字格式化
- 通用权限判断
- 其他页面的 DOM 操作

### 4.3 API 层边界

保留现有后端协议，前端新增按领域划分的 API 模块：

```text
api/
  http-client.js       # fetch、HTTP 错误、超时、请求取消
  domain-client.js     # ok、availability、capabilities 标准化
  overview-api.js
  products-api.js
  promotion-api.js
  data-center-api.js
```

页面不再到处直接写：

```js
DemoApi.domainRequest('/api/products?...')
```

而是调用：

```js
productsApi.list(query)
productsApi.updateMetadata(id, payload)
productsApi.star(id, starred)
```

这样 API URL 仍然不变，但 URL、参数、响应转换只维护一份。

## 5. 迁移策略

采用“双运行时兼容迁移”：

```text
现有 HTML
  -> legacy shell.js / legacy page script

新 HTML 或同一 HTML
  -> built entry module
```

每次只迁移一个页面。新模块稳定后：

1. 保留旧文件作为兼容入口。
2. 旧入口内部转发到新入口，或只保留薄适配层。
3. 更新测试引用到新模块。
4. 最后再删除重复实现。

禁止一次性把所有页面替换成新架构。

## 6. 分阶段实施计划

### 阶段 0：冻结行为基线

目标：先确保重构前后可比较。

工作：

- 固定现有 Flask 页面路由。
- 固定 API 响应契约。
- 运行 Python 测试。
- 运行 `scripts/validate_ui_demos.cjs`。
- 运行 `scripts/smoke_core_pages.cjs`。
- 保存桌面、平板、移动端截图和关键交互结果。
- 建立页面行为清单：
  - 日期切换
  - 刷新
  - 导出
  - 筛选
  - 重置
  - 弹窗
  - 表格分页
  - 权限禁用
  - 错误重试

验收：

- 重构前基线全部记录。
- 不新增产品功能。
- 不修改 API 协议。

### 阶段 1：引入构建工具，但不迁移业务

新增：

- `frontend/package.json`
- `frontend/vite.config.js`
- `frontend/src/`
- `frontend/dist/` 或直接输出到 `frontend/ui_demo/assets/build/`

Vite 配置要求：

- 输出目录固定。
- 不覆盖现有 `pages`。
- 支持 Windows 和 Electron 打包。
- 不依赖外部 CDN。
- 生成稳定资源名或带 hash 的资源名。

第一阶段只构建一个最小入口：

```text
src/entrypoints/runtime-smoke.js
```

验收：

- Flask 可以继续访问全部页面。
- Electron 可以继续启动。
- 旧页面不依赖构建产物也能运行。
- 构建产物不进入 Git。

### 阶段 2：先拆公共基础层

优先拆 `shell.js`，但保留 `shell.js` 作为兼容入口。

拆分顺序：

1. `error-reporter.js`
2. `event-bus.js`
3. `date-range-store.js`
4. `navigation.js`
5. `theme.js`
6. `capability-gate.js`
7. `data-state.js`
8. `modal.js`
9. `toolbox.js`
10. `shell-bootstrap.js`

旧入口暂时改为：

```js
import('./build/runtime.js').catch(reportBootstrapError);
```

注意：如果部分页面仍需要同步全局对象，兼容入口继续暴露：

```js
window.DemoApi
window.TmallUI
window.DemoNavigation
window.TmallDateRange
```

但新代码不再依赖这些全局对象。

验收：

- 日期事件名称和 payload 不变。
- URL 恢复行为不变。
- 导出、主题、移动端导航不变。
- 所有页面仍只有一个 active 导航项。

### 阶段 3：迁移数据中心

选择数据中心作为第一个完整迁移页面，因为它边界清晰、业务风险可控，并且能验证复杂状态流。

拆分：

```text
data-center/
  api.js
  state.js
  import-workflow.js
  capability-view.js
  render.js
  events.js
  index.js
```

重点：

- 统一导入状态机：
  - idle
  - uploading
  - previewing
  - mapping
  - validating
  - ready
  - importing
  - success
  - failed
  - partial
- 字段映射、质量校验、异常行和确认入库使用同一个状态源。
- 统一重试和撤销入口。
- 使用共享 `modal` 和 `data-state` 组件。

验收：

- 保持现有导入 API。
- 所有原有数据中心 smoke 流程通过。
- 上传失败、字段缺失、部分失败和撤销行为有浏览器测试。

### 阶段 4：迁移商品运营

商品页是最重要的高频页面，建议在数据中心之后迁移。

拆分：

```text
products/
  api.js
  query-model.js
  state.js
  columns.js
  templates.js
  table-renderer.js
  filters.js
  batch-actions.js
  mobile-summary.js
  events.js
  index.js
```

必须先解决的架构问题：

- 查询参数集中管理。
- `dim`、`start`、`end`、筛选项和排序只由 query-model 生成。
- 重置操作同时重置表单、内存和 URL。
- 桌面表格和移动摘要共享同一个数据模型。
- 详情弹窗独立为共享产品详情模块。
- 列配置、字段模板和分页状态不再散落在页面脚本中。

验收：

- 单日、跨日和无日期请求参数正确。
- 筛选、排序、分页和重置可通过浏览器测试。
- 桌面和移动端字段语义一致。
- 产品详情弹窗可从商品页和推广页复用。

### 阶段 5：迁移推广分析

推广页业务复杂度最高，建议在公共组件和商品页迁移稳定后处理。

拆分：

```text
promotion/
  api.js
  state.js
  view-tabs.js
  overview.js
  plans.js
  products.js
  charts.js
  field-definitions.js
  templates.js
  events.js
  index.js
```

重点：

- 概览、计划、商品三个视图共享查询状态。
- 图表实例统一由 `chart-registry` 管理。
- 切换视图、刷新和日期变化时统一 dispose。
- 计划展开使用 button 和 `aria-expanded`。
- 指标缺失、来源不可用和真实为 0 不能混用 `--`。

验收：

- 至少连续切换视图 10 次无图表实例增长。
- 日期变化不会残留旧数据。
- 计划展开支持鼠标、Enter、Space 和 Escape。
- 推广指标口径说明能跟随当前视图更新。

### 阶段 6：迁移概览和其余页面

顺序建议：

1. 概览
2. 生命周期
3. 自定义分析
4. 素材点击率
5. 市场、竞店、流量来源
6. 经营目标、复盘、设置

概览最后于前三个页面之后迁移，是因为它依赖最多公共能力：

- 日期范围
- KPI
- 图表
- 目标
- 运营提醒
- 数据质量
- 日度矩阵

## 7. 公共组件重构清单

现有 `ui-components.js` 和 `table-controls.js` 不删除，先作为组件实现来源。

建议逐步标准化：

### 必须统一

- `DataState`
- `EmptyState`
- `LoadingState`
- `ErrorState`
- `Modal`
- `Confirm`
- `Toast`
- `MetricCard`
- `FilterToolbar`
- `DataTable`
- `Pagination`
- `FieldSelector`
- `ChartContainer`

### 组件接口原则

组件接收数据和事件，不直接请求 API：

```js
createDataTable({
  columns,
  rows,
  loading,
  empty,
  onRowAction,
});
```

组件不读取具体页面选择器，不读取 `document.body.dataset.page`，不判断业务 API URL。

## 8. 状态管理原则

不引入大型状态管理库，使用轻量 store：

```js
const store = createStore(initialState);

store.subscribe(render);
store.set({ filters });
store.update((state) => ({
  ...state,
  loading: false,
}));
```

每个页面只允许一个页面状态源。

状态分三类：

1. URL 状态：日期、筛选、排序、分页、视图。
2. 页面状态：loading、error、rows、selected、dialog。
3. 持久化状态：主题、列配置、字段模板。

禁止把三类状态混在同一个对象里，也禁止只更新 URL 不更新页面状态。

## 9. API 和请求治理

新增请求层能力：

- 请求超时
- AbortController 取消旧请求
- 请求 token 防止旧响应覆盖新响应
- 统一 HTTP 错误
- 统一业务错误
- 统一 availability 状态
- 统一重试
- 开发环境请求日志

页面 API 不再直接拼接复杂 query string，统一使用：

```js
buildQuery({
  start,
  end,
  dim,
  filters,
});
```

任何 API 协议变更必须同时更新：

- 后端接口测试
- 前端 API 模块测试
- 页面浏览器测试
- 数据口径文档

## 10. HTML 和 Flask 集成方案

现有 Flask 路由继续返回：

```text
frontend/ui_demo/pages/*.html
```

迁移期间页面 HTML 保留公共根节点：

```html
<body data-page="products">
  <aside data-shell-sidebar></aside>
  <header data-shell-header></header>
  <main class="demo-page"></main>
  <script type="module" src="/assets/build/products.js"></script>
</body>
```

过渡期允许旧页面使用旧脚本，但每个迁移完成的页面只能选择一种入口：

- 旧入口
- 新模块入口

不能同时初始化同一个页面。

建议由 Flask 在开发环境提供未压缩模块，在生产和 Electron 中提供构建产物。

## 11. Electron 兼容要求

Electron 当前通过本地后端 URL 加载页面，前端构建无需改变主进程架构。

必须保证：

- 构建产物位于 Electron 打包清单包含的目录。
- 不使用 Node.js API。
- 不依赖 CDN。
- 资源路径使用相对路径或后端同源绝对路径。
- CSP 不允许任意外部脚本。
- Windows 路径下模块资源仍可加载。
- Electron 启动后页面首次加载不依赖网络。

在 `desktop` 侧增加一个打包契约测试，检查：

- build 产物存在
- 页面入口存在
- ECharts 和 Lucide 本地资源存在
- 所有 HTML 引用的构建资源都存在

## 12. 测试策略

### 单元测试

覆盖：

- query builder
- 日期范围转换
- API 响应标准化
- 数据状态转换
- 数字格式化
- 筛选重置
- 分页计算
- 图表配置生成

### 页面浏览器测试

每个迁移页面至少覆盖：

- 首次加载
- 空数据
- 部分数据
- 接口失败
- 日期切换
- 刷新
- 筛选和重置
- 弹窗打开关闭
- 键盘操作
- 移动端布局

### 现有门禁保留

继续执行：

```text
pytest
node scripts/validate_ui_demos.cjs
node scripts/smoke_core_pages.cjs
node scripts/audit_core_interactions.cjs
```

新增：

```text
npm --prefix frontend run build
npm --prefix frontend run test
node scripts/check_frontend_build.cjs
```

迁移期间旧的源码字符串契约测试逐步改为行为契约测试，不要一次性删除。

## 13. 发布和回滚

每个页面通过 feature flag 选择入口：

```text
TMALL_FRONTEND_RUNTIME=legacy
TMALL_FRONTEND_RUNTIME=module
```

开发、测试和桌面端可以单独切换。

发布顺序：

1. 构建产物发布。
2. 默认仍使用 legacy。
3. 测试环境启用 module。
4. 完成浏览器 smoke。
5. 生产环境逐页启用 module。
6. 保留旧入口一个版本周期。
7. 删除旧实现。

回滚只需切回 legacy，不需要回滚后端。

## 14. 推荐工期和任务拆分

### 第一周

- 冻结基线
- 建立 frontend package
- 建立 Vite 输出
- 加入构建契约测试
- 拆出 API、事件和状态基础模块

### 第二周

- 拆分 shell
- 迁移数据中心
- 增加导入流程浏览器测试

### 第三周

- 迁移商品运营
- 统一 query model
- 迁移共享产品详情

### 第四周

- 迁移推广分析
- 建立 chart registry
- 完善图表销毁和视图切换测试

### 第五周以后

- 迁移概览
- 迁移其余页面
- 清理 legacy 入口
- 更新文档和发布脚本

## 15. 完成标准

架构重构完成需要满足：

- 页面路由和 API 路径保持兼容。
- 页面不再依赖大型单文件控制器。
- `shell.js` 只保留兼容入口或薄引导层。
- 公共 API、状态、组件和格式化逻辑有独立模块。
- 页面状态可以通过 URL 恢复。
- 页面切换和刷新不会产生重复事件监听。
- 图表实例可以正确销毁。
- 桌面端和 Web 端都能构建和运行。
- 所有现有 Python、UI contract、smoke 和交互门禁通过。
- 任一迁移页面可以独立回滚到 legacy 入口。

## 16. 最终建议

实际执行顺序应为：

```text
冻结基线
  -> 引入 Vite
  -> 拆 shell 和 api
  -> 迁移 data-center
  -> 迁移 products
  -> 迁移 promotion
  -> 迁移 overview
  -> 迁移其余页面
  -> 删除 legacy
```

不要先做视觉重构，也不要先迁移框架。先建立模块边界、状态边界和测试边界，收益最大，风险最低。

## 17. 最终执行顺序（以此为准）

### 第 0 步：冻结现状

只做记录和验证，不改业务代码：

1. 运行现有 Python 测试。
2. 运行 UI contract、核心页面 smoke 和交互审计。
3. 保存桌面、平板、移动端关键页面截图。
4. 记录商品页、推广页、数据中心的关键操作结果。

产出：

- 一份可重复执行的基线命令。
- 一份页面行为清单。
- 一份已知失败和现有脆弱点清单。

### 第 1 步：拆公共基础能力

不移动页面目录，不引入 Vite，只在现有 `frontend/ui_demo/assets` 下新增模块。

优先顺序：

```text
api-client
  -> response-normalizer
  -> data-state
  -> event-bus
  -> date-range
  -> capability-gate
```

旧的 `api.js` 和 `shell.js` 暂时继续对外暴露兼容对象：

```text
window.DemoApi
window.TmallUI
window.TmallDateRange
window.DemoNavigation
```

新模块通过明确的初始化函数使用这些能力，不再直接读取其他页面的全局变量。

### 第 2 步：商品页作为样板

商品页优先于数据中心，因为它是使用频率最高、交互最复杂且可复用价值最高的页面。

推荐拆分：

```text
assets/pages/products/
  index.js
  state.js
  query.js
  api.js
  filters.js
  columns.js
  table.js
  batch-actions.js
  events.js
```

必须先完成：

- 日期维度和请求参数统一。
- 筛选、排序、分页和 URL 状态统一。
- 重置操作同步清理表单、内存和 URL。
- 桌面表格与移动摘要使用同一数据模型。
- 产品详情弹窗抽成独立共享模块。
- 页面脚本不再直接管理其他页面的 DOM。

### 第 3 步：产品详情和公共表格能力

商品详情弹窗同时被商品页和推广页使用，应独立处理：

- 详情数据请求
- Tab 状态
- 弹窗生命周期
- 销毁和焦点恢复
- 促销、生命周期和经营动作入口

同时把表格、分页、字段选择器和状态组件的接口固定下来，避免每个页面继续复制实现。

### 第 4 步：数据中心

在公共状态和弹窗稳定后迁移数据中心。

这里重点不是改页面样式，而是建立清晰的导入状态机：

```text
idle
  -> uploading
  -> previewing
  -> mapping
  -> validating
  -> ready
  -> importing
  -> success / partial / failed
```

字段映射、异常行、质量提示、确认导入、重试和撤销必须共用一个状态源。

### 第 5 步：推广分析

推广页最后处理核心复杂逻辑：

- 总览、计划、商品三个视图共享查询状态。
- 图表由统一 registry 管理。
- 切换视图、刷新和日期变化时销毁旧实例。
- 计划展开使用可访问的按钮语义。
- 缺失数据、无数据、真实为零和计算失败分别呈现。

### 第 6 步：概览和剩余页面

概览依赖公共能力最多，放在商品、数据中心和推广之后：

```text
overview
  -> lifecycle
  -> analysis
  -> creative-board
  -> market / rival / flow
  -> goals / reviews / settings
```

### 第 7 步：再评估 Vite

满足以下条件后，才评估 Vite：

- 至少 3 个页面已经使用独立模块入口。
- 公共 API、状态和组件边界已经稳定。
- Flask 和 Electron 都有构建产物校验。
- 现有测试已经从文件字符串契约逐步迁移到行为契约。
- 团队愿意维护构建产物和依赖升级。

如果以上条件不满足，继续使用原生 ES Modules 即可，不需要为了“现代化”增加构建链。

## 18. 实施决策

本项目建议立即执行的范围是：

- 新增公共模块目录。
- 拆 `api.js` 的请求和响应标准化能力。
- 拆 `shell.js` 的日期、事件和数据状态能力。
- 用商品页完成第一轮模块化。
- 增加模块行为测试和商品页浏览器回归测试。

本项目暂不执行的范围是：

- Vite 初始化。
- React/Vue 迁移。
- TypeScript 全量改造。
- 所有页面一次性改目录。
- 删除旧的 `*-live.js` 文件。

这样做可以在不改变用户入口和后端协议的前提下，先验证架构是否真的改善了维护成本。

## 19. 稳定性优先修订

如果当前表现是“改一个地方，多个页面出现问题”，说明项目还没有达到直接模块化迁移的起点。此时必须增加一个独立的稳定性治理阶段。

### 19.1 先处理什么

第一目标不是减少文件行数，而是让每次改动的影响范围可预测。

优先处理：

1. 测试环境统一。
2. 页面加载顺序统一。
3. 重复初始化和重复事件监听。
4. 请求竞态和旧响应覆盖新响应。
5. URL、内存、表单状态不一致。
6. 图表和弹窗未销毁。
7. 全局错误被静默吞掉。
8. 公共 DOM 选择器被多个页面复用。

### 19.2 当前已确认的稳定性风险

从当前代码可以确认：

- `shell.js` 会动态加载多个公共脚本，加载失败使用空 catch，真实错误可能被隐藏。
- 页面适配器通过 `window` 全局对象和事件名协作，初始化顺序存在隐式依赖。
- `products-live.js`、`promotion-live.js` 和 `shell.js` 中存在大量 DOM、事件和异步请求交叉逻辑。
- 页面切换、刷新和日期变化都可能触发重复请求或重复渲染。
- 现有 Python 测试必须使用项目 `.venv`，系统 Python 缺少 Flask 时会在收集阶段直接失败。
- 使用项目 `.venv` 运行测试时当前仍出现失败，说明不能把“已有测试数量多”当作“当前基线稳定”。

### 19.3 稳定性阶段的实施顺序

```text
统一测试和启动命令
  -> 记录失败基线
  -> 修复公共加载和初始化顺序
  -> 修复请求竞态和重复监听
  -> 修复 URL / 表单 / 内存状态同步
  -> 补充页面级回归测试
  -> 再开始模块化迁移
```

### 19.4 必须建立的稳定性约束

#### 公共脚本加载

- 所有页面使用统一的脚本顺序。
- 公共脚本加载失败不能静默吞掉。
- 每个页面只允许初始化一次。
- 页面适配器必须显式返回初始化结果。
- 同一个事件监听必须有可移除的引用。

#### 异步请求

- 日期、筛选、排序变化时取消旧请求。
- 每次请求携带 request token。
- 旧请求返回后不得覆盖新状态。
- 页面卸载或重新初始化时中止未完成请求。

#### 页面状态

- URL 状态、页面状态、持久化状态分开保存。
- 修改筛选后必须同时更新 URL、内存和视图。
- 重置必须恢复默认查询、分页和排序。
- loading、partial、no-data、error 必须由同一状态源驱动。

#### DOM 和事件

- 页面模块只能操作自己的根节点。
- 禁止用全局选择器修改其他页面或公共区域。
- 事件监听必须集中注册，并提供 destroy。
- 重新渲染不能重复注册事件。

#### 图表和弹窗

- 每个图表实例登记到 registry。
- 重新渲染前先 dispose。
- 页面销毁时统一清理。
- 弹窗关闭时恢复焦点并清理临时状态。

### 19.5 稳定性阶段的验收门槛

在以下条件满足之前，不开始大规模模块迁移：

- 使用 `.venv` 的测试命令固定并可复现。
- 现有测试失败数量已经归类并有明确处理结果。
- 核心页面连续刷新 10 次无未处理异常。
- 日期切换、筛选、重置连续操作不会出现旧数据覆盖。
- 页面切换和返回不会增加重复事件监听。
- 推广页图表连续切换 10 次无实例泄漏。
- 商品页连续筛选和重置后 URL、表单和列表一致。
- 数据中心导入失败后可以重试，不需要刷新页面才能恢复。

### 19.6 稳定后再重构

稳定性阶段完成后，架构迁移顺序才采用：

```text
公共 API / 状态模块
  -> 商品页样板
  -> 产品详情
  -> 数据中心
  -> 推广分析
  -> 概览
  -> 其他页面
```

因此，本项目当前的真实优先级是：

```text
稳定性治理 > 公共边界治理 > 页面模块化 > 构建工具升级
```
