# app/models.py
# IMPORTANT: импортируем все SQLAlchemy модели, чтобы они попали в Base.metadata

from app.modules.auth.models import User  # noqa: F401
from app.modules.customers.models import Customer  # noqa: F401
from app.modules.chats.models import Chat, ChatMessage  # noqa: F401
from app.modules.files.models import StoredFile, FileChunk  # noqa: F401
from app.modules.prompts.models import Prompt  # noqa: F401
# сюда добавляй все остальные модели проекта