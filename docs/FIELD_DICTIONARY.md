# TM 2.0 字段字典与字段模板

> 版本：v1.0
> 日期：2026-08-12
> 适用：TM 1.0 保留原架构版、TM 2.0 DS 兼容版
> 来源参考：`E:\bi\ecommerce-dashboard\src\lib\standard-fields.ts`、`bi-field-dictionary.ts`、`bi\field-registry.ts`、TM 当前 `dashboard.db`

## 1. 使用规则

这份文档是 TM 的字段真相源。页面、API、导入模板、指标计算和导出字段都引用这里的标准键，不直接把 Excel 原列名当成业务字段。

字段分三类：

- **R1**：快速可用版本必须支持，缺少字段时影响对应页面或指标。
- **R2**：完整经营分析版本支持，用于推广深度、生命周期、季节性和周期复盘。
- **预留**：参考 BI 已有或业务未来可能需要，但当前不进入产品承诺。

字段状态再区分：

- `existing`：TM 当前 SQLite 已有同义字段或同等数据。
- `mapped`：可由现有参考项目标准字段和常见报表列映射得到。
- `derived`：由标准事实字段计算得到。
- `pending`：当前数据库或已确认报表中没有稳定来源，必须补来源后才能启用。

### 1.1 命名层次

| 层 | 命名规则 | 示例 |
|---|---|---|
| 原始列 | 保留报表原始中文列名 | `支付金额`、`商品访客数` |
| 标准字段 | SQLite/API 内部统一使用 snake_case | `payment_amount` |
| DS DTO | 迁入 DS 时由 adapter 转 camelCase | `paymentAmount` |

R1 不要求立刻把 SQLite 全部改成新表，但新增接口必须返回标准键。旧接口返回的 `gmv`、`refund`、`conversion` 等别名只做兼容，不再作为新业务代码的字段名。

### 1.2 字段定义必备元数据

每条字段定义至少包含：

`standard_key`、`label`、`domain`、`type`、`unit`、`grain`、`aggregation`、`status`、`source_status`、`source_columns`、`nullable`、`formula`、`depends_on`、`pages`、`notes`。

## 2. 粒度和聚合枚举

| 粒度 | 含义 | 业务唯一键 |
|---|---|---|
| `shop_day` | 店铺日度 | `shop_id + stat_date` |
| `product_day` | 商品日度 | `shop_id + product_id + stat_date` |
| `product_week` | 商品自然周 | `shop_id + product_id + week_start` |
| `product_month` | 商品自然月 | `shop_id + product_id + month` |
| `ad_product_day` | 推广商品日度 | `shop_id + channel + product_id + stat_date` |
| `ad_unit_day` | 推广单元日度 | `shop_id + channel + campaign_id + unit_id + stat_date` |
| `goal_period` | 目标周期 | `shop_id + plan_id + period_type + period_key` |
| `action` | 商品运营动作 | `shop_id + action_id` |
| `lifecycle_assessment` | 生命周期判断 | `shop_id + product_id + assessment_date` |

聚合规则：

- 金额、件数、订单数、买家数、访客数、点击数、展现数使用 `sum`，前提是来源粒度可加且没有重复。
- 比率和 ROI 使用 `sum_then_derive`，先汇总依赖字段，再计算，禁止平均行比率。
- 单价使用 `sum_then_derive`，如 `支付金额 / 支付买家数`。
- 标签、名称、状态使用 `last_non_null` 或维表快照，不做求和。
- 不可确认可加性的字段标记 `strict`，禁止自动汇总。

## 3. 维度字段

| 标准键 | 中文名 | 类型/单位 | 粒度 | R | 来源列/当前字段 | 状态 | 页面 |
|---|---|---|---|---|---|---|---|
| `shop_id` | 店铺ID | text | all | R1 | 店铺配置 | existing | all |
| `shop_name` | 店铺名称 | text | all | R1 | 店铺名称、店铺 | mapped | all |
| `stat_date` | 统计日期 | date | day | R1 | 统计日期、日期、`daily_data.date` | existing | all |
| `week_start` | 周起始日 | date | week | R1 | `weekly_data.week_start` | existing | overview, goals |
| `month` | 月份 | YYYY-MM | month | R1 | `monthly_data.month` | existing | all |
| `period_type` | 周期类型 | enum | goal_period | R1 | 系统生成 | derived | goals |
| `period_key` | 周期键 | text | goal_period | R1 | 系统生成 | derived | goals |
| `product_id` | 商品ID | text | product_* | R1 | 商品ID、宝贝ID、主体ID、`*.product_id` | existing | products, promotion, lifecycle |
| `product_name` | 商品名称 | text | product_* | R1 | 商品名称、宝贝名称、主体名称、`products.title` | existing | products, lifecycle |
| `category_l1` | 一级类目 | text | product | R2 | 一级类目名称、一级类目 | mapped | products, lifecycle |
| `category_l2` | 二级类目 | text | product | R2 | 二级类目名称、二级类目 | mapped | products, lifecycle |
| `category` | 三级/叶子类目 | text | product | R1 | 类目、类目名称、商品类目、`products.category` | existing | products |
| `brand` | 品牌 | text | product | 预留 | 品牌名称 | mapped | products |
| `product_status` | 商品状态 | enum | product | R1 | 商品状态、`products.status` | existing | products |
| `tier` | 商品分层 | enum | product | R1 | 人工配置、`products.tier` | existing | products |
| `style` | 商品风格 | enum/text | product | R1 | 人工配置、`products.style` | existing | products |
| `scene` | 商品场景 | enum/text | product | R1 | 人工配置、`products.scene` | existing | products |
| `listed_at` | 上架时间 | datetime | product | R2 | 上架时间、`products.list_date` | existing/mapped | lifecycle |
| `image_url` | 商品图片 | text/url | product | R1 | 图片链接、`products.image_url` | existing/mapped | products |
| `manager` | 商品负责人 | text | product | R1 | 人工配置、`products.manager` | existing | products, actions |
| `remark` | 商品备注 | text | product | R1 | 人工配置、`products.remark` | existing | products |
| `data_source` | 数据来源 | text | fact | R1 | `*.data_source`、导入来源 | existing | data-center |
| `import_batch_id` | 导入批次ID | text | fact | R1 | 导入系统生成 | mapped | data-center |

## 4. 流量和行为事实字段

| 标准键 | 中文名 | 类型/单位 | 粒度 | R | 来源列/当前字段 | 状态 | 页面 |
|---|---|---|---|---|---|---|---|
| `product_visitors` | 商品访客数 | integer/人 | product_day | R1 | 访客数、商品访客数、`ipv`、`daily_data.ipv` | existing/mapped | overview, products |
| `page_views` | 商品浏览量 | integer/次 | product_day | R2 | 浏览量、商品浏览量、`pv` | existing/mapped | products |
| `search_visitors` | 搜索访客数 | integer/人 | product_day | R1 | 搜索访客数、搜索人数、`search_ipv` | existing/mapped | overview, products |
| `recommend_visitors` | 推荐访客数 | integer/人 | product_day | R2 | 推荐访客数、`recommend_ipv` | existing/mapped | products |
| `paid_visitors` | 付费访客数 | integer/人 | product_day | R2 | `paid_ipv`、广告访客数 | existing/mapped | products, promotion |
| `organic_visitors` | 自然访客数 | integer/人 | product_day | R2 | `organic_ipv`、非推广访客数 | existing/mapped | products |
| `impressions` | 展现量 | integer/次 | ad_* | R2 | 展现量、总展现量、`paid_detail.impressions` | existing/mapped | promotion |
| `clicks` | 点击量 | integer/次 | ad_* | R2 | 点击量、总点击量、`paid_detail.clicks` | existing/mapped | promotion |
| `cart_users` | 加购人数 | integer/人 | product_day | R2 | 加购人数、商品加购人数、`cart_users` | existing/mapped | products |
| `cart_qty` | 加购件数 | integer/件 | product_day | R2 | 加购件数、商品加购件数、`cart_qty` | existing/mapped | products |
| `favorite_users` | 收藏人数 | integer/人 | product_day | R2 | 收藏人数、商品收藏人数、`fav_users` | existing/mapped | products |
| `bounce_rate` | 详情页跳失率 | decimal/percent | product_day | R2 | 跳失率、商品详情页跳出率、`bounce_rate` | existing/mapped | products |
| `avg_stay_seconds` | 平均停留时长 | decimal/秒 | product_day | R2 | 平均停留时长、`avg_stay_duration` | existing/mapped | products |
| `search_rate` | 搜索占比 | decimal/percent | product_day | R1 | 搜索占比、`search_ratio` | existing/mapped | overview, products |

## 5. 交易和售后事实字段

| 标准键 | 中文名 | 类型/单位 | 粒度 | R | 来源列/当前字段 | 状态 | 页面 |
|---|---|---|---|---|---|---|---|
| `payment_amount` | 支付金额 | decimal/元 | product_day, shop_day | R1 | 支付金额、GMV、销售额、成交额、`payment_amount` | existing/mapped | overview, products, goals |
| `payment_orders` | 支付笔数 | integer/笔 | product_day | R2 | 支付笔数、支付父订单数、`pay_orders` | existing/mapped | products |
| `payment_buyers` | 支付买家数 | integer/人 | product_day, shop_day | R1 | 支付买家数、支付人数、买家数、`buyers` | existing/mapped | overview, products |
| `payment_qty` | 支付件数 | integer/件 | product_day | R1 | 支付件数、支付商品数、`payment_qty` | existing | overview, products |
| `payment_unit_price` | 支付笔单价 | decimal/元 | product_* | R2 | 支付笔单价、笔单价 | mapped/derived | products |
| `order_amount` | 下单金额 | decimal/元 | product_day | R2 | 下单金额、拍下订单金额 | mapped | products |
| `order_buyers` | 下单买家数 | integer/人 | product_day | R2 | 下单买家数 | mapped | products |
| `order_qty` | 下单件数 | integer/件 | product_day | R2 | 下单件数、`order_quantity` | mapped | products |
| `successful_refund_amount` | 成功退款金额 | decimal/元 | product_day, shop_day | R1 | 成功退款金额、退款金额、`refund_amount` | existing/mapped | overview, products |
| `net_sales` | 净销售额 | decimal/元 | product_*, shop_day | R1 | 派生 | derived | overview, products, goals |
| `refund_rate` | 退款率 | decimal/percent | product_*, shop_day | R1 | 退款率、`refund_rate` | existing/derived | overview, products |
| `payment_conversion_rate` | 商品支付转化率 | decimal/percent | product_*, shop_day | R1 | 支付转化率、`payment_conversion` | existing/derived | overview, products |
| `average_order_value` | 客单价 | decimal/元 | product_*, shop_day | R1 | 客单价、UV价值、`avg_order_value` | existing/derived | overview, products |
| `search_conversion_rate` | 搜索支付转化率 | decimal/percent | product_day | R2 | 搜索支付转化率、`search_conversion` | existing/mapped | products |

### 5.1 交易派生公式

| 派生键 | 公式 | 聚合模式 | 依赖 |
|---|---|---|---|
| `net_sales` | `sum(payment_amount) - sum(successful_refund_amount)` | sum_then_derive | payment_amount, successful_refund_amount |
| `refund_rate` | `sum(successful_refund_amount) / sum(payment_amount)` | sum_then_derive | successful_refund_amount, payment_amount |
| `payment_conversion_rate` | `sum(payment_buyers) / sum(product_visitors)` | sum_then_derive | payment_buyers, product_visitors |
| `average_order_value` | `sum(payment_amount) / sum(payment_buyers)` | sum_then_derive | payment_amount, payment_buyers |
| `payment_unit_price` | `sum(payment_amount) / sum(payment_orders)` | sum_then_derive | payment_amount, payment_orders |

## 6. 客户字段

| 标准键 | 中文名 | 类型/单位 | 粒度 | R | 来源列/当前字段 | 状态 | 页面 |
|---|---|---|---|---|---|---|---|
| `new_buyers` | 新客支付买家数 | integer/人 | shop_day, product_day | R1 | 支付新买家数、成交新客数、`new_buyers` | existing/mapped | overview, products |
| `returning_buyers` | 老客支付买家数 | integer/人 | shop_day, product_day | R1 | 支付老买家数、`old_buyers` | mapped | overview, products |
| `new_buyer_ratio` | 新客占比 | decimal/percent | shop_day, product_day | R1 | 成交新客占比、`new_buyer_ratio` | existing/mapped | products |
| `returning_buyer_ratio` | 老客占比 | decimal/percent | shop_day, product_day | R1 | 派生 | derived | overview, products |
| `old_buyer_revenue` | 老客支付金额 | decimal/元 | shop_day, product_day | R2 | 老买家支付金额、`old_buyer_revenue` | mapped | products |
| `repurchase_users` | 复购用户数 | integer/人 | product_* | R2 | 复购用户数、`repurchase_users` | existing/mapped | products, lifecycle |
| `repurchase_rate` | 复购率 | decimal/percent | product_* | R2 | 复购率、`repurchase_rate` | existing | products, lifecycle |
| `member_buyers` | 会员成交人数 | integer/人 | shop_day | 预留 | 会员成交人数 | mapped | products |
| `member_revenue` | 会员成交金额 | decimal/元 | shop_day | 预留 | 会员成交金额 | mapped | products |

公式：`returning_buyer_ratio = sum(returning_buyers) / sum(payment_buyers)`。只有店铺/人群来源提供去重买家数时，才在店铺总览展示；不能把商品老客数简单相加。

## 7. 推广字段

### 7.1 推广维度

| 标准键 | 中文名 | 类型 | 粒度 | R | 来源列 | 状态 |
|---|---|---|---|---|---|---|
| `channel` | 推广渠道 | enum | ad_* | R2 | 直通车、全站推广、万相台/引力魔方 | mapped/pending |
| `campaign_id` | 计划ID | text | ad_unit_day | R2 | 计划ID、场景ID | mapped |
| `campaign_name` | 计划名称 | text | ad_unit_day | R2 | 计划名字、场景名字 | mapped |
| `unit_id` | 单元ID | text | ad_unit_day | R2 | 单元ID | pending |
| `unit_name` | 单元名称 | text | ad_unit_day | R2 | 单元名字 | pending |
| `keyword` | 关键词 | text | ad_unit_day | 预留 | 词名字/词包名字 | mapped |
| `audience_name` | 人群名称 | text | ad_unit_day | 预留 | 人群名字 | mapped |
| `creative_id` | 创意ID | text | ad_unit_day | 预留 | 创意ID | mapped |

### 7.2 推广事实和派生字段

| 标准键 | 中文名 | 类型/单位 | R | 来源列/当前字段 | 状态 |
|---|---|---|---|---|---|
| `ad_spend` | 推广花费 | decimal/元 | R1 | 花费、营销推广消耗、`ad_spend`、`paid_detail.cost` | existing/mapped |
| `ad_deal_amount` | 推广成交金额 | decimal/元 | R2 | 总成交金额、广告成交金额、`paid_detail.total_gmv` | existing/mapped |
| `direct_deal_amount` | 直接成交金额 | decimal/元 | R2 | 直接成交金额、`direct_gmv` | existing/mapped |
| `indirect_deal_amount` | 间接成交金额 | decimal/元 | R2 | 间接成交金额、`indirect_gmv` | existing/mapped |
| `ad_impressions` | 推广展现量 | integer/次 | R2 | 展现量、`paid_detail.impressions` | existing/mapped |
| `ad_clicks` | 推广点击量 | integer/次 | R2 | 点击量、`paid_detail.clicks` | existing/mapped |
| `ad_ctr` | 推广点击率 | decimal/percent | R2 | 点击率、`paid_detail.ctr` | existing/mapped |
| `ad_cpc` | 平均点击花费 | decimal/元 | R2 | 平均点击花费、`paid_detail.cpc` | existing/mapped |
| `ad_cpm` | 千次展现花费 | decimal/元 | R2 | 千次展现花费、`paid_detail.cpm` | existing/mapped |
| `ad_orders` | 推广成交笔数 | integer/笔 | R2 | 总成交笔数、`paid_detail.total_orders` | existing/mapped |
| `ad_cart_qty` | 推广加购数 | integer/次 | R2 | 总购物车数、`paid_detail.cart_adds` | existing/mapped |
| `ad_favorite_qty` | 推广收藏数 | integer/次 | R2 | 总收藏数、`paid_detail.favs` | existing/mapped |
| `ad_roi` | 推广ROI | decimal/ratio | R1 | 推广ROI、`ad_roi`、`paid_detail.roi` | existing/derived |
| `expense_ratio` | 费比 | decimal/percent | R1 | 派生 | derived |
| `paid_ratio` | 付费占比 | decimal/percent | R2 | 付费占比、`paid_ratio` | existing/mapped |

推广公式：

| 派生键 | 公式 |
|---|---|
| `ad_roi` | `sum(ad_deal_amount) / sum(ad_spend)` |
| `expense_ratio` | `sum(ad_spend) / sum(payment_amount)` |
| `ad_ctr` | `sum(ad_clicks) / sum(ad_impressions)` |
| `ad_cpc` | `sum(ad_spend) / sum(ad_clicks)` |
| `ad_cpm` | `sum(ad_spend) / sum(ad_impressions) * 1000` |

## 8. 生命周期和经营管理字段

这些不是导入报表事实，而是 TM 自己维护的业务字段。

### 8.1 生命周期

| 标准键 | 中文名 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| `lifecycle_stage` | 生命周期阶段 | enum | 是 | 新品、成长、爆发、成熟、衰退、清退 |
| `lifecycle_source` | 阶段来源 | enum | 是 | system、manual |
| `lifecycle_confidence` | 阶段置信度 | enum | 是 | high、medium、low |
| `lifecycle_reason` | 阶段判断依据 | text | 是 | 指标、窗口、趋势和数据充分性 |
| `lifecycle_locked` | 阶段是否锁定 | boolean | 是 | 锁定后导入不覆盖 |
| `lifecycle_assessed_at` | 阶段判断时间 | datetime | 是 | 最近一次系统或人工判断时间 |
| `seasonality_type` | 季节属性 | enum | R2 | 稳定、春夏、秋冬、单峰、双峰、大促驱动、无明显 |
| `seasonality_source` | 季节属性来源 | enum | R2 | product、category、manual |
| `seasonality_confidence` | 季节置信度 | enum | R2 | high、medium、low |
| `next_cycle_phase` | 下一时间节点 | enum | R2 | 准备、启动、加速、峰值、回落、收尾、下一周期准备 |
| `next_cycle_date` | 下一节点日期 | date | R2 | 只有中/高置信度才输出 |

### 8.2 商品运营动作

| 标准键 | 中文名 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| `action_id` | 动作ID | text | 是 | 稳定主键 |
| `action_group_id` | 动作组ID | text | 否 | 批量创建时关联 |
| `purpose_type` | 目的类型 | enum | 是 | 提升销售、提升转化、降低退款、降低费比、清库存等 |
| `purpose_note` | 目的说明 | text | 是 | 问题和目标 |
| `action_type` | 动作类型 | enum | 是 | 加价、减价、换图、换标题、调SKU、调推广等 |
| `action_detail` | 动作详情 | text | 是 | 具体执行内容 |
| `action_status` | 动作状态 | enum | 是 | 草稿、待执行、执行中、待观察、待复盘、已完成、阻塞、计算失败、已取消 |
| `planned_at` | 计划时间 | datetime | 是 | 预计执行时间 |
| `executed_at` | 实际执行时间 | datetime | 否 | 执行完成时间 |
| `observer_window_days` | 观察窗口天数 | integer/天 | 是 | 动作后比较窗口 |
| `before_metric_value` | 动作前指标值 | decimal | 否 | 系统回算 |
| `after_metric_value` | 动作后指标值 | decimal | 否 | 系统回算 |
| `result_change` | 指标变化值 | decimal | 否 | 后值减前值 |
| `result_status` | 结果状态 | enum | 否 | 待计算、已计算、数据不足、结果失效、存在重叠 |
| `review_effective` | 是否有效 | boolean | 否 | 复盘填写 |
| `review_conclusion` | 复盘结论 | text | 否 | 经验和判断 |
| `next_action_id` | 后续动作ID | text | 否 | 动作链路 |

## 9. 字段模板

### 9.1 店铺日度经营模板 R1

必填：`stat_date`、`payment_amount`、`successful_refund_amount`、`product_visitors`、`payment_buyers`、`ad_spend`。

建议：`payment_qty`、`search_visitors`、`new_buyers`、`returning_buyers`、`cart_users`、`favorite_users`。

导入后生成：`net_sales`、`refund_rate`、`payment_conversion_rate`、`expense_ratio`、`average_order_value`、`returning_buyer_ratio`。

### 9.2 商品经营模板 R1

必填：`stat_date`、`product_id`、`product_name`、`payment_amount`、`successful_refund_amount`、`product_visitors`、`payment_buyers`、`ad_spend`。

建议：`category`、`product_status`、`payment_qty`、`payment_conversion_rate`、`average_order_value`、`search_visitors`、`search_rate`、`new_buyers`、`returning_buyers`。

主键：`shop_id + product_id + stat_date`。

### 9.3 推广商品模板 R2

必填：`stat_date`、`product_id`、`channel`、`ad_spend`、`ad_deal_amount`。

建议：`campaign_id`、`campaign_name`、`unit_id`、`unit_name`、`ad_impressions`、`ad_clicks`、`direct_deal_amount`、`indirect_deal_amount`、`ad_orders`、`ad_roi`。

粒度按来源选择：`ad_product_day` 或 `ad_unit_day`，不能把不同粒度混在同一导入批次。

### 9.4 生命周期辅助模板 R2

必填：`product_id`、`stat_date`、`payment_amount`、`product_visitors`、`payment_buyers`。

建议：`listed_at`、`product_status`、`payment_conversion_rate`、`successful_refund_amount`、`ad_spend`、`payment_qty`。

如果没有 12 个月完整数据，不导入或不输出季节性结论；字段缺失必须在页面显示。

## 10. 当前 TM 字段覆盖结论

当前 `dashboard.db` 已有 `daily_data`、`weekly_data`、`monthly_data`、`paid_detail` 和 `products`，因此 R1 的支付、退款、访客、转化、推广花费、ROI、商品身份和动作前后部分指标有基础可复用。

当前仍存在明显缺口：

- 店铺级独立日度事实表不足，许多店铺指标需要从商品日度汇总，必须先做对账标记。
- `payment_orders`、推广渠道/计划/单元维度、统一新老客店铺去重事实不完整。
- `operation_actions` 缺少目的、状态、结果说明、复盘、观察窗口和版本字段。
- lifecycle 和 seasonality 的系统建议、置信度、锁定和历史版本字段需要新增。
- 导入批次、字段映射模板、业务唯一键和撤销记录需要补齐或统一。

所以这份字典中标记为 `R1 + existing/mapped` 的字段可以进入快速开发；标记为 `pending` 的字段不能在页面里假装已经存在，必须显示数据不足或等对应报表接入。

## 11. 字段维护规则

1. 新增字段先添加到本字典，再添加数据库、API 或页面代码。
2. 删除字段先标记 `deprecated`，至少保留一个迁移周期，不能直接删列。
3. 修改公式必须同时更新依赖字段、测试样例和页面口径说明。
4. 原始列名变化只修改映射模板，不修改业务标准键。
5. 每种来源报表必须记录来源类型、来源粒度、业务唯一键、字段映射版本和导入批次。
6. 1.0 和 2.0 都引用这份字段定义；1.0 的原生前端使用 snake_case，2.0 迁入 DS 时由 adapter 转为 camelCase。
