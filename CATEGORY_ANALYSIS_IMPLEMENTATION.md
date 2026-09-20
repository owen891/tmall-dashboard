# 品类周期分析与利润分析落地方案

**项目**: tmall-dashboard  
**文档版本**: v1.0  
**编制日期**: 2026-09-20  
**状态**: v1.1 首版已落地，已增加独立常态化品类经营看板；利润成本补全与原生周/月数据源为后续增强项

## 1. 目标

新增统一的品类周期分析能力，支持按日、周、月和任意自定义日期区间分析，并对当前周期与对比周期计算同比、环比、差值、增长率和日均值。

产品形态分为两层：

- `品类经营看板`：常态化入口，打开后直接展示默认周期、同比/环比、趋势、利润拆解和商品贡献。
- `自定义分析`：临时取数工具，保留自由选择指标、维度和图表的能力，不承担日常经营看板职责。

典型场景：

- 标品袜子 2024、2025、2026 年月度对比
- 本周与上周同期对比
- 2026-09-01 至 2026-09-20 与去年同期对比
- 618 前后周期对比
- 品类销售额、净销售额和利润率变化分析

## 2. 功能范围

### 2.1 分析粒度

| 粒度 | 口径 | 首选数据源 |
| --- | --- | --- |
| 日 | 自然日 | `daily_data` |
| 周 | 周一至周日 | `weekly_data`，缺失时由 `daily_data` 聚合 |
| 月 | 自然月 | `monthly_data`，未完成月份由 `daily_data` 聚合 |
| 自定义 | 用户输入开始日期和结束日期 | `daily_data` |

自定义区间必须使用日度数据。只有月度数据时，不得把月度总数平均拆分到具体日期。

### 2.2 对比方式

- 去年同期
- 上一周期
- 自定义对比周期
- 无对比，仅查看当前趋势

系统同时保存当前周期和对比周期的：

- 总值
- 有效天数
- 日均值
- 差值
- 增长率
- 数据完整度

当两个周期长度不一致时，总值和日均值必须同时展示。

### 2.3 品类筛选

- 全部品类
- 系统品类，例如 `sock` / 标品袜子
- 设置中配置的自定义品类
- 后续支持多品类横向对比

品类过滤沿用现有 `category_mode` 和 `products.shop_label` 映射，不在新模块中复制一套品类配置。

## 3. 指标范围

### 3.1 基础指标

- `payment_amount`: 支付金额
- `net_sales`: 净销售额
- `payment_qty`: 支付件数
- `visitors`: 访客数
- `buyers`: 支付买家数
- `ad_spend`: 推广花费
- `refund_amount`: 退款金额

### 3.2 派生指标

- `payment_conversion_rate = buyers / visitors`
- `average_order_value = payment_amount / buyers`
- `refund_rate = refund_amount / payment_amount`
- `expense_ratio = ad_spend / net_sales`

比例指标必须用聚合后的分子和分母计算，不得直接平均商品或日度比例。

## 4. 利润口径

### 4.1 第一期：部分成本经营利润

第一期先支持可确认的成本项目：

```text
经营利润 =
净销售额
- 商品成本
- 推广花费
- 平台费用
- 物流成本
- 售后损失
- 其他费用
```

如果某些成本字段缺失，结果必须标记为 `partial`，并返回缺失字段列表。页面显示“部分成本利润”，不得将其包装为完整净利润。

### 4.2 第二期：完整利润

补充以下成本来源：

- 商品采购成本
- 包材成本
- 快递成本
- 平台佣金
- 支付手续费
- 推广花费
- 售后退款损失
- 人工及固定费用
- 其他费用

商品成本支持两种配置：

```text
固定单件成本 = 支付件数 * 单件成本
成本率       = 净销售额 * 成本率
```

商品配置优先于品类配置，品类配置优先于系统默认值。

### 4.3 利润指标

- 毛利
- 毛利率
- 经营利润
- 经营利润率
- 投放后利润
- 单件利润
- 盈亏平衡销售额

## 5. API 设计

新增统一接口：

```text
GET /api/category-analysis/compare
```

请求参数：

```text
category_mode=sock
grain=week
start=2026-09-14
end=2026-09-20
compare_start=2025-09-15
compare_end=2025-09-21
compare_mode=custom
metric=operating_profit
top_n=20
```

参数约束：

- `grain`: `day`、`week`、`month`
- `metric`: 白名单指标
- `start` 不得晚于 `end`
- 对比周期开始日期不得晚于结束日期
- 自定义区间必须使用有效日期
- 周区间按周一至周日规范化，并返回规范化后的实际日期
- 未完成当前周期需要返回 `is_partial_period=true`

响应结构：

```json
{
  "data": {
    "category": {
      "value": "sock",
      "label": "标品袜子"
    },
    "grain": "week",
    "metric": "operating_profit",
    "current_period": {
      "start": "2026-09-14",
      "end": "2026-09-20",
      "days": 7,
      "value": 95000,
      "daily_average": 13571.43
    },
    "compare_period": {
      "start": "2025-09-15",
      "end": "2025-09-21",
      "days": 7,
      "value": 80000,
      "daily_average": 11428.57
    },
    "change": {
      "amount": 15000,
      "rate": 0.1875,
      "percentage_point": null
    },
    "trend": [],
    "profit_breakdown": {
      "net_sales": 300000,
      "product_cost": 140000,
      "ad_spend": 30000,
      "platform_fee": 12000,
      "logistics_cost": 18000,
      "other_cost": 5000,
      "operating_profit": 95000,
      "operating_profit_rate": 0.3167
    },
    "contributors": {
      "up": [],
      "down": []
    },
    "data_quality": {
      "availability": "partial",
      "is_partial_period": true,
      "missing_fields": [],
      "source_tables": ["daily_data"]
    }
  }
}
```

建议新增：

- `services/category_analysis_service.py`
- `api/category_analysis_api.py`
- `tests/test_category_analysis_api.py`

路由注册应沿用现有蓝图和 API 响应格式。

## 6. 前端方案

优先改造现有自定义分析页面：

- `frontend/ui_demo/pages/analysis.html`
- `frontend/ui_demo/assets/analysis-live.js`
- `frontend/ui_demo/assets/analysis.css`

新增模板名称：`品类周期分析`

筛选控件：

- 品类
- 指标
- 统计粒度：日 / 周 / 月
- 当前周期
- 对比方式
- 对比周期
- TOP N

展示区域：

1. 当前周期与对比周期 KPI
2. 趋势图
3. 周/月明细表
4. 利润拆解图
5. 商品增长贡献表
6. 数据完整度和利润口径提示

必须保留以下状态：

- 加载中
- 无数据
- 数据不完整
- 利润字段缺失
- 请求失败

## 7. 数据口径与边界

### 7.1 同比

自然月按同月对比；自然周按同等天数的去年同期对比；自定义区间按用户提供的对比区间对比。

### 7.2 环比

当前周期与长度相同的上一周期比较。若周期长度不同，显示总值环比和日均环比。

### 7.3 缺失与零值

- 无数据：`--`
- 真实为零：`0`
- 无法计算：`不可计算`
- 数据不完整：显示状态和缺失字段

不能把缺失数据自动转换成零。

### 7.4 当前周期

当前日期为 2026-09-20。未结束的周、月或自定义区间必须显示“部分周期”，并优先与去年同期同天数数据比较。

## 8. 验收标准

- 可以选择标品袜子并查看日、周、月数据。
- 可以输入任意合法日期范围。
- 可以使用去年同期、上一周期和自定义对比周期。
- 周粒度默认按周一至周日。
- 总值、日均值、差值和增长率计算正确。
- 同一接口支持销售额、净销售额和利润指标。
- 缺失利润成本时明确显示部分成本口径。
- 商品贡献和品类总量与 API 聚合结果一致。
- 缺失数据、真实零值和不可计算状态展示不同。
- API、前端契约、浏览器冒烟测试通过。
