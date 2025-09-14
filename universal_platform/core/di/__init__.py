"""
Universal Platform Dependency Injection System

A comprehensive dependency injection framework inspired by enterprise patterns
like Spring DI and .NET Core DI, featuring:

- Constructor, property, and method injection
- Multiple scopes (singleton, transient, scoped, per-request)
- Circular dependency detection and resolution
- Conditional registration based on environment
- Factory methods and lazy initialization
- Configuration binding from environment/files
- Multi-tenancy support
- Interceptors and aspect-oriented programming
- Performance optimization with caching
- Thread-safety and async support

Example usage:

```python
from universal_platform.core.di import (
    DependencyContainer, ServiceScope, injectable, inject, singleton
)

# Using decorators
@injectable(ServiceScope.SINGLETON)
class DatabaseService:
    def __init__(self, connection_string: str):
        self.connection_string = connection_string

@injectable(ServiceScope.TRANSIENT)
class UserService:
    def __init__(self, db_service: DatabaseService):
        self.db_service = db_service

# Manual registration
container = DependencyContainer()
container.register_singleton(DatabaseService, DatabaseService)
container.register_transient(UserService, UserService)

# Resolution
user_service = container.resolve(UserService)

# Using injection decorators
@inject
def process_users(user_service: UserService):
    return user_service.get_all_users()
```
"""

# Core interfaces
from .interfaces import (
    # Main interfaces
    IDependencyContainer,
    IServiceProvider,
    IDependencyResolver,
    IServiceFactory,
    IServiceScope,
    ILifecycleManager,
    IInterceptor,
    IInvocation,
    IConfiguration,
    ITenantResolver,
    ICondition,
    
    # Enums
    ServiceScope,
    InjectionType,
    ResolutionStrategy,
    
    # Data classes
    ServiceDescriptor,
    
    # Exceptions
    DependencyInjectionError,
    ServiceNotRegisteredException,
    CircularDependencyException,
    InvalidScopeException,
    ServiceInstantiationException,
    ConfigurationBindingException,
    
    # Type aliases
    FactoryFunction,
    PredicateFunction,
    InitializationCallback,
    DisposalCallback
)

# Container implementation
from .container import (
    DependencyContainer,
    ServiceProvider,
    ContainerBuilder,
    create_container,
    request_scope,
    request_scope_async
)

# Scope management
from .scopes import (
    ScopeManager,
    SingletonScope,
    TransientScope,
    ScopedServiceScope,
    PerRequestScope,
    PerThreadScope,
    create_request_scope,
    create_request_scope_async,
    get_current_request_scope,
    has_request_scope
)

# Factory patterns
from .factory import (
    ServiceFactory,
    LazyProxy,
    AsyncLazyProxy,
    LazyFactory,
    FactoryBuilder,
    CustomServiceFactory,
    GenericFactory,
    PooledFactory,
    lazy_inject,
    factory,
    async_factory,
    conditional_factory,
    is_factory_function,
    is_async_factory_function,
    get_factory_condition
)

# Decorators
from .decorators import (
    # Service registration decorators
    injectable,
    singleton,
    transient,
    scoped,
    
    # Injection decorators
    inject,
    auto_inject,
    lazy_inject as lazy_inject_decorator,
    optional_inject,
    property_inject,
    method_inject,
    async_inject,
    
    # Configuration decorators
    configure,
    bind_configuration,
    
    # Conditional decorators
    conditional,
    qualifier,
    primary,
    profile,
    environment,
    
    # AOP decorators
    before,
    after,
    around,
    
    # Utility functions
    set_container,
    get_container,
    register_class,
    scan_and_register
)

# Configuration system
from .configuration import (
    Configuration,
    ConfigurationBuilder,
    IConfigurationSource,
    JsonConfigurationSource,
    YamlConfigurationSource,
    EnvironmentConfigurationSource,
    IniConfigurationSource,
    CompositeConfigurationSource,
    ConfigurationBasedRegistrar,
    create_default_configuration,
    
    # Configuration data classes
    ServiceConfiguration,
    EnvironmentCondition,
    ProfileCondition,
    PropertyCondition,
    
    # Condition implementations
    ConditionFactory,
    EnvironmentConditionImpl,
    ProfileConditionImpl,
    PropertyConditionImpl
)

# Version info
__version__ = "1.0.0"
__author__ = "Universal Platform Team"

# Export all public APIs
__all__ = [
    # Core interfaces
    "IDependencyContainer",
    "IServiceProvider", 
    "IDependencyResolver",
    "IServiceFactory",
    "IServiceScope",
    "ILifecycleManager",
    "IInterceptor",
    "IInvocation",
    "IConfiguration",
    "ITenantResolver",
    "ICondition",
    
    # Enums
    "ServiceScope",
    "InjectionType",
    "ResolutionStrategy",
    
    # Data classes
    "ServiceDescriptor",
    
    # Exceptions
    "DependencyInjectionError",
    "ServiceNotRegisteredException",
    "CircularDependencyException",
    "InvalidScopeException",
    "ServiceInstantiationException",
    "ConfigurationBindingException",
    
    # Container
    "DependencyContainer",
    "ServiceProvider",
    "ContainerBuilder",
    "create_container",
    "request_scope",
    "request_scope_async",
    
    # Scopes
    "ScopeManager",
    "SingletonScope",
    "TransientScope", 
    "ScopedServiceScope",
    "PerRequestScope",
    "PerThreadScope",
    "create_request_scope",
    "create_request_scope_async",
    "get_current_request_scope",
    "has_request_scope",
    
    # Factory
    "ServiceFactory",
    "LazyProxy",
    "AsyncLazyProxy",
    "LazyFactory",
    "FactoryBuilder",
    "CustomServiceFactory",
    "GenericFactory",
    "PooledFactory",
    "factory",
    "async_factory",
    "conditional_factory",
    
    # Decorators
    "injectable",
    "singleton",
    "transient", 
    "scoped",
    "inject",
    "auto_inject",
    "lazy_inject_decorator",
    "optional_inject",
    "property_inject",
    "method_inject",
    "async_inject",
    "configure",
    "bind_configuration",
    "conditional",
    "qualifier",
    "primary",
    "profile",
    "environment",
    "before",
    "after",
    "around",
    "set_container",
    "get_container",
    "register_class",
    "scan_and_register",
    
    # Configuration
    "Configuration",
    "ConfigurationBuilder",
    "IConfigurationSource",
    "JsonConfigurationSource",
    "YamlConfigurationSource",
    "EnvironmentConfigurationSource",
    "IniConfigurationSource",
    "CompositeConfigurationSource",
    "ConfigurationBasedRegistrar",
    "create_default_configuration",
    "ServiceConfiguration",
    "EnvironmentCondition",
    "ProfileCondition",
    "PropertyCondition",
    "ConditionFactory",
    
    # Version
    "__version__",
    "__author__"
]


def setup_default_container(config_file: str = None) -> DependencyContainer:
    """
    Setup a default container with common configuration
    
    Args:
        config_file: Optional configuration file path
        
    Returns:
        Configured DependencyContainer instance
    """
    # Create configuration
    config = create_default_configuration(config_file)
    
    # Create container
    container = DependencyContainer(config)
    
    # Set as global container for decorators
    set_container(container)
    
    return container


def create_web_container(config_file: str = None) -> DependencyContainer:
    """
    Create a container optimized for web applications
    
    Args:
        config_file: Optional configuration file path
        
    Returns:
        Web-optimized DependencyContainer instance
    """
    container = setup_default_container(config_file)
    
    # Register common web services
    from .scopes import create_request_scope
    
    # You would register actual web-specific services here
    # container.register_scoped(IHttpContext, HttpContext)
    # container.register_scoped(ISession, Session)
    
    return container


def create_test_container() -> DependencyContainer:
    """
    Create a container optimized for testing
    
    Returns:
        Test-optimized DependencyContainer instance
    """
    # Create minimal container for testing
    container = DependencyContainer()
    
    # Set as global container
    set_container(container)
    
    return container