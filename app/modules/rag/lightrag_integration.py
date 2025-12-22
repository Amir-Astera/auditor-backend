"""
Интеграция LightRAG (lightrag-hku) в проект.

ВАЖНО:
- lightrag-hku используется как БИБЛИОТЕКА: никаких отдельных сервисов/портов запускать не нужно.
- Для корректной работы LightRAG embedding_func должен быть экземпляром dataclass EmbeddingFunc.
  Иначе падает с: "replace() should be called on dataclass instances"

Данный модуль:
- безопасно импортирует LightRAG (может отключиться, если пакета нет)
- предоставляет LightRAGService для insert/query
- использует Google GenAI SDK (google-genai) для LLM и Embeddings
- устойчив к ошибкам сети (retries), не вводит в заблуждение логами

ФИКС ДЛЯ ARQ/ASYNCIO:
- LightRAG.insert() внутри делает loop.run_until_complete(...), что падает внутри уже запущенного event loop:
  RuntimeError: This event loop is already running
- Поэтому если asyncio loop уже запущен (arq/uvicorn/FastAPI), выполняем ainsert/aquery
  в ОТДЕЛЬНОМ потоке через asyncio.run().
"""

from __future__ import annotations

import asyncio
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.core.config import settings

logger = logging.getLogger(__name__)

# -----------------------------
# Safe imports: LightRAG
# -----------------------------
try:
    from lightrag import LightRAG as _LightRAG  # type: ignore
    from lightrag import QueryParam as _QueryParam  # type: ignore
    from lightrag.base import EmbeddingFunc as _EmbeddingFunc  # type: ignore

    LIGHTRAG_AVAILABLE = True
except Exception as e:
    _LightRAG = None  # type: ignore
    _QueryParam = None  # type: ignore
    _EmbeddingFunc = None  # type: ignore
    LIGHTRAG_AVAILABLE = False
    logger.warning(
        "LightRAG import failed: %s. LightRAG features will be disabled.", e, exc_info=True
    )

# -----------------------------
# Safe imports: Google GenAI
# -----------------------------
try:
    from google import genai  # type: ignore
except Exception as e:
    genai = None  # type: ignore
    logger.warning("google-genai import failed: %s", e, exc_info=True)


@dataclass(frozen=True)
class LightRAGConfig:
    working_dir: str
    llm_model: str
    embedding_model: str
    embedding_dim: int = 3072
    max_token_size: int = 8192
    send_dimensions: bool = False


class GeminiGenAI:
    """
    Тонкая обёртка над google-genai.
    Создаёт клиент на каждый вызов (статлес), чтобы не держать state/locks в воркере.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        llm_model: Optional[str] = None,
        embedding_model: Optional[str] = None,
        timeout_s: int = 60,
    ) -> None:
        if genai is None:
            raise RuntimeError("google-genai is not installed / import failed")

        self.api_key = api_key
        self.llm_model = llm_model
        self.embedding_model = embedding_model
        self.timeout_s = timeout_s

    def _client(self):
        return genai.Client(api_key=self.api_key)

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type(Exception),
    )
    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        client = self._client()
        model = self.llm_model or "gemini-2.5-flash"
        # google-genai обычно принимает system_instruction отдельно
        # но у тебя в проекте уже есть рабочая схема — оставляем максимально нейтрально:
        full_prompt = prompt if not system_prompt else f"{system_prompt}\n\n{prompt}"

        resp = client.models.generate_content(
            model=model,
            contents=full_prompt,
        )
        # Библиотека возвращает разные структуры, но text — самый частый путь
        return getattr(resp, "text", "") or ""

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type(Exception),
    )
    def embed(self, texts: Sequence[str], dims: Optional[int] = None) -> List[List[float]]:
        client = self._client()
        model = self.embedding_model or "gemini-embedding-001"

        vectors: List[List[float]] = []
        for t in texts:
            if dims is not None:
                resp = client.models.embed_content(
                    model=model,
                    contents=t,
                    config={"output_dimensionality": dims},
                )
            else:
                resp = client.models.embed_content(
                    model=model,
                    contents=t,
                )

            emb = getattr(resp, "embeddings", None)
            if emb and isinstance(emb, list) and len(emb) > 0:
                # типично resp.embeddings[0].values
                v = getattr(emb[0], "values", None)
                if v is None:
                    v = getattr(emb[0], "embedding", None)
                if v is None:
                    raise RuntimeError("Unexpected embedding response shape")
                vectors.append(list(v))
            else:
                # иногда бывает resp.embedding / resp.values
                v = getattr(resp, "values", None) or getattr(resp, "embedding", None)
                if v is None:
                    raise RuntimeError("Unexpected embedding response shape")
                vectors.append(list(v))

        return vectors


class LightRAGService:
    """
    Продакшн-обёртка LightRAG.
    - Если LightRAG/зависимости не установлены, сервис отключается и методы insert/query кидают понятную ошибку.
    - Исправляет проблему "This event loop is already running" внутри arq/asyncio.
    """

    def __init__(
        self,
        config: Optional[LightRAGConfig] = None,
    ) -> None:
        if not LIGHTRAG_AVAILABLE:
            self.cfg = None
            self.working_dir = None  # type: ignore
            self.rag = None
            logger.warning("LightRAG is not available, service is disabled.")
            return

        cfg = config or LightRAGConfig(
            working_dir=getattr(settings, "LIGHTRAG_WORKING_DIR", "./lightrag_cache"),
            llm_model=getattr(settings, "GEMINI_LLM_MODEL", "gemini-2.5-flash"),
            embedding_model=getattr(settings, "GEMINI_EMBED_MODEL", "gemini-embedding-001"),
            embedding_dim=getattr(settings, "GEMINI_EMBED_DIM", 3072),
            max_token_size=getattr(settings, "GEMINI_EMBED_MAX_TOKENS", 8192),
            send_dimensions=getattr(settings, "LIGHTRAG_SEND_DIMENSIONS", False),
        )

        self.cfg = cfg
        self.working_dir = Path(cfg.working_dir)
        self.working_dir.mkdir(parents=True, exist_ok=True)

        # LightRAG пишет в working_dir (граф/кэш). Чтобы избежать гонок при нескольких задачах,
        # сериализуем insert/query через один поток.
        self._executor = ThreadPoolExecutor(max_workers=1)

        self._gemini = GeminiGenAI(
            api_key=getattr(settings, "GEMINI_API_KEY", None),
            llm_model=cfg.llm_model,
            embedding_model=cfg.embedding_model,
        )

        # ---- LLM wrapper for LightRAG (expects callable(prompt, system_prompt?, **kwargs) -> str)
        def llm_wrapper(prompt: str, system_prompt: Optional[str] = None, **kwargs) -> str:
            return self._gemini.generate(prompt=prompt, system_prompt=system_prompt)

        # ---- Embedding wrapper for LightRAG
        # ВАЖНО: LightRAG ожидает EmbeddingFunc(dataclass) и внутри делает dataclasses.replace(...)
        if _EmbeddingFunc is None:
            raise RuntimeError("LightRAG EmbeddingFunc is not available")

        embedding_func = _EmbeddingFunc(  # type: ignore
            embedding_dim=cfg.embedding_dim,
            max_token_size=cfg.max_token_size,
            func=lambda texts: self._gemini.embed(
                texts=texts,
                dims=(cfg.embedding_dim if cfg.send_dimensions else None),
            ),
        )

        self.rag = None
        try:
            self.rag = _LightRAG(
                working_dir=str(self.working_dir),
                llm_model_func=llm_wrapper,
                embedding_func=embedding_func,
            )
            logger.info(
                "LightRAG initialized OK. working_dir=%s llm_model=%s embed_model=%s dim=%s",
                self.working_dir,
                cfg.llm_model,
                cfg.embedding_model,
                cfg.embedding_dim,
            )
        except Exception as e:
            self.rag = None
            logger.error("LightRAG init failed (disabled). error=%s", e, exc_info=True)

    def is_ready(self) -> bool:
        return self.rag is not None

    @staticmethod
    def _loop_is_running() -> bool:
        """True, если сейчас мы внутри уже запущенного asyncio event loop."""
        try:
            asyncio.get_running_loop()
            return True
        except RuntimeError:
            return False

    def insert(self, text: str) -> Any:
        """
        Вставка текста в LightRAG (создание/обогащение KG и индексов внутри LightRAG).
        """
        if not self.rag:
            raise RuntimeError("LightRAG is disabled (init failed). Check logs.")
        if not text or not text.strip():
            raise ValueError("insert(): text is empty")

        # Если мы не внутри running-loop — можно безопасно вызывать синхронный insert()
        if not self._loop_is_running():
            return self.rag.insert(text)

        # Если loop уже запущен (arq/uvicorn/FastAPI) — внутри LightRAG.insert есть run_until_complete,
        # что приводит к: RuntimeError('This event loop is already running').
        # Поэтому выполняем ainsert() в отдельном потоке через asyncio.run().
        def _run_in_thread():
            if hasattr(self.rag, "ainsert"):
                return asyncio.run(self.rag.ainsert(text))
            # fallback на синхронный insert (в отдельном потоке)
            return self.rag.insert(text)

        return self._executor.submit(_run_in_thread).result()

    def query(self, question: str, mode: str = "hybrid", top_k: int = 5, **kwargs) -> Dict[str, Any]:
        """
        Запрос к LightRAG.
        Возвращает унифицированный dict.
        """
        if not self.rag:
            raise RuntimeError("LightRAG is disabled (init failed). Check logs.")
        if _QueryParam is None:
            raise RuntimeError("LightRAG QueryParam is not available")

        qp = _QueryParam(
            question=question,
            mode=mode,
            top_k=top_k,
            **kwargs,
        )

        if not self._loop_is_running():
            result = self.rag.query(qp)
        else:
            def _run_query_in_thread():
                if hasattr(self.rag, "aquery"):
                    return asyncio.run(self.rag.aquery(qp))
                return self.rag.query(qp)

            result = self._executor.submit(_run_query_in_thread).result()

        if isinstance(result, dict):
            return {
                "answer": result.get("answer", ""),
                "context": result.get("context", []),
                "nodes": result.get("nodes", []),
                "edges": result.get("edges", []),
            }

        return {"answer": str(result), "context": [], "nodes": [], "edges": []}

    def close(self) -> None:
        """Аккуратно закрыть thread pool (если нужно при shutdown)."""
        try:
            self._executor.shutdown(wait=True, cancel_futures=True)
        except Exception:
            pass


def create_lightrag_service(
    working_dir: Optional[str] = None,
) -> LightRAGService:
    """
    Фабрика. Можно подменить working_dir для тестов.
    """
    cfg = LightRAGConfig(
        working_dir=working_dir or getattr(settings, "LIGHTRAG_WORKING_DIR", "./lightrag_cache"),
        llm_model=getattr(settings, "GEMINI_LLM_MODEL", "gemini-2.5-flash"),
        embedding_model=getattr(settings, "GEMINI_EMBED_MODEL", "gemini-embedding-001"),
        embedding_dim=getattr(settings, "GEMINI_EMBED_DIM", 3072),
        max_token_size=getattr(settings, "GEMINI_EMBED_MAX_TOKENS", 8192),
        send_dimensions=getattr(settings, "LIGHTRAG_SEND_DIMENSIONS", False),
    )
    return LightRAGService(config=cfg)
