"""
Circuit breaker pattern implementation for event handling resilience.
"""

import asyncio
import logging
import time
from typing import Any, Dict, Optional, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum


logger = logging.getLogger(__name__)


class CircuitBreakerState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"        # Normal operation
    OPEN = "open"           # Failing, all requests rejected
    HALF_OPEN = "half_open" # Testing if service recovered


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""
    failure_threshold: int = 5          # Failures before opening
    recovery_timeout: float = 60.0      # Seconds before trying half-open
    success_threshold: int = 3          # Successes to close from half-open
    timeout: float = 30.0               # Timeout for operations
    expected_exception: Exception = Exception
    fallback_result: Any = None
    
    # Advanced settings
    failure_rate_threshold: float = 0.5  # Failure rate to trigger opening
    minimum_requests: int = 10           # Min requests before calculating rate
    sliding_window_size: int = 100       # Size of sliding window
    slow_call_duration_threshold: float = 5.0  # Slow call threshold
    slow_call_rate_threshold: float = 0.5      # Slow call rate threshold


@dataclass
class CircuitBreakerMetrics:
    """Circuit breaker metrics."""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    slow_requests: int = 0
    rejected_requests: int = 0
    last_failure_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None
    state_changed_time: datetime = field(default_factory=datetime.utcnow)
    
    def get_failure_rate(self) -> float:
        """Get failure rate."""
        if self.total_requests == 0:
            return 0.0
        return self.failed_requests / self.total_requests
    
    def get_slow_call_rate(self) -> float:
        """Get slow call rate."""
        if self.total_requests == 0:
            return 0.0
        return self.slow_requests / self.total_requests


class CircuitBreaker:
    """Circuit breaker implementation with advanced features."""
    
    def __init__(self, config: Optional[CircuitBreakerConfig] = None):
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitBreakerState.CLOSED
        self.metrics = CircuitBreakerMetrics()
        
        # Sliding window for rate calculation
        self._call_history: list = []
        self._lock = asyncio.Lock()
        
        logger.info("CircuitBreaker initialized")
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection."""
        async with self._lock:
            # Check if we should reject the call
            if await self._should_reject_call():
                self.metrics.rejected_requests += 1
                if self.config.fallback_result is not None:
                    return self.config.fallback_result
                raise Exception("Circuit breaker is OPEN")
            
            # Record call attempt
            self.metrics.total_requests += 1
            call_start_time = time.time()
            
            try:
                # Execute with timeout
                result = await asyncio.wait_for(
                    self._execute_func(func, *args, **kwargs),
                    timeout=self.config.timeout
                )
                
                # Record success
                call_duration = time.time() - call_start_time
                await self._record_success(call_duration)
                
                return result
                
            except asyncio.TimeoutError as e:
                # Record timeout as failure
                call_duration = time.time() - call_start_time
                await self._record_failure(e, call_duration)
                raise
                
            except Exception as e:
                # Record failure
                call_duration = time.time() - call_start_time
                await self._record_failure(e, call_duration)
                
                if isinstance(e, self.config.expected_exception):
                    if self.config.fallback_result is not None:
                        return self.config.fallback_result
                
                raise
    
    async def _execute_func(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function (async or sync)."""
        if asyncio.iscoroutinefunction(func):
            return await func(*args, **kwargs)
        else:
            # Run sync function in executor
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, func, *args, **kwargs)
    
    async def _should_reject_call(self) -> bool:
        """Check if call should be rejected."""
        if self.state == CircuitBreakerState.CLOSED:
            return False
        
        if self.state == CircuitBreakerState.OPEN:
            # Check if recovery timeout has passed
            if self.metrics.last_failure_time:
                time_since_failure = datetime.utcnow() - self.metrics.last_failure_time
                if time_since_failure.total_seconds() >= self.config.recovery_timeout:
                    await self._transition_to_half_open()
                    return False
            return True
        
        if self.state == CircuitBreakerState.HALF_OPEN:
            # In half-open state, allow some calls through
            return False
        
        return False
    
    async def _record_success(self, call_duration: float) -> None:
        """Record successful call."""
        self.metrics.successful_requests += 1
        self.metrics.last_success_time = datetime.utcnow()
        
        # Check for slow call
        if call_duration > self.config.slow_call_duration_threshold:
            self.metrics.slow_requests += 1
        
        # Add to history
        self._call_history.append({
            "timestamp": time.time(),
            "success": True,
            "duration": call_duration,
        })
        self._trim_call_history()
        
        # State transition logic
        if self.state == CircuitBreakerState.HALF_OPEN:
            # Count consecutive successes in half-open
            recent_calls = self._get_recent_calls()
            consecutive_successes = 0
            for call in reversed(recent_calls):
                if call["success"]:
                    consecutive_successes += 1
                else:
                    break
            
            if consecutive_successes >= self.config.success_threshold:
                await self._transition_to_closed()
    
    async def _record_failure(self, exception: Exception, call_duration: float) -> None:
        """Record failed call."""
        self.metrics.failed_requests += 1
        self.metrics.last_failure_time = datetime.utcnow()
        
        # Check for slow call
        if call_duration > self.config.slow_call_duration_threshold:
            self.metrics.slow_requests += 1
        
        # Add to history
        self._call_history.append({
            "timestamp": time.time(),
            "success": False,
            "duration": call_duration,
            "exception": str(exception),
        })
        self._trim_call_history()
        
        # State transition logic
        if self.state == CircuitBreakerState.CLOSED:
            await self._check_failure_threshold()
        elif self.state == CircuitBreakerState.HALF_OPEN:
            # Any failure in half-open goes back to open
            await self._transition_to_open()
    
    async def _check_failure_threshold(self) -> None:
        """Check if failure threshold is exceeded."""
        recent_calls = self._get_recent_calls()
        
        if len(recent_calls) < self.config.minimum_requests:
            return
        
        # Check failure rate
        failures = sum(1 for call in recent_calls if not call["success"])
        failure_rate = failures / len(recent_calls)
        
        if failure_rate >= self.config.failure_rate_threshold:
            await self._transition_to_open()
            return
        
        # Check slow call rate
        slow_calls = sum(1 for call in recent_calls 
                        if call["duration"] > self.config.slow_call_duration_threshold)
        slow_call_rate = slow_calls / len(recent_calls)
        
        if slow_call_rate >= self.config.slow_call_rate_threshold:
            await self._transition_to_open()
            return
        
        # Check consecutive failures (traditional threshold)
        consecutive_failures = 0
        for call in reversed(recent_calls):
            if not call["success"]:
                consecutive_failures += 1
            else:
                break
        
        if consecutive_failures >= self.config.failure_threshold:
            await self._transition_to_open()
    
    async def _transition_to_open(self) -> None:
        """Transition to OPEN state."""
        if self.state != CircuitBreakerState.OPEN:
            old_state = self.state
            self.state = CircuitBreakerState.OPEN
            self.metrics.state_changed_time = datetime.utcnow()
            logger.warning(f"Circuit breaker transitioned from {old_state.value} to OPEN")
    
    async def _transition_to_half_open(self) -> None:
        """Transition to HALF_OPEN state."""
        if self.state != CircuitBreakerState.HALF_OPEN:
            old_state = self.state
            self.state = CircuitBreakerState.HALF_OPEN
            self.metrics.state_changed_time = datetime.utcnow()
            logger.info(f"Circuit breaker transitioned from {old_state.value} to HALF_OPEN")
    
    async def _transition_to_closed(self) -> None:
        """Transition to CLOSED state."""
        if self.state != CircuitBreakerState.CLOSED:
            old_state = self.state
            self.state = CircuitBreakerState.CLOSED
            self.metrics.state_changed_time = datetime.utcnow()
            logger.info(f"Circuit breaker transitioned from {old_state.value} to CLOSED")
    
    def _get_recent_calls(self) -> list:
        """Get recent calls within sliding window."""
        cutoff_time = time.time() - (self.config.sliding_window_size * 60)  # Last N minutes
        return [call for call in self._call_history if call["timestamp"] > cutoff_time]
    
    def _trim_call_history(self) -> None:
        """Trim call history to sliding window size."""
        if len(self._call_history) > self.config.sliding_window_size:
            self._call_history = self._call_history[-self.config.sliding_window_size:]
    
    def can_execute(self) -> bool:
        """Check if circuit breaker allows execution."""
        return self.state != CircuitBreakerState.OPEN
    
    def record_success(self) -> None:
        """Manually record a success (for external tracking)."""
        asyncio.create_task(self._record_success(0.0))
    
    def record_failure(self, exception: Optional[Exception] = None) -> None:
        """Manually record a failure (for external tracking)."""
        asyncio.create_task(self._record_failure(exception or Exception("Manual failure"), 0.0))
    
    def get_status(self) -> Dict[str, Any]:
        """Get circuit breaker status."""
        recent_calls = self._get_recent_calls()
        
        return {
            "state": self.state.value,
            "metrics": {
                "total_requests": self.metrics.total_requests,
                "successful_requests": self.metrics.successful_requests,
                "failed_requests": self.metrics.failed_requests,
                "slow_requests": self.metrics.slow_requests,
                "rejected_requests": self.metrics.rejected_requests,
                "failure_rate": self.metrics.get_failure_rate(),
                "slow_call_rate": self.metrics.get_slow_call_rate(),
                "last_failure_time": self.metrics.last_failure_time.isoformat() if self.metrics.last_failure_time else None,
                "last_success_time": self.metrics.last_success_time.isoformat() if self.metrics.last_success_time else None,
                "state_changed_time": self.metrics.state_changed_time.isoformat(),
            },
            "config": {
                "failure_threshold": self.config.failure_threshold,
                "recovery_timeout": self.config.recovery_timeout,
                "success_threshold": self.config.success_threshold,
                "timeout": self.config.timeout,
                "failure_rate_threshold": self.config.failure_rate_threshold,
                "minimum_requests": self.config.minimum_requests,
                "sliding_window_size": self.config.sliding_window_size,
            },
            "recent_calls": len(recent_calls),
        }
    
    async def reset(self) -> None:
        """Reset circuit breaker to initial state."""
        async with self._lock:
            self.state = CircuitBreakerState.CLOSED
            self.metrics = CircuitBreakerMetrics()
            self._call_history.clear()
            logger.info("Circuit breaker reset to CLOSED state")
    
    async def force_open(self) -> None:
        """Force circuit breaker to OPEN state."""
        async with self._lock:
            await self._transition_to_open()
    
    async def force_closed(self) -> None:
        """Force circuit breaker to CLOSED state."""
        async with self._lock:
            await self._transition_to_closed()


class EventHandlerCircuitBreaker(CircuitBreaker):
    """Circuit breaker specialized for event handlers."""
    
    def __init__(self, handler_name: str, config: Optional[CircuitBreakerConfig] = None):
        super().__init__(config)
        self.handler_name = handler_name
    
    async def call_handler(self, handler: Callable, event: Any) -> Any:
        """Call event handler with circuit breaker protection."""
        try:
            return await self.call(handler, event)
        except Exception as e:
            logger.error(f"Circuit breaker rejected call to handler {self.handler_name}: {e}")
            raise
    
    def get_status(self) -> Dict[str, Any]:
        """Get handler-specific status."""
        status = super().get_status()
        status["handler_name"] = self.handler_name
        return status