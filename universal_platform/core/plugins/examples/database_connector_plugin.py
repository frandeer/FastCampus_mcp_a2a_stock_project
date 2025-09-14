"""
Database Connector Plugin Example

Demonstrates a connector-type plugin that provides database connectivity
with connection pooling, query execution, and health monitoring.
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from ..interfaces import ConnectorPlugin, PluginConfig, PluginHealth
from ..decorators import (
    plugin_metadata, config_schema, lifecycle_hook, requires_permission,
    monitor_performance, retry_on_failure, timeout, validate_input,
    cache_result, log_calls,
    HookType, PermissionType
)


@plugin_metadata(
    name="database_connector",
    version="1.2.0",
    description="Universal database connector with connection pooling and query optimization",
    author="Universal Platform Team",
    plugin_type="connector",
    provides=["database", "sql", "storage"],
    requires=["network"],
    tags=["database", "sql", "connector", "storage"],
    max_memory_mb=200,
    network_access=True,
    file_system_access=False
)
@config_schema({
    'database_type': {'type': str, 'required': True, 'choices': ['postgresql', 'mysql', 'sqlite']},
    'host': {'type': str, 'required': False, 'default': 'localhost'},
    'port': {'type': int, 'required': False, 'default': 5432},
    'database': {'type': str, 'required': True},
    'username': {'type': str, 'required': True},
    'password': {'type': str, 'required': True},
    'pool_size': {'type': int, 'required': False, 'default': 10},
    'max_overflow': {'type': int, 'required': False, 'default': 20},
    'pool_timeout': {'type': int, 'required': False, 'default': 30},
    'query_timeout': {'type': int, 'required': False, 'default': 60},
    'enable_ssl': {'type': bool, 'required': False, 'default': True},
    'auto_commit': {'type': bool, 'required': False, 'default': False}
})
class DatabaseConnectorPlugin(ConnectorPlugin):
    """
    Database connector plugin providing universal database connectivity.
    """
    
    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self._connection_pool = None
        self._connection_params = None
        self._stats = {
            'connections_created': 0,
            'connections_closed': 0,
            'queries_executed': 0,
            'queries_failed': 0,
            'total_query_time': 0.0,
            'last_query_time': None
        }
        self._health_cache_ttl = 30  # seconds
    
    @lifecycle_hook(HookType.BEFORE_INIT)
    async def _validate_config(self):
        """Validate database configuration before initialization."""
        self.logger.info("Validating database configuration...")
    
    async def initialize(self, config: PluginConfig) -> None:
        """Initialize the database connector plugin."""
        self.logger.info("Initializing database connector plugin...")
        
        # Validate configuration
        if hasattr(self, 'validate_config'):
            self.validate_config(config)
        
        self._plugin_config = config
        
        # Store connection parameters
        self._connection_params = {
            'database_type': config.get('database_type'),
            'host': config.get('host', 'localhost'),
            'port': config.get('port', 5432),
            'database': config.get('database'),
            'username': config.get('username'),
            'password': config.get('password'),
            'enable_ssl': config.get('enable_ssl', True)
        }
        
        self._is_initialized = True
        self.logger.info("Database connector plugin initialized successfully")
    
    @timeout(30.0)
    @retry_on_failure(max_attempts=3, delay=2.0)
    async def start(self) -> None:
        """Start the database connector."""
        self.logger.info("Starting database connector...")
        
        # Create connection pool
        await self._create_connection_pool()
        
        # Test initial connection
        if not await self.is_connected():
            raise RuntimeError("Failed to establish initial database connection")
        
        self._is_started = True
        self.logger.info("Database connector started successfully")
    
    async def stop(self) -> None:
        """Stop the database connector."""
        self.logger.info("Stopping database connector...")
        
        # Close connection pool
        await self._close_connection_pool()
        
        self._is_started = False
        self.logger.info("Database connector stopped successfully")
    
    async def destroy(self) -> None:
        """Destroy the database connector plugin."""
        self.logger.info("Destroying database connector plugin...")
        
        # Ensure connection pool is closed
        if self._connection_pool:
            await self._close_connection_pool()
        
        # Clear statistics
        self._stats.clear()
        self._connection_params = None
        
        self._is_initialized = False
        self.logger.info("Database connector plugin destroyed")
    
    @requires_permission(PermissionType.NETWORK)
    @timeout(30.0)
    async def connect(self, connection_params: Dict[str, Any]) -> bool:
        """
        Establish connection to database (already handled in start).
        
        Args:
            connection_params: Connection parameters (optional, uses config)
            
        Returns:
            True if connected successfully
        """
        if connection_params:
            self.logger.info("Updating connection parameters...")
            self._connection_params.update(connection_params)
            
            # Recreate connection pool with new parameters
            if self._connection_pool:
                await self._close_connection_pool()
            await self._create_connection_pool()
        
        return await self.is_connected()
    
    async def disconnect(self) -> None:
        """Disconnect from database."""
        await self._close_connection_pool()
    
    @cache_result(ttl=10.0)  # Cache for 10 seconds
    async def is_connected(self) -> bool:
        """
        Check if connected to database.
        
        Returns:
            True if connected, False otherwise
        """
        if not self._connection_pool:
            return False
        
        try:
            # Test connection with simple query
            result = await self._execute_query("SELECT 1", fetch_results=False)
            return result.get('success', False)
        except Exception:
            return False
    
    @requires_permission(PermissionType.NETWORK)
    @monitor_performance(include_args=False)
    @validate_input(
        data=lambda x: isinstance(x, dict) and 'query' in x
    )
    async def send_data(self, data: Any) -> bool:
        """
        Send data to database (execute insert/update/delete).
        
        Args:
            data: Dictionary containing 'query' and optional 'parameters'
            
        Returns:
            True if successful, False otherwise
        """
        try:
            query = data['query']
            parameters = data.get('parameters', [])
            
            result = await self._execute_query(query, parameters, fetch_results=False)
            return result.get('success', False)
            
        except Exception as e:
            self.logger.error(f"Failed to send data: {e}")
            return False
    
    @requires_permission(PermissionType.NETWORK)
    @monitor_performance(include_args=False)
    @validate_input(
        query_data=lambda x: isinstance(x, dict) and 'query' in x
    )
    async def receive_data(self) -> Optional[Any]:
        """
        This method is not typically used for database connectors.
        Use execute_query method instead.
        """
        self.logger.warning("receive_data() called on database connector - use execute_query() instead")
        return None
    
    @requires_permission(PermissionType.NETWORK)
    @monitor_performance(include_args=True)
    @log_calls(level=logging.DEBUG, include_args=False, include_result=False)
    @timeout(60.0)
    @retry_on_failure(max_attempts=2, delay=0.5)
    async def execute_query(
        self,
        query: str,
        parameters: List[Any] = None,
        fetch_results: bool = True
    ) -> Dict[str, Any]:
        """
        Execute a database query.
        
        Args:
            query: SQL query to execute
            parameters: Query parameters
            fetch_results: Whether to fetch and return results
            
        Returns:
            Dictionary containing query results and metadata
        """
        return await self._execute_query(query, parameters or [], fetch_results)
    
    @requires_permission(PermissionType.NETWORK)
    @monitor_performance()
    async def execute_transaction(self, queries: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Execute multiple queries in a transaction.
        
        Args:
            queries: List of query dictionaries with 'query' and 'parameters'
            
        Returns:
            Transaction result
        """
        if not self._connection_pool:
            raise RuntimeError("Database not connected")
        
        start_time = time.time()
        
        try:
            # Simulate transaction execution
            await asyncio.sleep(0.2)  # Simulate transaction time
            
            results = []
            for query_data in queries:
                query = query_data['query']
                parameters = query_data.get('parameters', [])
                
                # Execute each query in transaction
                result = await self._execute_query(query, parameters, fetch_results=False)
                results.append(result)
                
                if not result.get('success'):
                    # Simulate transaction rollback
                    raise RuntimeError(f"Query failed: {result.get('error')}")
            
            execution_time = time.time() - start_time
            self._stats['total_query_time'] += execution_time
            self._stats['queries_executed'] += len(queries)
            
            return {
                'success': True,
                'queries_executed': len(queries),
                'execution_time': execution_time,
                'results': results
            }
            
        except Exception as e:
            self._stats['queries_failed'] += len(queries)
            self.logger.error(f"Transaction failed: {e}")
            
            return {
                'success': False,
                'error': str(e),
                'queries_attempted': len(queries)
            }
    
    async def health_check(self) -> PluginHealth:
        """Perform health check on the database connector."""
        try:
            if not await self.is_connected():
                return PluginHealth(
                    is_healthy=False,
                    score=0.0,
                    message="Database connection failed",
                    details={
                        'connection_status': 'disconnected',
                        'pool_status': 'unavailable'
                    }
                )
            
            # Check connection pool health
            pool_health = await self._check_pool_health()
            
            # Calculate health score based on connection pool status
            health_score = min(1.0, pool_health.get('active_connections', 0) / 
                             self._plugin_config.get('pool_size', 10))
            
            return PluginHealth(
                is_healthy=True,
                score=health_score,
                message="Database connector is healthy",
                details={
                    'connection_status': 'connected',
                    'pool_status': 'active',
                    'pool_health': pool_health,
                    'query_stats': {
                        'total_queries': self._stats['queries_executed'],
                        'failed_queries': self._stats['queries_failed'],
                        'avg_query_time': self._get_average_query_time()
                    }
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
        """Get database connector metrics."""
        pool_stats = await self._check_pool_health()
        
        return {
            'connections_created_total': self._stats['connections_created'],
            'connections_closed_total': self._stats['connections_closed'],
            'queries_executed_total': self._stats['queries_executed'],
            'queries_failed_total': self._stats['queries_failed'],
            'query_success_rate': self._get_query_success_rate(),
            'average_query_time_seconds': self._get_average_query_time(),
            'total_query_time_seconds': self._stats['total_query_time'],
            'last_query_timestamp': self._stats['last_query_time'],
            'connection_pool': pool_stats
        }
    
    # Private helper methods
    
    async def _create_connection_pool(self) -> None:
        """Create database connection pool."""
        self.logger.info("Creating database connection pool...")
        
        pool_size = self._plugin_config.get('pool_size', 10)
        
        # Simulate connection pool creation
        await asyncio.sleep(0.5)  # Simulate pool creation time
        
        self._connection_pool = {
            'pool_size': pool_size,
            'active_connections': 0,
            'available_connections': pool_size,
            'created_at': datetime.now()
        }
        
        self._stats['connections_created'] += pool_size
        
        self.logger.info(f"Connection pool created with {pool_size} connections")
    
    async def _close_connection_pool(self) -> None:
        """Close database connection pool."""
        if self._connection_pool:
            self.logger.info("Closing database connection pool...")
            
            active_connections = self._connection_pool.get('active_connections', 0)
            self._stats['connections_closed'] += active_connections
            
            await asyncio.sleep(0.2)  # Simulate cleanup time
            self._connection_pool = None
            
            self.logger.info("Connection pool closed")
    
    async def _execute_query(
        self,
        query: str,
        parameters: List[Any] = None,
        fetch_results: bool = True
    ) -> Dict[str, Any]:
        """Execute a database query (internal implementation)."""
        if not self._connection_pool:
            raise RuntimeError("Database not connected")
        
        start_time = time.time()
        
        try:
            # Simulate query execution
            await asyncio.sleep(0.05)  # Simulate query time
            
            # Determine query type
            query_type = query.strip().upper().split()[0]
            
            # Simulate different query results
            if query_type in ['SELECT', 'SHOW', 'DESCRIBE']:
                if fetch_results:
                    results = self._generate_mock_results(query)
                else:
                    results = []
                
                response = {
                    'success': True,
                    'query_type': query_type,
                    'results': results,
                    'row_count': len(results) if fetch_results else 0
                }
            else:
                # INSERT, UPDATE, DELETE
                affected_rows = 1  # Simulate affected rows
                
                response = {
                    'success': True,
                    'query_type': query_type,
                    'affected_rows': affected_rows
                }
            
            execution_time = time.time() - start_time
            
            # Update statistics
            self._stats['queries_executed'] += 1
            self._stats['total_query_time'] += execution_time
            self._stats['last_query_time'] = datetime.now().isoformat()
            
            response['execution_time'] = execution_time
            
            return response
            
        except Exception as e:
            self._stats['queries_failed'] += 1
            self.logger.error(f"Query execution failed: {e}")
            
            return {
                'success': False,
                'error': str(e),
                'query_type': 'unknown'
            }
    
    def _generate_mock_results(self, query: str) -> List[Dict[str, Any]]:
        """Generate mock query results for demonstration."""
        if 'user' in query.lower():
            return [
                {'id': 1, 'name': 'John Doe', 'email': 'john@example.com'},
                {'id': 2, 'name': 'Jane Smith', 'email': 'jane@example.com'}
            ]
        elif 'product' in query.lower():
            return [
                {'id': 101, 'name': 'Widget A', 'price': 19.99},
                {'id': 102, 'name': 'Widget B', 'price': 29.99}
            ]
        else:
            return [{'result': 'success', 'timestamp': datetime.now().isoformat()}]
    
    async def _check_pool_health(self) -> Dict[str, Any]:
        """Check connection pool health."""
        if not self._connection_pool:
            return {
                'status': 'unavailable',
                'active_connections': 0,
                'available_connections': 0
            }
        
        # Simulate pool health check
        pool_size = self._connection_pool['pool_size']
        active_connections = min(pool_size, self._stats['queries_executed'] % (pool_size + 1))
        
        return {
            'status': 'healthy',
            'pool_size': pool_size,
            'active_connections': active_connections,
            'available_connections': pool_size - active_connections,
            'uptime_seconds': (datetime.now() - self._connection_pool['created_at']).total_seconds()
        }
    
    def _get_query_success_rate(self) -> float:
        """Calculate query success rate."""
        total = self._stats['queries_executed'] + self._stats['queries_failed']
        if total == 0:
            return 1.0
        return self._stats['queries_executed'] / total
    
    def _get_average_query_time(self) -> float:
        """Calculate average query execution time."""
        if self._stats['queries_executed'] == 0:
            return 0.0
        return self._stats['total_query_time'] / self._stats['queries_executed']