# TM Dashboard 可开发功能规格

> 版本：0.1
> 范围：P0 真实数据能力、P1 派生能力与运营闭环、P2 数据源补齐后的能力边界
> 关联底稿：[DATA_CAPABILITY_BASELINE.md](./DATA_CAPABILITY_BASELINE.md)

## 1. 产品边界

本规格不新增综合“商品健康分”。所有问题都以可解释的指标提醒呈现；生命周期是阶段判断，问题提醒是异常判断，运营动作是处理结果。

数据状态统一使用：

- `available`：依赖字段和当前窗口完整。
- `partial`：部分商品、日期或粒度可用。
- `insufficient-data`：有数据，但不满足推导门槛。
- `no-data`：当前筛选范围没有记录。
- `missing-fields`：缺少必要字段。
- `source-unavailable`：数据源或批次不可用。
- `calculation-failed`：输入存在但计算失败。

所有正式接口必须返回统一 envelope，至少包含 `availability`、`evidence_level`、`missing_inputs`、`limitations`、`freshness`、`evidence`、`assumptions`、`unknowns` 和 `requestId`。

## 2. 交付分期

### P0：真实数据可支撑的第一版

1. 数据准备度与质量报告
2. 统一指标目录
3. 店铺经营总览
4. 商品经营分析
5. 推广效果分析
6. 商品问题提醒
7. 数据导入与批次审计

### P1：真实数据 + 独立演示数据

1. 生命周期评估
2. 事件时间线
3. 运营动作闭环
4. 周/月复盘

### P2：数据源补齐后再开发

1. 利润和毛利
2. 库存与周转
3. 用户 cohort 和留存
4. 严格因果归因
5. 完整市场机会分析

## 3. P0 功能规格

### DATA-001 数据准备度与质量报告

**目标**：让用户知道哪些数据可用、覆盖到哪里、哪些结论不能算。

**输入**：所有事实表、`import_batches`、`import_batch_changes`。

**输出**：

- 表级行数、最新日期、最早日期。
- 商品覆盖数、日期覆盖数、连续有效日。
- 核心字段空值率、异常值数量、日期缺口。
- 来源批次、导入时间、数据新鲜度。
- 每个数据域的 `availability` 和缺失原因。

**接口**：

- `GET /api/data-readiness`
- `GET /api/data-readiness?domain=product_daily`

**页面**：数据中心新增“数据准备度”视图。

**验收**：

- 能区分真实 0、缺失值和日期缺口。
- 商品日覆盖数应能显示 882 / 1,847，而不是只显示“有数据”。
- demo 批次和 real 批次来源可区分。

### METRIC-001 统一指标目录

**目标**：所有页面和接口使用同一套字段、公式和聚合规则。

**第一批指标**：

| 指标键 | 公式 | 允许粒度 |
|---|---|---|
| `net_sales` | `sum(payment_amount) - sum(successful_refund_amount)` | 店铺日、商品日/周/月 |
| `refund_rate` | `sum(successful_refund_amount) / sum(payment_amount)` | 店铺日、商品日/周/月 |
| `payment_conversion_rate` | `sum(payment_buyers) / sum(product_visitors)` | 店铺日、商品日/周/月 |
| `average_order_value` | `sum(payment_amount) / sum(payment_buyers)` | 店铺日、商品日/周/月 |
| `expense_ratio` | `sum(ad_spend) / sum(payment_amount)` | 店铺日、商品日 |
| `ad_roi` | `sum(attributed_payment_amount) / sum(ad_spend)` | 推广日 |
| `returning_buyer_ratio` | `sum(returning_payment_buyers) / sum(payment_buyers)` | 店铺日 |

**要求**：

- 原始字段先映射为标准字段。
- 比率和单价必须 `sum_then_derive`。
- 缺失值不自动补零。
- 每个结果记录依赖字段、窗口、来源批次和公式版本。

**验收**：同一指标在总览、商品和导出结果中数值一致。

#### 标准字段映射

| 标准字段 | `store_daily_facts` | `daily_data` | `monthly_data` | 处理规则 |
|---|---|---|---|---|
| `product_visitors` | `product_visitors` | `ipv` | `visitors` | 统一为访客人数，不与 PV 混用 |
| `page_views` | 不提供 | `pv` | `page_views` | 只用于浏览量分析 |
| `payment_buyers` | `payment_buyers` | `buyers` | `buyers` | 统一为支付买家数 |
| `successful_refund_amount` | `successful_refund_amount` | `refund_amount` | `refund_amount` | 只有源文件确认语义一致时才映射，否则指标不可用 |
| `payment_amount` | `payment_amount` | `payment_amount` | `payment_amount` | 金额单位统一为人民币元 |
| `ad_spend` | `ad_spend` | `ad_spend` | `ad_spend` | 不允许把推广归因成交当作花费 |

字段映射必须在导入批次中保存。源字段语义未确认时，返回 `missing-fields`，不得静默把相似字段当作同义字段。

### OVERVIEW-001 店铺经营总览

**目标**：回答“今天/本周期经营发生了什么”。

**输入**：`store_daily_facts`、目标表、事件表。

**功能**：

- 核心指标卡：支付金额、净销售额、退款率、转化率、客单价、费用率、老客占比。
- 日趋势和对比周期。
- 目标完成度和差距。
- 异常日期列表。
- 指标证据抽屉。

**接口**：沿用 `GET /api/overview`，补充统一证据字段；趋势使用 `GET /api/overview/daily-matrix`。

**验收**：

- 缺少退款字段时退款率显示不可用，不显示 0%。
- 对比周期长度和日期范围明确展示。
- 点击指标可以看到公式、数据范围和来源批次。

### PRODUCT-001 商品经营分析

**目标**：回答“哪些商品表现好、哪里出了问题”。

**输入**：`products`、`daily_data`、`weekly_data`、`monthly_data`。

**功能**：

- 商品搜索、分类、层级、状态和收藏筛选。
- 销售、增长、转化、退款、推广依赖排行。
- 商品趋势和周期对比。
- 流量漏斗：访客、加购、下单、支付。
- 商品问题提醒入口。
- 商品事实覆盖状态。

**接口**：沿用 `GET /api/products` 和商品详情接口，禁止把无日事实商品伪造成 0 指标商品。

**验收**：

- 商品主档和经营事实分开显示。
- 可以筛选“无日数据”“数据不足”“可分析”。
- 商品日和商品月数据不会被重复聚合。

### PROMOTION-001 推广效果分析

**目标**：回答“钱花在哪里，归因表现如何”。

**输入**：`promotion_daily_facts`、商品事实、店铺事实。

**功能**：

- 渠道、商品、活动和推广单元下钻。
- 花费、归因成交、ROI、直接成交、间接成交。
- 曝光、点击、CTR、CPC、CPM。
- 推广依赖度和趋势。
- 低效渠道问题提醒。

**接口**：沿用 `GET /api/promotion`，增加粒度、来源和归因说明。

**限制**：所有文案使用“归因表现”，不输出“投放带来的增量”或因果结论。

### ISSUE-001 商品问题提醒

**目标**：把指标变化转成可处理的问题，不生成综合评分。

**第一批规则**：

| 规则 | 触发条件 | 需要的保护条件 |
|---|---|---|
| 销售下降 | 最近窗口较前窗口下降超过阈值 | 两个窗口都有足够有效天数 |
| 转化偏低 | 访客稳定但转化连续低于基线 | 最小访客量、连续 3 个有效日 |
| 推广低效 | 花费上升且 ROI 连续下降 | 最小花费和归因成交量 |
| 退款上升 | 退款率高于商品自身基线 | 最小支付金额 |
| 流量异常 | 搜索/推荐/付费访客突降 | 排除数据缺口和活动切换 |
| 数据缺口 | 有效日不足或日期不连续 | 标记数据问题，不生成经营结论 |

**提醒字段**：

```text
issue_id, product_id, issue_type, severity, status,
current_value, baseline_value, change_rate,
window_start, window_end, evidence, limitations,
suggested_action, owner, created_at, resolved_at
```

**接口**：

- `GET /api/issues`
- `GET /api/issues/<issue_id>`
- `POST /api/issues/<issue_id>/acknowledge`
- `POST /api/issues/<issue_id>/resolve`

**验收**：同一规则在同一窗口不重复生成；缺失数据不会生成经营类提醒。

#### 问题域和数据模型

数据问题和经营问题分开处理：

- `data_issues`：字段缺失、日期断档、批次失败、跨表对账失败。
- `business_issues`：销售下降、转化偏低、推广低效、退款上升、流量异常。

建议使用三张表：

| 表 | 作用 |
|---|---|
| `issues` | 当前问题、类型、状态、严重程度和负责人 |
| `issue_evidence` | 指标值、基线值、窗口、来源批次和证据快照 |
| `issue_status_history` | 确认、处理中、解决、忽略等状态变更审计 |

`issues` 的去重键为：

```text
scope_type + scope_id + issue_type + window_start + window_end + rule_version
```

状态固定为：`open`、`acknowledged`、`in_progress`、`resolved`、`ignored`。经营问题必须关联商品或店铺；数据问题必须关联数据域或导入批次。

#### 初始规则参数

以下是第一版可执行的默认值，统一存入 `alert_rules`，后续通过设置页面调整：

| 规则 | 默认参数 |
|---|---|
| 销售下降 | 当前 14 天 vs 前 14 天，双方至少 7 个有效日，下降不低于 30% |
| 转化偏低 | 当前 7 天转化率低于 28 天基线 20%，至少 200 访客、连续 3 个有效日 |
| 推广低效 | 当前 7 天花费不低于 100 元，ROI 较 28 天基线下降 25% |
| 退款上升 | 当前 7 天支付金额不低于 500 元，退款率高于 30 天基线 1.5 个百分点 |
| 流量异常 | 当前 3 天访客较前 14 天日均下降 35%，且排除日期缺口 |
| 数据缺口 | 连续有效日不足或关键日期缺失，直接生成数据问题，不生成经营结论 |

严重程度不使用综合分数，按明确条件决定：

- `P0`：店铺级核心指标异常或数据源不可用。
- `P1`：商品核心指标持续异常，预计影响当前经营窗口。
- `P2`：单项指标轻微偏离或数据覆盖提醒。

### IMPORT-001 数据导入与批次审计

**目标**：让导入过程可预览、可确认、可追踪、可撤销。

**功能**：

- 多文件预览。
- 自动报告类型识别。
- 字段映射和质量报告。
- 事务写入。
- 批次来源和变更审计。
- 后续批次覆盖时的撤销冲突。

**接口**：沿用 `/api/imports/preview`、`/api/imports` 和 `/api/imports/:id/revert`。

**验收**：撤销冲突返回 409，不静默覆盖后续数据；演示数据只能写入独立 demo 库。

### DATA-002 跨表对账

**目标**：识别事实表之间的金额、数量和覆盖不一致，避免基于错误数据生成经营结论。

**规则**：

| 对账项 | 规则 | 失败处理 |
|---|---|---|
| 商品月 vs 商品日 | 在日事实完整的商品月份内，金额差异不超过 0.5% 或 0.01 元 | 生成数据问题 |
| 店铺日 vs 商品日 | 只比较商品覆盖率达到 95% 的日期；覆盖不足时标记 `partial` | 不阻断页面，显示覆盖缺口 |
| 推广归因成交 vs 店铺支付 | 归因成交超过店铺支付 1% 时告警 | 标记推广数据问题 |
| 日期连续性 | 按数据域和实体检查缺失日期 | 影响相关派生能力 |

对账结果必须出现在 `GET /api/data-readiness`，并能追溯到具体日期、表和批次。

## 4. P1 功能规格

### LIFECYCLE-001 生命周期评估

**输入**：商品日/月事实和商品主数据。

**功能**：新品、成长、爆发、成熟、衰退、数据积累中、季节性、置信度、理由、人工锁定。

**要求**：逐商品返回状态；整体允许 `partial`。演示数据先生成事实，再调用同一套算法，不直接硬编码结果。

### EVENT-001 经营事件时间线

**输入**：`chart_events`、运营动作、导入批次、人工变更。

**功能**：在趋势图上标记价格、主图、详情页、推广、活动、上下架等事件，并支持按事件类型筛选。

### ACTION-001 问题到动作的闭环

**流程**：

```text
问题提醒
→ 创建运营动作
→ 指定目标指标和观察窗口
→ 执行
→ 自动回算
→ 复盘
→ 关闭或创建下一动作
```

**要求**：动作必须关联 `issue_id`、目标指标、观察窗口和证据；不允许只有文字结论而没有前后数据。

**数据迁移**：为 `product_actions` 增加可为空的 `issue_id` 和 `idempotency_key`；历史动作保持可读，不强制回填问题来源。创建动作时使用 `idempotency_key` 防止重复提交，状态变更继续使用现有版本号乐观锁。

**权限**：新增能力键 `issues.view`、`issues.acknowledge`、`issues.resolve`、`issues.create_action`；所有写操作记录操作人、理由和前后值。

### REVIEW-001 周/月经营复盘

**输入**：商品周/月事实、店铺日事实、问题提醒、运营动作和事件。

**功能**：周期对比、主要变化、问题清单、已执行动作、动作结果和下周期计划。

**限制**：复盘结论必须区分事实、推断和人工判断。

## 5. 兼容和废弃规则

当前 `product_health` 表及相关旧接口不再作为产品能力来源：

1. 新页面不展示健康分或综合评分。
2. 新代码不得新增 `product_health` 写入。
3. 旧接口保留只读兼容期，但响应中标记 `legacy`。
4. 新问题提醒统一写入 `issues`，不再把问题压缩为 `health_score`。
5. 兼容期结束后再删除旧表和旧路由，删除前完成导出和审计留档。

## 6. P2 能力边界

以下能力暂不进入开发：

| 能力 | 缺少的数据 |
|---|---|
| 利润/毛利 | 成本、毛利、平台费用和履约费用 |
| 库存周转 | 库存、入库、出库、采购和缺货事实 |
| 用户 cohort | 用户级订单、首次购买和留存事实 |
| 严格因果归因 | 实验、对照组或可识别的外生变化 |
| 完整市场机会 | 市场事实、行业基准和稳定关键词来源 |

## 7. 开发顺序和依赖

```text
DATA-001 数据准备度
        ↓
METRIC-001 指标目录
        ↓
OVERVIEW-001 / PRODUCT-001 / PROMOTION-001
        ↓
ISSUE-001 问题提醒
        ↓
EVENT-001 + ACTION-001
        ↓
LIFECYCLE-001 + REVIEW-001
```

不得跳过数据准备度和指标目录，直接开发页面指标。

## 8. 接口和非功能要求

### 8.1 问题详情 DTO

```json
{
  "ok": true,
  "data": {
    "issue_id": "issue-001",
    "scope_type": "product",
    "scope_id": "PRODUCT-002",
    "issue_type": "promotion_low_efficiency",
    "severity": "P1",
    "status": "open",
    "current_value": 2.1,
    "baseline_value": 3.0,
    "change_rate": -0.3,
    "window": {"start": "2026-08-01", "end": "2026-08-14"},
    "evidence": [{"source": "promotion_daily_facts", "batch_id": "batch-001"}],
    "suggested_action": "检查低效渠道并降低预算",
    "rule_version": "issue-v1"
  },
  "availability": "available",
  "evidence_level": "full",
  "missing_inputs": [],
  "limitations": [],
  "freshness": {"end": "2026-08-12"},
  "assumptions": [],
  "unknowns": [],
  "requestId": "..."
}
```

### 8.2 写接口要求

- 所有写接口必须校验 capability key、操作人和理由。
- 状态变更必须校验 `version`，冲突返回 409。
- 创建问题、动作和导入批次必须支持幂等键。
- 对同一窗口重复请求不得重复写入结果。
- 页面查询默认分页，导出使用异步或流式方式，不能把全量事实一次性塞入浏览器。
- 正式域 API 的 P0 查询在当前数据库规模下，30 天窗口 p95 目标不超过 1.5 秒；超时必须返回可解释错误，不返回伪造空结果。

### 8.3 时间和单位

- 所有日期以店铺所在时区的自然日计算，当前默认 `Asia/Shanghai`。
- 金额统一人民币元，比例统一 0-1 存储，展示层再转换为百分比。
- API 日期格式统一 `YYYY-MM-DD`，月份统一 `YYYY-MM`。

## 9. 测试矩阵

每个功能至少覆盖以下场景：

| 场景 | 必测内容 |
|---|---|
| 指标 | 正常值、分母为 0、字段缺失、真实 0、跨日聚合 |
| 覆盖 | 全量覆盖、部分覆盖、日期断档、无数据 |
| 对账 | 一致、超容差、覆盖不足、批次混合 |
| 问题提醒 | 首次生成、重复去重、确认、解决、忽略、重新触发 |
| 动作闭环 | 关联问题、重复提交、版本冲突、观察窗口不足、复盘 |
| 导入 | 预览失败、字段缺失、事务回滚、撤销冲突、幂等重试 |
| 权限 | 只读用户、可确认用户、可写入用户、未授权写操作 |
| 前端 | `available`、`partial`、`insufficient-data`、`no-data` 五种状态 |

## 10. 统一验收要求

所有功能必须满足：

- 结果可追溯到事实表和导入批次。
- 缺失值不被当作 0。
- 每个结果带时间窗口和截止日期。
- 每个派生算法有版本号。
- 页面能够表达 `partial` 和 `insufficient-data`。
- 演示数据和真实数据物理隔离。
- 接口、页面能力注册表和测试使用同一能力键。
- 问题提醒可确认、关闭和关联运营动作。
- 不使用不可解释的综合商品评分。
