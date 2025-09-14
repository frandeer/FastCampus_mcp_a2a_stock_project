# Universal Platform Plugin System

Enterprise-grade plugin architecture providing dynamic discovery, loading, lifecycle management, hot-reloading, isolation, and comprehensive monitoring for the universal platform.

## Features

### Core Functionality
- **Dynamic Plugin Discovery**: Automatic discovery and registration of plugins from directories
- **Dependency Resolution**: Smart dependency management with cycle detection and conflict resolution
- **Lifecycle Management**: Complete plugin lifecycle (initialize → start → stop → destroy)
- **Hot Reloading**: Runtime plugin reloading without service interruption
- **Plugin Isolation**: Sandboxed execution with resource limits and security controls
- **Configuration Management**: Type-safe configuration with validation schemas

### Advanced Capabilities
- **Event-Driven Communication**: Inter-plugin communication via events
- **Health Monitoring**: Real-time health checks and performance metrics
- **Security & Permissions**: Fine-grained permission system with security contexts
- **Performance Tracking**: Comprehensive metrics and profiling
- **Error Handling**: Robust error recovery and retry mechanisms
- **Logging & Audit**: Enterprise-grade logging with audit trails

## Quick Start

### Basic Usage

```python
from universal_platform.core.plugins import PluginSystem, PluginConfig

# Initialize plugin system
plugin_system = PluginSystem(
    plugin_dirs=["/path/to/plugins"],
    enable_hot_reload=True,
    enable_isolation=True,
    enable_health_checks=True
)

# Start the system
await plugin_system.initialize()

# Load and start a plugin
await plugin_system.load_plugin("my_plugin")
await plugin_system.initialize_plugin("my_plugin")
await plugin_system.start_plugin("my_plugin")

# Get plugin status
status = await plugin_system.get_plugin_status("my_plugin")
print(f"Plugin status: {status}")

# Shutdown
await plugin_system.shutdown()
```

### Creating a Plugin

```python
from universal_platform.core.plugins import (
    ServicePlugin, PluginConfig, plugin_metadata, 
    config_schema, monitor_performance, requires_permission
)

@plugin_metadata(
    name="my_service",
    version="1.0.0",
    description="Example service plugin",
    plugin_type="service",
    provides=["my_capability"],
    requires=["network"]
)
@config_schema({
    'api_key': {'type': str, 'required': True},
    'timeout': {'type': int, 'required': False, 'default': 30}
})
class MyServicePlugin(ServicePlugin):
    
    async def initialize(self, config: PluginConfig) -> None:
        self.api_key = config.get('api_key')
        self.timeout = config.get('timeout', 30)
        # Initialization logic here
    
    async def start(self) -> None:
        # Start service logic here
        pass
    
    async def stop(self) -> None:
        # Stop service logic here
        pass
    
    async def destroy(self) -> None:
        # Cleanup logic here
        pass
    
    @monitor_performance()
    @requires_permission("network")
    async def process_request(self, request: dict) -> dict:
        # Process service requests
        return {"result": "processed"}
```

## Architecture

### Core Components

#### PluginSystem
Central orchestrator managing plugin lifecycle, dependencies, and monitoring.

```python
from universal_platform.core.plugins import PluginSystem

system = PluginSystem(
    plugin_dirs=["/plugins"],
    config_dir="/config",
    enable_hot_reload=True,
    enable_isolation=True,
    security_policy={
        'restricted_imports': ['os', 'subprocess'],
        'max_memory_mb': 100
    }
)
```

#### PluginRegistry
Manages plugin discovery, registration, and dependency resolution.

```python
# Get registry from plugin system
registry = system.registry

# Register a plugin manually
await registry.register_plugin_path("my_plugin", "/path/to/plugin")

# Resolve dependencies
resolved_order, conflicts = await registry.resolve_dependencies(["plugin1", "plugin2"])

# Check for conflicts
conflicts = await registry.check_conflicts()
```

#### Plugin Interfaces
Base interfaces for different plugin types:

- **PluginInterface**: Base interface for all plugins
- **ServicePlugin**: For service-type plugins providing ongoing functionality
- **ConnectorPlugin**: For external system integration
- **TransformerPlugin**: For data transformation and processing
- **MonitorPlugin**: For system monitoring and metrics collection

### Plugin Types

#### Service Plugin
Provides ongoing services and functionality:

```python
from universal_platform.core.plugins import ServicePlugin

class EmailServicePlugin(ServicePlugin):
    async def process_request(self, request: dict) -> dict:
        # Handle email sending requests
        return await self.send_email(request)
```

#### Connector Plugin
Integrates with external systems:

```python
from universal_platform.core.plugins import ConnectorPlugin

class DatabaseConnectorPlugin(ConnectorPlugin):
    async def connect(self, connection_params: dict) -> bool:
        # Establish database connection
        return await self.establish_connection(connection_params)
    
    async def send_data(self, data: any) -> bool:
        # Send data to database
        return await self.execute_query(data)
```

#### Transformer Plugin
Processes and transforms data:

```python
from universal_platform.core.plugins import TransformerPlugin

class DataTransformerPlugin(TransformerPlugin):
    async def transform(self, input_data: any, params: dict = None) -> any:
        # Transform data between formats
        return await self.convert_format(input_data, params)
```

#### Monitor Plugin
Observes and monitors system behavior:

```python
from universal_platform.core.plugins import MonitorPlugin

class SystemMonitorPlugin(MonitorPlugin):
    async def start_monitoring(self, targets: list) -> None:
        # Start monitoring specified targets
        await self.begin_monitoring(targets)
    
    async def get_monitoring_data(self, target: str = None) -> dict:
        # Return monitoring data
        return await self.collect_metrics(target)
```

## Decorators

### Metadata Decorators

#### @plugin_metadata
Define plugin metadata and requirements:

```python
@plugin_metadata(
    name="my_plugin",
    version="2.1.0",
    description="Advanced plugin with dependencies",
    author="Developer Team",
    plugin_type=PluginType.SERVICE,
    priority=PluginPriority.HIGH,
    security_level=SecurityLevel.RESTRICTED,
    dependencies={"auth_plugin": ">=1.0.0"},
    provides=["data_processing", "analytics"],
    requires=["database", "cache"],
    tags=["data", "analytics", "ml"],
    max_memory_mb=200,
    network_access=True
)
class AdvancedPlugin(ServicePlugin):
    pass
```

#### @config_schema
Define configuration validation schema:

```python
@config_schema({
    'database_url': {
        'type': str,
        'required': True,
        'pattern': r'^postgresql://.*'
    },
    'pool_size': {
        'type': int,
        'required': False,
        'default': 10,
        'minimum': 1,
        'maximum': 50
    },
    'features': {
        'type': dict,
        'required': False,
        'default': {},
        'properties': {
            'enable_caching': {'type': bool, 'default': True},
            'cache_ttl': {'type': int, 'default': 300}
        }
    }
})
class ConfigurablePlugin(ServicePlugin):
    pass
```

### Lifecycle Decorators

#### @lifecycle_hook
Register lifecycle event handlers:

```python
from universal_platform.core.plugins import lifecycle_hook, HookType

class MyPlugin(ServicePlugin):
    
    @lifecycle_hook(HookType.BEFORE_INIT)
    async def validate_environment(self):
        # Check prerequisites before initialization
        pass
    
    @lifecycle_hook(HookType.AFTER_START)
    async def post_start_setup(self):
        # Additional setup after starting
        pass
    
    @lifecycle_hook(HookType.ON_ERROR)
    async def handle_error(self, error):
        # Handle plugin errors
        pass
```

### Security Decorators

#### @requires_permission
Enforce permission requirements:

```python
from universal_platform.core.plugins import requires_permission, PermissionType

class SecurePlugin(ServicePlugin):
    
    @requires_permission(PermissionType.NETWORK, PermissionType.FILE_SYSTEM)
    async def sensitive_operation(self):
        # This method requires network and file system permissions
        pass
    
    @requires_permission(PermissionType.ADMIN)
    async def admin_only_operation(self):
        # This method requires admin permissions
        pass
```

### Performance Decorators

#### @monitor_performance
Track method performance:

```python
from universal_platform.core.plugins import monitor_performance

class OptimizedPlugin(ServicePlugin):
    
    @monitor_performance(include_args=True)
    async def expensive_operation(self, data):
        # Performance metrics will be collected automatically
        return await self.process_data(data)
```

#### @retry_on_failure
Add retry logic to methods:

```python
from universal_platform.core.plugins import retry_on_failure

class ResilientPlugin(ServicePlugin):
    
    @retry_on_failure(
        max_attempts=3,
        delay=2.0,
        exponential_backoff=True,
        exceptions=(ConnectionError, TimeoutError)
    )
    async def unreliable_operation(self):
        # Will retry up to 3 times with exponential backoff
        return await self.external_api_call()
```

#### @timeout
Add timeout protection:

```python
from universal_platform.core.plugins import timeout

class TimedPlugin(ServicePlugin):
    
    @timeout(30.0)  # 30 seconds timeout
    async def long_running_operation(self):
        # Will raise PluginTimeoutError if takes longer than 30 seconds
        return await self.complex_calculation()
```

#### @cache_result
Cache method results:

```python
from universal_platform.core.plugins import cache_result

class CachedPlugin(ServicePlugin):
    
    @cache_result(ttl=300.0)  # Cache for 5 minutes
    async def expensive_computation(self, input_data):
        # Results will be cached automatically
        return await self.compute_result(input_data)
```

### Validation Decorators

#### @validate_input
Validate method inputs:

```python
from universal_platform.core.plugins import validate_input

class ValidatedPlugin(ServicePlugin):
    
    @validate_input(
        email=lambda x: '@' in x and '.' in x,
        age=lambda x: isinstance(x, int) and 0 <= x <= 150
    )
    async def process_user_data(self, email: str, age: int):
        # Inputs will be validated before method execution
        pass
```

## Configuration

### Plugin Configuration

Plugins are configured using the `PluginConfig` class:

```python
from universal_platform.core.plugins import PluginConfig

config = PluginConfig(
    enabled=True,
    auto_start=True,
    debug_mode=False,
    log_level="INFO",
    memory_limit_mb=100,
    network_allowed=True,
    settings={
        'api_endpoint': 'https://api.example.com',
        'batch_size': 100,
        'features': {
            'enable_metrics': True,
            'enable_caching': False
        }
    }
)

# Access configuration values
endpoint = config.get('api_endpoint')
batch_size = config.get('batch_size', 50)  # Default value
metrics_enabled = config.get('features.enable_metrics', False)  # Nested access
```

### System Configuration

Configure the plugin system with various options:

```python
from universal_platform.core.plugins import PluginSystem

system = PluginSystem(
    plugin_dirs=[
        "/app/plugins",
        "/system/plugins",
        "/user/plugins"
    ],
    config_dir="/app/config",
    enable_hot_reload=True,
    enable_isolation=True,
    enable_health_checks=True,
    health_check_interval=60.0,
    security_policy={
        'restricted_imports': ['os', 'subprocess', 'socket'],
        'max_memory_mb': 150,
        'allowed_file_paths': ['/data', '/tmp'],
        'network_restrictions': {
            'allowed_hosts': ['api.example.com'],
            'blocked_ports': [22, 23, 25]
        }
    }
)
```

## Monitoring and Health Checks

### Health Monitoring

Plugins can implement health checks for monitoring:

```python
from universal_platform.core.plugins import PluginHealth

class MonitoredPlugin(ServicePlugin):
    
    async def health_check(self) -> PluginHealth:
        try:
            # Perform health checks
            db_healthy = await self.check_database_connection()
            cache_healthy = await self.check_cache_connection()
            
            # Calculate health score
            health_score = (db_healthy + cache_healthy) / 2
            
            return PluginHealth(
                is_healthy=health_score > 0.5,
                score=health_score,
                message="Service operational" if health_score > 0.8 else "Service degraded",
                details={
                    'database_status': 'healthy' if db_healthy else 'unhealthy',
                    'cache_status': 'healthy' if cache_healthy else 'unhealthy',
                    'connections_active': await self.get_active_connections()
                }
            )
            
        except Exception as e:
            return PluginHealth(
                is_healthy=False,
                score=0.0,
                message=f"Health check failed: {e}",
                details={'error': str(e)}
            )
```

### Performance Metrics

Access performance metrics for plugins:

```python
# Get system-wide metrics
metrics = await plugin_system.get_plugin_status("my_plugin")
print(f"Plugin metrics: {metrics}")

# Get detailed performance stats
from universal_platform.core.plugins import get_all_performance_stats
stats = get_all_performance_stats()
for method, metrics in stats.items():
    print(f"{method}: {metrics['call_count']} calls, {metrics['average_time']:.3f}s avg")
```

## Event System

### Event Publishing and Handling

Plugins can communicate via events:

```python
from universal_platform.core.plugins import PluginEvent, EventHandler

class PublisherPlugin(ServicePlugin):
    
    async def publish_data_event(self, data):
        event = PluginEvent(
            name="data_processed",
            source=self.metadata.name,
            data={'processed_data': data, 'timestamp': datetime.now()},
            priority=PluginPriority.NORMAL
        )
        
        if hasattr(self, '_event_publisher'):
            await self._event_publisher.publish_event(event)

class SubscriberPlugin(ServicePlugin, EventHandler):
    
    async def handle_event(self, event: PluginEvent) -> Optional[PluginEvent]:
        if event.name == "data_processed":
            # Process the received data
            await self.handle_processed_data(event.data)
        
        return None  # No response event
    
    def get_supported_events(self) -> List[str]:
        return ["data_processed", "system_alert"]
```

## Security and Isolation

### Security Features

The plugin system provides comprehensive security features:

```python
# Configure security policy
security_policy = {
    'restricted_imports': [
        'os', 'subprocess', 'socket', 'threading',
        'multiprocessing', 'ctypes', 'importlib'
    ],
    'max_memory_mb': 100,
    'max_cpu_percent': 25.0,
    'max_disk_mb': 50,
    'network_restrictions': {
        'allowed_hosts': ['api.internal.com'],
        'blocked_ports': [22, 23, 25, 443],
        'require_ssl': True
    },
    'file_system_restrictions': {
        'allowed_read_paths': ['/data/input'],
        'allowed_write_paths': ['/data/output'],
        'blocked_paths': ['/etc', '/sys', '/proc']
    }
}

system = PluginSystem(security_policy=security_policy)
```

### Permission System

Fine-grained permission control:

```python
from universal_platform.core.plugins import requires_permission, PermissionType

class SecurePlugin(ServicePlugin):
    
    @requires_permission(PermissionType.NETWORK)
    async def make_api_call(self):
        # Requires network permission
        pass
    
    @requires_permission(PermissionType.FILE_SYSTEM, PermissionType.WRITE)
    async def save_to_file(self, data):
        # Requires file system and write permissions
        pass
    
    @requires_permission(PermissionType.ADMIN)
    async def system_operation(self):
        # Requires admin permission
        pass
```

## Error Handling

### Comprehensive Error Handling

The plugin system provides robust error handling:

```python
from universal_platform.core.plugins import (
    PluginError, PluginInitializationError, PluginTimeoutError
)

try:
    await plugin_system.load_plugin("problematic_plugin")
except PluginInitializationError as e:
    logger.error(f"Plugin initialization failed: {e}")
    # Handle initialization failure
except PluginTimeoutError as e:
    logger.error(f"Plugin operation timed out: {e}")
    # Handle timeout
except PluginError as e:
    logger.error(f"General plugin error: {e}")
    # Handle general plugin errors
```

### Error Recovery

Automatic error recovery and retry mechanisms:

```python
class ResilientPlugin(ServicePlugin):
    
    @retry_on_failure(max_attempts=3, delay=1.0, exponential_backoff=True)
    async def critical_operation(self):
        # Will automatically retry on failure
        pass
    
    @lifecycle_hook(HookType.ON_ERROR)
    async def handle_plugin_error(self, error):
        # Custom error handling logic
        await self.log_error(error)
        await self.attempt_recovery()
```

## Example Plugins

The system includes comprehensive example plugins:

### Email Service Plugin
```python
from universal_platform.core.plugins.examples import EmailServicePlugin

# Configure and use email service
email_plugin = EmailServicePlugin()
config = PluginConfig(settings={
    'smtp_host': 'smtp.example.com',
    'smtp_port': 587,
    'username': 'user@example.com',
    'password': 'password'
})

await email_plugin.initialize(config)
await email_plugin.start()

# Send email
result = await email_plugin.process_request({
    'action': 'send_email',
    'to_emails': ['recipient@example.com'],
    'subject': 'Test Email',
    'body': 'Hello from plugin system!'
})
```

### Database Connector Plugin
```python
from universal_platform.core.plugins.examples import DatabaseConnectorPlugin

# Configure database connector
db_plugin = DatabaseConnectorPlugin()
config = PluginConfig(settings={
    'database_type': 'postgresql',
    'host': 'localhost',
    'port': 5432,
    'database': 'myapp',
    'username': 'user',
    'password': 'password'
})

await db_plugin.initialize(config)
await db_plugin.start()

# Execute query
result = await db_plugin.execute_query(
    "SELECT * FROM users WHERE active = ?",
    [True]
)
```

### Data Transformer Plugin
```python
from universal_platform.core.plugins.examples import DataTransformerPlugin

# Configure data transformer
transformer = DataTransformerPlugin()
await transformer.initialize(PluginConfig())
await transformer.start()

# Transform data
json_data = {'name': 'John', 'age': 30}
xml_result = await transformer.transform(
    json_data,
    {'from_format': 'json', 'to_format': 'xml'}
)
```

### System Monitor Plugin
```python
from universal_platform.core.plugins.examples import SystemMonitorPlugin

# Configure system monitor
monitor = SystemMonitorPlugin()
await monitor.initialize(PluginConfig())
await monitor.start()

# Start monitoring
await monitor.start_monitoring(['cpu', 'memory', 'disk'])

# Get monitoring data
data = await monitor.get_monitoring_data()
print(f"System metrics: {data}")
```

## Best Practices

### Plugin Development
1. **Follow Interface Contracts**: Always implement required interface methods
2. **Use Type Hints**: Provide clear type annotations for better IDE support
3. **Handle Errors Gracefully**: Implement proper error handling and logging
4. **Resource Management**: Always cleanup resources in destroy() method
5. **Configuration Validation**: Use config schemas for validation
6. **Security Awareness**: Be mindful of security implications

### Performance Optimization
1. **Use Async/Await**: Leverage async programming for I/O operations
2. **Cache Results**: Cache expensive computations when appropriate
3. **Monitor Resource Usage**: Track memory and CPU usage
4. **Batch Operations**: Process data in batches when possible
5. **Connection Pooling**: Use connection pools for external services

### Security Considerations
1. **Validate Inputs**: Always validate and sanitize inputs
2. **Principle of Least Privilege**: Request only necessary permissions
3. **Secure Defaults**: Use secure configuration defaults
4. **Audit Logging**: Log security-relevant operations
5. **Dependency Management**: Keep dependencies updated and secure

## API Reference

For detailed API documentation, see the individual module documentation:

- [`plugin_system.py`](./plugin_system.py) - Core plugin management
- [`registry.py`](./registry.py) - Plugin discovery and registration
- [`interfaces.py`](./interfaces.py) - Plugin interfaces and contracts
- [`decorators.py`](./decorators.py) - Plugin decorators and utilities
- [`examples/`](./examples/) - Example plugin implementations

## Contributing

When contributing to the plugin system:

1. Follow the established coding patterns and conventions
2. Add comprehensive tests for new functionality
3. Update documentation for any API changes
4. Ensure security implications are considered
5. Test with various plugin types and configurations

## License

This plugin system is part of the Universal Platform and is licensed under the MIT License.