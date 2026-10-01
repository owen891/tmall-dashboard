/**
 * 涨跌配色极性：唯一入口，回答「这个指标涨了算好还是算坏」。
 *
 * 为什么要有这个文件：改造前全站有 7 处各自为政的实现 ——
 *   overview-live.js        硬编码 ['ad_spend','refund_rate','expense_ratio'] 三个成本指标
 *   metric-cards.js         lowerBetter 形参，来源 targetRow.rate_better === 'low' || reverse_rate
 *   period-review-live.js   item.lower_better / metric.lower_better（后端下发）
 *   gap-attribution.js      contribution > 0（贡献方向，不是极性）
 *   leaf-board.js           n > 0（同上）
 *   product-columns.js      只看数值正负
 * 现在统一走 MetricPolarity，改口径只需要改这一个文件。
 *
 * 约定（全站一致，别改）：`is-up` = 好 = 绿（--success），`is-down` = 坏 = 红（--danger）。
 * 注意这跟「涨=红、跌=绿」的股票配色是两套语义 —— 这里 up/down 表示「变好/变坏」，
 * 不是价格方向。
 *
 * 优先级：调用方显式传入的标志（后端下发的 lower_better / rate_better）> 本文件的表 > 默认「越高越好」。
 * 显式标志优先是刻意的：目标/复盘口径按业务逐项配置，不能被通用表覆盖。
 *
 * 2026-10-01 业务确认（原「已知口径矛盾」的结论）：
 *   「推广花费」这类**绝对额**与「净费比」这类**费率**是两套语义，可以共存 ——
 *   花费涨 = 投放规模扩大（好，绿）；费率涨 = 投放效率下降（坏，红）。
 *   所以 ad_spend 归 HIGHER_IS_BETTER，与 period_matrix.MATRIX_METRICS
 *   （ad_spend lower_better=False / expense_ratio lower_better=True）一致。
 *   ⚠️ 别把它和「目标达成率」混为一谈：period_context.TARGET_METRICS 里推广费
 *   rate_better='low' 是**预算使用率**口径（实际÷目标，花超了算超标），
 *   与涨跌配色无关，不随本次调整而变。
 */
(function (global) {
  'use strict';

  // 越低越好的指标：**费率 / 单位成本 / 损失**。注意不含「花费总额」——
  // 花费总额归 HIGHER_IS_BETTER，见那里的说明。
  // 依据：services/period_context.py:METRIC_DEFS、services/period_matrix.py:MATRIX_METRICS
  //      + MATRIX_PROMO_METRICS、api/reviews_api.py 里 lower_better=True 的键。
  const LOWER_IS_BETTER = new Set([
    // 费率类（涨 = 效率下降）
    'ad_ratio',            // 费比
    'expense_ratio',       // 净费比
    'wujie_expense_ratio', // 无界净费比
    'net_expense_ratio', 'wujie_spend_ratio',
    'refund_ratio',        // 退款率
    'refund_rate',         // 退款率（BI 口径的键名）
    // 单位成本类（涨 = 获客变贵）
    'paid_cpc',            // 单次付费访客成本
    'cpc', 'cpm', 'cart_cost', 'total_fav_cart_cost', 'payment_cost',
    'product_cost', 'cost', 'cac', 'new_customer_cost',
    // 损失类
    'refund_amount',       // 退款金额
    'loss_amount', 'refund_gmv',
  ]);

  // 越高越好的指标。显式列出只是为了「改口径时看得见」，不在表里的默认也是越高越好。
  const HIGHER_IS_BETTER = new Set([
    // 花费总额类（涨 = 投放规模扩大）。2026-10-01 业务确认，原在 LOWER_IS_BETTER。
    'ad_spend',                // 推广花费
    'wujie_spend',             // 无界花费
    'brand_marketing_spend',   // 商品营销托管花费
    'gift_cost',               // 礼金总费用
    'product_sitewide_spend',  // 货品全站推花费
    'gsv', 'net_sales', 'payment_amount', 'link_gsv', 'visitors', 'buyers',
    'payment_buyers', 'payment_orders', 'payment_qty', 'aov', 'conversion',
    'payment_conversion_rate', 'cart_rate', 'fav_rate', 'roi', 'ad_roi',
    'wujie_roi', 'roi_with_presale', 'operating_profit', 'profit_rate',
    'gross_profit', 'share_of_gsv', 'clicks', 'impressions', 'cart_adds',
    'fav_items', 'total_fav_cart', 'organic_uv_value', 'new_buyers',
    'attributed_payment_amount', 'organic_payment', 'direct_payment_amount',
    'indirect_payment_amount',
  ]);

  /**
   * 该指标是不是「越低越好」。
   * @param {string} metricKey
   * @param {boolean} [explicitLowerBetter] 后端下发的 lower_better / rate_better==='low'，优先于本表
   */
  function isLowerBetter(metricKey, explicitLowerBetter) {
    if (explicitLowerBetter !== undefined && explicitLowerBetter !== null) {
      return Boolean(explicitLowerBetter);
    }
    if (LOWER_IS_BETTER.has(metricKey)) return true;
    if (HIGHER_IS_BETTER.has(metricKey)) return false;
    return false; // 不认识的键默认越高越好
  }

  /**
   * 变化方向是好事还是坏事。
   * @param {string} metricKey
   * @param {number|null} change
   * @param {{lowerBetter?: boolean, deadBand?: number}} [options]
   *        deadBand：小于该绝对值的波动视为持平（生命周期卡片用 0.05、叶子看板用 0.0001）
   * @returns {boolean|null} change 为 null/undefined/NaN 时返回 null；落在 deadBand 内返回 null
   */
  function isGood(metricKey, change, options) {
    const opts = options || {};
    const n = Number(change);
    if (change === null || change === undefined || Number.isNaN(n)) return null;
    if (n === 0) return null;
    if (opts.deadBand && Math.abs(n) <= Number(opts.deadBand)) return null;
    const lowerBetter = isLowerBetter(metricKey, opts.lowerBetter);
    return lowerBetter ? n < 0 : n > 0;
  }

  /**
   * 涨跌配色类名。
   * @returns {'is-up'|'is-down'|'is-flat'} is-up=好（绿）、is-down=坏（红）、is-flat=持平
   */
  function deltaClass(metricKey, change, options) {
    const good = isGood(metricKey, change, options);
    if (good === null) return 'is-flat';
    return good ? 'is-up' : 'is-down';
  }

  global.MetricPolarity = {
    isLowerBetter,
    isGood,
    deltaClass,
    LOWER_IS_BETTER,
    HIGHER_IS_BETTER,
  };
})(typeof window !== 'undefined' ? window : globalThis);
