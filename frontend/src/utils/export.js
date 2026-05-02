import * as xlsx from 'xlsx'
import { saveAs } from 'file-saver'

/**
 * 导出表格数据为Excel
 * @param {Array} data - 表格数据
 * @param {String} fileName - 文件名
 * @param {String} sheetName - 工作表名称
 */
export function exportTableToExcel(data, fileName = 'export', sheetName = 'Sheet1') {
  if (!data || data.length === 0) {
    console.warn('No data to export')
    return
  }

  const worksheet = xlsx.utils.json_to_sheet(data)
  const workbook = xlsx.utils.book_new()
  xlsx.utils.book_append_sheet(workbook, worksheet, sheetName)
  
  xlsx.writeFile(workbook, `${fileName}.xlsx`)
}

/**
 * 导出多个工作表到一个Excel文件
 * @param {Array} sheets - 工作表数组 [{name: 'Sheet1', data: []}]
 * @param {String} fileName - 文件名
 */
export function exportMultipleSheets(sheets, fileName = 'export') {
  const workbook = xlsx.utils.book_new()
  
  sheets.forEach(sheet => {
    if (sheet.data && sheet.data.length > 0) {
      const worksheet = xlsx.utils.json_to_sheet(sheet.data)
      xlsx.utils.book_append_sheet(workbook, worksheet, sheet.name)
    }
  })
  
  xlsx.writeFile(workbook, `${fileName}.xlsx`)
}

/**
 * 导出图表为PNG图片
 * @param {Object} chartInstance - ECharts实例
 * @param {String} fileName - 文件名
 */
export function exportChartToPNG(chartInstance, fileName = 'chart') {
  if (!chartInstance) {
    console.warn('No chart instance provided')
    return
  }

  const url = chartInstance.getDataURL({
    type: 'png',
    pixelRatio: 2,
    backgroundColor: '#fff'
  })
  
  const link = document.createElement('a')
  link.download = `${fileName}.png`
  link.href = url
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
}

/**
 * 导出数据为CSV
 * @param {Array} data - 数据
 * @param {String} fileName - 文件名
 */
export function exportToCSV(data, fileName = 'export') {
  if (!data || data.length === 0) {
    console.warn('No data to export')
    return
  }

  const worksheet = xlsx.utils.json_to_sheet(data)
  const csv = xlsx.utils.sheet_to_csv(worksheet)
  
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
  saveAs(blob, `${fileName}.csv`)
}

/**
 * 导出自定义格式的报表
 * @param {Object} config - 报表配置
 */
export function exportCustomReport(config) {
  const { title, data, columns, fileName } = config
  
  const exportData = data.map(row => {
    const obj = {}
    columns.forEach(col => {
      obj[col.label] = row[col.prop]
    })
    return obj
  })
  
  exportTableToExcel(exportData, fileName, title)
}

/**
 * 批量导出多个报表为ZIP
 * @param {Array} reports - 报表数组
 * @param {String} zipFileName - ZIP文件名
 */
export async function exportBatchReports(reports, zipFileName = 'reports') {
  const JSZip = (await import('jszip')).default
  const zip = new JSZip()
  
  reports.forEach((report, index) => {
    if (report.data && report.data.length > 0) {
      const worksheet = xlsx.utils.json_to_sheet(report.data)
      const workbook = xlsx.utils.book_new()
      xlsx.utils.book_append_sheet(workbook, worksheet, 'Sheet1')
      const excelBuffer = xlsx.write(workbook, { type: 'array', bookType: 'xlsx' })
      
      zip.file(`${report.name || `report_${index + 1}`}.xlsx`, excelBuffer)
    }
  })
  
  const content = await zip.generateAsync({ type: 'blob' })
  saveAs(content, `${zipFileName}.zip`)
}
