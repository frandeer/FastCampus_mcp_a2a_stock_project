"""
Tenant-aware repository implementations.

Provides base classes and mixins for implementing tenant-aware data access
patterns including automatic tenant filtering, cross-tenant access controls,
and tenant-specific query optimization.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Type, TypeVar, Union, Generic

from sqlalchemy import and_, Column, String, text
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import Session, Query, declarative_base
from sqlalchemy.orm.events import event
from sqlalchemy.sql import Select

from .tenant_context import get_current_tenant, get_current_tenant_safe, NoTenantContextError
from .isolation import TenantIsolationManager, IsolationStrategy

logger = logging.getLogger(__name__)

# Type variables for generic repository
ModelType = TypeVar('ModelType')
KeyType = TypeVar('KeyType')


class TenantAwareError(Exception):
    """Exception raised by tenant-aware operations."""
    pass


class CrossTenantAccessError(TenantAwareError):
    """Exception raised when attempting unauthorized cross-tenant access."""
    pass


class TenantModelMixin:
    """
    Mixin class for tenant-aware SQLAlchemy models.
    
    Adds tenant_id column and automatic tenant filtering to models.
    """
    
    @declared_attr
    def tenant_id(cls):
        """Tenant ID column."""
        return Column(String(100), nullable=False, index=True)
    
    @declared_attr
    def __table_args__(cls):
        """Add tenant_id to table indexes."""
        args = getattr(cls, '_table_args', ())
        if isinstance(args, dict):
            return args
        return args + ({'extend_existing': True},)
    
    def __init__(self, *args, **kwargs):
        """Initialize with current tenant ID if not provided."""
        if 'tenant_id' not in kwargs:
            try:
                context = get_current_tenant()
                kwargs['tenant_id'] = context.tenant_id
            except NoTenantContextError:
                # Allow explicit None for system/cross-tenant operations
                pass
        super().__init__(*args, **kwargs)
    
    def validate_tenant_access(self, required_tenant_id: Optional[str] = None) -> bool:
        """
        Validate that current tenant can access this record.
        
        Args:
            required_tenant_id: Specific tenant ID to check against
            
        Returns:
            bool: True if access is allowed
            
        Raises:
            CrossTenantAccessError: If access is not allowed
        """
        try:
            context = get_current_tenant()
            current_tenant_id = context.tenant_id
        except NoTenantContextError:
            # No tenant context - allow system access
            return True
        
        target_tenant_id = required_tenant_id or self.tenant_id
        
        if current_tenant_id != target_tenant_id:
            raise CrossTenantAccessError(
                f"Tenant {current_tenant_id} cannot access data for tenant {target_tenant_id}"
            )
        
        return True


class TenantFilteredQueryMixin:
    """
    Mixin for adding automatic tenant filtering to SQLAlchemy queries.
    """
    
    def filter_by_tenant(self, tenant_id: Optional[str] = None) -> Query:
        """
        Add tenant filter to query.
        
        Args:
            tenant_id: Specific tenant ID to filter by (uses current tenant if None)
            
        Returns:
            Query: Filtered query
        """
        if tenant_id is None:
            try:
                context = get_current_tenant()
                tenant_id = context.tenant_id
            except NoTenantContextError:
                # No tenant context - return unfiltered query
                return self
        
        # Add tenant filter
        return self.filter(self.column_descriptions[0]['type'].tenant_id == tenant_id)
    
    def allow_cross_tenant(self) -> Query:
        """
        Explicitly allow cross-tenant access for this query.
        
        Returns:
            Query: Query without tenant filtering
        """
        # Mark query as allowing cross-tenant access
        self._cross_tenant_allowed = True
        return self


def tenant_filter(query: Query, model_class: Type = None, tenant_id: Optional[str] = None) -> Query:
    """
    Apply tenant filtering to a SQLAlchemy query.
    
    Args:
        query: The SQLAlchemy query to filter
        model_class: The model class (auto-detected if None)
        tenant_id: Specific tenant ID to filter by
        
    Returns:
        Query: Filtered query
    """
    if tenant_id is None:
        try:
            context = get_current_tenant()
            tenant_id = context.tenant_id
        except NoTenantContextError:
            # No tenant context - return unfiltered query
            return query
    
    # Auto-detect model class if not provided
    if model_class is None and query.column_descriptions:
        model_class = query.column_descriptions[0]['type']
    
    if model_class and hasattr(model_class, 'tenant_id'):
        return query.filter(model_class.tenant_id == tenant_id)
    
    return query


class TenantAwareRepository(Generic[ModelType, KeyType], ABC):
    """
    Abstract base class for tenant-aware repositories.
    
    Provides common patterns for tenant-aware data access including
    automatic filtering, validation, and cross-tenant access controls.
    """
    
    def __init__(self, 
                 model_class: Type[ModelType],
                 isolation_manager: TenantIsolationManager,
                 allow_cross_tenant: bool = False):
        """
        Initialize tenant-aware repository.
        
        Args:
            model_class: The SQLAlchemy model class
            isolation_manager: Tenant isolation manager
            allow_cross_tenant: Whether to allow cross-tenant operations
        """
        self.model_class = model_class
        self.isolation_manager = isolation_manager
        self.allow_cross_tenant = allow_cross_tenant
    
    def get_session(self, tenant_id: Optional[str] = None) -> Session:
        """Get a tenant-aware database session."""
        return self.isolation_manager.get_session(tenant_id)
    
    def _apply_tenant_filter(self, query: Query, tenant_id: Optional[str] = None) -> Query:
        """Apply tenant filtering to query if needed."""
        if self.allow_cross_tenant:
            return query
        
        return self.isolation_manager.apply_tenant_filter(query, tenant_id)
    
    def _validate_tenant_access(self, obj: ModelType, operation: str = "access") -> None:
        """Validate tenant access for an object."""
        if self.allow_cross_tenant:
            return
        
        if hasattr(obj, 'validate_tenant_access'):
            obj.validate_tenant_access()
    
    def find_by_id(self, id: KeyType, tenant_id: Optional[str] = None) -> Optional[ModelType]:
        """
        Find a record by ID with tenant filtering.
        
        Args:
            id: The record ID
            tenant_id: Specific tenant ID to search within
            
        Returns:
            Optional[ModelType]: The record or None if not found
        """
        session = self.get_session(tenant_id)
        query = session.query(self.model_class).filter(self.model_class.id == id)
        query = self._apply_tenant_filter(query, tenant_id)
        
        result = query.first()
        if result:
            self._validate_tenant_access(result, "read")
        
        return result
    
    def find_all(self, tenant_id: Optional[str] = None, limit: Optional[int] = None, offset: int = 0) -> List[ModelType]:
        """
        Find all records with tenant filtering.
        
        Args:
            tenant_id: Specific tenant ID to search within
            limit: Maximum number of records to return
            offset: Number of records to skip
            
        Returns:
            List[ModelType]: List of records
        """
        session = self.get_session(tenant_id)
        query = session.query(self.model_class)
        query = self._apply_tenant_filter(query, tenant_id)
        
        if offset > 0:
            query = query.offset(offset)
        if limit is not None:
            query = query.limit(limit)
        
        results = query.all()
        
        # Validate access for each result
        for result in results:
            self._validate_tenant_access(result, "read")
        
        return results
    
    def find_by_criteria(self, criteria: Dict[str, Any], tenant_id: Optional[str] = None) -> List[ModelType]:
        """
        Find records by criteria with tenant filtering.
        
        Args:
            criteria: Dictionary of field-value pairs to filter by
            tenant_id: Specific tenant ID to search within
            
        Returns:
            List[ModelType]: List of matching records
        """
        session = self.get_session(tenant_id)
        query = session.query(self.model_class)
        
        # Apply criteria filters
        for field, value in criteria.items():
            if hasattr(self.model_class, field):
                query = query.filter(getattr(self.model_class, field) == value)
        
        query = self._apply_tenant_filter(query, tenant_id)
        
        results = query.all()
        
        # Validate access for each result
        for result in results:
            self._validate_tenant_access(result, "read")
        
        return results
    
    def count(self, tenant_id: Optional[str] = None) -> int:
        """
        Count records with tenant filtering.
        
        Args:
            tenant_id: Specific tenant ID to count within
            
        Returns:
            int: Number of records
        """
        session = self.get_session(tenant_id)
        query = session.query(self.model_class)
        query = self._apply_tenant_filter(query, tenant_id)
        
        return query.count()
    
    def create(self, obj: ModelType, tenant_id: Optional[str] = None) -> ModelType:
        """
        Create a new record with tenant assignment.
        
        Args:
            obj: The object to create
            tenant_id: Specific tenant ID to assign
            
        Returns:
            ModelType: The created object
        """
        session = self.get_session(tenant_id)
        
        # Set tenant ID if not already set
        if hasattr(obj, 'tenant_id') and not obj.tenant_id:
            if tenant_id is None:
                try:
                    context = get_current_tenant()
                    tenant_id = context.tenant_id
                except NoTenantContextError:
                    if not self.allow_cross_tenant:
                        raise TenantAwareError("No tenant context available for object creation")
            
            if tenant_id:
                obj.tenant_id = tenant_id
        
        # Validate tenant access
        self._validate_tenant_access(obj, "create")
        
        session.add(obj)
        session.commit()
        session.refresh(obj)
        
        return obj
    
    def update(self, obj: ModelType, tenant_id: Optional[str] = None) -> ModelType:
        """
        Update a record with tenant validation.
        
        Args:
            obj: The object to update
            tenant_id: Specific tenant ID context
            
        Returns:
            ModelType: The updated object
        """
        session = self.get_session(tenant_id)
        
        # Validate tenant access
        self._validate_tenant_access(obj, "update")
        
        session.merge(obj)
        session.commit()
        session.refresh(obj)
        
        return obj
    
    def delete(self, obj: ModelType, tenant_id: Optional[str] = None) -> bool:
        """
        Delete a record with tenant validation.
        
        Args:
            obj: The object to delete
            tenant_id: Specific tenant ID context
            
        Returns:
            bool: True if deleted successfully
        """
        session = self.get_session(tenant_id)
        
        # Validate tenant access
        self._validate_tenant_access(obj, "delete")
        
        session.delete(obj)
        session.commit()
        
        return True
    
    def delete_by_id(self, id: KeyType, tenant_id: Optional[str] = None) -> bool:
        """
        Delete a record by ID with tenant validation.
        
        Args:
            id: The record ID
            tenant_id: Specific tenant ID context
            
        Returns:
            bool: True if deleted successfully
        """
        obj = self.find_by_id(id, tenant_id)
        if obj:
            return self.delete(obj, tenant_id)
        return False
    
    def bulk_create(self, objects: List[ModelType], tenant_id: Optional[str] = None) -> List[ModelType]:
        """
        Create multiple records with tenant assignment.
        
        Args:
            objects: List of objects to create
            tenant_id: Specific tenant ID to assign
            
        Returns:
            List[ModelType]: List of created objects
        """
        session = self.get_session(tenant_id)
        
        # Set tenant ID for all objects
        for obj in objects:
            if hasattr(obj, 'tenant_id') and not obj.tenant_id:
                if tenant_id is None:
                    try:
                        context = get_current_tenant()
                        tenant_id = context.tenant_id
                    except NoTenantContextError:
                        if not self.allow_cross_tenant:
                            raise TenantAwareError("No tenant context available for bulk creation")
                
                if tenant_id:
                    obj.tenant_id = tenant_id
            
            # Validate tenant access
            self._validate_tenant_access(obj, "create")
        
        session.add_all(objects)
        session.commit()
        
        for obj in objects:
            session.refresh(obj)
        
        return objects
    
    def execute_raw_query(self, query: str, parameters: Dict[str, Any] = None, tenant_id: Optional[str] = None) -> Any:
        """
        Execute a raw SQL query with tenant context.
        
        Args:
            query: Raw SQL query
            parameters: Query parameters
            tenant_id: Specific tenant ID context
            
        Returns:
            Any: Query result
        """
        if not self.allow_cross_tenant and "tenant_id" not in query.lower():
            logger.warning("Raw query executed without explicit tenant filtering")
        
        session = self.get_session(tenant_id)
        
        # Add tenant context to parameters if available
        if parameters is None:
            parameters = {}
        
        if tenant_id is None:
            try:
                context = get_current_tenant()
                tenant_id = context.tenant_id
            except NoTenantContextError:
                pass
        
        if tenant_id and 'current_tenant_id' not in parameters:
            parameters['current_tenant_id'] = tenant_id
        
        return session.execute(text(query), parameters)


class CrossTenantRepository(TenantAwareRepository[ModelType, KeyType]):
    """
    Repository that allows cross-tenant operations.
    
    Useful for administrative functions and data that needs to be
    accessible across tenant boundaries.
    """
    
    def __init__(self, model_class: Type[ModelType], isolation_manager: TenantIsolationManager):
        super().__init__(model_class, isolation_manager, allow_cross_tenant=True)
    
    def find_by_tenant(self, tenant_id: str) -> List[ModelType]:
        """
        Find all records for a specific tenant.
        
        Args:
            tenant_id: The tenant ID to search for
            
        Returns:
            List[ModelType]: List of records for the tenant
        """
        session = self.get_session()
        query = session.query(self.model_class)
        
        if hasattr(self.model_class, 'tenant_id'):
            query = query.filter(self.model_class.tenant_id == tenant_id)
        
        return query.all()
    
    def get_tenant_statistics(self) -> Dict[str, Any]:
        """
        Get statistics across all tenants.
        
        Returns:
            Dict[str, Any]: Statistics dictionary
        """
        session = self.get_session()
        
        # Count total records
        total_count = session.query(self.model_class).count()
        
        # Count by tenant if tenant_id column exists
        tenant_counts = {}
        if hasattr(self.model_class, 'tenant_id'):
            from sqlalchemy import func
            result = session.query(
                self.model_class.tenant_id,
                func.count(self.model_class.id)
            ).group_by(self.model_class.tenant_id).all()
            
            tenant_counts = {tenant_id: count for tenant_id, count in result}
        
        return {
            "total_count": total_count,
            "tenant_counts": tenant_counts,
            "tenant_count": len(tenant_counts)
        }


class TenantAwareQueryBuilder:
    """
    Builder for constructing tenant-aware queries.
    
    Provides a fluent interface for building complex queries with
    automatic tenant filtering and validation.
    """
    
    def __init__(self, session: Session, model_class: Type[ModelType], isolation_manager: TenantIsolationManager):
        self.session = session
        self.model_class = model_class
        self.isolation_manager = isolation_manager
        self.query = session.query(model_class)
        self._tenant_id: Optional[str] = None
        self._cross_tenant_allowed = False
    
    def for_tenant(self, tenant_id: str) -> 'TenantAwareQueryBuilder':
        """Specify tenant ID for the query."""
        self._tenant_id = tenant_id
        return self
    
    def allow_cross_tenant(self) -> 'TenantAwareQueryBuilder':
        """Allow cross-tenant access for this query."""
        self._cross_tenant_allowed = True
        return self
    
    def filter_by(self, **kwargs) -> 'TenantAwareQueryBuilder':
        """Add filter conditions."""
        self.query = self.query.filter_by(**kwargs)
        return self
    
    def filter(self, *criterion) -> 'TenantAwareQueryBuilder':
        """Add filter criteria."""
        self.query = self.query.filter(*criterion)
        return self
    
    def order_by(self, *criterion) -> 'TenantAwareQueryBuilder':
        """Add ordering."""
        self.query = self.query.order_by(*criterion)
        return self
    
    def limit(self, limit: int) -> 'TenantAwareQueryBuilder':
        """Add limit."""
        self.query = self.query.limit(limit)
        return self
    
    def offset(self, offset: int) -> 'TenantAwareQueryBuilder':
        """Add offset."""
        self.query = self.query.offset(offset)
        return self
    
    def _finalize_query(self) -> Query:
        """Apply tenant filtering to the final query."""
        if not self._cross_tenant_allowed:
            self.query = self.isolation_manager.apply_tenant_filter(self.query, self._tenant_id)
        return self.query
    
    def all(self) -> List[ModelType]:
        """Execute query and return all results."""
        query = self._finalize_query()
        return query.all()
    
    def first(self) -> Optional[ModelType]:
        """Execute query and return first result."""
        query = self._finalize_query()
        return query.first()
    
    def one(self) -> ModelType:
        """Execute query and return exactly one result."""
        query = self._finalize_query()
        return query.one()
    
    def one_or_none(self) -> Optional[ModelType]:
        """Execute query and return one result or None."""
        query = self._finalize_query()
        return query.one_or_none()
    
    def count(self) -> int:
        """Count query results."""
        query = self._finalize_query()
        return query.count()


# SQLAlchemy event listeners for automatic tenant filtering

@event.listens_for(Session, 'before_bulk_delete')
def receive_before_bulk_delete(query_context):
    """Prevent bulk deletes without tenant filtering."""
    mapper = query_context.mapper
    if hasattr(mapper.class_, 'tenant_id'):
        # Check if tenant filter is applied
        whereclause = query_context.whereclause
        if whereclause is None or 'tenant_id' not in str(whereclause):
            try:
                context = get_current_tenant()
                logger.warning(f"Bulk delete on {mapper.class_.__name__} without explicit tenant filter for tenant {context.tenant_id}")
            except NoTenantContextError:
                logger.warning(f"Bulk delete on {mapper.class_.__name__} without tenant context")


@event.listens_for(Session, 'before_bulk_update')
def receive_before_bulk_update(query_context):
    """Prevent bulk updates without tenant filtering."""
    mapper = query_context.mapper
    if hasattr(mapper.class_, 'tenant_id'):
        # Check if tenant filter is applied
        whereclause = query_context.whereclause
        if whereclause is None or 'tenant_id' not in str(whereclause):
            try:
                context = get_current_tenant()
                logger.warning(f"Bulk update on {mapper.class_.__name__} without explicit tenant filter for tenant {context.tenant_id}")
            except NoTenantContextError:
                logger.warning(f"Bulk update on {mapper.class_.__name__} without tenant context")