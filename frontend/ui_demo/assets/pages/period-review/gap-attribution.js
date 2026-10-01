(function (global) {
  'use strict';

  /** 周月复盘页「目标差距归因」模块。

   *  回答用户复盘的核心问题：目标为什么没完成？差在流量、转化、客单还是付费/货品？
   *
   *  方法：连环替代法把净销售额的环比变化拆成 访客×转化率×净销售客单 三因子贡献——
   *  这是算术事实（分解恒等式成立），不是系统臆断；根因结论仍由人工在段落里填写。
   *  目标缺口进一步拆成「上期遗留」（target − 上期实际）与「本期变化」（上期 − 本期）。
   *
   *  归因线索（只报数字事实）：流量下滑最大的来源、付费三件套（花费/付费成本/净费比）
   *  变化、下滑货品合计；每条一键跳到拆因分析对应分节。
   *
   *  deps 契约（由 period-review-live.js 提供）：
   *  - h                 DOM 工厂
   *  - state             页面共享状态（context）
   *  - formatValue       金额/数值/百分数格式化
   *  - activateWorkbench 区块切换
   */

  function createGapAttribution(deps) {
    const { h, state, formatValue, activateWorkbench } = deps;

    const SOURCE_LABELS = { search: '搜索', recommend: '推荐', paid: '付费', organic: '自然' };

    function num(v) { return v === null || v === undefined || Number.isNaN(Number(v)) ? null : Number(v); }

    function pct(v, digits = 1) {
      const n = num(v);
      return n === null ? '--' : `${n > 0 ? '+' : ''}${(n * 100).toFixed(digits)}%`;
    }

    function signedMoney(v) {
      const n = num(v);
      if (n === null) return '--';
      return `${n > 0 ? '+' : ''}${formatValue(n, 'money')}`;
    }

    function ptDelta(cur, prev) {
      const a = num(cur); const b = num(prev);
      if (a === null || b === null) return null;
      return (a - b) * 100;
    }

    function jumpTo(section) {
      activateWorkbench('diagnosis');
      setTimeout(() => {
        document.querySelector(`[data-pr-diagnosis-section="${section}"]`)
          ?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }, 80);
    }

    /** 三因子连环替代分解：返回 null 表示任一周期缺少所需事实。 */
    function decompose(cur, prev) {
      const cv = num(cur.visitors);
      const cc = num(cur.conversion);
      const cn = num(cur.net_sales);
      const cb = num(cur.buyers);
      const pv = num(prev.visitors);
      const pc = num(prev.conversion);
      const pn = num(prev.net_sales);
      const pb = num(prev.buyers);
      if ([cv, cc, cn, cb, pv, pc, pn, pb].some((value) => value === null)
        || cv === 0 || pv === 0 || cb === 0 || pb === 0) return null;
      const ca = cn / cb;
      const pa = pn / pb;
      return {
        visitors: (cv - pv) * pc * pa,
        conversion: cv * (cc - pc) * pa,
        aov: cv * cc * (ca - pa),
        total: cn - pn,
        facts: {
          visitors: [pv, cv], conversion: [pc, cc], aov: [pa, ca],
        },
      };
    }

    function factorRow(name, contribution, factText) {
      // 4-3：这里的 contribution 是「该因子对销售额变化的贡献」，极性跟随销售额（越高越好）。
      const cls = contribution === 0 ? '' : MetricPolarity.deltaClass('gsv', contribution);
      return h('tr', null,
        h('td', { text: name }),
        h('td', { class: `num pr-delta ${cls}`.trim(), text: signedMoney(contribution) }),
        h('td', { class: 'num', text: factText }));
    }

    /** 归因线索行：事实 + 「去拆因」跳转。 */
    function clueLine(text, section, anchorLabel) {
      return h('li', null,
        h('span', { text: text }),
        h('button', {
          type: 'button', class: 'pr-anchor-link', text: `${anchorLabel} →`,
          onclick: () => jumpTo(section),
        }));
    }

    function buildBody(context) {
      const metrics = context.metrics || {};
      const cur = metrics.current || {};
      const prev = metrics.prev || {};
      const hasPrev = num(prev.net_sales) !== null && num(prev.net_sales) !== 0;
      const targetPath = context.target_path || {};
      const target = num(targetPath.target);
      const actual = num(cur.net_sales);
      const hasActual = actual !== null;

      if (!hasPrev && target === null) {
        return h('p', { class: 'pr-material__empty', text: '缺少对比期与目标，无法做差距归因；设置目标或切换到有环比数据的周期。' });
      }

      const parts = [];
      // —— 头部结论句
      if (target !== null) {
        if (!hasActual) {
          parts.push(h('p', { class: 'pr-gap__hint', text: '本期净销售额缺失，暂不能判断目标完成情况。' }));
        } else {
          const gap = target - actual;
          parts.push(h('p', { class: 'pr-gap__headline' },
            gap > 0
              ? h('span', { text: `目标未完成：差 ${formatValue(gap, 'money')}（达成率 ${((actual / target) * 100).toFixed(1)}%）。` })
              : h('span', { text: `目标已达成：超额 ${formatValue(-gap, 'money')}（达成率 ${((actual / target) * 100).toFixed(1)}%）。` })));
        }
      }

      // —— 三因子分解表（vs 上期）
      if (hasPrev) {
        const d = decompose(cur, prev);
        if (!d) {
          parts.push(h('p', { class: 'pr-gap__hint', text: '访客、买家或净销售额数据不完整，暂不展示三因子归因。' }));
        } else {
          const f = d.facts;
          const fmtPct = (v) => `${(v * 100).toFixed(2)}%`;
          parts.push(h('div', { class: 'pr-gap__decompose' },
            h('p', { class: 'pr-gap__hint', text: `净销售额环比变化 ${signedMoney(d.total)} 的三因子拆解（连环替代法，加总恒等于变化额）：` }),
            h('table', { class: 'pr-table' },
              h('thead', null, h('tr', null,
                h('th', { text: '因子' }), h('th', { class: 'num', text: '对净销售额的贡献' }), h('th', { class: 'num', text: '上期 → 本期' }))),
              h('tbody', null,
                factorRow('流量（访客数）', d.visitors, `${formatValue(f.visitors[0], 'number')} → ${formatValue(f.visitors[1], 'number')}`),
                factorRow('转化率', d.conversion, `${fmtPct(f.conversion[0])} → ${fmtPct(f.conversion[1])}`),
                factorRow('净销售客单价', d.aov, `${formatValue(f.aov[0], 'money')} → ${formatValue(f.aov[1], 'money')}`))),
          ));
          if (target !== null && num(prev.net_sales) !== null) {
            const legacy = target - num(prev.net_sales);
            parts.push(h('p', { class: 'pr-gap__hint' },
              `目标缺口拆两段：上期遗留 ${signedMoney(legacy)}（上期离目标就有这么远）＋ 本期变化 ${signedMoney(d.total)}。`));
          }
        }
      } else if (target !== null && hasActual) {
        parts.push(h('p', { class: 'pr-gap__hint', text: `目标缺口 ${signedMoney(target - actual)}；无上期数据，做不了三因子分解。` }));
      }

      // —— 归因线索（数字事实）
      const clues = [];
      // 流量：下滑最大的来源
      const traffic = (context.dimensions?.traffic?.items) || [];
      const falling = traffic
        .filter((t) => num(t.value) > 0 && num(t.change_rate) !== null && t.change_rate < -0.02)
        .sort((a, b) => a.change_rate - b.change_rate);
      falling.slice(0, 2).forEach((t) => {
        clues.push(clueLine(
          `流量线索：${SOURCE_LABELS[t.key] || t.key}访客 ${formatValue(t.value, 'number')}，环比 ${pct(t.change_rate)}${falling.indexOf(t) === 0 ? '（下滑最大来源）' : ''}`,
          'traffic', '去拆因 ③ 流量'));
      });
      // 付费：花费 / 付费成本 / 净费比
      const paidParts = [];
      const spendDelta = num(cur.ad_spend) !== null && num(prev.ad_spend) ? (num(cur.ad_spend) - num(prev.ad_spend)) / Math.abs(num(prev.ad_spend)) : null;
      if (spendDelta !== null) paidParts.push(`推广花费环比 ${pct(spendDelta)}`);
      const cpcDelta = num(cur.paid_cpc) !== null && num(prev.paid_cpc) ? (num(cur.paid_cpc) - num(prev.paid_cpc)) / num(prev.paid_cpc) : null;
      if (cpcDelta !== null) paidParts.push(`单次付费访客成本环比 ${pct(cpcDelta)}`);
      const ratioPt = ptDelta(cur.net_expense_ratio, prev.net_expense_ratio);
      if (ratioPt !== null) paidParts.push(`净费比 ${ratioPt > 0 ? '+' : ''}${ratioPt.toFixed(2)}pt`);
      if (paidParts.length) {
        clues.push(clueLine(`付费线索：${paidParts.join('；')}`, 'promotion', '去拆因 ② 推广'));
      }
      // 货品：下滑榜合计
      const decline = (context.products?.decline) || [];
      const declineSum = decline.reduce((s, r) => s + (num(r.delta) || 0), 0);
      if (decline.length && declineSum < 0) {
        const top = decline[0];
        clues.push(clueLine(
          `货品线索：下滑商品 ${decline.length} 个合计 ${signedMoney(declineSum)}，最大单笔 ${top.title || top.product_id} ${signedMoney(num(top.delta) || 0)}`,
          'products', '去拆因 ① 货品'));
      }
      if (clues.length) {
        parts.push(h('div', { class: 'pr-gap__clues' },
          h('p', { class: 'pr-gap__hint', text: '归因线索（数字事实，根因结论仍需人工判断）：' }),
          h('ul', { class: 'pr-actions-list pr-gap__clue-list' }, ...clues)));
      }
      return h('div', { class: 'pr-gap' }, ...parts);
    }

    function renderPanel(context, container) {
      if (!container) return;
      const body = buildBody(context);
      container.hidden = false;
      // 折叠形态：summary 直接给出三大目标完成率（复盘页最高频的问题「目标完成得怎样」
      // 不展开就能读），点开才是三因子分解与归因线索。
      container.replaceChildren(
        h('details', { class: 'ui-panel pr-gap-panel pr-gap-panel--collapsible' },
          h('summary', { class: 'pr-gap-panel__summary' },
            h('span', { class: 'pr-gap-panel__summary-title', text: '目标差距归因（流量 × 转化 × 净销售客单）' }),
            h('span', { class: 'pr-gap-panel__summary-hint', text: summaryText(context) })),
          h('div', { class: 'pr-gap-panel__body' }, body)),
      );
    }

    /** summary 摘要：三大目标完成率一行带过（口径与 target_path.targets 同源）。 */
    function summaryText(context) {
      const rows = (context.target_path && context.target_path.targets) || [];
      const parts = rows.map((row) => {
        const rate = row.achieved_rate;
        if (rate === null || rate === undefined) return `${row.label || row.key} 未设目标`;
        return `${row.label || row.key} ${(Number(rate) * 100).toFixed(0)}%`;
      });
      return parts.length ? parts.join(' · ') : '未设置目标，点开看环比三因子拆解';
    }

    return { buildBody, renderPanel };
  }

  global.createGapAttribution = createGapAttribution;
})(window);
