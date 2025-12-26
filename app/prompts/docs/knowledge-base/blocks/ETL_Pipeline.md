
## ETL Pipeline & Data Unification (G2 Extension)

**Назначение:** Унификация клиентских данных на входе для упрощения работы с Block E (Templates).

**Проблема:** Без унификации каждый шаблон должен парсить G1_Client (векторизованные chunks) ЗАНОВО → сложные mappers, долгая разработка.

**Решение:** ETL Pipeline при загрузке файла → структурированные таблицы в G2 → простые SQL mappers.

---

### Архитектура: 3 копии клиентских данных

```
┌─────────────────────────────────────────────────────────────┐
│ USER UPLOADS FILE (TB.xlsx, GL.csv, Sales.xlsx)           │
└──────────────────────┬──────────────────────────────────────┘
                       ↓
         ┌─────────────────────────┐
         │   ETL PIPELINE          │
         │  (File Processor)       │
         └─────┬──────┬──────┬─────┘
               │      │      │
       ┌───────┘      │      └──────┐
       ↓              ↓             ↓
┌───────────┐  ┌──────────┐  ┌────────────┐
│ G3 MinIO  │  │ G2 PG    │  │ G1_Client  │
│ (Original)│  │(Unified) │  │ Qdrant     │
│           │  │          │  │ (RAG)      │
│ TB.xlsx   │  │ G2.20_TB │  │ chunks     │
└───────────┘  └──────┬───┘  └────────────┘
                      │
                      ↓
              ┌───────────────┐
              │ MAPPER        │
              │ (Simple SQL)  │
              └───────┬───────┘
                      ↓
              ┌───────────────┐
              │ TEMPLATE      │
              │ (Jinja2)      │
              └───────────────┘
```

**Зачем 3 копии:**

| Хранилище         | Формат                    | Назначение                                                                    |
| -------------------------- | ------------------------------- | --------------------------------------------------------------------------------------- |
| **G3 MinIO**         | Оригинал (xlsx/csv/pdf) | Архив, audit trail, скачивание пользователем                |
| **G2 PostgreSQL**    | Structured tables               | **Быстрые SQL запросы для шаблонов** ← основное |
| **G1_Client Qdrant** | Vectorized chunks               | RAG для свободного чата ("покажи все инвойсы > 100K")  |

---

### G2 Extension: Новые таблицы для клиентских данных

#### G2.20: Trial Balance (унифицированная)

```sql
CREATE TABLE G2_20_trial_balance (
    id SERIAL PRIMARY KEY,
    project_id INT REFERENCES G2_1_projects(id),
    account_code VARCHAR(50) NOT NULL,
    account_name VARCHAR(200) NOT NULL,
    debit DECIMAL(15,2) DEFAULT 0,
    credit DECIMAL(15,2) DEFAULT 0,
    balance DECIMAL(15,2) NOT NULL,
    account_type VARCHAR(50),  -- Asset/Liability/Revenue/Expense/Equity
    uploaded_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT unique_account_per_project UNIQUE(project_id, account_code)
);

-- Индексы для быстрых запросов
CREATE INDEX idx_tb_project ON G2_20_trial_balance(project_id);
CREATE INDEX idx_tb_account_type ON G2_20_trial_balance(account_type);
```

**Назначение:** Унифицированный TB независимо от формата загрузки клиента.

**Используется в шаблонах:**

- E5 Audit Report (извлечение Revenue/Assets для цифр)
- E13 AR Testing (AR balance)
- E30 Disclosure Checklist (проверка структуры FS)

---

#### G2.21: General Ledger (унифицированный)

```sql
CREATE TABLE G2_21_general_ledger (
    id SERIAL PRIMARY KEY,
    project_id INT REFERENCES G2_1_projects(id),
    entry_date DATE NOT NULL,
    entry_number VARCHAR(50) NOT NULL,
    account_code VARCHAR(50) NOT NULL,
    description TEXT,
    debit DECIMAL(15,2) DEFAULT 0,
    credit DECIMAL(15,2) DEFAULT 0,
    is_manual BOOLEAN DEFAULT FALSE,  -- для JE testing (ISA 240)
    is_period_end BOOLEAN DEFAULT FALSE,  -- для period-end JE testing
    posted_by VARCHAR(100),
    uploaded_at TIMESTAMP DEFAULT NOW()
);

-- Индексы
CREATE INDEX idx_gl_project ON G2_21_general_ledger(project_id);
CREATE INDEX idx_gl_manual ON G2_21_general_ledger(is_manual) WHERE is_manual = TRUE;
CREATE INDEX idx_gl_period_end ON G2_21_general_ledger(is_period_end) WHERE is_period_end = TRUE;
CREATE INDEX idx_gl_date ON G2_21_general_ledger(entry_date);
```

**Назначение:** Унифицированный GL для JE testing и substantive tests.

**Критично для:**

- E11 Journal Entry Testing (manual entries, period-end entries)
- E18 Revenue Testing (sales transactions)

---

#### G2.22: Sales Register (унифицированный)

```sql
CREATE TABLE G2_22_sales_register (
    id SERIAL PRIMARY KEY,
    project_id INT REFERENCES G2_1_projects(id),
    invoice_number VARCHAR(50) NOT NULL,
    invoice_date DATE NOT NULL,
    customer_name VARCHAR(200) NOT NULL,
    customer_code VARCHAR(50),
    amount DECIMAL(15,2) NOT NULL,
    vat_amount DECIMAL(15,2) DEFAULT 0,
    total_amount DECIMAL(15,2) NOT NULL,
    payment_status VARCHAR(50),  -- Paid/Unpaid/Partial
    uploaded_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT unique_invoice_per_project UNIQUE(project_id, invoice_number)
);

-- Индексы
CREATE INDEX idx_sales_project ON G2_22_sales_register(project_id);
CREATE INDEX idx_sales_date ON G2_22_sales_register(invoice_date);
CREATE INDEX idx_sales_customer ON G2_22_sales_register(customer_name);
```

**Назначение:** Унифицированный Sales Register для revenue testing.

**Используется в:**

- E12 Revenue Testing (sample selection, cutoff testing)

---

#### G2.23: AR Register (унифицированный)

```sql
CREATE TABLE G2_23_ar_register (
    id SERIAL PRIMARY KEY,
    project_id INT REFERENCES G2_1_projects(id),
    customer_name VARCHAR(200) NOT NULL,
    customer_code VARCHAR(50),
    invoice_number VARCHAR(50) NOT NULL,
    invoice_date DATE NOT NULL,
    due_date DATE,
    amount DECIMAL(15,2) NOT NULL,
    outstanding_balance DECIMAL(15,2) NOT NULL,
    days_overdue INT DEFAULT 0,
    uploaded_at TIMESTAMP DEFAULT NOW()
);

-- Индексы
CREATE INDEX idx_ar_project ON G2_23_ar_register(project_id);
CREATE INDEX idx_ar_customer ON G2_23_ar_register(customer_name);
CREATE INDEX idx_ar_overdue ON G2_23_ar_register(days_overdue);
```

**Назначение:** Унифицированный AR Register для confirmations и aging analysis.

**Используется в:**

- E13 Accounts Receivable (confirmation selection, aging)
- E21 AR Circularization (sample selection)

---

### ETL Pipeline: Workflow при загрузке файла

```python
# etl/file_processor.py

class FileProcessor:
    """
    Обрабатывает загрузку клиентских файлов и унифицирует данные.
    """

    def process_upload(self, file, project_id: str, file_type: str):
        """
        file_type: 'trial_balance' | 'general_ledger' | 'sales_register' | 'ar_register'

        Workflow:
        1. Сохранить оригинал в MinIO (G3)
        2. Парсинг и нормализация
        3. Загрузка в G2 (structured)
        4. Векторизация для G1_Client (RAG)
        """

        # Step 1: Сохранить оригинал
        minio_path = f"project_{project_id}/originals/{file.filename}"
        minio_client.put_object(minio_path, file)

        # Step 2 & 3: Парсинг + загрузка в G2
        if file_type == 'trial_balance':
            df = self._parse_trial_balance(file)
            self._load_to_g2_20(df, project_id)

        elif file_type == 'general_ledger':
            df = self._parse_general_ledger(file)
            self._load_to_g2_21(df, project_id)

        elif file_type == 'sales_register':
            df = self._parse_sales_register(file)
            self._load_to_g2_22(df, project_id)

        elif file_type == 'ar_register':
            df = self._parse_ar_register(file)
            self._load_to_g2_23(df, project_id)

        # Step 4: Векторизация для RAG
        chunks = self._chunk_dataframe(df, file_type)
        qdrant_client.upload_points(
            collection='G1_Client',
            points=chunks,
            metadata={
                'project_id': project_id,
                'file_type': file_type,
                'original_file': minio_path
            }
        )

        return {
            'status': 'success',
            'minio_path': minio_path,
            'rows_loaded': len(df),
            'g2_table': f'G2_{self._get_table_number(file_type)}'
        }
```

---

### Парсинг и нормализация: Ключевая сложность

#### Проблема: Разные форматы от клиентов

**Пример: Trial Balance**

| Клиент A | Клиент B      | Клиент C |
| -------------- | ------------------- | -------------- |
| "Account Code" | "Код счета" | "Acc#"         |
| "Debit"        | "Дебет"        | "Dr"           |
| "Credit"       | "Кредит"      | "Cr"           |

#### Решение: Column mapping с фоллбеками

```python
def _parse_trial_balance(self, file) -> pd.DataFrame:
    """
    Унифицирует любой формат TB в стандартную схему G2.20.
    """
    # Загрузка файла
    if file.filename.endswith('.xlsx'):
        df = pd.read_excel(file)
    elif file.filename.endswith('.csv'):
        df = pd.read_csv(file)
    else:
        raise ValueError(f"Unsupported format: {file.filename}")

    # Нормализация названий колонок (с фоллбеками)
    column_mapping = {
        # Account Code
        'Account Code': 'account_code',
        'Код счета': 'account_code',
        'Acc#': 'account_code',
        'Account': 'account_code',
        'Счет': 'account_code',

        # Account Name
        'Account Name': 'account_name',
        'Наименование счета': 'account_name',
        'Name': 'account_name',
        'Наименование': 'account_name',

        # Debit
        'Debit': 'debit',
        'Дебет': 'debit',
        'Dr': 'debit',
        'Дт': 'debit',

        # Credit
        'Credit': 'credit',
        'Кредит': 'credit',
        'Cr': 'credit',
        'Кт': 'credit',
    }

    df = df.rename(columns=column_mapping)

    # Валидация обязательных колонок
    required = ['account_code', 'account_name', 'debit', 'credit']
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    # Расчёт balance
    df['debit'] = pd.to_numeric(df['debit'], errors='coerce').fillna(0)
    df['credit'] = pd.to_numeric(df['credit'], errors='coerce').fillna(0)
    df['balance'] = df['debit'] - df['credit']

    # Определение типа счета (упрощённо, по номеру счета)
    df['account_type'] = df['account_code'].apply(self._classify_account_type)

    return df[['account_code', 'account_name', 'debit', 'credit', 'balance', 'account_type']]

def _classify_account_type(self, account_code: str) -> str:
    """
    Классифицирует счёт по типу на основе кода.
    Упрощённая логика (для производственных систем нужна таблица соответствий).
    """
    code = str(account_code)

    # Стандартная нумерация IFRS/IAS
    if code.startswith('1'):
        return 'Asset'
    elif code.startswith('2'):
        return 'Liability'
    elif code.startswith('3'):
        return 'Equity'
    elif code.startswith('4'):
        return 'Revenue'
    elif code.startswith('5') or code.startswith('6'):
        return 'Expense'
    else:
        return 'Other'
```

---

### Сравнение: ДО vs ПОСЛЕ унификации

#### ДО (без ETL):

**Mapper для E12 Revenue Testing:**

```python
# Сложный mapper (6-8 часов разработки)
def get_sales_data(project_id: str) -> pd.DataFrame:
    # 1. RAG query в G1_Client
    query = f"Retrieve Sales Register for project {project_id}"
    chunks = qdrant_client.search(collection='G1_Client', query=query)

    # 2. Парсинг chunks (формат неизвестен!)
    if chunks[0].metadata['format'] == 'csv':
        df = parse_csv_from_text(chunks[0].text)
    elif chunks[0].metadata['format'] == 'xlsx':
        # Нужно достать оригинал из MinIO
        file = minio_client.get_object(chunks[0].metadata['file_path'])
        df = pd.read_excel(file)

    # 3. Нормализация колонок (угадай названия!)
    df = df.rename(columns={
        'Invoice No': 'invoice_number',
        # ... или 'Inv#'? или '№'?
    })

    # 4. Фильтрация, валидация
    # ...

    return df
```

**Время:**

- Разработка: 6-8 часов
- Runtime: 15 секунд (парсинг каждый раз)

---

#### ПОСЛЕ (с ETL):

**Mapper для E12 Revenue Testing:**

```python
# Простой mapper (30 минут разработки)
def get_sales_data(project_id: str) -> pd.DataFrame:
    query = """
        SELECT
            invoice_number,
            invoice_date,
            customer_name,
            total_amount
        FROM G2_22_sales_register
        WHERE project_id = %s
        ORDER BY invoice_date
    """
    return pd.read_sql(query, conn, params=[project_id])
```

**Время:**

- Разработка: 30 минут
- Runtime: 2 секунды (SQL query)

---

### Обновлённые сроки разработки Block E

#### MVP шаблоны (8 штук) - с учётом ETL

| Шаблон         | Категория | Template → Jinja2 | Schema  | **Mapper (SQL)**   | Testing | Итого     |
| -------------------- | ------------------ | ------------------ | ------- | ------------------------ | ------- | -------------- |
| E3 Engagement Letter | Простой     | 2h (AI)            | 1h (AI) | **30 мин**      | 1h      | **4.5h** |
| E4 Rep Letter        | Простой     | 2h                 | 1h      | **1h**             | 1h      | **5h**   |
| E6 Management Letter | Простой     | 2h                 | 1h      | **30 мин**      | 1h      | **4.5h** |
| E5 Audit Report      | Средний     | 3h                 | 2h      | **1h** (SQL + TB)  | 2h      | **8h**   |
| E18 Materiality      | Средний     | 3h                 | 2h      | **1h**             | 2h      | **8h**   |
| E21 AR Circ          | Средний     | 3h                 | 2h      | **1h**             | 2h      | **8h**   |
| E11 JE Testing       | Сложный     | 4h                 | 2h      | **2h** (SQL GL)    | 3h      | **11h**  |
| E12 Revenue          | Сложный     | 4h                 | 2h      | **2h** (SQL Sales) | 3h      | **11h**  |

**Итого MVP:**

- Простые: 14h (было 16h)
- Средние: 24h (было 30h)
- Сложные: 22h (было 34h)
- **Всего: 60 часов = 7-8 рабочих дней** (было 80 часов = 10 дней)

**Экономия:** 20 часов = 2-3 дня на MVP.

**Но:** Нужно добавить время на ETL Pipeline разработку.

---

### Трудозатраты ETL Pipeline

| Задача                                 | Время                               |
| -------------------------------------------- | ---------------------------------------- |
| G2 schema extension (4 таблицы)       | 2 часа                               |
| FileProcessor base class                     | 4 часа                               |
| Trial Balance parser                         | 6 часов (самый сложный) |
| General Ledger parser                        | 4 часа                               |
| Sales Register parser                        | 3 часа                               |
| AR Register parser                           | 3 часа                               |
| UI integration (upload flow)                 | 4 часа                               |
| Testing с реальными файлами | 6 часов                             |
| **Итого ETL Pipeline**            | **32 часа = 4 дня**         |

**Общий план:**

1. **ETL Pipeline:** 4 дня (делается 1 раз)
2. **MVP шаблоны:** 8 дней (с простыми SQL mappers)
3. **Итого MVP:** **12 дней** (было 23 дня без ETL)

**Экономия на полном Block E (41 шаблон):**

- Без ETL: ~82 дня
- С ETL: 4 дня (ETL) + ~35 дней (шаблоны) = **39 дней**
- **Экономия: 43 дня ≈ 2 месяца**

---

### Альтернативы PostgreSQL

#### ClickHouse (OLAP для больших данных)

**Когда нужен:**

- GL > 10M строк (крупные банки/телеком)
- Нужны быстрые агрегации

**Плюсы:**

- Очень быстрые аналитические запросы
- Колоночное хранение (экономия места)

**Минусы:**

- Сложнее в администрировании
- Overkill для 90% аудитов

**Рекомендация:** Phase 2+, только если клиенты - enterprise с огромными данными.

---

#### DuckDB (embedded OLAP)

**Когда нужен:**

- Локальная работа аудиторов (offline)
- Средние объёмы (до 10M строк)

**Плюсы:**

- Не нужен отдельный сервер
- Понимает Excel/CSV/Parquet из коробки

**Минусы:**

- Файл на диске (не центральная БД)
- Сложнее для multi-user

**Рекомендация:** Интересная альтернатива, но для MVP лучше PostgreSQL (уже есть).

---

#### Parquet в MinIO

**Когда нужен:**

- Максимальная простота (нет новой БД)

**Плюсы:**

- Простейшая реализация

**Минусы:**

- Нет SQL
- Медленнее PostgreSQL

**Рекомендация:** Только если хочется избежать G2 extension (не рекомендуется).

---

### Итоговая рекомендация

**Для MVP: PostgreSQL G2 Extension**

**Почему:**

- ✅ Уже есть в архитектуре
- ✅ SQL для гибких запросов
- ✅ ACID транзакции
- ✅ Multi-user
- ✅ Достаточно для 99% аудитов (< 10M строк)

**Когда расширять:**

- Phase 2+: ClickHouse для enterprise клиентов
- Или DuckDB для offline режима
