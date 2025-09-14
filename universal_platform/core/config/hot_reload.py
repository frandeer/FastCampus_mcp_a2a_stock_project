"""
Runtime configuration changes and notifications system.
"""

import asyncio
import weakref
from typing import Dict, Any, Optional, List, Callable, Set, Union
from dataclasses import dataclass
from enum import Enum
from datetime import datetime, timezone
import threading
import queue
import logging
from pathlib import Path
import json
import difflib

logger = logging.getLogger(__name__)


class ChangeType(Enum):
    """Types of configuration changes."""
    ADDED = "added"
    MODIFIED = "modified"
    DELETED = "deleted"
    PROVIDER_ADDED = "provider_added"
    PROVIDER_REMOVED = "provider_removed"
    VALIDATION_ERROR = "validation_error"


@dataclass
class ConfigChange:
    """Represents a configuration change."""
    change_type: ChangeType
    path: str
    old_value: Any = None
    new_value: Any = None
    timestamp: datetime = None
    provider_name: str = None
    validation_errors: List[str] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc)


class ChangeEvent:
    """Configuration change event."""
    
    def __init__(self, changes: List[ConfigChange], full_config: Dict[str, Any]):
        self.changes = changes
        self.full_config = full_config
        self.timestamp = datetime.now(timezone.utc)
        
    def has_changes_for_path(self, path: str) -> bool:
        """Check if there are changes for a specific path or its children."""
        for change in self.changes:
            if change.path == path or change.path.startswith(f"{path}."):
                return True
        return False
        
    def get_changes_for_path(self, path: str) -> List[ConfigChange]:
        """Get changes for a specific path or its children."""
        return [
            change for change in self.changes
            if change.path == path or change.path.startswith(f"{path}.")
        ]


class ConfigWatcher:
    """Watches for configuration changes and notifies listeners."""
    
    def __init__(self):
        self.listeners: List[Callable[[ChangeEvent], None]] = []
        self.path_listeners: Dict[str, List[Callable[[ChangeEvent], None]]] = {}
        self.change_history: List[ChangeEvent] = []
        self.max_history = 100
        self._lock = asyncio.Lock()
        
    def add_listener(self, callback: Callable[[ChangeEvent], None], 
                    path: str = None) -> None:
        """Add a change listener."""
        if path:
            if path not in self.path_listeners:
                self.path_listeners[path] = []
            self.path_listeners[path].append(callback)
        else:
            self.listeners.append(callback)
            
    def remove_listener(self, callback: Callable[[ChangeEvent], None], 
                       path: str = None) -> None:
        """Remove a change listener."""
        try:
            if path:
                if path in self.path_listeners:
                    self.path_listeners[path].remove(callback)
                    if not self.path_listeners[path]:
                        del self.path_listeners[path]
            else:
                self.listeners.remove(callback)
        except ValueError:
            pass  # Listener not found
            
    async def notify_change(self, event: ChangeEvent) -> None:
        """Notify all listeners of configuration changes."""
        async with self._lock:
            # Add to history
            self.change_history.append(event)
            if len(self.change_history) > self.max_history:
                self.change_history = self.change_history[-self.max_history:]
                
            # Notify global listeners
            for listener in self.listeners:
                try:
                    if asyncio.iscoroutinefunction(listener):
                        await listener(event)
                    else:
                        listener(event)
                except Exception as e:
                    logger.error(f"Error in change listener: {e}")
                    
            # Notify path-specific listeners
            for path, path_listeners in self.path_listeners.items():
                if event.has_changes_for_path(path):
                    for listener in path_listeners:
                        try:
                            if asyncio.iscoroutinefunction(listener):
                                await listener(event)
                            else:
                                listener(event)
                        except Exception as e:
                            logger.error(f"Error in path listener for {path}: {e}")
                            
    def get_change_history(self, limit: int = None) -> List[ChangeEvent]:
        """Get configuration change history."""
        if limit:
            return self.change_history[-limit:]
        return self.change_history.copy()


class HotReloadManager:
    """Manages hot reloading of configuration."""
    
    def __init__(self, watcher: ConfigWatcher = None):
        self.watcher = watcher or ConfigWatcher()
        self.reload_tasks: Set[asyncio.Task] = set()
        self.reload_callbacks: List[Callable[[Dict[str, Any]], None]] = []
        self.validation_callbacks: List[Callable[[Dict[str, Any]], List[str]]] = []
        self.rollback_history: List[Dict[str, Any]] = []
        self.max_rollback_history = 10
        self.reload_enabled = True
        self._reload_lock = asyncio.Lock()
        
    def add_reload_callback(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Add a callback to be executed when configuration is reloaded."""
        self.reload_callbacks.append(callback)
        
    def remove_reload_callback(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Remove a reload callback."""
        try:
            self.reload_callbacks.remove(callback)
        except ValueError:
            pass
            
    def add_validation_callback(self, callback: Callable[[Dict[str, Any]], List[str]]) -> None:
        """Add a validation callback."""
        self.validation_callbacks.append(callback)
        
    def enable_reload(self) -> None:
        """Enable configuration hot reloading."""
        self.reload_enabled = True
        
    def disable_reload(self) -> None:
        """Disable configuration hot reloading."""
        self.reload_enabled = False
        
    async def reload_config(self, new_config: Dict[str, Any], 
                           old_config: Dict[str, Any] = None,
                           provider_name: str = None) -> bool:
        """Reload configuration with validation and rollback support."""
        if not self.reload_enabled:
            logger.info("Configuration reload is disabled")
            return False
            
        async with self._reload_lock:
            try:
                # Validate new configuration
                validation_errors = []
                for validator in self.validation_callbacks:
                    try:
                        errors = validator(new_config)
                        if errors:
                            validation_errors.extend(errors)
                    except Exception as e:
                        validation_errors.append(f"Validation error: {e}")
                        
                if validation_errors:
                    logger.error(f"Configuration validation failed: {validation_errors}")
                    # Notify about validation errors
                    changes = [ConfigChange(
                        change_type=ChangeType.VALIDATION_ERROR,
                        path="",
                        validation_errors=validation_errors,
                        provider_name=provider_name
                    )]
                    await self.watcher.notify_change(ChangeEvent(changes, new_config))
                    return False
                    
                # Store current config for rollback
                if old_config:
                    self.rollback_history.append(old_config.copy())
                    if len(self.rollback_history) > self.max_rollback_history:
                        self.rollback_history = self.rollback_history[-self.max_rollback_history:]
                        
                # Calculate changes
                changes = self._calculate_changes(old_config or {}, new_config, provider_name)
                
                # Execute reload callbacks
                for callback in self.reload_callbacks:
                    try:
                        if asyncio.iscoroutinefunction(callback):
                            await callback(new_config)
                        else:
                            callback(new_config)
                    except Exception as e:
                        logger.error(f"Error in reload callback: {e}")
                        
                # Notify watchers
                if changes:
                    event = ChangeEvent(changes, new_config)
                    await self.watcher.notify_change(event)
                    
                logger.info(f"Configuration reloaded successfully with {len(changes)} changes")
                return True
                
            except Exception as e:
                logger.error(f"Failed to reload configuration: {e}")
                return False
                
    def _calculate_changes(self, old_config: Dict[str, Any], 
                          new_config: Dict[str, Any],
                          provider_name: str = None) -> List[ConfigChange]:
        """Calculate differences between old and new configuration."""
        changes = []
        
        def compare_dicts(old_dict: Dict[str, Any], new_dict: Dict[str, Any], 
                         path: str = "") -> None:
            # Check for added and modified keys
            for key, new_value in new_dict.items():
                current_path = f"{path}.{key}" if path else key
                
                if key not in old_dict:
                    changes.append(ConfigChange(
                        change_type=ChangeType.ADDED,
                        path=current_path,
                        old_value=None,
                        new_value=new_value,
                        provider_name=provider_name
                    ))
                elif old_dict[key] != new_value:
                    if isinstance(old_dict[key], dict) and isinstance(new_value, dict):
                        compare_dicts(old_dict[key], new_value, current_path)
                    else:
                        changes.append(ConfigChange(
                            change_type=ChangeType.MODIFIED,
                            path=current_path,
                            old_value=old_dict[key],
                            new_value=new_value,
                            provider_name=provider_name
                        ))
                        
            # Check for deleted keys
            for key, old_value in old_dict.items():
                current_path = f"{path}.{key}" if path else key
                
                if key not in new_dict:
                    changes.append(ConfigChange(
                        change_type=ChangeType.DELETED,
                        path=current_path,
                        old_value=old_value,
                        new_value=None,
                        provider_name=provider_name
                    ))
                    
        compare_dicts(old_config, new_config)
        return changes
        
    async def rollback_config(self, steps: int = 1) -> Optional[Dict[str, Any]]:
        """Rollback configuration to a previous state."""
        if not self.rollback_history:
            logger.warning("No configuration history available for rollback")
            return None
            
        if steps > len(self.rollback_history):
            steps = len(self.rollback_history)
            
        # Get the configuration to rollback to
        rollback_config = self.rollback_history[-(steps)]
        
        # Remove rolled back configurations from history
        self.rollback_history = self.rollback_history[:-steps]
        
        logger.info(f"Rolling back configuration {steps} steps")
        return rollback_config
        
    def get_rollback_history(self) -> List[Dict[str, Any]]:
        """Get configuration rollback history."""
        return self.rollback_history.copy()


class PerformanceMonitor:
    """Monitors configuration reload performance."""
    
    def __init__(self):
        self.reload_times: List[float] = []
        self.max_samples = 100
        
    def record_reload_time(self, reload_time: float) -> None:
        """Record a configuration reload time."""
        self.reload_times.append(reload_time)
        if len(self.reload_times) > self.max_samples:
            self.reload_times = self.reload_times[-self.max_samples:]
            
    def get_average_reload_time(self) -> float:
        """Get average reload time."""
        if not self.reload_times:
            return 0.0
        return sum(self.reload_times) / len(self.reload_times)
        
    def get_max_reload_time(self) -> float:
        """Get maximum reload time."""
        if not self.reload_times:
            return 0.0
        return max(self.reload_times)
        
    def get_reload_stats(self) -> Dict[str, Any]:
        """Get reload performance statistics."""
        if not self.reload_times:
            return {
                "count": 0,
                "average": 0.0,
                "min": 0.0,
                "max": 0.0
            }
            
        return {
            "count": len(self.reload_times),
            "average": self.get_average_reload_time(),
            "min": min(self.reload_times),
            "max": max(self.reload_times)
        }


class ChangeLogger:
    """Logs configuration changes for audit purposes."""
    
    def __init__(self, log_file: Union[str, Path] = None):
        self.log_file = Path(log_file) if log_file else None
        self.change_log: List[Dict[str, Any]] = []
        
    async def log_change(self, event: ChangeEvent) -> None:
        """Log a configuration change event."""
        log_entry = {
            "timestamp": event.timestamp.isoformat(),
            "changes": [
                {
                    "type": change.change_type.value,
                    "path": change.path,
                    "old_value": change.old_value,
                    "new_value": change.new_value,
                    "provider": change.provider_name
                }
                for change in event.changes
            ]
        }
        
        self.change_log.append(log_entry)
        
        # Write to file if configured
        if self.log_file:
            try:
                import aiofiles
                async with aiofiles.open(self.log_file, 'a') as f:
                    await f.write(json.dumps(log_entry) + '\n')
            except Exception as e:
                logger.error(f"Failed to write change log: {e}")
                
    def get_change_log(self, limit: int = None) -> List[Dict[str, Any]]:
        """Get configuration change log."""
        if limit:
            return self.change_log[-limit:]
        return self.change_log.copy()


class ConditionalReloader:
    """Reloads configuration based on conditions."""
    
    def __init__(self, hot_reload_manager: HotReloadManager):
        self.hot_reload_manager = hot_reload_manager
        self.conditions: List[Callable[[Dict[str, Any], Dict[str, Any]], bool]] = []
        
    def add_condition(self, condition: Callable[[Dict[str, Any], Dict[str, Any]], bool]) -> None:
        """Add a condition for configuration reload."""
        self.conditions.append(condition)
        
    async def conditional_reload(self, new_config: Dict[str, Any], 
                               old_config: Dict[str, Any],
                               provider_name: str = None) -> bool:
        """Reload configuration only if conditions are met."""
        for condition in self.conditions:
            try:
                if not condition(new_config, old_config):
                    logger.info("Configuration reload skipped due to condition")
                    return False
            except Exception as e:
                logger.error(f"Error evaluating reload condition: {e}")
                return False
                
        return await self.hot_reload_manager.reload_config(
            new_config, old_config, provider_name
        )


# Built-in reload conditions
class ReloadConditions:
    """Built-in reload conditions."""
    
    @staticmethod
    def only_if_critical_changed(critical_paths: Set[str]) -> Callable:
        """Only reload if critical configuration paths changed."""
        def condition(new_config: Dict[str, Any], old_config: Dict[str, Any]) -> bool:
            def has_critical_changes(new_dict: Dict[str, Any], old_dict: Dict[str, Any], 
                                   path: str = "") -> bool:
                for key, new_value in new_dict.items():
                    current_path = f"{path}.{key}" if path else key
                    
                    if current_path in critical_paths:
                        if key not in old_dict or old_dict[key] != new_value:
                            return True
                    elif isinstance(new_value, dict) and key in old_dict and isinstance(old_dict[key], dict):
                        if has_critical_changes(new_value, old_dict[key], current_path):
                            return True
                            
                return False
                
            return has_critical_changes(new_config, old_config)
        return condition
        
    @staticmethod
    def min_change_threshold(threshold: float) -> Callable:
        """Only reload if changes exceed threshold percentage."""
        def condition(new_config: Dict[str, Any], old_config: Dict[str, Any]) -> bool:
            def count_changes(new_dict: Dict[str, Any], old_dict: Dict[str, Any]) -> tuple:
                total, changed = 0, 0
                for key, new_value in new_dict.items():
                    total += 1
                    if key not in old_dict or old_dict[key] != new_value:
                        changed += 1
                    elif isinstance(new_value, dict) and isinstance(old_dict.get(key), dict):
                        sub_total, sub_changed = count_changes(new_value, old_dict[key])
                        total += sub_total
                        changed += sub_changed
                return total, changed
                
            total, changed = count_changes(new_config, old_config)
            if total == 0:
                return False
                
            change_percentage = changed / total
            return change_percentage >= threshold
        return condition
        
    @staticmethod
    def during_time_window(start_hour: int, end_hour: int) -> Callable:
        """Only reload during specific time window."""
        def condition(new_config: Dict[str, Any], old_config: Dict[str, Any]) -> bool:
            current_hour = datetime.now().hour
            if start_hour <= end_hour:
                return start_hour <= current_hour < end_hour
            else:  # Crosses midnight
                return current_hour >= start_hour or current_hour < end_hour
        return condition


# Factory functions
def create_hot_reload_manager(watcher: ConfigWatcher = None) -> HotReloadManager:
    """Create a hot reload manager."""
    return HotReloadManager(watcher)


def create_config_watcher() -> ConfigWatcher:
    """Create a configuration watcher."""
    return ConfigWatcher()


def create_change_logger(log_file: Union[str, Path] = None) -> ChangeLogger:
    """Create a change logger."""
    return ChangeLogger(log_file)


def create_conditional_reloader(hot_reload_manager: HotReloadManager) -> ConditionalReloader:
    """Create a conditional reloader."""
    return ConditionalReloader(hot_reload_manager)