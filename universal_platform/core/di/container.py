"""
Main Dependency Injection Container

This module implements the main DI container with lifecycle management,
circular dependency detection, multi-tenancy support, and performance optimization.
"""

import asyncio
import os
import threading
import time
import weakref
from typing import Any, Dict, List, Optional, Type, TypeVar, Union, Callable, Set
from collections import defaultdict, deque
from contextlib import contextmanager, asynccontextmanager
from functools import lru_cache
import logging

from .interfaces import (
    IDependencyContainer, IServiceProvider, ILifecycleManager, ITenantResolver,
    IInterceptor, IInvocation, ServiceDescriptor, ServiceScope, ResolutionStrategy,
    ServiceNotRegisteredException, CircularDependencyException, InvalidScopeException,
    ServiceInstantiationException, DependencyInjectionError
)
from .scopes import ScopeManager, create_request_scope, create_request_scope_async
from .factory import ServiceFactory, LazyFactory, LazyProxy
from .configuration import Configuration

T = TypeVar('T')
logger = logging.getLogger(__name__)


class InvocationContext(IInvocation):
    """Implementation of method invocation context"""
    
    def __init__(self, target: Any, method_name: str, args: tuple, kwargs: Dict[str, Any]):
        self._target = target
        self._method_name = method_name
        self._args = args
        self._kwargs = kwargs
        self._original_method = getattr(target, method_name)
    
    @property
    def target(self) -> Any:
        return self._target
    
    @property
    def method_name(self) -> str:
        return self._method_name
    
    @property
    def arguments(self) -> tuple:
        return self._args
    
    @property
    def keyword_arguments(self) -> Dict[str, Any]:
        return self._kwargs
    
    def proceed(self) -> Any:
        return self._original_method(*self._args, **self._kwargs)


class InterceptorProxy:
    """Proxy for intercepting method calls"""
    
    def __init__(self, target: Any, interceptors: List[IInterceptor]):
        self._target = target
        self._interceptors = interceptors
    
    def __getattr__(self, name: str) -> Any:
        attr = getattr(self._target, name)
        
        if callable(attr):
            def intercepted_method(*args, **kwargs):
                invocation = InvocationContext(self._target, name, args, kwargs)
                
                # Apply interceptors in chain
                result = invocation
                for interceptor in self._interceptors:
                    result = interceptor.intercept(result)
                
                return result
            
            return intercepted_method
        
        return attr


class LifecycleManager(ILifecycleManager):
    """Default lifecycle manager implementation"""
    
    def initialize(self, instance: Any) -> None:
        """Initialize service instance"""
        if hasattr(instance, 'initialize'):
            instance.initialize()
        elif hasattr(instance, '__post_init__'):
            instance.__post_init__()
    
    def dispose(self, instance: Any) -> None:
        """Dispose service instance"""
        if hasattr(instance, 'dispose'):
            instance.dispose()
        elif hasattr(instance, 'close'):
            instance.close()
        elif hasattr(instance, '__del__'):
            try:
                instance.__del__()
            except Exception:
                pass
    
    async def initialize_async(self, instance: Any) -> None:
        """Asynchronously initialize service instance"""
        if hasattr(instance, 'initialize_async'):
            await instance.initialize_async()
        elif hasattr(instance, 'initialize'):
            instance.initialize()
        elif hasattr(instance, '__aenter__'):
            await instance.__aenter__()
    
    async def dispose_async(self, instance: Any) -> None:
        """Asynchronously dispose service instance"""
        if hasattr(instance, 'dispose_async'):
            await instance.dispose_async()
        elif hasattr(instance, 'dispose'):
            instance.dispose()
        elif hasattr(instance, 'aclose'):
            await instance.aclose()
        elif hasattr(instance, 'close'):
            instance.close()


class TenantResolver(ITenantResolver):
    """Default tenant resolver implementation"""
    
    def __init__(self):
        self._current_tenant = threading.local()
    
    def get_current_tenant(self) -> Optional[str]:
        """Get current tenant identifier"""
        return getattr(self._current_tenant, 'tenant_id', None)
    
    def set_tenant_context(self, tenant_id: str) -> None:
        """Set tenant context"""
        self._current_tenant.tenant_id = tenant_id
    
    def clear_tenant_context(self) -> None:
        """Clear tenant context"""
        if hasattr(self._current_tenant, 'tenant_id'):
            delattr(self._current_tenant, 'tenant_id')


class CircularDependencyDetector:
    """Detects circular dependencies during resolution"""
    
    def __init__(self):
        self._resolution_stack = threading.local()
    
    @contextmanager
    def track_resolution(self, service_type: Type):
        """Track service resolution to detect cycles"""
        if not hasattr(self._resolution_stack, 'stack'):
            self._resolution_stack.stack = []
        
        stack = self._resolution_stack.stack
        
        if service_type in stack:
            cycle = ' -> '.join([t.__name__ for t in stack[stack.index(service_type):]] + [service_type.__name__])
            raise CircularDependencyException(f"Circular dependency detected: {cycle}")
        
        stack.append(service_type)
        try:
            yield
        finally:
            stack.pop()


class PerformanceCache:
    """Performance cache for expensive operations"""
    
    def __init__(self, max_size: int = 1000, ttl: float = 300):
        self._cache: Dict[str, tuple] = {}
        self._access_times: Dict[str, float] = {}
        self._max_size = max_size
        self._ttl = ttl
        self._lock = threading.RLock()
    
    def get(self, key: str) -> Optional[Any]:
        """Get cached value"""
        with self._lock:
            if key not in self._cache:
                return None
            
            # Check TTL
            if time.time() - self._access_times[key] > self._ttl:
                del self._cache[key]
                del self._access_times[key]
                return None
            
            self._access_times[key] = time.time()
            return self._cache[key][0]
    
    def put(self, key: str, value: Any) -> None:
        """Cache value"""
        with self._lock:
            # Evict oldest entries if cache is full
            if len(self._cache) >= self._max_size:
                oldest_key = min(self._access_times.keys(), key=lambda k: self._access_times[k])
                del self._cache[oldest_key]
                del self._access_times[oldest_key]
            
            self._cache[key] = (value, time.time())
            self._access_times[key] = time.time()
    
    def clear(self) -> None:
        """Clear cache"""
        with self._lock:
            self._cache.clear()
            self._access_times.clear()


class ServiceProvider(IServiceProvider):
    """Service provider implementation"""
    
    def __init__(self, container: 'DependencyContainer', scope_id: Optional[str] = None):
        self._container = container
        self._scope_id = scope_id
        self._disposed = False
    
    def resolve(self, service_type: Type[T], context: Optional[Dict[str, Any]] = None) -> T:
        """Resolve service"""
        if self._disposed:
            raise InvalidScopeException("Service provider has been disposed")
        return self._container.resolve(service_type, context)
    
    async def resolve_async(self, service_type: Type[T], context: Optional[Dict[str, Any]] = None) -> T:
        """Asynchronously resolve service"""
        if self._disposed:
            raise InvalidScopeException("Service provider has been disposed")
        return await self._container.resolve_async(service_type, context)
    
    def try_resolve(self, service_type: Type[T], context: Optional[Dict[str, Any]] = None) -> Optional[T]:
        """Try to resolve service"""
        if self._disposed:
            return None
        try:
            return self._container.resolve(service_type, context)
        except ServiceNotRegisteredException:
            return None
    
    def get_service(self, service_type: Type[T]) -> Optional[T]:
        """Get service or None"""
        return self.try_resolve(service_type)
    
    def get_services(self, service_type: Type[T]) -> List[T]:
        """Get all services of type"""
        if self._disposed:
            return []
        return self._container.resolve_all(service_type)
    
    def get_required_service(self, service_type: Type[T]) -> T:
        """Get required service (throws if not found)"""
        return self.resolve(service_type)
    
    def create_scope(self) -> 'ServiceProvider':
        """Create scoped service provider"""
        if self._disposed:
            raise InvalidScopeException("Cannot create scope from disposed provider")
        
        scope = self._container._scope_manager.create_scoped_scope()
        return ServiceProvider(self._container, scope)
    
    def dispose(self) -> None:
        """Dispose service provider"""
        if not self._disposed:
            self._disposed = True
            if self._scope_id:
                self._container._scope_manager.dispose_scope(self._scope_id)


class DependencyContainer(IDependencyContainer):
    """Main dependency injection container"""
    
    def __init__(self, configuration: Optional[Configuration] = None):
        self._services: Dict[Type, List[ServiceDescriptor]] = defaultdict(list)
        self._singletons: Dict[Type, Any] = {}
        self._scope_manager = ScopeManager()
        self._lifecycle_manager = LifecycleManager()
        self._tenant_resolver = TenantResolver()
        self._circular_detector = CircularDependencyDetector()
        self._performance_cache = PerformanceCache()
        self._service_factory = ServiceFactory(self)
        self._configuration = configuration
        self._lock = threading.RLock()
        self._disposed = False
        
        # Performance monitoring
        self._resolution_stats: Dict[str, Dict[str, float]] = defaultdict(lambda: {
            'count': 0,
            'total_time': 0,
            'avg_time': 0
        })
        
        # Register self
        self.register_instance(IDependencyContainer, self)
        self.register_instance(IServiceProvider, ServiceProvider(self))
        if configuration:
            self.register_instance(Configuration, configuration)
    
    def register(self, descriptor: ServiceDescriptor) -> None:
        """Register a service"""
        if self._disposed:
            raise DependencyInjectionError("Container has been disposed")
        
        with self._lock:
            self._services[descriptor.service_type].append(descriptor)
            
            # Clear related caches
            cache_key = f"resolve_{descriptor.service_type.__name__}"
            if cache_key in self._performance_cache._cache:
                del self._performance_cache._cache[cache_key]
            
            logger.debug(f"Registered service: {descriptor.service_name} with scope {descriptor.scope}")
    
    def register_singleton(self, service_type: Type[T], implementation: Union[Type[T], T, Callable[[], T]]) -> None:
        """Register as singleton"""
        if isinstance(implementation, type):
            descriptor = ServiceDescriptor(
                service_type=service_type,
                implementation_type=implementation,
                scope=ServiceScope.SINGLETON
            )
        elif callable(implementation):
            descriptor = ServiceDescriptor(
                service_type=service_type,
                factory=implementation,
                scope=ServiceScope.SINGLETON
            )
        else:
            descriptor = ServiceDescriptor(
                service_type=service_type,
                instance=implementation,
                scope=ServiceScope.SINGLETON
            )
        
        self.register(descriptor)
    
    def register_transient(self, service_type: Type[T], implementation: Union[Type[T], Callable[[], T]]) -> None:
        """Register as transient"""
        if isinstance(implementation, type):
            descriptor = ServiceDescriptor(
                service_type=service_type,
                implementation_type=implementation,
                scope=ServiceScope.TRANSIENT
            )
        else:
            descriptor = ServiceDescriptor(
                service_type=service_type,
                factory=implementation,
                scope=ServiceScope.TRANSIENT
            )
        
        self.register(descriptor)
    
    def register_scoped(self, service_type: Type[T], implementation: Union[Type[T], Callable[[], T]]) -> None:
        """Register as scoped"""
        if isinstance(implementation, type):
            descriptor = ServiceDescriptor(
                service_type=service_type,
                implementation_type=implementation,
                scope=ServiceScope.SCOPED
            )
        else:
            descriptor = ServiceDescriptor(
                service_type=service_type,
                factory=implementation,
                scope=ServiceScope.SCOPED
            )
        
        self.register(descriptor)
    
    def register_instance(self, service_type: Type[T], instance: T) -> None:
        """Register instance"""
        descriptor = ServiceDescriptor(
            service_type=service_type,
            instance=instance,
            scope=ServiceScope.SINGLETON
        )
        
        self.register(descriptor)
        
        # Also store in singletons cache
        with self._lock:
            self._singletons[service_type] = instance
    
    def resolve(self, service_type: Type[T], context: Optional[Dict[str, Any]] = None) -> T:
        """Resolve service"""
        if self._disposed:
            raise DependencyInjectionError("Container has been disposed")
        
        start_time = time.time()
        
        try:
            with self._circular_detector.track_resolution(service_type):
                result = self._resolve_internal(service_type, context or {})
                
                # Update performance stats
                resolution_time = time.time() - start_time
                self._update_resolution_stats(service_type.__name__, resolution_time)
                
                return result
        except Exception as e:
            logger.error(f"Failed to resolve {service_type.__name__}: {e}")
            raise
    
    async def resolve_async(self, service_type: Type[T], context: Optional[Dict[str, Any]] = None) -> T:
        """Asynchronously resolve service"""
        if self._disposed:
            raise DependencyInjectionError("Container has been disposed")
        
        # For now, delegate to sync version
        # In a full implementation, you'd support async factories and initialization
        return self.resolve(service_type, context)
    
    def resolve_all(self, service_type: Type[T]) -> List[T]:
        """Resolve all services of type"""
        if self._disposed:
            raise DependencyInjectionError("Container has been disposed")
        
        with self._lock:
            descriptors = self._services.get(service_type, [])
            
            context = self._create_resolution_context()
            
            services = []
            for descriptor in descriptors:
                if descriptor.can_resolve(context):
                    try:
                        service = self._create_service_instance(descriptor, context)
                        services.append(service)
                    except Exception as e:
                        logger.warning(f"Failed to resolve service {descriptor.service_name}: {e}")
            
            return services
    
    def create_scope(self) -> ServiceProvider:
        """Create new service scope"""
        if self._disposed:
            raise DependencyInjectionError("Container has been disposed")
        
        scope = self._scope_manager.create_scoped_scope()
        return ServiceProvider(self, scope)
    
    def is_registered(self, service_type: Type) -> bool:
        """Check if service is registered"""
        with self._lock:
            return service_type in self._services and len(self._services[service_type]) > 0
    
    def dispose(self) -> None:
        """Dispose container and all services"""
        if self._disposed:
            return
        
        with self._lock:
            self._disposed = True
            
            # Dispose all singleton instances
            for instance in self._singletons.values():
                try:
                    self._lifecycle_manager.dispose(instance)
                except Exception as e:
                    logger.warning(f"Error disposing singleton: {e}")
            
            # Dispose scope manager
            self._scope_manager.dispose_all()
            
            # Clear caches
            self._performance_cache.clear()
            
            # Clear collections
            self._services.clear()
            self._singletons.clear()
            
            logger.info("Dependency container disposed")
    
    async def dispose_async(self) -> None:
        """Asynchronously dispose container"""
        if self._disposed:
            return
        
        with self._lock:
            self._disposed = True
            
            # Dispose all singleton instances
            for instance in self._singletons.values():
                try:
                    await self._lifecycle_manager.dispose_async(instance)
                except Exception as e:
                    logger.warning(f"Error disposing singleton: {e}")
            
            # Dispose scope manager
            await self._scope_manager.dispose_all_async()
            
            # Clear caches and collections
            self._performance_cache.clear()
            self._services.clear()
            self._singletons.clear()
            
            logger.info("Dependency container disposed asynchronously")
    
    def _resolve_internal(self, service_type: Type[T], context: Dict[str, Any]) -> T:
        """Internal resolution logic"""
        # Check performance cache first
        cache_key = f"resolve_{service_type.__name__}_{hash(frozenset(context.items()))}"
        cached_result = self._performance_cache.get(cache_key)
        if cached_result is not None:
            return cached_result
        
        with self._lock:
            descriptors = self._services.get(service_type, [])
            
            if not descriptors:
                raise ServiceNotRegisteredException(f"Service {service_type.__name__} is not registered")
            
            # Find best matching descriptor
            best_descriptor = None
            for descriptor in descriptors:
                if descriptor.can_resolve(context):
                    best_descriptor = descriptor
                    break
            
            if best_descriptor is None:
                raise ServiceNotRegisteredException(
                    f"No suitable registration found for {service_type.__name__} with current context"
                )
            
            # Create service instance
            service = self._create_service_instance(best_descriptor, context)
            
            # Cache result if appropriate
            if best_descriptor.scope == ServiceScope.SINGLETON:
                self._performance_cache.put(cache_key, service)
            
            return service
    
    def _create_service_instance(self, descriptor: ServiceDescriptor, context: Dict[str, Any]) -> Any:
        """Create service instance based on descriptor"""
        scope = self._scope_manager.get_scope(descriptor.scope)
        
        if descriptor.scope == ServiceScope.SINGLETON and descriptor.service_type in self._singletons:
            return self._singletons[descriptor.service_type]
        
        def factory():
            if descriptor.instance is not None:
                instance = descriptor.instance
            elif descriptor.factory is not None:
                if callable(descriptor.factory):
                    instance = descriptor.factory(ServiceProvider(self))
                else:
                    instance = descriptor.factory()
            elif descriptor.implementation_type is not None:
                instance = self._service_factory.create(descriptor.implementation_type, context)
            else:
                raise ServiceInstantiationException(f"No way to create instance for {descriptor.service_name}")
            
            # Apply lifecycle management
            try:
                self._lifecycle_manager.initialize(instance)
            except Exception as e:
                logger.warning(f"Failed to initialize {descriptor.service_name}: {e}")
            
            # Apply interceptors
            if descriptor.interceptors:
                interceptor_instances = []
                for interceptor_type in descriptor.interceptors:
                    interceptor = self.resolve(interceptor_type, context)
                    interceptor_instances.append(interceptor)
                instance = InterceptorProxy(instance, interceptor_instances)
            
            return instance
        
        service_key = f"{descriptor.service_name}_{descriptor.scope.value}"
        instance = scope.get_or_create(service_key, factory)
        
        # Store singleton for direct access
        if descriptor.scope == ServiceScope.SINGLETON:
            self._singletons[descriptor.service_type] = instance
        
        return instance
    
    def _create_resolution_context(self) -> Dict[str, Any]:
        """Create resolution context"""
        context = {
            'tenant': self._tenant_resolver.get_current_tenant(),
            'environment': os.getenv('ENVIRONMENT', 'development'),
            'profiles': os.getenv('PROFILES', '').split(',') if os.getenv('PROFILES') else []
        }
        
        if self._configuration:
            context.update(self._configuration._config_data)
        
        return context
    
    def _update_resolution_stats(self, service_name: str, resolution_time: float) -> None:
        """Update resolution performance statistics"""
        stats = self._resolution_stats[service_name]
        stats['count'] += 1
        stats['total_time'] += resolution_time
        stats['avg_time'] = stats['total_time'] / stats['count']
    
    def get_resolution_stats(self) -> Dict[str, Dict[str, float]]:
        """Get resolution performance statistics"""
        return dict(self._resolution_stats)
    
    def clear_resolution_stats(self) -> None:
        """Clear resolution statistics"""
        self._resolution_stats.clear()


# Container builder for fluent configuration
class ContainerBuilder:
    """Fluent builder for dependency container"""
    
    def __init__(self):
        self._descriptors: List[ServiceDescriptor] = []
        self._configuration: Optional[Configuration] = None
    
    def register_singleton(self, service_type: Type[T], implementation: Union[Type[T], T, Callable]) -> 'ContainerBuilder':
        """Register singleton service"""
        if isinstance(implementation, type):
            descriptor = ServiceDescriptor(service_type, implementation_type=implementation, scope=ServiceScope.SINGLETON)
        elif callable(implementation):
            descriptor = ServiceDescriptor(service_type, factory=implementation, scope=ServiceScope.SINGLETON)
        else:
            descriptor = ServiceDescriptor(service_type, instance=implementation, scope=ServiceScope.SINGLETON)
        
        self._descriptors.append(descriptor)
        return self
    
    def register_transient(self, service_type: Type[T], implementation: Union[Type[T], Callable]) -> 'ContainerBuilder':
        """Register transient service"""
        if isinstance(implementation, type):
            descriptor = ServiceDescriptor(service_type, implementation_type=implementation, scope=ServiceScope.TRANSIENT)
        else:
            descriptor = ServiceDescriptor(service_type, factory=implementation, scope=ServiceScope.TRANSIENT)
        
        self._descriptors.append(descriptor)
        return self
    
    def register_scoped(self, service_type: Type[T], implementation: Union[Type[T], Callable]) -> 'ContainerBuilder':
        """Register scoped service"""
        if isinstance(implementation, type):
            descriptor = ServiceDescriptor(service_type, implementation_type=implementation, scope=ServiceScope.SCOPED)
        else:
            descriptor = ServiceDescriptor(service_type, factory=implementation, scope=ServiceScope.SCOPED)
        
        self._descriptors.append(descriptor)
        return self
    
    def add_configuration(self, configuration: Configuration) -> 'ContainerBuilder':
        """Add configuration"""
        self._configuration = configuration
        return self
    
    def build(self) -> DependencyContainer:
        """Build the container"""
        container = DependencyContainer(self._configuration)
        
        for descriptor in self._descriptors:
            container.register(descriptor)
        
        return container


# Utility functions
def create_container(configuration: Optional[Configuration] = None) -> DependencyContainer:
    """Create default dependency container"""
    return DependencyContainer(configuration)


@contextmanager
def request_scope(container: DependencyContainer):
    """Create request scope context"""
    with create_request_scope() as scope:
        yield ServiceProvider(container, scope)


@asynccontextmanager
async def request_scope_async(container: DependencyContainer):
    """Create async request scope context"""
    async with create_request_scope_async() as scope:
        yield ServiceProvider(container, scope)