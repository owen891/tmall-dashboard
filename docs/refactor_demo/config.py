"""
配置加载 — 重构后版本。

原始代码：db.py 中硬编码配置加载逻辑。
重构后：统一到 config.py，支持从 config.yaml 读取 + 环境变量覆盖。
"""
import os
import yaml


class Config:
    """应用配置"""

    # 数据库
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL',
        'sqlite:///data/dashboard.db'
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
    }

    # 文件上传
    MAX_CONTENT_LENGTH = 100 * 1024 * 1024  # 100MB
    UPLOAD_FOLDER = 'data/uploads'

    # 缓存
    CACHE_TTL = 300  # 5 分钟

    # 调度器
    SCHEDULER_ENABLED = os.environ.get('SCHEDULER_ENABLED', 'true').lower() == 'true'

    # 数据目录
    DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
    BACKUP_DIR = os.path.join(DATA_DIR, 'backups')
    RAW_DIR = os.path.join(DATA_DIR, 'raw')

    @classmethod
    def load_yaml(cls):
        """从 config.yaml 加载额外配置"""
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'config.yaml'
        )
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                yaml_config = yaml.safe_load(f)
                # 可以在这里将 yaml 配置映射到类属性
                if 'data' in yaml_config:
                    db_path = yaml_config['data'].get('db_path', '')
                    if db_path and not os.path.isabs(db_path):
                        db_path = os.path.join(
                            os.path.dirname(os.path.dirname(__file__)),
                            db_path
                        )
                    if db_path:
                        cls.SQLALCHEMY_DATABASE_URI = f'sqlite:///{db_path}'
        return cls
