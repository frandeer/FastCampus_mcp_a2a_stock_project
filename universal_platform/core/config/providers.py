"""
Configuration providers for multiple sources with priority ordering.
"""

import os
import json
import yaml
import asyncio
import aiofiles
import aiohttp
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Union
from pathlib import Path
from urllib.parse import urlparse
import sqlite3
import asyncpg
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)


class ConfigProvider(ABC):
    """Abstract base class for configuration providers."""
    
    def __init__(self, priority: int = 100):
        self.priority = priority
        self.last_modified: Optional[datetime] = None
        
    @abstractmethod
    async def load(self) -> Dict[str, Any]:
        """Load configuration data."""
        pass
        
    @abstractmethod
    async def watch(self, callback) -> None:
        """Watch for configuration changes."""
        pass
        
    @abstractmethod
    async def can_write(self) -> bool:
        """Check if provider supports writing."""
        pass
        
    async def save(self, config: Dict[str, Any]) -> None:
        """Save configuration data (if supported)."""
        raise NotImplementedError("Provider does not support writing")
        
    def __lt__(self, other):
        return self.priority < other.priority


class JSONFileProvider(ConfigProvider):
    """JSON file configuration provider."""
    
    def __init__(self, file_path: Union[str, Path], priority: int = 100):
        super().__init__(priority)
        self.file_path = Path(file_path)
        
    async def load(self) -> Dict[str, Any]:
        """Load configuration from JSON file."""
        try:
            if not self.file_path.exists():
                logger.warning(f"JSON config file not found: {self.file_path}")
                return {}
                
            # Update last modified time
            stat = self.file_path.stat()
            self.last_modified = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
            
            async with aiofiles.open(self.file_path, 'r', encoding='utf-8') as f:
                content = await f.read()
                config = json.loads(content)
                logger.info(f"Loaded JSON config from {self.file_path}")
                return config
                
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Failed to load JSON config from {self.file_path}: {e}")
            return {}
            
    async def watch(self, callback) -> None:
        """Watch JSON file for changes."""
        last_mtime = None
        if self.file_path.exists():
            last_mtime = self.file_path.stat().st_mtime
            
        while True:
            try:
                await asyncio.sleep(1)  # Check every second
                if self.file_path.exists():
                    current_mtime = self.file_path.stat().st_mtime
                    if last_mtime is None or current_mtime > last_mtime:
                        last_mtime = current_mtime
                        config = await self.load()
                        await callback(self, config)
            except Exception as e:
                logger.error(f"Error watching JSON file {self.file_path}: {e}")
                await asyncio.sleep(5)  # Wait longer on error
                
    async def can_write(self) -> bool:
        """Check if we can write to the JSON file."""
        try:
            if self.file_path.exists():
                return os.access(self.file_path, os.W_OK)
            else:
                # Check if parent directory is writable
                return os.access(self.file_path.parent, os.W_OK)
        except Exception:
            return False
            
    async def save(self, config: Dict[str, Any]) -> None:
        """Save configuration to JSON file."""
        try:
            # Ensure parent directory exists
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            
            async with aiofiles.open(self.file_path, 'w', encoding='utf-8') as f:
                content = json.dumps(config, indent=2, ensure_ascii=False)
                await f.write(content)
                
            logger.info(f"Saved JSON config to {self.file_path}")
            
        except Exception as e:
            logger.error(f"Failed to save JSON config to {self.file_path}: {e}")
            raise


class YAMLFileProvider(ConfigProvider):
    """YAML file configuration provider."""
    
    def __init__(self, file_path: Union[str, Path], priority: int = 100):
        super().__init__(priority)
        self.file_path = Path(file_path)
        
    async def load(self) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        try:
            if not self.file_path.exists():
                logger.warning(f"YAML config file not found: {self.file_path}")
                return {}
                
            # Update last modified time
            stat = self.file_path.stat()
            self.last_modified = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
            
            async with aiofiles.open(self.file_path, 'r', encoding='utf-8') as f:
                content = await f.read()
                config = yaml.safe_load(content) or {}
                logger.info(f"Loaded YAML config from {self.file_path}")
                return config
                
        except (yaml.YAMLError, IOError) as e:
            logger.error(f"Failed to load YAML config from {self.file_path}: {e}")
            return {}
            
    async def watch(self, callback) -> None:
        """Watch YAML file for changes."""
        last_mtime = None
        if self.file_path.exists():
            last_mtime = self.file_path.stat().st_mtime
            
        while True:
            try:
                await asyncio.sleep(1)  # Check every second
                if self.file_path.exists():
                    current_mtime = self.file_path.stat().st_mtime
                    if last_mtime is None or current_mtime > last_mtime:
                        last_mtime = current_mtime
                        config = await self.load()
                        await callback(self, config)
            except Exception as e:
                logger.error(f"Error watching YAML file {self.file_path}: {e}")
                await asyncio.sleep(5)
                
    async def can_write(self) -> bool:
        """Check if we can write to the YAML file."""
        try:
            if self.file_path.exists():
                return os.access(self.file_path, os.W_OK)
            else:
                return os.access(self.file_path.parent, os.W_OK)
        except Exception:
            return False
            
    async def save(self, config: Dict[str, Any]) -> None:
        """Save configuration to YAML file."""
        try:
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            
            async with aiofiles.open(self.file_path, 'w', encoding='utf-8') as f:
                content = yaml.dump(config, default_flow_style=False, 
                                   allow_unicode=True, sort_keys=False)
                await f.write(content)
                
            logger.info(f"Saved YAML config to {self.file_path}")
            
        except Exception as e:
            logger.error(f"Failed to save YAML config to {self.file_path}: {e}")
            raise


class EnvironmentProvider(ConfigProvider):
    """Environment variables configuration provider."""
    
    def __init__(self, prefix: str = "", priority: int = 10):
        super().__init__(priority)
        self.prefix = prefix.upper()
        
    async def load(self) -> Dict[str, Any]:
        """Load configuration from environment variables."""
        config = {}
        
        for key, value in os.environ.items():
            if self.prefix and not key.startswith(self.prefix):
                continue
                
            # Remove prefix and convert to lowercase
            config_key = key[len(self.prefix):].lstrip('_').lower()
            if not config_key:
                continue
                
            # Try to parse as JSON for complex values
            try:
                parsed_value = json.loads(value)
                config[config_key] = parsed_value
            except (json.JSONDecodeError, ValueError):
                # Fallback to string value
                config[config_key] = value
                
        logger.info(f"Loaded {len(config)} environment variables with prefix '{self.prefix}'")
        return config
        
    async def watch(self, callback) -> None:
        """Environment variables don't support watching in this implementation."""
        # Environment variables typically don't change during runtime
        # Could be extended to watch for process signals or file-based env updates
        pass
        
    async def can_write(self) -> bool:
        """Environment provider doesn't support writing."""
        return False


class DatabaseProvider(ConfigProvider):
    """Database configuration provider."""
    
    def __init__(self, connection_string: str, table_name: str = "config", 
                 priority: int = 50):
        super().__init__(priority)
        self.connection_string = connection_string
        self.table_name = table_name
        self._connection = None
        
    async def _get_connection(self):
        """Get database connection."""
        if self.connection_string.startswith('postgresql://'):
            if self._connection is None:
                self._connection = await asyncpg.connect(self.connection_string)
            return self._connection
        elif self.connection_string.startswith('sqlite://'):
            db_path = self.connection_string[9:]  # Remove 'sqlite://'
            return sqlite3.connect(db_path)
        else:
            raise ValueError(f"Unsupported database type: {self.connection_string}")
            
    async def load(self) -> Dict[str, Any]:
        """Load configuration from database."""
        try:
            if self.connection_string.startswith('postgresql://'):
                return await self._load_postgresql()
            elif self.connection_string.startswith('sqlite://'):
                return await self._load_sqlite()
        except Exception as e:
            logger.error(f"Failed to load config from database: {e}")
            return {}
            
    async def _load_postgresql(self) -> Dict[str, Any]:
        """Load from PostgreSQL database."""
        conn = await self._get_connection()
        
        # Ensure table exists
        await conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {self.table_name} (
                key VARCHAR(255) PRIMARY KEY,
                value JSONB,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        rows = await conn.fetch(f"SELECT key, value FROM {self.table_name}")
        config = {row['key']: row['value'] for row in rows}
        
        logger.info(f"Loaded {len(config)} config entries from PostgreSQL")
        return config
        
    async def _load_sqlite(self) -> Dict[str, Any]:
        """Load from SQLite database."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Ensure table exists
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {self.table_name} (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute(f"SELECT key, value FROM {self.table_name}")
        rows = cursor.fetchall()
        
        config = {}
        for key, value in rows:
            try:
                config[key] = json.loads(value)
            except (json.JSONDecodeError, ValueError):
                config[key] = value
                
        conn.close()
        logger.info(f"Loaded {len(config)} config entries from SQLite")
        return config
        
    async def watch(self, callback) -> None:
        """Watch database for changes (basic polling implementation)."""
        last_check = datetime.now(timezone.utc)
        
        while True:
            try:
                await asyncio.sleep(10)  # Check every 10 seconds
                
                if self.connection_string.startswith('postgresql://'):
                    conn = await self._get_connection()
                    # Check for updates since last check
                    rows = await conn.fetch(
                        f"SELECT COUNT(*) FROM {self.table_name} WHERE updated_at > $1",
                        last_check
                    )
                    if rows[0]['count'] > 0:
                        config = await self.load()
                        await callback(self, config)
                        last_check = datetime.now(timezone.utc)
                        
            except Exception as e:
                logger.error(f"Error watching database: {e}")
                await asyncio.sleep(30)  # Wait longer on error
                
    async def can_write(self) -> bool:
        """Database provider supports writing."""
        return True
        
    async def save(self, config: Dict[str, Any]) -> None:
        """Save configuration to database."""
        try:
            if self.connection_string.startswith('postgresql://'):
                await self._save_postgresql(config)
            elif self.connection_string.startswith('sqlite://'):
                await self._save_sqlite(config)
        except Exception as e:
            logger.error(f"Failed to save config to database: {e}")
            raise
            
    async def _save_postgresql(self, config: Dict[str, Any]) -> None:
        """Save to PostgreSQL database."""
        conn = await self._get_connection()
        
        # Clear existing config
        await conn.execute(f"DELETE FROM {self.table_name}")
        
        # Insert new config
        for key, value in config.items():
            await conn.execute(
                f"INSERT INTO {self.table_name} (key, value) VALUES ($1, $2)",
                key, json.dumps(value)
            )
            
        logger.info(f"Saved {len(config)} config entries to PostgreSQL")
        
    async def _save_sqlite(self, config: Dict[str, Any]) -> None:
        """Save to SQLite database."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Clear existing config
        cursor.execute(f"DELETE FROM {self.table_name}")
        
        # Insert new config
        for key, value in config.items():
            cursor.execute(
                f"INSERT INTO {self.table_name} (key, value) VALUES (?, ?)",
                (key, json.dumps(value))
            )
            
        conn.commit()
        conn.close()
        logger.info(f"Saved {len(config)} config entries to SQLite")


class RemoteProvider(ConfigProvider):
    """Remote HTTP/HTTPS configuration provider."""
    
    def __init__(self, url: str, headers: Optional[Dict[str, str]] = None, 
                 priority: int = 200, timeout: int = 30):
        super().__init__(priority)
        self.url = url
        self.headers = headers or {}
        self.timeout = timeout
        self.session = None
        
    async def _get_session(self):
        """Get HTTP session."""
        if self.session is None:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout)
            )
        return self.session
        
    async def load(self) -> Dict[str, Any]:
        """Load configuration from remote URL."""
        try:
            session = await self._get_session()
            
            async with session.get(self.url, headers=self.headers) as response:
                if response.status == 200:
                    content_type = response.headers.get('content-type', '').lower()
                    
                    if 'application/json' in content_type:
                        config = await response.json()
                    elif 'yaml' in content_type or 'yml' in content_type:
                        text = await response.text()
                        config = yaml.safe_load(text) or {}
                    else:
                        # Try JSON first, then YAML
                        text = await response.text()
                        try:
                            config = json.loads(text)
                        except json.JSONDecodeError:
                            config = yaml.safe_load(text) or {}
                            
                    logger.info(f"Loaded remote config from {self.url}")
                    return config
                else:
                    logger.error(f"Failed to load remote config: HTTP {response.status}")
                    return {}
                    
        except Exception as e:
            logger.error(f"Failed to load remote config from {self.url}: {e}")
            return {}
            
    async def watch(self, callback) -> None:
        """Poll remote URL for changes."""
        last_etag = None
        last_modified = None
        
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute
                
                session = await self._get_session()
                headers = self.headers.copy()
                
                # Add conditional headers
                if last_etag:
                    headers['If-None-Match'] = last_etag
                if last_modified:
                    headers['If-Modified-Since'] = last_modified
                    
                async with session.head(self.url, headers=headers) as response:
                    if response.status == 200:
                        # Content has changed
                        current_etag = response.headers.get('etag')
                        current_modified = response.headers.get('last-modified')
                        
                        if current_etag != last_etag or current_modified != last_modified:
                            config = await self.load()
                            await callback(self, config)
                            last_etag = current_etag
                            last_modified = current_modified
                            
            except Exception as e:
                logger.error(f"Error watching remote config {self.url}: {e}")
                await asyncio.sleep(300)  # Wait 5 minutes on error
                
    async def can_write(self) -> bool:
        """Remote provider doesn't support writing in this implementation."""
        return False
        
    async def close(self):
        """Close HTTP session."""
        if self.session:
            await self.session.close()
            self.session = None


class MemoryProvider(ConfigProvider):
    """In-memory configuration provider for testing and temporary config."""
    
    def __init__(self, initial_config: Optional[Dict[str, Any]] = None, 
                 priority: int = 1):
        super().__init__(priority)
        self.config = initial_config or {}
        
    async def load(self) -> Dict[str, Any]:
        """Load configuration from memory."""
        return self.config.copy()
        
    async def watch(self, callback) -> None:
        """Memory provider doesn't need watching."""
        pass
        
    async def can_write(self) -> bool:
        """Memory provider supports writing."""
        return True
        
    async def save(self, config: Dict[str, Any]) -> None:
        """Save configuration to memory."""
        self.config = config.copy()
        logger.info("Saved config to memory")


# Provider factory functions
def create_json_provider(file_path: Union[str, Path], priority: int = 100) -> JSONFileProvider:
    """Create a JSON file provider."""
    return JSONFileProvider(file_path, priority)


def create_yaml_provider(file_path: Union[str, Path], priority: int = 100) -> YAMLFileProvider:
    """Create a YAML file provider."""
    return YAMLFileProvider(file_path, priority)


def create_env_provider(prefix: str = "", priority: int = 10) -> EnvironmentProvider:
    """Create an environment variables provider."""
    return EnvironmentProvider(prefix, priority)


def create_database_provider(connection_string: str, table_name: str = "config", 
                           priority: int = 50) -> DatabaseProvider:
    """Create a database provider."""
    return DatabaseProvider(connection_string, table_name, priority)


def create_remote_provider(url: str, headers: Optional[Dict[str, str]] = None, 
                         priority: int = 200, timeout: int = 30) -> RemoteProvider:
    """Create a remote HTTP provider."""
    return RemoteProvider(url, headers, priority, timeout)


def create_memory_provider(initial_config: Optional[Dict[str, Any]] = None, 
                         priority: int = 1) -> MemoryProvider:
    """Create an in-memory provider."""
    return MemoryProvider(initial_config, priority)