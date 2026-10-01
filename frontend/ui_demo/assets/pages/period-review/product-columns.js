(function (global) {
  'use strict';

  /** 周月复盘页「货品表格（列可配置）+ 字段设置对话框」模块。

   *  字段设置复用全站公共组件 DemoFieldSelector（field-selector.js：
   *  分组 / 搜索 / 拖拽排序 / 必锁字段，overview / keyword-promotion 同款），
   *  不再自建 popover——字段多了之后平铺浮层没有搜索和分组，不可用。
   *
   *  deps 契约（由 period-review-live.js 提供）：
   *  - h                     DOM 工厂
   *  - productShare          行 销售额占比计算
   *  - declineRate           行变化比例计算
   *  - safeMetric            缺失安全的指标格式化
   *  - openProductDiagnosis  打开单品诊断弹窗
   *  - openProductTrend      打开周趋势弹窗
   *  - renderProductAnalysis 列变更后重渲染货品区块
   */

  function createProductColumns(deps) {
    const { h, productShare, declineRate, safeMetric, openProductDiagnosis, openProductTrend, renderProductAnalysis } = deps;

    // ------------------------------------------------- 货品表格（列可配置）
    // 每张榜单一套列开关（来自用户月复盘框架：「每个榜单的字段不一样，
    // 根据榜单的定义来定义展示字段」），共用同一份列定义；
    // 开关结果写进 localStorage，跨会话保留。
    const PRODUCT_COLUMN_KEY = 'dashboard.periodReviewProductColumns';

    // 列定义。group: 字段设置里的分组；boards scope 同 BOARDS；
    // fixed: 不可关（商品标题列，整行只剩数字就无法定位商品）。
    // 字段清单对齐后端 decorate 返回的全量字段（XMind 净销售 TOP 榜字段集）。
    const PRODUCT_COLUMNS = [
      // —— 商品标识
      { key: 'product_id', label: '商品ID', kind: 'id', scope: 'both', group: 'identity', default: true },
      { key: 'title', label: '商品', kind: 'title', scope: 'both', group: 'identity', default: true, fixed: true },
      { key: 'category', label: '类目', kind: 'text', scope: 'both', group: 'identity', default: false },
      // —— 销售结果（XMind：销售额 / 净销售 / 销售件数 / 客单价）
      { key: 'gsv', label: '本期销售额', labelTop: '销售额', kind: 'money', scope: 'both', group: 'sales', default: true },
      { key: 'prev_gsv', label: '上期销售额', kind: 'money', scope: 'delta', group: 'sales', default: true, reason: '不可判断' },
      { key: 'net_sales', label: '净销售额', kind: 'money', scope: 'both', group: 'sales', default: true },
      { key: 'payment_qty', label: '销售件数', kind: 'number', scope: 'both', group: 'sales', default: false },
      { key: 'share_of_gsv', label: '销售额占比', kind: 'percent', scope: 'top', group: 'sales', default: true },
      { key: 'aov', label: '客单价', kind: 'money', scope: 'both', group: 'sales', default: false },
      { key: 'refund_amount', label: '退款金额', kind: 'money', scope: 'both', group: 'sales', default: false },
      // —— 流量与转化（XMind：访客数 / 转化率）
      { key: 'visitors', label: '访客数', kind: 'number', scope: 'both', group: 'traffic', default: false },
      { key: 'buyers', label: '支付买家数', kind: 'number', scope: 'both', group: 'traffic', default: false },
      { key: 'conversion', label: '支付转化率', kind: 'percent', scope: 'both', group: 'traffic', default: false },
      // —— 利润（XMind：净利润 / 推广费 / 退款率）
      { key: 'operating_profit', label: '利润（支付预估）', kind: 'money', scope: 'both', group: 'profit', default: true },
      { key: 'profit_rate', label: '利润率', kind: 'percent', scope: 'both', group: 'profit', default: true },
      { key: 'gross_profit', label: '毛利', kind: 'money', scope: 'both', group: 'profit', default: false },
      { key: 'product_cost', label: '货品成本', kind: 'money', scope: 'both', group: 'profit', default: false },
      // —— 推广
      { key: 'ad_spend', label: '推广花费', kind: 'money', scope: 'both', group: 'ads', default: false },
      // —— 环比变化（下滑榜定位跌在哪里）
      // 4-3：极性统一走 MetricPolarity。polarityKey 声明「这列表达的是哪个指标的涨跌」——
      // 变化 / 变化比例都是销售额的派生列，极性跟随 gsv（越高越好）。
      { key: 'delta', label: '变化', kind: 'money', scope: 'delta', group: 'delta', default: true, signed: true, polarityKey: 'gsv', reason: '不可判断' },
      { key: 'change_rate', label: '变化比例', kind: 'percent', scope: 'delta', group: 'delta', default: true, polarityKey: 'gsv' },
      // —— 其他
      { key: 'refund_rate', label: '退款率', kind: 'percent', scope: 'both', group: 'other', default: false },
      { key: 'tags', label: '商品标签', kind: 'text', scope: 'both', group: 'other', default: false },
      // 异常线索：下滑榜专属固定列，直接展示后端 anomaly_tags（最多 3 个），
      // 不用逐条打开诊断弹窗就知道是流量/转化/退款问题。
      { key: 'anomaly_tags', label: '异常线索', kind: 'anomaly', scope: 'delta', group: 'other', fixed: true },
    ];

    const COLUMN_GROUPS = [
      { label: '商品标识', keys: 'identity' },
      { label: '销售结果', keys: 'sales' },
      { label: '流量与转化', keys: 'traffic' },
      { label: '利润', keys: 'profit' },
      { label: '推广', keys: 'ads' },
      { label: '环比变化', keys: 'delta' },
      { label: '其他', keys: 'other' },
    ];

    // 榜单维度配置：board（存 localStorage 的键名）+ 该榜支持的列 scope + 默认列覆盖。
    // scope: both=所有榜通用列；delta=仅下滑榜；top=仅销售榜（沿用旧 scope 语义，
    // paid/profit/loss/new 复用 both 列集，靠 defaults 差异化默认值）。
    const BOARDS = [
      {
        key: 'top', label: '销售贡献榜', withDelta: false, scope: 'top',
        defaults: { product_id: true, title: true, gsv: true, share_of_gsv: true, net_sales: true, operating_profit: true, profit_rate: true },
      },
      {
        key: 'decline', label: '下滑榜', withDelta: true, scope: 'delta',
        defaults: { product_id: true, title: true, prev_gsv: true, gsv: true, delta: true, change_rate: true, operating_profit: true, profit_rate: true },
      },
      {
        key: 'paid', label: '付费榜', withDelta: false, scope: 'both',
        defaults: { product_id: true, title: true, gsv: true, ad_spend: true, operating_profit: true, profit_rate: true, refund_rate: true },
      },
      {
        key: 'profit', label: '盈利榜', withDelta: false, scope: 'both',
        defaults: { product_id: true, title: true, gsv: true, net_sales: true, operating_profit: true, profit_rate: true, share_of_gsv: true },
      },
      {
        key: 'loss', label: '亏损榜', withDelta: false, scope: 'both',
        defaults: { product_id: true, title: true, gsv: true, ad_spend: true, operating_profit: true, profit_rate: true, refund_rate: true },
      },
      {
        key: 'new', label: '新品榜（净销）', withDelta: false, scope: 'both',
        defaults: { product_id: true, title: true, gsv: true, net_sales: true, buyers: true, conversion: true, operating_profit: true },
      },
      {
        key: 'new_paid', label: '新品榜（付费）', withDelta: false, scope: 'both',
        defaults: { product_id: true, title: true, gsv: true, ad_spend: true, conversion: true, operating_profit: true },
      },
    ];

    const PRODUCT_IDENTITY_KINDS = ['id', 'title'];

    function boardOf(boardKey) {
      return BOARDS.find((item) => item.key === boardKey) || BOARDS[0];
    }

    /** 某榜可用的列（scope 匹配），供字段设置对话框分组展示。 */
    function boardColumns(boardKey) {
      const board = boardOf(boardKey);
      return PRODUCT_COLUMNS.filter((col) => col.scope === 'both' || col.scope === board.scope);
    }

    function defaultProductColumns(boardKey) {
      const board = boardOf(boardKey);
      // 白名单：defaults 里显式为 true 的列 + 固定列（商品）才默认展示。
      return new Set(
        boardColumns(board.key).filter((col) => col.fixed || board.defaults[col.key] === true).map((col) => col.key),
      );
    }

    function readProductColumns(boardKey) {
      try {
        const raw = localStorage.getItem(`${PRODUCT_COLUMN_KEY}.${boardKey}`);
        if (raw) {
          const parsed = JSON.parse(raw);
          if (Array.isArray(parsed)) {
            // 只保留仍然存在的列，避免旧版本存下的键变成幽灵列。
            return new Set(parsed.filter((key) => PRODUCT_COLUMNS.some((col) => col.key === key)));
          }
        }
      } catch (_) { /* localStorage 不可用时退回默认列 */ }
      return defaultProductColumns(boardKey);
    }

    function storeProductColumns(boardKey, keys) {
      try { localStorage.setItem(`${PRODUCT_COLUMN_KEY}.${boardKey}`, JSON.stringify(Array.from(keys))); } catch (_) { /* 忽略写入失败 */ }
    }

    function productTableColumns(boardKey) {
      const board = boardOf(boardKey);
      const enabled = readProductColumns(board.key);
      const columns = boardColumns(board.key).filter((col) => col.fixed || enabled.has(col.key));
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
          return { text: `${(rate * 100).toFixed(2)}%`, cls: `num pr-delta ${MetricPolarity.deltaClass(col.polarityKey || col.key, rate)}` };
        }
        return { text: safeMetric(row[col.key], 'percent'), cls: 'num' };
      }
      if (col.kind === 'id') {
        return { text: row.product_id || '--', cls: 'pr-table__pid' };
      }
      if (col.kind === 'text') {
        return { text: row[col.key] ? String(row[col.key]) : '--', cls: 'pr-table__tags' };
      }
      if (col.kind === 'anomaly') {
        const tags = (row.anomaly_tags || []).slice(0, 3);
        return { text: tags.length ? tags.join(' / ') : '无异常标签', cls: 'pr-table__anomaly' + (tags.length ? ' has-tags' : '') };
      }
      const value = row[col.key];
      const signable = col.signed && value !== null && value !== undefined;
      return {
        text: safeMetric(value, col.kind, col.reason || '暂无数据'),
        cls: signable ? `num pr-delta ${MetricPolarity.deltaClass(col.polarityKey || col.key, Number(value))}` : 'num',
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
    const PRODUCT_HEAD_WIDTH = { id: '132px', title: '260px' };

    function renderProductTable(rows, boardKey) {
      if (!rows || !rows.length) return null;
      const board = boardOf(boardKey);
      const columns = productTableColumns(board.key);
      const head = h('tr', null, ...columns.map((col) => h('th', {
        class: PRODUCT_IDENTITY_KINDS.includes(col.kind) || col.kind === 'text' ? '' : 'num',
        ...(PRODUCT_HEAD_WIDTH[col.kind] ? { style: `width:${PRODUCT_HEAD_WIDTH[col.kind]}` } : {}),
        text: board.withDelta ? col.label : (col.labelTop || col.label),
      })));
      const body = rows.map((row) => h('tr', null,
        ...columns.map((col) => {
          if (col.kind === 'title') return productTitleCell(row);
          const cell = productCellValue(row, col, board.withDelta);
          return h('td', { class: cell.cls, text: cell.text });
        }),
        h('td', { class: 'pr-table__action' },
          h('button', {
            type: 'button', class: 'ui-button ui-button--ghost ui-button--compact', text: '趋势',
            title: '查看近 8 周销售额 / 访客 / 转化趋势',
            onclick: () => openProductTrend(row),
          }),
          h('button', {
            type: 'button', class: 'ui-button ui-button--ghost ui-button--compact', text: '查看诊断',
            onclick: () => openProductDiagnosis(row, board.withDelta),
          })),
      ));
      return h('div', { class: 'pr-table-scroll' },
        h('table', { class: 'pr-table pr-table--products' }, h('thead', null, head), h('tbody', null, ...body)));
    }

    // ------------------------------------------------ 货品表格字段设置（公共组件）
    // 复用全站 DemoFieldSelector（field-selector.js）：分组 / 搜索 / 拖拽排序 / 必锁列，
    // 与 overview / keyword-promotion 的字段设置同款体验。
    // 对话框挂在 body 上按需创建；一次只编辑一张榜单，切换榜单时重设配置。
    let fieldDialog = null;
    let fieldSelector = null;
    let fieldBoard = null;
    let lastProductContext = null;

    function refreshProductTables() {
      if (lastProductContext) renderProductAnalysis(lastProductContext);
    }

    // 主闭包渲染货品区块时登记 context，供列开关变更后重渲染使用。
    function rememberContext(context) {
      lastProductContext = context;
    }

    function ensureFieldDialog() {
      if (fieldDialog) return fieldDialog;
      fieldDialog = h('dialog', { class: 'modal-form ui-field-selector-dialog pr-columns-dialog' });
      document.body.append(fieldDialog);
      fieldDialog.addEventListener('close', () => { fieldDialog.close(); });
      return fieldDialog;
    }

    function fieldGroupsFor(boardKey) {
      const columns = boardColumns(boardKey);
      return COLUMN_GROUPS
        .map((group) => ({
          label: group.label,
          fields: columns
            .filter((col) => col.group === group.keys)
            .map((col) => ({ key: col.key, label: col.label, required: false, locked: Boolean(col.fixed) })),
        }))
        .filter((group) => group.fields.length);
    }

    function closeProductFieldDialog() {
      if (fieldDialog?.open) fieldDialog.close();
      fieldBoard = null;
    }

    // 字段选择器单例 + 挂载点也单例：DemoFieldSelector 闭包绑定创建时的 root 元素，
    // 每次打开换新 div 会导致它渲染进旧的 detached 节点（第二次打开空白）。
    let fieldSelectorRoot = null;

    function openProductFieldDialog(boardKey) {
      const board = boardOf(boardKey);
      const dialog = ensureFieldDialog();
      fieldBoard = board.key;
      const selected = [...readProductColumns(board.key)];
      if (!fieldSelectorRoot) {
        fieldSelectorRoot = h('div');
        document.body.append(fieldSelectorRoot);
        fieldSelectorRoot.hidden = true;
      }
      const root = fieldSelectorRoot;
      dialog.replaceChildren(
        // 结构对齐公共约定：modal-form__header / __body / __footer
        // （components.css 的 ui-field-selector-dialog 布局按这三个类划分 grid 行）。
        h('div', { class: 'modal-form__header' },
          h('div', null,
            h('span', { class: 'section-kicker', text: '字段设置' }),
            h('h3', { id: 'prColumnsTitle', text: `${board.label} · 展示字段` }),
            h('p', { text: '勾选要展示的字段，拖动调整列顺序；每张榜单单独保存。' })),
          h('button', {
            type: 'button', class: 'pr-dialog-close', 'aria-label': '关闭', text: '×',
            onclick: () => closeProductFieldDialog(),
          })),
        h('div', { class: 'modal-form__body' },
          h('div', { 'data-pr-product-field-selector': '' }),
          h('p', { class: 'modal-form__status', 'data-pr-columns-status': '' })),
        h('div', { class: 'modal-form__footer' },
          h('button', {
            type: 'button', class: 'ui-button ui-button--ghost ui-button--compact', text: '恢复默认',
            onclick: () => {
              storeProductColumns(board.key, defaultProductColumns(board.key));
              syncFromDialog();
              refreshProductTables();
            },
          }),
          h('button', {
            type: 'button', class: 'ui-button ui-button--primary', text: '应用',
            onclick: () => { syncFromDialog(); closeProductFieldDialog(); },
          })),
      );
      if (!fieldSelector) {
        fieldSelector = window.DemoFieldSelector.create({
          root,
          emptyText: '尚未选择字段',
          searchPlaceholder: '搜索字段名称',
          onChange: () => {
            // 勾选即保存即重渲染（与 keyword-promotion 的即时反馈一致），
            // 「应用」按钮只负责关对话框。
            syncFromDialog();
            const status = dialog.querySelector('[data-pr-columns-status]');
            if (status) status.textContent = `已更新 ${fieldSelector.getSelected().length} 列。`;
          },
        });
      }
      fieldSelector.setConfig({ groups: fieldGroupsFor(board.key), selected });
      const mount = dialog.querySelector('[data-pr-product-field-selector]');
      mount.replaceChildren(root);
      root.hidden = false;
      dialog.setAttribute('aria-labelledby', 'prColumnsTitle');
      if (!dialog.open) dialog.showModal();
      window.lucide?.createIcons();
    }

    /** 把字段选择器当前勾选写回 localStorage 并重渲染表格。 */
    function syncFromDialog() {
      if (!fieldSelector || !fieldBoard) return;
      const keys = fieldSelector.getSelected()
        // 过滤掉该榜不支持的列（field-selector 的 selected 可能混入其他榜的 key）。
        .filter((key) => boardColumns(fieldBoard).some((col) => col.key === key));
      storeProductColumns(fieldBoard, new Set(keys));
      refreshProductTables();
    }

    // 兼容旧入口：主闭包切走货品页签时调用（原浮层收起）。
    function closeProductFieldPopover() {
      closeProductFieldDialog();
    }

    function productTableToolbar(boardKey) {
      const board = boardOf(boardKey);
      const button = h('button', {
        type: 'button',
        class: 'ui-button ui-button--ghost ui-button--compact',
        'aria-haspopup': 'dialog',
        text: '字段设置',
        onclick: (event) => {
          event.stopPropagation();
          openProductFieldDialog(board.key);
        },
      });
      return h('div', { class: 'pr-table-toolbar' },
        h('div', { class: 'pr-table-toolbar__meta' },
          h('span', { text: board.label }),
          h('small', { text: '列可勾选与排序；标题过长会截断，悬停可看全文。' })),
        button);
    }

    // 每张榜一个面板（含该榜专属的字段设置工具栏），供主闭包统一渲染。
    function productBoardPanel(title, hint, rows, boardKey, emptyText) {
      const table = renderProductTable(rows, boardKey);
      return h('article', { class: 'ui-panel pr-analysis-panel' },
        h('div', { class: 'panel__header' },
          h('div', null, h('h3', { class: 'panel__title', text: title }), h('p', { class: 'panel__hint', text: hint })),
          productTableToolbar(boardKey)),
        h('div', { class: 'ui-panel__body' },
          table || h('p', { class: 'pr-material__empty', text: emptyText || '暂无数据。' })),
      );
    }

    return {
      rememberContext,
      renderProductTable,
      productTableToolbar,
      productBoardPanel,
      closeProductFieldPopover,
    };
  }

  global.createProductColumns = createProductColumns;
})(window);
