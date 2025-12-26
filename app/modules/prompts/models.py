"""Dynamic prompts models for database storage."""
import enum
import uuid
from datetime import datetime

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


class PromptCategory(str, enum.Enum):
    """Categories of prompts."""
    STYLE_GUIDE = "STYLE_GUIDE"
    ROUTING = "ROUTING"
    ACCEPTANCE = "ACCEPTANCE"
    ENTITY_ROUTING = "ENTITY_ROUTING"
    OPINION_ROUTING = "OPINION_ROUTING"
    MODEL_IO_GUIDE = "MODEL_IO_GUIDE"
    RISK_LIBRARY = "RISK_LIBRARY"
    GLOSSARY = "GLOSSARY"
    TEMPLATES = "TEMPLATES"
    PLAYBOOKS = "PLAYBOOKS"


class PromptStatus(str, enum.Enum):
    """Prompt status."""
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"


class Prompt(Base):
    """Dynamic prompt stored in database."""
    __tablename__ = "prompts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Basic info
    name = Column(String(255), nullable=False, unique=True)
    display_name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    version = Column(String(50), nullable=False, default="1.0")
    
    # Classification
    category = Column(Enum(PromptCategory), nullable=False)
    status = Column(Enum(PromptStatus), nullable=False, default=PromptStatus.DRAFT)
    
    # Content
    content = Column(Text, nullable=False)
    variables = Column(Text, nullable=True)  # JSON string of template variables
    
    # Metadata
    author_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    language = Column(String(10), nullable=False, default="EN")
    priority = Column(Integer, nullable=False, default=0)  # Higher = more important
    
    # Usage tracking
    usage_count = Column(Integer, nullable=False, default=0)
    last_used_at = Column(DateTime, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    author = relationship("User")
    versions = relationship("PromptVersion", back_populates="prompt", cascade="all, delete-orphan")


class PromptVersion(Base):
    """Version history for prompts."""
    __tablename__ = "prompt_versions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    prompt_id = Column(UUID(as_uuid=True), ForeignKey("prompts.id"), nullable=False)
    
    version = Column(String(50), nullable=False)
    content = Column(Text, nullable=False)
    change_summary = Column(Text, nullable=True)
    
    created_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    prompt = relationship("Prompt", back_populates="versions")
    created_by = relationship("User")


class PromptTemplate(Base):
    """Reusable prompt templates with variables."""
    __tablename__ = "prompt_templates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    name = Column(String(255), nullable=False, unique=True)
    display_name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    
    # Template content with placeholders like {{variable_name}}
    template = Column(Text, nullable=False)
    variables_schema = Column(Text, nullable=True)  # JSON schema for variables
    
    category = Column(Enum(PromptCategory), nullable=False)
    is_system = Column(Boolean, default=False)  # System templates can't be deleted
    
    created_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    created_by = relationship("User")


class PromptUsageLog(Base):
    """Logging of prompt usage for analytics."""
    __tablename__ = "prompt_usage_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    prompt_id = Column(UUID(as_uuid=True), ForeignKey("prompts.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=True)
    
    # Context
    query_type = Column(String(100), nullable=True)  # e.g., "legal_question", "materiality_calc"
    tokens_used = Column(Integer, nullable=True)
    response_time_ms = Column(Integer, nullable=True)
    
    # Outcome
    success = Column(Boolean, nullable=False)
    error_message = Column(Text, nullable=True)
    user_feedback = Column(Integer, nullable=True)  # 1-5 rating
    
    used_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    prompt = relationship("Prompt")
    user = relationship("User")
    customer = relationship("Customer")
