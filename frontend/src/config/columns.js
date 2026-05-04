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
      { key: 'status', label: '状态', width: 80 },
      { key: 'operations', label: '运营动作', width: 150 }
    ]
  },
  {
    label: '流量数据',
    key: 'traffic',
    fields: [
      { key: 'ipv', label: '商品访客数', width: 100 },
      { key: 'pv', label: '商品浏览量', width: 100 },
      { key: 'search_ipv', label: '搜索访客', width: 100 },
      { key: 'recommend_ipv', label: '推荐访客', width: 100 },
      { key: 'paid_ipv', label: '付费访客', width: 100 },
      { key: 'organic_ipv', label: '自然访客', width: 100 },
      { key: 'bounce_rate', label: '详情页跳出率', width: 100 },
      { key: 'avg_stay_duration', label: '平均停留时长', width: 120 }
    ]
  },
  {
    label: '转化数据',
    key: 'conversion',
    fields: [
      { key: 'payment_conversion', label: '商品支付转化率', width: 120 },
      { key: 'search_conversion', label: '搜索引导转化率', width: 120 },
      { key: 'cart_rate', label: '加购率', width: 80 },
      { key: 'fav_rate', label: '收藏率', width: 80 },
      { key: 'cart_users', label: '加购人数', width: 100 },
      { key: 'cart_qty', label: '加购件数', width: 100 },
      { key: 'fav_users', label: '收藏人数', width: 100 },
      { key: 'buyers', label: '支付买家数', width: 100 },
      { key: 'search_buyers', label: '搜索引导买家数', width: 120 }
    ]
  },
  {
    label: '销售数据',
    key: 'sales',
    fields: [
      { key: 'payment_amount', label: '支付金额', width: 120 },
      { key: 'payment_qty', label: '支付件数', width: 100 },
      { key: 'refund_amount', label: '成功退款金额', width: 120 },
      { key: 'net_sales', label: '净销售额', width: 120 },
      { key: 'avg_order_value', label: '笔单价', width: 100 },
      { key: 'uv_value', label: 'UV价值', width: 80 },
      { key: 'refund_rate', label: '退款率', width: 80 }
    ]
  },
  {
    label: '营销推广',
    key: 'marketing',
    fields: [
      { key: 'marketing_ipv', label: '营销推广IPV', width: 120 },
      { key: 'marketing_cost', label: '营销推广消耗', width: 120 },
      { key: 'marketing_roi', label: '营销推广ROI', width: 100 },
      { key: 'collect_add_rate', label: '收加率', width: 80 },
      { key: 'non_marketing_ipv', label: '非推广IPV', width: 120 },
      { key: 'free_search_ctr', label: '免费搜索点击率', width: 120 },
      { key: 'industry_ctr', label: '行业点击率', width: 100 },
      { key: 'bundle_qty', label: '连带购买量', width: 100 },
      { key: 'bundle_rate', label: '连带购买率', width: 100 },
      { key: 'bundle_category_width', label: '连带叶子类目宽度', width: 150 }
    ]
  },
  {
    label: '付费报表',
    key: 'paid',
    fields: [
      { key: 'impressions', label: '展现量', width: 100 },
      { key: 'clicks', label: '点击量', width: 100 },
      { key: 'cost', label: '花费', width: 100 },
      { key: 'ctr', label: '点击率', width: 80 },
      { key: 'avg_cpc', label: '平均点击花费', width: 120 },
      { key: 'cpm', label: '千次展现花费', width: 120 },
      { key: 'direct_amount', label: '直接成交金额', width: 120 },
      { key: 'indirect_amount', label: '间接成交金额', width: 120 },
      { key: 'total_amount', label: '总成交金额', width: 120 },
      { key: 'total_orders', label: '总成交笔数', width: 100 },
      { key: 'direct_orders', label: '直接成交笔数', width: 120 },
      { key: 'indirect_orders', label: '间接成交笔数', width: 120 },
      { key: 'click_conversion', label: '点击转化率', width: 100 },
      { key: 'roi', label: '投入产出比', width: 100 },
      { key: 'pre_sale_roi', label: '含预售投产比', width: 120 },
      { key: 'total_cost', label: '总成交成本', width: 120 },
      { key: 'total_cart', label: '总购物车数', width: 100 },
      { key: 'direct_cart', label: '直接购物车数', width: 120 },
      { key: 'indirect_cart', label: '间接购物车数', width: 120 },
      { key: 'cart_rate', label: '加购率', width: 80 },
      { key: 'collect_item', label: '收藏宝贝数', width: 120 },
      { key: 'collect_shop', label: '收藏店铺数', width: 120 },
      { key: 'shop_collect_cost', label: '店铺收藏成本', width: 120 },
      { key: 'total_collect_add', label: '总收藏加购数', width: 120 },
      { key: 'total_collect_add_cost', label: '总收藏加购成本', width: 140 },
      { key: 'item_collect_add', label: '宝贝收藏加购数', width: 140 },
      { key: 'item_collect_add_cost', label: '宝贝收藏加购成本', width: 150 },
      { key: 'total_collect', label: '总收藏数', width: 100 },
      { key: 'item_collect_cost', label: '宝贝收藏成本', width: 120 },
      { key: 'item_collect_rate', label: '宝贝收藏率', width: 100 },
      { key: 'cart_cost', label: '加购成本', width: 100 },
      { key: 'guide_visits', label: '引导访问量', width: 120 },
      { key: 'guide_visitors', label: '引导访问人数', width: 130 },
      { key: 'guide_potential', label: '引导访问潜客数', width: 140 },
      { key: 'guide_potential_ratio', label: '引导访问潜客占比', width: 150 },
      { key: 'new_customer_count', label: '成交新客数', width: 120 },
      { key: 'new_customer_ratio', label: '成交新客占比', width: 130 },
      { key: 'total_payers', label: '成交人数', width: 100 }
    ]
  },
  {
    label: '复购数据',
    key: 'repurchase',
    fields: [
      { key: 'repurchase_rate', label: '复购率', width: 80 },
      { key: 'repurchase_users', label: '复购用户数', width: 120 }
    ]
  },
  {
    label: '生命周期GSV',
    key: 'lifecycle_gsv',
    fields: [
      { key: 'gsv_2025_01', label: '25年1月GSV', width: 120 },
      { key: 'gsv_2025_02', label: '25年2月GSV', width: 120 },
      { key: 'gsv_2025_03', label: '25年3月GSV', width: 120 },
      { key: 'gsv_2025_04', label: '25年4月GSV', width: 120 },
      { key: 'gsv_2025_05', label: '25年5月GSV', width: 120 },
      { key: 'gsv_2025_06', label: '25年6月GSV', width: 120 },
      { key: 'gsv_2025_07', label: '25年7月GSV', width: 120 },
      { key: 'gsv_2025_08', label: '25年8月GSV', width: 120 },
      { key: 'gsv_2025_09', label: '25年9月GSV', width: 120 },
      { key: 'gsv_2025_10', label: '25年10月GSV', width: 120 },
      { key: 'gsv_2025_11', label: '25年11月GSV', width: 120 },
      { key: 'gsv_2025_12', label: '25年12月GSV', width: 120 },
      { key: 'gsv_2026_01', label: '26年1月GSV', width: 120 },
      { key: 'gsv_2026_02', label: '26年2月GSV', width: 120 },
      { key: 'gsv_2026_03', label: '26年3月GSV', width: 120 },
      { key: 'gsv_total_2025', label: '25年汇总GSV', width: 130 },
      { key: 'gsv_total_2026', label: '26年汇总GSV', width: 130 }
    ]
  },
  {
    label: '其他数据',
    key: 'other',
    fields: [
      { key: 'click_rate', label: '点击率', width: 80 },
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
