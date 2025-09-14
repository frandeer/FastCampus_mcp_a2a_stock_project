"""
Dependency Injection Interfaces and Contracts

This module defines the core interfaces and contracts for the DI system,
providing abstractions for dependency resolution, lifecycle management,
and service registration.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Type, TypeVar, Union, Callable
from enum import Enum
import asyncio

T = TypeVar('T')


class ServiceScope(Enum):
    """Service lifecycle scopes"""
    SINGLETON = "singleton"
    TRANSIENT = "transient"
    SCOPED = "scoped"
    PER_REQUEST = "per_request"
    PER_THREAD = "per_thread"


class InjectionType(Enum):
    """Types of dependency injection"""
    CONSTRUCTOR = "constructor"
    PROPERTY = "property"
    METHOD = "method"
    INTERFACE = "interface"


class ResolutionStrategy(Enum):
    """Dependency resolution strategies"""
    EAGER = "eager"
    LAZY = "lazy"
    JUST_IN_TIME = "just_in_time"


class IDependencyResolver(ABC):
    """Interface for dependency resolution"""
    
    @abstractmethod
    def resolve(self, service_type: Type[T], context: Optional[Dict[str, Any]] = None) -> T:
        """Resolve a service instance"""
        pass
    
    @abstractmethod
    async def resolve_async(self, service_type: Type[T], context: Optional[Dict[str, Any]] = None) -> T:
        """Asynchronously resolve a service instance"""
        pass
    
    @abstractmethod
    def try_resolve(self, service_type: Type[T], context: Optional[Dict[str, Any]] = None) -> Optional[T]:
        """Try to resolve a service, return None if not found"""
        pass


class IServiceFactory(ABC):
    """Interface for service factories"""
    
    @abstractmethod
    def create(self, service_type: Type[T], context: Optional[Dict[str, Any]] = None) -> T:
        """Create a service instance"""
        pass
    
    @abstractmethod
    async def create_async(self, service_type: Type[T], context: Optional[Dict[str, Any]] = None) -> T:
        """Asynchronously create a service instance"""
        pass
    
    @abstractmethod
    def can_create(self, service_type: Type[T]) -> bool:
        """Check if the factory can create the service type"""
        pass


class IServiceScope(ABC):
    """Interface for service scope management"""
    
    @abstractmethod
    def get_or_create(self, key: str, factory: Callable[[], T]) -> T:
        """Get existing instance or create new one"""
        pass
    
    @abstractmethod
    def dispose(self) -> None:
        """Dispose all instances in this scope"""
        pass
    
    @abstractmethod
    async def dispose_async(self) -> None:
        """Asynchronously dispose all instances in this scope"""
        pass


class ILifecycleManager(ABC):
    """Interface for managing service lifecycles"""
    
    @abstractmethod
    def initialize(self, instance: Any) -> None:
        """Initialize a service instance"""
        pass
    
    @abstractmethod
    def dispose(self, instance: Any) -> None:
        """Dispose a service instance"""
        pass
    
    @abstractmethod
    async def initialize_async(self, instance: Any) -> None:
        """Asynchronously initialize a service instance"""
        pass
    
    @abstractmethod
    async def dispose_async(self, instance: Any) -> None:
        """Asynchronously dispose a service instance"""
        pass


class IInterceptor(ABC):
    """Interface for service interception (AOP)"""
    
    @abstractmethod
    def intercept(self, invocation: 'IInvocation') -> Any:
        """Intercept method calls"""
        pass
    
    @abstractmethod
    async def intercept_async(self, invocation: 'IInvocation') -> Any:
        """Asynchronously intercept method calls"""
        pass


class IInvocation(ABC):
    """Interface for method invocation context"""
    
    @property
    @abstractmethod
    def target(self) -> Any:
        """The target object being invoked"""
        pass
    
    @property
    @abstractmethod
    def method_name(self) -> str:
        """The method being invoked"""
        pass
    
    @property
    @abstractmethod
    def arguments(self) -> tuple:
        """Method arguments"""
        pass
    
    @property
    @abstractmethod
    def keyword_arguments(self) -> Dict[str, Any]:
        """Method keyword arguments"""
        pass
    
    @abstractmethod
    def proceed(self) -> Any:
        """Proceed with the original method call"""
        pass


class IConfiguration(ABC):
    """Interface for configuration binding"""
    
    @abstractmethod
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value"""
        pass
    
    @abstractmethod
    def bind(self, target_type: Type[T]) -> T:
        """Bind configuration to a type"""
        pass
    
    @abstractmethod
    def reload(self) -> None:
        """Reload configuration"""
        pass


class ITenantResolver(ABC):
    """Interface for multi-tenant context resolution"""
    
    @abstractmethod
    def get_current_tenant(self) -> Optional[str]:
        """Get current tenant identifier"""
        pass
    
    @abstractmethod
    def set_tenant_context(self, tenant_id: str) -> None:
        """Set tenant context"""
        pass
    
    @abstractmethod
    def clear_tenant_context(self) -> None:
        """Clear tenant context"""
        pass


class ICondition(ABC):
    """Interface for conditional registration"""
    
    @abstractmethod
    def matches(self, context: Dict[str, Any]) -> bool:
        """Check if condition matches"""
        pass


class ServiceDescriptor:
    """Describes a service registration"""
    
    def __init__(
        self,
        service_type: Type,
        implementation_type: Optional[Type] = None,
        factory: Optional[Callable] = None,
        instance: Optional[Any] = None,
        scope: ServiceScope = ServiceScope.TRANSIENT,
        conditions: Optional[List[ICondition]] = None,
        interceptors: Optional[List[Type[IInterceptor]]] = None,
        initialization_strategy: ResolutionStrategy = ResolutionStrategy.LAZY,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.service_type = service_type
        self.implementation_type = implementation_type
        self.factory = factory
        self.instance = instance
        self.scope = scope
        self.conditions = conditions or []
        self.interceptors = interceptors or []
        self.initialization_strategy = initialization_strategy
        self.metadata = metadata or {}
        
        # Validation
        count = sum([
            implementation_type is not None,
            factory is not None,
            instance is not None
        ])
        if count != 1:
            raise ValueError("Exactly one of implementation_type, factory, or instance must be provided")
    
    @property
    def service_name(self) -> str:
        """Get service name for registration"""
        return f"{self.service_type.__module__}.{self.service_type.__name__}"
    
    def can_resolve(self, context: Dict[str, Any]) -> bool:
        """Check if service can be resolved in given context"""
        return all(condition.matches(context) for condition in self.conditions)


class IDependencyContainer(ABC):
    """Main dependency injection container interface"""
    
    @abstractmethod
    def register(self, descriptor: ServiceDescriptor) -> None:
        """Register a service"""
        pass
    
    @abstractmethod
    def register_singleton(self, service_type: Type[T], implementation: Union[Type[T], T, Callable[[], T]]) -> None:
        """Register as singleton"""
        pass
    
    @abstractmethod
    def register_transient(self, service_type: Type[T], implementation: Union[Type[T], Callable[[], T]]) -> None:
        """Register as transient"""
        pass
    
    @abstractmethod
    def register_scoped(self, service_type: Type[T], implementation: Union[Type[T], Callable[[], T]]) -> None:
        """Register as scoped"""
        pass
    
    @abstractmethod
    def register_instance(self, service_type: Type[T], instance: T) -> None:
        """Register instance"""
        pass
    
    @abstractmethod
    def resolve(self, service_type: Type[T]) -> T:
        """Resolve service"""
        pass
    
    @abstractmethod
    async def resolve_async(self, service_type: Type[T]) -> T:
        """Asynchronously resolve service"""
        pass
    
    @abstractmethod
    def resolve_all(self, service_type: Type[T]) -> List[T]:
        """Resolve all services of type"""
        pass
    
    @abstractmethod
    def create_scope(self) -> 'IServiceScope':
        """Create new service scope"""
        pass
    
    @abstractmethod
    def is_registered(self, service_type: Type) -> bool:
        """Check if service is registered"""
        pass
    
    @abstractmethod
    def dispose(self) -> None:
        """Dispose container and all services"""
        pass
    
    @abstractmethod
    async def dispose_async(self) -> None:
        """Asynchronously dispose container"""
        pass


class IServiceProvider(IDependencyResolver):
    """Service provider interface combining resolution and scoping"""
    
    @abstractmethod
    def create_scope(self) -> 'IServiceProvider':
        """Create scoped service provider"""
        pass
    
    @abstractmethod
    def get_service(self, service_type: Type[T]) -> Optional[T]:
        """Get service or None"""
        pass
    
    @abstractmethod
    def get_services(self, service_type: Type[T]) -> List[T]:
        """Get all services of type"""
        pass
    
    @abstractmethod
    def get_required_service(self, service_type: Type[T]) -> T:
        """Get required service (throws if not found)"""
        pass


# Common exceptions
class DependencyInjectionError(Exception):
    """Base DI exception"""
    pass


class ServiceNotRegisteredException(DependencyInjectionError):
    """Service not registered"""
    pass


class CircularDependencyException(DependencyInjectionError):
    """Circular dependency detected"""
    pass


class InvalidScopeException(DependencyInjectionError):
    """Invalid scope operation"""
    pass


class ServiceInstantiationException(DependencyInjectionError):
    """Service instantiation failed"""
    pass


class ConfigurationBindingException(DependencyInjectionError):
    """Configuration binding failed"""
    pass


# Utility types
FactoryFunction = Callable[['IServiceProvider'], T]
PredicateFunction = Callable[[Dict[str, Any]], bool]
InitializationCallback = Callable[[Any], None]
DisposalCallback = Callable[[Any], None]