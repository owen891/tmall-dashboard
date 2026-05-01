# 天猫数据管理系统 2.0

现代化的电商数据管理平台，采用 FastAPI + Vue3 前后端分离架构。

## 项目特性

- ✅ **数据持久化**：使用 SQLite + SQLAlchemy ORM
- ✅ **Excel 导入**：支持批量导入商品和周数据
- ✅ **商品管理**：完整的 CRUD，筛选和搜索
- ✅ **历史分析**：多维度数据可视化（ECharts）
- ✅ **GMV vs ROI 四象限分析**：智能选款辅助
- ✅ **KPI 指标监控**：关键绩效指标追踪与异常检测
- ✅ **健康度分析**：商品健康度综合评分
- ✅ **趋势分析**：店铺/商品维度趋势追踪
- ✅ **运营动作管理**：记录和分析运营活动效果
- ✅ **市场分析**：关键词机会发现
- ✅ **目标管理**：设置和追踪销售目标
- ✅ **告警系统**：异常数据实时告警
- ✅ **现代 UI**：Vue 3 + Element Plus
- ✅ **快速部署**：支持 Docker 一键部署

## 快速开始

### 1. 本地运行

#### 后端
```bash
cd backend
pip install -r requirements.txt
python run.py
```

后端服务运行在 http://localhost:8000

#### 前端
```bash
cd frontend
npm install
npm run dev
```

访问 http://localhost:5173 查看应用。

### 2. Docker 部署
```bash
docker-compose up -d
```

## 项目结构

```
.
├── backend/          # 后端服务 (FastAPI)
│   ├── app/
│   │   ├── api/      # API 路由
│   │   ├── core/     # 配置和数据库
│   │   ├── models/   # 数据模型
│   │   ├── schemas/  # Pydantic 模式
│   │   └── services/ # 业务逻辑
│   ├── data/         # 数据目录
│   ├── requirements.txt
│   └── run.py
├── frontend/         # 前端应用 (Vue 3)
│   ├── src/
│   │   ├── views/    # 页面组件
│   │   ├── api/      # API 调用
│   │   ├── router/   # 路由配置
│   │   └── stores/   # 状态管理
│   └── package.json
└── docs/             # 设计文档
```

## 页面功能

| 页面 | 路径 | 功能描述 |
|------|------|---------|
| 仪表盘 | `/` | 核心指标概览、GMV趋势、热销商品 |
| 商品列表 | `/products` | 商品管理、筛选搜索、批量操作 |
| 商品详情 | `/products/:id` | 单品分析、趋势图、运营动作 |
| KPI指标 | `/kpi` | 关键绩效指标、异常检测 |
| 趋势分析 | `/trends` | 店铺/商品维度趋势追踪 |
| 健康度 | `/health` | 商品健康度综合评分 |
| 四象限 | `/quadrant` | GMV vs ROI 四象限分析 |
| 告警 | `/alerts` | 异常数据告警管理 |
| 运营动作 | `/operations` | 运营活动记录与分析 |
| 退款 | `/refunds` | 退款数据分析 |
| 评价 | `/reviews` | 商品评价分析 |
| 市场 | `/market` | 市场分析与关键词机会 |
| 目标 | `/targets` | 销售目标管理 |
| 工具箱 | `/toolbox` | 数据导入导出、对比分析 |
| 生命周期 | `/lifecycle` | 商品生命周期分析 |
| 付费推广 | `/ads` | 广告投放数据分析 |
| 导入 | `/import` | Excel数据导入 |

## API 接口文档

### 商品管理

| 方法 | 端点 | 描述 |
|------|------|------|
| GET | `/api/products` | 获取商品列表（支持筛选和分页） |
| GET | `/api/products/{product_id}` | 获取商品详情 |
| GET | `/api/products/{product_id}/weekly-data` | 获取商品周数据 |
| GET | `/api/products/{product_id}/monthly-data` | 获取商品月数据 |
| GET | `/api/products/{product_id}/daily-data` | 获取商品日数据 |
| POST | `/api/products/{product_id}/star` | 标记/取消标记星标 |
| PATCH | `/api/products/{product_id}` | 更新商品字段 |
| POST | `/api/products/batch-update` | 批量更新商品 |
| GET | `/api/products/{product_id}/operations` | 获取运营动作 |
| GET | `/api/products/{product_id}/notes` | 获取商品备注 |
| POST | `/api/products/{product_id}/notes` | 添加商品备注 |
| GET | `/api/products/{product_id}/tags` | 获取商品标签 |
| POST | `/api/products/{product_id}/tags` | 添加商品标签 |
| DELETE | `/api/products/{product_id}/tags/{tag_id}` | 删除商品标签 |
| GET | `/api/products/filters/options` | 获取筛选选项 |
| GET | `/api/products/categories` | 获取分类列表 |

### 数据导入导出

| 方法 | 端点 | 描述 |
|------|------|------|
| POST | `/api/import/excel` | 导入 Excel 文件 |
| GET | `/api/export/products` | 导出商品数据 |
| GET | `/api/export/data` | 导出分析数据 |

### 仪表盘

| 方法 | 端点 | 描述 |
|------|------|------|
| GET | `/api/dashboard` | 获取仪表盘数据（兼容旧版） |
| GET | `/api/dashboard/summary` | 获取仪表盘汇总 |
| GET | `/api/dashboard/top-products` | 获取热门商品 |
| GET | `/api/dashboard/quadrant` | 获取四象限分析 |

### KPI 指标

| 方法 | 端点 | 描述 |
|------|------|------|
| GET | `/api/kpi/summary` | 获取 KPI 汇总 |
| GET | `/api/kpi/anomalies` | 获取 KPI 异常列表 |
| POST | `/api/kpi/anomalies/{alert_id}/dismiss` | 忽略异常 |

### 趋势分析

| 方法 | 端点 | 描述 |
|------|------|------|
| GET | `/api/trends/shop` | 获取店铺趋势 |
| GET | `/api/trends/product/{product_id}` | 获取商品趋势 |
| GET | `/api/trends/events` | 获取趋势事件 |
| POST | `/api/trends/events` | 添加趋势事件 |
| DELETE | `/api/trends/events/{event_id}` | 删除趋势事件 |

### 健康度分析

| 方法 | 端点 | 描述 |
|------|------|------|
| GET | `/api/health/list` | 获取商品健康度列表 |
| GET | `/api/health/summary` | 获取健康度汇总 |
| GET | `/api/health/{product_id}` | 获取商品健康度详情 |
| GET | `/api/health/alerts` | 获取健康度告警 |
| POST | `/api/health/refresh/{product_id}` | 刷新健康度评分 |

### 对比分析

| 方法 | 端点 | 描述 |
|------|------|------|
| GET | `/api/compare` | 对比两个周期数据 |

### 运营动作

| 方法 | 端点 | 描述 |
|------|------|------|
| GET | `/api/actions` | 获取运营动作列表 |
| POST | `/api/actions` | 创建运营动作 |
| DELETE | `/api/actions/{action_id}` | 删除运营动作 |
| GET | `/api/action-stats` | 获取运营统计 |

### 退款分析

| 方法 | 端点 | 描述 |
|------|------|------|
| GET | `/api/refunds` | 获取退款列表 |
| GET | `/api/refunds/summary` | 获取退款汇总 |

### 评价分析

| 方法 | 端点 | 描述 |
|------|------|------|
| GET | `/api/reviews` | 获取评价列表 |
| GET | `/api/reviews/summary` | 获取评价汇总 |
| GET | `/api/reviews/sentiment` | 获取情感分析 |

### 市场分析

| 方法 | 端点 | 描述 |
|------|------|------|
| GET | `/api/market/keywords` | 获取关键词分析 |
| GET | `/api/market/opportunities` | 获取市场机会 |
| GET | `/api/market/analysis` | 获取市场分析 |

### 目标管理

| 方法 | 端点 | 描述 |
|------|------|------|
| GET | `/api/targets` | 获取目标列表 |
| GET | `/api/targets/shop` | 获取店铺目标 |
| GET | `/api/targets/products` | 获取商品目标 |
| POST | `/api/targets` | 创建目标 |
| PUT | `/api/targets/{target_id}` | 更新目标 |
| DELETE | `/api/targets/{target_id}` | 删除目标 |

### 告警系统

| 方法 | 端点 | 描述 |
|------|------|------|
| GET | `/api/alerts` | 获取告警列表 |
| POST | `/api/alerts/{alert_id}/dismiss` | 忽略告警 |
| GET | `/api/alerts/rules` | 获取告警规则 |
| PUT | `/api/alerts/rules/{rule_id}` | 更新告警规则 |

### 商品生命周期

| 方法 | 端点 | 描述 |
|------|------|------|
| GET | `/api/lifecycle/products` | 获取生命周期分析 |
| GET | `/api/lifecycle/stages` | 获取生命周期阶段分布 |

### 付费推广

| 方法 | 端点 | 描述 |
|------|------|------|
| GET | `/api/ads/summary` | 获取广告投放汇总 |
| GET | `/api/ads/products` | 获取商品广告数据 |
| GET | `/api/ads/detail` | 获取广告详细数据 |

### 工具箱

| 方法 | 端点 | 描述 |
|------|------|------|
| GET | `/api/toolbox/templates` | 获取导入模板 |
| GET | `/api/toolbox/backup` | 备份数据 |
| POST | `/api/toolbox/restore` | 恢复数据 |

### 自定义字段

| 方法 | 端点 | 描述 |
|------|------|------|
| GET | `/api/custom-fields` | 获取自定义字段 |
| POST | `/api/custom-fields` | 创建自定义字段 |
| PUT | `/api/custom-fields/{field_id}` | 更新自定义字段 |
| DELETE | `/api/custom-fields/{field_id}` | 删除自定义字段 |

### 周期数据

| 方法 | 端点 | 描述 |
|------|------|------|
| GET | `/api/periods` | 获取可用周期列表 |

### 系统状态

| 方法 | 端点 | 描述 |
|------|------|------|
| GET | `/api/status` | 获取系统状态 |
| GET | `/api/health` | 健康检查 |

## 数据导入

### 使用现有的真实数据
```bash
cd backend
python simple_import.py
```

### 导入 Excel 文件
通过前端页面 `/import` 导入 Excel 文件。

## 数据库表结构

### 核心表

| 表名 | 描述 |
|------|------|
| `products` | 商品基础信息 |
| `daily_data` | 日数据 |
| `weekly_data` | 周数据 |
| `monthly_data` | 月数据 |
| `product_tags` | 商品标签 |
| `product_notes` | 商品备注 |
| `product_custom_fields` | 自定义字段 |
| `operation_actions` | 运营动作 |
| `paid_detail` | 付费推广详情 |

### 分析表

| 表名 | 描述 |
|------|------|
| `product_health` | 商品健康度 |
| `refunds` | 退款记录 |
| `reviews` | 评价记录 |
| `review_summary` | 评价汇总 |
| `market_analysis` | 市场分析 |
| `market_keyword_opportunities` | 关键词机会 |
| `chart_events` | 趋势事件 |
| `alerts` | 告警记录 |
| `alert_rules` | 告警规则 |

### 目标表

| 表名 | 描述 |
|------|------|
| `shop_targets` | 店铺目标 |
| `product_targets` | 商品目标 |

### 辅助表

| 表名 | 描述 |
|------|------|
| `scheduled_tasks` | 定时任务 |
| `operation_logs` | 操作日志 |

## 技术栈

- **后端**：FastAPI 0.115+, SQLAlchemy 2.0+, Pandas, Pydantic
- **前端**：Vue 3 + Vite + Element Plus + ECharts 5
- **数据库**：SQLite（轻量、易部署，可迁移到 PostgreSQL）

## 常用命令

```bash
# 后端
cd backend
python run.py                    # 启动后端服务
python simple_import.py          # 导入示例数据

# 前端
cd frontend
npm install                      # 安装依赖
npm run dev                      # 开发模式
npm run build                    # 生产构建
```

## 环境变量

### 后端 (.env)
```
DATABASE_URL=sqlite:///./data/dashboard.db
LOG_LEVEL=INFO
CORS_ORIGINS=http://localhost:5173
```

### 前端 (.env)
```
VITE_API_BASE=/api
```
