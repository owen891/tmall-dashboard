(function (global) {
  'use strict';

  /** 商品页「列设置 / 视图模板」模块。
   *
   *  从 products-live.js 的单闭包中切出（闭包状态显式化第一步）：
   *  本模块拥有 templates / templateLabels / builtinTemplateKeys 与列设置
   *  弹层的全部状态与行为；对主闭包的依赖全部通过 deps 显式注入。
   *
   *  deps 契约（由 products-live.js 提供）：
   *  - state                页面共享状态（view/visibleColumns/settings/serverDefaultView）
   *  - columns              列定义数组（rebuildColumns 后填充）
   *  - columnsByKey         列定义索引 Map
   *  - columnGroups         字段分组（field-selector 渲染用）
   *  - storageKeys          { view, columns, preference } 三个 localStorage 键
   *  - $                    查询助手
   *  - number               数值格式化
   *  - toast                提示
   *  - jsonOptions          API 请求选项
   *  - renderTable          应用列后重渲染主表
   *  - columnsDialog        列设置 <dialog> 元素
   */

  function createColumnSettings(deps) {
    const {
      state, columns, columnsByKey, columnGroups, storageKeys,
      $, number, toast, jsonOptions, renderTable, columnsDialog,
    } = deps;

    // 视窗体系（对齐 BI）：默认视窗轨 = 下列模板；个人视窗 = 单槽快存（settings.product_personal_view）。
    // 上限只拦新增勾选，不截断存量偏好，避免老用户打开页面列数被静默砍掉。
    const PERSONAL_VIEW_KEY = 'personal';
    const VIEW_COLUMN_LIMIT = 25;

    let columnsReturnFocus = null;
    let columnSelector = null;
    let templateManager = null;

    // 【已作废 2026-10-22】下列模板原先引用的无源列（style/product_type/product_time_node/
    // paid_ipv/organic_ipv/recommend_ipv/click_rate/paid_ratio/keyword_*/crowd_*/site_*/
    // lifecycle_stage/seasonality/has_pending_action/product_growth_stage）已从
    // products-live.js 的 columnGroups 移除，模板同步改为只含仍有真实数据的列。
    const templates = {
      operate: ['tier', 'payment_amount', 'net_sales', 'conversion', 'refund_rate', 'ad_spend', 'roi', 'search_ipv', 'repurchase_rate'],
      select: ['tier', 'visitors', 'conversion', 'cart_rate', 'fav_rate', 'payment_amount', 'buyers', 'avg_order_value', 'score'],
      paid: ['ad_spend', 'expense_ratio', 'roi', 'impressions', 'clicks', 'ctr', 'cpc', 'cpm', 'click_conversion'],
      refund: ['tier', 'payment_amount', 'net_sales', 'refund_amount', 'refund_rate', 'buyers', 'avg_order_value', 'new_buyers', 'new_buyer_ratio', 'repurchase_users', 'repurchase_rate', 'score'],
      lifecycle: ['tier', 'payment_amount', 'trend_change', 'search_click_rate', 'category_width', 'repurchase_rate'],
      traffic: ['tier', 'visitors', 'page_views', 'uv_value', 'conversion', 'cart_rate', 'fav_rate', 'bounce_rate', 'avg_stay_duration', 'search_visitors', 'search_ratio', 'search_conversion'],
      transaction: ['tier', 'payment_amount', 'payment_count', 'buyers', 'avg_order_value', 'net_sales', 'refund_amount', 'refund_rate', 'trend_change', 'cart_qty', 'score'],
      promotion: ['ad_spend', 'expense_ratio', 'roi', 'impressions', 'clicks', 'ctr', 'cpc', 'cpm', 'direct_gmv', 'total_gmv', 'cart_adds', 'cart_cost'],
    };
    const templateLabels = {
      operate: '\u7ecf\u8425\u603b\u89c8',
      select: '\u9009\u6b3e\u5206\u6790',
      paid: '\u6295\u653e\u6548\u7387',
      refund: '\u9000\u6b3e\u590d\u8d2d',
      lifecycle: '\u751f\u547d\u5468\u671f',
      traffic: '\u6d41\u91cf\u8f6c\u5316',
      transaction: '\u4ea4\u6613\u4e0e\u9000\u6b3e',
      promotion: '\u63a8\u5e7f\u4e0e\u8d39\u7528',
    };
    const builtinTemplateKeys = new Set(Object.keys(templates));

    const productTemplateRecords = () => Object.fromEntries(Object.entries(templates).map(([key, columnsList]) => [key, {
      label: templateLabels[key] || key,
      columns: [...columnsList],
    }]));

    function selectedDialogColumns() {
      return columnSelector?.getSelected() || [];
    }

    function personalView() {
      const view = state.settings?.product_personal_view;
      if (view && Array.isArray(view.columns)) {
        const valid = view.columns.filter((column) => columnsByKey.has(column));
        if (valid.length) return { ...view, columns: valid };
      }
      return null;
    }

    function formatSavedAt(savedAt) {
      const date = new Date(savedAt || '');
      if (Number.isNaN(date.getTime())) return '个人视窗';
      return `个人视窗（${date.getMonth() + 1}月${date.getDate()}日保存）`;
    }

    function updateViewControls() {
      const personal = personalView();
      const personalButton = document.querySelector('[data-products-view="personal"]');
      if (personalButton) {
        personalButton.hidden = !personal;
        personalButton.title = personal ? formatSavedAt(personal.saved_at) : '个人视窗';
      }
      document.querySelectorAll('[data-products-view]').forEach((button) => {
        button.setAttribute('aria-pressed', String(button.dataset.productsView === state.view));
      });
      const limit = $('[data-products-visible-limit]');
      if (limit) limit.textContent = String(VIEW_COLUMN_LIMIT);
      const clearButton = $('[data-products-personal-clear]');
      if (clearButton) clearButton.hidden = !personal;
    }

    function syncViewUrl() {
      try {
        const url = new URL(window.location.href);
        if (state.view === 'custom') url.searchParams.delete('view');
        else url.searchParams.set('view', state.view);
        history.replaceState(null, '', url);
      } catch {}
    }

    function switchView(key) {
      if (key === PERSONAL_VIEW_KEY) {
        const personal = personalView();
        if (!personal) return;
        applyColumns(personal.columns, PERSONAL_VIEW_KEY);
        return;
      }
      const resolved = templates[key] ? key : 'operate';
      try { localStorage.setItem(storageKeys.view, resolved); } catch {}
      applyColumns(templates[resolved] || templates.operate, resolved);
    }

    function updateColumnsDialogStatus() {
      const selected = selectedDialogColumns();
      $('[data-products-visible-count]').textContent = number(selected.length);
      const limit = $('[data-products-visible-limit]');
      if (limit && limit.textContent !== String(VIEW_COLUMN_LIMIT)) limit.textContent = String(VIEW_COLUMN_LIMIT);
      $('[data-products-columns-status]').textContent = selected.length ? '' : '至少保留一个可见字段';
      $('[data-products-columns-apply]').disabled = selected.length === 0;
      $('[data-products-template-save]').disabled = selected.length === 0;
      $('[data-products-personal-save]').disabled = selected.length === 0;
    }

    function renderTemplateSelect(selectedKey = state.view) {
      const select = $('[data-products-template-select]');
      select.replaceChildren(...Object.keys(templates).map((key) => {
        const option = document.createElement('option');
        option.value = key;
        option.textContent = templateLabels[key] || key;
        return option;
      }));
      if ([...select.options].some((option) => option.value === selectedKey)) select.value = selectedKey;
    }

    function renderColumnOptions(selected = state.visibleColumns) {
      // hidden 列不进入字段选择器（它们只保留定义用于口径追溯）。
      // 过滤后若整组为空，则整组不渲染，避免出现空标题分组。
      const groups = columnGroups
        .map((group) => ({ label: group.label, fields: (group.columns || []).filter((field) => field && !field.hidden) }))
        .filter((group) => group.fields.length > 0);
      const config = {
        groups,
        selected,
      };
      if (!columnSelector) {
        columnSelector = TmallUI.fieldSelector({
          root: $('[data-products-field-selector]'),
          ...config,
          maxSelected: VIEW_COLUMN_LIMIT,
          availableTitleId: 'productsAvailableFieldsTitle',
          previewTitleId: 'productsFieldPreviewTitle',
          optionDataAttribute: 'data-products-column-key',
          previewDataAttribute: 'data-products-preview-key',
          onChange: updateColumnsDialogStatus,
          onCapacity: (limit) => {
            $('[data-products-columns-status]').textContent = `最多选择 ${limit} 个字段，请先取消部分字段`;
          },
        });
      } else {
        columnSelector.setConfig(config);
      }
      if (!templateManager && window.DemoFieldTemplateManager) {
        templateManager = DemoFieldTemplateManager.create({
          root: $('[data-products-template-manager]'),
          builtinKeys: [...builtinTemplateKeys],
          templates: productTemplateRecords(),
          onChange: (event) => {
            if (event.type === 'use') {
              const selectedTemplate = templates[event.key];
              if (selectedTemplate) renderColumnOptions(selectedTemplate);
              renderTemplateSelect(event.key);
            }
          },
          onSave: (key, label) => updateProductTemplate(key, label),
          onDelete: (key) => deleteProductTemplate(key),
        });
      }
      templateManager?.setTemplates(productTemplateRecords());
      renderTemplateSelect();
      updateColumnsDialogStatus();
      window.lucide?.createIcons();
    }

    function openColumnsDialog(event) {
      columnsReturnFocus = event.currentTarget;
      renderColumnOptions();
      columnsDialog.hidden = false;
      columnsDialog.showModal();
      window.setTimeout(() => columnsDialog.querySelector('input')?.focus(), 0);
    }

    function closeColumnsDialog() {
      if (columnsDialog.open) columnsDialog.close();
      columnsDialog.hidden = true;
      columnsReturnFocus?.focus?.();
      columnsReturnFocus = null;
    }

    function saveColumns() {
      try {
        localStorage.setItem(storageKeys.view, state.view);
        localStorage.setItem(storageKeys.columns, JSON.stringify(state.visibleColumns));
        localStorage.setItem(storageKeys.preference, JSON.stringify({
          view: state.view,
          columns: state.visibleColumns,
          serverDefaultView: state.serverDefaultView,
        }));
      } catch {}
    }

    function applyColumns(selected, view = 'custom') {
      const valid = selected.filter((key) => columnsByKey.has(key));
      if (!valid.length) return;
      state.visibleColumns = valid;
      state.view = view;
      saveColumns();
      syncViewUrl();
      updateViewControls();
      renderTable();
    }

    function ingestViewTemplates(settings) {
      state.settings = settings;
      Object.keys(templates).forEach((key) => {
        if (!builtinTemplateKeys.has(key)) delete templates[key];
      });
      Object.keys(templateLabels).forEach((key) => {
        if (!builtinTemplateKeys.has(key)) delete templateLabels[key];
      });
      Object.entries(settings?.view_templates || {}).forEach(([key, value]) => {
        const columnsList = Array.isArray(value) ? value : value?.columns;
        if (!Array.isArray(columnsList)) return;
        const valid = columnsList.filter((column) => columnsByKey.has(column));
        if (!valid.length) return;
        templates[key] = valid;
        templateLabels[key] = Array.isArray(value) ? key : (value.label || key);
      });
      templateManager?.setTemplates(productTemplateRecords());
      updateViewControls();
    }

    async function updateProductTemplate(key, label) {
      const selected = selectedDialogColumns();
      if (!selected.length || !templates[key]) return;
      const viewTemplates = { ...(state.settings?.view_templates || {}), ...productTemplateRecords() };
      viewTemplates[key] = { label, columns: selected };
      try {
        const response = await DemoApi.domainRequest('/api/settings', jsonOptions({ view_templates: viewTemplates }, 'PUT'));
        ingestViewTemplates(response.data);
        applyColumns(selected, key);
        renderColumnOptions(selected);
        $('[data-products-columns-status]').textContent = `模板“${label}”已更新`;
      } catch (error) {
        $('[data-products-columns-status]').textContent = error.message || '模板更新失败';
      }
    }

    async function deleteProductTemplate(key) {
      if (builtinTemplateKeys.has(key)) return;
      const viewTemplates = { ...(state.settings?.view_templates || {}) };
      delete viewTemplates[key];
      const payload = { view_templates: viewTemplates };
      if (state.settings?.product_view_template === key) payload.product_view_template = 'operate';
      try {
        const response = await DemoApi.domainRequest('/api/settings', jsonOptions(payload, 'PUT'));
        ingestViewTemplates(response.data);
        const fallback = templates.operate;
        if (state.view === key) applyColumns(fallback, 'operate');
        renderColumnOptions(state.view === 'operate' ? fallback : state.visibleColumns);
        $('[data-products-columns-status]').textContent = '模板已删除';
      } catch (error) {
        $('[data-products-columns-status]').textContent = error.message || '模板删除失败';
      }
    }

    async function saveCustomTemplate() {
      const input = $('[data-products-template-name]');
      const name = input.value.trim();
      const selected = selectedDialogColumns();
      if (!name) {
        $('[data-products-columns-status]').textContent = '请输入模板名称';
        input.focus();
        return;
      }
      if (!selected.length) return;
      const key = `custom_${Date.now()}`;
      const viewTemplates = { ...(state.settings?.view_templates || {}) };
      viewTemplates[key] = { label: name, columns: selected };
      const button = $('[data-products-template-save]');
      button.disabled = true;
      $('[data-products-columns-status]').textContent = '正在保存模板';
      try {
        const response = await DemoApi.domainRequest('/api/settings', jsonOptions({ view_templates: viewTemplates }, 'PUT'));
        ingestViewTemplates(response.data);
        input.value = '';
        applyColumns(selected, key);
        renderTemplateSelect(key);
        $('[data-products-columns-status]').textContent = `模板“${name}”已保存`;
        toast(`已保存模板“${name}”`);
      } catch (error) {
        $('[data-products-columns-status]').textContent = error.message || '模板保存失败';
      } finally {
        button.disabled = false;
      }
    }

    async function savePersonalView() {
      const selected = selectedDialogColumns();
      if (!selected.length) return;
      const button = $('[data-products-personal-save]');
      button.disabled = true;
      $('[data-products-columns-status]').textContent = '正在保存个人视窗';
      try {
        const response = await DemoApi.domainRequest('/api/settings', jsonOptions({
          product_personal_view: { label: '个人视窗', columns: selected, saved_at: new Date().toISOString() },
        }, 'PUT'));
        ingestViewTemplates(response.data);
        applyColumns(selected, PERSONAL_VIEW_KEY);
        $('[data-products-columns-status]').textContent = '已保存为个人视窗，下次进入商品页默认使用';
        toast('已保存个人视窗');
      } catch (error) {
        $('[data-products-columns-status]').textContent = error.message || '个人视窗保存失败';
      } finally {
        button.disabled = false;
      }
    }

    async function clearPersonalView() {
      try {
        const response = await DemoApi.domainRequest('/api/settings', jsonOptions({ product_personal_view: null }, 'PUT'));
        ingestViewTemplates(response.data);
        if (state.view === PERSONAL_VIEW_KEY) {
          const fallbackKey = state.serverDefaultView && templates[state.serverDefaultView] ? state.serverDefaultView : 'operate';
          try { localStorage.setItem(storageKeys.view, fallbackKey); } catch {}
          applyColumns(templates[fallbackKey] || templates.operate, fallbackKey);
        } else {
          updateViewControls();
        }
        $('[data-products-columns-status]').textContent = '已恢复默认视窗';
        toast('已恢复默认视窗');
      } catch (error) {
        $('[data-products-columns-status]').textContent = error.message || '恢复默认视窗失败';
      }
    }

    function bindColumnSettings() {
      $('[data-products-columns-open]').addEventListener('click', openColumnsDialog);
      document.querySelectorAll('[data-products-columns-close]').forEach((button) => button.addEventListener('click', closeColumnsDialog));
      $('[data-products-columns-reset]').addEventListener('click', () => renderColumnOptions(templates.operate));
      // 全选走组件 selectAll：受上限约束（必选在前、按分组顺序补满）。
      $('[data-products-columns-select-all]').addEventListener('click', () => columnSelector?.selectAll({ notify: true }));
      $('[data-products-columns-clear-all]').addEventListener('click', () => renderColumnOptions([]));
      $('[data-products-personal-save]').addEventListener('click', () => savePersonalView());
      $('[data-products-personal-clear]').addEventListener('click', () => clearPersonalView());
      $('[data-products-template-apply]').addEventListener('click', () => {
        const key = $('[data-products-template-select]').value;
        renderColumnOptions(templates[key] || templates.operate);
        renderTemplateSelect(key);
      });
      $('[data-products-template-save]').addEventListener('click', () => saveCustomTemplate());
      $('[data-products-columns-apply]').addEventListener('click', () => {
        const selected = selectedDialogColumns();
        if (!selected.length) return;
        applyColumns(selected);
        closeColumnsDialog();
        toast(`已应用 ${selected.length} 个字段`);
      });
      columnsDialog.addEventListener('cancel', (event) => { event.preventDefault(); closeColumnsDialog(); });
      columnsDialog.addEventListener('close', () => {
        columnsDialog.hidden = true;
        columnsReturnFocus?.focus?.();
        columnsReturnFocus = null;
      });
    }

    return Object.freeze({
      templates,
      templateLabels,
      builtinTemplateKeys,
      bindColumnSettings,
      renderColumnOptions,
      renderTemplateSelect,
      applyColumns,
      saveColumns,
      ingestViewTemplates,
      openColumnsDialog,
      closeColumnsDialog,
      personalView,
      switchView,
      updateViewControls,
    });
  }

  global.TmallProducts = global.TmallProducts || {};
  global.TmallProducts.createColumnSettings = createColumnSettings;
})(window);
