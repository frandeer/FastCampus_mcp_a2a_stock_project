"""
Multi-tenant management system providing tenant isolation and resource management
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional, Set
from contextlib import contextmanager
from dataclasses import dataclass, field

from ...core.di import injectable, singleton, inject
from ...core.events import EventBus
from .models import TenantInfo, TenantStatus, AuditLog, LogLevel

logger = logging.getLogger(__name__)


@dataclass
class TenantContext:
    """Current tenant context"""
    tenant_id: str
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    permissions: Set[str] = field(default_factory=set)
    metadata: Dict[str, any] = field(default_factory=dict)


@singleton
@injectable
class TenantManager:
    """
    Multi-tenant management system providing:
    - Tenant registration and lifecycle management
    - Tenant-aware data isolation
    - Resource limits and quotas
    - Tenant context management
    - Cross-tenant security enforcement
    """
    
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.tenants: Dict[str, TenantInfo] = {}
        self.tenant_contexts: Dict[str, TenantContext] = {}
        self.resource_usage: Dict[str, Dict[str, int]] = {}
        self._current_context: Optional[TenantContext] = None
        
        # Initialize default tenant
        self.tenants["default"] = TenantInfo(
            tenant_id="default",
            name="Default Tenant",
            description="Default system tenant",
            status=TenantStatus.ACTIVE,
            domains_enabled=["ecommerce", "healthcare", "logistics"],
            resource_limits={
                "max_users": 1000,
                "max_storage_mb": 10240,
                "max_api_calls_per_hour": 10000
            }
        )
    
    async def initialize(self):
        """Initialize tenant manager"""
        try:
            # Setup event subscriptions
            await self.event_bus.subscribe("tenant.*", self._handle_tenant_event)
            
            # Initialize resource tracking
            for tenant_id in self.tenants.keys():
                self.resource_usage[tenant_id] = {
                    "users": 0,
                    "storage_mb": 0,
                    "api_calls_hour": 0,
                    "active_sessions": 0
                }
            
            logger.info("Tenant manager initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize tenant manager: {e}")
            raise
    
    async def create_tenant(self, tenant_info: TenantInfo) -> TenantInfo:
        """Create a new tenant"""
        try:
            if tenant_info.tenant_id in self.tenants:
                raise ValueError(f"Tenant {tenant_info.tenant_id} already exists")
            
            # Set creation time
            tenant_info.created_at = datetime.utcnow()
            
            # Initialize resource usage tracking
            self.resource_usage[tenant_info.tenant_id] = {
                "users": 0,
                "storage_mb": 0, 
                "api_calls_hour": 0,
                "active_sessions": 0
            }
            
            # Store tenant
            self.tenants[tenant_info.tenant_id] = tenant_info
            
            # Publish event
            await self.event_bus.publish("tenant.created", {
                "tenant_id": tenant_info.tenant_id,
                "tenant_info": tenant_info.to_dict()
            })
            
            # Log creation
            await self._log_audit_event(
                tenant_id=tenant_info.tenant_id,
                action="tenant.created",
                entity_type="tenant",
                entity_id=tenant_info.tenant_id,
                message=f"Tenant '{tenant_info.name}' created"
            )
            
            logger.info(f"Created tenant: {tenant_info.tenant_id}")
            return tenant_info
            
        except Exception as e:
            logger.error(f"Failed to create tenant {tenant_info.tenant_id}: {e}")
            raise
    
    async def get_tenant(self, tenant_id: str) -> Optional[TenantInfo]:
        """Get tenant information"""
        return self.tenants.get(tenant_id)
    
    async def list_tenants(self, status_filter: Optional[TenantStatus] = None) -> List[TenantInfo]:
        """List all tenants with optional status filter"""
        tenants = list(self.tenants.values())
        
        if status_filter:
            tenants = [t for t in tenants if t.status == status_filter]
        
        return tenants
    
    async def update_tenant(self, tenant_id: str, updates: Dict[str, any]) -> TenantInfo:
        """Update tenant information"""
        try:
            if tenant_id not in self.tenants:
                raise ValueError(f"Tenant {tenant_id} not found")
            
            tenant = self.tenants[tenant_id]
            old_values = tenant.to_dict()
            
            # Apply updates
            for key, value in updates.items():
                if hasattr(tenant, key):
                    setattr(tenant, key, value)
            
            # Publish event
            await self.event_bus.publish("tenant.updated", {
                "tenant_id": tenant_id,
                "updates": updates
            })
            
            # Log update
            await self._log_audit_event(
                tenant_id=tenant_id,
                action="tenant.updated",
                entity_type="tenant",
                entity_id=tenant_id,
                old_values=old_values,
                new_values=tenant.to_dict(),
                message=f"Tenant '{tenant.name}' updated"
            )
            
            logger.info(f"Updated tenant: {tenant_id}")
            return tenant
            
        except Exception as e:
            logger.error(f"Failed to update tenant {tenant_id}: {e}")
            raise
    
    async def delete_tenant(self, tenant_id: str):
        """Delete a tenant (soft delete by setting status)"""
        try:
            if tenant_id not in self.tenants:
                raise ValueError(f"Tenant {tenant_id} not found")
            
            if tenant_id == "default":
                raise ValueError("Cannot delete default tenant")
            
            tenant = self.tenants[tenant_id]
            tenant.status = TenantStatus.CANCELLED
            
            # Clear resource tracking
            if tenant_id in self.resource_usage:
                del self.resource_usage[tenant_id]
            
            # Publish event
            await self.event_bus.publish("tenant.deleted", {
                "tenant_id": tenant_id
            })
            
            # Log deletion
            await self._log_audit_event(
                tenant_id=tenant_id,
                action="tenant.deleted",
                entity_type="tenant", 
                entity_id=tenant_id,
                message=f"Tenant '{tenant.name}' deleted"
            )
            
            logger.info(f"Deleted tenant: {tenant_id}")
            
        except Exception as e:
            logger.error(f"Failed to delete tenant {tenant_id}: {e}")
            raise
    
    @contextmanager
    def tenant_context(self, tenant_id: str, user_id: Optional[str] = None):
        """Context manager for tenant-scoped operations"""
        if tenant_id not in self.tenants:
            raise ValueError(f"Tenant {tenant_id} not found")
        
        old_context = self._current_context
        
        try:
            self._current_context = TenantContext(
                tenant_id=tenant_id,
                user_id=user_id
            )
            yield self._current_context
        finally:
            self._current_context = old_context
    
    def get_current_tenant_id(self) -> str:
        """Get current tenant ID from context"""
        if self._current_context:
            return self._current_context.tenant_id
        return "default"
    
    def get_current_context(self) -> Optional[TenantContext]:
        """Get current tenant context"""
        return self._current_context
    
    async def check_resource_limits(self, tenant_id: str, resource_type: str, requested_amount: int = 1) -> bool:
        """Check if tenant can use additional resources"""
        try:
            if tenant_id not in self.tenants:
                return False
            
            tenant = self.tenants[tenant_id]
            current_usage = self.resource_usage.get(tenant_id, {})
            
            # Check specific resource limits
            if resource_type == "users":
                limit = tenant.resource_limits.get("max_users", 0)
                current = current_usage.get("users", 0)
            elif resource_type == "storage_mb":
                limit = tenant.resource_limits.get("max_storage_mb", 0)
                current = current_usage.get("storage_mb", 0)
            elif resource_type == "api_calls":
                limit = tenant.resource_limits.get("max_api_calls_per_hour", 0)
                current = current_usage.get("api_calls_hour", 0)
            else:
                # Unknown resource type, allow by default
                return True
            
            return (current + requested_amount) <= limit
            
        except Exception as e:
            logger.error(f"Error checking resource limits for tenant {tenant_id}: {e}")
            return False
    
    async def update_resource_usage(self, tenant_id: str, resource_type: str, delta: int):
        """Update resource usage for a tenant"""
        try:
            if tenant_id not in self.resource_usage:
                self.resource_usage[tenant_id] = {
                    "users": 0,
                    "storage_mb": 0,
                    "api_calls_hour": 0,
                    "active_sessions": 0
                }
            
            current = self.resource_usage[tenant_id].get(resource_type, 0)
            self.resource_usage[tenant_id][resource_type] = max(0, current + delta)
            
        except Exception as e:
            logger.error(f"Error updating resource usage for tenant {tenant_id}: {e}")
    
    async def get_resource_usage(self, tenant_id: str) -> Dict[str, int]:
        """Get current resource usage for a tenant"""
        return self.resource_usage.get(tenant_id, {})
    
    async def is_domain_enabled(self, tenant_id: str, domain: str) -> bool:
        """Check if a domain is enabled for a tenant"""
        tenant = await self.get_tenant(tenant_id)
        if not tenant:
            return False
        
        return domain in tenant.domains_enabled
    
    async def enable_domain(self, tenant_id: str, domain: str):
        """Enable a domain for a tenant"""
        tenant = await self.get_tenant(tenant_id)
        if not tenant:
            raise ValueError(f"Tenant {tenant_id} not found")
        
        if domain not in tenant.domains_enabled:
            tenant.domains_enabled.append(domain)
            
            await self.event_bus.publish("tenant.domain.enabled", {
                "tenant_id": tenant_id,
                "domain": domain
            })
            
            await self._log_audit_event(
                tenant_id=tenant_id,
                action="domain.enabled",
                entity_type="tenant",
                entity_id=tenant_id,
                message=f"Domain '{domain}' enabled for tenant"
            )
    
    async def disable_domain(self, tenant_id: str, domain: str):
        """Disable a domain for a tenant"""
        tenant = await self.get_tenant(tenant_id)
        if not tenant:
            raise ValueError(f"Tenant {tenant_id} not found")
        
        if domain in tenant.domains_enabled:
            tenant.domains_enabled.remove(domain)
            
            await self.event_bus.publish("tenant.domain.disabled", {
                "tenant_id": tenant_id,
                "domain": domain
            })
            
            await self._log_audit_event(
                tenant_id=tenant_id,
                action="domain.disabled", 
                entity_type="tenant",
                entity_id=tenant_id,
                message=f"Domain '{domain}' disabled for tenant"
            )
    
    async def _handle_tenant_event(self, event_type: str, event_data: Dict[str, any]):
        """Handle tenant-related events"""
        try:
            logger.debug(f"Handling tenant event: {event_type}")
            
            # Update resource usage based on events
            if event_type == "user.created":
                tenant_id = event_data.get("tenant_id", "default")
                await self.update_resource_usage(tenant_id, "users", 1)
            elif event_type == "user.deleted":
                tenant_id = event_data.get("tenant_id", "default")
                await self.update_resource_usage(tenant_id, "users", -1)
            elif event_type == "storage.used":
                tenant_id = event_data.get("tenant_id", "default")
                amount = event_data.get("amount_mb", 0)
                await self.update_resource_usage(tenant_id, "storage_mb", amount)
            elif event_type == "api.call":
                tenant_id = event_data.get("tenant_id", "default")
                await self.update_resource_usage(tenant_id, "api_calls_hour", 1)
            
        except Exception as e:
            logger.error(f"Error handling tenant event {event_type}: {e}")
    
    async def _log_audit_event(
        self,
        tenant_id: str,
        action: str,
        entity_type: str,
        entity_id: str,
        user_id: Optional[str] = None,
        old_values: Optional[Dict[str, any]] = None,
        new_values: Optional[Dict[str, any]] = None,
        message: Optional[str] = None
    ):
        """Log audit event"""
        try:
            audit_log = AuditLog(
                tenant_id=tenant_id,
                user_id=user_id,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                old_values=old_values,
                new_values=new_values,
                level=LogLevel.INFO,
                message=message
            )
            
            # Publish audit event
            await self.event_bus.publish("audit.logged", audit_log.to_dict())
            
        except Exception as e:
            logger.error(f"Failed to log audit event: {e}")