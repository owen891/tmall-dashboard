(function (global) {
  'use strict';

  /** 全站共享的展示格式化工具：HTML 转义、金额/百分比/万元缩写。
   *
   *  当前实际被调用的只有 escapeHtml（各 *-live.js 的本地 escape 回退）。
   *  金额/百分比这几个函数是全站唯一契约来源：新代码必须从这里取用，
   *  不要再复制本地副本——仓库里已经有 13 份各自为政的 money()，
   *  货币符号（¥ / ￥）与小数位（0/1/2）都不一致。
   *
   *  注意 money() 按设计**不拼接货币符号**：它只负责千分位与小数位，
   *  符号由调用方按场景决定（表格内可省、指标卡上要带）。
   *  需要带符号时用 moneyWan()，或在调用方自己补。 */

  const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char]
  ));

  const money = (value, { sign = false } = {}) => {
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
