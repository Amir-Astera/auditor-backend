# 🛠️ Implementation Guide

## 1. MinIO Setup (Docker)

```bash
# Start MinIO server
docker run -d \
  -p 9000:9000 \
  -p 9001:9001 \
  --name minio \
  -e "MINIO_ROOT_USER=admin" \
  -e "MINIO_ROOT_PASSWORD=password123" \
  -v /mnt/data:/data \
  minio/minio server /data --console-address ":9001"
```

```python
# src/storage/minio_client.py

from minio import Minio
import os

minio_client = Minio(
    "localhost:9000",
    access_key=os.getenv("MINIO_ACCESS_KEY"),
    secret_key=os.getenv("MINIO_SECRET_KEY"),
    secure=False  # True for production with TLS
)

def create_buckets():
    """Создать два bucket: knowledge-base и projects"""

    buckets = ["knowledge-base", "projects"]

    for bucket in buckets:
        if not minio_client.bucket_exists(bucket):
            minio_client.make_bucket(bucket)
            print(f"Bucket '{bucket}' created")
```

## 2. Upload Templates (Block E)

```python
# src/storage/template_uploader.py

def upload_templates_to_minio():
    """Загрузить все 41 шаблон Block E в MinIO"""

    template_dir = Path("knowledge/templates")

    for template_file in template_dir.glob("E*.docx"):
        object_name = f"templates/{template_file.name}"

        minio_client.fput_object(
            bucket_name="knowledge-base",
            object_name=object_name,
            file_path=str(template_file),
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            metadata={
                "x-amz-meta-template-id": template_file.stem.split("_")[0],  # E01, E12, ...
                "x-amz-meta-version": "v1",
                "x-amz-meta-category": extract_category(template_file.name)
            }
        )

        print(f"Uploaded: {object_name}")
```

## 3. Client File Upload Workflow

```python
# src/api/upload.py

from fastapi import UploadFile, HTTPException
import datetime

async def upload_client_file(
    project_id: str,
    file: UploadFile,
    file_type: str  # trial_balance, sales_register, ...
):
    """
    Upload client document to MinIO projects bucket.
    """
    # 1. Validate file
    if file.content_type not in ["application/vnd.ms-excel", "text/csv"]:
        raise HTTPException(400, "Invalid file type")

    # 2. Generate filename
    upload_date = datetime.datetime.now().strftime("%Y%m%d")
    filename = f"{file_type}_2024_{upload_date}.{file.filename.split('.')[-1]}"
    object_name = f"{project_id}/uploads/{filename}"

    # 3. Upload to MinIO
    minio_client.put_object(
        bucket_name="projects",
        object_name=object_name,
        data=file.file,
        length=-1,  # unknown length, will read until EOF
        part_size=10*1024*1024,  # 10MB chunks
        content_type=file.content_type,
        metadata={
            "x-amz-meta-project-id": project_id,
            "x-amz-meta-document-type": file_type,
            "x-amz-meta-fiscal-year": "2024",
            "x-amz-meta-uploaded-by": current_user.email,
            "x-amz-meta-etl-status": "pending"
        }
    )

    # 4. Trigger ETL Pipeline
    await trigger_etl(project_id, object_name, file_type)

    return {"status": "uploaded", "path": object_name}
```

## 4. Pre-signed URLs (Download)

```python
# src/storage/presigned_urls.py

from datetime import timedelta

def generate_download_url(
    project_id: str,
    file_path: str,
    expiry_hours: int = 1
) -> str:
    """
    Генерирует временную ссылку для скачивания.

    Expiry: default 1 час
    """
    url = minio_client.presigned_get_object(
        bucket_name="projects",
        object_name=f"{project_id}/outputs/{file_path}",
        expires=timedelta(hours=expiry_hours)
    )

    return url
```

## 5. Document Generation Workflow

```python
# src/generators/document_generator.py

from docxtpl import DocxTemplate
import tempfile

async def generate_document(
    template_id: str,
    project_id: str,
    data: dict
) -> dict:
    """
    Generate document from template.

    1. Download template from MinIO
    2. Render with data
    3. Upload to projects/outputs/
    4. Return pre-signed URL
    """
    # 1. Download template
    template_path = f"templates/{template_id}_v1.docx"

    with tempfile.NamedTemporaryFile(suffix=".docx") as tmp:
        minio_client.fget_object(
            bucket_name="knowledge-base",
            object_name=template_path,
            file_path=tmp.name
        )

        # 2. Render template
        doc = DocxTemplate(tmp.name)
        doc.render(data)

        # 3. Save rendered document
        output_filename = f"{template_id}_{data['fiscal_year']}_v1_{datetime.now().strftime('%Y%m%d')}.docx"
        output_path = f"{project_id}/outputs/{output_filename}"

        rendered_tmp = tempfile.NamedTemporaryFile(suffix=".docx", delete=False)
        doc.save(rendered_tmp.name)

        minio_client.fput_object(
            bucket_name="projects",
            object_name=output_path,
            file_path=rendered_tmp.name,
            metadata={
                "x-amz-meta-template-id": template_id,
                "x-amz-meta-project-id": project_id,
                "x-amz-meta-generated-by": current_user.email
            }
        )

    # 4. Generate download URL
    download_url = generate_download_url(project_id, output_filename)

    return {
        "file_path": output_path,
        "download_url": download_url,
        "expires_in": "1 hour"
    }
```

## 6. Lifecycle Policy (auto-cleanup)

```python
# Set lifecycle rules for temp files

from minio import LifecycleConfig, Rule, Expiration

lifecycle_config = LifecycleConfig(
    rules=[
        Rule(
            rule_id="temp-cleanup",
            rule_filter={"prefix": "temp/"},
            expiration=Expiration(days=1),
            status="Enabled"
        )
    ]
)

minio_client.set_bucket_lifecycle("projects", lifecycle_config)
```

## 7. TODO для разработчика

- [ ] Установить MinIO (Docker или self-hosted)
- [ ] Создать buckets: `knowledge-base`, `projects`
- [ ] Загрузить все 41 template Block E в `knowledge-base/templates/`
- [ ] Создать JSON schemas для каждого template
- [ ] Имплементировать `upload_client_file()` endpoint
- [ ] Имплементировать `generate_document()` с Jinja2 rendering
- [ ] Настроить pre-signed URLs (expiry: 1 час)
- [ ] Настроить lifecycle policy для `temp/` (TTL: 24h)

**Приоритет:** P2 (важный, зависит от Block E templates)

## 8. Связанные документы

- G1 Qdrant Design — файлы векторизуются после upload
- G2 PostgreSQL Schema — metadata о файлах в БД
- Block E Templates — 41 template для генерации
