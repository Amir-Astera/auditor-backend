import uuid
from datetime import datetime
import enum

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.db import Base


class FileScope(str, enum.Enum):
    ADMIN_LAW = "ADMIN_LAW"
    CUSTOMER_DOC = "CUSTOMER_DOC"


class StoredFile(Base):
    __tablename__ = "stored_files"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    customer_id = Column(String, nullable=True)

    scope = Column(Enum(FileScope), nullable=False)

    bucket = Column(String, nullable=False)
    object_key = Column(String, nullable=False)

    original_filename = Column(String, nullable=False)
    content_type = Column(String, nullable=True)
    size_bytes = Column(Integer, nullable=True)

    description = Column(Text, nullable=True)

    uploaded_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    is_indexed = Column(Boolean, default=False, nullable=False)
    index_error = Column(Text, nullable=True)

    chunks = relationship(
        "FileChunk",
        back_populates="file",
        cascade="all, delete-orphan",
    )


class FileChunk(Base):
    __tablename__ = "file_chunks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    file_id = Column(UUID(as_uuid=True), ForeignKey("stored_files.id"), nullable=False)

    chunk_index = Column(Integer, nullable=False)

    text = Column(Text, nullable=False)

    qdrant_point_id = Column(String, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    file = relationship("StoredFile", back_populates="chunks")
