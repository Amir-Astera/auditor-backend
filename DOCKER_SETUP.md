# Запуск всего проекта в Docker

Теперь весь проект можно запустить одной командой через Docker Compose!

## Быстрый старт

### 1. Клонируйте репозиторий и перейдите в директорию проекта

### 2. Создайте файл `.env` (опционально)

Для production важно изменить `SECRET_KEY`. Скопируйте `.env.example` или создайте `.env` вручную:

```env
SECRET_KEY=your-super-secret-key-change-this-in-production
```

Если не создадите `.env`, будут использованы значения по умолчанию из `docker-compose.yml`.

### 3. Запустите все сервисы

**Используйте новую команду `docker compose` (без дефиса):**

```bash
docker compose up -d
```

Или для просмотра логов в реальном времени:

```bash
docker compose up
```

**Примечание:** Если у вас старая версия Docker и команда `docker compose` не работает, обновите Docker или используйте `docker-compose` после его обновления. См. `DOCKER_TROUBLESHOOTING.md` для решения проблем.

### 4. Проверьте работу

После запуска все сервисы будут доступны:

- **FastAPI API**: http://localhost:8000
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **MinIO Console**: http://localhost:9001 (admin/password123)
- **Qdrant Dashboard**: http://localhost:6333/dashboard
- **PostgreSQL**: localhost:5432

## Сервисы в составе

1. **postgres** - База данных PostgreSQL
   - Порт: 5432
   - Пользователь: `auditor_user`
   - Пароль: `auditor_password_123`
   - База данных: `tri_s_audit`

2. **minio** - Объектное хранилище (S3-совместимое)
   - API: http://localhost:9000
   - Console: http://localhost:9001
   - User: `admin`
   - Password: `password123`

3. **qdrant** - Векторная база данных
   - REST API: http://localhost:6333
   - gRPC: localhost:6334

4. **api** - FastAPI приложение
   - Порт: 8000
   - Автоматически подключается ко всем сервисам

## Управление сервисами

### Остановка всех сервисов

```bash
docker compose down
```

### Остановка с удалением volumes (⚠️ удалит все данные!)

```bash
docker compose down -v
```

### Перезапуск конкретного сервиса

```bash
docker compose restart api
```

### Просмотр логов

```bash
# Все сервисы
docker compose logs -f

# Конкретный сервис
docker compose logs -f api
docker compose logs -f postgres
docker compose logs -f minio
docker compose logs -f qdrant
```

### Просмотр статуса

```bash
docker compose ps
```

### Пересборка API после изменений кода

```bash
docker compose build api
docker compose up -d api
```

Или с перезапуском:

```bash
docker compose up -d --build api
```

## Переменные окружения

Основные переменные можно настроить через файл `.env` или прямо в `docker-compose.yml`.

**Важно**: Для production обязательно измените:
- `SECRET_KEY` - секретный ключ для JWT токенов
- Пароли для PostgreSQL, MinIO и других сервисов

## Первый запуск

После первого запуска:

1. Откройте http://localhost:8000/docs
2. Создайте первого администратора через `POST /auth/admin/bootstrap`
3. Войдите через `POST /auth/admin/login` и получите токен
4. Используйте токен в Swagger UI (кнопка "Authorize")

## Устранение проблем

### Сервис не запускается

Проверьте логи:
```bash
docker-compose logs [service_name]
```

### База данных не подключается

Убедитесь, что PostgreSQL запустился полностью:
```bash
docker-compose logs postgres
```

Проверьте healthcheck:
```bash
docker-compose ps
```

### Порты заняты

Если порты уже используются, измените их в `docker-compose.yml`:

```yaml
ports:
  - "8001:8000"  # Вместо 8000:8000
```

### Пересборка с очисткой кэша

```bash
docker-compose build --no-cache api
docker-compose up -d
```

## Разработка

Для разработки с автоматической перезагрузкой кода, используйте volume для монтирования кода:

Добавьте в `docker-compose.yml` в секцию `api`:

```yaml
volumes:
  - .:/app
```

И измените команду на:

```yaml
command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Но учтите, что `--reload` требует установки дополнительных зависимостей в production.

