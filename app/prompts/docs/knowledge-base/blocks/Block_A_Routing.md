# Block A: Routing (System Prompts)

**Назначение блока:** Файлы которые идут прямо в промпт LLM. Определяют стиль ответов, логику маршрутизации запросов.

**Хранение:** In Prompt (не векторизуются)

**Архитектурное решение:** Загружаются ВСЕ 6 файлов ВСЕГДА (~6,000 токенов)

- **Принцип:** Надёжность > Экономия. Аудит не прощает ошибок.
- **Core (всегда нужны):** A1 StyleGuide, A2 RoutingPrompts, A6 Model IO Guide
- **Workflow (тоже всегда):** A3 Acceptance, A4 Understanding, A5 Opinion
- **Почему не по фазам:** Риск пропустить нужный контекст > экономия токенов

---

## Файлы Block A

| # | Файл                               | Что это                                    | Что внутри                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             | Зачем нужен (простыми словами)                                                                                                                                                                                                           | Где применяется                                                                   | Статус |
| - | -------------------------------------- | ------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------- | ------------ |
| 1 | A1_StyleGuide_v1.txt                   | Гайд по стилю                         | **Единый стиль для всех выходов:** 1) McKinsey-clarity (signal>noise, короткие предложения), 2) Таблицы > текст, bullets > проза, 3) Языки: ответ на языке юзера, внешние доки→EN, RU summary опционально, 4) Числа/даты/валюты (USD 1.25m, YYYY-MM-DD), 5) Структура документов (Title→Outcome→Context→Method→Findings→Actions), 6) Acceptance tests для таблиц, 7) Micro-libraries (готовые фразы для Materiality/Sampling/Legal/KAM/TCWG), 8) Quality Gates B4-level                                                          | Чтобы ВСЕ ответы бота были: audit-grade, copy-paste ready в Word/Excel, с единой терминологией ISA/IFRS, структурированы как в Big4                                                                 | Системный промпт LLM — применяется к каждому ответу    | ✅           |
| 2 | A2_ISA_RoutingPrompts_v1.txt           | Роутер намерений                  | **Главный маршрутизатор модели:** 1) 12 классов интентов (A-L): Planning/Materiality, Sampling, Risk, Cycle Deep-Dive (Revenue/Inventory/Leases и др.), Legal/SE, KAM, TCWG, PBC, Forensic, Translation, Disclosures, Model Ops, 2) Routing Map — какой output pack для какого интента, 3) Router Prompts (RP-*) — внутренние промпты для каждого маршрута, 4) Keywords EN/RU для детекции, 5) Ambiguity Handling (3 тира), 6) 6 Few-Shot примеров, 7) Safety Guardrails                                                                                                     | **Критически важный!** Определяет как бот понимает запрос и какие файлы/шаблоны подключать. Приоритет: Legal→KAM→TCWG→FS                                              | Системный промпт LLM — классификация каждого запроса | ✅           |
| 3 | A3_Acceptance_Routing_v1.txt           | Воркфлоу принятия клиента | **Роутинг для acceptance/continuance:** 1) Input fields: client_name, status (New/Continuing), framework (IFRS/Local GAAP), period_end, entity_type (PIE/Non-PIE), prior_auditor, prior_opinion, 2) 7 Core Questions (задает бот если данных нет), 3) Decision Logic: independence conflict→DECLINE, integrity concerns→ESCALATE, ok→ACCEPTANCE_MEMO, 4) JSON output для записи в БД                                                                                                                                                                                                                                                                       | Проверка "можем ли взять клиента?" при создании проекта. Выявляет конфликты интересов, проблемы с integrity руководства                                                | Создание проекта в User Panel → workflow J11                                   | ⏳           |
| 4 | A4_Understanding_Entity_Routing_v1.txt | Понимание клиента                | **Роутинг для ISA 315 (Understanding the Entity):** 1) Input fields: industry, business_model, key_revenue_streams, key_cost_drivers, key_processes, it_environment, internal_control, 2) 6 Questions: отрасль, как генерится выручка, ключевые процессы (sales/purchases/payroll), сложные транзакции, IT системы, контрольная среда, 3) JSON output → link_to_risks: true → J2_RISK                                                                                                                                                                                                                                       | Сбор полной картины о бизнесе клиента ПЕРЕД оценкой рисков. Бот спрашивает про бизнес-модель, IT, контроли                                                                  | Этап Planning → связь с Risk Assessment (J2)                                         | ⏳           |
| 5 | A5_Opinion_Routing_v1.txt              | Дерево мнений                        | **Роутинг для определения типа заключения (ISA 700/705/706):** 1) Input fields: misstatements_total, misstatements_unadjusted, performance_materiality, pervasive_effect, going_concern_issue, scope_limitation, 2) 5 Questions: материальные искажения? pervasive? going concern? раскрыто? ограничения объема?, 3) Logic: нет проблем→Unmodified, есть→Qualified/Adverse/Disclaimer, 4) JSON → next_block: J20_REPORT. Детальное дерево в D3                                                                                                                                          | Определить какое заключение выдавать: Unmodified (чистое), Qualified (с оговоркой), Adverse (отрицательное), Disclaimer (отказ)                                                                | Этап Completion → Report (J20)                                                             | ⏳           |
| 6 | A6_Model_IO_Guide_v1.txt               | Правила ввода-вывода           | **"Операционная система" модели:** 1) Input Classification (Drafting/Planning/Legal/Analytics/Forensic/Translation), 2) Canonical Output Schemas: Executive (Title→Outcome→Context→Method→Findings→Actions), Table, Template, Calculation, Email, 3) Quality Gates B4: Relevance, Traceability, Acceptance tests, No hallucinations, 4) Decision Trees (недост.данных→Assumptions, KAM?, IAS 37, Sampling), 5) Chunking Protocol для больших ответов, 6) Standard Tables (Action Tracker, PBC Wave, Legal Matrix, KAM One-Pager, SUM), 7) **Macros:** GEN::PBC, GEN::KAM, GEN::LEGAL, GEN::TCWG, GEN::MATERIALITY, GEN::SAMPLE и др. | **Критически важный!** Определяет КАК модель обрабатывает запросы и выдает результат. Все ответы должны быть production-ready, с cross-refs к файлам 01-14 | Системный промпт LLM — применяется к каждому ответу    | ✅           |

---

## Имплементация

### prompt_builder.py

```python
# src/core/prompt_builder.py

BLOCK_A_FILES = [
    "A1_StyleGuide_v1.txt",
    "A2_ISA_RoutingPrompts_v1.txt",
    "A3_Acceptance_Routing_v1.txt",
    "A4_Understanding_Entity_Routing_v1.txt",
    "A5_Opinion_Routing_v1.txt",
    "A6_Model_IO_Guide_v1.txt"
]

def build_system_prompt() -> str:
    """
    Загружает все файлы Block A в System Prompt.

    Returns:
        str: Полный системный промпт (~6,000 токенов)
    """
    sections = []

    for filename in BLOCK_A_FILES:
        content = load_file(filename)
        sections.append(f"# {filename}\n\n{content}")

    return "\n\n---\n\n".join(sections)

def load_file(filename: str) -> str:
    """Загружает файл из knowledge-base/."""
    path = f"knowledge-base/{filename}"
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()
```

---

## Почему ВСЕ файлы ВСЕГДА в промпте

### Аргументы ПРОТИВ условной загрузки

| Аргумент за условную | Контраргумент |
|---------------------|---------------|
| Экономия 4K токенов | При 128K context window — несущественно |
| Меньше "шума" | LLM сам фильтрует нерелевантное |
| Быстрее | Разница ~50ms — незаметно |

### Риски условной загрузки

1. **Неверно определена фаза** → неверный контекст → ошибка
2. **Переход между фазами** → пропущен нужный файл
3. **Сложность кода** → больше багов

### Итог

**Block A = 6 файлов = ~6,000 токенов = ВСЕГДА в System Prompt**

Это "мозг" системы. Экономить на мозге — плохая идея.

---

## Связь с другими блоками

| Файл Block A | Ссылается на | Зачем |
|--------------|--------------|-------|
| A2 RoutingPrompts | B1-B8 (Libraries) | Определяет какую библиотеку искать в RAG |
| A2 RoutingPrompts | C1-C5 (Formulas) | Routing к Python Tools для расчётов |
| A2 RoutingPrompts | E1-E41 (Templates) | Определяет какой шаблон генерировать |
| A5 Opinion Routing | D3 (Opinion Tree) | Детальное дерево решений для мнения |
| A6 Model IO Guide | Вся Knowledge Base | Определяет как структурировать выходы |

---

## Статус

| Компонент | Статус | Примечание |
|-----------|--------|------------|
| Файлы A1, A2, A6 | ✅ Готовы | Core функциональность |
| Файлы A3, A4, A5 | ⏳ В разработке | Workflow routing (нужна интеграция с G2) |
| prompt_builder.py | ✅ Готов | Код простой, реализация 1 час |
