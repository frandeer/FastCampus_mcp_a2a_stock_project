"""
Universal Platform Plugin Interfaces

Defines the core interfaces, contracts, and configuration classes that all plugins
must implement to integrate with the universal platform plugin system.

Features:
- Base plugin interface with lifecycle methods
- Configuration and metadata classes
- Event and communication interfaces
- Health monitoring interface
- Security and isolation contracts
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Type, Union, Callable
import asyncio


class PluginType(Enum):
    """Plugin type categories"""
    SERVICE = "service"
    MIDDLEWARE = "middleware"
    CONNECTOR = "connector"
    TRANSFORMER = "transformer"
    MONITOR = "monitor"
    SECURITY = "security"
    UI_COMPONENT = "ui_component"
    INTEGRATION = "integration"
    UTILITY = "utility"


class PluginPriority(Enum):
    """Plugin execution priority levels"""
    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3
    BACKGROUND = 4


class SecurityLevel(Enum):
    """Plugin security clearance levels"""
    UNRESTRICTED = "unrestricted"
    RESTRICTED = "restricted"
    SANDBOXED = "sandboxed"
    ISOLATED = "isolated"


@dataclass
class PluginMetadata:
    """
    Plugin metadata containing descriptive information and requirements.
    """
    name: str
    version: str
    description: str = ""
    author: str = ""
    homepage: str = ""
    license: str = ""
    plugin_type: PluginType = PluginType.UTILITY
    priority: PluginPriority = PluginPriority.NORMAL
    security_level: SecurityLevel = SecurityLevel.RESTRICTED
    
    # Dependencies and requirements
    dependencies: Dict[str, str] = field(default_factory=dict)
    python_requires: str = ">=3.8"
    platform_requires: List[str] = field(default_factory=list)
    
    # Capabilities and features
    provides: List[str] = field(default_factory=list)
    requires: List[str] = field(default_factory=list)
    optional_features: List[str] = field(default_factory=list)
    
    # Resource requirements
    max_memory_mb: int = 100
    max_cpu_percent: float = 10.0
    max_disk_mb: int = 50
    network_access: bool = False
    file_system_access: bool = False
    
    # Lifecycle and monitoring
    startup_timeout: float = 30.0
    shutdown_timeout: float = 10.0
    health_check_interval: float = 60.0
    auto_restart: bool = True
    
    # Tags and categorization
    tags: List[str] = field(default_factory=list)
    categories: List[str] = field(default_factory=list)
    
    # Compatibility
    min_platform_version: str = "1.0.0"
    max_platform_version: Optional[str] = None
    
    def __post_init__(self):
        """Validate metadata after initialization."""
        if not self.name:
            raise ValueError("Plugin name is required")
        if not self.version:
            raise ValueError("Plugin version is required")


@dataclass
class PluginConfig:
    """
    Plugin configuration container with settings and parameters.
    """
    # Core configuration
    enabled: bool = True
    auto_start: bool = True
    debug_mode: bool = False
    log_level: str = "INFO"
    
    # Resource limits
    memory_limit_mb: Optional[int] = None
    cpu_limit_percent: Optional[float] = None
    disk_limit_mb: Optional[int] = None
    
    # Network and security
    network_allowed: bool = False
    file_access_paths: List[str] = field(default_factory=list)
    environment_variables: Dict[str, str] = field(default_factory=dict)
    
    # Custom configuration
    settings: Dict[str, Any] = field(default_factory=dict)
    
    # Monitoring and health
    health_check_enabled: bool = True
    metrics_enabled: bool = True
    tracing_enabled: bool = False
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value with dotted notation support."""
        keys = key.split('.')
        value = self.settings
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def set(self, key: str, value: Any) -> None:
        """Set configuration value with dotted notation support."""
        keys = key.split('.')
        target = self.settings
        
        for k in keys[:-1]:
            if k not in target:
                target[k] = {}
            target = target[k]
        
        target[keys[-1]] = value


@dataclass
class PluginEvent:
    """
    Plugin event data structure for communication.
    """
    name: str
    source: str
    timestamp: datetime = field(default_factory=datetime.now)
    data: Dict[str, Any] = field(default_factory=dict)
    priority: PluginPriority = PluginPriority.NORMAL
    correlation_id: Optional[str] = None
    reply_to: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary."""
        return {
            'name': self.name,
            'source': self.source,
            'timestamp': self.timestamp.isoformat(),
            'data': self.data,
            'priority': self.priority.value,
            'correlation_id': self.correlation_id,
            'reply_to': self.reply_to
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PluginEvent':
        """Create event from dictionary."""
        return cls(
            name=data['name'],
            source=data['source'],
            timestamp=datetime.fromisoformat(data['timestamp']),
            data=data.get('data', {}),
            priority=PluginPriority(data.get('priority', PluginPriority.NORMAL.value)),
            correlation_id=data.get('correlation_id'),
            reply_to=data.get('reply_to')
        )


@dataclass
class PluginHealth:
    """
    Plugin health status information.
    """
    is_healthy: bool
    score: float  # 0.0 to 1.0
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert health status to dictionary."""
        return {
            'is_healthy': self.is_healthy,
            'score': self.score,
            'message': self.message,
            'details': self.details,
            'timestamp': self.timestamp.isoformat()
        }


class PluginInterface(ABC):
    """
    Abstract base class that all plugins must implement.
    
    This interface defines the contract for plugin lifecycle management,
    configuration, and communication with the plugin system.
    """
    
    def __init__(self):
        """Initialize the plugin."""
        self._plugin_metadata: Optional[PluginMetadata] = None
        self._plugin_config: Optional[PluginConfig] = None
        self._plugin_system: Optional[Any] = None
        self._is_initialized: bool = False
        self._is_started: bool = False
    
    @property
    def metadata(self) -> Optional[PluginMetadata]:
        """Get plugin metadata."""
        return self._plugin_metadata
    
    @property
    def config(self) -> Optional[PluginConfig]:
        """Get plugin configuration."""
        return self._plugin_config
    
    @property
    def is_initialized(self) -> bool:
        """Check if plugin is initialized."""
        return self._is_initialized
    
    @property
    def is_started(self) -> bool:
        """Check if plugin is started."""
        return self._is_started
    
    @abstractmethod
    async def initialize(self, config: PluginConfig) -> None:
        """
        Initialize the plugin with configuration.
        
        This method is called once when the plugin is loaded.
        Plugins should perform one-time setup here.
        
        Args:
            config: Plugin configuration
            
        Raises:
            PluginInitializationError: If initialization fails
        """
        pass
    
    @abstractmethod
    async def start(self) -> None:
        """
        Start the plugin.
        
        This method is called to start plugin operations.
        Plugins should begin their main functionality here.
        
        Raises:
            PluginStartError: If start fails
        """
        pass
    
    @abstractmethod
    async def stop(self) -> None:
        """
        Stop the plugin.
        
        This method is called to stop plugin operations gracefully.
        Plugins should cleanup active operations but preserve state.
        
        Raises:
            PluginStopError: If stop fails
        """
        pass
    
    @abstractmethod
    async def destroy(self) -> None:
        """
        Destroy the plugin and cleanup all resources.
        
        This method is called when the plugin is being unloaded.
        Plugins should cleanup all resources and state.
        
        Raises:
            PluginDestroyError: If destruction fails
        """
        pass
    
    async def health_check(self) -> PluginHealth:
        """
        Perform a health check on the plugin.
        
        Returns:
            PluginHealth: Health status information
        """
        return PluginHealth(
            is_healthy=self._is_started,
            score=1.0 if self._is_started else 0.0,
            message="Plugin is running" if self._is_started else "Plugin is not started"
        )
    
    async def get_metrics(self) -> Dict[str, Any]:
        """
        Get plugin performance metrics.
        
        Returns:
            Dictionary of metrics data
        """
        return {}
    
    async def get_status(self) -> Dict[str, Any]:
        """
        Get detailed plugin status information.
        
        Returns:
            Dictionary of status information
        """
        return {
            'initialized': self._is_initialized,
            'started': self._is_started,
            'metadata': self._plugin_metadata.__dict__ if self._plugin_metadata else None,
            'config': self._plugin_config.__dict__ if self._plugin_config else None
        }
    
    def set_plugin_system(self, plugin_system: Any) -> None:
        """Set reference to the plugin system."""
        self._plugin_system = plugin_system


class EventHandler(ABC):
    """
    Abstract base class for handling plugin events.
    """
    
    @abstractmethod
    async def handle_event(self, event: PluginEvent) -> Optional[PluginEvent]:
        """
        Handle a plugin event.
        
        Args:
            event: The event to handle
            
        Returns:
            Optional response event
        """
        pass
    
    @abstractmethod
    def get_supported_events(self) -> List[str]:
        """
        Get list of event names this handler supports.
        
        Returns:
            List of supported event names
        """
        pass


class EventPublisher(ABC):
    """
    Abstract base class for publishing plugin events.
    """
    
    @abstractmethod
    async def publish_event(self, event: PluginEvent) -> None:
        """
        Publish an event to the plugin system.
        
        Args:
            event: Event to publish
        """
        pass
    
    @abstractmethod
    async def subscribe_to_events(self, event_names: List[str], handler: EventHandler) -> None:
        """
        Subscribe to specific events.
        
        Args:
            event_names: List of event names to subscribe to
            handler: Event handler
        """
        pass
    
    @abstractmethod
    async def unsubscribe_from_events(self, event_names: List[str], handler: EventHandler) -> None:
        """
        Unsubscribe from specific events.
        
        Args:
            event_names: List of event names to unsubscribe from
            handler: Event handler
        """
        pass


class ResourceManager(ABC):
    """
    Abstract base class for managing plugin resources.
    """
    
    @abstractmethod
    async def allocate_resources(self, requirements: Dict[str, Any]) -> Dict[str, Any]:
        """
        Allocate resources for the plugin.
        
        Args:
            requirements: Resource requirements
            
        Returns:
            Allocated resource handles
        """
        pass
    
    @abstractmethod
    async def release_resources(self, handles: Dict[str, Any]) -> None:
        """
        Release allocated resources.
        
        Args:
            handles: Resource handles to release
        """
        pass
    
    @abstractmethod
    async def get_resource_usage(self) -> Dict[str, Any]:
        """
        Get current resource usage.
        
        Returns:
            Resource usage statistics
        """
        pass


class SecurityContext(ABC):
    """
    Abstract base class for plugin security context.
    """
    
    @abstractmethod
    async def check_permission(self, operation: str, resource: str) -> bool:
        """
        Check if plugin has permission for operation on resource.
        
        Args:
            operation: Operation to perform
            resource: Resource to access
            
        Returns:
            True if permission granted, False otherwise
        """
        pass
    
    @abstractmethod
    async def get_security_token(self) -> Optional[str]:
        """
        Get security token for authenticated operations.
        
        Returns:
            Security token or None if not available
        """
        pass
    
    @abstractmethod
    async def validate_input(self, data: Any) -> bool:
        """
        Validate input data for security.
        
        Args:
            data: Data to validate
            
        Returns:
            True if data is safe, False otherwise
        """
        pass


class ServicePlugin(PluginInterface):
    """
    Base class for service-type plugins that provide ongoing functionality.
    """
    
    @abstractmethod
    async def process_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a service request.
        
        Args:
            request: Request data
            
        Returns:
            Response data
        """
        pass
    
    async def get_service_info(self) -> Dict[str, Any]:
        """
        Get service information.
        
        Returns:
            Service information
        """
        return {
            'name': self.metadata.name if self.metadata else 'unknown',
            'version': self.metadata.version if self.metadata else 'unknown',
            'type': 'service',
            'provides': self.metadata.provides if self.metadata else []
        }


class ConnectorPlugin(PluginInterface):
    """
    Base class for connector-type plugins that integrate external systems.
    """
    
    @abstractmethod
    async def connect(self, connection_params: Dict[str, Any]) -> bool:
        """
        Establish connection to external system.
        
        Args:
            connection_params: Connection parameters
            
        Returns:
            True if connected successfully, False otherwise
        """
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """
        Disconnect from external system.
        """
        pass
    
    @abstractmethod
    async def is_connected(self) -> bool:
        """
        Check if connected to external system.
        
        Returns:
            True if connected, False otherwise
        """
        pass
    
    @abstractmethod
    async def send_data(self, data: Any) -> bool:
        """
        Send data to external system.
        
        Args:
            data: Data to send
            
        Returns:
            True if sent successfully, False otherwise
        """
        pass
    
    @abstractmethod
    async def receive_data(self) -> Optional[Any]:
        """
        Receive data from external system.
        
        Returns:
            Received data or None if no data available
        """
        pass


class TransformerPlugin(PluginInterface):
    """
    Base class for transformer-type plugins that process and transform data.
    """
    
    @abstractmethod
    async def transform(self, input_data: Any, transform_params: Dict[str, Any] = None) -> Any:
        """
        Transform input data.
        
        Args:
            input_data: Data to transform
            transform_params: Optional transformation parameters
            
        Returns:
            Transformed data
        """
        pass
    
    @abstractmethod
    async def validate_input(self, input_data: Any) -> bool:
        """
        Validate input data before transformation.
        
        Args:
            input_data: Data to validate
            
        Returns:
            True if valid, False otherwise
        """
        pass
    
    @abstractmethod
    async def get_supported_formats(self) -> List[str]:
        """
        Get list of supported data formats.
        
        Returns:
            List of supported format names
        """
        pass


class MonitorPlugin(PluginInterface):
    """
    Base class for monitor-type plugins that observe system behavior.
    """
    
    @abstractmethod
    async def start_monitoring(self, targets: List[str]) -> None:
        """
        Start monitoring specified targets.
        
        Args:
            targets: List of targets to monitor
        """
        pass
    
    @abstractmethod
    async def stop_monitoring(self) -> None:
        """
        Stop all monitoring activities.
        """
        pass
    
    @abstractmethod
    async def get_monitoring_data(self, target: str = None) -> Dict[str, Any]:
        """
        Get monitoring data.
        
        Args:
            target: Specific target to get data for (None for all)
            
        Returns:
            Monitoring data
        """
        pass
    
    @abstractmethod
    async def set_alert_threshold(self, metric: str, threshold: float) -> None:
        """
        Set alert threshold for a metric.
        
        Args:
            metric: Metric name
            threshold: Alert threshold value
        """
        pass


# Exception classes for plugin operations

class PluginError(Exception):
    """Base exception for plugin-related errors."""
    pass


class PluginInitializationError(PluginError):
    """Raised when plugin initialization fails."""
    pass


class PluginStartError(PluginError):
    """Raised when plugin start fails."""
    pass


class PluginStopError(PluginError):
    """Raised when plugin stop fails."""
    pass


class PluginDestroyError(PluginError):
    """Raised when plugin destruction fails."""
    pass


class PluginConfigurationError(PluginError):
    """Raised when plugin configuration is invalid."""
    pass


class PluginSecurityError(PluginError):
    """Raised when plugin security constraints are violated."""
    pass


class PluginResourceError(PluginError):
    """Raised when plugin resource allocation or usage fails."""
    pass


class PluginCommunicationError(PluginError):
    """Raised when plugin communication fails."""
    pass


class PluginTimeoutError(PluginError):
    """Raised when plugin operations timeout."""
    pass