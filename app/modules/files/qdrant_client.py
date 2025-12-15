from __future__ import annotations

from typing import Any, List

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
        """
        logger.info(
            "Searching in Qdrant",
            extra={
                "collection_name": self._collection_name,
                "limit": limit,
                "has_filter": filter_ is not None,
            },
        )

        results: List[ScoredPoint] = self._client.search(
            collection_name=self._collection_name,
            query_vector=query_vector,
            limit=limit,
            query_filter=filter_,
        )
        return results

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

