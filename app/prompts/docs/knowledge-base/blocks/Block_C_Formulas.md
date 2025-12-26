
## Block C: Formulas (Формулы)

**Назначение блока:** Формулы и методологии расчетов.

**Хранение:** Qdrant + Python Tool (текст в Qdrant для объяснений, расчёты через функции I1-I10)

| # | Файл                                    | ISA/IFRS         | Что это                               | Что внутри                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      | Зачем нужен (простыми словами)                                                                                                                                                                                                                                                                                            | Где применяется                            | Статус |
| - | ------------------------------------------- | ---------------- | ------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------- | ------------ |
| 1 | C1_Materiality_Playbook_v1.1.txt            | ISA 320, ISA 450 | Playbook существенности       | **Полная методология расчета:** 1) Политика фирмы (Revenue 0.5-1.5% default), 2) Альтернативные бенчмарки (PBT 5-10%, Assets 1-2%, Equity 2-5%), 3) Логика выбора % (риск→ниже, PIE→ниже), 4) Performance Materiality по риску (High 50-60%, Moderate 60-70%, Low 70-75%), 5) Clearly Trivial Threshold (3-5%), 6) Specific Materiality для чувствительных статей, 7) Отраслевые пресеты (Retail, Insurance, NFP и др.), 8) Формат рабочего документа, 9) Примеры расчетов                           | **Ключевой файл!** Автоматический расчет существенности по данным клиента. Бот спрашивает: отрасль, выручку, активы, PIE/не-PIE, уровень риска — и выдает готовый рабочий документ с OM/PM/CTT/SM | Таблица G2.3 materiality, Chat: intent class "A"  | ⏳           |
| 2 | C2_Sampling_Methods_ISA530_v1.txt           | ISA 530/330/520  | Методы выборки                 | **Полная методология выборки:** 1) Routing Questions (Area, Population N/TBV, Risk, TDR/TM, EDR/EM, CL/SR, Stratification, MUS suitability), 2) **Method Selection Matrix:** Attribute (controls, binary deviations), MUS/PPS (substantive, overstatement risk), Classical Variables (MPU/Ratio/Difference for negatives/zeros), 3) Workpapers для каждого метода (Selection Sheet, Results & Projection, Conclusion), 4) Stratification & Top-Sampling rules, 5) Worked Examples (Attribute for 3-way match, MUS for AR, Variables for Inventory), 6) **Strict Output Format**                                                | **Ключевой!** Бот спрашивает: population, assertion, risk level → выдает method + sample size n + pull list + acceptance tests                                                                                                                                                                                   | Sampling intent "B", Test of Controls/Substantive        | ⏳           |
| 3 | C4_Testing_Procedures_ISA500_520_530_v1.txt | ISA 500/520/530  | Процедуры тестирования | **Фреймворк тестирования:** 1) **3 типа тестов:** ToC (Test of Controls — проверка работы контролей), SAP (Substantive Analytical Procedure — аналитика для high-volume данных), ToD (Test of Details — проверка отдельных транзакций), 2) **Матрица размеров выборки:** Low Risk→10, Medium→25, High→40 образцов, 3) **Связь с БД:** FIELDS_G2_9 (project_id, risk_id, test_type, description, sample_size, status), FIELDS_G2_10 (procedure_id, exception_desc, amount, resolution, is_misstatement)            | Бот определяет тип теста по риску/контролю → формирует размер выборки → результаты пишет в G2.9/G2.10 (тесты + найденные исключения)                                                                                                           | Testing procedures, links C2 sampling → G2 results      | ✅           |
| 4 | C5_Misstatements_ISA450_Formulas_v1.txt     | ISA 450          | Формулы искажений           | **Логика SUD (Summary of Unadjusted Differences):** 1) **3 типа искажений:** factual (точные ошибки), judgmental (оценочные), projected (экстраполяция из выборки на популяцию), 2) **Формулы:** total_unadjusted_misstatements = SUM(amount WHERE is_adjusted=false), projected_misstatement = sample_error_rate × population_value, 3) **Правило сравнения с PM:** Above_PM (>PM) → modify opinion risk, Close_to_PM (>0.8×PM) → request adjustments, Below_PM → OK, 4) **Поля G2.11:** project_id, area, type, amount, is_adjusted, rationale | Агрегирует все найденные искажения по проекту, сравнивает с Performance Materiality, помогает принять решение: требовать исправления или менять мнение                                                                                 | SUD tracking in G2.11, links to C1 materiality & opinion | ✅           |

### Block C: Архитектурное решение (Hybrid: RAG + Python Tools)

**Принцип:** Block C содержит два типа документов с принципиально разной обработкой.

#### Два формата файлов

| Файлы       | Формат        | Структура                                                | Назначение                                                      | Обработка                  |
| ---------------- | ------------------- | ----------------------------------------------------------------- | ------------------------------------------------------------------------- | ----------------------------------- |
| **C1, C2** | Narrative playbooks | Секции с `====` маркерами (~200-250 строк) | Методологии для**о бъяснения** логики | **Qdrant** (section chunking) |
| **C4, C5** | YAML-like specs     | Machine-readable (~40-55 строк)                              | Спецификации для**имплементации**       | **Python Tools** (I1-I10)     |

#### Почему "Qdrant + Python Tool"

**Проблема:** Если загрузить формулы только в Qdrant — LLM будет пытаться "объяснить" формулы словами, а не **вычислить** результат.

**Решение:**

1. **C1, C2 → Qdrant (RAG):**

   - LLM читает narrative: "как выбрать бенчмарк для materiality", "когда использовать MUS vs Variables"
   - Может **объяснить** пользователю методологию
2. **C4, C5 → Python функции I1-I10:**

   - Формулы перекодированы в Python Tools
   - LLM **вызывает функцию** для расчёта, а не пытается считать сам
   - Гарантия точности вычислений
3. **Текст C4, C5 ТАКЖЕ в Qdrant** (для справки):

   - Если пользователь спрашивает "как считается sample_size" — LLM находит формулу в тексте
   - Но для реального расчёта — вызывает Python Tool

#### Примеры функций

Из документации [03_Functions_I1-I10.md](../components/03_Functions_I1-I10.md):

```python
# I1: calculate_materiality (C1 playbook)
def calculate_materiality(
    benchmark: str,           # "Revenue" | "PBT" | "Assets" | "Equity"
    benchmark_value: float,
    risk_level: str,          # "High" | "Moderate" | "Low"
    is_pie: bool
) -> dict:
    """
    Возвращает: {
        "om": 500000,
        "pm": 350000,
        "ct": 15000,
        "rationale": "Revenue 0.5% for PIE High risk..."
    }
    """

# I2: calculate_sample_size (C2 sampling)
def calculate_sample_size(
    population_size: int,
    pm: float,
    expected_errors: float,
    confidence: float
) -> dict:
    """
    Возвращает: {
        "sample_size": 40,
        "method": "MUS",
        "sampling_interval": 250000
    }
    """

# I3: assess_legal_matter (C4 testing + legal)
def assess_legal_matter(
    claim_amount: float,
    probability: str,         # "probable" | "possible" | "remote"
    pm: float,
    outcome_estimable: bool
) -> dict:
    """
    Возвращает: {
        "is_material": true,
        "disclosure_required": true,
        "provision_required": true,
        "is_kam": true
    }
    """
```

#### RAG конфигурация для C1, C2

```python
BLOCK_C_RAG_CONFIG = {
    # Chunking Strategy (как Block B)
    "chunk_strategy": "section",       # по ==== маркерам
    "chunk_size": 1024,
    "chunk_overlap": 0,                # секции самодостаточны

    # Retrieval
    "retrieval_top_k": 20,             # меньше чем Block B (меньше файлов)
    "rerank_top_k": 3,
    "min_similarity": 0.70,            # выше порог (точные формулы)

    # Metadata
    "metadata_fields": [
        "block",           # C
        "file_id",         # C1, C2
        "isa_reference",   # ISA 320, ISA 530, etc.
        "formula_id",      # для C1/C2: OM, PM, CTT, SI, RF
        "method_type",     # для C2: Attribute, MUS, Variables
        "section"
    ]
}
```

#### Файлы C4, C5 — НЕ векторизуются целиком

**C4, C5 обрабатываются иначе:**

| Файл              | Что извлекаем | Куда         | Зачем                                              |
| --------------------- | ------------------------- | ---------------- | ------------------------------------------------------- |
| C4_Testing_Procedures | `TEST_TYPE` schemas     | Python enums     | Классификация ToC/SAP/ToD                  |
| C4                    | `SAMPLE_SIZE_RULE`      | Python function  | Расчёт sample size по риску                |
| C5_Misstatements      | `MISSTATEMENT_TYPE`     | Python enums     | Классификация factual/judgmental/projected |
| C5                    | `FORMULA` expressions   | Python functions | Расчёт SUD, сравнение с PM              |

**Опционально:** Можем положить текстовое описание в Qdrant (как справку), но **расчёты всегда через Python**.

#### Workflow пользователя

**Сценарий 1: Пользователь спрашивает "Как считать materiality?"**

```
User: Как выбрать бенчмарк для materiality для retail компании?

→ RAG → G1 (C1 секция "02) Choosing the Benchmark")
→ LLM: "Для retail обычно Revenue 0.5-1.5%..."
```

**Сценарий 2: Пользователь просит "Рассчитай materiality" (user input)**

```
User: Рассчитай materiality. Выручка 100M, PIE, High risk.

→ LLM → calls I1: calculate_materiality("Revenue", 100000000, "High", true)
→ Python: return {"om": 500000, "pm": 300000, "ct": 15000, ...}
→ LLM writes to G2.3: project_id, om, pm, ct, benchmark, rationale
→ LLM: "OM: $500K (0.5%), PM: $300K (60% of OM), CTT: $15K (3%)"
```

**Сценарий 2б: Materiality из G1_Client (Trial Balance)**

```
User: "Рассчитай materiality из TB клиента"

→ Query G1_Client: "Trial Balance 2024" → находит Revenue = $100M
→ User context: PIE = true, Risk = High
→ LLM calls I1: calculate_materiality("Revenue", 100000000, "High", true)
→ Python: {om: 500000, pm: 300000, ct: 15000}
→ Writes to G2.3
```

**Сценарий 3: Пользователь просит "Объясни MUS и рассчитай sample size"**

```
User: Объясни MUS метод и рассчитай sample size для AR $10M, PM $300K

→ RAG → G1 (C2 секция "03) MUS / PPS — SUBSTANTIVE")
→ LLM: "MUS = Monetary Unit Sampling, используется для..."

→ LLM → calls I2: calculate_sample_size(10000000, 300000, ...)
→ Python: return {"sample_size": 33, "method": "MUS", "SI": 303030}
→ LLM: "Sample size: 33 items, SI: $303K"
```

**Сценарий 4: Real workflow с G1_Client (Revenue Testing)**

```
1. Client uploads "Sales Register 2024.xlsx" → MinIO (G3) + G1_Client (vectorized)

2. User: "Рассчитай sample size для revenue testing"

   → RAG G1: C2 (методология MUS)
   → Query G1_Client: "Sales Register" → парсит строки
   → Population: N=1,500 invoices, Total=$50M

   → LLM calls I2: calculate_sample_size(1500, pm=300000, ...)
   → Python: {sample_size: 40, method: "MUS", SI: 1250000}

   → LLM writes to G2.9:
     procedure_id: "PROC-REV-001"
     sample_size: 40
     status: "Planned"

3. User: "Выбери 40 invoices по MUS"

   → LLM reads Sales Register from G1_Client
   → Systematic selection: SI=$1.25M, random start
   → Generates list of 40 invoices
   → Saves to G2.12 (Sample Selection)

4. Auditor tests invoice #567 → finds exception:
   "No delivery note, amount $125K"

   → User: "Запиши exception"

   → LLM uses C5 logic: is_misstatement = true
   → Writes to G2.10: exception_desc, amount, is_misstatement
   → Auto-trigger: G2.10 → G2.11 SUD
```

#### Критический момент

**Формулы C1-C5 ≠ просто текст для чтения. Формулы = исполняемый код.**

Если просто положить в Qdrant и надеяться что LLM "посчитает" — будет дрейф точности:

- LLM может ошибиться в арифметике
- LLM может неправильно применить логику (IF/ELSE)
- Нет гарантии воспроизводимости

**Поэтому:**

- **Narrative части (C1, C2) → Qdrant** для объяснений
- **Формулы (C4, C5) → Python Tools** для вычислений
- **Текст C4, C5 в Qdrant опционально** (как справка)

#### Связь с системой

**Важно:** Система использует **два Qdrant namespace:**

- **G1** = Knowledge Base (Block A-F файлы от аудитора) — статичный, заполняется при деплое
- **G1_Client** = Client Documents (TB, invoices, contracts, bank statements) — динамичный, заполняется каждым проектом

| Компонент                      | Block C роль                                   | Откуда данные                                    |
| --------------------------------------- | -------------------------------------------------- | ------------------------------------------------------------ |
| **G2.3 Materiality**              | I1: calculate_materiality()                        | User input +**G1_Client** (TB для Revenue/Assets)   |
| **G2.9 Testing Procedures**       | I2: calculate_sample_size()                        | **G1_Client** (population count из GL/registers)     |
| **G2.10 Exceptions**              | Логика is_misstatement из C5 → Python     | **G1_Client** (invoices/contracts для тестов) |
| **G2.11 SUD**                     | total_unadjusted / compare_to_PM из C5 → Python | G2.10 (exceptions) + G2.3 (PM)                               |
| **Chat intent "A" (Materiality)** | RAG C1 (методология) + Python I1        | **G1** (C1 playbook)                                   |
| **Chat intent "B" (Sampling)**    | RAG C2 (методология) + Python I2        | **G1** (C2 playbook)                                   |

#### Имплементация: Порядок работ

1. **Phase 1: Python Tools (приоритет)**

   - Имплементировать I1: calculate_materiality()
   - Имплементировать I2: calculate_sample_size()
   - Имплементировать I3: assess_legal_matter()
   - Юнит-тесты с примерами из C1/C2
2. **Phase 2: RAG для C1, C2**

   - Векторизовать C1, C2 в Qdrant
   - Chunking по `====` маркерам
   - Metadata: formula_id, method_type
3. **Phase 3 (опционально): Справка по C4, C5**

   - Векторизовать YAML specs в Qdrant
   - **НЕ для расчётов, только для объяснений**

#### Трудозатраты

| Задача                    | Объём                    | Время                |
| ------------------------------- | ----------------------------- | ------------------------- |
| Python Tools I1-I3              | 3 функции + тесты | ~4 часа               |
| Векторизация C1, C2 | 2 файла                  | ~30 мин                |
| Integration тесты          | RAG + Tools                   | ~1 час                 |
| **Итого Phase 1+2**  |                               | **~5.5 часов** |

**Статус:** TODO — имплементация Python Tools перед векторизацией.
