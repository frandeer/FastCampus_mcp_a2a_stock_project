"""
Service Scope Management

This module implements different service scopes and lifetime management
strategies for the dependency injection system.
"""

import asyncio
import threading
import weakref
from typing import Any, Dict, Callable, Optional, Set, List
from collections import defaultdict
from contextlib import contextmanager, asynccontextmanager
from contextvars import ContextVar

from .interfaces import (
    IServiceScope, ILifecycleManager, ServiceScope,
    DependencyInjectionError, InvalidScopeException
)


class DisposableResource:
    """Wrapper for disposable resources"""
    
    def __init__(self, instance: Any, dispose_func: Optional[Callable] = None):
        self.instance = instance
        self.dispose_func = dispose_func
        self.is_disposed = False
    
    def dispose(self) -> None:
        """Dispose the resource"""
        if self.is_disposed:
            return
        
        try:
            if self.dispose_func:
                self.dispose_func(self.instance)
            elif hasattr(self.instance, 'dispose'):
                self.instance.dispose()
            elif hasattr(self.instance, 'close'):
                self.instance.close()
        finally:
            self.is_disposed = True
    
    async def dispose_async(self) -> None:
        """Asynchronously dispose the resource"""
        if self.is_disposed:
            return
        
        try:
            if self.dispose_func:
                if asyncio.iscoroutinefunction(self.dispose_func):
                    await self.dispose_func(self.instance)
                else:
                    self.dispose_func(self.instance)
            elif hasattr(self.instance, 'dispose_async'):
                await self.instance.dispose_async()
            elif hasattr(self.instance, 'dispose'):
                self.instance.dispose()
            elif hasattr(self.instance, 'aclose'):
                await self.instance.aclose()
            elif hasattr(self.instance, 'close'):
                self.instance.close()
        finally:
            self.is_disposed = True


class SingletonScope(IServiceScope):
    """Singleton scope - one instance per container"""
    
    def __init__(self):
        self._instances: Dict[str, DisposableResource] = {}
        self._lock = threading.RLock()
    
    def get_or_create(self, key: str, factory: Callable[[], Any]) -> Any:
        """Get existing singleton or create new one"""
        if key in self._instances:
            resource = self._instances[key]
            if not resource.is_disposed:
                return resource.instance
        
        with self._lock:
            # Double-checked locking
            if key in self._instances:
                resource = self._instances[key]
                if not resource.is_disposed:
                    return resource.instance
            
            instance = factory()
            self._instances[key] = DisposableResource(instance)
            return instance
    
    def dispose(self) -> None:
        """Dispose all singleton instances"""
        with self._lock:
            for resource in self._instances.values():
                try:
                    resource.dispose()
                except Exception:
                    pass  # Log error in production
            self._instances.clear()
    
    async def dispose_async(self) -> None:
        """Asynchronously dispose all instances"""
        instances = []
        with self._lock:
            instances = list(self._instances.values())
            self._instances.clear()
        
        for resource in instances:
            try:
                await resource.dispose_async()
            except Exception:
                pass  # Log error in production


class TransientScope(IServiceScope):
    """Transient scope - new instance every time"""
    
    def __init__(self):
        self._created_instances: Set[weakref.ReferenceType] = set()
        self._lock = threading.RLock()
    
    def get_or_create(self, key: str, factory: Callable[[], Any]) -> Any:
        """Always create new instance for transient scope"""
        instance = factory()
        
        # Track for disposal if needed
        if hasattr(instance, 'dispose') or hasattr(instance, 'close'):
            with self._lock:
                self._created_instances.add(weakref.ref(instance))
        
        return instance
    
    def dispose(self) -> None:
        """Dispose tracked instances that are still alive"""
        with self._lock:
            alive_refs = []
            for ref in self._created_instances:
                instance = ref()
                if instance is not None:
                    try:
                        DisposableResource(instance).dispose()
                    except Exception:
                        pass
                else:
                    alive_refs.append(ref)
            self._created_instances = set(alive_refs)
    
    async def dispose_async(self) -> None:
        """Asynchronously dispose tracked instances"""
        instances = []
        with self._lock:
            for ref in self._created_instances:
                instance = ref()
                if instance is not None:
                    instances.append(instance)
        
        for instance in instances:
            try:
                await DisposableResource(instance).dispose_async()
            except Exception:
                pass


class ScopedServiceScope(IServiceScope):
    """Scoped scope - one instance per scope lifetime"""
    
    def __init__(self, parent_scope: Optional['ScopedServiceScope'] = None):
        self._instances: Dict[str, DisposableResource] = {}
        self._parent_scope = parent_scope
        self._child_scopes: Set['ScopedServiceScope'] = set()
        self._lock = threading.RLock()
        self._is_disposed = False
        
        if parent_scope:
            parent_scope._add_child_scope(self)
    
    def _add_child_scope(self, child: 'ScopedServiceScope') -> None:
        """Add child scope for disposal tracking"""
        with self._lock:
            if not self._is_disposed:
                self._child_scopes.add(child)
    
    def get_or_create(self, key: str, factory: Callable[[], Any]) -> Any:
        """Get existing scoped instance or create new one"""
        if self._is_disposed:
            raise InvalidScopeException("Cannot resolve from disposed scope")
        
        if key in self._instances:
            resource = self._instances[key]
            if not resource.is_disposed:
                return resource.instance
        
        with self._lock:
            if self._is_disposed:
                raise InvalidScopeException("Cannot resolve from disposed scope")
            
            # Double-checked locking
            if key in self._instances:
                resource = self._instances[key]
                if not resource.is_disposed:
                    return resource.instance
            
            instance = factory()
            self._instances[key] = DisposableResource(instance)
            return instance
    
    def create_child_scope(self) -> 'ScopedServiceScope':
        """Create child scope"""
        if self._is_disposed:
            raise InvalidScopeException("Cannot create child scope from disposed scope")
        return ScopedServiceScope(self)
    
    def dispose(self) -> None:
        """Dispose scope and all children"""
        if self._is_disposed:
            return
        
        with self._lock:
            self._is_disposed = True
            
            # Dispose child scopes first
            for child in self._child_scopes:
                try:
                    child.dispose()
                except Exception:
                    pass
            self._child_scopes.clear()
            
            # Dispose instances
            for resource in self._instances.values():
                try:
                    resource.dispose()
                except Exception:
                    pass
            self._instances.clear()
    
    async def dispose_async(self) -> None:
        """Asynchronously dispose scope"""
        if self._is_disposed:
            return
        
        child_scopes = []
        instances = []
        
        with self._lock:
            self._is_disposed = True
            child_scopes = list(self._child_scopes)
            instances = list(self._instances.values())
            self._child_scopes.clear()
            self._instances.clear()
        
        # Dispose children
        for child in child_scopes:
            try:
                await child.dispose_async()
            except Exception:
                pass
        
        # Dispose instances
        for resource in instances:
            try:
                await resource.dispose_async()
            except Exception:
                pass


# Context variables for per-request and per-thread scopes
_request_scope: ContextVar[Optional[ScopedServiceScope]] = ContextVar('request_scope', default=None)
_thread_local = threading.local()


class PerRequestScope(IServiceScope):
    """Per-request scope using context variables"""
    
    def __init__(self):
        self._lock = threading.RLock()
    
    def get_or_create(self, key: str, factory: Callable[[], Any]) -> Any:
        """Get or create instance in current request context"""
        scope = _request_scope.get()
        if scope is None:
            raise InvalidScopeException("No request scope available. Use create_request_scope() context manager.")
        
        return scope.get_or_create(key, factory)
    
    def dispose(self) -> None:
        """Cannot dispose per-request scope directly"""
        raise InvalidScopeException("Per-request scope must be disposed via context manager")
    
    async def dispose_async(self) -> None:
        """Cannot dispose per-request scope directly"""
        raise InvalidScopeException("Per-request scope must be disposed via context manager")


class PerThreadScope(IServiceScope):
    """Per-thread scope using thread-local storage"""
    
    def __init__(self):
        self._lock = threading.RLock()
    
    def _get_thread_scope(self) -> ScopedServiceScope:
        """Get scope for current thread"""
        if not hasattr(_thread_local, 'scope'):
            _thread_local.scope = ScopedServiceScope()
        return _thread_local.scope
    
    def get_or_create(self, key: str, factory: Callable[[], Any]) -> Any:
        """Get or create instance in current thread"""
        scope = self._get_thread_scope()
        return scope.get_or_create(key, factory)
    
    def dispose(self) -> None:
        """Dispose current thread's scope"""
        if hasattr(_thread_local, 'scope'):
            _thread_local.scope.dispose()
            delattr(_thread_local, 'scope')
    
    async def dispose_async(self) -> None:
        """Asynchronously dispose current thread's scope"""
        if hasattr(_thread_local, 'scope'):
            await _thread_local.scope.dispose_async()
            delattr(_thread_local, 'scope')


class ScopeManager:
    """Manages different service scopes"""
    
    def __init__(self):
        self._singleton_scope = SingletonScope()
        self._transient_scope = TransientScope()
        self._per_request_scope = PerRequestScope()
        self._per_thread_scope = PerThreadScope()
        self._scoped_scopes: Dict[str, ScopedServiceScope] = {}
        self._lock = threading.RLock()
    
    def get_scope(self, scope_type: ServiceScope) -> IServiceScope:
        """Get scope instance by type"""
        if scope_type == ServiceScope.SINGLETON:
            return self._singleton_scope
        elif scope_type == ServiceScope.TRANSIENT:
            return self._transient_scope
        elif scope_type == ServiceScope.PER_REQUEST:
            return self._per_request_scope
        elif scope_type == ServiceScope.PER_THREAD:
            return self._per_thread_scope
        elif scope_type == ServiceScope.SCOPED:
            # Return a default scoped scope or raise error
            raise InvalidScopeException("Scoped services require explicit scope creation")
        else:
            raise ValueError(f"Unknown scope type: {scope_type}")
    
    def create_scoped_scope(self, scope_id: str = None) -> ScopedServiceScope:
        """Create named scoped scope"""
        scope = ScopedServiceScope()
        if scope_id:
            with self._lock:
                self._scoped_scopes[scope_id] = scope
        return scope
    
    def get_scoped_scope(self, scope_id: str) -> Optional[ScopedServiceScope]:
        """Get named scoped scope"""
        with self._lock:
            return self._scoped_scopes.get(scope_id)
    
    def dispose_scope(self, scope_id: str) -> bool:
        """Dispose named scoped scope"""
        with self._lock:
            scope = self._scoped_scopes.pop(scope_id, None)
            if scope:
                scope.dispose()
                return True
            return False
    
    def dispose_all(self) -> None:
        """Dispose all scopes"""
        with self._lock:
            # Dispose scoped scopes
            for scope in self._scoped_scopes.values():
                try:
                    scope.dispose()
                except Exception:
                    pass
            self._scoped_scopes.clear()
        
        # Dispose other scopes
        try:
            self._singleton_scope.dispose()
        except Exception:
            pass
        
        try:
            self._transient_scope.dispose()
        except Exception:
            pass
        
        try:
            self._per_thread_scope.dispose()
        except Exception:
            pass
    
    async def dispose_all_async(self) -> None:
        """Asynchronously dispose all scopes"""
        scoped_scopes = []
        with self._lock:
            scoped_scopes = list(self._scoped_scopes.values())
            self._scoped_scopes.clear()
        
        # Dispose scoped scopes
        for scope in scoped_scopes:
            try:
                await scope.dispose_async()
            except Exception:
                pass
        
        # Dispose other scopes
        try:
            await self._singleton_scope.dispose_async()
        except Exception:
            pass
        
        try:
            await self._transient_scope.dispose_async()
        except Exception:
            pass
        
        try:
            await self._per_thread_scope.dispose_async()
        except Exception:
            pass


# Context managers for request scoping
@contextmanager
def create_request_scope():
    """Create request scope context"""
    scope = ScopedServiceScope()
    token = _request_scope.set(scope)
    try:
        yield scope
    finally:
        _request_scope.reset(token)
        scope.dispose()


@asynccontextmanager
async def create_request_scope_async():
    """Create async request scope context"""
    scope = ScopedServiceScope()
    token = _request_scope.set(scope)
    try:
        yield scope
    finally:
        _request_scope.reset(token)
        await scope.dispose_async()


# Utility functions
def get_current_request_scope() -> Optional[ScopedServiceScope]:
    """Get current request scope"""
    return _request_scope.get()


def has_request_scope() -> bool:
    """Check if request scope is available"""
    return _request_scope.get() is not None