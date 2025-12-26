# G3: MinIO Structure

**Назначение:** Объектное хранилище для файлов (templates, client uploads, generated outputs).

**Критическое различие:** Три типа данных — KB templates (статичные), client uploads (входящие), outputs (генерированные).

---

## Bucket Structure

```
oson-storage/
├── knowledge-base/           # Статичные KB templates (Block E)
│   ├── templates/
│   │   ├── E01_TOR.docx
│   │   ├── E02_Engagement_Letter.docx
│   │   ├── E03_Risk_Assessment.docx
│   │   └── ... (41 файл)
│   └── schemas/              # JSON schemas для template mappers
│       ├── E01_schema.json
│       ├── E02_schema.json
│       └── ...
│
├── projects/                 # Per-project хранилище
│   ├── PRJ-001/
│   │   ├── uploads/          # Оригинальные файлы клиента
│   │   │   ├── TB_2024.xlsx
│   │   │   ├── GL_2024.csv
│   │   │   ├── Sales_Register.xlsx
│   │   │   └── ...
│   │   ├── outputs/          # Сгенерированные документы
│   │   │   ├── Engagement_Letter_v1.docx
│   │   │   ├── Risk_Assessment_v2.pdf
│   │   │   └── ...
│   │   └── working-papers/   # Рабочие документы (WP)
│   │       ├── WP_Revenue_Testing.xlsx
│   │       └── ...
│   ├── PRJ-002/
│   └── ...
│
└── temp/                     # Временные файлы (TTL 24h)
    ├── pending_uploads/
    └── processing/
```

---

## Bucket Configuration

### knowledge-base bucket

```json
{
  "bucket": "knowledge-base",
  "region": "us-east-1",
  "versioning": false,
  "lifecycle": {
    "rules": []
  },
  "access": "read-only",
  "encryption": "AES256"
}
```

**Назначение:** Хранение статичных шаблонов Block E.

**Обновления:** Только при релизе новых версий KB (раз в квартал).

---

### projects bucket

```json
{
  "bucket": "projects",
  "region": "us-east-1",
  "versioning": true,
  "lifecycle": {
    "rules": [
      {
        "id": "temp-files-cleanup",
        "prefix": "temp/",
        "expiration_days": 1
      },
      {
        "id": "archive-old-projects",
        "prefix": "*/",
        "transition_to_glacier_days": 365
      }
    ]
  },
  "access": "private",
  "encryption": "AES256"
}
```

**Назначение:** Хранение клиентских файлов и сгенерированных документов.

**Lifecycle:**
- `temp/` → удаляется через 24 часа
- Проекты старше 1 года → архив (Glacier)

---

## Naming Conventions

### Template files (knowledge-base/)

```
Format: {Block}{Number}_{Template_Name}_{Version}.{ext}

Examples:
- E01_TOR_v1.docx
- E12_Revenue_Testing_v2.xlsx
- E30_Disclosure_Checklist_v1.pdf
```

**Правила:**
- Только латиница, цифры, `_`, `-`
- Версионирование: `_v1`, `_v2`, `_v3`
- Расширения: `.docx`, `.xlsx`, `.pdf`

---

### Client uploads (projects/{project_id}/uploads/)

```
Format: {Document_Type}_{Fiscal_Year}_{Upload_Date}.{ext}

Examples:
- TB_2024_20250115.xlsx
- GL_2024_20250115.csv
- Sales_Register_2024_20250116.xlsx
- AR_Aging_2024_20250116.xlsx
```

**Правила:**
- `{Upload_Date}`: YYYYMMDD
- Сохраняем оригинальное расширение
- Если повторный upload → timestamp: `TB_2024_20250115_143022.xlsx`

---

### Generated outputs (projects/{project_id}/outputs/)

```
Format: {Template_Name}_{Fiscal_Year}_v{Version}_{Generated_Date}.{ext}

Examples:
- Engagement_Letter_2024_v1_20250118.docx
- Risk_Assessment_2024_v2_20250119.pdf
- Revenue_Testing_Program_2024_v1_20250120.docx
```

**Правила:**
- `{Version}`: инкрементируется при регенерации
- `{Generated_Date}`: YYYYMMDD
- Формат выхода: `.docx` (Word), `.pdf` (final)

---

## File Metadata

### Standard metadata (все файлы)

```json
{
  "Content-Type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "x-amz-meta-project-id": "PRJ-001",
  "x-amz-meta-uploaded-by": "user@example.com",
  "x-amz-meta-upload-timestamp": "2025-01-15T10:30:00Z",
  "x-amz-meta-file-category": "upload|output|template",
  "x-amz-meta-original-filename": "Trial_Balance_2024.xlsx"
}
```

---

### Template-specific metadata

```json
{
  "x-amz-meta-template-id": "E12",
  "x-amz-meta-template-version": "v2",
  "x-amz-meta-schema-path": "knowledge-base/schemas/E12_schema.json",
  "x-amz-meta-required-tables": "G2.22_sales_register,G2.9_testing"
}
```

**Применение:** Document Generator использует `schema-path` для маппинга данных.

---

### Client upload metadata

```json
{
  "x-amz-meta-document-type": "trial_balance",
  "x-amz-meta-fiscal-year": "2024",
  "x-amz-meta-etl-status": "processed|pending|failed",
  "x-amz-meta-g2-table": "G2.20_trial_balance",
  "x-amz-meta-g1-vectorized": "true"
}
```

**Применение:** ETL Pipeline обновляет `etl-status` после обработки.

---

## Access Control (IAM)

### Roles

```json
{
  "roles": [
    {
      "name": "ODI-Backend",
      "permissions": ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"],
      "buckets": ["knowledge-base/*", "projects/*"]
    },
    {
      "name": "ODI-User",
      "permissions": ["s3:GetObject", "s3:PutObject"],
      "buckets": ["projects/{user_project_id}/*"]
    },
    {
      "name": "ODI-Admin",
      "permissions": ["s3:*"],
      "buckets": ["*"]
    }
  ]
}
```

**Project isolation:** User может читать/писать только в `projects/PRJ-XXX/` где он owner.

---

### Pre-signed URLs

```python
# Generate pre-signed URL for client download
def generate_download_url(project_id: str, file_path: str, expiry: int = 3600):
    """
    Генерирует временную ссылку для скачивания файла.

    Args:
        project_id: ID проекта (для проверки прав)
        file_path: Путь к файлу в MinIO
        expiry: Время жизни ссылки (секунды)

    Returns:
        Pre-signed URL (expires in 1 hour)
    """
    return minio_client.presigned_get_object(
        bucket_name="projects",
        object_name=f"{project_id}/outputs/{file_path}",
        expires=timedelta(seconds=expiry)
    )
```

**Результат:** User получает ссылку на 1 час для скачивания без прямого доступа к MinIO.

---

## Storage Estimates

### Knowledge Base (static)

| Категория | Файлов | Средний размер | Итого |
|-----------|--------|----------------|-------|
| Templates (DOCX) | 41 | 100 KB | 4.1 MB |
| Schemas (JSON) | 41 | 5 KB | 205 KB |
| **Total KB** | 82 | — | **~4.3 MB** |

---

### Per Project (dynamic)

| Категория | Файлов | Средний размер | Итого |
|-----------|--------|----------------|-------|
| Uploads | 5-10 | 500 KB | 2.5-5 MB |
| Outputs | 8-15 | 200 KB | 1.6-3 MB |
| Working Papers | 3-5 | 300 KB | 0.9-1.5 MB |
| **Total per project** | 16-30 | — | **~5-10 MB** |

---

### 100 Projects

- KB: 4.3 MB (одноразово)
- Projects: 100 × 7.5 MB = 750 MB
- **Total:** ~750 MB

**MinIO pricing:**
- Self-hosted: Free (storage cost only)
- MinIO Cloud: $0.02/GB/month → ~$0.015/month для 750 MB

---

## Versioning Strategy

### Templates (knowledge-base/)

**Стратегия:** Semantic versioning при обновлении KB.

```
E12_Revenue_Testing_v1.docx  → Initial release
E12_Revenue_Testing_v2.docx  → Updated ISA 240 requirements (breaking change)
E12_Revenue_Testing_v2.1.docx → Minor fix (typo correction)
```

**Хранение:** Только последняя версия (старые → архив).

---

### Outputs (projects/{id}/outputs/)

**Стратегия:** Auto-increment при регенерации.

```python
def generate_output_filename(template_name: str, project_id: str) -> str:
    """
    Генерирует имя файла с автоинкрементом версии.

    Example:
        Engagement_Letter_2024_v1_20250118.docx
        Engagement_Letter_2024_v2_20250119.docx  # Regenerated
    """
    existing_files = minio_client.list_objects(
        bucket_name="projects",
        prefix=f"{project_id}/outputs/{template_name}"
    )

    versions = [int(re.search(r'_v(\d+)_', f.object_name).group(1))
                for f in existing_files]
    next_version = max(versions, default=0) + 1

    date = datetime.now().strftime('%Y%m%d')
    return f"{template_name}_2024_v{next_version}_{date}.docx"
```

**Хранение:** Все версии сохраняются (для audit trail).

---

## Backup & Disaster Recovery

### Backup strategy

```yaml
Frequency: Daily (00:00 UTC)
Retention:
  - Daily backups: 7 days
  - Weekly backups: 4 weeks
  - Monthly backups: 12 months

Backup targets:
  - knowledge-base/: Full backup monthly
  - projects/: Incremental daily + full weekly
```

---

### Disaster recovery

**RTO (Recovery Time Objective):** 4 hours

**RPO (Recovery Point Objective):** 24 hours

```python
# DR restore procedure
def restore_from_backup(bucket: str, restore_point: datetime):
    """
    1. Stop all services
    2. Create new MinIO bucket
    3. Restore from S3 Glacier
    4. Verify checksums
    5. Restart services
    """
    pass
```

---

## MinIO vs S3 Comparison

| Feature | MinIO (Self-hosted) | AWS S3 |
|---------|---------------------|--------|
| Cost | Free (infra only) | $0.023/GB |
| Latency | 10-50ms | 50-150ms |
| Control | Full | Limited |
| Scalability | Manual | Auto |
| Backup | DIY | Built-in |

**Рекомендация для MVP:** MinIO self-hosted на VPS ($5/month) → экономия ~$20/month.

---

## Integration with ETL Pipeline

### Upload workflow

```
1. User uploads "TB_2024.xlsx" via UI
   ↓
2. Backend receives file
   ↓
3. MinIO: Save to projects/PRJ-001/uploads/TB_2024_20250115.xlsx
   │       Set metadata: etl-status=pending
   ↓
4. Trigger ETL Pipeline
   ↓
5. ETL processes file
   ├─→ PostgreSQL: INSERT INTO G2.20_trial_balance
   └─→ Qdrant: Vectorize & INSERT INTO G1_Client
   ↓
6. MinIO: Update metadata: etl-status=processed
   ↓
7. Respond to user: "File processed successfully"
```

---

### Document generation workflow

```
1. User: "Generate Revenue Testing program"
   ↓
2. Document Generator:
   a) Load template: knowledge-base/templates/E12_Revenue_Testing_v2.docx
   b) Load schema: knowledge-base/schemas/E12_schema.json
   c) Query data from G2.22_sales_register (via PostgreSQL)
   d) Map data to schema
   e) Render Jinja2 template
   f) Generate DOCX
   ↓
3. MinIO: Save to projects/PRJ-001/outputs/Revenue_Testing_Program_2024_v1_20250120.docx
   ↓
4. Generate pre-signed URL (1 hour expiry)
   ↓
5. Return URL to user
```

**Время:** 2-3 секунды от запроса до готового файла.

---

## Monitoring & Alerts

### Key metrics

```yaml
Metrics:
  - Storage usage (per bucket)
  - Upload rate (files/hour)
  - Download rate (GB/hour)
  - Error rate (%)
  - Average latency (ms)

Alerts:
  - Storage > 80% → notify admin
  - Error rate > 5% → critical alert
  - Latency > 500ms → investigate
```

---

## Связанные документы

- [G1: Qdrant Design](G1_Qdrant_Design.md)
- [G2: PostgreSQL Schema](G2_PostgreSQL_Schema.md)
- [ETL Pipeline](../blocks/ETL_Pipeline.md)
- [Block E: Templates](../blocks/Block_E_Templates.md)
