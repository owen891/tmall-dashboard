"""
数据质量校验脚本
检查项：完整性、一致性、异常值、重复数据、新鲜度
用法: python scripts/data_quality_check.py
"""

import sqlite3
import json
import os
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / 'data' / 'dashboard.db'
REPORT_DIR = Path(__file__).parent.parent / 'logs'


def check_freshness(conn):
    """检查数据新鲜度：最新数据是否是最近3天内的"""
    issues = []
    tables = [
        ('daily_data', 'date', '日数据'),
        ('monthly_data', 'month', '月数据'),
        ('sycm_flow_source_daily', 'stat_date', '店铺流量'),
        ('sycm_item_flow_source_daily', 'stat_date', '单品流量'),
        ('promotion_daily_facts', 'date', '推广数据'),
    ]
    today = datetime.now().date()
    for table, date_col, name in tables:
        try:
            latest = conn.execute(f"SELECT MAX({date_col}) FROM {table}").fetchone()[0]
            if latest:
                latest_str = str(latest)
                # 支持 YYYY-MM 和 YYYY-MM-DD 两种格式
                if len(latest_str) == 7:
                    latest_date = datetime.strptime(latest_str + '-01', '%Y-%m-%d').date()
                else:
                    latest_date = datetime.strptime(latest_str[:10], '%Y-%m-%d').date()
                days_ago = (today - latest_date).days
                if days_ago > 3:
                    issues.append({
                        'level': 'warning',
                        'type': 'freshness',
                        'table': table,
                        'message': f'{name}最新数据是 {latest}，已 {days_ago} 天未更新',
                    })
            else:
                issues.append({
                    'level': 'warning',
                    'type': 'freshness',
                    'table': table,
                    'message': f'{name}表无数据',
                })
        except Exception as e:
            issues.append({'level': 'error', 'type': 'freshness', 'table': table, 'message': str(e)})
    return issues


def _table_columns(conn, table):
    """Return the columns available in a table without assuming a schema version."""
    return {row[1] for row in conn.execute(f'PRAGMA table_info({table})').fetchall()}


def check_completeness(conn):
    """检查完整性：按店铺检查最近30天是否有缺失日期。"""
    issues = []
    today = datetime.now().date()
    start_date = today - timedelta(days=30)

    try:
        rows = conn.execute(
            """SELECT shop_id, date FROM daily_data
               WHERE date >= ? GROUP BY shop_id, date ORDER BY shop_id, date""",
            (start_date.isoformat(),)
        ).fetchall()
        dates_by_shop = {}
        for shop_id, date_value in rows:
            dates_by_shop.setdefault(shop_id, set()).add(date_value)
        expected_dates = {(start_date + timedelta(days=i)).isoformat() for i in range(31)}
        for shop_id, date_set in dates_by_shop.items():
            missing = sorted(expected_dates - date_set)
            if missing:
                issues.append({
                    'level': 'warning',
                    'type': 'completeness',
                    'table': 'daily_data',
                    'shop_id': shop_id,
                    'message': f'店铺 {shop_id} 近30天缺失 {len(missing)} 天数据: {missing[:5]}...',
                })
    except Exception as e:
        issues.append({'level': 'error', 'type': 'completeness', 'table': 'daily_data', 'message': str(e)})

    return issues


def check_consistency(conn):
    """检查一致性：按可用店铺粒度对比日数据和月数据。"""
    issues = []
    try:
        monthly_columns = _table_columns(conn, 'monthly_data')
        if 'shop_id' in monthly_columns:
            scopes = conn.execute(
                "SELECT DISTINCT shop_id, month FROM monthly_data ORDER BY month DESC LIMIT 3"
            ).fetchall()
        else:
            scopes = [(None, row[0]) for row in conn.execute(
                "SELECT DISTINCT month FROM monthly_data ORDER BY month DESC LIMIT 3"
            ).fetchall()]
        for shop_id, month in scopes:
            daily_sql = "SELECT COALESCE(SUM(payment_amount), 0) FROM daily_data WHERE date LIKE ?"
            monthly_sql = "SELECT COALESCE(SUM(payment_amount), 0) FROM monthly_data WHERE month = ?"
            params = [f'{month}%']
            monthly_params = [month]
            if shop_id is not None:
                daily_sql += " AND shop_id = ?"
                monthly_sql += " AND shop_id = ?"
                params.append(shop_id)
                monthly_params.append(shop_id)
            daily_sum = conn.execute(daily_sql, params).fetchone()[0]
            monthly_sum = conn.execute(monthly_sql, monthly_params).fetchone()[0]
            if monthly_sum > 0 and abs(daily_sum - monthly_sum) / monthly_sum > 0.05:
                scope = f'店铺 {shop_id}，' if shop_id is not None else ''
                issues.append({
                    'level': 'warning',
                    'type': 'consistency',
                    'table': 'daily_data vs monthly_data',
                    'shop_id': shop_id,
                    'message': f'{scope}{month}: 日汇总 {daily_sum:.0f} vs 月数据 {monthly_sum:.0f}，差异 {abs(daily_sum-monthly_sum)/monthly_sum*100:.1f}%',
                })
    except Exception as e:
        issues.append({'level': 'error', 'type': 'consistency', 'message': str(e)})
    return issues


def check_anomalies(conn):
    """检查异常值：负数、超历史10倍"""
    issues = []
    try:
        # 负数检查
        neg_daily = conn.execute(
            "SELECT COUNT(*) FROM daily_data WHERE payment_amount < 0 OR refund_amount < 0 OR ipv < 0"
        ).fetchone()[0]
        if neg_daily > 0:
            issues.append({
                'level': 'error',
                'type': 'anomaly',
                'table': 'daily_data',
                'message': f'存在 {neg_daily} 条负数字段记录',
            })

        # 超历史均值10倍检查（最近7天）
        recent_avg = conn.execute(
            """SELECT AVG(daily_sum) FROM (
                SELECT date, SUM(payment_amount) as daily_sum 
                FROM daily_data 
                WHERE date >= date('now', '-30 days') 
                GROUP BY date
            )"""
        ).fetchone()[0]
        if recent_avg and recent_avg > 0:
            high_days = conn.execute(
                """SELECT date, SUM(payment_amount) as daily_sum 
                   FROM daily_data 
                   WHERE date >= date('now', '-7 days') 
                   GROUP BY date 
                   HAVING daily_sum > ? * 10""",
                (recent_avg,)
            ).fetchall()
            if high_days:
                issues.append({
                    'level': 'warning',
                    'type': 'anomaly',
                    'table': 'daily_data',
                    'message': f'近7天有 {len(high_days)} 天销售额超历史均值10倍（均值 {recent_avg:.0f}）',
                })
    except Exception as e:
        issues.append({'level': 'error', 'type': 'anomaly', 'message': str(e)})
    return issues


def check_duplicates(conn):
    """检查重复数据，使用各事实表实际支持的唯一粒度。"""
    issues = []
    try:
        dup_daily = conn.execute(
            """SELECT COUNT(*) FROM (
                SELECT shop_id, product_id, date, COUNT(*) as cnt
                FROM daily_data
                GROUP BY shop_id, product_id, date
                HAVING cnt > 1
            )"""
        ).fetchone()[0]
        if dup_daily > 0:
            issues.append({
                'level': 'error',
                'type': 'duplicate',
                'table': 'daily_data',
                'message': f'存在 {dup_daily} 组 (shop_id, product_id, date) 重复记录',
            })

        monthly_columns = _table_columns(conn, 'monthly_data')
        monthly_key = ('shop_id', 'product_id', 'month') if 'shop_id' in monthly_columns else ('product_id', 'month')
        monthly_group = ', '.join(monthly_key)
        dup_monthly = conn.execute(
            f"""SELECT COUNT(*) FROM (
                SELECT {monthly_group}, COUNT(*) as cnt
                FROM monthly_data
                GROUP BY {monthly_group}
                HAVING cnt > 1
            )"""
        ).fetchone()[0]
        if dup_monthly > 0:
            issues.append({
                'level': 'error',
                'type': 'duplicate',
                'table': 'monthly_data',
                'message': f'存在 {dup_monthly} 组 ({monthly_group}) 重复记录',
            })
    except Exception as e:
        issues.append({'level': 'error', 'type': 'duplicate', 'message': str(e)})
    return issues


def check_integrity(conn):
    """检查数据库完整性"""
    result = conn.execute("PRAGMA integrity_check").fetchone()[0]
    if result != 'ok':
        return [{'level': 'error', 'type': 'integrity', 'message': f'数据库完整性检查失败: {result}'}]
    return []


def main():
    if not DB_PATH.exists():
        print(f"数据库不存在: {DB_PATH}")
        return 1

    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    all_issues = []
    all_issues.extend(check_integrity(conn))
    all_issues.extend(check_freshness(conn))
    all_issues.extend(check_completeness(conn))
    all_issues.extend(check_consistency(conn))
    all_issues.extend(check_anomalies(conn))
    all_issues.extend(check_duplicates(conn))

    conn.close()

    # 统计
    errors = [i for i in all_issues if i['level'] == 'error']
    warnings = [i for i in all_issues if i['level'] == 'warning']

    # 生成报告
    report = {
        'check_time': datetime.now().isoformat(),
        'database': str(DB_PATH),
        'summary': {
            'total_checks': 6,
            'errors': len(errors),
            'warnings': len(warnings),
            'status': 'fail' if errors else ('warning' if warnings else 'pass'),
        },
        'issues': all_issues,
    }

    # 保存报告
    report_file = REPORT_DIR / f'data-quality-{datetime.now().strftime("%Y%m%d-%H%M%S")}.json'
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    # 输出摘要
    print(f"=== 数据质量校验报告 ===")
    print(f"检查时间: {report['check_time']}")
    print(f"状态: {report['summary']['status']}")
    print(f"错误: {len(errors)}, 警告: {len(warnings)}")
    print()
    for issue in all_issues:
        icon = '✗' if issue['level'] == 'error' else '⚠'
        print(f"  {icon} [{issue['type']}] {issue['message']}")

    # 清理30天前的报告
    for old_report in REPORT_DIR.glob('data-quality-*.json'):
        if old_report.stat().st_mtime < (datetime.now().timestamp() - 30 * 86400):
            old_report.unlink()

    return 1 if errors else 0


if __name__ == '__main__':
    exit(main())
