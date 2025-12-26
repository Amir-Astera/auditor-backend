# 🛠️ Implementation Guide

## 1. RAG Pipeline для Block B

```python
# src/rag/block_b_indexer.py

BLOCK_B_FILES = [
    "B1_Risk_Library_by_Cycle_v1.txt",
    "B2_PBC_Master_List_v1.txt",
    "B3_Glossary_EN-RU-UZ_v1.txt",
    "B4_Fraud_Risk_Factors_ISA240_v1.txt",
    "B5_Estimates_ISA540_Library_v1.txt",
    "B6_GoingConcern_ISA570_Indicators_v1.txt",
    "B7_RelatedParties_ISA550_Checklist_v1.txt",
    "B8_SubsequentEvents_ISA560_Library_v1.txt"
]

RAG_CONFIG = {
    "chunk_strategy": "section",       # по ==== и ---- маркерам
    "chunk_size": 1024,
    "chunk_overlap": 0,
    "retrieval_top_k": 30,
    "rerank_top_k": 5,
    "reranker": "cohere-rerank-v4"
}

def index_block_b():
    """Векторизация Block B в Qdrant namespace G1"""
    for filename in BLOCK_B_FILES:
        content = Path(f"knowledge/{filename}").read_text(encoding='utf-8')
        chunks = chunk_by_section(content, config=RAG_CONFIG)

        for chunk in chunks:
            qdrant_client.upsert(
                collection_name="oson_knowledge",
                points=[{
                    "id": generate_id(filename, chunk.index),
                    "vector": embed(chunk.text),
                    "payload": {
                        "block": "B",
                        "file_id": extract_file_id(filename),  # B1, B2, ...
                        "chunk_index": chunk.index,
                        "text": chunk.text,
                        "isa_reference": extract_isa_refs(chunk.text),
                        "cycle": extract_cycle(chunk.text),  # Revenue, Inventory, ...
                        "section": chunk.section
                    }
                }]
            )
```

## 2. Chunking Strategy

```python
# src/rag/chunking.py

def chunk_by_section(content: str, config: dict) -> list:
    """
    Разбивает документ по маркерам секций.

    Маркеры:
    - ==== (основные секции)
    - ---- (подсекции)
    """
    sections = re.split(r'^-{10,}|^={10,}', content, flags=re.MULTILINE)

    chunks = []
    for idx, section in enumerate(sections):
        if len(section.strip()) > 0:
            chunks.append({
                "index": idx,
                "text": section.strip(),
                "section": extract_section_title(section)
            })

    return chunks
```

## 3. PostgreSQL таблицы (для B2 PBC Tracker)

```sql
-- Трекер PBC запросов
CREATE TABLE pbc_tracker (
    pbc_id VARCHAR(20) PRIMARY KEY,
    project_id VARCHAR(50) REFERENCES projects(project_id),
    cycle VARCHAR(50),
    document_name TEXT,
    priority VARCHAR(10),
    status VARCHAR(20) DEFAULT 'Requested',
    requested_date DATE,
    received_date DATE,
    uploaded_file_path TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_pbc_project ON pbc_tracker(project_id);
CREATE INDEX idx_pbc_status ON pbc_tracker(status);
```

## 4. Query Example (B1 Risk Library)

```python
# Пользователь спрашивает про риски Revenue
query = "Какие риски для Revenue цикла?"

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

# Rerank top 5
final_context = rerank(results, query, top_k=5)
```

## 5. TODO для разработчика

- [ ] Создать `src/rag/block_b_indexer.py`
- [ ] Имплементировать `chunk_by_section()` с auto-detect маркеров
- [ ] Создать таблицу `pbc_tracker` в PostgreSQL (G2.6)
- [ ] Настроить Cohere Rerank API
- [ ] Протестировать retrieval для всех 8 файлов Block B
- [ ] Написать юнит-тесты для chunking стратегии

**Приоритет:** P1 (критический - основной контент KB)

## 6. Связанные документы

- G1 Qdrant Design — RAG pipeline, LightRAG hybrid
- G2 PostgreSQL Schema — таблица pbc_tracker (G2.6)
- Development Rules — Reranking best practices
