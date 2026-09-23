(function (global) {
  'use strict';

  /** 全站共享的展示格式化工具：HTML 转义、金额/百分比/万元缩写。
   *  页面脚本（*-live.js 等）统一从这里取用，不再各自复制实现；
   *  行为与被替换的各页副本一致（含 ￥ 符号与"缺失值返回 --"的约定）。 */

  const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char]
  ));

  const money = (value, { unit = 'yuan', sign = false } = {}) => {
    if (value == null || value === '' || Number.isNaN(Number(value))) return '--';
    const num = Number(value);
    const text = num.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    return sign && num > 0 ? `+${text}` : text;
  };

  const moneyWan = (value, symbol = '¥') => {
    if (value == null || value === '' || Number.isNaN(Number(value))) return '--';
    const num = Number(value);
    if (Math.abs(num) >= 10000) {
      const wan = (num / 10000).toLocaleString('zh-CN', { minimumFractionDigits: 0, maximumFractionDigits: 1 });
      return `${symbol}${wan}万`;
    }
    return `${symbol}${num.toLocaleString('zh-CN', { minimumFractionDigits: 0, maximumFractionDigits: 2 })}`;
  };

  const numberWan = (value) => {
    if (value == null || value === '' || Number.isNaN(Number(value))) return '--';
    const num = Number(value);
    if (Math.abs(num) >= 10000) return `${(num / 10000).toLocaleString('zh-CN', { maximumFractionDigits: 1 })}万`;
    return num.toLocaleString('zh-CN');
  };

  const percent = (value, digits = 2) => {
    if (value == null || value === '' || Number.isNaN(Number(value))) return '--';
    return `${(Number(value) * 100).toFixed(digits)}%`;
  };

  const fmtWan = (value) => {
    if (value == null || value === '' || Number.isNaN(Number(value))) return '--';
    const num = Number(value);
    if (Math.abs(num) >= 100000000) return `${(num / 100000000).toFixed(2)}亿`;
    if (Math.abs(num) >= 10000) return `${(num / 10000).toFixed(1)}万`;
    return num.toLocaleString('zh-CN', { maximumFractionDigits: 2 });
  };

  const fmtPct1 = (value) => {
    if (value == null || value === '' || Number.isNaN(Number(value))) return '--';
    return `${(Number(value) * 100).toFixed(1)}%`;
  };

  global.DemoFormat = Object.freeze({ escapeHtml, money, moneyWan, numberWan, percent, fmtWan, fmtPct1 });
})(window);
