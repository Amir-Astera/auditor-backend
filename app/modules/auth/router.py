# app/auth/router.py
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
import jwt

<<<<<<< HEAD
from app.core.database import get_db
from app.core.config import settings
from app.auth.schemas import LoginRequest, TokenResponse, UserBase
from app.auth.service import AuthService
from app.auth.repository import UserRepository
from app.auth.models import User

router = APIRouter(prefix="/auth", tags=["auth"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
=======
from app.core.config import settings
from app.core.db import get_db
from app.modules.auth.schemas import (
    AdminLoginRequest,
    TelegramLoginRequest,
    TokenResponse,
    UserBase,
    UserCreateRequest,
)
from app.modules.auth.service import AuthService
from app.modules.auth.repository import UserRepository
from app.modules.auth.models import User

router = APIRouter(prefix="/auth", tags=["auth"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/admin/login")
>>>>>>> e81b75286128c8454dcb0c6fa4879ac1da9358b2


def _get_auth_service(db: Session = Depends(get_db)) -> AuthService:
    return AuthService(db)


<<<<<<< HEAD
@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, service: AuthService = Depends(_get_auth_service)):
    try:
        token, _ = service.login_with_password(payload.email, payload.password)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
=======
@router.post("/admin/login", response_model=TokenResponse)
def admin_login(payload: AdminLoginRequest, service: AuthService = Depends(_get_auth_service)):
    try:
        token, _ = service.login_admin(payload.email, payload.password)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        )
    return TokenResponse(access_token=token)


@router.post("/telegram/login", response_model=TokenResponse)
def telegram_login(payload: TelegramLoginRequest, service: AuthService = Depends(_get_auth_service)):
    try:
        token, _ = service.login_telegram(payload.phone, payload.password)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
>>>>>>> e81b75286128c8454dcb0c6fa4879ac1da9358b2
        )
    return TokenResponse(access_token=token)


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    user_id: str | None = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    repo = UserRepository(db)
    user = repo.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User disabled")

    return user


def get_current_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required")
    return user


<<<<<<< HEAD
=======
@router.post("/admin/users", response_model=UserBase)
def create_user(
    payload: UserCreateRequest,
    service: AuthService = Depends(_get_auth_service),
    _: User = Depends(get_current_admin),
):
    try:
        return service.create_user(payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )


@router.post("/admin/bootstrap", response_model=UserBase)
def bootstrap_admin(payload: UserCreateRequest, service: AuthService = Depends(_get_auth_service)):
    try:
        return service.bootstrap_admin(payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )


>>>>>>> e81b75286128c8454dcb0c6fa4879ac1da9358b2
@router.get("/me", response_model=UserBase)
def me(user: User = Depends(get_current_user)):
    return user
