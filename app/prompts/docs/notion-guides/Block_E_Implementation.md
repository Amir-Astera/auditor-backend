# 🛠️ Implementation Guide

## 1. MinIO хранение шаблонов

```python
# src/storage/template_manager.py

TEMPLATE_BUCKET = "knowledge-base"
TEMPLATE_PATH = "templates/"

BLOCK_E_TEMPLATES = [
    "E01_TOR.docx",
    "E02_Engagement_Letter.docx",
    "E03_Risk_Assessment.docx",
    "E12_Revenue_Testing.docx",
    # ... 41 template total
]

def upload_templates_to_minio():
    """Загрузка всех шаблонов Block E в MinIO"""
    for template in BLOCK_E_TEMPLATES:
        file_path = Path(f"knowledge/templates/{template}")

        minio_client.fput_object(
            bucket_name=TEMPLATE_BUCKET,
            object_name=f"{TEMPLATE_PATH}{template}",
            file_path=str(file_path),
            metadata={
                "x-amz-meta-template-id": template.split("_")[0],  # E01, E12, ...
                "x-amz-meta-category": extract_category(template),
                "x-amz-meta-version": "v1"
            }
        )
```

## 2. Document Generator

```python
# src/generators/document_generator.py

from docxtpl import DocxTemplate
import json

def generate_document(
    template_id: str,
    project_id: str,
    data: dict
) -> str:
    """
    Генерация документа из шаблона.

    Args:
        template_id: "E12" (Revenue Testing)
        project_id: "PRJ-001"
        data: {client_name, fiscal_year, sample_size, ...}

    Returns:
        MinIO path to generated file
    """
    # 1. Download template from MinIO
    template_path = f"templates/{template_id}_*.docx"
    local_template = download_from_minio(TEMPLATE_BUCKET, template_path)

    # 2. Load Jinja2 template
    doc = DocxTemplate(local_template)

    # 3. Render with data
    doc.render(data)

    # 4. Save to MinIO
    output_filename = f"{template_id}_{data['fiscal_year']}_v1_{date.today()}.docx"
    output_path = f"projects/{project_id}/outputs/{output_filename}"

    doc.save(f"/tmp/{output_filename}")
    minio_client.fput_object(
        bucket_name="projects",
        object_name=output_path,
        file_path=f"/tmp/{output_filename}"
    )

    return output_path
```

## 3. Template Schema (JSON)

```json
// knowledge-base/schemas/E12_schema.json

{
  "template_id": "E12",
  "template_name": "Revenue Testing Program",
  "required_fields": [
    "client_name",
    "fiscal_year",
    "sample_size",
    "sampling_interval",
    "population_value"
  ],
  "data_sources": {
    "sample_size": "G2.9_testing_procedures",
    "population_value": "G2.22_sales_register"
  },
  "output_format": "docx"
}
```

## 4. PostgreSQL интеграция

```sql
-- Трекер сгенерированных документов
CREATE TABLE generated_documents (
    doc_id SERIAL PRIMARY KEY,
    project_id VARCHAR(50) REFERENCES projects(project_id),
    template_id VARCHAR(20),
    file_path TEXT,
    version INT DEFAULT 1,
    generated_at TIMESTAMP DEFAULT NOW(),
    generated_by VARCHAR(100)
);

CREATE INDEX idx_docs_project ON generated_documents(project_id);
```

## 5. H2 Buttons для генерации

```python
# Response после генерации
return {
    "response": "Revenue Testing Program сгенерирован",
    "buttons": [
        {
            "label": "Скачать DOCX",
            "action": "download-document",
            "data": {
                "file_path": "projects/PRJ-001/outputs/E12_2024_v1_20250120.docx",
                "presigned_url": generate_presigned_url(...)
            }
        },
        {
            "label": "Конвертировать в PDF",
            "action": "convert-to-pdf"
        }
    ]
}
```

## 6. TODO для разработчика

- [ ] Загрузить все 41 шаблон Block E в MinIO bucket `knowledge-base/templates/`
- [ ] Создать JSON schemas для каждого template (41 файл)
- [ ] Имплементировать `generate_document()` с Jinja2 rendering
- [ ] Создать таблицу `generated_documents` в PostgreSQL
- [ ] Настроить pre-signed URLs для скачивания (expiry: 1 час)
- [ ] Написать тесты для template rendering

**Приоритет:** P2 (важный, но зависит от G2 data availability)

## 7. Связанные документы

- G3 MinIO Structure — bucket organization, naming conventions
- G2 PostgreSQL Schema — data sources для templates
- Development Rules — H2 Buttons for downloads
