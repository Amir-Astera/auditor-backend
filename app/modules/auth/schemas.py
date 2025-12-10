# app/auth/schemas.py
<<<<<<< HEAD
from pydantic import BaseModel, EmailStr
=======
from pydantic import BaseModel, EmailStr, Field
>>>>>>> e81b75286128c8454dcb0c6fa4879ac1da9358b2


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


<<<<<<< HEAD
class LoginRequest(BaseModel):
    email: EmailStr
    password: str
=======
class AdminLoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, description="Административный пароль")


class TelegramLoginRequest(BaseModel):
    phone: str = Field(description="Номер телефона в формате Telegram")
    password: str = Field(min_length=8)


class UserCreateRequest(BaseModel):
    email: EmailStr | None = None
    full_name: str | None = None
    password: str = Field(min_length=8)
    telegram_phone: str | None = None
    telegram_user_id: int | None = None
    is_admin: bool = False
>>>>>>> e81b75286128c8454dcb0c6fa4879ac1da9358b2


class UserBase(BaseModel):
    id: str
    email: EmailStr | None = None
    full_name: str | None = None
    telegram_phone: str | None = None
    telegram_user_id: int | None = None
    is_admin: bool
    is_active: bool

    class Config:
        from_attributes = True
