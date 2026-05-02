# 嗨贝海数据仪表盘 2.0

现代化的电商数据管理平台，采用 FastAPI + Vue3 前后端分离架构，集成 SCALE OS 认知脚手架。

## ✨ 项目特性

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
- ✅ **智能导入**：AI 自动识别和导入数据
- ✅ **系统监控**：实时系统指标和健康检查
- ✅ **现代 UI**：Vue 3 + Element Plus
- ✅ **快速部署**：支持 Docker 一键部署
- ✅ **SCALE OS 集成**：认知工作流、质量门控、安全红线

## 🛠️ SCALE OS 集成特性

### 认知工作流
- 📋 **S-探索**：先理解需求，再写代码
- 📋 **C-创建计划**：Spec + Plan + Tasks，不遗漏
- 📋 **A-实现**：按计划执行，TDD 模式
- 📋 **L-验证**：Gate 机制，全链路质量保证
- 📋 **E-进化**：每次都比上次更好

### 质量门控
- 🔴 **Gate 1**：工具使用规范
- 🔴 **Gate 2**：代码规范检查
- 🔴 **Gate 3**：单元测试覆盖
- 🔴 **Gate 4**：集成测试覆盖
- 🔴 **Gate 5**：性能指标检查
- 🔴 **Gate 6**：安全检查

### 安全红线
- 🔴 **R-1**：不能有 hardcoded secrets
- 🔴 **R-2**：不能忽略 Exception，要有合理处理
- 🔴 **R-3**：关键路径上的每个输入都要有校验

## 🚀 快速开始

### 1. 一键设置（推荐）

```bash
make setup
```

### 2. 开发模式

```bash
make dev
```

### 3. 手动启动

#### 后端
```bash
cd backend
pip install -r requirements.txt
python main.py
```

后端服务运行在 http://localhost:8000

#### 前端
```bash
cd frontend
npm install
npm run dev
```

访问 http://localhost:5173 查看应用。

### 4. Docker 部署

```bash
# 构建镜像
make docker-build

# 启动服务
make docker-up

# 查看日志
make docker-logs

# 停止服务
make docker-down
```

## 📖 SCALE OS 工作流

### 开发新功能
```bash
# 1. 创建计划
make plan NAME=your-feature-name

# 2. 编辑文档
# - docs/plans/YYYY-MM-DD-your-feature-name/spec.md
# - docs/plans/YYYY-MM-DD-your-feature-name/plan.md
# - docs/plans/YYYY-MM-DD-your-feature-name/tasks.md

# 3. 保存 checkpoint
make checkpoint

# 4. 开发功能
# ...

# 5. 质量检查
make gate

# 6. 验证
make test
```

### 常用命令

```bash
# 开发
make dev                          # 同时启动前后端
make frontend                     # 仅启动前端
make backend                      # 仅启动后端
make build                        # 构建前端

# 质量保障
make test                         # 运行测试
make lint                         # 代码检查
make gate                         # 质量门控
make redlines                     # 安全红线检查

# 状态管理
make checkpoint                   # 保存检查点
make resume                       # 恢复工作
make status                       # 查看状态

# 部署和运维
make backup                       # 完整备份
make db-backup                    # 数据库备份
make metrics                      # 系统指标
make clean                        # 清理构建
```

## 📊 监控接口

### 系统状态
```
GET /api/system/status
GET /api/system/health
GET /api/system/metrics
```

### 健康检查
```
GET /health
```

## 📁 项目结构

```
.
├── backend/               # 后端服务 (FastAPI)
│   ├── app/
│   │   ├── api/          # API 路由
│   │   ├── core/         # 配置和数据库
│   │   ├── models/       # 数据模型
│   │   ├── schemas/      # Pydantic 模式
│   │   └── services/     # 业务逻辑
│   ├── data/             # 数据目录
│   ├── tests/            # 测试文件
│   ├── scripts/          # 工具脚本
│   ├── requirements.txt
│   └── main.py
├── frontend/             # 前端应用 (Vue 3)
│   ├── src/
│   │   ├── views/       # 页面组件
│   │   ├── components/  # 复用组件
│   │   ├── api/        # API 调用
│   │   ├── router/     # 路由配置
│   │   └── stores/     # 状态管理
│   └── package.json
├── docs/                # 设计文档和计划
│   └── plans/          # SCALE OS 计划
├── .agent/             # SCALE OS 状态
│   ├── state/         # 当前状态
│   └── checkpoints/   # 检查点
├── scripts/            # SCALE OS 脚本
├── Makefile           # 统一命令入口
├── CLAUDE.md          # AI 指导文档
├── docker-compose.yml
└── README.md
```

## 📱 页面功能

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
| 智能导入 | `/smart-import` | AI 智能导入 |
| 系统设置 | `/settings` | 系统配置 |

## 🔌 API 接口文档

### 系统监控

| 方法 | 端点 | 描述 |
|------|------|------|
| GET | `/api/system/status` | 系统状态概览 |
| GET | `/api/system/health` | 健康检查详情 |
| GET | `/api/system/metrics` | 完整指标数据 |

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

### 数据导入导出

| 方法 | 端点 | 描述 |
|------|------|------|
| POST | `/api/import/excel` | 导入 Excel 文件 |
| POST | `/api/smart-import/scan` | 智能扫描文件夹 |
| GET | `/api/export/products` | 导出商品数据 |
| GET | `/api/export/data` | 导出分析数据 |

### 仪表盘

| 方法 | 端点 | 描述 |
|------|------|------|
| GET | `/api/dashboard/summary` | 获取仪表盘汇总 |
| GET | `/api/dashboard/top-products` | 获取热门商品 |
| GET | `/api/dashboard/quadrant` | 获取四象限分析 |

### 完整 API 文档

启动后端服务后，访问：
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 💾 数据备份

```bash
# 数据库备份
make db-backup

# 完整备份
make backup

# 恢复（需要手动选择文件）
make db-restore
make restore
```

## 🛡️ 安全配置

### 环境变量示例

复制 `.env.example` 为 `.env` 并编辑：

```bash
cp backend/.env.example backend/.env
```

### 安全建议
- ✅ 从不提交 `.env` 文件到 Git
- ✅ 密钥自动生成，无需硬编码
- ✅ 使用环境变量管理配置
- ✅ 定期执行 `make redlines` 检查

## 🧪 测试

```bash
# 运行所有测试
make test

# 或直接运行
cd backend
python -m pytest tests/ -v
```

## 📈 性能优化

- 数据库索引优化
- 前端组件懒加载
- API 响应缓存
- ECharts 按需加载
- 分块构建策略

## 🔧 技术栈

- **后端**：FastAPI 0.115+, SQLAlchemy 2.0+, Pandas, Pydantic, psutil
- **前端**：Vue 3 + Vite + Element Plus + ECharts 5
- **数据库**：SQLite（轻量、易部署，可迁移到 PostgreSQL）
- **测试**：pytest, pytest-asyncio
- **部署**：Docker, docker-compose
- **AI 开发**：SCALE OS 认知脚手架

## 📚 相关资源

- [SCALE OS 配置网站](https://scale-os.hongmaple.top)
- [项目脚手架 GitHub](https://github.com/hongmaple0820/project-scaffold)
- [FastAPI 文档](https://fastapi.tiangolo.com)
- [Vue 3 文档](https://cn.vuejs.org)

## 📄 许可证

内部使用，请勿外传。

---

## 📞 支持

如遇问题，查看：
1. `docs/plans/` 下的项目文档
2. [CLAUDE.md](file:///workspace/CLAUDE.md) AI 指导
3. `/api/system/health` 系统状态
4. `make status` 当前状态检查
