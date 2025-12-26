# Intents (J1-J20)

> [← Engine](./01_Engine_F1-F6.md) | [Functions →](./03_Functions_I1-I10.md)

---

## Overview

Интенты — это типы аудиторских задач. Хранятся в Qdrant как часть Knowledge Base и используются LLM для понимания контекста запроса.

**Хранение:** Qdrant (векторизация)
**Использование:** RAG контекст для LLM

---

## MVP v1.0 (J1-J10)

| ID | Intent | ISA/IFRS | Description |
|----|--------|----------|-------------|
| J1 | MATERIALITY | ISA 320 | Расчёт OM/PM/CT |
| J2 | RISK | ISA 315/330 | Оценка рисков по циклам |
| J3 | LEGAL | ISA 501, IAS 37 | Оценка судебных исков |
| J4 | SAMPLING | ISA 530 | Расчёт размера выборки |
| J5 | PBC | ISA 500 | Управление запросами документов |
| J6 | TCWG | ISA 260/265 | Коммуникации с руководством |
| J7 | KAM | ISA 701 | Ключевые вопросы аудита |
| J8 | KNOWLEDGE | — | Поиск по базе знаний |
| J9 | DOCUMENT | — | Генерация документов |
| J10 | PROJECT | — | Управление проектом |

---

## Roadmap v1.5-2.5 (J11-J20)

| ID | Intent | ISA/IFRS | Version |
|----|--------|----------|---------|
| J11 | ACCEPTANCE | ISQM1/ISA 220 | v2.5 |
| J12 | UNDERSTANDING | ISA 315 | v2.5 |
| J13 | ESTIMATES | ISA 540 | v2.0 |
| J14 | GOING_CONCERN | ISA 570 | v1.5 |
| J15 | RELATED_PARTIES | ISA 550 | v2.5 |
| J16 | SUBSEQUENT_EVENTS | ISA 560 | v2.5 |
| J17 | TESTING | ISA 500/520/530 | v1.5 |
| J18 | MISSTATEMENTS | ISA 450 | v1.5 |
| J19 | OPINION | ISA 700-706 | v2.0 |
| J20 | REPORT | ISA 700-706 | v2.0 |

---

## Intent Details

### J1: MATERIALITY

**ISA:** 320
**Tools:** `calculate_materiality()`
**Keywords:** существенность, materiality, PM, CT, порог

**Пример запроса:**
> "Рассчитай существенность, выручка 500 млн"

---

### J2: RISK

**ISA:** 315, 330
**Tools:** `add_risk()`
**Keywords:** риск, risk, assertion, inherent, control

**Пример запроса:**
> "Оцени риски по циклу выручки"

---

### J3: LEGAL

**ISA:** 501, IAS 37
**Tools:** `assess_legal_matter()`
**Keywords:** иск, судебный, резерв, contingent, provision

**Пример запроса:**
> "Оцени судебный иск на 50 млн с вероятностью probable"

---

### J4: SAMPLING

**ISA:** 530
**Tools:** `calculate_sample_size()`
**Keywords:** выборка, sample, population, отбор

**Пример запроса:**
> "Рассчитай размер выборки для 1000 документов"

---

### J5: PBC

**ISA:** 500
**Tools:** `get_pbc_status()`, `update_pbc()`
**Keywords:** документ, запрос, PBC, deliverable

**Пример запроса:**
> "Статус запрошенных документов"

---

### J6: TCWG

**ISA:** 260, 265
**Tools:** `generate_document()`
**Keywords:** комитет, руководство, TCWG, board

**Пример запроса:**
> "Подготовь письмо для комитета по аудиту"

---

### J7: KAM

**ISA:** 701
**Tools:** `generate_document()`
**Keywords:** ключевой вопрос, KAM, significant matter

**Пример запроса:**
> "Какие вопросы могут быть KAM?"

---

### J8: KNOWLEDGE

**Tools:** `search_knowledge()`
**Keywords:** что такое, объясни, как, определение

**Пример запроса:**
> "Что такое inherent risk?"

---

### J9: DOCUMENT

**Tools:** `generate_document()`
**Keywords:** создай, сгенерируй, составь, шаблон

**Пример запроса:**
> "Создай engagement letter"

---

### J10: PROJECT

**Tools:** `get_project_context()`
**Keywords:** проект, статус, прогресс

**Пример запроса:**
> "Покажи статус проекта"

---

## Indexing

```bash
# Интенты индексируются как часть Knowledge Base
python scripts/index_knowledge.py --path /knowledge/intents/
```

---

## Related Docs

- [Engine](./01_Engine_F1-F6.md) — Как LLM использует контекст
- [Functions](./03_Functions_I1-I10.md) — Tools для каждого интента
