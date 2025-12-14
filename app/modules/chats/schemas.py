from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.modules.chats.models import SenderType


class ChatCreate(BaseModel):
    title: str | None = Field(None, description="Название/тема чата")


class ChatBase(BaseModel):
    id: UUID
    customer_id: UUID
    created_by_id: UUID
    title: str | None
    is_archived: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True


class ChatMessageCreate(BaseModel):
    content: str = Field(..., description="Текст сообщения сотрудника")


class ChatMessageBase(BaseModel):
    id: UUID
    chat_id: UUID
    sender_type: SenderType
    sender_id: UUID | None
    role: str
    content: str
    created_at: datetime

    class Config:
        orm_mode = True


class ChatWithMessages(ChatBase):
    messages: list[ChatMessageBase]