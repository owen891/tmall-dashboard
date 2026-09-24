(function (global) {
  'use strict';

  /** 周月复盘页「目标卡 + 目标 vs 实际表」模块。
   *
   *  从 period-review-live.js 的单闭包中切出（闭包状态显式化第二步，
   *  沿用 products/column-settings.js 的 deps 显式注入模式）：
   *  拥有目标输入口径换算、达成率配色、目标卡与目标表的全部渲染与即时重算。
   *
   *  deps 契约（由 period-review-live.js 提供）：
   *  - h           DOM 工厂
   *  - formatValue 指标格式化（金额/数值/百分数）
   *  - state       页面共享状态（读 context / period，refresh 时回写 targets 行）
   *  - els         页面 DOM 缓存（target 输入框组、overview 容器）
   */

  function createTargetCards(deps) {
    const { h, formatValue, state, els } = deps;

    // 复盘设置里可录目标的多项指标，顺序与后端 TARGET_METRICS 一致。
    // 净费比是反向指标（越低越好），达成率 = 目标 ÷ 实际。
    // 目标输入框：key = 复盘上下文里的指标 key，field = 落库字段名。
    // 净费比在库里存小数（0.237），表单里按百分数显示（23.70）——换算只在
    // 出入口各做一次（targetFormValue / fillTargetInputs），别在中间层再乘除。
    const TARGET_INPUT_SPECS = [
      { key: 'net_sales', field: 'target_amount', percent: false, el: () => els.target },
      { key: 'profit', field: 'target_profit', percent: false, el: () => els.targetProfit },
      { key: 'ad_spend', field: 'target_ad_spend', percent: false, el: () => els.targetAdSpend },
      { key: 'net_expense_ratio', field: 'target_net_expense_ratio', percent: true, el: () => els.targetNetExpenseRatio },
    ];

    const TARGET_SPEC_BY_KEY = TARGET_INPUT_SPECS.reduce((acc, spec) => {
      acc[spec.key] = spec;
      return acc;
    }, {});

    function inputNumber(el) {
      if (!el) return null;
      const raw = String(el.value ?? '').trim();
      if (raw === '') return null;
      const parsed = Number(raw);
      return Number.isFinite(parsed) ? parsed : null;
    }

    /** 读输入框并换算成落库口径（百分数输入 ÷100）。空值返回 null，不臆造 0。 */
    function targetFormValue(spec) {
      const value = inputNumber(spec.el());
      if (value === null) return null;
      return spec.percent ? value / 100 : value;
    }

    function formatTargetValue(value, format) {
      if (value === null || value === undefined) return '未设置';
      if (format === 'percent') return `${(Number(value) * 100).toFixed(2)}%`;
      return formatValue(value, format);
    }

    /**
     * 达成率配色。
     * rate_better='high'：达成率越高越好（销售额/净利润额/净费比——净费比是倒数口径，
     *   实际低于目标时达成率自然 >100%）。
     * rate_better='low'：达成率越低越好（推广费。它是「预算使用率」= 实际/目标，
     *   花得少达成率就低，但那是好事，所以配色方向要反过来）。
     */
    function targetRateClass(rate, rateBetter) {
      if (rate === null || rate === undefined || Number.isNaN(Number(rate))) return '';
      const value = Number(rate);
      if (rateBetter === 'low') {
        return value <= 1 ? 'is-success' : value <= 1.1 ? 'is-warning' : 'is-danger';
      }
      return value >= 1 ? 'is-success' : value >= 0.9 ? 'is-warning' : 'is-danger';
    }

    function formatTargetRate(rate) {
      return rate === null || rate === undefined ? '—' : `${(Number(rate) * 100).toFixed(2)}%`;
    }

    /**
     * 目标表要不要显示「时间进度」：只有周期短于一个月时才有意义
     * （月内时间进度对月度恒为 100%）。用户「经营目标」表的合计面板也没有这一列。
     */
    function targetTimeProgress(period) {
      if (!period || period.type === 'month') return null;
      return period.time_progress;
    }

    /**
     * 渲染「目标 vs 实际」表。
     * timeProgress 为 null 时不渲染「时间进度」列——月复盘传 null，
     * 因为用户「经营目标」表的合计面板没有这一列，且月内时间进度恒为 100%，是噪音。
     */
    function renderTargetTable(rows, timeProgress) {
      const list = Array.isArray(rows) ? rows : [];
      if (!list.length) return h('div', { class: 'pr-target-table', hidden: true });
      // 时间进度是「每个周期一个值」（用户表里跨 4 行合并），所以用 rowspan 只渲染一次，
      // 不去逐行重复同一个数。
      const showProgress = timeProgress !== null && timeProgress !== undefined;
      const progressText = showProgress ? `${(Number(timeProgress) * 100).toFixed(2)}%` : '';
      const body = list.map((row, index) => {
        const rateText = formatTargetRate(row.achieved_rate);
        const rateClass = targetRateClass(row.achieved_rate, row.rate_better);
        const gap = row.gap;
        const gapText = gap === null || gap === undefined
          ? '—'
          : `${gap > 0 ? '+' : ''}${formatTargetValue(gap, row.format)}`;
        const cells = [
          h('td', { text: row.label }),
          h('td', { class: 'num', text: formatTargetValue(row.target, row.format) }),
          h('td', { class: 'num', text: formatTargetValue(row.actual, row.format) }),
          h('td', { class: `num ${rateClass}`.trim(), text: rateText }),
          h('td', { class: 'num', text: gapText }),
        ];
        if (showProgress && index === 0) {
          cells.push(h('td', {
            class: 'num pr-target-table__progress',
            rowspan: String(list.length),
            text: progressText,
          }));
        }
        return h('tr', { 'data-pr-target-row': row.key }, ...cells);
      });
      const headCells = [
        h('th', { text: '指标' }),
        h('th', { class: 'num', text: '目标' }),
        h('th', { class: 'num', text: '实际' }),
        h('th', { class: 'num', text: '达成率' }),
        h('th', { class: 'num', text: '差距（目标-实际）' }),
      ];
      if (showProgress) headCells.push(h('th', { class: 'num', text: '时间进度' }));
      return h('div', { class: 'pr-target-table' },
        h('p', { class: 'pr-target-table__title', text: '目标 vs 实际' }),
        h('table', { class: 'pr-target-table__grid' },
          h('thead', null, h('tr', null, ...headCells)),
          h('tbody', null, ...body),
        ),
      );
    }

    // 目标输入框改动后即时重算目标表，避免「填了没反应」。
    function refreshTargetTable() {
      if (!state.context || !state.context.target_path) return;
      const saved = state.context.target_path.targets || [];
      const rows = saved.map((row) => {
        const spec = TARGET_SPEC_BY_KEY[row.key];
        const target = spec ? targetFormValue(spec) : null;
        if (target === null) return { ...row, target: null, gap: null, achieved_rate: null };
        const actual = row.actual;
        const gap = target - (actual || 0);
        // 与后端 _target_rows 同口径：reverse_rate 的指标取倒数（净费比），其余为实际÷目标。
        const rate = row.reverse_rate
          ? (actual ? target / actual : null)
          : (actual || 0) / target;
        return { ...row, target, gap, achieved_rate: rate };
      });
      state.context.target_path.targets = rows;
      const existing = els.overview && els.overview.querySelector('.pr-target-table');
      if (existing) {
        existing.replaceWith(renderTargetTable(rows, targetTimeProgress(state.context.period)));
      }
    }

    function fillTargetInputs(review) {
      const source = review || {};
      TARGET_INPUT_SPECS.forEach((spec) => {
        const input = spec.el();
        if (!input) return;
        const raw = source[spec.field];
        const value = raw === null || raw === undefined || raw === '' ? null : Number(raw);
        if (value === null || !Number.isFinite(value)) { input.value = ''; return; }
        input.value = spec.percent ? Number((value * 100).toFixed(4)) : value;
      });
    }

    function collectTargetInputs() {
      const payload = {};
      TARGET_INPUT_SPECS.forEach((spec) => {
        payload[spec.field] = targetFormValue(spec);
      });
      return payload;
    }

    function localTargetPath(targetValue) {
      const period = state.context.period;
      // 达成率口径与后端 _target_path 保持一致：净销售额 ÷ 目标（不是 GSV）。
      const netSales = state.context.metrics.current.net_sales || 0;
      const gap = targetValue - netSales;
      const requiredDaily = period.is_ongoing && period.remaining_days > 0 && gap > 0
        ? gap / period.remaining_days
        : 0;
      return {
        target: targetValue, source: 'review', gap, achieved_rate: netSales / targetValue,
        remaining_days: period.remaining_days, required_daily: requiredDaily,
        is_ongoing: period.is_ongoing,
      };
    }

    // 目标未保存前也立即给出差距与达成路径，避免「填了没反应」。
    function refreshTargetCard() {
      if (!state.context || !els.overview) return;
      const raw = els.target ? els.target.value.trim() : '';
      const parsed = raw === '' ? null : Number(raw);
      const value = Number.isFinite(parsed) && parsed > 0 ? parsed : null;
      const path = value !== null ? localTargetPath(value) : state.context.target_path;
      const existing = els.overview.querySelector('.pr-target');
      if (existing) existing.replaceWith(renderTarget(path));
      refreshTargetTable();
    }

    function renderTarget(path) {
      const wrap = h('div', { class: 'pr-target' });
      const cell = (label, value) => h('div', { class: 'pr-target__item' }, h('span', { text: label }), h('strong', { text: value }));

      if (!path.target) {
        wrap.append(cell('本期目标', '未设置'), cell('差距', '—'), cell('达成率', '—'));
        wrap.append(h('div', { class: 'pr-target__item' },
          h('span', { text: '达成路径' }),
          h('strong', { text: '填写上方目标后自动计算' })));
        return wrap;
      }

      const rate = path.achieved_rate === null || path.achieved_rate === undefined ? null : path.achieved_rate;
      const progressClass = rate === null ? '' : rate >= 1 ? 'is-success' : rate >= 0.9 ? 'is-warning' : 'is-danger';
      const progress = h('div', { class: `pr-progress ${progressClass}`.trim() },
        h('i', { style: `width:${Math.min(Math.max(rate || 0, 0), 1) * 100}%` }));

      wrap.append(
        cell('本期目标', formatValue(path.target, 'money')),
        cell('当前销售额', formatValue((path.target || 0) - (path.gap || 0), 'money')),
        cell('差距', path.gap === null ? '—' : formatValue(path.gap, 'money')),
        h('div', { class: 'pr-target__item' },
          h('span', { text: '达成率' }),
          h('strong', { text: rate === null ? '—' : `${(rate * 100).toFixed(1)}%` }),
          progress),
        cell('剩余天数', path.is_ongoing ? `${path.remaining_days} 天` : '周期已结束'),
        cell('达成路径', path.required_daily === null ? '—' : `日均需 ${formatValue(path.required_daily, 'money')}`),
      );
      // 经营目标表没有品类维度，按品类复盘时目标仍是店铺级，必须显式提示避免误判达成率。
      if (path.scope_mismatch) {
        wrap.append(h('div', { class: 'pr-target__item pr-target__item--wide' },
          h('span', { text: '口径提示' }),
          h('strong', { text: '该目标为店铺级，未按品类拆分，达成率仅供参考' })));
      }
      return wrap;
    }

    return {
      renderTarget,
      renderTargetTable,
      targetTimeProgress,
      refreshTargetCard,
      refreshTargetTable,
      fillTargetInputs,
      collectTargetInputs,
    };
  }

  global.createTargetCards = createTargetCards;
})(window);
