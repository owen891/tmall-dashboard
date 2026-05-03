"""
示例数据生成脚本
用于初始化海贝海数据仪表盘2.0的示例数据
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.models.dashboard_models import (
    DailyMetrics, MonthlyTarget, TrafficStructure,
    KeywordMetrics, FunnelMetrics, ProductRanking,
    ProductProfit, InventoryStatus, CampaignMetrics,
    AIPLStats, AlertRecord
)
from app.models.command_tower import (
    TaskItem, UserKPI
)

def random_float(min_val, max_val, decimals=2):
    import random
    return round(random.uniform(min_val, max_val), decimals)

def random_int(min_val, max_val):
    import random
    return random.randint(min_val, max_val)

def generate_sample_data():
    db = SessionLocal()
    
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        current_month = datetime.now().strftime("%Y-%m")
        
        print("开始生成示例数据...")
        
        dm = DailyMetrics(
            date=today,
            gmv=random_float(80000, 150000),
            gmv_yesterday=random_float(75000, 140000),
            total_uv=random_int(5000, 15000),
            new_uv=random_int(2000, 8000),
            conversion_rate=random_float(0.02, 0.05),
            avg_order_value=random_float(150, 350),
            uv_value=random_float(15, 35),
            gross_margin=random_float(0.35, 0.55),
            ad_spend=random_float(5000, 15000),
            ad_roi=random_float(2.5, 5.5),
            refund_rate=random_float(0.01, 0.04)
        )
        db.add(dm)
        
        ts = TrafficStructure(
            date=today,
            total_uv=random_int(5000, 15000),
            search_uv=random_int(2000, 6000),
            recommend_uv=random_int(1500, 5000),
            ztc_uv=random_int(500, 2000),
            wxt_uv=random_int(300, 1500),
            search_pct=random_float(35, 50),
            recommend_pct=random_float(25, 40),
            paid_pct=random_float(15, 30),
            free_pct=random_float(55, 70)
        )
        db.add(ts)
        
        mt = MonthlyTarget(
            month=current_month,
            target_gmv=random_float(2000000, 3500000),
            actual_gmv=random_float(800000, 1500000),
            completion_rate=random_float(30, 55),
            target_a_product=random_float(1000000, 2000000),
            target_b_product=random_float(800000, 1500000)
        )
        db.add(mt)
        
        for i in range(20):
            km = KeywordMetrics(
                date=today,
                keyword=f"关键词{i+1}",
                popularity=random_int(100, 1000),
                impressions=random_int(10000, 100000),
                clicks=random_int(500, 5000),
                ctr=random_float(0.01, 0.08),
                cvr=random_float(0.02, 0.1),
                cat_avg_ctr=random_float(0.02, 0.05),
                cat_avg_cvr=random_float(0.03, 0.08),
                efficacy=random_float(0.5, 2.0),
                category="流量词" if i % 3 == 0 else ("蓝海词" if i % 3 == 1 else "废词"),
                gmv=random_float(1000, 10000),
                cost=random_float(100, 1000),
                roi=random_float(1.5, 8.0)
            )
            db.add(km)
        
        fm = FunnelMetrics(
            date=today,
            impression_uv=random_int(50000, 200000),
            click_uv=random_int(3000, 15000),
            cart_uv=random_int(800, 4000),
            pay_buyers=random_int(150, 800),
            bounce_uv=random_int(1000, 5000),
            total_uv=random_int(5000, 15000),
            ctr=random_float(0.02, 0.08),
            cart_rate=random_float(0.15, 0.35),
            cvr=random_float(0.03, 0.1),
            bounce_rate=random_float(0.15, 0.4)
        )
        db.add(fm)
        
        for i in range(30):
            pr = ProductRanking(
                product_id=f"P{1000+i}",
                title=f"商品{i+1}号",
                sales_30d=random_int(10000, 500000),
                sales_rank=i+1,
                prev_rank=random_int(1, 50),
                rank_change=random_int(-5, 5),
                ipv=random_int(1000, 20000),
                ctr=random_float(0.02, 0.1),
                cvr=random_float(0.02, 0.15),
                search_weight=random_float(0.3, 0.95),
                product_type="A" if i < 15 else "B",
                tier=["引流款", "利润款", "潜力款"][i % 3]
            )
            db.add(pr)
            
            pp = ProductProfit(
                product_id=f"P{1000+i}",
                title=f"商品{i+1}号",
                gmv=random_float(10000, 100000),
                purchase_cost=random_float(5000, 60000),
                freight=random_float(200, 1500),
                ad_cost=random_float(500, 5000),
                net_profit=random_float(1000, 20000),
                ad_ratio=random_float(0.05, 0.35),
                roi=random_float(2.0, 8.0),
                gross_margin=random_float(0.25, 0.5),
                break_even_roi=random_float(1.5, 3.0),
                target_profit=random_float(2000, 15000),
                suggestion=["正常运营", "加大推广", "优化成本"][i % 3]
            )
            db.add(pp)
        
        for i in range(20):
            days_remaining = random_float(2, 30)
            alert_level = "red" if days_remaining < 3 else ("orange" if days_remaining < 7 else ("blue" if days_remaining < 14 else "green"))
            
            inv = InventoryStatus(
                sku_id=f"SKU{2000+i}",
                product_id=f"P{1000+i}",
                sku_name=f"SKU-{i+1}",
                current_stock=random_int(10, 500),
                avg_daily_sales_7d=random_float(5, 50),
                avg_daily_sales_30d=random_float(8, 45),
                days_remaining=days_remaining,
                safety_stock=random_int(20, 100),
                lead_time_days=random_int(5, 14),
                buffer_days=random_int(2, 5),
                in_transit=random_int(0, 200),
                suggested_order=random_int(50, 300),
                open_stock=random_int(100, 600),
                close_stock=random_int(80, 550),
                turnover_days=random_float(15, 60),
                alert_level=alert_level
            )
            db.add(inv)
        
        for i, ctype in enumerate(["ztc", "wxt", "tk"]):
            cm = CampaignMetrics(
                campaign_id=f"C{1000+i}",
                campaign_name=f"{ctype.upper()}计划{i+1}",
                campaign_type=ctype,
                cost=random_float(1000, 10000),
                impressions=random_int(50000, 500000),
                clicks=random_int(2000, 20000),
                conversions=random_int(50, 500),
                campaign_gmv=random_float(5000, 50000),
                roi=random_float(2.0, 8.0),
                cpa=random_float(15, 80),
                cpm=random_float(10, 50),
                ppc=random_float(0.5, 3.0),
                status="running"
            )
            db.add(cm)
        
        aipl = AIPLStats(
            date=today,
            a_count=random_int(50000, 200000),
            i_count=random_int(20000, 80000),
            p_count=random_int(5000, 20000),
            l_count=random_int(1000, 5000),
            a_to_i=random_float(0.2, 0.5),
            i_to_p=random_float(0.1, 0.35),
            p_to_l=random_float(0.05, 0.2)
        )
        db.add(aipl)
        
        for i in range(5):
            ar = AlertRecord(
                rule_id=random_int(1, 4),
                title=f"告警事件{i+1}",
                detail=f"检测到异常指标，需要处理",
                current_value=random_float(1.5, 8.0),
                threshold_value=random_float(2.0, 5.0),
                status=["pending", "handling", "resolved"][i % 3],
                handler="张三" if i % 2 == 0 else "",
                level=["urgent", "warning"][i % 2]
            )
            db.add(ar)
        
        tasks = [
            TaskItem(task_title="优化直通车投放策略", task_type="优化", priority="P0", assignee="张三", status="todo", due_date=(datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d")),
            TaskItem(task_title="处理滞销商品", task_type="清理", priority="P1", assignee="李四", status="in_progress", due_date=(datetime.now() + timedelta(days=5)).strftime("%Y-%m-%d")),
            TaskItem(task_title="分析本周GMV数据", task_type="分析", priority="P2", assignee="王五", status="done", due_date=(datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")),
            TaskItem(task_title="更新库存预警规则", task_type="维护", priority="P1", assignee="张三", status="todo", due_date=(datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")),
        ]
        for t in tasks:
            db.add(t)
        
        for i in range(3):
            uk = UserKPI(
                username=["张三", "李四", "王五"][i],
                period=current_month,
                target_gmv=random_float(300000, 500000),
                actual_gmv=random_float(150000, 400000),
                actual_task_count=random_int(10, 20),
                actual_operation_count=random_int(60, 120),
                performance_rating=["A", "B", "C"][i],
                comment="表现良好"
            )
            db.add(uk)
        
        db.commit()
        print("✅ 示例数据生成成功！")
        
    except Exception as e:
        db.rollback()
        print(f"❌ 生成失败: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    generate_sample_data()
