"""
Shared data models and base entities for cross-domain functionality
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from uuid import uuid4, UUID
from enum import Enum
from dataclasses import dataclass, field
from pydantic import BaseModel, Field
import json


class EntityStatus(str, Enum):
    """Common entity status values"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING = "pending"
    SUSPENDED = "suspended"
    DELETED = "deleted"


class TenantStatus(str, Enum):
    """Tenant status values"""
    ACTIVE = "active"
    TRIAL = "trial"
    SUSPENDED = "suspended"
    CANCELLED = "cancelled"


class LogLevel(str, Enum):
    """Log level enumeration"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class BaseEntity:
    """Base entity with common fields for all domain objects"""
    id: str = field(default_factory=lambda: str(uuid4()))
    tenant_id: str = field(default="default")
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    created_by: Optional[str] = None
    updated_by: Optional[str] = None
    version: int = field(default=1)
    status: EntityStatus = field(default=EntityStatus.ACTIVE)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def mark_updated(self, updated_by: Optional[str] = None):
        """Mark entity as updated"""
        self.updated_at = datetime.utcnow()
        self.updated_by = updated_by
        self.version += 1
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert entity to dictionary"""
        result = {}
        for key, value in self.__dict__.items():
            if isinstance(value, datetime):
                result[key] = value.isoformat()
            elif isinstance(value, Enum):
                result[key] = value.value
            else:
                result[key] = value
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BaseEntity':
        """Create entity from dictionary"""
        # Convert datetime strings back to datetime objects
        if 'created_at' in data and isinstance(data['created_at'], str):
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        if 'updated_at' in data and isinstance(data['updated_at'], str):
            data['updated_at'] = datetime.fromisoformat(data['updated_at'])
        
        # Convert status string to enum
        if 'status' in data and isinstance(data['status'], str):
            data['status'] = EntityStatus(data['status'])
        
        return cls(**data)


@dataclass 
class TenantInfo:
    """Tenant information for multi-tenancy"""
    tenant_id: str
    name: str
    description: Optional[str] = None
    status: TenantStatus = field(default=TenantStatus.ACTIVE)
    created_at: datetime = field(default_factory=datetime.utcnow)
    settings: Dict[str, Any] = field(default_factory=dict)
    domains_enabled: List[str] = field(default_factory=list)
    resource_limits: Dict[str, int] = field(default_factory=dict)
    contact_email: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "tenant_id": self.tenant_id,
            "name": self.name,
            "description": self.description,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "settings": self.settings,
            "domains_enabled": self.domains_enabled,
            "resource_limits": self.resource_limits,
            "contact_email": self.contact_email
        }


@dataclass
class AuditLog:
    """Audit log entry for tracking changes and actions"""
    id: str = field(default_factory=lambda: str(uuid4()))
    tenant_id: str = field(default="default")
    timestamp: datetime = field(default_factory=datetime.utcnow)
    user_id: Optional[str] = None
    action: str = ""
    entity_type: str = ""
    entity_id: str = ""
    old_values: Optional[Dict[str, Any]] = None
    new_values: Optional[Dict[str, Any]] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    session_id: Optional[str] = None
    level: LogLevel = field(default=LogLevel.INFO)
    message: Optional[str] = None
    additional_data: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "timestamp": self.timestamp.isoformat(),
            "user_id": self.user_id,
            "action": self.action,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "old_values": self.old_values,
            "new_values": self.new_values,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "session_id": self.session_id,
            "level": self.level.value,
            "message": self.message,
            "additional_data": self.additional_data
        }


# Pydantic models for API requests/responses
class BaseResponse(BaseModel):
    """Base response model"""
    success: bool = True
    message: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    

class ErrorResponse(BaseResponse):
    """Error response model"""
    success: bool = False
    error_code: Optional[str] = None
    error_details: Optional[Dict[str, Any]] = None


class PaginatedResponse(BaseResponse):
    """Paginated response model"""
    total: int
    page: int = 1
    page_size: int = 10
    total_pages: int
    
    @classmethod
    def create(cls, items: List, total: int, page: int = 1, page_size: int = 10):
        """Create paginated response"""
        total_pages = (total + page_size - 1) // page_size
        return cls(
            data=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages
        )


class HealthStatus(BaseModel):
    """Health check status model"""
    service: str
    status: str  # healthy, unhealthy, degraded
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    response_time_ms: Optional[float] = None
    details: Optional[Dict[str, Any]] = None
    dependencies: Optional[List['HealthStatus']] = None


class MetricData(BaseModel):
    """Metric data model"""
    name: str
    value: float
    unit: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    labels: Dict[str, str] = Field(default_factory=dict)
    type: str = "gauge"  # gauge, counter, histogram


class ConfigurationItem(BaseModel):
    """Configuration item model"""
    key: str
    value: Any
    description: Optional[str] = None
    is_sensitive: bool = False
    requires_restart: bool = False
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    updated_by: Optional[str] = None


class EventInfo(BaseModel):
    """Event information model"""
    event_type: str
    event_data: Dict[str, Any]
    source: str
    correlation_id: Optional[str] = None
    tenant_id: str = "default"
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)


# Update forward references
HealthStatus.model_rebuild()