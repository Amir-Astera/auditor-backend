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
import asyncio
import logging
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

import numpy as np
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

LightRAG = None
QueryParam = None
LightRAGEmbeddingFunc = None

# Prefer local vendored LightRAG (./LightRAG) if present.
_vendored_lightrag_root: Path | None = None
for _p in Path(__file__).resolve().parents:
    _candidate = _p / "LightRAG"
    if _candidate.exists():
        _vendored_lightrag_root = _candidate
        break

if _vendored_lightrag_root is not None:
    _vendored_str = str(_vendored_lightrag_root)
    if _vendored_str not in sys.path:
        sys.path.insert(0, _vendored_str)

try:
    # Попытка импорта LIGHTRAG
    # Если библиотека называется по-другому, нужно будет скорректировать
    try:
        from lightrag import LightRAG, QueryParam
        LIGHTRAG_AVAILABLE = True
    except ImportError:
        # Альтернативные варианты импорта
        try:
            import lightrag
            LightRAG = getattr(lightrag, "LightRAG", None)
            QueryParam = getattr(lightrag, "QueryParam", None)
            LIGHTRAG_AVAILABLE = LightRAG is not None and QueryParam is not None
        except ImportError:
            LIGHTRAG_AVAILABLE = False
except Exception:
    LIGHTRAG_AVAILABLE = False

if LIGHTRAG_AVAILABLE:
    try:
        from lightrag.utils import EmbeddingFunc as LightRAGEmbeddingFunc
    except Exception:
        LightRAGEmbeddingFunc = None

if not LIGHTRAG_AVAILABLE:
    logging.getLogger(__name__).debug("LIGHTRAG not installed. Install with: pip install lightrag")

from app.modules.rag.gemini import GeminiAPI
from app.modules.files.qdrant_client import QdrantVectorStore
from app.core.config import settings
from app.modules.embeddings.service import EmbeddingService, get_embedding_service

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


async def _lightrag_llm_complete(
    prompt: str,
    system_prompt: Optional[str] = None,
    **kwargs,
) -> str:
    full_prompt = prompt if not system_prompt else f"{system_prompt}\n\n{prompt}"
    gemini = GeminiAPI()
    return await asyncio.to_thread(gemini.generate_text, full_prompt)


async def _lightrag_aembed(texts: List[str], **kwargs) -> np.ndarray:
    embedding_service = get_embedding_service()
    vectors = await asyncio.to_thread(embedding_service.embed, texts)
    return np.array(vectors, dtype=np.float32)


class LightRAGService:
    """
    Продакшн-обёртка LightRAG.
    - Если LightRAG/зависимости не установлены, сервис отключается и методы insert/query кидают понятную ошибку.
    - Исправляет проблему "This event loop is already running" внутри arq/asyncio.
    """

    def __init__(
        self,
        working_dir: str = "./lightrag_cache",
        workspace: Optional[str] = None,
        gemini_api: Optional[GeminiAPI] = None,
        qdrant_store: Optional[QdrantVectorStore] = None,
        embedding_service: Optional[EmbeddingService] = None,
    ):
        if not LIGHTRAG_AVAILABLE:
            raise ImportError(
                "LIGHTRAG not installed. Install with: pip install lightrag"
            )

        if LightRAG is None:
            raise ImportError(
                "LIGHTRAG is installed but LightRAG symbol is not available in this package version"
            )
        
        self.working_dir = Path(working_dir)
        self.working_dir.mkdir(parents=True, exist_ok=True)
        
        self._executor = ThreadPoolExecutor(max_workers=1)

        if os.getenv("MAX_ASYNC") is None:
            os.environ["MAX_ASYNC"] = "1"
        if os.getenv("MAX_PARALLEL_INSERT") is None:
            os.environ["MAX_PARALLEL_INSERT"] = "1"

        self._loop: asyncio.AbstractEventLoop | None = None
        self._loop_thread: threading.Thread | None = None
        self._loop_ready = threading.Event()

        def _loop_runner() -> None:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self._loop = loop
            self._loop_ready.set()
            loop.run_forever()

        self._loop_thread = threading.Thread(target=_loop_runner, name="lightrag-loop", daemon=True)
        self._loop_thread.start()
        self._loop_ready.wait(timeout=10)
        
        self.rag = None

        embedding_func = None
        if LightRAGEmbeddingFunc is not None:
            embedding_func = LightRAGEmbeddingFunc(
                embedding_dim=get_embedding_service().vector_size,
                func=_lightrag_aembed,
                model_name="auditor-embedding",
            )

        try:
            if hasattr(LightRAG, "__init__"):
                self.rag = LightRAG(
                    working_dir=str(self.working_dir),
                    workspace=workspace or "",
                    llm_model_func=_lightrag_llm_complete,
                    embedding_func=embedding_func,
                )
            else:
                self.rag = LightRAG(working_dir=str(self.working_dir))
                if hasattr(self.rag, "llm_model_func"):
                    self.rag.llm_model_func = _lightrag_llm_complete
        except Exception as e:
            logger.error(f"Error initializing LightRAG: {e}")
            self.rag = None

        if self.rag is not None:
            logger.info(f"LightRAG initialized with working_dir: {self.working_dir}")

    def _submit(self, coro: "asyncio.Future") -> Any:
        if self._loop is None:
            raise RuntimeError("LightRAG loop is not initialized")
        fut = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return fut.result()

    async def _ensure_initialized(self) -> None:
        if self.rag is None:
            raise RuntimeError("LightRAG is not initialized")

        try:
            await self.rag.initialize_storages()
        except Exception:
            return

    async def ainsert(
        self,
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
        file_path: Optional[str] = None,
    ) -> str:
        """
        Вставляет текст в граф знаний LIGHTRAG.
        
        Args:
            text: Текст для вставки
            metadata: Дополнительные метаданные
            
        Returns:
            ID вставленного узла
        """
        def _run() -> str:
            async def _coro() -> str:
                await self._ensure_initialized()
                return await self.rag.ainsert(text, file_paths=file_path)

            return str(self._submit(_coro()))

        try:
            result = await asyncio.to_thread(_run)
            logger.info(f"Text inserted into LightRAG graph: {len(text)} characters")
            return result
        except Exception as e:
            logger.error(f"Error inserting text into LightRAG: {e}")
            raise

    def insert(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        async def _coro() -> str:
            await self._ensure_initialized()
            return await self.rag.ainsert(text, file_paths=None)

        return str(self._submit(_coro()))
    
    async def aquery_data(
        self,
        question: str,
        mode: str = "hybrid",
        top_k: int = 5,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Выполняет запрос к графу знаний.
        
        Args:
            question: Вопрос пользователя
            mode: Режим запроса ("naive", "local", "global", "hybrid")
            top_k: Количество возвращаемых результатов
            
        Returns:
            Словарь с ответом и контекстом
        """
        def _run() -> Dict[str, Any]:
            async def _coro() -> Dict[str, Any]:
                if QueryParam is None:
                    raise ImportError(
                        "LIGHTRAG is installed but QueryParam symbol is not available in this package version"
                    )
                if self.rag is None:
                    raise RuntimeError("LightRAG is not initialized")

                await self._ensure_initialized()

                query_param = QueryParam(
                    mode=mode,
                    top_k=top_k,
                    **kwargs,
                )

                return await self.rag.aquery_data(question, query_param)

            return self._submit(_coro())

        try:
            result = await asyncio.to_thread(_run)
            logger.info(f"LightRAG query_data completed: mode={mode}, question_length={len(question)}")
            return result
        except Exception as e:
            logger.error(f"Error querying LightRAG: {e}")
            raise

    async def aquery_hints(
        self,
        question: str,
        mode: str = "hybrid",
        top_k: int = 5,
        **kwargs,
    ) -> Dict[str, Any]:
        result = await self.aquery_data(question=question, mode=mode, top_k=top_k, **kwargs)
        data = result.get("data") or {}
        meta = result.get("metadata") or {}

        entities = data.get("entities") or []
        relationships = data.get("relationships") or []
        chunks = data.get("chunks") or []

        return {
            "keywords": meta.get("keywords") or {},
            "entities": entities[:20],
            "relationships": relationships[:20],
            "chunks": chunks[:5],
        }
    
    def query(
        self,
        question: str,
        mode: str = "hybrid",
        top_k: int = 5,
        **kwargs,
    ) -> Dict[str, Any]:
        """Synchronous wrapper around aquery_data (runs on the dedicated LightRAG loop)."""

        async def _coro() -> Dict[str, Any]:
            return await self.aquery_data(question=question, mode=mode, top_k=top_k, **kwargs)

        return self._submit(_coro())
    
    def delete(self, node_id: str) -> bool:
        """
        Удаляет узел из графа знаний.
        
        Args:
            node_id: ID узла для удаления
            
        Returns:
            True если удаление успешно
        """
        try:
            self._executor.shutdown(wait=True, cancel_futures=True)
        except Exception:
            pass

        try:
            if self._loop is not None:
                self._loop.call_soon_threadsafe(self._loop.stop)
        except Exception:
            pass

    def get_graph_stats(self) -> Dict[str, Any]:
        """Best-effort graph stats for /rag/stats."""
        if not self.rag:
            return {"nodes_count": 0, "edges_count": 0, "working_dir": str(self.working_dir)}

        nodes_count = 0
        edges_count = 0
        try:
            # Some versions expose graph_storage with NetworkX-like graph.
            gs = getattr(self.rag, "graph_storage", None)
            g = getattr(gs, "graph", None) if gs is not None else getattr(self.rag, "graph", None)
            if g is not None:
                nodes_count = int(getattr(g, "number_of_nodes")()) if callable(getattr(g, "number_of_nodes", None)) else int(len(getattr(g, "nodes", [])))
                edges_count = int(getattr(g, "number_of_edges")()) if callable(getattr(g, "number_of_edges", None)) else int(len(getattr(g, "edges", [])))
        except Exception:
            logger.exception("Failed to compute LightRAG graph stats")

        return {
            "nodes_count": nodes_count,
            "edges_count": edges_count,
            "working_dir": str(self.working_dir),
        }


def create_lightrag_service(
    working_dir: Optional[str] = None,
    gemini_api: Optional[GeminiAPI] = None,
    workspace: Optional[str] = None,
    embedding_service: Optional[EmbeddingService] = None,
) -> LightRAGService:
    """
    Фабрика. Можно подменить working_dir для тестов.
    """
    if working_dir is None:
        working_dir = "./lightrag_cache"
    
    return LightRAGService(
        working_dir=working_dir,
        workspace=workspace,
    )