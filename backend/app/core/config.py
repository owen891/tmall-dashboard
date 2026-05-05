from pydantic_settings import BaseSettings
from typing import List, Optional
from functools import lru_cache
import os
import logging
import warnings


class Settings(BaseSettings):
    PROJECT_NAME: str = "海贝海数据仪表盘"
    PROJECT_VERSION: str = "2.0.0"
    DEBUG: bool = os.getenv("DEBUG", "true").lower() == "true"

    DATABASE_URL: str = f"sqlite:///{os.path.dirname(os.path.dirname(os.path.dirname(__file__)))}/data/db/dashboard.db"

    BACKEND_CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:5174", "http://127.0.0.1:5174"]

    SECRET_KEY: str = ""
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    OPENAI_API_KEY: Optional[str] = None

    REDIS_URL: Optional[str] = None
    CACHE_TTL: int = 300

    COMMISSION_RATE: float = 0.06
    FREIGHT_RATE: float = 0.02
    INDUSTRY_CTR: float = 0.05

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.SECRET_KEY:
            if not self.DEBUG:
                raise ValueError("SECRET_KEY must be set in production environment")
            import secrets
            self.SECRET_KEY = secrets.token_urlsafe(32)
            warnings.warn(
                "SECRET_KEY not set, using auto-generated key. "
                "Tokens will NOT survive restarts. Set SECRET_KEY in .env for production.",
                stacklevel=2
            )


@lru_cache()
def get_settings():
    return Settings()


settings = get_settings()
