from __future__ import annotations

from arq.connections import create_pool, ArqRedis

from app.core.config import settings

_redis_pool: ArqRedis | None = None


async def get_arq_redis() -> ArqRedis:
    """
    Ленивая инициализация пула соединений к Redis для Arq
    из кода приложения (FastAPI).
    """
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = await create_pool(settings.REDIS_URL)
    return _redis_pool
