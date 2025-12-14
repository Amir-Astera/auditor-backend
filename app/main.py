"""FastAPI application entrypoint."""

import sys
from pathlib import Path

from fastapi import FastAPI

# Ensure the project root is on the import path when running as ``python app/main.py``.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from app.core.db import Base, engine
from app.core.logging import configure_logging, get_logger
from app.modules.auth.router import router as auth_router
from app.modules.files.router import router as files_router

configure_logging()
logger = get_logger(__name__)

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="OSON Document Intelligence",
    description="Авторизация для административной панели и Telegram Mini App",
    swagger_ui_parameters={"persistAuthorization": True},
)

from app.modules.chats.router import router as chats_router
from app.modules.customers.router import router as customers_router

app.include_router(auth_router)
app.include_router(files_router)
app.include_router(customers_router)
app.include_router(chats_router)