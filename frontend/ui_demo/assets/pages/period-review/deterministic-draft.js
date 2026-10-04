(function (global) {
  'use strict';

  /** 周月复盘「确定性初稿」生成器。
   *
   *  回答用户诉求：六段复盘的「分析 / 根因 / 下一步规划」不该让用户从零手写——
   *  系统把 context 里可复现的数据事实组织成初稿正文，回填到输入框；用户在其上修改。
   *
   *  生成边界（每句话必须可反查字段）：
   *  - 只写数据事实（指标、目标达成、榜单对象、变化额、动作记录）；
   *  - 算术归因复用 gap-attribution 的三因子分解（连环替代法，加总恒等）；
   *  - 缺数据写「无法判断（原因）」，不补 0；业务因果一律标「待确认」，不推断；
   *  - 生成结果不写 localStorage 草稿——回填优先级低于本地草稿和服务端已保存内容，
   *    每次可从 context 重新计算，不遮蔽人工内容。
   *
   *  deps 契约（period-review-live.js 提供）：
   *  - formatValue    金额/数值/百分数格式化
   *  - decompose      三因子连环替代分解（gap-attribution.js 导出，可能为 null）
   */

  function createDeterministicDraft(deps) {
    const { formatValue, decompose } = deps;

    function num(v) {
      return v === null || v === undefined || Number.isNaN(Number(v)) ? null : Number(v);
    }

    function money(v) { return formatValue(v, 'money'); }
    function decimal(v) { return formatValue(v, 'decimal'); }
    function percent(v, digits = 1) {
      const n = num(v);
      // 输入一律是十进制比率（0.253 → 25.3%），与 formatValue('percent') 同口径。
      return n === null ? null : `${(n * 100).toFixed(digits)}%`;
    }
    function shareText(v) {
      const n = num(v);
      return n === null ? null : `${(n * 100).toFixed(1)}%`;
    }
    function signedPercent(v) {
      const n = num(v);
      return n === null ? null : `${n > 0 ? '+' : ''}${(n * 100).toFixed(1)}%`;
    }
    function signedMoney(v) {
      const n = num(v);
      return n === null ? null : `${n > 0 ? '+' : ''}${money(n)}`;
    }
    function signedPt(v) {
      const n = num(v);
      return n === null ? null : `${n > 0 ? '+' : ''}${n.toFixed(2)}pt`;
    }
    const joinLines = (lines) => lines.filter(Boolean).join('\n');

    function targetRow(targets, key) {
      return (targets || []).find((row) => row && row.key === key) || null;
    }

    /** 目标句：达成/未达成/未设置/疑似单位异常，口径与 _target_rows 一致。 */
    function targetSentence(row) {
      if (!row || row.target === null || row.target === undefined) return null;
      if (row.reverse_rate && Number(row.target) > 1) {
        return `净费比目标 ${row.target} 疑似单位异常，暂不参与达标判断，请人工核查。`;
      }
      const actual = num(row.actual);
      if (actual === null) return `${row.label}目标 ${formatValue(row.target, row.format)}，本期实际缺失，无法判断达成。`;
      const rate = num(row.achieved_rate);
      const rateText = rate === null ? '达成率无法计算' : `达成率 ${percent(rate)}`;
      const gap = num(row.gap);
      // 差距单位跟随指标口径：金额类是钱，比率类（净费比）是百分点，不能用 ¥ 混单位。
      const gapText = gap === null ? '' : (gap > 0
        ? `，距目标 ${formatValue(gap, row.format)}`
        : `，超额 ${formatValue(-gap, row.format)}`);
      return `${row.label}目标 ${formatValue(row.target, row.format)}，实际 ${formatValue(actual, row.format)}，${rateText}${gapText}。`;
    }

    // ------------------------------------------------------------- category_summary
    function categorySummaryDraft(context) {
      const metrics = context.metrics || {};
      const cur = metrics.current || {};
      const targetPath = context.target_path || {};
      const coverage = metrics.coverage || {};
      const analysis = [];
      if (!metrics.has_data) {
        analysis.push('本期 daily_data 缺失，无法生成销售与利润结论。');
      } else {
        if (coverage.status === 'partial') {
          analysis.push(`当前覆盖 ${coverage.observed_days}/${coverage.expected_days} 天，以下为阶段性观察。`);
        }
        const netSales = num(cur.net_sales);
        if (netSales !== null) {
          const main = targetRow(targetPath.targets, 'net_sales');
          const targetLine = targetSentence(main);
          analysis.push(targetLine || `净销售额 ${money(netSales)}（未设置目标）。`);
        } else {
          analysis.push('净销售额缺失，无法判断销售目标达成。');
        }
        const items = metrics.items || [];
        const mom = items.find((item) => item.key === 'net_sales' && num(item.mom_change) !== null);
        const yoy = items.find((item) => item.key === 'net_sales' && num(item.yoy_change) !== null);
        const compareParts = [];
        if (mom) compareParts.push(`环比 ${signedPercent(mom.mom_change)}`);
        else if (metrics.prev) compareParts.push('环比无法计算（对比期数据不完整）');
        if (yoy) compareParts.push(`同比 ${signedPercent(yoy.yoy_change)}`);
        if (compareParts.length) analysis.push(`净销售额${compareParts.join('，')}。`);
        const profit = num(cur.profit);
        analysis.push(profit === null ? '净利润暂无数据（daily_data.profit 未采集或未回填）。' : `净利润 ${money(profit)}。`);
        const ratioRow = targetRow(targetPath.targets, 'net_expense_ratio');
        if (ratioRow && num(cur.net_expense_ratio) !== null) {
          const actualText = percent(cur.net_expense_ratio);
          if (ratioRow.target !== null && ratioRow.target !== undefined) {
            analysis.push(targetSentence(ratioRow) || `净费比 ${actualText}。`);
          } else {
            analysis.push(`净费比 ${actualText}（未设置目标）。`);
          }
        } else {
          analysis.push('净费比无法计算（缺净销售额或推广花费）。');
        }
        // 月复盘：月内分周销售事实（XMind「品类汇总-周维度」）。
        const breakdown = context.breakdown || {};
        if (breakdown.grain === 'week' && (breakdown.rows || []).length) {
          const weekText = breakdown.rows
            .filter((row) => num(row.metrics && row.metrics.net_sales) !== null)
            .map((row) => `${(row.label || '').split('（')[0]} ${money(row.metrics.net_sales)}`)
            .join('；');
          if (weekText) analysis.push(`月内分周净销售额：${weekText}。`);
        }
      }

      const rootCause = [];
      if (metrics.has_data && metrics.prev && decompose) {
        const d = decompose(cur, metrics.prev);
        if (d) {
          rootCause.push(
            `净销售额环比 ${signedMoney(d.total)}，三因子算术拆解（连环替代法）：`
            + `流量贡献 ${signedMoney(d.visitors)}，转化率贡献 ${signedMoney(d.conversion)}，`
            + `客单价贡献 ${signedMoney(d.aov)}。`,
          );
          const factors = [
            ['流量（访客数）', d.visitors],
            ['转化率', d.conversion],
            ['客单价', d.aov],
          ].filter(([, value]) => num(value) !== null && num(value) < 0)
            .sort((a, b) => num(a[1]) - num(b[1]));
          if (factors.length) {
            rootCause.push(`拖累最大的因子是「${factors[0][0]}」（贡献 ${signedMoney(factors[0][1])}）；`
              + '对应业务原因（主图/价格/活动/竞争等）系统不推断，待人工确认。');
          }
        } else {
          rootCause.push('访客/买家/净销售额对比数据不完整，无法做三因子算术拆解。');
        }
      } else if (metrics.has_data) {
        rootCause.push('缺少可比对比期，无法做环比算术归因。');
      } else {
        rootCause.push('无法判断（本期数据缺失）。');
      }
      const nextStep = [];
      if (metrics.has_data && metrics.prev && decompose) {
        const d = decompose(cur, metrics.prev);
        if (d) {
          const worst = [
            ['访客规模', d.visitors],
            ['转化率', d.conversion],
            ['客单价', d.aov],
          ].filter(([, value]) => num(value) !== null && num(value) < 0)
            .sort((a, b) => num(a[1]) - num(b[1]))[0];
          if (worst) {
            nextStep.push(`下期建议优先围绕「${worst[0]}」制定恢复动作（当前贡献 ${signedMoney(worst[1])}）；具体动作与目标值需人工设定。`);
          } else {
            nextStep.push('三因子均为正贡献；保持现有打法，目标与动作需人工确认。');
          }
        }
      }
      return { analysis: joinLines(analysis), root_cause: joinLines(rootCause), next_step: joinLines(nextStep) };
    }

    // --------------------------------------------------------------------- goods
    function goodsDraft(context) {
      const products = context.products || {};
      const summary = products.summary || null;
      const analysis = [];
      const top = (products.top || []).filter((row) => num(row.net_sales) !== null || num(row.gsv) !== null);
      if (top.length) {
        const topText = top.slice(0, 3)
          .map((row, index) => `${index + 1}. ${row.title || row.product_id} ${money(num(row.net_sales) ?? num(row.gsv))}`)
          .join('；');
        analysis.push(`净销售额 TOP：${topText}。`);
        const shareSum = top.reduce((acc, row) => acc + (num(row.share_of_gsv) || 0), 0);
        if (shareSum > 0) analysis.push(`TOP${top.length} 合计占销售额 ${shareText(shareSum)}。`);
      } else {
        analysis.push('本期没有正向销售商品（无法判断货品结构）。');
      }
      if (summary) {
        const parts = [];
        if (num(summary.sold_count) !== null) parts.push(`本期动销 ${summary.sold_count} 款`);
        if (num(summary.sell_through_rate) !== null) parts.push(`动销率 ${shareText(summary.sell_through_rate)}`);
        if (num(summary.new_sold_count) !== null) parts.push(`60 天新品动销 ${summary.new_sold_count} 款`);
        if (parts.length) analysis.push(`${parts.join('，')}。`);
        const segments = (summary.segment_stats || []).filter((row) => row.count);
        if (segments.length) {
          analysis.push(`产品分层：${segments.map((row) => `${row.segment} ${row.count} 款（销售额 ${money(row.gsv)}，占 ${shareText(row.gsv_share)}）`).join('；')}。`);
        }
      }

      const rootCause = [];
      const decline = products.decline || [];
      if (decline.length) {
        const declineSum = decline.reduce((acc, row) => acc + (num(row.delta) || 0), 0);
        const topText = decline.slice(0, 3)
          .map((row) => `${row.title || row.product_id} ${signedMoney(row.delta)}`)
          .join('；');
        rootCause.push(`环比下滑商品 ${decline.length} 个，合计 ${signedMoney(declineSum)}：${topText}。`);
        const worst = decline[0] || {};
        const tags = (worst.anomaly_tags || []).slice(0, 3);
        if (tags.length) {
          rootCause.push(`「${worst.title || worst.product_id}」系统检测到：${tags.join('、')}（数据事实）；业务原因待人工确认。`);
        } else {
          rootCause.push('下滑业务原因（库存/价格/流量等）系统不推断，待人工确认。');
        }
      } else {
        rootCause.push('缺少上期可比数据或无下滑商品，无法判断货品端问题。');
      }
      const loss = (products.loss || []);
      if (loss.length) {
        const worst = loss[0];
        rootCause.push(`亏损 TOP：「${worst.title || worst.product_id}」经营利润 ${money(worst.operating_profit)}（亏损原因待确认）。`);
      }

      const nextStep = [];
      if (decline.length) {
        const worst = decline[0];
        nextStep.push(`建议对下滑最大的「${worst.title || worst.product_id}」做单品诊断并制定恢复动作；目标值需人工设定。`);
      }
      const problemCount = (products.problem_items || []).length;
      if (problemCount) {
        nextStep.push(`问题单品清单共 ${problemCount} 个（下滑/亏损/高费比跨榜合并），在货品复盘段逐个确认数据事实与业务原因。`);
      }
      return { analysis: joinLines(analysis), root_cause: joinLines(rootCause), next_step: joinLines(nextStep) };
    }

    // ---------------------------------------------------------------------- ads
    function adsDraft(context) {
      const ads = context.ads || {};
      const cur = ads.current || {};
      const delta = ads.delta || {};
      const analysis = [];
      if (num(cur.ad_spend) === null && num(cur.roi) === null) {
        analysis.push('本期推广数据缺失，无法生成广告结论。');
      } else {
        const parts = [];
        if (num(cur.ad_spend) !== null) parts.push(`推广花费 ${money(cur.ad_spend)}`);
        if (num(cur.roi) !== null) parts.push(`投产比 ${decimal(cur.roi)}`);
        if (num(ads.direct_roi) !== null) parts.push(`直接投产 ${decimal(ads.direct_roi)}`);
        if (num(cur.ad_ratio) !== null) parts.push(`费比 ${percent(cur.ad_ratio)}`);
        analysis.push(`${parts.join('，')}。`);
        const changeParts = [];
        if (num(delta.ad_spend_change) !== null) changeParts.push(`花费 ${signedPercent(delta.ad_spend_change)}`);
        if (num(delta.ad_ratio_delta_pt) !== null) changeParts.push(`费比 ${signedPt(delta.ad_ratio_delta_pt)}`);
        if (num(delta.direct_roi_delta) !== null) changeParts.push(`直接投产 ${delta.direct_roi_delta > 0 ? '+' : ''}${delta.direct_roi_delta}`);
        if (changeParts.length) analysis.push(`对比期变化：${changeParts.join('，')}。`);
        const channelTotals = ads.channel_totals;
        if (channelTotals && (channelTotals.missing_inputs || []).includes('promotion_category_scope')) {
          analysis.push('按品类复盘时渠道拆分不可用（渠道行不带商品映射），避免混入全店数据。');
        }
      }

      const rootCause = [];
      const channels = (context.dimensions?.promotion?.channels?.items) || [];
      if (channels.length) {
        const top = channels[0];
        const worst = channels
          .filter((row) => num(row.payment_change_rate) !== null)
          .sort((a, b) => num(a.payment_change_rate) - num(b.payment_change_rate))[0];
        const lines = [];
        if (top) lines.push(`花费最高的渠道是「${top.name}」（${money(top.ad_spend)}，ROI ${top.roi === null || top.roi === undefined ? '无法计算' : decimal(top.roi)}）`);
        if (worst) lines.push(`成交下滑最大的是「${worst.name}」（${signedPercent(worst.payment_change_rate)}）`);
        if (lines.length) rootCause.push(`${lines.join('；')}（数据事实，投放策略原因待人工确认）。`);
      }
      const promoItems = (context.promotion_items && context.promotion_items.items) || [];
      const withSpend = promoItems.filter((item) => num(item.totals && item.totals.ad_spend) > 0);
      if (withSpend.length) {
        const top = withSpend[0];
        const totals = top.totals || {};
        rootCause.push(`单品消耗最高：「${top.title || top.product_id}」花费 ${money(totals.ad_spend)}，`
          + `直接投产 ${totals.direct_roi === null || totals.direct_roi === undefined ? '无法计算' : decimal(totals.direct_roi)}`
          + `，拉新成本 ${totals.new_cost === null || totals.new_cost === undefined ? '无法计算' : money(totals.new_cost)}。`);
      }
      if (!rootCause.length) rootCause.push('推广数据缺失，无法判断投放问题。');

      const nextStep = [];
      if (withSpend.length) {
        const inefficient = withSpend
          .filter((item) => num(item.totals && item.totals.direct_roi) !== null)
          .sort((a, b) => num(a.totals.direct_roi) - num(b.totals.direct_roi))[0];
        if (inefficient) {
          nextStep.push(`建议优先复核「${inefficient.title || inefficient.product_id}」的投放计划（直接投产 ${decimal(inefficient.totals.direct_roi)}，为花费 TOP 中最低）；预算调整幅度需人工决定。`);
        }
      } else if (channels.length) {
        nextStep.push('建议按渠道复核花费与成交变化；具体调整需人工确认。');
      }
      return { analysis: joinLines(analysis), root_cause: joinLines(rootCause), next_step: joinLines(nextStep) };
    }

    // ------------------------------------------------------------------- market
    function marketDraft(context) {
      const market = context.market || {};
      if (!market.available) {
        const missing = (market.missing_inputs || []).join('、') || '市场源数据';
        return {
          analysis: `本期市场数据缺失（${missing}），无法生成市场观察。`,
          root_cause: '无法判断（市场数据缺失）。',
          next_step: '',
        };
      }
      const analysis = [];
      const hints = market.decision_hints || [];
      if (hints.length) {
        analysis.push(`系统观察：${hints.map((hint) => `${hint.title}（${hint.detail}）`).join('；')}。`);
      }
      const categories = (market.categories || []).filter((row) => num(row.buyers_change_rate) !== null);
      if (categories.length) {
        const up = categories.filter((row) => num(row.buyers_change_rate) > 0)
          .sort((a, b) => num(b.buyers_change_rate) - num(a.buyers_change_rate))[0];
        const down = categories.filter((row) => num(row.buyers_change_rate) < 0)
          .sort((a, b) => num(a.buyers_change_rate) - num(b.buyers_change_rate))[0];
        const parts = [];
        if (up) parts.push(`${up.category || '未分类'} 买家数 ${signedPercent(up.buyers_change_rate)}`);
        if (down) parts.push(`${down.category || '未分类'} ${signedPercent(down.buyers_change_rate)}`);
        if (parts.length) analysis.push(`类目买家数变化：${parts.join('；')}。`);
      }
      const sourceDates = market.source_dates || {};
      const itemSource = sourceDates.sycm_market_item_rank || {};
      if (num(itemSource.sample_days) !== null) {
        analysis.push(`商品榜快照覆盖 ${itemSource.sample_days || 0} 天（${itemSource.first_date || '--'} ~ ${itemSource.last_date || '--'}）；不含价格、毛利、评价维度。`);
      }
      if (!analysis.length) analysis.push('本期市场批次无可用观察。');

      const rootCause = [];
      const risingShops = (market.rivals || []).filter((row) => row.status === 'rising');
      const fallingShops = (market.rivals || []).filter((row) => row.status === 'falling');
      if (risingShops.length) {
        rootCause.push(`竞店上升预警：${risingShops.slice(0, 3).map((row) => row.shop_name || '--').join('、')}（支付买家变化 ${risingShops[0].pay_buyer_change_rate > 0 ? '+' : ''}${(num(risingShops[0].pay_buyer_change_rate) * 100).toFixed(1)}%）。`);
      }
      if (fallingShops.length) {
        rootCause.push(`竞店下滑：${fallingShops.slice(0, 3).map((row) => row.shop_name || '--').join('、')}。`);
      }
      const risingItems = (market.competitor_items || []).filter((row) => row.status === 'rising');
      if (risingItems.length) {
        rootCause.push(`竞品上升：${risingItems.slice(0, 3).map((row) => row.title || row.item_id || '--').join('、')}。`);
      }
      if (!rootCause.length) rootCause.push('竞店/竞品本期无显著变化（覆盖不足的变化不标注）。');

      const nextStep = risingShops.length || risingItems.length
        ? '建议持续关注上升竞店/竞品的动作（价格、上新、投放）；我方应对策略需人工确认。'
        : '';
      return { analysis: joinLines(analysis), root_cause: joinLines(rootCause), next_step: nextStep };
    }

    // ------------------------------------------------------------------ summary
    function summaryDraft(context) {
      const done = context.actions_done || [];
      const analysis = [];
      if (done.length) {
        analysis.push(`本期已完成动作 ${done.length} 项：${done.slice(0, 3).map((row) => `${row.product_id} ${row.action_type || '动作'}（执行 ${row.executed_at || '--'}）`).join('；')}。`);
      } else {
        analysis.push('本期没有已完成的运营动作记录。');
      }
      const alerts = context.alerts || [];
      if (alerts.length) analysis.push(`系统告警 ${alerts.length} 条（最近：${alerts[0].title || alerts[0].alert_type || '--'}）。`);

      const rootCause = [];
      const anomalies = context.anomalies || [];
      const danger = anomalies.filter((row) => row.level === 'danger');
      if (danger.length) {
        rootCause.push(`异常日：${danger.map((row) => `${row.label}（${row.detail}）`).join('；')}。`);
      }
      const worstDay = anomalies.find((row) => row.label === '最低单日销售额');
      const bestDay = anomalies.find((row) => row.label === '最高单日销售额');
      if (bestDay && worstDay) {
        rootCause.push(`${bestDay.label}：${bestDay.detail}；${worstDay.label}：${worstDay.detail}（波动原因待人工确认）。`);
      }
      if (!rootCause.length) rootCause.push('本期无系统识别的销售异常。');

      const nextStep = [];
      const blocked = context.actions_blocked || [];
      if (blocked.length) {
        nextStep.push(`阻塞动作 ${blocked.length} 项：${blocked.slice(0, 3).map((row) => `${row.product_id} ${row.action_type || '动作'}（${row.blocked_reason || '原因未填'}，预计恢复 ${row.expected_recovery_at || '--'}）`).join('；')}。`);
      }
      const toVerify = context.actions_to_verify || [];
      if (toVerify.length) {
        nextStep.push(`待验收动作 ${toVerify.length} 项，请在「计划与动作」区确认观察结果。`);
      }
      return { analysis: joinLines(analysis), root_cause: joinLines(rootCause), next_step: joinLines(nextStep) };
    }

    // ---------------------------------------------------------------- next_plan
    function nextPlanDraft(context) {
      const metrics = context.metrics || {};
      const targetPath = context.target_path || {};
      const analysis = [];
      const main = targetRow(targetPath.targets, 'net_sales');
      if (main && num(main.target) !== null) {
        analysis.push(`本期目标 ${formatValue(main.target, main.format)}，${num(main.achieved_rate) === null ? '达成率无法计算' : `达成率 ${percent(main.achieved_rate)}`}；下期目标建议在复盘设置或经营目标页预置。`);
      } else {
        analysis.push('本期未设置目标；建议在复盘设置中填写或到经营目标页按月预置，目标需可验收。');
      }

      const rootCause = [];
      if (metrics.has_data && metrics.prev && decompose) {
        const d = decompose(metrics.current, metrics.prev);
        if (d) {
          const worst = [
            ['访客规模', d.visitors],
            ['转化率', d.conversion],
            ['客单价', d.aov],
          ].filter(([, value]) => num(value) !== null && num(value) < 0)
            .sort((a, b) => num(a[1]) - num(b[1]))[0];
          if (worst) rootCause.push(`达成路径建议优先补「${worst[0]}」（本期环比贡献 ${signedMoney(worst[1])}）；具体打法需人工确认。`);
        }
      }
      const decline = (context.products && context.products.decline) || [];
      if (decline.length) {
        rootCause.push(`货品端：先恢复下滑合计 ${signedMoney(decline.reduce((acc, row) => acc + (num(row.delta) || 0), 0))} 的 ${decline.length} 个商品。`);
      }
      if (!rootCause.length) rootCause.push('系统暂无可支撑的路径建议，请人工制定。');

      const nextStep = [];
      const planned = context.actions_planned || [];
      if (planned.length) {
        nextStep.push(`已有排期动作 ${planned.length} 项：${planned.slice(0, 3).map((row) => `${row.product_id} ${row.action_type || '动作'}（计划 ${row.planned_at || '--'}${row.assigned_to ? `，${row.assigned_to}` : ''}）`).join('；')}。`);
      } else {
        nextStep.push('暂无排期动作；可从各板块根因段把已确认问题转为动作草案（负责人 / 截止 / 验收）。');
      }
      return { analysis: joinLines(analysis), root_cause: joinLines(rootCause), next_step: joinLines(nextStep) };
    }

    const SECTION_BUILDERS = {
      category_summary: categorySummaryDraft,
      goods: goodsDraft,
      ads: adsDraft,
      market: marketDraft,
      summary: summaryDraft,
      next_plan: nextPlanDraft,
    };

    /** 入口：返回 { sections, meta }。meta 供页面渲染生成元信息条。 */
    function buildDraft(context) {
      const period = context.period || {};
      const coverage = (context.metrics && context.metrics.coverage) || {};
      const compare = context.compare || {};
      const sections = {};
      Object.entries(SECTION_BUILDERS).forEach(([key, build]) => {
        sections[key] = build(context);
      });
      const now = new Date();
      const pad = (value) => String(value).padStart(2, '0');
      return {
        sections,
        meta: {
          periodKey: period.key || '',
          periodLabel: period.label || period.key || '',
          compareLabel: compare.short_label || compare.label || '不对比',
          coverage: `${coverage.observed_days ?? 0}/${coverage.expected_days ?? '--'} 天`,
          coverageStatus: coverage.status || '',
          generatedAt: `${pad(now.getHours())}:${pad(now.getMinutes())}`,
        },
      };
    }

    return { buildDraft };
  }

  global.createDeterministicDraft = createDeterministicDraft;
})(window);
