"""
Universal Platform Demo Application

Enterprise demo showcasing all platform capabilities including:
- Multiple business domains running simultaneously
- Plugin hot-loading and configuration
- Multi-tenant data isolation
- Event-driven communication between domains
- Advanced dependency injection
- Configuration hot-reloading
- Performance monitoring and metrics
- API documentation and examples
- Admin dashboard for system management
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import Dict, List, Optional
import uvicorn
from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from prometheus_client import make_asgi_app
import sys

# Add the universal platform to the path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from universal_platform.core.di import (
    DependencyContainer, 
    setup_default_container,
    injectable,
    singleton,
    inject
)
from universal_platform.core.plugins import (
    PluginSystem,
    setup_plugin_logging,
    discover_plugins_in_directory
)
from universal_platform.core.events import (
    EventBus,
    EventBusConfig
)
from universal_platform.core.config import (
    ConfigurationBuilder,
    JsonConfigurationSource,
    EnvironmentConfigurationSource
)

# Import domain modules (will be created)
from demo_app.domains.ecommerce import EcommerceRouter, EcommerceDomain
from demo_app.domains.healthcare import HealthcareRouter, HealthcareDomain  
from demo_app.domains.logistics import LogisticsRouter, LogisticsDomain
from demo_app.domains.shared import (
    TenantManager,
    MetricsCollector,
    HealthChecker,
    AdminDashboard
)

# Global instances
container: Optional[DependencyContainer] = None
plugin_system: Optional[PluginSystem] = None
event_bus: Optional[EventBus] = None
tenant_manager: Optional[TenantManager] = None
metrics_collector: Optional[MetricsCollector] = None

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info("Starting Universal Platform Demo Application...")
    
    global container, plugin_system, event_bus, tenant_manager, metrics_collector
    
    try:
        # Initialize configuration
        config_path = os.path.join(os.path.dirname(__file__), "configurations", "config.json")
        container = setup_default_container(config_path)
        
        # Initialize event bus
        event_config = EventBusConfig(
            transport_type="memory",  # Use memory for demo, can be Redis/RabbitMQ
            max_retries=3,
            circuit_breaker_threshold=5
        )
        event_bus = EventBus(config=event_config)
        await event_bus.initialize()
        
        # Register event bus in container
        container.register_singleton(EventBus, lambda: event_bus)
        
        # Initialize plugin system
        plugin_dirs = [
            os.path.join(os.path.dirname(__file__), "plugins"),
            os.path.join(os.path.dirname(__file__), "domains", "ecommerce", "plugins"),
            os.path.join(os.path.dirname(__file__), "domains", "healthcare", "plugins"),
            os.path.join(os.path.dirname(__file__), "domains", "logistics", "plugins")
        ]
        
        setup_plugin_logging()
        plugin_system = PluginSystem(
            plugin_dirs=plugin_dirs,
            enable_hot_reload=True,
            enable_isolation=True
        )
        await plugin_system.initialize()
        
        # Register plugin system in container
        container.register_singleton(PluginSystem, lambda: plugin_system)
        
        # Initialize shared services
        tenant_manager = container.resolve(TenantManager)
        metrics_collector = container.resolve(MetricsCollector)
        
        # Initialize and start domain plugins
        await load_domain_plugins()
        
        # Initialize domains
        ecommerce_domain = container.resolve(EcommerceDomain)
        healthcare_domain = container.resolve(HealthcareDomain)
        logistics_domain = container.resolve(LogisticsDomain)
        
        await asyncio.gather(
            ecommerce_domain.initialize(),
            healthcare_domain.initialize(),
            logistics_domain.initialize()
        )
        
        # Setup cross-domain event subscriptions
        await setup_cross_domain_events()
        
        logger.info("Universal Platform Demo Application started successfully")
        
    except Exception as e:
        logger.error(f"Failed to start application: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down Universal Platform Demo Application...")
    
    try:
        if plugin_system:
            await plugin_system.shutdown()
        
        if event_bus:
            await event_bus.shutdown()
            
        logger.info("Application shutdown complete")
        
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")


async def load_domain_plugins():
    """Load and start domain-specific plugins"""
    try:
        # Discover and load plugins
        for plugin_dir in plugin_system.plugin_dirs:
            if os.path.exists(plugin_dir):
                discovered = discover_plugins_in_directory(plugin_dir)
                for name, path in discovered.items():
                    try:
                        await plugin_system.registry.register_plugin_path(name, path)
                        await plugin_system.load_plugin(name)
                        await plugin_system.initialize_plugin(name)
                        await plugin_system.start_plugin(name)
                        logger.info(f"Successfully loaded plugin: {name}")
                    except Exception as e:
                        logger.warning(f"Failed to load plugin {name}: {e}")
        
    except Exception as e:
        logger.error(f"Error loading domain plugins: {e}")


async def setup_cross_domain_events():
    """Setup event subscriptions for cross-domain communication"""
    try:
        # E-commerce to Logistics: Order fulfillment
        await event_bus.subscribe("ecommerce.order.created", "logistics.fulfill_order")
        await event_bus.subscribe("logistics.shipment.created", "ecommerce.order.shipped")
        
        # Healthcare to Logistics: Medical supply ordering
        await event_bus.subscribe("healthcare.supply.order", "logistics.medical_delivery")
        
        # General audit events
        await event_bus.subscribe("*.audit.*", "admin.audit_logger")
        
        logger.info("Cross-domain event subscriptions configured")
        
    except Exception as e:
        logger.error(f"Error setting up cross-domain events: {e}")


# Create FastAPI application
app = FastAPI(
    title="Universal Platform Demo",
    description="Enterprise demo application showcasing universal platform capabilities",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan
)

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure properly for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(GZipMiddleware, minimum_size=1000)

# Mount static files and templates
static_path = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_path):
    app.mount("/static", StaticFiles(directory=static_path), name="static")

templates_path = os.path.join(os.path.dirname(__file__), "templates")
if os.path.exists(templates_path):
    templates = Jinja2Templates(directory=templates_path)

# Mount Prometheus metrics
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)


# Dependency providers
def get_container() -> DependencyContainer:
    """Get the global dependency container"""
    if container is None:
        raise HTTPException(status_code=500, detail="Container not initialized")
    return container


def get_plugin_system() -> PluginSystem:
    """Get the global plugin system"""
    if plugin_system is None:
        raise HTTPException(status_code=500, detail="Plugin system not initialized")
    return plugin_system


def get_event_bus() -> EventBus:
    """Get the global event bus"""
    if event_bus is None:
        raise HTTPException(status_code=500, detail="Event bus not initialized")
    return event_bus


def get_tenant_manager() -> TenantManager:
    """Get the tenant manager"""
    if tenant_manager is None:
        raise HTTPException(status_code=500, detail="Tenant manager not initialized")
    return tenant_manager


def get_metrics_collector() -> MetricsCollector:
    """Get the metrics collector"""
    if metrics_collector is None:
        raise HTTPException(status_code=500, detail="Metrics collector not initialized")
    return metrics_collector


# API Routes

@app.get("/")
async def root():
    """Root endpoint with platform information"""
    return {
        "message": "Universal Platform Demo Application",
        "version": "1.0.0",
        "status": "running",
        "domains": ["ecommerce", "healthcare", "logistics"],
        "features": [
            "Multi-domain architecture",
            "Plugin hot-loading", 
            "Event-driven communication",
            "Multi-tenant isolation",
            "Real-time monitoring",
            "Configuration hot-reload"
        ],
        "endpoints": {
            "docs": "/docs",
            "metrics": "/metrics",
            "admin": "/admin",
            "health": "/health",
            "domains": {
                "ecommerce": "/api/v1/ecommerce",
                "healthcare": "/api/v1/healthcare", 
                "logistics": "/api/v1/logistics"
            }
        }
    }


@app.get("/health")
async def health_check(
    health_checker: HealthChecker = Depends(lambda: container.resolve(HealthChecker))
):
    """System health check endpoint"""
    try:
        health_status = await health_checker.check_system_health()
        return {
            "status": "healthy" if health_status["overall_healthy"] else "unhealthy",
            "timestamp": health_status["timestamp"],
            "details": health_status
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e)
        }


@app.get("/status")
async def system_status(
    plugin_sys: PluginSystem = Depends(get_plugin_system),
    metrics: MetricsCollector = Depends(get_metrics_collector)
):
    """Detailed system status information"""
    try:
        plugin_statuses = {}
        for plugin_name in plugin_sys.get_loaded_plugins():
            plugin_statuses[plugin_name] = await plugin_sys.get_plugin_status(plugin_name)
        
        system_metrics = await metrics.get_system_metrics()
        
        return {
            "system": {
                "uptime": system_metrics.get("uptime"),
                "memory_usage": system_metrics.get("memory"),
                "cpu_usage": system_metrics.get("cpu")
            },
            "plugins": plugin_statuses,
            "event_bus": {
                "status": "active" if event_bus else "inactive",
                "handlers_count": len(event_bus.handlers) if event_bus else 0
            },
            "domains_loaded": ["ecommerce", "healthcare", "logistics"]
        }
    except Exception as e:
        logger.error(f"Status check failed: {e}")
        raise HTTPException(status_code=500, detail=f"Status check failed: {str(e)}")


@app.post("/admin/reload-config")
async def reload_configuration():
    """Hot-reload system configuration"""
    try:
        # Reload configuration
        config_path = os.path.join(os.path.dirname(__file__), "configurations", "config.json")
        new_container = setup_default_container(config_path)
        
        # Update global container (in production, this would be more sophisticated)
        global container
        container = new_container
        
        return {"message": "Configuration reloaded successfully"}
    except Exception as e:
        logger.error(f"Configuration reload failed: {e}")
        raise HTTPException(status_code=500, detail=f"Configuration reload failed: {str(e)}")


@app.post("/admin/plugins/{plugin_name}/reload")
async def reload_plugin(
    plugin_name: str,
    plugin_sys: PluginSystem = Depends(get_plugin_system)
):
    """Hot-reload a specific plugin"""
    try:
        # Stop the plugin
        await plugin_sys.stop_plugin(plugin_name)
        
        # Reload the plugin
        await plugin_sys.reload_plugin(plugin_name)
        
        # Start the plugin
        await plugin_sys.start_plugin(plugin_name)
        
        return {"message": f"Plugin '{plugin_name}' reloaded successfully"}
    except Exception as e:
        logger.error(f"Plugin reload failed: {e}")
        raise HTTPException(status_code=500, detail=f"Plugin reload failed: {str(e)}")


@app.get("/admin/plugins")
async def list_plugins(plugin_sys: PluginSystem = Depends(get_plugin_system)):
    """List all loaded plugins with their status"""
    try:
        plugins_info = {}
        for plugin_name in plugin_sys.get_loaded_plugins():
            status = await plugin_sys.get_plugin_status(plugin_name)
            info = plugin_sys.registry.get_plugin_info(plugin_name)
            plugins_info[plugin_name] = {
                "status": status,
                "info": {
                    "name": info.name if info else plugin_name,
                    "version": info.version if info else "unknown",
                    "description": info.description if info else "No description",
                    "dependencies": info.dependencies if info else []
                }
            }
        
        return {"plugins": plugins_info}
    except Exception as e:
        logger.error(f"Failed to list plugins: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list plugins: {str(e)}")


@app.get("/admin/events/stats")
async def event_stats(bus: EventBus = Depends(get_event_bus)):
    """Get event bus statistics"""
    try:
        return {
            "handlers_count": len(bus.handlers),
            "subscriptions": bus.handlers,
            "processed_events": getattr(bus, "processed_count", 0),
            "failed_events": getattr(bus, "failed_count", 0)
        }
    except Exception as e:
        logger.error(f"Failed to get event stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get event stats: {str(e)}")


# Include domain routers
app.include_router(
    EcommerceRouter,
    prefix="/api/v1/ecommerce",
    tags=["E-commerce Domain"]
)

app.include_router(
    HealthcareRouter,
    prefix="/api/v1/healthcare", 
    tags=["Healthcare Domain"]
)

app.include_router(
    LogisticsRouter,
    prefix="/api/v1/logistics",
    tags=["Logistics Domain"]
)

# Admin dashboard routes
app.include_router(
    AdminDashboard.router,
    prefix="/admin",
    tags=["Administration"]
)


# Background tasks for demonstration
@app.on_event("startup")
async def start_background_tasks():
    """Start background monitoring and demo tasks"""
    asyncio.create_task(demo_cross_domain_workflow())
    asyncio.create_task(metrics_collection_task())


async def demo_cross_domain_workflow():
    """Demonstrate cross-domain integration"""
    await asyncio.sleep(30)  # Wait for system to be fully ready
    
    try:
        # Simulate an e-commerce order that triggers logistics fulfillment
        order_event = {
            "order_id": "demo-001",
            "customer_id": "customer-123",
            "items": [
                {"product_id": "prod-001", "quantity": 2},
                {"product_id": "prod-002", "quantity": 1}
            ],
            "shipping_address": {
                "street": "123 Demo St",
                "city": "Demo City",
                "zip": "12345"
            }
        }
        
        await event_bus.publish("ecommerce.order.created", order_event)
        logger.info("Demo cross-domain workflow triggered")
        
    except Exception as e:
        logger.error(f"Demo workflow failed: {e}")


async def metrics_collection_task():
    """Background task for collecting system metrics"""
    while True:
        try:
            await asyncio.sleep(60)  # Collect metrics every minute
            
            if metrics_collector:
                await metrics_collector.collect_system_metrics()
                await metrics_collector.collect_plugin_metrics(plugin_system)
                await metrics_collector.collect_event_metrics(event_bus)
                
        except Exception as e:
            logger.error(f"Metrics collection failed: {e}")


if __name__ == "__main__":
    # Configuration for development
    config = {
        "host": os.getenv("HOST", "0.0.0.0"),
        "port": int(os.getenv("PORT", 8000)),
        "reload": os.getenv("ENVIRONMENT", "development") == "development",
        "log_level": os.getenv("LOG_LEVEL", "info").lower()
    }
    
    logger.info(f"Starting server on {config['host']}:{config['port']}")
    uvicorn.run("main:app", **config)