#!/usr/bin/env python3
"""
数据库索引优化脚本
为常用查询字段添加索引，提升查询性能
"""
import sqlite3
import os
import sys

# 获取正确的数据库路径
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SCRIPT_DIR)
DB_PATH = os.path.join(BACKEND_DIR, "data", "dashboard.db")


def add_indexes():
    """添加索引"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    indexes_to_create = [
        # products 表索引
        ("idx_products_category", "products", "category"),
        ("idx_products_status", "products", "status"),
        ("idx_products_tier", "products", "tier"),
        ("idx_products_manager", "products", "manager"),
        ("idx_products_list_date", "products", "list_date"),

        # daily_data 表索引
        ("idx_daily_product_date", "daily_data", "product_id, date"),
        ("idx_daily_date", "daily_data", "date"),

        # weekly_data 表索引
        ("idx_weekly_product", "weekly_data", "product_id"),
        ("idx_weekly_week", "weekly_data", "week"),

        # monthly_data 表索引
        ("idx_monthly_product", "monthly_data", "product_id"),
        ("idx_monthly_month", "monthly_data", "month"),

        # alerts 表索引
        ("idx_alerts_product", "alerts", "product_id"),
        ("idx_alerts_severity", "alerts", "severity"),
        ("idx_alerts_status", "alerts", "status"),

        # reviews 表索引
        ("idx_reviews_product", "reviews", "product_id"),
        ("idx_reviews_date", "reviews", "review_date"),

        # operation_actions 表索引
        ("idx_operations_product", "operation_actions", "product_id"),
        ("idx_operations_date", "operation_actions", "action_date"),
        ("idx_operations_type", "operation_actions", "action_type"),
    ]

    created = []
    skipped = []
    failed = []

    for index_name, table, columns in indexes_to_create:
        try:
            # 检查索引是否已存在
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name=?",
                (index_name,)
            )
            if cursor.fetchone():
                skipped.append(index_name)
                print(f"⏭️  跳过: {index_name} (已存在)")
                continue

            # 创建索引
            column_list = ", ".join(columns.split(", "))
            sql = f"CREATE INDEX IF NOT EXISTS {index_name} ON {table}({column_list})"
            cursor.execute(sql)
            created.append(index_name)
            print(f"✅ 创建: {index_name}")

        except Exception as e:
            failed.append((index_name, str(e)))
            print(f"❌ 失败: {index_name} - {e}")

    conn.commit()

    # 显示统计
    print(f"\n{'='*50}")
    print(f"索引创建完成:")
    print(f"  ✅ 新建: {len(created)}")
    print(f"  ⏭️  跳过: {len(skipped)}")
    print(f"  ❌ 失败: {len(failed)}")

    if created:
        print(f"\n新建的索引:")
        for idx in created:
            print(f"  - {idx}")

    # 验证索引数量
    cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='index'")
    total_indexes = cursor.fetchone()[0]
    print(f"\n数据库当前索引总数: {total_indexes}")

    conn.close()

    return {
        "created": len(created),
        "skipped": len(skipped),
        "failed": len(failed),
        "total_indexes": total_indexes
    }


if __name__ == "__main__":
    print("🚀 开始数据库索引优化...")
    print(f"数据库路径: {DB_PATH}")
    print("="*50)
    result = add_indexes()
    print("="*50)
    print("✅ 索引优化完成!")
