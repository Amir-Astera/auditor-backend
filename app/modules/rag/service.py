"""RAG service with LIGHTRAG integration."""
import logging
from typing import Optional, Dict, Any

from app.modules.rag.gemini import GeminiAPI
from app.modules.rag.lightrag_integration import LightRAGService, create_lightrag_service
from app.core.config import settings

logger = logging.getLogger(__name__)


class RAGService:
    """Сервис для работы с RAG (Retrieval-Augmented Generation)."""
    
    def __init__(
        self,
        gemini_api: Optional[GeminiAPI] = None,
        lightrag_working_dir: Optional[str] = None,
    ):
        """
        Инициализация RAG сервиса.
        
        Args:
            gemini_api: Экземпляр GeminiAPI
            lightrag_working_dir: Директория для кэша LIGHTRAG
        """
        if gemini_api is None:
            gemini_api = GeminiAPI()
        
        self.gemini_api = gemini_api
        
        # Инициализация LIGHTRAG (опционально)
        self.lightrag = None
        try:
            self.lightrag = create_lightrag_service(
                working_dir=lightrag_working_dir or "./lightrag_cache",
                gemini_api=gemini_api,
            )
            logger.info("LIGHTRAG service initialized successfully")
        except ImportError as e:
            logger.warning(f"LIGHTRAG not available (install with: pip install lightrag>=0.1.0b1): {e}")
            self.lightrag = None
        except Exception as e:
            logger.error(f"Failed to initialize LIGHTRAG: {e}")
            self.lightrag = None
    
    def query(
        self,
        question: str,
        mode: str = "hybrid",
        top_k: int = 5,
    ) -> Dict[str, Any]:
        """
        Выполняет запрос к RAG системе.
        
        Args:
            question: Вопрос пользователя
            mode: Режим запроса (naive, local, global, hybrid)
            top_k: Количество результатов
            
        Returns:
            Словарь с ответом и контекстом
        """
        if not self.lightrag:
            # Fallback на простой запрос к Gemini
            logger.warning("LIGHTRAG not available, using direct Gemini query")
            response = self.gemini_api.generate_content(question)
            if response and 'candidates' in response:
                answer = response['candidates'][0]['content']['parts'][0]['text']
                return {
                    "answer": answer,
                    "context": [],
                    "nodes": [],
                    "edges": [],
                    "mode": "direct",
                }
            raise ValueError("Failed to get response from Gemini")
        
        try:
            result = self.lightrag.query(
                question=question,
                mode=mode,
                top_k=top_k,
            )
            result["mode"] = mode
            return result
        except Exception as e:
            logger.error(f"Error in RAG query: {e}")
            raise
    
    def insert_text(
        self,
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Вставляет текст в граф знаний.
        
        Args:
            text: Текст для вставки
            metadata: Метаданные документа
            
        Returns:
            Информация о созданном узле
        """
        if not self.lightrag:
            raise RuntimeError("LIGHTRAG service not available")
        
        try:
            node_id = self.lightrag.insert(text, metadata=metadata)
            return {
                "node_id": node_id,
                "success": True,
            }
        except Exception as e:
            logger.error(f"Error inserting text into RAG: {e}")
            raise
    
    def delete_node(self, node_id: str) -> Dict[str, Any]:
        """
        Удаляет узел из графа знаний.
        
        Args:
            node_id: ID узла для удаления
            
        Returns:
            Результат удаления
        """
        if not self.lightrag:
            raise RuntimeError("LIGHTRAG service not available")
        
        try:
            success = self.lightrag.delete(node_id)
            return {
                "success": success,
                "node_id": node_id,
            }
        except Exception as e:
            logger.error(f"Error deleting node from RAG: {e}")
            raise
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Возвращает статистику графа знаний.
        
        Returns:
            Статистика графа
        """
        if not self.lightrag:
            return {
                "nodes_count": 0,
                "edges_count": 0,
                "working_dir": "N/A",
                "status": "not_available",
            }
        
        try:
            stats = self.lightrag.get_graph_stats()
            stats["status"] = "available"
            return stats
        except Exception as e:
            logger.error(f"Error getting RAG stats: {e}")
            return {
                "nodes_count": 0,
                "edges_count": 0,
                "working_dir": "N/A",
                "status": "error",
                "error": str(e),
            }

