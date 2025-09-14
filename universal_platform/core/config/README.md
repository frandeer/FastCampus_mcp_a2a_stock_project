# Universal Platform Configuration Management

A comprehensive configuration management system for the Universal Platform providing enterprise-grade features for configuration handling, validation, and hot-reloading.

## Features

### Core Features
- **Multiple Configuration Sources**: JSON, YAML, Environment Variables, Database, Remote HTTP/HTTPS, In-memory
- **Priority-based Merging**: Intelligent configuration merging with configurable priority ordering
- **Schema Validation**: JSON Schema-based validation with custom rules and type checking
- **Hot Reloading**: Runtime configuration changes without application restart
- **Environment Management**: Environment-specific configurations with inheritance
- **Secrets Management**: Encrypted secrets storage with multiple backends
- **Configuration Versioning**: Track changes and rollback to previous states
- **Audit Logging**: Complete audit trail of configuration changes
- **Performance Monitoring**: Built-in performance metrics and optimization

### Advanced Features
- **Type-safe Access**: Type checking and validation for configuration values
- **Watch File Changes**: Automatic detection of configuration file changes
- **Remote Configuration**: Support for remote configuration sources with caching
- **Conditional Reloading**: Smart reloading based on configurable conditions
- **Change Notifications**: Event-driven notifications for configuration changes
- **Configuration Export/Import**: Backup and restore configuration states

## Quick Start

### Basic Usage

```python
from universal_platform.core.config import create_config_manager

# Create and configure manager
manager = (create_config_manager("myapp")
           .with_json_provider("config.json")
           .with_env_provider("MYAPP_")
           .with_auto_reload(True)
           .build())

# Load configuration
await manager.load()

# Get configuration values
database_url = await manager.get("database.url")
port = await manager.get("server.port", default=8000, expected_type=int)
```

### With Schema Validation

```python
from universal_platform.core.config import SchemaBuilder

# Create schema
schema = (SchemaBuilder("myapp")
          .string_field("database_url", required=True)
          .integer_field("port", default=8000, minimum=1, maximum=65535)
          .boolean_field("debug", default=False)
          .build())

# Use with manager
manager = (create_config_manager("myapp")
           .with_yaml_provider("config.yml")
           .with_schema(schema)
           .build())
```

### With Secrets Management

```python
from universal_platform.core.config import (
    create_secure_config_manager, create_file_secrets_manager
)

# Create secure manager
secrets_manager = create_file_secrets_manager("secrets.enc")
secure_manager = create_secure_config_manager(secrets_manager=secrets_manager)

# Store secrets
await secrets_manager.set_secret("database.password", "secret_password")

# Configuration with secret references
config = {
    "database": {
        "url": "postgresql://user:${secret:database.password}@localhost/db"
    }
}

# Secrets are automatically resolved
resolved_config = await secure_manager.load_secure_config(config)
```

## Configuration Providers

### File Providers
- **JSON Provider**: Load configuration from JSON files
- **YAML Provider**: Load configuration from YAML files with full YAML support

### Environment Provider
- **Environment Variables**: Load from environment variables with prefix support
- **Auto-type Detection**: Automatic JSON parsing for complex values

### Database Provider
- **PostgreSQL**: Store configuration in PostgreSQL with JSONB support
- **SQLite**: Lightweight database storage option

### Remote Provider
- **HTTP/HTTPS**: Load configuration from remote endpoints
- **Caching**: Built-in caching and conditional requests (ETag, Last-Modified)

### Memory Provider
- **In-Memory**: For testing and temporary configurations

## Schema System

### Field Types
- String fields with pattern matching, length constraints, format validation
- Integer and number fields with min/max constraints
- Boolean fields
- Array fields with item validation
- Object fields with nested schemas
- Custom validation rules

### Built-in Validators
- URL format validation
- Email format validation
- Port number validation
- File/directory existence validation
- Custom regex patterns

### Example Schema

```python
schema = (SchemaBuilder("app")
          .string_field("app_name", required=True, min_length=1)
          .integer_field("port", default=8000, minimum=1, maximum=65535)
          .string_field("database_url", required=True, format="url")
          .boolean_field("debug", default=False)
          .array_field("allowed_hosts", 
                      items=SchemaField("host", SchemaType.STRING))
          .build())
```

## Environment Management

### Environment Types
- Development
- Testing  
- Staging
- Production
- Custom environments

### Environment Detection
Automatic environment detection based on:
- Environment variables
- Hostname patterns
- Git branch names
- Process context
- Marker files

### Environment Inheritance

```python
from universal_platform.core.config import EnvironmentManager

env_manager = EnvironmentManager()

# Inheritance: base -> development -> local
env_manager.register_environment(EnvironmentInfo(
    name="local",
    type=EnvironmentType.DEVELOPMENT,
    parent="development"
))
```

## Hot Reloading

### Change Detection
- File system watching
- Database polling
- Remote endpoint monitoring
- Manual triggers

### Change Notifications

```python
def on_config_change(event: ChangeEvent):
    for change in event.changes:
        print(f"Changed: {change.path} = {change.new_value}")

manager.add_change_listener(on_config_change)
```

### Conditional Reloading

```python
from universal_platform.core.config import ReloadConditions

# Only reload during maintenance window
condition = ReloadConditions.during_time_window(2, 6)  # 2 AM to 6 AM

conditional_reloader = create_conditional_reloader(hot_reload_manager)
conditional_reloader.add_condition(condition)
```

## Secrets Management

### Secrets Backends
- **File-based**: Encrypted local file storage
- **System Keyring**: OS keyring integration
- **HashiCorp Vault**: Enterprise secrets management
- **Custom**: Implement your own secrets backend

### Secret References
Use `${secret:key}` syntax in configuration:

```yaml
database:
  url: "postgresql://user:${secret:db.password}@localhost/myapp"
api:
  key: "${secret:api.key}"
```

## Performance Features

### Caching
- Configurable TTL
- Memory-efficient storage
- Cache invalidation on changes

### Performance Monitoring
- Load time tracking
- Configuration access patterns
- Resource usage monitoring

### Optimization
- Lazy loading
- Parallel provider loading
- Smart cache management

## Error Handling

### Validation Errors
- Detailed validation messages
- Field-level error reporting
- Warning vs error classification

### Provider Failures
- Graceful degradation
- Fallback mechanisms
- Error recovery strategies

### Rollback Support
- Configuration history
- Automatic rollback on validation failures
- Manual rollback capabilities

## Testing Support

### Test Utilities
- Memory providers for testing
- Configuration mocking
- Isolated test environments

### Example Test Setup

```python
async def test_config():
    manager = (create_config_manager("test")
               .with_memory_provider({
                   "database_url": "sqlite:///:memory:",
                   "debug": True
               })
               .build())
    
    await manager.load()
    assert await manager.get("debug") is True
```

## Best Practices

### Configuration Organization
1. Use hierarchical configuration structure
2. Separate concerns (database, server, logging, etc.)
3. Use environment-specific overrides
4. Keep secrets separate from regular config

### Schema Design
1. Define schemas for all configuration
2. Use sensible defaults
3. Add descriptive field documentation
4. Implement custom validation rules

### Security
1. Never commit secrets to version control
2. Use encrypted secrets storage
3. Rotate encryption keys regularly
4. Audit configuration changes

### Performance
1. Enable caching for production
2. Use appropriate provider priorities
3. Monitor configuration load times
4. Avoid excessive hot reloading in production

## Examples

See `examples.py` for comprehensive usage examples including:
- Basic configuration management
- Schema validation
- Multi-provider setup
- Hot reloading
- Environment management
- Secrets handling
- Performance monitoring

## Requirements

- Python 3.8+
- `asyncio` for async operations
- `aiofiles` for async file operations
- `aiohttp` for remote providers
- `cryptography` for encryption
- `jsonschema` for validation
- `keyring` for system keyring (optional)
- `hvac` for HashiCorp Vault (optional)
- `asyncpg` for PostgreSQL (optional)
- `yaml` for YAML support

## License

Part of the Universal Platform project.