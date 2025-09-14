# Event-Driven Architecture System

A comprehensive, production-ready event-driven architecture system for the universal platform with advanced features for scalability, reliability, and observability.

## Features

### Core Components

- **Event Bus**: Central event routing with multiple transport mechanisms
- **Event Handlers**: Flexible handler registration and management
- **Middleware Pipeline**: Pluggable middleware for cross-cutting concerns
- **Event Persistence**: Event sourcing with snapshot support
- **Serialization**: Multiple serialization formats (JSON, MessagePack, Avro, Pickle)
- **Multiple Transports**: In-memory, Redis, RabbitMQ, Kafka support

### Advanced Features

- **Saga Pattern**: Distributed transaction management with compensation
- **Circuit Breakers**: Fault tolerance and resilience patterns
- **Event Replay**: Time-travel debugging and event replay capabilities
- **Dead Letter Queues**: Handling of failed events with retry mechanisms
- **Metrics & Monitoring**: Comprehensive performance monitoring
- **Event Versioning**: Schema evolution and migration support

### Production-Ready Features

- **Scalability**: Horizontal scaling with multiple transport options
- **Reliability**: Circuit breakers, retries, and dead letter queues
- **Observability**: Metrics, logging, tracing, and health checks
- **Performance**: Batching, compression, caching, and optimization
- **Security**: Encryption, authentication, and authorization support

## Quick Start

### Basic Usage

```python
import asyncio
from universal_platform.core.events import EventBus, Event

async def main():
    # Create event bus
    event_bus = EventBus()
    await event_bus.start()
    
    # Define event handler
    async def handle_user_created(event: Event):
        print(f"User created: {event.data['user_id']}")
    
    # Subscribe to events
    await event_bus.subscribe("user.created", handle_user_created)
    
    # Publish event
    await event_bus.publish(
        "user.created",
        data={"user_id": "123", "email": "user@example.com"}
    )
    
    await event_bus.stop()

asyncio.run(main())
```

### Using Decorators

```python
from universal_platform.core.events import event_handler, HandlerPriority

@event_handler(
    event_types=["user.created", "user.updated"],
    priority=HandlerPriority.HIGH.value,
    description="Handle user events"
)
async def handle_user_events(event: Event):
    print(f"Processing {event.event_type}: {event.data}")
```

## Configuration

### Event Bus Configuration

```python
from universal_platform.core.events import EventBusConfig, EventBus

config = EventBusConfig(
    max_workers=20,
    batch_size=100,
    enable_persistence=True,
    enable_metrics=True,
    enable_circuit_breaker=True,
    default_timeout_seconds=30,
    max_retries=3,
)

event_bus = EventBus(config=config)
```

### Transport Configuration

#### In-Memory Transport
```python
from universal_platform.core.events.transports import InMemoryTransport, MemoryTransportConfig

config = MemoryTransportConfig(
    max_queue_size=10000,
    enable_persistence=True,
    processing_delay_ms=0,
)

transport = InMemoryTransport(config)
```

#### Redis Transport
```python
from universal_platform.core.events.transports import RedisTransport, RedisTransportConfig

config = RedisTransportConfig(
    host="localhost",
    port=6379,
    enable_streams=True,
    enable_pub_sub=True,
    consumer_group="event_processors",
)

transport = RedisTransport(config)
```

#### RabbitMQ Transport
```python
from universal_platform.core.events.transports import RabbitMQTransport, RabbitMQTransportConfig

config = RabbitMQTransportConfig(
    host="localhost",
    port=5672,
    username="guest",
    password="guest",
    exchange_name="events",
    queue_durable=True,
)

transport = RabbitMQTransport(config)
```

#### Kafka Transport
```python
from universal_platform.core.events.transports import KafkaTransport, KafkaTransportConfig

config = KafkaTransportConfig(
    bootstrap_servers=["localhost:9092"],
    topic_prefix="events",
    group_id="event_processors",
    acks="all",
)

transport = KafkaTransport(config)
```

## Event Persistence

### Event Store
```python
from universal_platform.core.events import SQLiteEventStore, EventStoreConfig

config = EventStoreConfig(
    connection_string="sqlite:///events.db",
    compression_enabled=True,
    retention_days=365,
)

event_store = SQLiteEventStore(config)
await event_store.initialize()
```

### Event Sourcing
```python
from universal_platform.core.events import EventSourcing

event_sourcing = EventSourcing(event_store)

# Save events for an aggregate
events = [
    Event("account.created", {"aggregate_id": "acc123", "balance": 1000}),
    Event("account.deposit", {"aggregate_id": "acc123", "amount": 500}),
]

await event_sourcing.save_events("acc123", events)

# Load aggregate from events
# account = await event_sourcing.load_aggregate("acc123", AccountAggregate)
```

## Middleware

### Built-in Middleware
```python
from universal_platform.core.events.middleware import (
    LoggingMiddleware,
    ValidationMiddleware,
    MetricsMiddleware,
    TracingMiddleware,
    RateLimitingMiddleware,
)

# Add middleware to pipeline
await event_bus.middleware_pipeline.add_middleware(LoggingMiddleware())
await event_bus.middleware_pipeline.add_middleware(ValidationMiddleware())
await event_bus.middleware_pipeline.add_middleware(MetricsMiddleware())
```

### Custom Middleware
```python
from universal_platform.core.events.middleware import EventMiddleware, MiddlewareContext

class CustomMiddleware(EventMiddleware):
    async def process_inbound(self, context: MiddlewareContext) -> MiddlewareContext:
        # Process before handler execution
        print(f"Processing inbound: {context.event.event_type}")
        return context
    
    async def process_outbound(self, context: MiddlewareContext) -> MiddlewareContext:
        # Process after handler execution
        print(f"Processing outbound: {len(context.results)} results")
        return context

await event_bus.middleware_pipeline.add_middleware(CustomMiddleware("custom"))
```

## Saga Pattern

### Defining a Saga
```python
from universal_platform.core.events.saga import Saga, SagaStep

class OrderProcessingSaga(Saga):
    async def define_steps(self) -> List[SagaStep]:
        return [
            SagaStep(
                name="validate_order",
                action=self._validate_order,
                compensation=self._cancel_validation,
                timeout_seconds=30,
            ),
            SagaStep(
                name="reserve_inventory", 
                action=self._reserve_inventory,
                compensation=self._release_inventory,
                timeout_seconds=60,
            ),
            SagaStep(
                name="process_payment",
                action=self._process_payment,
                compensation=self._refund_payment,
                timeout_seconds=120,
            ),
        ]
    
    async def _validate_order(self, context):
        # Validation logic
        return {"validated": True}
    
    async def _cancel_validation(self, context, result):
        # Compensation logic
        pass
```

### Running Sagas
```python
from universal_platform.core.events.saga import SagaOrchestrator, SagaManager

# Create orchestrator
orchestrator = SagaOrchestrator(event_store)
await orchestrator.start()

# Create manager and register sagas
saga_manager = SagaManager(orchestrator)
saga_manager.register_saga(OrderProcessingSaga)

# Start saga execution
execution = await saga_manager.start_saga(
    "OrderProcessingSaga",
    context={"order_id": "123", "amount": 100}
)
```

## Circuit Breaker

```python
from universal_platform.core.events.circuit_breaker import CircuitBreaker, CircuitBreakerConfig

config = CircuitBreakerConfig(
    failure_threshold=5,
    recovery_timeout=60.0,
    success_threshold=3,
    timeout=30.0,
)

circuit_breaker = CircuitBreaker(config)

# Use circuit breaker
try:
    result = await circuit_breaker.call(unreliable_service)
except Exception as e:
    # Handle circuit breaker open or service failure
    print(f"Service call failed: {e}")
```

## Metrics and Monitoring

```python
from universal_platform.core.events.metrics import EventMetrics

metrics = EventMetrics()
await metrics.start()

# Metrics are automatically collected by the event bus
# Manual metrics recording:
metrics.record_event_published("user.created", processing_time_ms=10.5)
metrics.record_event_processed("user.created", processing_time_ms=25.0, handler_count=3)
metrics.record_handler_success("user_handler", execution_time_ms=15.0)

# Get metrics summary
summary = metrics.get_summary()
print(f"Events processed: {summary['overview']['events_processed_total']}")

# Export Prometheus metrics
prometheus_metrics = metrics.export_prometheus()
```

## Serialization

### Configure Serialization
```python
from universal_platform.core.events.serialization import (
    EventSerializerFactory, 
    SerializationConfig,
    SerializationFormat
)

config = SerializationConfig(
    format=SerializationFormat.JSON,
    compression_enabled=True,
    schema_validation=True,
)

serializer = EventSerializerFactory.create_serializer(config)
```

### Schema Validation
```python
from universal_platform.core.events.serialization import SchemaRegistry

schema_registry = SchemaRegistry()
schema_registry.register_schema(
    "user.created",
    "1.0",
    {
        "type": "object",
        "required": ["user_id", "email"],
        "properties": {
            "user_id": {"type": "string"},
            "email": {"type": "string"},
            "name": {"type": "string"},
        }
    }
)

# Validation happens automatically during event processing
```

## Error Handling

### Dead Letter Queue
```python
from universal_platform.core.events.persistence import DeadLetterQueue

dlq = DeadLetterQueue(event_store)

# Failed events are automatically sent to DLQ
# Retrieve dead letters
dead_letters = await dlq.get_dead_letters(limit=100)

# Retry dead letter
await dlq.retry_dead_letter("dead_letter_event_id")
```

### Retry Configuration
```python
# Configure retries in event metadata
event = Event(
    event_type="user.process",
    data={"user_id": "123"},
    metadata=EventMetadata(
        max_retries=5,
        retry_count=0,
    )
)
```

## Performance Optimization

### Batching
```python
# Events are automatically batched based on configuration
config = EventBusConfig(
    batch_size=100,
    batch_timeout_seconds=1.0,
)
```

### Caching
```python
from universal_platform.core.events.middleware import CachingMiddleware

cache_middleware = CachingMiddleware(
    cache_size=1000,
    cache_ttl_seconds=3600,
)
await event_bus.middleware_pipeline.add_middleware(cache_middleware)
```

### Compression
```python
# Enable compression in serialization config
config = SerializationConfig(
    compression_enabled=True,
    compression_level=6,
)
```

## Health Checks

```python
# Get comprehensive health status
health = await event_bus.get_health_status()
print(f"Status: {health['status']}")
print(f"Transport: {health['transport']['status']}")
print(f"Handlers: {health['handlers']['total_handlers']}")
print(f"Circuit breaker: {health['circuit_breaker']['state'] if health['circuit_breaker'] else 'disabled'}")
```

## Event Replay

```python
# Replay events from event store
replayed_count = await event_bus.replay_events(
    from_timestamp=datetime(2024, 1, 1),
    to_timestamp=datetime(2024, 12, 31),
    event_types=["user.created", "user.updated"],
)

print(f"Replayed {replayed_count} events")
```

## Examples

See `examples.py` for comprehensive examples including:

- Basic event publishing and handling
- Event persistence and sourcing
- Saga pattern implementation
- Circuit breaker usage
- Metrics collection
- Complete system integration

## Architecture

### System Components

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Event Bus     │────│  Middleware      │────│   Handlers      │
│   - Routing     │    │  - Logging       │    │   - Registry    │
│   - Publishing  │    │  - Validation    │    │   - Execution   │
│   - Batching    │    │  - Metrics       │    │   - Priorities  │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Transport     │    │   Persistence    │    │   Monitoring    │
│   - In-memory   │    │   - Event Store  │    │   - Metrics     │
│   - Redis       │    │   - Snapshots    │    │   - Health      │
│   - RabbitMQ    │    │   - Replay       │    │   - Tracing     │
│   - Kafka       │    │   - Sourcing     │    │   - Alerting    │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

### Event Flow

```
1. Event Creation → 2. Middleware (Inbound) → 3. Transport → 4. Handler Execution
                                ↓
8. Monitoring ← 7. Persistence ← 6. Middleware (Outbound) ← 5. Result Processing
```

## Best Practices

1. **Event Design**
   - Use descriptive event types (e.g., `user.created`, `order.shipped`)
   - Include correlation IDs for tracing
   - Keep event data minimal and focused
   - Use versioning for schema evolution

2. **Handler Design**
   - Keep handlers idempotent
   - Handle failures gracefully
   - Use appropriate priorities
   - Implement compensation logic for sagas

3. **Performance**
   - Use appropriate batch sizes
   - Enable compression for large events
   - Configure circuit breakers for external services
   - Monitor metrics and set up alerting

4. **Reliability**
   - Configure dead letter queues
   - Use appropriate retry strategies
   - Implement health checks
   - Set up monitoring and alerting

5. **Security**
   - Validate event data
   - Use encryption for sensitive data
   - Implement authentication and authorization
   - Audit event processing

## Contributing

When contributing to the event system:

1. Ensure all new features have tests
2. Update documentation
3. Follow the existing code style
4. Add metrics for new features
5. Consider backward compatibility

## License

This event system is part of the universal platform and follows the same license terms.