# app/auth/repository.py
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import select

from app.auth.models import User


class UserRepository:
    def __init__(self, db: Session):
        self.db = db

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
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user
