# -*- coding: utf-8 -*-
"""
市场分析数据导入脚本
将 market_analyzer 的分析结果导入数据库
"""

import os
import sys
import json
from datetime import datetime

# 确保项目根目录在 sys.path 中
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from db import get_connection
from scripts.market_analyzer import build_analysis_data, identify_files, extract_category_and_dates


def identify_market_files(file_paths):
    """识别文件类型，返回 {f30, f7, ft} 路径字典

    复用 market_analyzer 的 identify_files() 逻辑，
    将返回值转换为更清晰的字典格式。

    Args:
        file_paths: 文件路径列表

    Returns:
        dict: {f30: path_or_None, f7: path_or_None, ft: path_or_None}
    """
    if not file_paths or len(file_paths) < 3:
        return {'f30': None, 'f7': None, 'ft': None}

    f30, f7, ft = identify_files(file_paths)
    return {'f30': f30, 'f7': f7, 'ft': ft}


def import_market_data(f30_path, f7_path, ft_path):
    """调用 market_analyzer 分析数据并导入数据库

    Args:
        f30_path: 30天搜索数据文件路径
        f7_path: 7天搜索数据文件路径
        ft_path: 趋势分析数据文件路径

    Returns:
        int: 处理的关键词数量
    """
    # 调用 market_analyzer 构建分析数据
    data = build_analysis_data(f30_path, f7_path, ft_path)

    meta = data.get('meta', {})
    summary = data.get('summary', {})
    keywords = data.get('keywords', [])
    need_stats = data.get('need_stats', {})
    dimension_details = data.get('dimension_details', {})
    histograms = data.get('histograms', {})
    rankings = data.get('rankings', {})

    # 提取品类和日期信息
    category_path = meta.get('category_path', '')
    category_short = meta.get('category_short', '')
    period_30d = meta.get('period_30d', '')
    period_7d = meta.get('period_7d', '')
    period_trend = meta.get('period_trend', '')
    total_keywords = meta.get('total_keywords', 0)
    avg_ctr_7d = meta.get('avg_ctr_7d', 0)
    avg_cvr_30d = meta.get('avg_cvr_30d', 0)
    top5_keywords = meta.get('top5_keywords', [])

    # 从 period_30d 提取分析日期 (取结束日期)
    analysis_date = ''
    if period_30d:
        # 格式: "2026-03-20 ~ 2026-04-18"
        dates = period_30d.split('~')
        if len(dates) >= 2:
            analysis_date = dates[-1].strip()
        else:
            analysis_date = period_30d.strip()
    if not analysis_date:
        analysis_date = datetime.now().strftime('%Y-%m-%d')

    conn = get_connection()
    cursor = conn.cursor()

    try:
        # 插入/更新 market_analysis 表 (使用 INSERT OR REPLACE 处理 UNIQUE 约束)
        cursor.execute('''
            INSERT OR REPLACE INTO market_analysis (
                analysis_date, category_path, category_short,
                period_30d, period_7d, period_trend,
                total_keywords, avg_ctr_7d, avg_cvr_30d,
                top5_keywords, summary_data, keywords_data,
                need_stats_data, dimension_details, histograms_data, rankings_data
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            analysis_date,
            category_path,
            category_short,
            period_30d,
            period_7d,
            period_trend,
            total_keywords,
            avg_ctr_7d,
            avg_cvr_30d,
            json.dumps(top5_keywords, ensure_ascii=False),
            json.dumps(summary, ensure_ascii=False),
            json.dumps(keywords, ensure_ascii=False),
            json.dumps(need_stats, ensure_ascii=False),
            json.dumps(dimension_details, ensure_ascii=False),
            json.dumps(histograms, ensure_ascii=False),
            json.dumps(rankings, ensure_ascii=False),
        ))

        # 删除该分析日期的旧机会数据
        cursor.execute(
            'DELETE FROM market_keyword_opportunities WHERE analysis_date = ?',
            (analysis_date,)
        )

        # 提取关键词机会并插入 market_keyword_opportunities 表
        opp_count = 0
        for kw_item in keywords:
            keyword = kw_item.get('keyword', '')
            pop_30d = kw_item.get('pop_30d')
            ctr_7d = kw_item.get('ctr_7d')
            cvr_30d = kw_item.get('cvr_30d')
            opp_cat = kw_item.get('opportunity_category', '')
            opp_score = kw_item.get('opportunity_score', 0)
            need_tags = kw_item.get('need_tags', [])

            cursor.execute('''
                INSERT INTO market_keyword_opportunities (
                    analysis_date, keyword, pop_30d, ctr_7d, cvr_30d,
                    opportunity_category, opportunity_score, need_tags
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                analysis_date,
                keyword,
                pop_30d,
                ctr_7d,
                cvr_30d,
                opp_cat,
                opp_score,
                json.dumps(need_tags, ensure_ascii=False),
            ))
            opp_count += 1

        conn.commit()
        print("市场分析数据导入成功: %d 个关键词, 分析日期 %s" % (opp_count, analysis_date))
        return opp_count

    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


if __name__ == '__main__':
    if len(sys.argv) >= 4:
        f30_path = sys.argv[1]
        f7_path = sys.argv[2]
        ft_path = sys.argv[3]
    else:
        print("用法: python import_market.py <30天文件> <7天文件> <趋势文件>")
        sys.exit(1)

    count = import_market_data(f30_path, f7_path, ft_path)
    print("导入完成，共处理 %d 个关键词" % count)
