# app/core/config.py
from pydantic import BaseSettings, PostgresDsn


class Settings(BaseSettings):
    # Пример: postgresql+psycopg2://user:password@localhost:5432/tri_s_audit
    DATABASE_URL: PostgresDsn

    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    JWT_ALGORITHM: str = "HS256"

    # Для проверки Telegram WebApp initData
    TELEGRAM_BOT_TOKEN: str | None = None

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
