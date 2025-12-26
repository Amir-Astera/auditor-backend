"""
Chat Memory Service for storing and retrieving conversation history in Qdrant.

Features:
- Indexes chat messages as embeddings in Qdrant
- Supports semantic search for similar conversations
- ACL filtering by tenant_id, customer_id, user_id
- Rolling summary generation for long conversations
"""

import logging
import uuid
from typing import List, Optional, Dict, Any
from datetime import datetime
from dataclasses import dataclass

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    ScoredPoint,
    VectorParams,
)
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.modules.embeddings.service import get_embedding_service, EmbeddingService
from app.modules.chats.models import Chat, ChatMessage, SenderType

logger = get_logger(__name__)


@dataclass
class ChatMemoryEntry:
    """Single chat memory entry."""
    id: str
    chat_id: str
    customer_id: str
    user_id: str
    role: str
    content: str
    timestamp: datetime
    score: float = 0.0
    metadata: Dict[str, Any] = None


class ChatMemoryStore:
    """
    Qdrant-based chat memory store.
    
    Stores chat messages as embeddings for semantic retrieval.
    Separate collection from document embeddings.
    """
    
    COLLECTION_NAME = "chat_memory"
    
    def __init__(
        self,
        qdrant_url: str,
        vector_size: int = 768,
        embedding_service: Optional[EmbeddingService] = None,
    ):
        self._client = QdrantClient(url=qdrant_url)
        self._vector_size = vector_size
        self._embedding_service = embedding_service or get_embedding_service()
        
        self._ensure_collection()
        logger.info(f"ChatMemoryStore initialized, collection={self.COLLECTION_NAME}")
    
    def _ensure_collection(self):
        """Create collection if not exists."""
        collections = self._client.get_collections()
        exists = any(c.name == self.COLLECTION_NAME for c in collections.collections)
        
        if exists:
            # Try to read actual vector size from Qdrant in case collection was created earlier
            try:
                info = self._client.get_collection(self.COLLECTION_NAME)
                actual_size = None
                try:
                    actual_size = info.config.params.vectors.size  # type: ignore[attr-defined]
                except Exception:
                    try:
                        actual_size = info.config.params.vectors["size"]  # type: ignore[index]
                    except Exception:
                        actual_size = None
                if isinstance(actual_size, int) and actual_size > 0:
                    self._vector_size = actual_size
            except Exception:
                pass
            logger.info(f"Chat memory collection already exists: {self.COLLECTION_NAME}")
            return
        
        logger.info(f"Creating chat memory collection: {self.COLLECTION_NAME}")
        
        self._client.recreate_collection(
            collection_name=self.COLLECTION_NAME,
            vectors_config=VectorParams(
                size=self._vector_size,
                distance=Distance.COSINE,
            ),
        )
    
    def index_message(
        self,
        message_id: str,
        chat_id: str,
        customer_id: str,
        user_id: str,
        role: str,
        content: str,
        timestamp: datetime,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Index a single chat message.
        
        Returns:
            Point ID in Qdrant
        """
        # Generate embedding
        embedding = self._embedding_service.embed_single(content)
        
        point_id = str(uuid.uuid4())
        
        payload = {
            "message_id": message_id,
            "chat_id": chat_id,
            "customer_id": customer_id,
            "user_id": user_id,
            "role": role,
            "content": content[:1000],  # Truncate for payload
            "timestamp": timestamp.isoformat(),
            "indexed_at": datetime.utcnow().isoformat(),
        }
        
        if metadata:
            payload["metadata"] = metadata
        
        point = PointStruct(
            id=point_id,
            vector=embedding,
            payload=payload,
        )
        
        self._client.upsert(
            collection_name=self.COLLECTION_NAME,
            points=[point],
        )
        
        logger.debug(f"Indexed chat message: {message_id} -> {point_id}")
        return point_id
    
    def index_message_pair(
        self,
        user_message: ChatMessage,
        assistant_message: ChatMessage,
        customer_id: str,
    ) -> str:
        """
        Index user→assistant message pair as single unit.
        Better for retrieval than individual messages.
        
        Returns:
            Point ID in Qdrant
        """
        # Combine messages for embedding
        combined_text = f"User: {user_message.content}\nAssistant: {assistant_message.content}"
        
        embedding = self._embedding_service.embed_single(combined_text)
        
        point_id = str(uuid.uuid4())
        
        payload = {
            "type": "message_pair",
            "user_message_id": str(user_message.id),
            "assistant_message_id": str(assistant_message.id),
            "chat_id": str(user_message.chat_id),
            "customer_id": customer_id,
            "user_id": str(user_message.sender_id) if user_message.sender_id else None,
            "user_content": user_message.content[:500],
            "assistant_content": assistant_message.content[:500],
            "timestamp": user_message.created_at.isoformat(),
            "indexed_at": datetime.utcnow().isoformat(),
        }
        
        point = PointStruct(
            id=point_id,
            vector=embedding,
            payload=payload,
        )
        
        self._client.upsert(
            collection_name=self.COLLECTION_NAME,
            points=[point],
        )
        
        logger.debug(f"Indexed message pair: {user_message.id} + {assistant_message.id}")
        return point_id
    
    def search_similar(
        self,
        query: str,
        customer_id: Optional[str] = None,
        user_id: Optional[str] = None,
        chat_id: Optional[str] = None,
        exclude_chat_id: Optional[str] = None,
        limit: int = 10,
    ) -> List[ChatMemoryEntry]:
        """
        Search for similar chat memories.
        
        Args:
            query: Search query text
            customer_id: Filter by customer
            user_id: Filter by user
            chat_id: Filter by specific chat
            exclude_chat_id: Exclude specific chat (current chat)
            limit: Max results
            
        Returns:
            List of ChatMemoryEntry
        """
        # Generate query embedding
        query_embedding = self._embedding_service.embed_single(query)
        
        # Build filter
        filter_conditions = []
        
        if customer_id:
            filter_conditions.append(
                FieldCondition(key="customer_id", match=MatchValue(value=customer_id))
            )
        
        if user_id:
            filter_conditions.append(
                FieldCondition(key="user_id", match=MatchValue(value=user_id))
            )
        
        if chat_id:
            filter_conditions.append(
                FieldCondition(key="chat_id", match=MatchValue(value=chat_id))
            )
        
        query_filter = Filter(must=filter_conditions) if filter_conditions else None
        
        # Search
        if hasattr(self._client, "search"):
            results = self._client.search(
                collection_name=self.COLLECTION_NAME,
                query_vector=query_embedding,
                limit=limit + 5,  # Get extra to filter out excluded
                query_filter=query_filter,
            )
        else:
            resp = self._client.query_points(
                collection_name=self.COLLECTION_NAME,
                query=query_embedding,
                limit=limit + 5,
                query_filter=query_filter,
                with_payload=True,
            )
            results = getattr(resp, "points", None)
            if results is None:
                results = getattr(resp, "result", None)
            if results is None:
                results = []
        
        # Convert to ChatMemoryEntry
        entries = []
        for point in results:
            payload = point.payload or {}
            
            # Skip excluded chat
            if exclude_chat_id and payload.get("chat_id") == exclude_chat_id:
                continue
            
            entry = ChatMemoryEntry(
                id=str(point.id),
                chat_id=payload.get("chat_id", ""),
                customer_id=payload.get("customer_id", ""),
                user_id=payload.get("user_id", ""),
                role=payload.get("role", ""),
                content=payload.get("content") or payload.get("user_content", ""),
                timestamp=datetime.fromisoformat(payload.get("timestamp", datetime.utcnow().isoformat())),
                score=point.score,
                metadata=payload.get("metadata"),
            )
            entries.append(entry)
            
            if len(entries) >= limit:
                break
        
        logger.info(f"Found {len(entries)} similar chat memories for query")
        return entries
    
    def delete_chat_memories(self, chat_id: str) -> int:
        """Delete all memories for a chat."""
        # Note: Qdrant doesn't support delete by filter in all versions
        # This is a simplified implementation
        try:
            self._client.delete(
                collection_name=self.COLLECTION_NAME,
                points_selector={
                    "filter": {
                        "must": [
                            {"key": "chat_id", "match": {"value": chat_id}}
                        ]
                    }
                }
            )
            logger.info(f"Deleted memories for chat: {chat_id}")
            return 1
        except Exception as e:
            logger.error(f"Failed to delete chat memories: {e}")
            return 0
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """Get collection statistics."""
        try:
            info = self._client.get_collection(self.COLLECTION_NAME)
            return {
                "collection_name": self.COLLECTION_NAME,
                "vectors_count": info.vectors_count,
                "points_count": info.points_count,
                "status": info.status,
            }
        except Exception as e:
            logger.error(f"Failed to get collection stats: {e}")
            return {"error": str(e)}


class ChatMemoryService:
    """
    High-level service for chat memory management.
    
    Integrates with PostgreSQL (chat storage) and Qdrant (semantic search).
    """
    
    def __init__(
        self,
        db: Session,
        memory_store: ChatMemoryStore,
    ):
        self.db = db
        self.memory_store = memory_store
    
    def index_chat_messages(self, chat_id: str) -> int:
        """
        Index all messages from a chat.
        
        Returns:
            Number of indexed message pairs
        """
        chat = self.db.query(Chat).get(chat_id)
        if not chat:
            logger.warning(f"Chat not found: {chat_id}")
            return 0
        
        messages = (
            self.db.query(ChatMessage)
            .filter(ChatMessage.chat_id == chat_id)
            .order_by(ChatMessage.created_at.asc())
            .all()
        )
        
        indexed_count = 0
        
        # Index message pairs (user → assistant)
        i = 0
        while i < len(messages) - 1:
            user_msg = messages[i]
            assistant_msg = messages[i + 1]
            
            if user_msg.role == "user" and assistant_msg.role == "assistant":
                self.memory_store.index_message_pair(
                    user_message=user_msg,
                    assistant_message=assistant_msg,
                    customer_id=str(chat.customer_id),
                )
                indexed_count += 1
                i += 2
            else:
                i += 1
        
        logger.info(f"Indexed {indexed_count} message pairs for chat {chat_id}")
        return indexed_count
    
    def get_relevant_memories(
        self,
        query: str,
        customer_id: str,
        current_chat_id: Optional[str] = None,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Get relevant chat memories for a query.
        
        Args:
            query: User's question
            customer_id: Customer context
            current_chat_id: Exclude current chat from results
            limit: Max memories to return
            
        Returns:
            List of relevant memory summaries
        """
        entries = self.memory_store.search_similar(
            query=query,
            customer_id=customer_id,
            exclude_chat_id=current_chat_id,
            limit=limit,
        )
        
        memories = []
        for entry in entries:
            memories.append({
                "chat_id": entry.chat_id,
                "content": entry.content,
                "score": entry.score,
                "timestamp": entry.timestamp.isoformat(),
            })
        
        return memories
    
    def generate_rolling_summary(
        self,
        chat_id: str,
        gemini_api: Any = None,
    ) -> str:
        """
        Generate rolling summary for a chat.
        
        Uses LLM to summarize conversation history.
        """
        chat = self.db.query(Chat).get(chat_id)
        if not chat:
            return ""
        
        messages = (
            self.db.query(ChatMessage)
            .filter(ChatMessage.chat_id == chat_id)
            .order_by(ChatMessage.created_at.asc())
            .all()
        )
        
        if len(messages) < 6:
            return ""  # Too short for summary
        
        # Build conversation text
        conversation_text = ""
        for msg in messages[:-4]:  # Exclude last 4 messages (they go to last_turns)
            role = "User" if msg.role == "user" else "Assistant"
            conversation_text += f"{role}: {msg.content[:200]}...\n"
        
        if not gemini_api:
            # Return simple summary without LLM
            return f"Previous conversation with {len(messages)} messages about audit topics."
        
        # Generate summary with LLM
        summary_prompt = f"""Summarize this audit conversation concisely. Focus on:
1. Key facts discussed
2. Decisions made
3. Open questions
4. Important entities mentioned

Conversation:
{conversation_text[:3000]}

Summary (max 200 words):"""
        
        try:
            response = gemini_api.generate_content(summary_prompt)
            if response and 'candidates' in response:
                return response['candidates'][0]['content']['parts'][0]['text']
        except Exception as e:
            logger.error(f"Failed to generate summary: {e}")
        
        return f"Previous conversation with {len(messages)} messages."
    
    def update_chat_context_cache(
        self,
        chat_id: str,
        summary: str,
        facts: List[str] = None,
        entities: List[str] = None,
    ):
        """Update chat context cache in PostgreSQL."""
        import json
        
        chat = self.db.query(Chat).get(chat_id)
        if not chat:
            return
        
        context_data = {
            "summary": summary,
            "facts": facts or [],
            "entities": entities or [],
            "updated_at": datetime.utcnow().isoformat(),
        }
        
        chat.context_cache = json.dumps(context_data)
        self.db.commit()
        
        logger.info(f"Updated context cache for chat {chat_id}")


# Factory function
def create_chat_memory_service(
    db: Session,
    qdrant_url: str,
    vector_size: int = 768,
) -> ChatMemoryService:
    """Create ChatMemoryService with all dependencies."""
    memory_store = ChatMemoryStore(
        qdrant_url=qdrant_url,
        vector_size=vector_size,
    )
    
    return ChatMemoryService(
        db=db,
        memory_store=memory_store,
    )
