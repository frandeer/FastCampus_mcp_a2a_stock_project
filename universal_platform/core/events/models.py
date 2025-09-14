"""
Core event models and data structures.
"""

import uuid
from datetime import datetime
from typing import Any, Dict, Optional, List, Union
from dataclasses import dataclass, field
from enum import Enum
import json


class EventStatus(Enum):
    """Event processing status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"
    DEAD_LETTER = "dead_letter"


class EventPriority(Enum):
    """Event priority levels."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class EventMetadata:
    """Event metadata for tracking and routing."""
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    correlation_id: Optional[str] = None
    causation_id: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    version: int = 1
    source: Optional[str] = None
    priority: EventPriority = EventPriority.NORMAL
    retry_count: int = 0
    max_retries: int = 3
    timeout_seconds: Optional[int] = None
    scheduled_for: Optional[datetime] = None
    tags: List[str] = field(default_factory=list)
    trace_id: Optional[str] = None
    span_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metadata to dictionary."""
        return {
            "event_id": self.event_id,
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
            "timestamp": self.timestamp.isoformat(),
            "version": self.version,
            "source": self.source,
            "priority": self.priority.value,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "timeout_seconds": self.timeout_seconds,
            "scheduled_for": self.scheduled_for.isoformat() if self.scheduled_for else None,
            "tags": self.tags,
            "trace_id": self.trace_id,
            "span_id": self.span_id,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EventMetadata":
        """Create metadata from dictionary."""
        timestamp = datetime.fromisoformat(data["timestamp"])
        scheduled_for = None
        if data.get("scheduled_for"):
            scheduled_for = datetime.fromisoformat(data["scheduled_for"])
            
        return cls(
            event_id=data["event_id"],
            correlation_id=data.get("correlation_id"),
            causation_id=data.get("causation_id"),
            timestamp=timestamp,
            version=data.get("version", 1),
            source=data.get("source"),
            priority=EventPriority(data.get("priority", EventPriority.NORMAL.value)),
            retry_count=data.get("retry_count", 0),
            max_retries=data.get("max_retries", 3),
            timeout_seconds=data.get("timeout_seconds"),
            scheduled_for=scheduled_for,
            tags=data.get("tags", []),
            trace_id=data.get("trace_id"),
            span_id=data.get("span_id"),
        )


@dataclass
class Event:
    """Base event class."""
    event_type: str
    data: Dict[str, Any]
    metadata: EventMetadata = field(default_factory=EventMetadata)
    
    def __post_init__(self):
        """Post-initialization processing."""
        if not self.metadata.event_id:
            self.metadata.event_id = str(uuid.uuid4())
            
    @property
    def event_id(self) -> str:
        """Get event ID."""
        return self.metadata.event_id
    
    @property
    def correlation_id(self) -> Optional[str]:
        """Get correlation ID."""
        return self.metadata.correlation_id
    
    @property
    def timestamp(self) -> datetime:
        """Get event timestamp."""
        return self.metadata.timestamp
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary."""
        return {
            "event_type": self.event_type,
            "data": self.data,
            "metadata": self.metadata.to_dict(),
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Event":
        """Create event from dictionary."""
        metadata = EventMetadata.from_dict(data["metadata"])
        return cls(
            event_type=data["event_type"],
            data=data["data"],
            metadata=metadata,
        )
    
    def to_json(self) -> str:
        """Convert event to JSON string."""
        return json.dumps(self.to_dict(), default=str)
    
    @classmethod
    def from_json(cls, json_str: str) -> "Event":
        """Create event from JSON string."""
        data = json.loads(json_str)
        return cls.from_dict(data)
    
    def create_child_event(self, event_type: str, data: Dict[str, Any]) -> "Event":
        """Create a child event with proper correlation tracking."""
        child_metadata = EventMetadata(
            correlation_id=self.metadata.correlation_id or self.metadata.event_id,
            causation_id=self.metadata.event_id,
            source=self.metadata.source,
            trace_id=self.metadata.trace_id,
        )
        return Event(event_type=event_type, data=data, metadata=child_metadata)


@dataclass
class EventError:
    """Event processing error information."""
    error_type: str
    message: str
    stack_trace: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    retry_count: int = 0
    context: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary."""
        return {
            "error_type": self.error_type,
            "message": self.message,
            "stack_trace": self.stack_trace,
            "timestamp": self.timestamp.isoformat(),
            "retry_count": self.retry_count,
            "context": self.context,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EventError":
        """Create error from dictionary."""
        return cls(
            error_type=data["error_type"],
            message=data["message"],
            stack_trace=data.get("stack_trace"),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            retry_count=data.get("retry_count", 0),
            context=data.get("context", {}),
        )


@dataclass
class EventResult:
    """Event processing result."""
    event_id: str
    status: EventStatus
    result: Optional[Any] = None
    error: Optional[EventError] = None
    processing_time_ms: Optional[float] = None
    handler_name: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary."""
        return {
            "event_id": self.event_id,
            "status": self.status.value,
            "result": self.result,
            "error": self.error.to_dict() if self.error else None,
            "processing_time_ms": self.processing_time_ms,
            "handler_name": self.handler_name,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class DeadLetterEvent:
    """Dead letter event for failed processing."""
    original_event: Event
    error: EventError
    final_attempt_timestamp: datetime = field(default_factory=datetime.utcnow)
    total_attempts: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert dead letter event to dictionary."""
        return {
            "original_event": self.original_event.to_dict(),
            "error": self.error.to_dict(),
            "final_attempt_timestamp": self.final_attempt_timestamp.isoformat(),
            "total_attempts": self.total_attempts,
        }


# Common event types
class SystemEvents:
    """Common system event types."""
    SYSTEM_STARTUP = "system.startup"
    SYSTEM_SHUTDOWN = "system.shutdown"
    HEALTH_CHECK = "system.health_check"
    CONFIGURATION_CHANGED = "system.configuration_changed"
    
class ApplicationEvents:
    """Common application event types."""
    USER_CREATED = "user.created"
    USER_UPDATED = "user.updated"
    USER_DELETED = "user.deleted"
    SESSION_STARTED = "session.started"
    SESSION_ENDED = "session.ended"
    
class ErrorEvents:
    """Error event types."""
    VALIDATION_ERROR = "error.validation"
    PROCESSING_ERROR = "error.processing"
    TIMEOUT_ERROR = "error.timeout"
    DEPENDENCY_ERROR = "error.dependency"