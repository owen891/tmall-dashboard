from flask import Flask, render_template, send_from_directory
import os
from db import init_db
from api.data_api import data_bp
from api.status_api import status_bp
from api.tool_api import tool_bp
from config import Config
from models import db as orm_db

# 获取项目根目录的绝对路径
project_root = os.path.dirname(os.path.abspath(__file__))

def create_app(config=None):
    app = Flask(
        __name__,
        template_folder=os.path.join(project_root, 'templates'),
        static_folder=os.path.join(project_root, 'static'),
    )
    app.config.from_object(Config)
    if config:
        app.config.from_mapping(config)

    orm_db.init_app(app)
    app.register_blueprint(status_bp)
    app.register_blueprint(data_bp)
    app.register_blueprint(tool_bp)
    init_db()

    @app.route('/')
    def index():
        return render_template('dashboard.html')

    @app.route('/static/<path:path>')
    def static_files(path):
        return send_from_directory(os.path.join(project_root, 'static'), path)

    return app


app = create_app()

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=False)
