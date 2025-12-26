# OSON Document Intelligence — Complete Project Context

> **Для Claude Code:** Это главный контекстный файл проекта. Изучи его полностью перед началом работы.

---

## 1. PROJECT OVERVIEW

| Field                   | Value                                                                             |
| ----------------------- | --------------------------------------------------------------------------------- |
| **Product**       | OSON Document Intelligence (ранее TRI-S-AUDIT MVP)                           |
| **Company**       | OSON SOFT                                                                         |
| **Type**          | On-Premise RAG System for Audit Automation                                        |
| **Target Market** | Big 4 audit firms, крупные промышленные предприятия |
| **Key Value**     | Автоматизация аудиторских процедур по ISA/IFRS  |
| **Deployment**    | On-Premise, Air-gapped ready                                                      |

### Business Goals

1. Пилот с TRI-S-AUDIT (Q1 2025)
2. 5-10 локальных клиентов (Q2 2025)
3. Экспансия: Казахстан, Кыргызстан (Q3-Q4 2025)
4. Big4 региональные офисы (2026)

---

## 2. TECH STACK (APPROVED — НЕ МЕНЯТЬ)

```
┌─────────────────────────────────────────────────────────────┐
│                      FRONTEND                               │
│         Next.js 14 + TypeScript + Tailwind CSS              │
├─────────────────────────────────────────────────────────────┤
│                       BACKEND                               │
│              FastAPI + Python 3.11 + Pydantic               │
├─────────────────────────────────────────────────────────────┤
│                      DATABASES                              │
│  PostgreSQL 15  │  Qdrant (vectors)  │  Neo4j (graph)       │
├─────────────────────────────────────────────────────────────┤
│                         AI                                  │
│     LightRAG (Graph+Vector hybrid) + Claude API (primary)   │
├─────────────────────────────────────────────────────────────┤
│                   INFRASTRUCTURE                            │
│      Kubernetes  │  MinIO (S3)  │  Redis + Celery           │
└─────────────────────────────────────────────────────────────┘
```

### Почему этот стек

* **Не n8n** — Enterprise security, vendor lock-in, air-gapped deployment
* **LightRAG** — Graph + Vector hybrid даёт лучшее качество retrieval
* **On-Premise** — Data sovereignty для Big4 клиентов

---

## 3. ARCHITECTURE: 3 DATA CIRCUITS

```
┌─────────────────────────────────────────────────────────────┐
│                    OSON SYSTEM                              │
├───────────────┬─────────────────┬───────────────────────────┤
│   CIRCUIT 1   │    CIRCUIT 2    │        CIRCUIT 3          │
│    STATIC     │      API        │        CRAWLERS           │
│  (при деплое) │   (real-time)   │    (дни-месяцы)           │
├───────────────┼─────────────────┼───────────────────────────┤
│ Qdrant+Neo4j  │  REST APIs      │  Web Scrapers             │
├───────────────┼─────────────────┼───────────────────────────┤
│ • ISA/IFRS    │ • ЦБ РУз курсы  │ • lex.uz (законы)         │
│ • Risk Library│ • БРВ Минфин   │ • norma.uz                │
│ • PBC Lists   │ • ERP (1С)     │ • soliq.uz                │
│ • Glossaries  │ • Bank APIs    │ • Big4 whitepapers        │
│ • Templates   │ • OFAC lists   │                           │
└───────────────┴─────────────────┴───────────────────────────┘
```

---

## 4. SYSTEM COMPONENTS

### 4.1 Engine Components (F1-F6)

| ID           | Component          | Function                                                 | Technology           |
| ------------ | ------------------ | -------------------------------------------------------- | -------------------- |
| **F1** | Intent Detector    | Классификация запроса → J1-J20      | Python + keywords/ML |
| **F2** | RAG Engine         | Поиск в Qdrant + Neo4j                             | LightRAG             |
| **F3** | Prompt Builder     | Сборка system prompt + context                     | Jinja2 templates     |
| **F4** | Function Executor  | Выполнение Python функций I1-I10        | Python               |
| **F5** | Response Formatter | Форматирование: H1-H5 компоненты | Python               |
| **F6** | File Processor     | Парсинг PDF/XLSX/DOCX                             | PyMuPDF, openpyxl    |

### 4.2 Intents (J1-J20)

**MVP v1.0 (J1-J10):**

| ID  | Intent      | ISA/IFRS        | Description                                                  |
| --- | ----------- | --------------- | ------------------------------------------------------------ |
| J1  | MATERIALITY | ISA 320         | Расчёт OM/PM/CT                                        |
| J2  | RISK        | ISA 315/330     | Оценка рисков по циклам                  |
| J3  | LEGAL       | ISA 501, IAS 37 | Оценка судебных исков                     |
| J4  | SAMPLING    | ISA 530         | Расчёт размера выборки                   |
| J5  | PBC         | ISA 500         | Управление запросами документов |
| J6  | TCWG        | ISA 260/265     | Коммуникации с руководством         |
| J7  | KAM         | ISA 701         | Ключевые вопросы аудита                 |
| J8  | KNOWLEDGE   | —              | Поиск по базе знаний                        |
| J9  | DOCUMENT    | —              | Генерация документов                      |
| J10 | PROJECT     | —              | Управление проектом                        |

**Roadmap v1.5-2.5 (J11-J20):**

| ID  | Intent            | Version |
| --- | ----------------- | ------- |
| J11 | ACCEPTANCE        | v2.5    |
| J12 | UNDERSTANDING     | v2.5    |
| J13 | ESTIMATES         | v2.0    |
| J14 | GOING_CONCERN     | v1.5    |
| J15 | RELATED_PARTIES   | v2.5    |
| J16 | SUBSEQUENT_EVENTS | v2.5    |
| J17 | TESTING           | v1.5    |
| J18 | MISSTATEMENTS     | v1.5    |
| J19 | OPINION           | v2.0    |
| J20 | REPORT            | v2.0    |

### 4.3 Python Functions (I1-I10)

| ID  | Function                    | Input                   | Output                     |
| --- | --------------------------- | ----------------------- | -------------------------- |
| I1  | `calculate_materiality()` | benchmark, value, risk  | {om, pm, ct, rationale}    |
| I2  | `calculate_sample_size()` | population, pm, errors  | {size, method}             |
| I3  | `assess_legal_matter()`   | amount, probability, pm | {is_kam, provision}        |
| I4  | `save_materiality()`      | project_id, data        | DB record                  |
| I5  | `add_risk()`              | project_id, risk_data   | DB record                  |
| I6  | `add_legal_matter()`      | project_id, legal_data  | DB record                  |
| I7  | `generate_document()`     | template, data          | DOCX/PDF                   |
| I8  | `search_knowledge()`      | query                   | {chunks, sources}          |
| I9  | `get_project_context()`   | project_id              | {project, risks, warnings} |
| I10 | `get_pbc_status()`        | project_id              | {items, stats}             |

### 4.4 Response Components (H1-H5)

| ID | Component      | Example                                                              |
| -- | -------------- | -------------------------------------------------------------------- |
| H1 | Text Response  | "Рассчитал существенность: OM = 15 млн..." |
| H2 | Action Buttons | `[💾 Сохранить]` `[❌ Отмена]`                    |
| H3 | Data Table     | Таблица с расчётами                                 |
| H4 | File Download  | Ссылка на сгенерированный документ    |
| H5 | Redirect       | "Перейти к оценке рисков?"                       |

---

## 5. MAIN FLOW (7 STEPS)

```
┌─────────────────────────────────────────────────────────────┐
│  USER: "Рассчитай существенность, выручка 500 млн"          │
└─────────────────────────┬───────────────────────────────────┘
                          ▼
┌─────────────────────────────────────────────────────────────┐
│  1. UNDERSTAND │ Intent Detector (F1) → "J1_MATERIALITY"    │
└─────────────────────────┬───────────────────────────────────┘
                          ▼
┌─────────────────────────────────────────────────────────────┐
│  2. GET CONTEXT │ RAG (F2) → ISA 320 chunks                 │
│                 │ PostgreSQL → project data, existing calcs │
└─────────────────────────┬───────────────────────────────────┘
                          ▼
┌─────────────────────────────────────────────────────────────┐
│  3. CALCULATE │ I1: calculate_materiality(                  │
│               │     benchmark="revenue",                    │
│               │     value=500_000_000,                      │
│               │     risk="normal"                           │
│               │ ) → {om: 15M, pm: 9.75M, ct: 750K}          │
└─────────────────────────┬───────────────────────────────────┘
                          ▼
┌─────────────────────────────────────────────────────────────┐
│  4. PRESENT │ LLM formats response with H1+H2+H3            │
└─────────────────────────┬───────────────────────────────────┘
                          ▼
┌─────────────────────────────────────────────────────────────┐
│  5. CONFIRM │ User clicks [💾 Сохранить]                    │
│             │ ⚠️ LLM НИКОГДА не сохраняет без подтверждения │
└─────────────────────────┬───────────────────────────────────┘
                          ▼
┌─────────────────────────────────────────────────────────────┐
│  6. SAVE │ I4: save_materiality() → DB with confirmed_by    │
└─────────────────────────┬───────────────────────────────────┘
                          ▼
┌─────────────────────────────────────────────────────────────┐
│  7. REDIRECT │ H5: "✅ Сохранено. Перейти к рискам?"        │
└─────────────────────────────────────────────────────────────┘
```

---

## 6. DATABASE SCHEMA (PostgreSQL)

### G2.1: users

```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL CHECK (role IN ('admin', 'partner', 'manager', 'auditor')),
    password_hash VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### G2.2: projects

```sql
CREATE TABLE projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_name VARCHAR(255) NOT NULL,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    status VARCHAR(50) DEFAULT 'planning' 
        CHECK (status IN ('planning', 'fieldwork', 'review', 'completed', 'archived')),
    industry VARCHAR(100),
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### G2.3: materiality

```sql
CREATE TABLE materiality (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    benchmark VARCHAR(50) NOT NULL,  -- revenue, assets, equity, profit
    benchmark_value DECIMAL(20,2) NOT NULL,
    om DECIMAL(20,2) NOT NULL,       -- Overall Materiality
    pm DECIMAL(20,2) NOT NULL,       -- Performance Materiality (50-75% of OM)
    ct DECIMAL(20,2) NOT NULL,       -- Clearly Trivial (3-5% of OM)
    risk_level VARCHAR(20) DEFAULT 'normal' CHECK (risk_level IN ('low', 'normal', 'high')),
    rationale TEXT,
    -- Confirmation fields (CRITICAL!)
    confirmed_by UUID REFERENCES users(id),
    confirmed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### G2.4: risk_register

```sql
CREATE TABLE risk_register (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    cycle VARCHAR(100) NOT NULL,     -- Revenue, Inventory, Payroll, etc.
    assertion VARCHAR(50),           -- EAV, CO, RO, PD, VA
    risk_description TEXT NOT NULL,
    inherent_risk VARCHAR(20) NOT NULL CHECK (inherent_risk IN ('low', 'medium', 'high')),
    control_risk VARCHAR(20) NOT NULL CHECK (control_risk IN ('low', 'medium', 'high')),
    detection_risk VARCHAR(20),
    response TEXT,                   -- Audit response/procedures
    is_significant BOOLEAN DEFAULT false,
    is_fraud_risk BOOLEAN DEFAULT false,
    confirmed_by UUID REFERENCES users(id),
    confirmed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### G2.5: legal_matrix

```sql
CREATE TABLE legal_matrix (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    matter_name VARCHAR(255) NOT NULL,
    claim_amount DECIMAL(20,2),
    probability VARCHAR(20) NOT NULL CHECK (probability IN ('remote', 'possible', 'probable')),
    outcome_estimable BOOLEAN DEFAULT true,
    is_material BOOLEAN DEFAULT false,
    disclosure_required BOOLEAN DEFAULT false,
    provision_required BOOLEAN DEFAULT false,
    is_kam BOOLEAN DEFAULT false,
    rationale TEXT,
    confirmed_by UUID REFERENCES users(id),
    confirmed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### G2.6: pbc_items

```sql
CREATE TABLE pbc_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    item_code VARCHAR(50) NOT NULL,  -- e.g., PBC-REV01
    item_name VARCHAR(255) NOT NULL,
    cycle VARCHAR(100),
    priority VARCHAR(20) DEFAULT 'medium' CHECK (priority IN ('low', 'medium', 'high', 'critical')),
    status VARCHAR(50) DEFAULT 'pending' 
        CHECK (status IN ('pending', 'requested', 'received', 'reviewed', 'issue')),
    due_date DATE,
    received_date DATE,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### G2.7: chat_history

```sql
CREATE TABLE chat_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id),
    user_message TEXT NOT NULL,
    ai_response TEXT NOT NULL,
    intent VARCHAR(50),              -- J1, J2, etc.
    tool_calls JSONB,                -- Function calls made
    tokens_used INTEGER,
    response_time_ms INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### G2.8: project_docs

```sql
CREATE TABLE project_docs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    file_name VARCHAR(255) NOT NULL,
    file_type VARCHAR(50) NOT NULL,  -- pdf, xlsx, docx
    file_path VARCHAR(500) NOT NULL, -- MinIO path
    file_size INTEGER,
    is_vectorized BOOLEAN DEFAULT false,
    vectorized_at TIMESTAMP,
    chunk_count INTEGER,
    uploaded_by UUID REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## 7. API ENDPOINTS

### Authentication

```
POST   /api/v1/auth/login           # Returns JWT
POST   /api/v1/auth/refresh         # Refresh token
POST   /api/v1/auth/logout          # Invalidate token
GET    /api/v1/auth/me              # Current user info
```

### Projects

```
GET    /api/v1/projects             # List (with filters)
POST   /api/v1/projects             # Create
GET    /api/v1/projects/{id}        # Get with related data
PUT    /api/v1/projects/{id}        # Update
DELETE /api/v1/projects/{id}        # Soft delete
```

### Chat (Main AI Endpoint)

```
POST   /api/v1/chat                 # Send message → AI response
       Body: {project_id, message, attachments?}
       Response: {response, intent, buttons?, table?, file?}

GET    /api/v1/chat/{project_id}    # Get history
DELETE /api/v1/chat/{project_id}    # Clear history
```

### Actions (H2 Button Handlers)

```
POST   /api/v1/actions/save-materiality
POST   /api/v1/actions/add-risk
POST   /api/v1/actions/add-legal-matter
POST   /api/v1/actions/update-pbc
POST   /api/v1/actions/generate-document
```

### Files

```
POST   /api/v1/files/upload         # Upload + auto-vectorize
GET    /api/v1/files/{id}           # Download
GET    /api/v1/files/{id}/status    # Vectorization status
DELETE /api/v1/files/{id}           # Delete
```

### Knowledge (RAG)

```
POST   /api/v1/knowledge/search     # Search knowledge base
GET    /api/v1/knowledge/stats      # Index statistics
```

---

## 8. PROJECT STRUCTURE

```
/oson-core/
│
├── CLAUDE.md                    # ← ЭТО ФАЙЛ
├── docker-compose.yml
├── .env.example
│
├── /api/                        # FastAPI Backend
│   ├── main.py                  # Entry point
│   ├── config.py                # Settings (Pydantic)
│   ├── /routes/
│   │   ├── auth.py
│   │   ├── projects.py
│   │   ├── chat.py              # Main AI endpoint
│   │   ├── actions.py           # H2 button handlers
│   │   └── files.py
│   ├── /middleware/
│   │   ├── auth.py              # JWT validation
│   │   └── logging.py
│   └── /schemas/                # Pydantic models
│
├── /engine/                     # AI Processing
│   ├── intent_detector.py       # F1
│   ├── rag_engine.py            # F2 (LightRAG)
│   ├── prompt_builder.py        # F3
│   ├── function_executor.py     # F4
│   ├── response_formatter.py    # F5
│   └── file_processor.py        # F6
│
├── /handlers/                   # Intent Handlers
│   ├── router.py                # Routes to J1-J20
│   ├── materiality.py           # J1
│   ├── risk.py                  # J2
│   ├── legal.py                 # J3
│   ├── sampling.py              # J4
│   ├── pbc.py                   # J5
│   ├── tcwg.py                  # J6
│   ├── kam.py                   # J7
│   ├── knowledge.py             # J8
│   ├── document_gen.py          # J9
│   └── project_mgmt.py          # J10
│
├── /functions/                  # Business Logic (I1-I10)
│   ├── materiality.py           # I1: calculate_materiality
│   ├── sampling.py              # I2: calculate_sample_size
│   ├── legal.py                 # I3: assess_legal_matter
│   ├── context.py               # I9: get_project_context
│   └── validators.py            # Input validation
│
├── /db/
│   ├── models.py                # SQLAlchemy ORM
│   ├── queries.py               # Common queries
│   ├── session.py               # DB connection
│   └── /migrations/             # Alembic
│
├── /plugins/                    # Domain Plugins
│   ├── loader.py                # Plugin discovery
│   └── /audit/                  # Audit Plugin
│       ├── plugin.yaml          # Plugin manifest
│       ├── /prompts/            # A1-A5
│       ├── /knowledge/          # B1-B8, C1-C5, etc.
│       ├── /functions/          # Plugin-specific funcs
│       ├── /templates/          # E1-E6
│       └── /intents/            # J1-J20 configs
│
├── /web/                        # Next.js Frontend
│   ├── /app/
│   ├── /components/
│   └── /lib/
│
├── /admin/                      # Admin Panel
│
└── /tests/
    ├── /unit/
    ├── /integration/
    └── /e2e/
```

---

## 9. KEY FUNCTIONS IMPLEMENTATION

### I1: calculate_materiality

```python
def calculate_materiality(
    benchmark: Literal["revenue", "assets", "equity", "profit"],
    benchmark_value: float,
    risk_level: Literal["low", "normal", "high"] = "normal"
) -> dict:
    """
    ISA 320 materiality calculation.
  
    Benchmark rates:
    - Revenue: 0.5% - 2%
    - Total Assets: 0.5% - 1%
    - Equity: 2% - 5%
    - Profit before tax: 5% - 10%
  
    PM = 50-75% of OM (based on risk)
    CT = 3-5% of OM
    """
    RATES = {
        "revenue": (0.005, 0.02),
        "assets": (0.005, 0.01),
        "equity": (0.02, 0.05),
        "profit": (0.05, 0.10)
    }
  
    PM_RATES = {"low": 0.75, "normal": 0.65, "high": 0.50}
    CT_RATE = 0.05
  
    min_rate, max_rate = RATES[benchmark]
    mid_rate = (min_rate + max_rate) / 2
  
    om = benchmark_value * mid_rate
    pm = om * PM_RATES[risk_level]
    ct = om * CT_RATE
  
    return {
        "benchmark": benchmark,
        "benchmark_value": benchmark_value,
        "om": round(om, 2),
        "pm": round(pm, 2),
        "ct": round(ct, 2),
        "risk_level": risk_level,
        "rationale": f"OM = {benchmark_value:,.0f} × {mid_rate:.1%} = {om:,.0f}"
    }
```

### I3: assess_legal_matter

```python
def assess_legal_matter(
    claim_amount: float,
    probability: Literal["remote", "possible", "probable"],
    pm: float,
    outcome_estimable: bool = True
) -> dict:
    """
    ISA 501 + IAS 37 legal matter assessment.
  
    Decision matrix:
    - Remote: No disclosure, no provision
    - Possible + Material: Disclosure required
    - Probable + Estimable: Provision required
    - Probable + Not estimable: Disclosure only
    """
    is_material = claim_amount >= pm
  
    result = {
        "claim_amount": claim_amount,
        "probability": probability,
        "is_material": is_material,
        "disclosure_required": False,
        "provision_required": False,
        "is_kam": False,
        "rationale": ""
    }
  
    if probability == "remote":
        result["rationale"] = "Remote probability — no action required"
  
    elif probability == "possible":
        if is_material:
            result["disclosure_required"] = True
            result["rationale"] = "Possible + Material — disclose as contingent liability"
  
    elif probability == "probable":
        if outcome_estimable:
            result["provision_required"] = True
            result["rationale"] = "Probable + Estimable — recognize provision"
        else:
            result["disclosure_required"] = True
            result["rationale"] = "Probable + Not estimable — disclose range"
      
        if is_material:
            result["is_kam"] = True
            result["rationale"] += " | KAM candidate"
  
    return result
```

---

## 10. INTENT DETECTION

```python
INTENT_KEYWORDS = {
    "J1_MATERIALITY": {
        "en": ["materiality", "PM", "CT", "threshold", "performance materiality"],
        "ru": ["существенность", "порог", "материальность"]
    },
    "J2_RISK": {
        "en": ["risk", "assertion", "inherent", "control", "detection", "significant"],
        "ru": ["риск", "утверждение", "присущий", "контрольный"]
    },
    "J3_LEGAL": {
        "en": ["lawsuit", "legal", "litigation", "provision", "contingent", "claim"],
        "ru": ["иск", "судебный", "резерв", "условный"]
    },
    "J4_SAMPLING": {
        "en": ["sample", "sampling", "population", "ISA 530", "selection"],
        "ru": ["выборка", "население", "отбор"]
    },
    "J5_PBC": {
        "en": ["PBC", "document", "request", "deliverable"],
        "ru": ["документ", "запрос", "ПБК"]
    },
    "J6_TCWG": {
        "en": ["TCWG", "audit committee", "board", "governance"],
        "ru": ["комитет", "руководство", "совет"]
    },
    "J7_KAM": {
        "en": ["KAM", "key audit matter", "significant matter"],
        "ru": ["ключевой вопрос", "КВА"]
    },
    "J8_KNOWLEDGE": {
        "en": ["what is", "explain", "how to", "definition"],
        "ru": ["что такое", "объясни", "как", "определение"]
    },
    "J9_DOCUMENT": {
        "en": ["generate", "create", "draft", "template"],
        "ru": ["создай", "сгенерируй", "составь", "шаблон"]
    },
    "J10_PROJECT": {
        "en": ["project", "status", "progress", "overview"],
        "ru": ["проект", "статус", "прогресс"]
    }
}
```

---

## 11. ENVIRONMENT VARIABLES

```env
# ═══════════════════════════════════════════════════════════
# DATABASE
# ═══════════════════════════════════════════════════════════
DATABASE_URL=postgresql://oson:password@localhost:5432/oson_db
DATABASE_POOL_SIZE=20

# ═══════════════════════════════════════════════════════════
# VECTOR DATABASE (Qdrant)
# ═══════════════════════════════════════════════════════════
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=
QDRANT_COLLECTION=oson_knowledge

# ═══════════════════════════════════════════════════════════
# GRAPH DATABASE (Neo4j)
# ═══════════════════════════════════════════════════════════
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password

# ═══════════════════════════════════════════════════════════
# LLM PROVIDERS
# ═══════════════════════════════════════════════════════════
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...              # Fallback
DEFAULT_MODEL=claude-3-5-sonnet-20241022
MAX_TOKENS=4096
TEMPERATURE=0.3

# ═══════════════════════════════════════════════════════════
# FILE STORAGE (MinIO)
# ═══════════════════════════════════════════════════════════
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET=oson-files
MINIO_SECURE=false

# ═══════════════════════════════════════════════════════════
# CACHE (Redis)
# ═══════════════════════════════════════════════════════════
REDIS_URL=redis://localhost:6379/0

# ═══════════════════════════════════════════════════════════
# SECURITY
# ═══════════════════════════════════════════════════════════
JWT_SECRET=your-256-bit-secret-key-here
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# ═══════════════════════════════════════════════════════════
# APPLICATION
# ═══════════════════════════════════════════════════════════
APP_ENV=development
APP_DEBUG=true
LOG_LEVEL=INFO
CORS_ORIGINS=http://localhost:3000
```

---

## 12. DOCKER COMPOSE

```yaml
version: '3.8'

services:
  api:
    build: ./api
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://oson:password@postgres:5432/oson_db
    depends_on:
      - postgres
      - qdrant
      - redis
    volumes:
      - ./api:/app

  web:
    build: ./web
    ports:
      - "3000:3000"
    depends_on:
      - api

  postgres:
    image: postgres:15
    environment:
      POSTGRES_USER: oson
      POSTGRES_PASSWORD: password
      POSTGRES_DB: oson_db
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - "6333:6333"
    volumes:
      - qdrant_data:/qdrant/storage

  neo4j:
    image: neo4j:5
    environment:
      NEO4J_AUTH: neo4j/password
    ports:
      - "7474:7474"
      - "7687:7687"
    volumes:
      - neo4j_data:/data

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  minio:
    image: minio/minio
    command: server /data --console-address ":9001"
    ports:
      - "9000:9000"
      - "9001:9001"
    volumes:
      - minio_data:/data

volumes:
  postgres_data:
  qdrant_data:
  neo4j_data:
  minio_data:
```

---

## 13. DEVELOPMENT PHASES

| Phase                       | Duration  | Deliverables                                        |
| --------------------------- | --------- | --------------------------------------------------- |
| **1. Infrastructure** | 1-2 weeks | PostgreSQL tables, Qdrant collections, Docker setup |
| **2. Engine**         | 2-3 weeks | F1-F6 components working                            |
| **3. Audit Plugin**   | 2-3 weeks | J1-J10 intents, I1-I10 functions                    |
| **4. Integration**    | 1-2 weeks | Main flow, H2 buttons, confirmations                |
| **5. Admin Panel**    | 1 week    | Plugin management, user management                  |
| **6. Testing**        | 1 week    | Unit, integration, E2E tests                        |

---

## 14. RULES FOR CLAUDE CODE

### ✅ DO

1. **Use approved stack** — no substitutions without explicit approval
2. **Implement H2 buttons** — user must confirm before any DB write
3. **Use Python for calculations** — LLM formats, not calculates
4. **Follow ISA/IFRS** — reference standards in audit logic
5. **Write tests** — minimum 80% coverage for functions
6. **Use type hints** — Pydantic for validation
7. **Log everything** — structured logging for debugging

### ❌ DON'T

1. **Never suggest n8n** — decision is final
2. **Never let LLM save without confirmation** — always H2 buttons
3. **Never hardcode thresholds** — use config/DB
4. **Never expose API keys** — use environment variables
5. **Never skip validation** — especially for file uploads
6. **Never use synchronous DB calls** — use async with SQLAlchemy 2.0

### Quick Answers

* "Какой стек?" → Next.js + FastAPI + Qdrant + LightRAG + K8s
* "Почему не n8n?" → Enterprise security, vendor lock-in, air-gapped
* "Что такое G1?" → Global Knowledge Base в Qdrant + Neo4j
* "Сколько интентов?" → 20 (J1-J20), MVP = J1-J10
* "Как сохранить?" → Только через H2 кнопки с confirmed_by

---

## 15. KNOWLEDGE BASE STRUCTURE

```
/knowledge/
├── A_Routing/                   # System prompts (в промпт, не в вектор)
│   ├── A1_StyleGuide_v1.txt
│   ├── A2_ISA_RoutingPrompts_v1.txt
│   └── A3-A5...                 # TO CREATE
│
├── B_Libraries/                 # Vectorize → Qdrant
│   ├── B1_Risk_Library_by_Cycle_v1.txt
│   ├── B2_PBC_Master_List_v1.txt
│   ├── B3_Glossary_EN-RU-UZ_v1.txt
│   └── B4-B8...                 # TO CREATE
│
├── C_Formulas/                  # Vectorize → Qdrant
│   ├── C1_Materiality_Playbook_v1.txt
│   ├── C2_Sampling_Methods_ISA530_v1.txt
│   └── C3-C5...
│
├── D_DecisionTrees/             # Vectorize + Graph → Neo4j
│   ├── D1_Legal_Matrix_ISA560_501_v1.txt
│   └── D2-D4...                 # TO CREATE
│
├── E_Templates/                 # For document generation
│   ├── E1_TCWG_Communication_Pack_v1.txt
│   ├── E2_KAM_Skeletons_ISA701_v1.txt
│   ├── E3_Engagement_Letter_ISA210_Template_v1.txt
│   ├── E4_Management_Representation_Letter_ISA580_Template_v1.txt
│   ├── E5_Audit_Report_Templates_ISA700_705_706_v1.txt
│   └── E6_Management_Letter_ISA265_Template_v1.txt
│
└── F_Knowledge/
    └── F2_Industry_Knowledge_Pack_v1.txt  # TO CREATE
```

---

## 16. COMMANDS

```bash
# ═══════════════════════════════════════════════════════════
# DEVELOPMENT
# ═══════════════════════════════════════════════════════════
# Start all services
docker-compose up -d

# Run API in dev mode
cd api && uvicorn main:app --reload --port 8000

# Run frontend
cd web && npm run dev

# ═══════════════════════════════════════════════════════════
# DATABASE
# ═══════════════════════════════════════════════════════════
# Create migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1

# ═══════════════════════════════════════════════════════════
# TESTING
# ═══════════════════════════════════════════════════════════
# Run all tests
pytest tests/ -v

# Run with coverage
pytest --cov=api --cov-report=html

# Run specific test
pytest tests/test_materiality.py -v

# ═══════════════════════════════════════════════════════════
# KNOWLEDGE BASE
# ═══════════════════════════════════════════════════════════
# Index documents to Qdrant
python scripts/index_knowledge.py --path /knowledge/B_Libraries/

# Build Neo4j graph
python scripts/build_graph.py --path /knowledge/D_DecisionTrees/
```

---

*Last updated: December 2025*
*Version: 1.0*
*OSON SOFT © 2025*
