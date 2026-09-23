(function (global) {
  'use strict';

  function createProductsQuery(config = {}) {
    const filterKeys = [...(config.filterKeys || [])];

    function readUrl(urlLike = global.location.href) {
      const url = new URL(urlLike, global.location.origin);
      const filters = Object.fromEntries(
        filterKeys.filter((key) => url.searchParams.has(key)).map((key) => [key, url.searchParams.get(key) || ''])
      );
      const page = Number(url.searchParams.get('page'));
      const pageSize = Number(url.searchParams.get('page_size'));
      return {
        filters,
        page: Number.isInteger(page) && page > 0 ? page : null,
        pageSize: [20, 50, 100, 200].includes(pageSize) ? pageSize : null,
        starredOnly: url.searchParams.get('starred') === '1',
        displayMode: ['list', 'timeline'].includes(url.searchParams.get('product_view'))
          ? url.searchParams.get('product_view')
          : null,
        dimension: ['daily', 'weekly', 'monthly'].includes(url.searchParams.get('product_dim'))
          ? url.searchParams.get('product_dim')
          : null,
        timelineLimit: [3, 6, 12].includes(Number(url.searchParams.get('timeline_limit')))
          ? Number(url.searchParams.get('timeline_limit'))
          : null,
      };
    }

    function syncUrl(urlLike, { filters = {}, page = 1, pageSize = 20, starredOnly = false, displayMode = '', dimension = '', timelineLimit = 3 } = {}) {
      const url = new URL(urlLike, global.location.origin);
      filterKeys.forEach((key) => {
        const value = filters[key];
        if (value) url.searchParams.set(key, value);
        else url.searchParams.delete(key);
      });
      url.searchParams.set('page', String(page));
      url.searchParams.set('page_size', String(pageSize));
      if (starredOnly) url.searchParams.set('starred', '1');
      else url.searchParams.delete('starred');
      if (['list', 'timeline'].includes(displayMode)) url.searchParams.set('product_view', displayMode);
      else url.searchParams.delete('product_view');
      if (['daily', 'weekly', 'monthly'].includes(dimension)) url.searchParams.set('product_dim', dimension);
      else url.searchParams.delete('product_dim');
      if ([3, 6, 12].includes(Number(timelineLimit))) url.searchParams.set('timeline_limit', String(timelineLimit));
      else url.searchParams.delete('timeline_limit');
      return url;
    }

    function buildApiUrl({ range = {}, page = 1, pageSize = 20, filters = {}, dimension = '', period = '' } = {}) {
      const singleDay = Boolean(range.startDate && range.endDate && range.startDate === range.endDate);
      const selectedDimension = ['daily', 'weekly', 'monthly'].includes(dimension)
        ? dimension
        : (singleDay ? 'daily' : 'monthly');
      const params = new URLSearchParams({
        dim: selectedDimension,
        limit: String(pageSize),
        offset: String(Math.max(0, page - 1) * pageSize),
      });
      if (selectedDimension === 'daily') {
        if (range.startDate) params.set('start', range.startDate);
        if (range.endDate) params.set('end', range.endDate);
      } else {
        const raw = period || range.endDate || range.startDate || new Date().toISOString().slice(0, 10);
        params.set('period', selectedDimension === 'monthly' ? String(raw).slice(0, 7) : String(raw));
      }
      filterKeys.forEach((key) => {
        if (filters[key]) params.set(key, filters[key]);
      });
      return `/api/products?${params.toString()}`;
    }

    return Object.freeze({ readUrl, syncUrl, buildApiUrl });
  }

  global.TmallRuntime = global.TmallRuntime || {};
  global.TmallRuntime.createProductsQuery = createProductsQuery;
})(window);
