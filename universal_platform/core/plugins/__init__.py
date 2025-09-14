"""
Universal Platform Plugin System

Enterprise-grade plugin architecture providing dynamic discovery, loading,
lifecycle management, hot-reloading, isolation, and comprehensive monitoring.

Features:
- Dynamic plugin discovery and loading
- Plugin dependency resolution with cycle detection
- Lifecycle management (init, start, stop, destroy)
- Hot-reloading capabilities
- Plugin isolation and sandboxing
- Configuration management per plugin
- Event-driven plugin communication
- Plugin metadata and versioning
- Health checks and monitoring
- Performance tracking and metrics
- Comprehensive error handling and logging

Components:
- PluginSystem: Core plugin management framework
- PluginRegistry: Plugin discovery and dependency resolution
- PluginInterface: Base interface for all plugins
- Decorators: Plugin metadata and lifecycle decorators

Example Usage:
    ```python
    from universal_platform.core.plugins import PluginSystem, PluginConfig
    from universal_platform.core.plugins.examples import EmailServicePlugin
    
    # Initialize plugin system
    plugin_system = PluginSystem(
        plugin_dirs=["/path/to/plugins"],
        enable_hot_reload=True,
        enable_isolation=True
    )
    
    # Initialize and start the system
    await plugin_system.initialize()
    
    # Register and load a plugin
    await plugin_system.registry.register_plugin_path("email_service", "/path/to/plugin")
    await plugin_system.load_plugin("email_service")
    await plugin_system.initialize_plugin("email_service")
    await plugin_system.start_plugin("email_service")
    
    # Get plugin status
    status = await plugin_system.get_plugin_status("email_service")
    print(f"Plugin status: {status}")
    
    # Shutdown system
    await plugin_system.shutdown()
    ```

Security and Isolation:
- Plugins run in controlled environments with resource limits
- Network and file system access can be restricted per plugin
- Input validation and sanitization for all plugin operations
- Comprehensive audit logging for security monitoring

Performance and Monitoring:
- Real-time health checks and performance metrics
- Resource usage monitoring (CPU, memory, disk)
- Plugin dependency analysis and optimization
- Hot-reloading without service interruption

Plugin Development:
- Rich decorator system for metadata and lifecycle hooks
- Type-safe interfaces and configuration schemas
- Comprehensive error handling and logging utilities
- Performance monitoring and profiling tools
"""

import logging
from typing import Dict, List, Optional, Type

# Core components
from .plugin_system import PluginSystem, PluginInstance, PluginState
from .registry import PluginRegistry, PluginInfo, PluginConflict, ConflictType
from .interfaces import (
    # Base interfaces
    PluginInterface, ServicePlugin, ConnectorPlugin, TransformerPlugin, MonitorPlugin,
    
    # Configuration and metadata
    PluginConfig, PluginMetadata, PluginEvent, PluginHealth,
    PluginType, PluginPriority, SecurityLevel,
    
    # Event and communication interfaces
    EventHandler, EventPublisher, ResourceManager, SecurityContext,
    
    # Exception classes
    PluginError, PluginInitializationError, PluginStartError, PluginStopError,
    PluginDestroyError, PluginConfigurationError, PluginSecurityError,
    PluginResourceError, PluginCommunicationError, PluginTimeoutError
)
from .decorators import (
    # Metadata and configuration decorators
    plugin_metadata, config_schema,
    
    # Lifecycle decorators
    lifecycle_hook, HookType,
    
    # Security and permission decorators
    requires_permission, PermissionType,
    
    # Performance and monitoring decorators
    monitor_performance, retry_on_failure, timeout, validate_input,
    cache_result, log_calls, deprecated,
    
    # Utility decorators and functions
    singleton, plugin_context,
    get_plugin_metadata, get_lifecycle_hooks, get_permission_requirements,
    get_performance_metrics, clear_performance_metrics, get_all_performance_stats
)

# Set up logging for the plugin system
def setup_plugin_logging(
    level: int = logging.INFO,
    format_string: Optional[str] = None,
    handlers: Optional[List[logging.Handler]] = None
) -> None:
    """
    Setup logging configuration for the plugin system.
    
    Args:
        level: Logging level (default: INFO)
        format_string: Custom log format string
        handlers: List of custom log handlers
    """
    if format_string is None:
        format_string = (
            '%(asctime)s - %(name)s - %(levelname)s - '
            '[%(filename)s:%(lineno)d] - %(message)s'
        )
    
    # Configure root logger for plugin system
    logger = logging.getLogger('universal_platform.core.plugins')
    logger.setLevel(level)
    
    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Add new handlers
    if handlers:
        for handler in handlers:
            handler.setFormatter(logging.Formatter(format_string))
            logger.addHandler(handler)
    else:
        # Default console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter(format_string))
        logger.addHandler(console_handler)


# Plugin discovery utilities
def discover_plugins_in_directory(directory_path: str) -> Dict[str, str]:
    """
    Discover plugins in a directory.
    
    Args:
        directory_path: Directory path to search for plugins
        
    Returns:
        Dictionary mapping plugin names to their paths
    """
    import os
    from pathlib import Path
    
    discovered = {}
    plugin_dir = Path(directory_path)
    
    if not plugin_dir.exists() or not plugin_dir.is_dir():
        return discovered
    
    for item in plugin_dir.iterdir():
        if item.is_dir() and (item / "__init__.py").exists():
            # Python package plugin
            discovered[item.name] = str(item)
        elif item.is_file() and item.suffix == ".py" and item.name != "__init__.py":
            # Single file plugin
            discovered[item.stem] = str(item)
    
    return discovered


def validate_plugin_class(plugin_class: Type) -> bool:
    """
    Validate that a class implements the plugin interface correctly.
    
    Args:
        plugin_class: Plugin class to validate
        
    Returns:
        True if valid plugin class, False otherwise
    """
    try:
        # Check if it's a subclass of PluginInterface
        if not issubclass(plugin_class, PluginInterface):
            return False
        
        # Check if required methods are implemented
        required_methods = ['initialize', 'start', 'stop', 'destroy']
        for method_name in required_methods:
            if not hasattr(plugin_class, method_name):
                return False
            
            method = getattr(plugin_class, method_name)
            if not callable(method):
                return False
        
        # Check if metadata is available
        if hasattr(plugin_class, '_plugin_metadata'):
            metadata = plugin_class._plugin_metadata
            if not isinstance(metadata, PluginMetadata):
                return False
        
        return True
        
    except Exception:
        return False


# System information utilities
def get_system_info() -> Dict[str, any]:
    """
    Get system information relevant to plugin execution.
    
    Returns:
        Dictionary containing system information
    """
    import platform
    import sys
    import os
    
    return {
        'platform': {
            'system': platform.system(),
            'release': platform.release(),
            'version': platform.version(),
            'machine': platform.machine(),
            'processor': platform.processor()
        },
        'python': {
            'version': sys.version,
            'version_info': sys.version_info,
            'executable': sys.executable,
            'platform': sys.platform
        },
        'process': {
            'pid': os.getpid(),
            'working_directory': os.getcwd(),
            'environment_variables': len(os.environ)
        }
    }


# Version information
__version__ = "1.0.0"
__author__ = "Universal Platform Team"
__license__ = "MIT"

# Export all public components
__all__ = [
    # Core system
    'PluginSystem',
    'PluginRegistry',
    'PluginInstance',
    'PluginInfo',
    'PluginState',
    'PluginConflict',
    'ConflictType',
    
    # Interfaces
    'PluginInterface',
    'ServicePlugin',
    'ConnectorPlugin', 
    'TransformerPlugin',
    'MonitorPlugin',
    'EventHandler',
    'EventPublisher',
    'ResourceManager',
    'SecurityContext',
    
    # Configuration and metadata
    'PluginConfig',
    'PluginMetadata',
    'PluginEvent',
    'PluginHealth',
    'PluginType',
    'PluginPriority',
    'SecurityLevel',
    
    # Decorators
    'plugin_metadata',
    'config_schema',
    'lifecycle_hook',
    'requires_permission',
    'monitor_performance',
    'retry_on_failure',
    'timeout',
    'validate_input',
    'cache_result',
    'log_calls',
    'deprecated',
    'singleton',
    'plugin_context',
    'HookType',
    'PermissionType',
    
    # Exceptions
    'PluginError',
    'PluginInitializationError',
    'PluginStartError',
    'PluginStopError',
    'PluginDestroyError',
    'PluginConfigurationError',
    'PluginSecurityError',
    'PluginResourceError',
    'PluginCommunicationError',
    'PluginTimeoutError',
    
    # Utility functions
    'setup_plugin_logging',
    'discover_plugins_in_directory',
    'validate_plugin_class',
    'get_system_info',
    'get_plugin_metadata',
    'get_lifecycle_hooks',
    'get_permission_requirements',
    'get_performance_metrics',
    'clear_performance_metrics',
    'get_all_performance_stats',
    
    # Version info
    '__version__',
    '__author__',
    '__license__'
]