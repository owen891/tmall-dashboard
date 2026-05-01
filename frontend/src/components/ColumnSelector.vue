<template>
  <div class="column-selector">
    <el-dialog
      v-model="visible"
      title="自定义数据字段"
      width="900px"
      :close-on-click-modal="false"
    >
      <div class="dialog-content">
        <div class="dialog-header">
          <div class="header-left">
            <span class="title">自定义数据字段</span>
            <span class="field-count">({{ selectedFields.length }}/{{ totalFieldCount }})</span>
          </div>
          <div class="header-right">
            <el-input
              v-model="searchKeyword"
              placeholder="请输入关键字"
              clearable
              size="small"
              class="search-input"
            >
              <template #prefix>
                <el-icon><Search /></el-icon>
              </template>
            </el-input>
            <el-button size="small" @click="restoreDefault">恢复默认</el-button>
            <el-button size="small" type="danger" @click="clearAll">清空</el-button>
          </div>
        </div>

        <div class="main-content">
          <div class="left-panel">
            <div class="panel-header">
              <span>可用字段</span>
            </div>
            <div class="fields-tree">
              <div v-for="category in fieldCategories" :key="category.key" class="category-item">
                <div 
                  class="category-title" 
                  @click="toggleCategory(category.key)"
                  :class="{ expanded: expandedCategories[category.key] }"
                >
                  <el-icon class="expand-icon">
                    <ArrowDown v-if="expandedCategories[category.key]" />
                    <ArrowRight v-else />
                  </el-icon>
                  <span>{{ category.label }}</span>
                  <span class="category-count">({{ getFilteredFields(category).length }})</span>
                  <el-button 
                    v-if="expandedCategories[category.key] && getFilteredFields(category).length > 0"
                    size="mini" 
                    type="text"
                    @click.stop="toggleCategoryAll(category, !isCategoryAllSelected(category))"
                  >
                    {{ isCategoryAllSelected(category) ? '取消' : '全选' }}
                  </el-button>
                </div>
                <div v-show="expandedCategories[category.key]" class="category-content">
                  <el-checkbox
                    v-for="field in getFilteredFields(category)"
                    :key="field.key"
                    v-model="selectedFields"
                    :value="field.key"
                    :disabled="!expandedCategories[category.key]"
                    class="field-checkbox"
                  >
                    {{ field.label }}
                  </el-checkbox>
                </div>
              </div>
            </div>
          </div>

          <div class="center-panel">
            <el-button type="primary" :disabled="!hasUnselectedFields" @click="addToSelected" class="move-btn">
              <el-icon><ArrowRight /></el-icon>
            </el-button>
            <el-button type="primary" :disabled="!selectedFields.length" @click="removeFromSelected" class="move-btn">
              <el-icon><ArrowLeft /></el-icon>
            </el-button>
          </div>

          <div class="right-panel">
            <div class="panel-header">
              <span>已选字段</span>
              <span class="hint">拖动以下字段进行排序</span>
            </div>
            <div class="selected-fields">
              <div 
                v-for="(fieldKey, index) in selectedFields" 
                :key="fieldKey"
                class="selected-field-item"
                draggable="true"
                @dragstart="handleDragStart(index, $event)"
                @dragover.prevent
                @drop="handleDrop(index, $event)"
              >
                <span class="drag-handle">
                  <el-icon><Menu /></el-icon>
                </span>
                <span class="field-label">{{ getFieldLabel(fieldKey) }}</span>
                <el-button size="mini" type="text" @click="removeField(fieldKey)">
                  <el-icon><Close /></el-icon>
                </el-button>
              </div>
              <div v-if="!selectedFields.length" class="empty-state">
                <el-icon class="empty-icon"><Document /></el-icon>
                <span>暂无已选字段</span>
              </div>
            </div>
          </div>
        </div>

        <div class="dialog-footer">
          <div class="footer-left">
            <el-select v-model="currentTemplate" placeholder="选择模板" size="small" @change="applyTemplate">
              <el-option
                v-for="tpl in templates"
                :key="tpl.id"
                :label="tpl.name"
                :value="tpl.id"
              />
            </el-select>
            <el-button size="small" @click="showSaveTemplate = true">保存到个人视窗</el-button>
            <el-button
              v-if="currentTemplate && !isDefaultTemplate"
              size="small"
              type="danger"
              @click="deleteTemplate"
            >
              删除模板
            </el-button>
          </div>
          <div class="footer-right">
            <el-button @click="visible = false">取消</el-button>
            <el-button type="primary" @click="confirmSelection">确定</el-button>
          </div>
        </div>
      </div>

      <el-dialog v-model="showSaveTemplate" title="保存模板" width="400px">
        <el-form>
          <el-form-item label="模板名称">
            <el-input v-model="newTemplateName" placeholder="请输入模板名称" />
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="showSaveTemplate = false">取消</el-button>
          <el-button type="primary" @click="saveTemplate">保存</el-button>
        </template>
      </el-dialog>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Search, ArrowDown, ArrowRight, ArrowLeft, Menu, Close, Document } from '@element-plus/icons-vue'
import {
  fieldCategories,
  defaultTemplates,
  loadTemplates,
  saveCustomTemplate,
  deleteCustomTemplate as deleteTemplateFromStorage,
  saveColumnConfig,
  loadColumnConfig,
  getFieldConfig,
  defaultVisibleFields
} from '@/config/columns'

const props = defineProps({
  modelValue: {
    type: Array,
    default: () => []
  }
})

const emit = defineEmits(['update:modelValue', 'change'])

const visible = ref(false)
const selectedFields = ref([...props.modelValue])
const expandedCategories = ref({})
const templates = ref([])
const currentTemplate = ref(null)
const showSaveTemplate = ref(false)
const newTemplateName = ref('')
const searchKeyword = ref('')
const draggedIndex = ref(-1)

const totalFieldCount = computed(() => {
  return fieldCategories.reduce((sum, cat) => sum + cat.fields.length, 0)
})

const hasUnselectedFields = computed(() => {
  const allFields = fieldCategories.flatMap(cat => cat.fields.map(f => f.key))
  return allFields.some(f => !selectedFields.value.includes(f))
})

const isDefaultTemplate = computed(() => {
  return defaultTemplates.some(t => t.id === currentTemplate.value)
})

function getFilteredFields(category) {
  if (!searchKeyword.value.trim()) {
    return category.fields
  }
  const keyword = searchKeyword.value.toLowerCase()
  return category.fields.filter(f => 
    f.label.toLowerCase().includes(keyword) || 
    f.key.toLowerCase().includes(keyword)
  )
}

function getFieldLabel(fieldKey) {
  const config = getFieldConfig(fieldKey)
  return config ? config.label : fieldKey
}

watch(() => props.modelValue, (newVal) => {
  selectedFields.value = [...newVal]
})

watch(visible, (val) => {
  if (val) {
    loadData()
  }
})

watch(searchKeyword, () => {
  fieldCategories.forEach(cat => {
    const filtered = getFilteredFields(cat)
    if (filtered.length > 0 && !expandedCategories.value[cat.key]) {
      expandedCategories.value[cat.key] = true
    }
  })
})

function loadData() {
  selectedFields.value = [...props.modelValue]
  templates.value = loadTemplates()
  const config = loadColumnConfig()
  if (config.template) {
    currentTemplate.value = config.template
  }
  expandedCategories.value = {}
  fieldCategories.forEach(cat => {
    expandedCategories.value[cat.key] = true
  })
}

function toggleCategory(key) {
  expandedCategories.value[key] = !expandedCategories.value[key]
}

function isCategoryAllSelected(category) {
  const filteredFields = getFilteredFields(category)
  return filteredFields.every(f => selectedFields.value.includes(f.key))
}

function isCategoryPartiallySelected(category) {
  const filteredFields = getFilteredFields(category)
  const selected = filteredFields.filter(f => selectedFields.value.includes(f.key))
  return selected.length > 0 && selected.length < filteredFields.length
}

function toggleCategoryAll(category, checked) {
  const filteredFields = getFilteredFields(category)
  if (checked) {
    filteredFields.forEach(f => {
      if (!selectedFields.value.includes(f.key)) {
        selectedFields.value.push(f.key)
      }
    })
  } else {
    selectedFields.value = selectedFields.value.filter(
      key => !filteredFields.some(f => f.key === key)
    )
  }
}

function restoreDefault() {
  selectedFields.value = [...defaultVisibleFields]
  currentTemplate.value = 'default'
  ElMessage.info('已恢复默认字段')
}

function clearAll() {
  selectedFields.value = []
  currentTemplate.value = null
  ElMessage.info('已清空所有字段')
}

function addToSelected() {
  const allFields = fieldCategories.flatMap(cat => cat.fields.map(f => f.key))
  allFields.forEach(f => {
    if (!selectedFields.value.includes(f)) {
      selectedFields.value.push(f)
    }
  })
}

function removeFromSelected() {
  selectedFields.value = []
}

function removeField(fieldKey) {
  selectedFields.value = selectedFields.value.filter(f => f !== fieldKey)
}

function handleDragStart(index, event) {
  draggedIndex.value = index
  event.dataTransfer.effectAllowed = 'move'
}

function handleDrop(targetIndex, event) {
  if (draggedIndex.value === -1 || draggedIndex.value === targetIndex) {
    return
  }
  const draggedField = selectedFields.value[draggedIndex.value]
  selectedFields.value.splice(draggedIndex.value, 1)
  selectedFields.value.splice(targetIndex, 0, draggedField)
  draggedIndex.value = -1
}

function applyTemplate(templateId) {
  const tpl = templates.value.find(t => t.id === templateId)
  if (tpl) {
    selectedFields.value = [...tpl.fields]
    currentTemplate.value = templateId
  }
}

function saveTemplate() {
  if (!newTemplateName.value.trim()) {
    ElMessage.warning('请输入模板名称')
    return
  }
  const templateId = `custom_${Date.now()}`
  const template = {
    id: templateId,
    name: newTemplateName.value.trim(),
    fields: [...selectedFields.value]
  }
  const success = saveCustomTemplate(template)
  if (success) {
    templates.value = loadTemplates()
    currentTemplate.value = templateId
    showSaveTemplate.value = false
    newTemplateName.value = ''
    ElMessage.success('模板保存成功')
  } else {
    ElMessage.error('模板保存失败')
  }
}

function deleteTemplate() {
  if (currentTemplate.value && !isDefaultTemplate.value) {
    deleteTemplateFromStorage(currentTemplate.value)
    templates.value = loadTemplates()
    currentTemplate.value = null
    ElMessage.success('模板删除成功')
  }
}

function confirmSelection() {
  const config = {
    visibleFields: [...selectedFields.value],
    template: currentTemplate.value
  }
  saveColumnConfig(config)
  emit('update:modelValue', [...selectedFields.value])
  emit('change', [...selectedFields.value])
  visible.value = false
  ElMessage.success('字段配置已更新')
}

function open() {
  visible.value = true
}

defineExpose({ open })
</script>

<style scoped>
.dialog-content {
  display: flex;
  flex-direction: column;
  height: 600px;
}

.dialog-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 15px 20px;
  border-bottom: 1px solid #e4e7ed;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.title {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.field-count {
  color: #909399;
  font-size: 14px;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 10px;
}

.search-input {
  width: 200px;
}

.main-content {
  flex: 1;
  display: flex;
  gap: 15px;
  padding: 20px;
  overflow: hidden;
}

.left-panel, .right-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  border: 1px solid #e4e7ed;
  border-radius: 4px;
  overflow: hidden;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 15px;
  background: #f5f7fa;
  border-bottom: 1px solid #e4e7ed;
}

.panel-header span:first-child {
  font-weight: 500;
  color: #303133;
}

.hint {
  font-size: 12px;
  color: #909399;
}

.fields-tree {
  flex: 1;
  overflow-y: auto;
  padding: 10px;
}

.category-item {
  margin-bottom: 4px;
}

.category-title {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border-radius: 4px;
  cursor: pointer;
  user-select: none;
  transition: background-color 0.2s;
}

.category-title:hover {
  background: #f5f7fa;
}

.category-title.expanded {
  background: #ecf5ff;
}

.expand-icon {
  font-size: 12px;
  color: #909399;
}

.category-count {
  font-size: 12px;
  color: #909399;
}

.category-content {
  padding-left: 24px;
  padding-bottom: 8px;
}

.field-checkbox {
  display: block;
  padding: 4px 0;
  font-size: 13px;
}

.center-panel {
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 10px;
  padding: 20px 0;
}

.move-btn {
  width: 40px;
  height: 36px;
  padding: 0;
}

.selected-fields {
  flex: 1;
  overflow-y: auto;
  padding: 10px;
}

.selected-field-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  margin-bottom: 4px;
  background: #f5f7fa;
  border-radius: 4px;
  cursor: move;
  transition: background-color 0.2s;
}

.selected-field-item:hover {
  background: #ecf5ff;
}

.drag-handle {
  color: #909399;
  cursor: grab;
}

.drag-handle:active {
  cursor: grabbing;
}

.field-label {
  flex: 1;
  font-size: 13px;
  color: #303133;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 200px;
  color: #909399;
}

.empty-icon {
  font-size: 48px;
  margin-bottom: 10px;
  opacity: 0.5;
}

.dialog-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 15px 20px;
  border-top: 1px solid #e4e7ed;
}

.footer-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.footer-right {
  display: flex;
  gap: 10px;
}
</style>
