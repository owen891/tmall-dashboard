# 海贝海数据导入指南 - 新架构

## 概述

本指南说明如何将原始数据源 (F:\bi\海贝海\原始数据) 导入到新架构数据库中。

## 支持的文件类型

导入脚本会自动识别以下文件类型：

| 文件类型 | 文件名特征 | 导入表 |
|---------|----------|--------|
| 智能选款 | `智能选款_*.xlsx` | `products`, `monthly_data` |
| TOP N 商品 | `TOP*单品_*.xlsx`, `top*整体_*.xlsx` | `product_ranking`, `products` |
| 流量来源 | `*来源_*.xlsx`, `*traffic_*.xlsx` | `traffic_structure` |
| 搜索排行 | `搜索排行_*.xlsx`, `*关键词_*.xlsx` | `keyword_metrics` |
| 店铺日数据 | `*店铺*日*.xlsx` | `daily_metrics` |
| 品类数据 | `品类-*.xls` | `market_analysis` (待完善) |
| 市场排行 | `市场排行_*.xlsx` | `market_analysis` (待完善) |
| 生意参谋 | `【生意参谋平台】商品_*.xls` | `products`, `daily_data` (待完善) |

## 新架构数据模型

### 核心表

| 表名 | 用途 |
|------|------|
| `products` | 商品基本信息 (ID, 标题, 类目, 图片等) |
| `monthly_data` | 月度商品数据 (销量, 访客, 转化等) |
| `weekly_data` | 周度商品数据 |
| `daily_data` | 每日商品数据 |
| `traffic_structure` | 每日流量结构 |
| `keyword_metrics` | 关键词效能数据 |
| `daily_metrics` | 全店每日指标 |
| `product_ranking` | 商品排名数据 |
| `product_health` | 商品健康度数据 |
| `dmp_crowd` | DMP/达摩盘人群数据 |
| `wxt_campaign` | WXT/万相台活动数据 |

## 使用方法

### 1. 导入数据

使用我们创建的导入脚本：

```bash
cd backend
python import_raw_data.py
```

或者指定自定义源目录：

```bash
cd backend
python import_raw_data.py "D:\\Other\\Path\\Data"
```

脚本会自动：
- 扫描源目录下的所有Excel文件和ZIP压缩包
- 自动解压ZIP文件并处理内部的Excel文件
- 自动识别文件类型
- 智能查找表头位置
- 导入数据到对应的表中
- 去重更新（已存在的商品自动更新）
- 打印导入统计

### 2. 启动后端服务

```bash
cd backend
python run.py
```

API文档地址: http://localhost:8000/docs

### 3. 启动前端服务（开发模式）

```bash
cd frontend
npm install
npm run dev
```

前端地址: http://localhost:5173

## 数据匹配规则详解

### 智能选款文件导入规则

文件名格式: `智能选款_2026-04-20~2026-04-26.xlsx`

识别的Excel列名:
- 商品ID → `product_id`
- 商品标题 → `title`
- 商品类目 → `category`
- 支付金额 → `payment_amount`
- 退款金额 → `refund_amount`
- 退款后销售额 → `net_sales`
- 访客数 → `visitors`
- 浏览量 → `page_views`
- UV价值 → `uv_value`
- 搜索人数 → `search_visitors`
- 搜索占比 → `search_ratio`
- 支付转化率 → `payment_conversion`
- 搜索支付转化率 → `search_conversion`
- 加购率 → `cart_rate`
- 访客收藏率 → `fav_rate`
- 跳失率 → `bounce_rate`
- 平均停留时长 → `avg_stay_duration`
- 总推广花费 → `ad_spend`
- 推广直接ROI → `ad_roi`
- 总投产 → `overall_roi`
- 关键词推广花费 → `keyword_spend`
- 关键词推广销售额 → `keyword_sales`
- 关键词推广投产 → `keyword_roi`
- 关键词推广访客数 → `keyword_visitors`
- 关键词推广PPC → `keyword_ppc`
- 人群推广花费 → `crowd_spend`
- 人群推广销售额 → `crowd_sales`
- 人群推广投产 → `crowd_roi`
- 人群推广访客数 → `crowd_visitors`
- 人群推广PPC → `crowd_ppc`
- 货品全站推广花费 → `site_spend`
- 货品全站推广销售额 → `site_sales`
- 货品全站推广投产 → `site_roi`
- 货品全站推广访客数 → `site_visitors`
- 货品全站推广PPC → `site_ppc`
- 退款率 → `refund_rate`
- 复购率 → `repurchase_rate`
- 连带率 → `cross_sell_rate`
- 支付人数 → `buyers`
- 客单价 → `avg_order_value`
- 支付件数 → `payment_qty`
- 加购件数 → `cart_qty`
- 收藏人数 → `fav_users`
- 总点击率 → `click_rate`
- 评分 → `score`

### 流量来源文件导入规则

识别的Excel列名:
- 访客数, UV → `total_uv`
- 搜索, 搜索访客 → `search_uv`
- 推荐 → `recommend_uv`
- 直通车, ZTC → `ztc_uv`
- 万相台, WXT → `wxt_uv`

### 搜索排行/关键词文件导入规则

识别的Excel列名:
- 关键词, 搜索词 → `keyword`
- 搜索人气, 热度 → `popularity`
- 曝光, 展现 → `impressions`
- 点击, 点击量 → `clicks`
- 点击率 → `ctr`
- 转化率 → `cvr`
- GMV, 交易金额 → `gmv`
- 花费, 消耗 → `cost`
- ROI, 投产 → `roi`

### TOP N 商品导入规则

识别的Excel列名:
- 商品ID, 宝贝ID, 货号 → `product_id`
- 商品标题, 标题 → `title`
- 交易金额, 支付金额, GMV → `sales_30d`
- 排名（自动生成） → `sales_rank`

## 数据库位置

新架构数据库文件:
```
backend/data/db/dashboard.db
```

## 数据验证

导入后可以通过以下方式验证数据：

### 1. 通过API文档

访问 http://localhost:8000/docs 查看并测试API

### 2. 通过前端界面

打开前端应用查看数据是否正常显示

## 常见问题

### Q: 导入时报错找不到模块？

A: 确保在backend目录运行，并安装了依赖：
```bash
pip install -r requirements.txt
```

### Q: Excel文件解析失败？

A: 确保Excel文件格式正确，有完整的表头和数据

### Q: 数据导入了但前端看不到？

A: 检查是否在正确的分支（trae/solo-agent-80vGxp）并重启了服务

### Q: 只导入了一部分文件？

A: 可能某些文件格式特殊，脚本会跳过并继续处理其他文件。查看控制台错误信息。

### Q: 如何只导入部分文件？

A: 可以在源目录下只保留想导入的文件，或者修改脚本过滤逻辑。

## 下一步

数据导入成功后：

1. 探索新架构的所有功能页面
2. 体验智能告警
3. 设置用户KPI和任务看板
4. 导出报告分析

## 技术细节

### 日期解析规则

脚本从文件名中提取日期，支持以下格式：
- `2026-04-20~2026-04-26` → 月份 2026-04
- `2026-04-20` → 月份 2026-04
- `4月20-*` → 日期 2026-04-20
- `*_20260503_*.xlsx` → 日期 2026-05-03

### 表头查找规则

脚本会自动查找包含以下关键词的行作为表头：
- 商品ID, 宝贝ID, 主体ID
- 来源, 来源名称, 流量来源
- 关键词, 搜索词
- 访客数, UV, 浏览量
- 搜索人气, 搜索热度
- 等等...

如果找不到，会尝试使用第一行作为表头。

### 去重/更新规则

- **商品**: 通过 `product_id` 查找，已存在则更新
- **月度数据**: 通过 `product_id` + `month` 查找
- **排名数据**: 通过 `product_id` 查找
- **关键词数据**: 通过 `keyword` + `date`