"""Embeddings module for vector generation."""

from app.modules.embeddings.service import EmbeddingService, embed, embed_single, get_embedding_service

__all__ = ["EmbeddingService", "get_embedding_service", "embed", "embed_single"]
