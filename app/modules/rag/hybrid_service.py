"""
Hybrid RAG Service

This module implements a production-oriented hybrid RAG pipeline:

1) Retrieval:
   - Qdrant vector search over:
     a) admin laws / standards (scope=ADMIN_LAW)
     b) customer documents (scope=CUSTOMER_DOC, filtered by customer_id)
   - Optional LightRAG enrichment (graph-based reasoning), if available.

2) Prompting:
   - Pulls system prompts from DB (PromptService) with fallback to files in app/core/prompts:
     - STYLE_GUIDE (02_StyleGuide)
     - ROUTING (03_ISA_RoutingPrompts)
     - COMPANY_PROFILE

3) Generation:
   - Uses Gemini (google-genai) via app.modules.rag.gemini.GeminiAPI
   - Model: configured in Settings via LIGHTRAG_LLM_MODEL (default "gemini-3-pro-preview")

Design goals:
- Deterministic, audit-grade outputs (house style guide).
- Traceability: returns sources (chunks) used with clear citations.
- Safety: does not invent numbers; states assumptions and missing evidence requests.
- Operates even if LightRAG is not installed.

Expected payload schema in Qdrant points:
{
  "file_id": "...",
  "chunk_index": <int>,
  "scope": "ADMIN_LAW" | "CUSTOMER_DOC",
  "customer_id": <str|null>,
  "owner_id": <str>,
  "filename": <str>,
  "text": <str>,
}

Typing note:
- The HybridRAGService accepts any "prompts provider" that implements:
    get_active_prompt_content(PromptType) -> str
  This allows passing a DB-backed PromptService or a lightweight fallback shim.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol, Sequence, runtime_checkable

from app.core.config import settings
from app.core.logging import get_logger
from app.modules.files.models import FileScope
from app.modules.files.qdrant_client import QdrantVectorStore
from app.modules.prompts.models import PromptType
from app.modules.rag.gemini import GeminiAPI
from app.modules.rag.lightrag_integration import LightRAGService

logger = get_logger(__name__)


@runtime_checkable
class PromptsProvider(Protocol):
    def get_active_prompt_content(self, prompt_type: PromptType) -> str: ...


@dataclass(frozen=True)
class HybridRAGQuery:
    question: str
    customer_id: Optional[str] = None
    include_admin_laws: bool = True
    include_customer_docs: bool = True
    top_k: int = 8
    temperature: float = 0.3
    mode: str = "hybrid"  # "hybrid"|"qdrant"|"lightrag"


@dataclass(frozen=True)
class HybridRAGResult:
    answer: str
    context: List[Dict[str, Any]]
    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]
    mode: str


class HybridRAGService:
    """
    Hybrid RAG:
    - Qdrant supplies evidence (fast retrieval + filters)
    - LightRAG optionally enriches reasoning
    - Gemini generates final answer using strict audit-grade prompts
    """

    def __init__(
        self,
        gemini: GeminiAPI,
        prompts: PromptsProvider,
        qdrant: QdrantVectorStore,
        lightrag: LightRAGService | None = None,
    ):
        self._gemini = gemini
        self._prompts = prompts
        self._qdrant = qdrant
        self._lightrag = lightrag

    # ---------------------------
    # Public API
    # ---------------------------

    def query(self, q: HybridRAGQuery) -> HybridRAGResult:
        """
        Execute hybrid RAG query.
        """
        top_k = max(1, min(int(q.top_k), 30))
        temperature = float(q.temperature)

        # 1) Retrieve evidence from Qdrant (evidence must include citations)
        evidence = self._retrieve_evidence(
            question=q.question,
            top_k=top_k,
            customer_id=q.customer_id,
            include_admin_laws=q.include_admin_laws,
            include_customer_docs=q.include_customer_docs,
            mode=q.mode,
        )

        # 2) Optional LightRAG enrichment
        lightrag_payload: Dict[str, Any] | None = None
        if q.mode in ("hybrid", "lightrag") and self._lightrag is not None:
            try:
                # Note: LightRAG integration returns dict with keys: answer/context/nodes/edges
                lightrag_payload = self._lightrag.query(
                    question=q.question,
                    mode="hybrid",
                    top_k=top_k,
                    customer_id=q.customer_id,
                )
            except Exception as e:
                logger.warning(
                    "LightRAG enrichment failed; continuing with Qdrant-only",
                    extra={"error": str(e)},
                )
                lightrag_payload = None

        # 3) Build final prompt
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(
            question=q.question,
            customer_id=q.customer_id,
            evidence=evidence,
            lightrag_payload=lightrag_payload,
        )

        # 4) Generate answer
        model_name = getattr(settings, "LIGHTRAG_LLM_MODEL", "gemini-3-pro-preview")
        answer = self._gemini.generate_text(
            user_prompt,
            model=model_name,
            system_instruction=system_prompt,
            temperature=temperature,
            max_output_tokens=2048,
        )

        # 5) Return
        nodes: List[Dict[str, Any]] = []
        edges: List[Dict[str, Any]] = []
        if lightrag_payload and isinstance(lightrag_payload, dict):
            nodes = list(lightrag_payload.get("nodes") or [])
            edges = list(lightrag_payload.get("edges") or [])

        mode_used = q.mode
        return HybridRAGResult(
            answer=answer,
            context=evidence,
            nodes=nodes,
            edges=edges,
            mode=mode_used,
        )

    def evidence_only(self, q: HybridRAGQuery) -> Dict[str, Any]:
        """
        Retrieval-only method for debugging and traceability.
        Does NOT call the LLM for answer generation.

        Returns a dict compatible with RAGEvidenceResponse schema:
        {
          "context": [...],
          "nodes": [...],
          "edges": [...],
          "mode": str
        }
        """
        top_k = max(1, min(int(q.top_k), 50))

        evidence = self._retrieve_evidence(
            question=q.question,
            top_k=top_k,
            customer_id=q.customer_id,
            include_admin_laws=q.include_admin_laws,
            include_customer_docs=q.include_customer_docs,
            mode=q.mode,
        )

        nodes: List[Dict[str, Any]] = []
        edges: List[Dict[str, Any]] = []
        if q.mode in ("hybrid", "lightrag") and self._lightrag is not None:
            try:
                lightrag_payload = self._lightrag.query(
                    question=q.question,
                    mode="hybrid",
                    top_k=top_k,
                    customer_id=q.customer_id,
                )
                if isinstance(lightrag_payload, dict):
                    nodes = list(lightrag_payload.get("nodes") or [])
                    edges = list(lightrag_payload.get("edges") or [])
            except Exception as e:
                logger.warning(
                    "LightRAG evidence enrichment failed; returning Qdrant evidence only",
                    extra={"error": str(e)},
                )

        return {"context": evidence, "nodes": nodes, "edges": edges, "mode": q.mode}

    # ---------------------------
    # Retrieval
    # ---------------------------

    def _retrieve_evidence(
        self,
        *,
        question: str,
        top_k: int,
        customer_id: Optional[str],
        include_admin_laws: bool,
        include_customer_docs: bool,
        mode: str,
    ) -> List[Dict[str, Any]]:
        """
        Retrieves evidence chunks from Qdrant.

        Returns a normalized list of dict items:
        {
          "source": "qdrant",
          "scope": "ADMIN_LAW"|"CUSTOMER_DOC",
          "score": float,
          "file_id": str|None,
          "chunk_index": int|None,
          "filename": str|None,
          "customer_id": str|None,
          "text": str,
        }
        """
        # If user explicitly requests lightrag-only, skip Qdrant retrieval.
        if mode == "lightrag":
            return []

        query_vector = self._gemini.embed_query(question)

        items: List[Dict[str, Any]] = []

        if include_admin_laws:
            filt = self._qdrant.build_filter(scope=FileScope.ADMIN_LAW.value)
            hits = self._qdrant.search(
                query_vector=query_vector, limit=top_k, filter_=filt
            )
            items.extend(
                self._normalize_qdrant_hits(hits, scope=FileScope.ADMIN_LAW.value)
            )

        if include_customer_docs and customer_id:
            filt = self._qdrant.build_filter(
                scope=FileScope.CUSTOMER_DOC.value, customer_id=customer_id
            )
            hits = self._qdrant.search(
                query_vector=query_vector, limit=top_k, filter_=filt
            )
            items.extend(
                self._normalize_qdrant_hits(hits, scope=FileScope.CUSTOMER_DOC.value)
            )

        # light de-dup by first 200 chars
        deduped: List[Dict[str, Any]] = []
        seen: set[str] = set()
        for it in sorted(
            items, key=lambda x: float(x.get("score") or 0.0), reverse=True
        ):
            key = (it.get("scope") or "") + "::" + (it.get("text") or "")[:200]
            if key in seen:
                continue
            seen.add(key)
            # Precompute a stable citation string for downstream prompt formatting
            it["citation"] = self._format_citation(it)
            deduped.append(it)

        return deduped

    def _normalize_qdrant_hits(
        self, hits: Sequence[Any], *, scope: str
    ) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for h in hits:
            payload = getattr(h, "payload", None) or {}
            text = payload.get("text") or ""

            out.append(
                {
                    "source": "qdrant",
                    "scope": scope,
                    "score": float(getattr(h, "score", 0.0) or 0.0),
                    "file_id": payload.get("file_id"),
                    "chunk_index": payload.get("chunk_index"),
                    "filename": payload.get("filename"),
                    "customer_id": payload.get("customer_id"),
                    "owner_id": payload.get("owner_id"),
                    "text": text,
                }
            )
        return out

    # ---------------------------
    # Prompting
    # ---------------------------

    def _build_system_prompt(self) -> str:
        """
        Builds the system prompt from DB prompts (with fallback to core/prompts).
        """
        style_guide = self._prompts.get_active_prompt_content(PromptType.STYLE_GUIDE)
        routing = self._prompts.get_active_prompt_content(PromptType.ROUTING)
        company_profile = self._prompts.get_active_prompt_content(
            PromptType.COMPANY_PROFILE
        )

        # Minimal hard guardrails (in addition to style guide)
        guardrails = (
            "Hard rules:\n"
            "- Do not invent numbers or facts.\n"
            "- If evidence is missing, state what is missing and what documents/data are needed (PBC style).\n"
            "- Keep output audit-grade, structured, concise.\n"
            "- Cite ISA/IFRS names only when relevant and supported by provided context.\n"
        )

        blocks = [
            b
            for b in [style_guide, routing, company_profile, guardrails]
            if b and b.strip()
        ]
        return "\n\n".join(blocks).strip()

    def _build_user_prompt(
        self,
        *,
        question: str,
        customer_id: Optional[str],
        evidence: List[Dict[str, Any]],
        lightrag_payload: Optional[Dict[str, Any]],
    ) -> str:
        """
        Builds the user prompt with clear sections and evidence.
        """
        laws = [e for e in evidence if e.get("scope") == FileScope.ADMIN_LAW.value]
        docs = [e for e in evidence if e.get("scope") == FileScope.CUSTOMER_DOC.value]

        laws_block = self._format_evidence_block("LAWS / STANDARDS (ADMIN)", laws)
        docs_block = self._format_evidence_block("CUSTOMER DOCUMENTS", docs)

        lightrag_block = ""
        if lightrag_payload and isinstance(lightrag_payload, dict):
            lr_answer = lightrag_payload.get("answer")
            if lr_answer:
                lightrag_block = (
                    "LIGHTRAG (graph-based) preliminary reasoning (may be incomplete):\n"
                    f"{lr_answer}\n"
                )

        customer_line = (
            f"Customer ID: {customer_id}"
            if customer_id
            else "Customer ID: (not provided)"
        )

        return (
            f"{customer_line}\n\n"
            f"{laws_block}\n\n"
            f"{docs_block}\n\n"
            f"{lightrag_block}\n\n"
            "TASK:\n"
            "- Answer the question using BOTH laws/standards and customer documents if available.\n"
            "- If the question requires numeric amounts (e.g., debt), extract from customer documents; do NOT guess.\n"
            "- Provide explicit 'Sources used' section with citations.\n"
            "- Provide a short RU summary if user question is in Russian.\n\n"
            f"QUESTION:\n{question}\n"
        )

    def _format_evidence_block(self, title: str, items: List[Dict[str, Any]]) -> str:
        if not items:
            return f"{title}:\n- (no retrieved evidence)"

        lines: List[str] = [f"{title}:"]
        for i, it in enumerate(items[:20], start=1):
            score = it.get("score")
            citation = it.get("citation") or self._format_citation(it)
            text = (it.get("text") or "").strip()

            header = f"[{i}] {citation}"
            if score is not None:
                header += f" score={score:.4f}"

            if not text:
                lines.append(f"- {header}: (text missing in payload)")
                continue

            # Keep context reasonably bounded and copy-paste safe
            snippet = text
            if len(snippet) > 1800:
                snippet = snippet[:1800] + " ...[TRUNCATED]"

            lines.append(f"- {header}\n{snippet}")

        return "\n".join(lines)

    def _format_citation(self, item: Dict[str, Any]) -> str:
        """
        Formats a human-readable citation for an evidence item.
        """
        scope = item.get("scope") or "UNKNOWN_SCOPE"
        filename = item.get("filename") or ""
        file_id = item.get("file_id") or ""
        chunk_index = item.get("chunk_index")

        src = filename if filename else file_id if file_id else "unknown_source"
        if chunk_index is not None:
            return f"scope={scope} source={src} chunk={chunk_index}"
        return f"scope={scope} source={src}"
