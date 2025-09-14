"""
Tenant middleware for automatic context setup.

Provides middleware implementations for popular web frameworks
to automatically resolve and set tenant context from incoming requests.
"""

import asyncio
import logging
from typing import Any, Awaitable, Callable, Dict, Optional, Union

from .routing import ResolutionResult, TenantRouterManager
from .tenant_context import TenantContext, set_current_tenant, clear_tenant_context

logger = logging.getLogger(__name__)


class TenantMiddlewareError(Exception):
    """Exception raised by tenant middleware."""
    pass


class TenantMiddleware:
    """
    Base tenant middleware class.
    
    Provides common functionality for tenant resolution and context setup
    that can be extended for specific web frameworks.
    """
    
    def __init__(self, 
                 router_manager: TenantRouterManager,
                 resolver_name: Optional[str] = None,
                 require_tenant: bool = True,
                 default_tenant_id: Optional[str] = None,
                 on_resolution_error: Optional[Callable[[Exception], Any]] = None):
        """
        Initialize tenant middleware.
        
        Args:
            router_manager: The tenant router manager
            resolver_name: Name of resolver to use (None for default/composite)
            require_tenant: Whether tenant resolution is required
            default_tenant_id: Default tenant ID if resolution fails
            on_resolution_error: Callback for handling resolution errors
        """
        self.router_manager = router_manager
        self.resolver_name = resolver_name
        self.require_tenant = require_tenant
        self.default_tenant_id = default_tenant_id
        self.on_resolution_error = on_resolution_error
    
    def extract_request_data(self, request: Any) -> Dict[str, Any]:
        """
        Extract relevant data from request object.
        
        This method should be overridden by framework-specific implementations.
        
        Args:
            request: The framework-specific request object
            
        Returns:
            Dict[str, Any]: Extracted request data
        """
        return {}
    
    def handle_resolution_result(self, result: ResolutionResult, request: Any) -> Optional[TenantContext]:
        """
        Handle the result of tenant resolution.
        
        Args:
            result: The resolution result
            request: The original request object
            
        Returns:
            Optional[TenantContext]: The tenant context or None
        """
        if result.is_successful:
            # Create tenant context
            context = TenantContext(
                tenant=result.tenant_info,
                user_id=self._extract_user_id(request),
                permissions=self._extract_permissions(request),
                features=self._extract_features(request),
                settings=self._extract_settings(request)
            )
            return context
        
        elif not self.require_tenant and self.default_tenant_id:
            # Use default tenant if available and not required
            from .tenant_context import TenantInfo
            default_tenant = TenantInfo(
                tenant_id=self.default_tenant_id,
                tenant_name="Default Tenant",
                metadata={"source": "default"}
            )
            context = TenantContext(tenant=default_tenant)
            return context
        
        return None
    
    def _extract_user_id(self, request: Any) -> Optional[str]:
        """Extract user ID from request (to be overridden)."""
        return None
    
    def _extract_permissions(self, request: Any) -> set:
        """Extract user permissions from request (to be overridden)."""
        return set()
    
    def _extract_features(self, request: Any) -> Dict[str, bool]:
        """Extract feature flags from request (to be overridden)."""
        return {}
    
    def _extract_settings(self, request: Any) -> Dict[str, Any]:
        """Extract additional settings from request (to be overridden)."""
        return {}
    
    def handle_error(self, error: Exception, request: Any) -> Any:
        """
        Handle middleware errors.
        
        Args:
            error: The exception that occurred
            request: The original request object
            
        Returns:
            Any: Framework-specific error response or None to continue
        """
        if self.on_resolution_error:
            return self.on_resolution_error(error)
        
        logger.error(f"Tenant middleware error: {error}")
        
        if self.require_tenant:
            raise error
        
        return None


class FastAPITenantMiddleware:
    """FastAPI-specific tenant middleware."""
    
    def __init__(self, 
                 router_manager: TenantRouterManager,
                 resolver_name: Optional[str] = None,
                 require_tenant: bool = True,
                 default_tenant_id: Optional[str] = None,
                 excluded_paths: Optional[list] = None):
        """
        Initialize FastAPI tenant middleware.
        
        Args:
            router_manager: The tenant router manager
            resolver_name: Name of resolver to use
            require_tenant: Whether tenant resolution is required
            default_tenant_id: Default tenant ID if resolution fails
            excluded_paths: List of paths to exclude from tenant resolution
        """
        self.base_middleware = TenantMiddleware(
            router_manager=router_manager,
            resolver_name=resolver_name,
            require_tenant=require_tenant,
            default_tenant_id=default_tenant_id
        )
        self.excluded_paths = excluded_paths or ["/health", "/metrics", "/docs", "/openapi.json"]
    
    async def __call__(self, request, call_next):
        """FastAPI middleware call method."""
        # Check if path should be excluded
        if any(request.url.path.startswith(path) for path in self.excluded_paths):
            return await call_next(request)
        
        try:
            # Extract request data
            request_data = await self._extract_request_data(request)
            
            # Resolve tenant
            result = self.base_middleware.router_manager.resolve_tenant(
                request_data, 
                self.base_middleware.resolver_name
            )
            
            # Handle resolution result
            context = self.base_middleware.handle_resolution_result(result, request)
            
            if context:
                # Set tenant context
                set_current_tenant(context)
                
                # Add tenant info to request state
                request.state.tenant_context = context
                request.state.tenant_id = context.tenant_id
                
                try:
                    response = await call_next(request)
                    
                    # Add tenant headers to response
                    response.headers["X-Tenant-ID"] = context.tenant_id
                    response.headers["X-Tenant-Name"] = context.tenant_name
                    
                    return response
                finally:
                    # Clean up context
                    clear_tenant_context()
            
            elif self.base_middleware.require_tenant:
                # Return 400 if tenant is required but not found
                from fastapi import HTTPException
                raise HTTPException(
                    status_code=400,
                    detail=f"Tenant resolution failed: {result.metadata.get('error', 'Unknown error')}"
                )
            else:
                # Continue without tenant context
                return await call_next(request)
        
        except Exception as e:
            error_response = self.base_middleware.handle_error(e, request)
            if error_response:
                return error_response
            raise
    
    async def _extract_request_data(self, request) -> Dict[str, Any]:
        """Extract request data for FastAPI."""
        headers = dict(request.headers)
        
        return {
            "host": request.url.hostname,
            "domain": request.url.hostname,
            "path": request.url.path,
            "url": str(request.url),
            "headers": headers,
            "method": request.method,
            "query_params": dict(request.query_params)
        }


class DjangoTenantMiddleware:
    """Django-specific tenant middleware."""
    
    def __init__(self, get_response, 
                 router_manager: TenantRouterManager,
                 resolver_name: Optional[str] = None,
                 require_tenant: bool = True,
                 default_tenant_id: Optional[str] = None,
                 excluded_paths: Optional[list] = None):
        """
        Initialize Django tenant middleware.
        
        Args:
            get_response: Django get_response callable
            router_manager: The tenant router manager
            resolver_name: Name of resolver to use
            require_tenant: Whether tenant resolution is required
            default_tenant_id: Default tenant ID if resolution fails
            excluded_paths: List of paths to exclude from tenant resolution
        """
        self.get_response = get_response
        self.base_middleware = TenantMiddleware(
            router_manager=router_manager,
            resolver_name=resolver_name,
            require_tenant=require_tenant,
            default_tenant_id=default_tenant_id
        )
        self.excluded_paths = excluded_paths or ["/admin", "/health", "/metrics"]
    
    def __call__(self, request):
        """Django middleware call method."""
        # Check if path should be excluded
        if any(request.path.startswith(path) for path in self.excluded_paths):
            return self.get_response(request)
        
        try:
            # Extract request data
            request_data = self._extract_request_data(request)
            
            # Resolve tenant
            result = self.base_middleware.router_manager.resolve_tenant(
                request_data, 
                self.base_middleware.resolver_name
            )
            
            # Handle resolution result
            context = self.base_middleware.handle_resolution_result(result, request)
            
            if context:
                # Set tenant context
                set_current_tenant(context)
                
                # Add tenant info to request
                request.tenant_context = context
                request.tenant_id = context.tenant_id
                
                try:
                    response = self.get_response(request)
                    
                    # Add tenant headers to response
                    response["X-Tenant-ID"] = context.tenant_id
                    response["X-Tenant-Name"] = context.tenant_name
                    
                    return response
                finally:
                    # Clean up context
                    clear_tenant_context()
            
            elif self.base_middleware.require_tenant:
                # Return 400 if tenant is required but not found
                from django.http import JsonResponse
                return JsonResponse(
                    {"error": f"Tenant resolution failed: {result.metadata.get('error', 'Unknown error')}"},
                    status=400
                )
            else:
                # Continue without tenant context
                return self.get_response(request)
        
        except Exception as e:
            error_response = self.base_middleware.handle_error(e, request)
            if error_response:
                return error_response
            raise
    
    def _extract_request_data(self, request) -> Dict[str, Any]:
        """Extract request data for Django."""
        # Get headers (Django uses META with HTTP_ prefix)
        headers = {}
        for key, value in request.META.items():
            if key.startswith('HTTP_'):
                header_name = key[5:].replace('_', '-').title()
                headers[header_name] = value
        
        return {
            "host": request.get_host(),
            "domain": request.get_host().split(':')[0],
            "path": request.path,
            "url": request.build_absolute_uri(),
            "headers": headers,
            "method": request.method,
            "query_params": dict(request.GET)
        }


class FlaskTenantMiddleware:
    """Flask-specific tenant middleware."""
    
    def __init__(self, app, 
                 router_manager: TenantRouterManager,
                 resolver_name: Optional[str] = None,
                 require_tenant: bool = True,
                 default_tenant_id: Optional[str] = None,
                 excluded_paths: Optional[list] = None):
        """
        Initialize Flask tenant middleware.
        
        Args:
            app: Flask application instance
            router_manager: The tenant router manager
            resolver_name: Name of resolver to use
            require_tenant: Whether tenant resolution is required
            default_tenant_id: Default tenant ID if resolution fails
            excluded_paths: List of paths to exclude from tenant resolution
        """
        self.app = app
        self.base_middleware = TenantMiddleware(
            router_manager=router_manager,
            resolver_name=resolver_name,
            require_tenant=require_tenant,
            default_tenant_id=default_tenant_id
        )
        self.excluded_paths = excluded_paths or ["/health", "/metrics"]
        
        # Register Flask hooks
        app.before_request(self.before_request)
        app.after_request(self.after_request)
        app.teardown_appcontext(self.teardown_appcontext)
    
    def before_request(self):
        """Flask before_request handler."""
        from flask import request, g, abort, jsonify
        
        # Check if path should be excluded
        if any(request.path.startswith(path) for path in self.excluded_paths):
            return
        
        try:
            # Extract request data
            request_data = self._extract_request_data(request)
            
            # Resolve tenant
            result = self.base_middleware.router_manager.resolve_tenant(
                request_data, 
                self.base_middleware.resolver_name
            )
            
            # Handle resolution result
            context = self.base_middleware.handle_resolution_result(result, request)
            
            if context:
                # Set tenant context
                set_current_tenant(context)
                
                # Store in Flask g object
                g.tenant_context = context
                g.tenant_id = context.tenant_id
            
            elif self.base_middleware.require_tenant:
                # Return 400 if tenant is required but not found
                abort(400, description=f"Tenant resolution failed: {result.metadata.get('error', 'Unknown error')}")
        
        except Exception as e:
            error_response = self.base_middleware.handle_error(e, request)
            if error_response:
                return error_response
            raise
    
    def after_request(self, response):
        """Flask after_request handler."""
        from flask import g
        
        # Add tenant headers to response if tenant context exists
        if hasattr(g, 'tenant_context') and g.tenant_context:
            response.headers["X-Tenant-ID"] = g.tenant_context.tenant_id
            response.headers["X-Tenant-Name"] = g.tenant_context.tenant_name
        
        return response
    
    def teardown_appcontext(self, error):
        """Flask teardown_appcontext handler."""
        # Clean up tenant context
        clear_tenant_context()
    
    def _extract_request_data(self, request) -> Dict[str, Any]:
        """Extract request data for Flask."""
        return {
            "host": request.host,
            "domain": request.host.split(':')[0],
            "path": request.path,
            "url": request.url,
            "headers": dict(request.headers),
            "method": request.method,
            "query_params": dict(request.args)
        }


class ASGITenantMiddleware:
    """Generic ASGI tenant middleware."""
    
    def __init__(self, app,
                 router_manager: TenantRouterManager,
                 resolver_name: Optional[str] = None,
                 require_tenant: bool = True,
                 default_tenant_id: Optional[str] = None,
                 excluded_paths: Optional[list] = None):
        """
        Initialize ASGI tenant middleware.
        
        Args:
            app: ASGI application
            router_manager: The tenant router manager
            resolver_name: Name of resolver to use
            require_tenant: Whether tenant resolution is required
            default_tenant_id: Default tenant ID if resolution fails
            excluded_paths: List of paths to exclude from tenant resolution
        """
        self.app = app
        self.base_middleware = TenantMiddleware(
            router_manager=router_manager,
            resolver_name=resolver_name,
            require_tenant=require_tenant,
            default_tenant_id=default_tenant_id
        )
        self.excluded_paths = excluded_paths or ["/health", "/metrics"]
    
    async def __call__(self, scope, receive, send):
        """ASGI middleware call method."""
        if scope["type"] != "http":
            # Pass through non-HTTP requests
            await self.app(scope, receive, send)
            return
        
        # Check if path should be excluded
        path = scope.get("path", "")
        if any(path.startswith(excluded) for excluded in self.excluded_paths):
            await self.app(scope, receive, send)
            return
        
        try:
            # Extract request data from ASGI scope
            request_data = self._extract_request_data(scope)
            
            # Resolve tenant
            result = self.base_middleware.router_manager.resolve_tenant(
                request_data, 
                self.base_middleware.resolver_name
            )
            
            # Handle resolution result
            context = self.base_middleware.handle_resolution_result(result, scope)
            
            if context:
                # Set tenant context
                set_current_tenant(context)
                
                # Add tenant info to ASGI scope
                scope["tenant_context"] = context
                scope["tenant_id"] = context.tenant_id
                
                # Wrap send to add tenant headers
                async def wrapped_send(message):
                    if message["type"] == "http.response.start":
                        headers = list(message.get("headers", []))
                        headers.append([b"x-tenant-id", context.tenant_id.encode()])
                        headers.append([b"x-tenant-name", context.tenant_name.encode()])
                        message["headers"] = headers
                    await send(message)
                
                try:
                    await self.app(scope, receive, wrapped_send)
                finally:
                    # Clean up context
                    clear_tenant_context()
            
            elif self.base_middleware.require_tenant:
                # Return 400 if tenant is required but not found
                await self._send_error_response(
                    send, 
                    400, 
                    f"Tenant resolution failed: {result.metadata.get('error', 'Unknown error')}"
                )
            else:
                # Continue without tenant context
                await self.app(scope, receive, send)
        
        except Exception as e:
            error_response = self.base_middleware.handle_error(e, scope)
            if error_response:
                await self._send_error_response(send, 500, str(e))
            else:
                raise
    
    def _extract_request_data(self, scope) -> Dict[str, Any]:
        """Extract request data from ASGI scope."""
        # Parse headers
        headers = {}
        for name, value in scope.get("headers", []):
            headers[name.decode().lower()] = value.decode()
        
        # Construct host from headers or server info
        host = headers.get("host")
        if not host and "server" in scope:
            server = scope["server"]
            host = f"{server[0]}:{server[1]}"
        
        return {
            "host": host,
            "domain": host.split(':')[0] if host else None,
            "path": scope.get("path", ""),
            "headers": headers,
            "method": scope.get("method", "GET"),
            "query_string": scope.get("query_string", b"").decode()
        }
    
    async def _send_error_response(self, send, status_code: int, message: str):
        """Send an error response."""
        response_body = f'{{"error": "{message}"}}'.encode()
        
        await send({
            "type": "http.response.start",
            "status": status_code,
            "headers": [
                [b"content-type", b"application/json"],
                [b"content-length", str(len(response_body)).encode()],
            ],
        })
        
        await send({
            "type": "http.response.body",
            "body": response_body,
        })


class TenantMiddlewareFactory:
    """Factory for creating tenant middleware for different frameworks."""
    
    @staticmethod
    def create_fastapi_middleware(router_manager: TenantRouterManager, **kwargs) -> FastAPITenantMiddleware:
        """Create FastAPI tenant middleware."""
        return FastAPITenantMiddleware(router_manager, **kwargs)
    
    @staticmethod
    def create_django_middleware(router_manager: TenantRouterManager, **kwargs):
        """Create Django tenant middleware class."""
        def django_middleware(get_response):
            return DjangoTenantMiddleware(get_response, router_manager, **kwargs)
        return django_middleware
    
    @staticmethod
    def create_flask_middleware(app, router_manager: TenantRouterManager, **kwargs) -> FlaskTenantMiddleware:
        """Create Flask tenant middleware."""
        return FlaskTenantMiddleware(app, router_manager, **kwargs)
    
    @staticmethod
    def create_asgi_middleware(router_manager: TenantRouterManager, **kwargs):
        """Create ASGI tenant middleware class."""
        def asgi_middleware(app):
            return ASGITenantMiddleware(app, router_manager, **kwargs)
        return asgi_middleware