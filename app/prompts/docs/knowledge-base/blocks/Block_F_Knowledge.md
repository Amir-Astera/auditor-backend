
## Block F: Knowledge (Знания)

**Назначение блока:** Дополнительные знания о компании и отраслях.

**Хранение:** Qdrant (векторизованы в G1)

| # | Файл                              | Что это                     | Что внутри                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     | Зачем нужен (простыми словами)                                                                                                                            | Где применяется         | Статус |
| - | ------------------------------------- | --------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------- | ------------ |
| 1 | F1_Company_Profile_TRI-S-Audit_v1.txt | Профиль компании   | **Полный профиль TRI-S-AUDIT:** 1) **Legal:** Registered name, Jurisdiction (Uzbekistan), INN 204722723, Address (Tashkent, Mirabad), Website, Contacts (email, phone, WhatsApp, Telegram), 2) **Elevator Pitch (EN/RU):** краткое описание компании, 3) **Services (5 направлений):** Audit & Assurance (IFRS, NAS, US GAAP, ESG, forensic), Investment Consulting (DD, valuations), Business Intelligence (PEP/sanctions, dashboards), Advisory & Risk (COSO, tax), Digital Finance & IT (ERP, automation), 4) **Industries:** Energy, Distribution/FMCG, Mining, Construction, Insurance, IT/Startups, 5) **Quality & Ethics:** ISA/IESBA compliance, 6) **Leadership:** Managing Partner Svetlana Golosova | Бот может отвечать на вопросы о компании TRI-S-AUDIT: кто мы, что делаем, контакты, услуги, отрасли           | Proactive chat responses, Company FAQ | ✅           |
| 2 | F2_Industry_Knowledge_Pack_v1.txt     | Отраслевые знания | **Структурированный пак отраслевых знаний:** Каждая **INDUSTRY** содержит: code, name, key_revenue_models, key_risks, typical_controls. **Текущие отрасли (2):** 1) **RETAIL:** Sales of goods (stores/online), risks (revenue cut-off, inventory shrinkage), controls (POS reconciliations, cycle counts), 2) **INSURANCE:** Premium income, risks (liability measurement, revenue recognition), controls (actuarial reserving, policy admin systems). **Расширяемый формат** — добавлять отрасли по мере необходимости (Energy, Mining, Construction, IT и др. из F1)                                                                   | Бот использует отраслевую специфику: типичные риски и контроли для конкретной индустрии клиента | Industry-specific guidance in chat    | ✅           |

---

### Block F: Архитектурное решение (Simple RAG)

**Принцип:** Простейший блок — текстовая векторизация в Qdrant без сложностей.

**Особенности:**
- Нет сложных формул (как Block C) → только RAG, без Python Tools
- Нет деревьев решений (как Block D) → только информация
- Небольшой объём (2 файла, ~85 строк) → быстрая векторизация

#### RAG конфигурация для Block F

```python
# config/rag_settings.py

BLOCK_F_RAG_CONFIG = {
    # Chunking Strategy
    "chunk_strategy": "paragraph",  # F1 без маркеров секций (====)
    "chunk_size": 512,              # небольшие chunks для точности
    "chunk_overlap": 50,            # небольшой overlap для контекста

    # Retrieval
    "retrieval_top_k": 10,          # меньше чем Block B (всего 2 файла)
    "rerank_top_k": 3,
    "min_similarity": 0.70,

    # Metadata
    "metadata_fields": [
        "block",           # F
        "file_id",         # F1, F2
        "section",         # Legal, Services, Industries (для F1)
        "industry_code",   # RETAIL, INSURANCE (для F2)
        "lang"             # EN, RU (для F1 multilang sections)
    ]
}
```

#### Chunking стратегия

**F1_Company_Profile:**
- Структура: **Без маркеров секций** (только заголовки)
- Chunking: По параграфам (2-4 строки)
- Результат: ~15-20 chunks

**F2_Industry_Pack:**
- Структура: **INDUSTRY блоки** (по отраслям)
- Chunking: 1 отрасль = 1 chunk
- Результат: 2 chunks (RETAIL, INSURANCE) → расширяемо

#### Workflow примеры

**Пример 1: Вопрос о компании**

```
User: "Какие услуги предлагает TRI-S-AUDIT?"

→ RAG → G1 (F1 секция "Services")
→ LLM: "TRI-S-AUDIT предлагает 5 направлений:
  1. Audit & Assurance (IFRS, NAS, US GAAP, ESG, forensic)
  2. Investment Consulting (due diligence, valuations)
  3. Business Intelligence (PEP/sanctions checks, dashboards)
  4. Advisory & Risk (COSO, tax optimization)
  5. Digital Finance & IT (ERP, automation)"
```

**Пример 2: Отраслевая специфика**

```
User (project: retail client): "Какие типичные риски для retail?"

→ RAG → G1 (F2 RETAIL block)
→ LLM: "Для retail типичные риски:
  - Revenue cut-off (продажи в конце периода)
  - Inventory shrinkage (потери товара)
  - POS reconciliation (сверка кассовых данных)

  Типичные контроли:
  - Daily POS reconciliations
  - Cycle counts inventory
  - CCTV monitoring"
```

**Пример 3: Контакты (proactive)**

```
User: "Как связаться с компанией?"

→ RAG → G1 (F1 секция "Contacts")
→ LLM: "Контакты TRI-S-AUDIT:
  - Email: info@tri-s-audit.uz
  - Phone/WhatsApp/Telegram: +998 71 256-25-66
  - Website: https://www.tri-s-audit.uz/
  - Address: Uzbekistan, Tashkent, Mirabad, Taras Shevchenko 28"
```

#### Связь с другими блоками

| Block F предоставляет | Используется в |
|----------------------|----------------|
| **Отраслевые риски** (F2) | Block B (B1_Risk_Library) для кастомизации |
| **Услуги компании** (F1) | Chat responses (FAQ) |
| **Контакты** (F1) | Автоматические email/письма |

#### Имплементация

**Трудозатраты:**
- Парсинг 2 файлов: ~15 минут
- Chunking (paragraph-based): ~15 минут
- Metadata extraction: ~15 минут
- Upload в Qdrant: ~5 минут
- Testing queries: ~10 минут
- **Итого: ~1 час**

**Статус:** Простейший блок, можно векторизовать последним (не критичен для MVP).

---
