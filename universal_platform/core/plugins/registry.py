"""
Universal Platform Plugin Registry

Enterprise-grade plugin registry with dependency resolution, versioning,
conflict detection, and comprehensive plugin lifecycle management.

Features:
- Plugin discovery and registration
- Dependency resolution with cycle detection
- Version compatibility checking
- Plugin metadata management
- Conflict detection and resolution
- Plugin state tracking
- Performance monitoring
"""

import asyncio
import logging
import re
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from packaging import version

from .interfaces import PluginMetadata, PluginType, PluginPriority, SecurityLevel


class RegistryState(Enum):
    """Registry state enumeration"""
    INITIALIZING = "initializing"
    READY = "ready"
    UPDATING = "updating"
    ERROR = "error"


class ConflictType(Enum):
    """Plugin conflict types"""
    NAME_COLLISION = "name_collision"
    VERSION_CONFLICT = "version_conflict"
    DEPENDENCY_CONFLICT = "dependency_conflict"
    RESOURCE_CONFLICT = "resource_conflict"
    SECURITY_CONFLICT = "security_conflict"
    CAPABILITY_CONFLICT = "capability_conflict"


@dataclass
class PluginInfo:
    """Plugin registration information"""
    name: str
    path: Path
    metadata: Optional[PluginMetadata] = None
    registration_time: datetime = field(default_factory=datetime.now)
    last_updated: datetime = field(default_factory=datetime.now)
    is_available: bool = True
    load_count: int = 0
    error_count: int = 0
    last_error: Optional[str] = None
    
    def update_metadata(self, metadata: PluginMetadata) -> None:
        """Update plugin metadata."""
        self.metadata = metadata
        self.last_updated = datetime.now()
    
    def record_load(self) -> None:
        """Record successful plugin load."""
        self.load_count += 1
        self.last_updated = datetime.now()
    
    def record_error(self, error: str) -> None:
        """Record plugin error."""
        self.error_count += 1
        self.last_error = error
        self.last_updated = datetime.now()


@dataclass
class PluginConflict:
    """Plugin conflict information"""
    conflict_type: ConflictType
    plugins: List[str]
    description: str
    severity: str = "medium"
    resolution_suggested: Optional[str] = None
    auto_resolvable: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert conflict to dictionary."""
        return {
            'type': self.conflict_type.value,
            'plugins': self.plugins,
            'description': self.description,
            'severity': self.severity,
            'resolution_suggested': self.resolution_suggested,
            'auto_resolvable': self.auto_resolvable
        }


@dataclass
class DependencyGraph:
    """Dependency graph for plugin resolution"""
    nodes: Set[str] = field(default_factory=set)
    edges: Dict[str, Set[str]] = field(default_factory=lambda: defaultdict(set))
    reverse_edges: Dict[str, Set[str]] = field(default_factory=lambda: defaultdict(set))
    
    def add_node(self, node: str) -> None:
        """Add a node to the graph."""
        self.nodes.add(node)
        if node not in self.edges:
            self.edges[node] = set()
        if node not in self.reverse_edges:
            self.reverse_edges[node] = set()
    
    def add_edge(self, from_node: str, to_node: str) -> None:
        """Add an edge to the graph."""
        self.add_node(from_node)
        self.add_node(to_node)
        self.edges[from_node].add(to_node)
        self.reverse_edges[to_node].add(from_node)
    
    def remove_node(self, node: str) -> None:
        """Remove a node and all its edges."""
        if node not in self.nodes:
            return
        
        # Remove outgoing edges
        for target in list(self.edges[node]):
            self.reverse_edges[target].discard(node)
        del self.edges[node]
        
        # Remove incoming edges
        for source in list(self.reverse_edges[node]):
            self.edges[source].discard(node)
        del self.reverse_edges[node]
        
        # Remove from nodes
        self.nodes.discard(node)
    
    def has_cycle(self) -> bool:
        """Check if the graph has cycles using DFS."""
        white = set(self.nodes)
        gray = set()
        black = set()
        
        def dfs(node: str) -> bool:
            if node in black:
                return False
            if node in gray:
                return True  # Cycle found
            
            gray.add(node)
            white.discard(node)
            
            for neighbor in self.edges[node]:
                if dfs(neighbor):
                    return True
            
            gray.discard(node)
            black.add(node)
            return False
        
        for node in list(white):
            if dfs(node):
                return True
        
        return False
    
    def topological_sort(self) -> List[str]:
        """Return topologically sorted list of nodes."""
        if self.has_cycle():
            raise ValueError("Cannot sort graph with cycles")
        
        in_degree = {node: len(self.reverse_edges[node]) for node in self.nodes}
        queue = deque([node for node in self.nodes if in_degree[node] == 0])
        result = []
        
        while queue:
            node = queue.popleft()
            result.append(node)
            
            for neighbor in self.edges[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
        
        return result


class PluginRegistry:
    """
    Enterprise-grade plugin registry with dependency resolution and conflict management.
    
    Manages plugin discovery, registration, dependency resolution, version compatibility,
    and conflict detection for the universal platform plugin system.
    """
    
    def __init__(self):
        """Initialize the plugin registry."""
        self.logger = logging.getLogger(__name__)
        self.state = RegistryState.INITIALIZING
        
        # Plugin storage
        self.plugins: Dict[str, PluginInfo] = {}
        self.plugin_paths: Dict[str, Path] = {}
        self.metadata_cache: Dict[str, PluginMetadata] = {}
        
        # Dependency management
        self.dependency_graph = DependencyGraph()
        self.resolved_order: List[str] = []
        
        # Conflict tracking
        self.conflicts: List[PluginConflict] = []
        self.conflict_history: List[PluginConflict] = []
        
        # Indexing for performance
        self.plugins_by_type: Dict[PluginType, Set[str]] = defaultdict(set)
        self.plugins_by_capability: Dict[str, Set[str]] = defaultdict(set)
        self.plugins_by_author: Dict[str, Set[str]] = defaultdict(set)
        self.plugins_by_version: Dict[str, Dict[str, str]] = defaultdict(dict)
        
        # Statistics
        self.registration_count = 0
        self.resolution_count = 0
        self.conflict_count = 0
        
        self.logger.info("Plugin registry initialized")
    
    async def initialize(self) -> None:
        """Initialize the registry."""
        try:
            self.state = RegistryState.INITIALIZING
            self.logger.info("Initializing plugin registry...")
            
            # Build initial indexes
            await self._rebuild_indexes()
            
            self.state = RegistryState.READY
            self.logger.info("Plugin registry initialization complete")
            
        except Exception as e:
            self.state = RegistryState.ERROR
            self.logger.error(f"Failed to initialize plugin registry: {e}")
            raise
    
    async def register_plugin_path(self, plugin_name: str, plugin_path: Path) -> bool:
        """
        Register a plugin path for discovery.
        
        Args:
            plugin_name: Name of the plugin
            plugin_path: Path to the plugin
            
        Returns:
            True if registered successfully, False otherwise
        """
        try:
            self.logger.debug(f"Registering plugin path: {plugin_name} -> {plugin_path}")
            
            # Validate path exists
            if not plugin_path.exists():
                self.logger.error(f"Plugin path does not exist: {plugin_path}")
                return False
            
            # Check for existing registration
            if plugin_name in self.plugins:
                existing_path = self.plugins[plugin_name].path
                if existing_path != plugin_path:
                    self.logger.warning(f"Plugin {plugin_name} already registered with different path")
                    return False
                else:
                    self.logger.debug(f"Plugin {plugin_name} already registered with same path")
                    return True
            
            # Create plugin info
            plugin_info = PluginInfo(name=plugin_name, path=plugin_path)
            
            # Try to load metadata
            metadata = await self._load_plugin_metadata(plugin_path)
            if metadata:
                plugin_info.update_metadata(metadata)
                self.metadata_cache[plugin_name] = metadata
            
            # Register plugin
            self.plugins[plugin_name] = plugin_info
            self.plugin_paths[plugin_name] = plugin_path
            self.registration_count += 1
            
            # Update indexes
            await self._update_indexes_for_plugin(plugin_name, plugin_info)
            
            self.logger.info(f"Plugin {plugin_name} registered successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to register plugin {plugin_name}: {e}")
            return False
    
    async def unregister_plugin(self, plugin_name: str) -> bool:
        """
        Unregister a plugin.
        
        Args:
            plugin_name: Name of the plugin to unregister
            
        Returns:
            True if unregistered successfully, False otherwise
        """
        try:
            if plugin_name not in self.plugins:
                self.logger.warning(f"Plugin {plugin_name} is not registered")
                return True
            
            self.logger.info(f"Unregistering plugin: {plugin_name}")
            
            # Remove from dependency graph
            self.dependency_graph.remove_node(plugin_name)
            
            # Remove from indexes
            await self._remove_from_indexes(plugin_name)
            
            # Remove from main storage
            del self.plugins[plugin_name]
            del self.plugin_paths[plugin_name]
            self.metadata_cache.pop(plugin_name, None)
            
            # Remove from resolved order
            if plugin_name in self.resolved_order:
                self.resolved_order.remove(plugin_name)
            
            self.logger.info(f"Plugin {plugin_name} unregistered successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to unregister plugin {plugin_name}: {e}")
            return False
    
    async def get_plugin(self, plugin_name: str) -> Optional[PluginInfo]:
        """
        Get plugin information by name.
        
        Args:
            plugin_name: Name of the plugin
            
        Returns:
            Plugin information or None if not found
        """
        return self.plugins.get(plugin_name)
    
    async def list_plugins(
        self,
        plugin_type: Optional[PluginType] = None,
        capability: Optional[str] = None,
        author: Optional[str] = None,
        available_only: bool = True
    ) -> List[PluginInfo]:
        """
        List plugins with optional filters.
        
        Args:
            plugin_type: Filter by plugin type
            capability: Filter by capability
            author: Filter by author
            available_only: Only include available plugins
            
        Returns:
            List of matching plugin information
        """
        plugins = []
        
        # Get candidate plugin names based on filters
        candidates = set(self.plugins.keys())
        
        if plugin_type:
            candidates &= self.plugins_by_type.get(plugin_type, set())
        
        if capability:
            candidates &= self.plugins_by_capability.get(capability, set())
        
        if author:
            candidates &= self.plugins_by_author.get(author, set())
        
        # Filter by availability
        for plugin_name in candidates:
            plugin_info = self.plugins[plugin_name]
            if not available_only or plugin_info.is_available:
                plugins.append(plugin_info)
        
        return plugins
    
    async def resolve_dependencies(self, plugin_names: List[str]) -> Tuple[List[str], List[PluginConflict]]:
        """
        Resolve plugin dependencies and return load order.
        
        Args:
            plugin_names: List of plugin names to resolve
            
        Returns:
            Tuple of (resolved_order, conflicts)
        """
        try:
            self.logger.info(f"Resolving dependencies for plugins: {plugin_names}")
            self.resolution_count += 1
            
            # Build dependency graph for requested plugins
            graph = DependencyGraph()
            all_plugins = set()
            conflicts = []
            
            # Add plugins and their dependencies recursively
            to_process = deque(plugin_names)
            processed = set()
            
            while to_process:
                plugin_name = to_process.popleft()
                
                if plugin_name in processed:
                    continue
                
                processed.add(plugin_name)
                
                # Check if plugin exists
                if plugin_name not in self.plugins:
                    conflicts.append(PluginConflict(
                        conflict_type=ConflictType.DEPENDENCY_CONFLICT,
                        plugins=[plugin_name],
                        description=f"Plugin {plugin_name} not found in registry",
                        severity="high"
                    ))
                    continue
                
                plugin_info = self.plugins[plugin_name]
                
                # Check if plugin is available
                if not plugin_info.is_available:
                    conflicts.append(PluginConflict(
                        conflict_type=ConflictType.DEPENDENCY_CONFLICT,
                        plugins=[plugin_name],
                        description=f"Plugin {plugin_name} is not available",
                        severity="high"
                    ))
                    continue
                
                all_plugins.add(plugin_name)
                graph.add_node(plugin_name)
                
                # Add dependencies
                if plugin_info.metadata and plugin_info.metadata.dependencies:
                    for dep_name, dep_version in plugin_info.metadata.dependencies.items():
                        # Check if dependency exists
                        if dep_name not in self.plugins:
                            conflicts.append(PluginConflict(
                                conflict_type=ConflictType.DEPENDENCY_CONFLICT,
                                plugins=[plugin_name, dep_name],
                                description=f"Dependency {dep_name} not found for plugin {plugin_name}",
                                severity="high"
                            ))
                            continue
                        
                        # Check version compatibility
                        dep_info = self.plugins[dep_name]
                        if dep_info.metadata:
                            if not self._is_version_compatible(dep_info.metadata.version, dep_version):
                                conflicts.append(PluginConflict(
                                    conflict_type=ConflictType.VERSION_CONFLICT,
                                    plugins=[plugin_name, dep_name],
                                    description=f"Version conflict: {plugin_name} requires {dep_name} {dep_version}, but {dep_info.metadata.version} is available",
                                    severity="high"
                                ))
                                continue
                        
                        graph.add_edge(dep_name, plugin_name)
                        to_process.append(dep_name)
            
            # Check for circular dependencies
            if graph.has_cycle():
                conflicts.append(PluginConflict(
                    conflict_type=ConflictType.DEPENDENCY_CONFLICT,
                    plugins=list(all_plugins),
                    description="Circular dependency detected",
                    severity="critical"
                ))
                return [], conflicts
            
            # Detect additional conflicts
            additional_conflicts = await self._detect_conflicts(list(all_plugins))
            conflicts.extend(additional_conflicts)
            
            # Get topological order
            try:
                resolved_order = graph.topological_sort()
                # Filter to only include requested plugins and their dependencies
                resolved_order = [p for p in resolved_order if p in all_plugins]
                
                self.logger.info(f"Dependency resolution successful: {resolved_order}")
                return resolved_order, conflicts
                
            except ValueError as e:
                conflicts.append(PluginConflict(
                    conflict_type=ConflictType.DEPENDENCY_CONFLICT,
                    plugins=list(all_plugins),
                    description=f"Failed to resolve dependencies: {e}",
                    severity="critical"
                ))
                return [], conflicts
            
        except Exception as e:
            self.logger.error(f"Error during dependency resolution: {e}")
            conflicts.append(PluginConflict(
                conflict_type=ConflictType.DEPENDENCY_CONFLICT,
                plugins=plugin_names,
                description=f"Internal error during resolution: {e}",
                severity="critical"
            ))
            return [], conflicts
    
    async def check_conflicts(self, plugin_names: List[str] = None) -> List[PluginConflict]:
        """
        Check for conflicts between plugins.
        
        Args:
            plugin_names: Specific plugins to check (checks all if None)
            
        Returns:
            List of detected conflicts
        """
        if plugin_names is None:
            plugin_names = list(self.plugins.keys())
        
        return await self._detect_conflicts(plugin_names)
    
    async def get_load_order(self, plugin_names: List[str]) -> List[str]:
        """
        Get recommended load order for plugins.
        
        Args:
            plugin_names: List of plugin names
            
        Returns:
            Ordered list of plugin names
        """
        resolved_order, conflicts = await self.resolve_dependencies(plugin_names)
        
        if conflicts:
            # Log conflicts but continue with partial resolution
            for conflict in conflicts:
                if conflict.severity == "critical":
                    self.logger.error(f"Critical conflict: {conflict.description}")
                else:
                    self.logger.warning(f"Conflict: {conflict.description}")
        
        return resolved_order
    
    async def find_plugins_by_capability(self, capability: str) -> List[str]:
        """
        Find plugins that provide a specific capability.
        
        Args:
            capability: Capability to search for
            
        Returns:
            List of plugin names that provide the capability
        """
        return list(self.plugins_by_capability.get(capability, set()))
    
    async def find_plugins_by_type(self, plugin_type: PluginType) -> List[str]:
        """
        Find plugins of a specific type.
        
        Args:
            plugin_type: Plugin type to search for
            
        Returns:
            List of plugin names of the specified type
        """
        return list(self.plugins_by_type.get(plugin_type, set()))
    
    async def get_plugin_statistics(self) -> Dict[str, Any]:
        """
        Get registry statistics.
        
        Returns:
            Dictionary of statistics
        """
        available_count = sum(1 for p in self.plugins.values() if p.is_available)
        
        by_type = {}
        for plugin_type, plugin_set in self.plugins_by_type.items():
            by_type[plugin_type.value] = len(plugin_set)
        
        return {
            'total_plugins': len(self.plugins),
            'available_plugins': available_count,
            'unavailable_plugins': len(self.plugins) - available_count,
            'plugins_by_type': by_type,
            'total_capabilities': len(self.plugins_by_capability),
            'total_conflicts': len(self.conflicts),
            'registration_count': self.registration_count,
            'resolution_count': self.resolution_count,
            'conflict_count': self.conflict_count,
            'state': self.state.value
        }
    
    # Private helper methods
    
    async def _load_plugin_metadata(self, plugin_path: Path) -> Optional[PluginMetadata]:
        """Load plugin metadata from path."""
        try:
            # This would typically parse metadata from plugin files
            # For now, return a basic metadata structure
            metadata = PluginMetadata(
                name=plugin_path.stem,
                version="1.0.0",
                description=f"Plugin at {plugin_path}"
            )
            return metadata
            
        except Exception as e:
            self.logger.error(f"Failed to load metadata for {plugin_path}: {e}")
            return None
    
    async def _update_indexes_for_plugin(self, plugin_name: str, plugin_info: PluginInfo) -> None:
        """Update indexes when a plugin is added."""
        if plugin_info.metadata:
            metadata = plugin_info.metadata
            
            # Index by type
            self.plugins_by_type[metadata.plugin_type].add(plugin_name)
            
            # Index by capabilities
            for capability in metadata.provides:
                self.plugins_by_capability[capability].add(plugin_name)
            
            # Index by author
            if metadata.author:
                self.plugins_by_author[metadata.author].add(plugin_name)
            
            # Index by version
            self.plugins_by_version[plugin_name] = metadata.version
    
    async def _remove_from_indexes(self, plugin_name: str) -> None:
        """Remove plugin from all indexes."""
        plugin_info = self.plugins.get(plugin_name)
        if not plugin_info or not plugin_info.metadata:
            return
        
        metadata = plugin_info.metadata
        
        # Remove from type index
        self.plugins_by_type[metadata.plugin_type].discard(plugin_name)
        
        # Remove from capability index
        for capability in metadata.provides:
            self.plugins_by_capability[capability].discard(plugin_name)
        
        # Remove from author index
        if metadata.author:
            self.plugins_by_author[metadata.author].discard(plugin_name)
        
        # Remove from version index
        self.plugins_by_version.pop(plugin_name, None)
    
    async def _rebuild_indexes(self) -> None:
        """Rebuild all indexes from current plugins."""
        self.plugins_by_type.clear()
        self.plugins_by_capability.clear()
        self.plugins_by_author.clear()
        self.plugins_by_version.clear()
        
        for plugin_name, plugin_info in self.plugins.items():
            await self._update_indexes_for_plugin(plugin_name, plugin_info)
    
    async def _detect_conflicts(self, plugin_names: List[str]) -> List[PluginConflict]:
        """Detect conflicts between specified plugins."""
        conflicts = []
        
        # Name collisions (should not happen with current design)
        name_counts = {}
        for name in plugin_names:
            name_counts[name] = name_counts.get(name, 0) + 1
        
        for name, count in name_counts.items():
            if count > 1:
                conflicts.append(PluginConflict(
                    conflict_type=ConflictType.NAME_COLLISION,
                    plugins=[name],
                    description=f"Plugin name collision: {name}",
                    severity="critical"
                ))
        
        # Capability conflicts (multiple plugins providing same capability)
        capability_providers = defaultdict(list)
        for plugin_name in plugin_names:
            plugin_info = self.plugins.get(plugin_name)
            if plugin_info and plugin_info.metadata:
                for capability in plugin_info.metadata.provides:
                    capability_providers[capability].append(plugin_name)
        
        for capability, providers in capability_providers.items():
            if len(providers) > 1:
                conflicts.append(PluginConflict(
                    conflict_type=ConflictType.CAPABILITY_CONFLICT,
                    plugins=providers,
                    description=f"Multiple plugins provide capability '{capability}': {', '.join(providers)}",
                    severity="medium",
                    resolution_suggested="Configure plugin priority or disable conflicting plugins",
                    auto_resolvable=True
                ))
        
        # Resource conflicts (similar resource requirements)
        # This is a simplified check - real implementation would be more sophisticated
        high_resource_plugins = []
        for plugin_name in plugin_names:
            plugin_info = self.plugins.get(plugin_name)
            if plugin_info and plugin_info.metadata:
                if (plugin_info.metadata.max_memory_mb > 500 or 
                    plugin_info.metadata.max_cpu_percent > 50):
                    high_resource_plugins.append(plugin_name)
        
        if len(high_resource_plugins) > 2:
            conflicts.append(PluginConflict(
                conflict_type=ConflictType.RESOURCE_CONFLICT,
                plugins=high_resource_plugins,
                description=f"Multiple high-resource plugins may cause resource contention: {', '.join(high_resource_plugins)}",
                severity="low",
                resolution_suggested="Monitor resource usage and consider load balancing",
                auto_resolvable=False
            ))
        
        return conflicts
    
    def _is_version_compatible(self, available_version: str, required_version: str) -> bool:
        """Check if available version satisfies required version."""
        try:
            # Simple version compatibility check
            # Real implementation would handle semantic versioning properly
            available = version.parse(available_version)
            
            # Handle version ranges (simplified)
            if required_version.startswith('>='):
                required = version.parse(required_version[2:])
                return available >= required
            elif required_version.startswith('>'):
                required = version.parse(required_version[1:])
                return available > required
            elif required_version.startswith('<='):
                required = version.parse(required_version[2:])
                return available <= required
            elif required_version.startswith('<'):
                required = version.parse(required_version[1:])
                return available < required
            elif required_version.startswith('=='):
                required = version.parse(required_version[2:])
                return available == required
            else:
                # Default to exact match
                required = version.parse(required_version)
                return available == required
                
        except Exception:
            # If version parsing fails, assume incompatible
            return False