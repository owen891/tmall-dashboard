(function () {
  function create(options = {}) {
    const root = typeof options.root === 'string' ? document.querySelector(options.root) : options.root;
    const builtins = new Set(options.builtinKeys || []);
    let templates = { ...(options.templates || {}) };

    const emit = (event) => options.onChange?.(event, templates);

    function render() {
      if (!root) return;
      root.replaceChildren();
      const entries = Object.entries(templates);
      if (!entries.length) {
        const empty = document.createElement('span');
        empty.className = 'panel__hint';
        empty.textContent = '暂无字段模板';
        root.appendChild(empty);
        return;
      }
      entries.forEach(([key, template]) => {
        const row = document.createElement('span');
        row.className = 'template-pill field-template-manager__item';
        row.dataset.fieldTemplateKey = key;
        const use = document.createElement('button');
        use.type = 'button';
        use.className = 'field-template-manager__use';
        use.dataset.fieldTemplateUse = key;
        use.textContent = template.label || key;
        use.title = `使用模板 ${template.label || key}`;
        row.appendChild(use);

        const edit = document.createElement('button');
        edit.type = 'button';
        edit.className = 'field-template-manager__edit';
        edit.dataset.fieldTemplateEdit = key;
        edit.setAttribute('aria-label', `编辑模板 ${template.label || key}`);
        edit.title = `编辑模板 ${template.label || key}`;
        edit.textContent = '编辑';
        row.appendChild(edit);

        if (!builtins.has(key)) {
          const remove = document.createElement('button');
          remove.type = 'button';
          remove.className = 'field-template-manager__delete';
          remove.dataset.fieldTemplateDelete = key;
          remove.setAttribute('aria-label', `删除模板 ${template.label || key}`);
          remove.title = `删除模板 ${template.label || key}`;
          remove.textContent = '删除';
          row.appendChild(remove);
        }
        root.appendChild(row);
      });
      window.lucide?.createIcons();
    }

    function startEdit(key) {
      const row = root?.querySelector(`[data-field-template-key="${CSS.escape(key)}"]`);
      const template = templates[key];
      if (!row || !template) return;
      row.replaceChildren();
      const input = document.createElement('input');
      input.className = 'input field-template-manager__input';
      input.value = template.label || key;
      input.setAttribute('aria-label', `模板名称 ${template.label || key}`);
      const save = document.createElement('button');
      save.type = 'button';
      save.className = 'button button--ghost';
      save.dataset.fieldTemplateSave = key;
      save.textContent = '保存';
      const cancel = document.createElement('button');
      cancel.type = 'button';
      cancel.className = 'button button--ghost';
      cancel.dataset.fieldTemplateCancel = key;
      cancel.textContent = '取消';
      row.append(input, save, cancel);
      input.focus();
      input.select();
    }

    root?.addEventListener('click', async (event) => {
      const use = event.target.closest('[data-field-template-use]');
      if (use) emit({ type: 'use', key: use.dataset.fieldTemplateUse });
      const edit = event.target.closest('[data-field-template-edit]');
      if (edit) startEdit(edit.dataset.fieldTemplateEdit);
      const cancel = event.target.closest('[data-field-template-cancel]');
      if (cancel) render();
      const save = event.target.closest('[data-field-template-save]');
      if (save) {
        const input = save.parentElement.querySelector('input');
        const label = input?.value.trim();
        if (!label) return;
        await options.onSave?.(save.dataset.fieldTemplateSave, label, templates[save.dataset.fieldTemplateSave]);
      }
      const remove = event.target.closest('[data-field-template-delete]');
      if (remove) {
        const template = templates[remove.dataset.fieldTemplateDelete];
        if (!template || !window.confirm(`删除字段模板“${template.label || remove.dataset.fieldTemplateDelete}”？`)) return;
        await options.onDelete?.(remove.dataset.fieldTemplateDelete, template);
      }
    });

    return {
      setTemplates(next) { templates = { ...(next || {}) }; render(); },
      setBuiltinKeys(next) { builtins.clear(); (next || []).forEach((key) => builtins.add(key)); render(); },
      getTemplates() { return { ...templates }; },
      render,
    };
  }

  window.DemoFieldTemplateManager = { create };
})();
