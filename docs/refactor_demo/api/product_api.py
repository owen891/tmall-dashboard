"""
商品 API 路由 — 从 data_api.py 拆分。

原始代码在 data_api.py 中，包含 /api/products、/api/products/<id>/field、
/api/star、/api/batch_update 等路由，约 350 行。

重构后：路由精简为参数提取 + 调用 service/repo + 返回 JSON。
"""
from flask import Blueprint, jsonify, request

from repos.product_repo import ProductRepo
from models.constants import ALLOWED_FIELDS

product_bp = Blueprint('product', __name__)


@product_bp.route('/api/products', methods=['GET'])
def get_products():
    """
    商品列表 — 替代原 /api/products 路由（约 250 行手写 SQL）。

    原始代码：
        dim = request.args.get('dim', 'monthly')
        period = request.args.get('period')
        sort = request.args.get('sort', 'payment_amount')
        sql = f"SELECT p.*, m.* FROM products p JOIN {table} m ON ..."
        + 手动拼接 WHERE / ORDER BY / LIMIT / 格式化

    重构后：调用 repo，10 行搞定。
    """
    dim = request.args.get('dim', 'monthly')
    period = request.args.get('period')
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 20))
    sort = request.args.get('sort', 'payment_amount')
    order = request.args.get('order', 'desc')
    category = request.args.get('category')
    tier = request.args.get('tier')
    search = request.args.get('search')

    if not period:
        periods = ProductRepo.get_periods(dim)
        period = periods[0] if periods else None

    if not period:
        return jsonify({'products': [], 'total': 0})

    pagination = ProductRepo.list_products(
        dim, period, page, per_page, sort, order, category, tier, search
    )

    products = []
    for product, data in pagination.items:
        item = product.to_dict()
        item.update({
            'payment_amount': data.payment_amount or 0,
            'refund_amount': data.refund_amount or 0,
            'net_sales': data.net_sales or 0,
            'visitors': getattr(data, 'visitors', 0) or getattr(data, 'ipv', 0) or 0,
            'payment_conversion': data.payment_conversion or 0,
            'ad_spend': data.ad_spend or 0,
            'ad_roi': data.ad_roi or 0,
            'score': getattr(data, 'score', 0) or 0,
        })
        products.append(item)

    return jsonify({
        'products': products,
        'total': pagination.total,
        'pages': pagination.pages,
        'current_page': pagination.page,
    })


@product_bp.route('/api/products/<product_id>/field', methods=['PUT'])
def update_product_field(product_id):
    """
    行内编辑 — 替代原路由（约 40 行）。

    安全设计：field 必须在 ALLOWED_FIELDS 白名单中。
    """
    data = request.get_json()
    field = data.get('field')
    value = data.get('value')

    if field not in ALLOWED_FIELDS:
        return jsonify({'error': f'Field "{field}" is not allowed'}), 400

    try:
        ProductRepo.update_field(product_id, field, value)
        return jsonify({'success': True})
    except ValueError as e:
        return jsonify({'error': str(e)}), 400


@product_bp.route('/api/star', methods=['POST'])
def toggle_star():
    """星标切换 — 替代原路由"""
    data = request.get_json()
    product_id = data.get('product_id')

    product = ProductRepo.toggle_star(product_id)
    if product:
        return jsonify({'success': True, 'starred': product.starred})
    return jsonify({'error': 'Product not found'}), 404


@product_bp.route('/api/batch_update', methods=['POST'])
def batch_update():
    """批量更新 — 替代原路由"""
    data = request.get_json()
    product_ids = data.get('product_ids', [])
    updates = data.get('updates', {})

    # 安全检查
    for field in updates:
        if field not in ALLOWED_FIELDS:
            return jsonify({'error': f'Field "{field}" is not allowed'}), 400

    from models import db
    from models.product import Product
    Product.query.filter(Product.product_id.in_(product_ids)).update(
        updates, synchronize_session=False
    )
    db.session.commit()

    return jsonify({'success': True, 'updated': len(product_ids)})
