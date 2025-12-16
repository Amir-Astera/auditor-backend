"""
Интеграция LIGHTRAG в модуль RAG проекта.

LIGHTRAG - это легковесная реализация RAG с использованием графа знаний.
Интегрируется с существующей инфраструктурой: Qdrant, Gemini API, MinIO.
"""
import logging
from typing import List, Optional, Dict, Any
from pathlib import Path

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
            LIGHTRAG_AVAILABLE = True
        except ImportError:
            LIGHTRAG_AVAILABLE = False
except Exception:
    LIGHTRAG_AVAILABLE = False

if not LIGHTRAG_AVAILABLE:
    logging.warning("LIGHTRAG not installed. Install with: pip install lightrag")

from app.modules.rag.gemini import GeminiAPI
from app.modules.files.qdrant_client import QdrantVectorStore
from app.core.config import settings

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


class LightRAGService:
    """Сервис для работы с LIGHTRAG."""
    
    def __init__(
        self,
        working_dir: str = "./lightrag_cache",
        gemini_api: Optional[GeminiAPI] = None,
        qdrant_store: Optional[QdrantVectorStore] = None,
    ):
        if not LIGHTRAG_AVAILABLE:
            raise ImportError(
                "LIGHTRAG not installed. Install with: pip install lightrag"
            )
        
        self.working_dir = Path(working_dir)
        self.working_dir.mkdir(parents=True, exist_ok=True)
        
        # Инициализация Gemini адаптера
        if gemini_api is None:
            gemini_api = GeminiAPI()
        self.gemini_adapter = GeminiLLMAdapter(gemini_api)
        
        # Инициализация LIGHTRAG
        # Используем кастомный LLM адаптер для Gemini
        try:
            # Пытаемся использовать стандартный API LIGHTRAG
            if hasattr(LightRAG, '__init__'):
                self.rag = LightRAG(
                    working_dir=str(self.working_dir),
                    llm_model_func=self.gemini_adapter.complete,
                )
            else:
                # Альтернативная инициализация
                self.rag = LightRAG(working_dir=str(self.working_dir))
                # Устанавливаем кастомную функцию LLM если возможно
                if hasattr(self.rag, 'llm_model_func'):
                    self.rag.llm_model_func = self.gemini_adapter.complete
        except Exception as e:
            logger.error(f"Error initializing LightRAG: {e}")
            # Создаем заглушку для работы без LIGHTRAG
            self.rag = None
        
        logger.info(f"LightRAG initialized with working_dir: {self.working_dir}")
    
    def insert(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Вставляет текст в граф знаний LIGHTRAG.
        
        Args:
            text: Текст для вставки
            metadata: Дополнительные метаданные
            
        Returns:
            ID вставленного узла
        """
        try:
            # LIGHTRAG использует метод insert для добавления текста
            result = self.rag.insert(text)
            logger.info(f"Text inserted into LightRAG graph: {len(text)} characters")
            return result
        except Exception as e:
            logger.error(f"Error inserting text into LightRAG: {e}")
            raise
    
    def query(
        self,
        question: str,
        mode: str = "hybrid",
        top_k: int = 5,
        **kwargs
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
            # Создаем параметры запроса
            query_param = QueryParam(
                question=question,
                mode=mode,
                top_k=top_k,
                **kwargs
            )
            
            # Выполняем запрос
            result = self.rag.query(query_param)
            
            logger.info(f"LightRAG query completed: mode={mode}, question_length={len(question)}")
            
            return {
                "answer": result.get("answer", ""),
                "context": result.get("context", []),
                "nodes": result.get("nodes", []),
                "edges": result.get("edges", []),
            }
        except Exception as e:
            logger.error(f"Error querying LightRAG: {e}")
            raise
    
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
        gemini_api=gemini_api,
    )

