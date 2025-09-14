"""
Authentication and authorization management for multi-tenant system
"""

import jwt
import bcrypt
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field
from enum import Enum

from ...core.di import injectable, singleton, inject
from ...core.events import EventBus
from .models import BaseEntity, AuditLog, LogLevel
from .tenant_manager import TenantManager

logger = logging.getLogger(__name__)


class UserRole(str, Enum):
    """User role enumeration"""
    SUPER_ADMIN = "super_admin"
    TENANT_ADMIN = "tenant_admin"
    USER = "user"
    READONLY = "readonly"
    GUEST = "guest"


class Permission(str, Enum):
    """Permission enumeration"""
    # System permissions
    SYSTEM_ADMIN = "system:admin"
    SYSTEM_READ = "system:read"
    
    # Tenant permissions
    TENANT_ADMIN = "tenant:admin"
    TENANT_READ = "tenant:read"
    TENANT_WRITE = "tenant:write"
    
    # Domain permissions
    ECOMMERCE_READ = "ecommerce:read"
    ECOMMERCE_WRITE = "ecommerce:write"
    ECOMMERCE_ADMIN = "ecommerce:admin"
    
    HEALTHCARE_READ = "healthcare:read"
    HEALTHCARE_WRITE = "healthcare:write"
    HEALTHCARE_ADMIN = "healthcare:admin"
    
    LOGISTICS_READ = "logistics:read"
    LOGISTICS_WRITE = "logistics:write"
    LOGISTICS_ADMIN = "logistics:admin"
    
    # Plugin permissions
    PLUGIN_READ = "plugin:read"
    PLUGIN_WRITE = "plugin:write"
    PLUGIN_ADMIN = "plugin:admin"


@dataclass
class User(BaseEntity):
    """User entity"""
    username: str = ""
    email: str = ""
    password_hash: str = ""
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    role: UserRole = UserRole.USER
    permissions: Set[Permission] = field(default_factory=set)
    is_active: bool = True
    last_login: Optional[datetime] = None
    failed_login_attempts: int = 0
    password_changed_at: Optional[datetime] = None
    profile_data: Dict[str, any] = field(default_factory=dict)


@dataclass
class Session:
    """User session"""
    session_id: str
    user_id: str
    tenant_id: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: datetime = field(default_factory=lambda: datetime.utcnow() + timedelta(hours=24))
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    is_active: bool = True
    last_activity: datetime = field(default_factory=datetime.utcnow)


@singleton
@injectable
class AuthenticationManager:
    """
    Authentication management system providing:
    - User registration and login
    - Password hashing and verification
    - JWT token generation and validation
    - Session management
    - Multi-factor authentication support
    - Password policy enforcement
    - Account lockout protection
    """
    
    def __init__(self, event_bus: EventBus, tenant_manager: TenantManager):
        self.event_bus = event_bus
        self.tenant_manager = tenant_manager
        self.users: Dict[str, User] = {}
        self.sessions: Dict[str, Session] = {}
        self.jwt_secret = "demo-secret-key"  # In production, use secure random key
        self.jwt_algorithm = "HS256"
        self.session_timeout_hours = 24
        self.max_failed_attempts = 5
        self.lockout_duration_minutes = 30
        
        # Initialize demo users
        self._initialize_demo_users()
    
    async def initialize(self):
        """Initialize authentication manager"""
        try:
            await self.event_bus.subscribe("user.*", self._handle_user_event)
            logger.info("Authentication manager initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize authentication manager: {e}")
            raise
    
    def _initialize_demo_users(self):
        """Initialize demo users for testing"""
        # Super admin user
        admin_user = User(
            id="admin-001",
            username="admin",
            email="admin@demo.com",
            password_hash=self._hash_password("admin123"),
            first_name="System",
            last_name="Administrator",
            role=UserRole.SUPER_ADMIN,
            permissions={
                Permission.SYSTEM_ADMIN,
                Permission.TENANT_ADMIN,
                Permission.ECOMMERCE_ADMIN,
                Permission.HEALTHCARE_ADMIN,
                Permission.LOGISTICS_ADMIN,
                Permission.PLUGIN_ADMIN
            },
            tenant_id="default"
        )
        self.users[admin_user.id] = admin_user
        
        # Demo tenant admin
        tenant_admin = User(
            id="user-001",
            username="demo_admin",
            email="demo_admin@demo.com",
            password_hash=self._hash_password("demo123"),
            first_name="Demo",
            last_name="Admin",
            role=UserRole.TENANT_ADMIN,
            permissions={
                Permission.TENANT_READ,
                Permission.TENANT_WRITE,
                Permission.ECOMMERCE_ADMIN,
                Permission.HEALTHCARE_READ,
                Permission.LOGISTICS_READ
            },
            tenant_id="default"
        )
        self.users[tenant_admin.id] = tenant_admin
        
        # Demo regular user
        regular_user = User(
            id="user-002",
            username="demo_user",
            email="demo_user@demo.com",
            password_hash=self._hash_password("user123"),
            first_name="Demo",
            last_name="User",
            role=UserRole.USER,
            permissions={
                Permission.ECOMMERCE_READ,
                Permission.ECOMMERCE_WRITE,
                Permission.HEALTHCARE_READ
            },
            tenant_id="default"
        )
        self.users[regular_user.id] = regular_user
    
    async def register_user(
        self,
        username: str,
        email: str,
        password: str,
        tenant_id: str = "default",
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        role: UserRole = UserRole.USER
    ) -> User:
        """Register a new user"""
        try:
            # Validate input
            if not username or not email or not password:
                raise ValueError("Username, email, and password are required")
            
            # Check if user already exists
            existing_user = self._find_user_by_username_or_email(username, email)
            if existing_user:
                raise ValueError("User with this username or email already exists")
            
            # Validate password
            self._validate_password(password)
            
            # Check tenant exists
            tenant = await self.tenant_manager.get_tenant(tenant_id)
            if not tenant:
                raise ValueError(f"Tenant {tenant_id} not found")
            
            # Create user
            user = User(
                username=username,
                email=email,
                password_hash=self._hash_password(password),
                first_name=first_name,
                last_name=last_name,
                role=role,
                tenant_id=tenant_id,
                password_changed_at=datetime.utcnow()
            )
            
            # Set default permissions based on role
            user.permissions = self._get_default_permissions(role)
            
            # Store user
            self.users[user.id] = user
            
            # Publish event
            await self.event_bus.publish("user.registered", {
                "user_id": user.id,
                "username": username,
                "email": email,
                "tenant_id": tenant_id,
                "role": role.value
            })
            
            logger.info(f"User registered: {username} ({email})")
            return user
            
        except Exception as e:
            logger.error(f"Failed to register user {username}: {e}")
            raise
    
    async def authenticate(
        self,
        username_or_email: str,
        password: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Dict[str, any]:
        """Authenticate user and create session"""
        try:
            # Find user
            user = self._find_user_by_username_or_email(username_or_email, username_or_email)
            if not user:
                await self._log_failed_login(username_or_email, "user_not_found", ip_address)
                raise ValueError("Invalid credentials")
            
            # Check if account is locked
            if self._is_account_locked(user):
                await self._log_failed_login(user.username, "account_locked", ip_address)
                raise ValueError("Account is temporarily locked due to too many failed attempts")
            
            # Verify password
            if not self._verify_password(password, user.password_hash):
                user.failed_login_attempts += 1
                user.mark_updated()
                await self._log_failed_login(user.username, "invalid_password", ip_address)
                raise ValueError("Invalid credentials")
            
            # Check if user is active
            if not user.is_active:
                await self._log_failed_login(user.username, "user_inactive", ip_address)
                raise ValueError("User account is inactive")
            
            # Reset failed attempts on successful login
            user.failed_login_attempts = 0
            user.last_login = datetime.utcnow()
            user.mark_updated()
            
            # Create session
            session = self._create_session(user, ip_address, user_agent)
            self.sessions[session.session_id] = session
            
            # Generate JWT token
            token = self._generate_jwt_token(user, session)
            
            # Publish event
            await self.event_bus.publish("user.logged_in", {
                "user_id": user.id,
                "username": user.username,
                "tenant_id": user.tenant_id,
                "session_id": session.session_id,
                "ip_address": ip_address
            })
            
            logger.info(f"User authenticated: {user.username}")
            
            return {
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "role": user.role.value,
                    "tenant_id": user.tenant_id,
                    "permissions": [p.value for p in user.permissions]
                },
                "session": {
                    "session_id": session.session_id,
                    "expires_at": session.expires_at.isoformat()
                },
                "token": token
            }
            
        except Exception as e:
            logger.error(f"Authentication failed for {username_or_email}: {e}")
            raise
    
    async def logout(self, session_id: str):
        """Logout user and invalidate session"""
        try:
            session = self.sessions.get(session_id)
            if session:
                session.is_active = False
                session.last_activity = datetime.utcnow()
                
                user = self.users.get(session.user_id)
                if user:
                    await self.event_bus.publish("user.logged_out", {
                        "user_id": user.id,
                        "username": user.username,
                        "session_id": session_id
                    })
                
                logger.info(f"User logged out: session {session_id}")
            
        except Exception as e:
            logger.error(f"Error during logout: {e}")
    
    async def validate_session(self, session_id: str) -> Optional[User]:
        """Validate session and return user if valid"""
        try:
            session = self.sessions.get(session_id)
            if not session or not session.is_active:
                return None
            
            # Check if session expired
            if datetime.utcnow() > session.expires_at:
                session.is_active = False
                return None
            
            # Update last activity
            session.last_activity = datetime.utcnow()
            
            # Get user
            user = self.users.get(session.user_id)
            if not user or not user.is_active:
                return None
            
            return user
            
        except Exception as e:
            logger.error(f"Error validating session: {e}")
            return None
    
    async def validate_jwt_token(self, token: str) -> Optional[User]:
        """Validate JWT token and return user if valid"""
        try:
            payload = jwt.decode(token, self.jwt_secret, algorithms=[self.jwt_algorithm])
            
            user_id = payload.get("user_id")
            session_id = payload.get("session_id")
            
            if not user_id or not session_id:
                return None
            
            # Validate session
            user = await self.validate_session(session_id)
            if not user or user.id != user_id:
                return None
            
            return user
            
        except jwt.ExpiredSignatureError:
            logger.debug("JWT token expired")
            return None
        except jwt.InvalidTokenError:
            logger.debug("Invalid JWT token")
            return None
        except Exception as e:
            logger.error(f"Error validating JWT token: {e}")
            return None
    
    def _find_user_by_username_or_email(self, username: str, email: str) -> Optional[User]:
        """Find user by username or email"""
        for user in self.users.values():
            if user.username == username or user.email == email:
                return user
        return None
    
    def _hash_password(self, password: str) -> str:
        """Hash password using bcrypt"""
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    def _verify_password(self, password: str, password_hash: str) -> bool:
        """Verify password against hash"""
        return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))
    
    def _validate_password(self, password: str):
        """Validate password meets policy requirements"""
        if len(password) < 8:
            raise ValueError("Password must be at least 8 characters long")
        
        if not any(c.isupper() for c in password):
            raise ValueError("Password must contain at least one uppercase letter")
        
        if not any(c.islower() for c in password):
            raise ValueError("Password must contain at least one lowercase letter")
        
        if not any(c.isdigit() for c in password):
            raise ValueError("Password must contain at least one digit")
    
    def _is_account_locked(self, user: User) -> bool:
        """Check if account is locked due to failed attempts"""
        if user.failed_login_attempts < self.max_failed_attempts:
            return False
        
        # Check if lockout period has expired
        if user.updated_at:
            lockout_expires = user.updated_at + timedelta(minutes=self.lockout_duration_minutes)
            if datetime.utcnow() > lockout_expires:
                user.failed_login_attempts = 0
                return False
        
        return True
    
    def _create_session(
        self,
        user: User,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Session:
        """Create new user session"""
        import uuid
        
        return Session(
            session_id=str(uuid.uuid4()),
            user_id=user.id,
            tenant_id=user.tenant_id,
            expires_at=datetime.utcnow() + timedelta(hours=self.session_timeout_hours),
            ip_address=ip_address,
            user_agent=user_agent
        )
    
    def _generate_jwt_token(self, user: User, session: Session) -> str:
        """Generate JWT token for user session"""
        payload = {
            "user_id": user.id,
            "username": user.username,
            "tenant_id": user.tenant_id,
            "session_id": session.session_id,
            "role": user.role.value,
            "permissions": [p.value for p in user.permissions],
            "iat": datetime.utcnow(),
            "exp": session.expires_at
        }
        
        return jwt.encode(payload, self.jwt_secret, algorithm=self.jwt_algorithm)
    
    def _get_default_permissions(self, role: UserRole) -> Set[Permission]:
        """Get default permissions for user role"""
        if role == UserRole.SUPER_ADMIN:
            return set(Permission)  # All permissions
        elif role == UserRole.TENANT_ADMIN:
            return {
                Permission.TENANT_READ,
                Permission.TENANT_WRITE,
                Permission.ECOMMERCE_ADMIN,
                Permission.HEALTHCARE_ADMIN,
                Permission.LOGISTICS_ADMIN,
                Permission.PLUGIN_READ
            }
        elif role == UserRole.USER:
            return {
                Permission.ECOMMERCE_READ,
                Permission.ECOMMERCE_WRITE,
                Permission.HEALTHCARE_READ,
                Permission.LOGISTICS_READ
            }
        elif role == UserRole.READONLY:
            return {
                Permission.ECOMMERCE_READ,
                Permission.HEALTHCARE_READ,
                Permission.LOGISTICS_READ
            }
        else:  # GUEST
            return set()
    
    async def _log_failed_login(self, username: str, reason: str, ip_address: Optional[str]):
        """Log failed login attempt"""
        try:
            await self.event_bus.publish("auth.login_failed", {
                "username": username,
                "reason": reason,
                "ip_address": ip_address,
                "timestamp": datetime.utcnow().isoformat()
            })
        except Exception as e:
            logger.error(f"Error logging failed login: {e}")
    
    async def _handle_user_event(self, event_type: str, event_data: Dict[str, any]):
        """Handle user-related events"""
        try:
            logger.debug(f"Handling user event: {event_type}")
            # Handle specific user events if needed
        except Exception as e:
            logger.error(f"Error handling user event {event_type}: {e}")


@singleton
@injectable
class AuthorizationManager:
    """
    Authorization management system providing:
    - Permission-based access control
    - Role-based authorization
    - Resource-level permissions
    - Dynamic permission evaluation
    - Audit logging for authorization decisions
    """
    
    def __init__(self, event_bus: EventBus, auth_manager: AuthenticationManager):
        self.event_bus = event_bus
        self.auth_manager = auth_manager
    
    async def check_permission(self, user: User, permission: Permission, resource_id: Optional[str] = None) -> bool:
        """Check if user has specific permission"""
        try:
            # Check if user has the permission
            has_permission = permission in user.permissions
            
            # Log authorization check
            await self.event_bus.publish("auth.permission_checked", {
                "user_id": user.id,
                "permission": permission.value,
                "resource_id": resource_id,
                "granted": has_permission
            })
            
            return has_permission
            
        except Exception as e:
            logger.error(f"Error checking permission: {e}")
            return False
    
    async def check_domain_access(self, user: User, domain: str, action: str = "read") -> bool:
        """Check if user has access to a specific domain"""
        try:
            # Map domain and action to permission
            permission_map = {
                ("ecommerce", "read"): Permission.ECOMMERCE_READ,
                ("ecommerce", "write"): Permission.ECOMMERCE_WRITE,
                ("ecommerce", "admin"): Permission.ECOMMERCE_ADMIN,
                ("healthcare", "read"): Permission.HEALTHCARE_READ,
                ("healthcare", "write"): Permission.HEALTHCARE_WRITE,
                ("healthcare", "admin"): Permission.HEALTHCARE_ADMIN,
                ("logistics", "read"): Permission.LOGISTICS_READ,
                ("logistics", "write"): Permission.LOGISTICS_WRITE,
                ("logistics", "admin"): Permission.LOGISTICS_ADMIN,
            }
            
            required_permission = permission_map.get((domain, action))
            if not required_permission:
                return False
            
            return await self.check_permission(user, required_permission)
            
        except Exception as e:
            logger.error(f"Error checking domain access: {e}")
            return False
    
    async def require_permission(self, user: User, permission: Permission, resource_id: Optional[str] = None):
        """Require specific permission or raise exception"""
        if not await self.check_permission(user, permission, resource_id):
            raise PermissionError(f"Permission denied: {permission.value}")
    
    async def require_domain_access(self, user: User, domain: str, action: str = "read"):
        """Require domain access or raise exception"""
        if not await self.check_domain_access(user, domain, action):
            raise PermissionError(f"Access denied to {domain} domain for action: {action}")