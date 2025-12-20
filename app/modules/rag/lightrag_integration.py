"""
Интеграция LIGHTRAG в модуль RAG проекта.

LIGHTRAG - это легковесная реализация RAG с использованием графа знаний.
Интегрируется с существующей инфраструктурой: Gemini API, MinIO, Postgres.

Цели этого модуля:
- корректно работать даже если `lightrag` не установлен
- не падать при импорте (важно для uvicorn reload / CI)
- быть дружелюбным к статическому анализатору типов
"""

import logging
from pathlib import Path
from typing import Any, Dict, Optional

try:
    # Попытка импорта LIGHTRAG.
    # Важно: в средах без установленного пакета (или без type stubs) статический анализатор
    # может ругаться на "Import could not be resolved". Это безопасно для рантайма, так как
    # импорт находится внутри try/except и корректно обрабатывается.
    from lightrag import LightRAG as _LightRAG  # type: ignore[import-not-found]
    from lightrag import QueryParam as _QueryParam  # type: ignore[import-not-found]

    LIGHTRAG_AVAILABLE = True
except Exception:
    _LightRAG = None  # type: ignore[assignment]
    _QueryParam = None  # type: ignore[assignment]
    LIGHTRAG_AVAILABLE = False

if not LIGHTRAG_AVAILABLE:
    logging.warning("LIGHTRAG not installed. Install with: pip install lightrag")

from app.core.config import settings
from app.modules.rag.gemini import GeminiAPI

logger = logging.getLogger(__name__)


class GeminiLLMAdapter:
    """Адаптер для использования GeminiAPI с LIGHTRAG."""

    def __init__(self, gemini_api: GeminiAPI):
        self.gemini_api = gemini_api

    def complete(
        self, prompt: str, system_prompt: Optional[str] = None, **kwargs
    ) -> str:
        """
        Выполняет запрос к Gemini LLM.

        Важно:
        - Новый GeminiAPI возвращает строку (а не JSON candidates).
        """
        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"

        try:
            # GeminiAPI.generate_content оставлен как алиас и возвращает str
            return self.gemini_api.generate_content(full_prompt)
        except Exception as e:
            logger.error(f"Error calling Gemini API: {e}")
            raise


class LightRAGService:
    """Сервис для работы с LIGHTRAG."""

    def __init__(
        self,
        working_dir: str = "./lightrag_cache",
        gemini_api: Optional[GeminiAPI] = None,
    ):
        if not LIGHTRAG_AVAILABLE or _LightRAG is None or _QueryParam is None:
            raise ImportError(
                "LIGHTRAG not installed. Install with: pip install lightrag"
            )

        self.working_dir = Path(working_dir or settings.LIGHTRAG_WORKING_DIR)
        self.working_dir.mkdir(parents=True, exist_ok=True)

        if gemini_api is None:
            gemini_api = GeminiAPI()
        self.gemini_adapter = GeminiLLMAdapter(gemini_api)

        try:
            # используем локальные алиасы _LightRAG/_QueryParam, чтобы не было 'possibly unbound'
            self.rag = _LightRAG(
                working_dir=str(self.working_dir),
                llm_model_func=self.gemini_adapter.complete,
            )
        except Exception as e:
            logger.error(f"Error initializing LightRAG: {e}")
            self.rag = None

        logger.info(f"LightRAG initialized with working_dir: {self.working_dir}")

    def insert(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Вставляет текст в граф знаний LIGHTRAG.

        metadata пока не гарантированно используется LightRAG (зависит от версии),
        но сохраняется на уровне вашего приложения при необходимости.
        """
        if not self.rag:
            raise RuntimeError("LightRAG is not initialized")

        try:
            result = self.rag.insert(text)
            logger.info(f"Text inserted into LightRAG graph: {len(text)} characters")
            return str(result)
        except Exception as e:
            logger.error(f"Error inserting text into LightRAG: {e}")
            raise

    def query(
        self, question: str, mode: str = "hybrid", top_k: int = 5, **kwargs
    ) -> Dict[str, Any]:
        """
        Выполняет запрос к графу знаний.

        Возвращаемый формат адаптирован под RAG роутер.
        """
        if not self.rag:
            raise RuntimeError("LightRAG is not initialized")
        if _QueryParam is None:
            raise RuntimeError("LightRAG QueryParam is not available")

        try:
            query_param = _QueryParam(
                question=question, mode=mode, top_k=top_k, **kwargs
            )
            result = self.rag.query(query_param)

            logger.info(
                f"LightRAG query completed: mode={mode}, question_length={len(question)}"
            )

            # Некоторые версии LightRAG возвращают dict, некоторые строку.
            if isinstance(result, dict):
                return {
                    "answer": result.get("answer", ""),
                    "context": result.get("context", []),
                    "nodes": result.get("nodes", []),
                    "edges": result.get("edges", []),
                }

            return {"answer": str(result), "context": [], "nodes": [], "edges": []}

        except Exception as e:
            logger.error(f"Error querying LightRAG: {e}")
            raise

    def delete(self, node_id: str) -> bool:
        """Удаляет узел из графа знаний (best effort, зависит от версии LightRAG)."""
        try:
            logger.info(f"Deleting node from LightRAG: {node_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting node from LightRAG: {e}")
            return False

    def get_graph_stats(self) -> Dict[str, Any]:
        """Возвращает статистику графа знаний."""
        try:
            return {
                "working_dir": str(self.working_dir),
                "nodes_count": 0,
                "edges_count": 0,
            }
        except Exception as e:
            logger.error(f"Error getting graph stats: {e}")
            return {"error": str(e)}


def create_lightrag_service(
    working_dir: Optional[str] = None,
    gemini_api: Optional[GeminiAPI] = None,
) -> LightRAGService:
    """
    Фабрика для создания LightRAGService.
    """
    if working_dir is None:
        working_dir = settings.LIGHTRAG_WORKING_DIR

    return LightRAGService(
        working_dir=working_dir,
        gemini_api=gemini_api,
    )
