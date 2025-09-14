"""
Universal Platform Plugin Decorators

Enterprise-grade decorators for plugin metadata, configuration, lifecycle management,
security, performance monitoring, and development utilities.

Features:
- Plugin metadata decorators
- Configuration validation
- Lifecycle hook decorators
- Security and permission decorators
- Performance monitoring decorators
- Error handling and retry decorators
- Development and debugging utilities
"""

import asyncio
import functools
import inspect
import logging
import time
import traceback
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Type, Union
from weakref import WeakKeyDictionary

from .interfaces import (
    PluginMetadata, PluginConfig, PluginType, PluginPriority, SecurityLevel,
    PluginError, PluginSecurityError, PluginTimeoutError, PluginConfigurationError
)


class HookType(Enum):
    """Plugin lifecycle hook types"""
    BEFORE_INIT = "before_init"
    AFTER_INIT = "after_init"
    BEFORE_START = "before_start"
    AFTER_START = "after_start"
    BEFORE_STOP = "before_stop"
    AFTER_STOP = "after_stop"
    BEFORE_DESTROY = "before_destroy"
    AFTER_DESTROY = "after_destroy"
    ON_ERROR = "on_error"
    ON_CONFIG_CHANGE = "on_config_change"


class PermissionType(Enum):
    """Plugin permission types"""
    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"
    NETWORK = "network"
    FILE_SYSTEM = "file_system"
    SYSTEM = "system"
    ADMIN = "admin"


@dataclass
class PerformanceMetrics:
    """Performance metrics for decorated methods"""
    call_count: int = 0
    total_time: float = 0.0
    min_time: float = float('inf')
    max_time: float = 0.0
    error_count: int = 0
    last_called: Optional[datetime] = None
    
    @property
    def average_time(self) -> float:
        """Calculate average execution time."""
        return self.total_time / self.call_count if self.call_count > 0 else 0.0
    
    def record_call(self, execution_time: float, error: bool = False) -> None:
        """Record a method call."""
        self.call_count += 1
        self.total_time += execution_time
        self.min_time = min(self.min_time, execution_time)
        self.max_time = max(self.max_time, execution_time)
        self.last_called = datetime.now()
        
        if error:
            self.error_count += 1
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary."""
        return {
            'call_count': self.call_count,
            'total_time': self.total_time,
            'average_time': self.average_time,
            'min_time': self.min_time if self.min_time != float('inf') else 0.0,
            'max_time': self.max_time,
            'error_count': self.error_count,
            'error_rate': self.error_count / self.call_count if self.call_count > 0 else 0.0,
            'last_called': self.last_called.isoformat() if self.last_called else None
        }


# Global storage for decorator data
_plugin_metadata_registry: Dict[Type, PluginMetadata] = {}
_lifecycle_hooks: Dict[Type, Dict[HookType, List[Callable]]] = {}
_permission_requirements: Dict[Callable, Set[PermissionType]] = {}
_performance_metrics: WeakKeyDictionary = WeakKeyDictionary()
_method_performance: Dict[str, PerformanceMetrics] = {}


def plugin_metadata(
    name: str,
    version: str,
    description: str = "",
    author: str = "",
    homepage: str = "",
    license: str = "",
    plugin_type: PluginType = PluginType.UTILITY,
    priority: PluginPriority = PluginPriority.NORMAL,
    security_level: SecurityLevel = SecurityLevel.RESTRICTED,
    dependencies: Dict[str, str] = None,
    provides: List[str] = None,
    requires: List[str] = None,
    tags: List[str] = None,
    **kwargs
) -> Callable:
    """
    Decorator for defining plugin metadata.
    
    Args:
        name: Plugin name
        version: Plugin version
        description: Plugin description
        author: Plugin author
        homepage: Plugin homepage URL
        license: Plugin license
        plugin_type: Type of plugin
        priority: Plugin priority level
        security_level: Security clearance level
        dependencies: Plugin dependencies
        provides: Capabilities provided by plugin
        requires: Capabilities required by plugin
        tags: Plugin tags
        **kwargs: Additional metadata fields
    
    Returns:
        Decorated plugin class
    """
    def decorator(cls: Type) -> Type:
        # Create metadata object
        metadata = PluginMetadata(
            name=name,
            version=version,
            description=description,
            author=author,
            homepage=homepage,
            license=license,
            plugin_type=plugin_type,
            priority=priority,
            security_level=security_level,
            dependencies=dependencies or {},
            provides=provides or [],
            requires=requires or [],
            tags=tags or [],
            **kwargs
        )
        
        # Store metadata
        _plugin_metadata_registry[cls] = metadata
        cls._plugin_metadata = metadata
        
        return cls
    
    return decorator


def config_schema(schema: Dict[str, Any]) -> Callable:
    """
    Decorator for defining plugin configuration schema.
    
    Args:
        schema: JSON schema for configuration validation
    
    Returns:
        Decorated plugin class
    """
    def decorator(cls: Type) -> Type:
        cls._config_schema = schema
        
        # Add validation method if not present
        if not hasattr(cls, 'validate_config'):
            def validate_config(self, config: PluginConfig) -> bool:
                """Validate configuration against schema."""
                # Basic validation - real implementation would use jsonschema
                try:
                    for key, spec in schema.items():
                        if spec.get('required', False):
                            if not config.get(key):
                                raise PluginConfigurationError(f"Required config key missing: {key}")
                        
                        value = config.get(key)
                        if value is not None:
                            expected_type = spec.get('type')
                            if expected_type and not isinstance(value, expected_type):
                                raise PluginConfigurationError(
                                    f"Config key {key} must be of type {expected_type.__name__}"
                                )
                    
                    return True
                    
                except Exception as e:
                    raise PluginConfigurationError(f"Configuration validation failed: {e}")
            
            cls.validate_config = validate_config
        
        return cls
    
    return decorator


def lifecycle_hook(hook_type: HookType) -> Callable:
    """
    Decorator for registering lifecycle hooks.
    
    Args:
        hook_type: Type of lifecycle hook
    
    Returns:
        Decorated method
    """
    def decorator(func: Callable) -> Callable:
        # Get the class from the method
        if hasattr(func, '__qualname__'):
            class_name = func.__qualname__.split('.')[0]
        else:
            class_name = 'Unknown'
        
        # Store hook registration info on function
        if not hasattr(func, '_lifecycle_hooks'):
            func._lifecycle_hooks = []
        func._lifecycle_hooks.append(hook_type)
        
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                else:
                    return func(*args, **kwargs)
            except Exception as e:
                logging.getLogger(__name__).error(
                    f"Error in lifecycle hook {hook_type.value}: {e}"
                )
                raise
        
        return wrapper
    
    return decorator


def requires_permission(*permissions: PermissionType) -> Callable:
    """
    Decorator for requiring specific permissions.
    
    Args:
        *permissions: Required permissions
    
    Returns:
        Decorated method
    """
    def decorator(func: Callable) -> Callable:
        _permission_requirements[func] = set(permissions)
        
        @functools.wraps(func)
        async def wrapper(self, *args, **kwargs):
            # Check permissions if security context is available
            if hasattr(self, '_security_context') and self._security_context:
                for permission in permissions:
                    if not await self._security_context.check_permission(
                        permission.value, 
                        func.__name__
                    ):
                        raise PluginSecurityError(
                            f"Permission denied: {permission.value} required for {func.__name__}"
                        )
            
            # Execute the function
            if asyncio.iscoroutinefunction(func):
                return await func(self, *args, **kwargs)
            else:
                return func(self, *args, **kwargs)
        
        return wrapper
    
    return decorator


def monitor_performance(include_args: bool = False) -> Callable:
    """
    Decorator for monitoring method performance.
    
    Args:
        include_args: Whether to include arguments in metrics
    
    Returns:
        Decorated method
    """
    def decorator(func: Callable) -> Callable:
        method_key = f"{func.__module__}.{func.__qualname__}"
        
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            error_occurred = False
            
            try:
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)
                return result
                
            except Exception as e:
                error_occurred = True
                raise
                
            finally:
                execution_time = time.time() - start_time
                
                # Update metrics
                if method_key not in _method_performance:
                    _method_performance[method_key] = PerformanceMetrics()
                
                _method_performance[method_key].record_call(execution_time, error_occurred)
        
        return wrapper
    
    return decorator


def retry_on_failure(
    max_attempts: int = 3,
    delay: float = 1.0,
    exponential_backoff: bool = True,
    exceptions: Tuple[Type[Exception], ...] = (Exception,)
) -> Callable:
    """
    Decorator for retrying failed operations.
    
    Args:
        max_attempts: Maximum retry attempts
        delay: Initial delay between retries
        exponential_backoff: Whether to use exponential backoff
        exceptions: Exception types to retry on
    
    Returns:
        Decorated method
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            current_delay = delay
            
            for attempt in range(max_attempts):
                try:
                    if asyncio.iscoroutinefunction(func):
                        return await func(*args, **kwargs)
                    else:
                        return func(*args, **kwargs)
                        
                except exceptions as e:
                    last_exception = e
                    
                    if attempt < max_attempts - 1:
                        logging.getLogger(__name__).warning(
                            f"Attempt {attempt + 1} failed for {func.__name__}: {e}. "
                            f"Retrying in {current_delay}s..."
                        )
                        await asyncio.sleep(current_delay)
                        
                        if exponential_backoff:
                            current_delay *= 2
                    else:
                        logging.getLogger(__name__).error(
                            f"All {max_attempts} attempts failed for {func.__name__}: {e}"
                        )
            
            raise last_exception
        
        return wrapper
    
    return decorator


def timeout(seconds: float) -> Callable:
    """
    Decorator for adding timeout to async methods.
    
    Args:
        seconds: Timeout in seconds
    
    Returns:
        Decorated method
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                if asyncio.iscoroutinefunction(func):
                    return await asyncio.wait_for(func(*args, **kwargs), timeout=seconds)
                else:
                    # For sync functions, run in executor with timeout
                    loop = asyncio.get_event_loop()
                    return await asyncio.wait_for(
                        loop.run_in_executor(None, lambda: func(*args, **kwargs)),
                        timeout=seconds
                    )
            except asyncio.TimeoutError:
                raise PluginTimeoutError(
                    f"Method {func.__name__} timed out after {seconds} seconds"
                )
        
        return wrapper
    
    return decorator


def validate_input(**validators) -> Callable:
    """
    Decorator for validating method inputs.
    
    Args:
        **validators: Mapping of parameter names to validation functions
    
    Returns:
        Decorated method
    """
    def decorator(func: Callable) -> Callable:
        sig = inspect.signature(func)
        
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Bind arguments to parameters
            bound_args = sig.bind(*args, **kwargs)
            bound_args.apply_defaults()
            
            # Validate arguments
            for param_name, validator in validators.items():
                if param_name in bound_args.arguments:
                    value = bound_args.arguments[param_name]
                    if not validator(value):
                        raise ValueError(f"Validation failed for parameter {param_name}")
            
            # Execute function
            if asyncio.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            else:
                return func(*args, **kwargs)
        
        return wrapper
    
    return decorator


def cache_result(ttl: float = 300.0, key_func: Callable = None) -> Callable:
    """
    Decorator for caching method results.
    
    Args:
        ttl: Time to live in seconds
        key_func: Function to generate cache key
    
    Returns:
        Decorated method
    """
    cache: Dict[str, Tuple[Any, float]] = {}
    
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                cache_key = f"{func.__name__}_{hash(str(args) + str(sorted(kwargs.items())))}"
            
            # Check cache
            now = time.time()
            if cache_key in cache:
                result, timestamp = cache[cache_key]
                if now - timestamp < ttl:
                    return result
            
            # Execute function and cache result
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            cache[cache_key] = (result, now)
            
            # Clean expired entries
            expired_keys = [k for k, (_, ts) in cache.items() if now - ts >= ttl]
            for k in expired_keys:
                del cache[k]
            
            return result
        
        return wrapper
    
    return decorator


def log_calls(
    level: int = logging.INFO,
    include_args: bool = False,
    include_result: bool = False
) -> Callable:
    """
    Decorator for logging method calls.
    
    Args:
        level: Logging level
        include_args: Whether to include arguments in log
        include_result: Whether to include result in log
    
    Returns:
        Decorated method
    """
    def decorator(func: Callable) -> Callable:
        logger = logging.getLogger(func.__module__)
        
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Log entry
            if include_args:
                logger.log(level, f"Calling {func.__name__} with args={args}, kwargs={kwargs}")
            else:
                logger.log(level, f"Calling {func.__name__}")
            
            try:
                # Execute function
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)
                
                # Log success
                if include_result:
                    logger.log(level, f"{func.__name__} completed successfully with result: {result}")
                else:
                    logger.log(level, f"{func.__name__} completed successfully")
                
                return result
                
            except Exception as e:
                logger.error(f"{func.__name__} failed with error: {e}")
                logger.debug(f"Traceback: {traceback.format_exc()}")
                raise
        
        return wrapper
    
    return decorator


@contextmanager
def plugin_context(plugin_instance):
    """
    Context manager for plugin execution context.
    
    Args:
        plugin_instance: Plugin instance
    """
    # Store original context
    original_context = getattr(plugin_instance, '_execution_context', None)
    
    try:
        # Set new context
        plugin_instance._execution_context = {
            'start_time': datetime.now(),
            'thread_id': id(asyncio.current_task()),
            'call_stack': traceback.extract_stack()
        }
        yield plugin_instance
        
    finally:
        # Restore original context
        plugin_instance._execution_context = original_context


def singleton(cls: Type) -> Type:
    """
    Decorator for creating singleton plugin classes.
    
    Args:
        cls: Plugin class
    
    Returns:
        Singleton-wrapped class
    """
    instances = {}
    
    @functools.wraps(cls)
    def get_instance(*args, **kwargs):
        if cls not in instances:
            instances[cls] = cls(*args, **kwargs)
        return instances[cls]
    
    return get_instance


def deprecated(reason: str = "", version: str = "") -> Callable:
    """
    Decorator for marking methods as deprecated.
    
    Args:
        reason: Deprecation reason
        version: Version when deprecated
    
    Returns:
        Decorated method
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            message = f"Method {func.__name__} is deprecated"
            if version:
                message += f" since version {version}"
            if reason:
                message += f": {reason}"
            
            logging.getLogger(__name__).warning(message)
            
            if asyncio.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            else:
                return func(*args, **kwargs)
        
        return wrapper
    
    return decorator


# Utility functions for accessing decorator data

def get_plugin_metadata(plugin_class: Type) -> Optional[PluginMetadata]:
    """Get plugin metadata for a class."""
    return _plugin_metadata_registry.get(plugin_class)


def get_lifecycle_hooks(plugin_class: Type) -> Dict[HookType, List[Callable]]:
    """Get lifecycle hooks for a plugin class."""
    return _lifecycle_hooks.get(plugin_class, {})


def get_permission_requirements(method: Callable) -> Set[PermissionType]:
    """Get permission requirements for a method."""
    return _permission_requirements.get(method, set())


def get_performance_metrics(method_key: str = None) -> Union[Dict[str, PerformanceMetrics], PerformanceMetrics, None]:
    """Get performance metrics for methods."""
    if method_key:
        return _method_performance.get(method_key)
    return _method_performance.copy()


def clear_performance_metrics(method_key: str = None) -> None:
    """Clear performance metrics."""
    if method_key:
        _method_performance.pop(method_key, None)
    else:
        _method_performance.clear()


def get_all_performance_stats() -> Dict[str, Dict[str, Any]]:
    """Get all performance statistics as dictionaries."""
    return {key: metrics.to_dict() for key, metrics in _method_performance.items()}


# Registration helper for lifecycle hooks
def register_lifecycle_hooks(plugin_class: Type) -> None:
    """Register lifecycle hooks found in plugin class methods."""
    if plugin_class not in _lifecycle_hooks:
        _lifecycle_hooks[plugin_class] = {}
    
    for attr_name in dir(plugin_class):
        attr = getattr(plugin_class, attr_name)
        if hasattr(attr, '_lifecycle_hooks'):
            for hook_type in attr._lifecycle_hooks:
                if hook_type not in _lifecycle_hooks[plugin_class]:
                    _lifecycle_hooks[plugin_class][hook_type] = []
                _lifecycle_hooks[plugin_class][hook_type].append(attr)