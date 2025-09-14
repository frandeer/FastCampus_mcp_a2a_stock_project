"""
Per-tenant configuration management.

Provides hierarchical configuration management with tenant-specific overrides,
environment-based settings, feature flags, and dynamic configuration updates.
"""

import json
import logging
import os
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Type, TypeVar, Union

import yaml
from pydantic import BaseModel, Field, validator

from .tenant_context import get_current_tenant, get_current_tenant_safe

logger = logging.getLogger(__name__)

T = TypeVar('T')


class ConfigurationScope(Enum):
    """Configuration scope levels."""
    
    SYSTEM = "system"
    """System-wide configuration"""
    
    TENANT = "tenant"
    """Tenant-specific configuration"""
    
    USER = "user"
    """User-specific configuration"""
    
    SESSION = "session"
    """Session-specific configuration"""


class ConfigurationSource(Enum):
    """Configuration sources in order of precedence."""
    
    DEFAULT = "default"
    """Default hardcoded values"""
    
    FILE = "file"
    """Configuration files"""
    
    ENVIRONMENT = "environment"
    """Environment variables"""
    
    DATABASE = "database"
    """Database stored configuration"""
    
    RUNTIME = "runtime"
    """Runtime dynamic configuration"""


@dataclass
class ConfigurationEntry:
    """Individual configuration entry with metadata."""
    
    key: str
    value: Any
    source: ConfigurationSource
    scope: ConfigurationScope
    tenant_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    is_encrypted: bool = False
    is_sensitive: bool = False
    description: Optional[str] = None
    validation_schema: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        """Post-initialization processing."""
        if self.is_sensitive:
            self.is_encrypted = True


class TenantSettings(BaseModel):
    """
    Base model for tenant-specific settings.
    
    Can be extended to add application-specific configuration fields.
    """
    
    tenant_id: str = Field(..., description="Tenant identifier")
    tenant_name: str = Field(..., description="Tenant display name")
    
    # Basic tenant settings
    is_active: bool = Field(True, description="Whether tenant is active")
    max_users: Optional[int] = Field(None, description="Maximum number of users")
    max_storage: Optional[int] = Field(None, description="Maximum storage in MB")
    
    # Feature flags
    features: Dict[str, bool] = Field(default_factory=dict, description="Feature flags")
    
    # Customization settings
    theme: Dict[str, Any] = Field(default_factory=dict, description="UI theme settings")
    branding: Dict[str, Any] = Field(default_factory=dict, description="Branding configuration")
    
    # Integration settings
    integrations: Dict[str, Dict[str, Any]] = Field(default_factory=dict, description="Third-party integrations")
    
    # Business settings
    timezone: str = Field("UTC", description="Default timezone")
    currency: str = Field("USD", description="Default currency")
    locale: str = Field("en-US", description="Default locale")
    
    # Security settings
    password_policy: Dict[str, Any] = Field(default_factory=dict, description="Password policy settings")
    session_timeout: int = Field(3600, description="Session timeout in seconds")
    
    # Notification settings
    notification_settings: Dict[str, Any] = Field(default_factory=dict, description="Notification preferences")
    
    # Custom fields for application-specific settings
    custom_settings: Dict[str, Any] = Field(default_factory=dict, description="Custom tenant settings")
    
    @validator('max_users')
    def validate_max_users(cls, v):
        """Validate max_users is positive."""
        if v is not None and v <= 0:
            raise ValueError('max_users must be positive')
        return v
    
    @validator('max_storage')
    def validate_max_storage(cls, v):
        """Validate max_storage is positive."""
        if v is not None and v <= 0:
            raise ValueError('max_storage must be positive')
        return v
    
    @validator('session_timeout')
    def validate_session_timeout(cls, v):
        """Validate session timeout is reasonable."""
        if v < 300 or v > 86400:  # 5 minutes to 24 hours
            raise ValueError('session_timeout must be between 300 and 86400 seconds')
        return v
    
    def has_feature(self, feature_name: str) -> bool:
        """Check if a feature is enabled."""
        return self.features.get(feature_name, False)
    
    def get_custom_setting(self, key: str, default: Any = None) -> Any:
        """Get a custom setting value."""
        return self.custom_settings.get(key, default)
    
    def set_custom_setting(self, key: str, value: Any) -> None:
        """Set a custom setting value."""
        self.custom_settings[key] = value


class ConfigurationProvider(ABC):
    """Abstract base class for configuration providers."""
    
    @abstractmethod
    def get(self, key: str, default: Any = None, tenant_id: Optional[str] = None) -> Any:
        """Get a configuration value."""
        pass
    
    @abstractmethod
    def set(self, key: str, value: Any, tenant_id: Optional[str] = None) -> None:
        """Set a configuration value."""
        pass
    
    @abstractmethod
    def has(self, key: str, tenant_id: Optional[str] = None) -> bool:
        """Check if a configuration key exists."""
        pass
    
    @abstractmethod
    def delete(self, key: str, tenant_id: Optional[str] = None) -> bool:
        """Delete a configuration key."""
        pass
    
    @abstractmethod
    def get_all(self, tenant_id: Optional[str] = None) -> Dict[str, Any]:
        """Get all configuration for a tenant."""
        pass
    
    @property
    @abstractmethod
    def source(self) -> ConfigurationSource:
        """Get the configuration source."""
        pass


class FileConfigurationProvider(ConfigurationProvider):
    """Configuration provider that reads from files."""
    
    def __init__(self, config_dir: Union[str, Path], file_format: str = "yaml"):
        """
        Initialize file configuration provider.
        
        Args:
            config_dir: Directory containing configuration files
            file_format: Configuration file format (yaml, json)
        """
        self.config_dir = Path(config_dir)
        self.file_format = file_format.lower()
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._load_configurations()
    
    def _load_configurations(self):
        """Load all configuration files."""
        if not self.config_dir.exists():
            logger.warning(f"Configuration directory does not exist: {self.config_dir}")
            return
        
        # Load system configuration
        system_file = self.config_dir / f"system.{self.file_format}"
        if system_file.exists():
            self._cache["system"] = self._load_file(system_file)
        
        # Load tenant-specific configurations
        for tenant_file in self.config_dir.glob(f"tenant-*.{self.file_format}"):
            tenant_id = tenant_file.stem.replace("tenant-", "")
            self._cache[tenant_id] = self._load_file(tenant_file)
    
    def _load_file(self, file_path: Path) -> Dict[str, Any]:
        """Load configuration from a file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                if self.file_format == "yaml":
                    return yaml.safe_load(f) or {}
                elif self.file_format == "json":
                    return json.load(f)
                else:
                    raise ValueError(f"Unsupported file format: {self.file_format}")
        except Exception as e:
            logger.error(f"Error loading configuration file {file_path}: {e}")
            return {}
    
    def get(self, key: str, default: Any = None, tenant_id: Optional[str] = None) -> Any:
        """Get configuration value from file."""
        # Get tenant-specific config first, then fall back to system
        configs_to_check = []
        
        if tenant_id:
            configs_to_check.append(self._cache.get(tenant_id, {}))
        
        configs_to_check.append(self._cache.get("system", {}))
        
        for config in configs_to_check:
            if self._has_nested_key(config, key):
                return self._get_nested_value(config, key)
        
        return default
    
    def set(self, key: str, value: Any, tenant_id: Optional[str] = None) -> None:
        """Set configuration value (not supported for file provider)."""
        raise NotImplementedError("File configuration provider is read-only")
    
    def has(self, key: str, tenant_id: Optional[str] = None) -> bool:
        """Check if configuration key exists."""
        return self.get(key, None, tenant_id) is not None
    
    def delete(self, key: str, tenant_id: Optional[str] = None) -> bool:
        """Delete configuration key (not supported for file provider)."""
        raise NotImplementedError("File configuration provider is read-only")
    
    def get_all(self, tenant_id: Optional[str] = None) -> Dict[str, Any]:
        """Get all configuration."""
        result = self._cache.get("system", {}).copy()
        
        if tenant_id and tenant_id in self._cache:
            result.update(self._cache[tenant_id])
        
        return result
    
    @property
    def source(self) -> ConfigurationSource:
        """Get the configuration source."""
        return ConfigurationSource.FILE
    
    def _has_nested_key(self, config: Dict[str, Any], key: str) -> bool:
        """Check if nested key exists in configuration."""
        keys = key.split('.')
        current = config
        
        for k in keys:
            if not isinstance(current, dict) or k not in current:
                return False
            current = current[k]
        
        return True
    
    def _get_nested_value(self, config: Dict[str, Any], key: str) -> Any:
        """Get value from nested configuration key."""
        keys = key.split('.')
        current = config
        
        for k in keys:
            current = current[k]
        
        return current


class EnvironmentConfigurationProvider(ConfigurationProvider):
    """Configuration provider that reads from environment variables."""
    
    def __init__(self, prefix: str = "APP_"):
        """
        Initialize environment configuration provider.
        
        Args:
            prefix: Prefix for environment variables
        """
        self.prefix = prefix
    
    def _env_key(self, key: str, tenant_id: Optional[str] = None) -> str:
        """Generate environment variable name."""
        env_key = key.replace('.', '_').upper()
        
        if tenant_id:
            return f"{self.prefix}TENANT_{tenant_id.upper()}_{env_key}"
        else:
            return f"{self.prefix}{env_key}"
    
    def get(self, key: str, default: Any = None, tenant_id: Optional[str] = None) -> Any:
        """Get configuration value from environment."""
        # Try tenant-specific first, then global
        env_keys = []
        
        if tenant_id:
            env_keys.append(self._env_key(key, tenant_id))
        
        env_keys.append(self._env_key(key))
        
        for env_key in env_keys:
            value = os.getenv(env_key)
            if value is not None:
                return self._parse_env_value(value)
        
        return default
    
    def set(self, key: str, value: Any, tenant_id: Optional[str] = None) -> None:
        """Set configuration value (not supported for environment provider)."""
        raise NotImplementedError("Environment configuration provider is read-only")
    
    def has(self, key: str, tenant_id: Optional[str] = None) -> bool:
        """Check if configuration key exists."""
        return self.get(key, None, tenant_id) is not None
    
    def delete(self, key: str, tenant_id: Optional[str] = None) -> bool:
        """Delete configuration key (not supported for environment provider)."""
        raise NotImplementedError("Environment configuration provider is read-only")
    
    def get_all(self, tenant_id: Optional[str] = None) -> Dict[str, Any]:
        """Get all configuration from environment."""
        result = {}
        
        # Get all environment variables with our prefix
        for env_key, value in os.environ.items():
            if env_key.startswith(self.prefix):
                # Parse key structure
                key_part = env_key[len(self.prefix):]
                
                if tenant_id and key_part.startswith(f"TENANT_{tenant_id.upper()}_"):
                    # Tenant-specific variable
                    config_key = key_part[len(f"TENANT_{tenant_id.upper()}_"):].lower().replace('_', '.')
                    result[config_key] = self._parse_env_value(value)
                elif not key_part.startswith("TENANT_"):
                    # Global variable
                    config_key = key_part.lower().replace('_', '.')
                    result[config_key] = self._parse_env_value(value)
        
        return result
    
    @property
    def source(self) -> ConfigurationSource:
        """Get the configuration source."""
        return ConfigurationSource.ENVIRONMENT
    
    def _parse_env_value(self, value: str) -> Any:
        """Parse environment variable value to appropriate type."""
        # Handle boolean values
        if value.lower() in ('true', 'false'):
            return value.lower() == 'true'
        
        # Handle numeric values
        try:
            if '.' in value:
                return float(value)
            return int(value)
        except ValueError:
            pass
        
        # Handle JSON values
        if value.startswith(('{', '[')):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                pass
        
        return value


class DatabaseConfigurationProvider(ConfigurationProvider):
    """Configuration provider that stores configuration in database."""
    
    def __init__(self, session_factory, table_name: str = "tenant_configurations"):
        """
        Initialize database configuration provider.
        
        Args:
            session_factory: SQLAlchemy session factory
            table_name: Name of configuration table
        """
        self.session_factory = session_factory
        self.table_name = table_name
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._cache_timeout = 300  # 5 minutes
        self._last_cache_update: Dict[str, datetime] = {}
    
    def get(self, key: str, default: Any = None, tenant_id: Optional[str] = None) -> Any:
        """Get configuration value from database."""
        self._ensure_cache_fresh(tenant_id)
        
        cache_key = tenant_id or "system"
        tenant_config = self._cache.get(cache_key, {})
        
        return tenant_config.get(key, default)
    
    def set(self, key: str, value: Any, tenant_id: Optional[str] = None) -> None:
        """Set configuration value in database."""
        from sqlalchemy import text
        
        session = self.session_factory()
        try:
            # Upsert configuration entry
            upsert_query = text(f"""
                INSERT INTO {self.table_name} (key, value, tenant_id, created_at, updated_at)
                VALUES (:key, :value, :tenant_id, :created_at, :updated_at)
                ON CONFLICT (key, COALESCE(tenant_id, '')) 
                DO UPDATE SET 
                    value = EXCLUDED.value,
                    updated_at = EXCLUDED.updated_at
            """)
            
            session.execute(upsert_query, {
                'key': key,
                'value': json.dumps(value),
                'tenant_id': tenant_id,
                'created_at': datetime.utcnow(),
                'updated_at': datetime.utcnow()
            })
            
            session.commit()
            
            # Update cache
            cache_key = tenant_id or "system"
            if cache_key in self._cache:
                self._cache[cache_key][key] = value
        
        finally:
            session.close()
    
    def has(self, key: str, tenant_id: Optional[str] = None) -> bool:
        """Check if configuration key exists."""
        return self.get(key, None, tenant_id) is not None
    
    def delete(self, key: str, tenant_id: Optional[str] = None) -> bool:
        """Delete configuration key from database."""
        from sqlalchemy import text
        
        session = self.session_factory()
        try:
            delete_query = text(f"""
                DELETE FROM {self.table_name} 
                WHERE key = :key AND (tenant_id = :tenant_id OR (tenant_id IS NULL AND :tenant_id IS NULL))
            """)
            
            result = session.execute(delete_query, {
                'key': key,
                'tenant_id': tenant_id
            })
            
            session.commit()
            
            # Update cache
            cache_key = tenant_id or "system"
            if cache_key in self._cache and key in self._cache[cache_key]:
                del self._cache[cache_key][key]
            
            return result.rowcount > 0
        
        finally:
            session.close()
    
    def get_all(self, tenant_id: Optional[str] = None) -> Dict[str, Any]:
        """Get all configuration for a tenant."""
        self._ensure_cache_fresh(tenant_id)
        
        cache_key = tenant_id or "system"
        return self._cache.get(cache_key, {}).copy()
    
    @property
    def source(self) -> ConfigurationSource:
        """Get the configuration source."""
        return ConfigurationSource.DATABASE
    
    def _ensure_cache_fresh(self, tenant_id: Optional[str] = None):
        """Ensure cache is fresh for the given tenant."""
        cache_key = tenant_id or "system"
        last_update = self._last_cache_update.get(cache_key)
        
        if (not last_update or 
            (datetime.utcnow() - last_update).seconds > self._cache_timeout):
            self._load_tenant_config(tenant_id)
    
    def _load_tenant_config(self, tenant_id: Optional[str] = None):
        """Load configuration from database for a tenant."""
        from sqlalchemy import text
        
        session = self.session_factory()
        try:
            query = text(f"""
                SELECT key, value FROM {self.table_name} 
                WHERE tenant_id = :tenant_id OR (tenant_id IS NULL AND :tenant_id IS NULL)
            """)
            
            result = session.execute(query, {'tenant_id': tenant_id})
            
            config = {}
            for row in result:
                try:
                    config[row.key] = json.loads(row.value)
                except json.JSONDecodeError:
                    config[row.key] = row.value
            
            cache_key = tenant_id or "system"
            self._cache[cache_key] = config
            self._last_cache_update[cache_key] = datetime.utcnow()
        
        finally:
            session.close()


class TenantConfigurationManager:
    """
    Main configuration manager for tenant-aware applications.
    
    Provides hierarchical configuration with multiple providers
    and automatic tenant context resolution.
    """
    
    def __init__(self):
        """Initialize configuration manager."""
        self.providers: List[ConfigurationProvider] = []
        self.defaults: Dict[str, Any] = {}
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._tenant_settings_cache: Dict[str, TenantSettings] = {}
    
    def add_provider(self, provider: ConfigurationProvider):
        """
        Add a configuration provider.
        
        Providers are checked in the order they are added,
        with later providers taking precedence.
        """
        self.providers.append(provider)
    
    def set_defaults(self, defaults: Dict[str, Any]):
        """Set default configuration values."""
        self.defaults.update(defaults)
    
    def get(self, key: str, default: Any = None, tenant_id: Optional[str] = None) -> Any:
        """
        Get configuration value with hierarchical lookup.
        
        Args:
            key: Configuration key (supports dot notation)
            default: Default value if not found
            tenant_id: Specific tenant ID (uses current tenant if None)
            
        Returns:
            Any: Configuration value
        """
        if tenant_id is None:
            context = get_current_tenant_safe()
            tenant_id = context.tenant_id if context else None
        
        # Check providers in reverse order (later providers have higher precedence)
        for provider in reversed(self.providers):
            try:
                value = provider.get(key, None, tenant_id)
                if value is not None:
                    return value
            except Exception as e:
                logger.warning(f"Error getting config from {provider.source.value}: {e}")
        
        # Check defaults
        if self._has_nested_key(self.defaults, key):
            return self._get_nested_value(self.defaults, key)
        
        return default
    
    def set(self, key: str, value: Any, tenant_id: Optional[str] = None, persist: bool = True):
        """
        Set configuration value.
        
        Args:
            key: Configuration key
            value: Configuration value
            tenant_id: Specific tenant ID (uses current tenant if None)
            persist: Whether to persist to writable providers
        """
        if tenant_id is None:
            context = get_current_tenant_safe()
            tenant_id = context.tenant_id if context else None
        
        if persist:
            # Set in writable providers (typically database provider)
            for provider in self.providers:
                if hasattr(provider, 'set') and callable(provider.set):
                    try:
                        provider.set(key, value, tenant_id)
                        break  # Set in first writable provider
                    except NotImplementedError:
                        continue
                    except Exception as e:
                        logger.error(f"Error setting config in {provider.source.value}: {e}")
        
        # Update cache
        cache_key = tenant_id or "system"
        if cache_key not in self._cache:
            self._cache[cache_key] = {}
        self._cache[cache_key][key] = value
    
    def has(self, key: str, tenant_id: Optional[str] = None) -> bool:
        """Check if configuration key exists."""
        return self.get(key, None, tenant_id) is not None
    
    def delete(self, key: str, tenant_id: Optional[str] = None) -> bool:
        """Delete configuration key."""
        if tenant_id is None:
            context = get_current_tenant_safe()
            tenant_id = context.tenant_id if context else None
        
        # Delete from writable providers
        deleted = False
        for provider in self.providers:
            if hasattr(provider, 'delete') and callable(provider.delete):
                try:
                    if provider.delete(key, tenant_id):
                        deleted = True
                except NotImplementedError:
                    continue
                except Exception as e:
                    logger.error(f"Error deleting config from {provider.source.value}: {e}")
        
        # Update cache
        cache_key = tenant_id or "system"
        if cache_key in self._cache and key in self._cache[cache_key]:
            del self._cache[cache_key][key]
        
        return deleted
    
    def get_all(self, tenant_id: Optional[str] = None) -> Dict[str, Any]:
        """Get all configuration for a tenant."""
        if tenant_id is None:
            context = get_current_tenant_safe()
            tenant_id = context.tenant_id if context else None
        
        result = self.defaults.copy()
        
        # Merge from all providers
        for provider in self.providers:
            try:
                provider_config = provider.get_all(tenant_id)
                result.update(provider_config)
            except Exception as e:
                logger.warning(f"Error getting all config from {provider.source.value}: {e}")
        
        return result
    
    def get_tenant_settings(self, tenant_id: Optional[str] = None) -> TenantSettings:
        """
        Get tenant settings as a structured object.
        
        Args:
            tenant_id: Specific tenant ID (uses current tenant if None)
            
        Returns:
            TenantSettings: Tenant settings object
        """
        if tenant_id is None:
            context = get_current_tenant_safe()
            tenant_id = context.tenant_id if context else None
        
        if not tenant_id:
            raise ValueError("No tenant ID available")
        
        # Check cache first
        if tenant_id in self._tenant_settings_cache:
            return self._tenant_settings_cache[tenant_id]
        
        # Get all configuration for tenant
        config = self.get_all(tenant_id)
        
        # Extract tenant settings
        settings_data = {
            'tenant_id': tenant_id,
            'tenant_name': config.get('tenant.name', tenant_id),
            **config
        }
        
        # Create tenant settings object
        settings = TenantSettings(**settings_data)
        
        # Cache for future use
        self._tenant_settings_cache[tenant_id] = settings
        
        return settings
    
    def update_tenant_settings(self, settings: TenantSettings, persist: bool = True):
        """
        Update tenant settings.
        
        Args:
            settings: Updated tenant settings
            persist: Whether to persist changes
        """
        tenant_id = settings.tenant_id
        
        # Convert to dictionary
        settings_dict = settings.dict()
        
        # Update individual configuration keys
        for key, value in settings_dict.items():
            if key != 'tenant_id':
                self.set(f"tenant.{key}", value, tenant_id, persist)
        
        # Update cache
        self._tenant_settings_cache[tenant_id] = settings
    
    def clear_cache(self, tenant_id: Optional[str] = None):
        """Clear configuration cache."""
        if tenant_id:
            cache_key = tenant_id
            self._cache.pop(cache_key, None)
            self._tenant_settings_cache.pop(tenant_id, None)
        else:
            self._cache.clear()
            self._tenant_settings_cache.clear()
    
    def _has_nested_key(self, config: Dict[str, Any], key: str) -> bool:
        """Check if nested key exists in configuration."""
        keys = key.split('.')
        current = config
        
        for k in keys:
            if not isinstance(current, dict) or k not in current:
                return False
            current = current[k]
        
        return True
    
    def _get_nested_value(self, config: Dict[str, Any], key: str) -> Any:
        """Get value from nested configuration key."""
        keys = key.split('.')
        current = config
        
        for k in keys:
            current = current[k]
        
        return current


# Global configuration manager instance
config_manager = TenantConfigurationManager()


def get_tenant_config(key: str, default: Any = None, tenant_id: Optional[str] = None) -> Any:
    """
    Get tenant configuration value.
    
    Convenience function that uses the global configuration manager.
    
    Args:
        key: Configuration key
        default: Default value if not found
        tenant_id: Specific tenant ID (uses current tenant if None)
        
    Returns:
        Any: Configuration value
    """
    return config_manager.get(key, default, tenant_id)


def set_tenant_config(key: str, value: Any, tenant_id: Optional[str] = None, persist: bool = True):
    """
    Set tenant configuration value.
    
    Convenience function that uses the global configuration manager.
    
    Args:
        key: Configuration key
        value: Configuration value
        tenant_id: Specific tenant ID (uses current tenant if None)
        persist: Whether to persist to storage
    """
    config_manager.set(key, value, tenant_id, persist)