"""
万相台（one.alimama.com）报表数据采集与映射服务。

将万相台 HTTP 接口返回的 JSON 数据映射到天猫看板的 promotion_daily_facts 表，
实现推广分析模块的数据集成。

万相台核心接口：
- POST /report/query.json      — 报表明细数据
- POST /report/chargeSum.json  — 花费汇总数据

字段映射关系：
    charge                  -> ad_spend                  推广花费
    click                   -> clicks                    点击量
    alipayInshopAmt         -> attributed_payment_amount 归因支付金额（成交金额）
    alipayInshopNum         -> payment_buyers            支付买家数（成交笔数）
    impressions             -> impressions               展现量
    cartRate                -> (计算字段，不入库)
    ctr/cvr/roi/ecpc        -> (计算字段，不入库)
"""

from datetime import date, datetime, timedelta
from typing import Any


# ── 渠道映射 ──────────────────────────────────────────────────────────────
# 万相台营销场景编码 → 天猫看板 promotion_daily_facts.channel 值
CHANNEL_MAP = {
    'search': '搜索推广',           # 货品全站推广 / 搜索推广
    'contentScene': '内容推广',     # 关键词推广 / 内容场景
    'crowd': '人群推广',            # 人群推广
    'shop': '店铺推广',             # 店铺直达
    'display': '展示推广',          # 内容场景 / 展示广告
    'default': '全部',              # 汇总/默认
}

# 反向映射：看板 channel 值 → 万相台场景 key
CHANNEL_REVERSE = {v: k for k, v in CHANNEL_MAP.items()}

# 维度报表(rptType)行的 bizCode 兜底渠道。无界报表行自带 scene1Name，
# 缺失时按 bizCode 归渠道，与外部采集器脚本保持一致。
BIZ_CODE_CHANNEL_MAP = {
    'onebpSearch': '搜索推广',
    'onebpUniversal': '全站推广',
    'onebpCrowd': '人群推广',
    'onebpContent': '内容推广',
    'onebpDisplay': '展示推广',
    'onebpShop': '店铺推广',
}

# report_type → promotion_daily_facts.grain 标签。
# channel/campaign/product 粒度互斥，report 查询按 grain 过滤避免重复求和。
REPORT_TYPE_GRAIN = {
    'channel': 'channel',
    'account': 'product',        # 账户报表实际返回商品级行，无渠道归属
    'item_promotion': 'product',
    'campaign': 'campaign',
    'adgroup': 'unit',
    'unit': 'unit',
    'bidword': 'unit',
    'crowd': 'unit',
    'product': 'product',
}


# ── 字段映射 ──────────────────────────────────────────────────────────────
# 万相台 queryFieldList 字段 → promotion_daily_facts 列名
FIELD_MAP = {
    'charge': 'ad_spend',
    'click': 'clicks',
    'adPv': 'impressions',          # 万相台接口实际返回的展现量字段名
    'impressions': 'impressions',   # 兼容旧字段名
    'alipayInshopAmt': 'attributed_payment_amount',
    'alipayInshopNum': 'payment_buyers',
    'alipayDirAmt': 'direct_payment_amount',
    'alipayDirNum': None,
    'cartRate': None,
    'ctr': None,
    'cvr': None,
    'roi': None,
    'ecpc': None,
    'cpm': None,
    'ecpm': None,
}


class WanxiangtaiValidationError(ValueError):
    """万相台数据验证错误。"""
    pass


class WanxiangtaiService:
    """万相台报表数据采集与映射服务。"""

    # ── 数据解析 ──────────────────────────────────────────────────────────

    @staticmethod
    def parse_report_payload(payload: dict, report_type: str = 'account',
                             split_type: str = 'day',
                             start_date: str = None,
                             end_date: str = None) -> dict:
        """
        解析万相台 /report/query.json 维度报表响应，返回结构化结果。

        与 parse_query_response 的区别：除 facts 行外，还产出
        - creatives: 创意维度行（creative 报表，写入 promotion_creatives）
        - campaign_items: 计划×商品映射行（campaign 报表 promotions[]，
          写入 promotion_campaign_items，支撑商品抽屉的计划/渠道归因）
        """
        if not isinstance(payload, dict):
            raise WanxiangtaiValidationError('响应必须是 JSON 对象')

        data = payload.get('data') or {}
        rows = data.get('list') or []

        result = {'facts': [], 'creatives': [], 'campaign_items': []}
        for idx, row in enumerate(rows):
            try:
                if report_type == 'creative':
                    creative = WanxiangtaiService._row_to_creative(row)
                    fact = None
                    if creative:
                        fact = WanxiangtaiService._creative_row_to_fact(
                            row, split_type, start_date, end_date)
                    if creative:
                        result['creatives'].append(creative)
                    if fact:
                        result['facts'].append(fact)
                    continue

                fact = WanxiangtaiService._row_to_fact(
                    row, report_type, split_type, start_date, end_date, idx
                )
                if fact:
                    result['facts'].append(fact)
                if report_type == 'campaign':
                    result['campaign_items'].extend(
                        WanxiangtaiService._campaign_row_to_items(row, fact))
            except Exception:
                # 单行解析失败不影响其他行
                continue

        return result

    @staticmethod
    def parse_query_response(payload: dict, report_type: str = 'account',
                              split_type: str = 'day',
                              start_date: str = None,
                              end_date: str = None) -> list[dict]:
        """
        解析万相台 /report/query.json 接口响应，转换为 promotion_daily_facts 行。

        Args:
            payload: 接口返回的完整 JSON（含 status, data）
            report_type: 报表类型 account/campaign/adgroup/bidword/crowd/item/creative/area
            split_type: 时间粒度 day/week/month/calendarmonth/hour/summary
            start_date: 查询开始日期 YYYY-MM-DD（用于分日数据补全）
            end_date: 查询结束日期 YYYY-MM-DD

        Returns:
            list[dict]: 可直接写入 promotion_daily_facts 的行列表
        """
        return WanxiangtaiService.parse_report_payload(
            payload, report_type, split_type, start_date, end_date
        )['facts']

    @staticmethod
    def parse_charge_sum_response(payload: dict, start_date: str = None,
                                   end_date: str = None) -> list[dict]:
        """
        解析万相台 /report/chargeSum.json 接口响应，按营销场景拆分为多行。

        chargeSum 返回的是各营销场景的花费汇总，适合作为渠道级数据导入。

        Args:
            payload: 接口返回的完整 JSON
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            list[dict]: promotion_daily_facts 行列表（按渠道拆分）
        """
        if not isinstance(payload, dict):
            raise WanxiangtaiValidationError('响应必须是 JSON 对象')

        data = payload.get('data') or {}
        if not data:
            return []

        # chargeSum 响应中的场景字段映射
        scene_fields = {
            'searchCharge': 'search',
            'contentSceneCharge': 'contentScene',
            'crowdCharge': 'crowd',
            'shopCharge': 'shop',
            'displayCharge': 'display',
        }

        result = []
        # chargeSum 是区间汇总，不具备逐日粒度。只有单日查询才能写入
        # promotion_daily_facts；多日查询保留区间元数据，由调用方决定如何存储。
        is_single_day = bool(start_date and end_date and start_date == end_date)
        target_date = (start_date or end_date or date.today().isoformat()) if is_single_day else None

        for field, scene_key in scene_fields.items():
            spend = data.get(field)
            if spend is None or float(spend) == 0:
                continue

            channel = CHANNEL_MAP.get(scene_key, scene_key)
            result.append({
                'date': target_date,
                'period_start': start_date,
                'period_end': end_date,
                'granularity': 'day' if is_single_day else 'summary',
                'channel': channel,
                'campaign_id': '',
                'unit_id': '',
                'product_id': '',
                'ad_spend': float(spend),
                'attributed_payment_amount': None,
                'impressions': None,
                'clicks': None,
                'payment_buyers': None,
                'direct_payment_amount': None,
                'indirect_payment_amount': None,
            })

        return result

    # ── 单行转换 ──────────────────────────────────────────────────────────

    @staticmethod
    def _row_to_fact(row: dict, report_type: str, split_type: str,
                      start_date: str, end_date: str, row_index: int) -> dict | None:
        """将万相台接口返回的单行数据转换为 promotion_daily_facts 行。"""
        # 提取维度字段
        channel = WanxiangtaiService._extract_channel(row, report_type)
        campaign_id = str(row.get('campaignId') or row.get('campaign_id') or '')
        unit_id = str(row.get('adgroupId') or row.get('unit_id') or '')
        product_id = str(row.get('itemId') or row.get('promotionId') or row.get('product_id') or '')

        # 维度报表行级修正：campaign 报表行是计划粒度，product_id 由
        # promotions[] 映射表承载，不落在事实行上（避免同一计划多商品重复计花费）。
        if report_type == 'campaign':
            product_id = ''
        if report_type == 'item_promotion':
            unit_id = ''

        # 提取日期
        fact_date = WanxiangtaiService._extract_date(
            row, split_type, start_date, end_date, row_index
        )
        if not fact_date:
            return None

        # 提取指标字段
        ad_spend = WanxiangtaiService._to_float(row.get('charge'))
        clicks = WanxiangtaiService._to_int(row.get('click'))
        impressions = WanxiangtaiService._to_int(row.get('adPv') if row.get('adPv') is not None else row.get('impressions'))
        attributed_payment = WanxiangtaiService._to_float(row.get('alipayInshopAmt'))
        payment_buyers = WanxiangtaiService._to_int(row.get('alipayInshopNum'))
        direct_payment = WanxiangtaiService._to_float(row.get('alipayDirAmt'))
        cart_adds = WanxiangtaiService._to_int(row.get('cartInshopNum'))
        cart_cost = WanxiangtaiService._to_float(row.get('cartCost'))
        new_buyers = WanxiangtaiService._to_int(row.get('newAlipayInshopNum'))

        # 至少要有花费或成交金额，否则跳过
        if ad_spend is None and attributed_payment is None:
            return None

        grain = REPORT_TYPE_GRAIN.get(report_type, '')
        if report_type == 'account' and not product_id:
            # 账户报表里的总账行(无商品归属),单独标粒度,不进商品排行
            grain = 'account'
        return {
            'date': fact_date,
            'channel': channel,
            'campaign_id': campaign_id,
            'campaign_name': str(row.get('campaignName') or ''),
            'unit_id': unit_id,
            'product_id': product_id,
            'grain': grain,
            'ad_spend': ad_spend,
            'attributed_payment_amount': attributed_payment,
            'impressions': impressions,
            'clicks': clicks,
            'payment_buyers': payment_buyers,
            'direct_payment_amount': direct_payment,
            'indirect_payment_amount': None,
            'cart_adds': cart_adds,
            'cart_cost': cart_cost,
            'new_buyers': new_buyers,
        }

    @staticmethod
    def _row_to_creative(row: dict) -> dict | None:
        """将创意报表行转换为 promotion_creatives 维度行。"""
        creative_id = str(row.get('creativeId') or '')
        if not creative_id:
            return None
        return {
            'creative_id': creative_id,
            'creative_name': str(row.get('creativeName') or ''),
            'image_url': str(row.get('creativeImagePath') or row.get('creativeImagePathUrl') or ''),
            'video_url': str(row.get('creativeVedioPath') or ''),
            'creative_format': str(row.get('creativeFormat') or ''),
            'product_id': str(row.get('promotionId') or ''),
            'product_name': str(row.get('promotionName') or ''),
            'channel': WanxiangtaiService._extract_channel(row, 'creative'),
        }

    @staticmethod
    def _creative_row_to_fact(row: dict, split_type: str,
                              start_date: str, end_date: str) -> dict | None:
        """将创意报表行转换为 promotion_creative_daily 事实行。"""
        ad_spend = WanxiangtaiService._to_float(row.get('charge'))
        attributed_payment = WanxiangtaiService._to_float(row.get('alipayInshopAmt'))
        if ad_spend is None and attributed_payment is None:
            return None
        fact_date = WanxiangtaiService._extract_date(
            row, split_type, start_date, end_date, 0)
        if not fact_date:
            return None
        return {
            'date': fact_date,
            'channel': WanxiangtaiService._extract_channel(row, 'creative'),
            'creative_id': str(row.get('creativeId') or ''),
            'product_id': str(row.get('promotionId') or ''),
            'campaign_id': str(row.get('campaignId') or ''),
            'ad_spend': ad_spend,
            'attributed_payment_amount': attributed_payment,
            'impressions': WanxiangtaiService._to_int(row.get('adPv')),
            'clicks': WanxiangtaiService._to_int(row.get('click')),
            'payment_buyers': WanxiangtaiService._to_int(row.get('alipayInshopNum')),
            'direct_payment_amount': WanxiangtaiService._to_float(row.get('alipayDirAmt')),
            'indirect_payment_amount': None,
            'cart_adds': WanxiangtaiService._to_int(row.get('cartInshopNum')),
            'new_buyers': WanxiangtaiService._to_int(row.get('newAlipayInshopNum')),
        }

    @staticmethod
    def _campaign_row_to_items(row: dict, fact: dict | None) -> list[dict]:
        """从 campaign 报表行的 promotions[] 提取计划×商品映射。"""
        campaign_id = str(row.get('campaignId') or '')
        if not campaign_id:
            return []
        channel = fact['channel'] if fact else ''
        campaign_name = str(row.get('campaignName') or '')
        items = []
        for promo in row.get('promotions') or []:
            if not isinstance(promo, dict):
                continue
            product_id = str(promo.get('promotionId') or '')
            if not product_id:
                continue
            items.append({
                'campaign_id': campaign_id,
                'product_id': product_id,
                'campaign_name': campaign_name,
                'product_name': str(promo.get('promotionName') or ''),
                'image_url': str(promo.get('imgUrl') or ''),
                'channel': channel,
            })
        return items

    @staticmethod
    def _extract_channel(row: dict, report_type: str) -> str:
        """从数据行中提取渠道信息。"""
        # 无界维度报表行自带场景名（scene1Name / originalSceneName）
        for key in ('scene1Name', 'originalSceneName', 'sceneName',
                    'channel', 'channelName', 'channel_name', 'marketingScene'):
            val = row.get(key)
            if val:
                val_str = str(val)
                # 如果是英文编码，映射为中文
                if val_str in CHANNEL_MAP:
                    return CHANNEL_MAP[val_str]
                return val_str

        # 场景名缺失时按 bizCode 归渠道
        biz_code = row.get('bizCode') or row.get('originalBizCode')
        if biz_code and str(biz_code) in BIZ_CODE_CHANNEL_MAP:
            return BIZ_CODE_CHANNEL_MAP[str(biz_code)]

        # 营销场景报表默认按渠道拆分，根据报表类型给默认值
        if report_type == 'account':
            return CHANNEL_MAP['default']
        return '全部'

    @staticmethod
    def _extract_date(row: dict, split_type: str, start_date: str,
                      end_date: str, row_index: int) -> str | None:
        """从数据行中提取日期。"""
        # 优先从行数据中获取日期字段
        for key in ('date', 'bizDate', 'statDate', 'day', 'logDate'):
            val = row.get(key)
            if val:
                return WanxiangtaiService._normalize_date(str(val))

        # 单日查询（start == end）：维度报表行不携带日期，整批归当天
        if start_date and end_date and start_date == end_date:
            return start_date

        # 分日数据：根据行索引和开始日期推算
        if split_type == 'day' and start_date:
            try:
                base = date.fromisoformat(start_date)
                target = base + timedelta(days=row_index)
                if end_date:
                    end = date.fromisoformat(end_date)
                    if target > end:
                        return end.isoformat()
                return target.isoformat()
            except (ValueError, TypeError):
                # 日期解析失败时跳过该条数据
                pass

        # 分周/分月：使用结束日期作为代表日期
        if split_type in ('week', 'month', 'calendarmonth') and end_date:
            return end_date

        # 汇总：使用结束日期
        if split_type == 'summary' and end_date:
            return end_date

        # 兜底：使用开始日期或今天
        return start_date or date.today().isoformat()

    # ── 工具方法 ──────────────────────────────────────────────────────────

    @staticmethod
    def _normalize_date(date_str: str) -> str | None:
        """将各种日期格式统一为 YYYY-MM-DD。"""
        date_str = date_str.strip()
        formats = (
            '%Y-%m-%d', '%Y/%m/%d', '%Y%m%d',
            '%Y-%m-%d %H:%M:%S', '%Y/%m/%d %H:%M:%S',
        )
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt).strftime('%Y-%m-%d')
            except ValueError:
                continue
        return None

    @staticmethod
    def _to_float(val: Any) -> float | None:
        """安全转换为 float。"""
        if val is None or val == '':
            return None
        try:
            return float(val)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _to_int(val: Any) -> int | None:
        """安全转换为 int。"""
        if val is None or val == '':
            return None
        try:
            return int(float(val))
        except (ValueError, TypeError):
            return None

    # ── 构建接口请求参数 ──────────────────────────────────────────────────

    @staticmethod
    def build_query_payload(start_date: str, end_date: str,
                            split_type: str = 'day',
                            effect_equal: int = 15,
                            extra_fields: list[str] = None) -> dict:
        """
        构建万相台 /report/query.json 的 POST 请求体。

        Args:
            start_date: 开始日期 YYYY-MM-DD
            end_date: 结束日期 YYYY-MM-DD
            split_type: 时间粒度 day/week/month/calendarmonth/hour/summary
            effect_equal: 转化统计周期（天）
            extra_fields: 额外查询的指标字段

        Returns:
            dict: POST 请求体（JSON）
        """
        base_fields = [
            'charge', 'click', 'adPv',
            'ctr', 'roi', 'cvr', 'ecpc', 'ecpm',
            'alipayInshopAmt', 'alipayInshopNum',
            'alipayDirAmt', 'alipayDirNum',
            'cartNum', 'cartCost',
            'newBuyers', 'favCount',
        ]
        if extra_fields:
            for f in extra_fields:
                if f not in base_fields:
                    base_fields.append(f)

        return {
            'bizCode': 'universalBP',
            'fromRealTime': False,
            'source': 'baseReport',
            'startTime': start_date,
            'endTime': end_date,
            'unitType': 'zhai',
            'effectEqual': effect_equal,
            'splitType': split_type,
            'queryFieldList': base_fields,
            'chargeClickCvr': False,
            'tips': None,
            'properties': [],
        }

    @staticmethod
    def build_charge_sum_payload(start_date: str, end_date: str,
                                  split_type: str = 'day',
                                  effect_equal: int = 15) -> dict:
        """构建万相台 /report/chargeSum.json 的 POST 请求体。"""
        payload = WanxiangtaiService.build_query_payload(
            start_date, end_date, split_type, effect_equal
        )
        payload.update({
            'byPage': True,
            'totalTag': True,
            'needCountAccelerate': True,
            'byPageEndTime': end_date,
        })
        return payload


# 单例
wanxiangtai_service = WanxiangtaiService()
