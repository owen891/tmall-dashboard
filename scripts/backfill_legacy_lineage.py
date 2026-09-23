#!/usr/bin/env python3
"""
历史 Lineage 回填工具

用途：为已有 daily_data_observations 但缺失 fact_field_lineage 的历史数据生成 lineage。
前提：只处理有明确来源证据（observation + payload）的数据，不猜测或伪造来源。

使用：
  python scripts/backfill_legacy_lineage.py --database data/dashboard.db --dry-run
  python scripts/backfill_legacy_lineage.py --database data/dashboard.db --execute
"""

import argparse
import json
import logging
import sqlite3
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


def get_missing_lineage_scope(conn):
    """识别缺失 lineage 的数据范围"""
    cursor = conn.execute('''
        SELECT 
            COUNT(*) total_facts,
            COUNT(DISTINCT shop_id || '/' || product_id || '/' || date) unique_keys,
            MIN(date) min_date,
            MAX(date) max_date
        FROM daily_data d
        WHERE NOT EXISTS (
            SELECT 1 FROM fact_field_lineage l 
            WHERE l.shop_id = d.shop_id 
              AND l.product_id = d.product_id 
              AND l.date = d.date
        )
    ''')
    return cursor.fetchone()


def get_observation_coverage(conn):
    """检查缺失 lineage 的数据中有多少有 observation"""
    cursor = conn.execute('''
        SELECT 
            COUNT(DISTINCT d.shop_id || '/' || d.product_id || '/' || d.date) facts_without_lineage,
            COUNT(DISTINCT CASE 
                WHEN EXISTS (
                    SELECT 1 FROM daily_data_observations o 
                    WHERE o.shop_id = d.shop_id 
                      AND o.product_id = d.product_id 
                      AND o.date = d.date
                ) THEN d.shop_id || '/' || d.product_id || '/' || d.date 
            END) facts_with_observation
        FROM daily_data d
        WHERE NOT EXISTS (
            SELECT 1 FROM fact_field_lineage l 
            WHERE l.shop_id = d.shop_id 
              AND l.product_id = d.product_id 
              AND l.date = d.date
        )
    ''')
    return cursor.fetchone()


def backfill_lineage_from_observations(conn, dry_run=True):
    """从 observation 回填 lineage"""
    
    # 查找所有缺失 lineage 但有 observation 的记录
    cursor = conn.execute('''
        SELECT 
            o.shop_id,
            o.product_id,
            o.date,
            o.source_system,
            o.source_type,
            o.source_batch_id,
            o.payload_json,
            o.field_presence_json
        FROM daily_data_observations o
        WHERE EXISTS (
            SELECT 1 FROM daily_data d 
            WHERE d.shop_id = o.shop_id 
              AND d.product_id = o.product_id 
              AND d.date = o.date
        )
        AND NOT EXISTS (
            SELECT 1 FROM fact_field_lineage l 
            WHERE l.shop_id = o.shop_id 
              AND l.product_id = o.product_id 
              AND l.date = o.date
        )
        ORDER BY o.date, o.product_id
    ''')
    
    observations = cursor.fetchall()
    logger.info(f"发现 {len(observations)} 条有 observation 但缺失 lineage 的记录")
    
    if not observations:
        return 0
    
    # 为每个 observation 生成 lineage
    lineage_records = []
    
    for obs in observations:
        shop_id, product_id, date, source_system, source_type, source_batch_id, payload_json, field_presence_json = obs
        
        try:
            field_presence = json.loads(field_presence_json)
        except json.JSONDecodeError:
            logger.warning(f"跳过 {shop_id}/{product_id}/{date}: field_presence 无效")
            continue
        
        try:
            payload = json.loads(payload_json)
        except json.JSONDecodeError:
            logger.warning(f"跳过 {shop_id}/{product_id}/{date}: payload 无效")
            continue
        
        # 为每个存在的字段生成 lineage 记录
        for field_key, present in field_presence.items():
            if not present:
                continue
            
            value = payload.get(field_key)
            
            lineage_records.append({
                'shop_id': shop_id,
                'product_id': product_id,
                'date': date,
                'field_key': field_key,
                'effective_source_system': source_system,
                'effective_source_type': source_type,
                'source_batch_id': source_batch_id,
                'source_role': 'primary',
                'fallback_used': 0,
                'conflict_status': 'none',
                'observed_sources_json': json.dumps([{
                    'source_system': source_system,
                    'source_type': source_type,
                    'source_batch_id': source_batch_id,
                    'value': value
                }], ensure_ascii=False),
                'effective_value_json': json.dumps(value, ensure_ascii=False),
                'reason': 'backfilled from legacy observation'
            })
    
    logger.info(f"准备写入 {len(lineage_records)} 条 lineage 记录")
    
    if dry_run:
        logger.info("DRY RUN: 不会实际写入数据库")
        if lineage_records:
            sample = lineage_records[0]
            logger.info(f"示例记录: {sample['shop_id']}/{sample['product_id']}/{sample['date']} {sample['field_key']}")
        return len(lineage_records)
    
    # 实际写入
    conn.execute('BEGIN')
    try:
        conn.executemany('''
            INSERT INTO fact_field_lineage (
                shop_id, product_id, date, field_key,
                effective_source_system, effective_source_type, source_batch_id,
                source_role, fallback_used, conflict_status,
                observed_sources_json, effective_value_json, reason
            ) VALUES (
                :shop_id, :product_id, :date, :field_key,
                :effective_source_system, :effective_source_type, :source_batch_id,
                :source_role, :fallback_used, :conflict_status,
                :observed_sources_json, :effective_value_json, :reason
            )
        ''', lineage_records)
        
        conn.commit()
        logger.info(f"成功写入 {len(lineage_records)} 条 lineage 记录")
        return len(lineage_records)
        
    except Exception as e:
        conn.rollback()
        logger.error(f"写入失败: {e}")
        raise


def main():
    parser = argparse.ArgumentParser(description='回填历史数据的 field lineage')
    parser.add_argument('--database', required=True, help='数据库路径')
    parser.add_argument('--dry-run', action='store_true', help='只分析不写入')
    parser.add_argument('--execute', action='store_true', help='实际执行回填')
    parser.add_argument('--backup-destination', help='Required with --execute: integrity-checked SQLite backup path')
    
    args = parser.parse_args()
    
    if not args.dry_run and not args.execute:
        logger.error("必须指定 --dry-run 或 --execute")
        sys.exit(1)
    if args.execute and not args.backup_destination:
        parser.error('--backup-destination is required with --execute')
    
    db_path = Path(args.database).resolve()
    if not db_path.exists():
        logger.error(f"数据库不存在: {db_path}")
        sys.exit(1)
    
    logger.info(f"连接数据库: {db_path}")
    if args.execute:
        from scripts.backup_database import backup_database

        backup = backup_database(db_path, args.backup_destination)
        if not backup['ok']:
            raise RuntimeError('database backup integrity check failed')
    conn = sqlite3.connect(db_path)
    
    try:
        # 分析当前状态
        logger.info("分析缺失 lineage 的数据...")
        scope = get_missing_lineage_scope(conn)
        total_facts, unique_keys, min_date, max_date = scope
        
        logger.info(f"缺失 lineage: {total_facts} 条记录 ({unique_keys} 个唯一键)")
        logger.info(f"日期范围: {min_date} ~ {max_date}")
        
        coverage = get_observation_coverage(conn)
        facts_without_lineage, facts_with_observation = coverage
        
        logger.info(f"其中有 observation: {facts_with_observation}/{facts_without_lineage}")
        
        if facts_with_observation == 0:
            logger.info("没有可回填的数据")
            return 0
        
        # 执行回填
        records_written = backfill_lineage_from_observations(
            conn, 
            dry_run=args.dry_run
        )
        
        if not args.dry_run:
            # 验证结果
            logger.info("验证回填结果...")
            scope_after = get_missing_lineage_scope(conn)
            remaining = scope_after[0]
            logger.info(f"剩余缺失 lineage: {remaining} 条")
            
            if remaining > 0:
                logger.warning("仍有数据缺失 lineage，这些数据可能没有对应的 observation")
        
        return 0
        
    finally:
        conn.close()


if __name__ == '__main__':
    sys.exit(main())
