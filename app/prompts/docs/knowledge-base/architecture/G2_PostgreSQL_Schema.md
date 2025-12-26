# G2: PostgreSQL Schema

**Назначение:** Реляционное хранилище структурированных данных для проектов и клиентских документов.

**Критическое различие:** G2.1-19 (project data) + G2.20-23 (ETL unified client data).

---

## Две части схемы

| Диапазон  | Что хранит                  | Когда заполняется           | Обновления |
|-----------|-----------------------------|-----------------------------|------------|
| **G2.1-19** | Проектные данные (Materiality, Risks, Testing, Opinion) | В процессе аудита | Часто (по мере работы) |
| **G2.20-23** | Unified клиентские данные (TB, GL, Sales, AR) | При загрузке файлов (ETL) | Редко (только re-upload) |

**Почему разделение:**
1. **G2.1-19:** Создаются аудиторами вручную → нормализованная структура
2. **G2.20-23:** Заполняются ETL Pipeline → унифицированная структура для упрощения Mappers

---

## G2.1-19: Project Tables

### G2.1: Projects (Master table)

```sql
CREATE TABLE G2_1_projects (
    id SERIAL PRIMARY KEY,
    project_code VARCHAR(50) UNIQUE NOT NULL,
    client_name VARCHAR(200) NOT NULL,
    fiscal_year_end DATE NOT NULL,
    engagement_partner VARCHAR(100),
    audit_status VARCHAR(50) DEFAULT 'planning',  -- planning|fieldwork|reporting|completed
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_projects_status ON G2_1_projects(audit_status);
CREATE INDEX idx_projects_fiscal_year ON G2_1_projects(fiscal_year_end);
```

---

### G2.2: Users

```sql
CREATE TABLE G2_2_users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    email VARCHAR(200) UNIQUE NOT NULL,
    role VARCHAR(50) NOT NULL,  -- partner|manager|senior|assistant
    created_at TIMESTAMP DEFAULT NOW()
);
```

---

### G2.3: Materiality

```sql
CREATE TABLE G2_3_materiality (
    id SERIAL PRIMARY KEY,
    project_id INT REFERENCES G2_1_projects(id) ON DELETE CASCADE,
    benchmark VARCHAR(50) NOT NULL,  -- revenue|assets|equity|pretax_income
    benchmark_value DECIMAL(15,2) NOT NULL,
    risk_level VARCHAR(50) NOT NULL,  -- low|moderate|high
    overall_materiality DECIMAL(15,2) NOT NULL,  -- OM
    performance_materiality DECIMAL(15,2) NOT NULL,  -- PM
    clearly_trivial_threshold DECIMAL(15,2) NOT NULL,  -- CTT
    rationale TEXT,
    calculated_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT unique_materiality_per_project UNIQUE(project_id)
);
```

---

### G2.4: Risks (ISA 315 identified risks)

```sql
CREATE TABLE G2_4_risks (
    id SERIAL PRIMARY KEY,
    project_id INT REFERENCES G2_1_projects(id) ON DELETE CASCADE,
    risk_id VARCHAR(50) NOT NULL,  -- RR-001, FR-001, etc.
    risk_type VARCHAR(50) NOT NULL,  -- inherent|control|fraud
    cycle VARCHAR(100),  -- Revenue|Inventory|Fixed_Assets|etc.
    description TEXT NOT NULL,
    likelihood VARCHAR(50),  -- low|medium|high
    impact VARCHAR(50),  -- low|medium|high
    is_significant BOOLEAN DEFAULT FALSE,
    response_plan TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_risks_project ON G2_4_risks(project_id);
CREATE INDEX idx_risks_cycle ON G2_4_risks(cycle);
```

---

### G2.5: Controls (ISA 315 controls)

```sql
CREATE TABLE G2_5_controls (
    id SERIAL PRIMARY KEY,
    project_id INT REFERENCES G2_1_projects(id) ON DELETE CASCADE,
    control_id VARCHAR(50) NOT NULL,
    risk_id VARCHAR(50),  -- Links to G2.4.risk_id
    control_type VARCHAR(50),  -- preventive|detective|automated|manual
    description TEXT NOT NULL,
    frequency VARCHAR(50),  -- daily|weekly|monthly|annual
    design_effective BOOLEAN,
    implementation_effective BOOLEAN,
    tested BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_controls_project ON G2_5_controls(project_id);
```

---

### G2.6: Audit Procedures (ISA 330 responses)

```sql
CREATE TABLE G2_6_audit_procedures (
    id SERIAL PRIMARY KEY,
    project_id INT REFERENCES G2_1_projects(id) ON DELETE CASCADE,
    procedure_code VARCHAR(50) NOT NULL,
    risk_id VARCHAR(50),  -- Links to G2.4.risk_id
    procedure_type VARCHAR(50),  -- substantive|test_of_controls|analytical
    assertion VARCHAR(100),  -- existence|completeness|valuation|rights_obligations|presentation
    description TEXT NOT NULL,
    expected_evidence TEXT,
    performed_by INT REFERENCES G2_2_users(id),
    status VARCHAR(50) DEFAULT 'planned',  -- planned|in_progress|completed
    conclusion TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_procedures_project ON G2_6_audit_procedures(project_id);
CREATE INDEX idx_procedures_status ON G2_6_audit_procedures(status);
```

---

### G2.7: Sampling (ISA 530)

```sql
CREATE TABLE G2_7_sampling (
    id SERIAL PRIMARY KEY,
    project_id INT REFERENCES G2_1_projects(id) ON DELETE CASCADE,
    test_area VARCHAR(100) NOT NULL,  -- Revenue|AR|Inventory|etc.
    population_size INT NOT NULL,
    sample_size INT NOT NULL,
    sampling_method VARCHAR(50),  -- MUS|stratified|random|systematic
    selection_criteria TEXT,
    confidence_level DECIMAL(5,2) DEFAULT 95.00,
    expected_error_rate DECIMAL(5,2) DEFAULT 0.00,
    calculated_at TIMESTAMP DEFAULT NOW()
);
```

---

### G2.8: Testing Results

```sql
CREATE TABLE G2_8_testing_results (
    id SERIAL PRIMARY KEY,
    project_id INT REFERENCES G2_1_projects(id) ON DELETE CASCADE,
    procedure_id INT REFERENCES G2_6_audit_procedures(id),
    sample_item VARCHAR(200),  -- Invoice #, JE #, etc.
    test_date DATE,
    result VARCHAR(50),  -- passed|failed|not_applicable
    deviation_description TEXT,
    deviation_amount DECIMAL(15,2),
    is_material BOOLEAN DEFAULT FALSE,
    follow_up_action TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_testing_project ON G2_8_testing_results(project_id);
CREATE INDEX idx_testing_result ON G2_8_testing_results(result);
```

---

### G2.9: Exceptions (ISA 450 misstatements)

```sql
CREATE TABLE G2_9_exceptions (
    id SERIAL PRIMARY KEY,
    project_id INT REFERENCES G2_1_projects(id) ON DELETE CASCADE,
    exception_id VARCHAR(50) NOT NULL,
    exception_type VARCHAR(50),  -- factual|judgmental|projected
    account VARCHAR(200),
    amount DECIMAL(15,2) NOT NULL,
    description TEXT NOT NULL,
    is_material BOOLEAN DEFAULT FALSE,
    management_response TEXT,
    adjusted BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_exceptions_project ON G2_9_exceptions(project_id);
CREATE INDEX idx_exceptions_material ON G2_9_exceptions(is_material);
```

---

### G2.10: SUD (Summary of Unadjusted Differences)

```sql
CREATE TABLE G2_10_sud (
    id SERIAL PRIMARY KEY,
    project_id INT REFERENCES G2_1_projects(id) ON DELETE CASCADE,
    exception_id INT REFERENCES G2_9_exceptions(id),
    account_code VARCHAR(50),
    account_name VARCHAR(200),
    debit_adjustment DECIMAL(15,2) DEFAULT 0,
    credit_adjustment DECIMAL(15,2) DEFAULT 0,
    cumulative_impact DECIMAL(15,2),
    exceeds_pm BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);
```

---

### G2.11: Opinion (ISA 700-706)

```sql
CREATE TABLE G2_11_opinion (
    id SERIAL PRIMARY KEY,
    project_id INT REFERENCES G2_1_projects(id) ON DELETE CASCADE,
    opinion_type VARCHAR(50) NOT NULL,  -- unmodified|qualified|adverse|disclaimer
    basis_for_modification TEXT,
    emphasis_of_matter TEXT,
    key_audit_matters TEXT,  -- JSON array of KAM descriptions
    issued_date DATE,
    created_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT unique_opinion_per_project UNIQUE(project_id)
);
```

---

### G2.12: Legal Matters (ISA 501/560, IAS 37)

```sql
CREATE TABLE G2_12_legal_matters (
    id SERIAL PRIMARY KEY,
    project_id INT REFERENCES G2_1_projects(id) ON DELETE CASCADE,
    matter_id VARCHAR(50) NOT NULL,
    description TEXT NOT NULL,
    counterparty VARCHAR(200),
    matter_type VARCHAR(50),          -- litigation|regulatory|contract|noclar
    claim_amount DECIMAL(15,2),
    probability VARCHAR(50),          -- probable|possible|remote
    outcome_estimable BOOLEAN,
    is_material BOOLEAN,
    disclosure_required BOOLEAN,
    provision_required BOOLEAN,
    provision_amount DECIMAL(15,2),
    is_kam BOOLEAN DEFAULT FALSE,
    is_adjusting_event BOOLEAN,       -- IAS 10
    assessed_by INT REFERENCES G2_2_users(id),
    assessed_at TIMESTAMP DEFAULT NOW(),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_legal_project ON G2_12_legal_matters(project_id);
CREATE INDEX idx_legal_material ON G2_12_legal_matters(is_material);
```

**Применение:** D1 Legal Matrix tree → запись результатов assess_legal_matter()

---

### G2.13: Client Acceptance (ISQM 1, ISA 220)

```sql
CREATE TABLE G2_13_client_acceptance (
    id SERIAL PRIMARY KEY,
    project_id INT REFERENCES G2_1_projects(id) ON DELETE CASCADE,
    assessment_date DATE NOT NULL,
    integrity_check BOOLEAN,           -- D2 node A2: Management integrity
    competence_check BOOLEAN,          -- D2 node A3: Adequate resources
    independence_confirmed BOOLEAN,    -- D2 node A1: Independence threats
    preconditions_agreed BOOLEAN,      -- D2 node A4: ISA 210 preconditions
    decision VARCHAR(50),              -- accept|reject|escalate|partner_decision
    conditions TEXT,
    escalation_reason TEXT,
    assessed_by INT REFERENCES G2_2_users(id),
    created_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT unique_acceptance_per_project UNIQUE(project_id)
);

CREATE INDEX idx_acceptance_project ON G2_13_client_acceptance(project_id);
CREATE INDEX idx_acceptance_decision ON G2_13_client_acceptance(decision);
```

**Применение:** D2 Acceptance tree → запись результатов принятия клиента

---

### G2.14-19: Additional tables (placeholders)

```sql
-- G2.14: Going Concern (ISA 570) - для D4 GC tree
-- G2.15: Subsequent Events (ISA 560)
-- G2.16: Related Parties (ISA 550)
-- G2.17: Accounting Estimates (ISA 540)
-- G2.18: Fair Value (ISA 540)
-- G2.19: Group Audits (ISA 600)
```

*(Полные схемы — по необходимости в Phase 2)*

---

## G2.20-23: ETL Unified Tables

### G2.20: Trial Balance

```sql
CREATE TABLE G2_20_trial_balance (
    id SERIAL PRIMARY KEY,
    project_id INT REFERENCES G2_1_projects(id) ON DELETE CASCADE,
    account_code VARCHAR(50) NOT NULL,
    account_name VARCHAR(200) NOT NULL,
    debit DECIMAL(15,2) DEFAULT 0,
    credit DECIMAL(15,2) DEFAULT 0,
    balance DECIMAL(15,2) NOT NULL,
    account_type VARCHAR(50),  -- asset|liability|equity|revenue|expense
    fs_line_item VARCHAR(200),  -- Mapping to FS disclosure
    uploaded_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT unique_account_per_project UNIQUE(project_id, account_code)
);

CREATE INDEX idx_tb_project ON G2_20_trial_balance(project_id);
CREATE INDEX idx_tb_type ON G2_20_trial_balance(account_type);
```

**Результат ETL:** Любой формат TB (Excel, CSV, PDF) → унифицированная таблица.

---

### G2.21: General Ledger

```sql
CREATE TABLE G2_21_general_ledger (
    id SERIAL PRIMARY KEY,
    project_id INT REFERENCES G2_1_projects(id) ON DELETE CASCADE,
    entry_number VARCHAR(50),
    entry_date DATE NOT NULL,
    account_code VARCHAR(50) NOT NULL,
    account_name VARCHAR(200),
    description TEXT,
    debit DECIMAL(15,2) DEFAULT 0,
    credit DECIMAL(15,2) DEFAULT 0,
    posted_by VARCHAR(100),
    is_manual_entry BOOLEAN DEFAULT FALSE,  -- Для JE testing
    uploaded_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_gl_project ON G2_21_general_ledger(project_id);
CREATE INDEX idx_gl_date ON G2_21_general_ledger(entry_date);
CREATE INDEX idx_gl_manual ON G2_21_general_ledger(is_manual_entry);
```

**Применение:** ISA 240 Journal Entry Testing (фильтр: `is_manual_entry = TRUE` + unusual accounts).

---

### G2.22: Sales Register

```sql
CREATE TABLE G2_22_sales_register (
    id SERIAL PRIMARY KEY,
    project_id INT REFERENCES G2_1_projects(id) ON DELETE CASCADE,
    invoice_number VARCHAR(50) NOT NULL,
    invoice_date DATE NOT NULL,
    customer_name VARCHAR(200) NOT NULL,
    customer_code VARCHAR(50),
    total_amount DECIMAL(15,2) NOT NULL,
    vat_amount DECIMAL(15,2),
    payment_terms VARCHAR(100),
    payment_status VARCHAR(50),  -- paid|unpaid|partial
    uploaded_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT unique_invoice_per_project UNIQUE(project_id, invoice_number)
);

CREATE INDEX idx_sales_project ON G2_22_sales_register(project_id);
CREATE INDEX idx_sales_date ON G2_22_sales_register(invoice_date);
```

**Применение:** Revenue Testing (E12), Cut-off Testing.

---

### G2.23: AR Register

```sql
CREATE TABLE G2_23_ar_register (
    id SERIAL PRIMARY KEY,
    project_id INT REFERENCES G2_1_projects(id) ON DELETE CASCADE,
    customer_name VARCHAR(200) NOT NULL,
    customer_code VARCHAR(50),
    invoice_number VARCHAR(50),
    invoice_date DATE,
    due_date DATE,
    outstanding_amount DECIMAL(15,2) NOT NULL,
    aging_days INT,  -- Days overdue
    aging_category VARCHAR(50),  -- current|30-60|60-90|90+
    uploaded_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_ar_project ON G2_23_ar_register(project_id);
CREATE INDEX idx_ar_aging ON G2_23_ar_register(aging_category);
```

**Применение:** Accounts Receivable Testing (E13), External Confirmations.

---

## Foreign Keys & Constraints

### Key relationships

```
G2.1 Projects (1) ←→ (N) G2.3-11, G2.20-23
G2.4 Risks (1) ←→ (N) G2.5 Controls
G2.4 Risks (1) ←→ (N) G2.6 Procedures
G2.6 Procedures (1) ←→ (N) G2.8 Testing Results
G2.9 Exceptions (1) ←→ (N) G2.10 SUD
```

### Cascade rules

- **DELETE CASCADE:** При удалении проекта → удаляются все связанные данные
- **UPDATE RESTRICT:** Нельзя изменить project_id у существующих записей

---

## Indexes Strategy

### Critical indexes (performance)

```sql
-- Most queried: project_id
CREATE INDEX idx_X_project ON G2_X_table(project_id);

-- Filtering: status, types
CREATE INDEX idx_procedures_status ON G2_6_audit_procedures(status);
CREATE INDEX idx_risks_cycle ON G2_4_risks(cycle);

-- ETL tables: dates for cut-off testing
CREATE INDEX idx_gl_date ON G2_21_general_ledger(entry_date);
CREATE INDEX idx_sales_date ON G2_22_sales_register(invoice_date);
```

---

## Migration Strategy

### Initial schema deployment

```sql
-- Version 1.0: Core tables (G2.1-11)
CREATE MIGRATION '2025_01_core_schema';

-- Version 1.1: ETL extension (G2.20-23)
CREATE MIGRATION '2025_02_etl_tables';

-- Version 2.0: Additional modules (G2.12-19)
CREATE MIGRATION '2025_03_additional_modules';
```

### Data migration from legacy

```python
# Legacy → G2 migration script
def migrate_project(legacy_id: str):
    # 1. Create G2.1 project
    project = create_project(legacy_data)

    # 2. Migrate materiality
    migrate_materiality(legacy_id, project.id)

    # 3. Migrate risks & procedures
    migrate_risks_and_procedures(legacy_id, project.id)

    # 4. Re-run ETL for client docs
    trigger_etl_pipeline(project.id)
```

---

## Storage Estimates

### Per project (average)

| Таблица       | Строк | Размер   |
|---------------|-------|----------|
| G2.1 Projects | 1     | 1 KB     |
| G2.3-11       | ~500  | 150 KB   |
| **G2.20 TB**  | ~300  | 50 KB    |
| **G2.21 GL**  | ~5,000 | 800 KB  |
| **G2.22 Sales** | ~1,200 | 200 KB |
| **G2.23 AR**  | ~800  | 120 KB   |
| **Итого**     |       | **~1.3 MB** |

### 100 projects

- Core data: 100 × 150 KB = 15 MB
- ETL data: 100 × 1.15 MB = 115 MB
- **Total:** ~130 MB (с indexes: ~200 MB)

**PostgreSQL tier:** Free tier (до 10GB) подходит для MVP.

---

## Связанные документы

- [G1: Qdrant Design](G1_Qdrant_Design.md)
- [G3: MinIO Structure](G3_MinIO_Structure.md)
- [ETL Pipeline](../blocks/ETL_Pipeline.md)
- [Block E: Templates](../blocks/Block_E_Templates.md)
