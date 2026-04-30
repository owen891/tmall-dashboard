# 天猫数据管理系统 2.0

全新架构的数据管理系统，采用 FastAPI + Vue3 + Element Plus 构建

## 项目结构

```
/workspace
├── backend/          # FastAPI 后端
│   ├── app/         # 应用代码
│   │   ├── api/    # API 路由
│   │   ├── core/   # 核心配置
│   │   ├── models/ # 数据模型
│   │   ├── schemas/# Pydantic 模式
│   │   └── services/# 业务逻辑
│   ├── data/       # 数据目录
│   └── requirements.txt
├── frontend/         # Vue3 前端
│   ├── src/
│   │   ├── views/  # 页面组件
│   │   ├── api/    # API 封装
│   │   └── router/ # 路由配置
│   └── package.json
└── legacy/          # 旧系统代码
```

## 快速开始

### 启动后端

```bash
cd /workspace/backend
pip install -r requirements.txt
python migrate_old_data.py  # 迁移旧数据（可选）
python run.py
```
后端会在 http://localhost:8000 启动

### 启动前端

```bash
cd /workspace/frontend
npm install
npm run dev
```
前端会在 http://localhost:5173 启动

## 功能特性

- ✅ 数据持久化（SQLite + SQLAlchemy 2.0）
- ✅ Excel 数据导入
- ✅ 商品数据管理和筛选
- ✅ 历史数据分析和可视化（ECharts）
- ✅ GMV vs ROI 四象限分析
- ✅ 现代 UI 界面（Vue3 + Element Plus）
- ✅ 商品标签管理
- ✅ 操作记录管理

## API 端点

### 商品相关
- `GET /api/products` - 获取商品列表
- `GET /api/products/{product_id}` - 获取商品详情
- `POST /api/products/{product_id}/star` - 标记/取消标记商品
- `POST /api/products/{product_id}/tags` - 添加标签

### 导入相关
- `POST /api/import/excel` - 导入 Excel
- `POST /api/import/preview` - 预览 Excel

### 仪表盘
- `GET /api/dashboard/summary` - 获取汇总数据
- `GET /api/dashboard/quadrant` - 获取四象限分析数据
