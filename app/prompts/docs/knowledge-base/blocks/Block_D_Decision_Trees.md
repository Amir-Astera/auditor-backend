
## Block D: Decision Trees

**Назначение блока:** Деревья решений для сложных вопросов.

**Хранение:** Qdrant (векторизованы в G1)

| # | Файл                                           | ISA/IFRS                       | Что это                                | Что внутри                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                | Зачем нужен (простыми словами)                                                                                                                                                                                             | Где применяется                     | Статус |
| - | -------------------------------------------------- | ------------------------------ | -------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------- | ------------ |
| 1 | D1_Legal_Matrix_ISA560_501_v1.txt                  | ISA 501/560/250/580, IAS 37/10 | Матрица судебных дел       | **Центральный реестр правовых вопросов:** 1) **Scope:** Litigation & claims, Regulatory investigations, Contract disputes, NOCLAR, Subsequent events, 2) **Identification Channels:** Management inquiry, External counsel letter, BoD/AC minutes, Legal fees GL scan, Regulator correspondence, Press monitoring, 3) **Decision Rules (IAS 37):** Probable→Provision, Possible→Contingent disclosure, Remote→None, 4) **IAS 10:** Adjusting (condition existed at date) vs Non-adjusting events, 5) **Register Template (17+ fields):** ID, Counterparty, Type, Period, Assertions@Risk, Risk Level, Probability, Financial Impact Range, IFRS Ref, Required FS Action, Evidence, ISA Refs, Owner, Status, Through-date, KAM/Forensic/Rep Letter linkages, 6) **Procedures Checklist:** per-matter workflow, 7) **Linkages:** PBC, Management Rep, KAM, Forensic, Materiality | Единый реестр всех судебных/регуляторных дел с автоматическим определением: нужен provision или disclosure, adjusting или non-adjusting, escalate to KAM или нет | G2.12 legal_matters, links to PBC/Rep Letter/KAM  | ✅           |
| 2 | D2_Acceptance_Continuance_ISQM1_ISA220_Tree_v1.txt | ISQM1/ISA 220/210              | Дерево принятия клиента | **Дерево решений (4 узла):** NODE A1: "Independence threats?" → YES=REJECT, NO→A2, NODE A2: "Management integrity concerns (fraud, NOCLAR, reputation)?" → YES=ESCALATE_PARTNER, NO→A3, NODE A3: "Adequate competence & resources?" → YES→A4, NO=PARTNER_DECISION, NODE A4: "ISA 210 preconditions agreed?" → YES=ACCEPT, NO=REJECT. **4 исхода:** ACCEPT_ENGAGEMENT, REJECT_ENGAGEMENT, ESCALATE_FOR_PARTNER_REVIEW, PARTNER_TO_DECIDE                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        | Автоматизация решения "брать клиента или нет": бот задает 4 вопроса по порядку и выводит: Accept/Reject/Escalate                                                             | A3_Acceptance_Routing workflow, Client onboarding | ✅           |
| 3 | D3_Opinion_Decision_Tree_ISA700_705_706_v1.txt     | ISA 700/705/706                | Дерево типа мнения           | **Дерево решений (6 узлов):** **Inputs:** misstatements_material, misstatements_pervasive, scope_limitation_material, scope_limitation_pervasive, going_concern_material_uncertainty. **Flow:** O1: Material misstatements? → YES→O2, NO→O4. O2: Pervasive? → YES=ADVERSE, NO=QUALIFIED. O4: Material scope limitation? → YES→O5, NO→O7. O5: Pervasive? → YES=DISCLAIMER, NO=QUALIFIED. O7: GC uncertainty disclosed? → YES=UNMODIFIED+EOM, NO→O8. O8: GC not disclosed? → YES=ADVERSE/DISCLAIMER, NO=UNMODIFIED. **6 исходов:** Unmodified, Unmodified+EOM, Qualified, Adverse, Disclaimer, Adverse_or_Disclaimer (partner call)                                                                                                                                                                                                                                                                            | Автоматическое определение типа мнения по 5 входным параметрам: material/pervasive misstatements, scope limitations, going concern                                                            | A5_Opinion_Routing, Final opinion output          | ✅           |
| 4 | D4_GoingConcern_Decision_Tree_ISA570_v1.txt        | ISA 570                        | Дерево непрерывности      | **Дерево решений (4 узла):** **Inputs:** indicators_present, management_assessment_prepared, material_uncertainty_exists, disclosure_adequate. **Flow:** G1: Significant GC indicators? → NO=NO_GC_ISSUE, YES→G2. G2: Management assessment prepared? → NO=SCOPE_LIMITATION, YES→G3. G3: Material uncertainty? → NO=NO_MATERIAL_UNCERTAINTY, YES→G4. G4: Disclosure adequate? → YES=EOM_REQUIRED, NO=INADEQUATE_DISCLOSURE. **5 исходов:** No_GC_Issue, Scope_Limitation_or_Deficiency (нужны доп.процедуры), No_Material_Uncertainty (возможен EOM), Material_Uncertainty_Disclosed (EOM обязателен), Inadequate_Disclosure (Qualified/Adverse)                                                                                                                                                                                                                               | Автоматическая оценка: есть ли проблема с непрерывностью? → нужен EOM? → или модификация мнения? Связан с B6 (индикаторы) и D3 (opinion)              | Going Concern assessment, links B6 → D3 opinion  | ✅           |

### Block D: Архитектурное решение (Hybrid: RAG + LLM Reasoning + Python)

**Принцип:** Decision Trees = исполняемая логика, а не просто текст для чтения.

#### Два типа деревьев

| Деревья                             | Сложность                   | Обработка                 | Пример                                                     |
| ------------------------------------------ | ------------------------------------ | ---------------------------------- | ---------------------------------------------------------------- |
| **Простые (D2, D3, D4)**      | 4-6 узлов, чёткие IF/ELSE | RAG G1 + LLM reasoning             | Acceptance (4 узла), Opinion (6 узлов), GC (4 узла) |
| **Сложные (D1 Legal Matrix)** | 17+ полей, IAS 37 logic         | RAG G1 +**Python Tool (I3)** | Legal matter classification                                      |

#### Почему RAG + LLM Reasoning для D2, D3, D4?

**Деревья D2-D4 достаточно простые для LLM:**

- Линейная логика: узел → вопрос → YES/NO → следующий узел
- Нет сложной математики
- LLM с Chain-of-Thought хорошо справляется

**Workflow (D3 Opinion Tree пример):**

```
User: "У нас SUD $240K, PM $300K, pervasive? Нет. Какое мнение?"

→ RAG G1: D3_Opinion_Decision_Tree
→ LLM читает дерево:
  O1: Material misstatements? ($240K < $300K PM) → NO
  O4: Material scope limitation? → NO
  O7: GC uncertainty? → NO
  O8: Final check → NO
  → Outcome: UNMODIFIED

→ LLM: "Unmodified opinion (чистое). SUD ниже PM."
```

**LLM делает traversal дерева сам** — не нужен Python код для простых деревьев.

#### Почему Python Tool для D1 Legal Matrix?

**D1 Legal Matrix — это не дерево, а сложная система правил:**

- IAS 37 logic: Probable/Possible/Remote → Provision/Disclosure/None
- IAS 10 logic: Adjusting vs Non-adjusting
- Materiality check (PM)
- KAM escalation logic
- 17+ полей для оценки

**Слишком сложно для LLM reasoning** → нужна Python функция I3.

#### Python функция I3: assess_legal_matter

Из [03_Functions_I1-I10.md](../components/03_Functions_I1-I10.md):

```python
def assess_legal_matter(
    claim_amount: float,
    probability: str,         # "probable" | "possible" | "remote"
    pm: float,
    outcome_estimable: bool
) -> dict:
    """
    IAS 37 + ISA 501 logic для legal matters.

    Возвращает: {
        "is_material": bool,              # claim_amount vs PM
        "disclosure_required": bool,      # IAS 37.86
        "provision_required": bool,       # IAS 37.14
        "is_kam": bool,                   # ISA 701 (если material + judgment)
        "is_adjusting_event": bool,       # IAS 10 (если подтверждает условие на дату)
        "fs_action": str,                 # "Provision" | "Disclosure" | "None"
        "rationale": str
    }
    """

    # IAS 37 logic
    is_material = claim_amount >= pm

    if probability == "probable" and outcome_estimable:
        provision_required = True
        disclosure_required = True
        fs_action = "Provision"
    elif probability == "possible":
        provision_required = False
        disclosure_required = True
        fs_action = "Contingent Liability Disclosure"
    else:  # remote
        provision_required = False
        disclosure_required = False
        fs_action = "None"

    # KAM escalation
    is_kam = is_material and (
        probability in ["probable", "possible"]
        and claim_amount >= 2 * pm  # critical threshold
    )

    return {
        "is_material": is_material,
        "disclosure_required": disclosure_required,
        "provision_required": provision_required,
        "is_kam": is_kam,
        "fs_action": fs_action,
        "rationale": f"IAS 37: {probability} + estimable={outcome_estimable}"
    }
```

#### RAG конфигурация для Block D

```python
BLOCK_D_RAG_CONFIG = {
    # Chunking Strategy
    "chunk_strategy": "section",       # D1 использует ───── маркеры
    "chunk_size": 1024,
    "chunk_overlap": 0,

    # Retrieval
    "retrieval_top_k": 15,             # меньше файлов чем Block B
    "rerank_top_k": 3,
    "min_similarity": 0.75,            # высокий порог (критические решения)

    # Metadata
    "metadata_fields": [
        "block",           # D
        "file_id",         # D1, D2, D3, D4
        "tree_type",       # acceptance, opinion, gc, legal
        "isa_reference",   # ISA 570, 700, 705, 706, etc.
        "decision_nodes",  # количество узлов
        "outcomes"         # возможные исходы
    ]
}
```

#### Workflow примеры

**Пример 1: D3 Opinion Tree (LLM reasoning)**

```
User: "SUD $250K (PM $300K), pervasive = no, scope issues = no. Мнение?"

→ RAG G1: D3_Opinion_Decision_Tree
→ LLM reasoning (Chain-of-Thought):
  "Checking node O1: Material misstatements?
   SUD $250K < PM $300K → Not material individually
   BUT $250K = 83% of PM → Close, need to check qualitative

   Assuming no qualitative factors → NO material misstatements

   O4: Material scope limitation? → NO
   O7: Going concern uncertainty? → NO

   Final outcome: UNMODIFIED"

→ LLM: "Рекомендация: Unmodified opinion. SUD близко к PM (83%),
        но ниже порога. Убедитесь нет qualitative факторов."
```

**Пример 2: D1 Legal Matrix + I3 Python Tool**

```
User: "Судебное дело на $2M, probability = probable, можем оценить. PM $300K"

→ RAG G1: D1_Legal_Matrix (для контекста IAS 37/ISA 501)
→ LLM calls I3: assess_legal_matter(2000000, "probable", 300000, true)

→ Python returns:
{
  "is_material": true,
  "disclosure_required": true,
  "provision_required": true,
  "is_kam": true,              # $2M > 2×PM
  "fs_action": "Provision",
  "rationale": "IAS 37: probable + estimable=true"
}

→ LLM writes to G2.12 Legal Matters:
  legal_id, claim_amount, probability, provision_required, is_kam, ...

→ LLM: "Provision required: $2M (IAS 37.14). Disclose в notes.
        Escalate to KAM (material + judgment)."
```

**Пример 3: D4 Going Concern + G1_Client**

```
User: "Оцени going concern для клиента"

→ Query G1_Client: "Financial Statements 2024" → парсит indicators
  - Net current liabilities: $5M
  - Negative operating CF: $2M
  - Defaults on loans: Yes

→ RAG G1: B6 (GC indicators) + D4 (GC tree)
→ LLM reasoning:
  G1: Indicators present? → YES (3 financial indicators)
  G2: Management assessment prepared? → Query user

User: "Да, есть CF forecast"

→ LLM: G3: Material uncertainty exists? → Нужен analysis CF forecast
  → Request: "Загрузи CF forecast"

Client uploads → G1_Client

→ LLM analyzes forecast:
  - Breach of covenants in Q2 2025
  - No committed financing
  → Material uncertainty = YES

→ G4: Disclosure adequate?
  → Query FS from G1_Client → finds IAS 1 disclosure
  → YES, disclosed

→ Outcome: EOM_REQUIRED

→ LLM writes to G2.14 (Going Concern table):
  material_uncertainty: true
  disclosure_adequate: true
  eom_required: true

→ LLM: "EOM paragraph required (ISA 570).
        Unmodified opinion + Emphasis of Matter на GC."
```

#### Связь с системой

| Компонент                   | Block D роль                      | Откуда данные                                                   |
| ------------------------------------ | ------------------------------------- | --------------------------------------------------------------------------- |
| **G2.13 Client Acceptance**    | D2 decision tree (4 узла)         | User input (questionnaire)                                                  |
| **G2.12 Legal Matters**        | D1 matrix + I3: assess_legal_matter() | **G1_Client** (legal letters, Board minutes) + User input             |
| **G2.14 Going Concern**        | D4 tree (4 узла)                  | **G1_Client** (FS, CF forecast) + B6 (indicators from G1)             |
| **G2.11 Opinion**              | D3 tree (6 узлов)                | G2.10 (SUD), G2.14 (GC), G2.3 (PM)                                          |
| **Chat intent "E" (Legal/SE)** | RAG D1 + Python I3                    | **G1** (методология) + **G1_Client** (legal letters) |

#### Критический момент: Когда LLM, когда Python?

| Критерий                | LLM Reasoning (RAG)                        | Python Tool                                              |
| ------------------------------- | ------------------------------------------ | -------------------------------------------------------- |
| **Логика**          | Простая, линейная (IF/ELSE) | Сложная, вложенная, математика |
| **Узлов**            | 4-6 узлов                             | 10+ узлов или 17+ полей                     |
| **Стандарты**    | Один (ISA 570, ISA 700)                | Комбо (IAS 37 + IAS 10 + ISA 501)                   |
| **Примеры**        | D2, D3, D4                                 | D1 Legal Matrix                                          |
| **Риск ошибки** | Низкий (LLM хорош в reasoning) | Высокий (нужна гарантия)             |

**Golden Rule:** Если дерево влияет на финальное мнение (D3 Opinion, D4 GC→Opinion) — можно LLM. Если влияет на финансовые показатели (D1 Provision) — лучше Python.

#### Имплементация: Порядок работ

1. **Phase 1: RAG для D2, D3, D4**

   - Векторизовать в G1 Qdrant
   - Chunking по секциям (D1 использует `─────`, остальные по заголовкам)
   - Metadata: tree_type, decision_nodes, outcomes
   - Тесты: LLM правильно traverses деревья
2. **Phase 2: Python Tool для D1**

   - Имплементировать I3: assess_legal_matter()
   - Юнит-тесты: probable/possible/remote scenarios
   - Integration тест: I3 + G2.12 Legal Matters
3. **Phase 3: Integration с G2**

   - D2 → G2.13 Client Acceptance
   - D1 → G2.12 Legal Matters
   - D4 → G2.14 Going Concern
   - D3 → G2.11 Opinion

#### Трудозатраты

| Задача                   | Объём                    | Время              |
| ------------------------------ | ----------------------------- | ----------------------- |
| Векторизация D1-D4 | 4 файла                  | ~30 мин              |
| Python Tool I3                 | 1 функция + тесты | ~2 часа             |
| LLM reasoning тесты       | D2, D3, D4 traversal          | ~1 час               |
| Integration G2                 | 4 таблицы              | ~1.5 часа           |
| **Итого**           |                               | **~5 часов** |

**Статус:** TODO — Phase 1 (RAG) можно начинать параллельно с Block C Python Tools.

---
