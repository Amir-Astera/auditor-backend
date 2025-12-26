from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.auth.models import User
from app.modules.auth.router import get_current_employee
from app.modules.chats.models import Chat, ChatMessage, SenderType
from app.modules.chats.service import ChatService
from app.modules.chats.schemas import (
    ChatBase,
    ChatCreate,
    ChatMessageBase,
    ChatMessageCreate,
    ChatWithMessages,
)
from app.modules.customers.models import Customer
from app.modules.rag.service import RAGService
from app.modules.rag.router import _get_rag_service

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


def _get_chat_service(
    db: Session = Depends(get_db),
    rag_service: RAGService = Depends(_get_rag_service),
) -> ChatService:
    """Создает экземпляр ChatService с RAG."""
    return ChatService(db=db, rag_service=rag_service)


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
    
    chat_service = ChatService(db=db)
    chat = chat_service.create_chat(
        customer_id=str(customer_id),
        user_id=str(current_user.id),
        title=payload.title,
    )
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
    response_model=dict,
    summary="Отправить сообщение в чат с RAG ответом",
)
async def send_message_with_rag(
    customer_id: UUID,
    chat_id: UUID,
    payload: ChatMessageCreate,
    chat_service: ChatService = Depends(_get_chat_service),
    current_user: User = Depends(get_current_employee),
):
    """
    Отправляет сообщение в чат и получает ответ от RAG системы.
    
    Ответ включает:
    - Сохраненное сообщение пользователя
    - Ответ ассистента от RAG системы
    - Использованные источники документов
    - Контекст поиска
    """
    _ensure_customer_access(chat_service.db, customer_id, current_user)
    
    # Проверяем существование чата
    chat = chat_service.get_chat_with_messages(str(chat_id), str(current_user.id))
    if not chat or chat.customer_id != customer_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found"
        )
    
    try:
        result = await chat_service.send_message_with_rag(
            chat_id=str(chat_id),
            user_message=payload.content,
            customer_id=str(customer_id),
            user_id=str(current_user.id),
            tenant_id=str(customer_id),
            include_admin_laws=True,  # Можно сделать параметром запроса
            include_customer_docs=True,
        )
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="RAG service not available"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing message: {str(e)}"
        )

