# app/core/config.py
from pydantic import AnyUrl, BaseSettings, PostgresDsn


class Settings(BaseSettings):
    # Пример: postgresql+psycopg2://user:password@localhost:5432/tri_s_audit
    DATABASE_URL: PostgresDsn

    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    JWT_ALGORITHM: str = "HS256"

    # Для проверки Telegram WebApp initData
    TELEGRAM_BOT_TOKEN: str | None = None

    # S3 / MinIO
    S3_ENDPOINT_URL: str
    S3_ACCESS_KEY: str
    S3_SECRET_KEY: str
    S3_REGION: str = "us-east-1"
    S3_BUCKET_ADMIN_LAWS: str
    S3_BUCKET_CUSTOMER_DOCS: str

    # Qdrant
    QDRANT_URL: str
    QDRANT_COLLECTION_NAME: str
    QDRANT_VECTOR_SIZE: int = 1536

    # Redis / Arq
    REDIS_URL: AnyUrl = "redis://localhost:6379/0"

    class Config(BaseSettings.Config):
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()