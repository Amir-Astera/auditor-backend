# 🛠️ Implementation Guide

## 1. Python Tools для расчётов (приоритет)

```python
# src/tools/materiality.py

def calculate_materiality(
    benchmark: str,           # "Revenue" | "PBT" | "Assets" | "Equity"
    benchmark_value: float,
    risk_level: str,          # "High" | "Moderate" | "Low"
    is_pie: bool
) -> dict:
    """
    ISA 320 materiality calculation.

    Benchmark rates:
    - Revenue: 0.5% - 1.5%
    - PBT: 5% - 10%
    - Assets: 0.5% - 2%
    - Equity: 2% - 5%
    """
    # Базовые ставки
    rates = {
        "Revenue": {"High": 0.005, "Moderate": 0.01, "Low": 0.015},
        "PBT": {"High": 0.05, "Moderate": 0.075, "Low": 0.10},
        "Assets": {"High": 0.005, "Moderate": 0.01, "Low": 0.02},
        "Equity": {"High": 0.02, "Moderate": 0.03, "Low": 0.05}
    }

    om_rate = rates[benchmark][risk_level]
    om = benchmark_value * om_rate

    # Performance Materiality (60-75% of OM)
    pm_rates = {"High": 0.60, "Moderate": 0.65, "Low": 0.75}
    pm = om * pm_rates[risk_level]

    # Clearly Trivial Threshold (3-5% of OM)
    ct = om * 0.03

    return {
        "om": round(om, 2),
        "pm": round(pm, 2),
        "ct": round(ct, 2),
        "benchmark": benchmark,
        "rate": om_rate,
        "rationale": f"{benchmark} {om_rate*100}% for {'PIE' if is_pie else 'non-PIE'} {risk_level} risk"
    }
```

```python
# src/tools/sampling.py

def calculate_sample_size(
    population_size: int,
    pm: float,
    expected_error_rate: float = 0.0,
    confidence_level: float = 0.95
) -> dict:
    """
    ISA 530 sample size calculation (MUS method).
    """
    import math

    # Риск-фактор для 95% confidence
    risk_factor = 3.0 if confidence_level == 0.95 else 2.3

    # Sampling Interval
    si = pm / risk_factor

    # Sample size
    sample_size = math.ceil(population_size / si)

    return {
        "sample_size": sample_size,
        "method": "MUS",
        "sampling_interval": round(si, 2),
        "confidence": confidence_level,
        "risk_factor": risk_factor
    }
```

## 2. PostgreSQL таблицы

```sql
-- Materiality расчёты
CREATE TABLE materiality (
    materiality_id SERIAL PRIMARY KEY,
    project_id VARCHAR(50) REFERENCES projects(project_id),
    benchmark VARCHAR(50),
    benchmark_value NUMERIC(15,2),
    om NUMERIC(15,2),
    pm NUMERIC(15,2),
    ct NUMERIC(15,2),
    rationale TEXT,
    confirmed_by VARCHAR(100),
    confirmed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Sampling планы
CREATE TABLE testing_procedures (
    procedure_id VARCHAR(50) PRIMARY KEY,
    project_id VARCHAR(50) REFERENCES projects(project_id),
    area VARCHAR(100),
    test_type VARCHAR(20),  -- 'ToC' | 'SAP' | 'ToD'
    sample_size INT,
    method VARCHAR(50),     -- 'MUS' | 'Attribute' | 'Variables'
    status VARCHAR(20) DEFAULT 'Planned',
    created_at TIMESTAMP DEFAULT NOW()
);
```

## 3. H2 Buttons для расчётов

```python
# Response с подтверждением
return {
    "response": "Materiality рассчитан:\n- OM: $500K\n- PM: $350K\n- CT: $15K",
    "buttons": [
        {
            "label": "Сохранить",
            "action": "save-materiality",
            "data": {
                "benchmark": "Revenue",
                "om": 500000,
                "pm": 350000,
                "ct": 15000
            }
        },
        {
            "label": "Пересчитать",
            "action": "recalculate"
        }
    ]
}
```

## 4. RAG для методологий C1, C2

```python
# Векторизация только C1, C2 (narrative playbooks)
BLOCK_C_RAG_FILES = [
    "C1_Materiality_Playbook_v1.1.txt",
    "C2_Sampling_Methods_ISA530_v1.txt"
]

# C4, C5 - только Python Tools, НЕ векторизуем
```

## 5. TODO для разработчика

- [ ] Имплементировать `calculate_materiality()` в `src/tools/materiality.py`
- [ ] Имплементировать `calculate_sample_size()` в `src/tools/sampling.py`
- [ ] Создать таблицы `materiality` и `testing_procedures` в PostgreSQL
- [ ] Написать юнит-тесты с примерами из C1/C2 playbooks
- [ ] Интеграция H2 buttons для user confirmation
- [ ] Векторизовать C1, C2 в Qdrant (опционально для справки)

**Приоритет:** P1 (критический - формулы должны работать точно)

## 6. Связанные документы

- G2 PostgreSQL Schema — таблицы materiality, testing_procedures
- Development Rules — Python Tools for calculations
- Functions I1-I10 — спецификация всех Python tools
