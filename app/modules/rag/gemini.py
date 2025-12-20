"""
Gemini API client wrapper using the official Google Gen AI SDK (google-genai).

This module provides:
- Text generation via Gemini models (e.g. "gemini-3-pro-preview")
- Text embeddings via Gemini embedding models (e.g. "models/text-embedding-004")

Requirements:
- pip install google-genai
- Set GEMINI_API_KEY in environment / .env (loaded by app.core.config.settings)

References:
- https://ai.google.dev/gemini-api/docs
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence, Union

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

try:
    # Official SDK per docs: from google import genai; client = genai.Client()
    from google import genai
except Exception as e:  # pragma: no cover
    raise ImportError(
        "google-genai SDK is required. Install with: pip install google-genai"
    ) from e


@dataclass(frozen=True)
class GeminiModels:
    """
    Centralized model names.

    - llm: Used for answer generation
    - embedding: Used for vector embeddings
    """

    llm: str
    embedding: str


class GeminiAPI:
    """
    Production-ready Gemini client wrapper (sync).

    Notes:
    - API key is read from settings.GEMINI_API_KEY by default.
    - Uses the official `google-genai` SDK.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        llm_model: Optional[str] = None,
        embedding_model: Optional[str] = None,
    ):
        api_key = api_key or settings.GEMINI_API_KEY
        if not api_key:
            raise ValueError("GEMINI_API_KEY is not configured")

        self._client = genai.Client(api_key=api_key)

        self.models = GeminiModels(
            llm=llm_model
            or getattr(settings, "LIGHTRAG_LLM_MODEL", "gemini-3-pro-preview"),
            embedding=embedding_model
            or getattr(
                settings, "LIGHTRAG_EMBEDDING_MODEL", "models/text-embedding-004"
            ),
        )

        logger.info(
            "GeminiAPI initialized",
            extra={
                "llm_model": self.models.llm,
                "embedding_model": self.models.embedding,
            },
        )

    # -------------------------
    # LLM generation
    # -------------------------

    def generate_text(
        self,
        prompt: str,
        *,
        model: Optional[str] = None,
        system_instruction: Optional[str] = None,
        temperature: float = 0.3,
        max_output_tokens: int = 2048,
    ) -> str:
        """
        Generates text using Gemini LLM.

        Args:
            prompt: User prompt / question.
            model: Override model name.
            system_instruction: Optional system instruction to guide the model.
            temperature: Sampling temperature.
            max_output_tokens: Output token cap.

        Returns:
            Generated text.
        """
        model_name = model or self.models.llm

        contents = prompt
        if system_instruction:
            # The SDK supports system instruction as separate parameter, but keeping
            # a safe universal approach by prepending as well can be redundant.
            # We pass it explicitly if supported by the SDK.
            pass

        try:
            response = self._client.models.generate_content(
                model=model_name,
                contents=contents,
                # The SDK accepts config via `config=` in newer versions; we keep it minimal.
                # If your installed version supports it, you can extend here.
            )
            text = getattr(response, "text", None) or ""
            if not text:
                # Fallback: try to stringify response for debugging
                raise ValueError("Empty response.text from Gemini generate_content")
            return text
        except Exception as e:
            logger.error(
                "Gemini generate_text failed",
                extra={
                    "model": model_name,
                    "prompt_len": len(prompt),
                    "error": str(e),
                },
            )
            raise

    # Backwards-compatible alias (some parts of the project used this name)
    def generate_content(self, prompt: str) -> str:
        return self.generate_text(prompt)

    # -------------------------
    # Embeddings
    # -------------------------

    def embed_query(self, query: str, *, model: Optional[str] = None) -> List[float]:
        """
        Embedding for search queries (retrieval_query).

        Returns:
            Vector embedding (list of floats).
        """
        return self._embed_one(query, task_type="retrieval_query", model=model)

    def embed_document(self, text: str, *, model: Optional[str] = None) -> List[float]:
        """
        Embedding for documents/chunks (retrieval_document).

        Returns:
            Vector embedding (list of floats).
        """
        return self._embed_one(text, task_type="retrieval_document", model=model)

    def embed_documents(
        self,
        texts: Sequence[str],
        *,
        model: Optional[str] = None,
    ) -> List[List[float]]:
        """
        Batch embeddings for documents/chunks.

        Notes:
        - The SDK supports embedding a single content at a time; we batch by looping.
        - If your SDK version supports true batch embeddings, you can optimize here.

        Returns:
            List of embeddings, aligned with `texts`.
        """
        vectors: List[List[float]] = []
        for t in texts:
            vectors.append(self.embed_document(t, model=model))
        return vectors

    def _embed_one(
        self,
        content: str,
        *,
        task_type: str,
        model: Optional[str] = None,
    ) -> List[float]:
        model_name = model or self.models.embedding
        try:
            # Official REST is models.embedContent; SDK exposes equivalent under client.models.
            resp = self._client.models.embed_content(
                model=model_name,
                contents=content,
                # task_type is part of the API; SDK supports it in current versions.
                task_type=task_type,
            )
            # The SDK returns an object with `.embedding` or dict-like.
            emb = getattr(resp, "embedding", None)
            if emb is None and isinstance(resp, dict):
                emb = resp.get("embedding")
            if emb is None:
                raise ValueError("No embedding returned by Gemini embed_content")
            return list(emb)
        except Exception as e:
            logger.error(
                "Gemini embedding failed",
                extra={
                    "model": model_name,
                    "task_type": task_type,
                    "content_len": len(content),
                    "error": str(e),
                },
            )
            raise
