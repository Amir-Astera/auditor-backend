# 🛠️ Implementation Guide

## 1. RAG для Block F (простая векторизация)

```python
# src/rag/block_f_indexer.py

BLOCK_F_FILES = [
    "F1_Company_Profile_TRI-S-Audit_v1.txt",
    "F2_Industry_Knowledge_Pack_v1.txt"
]

RAG_CONFIG = {
    "chunk_strategy": "paragraph",  # F1 без маркеров секций
    "chunk_size": 512,
    "chunk_overlap": 50,
    "retrieval_top_k": 10,
    "rerank_top_k": 3
}

def index_block_f():
    """Векторизация Block F в Qdrant"""
    for filename in BLOCK_F_FILES:
        content = Path(f"knowledge/{filename}").read_text(encoding='utf-8')

        # Chunking по параграфам
        chunks = chunk_by_paragraph(content, config=RAG_CONFIG)

        for chunk in chunks:
            qdrant_client.upsert(
                collection_name="oson_knowledge",
                points=[{
                    "id": generate_id(filename, chunk.index),
                    "vector": embed(chunk.text),
                    "payload": {
                        "block": "F",
                        "file_id": extract_file_id(filename),  # F1, F2
                        "section": chunk.section,  # Legal, Services, Industries
                        "industry_code": extract_industry(chunk.text),  # RETAIL, INSURANCE
                        "lang": detect_language(chunk.text),  # EN, RU
                        "text": chunk.text
                    }
                }]
            )
```

## 2. Chunking стратегия

```python
# src/rag/chunking.py

def chunk_by_paragraph(content: str, config: dict) -> list:
    """
    Разбивает документ по параграфам (2-4 строки).

    F1 Company Profile: ~15-20 chunks
    F2 Industry Pack: 1 chunk per industry (расширяемо)
    """
    paragraphs = content.split("\n\n")

    chunks = []
    for idx, para in enumerate(paragraphs):
        if len(para.strip()) > 50:  # минимальная длина
            chunks.append({
                "index": idx,
                "text": para.strip(),
                "section": extract_section_from_paragraph(para)
            })

    return chunks
```

## 3. Industry-specific риски (F2)

```python
# Пример query для industry guidance

query = "Типичные риски для retail компании"

results = qdrant_client.search(
    collection_name="oson_knowledge",
    query_vector=embed(query),
    query_filter={
        "must": [
            {"key": "block", "match": {"value": "F"}},
            {"key": "file_id", "match": {"value": "F2"}},
            {"key": "industry_code", "match": {"value": "RETAIL"}}
        ]
    },
    limit=10
)

# Response:
"""
Для retail типичные риски:
- Revenue cut-off
- Inventory shrinkage
- POS reconciliation issues

Типичные контроли:
- Daily POS reconciliations
- Cycle counts
- CCTV monitoring
"""
```

## 4. Company FAQ (F1)

```python
# Proactive responses для FAQ

FAQ_QUERIES = [
    "Какие услуги предлагает TRI-S-AUDIT?",
    "Как связаться с компанией?",
    "В каких отраслях работает компания?"
]

def handle_company_faq(user_query: str) -> str:
    """Автоматический ответ на вопросы о компании"""
    context = retrieve_from_qdrant(
        query=user_query,
        filters={"block": "F", "file_id": "F1"}
    )

    return llm.generate(
        prompt=f"Ответь на вопрос о TRI-S-AUDIT: {user_query}",
        context=context
    )
```

## 5. Расширение F2 (новые отрасли)

```python
# Добавление новой отрасли в F2_Industry_Pack

def add_industry(industry_code: str, data: dict):
    """
    Добавляет новую отрасль в F2 и ре-индексирует.

    Args:
        industry_code: "ENERGY" | "MINING" | "CONSTRUCTION"
        data: {
            name: str,
            key_revenue_models: list,
            key_risks: list,
            typical_controls: list
        }
    """
    # 1. Append to F2 file
    with open("knowledge/F2_Industry_Knowledge_Pack_v1.txt", "a") as f:
        f.write(f"\n\n========================================\n")
        f.write(f"INDUSTRY: {industry_code}\n")
        f.write(f"Name: {data['name']}\n")
        # ... append all fields

    # 2. Re-index
    index_block_f()
```

## 6. TODO для разработчика

- [ ] Векторизовать F1, F2 в Qdrant (paragraph-based chunking)
- [ ] Имплементировать `chunk_by_paragraph()` с overlap=50
- [ ] Создать FAQ handler для Company Profile questions
- [ ] Протестировать industry-specific queries для F2
- [ ] Добавить metadata: `section`, `industry_code`, `lang`
- [ ] Опционально: расширить F2 новыми отраслями (Energy, Mining, Construction)

**Приоритет:** P3 (не критичный, можно в последнюю очередь)

## 7. Связанные документы

- G1 Qdrant Design — paragraph chunking strategy
- Block B Libraries — связь F2 industries → B1 risks
- Development Rules — FAQ automation
