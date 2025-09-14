"""
Example configurations and usage patterns for the configuration management system.
"""

import asyncio
import logging
from pathlib import Path
from typing import Dict, Any

from . import (
    create_config_manager, SchemaBuilder, create_secure_config_manager,
    create_file_secrets_manager, EnvironmentManager, ChangeEvent
)

# Setup logging for examples
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def basic_example():
    """Basic configuration management example."""
    print("\n=== Basic Configuration Example ===")
    
    # Create a simple configuration manager
    manager = (create_config_manager("basic_example")
               .with_memory_provider({
                   "app": {
                       "name": "My Application",
                       "version": "1.0.0",
                       "debug": True
                   },
                   "server": {
                       "host": "localhost",
                       "port": 8000
                   },
                   "database": {
                       "url": "sqlite:///app.db",
                       "pool_size": 5
                   }
               })
               .build())
    
    # Load configuration
    await manager.load()
    
    # Get configuration values
    app_name = await manager.get("app.name")
    port = await manager.get("server.port", expected_type=int)
    debug = await manager.get("app.debug", expected_type=bool)
    
    print(f"Application: {app_name}")
    print(f"Port: {port}")
    print(f"Debug mode: {debug}")
    
    # Set a new value
    await manager.set("server.port", 9000)
    new_port = await manager.get("server.port")
    print(f"Updated port: {new_port}")
    
    await manager.close()


async def schema_validation_example():
    """Schema validation example."""
    print("\n=== Schema Validation Example ===")
    
    # Create a schema
    schema = (SchemaBuilder("app_schema")
              .string_field("app_name", "Application name", required=True)
              .integer_field("port", "Server port", default=8000, minimum=1, maximum=65535)
              .boolean_field("debug", "Debug mode", default=False)
              .string_field("database_url", "Database connection URL", required=True)
              .number_field("timeout", "Request timeout", default=30.0, minimum=0.1)
              .build())
    
    # Create manager with schema
    manager = (create_config_manager("schema_example")
               .with_memory_provider({
                   "app_name": "Schema Example App",
                   "port": 3000,
                   "debug": True,
                   "database_url": "postgresql://user:pass@localhost/db",
                   "timeout": 45.5
               })
               .with_schema(schema)
               .build())
    
    # Load and validate
    await manager.load()
    
    # Validate current configuration
    validation_result = await manager.validate_config()
    print(f"Configuration is valid: {validation_result.is_valid()}")
    
    if validation_result.warnings:
        print("Warnings:")
        for warning in validation_result.warnings:
            print(f"  - {warning.path}: {warning.message}")
    
    # Try setting an invalid value
    try:
        await manager.set("port", 99999)  # Out of range
        validation_result = await manager.validate_config()
        if not validation_result.is_valid():
            print("Validation errors after setting invalid port:")
            for error in validation_result.errors:
                print(f"  - {error.path}: {error.message}")
    except Exception as e:
        print(f"Error setting invalid port: {e}")
    
    await manager.close()


async def multi_provider_example():
    """Multiple providers with priority example."""
    print("\n=== Multi-Provider Example ===")
    
    # Create temporary config files
    base_config = {
        "app": {"name": "Base App", "version": "1.0.0"},
        "server": {"host": "0.0.0.0", "port": 8000},
        "features": {"feature_a": True, "feature_b": False}
    }
    
    local_config = {
        "app": {"name": "Local App"},  # Override app name
        "server": {"port": 3000},      # Override port
        "features": {"feature_b": True}  # Override feature_b
    }
    
    # Create manager with multiple providers
    manager = (create_config_manager("multi_provider")
               .with_memory_provider(base_config, priority=100)  # Lower priority (base)
               .with_memory_provider(local_config, priority=50)  # Higher priority (overrides)
               .build())
    
    await manager.load()
    
    # Show merged configuration
    app_name = await manager.get("app.name")
    version = await manager.get("app.version")
    port = await manager.get("server.port")
    feature_a = await manager.get("features.feature_a")
    feature_b = await manager.get("features.feature_b")
    
    print(f"App name: {app_name} (overridden by local config)")
    print(f"Version: {version} (from base config)")
    print(f"Port: {port} (overridden by local config)")
    print(f"Feature A: {feature_a} (from base config)")
    print(f"Feature B: {feature_b} (overridden by local config)")
    
    await manager.close()


async def hot_reload_example():
    """Hot reload example."""
    print("\n=== Hot Reload Example ===")
    
    # Configuration change listener
    def on_config_change(event: ChangeEvent):
        print(f"Configuration changed! {len(event.changes)} changes detected:")
        for change in event.changes:
            print(f"  - {change.change_type.value}: {change.path}")
            if change.old_value is not None:
                print(f"    Old: {change.old_value}")
            if change.new_value is not None:
                print(f"    New: {change.new_value}")
    
    # Create manager with hot reload
    manager = (create_config_manager("hot_reload_example")
               .with_memory_provider({"value": 100})
               .build())
    
    # Add change listener
    manager.add_change_listener(on_config_change)
    
    await manager.load()
    
    # Make some changes
    print("Making configuration changes...")
    await manager.set("value", 200)
    await manager.set("new_key", "new_value")
    await manager.delete("value")
    
    await manager.close()


async def environment_example():
    """Environment management example."""
    print("\n=== Environment Management Example ===")
    
    # Create environment manager
    env_manager = EnvironmentManager()
    
    # Set current environment
    env_manager.set_current_environment("development")
    
    # Get environment info
    current_env = env_manager.get_current_environment()
    env_info = env_manager.get_environment_info()
    inheritance_chain = env_manager.get_inheritance_chain()
    
    print(f"Current environment: {current_env}")
    print(f"Environment type: {env_info.type.value}")
    print(f"Description: {env_info.description}")
    print(f"Inheritance chain: {' -> '.join(inheritance_chain)}")
    
    # Create environment-specific providers
    providers = env_manager.create_environment_providers()
    print(f"Created {len(providers)} environment-specific providers")
    
    # Get environment tree
    env_tree = env_manager.get_environment_tree()
    print("Environment tree:")
    for root in env_tree["roots"]:
        print(f"  {root['name']} ({root['type']})")
        for child in root["children"]:
            print(f"    └── {child['name']} ({child['type']})")


async def secrets_example():
    """Secrets management example."""
    print("\n=== Secrets Management Example ===")
    
    # Create a temporary secrets file
    import tempfile
    with tempfile.NamedTemporaryFile(suffix='.secrets', delete=False) as f:
        secrets_file = f.name
    
    try:
        # Create secrets manager
        secrets_manager = create_file_secrets_manager(secrets_file)
        
        # Store some secrets
        await secrets_manager.set_secret("database.password", "super_secret_pass")
        await secrets_manager.set_secret("api.key", "abc123xyz789")
        
        # Create secure configuration manager
        secure_manager = create_secure_config_manager(secrets_manager=secrets_manager)
        
        # Configuration with secret references
        config_with_secrets = {
            "database": {
                "host": "localhost",
                "username": "user",
                "password": "${secret:database.password}"  # Secret reference
            },
            "api": {
                "endpoint": "https://api.example.com",
                "key": "${secret:api.key}"  # Secret reference
            },
            "public_info": "This is not secret"
        }
        
        # Load and resolve secrets
        resolved_config = await secure_manager.load_secure_config(config_with_secrets)
        
        print("Original config with secret references:")
        print(f"  Database password: {config_with_secrets['database']['password']}")
        print(f"  API key: {config_with_secrets['api']['key']}")
        
        print("Resolved config with actual secrets:")
        print(f"  Database password: {resolved_config['database']['password']}")
        print(f"  API key: {resolved_config['api']['key']}")
        
    finally:
        # Cleanup
        Path(secrets_file).unlink(missing_ok=True)


async def performance_monitoring_example():
    """Performance monitoring example."""
    print("\n=== Performance Monitoring Example ===")
    
    manager = (create_config_manager("perf_example")
               .with_memory_provider({"test": "value"})
               .build())
    
    # Load multiple times to generate performance data
    for i in range(5):
        await manager.load(force_reload=True)
        await asyncio.sleep(0.1)  # Small delay
    
    # Get performance statistics
    info = manager.get_config_info()
    perf_stats = info["performance"]
    
    print(f"Load count: {perf_stats['count']}")
    print(f"Average load time: {perf_stats['average']:.4f}s")
    print(f"Min load time: {perf_stats['min']:.4f}s")
    print(f"Max load time: {perf_stats['max']:.4f}s")
    
    await manager.close()


async def main():
    """Run all examples."""
    print("Configuration Management System Examples")
    print("=" * 50)
    
    examples = [
        basic_example,
        schema_validation_example,
        multi_provider_example,
        hot_reload_example,
        environment_example,
        secrets_example,
        performance_monitoring_example
    ]
    
    for example in examples:
        try:
            await example()
            await asyncio.sleep(0.5)  # Small delay between examples
        except Exception as e:
            logger.error(f"Error in {example.__name__}: {e}")
    
    print("\nAll examples completed!")


if __name__ == "__main__":
    asyncio.run(main())