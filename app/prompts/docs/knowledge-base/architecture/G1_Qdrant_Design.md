# G1: Qdrant Architecture

**Назначение:** Векторное хранилище для Knowledge Base (Block B/C/D/F) и клиентских документов.

**Ключевое различие:** Два независимых namespace — G1 (статичный KB) и G1_Client (динамичный per-project).

---

## Два Qdrant Namespace

| Namespace     | Что хранит                    | Когда заполняется         | Размер      | Обновления |
|---------------|-------------------------------|---------------------------|-------------|------------|
| **G1**        | Knowledge Base (Block A-F)    | Deploy (1 раз)            | ~65 файлов  | Редко (при обновлении KB) |
| **G1_Client** | Client documents              | Каждый проект (динамично) | Per-project | Часто (при загрузке docs) |

**Почему два namespace:**
1. **Разная природа данных:** KB = универсальные знания, Client = специфичные данные
2. **Разная частота обновлений:** KB обновляется раз в квартал, Client — каждый день
3. **Разные фильтры:** KB фильтруется по ISA/IFRS/Cycle, Client — по project_id
4. **Изоляция:** Удаление проекта = удаление G1_Client данных, KB остаётся

---

## G1: Knowledge Base Collection

### Collection configuration

\`\`\`python
{
    "collection_name": "oson_knowledge",
    "vectors": {
        "size": 1536,            # OpenAI text-embedding-3-small
        "distance": "Cosine"
    },
    "indexing": {
        "hnsw": {"m": 16, "ef_construct": 128}
    },
    "storage": {
        "on_disk": True,
        "quantization": {"scalar": {"type": "int8"}}
    }
}
\`\`\`

### Payload schema

\`\`\`python
{
    "block": "B|C|D|F",
    "file_id": "B1|C1|...",
    "chunk_index": int,
    "text": str,
    "isa_reference": ["ISA 315", ...],
    "ifrs_reference": ["IAS 37", ...],
    "cycle": "Revenue|Inventory|...",  # Block B only
    "formula_id": "OM|PM|CTT|...",     # Block C only
    "section": str
}
\`\`\`

### Chunking strategies

| Block | Strategy  | Размер | Overlap | Маркер    | Результат |
|-------|-----------|--------|---------|-----------|-----------|
| B     | Section   | 1024   | 0       | ====,---- | ~105 chunks |
| C     | Section   | 1024   | 0       | ====      | ~20 chunks |
| D     | Section   | 1024   | 0       | ─────     | ~8 chunks |
| F     | Paragraph | 512    | 50      | Нет       | ~20 chunks |

**Итого G1:** ~150-200 chunks.

---

## G1_Client: Client Documents Collection

### Collection configuration

\`\`\`python
{
    "collection_name": "client_documents",
    "vectors": {"size": 1536, "distance": "Cosine"},
    "indexing": {"hnsw": {"m": 16, "ef_construct": 128}},
    "storage": {"on_disk": True, "quantization": {"scalar": {"type": "int8"}}}
}
\`\`\`

### Payload schema

\`\`\`python
{
    "project_id": "PRJ-001",
    "file_type": "trial_balance|general_ledger|sales_register|ar_register",
    "original_file": "MinIO path",
    "chunk_index": int,
    "text": str,
    "uploaded_at": "ISO timestamp",
    "account_code": str,      # Для TB/GL
    "invoice_number": str,    # Для invoices
    "amount": float          # Опционально
}
\`\`\`

**Итого G1_Client:** ~12K-15K chunks per project.

---

## LightRAG Integration (Hybrid: Graph + Vector)

### Graph layer

\`\`\`python
# Entities (auto-extracted)
["ISA 315", "IAS 37", "Revenue", "Inventory", "Materiality", "Sampling"]

# Relations
[
    ("ISA 315", "identifies", "Risks"),
    ("ISA 330", "responds_to", "Risks"),
    ("Revenue", "requires", "ISA 240"),  # Fraud risk
    ("Materiality", "uses", "Benchmark")
]
\`\`\`

**Результат:** +20-30% accuracy (по бенчмаркам LightRAG).

---

## Reranking Pipeline

\`\`\`
User Query → Vector Search (top 30) → Reranker (top 5) → LLM
                 ↑                          ↑
            Embeddings              Cohere Rerank v4
\`\`\`

**Результат:** +20-35% accuracy для ISA/IFRS документов.

---

## Metadata Indexing

### Indexes

\`\`\`python
# G1
INDEXES = [
    ("block", "keyword"),
    ("isa_reference", "keyword[]"),
    ("cycle", "keyword")
]

# G1_Client
INDEXES = [
    ("project_id", "keyword"),  # Критичен!
    ("file_type", "keyword")
]
\`\`\`

### Filtered search example

\`\`\`python
results = qdrant_client.search(
    collection_name="oson_knowledge",
    query_vector=embedding,
    query_filter={
        "must": [
            {"key": "block", "match": {"value": "B"}},
            {"key": "cycle", "match": {"value": "Revenue"}}
        ]
    },
    limit=30
)
\`\`\`

---

## Cost Estimation

### Storage

- **G1:** 200 chunks × 8 KB = 1.6 MB
- **G1_Client:** 15K chunks × 8 KB = 120 MB per project
- **10 projects:** ~1.2 GB (с quantization: ~600 MB)

### Qdrant Cloud pricing

| Tier    | vCPU | RAM | Storage | Price/month | Для |
|---------|------|-----|---------|-------------|-----|
| Free    | 0.5  | 1GB | 4GB     | $0          | Dev |
| Starter | 2    | 4GB | 20GB    | $25         | MVP (50 projects) |
| Pro     | 4    | 8GB | 50GB    | $95         | Production (200 projects) |

**Рекомендация:** Starter для MVP.

---

## Связанные документы

- [G2: PostgreSQL Schema](G2_PostgreSQL_Schema.md)
- [G3: MinIO Structure](G3_MinIO_Structure.md)
- [Block B: Libraries](../blocks/Block_B_Libraries.md)
- [ETL Pipeline](../blocks/ETL_Pipeline.md)
