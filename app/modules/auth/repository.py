<<<<<<< HEAD
# app/auth/repository.py
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import select

from app.auth.models import User
=======
"""Persistence layer for authentication and user management."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.auth.models import User
>>>>>>> e81b75286128c8454dcb0c6fa4879ac1da9358b2


class UserRepository:
    def __init__(self, db: Session):
        self.db = db

<<<<<<< HEAD
    def get_by_id(self, user_id: str) -> Optional[User]:
        return self.db.get(User, user_id)

    def get_by_email(self, email: str) -> Optional[User]:
        stmt = select(User).where(User.email == email)
        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_telegram_phone(self, phone: str) -> Optional[User]:
        stmt = select(User).where(User.telegram_phone == phone)
        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_telegram_user_id(self, telegram_user_id: int) -> Optional[User]:
        stmt = select(User).where(User.telegram_user_id == telegram_user_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def save(self, user: User) -> User:
=======
    def get_by_id(self, user_id: str) -> User | None:
        return self.db.get(User, user_id)

    def get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(func.lower(User.email) == email.lower())
        return self.db.scalar(stmt)

    def get_by_phone(self, phone: str) -> User | None:
        stmt = select(User).where(User.telegram_phone == phone)
        return self.db.scalar(stmt)

    def has_admins(self) -> bool:
        stmt = select(func.count()).select_from(User).where(User.is_admin.is_(True))
        return bool(self.db.scalar(stmt))

    def create(self, user: User) -> User:
>>>>>>> e81b75286128c8454dcb0c6fa4879ac1da9358b2
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user
