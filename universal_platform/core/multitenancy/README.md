# Universal Platform Multi-Tenancy

A comprehensive, enterprise-ready multi-tenancy solution for the Universal Platform that supports multiple tenancy models, automatic tenant isolation, and advanced security features.

## Features

### Core Capabilities
- **Thread-safe tenant context management** with async support
- **Multiple tenancy models**: Single-tenant, shared database, separate schemas, separate databases, and hybrid approaches
- **Automatic tenant resolution** from domain, subdomain, headers, JWT tokens, and URL paths
- **Tenant-aware middleware** for popular web frameworks (FastAPI, Django, Flask, ASGI)
- **Repository pattern** with automatic tenant filtering and cross-tenant access controls
- **Hierarchical configuration management** with tenant-specific overrides
- **Schema migration and versioning** with rollback capabilities

### Security & Isolation
- **Data isolation strategies** with configurable security levels
- **Cross-tenant access controls** with permission validation
- **Audit logging** per tenant with security event tracking
- **Encrypted sensitive configuration** with key management
- **Row-level security** support for shared database models

### Performance & Scalability
- **Tenant-aware caching** with automatic cache key prefixing
- **Connection pooling** per tenant database
- **Query optimization** with tenant-specific indexing
- **Bulk operations** with tenant context preservation
- **Performance monitoring** per tenant

### Operations & Management
- **Tenant onboarding** with automated schema provisioning
- **Backup and restore** capabilities per tenant
- **Migration coordination** across multiple tenants
- **Health checks** and monitoring per tenant
- **Administrative tools** for cross-tenant operations

## Quick Start

### 1. Basic Setup

```python
from universal_platform.core.multitenancy import (
    TenantIsolationManager, TenancyModel,
    TenantRouterManager, TenantMiddlewareFactory
)
from sqlalchemy import create_engine

# Create database engine
engine = create_engine("postgresql://user:pass@localhost/myapp")

# Setup tenant isolation
isolation_manager = TenantIsolationManager(
    tenancy_model=TenancyModel.MULTI_TENANT_SHARED,
    engine=engine
)

# Setup tenant routing
router_manager = TenantRouterManager()

# Add domain-based resolver
domain_resolver = router_manager.add_domain_resolver(is_default=True)
domain_resolver.add_subdomain_pattern("myapp.com")

# Add header-based resolver as fallback
router_manager.add_header_resolver(tenant_header="X-Tenant-ID")

# Create composite resolver
router_manager.create_composite_resolver(["domain", "header"])
```

### 2. Framework Integration

#### FastAPI

```python
from fastapi import FastAPI
from universal_platform.core.multitenancy import FastAPITenantMiddleware

app = FastAPI()

# Add tenant middleware
tenant_middleware = FastAPITenantMiddleware(
    router_manager=router_manager,
    require_tenant=True
)

app.middleware("http")(tenant_middleware)

@app.get("/api/data")
async def get_data(request: Request):
    # Tenant context is automatically available
    tenant_context = request.state.tenant_context
    return {"tenant_id": tenant_context.tenant_id}
```

#### Django

```python
# settings.py
MIDDLEWARE = [
    'universal_platform.core.multitenancy.DjangoTenantMiddleware',
    # ... other middleware
]

TENANT_ROUTER_MANAGER = router_manager

# views.py
from universal_platform.core.multitenancy import get_current_tenant

def my_view(request):
    tenant = get_current_tenant()
    return JsonResponse({"tenant_id": tenant.tenant_id})
```

### 3. Repository Usage

```python
from universal_platform.core.multitenancy import TenantAwareRepository, TenantModelMixin
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String

Base = declarative_base()

class User(Base, TenantModelMixin):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100))
    email = Column(String(100))

# Create repository
user_repo = TenantAwareRepository(User, isolation_manager)

# Usage with automatic tenant filtering
users = user_repo.find_all()  # Only returns users for current tenant
user = user_repo.find_by_id(1)  # Validates tenant access
new_user = user_repo.create(User(name="John", email="john@example.com"))
```

### 4. Configuration Management

```python
from universal_platform.core.multitenancy import (
    TenantConfigurationManager,
    FileConfigurationProvider,
    DatabaseConfigurationProvider,
    get_tenant_config
)

# Setup configuration manager
config_manager = TenantConfigurationManager()

# Add providers (in order of precedence)
config_manager.add_provider(FileConfigurationProvider("config/"))
config_manager.add_provider(DatabaseConfigurationProvider(session_factory))

# Usage
api_key = get_tenant_config("integrations.stripe.api_key")
feature_enabled = get_tenant_config("features.advanced_analytics", False)

# Tenant-specific settings
tenant_settings = config_manager.get_tenant_settings()
if tenant_settings.has_feature("premium_features"):
    # Enable premium functionality
    pass
```

## Architecture

### Tenancy Models

#### 1. Single Tenant
```python
isolation_manager = TenantIsolationManager(
    tenancy_model=TenancyModel.SINGLE_TENANT,
    engine=engine
)
```
- One tenant per application instance
- No data isolation needed
- Simplest deployment model

#### 2. Multi-Tenant Shared Database
```python
isolation_manager = TenantIsolationManager(
    tenancy_model=TenancyModel.MULTI_TENANT_SHARED,
    engine=engine,
    tenant_id_column="tenant_id"
)
```
- Multiple tenants share same database
- Row-level security with tenant_id filtering
- Most cost-effective for large numbers of tenants

#### 3. Multi-Tenant Separate Schemas
```python
isolation_manager = TenantIsolationManager(
    tenancy_model=TenancyModel.MULTI_TENANT_SCHEMA,
    engine=engine,
    schema_template="tenant_{tenant_id}"
)
```
- Each tenant has separate database schema
- Better isolation while sharing database resources
- Good balance of security and efficiency

#### 4. Multi-Tenant Separate Databases
```python
isolation_manager = TenantIsolationManager(
    tenancy_model=TenancyModel.MULTI_TENANT_DATABASE,
    default_connection_string="postgresql://user:pass@localhost/template"
)

# Add tenant databases
config = TenantDatabaseConfig(
    tenant_id="tenant1",
    connection_string="postgresql://user:pass@localhost/tenant1_db"
)
isolation_manager.strategy.add_tenant_database(config)
```
- Each tenant has completely separate database
- Maximum isolation and security
- Higher resource overhead

#### 5. Hybrid Approach
```python
isolation_manager = TenantIsolationManager(tenancy_model=TenancyModel.HYBRID)

# Configure different strategies for different data types
hybrid_strategy = isolation_manager.strategy
hybrid_strategy.add_strategy("shared", shared_strategy, is_default=True)
hybrid_strategy.add_strategy("isolated", separate_db_strategy)

# Map sensitive data to isolated strategy
hybrid_strategy.map_resource_to_strategy("payments", "isolated")
hybrid_strategy.map_resource_to_strategy("financial_data", "isolated")
```

### Tenant Resolution

#### Domain-Based Resolution
```python
domain_resolver = DomainTenantResolver()

# Direct domain mapping
domain_resolver.add_domain_mapping("acme.myapp.com", tenant_info)

# Pattern-based resolution
domain_resolver.add_subdomain_pattern("myapp.com", "{subdomain}")
domain_resolver.add_domain_pattern(r"(?P<tenant>\w+)\.example\.com", "{tenant}")
```

#### Header-Based Resolution
```python
header_resolver = HeaderTenantResolver(
    tenant_header="X-Tenant-ID",
    validate_tenant=True
)
```

#### JWT-Based Resolution
```python
jwt_resolver = JWTTenantResolver(
    secret_key="your-secret-key",
    tenant_claim="tenant_id",
    algorithms=["HS256"]
)
```

#### Composite Resolution
```python
composite_resolver = CompositeTenantResolver([
    domain_resolver,
    jwt_resolver,
    header_resolver
])
composite_resolver.set_fallback_resolver(default_resolver)
```

## Advanced Features

### Cross-Tenant Operations

```python
# Create cross-tenant repository for admin operations
admin_repo = CrossTenantRepository(User, isolation_manager)

# Get statistics across all tenants
stats = admin_repo.get_tenant_statistics()

# Find all users for a specific tenant
tenant_users = admin_repo.find_by_tenant("tenant1")
```

### Tenant Context Management

```python
from universal_platform.core.multitenancy import tenant_context, TenantContext

# Temporary tenant switching
with tenant_context(other_tenant_context):
    # Operations here run with different tenant context
    data = user_repo.find_all()

# Manual context management
from universal_platform.core.multitenancy import context_manager

context_manager.push_context(admin_context)
try:
    # Admin operations
    pass
finally:
    context_manager.pop_context()
```

### Migration Management

```python
from universal_platform.core.multitenancy import TenantMigrationManager

migration_manager = TenantMigrationManager(
    isolation_manager=isolation_manager,
    migration_dir="migrations/"
)

# Create new migration
migration = migration_manager.create_migration(
    name="add_user_preferences",
    description="Add user preferences table",
    sql_up="""
        CREATE TABLE user_preferences (
            id SERIAL PRIMARY KEY,
            tenant_id VARCHAR(100) NOT NULL,
            user_id INTEGER NOT NULL,
            preferences JSONB,
            created_at TIMESTAMP DEFAULT NOW()
        );
        CREATE INDEX idx_user_preferences_tenant ON user_preferences(tenant_id);
    """,
    sql_down="DROP TABLE user_preferences;"
)

# Execute migrations for all tenants
results = migration_manager.migrate_all_tenants()

# Check migration status
status = migration_manager.get_migration_status("tenant1")
```

### Schema Management

```python
from universal_platform.core.multitenancy import TenantSchemaManager

schema_manager = TenantSchemaManager(isolation_manager, metadata)

# Create schema for new tenant
schema_manager.create_tenant_schema("new_tenant")

# Backup tenant data
backup_path = schema_manager.backup_tenant_data("tenant1")

# Restore from backup
schema_manager.restore_tenant_data("tenant1", backup_path)
```

## Configuration Reference

### Environment Variables

```bash
# Database configuration
APP_DATABASE_URL=postgresql://user:pass@localhost/myapp
APP_TENANT_DATABASE_POOL_SIZE=5

# Tenant resolution
APP_TENANT_HEADER=X-Tenant-ID
APP_TENANT_JWT_SECRET=your-jwt-secret
APP_TENANT_DEFAULT_ID=default

# Feature flags
APP_TENANT_TENANT1_FEATURES_PREMIUM=true
APP_TENANT_TENANT1_MAX_USERS=100

# Security
APP_SECURITY_REQUIRE_TENANT=true
APP_SECURITY_ENCRYPT_CONFIG=true
```

### Configuration Files

#### system.yaml
```yaml
database:
  pool_size: 10
  timeout: 30

features:
  analytics: true
  reporting: false

security:
  session_timeout: 3600
  password_policy:
    min_length: 8
    require_special: true
```

#### tenant-acme.yaml
```yaml
features:
  analytics: true
  premium_features: true

branding:
  logo_url: "https://acme.com/logo.png"
  primary_color: "#1E40AF"
  
integrations:
  stripe:
    public_key: "pk_test_..."
```

## Best Practices

### Security

1. **Always validate tenant access**
   ```python
   def get_user(user_id: int):
       user = user_repo.find_by_id(user_id)
       if user:
           user.validate_tenant_access()  # Throws exception if invalid
       return user
   ```

2. **Use tenant-aware caching**
   ```python
   from universal_platform.core.multitenancy import get_cache_key
   
   cache_key = get_cache_key("user_data")  # Automatically prefixed with tenant
   cached_data = cache.get(cache_key)
   ```

3. **Implement audit logging**
   ```python
   def audit_action(action: str, resource: str, details: dict = None):
       tenant = get_current_tenant()
       audit_log.create({
           "tenant_id": tenant.tenant_id,
           "action": action,
           "resource": resource,
           "details": details,
           "timestamp": datetime.utcnow()
       })
   ```

### Performance

1. **Use bulk operations when possible**
   ```python
   users = [User(name=f"User {i}") for i in range(100)]
   user_repo.bulk_create(users)  # More efficient than individual creates
   ```

2. **Optimize database connections**
   ```python
   # Configure appropriate pool sizes per tenant
   config = TenantDatabaseConfig(
       tenant_id="high_traffic_tenant",
       connection_string="...",
       pool_size=20,
       max_overflow=30
   )
   ```

3. **Use query builders for complex operations**
   ```python
   builder = TenantAwareQueryBuilder(session, User, isolation_manager)
   users = (builder
           .filter(User.active == True)
           .filter(User.created_at > last_week)
           .order_by(User.name)
           .limit(50)
           .all())
   ```

### Testing

```python
import pytest
from universal_platform.core.multitenancy import tenant_context

@pytest.fixture
def test_tenant():
    return TenantContext(
        tenant=TenantInfo(tenant_id="test", tenant_name="Test Tenant")
    )

def test_user_creation(test_tenant):
    with tenant_context(test_tenant):
        user = user_repo.create(User(name="Test User"))
        assert user.tenant_id == "test"
```

## Migration Guide

### From Single-Tenant to Multi-Tenant

1. **Add tenant columns to existing tables**
2. **Update models to inherit from TenantModelMixin**
3. **Replace repositories with TenantAwareRepository**
4. **Add tenant middleware to application**
5. **Update queries to use tenant filtering**

### From Shared Database to Separate Schemas

1. **Create migration to extract tenant data**
2. **Update isolation manager configuration**
3. **Run schema creation for each tenant**
4. **Migrate data to new schemas**
5. **Update application configuration**

## Troubleshooting

### Common Issues

1. **NoTenantContextError**
   - Ensure middleware is properly configured
   - Check tenant resolution logic
   - Verify request contains tenant information

2. **CrossTenantAccessError**
   - Review permission settings
   - Check if cross-tenant access is intentional
   - Use CrossTenantRepository for admin operations

3. **Migration failures**
   - Check migration dependencies
   - Verify database permissions
   - Review migration SQL syntax
   - Check for data conflicts

### Debug Mode

```python
import logging
logging.getLogger('universal_platform.core.multitenancy').setLevel(logging.DEBUG)
```

## Contributing

See the main Universal Platform documentation for contribution guidelines.

## License

This multi-tenancy module is part of the Universal Platform and follows the same licensing terms.