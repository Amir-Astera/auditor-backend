"""Dynamic prompts service for database management."""
import json
import logging
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session

from app.modules.prompts.models import (
    Prompt, PromptVersion, PromptTemplate, PromptCategory, PromptStatus
)
from app.core.logging import get_logger

logger = get_logger(__name__)


class PromptsService:
    """Service for managing dynamic prompts."""
    
    def __init__(self, db: Session):
        self.db = db
        self._cache = {}  # Simple cache for active prompts
    
    def get_active_prompt(
        self,
        name: str,
        category: Optional[PromptCategory] = None,
        language: str = "EN"
    ) -> Optional[Prompt]:
        """
        Get active prompt by name with caching.
        """
        cache_key = f"{name}_{category}_{language}"
        
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        query = self.db.query(Prompt).filter(
            Prompt.name == name,
            Prompt.status == PromptStatus.ACTIVE,
            Prompt.language == language
        )
        
        if category:
            query = query.filter(Prompt.category == category)
        
        prompt = query.first()
        
        if prompt:
            self._cache[cache_key] = prompt
            logger.info(f"Loaded active prompt: {prompt.name} v{prompt.version}")
        else:
            logger.warning(f"Active prompt not found: {name}")
        
        return prompt
    
    def get_prompt_by_id(self, prompt_id: str) -> Optional[Prompt]:
        """Get prompt by ID."""
        return self.db.query(Prompt).get(prompt_id)
    
    def create_prompt(
        self,
        name: str,
        display_name: str,
        content: str,
        category: PromptCategory,
        author_id: str,
        description: Optional[str] = None,
        variables: Optional[Dict[str, Any]] = None,
        language: str = "EN",
        priority: int = 0,
    ) -> Prompt:
        """
        Create new prompt.
        """
        # Check if prompt with this name already exists
        existing = self.db.query(Prompt).filter(Prompt.name == name).first()
        if existing:
            raise ValueError(f"Prompt with name '{name}' already exists")
        
        prompt = Prompt(
            name=name,
            display_name=display_name,
            description=description,
            category=category,
            content=content,
            variables=json.dumps(variables or {}),
            author_id=author_id,
            language=language,
            priority=priority,
        )
        
        self.db.add(prompt)
        self.db.commit()
        self.db.refresh(prompt)
        
        # Create initial version
        self._create_version(prompt, content, "Initial version", author_id)
        
        # Clear cache
        self._clear_cache_for_name(name)
        
        logger.info(f"Created prompt: {prompt.name}")
        return prompt
    
    def update_prompt(
        self,
        prompt_id: str,
        content: Optional[str] = None,
        display_name: Optional[str] = None,
        description: Optional[str] = None,
        variables: Optional[Dict[str, Any]] = None,
        status: Optional[PromptStatus] = None,
        priority: Optional[int] = None,
        updated_by_id: Optional[str] = None,
        change_summary: Optional[str] = None,
    ) -> Prompt:
        """
        Update existing prompt with version tracking.
        """
        prompt = self.db.query(Prompt).get(prompt_id)
        if not prompt:
            raise ValueError(f"Prompt not found: {prompt_id}")
        
        old_content = prompt.content
        
        # Update fields
        if display_name is not None:
            prompt.display_name = display_name
        if description is not None:
            prompt.description = description
        if variables is not None:
            prompt.variables = json.dumps(variables)
        if status is not None:
            prompt.status = status
        if priority is not None:
            prompt.priority = priority
        
        # Update content and create version if changed
        if content is not None and content != old_content:
            prompt.content = content
            if updated_by_id:
                self._create_version(prompt, content, change_summary or "Content updated", updated_by_id)
        
        self.db.commit()
        self.db.refresh(prompt)
        
        # Clear cache
        self._clear_cache_for_name(prompt.name)
        
        logger.info(f"Updated prompt: {prompt.name}")
        return prompt
    
    def activate_prompt(self, prompt_id: str, activated_by_id: str) -> Prompt:
        """Activate prompt and deactivate others with same name."""
        prompt = self.db.query(Prompt).get(prompt_id)
        if not prompt:
            raise ValueError(f"Prompt not found: {prompt_id}")
        
        # Deactivate other prompts with same name
        self.db.query(Prompt).filter(
            Prompt.name == prompt.name,
            Prompt.id != prompt_id,
            Prompt.status == PromptStatus.ACTIVE
        ).update({"status": PromptStatus.DRAFT})
        
        # Activate this prompt
        prompt.status = PromptStatus.ACTIVE
        
        self.db.commit()
        
        # Clear cache
        self._clear_cache_for_name(prompt.name)
        
        logger.info(f"Activated prompt: {prompt.name}")
        return prompt
    
    def list_prompts(
        self,
        category: Optional[PromptCategory] = None,
        status: Optional[PromptStatus] = None,
        language: str = "EN",
        author_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Prompt]:
        """List prompts with filters."""
        query = self.db.query(Prompt)
        
        if category:
            query = query.filter(Prompt.category == category)
        if status:
            query = query.filter(Prompt.status == status)
        if language:
            query = query.filter(Prompt.language == language)
        if author_id:
            query = query.filter(Prompt.author_id == author_id)
        
        return query.order_by(Prompt.priority.desc(), Prompt.name.asc()).offset(offset).limit(limit).all()
    
    def get_prompt_versions(self, prompt_id: str) -> List[PromptVersion]:
        """Get version history for a prompt."""
        return self.db.query(PromptVersion).filter(
            PromptVersion.prompt_id == prompt_id
        ).order_by(PromptVersion.created_at.desc()).all()
    
    def render_prompt(
        self,
        prompt_name: str,
        variables: Dict[str, Any],
        category: Optional[PromptCategory] = None,
        language: str = "EN"
    ) -> str:
        """
        Render prompt with variables.
        """
        prompt = self.get_active_prompt(prompt_name, category, language)
        if not prompt:
            raise ValueError(f"Active prompt not found: {prompt_name}")
        
        content = prompt.content
        
        # Simple template rendering
        for key, value in variables.items():
            placeholder = f"{{{{{key}}}}}"
            content = content.replace(placeholder, str(value))
        
        return content
    
    def search_prompts(
        self,
        query: str,
        category: Optional[PromptCategory] = None,
        limit: int = 20
    ) -> List[Prompt]:
        """Search prompts by content."""
        db_query = self.db.query(Prompt).filter(
            Prompt.content.ilike(f"%{query}%") |
            Prompt.display_name.ilike(f"%{query}%") |
            Prompt.description.ilike(f"%{query}%")
        )
        
        if category:
            db_query = db_query.filter(Prompt.category == category)
        
        return db_query.order_by(Prompt.usage_count.desc()).limit(limit).all()
    
    def log_usage(
        self,
        prompt_id: str,
        user_id: str,
        customer_id: Optional[str],
        query_type: Optional[str],
        tokens_used: Optional[int],
        response_time_ms: Optional[int],
        success: bool,
        error_message: Optional[str] = None,
        user_feedback: Optional[int] = None,
    ):
        """Log prompt usage for analytics."""
        from app.modules.prompts.models import PromptUsageLog
        
        # Update usage count
        prompt = self.db.query(Prompt).get(prompt_id)
        if prompt:
            prompt.usage_count += 1
            prompt.last_used_at = datetime.utcnow()
        
        # Create usage log
        usage_log = PromptUsageLog(
            prompt_id=prompt_id,
            user_id=user_id,
            customer_id=customer_id,
            query_type=query_type,
            tokens_used=tokens_used,
            response_time_ms=response_time_ms,
            success=success,
            error_message=error_message,
            user_feedback=user_feedback,
        )
        
        self.db.add(usage_log)
        self.db.commit()
    
    def get_usage_stats(
        self,
        prompt_id: Optional[str] = None,
        days: int = 30
    ) -> Dict[str, Any]:
        """Get usage statistics for prompts."""
        from datetime import datetime, timedelta
        from sqlalchemy import func
        
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        query = self.db.query(PromptUsageLog).filter(
            PromptUsageLog.used_at >= cutoff_date
        )
        
        if prompt_id:
            query = query.filter(PromptUsageLog.prompt_id == prompt_id)
        
        # Basic stats
        total_usage = query.count()
        success_rate = query.filter(PromptUsageLog.success == True).count()
        avg_tokens = query.filter(PromptUsageLog.tokens_used.isnot(None)).with_entities(
            func.avg(PromptUsageLog.tokens_used)
        ).scalar() or 0
        avg_response_time = query.filter(PromptUsageLog.response_time_ms.isnot(None)).with_entities(
            func.avg(PromptUsageLog.response_time_ms)
        ).scalar() or 0
        
        return {
            "total_usage": total_usage,
            "success_rate": success_rate / total_usage if total_usage > 0 else 0,
            "avg_tokens": round(avg_tokens, 1),
            "avg_response_time_ms": round(avg_response_time, 1),
            "days": days,
        }
    
    def _create_version(self, prompt: Prompt, content: str, summary: str, created_by_id: str):
        """Create a new version of a prompt."""
        # Increment version
        last_version = self.db.query(PromptVersion).filter(
            PromptVersion.prompt_id == prompt.id
        ).order_by(PromptVersion.created_at.desc()).first()
        
        if last_version:
            # Simple version increment
            try:
                version_num = int(last_version.version.split('.')[-1]) + 1
                new_version = f"1.{version_num}"
            except (ValueError, IndexError):
                new_version = "1.1"
        else:
            new_version = "1.0"
        
        version = PromptVersion(
            prompt_id=prompt.id,
            version=new_version,
            content=content,
            change_summary=summary,
            created_by_id=created_by_id,
        )
        
        self.db.add(version)
        return version
    
    def _clear_cache_for_name(self, name: str):
        """Clear cache entries for a prompt name."""
        keys_to_remove = [key for key in self._cache.keys() if key.startswith(f"{name}_")]
        for key in keys_to_remove:
            del self._cache[key]
    
    def initialize_default_prompts(self, admin_user_id: str):
        """Initialize system with default prompts from files."""
        import os
        from pathlib import Path
        
        prompts_dir = Path(__file__).parent.parent.parent / "prompts"
        
        # Map file names to categories
        file_mapping = {
            "A1_StyleGuide_v1.txt": PromptCategory.STYLE_GUIDE,
            "A2_ISA_RoutingPrompts_v1.txt": PromptCategory.ROUTING,
            "A3_Acceptance_Routing_v1.txt": PromptCategory.ACCEPTANCE,
            "A4_Understanding_Entity_Routing_v1.txt": PromptCategory.ENTITY_ROUTING,
            "A5_Opinion_Routing_v1.txt": PromptCategory.OPINION_ROUTING,
            "A6_Model_IO_Guide_v1.txt": PromptCategory.MODEL_IO_GUIDE,
        }
        
        for filename, category in file_mapping.items():
            file_path = prompts_dir / filename
            if file_path.exists():
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # Extract name from filename
                    name = filename.replace('.txt', '')
                    display_name = name.replace('_', ' ').replace('v1', 'v1.0')
                    
                    # Check if already exists
                    existing = self.db.query(Prompt).filter(Prompt.name == name).first()
                    if not existing:
                        self.create_prompt(
                            name=name,
                            display_name=display_name,
                            content=content,
                            category=category,
                            author_id=admin_user_id,
                            description=f"System prompt from {filename}",
                            language="EN",
                            priority=100,  # High priority for system prompts
                        )
                        
                        # Activate the prompt
                        prompt = self.get_active_prompt(name, category)
                        if prompt:
                            self.activate_prompt(prompt.id, admin_user_id)
                        
                        logger.info(f"Initialized default prompt: {name}")
                    else:
                        logger.info(f"Prompt already exists: {name}")
                        
                except Exception as e:
                    logger.error(f"Failed to initialize prompt {filename}: {e}")
            else:
                logger.warning(f"Prompt file not found: {file_path}")
