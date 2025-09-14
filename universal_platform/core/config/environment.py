"""
Environment-specific configuration management with inheritance and overrides.
"""

import os
import json
import asyncio
from typing import Dict, Any, Optional, List, Set, Union
from pathlib import Path
from dataclasses import dataclass
from enum import Enum
from datetime import datetime, timezone
import logging
import re

from .providers import ConfigProvider, JSONFileProvider, YAMLFileProvider, EnvironmentProvider

logger = logging.getLogger(__name__)


class EnvironmentType(Enum):
    """Standard environment types."""
    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"
    LOCAL = "local"
    PREVIEW = "preview"


@dataclass
class EnvironmentInfo:
    """Environment information and metadata."""
    name: str
    type: EnvironmentType
    description: str = ""
    parent: Optional[str] = None
    tags: Set[str] = None
    created_at: datetime = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = set()
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)


class EnvironmentDetector:
    """Automatically detect current environment."""
    
    def __init__(self):
        self.detection_rules: List[callable] = [
            self._detect_from_env_var,
            self._detect_from_hostname,
            self._detect_from_process,
            self._detect_from_file,
            self._detect_from_git_branch
        ]
        
    def detect_environment(self) -> str:
        """Detect current environment using various heuristics."""
        for rule in self.detection_rules:
            try:
                env = rule()
                if env:
                    logger.info(f"Environment detected as '{env}' via {rule.__name__}")
                    return env
            except Exception as e:
                logger.debug(f"Environment detection rule {rule.__name__} failed: {e}")
                
        # Default fallback
        logger.warning("Could not detect environment, defaulting to 'development'")
        return "development"
        
    def _detect_from_env_var(self) -> Optional[str]:
        """Detect from environment variables."""
        env_vars = [
            "ENVIRONMENT", "ENV", "NODE_ENV", "FLASK_ENV", 
            "DJANGO_SETTINGS_MODULE", "RAILS_ENV", "APP_ENV"
        ]
        
        for var in env_vars:
            value = os.environ.get(var)
            if value:
                # Normalize common values
                normalized = value.lower().strip()
                if normalized in ["dev", "develop"]:
                    return "development"
                elif normalized in ["prod"]:
                    return "production"
                elif normalized in ["test"]:
                    return "testing"
                elif normalized in ["stage"]:
                    return "staging"
                return normalized
                
        return None
        
    def _detect_from_hostname(self) -> Optional[str]:
        """Detect from hostname patterns."""
        import socket
        hostname = socket.gethostname().lower()
        
        patterns = {
            "development": [r"dev", r"local", r"laptop", r"desktop"],
            "testing": [r"test", r"ci", r"build"],
            "staging": [r"stage", r"staging", r"pre"],
            "production": [r"prod", r"live", r"www"]
        }
        
        for env_type, patterns_list in patterns.items():
            for pattern in patterns_list:
                if re.search(pattern, hostname):
                    return env_type
                    
        return None
        
    def _detect_from_process(self) -> Optional[str]:
        """Detect from process environment."""
        import sys
        
        # Check for common development tools
        if hasattr(sys, 'ps1') or sys.flags.interactive:
            return "development"
            
        # Check for testing frameworks
        test_modules = ['pytest', 'unittest', 'nose', 'tox']
        for module in test_modules:
            if module in sys.modules:
                return "testing"
                
        return None
        
    def _detect_from_file(self) -> Optional[str]:
        """Detect from environment marker files."""
        markers = {
            ".development": "development",
            ".testing": "testing",
            ".staging": "staging",
            ".production": "production",
            "development.flag": "development",
            "production.flag": "production"
        }
        
        current_dir = Path.cwd()
        for marker_file, env_type in markers.items():
            if (current_dir / marker_file).exists():
                return env_type
                
        return None
        
    def _detect_from_git_branch(self) -> Optional[str]:
        """Detect from git branch name."""
        try:
            import subprocess
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                branch = result.stdout.strip().lower()
                
                branch_patterns = {
                    "development": [r"dev", r"develop", r"feature/", r"fix/"],
                    "testing": [r"test", r"qa"],
                    "staging": [r"stage", r"staging", r"release/"],
                    "production": [r"main", r"master", r"prod"]
                }
                
                for env_type, patterns in branch_patterns.items():
                    for pattern in patterns:
                        if re.search(pattern, branch):
                            return env_type
                            
        except Exception:
            pass
            
        return None


class EnvironmentManager:
    """Manages environment-specific configurations."""
    
    def __init__(self, base_path: Union[str, Path] = None):
        self.base_path = Path(base_path) if base_path else Path.cwd()
        self.environments: Dict[str, EnvironmentInfo] = {}
        self.current_environment: Optional[str] = None
        self.detector = EnvironmentDetector()
        self.inheritance_cache: Dict[str, List[str]] = {}
        
        # Default environments
        self._setup_default_environments()
        
    def _setup_default_environments(self):
        """Setup standard environments with inheritance."""
        self.environments = {
            "base": EnvironmentInfo(
                name="base",
                type=EnvironmentType.DEVELOPMENT,
                description="Base configuration shared by all environments"
            ),
            "development": EnvironmentInfo(
                name="development",
                type=EnvironmentType.DEVELOPMENT,
                description="Development environment",
                parent="base",
                tags={"dev", "local"}
            ),
            "testing": EnvironmentInfo(
                name="testing",
                type=EnvironmentType.TESTING,
                description="Testing and CI environment",
                parent="base",
                tags={"test", "ci"}
            ),
            "staging": EnvironmentInfo(
                name="staging",
                type=EnvironmentType.STAGING,
                description="Staging environment",
                parent="base",
                tags={"stage", "pre-prod"}
            ),
            "production": EnvironmentInfo(
                name="production",
                type=EnvironmentType.PRODUCTION,
                description="Production environment",
                parent="base",
                tags={"prod", "live"}
            )
        }
        
    def register_environment(self, env_info: EnvironmentInfo) -> 'EnvironmentManager':
        """Register a new environment."""
        self.environments[env_info.name] = env_info
        # Clear inheritance cache
        self.inheritance_cache.clear()
        return self
        
    def set_current_environment(self, name: str) -> 'EnvironmentManager':
        """Set current environment."""
        if name not in self.environments:
            raise ValueError(f"Unknown environment: {name}")
        self.current_environment = name
        logger.info(f"Current environment set to: {name}")
        return self
        
    def get_current_environment(self) -> str:
        """Get current environment name."""
        if self.current_environment is None:
            self.current_environment = self.detector.detect_environment()
            
            # Register detected environment if not exists
            if self.current_environment not in self.environments:
                self.environments[self.current_environment] = EnvironmentInfo(
                    name=self.current_environment,
                    type=EnvironmentType.DEVELOPMENT,
                    description=f"Auto-detected environment: {self.current_environment}",
                    parent="base"
                )
                
        return self.current_environment
        
    def get_environment_info(self, name: str = None) -> EnvironmentInfo:
        """Get environment information."""
        env_name = name or self.get_current_environment()
        if env_name not in self.environments:
            raise ValueError(f"Unknown environment: {env_name}")
        return self.environments[env_name]
        
    def get_inheritance_chain(self, name: str = None) -> List[str]:
        """Get environment inheritance chain from root to current."""
        env_name = name or self.get_current_environment()
        
        # Check cache
        if env_name in self.inheritance_cache:
            return self.inheritance_cache[env_name]
            
        chain = []
        current = env_name
        visited = set()
        
        while current and current not in visited:
            if current not in self.environments:
                break
            visited.add(current)
            chain.append(current)
            current = self.environments[current].parent
            
        # Reverse to get root-to-leaf order
        chain.reverse()
        
        # Cache result
        self.inheritance_cache[env_name] = chain
        
        return chain
        
    async def load_environment_config(self, name: str = None) -> Dict[str, Any]:
        """Load configuration for specific environment with inheritance."""
        env_name = name or self.get_current_environment()
        inheritance_chain = self.get_inheritance_chain(env_name)
        
        merged_config = {}
        
        # Load and merge configs in inheritance order
        for env in inheritance_chain:
            env_config = await self._load_single_environment_config(env)
            if env_config:
                merged_config = self._deep_merge(merged_config, env_config)
                logger.debug(f"Loaded environment config for: {env}")
                
        return merged_config
        
    async def _load_single_environment_config(self, name: str) -> Dict[str, Any]:
        """Load configuration for a single environment."""
        config = {}
        
        # Try different file formats and locations
        config_files = [
            self.base_path / "config" / f"{name}.json",
            self.base_path / "config" / f"{name}.yml",
            self.base_path / "config" / f"{name}.yaml",
            self.base_path / f"config.{name}.json",
            self.base_path / f"config.{name}.yml",
            self.base_path / f"config.{name}.yaml",
            self.base_path / "environments" / f"{name}.json",
            self.base_path / "environments" / f"{name}.yml",
            self.base_path / "environments" / f"{name}.yaml"
        ]
        
        for config_file in config_files:
            if config_file.exists():
                try:
                    if config_file.suffix.lower() == '.json':
                        provider = JSONFileProvider(config_file)
                    else:
                        provider = YAMLFileProvider(config_file)
                        
                    file_config = await provider.load()
                    if file_config:
                        config = self._deep_merge(config, file_config)
                        
                except Exception as e:
                    logger.error(f"Failed to load environment config {config_file}: {e}")
                    
        return config
        
    async def get_environment_config(self, name: str = None) -> Dict[str, Any]:
        """Get complete environment configuration."""
        return await self.load_environment_config(name)
        
    def get_environment_variables(self, name: str = None) -> Dict[str, str]:
        """Get environment-specific environment variables."""
        env_name = name or self.get_current_environment()
        env_prefix = f"{env_name.upper()}_"
        
        env_vars = {}
        for key, value in os.environ.items():
            if key.startswith(env_prefix):
                # Remove prefix and convert to config key
                config_key = key[len(env_prefix):].lower()
                env_vars[config_key] = value
                
        return env_vars
        
    def create_environment_providers(self, name: str = None) -> List[ConfigProvider]:
        """Create configuration providers for environment."""
        env_name = name or self.get_current_environment()
        inheritance_chain = self.get_inheritance_chain(env_name)
        
        providers = []
        priority = 100  # Start with low priority
        
        # Create providers for inheritance chain (reverse order for correct priority)
        for env in reversed(inheritance_chain):
            # JSON provider
            json_file = self.base_path / "config" / f"{env}.json"
            if json_file.exists():
                providers.append(JSONFileProvider(json_file, priority))
                priority -= 1
                
            # YAML provider
            for ext in ['.yml', '.yaml']:
                yaml_file = self.base_path / "config" / f"{env}{ext}"
                if yaml_file.exists():
                    providers.append(YAMLFileProvider(yaml_file, priority))
                    priority -= 1
                    break
                    
        # Environment variables provider (highest priority)
        env_prefix = f"{env_name.upper()}_"
        providers.append(EnvironmentProvider(env_prefix, 10))
        
        return providers
        
    def _deep_merge(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """Deep merge two dictionaries."""
        result = base.copy()
        
        for key, value in override.items():
            if (key in result and isinstance(result[key], dict) 
                and isinstance(value, dict)):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
                
        return result
        
    def validate_environment(self, name: str) -> List[str]:
        """Validate environment configuration."""
        errors = []
        
        if name not in self.environments:
            errors.append(f"Environment '{name}' is not registered")
            return errors
            
        env_info = self.environments[name]
        
        # Check parent exists
        if env_info.parent and env_info.parent not in self.environments:
            errors.append(f"Parent environment '{env_info.parent}' not found")
            
        # Check for circular inheritance
        try:
            self.get_inheritance_chain(name)
        except RecursionError:
            errors.append(f"Circular inheritance detected in environment '{name}'")
            
        return errors
        
    def list_environments(self) -> List[str]:
        """List all registered environments."""
        return list(self.environments.keys())
        
    def get_environment_tree(self) -> Dict[str, Any]:
        """Get environment inheritance tree."""
        tree = {}
        
        def build_tree(env_name: str) -> Dict[str, Any]:
            env_info = self.environments[env_name]
            children = [
                name for name, info in self.environments.items()
                if info.parent == env_name
            ]
            
            return {
                "name": env_name,
                "type": env_info.type.value,
                "description": env_info.description,
                "tags": list(env_info.tags),
                "children": [build_tree(child) for child in children]
            }
            
        # Find root environments (no parent)
        roots = [
            name for name, info in self.environments.items()
            if info.parent is None
        ]
        
        return {
            "roots": [build_tree(root) for root in roots]
        }
        
    def export_environment_config(self, name: str = None, 
                                 format: str = "json") -> str:
        """Export environment configuration."""
        env_name = name or self.get_current_environment()
        
        # Get environment config (this is async, so we need to handle it)
        import asyncio
        config = asyncio.run(self.load_environment_config(env_name))
        
        if format.lower() == "json":
            return json.dumps(config, indent=2, ensure_ascii=False)
        elif format.lower() in ["yml", "yaml"]:
            import yaml
            return yaml.dump(config, default_flow_style=False, allow_unicode=True)
        else:
            raise ValueError(f"Unsupported format: {format}")
            
    async def switch_environment(self, name: str) -> Dict[str, Any]:
        """Switch to different environment and return its config."""
        if name not in self.environments:
            raise ValueError(f"Unknown environment: {name}")
            
        old_env = self.current_environment
        self.current_environment = name
        
        logger.info(f"Switched environment from '{old_env}' to '{name}'")
        
        return await self.load_environment_config(name)
        
    def create_environment_snapshot(self, name: str = None) -> Dict[str, Any]:
        """Create snapshot of environment configuration."""
        env_name = name or self.get_current_environment()
        env_info = self.environments[env_name]
        
        return {
            "environment": {
                "name": env_info.name,
                "type": env_info.type.value,
                "description": env_info.description,
                "parent": env_info.parent,
                "tags": list(env_info.tags),
                "created_at": env_info.created_at.isoformat()
            },
            "inheritance_chain": self.get_inheritance_chain(env_name),
            "config_files": [
                str(file) for file in [
                    self.base_path / "config" / f"{env_name}.json",
                    self.base_path / "config" / f"{env_name}.yml",
                    self.base_path / "config" / f"{env_name}.yaml"
                ] if file.exists()
            ],
            "snapshot_time": datetime.now(timezone.utc).isoformat()
        }


# Factory functions
def create_environment_manager(base_path: Union[str, Path] = None) -> EnvironmentManager:
    """Create an environment manager."""
    return EnvironmentManager(base_path)


def create_environment_detector() -> EnvironmentDetector:
    """Create an environment detector."""
    return EnvironmentDetector()


# Global environment manager
_global_environment_manager: Optional[EnvironmentManager] = None


def get_global_environment_manager() -> EnvironmentManager:
    """Get global environment manager (singleton)."""
    global _global_environment_manager
    if _global_environment_manager is None:
        _global_environment_manager = EnvironmentManager()
    return _global_environment_manager


def set_global_environment_manager(manager: EnvironmentManager) -> None:
    """Set global environment manager."""
    global _global_environment_manager
    _global_environment_manager = manager