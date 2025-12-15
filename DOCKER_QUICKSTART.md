# Быстрый запуск проекта через Docker

## Запуск всех сервисов

### Вариант 1: Через скрипт (Windows)

```bash
start-docker.bat
```

### Вариант 2: Через команду

```bash
docker compose up -d --build
```

## Что будет запущено

1. **PostgreSQL** - База данных (порт 5432)
2. **Redis** - Кэш и очереди (порт 6379)
3. **MinIO** - Объектное хранилище (порты 9000, 9001)
4. **Qdrant** - Векторная база данных (порты 6333, 6334)
5. **API** - FastAPI приложение (порт 8000)
6. **Worker** - Фоновый воркер для индексации файлов

## Доступ к сервисам

После запуска доступны:

- **FastAPI API**: http://localhost:8000
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **MinIO Console**: http://localhost:9001
  - User: `admin`
  - Password: `password123`
- **Qdrant Dashboard**: http://localhost:6333/dashboard
- **PostgreSQL**: localhost:5432
  - User: `auditor_user`
  - Password: `auditor_password_123`
  - Database: `tri_s_audit`

## Первый запуск

1. **Создайте первого администратора** через Swagger UI:
   - Откройте http://localhost:8000/docs
   - Найдите `POST /auth/admin/bootstrap`
   - Создайте администратора

2. **Войдите в систему**:
   - Используйте `POST /auth/admin/login`
   - Получите токен

3. **Авторизуйтесь в Swagger**:
   - Нажмите "Authorize" и вставьте токен

## Просмотр логов

```bash
# Все сервисы
docker compose logs -f

# Конкретный сервис
docker compose logs -f api
docker compose logs -f worker
```

## Остановка

```bash
docker compose down
```

## Остановка с удалением данных

```bash
docker compose down -v
```

## Пересборка после изменений

```bash
docker compose up -d --build api
```

## Troubleshooting

### Порт занят

Если порт занят, измените его в `docker-compose.yml`:

```yaml
ports:
  - "8001:8000"  # Вместо 8000:8000
```

### Ошибки сборки

Очистите кэш и пересоберите:

```bash
docker compose build --no-cache api
docker compose up -d
```

### Проверка статуса

```bash
docker compose ps
```

### Проверка healthcheck

```bash
docker compose ps
# Проверьте статус healthcheck для каждого сервиса
```

