import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class FileScope(str, enum.Enum):
    ADMIN_LAW = "ADMIN_LAW"
    CUSTOMER_DOC = "CUSTOMER_DOC"


class FileIndexStatus(str, enum.Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    DONE = "DONE"
    ERROR = "ERROR"


class StoredFile(Base):
    __tablename__ = "stored_files"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )

    customer_id: Mapped[str | None] = mapped_column(String, nullable=True)

    scope: Mapped[FileScope] = mapped_column(Enum(FileScope), nullable=False)

    bucket: Mapped[str] = mapped_column(String, nullable=False)
    object_key: Mapped[str] = mapped_column(String, nullable=False)

    original_filename: Mapped[str] = mapped_column(String, nullable=False)
    content_type: Mapped[str | None] = mapped_column(String, nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    is_indexed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    index_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    index_status: Mapped[FileIndexStatus] = mapped_column(
        Enum(FileIndexStatus),
        default=FileIndexStatus.QUEUED,
        nullable=False,
    )
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    chunks: Mapped[list["FileChunk"]] = relationship(
        "FileChunk",
        back_populates="file",
        cascade="all, delete-orphan",
    )


class FileChunk(Base):
    __tablename__ = "file_chunks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    file_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("stored_files.id"),
        nullable=False,
    )

    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)

    text: Mapped[str] = mapped_column(Text, nullable=False)

    qdrant_point_id: Mapped[str | None] = mapped_column(String, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    file: Mapped[StoredFile] = relationship("StoredFile", back_populates="chunks")