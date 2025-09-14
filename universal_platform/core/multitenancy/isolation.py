"""
Data isolation strategies for multi-tenant applications.

Provides different tenancy models and isolation strategies to support
various multi-tenant architectures including shared database, separate
database, and hybrid approaches.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Type, Union

from sqlalchemy import MetaData, create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from .tenant_context import get_current_tenant, get_current_tenant_safe

logger = logging.getLogger(__name__)


class TenancyModel(Enum):
    """Different tenancy models supported by the platform."""
    
    SINGLE_TENANT = "single_tenant"
    """Single tenant per application instance"""
    
    MULTI_TENANT_SHARED = "multi_tenant_shared"  
    """Multiple tenants sharing the same database with row-level security"""
    
    MULTI_TENANT_SCHEMA = "multi_tenant_schema"
    """Multiple tenants with separate schemas in the same database"""
    
    MULTI_TENANT_DATABASE = "multi_tenant_database"
    """Multiple tenants with separate databases"""
    
    HYBRID = "hybrid"
    """Hybrid approach with different strategies for different data types"""


class IsolationLevel(Enum):
    """Levels of tenant data isolation."""
    
    NONE = "none"
    """No isolation (single tenant)"""
    
    ROW_LEVEL = "row_level"
    """Row-level isolation with tenant_id filtering"""
    
    SCHEMA_LEVEL = "schema_level"
    """Schema-level isolation"""
    
    DATABASE_LEVEL = "database_level"
    """Database-level isolation"""


@dataclass
class TenantDatabaseConfig:
    """Configuration for tenant database access."""
    
    tenant_id: str
    connection_string: str
    schema_name: Optional[str] = None
    pool_size: int = 5
    max_overflow: int = 10
    pool_timeout: int = 30
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class IsolationStrategy(ABC):
    """Abstract base class for tenant isolation strategies."""
    
    @abstractmethod
    def get_session(self, tenant_id: Optional[str] = None) -> Session:
        """Get a database session for the specified tenant."""
        pass
    
    @abstractmethod
    def apply_tenant_filter(self, query: Any, tenant_id: Optional[str] = None) -> Any:
        """Apply tenant filtering to a query."""
        pass
    
    @abstractmethod
    def get_table_name(self, base_name: str, tenant_id: Optional[str] = None) -> str:
        """Get the actual table name for a tenant."""
        pass
    
    @abstractmethod
    def validate_access(self, tenant_id: str, resource: str) -> bool:
        """Validate if a tenant can access a specific resource."""
        pass


class SingleTenantStrategy(IsolationStrategy):
    """Strategy for single-tenant applications."""
    
    def __init__(self, engine: Engine):
        self.engine = engine
        self.session_factory = sessionmaker(bind=engine)
    
    def get_session(self, tenant_id: Optional[str] = None) -> Session:
        """Get a database session (tenant_id ignored for single tenant)."""
        return self.session_factory()
    
    def apply_tenant_filter(self, query: Any, tenant_id: Optional[str] = None) -> Any:
        """No filtering needed for single tenant."""
        return query
    
    def get_table_name(self, base_name: str, tenant_id: Optional[str] = None) -> str:
        """Return the base table name."""
        return base_name
    
    def validate_access(self, tenant_id: str, resource: str) -> bool:
        """Always allow access in single tenant mode."""
        return True


class SharedDatabaseStrategy(IsolationStrategy):
    """Strategy for multi-tenant shared database with row-level security."""
    
    def __init__(self, engine: Engine, tenant_id_column: str = "tenant_id"):
        self.engine = engine
        self.session_factory = sessionmaker(bind=engine)
        self.tenant_id_column = tenant_id_column
        self._allowed_tenants: Set[str] = set()
    
    def add_allowed_tenant(self, tenant_id: str) -> None:
        """Add a tenant to the allowed tenants list."""
        self._allowed_tenants.add(tenant_id)
    
    def remove_allowed_tenant(self, tenant_id: str) -> None:
        """Remove a tenant from the allowed tenants list."""
        self._allowed_tenants.discard(tenant_id)
    
    def get_session(self, tenant_id: Optional[str] = None) -> Session:
        """Get a database session with tenant context."""
        session = self.session_factory()
        
        # Set tenant context in session for RLS policies
        if tenant_id is None:
            context = get_current_tenant_safe()
            tenant_id = context.tenant_id if context else None
        
        if tenant_id and self.validate_access(tenant_id, "database"):
            # Set tenant context for RLS policies
            session.execute(text(f"SET app.current_tenant_id = '{tenant_id}'"))
        
        return session
    
    def apply_tenant_filter(self, query: Any, tenant_id: Optional[str] = None) -> Any:
        """Apply tenant filtering to query."""
        if tenant_id is None:
            context = get_current_tenant_safe()
            tenant_id = context.tenant_id if context else None
        
        if tenant_id and hasattr(query, 'filter'):
            # Apply tenant filter to SQLAlchemy queries
            return query.filter(getattr(query.column_descriptions[0]['type'], self.tenant_id_column) == tenant_id)
        
        return query
    
    def get_table_name(self, base_name: str, tenant_id: Optional[str] = None) -> str:
        """Return the base table name (shared tables)."""
        return base_name
    
    def validate_access(self, tenant_id: str, resource: str) -> bool:
        """Validate tenant access."""
        if not self._allowed_tenants:
            return True  # No restrictions if no tenants explicitly allowed
        return tenant_id in self._allowed_tenants


class SeparateSchemaStrategy(IsolationStrategy):
    """Strategy for multi-tenant with separate schemas per tenant."""
    
    def __init__(self, engine: Engine, schema_template: str = "tenant_{tenant_id}"):
        self.engine = engine
        self.base_session_factory = sessionmaker(bind=engine)
        self.schema_template = schema_template
        self._tenant_sessions: Dict[str, sessionmaker] = {}
        self._schema_cache: Dict[str, str] = {}
    
    def get_schema_name(self, tenant_id: str) -> str:
        """Get the schema name for a tenant."""
        if tenant_id not in self._schema_cache:
            self._schema_cache[tenant_id] = self.schema_template.format(tenant_id=tenant_id)
        return self._schema_cache[tenant_id]
    
    def get_session(self, tenant_id: Optional[str] = None) -> Session:
        """Get a database session for the specified tenant schema."""
        if tenant_id is None:
            context = get_current_tenant()
            tenant_id = context.tenant_id
        
        if tenant_id not in self._tenant_sessions:
            # Create schema-specific session factory
            session_factory = sessionmaker(bind=self.engine)
            self._tenant_sessions[tenant_id] = session_factory
        
        session = self._tenant_sessions[tenant_id]()
        
        # Set the search path to the tenant schema
        schema_name = self.get_schema_name(tenant_id)
        session.execute(text(f"SET search_path TO {schema_name}, public"))
        
        return session
    
    def apply_tenant_filter(self, query: Any, tenant_id: Optional[str] = None) -> Any:
        """No additional filtering needed as schema isolation handles it."""
        return query
    
    def get_table_name(self, base_name: str, tenant_id: Optional[str] = None) -> str:
        """Get the fully qualified table name with schema."""
        if tenant_id is None:
            context = get_current_tenant_safe()
            tenant_id = context.tenant_id if context else None
        
        if tenant_id:
            schema_name = self.get_schema_name(tenant_id)
            return f"{schema_name}.{base_name}"
        
        return base_name
    
    def validate_access(self, tenant_id: str, resource: str) -> bool:
        """Validate tenant access to schema."""
        # Check if schema exists
        inspector = inspect(self.engine)
        schema_name = self.get_schema_name(tenant_id)
        return schema_name in inspector.get_schema_names()
    
    def create_tenant_schema(self, tenant_id: str) -> None:
        """Create a new tenant schema."""
        schema_name = self.get_schema_name(tenant_id)
        
        with self.engine.connect() as conn:
            conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema_name}"))
            conn.commit()
        
        logger.info(f"Created schema {schema_name} for tenant {tenant_id}")
    
    def drop_tenant_schema(self, tenant_id: str, cascade: bool = False) -> None:
        """Drop a tenant schema."""
        schema_name = self.get_schema_name(tenant_id)
        cascade_clause = "CASCADE" if cascade else "RESTRICT"
        
        with self.engine.connect() as conn:
            conn.execute(text(f"DROP SCHEMA IF EXISTS {schema_name} {cascade_clause}"))
            conn.commit()
        
        # Clean up cache
        self._schema_cache.pop(tenant_id, None)
        self._tenant_sessions.pop(tenant_id, None)
        
        logger.info(f"Dropped schema {schema_name} for tenant {tenant_id}")


class SeparateDatabaseStrategy(IsolationStrategy):
    """Strategy for multi-tenant with separate databases per tenant."""
    
    def __init__(self, default_connection_string: str):
        self.default_connection_string = default_connection_string
        self._tenant_engines: Dict[str, Engine] = {}
        self._tenant_sessions: Dict[str, sessionmaker] = {}
        self._tenant_configs: Dict[str, TenantDatabaseConfig] = {}
    
    def add_tenant_database(self, config: TenantDatabaseConfig) -> None:
        """Add a tenant database configuration."""
        self._tenant_configs[config.tenant_id] = config
        
        # Create engine for the tenant
        engine = create_engine(
            config.connection_string,
            pool_size=config.pool_size,
            max_overflow=config.max_overflow,
            pool_timeout=config.pool_timeout,
            poolclass=StaticPool if config.connection_string.startswith('sqlite') else None
        )
        
        self._tenant_engines[config.tenant_id] = engine
        self._tenant_sessions[config.tenant_id] = sessionmaker(bind=engine)
        
        logger.info(f"Added database configuration for tenant {config.tenant_id}")
    
    def get_session(self, tenant_id: Optional[str] = None) -> Session:
        """Get a database session for the specified tenant database."""
        if tenant_id is None:
            context = get_current_tenant()
            tenant_id = context.tenant_id
        
        if tenant_id not in self._tenant_sessions:
            raise ValueError(f"No database configuration found for tenant {tenant_id}")
        
        return self._tenant_sessions[tenant_id]()
    
    def apply_tenant_filter(self, query: Any, tenant_id: Optional[str] = None) -> Any:
        """No additional filtering needed as database isolation handles it."""
        return query
    
    def get_table_name(self, base_name: str, tenant_id: Optional[str] = None) -> str:
        """Return the base table name (separate databases)."""
        return base_name
    
    def validate_access(self, tenant_id: str, resource: str) -> bool:
        """Validate tenant access to database."""
        return tenant_id in self._tenant_configs
    
    def get_tenant_engine(self, tenant_id: str) -> Engine:
        """Get the database engine for a tenant."""
        if tenant_id not in self._tenant_engines:
            raise ValueError(f"No database engine found for tenant {tenant_id}")
        return self._tenant_engines[tenant_id]
    
    def remove_tenant_database(self, tenant_id: str) -> None:
        """Remove tenant database configuration."""
        if tenant_id in self._tenant_engines:
            self._tenant_engines[tenant_id].dispose()
            del self._tenant_engines[tenant_id]
        
        self._tenant_sessions.pop(tenant_id, None)
        self._tenant_configs.pop(tenant_id, None)
        
        logger.info(f"Removed database configuration for tenant {tenant_id}")


class HybridStrategy(IsolationStrategy):
    """Hybrid strategy that combines multiple isolation approaches."""
    
    def __init__(self):
        self._strategies: Dict[str, IsolationStrategy] = {}
        self._resource_mapping: Dict[str, str] = {}
        self._default_strategy_name: Optional[str] = None
    
    def add_strategy(self, name: str, strategy: IsolationStrategy, is_default: bool = False) -> None:
        """Add an isolation strategy."""
        self._strategies[name] = strategy
        if is_default:
            self._default_strategy_name = name
    
    def map_resource_to_strategy(self, resource_pattern: str, strategy_name: str) -> None:
        """Map a resource pattern to a specific strategy."""
        self._resource_mapping[resource_pattern] = strategy_name
    
    def get_strategy_for_resource(self, resource: str) -> IsolationStrategy:
        """Get the appropriate strategy for a resource."""
        # Try exact match first
        if resource in self._resource_mapping:
            strategy_name = self._resource_mapping[resource]
            return self._strategies[strategy_name]
        
        # Try pattern matching
        for pattern, strategy_name in self._resource_mapping.items():
            if resource.startswith(pattern) or pattern in resource:
                return self._strategies[strategy_name]
        
        # Fall back to default strategy
        if self._default_strategy_name:
            return self._strategies[self._default_strategy_name]
        
        raise ValueError(f"No strategy found for resource {resource}")
    
    def get_session(self, tenant_id: Optional[str] = None) -> Session:
        """Get a session from the default strategy."""
        if not self._default_strategy_name:
            raise ValueError("No default strategy configured")
        return self._strategies[self._default_strategy_name].get_session(tenant_id)
    
    def apply_tenant_filter(self, query: Any, tenant_id: Optional[str] = None) -> Any:
        """Apply tenant filter using the default strategy."""
        if not self._default_strategy_name:
            raise ValueError("No default strategy configured")
        return self._strategies[self._default_strategy_name].apply_tenant_filter(query, tenant_id)
    
    def get_table_name(self, base_name: str, tenant_id: Optional[str] = None) -> str:
        """Get table name using the appropriate strategy."""
        strategy = self.get_strategy_for_resource(base_name)
        return strategy.get_table_name(base_name, tenant_id)
    
    def validate_access(self, tenant_id: str, resource: str) -> bool:
        """Validate access using the appropriate strategy."""
        strategy = self.get_strategy_for_resource(resource)
        return strategy.validate_access(tenant_id, resource)


class TenantIsolationManager:
    """
    Main manager for tenant isolation strategies.
    
    Provides a unified interface for managing different isolation strategies
    and switching between them based on configuration.
    """
    
    def __init__(self, tenancy_model: TenancyModel, **kwargs):
        self.tenancy_model = tenancy_model
        self.strategy = self._create_strategy(**kwargs)
    
    def _create_strategy(self, **kwargs) -> IsolationStrategy:
        """Create the appropriate isolation strategy based on tenancy model."""
        if self.tenancy_model == TenancyModel.SINGLE_TENANT:
            engine = kwargs.get('engine')
            if not engine:
                raise ValueError("Engine required for single tenant strategy")
            return SingleTenantStrategy(engine)
        
        elif self.tenancy_model == TenancyModel.MULTI_TENANT_SHARED:
            engine = kwargs.get('engine')
            tenant_id_column = kwargs.get('tenant_id_column', 'tenant_id')
            if not engine:
                raise ValueError("Engine required for shared database strategy")
            return SharedDatabaseStrategy(engine, tenant_id_column)
        
        elif self.tenancy_model == TenancyModel.MULTI_TENANT_SCHEMA:
            engine = kwargs.get('engine')
            schema_template = kwargs.get('schema_template', 'tenant_{tenant_id}')
            if not engine:
                raise ValueError("Engine required for separate schema strategy")
            return SeparateSchemaStrategy(engine, schema_template)
        
        elif self.tenancy_model == TenancyModel.MULTI_TENANT_DATABASE:
            default_connection_string = kwargs.get('default_connection_string')
            if not default_connection_string:
                raise ValueError("Default connection string required for separate database strategy")
            return SeparateDatabaseStrategy(default_connection_string)
        
        elif self.tenancy_model == TenancyModel.HYBRID:
            return HybridStrategy()
        
        else:
            raise ValueError(f"Unsupported tenancy model: {self.tenancy_model}")
    
    def get_session(self, tenant_id: Optional[str] = None) -> Session:
        """Get a database session for the current or specified tenant."""
        return self.strategy.get_session(tenant_id)
    
    def apply_tenant_filter(self, query: Any, tenant_id: Optional[str] = None) -> Any:
        """Apply tenant filtering to a query."""
        return self.strategy.apply_tenant_filter(query, tenant_id)
    
    def get_table_name(self, base_name: str, tenant_id: Optional[str] = None) -> str:
        """Get the actual table name for a tenant."""
        return self.strategy.get_table_name(base_name, tenant_id)
    
    def validate_access(self, tenant_id: str, resource: str) -> bool:
        """Validate if a tenant can access a specific resource."""
        return self.strategy.validate_access(tenant_id, resource)
    
    def get_isolation_level(self) -> IsolationLevel:
        """Get the isolation level for the current strategy."""
        if self.tenancy_model == TenancyModel.SINGLE_TENANT:
            return IsolationLevel.NONE
        elif self.tenancy_model == TenancyModel.MULTI_TENANT_SHARED:
            return IsolationLevel.ROW_LEVEL
        elif self.tenancy_model == TenancyModel.MULTI_TENANT_SCHEMA:
            return IsolationLevel.SCHEMA_LEVEL
        elif self.tenancy_model == TenancyModel.MULTI_TENANT_DATABASE:
            return IsolationLevel.DATABASE_LEVEL
        else:
            return IsolationLevel.ROW_LEVEL  # Default for hybrid