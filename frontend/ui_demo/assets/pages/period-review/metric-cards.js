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

    /** 变化率：与后端 _metric_items 同公式 (cur-prev)/|prev|，保留 1 位小数。 */
    function metricChange(key, kind) {
      const metrics = (state.context && state.context.metrics) || {};
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

    function formatRate(rate) {
      return rate === null || rate === undefined ? '—' : `${(Number(rate) * 100).toFixed(1)}%`;
    }

    function formatTarget(value, format) {
      return value === null || value === undefined ? '未设置' : formatValue(value, format);
    }

    /** 环比/同比行：净费比是反向指标（越低越好），方向判断走 rate_better='low'。 */
    function changeNode(key, kind, lowerBetter) {
      const change = metricChange(key, kind);
      if (change === null) return null;
      const good = lowerBetter ? change < 0 : change > 0;
      const cls = change === 0 ? 'pr-delta' : `pr-delta ${good ? 'is-up' : 'is-down'}`;
      const label = kind === 'mom' ? (state.context?.compare?.short_label || '环比') : '同比';
      return h('span', { class: cls, text: `${label} ${change > 0 ? '+' : ''}${change}%` });
    }

    function insightFor(key) {
      const metrics = (state.context && state.context.metrics) || {};
      const yoy = metricChange(key, 'yoy');
      const visitorYoy = metricChange('visitors', 'yoy');
      if (key === 'net_sales') {
        const visitorText = visitorYoy === null ? '流量端变化明显' : `访客同比${visitorYoy > 0 ? '增长' : '下降'} ${Math.abs(visitorYoy).toFixed(1)}%`;
        return { label: '主要问题', text: `${visitorText}，流量端是首要缺口。` };
      }
      if (key === 'profit') {
        return { label: '经营判断', text: '收入下滑叠加费比上升，本期利润承压，需要优先修复流量与投放效率。' };
      }
      if (key === 'ad_spend') {
        const metrics = (state.context && state.context.metrics) || {};
        const current = metrics.current || {};
        const items = [
          ['付费工具占比', current.paid_ipv && current.visitors ? `${((Number(current.paid_ipv) / Number(current.visitors)) * 100).toFixed(1)}%` : '暂无数据'],
          ['投产 ROI', current.roi === null || current.roi === undefined ? '暂无数据' : formatValue(current.roi, 'decimal')],
          ['加购成本', current.cart_cost === null || current.cart_cost === undefined ? '暂无数据' : formatValue(current.cart_cost, 'money')],
          ['拉新成本', current.new_cost === null || current.new_cost === undefined ? '暂无数据' : formatValue(current.new_cost, 'money')],
          ['点击成本', current.paid_cpc === null || current.paid_cpc === undefined ? '暂无数据' : formatValue(current.paid_cpc, 'money')],
        ];
        return { label: '投放效率', text: items.map(([label, value]) => `${label} ${value}`).join(' · ') };
      }
      const targetRow = findTargetRow(key);
      const target = targetRow && targetRow.target !== null && targetRow.target !== undefined ? Number(targetRow.target) : null;
      const current = metricValue(key);
      const targetText = target === null || current === null ? '当前费比需要持续关注' : `当前费比 ${formatValue(current, targetRow.format)} 高于目标 ${formatValue(target, targetRow.format)}`;
      return { label: '拖累来源', text: `${targetText}，建议优化投放结构与商品分层。` };
    }

    /**
     * 渲染三张完成率卡。目标、完成率、环比同比与经营洞察分层展示，保证结论有稳定阅读宽度。
     * 指标值为 null（周期无数据）时整卡显示空态，不臆造 0。
     */
    function renderMetricCards() {
      const grid = h('div', { class: 'pr-metric-cards' });
      CARD_SPECS.forEach((spec) => {
        const targetRow = findTargetRow(spec.targetKey);
        if (!targetRow) return;
        const value = metricValue(spec.targetKey);
        if (value === null) return;

        const rate = targetRow.achieved_rate;
        const rateState = rateClass(rate, targetRow.rate_better);
        // 目标-实际差距：reverse_rate（净费比）的 gap 已是后端口径（目标-实际），直接展示。
        const gapText = targetRow.gap === null || targetRow.gap === undefined
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

        const insight = insightFor(spec.targetKey);
        const card = h('div', {
          class: `pr-metric-card ${spec.primary ? 'pr-metric-card--primary' : ''} ${rateState}`.trim(),
        },
        h('div', { class: 'pr-metric-card__head' },
          h('span', { class: `pr-metric-card__status-dot ${rateState}`.trim(), 'aria-hidden': 'true' }),
          h('span', { class: 'pr-metric-card__label', text: spec.label }),
          spec.primary ? h('span', { class: 'pr-metric-card__priority', text: '核心结果' }) : null),
        h('strong', { class: 'pr-metric-card__value', text: formatValue(value, targetRow.format) }),
        h('small', { class: 'pr-metric-card__target', text: `目标 ${formatTarget(targetRow.target, targetRow.format)} · 差距 ${gapText}` }),
        h('div', { class: 'pr-metric-card__rate' },
          h('span', { class: 'pr-metric-card__rate-label', text: '完成率' }),
          h('strong', { text: formatRate(rate) })),
        changes.length
          ? h('div', { class: 'pr-metric-card__changes' }, ...changes)
          : h('div', { class: 'pr-metric-card__changes' },
            h('span', { class: 'pr-delta', text: compareMode === 'none' ? '未开启对比' : '对比周期无数据' })),
        h('div', { class: `pr-metric-card__insight ${spec.targetKey === 'ad_spend' ? 'pr-metric-card__insight--efficiency' : ''}`.trim() },
          h('strong', { text: insight.label }),
          h('span', { text: insight.text })),
        );
        if (rate === null || rate === undefined) {
          card.append(h('p', { class: 'pr-metric-card__hint', text: '目标未录入，完成率待补录后计算。' }));
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
