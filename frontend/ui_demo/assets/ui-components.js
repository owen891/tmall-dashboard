(function () {
  const text = (node, value) => {
    if (node) node.textContent = value == null || value === '' ? '--' : String(value);
    return node;
  };
  const create = (tag, className, value) => {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (value !== undefined) text(node, value);
    return node;
  };
  const clear = (node) => {
    if (node) node.replaceChildren();
    return node;
  };
  const formatDateTime = (value) => {
    if (!value) return '--';
    const normalized = String(value).replace('T', ' ').replace(/\.\d+Z?$/, '');
    return normalized.slice(0, 16);
  };
  const status = (node, state, details = {}) => {
    if (!node || !window.DemoApi?.renderDataState) return;
    window.DemoApi.renderDataState(node, state, details);
  };
  const icon = (name, label) => {
    const node = create('i');
    node.dataset.lucide = name;
    if (label) node.setAttribute('aria-label', label);
    else node.setAttribute('aria-hidden', 'true');
    return node;
  };
  window.TmallUI = Object.freeze({ text, create, clear, formatDateTime, status, icon });
})();
