"""
In-memory event transport for development and testing.
"""

import asyncio
import logging
from typing import Any, Dict, List, Callable, Optional
from datetime import datetime
from collections import defaultdict, deque
from dataclasses import dataclass
import weakref

from ..models import Event


logger = logging.getLogger(__name__)


@dataclass
class MemoryTransportConfig:
    """Configuration for in-memory transport."""
    max_queue_size: int = 10000
    max_subscribers_per_topic: int = 100
    enable_persistence: bool = False
    max_persisted_events: int = 50000
    processing_delay_ms: int = 0  # For testing
    enable_metrics: bool = True


class InMemoryTransport:
    """In-memory event transport with advanced features."""
    
    def __init__(self, config: Optional[MemoryTransportConfig] = None):
        self.config = config or MemoryTransportConfig()
        
        # Core components
        self.subscribers: Dict[str, List[Callable]] = defaultdict(list)
        self.event_queue = asyncio.Queue(maxsize=self.config.max_queue_size)
        self.running = False
        
        # Processing
        self._processor_task: Optional[asyncio.Task] = None
        self._worker_tasks: List[asyncio.Task] = []
        self._num_workers = 3
        
        # Persistence
        self._persisted_events: deque = deque(maxlen=self.config.max_persisted_events)
        
        # Metrics
        self._metrics = {
            "events_published": 0,
            "events_processed": 0,
            "events_failed": 0,
            "subscribers_count": 0,
            "queue_size": 0,
            "last_event_time": None,
        }
        
        # Weak references for automatic cleanup
        self._weak_refs: List[weakref.ReferenceType] = []
        
        logger.info("InMemoryTransport initialized")
    
    async def start(self) -> None:
        """Start the transport."""
        if self.running:
            return
        
        self.running = True
        
        # Start event processor
        self._processor_task = asyncio.create_task(self._process_events())
        
        # Start worker tasks for parallel processing
        self._worker_tasks = [
            asyncio.create_task(self._worker(i)) 
            for i in range(self._num_workers)
        ]
        
        logger.info("InMemoryTransport started")
    
    async def stop(self) -> None:
        """Stop the transport."""
        if not self.running:
            return
        
        self.running = False
        
        # Cancel processor task
        if self._processor_task:
            self._processor_task.cancel()
            try:
                await self._processor_task
            except asyncio.CancelledError:
                pass
        
        # Cancel worker tasks
        for task in self._worker_tasks:
            task.cancel()
        
        await asyncio.gather(*self._worker_tasks, return_exceptions=True)
        self._worker_tasks.clear()
        
        logger.info("InMemoryTransport stopped")
    
    async def publish(self, event: Event) -> bool:
        """Publish an event."""
        if not self.running:
            return False
        
        try:
            # Check queue capacity
            if self.event_queue.full():
                logger.warning("Event queue is full, dropping event")
                return False
            
            # Add to queue
            await self.event_queue.put(event)
            
            # Update metrics
            self._metrics["events_published"] += 1
            self._metrics["queue_size"] = self.event_queue.qsize()
            self._metrics["last_event_time"] = datetime.utcnow()
            
            # Persist if enabled
            if self.config.enable_persistence:
                self._persisted_events.append(event)
            
            logger.debug(f"Published event {event.event_id} to queue")
            return True
            
        except Exception as e:
            logger.error(f"Failed to publish event {event.event_id}: {e}")
            return False
    
    async def subscribe(self, event_type: str, handler: Callable[[Event], Any]) -> None:
        """Subscribe to events of a specific type."""
        if len(self.subscribers[event_type]) >= self.config.max_subscribers_per_topic:
            raise ValueError(f"Too many subscribers for topic: {event_type}")
        
        # Add handler
        self.subscribers[event_type].append(handler)
        
        # Create weak reference for cleanup
        weak_ref = weakref.ref(handler, lambda ref: self._cleanup_handler(event_type, ref))
        self._weak_refs.append(weak_ref)
        
        # Update metrics
        self._metrics["subscribers_count"] = sum(len(handlers) for handlers in self.subscribers.values())
        
        logger.info(f"Subscribed to {event_type} (total subscribers: {len(self.subscribers[event_type])})")
    
    async def unsubscribe(self, event_type: str, handler: Callable[[Event], Any]) -> None:
        """Unsubscribe from events."""
        if event_type in self.subscribers:
            try:
                self.subscribers[event_type].remove(handler)
                if not self.subscribers[event_type]:
                    del self.subscribers[event_type]
                
                # Update metrics
                self._metrics["subscribers_count"] = sum(len(handlers) for handlers in self.subscribers.values())
                
                logger.info(f"Unsubscribed from {event_type}")
                
            except ValueError:
                logger.warning(f"Handler not found for {event_type}")
    
    async def health_check(self) -> Dict[str, Any]:
        """Check transport health."""
        return {
            "status": "healthy" if self.running else "stopped",
            "queue_size": self.event_queue.qsize(),
            "max_queue_size": self.config.max_queue_size,
            "subscriber_topics": len(self.subscribers),
            "total_subscribers": sum(len(handlers) for handlers in self.subscribers.values()),
            "metrics": self._metrics.copy(),
        }
    
    async def _process_events(self) -> None:
        """Main event processing loop."""
        logger.info("Event processor started")
        
        while self.running:
            try:
                # Wait for event with timeout
                event = await asyncio.wait_for(self.event_queue.get(), timeout=1.0)
                
                # Add processing delay if configured (for testing)
                if self.config.processing_delay_ms > 0:
                    await asyncio.sleep(self.config.processing_delay_ms / 1000)
                
                # Process event
                await self._handle_event(event)
                
                # Mark task as done
                self.event_queue.task_done()
                
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Error in event processor: {e}")
    
    async def _worker(self, worker_id: int) -> None:
        """Worker task for parallel event processing."""
        logger.info(f"Worker {worker_id} started")
        
        while self.running:
            try:
                # This is a placeholder for worker-based processing
                # In practice, you might have workers pull from separate queues
                await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Error in worker {worker_id}: {e}")
        
        logger.info(f"Worker {worker_id} stopped")
    
    async def _handle_event(self, event: Event) -> None:
        """Handle incoming event."""
        try:
            # Get handlers for exact match
            handlers = self.subscribers.get(event.event_type, [])
            
            # Add wildcard handlers
            wildcard_handlers = self.subscribers.get("*", [])
            handlers.extend(wildcard_handlers)
            
            if not handlers:
                logger.debug(f"No handlers for event type: {event.event_type}")
                return
            
            # Process handlers concurrently
            tasks = []
            for handler in handlers:
                task = asyncio.create_task(self._call_handler(handler, event))
                tasks.append(task)
            
            # Wait for all handlers to complete
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Count successes and failures
            successes = sum(1 for result in results if not isinstance(result, Exception))
            failures = len(results) - successes
            
            # Update metrics
            self._metrics["events_processed"] += 1
            self._metrics["events_failed"] += failures
            
            if failures > 0:
                logger.warning(f"Event {event.event_id} had {failures} handler failures")
            
        except Exception as e:
            logger.error(f"Failed to handle event {event.event_id}: {e}")
            self._metrics["events_failed"] += 1
    
    async def _call_handler(self, handler: Callable, event: Event) -> Any:
        """Call event handler safely."""
        try:
            if asyncio.iscoroutinefunction(handler):
                return await handler(event)
            else:
                # Run sync handler in thread pool
                loop = asyncio.get_event_loop()
                return await loop.run_in_executor(None, handler, event)
                
        except Exception as e:
            logger.error(f"Handler {handler} failed for event {event.event_id}: {e}")
            raise
    
    def _cleanup_handler(self, event_type: str, handler_ref: weakref.ReferenceType) -> None:
        """Clean up handler reference."""
        # This would be called when a handler is garbage collected
        logger.debug(f"Cleaning up handler reference for {event_type}")
    
    async def get_events_by_type(self, event_type: str, limit: int = 100) -> List[Event]:
        """Get persisted events by type (if persistence enabled)."""
        if not self.config.enable_persistence:
            return []
        
        matching_events = [
            event for event in self._persisted_events 
            if event.event_type == event_type
        ]
        
        return list(matching_events)[-limit:]
    
    async def get_all_events(self, limit: int = 100) -> List[Event]:
        """Get all persisted events (if persistence enabled)."""
        if not self.config.enable_persistence:
            return []
        
        return list(self._persisted_events)[-limit:]
    
    async def clear_events(self) -> None:
        """Clear persisted events."""
        if self.config.enable_persistence:
            self._persisted_events.clear()
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get transport metrics."""
        metrics = self._metrics.copy()
        metrics["queue_size"] = self.event_queue.qsize()
        return metrics
    
    async def wait_for_processing(self, timeout: Optional[float] = None) -> bool:
        """Wait for all events in queue to be processed."""
        try:
            await asyncio.wait_for(self.event_queue.join(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            return False
    
    def get_subscriber_info(self) -> Dict[str, Any]:
        """Get detailed subscriber information."""
        subscriber_info = {}
        
        for event_type, handlers in self.subscribers.items():
            subscriber_info[event_type] = {
                "count": len(handlers),
                "handlers": [
                    {
                        "name": getattr(handler, "__name__", str(handler)),
                        "module": getattr(handler, "__module__", "unknown"),
                    }
                    for handler in handlers
                ]
            }
        
        return subscriber_info