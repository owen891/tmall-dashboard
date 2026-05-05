export function formatDate(date, format = 'YYYY-MM-DD') {
  if (!date) return ''
  
  const d = new Date(date)
  if (isNaN(d.getTime())) return ''

  const year = d.getFullYear()
  const month = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  const hours = String(d.getHours()).padStart(2, '0')
  const minutes = String(d.getMinutes()).padStart(2, '0')
  const seconds = String(d.getSeconds()).padStart(2, '0')

  const tokens = {
    'YYYY': year,
    'MM': month,
    'DD': day,
    'HH': hours,
    'mm': minutes,
    'ss': seconds,
  }

  let result = format
  for (const [token, value] of Object.entries(tokens)) {
    result = result.replace(token, String(value))
  }
  return result
}

export function parseDate(dateStr) {
  if (!dateStr) return null
  const d = new Date(dateStr)
  if (isNaN(d.getTime())) return null
  return d
}

export function getDaysBetween(startDate, endDate) {
  const start = new Date(startDate)
  const end = new Date(endDate)
  if (isNaN(start.getTime()) || isNaN(end.getTime())) return 0
  start.setHours(0, 0, 0, 0)
  end.setHours(0, 0, 0, 0)
  const diffTime = Math.abs(end - start)
  return Math.round(diffTime / (1000 * 60 * 60 * 24))
}

export function addDays(date, days) {
  if (!date) return null
  const result = new Date(date)
  if (isNaN(result.getTime())) return null
  result.setDate(result.getDate() + days)
  return result
}

export function getWeekRange(date) {
  const d = new Date(date)
  if (isNaN(d.getTime())) return null
  d.setHours(0, 0, 0, 0)
  const day = d.getDay() || 7
  const start = new Date(d)
  start.setDate(d.getDate() - day + 1)
  const end = new Date(start)
  end.setDate(start.getDate() + 6)
  return { start, end }
}

export function getMonthRange(date) {
  const d = new Date(date)
  if (isNaN(d.getTime())) return null
  d.setHours(0, 0, 0, 0)
  const start = new Date(d.getFullYear(), d.getMonth(), 1)
  const end = new Date(d.getFullYear(), d.getMonth() + 1, 0)
  return { start, end }
}
