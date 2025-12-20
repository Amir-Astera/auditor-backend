"""
RAG service (hybrid-ready).

This module keeps the existing LightRAG-oriented endpoints working
(/rag/insert, /rag/node/{id}, /rag/stats) while wiring hybrid retrieval+generation
into /rag/query.

Hybrid approach:
- Retrieve evidence from Qdrant (admin laws + optionally customer docs)
- Optionally enrich with LightRAG if available
- Generate final answer with Gemini using system prompts stored in Postgres
  (with fallback to files under app/core/prompts via PromptService)

Additionally:
- Provides retrieval-only support (evidence-only) for /rag/evidence (router layer),
  so you can debug retrieval without paying for generation.

Notes:
- This file intentionally does NOT import FastAPI. It is pure service logic.
- This file assumes:
  - app/modules/rag/hybrid_service.py exists
  - app/modules/prompts/service.py exists
  - app/modules/files/qdrant_client.py exists
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from app.core.config import settings
from app.modules.files.qdrant_client import QdrantVectorStore
from app.modules.rag.gemini import GeminiAPI
from app.modules.rag.hybrid_service import (
    HybridRAGQuery,
    HybridRAGService,
    PromptsProvider,
)
from app.modules.rag.lightrag_integration import create_lightrag_service

logger = logging.getLogger(__name__)


class RAGService:
    """
    High-level RAG service used by API layer.

    Responsibilities:
    - Provide /rag/query with hybrid RAG behavior (Qdrant + Gemini, optional LightRAG).
    - Preserve legacy LightRAG operations for /rag/insert, /rag/node/{id}, /rag/stats.

    Construction:
    - Router currently instantiates RAGService(gemini_api=GeminiAPI()) with no DB session.
      For full prompt DB integration, prefer constructing with `prompts=PromptService(db)`.
    """

    def __init__(
        self,
        gemini_api: Optional[GeminiAPI] = None,
        lightrag_working_dir: Optional[str] = None,
        prompts: Optional[PromptsProvider] = None,
        qdrant: Optional[QdrantVectorStore] = None,
    ):
        self.gemini_api = gemini_api or GeminiAPI()

        # Prompts: if not provided, we create a "file fallback only" PromptService-like shim.
        # The real PromptService requires DB session; routers should pass it in.
        self.prompts = prompts

        # Qdrant for hybrid retrieval
        self.qdrant = qdrant
        if self.qdrant is None:
            try:
                self.qdrant = QdrantVectorStore(
                    url=settings.QDRANT_URL,
                    collection_name=settings.QDRANT_COLLECTION_NAME,
                    vector_size=settings.QDRANT_VECTOR_SIZE,
                )
            except Exception as e:
                logger.warning("Qdrant is not available: %s", e)
                self.qdrant = None

        # LightRAG (optional)
        self.lightrag = None
        try:
            self.lightrag = create_lightrag_service(
                working_dir=lightrag_working_dir or settings.LIGHTRAG_WORKING_DIR,
                gemini_api=self.gemini_api,
            )
            logger.info("LightRAG service initialized successfully")
        except Exception as e:
            logger.warning("LightRAG not available: %s", e)
            self.lightrag = None

    # -------------------------
    # Query: HYBRID pipeline
    # -------------------------

    def query(
        self,
        question: str,
        mode: str = "hybrid",
        top_k: int = 8,
        customer_id: Optional[str] = None,
        include_admin_laws: bool = True,
        include_customer_docs: bool = True,
        temperature: float = 0.3,
    ) -> Dict[str, Any]:
        """
        Executes hybrid RAG query.

        Returns shape compatible with existing router response model:
        {
          "answer": str,
          "context": [...],
          "nodes": [...],
          "edges": [...],
          "mode": str
        }
        """
        # If we don't have prompts service (DB), we can still answer with minimal system prompt.
        if self.prompts is None:
            # Use a very small, safe system prompt rather than failing.
            # Full prompt DB integration should be done by passing PromptService(db) from router.
            class _FallbackPrompts:
                def get_active_prompt_content(self, prompt_type):  # noqa: ANN001
                    return ""

            prompts = _FallbackPrompts()  # type: ignore[assignment]
        else:
            prompts = self.prompts

        if self.qdrant is None:
            # No retrieval backend; fallback to direct Gemini generation.
            logger.warning(
                "Qdrant not configured; falling back to direct Gemini generation"
            )
            answer = self.gemini_api.generate_text(
                question,
                model=getattr(settings, "LIGHTRAG_LLM_MODEL", "gemini-3-pro-preview"),
                temperature=temperature,
                max_output_tokens=2048,
            )
            return {
                "answer": answer,
                "context": [],
                "nodes": [],
                "edges": [],
                "mode": "direct",
            }

        hybrid = HybridRAGService(
            gemini=self.gemini_api,
            prompts=prompts,  # PromptService or fallback shim
            qdrant=self.qdrant,
            lightrag=self.lightrag,
        )

        result = hybrid.query(
            HybridRAGQuery(
                question=question,
                customer_id=customer_id,
                include_admin_laws=include_admin_laws,
                include_customer_docs=include_customer_docs,
                top_k=top_k,
                temperature=temperature,
                mode=mode,
            )
        )

        return {
            "answer": result.answer,
            "context": result.context,
            "nodes": result.nodes,
            "edges": result.edges,
            "mode": result.mode,
        }

    def evidence(
        self,
        question: str,
        mode: str = "hybrid",
        top_k: int = 8,
        customer_id: Optional[str] = None,
        include_admin_laws: bool = True,
        include_customer_docs: bool = True,
    ) -> Dict[str, Any]:
        """
        Retrieval-only (no generation). Intended for /rag/evidence endpoint.

        Returns:
        {
          "context": [...],
          "nodes": [...],
          "edges": [...],
          "mode": str
        }
        """
        if self.prompts is None:

            class _FallbackPrompts:
                def get_active_prompt_content(self, prompt_type):  # noqa: ANN001
                    return ""

            prompts = _FallbackPrompts()  # type: ignore[assignment]
        else:
            prompts = self.prompts

        if self.qdrant is None:
            logger.warning("Qdrant not configured; returning empty evidence set")
            return {"context": [], "nodes": [], "edges": [], "mode": mode}

        hybrid = HybridRAGService(
            gemini=self.gemini_api,
            prompts=prompts,  # PromptsProvider
            qdrant=self.qdrant,
            lightrag=self.lightrag,
        )

        payload = hybrid.evidence_only(
            HybridRAGQuery(
                question=question,
                customer_id=customer_id,
                include_admin_laws=include_admin_laws,
                include_customer_docs=include_customer_docs,
                top_k=top_k,
                temperature=0.0,
                mode=mode,
            )
        )

        # Ensure stable shape
        return {
            "context": payload.get("context", []),
            "nodes": payload.get("nodes", []),
            "edges": payload.get("edges", []),
            "mode": payload.get("mode", mode),
        }

    # -------------------------
    # Legacy LightRAG endpoints
    # -------------------------

    def insert_text(
        self, text: str, metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Inserts text into LightRAG graph (if available).
        Used by /rag/insert.
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
