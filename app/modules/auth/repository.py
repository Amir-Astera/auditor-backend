"""Persistence layer for authentication and user management."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.auth.models import User


class UserRepository:
    def __init__(self, db: Session):
        self.db = db

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
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user
