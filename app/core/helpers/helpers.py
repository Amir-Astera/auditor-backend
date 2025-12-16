from __future__ import annotations

from arq.connections import ArqRedis, RedisSettings, create_pool

from app.core.config import settings

_redis_pool: ArqRedis | None = None


async def get_arq_redis() -> ArqRedis:
    """

    Ленивая инициализация пула соединений к Redis для Arq

    из кода приложения (FastAPI).

    """

    global _redis_pool

    if _redis_pool is None:
        # settings.REDIS_URL — это AnyUrl из Pydantic, Arq ожидает либо строку,
        # либо RedisSettings. Приводим к строке и создаём RedisSettings.
        redis_settings = RedisSettings.from_dsn(str(settings.REDIS_URL))
        _redis_pool = await create_pool(redis_settings)
    return _redis_pool
