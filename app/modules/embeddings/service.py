"""
Production-grade Embedding Service with multiple providers.

Supports:
- Google Gemini text-embedding-004 (primary)
- OpenAI text-embedding-3-small (fallback)
- SentenceTransformers (local fallback)

Features:
- Automatic fallback on provider failure
- Batch processing for efficiency
- Caching for repeated queries
- Rate limiting awareness
"""

import logging
import hashlib
from typing import List, Optional, Dict, Any
from functools import lru_cache
import requests
import time

logger = logging.getLogger(__name__)


class EmbeddingProvider:
    """Base class for embedding providers."""
    
    name: str = "base"
    vector_size: int = 768
    
    def embed(self, texts: List[str]) -> List[List[float]]:
        raise NotImplementedError
    
    def embed_single(self, text: str) -> List[float]:
        return self.embed([text])[0]


class GeminiEmbeddingProvider(EmbeddingProvider):
    """
    Google Gemini embedding provider.
    
    Model: text-embedding-004
    Vector size: 768
    Max tokens: 2048
    Rate limit: 1500 RPM (free tier)
    """
    
    name = "gemini"
    vector_size = 768
    
    def __init__(self, api_key: str, model: str = "text-embedding-004"):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models"
        self._last_request_time = 0
        self._min_request_interval = 0.05  # 50ms between requests (rate limiting)
        
        logger.info(f"Initialized Gemini embedding provider with model: {model}")
    
    def _rate_limit(self):
        """Simple rate limiting."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self._min_request_interval:
            time.sleep(self._min_request_interval - elapsed)
        self._last_request_time = time.time()
    
    def embed(self, texts: List[str]) -> List[List[float]]:
        """Get embeddings from Gemini API."""
        embeddings = []
        
        for text in texts:
            self._rate_limit()
            
            # Truncate text if too long (max ~2048 tokens ≈ 8000 chars)
            if len(text) > 8000:
                text = text[:8000]
            
            url = f"{self.base_url}/{self.model}:embedContent"
            headers = {"Content-Type": "application/json"}
            params = {"key": self.api_key}
            data = {
                "model": f"models/{self.model}",
                "content": {"parts": [{"text": text}]}
            }
            
            try:
                response = requests.post(
                    url, 
                    headers=headers, 
                    params=params, 
                    json=data,
                    timeout=30,
                    verify=False  # For corporate proxies
                )
                response.raise_for_status()
                
                result = response.json()
                if "embedding" in result and "values" in result["embedding"]:
                    embedding = result["embedding"]["values"]
                    embeddings.append(embedding)
                    logger.debug(f"Gemini embedding generated, dim={len(embedding)}")
                else:
                    logger.error(f"Unexpected Gemini response structure: {result}")
                    raise ValueError("Invalid embedding response")
                    
            except requests.exceptions.RequestException as e:
                logger.error(f"Gemini embedding request failed: {e}")
                raise
            except Exception as e:
                logger.error(f"Gemini embedding failed: {e}")
                raise
        
        return embeddings
    
    def embed_batch(self, texts: List[str], batch_size: int = 100) -> List[List[float]]:
        """
        Batch embedding with Gemini batchEmbedContents API.
        More efficient for large batches.
        """
        if len(texts) <= 5:
            return self.embed(texts)
        
        url = f"{self.base_url}/{self.model}:batchEmbedContents"
        headers = {"Content-Type": "application/json"}
        params = {"key": self.api_key}
        
        all_embeddings = []
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            
            # Truncate texts
            batch = [t[:8000] if len(t) > 8000 else t for t in batch]
            
            data = {
                "requests": [
                    {
                        "model": f"models/{self.model}",
                        "content": {"parts": [{"text": text}]}
                    }
                    for text in batch
                ]
            }
            
            try:
                self._rate_limit()
                response = requests.post(
                    url,
                    headers=headers,
                    params=params,
                    json=data,
                    timeout=60,
                    verify=False
                )
                response.raise_for_status()
                
                result = response.json()
                if "embeddings" in result:
                    for emb in result["embeddings"]:
                        all_embeddings.append(emb["values"])
                else:
                    # Fallback to single requests
                    logger.warning("Batch embedding failed, falling back to single requests")
                    all_embeddings.extend(self.embed(batch))
                    
            except Exception as e:
                logger.error(f"Batch embedding failed: {e}, falling back to single requests")
                all_embeddings.extend(self.embed(batch))
        
        return all_embeddings


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """
    OpenAI embedding provider as fallback.
    
    Model: text-embedding-3-small
    Vector size: 1536
    """
    
    name = "openai"
    vector_size = 1536
    
    def __init__(self, api_key: str, model: str = "text-embedding-3-small"):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://api.openai.com/v1/embeddings"
        
        logger.info(f"Initialized OpenAI embedding provider with model: {model}")
    
    def embed(self, texts: List[str]) -> List[List[float]]:
        """Get embeddings from OpenAI API."""
        # Truncate texts (max 8191 tokens ≈ 32000 chars for safety)
        texts = [t[:32000] if len(t) > 32000 else t for t in texts]
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        data = {
            "input": texts,
            "model": self.model
        }
        
        try:
            response = requests.post(
                self.base_url, 
                headers=headers, 
                json=data,
                timeout=60
            )
            response.raise_for_status()
            
            result = response.json()
            embeddings = [item["embedding"] for item in result["data"]]
            logger.debug(f"OpenAI embeddings generated, count={len(embeddings)}")
            return embeddings
            
        except Exception as e:
            logger.error(f"OpenAI embedding failed: {e}")
            raise


class SentenceTransformerProvider(EmbeddingProvider):
    """
    Local SentenceTransformers provider.
    
    Model: paraphrase-multilingual-MiniLM-L12-v2 (supports RU/EN/UZ)
    Vector size: 384
    """
    
    name = "sentence_transformers"
    vector_size = 384
    
    def __init__(self, model_name: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"):
        self.model_name = model_name
        self.model = None
        self._load_model()
    
    def _load_model(self):
        """Lazy load model."""
        try:
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer(self.model_name)
            logger.info(f"Loaded SentenceTransformer model: {self.model_name}")
        except ImportError:
            logger.warning("sentence-transformers not installed, provider unavailable")
            self.model = None
        except Exception as e:
            logger.error(f"Failed to load SentenceTransformer: {e}")
            self.model = None
    
    def embed(self, texts: List[str]) -> List[List[float]]:
        """Get embeddings from local model."""
        if not self.model:
            raise RuntimeError("SentenceTransformer model not loaded")
        
        try:
            embeddings = self.model.encode(
                texts, 
                convert_to_numpy=True,
                show_progress_bar=False
            )
            return embeddings.tolist()
        except Exception as e:
            logger.error(f"SentenceTransformer embedding failed: {e}")
            raise


class EmbeddingService:
    """
    Production embedding service with multiple providers and fallback.
    
    Usage:
        service = EmbeddingService(gemini_api_key="...")
        embeddings = service.embed(["text1", "text2"])
        single = service.embed_single("text")
    """
    
    def __init__(
        self,
        gemini_api_key: Optional[str] = None,
        openai_api_key: Optional[str] = None,
        use_local_fallback: bool = True,
        cache_enabled: bool = True,
    ):
        self.providers: List[EmbeddingProvider] = []
        self.cache_enabled = cache_enabled
        self._cache: Dict[str, List[float]] = {}
        self._cache_max_size = 10000
        
        self._init_providers(gemini_api_key, openai_api_key, use_local_fallback)
        
        if not self.providers:
            raise RuntimeError("No embedding providers available")
        
        # Primary provider determines vector size
        self.vector_size = self.providers[0].vector_size
        logger.info(f"EmbeddingService initialized with {len(self.providers)} providers, vector_size={self.vector_size}")
    
    def _init_providers(
        self, 
        gemini_api_key: Optional[str],
        openai_api_key: Optional[str],
        use_local_fallback: bool
    ):
        """Initialize available providers in priority order."""
        
        # 1. Gemini as primary (free tier available)
        if gemini_api_key:
            try:
                provider = GeminiEmbeddingProvider(gemini_api_key)
                self.providers.append(provider)
                logger.info("Added Gemini embedding provider (primary)")
            except Exception as e:
                logger.error(f"Failed to init Gemini provider: {e}")
        
        # 2. OpenAI as fallback
        if openai_api_key:
            try:
                provider = OpenAIEmbeddingProvider(openai_api_key)
                self.providers.append(provider)
                logger.info("Added OpenAI embedding provider (fallback)")
            except Exception as e:
                logger.error(f"Failed to init OpenAI provider: {e}")
        
        # 3. Local SentenceTransformers as last resort
        if use_local_fallback:
            try:
                provider = SentenceTransformerProvider()
                if provider.model is not None:
                    self.providers.append(provider)
                    logger.info("Added SentenceTransformer provider (local fallback)")
            except Exception as e:
                logger.error(f"Failed to init SentenceTransformer provider: {e}")
    
    def _get_cache_key(self, text: str) -> str:
        """Generate cache key for text."""
        return hashlib.md5(text.encode()).hexdigest()
    
    def _get_from_cache(self, text: str) -> Optional[List[float]]:
        """Get embedding from cache."""
        if not self.cache_enabled:
            return None
        key = self._get_cache_key(text)
        return self._cache.get(key)
    
    def _add_to_cache(self, text: str, embedding: List[float]):
        """Add embedding to cache with size limit."""
        if not self.cache_enabled:
            return
        if len(self._cache) >= self._cache_max_size:
            # Remove oldest entries (simple FIFO)
            keys_to_remove = list(self._cache.keys())[:1000]
            for key in keys_to_remove:
                del self._cache[key]
        key = self._get_cache_key(text)
        self._cache[key] = embedding
    
    def embed(self, texts: List[str]) -> List[List[float]]:
        """
        Get embeddings for texts using available providers with fallback.
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List of embedding vectors
        """
        if not texts:
            return []
        
        # Check cache first
        results = [None] * len(texts)
        texts_to_embed = []
        indices_to_embed = []
        
        for i, text in enumerate(texts):
            cached = self._get_from_cache(text)
            if cached is not None:
                results[i] = cached
            else:
                texts_to_embed.append(text)
                indices_to_embed.append(i)
        
        if not texts_to_embed:
            return results
        
        # Try providers in order
        embeddings = None
        last_error = None
        
        for provider in self.providers:
            try:
                logger.debug(f"Trying embedding provider: {provider.name}")
                embeddings = provider.embed(texts_to_embed)
                
                if embeddings and len(embeddings) == len(texts_to_embed):
                    logger.info(f"Embeddings generated using {provider.name}")
                    break
                else:
                    logger.warning(f"Provider {provider.name} returned invalid embeddings")
                    embeddings = None
                    
            except Exception as e:
                last_error = e
                logger.warning(f"Provider {provider.name} failed: {e}")
                continue
        
        if embeddings is None:
            logger.error(f"All embedding providers failed. Last error: {last_error}")
            raise RuntimeError(f"All embedding providers failed: {last_error}")
        
        # Fill results and cache
        for i, idx in enumerate(indices_to_embed):
            results[idx] = embeddings[i]
            self._add_to_cache(texts_to_embed[i], embeddings[i])
        
        return results
    
    def embed_single(self, text: str) -> List[float]:
        """Embed single text."""
        embeddings = self.embed([text])
        return embeddings[0]
    
    def embed_batch(self, texts: List[str], batch_size: int = 100) -> List[List[float]]:
        """
        Embed large batch of texts efficiently.
        
        Args:
            texts: List of texts
            batch_size: Size of each batch
            
        Returns:
            List of embeddings
        """
        all_embeddings = []
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            embeddings = self.embed(batch)
            all_embeddings.extend(embeddings)
            
            if i > 0 and i % (batch_size * 10) == 0:
                logger.info(f"Embedded {i}/{len(texts)} texts")
        
        return all_embeddings
    
    def clear_cache(self):
        """Clear embedding cache."""
        self._cache.clear()
        logger.info("Embedding cache cleared")


# Global instance - will be initialized on first import with settings
_embedding_service: Optional[EmbeddingService] = None


def get_embedding_service() -> EmbeddingService:
    """Get or create global embedding service instance."""
    global _embedding_service
    
    if _embedding_service is None:
        # Import here to avoid circular imports
        from app.core.config import settings

        _embedding_service = EmbeddingService(
            gemini_api_key=settings.GEMINI_API_KEY,
            openai_api_key=settings.OPENAI_API_KEY,
            use_local_fallback=True,
        )
    
    return _embedding_service


# Convenience function
def embed(texts: List[str]) -> List[List[float]]:
    """Embed texts using global service."""
    return get_embedding_service().embed(texts)


def embed_single(text: str) -> List[float]:
    """Embed single text using global service."""
    return get_embedding_service().embed_single(text)
