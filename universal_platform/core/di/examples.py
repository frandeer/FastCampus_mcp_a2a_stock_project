"""
Dependency Injection Examples

This module demonstrates various usage patterns of the DI system.
"""

import asyncio
from typing import List, Optional
from abc import ABC, abstractmethod
from dataclasses import dataclass

from . import (
    DependencyContainer, ServiceScope, injectable, inject, singleton, transient,
    scoped, auto_inject, lazy_inject_decorator, property_inject, Configuration,
    ConfigurationBuilder, environment, profile, primary, conditional,
    create_default_container, request_scope
)


# Example 1: Basic Service Registration and Resolution
@dataclass
class DatabaseConfig:
    host: str = "localhost"
    port: int = 5432
    database: str = "myapp"
    username: str = "user"
    password: str = "password"


@singleton
class DatabaseService:
    """Singleton database service"""
    
    def __init__(self, config: DatabaseConfig):
        self.config = config
        self.connection = None
    
    def connect(self):
        print(f"Connecting to {self.config.host}:{self.config.port}/{self.config.database}")
        # Simulate connection
        self.connection = f"connection_to_{self.config.database}"
        return self.connection
    
    def execute_query(self, query: str):
        if not self.connection:
            self.connect()
        return f"Result of: {query}"


@transient
class UserRepository:
    """Transient user repository"""
    
    def __init__(self, db_service: DatabaseService):
        self.db_service = db_service
    
    def get_user(self, user_id: int):
        query = f"SELECT * FROM users WHERE id = {user_id}"
        return self.db_service.execute_query(query)
    
    def get_all_users(self):
        return self.db_service.execute_query("SELECT * FROM users")


@scoped
class UserService:
    """Scoped user service"""
    
    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo
    
    def get_user_details(self, user_id: int):
        user_data = self.user_repo.get_user(user_id)
        return f"User details: {user_data}"


# Example 2: Interface-based Registration
class INotificationService(ABC):
    @abstractmethod
    def send_notification(self, message: str, recipient: str) -> bool:
        pass


@injectable(ServiceScope.SINGLETON, interface=INotificationService)
class EmailNotificationService(INotificationService):
    def send_notification(self, message: str, recipient: str) -> bool:
        print(f"Sending email to {recipient}: {message}")
        return True


@injectable(ServiceScope.SINGLETON, interface=INotificationService)
@primary
class SMSNotificationService(INotificationService):
    def send_notification(self, message: str, recipient: str) -> bool:
        print(f"Sending SMS to {recipient}: {message}")
        return True


# Example 3: Conditional Registration
@injectable(ServiceScope.SINGLETON)
@environment("development", "testing")
class MockPaymentService:
    def process_payment(self, amount: float) -> bool:
        print(f"Mock payment processing: ${amount}")
        return True


@injectable(ServiceScope.SINGLETON)
@environment("production")
class RealPaymentService:
    def process_payment(self, amount: float) -> bool:
        print(f"Real payment processing: ${amount}")
        # Real payment logic here
        return True


# Example 4: Factory Pattern
class CacheServiceFactory:
    @staticmethod
    def create_redis_cache():
        return RedisCache("localhost:6379")
    
    @staticmethod
    def create_memory_cache():
        return MemoryCache()


class RedisCache:
    def __init__(self, connection_string: str):
        self.connection_string = connection_string
    
    def get(self, key: str):
        return f"redis_value_for_{key}"
    
    def set(self, key: str, value: str):
        print(f"Setting {key}={value} in Redis")


class MemoryCache:
    def __init__(self):
        self._cache = {}
    
    def get(self, key: str):
        return self._cache.get(key)
    
    def set(self, key: str, value: str):
        self._cache[key] = value
        print(f"Setting {key}={value} in Memory")


# Example 5: Property Injection
@property_inject(INotificationService, "notification_service")
class OrderService:
    def __init__(self):
        self.orders = []
    
    def create_order(self, order_data: dict):
        self.orders.append(order_data)
        # notification_service will be injected as property
        self.notification_service.send_notification(
            f"Order created: {order_data['id']}", 
            order_data['customer_email']
        )


# Example 6: Method Injection and Function Injection
class ProductService:
    def __init__(self):
        self.products = [
            {"id": 1, "name": "Laptop", "price": 999.99},
            {"id": 2, "name": "Mouse", "price": 29.99}
        ]
    
    def get_products(self):
        return self.products


@inject
def get_user_orders(user_service: UserService, product_service: ProductService):
    """Function with injected dependencies"""
    users = user_service.user_repo.get_all_users()
    products = product_service.get_products()
    return {"users": users, "products": products}


@auto_inject
def process_order_notification(notification_service: INotificationService, order_data: dict):
    """Auto-inject based on type hints"""
    return notification_service.send_notification(
        f"Order {order_data['id']} processed",
        order_data['customer_email']
    )


# Example 7: Lazy Injection
@transient
class ExpensiveService:
    def __init__(self):
        print("Creating expensive service...")
        # Simulate expensive initialization
        import time
        time.sleep(0.1)
    
    def do_work(self):
        return "Expensive work done"


@transient
class LazyConsumerService:
    @lazy_inject_decorator(ExpensiveService)
    def use_expensive_service(self, expensive_service: ExpensiveService):
        # expensive_service is a lazy proxy
        return expensive_service.do_work()


# Example 8: Configuration Binding
@dataclass
class AppSettings:
    app_name: str = "MyApp"
    debug: bool = False
    max_connections: int = 100
    features: List[str] = None
    
    def __post_init__(self):
        if self.features is None:
            self.features = []


# Example 9: Multi-tenant Support
@injectable(ServiceScope.SCOPED)
class TenantService:
    def __init__(self, db_service: DatabaseService):
        self.db_service = db_service
    
    def get_tenant_data(self, tenant_id: str):
        query = f"SELECT * FROM tenant_data WHERE tenant_id = '{tenant_id}'"
        return self.db_service.execute_query(query)


# Example 10: Async Services
@injectable(ServiceScope.SINGLETON)
class AsyncEmailService:
    async def send_email_async(self, to: str, subject: str, body: str):
        print(f"Sending async email to {to}")
        await asyncio.sleep(0.1)  # Simulate async operation
        return True


@injectable(ServiceScope.TRANSIENT)
class AsyncNotificationProcessor:
    def __init__(self, email_service: AsyncEmailService):
        self.email_service = email_service
    
    async def process_notifications(self, notifications: List[dict]):
        tasks = []
        for notification in notifications:
            task = self.email_service.send_email_async(
                notification['to'],
                notification['subject'],
                notification['body']
            )
            tasks.append(task)
        
        results = await asyncio.gather(*tasks)
        return results


def basic_example():
    """Basic DI container usage example"""
    print("=== Basic Example ===")
    
    # Create container and register services
    container = DependencyContainer()
    
    # Register configuration
    config = DatabaseConfig(host="prod-db", database="production")
    container.register_singleton(DatabaseConfig, config)
    
    # Services are auto-registered via decorators if container is set
    from .decorators import set_container
    set_container(container)
    
    # Manual registration alternative
    container.register_singleton(DatabaseService, DatabaseService)
    container.register_transient(UserRepository, UserRepository)
    container.register_scoped(UserService, UserService)
    
    # Resolve services
    user_service = container.resolve(UserService)
    print(user_service.get_user_details(123))
    
    # Multiple resolutions of singleton
    db1 = container.resolve(DatabaseService)
    db2 = container.resolve(DatabaseService)
    print(f"Same singleton instance: {db1 is db2}")
    
    # Multiple resolutions of transient
    repo1 = container.resolve(UserRepository)
    repo2 = container.resolve(UserRepository)
    print(f"Different transient instances: {repo1 is not repo2}")


def interface_example():
    """Interface-based registration example"""
    print("\n=== Interface Example ===")
    
    container = DependencyContainer()
    from .decorators import set_container
    set_container(container)
    
    # Register interface implementations
    container.register_singleton(INotificationService, EmailNotificationService)
    container.register_singleton(INotificationService, SMSNotificationService)
    
    # Resolve primary implementation
    notification_service = container.resolve(INotificationService)
    notification_service.send_notification("Hello!", "user@example.com")
    
    # Resolve all implementations
    all_services = container.resolve_all(INotificationService)
    print(f"Found {len(all_services)} notification services")


def conditional_example():
    """Conditional registration example"""
    print("\n=== Conditional Example ===")
    
    container = DependencyContainer()
    from .decorators import set_container
    set_container(container)
    
    # Test with development environment
    import os
    os.environ['ENVIRONMENT'] = 'development'
    
    try:
        payment_service = container.resolve(MockPaymentService)
        payment_service.process_payment(99.99)
    except:
        print("Mock payment service not available in this environment")


def factory_example():
    """Factory pattern example"""
    print("\n=== Factory Example ===")
    
    container = DependencyContainer()
    
    # Register factory
    container.register_singleton(RedisCache, CacheServiceFactory.create_redis_cache)
    container.register_singleton(MemoryCache, CacheServiceFactory.create_memory_cache)
    
    # Use cache services
    redis_cache = container.resolve(RedisCache)
    redis_cache.set("key1", "value1")
    print(redis_cache.get("key1"))
    
    memory_cache = container.resolve(MemoryCache)
    memory_cache.set("key2", "value2")
    print(memory_cache.get("key2"))


def scoped_example():
    """Scoped services example"""
    print("\n=== Scoped Example ===")
    
    container = DependencyContainer()
    from .decorators import set_container
    set_container(container)
    
    # Register services
    container.register_singleton(DatabaseConfig, DatabaseConfig())
    container.register_singleton(DatabaseService, DatabaseService)
    container.register_transient(UserRepository, UserRepository)
    container.register_scoped(UserService, UserService)
    
    # Use request scope
    with request_scope(container) as scope:
        user_service1 = scope.resolve(UserService)
        user_service2 = scope.resolve(UserService)
        print(f"Same scoped instance: {user_service1 is user_service2}")
    
    # New scope gets new instance
    with request_scope(container) as scope:
        user_service3 = scope.resolve(UserService)
        print(f"Different scope instance: {user_service1 is not user_service3}")


async def async_example():
    """Async services example"""
    print("\n=== Async Example ===")
    
    container = DependencyContainer()
    from .decorators import set_container
    set_container(container)
    
    container.register_singleton(AsyncEmailService, AsyncEmailService)
    container.register_transient(AsyncNotificationProcessor, AsyncNotificationProcessor)
    
    processor = container.resolve(AsyncNotificationProcessor)
    
    notifications = [
        {"to": "user1@example.com", "subject": "Hello", "body": "Welcome!"},
        {"to": "user2@example.com", "subject": "Hello", "body": "Welcome!"}
    ]
    
    results = await processor.process_notifications(notifications)
    print(f"Sent {len(results)} notifications")


def configuration_example():
    """Configuration binding example"""
    print("\n=== Configuration Example ===")
    
    # Create configuration from multiple sources
    config = ConfigurationBuilder() \
        .add_environment_variables("MYAPP_") \
        .add_json_file("appsettings.json") \
        .build()
    
    container = DependencyContainer(config)
    
    # Bind configuration to class
    app_settings = config.bind(AppSettings)
    print(f"App: {app_settings.app_name}, Debug: {app_settings.debug}")
    
    container.register_instance(AppSettings, app_settings)


def main():
    """Run all examples"""
    print("Dependency Injection Examples\n")
    
    basic_example()
    interface_example()
    conditional_example()
    factory_example()
    scoped_example()
    
    # Run async example
    asyncio.run(async_example())
    
    configuration_example()
    
    print("\nAll examples completed!")


if __name__ == "__main__":
    main()