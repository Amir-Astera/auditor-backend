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

import json
import re
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol, Sequence, runtime_checkable

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.modules.files.models import FileScope
from app.modules.files.models import FileChunk
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
    owner_id: Optional[str] = None
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
    debug: Optional[Dict[str, Any]] = None


class HybridRAGService:
    """
    Hybrid RAG:
    - Qdrant supplies evidence (fast retrieval + filters)
    - LightRAG optionally enriches reasoning
    - Gemini generates final answer using strict audit-grade prompts
    """

    def __init__(
        self,
        db: Session | None,
        gemini: GeminiAPI,
        prompts: PromptsProvider,
        qdrant_admin: QdrantVectorStore,
        qdrant_client: QdrantVectorStore,
        lightrag: LightRAGService | None = None,
    ):
        self._db = db
        self._gemini = gemini
        self._prompts = prompts
        self._qdrant_admin = qdrant_admin
        self._qdrant_client = qdrant_client
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

        policy = self._policy_gate(
            owner_id=q.owner_id,
            customer_id=q.customer_id,
            include_admin_laws=q.include_admin_laws,
            include_customer_docs=q.include_customer_docs,
        )

        router = self._route_question(
            question=q.question,
            customer_id=q.customer_id,
            owner_id=q.owner_id,
            include_admin_laws=q.include_admin_laws,
            include_customer_docs=q.include_customer_docs,
        )

        plan = self._build_query_plan(
            question=q.question,
            router=router,
        )

        retrieved = self._retrieve_multi(
            plan=plan,
            policy=policy,
            include_admin_laws=router.get("include_admin_laws", False),
            include_customer_docs=router.get("include_customer_docs", False),
            retrieve_k=30,
            mode=q.mode,
        )

        reranked = self._rerank_llm(
            question=q.question,
            candidates=retrieved,
            final_k=min(top_k, 5),
        )

        evidence = self._build_evidence_sql(
            seeds=reranked,
            policy=policy,
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
            debug={
                "policy": policy,
                "router": router,
                "plan": plan,
                "retrieved_count": len(retrieved),
                "reranked_count": len(reranked),
                "evidence_count": len(evidence),
            },
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

        policy = self._policy_gate(
            owner_id=q.owner_id,
            customer_id=q.customer_id,
            include_admin_laws=q.include_admin_laws,
            include_customer_docs=q.include_customer_docs,
        )

        router = self._route_question(
            question=q.question,
            customer_id=q.customer_id,
            owner_id=q.owner_id,
            include_admin_laws=q.include_admin_laws,
            include_customer_docs=q.include_customer_docs,
        )

        plan = self._build_query_plan(
            question=q.question,
            router=router,
        )

        retrieved = self._retrieve_multi(
            plan=plan,
            policy=policy,
            include_admin_laws=router.get("include_admin_laws", False),
            include_customer_docs=router.get("include_customer_docs", False),
            retrieve_k=30,
            mode=q.mode,
        )

        reranked = self._rerank_llm(
            question=q.question,
            candidates=retrieved,
            final_k=min(top_k, 5),
        )

        evidence = self._build_evidence_sql(
            seeds=reranked,
            policy=policy,
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

        return {
            "context": evidence,
            "nodes": nodes,
            "edges": edges,
            "mode": q.mode,
            "debug": {
                "policy": policy,
                "router": router,
                "plan": plan,
                "retrieved_count": len(retrieved),
                "reranked_count": len(reranked),
                "evidence_count": len(evidence),
            },
        }

    def _policy_gate(
        self,
        *,
        owner_id: Optional[str],
        customer_id: Optional[str],
        include_admin_laws: bool,
        include_customer_docs: bool,
    ) -> Dict[str, Any]:
        allowed_scopes: List[str] = []
        if include_admin_laws and owner_id is None:
            allowed_scopes.append(FileScope.ADMIN_LAW.value)
        if include_customer_docs and customer_id:
            allowed_scopes.append(FileScope.CUSTOMER_DOC.value)

        return {
            "tenant_id": None,
            "customer_id": customer_id,
            "allowed_scopes": allowed_scopes,
            "filters": {
                "tenant_id": None,
                "customer_id": customer_id,
                "owner_id": owner_id,
                "scope": allowed_scopes,
            },
        }

    def _route_question(
        self,
        *,
        question: str,
        customer_id: Optional[str],
        owner_id: Optional[str],
        include_admin_laws: bool,
        include_customer_docs: bool,
    ) -> Dict[str, Any]:
        q = (question or "").lower()
        legal_kw = (
            "isa",
            "ifrs",
            "фсбу",
            "закон",
            "кодекс",
            "постанов",
            "54-фз",
            "54 фз",
            "пбу",
            "гк",
            "нк",
        )
        finance_kw = (
            "выруч",
            "ндс",
            "дивид",
            "сумм",
            "оборот",
            "платеж",
            "выписк",
            "контраг",
            "транзак",
            "банк",
        )

        is_legal = any(k in q for k in legal_kw)
        is_finance = any(k in q for k in finance_kw)

        domain = "both" if (is_legal and is_finance) else "legal" if is_legal else "finance" if is_finance else "both"

        resolved_customer_docs = bool(include_customer_docs and customer_id)
        resolved_admin_laws = bool(include_admin_laws)

        required_sources: List[str] = []
        if resolved_admin_laws:
            required_sources.append("kb_admin")
        if resolved_customer_docs:
            required_sources.append("client_docs")

        required_tools: List[str] = ["qdrant"]
        if domain in ("legal", "both"):
            required_tools.append("lightrag")

        ambiguity_tier = 1
        if domain == "both":
            ambiguity_tier = 2
        if resolved_customer_docs and not customer_id:
            ambiguity_tier = 3

        return {
            "domain": domain,
            "required_sources": required_sources,
            "required_tools": required_tools,
            "filters": {
                "customer_id": customer_id,
                "owner_id": owner_id,
            },
            "include_admin_laws": resolved_admin_laws,
            "include_customer_docs": resolved_customer_docs,
            "ambiguity_tier": ambiguity_tier,
        }

    def _build_query_plan(self, *, question: str, router: Dict[str, Any]) -> Dict[str, Any]:
        """Gemini-prompted planner. Returns {subqueries:[], must_find:[]}"""
        prompt = (
            "You are a retrieval planner for an audit-grade RAG system.\n"
            "Return STRICT JSON only.\n\n"
            f"Question: {question}\n"
            f"Domain: {router.get('domain')}\n"
            "Task: produce 3-6 short search subqueries and 2-6 'must_find' items.\n"
            "JSON schema: {\"subqueries\": [..], \"must_find\": [..]}\n"
        )
        try:
            txt = self._gemini.generate_text(
                prompt,
                model=getattr(settings, "LIGHTRAG_LLM_MODEL", "gemini-3-pro-preview"),
                temperature=0.2,
                max_output_tokens=512,
            )
            data = self._safe_json_extract(txt)
            subq = [str(x).strip() for x in (data.get("subqueries") or []) if str(x).strip()]
            must = [str(x).strip() for x in (data.get("must_find") or []) if str(x).strip()]
            if not subq:
                subq = [question]
            return {"subqueries": subq[:6], "must_find": must[:6]}
        except Exception as e:
            logger.warning("Planner failed; fallback to single query", extra={"error": str(e)})
            return {"subqueries": [question], "must_find": []}

    def _retrieve_multi(
        self,
        *,
        plan: Dict[str, Any],
        policy: Dict[str, Any],
        include_admin_laws: bool,
        include_customer_docs: bool,
        retrieve_k: int,
        mode: str,
    ) -> List[Dict[str, Any]]:
        if mode == "lightrag":
            return []

        subqueries = list(plan.get("subqueries") or [])
        if not subqueries:
            subqueries = []

        merged: Dict[str, Dict[str, Any]] = {}
        for sq in subqueries[:6]:
            sq_text = str(sq).strip()
            if not sq_text:
                continue
            query_vector = self._gemini.embed_query(sq_text)

            if include_admin_laws:
                filt = self._qdrant_admin.build_filter(scope=FileScope.ADMIN_LAW.value)
                hits = self._qdrant_admin.search(
                    query_vector=query_vector,
                    limit=retrieve_k,
                    filter_=filt,
                )
                for it in self._normalize_qdrant_hits(hits, scope=FileScope.ADMIN_LAW.value):
                    key = str(it.get("chunk_id") or "")
                    prev = merged.get(key)
                    if prev is None or float(it.get("score") or 0.0) > float(prev.get("score") or 0.0):
                        merged[key] = it

            if include_customer_docs and policy.get("customer_id"):
                customer_id = policy.get("customer_id")
                owner_id = (policy.get("filters") or {}).get("owner_id")
                filt = self._qdrant_client.build_filter(
                    scope=FileScope.CUSTOMER_DOC.value,
                    customer_id=customer_id,
                    owner_id=owner_id,
                )
                hits = self._qdrant_client.search(
                    query_vector=query_vector,
                    limit=retrieve_k,
                    filter_=filt,
                )
                for it in self._normalize_qdrant_hits(hits, scope=FileScope.CUSTOMER_DOC.value):
                    key = str(it.get("chunk_id") or "")
                    prev = merged.get(key)
                    if prev is None or float(it.get("score") or 0.0) > float(prev.get("score") or 0.0):
                        merged[key] = it

        items = list(merged.values())
        items.sort(key=lambda x: float(x.get("score") or 0.0), reverse=True)
        for it in items:
            it["citation"] = self._format_citation(it)
        return items[: max(retrieve_k, 30)]

    def _rerank_llm(
        self,
        *,
        question: str,
        candidates: List[Dict[str, Any]],
        final_k: int,
    ) -> List[Dict[str, Any]]:
        final_k = max(1, int(final_k))
        if not candidates:
            return []
        if len(candidates) <= final_k:
            return candidates

        items = candidates[:30]
        lines: List[str] = []
        for i, c in enumerate(items, start=1):
            txt = (c.get("text") or "").strip()
            if len(txt) > 400:
                txt = txt[:400] + "..."
            lines.append(f"[{i}] {c.get('citation')}\n{txt}")

        prompt = (
            "You are a reranker. Return STRICT JSON only.\n"
            "Select the best items to answer the question.\n"
            f"Return schema: {{\"selected\": [1,2,..]}} with {final_k} ids.\n\n"
            f"QUESTION:\n{question}\n\n"
            "CANDIDATES:\n" + "\n\n".join(lines)
        )

        try:
            txt = self._gemini.generate_text(
                prompt,
                model=getattr(settings, "LIGHTRAG_LLM_MODEL", "gemini-3-pro-preview"),
                temperature=0.0,
                max_output_tokens=256,
            )
            data = self._safe_json_extract(txt)
            sel = data.get("selected") or []
            idxs: List[int] = []
            for x in sel:
                try:
                    xi = int(x)
                    if 1 <= xi <= len(items):
                        idxs.append(xi)
                except Exception:
                    continue
            if not idxs:
                return items[:final_k]
            dedup: List[Dict[str, Any]] = []
            seen: set[int] = set()
            for xi in idxs:
                if xi in seen:
                    continue
                seen.add(xi)
                dedup.append(items[xi - 1])
                if len(dedup) >= final_k:
                    break
            if len(dedup) < final_k:
                for c in items:
                    if len(dedup) >= final_k:
                        break
                    if c not in dedup:
                        dedup.append(c)
            return dedup
        except Exception as e:
            logger.warning("LLM rerank failed; fallback by score", extra={"error": str(e)})
            return items[:final_k]

    def _expand_neighbors(
        self,
        *,
        seeds: List[Dict[str, Any]],
        customer_id: Optional[str],
        owner_id: Optional[str],
        neighbor_window: int,
    ) -> List[Dict[str, Any]]:
        if not seeds:
            return []

        out: Dict[str, Dict[str, Any]] = {}
        for s in seeds:
            file_id = s.get("file_id")
            chunk_index = s.get("chunk_index")
            scope = s.get("scope")
            if not file_id or chunk_index is None:
                key = f"{scope}::{file_id}::{chunk_index}"
                out[key] = s
                continue

            start = max(0, int(chunk_index) - int(neighbor_window))
            end = int(chunk_index) + int(neighbor_window)

            store = self._qdrant_admin if scope == FileScope.ADMIN_LAW.value else self._qdrant_client
            filt = store.build_file_chunk_range_filter(
                file_id=str(file_id),
                chunk_start=start,
                chunk_end=end,
                scope=str(scope) if scope else None,
                customer_id=customer_id if scope == FileScope.CUSTOMER_DOC.value else None,
                owner_id=owner_id if scope == FileScope.CUSTOMER_DOC.value else None,
            )
            points = store.scroll(filter_=filt, limit=25)
            for p in points:
                payload = getattr(p, "payload", None) or {}
                it = {
                    "source": "qdrant",
                    "scope": scope,
                    "score": float(s.get("score") or 0.0),
                    "file_id": payload.get("file_id"),
                    "chunk_index": payload.get("chunk_index"),
                    "filename": payload.get("filename"),
                    "customer_id": payload.get("customer_id"),
                    "owner_id": payload.get("owner_id"),
                    "text": payload.get("text") or "",
                }
                key = f"{it.get('scope')}::{it.get('file_id')}::{it.get('chunk_index')}"
                it["citation"] = self._format_citation(it)
                out[key] = it

        items = list(out.values())
        items.sort(key=lambda x: (x.get("scope") or "", str(x.get("file_id") or ""), int(x.get("chunk_index") or 0)))
        return items

    def _safe_json_extract(self, text: str) -> Dict[str, Any]:
        if not text:
            return {}
        s = text.strip()
        try:
            obj = json.loads(s)
            return obj if isinstance(obj, dict) else {}
        except Exception:
            pass

        m = re.search(r"\{[\s\S]*\}", s)
        if not m:
            return {}
        try:
            obj = json.loads(m.group(0))
            return obj if isinstance(obj, dict) else {}
        except Exception:
            return {}

    # ---------------------------
    # Retrieval
    # ---------------------------

    def _retrieve_evidence(
        self,
        *,
        question: str,
        top_k: int,
        customer_id: Optional[str],
        owner_id: Optional[str],
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
            filt = self._qdrant_admin.build_filter(scope=FileScope.ADMIN_LAW.value)
            hits = self._qdrant_admin.search(
                query_vector=query_vector, limit=top_k, filter_=filt
            )
            items.extend(
                self._normalize_qdrant_hits(hits, scope=FileScope.ADMIN_LAW.value)
            )

        if include_customer_docs and customer_id:
            filt = self._qdrant_client.build_filter(
                scope=FileScope.CUSTOMER_DOC.value,
                customer_id=customer_id,
                owner_id=owner_id,
            )
            hits = self._qdrant_client.search(
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
                    "chunk_id": payload.get("chunk_id"),
                    "file_id": payload.get("file_id"),
                    "chunk_index": payload.get("chunk_index"),
                    "filename": payload.get("filename"),
                    "customer_id": payload.get("customer_id"),
                    "owner_id": payload.get("owner_id"),
                    "text": text,
                }
            )
        return out

    def _build_evidence_sql(self, *, seeds: List[Dict[str, Any]], policy: Dict[str, Any]) -> List[Dict[str, Any]]:
        if not seeds:
            return []
        if self._db is None:
            return seeds

        out: List[Dict[str, Any]] = []
        seen: set[str] = set()

        customer_id = policy.get("customer_id")
        owner_id = (policy.get("filters") or {}).get("owner_id")

        for s in seeds:
            chunk_id = s.get("chunk_id")
            file_id = s.get("file_id")
            chunk_index = s.get("chunk_index")
            scope = s.get("scope")
            score = float(s.get("score") or 0.0)

            if chunk_id:
                try:
                    chunk_uuid = uuid.UUID(str(chunk_id))
                except Exception:
                    chunk_uuid = None

                row = self._db.get(FileChunk, chunk_uuid) if chunk_uuid is not None else None
                if row is not None:
                    file_id = row.file_id
                    chunk_index = int(row.chunk_index)
                    scope = row.scope or scope

            if not file_id or chunk_index is None:
                continue

            k = 1
            base_text = (s.get("text") or "").strip()
            if base_text and (
                (len(base_text) > 0 and base_text[-1] not in ".?!:)" )
                or (len(base_text) > 0 and base_text[0].islower())
            ):
                k = 2

            start = max(0, int(chunk_index) - k)
            end = int(chunk_index) + k

            try:
                file_uuid = file_id if isinstance(file_id, uuid.UUID) else uuid.UUID(str(file_id))
            except Exception:
                continue

            q = self._db.query(FileChunk).filter(
                FileChunk.file_id == file_uuid,
                FileChunk.chunk_index >= start,
                FileChunk.chunk_index <= end,
            )
            if scope:
                q = q.filter(FileChunk.scope == scope)
            if scope == FileScope.CUSTOMER_DOC.value and customer_id:
                q = q.filter(FileChunk.customer_id == customer_id)
            if scope == FileScope.CUSTOMER_DOC.value and owner_id:
                q = q.filter(FileChunk.owner_id == owner_id)

            rows = q.order_by(FileChunk.chunk_index.asc()).all()
            if not rows:
                continue

            citations = [
                {
                    "chunk_id": str(r.id),
                    "file_id": str(r.file_id),
                    "chunk_index": int(r.chunk_index),
                }
                for r in rows
            ]
            combined = "\n\n".join([str(r.text or "") for r in rows]).strip()

            evidence_item = {
                "source": "sql",
                "scope": scope,
                "score": score,
                "chunk_id": str(rows[len(rows) // 2].id),
                "file_id": str(rows[0].file_id),
                "chunk_index": int(rows[0].chunk_index),
                "chunk_index_range": [int(rows[0].chunk_index), int(rows[-1].chunk_index)],
                "customer_id": rows[0].customer_id,
                "owner_id": rows[0].owner_id,
                "text": combined,
                "citations": citations,
            }
            evidence_item["citation"] = self._format_citation(evidence_item)

            dedup_key = f"{evidence_item.get('file_id')}::{evidence_item.get('chunk_index_range')}"
            if dedup_key in seen:
                continue
            seen.add(dedup_key)
            out.append(evidence_item)

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
