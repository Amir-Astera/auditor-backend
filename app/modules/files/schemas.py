from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict


class FileScope(str, Enum):
    ADMIN_LAW = "ADMIN_LAW"
    CUSTOMER_DOC = "CUSTOMER_DOC"


class FileIndexStatus(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    DONE = "DONE"
    ERROR = "ERROR"


class FileUploadResponse(BaseModel):
    id: str
    scope: FileScope
    customer_id: Optional[str] = None
    bucket: str
    object_key: str
    original_filename: str
    is_indexed: bool
    index_status: Optional[FileIndexStatus] = None
    index_error: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class FileInfo(FileUploadResponse):
    content_type: Optional[str] = None
    size_bytes: Optional[int] = None


class FileListResponse(BaseModel):
    items: list[FileInfo]
    total: int


class FileStatusResponse(BaseModel):
    id: str
    scope: FileScope
    customer_id: Optional[str] = None
    original_filename: str
    is_indexed: bool
    index_status: Optional[FileIndexStatus] = None
    index_error: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
    
    @classmethod
    def model_validate(cls, obj, *, strict=None, from_attributes=None, context=None):
        """Override to convert UUID id to string."""
        if hasattr(obj, 'id') and hasattr(obj.id, '__str__'):
            # Create a dict with id as string
            data = {
                "id": str(obj.id),
                "scope": obj.scope,
                "customer_id": obj.customer_id,
                "original_filename": obj.original_filename,
                "is_indexed": obj.is_indexed,
                "index_status": obj.index_status,
                "index_error": obj.index_error,
            }
            return cls(**data)
        return super().model_validate(obj, strict=strict, from_attributes=from_attributes, context=context)


class ChunkSearchResult(BaseModel):
    score: float
    file_id: str
    chunk_index: int
    text: str
    filename: Optional[str] = None
    scope: Optional[FileScope] = None
    customer_id: Optional[str] = None
    owner_id: Optional[str] = None


class ChunkSearchResponse(BaseModel):
    items: list[ChunkSearchResult]
    total: int
