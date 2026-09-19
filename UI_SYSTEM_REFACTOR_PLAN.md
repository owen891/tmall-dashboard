# 天猫数据仪表盘 UI 系统统一改造方案

## 1. 改造目标

本次改造只调整前端 UI 架构，不改变 Flask API、页面路由、业务数据口径和 Electron 集成。

最终必须达到以下结果：

1. 同一种 UI 只存在一个组件实现和一套交互规则。
2. 页面只负责业务组合，不再自行实现按钮、卡片、表格状态、弹窗等公共结构。
3. 颜色、字号、间距、尺寸、圆角和阴影只来自设计令牌。
4. 公共组件修改一次即可同步影响全部页面。
5. 新页面通过标准模板和组件目录创建，不再复制旧页面后继续分叉。
6. 自动检查能够阻止硬编码样式、重复组件和不符合约定的页面进入主分支。

## 2. 现状与主要问题

当前已经具备 `tokens.css`、`shell.css`、`components.css` 和 `DESIGN_SYSTEM.md`，但它们还没有形成可执行的组件系统：

- `components.css` 同时包含基础组件、复合组件和大量页面专属样式，职责混杂。
- `ui-components.js` 只有 DOM 工具函数，没有 Button、MetricCard、Panel、Modal、DataState 等稳定 API。
- 页面 HTML 重复维护页面头部、KPI 卡片、Panel、表格和弹窗结构。
- 各 `*-live.js` 分别拼接 HTML、处理空状态、格式化数值和初始化图标，行为容易分叉。
- 组件样式和业务钩子都依赖普通 class，视觉调整可能误伤业务逻辑。
- 规范主要依靠人工遵守，缺少 lint、组件目录页和视觉回归测试。

## 3. 技术路线

第一阶段继续使用原生 HTML、CSS、JavaScript，不立即引入 Vue 或 React。采用“标准 DOM 契约 + 原生模块化组件 + 渐进迁移”的方式：

- 静态组件使用统一 HTML 结构和 CSS class。
- 动态组件由 `TmallUI` 工厂函数创建，禁止页面自行拼接同类 HTML。
- 有完整生命周期和交互状态的复杂组件使用 Custom Element。
- 页面脚本只保留请求、业务状态、数据映射和事件编排。

当所有页面完成组件迁移后，再根据复杂度评估是否引入 Vue。届时设计令牌、组件 API 和页面组合规则仍可直接复用。

## 4. 目标目录

```text
frontend/ui_demo/
├── assets/
│   ├── styles/
│   │   ├── tokens.css              # 原始令牌、语义令牌、组件令牌
│   │   ├── foundations.css         # reset、排版、焦点、可访问性
│   │   ├── shell.css               # 应用外壳和页面布局
│   │   ├── components/             # 一个组件一个文件
│   │   │   ├── button.css
│   │   │   ├── badge.css
│   │   │   ├── panel.css
│   │   │   ├── metric-card.css
│   │   │   ├── data-table.css
│   │   │   ├── modal.css
│   │   │   └── data-state.css
│   │   ├── patterns/               # 页面级复合结构
│   │   │   ├── page-header.css
│   │   │   ├── filter-toolbar.css
│   │   │   └── metric-grid.css
│   │   └── pages/                  # 仅允许业务页面差异
│   └── ui/
│       ├── core.js                 # DOM、安全文本、事件与生命周期工具
│       ├── formatters.js           # 金额、数字、比例、日期统一格式化
│       ├── components/             # 公共组件实现
│       ├── patterns/               # 复合组件实现
│       └── registry.js             # 唯一公共入口 TmallUI
├── pages/
└── system/
    └── component-catalog.html      # 组件目录和所有状态预览
```

过渡期保留原资源路径，通过入口文件加载新目录，完成全部页面迁移后再删除兼容层。

## 5. 分层规则

### 5.1 Design Tokens

令牌分为三层：

- Primitive：原始颜色和尺寸，页面不得直接使用。
- Semantic：`surface`、`text`、`border`、`brand`、`success` 等语义变量。
- Component：`button-height`、`panel-radius`、`table-row-height` 等组件契约。

页面 CSS 只能使用 Semantic 和 Component 令牌。任何新增硬编码颜色、字号、阴影、圆角和常用间距都必须被自动检查拦截。

### 5.2 基础组件

首批统一以下组件：

| 组件 | 统一内容 |
| --- | --- |
| Button / IconButton | 尺寸、层级、图标、禁用、加载、危险操作 |
| Input / Select / Checkbox | 标签、帮助文本、校验、禁用和错误状态 |
| Badge / Chip / Delta | 语义色、状态映射和数字方向 |
| EmptyState / DataState | loading、empty、error、partial 等标准状态 |
| Panel | 标题、说明、工具区、内容区和底部操作 |
| MetricCard | 标签、值、趋势、图标、选中和加载状态 |
| Modal | 标题、正文、页脚、关闭、焦点和滚动行为 |
| DataTable | 表头、排序、数字列、空状态、分页和横向滚动 |

### 5.3 复合组件

统一 `AppShell`、`PageHeader`、`MetricGrid`、`FilterToolbar`、`ChartPanel`、`TablePanel`、`FieldSelector` 和 `ConfirmDialog`。业务页面只能组合这些结构，不得复制后创建变体。

### 5.4 业务组件

只有包含明确业务语义且不能跨页面复用时才进入 `pages/`，例如商品筛选、推广计划视图和数据导入记录。业务组件仍必须组合公共组件，不能重写其视觉规则。

## 6. 组件契约

每个公共组件必须同时具备：

1. 唯一名称和使用场景。
2. 标准 DOM 结构或 JS API。
3. `default`、`hover`、`focus`、`disabled`、`loading`、`empty`、`error` 等适用状态。
4. 尺寸、variant 和 tone 的有限枚举，禁止页面自由创造修饰符。
5. 键盘操作、ARIA 和焦点管理规则。
6. 组件目录页示例和最小 DOM 测试。

动态组件统一从 `window.TmallUI` 调用，例如：

```js
TmallUI.metricCard({
  label: '净销售额',
  value: TmallUI.format.money(value),
  trend: { value: change, direction: 'up' },
  tone: 'brand',
});
```

## 7. 强制开发规则

- `.ui-*` 表示公共组件样式，`.layout-*` 表示布局，`.is-*` 表示运行状态，`.page-*` 表示页面专属样式。
- `data-ui-*` 只用于公共组件行为；`data-{page}-*` 只用于业务数据绑定。
- JS 不得依赖视觉 class 查找节点，CSS 不得依赖业务 `data-*` 设置外观。
- 页面脚本不得为公共组件使用 `innerHTML` 拼接模板；动态文本默认使用 `textContent`。
- 页面 CSS 不得覆盖 `.ui-*` 内部结构，只能通过公开的 variant、slot 或组件令牌配置。
- 图标只使用统一 Lucide 封装；数值和日期只使用统一 formatter。
- 新增页面必须从标准 Page Template 创建，并在组件目录中复用已有模式。
- 公共组件发生破坏性修改时，必须先修改组件契约和所有消费者，再删除兼容行为。

## 8. 实施阶段

### 阶段 0：基线与冻结

- 记录 17 个页面的桌面和窄屏基线截图。
- 生成现有组件、选择器、硬编码值和重复渲染逻辑清单。
- 约定迁移期间不再新增公共组件的页面私有版本。

验收：所有页面有可比较基线，功能与关键交互清单完整。

### 阶段 1：设计系统基础

- 重整 token 分层，补充表格、弹窗、状态和响应式令牌。
- 拆分 `components.css`，保留兼容入口。
- 建立 `TmallUI` registry、formatters 和 component catalog。
- 加入 UI 规则检查脚本。

验收：旧页面视觉不变；组件目录覆盖全部基础组件及其状态。

### 阶段 2：核心组件与试点页面

- 实现 PageHeader、MetricCard、Panel、DataState、Modal 和 DataTable。
- 选择 `products` 作为表格型试点，`overview` 作为仪表盘型试点。
- 将试点页脚本中的通用 HTML 渲染和格式化移入组件层。

验收：两页不再自建公共组件；功能、键盘操作、桌面和窄屏截图通过。

### 阶段 3：按页面族迁移

1. 表格页：keyword-promotion、market-ranking、flow-source、lifecycle。
2. 分析页：promotion、rival-analysis、analysis、compare、reviews。
3. 管理页：data-center、data-collection、settings、goals、manage。
4. 详情页：product-detail 及公共商品详情弹窗。

每迁移一页，就删除该页对应的重复 CSS 和渲染函数，不保留双实现。

### 阶段 4：收口

- 删除旧 class、兼容 alias、重复 formatter 和废弃组件逻辑。
- 将 `DESIGN_SYSTEM.md` 改为规则入口，将具体组件文档放到组件目录旁。
- 建立新增页面模板、代码评审清单和版本变更记录。

验收：公共组件只有一个实现；页面专属 CSS 不包含公共组件覆盖。

## 9. 自动检查与测试

提交前执行以下检查：

- CSS：禁止页面文件出现硬编码颜色、阴影、圆角、字号和非白名单间距。
- HTML：检查标准资源顺序、页面骨架、标题层级和必需 ARIA。
- JS：检查页面直接拼接公共组件、重复 formatter、危险 `innerHTML`。
- DOM contract：验证组件 variant、状态和事件行为。
- Visual regression：至少覆盖 overview、products、promotion、settings 的桌面与窄屏截图。
- Smoke test：导航、筛选、排序、分页、弹窗、主题和数据状态。

检查应接入现有测试命令和 CI；规则失败时不允许合并。

## 10. 完成标准

改造完成必须同时满足：

- 100% 页面使用同一 AppShell、PageHeader、Panel、Modal 和 DataState。
- 所有动态数值使用统一 formatter，所有空值统一显示 `--`。
- 公共组件不存在页面级复制实现。
- 页面 CSS 只表达业务布局差异，不覆盖公共组件内部样式。
- light/dark、桌面/窄屏及键盘操作均通过验收。
- 修改任一公共组件后，组件目录和代表页面的视觉回归能够显示全部影响。
- 新页面不复制旧页面文件，通过标准模板和组件组合完成。

## 11. 建议排期

按单人连续开发估算：

| 阶段 | 时间 |
| --- | --- |
| 基线、盘点和规则冻结 | 1-2 天 |
| Token、CSS 分层、组件目录和检查工具 | 2-3 天 |
| 核心组件及两个试点页面 | 4-6 天 |
| 其余页面迁移 | 7-10 天 |
| 清理、回归和文档收口 | 2-3 天 |

总计约 16-24 个工作日。应按阶段合并，每一阶段都保持应用可运行，不做一次性整体替换。
