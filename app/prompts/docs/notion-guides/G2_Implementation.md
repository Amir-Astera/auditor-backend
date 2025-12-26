# 🛠️ Implementation Guide

## 1. PostgreSQL Setup (Alembic migrations)

```python
# alembic/env.py

from sqlalchemy import create_engine
from alembic import context
import os

DATABASE_URL = os.getenv("DATABASE_URL")

def run_migrations():
    """Apply all migrations to create G2 schema"""
    engine = create_engine(DATABASE_URL)

    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=metadata
        )

        with context.begin_transaction():
            context.run_migrations()
```

```bash
# Create initial migration
alembic revision --autogenerate -m "Create G2 schema"

# Apply migrations
alembic upgrade head
```

## 2. Core Tables (критичные)

```sql
-- G2.1 Projects
CREATE TABLE projects (
    project_id VARCHAR(50) PRIMARY KEY,
    client_name VARCHAR(255),
    fiscal_year INT,
    engagement_type VARCHAR(50),
    is_pie BOOLEAN,
    risk_level VARCHAR(20),
    status VARCHAR(50) DEFAULT 'Active',
    created_at TIMESTAMP DEFAULT NOW()
);

-- G2.3 Materiality
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

-- G2.9 Testing Procedures
CREATE TABLE testing_procedures (
    procedure_id VARCHAR(50) PRIMARY KEY,
    project_id VARCHAR(50) REFERENCES projects(project_id),
    area VARCHAR(100),
    test_type VARCHAR(20),
    description TEXT,
    sample_size INT,
    status VARCHAR(20) DEFAULT 'Planned',
    created_at TIMESTAMP DEFAULT NOW()
);

-- G2.10 Exceptions
CREATE TABLE exceptions (
    exception_id SERIAL PRIMARY KEY,
    procedure_id VARCHAR(50) REFERENCES testing_procedures(procedure_id),
    exception_desc TEXT,
    amount NUMERIC(15,2),
    is_misstatement BOOLEAN,
    resolution TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- G2.11 Summary of Unadjusted Differences (SUD)
CREATE TABLE sud (
    sud_id SERIAL PRIMARY KEY,
    project_id VARCHAR(50) REFERENCES projects(project_id),
    area VARCHAR(100),
    misstatement_type VARCHAR(50),  -- factual, judgmental, projected
    amount NUMERIC(15,2),
    is_adjusted BOOLEAN DEFAULT FALSE,
    rationale TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);
```

## 3. SQLAlchemy Models

```python
# src/models/project.py

from sqlalchemy import Column, String, Integer, Boolean, TIMESTAMP, Numeric
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class Project(Base):
    __tablename__ = "projects"

    project_id = Column(String(50), primary_key=True)
    client_name = Column(String(255))
    fiscal_year = Column(Integer)
    engagement_type = Column(String(50))
    is_pie = Column(Boolean)
    risk_level = Column(String(20))
    status = Column(String(50), default="Active")
    created_at = Column(TIMESTAMP)

class Materiality(Base):
    __tablename__ = "materiality"

    materiality_id = Column(Integer, primary_key=True)
    project_id = Column(String(50), ForeignKey("projects.project_id"))
    benchmark = Column(String(50))
    benchmark_value = Column(Numeric(15, 2))
    om = Column(Numeric(15, 2))
    pm = Column(Numeric(15, 2))
    ct = Column(Numeric(15, 2))
    rationale = Column(String)
    confirmed_by = Column(String(100))
    confirmed_at = Column(TIMESTAMP)
    created_at = Column(TIMESTAMP)
```

## 4. Async Database Operations

```python
# src/db/operations.py

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.future import select

async_engine = create_async_engine(
    "postgresql+asyncpg://user:pass@localhost/odi",
    echo=True
)

async def save_materiality(data: dict):
    """Save materiality calculation to G2.3"""
    async with AsyncSession(async_engine) as session:
        materiality = Materiality(
            project_id=data["project_id"],
            benchmark=data["benchmark"],
            om=data["om"],
            pm=data["pm"],
            ct=data["ct"],
            rationale=data["rationale"],
            confirmed_by=data["confirmed_by"]
        )

        session.add(materiality)
        await session.commit()

async def get_project_materiality(project_id: str):
    """Retrieve materiality for project"""
    async with AsyncSession(async_engine) as session:
        result = await session.execute(
            select(Materiality).filter_by(project_id=project_id)
        )
        return result.scalar_one_or_none()
```

## 5. H2 Buttons Integration

```python
# После расчёта materiality, LLM возвращает:

return {
    "response": "Materiality рассчитан",
    "buttons": [
        {
            "label": "Сохранить",
            "action": "save-materiality",
            "data": {
                "project_id": "PRJ-001",
                "benchmark": "Revenue",
                "om": 500000,
                "pm": 350000,
                "ct": 15000,
                "rationale": "Revenue 0.5% for PIE High risk"
            }
        }
    ]
}

# User clicks "Сохранить" → backend calls:
await save_materiality(button_data)
```

## 6. Indexes для Performance

```sql
-- Критичные indexes
CREATE INDEX idx_materiality_project ON materiality(project_id);
CREATE INDEX idx_procedures_project ON testing_procedures(project_id);
CREATE INDEX idx_exceptions_procedure ON exceptions(procedure_id);
CREATE INDEX idx_sud_project ON sud(project_id);

-- Composite indexes
CREATE INDEX idx_procedures_status ON testing_procedures(project_id, status);
CREATE INDEX idx_sud_type ON sud(project_id, misstatement_type);
```

## 7. TODO для разработчика

- [ ] Установить PostgreSQL 15
- [ ] Создать database `odi`
- [ ] Настроить Alembic migrations
- [ ] Создать все таблицы G2.1-G2.23 (23 таблицы)
- [ ] Имплементировать async SQLAlchemy models
- [ ] Создать критичные indexes
- [ ] Написать тесты для async CRUD operations
- [ ] Интеграция с H2 buttons (confirmed_by field)

**Приоритет:** P1 (критический - persistent storage)

## 8. Связанные документы

- G1 Qdrant Design — vector + relational hybrid
- Development Rules — Async DB calls, H2 Buttons
- Functions I1-I10 — Python tools writing to G2
