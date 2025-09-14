"""
Event-driven architecture system for the universal platform.

This module provides a comprehensive event system with:
- Multiple transport mechanisms
- Event sourcing and persistence
- Saga pattern support
- Circuit breakers and error handling
- Performance monitoring
"""

from .event_bus import EventBus, EventBusConfig
from .handlers import EventHandler, HandlerRegistry
from .middleware import EventMiddleware, MiddlewarePipeline
from .persistence import EventStore, EventSourcing
from .serialization import EventSerializer, EventDeserializer
from .models import Event, EventMetadata, EventError
from .saga import Saga, SagaManager
from .circuit_breaker import CircuitBreaker

__all__ = [
    "EventBus",
    "EventBusConfig", 
    "EventHandler",
    "HandlerRegistry",
    "EventMiddleware",
    "MiddlewarePipeline",
    "EventStore",
    "EventSourcing",
    "EventSerializer",
    "EventDeserializer",
    "Event",
    "EventMetadata",
    "EventError",
    "Saga",
    "SagaManager",
    "CircuitBreaker",
]