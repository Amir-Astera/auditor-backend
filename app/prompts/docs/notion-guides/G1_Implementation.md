# 🛠️ Implementation Guide

## 1. Qdrant Collections Setup

```python
# src/rag/qdrant_setup.py

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, ScalarQuantization

def create_qdrant_collections():
    """Создать два Qdrant namespace: G1 и G1_Client"""

    client = QdrantClient(url="http://localhost:6333")

    # G1: Knowledge Base (static)
    client.create_collection(
        collection_name="oson_knowledge",
        vectors_config=VectorParams(
            size=1536,  # OpenAI text-embedding-3-small
            distance=Distance.COSINE
        ),
        hnsw_config={
            "m": 16,
            "ef_construct": 128
        },
        quantization_config=ScalarQuantization(
            type="int8",
            always_ram=True
        ),
        on_disk_payload=True
    )

    # G1_Client: Client Documents (dynamic)
    client.create_collection(
        collection_name="client_documents",
        vectors_config=VectorParams(
            size=1536,
            distance=Distance.COSINE
        ),
        hnsw_config={
            "m": 16,
            "ef_construct": 128
        },
        quantization_config=ScalarQuantization(
            type="int8",
            always_ram=True
        ),
        on_disk_payload=True
    )
```

## 2. Metadata Indexing

```python
# Создание payload indexes для быстрого фильтра

from qdrant_client.models import PayloadSchemaType

# G1 indexes
client.create_payload_index(
    collection_name="oson_knowledge",
    field_name="block",
    field_schema=PayloadSchemaType.KEYWORD
)

client.create_payload_index(
    collection_name="oson_knowledge",
    field_name="isa_reference",
    field_schema=PayloadSchemaType.KEYWORD
)

client.create_payload_index(
    collection_name="oson_knowledge",
    field_name="cycle",
    field_schema=PayloadSchemaType.KEYWORD
)

# G1_Client indexes
client.create_payload_index(
    collection_name="client_documents",
    field_name="project_id",
    field_schema=PayloadSchemaType.KEYWORD  # КРИТИЧЕН!
)

client.create_payload_index(
    collection_name="client_documents",
    field_name="file_type",
    field_schema=PayloadSchemaType.KEYWORD
)
```

## 3. LightRAG Hybrid (Graph + Vector)

```python
# src/rag/lightrag_integration.py

from lightrag import LightRAG

def setup_lightrag(working_dir: str):
    """
    Настройка LightRAG для hybrid retrieval.

    Graph layer автоматически извлекает:
    - Entities: ISA 315, IAS 37, Revenue, Materiality
    - Relations: (ISA 315, identifies, Risks), ...
    """
    rag = LightRAG(
        working_dir=working_dir,
        llm_model_func=claude_llm_func,
        embedding_func=openai_embedding_func,
        graph_storage="NetworkXStorage",
        vector_storage="QdrantStorage",
        qdrant_config={
            "collection_name": "oson_knowledge",
            "url": "http://localhost:6333"
        }
    )

    return rag

# Индексация KB в LightRAG
def index_knowledge_base(rag: LightRAG):
    """Индексирует все Block A-F в LightRAG"""
    all_files = get_all_kb_files()  # A1-F2

    for file in all_files:
        content = Path(f"knowledge/{file}").read_text(encoding='utf-8')
        rag.insert(content)
```

## 4. Reranking Pipeline

```python
# src/rag/reranker.py

import cohere

def rerank_results(query: str, results: list, top_k: int = 5) -> list:
    """
    Cohere Rerank v4 для +20-35% accuracy.
    """
    co = cohere.Client(api_key=os.getenv("COHERE_API_KEY"))

    documents = [r.payload["text"] for r in results]

    reranked = co.rerank(
        model="rerank-english-v3.0",
        query=query,
        documents=documents,
        top_n=top_k
    )

    # Возвращаем top_k переранкированных результатов
    return [results[r.index] for r in reranked.results]
```

## 5. Filtered Search Example

```python
# Поиск рисков для Revenue цикла (Block B1)

def search_revenue_risks(query: str) -> list:
    """Search with filters for Block B, Cycle=Revenue"""

    # 1. Vector search (top 30)
    results = qdrant_client.search(
        collection_name="oson_knowledge",
        query_vector=embed(query),
        query_filter={
            "must": [
                {"key": "block", "match": {"value": "B"}},
                {"key": "file_id", "match": {"value": "B1"}},
                {"key": "cycle", "match": {"value": "Revenue"}}
            ]
        },
        limit=30
    )

    # 2. Rerank (top 5)
    final_results = rerank_results(query, results, top_k=5)

    return final_results
```

## 6. Client Documents Workflow

```python
# Upload client TB → G1_Client

def index_client_document(
    project_id: str,
    file_type: str,
    content: str
):
    """Векторизация клиентского документа в G1_Client"""

    chunks = chunk_document(content, chunk_size=512, overlap=50)

    for idx, chunk in enumerate(chunks):
        qdrant_client.upsert(
            collection_name="client_documents",
            points=[{
                "id": f"{project_id}_{file_type}_{idx}",
                "vector": embed(chunk.text),
                "payload": {
                    "project_id": project_id,  # КРИТИЧЕН для фильтрации
                    "file_type": file_type,    # trial_balance, sales_register, ...
                    "chunk_index": idx,
                    "text": chunk.text,
                    "uploaded_at": datetime.now().isoformat()
                }
            }]
        )
```

## 7. TODO для разработчика

- [ ] Установить Qdrant (Docker: `docker run -p 6333:6333 qdrant/qdrant`)
- [ ] Создать collections: `oson_knowledge`, `client_documents`
- [ ] Создать payload indexes для block, isa_reference, cycle, project_id
- [ ] Настроить LightRAG integration (hybrid graph+vector)
- [ ] Интегрировать Cohere Rerank v4
- [ ] Протестировать filtered search с metadata
- [ ] Написать тесты для G1_Client isolation (project_id filtering)

**Приоритет:** P1 (критический - основа всего RAG)

## 8. Связанные документы

- G2 PostgreSQL Schema — связь с реляционными данными
- G3 MinIO Structure — файлы перед векторизацией
- Development Rules — RAG best practices
