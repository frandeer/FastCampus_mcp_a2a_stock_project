"""
FastAPI main application with dependency injection.

This module demonstrates simplified clean architecture with:
- Dependency injection container
- Proper error handling
- OpenAPI documentation
- Health checks
- CORS and security headers
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError, HTTPException

from dependencies import DependencyContainer
from routers import create_router
from models import ErrorResponse


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan handler.
    Manages startup and shutdown of dependencies.
    """
    # Startup
    container = DependencyContainer()
    await container.startup()
    app.state.container = container
    
    yield
    
    # Shutdown
    await container.shutdown()


def create_app() -> FastAPI:
    """
    Factory function to create FastAPI application.
    
    Returns:
        FastAPI: Configured application instance
    """
    app = FastAPI(
        title="Stock Analysis API",
        description="A simplified clean architecture FastAPI application for stock analysis",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan
    )
    
    # Add middleware
    _configure_middleware(app)
    
    # Add exception handlers
    _configure_exception_handlers(app)
    
    # Add routes
    _configure_routes(app)
    
    return app


def _configure_middleware(app: FastAPI) -> None:
    """Configure application middleware."""
    
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["*"],
    )
    
    # Trusted host middleware (security)
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["localhost", "127.0.0.1", "*.localhost"]
    )


def _configure_exception_handlers(app: FastAPI) -> None:
    """Configure global exception handlers."""
    
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, 
        exc: RequestValidationError
    ) -> JSONResponse:
        """Handle validation errors with detailed information."""
        return JSONResponse(
            status_code=422,
            content=ErrorResponse(
                error="Validation Error",
                message="Invalid request data",
                details=[
                    {
                        "field": ".".join(str(loc) for loc in error["loc"]),
                        "message": error["msg"],
                        "type": error["type"]
                    }
                    for error in exc.errors()
                ]
            ).model_dump()
        )
    
    @app.exception_handler(HTTPException)
    async def http_exception_handler(
        request: Request, 
        exc: HTTPException
    ) -> JSONResponse:
        """Handle HTTP exceptions."""
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(
                error=f"HTTP {exc.status_code}",
                message=exc.detail,
                details=None
            ).model_dump()
        )
    
    @app.exception_handler(Exception)
    async def general_exception_handler(
        request: Request, 
        exc: Exception
    ) -> JSONResponse:
        """Handle unexpected exceptions."""
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                error="Internal Server Error",
                message="An unexpected error occurred",
                details=None
            ).model_dump()
        )


def _configure_routes(app: FastAPI) -> None:
    """Configure application routes."""
    
    # Include main router
    app.include_router(
        create_router(),
        prefix="/api/v1",
        tags=["Stock Analysis API"]
    )
    
    # Health check endpoint (not versioned)
    @app.get("/health", tags=["Health"], response_model=dict)
    async def health_check() -> dict:
        """
        Health check endpoint.
        
        Returns:
            dict: Health status information
        """
        return {
            "status": "healthy",
            "service": "Stock Analysis API",
            "version": "1.0.0"
        }


# Create application instance
app = create_app()


if __name__ == "__main__":
    """Run the application directly."""
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        log_level="info",
        access_log=True
    )