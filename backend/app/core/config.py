from pydantic_settings import BaseSettings
from typing import List, Optional
from functools import lru_cache
import os
import secrets


class Settings(BaseSettings):
    PROJECT_NAME: str = "海贝海数据仪表盘"
    PROJECT_VERSION: str = "2.0.0"
    DEBUG: bool = True

    DATABASE_URL: str = f"sqlite:///{os.path.dirname(os.path.dirname(os.path.dirname(__file__)))}/data/dashboard.db"

    BACKEND_CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:5174", "http://127.0.0.1:5174"]

    SECRET_KEY: str = secrets.token_urlsafe(32)
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    OPENAI_API_KEY: Optional[str] = None

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"


@lru_cache()
def get_settings():
    return Settings()


settings = get_settings()
