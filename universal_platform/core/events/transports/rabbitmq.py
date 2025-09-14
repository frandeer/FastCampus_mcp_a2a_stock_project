"""
RabbitMQ-based event transport implementation.
"""

import asyncio
import logging
import json
from typing import Any, Dict, List, Callable, Optional
from datetime import datetime
from dataclasses import dataclass
import aio_pika
from aio_pika import Connection, Channel, Exchange, Queue, Message
from aio_pika.abc import AbstractChannel, AbstractExchange, AbstractQueue
from aio_pika.patterns import Master

from ..models import Event
from ..serialization import EventSerializer, JSONEventSerializer, SerializationConfig


logger = logging.getLogger(__name__)


@dataclass
class RabbitMQTransportConfig:
    """Configuration for RabbitMQ transport."""
    # Connection settings
    host: str = "localhost"
    port: int = 5672
    virtual_host: str = "/"
    username: str = "guest"
    password: str = "guest"
    ssl: bool = False
    ssl_options: Optional[Dict[str, Any]] = None
    
    # Connection pool settings
    max_channels: int = 10
    heartbeat: int = 60
    connection_timeout: int = 30
    
    # Exchange settings
    exchange_name: str = "events"
    exchange_type: str = "topic"
    exchange_durable: bool = True
    exchange_auto_delete: bool = False
    
    # Queue settings
    queue_prefix: str = "events"
    queue_durable: bool = True
    queue_auto_delete: bool = False
    queue_exclusive: bool = False
    dead_letter_exchange: str = "events.dlx"
    
    # Message settings
    message_ttl: Optional[int] = None  # milliseconds
    max_retries: int = 3
    retry_delay: int = 5000  # milliseconds
    
    # Consumer settings
    prefetch_count: int = 10
    auto_ack: bool = False
    
    # Performance settings
    confirm_delivery: bool = True
    publisher_confirms: bool = True


class RabbitMQTransport:
    """RabbitMQ-based event transport with advanced features."""
    
    def __init__(
        self,
        config: Optional[RabbitMQTransportConfig] = None,
        serializer: Optional[EventSerializer] = None,
    ):
        self.config = config or RabbitMQTransportConfig()
        self.serializer = serializer or JSONEventSerializer(SerializationConfig())
        
        # Connection management
        self.connection: Optional[Connection] = None
        self.channel: Optional[Channel] = None
        self.master: Optional[Master] = None
        
        # Exchanges and queues
        self.event_exchange: Optional[Exchange] = None
        self.dlx_exchange: Optional[Exchange] = None
        self.queues: Dict[str, Queue] = {}
        
        # State
        self.running = False
        self.subscribers: Dict[str, List[Callable]] = {}
        
        # Background tasks
        self._consumer_tasks: List[asyncio.Task] = []
        self._health_check_task: Optional[asyncio.Task] = None
        
        # Metrics
        self._metrics = {
            "events_published": 0,
            "events_received": 0,
            "events_failed": 0,
            "events_retried": 0,
            "connection_errors": 0,
            "dead_letters": 0,
            "last_heartbeat": None,
        }
        
        logger.info("RabbitMQTransport initialized")
    
    async def start(self) -> None:
        """Start the RabbitMQ transport."""
        if self.running:
            return
        
        try:
            # Create connection
            connection_url = self._build_connection_url()
            self.connection = await aio_pika.connect_robust(
                connection_url,
                heartbeat=self.config.heartbeat,
                connection_timeout=self.config.connection_timeout,
            )
            
            # Create channel
            self.channel = await self.connection.channel()
            await self.channel.set_qos(prefetch_count=self.config.prefetch_count)
            
            # Enable publisher confirms if configured
            if self.config.publisher_confirms:
                await self.channel.confirm_delivery()
            
            # Create master for RPC patterns
            self.master = Master(self.channel)
            
            # Set up exchanges
            await self._setup_exchanges()
            
            # Start health check
            self._health_check_task = asyncio.create_task(self._health_check_loop())
            
            self.running = True
            logger.info("RabbitMQTransport started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start RabbitMQTransport: {e}")
            await self.stop()
            raise
    
    async def stop(self) -> None:
        """Stop the RabbitMQ transport."""
        if not self.running:
            return
        
        self.running = False
        
        # Cancel consumer tasks
        for task in self._consumer_tasks:
            task.cancel()
        
        # Cancel health check
        if self._health_check_task:
            self._health_check_task.cancel()
        
        # Wait for tasks to complete
        all_tasks = self._consumer_tasks + [self._health_check_task]
        await asyncio.gather(*[t for t in all_tasks if t], return_exceptions=True)
        
        # Close connections
        if self.connection and not self.connection.is_closed:
            await self.connection.close()
        
        logger.info("RabbitMQTransport stopped")
    
    async def publish(self, event: Event) -> bool:
        """Publish an event to RabbitMQ."""
        if not self.running or not self.channel or not self.event_exchange:
            return False
        
        try:
            # Serialize event
            event_data = self.serializer.serialize(event)
            
            # Create message
            message = Message(
                event_data,
                content_type=self.serializer.get_content_type(),
                message_id=event.event_id,
                correlation_id=event.metadata.correlation_id,
                timestamp=event.metadata.timestamp,
                headers={
                    "event_type": event.event_type,
                    "version": event.metadata.version,
                    "source": event.metadata.source,
                    "retry_count": event.metadata.retry_count,
                },
                expiration=self.config.message_ttl,
            )
            
            # Determine routing key
            routing_key = self._get_routing_key(event.event_type)
            
            # Publish message
            await self.event_exchange.publish(
                message,
                routing_key=routing_key,
                mandatory=True,
            )
            
            # Update metrics
            self._metrics["events_published"] += 1
            
            logger.debug(f"Published event {event.event_id} to RabbitMQ")
            return True
            
        except Exception as e:
            logger.error(f"Failed to publish event {event.event_id}: {e}")
            self._metrics["events_failed"] += 1
            return False
    
    async def subscribe(self, event_type: str, handler: Callable[[Event], Any]) -> None:
        """Subscribe to events of a specific type."""
        if not self.channel:
            raise RuntimeError("Transport not started")
        
        # Add handler to subscribers
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        self.subscribers[event_type].append(handler)
        
        # Create queue if not exists
        if event_type not in self.queues:
            await self._create_queue(event_type)
        
        # Start consumer if this is the first handler
        if len(self.subscribers[event_type]) == 1:
            task = asyncio.create_task(self._consume_queue(event_type))
            self._consumer_tasks.append(task)
        
        logger.info(f"Subscribed to {event_type}")
    
    async def unsubscribe(self, event_type: str, handler: Callable[[Event], Any]) -> None:
        """Unsubscribe from events."""
        if event_type in self.subscribers:
            try:
                self.subscribers[event_type].remove(handler)
                
                # If no more handlers, we could cancel the consumer task
                # For simplicity, we'll leave the consumer running
                
                if not self.subscribers[event_type]:
                    del self.subscribers[event_type]
                
                logger.info(f"Unsubscribed from {event_type}")
                
            except ValueError:
                logger.warning(f"Handler not found for {event_type}")
    
    async def health_check(self) -> Dict[str, Any]:
        """Check RabbitMQ transport health."""
        if not self.connection:
            return {"status": "disconnected"}
        
        try:
            # Check connection
            if self.connection.is_closed:
                return {"status": "connection_closed"}
            
            # Get basic info
            return {
                "status": "healthy" if self.running else "stopped",
                "connection_state": "open" if not self.connection.is_closed else "closed",
                "active_consumers": len(self._consumer_tasks),
                "subscribed_topics": len(self.subscribers),
                "queues": list(self.queues.keys()),
                "metrics": self._metrics.copy(),
            }
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            self._metrics["connection_errors"] += 1
            return {
                "status": "unhealthy",
                "error": str(e),
            }
    
    def _build_connection_url(self) -> str:
        """Build RabbitMQ connection URL."""
        scheme = "amqps" if self.config.ssl else "amqp"
        return (
            f"{scheme}://{self.config.username}:{self.config.password}"
            f"@{self.config.host}:{self.config.port}{self.config.virtual_host}"
        )
    
    async def _setup_exchanges(self) -> None:
        """Set up RabbitMQ exchanges."""
        if not self.channel:
            return
        
        # Create main event exchange
        self.event_exchange = await self.channel.declare_exchange(
            self.config.exchange_name,
            type=self.config.exchange_type,
            durable=self.config.exchange_durable,
            auto_delete=self.config.exchange_auto_delete,
        )
        
        # Create dead letter exchange
        self.dlx_exchange = await self.channel.declare_exchange(
            self.config.dead_letter_exchange,
            type="direct",
            durable=True,
            auto_delete=False,
        )
        
        logger.info("RabbitMQ exchanges set up successfully")
    
    async def _create_queue(self, event_type: str) -> None:
        """Create queue for event type."""
        if not self.channel or not self.event_exchange:
            return
        
        queue_name = f"{self.config.queue_prefix}.{event_type}"
        routing_key = self._get_routing_key(event_type)
        
        # Dead letter queue arguments
        arguments = {}
        if self.config.dead_letter_exchange:
            arguments.update({
                "x-dead-letter-exchange": self.config.dead_letter_exchange,
                "x-dead-letter-routing-key": f"dead.{event_type}",
            })
        
        if self.config.message_ttl:
            arguments["x-message-ttl"] = self.config.message_ttl
        
        # Create queue
        queue = await self.channel.declare_queue(
            queue_name,
            durable=self.config.queue_durable,
            auto_delete=self.config.queue_auto_delete,
            exclusive=self.config.queue_exclusive,
            arguments=arguments,
        )
        
        # Bind to exchange
        await queue.bind(self.event_exchange, routing_key=routing_key)
        
        # Store queue reference
        self.queues[event_type] = queue
        
        # Create dead letter queue
        dlq_name = f"{queue_name}.dead"
        dlq = await self.channel.declare_queue(
            dlq_name,
            durable=True,
            auto_delete=False,
        )
        
        if self.dlx_exchange:
            await dlq.bind(self.dlx_exchange, routing_key=f"dead.{event_type}")
        
        logger.info(f"Created queue {queue_name} for event type {event_type}")
    
    async def _consume_queue(self, event_type: str) -> None:
        """Consume messages from queue."""
        if event_type not in self.queues:
            return
        
        queue = self.queues[event_type]
        logger.info(f"Starting consumer for {event_type}")
        
        try:
            async with queue.iterator() as queue_iter:
                async for message in queue_iter:
                    if not self.running:
                        break
                    
                    await self._handle_message(event_type, message)
                    
        except asyncio.CancelledError:
            logger.info(f"Consumer for {event_type} cancelled")
        except Exception as e:
            logger.error(f"Consumer for {event_type} failed: {e}")
            self._metrics["connection_errors"] += 1
    
    async def _handle_message(self, event_type: str, message: aio_pika.IncomingMessage) -> None:
        """Handle incoming message."""
        try:
            async with message.process(requeue=False):
                # Deserialize event
                event = self.serializer.deserialize(message.body)
                
                # Get retry count from headers
                retry_count = int(message.headers.get("retry_count", 0))
                
                # Call handlers
                handlers = self.subscribers.get(event_type, [])
                if handlers:
                    await self._call_handlers(handlers, event)
                
                # Update metrics
                self._metrics["events_received"] += 1
                
        except Exception as e:
            logger.error(f"Failed to handle message: {e}")
            
            # Check if we should retry
            retry_count = int(message.headers.get("retry_count", 0))
            if retry_count < self.config.max_retries:
                await self._retry_message(message, retry_count + 1)
            else:
                # Send to dead letter queue
                self._metrics["dead_letters"] += 1
                logger.error(f"Message sent to dead letter queue after {retry_count} retries")
            
            self._metrics["events_failed"] += 1
            
            # Reject message (will go to DLQ due to queue configuration)
            message.reject()
    
    async def _retry_message(self, message: aio_pika.IncomingMessage, retry_count: int) -> None:
        """Retry failed message."""
        if not self.channel or not self.event_exchange:
            return
        
        try:
            # Create retry message with updated headers
            headers = dict(message.headers or {})
            headers["retry_count"] = retry_count
            
            retry_message = Message(
                message.body,
                content_type=message.content_type,
                message_id=message.message_id,
                correlation_id=message.correlation_id,
                timestamp=datetime.utcnow(),
                headers=headers,
                expiration=self.config.retry_delay,  # Delay before retry
            )
            
            # Determine routing key from headers
            event_type = headers.get("event_type")
            if event_type:
                routing_key = self._get_routing_key(event_type)
                
                # Publish retry message
                await self.event_exchange.publish(
                    retry_message,
                    routing_key=routing_key,
                )
                
                self._metrics["events_retried"] += 1
                logger.info(f"Retrying message (attempt {retry_count})")
                
        except Exception as e:
            logger.error(f"Failed to retry message: {e}")
    
    async def _call_handlers(self, handlers: List[Callable], event: Event) -> None:
        """Call all handlers for an event."""
        tasks = []
        for handler in handlers:
            task = asyncio.create_task(self._call_handler(handler, event))
            tasks.append(task)
        
        # Wait for all handlers
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Log any handler failures
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Handler {handlers[i]} failed: {result}")
    
    async def _call_handler(self, handler: Callable, event: Event) -> None:
        """Call individual handler."""
        try:
            if asyncio.iscoroutinefunction(handler):
                await handler(event)
            else:
                # Run sync handler in thread pool
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, handler, event)
                
        except Exception as e:
            logger.error(f"Handler {handler} failed for event {event.event_id}: {e}")
            raise
    
    def _get_routing_key(self, event_type: str) -> str:
        """Get routing key for event type."""
        # Convert event type to routing key
        # e.g., "user.created" -> "user.created"
        # e.g., "order.payment.completed" -> "order.payment.completed"
        return event_type
    
    async def _health_check_loop(self) -> None:
        """Background health check loop."""
        while self.running:
            try:
                await asyncio.sleep(30)  # Check every 30 seconds
                
                if self.connection and not self.connection.is_closed:
                    self._metrics["last_heartbeat"] = datetime.utcnow()
                else:
                    self._metrics["connection_errors"] += 1
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health check failed: {e}")
                self._metrics["connection_errors"] += 1
    
    async def get_queue_info(self, event_type: str) -> Optional[Dict[str, Any]]:
        """Get queue information."""
        if event_type not in self.queues or not self.channel:
            return None
        
        try:
            queue = self.queues[event_type]
            info = await self.channel.queue_declare(queue.name, passive=True)
            
            return {
                "name": queue.name,
                "message_count": info.method.message_count,
                "consumer_count": info.method.consumer_count,
                "durable": queue.durable,
                "auto_delete": queue.auto_delete,
                "exclusive": queue.exclusive,
            }
            
        except Exception as e:
            logger.error(f"Failed to get queue info: {e}")
            return None
    
    async def purge_queue(self, event_type: str) -> bool:
        """Purge all messages from queue."""
        if event_type not in self.queues:
            return False
        
        try:
            queue = self.queues[event_type]
            await queue.purge()
            logger.info(f"Purged queue for {event_type}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to purge queue: {e}")
            return False