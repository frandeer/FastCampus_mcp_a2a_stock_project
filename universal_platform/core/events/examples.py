"""
Examples demonstrating the event-driven architecture system usage.
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict

from .event_bus import EventBus, EventBusConfig
from .handlers import event_handler, HandlerPriority
from .middleware import LoggingMiddleware, ValidationMiddleware, MetricsMiddleware
from .models import Event, EventMetadata, EventPriority
from .persistence import SQLiteEventStore, EventStoreConfig, EventSourcing
from .serialization import JSONEventSerializer, SerializationConfig
from .transports.memory import InMemoryTransport, MemoryTransportConfig
from .saga import OrderProcessingSaga, UserRegistrationSaga, SagaOrchestrator, SagaManager
from .circuit_breaker import CircuitBreaker, CircuitBreakerConfig
from .metrics import EventMetrics


# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class UserService:
    """Example user service with event-driven patterns."""
    
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.users = {}
        
        # Subscribe to events
        asyncio.create_task(self._subscribe_to_events())
    
    async def _subscribe_to_events(self):
        """Subscribe to relevant events."""
        await self.event_bus.subscribe("user.create_requested", self.handle_create_user)
        await self.event_bus.subscribe("user.update_requested", self.handle_update_user)
        await self.event_bus.subscribe("user.delete_requested", self.handle_delete_user)
    
    @event_handler(
        "user.create_requested",
        priority=HandlerPriority.HIGH.value,
        description="Handle user creation requests"
    )
    async def handle_create_user(self, event: Event) -> None:
        """Handle user creation."""
        user_data = event.data
        user_id = user_data.get("user_id")
        
        # Simulate user creation
        self.users[user_id] = {
            "id": user_id,
            "email": user_data.get("email"),
            "name": user_data.get("name"),
            "created_at": datetime.utcnow().isoformat(),
        }
        
        # Publish user created event
        await self.event_bus.publish(
            "user.created",
            data={
                "user_id": user_id,
                "email": user_data.get("email"),
                "name": user_data.get("name"),
            },
            correlation_id=event.correlation_id,
        )
        
        logger.info(f"User created: {user_id}")
    
    async def handle_update_user(self, event: Event) -> None:
        """Handle user updates."""
        user_data = event.data
        user_id = user_data.get("user_id")
        
        if user_id in self.users:
            self.users[user_id].update(user_data)
            
            await self.event_bus.publish(
                "user.updated",
                data={"user_id": user_id, "changes": user_data},
                correlation_id=event.correlation_id,
            )
            
            logger.info(f"User updated: {user_id}")
    
    async def handle_delete_user(self, event: Event) -> None:
        """Handle user deletion."""
        user_id = event.data.get("user_id")
        
        if user_id in self.users:
            del self.users[user_id]
            
            await self.event_bus.publish(
                "user.deleted",
                data={"user_id": user_id},
                correlation_id=event.correlation_id,
            )
            
            logger.info(f"User deleted: {user_id}")


class NotificationService:
    """Example notification service."""
    
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        
        # Subscribe to events
        asyncio.create_task(self._subscribe_to_events())
    
    async def _subscribe_to_events(self):
        """Subscribe to notification events."""
        await self.event_bus.subscribe("user.created", self.send_welcome_email)
        await self.event_bus.subscribe("order.completed", self.send_order_confirmation)
    
    @event_handler("user.created", description="Send welcome email to new users")
    async def send_welcome_email(self, event: Event) -> None:
        """Send welcome email."""
        user_data = event.data
        email = user_data.get("email")
        name = user_data.get("name")
        
        # Simulate email sending
        await asyncio.sleep(0.1)
        
        logger.info(f"Welcome email sent to {email} ({name})")
        
        # Publish email sent event
        await self.event_bus.publish(
            "notification.email_sent",
            data={
                "recipient": email,
                "type": "welcome",
                "status": "delivered",
            },
            correlation_id=event.correlation_id,
        )
    
    async def send_order_confirmation(self, event: Event) -> None:
        """Send order confirmation."""
        order_data = event.data
        order_id = order_data.get("order_id")
        customer_email = order_data.get("customer_email")
        
        logger.info(f"Order confirmation sent for order {order_id} to {customer_email}")


class OrderService:
    """Example order service with saga integration."""
    
    def __init__(self, event_bus: EventBus, saga_manager: SagaManager):
        self.event_bus = event_bus
        self.saga_manager = saga_manager
        
        # Subscribe to events
        asyncio.create_task(self._subscribe_to_events())
    
    async def _subscribe_to_events(self):
        """Subscribe to order events."""
        await self.event_bus.subscribe("order.create_requested", self.handle_create_order)
    
    async def handle_create_order(self, event: Event) -> None:
        """Handle order creation using saga."""
        order_data = event.data
        
        # Start order processing saga
        saga_execution = await self.saga_manager.start_saga(
            "OrderProcessingSaga",
            context={
                "order_id": order_data.get("order_id"),
                "items": order_data.get("items", []),
                "amount": order_data.get("amount", 0),
                "customer_email": order_data.get("customer_email"),
            }
        )
        
        if saga_execution:
            logger.info(f"Started order processing saga: {saga_execution.saga_id}")


class AuditService:
    """Example audit service for event tracking."""
    
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.audit_log = []
        
        # Subscribe to all events
        asyncio.create_task(self._subscribe_to_events())
    
    async def _subscribe_to_events(self):
        """Subscribe to all events for auditing."""
        await self.event_bus.subscribe("*", self.audit_event)
    
    async def audit_event(self, event: Event) -> None:
        """Audit all events."""
        audit_entry = {
            "event_id": event.event_id,
            "event_type": event.event_type,
            "timestamp": event.metadata.timestamp.isoformat(),
            "source": event.metadata.source,
            "correlation_id": event.metadata.correlation_id,
            "data_keys": list(event.data.keys()),
        }
        
        self.audit_log.append(audit_entry)
        
        # Keep only last 1000 entries
        if len(self.audit_log) > 1000:
            self.audit_log = self.audit_log[-1000:]
        
        logger.debug(f"Audited event: {event.event_type}")


async def basic_example():
    """Basic event system usage example."""
    print("=== Basic Event System Example ===")
    
    # Create event bus with in-memory transport
    config = EventBusConfig(
        enable_metrics=True,
        enable_persistence=False,
    )
    
    event_bus = EventBus(
        config=config,
        transport=InMemoryTransport(MemoryTransportConfig()),
    )
    
    # Add middleware
    await event_bus.middleware_pipeline.add_middleware(LoggingMiddleware())
    await event_bus.middleware_pipeline.add_middleware(MetricsMiddleware())
    
    # Start event bus
    await event_bus.start()
    
    try:
        # Create services
        user_service = UserService(event_bus)
        notification_service = NotificationService(event_bus)
        
        # Wait for subscriptions
        await asyncio.sleep(0.1)
        
        # Publish some events
        await event_bus.publish(
            "user.create_requested",
            data={
                "user_id": "user123",
                "email": "alice@example.com",
                "name": "Alice Johnson",
            },
            priority=EventPriority.HIGH,
        )
        
        # Wait for event processing
        await asyncio.sleep(0.2)
        
        # Publish more events
        await event_bus.publish(
            "user.update_requested",
            data={
                "user_id": "user123",
                "name": "Alice Smith",
            }
        )
        
        await event_bus.publish(
            "user.delete_requested",
            data={"user_id": "user123"}
        )
        
        # Wait for processing
        await asyncio.sleep(0.2)
        
        # Show health status
        health = await event_bus.get_health_status()
        print(f"Event bus health: {health['status']}")
        print(f"Events processed: {health['performance']['events_processed']}")
        
    finally:
        await event_bus.stop()


async def persistence_example():
    """Event sourcing and persistence example."""
    print("\n=== Event Persistence Example ===")
    
    # Create event store
    event_store_config = EventStoreConfig(
        connection_string="sqlite:///events_example.db",
        compression_enabled=True,
    )
    event_store = SQLiteEventStore(event_store_config)
    await event_store.initialize()
    
    # Create event bus with persistence
    config = EventBusConfig(
        enable_persistence=True,
        enable_metrics=True,
    )
    
    event_bus = EventBus(
        config=config,
        event_store=event_store,
        serializer=JSONEventSerializer(SerializationConfig()),
    )
    
    await event_bus.start()
    
    try:
        # Create event sourcing
        event_sourcing = EventSourcing(event_store)
        
        # Publish events for an aggregate
        events = [
            Event(
                event_type="account.created",
                data={"aggregate_id": "account123", "owner": "Alice", "balance": 1000},
                metadata=EventMetadata(correlation_id="tx123"),
            ),
            Event(
                event_type="account.deposit",
                data={"aggregate_id": "account123", "amount": 500},
                metadata=EventMetadata(correlation_id="tx124", version=2),
            ),
            Event(
                event_type="account.withdrawal",
                data={"aggregate_id": "account123", "amount": 200},
                metadata=EventMetadata(correlation_id="tx125", version=3),
            ),
        ]
        
        # Save events
        await event_sourcing.save_events("account123", events)
        
        # Query events
        stored_events = await event_store.get_events(
            event_types=["account.created", "account.deposit", "account.withdrawal"]
        )
        
        print(f"Stored {len(stored_events)} events")
        for event in stored_events:
            print(f"- {event.event_type}: {event.data}")
        
        # Event store stats
        stats = await event_store.get_stats()
        print(f"Event store stats: {stats}")
        
    finally:
        await event_bus.stop()


async def saga_example():
    """Saga pattern example."""
    print("\n=== Saga Pattern Example ===")
    
    # Create event bus
    event_bus = EventBus()
    await event_bus.start()
    
    try:
        # Create saga orchestrator
        orchestrator = SagaOrchestrator()
        await orchestrator.start()
        
        # Create saga manager
        saga_manager = SagaManager(orchestrator)
        saga_manager.register_saga(OrderProcessingSaga)
        saga_manager.register_saga(UserRegistrationSaga)
        
        # Create order service
        order_service = OrderService(event_bus, saga_manager)
        
        # Wait for subscriptions
        await asyncio.sleep(0.1)
        
        # Start order processing saga
        print("Starting order processing saga...")
        await event_bus.publish(
            "order.create_requested",
            data={
                "order_id": "order123",
                "items": [
                    {"product": "laptop", "quantity": 1, "price": 1200},
                    {"product": "mouse", "quantity": 2, "price": 25},
                ],
                "amount": 1250,
                "customer_email": "customer@example.com",
            }
        )
        
        # Wait for saga to complete
        await asyncio.sleep(2)
        
        # Check saga status
        running_sagas = orchestrator.get_running_sagas()
        print(f"Running sagas: {len(running_sagas)}")
        
        # Start user registration saga
        print("Starting user registration saga...")
        user_saga = await saga_manager.start_saga(
            "UserRegistrationSaga",
            context={
                "email": "newuser@example.com",
                "name": "New User",
            }
        )
        
        if user_saga:
            print(f"User registration saga started: {user_saga.saga_id}")
        
        # Wait for completion
        await asyncio.sleep(1)
        
        await orchestrator.stop()
        
    finally:
        await event_bus.stop()


async def circuit_breaker_example():
    """Circuit breaker example."""
    print("\n=== Circuit Breaker Example ===")
    
    # Create circuit breaker
    config = CircuitBreakerConfig(
        failure_threshold=3,
        recovery_timeout=5.0,
        timeout=2.0,
    )
    circuit_breaker = CircuitBreaker(config)
    
    # Simulate failing service
    call_count = 0
    
    async def unreliable_service():
        nonlocal call_count
        call_count += 1
        
        # Fail first 5 calls
        if call_count <= 5:
            raise Exception(f"Service failure #{call_count}")
        
        return f"Success after {call_count} calls"
    
    # Test circuit breaker
    for i in range(10):
        try:
            result = await circuit_breaker.call(unreliable_service)
            print(f"Call {i + 1}: {result}")
        except Exception as e:
            print(f"Call {i + 1}: {e}")
        
        # Show circuit breaker status
        status = circuit_breaker.get_status()
        print(f"  Circuit breaker state: {status['state']}")
        
        await asyncio.sleep(0.1)


async def metrics_example():
    """Metrics collection example."""
    print("\n=== Metrics Example ===")
    
    # Create metrics collector
    metrics = EventMetrics()
    await metrics.start()
    
    try:
        # Simulate some events
        for i in range(100):
            event_type = f"test.event_{i % 5}"
            
            # Record event publication
            metrics.record_event_published(event_type, processing_time_ms=float(i % 10))
            
            # Record event processing
            metrics.record_event_processed(event_type, processing_time_ms=float(i % 20), handler_count=2)
            
            # Occasionally record failures
            if i % 10 == 0:
                metrics.record_event_failed(event_type, "Simulated error")
            
            # Record handler metrics
            metrics.record_handler_success(f"handler_{i % 3}", execution_time_ms=float(i % 15))
        
        # Collect system metrics
        await metrics.collect_system_metrics()
        
        # Show metrics summary
        summary = metrics.get_summary()
        print(f"Events published: {summary['overview']['events_published_total']}")
        print(f"Events processed: {summary['overview']['events_processed_total']}")
        print(f"Events failed: {summary['overview']['events_failed_total']}")
        
        print("\nTop event types:")
        for event_info in summary['top_event_types'][:3]:
            print(f"- {event_info['event_type']}: {event_info['published']} published")
        
        print("\nTop handlers:")
        for handler_info in summary['top_handlers'][:3]:
            print(f"- {handler_info['handler']}: {handler_info['executions']} executions")
        
        # Export Prometheus metrics
        prometheus_metrics = metrics.export_prometheus()
        print(f"\nPrometheus metrics (first 500 chars):\n{prometheus_metrics[:500]}...")
        
    finally:
        await metrics.stop()


async def comprehensive_example():
    """Comprehensive example with all features."""
    print("\n=== Comprehensive Example ===")
    
    # Create event store
    event_store_config = EventStoreConfig(
        connection_string="sqlite:///comprehensive_example.db",
    )
    event_store = SQLiteEventStore(event_store_config)
    await event_store.initialize()
    
    # Create event bus with all features
    config = EventBusConfig(
        enable_persistence=True,
        enable_metrics=True,
        enable_circuit_breaker=True,
        enable_dead_letter_queue=True,
    )
    
    event_bus = EventBus(
        config=config,
        event_store=event_store,
    )
    
    # Add middleware
    await event_bus.middleware_pipeline.add_middleware(LoggingMiddleware(include_data=True))
    await event_bus.middleware_pipeline.add_middleware(ValidationMiddleware())
    await event_bus.middleware_pipeline.add_middleware(MetricsMiddleware())
    
    await event_bus.start()
    
    try:
        # Create all services
        user_service = UserService(event_bus)
        notification_service = NotificationService(event_bus)
        audit_service = AuditService(event_bus)
        
        # Create saga system
        orchestrator = SagaOrchestrator(event_store)
        await orchestrator.start()
        
        saga_manager = SagaManager(orchestrator)
        saga_manager.register_saga(OrderProcessingSaga)
        saga_manager.register_saga(UserRegistrationSaga)
        
        order_service = OrderService(event_bus, saga_manager)
        
        # Wait for subscriptions
        await asyncio.sleep(0.1)
        
        # Simulate a complete user workflow
        print("Simulating complete user workflow...")
        
        # 1. User registration
        await event_bus.publish(
            "user.create_requested",
            data={
                "user_id": "user456",
                "email": "bob@example.com",
                "name": "Bob Wilson",
            },
            priority=EventPriority.HIGH,
        )
        
        # 2. Order creation
        await event_bus.publish(
            "order.create_requested",
            data={
                "order_id": "order456",
                "customer_id": "user456",
                "customer_email": "bob@example.com",
                "items": [
                    {"product": "smartphone", "quantity": 1, "price": 800},
                    {"product": "case", "quantity": 1, "price": 20},
                ],
                "amount": 820,
            },
        )
        
        # Wait for processing
        await asyncio.sleep(2)
        
        # Show comprehensive health status
        health = await event_bus.get_health_status()
        print(f"\nSystem Health:")
        print(f"- Status: {health['status']}")
        print(f"- Events processed: {health['performance']['events_processed']}")
        print(f"- Processing events: {health['processing_events']}")
        
        if health['metrics']:
            metrics_summary = health['metrics']
            print(f"- Publish rate: {metrics_summary.get('publish_rate_per_minute', 0):.1f}/min")
        
        # Show saga status
        running_sagas = orchestrator.get_running_sagas()
        print(f"\nActive sagas: {len(running_sagas)}")
        
        # Show audit log sample
        print(f"\nAudit log entries: {len(audit_service.audit_log)}")
        for entry in audit_service.audit_log[-3:]:
            print(f"- {entry['event_type']} at {entry['timestamp']}")
        
        await orchestrator.stop()
        
    finally:
        await event_bus.stop()


async def main():
    """Run all examples."""
    print("Event-Driven Architecture System Examples")
    print("=" * 50)
    
    await basic_example()
    await persistence_example()
    await saga_example()
    await circuit_breaker_example()
    await metrics_example()
    await comprehensive_example()
    
    print("\n" + "=" * 50)
    print("All examples completed successfully!")


if __name__ == "__main__":
    asyncio.run(main())