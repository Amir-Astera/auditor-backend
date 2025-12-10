# app/auth/service.py
import uuid
from typing import Tuple

from sqlalchemy.orm import Session

from app.auth.models import User
from app.auth.repository import UserRepository
from app.core.security import hash_password, verify_password, create_access_token


class AuthService:
    def __init__(self, db: Session):
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
