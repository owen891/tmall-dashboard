(function (global) {
  'use strict';

  /** 周月复盘「导出 Markdown」模块。

   *  定稿复盘一键导出结构化 Markdown，顺序对齐月复盘 XMind 的六大板块：
   *  品类汇总 → 货品 → 广告 → 市场监控 → 总结 → 下期规划。
   *  这是「重构成功」的检验标准：写月报时不再需要打开 XMind 对照结构。
   *
   *  数据全部来自页面 state（context + review），纯前端 Blob 下载，
   *  不新增后端接口与依赖。素材缺失的板块保留标题 + 空态说明，不臆造内容。
   *
   *  deps 契约（由 period-review-live.js 提供）：
   *  - h         DOM 工厂
   *  - state     页面共享状态（context / review / template）
   */

  function createReviewExport(deps) {
    const { h, state } = deps;

    function fmtMoney(value) {
      if (value === null || value === undefined || Number.isNaN(Number(value))) return '--';
      return `¥${Number(value).toLocaleString('zh-CN', { maximumFractionDigits: 2 })}`;
    }

    function fmtPercent(value, digits = 2) {
      if (value === null || value === undefined || Number.isNaN(Number(value))) return '--';
      return `${(Number(value) * 100).toFixed(digits)}%`;
    }

    function targetRowsMd(targetPath) {
      const rows = (targetPath && targetPath.targets) || [];
      if (!rows.length) return '_未录入目标。_\n';
      const lines = ['| 指标 | 目标 | 实际 | 达成率 |', '| --- | --- | --- | --- |'];
      rows.forEach((row) => {
        const target = row.target === null || row.target === undefined ? '未设置'
          : (row.format === 'percent' ? fmtPercent(row.target) : fmtMoney(row.target));
        const actual = row.format === 'percent' ? fmtPercent(row.actual) : fmtMoney(row.actual);
        const rate = row.achieved_rate === null || row.achieved_rate === undefined ? '—'
          : `${(Number(row.achieved_rate) * 100).toFixed(1)}%`;
        lines.push(`| ${row.label} | ${target} | ${actual} | ${rate} |`);
      });
      return `${lines.join('\n')}\n`;
    }

    /** 段落三段式（subsections 优先，text 兜底——老复盘结构仍可导出）。 */
    function sectionMd(section, savedSections) {
      const saved = (savedSections || {})[section.key] || {};
      const subs = saved.subsections;
      const lines = [`### ${section.title}`, ''];
      if (subs && typeof subs === 'object') {
        const defs = section.subsections || [];
        const seen = new Set();
        defs.forEach((def) => {
          seen.add(def.key);
          const text = String(subs[def.key] || '').trim();
          lines.push(`**${def.title}**：${text || '（未填写）'}`, '');
        });
        Object.entries(subs).forEach(([key, value]) => {
          if (seen.has(key)) return;
          const text = String(value || '').trim();
          if (text) lines.push(`**${key}**：${text}`, '');
        });
      } else if (saved.text) {
        lines.push(saved.text, '');
      } else {
        lines.push('_（未填写）_', '');
      }
      return lines.join('\n');
    }

    function problemItemsMd(products) {
      const items = (products && products.problem_items) || [];
      if (!items.length) return '_本期没有命中问题条件的商品。_\n';
      const lines = ['| 商品 | 问题来源 | 销售额 | 销售额占比 | 经营利润 | 费比 |', '| --- | --- | --- | --- | --- | --- |'];
      items.slice(0, 20).forEach((row) => {
        const share = row.gsv && products.total_gsv ? (row.gsv / products.total_gsv) : null;
        const ratio = row.gsv && row.ad_spend ? fmtPercent(row.ad_spend / row.gsv, 1) : '--';
        lines.push(`| ${row.title || row.product_id} | ${(row.problem_sources || []).join('/')} `
          + `| ${fmtMoney(row.gsv)} | ${share === null ? '--' : fmtPercent(share, 1)} `
          + `| ${fmtMoney(row.operating_profit)} | ${ratio} |`);
      });
      return `${lines.join('\n')}\n`;
    }

    function actionsMd(context) {
      const planned = context.actions_planned || [];
      const toVerify = context.actions_to_verify || [];
      if (!planned.length && !toVerify.length) return '_当前没有待执行 / 待验证动作。_\n';
      const lines = [];
      if (planned.length) {
        lines.push('**待执行 / 执行中**', '');
        planned.forEach((row) => {
          lines.push(`- ${row.product_title || row.product_id} · ${row.action_type || '动作'} · 计划 ${row.planned_at || '--'}${row.assigned_to ? ` · 负责人 ${row.assigned_to}` : ''}`);
        });
        lines.push('');
      }
      if (toVerify.length) {
        lines.push('**本期待验证**', '');
        toVerify.forEach((row) => {
          lines.push(`- ${row.product_title || row.product_id} · ${row.action_type || '动作'} · 验证周期 ${row.verification_period_key || '--'}`);
        });
        lines.push('');
      }
      return lines.join('\n');
    }

    function buildMarkdown() {
      const context = state.context;
      const review = state.review || {};
      const period = context.period;
      const periodNoun = state.mode === 'week' ? '周' : '月';
      const compare = context.compare || {};
      const out = [];
      out.push(`# ${period.label.replace(/\s/g, '')} ${periodNoun}复盘`, '');
      out.push(`> 品类：${(context.category && context.category.label) || '全部品类'} · `
        + `${period.start} ~ ${period.end} · 对比：${compare.label || '不对比'} · `
        + `复盘人：${review.reviewer || '--'} · 状态：${review.status === 'final' ? '已定稿' : '草稿'}`, '');
      out.push('## 一、品类汇总（三大指标完成情况）', '');
      out.push(targetRowsMd(context.target_path));
      const breakdown = context.breakdown;
      if (breakdown && breakdown.rows && breakdown.rows.length) {
        out.push(`**周期分解（${breakdown.grain === 'week' ? '月内分周' : '按日'}）**：`
          + breakdown.rows.map((row) => `${row.label}（净销售额 ${fmtMoney((row.metrics || {}).net_sales)}）`).join('；'), '');
      }
      const sectionOrder = {
        category_summary: '一、', goods: '二、', ads: '三、', market: '四、',
        summary: '五、', next_plan: '六、',
      };
      (state.template || []).forEach((section) => {
        out.push(`## ${sectionOrder[section.key] || ''}${section.title}`.replace('（）', ''), '');

        if (section.key === 'goods') {
          out.push(problemItemsMd(context.products));
        }
        if (section.key === 'next_plan') {
          out.push(actionsMd(context));
        }
        out.push(sectionMd(section, review.sections));
      });
      return out.join('\n');
    }

    function exportMarkdown() {
      if (!state.context || !state.context.period) return false;
      const md = buildMarkdown();
      const blob = new Blob([md], { type: 'text/markdown;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `复盘_${state.mode === 'week' ? '周' : '月'}_${state.context.period.key}.md`;
      document.body.append(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
      return true;
    }

    function exportButton() {
      return h('button', {
        type: 'button',
        class: 'ui-button',
        onclick: exportMarkdown,
      }, h('i', { 'data-lucide': 'download' }), h('span', { text: '导出复盘' }));
    }

    return { exportMarkdown, exportButton, buildMarkdown };
  }

  global.createReviewExport = createReviewExport;
})(window);
