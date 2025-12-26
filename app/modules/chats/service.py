"""Chat service with RAG integration, context management, and chat memory."""
import logging
import json
from typing import Optional, Dict, Any, List
from datetime import datetime
from sqlalchemy.orm import Session

from app.modules.chats.models import Chat, ChatMessage, SenderType
from app.modules.rag.service import RAGService
from app.core.logging import get_logger

logger = get_logger(__name__)


class ChatService:
    """
    Production chat service with RAG integration and chat memory.
    
    Features:
    - 3-layer conversation memory (rolling summary + last turns + semantic retrieval)
    - Integration with enhanced RAG pipeline
    - Automatic chat memory indexing in Qdrant
    - Context caching for long conversations
    """
    
    def __init__(
        self,
        db: Session,
        rag_service: Optional[RAGService] = None,
    ):
        self.db = db
        self.rag_service = rag_service
        self.memory_service = None
        
        # Try to initialize chat memory service
        try:
            from app.modules.chats.memory import create_chat_memory_service
            from app.core.config import settings
            
            self.memory_service = create_chat_memory_service(
                db=db,
                qdrant_url=settings.QDRANT_URL,
                vector_size=settings.QDRANT_VECTOR_SIZE,
            )
            logger.info("ChatMemoryService initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize ChatMemoryService: {e}")
    
    def get_chat_context(self, chat_id: str, message_limit: int = 10) -> List[Dict[str, Any]]:
        """Get chat context (last messages)."""
        messages = (
            self.db.query(ChatMessage)
            .filter(ChatMessage.chat_id == chat_id)
            .order_by(ChatMessage.created_at.desc())
            .limit(message_limit)
            .all()
        )
        
        context = []
        for message in reversed(messages):
            context.append({
                "role": message.role,
                "content": message.content,
                "sender_type": message.sender_type.value,
                "timestamp": message.created_at.isoformat(),
            })
        
        return context
    
    def get_rolling_summary(self, chat_id: str) -> str:
        """Get rolling summary for long conversations."""
        chat = self.db.query(Chat).get(chat_id)
        if not chat or not chat.context_cache:
            return ""
        
        try:
            cache_data = json.loads(chat.context_cache)
            return cache_data.get("summary", "")
        except (json.JSONDecodeError, TypeError):
            return chat.context_cache or ""
    
    def update_context_cache(self, chat_id: str, context_data: Dict[str, Any]) -> None:
        """Update chat context cache."""
        chat = self.db.query(Chat).get(chat_id)
        if chat:
            chat.context_cache = json.dumps(context_data)
            self.db.commit()
    
    def get_relevant_chat_memories(
        self,
        query: str,
        customer_id: str,
        current_chat_id: Optional[str] = None,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """Get relevant memories from previous chats."""
        if not self.memory_service:
            return []
        
        return self.memory_service.get_relevant_memories(
            query=query,
            customer_id=customer_id,
            current_chat_id=current_chat_id,
            limit=limit,
        )
    
    async def send_message_with_rag(
        self,
        chat_id: str,
        user_message: str,
        customer_id: str,
        user_id: str,
        tenant_id: Optional[str] = None,
        include_admin_laws: bool = True,
        include_customer_docs: bool = True,
    ) -> Dict[str, Any]:
        """
        Send message and get RAG response with full pipeline.
        
        Includes:
        - 3-layer memory (rolling summary + last turns + chat memory retrieval)
        - Policy Gate with ACL
        - Hybrid search (dense + sparse)
        - Reranking and grounding check
        """
        if not self.rag_service:
            raise ValueError("RAG service not available")
        
        # 1. Save user message
        user_msg = ChatMessage(
            chat_id=chat_id,
            sender_type=SenderType.EMPLOYEE,
            sender_id=user_id,
            role="user",
            content=user_message,
        )
        self.db.add(user_msg)
        self.db.commit()
        self.db.refresh(user_msg)
        
        # 2. Collect 3-layer context
        rolling_summary = self.get_rolling_summary(chat_id)
        last_turns = self.get_chat_context(chat_id, message_limit=4)
        chat_memories = self.get_relevant_chat_memories(
            query=user_message,
            customer_id=customer_id,
            current_chat_id=chat_id,
            limit=3,
        )
        
        # 3. Execute RAG query
        try:
            rag_result = await self.rag_service.query(
                question=user_message,
                customer_id=customer_id,
                include_admin_laws=include_admin_laws,
                include_customer_docs=include_customer_docs,
                owner_id=user_id,
                mode="hybrid",
                top_k=10,
                temperature=0.3,
                chat_context=last_turns,
                tenant_id=tenant_id,
                user_id=user_id,
            )
        except Exception as e:
            logger.error(f"RAG query failed: {e}")
            try:
                self.db.rollback()
            except Exception:
                pass
            rag_result = {
                "answer": "Извините, произошла ошибка при поиске информации.",
                "context": [],
                "sources_used": [],
                "enhanced_pipeline": False,
            }
        
        # 4. Save assistant response
        assistant_msg = ChatMessage(
            chat_id=chat_id,
            sender_type=SenderType.ASSISTANT,
            sender_id=None,
            role="assistant",
            content=rag_result["answer"],
        )
        try:
            self.db.add(assistant_msg)
            self.db.commit()
            self.db.refresh(assistant_msg)
        except Exception:
            try:
                self.db.rollback()
            except Exception:
                pass
            raise
        
        # 5. Index message pair to chat memory
        if self.memory_service:
            try:
                chat = self.db.query(Chat).get(chat_id)
                if chat:
                    self.memory_service.memory_store.index_message_pair(
                        user_message=user_msg,
                        assistant_message=assistant_msg,
                        customer_id=str(chat.customer_id),
                    )
            except Exception as e:
                logger.warning(f"Failed to index message pair: {e}")
        
        # 6. Update rolling summary if conversation is long
        if len(last_turns) > 6:
            self._update_rolling_summary(chat_id, last_turns)
        
        return {
            "user_message": {
                "id": str(user_msg.id),
                "content": user_message,
                "created_at": user_msg.created_at.isoformat(),
            },
            "assistant_message": {
                "id": str(assistant_msg.id),
                "content": rag_result["answer"],
                "created_at": assistant_msg.created_at.isoformat(),
            },
            "rag_context": rag_result.get("context", []),
            "sources_used": rag_result.get("sources_used", []),
            "enhanced_pipeline": rag_result.get("enhanced_pipeline", False),
            "grounding_score": rag_result.get("grounding_score", 0.0),
            "chat_memories_used": len(chat_memories),
        }
    
    def _update_rolling_summary(self, chat_id: str, messages: List[Dict[str, Any]]) -> None:
        """Update rolling summary for long conversations."""
        chat = self.db.query(Chat).get(chat_id)
        if not chat:
            return
        
        # Generate summary using LLM if available
        summary = ""
        if self.memory_service and self.rag_service:
            try:
                gemini_api = getattr(self.rag_service, 'gemini_api', None)
                summary = self.memory_service.generate_rolling_summary(
                    chat_id=chat_id,
                    gemini_api=gemini_api,
                )
            except Exception as e:
                logger.warning(f"Failed to generate summary: {e}")
        
        if not summary:
            summary = f"Conversation with {len(messages)} messages."
        
        self.update_context_cache(chat_id, {
            "summary": summary,
            "message_count": len(messages),
            "updated_at": datetime.utcnow().isoformat(),
        })
    
    def create_chat(self, customer_id: str, user_id: str, title: Optional[str] = None) -> Chat:
        """Create new chat."""
        chat = Chat(
            customer_id=customer_id,
            created_by_id=user_id,
            title=title or "Новый чат",
        )
        self.db.add(chat)
        self.db.commit()
        self.db.refresh(chat)
        return chat
    
    def get_chat_with_messages(self, chat_id: str, user_id: str) -> Optional[Chat]:
        """Get chat with messages."""
        chat = self.db.query(Chat).get(chat_id)
        return chat
    
    def index_chat_to_memory(self, chat_id: str) -> int:
        """Index chat messages to Qdrant for semantic search."""
        if not self.memory_service:
            logger.warning("Chat memory service not available")
            return 0
        
        return self.memory_service.index_chat_messages(chat_id)
