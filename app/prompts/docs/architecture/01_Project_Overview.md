# Project Overview

> [← INDEX](../INDEX.md) | [Tech Stack →](./02_Tech_Stack.md)

---

## Product Info

| Field | Value |
|-------|-------|
| **Product** | OSON Document Intelligence (ранее TRI-S-AUDIT MVP) |
| **Company** | OSON SOFT |
| **Type** | On-Premise RAG System for Audit Automation |
| **Target Market** | Big 4 audit firms, крупные промышленные предприятия |
| **Key Value** | Автоматизация аудиторских процедур по ISA/IFRS |
| **Deployment** | On-Premise, Air-gapped ready |

---

## Business Goals & Roadmap

| Quarter | Goal |
|---------|------|
| Q1 2025 | Пилот с TRI-S-AUDIT |
| Q2 2025 | 5-10 локальных клиентов |
| Q3-Q4 2025 | Экспансия: Казахстан, Кыргызстан |
| 2026 | Big4 региональные офисы |

---

## Key Decisions

### Почему On-Premise?
- **Data sovereignty** — Big4 клиенты требуют контроль над данными
- **Air-gapped** — возможность работы без интернета
- **Compliance** — соответствие локальным регуляциям

### Почему не SaaS?
- Аудиторские данные = конфиденциальные
- Клиенты не готовы хранить данные в облаке
- Возможен гибридный вариант в будущем

---

## Interfaces

ODI предоставляет **3 интерфейса** для работы с системой:

```
┌─────────────────────────────────────────────────────────────┐
│                        INTERFACES                           │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │
│  │ ADMIN PANEL │  │ USER PANEL  │  │ TELEGRAM    │          │
│  │   (Web)     │  │   (Web)     │  │    APP      │          │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘          │
│         │                │                │                 │
│         └────────────────┼────────────────┘                 │
│                          ▼                                  │
│                 ┌─────────────────┐                         │
│                 │  FastAPI Backend │                        │
│                 └─────────────────┘                         │
└─────────────────────────────────────────────────────────────┘
```

### Admin Panel (Web)

| Функция | Описание |
|---------|----------|
| User Management | CRUD пользователей, роли (admin/partner/manager/auditor) |
| Telegram Auth | Добавление tg_id для аутентификации в Telegram |
| System Settings | Конфигурация LLM, RAG параметров |
| Knowledge Base | Управление файлами A-F блоков |
| Statistics | Использование токенов, активность |

### User Panel (Web)

| Функция | Описание |
|---------|----------|
| Project List | Список проектов пользователя |
| Create Project | Создание нового аудита (client, industry, period, framework) |
| File Upload | Загрузка документов клиента → MinIO + G1.X Qdrant |
| AI Chat | Чат с LLM в рамках проекта |
| Dashboard | Materiality, Risks, Legal Matrix, PBC status |

### Telegram App

| Функция | Описание |
|---------|----------|
| Auth | По tg_id (admin добавляет в web panel) |
| Project Select | Выбор активного проекта |
| Chat | Тот же backend, адаптированные H1-H5 ответы |
| Quick Actions | Inline buttons для частых операций |

**Telegram Auth Flow:**
```
1. Admin (Web) → добавляет user с phone/tg_id
2. User (Telegram) → /start → Bot проверяет tg_id в G2.1 users
3. Если найден → выбор проекта → chat
```

---

## Related Docs

- [Tech Stack](./02_Tech_Stack.md) — Утверждённый стек
- [Data Circuits](./03_Data_Circuits.md) — Архитектура данных
