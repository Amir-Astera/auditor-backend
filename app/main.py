"""FastAPI application entrypoint."""

from pathlib import Path
import sys

from fastapi import FastAPI


# Ensure the project root is on the import path when running as ``python app/main.py``.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from app.core.db import Base, engine
from app.modules.auth.router import router as auth_router
from app.modules.files.router import router as files_router

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="OSON Document Intelligence",
    description="Авторизация для административной панели и Telegram Mini App",
    swagger_ui_parameters={"persistAuthorization": True},
)

app.include_router(auth_router)
app.include_router(files_router)
