export const fieldCategories = [
  {
    label: '基础信息',
    key: 'basic',
    fields: [
      { key: 'product_id', label: '商品ID', width: 120 },
      { key: 'title', label: '商品标题', minWidth: 200 },
      { key: 'category', label: '类目', width: 100 },
      { key: 'tier', label: '分层', width: 80 },
      { key: 'style', label: '风格', width: 80 },
      { key: 'scene', label: '场景', width: 80 },
      { key: 'manager', label: '负责人', width: 80 },
      { key: 'list_date', label: '上架日期', width: 100 },
      { key: 'status', label: '状态', width: 80 }
    ]
  },
  {
    label: '流量数据',
    key: 'traffic',
    fields: [
      { key: 'ipv', label: '访客数', width: 100 },
      { key: 'pv', label: '浏览量', width: 100 },
      { key: 'search_ipv', label: '搜索访客', width: 100 },
      { key: 'recommend_ipv', label: '推荐访客', width: 100 },
      { key: 'paid_ipv', label: '付费访客', width: 100 },
      { key: 'organic_ipv', label: '自然访客', width: 100 },
      { key: 'bounce_rate', label: '跳出率', width: 80 },
      { key: 'avg_stay_duration', label: '平均停留', width: 100 }
    ]
  },
  {
    label: '转化数据',
    key: 'conversion',
    fields: [
      { key: 'payment_conversion', label: '支付转化率', width: 100 },
      { key: 'cart_rate', label: '加购率', width: 80 },
      { key: 'fav_rate', label: '收藏率', width: 80 },
      { key: 'search_conversion', label: '搜索转化率', width: 100 },
      { key: 'cart_users', label: '加购人数', width: 100 },
      { key: 'buyers', label: '支付人数', width: 100 }
    ]
  },
  {
    label: '销售数据',
    key: 'sales',
    fields: [
      { key: 'payment_amount', label: '支付金额', width: 120 },
      { key: 'refund_amount', label: '退款金额', width: 120 },
      { key: 'net_sales', label: '净销售额', width: 120 },
      { key: 'payment_qty', label: '支付件数', width: 100 },
      { key: 'avg_order_value', label: '平均客单价', width: 100 },
      { key: 'uv_value', label: 'UV价值', width: 80 },
      { key: 'refund_rate', label: '退款率', width: 80 }
    ]
  },
  {
    label: '付费推广',
    key: 'ads',
    fields: [
      { key: 'ad_spend', label: '广告花费', width: 100 },
      { key: 'ad_roi', label: '广告ROI', width: 80 },
      { key: 'ad_ratio', label: '广告占比', width: 80 },
      { key: 'keyword_spend', label: '关键词花费', width: 100 },
      { key: 'keyword_sales', label: '关键词销售额', width: 120 },
      { key: 'keyword_roi', label: '关键词ROI', width: 80 },
      { key: 'keyword_visitors', label: '关键词访客', width: 100 },
      { key: 'keyword_ppc', label: '关键词PPC', width: 80 },
      { key: 'crowd_spend', label: '人群花费', width: 100 },
      { key: 'crowd_sales', label: '人群销售额', width: 120 },
      { key: 'crowd_roi', label: '人群ROI', width: 80 },
      { key: 'site_spend', label: '站外花费', width: 100 },
      { key: 'site_sales', label: '站外销售额', width: 120 },
      { key: 'site_roi', label: '站外ROI', width: 80 }
    ]
  },
  {
    label: '万相台',
    key: 'wanxiang',
    fields: [
      { key: 'guide_visits', label: '引导进店', width: 100 },
      { key: 'guide_visitors', label: '引导访客', width: 100 },
      { key: 'guide_potential', label: '引导潜客', width: 100 },
      { key: 'guide_potential_ratio', label: '潜客占比', width: 100 }
    ]
  },
  {
    label: '复购与关联',
    key: 'repurchase',
    fields: [
      { key: 'repurchase_rate', label: '复购率', width: 80 },
      { key: 'repurchase_users', label: '复购人数', width: 100 },
      { key: 'cross_sell_qty', label: '关联销售数', width: 100 },
      { key: 'cross_sell_rate', label: '关联销售率', width: 100 },
      { key: 'new_buyers', label: '新买家数', width: 100 },
      { key: 'new_buyer_ratio', label: '新买家占比', width: 100 }
    ]
  },
  {
    label: '其他数据',
    key: 'other',
    fields: [
      { key: 'fav_users', label: '收藏人数', width: 100 },
      { key: 'cart_qty', label: '加购件数', width: 100 },
      { key: 'click_rate', label: '点击率', width: 80 },
      { key: 'industry_ctr', label: '行业CTR', width: 80 },
      { key: 'search_click_rate', label: '搜索点击率', width: 100 },
      { key: 'score', label: '评分', width: 80 },
      { key: 'category_width', label: '品类宽度', width: 100 }
    ]
  },
  {
    label: '自定义字段',
    key: 'custom',
    fields: [
      { key: 'custom_field_1', label: '自定义字段1', width: 120 },
      { key: 'custom_field_2', label: '自定义字段2', width: 120 },
      { key: 'custom_field_3', label: '自定义字段3', width: 120 }
    ]
  }
]

export const defaultVisibleFields = [
  'title',
  'category',
  'tier',
  'style',
  'scene',
  'ipv',
  'payment_amount',
  'payment_conversion',
  'ad_spend',
  'ad_roi'
]

export const defaultTemplates = [
  {
    id: 'default',
    name: '默认视图',
    fields: defaultVisibleFields
  },
  {
    id: 'basic',
    name: '基础视图',
    fields: ['title', 'category', 'tier', 'style', 'scene', 'manager']
  },
  {
    id: 'full',
    name: '完整视图',
    fields: fieldCategories.flatMap(cat => cat.fields.map(f => f.key))
  }
]

export const STORAGE_KEY = 'product_column_config'
export const TEMPLATE_STORAGE_KEY = 'product_column_templates'

export function getFieldConfig(key) {
  for (const category of fieldCategories) {
    const field = category.fields.find(f => f.key === key)
    if (field) {
      return { ...field, category: category.label }
    }
  }
  return null
}

export function loadColumnConfig() {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved) {
      return JSON.parse(saved)
    }
  } catch (e) {
    console.error('Failed to load column config:', e)
  }
  return { visibleFields: defaultVisibleFields, template: null }
}

export function saveColumnConfig(config) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(config))
  } catch (e) {
    console.error('Failed to save column config:', e)
  }
}

export function loadTemplates() {
  try {
    const saved = localStorage.getItem(TEMPLATE_STORAGE_KEY)
    if (saved) {
      return [...defaultTemplates, ...JSON.parse(saved)]
    }
  } catch (e) {
    console.error('Failed to load templates:', e)
  }
  return defaultTemplates
}

export function saveCustomTemplate(template) {
  try {
    const existing = localStorage.getItem(TEMPLATE_STORAGE_KEY)
    const templates = existing ? JSON.parse(existing) : []
    const existingIndex = templates.findIndex(t => t.id === template.id)
    if (existingIndex >= 0) {
      templates[existingIndex] = template
    } else {
      templates.push(template)
    }
    localStorage.setItem(TEMPLATE_STORAGE_KEY, JSON.stringify(templates))
    return true
  } catch (e) {
    console.error('Failed to save template:', e)
    return false
  }
}

export function deleteCustomTemplate(templateId) {
  try {
    const existing = localStorage.getItem(TEMPLATE_STORAGE_KEY)
    if (existing) {
      const templates = JSON.parse(existing)
      const filtered = templates.filter(t => t.id !== templateId)
      localStorage.setItem(TEMPLATE_STORAGE_KEY, JSON.stringify(filtered))
    }
    return true
  } catch (e) {
    console.error('Failed to delete template:', e)
    return false
  }
}
