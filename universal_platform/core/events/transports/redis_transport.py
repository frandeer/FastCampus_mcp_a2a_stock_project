"""
Redis-based event transport implementation.
"""

import asyncio
import logging
import json
from typing import Any, Dict, List, Callable, Optional, Set
from datetime import datetime
from dataclasses import dataclass
import redis.asyncio as redis
from redis.asyncio.client import PubSub

from ..models import Event
from ..serialization import EventSerializer, JSONEventSerializer, SerializationConfig


logger = logging.getLogger(__name__)


@dataclass
class RedisTransportConfig:
    """Configuration for Redis transport."""
    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: Optional[str] = None
    username: Optional[str] = None
    ssl: bool = False
    ssl_cert_reqs: Optional[str] = None
    ssl_ca_certs: Optional[str] = None
    ssl_certfile: Optional[str] = None
    ssl_keyfile: Optional[str] = None
    
    # Connection pool settings
    max_connections: int = 20
    retry_on_timeout: bool = True
    health_check_interval: int = 30
    socket_connect_timeout: float = 5.0
    socket_timeout: float = 5.0
    
    # Event settings
    stream_maxlen: int = 10000
    consumer_group: str = "event_processors"
    consumer_name: str = "processor_1"
    batch_size: int = 10
    block_time_ms: int = 1000
    
    # Persistence settings
    enable_streams: bool = True
    enable_pub_sub: bool = True
    ttl_seconds: int = 86400  # 24 hours
    
    # Performance settings
    pipeline_size: int = 100
    compression_enabled: bool = False


class RedisTransport:
    """Redis-based event transport with streams and pub/sub."""
    
    def __init__(
        self,
        config: Optional[RedisTransportConfig] = None,
        serializer: Optional[EventSerializer] = None,
    ):
        self.config = config or RedisTransportConfig()
        self.serializer = serializer or JSONEventSerializer(SerializationConfig())
        
        # Redis connections
        self.redis: Optional[redis.Redis] = None
        self.pubsub: Optional[PubSub] = None
        
        # State
        self.running = False
        self.subscribers: Dict[str, List[Callable]] = {}
        self.subscribed_channels: Set[str] = set()
        
        # Background tasks
        self._pubsub_task: Optional[asyncio.Task] = None
        self._stream_tasks: List[asyncio.Task] = []
        self._health_check_task: Optional[asyncio.Task] = None
        
        # Metrics
        self._metrics = {
            "events_published": 0,
            "events_received": 0,
            "events_failed": 0,
            "connection_errors": 0,
            "last_heartbeat": None,
        }
        
        logger.info("RedisTransport initialized")
    
    async def start(self) -> None:
        """Start the Redis transport."""
        if self.running:
            return
        
        try:
            # Create Redis connection
            self.redis = redis.Redis(
                host=self.config.host,
                port=self.config.port,
                db=self.config.db,
                password=self.config.password,
                username=self.config.username,
                ssl=self.config.ssl,
                ssl_cert_reqs=self.config.ssl_cert_reqs,
                ssl_ca_certs=self.config.ssl_ca_certs,
                ssl_certfile=self.config.ssl_certfile,
                ssl_keyfile=self.config.ssl_keyfile,
                max_connections=self.config.max_connections,
                retry_on_timeout=self.config.retry_on_timeout,
                socket_connect_timeout=self.config.socket_connect_timeout,
                socket_timeout=self.config.socket_timeout,
                decode_responses=False,  # We handle encoding ourselves
            )
            
            # Test connection
            await self.redis.ping()
            
            # Create pub/sub if enabled
            if self.config.enable_pub_sub:
                self.pubsub = self.redis.pubsub()
                self._pubsub_task = asyncio.create_task(self._pubsub_listener())
            
            # Create consumer groups for streams if enabled
            if self.config.enable_streams:
                await self._setup_consumer_groups()
            
            # Start health check
            self._health_check_task = asyncio.create_task(self._health_check_loop())
            
            self.running = True
            logger.info("RedisTransport started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start RedisTransport: {e}")
            await self.stop()
            raise
    
    async def stop(self) -> None:
        """Stop the Redis transport."""
        if not self.running:
            return
        
        self.running = False
        
        # Cancel background tasks
        if self._pubsub_task:
            self._pubsub_task.cancel()
            
        for task in self._stream_tasks:
            task.cancel()
            
        if self._health_check_task:
            self._health_check_task.cancel()
        
        # Wait for tasks to complete
        all_tasks = [self._pubsub_task] + self._stream_tasks + [self._health_check_task]
        await asyncio.gather(*[t for t in all_tasks if t], return_exceptions=True)
        
        # Close connections
        if self.pubsub:
            await self.pubsub.close()
        
        if self.redis:
            await self.redis.close()
        
        logger.info("RedisTransport stopped")
    
    async def publish(self, event: Event) -> bool:
        """Publish an event to Redis."""
        if not self.running or not self.redis:
            return False
        
        try:
            # Serialize event
            event_data = self.serializer.serialize(event)
            
            # Create pipeline for atomic operations
            pipe = self.redis.pipeline()
            
            # Publish to pub/sub if enabled
            if self.config.enable_pub_sub:
                channel = f"events:{event.event_type}"
                pipe.publish(channel, event_data)
            
            # Add to stream if enabled
            if self.config.enable_streams:
                stream_key = f"stream:events:{event.event_type}"
                fields = {
                    "event_id": event.event_id,
                    "data": event_data,
                    "timestamp": int(event.metadata.timestamp.timestamp() * 1000),
                }
                
                pipe.xadd(
                    stream_key,
                    fields,
                    maxlen=self.config.stream_maxlen,
                    approximate=True,
                )
                
                # Set TTL on stream
                pipe.expire(stream_key, self.config.ttl_seconds)
            
            # Execute pipeline
            await pipe.execute()
            
            # Update metrics
            self._metrics["events_published"] += 1
            
            logger.debug(f"Published event {event.event_id} to Redis")
            return True
            
        except Exception as e:
            logger.error(f"Failed to publish event {event.event_id}: {e}")
            self._metrics["events_failed"] += 1
            return False
    
    async def subscribe(self, event_type: str, handler: Callable[[Event], Any]) -> None:
        """Subscribe to events of a specific type."""
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        
        self.subscribers[event_type].append(handler)
        
        # Subscribe to pub/sub channel if enabled and not already subscribed
        if self.config.enable_pub_sub and self.pubsub:
            channel = f"events:{event_type}"
            if channel not in self.subscribed_channels:
                await self.pubsub.subscribe(channel)
                self.subscribed_channels.add(channel)
        
        # Start stream consumer if enabled
        if self.config.enable_streams:
            stream_key = f"stream:events:{event_type}"
            task = asyncio.create_task(self._stream_consumer(stream_key, event_type))
            self._stream_tasks.append(task)
        
        logger.info(f"Subscribed to {event_type}")
    
    async def unsubscribe(self, event_type: str, handler: Callable[[Event], Any]) -> None:
        """Unsubscribe from events."""
        if event_type in self.subscribers:
            try:
                self.subscribers[event_type].remove(handler)
                
                # If no more handlers, unsubscribe from channel
                if not self.subscribers[event_type]:
                    del self.subscribers[event_type]
                    
                    if self.config.enable_pub_sub and self.pubsub:
                        channel = f"events:{event_type}"
                        await self.pubsub.unsubscribe(channel)
                        self.subscribed_channels.discard(channel)
                
                logger.info(f"Unsubscribed from {event_type}")
                
            except ValueError:
                logger.warning(f"Handler not found for {event_type}")
    
    async def health_check(self) -> Dict[str, Any]:
        """Check Redis transport health."""
        if not self.redis:
            return {"status": "disconnected"}
        
        try:
            # Test connection
            await self.redis.ping()
            
            # Get Redis info
            info = await self.redis.info()
            
            return {
                "status": "healthy" if self.running else "stopped",
                "redis_version": info.get("redis_version"),
                "connected_clients": info.get("connected_clients"),
                "used_memory": info.get("used_memory"),
                "used_memory_human": info.get("used_memory_human"),
                "subscribed_channels": len(self.subscribed_channels),
                "active_stream_consumers": len(self._stream_tasks),
                "metrics": self._metrics.copy(),
            }
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            self._metrics["connection_errors"] += 1
            return {
                "status": "unhealthy",
                "error": str(e),
            }
    
    async def _setup_consumer_groups(self) -> None:
        """Set up consumer groups for event streams."""
        try:
            # This would set up consumer groups for existing streams
            # In practice, you'd query for existing streams and create groups
            
            # For now, we'll create groups as needed when processing streams
            pass
            
        except Exception as e:
            logger.error(f"Failed to setup consumer groups: {e}")
    
    async def _pubsub_listener(self) -> None:
        """Listen for pub/sub messages."""
        if not self.pubsub:
            return
        
        logger.info("Starting pub/sub listener")
        
        try:
            async for message in self.pubsub.listen():
                if not self.running:
                    break
                
                if message["type"] == "message":
                    await self._handle_pubsub_message(message)
                    
        except asyncio.CancelledError:
            logger.info("Pub/sub listener cancelled")
        except Exception as e:
            logger.error(f"Pub/sub listener error: {e}")
            self._metrics["connection_errors"] += 1
    
    async def _handle_pubsub_message(self, message: Dict[str, Any]) -> None:
        """Handle pub/sub message."""
        try:
            channel = message["channel"].decode()
            event_data = message["data"]
            
            # Extract event type from channel
            if channel.startswith("events:"):
                event_type = channel[7:]  # Remove "events:" prefix
                
                # Deserialize event
                event = self.serializer.deserialize(event_data)
                
                # Call handlers
                await self._call_handlers(event_type, event)
                
                self._metrics["events_received"] += 1
                
        except Exception as e:
            logger.error(f"Failed to handle pub/sub message: {e}")
            self._metrics["events_failed"] += 1
    
    async def _stream_consumer(self, stream_key: str, event_type: str) -> None:
        """Consume events from Redis stream."""
        if not self.redis:
            return
        
        logger.info(f"Starting stream consumer for {stream_key}")
        
        try:
            # Create consumer group if it doesn't exist
            try:
                await self.redis.xgroup_create(
                    stream_key,
                    self.config.consumer_group,
                    id="0",
                    mkstream=True,
                )
            except redis.ResponseError as e:
                if "BUSYGROUP" not in str(e):
                    raise
            
            # Start consuming
            while self.running:
                try:
                    # Read from stream
                    messages = await self.redis.xreadgroup(
                        self.config.consumer_group,
                        self.config.consumer_name,
                        {stream_key: ">"},
                        count=self.config.batch_size,
                        block=self.config.block_time_ms,
                    )
                    
                    for stream, msgs in messages:
                        for msg_id, fields in msgs:
                            await self._handle_stream_message(
                                stream_key,
                                msg_id,
                                fields,
                                event_type,
                            )
                            
                except asyncio.TimeoutError:
                    continue
                except Exception as e:
                    logger.error(f"Stream consumer error: {e}")
                    await asyncio.sleep(1)  # Brief pause before retry
                    
        except asyncio.CancelledError:
            logger.info(f"Stream consumer for {stream_key} cancelled")
        except Exception as e:
            logger.error(f"Stream consumer for {stream_key} failed: {e}")
    
    async def _handle_stream_message(
        self,
        stream_key: str,
        msg_id: bytes,
        fields: Dict[bytes, bytes],
        event_type: str,
    ) -> None:
        """Handle stream message."""
        try:
            # Extract event data
            event_data = fields.get(b"data")
            if not event_data:
                logger.warning(f"No event data in stream message {msg_id}")
                return
            
            # Deserialize event
            event = self.serializer.deserialize(event_data)
            
            # Call handlers
            await self._call_handlers(event_type, event)
            
            # Acknowledge message
            if self.redis:
                await self.redis.xack(
                    stream_key,
                    self.config.consumer_group,
                    msg_id,
                )
            
            self._metrics["events_received"] += 1
            
        except Exception as e:
            logger.error(f"Failed to handle stream message {msg_id}: {e}")
            self._metrics["events_failed"] += 1
    
    async def _call_handlers(self, event_type: str, event: Event) -> None:
        """Call all handlers for an event type."""
        handlers = self.subscribers.get(event_type, [])
        if not handlers:
            return
        
        # Call handlers concurrently
        tasks = []
        for handler in handlers:
            task = asyncio.create_task(self._call_handler(handler, event))
            tasks.append(task)
        
        # Wait for all handlers
        await asyncio.gather(*tasks, return_exceptions=True)
    
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
    
    async def _health_check_loop(self) -> None:
        """Background health check loop."""
        while self.running:
            try:
                await asyncio.sleep(self.config.health_check_interval)
                
                if self.redis:
                    await self.redis.ping()
                    self._metrics["last_heartbeat"] = datetime.utcnow()
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health check failed: {e}")
                self._metrics["connection_errors"] += 1
    
    async def get_stream_info(self, event_type: str) -> Optional[Dict[str, Any]]:
        """Get stream information."""
        if not self.redis:
            return None
        
        try:
            stream_key = f"stream:events:{event_type}"
            info = await self.redis.xinfo_stream(stream_key)
            return {
                "length": info.get("length"),
                "radix_tree_keys": info.get("radix-tree-keys"),
                "radix_tree_nodes": info.get("radix-tree-nodes"),
                "groups": info.get("groups"),
                "last_generated_id": info.get("last-generated-id"),
                "first_entry": info.get("first-entry"),
                "last_entry": info.get("last-entry"),
            }
            
        except Exception as e:
            logger.error(f"Failed to get stream info: {e}")
            return None
    
    async def get_pending_messages(self, event_type: str) -> List[Dict[str, Any]]:
        """Get pending messages for consumer group."""
        if not self.redis:
            return []
        
        try:
            stream_key = f"stream:events:{event_type}"
            pending = await self.redis.xpending_range(
                stream_key,
                self.config.consumer_group,
                min="-",
                max="+",
                count=100,
            )
            
            return [
                {
                    "message_id": msg["message_id"],
                    "consumer": msg["consumer"],
                    "time_since_delivered": msg["time_since_delivered"],
                    "delivery_count": msg["delivery_count"],
                }
                for msg in pending
            ]
            
        except Exception as e:
            logger.error(f"Failed to get pending messages: {e}")
            return []