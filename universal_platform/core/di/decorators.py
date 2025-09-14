"""
Dependency Injection Decorators

This module provides decorators for dependency injection, including
@inject, @injectable, @singleton, and other convenience decorators.
"""

import functools
import inspect
import threading
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar, Union, get_type_hints
from dataclasses import dataclass

from .interfaces import (
    ServiceScope, ServiceDescriptor, InjectionType, ResolutionStrategy,
    IDependencyContainer, IServiceProvider, ServiceNotRegisteredException
)

T = TypeVar('T')
F = TypeVar('F', bound=Callable[..., Any])

# Global container reference for decorators
_container: Optional[IDependencyContainer] = None
_container_lock = threading.RLock()


def set_container(container: IDependencyContainer) -> None:
    """Set global container for decorators"""
    global _container
    with _container_lock:
        _container = container


def get_container() -> Optional[IDependencyContainer]:
    """Get global container"""
    with _container_lock:
        return _container


@dataclass
class InjectionMetadata:
    """Metadata for injection"""
    parameter_name: str
    service_type: Type
    optional: bool = False
    qualifier: Optional[str] = None
    lazy: bool = False


class DependencyInjectionDecorator:
    """Base class for DI decorators"""
    
    def __init__(self):
        self._injection_metadata: Dict[str, List[InjectionMetadata]] = {}
        self._lock = threading.RLock()
    
    def add_injection_metadata(self, target: str, metadata: InjectionMetadata) -> None:
        """Add injection metadata"""
        with self._lock:
            if target not in self._injection_metadata:
                self._injection_metadata[target] = []
            self._injection_metadata[target].append(metadata)
    
    def get_injection_metadata(self, target: str) -> List[InjectionMetadata]:
        """Get injection metadata"""
        with self._lock:
            return self._injection_metadata.get(target, []).copy()


# Global decorator instance
_di_decorator = DependencyInjectionDecorator()


def injectable(
    scope: ServiceScope = ServiceScope.TRANSIENT,
    interface: Optional[Type] = None,
    name: Optional[str] = None,
    lazy: bool = False,
    conditions: Optional[List[Callable]] = None
) -> Callable[[Type[T]], Type[T]]:
    """
    Mark class as injectable service
    
    Args:
        scope: Service scope (singleton, transient, etc.)
        interface: Interface type to register as
        name: Named registration
        lazy: Enable lazy initialization
        conditions: Conditional registration predicates
    """
    def decorator(cls: Type[T]) -> Type[T]:
        # Store metadata on class
        cls._di_scope = scope
        cls._di_interface = interface or cls
        cls._di_name = name
        cls._di_lazy = lazy
        cls._di_conditions = conditions or []
        
        # Auto-register if container is available
        container = get_container()
        if container:
            register_class(container, cls)
        
        return cls
    
    return decorator


def singleton(interface: Optional[Type] = None, name: Optional[str] = None) -> Callable[[Type[T]], Type[T]]:
    """Shortcut decorator for singleton services"""
    return injectable(ServiceScope.SINGLETON, interface, name)


def transient(interface: Optional[Type] = None, name: Optional[str] = None) -> Callable[[Type[T]], Type[T]]:
    """Shortcut decorator for transient services"""
    return injectable(ServiceScope.TRANSIENT, interface, name)


def scoped(interface: Optional[Type] = None, name: Optional[str] = None) -> Callable[[Type[T]], Type[T]]:
    """Shortcut decorator for scoped services"""
    return injectable(ServiceScope.SCOPED, interface, name)


def inject(
    *dependencies: Union[Type, str],
    lazy: bool = False,
    optional: bool = False
) -> Callable[[F], F]:
    """
    Inject dependencies into function/method
    
    Args:
        dependencies: Types or names to inject
        lazy: Create lazy proxies
        optional: Allow missing dependencies
    """
    def decorator(func: F) -> F:
        # Get function signature
        sig = inspect.signature(func)
        type_hints = get_type_hints(func)
        
        # Create injection metadata
        injection_data = []
        for i, (param_name, param) in enumerate(sig.parameters.items()):
            if i < len(dependencies):
                service_type = dependencies[i]
                if isinstance(service_type, str):
                    # Named dependency - try to resolve type from hints
                    service_type = type_hints.get(param_name, Any)
                
                injection_data.append(InjectionMetadata(
                    parameter_name=param_name,
                    service_type=service_type,
                    optional=optional,
                    lazy=lazy
                ))
            elif param_name in type_hints:
                # Auto-inject based on type hints
                injection_data.append(InjectionMetadata(
                    parameter_name=param_name,
                    service_type=type_hints[param_name],
                    optional=param.default != inspect.Parameter.empty,
                    lazy=lazy
                ))
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            container = get_container()
            if not container:
                return func(*args, **kwargs)
            
            # Resolve dependencies
            for metadata in injection_data:
                if metadata.parameter_name not in kwargs:
                    try:
                        if metadata.lazy:
                            from .factory import LazyFactory
                            service = LazyFactory.create_lazy(metadata.service_type, container)
                        else:
                            service = container.resolve(metadata.service_type)
                        kwargs[metadata.parameter_name] = service
                    except ServiceNotRegisteredException:
                        if not metadata.optional:
                            raise
            
            return func(*args, **kwargs)
        
        # Store metadata
        wrapper._injection_metadata = injection_data
        return wrapper
    
    return decorator


def auto_inject(func: F) -> F:
    """
    Auto-inject dependencies based on type hints
    """
    sig = inspect.signature(func)
    type_hints = get_type_hints(func)
    
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        container = get_container()
        if not container:
            return func(*args, **kwargs)
        
        # Auto-resolve based on type hints
        for param_name, param in sig.parameters.items():
            if (param_name in type_hints and 
                param_name not in kwargs and
                type_hints[param_name] != inspect.Parameter.empty):
                
                try:
                    service = container.resolve(type_hints[param_name])
                    kwargs[param_name] = service
                except ServiceNotRegisteredException:
                    if param.default == inspect.Parameter.empty:
                        raise
        
        return func(*args, **kwargs)
    
    return wrapper


def lazy_inject(*dependencies: Type) -> Callable[[F], F]:
    """Inject lazy dependencies"""
    return inject(*dependencies, lazy=True)


def optional_inject(*dependencies: Type) -> Callable[[F], F]:
    """Inject optional dependencies"""
    return inject(*dependencies, optional=True)


def property_inject(service_type: Type, name: Optional[str] = None, lazy: bool = False):
    """
    Property injection decorator
    """
    def decorator(cls: Type[T]) -> Type[T]:
        prop_name = name or f"_{service_type.__name__.lower()}"
        
        def getter(self):
            if not hasattr(self, prop_name):
                container = get_container()
                if container:
                    if lazy:
                        from .factory import LazyFactory
                        service = LazyFactory.create_lazy(service_type, container)
                    else:
                        service = container.resolve(service_type)
                    setattr(self, prop_name, service)
            return getattr(self, prop_name, None)
        
        def setter(self, value):
            setattr(self, prop_name, value)
        
        # Add property to class
        setattr(cls, name or service_type.__name__.lower(), property(getter, setter))
        
        return cls
    
    return decorator


def method_inject(method_name: str, *dependencies: Type):
    """
    Method injection decorator
    """
    def decorator(cls: Type[T]) -> Type[T]:
        original_method = getattr(cls, method_name)
        
        @functools.wraps(original_method)
        def wrapper(self, *args, **kwargs):
            container = get_container()
            if container:
                # Inject dependencies as additional arguments
                injected_args = []
                for dep_type in dependencies:
                    service = container.resolve(dep_type)
                    injected_args.append(service)
                args = tuple(injected_args) + args
            
            return original_method(self, *args, **kwargs)
        
        setattr(cls, method_name, wrapper)
        return cls
    
    return decorator


def configure(*config_classes: Type):
    """
    Configure decorator for configuration classes
    """
    def decorator(cls: Type[T]) -> Type[T]:
        cls._di_configurations = config_classes
        return cls
    
    return decorator


def conditional(condition: Callable[..., bool]):
    """
    Conditional registration decorator
    """
    def decorator(cls: Type[T]) -> Type[T]:
        if not hasattr(cls, '_di_conditions'):
            cls._di_conditions = []
        cls._di_conditions.append(condition)
        return cls
    
    return decorator


def qualifier(name: str):
    """
    Qualifier decorator for named services
    """
    def decorator(cls: Type[T]) -> Type[T]:
        cls._di_qualifier = name
        return cls
    
    return decorator


def primary(cls: Type[T]) -> Type[T]:
    """
    Mark service as primary (preferred) implementation
    """
    cls._di_primary = True
    return cls


def profile(*profiles: str):
    """
    Profile-based conditional registration
    """
    def condition(**context):
        active_profiles = context.get('profiles', [])
        return any(p in active_profiles for p in profiles)
    
    return conditional(condition)


def environment(*envs: str):
    """
    Environment-based conditional registration
    """
    def condition(**context):
        current_env = context.get('environment', 'development')
        return current_env in envs
    
    return conditional(condition)


# Async decorators
def async_inject(*dependencies: Type) -> Callable:
    """
    Async dependency injection decorator
    """
    def decorator(func: Callable) -> Callable:
        sig = inspect.signature(func)
        type_hints = get_type_hints(func)
        
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            container = get_container()
            if not container:
                return await func(*args, **kwargs)
            
            # Resolve dependencies asynchronously
            for i, (param_name, param) in enumerate(sig.parameters.items()):
                if i < len(dependencies) and param_name not in kwargs:
                    service_type = dependencies[i]
                    service = await container.resolve_async(service_type)
                    kwargs[param_name] = service
            
            return await func(*args, **kwargs)
        
        return wrapper
    
    return decorator


# Utility functions
def register_class(container: IDependencyContainer, cls: Type) -> None:
    """Register class with container using decorator metadata"""
    scope = getattr(cls, '_di_scope', ServiceScope.TRANSIENT)
    interface = getattr(cls, '_di_interface', cls)
    conditions = getattr(cls, '_di_conditions', [])
    
    descriptor = ServiceDescriptor(
        service_type=interface,
        implementation_type=cls,
        scope=scope,
        conditions=conditions
    )
    
    container.register(descriptor)


def scan_and_register(container: IDependencyContainer, module_or_package) -> None:
    """
    Scan module/package for injectable classes and register them
    """
    import pkgutil
    import importlib
    
    if hasattr(module_or_package, '__path__'):
        # It's a package
        for importer, modname, ispkg in pkgutil.iter_modules(module_or_package.__path__):
            module = importlib.import_module(f"{module_or_package.__name__}.{modname}")
            _scan_module(container, module)
    else:
        # It's a module
        _scan_module(container, module_or_package)


def _scan_module(container: IDependencyContainer, module) -> None:
    """Scan single module for injectable classes"""
    for name in dir(module):
        obj = getattr(module, name)
        if (inspect.isclass(obj) and 
            hasattr(obj, '_di_scope')):
            register_class(container, obj)


# Aspect-oriented programming decorators
def before(func: Callable):
    """Before advice decorator"""
    def decorator(target_func: Callable) -> Callable:
        @functools.wraps(target_func)
        def wrapper(*args, **kwargs):
            func(*args, **kwargs)
            return target_func(*args, **kwargs)
        return wrapper
    return decorator


def after(func: Callable):
    """After advice decorator"""
    def decorator(target_func: Callable) -> Callable:
        @functools.wraps(target_func)
        def wrapper(*args, **kwargs):
            try:
                result = target_func(*args, **kwargs)
                func(*args, **kwargs)
                return result
            except Exception:
                func(*args, **kwargs)
                raise
        return wrapper
    return decorator


def around(func: Callable):
    """Around advice decorator"""
    def decorator(target_func: Callable) -> Callable:
        @functools.wraps(target_func)
        def wrapper(*args, **kwargs):
            return func(target_func, *args, **kwargs)
        return wrapper
    return decorator


# Configuration binding decorators
def bind_configuration(config_key: str, config_type: Optional[Type] = None):
    """
    Bind configuration values to class properties
    """
    def decorator(cls: Type[T]) -> Type[T]:
        if not hasattr(cls, '_di_config_bindings'):
            cls._di_config_bindings = []
        
        cls._di_config_bindings.append({
            'key': config_key,
            'type': config_type
        })
        
        return cls
    
    return decorator