# Engine Components

> [← INDEX](../INDEX.md) | [Functions →](./03_Functions_I1-I10.md)

---

## Overview

Упрощённая архитектура: LLM обрабатывает запросы напрямую с RAG контекстом.

```
User Query → RAG (Qdrant) → LLM + Tools → Response + Buttons
```

---

## Components

### RAG Engine

**Функция:** Поиск релевантного контекста в Qdrant

| Параметр | Значение |
|----------|----------|
| Input | User query |
| Output | Relevant chunks |
| Technology | LightRAG + Qdrant |
| Location | `/engine/rag_engine.py` |

**Особенности:**
- Vector search для всех блоков (B, C, D, F)
- Semantic ranking
- Контекст подаётся в промпт LLM

---

### Prompt Builder

**Функция:** Сборка system prompt + context для LLM

| Параметр | Значение |
|----------|----------|
| Input | RAG chunks, Project context |
| Output | Complete prompt |
| Technology | Jinja2 templates |
| Location | `/engine/prompt_builder.py` |

**Шаблоны:**
- A1_StyleGuide → базовый стиль
- A2_ISA_RoutingPrompts → аудиторский контекст
- A6_Model_IO_Guide → формат ввода/вывода

---

### Function Executor (Tools)

**Функция:** Выполнение Python функций по вызову LLM

| Параметр | Значение |
|----------|----------|
| Input | Function call from LLM |
| Output | Calculation results |
| Technology | Python |
| Location | `/engine/function_executor.py` |

**Важно:**
- LLM НЕ делает расчёты сам
- LLM вызывает tools (функции)
- Функции возвращают результаты
- LLM форматирует ответ

**Доступные tools:**
- `calculate_materiality()` — расчёт существенности
- `calculate_sample_size()` — размер выборки
- `assess_legal_matter()` — оценка судебных дел
- `search_knowledge()` — поиск в базе знаний
- `generate_document()` — генерация документов

См: [Functions](./03_Functions_I1-I10.md)

---

### Response Formatter

**Функция:** Форматирование ответа с компонентами H1-H5

| Параметр | Значение |
|----------|----------|
| Input | LLM response, Function results |
| Output | Formatted response with buttons |
| Technology | Python |
| Location | `/engine/response_formatter.py` |

**Компоненты ответа:**
- H1: Text Response
- H2: Action Buttons (💾 Сохранить)
- H3: Data Table
- H4: File Download
- H5: Redirect

См: [Response H1-H5](./04_Response_H1-H5.md)

---

### File Processor

**Функция:** Парсинг загруженных документов

| Параметр | Значение |
|----------|----------|
| Input | PDF, XLSX, DOCX files |
| Output | Extracted text, tables |
| Technology | PyMuPDF, openpyxl, python-docx |
| Location | `/engine/file_processor.py` |

**Рекомендации:**
- Добавить **Unstructured** для сложных PDF
- Добавить **LlamaParse** для финансовых таблиц

---

## Simplified Flow

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│    User     │────>│   Backend   │────>│   Qdrant    │
│   Message   │     │   (FastAPI) │     │   (RAG)     │
└─────────────┘     └──────┬──────┘     └──────┬──────┘
                          │                    │
                          │ context            │
                          ◄────────────────────┘
                          │
                          ▼
                   ┌─────────────┐
                   │    LLM      │
                   │  (Claude)   │
                   │  + Tools    │
                   └──────┬──────┘
                          │
                          ▼
                   ┌─────────────┐
                   │  Response   │
                   │  + Buttons  │
                   └─────────────┘
```

---

## File Structure

```
/engine/
├── rag_engine.py            # LightRAG + Qdrant
├── prompt_builder.py        # Jinja2 templates
├── function_executor.py     # Tools execution
├── response_formatter.py    # H1-H5 formatting
└── file_processor.py        # PDF/XLSX/DOCX
```

---

## Related Docs

- [Functions](./03_Functions_I1-I10.md) — Бизнес-логика (tools)
- [Response H1-H5](./04_Response_H1-H5.md) — Компоненты ответа
- [Main Flow](./05_Main_Flow.md) — Полный flow
