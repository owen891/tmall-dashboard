# 数据库表结构文档

## 概述

本文档详细描述天猫数据管理系统的数据库表结构，基于 SQLAlchemy ORM 模型定义。

---

## 核心商品表

### products - 商品基础信息

| 字段名 | 类型 | 可空 | 默认值 | 描述 |
|--------|------|------|--------|------|
| `id` | INTEGER | 否 | 自增 | 主键 |
| `product_id` | VARCHAR | 否 | - | 商品ID（唯一索引） |
| `title` | VARCHAR | 是 | - | 商品标题 |
| `category` | VARCHAR | 是 | - | 商品分类 |
| `tier` | VARCHAR | 是 | - | 商品分层（引流款/利润款/潜力款） |
| `style` | VARCHAR | 是 | - | 款式风格 |
| `scene` | VARCHAR | 是 | - | 使用场景 |
| `list_date` | VARCHAR | 是 | - | 上架日期 |
| `status` | VARCHAR | 是 | active | 状态 |
| `remark` | TEXT | 是 | - | 备注 |
| `image_url` | VARCHAR | 是 | - | 商品图片URL |
| `manager` | VARCHAR | 是 | - | 负责人 |
| `starred` | BOOLEAN | 是 | false | 是否星标 |
| `created_at` | DATETIME | 是 | 当前时间 | 创建时间 |
| `updated_at` | DATETIME | 是 | 当前时间 | 更新时间 |

---

## 数据统计表

### daily_data - 日数据

| 字段名 | 类型 | 可空 | 默认值 | 描述 |
|--------|------|------|--------|------|
| `id` | INTEGER | 否 | 自增 | 主键 |
| `product_id` | VARCHAR | 否 | - | 商品ID（索引） |
| `date` | VARCHAR | 否 | - | 日期（索引） |
| `payment_amount` | FLOAT | 是 | 0 | 支付金额 |
| `refund_amount` | FLOAT | 是 | 0 | 退款金额 |
| `net_sales` | FLOAT | 是 | 0 | 净销售额 |
| `payment_qty` | INTEGER | 是 | 0 | 支付件数 |
| `ipv` | INTEGER | 是 | 0 | 访客数 |
| `pv` | INTEGER | 是 | 0 | 浏览量 |
| `search_ipv` | INTEGER | 是 | 0 | 搜索访客 |
| `recommend_ipv` | INTEGER | 是 | 0 | 推荐访客 |
| `paid_ipv` | INTEGER | 是 | 0 | 付费访客 |
| `organic_ipv` | INTEGER | 是 | 0 | 自由访客 |
| `payment_conversion` | FLOAT | 是 | 0 | 支付转化率 |
| `cart_rate` | FLOAT | 是 | 0 | 加购率 |
| `fav_rate` | FLOAT | 是 | 0 | 收藏率 |
| `bounce_rate` | FLOAT | 是 | 0 | 跳出率 |
| `avg_stay_duration` | FLOAT | 是 | 0 | 平均停留时长 |
| `ad_spend` | FLOAT | 是 | 0 | 广告花费 |
| `ad_roi` | FLOAT | 是 | 0 | 广告ROI |
| `buyers` | INTEGER | 是 | 0 | 买家数 |
| `avg_order_value` | FLOAT | 是 | 0 | 平均订单价值 |
| `data_source` | VARCHAR | 是 | - | 数据来源 |
| `imported_at` | DATETIME | 是 | 当前时间 | 导入时间 |
| `uv_value` | FLOAT | 是 | 0 | UV价值 |
| `cart_qty` | INTEGER | 是 | 0 | 加购件数 |
| `fav_users` | INTEGER | 是 | 0 | 收藏用户数 |
| `search_conversion` | FLOAT | 是 | 0 | 搜索转化率 |
| `search_visitors` | INTEGER | 是 | 0 | 搜索访客数 |
| `cart_users` | INTEGER | 是 | 0 | 加购用户数 |

### weekly_data - 周数据

| 字段名 | 类型 | 可空 | 默认值 | 描述 |
|--------|------|------|--------|------|
| `id` | INTEGER | 否 | 自增 | 主键 |
| `product_id` | VARCHAR | 否 | - | 商品ID（索引） |
| `week_start` | VARCHAR | 否 | - | 周起始日期（索引） |
| `payment_amount` | FLOAT | 是 | 0 | 支付金额 |
| `refund_amount` | FLOAT | 是 | 0 | 退款金额 |
| `net_sales` | FLOAT | 是 | 0 | 净销售额 |
| `presale_amount` | FLOAT | 是 | 0 | 预售金额 |
| `presale_qty` | INTEGER | 是 | 0 | 预售件数 |
| `ipv` | INTEGER | 是 | 0 | 访客数 |
| `pv` | INTEGER | 是 | 0 | 浏览量 |
| `search_ipv` | INTEGER | 是 | 0 | 搜索访客 |
| `recommend_ipv` | INTEGER | 是 | 0 | 推荐访客 |
| `paid_ipv` | INTEGER | 是 | 0 | 付费访客 |
| `organic_ipv` | INTEGER | 是 | 0 | 自由访客 |
| `payment_conversion` | FLOAT | 是 | 0 | 支付转化率 |
| `cart_rate` | FLOAT | 是 | 0 | 加购率 |
| `fav_rate` | FLOAT | 是 | 0 | 收藏率 |
| `search_click_rate` | FLOAT | 是 | 0 | 搜索点击率 |
| `bounce_rate` | FLOAT | 是 | 0 | 跳出率 |
| `avg_stay_duration` | FLOAT | 是 | 0 | 平均停留时长 |
| `ad_spend` | FLOAT | 是 | 0 | 广告花费 |
| `ad_roi` | FLOAT | 是 | 0 | 广告ROI |
| `repurchase_rate` | FLOAT | 是 | 0 | 复购率 |
| `repurchase_users` | INTEGER | 是 | 0 | 复购用户数 |
| `cross_sell_qty` | INTEGER | 是 | 0 | 跨店销售件数 |
| `cross_sell_rate` | FLOAT | 是 | 0 | 跨店销售率 |
| `avg_order_value` | FLOAT | 是 | 0 | 平均订单价值 |
| `category_width` | INTEGER | 是 | 0 | 类目宽度 |
| `action_1` | TEXT | 是 | - | 运营动作1 |
| `action_2` | TEXT | 是 | - | 运营动作2 |
| `data_source` | VARCHAR | 是 | - | 数据来源 |
| `imported_at` | DATETIME | 是 | 当前时间 | 导入时间 |
| `industry_ctr` | FLOAT | 是 | 0 | 行业CTR |

### monthly_data - 月数据

| 字段名 | 类型 | 可空 | 默认值 | 描述 |
|--------|------|------|--------|------|
| `id` | INTEGER | 否 | 自增 | 主键 |
| `product_id` | VARCHAR | 否 | - | 商品ID（索引） |
| `month` | VARCHAR | 否 | - | 月份（索引） |
| `payment_amount` | FLOAT | 是 | 0 | 支付金额 |
| `refund_amount` | FLOAT | 是 | 0 | 退款金额 |
| `net_sales` | FLOAT | 是 | 0 | 净销售额 |
| `visitors` | INTEGER | 是 | 0 | 访客数 |
| `page_views` | INTEGER | 是 | 0 | 页面浏览量 |
| `uv_value` | FLOAT | 是 | 0 | UV价值 |
| `search_visitors` | INTEGER | 是 | 0 | 搜索访客 |
| `search_ratio` | FLOAT | 是 | 0 | 搜索占比 |
| `payment_conversion` | FLOAT | 是 | 0 | 支付转化率 |
| `search_conversion` | FLOAT | 是 | 0 | 搜索转化率 |
| `cart_rate` | FLOAT | 是 | 0 | 加购率 |
| `fav_rate` | FLOAT | 是 | 0 | 收藏率 |
| `bounce_rate` | FLOAT | 是 | 0 | 跳出率 |
| `avg_stay_duration` | FLOAT | 是 | 0 | 平均停留时长 |
| `ad_spend` | FLOAT | 是 | 0 | 广告花费 |
| `ad_roi` | FLOAT | 是 | 0 | 广告ROI |
| `overall_roi` | FLOAT | 是 | 0 | 全店ROI |
| `paid_ratio` | FLOAT | 是 | 0 | 付费占比 |
| `refund_paid_ratio` | FLOAT | 是 | 0 | 退款支付比 |
| `keyword_spend` | FLOAT | 是 | 0 | 关键词花费 |
| `keyword_sales` | FLOAT | 是 | 0 | 关键词销售额 |
| `keyword_roi` | FLOAT | 是 | 0 | 关键词ROI |
| `keyword_visitors` | INTEGER | 是 | 0 | 关键词访客 |
| `keyword_ppc` | FLOAT | 是 | 0 | 关键词PPC |
| `crowd_spend` | FLOAT | 是 | 0 | 人群花费 |
| `crowd_sales` | FLOAT | 是 | 0 | 人群销售额 |
| `crowd_roi` | FLOAT | 是 | 0 | 人群ROI |
| `crowd_visitors` | INTEGER | 是 | 0 | 人群访客 |
| `crowd_ppc` | FLOAT | 是 | 0 | 人群PPC |
| `site_spend` | FLOAT | 是 | 0 | 站外花费 |
| `site_sales` | FLOAT | 是 | 0 | 站外销售额 |
| `site_roi` | FLOAT | 是 | 0 | 站外ROI |
| `site_visitors` | INTEGER | 是 | 0 | 站外访客 |
| `site_ppc` | FLOAT | 是 | 0 | 站外PPC |
| `refund_rate` | FLOAT | 是 | 0 | 退款率 |
| `repurchase_rate` | FLOAT | 是 | 0 | 复购率 |
| `cross_sell_rate` | FLOAT | 是 | 0 | 跨店销售率 |
| `buyers` | INTEGER | 是 | 0 | 买家数 |
| `avg_order_value` | FLOAT | 是 | 0 | 平均订单价值 |
| `payment_qty` | INTEGER | 是 | 0 | 支付件数 |
| `cart_qty` | INTEGER | 是 | 0 | 加购件数 |
| `fav_users` | INTEGER | 是 | 0 | 收藏用户数 |
| `click_rate` | FLOAT | 是 | 0 | 点击率 |
| `score` | INTEGER | 是 | 0 | 评分 |
| `data_source` | VARCHAR | 是 | - | 数据来源 |
| `imported_at` | DATETIME | 是 | 当前时间 | 导入时间 |
| `paid_ipv` | INTEGER | 是 | 0 | 付费访客 |
| `organic_ipv` | INTEGER | 是 | 0 | 自由访客 |
| `search_ipv` | INTEGER | 是 | 0 | 搜索访客 |
| `recommend_ipv` | INTEGER | 是 | 0 | 推荐访客 |
| `cart_users` | INTEGER | 是 | 0 | 加购用户数 |
| `industry_ctr` | FLOAT | 是 | 0 | 行业CTR |
| `cross_sell_qty` | INTEGER | 是 | 0 | 跨店销售件数 |
| `cross_sell_categories` | INTEGER | 是 | 0 | 跨店类目数 |
| `repurchase_users` | INTEGER | 是 | 0 | 复购用户数 |
| `guide_visits` | INTEGER | 是 | 0 | 引导访问 |
| `guide_visitors` | INTEGER | 是 | 0 | 引导访客 |
| `guide_potential` | INTEGER | 是 | 0 | 引导潜力 |
| `guide_potential_ratio` | FLOAT | 是 | 0 | 引导潜力比 |
| `new_buyers` | INTEGER | 是 | 0 | 新买家数 |
| `new_buyer_ratio` | FLOAT | 是 | 0 | 新买家占比 |

---

## 商品关联表

### product_tags - 商品标签

| 字段名 | 类型 | 可空 | 默认值 | 描述 |
|--------|------|------|--------|------|
| `id` | INTEGER | 否 | 自增 | 主键 |
| `product_id` | VARCHAR | 否 | - | 商品ID（索引） |
| `tag` | VARCHAR | 否 | - | 标签内容 |
| `is_auto` | BOOLEAN | 是 | false | 是否自动生成 |
| `created_at` | DATETIME | 是 | 当前时间 | 创建时间 |

### product_notes - 商品备注

| 字段名 | 类型 | 可空 | 默认值 | 描述 |
|--------|------|------|--------|------|
| `id` | INTEGER | 否 | 自增 | 主键 |
| `product_id` | VARCHAR | 否 | - | 商品ID（索引） |
| `note` | TEXT | 否 | - | 备注内容 |
| `created_by` | VARCHAR | 是 | admin | 创建人 |
| `created_at` | DATETIME | 是 | 当前时间 | 创建时间 |

### product_custom_fields - 自定义字段

| 字段名 | 类型 | 可空 | 默认值 | 描述 |
|--------|------|------|--------|------|
| `id` | INTEGER | 否 | 自增 | 主键 |
| `product_id` | VARCHAR | 否 | - | 商品ID（索引） |
| `field_key` | VARCHAR | 否 | - | 字段键（索引） |
| `field_value` | TEXT | 是 | - | 字段值 |
| `field_type` | VARCHAR | 是 | text | 字段类型 |
| `created_at` | DATETIME | 是 | 当前时间 | 创建时间 |
| `updated_at` | DATETIME | 是 | 当前时间 | 更新时间 |

### operation_actions - 运营动作

| 字段名 | 类型 | 可空 | 默认值 | 描述 |
|--------|------|------|--------|------|
| `id` | INTEGER | 否 | 自增 | 主键 |
| `product_id` | VARCHAR | 否 | - | 商品ID（索引） |
| `action_date` | VARCHAR | 否 | - | 动作日期 |
| `action_type` | VARCHAR | 是 | - | 动作类型 |
| `action_detail` | TEXT | 是 | - | 动作详情 |
| `before_payment` | FLOAT | 是 | 0 | 操作前支付金额 |
| `before_visitors` | INTEGER | 是 | 0 | 操作前访客数 |
| `before_conversion` | FLOAT | 是 | 0 | 操作前转化率 |
| `before_roi` | FLOAT | 是 | 0 | 操作前ROI |
| `after_payment` | FLOAT | 是 | 0 | 操作后支付金额 |
| `after_visitors` | INTEGER | 是 | 0 | 操作后访客数 |
| `after_conversion` | FLOAT | 是 | 0 | 操作后转化率 |
| `after_roi` | FLOAT | 是 | 0 | 操作后ROI |
| `payment_change` | FLOAT | 是 | 0 | 支付金额变化 |
| `conversion_change` | FLOAT | 是 | 0 | 转化率变化 |
| `roi_change` | FLOAT | 是 | 0 | ROI变化 |
| `effectiveness_score` | FLOAT | 是 | 0 | 效果评分 |
| `imported_at` | DATETIME | 是 | 当前时间 | 导入时间 |

---

## 分析表

### product_health - 商品健康度

| 字段名 | 类型 | 可空 | 默认值 | 描述 |
|--------|------|------|--------|------|
| `id` | INTEGER | 否 | 自增 | 主键 |
| `product_id` | VARCHAR | 否 | - | 商品ID（索引） |
| `period` | VARCHAR | 否 | - | 周期 |
| `sales_score` | FLOAT | 是 | 0 | 销售评分 |
| `conversion_score` | FLOAT | 是 | 0 | 转化评分 |
| `roi_score` | FLOAT | 是 | 0 | ROI评分 |
| `refund_score` | FLOAT | 是 | 0 | 退款评分 |
| `growth_score` | FLOAT | 是 | 0 | 增长评分 |
| `review_score` | FLOAT | 是 | 0 | 评价评分 |
| `gmv_change_score` | FLOAT | 是 | 0 | GMV变化评分 |
| `ad_spend_change_score` | FLOAT | 是 | 0 | 广告花费变化评分 |
| `roi_change_score` | FLOAT | 是 | 0 | ROI变化评分 |
| `refund_rate_score` | FLOAT | 是 | 0 | 退款率评分 |
| `cart_rate_score` | FLOAT | 是 | 0 | 加购率评分 |
| `search_ratio_score` | FLOAT | 是 | 0 | 搜索占比评分 |
| `new_customer_cost_score` | FLOAT | 是 | 0 | 新客成本评分 |
| `direct_cart_cost_score` | FLOAT | 是 | 0 | 直通车成本评分 |
| `total_cart_cost_score` | FLOAT | 是 | 0 | 总推广成本评分 |
| `repurchase_rate_score` | FLOAT | 是 | 0 | 复购率评分 |
| `cross_sell_rate_score` | FLOAT | 是 | 0 | 跨店销售率评分 |
| `search_ctr_vs_industry_score` | FLOAT | 是 | 0 | 搜索CTR对比行业评分 |
| `health_score` | FLOAT | 是 | 0 | 健康度总分 |
| `health_level` | VARCHAR | 是 | - | 健康等级 |
| `alert_dimensions` | TEXT | 是 | - | 告警维度 |
| `created_at` | DATETIME | 是 | 当前时间 | 创建时间 |

### paid_detail - 付费推广详情

| 字段名 | 类型 | 可空 | 默认值 | 描述 |
|--------|------|------|--------|------|
| `id` | INTEGER | 否 | 自增 | 主键 |
| `product_id` | VARCHAR | 否 | - | 商品ID（索引） |
| `date_range` | VARCHAR | 否 | - | 日期范围 |
| `impressions` | INTEGER | 是 | 0 | 展现量 |
| `clicks` | INTEGER | 是 | 0 | 点击量 |
| `cost` | FLOAT | 是 | 0 | 花费 |
| `ctr` | FLOAT | 是 | 0 | 点击率 |
| `cpc` | FLOAT | 是 | 0 | 点击单价 |
| `cpm` | FLOAT | 是 | 0 | 千次展现成本 |
| `total_gmv` | FLOAT | 是 | 0 | 总GMV |
| `total_orders` | INTEGER | 是 | 0 | 总订单数 |
| `direct_gmv` | FLOAT | 是 | 0 | 直接GMV |
| `indirect_gmv` | FLOAT | 是 | 0 | 间接GMV |
| `roi` | FLOAT | 是 | 0 | ROI |
| `cart_adds` | INTEGER | 是 | 0 | 加购数 |
| `cart_rate` | FLOAT | 是 | 0 | 加购率 |
| `favs` | INTEGER | 是 | 0 | 收藏数 |
| `new_buyers` | INTEGER | 是 | 0 | 新买家数 |
| `members_gmv` | FLOAT | 是 | 0 | 会员GMV |
| `imported_at` | DATETIME | 是 | 当前时间 | 导入时间 |
| `direct_orders` | INTEGER | 是 | 0 | 直接订单数 |
| `indirect_orders` | INTEGER | 是 | 0 | 间接订单数 |
| `click_conversion` | FLOAT | 是 | 0 | 点击转化率 |
| `presale_roi` | FLOAT | 是 | 0 | 预售ROI |
| `total_cost` | FLOAT | 是 | 0 | 总花费 |
| `direct_cart_adds` | INTEGER | 是 | 0 | 直接加购数 |
| `indirect_cart_adds` | INTEGER | 是 | 0 | 间接加购数 |
| `store_favs` | INTEGER | 是 | 0 | 店铺收藏数 |
| `store_fav_cost` | FLOAT | 是 | 0 | 店铺收藏成本 |
| `total_fav_cart` | INTEGER | 是 | 0 | 总收藏加购数 |
| `total_fav_cart_cost` | FLOAT | 是 | 0 | 总收藏加购成本 |
| `item_fav_cart` | INTEGER | 是 | 0 | 商品收藏加购数 |
| `item_fav_cart_cost` | FLOAT | 是 | 0 | 商品收藏加购成本 |
| `total_favs` | INTEGER | 是 | 0 | 总收藏数 |
| `item_fav_cost` | FLOAT | 是 | 0 | 商品收藏成本 |
| `item_fav_rate` | FLOAT | 是 | 0 | 商品收藏率 |
| `cart_cost` | FLOAT | 是 | 0 | 加购成本 |

---

## 退款与评价表

### refunds - 退款记录

| 字段名 | 类型 | 可空 | 默认值 | 描述 |
|--------|------|------|--------|------|
| `id` | INTEGER | 否 | 自增 | 主键 |
| `product_id` | VARCHAR | 否 | - | 商品ID（索引） |
| `product_name` | VARCHAR | 是 | - | 商品名称 |
| `refund_date` | VARCHAR | 是 | - | 退款日期 |
| `refund_count` | INTEGER | 是 | 0 | 退款数量 |
| `refund_amount` | FLOAT | 是 | 0 | 退款金额 |
| `refund_rate` | FLOAT | 是 | 0 | 退款率 |
| `refund_reason` | VARCHAR | 是 | - | 退款原因 |
| `refund_days` | INTEGER | 是 | 0 | 退款天数 |
| `created_at` | DATETIME | 是 | 当前时间 | 创建时间 |

### reviews - 评价记录

| 字段名 | 类型 | 可空 | 默认值 | 描述 |
|--------|------|------|--------|------|
| `id` | INTEGER | 否 | 自增 | 主键 |
| `product_id` | VARCHAR | 否 | - | 商品ID（索引） |
| `review_date` | VARCHAR | 是 | - | 评价日期 |
| `content` | TEXT | 否 | - | 评价内容 |
| `rating` | INTEGER | 是 | 5 | 评分 |
| `reviewer` | VARCHAR | 是 | - | 评价人 |
| `is_effective` | BOOLEAN | 是 | false | 是否有效 |
| `sentiment` | VARCHAR | 是 | neutral | 情感倾向 |
| `positive_dims` | TEXT | 是 | - | 正面维度 |
| `negative_dims` | TEXT | 是 | - | 负面维度 |
| `scenes` | TEXT | 是 | - | 使用场景 |
| `has_image` | BOOLEAN | 是 | false | 是否有图 |
| `source` | VARCHAR | 是 | - | 来源 |
| `imported_at` | DATETIME | 是 | 当前时间 | 导入时间 |

### review_summary - 评价汇总

| 字段名 | 类型 | 可空 | 默认值 | 描述 |
|--------|------|------|--------|------|
| `id` | INTEGER | 否 | 自增 | 主键 |
| `product_id` | VARCHAR | 否 | - | 商品ID（索引） |
| `analysis_date` | VARCHAR | 是 | - | 分析日期 |
| `total_reviews` | INTEGER | 是 | 0 | 总评价数 |
| `positive_rate` | FLOAT | 是 | 0 | 好评率 |
| `negative_rate` | FLOAT | 是 | 0 | 差评率 |
| `effective_rate` | FLOAT | 是 | 0 | 有效评价率 |
| `top_positive_dims` | TEXT | 是 | - | 热门正面维度 |
| `top_negative_dims` | TEXT | 是 | - | 热门负面维度 |
| `top_scenes` | TEXT | 是 | - | 热门使用场景 |
| `updated_at` | DATETIME | 是 | 当前时间 | 更新时间 |

---

## 市场分析表

### market_analysis - 市场分析

| 字段名 | 类型 | 可空 | 默认值 | 描述 |
|--------|------|------|--------|------|
| `id` | INTEGER | 否 | 自增 | 主键 |
| `analysis_date` | VARCHAR | 是 | - | 分析日期 |
| `category_path` | VARCHAR | 是 | - | 类目路径 |
| `category_short` | VARCHAR | 是 | - | 简短类目 |
| `period_30d` | VARCHAR | 是 | - | 30天周期 |
| `period_7d` | VARCHAR | 是 | - | 7天周期 |
| `period_trend` | VARCHAR | 是 | - | 周期趋势 |
| `total_keywords` | INTEGER | 是 | 0 | 总关键词数 |
| `avg_ctr_7d` | FLOAT | 是 | 0 | 7天平均CTR |
| `avg_cvr_30d` | FLOAT | 是 | 0 | 30天平均CVR |
| `top5_keywords` | TEXT | 是 | - | TOP5关键词 |
| `summary_data` | TEXT | 是 | - | 汇总数据 |
| `keywords_data` | TEXT | 是 | - | 关键词数据 |
| `need_stats_data` | TEXT | 是 | - | 需求统计数据 |
| `dimension_details` | TEXT | 是 | - | 维度详情 |
| `histograms_data` | TEXT | 是 | - | 直方图数据 |
| `rankings_data` | TEXT | 是 | - | 排名数据 |
| `created_at` | DATETIME | 是 | 当前时间 | 创建时间 |

### market_keyword_opportunities - 关键词机会

| 字段名 | 类型 | 可空 | 默认值 | 描述 |
|--------|------|------|--------|------|
| `id` | INTEGER | 否 | 自增 | 主键 |
| `analysis_date` | VARCHAR | 是 | - | 分析日期 |
| `keyword` | VARCHAR | 否 | - | 关键词 |
| `pop_30d` | FLOAT | 是 | 0 | 30天搜索量 |
| `ctr_7d` | FLOAT | 是 | 0 | 7天CTR |
| `cvr_30d` | FLOAT | 是 | 0 | 30天CVR |
| `opportunity_category` | VARCHAR | 是 | - | 机会类目 |
| `opportunity_score` | FLOAT | 是 | 0 | 机会评分 |
| `need_tags` | TEXT | 是 | - | 需求标签 |
| `created_at` | DATETIME | 是 | 当前时间 | 创建时间 |

---

## 目标与告警表

### shop_targets - 店铺目标

| 字段名 | 类型 | 可空 | 默认值 | 描述 |
|--------|------|------|--------|------|
| `id` | INTEGER | 否 | 自增 | 主键 |
| `period` | VARCHAR | 否 | - | 周期（索引） |
| `target_gsv` | FLOAT | 是 | 0 | 目标销售额 |
| `target_ad_spend` | FLOAT | 是 | 0 | 目标广告花费 |
| `target_ad_ratio` | FLOAT | 是 | 0 | 目标广告占比 |
| `target_conversion` | FLOAT | 是 | 0 | 目标转化率 |
| `target_refund_rate` | FLOAT | 是 | 0 | 目标退款率 |
| `remark` | TEXT | 是 | - | 备注 |
| `created_at` | DATETIME | 是 | 当前时间 | 创建时间 |

### product_targets - 商品目标

| 字段名 | 类型 | 可空 | 默认值 | 描述 |
|--------|------|------|--------|------|
| `id` | INTEGER | 否 | 自增 | 主键 |
| `product_id` | VARCHAR | 是 | - | 商品ID（索引） |
| `tier` | VARCHAR | 是 | - | 分层 |
| `period` | VARCHAR | 否 | - | 周期（索引） |
| `target_gsv` | FLOAT | 是 | 0 | 目标销售额 |
| `target_ad_spend` | FLOAT | 是 | 0 | 目标广告花费 |
| `target_ad_ratio` | FLOAT | 是 | 0 | 目标广告占比 |
| `remark` | TEXT | 是 | - | 备注 |
| `created_at` | DATETIME | 是 | 当前时间 | 创建时间 |

### alerts - 告警记录

| 字段名 | 类型 | 可空 | 默认值 | 描述 |
|--------|------|------|--------|------|
| `id` | INTEGER | 否 | 自增 | 主键 |
| `alert_date` | VARCHAR | 是 | - | 告警日期 |
| `alert_type` | VARCHAR | 否 | - | 告警类型（索引） |
| `severity` | VARCHAR | 是 | warning | 严重程度 |
| `title` | VARCHAR | 是 | - | 告警标题 |
| `detail` | TEXT | 是 | - | 告警详情 |
| `metric_name` | VARCHAR | 是 | - | 指标名称 |
| `current_value` | FLOAT | 是 | 0 | 当前值 |
| `target_value` | FLOAT | 是 | 0 | 目标值 |
| `period` | VARCHAR | 是 | - | 周期 |
| `dismissed` | BOOLEAN | 是 | false | 是否已忽略 |
| `created_at` | DATETIME | 是 | 当前时间 | 创建时间 |

### alert_rules - 告警规则

| 字段名 | 类型 | 可空 | 默认值 | 描述 |
|--------|------|------|--------|------|
| `id` | INTEGER | 否 | 自增 | 主键 |
| `metric` | VARCHAR | 否 | - | 指标名称 |
| `operator` | VARCHAR | 否 | - | 操作符 |
| `threshold` | FLOAT | 否 | - | 阈值 |
| `level` | VARCHAR | 是 | warning | 告警级别 |
| `enabled` | BOOLEAN | 是 | true | 是否启用 |
| `created_at` | DATETIME | 是 | 当前时间 | 创建时间 |

---

## 辅助表

### chart_events - 趋势事件

| 字段名 | 类型 | 可空 | 默认值 | 描述 |
|--------|------|------|--------|------|
| `id` | INTEGER | 否 | 自增 | 主键 |
| `event_date` | VARCHAR | 否 | - | 事件日期 |
| `title` | VARCHAR | 是 | - | 事件标题 |
| `description` | TEXT | 是 | - | 事件描述 |
| `color` | VARCHAR | 是 | #EF4444 | 事件颜色 |
| `chart_type` | VARCHAR | 否 | - | 图表类型 |
| `created_at` | DATETIME | 是 | 当前时间 | 创建时间 |

### scheduled_tasks - 定时任务

| 字段名 | 类型 | 可空 | 默认值 | 描述 |
|--------|------|------|--------|------|
| `id` | INTEGER | 否 | 自增 | 主键 |
| `task_name` | VARCHAR | 否 | - | 任务名称 |
| `task_type` | VARCHAR | 是 | - | 任务类型 |
| `cron_expr` | VARCHAR | 是 | - | Cron表达式 |
| `file_pattern` | VARCHAR | 是 | - | 文件匹配模式 |
| `enabled` | BOOLEAN | 是 | true | 是否启用 |
| `last_run` | VARCHAR | 是 | - | 上次运行时间 |
| `next_run` | VARCHAR | 是 | - | 下次运行时间 |
| `status` | VARCHAR | 是 | - | 任务状态 |
| `created_at` | DATETIME | 是 | 当前时间 | 创建时间 |

### operation_logs - 操作日志

| 字段名 | 类型 | 可空 | 默认值 | 描述 |
|--------|------|------|--------|------|
| `id` | INTEGER | 否 | 自增 | 主键 |
| `action` | TEXT | 否 | - | 操作动作 |
| `detail` | TEXT | 是 | - | 操作详情 |
| `operator` | VARCHAR | 是 | - | 操作人 |
| `created_at` | DATETIME | 是 | 当前时间 | 创建时间 |

---

## 索引说明

### 主键索引
- 所有表都有自增主键 `id`

### 唯一索引
- `products.product_id` - 确保商品ID唯一

### 普通索引
- `daily_data.product_id`, `daily_data.date`
- `weekly_data.product_id`, `weekly_data.week_start`
- `monthly_data.product_id`, `monthly_data.month`
- `product_tags.product_id`
- `product_notes.product_id`
- `product_custom_fields.product_id`, `product_custom_fields.field_key`
- `operation_actions.product_id`
- `product_health.product_id`
- `paid_detail.product_id`
- `refunds.product_id`
- `reviews.product_id`
- `review_summary.product_id`
- `shop_targets.period`
- `product_targets.product_id`, `product_targets.period`
- `alerts.alert_type`

---

## 外键关系

```
products (1) ←→ (N) daily_data
products (1) ←→ (N) weekly_data
products (1) ←→ (N) monthly_data
products (1) ←→ (N) product_tags
products (1) ←→ (N) product_notes
products (1) ←→ (N) product_custom_fields
products (1) ←→ (N) operation_actions
products (1) ←→ (N) product_health
products (1) ←→ (N) paid_detail
products (1) ←→ (N) refunds
products (1) ←→ (N) reviews
products (1) ←→ (N) review_summary
products (1) ←→ (N) product_targets
```

---

## 数据导入说明

数据主要通过以下方式导入：
1. **Excel 导入**：通过 `/api/import/excel` 接口导入
2. **简单导入脚本**：`backend/simple_import.py`
3. **手动导入**：通过后台管理界面

导入时注意：
- 确保日期格式正确（YYYY-MM-DD 或 YYYY-MM）
- 确保数值字段为空或有效数字
- 确保商品ID存在且唯一
