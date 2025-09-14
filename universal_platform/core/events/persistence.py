"""
Event sourcing and event store implementation.
"""

import asyncio
import logging
import json
import gzip
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union, Iterator, AsyncIterator
from datetime import datetime, timedelta
from pathlib import Path
import sqlite3
import aiosqlite
from contextlib import asynccontextmanager
import pickle
import hashlib

from .models import Event, EventMetadata, EventStatus, EventError, DeadLetterEvent
from .serialization import EventSerializer


logger = logging.getLogger(__name__)


@dataclass
class EventStoreConfig:
    """Configuration for event store."""
    connection_string: str = "sqlite:///events.db"
    batch_size: int = 100
    compression_enabled: bool = True
    encryption_enabled: bool = False
    snapshot_frequency: int = 1000
    retention_days: int = 365
    auto_vacuum: bool = True
    write_buffer_size: int = 1000
    read_cache_size: int = 500
    backup_enabled: bool = True
    backup_frequency_hours: int = 24


@dataclass
class EventSnapshot:
    """Event snapshot for optimization."""
    aggregate_id: str
    aggregate_type: str
    version: int
    data: Dict[str, Any]
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert snapshot to dictionary."""
        return {
            "aggregate_id": self.aggregate_id,
            "aggregate_type": self.aggregate_type,
            "version": self.version,
            "data": self.data,
            "created_at": self.created_at.isoformat(),
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EventSnapshot":
        """Create snapshot from dictionary."""
        return cls(
            aggregate_id=data["aggregate_id"],
            aggregate_type=data["aggregate_type"],
            version=data["version"],
            data=data["data"],
            created_at=datetime.fromisoformat(data["created_at"]),
        )


class EventStore(ABC):
    """Abstract event store interface."""
    
    @abstractmethod
    async def store_event(self, event: Event) -> bool:
        """Store an event."""
        pass
    
    @abstractmethod
    async def store_events(self, events: List[Event]) -> int:
        """Store multiple events."""
        pass
    
    @abstractmethod
    async def get_event(self, event_id: str) -> Optional[Event]:
        """Get event by ID."""
        pass
    
    @abstractmethod
    async def get_events(
        self,
        aggregate_id: Optional[str] = None,
        event_types: Optional[List[str]] = None,
        from_timestamp: Optional[datetime] = None,
        to_timestamp: Optional[datetime] = None,
        limit: Optional[int] = None,
        offset: int = 0,
        correlation_id: Optional[str] = None,
    ) -> List[Event]:
        """Get events with filtering."""
        pass
    
    @abstractmethod
    async def get_events_stream(
        self,
        aggregate_id: Optional[str] = None,
        event_types: Optional[List[str]] = None,
        from_timestamp: Optional[datetime] = None,
        to_timestamp: Optional[datetime] = None,
        correlation_id: Optional[str] = None,
    ) -> AsyncIterator[Event]:
        """Get events as async stream."""
        pass
    
    @abstractmethod
    async def store_snapshot(self, snapshot: EventSnapshot) -> bool:
        """Store event snapshot."""
        pass
    
    @abstractmethod
    async def get_snapshot(self, aggregate_id: str) -> Optional[EventSnapshot]:
        """Get latest snapshot for aggregate."""
        pass
    
    @abstractmethod
    async def cleanup_old_events(self, before: datetime) -> int:
        """Clean up old events."""
        pass


class SQLiteEventStore(EventStore):
    """SQLite-based event store implementation."""
    
    def __init__(self, config: EventStoreConfig, serializer: Optional[EventSerializer] = None):
        self.config = config
        self.serializer = serializer or EventSerializer()
        self.db_path = self._parse_connection_string(config.connection_string)
        self._connection_pool: List[aiosqlite.Connection] = []
        self._pool_lock = asyncio.Lock()
        self._write_buffer: List[Event] = []
        self._write_lock = asyncio.Lock()
        
        logger.info(f"SQLiteEventStore initialized with database: {self.db_path}")
    
    def _parse_connection_string(self, connection_string: str) -> str:
        """Parse SQLite connection string."""
        if connection_string.startswith("sqlite:///"):
            return connection_string[10:]  # Remove sqlite:/// prefix
        return connection_string
    
    async def initialize(self) -> None:
        """Initialize database schema."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    event_id TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    aggregate_id TEXT,
                    correlation_id TEXT,
                    causation_id TEXT,
                    version INTEGER NOT NULL,
                    timestamp DATETIME NOT NULL,
                    data BLOB NOT NULL,
                    metadata TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            await db.execute("""
                CREATE TABLE IF NOT EXISTS snapshots (
                    aggregate_id TEXT PRIMARY KEY,
                    aggregate_type TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    data BLOB NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            await db.execute("""
                CREATE TABLE IF NOT EXISTS dead_letter_queue (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    original_event BLOB NOT NULL,
                    error_info TEXT NOT NULL,
                    attempt_count INTEGER NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create indexes
            await db.execute("CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_events_aggregate ON events(aggregate_id)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_events_correlation ON events(correlation_id)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_events_created_at ON events(created_at)")
            
            await db.commit()
    
    @asynccontextmanager
    async def get_connection(self):
        """Get database connection from pool."""
        async with self._pool_lock:
            if self._connection_pool:
                conn = self._connection_pool.pop()
            else:
                conn = await aiosqlite.connect(self.db_path)
        
        try:
            yield conn
        finally:
            async with self._pool_lock:
                if len(self._connection_pool) < 10:  # Pool size limit
                    self._connection_pool.append(conn)
                else:
                    await conn.close()
    
    async def store_event(self, event: Event) -> bool:
        """Store a single event."""
        async with self._write_lock:
            self._write_buffer.append(event)
            
            # Flush buffer if it reaches batch size
            if len(self._write_buffer) >= self.config.batch_size:
                await self._flush_write_buffer()
        
        return True
    
    async def store_events(self, events: List[Event]) -> int:
        """Store multiple events."""
        async with self._write_lock:
            self._write_buffer.extend(events)
            
            # Always flush when storing multiple events
            await self._flush_write_buffer()
        
        return len(events)
    
    async def _flush_write_buffer(self) -> None:
        """Flush write buffer to database."""
        if not self._write_buffer:
            return
        
        events_to_write = self._write_buffer.copy()
        self._write_buffer.clear()
        
        async with self.get_connection() as db:
            try:
                await db.execute("BEGIN TRANSACTION")
                
                for event in events_to_write:
                    # Serialize event data
                    data_blob = await self._serialize_event_data(event)
                    metadata_json = json.dumps(event.metadata.to_dict())
                    
                    await db.execute("""
                        INSERT OR REPLACE INTO events (
                            event_id, event_type, aggregate_id, correlation_id,
                            causation_id, version, timestamp, data, metadata
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        event.event_id,
                        event.event_type,
                        event.data.get("aggregate_id"),  # Extract from data if present
                        event.metadata.correlation_id,
                        event.metadata.causation_id,
                        event.metadata.version,
                        event.metadata.timestamp,
                        data_blob,
                        metadata_json,
                    ))
                
                await db.commit()
                logger.debug(f"Stored {len(events_to_write)} events to database")
                
            except Exception as e:
                await db.rollback()
                logger.error(f"Failed to store events: {e}")
                # Re-add events to buffer for retry
                self._write_buffer.extend(events_to_write)
                raise
    
    async def get_event(self, event_id: str) -> Optional[Event]:
        """Get event by ID."""
        async with self.get_connection() as db:
            cursor = await db.execute(
                "SELECT data, metadata FROM events WHERE event_id = ?",
                (event_id,)
            )
            row = await cursor.fetchone()
            
            if row:
                return await self._deserialize_event(row[0], row[1])
            return None
    
    async def get_events(
        self,
        aggregate_id: Optional[str] = None,
        event_types: Optional[List[str]] = None,
        from_timestamp: Optional[datetime] = None,
        to_timestamp: Optional[datetime] = None,
        limit: Optional[int] = None,
        offset: int = 0,
        correlation_id: Optional[str] = None,
    ) -> List[Event]:
        """Get events with filtering."""
        query = "SELECT data, metadata FROM events WHERE 1=1"
        params = []
        
        if aggregate_id:
            query += " AND aggregate_id = ?"
            params.append(aggregate_id)
        
        if event_types:
            placeholders = ",".join("?" * len(event_types))
            query += f" AND event_type IN ({placeholders})"
            params.extend(event_types)
        
        if from_timestamp:
            query += " AND timestamp >= ?"
            params.append(from_timestamp)
        
        if to_timestamp:
            query += " AND timestamp <= ?"
            params.append(to_timestamp)
        
        if correlation_id:
            query += " AND correlation_id = ?"
            params.append(correlation_id)
        
        query += " ORDER BY timestamp ASC"
        
        if limit:
            query += " LIMIT ?"
            params.append(limit)
        
        if offset:
            query += " OFFSET ?"
            params.append(offset)
        
        async with self.get_connection() as db:
            cursor = await db.execute(query, params)
            rows = await cursor.fetchall()
            
            events = []
            for row in rows:
                event = await self._deserialize_event(row[0], row[1])
                if event:
                    events.append(event)
            
            return events
    
    async def get_events_stream(
        self,
        aggregate_id: Optional[str] = None,
        event_types: Optional[List[str]] = None,
        from_timestamp: Optional[datetime] = None,
        to_timestamp: Optional[datetime] = None,
        correlation_id: Optional[str] = None,
    ) -> AsyncIterator[Event]:
        """Get events as async stream."""
        batch_size = 100
        offset = 0
        
        while True:
            events = await self.get_events(
                aggregate_id=aggregate_id,
                event_types=event_types,
                from_timestamp=from_timestamp,
                to_timestamp=to_timestamp,
                limit=batch_size,
                offset=offset,
                correlation_id=correlation_id,
            )
            
            if not events:
                break
            
            for event in events:
                yield event
            
            if len(events) < batch_size:
                break
            
            offset += batch_size
    
    async def store_snapshot(self, snapshot: EventSnapshot) -> bool:
        """Store event snapshot."""
        try:
            data_blob = await self._serialize_snapshot_data(snapshot)
            
            async with self.get_connection() as db:
                await db.execute("""
                    INSERT OR REPLACE INTO snapshots (
                        aggregate_id, aggregate_type, version, data
                    ) VALUES (?, ?, ?, ?)
                """, (
                    snapshot.aggregate_id,
                    snapshot.aggregate_type,
                    snapshot.version,
                    data_blob,
                ))
                await db.commit()
            
            logger.debug(f"Stored snapshot for aggregate {snapshot.aggregate_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to store snapshot: {e}")
            return False
    
    async def get_snapshot(self, aggregate_id: str) -> Optional[EventSnapshot]:
        """Get latest snapshot for aggregate."""
        async with self.get_connection() as db:
            cursor = await db.execute("""
                SELECT aggregate_type, version, data, created_at 
                FROM snapshots 
                WHERE aggregate_id = ?
                ORDER BY version DESC 
                LIMIT 1
            """, (aggregate_id,))
            row = await cursor.fetchone()
            
            if row:
                data = await self._deserialize_snapshot_data(row[2])
                return EventSnapshot(
                    aggregate_id=aggregate_id,
                    aggregate_type=row[0],
                    version=row[1],
                    data=data,
                    created_at=datetime.fromisoformat(row[3]),
                )
            return None
    
    async def cleanup_old_events(self, before: datetime) -> int:
        """Clean up old events."""
        async with self.get_connection() as db:
            cursor = await db.execute(
                "DELETE FROM events WHERE created_at < ?",
                (before,)
            )
            await db.commit()
            return cursor.rowcount
    
    async def _serialize_event_data(self, event: Event) -> bytes:
        """Serialize event data."""
        data = {
            "event_type": event.event_type,
            "data": event.data,
            "metadata": event.metadata.to_dict(),
        }
        
        serialized = json.dumps(data, default=str).encode('utf-8')
        
        if self.config.compression_enabled:
            serialized = gzip.compress(serialized)
        
        return serialized
    
    async def _deserialize_event(self, data_blob: bytes, metadata_json: str) -> Optional[Event]:
        """Deserialize event from database."""
        try:
            if self.config.compression_enabled:
                data_blob = gzip.decompress(data_blob)
            
            data = json.loads(data_blob.decode('utf-8'))
            metadata_dict = json.loads(metadata_json)
            
            metadata = EventMetadata.from_dict(metadata_dict)
            return Event(
                event_type=data["event_type"],
                data=data["data"],
                metadata=metadata,
            )
            
        except Exception as e:
            logger.error(f"Failed to deserialize event: {e}")
            return None
    
    async def _serialize_snapshot_data(self, snapshot: EventSnapshot) -> bytes:
        """Serialize snapshot data."""
        data = snapshot.to_dict()
        serialized = json.dumps(data, default=str).encode('utf-8')
        
        if self.config.compression_enabled:
            serialized = gzip.compress(serialized)
        
        return serialized
    
    async def _deserialize_snapshot_data(self, data_blob: bytes) -> Dict[str, Any]:
        """Deserialize snapshot data."""
        if self.config.compression_enabled:
            data_blob = gzip.decompress(data_blob)
        
        return json.loads(data_blob.decode('utf-8'))["data"]
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get event store statistics."""
        async with self.get_connection() as db:
            # Event count
            cursor = await db.execute("SELECT COUNT(*) FROM events")
            event_count = (await cursor.fetchone())[0]
            
            # Event types
            cursor = await db.execute("""
                SELECT event_type, COUNT(*) 
                FROM events 
                GROUP BY event_type 
                ORDER BY COUNT(*) DESC
            """)
            event_types = await cursor.fetchall()
            
            # Snapshot count
            cursor = await db.execute("SELECT COUNT(*) FROM snapshots")
            snapshot_count = (await cursor.fetchone())[0]
            
            # Database size
            cursor = await db.execute("SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size()")
            db_size = (await cursor.fetchone())[0]
            
            return {
                "total_events": event_count,
                "total_snapshots": snapshot_count,
                "database_size_bytes": db_size,
                "event_types": dict(event_types),
                "write_buffer_size": len(self._write_buffer),
            }


class EventSourcing:
    """Event sourcing implementation for aggregates."""
    
    def __init__(self, event_store: EventStore):
        self.event_store = event_store
        self._aggregate_cache: Dict[str, Any] = {}
        self._cache_lock = asyncio.Lock()
    
    async def save_events(
        self,
        aggregate_id: str,
        events: List[Event],
        expected_version: Optional[int] = None,
    ) -> bool:
        """Save events for an aggregate."""
        try:
            # Check version if provided (optimistic concurrency)
            if expected_version is not None:
                current_version = await self._get_aggregate_version(aggregate_id)
                if current_version != expected_version:
                    raise Exception(f"Concurrency conflict: expected {expected_version}, got {current_version}")
            
            # Add aggregate_id to event data
            for event in events:
                event.data["aggregate_id"] = aggregate_id
            
            # Store events
            stored_count = await self.event_store.store_events(events)
            
            # Clear cache for this aggregate
            async with self._cache_lock:
                self._aggregate_cache.pop(aggregate_id, None)
            
            return stored_count == len(events)
            
        except Exception as e:
            logger.error(f"Failed to save events for aggregate {aggregate_id}: {e}")
            return False
    
    async def load_aggregate(
        self,
        aggregate_id: str,
        aggregate_class: type,
        up_to_version: Optional[int] = None,
    ) -> Optional[Any]:
        """Load aggregate from events."""
        # Check cache first
        async with self._cache_lock:
            if aggregate_id in self._aggregate_cache:
                cached_aggregate = self._aggregate_cache[aggregate_id]
                if up_to_version is None or cached_aggregate.version <= up_to_version:
                    return cached_aggregate
        
        try:
            # Try to load from snapshot first
            snapshot = await self.event_store.get_snapshot(aggregate_id)
            
            if snapshot:
                # Create aggregate from snapshot
                aggregate = aggregate_class.from_snapshot(snapshot)
                start_version = snapshot.version + 1
            else:
                # Create new aggregate
                aggregate = aggregate_class(aggregate_id)
                start_version = 1
            
            # Load events after snapshot
            events = await self.event_store.get_events(
                aggregate_id=aggregate_id,
                from_timestamp=snapshot.created_at if snapshot else None,
            )
            
            # Filter events by version if needed
            if up_to_version is not None:
                events = [e for e in events if e.metadata.version <= up_to_version]
            
            # Apply events to aggregate
            for event in events:
                if hasattr(aggregate, 'apply_event'):
                    aggregate.apply_event(event)
            
            # Cache the aggregate
            async with self._cache_lock:
                self._aggregate_cache[aggregate_id] = aggregate
            
            return aggregate
            
        except Exception as e:
            logger.error(f"Failed to load aggregate {aggregate_id}: {e}")
            return None
    
    async def create_snapshot(
        self,
        aggregate_id: str,
        aggregate: Any,
    ) -> bool:
        """Create snapshot for aggregate."""
        try:
            if hasattr(aggregate, 'to_snapshot'):
                snapshot_data = aggregate.to_snapshot()
            else:
                # Default serialization
                snapshot_data = aggregate.__dict__.copy()
            
            snapshot = EventSnapshot(
                aggregate_id=aggregate_id,
                aggregate_type=type(aggregate).__name__,
                version=getattr(aggregate, 'version', 0),
                data=snapshot_data,
            )
            
            return await self.event_store.store_snapshot(snapshot)
            
        except Exception as e:
            logger.error(f"Failed to create snapshot for aggregate {aggregate_id}: {e}")
            return False
    
    async def _get_aggregate_version(self, aggregate_id: str) -> int:
        """Get current version of aggregate."""
        events = await self.event_store.get_events(
            aggregate_id=aggregate_id,
            limit=1,
        )
        
        if events:
            return events[-1].metadata.version
        return 0
    
    async def replay_events(
        self,
        aggregate_id: str,
        from_version: int = 1,
        to_version: Optional[int] = None,
    ) -> AsyncIterator[Event]:
        """Replay events for debugging/analysis."""
        async for event in self.event_store.get_events_stream(aggregate_id=aggregate_id):
            if event.metadata.version >= from_version:
                if to_version is None or event.metadata.version <= to_version:
                    yield event
                elif event.metadata.version > to_version:
                    break


class DeadLetterQueue:
    """Dead letter queue for failed events."""
    
    def __init__(self, event_store: EventStore):
        self.event_store = event_store
    
    async def add_dead_letter(self, event: Event, error: EventError) -> bool:
        """Add event to dead letter queue."""
        dead_letter = DeadLetterEvent(
            original_event=event,
            error=error,
            total_attempts=event.metadata.retry_count + 1,
        )
        
        # Store in database (this would need to be implemented in the event store)
        try:
            # This is a simplified implementation
            # In practice, you'd want a dedicated dead letter table
            dead_letter_event = Event(
                event_type="system.dead_letter",
                data=dead_letter.to_dict(),
                metadata=EventMetadata(
                    correlation_id=event.metadata.correlation_id,
                    source="dead_letter_queue",
                ),
            )
            
            await self.event_store.store_event(dead_letter_event)
            logger.warning(f"Added event {event.event_id} to dead letter queue")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add event to dead letter queue: {e}")
            return False
    
    async def get_dead_letters(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> List[DeadLetterEvent]:
        """Get dead letter events."""
        events = await self.event_store.get_events(
            event_types=["system.dead_letter"],
            limit=limit,
            offset=offset,
        )
        
        dead_letters = []
        for event in events:
            try:
                original_event_data = event.data["original_event"]
                original_event = Event.from_dict(original_event_data)
                
                error_data = event.data["error"]
                error = EventError.from_dict(error_data)
                
                dead_letter = DeadLetterEvent(
                    original_event=original_event,
                    error=error,
                    final_attempt_timestamp=datetime.fromisoformat(event.data["final_attempt_timestamp"]),
                    total_attempts=event.data["total_attempts"],
                )
                dead_letters.append(dead_letter)
                
            except Exception as e:
                logger.error(f"Failed to deserialize dead letter event: {e}")
        
        return dead_letters
    
    async def retry_dead_letter(self, dead_letter_event_id: str) -> bool:
        """Retry a dead letter event."""
        # Implementation would retrieve the dead letter and retry it
        # This is a placeholder
        logger.info(f"Retrying dead letter event: {dead_letter_event_id}")
        return True