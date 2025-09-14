# Universal Platform Dependency Injection System

A comprehensive dependency injection framework for Python inspired by enterprise patterns like Spring DI and .NET Core DI.

## Features

### Core Features
- **Constructor Injection**: Automatic dependency resolution through constructor parameters
- **Property Injection**: Dependencies injected as class properties
- **Method Injection**: Dependencies passed to specific methods
- **Interface-based Registration**: Register implementations by interface/abstract base class

### Lifecycle Management
- **Multiple Scopes**: Singleton, Transient, Scoped, Per-Request, Per-Thread
- **Automatic Disposal**: Proper cleanup of resources and instances
- **Lifecycle Callbacks**: Initialize and dispose hooks for services

### Advanced Features
- **Circular Dependency Detection**: Automatic detection and helpful error messages
- **Conditional Registration**: Register services based on environment, profiles, or custom conditions
- **Factory Methods**: Support for factory functions and lazy initialization
- **Configuration Binding**: Bind configuration from files and environment variables
- **Multi-tenancy Support**: Tenant-aware service resolution
- **Interceptors and AOP**: Aspect-oriented programming with method interception
- **Performance Optimization**: Caching and performance monitoring
- **Thread Safety**: Full thread-safe operation with async support

## Quick Start

### Basic Usage

```python
from universal_platform.core.di import (
    DependencyContainer, injectable, inject, singleton, transient
)

# Define services with decorators
@singleton
class DatabaseService:
    def __init__(self, connection_string: str):
        self.connection_string = connection_string
    
    def query(self, sql: str):
        return f"Result of: {sql}"

@transient
class UserService:
    def __init__(self, db: DatabaseService):
        self.db = db
    
    def get_user(self, user_id: int):
        return self.db.query(f"SELECT * FROM users WHERE id = {user_id}")

# Create and configure container
container = DependencyContainer()
container.register_instance(str, "postgresql://localhost/mydb")  # connection_string

# Resolve services
user_service = container.resolve(UserService)
user = user_service.get_user(123)
```

### Using Injection Decorators

```python
@inject
def process_user_data(user_service: UserService, logger: Logger):
    """Dependencies automatically injected based on type hints"""
    users = user_service.get_all_users()
    logger.info(f"Processing {len(users)} users")
    return users

# Call function - dependencies resolved automatically
result = process_user_data()
```

### Configuration-based Setup

```python
from universal_platform.core.di import (
    ConfigurationBuilder, setup_default_container
)

# Create configuration from multiple sources
config = ConfigurationBuilder() \
    .add_environment_variables("MYAPP_") \
    .add_json_file("appsettings.json") \
    .add_yaml_file("config.yaml") \
    .build()

# Setup container with configuration
container = setup_default_container("appsettings.json")

# Configuration automatically bound to classes
@dataclass
class DatabaseConfig:
    host: str = "localhost"
    port: int = 5432
    database: str = "myapp"

db_config = config.bind(DatabaseConfig)
```

## Service Scopes

### Singleton
One instance per container lifetime:

```python
@singleton
class CacheService:
    def __init__(self):
        self.cache = {}

# Or manual registration
container.register_singleton(CacheService, CacheService)
```

### Transient
New instance every time:

```python
@transient
class EmailService:
    def send_email(self, to: str, message: str):
        pass

# Always gets new instance
email1 = container.resolve(EmailService)
email2 = container.resolve(EmailService)
assert email1 is not email2
```

### Scoped
One instance per scope (e.g., per web request):

```python
@scoped
class UserContext:
    def __init__(self):
        self.user_id = None

# Use with request scope
with request_scope(container) as scope:
    ctx1 = scope.resolve(UserContext)
    ctx2 = scope.resolve(UserContext)
    assert ctx1 is ctx2  # Same instance within scope
```

## Advanced Patterns

### Interface-based Registration

```python
from abc import ABC, abstractmethod

class INotificationService(ABC):
    @abstractmethod
    def send(self, message: str) -> bool:
        pass

@injectable(interface=INotificationService)
class EmailNotificationService(INotificationService):
    def send(self, message: str) -> bool:
        print(f"Sending email: {message}")
        return True

@injectable(interface=INotificationService)
@primary  # Mark as preferred implementation
class SMSNotificationService(INotificationService):
    def send(self, message: str) -> bool:
        print(f"Sending SMS: {message}")
        return True

# Resolve interface - gets primary implementation
service = container.resolve(INotificationService)  # Gets SMSNotificationService

# Resolve all implementations
all_services = container.resolve_all(INotificationService)
```

### Conditional Registration

```python
@injectable
@environment("production")  # Only in production
class ProductionLogger:
    def log(self, message: str):
        # Real logging
        pass

@injectable
@environment("development", "testing")  # Only in dev/test
class ConsoleLogger:
    def log(self, message: str):
        print(message)

@injectable
@profile("feature-x")  # Only when feature-x profile is active
class FeatureXService:
    pass

# Custom conditions
@conditional(lambda ctx: ctx.get('database_type') == 'postgresql')
class PostgreSQLRepository:
    pass
```

### Factory Methods

```python
# Factory functions
def create_redis_cache():
    return RedisCache("localhost:6379")

def create_database_connection(config: DatabaseConfig):
    return Database(config.connection_string)

# Register factories
container.register_singleton(RedisCache, create_redis_cache)
container.register_singleton(Database, create_database_connection)

# Factory classes
class ServiceFactory:
    @staticmethod
    def create_email_service(config: EmailConfig):
        if config.provider == "sendgrid":
            return SendGridEmailService(config.api_key)
        else:
            return SMTPEmailService(config.smtp_settings)

container.register_transient(EmailService, ServiceFactory.create_email_service)
```

### Lazy Initialization

```python
from universal_platform.core.di import LazyProxy

@transient
class ExpensiveService:
    def __init__(self):
        # Expensive initialization
        time.sleep(1)

@transient  
class ServiceConsumer:
    def __init__(self, expensive: LazyProxy[ExpensiveService]):
        self.expensive = expensive  # Not created yet
    
    def do_work(self):
        # Created only when first accessed
        return self.expensive.calculate()

# Or with decorator
@lazy_inject_decorator(ExpensiveService)
def process_data(expensive_service: ExpensiveService):
    # expensive_service is lazy proxy
    return expensive_service.process()
```

### Property and Method Injection

```python
@property_inject(INotificationService, "notifier")
class OrderService:
    def __init__(self):
        self.orders = []
    
    def create_order(self, order_data):
        self.orders.append(order_data)
        # self.notifier automatically injected
        self.notifier.send(f"Order created: {order_data['id']}")

@method_inject("process", IPaymentService, IOrderService)
class PaymentProcessor:
    def process(self, payment_service, order_service, payment_data):
        # Services injected as method parameters
        order = order_service.get_order(payment_data.order_id)
        return payment_service.process_payment(order.amount)
```

### Configuration Binding

```python
# appsettings.json
{
    "database": {
        "host": "localhost",
        "port": 5432,
        "name": "myapp"
    },
    "features": {
        "enable_caching": true,
        "max_cache_size": 1000
    }
}

@dataclass
class DatabaseConfig:
    host: str
    port: int
    name: str

@dataclass  
class FeatureConfig:
    enable_caching: bool
    max_cache_size: int

# Automatic binding
config = create_default_configuration("appsettings.json")
db_config = config.bind(DatabaseConfig)  # Binds from "database" section
feature_config = config.bind(FeatureConfig)  # Binds from "features" section
```

### Multi-tenancy

```python
@injectable
class TenantService:
    def __init__(self, tenant_resolver: ITenantResolver):
        self.tenant_resolver = tenant_resolver
    
    def get_tenant_data(self):
        tenant_id = self.tenant_resolver.get_current_tenant()
        return f"Data for tenant: {tenant_id}"

# Set tenant context
container.resolve(ITenantResolver).set_tenant_context("tenant-123")
service = container.resolve(TenantService)
data = service.get_tenant_data()  # Uses tenant-123 context
```

### Interceptors and AOP

```python
class LoggingInterceptor(IInterceptor):
    def intercept(self, invocation: IInvocation) -> Any:
        print(f"Calling {invocation.method_name}")
        result = invocation.proceed()
        print(f"Completed {invocation.method_name}")
        return result

@injectable(interceptors=[LoggingInterceptor])
class BusinessService:
    def process_business_logic(self):
        return "Business result"

# Method calls will be logged automatically
service = container.resolve(BusinessService)
result = service.process_business_logic()

# AOP decorators
@before(lambda *args, **kwargs: print("Before method"))
@after(lambda *args, **kwargs: print("After method"))
def business_method():
    print("Executing business logic")
```

## Async Support

```python
@injectable
class AsyncEmailService:
    async def send_email_async(self, to: str, message: str):
        await asyncio.sleep(0.1)  # Simulate async work
        return True

@injectable
class AsyncNotificationService:
    def __init__(self, email_service: AsyncEmailService):
        self.email_service = email_service
    
    async def notify_users_async(self, users: List[str]):
        tasks = [
            self.email_service.send_email_async(user, "Hello!")
            for user in users
        ]
        return await asyncio.gather(*tasks)

# Async resolution
async def main():
    service = await container.resolve_async(AsyncNotificationService)
    await service.notify_users_async(["user1@example.com", "user2@example.com"])
```

## Performance Features

### Caching

```python
# Resolution results are cached automatically for singletons
# Custom caching configuration
container = DependencyContainer()
container._performance_cache.max_size = 2000
container._performance_cache.ttl = 600  # 10 minutes

# Performance monitoring
stats = container.get_resolution_stats()
print(f"UserService resolved {stats['UserService']['count']} times")
print(f"Average resolution time: {stats['UserService']['avg_time']}ms")
```

### Object Pooling

```python
from universal_platform.core.di import PooledFactory

# Use pooled factory for expensive objects
pooled_factory = PooledFactory(ServiceFactory(), pool_size=20)
container.register_factory(ExpensiveService, pooled_factory)

# Objects are reused from pool
service1 = container.resolve(ExpensiveService)
# ... use service1
pooled_factory.return_to_pool(ExpensiveService, service1)

service2 = container.resolve(ExpensiveService)  # May reuse service1
```

## Error Handling

### Circular Dependencies

```python
# Automatic detection
@injectable
class ServiceA:
    def __init__(self, service_b: 'ServiceB'):
        self.service_b = service_b

@injectable  
class ServiceB:
    def __init__(self, service_a: ServiceA):
        self.service_a = service_a

try:
    container.resolve(ServiceA)
except CircularDependencyException as e:
    print(f"Circular dependency: {e}")
    # Output: "Circular dependency detected: ServiceA -> ServiceB -> ServiceA"
```

### Missing Dependencies

```python
try:
    service = container.resolve(UnregisteredService)
except ServiceNotRegisteredException as e:
    print(f"Service not found: {e}")
```

## Best Practices

### 1. Use Interfaces
```python
# Good: Depend on abstractions
class OrderService:
    def __init__(self, payment: IPaymentService, notification: INotificationService):
        pass

# Avoid: Depend on concrete classes
class OrderService:
    def __init__(self, payment: StripePaymentService, notification: EmailService):
        pass
```

### 2. Minimize Constructor Complexity
```python
# Good: Simple constructor
@injectable
class UserService:
    def __init__(self, repository: IUserRepository):
        self.repository = repository

# Avoid: Complex initialization in constructor
@injectable
class UserService:
    def __init__(self, repository: IUserRepository):
        self.repository = repository
        self.cache = {}
        self.logger = Logger()
        # ... lots of initialization
```

### 3. Use Appropriate Scopes
```python
# Singleton: Expensive, stateless services
@singleton
class DatabaseConnectionPool:
    pass

# Transient: Lightweight, stateful services
@transient  
class EmailMessage:
    pass

# Scoped: Per-request services
@scoped
class UserContext:
    pass
```

### 4. Leverage Configuration
```python
# Use configuration for environment-specific settings
@injectable
class EmailService:
    def __init__(self, config: EmailConfig):
        self.smtp_host = config.smtp_host
        self.api_key = config.api_key
```

### 5. Handle Disposal
```python
@injectable
class DatabaseService:
    def dispose(self):
        if self.connection:
            self.connection.close()

# Disposal happens automatically when container is disposed
container.dispose()
```

## Integration Examples

### Web Framework Integration
```python
# Flask example
from flask import Flask, g
from universal_platform.core.di import create_web_container, request_scope

app = Flask(__name__)
container = create_web_container("config.json")

@app.before_request
def before_request():
    g.scope = container.create_scope()

@app.teardown_request  
def teardown_request(exception):
    if hasattr(g, 'scope'):
        g.scope.dispose()

@app.route('/users/<int:user_id>')
def get_user(user_id):
    user_service = g.scope.resolve(UserService)
    return user_service.get_user(user_id)
```

### Testing Integration
```python
import pytest
from universal_platform.core.di import create_test_container

@pytest.fixture
def container():
    container = create_test_container()
    
    # Register test doubles
    container.register_singleton(IUserRepository, MockUserRepository)
    container.register_singleton(IEmailService, FakeEmailService)
    
    yield container
    container.dispose()

def test_user_service(container):
    user_service = container.resolve(UserService)
    user = user_service.get_user(123)
    assert user is not None
```

## API Reference

For complete API documentation, see the individual module files:

- `interfaces.py` - Core interfaces and contracts
- `container.py` - Main DI container implementation  
- `scopes.py` - Service scope management
- `factory.py` - Factory patterns and lazy loading
- `decorators.py` - Injection decorators
- `configuration.py` - Configuration binding system

## Examples

See `examples.py` for comprehensive usage examples covering all features.

## Requirements

- Python 3.8+
- PyYAML (for YAML configuration files)
- No other external dependencies

## License

This project is part of the Universal Platform and follows the same licensing terms.