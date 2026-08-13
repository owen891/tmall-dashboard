(function () {
  const form = document.querySelector('[data-settings-form]');
  const status = document.querySelector('[data-settings-status]');
  if (!form.elements.mapping_templates || !form.elements.view_templates) {
    const make = (name, label) => { const field = document.createElement('label'); field.textContent = label; const input = document.createElement('textarea'); input.className = 'input'; input.name = name; input.rows = 3; input.value = '{}'; field.appendChild(input); return field; };
    form.insertBefore(make('mapping_templates', '导入映射模板（JSON）'), form.querySelector('[type="submit"]'));
    form.insertBefore(make('view_templates', '商品视图模板（JSON）'), form.querySelector('[type="submit"]'));
  }
  const set = (data) => Object.entries(data).forEach(([key, value]) => { if (form.elements[key] && value !== null) form.elements[key].value = typeof value === 'object' ? JSON.stringify(value, null, 2) : value; });
  const load = async () => { try { set((await DemoApi.domainRequest('/api/settings')).data); } catch (error) { status.textContent = error.message; } };
  form.addEventListener('submit', async (event) => {
    event.preventDefault(); const data = new FormData(form);
    try {
      const json = (key) => JSON.parse(data.get(key) || '{}');
      const response = await DemoApi.domainRequest('/api/settings', {method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({shop_name: data.get('shop_name'), timezone: data.get('timezone'), currency: data.get('currency'), week_starts_on: data.get('week_starts_on'), annual_target_default: Number(data.get('annual_target_default') || 0), lifecycle_thresholds: json('lifecycle_thresholds'), field_mappings: json('field_mappings'), mapping_templates: json('mapping_templates'), view_templates: json('view_templates'), product_view_template: data.get('product_view_template')})});
      set(response.data); status.textContent = '设置已保存';
    } catch (error) { status.textContent = error.message || 'JSON 格式不正确'; }
  });
  load();
})();
