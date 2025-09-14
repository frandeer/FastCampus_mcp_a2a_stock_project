"""
Main event bus implementation with multiple transport mechanisms.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable, Union, Type
from datetime import datetime, timedelta
import time
import weakref
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager

from .models import Event, EventResult, EventStatus, EventError, EventPriority
from .handlers import HandlerRegistry, EventHandler
from .middleware import MiddlewarePipeline
from .persistence import EventStore
from .serialization import EventSerializer
from .circuit_breaker import CircuitBreaker
from .metrics import EventMetrics


logger = logging.getLogger(__name__)


@dataclass
class EventBusConfig:
    """Event bus configuration."""
    max_workers: int = 10
    batch_size: int = 100
    batch_timeout_seconds: float = 1.0
    enable_persistence: bool = True
    enable_dead_letter_queue: bool = True
    enable_metrics: bool = True
    enable_circuit_breaker: bool = True
    default_timeout_seconds: int = 30
    max_retries: int = 3
    retry_delay_seconds: float = 1.0
    retry_exponential_base: float = 2.0
    cleanup_interval_minutes: int = 60
    event_ttl_hours: int = 24
    snapshot_interval_events: int = 1000
    enable_compression: bool = False
    enable_encryption: bool = False
    
    # Performance settings
    queue_max_size: int = 10000
    memory_threshold_mb: int = 512
    cpu_threshold_percent: float = 80.0
    
    # Monitoring settings
    metrics_collection_interval: int = 60
    health_check_interval: int = 30


class EventTransport(ABC):
    """Abstract base class for event transports."""
    
    @abstractmethod
    async def publish(self, event: Event) -> bool:
        """Publish an event."""
        pass
    
    @abstractmethod
    async def subscribe(self, event_type: str, handler: Callable[[Event], Any]) -> None:
        """Subscribe to events of a specific type."""
        pass
    
    @abstractmethod
    async def unsubscribe(self, event_type: str, handler: Callable[[Event], Any]) -> None:
        """Unsubscribe from events."""
        pass
    
    @abstractmethod
    async def start(self) -> None:
        """Start the transport."""
        pass
    
    @abstractmethod
    async def stop(self) -> None:
        """Stop the transport."""
        pass
    
    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """Check transport health."""
        pass


class InMemoryTransport(EventTransport):
    """In-memory event transport for development and testing."""
    
    def __init__(self):
        self.subscribers: Dict[str, List[Callable]] = {}
        self.queue = asyncio.Queue()
        self.running = False
        self._processor_task: Optional[asyncio.Task] = None
        
    async def publish(self, event: Event) -> bool:
        """Publish an event to in-memory queue."""
        try:
            await self.queue.put(event)
            return True
        except Exception as e:
            logger.error(f"Failed to publish event {event.event_id}: {e}")
            return False
    
    async def subscribe(self, event_type: str, handler: Callable[[Event], Any]) -> None:
        """Subscribe to events of a specific type."""
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        self.subscribers[event_type].append(handler)
    
    async def unsubscribe(self, event_type: str, handler: Callable[[Event], Any]) -> None:
        """Unsubscribe from events."""
        if event_type in self.subscribers:
            try:
                self.subscribers[event_type].remove(handler)
                if not self.subscribers[event_type]:
                    del self.subscribers[event_type]
            except ValueError:
                pass
    
    async def start(self) -> None:
        """Start the transport."""
        self.running = True
        self._processor_task = asyncio.create_task(self._process_events())
        logger.info("In-memory transport started")
    
    async def stop(self) -> None:
        """Stop the transport."""
        self.running = False
        if self._processor_task:
            self._processor_task.cancel()
            try:
                await self._processor_task
            except asyncio.CancelledError:
                pass
        logger.info("In-memory transport stopped")
    
    async def health_check(self) -> Dict[str, Any]:
        """Check transport health."""
        return {
            "status": "healthy" if self.running else "stopped",
            "queue_size": self.queue.qsize(),
            "subscriber_count": sum(len(handlers) for handlers in self.subscribers.values()),
        }
    
    async def _process_events(self) -> None:
        """Process events from the queue."""
        while self.running:
            try:
                # Wait for event with timeout
                event = await asyncio.wait_for(self.queue.get(), timeout=1.0)
                
                # Notify subscribers
                handlers = self.subscribers.get(event.event_type, [])
                if handlers:
                    # Process handlers concurrently
                    tasks = [self._call_handler(handler, event) for handler in handlers]
                    await asyncio.gather(*tasks, return_exceptions=True)
                    
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Error processing event: {e}")
    
    async def _call_handler(self, handler: Callable, event: Event) -> None:
        """Call event handler safely."""
        try:
            if asyncio.iscoroutinefunction(handler):
                await handler(event)
            else:
                handler(event)
        except Exception as e:
            logger.error(f"Handler {handler} failed for event {event.event_id}: {e}")


class EventBus:
    """Main event bus with comprehensive event processing capabilities."""
    
    def __init__(
        self,
        config: Optional[EventBusConfig] = None,
        transport: Optional[EventTransport] = None,
        event_store: Optional[EventStore] = None,
        serializer: Optional[EventSerializer] = None,
    ):
        self.config = config or EventBusConfig()
        self.transport = transport or InMemoryTransport()
        self.event_store = event_store
        self.serializer = serializer or EventSerializer()
        
        # Core components
        self.handler_registry = HandlerRegistry()
        self.middleware_pipeline = MiddlewarePipeline()
        self.circuit_breaker = CircuitBreaker() if config and config.enable_circuit_breaker else None
        self.metrics = EventMetrics() if config and config.enable_metrics else None
        
        # Internal state
        self.running = False
        self.executor = ThreadPoolExecutor(max_workers=self.config.max_workers)
        self._background_tasks: List[asyncio.Task] = []
        self._event_cache: Dict[str, Event] = {}
        self._processing_events: Dict[str, datetime] = {}
        
        # Performance monitoring
        self._performance_stats = {
            "events_processed": 0,
            "events_failed": 0,
            "average_processing_time": 0.0,
            "last_reset": datetime.utcnow(),
        }
        
        logger.info("EventBus initialized")
    
    async def start(self) -> None:
        """Start the event bus."""
        if self.running:
            return
            
        logger.info("Starting EventBus...")
        
        # Start transport
        await self.transport.start()
        
        # Start background tasks
        self._background_tasks = [
            asyncio.create_task(self._cleanup_task()),
            asyncio.create_task(self._health_monitor_task()),
        ]
        
        if self.metrics:
            self._background_tasks.append(
                asyncio.create_task(self._metrics_collection_task())
            )
        
        self.running = True
        logger.info("EventBus started successfully")
    
    async def stop(self) -> None:
        """Stop the event bus."""
        if not self.running:
            return
            
        logger.info("Stopping EventBus...")
        
        self.running = False
        
        # Stop background tasks
        for task in self._background_tasks:
            task.cancel()
        
        await asyncio.gather(*self._background_tasks, return_exceptions=True)
        self._background_tasks.clear()
        
        # Stop transport
        await self.transport.stop()
        
        # Shutdown executor
        self.executor.shutdown(wait=True)
        
        logger.info("EventBus stopped")
    
    async def publish(
        self,
        event: Union[Event, str],
        data: Optional[Dict[str, Any]] = None,
        priority: EventPriority = EventPriority.NORMAL,
        correlation_id: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> EventResult:
        """Publish an event."""
        start_time = time.time()
        
        # Create event if string provided
        if isinstance(event, str):
            from .models import EventMetadata
            metadata = EventMetadata(
                correlation_id=correlation_id,
                priority=priority,
                timeout_seconds=timeout or self.config.default_timeout_seconds,
            )
            event = Event(event_type=event, data=data or {}, metadata=metadata)
        
        try:
            # Apply middleware
            event = await self.middleware_pipeline.process_inbound(event)
            
            # Persist event if enabled
            if self.event_store and self.config.enable_persistence:
                await self.event_store.store_event(event)
            
            # Check circuit breaker
            if self.circuit_breaker and not self.circuit_breaker.can_execute():
                raise Exception("Circuit breaker is open")
            
            # Cache event for processing tracking
            self._event_cache[event.event_id] = event
            self._processing_events[event.event_id] = datetime.utcnow()
            
            # Publish to transport
            success = await self.transport.publish(event)
            
            processing_time = (time.time() - start_time) * 1000
            
            if success:
                # Record success metrics
                if self.metrics:
                    self.metrics.record_event_published(event.event_type, processing_time)
                
                if self.circuit_breaker:
                    self.circuit_breaker.record_success()
                
                self._performance_stats["events_processed"] += 1
                
                return EventResult(
                    event_id=event.event_id,
                    status=EventStatus.COMPLETED,
                    processing_time_ms=processing_time,
                )
            else:
                raise Exception("Failed to publish to transport")
                
        except Exception as e:
            processing_time = (time.time() - start_time) * 1000
            error = EventError(
                error_type=type(e).__name__,
                message=str(e),
                context={"event_type": event.event_type},
            )
            
            # Record failure metrics
            if self.metrics:
                self.metrics.record_event_failed(event.event_type, str(e))
            
            if self.circuit_breaker:
                self.circuit_breaker.record_failure()
            
            self._performance_stats["events_failed"] += 1
            
            logger.error(f"Failed to publish event {event.event_id}: {e}")
            
            return EventResult(
                event_id=event.event_id,
                status=EventStatus.FAILED,
                error=error,
                processing_time_ms=processing_time,
            )
        
        finally:
            # Cleanup
            self._event_cache.pop(event.event_id, None)
            self._processing_events.pop(event.event_id, None)
    
    async def subscribe(
        self,
        event_type: str,
        handler: Union[EventHandler, Callable],
        priority: int = 0,
        condition: Optional[Callable[[Event], bool]] = None,
    ) -> None:
        """Subscribe to events."""
        # Register handler
        if not isinstance(handler, EventHandler):
            handler = EventHandler(
                name=getattr(handler, "__name__", str(handler)),
                handler_func=handler,
                event_types=[event_type],
                priority=priority,
                condition=condition,
            )
        
        self.handler_registry.register(handler)
        
        # Subscribe to transport
        await self.transport.subscribe(event_type, self._handle_event)
        
        logger.info(f"Subscribed to {event_type} with handler {handler.name}")
    
    async def unsubscribe(self, event_type: str, handler: Union[EventHandler, Callable]) -> None:
        """Unsubscribe from events."""
        handler_name = handler.name if isinstance(handler, EventHandler) else str(handler)
        
        # Unregister handler
        self.handler_registry.unregister(event_type, handler_name)
        
        # Unsubscribe from transport if no more handlers
        if not self.handler_registry.get_handlers(event_type):
            await self.transport.unsubscribe(event_type, self._handle_event)
        
        logger.info(f"Unsubscribed from {event_type} handler {handler_name}")
    
    async def _handle_event(self, event: Event) -> None:
        """Handle incoming event."""
        start_time = time.time()
        
        try:
            # Apply inbound middleware
            processed_event = await self.middleware_pipeline.process_inbound(event)
            
            # Get handlers for event type
            handlers = self.handler_registry.get_handlers(processed_event.event_type)
            
            if not handlers:
                logger.warning(f"No handlers for event type: {processed_event.event_type}")
                return
            
            # Process handlers
            results = []
            for handler in handlers:
                try:
                    # Check condition if provided
                    if handler.condition and not handler.condition(processed_event):
                        continue
                    
                    # Execute handler
                    result = await self._execute_handler(handler, processed_event)
                    results.append(result)
                    
                except Exception as e:
                    logger.error(f"Handler {handler.name} failed: {e}")
                    if self.metrics:
                        self.metrics.record_handler_failed(handler.name, str(e))
            
            # Apply outbound middleware
            await self.middleware_pipeline.process_outbound(processed_event, results)
            
            processing_time = (time.time() - start_time) * 1000
            
            # Record metrics
            if self.metrics:
                self.metrics.record_event_processed(
                    processed_event.event_type,
                    processing_time,
                    len(handlers),
                )
                
        except Exception as e:
            logger.error(f"Failed to handle event {event.event_id}: {e}")
            if self.metrics:
                self.metrics.record_event_failed(event.event_type, str(e))
    
    async def _execute_handler(self, handler: EventHandler, event: Event) -> Any:
        """Execute event handler with timeout and circuit breaker."""
        timeout = event.metadata.timeout_seconds or self.config.default_timeout_seconds
        
        try:
            if asyncio.iscoroutinefunction(handler.handler_func):
                result = await asyncio.wait_for(
                    handler.handler_func(event),
                    timeout=timeout
                )
            else:
                # Run sync handler in executor
                result = await asyncio.wait_for(
                    asyncio.get_event_loop().run_in_executor(
                        self.executor,
                        handler.handler_func,
                        event
                    ),
                    timeout=timeout
                )
            
            if self.metrics:
                self.metrics.record_handler_success(handler.name)
            
            return result
            
        except asyncio.TimeoutError:
            error_msg = f"Handler {handler.name} timeout after {timeout}s"
            logger.error(error_msg)
            raise TimeoutError(error_msg)
        except Exception as e:
            logger.error(f"Handler {handler.name} execution failed: {e}")
            raise
    
    async def _cleanup_task(self) -> None:
        """Background cleanup task."""
        while self.running:
            try:
                await asyncio.sleep(self.config.cleanup_interval_minutes * 60)
                await self._cleanup_expired_events()
            except Exception as e:
                logger.error(f"Cleanup task error: {e}")
    
    async def _cleanup_expired_events(self) -> None:
        """Clean up expired events."""
        cutoff_time = datetime.utcnow() - timedelta(hours=self.config.event_ttl_hours)
        
        # Clean processing events
        expired_events = [
            event_id for event_id, timestamp in self._processing_events.items()
            if timestamp < cutoff_time
        ]
        
        for event_id in expired_events:
            self._processing_events.pop(event_id, None)
            self._event_cache.pop(event_id, None)
        
        if expired_events:
            logger.info(f"Cleaned up {len(expired_events)} expired events")
    
    async def _health_monitor_task(self) -> None:
        """Background health monitoring task."""
        while self.running:
            try:
                await asyncio.sleep(self.config.health_check_interval)
                await self._check_health()
            except Exception as e:
                logger.error(f"Health monitor error: {e}")
    
    async def _check_health(self) -> None:
        """Check system health."""
        # Check transport health
        transport_health = await self.transport.health_check()
        
        # Check memory usage
        import psutil
        memory_percent = psutil.virtual_memory().percent
        cpu_percent = psutil.cpu_percent()
        
        if memory_percent > 90:
            logger.warning(f"High memory usage: {memory_percent}%")
        
        if cpu_percent > self.config.cpu_threshold_percent:
            logger.warning(f"High CPU usage: {cpu_percent}%")
    
    async def _metrics_collection_task(self) -> None:
        """Background metrics collection task."""
        while self.running:
            try:
                await asyncio.sleep(self.config.metrics_collection_interval)
                if self.metrics:
                    await self.metrics.collect_system_metrics()
            except Exception as e:
                logger.error(f"Metrics collection error: {e}")
    
    async def get_health_status(self) -> Dict[str, Any]:
        """Get comprehensive health status."""
        transport_health = await self.transport.health_check()
        
        return {
            "status": "healthy" if self.running else "stopped",
            "transport": transport_health,
            "handlers": self.handler_registry.get_status(),
            "performance": self._performance_stats,
            "processing_events": len(self._processing_events),
            "circuit_breaker": self.circuit_breaker.get_status() if self.circuit_breaker else None,
            "metrics": self.metrics.get_summary() if self.metrics else None,
        }
    
    async def replay_events(
        self,
        from_timestamp: Optional[datetime] = None,
        to_timestamp: Optional[datetime] = None,
        event_types: Optional[List[str]] = None,
        correlation_id: Optional[str] = None,
    ) -> int:
        """Replay events from event store."""
        if not self.event_store:
            raise ValueError("Event store not configured")
        
        events = await self.event_store.get_events(
            from_timestamp=from_timestamp,
            to_timestamp=to_timestamp,
            event_types=event_types,
            correlation_id=correlation_id,
        )
        
        replayed_count = 0
        for event in events:
            try:
                await self.publish(event)
                replayed_count += 1
            except Exception as e:
                logger.error(f"Failed to replay event {event.event_id}: {e}")
        
        logger.info(f"Replayed {replayed_count} events")
        return replayed_count
    
    @asynccontextmanager
    async def transaction(self):
        """Transaction context for event publishing."""
        events = []
        
        class TransactionContext:
            def __init__(self, event_list):
                self.events = event_list
                
            async def publish(self, event: Union[Event, str], data: Optional[Dict[str, Any]] = None):
                if isinstance(event, str):
                    from .models import EventMetadata
                    event = Event(event_type=event, data=data or {}, metadata=EventMetadata())
                self.events.append(event)
        
        context = TransactionContext(events)
        
        try:
            yield context
            
            # Publish all events if no exception
            results = []
            for event in events:
                result = await self.publish(event)
                results.append(result)
                
            # Check if all succeeded
            if any(result.status == EventStatus.FAILED for result in results):
                raise Exception("Transaction failed - some events could not be published")
                
        except Exception:
            # Transaction failed - could implement compensation here
            logger.error(f"Transaction failed - {len(events)} events not published")
            raise