"""
System Monitor Plugin Example

Demonstrates a monitor-type plugin that observes system metrics
with alerting, data collection, and health tracking capabilities.
"""

import asyncio
import logging
import psutil
import time
from collections import deque
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set

from ..interfaces import MonitorPlugin, PluginConfig, PluginHealth
from ..decorators import (
    plugin_metadata, config_schema, lifecycle_hook, requires_permission,
    monitor_performance, timeout, cache_result, log_calls,
    HookType, PermissionType
)


@plugin_metadata(
    name="system_monitor",
    version="1.3.0",
    description="Comprehensive system monitoring with alerting and data collection",
    author="Universal Platform Team",
    plugin_type="monitor",
    provides=["system_monitoring", "metrics_collection", "alerting"],
    requires=["system"],
    tags=["monitor", "system", "metrics", "alerts", "performance"],
    max_memory_mb=100,
    max_cpu_percent=5.0,
    network_access=False,
    file_system_access=True
)
@config_schema({
    'monitoring_interval': {'type': int, 'required': False, 'default': 30},  # seconds
    'data_retention_hours': {'type': int, 'required': False, 'default': 24},
    'alert_thresholds': {
        'type': dict,
        'required': False,
        'default': {
            'cpu_percent': 80.0,
            'memory_percent': 85.0,
            'disk_percent': 90.0,
            'load_average': 2.0,
            'temperature': 70.0
        }
    },
    'monitored_metrics': {
        'type': list,
        'required': False,
        'default': ['cpu', 'memory', 'disk', 'network', 'processes']
    },
    'enable_alerting': {'type': bool, 'required': False, 'default': True},
    'alert_cooldown_minutes': {'type': int, 'required': False, 'default': 15},
    'disk_paths': {
        'type': list,
        'required': False,
        'default': ['/']
    },
    'network_interfaces': {
        'type': list,
        'required': False,
        'default': []  # Empty means all interfaces
    }
})
class SystemMonitorPlugin(MonitorPlugin):
    """
    System monitoring plugin that tracks various system metrics and generates alerts.
    """
    
    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self._monitoring_task = None
        self._monitoring_targets: Set[str] = set()
        self._alert_thresholds: Dict[str, float] = {}
        self._alert_history: deque = deque(maxlen=1000)
        self._metric_history: Dict[str, deque] = {}
        self._last_alerts: Dict[str, datetime] = {}
        self._is_monitoring = False
        
        # Initialize metric storage
        self._current_metrics = {
            'timestamp': None,
            'cpu': {},
            'memory': {},
            'disk': {},
            'network': {},
            'processes': {}
        }
    
    @lifecycle_hook(HookType.BEFORE_INIT)
    async def _check_system_compatibility(self):
        """Check system compatibility before initialization."""
        self.logger.info("Checking system monitoring compatibility...")
        
        # Check if psutil can access system information
        try:
            psutil.cpu_percent()
            psutil.virtual_memory()
            self.logger.info("System monitoring compatibility confirmed")
        except Exception as e:
            self.logger.error(f"System monitoring compatibility issue: {e}")
    
    async def initialize(self, config: PluginConfig) -> None:
        """Initialize the system monitor plugin."""
        self.logger.info("Initializing system monitor plugin...")
        
        # Validate configuration
        if hasattr(self, 'validate_config'):
            self.validate_config(config)
        
        self._plugin_config = config
        
        # Initialize alert thresholds
        self._alert_thresholds = config.get('alert_thresholds', {
            'cpu_percent': 80.0,
            'memory_percent': 85.0,
            'disk_percent': 90.0,
            'load_average': 2.0,
            'temperature': 70.0
        })
        
        # Initialize metric history storage
        monitored_metrics = config.get('monitored_metrics', ['cpu', 'memory', 'disk'])
        retention_hours = config.get('data_retention_hours', 24)
        max_data_points = int((retention_hours * 3600) / config.get('monitoring_interval', 30))
        
        for metric in monitored_metrics:
            self._metric_history[metric] = deque(maxlen=max_data_points)
        
        self._is_initialized = True
        self.logger.info("System monitor plugin initialized successfully")
    
    @lifecycle_hook(HookType.AFTER_START)
    async def _start_monitoring_task(self):
        """Start the background monitoring task."""
        if not self._monitoring_task or self._monitoring_task.done():
            self._monitoring_task = asyncio.create_task(self._monitoring_loop())
            self.logger.info("Background monitoring task started")
    
    async def start(self) -> None:
        """Start the system monitor."""
        self.logger.info("Starting system monitor...")
        
        # Start monitoring all configured metrics by default
        monitored_metrics = self._plugin_config.get('monitored_metrics', ['cpu', 'memory', 'disk'])
        await self.start_monitoring(monitored_metrics)
        
        self._is_started = True
        self.logger.info("System monitor started successfully")
    
    @lifecycle_hook(HookType.BEFORE_STOP)
    async def _stop_monitoring_task(self):
        """Stop the background monitoring task."""
        if self._monitoring_task and not self._monitoring_task.done():
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
            self.logger.info("Background monitoring task stopped")
    
    async def stop(self) -> None:
        """Stop the system monitor."""
        self.logger.info("Stopping system monitor...")
        
        await self.stop_monitoring()
        
        self._is_started = False
        self.logger.info("System monitor stopped successfully")
    
    async def destroy(self) -> None:
        """Destroy the system monitor plugin."""
        self.logger.info("Destroying system monitor plugin...")
        
        # Ensure monitoring is stopped
        if self._is_monitoring:
            await self.stop_monitoring()
        
        # Clear all data
        self._metric_history.clear()
        self._alert_history.clear()
        self._last_alerts.clear()
        self._current_metrics.clear()
        
        self._is_initialized = False
        self.logger.info("System monitor plugin destroyed")
    
    @requires_permission(PermissionType.SYSTEM)
    async def start_monitoring(self, targets: List[str]) -> None:
        """
        Start monitoring specified targets.
        
        Args:
            targets: List of metrics to monitor ('cpu', 'memory', 'disk', etc.)
        """
        self.logger.info(f"Starting monitoring for targets: {targets}")
        
        # Validate targets
        valid_targets = {'cpu', 'memory', 'disk', 'network', 'processes', 'system'}
        invalid_targets = set(targets) - valid_targets
        
        if invalid_targets:
            self.logger.warning(f"Invalid monitoring targets ignored: {invalid_targets}")
        
        # Add valid targets
        self._monitoring_targets.update(set(targets) & valid_targets)
        
        # Start monitoring if not already running
        if not self._is_monitoring:
            self._is_monitoring = True
            
            # Start monitoring task if not already started in lifecycle hook
            if not self._monitoring_task or self._monitoring_task.done():
                self._monitoring_task = asyncio.create_task(self._monitoring_loop())
        
        self.logger.info(f"Monitoring active for targets: {self._monitoring_targets}")
    
    async def stop_monitoring(self) -> None:
        """Stop all monitoring activities."""
        self.logger.info("Stopping all monitoring activities...")
        
        self._is_monitoring = False
        self._monitoring_targets.clear()
        
        if self._monitoring_task and not self._monitoring_task.done():
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
            self._monitoring_task = None
        
        self.logger.info("All monitoring activities stopped")
    
    @cache_result(ttl=5.0)  # Cache for 5 seconds to avoid excessive system calls
    async def get_monitoring_data(self, target: str = None) -> Dict[str, Any]:
        """
        Get monitoring data for specified target or all targets.
        
        Args:
            target: Specific target to get data for (None for all)
            
        Returns:
            Dictionary containing monitoring data
        """
        if target:
            if target not in self._monitoring_targets:
                raise ValueError(f"Target '{target}' is not being monitored")
            
            return {
                'target': target,
                'current': self._current_metrics.get(target, {}),
                'history': list(self._metric_history.get(target, [])),
                'alerts': self._get_target_alerts(target)
            }
        else:
            # Return all monitoring data
            result = {
                'timestamp': self._current_metrics.get('timestamp'),
                'targets': list(self._monitoring_targets),
                'current_metrics': {},
                'history': {},
                'recent_alerts': list(self._alert_history)[-10:]  # Last 10 alerts
            }
            
            for tgt in self._monitoring_targets:
                result['current_metrics'][tgt] = self._current_metrics.get(tgt, {})
                result['history'][tgt] = list(self._metric_history.get(tgt, []))
            
            return result
    
    async def set_alert_threshold(self, metric: str, threshold: float) -> None:
        """
        Set alert threshold for a metric.
        
        Args:
            metric: Metric name (e.g., 'cpu_percent', 'memory_percent')
            threshold: Alert threshold value
        """
        self.logger.info(f"Setting alert threshold for {metric}: {threshold}")
        
        self._alert_thresholds[metric] = threshold
        
        # Update configuration
        if 'alert_thresholds' not in self._plugin_config.settings:
            self._plugin_config.settings['alert_thresholds'] = {}
        self._plugin_config.settings['alert_thresholds'][metric] = threshold
    
    @monitor_performance()
    async def health_check(self) -> PluginHealth:
        """Perform health check on the system monitor."""
        try:
            # Check if monitoring is active
            if not self._is_monitoring:
                return PluginHealth(
                    is_healthy=False,
                    score=0.5,
                    message="Monitoring is not active",
                    details={'monitoring_status': 'stopped'}
                )
            
            # Check monitoring task health
            if not self._monitoring_task or self._monitoring_task.done():
                return PluginHealth(
                    is_healthy=False,
                    score=0.3,
                    message="Monitoring task is not running",
                    details={'task_status': 'stopped'}
                )
            
            # Check if we're getting recent data
            last_update = self._current_metrics.get('timestamp')
            if last_update:
                time_since_update = (datetime.now() - datetime.fromisoformat(last_update)).total_seconds()
                if time_since_update > self._plugin_config.get('monitoring_interval', 30) * 2:
                    return PluginHealth(
                        is_healthy=False,
                        score=0.4,
                        message=f"No recent data (last update: {time_since_update:.1f}s ago)",
                        details={'last_update': last_update}
                    )
            
            # Check system health based on current metrics
            system_score = await self._calculate_system_health_score()
            
            return PluginHealth(
                is_healthy=True,
                score=system_score,
                message="System monitor is healthy" if system_score > 0.7 else "System monitor detecting issues",
                details={
                    'monitoring_targets': list(self._monitoring_targets),
                    'active_alerts': len(self._alert_history),
                    'system_health_score': system_score,
                    'last_update': last_update
                }
            )
            
        except Exception as e:
            return PluginHealth(
                is_healthy=False,
                score=0.0,
                message=f"Health check failed: {e}",
                details={'error': str(e)}
            )
    
    async def get_metrics(self) -> Dict[str, Any]:
        """Get system monitor metrics."""
        total_alerts = len(self._alert_history)
        recent_alerts = len([a for a in self._alert_history 
                           if datetime.fromisoformat(a['timestamp']) > 
                           datetime.now() - timedelta(hours=1)])
        
        return {
            'monitoring_targets_count': len(self._monitoring_targets),
            'monitoring_active': self._is_monitoring,
            'total_alerts': total_alerts,
            'recent_alerts_1h': recent_alerts,
            'alert_rate_per_hour': recent_alerts,
            'data_points_collected': sum(len(history) for history in self._metric_history.values()),
            'last_collection_timestamp': self._current_metrics.get('timestamp'),
            'configured_thresholds': len(self._alert_thresholds),
            'system_health_score': await self._calculate_system_health_score()
        }
    
    # Private helper methods
    
    async def _monitoring_loop(self) -> None:
        """Main monitoring loop."""
        self.logger.info("Starting monitoring loop")
        
        monitoring_interval = self._plugin_config.get('monitoring_interval', 30)
        
        try:
            while self._is_monitoring:
                try:
                    # Collect metrics for all monitored targets
                    await self._collect_metrics()
                    
                    # Check for alerts
                    if self._plugin_config.get('enable_alerting', True):
                        await self._check_alerts()
                    
                    # Wait for next collection
                    await asyncio.sleep(monitoring_interval)
                    
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    self.logger.error(f"Error in monitoring loop: {e}")
                    await asyncio.sleep(5)  # Short delay before retrying
                    
        except asyncio.CancelledError:
            pass
        finally:
            self.logger.info("Monitoring loop stopped")
    
    @timeout(10.0)
    async def _collect_metrics(self) -> None:
        """Collect system metrics."""
        timestamp = datetime.now().isoformat()
        self._current_metrics['timestamp'] = timestamp
        
        try:
            for target in self._monitoring_targets:
                if target == 'cpu':
                    await self._collect_cpu_metrics()
                elif target == 'memory':
                    await self._collect_memory_metrics()
                elif target == 'disk':
                    await self._collect_disk_metrics()
                elif target == 'network':
                    await self._collect_network_metrics()
                elif target == 'processes':
                    await self._collect_process_metrics()
                elif target == 'system':
                    await self._collect_system_metrics()
            
        except Exception as e:
            self.logger.error(f"Error collecting metrics: {e}")
    
    async def _collect_cpu_metrics(self) -> None:
        """Collect CPU metrics."""
        try:
            cpu_data = {
                'usage_percent': psutil.cpu_percent(interval=0.1),
                'usage_per_cpu': psutil.cpu_percent(interval=0.1, percpu=True),
                'load_average': psutil.getloadavg() if hasattr(psutil, 'getloadavg') else [0, 0, 0],
                'cpu_count': psutil.cpu_count(),
                'cpu_count_logical': psutil.cpu_count(logical=True)
            }
            
            self._current_metrics['cpu'] = cpu_data
            
            # Store in history
            if 'cpu' in self._metric_history:
                self._metric_history['cpu'].append({
                    'timestamp': self._current_metrics['timestamp'],
                    'data': cpu_data
                })
            
        except Exception as e:
            self.logger.error(f"Error collecting CPU metrics: {e}")
    
    async def _collect_memory_metrics(self) -> None:
        """Collect memory metrics."""
        try:
            memory = psutil.virtual_memory()
            swap = psutil.swap_memory()
            
            memory_data = {
                'total_bytes': memory.total,
                'available_bytes': memory.available,
                'used_bytes': memory.used,
                'usage_percent': memory.percent,
                'swap_total_bytes': swap.total,
                'swap_used_bytes': swap.used,
                'swap_usage_percent': swap.percent
            }
            
            self._current_metrics['memory'] = memory_data
            
            # Store in history
            if 'memory' in self._metric_history:
                self._metric_history['memory'].append({
                    'timestamp': self._current_metrics['timestamp'],
                    'data': memory_data
                })
            
        except Exception as e:
            self.logger.error(f"Error collecting memory metrics: {e}")
    
    async def _collect_disk_metrics(self) -> None:
        """Collect disk metrics."""
        try:
            disk_paths = self._plugin_config.get('disk_paths', ['/'])
            disk_data = {}
            
            for path in disk_paths:
                try:
                    usage = psutil.disk_usage(path)
                    disk_data[path] = {
                        'total_bytes': usage.total,
                        'used_bytes': usage.used,
                        'free_bytes': usage.free,
                        'usage_percent': (usage.used / usage.total) * 100 if usage.total > 0 else 0
                    }
                except Exception as e:
                    self.logger.warning(f"Error collecting disk metrics for {path}: {e}")
            
            # Get disk I/O statistics
            try:
                disk_io = psutil.disk_io_counters()
                if disk_io:
                    disk_data['io'] = {
                        'read_bytes': disk_io.read_bytes,
                        'write_bytes': disk_io.write_bytes,
                        'read_count': disk_io.read_count,
                        'write_count': disk_io.write_count
                    }
            except Exception as e:
                self.logger.warning(f"Error collecting disk I/O metrics: {e}")
            
            self._current_metrics['disk'] = disk_data
            
            # Store in history
            if 'disk' in self._metric_history:
                self._metric_history['disk'].append({
                    'timestamp': self._current_metrics['timestamp'],
                    'data': disk_data
                })
            
        except Exception as e:
            self.logger.error(f"Error collecting disk metrics: {e}")
    
    async def _collect_network_metrics(self) -> None:
        """Collect network metrics."""
        try:
            network_io = psutil.net_io_counters(pernic=True)
            network_data = {}
            
            interfaces = self._plugin_config.get('network_interfaces', [])
            if not interfaces:
                interfaces = list(network_io.keys())
            
            for interface in interfaces:
                if interface in network_io:
                    stats = network_io[interface]
                    network_data[interface] = {
                        'bytes_sent': stats.bytes_sent,
                        'bytes_recv': stats.bytes_recv,
                        'packets_sent': stats.packets_sent,
                        'packets_recv': stats.packets_recv,
                        'errors_in': stats.errin,
                        'errors_out': stats.errout,
                        'drop_in': stats.dropin,
                        'drop_out': stats.dropout
                    }
            
            self._current_metrics['network'] = network_data
            
            # Store in history
            if 'network' in self._metric_history:
                self._metric_history['network'].append({
                    'timestamp': self._current_metrics['timestamp'],
                    'data': network_data
                })
            
        except Exception as e:
            self.logger.error(f"Error collecting network metrics: {e}")
    
    async def _collect_process_metrics(self) -> None:
        """Collect process metrics."""
        try:
            process_count = len(psutil.pids())
            
            # Get top processes by CPU and memory
            processes = []
            for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
                try:
                    processes.append(proc.info)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            
            # Sort by CPU usage
            top_cpu = sorted(processes, key=lambda x: x['cpu_percent'] or 0, reverse=True)[:10]
            
            # Sort by memory usage
            top_memory = sorted(processes, key=lambda x: x['memory_percent'] or 0, reverse=True)[:10]
            
            process_data = {
                'total_count': process_count,
                'top_cpu_processes': top_cpu,
                'top_memory_processes': top_memory
            }
            
            self._current_metrics['processes'] = process_data
            
            # Store in history
            if 'processes' in self._metric_history:
                self._metric_history['processes'].append({
                    'timestamp': self._current_metrics['timestamp'],
                    'data': process_data
                })
            
        except Exception as e:
            self.logger.error(f"Error collecting process metrics: {e}")
    
    async def _collect_system_metrics(self) -> None:
        """Collect general system metrics."""
        try:
            boot_time = datetime.fromtimestamp(psutil.boot_time())
            uptime = datetime.now() - boot_time
            
            system_data = {
                'boot_time': boot_time.isoformat(),
                'uptime_seconds': uptime.total_seconds(),
                'users_count': len(psutil.users())
            }
            
            # Try to get temperature if available
            try:
                temps = psutil.sensors_temperatures()
                if temps:
                    temp_data = {}
                    for name, entries in temps.items():
                        temp_data[name] = [{'label': entry.label, 'current': entry.current} 
                                         for entry in entries]
                    system_data['temperatures'] = temp_data
            except Exception:
                pass  # Temperature monitoring not available
            
            self._current_metrics['system'] = system_data
            
            # Store in history
            if 'system' in self._metric_history:
                self._metric_history['system'].append({
                    'timestamp': self._current_metrics['timestamp'],
                    'data': system_data
                })
            
        except Exception as e:
            self.logger.error(f"Error collecting system metrics: {e}")
    
    async def _check_alerts(self) -> None:
        """Check for alert conditions."""
        try:
            alerts_generated = []
            
            # Check CPU alerts
            if 'cpu' in self._current_metrics:
                cpu_usage = self._current_metrics['cpu'].get('usage_percent', 0)
                if cpu_usage > self._alert_thresholds.get('cpu_percent', 80):
                    alert = await self._generate_alert(
                        'cpu_high',
                        f"High CPU usage: {cpu_usage:.1f}%",
                        'warning',
                        {'cpu_usage': cpu_usage}
                    )
                    if alert:
                        alerts_generated.append(alert)
            
            # Check memory alerts
            if 'memory' in self._current_metrics:
                memory_usage = self._current_metrics['memory'].get('usage_percent', 0)
                if memory_usage > self._alert_thresholds.get('memory_percent', 85):
                    alert = await self._generate_alert(
                        'memory_high',
                        f"High memory usage: {memory_usage:.1f}%",
                        'warning',
                        {'memory_usage': memory_usage}
                    )
                    if alert:
                        alerts_generated.append(alert)
            
            # Check disk alerts
            if 'disk' in self._current_metrics:
                for path, disk_info in self._current_metrics['disk'].items():
                    if path != 'io' and isinstance(disk_info, dict):
                        disk_usage = disk_info.get('usage_percent', 0)
                        if disk_usage > self._alert_thresholds.get('disk_percent', 90):
                            alert = await self._generate_alert(
                                f'disk_high_{path.replace("/", "_")}',
                                f"High disk usage on {path}: {disk_usage:.1f}%",
                                'warning',
                                {'path': path, 'disk_usage': disk_usage}
                            )
                            if alert:
                                alerts_generated.append(alert)
            
            if alerts_generated:
                self.logger.info(f"Generated {len(alerts_generated)} alerts")
            
        except Exception as e:
            self.logger.error(f"Error checking alerts: {e}")
    
    async def _generate_alert(
        self,
        alert_type: str,
        message: str,
        severity: str,
        data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Generate an alert if cooldown period has passed."""
        now = datetime.now()
        cooldown_minutes = self._plugin_config.get('alert_cooldown_minutes', 15)
        
        # Check cooldown
        if alert_type in self._last_alerts:
            time_since_last = now - self._last_alerts[alert_type]
            if time_since_last < timedelta(minutes=cooldown_minutes):
                return None  # Still in cooldown
        
        # Generate alert
        alert = {
            'type': alert_type,
            'message': message,
            'severity': severity,
            'timestamp': now.isoformat(),
            'data': data
        }
        
        # Store alert
        self._alert_history.append(alert)
        self._last_alerts[alert_type] = now
        
        self.logger.warning(f"ALERT: {message}")
        
        return alert
    
    def _get_target_alerts(self, target: str) -> List[Dict[str, Any]]:
        """Get recent alerts for a specific target."""
        target_alerts = []
        cutoff_time = datetime.now() - timedelta(hours=24)
        
        for alert in self._alert_history:
            alert_time = datetime.fromisoformat(alert['timestamp'])
            if alert_time > cutoff_time and target in alert['type']:
                target_alerts.append(alert)
        
        return target_alerts
    
    async def _calculate_system_health_score(self) -> float:
        """Calculate overall system health score."""
        try:
            scores = []
            
            # CPU health score
            if 'cpu' in self._current_metrics:
                cpu_usage = self._current_metrics['cpu'].get('usage_percent', 0)
                cpu_score = max(0, 1.0 - (cpu_usage / 100))
                scores.append(cpu_score)
            
            # Memory health score
            if 'memory' in self._current_metrics:
                memory_usage = self._current_metrics['memory'].get('usage_percent', 0)
                memory_score = max(0, 1.0 - (memory_usage / 100))
                scores.append(memory_score)
            
            # Disk health score (average of all disks)
            if 'disk' in self._current_metrics:
                disk_scores = []
                for path, disk_info in self._current_metrics['disk'].items():
                    if path != 'io' and isinstance(disk_info, dict):
                        disk_usage = disk_info.get('usage_percent', 0)
                        disk_scores.append(max(0, 1.0 - (disk_usage / 100)))
                
                if disk_scores:
                    scores.append(sum(disk_scores) / len(disk_scores))
            
            # Return average score or 1.0 if no metrics available
            return sum(scores) / len(scores) if scores else 1.0
            
        except Exception:
            return 0.5  # Default neutral score on error