# app/core/config.py
from pydantic import AnyUrl, BaseSettings, PostgresDsn


class Settings(BaseSettings):
    # Database
    DATABASE_URL: PostgresDsn

    # Security
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    JWT_ALGORITHM: str = "HS256"
    TELEGRAM_BOT_TOKEN: str | None = None

    # S3 / MinIO
    S3_ENDPOINT_URL: str
    S3_ACCESS_KEY: str
    S3_SECRET_KEY: str
    S3_REGION: str = "us-east-1"
    S3_BUCKET_ADMIN_LAWS: str
    S3_BUCKET_CUSTOMER_DOCS: str

    # Redis / Arq
    REDIS_URL: AnyUrl = "redis://localhost:6379/0"

    # Gemini AI
    GEMINI_API_KEY: str

    # LightRAG
    LIGHTRAG_WORKING_DIR: str = "./lightrag_cache"
    LIGHTRAG_EMBEDDING_MODEL: str = "models/text-embedding-004"
    LIGHTRAG_LLM_MODEL: str = "gemini-1.5-pro"

    # Indexing configuration
    CHUNK_SIZE: int = 1500  # символов
    MERGE_SIZE: int = 5  # чанков в один блок для LightRAG
    QDRANT_BATCH_SIZE: int = 256
    EMBEDDING_BATCH_SIZE: int = 32

    class Config(BaseSettings.Config):
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
