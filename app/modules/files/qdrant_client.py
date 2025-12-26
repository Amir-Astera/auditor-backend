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

    @property
    def vector_size(self) -> int:
        return self._vector_size

    def _ensure_collection(self) -> None:
        """
        Создаёт коллекцию, если её ещё нет.
        """
        collections = self._client.get_collections()
        exists = any(c.name == self._collection_name for c in collections.collections)

        if exists:
            # Try to read actual vector size from Qdrant (collection could have been created earlier)
            try:
                info = self._client.get_collection(self._collection_name)
                # qdrant-client response shapes vary between versions; keep it defensive
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

        if hasattr(self._client, "search"):
            results: List[ScoredPoint] = self._client.search(
                collection_name=self._collection_name,
                query_vector=query_vector,
                limit=limit,
                query_filter=filter_,
            )
            return results

        resp = self._client.query_points(
            collection_name=self._collection_name,
            query=query_vector,
            limit=limit,
            query_filter=filter_,
            with_payload=True,
        )

        points = getattr(resp, "points", None)
        if points is None:
            points = getattr(resp, "result", None)
        if points is None:
            points = []

        return list(points)

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