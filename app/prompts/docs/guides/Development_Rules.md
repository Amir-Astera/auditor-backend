# Development Rules

> [← Notion Admin Guide](./Notion_Admin_Guide.md) | [INDEX →](../INDEX.md)

---

## Overview

Правила разработки для проекта OSON Document Intelligence.

---

## DO (Обязательно)

### 1. Use Approved Stack

Используй только утверждённый стек технологий:
- Next.js 14 + TypeScript + Tailwind CSS
- FastAPI + Python 3.11 + Pydantic
- PostgreSQL 15 + Qdrant
- LightRAG + Claude API

**Никаких замен без явного одобрения.**

### 2. Implement H2 Buttons

Пользователь должен подтвердить любую запись в БД:

```python
# Response with action buttons
{
    "response": "Рассчитал существенность...",
    "buttons": [
        {"label": "Сохранить", "action": "save-materiality", "data": {...}},
        {"label": "Отмена", "action": "cancel"}
    ]
}
```

### 3. Use Python Tools for Calculations

LLM форматирует, Python считает:

```python
# Correct: LLM calls a tool
response = await llm.generate(
    prompt=prompt,
    tools=[calculate_materiality, calculate_sample_size, ...]
)

# Wrong: LLM calculates
# "OM = 500M × 3% = 15M" <- Never let LLM do math
```

### 4. Follow ISA/IFRS

Всегда ссылайся на стандарты в аудиторской логике:

```python
def calculate_materiality(...):
    """
    ISA 320 materiality calculation.

    Benchmark rates:
    - Revenue: 0.5% - 2%
    - Total Assets: 0.5% - 1%
    ...
    """
```

### 5. Write Tests

Минимум 80% coverage для функций:

```bash
# Run with coverage
pytest --cov=api --cov-report=html

# Run specific test
pytest tests/test_materiality.py -v
```

### 6. Use Type Hints

Pydantic для валидации:

```python
from pydantic import BaseModel
from typing import Literal

class MaterialityInput(BaseModel):
    benchmark: Literal["revenue", "assets", "equity", "profit"]
    benchmark_value: float
    risk_level: Literal["low", "normal", "high"] = "normal"
```

### 7. Log Everything

Структурированное логирование:

```python
import structlog

logger = structlog.get_logger()

logger.info("materiality_calculated",
    benchmark="revenue",
    om=15_000_000,
    user_id=user.id
)
```

---

## DON'T (Запрещено)

### 1. Never Suggest n8n

Решение финальное:
- Enterprise security
- Vendor lock-in
- Air-gapped deployment

### 2. Never Let LLM Save Without Confirmation

```python
# WRONG: Auto-save
await save_materiality(data)

# CORRECT: User confirmation required
return {"buttons": [{"label": "Сохранить", "action": "save-materiality"}]}
```

### 3. Never Hardcode Thresholds

Используй config/DB:

```python
# WRONG
PM_RATE = 0.65

# CORRECT
PM_RATE = config.get("pm_rate", default=0.65)
```

### 4. Never Expose API Keys

Используй environment variables:

```python
# WRONG
ANTHROPIC_API_KEY = "sk-ant-..."

# CORRECT
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
```

### 5. Never Skip Validation

Особенно для file uploads:

```python
ALLOWED_EXTENSIONS = {"pdf", "xlsx", "docx"}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

def validate_upload(file: UploadFile):
    ext = file.filename.split(".")[-1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, "Invalid file type")
```

### 6. Never Use Synchronous DB Calls

Используй async с SQLAlchemy 2.0:

```python
# WRONG
result = session.query(User).filter_by(id=user_id).first()

# CORRECT
async with async_session() as session:
    result = await session.execute(
        select(User).filter_by(id=user_id)
    )
    user = result.scalar_one_or_none()
```

---

## Quick Answers

| Question | Answer |
|----------|--------|
| Какой стек? | Next.js + FastAPI + Qdrant + LightRAG + K8s |
| Почему не n8n? | Enterprise security, vendor lock-in, air-gapped |
| Как работает? | User → RAG → LLM + Tools → Response + Buttons |
| Как сохранить? | Только через H2 кнопки с confirmed_by |

---

## Development Commands

```bash
# Start all services
docker-compose up -d

# Run API in dev mode
cd api && uvicorn main:app --reload --port 8000

# Run frontend
cd web && npm run dev

# Create migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Run all tests
pytest tests/ -v

# Index knowledge to Qdrant
python scripts/index_knowledge.py --all
```

---

## Related Docs

- [Tech Stack](../architecture/02_Tech_Stack.md) — Approved stack (DO NOT CHANGE)
- [Main Flow](../components/05_Main_Flow.md) — How it works
- [Functions](../components/03_Functions_I1-I10.md) — Python tools
