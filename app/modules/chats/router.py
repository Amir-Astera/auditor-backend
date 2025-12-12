from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.auth.models import User
from app.modules.auth.router import get_current_employee
from app.modules.chats.models import Chat, ChatMessage, SenderType
from app.modules.chats.schemas import (
    ChatBase,
    ChatCreate,
    ChatMessageBase,
    ChatMessageCreate,
    ChatWithMessages,
)
from app.modules.customers.models import Customer

router = APIRouter(prefix="/customers/{customer_id}/chats", tags=["chats"])


def _ensure_customer_access(
    db: Session,
    customer_id: UUID,
    user: User,
) -> Customer:
    customer = db.query(Customer).get(customer_id)
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found"
        )

    if customer.assigned_employee_id != user.id and not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    return customer


@router.post(
    "",
    response_model=ChatBase,
    summary="Создать чат для заказчика",
)
def create_chat(
    customer_id: UUID,
    payload: ChatCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_employee),
):
    _ensure_customer_access(db, customer_id, current_user)

    chat = Chat(
        customer_id=customer_id,
        created_by_id=current_user.id,
        title=payload.title,
    )
    db.add(chat)
    db.commit()
    db.refresh(chat)
    return chat


@router.get(
    "",
    response_model=list[ChatBase],
    summary="Список чатов заказчика",
)
def list_chats(
    customer_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_employee),
):
    _ensure_customer_access(db, customer_id, current_user)

    chats = (
        db.query(Chat)
        .filter(Chat.customer_id == customer_id)
        .order_by(Chat.created_at.desc())
        .all()
    )
    return chats


@router.get(
    "/{chat_id}",
    response_model=ChatWithMessages,
    summary="Получить чат с сообщениями",
)
def get_chat(
    customer_id: UUID,
    chat_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_employee),
):
    _ensure_customer_access(db, customer_id, current_user)

    chat = db.query(Chat).get(chat_id)
    if not chat or chat.customer_id != customer_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found"
        )

    return chat


@router.post(
    "/{chat_id}/messages",
    response_model=ChatMessageBase,
    summary="Отправить сообщение в чат (сотрудник)",
)
def send_message(
    customer_id: UUID,
    chat_id: UUID,
    payload: ChatMessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_employee),
):
    _ensure_customer_access(db, customer_id, current_user)

    chat = db.query(Chat).get(chat_id)
    if not chat or chat.customer_id != customer_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found"
        )

    message = ChatMessage(
        chat_id=chat_id,
        sender_type=SenderType.EMPLOYEE,
        sender_id=current_user.id,
        role="user",
        content=payload.content,
    )
    db.add(message)
    db.commit()
    db.refresh(message)

    # Здесь позже можно вызывать Gemini и сохранять ответ как отдельное сообщение:
    # assistant_message = ChatMessage(...)
    # db.add(assistant_message)
    # db.commit()

    return message
