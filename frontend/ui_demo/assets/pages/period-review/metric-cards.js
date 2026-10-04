(function (global) {
  'use strict';

  /** 周月复盘页「四大经营指标卡」模块。

   *  对齐月复盘 XMind 的「完成情况分析」：
   *  净销售额 / 净利润 / 账单花费 / 净费比，每张卡 = 数值 + 目标 + 完成率 + 环比 + 同比。
   *  口径与复盘设置的四项目标输入同源（target_path.targets，后端 _target_rows），
   *  完成率方向（reverse_rate）与配色方向（rate_better）沿用后端口径，不在前端重算。
   *
   *  deps 契约（由 period-review-live.js 提供）：
   *  - h           DOM 工厂
   *  - state       页面共享状态（读 context.metrics / context.target_path / compare）
   */

  function createMetricCards(deps) {
    const { h, state } = deps;

    // 四大指标卡定义：targetKey 对应 target_path.targets 的行 key。
    // 账单花费沿用推广花费目标口径；净费比是推广花费 ÷ 净销售额。
    const CARD_SPECS = [
      { targetKey: 'net_sales', label: '净销售额', primary: true },
      { targetKey: 'profit', label: '净利润' },
      { targetKey: 'ad_spend', label: '账单花费', format: 'money' },
      { targetKey: 'net_expense_ratio', label: '净费比', format: 'percent' },
    ];

    function findTargetRow(key) {
      const rows = (state.context && state.context.target_path && state.context.target_path.targets) || [];
      return rows.find((row) => row.key === key) || null;
    }

    /** 指标当前值：优先 target 行的 actual（四项目标行全量覆盖），缺则退 current。 */
    function metricValue(key) {
      const row = findTargetRow(key);
      if (row && row.actual !== null && row.actual !== undefined) return Number(row.actual);
      const current = state.context && state.context.metrics && state.context.metrics.current;
      const value = current ? current[key] : null;
      return value === null || value === undefined ? null : Number(value);
    }

    /** 变化率：与后端 _metric_items 同公式 (cur-prev)/|prev|，保留 1 位小数。
     *  基线不可比（后端 comparability.comparable=false，如周复盘遇到月度兜底基线）
     *  时返回 null，由调用方展示「不可比」，绝不输出窗口错配的极端百分比。 */
    function metricChange(key, kind) {
      const metrics = (state.context && state.context.metrics) || {};
      const comparability = metrics.comparability && metrics.comparability[kind];
      if (comparability && comparability.comparable === false) return null;
      const cur = metrics.current ? metrics.current[key] : null;
      const base = kind === 'mom'
        ? (metrics.prev ? metrics.prev[key] : null)
        : (metrics.yoy ? metrics.yoy[key] : null);
      if (cur === null || cur === undefined || base === null || base === undefined || !Number(base)) return null;
      return Math.round(((Number(cur) - Number(base)) / Math.abs(Number(base))) * 1000) / 10;
    }

    function formatValue(value, format) {
      if (value === null || value === undefined || Number.isNaN(Number(value))) return '--';
      const num = Number(value);
      if (format === 'percent') return `${(num * 100).toFixed(2)}%`;
      return num.toLocaleString('zh-CN', { maximumFractionDigits: 2 });
    }

    /** 完成率配色：沿 target-cards.js targetRateClass 同口径，避免两处配色打架。 */
    function rateClass(rate, rateBetter) {
      if (rate === null || rate === undefined || Number.isNaN(Number(rate))) return '';
      const value = Number(rate);
      if (rateBetter === 'low') {
        return value <= 1 ? 'is-success' : value <= 1.1 ? 'is-warning' : 'is-danger';
      }
      return value >= 1 ? 'is-success' : value >= 0.9 ? 'is-warning' : 'is-danger';
    }

    // 4-6：完成率状态的文字表达。原来只有一个小圆点靠颜色区分（实测全站 4 个
    // `.pr-metric-card__status-dot` 是「无文本/无 aria/无图标」的纯颜色指示器），
    // 色觉障碍用户与读屏都拿不到状态。这里给每个状态配一个词，圆点保留但降级为装饰。
    const RATE_STATE_TEXT = { 'is-success': '达标', 'is-warning': '临界', 'is-danger': '未达标' };

    function formatRate(rate) {
      return rate === null || rate === undefined ? '—' : `${(Number(rate) * 100).toFixed(1)}%`;
    }

    function isSuspiciousRatioTarget(row) {
      return row && row.key === 'net_expense_ratio'
        && row.target !== null && row.target !== undefined
        && Number(row.target) > 1;
    }

    /** 利润是否部分口径（P0 #4）：以后端 profit_structure.identity.ok 为唯一判据。
     *  恒等式不平＝费用列不全（补采哨兵行），此时利润值不可当准数用。
     *  实测所有口径下 identity.ok 均为 false，故净利润卡必须常带此标注。 */
    function profitIsPartial() {
      const structure = state.context && state.context.profit_structure;
      return Boolean(structure && structure.available
        && structure.identity && structure.identity.ok === false);
    }

    function profitCaliberHint() {
      const structure = (state.context && state.context.profit_structure) || {};
      const identity = structure.identity || {};
      const sentinel = structure.sentinel_rows;
      const parts = ['利润为部分口径'];
      if (sentinel) parts.push(`${sentinel} 行利润未回填`);
      if (identity.gap !== null && identity.gap !== undefined) {
        parts.push(`恒等残差 ${Number(identity.gap).toLocaleString('zh-CN', { maximumFractionDigits: 0 })}`);
      }
      return `${parts.join('：')}，该值仅供参考。详见「利润结构（利润瀑布）」。`;
    }

    function formatTarget(value, format, row) {
      if (isSuspiciousRatioTarget(row)) return '疑似单位异常';
      return value === null || value === undefined ? '未设置' : formatValue(value, format);
    }

    /** 环比/同比行：净费比是反向指标（越低越好），方向判断走 rate_better='low'。 */
    function changeNode(key, kind, lowerBetter) {
      const metrics = (state.context && state.context.metrics) || {};
      const comparability = metrics.comparability && metrics.comparability[kind];
      const label = kind === 'mom' ? (state.context?.compare?.short_label || '环比') : '同比';
      // 基线不可比（如 4 天窗口 vs 整月兜底基线）时显式标注「不可比」，
      // 与 KPI 区 deltaNode 同口径，绝不静默丢弃、也不输出错配的极端百分比。
      if (comparability && comparability.comparable === false) {
        return h('span', { class: 'pr-delta pr-delta--na', text: `${label} 不可比` });
      }
      const change = metricChange(key, kind);
      if (change === null) return null;
      // 4-3：极性统一走 MetricPolarity，目标口径的 rate_better/reverse_rate 作为显式覆盖传入。
      const cls = change === 0
        ? 'pr-delta'
        : `pr-delta ${MetricPolarity.deltaClass(key, change, { lowerBetter })}`;
      return h('span', { class: cls, text: `${label} ${change > 0 ? '+' : ''}${change}%` });
    }

  /**
   * 渲染四张结构化指标卡。卡片只承载结果、目标、完成率和对比变化，
   * 经营判断统一放在复盘结论与拆因工作区，避免同一结论出现两次。
   * 指标值为 null（周期无数据）时整卡显示空态，不臆造 0。
   */
    function renderMetricCards() {
      const grid = h('div', { class: 'pr-metric-cards' });
      CARD_SPECS.forEach((spec) => {
        const targetRow = findTargetRow(spec.targetKey);
        if (!targetRow) return;
        const value = metricValue(spec.targetKey);
        if (value === null) return;

        const targetNeedsReview = isSuspiciousRatioTarget(targetRow);
        const rate = targetNeedsReview ? null : targetRow.achieved_rate;
        const rateState = targetNeedsReview ? 'is-warning' : rateClass(rate, targetRow.rate_better);
        // 目标-实际差距：reverse_rate（净费比）的 gap 已是后端口径（目标-实际），直接展示。
        const gapText = targetNeedsReview
          ? '待核查'
          : targetRow.gap === null || targetRow.gap === undefined
            ? '—'
            : `${targetRow.gap > 0 ? '+' : ''}${formatValue(targetRow.gap, targetRow.format)}`;

        // 环比同比基线去重：对比基线本身是同比时不重复显示同比行（与 deltaNode 同口径）。
        const compareMode = (state.context && state.context.compare && state.context.compare.mode) || 'previous';
        // 完成率反向指标（净费比 reverse_rate）的变化方向同样反转。
        const lowerBetter = targetRow.rate_better === 'low' || targetRow.reverse_rate;
        const changes = [];
        const mom = changeNode(spec.targetKey, 'mom', lowerBetter);
        if (compareMode !== 'none' && mom) changes.push(mom);
        if (compareMode !== 'yoy') {
          const yoy = changeNode(spec.targetKey, 'yoy', lowerBetter);
          if (yoy) changes.push(yoy);
        }
        // 变化率缺失时的兜底：不可比已在 changeNode 内显式成行（「xx 不可比」），
        // 这里只剩「未开启对比 / 对比周期无数据」两种情形。
        const fallbackText = compareMode === 'none' ? '未开启对比' : '对比周期无数据';

        const card = h('div', {
          class: `pr-metric-card ${spec.primary ? 'pr-metric-card--primary' : ''} ${rateState}`.trim(),
        },
        h('div', { class: 'pr-metric-card__head' },
          h('span', { class: `pr-metric-card__status ${rateState}`.trim() },
            h('span', { class: 'pr-metric-card__status-dot', 'aria-hidden': 'true' }),
            RATE_STATE_TEXT[rateState]
              ? h('span', { class: 'pr-metric-card__status-text', text: RATE_STATE_TEXT[rateState] })
              : null),
          h('span', { class: 'pr-metric-card__label', text: spec.label }),
          spec.primary ? h('span', { class: 'pr-metric-card__priority', text: '核心结果' }) : null,
          // P0 #4：净利润为部分口径时就地标注，不让读者先读脚注才知道不能全信。
          spec.targetKey === 'profit' && profitIsPartial()
            ? h('span', { class: 'pr-caliber-badge is-warning', text: '部分口径', title: profitCaliberHint() })
            : null),
        h('strong', { class: 'pr-metric-card__value', text: formatValue(value, targetRow.format) }),
        h('small', { class: 'pr-metric-card__target', text: `目标 ${formatTarget(targetRow.target, targetRow.format, targetRow)} · 差距 ${gapText}` }),
        h('div', { class: 'pr-metric-card__rate' },
          h('span', { class: 'pr-metric-card__rate-label', text: '完成率' }),
          h('strong', { text: targetNeedsReview ? '待核查' : formatRate(rate) })),
        changes.length
          ? h('div', { class: 'pr-metric-card__changes' }, ...changes)
          : h('div', { class: 'pr-metric-card__changes' },
            h('span', { class: 'pr-delta', text: fallbackText })),
        );
        if (targetNeedsReview) {
          card.append(h('p', { class: 'pr-metric-card__hint', text: '净费比目标疑似按百分数存成小数前值，暂不参与达标判断。' }));
        } else if (rate === null || rate === undefined) {
          card.append(h('p', { class: 'pr-metric-card__hint', text: '目标未录入，完成率待补录后计算。' }));
        }
        if (spec.targetKey === 'profit' && profitIsPartial()) {
          card.append(h('p', { class: 'pr-metric-card__hint', text: profitCaliberHint() }));
        }
        grid.append(card);
      });
      if (!grid.childElementCount) {
        grid.append(h('p', { class: 'pr-material__empty', text: '本期暂无指标数据。' }));
      }
      return grid;
    }

    return { renderMetricCards };
  }

  global.createMetricCards = createMetricCards;
})(window);
