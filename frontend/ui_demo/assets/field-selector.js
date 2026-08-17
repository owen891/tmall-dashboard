(function () {
  function create(options) {
    const root = options.root;
    let groups = [];
    let fieldsByKey = new Map();
    let selected = [];
    let draggedPosition = -1;
    let dragOverPosition = -1;

    function normalizeGroups(nextGroups) {
      return (nextGroups || []).map((group) => ({
        label: String(group.label || '字段'),
        fields: (group.fields || group.columns || []).filter((field) => field?.key).map((field) => ({
          key: String(field.key),
          label: String(field.label || field.key),
          required: Boolean(field.required),
          locked: Boolean(field.locked),
        })),
      }));
    }

    function requiredKeys() {
      return [...new Set(groups.flatMap((group) => group.fields)
        .filter((field) => field.required || field.locked)
        .map((field) => field.key))];
    }

    function normalizeSelected(nextSelected) {
      const available = [...new Set((nextSelected || []).map(String).filter((key) => fieldsByKey.has(key)))];
      const required = requiredKeys();
      return [...required, ...available.filter((key) => !required.includes(key))];
    }

    function notify() {
      options.onChange?.([...selected]);
    }

    function makeHeading(id, title, hint) {
      const heading = document.createElement('div');
      heading.className = 'field-selection-pane__heading';
      const strong = document.createElement('strong');
      strong.id = id;
      strong.textContent = title;
      const span = document.createElement('span');
      span.textContent = hint;
      heading.append(strong, span);
      return heading;
    }

    function moveField(position, offset) {
      const target = position + offset;
      const requiredCount = requiredKeys().length;
      if (target < requiredCount || target >= selected.length || position < requiredCount) return;
      [selected[position], selected[target]] = [selected[target], selected[position]];
      renderPreview();
      notify();
      window.lucide?.createIcons();
    }

    function updateDragClasses() {
      const list = root.querySelector('[data-field-selector-preview]');
      if (!list) return;
      list.classList.toggle('is-drag-over-end', dragOverPosition === selected.length && draggedPosition >= 0);
      list.querySelectorAll('[data-field-preview-position]').forEach((item) => {
        const position = Number(item.dataset.fieldPreviewPosition);
        item.classList.toggle('is-dragging', position === draggedPosition);
        item.classList.toggle('is-drag-over', position === dragOverPosition && position !== draggedPosition);
        item.setAttribute('aria-grabbed', position === draggedPosition ? 'true' : 'false');
      });
    }

    function previewItemFromEvent(event, list) {
      const pointed = document.elementFromPoint(event.clientX, event.clientY)?.closest?.('[data-field-preview-position]');
      if (pointed && list.contains(pointed)) return pointed;
      const byBounds = [...list.querySelectorAll('[data-field-preview-position]')].find((item) => {
        const bounds = item.getBoundingClientRect();
        return event.clientX >= bounds.left && event.clientX <= bounds.right
          && event.clientY >= bounds.top && event.clientY <= bounds.bottom;
      });
      if (byBounds) return byBounds;
      const direct = event.target?.closest?.('[data-field-preview-position]');
      return direct && list.contains(direct) ? direct : null;
    }

    function dropPositionFromEvent(event, list) {
      const target = previewItemFromEvent(event, list);
      if (target) return getDropPosition(event, Number(target.dataset.fieldPreviewPosition), target);
      const bounds = list.getBoundingClientRect();
      const insideList = event.clientX >= bounds.left && event.clientX <= bounds.right
        && event.clientY >= bounds.top && event.clientY <= bounds.bottom;
      const last = list.querySelector('[data-field-preview-position]:last-of-type');
      if (insideList && last && event.clientY >= last.getBoundingClientRect().bottom) return selected.length;
      return -1;
    }

    function getDropPosition(event, itemPosition, targetItem) {
      const bounds = (targetItem || event.currentTarget).getBoundingClientRect();
      const afterMidpoint = event.clientY > bounds.top + bounds.height / 2;
      return Math.max(0, Math.min(selected.length, itemPosition + (afterMidpoint ? 1 : 0)));
    }

    function finishDrag(insertAt) {
      const from = draggedPosition;
      draggedPosition = -1;
      dragOverPosition = -1;
      if (from < 0 || insertAt < 0) {
        updateDragClasses();
        return;
      }
      const requiredCount = requiredKeys().length;
      if (from < requiredCount) {
        updateDragClasses();
        return;
      }
      const [moved] = selected.splice(from, 1);
      if (insertAt > from) insertAt -= 1;
      selected.splice(Math.max(requiredCount, Math.min(insertAt, selected.length)), 0, moved);
      selected = normalizeSelected(selected);
      renderPreview();
      notify();
      window.lucide?.createIcons();
    }

    function renderPreview() {
      const list = root.querySelector('[data-field-selector-preview]');
      list.replaceChildren();
      if (!selected.length) {
        const empty = document.createElement('li');
        empty.className = 'field-order-preview__empty';
        empty.textContent = options.emptyText || '尚未选择字段';
        list.appendChild(empty);
        return;
      }
      selected.forEach((key, position) => {
        const field = fieldsByKey.get(key);
        if (!field) return;
        const isLocked = field.required || field.locked;
        const item = document.createElement('li');
        item.className = 'field-order-preview__item';
        item.setAttribute(options.previewDataAttribute || 'data-field-preview-key', key);
        item.dataset.fieldPreviewPosition = String(position);
        item.draggable = false;
        item.title = '拖动以调整字段顺序';
        item.setAttribute('aria-grabbed', position === draggedPosition ? 'true' : 'false');

        const index = document.createElement('span');
        index.className = 'field-order-preview__index';
        index.textContent = String(position + 1);
        const label = document.createElement('span');
        label.className = 'field-order-preview__label';
        label.textContent = field.label;
        const actions = document.createElement('span');
        actions.className = 'field-order-preview__actions';

        [['arrow-up', -1, '上移'], ['arrow-down', 1, '下移']].forEach(([icon, offset, name]) => {
          const button = document.createElement('button');
          button.type = 'button';
          button.className = 'button button--ghost field-order-preview__button';
          button.setAttribute('aria-label', `${name}${field.label}`);
          button.title = `${name}${field.label}`;
          button.disabled = position + offset < 0 || position + offset >= selected.length;
          if (isLocked || position + offset < requiredKeys().length) button.disabled = true;
          const iconElement = document.createElement('i');
          iconElement.dataset.lucide = icon;
          button.appendChild(iconElement);
          button.addEventListener('click', () => moveField(position, offset));
          actions.appendChild(button);
        });

        item.append(index, label, actions);
        item.addEventListener('pointerdown', (event) => {
          if (isLocked || event.button !== 0 || event.target.closest('button')) return;
          draggedPosition = position;
          dragOverPosition = position;
          item.setPointerCapture?.(event.pointerId);
          event.preventDefault();
          updateDragClasses();
        });
        item.addEventListener('pointermove', (event) => {
          if (draggedPosition < 0) return;
          event.preventDefault();
          const list = root.querySelector('[data-field-selector-preview]');
          if (list) dragOverPosition = dropPositionFromEvent(event, list);
          updateDragClasses();
        });
        item.addEventListener('pointerup', (event) => {
          if (draggedPosition < 0) return;
          event.preventDefault();
          const list = root.querySelector('[data-field-selector-preview]');
          const insertAt = list ? dropPositionFromEvent(event, list) : dragOverPosition;
          item.releasePointerCapture?.(event.pointerId);
          finishDrag(insertAt);
        });
        item.addEventListener('pointercancel', () => {
          draggedPosition = -1;
          dragOverPosition = -1;
          updateDragClasses();
        });
        list.appendChild(item);
      });
      updateDragClasses();
    }

    function renderOptions() {
      const container = root.querySelector('[data-field-selector-options]');
      container.replaceChildren(...groups.map((group) => {
        const section = document.createElement('section');
        section.className = 'field-group';
        const heading = document.createElement('strong');
        heading.textContent = group.label;
        section.appendChild(heading);
        group.fields.forEach((field) => {
          const label = document.createElement('label');
          const input = document.createElement('input');
          input.type = 'checkbox';
          input.setAttribute(options.optionDataAttribute || 'data-field-option-key', field.key);
          input.checked = selected.includes(field.key);
          input.disabled = field.required || field.locked;
          input.addEventListener('change', () => {
            if (field.required || field.locked) return;
            if (input.checked && !selected.includes(field.key)) selected.push(field.key);
            if (!input.checked) selected = selected.filter((key) => key !== field.key);
            renderPreview();
            notify();
            window.lucide?.createIcons();
          });
          label.append(input, document.createTextNode(field.label));
          section.appendChild(label);
        });
        return section;
      }));
    }

    function renderShell() {
      root.className = `field-selection-layout ${options.className || ''}`.trim();
      const availableTitleId = options.availableTitleId || `fieldSelectorAvailable-${Math.random().toString(36).slice(2)}`;
      const previewTitleId = options.previewTitleId || `fieldSelectorPreview-${Math.random().toString(36).slice(2)}`;

      const available = document.createElement('section');
      available.className = 'field-selection-pane';
      available.setAttribute('aria-labelledby', availableTitleId);
      available.appendChild(makeHeading(availableTitleId, options.availableTitle || '可选字段', options.availableHint || '勾选要展示的字段'));
      const optionsRoot = document.createElement('div');
      optionsRoot.className = 'field-group-grid';
      optionsRoot.dataset.fieldSelectorOptions = '';
      available.appendChild(optionsRoot);

      const preview = document.createElement('section');
      preview.className = 'field-preview-pane';
      preview.setAttribute('aria-labelledby', previewTitleId);
      preview.appendChild(makeHeading(previewTitleId, options.previewTitle || '字段预览', options.previewHint || '按表格列顺序展示'));
      const previewRoot = document.createElement('ol');
      previewRoot.className = 'field-order-preview';
      previewRoot.dataset.fieldSelectorPreview = '';
      preview.appendChild(previewRoot);

      root.replaceChildren(available, preview);
    }

    function setConfig(config) {
      groups = normalizeGroups(config.groups);
      fieldsByKey = new Map(groups.flatMap((group) => group.fields).map((field) => [field.key, field]));
      selected = normalizeSelected(config.selected);
      renderShell();
      renderOptions();
      renderPreview();
      window.lucide?.createIcons();
    }

    function setSelected(nextSelected, settings = {}) {
      selected = normalizeSelected(nextSelected);
      renderOptions();
      renderPreview();
      if (settings.notify) notify();
      window.lucide?.createIcons();
    }

    setConfig({ groups: options.groups, selected: options.selected });

    return {
      clear(settings = { notify: true }) { setSelected([], settings); },
      getSelected() { return [...selected]; },
      selectAll(settings = { notify: true }) { setSelected([...fieldsByKey.keys()], settings); },
      setConfig,
      setSelected,
    };
  }

  window.DemoFieldSelector = { create };
})();
