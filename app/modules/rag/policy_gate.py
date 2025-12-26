"""
Production Policy Gate for RAG access control.

Features:
- Role-based access control (RBAC)
- Customer-level permissions
- Scope-based filtering (ADMIN_LAW, CUSTOMER_DOC)
- Audit trail logging
- Rate limiting by user tier
"""

import logging
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import json

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.modules.files.models import FileScope

logger = get_logger(__name__)


class UserRole(str, Enum):
    """User roles for access control."""
    ADMIN = "admin"
    EMPLOYEE = "employee"
    CUSTOMER = "customer"
    GUEST = "guest"


class AccessLevel(str, Enum):
    """Access levels for resources."""
    FULL = "full"
    READ_ONLY = "read_only"
    RESTRICTED = "restricted"
    NONE = "none"


@dataclass
class PolicyDecision:
    """Result of policy gate evaluation."""
    allowed: bool
    allowed_scopes: List[str]
    allowed_customer_ids: List[str]
    max_k: int
    max_context_tokens: int
    temperature_range: tuple
    rate_limit_remaining: int
    decision_reason: str
    audit_log: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "allowed": self.allowed,
            "allowed_scopes": self.allowed_scopes,
            "allowed_customer_ids": self.allowed_customer_ids,
            "max_k": self.max_k,
            "max_context_tokens": self.max_context_tokens,
            "temperature_range": self.temperature_range,
            "rate_limit_remaining": self.rate_limit_remaining,
            "decision_reason": self.decision_reason,
        }


@dataclass
class AuditLogEntry:
    """Audit log entry for policy decisions."""
    timestamp: datetime
    user_id: str
    tenant_id: str
    customer_id: Optional[str]
    action: str
    resource_type: str
    decision: str
    reason: str
    request_metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "user_id": self.user_id,
            "tenant_id": self.tenant_id,
            "customer_id": self.customer_id,
            "action": self.action,
            "resource_type": self.resource_type,
            "decision": self.decision,
            "reason": self.reason,
            "request_metadata": self.request_metadata,
        }


class PolicyGate:
    """
    Production policy gate for RAG access control.
    
    Evaluates access permissions based on:
    - User role and permissions
    - Customer assignment
    - Resource scope
    - Rate limits
    """
    
    # Default limits by role
    ROLE_LIMITS = {
        UserRole.ADMIN: {
            "max_k": 20,
            "max_context_tokens": 16000,
            "temperature_range": (0.0, 2.0),
            "rate_limit_per_hour": 1000,
        },
        UserRole.EMPLOYEE: {
            "max_k": 15,
            "max_context_tokens": 12000,
            "temperature_range": (0.0, 1.5),
            "rate_limit_per_hour": 500,
        },
        UserRole.CUSTOMER: {
            "max_k": 10,
            "max_context_tokens": 8000,
            "temperature_range": (0.0, 1.0),
            "rate_limit_per_hour": 100,
        },
        UserRole.GUEST: {
            "max_k": 5,
            "max_context_tokens": 4000,
            "temperature_range": (0.3, 0.7),
            "rate_limit_per_hour": 10,
        },
    }
    
    def __init__(self, db: Session):
        self.db = db
        self._rate_limit_cache: Dict[str, Dict] = {}
    
    def evaluate(
        self,
        user_id: str,
        tenant_id: str,
        customer_id: Optional[str],
        requested_scopes: List[str],
        action: str = "rag_query",
    ) -> PolicyDecision:
        """
        Evaluate access policy for a RAG request.
        
        Args:
            user_id: ID of requesting user
            tenant_id: Tenant context
            customer_id: Target customer (if applicable)
            requested_scopes: Requested document scopes
            action: Type of action being performed
            
        Returns:
            PolicyDecision with access permissions
        """
        # 1. Get user info and role
        user_info = self._get_user_info(user_id)
        if not user_info:
            return self._deny("User not found")
        
        role = UserRole(user_info.get("role", "guest"))
        is_admin = user_info.get("is_admin", False)
        
        # 2. Check rate limits
        rate_limit_ok, remaining = self._check_rate_limit(user_id, role)
        if not rate_limit_ok:
            return self._deny("Rate limit exceeded", rate_limit_remaining=0)
        
        # 3. Determine allowed scopes
        allowed_scopes = self._get_allowed_scopes(
            role=role,
            is_admin=is_admin,
            requested_scopes=requested_scopes,
        )
        
        if not allowed_scopes:
            return self._deny("No access to requested scopes")
        
        # 4. Determine allowed customers
        allowed_customer_ids = self._get_allowed_customers(
            user_id=user_id,
            role=role,
            is_admin=is_admin,
            requested_customer_id=customer_id,
        )
        
        # For CUSTOMER_DOC scope, must have customer access
        if FileScope.CUSTOMER_DOC.value in allowed_scopes:
            if not allowed_customer_ids:
                allowed_scopes.remove(FileScope.CUSTOMER_DOC.value)
        
        if not allowed_scopes:
            return self._deny("No access to customer documents")
        
        # 5. Get limits for role
        limits = self.ROLE_LIMITS.get(role, self.ROLE_LIMITS[UserRole.GUEST])
        
        # 6. Build audit log
        audit_entry = AuditLogEntry(
            timestamp=datetime.utcnow(),
            user_id=user_id,
            tenant_id=tenant_id,
            customer_id=customer_id,
            action=action,
            resource_type="rag_documents",
            decision="allowed",
            reason=f"Access granted for role {role.value}",
            request_metadata={
                "requested_scopes": requested_scopes,
                "allowed_scopes": allowed_scopes,
                "allowed_customers": allowed_customer_ids,
            },
        )
        
        # Log audit entry
        self._log_audit(audit_entry)
        
        # 7. Return decision
        return PolicyDecision(
            allowed=True,
            allowed_scopes=allowed_scopes,
            allowed_customer_ids=allowed_customer_ids,
            max_k=limits["max_k"],
            max_context_tokens=limits["max_context_tokens"],
            temperature_range=limits["temperature_range"],
            rate_limit_remaining=remaining,
            decision_reason=f"Access granted for {role.value}",
            audit_log=audit_entry.to_dict(),
        )
    
    def _get_user_info(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user information from database."""
        try:
            from app.modules.auth.models import User
            
            user = self.db.query(User).get(user_id)
            if not user:
                return None
            
            return {
                "id": str(user.id),
                "role": "admin" if user.is_admin else "employee",
                "is_admin": user.is_admin,
                "is_active": user.is_active,
            }
        except Exception as e:
            logger.error(f"Failed to get user info: {e}")
            return None
    
    def _get_allowed_scopes(
        self,
        role: UserRole,
        is_admin: bool,
        requested_scopes: List[str],
    ) -> List[str]:
        """Determine allowed scopes based on role."""
        allowed = []
        
        # Admin can access all scopes
        if is_admin or role == UserRole.ADMIN:
            return [s for s in requested_scopes if s in [FileScope.ADMIN_LAW.value, FileScope.CUSTOMER_DOC.value]]
        
        # Employee can access ADMIN_LAW and assigned customer docs
        if role == UserRole.EMPLOYEE:
            if FileScope.ADMIN_LAW.value in requested_scopes:
                allowed.append(FileScope.ADMIN_LAW.value)
            if FileScope.CUSTOMER_DOC.value in requested_scopes:
                allowed.append(FileScope.CUSTOMER_DOC.value)
            return allowed
        
        # Customer can only access their own docs
        if role == UserRole.CUSTOMER:
            if FileScope.CUSTOMER_DOC.value in requested_scopes:
                allowed.append(FileScope.CUSTOMER_DOC.value)
            return allowed
        
        # Guest has no access
        return []
    
    def _get_allowed_customers(
        self,
        user_id: str,
        role: UserRole,
        is_admin: bool,
        requested_customer_id: Optional[str],
    ) -> List[str]:
        """Determine allowed customer IDs."""
        # Admin can access all customers
        if is_admin or role == UserRole.ADMIN:
            return [requested_customer_id] if requested_customer_id else []
        
        # Employee can access assigned customers
        if role == UserRole.EMPLOYEE:
            assigned_customers = self._get_assigned_customers(user_id)
            
            if requested_customer_id:
                if requested_customer_id in assigned_customers:
                    return [requested_customer_id]
                return []
            
            return assigned_customers
        
        # Customer can only access their own
        if role == UserRole.CUSTOMER:
            # Customer's own customer_id would be in their profile
            return [requested_customer_id] if requested_customer_id else []
        
        return []
    
    def _get_assigned_customers(self, user_id: str) -> List[str]:
        """Get customers assigned to an employee."""
        try:
            from app.modules.customers.models import Customer
            
            customers = self.db.query(Customer).filter(
                Customer.assigned_employee_id == user_id
            ).all()
            
            return [str(c.id) for c in customers]
        except Exception as e:
            logger.error(f"Failed to get assigned customers: {e}")
            return []
    
    def _check_rate_limit(self, user_id: str, role: UserRole) -> tuple:
        """Check and update rate limit for user."""
        limits = self.ROLE_LIMITS.get(role, self.ROLE_LIMITS[UserRole.GUEST])
        max_requests = limits["rate_limit_per_hour"]
        
        # Simple in-memory rate limiting (should use Redis in production)
        now = datetime.utcnow()
        cache_key = f"rate_limit:{user_id}"
        
        if cache_key not in self._rate_limit_cache:
            self._rate_limit_cache[cache_key] = {
                "count": 0,
                "window_start": now,
            }
        
        cache = self._rate_limit_cache[cache_key]
        
        # Reset window if expired (1 hour)
        window_age = (now - cache["window_start"]).total_seconds()
        if window_age > 3600:
            cache["count"] = 0
            cache["window_start"] = now
        
        # Check limit
        if cache["count"] >= max_requests:
            return False, 0
        
        # Increment counter
        cache["count"] += 1
        remaining = max_requests - cache["count"]
        
        return True, remaining
    
    def _deny(
        self,
        reason: str,
        rate_limit_remaining: int = 0,
    ) -> PolicyDecision:
        """Create denial decision."""
        logger.warning(f"Policy gate denied: {reason}")
        
        return PolicyDecision(
            allowed=False,
            allowed_scopes=[],
            allowed_customer_ids=[],
            max_k=0,
            max_context_tokens=0,
            temperature_range=(0.0, 0.0),
            rate_limit_remaining=rate_limit_remaining,
            decision_reason=reason,
            audit_log={
                "decision": "denied",
                "reason": reason,
                "timestamp": datetime.utcnow().isoformat(),
            },
        )
    
    def _log_audit(self, entry: AuditLogEntry):
        """Log audit entry to database or file."""
        # In production, save to audit_logs table
        logger.info(
            f"AUDIT: {entry.action} by {entry.user_id} - {entry.decision}",
            extra=entry.to_dict(),
        )
        
        # TODO: Save to database
        # audit_log = AuditLog(**entry.to_dict())
        # self.db.add(audit_log)
        # self.db.commit()


class PolicyGateFactory:
    """Factory for creating PolicyGate instances."""
    
    @staticmethod
    def create(db: Session) -> PolicyGate:
        """Create PolicyGate with database session."""
        return PolicyGate(db=db)
