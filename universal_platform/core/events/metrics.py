"""
Event system metrics collection and monitoring.
"""

import asyncio
import logging
import time
import psutil
from typing import Any, Dict, List, Optional, DefaultDict
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import defaultdict, deque
import json


logger = logging.getLogger(__name__)


@dataclass
class MetricPoint:
    """Single metric measurement."""
    timestamp: datetime
    value: float
    labels: Dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "value": self.value,
            "labels": self.labels,
        }


@dataclass
class TimeSeries:
    """Time series data for a metric."""
    name: str
    points: deque = field(default_factory=lambda: deque(maxlen=1000))
    
    def add_point(self, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        """Add a data point."""
        point = MetricPoint(
            timestamp=datetime.utcnow(),
            value=value,
            labels=labels or {},
        )
        self.points.append(point)
    
    def get_latest(self) -> Optional[MetricPoint]:
        """Get latest point."""
        return self.points[-1] if self.points else None
    
    def get_average(self, duration_minutes: int = 5) -> float:
        """Get average value over duration."""
        cutoff = datetime.utcnow() - timedelta(minutes=duration_minutes)
        relevant_points = [
            p.value for p in self.points 
            if p.timestamp >= cutoff
        ]
        return sum(relevant_points) / len(relevant_points) if relevant_points else 0.0
    
    def get_rate(self, duration_minutes: int = 1) -> float:
        """Get rate per minute over duration."""
        cutoff = datetime.utcnow() - timedelta(minutes=duration_minutes)
        relevant_points = [
            p for p in self.points 
            if p.timestamp >= cutoff
        ]
        
        if len(relevant_points) < 2:
            return 0.0
        
        # Calculate rate based on value differences
        total_change = relevant_points[-1].value - relevant_points[0].value
        time_diff = (relevant_points[-1].timestamp - relevant_points[0].timestamp).total_seconds() / 60
        
        return total_change / time_diff if time_diff > 0 else 0.0


class EventMetrics:
    """Comprehensive event system metrics collector."""
    
    def __init__(self, retention_hours: int = 24):
        self.retention_hours = retention_hours
        
        # Time series metrics
        self.time_series: Dict[str, TimeSeries] = {}
        
        # Counters
        self.counters: DefaultDict[str, int] = defaultdict(int)
        
        # Histograms for latency tracking
        self.histograms: DefaultDict[str, List[float]] = defaultdict(list)
        
        # Event type metrics
        self.event_metrics: DefaultDict[str, Dict[str, Any]] = defaultdict(lambda: {
            "published": 0,
            "processed": 0,
            "failed": 0,
            "total_processing_time": 0.0,
            "min_processing_time": float('inf'),
            "max_processing_time": 0.0,
            "last_seen": None,
        })
        
        # Handler metrics
        self.handler_metrics: DefaultDict[str, Dict[str, Any]] = defaultdict(lambda: {
            "executions": 0,
            "successes": 0,
            "failures": 0,
            "total_execution_time": 0.0,
            "min_execution_time": float('inf'),
            "max_execution_time": 0.0,
            "last_executed": None,
            "error_types": defaultdict(int),
        })
        
        # System metrics
        self.system_metrics = {
            "cpu_usage": TimeSeries("cpu_usage"),
            "memory_usage": TimeSeries("memory_usage"),
            "disk_usage": TimeSeries("disk_usage"),
            "network_io": TimeSeries("network_io"),
        }
        
        # Background cleanup task
        self._cleanup_task: Optional[asyncio.Task] = None
        self._running = False
        
        logger.info("EventMetrics initialized")
    
    async def start(self) -> None:
        """Start metrics collection."""
        if self._running:
            return
        
        self._running = True
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("EventMetrics started")
    
    async def stop(self) -> None:
        """Stop metrics collection."""
        if not self._running:
            return
        
        self._running = False
        
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        logger.info("EventMetrics stopped")
    
    def record_event_published(self, event_type: str, processing_time_ms: float) -> None:
        """Record event publication."""
        self.counters["events_published_total"] += 1
        self.counters[f"events_published_{event_type}"] += 1
        
        # Update event metrics
        metrics = self.event_metrics[event_type]
        metrics["published"] += 1
        metrics["last_seen"] = datetime.utcnow()
        
        # Record in time series
        self._ensure_time_series("events_published_rate").add_point(
            1.0, {"event_type": event_type}
        )
        
        # Record processing time
        self.histograms[f"event_publish_duration_{event_type}"].append(processing_time_ms)
        
        logger.debug(f"Recorded event publication: {event_type}")
    
    def record_event_processed(
        self,
        event_type: str,
        processing_time_ms: float,
        handler_count: int,
    ) -> None:
        """Record event processing."""
        self.counters["events_processed_total"] += 1
        self.counters[f"events_processed_{event_type}"] += 1
        
        # Update event metrics
        metrics = self.event_metrics[event_type]
        metrics["processed"] += 1
        metrics["total_processing_time"] += processing_time_ms
        metrics["min_processing_time"] = min(
            metrics["min_processing_time"], processing_time_ms
        )
        metrics["max_processing_time"] = max(
            metrics["max_processing_time"], processing_time_ms
        )
        
        # Record in time series
        self._ensure_time_series("events_processed_rate").add_point(
            1.0, {"event_type": event_type}
        )
        
        self._ensure_time_series("event_processing_duration").add_point(
            processing_time_ms, {"event_type": event_type}
        )
        
        self._ensure_time_series("event_handler_count").add_point(
            handler_count, {"event_type": event_type}
        )
        
        # Record processing time histogram
        self.histograms[f"event_processing_duration_{event_type}"].append(processing_time_ms)
    
    def record_event_failed(self, event_type: str, error: str) -> None:
        """Record event processing failure."""
        self.counters["events_failed_total"] += 1
        self.counters[f"events_failed_{event_type}"] += 1
        
        # Update event metrics
        metrics = self.event_metrics[event_type]
        metrics["failed"] += 1
        
        # Record in time series
        self._ensure_time_series("events_failed_rate").add_point(
            1.0, {"event_type": event_type, "error": error}
        )
        
        logger.debug(f"Recorded event failure: {event_type} - {error}")
    
    def record_handler_success(self, handler_name: str, execution_time_ms: float = 0.0) -> None:
        """Record handler success."""
        self.counters["handler_executions_total"] += 1
        self.counters["handler_successes_total"] += 1
        
        # Update handler metrics
        metrics = self.handler_metrics[handler_name]
        metrics["executions"] += 1
        metrics["successes"] += 1
        metrics["last_executed"] = datetime.utcnow()
        
        if execution_time_ms > 0:
            metrics["total_execution_time"] += execution_time_ms
            metrics["min_execution_time"] = min(
                metrics["min_execution_time"], execution_time_ms
            )
            metrics["max_execution_time"] = max(
                metrics["max_execution_time"], execution_time_ms
            )
            
            # Record in time series
            self._ensure_time_series("handler_execution_duration").add_point(
                execution_time_ms, {"handler": handler_name}
            )
        
        # Record in time series
        self._ensure_time_series("handler_success_rate").add_point(
            1.0, {"handler": handler_name}
        )
    
    def record_handler_failed(self, handler_name: str, error: str) -> None:
        """Record handler failure."""
        self.counters["handler_executions_total"] += 1
        self.counters["handler_failures_total"] += 1
        
        # Update handler metrics
        metrics = self.handler_metrics[handler_name]
        metrics["executions"] += 1
        metrics["failures"] += 1
        metrics["last_executed"] = datetime.utcnow()
        metrics["error_types"][error] += 1
        
        # Record in time series
        self._ensure_time_series("handler_failure_rate").add_point(
            1.0, {"handler": handler_name, "error": error}
        )
        
        logger.debug(f"Recorded handler failure: {handler_name} - {error}")
    
    async def collect_system_metrics(self) -> None:
        """Collect system performance metrics."""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            self.system_metrics["cpu_usage"].add_point(cpu_percent)
            
            # Memory usage
            memory = psutil.virtual_memory()
            self.system_metrics["memory_usage"].add_point(memory.percent)
            
            # Disk usage
            disk = psutil.disk_usage('/')
            disk_percent = (disk.used / disk.total) * 100
            self.system_metrics["disk_usage"].add_point(disk_percent)
            
            # Network I/O
            net_io = psutil.net_io_counters()
            total_bytes = net_io.bytes_sent + net_io.bytes_recv
            self.system_metrics["network_io"].add_point(total_bytes)
            
            logger.debug("Collected system metrics")
            
        except Exception as e:
            logger.error(f"Failed to collect system metrics: {e}")
    
    def increment_counter(self, name: str, value: int = 1, labels: Optional[Dict[str, str]] = None) -> None:
        """Increment a counter metric."""
        counter_key = name
        if labels:
            label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
            counter_key = f"{name}_{label_str}"
        
        self.counters[counter_key] += value
    
    def record_histogram(self, name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        """Record a histogram value."""
        histogram_key = name
        if labels:
            label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
            histogram_key = f"{name}_{label_str}"
        
        self.histograms[histogram_key].append(value)
        
        # Limit histogram size
        if len(self.histograms[histogram_key]) > 1000:
            self.histograms[histogram_key] = self.histograms[histogram_key][-1000:]
    
    def record_gauge(self, name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        """Record a gauge value."""
        self._ensure_time_series(name).add_point(value, labels)
    
    def _ensure_time_series(self, name: str) -> TimeSeries:
        """Ensure time series exists."""
        if name not in self.time_series:
            self.time_series[name] = TimeSeries(name)
        return self.time_series[name]
    
    def get_counter(self, name: str) -> int:
        """Get counter value."""
        return self.counters.get(name, 0)
    
    def get_histogram_stats(self, name: str) -> Dict[str, float]:
        """Get histogram statistics."""
        values = self.histograms.get(name, [])
        if not values:
            return {"count": 0, "min": 0, "max": 0, "avg": 0, "p50": 0, "p95": 0, "p99": 0}
        
        sorted_values = sorted(values)
        count = len(sorted_values)
        
        def percentile(p: float) -> float:
            idx = int(p * count)
            return sorted_values[min(idx, count - 1)]
        
        return {
            "count": count,
            "min": min(values),
            "max": max(values),
            "avg": sum(values) / count,
            "p50": percentile(0.5),
            "p95": percentile(0.95),
            "p99": percentile(0.99),
        }
    
    def get_gauge_latest(self, name: str) -> Optional[float]:
        """Get latest gauge value."""
        ts = self.time_series.get(name)
        if ts:
            latest = ts.get_latest()
            return latest.value if latest else None
        return None
    
    def get_event_type_metrics(self, event_type: str) -> Dict[str, Any]:
        """Get metrics for specific event type."""
        metrics = self.event_metrics[event_type].copy()
        
        # Calculate derived metrics
        if metrics["processed"] > 0:
            metrics["avg_processing_time"] = (
                metrics["total_processing_time"] / metrics["processed"]
            )
        else:
            metrics["avg_processing_time"] = 0.0
        
        # Calculate success rate
        total_attempts = metrics["processed"] + metrics["failed"]
        if total_attempts > 0:
            metrics["success_rate"] = metrics["processed"] / total_attempts
        else:
            metrics["success_rate"] = 0.0
        
        # Format timestamps
        if metrics["last_seen"]:
            metrics["last_seen"] = metrics["last_seen"].isoformat()
        
        return metrics
    
    def get_handler_metrics(self, handler_name: str) -> Dict[str, Any]:
        """Get metrics for specific handler."""
        metrics = self.handler_metrics[handler_name].copy()
        
        # Calculate derived metrics
        if metrics["executions"] > 0:
            metrics["success_rate"] = metrics["successes"] / metrics["executions"]
            metrics["failure_rate"] = metrics["failures"] / metrics["executions"]
            metrics["avg_execution_time"] = (
                metrics["total_execution_time"] / metrics["executions"]
            )
        else:
            metrics["success_rate"] = 0.0
            metrics["failure_rate"] = 0.0
            metrics["avg_execution_time"] = 0.0
        
        # Format timestamps
        if metrics["last_executed"]:
            metrics["last_executed"] = metrics["last_executed"].isoformat()
        
        # Convert error types to regular dict
        metrics["error_types"] = dict(metrics["error_types"])
        
        return metrics
    
    def get_summary(self) -> Dict[str, Any]:
        """Get comprehensive metrics summary."""
        # Calculate total events per second
        events_published_ts = self.time_series.get("events_published_rate")
        events_processed_ts = self.time_series.get("events_processed_rate")
        
        publish_rate = events_published_ts.get_rate() if events_published_ts else 0.0
        process_rate = events_processed_ts.get_rate() if events_processed_ts else 0.0
        
        # Get top event types by volume
        top_event_types = sorted(
            self.event_metrics.items(),
            key=lambda x: x[1]["published"],
            reverse=True
        )[:10]
        
        # Get handler performance
        top_handlers = sorted(
            self.handler_metrics.items(),
            key=lambda x: x[1]["executions"],
            reverse=True
        )[:10]
        
        # System metrics
        system_status = {}
        for name, ts in self.system_metrics.items():
            latest = ts.get_latest()
            if latest:
                system_status[name] = {
                    "current": latest.value,
                    "avg_5min": ts.get_average(5),
                }
        
        return {
            "overview": {
                "events_published_total": self.counters["events_published_total"],
                "events_processed_total": self.counters["events_processed_total"],
                "events_failed_total": self.counters["events_failed_total"],
                "handler_executions_total": self.counters["handler_executions_total"],
                "handler_successes_total": self.counters["handler_successes_total"],
                "handler_failures_total": self.counters["handler_failures_total"],
                "publish_rate_per_minute": publish_rate,
                "process_rate_per_minute": process_rate,
            },
            "top_event_types": [
                {
                    "event_type": event_type,
                    "published": metrics["published"],
                    "processed": metrics["processed"],
                    "failed": metrics["failed"],
                    "success_rate": (
                        metrics["processed"] / (metrics["processed"] + metrics["failed"])
                        if (metrics["processed"] + metrics["failed"]) > 0 else 0.0
                    ),
                }
                for event_type, metrics in top_event_types
            ],
            "top_handlers": [
                {
                    "handler": handler_name,
                    "executions": metrics["executions"],
                    "successes": metrics["successes"],
                    "failures": metrics["failures"],
                    "success_rate": (
                        metrics["successes"] / metrics["executions"]
                        if metrics["executions"] > 0 else 0.0
                    ),
                }
                for handler_name, metrics in top_handlers
            ],
            "system": system_status,
            "timestamp": datetime.utcnow().isoformat(),
        }
    
    def export_prometheus(self) -> str:
        """Export metrics in Prometheus format."""
        lines = []
        
        # Counters
        for name, value in self.counters.items():
            lines.append(f"# TYPE {name} counter")
            lines.append(f"{name} {value}")
        
        # Histograms
        for name, values in self.histograms.items():
            if values:
                stats = self.get_histogram_stats(name)
                lines.append(f"# TYPE {name} histogram")
                lines.append(f"{name}_count {stats['count']}")
                lines.append(f"{name}_sum {sum(values)}")
                lines.append(f"{name}_bucket{{le=\"0.1\"}} {sum(1 for v in values if v <= 0.1)}")
                lines.append(f"{name}_bucket{{le=\"1\"}} {sum(1 for v in values if v <= 1)}")
                lines.append(f"{name}_bucket{{le=\"10\"}} {sum(1 for v in values if v <= 10)}")
                lines.append(f"{name}_bucket{{le=\"100\"}} {sum(1 for v in values if v <= 100)}")
                lines.append(f"{name}_bucket{{le=\"+Inf\"}} {len(values)}")
        
        # Gauges from time series
        for name, ts in self.time_series.items():
            latest = ts.get_latest()
            if latest:
                lines.append(f"# TYPE {name} gauge")
                label_str = ",".join(f'{k}="{v}"' for k, v in latest.labels.items())
                if label_str:
                    lines.append(f"{name}{{{label_str}}} {latest.value}")
                else:
                    lines.append(f"{name} {latest.value}")
        
        return "\n".join(lines)
    
    async def _cleanup_loop(self) -> None:
        """Background cleanup of old metrics."""
        while self._running:
            try:
                await asyncio.sleep(3600)  # Run every hour
                await self._cleanup_old_data()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Metrics cleanup error: {e}")
    
    async def _cleanup_old_data(self) -> None:
        """Clean up old metric data."""
        cutoff_time = datetime.utcnow() - timedelta(hours=self.retention_hours)
        
        # Clean up time series
        for ts in self.time_series.values():
            original_count = len(ts.points)
            ts.points = deque(
                (p for p in ts.points if p.timestamp >= cutoff_time),
                maxlen=ts.points.maxlen
            )
            cleaned = original_count - len(ts.points)
            if cleaned > 0:
                logger.debug(f"Cleaned {cleaned} old points from {ts.name}")
        
        # Clean up histograms (keep only recent data)
        for name, values in self.histograms.items():
            if len(values) > 1000:
                self.histograms[name] = values[-1000:]
        
        logger.info("Completed metrics cleanup")