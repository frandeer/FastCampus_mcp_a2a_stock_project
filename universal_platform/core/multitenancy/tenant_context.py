"""
Thread-local tenant context management.

Provides thread-safe access to current tenant information throughout the application
without requiring explicit tenant parameter passing. Uses contextvars for async-safe
context management.
"""

import contextvars
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional, Union
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class TenantInfo(BaseModel):
    """Tenant information model."""
    
    tenant_id: str = Field(..., description="Unique tenant identifier")
    tenant_name: str = Field(..., description="Human-readable tenant name")
    schema_name: Optional[str] = Field(None, description="Database schema name")
    domain: Optional[str] = Field(None, description="Primary domain")
    subdomain: Optional[str] = Field(None, description="Subdomain")
    is_active: bool = Field(True, description="Whether tenant is active")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional tenant metadata")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


@dataclass
class TenantContext:
    """
    Container for tenant context information.
    
    This class holds all tenant-related context that should be available
    throughout the request lifecycle.
    """
    
    tenant: TenantInfo
    request_id: str = field(default_factory=lambda: str(uuid4()))
    user_id: Optional[str] = None
    permissions: set = field(default_factory=set)
    features: Dict[str, bool] = field(default_factory=dict)
    settings: Dict[str, Any] = field(default_factory=dict)
    cache_prefix: str = field(init=False)
    
    def __post_init__(self):
        """Initialize computed fields after dataclass initialization."""
        self.cache_prefix = f"tenant:{self.tenant.tenant_id}"
    
    @property
    def tenant_id(self) -> str:
        """Get the tenant ID."""
        return self.tenant.tenant_id
    
    @property
    def tenant_name(self) -> str:
        """Get the tenant name."""
        return self.tenant.tenant_name
    
    @property
    def schema_name(self) -> Optional[str]:
        """Get the database schema name."""
        return self.tenant.schema_name
    
    def has_permission(self, permission: str) -> bool:
        """Check if current context has a specific permission."""
        return permission in self.permissions
    
    def has_feature(self, feature: str) -> bool:
        """Check if a feature is enabled for this tenant."""
        return self.features.get(feature, False)
    
    def get_setting(self, key: str, default: Any = None) -> Any:
        """Get a tenant-specific setting."""
        return self.settings.get(key, default)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary for serialization."""
        return {
            "tenant": self.tenant.dict(),
            "request_id": self.request_id,
            "user_id": self.user_id,
            "permissions": list(self.permissions),
            "features": self.features,
            "settings": self.settings,
            "cache_prefix": self.cache_prefix,
        }


# Context variable for async-safe tenant context storage
_tenant_context: contextvars.ContextVar[Optional[TenantContext]] = contextvars.ContextVar(
    'tenant_context', 
    default=None
)

# Thread-local storage for sync contexts (fallback)
_thread_local = threading.local()


class TenantContextError(Exception):
    """Exception raised when tenant context operations fail."""
    pass


class NoTenantContextError(TenantContextError):
    """Exception raised when no tenant context is available."""
    pass


def get_current_tenant() -> TenantContext:
    """
    Get the current tenant context.
    
    Returns:
        TenantContext: The current tenant context
        
    Raises:
        NoTenantContextError: If no tenant context is set
    """
    # Try contextvars first (async-safe)
    context = _tenant_context.get()
    if context is not None:
        return context
    
    # Fallback to thread-local storage
    context = getattr(_thread_local, 'tenant_context', None)
    if context is not None:
        return context
    
    raise NoTenantContextError("No tenant context is currently set")


def get_current_tenant_safe() -> Optional[TenantContext]:
    """
    Get the current tenant context without raising an exception.
    
    Returns:
        Optional[TenantContext]: The current tenant context or None
    """
    try:
        return get_current_tenant()
    except NoTenantContextError:
        return None


def set_current_tenant(context: TenantContext) -> None:
    """
    Set the current tenant context.
    
    Args:
        context: The tenant context to set
    """
    # Set in contextvars (async-safe)
    _tenant_context.set(context)
    
    # Also set in thread-local storage for sync contexts
    _thread_local.tenant_context = context


def clear_tenant_context() -> None:
    """Clear the current tenant context."""
    # Clear contextvars
    _tenant_context.set(None)
    
    # Clear thread-local storage
    if hasattr(_thread_local, 'tenant_context'):
        delattr(_thread_local, 'tenant_context')


@contextmanager
def tenant_context(context: TenantContext):
    """
    Context manager for temporary tenant context switching.
    
    Args:
        context: The tenant context to use within the context
        
    Example:
        >>> tenant = TenantInfo(tenant_id="tenant1", tenant_name="Tenant 1")
        >>> ctx = TenantContext(tenant=tenant)
        >>> with tenant_context(ctx):
        ...     # Code here runs with the specified tenant context
        ...     current = get_current_tenant()
        ...     assert current.tenant_id == "tenant1"
    """
    previous_context = get_current_tenant_safe()
    
    try:
        set_current_tenant(context)
        yield context
    finally:
        if previous_context is not None:
            set_current_tenant(previous_context)
        else:
            clear_tenant_context()


def get_current_tenant_id() -> str:
    """
    Get the current tenant ID.
    
    Returns:
        str: The current tenant ID
        
    Raises:
        NoTenantContextError: If no tenant context is set
    """
    return get_current_tenant().tenant_id


def get_current_tenant_id_safe() -> Optional[str]:
    """
    Get the current tenant ID without raising an exception.
    
    Returns:
        Optional[str]: The current tenant ID or None
    """
    context = get_current_tenant_safe()
    return context.tenant_id if context else None


def get_current_schema_name() -> Optional[str]:
    """
    Get the current tenant's schema name.
    
    Returns:
        Optional[str]: The current tenant's schema name
        
    Raises:
        NoTenantContextError: If no tenant context is set
    """
    return get_current_tenant().schema_name


def get_cache_key(key: str) -> str:
    """
    Generate a tenant-aware cache key.
    
    Args:
        key: The base cache key
        
    Returns:
        str: The prefixed cache key
        
    Raises:
        NoTenantContextError: If no tenant context is set
    """
    context = get_current_tenant()
    return f"{context.cache_prefix}:{key}"


def get_cache_key_safe(key: str, default_prefix: str = "global") -> str:
    """
    Generate a tenant-aware cache key without raising an exception.
    
    Args:
        key: The base cache key
        default_prefix: The default prefix to use if no tenant context
        
    Returns:
        str: The prefixed cache key
    """
    context = get_current_tenant_safe()
    if context:
        return f"{context.cache_prefix}:{key}"
    return f"{default_prefix}:{key}"


class TenantContextManager:
    """
    Advanced tenant context manager for complex scenarios.
    
    Provides additional functionality for managing tenant contexts
    in multi-tenant applications.
    """
    
    def __init__(self):
        self._context_stack = []
    
    def push_context(self, context: TenantContext) -> None:
        """
        Push a new tenant context onto the stack.
        
        Args:
            context: The tenant context to push
        """
        current = get_current_tenant_safe()
        if current:
            self._context_stack.append(current)
        set_current_tenant(context)
    
    def pop_context(self) -> Optional[TenantContext]:
        """
        Pop the previous tenant context from the stack.
        
        Returns:
            Optional[TenantContext]: The previous context or None
        """
        if self._context_stack:
            previous = self._context_stack.pop()
            set_current_tenant(previous)
            return previous
        else:
            clear_tenant_context()
            return None
    
    def switch_tenant(self, tenant_info: TenantInfo, **context_kwargs) -> TenantContext:
        """
        Switch to a different tenant context.
        
        Args:
            tenant_info: The new tenant information
            **context_kwargs: Additional context parameters
            
        Returns:
            TenantContext: The new tenant context
        """
        new_context = TenantContext(tenant=tenant_info, **context_kwargs)
        self.push_context(new_context)
        return new_context
    
    @contextmanager
    def temporary_tenant(self, tenant_info: TenantInfo, **context_kwargs):
        """
        Context manager for temporary tenant switching.
        
        Args:
            tenant_info: The tenant information to switch to
            **context_kwargs: Additional context parameters
        """
        self.push_context(TenantContext(tenant=tenant_info, **context_kwargs))
        try:
            yield get_current_tenant()
        finally:
            self.pop_context()
    
    def clear_stack(self) -> None:
        """Clear the entire context stack."""
        self._context_stack.clear()
        clear_tenant_context()


# Global context manager instance
context_manager = TenantContextManager()