# Block B: Libraries (Справочники)

**Назначение блока:** Справочные библиотеки которые LLM использует через RAG-поиск. Содержат готовые риски, чеклисты, глоссарий.

**Хранение:** Qdrant (векторизованы в G1)

---

## Файлы Block B

| # | Файл                                  | ISA/IFRS           | Что это                                       | Что внутри                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           | Зачем нужен (простыми словами)                                                                                                                                                                     | Где применяется                 | Статус |
| - | ----------------------------------------- | ------------------ | --------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------- | ------------ |
| 1 | B1_Risk_Library_by_Cycle_v1.txt           | ISA 315/330, IFRS  | Библиотека рисков                   | **Центральная библиотека — 21 цикл (A-U):** Revenue/AR, Purchases/AP, Inventory, PPE/Impairment, Intangibles/R&D, Payroll, Cash/Treasury, Financial Instruments/ECL, Leases, Provisions/Legal, Taxation, Related Parties, Consolidation, Investment Property, FX, Going Concern, Estimates, IT Controls, Service Orgs, Disclosures, JE/Override. **Для каждого:** Assertions EN/RU, Typical risks, Fraud red flags, Audit responses (controls vs substantive), Analytics, Sampling, PBC data                                                  | **Ключевой!** Готовый каталог рисков по всем циклам аудита. Аудитор выбирает циклы → бот подбирает риски, процедуры, PBC | Risk Assessment (G2.4), Chat: intent "C"      | ✅           |
| 2 | B2_PBC_Master_List_v1.txt                 | ISA 500/505/580    | Мастер-лист документов          | **Центральный каталог PBC — ~60 позиций по циклам:** Governance (GOV01-03), Legal/SE (LEG01-04), FS/Closing (FS01-06), Cash/Bank (CB01-04), Revenue/AR (REV01-05), AP (AP01-05), Inventory (INV01-04), PPE/Intangibles (FA01-05), Equity/Debt, Provisions, Tax (TAX01-04), Related Parties, HR/Payroll, IT Controls, Going Concern (GC01-03), Confirmations, Management Rep. **Quality Gates:** форматы, naming, acceptance. **Phases:** PLN/YE/CL/BR. **Industry Addenda:** Insurance (IFRS 17), Mining, Construction, FMCG | **Ключевой!** Готовый чеклист что запросить у клиента. Бот фильтрует по Cycle/Phase/Priority и генерит email                                          | PBC трекер (G2.6), Chat: intent "H"     | ✅           |
| 3 | B3_Glossary_EN-RU-UZ_v1.txt               | ISA/IFRS all       | Глоссарий                                  | **Трехъязычный глоссарий (EN/RU/UZ-Latin) — ~100 терминов по категориям:** General & Reporting (Audit, TCWG, Going concern, Subsequent events), IFRS Concepts (Recognition, Fair value, Impairment, Provision, Contingent), IFRS 15/16/9/17 термины, Audit Core (Assertions, Materiality, PM, CT), Legal (Adjusting/Non-adjusting, KAM), PBC/Controls, Forensic (Red flags, NOCLAR). **False Friends:** Provision="оценочное обязательство" (не "резерв"!). CSV/XLSX export format                 | Единая терминология во всех ответах бота. Особенно важно для RU/UZ переводов в соответствии с IFRS                                                | Весь чат, Translation intent "J"       | ✅           |
| 4 | B4_Fraud_Risk_Factors_ISA240_v1.txt       | ISA 240            | Факторы фрода                           | **Библиотека по "треугольнику фрода":** 1) **Pressure** — агрессивные таргеты, бонусы от прибыли, 2) **Opportunity** — override controls, complex JE, слабый надзор, 3) **Rationalization**. Каждый фактор: id, category, description, assertions, related_cycle. **MANDATORY risks:** Revenue fraud (презумпция ISA 240), Management override — ОБЯЗАТЕЛЬНО на каждом аудите                                                       | Чеклист для форензик-оценки. ISA 240 требует всегда проверять Revenue fraud + Override                                                                                        | Forensic intent "I", Risk Assessment          | ⏳           |
| 5 | B5_Estimates_ISA540_Library_v1.txt        | ISA 540, IFRS 9/13 | Оценочные значения                 | **Библиотека accounting estimates:** Каждая оценка: estimate_id, name, examples, inherent_risk_level (High/Moderate/Low), assertions, typical_procedures. **Примеры:** ECL on receivables (IFRS 9) — High, test model/inputs/sensitivity; Fair value property (IFRS 13/IAS 40) — High, evaluate valuers, compare market. Расширяется по отраслям                                                                                                                                                                              | Каталог оценочных значений. ISA 540 — особое внимание к judgment, bias management                                                                                                   | Аудит оценок, Risk intent "C"      | ⏳           |
| 6 | B6_GoingConcern_ISA570_Indicators_v1.txt  | ISA 570            | Индикаторы непрерывности     | **Чеклист индикаторов по 3 категориям:** 1) **Financial** — net liability, negative cash flows, recurring losses; 2) **Operating** — loss of key market/customer/supplier, labour issues; 3) **Other** — legal threats. Каждый индикатор: id, category, description. JSON: indicator_id, present, evidence_ref, mgmt_assessment                                                                                                                                                                                       | Определить может ли компания продолжить работу. Индикаторы → запрос оценки руководства                                                           | Going Concern, Risk intent "D"                | ⏳           |
| 7 | B7_RelatedParties_ISA550_Checklist_v1.txt | ISA 550, IAS 24    | Чеклист связанных сторон      | **3 секции:** 1) **Identification** — реестр RP? акционеры/менеджмент/родственники?; 2) **Transactions** — все транзакции? arm's length?; 3) **Disclosure** — раскрытия полные? нераскрытые RP? JSON: all_identified, undisclosed_found, disclosure_adequate                                                                                                                                                                                                     | Найти ВСЕ связанные стороны. Нераскрытые RP = серьезный риск                                                                                                                | Проверка раскрытий, Risk "L" | ⏳           |
| 8 | B8_SubsequentEvents_ISA560_Library_v1.txt | ISA 560, IAS 10    | События после отчетной даты | **Библиотека + Чеклист:** EVENT_TYPE: Adjusting (confirms condition at balance sheet, напр. банкротство) vs Non-adjusting (новое, напр. M&A). Checklist: reviewed minutes/legal? adjusting reflected? non-adjusting disclosed? JSON: event_id, class, impact (Adjustment/Disclosure/None)                                                                                                                                                                                                                                      | Классифицировать события: корректировать FS или раскрыть                                                                                                                    | СПОД (bring-down), Legal "E"              | ⏳           |

---

## Архитектурное решение (RAG Pipeline)

**Принцип:** Block B слишком большой для System Prompt (~40K токенов), поэтому используется RAG через Qdrant.

### Рекомендуемая конфигурация

```python
# config/rag_settings.py

BLOCK_B_RAG_CONFIG = {
    # Chunking Strategy
    "chunk_strategy": "section",       # по секциям (====, ----), не по токенам
    "chunk_size": 1024,                # max токенов (если секция больше — split)
    "chunk_overlap": 0,                # структурированные docs — overlap не нужен

    # Retrieval
    "retrieval_top_k": 30,             # первичный поиск в Qdrant
    "rerank_top_k": 5,                 # после reranking → в LLM
    "min_similarity": 0.65,            # порог релевантности

    # Reranking (критически важно для compliance)
    "reranker": "cohere-rerank-v4",    # или mxbai-rerank-large-v2 (open-source)
    "rerank_enabled": True,

    # LightRAG specific
    "lightrag_mode": "hybrid",         # graph + vector
    "entity_extraction": True,         # извлечение ISA/IFRS сущностей

    # Metadata enrichment
    "metadata_fields": [
        "block",           # B
        "file_id",         # B1, B2, ...
        "isa_reference",   # ISA 315, ISA 530, etc.
        "ifrs_reference",  # IAS 37, IFRS 16, etc.
        "cycle",           # Revenue, Inventory, etc.
        "section"          # из структуры документа
    ]
}
```

### Обоснование (по результатам исследования 2024-2025)

| Решение                   | Почему                                                                                                                      | Источник                                                                                                                             |
| -------------------------------- | --------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| **Section-based chunking** | Аудиторские документы структурированы по секциям (====, ----). Секция = 1 chunk | [NVIDIA Benchmark 2024](https://stackoverflow.blog/2024/12/27/breaking-up-is-hard-to-do-chunking-in-rag-applications/)                          |
| **Chunk size 1024**        | Max размер секции. Factoid: 256-512, Analytical: 1024+. Секции ODI ≈ 300-800 токенов                    | [Qdrant Best Practices](https://qdrant.tech/course/essentials/day-1/chunking-strategies/)                                                       |
| **Overlap = 0**            | Структурированные документы с чёткими границами — overlap не нужен             | Анализ файлов ODI                                                                                                                |
| **Reranking**              | +20-35% accuracy для compliance документов                                                                           | [Analytics Vidhya 2025](https://www.analyticsvidhya.com/blog/2025/06/top-rerankers-for-rag/)                                                    |
| **LightRAG hybrid**        | Graph layer извлекает связи ISA↔IFRS↔Cycles                                                                       | [HKUDS/LightRAG](https://github.com/HKUDS/LightRAG)                                                                                             |
| **Metadata tagging**       | Фильтрация по ISA/IFRS/Cycle ускоряет retrieval                                                               | [Auxiliobits Financial RAG](https://www.auxiliobits.com/blog/rag-architecture-for-domain-specific-knowledge-retrieval-in-financial-compliance/) |

### Pipeline

```
User Query → Qdrant (top 30) → Reranker (top 5) → LLM + Context → Response
                    ↑                   ↑
            Vector + Graph        Cross-encoder
            (LightRAG hybrid)     (+20-35% accuracy)
```

### Альтернатива: Late Chunking (рассмотреть)

[Jina AI Late Chunking](https://jina.ai/news/late-chunking-in-long-context-embedding-models/) показывает **+24.47%** улучшение retrieval:

```
Традиционный: Текст → Chunk → Embed → Store
Late Chunking: Текст → Embed (весь) → Chunk → Store
```

**Требует:** Jina Embeddings v3 вместо OpenAI embeddings. Решение для Phase 2.

---

## Chunking: Анализ реальных файлов

### Проблема: Разные маркеры секций

После анализа файлов из всех блоков выявлена проблема — **разные форматы разделителей:**

| Block | Файл (пример) | Маркер секций         | Пример                    |
| ----- | ----------------------- | --------------------------------- | ------------------------------- |
| B     | B1_Risk_Library         | `====`, `----`                | `============`                |
| B     | B2_PBC_Master_List      | Заголовки +`---`       | `REVENUE & AR`                |
| C     | C1_Materiality          | `====`                          | `============`                |
| D     | D1_Legal_Matrix         | `─────` (Unicode)          | `─────────────`  |
| F     | F1_Company_Profile      | **Нет маркеров** | Только заголовки |

### Уточнение: Overlap НЕ нужен

После анализа реальных файлов Block B/C/D/F:

| Тип документа                              | Overlap          | Причина                                                                            |
| ------------------------------------------------------ | ---------------- | ----------------------------------------------------------------------------------------- |
| **Структурированные** (B, C, D) | **0**      | Чёткие границы `====`, `----`, секции самодостаточны |
| **Narrative** (F)                                | **50-100** | Контекст может "перетекать" между параграфами      |

**Вывод:** Для 90% файлов ODI overlap = 0, т.к. все документы структурированы по секциям.

### Варианты решения

**Вариант А: Унификация файлов**

Привести ВСЕ файлы к единому формату с маркером `---` или `##`:

```
До (F1_Company_Profile):
Legal & Identity

Registered name...

После:
---
## Legal & Identity

Registered name...
```

| Плюсы                                      | Минусы                                                         |
| ----------------------------------------------- | -------------------------------------------------------------------- |
| Один простой chunker                 | Нужно менять исходные файлы                  |
| Меньше кода = меньше багов | При обновлении — снова форматировать |
| Файлы более читаемые          | Одноразовая работа                                  |

**Вариант Б: Индивидуальные конфиги**

Создать конфиг `knowledge_index.yaml` с параметрами для каждого файла:

```yaml
# config/knowledge_index.yaml

files:
  B1_Risk_Library:
    section_marker: "^-{10,}|^={10,}"
    metadata_patterns:
      cycle: "^[A-Z]\\)\\s*(.+?)(?:\\s*\\(|$)"
      standards: "(ISA|IAS|IFRS)\\s*(\\d+)"
    expected_chunks: 21

  D1_Legal_Matrix:
    section_marker: "^─{10,}"  # Unicode dash
    metadata_patterns:
      standards: "(ISA|IAS)\\s*(\\d+)"
    expected_chunks: 8

  F1_Company_Profile:
    section_marker: "^[A-Z][a-z]+(?:\\s*[&,]\\s*[A-Z][a-z]+)*\\n\\n"
    metadata_patterns:
      lang: "(EN|RU):"
    expected_chunks: 10
```

| Плюсы                             | Минусы                                             |
| -------------------------------------- | -------------------------------------------------------- |
| Файлы не меняются       | Сложнее chunker                                   |
| Гибкость                       | Нужен конфиг для каждого файла |
| Точный контроль metadata | Больше кода                                    |

**Вариант В: Гибридный (рекомендуемый)**

1. Chunker с **умными defaults** (auto-detect маркеров)
2. **Опциональный конфиг** для файлов с особенностями
3. Файлы **НЕ меняем**

```python
def chunk_file(content: str, file_id: str) -> list[dict]:
    config = load_config(file_id)  # None если нет

    if config:
        marker = config["section_marker"]
    else:
        marker = auto_detect_marker(content)  # ====, ----, ─────, ##

    return split_by_marker(content, marker)
```

### Трудозатраты на конфиги

| Задача                                           | Объём        | Время              |
| ------------------------------------------------------ | ----------------- | ----------------------- |
| Прочитать все файлы                   | 18 файлов   | ~30 мин              |
| Определить структуру каждого | 18 файлов   | ~1 час               |
| Написать конфиг YAML                     | 18 записей | ~30 мин              |
| Проверить/отладить                    | —                | ~30 мин              |
| **Итого**                                   |                   | **~2.5 часа** |

**Статус:** TODO — подготовить `knowledge_index.yaml` перед имплементацией.

---

## Статус

| Файл | Статус | Примечание |
|------|--------|------------|
| B1 Risk Library | ✅ Готов | Центральная библиотека рисков |
| B2 PBC Master List | ✅ Готов | Мастер-лист документов |
| B3 Glossary | ✅ Готов | Трёхъязычный глоссарий |
| B4-B8 | ⏳ В разработке | Специализированные библиотеки |
| RAG Pipeline | ✅ Архитектура готова | Имплементация: 2-3 дня |
| knowledge_index.yaml | ⏳ TODO | Конфиг для chunking: 2.5 часа |
