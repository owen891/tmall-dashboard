# -*- coding: utf-8 -*-
"""工具箱 API - 运营工具任务管理"""

import re
import json
from collections import Counter
from flask import Blueprint, jsonify, request
from db import get_db
from services.shop_scope_service import reject_legacy_shop_scope

tool_bp = Blueprint('tool', __name__)

# 工具定义
TOOLS = [
    {
        "id": "data_import",
        "name": "数据导入",
        "icon": "📥",
        "desc": "上传生意参谋/付费报表/DMP等Excel数据文件，自动识别Sheet类型并导入",
        "status": "active",
        "params": [
            {"key": "file", "label": "Excel文件", "type": "file", "placeholder": "上传.xlsx文件"},
        ],
    },
    {
        "id": "main_image_suggest",
        "name": "评价生成主图建议",
        "icon": "🖼️",
        "desc": "分析好评数据，提取核心卖点，生成主图优化建议",
        "status": "available",
        "params": [
            {"key": "product_id", "label": "商品ID（可选）", "type": "text", "placeholder": "留空则分析全部商品", "required": False},
            {"key": "limit", "label": "分析评价数量", "type": "number", "placeholder": "默认50条", "required": False},
        ],
    },
    {
        "id": "review_reply",
        "name": "评价仿写助手",
        "icon": "✍️",
        "desc": "根据评价内容自动生成专业回复模板",
        "status": "available",
        "params": [
            {"key": "review_text", "label": "评价内容", "type": "text", "placeholder": "请输入需要回复的评价内容", "required": True},
            {"key": "reply_style", "label": "回复风格", "type": "select", "required": False,
             "options": [
                 {"value": "专业正式", "label": "专业正式"},
                 {"value": "亲切温暖", "label": "亲切温暖"},
                 {"value": "简洁高效", "label": "简洁高效"},
             ]},
            {"key": "product_type", "label": "商品类型（可选）", "type": "text", "placeholder": "如：连衣裙、手机壳、零食", "required": False},
        ],
    },
    {
        "id": "product_diagnose",
        "name": "商品详情页诊断",
        "icon": "🔍",
        "desc": "综合分析商品数据，诊断详情页各维度优化机会",
        "status": "available",
        "params": [
            {"key": "product_id", "label": "商品ID", "type": "text", "placeholder": "请输入商品ID", "required": True},
        ],
    },
    {
        "id": "main_image_gen",
        "name": "评价生成主图",
        "icon": "🖼️",
        "desc": "基于竞品评价洞察生成5张产品主图",
        "status": "coming_soon",
        "params": [
            {"key": "brand", "label": "品牌名称", "type": "text", "placeholder": "请输入品牌名称"},
            {"key": "category", "label": "品类", "type": "text", "placeholder": "请输入品类"},
            {"key": "white_bg_image", "label": "白底图", "type": "file", "placeholder": "上传白底产品图"},
            {"key": "competitor_ids", "label": "竞品商品ID", "type": "text", "placeholder": "多个ID用逗号分隔"},
        ],
    },
    {
        "id": "detail_clone",
        "name": "爆款详情页复刻",
        "icon": "📋",
        "desc": "学习竞品详情页，生成超越竞品的详情页",
        "status": "coming_soon",
        "params": [
            {"key": "product_id", "label": "自己的商品ID", "type": "text", "placeholder": "请输入商品ID"},
            {"key": "competitor_id", "label": "竞品商品ID", "type": "text", "placeholder": "请输入竞品商品ID"},
        ],
    },
    {
        "id": "detail_optimize",
        "name": "详情页优化对比",
        "icon": "✨",
        "desc": "原版 vs AI优化版详情页左右对比",
        "status": "coming_soon",
        "params": [
            {"key": "product_id", "label": "商品ID", "type": "text", "placeholder": "请输入商品ID"},
        ],
    },
    {
        "id": "comment_rewrite",
        "name": "评价仿写",
        "icon": "✍️",
        "desc": "竞品评价1:1仿写，生成高质量评价",
        "status": "coming_soon",
        "params": [
            {"key": "competitor_id", "label": "竞品商品ID", "type": "text", "placeholder": "请输入竞品商品ID"},
            {"key": "count", "label": "生成数量", "type": "number", "placeholder": "默认10条"},
        ],
    },
    {
        "id": "get_comments",
        "name": "获取商品评价",
        "icon": "💬",
        "desc": "通过API获取商品评价数据",
        "status": "coming_soon",
        "params": [
            {"key": "product_ids", "label": "商品ID列表", "type": "text", "placeholder": "多个ID用逗号分隔"},
        ],
    },
    {
        "id": "get_properties",
        "name": "获取商品属性",
        "icon": "🏷️",
        "desc": "通过API获取商品销售属性",
        "status": "coming_soon",
        "params": [
            {"key": "product_ids", "label": "商品ID列表", "type": "text", "placeholder": "多个ID用逗号分隔"},
        ],
    },
    {
        "id": "get_detail",
        "name": "获取商品详情页",
        "icon": "📄",
        "desc": "通过API获取商品详情和图片",
        "status": "coming_soon",
        "params": [
            {"key": "product_ids", "label": "商品ID列表", "type": "text", "placeholder": "多个ID用逗号分隔"},
        ],
    },
]


@tool_bp.route('/api/tools/list', methods=['GET'])
def get_tools():
    """获取工具列表"""
    return jsonify({"tools": TOOLS})


@tool_bp.route('/api/tools/execute', methods=['POST'])
def execute_tool():
    """执行工具任务"""
    data = request.get_json(force=True, silent=True) or {}
    tool_id = data.get('tool_id', '')
    params = data.get('params', {})

    # 验证工具是否存在
    tool = next((t for t in TOOLS if t['id'] == tool_id), None)
    if not tool:
        return jsonify({"error": "tool_not_found", "message": f"未找到工具: {tool_id}"}), 404

    if tool['status'] == 'coming_soon':
        return jsonify({
            "error": "tool_not_available",
            "message": f"「{tool['name']}」尚未接入，敬请期待",
            "tool_id": tool_id,
        })

    # data_import 工具由前端直接调用 /api/upload/data
    if tool_id == 'data_import':
        return jsonify({
            "error": "tool_not_available",
            "message": "「数据导入」请通过前端上传文件",
            "tool_id": tool_id,
        })

    if tool_id in {'product_diagnose', 'main_image_suggest'}:
        denied = reject_legacy_shop_scope('商品工具')
        if denied:
            return denied

    # 分发到具体工具处理器
    try:
        if tool_id == 'main_image_suggest':
            result = _exec_main_image_suggest(params)
        elif tool_id == 'review_reply':
            result = _exec_review_reply(params)
        elif tool_id == 'product_diagnose':
            result = _exec_product_diagnose(params)
        else:
            return jsonify({
                "error": "tool_not_available",
                "message": f"「{tool['name']}」请通过前端上传文件",
                "tool_id": tool_id,
            })
        if isinstance(result, dict) and result.get('code') == 'UNSUPPORTED_SCOPE':
            return jsonify(result), 422
        return jsonify({"result": result, "status": "success"})
    except Exception as e:
        return jsonify({"error": "exec_error", "message": f"执行失败: {str(e)}"}), 500


# ================================================================
#  Feature 15: 评价生成主图建议
# ================================================================

# 常见中文停用词
_STOP_WORDS = set([
    '的', '了', '是', '在', '我', '有', '和', '就', '不', '人', '都', '一', '一个',
    '上', '也', '很', '到', '说', '要', '去', '你', '会', '着', '没有', '看', '好',
    '自己', '这', '他', '她', '它', '们', '那', '些', '什么', '怎么', '如何', '还',
    '可以', '这个', '那个', '比较', '但是', '因为', '所以', '如果', '虽然', '已经',
    '而且', '或者', '以及', '就是', '只是', '应该', '可能', '需要', '真的', '太',
    '非常', '特别', '挺', '蛮', '超', '巨', '贼', '够', '真', '挺', '还是', '又',
    '吧', '啊', '哦', '嗯', '呀', '嘛', '呢', '哈', '啦', '噢', '哇', '么', '地',
    '得', '过', '把', '被', '让', '给', '对', '与', '从', '向', '以', '为', '之',
    '等', '用', '做', '来', '买', '卖', '用', '给', '到', '多', '少', '大', '小',
    '时候', '东西', '东西', '这样', '那样', '这么', '那么', '几', '个', '些', '点',
    '下', '里', '中', '后', '前', '出', '回', '起', '来', '去', '能', '会', '该',
    '想', '觉得', '感觉', '推荐', '收到', '发货', '快递', '物流', '包装', '客服',
    '卖家', '店铺', '第一次', '第二次', '下次', '以后', '之前', '之后', '一直',
    '已经', '开始', '现在', '今天', '昨天', '整体', '总体', '总的来说', '总体来说',
])


def _exec_main_image_suggest(params):
    """评价生成主图建议 - 分析好评提取卖点"""
    product_id = params.get('product_id', '').strip()
    limit = int(params.get('limit', 50) or 50)
    limit = min(max(limit, 10), 200)

    with get_db() as conn:
        # 查询好评数据
        if product_id:
            rows = conn.execute('''
                SELECT content, positive_dims, scenes, rating
                FROM reviews
                WHERE sentiment = 'positive' AND rating >= 4 AND product_id = ?
                ORDER BY rating DESC
                LIMIT ?
            ''', (product_id, limit)).fetchall()
        else:
            rows = conn.execute('''
                SELECT content, positive_dims, scenes, rating
                FROM reviews
                WHERE sentiment = 'positive' AND rating >= 4
                ORDER BY rating DESC
                LIMIT ?
            ''', (limit,)).fetchall()

    if not rows:
        return {
            "suggestions": {
                "core_selling_points": [],
                "scene_suggestions": [],
                "keyword_suggestions": [],
                "optimization_directions": ["暂无足够的好评数据，建议积累更多评价后再进行分析"],
            },
            "review_count": 0,
            "analysis_summary": "未找到符合条件的评价数据，请确认评价数据已导入且包含好评",
        }

    # 1. 提取维度频次（positive_dims 是 JSON 数组）
    dim_counter = Counter()
    for row in rows:
        dims = row['positive_dims'] or '[]'
        try:
            dim_list = json.loads(dims)
            for d in dim_list:
                if d and d.strip():
                    dim_counter[d.strip()] += 1
        except (json.JSONDecodeError, TypeError):
            pass

    core_selling_points = [
        {"name": name, "count": count}
        for name, count in dim_counter.most_common(5)
    ]

    # 2. 提取场景频次（scenes 是 JSON 数组）
    scene_counter = Counter()
    for row in rows:
        scenes = row['scenes'] or '[]'
        try:
            scene_list = json.loads(scenes)
            for s in scene_list:
                if s and s.strip():
                    scene_counter[s.strip()] += 1
        except (json.JSONDecodeError, TypeError):
            pass

    scene_suggestions = [
        {"name": name, "count": count}
        for name, count in scene_counter.most_common(5)
    ]

    # 3. 提取内容关键词频次
    word_counter = Counter()
    for row in rows:
        content = row['content'] or ''
        # 按常见分隔符分词
        words = re.split(r'[，。！？、；：\s,.\-!?;:\(\)（）\[\]【】""''"\'\\~·]+', content)
        for w in words:
            w = w.strip()
            if len(w) >= 2 and w not in _STOP_WORDS:
                word_counter[w] += 1

    keyword_suggestions = [
        {"word": word, "count": count}
        for word, count in word_counter.most_common(10)
    ]

    # 4. 生成优化方向
    optimization_directions = _generate_image_optimization(core_selling_points, scene_suggestions, keyword_suggestions)

    # 生成分析摘要
    top_dims = '、'.join([p['name'] for p in core_selling_points[:3]]) if core_selling_points else '暂无'
    top_scenes = '、'.join([s['name'] for s in scene_suggestions[:3]]) if scene_suggestions else '暂无'
    analysis_summary = (
        f"基于 {len(rows)} 条好评分析，消费者最关注的维度为「{top_dims}」，"
        f"主要使用场景为「{top_scenes}」。"
        f"建议在主图中突出这些核心卖点和使用场景，提升点击率和转化率。"
    )

    return {
        "suggestions": {
            "core_selling_points": core_selling_points,
            "scene_suggestions": scene_suggestions,
            "keyword_suggestions": keyword_suggestions,
            "optimization_directions": optimization_directions,
        },
        "review_count": len(rows),
        "analysis_summary": analysis_summary,
    }


def _generate_image_optimization(selling_points, scenes, keywords):
    """根据分析结果生成主图优化方向"""
    directions = []

    if selling_points:
        top = selling_points[0]['name']
        directions.append(f"首图突出「{top}」核心卖点，使用大字号醒目标注，让买家第一眼看到产品最大优势")

    if len(selling_points) >= 2:
        second = selling_points[1]['name']
        directions.append(f"第二张主图展示「{second}」细节特写，配合使用前后对比或局部放大效果")

    if scenes:
        top_scene = scenes[0]['name']
        directions.append(f"增加「{top_scene}」场景实拍图，让买家直观感受产品在实际使用中的效果")

    if keywords:
        # 从关键词中找适合标题的词
        title_words = [k['word'] for k in keywords[:5] if len(k['word']) <= 6]
        if title_words:
            directions.append(f"主图标题文案建议包含关键词：{'、'.join(title_words[:4])}，提升搜索匹配度")

    if len(selling_points) >= 3:
        third = selling_points[2]['name']
        directions.append(f"增加「{third}」卖点证明图，如检测报告、材质对比、用户好评截图等信任背书")

    if not directions:
        directions.append("建议收集更多评价数据以获得更精准的主图优化建议")

    return directions[:5]


# ================================================================
#  Feature 16: 评价仿写助手
# ================================================================

# 情感关键词库
_POSITIVE_WORDS = ['好', '满意', '喜欢', '不错', '推荐', '棒', '赞', '完美', '惊喜', '超值',
                   '值得', '方便', '实用', '舒服', '漂亮', '好看', '质量好', '很棒', '很好',
                   '爱了', '回购', '好评', '五星', '物超所值', '性价比', '正品']
_NEUTRAL_WORDS = ['一般', '还行', '可以', '凑合', '普通', '正常', '中规中矩', '过得去',
                  '马马虎虎', '还行吧', '就那样', '没什么特别']
_NEGATIVE_WORDS = ['差', '失望', '退货', '烂', '垃圾', '难用', '不好', '太差', '假货',
                   '骗人', '不推荐', '差评', '后悔', '浪费', '不值', '破', '坏了',
                   '掉色', '起球', '脱线', '有味道', '质量差']
_LOGISTICS_WORDS = ['物流', '快递', '包装', '发货', '到货', '配送', '快递员', '送货']
_QUALITY_WORDS = ['质量', '材质', '做工', '面料', '手感', '厚实', '薄', '线头', '色差',
                  '掉色', '起球', '做工精细', '质感', '材料']


def _detect_sentiment(text):
    """检测评价情感倾向"""
    text_lower = text.lower()

    # 检查物流相关
    logistics_count = sum(1 for w in _LOGISTICS_WORDS if w in text_lower)
    if logistics_count >= 2:
        return 'logistics'

    # 检查质量相关
    quality_count = sum(1 for w in _QUALITY_WORDS if w in text_lower)
    if quality_count >= 2:
        return 'quality'

    # 检查正面
    positive_count = sum(1 for w in _POSITIVE_WORDS if w in text_lower)
    # 检查负面
    negative_count = sum(1 for w in _NEGATIVE_WORDS if w in text_lower)
    # 检查中性
    neutral_count = sum(1 for w in _NEUTRAL_WORDS if w in text_lower)

    if negative_count >= 2:
        return 'negative'
    if positive_count >= 2:
        return 'positive'
    if neutral_count >= 1:
        return 'neutral'

    # 默认根据星级判断
    return 'positive'


def _generate_replies(text, style, product_type):
    """根据评价内容和风格生成3条回复"""
    sentiment = _detect_sentiment(text)
    product_label = product_type if product_type else '本产品'

    # 提取评价中的关键特征词
    feature_words = []
    for word in _POSITIVE_WORDS + _QUALITY_WORDS:
        if word in text and len(word) >= 2:
            feature_words.append(word)
    feature_str = '、'.join(feature_words[:3]) if feature_words else '产品'

    if sentiment == 'positive':
        templates = _positive_templates(style, product_label, feature_str)
    elif sentiment == 'neutral':
        templates = _neutral_templates(style, product_label, feature_str)
    elif sentiment == 'negative':
        templates = _negative_templates(style, product_label)
    elif sentiment == 'logistics':
        templates = _logistics_templates(style)
    elif sentiment == 'quality':
        templates = _quality_templates(style, product_label, feature_str)
    else:
        templates = _positive_templates(style, product_label, feature_str)

    return templates


def _positive_templates(style, product_label, feature_str):
    """正面评价回复模板"""
    if style == '专业正式':
        return [
            f"尊敬的顾客，感谢您对{product_label}的认可与好评。我们始终致力于为用户提供高品质的产品与服务，您的满意是我们最大的动力。期待您的再次光临！",
            f"感谢您选择{product_label}并给予五星好评！您提到的{feature_str}正是我们产品的核心优势，我们将继续保持品质，为您提供更优质的体验。",
            f"非常感谢您的详细评价！您的认可是对我们团队最大的鼓励。{product_label}经过严格品控，力求为每一位用户带来满意的使用体验。欢迎随时联系客服了解更多。",
        ]
    elif style == '亲切温暖':
        return [
            f"亲爱的小伙伴，看到您的好评太开心啦！很高兴{product_label}能让您满意，我们会继续努力做出更好的产品哦~ 期待下次再见！",
            f"哇，感谢您的喜欢！看到您对{feature_str}的认可，我们整个团队都超激动~ 您的满意就是我们最大的幸福，记得常来看看新品哦！",
            f"谢谢亲的好评呀！您的每一句夸奖都是我们前进的动力~ {product_label}会一直陪伴您，有任何问题随时找我们，24小时在线等您！",
        ]
    else:  # 简洁高效
        return [
            f"感谢好评！很高兴{product_label}能让您满意，我们会继续保持品质。如有任何问题，随时联系客服。",
            f"感谢您的认可！{feature_str}正是我们的产品亮点。期待您的再次光临，祝您生活愉快！",
            f"谢谢五星好评！您的满意是我们最大的追求。{product_label}品质有保障，欢迎随时回购~",
        ]


def _neutral_templates(style, product_label, feature_str):
    """中性评价回复模板"""
    if style == '专业正式':
        return [
            f"感谢您的评价与反馈。我们重视每一位用户的意见，{product_label}将持续优化改进。如您有任何建议，欢迎随时联系客服团队，我们将竭诚为您服务。",
            f"感谢您选择{product_label}并留下宝贵意见。我们已记录您的反馈，产品团队将持续改进。期待能为您提供更满意的体验。",
            f"感谢您的中肯评价。我们理解您对{feature_str}的期望，产品团队正在持续优化中。如有任何疑问，欢迎联系客服获取专业解答。",
        ]
    elif style == '亲切温暖':
        return [
            f"亲，感谢您的真实反馈~ 我们会继续努力让{product_label}变得更好！如果有什么不满意的地方，随时找客服聊聊，我们一定帮您解决~",
            f"收到您的评价啦，感谢亲的宝贵意见！我们会认真对待每一条反馈，争取下次让您给五星好评哦~ 有问题随时联系我们！",
            f"谢谢亲的评价~ 虽然还有进步空间，但我们会加油的！{product_label}会越来越好，期待下次能给您带来惊喜~",
        ]
    else:  # 简洁高效
        return [
            f"感谢反馈！我们会持续优化{product_label}，如有问题可随时联系客服处理。",
            f"感谢您的评价，您的建议对我们很重要。{product_label}将持续改进，期待下次给您更好的体验。",
            f"收到反馈，感谢！我们会不断优化产品和服务，有任何问题欢迎随时联系。",
        ]


def _negative_templates(style, product_label):
    """负面评价回复模板"""
    if style == '专业正式':
        return [
            f"尊敬的顾客，对于给您带来的不佳体验，我们深表歉意。我们非常重视您的反馈，已安排专人跟进处理。请您联系客服提供订单信息，我们将尽快为您妥善处理，给您一个满意的解决方案。",
            f"非常抱歉未能达到您的期望。{product_label}始终以品质为先，您的反馈已转交品质部门核查。请联系在线客服，我们将为您提供退换货或补偿方案，确保您的权益得到保障。",
            f"对于此次不愉快的购物体验，我们诚挚致歉。您的反馈对我们改进产品至关重要。请通过客服通道联系我们，我们将第一时间为您处理，并赠送优惠券作为补偿。",
        ]
    elif style == '亲切温暖':
        return [
            f"亲，真的非常抱歉给您带来了不好的体验T_T 我们特别重视您的反馈，已经马上安排处理啦！请联系客服小姐姐，我们一定给您一个满意的解决方案，求给个机会弥补~",
            f"看到您的评价我们好难过呀... 对不起没能让您满意！请务必联系客服，我们会尽全力帮您解决问题，退换货都可以安排的，一定要让我们弥补一下呀~",
            f"亲亲，真的很抱歉！您的反馈我们已经收到并紧急处理中~ 请联系客服告诉我们具体情况，我们一定给您一个满意的结果，下次一定让您开开心心购物！",
        ]
    else:  # 简洁高效
        return [
            f"非常抱歉给您带来不佳体验。请联系客服提供订单号，我们将尽快为您处理退换或补偿。",
            f"抱歉未能让您满意。请通过在线客服联系我们，我们将第一时间为您解决问题并给予补偿。",
            f"收到您的反馈，深表歉意。请联系客服处理，我们承诺为您妥善解决，保障您的权益。",
        ]


def _logistics_templates(style):
    """物流相关评价回复模板"""
    if style == '专业正式':
        return [
            f"感谢您的反馈。关于物流配送方面的问题，我们已与物流合作伙伴沟通协调。如包裹有损坏或配送异常，请联系客服提供订单号，我们将立即为您处理。",
            f"感谢您对物流的评价。我们已记录您的反馈，将持续优化发货和配送流程。如需查询物流信息或处理配送问题，请随时联系客服团队。",
            f"感谢您的评价。我们理解物流体验对购物满意度的重要影响，已加强包装标准和物流合作方管理。如有任何配送问题，请联系客服跟进处理。",
        ]
    elif style == '亲切温暖':
        return [
            f"亲，感谢反馈物流情况~ 我们已经跟快递公司沟通啦，会努力让包裹更快更安全地到达您手中！下次购物一定给您更好的物流体验~",
            f"收到啦，物流方面我们会继续加油优化的！感谢亲的理解和耐心等待~ 有任何快递问题随时找客服，我们帮您跟进！",
            f"谢谢亲的反馈~ 我们一直在努力提升发货速度和包装质量呢！下次一定给您更棒的收货体验，期待您的再次光临~",
        ]
    else:  # 简洁高效
        return [
            f"感谢反馈物流情况，我们已加强包装和配送管理。如有问题请联系客服处理。",
            f"收到反馈，我们将持续优化物流体验。配送问题可随时联系客服跟进。",
            f"感谢评价，物流方面我们会继续改进。如有异常请联系客服，我们将尽快处理。",
        ]


def _quality_templates(style, product_label, feature_str):
    """质量相关评价回复模板"""
    if style == '专业正式':
        return [
            f"感谢您对{product_label}品质的关注。我们的产品均经过严格质检流程，{feature_str}方面有专业保障。如您对产品品质有任何疑问，欢迎联系客服获取详细的产品信息。",
            f"感谢您的评价。{product_label}在品质管控方面有着严格标准，每一件产品都经过多道工序检验。如您发现任何品质问题，请联系客服，我们将按售后政策为您处理。",
            f"感谢您对产品质量的反馈。{product_label}始终坚持品质为先的原则，所有产品均有质量保证。如有任何品质疑虑，请联系客服团队，我们将为您提供专业的解答和售后保障。",
        ]
    elif style == '亲切温暖':
        return [
            f"亲，感谢您关注{product_label}的品质~ 我们的产品都是精心挑选和严格质检的呢！{feature_str}方面您可以放心~ 有任何问题随时找客服聊聊哦！",
            f"谢谢亲对品质的认可呀！{product_label}在质量上可是下了很大功夫的~ 我们希望每一件产品都能让您满意，有任何品质问题随时联系我们！",
            f"亲亲，品质是我们的生命线呢！{product_label}每一件都经过严格检查才发出的~ 您放心使用，有问题随时找客服，我们一定负责到底！",
        ]
    else:  # 简洁高效
        return [
            f"感谢反馈！{product_label}品质有严格保障，如有问题请联系客服处理售后。",
            f"收到评价，{product_label}经过严格质检。品质问题可联系客服，我们将按售后政策处理。",
            f"感谢关注品质！{product_label}质量有保障，如有任何疑虑欢迎联系客服咨询。",
        ]


def _exec_review_reply(params):
    """评价仿写助手 - 生成回复模板"""
    review_text = params.get('review_text', '').strip()
    reply_style = params.get('reply_style', '专业正式').strip()
    product_type = params.get('product_type', '').strip()

    if not review_text:
        return {"error": "请输入评价内容"}

    if reply_style not in ('专业正式', '亲切温暖', '简洁高效'):
        reply_style = '专业正式'

    sentiment = _detect_sentiment(review_text)
    replies = _generate_replies(review_text, reply_style, product_type)

    sentiment_map = {
        'positive': '正面',
        'neutral': '中性',
        'negative': '负面',
        'logistics': '物流相关',
        'quality': '品质相关',
    }

    return {
        "replies": [
            {"style": f"{reply_style} - 版本{i+1}", "content": r}
            for i, r in enumerate(replies)
        ],
        "detected_sentiment": sentiment,
        "detected_sentiment_label": sentiment_map.get(sentiment, '未知'),
    }


# ================================================================
#  Feature 17: 商品详情页诊断
# ================================================================

def _exec_product_diagnose(params):
    """商品详情页诊断 - 综合分析商品数据"""
    product_id = params.get('product_id', '').strip()
    if not product_id:
        return {"error": "请输入商品ID"}

    with get_db() as conn:
        # 1. 查询商品基本信息
        product = conn.execute('''
            SELECT product_id, title, category, tier, style, scene, status
            FROM products WHERE product_id = ?
        ''', (product_id,)).fetchone()

        if not product:
            return {"error": f"未找到商品: {product_id}"}

        product_info = {
            "product_id": product['product_id'],
            "title": product['title'] or '未知商品',
            "category": product['category'] or '-',
            "tier": product['tier'] or '-',
            "style": product['style'] or '-',
        }

        # 2. 查询最新月度数据
        monthly = conn.execute('''
            SELECT * FROM monthly_data
            WHERE product_id = ?
            ORDER BY month DESC LIMIT 1
        ''', (product_id,)).fetchone()

        monthly_data = dict(monthly) if monthly else {}

        # 3. 查询健康评分
        health = conn.execute('''
            SELECT * FROM product_health
            WHERE product_id = ?
            ORDER BY period DESC LIMIT 1
        ''', (product_id,)).fetchone()

        health_data = dict(health) if health else {}

        # 4. 查询评价汇总
        review_stats = conn.execute('''
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN sentiment = 'positive' THEN 1 ELSE 0 END) as positive_count,
                SUM(CASE WHEN sentiment = 'neutral' THEN 1 ELSE 0 END) as neutral_count,
                SUM(CASE WHEN sentiment = 'negative' THEN 1 ELSE 0 END) as negative_count,
                AVG(rating) as avg_rating
            FROM reviews WHERE product_id = ?
        ''', (product_id,)).fetchone()

        review_data = dict(review_stats) if review_stats else {}

    # 计算各维度诊断
    diagnostics = []

    # --- 主图吸引力 ---
    click_rate = monthly_data.get('click_rate', 0) or 0
    industry_ctr = 0.05  # 行业平均点击率基准
    if click_rate > 0:
        ctr_score = min(100, max(0, int((click_rate / industry_ctr) * 50)))
    else:
        ctr_score = 50  # 无数据给中间值

    if ctr_score >= 80:
        ctr_level, ctr_suggestion = '优秀', '主图点击率表现优异，建议保持当前主图策略，定期A/B测试新方案'
    elif ctr_score >= 60:
        ctr_level, ctr_suggestion = '良好', '主图点击率尚可，建议尝试优化主图文案和排版，突出差异化卖点'
    elif ctr_score >= 40:
        ctr_level, ctr_suggestion = '待优化', '主图点击率偏低，建议重新设计主图，突出核心卖点，增加场景化展示'
    else:
        ctr_level, ctr_suggestion = '需改进', '主图点击率明显低于行业水平，建议全面重新设计主图，参考竞品优秀案例'

    diagnostics.append({
        "area": "主图吸引力",
        "score": ctr_score,
        "level": ctr_level,
        "suggestion": ctr_suggestion,
        "metric": f"点击率: {click_rate*100:.1f}%" if click_rate > 0 else "点击率: 暂无数据",
    })

    # --- 标题优化 ---
    search_ratio = monthly_data.get('search_ratio', 0) or 0
    if search_ratio > 0:
        title_score = min(100, max(0, int(search_ratio * 200)))
    else:
        title_score = 50

    if title_score >= 80:
        title_level, title_suggestion = '优秀', '搜索流量占比优秀，标题关键词覆盖面广，建议保持并持续监控'
    elif title_score >= 60:
        title_level, title_suggestion = '良好', '搜索流量占比良好，可尝试补充长尾关键词，拓展搜索覆盖面'
    elif title_score >= 40:
        title_level, title_suggestion = '待优化', '搜索流量占比较低，建议优化标题关键词，增加品类热门搜索词'
    else:
        title_level, title_suggestion = '需改进', '搜索流量严重不足，建议重新规划标题SEO策略，覆盖核心搜索词'

    diagnostics.append({
        "area": "标题优化",
        "score": title_score,
        "level": title_level,
        "suggestion": title_suggestion,
        "metric": f"搜索占比: {search_ratio*100:.1f}%" if search_ratio > 0 else "搜索占比: 暂无数据",
    })

    # --- 价格竞争力 ---
    conversion = monthly_data.get('payment_conversion', 0) or 0
    avg_order_value = monthly_data.get('avg_order_value', 0) or 0
    # 综合转化率和客单价判断
    conv_score = min(100, max(0, int(conversion * 500))) if conversion > 0 else 50
    price_score = int(conv_score * 0.7 + 50 * 0.3)  # 综合评分

    if price_score >= 80:
        price_level, price_suggestion = '优秀', '转化率和客单价表现优秀，价格策略合理，建议维持当前定价'
    elif price_score >= 60:
        price_level, price_suggestion = '良好', '转化率表现良好，可尝试优化促销策略提升客单价'
    elif price_score >= 40:
        price_level, price_suggestion = '待优化', '转化率偏低，建议检查价格竞争力，考虑促销活动或组合优惠'
    else:
        price_level, price_suggestion = '需改进', '转化率严重偏低，建议重新评估定价策略，参考竞品价格区间调整'

    diagnostics.append({
        "area": "价格竞争力",
        "score": price_score,
        "level": price_level,
        "suggestion": price_suggestion,
        "metric": f"转化率: {conversion*100:.1f}%, 客单价: ¥{avg_order_value:.0f}" if conversion > 0 else "转化率: 暂无数据",
    })

    # --- 详情页内容 ---
    avg_stay = monthly_data.get('avg_stay_duration', 0) or 0
    bounce_rate = monthly_data.get('bounce_rate', 0) or 0
    cart_rate = monthly_data.get('cart_rate', 0) or 0

    # 停留时长评分（假设60秒为优秀）
    stay_score = min(100, max(0, int((avg_stay / 60) * 80))) if avg_stay > 0 else 50
    # 跳失率评分（越低越好）
    bounce_score = min(100, max(0, int((1 - bounce_rate) * 100))) if bounce_rate > 0 and bounce_rate < 1 else 50
    # 加购率评分
    cart_score = min(100, max(0, int(cart_rate * 500))) if cart_rate > 0 else 50

    detail_score = int(stay_score * 0.3 + bounce_score * 0.3 + cart_score * 0.4)

    if detail_score >= 80:
        detail_level, detail_suggestion = '优秀', '详情页内容质量高，用户停留时间长、加购率高，建议保持并微调优化'
    elif detail_score >= 60:
        detail_level, detail_suggestion = '良好', '详情页表现良好，可增加买家秀、视频等互动内容提升转化'
    elif detail_score >= 40:
        detail_level, detail_suggestion = '待优化', '详情页需优化，建议增加卖点展示、使用场景图、对比图等提升吸引力'
    else:
        detail_level, detail_suggestion = '需改进', '详情页效果差，建议全面重构详情页，增加视频、买家秀、FAQ等模块'

    diagnostics.append({
        "area": "详情页内容",
        "score": detail_score,
        "level": detail_level,
        "suggestion": detail_suggestion,
        "metric": f"停留: {avg_stay:.0f}秒, 跳失率: {bounce_rate*100:.1f}%, 加购率: {cart_rate*100:.1f}%" if avg_stay > 0 else "详情页数据: 暂无",
    })

    # --- 评价管理 ---
    total_reviews = review_data.get('total', 0) or 0
    positive_count = review_data.get('positive_count', 0) or 0
    avg_rating = review_data.get('avg_rating', 0) or 0

    if total_reviews > 0:
        positive_rate = positive_count / total_reviews
        review_mgmt_score = min(100, max(0, int(positive_rate * 100)))
    else:
        review_mgmt_score = 50

    if review_mgmt_score >= 80:
        review_level, review_suggestion = '优秀', '好评率优秀，建议引导更多买家晒图评价，积累优质买家秀'
    elif review_mgmt_score >= 60:
        review_level, review_suggestion = '良好', '好评率良好，建议关注中差评并及时回复，提升整体评价质量'
    elif review_mgmt_score >= 40:
        review_level, review_suggestion = '待优化', '好评率偏低，建议加强品质管控，主动联系差评用户解决问题'
    else:
        review_level, review_suggestion = '需改进', '好评率严重偏低，需立即排查产品质量问题，制定评价改善计划'

    diagnostics.append({
        "area": "评价管理",
        "score": review_mgmt_score,
        "level": review_level,
        "suggestion": review_suggestion,
        "metric": f"好评率: {positive_rate*100:.1f}%, 平均评分: {avg_rating:.1f}" if total_reviews > 0 else "评价数据: 暂无",
    })

    # --- 推广效率 ---
    ad_roi = monthly_data.get('ad_roi', 0) or 0
    ppc = monthly_data.get('keyword_ppc', 0) or 0
    paid_ratio = monthly_data.get('paid_ratio', 0) or 0

    if ad_roi > 0:
        roi_score = min(100, max(0, int(ad_roi * 25)))  # ROI=4为满分
    else:
        roi_score = 50

    if ppc > 0:
        ppc_score = min(100, max(0, int((3 / max(ppc, 0.1)) * 30)))  # PPC=3元为基准
    else:
        ppc_score = 50

    ad_score = int(roi_score * 0.6 + ppc_score * 0.4)

    if ad_score >= 80:
        ad_level, ad_suggestion = '优秀', '推广效率优秀，ROI表现突出，建议维持当前投放策略并适当扩大规模'
    elif ad_score >= 60:
        ad_level, ad_suggestion = '良好', '推广效率良好，可优化关键词出价和人群定向，提升ROI'
    elif ad_score >= 40:
        ad_level, ad_suggestion = '待优化', '推广效率偏低，建议优化投放关键词，降低PPC，提升精准度'
    else:
        ad_level, ad_suggestion = '需改进', '推广效率严重不足，建议重新规划推广策略，暂停低效计划，聚焦高转化词'

    diagnostics.append({
        "area": "推广效率",
        "score": ad_score,
        "level": ad_level,
        "suggestion": ad_suggestion,
        "metric": f"ROI: {ad_roi:.1f}, PPC: ¥{ppc:.1f}" if ad_roi > 0 else "推广数据: 暂无",
    })

    # 计算综合评分
    overall_score = int(sum(d['score'] for d in diagnostics) / len(diagnostics))

    # 优先行动（取分数最低的3个）
    priority_actions = sorted(diagnostics, key=lambda x: x['score'])[:3]
    priority_list = [
        {"area": p['area'], "action": p['suggestion'], "score": p['score']}
        for p in priority_actions
    ]

    return {
        "product_info": product_info,
        "diagnostics": diagnostics,
        "overall_score": overall_score,
        "priority_actions": priority_list,
    }


@tool_bp.route('/api/tools/tasks', methods=['GET'])
def get_tasks():
    """获取任务列表（骨架）"""
    return jsonify({"tasks": []})
