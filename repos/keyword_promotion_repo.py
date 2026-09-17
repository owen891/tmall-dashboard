from db import get_db, get_shop_id


class KeywordPromotionRepo:
    """关键词推广商品级数据访问层"""

    # 可筛选的属性字段
    FILTER_COLUMNS = {
        'gender': 'gender',
        'season': 'season',
        'category': 'category',
        'material': 'material',
        'scene': 'scene',
        'thickness': 'thickness',
        'style': 'style',
        'score_grade': 'score_grade',
        'suggested_action': 'suggested_action',
        'shop_label': 'shop_label',
    }

    # 可排序字段
    SORT_COLUMNS = {
        'total_score': 'total_score',
        'roi': 'roi',
        'ad_spend': 'ad_spend',
        'payment_amount': 'payment_amount',
        'cvr': 'cvr',
        'ctr': 'ctr',
        'cart_rate': 'cart_rate',
        'clicks': 'clicks',
        'impressions': 'impressions',
        'new_buyers': 'new_buyers',
        'organic_visitors': 'organic_visitors',
        'organic_payment': 'organic_payment',
        'organic_cvr': 'organic_cvr',
        'organic_uv_value': 'organic_uv_value',
    }

    @staticmethod
    def list_products(filters, sort_by='total_score', sort_order='desc', page=1, page_size=50):
        shop_id = get_shop_id()
        where = ['shop_id = ?']
        params = [shop_id]

        # 属性筛选
        for key, col in KeywordPromotionRepo.FILTER_COLUMNS.items():
            val = filters.get(key)
            if val:
                where.append(f'{col} = ?')
                params.append(val)

        # 最小花费筛选（数据有效性）
        min_spend = filters.get('min_spend')
        if min_spend is not None:
            where.append('ad_spend >= ?')
            params.append(float(min_spend))

        # 最小ROI筛选
        min_roi = filters.get('min_roi')
        if min_roi is not None:
            where.append('roi >= ?')
            params.append(float(min_roi))

        # 关键词搜索（标题）
        keyword = filters.get('keyword')
        if keyword:
            where.append('title LIKE ?')
            params.append(f'%{keyword}%')

        where_sql = ' AND '.join(where)

        # 排序
        sort_col = KeywordPromotionRepo.SORT_COLUMNS.get(sort_by, 'total_score')
        sort_dir = 'DESC' if sort_order == 'desc' else 'ASC'

        # 分页
        offset = (page - 1) * page_size

        query = f'''
            SELECT * FROM keyword_promotion_products
            WHERE {where_sql}
            ORDER BY {sort_col} {sort_dir}
            LIMIT ? OFFSET ?
        '''
        params.extend([page_size, offset])

        with get_db() as conn:
            rows = conn.execute(query, params).fetchall()
            count = conn.execute(
                f'SELECT COUNT(*) FROM keyword_promotion_products WHERE {where_sql}',
                params[:-2]
            ).fetchone()[0]

        return {
            'rows': [dict(r) for r in rows],
            'total': count,
            'page': page,
            'page_size': page_size,
        }

    @staticmethod
    def summary(filters):
        shop_id = get_shop_id()
        where = ['shop_id = ?']
        params = [shop_id]

        for key, col in KeywordPromotionRepo.FILTER_COLUMNS.items():
            val = filters.get(key)
            if val:
                where.append(f'{col} = ?')
                params.append(val)

        min_spend = filters.get('min_spend')
        if min_spend is not None:
            where.append('ad_spend >= ?')
            params.append(float(min_spend))

        min_roi = filters.get('min_roi')
        if min_roi is not None:
            where.append('roi >= ?')
            params.append(float(min_roi))

        keyword = filters.get('keyword')
        if keyword:
            where.append('title LIKE ?')
            params.append(f'%{keyword}%')

        where_sql = ' AND '.join(where)

        query = f'''
            SELECT
                COUNT(*) as product_count,
                SUM(ad_spend) as total_spend,
                SUM(payment_amount) as total_payment,
                SUM(clicks) as total_clicks,
                SUM(impressions) as total_impressions,
                SUM(payment_orders) as total_orders,
                SUM(cart_adds) as total_cart_adds,
                SUM(new_buyers) as total_new_buyers,
                AVG(roi) as avg_roi,
                AVG(cvr) as avg_cvr,
                AVG(ctr) as avg_ctr,
                AVG(cart_rate) as avg_cart_rate,
                SUM(CASE WHEN roi >= 1 THEN 1 ELSE 0 END) as roi_qualified,
                SUM(CASE WHEN total_score >= 55 THEN 1 ELSE 0 END) as good_products
            FROM keyword_promotion_products
            WHERE {where_sql}
        '''

        with get_db() as conn:
            row = conn.execute(query, params).fetchone()

        result = dict(row)
        # 计算整体ROI
        if result['total_spend'] and result['total_spend'] > 0:
            result['overall_roi'] = round(result['total_payment'] / result['total_spend'], 4)
        else:
            result['overall_roi'] = None
        return result

    @staticmethod
    def filter_options():
        """获取各属性的筛选选项分布"""
        options = {}
        with get_db() as conn:
            for col in ['gender', 'season', 'category', 'material', 'scene', 'thickness', 'style', 'score_grade', 'suggested_action']:
                rows = conn.execute(
                    f'SELECT {col} as value, COUNT(*) as count FROM keyword_promotion_products WHERE {col} IS NOT NULL GROUP BY {col} ORDER BY count DESC'
                ).fetchall()
                options[col] = [{'value': r['value'], 'count': r['count']} for r in rows if r['value']]
        return options

    @staticmethod
    def grade_distribution():
        """推广评级分布"""
        with get_db() as conn:
            rows = conn.execute('''
                SELECT score_grade, COUNT(*) as count,
                       SUM(ad_spend) as total_spend,
                       SUM(payment_amount) as total_payment
                FROM keyword_promotion_products
                GROUP BY score_grade
                ORDER BY count DESC
            ''').fetchall()
        return [dict(r) for r in rows]
