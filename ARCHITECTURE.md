# Auditor AI Backend - Production Architecture

## Обзор системы

Production-ready RAG система для аудиторского AI-ассистента с полным пайплайном обработки запросов.

## Архитектура пайплайна

```
┌─────────────────────────────────────────────────────────────────────┐
│                         USER QUERY                                   │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  1. POLICY GATE                                                      │
│  ├── Role-based access control (Admin/Employee/Customer)            │
│  ├── Customer assignment validation                                  │
│  ├── Scope filtering (ADMIN_LAW / CUSTOMER_DOC)                     │
│  ├── Rate limiting by user tier                                      │
│  └── Audit trail logging                                             │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  2. CONVERSATION MEMORY (3-layer)                                    │
│  ├── Layer 1: Rolling Summary (PostgreSQL context_cache)            │
│  ├── Layer 2: Last Turns (2-4 messages for coherence)               │
│  └── Layer 3: Chat Memory Retrieval (Qdrant semantic search)        │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  3. QUERY ROUTER / PLANNER                                           │
│  ├── Intent detection (Legal/KAM/TCWG/Materiality/Sampling/etc)     │
│  ├── Evidence budget allocation (admin_law vs customer_doc)         │
│  ├── Pattern extraction (dates, amounts, references)                 │
│  └── Governing standards identification (ISA/IFRS)                   │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  4. EVIDENCE RETRIEVAL (Hybrid)                                      │
│  ├── Dense Search: Qdrant vector search with Gemini embeddings      │
│  ├── Sparse Search: PostgreSQL FTS (BM25) with RU/EN support        │
│  ├── LightRAG Enrichment: Entity/relationship extraction            │
│  └── ACL Filters: tenant_id, customer_id, owner_id, scope           │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  5. MERGE / DEDUPE / RRF                                             │
│  ├── Reciprocal Rank Fusion for combining dense + sparse            │
│  ├── Deduplication by file_id + chunk_index                         │
│  └── Score normalization                                             │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  6. RERANKER (LLM-based)                                             │
│  ├── Top 30 candidates → Top 10-15 evidence                         │
│  ├── Relevance scoring with Gemini                                   │
│  └── Trust level consideration                                       │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  7. EVIDENCE BUILDER                                                 │
│  ├── Neighbor chunks (±1) for context                               │
│  ├── Citation formatting                                             │
│  ├── Trust level tagging (official/client_provided/unknown)         │
│  └── Metadata enrichment (doc_id, page, section)                    │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  8. PROMPT ASSEMBLY                                                  │
│  ├── System prompts from DB (StyleGuide, Routing, Model IO)         │
│  ├── Guardrails injection                                            │
│  ├── Rolling summary + Last turns + Chat memories                   │
│  ├── Evidence pack (10-15 chunks)                                    │
│  ├── User query                                                      │
│  └── Token budgeting (cut history first, then evidence)             │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  9. GEMINI GENERATION                                                │
│  ├── gemini-2.0-flash model                                          │
│  ├── Temperature control by intent                                   │
│  └── Structured output with citations                                │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  10. GROUNDING CHECK                                                 │
│  ├── Verify all claims have evidence support                        │
│  ├── Citation validation                                             │
│  └── Hallucination detection                                         │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  11. MEMORY UPDATE                                                   │
│  ├── Save messages to PostgreSQL                                     │
│  ├── Index message pairs to Qdrant (chat_memory collection)         │
│  └── Update rolling summary if conversation is long                  │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         RESPONSE                                     │
└─────────────────────────────────────────────────────────────────────┘
```

## Компоненты системы

### 1. Embedding Service (`app/modules/embeddings/service.py`)
- **Primary**: Gemini `text-embedding-004` (768 dims)
- **Fallback 1**: OpenAI `text-embedding-3-small` (1536 dims)
- **Fallback 2**: SentenceTransformers local (384 dims)
- Кэширование эмбеддингов
- Rate limiting

### 2. Chat Memory (`app/modules/chats/memory.py`)
- Отдельная коллекция `chat_memory` в Qdrant
- Индексация пар сообщений (user→assistant)
- Семантический поиск по истории диалогов
- ACL фильтрация

### 3. Policy Gate (`app/modules/rag/policy_gate.py`)
- RBAC: Admin/Employee/Customer/Guest
- Лимиты по ролям (max_k, max_context_tokens, rate_limit)
- Audit trail для compliance
- Customer assignment validation

### 4. Sparse Search (`app/modules/rag/sparse_search.py`)
- PostgreSQL Full-Text Search
- Поддержка русского и английского языков
- GIN индексы для производительности
- Hybrid Search с RRF (Reciprocal Rank Fusion)

### 5. Enhanced Pipeline (`app/modules/rag/enhanced_pipeline.py`)
- Полный 11-шаговый пайплайн
- Intent detection и routing
- Интеграция всех компонентов

### 6. Dynamic Prompts (`app/modules/prompts/`)
- Хранение промптов в PostgreSQL
- Версионирование
- CRUD для админа
- Usage analytics

## Коллекции Qdrant

1. **documents** (`QDRANT_COLLECTION_NAME`)
   - Чанки документов
   - Payload: file_id, chunk_index, scope, customer_id, owner_id

2. **chat_memory** (`QDRANT_CHAT_MEMORY_COLLECTION`)
   - Пары сообщений чата
   - Payload: chat_id, customer_id, user_id, content, timestamp

## Конфигурация

```env
# Qdrant
QDRANT_URL=http://localhost:6333
QDRANT_COLLECTION_NAME=documents
QDRANT_VECTOR_SIZE=768
QDRANT_CHAT_MEMORY_COLLECTION=chat_memory

# Gemini
GEMINI_API_KEY=your_key
GEMINI_MODEL=gemini-2.0-flash
GEMINI_EMBEDDING_MODEL=text-embedding-004

# RAG
RAG_MAX_CONTEXT_TOKENS=12000
RAG_DEFAULT_TOP_K=10
RAG_RERANK_ENABLED=true
```

## Миграции

Выполните SQL миграцию для FTS:
```bash
psql -d your_database -f app/modules/rag/migrations/001_add_fts_to_file_chunks.sql
```

## API Endpoints

### RAG Query
```
POST /rag/query
{
    "question": "Как рассчитать существенность?",
    "customer_id": "uuid",
    "include_admin_laws": true,
    "include_customer_docs": true,
    "mode": "hybrid",
    "top_k": 10
}
```

### Chat with RAG
```
POST /customers/{customer_id}/chats/{chat_id}/messages
{
    "content": "Вопрос пользователя"
}
```

## Промпты из файлов

Система использует промпты из `app/prompts/`:
- `A1_StyleGuide_v1.txt` - Стиль ответов
- `A2_ISA_RoutingPrompts_v1.txt` - Маршрутизация по ISA
- `A6_Model_IO_Guide_v1.txt` - Правила ввода/вывода

Промпты загружаются в БД через `PromptsService.initialize_default_prompts()`.

## Мониторинг

- Логирование всех этапов пайплайна
- Audit trail для Policy Gate
- Usage analytics для промптов
- Grounding score для качества ответов
