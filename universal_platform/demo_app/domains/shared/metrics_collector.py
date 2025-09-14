"""
Comprehensive metrics collection and monitoring system
"""

import asyncio
import time
import psutil
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from collections import defaultdict, deque
import threading

from ...core.di import injectable, singleton, inject
from ...core.events import EventBus
from ...core.plugins import PluginSystem
from .models import MetricData

logger = logging.getLogger(__name__)


@dataclass
class MetricValue:
    """Individual metric value with timestamp"""
    value: float
    timestamp: datetime = field(default_factory=datetime.utcnow)
    labels: Dict[str, str] = field(default_factory=dict)


@dataclass
class MetricSeries:
    """Time series of metric values"""
    name: str
    unit: Optional[str] = None
    type: str = "gauge"
    values: deque = field(default_factory=lambda: deque(maxlen=1000))
    
    def add_value(self, value: float, labels: Dict[str, str] = None):
        """Add a new value to the series"""
        self.values.append(MetricValue(
            value=value,
            labels=labels or {},
            timestamp=datetime.utcnow()
        ))
    
    def get_latest_value(self) -> Optional[MetricValue]:
        """Get the most recent value"""
        return self.values[-1] if self.values else None
    
    def get_average(self, duration: Optional[timedelta] = None) -> Optional[float]:
        """Get average value over specified duration"""
        if not self.values:
            return None
        
        if duration:
            cutoff = datetime.utcnow() - duration
            relevant_values = [v for v in self.values if v.timestamp >= cutoff]
        else:
            relevant_values = list(self.values)
        
        if not relevant_values:
            return None
        
        return sum(v.value for v in relevant_values) / len(relevant_values)
    
    def get_max(self, duration: Optional[timedelta] = None) -> Optional[float]:
        """Get maximum value over specified duration"""
        if not self.values:
            return None
        
        if duration:
            cutoff = datetime.utcnow() - duration
            relevant_values = [v for v in self.values if v.timestamp >= cutoff]
        else:
            relevant_values = list(self.values)
        
        if not relevant_values:
            return None
        
        return max(v.value for v in relevant_values)
    
    def get_min(self, duration: Optional[timedelta] = None) -> Optional[float]:
        """Get minimum value over specified duration"""
        if not self.values:
            return None
        
        if duration:
            cutoff = datetime.utcnow() - duration
            relevant_values = [v for v in self.values if v.timestamp >= cutoff]
        else:
            relevant_values = list(self.values)
        
        if not relevant_values:
            return None
        
        return min(v.value for v in relevant_values)


@singleton
@injectable
class MetricsCollector:
    """
    Comprehensive metrics collection system providing:
    - System performance metrics (CPU, memory, disk, network)
    - Application metrics (API calls, response times, errors)
    - Plugin metrics (performance, health, resource usage)
    - Event metrics (processing times, failure rates)
    - Custom business metrics
    - Real-time monitoring and alerting
    """
    
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.metrics: Dict[str, MetricSeries] = {}
        self.collectors: Dict[str, Callable] = {}
        self.collection_interval = 30  # seconds
        self.collection_task: Optional[asyncio.Task] = None
        self.start_time = datetime.utcnow()
        self.lock = threading.Lock()
        
        # Initialize built-in metrics
        self._initialize_metrics()
    
    async def initialize(self):
        """Initialize metrics collector"""
        try:
            # Subscribe to relevant events
            await self.event_bus.subscribe("api.*", self._handle_api_event)
            await self.event_bus.subscribe("plugin.*", self._handle_plugin_event)
            await self.event_bus.subscribe("error.*", self._handle_error_event)
            await self.event_bus.subscribe("*.created", self._handle_creation_event)
            await self.event_bus.subscribe("*.deleted", self._handle_deletion_event)
            
            # Start collection task
            self.collection_task = asyncio.create_task(self._collection_loop())
            
            logger.info("Metrics collector initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize metrics collector: {e}")
            raise
    
    async def shutdown(self):
        """Shutdown metrics collector"""
        if self.collection_task:
            self.collection_task.cancel()
            try:
                await self.collection_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Metrics collector shut down")
    
    def _initialize_metrics(self):
        """Initialize built-in metric series"""
        system_metrics = [
            ("system.cpu.usage_percent", "percent", "gauge"),
            ("system.memory.usage_percent", "percent", "gauge"),
            ("system.memory.used_mb", "MB", "gauge"),
            ("system.disk.usage_percent", "percent", "gauge"),
            ("system.network.bytes_sent", "bytes", "counter"),
            ("system.network.bytes_received", "bytes", "counter"),
        ]
        
        application_metrics = [
            ("app.uptime_seconds", "seconds", "gauge"),
            ("app.api.requests_total", "requests", "counter"),
            ("app.api.response_time_ms", "milliseconds", "histogram"),
            ("app.api.errors_total", "errors", "counter"),
            ("app.events.processed_total", "events", "counter"),
            ("app.events.failed_total", "events", "counter"),
        ]
        
        plugin_metrics = [
            ("plugins.loaded_count", "plugins", "gauge"),
            ("plugins.active_count", "plugins", "gauge"),
            ("plugins.memory_usage_mb", "MB", "gauge"),
            ("plugins.cpu_usage_percent", "percent", "gauge"),
        ]
        
        all_metrics = system_metrics + application_metrics + plugin_metrics
        
        with self.lock:
            for name, unit, metric_type in all_metrics:
                self.metrics[name] = MetricSeries(name=name, unit=unit, type=metric_type)
    
    def register_custom_collector(self, name: str, collector_func: Callable[[], Dict[str, float]]):
        """Register a custom metrics collector function"""
        self.collectors[name] = collector_func
        logger.info(f"Registered custom collector: {name}")
    
    def record_metric(self, name: str, value: float, labels: Dict[str, str] = None, unit: str = None, metric_type: str = "gauge"):
        """Record a metric value"""
        try:
            with self.lock:
                if name not in self.metrics:
                    self.metrics[name] = MetricSeries(name=name, unit=unit, type=metric_type)
                
                self.metrics[name].add_value(value, labels)
            
        except Exception as e:
            logger.error(f"Error recording metric {name}: {e}")
    
    def increment_counter(self, name: str, value: float = 1, labels: Dict[str, str] = None):
        """Increment a counter metric"""
        # For counters, we need to track the cumulative value
        with self.lock:
            if name not in self.metrics:
                self.metrics[name] = MetricSeries(name=name, type="counter")
            
            current = self.metrics[name].get_latest_value()
            new_value = (current.value if current else 0) + value
            self.metrics[name].add_value(new_value, labels)
    
    def record_histogram(self, name: str, value: float, labels: Dict[str, str] = None):
        """Record a histogram metric (like response time)"""
        self.record_metric(name, value, labels, metric_type="histogram")
    
    async def get_metric(self, name: str) -> Optional[MetricSeries]:
        """Get a specific metric series"""
        with self.lock:
            return self.metrics.get(name)
    
    async def get_all_metrics(self) -> Dict[str, MetricSeries]:
        """Get all metric series"""
        with self.lock:
            return self.metrics.copy()
    
    async def get_system_metrics(self) -> Dict[str, Any]:
        """Get current system metrics"""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            self.record_metric("system.cpu.usage_percent", cpu_percent)
            
            # Memory usage
            memory = psutil.virtual_memory()
            self.record_metric("system.memory.usage_percent", memory.percent)
            self.record_metric("system.memory.used_mb", memory.used / 1024 / 1024)
            
            # Disk usage
            disk = psutil.disk_usage('/')
            disk_percent = (disk.used / disk.total) * 100
            self.record_metric("system.disk.usage_percent", disk_percent)
            
            # Network I/O
            network = psutil.net_io_counters()
            self.record_metric("system.network.bytes_sent", network.bytes_sent)
            self.record_metric("system.network.bytes_received", network.bytes_recv)
            
            # Application uptime
            uptime = (datetime.utcnow() - self.start_time).total_seconds()
            self.record_metric("app.uptime_seconds", uptime)
            
            return {
                "cpu_percent": cpu_percent,
                "memory": {
                    "percent": memory.percent,
                    "used_mb": memory.used / 1024 / 1024,
                    "available_mb": memory.available / 1024 / 1024
                },
                "disk": {
                    "percent": disk_percent,
                    "used_gb": disk.used / 1024 / 1024 / 1024,
                    "free_gb": disk.free / 1024 / 1024 / 1024
                },
                "network": {
                    "bytes_sent": network.bytes_sent,
                    "bytes_received": network.bytes_recv
                },
                "uptime": uptime
            }
            
        except Exception as e:
            logger.error(f"Error collecting system metrics: {e}")
            return {}
    
    async def collect_plugin_metrics(self, plugin_system: PluginSystem):
        """Collect plugin-specific metrics"""
        try:
            loaded_plugins = plugin_system.get_loaded_plugins()
            active_plugins = []
            total_memory = 0
            
            for plugin_name in loaded_plugins:
                status = await plugin_system.get_plugin_status(plugin_name)
                if status.get("state") == "RUNNING":
                    active_plugins.append(plugin_name)
                
                # Estimate memory usage (simplified)
                memory_usage = status.get("memory_usage_mb", 0)
                total_memory += memory_usage
            
            self.record_metric("plugins.loaded_count", len(loaded_plugins))
            self.record_metric("plugins.active_count", len(active_plugins))
            self.record_metric("plugins.memory_usage_mb", total_memory)
            
        except Exception as e:
            logger.error(f"Error collecting plugin metrics: {e}")
    
    async def collect_event_metrics(self, event_bus: EventBus):
        """Collect event bus metrics"""
        try:
            # Get event statistics (if available)
            handlers_count = len(event_bus.handlers) if hasattr(event_bus, 'handlers') else 0
            processed_count = getattr(event_bus, 'processed_count', 0)
            failed_count = getattr(event_bus, 'failed_count', 0)
            
            self.record_metric("app.events.handlers_count", handlers_count)
            self.record_metric("app.events.processed_total", processed_count)
            self.record_metric("app.events.failed_total", failed_count)
            
        except Exception as e:
            logger.error(f"Error collecting event metrics: {e}")
    
    async def get_metrics_summary(self) -> Dict[str, Any]:
        """Get a summary of key metrics"""
        try:
            with self.lock:
                summary = {}
                
                # System metrics
                cpu_metric = self.metrics.get("system.cpu.usage_percent")
                memory_metric = self.metrics.get("system.memory.usage_percent")
                disk_metric = self.metrics.get("system.disk.usage_percent")
                
                if cpu_metric:
                    summary["cpu_usage_percent"] = cpu_metric.get_latest_value().value
                if memory_metric:
                    summary["memory_usage_percent"] = memory_metric.get_latest_value().value
                if disk_metric:
                    summary["disk_usage_percent"] = disk_metric.get_latest_value().value
                
                # Application metrics
                uptime_metric = self.metrics.get("app.uptime_seconds")
                if uptime_metric:
                    summary["uptime_seconds"] = uptime_metric.get_latest_value().value
                
                api_requests = self.metrics.get("app.api.requests_total")
                if api_requests:
                    summary["total_api_requests"] = api_requests.get_latest_value().value
                
                api_errors = self.metrics.get("app.api.errors_total")
                if api_errors:
                    summary["total_api_errors"] = api_errors.get_latest_value().value
                
                # Response time statistics
                response_time = self.metrics.get("app.api.response_time_ms")
                if response_time:
                    summary["avg_response_time_ms"] = response_time.get_average(timedelta(minutes=5))
                    summary["max_response_time_ms"] = response_time.get_max(timedelta(minutes=5))
                
                return summary
                
        except Exception as e:
            logger.error(f"Error generating metrics summary: {e}")
            return {}
    
    async def _collection_loop(self):
        """Background metrics collection loop"""
        while True:
            try:
                await self.get_system_metrics()
                
                # Run custom collectors
                for name, collector_func in self.collectors.items():
                    try:
                        custom_metrics = collector_func()
                        for metric_name, value in custom_metrics.items():
                            self.record_metric(f"custom.{name}.{metric_name}", value)
                    except Exception as e:
                        logger.error(f"Error in custom collector {name}: {e}")
                
                await asyncio.sleep(self.collection_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in metrics collection loop: {e}")
                await asyncio.sleep(self.collection_interval)
    
    async def _handle_api_event(self, event_type: str, event_data: Dict[str, Any]):
        """Handle API-related events"""
        try:
            if event_type == "api.request":
                self.increment_counter("app.api.requests_total")
                
                # Record response time if available
                response_time = event_data.get("response_time_ms")
                if response_time:
                    self.record_histogram("app.api.response_time_ms", response_time)
                
                # Record by endpoint
                endpoint = event_data.get("endpoint", "unknown")
                self.increment_counter("app.api.requests_by_endpoint", labels={"endpoint": endpoint})
                
            elif event_type == "api.error":
                self.increment_counter("app.api.errors_total")
                
                # Record by error type
                error_type = event_data.get("error_type", "unknown")
                self.increment_counter("app.api.errors_by_type", labels={"error_type": error_type})
                
        except Exception as e:
            logger.error(f"Error handling API event: {e}")
    
    async def _handle_plugin_event(self, event_type: str, event_data: Dict[str, Any]):
        """Handle plugin-related events"""
        try:
            plugin_name = event_data.get("plugin_name", "unknown")
            
            if event_type == "plugin.loaded":
                self.increment_counter("plugins.load_events", labels={"plugin": plugin_name, "event": "loaded"})
            elif event_type == "plugin.started":
                self.increment_counter("plugins.load_events", labels={"plugin": plugin_name, "event": "started"})
            elif event_type == "plugin.error":
                self.increment_counter("plugins.errors", labels={"plugin": plugin_name})
                
        except Exception as e:
            logger.error(f"Error handling plugin event: {e}")
    
    async def _handle_error_event(self, event_type: str, event_data: Dict[str, Any]):
        """Handle error events"""
        try:
            error_category = event_data.get("category", "unknown")
            severity = event_data.get("severity", "unknown")
            
            self.increment_counter("app.errors_total", labels={
                "category": error_category,
                "severity": severity
            })
            
        except Exception as e:
            logger.error(f"Error handling error event: {e}")
    
    async def _handle_creation_event(self, event_type: str, event_data: Dict[str, Any]):
        """Handle entity creation events"""
        try:
            entity_type = event_type.split('.')[0]  # e.g., "user.created" -> "user"
            
            self.increment_counter(f"entities.{entity_type}.created")
            self.increment_counter("entities.total_created")
            
        except Exception as e:
            logger.error(f"Error handling creation event: {e}")
    
    async def _handle_deletion_event(self, event_type: str, event_data: Dict[str, Any]):
        """Handle entity deletion events"""
        try:
            entity_type = event_type.split('.')[0]  # e.g., "user.deleted" -> "user"
            
            self.increment_counter(f"entities.{entity_type}.deleted")
            self.increment_counter("entities.total_deleted")
            
        except Exception as e:
            logger.error(f"Error handling deletion event: {e}")