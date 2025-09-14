"""
Tenant schema migration and versioning.

Provides comprehensive migration management for multi-tenant applications
including schema creation, data migration, version management, and rollback capabilities.
"""

import logging
import os
import shutil
import tempfile
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import yaml
from alembic import command as alembic_command
from alembic.config import Config as AlembicConfig
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text, MetaData, Table, Column, String, DateTime, Integer, Text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from .tenant_context import get_current_tenant_safe
from .isolation import TenancyModel, TenantIsolationManager

logger = logging.getLogger(__name__)


class MigrationStatus(Enum):
    """Migration execution status."""
    
    PENDING = "pending"
    """Migration is pending execution"""
    
    RUNNING = "running"
    """Migration is currently running"""
    
    COMPLETED = "completed"
    """Migration completed successfully"""
    
    FAILED = "failed"
    """Migration failed"""
    
    ROLLED_BACK = "rolled_back"
    """Migration was rolled back"""


class MigrationScope(Enum):
    """Scope of migration execution."""
    
    SYSTEM = "system"
    """System-wide migration affecting all tenants"""
    
    TENANT = "tenant"
    """Tenant-specific migration"""
    
    SELECTIVE = "selective"
    """Migration applied to selected tenants"""


@dataclass
class MigrationRecord:
    """Record of a migration execution."""
    
    migration_id: str
    version: str
    tenant_id: Optional[str]
    status: MigrationStatus
    scope: MigrationScope
    started_at: datetime
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    rollback_data: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def duration(self) -> Optional[float]:
        """Get migration duration in seconds."""
        if self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None
    
    @property
    def is_successful(self) -> bool:
        """Check if migration was successful."""
        return self.status == MigrationStatus.COMPLETED


@dataclass
class MigrationDefinition:
    """Definition of a migration operation."""
    
    id: str
    version: str
    name: str
    description: str
    scope: MigrationScope
    dependencies: List[str] = field(default_factory=list)
    sql_up: Optional[str] = None
    sql_down: Optional[str] = None
    python_up: Optional[str] = None
    python_down: Optional[str] = None
    tenant_filter: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_file(cls, file_path: Path) -> 'MigrationDefinition':
        """Load migration definition from YAML file."""
        with open(file_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        return cls(**data)
    
    def to_file(self, file_path: Path) -> None:
        """Save migration definition to YAML file."""
        with open(file_path, 'w', encoding='utf-8') as f:
            yaml.dump(asdict(self), f, default_flow_style=False)


class MigrationError(Exception):
    """Base exception for migration errors."""
    pass


class MigrationExecutionError(MigrationError):
    """Exception raised during migration execution."""
    pass


class MigrationValidationError(MigrationError):
    """Exception raised during migration validation."""
    pass


class TenantMigrationStrategy(ABC):
    """Abstract base class for tenant migration strategies."""
    
    @abstractmethod
    def execute_migration(self, migration: MigrationDefinition, tenant_id: Optional[str] = None) -> MigrationRecord:
        """Execute a migration for a tenant."""
        pass
    
    @abstractmethod
    def rollback_migration(self, migration: MigrationDefinition, tenant_id: Optional[str] = None) -> bool:
        """Rollback a migration for a tenant."""
        pass
    
    @abstractmethod
    def validate_migration(self, migration: MigrationDefinition, tenant_id: Optional[str] = None) -> bool:
        """Validate a migration before execution."""
        pass


class SQLMigrationStrategy(TenantMigrationStrategy):
    """Migration strategy for executing SQL-based migrations."""
    
    def __init__(self, isolation_manager: TenantIsolationManager):
        self.isolation_manager = isolation_manager
    
    def execute_migration(self, migration: MigrationDefinition, tenant_id: Optional[str] = None) -> MigrationRecord:
        """Execute SQL migration."""
        record = MigrationRecord(
            migration_id=migration.id,
            version=migration.version,
            tenant_id=tenant_id,
            status=MigrationStatus.RUNNING,
            scope=migration.scope,
            started_at=datetime.utcnow()
        )
        
        try:
            session = self.isolation_manager.get_session(tenant_id)
            
            if migration.sql_up:
                # Execute SQL migration
                statements = self._parse_sql_statements(migration.sql_up)
                
                for statement in statements:
                    if statement.strip():
                        session.execute(text(statement))
                
                session.commit()
            
            record.status = MigrationStatus.COMPLETED
            record.completed_at = datetime.utcnow()
            
        except Exception as e:
            record.status = MigrationStatus.FAILED
            record.error_message = str(e)
            record.completed_at = datetime.utcnow()
            logger.error(f"Migration {migration.id} failed for tenant {tenant_id}: {e}")
            raise MigrationExecutionError(f"Migration failed: {e}") from e
        
        finally:
            session.close()
        
        return record
    
    def rollback_migration(self, migration: MigrationDefinition, tenant_id: Optional[str] = None) -> bool:
        """Rollback SQL migration."""
        try:
            session = self.isolation_manager.get_session(tenant_id)
            
            if migration.sql_down:
                # Execute rollback SQL
                statements = self._parse_sql_statements(migration.sql_down)
                
                for statement in statements:
                    if statement.strip():
                        session.execute(text(statement))
                
                session.commit()
                return True
            
        except Exception as e:
            logger.error(f"Migration rollback {migration.id} failed for tenant {tenant_id}: {e}")
            return False
        
        finally:
            session.close()
        
        return False
    
    def validate_migration(self, migration: MigrationDefinition, tenant_id: Optional[str] = None) -> bool:
        """Validate SQL migration."""
        if not migration.sql_up:
            return False
        
        try:
            # Basic SQL syntax validation
            statements = self._parse_sql_statements(migration.sql_up)
            
            # Check for dangerous operations
            dangerous_keywords = ['DROP DATABASE', 'DROP SCHEMA', 'TRUNCATE']
            for statement in statements:
                for keyword in dangerous_keywords:
                    if keyword in statement.upper():
                        logger.warning(f"Potentially dangerous operation in migration {migration.id}: {keyword}")
            
            return True
        
        except Exception as e:
            logger.error(f"Migration validation failed for {migration.id}: {e}")
            return False
    
    def _parse_sql_statements(self, sql: str) -> List[str]:
        """Parse SQL script into individual statements."""
        # Simple statement splitting (could be enhanced for complex cases)
        statements = []
        current_statement = ""
        
        for line in sql.split('\n'):
            line = line.strip()
            
            # Skip comments
            if line.startswith('--') or line.startswith('#'):
                continue
            
            current_statement += line + '\n'
            
            # Check for statement terminator
            if line.endswith(';'):
                statements.append(current_statement.strip())
                current_statement = ""
        
        # Add final statement if it doesn't end with semicolon
        if current_statement.strip():
            statements.append(current_statement.strip())
        
        return statements


class PythonMigrationStrategy(TenantMigrationStrategy):
    """Migration strategy for executing Python-based migrations."""
    
    def __init__(self, isolation_manager: TenantIsolationManager):
        self.isolation_manager = isolation_manager
    
    def execute_migration(self, migration: MigrationDefinition, tenant_id: Optional[str] = None) -> MigrationRecord:
        """Execute Python migration."""
        record = MigrationRecord(
            migration_id=migration.id,
            version=migration.version,
            tenant_id=tenant_id,
            status=MigrationStatus.RUNNING,
            scope=migration.scope,
            started_at=datetime.utcnow()
        )
        
        try:
            if migration.python_up:
                # Execute Python migration
                session = self.isolation_manager.get_session(tenant_id)
                
                # Create execution context
                context = {
                    'session': session,
                    'tenant_id': tenant_id,
                    'migration': migration,
                    'engine': session.bind,
                    'logger': logger
                }
                
                # Execute migration code
                exec(migration.python_up, context)
                
                session.commit()
                session.close()
            
            record.status = MigrationStatus.COMPLETED
            record.completed_at = datetime.utcnow()
            
        except Exception as e:
            record.status = MigrationStatus.FAILED
            record.error_message = str(e)
            record.completed_at = datetime.utcnow()
            logger.error(f"Python migration {migration.id} failed for tenant {tenant_id}: {e}")
            raise MigrationExecutionError(f"Migration failed: {e}") from e
        
        return record
    
    def rollback_migration(self, migration: MigrationDefinition, tenant_id: Optional[str] = None) -> bool:
        """Rollback Python migration."""
        try:
            if migration.python_down:
                session = self.isolation_manager.get_session(tenant_id)
                
                # Create execution context
                context = {
                    'session': session,
                    'tenant_id': tenant_id,
                    'migration': migration,
                    'engine': session.bind,
                    'logger': logger
                }
                
                # Execute rollback code
                exec(migration.python_down, context)
                
                session.commit()
                session.close()
                return True
            
        except Exception as e:
            logger.error(f"Python migration rollback {migration.id} failed for tenant {tenant_id}: {e}")
            return False
        
        return False
    
    def validate_migration(self, migration: MigrationDefinition, tenant_id: Optional[str] = None) -> bool:
        """Validate Python migration."""
        if not migration.python_up:
            return False
        
        try:
            # Basic syntax validation
            compile(migration.python_up, f'<migration-{migration.id}>', 'exec')
            
            if migration.python_down:
                compile(migration.python_down, f'<migration-{migration.id}-down>', 'exec')
            
            return True
        
        except SyntaxError as e:
            logger.error(f"Python migration syntax error in {migration.id}: {e}")
            return False


class TenantSchemaManager:
    """
    Manager for tenant schema operations.
    
    Handles schema creation, modification, and tenant onboarding.
    """
    
    def __init__(self, isolation_manager: TenantIsolationManager, base_metadata: MetaData):
        self.isolation_manager = isolation_manager
        self.base_metadata = base_metadata
    
    def create_tenant_schema(self, tenant_id: str, template_schema: Optional[str] = None) -> bool:
        """
        Create schema for a new tenant.
        
        Args:
            tenant_id: The tenant identifier
            template_schema: Template schema to copy from
            
        Returns:
            bool: True if schema was created successfully
        """
        try:
            strategy = self.isolation_manager.strategy
            
            if hasattr(strategy, 'create_tenant_schema'):
                strategy.create_tenant_schema(tenant_id)
            
            # Create tables in the new schema
            session = self.isolation_manager.get_session(tenant_id)
            engine = session.bind
            
            # Create all tables
            self.base_metadata.create_all(engine)
            
            # Copy template data if specified
            if template_schema:
                self._copy_template_data(tenant_id, template_schema)
            
            session.close()
            logger.info(f"Created schema for tenant {tenant_id}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to create schema for tenant {tenant_id}: {e}")
            return False
    
    def drop_tenant_schema(self, tenant_id: str, backup: bool = True) -> bool:
        """
        Drop schema for a tenant.
        
        Args:
            tenant_id: The tenant identifier
            backup: Whether to create a backup before dropping
            
        Returns:
            bool: True if schema was dropped successfully
        """
        try:
            if backup:
                self.backup_tenant_data(tenant_id)
            
            strategy = self.isolation_manager.strategy
            
            if hasattr(strategy, 'drop_tenant_schema'):
                strategy.drop_tenant_schema(tenant_id, cascade=True)
            
            logger.info(f"Dropped schema for tenant {tenant_id}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to drop schema for tenant {tenant_id}: {e}")
            return False
    
    def backup_tenant_data(self, tenant_id: str, backup_path: Optional[Path] = None) -> Optional[Path]:
        """
        Create backup of tenant data.
        
        Args:
            tenant_id: The tenant identifier
            backup_path: Path to store backup (auto-generated if None)
            
        Returns:
            Optional[Path]: Path to backup file or None if failed
        """
        try:
            if backup_path is None:
                backup_dir = Path("backups") / tenant_id
                backup_dir.mkdir(parents=True, exist_ok=True)
                backup_path = backup_dir / f"backup_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.sql"
            
            session = self.isolation_manager.get_session(tenant_id)
            engine = session.bind
            
            # Get all table names
            inspector = inspect(engine)
            tables = inspector.get_table_names()
            
            with open(backup_path, 'w', encoding='utf-8') as f:
                f.write(f"-- Backup for tenant {tenant_id} created at {datetime.utcnow()}\n\n")
                
                for table_name in tables:
                    # Export table structure and data
                    f.write(f"-- Table: {table_name}\n")
                    
                    # Get table data
                    result = session.execute(text(f"SELECT * FROM {table_name}"))
                    rows = result.fetchall()
                    
                    if rows:
                        columns = result.keys()
                        f.write(f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES\n")
                        
                        for i, row in enumerate(rows):
                            values = []
                            for value in row:
                                if value is None:
                                    values.append('NULL')
                                elif isinstance(value, str):
                                    values.append(f"'{value.replace(\"'\", \"''\")}'")
                                else:
                                    values.append(str(value))
                            
                            f.write(f"  ({', '.join(values)})")
                            
                            if i < len(rows) - 1:
                                f.write(",\n")
                            else:
                                f.write(";\n\n")
            
            session.close()
            logger.info(f"Created backup for tenant {tenant_id} at {backup_path}")
            return backup_path
        
        except Exception as e:
            logger.error(f"Failed to backup tenant {tenant_id}: {e}")
            return None
    
    def restore_tenant_data(self, tenant_id: str, backup_path: Path) -> bool:
        """
        Restore tenant data from backup.
        
        Args:
            tenant_id: The tenant identifier
            backup_path: Path to backup file
            
        Returns:
            bool: True if restore was successful
        """
        try:
            session = self.isolation_manager.get_session(tenant_id)
            
            with open(backup_path, 'r', encoding='utf-8') as f:
                sql_content = f.read()
            
            # Execute backup SQL
            statements = sql_content.split(';')
            for statement in statements:
                statement = statement.strip()
                if statement and not statement.startswith('--'):
                    session.execute(text(statement))
            
            session.commit()
            session.close()
            
            logger.info(f"Restored data for tenant {tenant_id} from {backup_path}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to restore tenant {tenant_id} from {backup_path}: {e}")
            return False
    
    def _copy_template_data(self, tenant_id: str, template_schema: str):
        """Copy data from template schema to new tenant schema."""
        # Implementation depends on the specific tenancy model
        # This is a placeholder for template data copying logic
        pass


class TenantMigrationManager:
    """
    Main manager for tenant migrations.
    
    Provides comprehensive migration management including execution,
    rollback, versioning, and coordination across multiple tenants.
    """
    
    def __init__(self, 
                 isolation_manager: TenantIsolationManager,
                 migration_dir: Union[str, Path],
                 alembic_config_path: Optional[Union[str, Path]] = None):
        """
        Initialize tenant migration manager.
        
        Args:
            isolation_manager: Tenant isolation manager
            migration_dir: Directory containing migration files
            alembic_config_path: Path to Alembic configuration file
        """
        self.isolation_manager = isolation_manager
        self.migration_dir = Path(migration_dir)
        self.alembic_config_path = Path(alembic_config_path) if alembic_config_path else None
        
        # Migration strategies
        self.strategies = {
            'sql': SQLMigrationStrategy(isolation_manager),
            'python': PythonMigrationStrategy(isolation_manager)
        }
        
        # Migration tracking
        self.migration_records: List[MigrationRecord] = []
        
        # Ensure migration directory exists
        self.migration_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize migration tracking table
        self._initialize_migration_tracking()
    
    def _initialize_migration_tracking(self):
        """Initialize migration tracking table."""
        try:
            session = self.isolation_manager.get_session()
            engine = session.bind
            
            # Create migration tracking table if it doesn't exist
            metadata = MetaData()
            migration_table = Table(
                'tenant_migration_history',
                metadata,
                Column('id', Integer, primary_key=True),
                Column('migration_id', String(100), nullable=False),
                Column('version', String(50), nullable=False),
                Column('tenant_id', String(100)),
                Column('status', String(20), nullable=False),
                Column('scope', String(20), nullable=False),
                Column('started_at', DateTime, nullable=False),
                Column('completed_at', DateTime),
                Column('error_message', Text),
                Column('rollback_data', Text),
                Column('metadata', Text)
            )
            
            metadata.create_all(engine)
            session.close()
            
        except Exception as e:
            logger.error(f"Failed to initialize migration tracking: {e}")
    
    def load_migrations(self) -> List[MigrationDefinition]:
        """Load all migration definitions from the migration directory."""
        migrations = []
        
        for migration_file in self.migration_dir.glob("*.yaml"):
            try:
                migration = MigrationDefinition.from_file(migration_file)
                migrations.append(migration)
            except Exception as e:
                logger.error(f"Failed to load migration from {migration_file}: {e}")
        
        # Sort by version
        migrations.sort(key=lambda m: m.version)
        
        return migrations
    
    def get_pending_migrations(self, tenant_id: Optional[str] = None) -> List[MigrationDefinition]:
        """Get list of pending migrations for a tenant."""
        all_migrations = self.load_migrations()
        applied_migrations = self._get_applied_migrations(tenant_id)
        
        pending = []
        for migration in all_migrations:
            if migration.id not in applied_migrations:
                # Check if this migration applies to the tenant
                if self._migration_applies_to_tenant(migration, tenant_id):
                    pending.append(migration)
        
        return pending
    
    def execute_migration(self, migration_id: str, tenant_id: Optional[str] = None) -> MigrationRecord:
        """
        Execute a specific migration.
        
        Args:
            migration_id: The migration identifier
            tenant_id: Specific tenant ID (None for system-wide)
            
        Returns:
            MigrationRecord: Migration execution record
        """
        # Load migration definition
        migration = self._load_migration(migration_id)
        if not migration:
            raise MigrationError(f"Migration not found: {migration_id}")
        
        # Validate migration
        strategy = self._get_strategy(migration)
        if not strategy.validate_migration(migration, tenant_id):
            raise MigrationValidationError(f"Migration validation failed: {migration_id}")
        
        # Check dependencies
        self._check_dependencies(migration, tenant_id)
        
        # Execute migration
        record = strategy.execute_migration(migration, tenant_id)
        
        # Save migration record
        self._save_migration_record(record)
        self.migration_records.append(record)
        
        return record
    
    def execute_pending_migrations(self, tenant_id: Optional[str] = None) -> List[MigrationRecord]:
        """
        Execute all pending migrations for a tenant.
        
        Args:
            tenant_id: Specific tenant ID (None for system-wide)
            
        Returns:
            List[MigrationRecord]: List of migration execution records
        """
        pending_migrations = self.get_pending_migrations(tenant_id)
        records = []
        
        for migration in pending_migrations:
            try:
                record = self.execute_migration(migration.id, tenant_id)
                records.append(record)
                
                if record.status == MigrationStatus.FAILED:
                    logger.error(f"Migration {migration.id} failed, stopping execution")
                    break
                    
            except Exception as e:
                logger.error(f"Failed to execute migration {migration.id}: {e}")
                break
        
        return records
    
    def rollback_migration(self, migration_id: str, tenant_id: Optional[str] = None) -> bool:
        """
        Rollback a specific migration.
        
        Args:
            migration_id: The migration identifier
            tenant_id: Specific tenant ID (None for system-wide)
            
        Returns:
            bool: True if rollback was successful
        """
        # Load migration definition
        migration = self._load_migration(migration_id)
        if not migration:
            raise MigrationError(f"Migration not found: {migration_id}")
        
        # Execute rollback
        strategy = self._get_strategy(migration)
        success = strategy.rollback_migration(migration, tenant_id)
        
        if success:
            # Update migration record
            self._update_migration_status(migration_id, tenant_id, MigrationStatus.ROLLED_BACK)
        
        return success
    
    def migrate_all_tenants(self, tenant_ids: Optional[List[str]] = None) -> Dict[str, List[MigrationRecord]]:
        """
        Execute pending migrations for multiple tenants.
        
        Args:
            tenant_ids: List of tenant IDs (None for all tenants)
            
        Returns:
            Dict[str, List[MigrationRecord]]: Migration records by tenant ID
        """
        if tenant_ids is None:
            # Get all tenant IDs (implementation depends on your tenant management)
            tenant_ids = self._get_all_tenant_ids()
        
        results = {}
        
        for tenant_id in tenant_ids:
            try:
                records = self.execute_pending_migrations(tenant_id)
                results[tenant_id] = records
            except Exception as e:
                logger.error(f"Failed to migrate tenant {tenant_id}: {e}")
                results[tenant_id] = []
        
        return results
    
    def get_migration_status(self, tenant_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get migration status for a tenant.
        
        Args:
            tenant_id: Specific tenant ID (None for system-wide)
            
        Returns:
            Dict[str, Any]: Migration status information
        """
        all_migrations = self.load_migrations()
        applied_migrations = self._get_applied_migrations(tenant_id)
        pending_migrations = self.get_pending_migrations(tenant_id)
        
        return {
            'tenant_id': tenant_id,
            'total_migrations': len(all_migrations),
            'applied_migrations': len(applied_migrations),
            'pending_migrations': len(pending_migrations),
            'migration_details': {
                'applied': list(applied_migrations.keys()),
                'pending': [m.id for m in pending_migrations]
            }
        }
    
    def create_migration(self, 
                        name: str,
                        description: str,
                        scope: MigrationScope = MigrationScope.SYSTEM,
                        sql_up: Optional[str] = None,
                        sql_down: Optional[str] = None) -> MigrationDefinition:
        """
        Create a new migration definition.
        
        Args:
            name: Migration name
            description: Migration description
            scope: Migration scope
            sql_up: SQL for migration
            sql_down: SQL for rollback
            
        Returns:
            MigrationDefinition: Created migration definition
        """
        # Generate migration ID and version
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        migration_id = f"{timestamp}_{name.lower().replace(' ', '_')}"
        version = timestamp
        
        migration = MigrationDefinition(
            id=migration_id,
            version=version,
            name=name,
            description=description,
            scope=scope,
            sql_up=sql_up,
            sql_down=sql_down
        )
        
        # Save to file
        migration_file = self.migration_dir / f"{migration_id}.yaml"
        migration.to_file(migration_file)
        
        logger.info(f"Created migration {migration_id}")
        return migration
    
    def _load_migration(self, migration_id: str) -> Optional[MigrationDefinition]:
        """Load a specific migration definition."""
        migration_file = self.migration_dir / f"{migration_id}.yaml"
        
        if migration_file.exists():
            return MigrationDefinition.from_file(migration_file)
        
        return None
    
    def _get_strategy(self, migration: MigrationDefinition) -> TenantMigrationStrategy:
        """Get the appropriate migration strategy."""
        if migration.sql_up or migration.sql_down:
            return self.strategies['sql']
        elif migration.python_up or migration.python_down:
            return self.strategies['python']
        else:
            raise MigrationError(f"No valid migration strategy for {migration.id}")
    
    def _migration_applies_to_tenant(self, migration: MigrationDefinition, tenant_id: Optional[str]) -> bool:
        """Check if a migration applies to a specific tenant."""
        if migration.scope == MigrationScope.SYSTEM:
            return True
        elif migration.scope == MigrationScope.TENANT and tenant_id:
            return True
        elif migration.scope == MigrationScope.SELECTIVE:
            # Check tenant filter
            if migration.tenant_filter and tenant_id:
                # Simple implementation - could be enhanced with more complex filtering
                return tenant_id in migration.tenant_filter.split(',')
            return False
        
        return False
    
    def _check_dependencies(self, migration: MigrationDefinition, tenant_id: Optional[str]):
        """Check if migration dependencies are satisfied."""
        applied_migrations = self._get_applied_migrations(tenant_id)
        
        for dependency in migration.dependencies:
            if dependency not in applied_migrations:
                raise MigrationError(f"Migration dependency not satisfied: {dependency}")
    
    def _get_applied_migrations(self, tenant_id: Optional[str]) -> Dict[str, MigrationRecord]:
        """Get applied migrations for a tenant."""
        try:
            session = self.isolation_manager.get_session()
            
            query = text("""
                SELECT migration_id, version, status, started_at, completed_at, error_message
                FROM tenant_migration_history 
                WHERE (tenant_id = :tenant_id OR (tenant_id IS NULL AND :tenant_id IS NULL))
                AND status = 'completed'
            """)
            
            result = session.execute(query, {'tenant_id': tenant_id})
            
            applied = {}
            for row in result:
                record = MigrationRecord(
                    migration_id=row.migration_id,
                    version=row.version,
                    tenant_id=tenant_id,
                    status=MigrationStatus(row.status),
                    scope=MigrationScope.SYSTEM,  # Would need to store this
                    started_at=row.started_at,
                    completed_at=row.completed_at,
                    error_message=row.error_message
                )
                applied[row.migration_id] = record
            
            session.close()
            return applied
        
        except Exception as e:
            logger.error(f"Failed to get applied migrations: {e}")
            return {}
    
    def _save_migration_record(self, record: MigrationRecord):
        """Save migration record to database."""
        try:
            session = self.isolation_manager.get_session()
            
            query = text("""
                INSERT INTO tenant_migration_history 
                (migration_id, version, tenant_id, status, scope, started_at, completed_at, error_message)
                VALUES (:migration_id, :version, :tenant_id, :status, :scope, :started_at, :completed_at, :error_message)
            """)
            
            session.execute(query, {
                'migration_id': record.migration_id,
                'version': record.version,
                'tenant_id': record.tenant_id,
                'status': record.status.value,
                'scope': record.scope.value,
                'started_at': record.started_at,
                'completed_at': record.completed_at,
                'error_message': record.error_message
            })
            
            session.commit()
            session.close()
        
        except Exception as e:
            logger.error(f"Failed to save migration record: {e}")
    
    def _update_migration_status(self, migration_id: str, tenant_id: Optional[str], status: MigrationStatus):
        """Update migration status in database."""
        try:
            session = self.isolation_manager.get_session()
            
            query = text("""
                UPDATE tenant_migration_history 
                SET status = :status, completed_at = :completed_at
                WHERE migration_id = :migration_id 
                AND (tenant_id = :tenant_id OR (tenant_id IS NULL AND :tenant_id IS NULL))
            """)
            
            session.execute(query, {
                'migration_id': migration_id,
                'tenant_id': tenant_id,
                'status': status.value,
                'completed_at': datetime.utcnow()
            })
            
            session.commit()
            session.close()
        
        except Exception as e:
            logger.error(f"Failed to update migration status: {e}")
    
    def _get_all_tenant_ids(self) -> List[str]:
        """Get all tenant IDs (implementation depends on your tenant management)."""
        # This is a placeholder implementation
        # In a real application, you would query your tenant table
        return []


def migrate_tenant(tenant_id: str, migration_manager: TenantMigrationManager) -> List[MigrationRecord]:
    """
    Convenience function to migrate a specific tenant.
    
    Args:
        tenant_id: The tenant identifier
        migration_manager: Migration manager instance
        
    Returns:
        List[MigrationRecord]: Migration execution records
    """
    return migration_manager.execute_pending_migrations(tenant_id)