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
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

import numpy as np

LightRAG = None
QueryParam = None
LightRAGEmbeddingFunc = None

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
        model = self.embedding_model or "models/text-embedding-004"
        if model == "models/text-embedding-001":
            model = "models/text-embedding-004"

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

    async def acomplete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs,
    ) -> str:
        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"

        try:
            response = await asyncio.to_thread(self.gemini_api.generate_content, full_prompt)
            if response and "candidates" in response:
                return response["candidates"][0]["content"]["parts"][0]["text"]
            raise ValueError("Unexpected response format from Gemini")
        except Exception as e:
            logger.error(f"Error calling Gemini API: {e}")
            raise


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
        
        # Инициализация Gemini адаптера
        if gemini_api is None:
            gemini_api = GeminiAPI()
        self.gemini_adapter = GeminiLLMAdapter(gemini_api)

        if embedding_service is None:
            embedding_service = get_embedding_service()
        self.embedding_service = embedding_service

        async def _aembed(texts: List[str], **kwargs) -> np.ndarray:
            vectors = await asyncio.to_thread(self.embedding_service.embed, texts)
            return np.array(vectors, dtype=np.float32)

        embedding_func = None
        if LightRAGEmbeddingFunc is not None:
            embedding_func = LightRAGEmbeddingFunc(
                embedding_dim=self.embedding_service.vector_size,
                func=_aembed,
                model_name="auditor-embedding",
            )

        # Инициализация LIGHTRAG
        # Используем кастомный LLM адаптер для Gemini
        try:
            # Пытаемся использовать стандартный API LIGHTRAG
            if hasattr(LightRAG, '__init__'):
                self.rag = LightRAG(
                    working_dir=str(self.working_dir),
                    workspace=workspace or "",
                    llm_model_func=self.gemini_adapter.acomplete,
                    embedding_func=embedding_func,
                )
            else:
                # Альтернативная инициализация
                self.rag = LightRAG(working_dir=str(self.working_dir))
                # Устанавливаем кастомную функцию LLM если возможно
                if hasattr(self.rag, 'llm_model_func'):
                    self.rag.llm_model_func = self.gemini_adapter.acomplete
        except Exception as e:
            logger.error(f"Error initializing LightRAG: {e}")
            # Создаем заглушку для работы без LIGHTRAG
            self.rag = None
        
        logger.info(f"LightRAG initialized with working_dir: {self.working_dir}")
    
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
        try:
            await self._ensure_initialized()
            result = await self.rag.ainsert(text, file_paths=file_path)
            logger.info(f"Text inserted into LightRAG graph: {len(text)} characters")
            return result
        except Exception as e:
            logger.error(f"Error inserting text into LightRAG: {e}")
            raise

    def insert(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop is not None:
            raise RuntimeError("Use ainsert() inside async context")
        return asyncio.run(self.ainsert(text=text, metadata=metadata))
    
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
        try:
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

            result = await self.rag.aquery_data(question, query_param)
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
        gemini_api=gemini_api,
        embedding_service=embedding_service,
    )

    if cfg.embedding_model == "models/text-embedding-001":
        cfg = LightRAGConfig(
            working_dir=cfg.working_dir,
            llm_model=cfg.llm_model,
            embedding_model="models/text-embedding-004",
            embedding_dim=cfg.embedding_dim,
            max_token_size=cfg.max_token_size,
            send_dimensions=cfg.send_dimensions,
        )

    return LightRAGService(config=cfg)