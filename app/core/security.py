# app/core/security.py
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

import jwt
from passlib.context import CryptContext

from app.core.config import settings

# Настройка bcrypt через passlib
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
)

MAX_BCRYPT_BYTES = 72


def hash_password(password: str) -> str:
    """
    Хеширование пароля с использованием bcrypt.

    bcrypt по стандарту использует максимум 72 байта.
    Для ASCII-строк это 72 символа. Для твоих паролей (типа 'Qwerty123')
    ограничение в реальности не заденет.
    """
    if not isinstance(password, str):
        raise TypeError("password must be a string")

    password_bytes = password.encode("utf-8")
    if len(password_bytes) > MAX_BCRYPT_BYTES:
        # Это та самая ошибка, которую ты видел в HTTP-ответе.
        # Для обычных паролей она не должна срабатывать.
        raise ValueError(
            "password cannot be longer than 72 bytes, truncate manually if "
            "necessary (e.g. my_password[:72])"
        )

    return pwd_context.hash(password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    """
    Сравнение открытого пароля с хешем.
    """
    if not plain_password or not password_hash:
        return False
    return pwd_context.verify(plain_password, password_hash)


def create_access_token(
    user_id: str | int,
    extra_claims: Dict[str, Any] | None = None,
    expires_minutes: int | None = None,
) -> str:
    """
    Генерация JWT токена для авторизации.
    """
    to_encode: Dict[str, Any] = {"sub": str(user_id)}

    if extra_claims:
        to_encode.update(extra_claims)

    expire = datetime.now(timezone.utc) + timedelta(
        minutes=expires_minutes or settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    to_encode["exp"] = expire

    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    return encoded_jwt
