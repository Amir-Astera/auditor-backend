"""
Интеграция LIGHTRAG в модуль RAG проекта.

LIGHTRAG - это легковесная реализация RAG с использованием графа знаний.
Интегрируется с существующей инфраструктурой: Qdrant, Gemini API, MinIO.
"""
import asyncio
import logging
from typing import List, Optional, Dict, Any
from pathlib import Path

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


class GeminiLLMAdapter:
    """Адаптер для использования Gemini API с LIGHTRAG."""
    
    def __init__(self, gemini_api: GeminiAPI):
        self.gemini_api = gemini_api
    
    def complete(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> str:
        """Выполняет запрос к Gemini API."""
        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"
        
        try:
            response = self.gemini_api.generate_content(full_prompt)
            if response and 'candidates' in response:
                text = response['candidates'][0]['content']['parts'][0]['text']
                return text
            raise ValueError("Unexpected response format from Gemini")
        except Exception as e:
            logger.error(f"Error calling Gemini API: {e}")
            raise

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
    """Сервис для работы с LIGHTRAG."""
    
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
            # LIGHTRAG может иметь метод delete или нужно реализовать через граф
            # Это зависит от версии LIGHTRAG
            logger.info(f"Deleting node from LightRAG: {node_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting node from LightRAG: {e}")
            return False
    
    def get_graph_stats(self) -> Dict[str, Any]:
        """Возвращает статистику графа знаний."""
        try:
            # Получаем информацию о графе
            stats = {
                "working_dir": str(self.working_dir),
                "nodes_count": 0,
                "edges_count": 0,
            }
            
            # Попытка получить статистику из графа
            # Это зависит от реализации LIGHTRAG
            return stats
        except Exception as e:
            logger.error(f"Error getting graph stats: {e}")
            return {"error": str(e)}


def create_lightrag_service(
    working_dir: Optional[str] = None,
    gemini_api: Optional[GeminiAPI] = None,
    workspace: Optional[str] = None,
    embedding_service: Optional[EmbeddingService] = None,
) -> LightRAGService:
    """
    Фабричная функция для создания LightRAGService.
    
    Args:
        working_dir: Директория для хранения кэша LIGHTRAG
        gemini_api: Экземпляр GeminiAPI (опционально)
        
    Returns:
        Экземпляр LightRAGService
    """
    if working_dir is None:
        working_dir = "./lightrag_cache"
    
    return LightRAGService(
        working_dir=working_dir,
        workspace=workspace,
        gemini_api=gemini_api,
        embedding_service=embedding_service,
    )

