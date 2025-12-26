"""RAG service with EnhancedRAGPipeline integration."""
import asyncio
import logging
from typing import Optional, Dict, Any, List

from sqlalchemy.orm import Session

from app.modules.rag.gemini import GeminiAPI
from app.modules.rag.lightrag_integration import LightRAGService, create_lightrag_service
from app.modules.rag.enhanced_pipeline import EnhancedRAGPipeline
from app.modules.files.qdrant_client import QdrantVectorStore
from app.modules.files.models import FileScope, FileChunk, StoredFile
from app.modules.embeddings.service import get_embedding_service
from app.core.config import settings

logger = logging.getLogger(__name__)


class RAGService:
    """Сервис для работы с RAG (Retrieval-Augmented Generation) с улучшенным пайплайном."""
    
    def __init__(
        self,
        db: Optional[Session] = None,
        gemini_api: Optional[GeminiAPI] = None,
        lightrag_working_dir: Optional[str] = None,
        qdrant_store: Optional[QdrantVectorStore] = None,
        qdrant_store_admin: Optional[QdrantVectorStore] = None,
        qdrant_store_client: Optional[QdrantVectorStore] = None,
        prompts_db: Optional[Any] = None,
        use_enhanced_pipeline: bool = True,
    ):
        """
        Инициализация RAG сервиса.
        
        Args:
            gemini_api: Экземпляр GeminiAPI
            lightrag_working_dir: Директория для кэша LIGHTRAG
            qdrant_store: Экземпляр QdrantVectorStore для поиска документов
            prompts_db: Подключение к БД для динамических промптов
            use_enhanced_pipeline: Использовать улучшенный пайплайн
        """
        if gemini_api is None:
            gemini_api = GeminiAPI()
        
        self.db = db
        self.gemini_api = gemini_api
        # Backwards compatibility: if only one store provided, use it for both.
        if qdrant_store_admin is None and qdrant_store_client is None:
            qdrant_store_admin = qdrant_store
            qdrant_store_client = qdrant_store

        self.qdrant_store_admin = qdrant_store_admin
        self.qdrant_store_client = qdrant_store_client
        self.use_enhanced_pipeline = use_enhanced_pipeline
        
        # Инициализация улучшенного пайплайна
        # NOTE: EnhancedRAGPipeline now requires DB session; prompts are optional.
        # Enhanced pipeline currently supports a single Qdrant store.
        qdrant_for_pipeline = qdrant_store_client or qdrant_store_admin
        if use_enhanced_pipeline and db and qdrant_for_pipeline:
            self.enhanced_pipeline = EnhancedRAGPipeline(
                db=db,
                gemini_api=gemini_api,
                qdrant_store=qdrant_for_pipeline,
            )
            logger.info("Enhanced RAG pipeline initialized")
        else:
            self.enhanced_pipeline = None
            if use_enhanced_pipeline:
                logger.warning("Enhanced pipeline requested but missing components, using fallback")
        
        # Инициализация LIGHTRAG (опционально)
        self.lightrag = None
        try:
            self.lightrag = create_lightrag_service(
                working_dir=lightrag_working_dir or settings.LIGHTRAG_WORKING_DIR,
            )
            logger.info("LightRAG service initialized successfully")
        except Exception as e:
            logger.warning("LightRAG not available: %s", e)
            self.lightrag = None
    
    async def query(
        self,
        question: str,
        customer_id: Optional[str] = None,
        include_admin_laws: bool = True,
        include_customer_docs: bool = True,
        owner_id: Optional[str] = None,
        mode: str = "hybrid",
        top_k: int = 5,
        temperature: float = 0.3,
        chat_context: Optional[List[Dict[str, Any]]] = None,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Выполняет запрос к RAG системе с поддержкой фильтрации.
        
        Args:
            question: Вопрос пользователя
            customer_id: ID заказчика для фильтрации документов
            include_admin_laws: Включить общие документы (ADMIN_LAW)
            include_customer_docs: Включить документы заказчика (CUSTOMER_DOC)
            owner_id: ID владельца для дополнительной фильтрации
            mode: Режим запроса (naive, local, global, hybrid)
            top_k: Количество результатов
            temperature: Temperature для генерации
            chat_context: Контекст чата (история сообщений)
            tenant_id: ID тенанта для Policy Gate
            user_id: ID пользователя для Policy Gate
            
        Returns:
            Словарь с ответом и контекстом
        """
        # Используем улучшенный пайплайн если доступен
        if self.enhanced_pipeline and tenant_id and user_id:
            try:
                result = await self.enhanced_pipeline.process_query(
                    question=question,
                    customer_id=customer_id,
                    user_id=user_id,
                    tenant_id=tenant_id,
                    chat_context=chat_context,
                    include_admin_laws=include_admin_laws,
                    include_customer_docs=include_customer_docs,
                    mode=mode,
                    top_k=top_k,
                    temperature=temperature,
                )
                
                # Форматируем результат для совместимости
                return {
                    "answer": result["answer"],
                    "context": result["evidence_pack"]["evidence"],
                    "nodes": [],  # Enhanced pipeline doesn't use graph nodes
                    "edges": [],  # Enhanced pipeline doesn't use graph edges
                    "mode": mode,
                    "customer_id": customer_id,
                    "sources_used": result["sources_used"],
                    "enhanced_pipeline": True,
                    "processing_metadata": result.get("processing_metadata", {}),
                    "grounding_score": result.get("grounding_score", 0.0),
                }
                
            except Exception as e:
                logger.error(f"Enhanced pipeline failed, falling back to basic: {e}")
                if self.db is not None:
                    try:
                        self.db.rollback()
                    except Exception:
                        pass
                # Продолжаем с базовым пайплайном
        
        # Базовый пайплайн (fallback)
        return await self._basic_query(
            question=question,
            customer_id=customer_id,
            include_admin_laws=include_admin_laws,
            include_customer_docs=include_customer_docs,
            owner_id=owner_id,
            mode=mode,
            top_k=top_k,
            temperature=temperature,
        )
    
    async def _basic_query(
        self,
        question: str,
        customer_id: Optional[str] = None,
        include_admin_laws: bool = True,
        include_customer_docs: bool = True,
        owner_id: Optional[str] = None,
        mode: str = "hybrid",
        top_k: int = 5,
        temperature: float = 0.3,
    ) -> Dict[str, Any]:
        """Базовый RAG запрос как fallback."""
        # 1. Поиск документов в Qdrant с фильтрами
        context_docs = []
        
        if self.qdrant_store_admin or self.qdrant_store_client:
            context_docs = self._search_qdrant_documents(
                question=question,
                customer_id=customer_id,
                include_admin_laws=include_admin_laws,
                include_customer_docs=include_customer_docs,
                owner_id=owner_id,
                limit=top_k,
            )
        
        # 2. Если есть LightRAG, используем его для дополнения контекста
        lightrag_result = None
        if self.lightrag and (not customer_id or (include_admin_laws and include_customer_docs)):
            try:
                lightrag_result = self.lightrag.query(
                    question=question,
                    mode=mode,
                    top_k=top_k,
                )
                logger.info("LightRAG query completed successfully")
            except Exception as e:
                logger.error(f"LightRAG query failed: {e}")
        
        # 3. Генерация ответа через Gemini
        answer = await self._generate_answer(
            question=question,
            context_docs=context_docs,
            lightrag_context=lightrag_result.get("context", []) if lightrag_result else [],
            temperature=temperature,
        )
        
        # 4. Формирование результата
        result = {
            "answer": answer,
            "context": context_docs,
            "nodes": lightrag_result.get("nodes", []) if lightrag_result else [],
            "edges": lightrag_result.get("edges", []) if lightrag_result else [],
            "mode": mode,
            "customer_id": customer_id,
            "sources_used": self._get_sources_summary(context_docs),
            "enhanced_pipeline": False,
        }
        
        return result
    
    def _search_qdrant_documents(
        self,
        question: str,
        customer_id: Optional[str] = None,
        include_admin_laws: bool = True,
        include_customer_docs: bool = True,
        owner_id: Optional[str] = None,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """Поиск документов в Qdrant с применением фильтров."""
        if not self.qdrant_store_admin and not self.qdrant_store_client:
            return []

        query_vector = get_embedding_service().embed_single(question)

        target_store = self.qdrant_store_client or self.qdrant_store_admin
        target_size = getattr(target_store, "vector_size", None) if target_store else None
        if isinstance(target_size, int) and target_size > 0:
            if len(query_vector) > target_size:
                query_vector = query_vector[:target_size]
            elif len(query_vector) < target_size:
                query_vector = query_vector + [0.0] * (target_size - len(query_vector))

        results: List[Dict[str, Any]] = []

        if include_admin_laws:
            admin_store = self.qdrant_store_admin or self.qdrant_store_client
            if admin_store is None:
                logger.warning("Admin Qdrant store not available, skipping ADMIN_LAW search")
            else:
                admin_filter = admin_store.build_filter(
                    scope=FileScope.ADMIN_LAW.value,
                    customer_id=None,
                    owner_id=None,
                )
                try:
                    admin_points = admin_store.search(
                        query_vector=query_vector,
                        limit=limit,
                        filter_=admin_filter,
                    )

                    for point in admin_points:
                        payload = point.payload or {}

                        chunk_text_value = None
                        filename = None
                        if self.db is not None:
                            try:
                                db_chunk = (
                                    self.db.query(FileChunk)
                                    .filter(
                                        FileChunk.file_id == payload.get("file_id"),
                                        FileChunk.chunk_index == payload.get("chunk_index"),
                                    )
                                    .first()
                                )
                                if db_chunk is not None:
                                    chunk_text_value = db_chunk.text

                                db_file = self.db.query(StoredFile).get(payload.get("file_id"))
                                if db_file is not None:
                                    filename = db_file.original_filename
                            except Exception:
                                chunk_text_value = None
                                filename = None

                        results.append(
                            {
                                "source": "qdrant",
                                "scope": "ADMIN_LAW",
                                "score": point.score,
                                "file_id": payload.get("file_id"),
                                "chunk_index": payload.get("chunk_index"),
                                "filename": filename,
                                "customer_id": None,
                                "owner_id": payload.get("owner_id"),
                                "text": chunk_text_value or "",
                                "citation": f"scope=ADMIN_LAW source={payload.get('file_id')} chunk={payload.get('chunk_index')}",
                            }
                        )
                except Exception as e:
                    logger.error(f"Error searching ADMIN_LAW documents: {e}")

        if include_customer_docs and customer_id:
            customer_store = self.qdrant_store_client or self.qdrant_store_admin
            if customer_store is None:
                logger.warning("Customer Qdrant store not available, skipping CUSTOMER_DOC search")
            else:
                customer_filter = customer_store.build_filter(
                    scope=FileScope.CUSTOMER_DOC.value,
                    customer_id=customer_id,
                    owner_id=owner_id,
                )
                try:
                    customer_points = customer_store.search(
                        query_vector=query_vector,
                        limit=limit,
                        filter_=customer_filter,
                    )

                    for point in customer_points:
                        payload = point.payload or {}

                        chunk_text_value = None
                        filename = None
                        if self.db is not None:
                            try:
                                db_chunk = (
                                    self.db.query(FileChunk)
                                    .filter(
                                        FileChunk.file_id == payload.get("file_id"),
                                        FileChunk.chunk_index == payload.get("chunk_index"),
                                    )
                                    .first()
                                )
                                if db_chunk is not None:
                                    chunk_text_value = db_chunk.text

                                db_file = self.db.query(StoredFile).get(payload.get("file_id"))
                                if db_file is not None:
                                    filename = db_file.original_filename
                            except Exception:
                                chunk_text_value = None
                                filename = None

                        results.append(
                            {
                                "source": "qdrant",
                                "scope": "CUSTOMER_DOC",
                                "score": point.score,
                                "file_id": payload.get("file_id"),
                                "chunk_index": payload.get("chunk_index"),
                                "filename": filename,
                                "customer_id": customer_id,
                                "owner_id": payload.get("owner_id"),
                                "text": chunk_text_value or "",
                                "citation": f"scope=CUSTOMER_DOC source={payload.get('file_id')} chunk={payload.get('chunk_index')}",
                            }
                        )
                except Exception as e:
                    logger.error(f"Error searching CUSTOMER_DOC documents: {e}")

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:limit]
    
    async def _generate_answer(
        self,
        question: str,
        context_docs: List[Dict[str, Any]],
        lightrag_context: List[Dict[str, Any]],
        temperature: float,
    ) -> str:
        """Генерация ответа через Gemini с учетом контекста."""
        # Формируем контекст для промпта
        context_text = ""
        
        if context_docs:
            context_text += "### Релевантные документы:\n"
            for i, doc in enumerate(context_docs, 1):
                filename = doc.get("filename")
                title = f"[{doc['scope']}] {doc['citation']}"
                if filename:
                    title = f"{title} (file={filename})"
                context_text += f"{i}. {title}\n"
                text = (doc.get("text") or "").strip()
                if text:
                    context_text += f"{text}\n\n"
            
        if lightrag_context:
            context_text += "\n### Дополнительный контекст из графа знаний:\n"
            context_text += str(lightrag_context)
        
        # Промпт для аудитора
        system_prompt = """Ты - профессиональный аудитор-помощник. Отвечай на вопросы строго на основе предоставленных документов.
        
Правила:
- Используй только информацию из предоставленных документов
- Указывай источники в формате [номер источника]
- Будь точным и профессиональным
- Если информации недостаточно, так и скажи"""
        
        full_prompt = f"{system_prompt}\n\n{context_text}\n\n### Вопрос:\n{question}\n\n### Ответ:"
        
        try:
            response_text = await asyncio.to_thread(
                self.gemini_api.generate_text,
                full_prompt,
                temperature=temperature,
            )
            return response_text
        except Exception as e:
            logger.error(f"Error generating answer: {e}")
            return "Извините, произошла ошибка при генерации ответа. Попробуйте переформулировать вопрос."
    
    def _get_sources_summary(self, context_docs: List[Dict[str, Any]]) -> List[str]:
        """Формирует список использованных источников."""
        sources = []
        for doc in context_docs:
            sources.append(doc.get("citation", "Unknown source"))
        return sources
    
    async def evidence(
        self,
        question: str,
        customer_id: Optional[str] = None,
        include_admin_laws: bool = True,
        include_customer_docs: bool = True,
        owner_id: Optional[str] = None,
        mode: str = "hybrid",
        top_k: int = 8,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Retrieval-only (no generation). Returns evidence without LLM answer.
        """
        if not self.qdrant_store_admin and not self.qdrant_store_client:
            logger.warning("Qdrant not configured; returning empty evidence set")
            return {"context": [], "nodes": [], "edges": [], "mode": mode}

        context_docs = self._search_qdrant_documents(
            question=question,
            customer_id=customer_id,
            include_admin_laws=include_admin_laws,
            include_customer_docs=include_customer_docs,
            owner_id=owner_id,
            limit=top_k,
        )

        return {
            "context": context_docs,
            "nodes": [],
            "edges": [],
            "mode": mode,
        }

    # -------------------------
    # LightRAG endpoints
    # -------------------------

    def insert_text(
        self, text: str, metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Inserts text into LightRAG graph (if available).
        """
        if not self.lightrag:
            raise RuntimeError("LightRAG service not available")

        node_id = self.lightrag.insert(text, metadata=metadata)
        return {"node_id": str(node_id), "success": True}

    def delete_node(self, node_id: str) -> Dict[str, Any]:
        """
        Deletes a node from LightRAG graph (best effort; depends on LightRAG version).
        Used by /rag/node/{node_id}.
        """
        if not self.lightrag:
            raise RuntimeError("LightRAG service not available")

        success = self.lightrag.delete(node_id)
        return {"success": bool(success), "node_id": node_id}

    def get_stats(self) -> Dict[str, Any]:
        """
        Returns LightRAG graph stats.
        Used by /rag/stats.
        """
        if not self.lightrag:
            return {
                "nodes_count": 0,
                "edges_count": 0,
                "working_dir": "N/A",
            }

        stats = self.lightrag.get_graph_stats()
        # Ensure required keys exist for response model
        return {
            "nodes_count": int(stats.get("nodes_count", 0) or 0),
            "edges_count": int(stats.get("edges_count", 0) or 0),
            "working_dir": str(stats.get("working_dir", "N/A")),
        }
