const WAN = 10000
const YI = 100000000

export function formatNumber(value, decimals = 2) {
  if (value == null || isNaN(value)) return '-'
  const num = Number(value)
  if (num === 0) return '0'
  if (Math.abs(num) >= YI) {
    return (num / YI).toFixed(decimals) + '亿'
  }
  if (Math.abs(num) >= WAN) {
    return (num / WAN).toFixed(decimals) + '万'
  }
  return num.toLocaleString('zh-CN', {
    minimumFractionDigits: 0,
    maximumFractionDigits: decimals,
  })
}

export function formatPercent(value, decimals = 2) {
  if (value == null || isNaN(value)) return '-'
  const num = Number(value)
  if (num === 0) return '0%'
  return num.toFixed(decimals) + '%'
}

export function formatCurrency(value, decimals = 2) {
  if (value == null || isNaN(value)) return '-'
  const num = Number(value)
  if (Math.abs(num) >= YI) {
    return '¥' + (num / YI).toFixed(decimals) + '亿'
  }
  if (Math.abs(num) >= WAN) {
    return '¥' + (num / WAN).toFixed(decimals) + '万'
  }
  return '¥' + num.toLocaleString('zh-CN', {
    minimumFractionDigits: 0,
    maximumFractionDigits: decimals,
  })
}

const TIER_TYPE_MAP = {
  '引流款': 'success',
  '利润款': 'primary',
  '潜力款': 'warning',
  '形象款': 'danger',
  'A': 'success',
  'B': 'warning',
  'C': 'danger',
}

export function getTierType(tier) {
  return TIER_TYPE_MAP[tier] || 'info'
}

const LEVEL_TYPE_MAP = {
  'critical': 'danger',
  'warning': 'warning',
  'info': 'info',
  'error': 'danger',
}

export function getLevelType(level) {
  return LEVEL_TYPE_MAP[level] || 'info'
}

const LEVEL_LABEL_MAP = {
  'critical': '严重',
  'warning': '警告',
  'info': '提示',
  'error': '错误',
}

export function getLevelLabel(level) {
  return LEVEL_LABEL_MAP[level] || level
}

export function safeDiv(numerator, denominator, fallback = 0) {
  if (!denominator || denominator === 0) return fallback
  return numerator / denominator
}
