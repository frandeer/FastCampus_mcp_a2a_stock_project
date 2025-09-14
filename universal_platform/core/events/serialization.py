"""
Event serialization and deserialization with multiple formats.
"""

import json
import pickle
import gzip
import base64
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union, Type
from datetime import datetime
from dataclasses import dataclass
from enum import Enum
import msgpack
import avro.schema
import avro.io
import io

from .models import Event, EventMetadata


logger = logging.getLogger(__name__)


class SerializationFormat(Enum):
    """Supported serialization formats."""
    JSON = "json"
    PICKLE = "pickle"
    MSGPACK = "msgpack"
    AVRO = "avro"
    PROTOBUF = "protobuf"


@dataclass
class SerializationConfig:
    """Configuration for event serialization."""
    format: SerializationFormat = SerializationFormat.JSON
    compression_enabled: bool = False
    compression_level: int = 6
    encryption_enabled: bool = False
    encryption_key: Optional[bytes] = None
    schema_validation: bool = False
    schema_registry_url: Optional[str] = None
    pretty_print: bool = False
    include_metadata: bool = True
    version: str = "1.0"


class EventSerializer(ABC):
    """Abstract base class for event serializers."""
    
    @abstractmethod
    def serialize(self, event: Event) -> bytes:
        """Serialize event to bytes."""
        pass
    
    @abstractmethod
    def deserialize(self, data: bytes) -> Event:
        """Deserialize bytes to event."""
        pass
    
    @abstractmethod
    def get_content_type(self) -> str:
        """Get content type for serialized data."""
        pass


class JSONEventSerializer(EventSerializer):
    """JSON-based event serializer."""
    
    def __init__(self, config: SerializationConfig):
        self.config = config
    
    def serialize(self, event: Event) -> bytes:
        """Serialize event to JSON bytes."""
        try:
            # Convert event to dictionary
            event_dict = self._event_to_dict(event)
            
            # Serialize to JSON
            if self.config.pretty_print:
                json_str = json.dumps(event_dict, indent=2, default=self._json_serializer)
            else:
                json_str = json.dumps(event_dict, separators=(',', ':'), default=self._json_serializer)
            
            data = json_str.encode('utf-8')
            
            # Apply compression if enabled
            if self.config.compression_enabled:
                data = gzip.compress(data, compresslevel=self.config.compression_level)
            
            return data
            
        except Exception as e:
            logger.error(f"Failed to serialize event {event.event_id}: {e}")
            raise
    
    def deserialize(self, data: bytes) -> Event:
        """Deserialize JSON bytes to event."""
        try:
            # Decompress if needed
            if self.config.compression_enabled:
                data = gzip.decompress(data)
            
            # Parse JSON
            json_str = data.decode('utf-8')
            event_dict = json.loads(json_str)
            
            # Convert to event
            return self._dict_to_event(event_dict)
            
        except Exception as e:
            logger.error(f"Failed to deserialize event data: {e}")
            raise
    
    def get_content_type(self) -> str:
        """Get content type for JSON."""
        if self.config.compression_enabled:
            return "application/json+gzip"
        return "application/json"
    
    def _event_to_dict(self, event: Event) -> Dict[str, Any]:
        """Convert event to dictionary."""
        event_dict = {
            "format_version": self.config.version,
            "event_type": event.event_type,
            "data": event.data,
        }
        
        if self.config.include_metadata:
            event_dict["metadata"] = event.metadata.to_dict()
        
        return event_dict
    
    def _dict_to_event(self, event_dict: Dict[str, Any]) -> Event:
        """Convert dictionary to event."""
        metadata = EventMetadata()
        if "metadata" in event_dict:
            metadata = EventMetadata.from_dict(event_dict["metadata"])
        
        return Event(
            event_type=event_dict["event_type"],
            data=event_dict["data"],
            metadata=metadata,
        )
    
    def _json_serializer(self, obj: Any) -> Any:
        """Custom JSON serializer for complex types."""
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif hasattr(obj, '__dict__'):
            return obj.__dict__
        else:
            return str(obj)


class PickleEventSerializer(EventSerializer):
    """Pickle-based event serializer."""
    
    def __init__(self, config: SerializationConfig):
        self.config = config
    
    def serialize(self, event: Event) -> bytes:
        """Serialize event using pickle."""
        try:
            data = pickle.dumps(event, protocol=pickle.HIGHEST_PROTOCOL)
            
            if self.config.compression_enabled:
                data = gzip.compress(data, compresslevel=self.config.compression_level)
            
            return data
            
        except Exception as e:
            logger.error(f"Failed to pickle serialize event {event.event_id}: {e}")
            raise
    
    def deserialize(self, data: bytes) -> Event:
        """Deserialize pickle bytes to event."""
        try:
            if self.config.compression_enabled:
                data = gzip.decompress(data)
            
            return pickle.loads(data)
            
        except Exception as e:
            logger.error(f"Failed to pickle deserialize event data: {e}")
            raise
    
    def get_content_type(self) -> str:
        """Get content type for pickle."""
        if self.config.compression_enabled:
            return "application/pickle+gzip"
        return "application/pickle"


class MsgPackEventSerializer(EventSerializer):
    """MessagePack-based event serializer."""
    
    def __init__(self, config: SerializationConfig):
        self.config = config
    
    def serialize(self, event: Event) -> bytes:
        """Serialize event using MessagePack."""
        try:
            # Convert event to dictionary
            event_dict = {
                "event_type": event.event_type,
                "data": event.data,
                "metadata": event.metadata.to_dict() if self.config.include_metadata else None,
            }
            
            data = msgpack.packb(event_dict, default=self._msgpack_encoder, use_bin_type=True)
            
            if self.config.compression_enabled:
                data = gzip.compress(data, compresslevel=self.config.compression_level)
            
            return data
            
        except Exception as e:
            logger.error(f"Failed to msgpack serialize event {event.event_id}: {e}")
            raise
    
    def deserialize(self, data: bytes) -> Event:
        """Deserialize MessagePack bytes to event."""
        try:
            if self.config.compression_enabled:
                data = gzip.decompress(data)
            
            event_dict = msgpack.unpackb(data, raw=False, timestamp=3)
            
            metadata = EventMetadata()
            if event_dict.get("metadata"):
                metadata = EventMetadata.from_dict(event_dict["metadata"])
            
            return Event(
                event_type=event_dict["event_type"],
                data=event_dict["data"],
                metadata=metadata,
            )
            
        except Exception as e:
            logger.error(f"Failed to msgpack deserialize event data: {e}")
            raise
    
    def get_content_type(self) -> str:
        """Get content type for MessagePack."""
        if self.config.compression_enabled:
            return "application/msgpack+gzip"
        return "application/msgpack"
    
    def _msgpack_encoder(self, obj: Any) -> Any:
        """Custom MessagePack encoder."""
        if isinstance(obj, datetime):
            return obj.timestamp()
        elif hasattr(obj, '__dict__'):
            return obj.__dict__
        else:
            return str(obj)


class AvroEventSerializer(EventSerializer):
    """Avro-based event serializer with schema evolution."""
    
    def __init__(self, config: SerializationConfig, schema: Optional[str] = None):
        self.config = config
        self.schema = self._get_schema(schema)
        
    def serialize(self, event: Event) -> bytes:
        """Serialize event using Avro."""
        try:
            # Convert event to Avro-compatible format
            avro_record = {
                "event_id": event.event_id,
                "event_type": event.event_type,
                "data": json.dumps(event.data),
                "timestamp": int(event.metadata.timestamp.timestamp() * 1000),
                "version": event.metadata.version,
                "correlation_id": event.metadata.correlation_id,
                "source": event.metadata.source,
            }
            
            # Serialize using Avro
            writer = avro.io.DatumWriter(self.schema)
            bytes_writer = io.BytesIO()
            encoder = avro.io.BinaryEncoder(bytes_writer)
            writer.write(avro_record, encoder)
            
            data = bytes_writer.getvalue()
            
            if self.config.compression_enabled:
                data = gzip.compress(data, compresslevel=self.config.compression_level)
            
            return data
            
        except Exception as e:
            logger.error(f"Failed to avro serialize event {event.event_id}: {e}")
            raise
    
    def deserialize(self, data: bytes) -> Event:
        """Deserialize Avro bytes to event."""
        try:
            if self.config.compression_enabled:
                data = gzip.decompress(data)
            
            # Deserialize using Avro
            reader = avro.io.DatumReader(self.schema)
            bytes_reader = io.BytesIO(data)
            decoder = avro.io.BinaryDecoder(bytes_reader)
            avro_record = reader.read(decoder)
            
            # Convert back to event
            metadata = EventMetadata(
                event_id=avro_record["event_id"],
                timestamp=datetime.fromtimestamp(avro_record["timestamp"] / 1000),
                version=avro_record["version"],
                correlation_id=avro_record.get("correlation_id"),
                source=avro_record.get("source"),
            )
            
            return Event(
                event_type=avro_record["event_type"],
                data=json.loads(avro_record["data"]),
                metadata=metadata,
            )
            
        except Exception as e:
            logger.error(f"Failed to avro deserialize event data: {e}")
            raise
    
    def get_content_type(self) -> str:
        """Get content type for Avro."""
        if self.config.compression_enabled:
            return "application/avro+gzip"
        return "application/avro"
    
    def _get_schema(self, schema_str: Optional[str]) -> avro.schema.Schema:
        """Get or create Avro schema."""
        if schema_str:
            return avro.schema.parse(schema_str)
        
        # Default event schema
        default_schema = """
        {
            "type": "record",
            "name": "Event",
            "fields": [
                {"name": "event_id", "type": "string"},
                {"name": "event_type", "type": "string"},
                {"name": "data", "type": "string"},
                {"name": "timestamp", "type": "long"},
                {"name": "version", "type": "int"},
                {"name": "correlation_id", "type": ["null", "string"], "default": null},
                {"name": "source", "type": ["null", "string"], "default": null}
            ]
        }
        """
        return avro.schema.parse(default_schema)


class EventSerializerFactory:
    """Factory for creating event serializers."""
    
    @staticmethod
    def create_serializer(config: SerializationConfig) -> EventSerializer:
        """Create serializer based on configuration."""
        if config.format == SerializationFormat.JSON:
            return JSONEventSerializer(config)
        elif config.format == SerializationFormat.PICKLE:
            return PickleEventSerializer(config)
        elif config.format == SerializationFormat.MSGPACK:
            return MsgPackEventSerializer(config)
        elif config.format == SerializationFormat.AVRO:
            return AvroEventSerializer(config)
        else:
            raise ValueError(f"Unsupported serialization format: {config.format}")


class VersionedEventSerializer:
    """Versioned event serializer with migration support."""
    
    def __init__(self):
        self.serializers: Dict[str, EventSerializer] = {}
        self.migrations: Dict[str, Callable] = {}
        self.current_version = "1.0"
    
    def register_serializer(self, version: str, serializer: EventSerializer) -> None:
        """Register serializer for specific version."""
        self.serializers[version] = serializer
        logger.info(f"Registered serializer for version {version}")
    
    def register_migration(self, from_version: str, to_version: str, migration_func: Callable) -> None:
        """Register migration function between versions."""
        migration_key = f"{from_version}->{to_version}"
        self.migrations[migration_key] = migration_func
        logger.info(f"Registered migration {migration_key}")
    
    def serialize(self, event: Event) -> bytes:
        """Serialize event using current version."""
        serializer = self.serializers.get(self.current_version)
        if not serializer:
            raise ValueError(f"No serializer registered for version {self.current_version}")
        
        return serializer.serialize(event)
    
    def deserialize(self, data: bytes, version: Optional[str] = None) -> Event:
        """Deserialize event with automatic migration."""
        # Try to detect version if not provided
        if version is None:
            version = self._detect_version(data)
        
        # Get serializer for version
        serializer = self.serializers.get(version)
        if not serializer:
            raise ValueError(f"No serializer registered for version {version}")
        
        # Deserialize event
        event = serializer.deserialize(data)
        
        # Migrate if needed
        if version != self.current_version:
            event = self._migrate_event(event, version, self.current_version)
        
        return event
    
    def _detect_version(self, data: bytes) -> str:
        """Detect version from serialized data."""
        # This is a simplified implementation
        # In practice, you might embed version info in the data
        try:
            # Try to parse as JSON and look for version field
            if data.startswith(b'{'):
                json_data = json.loads(data.decode('utf-8'))
                return json_data.get("format_version", "1.0")
        except:
            pass
        
        # Default to oldest version
        return "1.0"
    
    def _migrate_event(self, event: Event, from_version: str, to_version: str) -> Event:
        """Migrate event between versions."""
        current_version = from_version
        migrated_event = event
        
        # Apply migrations step by step
        while current_version != to_version:
            next_version = self._find_next_migration_version(current_version, to_version)
            migration_key = f"{current_version}->{next_version}"
            
            if migration_key not in self.migrations:
                raise ValueError(f"No migration path from {current_version} to {next_version}")
            
            migration_func = self.migrations[migration_key]
            migrated_event = migration_func(migrated_event)
            current_version = next_version
        
        return migrated_event
    
    def _find_next_migration_version(self, current: str, target: str) -> str:
        """Find next version in migration path."""
        # This is a simplified implementation
        # In practice, you'd build a migration graph
        available_migrations = [
            key for key in self.migrations.keys() 
            if key.startswith(f"{current}->")
        ]
        
        if not available_migrations:
            raise ValueError(f"No migrations available from version {current}")
        
        # Return the first available migration
        return available_migrations[0].split("->")[1]


class SchemaRegistry:
    """Registry for event schemas."""
    
    def __init__(self):
        self.schemas: Dict[str, Dict[str, Any]] = {}
        self.compatibility_rules: Dict[str, str] = {}
    
    def register_schema(
        self,
        event_type: str,
        version: str,
        schema: Dict[str, Any],
        compatibility: str = "backward",
    ) -> None:
        """Register schema for event type."""
        schema_key = f"{event_type}:{version}"
        self.schemas[schema_key] = schema
        self.compatibility_rules[schema_key] = compatibility
        
        logger.info(f"Registered schema for {schema_key}")
    
    def get_schema(self, event_type: str, version: str = "latest") -> Optional[Dict[str, Any]]:
        """Get schema for event type and version."""
        if version == "latest":
            # Find latest version
            matching_schemas = [
                key for key in self.schemas.keys() 
                if key.startswith(f"{event_type}:")
            ]
            if not matching_schemas:
                return None
            
            # Sort by version and get latest
            latest_key = sorted(matching_schemas)[-1]
            return self.schemas[latest_key]
        
        schema_key = f"{event_type}:{version}"
        return self.schemas.get(schema_key)
    
    def validate_event(self, event: Event, schema: Optional[Dict[str, Any]] = None) -> bool:
        """Validate event against schema."""
        if schema is None:
            schema = self.get_schema(event.event_type)
        
        if not schema:
            logger.warning(f"No schema found for event type: {event.event_type}")
            return True  # Allow events without schemas
        
        try:
            # Basic validation
            required_fields = schema.get("required", [])
            for field in required_fields:
                if field not in event.data:
                    logger.error(f"Required field '{field}' missing from event {event.event_id}")
                    return False
            
            # Type validation
            field_types = schema.get("properties", {})
            for field, type_info in field_types.items():
                if field in event.data:
                    expected_type = type_info.get("type")
                    actual_value = event.data[field]
                    
                    if not self._validate_type(actual_value, expected_type):
                        logger.error(f"Field '{field}' type mismatch in event {event.event_id}")
                        return False
            
            return True
            
        except Exception as e:
            logger.error(f"Schema validation error for event {event.event_id}: {e}")
            return False
    
    def _validate_type(self, value: Any, expected_type: str) -> bool:
        """Validate value type."""
        type_mapping = {
            "string": str,
            "integer": int,
            "number": (int, float),
            "boolean": bool,
            "array": list,
            "object": dict,
        }
        
        expected_python_type = type_mapping.get(expected_type)
        if expected_python_type:
            return isinstance(value, expected_python_type)
        
        return True  # Unknown type, allow it


# Default serializer instance
default_serializer = JSONEventSerializer(SerializationConfig())