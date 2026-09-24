(function (global) {
  'use strict';

  /** 周月复盘页「货品表格（列可配置）+ 字段设置浮层」模块。
   *
   *  从 period-review-live.js 的单闭包中切出（闭包状态显式化第一步，
   *  沿用 products/column-settings.js 的 deps 显式注入模式）：
   *  本模块拥有列定义 / 列开关 localStorage / 字段设置浮层的全部状态与行为。
   *
   *  deps 契约（由 period-review-live.js 提供）：
   *  - h                     DOM 工厂
   *  - productShare          行 GSV 占比计算
   *  - declineRate           行变化比例计算
   *  - safeMetric            缺失安全的指标格式化
   *  - openProductDiagnosis  打开单品诊断弹窗
   *  - renderProductAnalysis 列变更后重渲染货品区块
   */

  function createProductColumns(deps) {
    const { h, productShare, declineRate, safeMetric, openProductDiagnosis, renderProductAnalysis } = deps;

    // ------------------------------------------------- 货品表格（列可配置）
    // 「销售贡献 TOP10」与「下滑商品 TOP10」共用同一套列开关：
    // 每张表只渲染自己支持的列（scope 为 top / delta / both），
    // 开关结果写进 localStorage，跨会话保留。
    const PRODUCT_COLUMN_KEY = 'dashboard.periodReviewProductColumns';

    const PRODUCT_COLUMNS = [
      { key: 'product_id', label: '商品ID', kind: 'id', scope: 'both', default: true },
      { key: 'title', label: '商品', kind: 'title', scope: 'both', default: true, fixed: true },
      { key: 'prev_gsv', label: '上期 GSV', kind: 'money', scope: 'delta', default: true, reason: '不可判断' },
      { key: 'gsv', label: '本期 GSV', labelTop: 'GSV', kind: 'money', scope: 'both', default: true },
      { key: 'delta', label: '变化', kind: 'money', scope: 'delta', default: true, signed: true, reason: '不可判断' },
      { key: 'change_rate', label: '变化比例', kind: 'percent', scope: 'delta', default: true },
      { key: 'share_of_gsv', label: 'GSV 占比', kind: 'percent', scope: 'top', default: true },
      { key: 'net_sales', label: '净销售额', kind: 'money', scope: 'top', default: true },
      { key: 'operating_profit', label: '利润（支付预估）', kind: 'money', scope: 'both', default: true },
      { key: 'profit_rate', label: '利润率', kind: 'percent', scope: 'both', default: true },
      { key: 'gross_profit', label: '毛利', kind: 'money', scope: 'both', default: false },
      { key: 'product_cost', label: '货品成本', kind: 'money', scope: 'both', default: false },
      { key: 'buyers', label: '支付买家数', kind: 'number', scope: 'both', default: false },
      { key: 'visitors', label: '访客数', kind: 'number', scope: 'both', default: false },
      { key: 'conversion', label: '支付转化率', kind: 'percent', scope: 'both', default: false },
      { key: 'aov', label: '客单价', kind: 'money', scope: 'both', default: false },
      { key: 'ad_spend', label: '推广花费', kind: 'money', scope: 'both', default: false },
      { key: 'refund_rate', label: '退款率', kind: 'percent', scope: 'both', default: false },
      { key: 'tags', label: '商品标签', kind: 'text', scope: 'both', default: false },
    ];

    const PRODUCT_IDENTITY_KINDS = ['id', 'title'];

    function defaultProductColumns() {
      return new Set(PRODUCT_COLUMNS.filter((col) => col.default).map((col) => col.key));
    }

    function readProductColumns() {
      try {
        const raw = localStorage.getItem(PRODUCT_COLUMN_KEY);
        if (raw) {
          const parsed = JSON.parse(raw);
          if (Array.isArray(parsed)) {
            // 只保留仍然存在的列，避免旧版本存下的键变成幽灵列。
            return new Set(parsed.filter((key) => PRODUCT_COLUMNS.some((col) => col.key === key)));
          }
        }
      } catch (_) { /* localStorage 不可用时退回默认列 */ }
      return defaultProductColumns();
    }

    function storeProductColumns(keys) {
      try { localStorage.setItem(PRODUCT_COLUMN_KEY, JSON.stringify(Array.from(keys))); } catch (_) { /* 忽略写入失败 */ }
    }

    function productTableColumns(withDelta) {
      const enabled = readProductColumns();
      const scope = withDelta ? 'delta' : 'top';
      const columns = PRODUCT_COLUMNS.filter((col) => enabled.has(col.key) && (col.scope === 'both' || col.scope === scope));
      // 商品ID / 商品不能全关，否则整行只剩数字，无法定位到具体商品。
      if (!columns.some((col) => PRODUCT_IDENTITY_KINDS.includes(col.kind))) {
        columns.unshift(PRODUCT_COLUMNS.find((col) => col.kind === 'title'));
      }
      return columns;
    }

    function productCellValue(row, col, withDelta) {
      if (col.kind === 'percent') {
        if (col.key === 'share_of_gsv') {
          const share = productShare(row);
          return { text: share === null ? '不可判断' : `${(share * 100).toFixed(2)}%`, cls: 'num' };
        }
        if (col.key === 'change_rate') {
          const rate = declineRate(row);
          if (rate === null) return { text: '不可判断', cls: 'num' };
          return { text: `${(rate * 100).toFixed(2)}%`, cls: `num pr-delta ${rate < 0 ? 'is-down' : 'is-up'}` };
        }
        return { text: safeMetric(row[col.key], 'percent'), cls: 'num' };
      }
      if (col.kind === 'id') {
        return { text: row.product_id || '--', cls: 'pr-table__pid' };
      }
      if (col.kind === 'text') {
        return { text: row[col.key] ? String(row[col.key]) : '--', cls: 'pr-table__tags' };
      }
      const value = row[col.key];
      const signable = col.signed && value !== null && value !== undefined;
      return {
        text: safeMetric(value, col.kind, col.reason || '暂无数据'),
        cls: signable ? `num pr-delta ${Number(value) < 0 ? 'is-down' : 'is-up'}` : 'num',
      };
    }

    function productTitleCell(row) {
      const full = row.title || row.product_id || '';
      return h('td', { class: 'pr-table__title' },
        row.image_url ? h('img', { src: row.image_url, alt: '', loading: 'lazy' }) : null,
        // 标题常常很长，这里单行截断，完整标题挂在 title 上供悬停查看，避免一行占两三行高度。
        h('span', { class: 'pr-table__title-text', title: full, text: full }));
    }

    // 商品ID / 商品两列宽度写死，富余宽度让给数值列：
    // 否则 table-layout: auto 会把多出来的空间按内容长度比例分给标题，标题列永远最宽。
    const PRODUCT_HEAD_WIDTH = { id: '132px', title: '320px' };

    function renderProductTable(rows, withDelta) {
      if (!rows || !rows.length) return null;
      const columns = productTableColumns(withDelta);
      const head = h('tr', null, ...columns.map((col) => h('th', {
        class: PRODUCT_IDENTITY_KINDS.includes(col.kind) || col.kind === 'text' ? '' : 'num',
        ...(PRODUCT_HEAD_WIDTH[col.kind] ? { style: `width:${PRODUCT_HEAD_WIDTH[col.kind]}` } : {}),
        text: withDelta ? col.label : (col.labelTop || col.label),
      })));
      const body = rows.map((row) => h('tr', null,
        ...columns.map((col) => {
          if (col.kind === 'title') return productTitleCell(row);
          const cell = productCellValue(row, col, withDelta);
          return h('td', { class: cell.cls, text: cell.text });
        }),
        h('td', { class: 'pr-table__action' }, h('button', {
          type: 'button', class: 'ui-button ui-button--ghost ui-button--compact', text: '查看诊断',
          onclick: () => openProductDiagnosis(row, withDelta),
        })),
      ));
      return h('table', { class: 'pr-table pr-table--products' }, h('thead', null, head), h('tbody', null, ...body));
    }

    // ------------------------------------------------------- 货品表格字段设置
    let productFieldPopover = null;
    let productFieldAnchor = null;
    let lastProductContext = null;

    function closeProductFieldPopover() {
      if (!productFieldPopover) return;
      productFieldPopover.remove();
      productFieldPopover = null;
      if (productFieldAnchor) {
        productFieldAnchor.setAttribute('aria-expanded', 'false');
        productFieldAnchor = null;
      }
    }

    function refreshProductTables() {
      if (lastProductContext) renderProductAnalysis(lastProductContext);
    }

    // 主闭包渲染货品区块时登记 context，供列开关变更后重渲染使用。
    function rememberContext(context) {
      lastProductContext = context;
    }

    function fillProductFieldPopover() {
      if (!productFieldPopover) return;
      const enabled = readProductColumns();
      const list = h('div', { class: 'pr-field-popover__list' });
      PRODUCT_COLUMNS.forEach((col) => {
        const input = h('input', { type: 'checkbox' });
        input.checked = enabled.has(col.key);
        input.disabled = !!col.fixed;
        input.addEventListener('change', () => {
          if (input.checked) enabled.add(col.key);
          else enabled.delete(col.key);
          storeProductColumns(enabled);
          refreshProductTables();
        });
        list.append(h('label', { class: `pr-field-popover__item${col.fixed ? ' is-fixed' : ''}` },
          input,
          h('span', { text: col.label }),
          col.fixed ? h('em', { text: '固定' }) : null));
      });
      productFieldPopover.replaceChildren(
        h('div', { class: 'pr-field-popover__head' },
          h('strong', { text: '字段设置' }),
          h('button', {
            type: 'button',
            class: 'pr-field-popover__reset',
            text: '恢复默认',
            onclick: () => { storeProductColumns(defaultProductColumns()); fillProductFieldPopover(); refreshProductTables(); },
          })),
        list,
        h('p', { class: 'pr-field-popover__hint', text: '两张货品表共用这套开关；表内不支持的列会自动跳过。' }),
      );
    }

    function positionProductFieldPopover() {
      if (!productFieldPopover || !productFieldAnchor) return;
      const rect = productFieldAnchor.getBoundingClientRect();
      // 锚点被滚出视口后浮层留在屏幕上没有意义，直接收起。
      if (rect.bottom < 0 || rect.top > window.innerHeight) {
        closeProductFieldPopover();
        return;
      }
      const width = productFieldPopover.offsetWidth;
      const height = productFieldPopover.offsetHeight;
      // 贴着按钮右下角，靠近视口左右边缘时自动收进来。
      const left = Math.min(Math.max(8, rect.right - width), Math.max(8, window.innerWidth - width - 8));
      // 下方放不下就翻到按钮上方，避免浮层被视口裁掉。
      const below = rect.bottom + 6;
      const top = below + height > window.innerHeight - 8 ? Math.max(8, rect.top - height - 6) : below;
      productFieldPopover.style.top = `${top}px`;
      productFieldPopover.style.left = `${left}px`;
    }

    function toggleProductFieldPopover(anchor) {
      if (productFieldPopover) {
        closeProductFieldPopover();
        return;
      }
      const popover = h('div', { class: 'pr-field-popover', role: 'group', 'aria-label': '货品表格字段设置' });
      // 浮层挂在 body 上：表格重渲染时它不会被一起清掉，可以连续勾选多个字段。
      document.body.append(popover);
      productFieldPopover = popover;
      productFieldAnchor = anchor;
      anchor.setAttribute('aria-expanded', 'true');
      fillProductFieldPopover();
      positionProductFieldPopover();
    }

    function productTableToolbar() {
      const button = h('button', {
        type: 'button',
        class: 'ui-button ui-button--ghost ui-button--compact',
        'aria-haspopup': 'true',
        'aria-expanded': 'false',
        text: '字段设置',
        onclick: (event) => {
          event.stopPropagation();
          toggleProductFieldPopover(button);
        },
      });
      return h('div', { class: 'pr-table-toolbar' },
        h('div', { class: 'pr-table-toolbar__meta' },
          h('span', { text: '货品明细' }),
          h('small', { text: '商品ID 用于与后台/BI 对齐；标题过长会截断，悬停可看全文。' })),
        button);
    }

    // 字段设置浮层：点击别处 / Esc / 视口变化都收起，避免浮层悬在错误位置。
    document.addEventListener('click', (event) => {
      if (productFieldPopover && !productFieldPopover.contains(event.target)) closeProductFieldPopover();
    });
    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape') closeProductFieldPopover();
    });
    window.addEventListener('resize', positionProductFieldPopover);
    // 固定定位的浮层需要跟着锚点走；浮层内部自己滚动列表时不算。
    window.addEventListener('scroll', (event) => {
      if (productFieldPopover && productFieldPopover.contains(event.target)) return;
      positionProductFieldPopover();
    }, true);

    return {
      rememberContext,
      renderProductTable,
      productTableToolbar,
      closeProductFieldPopover,
      positionProductFieldPopover,
    };
  }

  global.createProductColumns = createProductColumns;
})(window);
