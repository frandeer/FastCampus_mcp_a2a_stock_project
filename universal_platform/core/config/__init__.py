"""
Universal Platform Configuration Management System.

A comprehensive configuration management system providing:
- Multiple configuration sources with priority ordering
- Schema-based validation with JSON Schema
- Configuration hot-reloading without restart
- Secrets management and encryption
- Environment-specific overrides
- Configuration versioning and rollback
- File change watching and remote config updates
- Type-safe configuration access
- Configuration merging and composition
- Audit logging for configuration changes

Usage:
    Basic usage:
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
    
    Advanced usage with schema and encryption:
    ```python
    from universal_platform.core.config import (
        create_config_manager, SchemaBuilder, create_secure_config_manager,
        create_file_secrets_manager
    )
    
    # Create schema
    schema = (SchemaBuilder("myapp")
              .string_field("database_url", required=True)
              .integer_field("port", default=8000, minimum=1, maximum=65535)
              .build())
    
    # Create secure manager
    secrets_manager = create_file_secrets_manager("secrets.enc")
    secure_manager = create_secure_config_manager(secrets_manager=secrets_manager)
    
    # Build configuration manager
    manager = (create_config_manager("myapp")
               .with_yaml_provider("base.yml", priority=100)
               .with_json_provider("local.json", priority=50)
               .with_env_provider("MYAPP_", priority=10)
               .with_schema(schema)
               .with_secure_manager(secure_manager)
               .with_auto_reload(True, interval=30)
               .build())
    ```
"""

from .providers import (
    ConfigProvider,
    JSONFileProvider,
    YAMLFileProvider,
    EnvironmentProvider,
    DatabaseProvider,
    RemoteProvider,
    MemoryProvider,
    create_json_provider,
    create_yaml_provider,
    create_env_provider,
    create_database_provider,
    create_remote_provider,
    create_memory_provider
)

from .schema import (
    ConfigSchema,
    SchemaField,
    SchemaType,
    SchemaBuilder,
    ValidationResult,
    ValidationError,
    ValidationRule,
    ConfigValidationError,
    BuiltinRules,
    create_database_schema,
    create_server_schema,
    create_logging_schema
)

from .encryption import (
    ConfigEncryption,
    SecretsManager,
    FileSecretsManager,
    KeyringSecretsManager,
    VaultSecretsManager,
    SecretResolver,
    SecureConfigManager,
    EncryptionError,
    create_file_secrets_manager,
    create_keyring_secrets_manager,
    create_vault_secrets_manager,
    create_secure_config_manager
)

from .hot_reload import (
    ConfigWatcher,
    HotReloadManager,
    ChangeEvent,
    ConfigChange,
    ChangeType,
    PerformanceMonitor,
    ChangeLogger,
    ConditionalReloader,
    ReloadConditions,
    create_hot_reload_manager,
    create_config_watcher,
    create_change_logger,
    create_conditional_reloader
)

from .environment import (
    EnvironmentManager,
    EnvironmentDetector,
    EnvironmentInfo,
    EnvironmentType,
    create_environment_manager,
    create_environment_detector,
    get_global_environment_manager,
    set_global_environment_manager
)

from .manager import (
    ConfigManager,
    ConfigManagerBuilder,
    ConfigurationError,
    create_config_manager,
    get_config_manager,
    set_config_manager
)

# Version information
__version__ = "1.0.0"
__author__ = "Universal Platform Team"

# Public API
__all__ = [
    # Core classes
    "ConfigManager",
    "ConfigManagerBuilder",
    "ConfigSchema",
    "SchemaBuilder",
    "ConfigWatcher",
    "HotReloadManager",
    "EnvironmentManager",
    
    # Providers
    "ConfigProvider",
    "JSONFileProvider",
    "YAMLFileProvider", 
    "EnvironmentProvider",
    "DatabaseProvider",
    "RemoteProvider",
    "MemoryProvider",
    
    # Security
    "SecureConfigManager",
    "SecretsManager",
    "FileSecretsManager",
    "KeyringSecretsManager",
    "VaultSecretsManager",
    "ConfigEncryption",
    
    # Schema and validation
    "SchemaField",
    "SchemaType",
    "ValidationResult",
    "ValidationError",
    "ValidationRule",
    "BuiltinRules",
    
    # Hot reload
    "ChangeEvent",
    "ConfigChange",
    "ChangeType",
    "PerformanceMonitor",
    "ChangeLogger",
    "ConditionalReloader",
    "ReloadConditions",
    
    # Environment
    "EnvironmentDetector",
    "EnvironmentInfo",
    "EnvironmentType",
    
    # Exceptions
    "ConfigurationError",
    "ConfigValidationError",
    "EncryptionError",
    
    # Factory functions
    "create_config_manager",
    "create_json_provider",
    "create_yaml_provider",
    "create_env_provider",
    "create_database_provider",
    "create_remote_provider",
    "create_memory_provider",
    "create_file_secrets_manager",
    "create_keyring_secrets_manager",
    "create_vault_secrets_manager",
    "create_secure_config_manager",
    "create_hot_reload_manager",
    "create_config_watcher",
    "create_change_logger",
    "create_conditional_reloader",
    "create_environment_manager",
    "create_environment_detector",
    "create_database_schema",
    "create_server_schema",
    "create_logging_schema",
    
    # Global functions
    "get_config_manager",
    "set_config_manager",
    "get_global_environment_manager",
    "set_global_environment_manager",
    
    # Version
    "__version__"
]


# Default configuration manager instance
_default_manager = None


async def initialize_default_config(config_path: str = "config.yml",
                                  env_prefix: str = "",
                                  schema: ConfigSchema = None,
                                  auto_reload: bool = True) -> ConfigManager:
    """
    Initialize default configuration manager with common settings.
    
    Args:
        config_path: Path to main configuration file
        env_prefix: Environment variable prefix
        schema: Configuration schema for validation
        auto_reload: Enable automatic reloading
        
    Returns:
        Configured ConfigManager instance
    """
    global _default_manager
    
    if _default_manager is not None:
        return _default_manager
        
    # Detect file type and create appropriate provider
    config_path = Path(config_path)
    
    builder = create_config_manager("default")
    
    if config_path.suffix.lower() == '.json':
        builder.with_json_provider(config_path, priority=100)
    else:
        builder.with_yaml_provider(config_path, priority=100)
        
    # Add environment provider
    if env_prefix:
        builder.with_env_provider(env_prefix, priority=10)
        
    # Add schema if provided
    if schema:
        builder.with_schema(schema)
        
    # Configure auto-reload
    if auto_reload:
        builder.with_auto_reload(True, interval=60)
        
    # Build and initialize
    _default_manager = builder.build()
    await _default_manager.load()
    
    # Register as global default
    set_config_manager(_default_manager, is_default=True)
    
    return _default_manager


async def get_config(key: str, default: Any = None, 
                    expected_type: Type = None) -> Any:
    """
    Get configuration value from default manager.
    
    Args:
        key: Configuration key path (dot notation)
        default: Default value if key not found
        expected_type: Expected type for validation
        
    Returns:
        Configuration value
    """
    global _default_manager
    
    if _default_manager is None:
        _default_manager = await initialize_default_config()
        
    return await _default_manager.get(key, default, expected_type)


async def set_config(key: str, value: Any) -> None:
    """
    Set configuration value in default manager.
    
    Args:
        key: Configuration key path (dot notation)
        value: Value to set
    """
    global _default_manager
    
    if _default_manager is None:
        _default_manager = await initialize_default_config()
        
    await _default_manager.set(key, value)


def add_config_change_listener(callback: Callable[[ChangeEvent], None], 
                              path: str = None) -> None:
    """
    Add configuration change listener to default manager.
    
    Args:
        callback: Function to call on configuration changes
        path: Specific path to watch (None for all changes)
    """
    global _default_manager
    
    if _default_manager is None:
        raise ConfigurationError("No default configuration manager initialized")
        
    _default_manager.add_change_listener(callback, path)


# Quick setup functions for common use cases
def setup_development_config() -> ConfigManagerBuilder:
    """Setup configuration for development environment."""
    return (create_config_manager("development")
            .with_yaml_provider("config/base.yml", priority=100)
            .with_yaml_provider("config/development.yml", priority=50)
            .with_env_provider("DEV_", priority=10)
            .with_auto_reload(True, interval=5)
            .with_caching(True, ttl=60))


def setup_production_config() -> ConfigManagerBuilder:
    """Setup configuration for production environment."""
    return (create_config_manager("production")
            .with_yaml_provider("config/base.yml", priority=100)
            .with_yaml_provider("config/production.yml", priority=50)
            .with_env_provider("PROD_", priority=10)
            .with_auto_reload(False)
            .with_caching(True, ttl=300))


def setup_testing_config() -> ConfigManagerBuilder:
    """Setup configuration for testing environment."""
    return (create_config_manager("testing")
            .with_yaml_provider("config/base.yml", priority=100)
            .with_yaml_provider("config/testing.yml", priority=50)
            .with_memory_provider({"testing": True}, priority=10)
            .with_auto_reload(False)
            .with_caching(False))


# Example usage and documentation
if __name__ == "__main__":
    import asyncio
    import logging
    
    # Setup logging
    logging.basicConfig(level=logging.INFO)
    
    async def example_usage():
        """Example usage of the configuration system."""
        
        # Create a simple schema
        schema = (SchemaBuilder("example")
                  .string_field("app_name", required=True, default="MyApp")
                  .integer_field("port", default=8000, minimum=1, maximum=65535)
                  .boolean_field("debug", default=False)
                  .string_field("database_url", required=True)
                  .build())
        
        # Create configuration manager
        manager = (create_config_manager("example")
                   .with_memory_provider({
                       "app_name": "Example App",
                       "port": 3000,
                       "debug": True,
                       "database_url": "sqlite:///example.db"
                   }, priority=100)
                   .with_env_provider("EXAMPLE_", priority=10)
                   .with_schema(schema)
                   .with_auto_reload(False)  # Disable for example
                   .build())
        
        # Load configuration
        await manager.load()
        
        # Get values
        app_name = await manager.get("app_name")
        port = await manager.get("port", expected_type=int)
        debug = await manager.get("debug", expected_type=bool)
        
        print(f"App: {app_name}")
        print(f"Port: {port}")
        print(f"Debug: {debug}")
        
        # Validate configuration
        validation_result = await manager.validate_config()
        print(f"Configuration valid: {validation_result.is_valid()}")
        
        # Get manager info
        info = manager.get_config_info()
        print(f"Manager info: {info}")
        
        await manager.close()
    
    # Run example
    asyncio.run(example_usage())