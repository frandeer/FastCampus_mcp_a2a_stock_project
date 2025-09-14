"""
Kafka-based event transport implementation.
"""

import asyncio
import logging
import json
from typing import Any, Dict, List, Callable, Optional, Set
from datetime import datetime
from dataclasses import dataclass
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
from aiokafka.errors import KafkaError
from kafka.admin import KafkaAdminClient, NewTopic
from kafka.admin.config_resource import ConfigResource, ConfigResourceType
from kafka.errors import TopicAlreadyExistsError

from ..models import Event
from ..serialization import EventSerializer, JSONEventSerializer, SerializationConfig


logger = logging.getLogger(__name__)


@dataclass
class KafkaTransportConfig:
    """Configuration for Kafka transport."""
    # Broker settings
    bootstrap_servers: List[str] = None
    security_protocol: str = "PLAINTEXT"
    sasl_mechanism: Optional[str] = None
    sasl_plain_username: Optional[str] = None
    sasl_plain_password: Optional[str] = None
    ssl_context: Optional[Any] = None
    
    # Topic settings
    topic_prefix: str = "events"
    num_partitions: int = 3
    replication_factor: int = 1
    topic_config: Dict[str, str] = None
    auto_create_topics: bool = True
    
    # Producer settings
    acks: str = "all"  # 0, 1, or "all"
    retries: int = 3
    batch_size: int = 16384
    linger_ms: int = 10
    buffer_memory: int = 33554432
    compression_type: Optional[str] = "gzip"
    max_request_size: int = 1048576
    
    # Consumer settings
    group_id: str = "event_processors"
    auto_offset_reset: str = "latest"
    enable_auto_commit: bool = True
    auto_commit_interval_ms: int = 5000
    max_poll_records: int = 500
    max_poll_interval_ms: int = 300000
    session_timeout_ms: int = 30000
    heartbeat_interval_ms: int = 10000
    fetch_min_bytes: int = 1
    fetch_max_wait_ms: int = 500
    
    # Performance settings
    max_concurrent_handlers: int = 10
    consumer_timeout_ms: int = 1000
    
    def __post_init__(self):
        if self.bootstrap_servers is None:
            self.bootstrap_servers = ["localhost:9092"]
        if self.topic_config is None:
            self.topic_config = {
                "cleanup.policy": "delete",
                "retention.ms": str(7 * 24 * 60 * 60 * 1000),  # 7 days
                "segment.ms": str(24 * 60 * 60 * 1000),  # 24 hours
            }


class KafkaTransport:
    """Kafka-based event transport with high throughput and durability."""
    
    def __init__(
        self,
        config: Optional[KafkaTransportConfig] = None,
        serializer: Optional[EventSerializer] = None,
    ):
        self.config = config or KafkaTransportConfig()
        self.serializer = serializer or JSONEventSerializer(SerializationConfig())
        
        # Kafka clients
        self.producer: Optional[AIOKafkaProducer] = None
        self.consumers: Dict[str, AIOKafkaConsumer] = {}
        self.admin_client: Optional[KafkaAdminClient] = None
        
        # State
        self.running = False
        self.subscribers: Dict[str, List[Callable]] = {}
        self.created_topics: Set[str] = set()
        
        # Background tasks
        self._consumer_tasks: List[asyncio.Task] = []
        self._health_check_task: Optional[asyncio.Task] = None
        
        # Concurrency control
        self._handler_semaphore = asyncio.Semaphore(self.config.max_concurrent_handlers)
        
        # Metrics
        self._metrics = {
            "events_published": 0,
            "events_received": 0,
            "events_failed": 0,
            "producer_errors": 0,
            "consumer_errors": 0,
            "topics_created": 0,
            "last_heartbeat": None,
        }
        
        logger.info("KafkaTransport initialized")
    
    async def start(self) -> None:
        """Start the Kafka transport."""
        if self.running:
            return
        
        try:
            # Create admin client
            self._create_admin_client()
            
            # Create producer
            await self._create_producer()
            
            # Start health check
            self._health_check_task = asyncio.create_task(self._health_check_loop())
            
            self.running = True
            logger.info("KafkaTransport started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start KafkaTransport: {e}")
            await self.stop()
            raise
    
    async def stop(self) -> None:
        """Stop the Kafka transport."""
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
        
        # Stop consumers
        for consumer in self.consumers.values():
            await consumer.stop()
        self.consumers.clear()
        
        # Stop producer
        if self.producer:
            await self.producer.stop()
        
        # Close admin client
        if self.admin_client:
            self.admin_client.close()
        
        logger.info("KafkaTransport stopped")
    
    async def publish(self, event: Event) -> bool:
        """Publish an event to Kafka."""
        if not self.running or not self.producer:
            return False
        
        try:
            # Get topic name
            topic = self._get_topic_name(event.event_type)
            
            # Create topic if needed
            if self.config.auto_create_topics and topic not in self.created_topics:
                await self._ensure_topic_exists(topic)
            
            # Serialize event
            event_data = self.serializer.serialize(event)
            
            # Create headers
            headers = [
                ("event_id", event.event_id.encode()),
                ("event_type", event.event_type.encode()),
                ("version", str(event.metadata.version).encode()),
                ("timestamp", str(int(event.metadata.timestamp.timestamp() * 1000)).encode()),
            ]
            
            if event.metadata.correlation_id:
                headers.append(("correlation_id", event.metadata.correlation_id.encode()))
            
            if event.metadata.source:
                headers.append(("source", event.metadata.source.encode()))
            
            # Determine partition key (for ordering)
            partition_key = self._get_partition_key(event)
            
            # Send message
            future = await self.producer.send(
                topic,
                value=event_data,
                key=partition_key.encode() if partition_key else None,
                headers=headers,
            )
            
            # Wait for acknowledgment
            record_metadata = await future
            
            # Update metrics
            self._metrics["events_published"] += 1
            
            logger.debug(
                f"Published event {event.event_id} to topic {topic} "
                f"(partition {record_metadata.partition}, offset {record_metadata.offset})"
            )
            return True
            
        except Exception as e:
            logger.error(f"Failed to publish event {event.event_id}: {e}")
            self._metrics["producer_errors"] += 1
            return False
    
    async def subscribe(self, event_type: str, handler: Callable[[Event], Any]) -> None:
        """Subscribe to events of a specific type."""
        # Add handler to subscribers
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        self.subscribers[event_type].append(handler)
        
        # Create consumer if this is the first handler
        if len(self.subscribers[event_type]) == 1:
            await self._create_consumer(event_type)
            
            # Start consumer task
            task = asyncio.create_task(self._consume_topic(event_type))
            self._consumer_tasks.append(task)
        
        logger.info(f"Subscribed to {event_type}")
    
    async def unsubscribe(self, event_type: str, handler: Callable[[Event], Any]) -> None:
        """Unsubscribe from events."""
        if event_type in self.subscribers:
            try:
                self.subscribers[event_type].remove(handler)
                
                # If no more handlers, stop consumer
                if not self.subscribers[event_type]:
                    del self.subscribers[event_type]
                    
                    if event_type in self.consumers:
                        consumer = self.consumers[event_type]
                        await consumer.stop()
                        del self.consumers[event_type]
                
                logger.info(f"Unsubscribed from {event_type}")
                
            except ValueError:
                logger.warning(f"Handler not found for {event_type}")
    
    async def health_check(self) -> Dict[str, Any]:
        """Check Kafka transport health."""
        try:
            # Check producer
            producer_healthy = self.producer is not None and not self.producer._closed
            
            # Check consumers
            consumers_healthy = all(
                not consumer._closed for consumer in self.consumers.values()
            )
            
            # Get cluster metadata
            cluster_info = {}
            if self.producer:
                try:
                    metadata = await self.producer.client.fetch_metadata()
                    cluster_info = {
                        "brokers": len(metadata.brokers),
                        "topics": len(metadata.topics),
                    }
                except Exception:
                    pass
            
            return {
                "status": "healthy" if (self.running and producer_healthy and consumers_healthy) else "unhealthy",
                "producer_healthy": producer_healthy,
                "consumers_healthy": consumers_healthy,
                "active_consumers": len(self.consumers),
                "subscribed_topics": len(self.subscribers),
                "cluster_info": cluster_info,
                "metrics": self._metrics.copy(),
            }
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
            }
    
    def _create_admin_client(self) -> None:
        """Create Kafka admin client."""
        admin_config = {
            "bootstrap_servers": self.config.bootstrap_servers,
            "security_protocol": self.config.security_protocol,
        }
        
        if self.config.sasl_mechanism:
            admin_config.update({
                "sasl_mechanism": self.config.sasl_mechanism,
                "sasl_plain_username": self.config.sasl_plain_username,
                "sasl_plain_password": self.config.sasl_plain_password,
            })
        
        self.admin_client = KafkaAdminClient(**admin_config)
    
    async def _create_producer(self) -> None:
        """Create Kafka producer."""
        producer_config = {
            "bootstrap_servers": self.config.bootstrap_servers,
            "security_protocol": self.config.security_protocol,
            "acks": self.config.acks,
            "retries": self.config.retries,
            "batch_size": self.config.batch_size,
            "linger_ms": self.config.linger_ms,
            "buffer_memory": self.config.buffer_memory,
            "compression_type": self.config.compression_type,
            "max_request_size": self.config.max_request_size,
        }
        
        if self.config.sasl_mechanism:
            producer_config.update({
                "sasl_mechanism": self.config.sasl_mechanism,
                "sasl_plain_username": self.config.sasl_plain_username,
                "sasl_plain_password": self.config.sasl_plain_password,
            })
        
        self.producer = AIOKafkaProducer(**producer_config)
        await self.producer.start()
    
    async def _create_consumer(self, event_type: str) -> None:
        """Create Kafka consumer for event type."""
        topic = self._get_topic_name(event_type)
        
        # Ensure topic exists
        if self.config.auto_create_topics:
            await self._ensure_topic_exists(topic)
        
        consumer_config = {
            "bootstrap_servers": self.config.bootstrap_servers,
            "group_id": f"{self.config.group_id}_{event_type}",
            "security_protocol": self.config.security_protocol,
            "auto_offset_reset": self.config.auto_offset_reset,
            "enable_auto_commit": self.config.enable_auto_commit,
            "auto_commit_interval_ms": self.config.auto_commit_interval_ms,
            "max_poll_records": self.config.max_poll_records,
            "max_poll_interval_ms": self.config.max_poll_interval_ms,
            "session_timeout_ms": self.config.session_timeout_ms,
            "heartbeat_interval_ms": self.config.heartbeat_interval_ms,
            "fetch_min_bytes": self.config.fetch_min_bytes,
            "fetch_max_wait_ms": self.config.fetch_max_wait_ms,
            "consumer_timeout_ms": self.config.consumer_timeout_ms,
        }
        
        if self.config.sasl_mechanism:
            consumer_config.update({
                "sasl_mechanism": self.config.sasl_mechanism,
                "sasl_plain_username": self.config.sasl_plain_username,
                "sasl_plain_password": self.config.sasl_plain_password,
            })
        
        consumer = AIOKafkaConsumer(topic, **consumer_config)
        await consumer.start()
        
        self.consumers[event_type] = consumer
        logger.info(f"Created consumer for topic {topic}")
    
    async def _consume_topic(self, event_type: str) -> None:
        """Consume messages from Kafka topic."""
        if event_type not in self.consumers:
            return
        
        consumer = self.consumers[event_type]
        logger.info(f"Starting consumer for {event_type}")
        
        try:
            async for message in consumer:
                if not self.running:
                    break
                
                # Process message with concurrency control
                async with self._handler_semaphore:
                    await self._handle_message(event_type, message)
                    
        except asyncio.CancelledError:
            logger.info(f"Consumer for {event_type} cancelled")
        except Exception as e:
            logger.error(f"Consumer for {event_type} failed: {e}")
            self._metrics["consumer_errors"] += 1
    
    async def _handle_message(self, event_type: str, message) -> None:
        """Handle incoming Kafka message."""
        try:
            # Deserialize event
            event = self.serializer.deserialize(message.value)
            
            # Call handlers
            handlers = self.subscribers.get(event_type, [])
            if handlers:
                await self._call_handlers(handlers, event)
            
            # Update metrics
            self._metrics["events_received"] += 1
            
            logger.debug(
                f"Processed event {event.event_id} from topic {message.topic} "
                f"(partition {message.partition}, offset {message.offset})"
            )
            
        except Exception as e:
            logger.error(f"Failed to handle message: {e}")
            self._metrics["events_failed"] += 1
    
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
    
    def _get_topic_name(self, event_type: str) -> str:
        """Get Kafka topic name for event type."""
        # Replace dots with underscores for valid topic names
        sanitized_type = event_type.replace(".", "_")
        return f"{self.config.topic_prefix}_{sanitized_type}"
    
    def _get_partition_key(self, event: Event) -> Optional[str]:
        """Get partition key for event (for ordering)."""
        # Use correlation_id for partitioning to maintain order for related events
        if event.metadata.correlation_id:
            return event.metadata.correlation_id
        
        # Extract aggregate_id from event data if available
        aggregate_id = event.data.get("aggregate_id")
        if aggregate_id:
            return str(aggregate_id)
        
        # Default: use event type for basic partitioning
        return event.event_type
    
    async def _ensure_topic_exists(self, topic: str) -> None:
        """Ensure Kafka topic exists."""
        if topic in self.created_topics:
            return
        
        try:
            if not self.admin_client:
                return
            
            # Check if topic already exists
            existing_topics = self.admin_client.list_topics()
            if topic in existing_topics:
                self.created_topics.add(topic)
                return
            
            # Create topic
            topic_list = [
                NewTopic(
                    name=topic,
                    num_partitions=self.config.num_partitions,
                    replication_factor=self.config.replication_factor,
                    topic_configs=self.config.topic_config,
                )
            ]
            
            self.admin_client.create_topics(topic_list, validate_only=False)
            self.created_topics.add(topic)
            self._metrics["topics_created"] += 1
            
            logger.info(f"Created Kafka topic: {topic}")
            
        except TopicAlreadyExistsError:
            # Topic was created by another process
            self.created_topics.add(topic)
        except Exception as e:
            logger.error(f"Failed to create topic {topic}: {e}")
    
    async def _health_check_loop(self) -> None:
        """Background health check loop."""
        while self.running:
            try:
                await asyncio.sleep(30)  # Check every 30 seconds
                
                # Update heartbeat
                self._metrics["last_heartbeat"] = datetime.utcnow()
                
                # Check producer health
                if self.producer and self.producer._closed:
                    logger.warning("Kafka producer is closed")
                    self._metrics["producer_errors"] += 1
                
                # Check consumer health
                for event_type, consumer in self.consumers.items():
                    if consumer._closed:
                        logger.warning(f"Kafka consumer for {event_type} is closed")
                        self._metrics["consumer_errors"] += 1
                        
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health check failed: {e}")
    
    async def get_topic_info(self, event_type: str) -> Optional[Dict[str, Any]]:
        """Get topic information."""
        topic = self._get_topic_name(event_type)
        
        try:
            if not self.admin_client:
                return None
            
            # Get topic metadata
            metadata = self.admin_client.describe_topics([topic])
            if topic not in metadata:
                return None
            
            topic_metadata = metadata[topic]
            
            # Get topic configuration
            resource = ConfigResource(ConfigResourceType.TOPIC, topic)
            configs = self.admin_client.describe_configs([resource])
            topic_config = configs.get(resource, {})
            
            return {
                "name": topic,
                "partitions": len(topic_metadata.partitions),
                "replication_factor": len(topic_metadata.partitions[0].replicas) if topic_metadata.partitions else 0,
                "config": {k: v.value for k, v in topic_config.items()},
            }
            
        except Exception as e:
            logger.error(f"Failed to get topic info: {e}")
            return None
    
    async def get_consumer_lag(self, event_type: str) -> Optional[Dict[str, int]]:
        """Get consumer lag for event type."""
        if event_type not in self.consumers:
            return None
        
        try:
            consumer = self.consumers[event_type]
            
            # Get committed offsets
            committed = await consumer.committed(consumer.assignment())
            
            # Get high water marks
            partition_metadata = {}
            for tp in consumer.assignment():
                high_water = await consumer.highwater(tp)
                committed_offset = committed.get(tp, 0)
                lag = high_water - committed_offset
                
                partition_metadata[f"partition_{tp.partition}"] = {
                    "committed_offset": committed_offset,
                    "high_water_mark": high_water,
                    "lag": lag,
                }
            
            return partition_metadata
            
        except Exception as e:
            logger.error(f"Failed to get consumer lag: {e}")
            return None