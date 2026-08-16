"""Seed an idempotent, cross-domain TM 1.0 demonstration dataset."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sqlite3
import sys
from contextlib import closing
from datetime import date, datetime, timedelta


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

PRODUCTS = [
    ('DEMO-001', '云感轻暖四季被', '家居家纺', 'A', '基础款', '卧室', '2024-09-18', 'active', '林晓'),
    ('DEMO-002', '凉感抑菌夏被', '家居家纺', 'A', '季节款', '卧室', '2024-11-08', 'active', '林晓'),
    ('DEMO-003', '纯棉磨毛床笠', '家居家纺', 'B', '基础款', '卧室', '2024-06-20', 'active', '周然'),
    ('DEMO-004', '酒店风四件套', '家居家纺', 'A', '形象款', '婚庆', '2024-03-12', 'active', '周然'),
    ('DEMO-005', '儿童防螨枕芯', '母婴家纺', 'B', '增长款', '儿童房', '2025-02-15', 'active', '许宁'),
    ('DEMO-006', '大豆纤维冬被', '家居家纺', 'B', '季节款', '卧室', '2024-08-10', 'active', '许宁'),
    ('DEMO-007', '乳胶护颈枕', '家居家纺', 'C', '测试款', '卧室', '2025-09-01', 'active', '何薇'),
    ('DEMO-008', '旅行隔脏睡袋', '旅行用品', 'C', '清仓款', '旅行', '2024-01-10', 'inactive', '何薇'),
]

CHANNELS = [('万相台', 'campaign-wxt', 'unit-smart'), ('直通车', 'campaign-ztc', 'unit-keyword'),
            ('引力魔方', 'campaign-yltf', 'unit-crowd'), ('淘宝客', 'campaign-tbk', 'unit-affiliate')]


def _dates(start: date, end: date):
    cursor = start
    while cursor <= end:
        yield cursor
        cursor += timedelta(days=1)


def _batch(batch_id, source_type, filename, total_rows, start, end):
    digest = hashlib.sha256(batch_id.encode('utf-8')).hexdigest()
    quality = json.dumps({
        'total_rows': total_rows, 'valid_rows': total_rows, 'invalid_rows': 0,
        'date_range': {'start': start, 'end': end}, 'duplicate_keys': 0,
        'conclusion': '通过',
    }, ensure_ascii=False)
    return (batch_id, source_type, filename, digest, 'completed', total_rows, total_rows, 0,
            total_rows, 0, quality, f'{end} 08:30:00', f'{end} 08:31:00')


def seed_demo_data(database_path=None):
    from db import init_db

    target = os.path.abspath(database_path or os.path.join(ROOT, 'data', 'dashboard.db'))
    init_db(target)
    start = date(2025, 1, 1)
    end = date(2026, 8, 12)
    product_end = date(2026, 8, 12)
    days = list(_dates(start, end))

    with closing(sqlite3.connect(target)) as connection:
        connection.execute('PRAGMA foreign_keys = ON')
        connection.executemany(
            '''INSERT INTO products (product_id,title,category,tier,style,scene,list_date,status,manager,remark)
               VALUES (?,?,?,?,?,?,?,?,?,'演示数据')
               ON CONFLICT(product_id) DO UPDATE SET title=excluded.title,category=excluded.category,
                 tier=excluded.tier,style=excluded.style,scene=excluded.scene,list_date=excluded.list_date,
                 status=excluded.status,manager=excluded.manager,remark=excluded.remark,updated_at=CURRENT_TIMESTAMP''',
            PRODUCTS,
        )

        batches = [
            _batch('demo-product-batch', 'product_day', 'demo_product_day.xlsx', len(days) * len(PRODUCTS), start.isoformat(), end.isoformat()),
            _batch('demo-store-batch', 'store_day', 'demo_store_day.xlsx', len(days), start.isoformat(), end.isoformat()),
            _batch('demo-promotion-batch', 'promotion_product_day', 'demo_promotion_product_day.xlsx', len(days) * len(CHANNELS), start.isoformat(), end.isoformat()),
        ]
        connection.executemany(
            '''INSERT INTO import_batches (id,source_type,source_filename,source_hash,status,total_rows,valid_rows,
                 invalid_rows,inserted_count,updated_count,quality_summary,created_at,completed_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(id) DO UPDATE SET source_hash=excluded.source_hash,status='completed',
                 total_rows=excluded.total_rows,valid_rows=excluded.valid_rows,invalid_rows=0,
                 inserted_count=excluded.inserted_count,quality_summary=excluded.quality_summary,
                 completed_at=excluded.completed_at''', batches,
        )

        daily_rows = []
        for day_index, day in enumerate(days):
            weekday = 0.82 if day.weekday() in (0, 1) else 1.08 if day.weekday() in (5, 6) else 1.0
            season = 1 + 0.18 * math.sin((day.timetuple().tm_yday - 40) / 365 * math.tau)
            campaign = 1.45 if (day.month, day.day) in {(6, 18), (11, 11), (12, 12)} else 1.0
            for index, product in enumerate(PRODUCTS):
                growth = 1 + day_index / max(len(days), 1) * (0.22 - index * 0.025)
                base = 900 + index * 260
                payment = round(base * weekday * season * campaign * growth, 2)
                refund_rate = 0.035 + index * 0.008
                refund = round(payment * refund_rate, 2)
                visitors = max(40, int(payment / (7.5 + index * .7)))
                buyers = max(4, int(visitors * (0.055 + index * .004)))
                spend = round(payment * (0.08 + index * .012), 2)
                daily_rows.append((product[0], day.isoformat(), payment, refund, payment-refund, buyers,
                                   visitors, visitors*3, int(visitors*.32), int(visitors*.20), int(visitors*.18),
                                   int(visitors*.30), buyers/visitors, .12, .08, .31, 48+index*3, spend,
                                   payment/spend if spend else 0, buyers, payment/buyers, 'demo_product_day.xlsx',
                                   payment/visitors, int(visitors*.12), int(visitors*.08), buyers/max(int(visitors*.32), 1), int(visitors*.32), int(visitors*.12)))
        connection.executemany(
            '''INSERT INTO daily_data (shop_id,product_id,date,payment_amount,refund_amount,net_sales,payment_qty,ipv,pv,
                 search_ipv,recommend_ipv,paid_ipv,organic_ipv,payment_conversion,cart_rate,fav_rate,bounce_rate,
                 avg_stay_duration,ad_spend,ad_roi,buyers,avg_order_value,data_source,uv_value,cart_qty,fav_users,
                 search_conversion,search_visitors,cart_users)
               VALUES ('default',?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(shop_id,product_id,date) DO UPDATE SET payment_amount=excluded.payment_amount,
                 refund_amount=excluded.refund_amount,net_sales=excluded.net_sales,payment_qty=excluded.payment_qty,
                 ipv=excluded.ipv,pv=excluded.pv,search_ipv=excluded.search_ipv,
                 recommend_ipv=excluded.recommend_ipv,paid_ipv=excluded.paid_ipv,
                 organic_ipv=excluded.organic_ipv,payment_conversion=excluded.payment_conversion,
                 cart_rate=excluded.cart_rate,fav_rate=excluded.fav_rate,bounce_rate=excluded.bounce_rate,
                 avg_stay_duration=excluded.avg_stay_duration,ad_spend=excluded.ad_spend,
                 ad_roi=excluded.ad_roi,buyers=excluded.buyers,avg_order_value=excluded.avg_order_value,
                 data_source=excluded.data_source,uv_value=excluded.uv_value,cart_qty=excluded.cart_qty,
                 fav_users=excluded.fav_users,search_conversion=excluded.search_conversion,
                 search_visitors=excluded.search_visitors,cart_users=excluded.cart_users''', daily_rows,
        )
        connection.execute("DELETE FROM import_batch_changes WHERE batch_id = 'demo-product-batch'")
        connection.executemany(
            '''INSERT INTO import_batch_changes
               (batch_id, table_name, business_key, previous_row, written_by)
               VALUES ('demo-product-batch', 'daily_data', ?, NULL, 'demo-product-batch')''',
            [(f'{row[0]}|{row[1]}',) for row in daily_rows],
        )

        rows_by_date = {}
        for row in daily_rows:
            rows_by_date.setdefault(row[1], []).append(row)
        store_rows = []
        for day in days:
            values = rows_by_date[day.isoformat()]
            payment = round(sum(row[2] for row in values), 2)
            refund = round(sum(row[3] for row in values), 2)
            visitors = int(sum(row[6] for row in values) * .72)
            buyers = int(sum(row[19] for row in values) * .88)
            returning = int(buyers * (.28 + (day.month % 4) * .025))
            spend = round(sum(row[17] for row in values), 2)
            store_rows.append(('default', day.isoformat(), payment, refund, visitors, buyers, returning, spend, 'demo-store-batch'))
        connection.executemany(
            '''INSERT INTO store_daily_facts (shop_id,date,payment_amount,successful_refund_amount,product_visitors,
                 payment_buyers,returning_payment_buyers,ad_spend,source_batch_id) VALUES (?,?,?,?,?,?,?,?,?)
               ON CONFLICT(shop_id,date) DO NOTHING''', store_rows,
        )

        promotion_rows = []
        for day_index, day in enumerate(days):
            for index, (channel, campaign_id, unit_id) in enumerate(CHANNELS):
                product_id = PRODUCTS[(day_index + index) % len(PRODUCTS)][0]
                spend = round(160 + index * 65 + 35 * math.sin(day_index / 14 + index), 2)
                roi = 3.2 + index * .65
                deal = round(spend * roi, 2)
                impressions = 12000 + index * 3500 + day_index % 900
                clicks = int(impressions * (.026 + index * .004))
                buyers = max(1, int(clicks * (.045 + index * .006)))
                promotion_rows.append(('default', day.isoformat(), channel, campaign_id, unit_id, product_id,
                                       spend, deal, impressions, clicks, buyers, round(deal*.68, 2),
                                       round(deal*.32, 2), 'demo-promotion-batch'))
        connection.executemany(
            '''INSERT INTO promotion_daily_facts (shop_id,date,channel,campaign_id,unit_id,product_id,ad_spend,
                 attributed_payment_amount,impressions,clicks,payment_buyers,direct_payment_amount,
                 indirect_payment_amount,source_batch_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(shop_id,date,channel,campaign_id,unit_id,product_id) DO UPDATE SET
                 ad_spend=excluded.ad_spend,attributed_payment_amount=excluded.attributed_payment_amount,
                 impressions=excluded.impressions,clicks=excluded.clicks,payment_buyers=excluded.payment_buyers,
                 direct_payment_amount=excluded.direct_payment_amount,indirect_payment_amount=excluded.indirect_payment_amount,
                 source_batch_id=excluded.source_batch_id''', promotion_rows,
        )

        # Derived demo grains used by compare, product analysis, paid-detail,
        # health and review screens. Keep these rows explicitly demo-owned so
        # re-seeding never overwrites imported or manually maintained data.
        connection.execute("DELETE FROM weekly_data WHERE product_id LIKE 'DEMO-%'")
        connection.execute("DELETE FROM monthly_data WHERE product_id LIKE 'DEMO-%'")
        connection.execute("DELETE FROM paid_detail WHERE product_id LIKE 'DEMO-%'")
        connection.execute("DELETE FROM product_health WHERE product_id LIKE 'DEMO-%'")
        connection.execute("DELETE FROM reviews WHERE product_id LIKE 'DEMO-%'")

        by_product = {product[0]: [] for product in PRODUCTS}
        for row in daily_rows:
            by_product[row[0]].append(row)
        weekly_rows, monthly_rows, paid_rows, health_rows = [], [], [], []
        for product_index, product in enumerate(PRODUCTS):
            pid = product[0]
            rows = by_product[pid]
            weeks = {}
            months = {}
            for row in rows:
                day = date.fromisoformat(row[1])
                week_start = day - timedelta(days=day.weekday())
                weeks.setdefault(week_start.isoformat(), []).append(row)
                months.setdefault(day.strftime('%Y-%m'), []).append(row)
            for week, values in weeks.items():
                payment = sum(v[2] for v in values); refund = sum(v[3] for v in values)
                visitors = sum(v[6] for v in values); buyers = sum(v[19] for v in values)
                spend = sum(v[17] for v in values)
                weekly_rows.append((pid, week, round(payment, 2), round(refund, 2), round(payment-refund, 2),
                    visitors, sum(v[7] for v in values), sum(v[8] for v in values), sum(v[9] for v in values),
                    sum(v[10] for v in values), sum(v[11] for v in values), buyers/max(visitors, 1),
                    sum(v[13] for v in values)/len(values), sum(v[14] for v in values)/len(values),
                    sum(v[15] for v in values)/len(values), sum(v[16] for v in values)/len(values),
                    round(spend, 2), round(payment/max(spend, 1), 3), .08 + product_index*.01,
                    int(buyers*.22), int(buyers*.04), .03, payment/max(buyers, 1),
                    4 + product_index, 'demo weekly trend', 'demo weekly action', 'demo_product_day.xlsx'))
            for month, values in months.items():
                payment = sum(v[2] for v in values); refund = sum(v[3] for v in values)
                visitors = sum(v[6] for v in values); buyers = sum(v[19] for v in values)
                spend = sum(v[17] for v in values); clicks = sum(v[8] for v in values)
                monthly_rows.append((pid, month, round(payment,2), round(refund,2), round(payment-refund,2),
                    visitors, sum(v[7] for v in values), payment/max(visitors,1), sum(v[8] for v in values),
                    sum(v[8] for v in values)/max(visitors,1), buyers/max(visitors,1),
                    sum(v[13] for v in values)/len(values), sum(v[14] for v in values)/len(values),
                    sum(v[15] for v in values)/len(values), sum(v[16] for v in values)/len(values),
                    round(spend,2), round(payment/max(spend,1),3), spend/max(payment,1), refund/max(payment,1),
                    .05, .03, buyers, payment/max(buyers,1), int(visitors*.15), int(visitors*.12),
                    int(visitors*.08), int(visitors*.06), .034, 82-product_index*2, 'demo_product_day.xlsx'))
            latest = rows[-14:]
            payment = sum(v[2] for v in latest); spend = sum(v[17] for v in latest); refund = sum(v[3] for v in latest)
            health = round(72 + product_index*2 + (payment / max(spend, 1)) * 2 - refund/max(payment,1)*50, 1)
            level = 'excellent' if health >= 85 else 'healthy' if health >= 70 else 'watch'
            health_rows.append((pid, '2026-08', health*.92, health*.88, health*.95, 100-refund/max(payment,1)*100,
                health*.9, health*.84, health, level, health*.9, 100-spend/max(payment,1)*100,
                health*.95, 100-refund/max(payment,1)*100, 72, 68, 70, 74, 77, 71, 69, 73, '[]'))
            paid_rows.append((pid, '2026-08', int(sum(v[7] for v in latest)), int(sum(v[8] for v in latest)), round(spend,2),
                sum(v[8] for v in latest)/max(sum(v[7] for v in latest),1), spend/max(sum(v[8] for v in latest),1),
                spend/max(sum(v[7] for v in latest),1)*1000, round(payment,2), int(sum(v[19] for v in latest)),
                round(payment*.68,2), round(payment*.32,2), round(payment/max(spend,1),2), int(sum(v[12] for v in latest)),
                sum(v[12] for v in latest)/max(sum(v[6] for v in latest),1), int(sum(v[24] for v in latest)), int(sum(v[19] for v in latest)*.3)))
        connection.executemany('''INSERT INTO weekly_data
            (product_id,week_start,payment_amount,refund_amount,net_sales,ipv,pv,search_ipv,recommend_ipv,paid_ipv,organic_ipv,
             payment_conversion,cart_rate,fav_rate,bounce_rate,avg_stay_duration,ad_spend,ad_roi,repurchase_rate,repurchase_users,
             cross_sell_qty,cross_sell_rate,avg_order_value,category_width,action_1,action_2,data_source)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', weekly_rows)
        connection.executemany('''INSERT INTO monthly_data
            (product_id,month,payment_amount,refund_amount,net_sales,visitors,page_views,uv_value,search_visitors,search_ratio,
             payment_conversion,cart_rate,fav_rate,bounce_rate,avg_stay_duration,ad_spend,ad_roi,paid_ratio,refund_rate,
             repurchase_rate,cross_sell_rate,buyers,avg_order_value,payment_qty,cart_qty,fav_users,cart_users,click_rate,score,data_source)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', monthly_rows)
        connection.executemany('''INSERT INTO paid_detail
            (product_id,date_range,impressions,clicks,cost,ctr,cpc,cpm,total_gmv,total_orders,direct_gmv,indirect_gmv,roi,cart_adds,cart_rate,favs,new_buyers)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', paid_rows)
        connection.executemany('''INSERT INTO product_health
            (product_id,period,sales_score,conversion_score,roi_score,refund_score,growth_score,review_score,health_score,health_level,
             gmv_change_score,ad_spend_change_score,roi_change_score,refund_rate_score,cart_rate_score,search_ratio_score,new_customer_cost_score,
             direct_cart_cost_score,total_cart_cost_score,repurchase_rate_score,cross_sell_rate_score,search_ctr_vs_industry_score,alert_dimensions)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', health_rows)

        review_rows = []
        review_text = [('面料柔软，尺寸合适，第二次回购。', 5, 'positive'), ('发货很快，颜色和详情页一致。', 5, 'positive'),
                       ('枕芯比预期略薄，但睡感还可以。', 4, 'neutral'), ('包装有轻微压痕，客服已处理。', 3, 'negative')]
        for i in range(32):
            pid = PRODUCTS[i % len(PRODUCTS)][0]; text_value, rating, sentiment = review_text[i % len(review_text)]
            review_rows.append((pid, (date(2026,8,12)-timedelta(days=i%28)).isoformat(), text_value, rating, f'买家{i+1:03d}', 1, sentiment,
                                json.dumps(['质量','舒适度'] if rating >= 4 else ['包装'], ensure_ascii=False),
                                json.dumps(['包装'] if rating == 3 else [], ensure_ascii=False), json.dumps(['卧室'], ensure_ascii=False), int(i%3==0), 'demo-review'))
        connection.executemany('''INSERT INTO reviews
            (product_id,review_date,content,rating,reviewer,is_effective,sentiment,positive_dims,negative_dims,scenes,has_image,source)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''', review_rows)

        # Legacy operating-workspace context consumed by the manage/toolbox
        # APIs. Demo-owned rows are refreshed on every run.
        for table, predicate in (
            ('shop_targets', "remark LIKE '演示%'") , ('product_targets', "remark LIKE '演示%'") ,
            ('alerts', "title LIKE '演示%'") , ('task_items', "title LIKE '演示%'") ,
            ('user_kpis', "user_name LIKE '演示%'") , ('product_notes', "note LIKE '演示%'") ,
            ('product_tags', "tag LIKE '演示%'") , ('review_summary', "product_id LIKE 'DEMO-%'") ,
            ('operation_actions', "action_type LIKE '演示%'") ,
        ):
            connection.execute(f'DELETE FROM {table} WHERE {predicate}')

        connection.executemany(
            '''INSERT INTO shop_targets
               (period,target_gsv,target_ad_spend,target_ad_ratio,target_conversion,target_refund_rate,remark)
               VALUES (?,?,?,?,?,?,?)
               ON CONFLICT(period) DO UPDATE SET target_gsv=excluded.target_gsv,target_ad_spend=excluded.target_ad_spend,
                 target_ad_ratio=excluded.target_ad_ratio,target_conversion=excluded.target_conversion,
                 target_refund_rate=excluded.target_refund_rate,remark=excluded.remark''',
            [('2026-08',880000,69000,.078,.060,.040,'演示月度经营目标'),('2026-W33',205000,16500,.081,.058,.042,'演示周度经营目标'),('2026-08-12',28500,2200,.077,.061,.040,'演示日度经营目标')])
        connection.executemany(
            '''INSERT INTO product_targets (product_id,tier,period,target_gsv,target_ad_spend,target_ad_ratio,remark)
               VALUES (?,?,?,?,?,?,?)
               ON CONFLICT(product_id,period) DO UPDATE SET tier=excluded.tier,target_gsv=excluded.target_gsv,
                 target_ad_spend=excluded.target_ad_spend,target_ad_ratio=excluded.target_ad_ratio,remark=excluded.remark''',
            [(p[0],p[3],'2026-08',98000+i*12500,round((98000+i*12500)*(.075+i*.006),2),.075+i*.006,'演示商品月目标') for i,p in enumerate(PRODUCTS)])
        connection.executemany(
            '''INSERT INTO alerts (alert_date,alert_type,severity,title,detail,metric_name,current_value,target_value,period,dismissed)
               VALUES (?,?,?,?,?,?,?,?,?,?)''',
            [('2026-08-12','roi_drop','warning','演示｜引力魔方费比偏高','近 7 日 ROI 低于商品目标，建议收缩低效单元。','roi',2.84,3.2,'2026-08-12',0),('2026-08-12','refund_rate','info','演示｜夏被退款率上升','凉感抑菌夏被退款率较上周上升 0.6 个百分点。','refund_rate',.046,.040,'2026-08-12',0)])
        connection.executemany('''INSERT INTO task_items (title,description,status,priority,assignee,due_date) VALUES (?,?,?,?,?,?)''', [
            ('演示｜复核凉感夏被退款原因','查看最近 20 条中差评并更新商品动作。','todo','P1','林晓','2026-08-14'),
            ('演示｜调整引力魔方低效单元','将 ROI 低于 3.2 的单元预算下调 10%。','doing','P1','周然','2026-08-15'),
            ('演示｜准备秋季四件套素材','完成婚庆场景主图和标题 A/B 方案。','todo','P2','许宁','2026-08-18')])
        kpis = [('演示｜林晓',320000,298600,'B+'),('演示｜周然',285000,301400,'A'),('演示｜许宁',210000,196800,'B+')]
        connection.executemany('''INSERT INTO user_kpis (user_name,period,target_gmv,actual_gmv,achievement_rate,rating) VALUES (?,?,?,?,?,?)''',
            [(n,'2026-08',t,a,round(a/t,4),r) for n,t,a,r in kpis])
        connection.executemany("INSERT INTO product_notes (product_id,note,created_by) VALUES (?,?,?)", [(p,n,'demo-seed') for p,n in [
            ('DEMO-001','演示｜主图卖点突出保暖和四季可用，当前作为稳定主推款。'),('DEMO-002','演示｜季节性明显，八月重点关注退款原因与投放费比。'),('DEMO-004','演示｜婚庆场景素材准备中，配合秋季节点观察转化。'),('DEMO-008','演示｜清仓款，保持低库存与低预算，不新增备货。')]])
        connection.executemany("INSERT INTO product_tags (product_id,tag,is_auto) VALUES (?,?,0)", [(p[0],f'演示｜{p[3]}层') for p in PRODUCTS])
        connection.executemany('''INSERT INTO review_summary (product_id,analysis_date,total_reviews,positive_rate,negative_rate,effective_rate,top_positive_dims,top_negative_dims,top_scenes) VALUES (?,?,?,?,?,?,?,?,?)''', [
            (p[0],'2026-08-12',32,round(.78-i*.015,4),round(.14+i*.015,4),.97,json.dumps(['舒适度','质量'],ensure_ascii=False),json.dumps(['包装'] if i in (1,4) else [],ensure_ascii=False),json.dumps(['卧室','日常使用'],ensure_ascii=False)) for i,p in enumerate(PRODUCTS)])
        connection.executemany('''INSERT INTO operation_actions (product_id,action_date,action_type,action_detail,before_payment,before_visitors,before_conversion,before_roi,after_payment,after_visitors,after_conversion,after_roi,payment_change,conversion_change,roi_change,effectiveness_score) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', [
            ('DEMO-001','2026-07-01','演示｜换主图','强调四季可用与保暖卖点',1260,4200,.052,4.1,1475,4680,.061,4.7,.171,.009,.146,86),
            ('DEMO-002','2026-08-01','演示｜调整推广','下调低效渠道出价 12%',1820,6100,.047,3.1,1930,6250,.050,3.8,.060,.003,.226,78),
            ('DEMO-008','2026-06-01','演示｜清仓减价','清仓价下调 15%',430,1250,.032,2.7,610,1510,.041,3.9,.419,.009,.444,92)])

        stages = ['mature', 'growth', 'mature', 'breakout', 'growth', 'mature', 'new', 'clearance']
        seasons = ['stable', 'spring_summer', 'stable', 'promotion_driven', 'stable', 'autumn_winter', None, 'stable']
        lifecycle_rows = [(product[0], stages[index], None, 0, seasons[index], 'system' if seasons[index] else None,
                           'high' if index < 6 else 'low', f'基于 {len(days)} 个连续有效日与趋势评估',
                           '2026-09-01', 1, 'demo-seed') for index, product in enumerate(PRODUCTS)]
        connection.executemany(
            '''INSERT INTO lifecycle_profiles (product_id,recommended_stage,manual_stage,stage_locked,seasonal_attribute,
                 seasonal_source,confidence,rationale,next_key_date,version,updated_by) VALUES (?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(product_id) DO UPDATE SET recommended_stage=excluded.recommended_stage,
                 seasonal_attribute=excluded.seasonal_attribute,seasonal_source=excluded.seasonal_source,
                 confidence=excluded.confidence,rationale=excluded.rationale,next_key_date=excluded.next_key_date,
                 updated_by=excluded.updated_by''', lifecycle_rows,
        )
        connection.execute("DELETE FROM lifecycle_history WHERE product_id LIKE 'DEMO-%'")
        connection.executemany(
            '''INSERT INTO lifecycle_history
               (product_id, recommended_stage, manual_stage, seasonal_attribute, locked, reason, operator, version)
               VALUES (?, ?, NULL, ?, 0, '演示｜系统完成首次生命周期评估', 'demo-seed', 1)''',
            [(row[0], row[1], row[4]) for row in lifecycle_rows],
        )

        actions = [
            ('demo-action-1','DEMO-001','increase_sales','提升主推款转化','换主图','替换为利益点更清晰的主图','payment_amount',.12,'pending_review','2026-07-01','2026-07-01',14,'林晓',1260,1475,.171,'观察窗口完整，排除大促日',1,'主图卖点更明确','转化和净销售同步提升','扩大到相似商品','运营主管','2026-07-20',4),
            ('demo-action-2','DEMO-002','reduce_cost','控制旺季投放费比','调整推广','下调低效渠道出价 12%','expense_ratio',-.08,'observing','2026-08-01','2026-08-01',14,'林晓',.16,None,None,'观察至 2026-08-15',None,None,None,None,None,None,3),
            ('demo-action-3','DEMO-003','increase_sales','提升连带成交','调整 SKU','增加床笠与枕套组合 SKU','payment_amount',.1,'executing','2026-08-10','2026-08-10',10,'周然',980,None,None,None,None,None,None,None,None,None,2),
            ('demo-action-4','DEMO-004','increase_sales','准备秋季婚庆场景','换标题','强化酒店风与婚庆关键词','payment_amount',.15,'pending_review','2026-08-18',None,14,'周然',None,None,None,None,None,None,None,None,None,None,1),
            ('demo-action-5','DEMO-005','increase_conversion','改善儿童枕详情转化','换主图','增加防螨检测与年龄段信息','payment_conversion_rate',.08,'blocked','2026-08-08',None,14,'许宁',None,None,None,None,None,None,None,None,None,None,2),
            ('demo-action-6','DEMO-008','clearance','清理旅行睡袋库存','减价','清仓价下调 15%','payment_amount',.2,'completed','2026-06-01','2026-06-01',14,'何薇',430,610,.419,'完整观察窗口',1,'价格弹性明显','清仓效率符合预期','保持库存阈值','运营主管','2026-06-20',5),
        ]
        connection.executemany(
            '''INSERT INTO product_actions (id,product_id,purpose_type,purpose_note,action_type,action_detail,target_metric,
                 expected_change,status,planned_at,executed_at,observer_window_days,assigned_to,before_metric_value,
                 after_metric_value,result_change,calculation_note,review_effective,review_reason,review_conclusion,
                 review_next_action,reviewed_by,reviewed_at,version)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(id) DO UPDATE SET status=excluded.status,executed_at=excluded.executed_at,
                 after_metric_value=excluded.after_metric_value,result_change=excluded.result_change,
                 calculation_note=excluded.calculation_note,review_effective=excluded.review_effective,
                 review_reason=excluded.review_reason,review_conclusion=excluded.review_conclusion,
                 review_next_action=excluded.review_next_action,reviewed_by=excluded.reviewed_by,
                 reviewed_at=excluded.reviewed_at,version=excluded.version''', actions,
        )
        connection.execute("DELETE FROM product_action_history WHERE action_id LIKE 'demo-action-%'")
        history = []
        for action in actions:
            action_id, status, version = action[0], action[8], action[-1]
            history.append((action_id, None, 'draft', '创建演示动作', 'demo-seed', 1))
            if status != 'draft': history.append((action_id, 'draft', status, '演示状态推进', 'demo-seed', version))
        connection.executemany(
            '''INSERT INTO product_action_history (action_id,from_status,to_status,detail,operator,version)
               VALUES (?,?,?,?,?,?)''', history,
        )

        reviews = [('day','2026-08-12','日销售保持平稳，推广费比可控','主推款增长，低效渠道需继续收缩','跟进夏被素材与渠道预算','运营主管'),
                   ('week','2026-W33','周目标完成度良好','自然流量增长，退款率稳定','复制高转化主图并观察七天','运营主管'),
                   ('month','2026-07','月度净销售超目标','主推款和季节款贡献增长','八月控制费比并准备秋季新品','店长')]
        connection.executemany(
            '''INSERT INTO period_reviews (period_type,period_key,summary,conclusions,next_actions,reviewer)
               VALUES (?,?,?,?,?,?) ON CONFLICT(period_type,period_key) DO NOTHING''', reviews,
        )

        goal_year = 2026
        annual_target = 8_800_000.0
        connection.execute(
            '''INSERT INTO goal_versions (year,version,annual_target) VALUES (?,1,?)
               ON CONFLICT(year) DO NOTHING''',
            (goal_year, annual_target),
        )
        goal_days = list(_dates(date(goal_year, 1, 1), date(goal_year, 12, 31)))
        cents = round(annual_target * 100)
        base_cents, remainder = divmod(cents, len(goal_days))
        goals = [(goal_year, day.isoformat(), (base_cents + (1 if i < remainder else 0)) / 100, 'recommended', '演示年度目标', 1) for i, day in enumerate(goal_days)]
        connection.executemany(
            '''INSERT INTO daily_goals (year,goal_date,target_amount,source,reason,version) VALUES (?,?,?,?,?,?)
               ON CONFLICT(year,goal_date) DO NOTHING''', goals,
        )
        goal_version = connection.execute(
            'SELECT version, annual_target FROM goal_versions WHERE year = ?', (goal_year,)
        ).fetchone()
        if goal_version == (1, annual_target):
            connection.execute(
                "DELETE FROM goal_adjustments WHERE year = ? AND reason LIKE '演示%'", (goal_year,)
            )
            connection.execute(
                '''INSERT INTO goal_adjustments
                   (year, period_type, period_key, target_amount, operator, reason, version)
                   VALUES (?, 'month', '2026-08', 880000, 'demo-seed', '演示｜旺季月目标人工校准', 1)''',
                (goal_year,),
            )
            connection.execute(
                '''INSERT INTO goal_locks (year, period_type, period_key, version)
                   VALUES (?, 'month', '2026-08', 1)
                   ON CONFLICT(year, period_type, period_key) DO NOTHING''',
                (goal_year,),
            )
        connection.commit()

        counts = {}
        for table in ('products','daily_data','store_daily_facts','promotion_daily_facts','product_actions',
                      'product_action_history','lifecycle_profiles','period_reviews','goal_versions','daily_goals','import_batches',
                      'weekly_data','monthly_data','paid_detail','product_health','reviews'):
            counts[table] = connection.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
    return counts


def main():
    parser = argparse.ArgumentParser(description='写入隔离的 TM 1.0 演示数据库。')
    target_group = parser.add_mutually_exclusive_group()
    target_group.add_argument('--database', help='明确指定目标 SQLite 路径')
    target_group.add_argument(
        '--demo-database',
        nargs='?',
        const=os.path.join(ROOT, 'data', 'demo', 'dashboard.db'),
        help='写入演示数据库；不带路径时使用 data/demo/dashboard.db',
    )
    parser.add_argument(
        '--allow-production-database',
        action='store_true',
        help='明确允许写入 data/dashboard.db；仅限受控恢复演练',
    )
    args = parser.parse_args()
    target = args.database or args.demo_database
    if not target:
        parser.error('必须显式指定 --demo-database 或 --database')
    target_path = os.path.abspath(target)
    production_path = os.path.abspath(os.path.join(ROOT, 'data', 'dashboard.db'))
    if target_path == production_path and not args.allow_production_database:
        parser.error('拒绝直接写入生产数据库；如确需受控演练，请显式添加 --allow-production-database')
    print(json.dumps(seed_demo_data(target_path), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
