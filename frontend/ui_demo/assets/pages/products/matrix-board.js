(function (global) {
  'use strict';

  /** 货品矩阵地图（products 页）：四象限散点 + 分层统计卡。
   *
   *  数据源 GET /api/product-overview/matrix（period/category 由 api.js 品类联动注入）。
   *  口径（2026-10-02 拍板）：费比 = 花费÷GSV；引流款 ≥30%、利润款 <10%、动销款 0；
   *  亏损与角色正交（loss 标志）。X 轴=费比（30%/10% 参考线），Y 轴=访客占比，
   *  气泡面积=净销售额，颜色=分层。只渲染净销 TOP N 气泡，其余进统计卡。
   */

  const SEGMENT_COLORS = {
    '引流款': '#ef4444',
    '利润款': '#10b981',
    '动销款': '#3b82f6',
    '亏损观察': '#9ca3af',
    '未分层': '#d1d5db',
  };

  function createMatrixBoard(deps) {
    const { renderDataState } = deps;
    // DemoFormat 全局工具（escapeHtml/money/percent 等），deps 只注入页面闭包私有的。
    const { escapeHtml } = window.DemoFormat;

    let boardData = null;
    let applying = false;

    function svgScatter(items) {
      const width = 640;
      const height = 360;
      const pad = 40;
      const maxRatio = Math.max(0.5, Math.min(...[1.0], Math.max(...items.map(i => i.ad_ratio || 0), 0.35)));
      const maxVisitors = Math.max(...items.map(i => i.visitors || 0), 1);
      const maxNet = Math.max(...items.map(i => i.net_sales || 0), 1);
      const scaleX = (v) => pad + (Math.min(v, maxRatio) / maxRatio) * (width - pad * 2);
      const scaleY = (v) => height - pad - (Math.min(v, 1) / 1) * (height - pad * 2);
      const svgNS = 'http://www.w3.org/2000/svg';
      const svg = document.createElementNS(svgNS, 'svg');
      svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
      svg.setAttribute('style', 'width:100%;height:auto');

      // 参考线：费比 30% / 10%（XMind 三分法阈值）
      [[0.30, '费比 30%'], [0.10, '费比 10%']].forEach(([ratio, label]) => {
        const x = scaleX(ratio);
        const line = document.createElementNS(svgNS, 'line');
        line.setAttribute('x1', x); line.setAttribute('y1', pad);
        line.setAttribute('x2', x); line.setAttribute('y2', height - pad);
        line.setAttribute('stroke', '#e5e7eb');
        line.setAttribute('stroke-dasharray', '4 4');
        svg.append(line);
        const text = document.createElementNS(svgNS, 'text');
        text.setAttribute('x', x + 4); text.setAttribute('y', pad + 12);
        text.setAttribute('font-size', '10'); text.setAttribute('fill', '#9ca3af');
        text.textContent = label;
        svg.append(text);
      });

      // 气泡只取净销 TOP 60，避免千点糊版
      const top = items.slice().sort((a, b) => (b.net_sales || 0) - (a.net_sales || 0)).slice(0, 60);
      const visitorTotal = items.reduce((sum, i) => sum + (i.visitors || 0), 0) || 1;
      top.forEach((item) => {
        const ratio = item.ad_ratio === null || item.ad_ratio === undefined ? 0 : item.ad_ratio;
        const share = (item.visitors || 0) / visitorTotal;
        const r = 4 + Math.sqrt(Math.max(item.net_sales || 0, 0) / maxNet) * 14;
        const circle = document.createElementNS(svgNS, 'circle');
        circle.setAttribute('cx', scaleX(ratio));
        circle.setAttribute('cy', scaleY(share));
        circle.setAttribute('r', r.toFixed(1));
        circle.setAttribute('fill', SEGMENT_COLORS[item.segment] || '#d1d5db');
        circle.setAttribute('fill-opacity', '0.45');
        circle.setAttribute('stroke', SEGMENT_COLORS[item.segment] || '#d1d5db');
        const title = document.createElementNS(svgNS, 'title');
        title.textContent = `${item.title}\n${item.segment}${item.loss ? ' · 亏损' : ''}\n费比 ${(ratio * 100).toFixed(1)}% · 净销 ${Math.round(item.net_sales).toLocaleString()} · 访客占比 ${(share * 100).toFixed(2)}%`;
        circle.append(title);
        svg.append(circle);
      });
      return svg;
    }

    function renderStats(stats) {
      const colors = SEGMENT_COLORS;
      return stats.map((entry) => {
        const color = colors[entry.segment] || '#d1d5db';
        const lossNote = entry.loss_count ? ` · 亏损 ${entry.loss_count}` : '';
        return `<div style="margin-bottom:10px">
          <div style="display:flex;justify-content:space-between;align-items:baseline;font-size:13px">
            <span style="font-weight:600"><span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:${color};margin-right:6px"></span>${escapeHtml(entry.segment)}${lossNote}</span>
            <span style="color:var(--text-secondary)">${entry.count} 款</span>
          </div>
          <div style="display:flex;gap:12px;font-size:11px;color:var(--text-secondary);margin-top:2px">
            <span>净销 ${fmtMoney(entry.net_sales)}（${fmtPct(entry.net_sales_share)}）</span>
            <span>花费 ${fmtMoney(entry.ad_spend)}</span>
            <span>均费比 ${entry.avg_ad_ratio === null || entry.avg_ad_ratio === undefined ? '--' : (entry.avg_ad_ratio * 100).toFixed(1) + '%'}</span>
          </div>
        </div>`;
      }).join('');
    }

    function fmtMoney(value) {
      if (value === null || value === undefined) return '--';
      if (Math.abs(value) >= 10000) return `¥${(value / 10000).toFixed(1)}万`;
      return `¥${Math.round(value).toLocaleString()}`;
    }

    function fmtPct(value) {
      if (value === null || value === undefined || Number.isNaN(Number(value))) return '--';
      return `${(Number(value) * 100).toFixed(1)}%`;
    }

    async function load() {
      const status = document.querySelector('[data-matrix-status]');
      const scatter = document.querySelector('[data-matrix-scatter]');
      const statsNode = document.querySelector('[data-matrix-stats]');
      try {
        const response = await DemoApi.domainRequest('/api/product-overview/matrix');
        boardData = response.data;
        if (!boardData || !boardData.available) {
          if (status) status.textContent = '当前周期没有可分层的商品数据';
          if (scatter) scatter.textContent = '暂无数据';
          if (statsNode) statsNode.textContent = '暂无数据';
          return;
        }
        if (status) {
          status.textContent = `${boardData.month} · ${boardData.items.length} 款在图口径内 · ${boardData.caliber.ad_ratio}`;
        }
        if (scatter) scatter.replaceChildren(svgScatter(boardData.items));
        if (statsNode) statsNode.innerHTML = renderStats(boardData.stats);
      } catch (error) {
        if (scatter) renderDataState(scatter, 'source-unavailable', { message: `矩阵加载失败：${error.message}` });
      }
    }

    async function loadProfitStructure() {
      const node = document.querySelector('[data-profit-structure]');
      if (!node) return;
      try {
        const response = await DemoApi.domainRequest('/api/product-overview/profit-structure');
        const data = response.data;
        if (!data || !data.available) {
          node.textContent = '当前周期没有费用结构数据（等待 daily_data 费用列采集）';
          return;
        }
        const net = data.net_sales || 0;
        const frag = document.createDocumentFragment();
        const netLine = document.createElement('p');
        netLine.textContent = `净销售额 ${fmtMoney(net)}${data.compare ? `（对比期 ${data.compare.start} ~ ${data.compare.end}）` : ''}`;
        netLine.style.cssText = 'font-weight:600;font-size:12px;color:var(--text-secondary);margin:0 0 6px';
        frag.append(netLine);
        (data.rows || []).forEach((row) => {
          const share = row.share_of_net === null || row.share_of_net === undefined ? null : row.share_of_net * 100;
          const isProfit = row.key === 'operating_profit';
          const valueText = row.value === null || row.value === undefined ? '缺失' : fmtMoney(row.value);
          const shareText = share === null ? '' : `${share.toFixed(1)}%`;
          const change = row.change_rate === null || row.change_rate === undefined
            ? '' : ` · ${(row.change_rate > 0 ? '+' : '')}${(row.change_rate * 100).toFixed(1)}%`;
          const width = Math.min(Math.abs(row.share_of_net || 0) * 100, 100);
          const color = isProfit ? (row.value < 0 ? '#dc2626' : '#059669') : '#4f46e5';
          const line = document.createElement('div');
          line.style.cssText = 'display:grid;grid-template-columns:96px 1fr auto;gap:8px;align-items:center;font-size:12px;margin-bottom:5px';
          line.innerHTML = `<span style="color:var(--text-secondary)">${escapeHtml(row.label)}</span>`
            + `<div style="height:8px;border-radius:4px;background:rgba(148,163,184,0.12);overflow:hidden"><div style="height:100%;border-radius:4px;width:${(width * 100).toFixed(1)}%;background:${color}"></div></div>`
            + `<span style="white-space:nowrap">${valueText} · ${shareText}${change}</span>`;
          frag.append(line);
        });
        if (data.caliber?.custom_cost_note) {
          const note = document.createElement('p');
          note.textContent = data.caliber.custom_cost_note;
          note.style.cssText = 'color:var(--text-secondary);font-size:11px;margin:8px 0 0';
          frag.append(note);
        }
        const identity = data.identity || {};
        if (identity.note) {
          const note = document.createElement('p');
          note.textContent = identity.note;
          note.style.cssText = 'color:var(--text-secondary);font-size:11px;margin:4px 0 0';
          frag.append(note);
        }
        node.replaceChildren(frag);
      } catch (error) {
        node.textContent = `利润结构加载失败：${error.message}`;
      }
    }

    async function applyTier() {
      if (applying || !boardData || !boardData.available) return;
      applying = true;
      const button = document.querySelector('[data-matrix-apply-tier]');
      if (button) { button.disabled = true; button.setAttribute('aria-busy', 'true'); }
      try {
        const response = await DemoApi.domainRequest('/api/product-overview/matrix/apply-tier', { method: 'POST' });
        const { updated, skipped_locked } = response.data;
        if (button) button.textContent = `已写回 ${updated} 款`;
        setTimeout(() => { if (button) button.textContent = '分层写回 tier'; }, 3000);
      } catch (error) {
        if (button) button.textContent = `写回失败：${error.message}`;
        setTimeout(() => { if (button) button.textContent = '分层写回 tier'; }, 3000);
      } finally {
        applying = false;
        if (button) { button.removeAttribute('aria-busy'); }
      }
    }

    function bind() {
      const button = document.querySelector('[data-matrix-apply-tier]');
      if (button) button.addEventListener('click', applyTier);
    }

    return { load, bind, loadProfitStructure };
  }

  global.createProductMatrixBoard = createMatrixBoard;
})(window);
