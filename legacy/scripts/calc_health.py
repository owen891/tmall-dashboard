import sys
import os
import json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db import get_connection

# 12 dimensions with weights
DIMENSIONS = [
    {'key': 'gmv_change', 'weight': 0.15, 'label': 'GSV环比', 'higher_better': True},
    {'key': 'ad_spend_change', 'weight': 0.08, 'label': '总推广花费环比', 'higher_better': False},
    {'key': 'roi_change', 'weight': 0.10, 'label': '直接ROI环比', 'higher_better': True},
    {'key': 'refund_rate', 'weight': 0.10, 'label': '退款率', 'higher_better': False},
    {'key': 'cart_rate', 'weight': 0.08, 'label': '加购率', 'higher_better': True},
    {'key': 'search_ratio', 'weight': 0.07, 'label': '引潜比', 'higher_better': True},
    {'key': 'new_customer_cost', 'weight': 0.07, 'label': '拉新成本', 'higher_better': False},
    {'key': 'direct_cart_cost', 'weight': 0.05, 'label': '直接加购成本', 'higher_better': False},
    {'key': 'total_cart_cost', 'weight': 0.05, 'label': '总加购成本', 'higher_better': False},
    {'key': 'repurchase_rate', 'weight': 0.08, 'label': '复购率', 'higher_better': True},
    {'key': 'cross_sell_rate', 'weight': 0.07, 'label': '连带率', 'higher_better': True},
    {'key': 'search_ctr_vs_industry', 'weight': 0.10, 'label': '搜索点击率vs行业', 'higher_better': True},
]

def calc_health_scores(period=None, dimension='monthly'):
    """计算商品健康度评分（12维度加权百分位）"""
    conn = get_connection()

    if dimension == 'monthly':
        table, date_col = 'monthly_data', 'month'
    else:
        table, date_col = 'weekly_data', 'week_start'

    # 获取所有有数据的商品当期指标
    if dimension == 'monthly':
        visitors_col = 'visitors'
    else:
        visitors_col = 'ipv'

    products = conn.execute(f'''
        SELECT product_id,
               payment_amount,
               ad_spend,
               ad_roi,
               refund_rate,
               cart_rate,
               search_ratio,
               payment_conversion,
               repurchase_rate,
               cross_sell_rate,
               buyers,
               payment_qty,
               cart_qty,
               {visitors_col} as visitors,
               COALESCE(click_rate, 0) as click_rate,
               COALESCE(industry_ctr, 0) as industry_ctr
        FROM {table}
        WHERE {date_col} = ?
    ''', (period,)).fetchall()

    if not products:
        conn.close()
        return 0

    product_ids = [p[0] for p in products]
    pid_set = set(product_ids)

    # 获取上一期数据用于计算环比
    prev_period = None
    if dimension == 'monthly':
        try:
            parts = period.split('-')
            year, month = int(parts[0]), int(parts[1])
            month -= 1
            if month == 0:
                month = 12
                year -= 1
            prev_period = f"{year}-{month:02d}"
        except Exception:
            pass
    elif dimension == 'weekly':
        # 周度：取上一个周起始日期
        try:
            from datetime import datetime, timedelta
            week_dt = datetime.strptime(period, '%Y-%m-%d')
            prev_dt = week_dt - timedelta(days=7)
            prev_period = prev_dt.strftime('%Y-%m-%d')
        except Exception:
            pass

    prev_data = {}
    if prev_period:
        prev_rows = conn.execute(f'''
            SELECT product_id, payment_amount, ad_spend, ad_roi
            FROM {table}
            WHERE {date_col} = ?
        ''', (prev_period,)).fetchall()
        for r in prev_rows:
            prev_data[r[0]] = {
                'payment_amount': r[1] or 0,
                'ad_spend': r[2] or 0,
                'ad_roi': r[3] or 0,
            }

    # 计算每个商品的12维度原始值
    product_metrics = {}
    for p in products:
        pid = p[0]
        cur_gsv = p[1] or 0
        cur_ad_spend = p[2] or 0
        cur_roi = p[3] or 0
        cur_refund_rate = p[4] or 0
        cur_cart_rate = p[5] or 0
        cur_search_ratio = p[6] or 0
        cur_conversion = p[7] or 0
        cur_repurchase = p[8] or 0
        cur_cross_sell = p[9] or 0
        cur_buyers = p[10] or 0
        cur_qty = p[11] or 0
        cur_cart_qty = p[12] or 0
        cur_visitors = p[13] or 0
        cur_click_rate = p[14] or 0
        cur_industry_ctr = p[15] or 0

        prev = prev_data.get(pid, {})
        prev_gsv = prev.get('payment_amount', 0)
        prev_ad_spend = prev.get('ad_spend', 0)
        prev_roi = prev.get('ad_roi', 0)

        # 1. GSV环比
        gmv_change = (cur_gsv - prev_gsv) / prev_gsv if prev_gsv > 0 else 0.5

        # 2. 总推广花费环比 (越低越好)
        ad_spend_change = (cur_ad_spend - prev_ad_spend) / prev_ad_spend if prev_ad_spend > 0 else 0.0

        # 3. 直接ROI环比
        roi_change = (cur_roi - prev_roi) / prev_roi if prev_roi > 0 else 0.0

        # 4. 退款率
        refund_rate_val = cur_refund_rate

        # 5. 加购率
        cart_rate_val = cur_cart_rate

        # 6. 引潜比
        search_ratio_val = cur_search_ratio

        # 7. 拉新成本 (推广花费/买家数)
        new_customer_cost = cur_ad_spend / cur_buyers if cur_buyers > 0 else 0

        # 8. 直接加购成本 (推广花费/加购数)
        direct_cart_cost = cur_ad_spend / cur_cart_qty if cur_cart_qty > 0 else 0

        # 9. 总加购成本 (推广花费/访客数 * 加购率)
        total_cart_cost = (cur_ad_spend / cur_visitors * cur_cart_rate) if cur_visitors > 0 else 0

        # 10. 复购率
        repurchase_rate_val = cur_repurchase

        # 11. 连带率
        cross_sell_rate_val = cur_cross_sell

        # 12. 搜索点击率vs行业 (click_rate - industry_ctr)
        search_ctr_vs_industry = cur_click_rate - cur_industry_ctr

        product_metrics[pid] = {
            'gmv_change': gmv_change,
            'ad_spend_change': ad_spend_change,
            'roi_change': roi_change,
            'refund_rate': refund_rate_val,
            'cart_rate': cart_rate_val,
            'search_ratio': search_ratio_val,
            'new_customer_cost': new_customer_cost,
            'direct_cart_cost': direct_cart_cost,
            'total_cart_cost': total_cart_cost,
            'repurchase_rate': repurchase_rate_val,
            'cross_sell_rate': cross_sell_rate_val,
            'search_ctr_vs_industry': search_ctr_vs_industry,
        }

    # 过滤掉GSV为0的商品
    valid_pids = [pid for pid in product_ids if (product_metrics[pid].get('gmv_change', 0) != 0 or any(p[1] > 0 for p in products if p[0] == pid))]

    # 对每个维度计算百分位
    def percentile_rank(val, all_vals, higher_better=True):
        """计算百分位排名 (0-100)"""
        if not all_vals:
            return 50
        sorted_vals = sorted(all_vals)
        n = len(sorted_vals)
        # 处理相同值
        count_le = sum(1 for v in sorted_vals if v <= val)
        count_lt = sum(1 for v in sorted_vals if v < val)
        rank = (count_le + count_lt) / 2
        pct = rank / n * 100
        if not higher_better:
            pct = 100 - pct
        return round(pct)

    # 收集每个维度的所有值
    dim_all_vals = {}
    for dim in DIMENSIONS:
        key = dim['key']
        vals = []
        for pid in product_ids:
            v = product_metrics[pid].get(key)
            if v is not None:
                vals.append(v)
        dim_all_vals[key] = vals

    # 计算每个商品每个维度的百分位得分
    product_scores = {}
    for pid in product_ids:
        scores = {}
        for dim in DIMENSIONS:
            key = dim['key']
            val = product_metrics[pid].get(key)
            pct = percentile_rank(val, dim_all_vals[key], dim['higher_better'])
            scores[key] = pct
        product_scores[pid] = scores

    # 计算加权健康分和预警维度
    updated = 0
    for pid in product_ids:
        scores = product_scores[pid]
        health = 0
        for dim in DIMENSIONS:
            health += scores[dim['key']] * dim['weight']
        health = round(health, 1)

        if health >= 80:
            level = '优秀'
        elif health >= 60:
            level = '良好'
        elif health >= 40:
            level = '关注'
        else:
            level = '预警'

        # 检测预警维度（bottom 20%）
        alert_dims = []
        for dim in DIMENSIONS:
            key = dim['key']
            if scores[key] < 20:
                alert_dims.append({
                    'key': key,
                    'label': dim['label'],
                    'score': scores[key],
                })

        # 保留旧字段兼容性
        sales_score = scores.get('gmv_change', 50)
        conv_score = scores.get('cart_rate', 50)
        roi_score = scores.get('roi_change', 50)
        refund_score = scores.get('refund_rate', 50)
        growth_score = scores.get('gmv_change', 50)
        review_score = 50  # 评价维度保留默认

        conn.execute('''
            INSERT OR REPLACE INTO product_health (
                product_id, period,
                sales_score, conversion_score, roi_score, refund_score, growth_score, review_score,
                gmv_change_score, ad_spend_change_score, roi_change_score,
                refund_rate_score, cart_rate_score, search_ratio_score,
                new_customer_cost_score, direct_cart_cost_score, total_cart_cost_score,
                repurchase_rate_score, cross_sell_rate_score, search_ctr_vs_industry_score,
                health_score, health_level, alert_dimensions
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            pid, period,
            sales_score, conv_score, roi_score, refund_score, growth_score, review_score,
            scores.get('gmv_change', 50),
            scores.get('ad_spend_change', 50),
            scores.get('roi_change', 50),
            scores.get('refund_rate', 50),
            scores.get('cart_rate', 50),
            scores.get('search_ratio', 50),
            scores.get('new_customer_cost', 50),
            scores.get('direct_cart_cost', 50),
            scores.get('total_cart_cost', 50),
            scores.get('repurchase_rate', 50),
            scores.get('cross_sell_rate', 50),
            scores.get('search_ctr_vs_industry', 50),
            health, level,
            json.dumps(alert_dims, ensure_ascii=False),
        ))

        updated += 1

    conn.commit()
    conn.close()
    return updated

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='计算商品健康度评分')
    parser.add_argument('--period', type=str, required=True, help='周期（如 2026-04）')
    parser.add_argument('--dimension', type=str, default='monthly', choices=['monthly', 'weekly'], help='数据维度')
    args = parser.parse_args()

    count = calc_health_scores(period=args.period, dimension=args.dimension)
    print(f"健康度计算完成: {count} 个商品已更新")
