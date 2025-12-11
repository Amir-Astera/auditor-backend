from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
import jwt
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
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

# Swagger's "Authorize" button will use this URL to obtain tokens.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/admin/login")


def _get_auth_service(db: Session = Depends(get_db)) -> AuthService:
    return AuthService(db)


def _decode_token(
    token: str,
    audience: list[str] | None = None,
) -> dict:
    """
    Универсальная функция декодирования JWT.
    Если audience передан, PyJWT проверит, что aud в токене входит в этот список.
    """
    try:
        return jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            audience=audience,
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    # Разрешаем оба типа токенов: админский и сотрудника
    payload = _decode_token(
        token,
        audience=["sec.asteradigital.kz", "divan.asteradigital.kz"],
    )

    user_id: str | None = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    repo = UserRepository(db)
    user = repo.get_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User disabled",
        )

    return user


def get_current_admin(
    token: str = Depends(oauth2_scheme),
    user: User = Depends(get_current_user),
) -> User:
    """
    Требуется токен с aud = sec.asteradigital.kz и user.is_admin = True.
    """
    payload = _decode_token(
        token,
        audience=["sec.asteradigital.kz"],  # только админский audience
    )
    if payload.get("aud") != "sec.asteradigital.kz":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin token required",
        )

    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return user


def get_current_employee(
    token: str = Depends(oauth2_scheme),
    user: User = Depends(get_current_user),
) -> User:
    """
    Требуется токен с aud = divan.asteradigital.kz.
    Можно сделать, чтобы админ тоже мог пользоваться, если нужно.
    """
    payload = _decode_token(
        token,
        audience=["divan.asteradigital.kz"],
    )
    if payload.get("aud") != "divan.asteradigital.kz":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Employee token required",
        )
    
    return user


def get_current_employee(user: User = Depends(get_current_user)) -> User:
    if user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Employee privileges required")
    return user


@router.post(
    "/admin/login",
    response_model=TokenResponse,
    summary="Админ: вход по email и паролю (OAuth2 password flow)",
)
def admin_login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    service: AuthService = Depends(_get_auth_service),
):
    # Swagger будет передавать email в поле "username"
    email = form_data.username
    password = form_data.password

    try:
        token, _ = service.login_admin(email, password)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        )
    return TokenResponse(access_token=token)



@router.post(
    "/telegram/login",
    response_model=TokenResponse,
    summary="Сотрудник: вход по телефону и паролю",
)
def telegram_login(
    payload: TelegramLoginRequest, service: AuthService = Depends(_get_auth_service)
):
    try:
        token, _ = service.login_telegram(payload.phone, payload.password)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        )
    return TokenResponse(access_token=token)


@router.post(
    "/admin/users",
    response_model=UserBase,
    summary="Создание сотрудника или администратора",
)
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


@router.post(
    "/admin/bootstrap",
    response_model=UserBase,
    summary="Инициализация первого администратора",
)
def bootstrap_admin(payload: UserCreateRequest, service: AuthService = Depends(_get_auth_service)):
    try:
        return service.bootstrap_admin(payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )


@router.get("/me", response_model=UserBase, summary="Проверка авторизации")
def me(user: User = Depends(get_current_user)):
    return user
