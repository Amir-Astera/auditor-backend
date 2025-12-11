from typing import Any, List

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams


class QdrantVectorStore:
    def __init__(self, url: str, collection_name: str, vector_size: int):
        self._client = QdrantClient(url=url)
        self._collection_name = collection_name
        self._vector_size = vector_size
        self._ensure_collection()

    def _ensure_collection(self) -> None:
        exists: bool
        try:
            exists = self._client.collection_exists(self._collection_name)
        except AttributeError:  # pragma: no cover - client variations
            try:
                self._client.get_collection(self._collection_name)
                exists = True
            except Exception:  # pragma: no cover - network dependent
                exists = False
        if not exists:
            self._client.create_collection(
                collection_name=self._collection_name,
                vectors_config=VectorParams(size=self._vector_size, distance=Distance.COSINE),
            )

    def upsert_vectors(self, points: List[PointStruct]) -> None:
        if not points:
            return
        self._client.upsert(collection_name=self._collection_name, points=points)

    def search(
        self,
        query_vector: List[float],
        limit: int,
        filter_: Any | None = None,
    ):
        return self._client.search(
            collection_name=self._collection_name,
            query_vector=query_vector,
            limit=limit,
            query_filter=filter_,
        )
