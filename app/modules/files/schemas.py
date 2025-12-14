from enum import Enum
from typing import Optional

from pydantic import BaseModel


class FileScope(str, Enum):
    ADMIN_LAW = "ADMIN_LAW"
    CUSTOMER_DOC = "CUSTOMER_DOC"


class FileUploadResponse(BaseModel):
    id: str
    scope: FileScope
    customer_id: Optional[str] = None
    bucket: str
    object_key: str
    original_filename: str
    is_indexed: bool

    class Config:
        orm_mode = True


class FileInfo(FileUploadResponse):
    content_type: Optional[str] = None
    size_bytes: Optional[int] = None


class FileListResponse(BaseModel):
    items: list[FileInfo]
    total: int


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