# TM 页面能力注册表设计

**日期：** 2026-08-14
**状态：** 已确认设计，待实施计划
**范围：** 当前单店 Flask + SQLite 仪表盘的全部正式页面、上下文页、管理入口、弹窗和抽屉

## 1. 问题

数据能力目录已经能回答“系统当前有什么数据、能计算什么指标”，但页面能力仍分散在 HTML、JavaScript、API 路由和按钮事件中。当前存在四类结构性问题：

1. 页面职责重叠，例如全局数据工具箱与 Data Center 各自维护导入和调度入口。
2. 同一能力存在多套实现，例如商品详情页与商品详情弹窗、正式与旧版预警规则 API。
3. 部分功能没有数据证据，例如完整行业 benchmark、完整漏斗和市场机会仍可能出现在经营页面中。
4. 弹层类型只靠 DOM 属性，无法验证其数据前提、影响范围、可撤销性和正式 API。

本阶段建立代码级页面能力注册表，并将其与实时数据能力目录组合，形成可测试、可查询、可视化的治理模型。

## 2. 决策

采用“代码注册表 + Data Center 只读投影”方案：

- 代码拥有页面职责、能力、弹层和 API 归属的唯一业务语义。
- `services/data_capability_service.py` 继续提供实时数据覆盖证据。
- 新的页面能力解析服务组合两者，但不替代各业务 API 的请求级 `capabilities`。
- Data Center 显示页面能力矩阵，供产品和开发共同审计。
- 发布门禁拒绝任何 `unclassified` 页面、能力、弹层或不存在的正式 API。

不采用仅文档方案，因为文档无法阻止页面继续漂移；不采用数据库可编辑配置，因为用户配置不能声明代码实际不支持的能力。

## 3. 三层状态模型

每项能力同时具有三个正交状态：

### 3.1 产品支持级别

- `supported`：当前产品和数据模型正式支持。
- `conditional`：满足字段、覆盖范围、样本量或业务状态后支持。
- `unsupported`：已确认缺少必要数据或方法。
- `unclassified`：尚未完成归属；发布门禁必须失败。

### 3.2 数据可用性

沿用统一 API 合同：

- `available`
- `partial`
- `no-data`
- `insufficient-data`
- `missing-fields`
- `source-unavailable`
- `calculation-failed`

### 3.3 交互状态

- `enabled`：当前可执行。
- `disabled`：能力存在，但当前前提不满足；必须返回具体原因。
- `hidden`：业务页面不应展示该能力；只在治理视图中显示边界。

决策顺序为：产品支持级别 -> 数据域证据 -> 请求级业务 API 能力。注册表不得通过静态声明把业务 API 已禁止的操作重新启用。

## 4. 注册表模型

### 4.1 PageDefinition

```python
{
    "key": "promotion",
    "label": "推广分析",
    "page_type": "primary",
    "route": "/promotion",
    "core_question": "推广费用花在哪里，是否有效",
    "data_domains": ["promotion_daily", "product_master", "alert_configuration"],
    "metric_keys": ["ad_roi", "payment_conversion_rate"],
    "capability_keys": ["promotion.view", "promotion.drilldown", "promotion.export"],
    "entry_points": ["sidebar", "product.context"],
    "exit_points": ["product_detail", "reviews"],
}
```

`page_type` 只允许 `primary`、`context`、`admin`。

### 4.2 CapabilityDefinition

```python
{
    "key": "promotion.drilldown",
    "label": "推广粒度下钻",
    "mode": "analyze",
    "support_level": "conditional",
    "data_domains": ["promotion_daily"],
    "metric_keys": ["ad_roi"],
    "api_endpoints": ["GET /api/promotion"],
    "required_domain_capabilities": ["drilldown"],
    "missing_prerequisites": [],
}
```

`mode` 只允许 `observe`、`analyze`、`export`、`mutate`、`configure`、`workflow`。

每项能力必须至少具有一项依据：数据域、正式 API，或明确的静态配置理由。否则只能是 `unclassified`。

### 4.3 SurfaceDefinition

```python
{
    "key": "promotion.detail",
    "page_key": "promotion",
    "label": "推广下钻详情",
    "modal_kind": "detail",
    "trigger_capability": "promotion.drilldown",
    "read_only": True,
    "impact_scope": None,
    "reversible": None,
    "selector": "[data-promotion-drawer]",
}
```

`modal_kind` 只允许 `detail`、`edit`、`config`、`flow`。动态创建的 dialog 也必须设置 `data-modal-kind`，不能绕过治理测试。

## 5. 数据目录补充

现有 13 个数据域覆盖经营事实，但不足以解释所有页面和弹层。页面能力注册表实施前，数据目录增加以下持久化域：

| 数据域 | 来源表 | 主要消费者 |
|---|---|---|
| `period_reviews` | `period_reviews` | 经营复盘 |
| `annotations` | `product_notes`, `product_tags`, `chart_events` | 概览、商品运营、商品详情 |
| `alert_configuration` | `alert_rules`, `alerts` | 概览、推广、设置 |
| `application_settings` | `app_settings` | 设置、商品、推广、生命周期、导入 |
| `management` | `task_items`, `user_kpis`, `scheduled_tasks`, `operation_logs` | 管理工作台、数据工具快捷入口 |
| `audit` | `audit_logs`, `product_action_history`, `import_batch_changes` | 生命周期、动作、导入、设置 |

这些域属于运营状态和配置事实，不是外部经营指标。它们不得被混入销售、推广或市场指标计算。

## 6. 页面层级与唯一职责

### 6.1 七个主页面

| 页面 | 核心问题 | 正式能力边界 |
|---|---|---|
| 数据概览 | 店铺最近发生了什么 | KPI、趋势、目标偏差、异常入口、事件；不输出无来源 benchmark |
| 商品运营 | 哪些商品需要处理 | 搜索、筛选、排序、批量分类、标签、备注、动作入口、导出 |
| 推广分析 | 推广费用花在哪里且是否有效 | 已导入粒度下钻、ROI、预警、字段模板；不承诺严格归因 |
| 生命周期 | 商品处于什么阶段 | 证据充分性、阶段建议、人工调整、锁定、历史、导出 |
| 经营复盘 | 哪个动作是否有效 | 动作迁移、观察窗口重算、动作复盘、周期总结 |
| 数据中心 | 数据是否可信 | 数据能力、页面能力、导入预览、映射、质量、批次、审计 |
| 设置 | 业务口径如何管理 | 店铺配置、字典、模板、阈值、预警规则 |

### 6.2 上下文页

| 页面 | 来源 | 职责 |
|---|---|---|
| 商品详情 | 商品运营、概览、推广 | 解释单品趋势、推广、评价、生命周期和动作历史 |
| 经营目标 | 概览 | 建议、生成、调整、锁定和版本审计 |
| 周期对比 | 概览、商品运营 | 比较同口径周期指标和差异 |

上下文页不进入一级导航，返回时必须保留来源页面及筛选条件。

### 6.3 管理入口

管理工作台只管理任务、人员 KPI、调度和日志。它不解释经营指标，不与七个业务主页面并列。入口归入设置的管理区。

## 7. 首批能力清单

### 7.1 数据概览

- `overview.view_kpis`：`supported`，依赖 `store_daily`。
- `overview.view_trend`：`supported`，依赖 `store_daily`。
- `overview.view_matrix`：`conditional`，依赖日期覆盖。
- `overview.compare`：`conditional`，依赖两个完整周期。
- `overview.view_goal_progress`：`conditional`，依赖 `goals`。
- `overview.view_customer_mix`：`conditional`，依赖新老客聚合字段。
- `overview.view_funnel`：`conditional`，仅在漏斗各步骤字段存在时启用。
- `overview.industry_benchmark`：`unsupported`，缺少正式行业基准事实。
- `overview.manage_event`：`supported`，依赖 `annotations`。
- `overview.export`：`supported`，导出与当前筛选一致的日度矩阵。

### 7.2 商品运营与商品详情

- 商品列表、筛选、排序、字段模板和导出为 `supported`。
- 批量修改、标签、备注和创建动作依赖对应请求级写能力。
- 商品详情趋势依赖日/周/月事实，推广、评价和生命周期板块分别按域降级。
- 商品详情整页和共享弹窗使用同一 capability key 与渲染模型。
- 无图片、无评价或无推广事实时显示分区状态，不制造占位结论。

### 7.3 推广分析

- 渠道、计划、单元、商品下钻由 API 返回的 `available_grains` 决定。
- 只展示真实导入维度；未导入计划或单元时禁用并解释。
- `ad_roi` 依赖成交归因金额与广告花费。
- 严格因果归因、创意层级和未导入的人群/站点明细为 `unsupported`。
- 预警规则只使用 `/api/alert-rules`；旧 `/api/alert_rules` 不进入正式注册表。

### 7.4 生命周期、目标与复盘

- 生命周期人工调整依赖充分历史、当前版本和 `can_edit_stage`。
- 目标生成、调整与锁定均为 `flow`，必须显示版本和影响周期。
- 动作状态迁移、重算与复盘均为 `flow`，必须显示观察窗口、影响记录和失败处理。
- 周期复盘与商品评价是两个不同数据域，不能继续共用“reviews”语义。

### 7.5 数据中心、设置与管理

- Data Center 同时展示数据能力和页面能力，但两者分别回答“有什么数据”和“页面允许做什么”。
- 全局数据工具箱改为跳转/快捷入口，不再维护第二套完整导入与调度表单。
- 设置负责字典、模板、阈值和预警规则，不执行经营动作。
- 调度创建、启停、运行和删除具有副作用，统一属于 `flow`，不是 `config`。

## 8. 弹层登记与整改

| Surface | 类型 | 决策 |
|---|---|---|
| 数据能力详情 | `detail` | 保留 |
| 页面能力详情 | `detail` | 新增 |
| 推广下钻抽屉 | `detail` | 保留 |
| 生命周期证据详情 | `detail` | 保留 |
| 共享商品详情 | `detail` | 动态 dialog 补 `data-modal-kind` |
| 生命周期人工调整 | `edit` | 保留，受能力门控 |
| 概览事件编辑 | `edit` | 保留 |
| 任务编辑 | `edit` | 保留 |
| 人员 KPI 编辑 | `edit` | 保留 |
| 商品列设置 | `config` | 保留 |
| 推广字段设置 | `config` | 保留 |
| 预警规则编辑 | `config` | 动态 dialog 补 `data-modal-kind` |
| 调度创建/编辑 | `flow` | 从 `config` 修正 |
| 全局数据工具箱 | `flow` | 缩减为 Data Center / 管理入口快捷方式 |
| 导入确认与撤销 | `flow` | 必须显示影响范围和可恢复性 |
| 目标生成/调整/锁定 | `flow` | 必须显示版本与冲突处理 |
| 动作创建/迁移/复盘 | `flow` | 必须显示观察窗口和审计结果 |

所有弹层必须支持 Escape、关闭按钮、焦点回收、加载状态、失败原因和移动端不溢出。

## 9. 解析服务与 API

新增 `services/page_capability_service.py`，职责：

1. 校验注册表 key、页面类型、能力模式和弹层类型。
2. 调用 `build_catalog()` 获取实时数据域状态。
3. 解析每项能力的支持级别、数据可用性和默认交互状态。
4. 输出缺失数据域、指标、API 和前提，不吞掉单项错误。
5. 支持精确筛选，不接受模糊或未知枚举。

新增：

```text
GET /api/page-capabilities
```

筛选参数：

- `page`
- `domain`
- `support_level`
- `modal_kind`

响应数据：

```json
{
  "summary": {
    "page_count": 11,
    "surface_count": 0,
    "capability_count": 0,
    "conditional": 0,
    "unsupported": 0,
    "unclassified": 0
  },
  "pages": [],
  "surfaces": [],
  "unsupported_capabilities": []
}
```

标准 envelope 的 `capabilities` 为：

```json
{
  "can_view_registry": true,
  "can_export": true,
  "can_edit_registry": false,
  "can_release": false
}
```

`can_release` 只在没有 `unclassified`、不存在的 endpoint、重复 key 或非法弹层类型时为 true。

## 10. Data Center 页面能力视图

在现有数据能力地图旁增加“页面能力”标签页：

- 摘要显示主页面、上下文页、管理页、条件能力、不支持能力和未分类能力数量。
- 表格显示页面、核心问题、数据域、指标、能力、正式 API、弹层和状态。
- 支持页面、数据域、支持级别和弹层类型筛选。
- 详情弹窗展示完整证据链和整改原因。
- `unsupported` 始终可见但不可点击为业务功能。
- `unclassified` 使用错误状态并使发布门禁失败。

页面不允许直接编辑注册表。

## 11. 错误处理

- 未知筛选值返回 `422 / VALIDATION_ERROR` 和允许值。
- 数据域不存在时，对应能力变为 `unclassified`，不让整个目录 500。
- 正式 API 不存在时标记 `endpoint-missing`，`can_release=false`。
- 单个页面定义错误不会隐藏其他页面，但会进入 summary 和 limitations。
- 数据库连接失败沿用标准失败 envelope。

## 12. 验证

### 注册表测试

- 11 个页面全部登记且 key 唯一。
- 七个主页面与 manifest 完全一致。
- 上下文页和管理入口路由真实存在。
- 所有 capability、surface key 唯一。
- 所有引用的数据域和指标存在。
- 所有正式 endpoint 在 Flask URL map 中存在。
- 所有 HTML 和动态 dialog/drawer 均有注册项及合法类型。
- `unclassified` 为零。

### API 测试

- 返回标准 envelope、summary、pages、surfaces 和限制。
- 四种筛选确定性生效。
- 未知筛选返回 422。
- `can_release` 与注册表校验结果一致。

### 前端和浏览器测试

- Data Center 加载 `/api/page-capabilities`。
- 页面与弹层筛选改变可见行。
- 详情弹窗关闭后恢复焦点。
- 不支持能力显示缺失前提，不显示业务操作按钮。
- 移动端无水平页面溢出。

### 整改门禁

- 动态商品详情和预警规则 dialog 声明正确类型。
- 调度弹窗改为 `flow`。
- 全局工具箱不再复制完整 Data Center 导入流程。
- 概览行业 benchmark 不再作为可用结论。
- 正式页面不调用旧 `/api/alert_rules`。

## 13. 分阶段实施

### 阶段 A：治理基础

- 补充运营与配置数据域。
- 创建页面、能力和弹层注册表。
- 创建解析服务和只读 API。
- 增加 Data Center 页面能力视图。
- 建立注册表、静态和浏览器门禁。

### 阶段 B：首轮结构整改

- 修复动态弹层类型和调度归类。
- 合并商品详情能力定义。
- 将全局工具箱缩减为快捷入口。
- 隔离无证据 benchmark、完整漏斗和市场机会。
- 统一正式预警规则 API。

后续页面改造只允许从注册表已声明能力中选择，不再新增未登记控件。

## 14. 非目标

- 不新增利润、库存、用户明细、完整市场或行业 benchmark 数据。
- 不自动生成页面。
- 不把注册表变成可编辑配置。
- 不在本阶段引入多店权限模型。
- 不删除旧接口；旧接口保留兼容，但不得被正式页面注册或调用。

## 15. 验收标准

- 一个 API 响应能回答每个页面为何存在、依赖哪些数据、提供哪些能力、使用哪些 API、有哪些弹层和当前为何启用或禁用。
- 当前全部页面、能力和弹层都不存在 `unclassified`。
- 每个操作可追溯到数据域、正式 API 和请求级能力。
- Data Center 能同时审计数据能力与页面能力。
- 重复入口和无数据证据能力完成首轮整改。
- 全量单测、静态验证、定向浏览器门禁和 production preflight 通过。
