"""市场监控深化计算（对齐月复盘框架「市场监控-行业」）。

四项能力：
- 关键词 8 大归类 + 词根需求：类目/人群/属性/风格/场景/功能/品牌/价格，
  每类给出搜索量占比 + 覆盖词数 + 核心词根（TOP3）。
- 蓝海机会词：细分词（剔除泛词）高搜索 × 高支付转化。SKILL 完整口径还要求
  「每万供给覆盖」，该字段当前采集链路没有导出——此处用 热度×转化率 近似，
  并在返回里标注 limitation，待搜索词分析导出补齐供给覆盖后替换。
- 趋势节点：近 7 天日均搜索热度 vs 前置窗口（至多 23 天）日均，增速超阈值
  判「起势」/「退势」；历史不足 14 天时窗口自动收缩并如实标注天数。
- 竞店爆品排名变化：生意参谋商品榜（sycm_market_item_rank）窗口首尾对比，
  每店给出 上升/下降/新进榜/退出 榜单与 TOP 变动。
- 商品排行·趋势市场（`trend_items`）：同一套窗口首尾对比，聚合维度换成商品，
  给出全市场上升最快与新进榜商品。

全部只读；数据缺失返回空列表与 missing_inputs，不臆造 0。
"""

from collections import defaultdict
import json
from pathlib import Path


def _load_lexicon():
    """归类词典是运营配置（品牌与类目词表），随私有数据目录 data/ 分发。

    公开 checkout 不携带该文件：词典为空时归类全部退化为「其他」、
    蓝海词根集为空，市场监控仍只读运行、不臆造数据。
    """
    path = Path(__file__).resolve().parents[1] / 'data' / 'market_monitor_lexicon.json'
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return frozenset(), ()
    generic = frozenset(str(item) for item in payload.get('generic_keywords') or [])
    rules = tuple(
        (str(key), str(label), tuple(str(term) for term in terms or []))
        for key, label, terms in payload.get('keyword_rules') or []
    )
    return generic, rules


# 泛词表（泛词参与蓝海判断会让大词被误判为蓝海）。
# 8 大归类规则词典（有序，先命中先归类）。词表随搜索词滚动维护，
# 在页面上人工纠偏后回填 data/market_monitor_lexicon.json（私有运营数据）。
GENERIC_KEYWORDS, KEYWORD_RULES = _load_lexicon()


KEYWORD_CATEGORY_LABELS = {key: label for key, label, _ in KEYWORD_RULES} | {'other': '其他'}

# 蓝海分级展示顺序：已分级的在前，「待核」（在榜样本未命中词根）排最后 ——
# 待核不是结论，不该占榜首。
GRADE_ORDER = {'高潜蓝海': 0, '中等': 1, '供给偏多': 2, '待核': 3}


def _classify_keyword(keyword):
    """按规则词典归类；先品牌后人群……未命中为「其他」。返回 category key。"""
    text = str(keyword or '').strip().lower()
    if not text:
        return 'other'
    for key, _, terms in KEYWORD_RULES:
        for term in terms:
            if term.lower() in text:
                return key
    return 'other'


def classify_keyword(keyword):
    """公开包装：返回 (key, label)。

    月复盘页要用同一套 8 大归类口径标注趋势词，不能各写一份（会漂移）。
    """
    key = _classify_keyword(keyword)
    return key, KEYWORD_CATEGORY_LABELS.get(key, '其他')


def _clean_days(rows):
    """[(stat_date, keyword, search_heat, pay_rate, click_rate)] → 按日期索引。"""
    by_date = defaultdict(dict)
    for stat_date, keyword, heat, pay_rate, click_rate in rows:
        if keyword:
            by_date[str(stat_date)][str(keyword)] = {
                'search_heat': heat, 'pay_rate': pay_rate, 'click_rate': click_rate,
            }
    return by_date


def blue_ocean_words(keyword_rows, item_titles):
    """蓝海完整口径（SKILL 阶段二点五，硬约束）：

    - 词集收敛：只对「类目 / 功能」两类归类的词跑覆盖（SKILL 原义=细分品类/
      功能词，如 款式词/款型词/功能词——先人工挑 20 个细分词再算覆盖）。
      对全量 2500+ 词跑覆盖会让 600 款在榜样本淹没绝大多数词（覆盖=0 全被
      误判「高潜蓝海」），品牌/人群/属性等非供给维度词不进分级榜。
    - 搜索量 = 词精确匹配的近 7 天日均搜索热度（不累加词根下其他词）；
    - 商品覆盖 = 最新采集日在榜商品 title 含该词的商品数（product_id 去重）；
    - 每万覆盖 = 覆盖数 ÷ (日均热度 / 10000)，<5 高潜蓝海、5-10 中等、>10 供给偏多；
    - **覆盖 = 0 单列「待核」**：0 不代表供给稀缺（也可能只是词根与标题用词不一致），
      直接判高潜蓝海会让榜单塌成一档，对运营是误导；
    - 泛词剔除、转化率作辅助维度。
    """
    by_date = _clean_days(keyword_rows)
    dates = sorted(by_date)
    if not dates:
        return {'available': False, 'words': [],
                'missing_inputs': ['sycm_market_search_rank']}
    # 细分词根集：类目词（形态/品类）+ 功能词，均来自 8 大归类词典——
    # 与 SKILL CATEGORY_WORDS 同性质（细分品类/功能词，如 款式词/功能词）。
    # 覆盖匹配按「词根」而非长尾组合词：600 款在榜样本不会原样包含
    # 「品类长尾2026新款爆款」这类长尾词，完整词匹配全得 0 覆盖；
    # 词根才是供给粒度（与 SKILL 原文 str.contains(word) 的短词集一致）。
    # ≥3 字下限过滤过泛功能词（如「加固」单独出现时覆盖无意义）。
    supply_root_terms = set()
    for key, _, terms in KEYWORD_RULES:
        if key in ('category', 'function'):
            for term in terms:
                if 3 <= len(term) <= 6:
                    supply_root_terms.add(term.lower())
    recent_dates = dates[-7:]
    term_daily = defaultdict(list)
    for date in recent_dates:
        for keyword, metrics in by_date[date].items():
            text = str(keyword).strip().lower()
            if text in GENERIC_KEYWORDS or len(text) < 2:
                continue
            if metrics['search_heat'] is not None:
                term_daily[str(keyword)].append(float(metrics['search_heat']))
    words = []
    for keyword, heats in term_daily.items():
        text = str(keyword).strip().lower()
        # 词集收敛：词必须含细分词根；覆盖按词根匹配（长尾组合聚合到词根上）。
        roots = [root for root in supply_root_terms if root in text]
        if not roots:
            continue
        # 取最长的命中词根做匹配单位（「功能词」优先于泛根）。
        root = max(roots, key=len)
        daily_heat = sum(heats) / len(heats)
        if daily_heat < 100:
            continue
        cover = sum(1 for title in item_titles if root in str(title or ''))
        cover_per_10k = (cover / (daily_heat / 10000.0)) if daily_heat else None
        # ⚠️ cover=0 **不等于**「供给稀缺」。在榜样本只有最新日 600 款（5 类目 × top120），
        #    当词根与标题用词不一致时（「脚尖加固」「材质词」标题里基本没人这么写）也是 0。
        #    把 0 直接判「高潜蓝海」会让整张榜单塌成一档 —— 实测 12 词里 8 词覆盖为 0、
        #    全判高潜蓝海，分级等于失效，且对运营是误导（会去追一个根本不存在的蓝海）。
        #    故 cover=0 单列「待核」：给出信号，但不给分级结论。
        if cover == 0:
            grade = '待核'
        elif cover_per_10k is not None and cover_per_10k < 5:
            grade = '高潜蓝海'
        elif cover_per_10k is not None and cover_per_10k <= 10:
            grade = '中等'
        else:
            grade = '供给偏多'
        words.append({
            'keyword': root,
            'keyword_full': keyword,
            'search_heat': round(daily_heat, 1),
            'cover_count': cover,
            'cover_per_10k': (round(cover_per_10k, 2) if cover_per_10k is not None else None),
            'grade': grade,
            'note': ('在榜样本标题未命中该词根，无法判定供给：可能是真蓝海，'
                     '也可能是词根与标题用词不一致，需人工核。' if cover == 0 else None),
        })
    # 同词根聚合：热度/转化率取代表词（日均口径），每万覆盖同根同值。
    aggregated = {}
    for word in words:
        key = word['keyword']
        current = aggregated.get(key)
        if current is None or word['search_heat'] > current['search_heat']:
            aggregated[key] = word
    ranked = sorted(aggregated.values(),
                    key=lambda item: (GRADE_ORDER.get(item['grade'], 9),
                                      item['cover_per_10k'] if item['cover_per_10k'] is not None else 0))
    # 已分级的排前（按供给由少到多），「待核」单独保留可见 ——
    # 若把待核一并截断，遇到「已分级词 ≥12」时它们会整体消失，
    # 而待核恰恰是需要人工看一眼的那批。
    graded = [w for w in ranked if w['grade'] != '待核']
    pending = [w for w in ranked if w['grade'] == '待核']
    words = graded[:12] + pending[:6]
    # 从近似口径映射该词根代表词的支付转化率，供表格补列（词根本身没有转化率）。
    pay_rate_by_keyword = {}
    for date in dates[-7:]:
        for keyword, metrics in by_date[date].items():
            if metrics['pay_rate'] is not None:
                pay_rate_by_keyword[str(keyword)] = metrics['pay_rate']
    for word in words:
        representative = pay_rate_by_keyword.get(word['keyword_full'])
        word['pay_rate'] = (round(float(representative), 6) if representative is not None else None)
    return {
        'available': bool(words),
        'words': words,
        'graded_count': len(graded),
        'pending_count': len(pending),
        'word_scope': '细分品类词/功能词根（8大归类中的类目+功能，词根级匹配）',
        'missing_inputs': [] if words else ['sycm_market_item_rank.title'],
    }


def _avg_over_dates(by_date, dates, keyword, field):
    values = [by_date[d][keyword][field] for d in dates if keyword in by_date[d]
              and by_date[d][keyword][field] is not None]
    if not values:
        return None
    return sum(float(v) for v in values) / len(values)


def keyword_insights(start_date, end_date, rows):
    """8大归类 + 词根需求 + 蓝海机会 + 趋势节点。

    rows: [(stat_date, keyword, search_heat, pay_rate, click_rate)] 升序。
    """
    by_date = _clean_days(rows)
    dates = sorted(by_date)
    if not dates:
        return {'available': False, 'missing_inputs': ['sycm_market_search_rank'],
                'categories': [], 'blue_ocean': [], 'trend_nodes': {'rising': [], 'cooling': []}}

    # ---- 8 大归类 + 词根需求（全窗口聚合）----
    heat_total = 0.0
    category_stats = defaultdict(lambda: {'keyword_count': 0, 'search_heat': 0.0, 'keywords': {}})
    for date in dates:
        for keyword, metrics in by_date[date].items():
            heat = float(metrics['search_heat'] or 0)
            heat_total += heat
            key = _classify_keyword(keyword)
            stats = category_stats[key]
            stats['search_heat'] += heat
            stats['keywords'].setdefault(keyword, 0.0)
            stats['keywords'][keyword] += heat
    unique_keywords = {kw for date in dates for kw in by_date[date]}
    per_category_unique = defaultdict(set)
    for kw in unique_keywords:
        per_category_unique[_classify_keyword(kw)].add(kw)
    categories = []
    for key in list(KEYWORD_CATEGORY_LABELS):
        if key not in category_stats:
            continue
        stats = category_stats[key]
        top_roots = sorted(stats['keywords'].items(), key=lambda item: item[1], reverse=True)[:3]
        categories.append({
            'key': key,
            'label': KEYWORD_CATEGORY_LABELS[key],
            'keyword_count': len(per_category_unique[key]),
            'search_heat': round(stats['search_heat'], 1),
            'heat_share': round(stats['search_heat'] / heat_total, 6) if heat_total else None,
            'top_keywords': [{'keyword': kw, 'search_heat': round(heat, 1)} for kw, heat in top_roots],
        })
    categories.sort(key=lambda item: item['search_heat'], reverse=True)

    # ---- 蓝海机会词（近 7 天窗口；热度×支付转化，剔除泛词）----
    # 热度过低的词支付转化率是小样本噪声（实测会出现 >1 的脏值），设下限滤掉。
    MIN_BLUE_OCEAN_HEAT = 100.0
    recent_dates = dates[-7:]
    kw_recent = {kw for date in recent_dates for kw in by_date[date]}
    candidates = []
    for keyword in kw_recent:
        if keyword.strip().lower() in GENERIC_KEYWORDS or len(keyword.strip()) < 2:
            continue
        heat = _avg_over_dates(by_date, recent_dates, keyword, 'search_heat')
        pay_rate = _avg_over_dates(by_date, recent_dates, keyword, 'pay_rate')
        if heat is None or pay_rate is None or heat < MIN_BLUE_OCEAN_HEAT:
            continue
        candidates.append({'keyword': keyword, 'search_heat': heat, 'pay_rate': pay_rate})
    blue_ocean = []
    if candidates:
        max_heat = max(item['search_heat'] for item in candidates) or 1.0
        max_rate = max(item['pay_rate'] for item in candidates) or 1.0
        for item in candidates:
            # 蓝海度近似：热度归一 × 转化归一（供给覆盖字段未采集，见模块注释）。
            item['score'] = round((item['search_heat'] / max_heat) * 0.5
                                  + (item['pay_rate'] / max_rate) * 0.5, 4)
        blue_ocean = sorted(candidates, key=lambda item: item['score'], reverse=True)[:10]
        for item in blue_ocean:
            item['search_heat'] = round(item['search_heat'], 1)
            item['pay_rate'] = round(item['pay_rate'], 6)

    # ---- 趋势节点：近 7 天 vs 前置窗口（至多 23 天，凑足 30 天口径）----
    recent = dates[-7:]
    baseline_pool = [d for d in dates if d < recent[0]]
    baseline = baseline_pool[-23:]
    rising, cooling = [], []
    trend_available = bool(recent) and bool(baseline)
    if trend_available:
        for keyword in {kw for date in (recent + baseline) for kw in by_date[date]}:
            if keyword.strip().lower() in GENERIC_KEYWORDS:
                continue
            recent_heat = _avg_over_dates(by_date, recent, keyword, 'search_heat')
            base_heat = _avg_over_dates(by_date, baseline, keyword, 'search_heat')
            if not recent_heat or not base_heat:
                continue
            growth = (recent_heat - base_heat) / base_heat
            entry = {
                'keyword': keyword,
                'recent_heat': round(recent_heat, 1),
                'baseline_heat': round(base_heat, 1),
                'growth': round(growth, 4),
            }
            if growth >= 0.5:
                rising.append(entry)
            elif growth <= -0.5:
                cooling.append(entry)
        rising.sort(key=lambda item: item['growth'], reverse=True)
        cooling.sort(key=lambda item: item['growth'])
        rising, cooling = rising[:10], cooling[:10]

    return {
        'available': True,
        'window': {'start': dates[0], 'end': dates[-1], 'day_count': len(dates)},
        'recent_window': {'start': recent[0], 'end': recent[-1], 'day_count': len(recent)},
        'baseline_window': ({'start': baseline[0], 'end': baseline[-1], 'day_count': len(baseline)}
                            if baseline else None),
        'unique_keyword_count': len(unique_keywords),
        'categories': categories,
        'blue_ocean': blue_ocean,
        'trend_nodes': {'rising': rising, 'cooling': cooling,
                        'available': trend_available,
                        'threshold': 0.5},
        'limitations': (['供给覆盖字段未采集：蓝海度=搜索热度×支付转化率近似，'
                         '待搜索词分析导出补齐「每万覆盖」后按 SKILL 完整口径重算。']
                        if blue_ocean else []),
        'missing_inputs': [] if blue_ocean or categories else ['sycm_market_search_rank'],
    }


def rival_item_moves(start_date, end_date, rows, movers_limit=200):
    """竞店爆品排名变化（XMind「竞店-爆品排名变化」）。

    rows: [(stat_date, item_id, title, shop_name, rank, is_self, uv, pay_buyer_count[, pic_url])]
    升序。以窗口内每个商品 首次/末次 在榜排名对比；只在首日出现而不在末日 = 退出，
    反之 = 新进榜。is_self=1（本店）不纳入竞店口径。

    movers_limit 是**单类上限**（默认 200，仅作 payload 兜底），不是页面展示条数：
    页面按店铺展开后应展示该店窗口内全部有排名变化的商品（含主图），
    未变动的在榜商品数单独回传 `unchanged_count`，避免「在榜 81 品却只列 6 行」的误解。
    """
    by_shop = defaultdict(lambda: defaultdict(list))
    shop_days = defaultdict(set)
    for row in rows:
        # 兼容 8 列（无 pic_url 的旧调用/旧测试）与 9 列两种行结构。
        stat_date, item_id, title, shop_name, rank, is_self, uv, pay_buyer_count = row[:8]
        pic_url = row[8] if len(row) > 8 else None
        if is_self:
            continue
        shop = shop_name or '未知店铺'
        by_shop[shop][str(item_id)].append({
            'date': str(stat_date), 'rank': rank, 'title': title or '',
            'uv': uv, 'pay_buyer_count': pay_buyer_count, 'pic_url': pic_url or '',
        })
        shop_days[shop].add(str(stat_date))
    shops = []
    for shop, items in by_shop.items():
        days = sorted(shop_days[shop])
        first_day, last_day = days[0], days[-1]
        rising, falling, new_items, exit_items, stable = [], [], [], [], []
        for item_id, appearances in items.items():
            appearances.sort(key=lambda entry: entry['date'])
            dates_seen = {entry['date'] for entry in appearances}
            first = appearances[0]
            last = appearances[-1]
            if first_day not in dates_seen and last_day in dates_seen:
                new_items.append({'item_id': item_id, 'title': last['title'] or item_id,
                                  'rank': last['rank'], 'date': last['date'],
                                  'pic_url': last['pic_url']})
                continue
            if first_day in dates_seen and last_day not in dates_seen:
                exit_items.append({'item_id': item_id, 'title': first['title'] or item_id,
                                   'rank': first['rank'], 'date': first['date'],
                                   'pic_url': first['pic_url']})
                continue
            if first['rank'] is None or last['rank'] is None:
                continue
            change = int(first['rank']) - int(last['rank'])  # 排名变小=上升
            entry = {'item_id': item_id, 'title': last['title'] or item_id,
                     'first_rank': first['rank'], 'last_rank': last['rank'],
                     'rank_change': change, 'uv': last['uv'], 'pay_buyer_count': last['pay_buyer_count'],
                     'pic_url': last['pic_url']}
            if change > 0:
                rising.append(entry)
            elif change < 0:
                falling.append(entry)
            else:
                stable.append(entry)
        rising.sort(key=lambda item: item['rank_change'], reverse=True)
        falling.sort(key=lambda item: item['rank_change'])
        stable.sort(key=lambda item: (item['last_rank'] if item['last_rank'] is not None else 10 ** 9))
        new_items.sort(key=lambda item: (item['rank'] if item['rank'] is not None else 10 ** 9))
        exit_items.sort(key=lambda item: (item['rank'] if item['rank'] is not None else 10 ** 9))
        # 页面的「变动最大」列与表格都按绝对变动幅度降序，上升/下降混排。
        movers = sorted(rising + falling, key=lambda item: abs(item['rank_change']), reverse=True)
        shops.append({
            'shop_name': shop,
            'window': {'start': first_day, 'end': last_day, 'day_count': len(days)},
            'item_count': len(items),
            'rising_count': len(rising), 'falling_count': len(falling),
            'new_count': len(new_items), 'exit_count': len(exit_items),
            'unchanged_count': len(stable),
            'rising': rising[:movers_limit],
            'falling': falling[:movers_limit],
            'new_items': new_items[:movers_limit],
            'exit_items': exit_items[:movers_limit],
            'stable': stable[:movers_limit],
            'movers': movers[:movers_limit * 2],
            'movers_total': len(movers),
        })
    shops.sort(key=lambda item: (item['rising_count'] + item['falling_count']
                                 + item['new_count'] + item['exit_count']), reverse=True)
    # 商品榜覆盖全市场店铺（窗口内可达数百家），页面只展示变动最活跃的前 15 家，
    # 全量计数保留在 shop_count 供「共 N 家在榜」提示。
    return {
        'available': bool(shops),
        'shop_count': len(shops),
        'shops': shops[:15],
        'missing_inputs': [] if shops else ['sycm_market_item_rank'],
    }


def trend_items(start_date, end_date, rows, limit=10):
    """商品排行 · 趋势市场（XMind「行业-商品排行-趋势市场」）。

    rows 同 `rival_item_moves`（[(stat_date, item_id, title, shop_name, rank, is_self, uv, pay_buyer_count[, pic_url])]）。
    与 `rival_item_moves` **同源**（窗口首尾排名对比），差别只在聚合维度：
    按商品而非按店 —— 所以两个函数必须一起改，别让口径分叉。

    - 上升：末次排名优于首次（rank 数字变小）→ 按改善幅度排序
    - 新进榜：窗口首日不在榜、末日已在榜
    - 本店（is_self=1）不纳入「趋势市场」（看的是别人）
    """
    by_item = defaultdict(list)
    all_days = set()
    for row in rows:
        stat_date, item_id, title, shop_name, rank, is_self, uv, pay_buyer_count = row[:8]
        pic_url = row[8] if len(row) > 8 else None
        all_days.add(str(stat_date))
        if is_self:
            continue
        by_item[str(item_id)].append({
            'date': str(stat_date), 'rank': rank, 'title': title or '',
            'shop_name': shop_name or '', 'uv': uv, 'pay_buyer_count': pay_buyer_count,
            'pic_url': pic_url or '',
        })
    if not all_days:
        return {'available': False, 'rising': [], 'new_items': [],
                'missing_inputs': ['sycm_market_item_rank']}
    days = sorted(all_days)
    first_day, last_day = days[0], days[-1]
    rising, new_items = [], []
    for item_id, appearances in by_item.items():
        appearances.sort(key=lambda entry: entry['date'])
        dates_seen = {entry['date'] for entry in appearances}
        first, last = appearances[0], appearances[-1]
        if first_day not in dates_seen and last_day in dates_seen:
            new_items.append({'item_id': item_id, 'title': last['title'] or item_id,
                              'shop_name': last['shop_name'], 'rank': last['rank'],
                              'uv': last['uv'], 'pay_buyer_count': last['pay_buyer_count'],
                              'pic_url': last['pic_url'], 'date': last['date']})
            continue
        if first['rank'] is None or last['rank'] is None:
            continue
        change = int(first['rank']) - int(last['rank'])
        if change > 0:
            rising.append({'item_id': item_id, 'title': last['title'] or item_id,
                           'shop_name': last['shop_name'],
                           'first_rank': first['rank'], 'last_rank': last['rank'],
                           'rank_change': change,
                           'uv': last['uv'], 'pay_buyer_count': last['pay_buyer_count'],
                           'pic_url': last['pic_url']})
    rising.sort(key=lambda item: item['rank_change'], reverse=True)
    new_items.sort(key=lambda item: (item['rank'] if item['rank'] is not None else 10 ** 9))
    return {
        'available': bool(rising or new_items),
        'window': {'start': first_day, 'end': last_day, 'day_count': len(days)},
        'item_count': len(by_item),
        'rising': rising[:limit],
        'new_items': new_items[:limit],
        'rising_total': len(rising),
        'new_total': len(new_items),
        'missing_inputs': [] if (rising or new_items) else ['sycm_market_item_rank'],
    }
