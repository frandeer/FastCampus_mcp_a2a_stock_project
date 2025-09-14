"""
Comprehensive health checking system for monitoring system and component health
"""

import asyncio
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from enum import Enum

from ...core.di import injectable, singleton, inject
from ...core.events import EventBus
from ...core.plugins import PluginSystem
from .models import HealthStatus

logger = logging.getLogger(__name__)


class HealthState(str, Enum):
    """Health state enumeration"""
    HEALTHY = "healthy"
    DEGRADED = "degraded" 
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class HealthCheck:
    """Individual health check definition"""
    name: str
    check_func: Callable[[], Any]
    timeout_seconds: float = 30.0
    critical: bool = True
    description: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class HealthCheckResult:
    """Result of a health check"""
    name: str
    state: HealthState
    response_time_ms: float
    message: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    error: Optional[str] = None


@singleton
@injectable
class HealthChecker:
    """
    Comprehensive health checking system providing:
    - System-wide health monitoring
    - Component-specific health checks
    - Plugin health monitoring
    - Dependency health verification
    - Automatic health status aggregation
    - Health status history and trends
    - Alerting on health status changes
    """
    
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.health_checks: Dict[str, HealthCheck] = {}
        self.last_results: Dict[str, HealthCheckResult] = {}
        self.check_interval = 60  # seconds
        self.monitoring_task: Optional[asyncio.Task] = None
        self.health_history: Dict[str, List[HealthCheckResult]] = {}
        self.max_history_size = 100
        
        # Initialize built-in health checks
        self._initialize_builtin_checks()
    
    async def initialize(self):
        """Initialize health checker"""
        try:
            # Subscribe to relevant events
            await self.event_bus.subscribe("plugin.*", self._handle_plugin_event)
            await self.event_bus.subscribe("error.*", self._handle_error_event)
            
            # Start monitoring task
            self.monitoring_task = asyncio.create_task(self._monitoring_loop())
            
            logger.info("Health checker initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize health checker: {e}")
            raise
    
    async def shutdown(self):
        """Shutdown health checker"""
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Health checker shut down")
    
    def _initialize_builtin_checks(self):
        """Initialize built-in health checks"""
        # System health checks
        self.register_health_check(
            "system_memory",
            self._check_system_memory,
            timeout_seconds=5.0,
            critical=True,
            description="Check system memory usage"
        )
        
        self.register_health_check(
            "system_disk",
            self._check_system_disk,
            timeout_seconds=5.0,
            critical=True,
            description="Check system disk usage"
        )
        
        self.register_health_check(
            "system_cpu",
            self._check_system_cpu,
            timeout_seconds=10.0,
            critical=False,
            description="Check system CPU usage"
        )
        
        # Application health checks
        self.register_health_check(
            "event_bus",
            self._check_event_bus,
            timeout_seconds=5.0,
            critical=True,
            description="Check event bus connectivity"
        )
    
    def register_health_check(
        self,
        name: str,
        check_func: Callable,
        timeout_seconds: float = 30.0,
        critical: bool = True,
        description: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Register a new health check"""
        health_check = HealthCheck(
            name=name,
            check_func=check_func,
            timeout_seconds=timeout_seconds,
            critical=critical,
            description=description,
            metadata=metadata or {}
        )
        
        self.health_checks[name] = health_check
        logger.info(f"Registered health check: {name}")
    
    def unregister_health_check(self, name: str):
        """Unregister a health check"""
        if name in self.health_checks:
            del self.health_checks[name]
            if name in self.last_results:
                del self.last_results[name]
            if name in self.health_history:
                del self.health_history[name]
            logger.info(f"Unregistered health check: {name}")
    
    async def run_health_check(self, name: str) -> HealthCheckResult:
        """Run a specific health check"""
        if name not in self.health_checks:
            return HealthCheckResult(
                name=name,
                state=HealthState.UNKNOWN,
                response_time_ms=0,
                error="Health check not found"
            )
        
        health_check = self.health_checks[name]
        start_time = time.time()
        
        try:
            # Run the check with timeout
            if asyncio.iscoroutinefunction(health_check.check_func):
                check_result = await asyncio.wait_for(
                    health_check.check_func(),
                    timeout=health_check.timeout_seconds
                )
            else:
                check_result = await asyncio.wait_for(
                    asyncio.get_event_loop().run_in_executor(
                        None, health_check.check_func
                    ),
                    timeout=health_check.timeout_seconds
                )
            
            response_time = (time.time() - start_time) * 1000
            
            # Process the result
            if isinstance(check_result, dict):
                state = HealthState(check_result.get("state", HealthState.HEALTHY))
                message = check_result.get("message")
                details = check_result.get("details")
            elif isinstance(check_result, bool):
                state = HealthState.HEALTHY if check_result else HealthState.UNHEALTHY
                message = None
                details = None
            else:
                # Assume healthy if check completed without exception
                state = HealthState.HEALTHY
                message = str(check_result) if check_result else None
                details = None
            
            result = HealthCheckResult(
                name=name,
                state=state,
                response_time_ms=response_time,
                message=message,
                details=details
            )
            
        except asyncio.TimeoutError:
            response_time = health_check.timeout_seconds * 1000
            result = HealthCheckResult(
                name=name,
                state=HealthState.UNHEALTHY,
                response_time_ms=response_time,
                error=f"Health check timed out after {health_check.timeout_seconds}s"
            )
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            result = HealthCheckResult(
                name=name,
                state=HealthState.UNHEALTHY,
                response_time_ms=response_time,
                error=str(e)
            )
        
        # Store result
        self.last_results[name] = result
        self._add_to_history(name, result)
        
        # Publish health event
        await self.event_bus.publish("health.check.completed", {
            "check_name": name,
            "state": result.state.value,
            "response_time_ms": result.response_time_ms,
            "error": result.error
        })
        
        return result
    
    async def run_all_health_checks(self) -> Dict[str, HealthCheckResult]:
        """Run all registered health checks"""
        tasks = []
        check_names = []
        
        for name in self.health_checks.keys():
            tasks.append(self.run_health_check(name))
            check_names.append(name)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        health_results = {}
        for name, result in zip(check_names, results):
            if isinstance(result, Exception):
                health_results[name] = HealthCheckResult(
                    name=name,
                    state=HealthState.UNHEALTHY,
                    response_time_ms=0,
                    error=str(result)
                )
            else:
                health_results[name] = result
        
        return health_results
    
    async def check_system_health(self) -> Dict[str, Any]:
        """Get comprehensive system health status"""
        try:
            # Run all health checks
            check_results = await self.run_all_health_checks()
            
            # Determine overall health
            overall_healthy = True
            critical_failures = []
            warnings = []
            
            for name, result in check_results.items():
                health_check = self.health_checks[name]
                
                if result.state == HealthState.UNHEALTHY:
                    if health_check.critical:
                        overall_healthy = False
                        critical_failures.append(name)
                    else:
                        warnings.append(name)
                elif result.state == HealthState.DEGRADED:
                    warnings.append(name)
            
            # Calculate average response time
            response_times = [r.response_time_ms for r in check_results.values()]
            avg_response_time = sum(response_times) / len(response_times) if response_times else 0
            
            health_status = {
                "overall_healthy": overall_healthy,
                "state": HealthState.HEALTHY.value if overall_healthy else HealthState.UNHEALTHY.value,
                "timestamp": datetime.utcnow().isoformat(),
                "checks_total": len(check_results),
                "checks_healthy": len([r for r in check_results.values() if r.state == HealthState.HEALTHY]),
                "checks_degraded": len([r for r in check_results.values() if r.state == HealthState.DEGRADED]),
                "checks_unhealthy": len([r for r in check_results.values() if r.state == HealthState.UNHEALTHY]),
                "average_response_time_ms": avg_response_time,
                "critical_failures": critical_failures,
                "warnings": warnings,
                "details": {name: {
                    "state": result.state.value,
                    "response_time_ms": result.response_time_ms,
                    "message": result.message,
                    "error": result.error,
                    "critical": self.health_checks[name].critical
                } for name, result in check_results.items()}
            }
            
            # Publish overall health status
            await self.event_bus.publish("health.status.updated", health_status)
            
            return health_status
            
        except Exception as e:
            logger.error(f"Error checking system health: {e}")
            return {
                "overall_healthy": False,
                "state": HealthState.UNHEALTHY.value,
                "timestamp": datetime.utcnow().isoformat(),
                "error": str(e)
            }
    
    async def get_health_history(self, check_name: str, hours: int = 24) -> List[HealthCheckResult]:
        """Get health check history for a specific check"""
        if check_name not in self.health_history:
            return []
        
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        return [
            result for result in self.health_history[check_name]
            if result.timestamp >= cutoff
        ]
    
    def _add_to_history(self, check_name: str, result: HealthCheckResult):
        """Add result to health history"""
        if check_name not in self.health_history:
            self.health_history[check_name] = []
        
        self.health_history[check_name].append(result)
        
        # Trim history if too large
        if len(self.health_history[check_name]) > self.max_history_size:
            self.health_history[check_name] = self.health_history[check_name][-self.max_history_size:]
    
    async def _monitoring_loop(self):
        """Background health monitoring loop"""
        while True:
            try:
                await self.check_system_health()
                await asyncio.sleep(self.check_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in health monitoring loop: {e}")
                await asyncio.sleep(self.check_interval)
    
    # Built-in health checks
    
    async def _check_system_memory(self) -> Dict[str, Any]:
        """Check system memory usage"""
        try:
            import psutil
            memory = psutil.virtual_memory()
            
            if memory.percent > 90:
                return {
                    "state": HealthState.UNHEALTHY,
                    "message": f"Memory usage critically high: {memory.percent:.1f}%",
                    "details": {"usage_percent": memory.percent, "available_gb": memory.available / 1024**3}
                }
            elif memory.percent > 80:
                return {
                    "state": HealthState.DEGRADED,
                    "message": f"Memory usage high: {memory.percent:.1f}%",
                    "details": {"usage_percent": memory.percent, "available_gb": memory.available / 1024**3}
                }
            else:
                return {
                    "state": HealthState.HEALTHY,
                    "message": f"Memory usage normal: {memory.percent:.1f}%",
                    "details": {"usage_percent": memory.percent, "available_gb": memory.available / 1024**3}
                }
                
        except Exception as e:
            return {
                "state": HealthState.UNHEALTHY,
                "message": f"Failed to check memory: {str(e)}"
            }
    
    async def _check_system_disk(self) -> Dict[str, Any]:
        """Check system disk usage"""
        try:
            import psutil
            disk = psutil.disk_usage('/')
            usage_percent = (disk.used / disk.total) * 100
            
            if usage_percent > 95:
                return {
                    "state": HealthState.UNHEALTHY,
                    "message": f"Disk usage critically high: {usage_percent:.1f}%",
                    "details": {"usage_percent": usage_percent, "free_gb": disk.free / 1024**3}
                }
            elif usage_percent > 85:
                return {
                    "state": HealthState.DEGRADED,
                    "message": f"Disk usage high: {usage_percent:.1f}%",
                    "details": {"usage_percent": usage_percent, "free_gb": disk.free / 1024**3}
                }
            else:
                return {
                    "state": HealthState.HEALTHY,
                    "message": f"Disk usage normal: {usage_percent:.1f}%",
                    "details": {"usage_percent": usage_percent, "free_gb": disk.free / 1024**3}
                }
                
        except Exception as e:
            return {
                "state": HealthState.UNHEALTHY,
                "message": f"Failed to check disk: {str(e)}"
            }
    
    async def _check_system_cpu(self) -> Dict[str, Any]:
        """Check system CPU usage"""
        try:
            import psutil
            cpu_percent = psutil.cpu_percent(interval=1)
            
            if cpu_percent > 95:
                return {
                    "state": HealthState.DEGRADED,
                    "message": f"CPU usage very high: {cpu_percent:.1f}%",
                    "details": {"usage_percent": cpu_percent}
                }
            elif cpu_percent > 80:
                return {
                    "state": HealthState.DEGRADED,
                    "message": f"CPU usage high: {cpu_percent:.1f}%", 
                    "details": {"usage_percent": cpu_percent}
                }
            else:
                return {
                    "state": HealthState.HEALTHY,
                    "message": f"CPU usage normal: {cpu_percent:.1f}%",
                    "details": {"usage_percent": cpu_percent}
                }
                
        except Exception as e:
            return {
                "state": HealthState.UNHEALTHY,
                "message": f"Failed to check CPU: {str(e)}"
            }
    
    async def _check_event_bus(self) -> Dict[str, Any]:
        """Check event bus health"""
        try:
            # Simple connectivity test
            test_event = {"test": "health_check", "timestamp": datetime.utcnow().isoformat()}
            await self.event_bus.publish("health.test", test_event)
            
            return {
                "state": HealthState.HEALTHY,
                "message": "Event bus is operational",
                "details": {"handlers_count": len(self.event_bus.handlers) if hasattr(self.event_bus, 'handlers') else 0}
            }
            
        except Exception as e:
            return {
                "state": HealthState.UNHEALTHY,
                "message": f"Event bus error: {str(e)}"
            }
    
    async def _handle_plugin_event(self, event_type: str, event_data: Dict[str, Any]):
        """Handle plugin-related events for health monitoring"""
        try:
            plugin_name = event_data.get("plugin_name", "unknown")
            
            if event_type == "plugin.error":
                # Create a health check for this plugin if it doesn't exist
                check_name = f"plugin_{plugin_name}"
                if check_name not in self.health_checks:
                    self.register_health_check(
                        check_name,
                        lambda: self._check_plugin_health(plugin_name),
                        critical=False,
                        description=f"Health check for plugin {plugin_name}"
                    )
                
                # Record the error in health status
                result = HealthCheckResult(
                    name=check_name,
                    state=HealthState.UNHEALTHY,
                    response_time_ms=0,
                    error=event_data.get("error", "Unknown plugin error")
                )
                
                self.last_results[check_name] = result
                self._add_to_history(check_name, result)
                
        except Exception as e:
            logger.error(f"Error handling plugin event: {e}")
    
    async def _handle_error_event(self, event_type: str, event_data: Dict[str, Any]):
        """Handle error events for health monitoring"""
        try:
            severity = event_data.get("severity", "unknown")
            category = event_data.get("category", "system")
            
            # For critical errors, update system health
            if severity in ["critical", "error"]:
                check_name = f"error_{category}"
                
                result = HealthCheckResult(
                    name=check_name,
                    state=HealthState.DEGRADED if severity == "error" else HealthState.UNHEALTHY,
                    response_time_ms=0,
                    message=event_data.get("message", "System error detected"),
                    details={"error_type": event_type, "severity": severity}
                )
                
                self.last_results[check_name] = result
                self._add_to_history(check_name, result)
                
        except Exception as e:
            logger.error(f"Error handling error event: {e}")
    
    async def _check_plugin_health(self, plugin_name: str) -> Dict[str, Any]:
        """Check health of a specific plugin"""
        # This would be implemented based on plugin system capabilities
        # For now, return healthy status
        return {
            "state": HealthState.HEALTHY,
            "message": f"Plugin {plugin_name} is running"
        }