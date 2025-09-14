"""
Multi-tenancy support for the Universal Platform.

This package provides comprehensive multi-tenant capabilities including:
- Thread-safe tenant context management
- Multiple tenancy models (single-tenant, multi-tenant shared, multi-tenant isolated)
- Tenant resolution from various sources (domain, subdomain, header, JWT)
- Automatic data filtering by tenant ID
- Tenant-specific configuration and customization
- Cross-tenant access controls and security
- Performance optimization with tenant-aware caching
"""

from .tenant_context import (
    TenantContext,
    get_current_tenant,
    set_current_tenant,
    clear_tenant_context,
    tenant_context,
)
from .isolation import (
    TenancyModel,
    IsolationStrategy,
    TenantIsolationManager,
)
from .routing import (
    TenantResolver,
    DomainTenantResolver,
    HeaderTenantResolver,
    JWTTenantResolver,
    CompositeTenantResolver,
)
from .middleware import (
    TenantMiddleware,
    FastAPITenantMiddleware,
    DjangoTenantMiddleware,
)
from .repository import (
    TenantAwareRepository,
    TenantFilteredQueryMixin,
    tenant_filter,
)
from .configuration import (
    TenantConfigurationManager,
    TenantSettings,
    get_tenant_config,
)
from .migration import (
    TenantMigrationManager,
    TenantSchemaManager,
    migrate_tenant,
)

__all__ = [
    # Context management
    "TenantContext",
    "get_current_tenant",
    "set_current_tenant", 
    "clear_tenant_context",
    "tenant_context",
    # Isolation
    "TenancyModel",
    "IsolationStrategy",
    "TenantIsolationManager",
    # Routing
    "TenantResolver",
    "DomainTenantResolver",
    "HeaderTenantResolver",
    "JWTTenantResolver",
    "CompositeTenantResolver",
    # Middleware
    "TenantMiddleware",
    "FastAPITenantMiddleware",
    "DjangoTenantMiddleware",
    # Repository
    "TenantAwareRepository",
    "TenantFilteredQueryMixin",
    "tenant_filter",
    # Configuration
    "TenantConfigurationManager",
    "TenantSettings",
    "get_tenant_config",
    # Migration
    "TenantMigrationManager",
    "TenantSchemaManager",
    "migrate_tenant",
]