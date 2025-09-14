"""
Factory Patterns and Lazy Loading

This module implements factory patterns, lazy initialization, and advanced
service creation strategies for the dependency injection system.
"""

import asyncio
import threading
import weakref
from typing import Any, Dict, Callable, Optional, Type, TypeVar, Union, List, Generic
from functools import wraps, partial
from collections import defaultdict
import inspect

from .interfaces import (
    IServiceFactory, IServiceProvider, ServiceDescriptor, ServiceScope,
    ResolutionStrategy, ServiceInstantiationException, FactoryFunction
)

T = TypeVar('T')


class LazyProxy(Generic[T]):
    """Lazy proxy for deferred service resolution"""
    
    def __init__(self, service_type: Type[T], provider: IServiceProvider):
        self._service_type = service_type
        self._provider = provider
        self._instance: Optional[T] = None
        self._lock = threading.RLock()
        self._is_resolved = False
    
    def _resolve(self) -> T:
        """Resolve the actual service instance"""
        if not self._is_resolved:
            with self._lock:
                if not self._is_resolved:
                    self._instance = self._provider.get_required_service(self._service_type)
                    self._is_resolved = True
        return self._instance
    
    def __getattr__(self, name: str) -> Any:
        """Delegate attribute access to resolved instance"""
        instance = self._resolve()
        return getattr(instance, name)
    
    def __call__(self, *args, **kwargs) -> Any:
        """Delegate calls to resolved instance"""
        instance = self._resolve()
        return instance(*args, **kwargs)
    
    def __repr__(self) -> str:
        if self._is_resolved:
            return f"LazyProxy({self._instance!r})"
        return f"LazyProxy({self._service_type.__name__}, unresolved)"


class AsyncLazyProxy(Generic[T]):
    """Async lazy proxy for deferred service resolution"""
    
    def __init__(self, service_type: Type[T], provider: IServiceProvider):
        self._service_type = service_type
        self._provider = provider
        self._instance: Optional[T] = None
        self._lock = asyncio.Lock()
        self._is_resolved = False
    
    async def _resolve(self) -> T:
        """Asynchronously resolve the service instance"""
        if not self._is_resolved:
            async with self._lock:
                if not self._is_resolved:
                    self._instance = await self._provider.resolve_async(self._service_type)
                    self._is_resolved = True
        return self._instance
    
    async def __aenter__(self):
        """Async context manager entry"""
        instance = await self._resolve()
        if hasattr(instance, '__aenter__'):
            return await instance.__aenter__()
        return instance
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self._is_resolved and hasattr(self._instance, '__aexit__'):
            return await self._instance.__aexit__(exc_type, exc_val, exc_tb)


class ServiceFactory(IServiceFactory):
    """Default service factory implementation"""
    
    def __init__(self, provider: Optional[IServiceProvider] = None):
        self._provider = provider
        self._creation_cache: Dict[Type, Callable] = {}
        self._lock = threading.RLock()
    
    def create(self, service_type: Type[T], context: Optional[Dict[str, Any]] = None) -> T:
        """Create service instance using constructor injection"""
        try:
            creator = self._get_creator(service_type)
            return creator(context or {})
        except Exception as e:
            raise ServiceInstantiationException(f"Failed to create {service_type.__name__}: {e}") from e
    
    async def create_async(self, service_type: Type[T], context: Optional[Dict[str, Any]] = None) -> T:
        """Asynchronously create service instance"""
        try:
            creator = self._get_creator(service_type)
            result = creator(context or {})
            
            # If result is awaitable, await it
            if inspect.iscoroutine(result):
                return await result
            return result
        except Exception as e:
            raise ServiceInstantiationException(f"Failed to create {service_type.__name__}: {e}") from e
    
    def can_create(self, service_type: Type[T]) -> bool:
        """Check if factory can create the service type"""
        try:
            # Check if type has a constructor we can analyze
            signature = inspect.signature(service_type.__init__)
            return True
        except (ValueError, TypeError):
            return False
    
    def _get_creator(self, service_type: Type[T]) -> Callable:
        """Get or create service creator function"""
        if service_type not in self._creation_cache:
            with self._lock:
                if service_type not in self._creation_cache:
                    self._creation_cache[service_type] = self._build_creator(service_type)
        
        return self._creation_cache[service_type]
    
    def _build_creator(self, service_type: Type[T]) -> Callable:
        """Build creator function with dependency injection"""
        try:
            signature = inspect.signature(service_type.__init__)
            parameters = list(signature.parameters.values())[1:]  # Skip 'self'
        except (ValueError, TypeError):
            # If we can't get signature, just try to create instance directly
            def simple_creator(context: Dict[str, Any]) -> T:
                return service_type()
            return simple_creator
        
        def creator(context: Dict[str, Any]) -> T:
            kwargs = {}
            
            for param in parameters:
                param_type = param.annotation
                param_name = param.name
                
                # Skip *args and **kwargs
                if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
                    continue
                
                # Try to resolve from context first
                if param_name in context:
                    kwargs[param_name] = context[param_name]
                # Try to resolve from provider if type annotation is available
                elif self._provider and param_type != inspect.Parameter.empty:
                    try:
                        if hasattr(self._provider, 'get_required_service'):
                            kwargs[param_name] = self._provider.get_required_service(param_type)
                        elif hasattr(self._provider, 'resolve'):
                            kwargs[param_name] = self._provider.resolve(param_type)
                        else:
                            raise ServiceInstantiationException(f"Provider does not support service resolution")
                    except Exception:
                        # Use default if available
                        if param.default != inspect.Parameter.empty:
                            kwargs[param_name] = param.default
                        else:
                            raise
                # Use default if available
                elif param.default != inspect.Parameter.empty:
                    kwargs[param_name] = param.default
                else:
                    # Only raise error if parameter has no default and no annotation
                    if param_type == inspect.Parameter.empty:
                        # Skip parameters we can't resolve without type info
                        continue
                    raise ServiceInstantiationException(
                        f"Cannot resolve parameter '{param_name}' of type '{param_type}' for {service_type.__name__}"
                    )
            
            return service_type(**kwargs)
        
        return creator


class FactoryBuilder:
    """Builder for creating custom factories"""
    
    def __init__(self):
        self._factories: Dict[Type, Callable] = {}
        self._conditions: Dict[Type, List[Callable]] = defaultdict(list)
        self._interceptors: Dict[Type, List[Callable]] = defaultdict(list)
    
    def register_factory(self, service_type: Type[T], factory: Callable[[], T]) -> 'FactoryBuilder':
        """Register factory function"""
        self._factories[service_type] = factory
        return self
    
    def register_provider_factory(self, service_type: Type[T], factory: FactoryFunction[T]) -> 'FactoryBuilder':
        """Register factory that takes service provider"""
        self._factories[service_type] = factory
        return self
    
    def add_condition(self, service_type: Type[T], condition: Callable[[Dict[str, Any]], bool]) -> 'FactoryBuilder':
        """Add creation condition"""
        self._conditions[service_type].append(condition)
        return self
    
    def add_interceptor(self, service_type: Type[T], interceptor: Callable) -> 'FactoryBuilder':
        """Add creation interceptor"""
        self._interceptors[service_type].append(interceptor)
        return self
    
    def build(self, provider: IServiceProvider) -> IServiceFactory:
        """Build the factory"""
        return CustomServiceFactory(
            provider,
            self._factories.copy(),
            self._conditions.copy(),
            self._interceptors.copy()
        )


class CustomServiceFactory(IServiceFactory):
    """Custom service factory with conditions and interceptors"""
    
    def __init__(
        self,
        provider: IServiceProvider,
        factories: Dict[Type, Callable],
        conditions: Dict[Type, List[Callable]],
        interceptors: Dict[Type, List[Callable]]
    ):
        self._provider = provider
        self._factories = factories
        self._conditions = conditions
        self._interceptors = interceptors
        self._default_factory = ServiceFactory(provider)
    
    def create(self, service_type: Type[T], context: Optional[Dict[str, Any]] = None) -> T:
        """Create service with custom logic"""
        context = context or {}
        
        # Check conditions
        if not self._check_conditions(service_type, context):
            raise ServiceInstantiationException(f"Conditions not met for {service_type.__name__}")
        
        # Get factory
        factory = self._factories.get(service_type)
        if factory is None:
            return self._default_factory.create(service_type, context)
        
        # Create instance
        try:
            # Check if factory expects provider
            sig = inspect.signature(factory)
            if len(sig.parameters) > 0:
                instance = factory(self._provider)
            else:
                instance = factory()
        except Exception as e:
            raise ServiceInstantiationException(f"Factory failed for {service_type.__name__}: {e}") from e
        
        # Apply interceptors
        for interceptor in self._interceptors.get(service_type, []):
            instance = interceptor(instance, context)
        
        return instance
    
    async def create_async(self, service_type: Type[T], context: Optional[Dict[str, Any]] = None) -> T:
        """Asynchronously create service"""
        # For now, delegate to sync version
        # In a real implementation, you'd handle async factories
        return self.create(service_type, context)
    
    def can_create(self, service_type: Type[T]) -> bool:
        """Check if factory can create the service type"""
        return (service_type in self._factories or 
                self._default_factory.can_create(service_type))
    
    def _check_conditions(self, service_type: Type[T], context: Dict[str, Any]) -> bool:
        """Check if all conditions are met"""
        conditions = self._conditions.get(service_type, [])
        return all(condition(context) for condition in conditions)


class LazyFactory:
    """Factory for creating lazy proxies"""
    
    @staticmethod
    def create_lazy(service_type: Type[T], provider: IServiceProvider) -> LazyProxy[T]:
        """Create lazy proxy"""
        return LazyProxy(service_type, provider)
    
    @staticmethod
    def create_async_lazy(service_type: Type[T], provider: IServiceProvider) -> AsyncLazyProxy[T]:
        """Create async lazy proxy"""
        return AsyncLazyProxy(service_type, provider)


def lazy_inject(service_type: Type[T]) -> Callable:
    """Decorator for lazy dependency injection"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # This would be implemented with actual provider access
            # For now, it's a placeholder
            return func(*args, **kwargs)
        return wrapper
    return decorator


class GenericFactory(Generic[T]):
    """Generic factory for type-safe creation"""
    
    def __init__(self, factory_func: Callable[[], T]):
        self._factory_func = factory_func
    
    def create(self) -> T:
        """Create instance"""
        return self._factory_func()
    
    async def create_async(self) -> T:
        """Asynchronously create instance"""
        result = self._factory_func()
        if inspect.iscoroutine(result):
            return await result
        return result


class PooledFactory(IServiceFactory):
    """Factory with object pooling for expensive objects"""
    
    def __init__(self, base_factory: IServiceFactory, pool_size: int = 10):
        self._base_factory = base_factory
        self._pools: Dict[Type, List[Any]] = defaultdict(list)
        self._pool_size = pool_size
        self._lock = threading.RLock()
    
    def create(self, service_type: Type[T], context: Optional[Dict[str, Any]] = None) -> T:
        """Create or reuse instance from pool"""
        with self._lock:
            pool = self._pools[service_type]
            if pool:
                return pool.pop()
        
        # Create new instance if pool is empty
        return self._base_factory.create(service_type, context)
    
    async def create_async(self, service_type: Type[T], context: Optional[Dict[str, Any]] = None) -> T:
        """Asynchronously create or reuse instance"""
        with self._lock:
            pool = self._pools[service_type]
            if pool:
                return pool.pop()
        
        return await self._base_factory.create_async(service_type, context)
    
    def can_create(self, service_type: Type[T]) -> bool:
        """Check if factory can create the service type"""
        return self._base_factory.can_create(service_type)
    
    def return_to_pool(self, service_type: Type, instance: Any) -> None:
        """Return instance to pool"""
        with self._lock:
            pool = self._pools[service_type]
            if len(pool) < self._pool_size:
                # Reset instance if possible
                if hasattr(instance, 'reset'):
                    instance.reset()
                pool.append(instance)
    
    def clear_pools(self) -> None:
        """Clear all pools"""
        with self._lock:
            for pool in self._pools.values():
                for instance in pool:
                    if hasattr(instance, 'dispose'):
                        try:
                            instance.dispose()
                        except Exception:
                            pass
            self._pools.clear()


# Factory decorators
def factory(func: Callable[[], T]) -> Callable[[], T]:
    """Mark function as factory"""
    func._is_factory = True
    return func


def async_factory(func: Callable[[], T]) -> Callable[[], T]:
    """Mark function as async factory"""
    func._is_async_factory = True
    return func


def conditional_factory(condition: Callable[[Dict[str, Any]], bool]):
    """Conditional factory decorator"""
    def decorator(func: Callable) -> Callable:
        func._factory_condition = condition
        return func
    return decorator


# Utility functions
def is_factory_function(func: Callable) -> bool:
    """Check if function is marked as factory"""
    return getattr(func, '_is_factory', False)


def is_async_factory_function(func: Callable) -> bool:
    """Check if function is marked as async factory"""
    return getattr(func, '_is_async_factory', False)


def get_factory_condition(func: Callable) -> Optional[Callable]:
    """Get factory condition if any"""
    return getattr(func, '_factory_condition', None)