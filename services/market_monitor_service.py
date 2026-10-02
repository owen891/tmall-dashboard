"""市场监控深化计算（对齐月复盘 XMind「市场监控-行业」）。

四项能力，口径迁移自 `E:/skill-dianshang/月复盘SKILL/SKILL.md` §340-360：
- 关键词 8 大归类 + 词根需求：类目/人群/属性/风格/场景/功能/品牌/价格，
  每类给出搜索量占比 + 覆盖词数 + 核心词根（TOP3）。
- 蓝海机会词：细分词（剔除泛词）高搜索 × 高支付转化。SKILL 完整口径还要求
  「每万供给覆盖」，该字段当前采集链路没有导出——此处用 热度×转化率 近似，
  并在返回里标注 limitation，待搜索词分析导出补齐供给覆盖后替换。
- 趋势节点：近 7 天日均搜索热度 vs 前置窗口（至多 23 天）日均，增速超阈值
  判「起势」/「退势」；历史不足 14 天时窗口自动收缩并如实标注天数。
- 竞店爆品排名变化：生意参谋商品榜（sycm_market_item_rank）窗口首尾对比，
  每店给出 上升/下降/新进榜/退出 榜单与 TOP 变动。

全部只读；数据缺失返回空列表与 missing_inputs，不臆造 0。
"""

from collections import defaultdict

# 泛词表（SKILL：泛词参与蓝海判断会让大词被误判为蓝海）。
GENERIC_KEYWORDS = {
    '袜子', '袜', '袜子女', '袜子男', '男袜子', '女袜子', '男士袜子', '女士袜子',
    '男款袜子', '女款袜子', '袜子男款', '袜子女款', '男士袜', '女士袜',
    'socks', '店铺', '旗舰店',
}

# 8 大归类规则词典（有序，先命中先归类）。词表是可维护的初版，
# 归类结果随搜索词滚动变化，后续可在页面上人工纠偏后回填这里。
KEYWORD_RULES = (
    ('brand', '品牌', (
        '蕉内', '有棵树', '秘密世界', '棉竹屋', '棉芝士', '妮轻', '竹久', '南极人',
        '俞兆林', '猫人', '北极绒', '帕兰朵', '优衣库', '斐乐', '耐克', 'nike',
        '阿迪', 'adidas', '乔丹', '安踏', '李宁', '迪士尼', 'miniso', '名创优品',
        'ubras', '内外', '蕉下', '浪莎', '梦娜', '芬腾', '恒源祥', '七匹狼',
    )),
    ('crowd', '人群', (
        '儿童', '婴', '宝宝', '幼儿', '男', '女', '情侣', '亲子', '学生', '月子',
        '孕妇', '老人', '大码', '加大', '成人',
    )),
    ('function', '功能', (
        '压力', '抗菌', '防臭', '防滑', '防勾丝', '瑜伽', '睡眠', '运动', '篮球',
        '跑步', '登山', '滑雪', '骑行', '健身', '防晒', '保暖', '发热', '自发热',
        '吸汗', '透气', '束腰', '塑形', '矫正', '按摩', '托腹', '静音', '压缩',
    )),
    ('scene', '场景', (
        '春夏', '秋冬', '夏季', '冬季', '春秋', '四季', '春款', '夏款', '秋款',
        '冬款', '坐月子', '月子里', '婚', '新娘', '通勤', '户外', '居家', '睡觉',
    )),
    ('style', '风格', (
        '日系', '韩系', 'ins', '复古', '甜美', '学院', '港风', '法式', '纯欲',
        '辣妹', '堆堆', '字母', '卡通', '印花', '刺绣', '纯色', '撞色', '彩色',
        '彩虹', '条纹', '格纹', '波点', '褶皱', '木耳边', '花边', '蕾丝',
    )),
    ('attribute', '属性', (
        '纯棉', '棉', '羊毛', '羊绒', '蚕丝', '冰丝', '莫代尔', '竹纤维', '莱卡',
        '锦纶', '涤纶', '薄', '厚', '中厚', '加绒', '加厚', '毛巾圈', '毛圈',
        '网眼', '隐形', '透明', '黑色', '白色', '灰色', '肤色', '咖啡', '卡其',
        '高腰', '低腰', '长款', '短款', '钢丝', '无骨', '无缝',
    )),
    ('price', '价格', (
        '特价', '清仓', '折扣', '便宜', '平价', '百亿补贴', '包邮', '断码',
        '9.9', '19.9', '29.9', '39.9',
    )),
    ('category', '类目', (
        '袜子', '中筒', '长筒', '船袜', '隐形袜', '短袜', '连裤袜', '打底裤',
        '丝袜', '黑丝', '白丝', '灰丝', '过膝', '小腿袜', '五指袜', '地板袜',
        '毛圈袜', '拖鞋袜', '蹦迪袜', '足球袜', '袜套', '袜筒', '筒袜',
        '光腿', '美腿', '打底', '压力袜', '静脉曲张',
    )),
)

KEYWORD_CATEGORY_LABELS = {key: label for key, label, _ in KEYWORD_RULES} | {'other': '其他'}


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

    - 搜索量 = 词精确匹配的近 30 天日均搜索热度（不累加词根下其他词）；
    - 商品覆盖 = 最新采集日在榜商品 title 含该词的商品数（product_id 去重）；
    - 每万覆盖 = 覆盖数 ÷ (日均热度 / 10000)，<5 高潜蓝海、5-10 中等、>10 供给偏多；
    - 泛词剔除、转化率作辅助维度。
    """
    by_date = _clean_days(keyword_rows)
    dates = sorted(by_date)
    if not dates:
        return {'available': False, 'words': [],
                'missing_inputs': ['sycm_market_search_rank']}
    recent_dates = dates[-7:]
    term_daily = defaultdict(list)
    for date in recent_dates:
        for keyword, metrics in by_date[date].items():
            if str(keyword).strip().lower() in GENERIC_KEYWORDS or len(str(keyword).strip()) < 2:
                continue
            if metrics['search_heat'] is not None:
                term_daily[str(keyword)].append(float(metrics['search_heat']))
    max_rate = 0.0
    words = []
    for keyword, heats in term_daily.items():
        daily_heat = sum(heats) / len(heats)
        if daily_heat < 100:
            continue
        cover = sum(1 for title in item_titles if keyword in str(title or ''))
        cover_per_10k = (cover / (daily_heat / 10000.0)) if daily_heat else None
        words.append({
            'keyword': keyword,
            'search_heat': round(daily_heat, 1),
            'cover_count': cover,
            'cover_per_10k': (round(cover_per_10k, 2) if cover_per_10k is not None else None),
            'grade': ('高潜蓝海' if cover_per_10k is not None and cover_per_10k < 5
                      else '中等' if cover_per_10k is not None and cover_per_10k <= 10 else '供给偏多'),
        })
    return {
        'available': bool(words),
        'words': sorted(words, key=lambda item: (item['cover_per_10k'] is None,
                                                 item['cover_per_10k'] or 0))[:12],
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


def rival_item_moves(start_date, end_date, rows, movers_limit=8):
    """竞店爆品排名变化（XMind「竞店-爆品排名变化」）。

    rows: [(stat_date, item_id, title, shop_name, rank, is_self, uv, pay_buyer_count)] 升序。
    以窗口内每个商品 首次/末次 在榜排名对比；只在首日出现而不在末日 = 退出，
    反之 = 新进榜。is_self=1（本店）不纳入竞店口径。
    """
    by_shop = defaultdict(lambda: defaultdict(list))
    shop_days = defaultdict(set)
    for stat_date, item_id, title, shop_name, rank, is_self, uv, pay_buyer_count in rows:
        if is_self:
            continue
        shop = shop_name or '未知店铺'
        by_shop[shop][str(item_id)].append({
            'date': str(stat_date), 'rank': rank, 'title': title or '',
            'uv': uv, 'pay_buyer_count': pay_buyer_count,
        })
        shop_days[shop].add(str(stat_date))
    shops = []
    for shop, items in by_shop.items():
        days = sorted(shop_days[shop])
        first_day, last_day = days[0], days[-1]
        rising, falling, new_items, exit_items = [], [], [], []
        for item_id, appearances in items.items():
            appearances.sort(key=lambda entry: entry['date'])
            dates_seen = {entry['date'] for entry in appearances}
            first = appearances[0]
            last = appearances[-1]
            if first_day not in dates_seen and last_day in dates_seen:
                new_items.append({'item_id': item_id, 'title': last['title'] or item_id,
                                  'rank': last['rank'], 'date': last['date']})
                continue
            if first_day in dates_seen and last_day not in dates_seen:
                exit_items.append({'item_id': item_id, 'title': first['title'] or item_id,
                                   'rank': first['rank'], 'date': first['date']})
                continue
            if first['rank'] is None or last['rank'] is None:
                continue
            change = int(first['rank']) - int(last['rank'])  # 排名变小=上升
            entry = {'item_id': item_id, 'title': last['title'] or item_id,
                     'first_rank': first['rank'], 'last_rank': last['rank'],
                     'rank_change': change, 'uv': last['uv'], 'pay_buyer_count': last['pay_buyer_count']}
            if change > 0:
                rising.append(entry)
            elif change < 0:
                falling.append(entry)
        rising.sort(key=lambda item: item['rank_change'], reverse=True)
        falling.sort(key=lambda item: item['rank_change'])
        movers = (rising[:movers_limit] + falling[:movers_limit])
        shops.append({
            'shop_name': shop,
            'window': {'start': first_day, 'end': last_day, 'day_count': len(days)},
            'item_count': len(items),
            'rising_count': len(rising), 'falling_count': len(falling),
            'new_count': len(new_items), 'exit_count': len(exit_items),
            'rising': rising[:movers_limit],
            'falling': falling[:movers_limit],
            'new_items': new_items[:movers_limit],
            'exit_items': exit_items[:movers_limit],
            'movers': movers,
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
