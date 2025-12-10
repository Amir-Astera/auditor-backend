<<<<<<< HEAD
# app/auth/service.py
import uuid
from typing import Tuple

from sqlalchemy.orm import Session

from app.auth.models import User
from app.auth.repository import UserRepository
from app.core.security import hash_password, verify_password, create_access_token
=======
"""Business logic for authentication flows."""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password, verify_password
from app.modules.auth.models import User
from app.modules.auth.repository import UserRepository
from app.modules.auth.schemas import UserCreateRequest


@dataclass
class AuthResult:
    token: str
    user: User
>>>>>>> e81b75286128c8454dcb0c6fa4879ac1da9358b2


class AuthService:
    def __init__(self, db: Session):
<<<<<<< HEAD
        self.db = db
        self.repo = UserRepository(db)

    # Логин для админки: email + пароль
    def login_with_password(self, email: str, password: str) -> Tuple[str, User]:
        user = self.repo.get_by_email(email)
        if not user or not user.password_hash:
            raise ValueError("Invalid credentials")

        if not verify_password(password, user.password_hash):
            raise ValueError("Invalid credentials")

        if not user.is_active:
            raise ValueError("User is not active")

        token = create_access_token(subject=user.id, extra_claims={"is_admin": user.is_admin})
        return token, user

    # Создание админа (можно дернуть один раз или через миграцию)
    def create_admin(self, email: str, password: str, full_name: str | None = None) -> User:
        if self.repo.get_by_email(email):
            raise ValueError("User with this email already exists")

        user = User(
            id=str(uuid.uuid4()),
            email=email,
            full_name=full_name,
            password_hash=hash_password(password),
            is_admin=True,
            is_active=True,
        )
        return self.repo.save(user)

    # Логин по Telegram user id (для мини-аппа)
    def login_with_telegram_user_id(self, telegram_user_id: int) -> Tuple[str, User]:
        user = self.repo.get_by_telegram_user_id(telegram_user_id)
        if not user:
            raise ValueError("User not found or not linked with Telegram")

        if not user.is_active:
            raise ValueError("User is not active")

        token = create_access_token(subject=user.id, extra_claims={"is_admin": user.is_admin})
        return token, user
=======
        self.repo = UserRepository(db)

    def login_admin(self, email: str, password: str) -> AuthResult:
        user = self.repo.get_by_email(email)
        if not user or not user.is_admin:
            raise ValueError("Invalid email or password")
        self._ensure_active(user)
        self._validate_password(password, user)
        token = create_access_token(user.id, extra_claims={"role": "admin", "aud": "sec.asteradigital.kz"})
        return AuthResult(token=token, user=user)

    def login_telegram(self, phone: str, password: str) -> AuthResult:
        user = self.repo.get_by_phone(phone)
        if not user:
            raise ValueError("Invalid phone or password")
        self._ensure_active(user)
        self._validate_password(password, user)
        token = create_access_token(user.id, extra_claims={"role": "employee", "aud": "divan.asteradigital.kz"})
        return AuthResult(token=token, user=user)

    def create_user(self, payload: UserCreateRequest) -> User:
        if payload.is_admin is False and not payload.telegram_phone:
            raise ValueError("Telegram phone is required for employee accounts")

        new_user = User(
            email=payload.email,
            full_name=payload.full_name,
            telegram_phone=payload.telegram_phone,
            telegram_user_id=payload.telegram_user_id,
            is_admin=payload.is_admin,
            is_active=True,
            password_hash=hash_password(payload.password),
        )
        return self.repo.create(new_user)

    def bootstrap_admin(self, payload: UserCreateRequest) -> User:
        if self.repo.has_admins():
            raise ValueError("Admin already exists")
        admin_payload = UserCreateRequest(**payload.dict(), is_admin=True)
        return self.create_user(admin_payload)

    @staticmethod
    def _ensure_active(user: User) -> None:
        if not user.is_active:
            raise ValueError("User disabled")

    @staticmethod
    def _validate_password(password: str, user: User) -> None:
        if not user.password_hash or not verify_password(password, user.password_hash):
            raise ValueError("Invalid credentials")
>>>>>>> e81b75286128c8454dcb0c6fa4879ac1da9358b2
