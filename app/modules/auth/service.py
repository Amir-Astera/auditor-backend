"""Business logic for authentication flows."""
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password, verify_password
from app.modules.auth.models import User
from app.modules.auth.repository import UserRepository
from app.modules.auth.schemas import UserCreateRequest


class AuthService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = UserRepository(db)

    def login_admin(self, email: str, password: str) -> tuple[str, User]:
        user = self.repo.get_by_email(email)
        if not user or not user.is_admin:
            raise ValueError("Invalid email or password")

        self._ensure_active(user)
        self._validate_password(password, user)

        token = create_access_token(
            user.id,
            extra_claims={"role": "admin", "aud": "sec.asteradigital.kz"},
        )
        return token, user

    def login_telegram(self, phone: str, password: str) -> tuple[str, User]:
        user = self.repo.get_by_phone(phone)
        if not user:
            raise ValueError("Invalid phone or password")

        self._ensure_active(user)
        self._validate_password(password, user)

        token = create_access_token(
            user.id,
            extra_claims={"role": "employee", "aud": "divan.asteradigital.kz"},
        )
        return token, user

    def create_user(self, payload: UserCreateRequest) -> User:
        # Сотруднику обязательно нужен телефон Telegram
        if payload.is_admin is False and not payload.telegram_phone:
            raise ValueError("Telegram phone is required for employee accounts")

        # Уникальность e-mail
        if payload.email and self.repo.get_by_email(payload.email):
            raise ValueError("User with this email already exists")

        # Уникальность телефона
        if payload.telegram_phone and self.repo.get_by_phone(payload.telegram_phone):
            raise ValueError("User with this phone already exists")

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
        """Создание первого администратора (инициализация системы)."""
        if self.repo.has_admins():
            raise ValueError("Admin already exists")

        # ВАЖНО: не дублируем is_admin, а обновляем.
        admin_payload = payload.copy(update={"is_admin": True})
        # Альтернатива:
        # admin_payload = UserCreateRequest(
        #     **payload.dict(exclude={"is_admin"}),
        #     is_admin=True,
        # )

        return self.create_user(admin_payload)

    @staticmethod
    def _ensure_active(user: User) -> None:
        if not user.is_active:
            raise ValueError("User disabled")

    @staticmethod
    def _validate_password(password: str, user: User) -> None:
        if not user.password_hash or not verify_password(password, user.password_hash):
            raise ValueError("Invalid credentials")
