"""
Tenant routing and resolution from HTTP requests.

Provides various strategies to identify and resolve tenant information
from incoming requests including domain-based, header-based, JWT-based,
and composite resolution strategies.
"""

import base64
import json
import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Pattern, Tuple, Union
from urllib.parse import urlparse

import jwt
from pydantic import BaseModel, Field

from .tenant_context import TenantInfo

logger = logging.getLogger(__name__)


class TenantResolutionError(Exception):
    """Exception raised when tenant resolution fails."""
    pass


class TenantNotFoundError(TenantResolutionError):
    """Exception raised when tenant cannot be found."""
    pass


class InvalidTenantError(TenantResolutionError):
    """Exception raised when tenant is invalid or inactive."""
    pass


@dataclass
class ResolutionResult:
    """Result of tenant resolution."""
    
    tenant_info: Optional[TenantInfo]
    confidence: float  # 0.0 to 1.0
    source: str  # Source of the resolution (domain, header, jwt, etc.)
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
    
    @property
    def is_successful(self) -> bool:
        """Check if resolution was successful."""
        return self.tenant_info is not None
    
    @property
    def tenant_id(self) -> Optional[str]:
        """Get the tenant ID if resolution was successful."""
        return self.tenant_info.tenant_id if self.tenant_info else None


class TenantResolver(ABC):
    """Abstract base class for tenant resolution strategies."""
    
    @abstractmethod
    def resolve(self, request_data: Dict[str, Any]) -> ResolutionResult:
        """
        Resolve tenant information from request data.
        
        Args:
            request_data: Dictionary containing request information
            
        Returns:
            ResolutionResult: The resolution result
        """
        pass
    
    def can_resolve(self, request_data: Dict[str, Any]) -> bool:
        """
        Check if this resolver can handle the given request.
        
        Args:
            request_data: Dictionary containing request information
            
        Returns:
            bool: True if this resolver can handle the request
        """
        return True


class DomainTenantResolver(TenantResolver):
    """Resolve tenant from domain or subdomain."""
    
    def __init__(self, tenant_mapping: Optional[Dict[str, TenantInfo]] = None):
        self.tenant_mapping = tenant_mapping or {}
        self._domain_patterns: List[Tuple[Pattern, str]] = []
        self._subdomain_patterns: List[Tuple[Pattern, str]] = []
    
    def add_domain_mapping(self, domain: str, tenant_info: TenantInfo) -> None:
        """Add a direct domain to tenant mapping."""
        self.tenant_mapping[domain.lower()] = tenant_info
    
    def add_domain_pattern(self, pattern: str, tenant_id_template: str) -> None:
        """
        Add a domain pattern for dynamic tenant resolution.
        
        Args:
            pattern: Regex pattern with named groups
            tenant_id_template: Template for tenant ID (e.g., "{subdomain}")
        """
        compiled_pattern = re.compile(pattern, re.IGNORECASE)
        self._domain_patterns.append((compiled_pattern, tenant_id_template))
    
    def add_subdomain_pattern(self, base_domain: str, tenant_id_template: str = "{subdomain}") -> None:
        """
        Add a subdomain pattern for tenant resolution.
        
        Args:
            base_domain: Base domain (e.g., "example.com")
            tenant_id_template: Template for tenant ID (default: "{subdomain}")
        """
        # Pattern to match subdomain.basedomain.com
        pattern = rf"^(?P<subdomain>[a-z0-9-]+)\.{re.escape(base_domain)}$"
        compiled_pattern = re.compile(pattern, re.IGNORECASE)
        self._subdomain_patterns.append((compiled_pattern, tenant_id_template))
    
    def resolve(self, request_data: Dict[str, Any]) -> ResolutionResult:
        """Resolve tenant from domain/subdomain."""
        host = request_data.get('host') or request_data.get('domain')
        if not host:
            return ResolutionResult(
                tenant_info=None,
                confidence=0.0,
                source="domain",
                metadata={"error": "No host information available"}
            )
        
        # Clean up host (remove port if present)
        host = host.split(':')[0].lower()
        
        # Try direct domain mapping first
        if host in self.tenant_mapping:
            return ResolutionResult(
                tenant_info=self.tenant_mapping[host],
                confidence=1.0,
                source="domain",
                metadata={"matched_domain": host}
            )
        
        # Try subdomain patterns
        for pattern, template in self._subdomain_patterns:
            match = pattern.match(host)
            if match:
                groups = match.groupdict()
                tenant_id = template.format(**groups)
                
                # Create tenant info (would typically load from database)
                tenant_info = self._create_tenant_info(tenant_id, groups)
                if tenant_info:
                    return ResolutionResult(
                        tenant_info=tenant_info,
                        confidence=0.9,
                        source="subdomain",
                        metadata={"matched_pattern": pattern.pattern, "groups": groups}
                    )
        
        # Try general domain patterns
        for pattern, template in self._domain_patterns:
            match = pattern.match(host)
            if match:
                groups = match.groupdict()
                tenant_id = template.format(**groups)
                
                tenant_info = self._create_tenant_info(tenant_id, groups)
                if tenant_info:
                    return ResolutionResult(
                        tenant_info=tenant_info,
                        confidence=0.8,
                        source="domain_pattern",
                        metadata={"matched_pattern": pattern.pattern, "groups": groups}
                    )
        
        return ResolutionResult(
            tenant_info=None,
            confidence=0.0,
            source="domain",
            metadata={"error": f"No tenant mapping found for host: {host}"}
        )
    
    def _create_tenant_info(self, tenant_id: str, match_groups: Dict[str, str]) -> Optional[TenantInfo]:
        """
        Create tenant info from resolved tenant ID.
        
        This is a placeholder implementation. In a real application,
        you would load tenant information from a database or cache.
        """
        # Validate tenant ID format
        if not re.match(r'^[a-z0-9-]+$', tenant_id):
            return None
        
        return TenantInfo(
            tenant_id=tenant_id,
            tenant_name=tenant_id.replace('-', ' ').title(),
            subdomain=match_groups.get('subdomain'),
            domain=match_groups.get('domain'),
            metadata={"resolution_groups": match_groups}
        )


class HeaderTenantResolver(TenantResolver):
    """Resolve tenant from HTTP headers."""
    
    def __init__(self, 
                 tenant_header: str = "X-Tenant-ID",
                 tenant_mapping: Optional[Dict[str, TenantInfo]] = None,
                 validate_tenant: bool = True):
        self.tenant_header = tenant_header.lower()
        self.tenant_mapping = tenant_mapping or {}
        self.validate_tenant = validate_tenant
    
    def add_tenant_mapping(self, tenant_id: str, tenant_info: TenantInfo) -> None:
        """Add a tenant ID to tenant info mapping."""
        self.tenant_mapping[tenant_id] = tenant_info
    
    def resolve(self, request_data: Dict[str, Any]) -> ResolutionResult:
        """Resolve tenant from headers."""
        headers = request_data.get('headers', {})
        
        # Normalize header names to lowercase
        normalized_headers = {k.lower(): v for k, v in headers.items()}
        
        tenant_id = normalized_headers.get(self.tenant_header)
        if not tenant_id:
            return ResolutionResult(
                tenant_info=None,
                confidence=0.0,
                source="header",
                metadata={"error": f"Header {self.tenant_header} not found"}
            )
        
        # Validate tenant ID format
        if not self._is_valid_tenant_id(tenant_id):
            return ResolutionResult(
                tenant_info=None,
                confidence=0.0,
                source="header",
                metadata={"error": f"Invalid tenant ID format: {tenant_id}"}
            )
        
        # Get tenant info
        if self.validate_tenant and tenant_id in self.tenant_mapping:
            tenant_info = self.tenant_mapping[tenant_id]
            confidence = 1.0
        elif not self.validate_tenant:
            # Create basic tenant info without validation
            tenant_info = TenantInfo(
                tenant_id=tenant_id,
                tenant_name=tenant_id,
                metadata={"source": "header"}
            )
            confidence = 0.7
        else:
            return ResolutionResult(
                tenant_info=None,
                confidence=0.0,
                source="header",
                metadata={"error": f"Tenant not found: {tenant_id}"}
            )
        
        return ResolutionResult(
            tenant_info=tenant_info,
            confidence=confidence,
            source="header",
            metadata={"header": self.tenant_header, "tenant_id": tenant_id}
        )
    
    def _is_valid_tenant_id(self, tenant_id: str) -> bool:
        """Validate tenant ID format."""
        if not tenant_id or len(tenant_id) > 100:
            return False
        # Allow alphanumeric, hyphens, and underscores
        return re.match(r'^[a-zA-Z0-9_-]+$', tenant_id) is not None


class JWTTenantResolver(TenantResolver):
    """Resolve tenant from JWT token claims."""
    
    def __init__(self,
                 secret_key: str,
                 tenant_claim: str = "tenant_id",
                 token_header: str = "Authorization",
                 token_prefix: str = "Bearer ",
                 algorithms: List[str] = None,
                 tenant_mapping: Optional[Dict[str, TenantInfo]] = None):
        self.secret_key = secret_key
        self.tenant_claim = tenant_claim
        self.token_header = token_header.lower()
        self.token_prefix = token_prefix
        self.algorithms = algorithms or ["HS256"]
        self.tenant_mapping = tenant_mapping or {}
    
    def add_tenant_mapping(self, tenant_id: str, tenant_info: TenantInfo) -> None:
        """Add a tenant ID to tenant info mapping."""
        self.tenant_mapping[tenant_id] = tenant_info
    
    def resolve(self, request_data: Dict[str, Any]) -> ResolutionResult:
        """Resolve tenant from JWT token."""
        headers = request_data.get('headers', {})
        normalized_headers = {k.lower(): v for k, v in headers.items()}
        
        auth_header = normalized_headers.get(self.token_header)
        if not auth_header:
            return ResolutionResult(
                tenant_info=None,
                confidence=0.0,
                source="jwt",
                metadata={"error": f"Header {self.token_header} not found"}
            )
        
        # Extract token from header
        if not auth_header.startswith(self.token_prefix):
            return ResolutionResult(
                tenant_info=None,
                confidence=0.0,
                source="jwt",
                metadata={"error": f"Invalid token format, expected prefix: {self.token_prefix}"}
            )
        
        token = auth_header[len(self.token_prefix):].strip()
        
        try:
            # Decode and verify JWT
            payload = jwt.decode(token, self.secret_key, algorithms=self.algorithms)
            
            # Extract tenant ID from claims
            tenant_id = payload.get(self.tenant_claim)
            if not tenant_id:
                return ResolutionResult(
                    tenant_info=None,
                    confidence=0.0,
                    source="jwt",
                    metadata={"error": f"Claim {self.tenant_claim} not found in token"}
                )
            
            # Get tenant info
            if tenant_id in self.tenant_mapping:
                tenant_info = self.tenant_mapping[tenant_id]
                confidence = 1.0
            else:
                # Create basic tenant info from JWT claims
                tenant_info = TenantInfo(
                    tenant_id=tenant_id,
                    tenant_name=payload.get("tenant_name", tenant_id),
                    metadata={
                        "source": "jwt",
                        "jwt_claims": {k: v for k, v in payload.items() if k not in ["exp", "iat", "aud", "iss"]}
                    }
                )
                confidence = 0.8
            
            return ResolutionResult(
                tenant_info=tenant_info,
                confidence=confidence,
                source="jwt",
                metadata={
                    "tenant_claim": self.tenant_claim,
                    "jwt_claims": payload,
                    "token_valid": True
                }
            )
        
        except jwt.ExpiredSignatureError:
            return ResolutionResult(
                tenant_info=None,
                confidence=0.0,
                source="jwt",
                metadata={"error": "Token has expired"}
            )
        except jwt.InvalidTokenError as e:
            return ResolutionResult(
                tenant_info=None,
                confidence=0.0,
                source="jwt",
                metadata={"error": f"Invalid token: {str(e)}"}
            )
        except Exception as e:
            return ResolutionResult(
                tenant_info=None,
                confidence=0.0,
                source="jwt",
                metadata={"error": f"Token processing error: {str(e)}"}
            )


class PathTenantResolver(TenantResolver):
    """Resolve tenant from URL path."""
    
    def __init__(self, path_patterns: Optional[List[Tuple[str, str]]] = None):
        self.path_patterns = path_patterns or []
        self._compiled_patterns: List[Tuple[Pattern, str]] = []
        
        # Compile patterns
        for pattern, template in self.path_patterns:
            compiled_pattern = re.compile(pattern)
            self._compiled_patterns.append((compiled_pattern, template))
    
    def add_path_pattern(self, pattern: str, tenant_id_template: str) -> None:
        """
        Add a path pattern for tenant resolution.
        
        Args:
            pattern: Regex pattern with named groups
            tenant_id_template: Template for tenant ID
        """
        compiled_pattern = re.compile(pattern)
        self._compiled_patterns.append((compiled_pattern, tenant_id_template))
    
    def resolve(self, request_data: Dict[str, Any]) -> ResolutionResult:
        """Resolve tenant from URL path."""
        path = request_data.get('path') or request_data.get('url', '')
        if not path:
            return ResolutionResult(
                tenant_info=None,
                confidence=0.0,
                source="path",
                metadata={"error": "No path information available"}
            )
        
        for pattern, template in self._compiled_patterns:
            match = pattern.match(path)
            if match:
                groups = match.groupdict()
                tenant_id = template.format(**groups)
                
                # Create tenant info
                tenant_info = TenantInfo(
                    tenant_id=tenant_id,
                    tenant_name=tenant_id,
                    metadata={"source": "path", "path_groups": groups}
                )
                
                return ResolutionResult(
                    tenant_info=tenant_info,
                    confidence=0.8,
                    source="path",
                    metadata={"matched_pattern": pattern.pattern, "groups": groups}
                )
        
        return ResolutionResult(
            tenant_info=None,
            confidence=0.0,
            source="path",
            metadata={"error": f"No tenant pattern matched path: {path}"}
        )


class CompositeTenantResolver(TenantResolver):
    """Composite resolver that tries multiple resolution strategies."""
    
    def __init__(self, resolvers: Optional[List[TenantResolver]] = None):
        self.resolvers = resolvers or []
        self.fallback_resolver: Optional[TenantResolver] = None
    
    def add_resolver(self, resolver: TenantResolver) -> None:
        """Add a resolver to the chain."""
        self.resolvers.append(resolver)
    
    def set_fallback_resolver(self, resolver: TenantResolver) -> None:
        """Set a fallback resolver to use if all others fail."""
        self.fallback_resolver = resolver
    
    def resolve(self, request_data: Dict[str, Any]) -> ResolutionResult:
        """Try each resolver in order until one succeeds."""
        best_result: Optional[ResolutionResult] = None
        
        for resolver in self.resolvers:
            if not resolver.can_resolve(request_data):
                continue
            
            try:
                result = resolver.resolve(request_data)
                
                # If successful, return immediately
                if result.is_successful:
                    return result
                
                # Keep track of the best (highest confidence) failed result
                if not best_result or result.confidence > best_result.confidence:
                    best_result = result
                    
            except Exception as e:
                logger.warning(f"Resolver {type(resolver).__name__} failed: {e}")
                continue
        
        # Try fallback resolver if all others failed
        if self.fallback_resolver and self.fallback_resolver.can_resolve(request_data):
            try:
                fallback_result = self.fallback_resolver.resolve(request_data)
                if fallback_result.is_successful or (not best_result):
                    return fallback_result
            except Exception as e:
                logger.warning(f"Fallback resolver failed: {e}")
        
        # Return the best failed result or a default failure
        return best_result or ResolutionResult(
            tenant_info=None,
            confidence=0.0,
            source="composite",
            metadata={"error": "All resolvers failed"}
        )


class TenantRouterManager:
    """
    Main manager for tenant routing and resolution.
    
    Provides a high-level interface for configuring and using
    tenant resolution strategies.
    """
    
    def __init__(self):
        self.resolvers: Dict[str, TenantResolver] = {}
        self.default_resolver: Optional[str] = None
        self.composite_resolver: Optional[CompositeTenantResolver] = None
    
    def add_domain_resolver(self, 
                          name: str = "domain",
                          tenant_mapping: Optional[Dict[str, TenantInfo]] = None,
                          is_default: bool = False) -> DomainTenantResolver:
        """Add a domain-based tenant resolver."""
        resolver = DomainTenantResolver(tenant_mapping)
        self.resolvers[name] = resolver
        
        if is_default:
            self.default_resolver = name
        
        return resolver
    
    def add_header_resolver(self,
                          name: str = "header",
                          tenant_header: str = "X-Tenant-ID",
                          tenant_mapping: Optional[Dict[str, TenantInfo]] = None,
                          is_default: bool = False) -> HeaderTenantResolver:
        """Add a header-based tenant resolver."""
        resolver = HeaderTenantResolver(tenant_header, tenant_mapping)
        self.resolvers[name] = resolver
        
        if is_default:
            self.default_resolver = name
        
        return resolver
    
    def add_jwt_resolver(self,
                        name: str = "jwt",
                        secret_key: str = "",
                        tenant_claim: str = "tenant_id",
                        tenant_mapping: Optional[Dict[str, TenantInfo]] = None,
                        is_default: bool = False) -> JWTTenantResolver:
        """Add a JWT-based tenant resolver."""
        resolver = JWTTenantResolver(secret_key, tenant_claim, tenant_mapping=tenant_mapping)
        self.resolvers[name] = resolver
        
        if is_default:
            self.default_resolver = name
        
        return resolver
    
    def add_path_resolver(self,
                         name: str = "path", 
                         path_patterns: Optional[List[Tuple[str, str]]] = None,
                         is_default: bool = False) -> PathTenantResolver:
        """Add a path-based tenant resolver."""
        resolver = PathTenantResolver(path_patterns)
        self.resolvers[name] = resolver
        
        if is_default:
            self.default_resolver = name
        
        return resolver
    
    def create_composite_resolver(self, resolver_names: List[str], fallback_name: Optional[str] = None) -> CompositeTenantResolver:
        """Create a composite resolver from existing resolvers."""
        resolvers = [self.resolvers[name] for name in resolver_names if name in self.resolvers]
        composite = CompositeTenantResolver(resolvers)
        
        if fallback_name and fallback_name in self.resolvers:
            composite.set_fallback_resolver(self.resolvers[fallback_name])
        
        self.composite_resolver = composite
        return composite
    
    def resolve_tenant(self, request_data: Dict[str, Any], resolver_name: Optional[str] = None) -> ResolutionResult:
        """
        Resolve tenant using the specified or default resolver.
        
        Args:
            request_data: Request data dictionary
            resolver_name: Name of resolver to use (defaults to configured default)
            
        Returns:
            ResolutionResult: The resolution result
        """
        # Use composite resolver if available and no specific resolver requested
        if not resolver_name and self.composite_resolver:
            return self.composite_resolver.resolve(request_data)
        
        # Use specified or default resolver
        resolver_name = resolver_name or self.default_resolver
        if not resolver_name or resolver_name not in self.resolvers:
            raise TenantResolutionError(f"No resolver found: {resolver_name}")
        
        resolver = self.resolvers[resolver_name]
        return resolver.resolve(request_data)
    
    def get_resolver(self, name: str) -> Optional[TenantResolver]:
        """Get a resolver by name."""
        return self.resolvers.get(name)