from __future__ import annotations

from typing import Any, List

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    Range,
    ScoredPoint,
    VectorParams,
)

from app.core.logging import get_logger

logger = get_logger(__name__)


class QdrantVectorStore:
    """
    Обёртка над QdrantClient для хранения и поиска векторов файловых чанков.

    - Инициализирует коллекцию, если её нет.
    - Позволяет upsert'ить батч поинтов.
    - Даёт удобный метод поиска с Filter.
    """

    def __init__(self, url: str, collection_name: str, vector_size: int):
        # Используем Any, т.к. type-stubs qdrant-client неполные и basedpyright
        # не знает о методах search/upsert/...
        self._client: Any = QdrantClient(url=url)
        self._collection_name = collection_name
        self._vector_size = vector_size

        self._ensure_collection()

    def _ensure_collection(self) -> None:
        """
        Создаёт коллекцию, если её ещё нет.
        """
        collections = self._client.get_collections()
        exists = any(c.name == self._collection_name for c in collections.collections)

        if exists:
            logger.info(
                "Qdrant collection already exists",
                extra={"collection_name": self._collection_name},
            )
            return

        logger.info(
            "Creating Qdrant collection",
            extra={
                "collection_name": self._collection_name,
                "vector_size": self._vector_size,
            },
        )

        self._client.recreate_collection(
            collection_name=self._collection_name,
            vectors_config=VectorParams(
                size=self._vector_size,
                distance=Distance.COSINE,
            ),
        )

    def upsert_vectors(self, points: List[PointStruct]) -> None:
        """
        Upsert батча векторов в коллекцию.
        """
        if not points:
            return

        logger.info(
            "Upserting vectors to Qdrant",
            extra={
                "collection_name": self._collection_name,
                "points": len(points),
            },
        )

        self._client.upsert(
            collection_name=self._collection_name,
            points=points,
        )

    def search(
        self,
        query_vector: List[float],
        limit: int,
        filter_: Filter | None = None,
    ) -> List[ScoredPoint]:
        """
        Ищет ближайшие вектора по query_vector с опциональным фильтром по payload.
        
        Использует query_points для новых версий qdrant-client или fallback на старый API.
        """
        logger.info(
            "Searching in Qdrant",
            extra={
                "collection_name": self._collection_name,
                "limit": limit,
                "has_filter": filter_ is not None,
            },
        )

        # Try new API first (query_points - can accept vector directly or NearestQuery)
        try:
            # First try: pass vector directly (simplest approach)
            response = self._client.query_points(
                collection_name=self._collection_name,
                query=query_vector,  # Direct vector as query
                query_filter=filter_,
                limit=limit,
                with_payload=True,
                with_vectors=False,
            )
            
            # Extract ScoredPoint from QueryResponse
            if hasattr(response, "points"):
                return list(response.points)
            elif hasattr(response, "result") and hasattr(response.result, "points"):
                return list(response.result.points)
            elif isinstance(response, list):
                return response
            else:
                # Try to get points from response attributes
                for attr in ["points", "result", "data"]:
                    if hasattr(response, attr):
                        points = getattr(response, attr)
                        if isinstance(points, list):
                            return points
                logger.warning(
                    "Unknown response structure from query_points",
                    extra={"response_type": type(response).__name__},
                )
                return []
        except (AttributeError, TypeError, ValueError) as e:
            # Fallback: try passing vector directly (some SDK versions)
            try:
                response = self._client.query_points(
                    collection_name=self._collection_name,
                    query=query_vector,  # Direct vector
                    query_filter=filter_,
                    limit=limit,
                    with_payload=True,
                    with_vectors=False,
                )
                if hasattr(response, "points"):
                    return list(response.points)
                elif isinstance(response, list):
                    return response
                return []
            except Exception as e2:
                # Fallback to old API if query_points doesn't work
                logger.warning(
                    "query_points failed, trying legacy search API",
                    extra={"error": str(e), "error2": str(e2)},
                )
                try:
                    # Try legacy search method (for older qdrant-client versions)
                    results: List[ScoredPoint] = self._client.search(
                        collection_name=self._collection_name,
                        query_vector=query_vector,
                        limit=limit,
                        query_filter=filter_,
                    )
                    return results
                except AttributeError:
                    # If neither works, raise with helpful message
                    raise AttributeError(
                        f"QdrantClient does not have 'search' or 'query_points' method. "
                        f"Available methods: {[m for m in dir(self._client) if not m.startswith('_')][:20]}"
                    ) from e2

    def scroll(
        self,
        *,
        filter_: Filter | None,
        limit: int = 50,
        offset: Any | None = None,
    ) -> List[Any]:
        """Scroll points by filter without vector search (best-effort across SDK versions)."""
        try:
            response = self._client.scroll(
                collection_name=self._collection_name,
                scroll_filter=filter_,
                limit=limit,
                with_payload=True,
                with_vectors=False,
                offset=offset,
            )
            if isinstance(response, tuple) and len(response) >= 1:
                return list(response[0] or [])
            if hasattr(response, "points"):
                return list(response.points)
            if hasattr(response, "result") and hasattr(response.result, "points"):
                return list(response.result.points)
            if isinstance(response, list):
                return response
            return []
        except Exception:
            logger.exception(
                "Qdrant scroll failed",
                extra={"collection_name": self._collection_name, "limit": limit},
            )
            return []

    @staticmethod
    def build_filter(
        scope: str | None = None,
        customer_id: str | None = None,
        owner_id: str | None = None,
    ) -> Filter | None:
        """
        Построить Filter по payload (scope, customer_id, owner_id).

        payload мы кладём в upsert примерно таким образом:
        {
            "file_id": str(stored_file.id),
            "chunk_index": idx,
            "scope": stored_file.scope.value,
            "customer_id": stored_file.customer_id,
            "owner_id": str(stored_file.owner_id),
        }
        """
        conditions: list[FieldCondition] = []

        if scope is not None:
            conditions.append(
                FieldCondition(
                    key="scope",
                    match=MatchValue(value=scope),
                )
            )

        if customer_id is not None:
            conditions.append(
                FieldCondition(
                    key="customer_id",
                    match=MatchValue(value=customer_id),
                )
            )

        if owner_id is not None:
            conditions.append(
                FieldCondition(
                    key="owner_id",
                    match=MatchValue(value=owner_id),
                )
            )

        if not conditions:
            return None

        return Filter(must=conditions)

    @staticmethod
    def build_file_chunk_range_filter(
        *,
        file_id: str,
        chunk_start: int,
        chunk_end: int,
        scope: str | None = None,
        customer_id: str | None = None,
        owner_id: str | None = None,
    ) -> Filter:
        """Build filter for fetching neighbor chunks within one file."""
        conditions: list[FieldCondition] = [
            FieldCondition(key="file_id", match=MatchValue(value=file_id)),
            FieldCondition(key="chunk_index", range=Range(gte=int(chunk_start), lte=int(chunk_end))),
        ]

        base = QdrantVectorStore.build_filter(
            scope=scope,
            customer_id=customer_id,
            owner_id=owner_id,
        )
        if base is not None:
            conditions.extend(list(base.must or []))

        return Filter(must=conditions)