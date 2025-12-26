# Tech Stack

> [← Project Overview](./01_Project_Overview.md) | [Data Circuits →](./03_Data_Circuits.md)

---

## APPROVED STACK (НЕ МЕНЯТЬ БЕЗ СОГЛАСОВАНИЯ)

```
┌─────────────────────────────────────────────────────────────┐
│                      FRONTEND                               │
│         Next.js 14 + TypeScript + Tailwind CSS              │
├─────────────────────────────────────────────────────────────┤
│                       BACKEND                               │
│              FastAPI + Python 3.11 + Pydantic               │
├─────────────────────────────────────────────────────────────┤
│                      DATABASES                              │
│            PostgreSQL 15  │  Qdrant (vectors)               │
├─────────────────────────────────────────────────────────────┤
│                         AI                                  │
│            LightRAG + Claude API (primary LLM)              │
├─────────────────────────────────────────────────────────────┤
│                   INFRASTRUCTURE                            │
│      Kubernetes  │  MinIO (S3)  │  Redis + Celery           │
└─────────────────────────────────────────────────────────────┘
```

---

## Stack Details

### Frontend
| Tech | Version | Purpose |
|------|---------|---------|
| Next.js | 14 | React framework, SSR |
| TypeScript | 5.x | Type safety |
| Tailwind CSS | 3.x | Styling |

### Backend
| Tech | Version | Purpose |
|------|---------|---------|
| FastAPI | 0.100+ | REST API |
| Python | 3.11 | Runtime |
| Pydantic | 2.x | Validation |
| SQLAlchemy | 2.0 | ORM (async) |
| Alembic | — | Migrations |

### Databases
| Tech | Purpose |
|------|---------|
| PostgreSQL 15 | Main DB — G2.1-G2.8 tables (users, projects, audit data) |
| Qdrant (G1 System) | Vector search — ISA/IFRS knowledge base (oson_knowledge) |
| Qdrant (G1.X Client) | Vector search — Client data per project (oson_client_{id}) |
| Redis | Cache, sessions |
| MinIO | S3-compatible file storage (E_Templates) |

> **Dual Qdrant Architecture:** Системные знания (ISA, IFRS, справочники) хранятся в G1 коллекции. Данные клиентов изолированы в отдельных G1.X коллекциях по project_id.

### AI/ML
| Tech | Purpose |
|------|---------|
| LightRAG | Graph + Vector RAG (строит граф-связи поверх Qdrant) |
| Claude API | Primary LLM (обрабатывает запросы напрямую) |
| OpenAI API | Fallback LLM |

> **LightRAG Architecture:** LightRAG — это гибридный фреймворк, который строит graph reasoning поверх векторного хранилища (Qdrant). Отдельная графовая БД (Neo4j) НЕ нужна — LightRAG программно создаёт связи между чанками и предоставляет graph-based retrieval.

---

## Rejected Alternatives

| Alternative | Reason for Rejection |
|-------------|---------------------|
| **n8n** | Enterprise security concerns, vendor lock-in, air-gapped не поддерживает |
| **LangChain** | Слишком абстрактный, LightRAG проще |
| **Pinecone** | Cloud-only, не подходит для On-Premise |
| **Neo4j** | Избыточен для текущих задач |

---

## Environment Variables

See: [../api/02_Auth.md](../api/02_Auth.md) для полного списка env vars.

---

## Related Docs

- [Data Circuits](./03_Data_Circuits.md) — Как данные движутся
- [Database Schema](../database/01_Schema.md) — Структура PostgreSQL
