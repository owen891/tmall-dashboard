from flask import Blueprint

from api.api_response import failure, success
from db import get_db
from repos.actions_repo import ActionsRepo
from services.lifecycle_service import lifecycle_service


product_detail_bp = Blueprint('product_detail', __name__)


@product_detail_bp.route('/api/products/<product_id>/detail')
def product_detail(product_id):
    with get_db() as connection:
        product = connection.execute('SELECT * FROM products WHERE product_id = ?', (product_id,)).fetchone()
        if not product:
            return failure('NOT_FOUND', '商品不存在', status=404)
        trend = connection.execute(
            '''SELECT date, payment_amount, refund_amount, payment_amount - refund_amount AS net_sales,
                      ipv AS product_visitors, buyers AS payment_buyers, ad_spend
               FROM daily_data WHERE product_id = ? ORDER BY date''', (product_id,)
        ).fetchall()
    product_data = dict(product)
    lifecycle = next((item for item in lifecycle_service.list() if item['product_id'] == product_id), None)
    return success({'product': product_data, 'daily_trend': [dict(row) for row in trend],
                    'lifecycle': lifecycle, 'actions': ActionsRepo.list_actions(product_id)})
