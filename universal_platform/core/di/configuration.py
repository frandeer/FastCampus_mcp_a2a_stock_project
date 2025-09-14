"""
Configuration-based Dependency Setup

This module provides configuration-driven dependency injection setup,
supporting various configuration sources and binding strategies.
"""

import os
import json
import yaml
import configparser
from typing import Any, Dict, List, Optional, Type, TypeVar, Union, Callable
from pathlib import Path
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
import logging

from .interfaces import (
    IConfiguration, ServiceScope, ServiceDescriptor, ICondition,
    ConfigurationBindingException, IDependencyContainer
)

T = TypeVar('T')
logger = logging.getLogger(__name__)


@dataclass
class ServiceConfiguration:
    """Configuration for a service registration"""
    service_type: str
    implementation: Optional[str] = None
    factory: Optional[str] = None
    scope: str = "transient"
    lazy: bool = False
    conditions: List[str] = field(default_factory=list)
    properties: Dict[str, Any] = field(default_factory=dict)
    interceptors: List[str] = field(default_factory=list)


@dataclass
class EnvironmentCondition:
    """Environment-based condition configuration"""
    environment: Union[str, List[str]]
    negate: bool = False


@dataclass
class ProfileCondition:
    """Profile-based condition configuration"""
    profiles: Union[str, List[str]]
    negate: bool = False


@dataclass
class PropertyCondition:
    """Property-based condition configuration"""
    property_name: str
    expected_value: Any = None
    negate: bool = False


class IConfigurationSource(ABC):
    """Interface for configuration sources"""
    
    @abstractmethod
    def load(self) -> Dict[str, Any]:
        """Load configuration data"""
        pass
    
    @abstractmethod
    def supports_reload(self) -> bool:
        """Check if source supports reloading"""
        pass
    
    @abstractmethod
    def reload(self) -> Dict[str, Any]:
        """Reload configuration data"""
        pass


class JsonConfigurationSource(IConfigurationSource):
    """JSON file configuration source"""
    
    def __init__(self, file_path: Union[str, Path]):
        self.file_path = Path(file_path)
        self._last_modified = None
    
    def load(self) -> Dict[str, Any]:
        """Load JSON configuration"""
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                self._last_modified = self.file_path.stat().st_mtime
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            raise ConfigurationBindingException(f"Failed to load JSON config from {self.file_path}: {e}")
    
    def supports_reload(self) -> bool:
        """JSON files support reloading"""
        return True
    
    def reload(self) -> Dict[str, Any]:
        """Reload if file changed"""
        current_modified = self.file_path.stat().st_mtime
        if current_modified != self._last_modified:
            return self.load()
        return {}


class YamlConfigurationSource(IConfigurationSource):
    """YAML file configuration source"""
    
    def __init__(self, file_path: Union[str, Path]):
        self.file_path = Path(file_path)
        self._last_modified = None
    
    def load(self) -> Dict[str, Any]:
        """Load YAML configuration"""
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                self._last_modified = self.file_path.stat().st_mtime
                return yaml.safe_load(f) or {}
        except (FileNotFoundError, yaml.YAMLError) as e:
            raise ConfigurationBindingException(f"Failed to load YAML config from {self.file_path}: {e}")
    
    def supports_reload(self) -> bool:
        """YAML files support reloading"""
        return True
    
    def reload(self) -> Dict[str, Any]:
        """Reload if file changed"""
        current_modified = self.file_path.stat().st_mtime
        if current_modified != self._last_modified:
            return self.load()
        return {}


class EnvironmentConfigurationSource(IConfigurationSource):
    """Environment variables configuration source"""
    
    def __init__(self, prefix: str = ""):
        self.prefix = prefix.upper()
    
    def load(self) -> Dict[str, Any]:
        """Load environment variables"""
        config = {}
        for key, value in os.environ.items():
            if not self.prefix or key.startswith(self.prefix):
                # Convert environment key to nested dict
                config_key = key[len(self.prefix):].lstrip('_') if self.prefix else key
                self._set_nested_value(config, config_key.lower(), self._parse_value(value))
        return config
    
    def supports_reload(self) -> bool:
        """Environment variables support reloading"""
        return True
    
    def reload(self) -> Dict[str, Any]:
        """Reload environment variables"""
        return self.load()
    
    def _set_nested_value(self, config: Dict, key: str, value: Any):
        """Set nested dictionary value from dotted key"""
        parts = key.split('_')
        current = config
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]
        current[parts[-1]] = value
    
    def _parse_value(self, value: str) -> Any:
        """Parse environment value to appropriate type"""
        # Boolean values
        if value.lower() in ('true', 'false'):
            return value.lower() == 'true'
        
        # Integer values
        try:
            return int(value)
        except ValueError:
            pass
        
        # Float values
        try:
            return float(value)
        except ValueError:
            pass
        
        # JSON values
        if value.startswith('{') or value.startswith('['):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                pass
        
        return value


class IniConfigurationSource(IConfigurationSource):
    """INI file configuration source"""
    
    def __init__(self, file_path: Union[str, Path]):
        self.file_path = Path(file_path)
        self._last_modified = None
    
    def load(self) -> Dict[str, Any]:
        """Load INI configuration"""
        try:
            parser = configparser.ConfigParser()
            parser.read(self.file_path, encoding='utf-8')
            
            config = {}
            for section_name in parser.sections():
                config[section_name] = dict(parser[section_name])
            
            self._last_modified = self.file_path.stat().st_mtime
            return config
        except (FileNotFoundError, configparser.Error) as e:
            raise ConfigurationBindingException(f"Failed to load INI config from {self.file_path}: {e}")
    
    def supports_reload(self) -> bool:
        """INI files support reloading"""
        return True
    
    def reload(self) -> Dict[str, Any]:
        """Reload if file changed"""
        current_modified = self.file_path.stat().st_mtime
        if current_modified != self._last_modified:
            return self.load()
        return {}


class CompositeConfigurationSource(IConfigurationSource):
    """Composite configuration source combining multiple sources"""
    
    def __init__(self, sources: List[IConfigurationSource]):
        self.sources = sources
    
    def load(self) -> Dict[str, Any]:
        """Load and merge all sources"""
        merged_config = {}
        for source in self.sources:
            try:
                config = source.load()
                self._deep_merge(merged_config, config)
            except Exception as e:
                logger.warning(f"Failed to load config from source {source}: {e}")
        return merged_config
    
    def supports_reload(self) -> bool:
        """Support reload if any source supports it"""
        return any(source.supports_reload() for source in self.sources)
    
    def reload(self) -> Dict[str, Any]:
        """Reload all sources that support it"""
        merged_config = {}
        for source in self.sources:
            if source.supports_reload():
                try:
                    config = source.reload()
                    if config:
                        self._deep_merge(merged_config, config)
                except Exception as e:
                    logger.warning(f"Failed to reload config from source {source}: {e}")
        return merged_config
    
    def _deep_merge(self, target: Dict[str, Any], source: Dict[str, Any]):
        """Deep merge source into target"""
        for key, value in source.items():
            if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                self._deep_merge(target[key], value)
            else:
                target[key] = value


class Configuration(IConfiguration):
    """Main configuration implementation"""
    
    def __init__(self, sources: List[IConfigurationSource]):
        self.sources = sources
        self._config_data: Dict[str, Any] = {}
        self._type_bindings: Dict[Type, Any] = {}
        self.reload()
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value by key"""
        return self._get_nested_value(self._config_data, key, default)
    
    def bind(self, target_type: Type[T]) -> T:
        """Bind configuration to a type"""
        if target_type in self._type_bindings:
            return self._type_bindings[target_type]
        
        try:
            # Try to create instance with configuration
            if hasattr(target_type, '__dataclass_fields__'):
                # Dataclass binding
                instance = self._bind_dataclass(target_type)
            else:
                # Regular class binding
                instance = self._bind_class(target_type)
            
            self._type_bindings[target_type] = instance
            return instance
        except Exception as e:
            raise ConfigurationBindingException(f"Failed to bind configuration to {target_type.__name__}: {e}")
    
    def reload(self) -> None:
        """Reload configuration from all sources"""
        composite_source = CompositeConfigurationSource(self.sources)
        self._config_data = composite_source.load()
        # Clear cached bindings
        self._type_bindings.clear()
    
    def _get_nested_value(self, data: Dict[str, Any], key: str, default: Any = None) -> Any:
        """Get nested value from configuration data"""
        parts = key.split('.')
        current = data
        
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return default
        
        return current
    
    def _bind_dataclass(self, target_type: Type) -> Any:
        """Bind configuration to dataclass"""
        import dataclasses
        
        field_values = {}
        type_name = target_type.__name__.lower()
        type_config = self.get(type_name, {})
        
        for field in dataclasses.fields(target_type):
            field_name = field.name
            field_type = field.type
            
            # Try to get value from configuration
            value = None
            if field_name in type_config:
                value = type_config[field_name]
            elif hasattr(field, 'metadata') and 'config_key' in field.metadata:
                config_key = field.metadata['config_key']
                value = self.get(config_key)
            
            if value is not None:
                field_values[field_name] = self._convert_value(value, field_type)
            elif field.default != dataclasses.MISSING:
                field_values[field_name] = field.default
            elif field.default_factory != dataclasses.MISSING:
                field_values[field_name] = field.default_factory()
        
        return target_type(**field_values)
    
    def _bind_class(self, target_type: Type) -> Any:
        """Bind configuration to regular class"""
        type_name = target_type.__name__.lower()
        type_config = self.get(type_name, {})
        
        # Try to construct with configuration as kwargs
        return target_type(**type_config)
    
    def _convert_value(self, value: Any, target_type: Type) -> Any:
        """Convert value to target type"""
        if isinstance(value, target_type):
            return value
        
        # Handle common type conversions
        if target_type == bool and isinstance(value, str):
            return value.lower() in ('true', '1', 'yes', 'on')
        elif target_type in (int, float, str):
            return target_type(value)
        
        return value


class ConditionFactory:
    """Factory for creating condition instances from configuration"""
    
    @staticmethod
    def create_condition(condition_config: Dict[str, Any]) -> ICondition:
        """Create condition from configuration"""
        condition_type = condition_config.get('type', '')
        
        if condition_type == 'environment':
            return EnvironmentConditionImpl(condition_config)
        elif condition_type == 'profile':
            return ProfileConditionImpl(condition_config)
        elif condition_type == 'property':
            return PropertyConditionImpl(condition_config)
        else:
            raise ValueError(f"Unknown condition type: {condition_type}")


class EnvironmentConditionImpl(ICondition):
    """Environment-based condition implementation"""
    
    def __init__(self, config: Dict[str, Any]):
        self.environments = config.get('environments', [])
        if isinstance(self.environments, str):
            self.environments = [self.environments]
        self.negate = config.get('negate', False)
    
    def matches(self, context: Dict[str, Any]) -> bool:
        """Check if environment matches"""
        current_env = context.get('environment', os.getenv('ENVIRONMENT', 'development'))
        matches = current_env in self.environments
        return not matches if self.negate else matches


class ProfileConditionImpl(ICondition):
    """Profile-based condition implementation"""
    
    def __init__(self, config: Dict[str, Any]):
        self.profiles = config.get('profiles', [])
        if isinstance(self.profiles, str):
            self.profiles = [self.profiles]
        self.negate = config.get('negate', False)
    
    def matches(self, context: Dict[str, Any]) -> bool:
        """Check if profile matches"""
        active_profiles = context.get('profiles', [])
        matches = any(profile in active_profiles for profile in self.profiles)
        return not matches if self.negate else matches


class PropertyConditionImpl(ICondition):
    """Property-based condition implementation"""
    
    def __init__(self, config: Dict[str, Any]):
        self.property_name = config['property_name']
        self.expected_value = config.get('expected_value')
        self.negate = config.get('negate', False)
    
    def matches(self, context: Dict[str, Any]) -> bool:
        """Check if property matches"""
        property_value = context.get(self.property_name)
        
        if self.expected_value is None:
            matches = property_value is not None
        else:
            matches = property_value == self.expected_value
        
        return not matches if self.negate else matches


class ConfigurationBasedRegistrar:
    """Register services based on configuration"""
    
    def __init__(self, configuration: IConfiguration):
        self.configuration = configuration
    
    def register_services(self, container: IDependencyContainer, config_key: str = 'services') -> None:
        """Register services from configuration"""
        services_config = self.configuration.get(config_key, {})
        
        for service_name, service_config in services_config.items():
            try:
                descriptor = self._create_service_descriptor(service_name, service_config)
                container.register(descriptor)
                logger.info(f"Registered service: {service_name}")
            except Exception as e:
                logger.error(f"Failed to register service {service_name}: {e}")
    
    def _create_service_descriptor(self, service_name: str, config: Dict[str, Any]) -> ServiceDescriptor:
        """Create service descriptor from configuration"""
        # Parse service type
        service_type_name = config.get('service_type', service_name)
        service_type = self._resolve_type(service_type_name)
        
        # Parse implementation
        implementation_type = None
        factory = None
        instance = None
        
        if 'implementation' in config:
            implementation_type = self._resolve_type(config['implementation'])
        elif 'factory' in config:
            factory = self._resolve_factory(config['factory'])
        elif 'instance' in config:
            instance = config['instance']
        else:
            implementation_type = service_type
        
        # Parse scope
        scope_str = config.get('scope', 'transient')
        scope = ServiceScope(scope_str)
        
        # Parse conditions
        conditions = []
        for condition_config in config.get('conditions', []):
            condition = ConditionFactory.create_condition(condition_config)
            conditions.append(condition)
        
        return ServiceDescriptor(
            service_type=service_type,
            implementation_type=implementation_type,
            factory=factory,
            instance=instance,
            scope=scope,
            conditions=conditions
        )
    
    def _resolve_type(self, type_name: str) -> Type:
        """Resolve type from string name"""
        # This would need to implement actual type resolution
        # For now, returning a placeholder
        parts = type_name.split('.')
        module_name = '.'.join(parts[:-1])
        class_name = parts[-1]
        
        try:
            module = __import__(module_name, fromlist=[class_name])
            return getattr(module, class_name)
        except (ImportError, AttributeError) as e:
            raise ConfigurationBindingException(f"Cannot resolve type {type_name}: {e}")
    
    def _resolve_factory(self, factory_name: str) -> Callable:
        """Resolve factory function from string name"""
        return self._resolve_type(factory_name)


# Configuration builder
class ConfigurationBuilder:
    """Builder for configuration setup"""
    
    def __init__(self):
        self._sources: List[IConfigurationSource] = []
    
    def add_json_file(self, file_path: Union[str, Path]) -> 'ConfigurationBuilder':
        """Add JSON configuration file"""
        self._sources.append(JsonConfigurationSource(file_path))
        return self
    
    def add_yaml_file(self, file_path: Union[str, Path]) -> 'ConfigurationBuilder':
        """Add YAML configuration file"""
        self._sources.append(YamlConfigurationSource(file_path))
        return self
    
    def add_ini_file(self, file_path: Union[str, Path]) -> 'ConfigurationBuilder':
        """Add INI configuration file"""
        self._sources.append(IniConfigurationSource(file_path))
        return self
    
    def add_environment_variables(self, prefix: str = "") -> 'ConfigurationBuilder':
        """Add environment variables"""
        self._sources.append(EnvironmentConfigurationSource(prefix))
        return self
    
    def add_source(self, source: IConfigurationSource) -> 'ConfigurationBuilder':
        """Add custom configuration source"""
        self._sources.append(source)
        return self
    
    def build(self) -> Configuration:
        """Build configuration"""
        return Configuration(self._sources.copy())


# Utility functions
def create_default_configuration(config_file: Optional[str] = None) -> Configuration:
    """Create default configuration with common sources"""
    builder = ConfigurationBuilder()
    
    # Add environment variables first (lowest priority)
    builder.add_environment_variables()
    
    # Add configuration file if specified
    if config_file:
        config_path = Path(config_file)
        if config_path.suffix.lower() == '.json':
            builder.add_json_file(config_path)
        elif config_path.suffix.lower() in ('.yml', '.yaml'):
            builder.add_yaml_file(config_path)
        elif config_path.suffix.lower() in ('.ini', '.cfg'):
            builder.add_ini_file(config_path)
    
    # Look for common configuration files
    for config_name in ['appsettings.json', 'config.yaml', 'config.yml', 'application.ini']:
        config_path = Path(config_name)
        if config_path.exists():
            if config_name.endswith('.json'):
                builder.add_json_file(config_path)
            elif config_name.endswith(('.yml', '.yaml')):
                builder.add_yaml_file(config_path)
            elif config_name.endswith('.ini'):
                builder.add_ini_file(config_path)
    
    return builder.build()