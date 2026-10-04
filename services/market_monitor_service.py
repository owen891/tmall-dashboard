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
- 商品排行·趋势市场（`trend_items`）：同一套窗口首尾对比，聚合维度换成商品，
  给出全市场上升最快与新进榜商品。

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
        # 2026-10-02 按未归 TOP100 热度词回填：新锐品牌/设计师品牌/海外品牌。
        '小野和子', '茉寻', '涞觅', '菇娘家', '绫', '汲润', '觅橘', '宝娜斯',
        '上森派系', '一朵云', '一只鱼', '黄小姐', '蒋大猫', '安幸', 'yangma',
        'calzedonia', 'wolford', 'tabio', 'himade', 'purple guys', 'roji',
        'swwamvennt',
    )),
    ('crowd', '人群', (
        '儿童', '婴', '宝宝', '幼儿', '男', '女', '情侣', '亲子', '学生', '月子',
        '孕妇', '老人', '大码', '加大', '成人', '伪娘', 'lolita', '艺术生',
    )),
    ('function', '功能', (
        '压力', '抗菌', '防臭', '防滑', '防勾丝', '瑜伽', '睡眠', '运动', '篮球',
        '跑步', '登山', '滑雪', '骑行', '健身', '防晒', '保暖', '发热', '自发热',
        '吸汗', '透气', '束腰', '塑形', '矫正', '按摩', '托腹', '静音', '压缩',
        '护膝', '瘦腿', '马油', '脚尖加固', '加固', '防磨', '吸湿',
    )),
    ('scene', '场景', (
        '春夏', '秋冬', '夏季', '冬季', '春秋', '四季', '春款', '夏款', '秋款',
        '冬款', '坐月子', '月子里', '婚', '新娘', '通勤', '户外', '居家', '睡觉',
        '高跟鞋', '单鞋', '靴子', '搭lo', 'jk',
    )),
    ('style', '风格', (
        '日系', '韩系', 'ins', '复古', '甜美', '学院', '港风', '法式', '纯欲',
        '辣妹', '堆堆', '字母', '卡通', '印花', '刺绣', '纯色', '撞色', '彩色',
        '彩虹', '条纹', '格纹', '波点', '褶皱', '木耳边', '花边', '蕾丝',
        'lolita', '渔网', '肉色', '腿精', '银葱', '花藤', '奶油', '雾霾蓝',
        'lolita袜', 'lolita',
    )),
    ('attribute', '属性', (
        '纯棉', '棉', '羊毛', '羊绒', '蚕丝', '冰丝', '莫代尔', '竹纤维', '莱卡',
        '锦纶', '涤纶', '薄', '厚', '中厚', '加绒', '加厚', '毛巾圈', '毛圈',
        '网眼', '隐形', '透明', '黑色', '白色', '灰色', '肤色', '咖啡', '卡其',
        '高腰', '低腰', '长款', '短款', '钢丝', '无骨', '无缝',
        '即弃', '银葱', '毛巾', '夹趾', '分趾', '半掌', '踩脚', '浅口', '松口', '天鹅绒', '水光', '美肤',
        '丝滑', '油亮', '光面', '冰', 'cool',
    )),
    ('price', '价格', (
        '特价', '清仓', '折扣', '便宜', '平价', '百亿补贴', '包邮', '断码',
        '9.9', '19.9', '29.9', '39.9',
        '先用后付', '超级品类日', '天天特卖', '淘工厂', '福袋', '30元',
    )),
    ('category', '类目', (
        '袜子', '中筒', '长筒', '船袜', '隐形袜', '短袜', '连裤袜', '打底裤',
        '丝袜', '黑丝', '白丝', '灰丝', '过膝', '小腿袜', '五指袜', '地板袜',
        '毛圈袜', '拖鞋袜', '蹦迪袜', '足球袜', '袜套', '袜筒', '筒袜',
        '光腿', '美腿', '打底', '压力袜', '静脉曲张',
        # 2026-10-02 按未归 TOP100 回填：长袜/裤袜系与形态细分。
        '长袜', '裤袜', '腿袜', '吊带袜', '大腿袜', '长腿袜', '半腿袜', '半截袜',
        '靴袜', '连体袜', '连袜裤', '网袜', '网面袜', '白袜', '膝盖袜', '护腿',
        '腿套', '千金袜', '小白袜', '冰冰袜', '毛巾袜', '连裤', '打底袜', '袜裤', '诸暨',
    )),
)

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
      功能词，如 堆堆袜/小腿袜/压力袜——先人工挑 20 个细分词再算覆盖）。
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
    # 与 SKILL CATEGORY_WORDS 同性质（细分品类/功能词，如 堆堆袜/压力袜）。
    # 覆盖匹配按「词根」而非长尾组合词：600 款在榜样本不会原样包含
    # 「袜子女2026新款爆款」这类长尾词，完整词匹配全得 0 覆盖；
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
        # 取最长的命中词根做匹配单位（「压力袜」优先于「袜」类泛根）。
        root = max(roots, key=len)
        daily_heat = sum(heats) / len(heats)
        if daily_heat < 100:
            continue
        cover = sum(1 for title in item_titles if root in str(title or ''))
        cover_per_10k = (cover / (daily_heat / 10000.0)) if daily_heat else None
        # ⚠️ cover=0 **不等于**「供给稀缺」。在榜样本只有最新日 600 款（5 类目 × top120），
        #    当词根与标题用词不一致时（「脚尖加固」「毛巾袜」标题里基本没人这么写）也是 0。
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


def trend_items(start_date, end_date, rows, limit=10):
    """商品排行 · 趋势市场（XMind「行业-商品排行-趋势市场」）。

    rows 同 `rival_item_moves`（[(stat_date, item_id, title, shop_name, rank, is_self, uv, pay_buyer_count)]）。
    与 `rival_item_moves` **同源**（窗口首尾排名对比），差别只在聚合维度：
    按商品而非按店 —— 所以两个函数必须一起改，别让口径分叉。

    - 上升：末次排名优于首次（rank 数字变小）→ 按改善幅度排序
    - 新进榜：窗口首日不在榜、末日已在榜
    - 本店（is_self=1）不纳入「趋势市场」（看的是别人）
    """
    by_item = defaultdict(list)
    all_days = set()
    for stat_date, item_id, title, shop_name, rank, is_self, uv, pay_buyer_count in rows:
        all_days.add(str(stat_date))
        if is_self:
            continue
        by_item[str(item_id)].append({
            'date': str(stat_date), 'rank': rank, 'title': title or '',
            'shop_name': shop_name or '', 'uv': uv, 'pay_buyer_count': pay_buyer_count,
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
                              'date': last['date']})
            continue
        if first['rank'] is None or last['rank'] is None:
            continue
        change = int(first['rank']) - int(last['rank'])
        if change > 0:
            rising.append({'item_id': item_id, 'title': last['title'] or item_id,
                           'shop_name': last['shop_name'],
                           'first_rank': first['rank'], 'last_rank': last['rank'],
                           'rank_change': change,
                           'uv': last['uv'], 'pay_buyer_count': last['pay_buyer_count']})
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
