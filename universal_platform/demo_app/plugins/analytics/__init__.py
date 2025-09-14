"""
Analytics Plugin

This plugin provides analytics and reporting capabilities across all domains
"""

import logging
from typing import Dict, Any, List
from datetime import datetime, timedelta

from ...core.plugins import PluginInterface, plugin_metadata, lifecycle_hook, HookType
from ...core.events import EventBus

logger = logging.getLogger(__name__)


@plugin_metadata(
    name="analytics_plugin",
    version="1.0.0",
    description="Cross-domain analytics and reporting plugin",
    author="Universal Platform Team",
    dependencies=[]
)
class AnalyticsPlugin(PluginInterface):
    """Analytics plugin for tracking metrics across all domains"""
    
    def __init__(self):
        self.event_bus = None
        self.analytics_data = {
            "events": [],
            "metrics": {},
            "reports": {}
        }
    
    @lifecycle_hook(HookType.INITIALIZE)
    async def initialize(self, context=None):
        """Initialize the analytics plugin"""
        try:
            self.event_bus = context.get("event_bus") if context else None
            
            if self.event_bus:
                # Subscribe to all events for analytics
                await self.event_bus.subscribe("*", self._track_event)
            
            logger.info("Analytics plugin initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize analytics plugin: {e}")
            raise
    
    @lifecycle_hook(HookType.START)
    async def start(self):
        """Start the analytics plugin"""
        try:
            # Start analytics collection
            logger.info("Analytics plugin started - collecting data across all domains")
            
        except Exception as e:
            logger.error(f"Failed to start analytics plugin: {e}")
            raise
    
    @lifecycle_hook(HookType.STOP)
    async def stop(self):
        """Stop the analytics plugin"""
        try:
            logger.info("Analytics plugin stopped")
            
        except Exception as e:
            logger.error(f"Error stopping analytics plugin: {e}")
    
    @lifecycle_hook(HookType.DESTROY)
    async def destroy(self):
        """Destroy the analytics plugin"""
        try:
            self.analytics_data.clear()
            logger.info("Analytics plugin destroyed")
            
        except Exception as e:
            logger.error(f"Error destroying analytics plugin: {e}")
    
    async def _track_event(self, event_type: str, event_data: Dict[str, Any]):
        """Track all system events for analytics"""
        try:
            # Store event data
            event_record = {
                "type": event_type,
                "data": event_data,
                "timestamp": datetime.utcnow().isoformat(),
                "domain": self._extract_domain(event_type)
            }
            
            self.analytics_data["events"].append(event_record)
            
            # Keep only last 1000 events to prevent memory issues
            if len(self.analytics_data["events"]) > 1000:
                self.analytics_data["events"] = self.analytics_data["events"][-1000:]
            
            # Update metrics
            self._update_metrics(event_type, event_data)
            
        except Exception as e:
            logger.error(f"Error tracking event: {e}")
    
    def _extract_domain(self, event_type: str) -> str:
        """Extract domain from event type"""
        if "." in event_type:
            return event_type.split(".")[0]
        return "system"
    
    def _update_metrics(self, event_type: str, event_data: Dict[str, Any]):
        """Update analytics metrics"""
        try:
            domain = self._extract_domain(event_type)
            
            if domain not in self.analytics_data["metrics"]:
                self.analytics_data["metrics"][domain] = {
                    "event_count": 0,
                    "events_by_type": {},
                    "last_activity": None
                }
            
            metrics = self.analytics_data["metrics"][domain]
            metrics["event_count"] += 1
            metrics["last_activity"] = datetime.utcnow().isoformat()
            
            if event_type not in metrics["events_by_type"]:
                metrics["events_by_type"][event_type] = 0
            metrics["events_by_type"][event_type] += 1
            
        except Exception as e:
            logger.error(f"Error updating metrics: {e}")
    
    async def get_analytics_report(self, domain: str = None, hours: int = 24) -> Dict[str, Any]:
        """Generate analytics report"""
        try:
            cutoff = datetime.utcnow() - timedelta(hours=hours)
            
            # Filter events by time and domain
            filtered_events = []
            for event in self.analytics_data["events"]:
                event_time = datetime.fromisoformat(event["timestamp"])
                if event_time >= cutoff:
                    if domain is None or event["domain"] == domain:
                        filtered_events.append(event)
            
            # Generate summary
            event_types = {}
            domains = {}
            
            for event in filtered_events:
                event_type = event["type"]
                event_domain = event["domain"]
                
                if event_type not in event_types:
                    event_types[event_type] = 0
                event_types[event_type] += 1
                
                if event_domain not in domains:
                    domains[event_domain] = 0
                domains[event_domain] += 1
            
            return {
                "report_generated": datetime.utcnow().isoformat(),
                "time_range_hours": hours,
                "domain_filter": domain,
                "summary": {
                    "total_events": len(filtered_events),
                    "event_types": len(event_types),
                    "active_domains": len(domains)
                },
                "events_by_type": event_types,
                "events_by_domain": domains,
                "top_event_types": sorted(event_types.items(), key=lambda x: x[1], reverse=True)[:10]
            }
            
        except Exception as e:
            logger.error(f"Error generating analytics report: {e}")
            return {"error": str(e)}


# Plugin instance for loading
plugin_instance = AnalyticsPlugin()