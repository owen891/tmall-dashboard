# 前端代码规范

## 1. Vue 3 组件规范

### 1.1 组件结构

```
<template>
  <!-- HTML 模板 -->
</template>

<script setup>
// 1. 导入
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import api from '@/api'

// 2. 常量定义
const PAGE_SIZE = 20
const STATUS_OPTIONS = ['启用', '禁用']

// 3. 响应式数据
const loading = ref(false)
const dataList = ref([])
const form = ref({
  name: '',
  status: '启用'
})

// 4. 计算属性
const total = computed(() => dataList.value.length)
const isValid = computed(() => form.value.name.length > 0)

// 5. 方法
const loadData = async () => {
  loading.value = true
  try {
    const res = await api.getList()
    dataList.value = res.data || []
    ElMessage.success('加载成功')
  } catch (error) {
    console.error('加载失败:', error)
    ElMessage.error('加载失败，请重试')
  } finally {
    loading.value = false
  }
}

// 6. 生命周期
onMounted(() => {
  loadData()
})
</script>

<style scoped>
/* 样式 */
</style>
```

### 1.2 命名规范

| 类型 | 规范 | 示例 |
|------|------|------|
| 组件文件 | PascalCase | `UserProfile.vue` |
| 组件变量 | camelCase | `userProfile`, `isLoading` |
| 常量 | UPPER_SNAKE | `PAGE_SIZE`, `API_URL` |
| 事件方法 | handle + 动作 | `handleClick`, `handleSubmit` |
| 加载方法 | load + 名词 | `loadData`, `loadUsers` |
| 提交方法 | submit + 名词 | `submitForm`, `submitData` |

### 1.3 Props 定义

```javascript
// ✅ 正确
const props = defineProps({
  title: {
    type: String,
    required: true
  },
  list: {
    type: Array,
    default: () => []
  },
  count: {
    type: Number,
    default: 0
  }
})

// ❌ 错误
const props = defineProps(['title', 'list', 'count'])
```

### 1.4 事件定义

```javascript
// ✅ 正确：使用 emit 定义事件
const emit = defineEmits(['update', 'delete', 'click'])

// 使用
emit('update', data)
emit('delete', id)

// ❌ 错误：直接使用 $emit
this.$emit('update', data)
```

## 2. API 调用规范

### 2.1 API 模块结构

```javascript
// src/api/index.js
import axios from 'axios'

const request = axios.create({
  baseURL: '/api',
  timeout: 30000
})

// 响应拦截器
request.interceptors.response.use(
  response => {
    return response.data
  },
  error => {
    console.error('API Error:', error)
    return Promise.reject(error)
  }
)

// 导出 API 方法
export default {
  // GET 请求
  getList(params) {
    return request.get('/list', { params })
  },
  
  // POST 请求
  create(data) {
    return request.post('/create', data)
  },
  
  // PUT 请求
  update(id, data) {
    return request.put(`/update/${id}`, data)
  },
  
  // DELETE 请求
  delete(id) {
    return request.delete(`/delete/${id}`)
  }
}
```

### 2.2 组件中使用 API

```javascript
import api from '@/api'

// ✅ 正确
const loadData = async () => {
  loading.value = true
  try {
    const res = await api.getList({ page: 1, size: 20 })
    if (res && res.data) {
      list.value = res.data
      total.value = res.total
    }
  } catch (error) {
    console.error('加载数据失败:', error)
    ElMessage.error('加载失败')
  } finally {
    loading.value = false
  }
}

// ❌ 错误：缺少错误处理
const loadData = async () => {
  const res = await api.getList()
  list.value = res.data
}
```

## 3. 样式规范

### 3.1 CSS 命名

使用 BEM 命名法：
- Block: `card`
- Element: `card__header`, `card__body`
- Modifier: `card--active`, `card--disabled`

```css
/* ✅ 正确 */
.card {
  padding: 16px;
}

.card__header {
  border-bottom: 1px solid #ebeef5;
}

.card--active {
  border-color: #409eff;
}

/* ❌ 错误 */
.cardHeader {
  border-bottom: 1px solid #ebeef5;
}
```

### 3.2 响应式断点

```css
/* 移动端优先 */
.element {
  font-size: 14px;
}

@media (min-width: 768px) {
  .element {
    font-size: 16px;
  }
}

@media (min-width: 1200px) {
  .element {
    font-size: 18px;
  }
}
```

## 4. Element Plus 使用规范

### 4.1 按钮规范

```vue
<!-- 主要操作 -->
<el-button type="primary">确定</el-button>

<!-- 次要操作 -->
<el-button>取消</el-button>

<!-- 危险操作 -->
<el-button type="danger">删除</el-button>

<!-- 文字按钮 -->
<el-button type="text">查看详情</el-button>

<!-- 带图标 -->
<el-button type="primary">
  <el-icon><Plus /></el-icon>
  新增
</el-button>
```

### 4.2 表格规范

```vue
<el-table 
  :data="list" 
  stripe 
  v-loading="loading"
  @selection-change="handleSelectionChange"
>
  <el-table-column type="selection" width="55" />
  <el-table-column prop="name" label="名称" min-width="120" />
  <el-table-column prop="status" label="状态" width="100">
    <template #default="{ row }">
      <el-tag :type="row.status === '启用' ? 'success' : 'info'">
        {{ row.status }}
      </el-tag>
    </template>
  </el-table-column>
  <el-table-column label="操作" width="150" fixed="right">
    <template #default="{ row }">
      <el-button type="text" @click="handleEdit(row)">编辑</el-button>
      <el-button type="text" @click="handleDelete(row)">删除</el-button>
    </template>
  </el-table-column>
</el-table>
```

### 4.3 表单规范

```vue
<el-form 
  :model="form" 
  :rules="rules" 
  ref="formRef"
  label-width="100px"
>
  <el-form-item label="名称" prop="name">
    <el-input v-model="form.name" placeholder="请输入名称" />
  </el-form-item>
  <el-form-item label="状态" prop="status">
    <el-select v-model="form.status">
      <el-option label="启用" value="启用" />
      <el-option label="禁用" value="禁用" />
    </el-select>
  </el-form-item>
</el-form>
```

## 5. 错误处理规范

### 5.1 异步操作错误处理

```javascript
// ✅ 正确
async function submitData() {
  loading.value = true
  try {
    await api.submit(form.value)
    ElMessage.success('提交成功')
    dialogVisible.value = false
    loadData()
  } catch (error) {
    console.error('提交失败:', error)
    if (error.response?.data?.message) {
      ElMessage.error(error.response.data.message)
    } else {
      ElMessage.error('提交失败，请重试')
    }
  } finally {
    loading.value = false
  }
}

// ❌ 错误
function submitData() {
  api.submit(form.value)
  ElMessage.success('提交成功')
}
```

### 5.2 Promise 错误处理

```javascript
// ✅ 正确
api.getData()
  .then(res => {
    list.value = res.data
  })
  .catch(error => {
    console.error('获取数据失败:', error)
    ElMessage.error('加载失败')
  })
  .finally(() => {
    loading.value = false
  })

// ❌ 错误
api.getData()
  .then(res => {
    list.value = res.data
  })
```

## 6. 代码格式化

使用 ESLint + Prettier：

```json
// .eslintrc.json
{
  "extends": [
    "plugin:vue/vue3-recommended",
    "prettier"
  ],
  "rules": {
    "vue/multi-word-component-names": "off"
  }
}
```

运行格式化：

```bash
# 格式化所有文件
npm run lint

# 修复可自动修复的问题
npm run lint -- --fix
```
