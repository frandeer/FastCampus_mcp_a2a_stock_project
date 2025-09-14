"""
Configuration manager with hot-reload, validation, and multi-provider support.
"""

import asyncio
import copy
import time
from typing import Dict, Any, Optional, List, Union, Callable, Type, get_type_hints
from pathlib import Path
from datetime import datetime, timezone
import logging
import weakref

from .providers import ConfigProvider, create_json_provider, create_yaml_provider, create_env_provider
from .schema import ConfigSchema, ValidationResult, ConfigValidationError
from .encryption import SecureConfigManager, SecretsManager
from .hot_reload import HotReloadManager, ConfigWatcher, ChangeEvent, PerformanceMonitor
from .environment import EnvironmentManager

logger = logging.getLogger(__name__)


class ConfigurationError(Exception):
    """Raised when configuration operations fail."""
    pass


class ConfigManager:
    """Main configuration manager with full feature support."""
    
    def __init__(self, name: str = "default"):
        self.name = name
        self.providers: List[ConfigProvider] = []
        self.schema: Optional[ConfigSchema] = None
        self.config: Dict[str, Any] = {}
        self.secure_manager: Optional[SecureConfigManager] = None
        self.hot_reload_manager = HotReloadManager()
        self.environment_manager = EnvironmentManager()
        self.performance_monitor = PerformanceMonitor()
        
        # Configuration state
        self.is_loaded = False
        self.last_load_time: Optional[datetime] = None
        self.load_count = 0
        self.version_counter = 0
        
        # Hot reload settings
        self.auto_reload = False
        self.reload_interval = 60  # seconds
        self.watch_tasks: List[asyncio.Task] = []
        
        # Caching
        self.enable_caching = True
        self.cache_ttl = 300  # 5 minutes
        self.cached_config: Optional[Dict[str, Any]] = None
        self.cache_timestamp: Optional[datetime] = None
        
        # Configuration access tracking
        self.access_patterns: Dict[str, int] = {}
        self.type_registry: Dict[str, Type] = {}
        
        # Thread safety
        self._lock = asyncio.Lock()
        
    def add_provider(self, provider: ConfigProvider) -> 'ConfigManager':
        """Add a configuration provider."""
        self.providers.append(provider)
        # Sort providers by priority (lower numbers = higher priority)
        self.providers.sort()
        
        # If auto-reload is enabled, start watching this provider
        if self.auto_reload:
            task = asyncio.create_task(self._watch_provider(provider))
            self.watch_tasks.append(task)
            
        return self
        
    def remove_provider(self, provider: ConfigProvider) -> 'ConfigManager':
        """Remove a configuration provider."""
        try:
            self.providers.remove(provider)
            return self
        except ValueError:
            logger.warning("Provider not found for removal")
            return self
            
    def set_schema(self, schema: ConfigSchema) -> 'ConfigManager':
        """Set configuration schema for validation."""
        self.schema = schema
        return self
        
    def set_secure_manager(self, secure_manager: SecureConfigManager) -> 'ConfigManager':
        """Set secure configuration manager."""
        self.secure_manager = secure_manager
        return self
        
    def set_environment_manager(self, env_manager: EnvironmentManager) -> 'ConfigManager':
        """Set environment manager."""
        self.environment_manager = env_manager
        return self
        
    async def load(self, force_reload: bool = False) -> 'ConfigManager':
        """Load configuration from all providers."""
        async with self._lock:
            # Check cache first
            if not force_reload and self._is_cache_valid():
                self.config = self.cached_config.copy()
                logger.debug("Configuration loaded from cache")
                return self
                
            start_time = time.time()
            
            try:
                # Load from all providers in priority order
                merged_config = {}
                
                for provider in self.providers:
                    try:
                        provider_config = await provider.load()
                        if provider_config:
                            # Merge configuration (higher priority providers override lower)
                            merged_config = self._deep_merge(merged_config, provider_config)
                            logger.debug(f"Loaded config from {provider.__class__.__name__}")
                    except Exception as e:
                        logger.error(f"Failed to load from provider {provider.__class__.__name__}: {e}")
                        # Continue with other providers
                        
                # Apply environment-specific overrides
                if self.environment_manager:
                    env_config = await self.environment_manager.get_environment_config()
                    if env_config:
                        merged_config = self._deep_merge(merged_config, env_config)
                        
                # Apply schema defaults
                if self.schema:
                    merged_config = self.schema.apply_defaults(merged_config)
                    
                # Decrypt and resolve secrets
                if self.secure_manager:
                    merged_config = await self.secure_manager.load_secure_config(merged_config)
                    
                # Validate configuration
                if self.schema:
                    validation_result = self.schema.validate(merged_config)
                    if not validation_result.is_valid():
                        error_msg = f"Configuration validation failed: {validation_result}"
                        logger.error(error_msg)
                        if self.is_loaded:
                            # Keep current config if validation fails on reload
                            logger.warning("Keeping current configuration due to validation errors")
                            return self
                        else:
                            raise ConfigValidationError(error_msg, validation_result.errors)
                            
                # Update configuration
                old_config = self.config.copy() if self.is_loaded else {}
                self.config = merged_config
                
                # Update state
                self.is_loaded = True
                self.last_load_time = datetime.now(timezone.utc)
                self.load_count += 1
                self.version_counter += 1
                
                # Update cache
                if self.enable_caching:
                    self.cached_config = self.config.copy()
                    self.cache_timestamp = datetime.now(timezone.utc)
                    
                # Record performance
                load_time = time.time() - start_time
                self.performance_monitor.record_reload_time(load_time)
                
                # Notify hot reload manager
                if old_config != self.config:
                    await self.hot_reload_manager.reload_config(
                        self.config, old_config, "config_manager"
                    )
                    
                logger.info(f"Configuration loaded successfully in {load_time:.3f}s "
                          f"(version {self.version_counter})")
                
                return self
                
            except Exception as e:
                logger.error(f"Failed to load configuration: {e}")
                if not self.is_loaded:
                    # No fallback available
                    raise ConfigurationError(f"Failed to load configuration: {e}")
                # Keep current configuration on reload failure
                return self
                
    async def get(self, key: str, default: Any = None, 
                 expected_type: Type = None) -> Any:
        """Get configuration value by key path."""
        if not self.is_loaded:
            await self.load()
            
        # Track access pattern
        self.access_patterns[key] = self.access_patterns.get(key, 0) + 1
        
        # Navigate through nested keys
        keys = key.split('.')
        value = self.config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
                
        # Type checking
        if expected_type and not isinstance(value, expected_type):
            logger.warning(f"Configuration key '{key}' expected {expected_type.__name__}, "
                         f"got {type(value).__name__}")
            
        return value
        
    async def set(self, key: str, value: Any, 
                 provider_priority: int = 0) -> 'ConfigManager':
        """Set configuration value."""
        async with self._lock:
            # Navigate to parent and set value
            keys = key.split('.')
            target = self.config
            
            for k in keys[:-1]:
                if k not in target:
                    target[k] = {}
                target = target[k]
                
            old_value = target.get(keys[-1])
            target[keys[-1]] = value
            
            # Invalidate cache
            self._invalidate_cache()
            
            # Update version
            self.version_counter += 1
            
            # Try to persist to writable providers
            await self._persist_to_providers()
            
            # Notify change
            from .hot_reload import ConfigChange, ChangeType
            changes = [ConfigChange(
                change_type=ChangeType.MODIFIED if old_value is not None else ChangeType.ADDED,
                path=key,
                old_value=old_value,
                new_value=value
            )]
            event = ChangeEvent(changes, self.config)
            await self.hot_reload_manager.watcher.notify_change(event)
            
            return self
            
    async def delete(self, key: str) -> 'ConfigManager':
        """Delete configuration key."""
        async with self._lock:
            keys = key.split('.')
            target = self.config
            
            # Navigate to parent
            for k in keys[:-1]:
                if k not in target or not isinstance(target[k], dict):
                    return self  # Key doesn't exist
                target = target[k]
                
            # Delete the key
            old_value = target.pop(keys[-1], None)
            if old_value is None:
                return self  # Key didn't exist
                
            # Invalidate cache
            self._invalidate_cache()
            
            # Update version
            self.version_counter += 1
            
            # Persist changes
            await self._persist_to_providers()
            
            # Notify change
            from .hot_reload import ConfigChange, ChangeType
            changes = [ConfigChange(
                change_type=ChangeType.DELETED,
                path=key,
                old_value=old_value,
                new_value=None
            )]
            event = ChangeEvent(changes, self.config)
            await self.hot_reload_manager.watcher.notify_change(event)
            
            return self
            
    def enable_auto_reload(self, interval: int = 60) -> 'ConfigManager':
        """Enable automatic configuration reloading."""
        self.auto_reload = True
        self.reload_interval = interval
        
        # Start watching existing providers
        for provider in self.providers:
            task = asyncio.create_task(self._watch_provider(provider))
            self.watch_tasks.append(task)
            
        return self
        
    def disable_auto_reload(self) -> 'ConfigManager':
        """Disable automatic configuration reloading."""
        self.auto_reload = False
        
        # Cancel watch tasks
        for task in self.watch_tasks:
            task.cancel()
        self.watch_tasks.clear()
        
        return self
        
    async def reload(self) -> 'ConfigManager':
        """Manually reload configuration."""
        return await self.load(force_reload=True)
        
    async def rollback(self, steps: int = 1) -> 'ConfigManager':
        """Rollback configuration to previous state."""
        rollback_config = await self.hot_reload_manager.rollback_config(steps)
        if rollback_config:
            async with self._lock:
                old_config = self.config.copy()
                self.config = rollback_config
                self.version_counter += 1
                self._invalidate_cache()
                
                # Notify change
                await self.hot_reload_manager.reload_config(
                    self.config, old_config, "rollback"
                )
                
        return self
        
    def add_change_listener(self, callback: Callable[[ChangeEvent], None], 
                          path: str = None) -> 'ConfigManager':
        """Add a configuration change listener."""
        self.hot_reload_manager.watcher.add_listener(callback, path)
        return self
        
    def remove_change_listener(self, callback: Callable[[ChangeEvent], None], 
                             path: str = None) -> 'ConfigManager':
        """Remove a configuration change listener."""
        self.hot_reload_manager.watcher.remove_listener(callback, path)
        return self
        
    def get_config_info(self) -> Dict[str, Any]:
        """Get configuration manager information."""
        return {
            "name": self.name,
            "is_loaded": self.is_loaded,
            "last_load_time": self.last_load_time.isoformat() if self.last_load_time else None,
            "load_count": self.load_count,
            "version": self.version_counter,
            "providers": [
                {
                    "type": provider.__class__.__name__,
                    "priority": provider.priority,
                    "last_modified": provider.last_modified.isoformat() if provider.last_modified else None
                }
                for provider in self.providers
            ],
            "schema": {
                "name": self.schema.name,
                "version": self.schema.version
            } if self.schema else None,
            "auto_reload": self.auto_reload,
            "reload_interval": self.reload_interval,
            "performance": self.performance_monitor.get_reload_stats(),
            "access_patterns": self.access_patterns
        }
        
    def export_config(self, include_secrets: bool = False) -> Dict[str, Any]:
        """Export current configuration."""
        config = copy.deepcopy(self.config)
        
        if not include_secrets and self.secure_manager:
            # Remove or mask sensitive data
            config = self._mask_sensitive_data(config)
            
        return {
            "config": config,
            "metadata": {
                "exported_at": datetime.now(timezone.utc).isoformat(),
                "version": self.version_counter,
                "manager_name": self.name
            }
        }
        
    async def import_config(self, config_data: Dict[str, Any], 
                          validate: bool = True) -> 'ConfigManager':
        """Import configuration data."""
        if "config" in config_data:
            new_config = config_data["config"]
        else:
            new_config = config_data
            
        if validate and self.schema:
            validation_result = self.schema.validate(new_config)
            if not validation_result.is_valid():
                raise ConfigValidationError(
                    f"Imported configuration is invalid: {validation_result}",
                    validation_result.errors
                )
                
        async with self._lock:
            old_config = self.config.copy()
            self.config = new_config
            self.version_counter += 1
            self._invalidate_cache()
            
            # Persist to providers
            await self._persist_to_providers()
            
            # Notify change
            await self.hot_reload_manager.reload_config(
                self.config, old_config, "import"
            )
            
        return self
        
    async def validate_config(self, config: Dict[str, Any] = None) -> ValidationResult:
        """Validate configuration against schema."""
        if not self.schema:
            raise ConfigurationError("No schema configured for validation")
            
        target_config = config if config is not None else self.config
        return self.schema.validate(target_config)
        
    def _deep_merge(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """Deep merge two dictionaries."""
        result = base.copy()
        
        for key, value in override.items():
            if (key in result and isinstance(result[key], dict) 
                and isinstance(value, dict)):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
                
        return result
        
    def _is_cache_valid(self) -> bool:
        """Check if cached configuration is still valid."""
        if not self.enable_caching or not self.cached_config:
            return False
            
        if not self.cache_timestamp:
            return False
            
        age = (datetime.now(timezone.utc) - self.cache_timestamp).total_seconds()
        return age < self.cache_ttl
        
    def _invalidate_cache(self) -> None:
        """Invalidate configuration cache."""
        self.cached_config = None
        self.cache_timestamp = None
        
    async def _persist_to_providers(self) -> None:
        """Persist configuration to writable providers."""
        for provider in self.providers:
            try:
                if await provider.can_write():
                    await provider.save(self.config)
                    logger.debug(f"Persisted config to {provider.__class__.__name__}")
                    break  # Save to first writable provider only
            except Exception as e:
                logger.error(f"Failed to persist to {provider.__class__.__name__}: {e}")
                
    async def _watch_provider(self, provider: ConfigProvider) -> None:
        """Watch a provider for changes."""
        try:
            await provider.watch(self._on_provider_change)
        except Exception as e:
            logger.error(f"Provider watch failed for {provider.__class__.__name__}: {e}")
            
    async def _on_provider_change(self, provider: ConfigProvider, 
                                 new_config: Dict[str, Any]) -> None:
        """Handle provider configuration changes."""
        if self.auto_reload:
            logger.info(f"Configuration change detected from {provider.__class__.__name__}")
            await self.load(force_reload=True)
            
    def _mask_sensitive_data(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Mask sensitive data in configuration."""
        masked = copy.deepcopy(config)
        
        def mask_dict(d: Dict[str, Any]) -> None:
            for key, value in d.items():
                key_lower = key.lower()
                if any(pattern in key_lower for pattern in 
                      ['password', 'secret', 'key', 'token', 'credential']):
                    d[key] = "***MASKED***"
                elif isinstance(value, dict):
                    mask_dict(value)
                    
        mask_dict(masked)
        return masked
        
    async def close(self) -> None:
        """Close configuration manager and cleanup resources."""
        # Cancel watch tasks
        for task in self.watch_tasks:
            task.cancel()
            
        # Close providers that support it
        for provider in self.providers:
            if hasattr(provider, 'close'):
                try:
                    await provider.close()
                except Exception as e:
                    logger.error(f"Error closing provider: {e}")
                    
        logger.info(f"Configuration manager '{self.name}' closed")


class ConfigManagerBuilder:
    """Fluent builder for ConfigManager."""
    
    def __init__(self, name: str = "default"):
        self.manager = ConfigManager(name)
        
    def with_json_provider(self, file_path: Union[str, Path], 
                          priority: int = 100) -> 'ConfigManagerBuilder':
        """Add JSON file provider."""
        provider = create_json_provider(file_path, priority)
        self.manager.add_provider(provider)
        return self
        
    def with_yaml_provider(self, file_path: Union[str, Path], 
                          priority: int = 100) -> 'ConfigManagerBuilder':
        """Add YAML file provider."""
        provider = create_yaml_provider(file_path, priority)
        self.manager.add_provider(provider)
        return self
        
    def with_env_provider(self, prefix: str = "", 
                         priority: int = 10) -> 'ConfigManagerBuilder':
        """Add environment variables provider."""
        provider = create_env_provider(prefix, priority)
        self.manager.add_provider(provider)
        return self
        
    def with_schema(self, schema: ConfigSchema) -> 'ConfigManagerBuilder':
        """Set configuration schema."""
        self.manager.set_schema(schema)
        return self
        
    def with_secure_manager(self, secure_manager: SecureConfigManager) -> 'ConfigManagerBuilder':
        """Set secure configuration manager."""
        self.manager.set_secure_manager(secure_manager)
        return self
        
    def with_auto_reload(self, enabled: bool = True, 
                        interval: int = 60) -> 'ConfigManagerBuilder':
        """Configure auto-reload."""
        if enabled:
            self.manager.enable_auto_reload(interval)
        return self
        
    def with_caching(self, enabled: bool = True, 
                    ttl: int = 300) -> 'ConfigManagerBuilder':
        """Configure caching."""
        self.manager.enable_caching = enabled
        self.manager.cache_ttl = ttl
        return self
        
    def build(self) -> ConfigManager:
        """Build the configuration manager."""
        return self.manager


# Global configuration manager registry
_config_managers: Dict[str, ConfigManager] = {}
_default_manager: Optional[ConfigManager] = None


def get_config_manager(name: str = "default") -> Optional[ConfigManager]:
    """Get a registered configuration manager."""
    global _default_manager
    if name == "default" and _default_manager:
        return _default_manager
    return _config_managers.get(name)


def set_config_manager(manager: ConfigManager, is_default: bool = False) -> None:
    """Register a configuration manager."""
    global _default_manager
    _config_managers[manager.name] = manager
    if is_default:
        _default_manager = manager


def create_config_manager(name: str = "default") -> ConfigManagerBuilder:
    """Create a new configuration manager using builder pattern."""
    return ConfigManagerBuilder(name)