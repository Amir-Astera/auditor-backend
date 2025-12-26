# API Endpoints

> [← Neo4j](../database/03_Neo4j.md) | [Auth →](./02_Auth.md)

---

## Overview

FastAPI REST API для OSON Document Intelligence. Все endpoints требуют JWT аутентификацию (кроме /auth/login).

Base URL: `http://localhost:8000/api/v1`

---

## Authentication

```
POST   /api/v1/auth/login           # Returns JWT
POST   /api/v1/auth/refresh         # Refresh token
POST   /api/v1/auth/logout          # Invalidate token
GET    /api/v1/auth/me              # Current user info
```

See [Auth Documentation](./02_Auth.md) for details.

---

## Projects

```
GET    /api/v1/projects             # List (with filters)
POST   /api/v1/projects             # Create
GET    /api/v1/projects/{id}        # Get with related data
PUT    /api/v1/projects/{id}        # Update
DELETE /api/v1/projects/{id}        # Soft delete
```

### List Projects

```http
GET /api/v1/projects?status=planning&limit=10
Authorization: Bearer <token>
```

Response:
```json
{
    "items": [
        {
            "id": "uuid",
            "client_name": "Client A",
            "status": "planning",
            "period_start": "2024-01-01",
            "period_end": "2024-12-31"
        }
    ],
    "total": 50,
    "page": 1
}
```

---

## Chat (Main AI Endpoint)

### Send Message

```http
POST /api/v1/chat
Authorization: Bearer <token>
Content-Type: application/json

{
    "project_id": "uuid",
    "message": "Рассчитай существенность, выручка 500 млн",
    "attachments": []
}
```

Response:
```json
{
    "response": "Рассчитал существенность по ISA 320...",
    "intent": "J1_MATERIALITY",
    "buttons": [
        {"label": "Сохранить", "action": "save-materiality", "data": {...}},
        {"label": "Отмена", "action": "cancel"}
    ],
    "table": {
        "headers": ["Показатель", "Значение"],
        "rows": [
            ["OM", "15,000,000"],
            ["PM", "9,750,000"],
            ["CT", "750,000"]
        ]
    }
}
```

### Get Chat History

```http
GET /api/v1/chat/{project_id}
Authorization: Bearer <token>
```

### Clear Chat History

```http
DELETE /api/v1/chat/{project_id}
Authorization: Bearer <token>
```

---

## Actions (H2 Button Handlers)

```
POST   /api/v1/actions/save-materiality
POST   /api/v1/actions/add-risk
POST   /api/v1/actions/add-legal-matter
POST   /api/v1/actions/update-pbc
POST   /api/v1/actions/generate-document
```

### Save Materiality

```http
POST /api/v1/actions/save-materiality
Authorization: Bearer <token>
Content-Type: application/json

{
    "project_id": "uuid",
    "benchmark": "revenue",
    "benchmark_value": 500000000,
    "om": 15000000,
    "pm": 9750000,
    "ct": 750000,
    "risk_level": "normal",
    "rationale": "OM = 500M × 3% = 15M"
}
```

Response:
```json
{
    "success": true,
    "message": "Существенность сохранена",
    "record_id": "uuid"
}
```

**Note:** All actions require `confirmed_by` (set from JWT user).

---

## Files

```
POST   /api/v1/files/upload         # Upload + auto-vectorize
GET    /api/v1/files/{id}           # Download
GET    /api/v1/files/{id}/status    # Vectorization status
DELETE /api/v1/files/{id}           # Delete
```

### Upload File

```http
POST /api/v1/files/upload
Authorization: Bearer <token>
Content-Type: multipart/form-data

project_id=uuid
file=@document.pdf
```

Response:
```json
{
    "id": "uuid",
    "file_name": "document.pdf",
    "file_type": "pdf",
    "file_size": 1024000,
    "is_vectorized": false,
    "status": "processing"
}
```

### Check Vectorization Status

```http
GET /api/v1/files/{id}/status
Authorization: Bearer <token>
```

Response:
```json
{
    "is_vectorized": true,
    "vectorized_at": "2024-01-15T10:30:00Z",
    "chunk_count": 42
}
```

---

## Knowledge (RAG)

```
POST   /api/v1/knowledge/search     # Search knowledge base
GET    /api/v1/knowledge/stats      # Index statistics
```

### Search Knowledge Base

```http
POST /api/v1/knowledge/search
Authorization: Bearer <token>
Content-Type: application/json

{
    "query": "materiality calculation for manufacturing",
    "top_k": 5,
    "filter": {
        "block": ["B", "C"]
    }
}
```

Response:
```json
{
    "chunks": [
        {
            "content": "ISA 320 requires...",
            "source": "C1_Materiality_Playbook_v1.txt",
            "score": 0.92
        }
    ],
    "sources": ["C1_Materiality_Playbook_v1.txt"]
}
```

---

## Response Components (H1-H5)

| Component | JSON Field | Description |
|-----------|------------|-------------|
| H1 | `response` | Text response |
| H2 | `buttons` | Action buttons |
| H3 | `table` | Data table |
| H4 | `file` | File download link |
| H5 | `redirect` | Redirect suggestion |

---

## Error Responses

```json
{
    "detail": "Error message",
    "code": "ERROR_CODE",
    "status_code": 400
}
```

Common error codes:
- `UNAUTHORIZED` (401) — Invalid/expired token
- `FORBIDDEN` (403) — Insufficient permissions
- `NOT_FOUND` (404) — Resource not found
- `VALIDATION_ERROR` (422) — Invalid request data

---

## Related Docs

- [Auth](./02_Auth.md) — Authentication details
- [Response Components](../components/04_Response_H1-H5.md) — H1-H5

