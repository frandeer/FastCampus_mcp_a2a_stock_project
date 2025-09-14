"""
FastAPI application implementing simplified clean architecture.

This package demonstrates:
- Dependency injection pattern with service containers
- Clean separation of concerns
- Interface-based programming
- Proper error handling and validation
- OpenAPI documentation integration
"""

from .main import app, create_app
from .dependencies import DependencyContainer
from .routers import create_router

__version__ = "1.0.0"

__all__ = [
    "app",
    "create_app", 
    "DependencyContainer",
    "create_router"
]