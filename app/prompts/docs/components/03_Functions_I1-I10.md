# Python Functions (I1-I10)

> [← Intents](./02_Intents_J1-J20.md) | [Response →](./04_Response_H1-H5.md)

---

## Overview

Бизнес-логика вынесена в Python функции. LLM НЕ делает расчёты — только вызывает функции.

---

## Functions List

| ID | Function | Input | Output |
|----|----------|-------|--------|
| I1 | `calculate_materiality()` | benchmark, value, risk | {om, pm, ct, rationale} |
| I2 | `calculate_sample_size()` | population, pm, errors | {size, method} |
| I3 | `assess_legal_matter()` | amount, probability, pm | {is_kam, provision} |
| I4 | `save_materiality()` | project_id, data | DB record |
| I5 | `add_risk()` | project_id, risk_data | DB record |
| I6 | `add_legal_matter()` | project_id, legal_data | DB record |
| I7 | `generate_document()` | template, data | DOCX/PDF |
| I8 | `search_knowledge()` | query | {chunks, sources} |
| I9 | `get_project_context()` | project_id | {project, risks, warnings} |
| I10 | `get_pbc_status()` | project_id | {items, stats} |

---

## I1: calculate_materiality

**ISA 320** — Расчёт существенности

```python
def calculate_materiality(
    benchmark: Literal["revenue", "assets", "equity", "profit"],
    benchmark_value: float,
    risk_level: Literal["low", "normal", "high"] = "normal"
) -> dict:
    """
    Benchmark rates:
    - Revenue: 0.5% - 2%
    - Total Assets: 0.5% - 1%
    - Equity: 2% - 5%
    - Profit before tax: 5% - 10%

    PM = 50-75% of OM (based on risk)
    CT = 3-5% of OM
    """
    RATES = {
        "revenue": (0.005, 0.02),
        "assets": (0.005, 0.01),
        "equity": (0.02, 0.05),
        "profit": (0.05, 0.10)
    }

    PM_RATES = {"low": 0.75, "normal": 0.65, "high": 0.50}
    CT_RATE = 0.05

    min_rate, max_rate = RATES[benchmark]
    mid_rate = (min_rate + max_rate) / 2

    om = benchmark_value * mid_rate
    pm = om * PM_RATES[risk_level]
    ct = om * CT_RATE

    return {
        "benchmark": benchmark,
        "benchmark_value": benchmark_value,
        "om": round(om, 2),
        "pm": round(pm, 2),
        "ct": round(ct, 2),
        "risk_level": risk_level,
        "rationale": f"OM = {benchmark_value:,.0f} × {mid_rate:.1%} = {om:,.0f}"
    }
```

---

## I2: calculate_sample_size

**ISA 530** — Расчёт выборки

```python
def calculate_sample_size(
    population_size: int,
    pm: float,
    expected_errors: int = 0,
    confidence_level: float = 0.95
) -> dict:
    """
    Methods:
    - Statistical sampling
    - MUS (Monetary Unit Sampling)
    - Non-statistical
    """
    # Simplified calculation
    confidence_factor = {0.90: 2.31, 0.95: 3.0, 0.99: 4.61}

    sample_size = int((confidence_factor[confidence_level] * population_size) / pm)
    sample_size = min(sample_size, population_size)

    return {
        "population_size": population_size,
        "sample_size": sample_size,
        "method": "statistical",
        "confidence_level": confidence_level
    }
```

---

## I3: assess_legal_matter

**ISA 501 + IAS 37** — Оценка судебных дел

```python
def assess_legal_matter(
    claim_amount: float,
    probability: Literal["remote", "possible", "probable"],
    pm: float,
    outcome_estimable: bool = True
) -> dict:
    """
    Decision matrix:
    - Remote: No disclosure, no provision
    - Possible + Material: Disclosure required
    - Probable + Estimable: Provision required
    - Probable + Not estimable: Disclosure only
    """
    is_material = claim_amount >= pm

    result = {
        "claim_amount": claim_amount,
        "probability": probability,
        "is_material": is_material,
        "disclosure_required": False,
        "provision_required": False,
        "is_kam": False,
        "rationale": ""
    }

    if probability == "remote":
        result["rationale"] = "Remote probability — no action required"

    elif probability == "possible":
        if is_material:
            result["disclosure_required"] = True
            result["rationale"] = "Possible + Material — disclose as contingent liability"

    elif probability == "probable":
        if outcome_estimable:
            result["provision_required"] = True
            result["rationale"] = "Probable + Estimable — recognize provision"
        else:
            result["disclosure_required"] = True
            result["rationale"] = "Probable + Not estimable — disclose range"

        if is_material:
            result["is_kam"] = True
            result["rationale"] += " | KAM candidate"

    return result
```

---

## I4-I6: Save Functions

**Важно:** Все функции сохранения требуют `confirmed_by`!

```python
async def save_materiality(
    project_id: UUID,
    data: MaterialityData,
    confirmed_by: UUID  # ОБЯЗАТЕЛЬНО!
) -> MaterialityRecord:
    """
    Сохраняет расчёт существенности.
    LLM НИКОГДА не вызывает напрямую — только через H2 кнопку.
    """
    record = Materiality(
        project_id=project_id,
        benchmark=data.benchmark,
        benchmark_value=data.benchmark_value,
        om=data.om,
        pm=data.pm,
        ct=data.ct,
        risk_level=data.risk_level,
        rationale=data.rationale,
        confirmed_by=confirmed_by,
        confirmed_at=datetime.utcnow()
    )
    await db.add(record)
    return record
```

---

## I7: generate_document

```python
async def generate_document(
    template_id: str,  # E1, E2, E3...
    data: dict,
    output_format: Literal["docx", "pdf"] = "docx"
) -> str:
    """
    Генерирует документ по шаблону.
    Returns: MinIO path to generated file
    """
    template = load_template(template_id)
    rendered = render_template(template, data)
    file_path = save_to_minio(rendered, output_format)
    return file_path
```

---

## I8: search_knowledge

```python
async def search_knowledge(
    query: str,
    filters: Optional[dict] = None,
    limit: int = 5
) -> dict:
    """
    RAG search через LightRAG.
    """
    results = await rag_engine.search(
        query=query,
        filters=filters,
        limit=limit
    )
    return {
        "chunks": results.chunks,
        "sources": results.sources,
        "scores": results.scores
    }
```

---

## I9-I10: Context Functions

```python
async def get_project_context(project_id: UUID) -> dict:
    """
    Возвращает полный контекст проекта для LLM.
    """
    project = await get_project(project_id)
    materiality = await get_latest_materiality(project_id)
    risks = await get_risks(project_id)

    return {
        "project": project,
        "materiality": materiality,
        "risks": risks,
        "warnings": generate_warnings(project)
    }

async def get_pbc_status(project_id: UUID) -> dict:
    """
    Статус запрошенных документов (PBC).
    """
    items = await get_pbc_items(project_id)
    return {
        "items": items,
        "stats": {
            "total": len(items),
            "pending": count_by_status(items, "pending"),
            "received": count_by_status(items, "received"),
            "overdue": count_overdue(items)
        }
    }
```

---

## File Structure

```
/functions/
├── materiality.py     # I1: calculate_materiality
├── sampling.py        # I2: calculate_sample_size
├── legal.py           # I3: assess_legal_matter
├── context.py         # I9: get_project_context
└── validators.py      # Input validation
```

---

## Related Docs

- [Response H1-H5](./04_Response_H1-H5.md) — Как результаты форматируются
- [Database Schema](../database/01_Schema.md) — Где сохраняются данные
