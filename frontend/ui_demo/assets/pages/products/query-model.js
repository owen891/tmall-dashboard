(function (global) {
  'use strict';

  function createProductsQuery(config = {}) {
    const filterKeys = [...(config.filterKeys || [])];

    function readRanges(url) {
      // 表头四合一筛选的 min_/max_ 参数：字段名白名单在服务端，这里只做形状透传
      const ranges = {};
      url.searchParams.forEach((value, key) => {
        const match = key.match(/^(min|max)_([a-z_]+)$/);
        if (!match) return;
        (ranges[match[2]] = ranges[match[2]] || {})[match[1]] = value;
      });
      return ranges;
    }

    function writeRanges(url, ranges = {}) {
      [...url.searchParams.keys()].filter((key) => /^(min|max)_/.test(key)).forEach((key) => url.searchParams.delete(key));
      Object.entries(ranges).forEach(([field, bounds]) => {
        if (!bounds) return;
        if (bounds.min !== undefined && bounds.min !== '') url.searchParams.set(`min_${field}`, String(bounds.min));
        if (bounds.max !== undefined && bounds.max !== '') url.searchParams.set(`max_${field}`, String(bounds.max));
      });
    }

    function readUrl(urlLike = global.location.href) {
      const url = new URL(urlLike, global.location.origin);
      const filters = Object.fromEntries(
        filterKeys.filter((key) => url.searchParams.has(key)).map((key) => [key, url.searchParams.get(key) || ''])
      );
      const page = Number(url.searchParams.get('page'));
      const pageSize = Number(url.searchParams.get('page_size'));
      return {
        filters,
        ranges: readRanges(url),
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

    function syncUrl(urlLike, { filters = {}, ranges = {}, page = 1, pageSize = 20, starredOnly = false, displayMode = '', dimension = '', timelineLimit = 3 } = {}) {
      const url = new URL(urlLike, global.location.origin);
      filterKeys.forEach((key) => {
        const value = filters[key];
        if (value) url.searchParams.set(key, value);
        else url.searchParams.delete(key);
      });
      writeRanges(url, ranges);
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

    function buildApiUrl({ range = {}, ranges = {}, page = 1, pageSize = 20, filters = {}, dimension = '', period = '' } = {}) {
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
      Object.entries(ranges).forEach(([field, bounds]) => {
        if (!bounds) return;
        if (bounds.min !== undefined && bounds.min !== '') params.set(`min_${field}`, String(bounds.min));
        if (bounds.max !== undefined && bounds.max !== '') params.set(`max_${field}`, String(bounds.max));
      });
      return `/api/products?${params.toString()}`;
    }

    return Object.freeze({ readUrl, syncUrl, buildApiUrl });
  }

  global.TmallRuntime = global.TmallRuntime || {};
  global.TmallRuntime.createProductsQuery = createProductsQuery;
})(window);
