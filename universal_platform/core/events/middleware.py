"""
Event middleware pipeline for event processing.
"""

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable, Union, Type
from datetime import datetime
from enum import Enum
import json
import traceback

from .models import Event, EventMetadata, EventResult, EventError


logger = logging.getLogger(__name__)


class MiddlewareType(Enum):
    """Middleware execution types."""
    INBOUND = "inbound"  # Before event processing
    OUTBOUND = "outbound"  # After event processing
    BIDIRECTIONAL = "bidirectional"  # Both inbound and outbound


@dataclass
class MiddlewareContext:
    """Context passed through middleware pipeline."""
    event: Event
    metadata: Dict[str, Any] = field(default_factory=dict)
    start_time: datetime = field(default_factory=datetime.utcnow)
    processing_time_ms: Optional[float] = None
    middleware_stack: List[str] = field(default_factory=list)
    results: List[Any] = field(default_factory=list)
    
    def add_metadata(self, key: str, value: Any) -> None:
        """Add metadata to context."""
        self.metadata[key] = value
    
    def get_metadata(self, key: str, default: Any = None) -> Any:
        """Get metadata from context."""
        return self.metadata.get(key, default)


class EventMiddleware(ABC):
    """Abstract base class for event middleware."""
    
    def __init__(
        self,
        name: str,
        priority: int = 50,
        middleware_type: MiddlewareType = MiddlewareType.BIDIRECTIONAL,
        enabled: bool = True,
    ):
        self.name = name
        self.priority = priority
        self.middleware_type = middleware_type
        self.enabled = enabled
        self._execution_count = 0
        self._error_count = 0
        self._total_execution_time = 0.0
    
    @abstractmethod
    async def process_inbound(self, context: MiddlewareContext) -> MiddlewareContext:
        """Process inbound event (before handler execution)."""
        pass
    
    @abstractmethod
    async def process_outbound(self, context: MiddlewareContext) -> MiddlewareContext:
        """Process outbound event (after handler execution)."""
        pass
    
    async def execute_inbound(self, context: MiddlewareContext) -> MiddlewareContext:
        """Execute inbound processing with error handling."""
        if not self.enabled or self.middleware_type == MiddlewareType.OUTBOUND:
            return context
        
        start_time = time.time()
        
        try:
            context.middleware_stack.append(f"{self.name}:inbound")
            result = await self.process_inbound(context)
            self._execution_count += 1
            return result
            
        except Exception as e:
            self._error_count += 1
            logger.error(f"Middleware {self.name} inbound processing failed: {e}")
            # Continue with original context
            return context
        
        finally:
            execution_time = (time.time() - start_time) * 1000
            self._total_execution_time += execution_time
    
    async def execute_outbound(self, context: MiddlewareContext) -> MiddlewareContext:
        """Execute outbound processing with error handling."""
        if not self.enabled or self.middleware_type == MiddlewareType.INBOUND:
            return context
        
        start_time = time.time()
        
        try:
            context.middleware_stack.append(f"{self.name}:outbound")
            result = await self.process_outbound(context)
            self._execution_count += 1
            return result
            
        except Exception as e:
            self._error_count += 1
            logger.error(f"Middleware {self.name} outbound processing failed: {e}")
            # Continue with original context
            return context
        
        finally:
            execution_time = (time.time() - start_time) * 1000
            self._total_execution_time += execution_time
    
    def get_stats(self) -> Dict[str, Any]:
        """Get middleware execution statistics."""
        avg_execution_time = 0.0
        if self._execution_count > 0:
            avg_execution_time = self._total_execution_time / self._execution_count
        
        return {
            "name": self.name,
            "enabled": self.enabled,
            "type": self.middleware_type.value,
            "priority": self.priority,
            "execution_count": self._execution_count,
            "error_count": self._error_count,
            "average_execution_time_ms": avg_execution_time,
        }


class LoggingMiddleware(EventMiddleware):
    """Middleware for logging event processing."""
    
    def __init__(
        self,
        name: str = "logging",
        log_level: str = "INFO",
        include_data: bool = False,
        max_data_size: int = 1000,
    ):
        super().__init__(name, priority=10)  # High priority for logging
        self.log_level = getattr(logging, log_level.upper())
        self.include_data = include_data
        self.max_data_size = max_data_size
    
    async def process_inbound(self, context: MiddlewareContext) -> MiddlewareContext:
        """Log inbound event."""
        event = context.event
        log_data = {
            "event_id": event.event_id,
            "event_type": event.event_type,
            "source": event.metadata.source,
            "correlation_id": event.metadata.correlation_id,
            "timestamp": event.metadata.timestamp.isoformat(),
        }
        
        if self.include_data:
            data_str = json.dumps(event.data)
            if len(data_str) > self.max_data_size:
                data_str = data_str[:self.max_data_size] + "..."
            log_data["data"] = data_str
        
        logger.log(self.log_level, f"Processing event: {log_data}")
        return context
    
    async def process_outbound(self, context: MiddlewareContext) -> MiddlewareContext:
        """Log outbound event processing result."""
        event = context.event
        processing_time = context.processing_time_ms or 0
        
        log_data = {
            "event_id": event.event_id,
            "event_type": event.event_type,
            "processing_time_ms": processing_time,
            "result_count": len(context.results),
        }
        
        logger.log(self.log_level, f"Event processed: {log_data}")
        return context


class ValidationMiddleware(EventMiddleware):
    """Middleware for event validation."""
    
    def __init__(
        self,
        name: str = "validation",
        schemas: Optional[Dict[str, Dict[str, Any]]] = None,
        strict_mode: bool = False,
    ):
        super().__init__(name, priority=90)  # High priority for validation
        self.schemas = schemas or {}
        self.strict_mode = strict_mode
    
    async def process_inbound(self, context: MiddlewareContext) -> MiddlewareContext:
        """Validate inbound event."""
        event = context.event
        
        # Basic validation
        if not event.event_type:
            raise ValueError("Event type is required")
        
        if not event.event_id:
            raise ValueError("Event ID is required")
        
        # Schema validation if available
        if event.event_type in self.schemas:
            schema = self.schemas[event.event_type]
            await self._validate_against_schema(event, schema)
        elif self.strict_mode:
            raise ValueError(f"No schema found for event type: {event.event_type}")
        
        context.add_metadata("validation_passed", True)
        return context
    
    async def process_outbound(self, context: MiddlewareContext) -> MiddlewareContext:
        """Validate outbound processing."""
        # Could validate results or side effects here
        return context
    
    async def _validate_against_schema(self, event: Event, schema: Dict[str, Any]) -> None:
        """Validate event against schema."""
        # Simple schema validation - could be replaced with jsonschema
        required_fields = schema.get("required", [])
        
        for field in required_fields:
            if field not in event.data:
                raise ValueError(f"Required field '{field}' missing from event data")
        
        # Type validation
        field_types = schema.get("types", {})
        for field, expected_type in field_types.items():
            if field in event.data:
                value = event.data[field]
                if not isinstance(value, expected_type):
                    raise TypeError(
                        f"Field '{field}' should be {expected_type.__name__}, "
                        f"got {type(value).__name__}"
                    )


class MetricsMiddleware(EventMiddleware):
    """Middleware for collecting event metrics."""
    
    def __init__(self, name: str = "metrics"):
        super().__init__(name, priority=20)
        self.metrics = {
            "events_processed": 0,
            "events_by_type": {},
            "processing_times": [],
            "errors": 0,
        }
    
    async def process_inbound(self, context: MiddlewareContext) -> MiddlewareContext:
        """Record inbound metrics."""
        event = context.event
        
        # Track event by type
        event_type = event.event_type
        if event_type not in self.metrics["events_by_type"]:
            self.metrics["events_by_type"][event_type] = 0
        self.metrics["events_by_type"][event_type] += 1
        
        # Store start time for processing duration
        context.add_metadata("metrics_start_time", time.time())
        
        return context
    
    async def process_outbound(self, context: MiddlewareContext) -> MiddlewareContext:
        """Record outbound metrics."""
        start_time = context.get_metadata("metrics_start_time")
        if start_time:
            processing_time = (time.time() - start_time) * 1000
            context.processing_time_ms = processing_time
            self.metrics["processing_times"].append(processing_time)
            
            # Keep only last 1000 processing times
            if len(self.metrics["processing_times"]) > 1000:
                self.metrics["processing_times"] = self.metrics["processing_times"][-1000:]
        
        self.metrics["events_processed"] += 1
        return context
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get metrics summary."""
        processing_times = self.metrics["processing_times"]
        avg_processing_time = sum(processing_times) / len(processing_times) if processing_times else 0
        
        return {
            "events_processed": self.metrics["events_processed"],
            "events_by_type": self.metrics["events_by_type"],
            "average_processing_time_ms": avg_processing_time,
            "errors": self.metrics["errors"],
        }


class TracingMiddleware(EventMiddleware):
    """Middleware for distributed tracing."""
    
    def __init__(self, name: str = "tracing", service_name: str = "event-system"):
        super().__init__(name, priority=15)
        self.service_name = service_name
    
    async def process_inbound(self, context: MiddlewareContext) -> MiddlewareContext:
        """Add tracing information."""
        event = context.event
        
        # Generate trace ID if not present
        if not event.metadata.trace_id:
            import uuid
            event.metadata.trace_id = str(uuid.uuid4())
        
        # Generate span ID
        if not event.metadata.span_id:
            import uuid
            event.metadata.span_id = str(uuid.uuid4())
        
        # Add tracing metadata
        context.add_metadata("trace_id", event.metadata.trace_id)
        context.add_metadata("span_id", event.metadata.span_id)
        context.add_metadata("service_name", self.service_name)
        
        return context
    
    async def process_outbound(self, context: MiddlewareContext) -> MiddlewareContext:
        """Complete tracing span."""
        # Could send span data to tracing system here
        return context


class RateLimitingMiddleware(EventMiddleware):
    """Middleware for rate limiting."""
    
    def __init__(
        self,
        name: str = "rate_limiting",
        max_events_per_second: int = 100,
        burst_size: int = 10,
    ):
        super().__init__(name, priority=80)
        self.max_events_per_second = max_events_per_second
        self.burst_size = burst_size
        self.tokens = burst_size
        self.last_refill = time.time()
    
    async def process_inbound(self, context: MiddlewareContext) -> MiddlewareContext:
        """Apply rate limiting."""
        current_time = time.time()
        
        # Refill tokens based on time elapsed
        time_elapsed = current_time - self.last_refill
        tokens_to_add = time_elapsed * self.max_events_per_second
        self.tokens = min(self.burst_size, self.tokens + tokens_to_add)
        self.last_refill = current_time
        
        # Check if we have tokens available
        if self.tokens < 1:
            raise Exception("Rate limit exceeded")
        
        # Consume a token
        self.tokens -= 1
        
        return context
    
    async def process_outbound(self, context: MiddlewareContext) -> MiddlewareContext:
        """No outbound processing for rate limiting."""
        return context


class ErrorHandlingMiddleware(EventMiddleware):
    """Middleware for error handling and recovery."""
    
    def __init__(
        self,
        name: str = "error_handling",
        capture_stack_traces: bool = True,
        notify_on_error: bool = False,
    ):
        super().__init__(name, priority=5)  # Very high priority
        self.capture_stack_traces = capture_stack_traces
        self.notify_on_error = notify_on_error
        self.error_history = []
    
    async def process_inbound(self, context: MiddlewareContext) -> MiddlewareContext:
        """Set up error handling context."""
        context.add_metadata("error_handler_active", True)
        return context
    
    async def process_outbound(self, context: MiddlewareContext) -> MiddlewareContext:
        """Handle any errors that occurred during processing."""
        # Check if there were any errors in the results
        for result in context.results:
            if isinstance(result, Exception):
                await self._handle_error(context.event, result)
        
        return context
    
    async def _handle_error(self, event: Event, error: Exception) -> None:
        """Handle a processing error."""
        error_info = {
            "event_id": event.event_id,
            "event_type": event.event_type,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        if self.capture_stack_traces:
            error_info["stack_trace"] = traceback.format_exc()
        
        self.error_history.append(error_info)
        
        # Keep only last 100 errors
        if len(self.error_history) > 100:
            self.error_history = self.error_history[-100:]
        
        logger.error(f"Event processing error: {error_info}")
        
        if self.notify_on_error:
            # Could send notification here
            pass


class TransformationMiddleware(EventMiddleware):
    """Middleware for event transformation."""
    
    def __init__(
        self,
        name: str = "transformation",
        transformations: Optional[Dict[str, Callable[[Event], Event]]] = None,
    ):
        super().__init__(name, priority=60)
        self.transformations = transformations or {}
    
    async def process_inbound(self, context: MiddlewareContext) -> MiddlewareContext:
        """Apply event transformations."""
        event = context.event
        
        if event.event_type in self.transformations:
            transformer = self.transformations[event.event_type]
            try:
                transformed_event = transformer(event)
                context.event = transformed_event
                context.add_metadata("transformed", True)
            except Exception as e:
                logger.error(f"Event transformation failed: {e}")
        
        return context
    
    async def process_outbound(self, context: MiddlewareContext) -> MiddlewareContext:
        """No outbound transformation."""
        return context


class CachingMiddleware(EventMiddleware):
    """Middleware for event caching."""
    
    def __init__(
        self,
        name: str = "caching",
        cache_size: int = 1000,
        cache_ttl_seconds: int = 3600,
    ):
        super().__init__(name, priority=30)
        self.cache = {}
        self.cache_timestamps = {}
        self.cache_size = cache_size
        self.cache_ttl_seconds = cache_ttl_seconds
    
    async def process_inbound(self, context: MiddlewareContext) -> MiddlewareContext:
        """Check cache for event."""
        event = context.event
        cache_key = f"{event.event_type}:{hash(json.dumps(event.data, sort_keys=True))}"
        
        current_time = time.time()
        
        # Check if cached result exists and is valid
        if cache_key in self.cache:
            timestamp = self.cache_timestamps.get(cache_key, 0)
            if current_time - timestamp < self.cache_ttl_seconds:
                cached_result = self.cache[cache_key]
                context.results = [cached_result]
                context.add_metadata("cache_hit", True)
                logger.debug(f"Cache hit for event {event.event_id}")
            else:
                # Remove expired entry
                del self.cache[cache_key]
                del self.cache_timestamps[cache_key]
        
        context.add_metadata("cache_key", cache_key)
        return context
    
    async def process_outbound(self, context: MiddlewareContext) -> MiddlewareContext:
        """Cache successful results."""
        if not context.get_metadata("cache_hit", False) and context.results:
            cache_key = context.get_metadata("cache_key")
            if cache_key:
                # Cache the first successful result
                result = context.results[0]
                if not isinstance(result, Exception):
                    self._add_to_cache(cache_key, result)
        
        return context
    
    def _add_to_cache(self, key: str, value: Any) -> None:
        """Add item to cache with LRU eviction."""
        # Remove oldest items if cache is full
        while len(self.cache) >= self.cache_size:
            oldest_key = min(self.cache_timestamps.keys(), key=lambda k: self.cache_timestamps[k])
            del self.cache[oldest_key]
            del self.cache_timestamps[oldest_key]
        
        self.cache[key] = value
        self.cache_timestamps[key] = time.time()


class MiddlewarePipeline:
    """Pipeline for managing and executing middleware."""
    
    def __init__(self):
        self.middleware: List[EventMiddleware] = []
        self._lock = asyncio.Lock()
    
    async def add_middleware(self, middleware: EventMiddleware) -> None:
        """Add middleware to pipeline."""
        async with self._lock:
            self.middleware.append(middleware)
            # Sort by priority (highest first)
            self.middleware.sort(key=lambda m: m.priority, reverse=True)
        
        logger.info(f"Added middleware: {middleware.name} (priority: {middleware.priority})")
    
    async def remove_middleware(self, name: str) -> bool:
        """Remove middleware from pipeline."""
        async with self._lock:
            for i, middleware in enumerate(self.middleware):
                if middleware.name == name:
                    del self.middleware[i]
                    logger.info(f"Removed middleware: {name}")
                    return True
        return False
    
    async def process_inbound(self, event: Event) -> Event:
        """Process event through inbound middleware pipeline."""
        context = MiddlewareContext(event=event)
        
        for middleware in self.middleware:
            context = await middleware.execute_inbound(context)
        
        return context.event
    
    async def process_outbound(self, event: Event, results: List[Any]) -> None:
        """Process event through outbound middleware pipeline."""
        context = MiddlewareContext(event=event, results=results)
        
        # Process middleware in reverse order for outbound
        for middleware in reversed(self.middleware):
            context = await middleware.execute_outbound(context)
    
    def get_middleware_stats(self) -> List[Dict[str, Any]]:
        """Get statistics for all middleware."""
        return [middleware.get_stats() for middleware in self.middleware]
    
    def get_status(self) -> Dict[str, Any]:
        """Get pipeline status."""
        enabled_count = sum(1 for m in self.middleware if m.enabled)
        
        return {
            "total_middleware": len(self.middleware),
            "enabled_middleware": enabled_count,
            "middleware_names": [m.name for m in self.middleware if m.enabled],
        }