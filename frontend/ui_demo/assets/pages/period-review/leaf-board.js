(function (global) {
  'use strict';

  /** 周月复盘页「叶子类目近 3 周对比看板」模块。
   *
   *  从 period-review-live.js 的单闭包中切出（闭包状态显式化第三步，
   *  沿用 deps 显式注入模式）：拥有看板的格式化助手、KPI/对比条/明细表
   *  渲染与数据加载。看板自建 #leaf-weekly-board 节点，不覆盖主面板。
   *
   *  deps 契约（由 period-review-live.js 提供）：
   *  - h                    DOM 工厂
   *  - state                页面共享状态（leafBoard / leafBoardError / context.compare）
   *  - els                  页面 DOM 缓存（categoryBreakdown 容器）
   *  - describeRequestError 请求错误文案化
   */

  function createLeafBoard(deps) {
    const { h, state, els, describeRequestError } = deps;

    // 格式化收敛到 DemoFormat（format.js 已在本页加载），无则本地兜底。
    const fmtWan = global.DemoFormat?.fmtWan
      || ((v) => v === null || v === undefined || Number.isNaN(Number(v)) ? '--' : (Math.abs(Number(v)) >= 10000 ? `${(Number(v) / 10000).toFixed(1)}万` : Number(v).toLocaleString('zh-CN', { maximumFractionDigits: 0 })));
    const fmtPct = (v, digits = 1) => (v === null || v === undefined || Number.isNaN(Number(v))
      ? '--'
      : `${(Number(v) * 100).toFixed(digits)}%`);
    const fmtNum = (v) => v === null || v === undefined || Number.isNaN(Number(v))
      ? '--'
      : Number(v).toLocaleString('zh-CN', { maximumFractionDigits: 0 });

    function deltaBadge(rate) {
      if (rate === null || rate === undefined || Number.isNaN(Number(rate))) return h('span', { class: 'lb-delta lb-delta--na', text: '--' });
      const n = Number(rate);
      const cls = n > 0.0001 ? 'is-up' : n < -0.0001 ? 'is-down' : 'is-flat';
      const sign = n > 0 ? '+' : '';
      return h('span', { class: `lb-delta ${cls}`, text: `${sign}${(n * 100).toFixed(1)}%` });
    }
    function ppBadge(pp) {
      if (pp === null || pp === undefined || Number.isNaN(Number(pp))) return h('span', { class: 'lb-delta lb-delta--na', text: '--' });
      const n = Number(pp);
      const cls = n > 0.0001 ? 'is-up' : n < -0.0001 ? 'is-down' : 'is-flat';
      const sign = n > 0 ? '+' : '';
      return h('span', { class: `lb-delta ${cls}`, text: `${sign}${(n * 100).toFixed(1)}pp` });
    }
    function lbCell(valueNode, changeNode, compareLabel) {
      return h('td', { class: 'lb-cell' },
        h('div', { class: 'lb-cell__value' }, valueNode),
        h('div', { class: 'lb-cell__delta' },
          compareLabel ? h('span', { class: 'lb-cell__comparison-label', text: compareLabel }) : null,
          changeNode || h('span', { class: 'lb-delta--na', text: '--' }),
        ),
      );
    }
    function renderLeafBoard(data, error, loading) {
      const root = els.categoryBreakdown;
      if (!root) return;
      // 新建一个独立的看板容器，不覆盖原有 category-breakdown 内容
      let board = document.getElementById('leaf-weekly-board');
      if (!board) {
        board = h('section', { id: 'leaf-weekly-board', class: 'leaf-board' });
        root.parentNode.insertBefore(board, root);
      }
      if (loading) {
        board.replaceChildren(h('div', { class: 'pr-load-failure' }, h('p', { text: '正在加载叶子类目近 3 周数据…' })));
        return;
      }
      if (error || !data) {
        const reason = describeRequestError(error);
        board.replaceChildren(
          h('article', { class: 'ui-panel pr-analysis-panel' },
            h('div', { class: 'panel__header' },
              h('div', null, h('h3', { class: 'panel__title', text: '叶子类目近 3 周对比看板' }),
                h('p', { class: 'panel__hint', text: '数据加载失败：' + reason }))),
            h('div', { class: 'ui-panel__body' },
              h('button', { type: 'button', class: 'ui-button ui-button--compact', onclick: () => loadLeafBoard(true), text: '重试' }))),
        );
        return;
      }
      const weeks = data.weeks || {};
      const totals = data.totals || {};
      const rows = data.rows || [];
      const compare = state.context?.compare || { mode: 'previous', short_label: '环比' };
      const baselineKey = compare.mode === 'yoy' ? 'y0' : compare.mode === 'previous' ? 'w1' : null;
      const compareLabel = compare.mode === 'yoy' ? '同比' : compare.mode === 'previous' ? '环比' : '';
      const w0 = totals.w0 || {};
      const baseline = baselineKey ? totals[baselineKey] || {} : {};
      const pctChange = (current, previous) => current != null && previous != null && previous !== 0
        ? (current - previous) / Math.abs(previous) : null;
      const ppChange = (current, previous) => current != null && previous != null ? current - previous : null;

      // KPI 行
      const kpis = [
        { label: '本周净销售额', value: `¥${fmtWan(w0.net_sales)}`, delta: deltaBadge(pctChange(w0.net_sales, baseline.net_sales)) },
        { label: '本周推广花费', value: `¥${fmtWan(w0.ad_spend)}`, delta: deltaBadge(pctChange(w0.ad_spend, baseline.ad_spend)) },
        { label: '本周利润', value: `¥${fmtWan(w0.profit)}`, delta: deltaBadge(pctChange(w0.profit, baseline.profit)) },
        { label: '本周利润率', value: fmtPct(w0.profit_rate), delta: ppBadge(ppChange(w0.profit_rate, baseline.profit_rate)) },
        { label: '本周费比', value: fmtPct(w0.ad_ratio), delta: ppBadge(ppChange(w0.ad_ratio, baseline.ad_ratio)) },
      ];
      const kpiRow = h('div', { class: 'leaf-board__kpis' }, ...kpis.map((k) =>
        h('div', { class: 'leaf-board__kpi' },
          h('span', { class: 'leaf-board__kpi-label', text: k.label }),
          h('strong', { class: 'leaf-board__kpi-value', text: k.value }),
          h('span', { class: 'leaf-board__kpi-deltas' },
            compareLabel ? h('span', { class: 'lb-cell__comparison-label', text: compareLabel }) : null,
            k.delta || h('span', { class: 'lb-delta--na', text: '--' })))));

      // 4 周净销售额对比条
      const chartData = [
        { key: 'w2', label: (weeks.w2 || {}).label, value: (totals.w2 || {}).net_sales || 0 },
        { key: 'w1', label: (weeks.w1 || {}).label, value: (totals.w1 || {}).net_sales || 0 },
        { key: 'w0', label: (weeks.w0 || {}).label, value: (totals.w0 || {}).net_sales || 0 },
        { key: 'y0', label: (weeks.y0 || {}).label, value: (totals.y0 || {}).net_sales || 0 },
      ];
      const maxV = Math.max(...chartData.map((c) => Math.abs(c.value)), 1);
      const bars = h('div', { class: 'leaf-board__bars' }, ...chartData.map((c) => {
        const barClass = 'leaf-board__bar ' + (c.key === 'y0' ? 'is-y0' : c.key === 'w0' ? 'is-w0' : '');
        const barWidth = (Math.abs(c.value) / maxV * 100).toFixed(1) + '%';
        return h('div', { class: 'leaf-board__bar-row' },
          h('span', { class: 'leaf-board__bar-label', text: c.label }),
          h('div', { class: 'leaf-board__bar-track' },
            h('div', { class: barClass, style: 'width:' + barWidth })),
          h('span', { class: 'leaf-board__bar-value', text: '¥' + fmtWan(c.value) }));
      }));
      const headRow = h('tr', null,
        h('th', { class: 'leaf-board__th leaf-board__th--leaf' }, '叶子类目'),
        h('th', { class: 'leaf-board__th' }, '标品在售链接数'),
        h('th', { class: 'leaf-board__th' }, '净销售额'),
        h('th', { class: 'leaf-board__th' }, '退款率'),
        h('th', { class: 'leaf-board__th' }, '访客数'),
        h('th', { class: 'leaf-board__th' }, '转化率'),
        h('th', { class: 'leaf-board__th' }, '客单价'),
        h('th', { class: 'leaf-board__th' }, '加购率'),
        h('th', { class: 'leaf-board__th' }, '推广花费'),
        h('th', { class: 'leaf-board__th' }, '费比'),
        h('th', { class: 'leaf-board__th' }, '利润额'),
        h('th', { class: 'leaf-board__th' }, '利润率'));

      const bodyRows = rows.map((row) => {
        const wk = row.weeks || {};
        const w = wk.w0 || {};
        const baselineWeek = baselineKey ? wk[baselineKey] || {} : {};
        const cell = (field, fmt) => {
          const v = w[field];
          let display = '--';
          if (field === 'net_sales' || field === 'ad_spend' || field === 'profit') display = v != null ? `¥${fmtWan(v)}` : '--';
          else if (field === 'ipv') display = fmtNum(v);
          else if (field === 'links_active') display = fmtNum(w.links_active);
          else display = fmt(v);
          const previous = baselineWeek[field];
          const denominator = field === 'links_active' ? previous || 1 : Math.abs(previous || 1);
          const change = previous != null && previous !== 0 && v != null ? (v - previous) / denominator : null;
          return lbCell(display, deltaBadge(change), compareLabel);
        };
        // 占比类指标用百分点
        const ratioCell = (field) => lbCell(
          fmtPct(w[field]), ppBadge(ppChange(w[field], baselineWeek[field])), compareLabel);
        return h('tr', { class: 'leaf-board__row' },
          h('td', { class: 'leaf-board__td leaf-board__td--leaf' }, row.leaf),
          lbCell(fmtNum(row.links_on_sale), null, null),
          cell('net_sales'),
          cell('refund_rate', (v) => fmtPct(v)),
          cell('ipv', (v) => fmtNum(v)),
          cell('cvr', (v) => fmtPct(v)),
          cell('aov', (v) => v != null ? `¥${Number(v).toFixed(1)}` : '--'),
          cell('cart_rate', (v) => fmtPct(v)),
          cell('ad_spend'),
          ratioCell('ad_ratio'),
          cell('profit'),
          ratioCell('profit_rate'));
      });

      const table = h('table', { class: 'leaf-board__table' }, h('thead', null, headRow), h('tbody', null, ...bodyRows));

      const hint = h('p', { class: 'panel__hint leaf-board__hint' },
        `口径：周=周一至周日；本周=${(weeks.w0 || {}).start}~${(weeks.w0 || {}).end}（实际覆盖 ${(data.data_quality || {}).w0_covered_days || '?'} 天）；${baselineKey ? `${compareLabel}基线=${(weeks[baselineKey] || {}).label || '--'}；` : '当前未应用类目周对比；'}比例指标由聚合后分子/分母计算；净销售额/推广/利润绝对值<¥100 的类目行已隐藏。`);

      board.replaceChildren(
        h('article', { class: 'ui-panel pr-analysis-panel' },
          h('div', { class: 'panel__header' },
            h('div', null, h('h3', { class: 'panel__title', text: '叶子类目近 3 周对比看板' }),
              h('p', { class: 'panel__hint', text: compare.mode === 'custom'
                ? '类目周看板暂不支持自定义基线，变化值已隐藏；主复盘指标仍按所选自定义周期计算。'
                : `仅统计标品袜子；变化值按当前选择的${compareLabel || '不对比'}口径展示；在售链接数为当前在售快照。` }))),
          h('div', { class: 'ui-panel__body' },
            kpiRow, bars, table, hint)));
    }

    async function loadLeafBoard(showLoading = false) {
      if (showLoading) {
        state.leafBoardError = null;
        renderLeafBoard(state.leafBoard, null, true);
      }
      try {
        const r = await global.DemoApi.domainRequest('/api/category-analysis/leaf-weekly-board');
        state.leafBoard = r.data;
        state.leafBoardError = null;
      } catch (error) {
        state.leafBoardError = error;
      }
      renderLeafBoard(state.leafBoard, state.leafBoardError, false);
    }

    return { renderLeafBoard, loadLeafBoard };
  }

  global.createLeafBoard = createLeafBoard;
})(window);
