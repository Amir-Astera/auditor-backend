# Интеграция LIGHTRAG в модуль RAG

## Описание

LIGHTRAG - это легковесная реализация RAG (Retrieval-Augmented Generation) с использованием графа знаний. Интеграция позволяет использовать LIGHTRAG вместе с существующей инфраструктурой проекта:
- Gemini API для генерации ответов
- Qdrant для векторного поиска
- MinIO для хранения файлов

## Установка

### 1. Установка зависимостей

```bash
pip install -r requirements.txt
```

Или установите LIGHTRAG отдельно:

```bash
pip install lightrag
```

### 2. Настройка переменных окружения

Убедитесь, что в `.env` файле настроены:
- `GEMINI_API_KEY` - ключ для Gemini API (опционально, можно использовать встроенный)
- `QDRANT_URL` - URL для Qdrant
- `QDRANT_COLLECTION_NAME` - имя коллекции

## Использование

### API Endpoints

#### 1. Запрос к RAG системе

```bash
POST /rag/query
```

**Тело запроса:**
```json
{
  "question": "Что такое искусственный интеллект?",
  "mode": "hybrid",
  "top_k": 5
}
```

**Режимы запроса:**
- `naive` - Простой запрос без использования графа
- `local` - Использование локального контекста
- `global` - Использование глобального контекста графа
- `hybrid` - Комбинация локального и глобального контекста (рекомендуется)

**Ответ:**
```json
{
  "answer": "Искусственный интеллект - это...",
  "context": [...],
  "nodes": [...],
  "edges": [...],
  "mode": "hybrid"
}
```

#### 2. Вставка текста в граф знаний

```bash
POST /rag/insert
```

**Тело запроса:**
```json
{
  "text": "Текст документа для добавления в граф знаний...",
  "metadata": {
    "source": "document.pdf",
    "author": "Иван Иванов"
  }
}
```

**Ответ:**
```json
{
  "node_id": "node_123",
  "success": true
}
```

#### 3. Удаление узла

```bash
DELETE /rag/node/{node_id}
```

#### 4. Статистика графа

```bash
GET /rag/stats
```

**Ответ:**
```json
{
  "nodes_count": 150,
  "edges_count": 300,
  "working_dir": "./lightrag_cache"
}
```

## Архитектура

### Компоненты

1. **LightRAGService** (`app/modules/rag/lightrag_integration.py`)
   - Основной сервис для работы с LIGHTRAG
   - Интегрируется с Gemini API через адаптер
   - Управляет графом знаний

2. **GeminiLLMAdapter**
   - Адаптер для использования Gemini API с LIGHTRAG
   - Преобразует вызовы LIGHTRAG в запросы к Gemini

3. **RAGService** (`app/modules/rag/service.py`)
   - Высокоуровневый сервис для работы с RAG
   - Объединяет LIGHTRAG и существующую инфраструктуру

4. **RAG Router** (`app/modules/rag/router.py`)
   - FastAPI endpoints для работы с RAG
   - Требует авторизации через JWT токен

## Примеры использования

### Python

```python
import requests

BASE_URL = "http://localhost:8000"
TOKEN = "your_jwt_token"

headers = {"Authorization": f"Bearer {TOKEN}"}

# Вставка текста
response = requests.post(
    f"{BASE_URL}/rag/insert",
    json={
        "text": "Документ о новых технологиях...",
        "metadata": {"source": "tech_doc.pdf"}
    },
    headers=headers
)
print(response.json())

# Запрос
response = requests.post(
    f"{BASE_URL}/rag/query",
    json={
        "question": "Какие новые технологии упоминаются?",
        "mode": "hybrid",
        "top_k": 5
    },
    headers=headers
)
print(response.json())
```

### cURL

```bash
# Вставка текста
curl -X POST "http://localhost:8000/rag/insert" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Текст документа...",
    "metadata": {"source": "doc.pdf"}
  }'

# Запрос
curl -X POST "http://localhost:8000/rag/query" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Ваш вопрос",
    "mode": "hybrid",
    "top_k": 5
  }'
```

## Интеграция с существующими модулями

### Интеграция с модулем Files

Можно автоматически индексировать загруженные файлы в граф знаний:

```python
from app.modules.rag.service import RAGService
from app.modules.files.service import FileService

# После загрузки файла
file_content = extract_text_from_file(file)
rag_service = RAGService()
rag_service.insert_text(
    text=file_content,
    metadata={"file_id": str(file.id), "filename": file.original_filename}
)
```

### Интеграция с модулем Chats

Использовать RAG для ответов в чатах:

```python
from app.modules.rag.service import RAGService

rag_service = RAGService()
response = rag_service.query(
    question=user_message,
    mode="hybrid"
)
chat_response = response["answer"]
```

## Настройка

### Рабочая директория

По умолчанию LIGHTRAG использует `./lightrag_cache`. Можно изменить через переменную окружения или при создании сервиса:

```python
rag_service = RAGService(
    lightrag_working_dir="/path/to/custom/cache"
)
```

### Параметры Gemini

Настройки Gemini API можно изменить в `app/modules/rag/gemini.py`:

```python
GEMINI_API_KEY = "your_key"
MODEL_NAME = 'gemini-2.0-flash'
```

## Troubleshooting

### LIGHTRAG не установлен

Если LIGHTRAG не установлен, система будет использовать fallback на прямой запрос к Gemini API.

### Ошибки инициализации

Проверьте:
1. Установлен ли LIGHTRAG: `pip install lightrag`
2. Правильность путей к рабочей директории
3. Доступность Gemini API

### Проблемы с производительностью

- Уменьшите `top_k` в запросах
- Используйте режим `naive` для простых запросов
- Очищайте кэш графа при необходимости

## Дополнительные ресурсы

- [LIGHTRAG GitHub](https://github.com/HKUDS/LightRAG) (если доступен)
- [Gemini API Documentation](https://ai.google.dev/docs)
- [Qdrant Documentation](https://qdrant.tech/documentation/)

