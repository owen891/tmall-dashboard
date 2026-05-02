#!/usr/bin/env python3
"""
六边形指挥塔数据库迁移脚本
创建所有新的表结构
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.core.database import engine, Base
from app.models.command_tower import (
    WxtCampaign,
    WxtDailyMetrics,
    DmpCrowd,
    DmpCampaignLink,
    CrowdAssetStats,
    ABTest,
    ABTestVariant,
    ABTestMetrics,
    ABTestAnalysis,
    SOPTemplate,
    CampaignProject,
    TaskItem,
    UserKPI,
    SmartAlertRule,
    SmartAlert,
    SupplyChainData,
    InventoryAlert,
    CampaignProjectSOPLink,
    UserDailyPerformance
)


def create_tables():
    """创建所有新表"""
    print("正在创建六边形指挥塔数据库表...")
    
    # 导入所有模型后创建表
    Base.metadata.create_all(bind=engine, tables=[
        WxtCampaign.__table__,
        WxtDailyMetrics.__table__,
        DmpCrowd.__table__,
        DmpCampaignLink.__table__,
        CrowdAssetStats.__table__,
        ABTest.__table__,
        ABTestVariant.__table__,
        ABTestMetrics.__table__,
        ABTestAnalysis.__table__,
        SOPTemplate.__table__,
        CampaignProject.__table__,
        TaskItem.__table__,
        UserKPI.__table__,
        SmartAlertRule.__table__,
        SmartAlert.__table__,
        SupplyChainData.__table__,
        InventoryAlert.__table__,
        CampaignProjectSOPLink.__table__,
        UserDailyPerformance.__table__,
    ])
    
    print("✅ 数据库表创建完成！")
    
    # 列出已创建的表
    from sqlalchemy import inspect
    inspector = inspect(engine)
    print("\n已创建的表:")
    for table_name in inspector.get_table_names():
        if any(keyword in table_name for keyword in [
            'wxt', 'dmp', 'crowd', 'ab_test', 'sop', 'campaign', 'task',
            'user_kpi', 'smart_alert', 'supply', 'inventory'
        ]):
            print(f"  - {table_name}")


def main():
    print("=" * 50)
    print("六边形指挥塔 - 数据库迁移")
    print("=" * 50)
    create_tables()
    print("\n迁移完成！")


if __name__ == "__main__":
    main()

