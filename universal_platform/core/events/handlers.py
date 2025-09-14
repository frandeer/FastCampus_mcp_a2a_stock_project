"""
Event handler registration and management system.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable, Union, Set
from datetime import datetime
import inspect
import weakref
from collections import defaultdict
from enum import Enum

from .models import Event, EventResult, EventStatus, EventError


logger = logging.getLogger(__name__)


class HandlerPriority(Enum):
    """Handler priority levels."""
    LOWEST = 0
    LOW = 25
    NORMAL = 50
    HIGH = 75
    HIGHEST = 100


@dataclass
class HandlerMetadata:
    """Metadata for event handlers."""
    name: str
    description: Optional[str] = None
    version: str = "1.0.0"
    author: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    timeout_seconds: Optional[int] = None
    retry_count: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_executed: Optional[datetime] = None
    execution_count: int = 0
    success_count: int = 0
    failure_count: int = 0


@dataclass
class EventHandler:
    """Event handler definition."""
    name: str
    handler_func: Callable[[Event], Any]
    event_types: List[str]
    priority: int = HandlerPriority.NORMAL.value
    condition: Optional[Callable[[Event], bool]] = None
    metadata: Optional[HandlerMetadata] = None
    is_async: bool = True
    
    def __post_init__(self):
        """Post-initialization processing."""
        if self.metadata is None:
            self.metadata = HandlerMetadata(name=self.name)
        
        # Auto-detect if handler is async
        self.is_async = asyncio.iscoroutinefunction(self.handler_func)
    
    def matches_event(self, event: Event) -> bool:
        """Check if handler matches the event."""
        # Check event type
        if event.event_type not in self.event_types and "*" not in self.event_types:
            return False
        
        # Check condition if provided
        if self.condition and not self.condition(event):
            return False
        
        return True
    
    async def handle(self, event: Event) -> Any:
        """Execute the handler for the event."""
        start_time = datetime.utcnow()
        
        try:
            # Update metadata
            self.metadata.execution_count += 1
            self.metadata.last_executed = start_time
            
            # Execute handler
            if self.is_async:
                result = await self.handler_func(event)
            else:
                result = self.handler_func(event)
            
            # Update success metrics
            self.metadata.success_count += 1
            
            logger.debug(f"Handler {self.name} executed successfully for event {event.event_id}")
            return result
            
        except Exception as e:
            # Update failure metrics
            self.metadata.failure_count += 1
            
            logger.error(f"Handler {self.name} failed for event {event.event_id}: {e}")
            raise
    
    def get_stats(self) -> Dict[str, Any]:
        """Get handler statistics."""
        success_rate = 0.0
        if self.metadata.execution_count > 0:
            success_rate = self.metadata.success_count / self.metadata.execution_count
        
        return {
            "name": self.name,
            "event_types": self.event_types,
            "priority": self.priority,
            "execution_count": self.metadata.execution_count,
            "success_count": self.metadata.success_count,
            "failure_count": self.metadata.failure_count,
            "success_rate": success_rate,
            "last_executed": self.metadata.last_executed.isoformat() if self.metadata.last_executed else None,
            "created_at": self.metadata.created_at.isoformat(),
        }


class HandlerDecorator:
    """Decorator for event handlers."""
    
    def __init__(
        self,
        event_types: Union[str, List[str]],
        priority: int = HandlerPriority.NORMAL.value,
        condition: Optional[Callable[[Event], bool]] = None,
        timeout_seconds: Optional[int] = None,
        retry_count: int = 0,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ):
        self.event_types = [event_types] if isinstance(event_types, str) else event_types
        self.priority = priority
        self.condition = condition
        self.timeout_seconds = timeout_seconds
        self.retry_count = retry_count
        self.description = description
        self.tags = tags or []
    
    def __call__(self, func: Callable) -> EventHandler:
        """Create event handler from decorated function."""
        metadata = HandlerMetadata(
            name=func.__name__,
            description=self.description or func.__doc__,
            timeout_seconds=self.timeout_seconds,
            retry_count=self.retry_count,
            tags=self.tags,
        )
        
        return EventHandler(
            name=func.__name__,
            handler_func=func,
            event_types=self.event_types,
            priority=self.priority,
            condition=self.condition,
            metadata=metadata,
        )


# Decorator function
def event_handler(
    event_types: Union[str, List[str]],
    priority: int = HandlerPriority.NORMAL.value,
    condition: Optional[Callable[[Event], bool]] = None,
    timeout_seconds: Optional[int] = None,
    retry_count: int = 0,
    description: Optional[str] = None,
    tags: Optional[List[str]] = None,
):
    """Decorator for creating event handlers."""
    return HandlerDecorator(
        event_types=event_types,
        priority=priority,
        condition=condition,
        timeout_seconds=timeout_seconds,
        retry_count=retry_count,
        description=description,
        tags=tags,
    )


class HandlerRegistry:
    """Registry for managing event handlers."""
    
    def __init__(self):
        self._handlers: Dict[str, List[EventHandler]] = defaultdict(list)
        self._handler_by_name: Dict[str, EventHandler] = {}
        self._weak_refs: Dict[str, weakref.ReferenceType] = {}
        self._lock = asyncio.Lock()
        
        logger.info("HandlerRegistry initialized")
    
    async def register(self, handler: EventHandler) -> None:
        """Register an event handler."""
        async with self._lock:
            # Check for duplicate names
            if handler.name in self._handler_by_name:
                raise ValueError(f"Handler with name '{handler.name}' already registered")
            
            # Register for each event type
            for event_type in handler.event_types:
                self._handlers[event_type].append(handler)
                
                # Sort by priority (highest first)
                self._handlers[event_type].sort(key=lambda h: h.priority, reverse=True)
            
            # Store by name for lookup
            self._handler_by_name[handler.name] = handler
            
            logger.info(f"Registered handler '{handler.name}' for events: {handler.event_types}")
    
    async def unregister(self, event_type: str, handler_name: str) -> bool:
        """Unregister an event handler."""
        async with self._lock:
            if handler_name not in self._handler_by_name:
                return False
            
            handler = self._handler_by_name[handler_name]
            
            # Remove from event type lists
            removed = False
            if event_type in self._handlers:
                handlers_before = len(self._handlers[event_type])
                self._handlers[event_type] = [
                    h for h in self._handlers[event_type] if h.name != handler_name
                ]
                removed = len(self._handlers[event_type]) < handlers_before
                
                # Clean up empty lists
                if not self._handlers[event_type]:
                    del self._handlers[event_type]
            
            # If this was the handler's last event type, remove from name registry
            if not any(handler in handlers for handlers in self._handlers.values()):
                del self._handler_by_name[handler_name]
            
            if removed:
                logger.info(f"Unregistered handler '{handler_name}' from event type '{event_type}'")
            
            return removed
    
    async def unregister_all(self, handler_name: str) -> bool:
        """Unregister handler from all event types."""
        async with self._lock:
            if handler_name not in self._handler_by_name:
                return False
            
            handler = self._handler_by_name[handler_name]
            
            # Remove from all event types
            for event_type in list(self._handlers.keys()):
                self._handlers[event_type] = [
                    h for h in self._handlers[event_type] if h.name != handler_name
                ]
                
                # Clean up empty lists
                if not self._handlers[event_type]:
                    del self._handlers[event_type]
            
            # Remove from name registry
            del self._handler_by_name[handler_name]
            
            logger.info(f"Unregistered handler '{handler_name}' from all event types")
            return True
    
    def get_handlers(self, event_type: str) -> List[EventHandler]:
        """Get handlers for a specific event type."""
        # Get exact matches
        handlers = self._handlers.get(event_type, []).copy()
        
        # Add wildcard handlers
        wildcard_handlers = self._handlers.get("*", [])
        handlers.extend(wildcard_handlers)
        
        # Sort by priority (highest first)
        handlers.sort(key=lambda h: h.priority, reverse=True)
        
        return handlers
    
    def get_handler(self, handler_name: str) -> Optional[EventHandler]:
        """Get handler by name."""
        return self._handler_by_name.get(handler_name)
    
    def list_handlers(self) -> List[EventHandler]:
        """List all registered handlers."""
        return list(self._handler_by_name.values())
    
    def list_event_types(self) -> List[str]:
        """List all registered event types."""
        return list(self._handlers.keys())
    
    def get_status(self) -> Dict[str, Any]:
        """Get registry status."""
        handler_count_by_type = {
            event_type: len(handlers) for event_type, handlers in self._handlers.items()
        }
        
        return {
            "total_handlers": len(self._handler_by_name),
            "event_types": len(self._handlers),
            "handlers_by_type": handler_count_by_type,
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """Get detailed statistics."""
        stats = {
            "total_handlers": len(self._handler_by_name),
            "total_event_types": len(self._handlers),
            "handlers": [],
        }
        
        for handler in self._handler_by_name.values():
            stats["handlers"].append(handler.get_stats())
        
        return stats
    
    async def validate_handlers(self) -> Dict[str, List[str]]:
        """Validate all registered handlers."""
        validation_errors = defaultdict(list)
        
        for handler_name, handler in self._handler_by_name.items():
            # Check if handler function is still valid
            if not callable(handler.handler_func):
                validation_errors[handler_name].append("Handler function is not callable")
            
            # Check if event types are valid
            if not handler.event_types:
                validation_errors[handler_name].append("No event types specified")
            
            # Check for required dependencies
            if handler.metadata and handler.metadata.dependencies:
                for dep in handler.metadata.dependencies:
                    if dep not in self._handler_by_name:
                        validation_errors[handler_name].append(f"Missing dependency: {dep}")
        
        return dict(validation_errors)
    
    async def get_dependency_graph(self) -> Dict[str, List[str]]:
        """Get handler dependency graph."""
        graph = {}
        
        for handler_name, handler in self._handler_by_name.items():
            dependencies = []
            if handler.metadata and handler.metadata.dependencies:
                dependencies = [
                    dep for dep in handler.metadata.dependencies 
                    if dep in self._handler_by_name
                ]
            graph[handler_name] = dependencies
        
        return graph
    
    async def execute_handlers_for_event(self, event: Event) -> List[Any]:
        """Execute all matching handlers for an event."""
        handlers = self.get_handlers(event.event_type)
        
        if not handlers:
            logger.debug(f"No handlers found for event type: {event.event_type}")
            return []
        
        results = []
        for handler in handlers:
            try:
                if handler.matches_event(event):
                    result = await handler.handle(event)
                    results.append(result)
            except Exception as e:
                logger.error(f"Handler {handler.name} failed: {e}")
                # Continue with other handlers
        
        return results


class ConditionalHandler:
    """Handler with advanced conditional logic."""
    
    def __init__(
        self,
        name: str,
        handler_func: Callable[[Event], Any],
        event_types: List[str],
        conditions: Optional[Dict[str, Any]] = None,
        priority: int = HandlerPriority.NORMAL.value,
    ):
        self.handler = EventHandler(
            name=name,
            handler_func=handler_func,
            event_types=event_types,
            priority=priority,
            condition=self._build_condition(conditions or {}),
        )
    
    def _build_condition(self, conditions: Dict[str, Any]) -> Callable[[Event], bool]:
        """Build condition function from configuration."""
        def condition_func(event: Event) -> bool:
            # Check data field conditions
            if "data" in conditions:
                for key, expected_value in conditions["data"].items():
                    if event.data.get(key) != expected_value:
                        return False
            
            # Check metadata conditions
            if "metadata" in conditions:
                metadata_conditions = conditions["metadata"]
                
                if "source" in metadata_conditions:
                    if event.metadata.source != metadata_conditions["source"]:
                        return False
                
                if "priority" in metadata_conditions:
                    expected_priority = metadata_conditions["priority"]
                    if isinstance(expected_priority, str):
                        from .models import EventPriority
                        expected_priority = EventPriority[expected_priority.upper()]
                    if event.metadata.priority != expected_priority:
                        return False
                
                if "tags" in metadata_conditions:
                    required_tags = metadata_conditions["tags"]
                    if not all(tag in event.metadata.tags for tag in required_tags):
                        return False
            
            # Check time-based conditions
            if "time" in conditions:
                time_conditions = conditions["time"]
                
                if "after" in time_conditions:
                    after_time = datetime.fromisoformat(time_conditions["after"])
                    if event.metadata.timestamp <= after_time:
                        return False
                
                if "before" in time_conditions:
                    before_time = datetime.fromisoformat(time_conditions["before"])
                    if event.metadata.timestamp >= before_time:
                        return False
            
            return True
        
        return condition_func


class HandlerChain:
    """Chain of handlers for sequential processing."""
    
    def __init__(self, name: str, handlers: List[EventHandler]):
        self.name = name
        self.handlers = handlers
        self._execution_stats = {
            "total_executions": 0,
            "successful_executions": 0,
            "failed_executions": 0,
            "average_execution_time": 0.0,
        }
    
    async def execute(self, event: Event) -> List[Any]:
        """Execute handler chain."""
        start_time = datetime.utcnow()
        results = []
        
        try:
            self._execution_stats["total_executions"] += 1
            
            for handler in self.handlers:
                try:
                    if handler.matches_event(event):
                        result = await handler.handle(event)
                        results.append(result)
                        
                        # Pass result to next handler if it's an event
                        if isinstance(result, Event):
                            event = result
                            
                except Exception as e:
                    logger.error(f"Handler chain {self.name} failed at {handler.name}: {e}")
                    raise
            
            self._execution_stats["successful_executions"] += 1
            
        except Exception as e:
            self._execution_stats["failed_executions"] += 1
            raise
        
        finally:
            # Update timing stats
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            current_avg = self._execution_stats["average_execution_time"]
            total_executions = self._execution_stats["total_executions"]
            
            # Calculate new average
            self._execution_stats["average_execution_time"] = (
                (current_avg * (total_executions - 1) + execution_time) / total_executions
            )
        
        return results
    
    def get_stats(self) -> Dict[str, Any]:
        """Get chain execution statistics."""
        success_rate = 0.0
        if self._execution_stats["total_executions"] > 0:
            success_rate = (
                self._execution_stats["successful_executions"] / 
                self._execution_stats["total_executions"]
            )
        
        return {
            "name": self.name,
            "handler_count": len(self.handlers),
            "execution_stats": self._execution_stats,
            "success_rate": success_rate,
        }


class HandlerGroup:
    """Group of handlers for parallel processing."""
    
    def __init__(self, name: str, handlers: List[EventHandler]):
        self.name = name
        self.handlers = handlers
    
    async def execute(self, event: Event) -> List[Any]:
        """Execute handlers in parallel."""
        matching_handlers = [h for h in self.handlers if h.matches_event(event)]
        
        if not matching_handlers:
            return []
        
        # Execute all handlers concurrently
        tasks = [handler.handle(event) for handler in matching_handlers]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out exceptions and log them
        successful_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                handler_name = matching_handlers[i].name
                logger.error(f"Handler {handler_name} in group {self.name} failed: {result}")
            else:
                successful_results.append(result)
        
        return successful_results