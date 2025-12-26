"""Pydantic schemas for authentication endpoints."""

from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, validator

MAX_PASSWORD_BYTES = 72


def validate_password_length(value: str) -> str:
    if isinstance(value, str):
        password_bytes = value.encode("utf-8")
        if len(password_bytes) > MAX_PASSWORD_BYTES:
            raise ValueError(
                f"Пароль слишком длинный. Максимум {MAX_PASSWORD_BYTES} байт "
                f"({len(value)} символов). Для ASCII это примерно {MAX_PASSWORD_BYTES} символов."
            )
    return value


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AdminLoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(
        min_length=8,
        max_length=72,
        description="Административный пароль (минимум 8 символов, максимум 72 байта)",
    )

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        return validate_password_length(v)


class TelegramLoginRequest(BaseModel):
    phone: str = Field(description="Номер телефона в формате Telegram")
    password: str = Field(min_length=8, max_length=72)

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        return validate_password_length(v)


class UserCreateRequest(BaseModel):
    email: EmailStr | None = None
    full_name: str | None = None
    password: str = Field(
        min_length=8,
        max_length=72,
        description="Пароль (минимум 8 символов, максимум 72 байта)",
    )
    telegram_phone: str | None = None
    telegram_user_id: int | None = None
    is_admin: bool = False

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        return validate_password_length(v)


class UserBase(BaseModel):
    id: UUID
    email: EmailStr | None = None
    full_name: str | None = None
    telegram_phone: str | None = None
    telegram_user_id: int | None = None
    is_admin: bool
    is_active: bool

    model_config = ConfigDict(from_attributes=True)