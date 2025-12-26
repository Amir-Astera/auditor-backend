# app/core/config.py
from pydantic import AnyUrl, PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

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
    # Используем str вместо AnyUrl, чтобы избежать ложных срабатываний статического анализатора
    # и не привязываться к pydantic типам URL (Arq всё равно принимает DSN как строку).
    REDIS_URL: str = "redis://localhost:6379/0"

    # Gemini AI
    GEMINI_API_KEY: str

    # LightRAG
    LIGHTRAG_WORKING_DIR: str = "./lightrag_cache"
    LIGHTRAG_EMBEDDING_MODEL: str = "models/text-embedding-004"
    LIGHTRAG_LLM_MODEL: str = "gemini-2.5-flash"
    LIGHTRAG_EMBED_DIM: int = 3072
    LIGHTRAG_EMBED_MAX_TOKENS: int = 8192
    LIGHTRAG_SEND_DIMENSIONS: bool = False

    # Qdrant (Hybrid RAG)
    QDRANT_URL: str
    QDRANT_COLLECTION_NAME: str
    QDRANT_VECTOR_SIZE: int = 768  # Gemini embedding size
    QDRANT_CHAT_MEMORY_COLLECTION: str = "chat_memory"

    # Indexing configuration
    CHUNK_SIZE: int = 1500  # символов
    MERGE_SIZE: int = 5  # чанков в один блок для LightRAG
    QDRANT_BATCH_SIZE: int = 256
    EMBEDDING_BATCH_SIZE: int = 32

    # Gemini API
    GEMINI_API_KEY: str | None = None
    GEMINI_MODEL: str = "gemini-2.0-flash"
    GEMINI_EMBEDDING_MODEL: str = "text-embedding-004"

    # OpenAI API (fallback)
    OPENAI_API_KEY: str | None = None

    # RAG Settings
    RAG_MAX_CONTEXT_TOKENS: int = 12000
    RAG_DEFAULT_TOP_K: int = 10
    RAG_RERANK_ENABLED: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
