from flask import Flask, render_template, send_from_directory
import os
from db import init_db
from api.data_api import data_bp
from api.tool_api import tool_bp

app = Flask(__name__,
            template_folder='templates',
            static_folder='static')
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB 上传限制

app.register_blueprint(data_bp)
app.register_blueprint(tool_bp)

@app.route('/')
def index():
    return render_template('dashboard.html')

@app.route('/<path:path>')
def static_files(path):
    return send_from_directory('.', path)

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=False)
