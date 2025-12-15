@echo off
echo Starting auditor-backend with Docker Compose...
echo.

docker compose up -d --build

echo.
echo Waiting for services to start...
timeout /t 10 /nobreak >nul

echo.
echo Services started!
echo.
echo FastAPI API: http://localhost:8000
echo Swagger UI: http://localhost:8000/docs
echo MinIO Console: http://localhost:9001 (admin/password123)
echo Qdrant Dashboard: http://localhost:6333/dashboard
echo.
echo To view logs: docker compose logs -f
echo To stop: docker compose down
echo.
pause

