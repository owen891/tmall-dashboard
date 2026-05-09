const STORAGE_KEY = 'product_column_config'

export const fieldCategories = [
  {
    key: 'basic',
    label: '基本信息',
    fields: [
      { key: 'title', label: '商品名称', width: 200, minWidth: 150 },
      { key: 'tier', label: '分层', width: 100 },
      { key: 'style', label: '风格', width: 100 },
      { key: 'category', label: '品类', width: 100 },
      { key: 'scene', label: '场景', width: 100 }
    ]
  },
  {
    key: 'sales',
    label: '销售数据',
    fields: [
      { key: 'payment_amount', label: '支付金额', width: 120 },
      { key: 'net_sales', label: '净销售额', width: 120 },
      { key: 'refund_amount', label: '退款金额', width: 120 },
      { key: 'visitors', label: '访客数', width: 100 },
      { key: 'payment_conversion', label: '转化率', width: 100 },
      { key: 'avg_order_value', label: '客单价', width: 100 }
    ]
  },
  {
    key: 'ad',
    label: '广告数据',
    fields: [
      { key: 'ad_spend', label: '广告花费', width: 120 },
      { key: 'ad_ratio', label: '广告占比', width: 100 },
      { key: 'roi', label: 'ROI', width: 80 }
    ]
  },
  {
    key: 'engagement',
    label: '互动数据',
    fields: [
      { key: 'cart_rate', label: '加购率', width: 100 },
      { key: 'fav_rate', label: '收藏率', width: 100 },
      { key: 'refund_rate', label: '退款率', width: 100 }
    ]
  }
]

export const defaultVisibleFields = [
  'payment_amount',
  'visitors',
  'payment_conversion',
  'ad_spend',
  'roi',
  'refund_rate'
]

const allFieldsMap = {}
fieldCategories.forEach(category => {
  category.fields.forEach(field => {
    allFieldsMap[field.key] = field
  })
})

export function getFieldConfig(key) {
  return allFieldsMap[key] || null
}

export function loadColumnConfig() {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored) {
      const config = JSON.parse(stored)
      if (Array.isArray(config) && config.length > 0) {
        return { visibleFields: config }
      }
    }
  } catch (e) {
    // ignore
  }
  return { visibleFields: defaultVisibleFields }
}

export function saveColumnConfig(fields) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(fields))
}
