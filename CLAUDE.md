# 嗨贝海数据仪表盘 - AI 执行规范

## 项目概述

**项目名称**: 嗨贝海数据仪表盘  
**项目类型**: 前后端分离的电商数据分析系统  
**技术栈**: Vue 3 + FastAPI + SQLite + Element Plus + ECharts

## 目录结构

```
workspace/
├── frontend/           # Vue 3 前端项目
│   ├── src/
│   │   ├── views/    # 页面组件
│   │   ├── components/# 公共组件
│   │   ├── api/      # API 接口
│   │   └── router/   # 路由配置
│   └── package.json
├── backend/           # FastAPI 后端项目
│   ├── app/
│   │   ├── api/      # API 路由
│   │   ├── models/   # 数据模型
│   │   └── core/     # 核心配置
│   └── main.py
└── docs/             # 项目文档
```

## 核心规范

### 1. 开发前必读

- 修改任何页面组件前，先阅读 [frontend/src/views/](file:///workspace/frontend/src/views/) 中的现有代码
- 修改后端 API 前，先阅读 [backend/app/api/](file:///workspace/backend/app/api/) 中的现有代码
- 遵循现有代码的命名规范和风格

### 2. 质量红线（不可违反）

| 红线 | 描述 | 检查命令 |
|------|------|----------|
| R1 | 禁止提交硬编码密钥 | `grep -r "password\|secret\|key" --include="*.py" --include="*.vue" --include="*.js"` |
| R2 | 禁止空 catch 块 | `grep -E "except.*:\s*pass\|except.*:\s*#" backend/` |
| R3 | 前端必须构建验证 | `cd frontend && npm run build` |
| R4 | API 调用必须错误处理 | 检查所有 async 函数有 try-except |
| R5 | 组件必须有 loading 状态 | 检查数据请求有 v-loading |

### 3. 开发工作流

```
探索 → 规划 → 执行 → 验证 → 沉淀
```

**G1 探索**: 修改前必须阅读至少 3 个相关文件  
**G2 规划**: 创建 TODO 列表，标注优先级  
**G3 执行**: 按优先级顺序开发，不要跳步  
**G4 验证**: 必须运行 `npm run build` 验证前端  
**G5 沉淀**: 更新相关文档

### 4. 前端开发规范

#### 4.1 组件结构

```vue
<template>
  <!-- 模板内容 -->
</template>

<script setup>
// 1. 导入
import { ref, computed } from 'vue'
import api from '@/api'

// 2. 常量定义
const PAGE_SIZE = 20

// 3. 响应式数据
const data = ref([])

// 4. 计算属性
const total = computed(() => data.value.length)

// 5. 方法
const loadData = async () => {
  try {
    loading.value = true
    const res = await api.getData()
    data.value = res.data || []
  } catch (error) {
    console.error('加载失败:', error)
    ElMessage.error('数据加载失败')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
/* 样式 */
</style>
```

#### 4.2 API 调用规范

```javascript
// ✅ 正确：完整的错误处理
const loadData = async () => {
  loading.value = true
  try {
    const res = await api.getData(params)
    if (res && res.data) {
      data.value = res.data
    }
  } catch (error) {
    console.error('API Error:', error)
    ElMessage.error('加载失败')
  } finally {
    loading.value = false
  }
}

// ❌ 错误：没有错误处理
const loadData = async () => {
  const res = await api.getData()
  data.value = res.data
}
```

#### 4.3 图标使用

**只使用 Element Plus 内置图标**：
- ✅ `ArrowUp`, `ArrowDown`, `ArrowLeft`, `ArrowRight`
- ✅ `Refresh`, `Search`, `Download`, `Upload`
- ✅ `Plus`, `Minus`, `Close`, `Edit`
- ✅ `Star`, `Sunny`, `Moon`
- ❌ `TrendingUp`, `TrendingDown` (不存在)
- ❌ `CheckCircle`, `AlertCircle` (不存在)

检查可用图标：
```bash
node -e "const icons = require('@element-plus/icons-vue'); console.log(Object.keys(icons).sort().join('\n'))"
```

### 5. 后端开发规范

#### 5.1 API 路由结构

```python
from fastapi import APIRouter, Query
from typing import Optional

router = APIRouter(prefix="/api/resource", tags=["资源管理"])

@router.get("/list")
async def get_list(
    page: int = Query(1, description="页码"),
    page_size: int = Query(20, description="每页数量")
):
    """获取列表数据"""
    # 必须有错误处理
    try:
        # 业务逻辑
        return {"data": [], "total": 0}
    except Exception as e:
        # 记录错误
        raise HTTPException(status_code=500, detail=str(e))
```

#### 5.2 数据库操作

```python
# ✅ 正确
with app.app_context():
    products = Product.query.all()
    db.session.commit()

# ❌ 错误：没有上下文
products = Product.query.all()
```

### 6. 文件修改优先级

修改现有文件时，遵循以下优先级：

1. **直接修改** - 如果功能简单，直接修改
2. **创建新组件** - 如果功能复杂，创建新组件
3. **创建新页面** - 如果是全新功能，创建新页面 + 路由

### 7. Git 提交规范

```
feat: 新功能
fix: 修复bug
docs: 文档更新
style: 代码格式
refactor: 重构
test: 测试
chore: 构建/工具
```

### 8. 常用命令

```bash
# 前端
cd frontend
npm install          # 安装依赖
npm run dev          # 开发模式
npm run build        # 构建生产版本（必须执行）

# 后端
cd backend
python main.py       # 启动服务
```

### 9. 验证清单

修改完成后，必须验证：

- [ ] `npm run build` 成功
- [ ] 没有控制台错误
- [ ] API 调用有错误处理
- [ ] 组件有 loading 状态
- [ ] 页面能正常显示数据

### 10. 当不确定时

- [ ] 标记 `[UNCERTAIN]` 并说明不确定的地方
- [ ] 不要编造不存在的 API
- [ ] 不要跳过构建验证
- [ ] 不要忽略错误

## 快速开始

```bash
# 1. 安装前端依赖
cd frontend && npm install

# 2. 启动前端开发
npm run dev

# 3. 启动后端
cd ../backend && python main.py

# 4. 验证构建
npm run build
```
