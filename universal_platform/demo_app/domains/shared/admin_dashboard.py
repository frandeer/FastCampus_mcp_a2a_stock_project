"""
Admin dashboard for system management and monitoring
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import os

from ...core.di import injectable, singleton, inject
from ...core.events import EventBus
from ...core.plugins import PluginSystem
from .models import BaseResponse, ErrorResponse, HealthStatus
from .tenant_manager import TenantManager
from .metrics_collector import MetricsCollector
from .health_checker import HealthChecker
from .auth import AuthenticationManager, AuthorizationManager, Permission

logger = logging.getLogger(__name__)

# Get templates directory
templates_dir = os.path.join(os.path.dirname(__file__), "..", "..", "templates")
templates = Jinja2Templates(directory=templates_dir) if os.path.exists(templates_dir) else None


@singleton
@injectable
class AdminDashboard:
    """
    Admin dashboard providing:
    - System overview and monitoring
    - Plugin management
    - Tenant management
    - Configuration management
    - Health monitoring
    - Metrics visualization
    - Event system monitoring
    - Security and audit logs
    """
    
    def __init__(
        self,
        event_bus: EventBus,
        plugin_system: PluginSystem,
        tenant_manager: TenantManager,
        metrics_collector: MetricsCollector,
        health_checker: HealthChecker,
        auth_manager: AuthenticationManager,
        auth_z_manager: AuthorizationManager
    ):
        self.event_bus = event_bus
        self.plugin_system = plugin_system
        self.tenant_manager = tenant_manager
        self.metrics_collector = metrics_collector
        self.health_checker = health_checker
        self.auth_manager = auth_manager
        self.auth_z_manager = auth_z_manager
        self.router = APIRouter()
        
        # Setup routes
        self._setup_routes()
    
    def _setup_routes(self):
        """Setup admin dashboard routes"""
        
        @self.router.get("/", response_class=HTMLResponse)
        async def admin_dashboard(request: Request):
            """Main admin dashboard page"""
            if templates:
                return templates.TemplateResponse("admin/dashboard.html", {
                    "request": request,
                    "title": "Universal Platform Admin Dashboard"
                })
            else:
                return HTMLResponse("""
                <html>
                <head><title>Universal Platform Admin</title></head>
                <body>
                    <h1>Universal Platform Admin Dashboard</h1>
                    <p>Use the API endpoints to manage the system:</p>
                    <ul>
                        <li><a href="/admin/overview">System Overview</a></li>
                        <li><a href="/admin/plugins">Plugin Management</a></li>
                        <li><a href="/admin/tenants">Tenant Management</a></li>
                        <li><a href="/admin/health">Health Status</a></li>
                        <li><a href="/admin/metrics">System Metrics</a></li>
                    </ul>
                </body>
                </html>
                """)
        
        @self.router.get("/overview")
        async def system_overview():
            """Get system overview information"""
            try:
                # Get basic system information
                health_status = await self.health_checker.check_system_health()
                metrics_summary = await self.metrics_collector.get_metrics_summary()
                
                # Get plugin information
                loaded_plugins = self.plugin_system.get_loaded_plugins()
                plugin_statuses = {}
                for plugin_name in loaded_plugins:
                    plugin_statuses[plugin_name] = await self.plugin_system.get_plugin_status(plugin_name)
                
                # Get tenant information
                tenants = await self.tenant_manager.list_tenants()
                
                return {
                    "system": {
                        "status": health_status.get("state", "unknown"),
                        "uptime_seconds": metrics_summary.get("uptime_seconds", 0),
                        "timestamp": datetime.utcnow().isoformat()
                    },
                    "health": {
                        "overall_healthy": health_status.get("overall_healthy", False),
                        "checks_total": health_status.get("checks_total", 0),
                        "checks_healthy": health_status.get("checks_healthy", 0),
                        "critical_failures": health_status.get("critical_failures", [])
                    },
                    "performance": {
                        "cpu_usage_percent": metrics_summary.get("cpu_usage_percent"),
                        "memory_usage_percent": metrics_summary.get("memory_usage_percent"),
                        "disk_usage_percent": metrics_summary.get("disk_usage_percent"),
                        "avg_response_time_ms": metrics_summary.get("avg_response_time_ms")
                    },
                    "plugins": {
                        "total_loaded": len(loaded_plugins),
                        "active_count": len([s for s in plugin_statuses.values() if s.get("state") == "RUNNING"]),
                        "statuses": plugin_statuses
                    },
                    "tenants": {
                        "total_count": len(tenants),
                        "active_count": len([t for t in tenants if t.status.value == "active"])
                    },
                    "events": {
                        "handlers_count": len(self.event_bus.handlers) if hasattr(self.event_bus, 'handlers') else 0,
                        "processed_events": getattr(self.event_bus, 'processed_count', 0),
                        "failed_events": getattr(self.event_bus, 'failed_count', 0)
                    }
                }
                
            except Exception as e:
                logger.error(f"Error getting system overview: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.router.get("/health")
        async def health_status():
            """Get detailed health status"""
            try:
                health_data = await self.health_checker.check_system_health()
                return health_data
            except Exception as e:
                logger.error(f"Error getting health status: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.router.get("/health/{check_name}/history")
        async def health_history(check_name: str, hours: int = 24):
            """Get health check history"""
            try:
                history = await self.health_checker.get_health_history(check_name, hours)
                return {
                    "check_name": check_name,
                    "hours": hours,
                    "history": [
                        {
                            "timestamp": result.timestamp.isoformat(),
                            "state": result.state.value,
                            "response_time_ms": result.response_time_ms,
                            "message": result.message,
                            "error": result.error
                        }
                        for result in history
                    ]
                }
            except Exception as e:
                logger.error(f"Error getting health history: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.router.get("/metrics")
        async def system_metrics():
            """Get system metrics"""
            try:
                metrics_summary = await self.metrics_collector.get_metrics_summary()
                system_metrics = await self.metrics_collector.get_system_metrics()
                
                return {
                    "summary": metrics_summary,
                    "system": system_metrics,
                    "timestamp": datetime.utcnow().isoformat()
                }
            except Exception as e:
                logger.error(f"Error getting metrics: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.router.get("/metrics/{metric_name}")
        async def get_metric(metric_name: str):
            """Get specific metric data"""
            try:
                metric_series = await self.metrics_collector.get_metric(metric_name)
                if not metric_series:
                    raise HTTPException(status_code=404, detail=f"Metric {metric_name} not found")
                
                # Get recent values
                recent_values = list(metric_series.values)[-100:]  # Last 100 values
                
                return {
                    "name": metric_series.name,
                    "unit": metric_series.unit,
                    "type": metric_series.type,
                    "values": [
                        {
                            "timestamp": value.timestamp.isoformat(),
                            "value": value.value,
                            "labels": value.labels
                        }
                        for value in recent_values
                    ],
                    "statistics": {
                        "latest": metric_series.get_latest_value().value if metric_series.get_latest_value() else None,
                        "average_1h": metric_series.get_average(timedelta(hours=1)),
                        "max_1h": metric_series.get_max(timedelta(hours=1)),
                        "min_1h": metric_series.get_min(timedelta(hours=1))
                    }
                }
            except Exception as e:
                logger.error(f"Error getting metric {metric_name}: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.router.get("/plugins")
        async def list_plugins():
            """List all plugins with detailed information"""
            try:
                loaded_plugins = self.plugin_system.get_loaded_plugins()
                plugins_info = {}
                
                for plugin_name in loaded_plugins:
                    status = await self.plugin_system.get_plugin_status(plugin_name)
                    info = self.plugin_system.registry.get_plugin_info(plugin_name)
                    
                    plugins_info[plugin_name] = {
                        "name": plugin_name,
                        "state": status.get("state", "unknown"),
                        "info": {
                            "version": info.version if info else "unknown",
                            "description": info.description if info else "No description",
                            "dependencies": info.dependencies if info else [],
                            "author": getattr(info, "author", "unknown") if info else "unknown"
                        },
                        "health": status.get("health", {}),
                        "performance": status.get("performance", {}),
                        "last_updated": status.get("last_updated", "unknown")
                    }
                
                return {
                    "total_count": len(loaded_plugins),
                    "plugins": plugins_info
                }
            except Exception as e:
                logger.error(f"Error listing plugins: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.router.post("/plugins/{plugin_name}/reload")
        async def reload_plugin(plugin_name: str, background_tasks: BackgroundTasks):
            """Reload a specific plugin"""
            try:
                # Add reload task to background
                background_tasks.add_task(self._reload_plugin_task, plugin_name)
                
                return BaseResponse(
                    message=f"Plugin '{plugin_name}' reload initiated"
                )
            except Exception as e:
                logger.error(f"Error initiating plugin reload: {e}")
                return ErrorResponse(
                    message=f"Failed to reload plugin: {str(e)}",
                    error_code="PLUGIN_RELOAD_FAILED"
                )
        
        @self.router.post("/plugins/{plugin_name}/start")
        async def start_plugin(plugin_name: str):
            """Start a plugin"""
            try:
                await self.plugin_system.start_plugin(plugin_name)
                return BaseResponse(message=f"Plugin '{plugin_name}' started successfully")
            except Exception as e:
                logger.error(f"Error starting plugin: {e}")
                return ErrorResponse(
                    message=f"Failed to start plugin: {str(e)}",
                    error_code="PLUGIN_START_FAILED"
                )
        
        @self.router.post("/plugins/{plugin_name}/stop")
        async def stop_plugin(plugin_name: str):
            """Stop a plugin"""
            try:
                await self.plugin_system.stop_plugin(plugin_name)
                return BaseResponse(message=f"Plugin '{plugin_name}' stopped successfully")
            except Exception as e:
                logger.error(f"Error stopping plugin: {e}")
                return ErrorResponse(
                    message=f"Failed to stop plugin: {str(e)}",
                    error_code="PLUGIN_STOP_FAILED"
                )
        
        @self.router.get("/tenants")
        async def list_tenants():
            """List all tenants"""
            try:
                tenants = await self.tenant_manager.list_tenants()
                tenants_info = []
                
                for tenant in tenants:
                    resource_usage = await self.tenant_manager.get_resource_usage(tenant.tenant_id)
                    
                    tenants_info.append({
                        "tenant_id": tenant.tenant_id,
                        "name": tenant.name,
                        "status": tenant.status.value,
                        "created_at": tenant.created_at.isoformat(),
                        "domains_enabled": tenant.domains_enabled,
                        "resource_usage": resource_usage,
                        "resource_limits": tenant.resource_limits,
                        "contact_email": tenant.contact_email
                    })
                
                return {
                    "total_count": len(tenants),
                    "tenants": tenants_info
                }
            except Exception as e:
                logger.error(f"Error listing tenants: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.router.get("/tenants/{tenant_id}")
        async def get_tenant(tenant_id: str):
            """Get detailed tenant information"""
            try:
                tenant = await self.tenant_manager.get_tenant(tenant_id)
                if not tenant:
                    raise HTTPException(status_code=404, detail=f"Tenant {tenant_id} not found")
                
                resource_usage = await self.tenant_manager.get_resource_usage(tenant_id)
                
                return {
                    "tenant": tenant.to_dict(),
                    "resource_usage": resource_usage,
                    "resource_utilization": {
                        "users": (resource_usage.get("users", 0) / tenant.resource_limits.get("max_users", 1)) * 100,
                        "storage": (resource_usage.get("storage_mb", 0) / tenant.resource_limits.get("max_storage_mb", 1)) * 100,
                        "api_calls": (resource_usage.get("api_calls_hour", 0) / tenant.resource_limits.get("max_api_calls_per_hour", 1)) * 100
                    }
                }
            except Exception as e:
                logger.error(f"Error getting tenant {tenant_id}: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.router.post("/tenants/{tenant_id}/domains/{domain}/enable")
        async def enable_tenant_domain(tenant_id: str, domain: str):
            """Enable a domain for a tenant"""
            try:
                await self.tenant_manager.enable_domain(tenant_id, domain)
                return BaseResponse(message=f"Domain '{domain}' enabled for tenant '{tenant_id}'")
            except Exception as e:
                logger.error(f"Error enabling domain: {e}")
                return ErrorResponse(
                    message=f"Failed to enable domain: {str(e)}",
                    error_code="DOMAIN_ENABLE_FAILED"
                )
        
        @self.router.post("/tenants/{tenant_id}/domains/{domain}/disable")
        async def disable_tenant_domain(tenant_id: str, domain: str):
            """Disable a domain for a tenant"""
            try:
                await self.tenant_manager.disable_domain(tenant_id, domain)
                return BaseResponse(message=f"Domain '{domain}' disabled for tenant '{tenant_id}'")
            except Exception as e:
                logger.error(f"Error disabling domain: {e}")
                return ErrorResponse(
                    message=f"Failed to disable domain: {str(e)}",
                    error_code="DOMAIN_DISABLE_FAILED"
                )
        
        @self.router.get("/events/stats")
        async def event_stats():
            """Get event bus statistics"""
            try:
                return {
                    "handlers_count": len(self.event_bus.handlers) if hasattr(self.event_bus, 'handlers') else 0,
                    "subscriptions": getattr(self.event_bus, 'handlers', {}),
                    "processed_events": getattr(self.event_bus, 'processed_count', 0),
                    "failed_events": getattr(self.event_bus, 'failed_count', 0),
                    "timestamp": datetime.utcnow().isoformat()
                }
            except Exception as e:
                logger.error(f"Error getting event stats: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.router.post("/system/reload-config")
        async def reload_system_config():
            """Reload system configuration"""
            try:
                # In a real implementation, this would reload configuration
                # from files and update the system accordingly
                
                await self.event_bus.publish("system.config.reload", {
                    "timestamp": datetime.utcnow().isoformat(),
                    "initiated_by": "admin_dashboard"
                })
                
                return BaseResponse(message="System configuration reload initiated")
            except Exception as e:
                logger.error(f"Error reloading config: {e}")
                return ErrorResponse(
                    message=f"Failed to reload configuration: {str(e)}",
                    error_code="CONFIG_RELOAD_FAILED"
                )
        
        @self.router.post("/system/maintenance")
        async def toggle_maintenance_mode(enabled: bool = True):
            """Toggle system maintenance mode"""
            try:
                await self.event_bus.publish("system.maintenance.toggle", {
                    "enabled": enabled,
                    "timestamp": datetime.utcnow().isoformat()
                })
                
                status = "enabled" if enabled else "disabled"
                return BaseResponse(message=f"Maintenance mode {status}")
            except Exception as e:
                logger.error(f"Error toggling maintenance mode: {e}")
                return ErrorResponse(
                    message=f"Failed to toggle maintenance mode: {str(e)}",
                    error_code="MAINTENANCE_TOGGLE_FAILED"
                )
        
        @self.router.get("/logs/recent")
        async def get_recent_logs(level: str = "INFO", limit: int = 100):
            """Get recent system logs"""
            try:
                # In a real implementation, this would fetch logs from a log store
                # For demo purposes, return mock data
                
                return {
                    "level": level,
                    "limit": limit,
                    "logs": [
                        {
                            "timestamp": datetime.utcnow().isoformat(),
                            "level": "INFO",
                            "logger": "universal_platform.demo",
                            "message": "System is running normally",
                            "module": "admin_dashboard"
                        }
                    ],
                    "message": "Log retrieval functionality would be implemented with a proper logging backend"
                }
            except Exception as e:
                logger.error(f"Error getting logs: {e}")
                raise HTTPException(status_code=500, detail=str(e))
    
    async def _reload_plugin_task(self, plugin_name: str):
        """Background task for plugin reload"""
        try:
            await self.plugin_system.stop_plugin(plugin_name)
            await asyncio.sleep(1)  # Brief pause
            await self.plugin_system.reload_plugin(plugin_name)
            await self.plugin_system.start_plugin(plugin_name)
            
            await self.event_bus.publish("admin.plugin.reloaded", {
                "plugin_name": plugin_name,
                "timestamp": datetime.utcnow().isoformat(),
                "success": True
            })
            
        except Exception as e:
            logger.error(f"Failed to reload plugin {plugin_name}: {e}")
            
            await self.event_bus.publish("admin.plugin.reload_failed", {
                "plugin_name": plugin_name,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            })