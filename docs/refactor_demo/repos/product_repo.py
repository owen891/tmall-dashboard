"""
商品 Repository — 商品列表查询、字段更新、标签管理。

演示如何用 SQLAlchemy ORM 替代手写 SQL。
原始代码在 data_api.py 的 get_products() 函数中（约 250 行手写 SQL）。
"""
from models import db
from models.product import Product
from models.data import DailyData, WeeklyData, MonthlyData
from models.constants import DIMENSION_MAP, ALLOWED_FIELDS, SORT_WHITELIST
from repos.base_repo import BaseRepo


class ProductRepo(BaseRepo):
    model = Product

    # 维度 → ORM 模型映射（替代 DIMENSION_MAP 中的表名字符串）
    _table_map = {
        'monthly': MonthlyData,
        'weekly': WeeklyData,
        'daily': DailyData,
    }

    @staticmethod
    def list_products(dim, period, page=1, per_page=20, sort='payment_amount',
                      order='desc', category=None, tier=None, search=None):
        """
        商品列表查询 — 替代原 get_products() 中的手写 SQL。

        原始代码：
            sql = f"SELECT p.*, m.* FROM products p JOIN {table} m ON ..."
            + 手动拼接 WHERE / ORDER BY / LIMIT

        重构后：ORM 查询，类型安全，无 SQL 注入风险。
        """
        model = ProductRepo._table_map[dim]
        date_col = getattr(model, DIMENSION_MAP[dim]['date_col'])

        query = db.session.query(Product, model).join(
            model, Product.product_id == model.product_id
        ).filter(date_col == period)

        # 筛选条件
        if category:
            query = query.filter(Product.category == category)
        if tier:
            query = query.filter(Product.tier == tier)
        if search:
            query = query.filter(Product.title.contains(search))

        # 排序 — 白名单校验，防止任意字段排序
        if sort in SORT_WHITELIST:
            sort_col = getattr(model, sort, None) or getattr(Product, sort, None)
            if sort_col is not None:
                query = query.order_by(
                    sort_col.desc() if order == 'desc' else sort_col.asc()
                )

        return query.paginate(page=page, per_page=per_page, error_out=False)

    @staticmethod
    def update_field(product_id, field, value):
        """
        行内编辑 — 替代原 /api/products/<product_id>/field 路由中的 SQL。

        安全设计：field 必须在 ALLOWED_FIELDS 白名单中。
        """
        if field not in ALLOWED_FIELDS:
            raise ValueError(f"Field '{field}' is not allowed for inline edit")

        Product.query.filter_by(product_id=product_id).update({field: value})
        db.session.commit()

    @staticmethod
    def toggle_star(product_id):
        """星标切换"""
        product = Product.query.filter_by(product_id=product_id).first()
        if product:
            product.starred = 1 if not product.starred else 0
            db.session.commit()
        return product

    @staticmethod
    def get_starred():
        """获取所有星标商品"""
        return Product.query.filter_by(starred=1).all()

    @staticmethod
    def get_periods(dim):
        """获取可用周期列表"""
        model = ProductRepo._table_map[dim]
        date_col = getattr(model, DIMENSION_MAP[dim]['date_col'])
        results = db.session.query(date_col).distinct().order_by(date_col.desc()).all()
        return [str(r[0]) for r in results]
