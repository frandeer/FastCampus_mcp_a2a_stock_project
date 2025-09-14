"""
Email Service Plugin Example

Demonstrates a service-type plugin that provides email functionality
with configuration validation, lifecycle management, and monitoring.
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..interfaces import ServicePlugin, PluginConfig, PluginHealth
from ..decorators import (
    plugin_metadata, config_schema, lifecycle_hook, requires_permission,
    monitor_performance, retry_on_failure, timeout, validate_input,
    HookType, PermissionType
)


@plugin_metadata(
    name="email_service",
    version="1.0.0",
    description="Email service plugin for sending and managing emails",
    author="Universal Platform Team",
    plugin_type="service",
    provides=["email", "notification", "messaging"],
    requires=["network"],
    tags=["email", "smtp", "communication"],
    max_memory_mb=50,
    network_access=True
)
@config_schema({
    'smtp_host': {'type': str, 'required': True},
    'smtp_port': {'type': int, 'required': True, 'default': 587},
    'username': {'type': str, 'required': True},
    'password': {'type': str, 'required': True},
    'use_tls': {'type': bool, 'required': False, 'default': True},
    'from_email': {'type': str, 'required': True},
    'max_recipients': {'type': int, 'required': False, 'default': 100},
    'rate_limit': {'type': int, 'required': False, 'default': 50}  # emails per minute
})
class EmailServicePlugin(ServicePlugin):
    """
    Email service plugin providing email sending capabilities.
    """
    
    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self._smtp_connection = None
        self._rate_limiter = None
        self._stats = {
            'emails_sent': 0,
            'emails_failed': 0,
            'last_email_time': None
        }
    
    @lifecycle_hook(HookType.BEFORE_INIT)
    async def _before_init(self):
        """Hook called before initialization."""
        self.logger.info("Preparing email service initialization...")
    
    @lifecycle_hook(HookType.AFTER_INIT)
    async def _after_init(self):
        """Hook called after initialization."""
        self.logger.info("Email service initialization completed")
    
    async def initialize(self, config: PluginConfig) -> None:
        """Initialize the email service plugin."""
        self.logger.info("Initializing email service plugin...")
        
        # Validate configuration
        if hasattr(self, 'validate_config'):
            self.validate_config(config)
        
        self._plugin_config = config
        
        # Initialize rate limiter
        rate_limit = config.get('rate_limit', 50)
        self._rate_limiter = RateLimiter(rate_limit, 60)  # per minute
        
        self._is_initialized = True
        self.logger.info("Email service plugin initialized successfully")
    
    @lifecycle_hook(HookType.BEFORE_START)
    async def _before_start(self):
        """Hook called before starting."""
        self.logger.info("Preparing to start email service...")
    
    @timeout(30.0)
    @retry_on_failure(max_attempts=3, delay=2.0)
    async def start(self) -> None:
        """Start the email service."""
        self.logger.info("Starting email service...")
        
        # Connect to SMTP server
        await self._connect_smtp()
        
        self._is_started = True
        self.logger.info("Email service started successfully")
    
    @lifecycle_hook(HookType.BEFORE_STOP)
    async def _before_stop(self):
        """Hook called before stopping."""
        self.logger.info("Preparing to stop email service...")
    
    async def stop(self) -> None:
        """Stop the email service."""
        self.logger.info("Stopping email service...")
        
        # Disconnect from SMTP server
        await self._disconnect_smtp()
        
        self._is_started = False
        self.logger.info("Email service stopped successfully")
    
    async def destroy(self) -> None:
        """Destroy the email service plugin."""
        self.logger.info("Destroying email service plugin...")
        
        # Cleanup resources
        self._rate_limiter = None
        self._stats.clear()
        
        self._is_initialized = False
        self.logger.info("Email service plugin destroyed")
    
    @requires_permission(PermissionType.NETWORK)
    @monitor_performance(include_args=False)
    @validate_input(
        to_emails=lambda x: isinstance(x, (str, list)) and x,
        subject=lambda x: isinstance(x, str) and len(x.strip()) > 0,
        body=lambda x: isinstance(x, str)
    )
    @timeout(60.0)
    @retry_on_failure(max_attempts=2, delay=1.0)
    async def process_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process an email sending request.
        
        Args:
            request: Email request containing 'to_emails', 'subject', 'body', etc.
            
        Returns:
            Response with sending status
        """
        action = request.get('action', 'send_email')
        
        if action == 'send_email':
            return await self._send_email(
                to_emails=request['to_emails'],
                subject=request['subject'],
                body=request['body'],
                cc_emails=request.get('cc_emails'),
                bcc_emails=request.get('bcc_emails'),
                attachments=request.get('attachments')
            )
        elif action == 'get_stats':
            return await self._get_stats()
        else:
            raise ValueError(f"Unknown action: {action}")
    
    async def health_check(self) -> PluginHealth:
        """Perform health check on the email service."""
        try:
            # Check SMTP connection
            if not self._smtp_connection or not await self._test_smtp_connection():
                return PluginHealth(
                    is_healthy=False,
                    score=0.0,
                    message="SMTP connection failed",
                    details={'smtp_status': 'disconnected'}
                )
            
            # Check rate limiter
            if self._rate_limiter and self._rate_limiter.is_exhausted():
                return PluginHealth(
                    is_healthy=True,
                    score=0.5,
                    message="Rate limit approaching",
                    details={'rate_limit_status': 'warning'}
                )
            
            return PluginHealth(
                is_healthy=True,
                score=1.0,
                message="Email service is healthy",
                details={
                    'smtp_status': 'connected',
                    'emails_sent': self._stats['emails_sent'],
                    'emails_failed': self._stats['emails_failed']
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
        """Get email service metrics."""
        return {
            'emails_sent_total': self._stats['emails_sent'],
            'emails_failed_total': self._stats['emails_failed'],
            'success_rate': self._get_success_rate(),
            'last_email_timestamp': self._stats['last_email_time'],
            'rate_limit_remaining': self._rate_limiter.remaining() if self._rate_limiter else 0
        }
    
    # Private helper methods
    
    async def _send_email(
        self,
        to_emails: List[str],
        subject: str,
        body: str,
        cc_emails: Optional[List[str]] = None,
        bcc_emails: Optional[List[str]] = None,
        attachments: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Send an email."""
        try:
            # Check rate limit
            if not await self._rate_limiter.acquire():
                raise RuntimeError("Rate limit exceeded")
            
            # Validate recipients
            all_recipients = self._normalize_recipients(to_emails)
            if cc_emails:
                all_recipients.extend(self._normalize_recipients(cc_emails))
            if bcc_emails:
                all_recipients.extend(self._normalize_recipients(bcc_emails))
            
            max_recipients = self._plugin_config.get('max_recipients', 100)
            if len(all_recipients) > max_recipients:
                raise ValueError(f"Too many recipients: {len(all_recipients)} > {max_recipients}")
            
            # Simulate email sending
            await asyncio.sleep(0.1)  # Simulate network delay
            
            # Update statistics
            self._stats['emails_sent'] += 1
            self._stats['last_email_time'] = datetime.now().isoformat()
            
            self.logger.info(f"Email sent successfully to {len(all_recipients)} recipients")
            
            return {
                'success': True,
                'message_id': f"msg_{datetime.now().timestamp()}",
                'recipients_count': len(all_recipients),
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            self._stats['emails_failed'] += 1
            self.logger.error(f"Failed to send email: {e}")
            
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    async def _get_stats(self) -> Dict[str, Any]:
        """Get email service statistics."""
        return {
            'emails_sent': self._stats['emails_sent'],
            'emails_failed': self._stats['emails_failed'],
            'success_rate': self._get_success_rate(),
            'last_email_time': self._stats['last_email_time']
        }
    
    async def _connect_smtp(self) -> None:
        """Connect to SMTP server."""
        # Simulate SMTP connection
        self.logger.info("Connecting to SMTP server...")
        await asyncio.sleep(0.5)  # Simulate connection time
        self._smtp_connection = "connected"
        self.logger.info("SMTP connection established")
    
    async def _disconnect_smtp(self) -> None:
        """Disconnect from SMTP server."""
        if self._smtp_connection:
            self.logger.info("Disconnecting from SMTP server...")
            await asyncio.sleep(0.1)
            self._smtp_connection = None
            self.logger.info("SMTP connection closed")
    
    async def _test_smtp_connection(self) -> bool:
        """Test SMTP connection."""
        return self._smtp_connection is not None
    
    def _normalize_recipients(self, recipients) -> List[str]:
        """Normalize recipient list."""
        if isinstance(recipients, str):
            return [recipients]
        elif isinstance(recipients, list):
            return recipients
        else:
            raise ValueError("Recipients must be string or list of strings")
    
    def _get_success_rate(self) -> float:
        """Calculate success rate."""
        total = self._stats['emails_sent'] + self._stats['emails_failed']
        if total == 0:
            return 1.0
        return self._stats['emails_sent'] / total


class RateLimiter:
    """Simple rate limiter implementation."""
    
    def __init__(self, limit: int, window_seconds: int):
        self.limit = limit
        self.window_seconds = window_seconds
        self.requests = []
    
    async def acquire(self) -> bool:
        """Acquire a rate limit token."""
        now = datetime.now().timestamp()
        
        # Remove old requests outside the window
        cutoff = now - self.window_seconds
        self.requests = [req_time for req_time in self.requests if req_time > cutoff]
        
        # Check if we can make a new request
        if len(self.requests) < self.limit:
            self.requests.append(now)
            return True
        
        return False
    
    def remaining(self) -> int:
        """Get remaining requests in current window."""
        now = datetime.now().timestamp()
        cutoff = now - self.window_seconds
        current_requests = [req_time for req_time in self.requests if req_time > cutoff]
        return max(0, self.limit - len(current_requests))
    
    def is_exhausted(self) -> bool:
        """Check if rate limit is exhausted."""
        return self.remaining() == 0