from fastapi import FastAPI

from app.core.db import Base, engine
from app.modules.auth.router import router as auth_router

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="OSON Document Intelligence",
    description="Авторизация для административной панели и Telegram Mini App",
    swagger_ui_parameters={"persistAuthorization": True},
)

app.include_router(auth_router)
