from db import get_db


class SystemRepo:
    @staticmethod
    def get_status():
        with get_db() as connection:
            product_count = connection.execute(
                'SELECT COUNT(*) FROM products'
            ).fetchone()[0]
            monthly_count = connection.execute(
                'SELECT COUNT(*) FROM monthly_data'
            ).fetchone()[0]
            weekly_count = connection.execute(
                'SELECT COUNT(*) FROM weekly_data'
            ).fetchone()[0]

        return {
            'has_data': product_count > 0 and (monthly_count > 0 or weekly_count > 0),
            'product_count': product_count,
            'monthly_periods': monthly_count,
            'weekly_periods': weekly_count,
        }
