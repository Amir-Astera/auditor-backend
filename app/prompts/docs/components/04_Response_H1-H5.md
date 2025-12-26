# Response Components (H1-H5)

> [← Functions](./03_Functions_I1-I10.md) | [Main Flow →](./05_Main_Flow.md)

---

## Overview

Ответы системы состоят из 5 типов компонентов. Каждый ответ может содержать комбинацию H1-H5.

---

## Components

### H1: Text Response

Основной текстовый ответ от LLM.

```json
{
  "type": "H1_TEXT",
  "content": "Рассчитал существенность на основе выручки 500 млн:\n\n- **OM (Overall Materiality):** 15 000 000 ₽\n- **PM (Performance Materiality):** 9 750 000 ₽\n- **CT (Clearly Trivial):** 750 000 ₽"
}
```

---

### H2: Action Buttons

**КРИТИЧНО:** Пользователь должен подтвердить любое сохранение!

```json
{
  "type": "H2_BUTTONS",
  "buttons": [
    {
      "id": "save_materiality",
      "label": "💾 Сохранить",
      "action": "POST /api/v1/actions/save-materiality",
      "payload": {
        "project_id": "uuid",
        "om": 15000000,
        "pm": 9750000,
        "ct": 750000
      },
      "style": "primary"
    },
    {
      "id": "cancel",
      "label": "❌ Отмена",
      "action": "dismiss",
      "style": "secondary"
    },
    {
      "id": "recalculate",
      "label": "🔄 Пересчитать",
      "action": "prompt",
      "prompt": "Пересчитай с другими параметрами",
      "style": "outline"
    }
  ]
}
```

**Правила H2:**
1. LLM НИКОГДА не сохраняет без кнопки
2. Кнопка "Сохранить" всегда требует confirmed_by
3. Должна быть опция отмены

---

### H3: Data Table

Структурированные данные в таблице.

```json
{
  "type": "H3_TABLE",
  "title": "Расчёт существенности",
  "columns": ["Показатель", "Значение", "Формула"],
  "rows": [
    ["Benchmark", "Выручка", "—"],
    ["Benchmark Value", "500 000 000 ₽", "—"],
    ["OM", "15 000 000 ₽", "500M × 3%"],
    ["PM", "9 750 000 ₽", "OM × 65%"],
    ["CT", "750 000 ₽", "OM × 5%"]
  ],
  "footer": "Уровень риска: Normal"
}
```

---

### H4: File Download

Ссылка на сгенерированный файл.

```json
{
  "type": "H4_FILE",
  "filename": "TCWG_Communication_TRI-S_2024.docx",
  "url": "/api/v1/files/download/abc123",
  "size": "245 KB",
  "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "generated_at": "2025-12-20T15:30:00Z"
}
```

---

### H5: Redirect / Follow-up

Предложение перейти к следующему шагу.

```json
{
  "type": "H5_REDIRECT",
  "message": "✅ Существенность сохранена. Перейти к оценке рисков?",
  "options": [
    {
      "label": "Да, перейти к рискам",
      "action": "navigate",
      "target": "/project/{id}/risks"
    },
    {
      "label": "Нет, остаться здесь",
      "action": "dismiss"
    }
  ]
}
```

---

## Response Schema

```python
from pydantic import BaseModel
from typing import List, Optional, Literal

class Button(BaseModel):
    id: str
    label: str
    action: str
    payload: Optional[dict] = None
    style: Literal["primary", "secondary", "outline", "danger"]

class TableData(BaseModel):
    title: str
    columns: List[str]
    rows: List[List[str]]
    footer: Optional[str] = None

class FileInfo(BaseModel):
    filename: str
    url: str
    size: str
    mime_type: str

class RedirectOption(BaseModel):
    label: str
    action: str
    target: Optional[str] = None

class ChatResponse(BaseModel):
    intent: str  # J1-J20
    text: str  # H1
    buttons: Optional[List[Button]] = None  # H2
    table: Optional[TableData] = None  # H3
    file: Optional[FileInfo] = None  # H4
    redirect: Optional[dict] = None  # H5
```

---

## Example: Complete Response

```json
{
  "intent": "J1_MATERIALITY",
  "text": "Рассчитал существенность на основе выручки 500 млн...",
  "table": {
    "title": "Расчёт существенности",
    "columns": ["Показатель", "Значение"],
    "rows": [
      ["OM", "15 000 000 ₽"],
      ["PM", "9 750 000 ₽"],
      ["CT", "750 000 ₽"]
    ]
  },
  "buttons": [
    {"id": "save", "label": "💾 Сохранить", "action": "save_materiality", "style": "primary"},
    {"id": "cancel", "label": "❌ Отмена", "action": "dismiss", "style": "secondary"}
  ],
  "redirect": {
    "message": "После сохранения перейти к рискам?",
    "options": [
      {"label": "Да", "action": "navigate", "target": "/risks"},
      {"label": "Нет", "action": "dismiss"}
    ]
  }
}
```

---

## Related Docs

- [Main Flow](./05_Main_Flow.md) — Где H1-H5 используются
- [API Endpoints](../api/01_Endpoints.md) — Button handlers
