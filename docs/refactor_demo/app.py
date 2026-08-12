"""
Flask 应用入口 — 重构后版本。

原始 app.py（或 data_api.py 底部）：
    app = Flask(__name__)
    app.register_blueprint(data_bp)  # 84 个路由全在一个蓝图
    # + 手动 init_db()

重构后：
    1. 创建 Flask app
    2. 加载配置
    3. 初始化 SQLAlchemy
    4. 按业务域注册多个蓝图
    5. 启动调度器（可选）
"""
import os
from flask import Flask, send_from_directory

from models import db
from config import Config


def create_app(config_class=Config):
    """应用工厂模式"""
    app = Flask(__name__,
                template_folder='../templates',
                static_folder='../static')

    app.config.from_object(config_class)

    # 初始化数据库
    db.init_app(app)

    # 注册蓝图 — 按业务域拆分
    _register_blueprints(app)

    # 确保数据库目录存在
    os.makedirs(os.path.dirname(app.config['SQLALCHEMY_DATABASE_URI']
                                .replace('sqlite:///', '')), exist_ok=True)

    # 创建表（开发环境；生产环境用 alembic migrate）
    with app.app_context():
        import models.product
        import models.data
        import models.paid
        import models.health
        import models.review
        import models.market
        import models.action
        import models.alert
        import models.system
        db.create_all()

    # 静态文件路由
    @app.route('/')
    def index():
        return send_from_directory('../templates', 'dashboard.html')

    return app


def _register_blueprints(app):
    """注册所有业务蓝图"""
    from api.kpi_api import kpi_bp
    from api.product_api import product_bp
    # ... 其他蓝图（按需添加）
    # from api.ad_api import ad_bp
    # from api.refund_api import refund_bp
    # from api.action_api import action_bp
    # from api.alert_api import alert_bp
    # from api.health_api import health_bp
    # from api.review_api import review_bp
    # from api.market_api import market_bp
    # from api.compare_api import compare_bp
    # from api.import_api import import_bp
    # from api.system_api import system_bp
    # from api.chart_event_api import chart_event_bp
    # from api.task_api import task_bp
    # from api.tool_api import tool_bp

    app.register_blueprint(kpi_bp)
    app.register_blueprint(product_bp)
    # ... 注册其他蓝图


# 创建应用实例
app = create_app()


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=True)
