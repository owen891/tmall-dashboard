(function (global) {
  'use strict';

  /** 商品页「批量操作 / 复制选中」模块。
   *
   *  从 products-live.js 的单闭包中切出（闭包状态显式化第四步）：
   *  本模块拥有批量改字段、批量打标、批量收藏、复制商品 ID 的全部行为，
   *  以及批量字段选项填充；selected/rows/batchMutation 仍存放在页面共享 state 上，
   *  对主闭包的依赖全部通过 deps 显式注入。
   *
   *  deps 契约（由 products-live.js 提供）：
   *  - state                 页面共享状态（selected/rows/copyingIds/batchMutation）
   *  - $                     查询助手
   *  - toast/setStatus       提示与状态文案
   *  - jsonOptions           API 请求选项
   *  - productId             行级取值助手
   *  - classificationValues  分类候选值（批量字段 datalist）
   *  - rememberClassification  新值回写字典
   *  - load                  批量改字段后重载列表
   *  - renderTable           批量收藏后重渲染表格（可缺省）
   *  - updateSelection       批量打标/复制后刷新选择计数（可缺省）
   */

  function createBatchOps(deps) {
    const {
      state, $, toast, setStatus, jsonOptions, productId,
      classificationValues, rememberClassification, load, renderTable, updateSelection,
    } = deps;

    function copyWithFallback(text) {
      const textarea = document.createElement('textarea');
      textarea.value = text;
      textarea.setAttribute('readonly', '');
      textarea.style.position = 'fixed';
      textarea.style.opacity = '0';
      document.body.appendChild(textarea);
      textarea.select();
      const copied = document.execCommand('copy');
      textarea.remove();
      if (!copied) throw new Error('当前浏览器不支持复制');
    }

    async function copySelectedProductIds(button) {
      if (state.copyingIds) return;
      const ids = [...state.selected].map((id) => String(id || '').trim()).filter(Boolean);
      if (!ids.length) {
        toast('请选择商品');
        return;
      }
      state.copyingIds = true;
      button.disabled = true;
      button.setAttribute('aria-busy', 'true');
      const text = ids.join('\n');
      try {
        if (navigator.clipboard?.writeText) {
          try {
            await navigator.clipboard.writeText(text);
          } catch (_) {
            copyWithFallback(text);
          }
        } else {
          copyWithFallback(text);
        }
        setStatus(`已复制 ${ids.length} 个商品 ID`);
        toast(`已复制 ${ids.length} 个商品 ID`);
      } catch (error) {
        setStatus(error.message || '复制商品 ID 失败，请重试');
        toast(error.message || '复制商品 ID 失败，请重试');
      } finally {
        state.copyingIds = false;
        button.removeAttribute('aria-busy');
        updateSelection?.();
      }
    }

    async function applyBatchField() {
      if (state.batchMutation) return;
      state.batchMutation = true;
      const ids = [...state.selected];
      const fieldName = $('[data-products-batch-field]').value;
      const value = $('[data-products-batch-value]').value.trim();
      if (!ids.length || !value) {
        toast('请选择商品并输入批量值');
        state.batchMutation = false;
        return;
      }
      try {
        await DemoApi.domainRequest('/api/products/batch-update', jsonOptions({ product_ids: ids, field: fieldName, value, operator: '商品运营', reason: `批量修改${fieldName}` }));
        await rememberClassification(fieldName === 'tier' ? 'tiers' : 'styles', value);
        toast(`已更新 ${ids.length} 件商品`);
        state.selected.clear();
        $('[data-products-batch-value]').value = '';
        await load();
      } finally { state.batchMutation = false; }
    }

    async function applyBatchTag() {
      if (state.batchMutation) return;
      state.batchMutation = true;
      const ids = [...state.selected];
      const tag = $('[data-products-batch-tag]').value.trim();
      if (!ids.length || !tag) {
        toast('请选择商品并输入标签');
        state.batchMutation = false;
        return;
      }
      try {
        await DemoApi.domainRequest('/api/products/batch-tags', jsonOptions({ product_ids: ids, tag, operator: '商品运营', reason: '批量添加商品标签' }));
        toast(`已为 ${ids.length} 件商品新增标签`);
        $('[data-products-batch-tag]').value = '';
        state.selected.clear();
        updateSelection?.();
      } finally { state.batchMutation = false; }
    }

    async function batchStar() {
      if (state.batchMutation) return;
      state.batchMutation = true;
      const ids = [...state.selected];
      if (!ids.length) {
        toast('请选择商品');
        state.batchMutation = false;
        return;
      }
      const targets = ids.filter((id) => {
        const row = state.rows.find((item) => productId(item) === id);
        return row && Number(row.starred || 0) !== 1;
      });
      if (!targets.length) {
        state.selected.clear();
        renderTable?.();
        toast('选中商品已全部收藏，已跳过');
        state.batchMutation = false;
        return;
      }
      try {
        const results = await Promise.allSettled(targets.map((id) => DemoApi.domainRequest(`/api/products/${encodeURIComponent(id)}/star`, jsonOptions({ product_id: id, starred: 1, operator: '商品运营', reason: '批量收藏商品' }))));
        const ok = results.filter((item) => item.status === 'fulfilled').length;
        const fail = results.length - ok;
        results.forEach((result, index) => {
          if (result.status !== 'fulfilled') return;
          const row = state.rows.find((item) => productId(item) === targets[index]);
          if (row) row.starred = Number(result.value?.data?.starred || 0);
        });
        state.selected.clear();
        renderTable?.();
        toast(`批量收藏完成：成功 ${ok}，失败 ${fail}，跳过 ${ids.length - targets.length}`);
      } finally { state.batchMutation = false; }
    }

    function fillBatchOptions() {
      const fieldName = $('[data-products-batch-field]').value;
      $('[data-products-batch-value]').setAttribute('list', `products-${fieldName}-options`);
      const list = $('[data-products-batch-options]'); list.id = `products-${fieldName}-options`;
      list.replaceChildren(...classificationValues(fieldName).map((value) => new Option('', value)));
    }

    return Object.freeze({
      copySelectedProductIds,
      applyBatchField,
      applyBatchTag,
      batchStar,
      fillBatchOptions,
    });
  }

  global.TmallProducts = global.TmallProducts || {};
  global.TmallProducts.createBatchOps = createBatchOps;
})(window);
