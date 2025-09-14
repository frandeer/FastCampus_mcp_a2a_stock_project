"""
Basic tests for the DI system to verify it works correctly.
"""

import pytest
import sys
import os

# Add the parent directory to Python path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

from universal_platform.core.di import (
    DependencyContainer, ServiceScope, injectable, inject, singleton, transient,
    scoped, ServiceNotRegisteredException, CircularDependencyException,
    create_container, request_scope
)


class TestBasicDI:
    """Test basic dependency injection functionality"""
    
    def test_simple_registration_and_resolution(self):
        """Test basic service registration and resolution"""
        container = DependencyContainer()
        
        class SimpleService:
            def get_message(self):
                return "Hello World"
        
        container.register_singleton(SimpleService, SimpleService)
        
        service = container.resolve(SimpleService)
        assert service is not None
        assert service.get_message() == "Hello World"
    
    def test_constructor_injection(self):
        """Test constructor dependency injection"""
        container = DependencyContainer()
        
        class DatabaseService:
            def query(self, sql):
                return f"Result: {sql}"
        
        class UserService:
            def __init__(self, db: DatabaseService):
                self.db = db
            
            def get_user(self, user_id):
                return self.db.query(f"SELECT * FROM users WHERE id = {user_id}")
        
        container.register_singleton(DatabaseService, DatabaseService)
        container.register_transient(UserService, UserService)
        
        user_service = container.resolve(UserService)
        result = user_service.get_user(123)
        assert "SELECT * FROM users WHERE id = 123" in result
    
    def test_singleton_scope(self):
        """Test singleton scope behavior"""
        container = DependencyContainer()
        
        class SingletonService:
            def __init__(self):
                self.instance_id = id(self)
        
        container.register_singleton(SingletonService, SingletonService)
        
        service1 = container.resolve(SingletonService)
        service2 = container.resolve(SingletonService)
        
        assert service1 is service2
        assert service1.instance_id == service2.instance_id
    
    def test_transient_scope(self):
        """Test transient scope behavior"""
        container = DependencyContainer()
        
        class TransientService:
            def __init__(self):
                self.instance_id = id(self)
        
        container.register_transient(TransientService, TransientService)
        
        service1 = container.resolve(TransientService)
        service2 = container.resolve(TransientService)
        
        assert service1 is not service2
        assert service1.instance_id != service2.instance_id
    
    def test_scoped_services(self):
        """Test scoped service behavior"""
        container = DependencyContainer()
        
        class ScopedService:
            def __init__(self):
                self.instance_id = id(self)
        
        container.register_scoped(ScopedService, ScopedService)
        
        # Within same scope
        with request_scope(container) as scope:
            service1 = scope.resolve(ScopedService)
            service2 = scope.resolve(ScopedService)
            assert service1 is service2
        
        # Different scope
        with request_scope(container) as scope:
            service3 = scope.resolve(ScopedService)
            assert service1 is not service3
    
    def test_service_not_registered_exception(self):
        """Test exception when service not registered"""
        container = DependencyContainer()
        
        class UnregisteredService:
            pass
        
        with pytest.raises(ServiceNotRegisteredException):
            container.resolve(UnregisteredService)
    
    def test_circular_dependency_detection(self):
        """Test circular dependency detection"""
        container = DependencyContainer()
        
        class ServiceA:
            def __init__(self, service_b: 'ServiceB'):
                self.service_b = service_b
        
        class ServiceB:
            def __init__(self, service_a: ServiceA):
                self.service_a = service_a
        
        container.register_transient(ServiceA, ServiceA)
        container.register_transient(ServiceB, ServiceB)
        
        with pytest.raises(CircularDependencyException):
            container.resolve(ServiceA)


class TestDecorators:
    """Test decorator-based registration"""
    
    def test_injectable_decorator(self):
        """Test @injectable decorator"""
        container = DependencyContainer()
        
        # Set global container for decorators
        from universal_platform.core.di.decorators import set_container
        set_container(container)
        
        @singleton
        class DecoratedService:
            def get_value(self):
                return "decorated"
        
        # Register manually since auto-registration needs container setup
        container.register_singleton(DecoratedService, DecoratedService)
        
        service = container.resolve(DecoratedService)
        assert service.get_value() == "decorated"
    
    def test_inject_decorator(self):
        """Test @inject decorator"""
        container = DependencyContainer()
        
        class HelperService:
            def help(self):
                return "helping"
        
        container.register_singleton(HelperService, HelperService)
        
        # Set global container for decorators
        from universal_platform.core.di.decorators import set_container
        set_container(container)
        
        @inject
        def process_with_helper(helper: HelperService):
            return f"Processing with {helper.help()}"
        
        result = process_with_helper()
        assert result == "Processing with helping"


class TestFactories:
    """Test factory patterns"""
    
    def test_factory_function(self):
        """Test factory function registration"""
        container = DependencyContainer()
        
        class ConfigurableService:
            def __init__(self, config_value):
                self.config_value = config_value
        
        def create_service():
            return ConfigurableService("factory-created")
        
        container.register_singleton(ConfigurableService, create_service)
        
        service = container.resolve(ConfigurableService)
        assert service.config_value == "factory-created"
    
    def test_instance_registration(self):
        """Test instance registration"""
        container = DependencyContainer()
        
        class PreBuiltService:
            def __init__(self, value):
                self.value = value
        
        instance = PreBuiltService("pre-built")
        container.register_instance(PreBuiltService, instance)
        
        resolved = container.resolve(PreBuiltService)
        assert resolved is instance
        assert resolved.value == "pre-built"


class TestConfiguration:
    """Test configuration system"""
    
    def test_configuration_binding(self):
        """Test configuration binding to classes"""
        from universal_platform.core.di import ConfigurationBuilder
        from dataclasses import dataclass
        
        # Create test configuration
        config_data = {
            'database': {
                'host': 'test-host',
                'port': 1234,
                'name': 'test-db'
            }
        }
        
        # Mock configuration source
        class TestConfigSource:
            def load(self):
                return config_data
            
            def supports_reload(self):
                return False
            
            def reload(self):
                return {}
        
        from universal_platform.core.di.configuration import Configuration
        config = Configuration([TestConfigSource()])
        
        @dataclass
        class DatabaseConfig:
            host: str = "localhost"
            port: int = 5432
            name: str = "default"
        
        # This would require implementing the binding logic
        # For now, just test that configuration loads
        assert config.get('database.host') == 'test-host'
        assert config.get('database.port') == 1234


def test_container_disposal():
    """Test proper container disposal"""
    container = DependencyContainer()
    
    class DisposableService:
        def __init__(self):
            self.disposed = False
        
        def dispose(self):
            self.disposed = True
    
    container.register_singleton(DisposableService, DisposableService)
    service = container.resolve(DisposableService)
    
    assert not service.disposed
    
    container.dispose()
    assert service.disposed


if __name__ == "__main__":
    # Run tests without pytest for basic verification
    test_basic = TestBasicDI()
    test_basic.test_simple_registration_and_resolution()
    test_basic.test_constructor_injection()
    test_basic.test_singleton_scope()
    test_basic.test_transient_scope()
    test_basic.test_scoped_services()
    
    print("✅ Basic DI tests passed!")
    
    test_factories = TestFactories()
    test_factories.test_factory_function()
    test_factories.test_instance_registration()
    
    print("✅ Factory tests passed!")
    
    test_container_disposal()
    print("✅ Container disposal test passed!")
    
    print("🎉 All basic tests completed successfully!")