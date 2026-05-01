# 天猫数据管理系统 2.0

现代化的电商数据管理平台，采用 FastAPI + Vue3 前后端分离架构。

## 项目特性

- ✅ **数据持久化**：使用 SQLite + SQLAlchemy ORM
- ✅ **Excel 导入**：支持批量导入商品和周数据
- ✅ **商品管理**：完整的 CRUD，筛选和搜索
- ✅ **历史分析**：多维度数据可视化（ECharts）
- ✅ **GMV vs ROI 四象限分析**：智能选款辅助
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

#### 前端
```bash
cd frontend
npm install
npm run dev
```

访问 http://localhost:5173 查看应用。

### 2. Docker 部署（可选）
```bash
docker-compose up -d
```

## 项目结构

```
.
├── backend/          # 后端服务 (FastAPI)
│   ├── app/          # 核心应用代码
│   │   ├── api/     # API 路由
│   │   ├── core/    # 配置和数据库
│   │   ├── models/  # 数据模型
│   │   ├── schemas/ # Pydantic 模式
│   │   └── services/ # 业务逻辑
│   ├── data/        # 数据目录
│   └── requirements.txt
├── frontend/         # 前端应用 (Vue 3)
│   ├── src/
│   │   ├── views/   # 页面组件
│   │   ├── api/     # API 调用
│   │   └── router/  # 路由配置
│   └── package.json
└── legacy/           # 旧系统代码（保留参考）
```

## API 端点

### 商品
- `GET /api/products` - 获取商品列表（支持筛选和分页）
- `GET /api/products/{product_id}` - 获取商品详情
- `GET /api/products/{product_id}/weekly-data` - 获取商品历史数据
- `POST /api/products/{product_id}/star` - 标记/取消标记星标

### 数据导入
- `POST /api/import/excel` - 导入 Excel 文件

### 仪表盘
- `GET /api/dashboard/summary` - 获取汇总数据
- `GET /api/dashboard/top-products` - 获取热门商品
- `GET /api/dashboard/quadrant` - 获取四象限分析数据

## 数据导入

### 使用现有的真实数据
```bash
cd backend
python simple_import.py
```

### 或从旧系统迁移
```bash
python migrate_old_data.py
```

## 技术栈

- 后端：FastAPI 0.115+, SQLAlchemy 2.0+, Pandas
- 前端：Vue 3 + Vite + Element Plus + ECharts 5
- 数据库：SQLite（轻量、易部署）
