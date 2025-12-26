# Data Circuits Architecture

> [← Tech Stack](./02_Tech_Stack.md) | [Crawlers Sources →](./04_Crawlers_Sources.md)

---

## 3 Data Circuits

```
┌─────────────────────────────────────────────────────────────┐
│                    OSON SYSTEM                              │
├───────────────┬─────────────────┬───────────────────────────┤
│   CIRCUIT 1   │    CIRCUIT 2    │        CIRCUIT 3          │
│    STATIC     │      API        │        CRAWLERS           │
│  (при деплое) │   (real-time)   │    (дни-месяцы)           │
├───────────────┼─────────────────┼───────────────────────────┤
│    Qdrant     │  REST APIs      │  Web Scrapers             │
├───────────────┼─────────────────┼───────────────────────────┤
│ • ISA/IFRS    │ • ЦБ РУз курсы  │ • Global Standards        │
│ • Risk Library│ • БРВ Минфин   │ • Compliance/AML          │
│ • PBC Lists   │ • ERP (1С)     │ • Regulators (US/UK/EU)   │
│ • Glossaries  │ • Bank APIs    │ • Uzbekistan sources      │
│ • Templates   │ • OFAC lists   │ • Big4 Insights           │
└───────────────┴─────────────────┴───────────────────────────┘
```

---

## Circuit 1: Static Knowledge Base

**Когда:** При деплое и обновлениях
**Где хранится:** Qdrant (vectors)
**Что включает:**

| Блок | Содержимое | Хранилище |
|------|------------|-----------|
| A (Routing) | System prompts, Style guide | В промпт (не векторизуется) |
| B (Libraries) | Risk Library, PBC, Glossary | Qdrant |
| C (Formulas) | Materiality, Sampling | Qdrant |
| D (Decision Trees) | Legal Matrix, Opinion Tree | Qdrant |
| E (Templates) | TCWG, KAM, Reports | MinIO (file storage) |
| F (Knowledge) | Company Profile, Industry | Qdrant |

**Статус:** ✅ Приоритет для MVP

---

## Circuit 2: API Integrations

**Когда:** Real-time при запросах
**Статус:** ⏸️ ОТЛОЖЕНО (не нужно для MVP)

| API | Назначение | Приоритет |
|-----|------------|-----------|
| ЦБ РУз | Курсы валют | v1.5 |
| Минфин (БРВ) | Базовые расчётные величины | v1.5 |
| 1С ERP | Данные клиента | v2.0 |
| Bank APIs | Выписки | v2.0 |
| OFAC | Санкционные списки | v2.0 |

**Примечание:** lex.uz и norma.uz будут через API, не краулеры.

---

## Circuit 3: Web Crawlers

**Когда:** Периодически (дни-месяцы)
**Статус:** 📋 Список готов, реализация в roadmap

**Полный список источников:** [04_Crawlers_Sources.md](./04_Crawlers_Sources.md)

### Архитектурные принципы:

#### 1. Dynamic vs Static
```
DYNAMIC (News/Updates)     → Инкрементальная индексация
├── spot.uz
├── investopedia.com
└── Big4 insights

STATIC (Reference)         → Переиндексация при обновлениях
├── ifrs.org
├── lex.uz
└── sec.gov/EDGAR
```

#### 2. PDF Parsing
Большинство полезной информации в PDF. Использовать:
- **Unstructured** — для сложных документов
- **LlamaParse** — для таблиц финансовых отчетов

#### 3. Link Preservation (lex.uz)
Критично сохранять связи между документами:
- Ссылки на изменения
- История отмен
- Чтобы RAG не выдавал отменённые нормы

---

## Data Flow

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Circuit 1  │     │   Circuit 2  │     │   Circuit 3  │
│    Static    │     │     API      │     │   Crawlers   │
└──────┬───────┘     └──────┬───────┘     └──────┬───────┘
       │                    │                    │
       ▼                    ▼                    ▼
┌─────────────────────────────────────────────────────────┐
│                   ETL Pipeline                          │
│         (Parsing → Chunking → Embedding)                │
└─────────────────────────┬───────────────────────────────┘
                          │
          ┌───────────────┴───────────────┐
          ▼                               ▼
    ┌──────────┐                    ┌──────────┐
    │  Qdrant  │                    │PostgreSQL│
    │ (vectors)│                    │  (meta)  │
    └──────────┘                    └──────────┘
```

---

## Related Docs

- [Crawlers Sources](./04_Crawlers_Sources.md) — Полный список источников
- [Knowledge Base Structure](../knowledge-base/01_Structure.md) — Блоки A-F
