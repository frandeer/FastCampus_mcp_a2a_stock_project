"""
Saga pattern implementation for distributed transaction management.
"""

import asyncio
import logging
import json
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Callable, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import uuid

from .models import Event, EventMetadata
from .persistence import EventStore


logger = logging.getLogger(__name__)


class SagaState(Enum):
    """Saga execution states."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    COMPENSATING = "compensating"
    COMPENSATED = "compensated"
    FAILED = "failed"


class StepState(Enum):
    """Individual step states."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    COMPENSATING = "compensating" 
    COMPENSATED = "compensated"
    FAILED = "failed"


@dataclass
class SagaStep:
    """Individual step in a saga."""
    name: str
    action: Callable
    compensation: Optional[Callable] = None
    timeout_seconds: int = 30
    retry_count: int = 3
    retry_delay_seconds: float = 1.0
    state: StepState = StepState.PENDING
    result: Any = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    attempt_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert step to dictionary."""
        return {
            "name": self.name,
            "state": self.state.value,
            "result": self.result,
            "error": self.error,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "attempt_count": self.attempt_count,
            "timeout_seconds": self.timeout_seconds,
            "retry_count": self.retry_count,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any], action: Callable, compensation: Optional[Callable] = None) -> "SagaStep":
        """Create step from dictionary."""
        return cls(
            name=data["name"],
            action=action,
            compensation=compensation,
            timeout_seconds=data.get("timeout_seconds", 30),
            retry_count=data.get("retry_count", 3),
            state=StepState(data.get("state", "pending")),
            result=data.get("result"),
            error=data.get("error"),
            started_at=datetime.fromisoformat(data["started_at"]) if data.get("started_at") else None,
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
            attempt_count=data.get("attempt_count", 0),
        )


@dataclass
class SagaDefinition:
    """Definition of a saga workflow."""
    saga_id: str
    name: str
    steps: List[SagaStep]
    timeout_seconds: int = 300
    created_at: datetime = field(default_factory=datetime.utcnow)
    context: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "saga_id": self.saga_id,
            "name": self.name,
            "steps": [step.to_dict() for step in self.steps],
            "timeout_seconds": self.timeout_seconds,
            "created_at": self.created_at.isoformat(),
            "context": self.context,
        }


@dataclass
class SagaExecution:
    """Saga execution instance."""
    saga_id: str
    definition: SagaDefinition
    state: SagaState = SagaState.PENDING
    current_step_index: int = 0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    compensation_started_at: Optional[datetime] = None
    compensation_completed_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "saga_id": self.saga_id,
            "definition": self.definition.to_dict(),
            "state": self.state.value,
            "current_step_index": self.current_step_index,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error": self.error,
            "compensation_started_at": self.compensation_started_at.isoformat() if self.compensation_started_at else None,
            "compensation_completed_at": self.compensation_completed_at.isoformat() if self.compensation_completed_at else None,
        }
    
    def get_current_step(self) -> Optional[SagaStep]:
        """Get current step being executed."""
        if 0 <= self.current_step_index < len(self.definition.steps):
            return self.definition.steps[self.current_step_index]
        return None
    
    def get_completed_steps(self) -> List[SagaStep]:
        """Get steps that have completed successfully."""
        return [
            step for step in self.definition.steps
            if step.state == StepState.COMPLETED
        ]
    
    def get_failed_steps(self) -> List[SagaStep]:
        """Get steps that have failed."""
        return [
            step for step in self.definition.steps
            if step.state == StepState.FAILED
        ]


class Saga(ABC):
    """Abstract base class for saga implementations."""
    
    def __init__(self, saga_id: str, name: str):
        self.saga_id = saga_id
        self.name = name
        self.steps: List[SagaStep] = []
    
    @abstractmethod
    async def define_steps(self) -> List[SagaStep]:
        """Define the steps for this saga."""
        pass
    
    def add_step(
        self,
        name: str,
        action: Callable,
        compensation: Optional[Callable] = None,
        timeout_seconds: int = 30,
        retry_count: int = 3,
    ) -> "Saga":
        """Add a step to the saga."""
        step = SagaStep(
            name=name,
            action=action,
            compensation=compensation,
            timeout_seconds=timeout_seconds,
            retry_count=retry_count,
        )
        self.steps.append(step)
        return self
    
    async def get_definition(self) -> SagaDefinition:
        """Get saga definition."""
        if not self.steps:
            self.steps = await self.define_steps()
        
        return SagaDefinition(
            saga_id=self.saga_id,
            name=self.name,
            steps=self.steps,
        )


class SagaOrchestrator:
    """Orchestrator for managing saga execution."""
    
    def __init__(self, event_store: Optional[EventStore] = None):
        self.event_store = event_store
        self.running_sagas: Dict[str, SagaExecution] = {}
        self._background_tasks: List[asyncio.Task] = []
        self._running = False
        
        logger.info("SagaOrchestrator initialized")
    
    async def start(self) -> None:
        """Start the saga orchestrator."""
        if self._running:
            return
        
        self._running = True
        
        # Start background monitoring task
        task = asyncio.create_task(self._monitor_sagas())
        self._background_tasks.append(task)
        
        logger.info("SagaOrchestrator started")
    
    async def stop(self) -> None:
        """Stop the saga orchestrator."""
        if not self._running:
            return
        
        self._running = False
        
        # Cancel background tasks
        for task in self._background_tasks:
            task.cancel()
        
        await asyncio.gather(*self._background_tasks, return_exceptions=True)
        self._background_tasks.clear()
        
        logger.info("SagaOrchestrator stopped")
    
    async def start_saga(self, saga: Saga, context: Optional[Dict[str, Any]] = None) -> SagaExecution:
        """Start executing a saga."""
        definition = await saga.get_definition()
        if context:
            definition.context.update(context)
        
        execution = SagaExecution(
            saga_id=definition.saga_id,
            definition=definition,
        )
        
        # Store in running sagas
        self.running_sagas[definition.saga_id] = execution
        
        # Start execution
        task = asyncio.create_task(self._execute_saga(execution))
        self._background_tasks.append(task)
        
        logger.info(f"Started saga: {definition.name} ({definition.saga_id})")
        return execution
    
    async def get_saga_status(self, saga_id: str) -> Optional[SagaExecution]:
        """Get status of a running saga."""
        return self.running_sagas.get(saga_id)
    
    async def cancel_saga(self, saga_id: str, reason: str = "Manual cancellation") -> bool:
        """Cancel a running saga."""
        execution = self.running_sagas.get(saga_id)
        if not execution:
            return False
        
        if execution.state in [SagaState.COMPLETED, SagaState.COMPENSATED, SagaState.FAILED]:
            return False
        
        # Mark as failed and start compensation
        execution.error = reason
        await self._start_compensation(execution)
        
        logger.info(f"Cancelled saga: {saga_id} - {reason}")
        return True
    
    async def _execute_saga(self, execution: SagaExecution) -> None:
        """Execute a saga."""
        try:
            execution.state = SagaState.RUNNING
            execution.started_at = datetime.utcnow()
            
            await self._persist_saga_event(execution, "saga_started")
            
            # Execute steps sequentially
            for i, step in enumerate(execution.definition.steps):
                execution.current_step_index = i
                
                success = await self._execute_step(execution, step)
                if not success:
                    # Step failed, start compensation
                    execution.error = f"Step {step.name} failed: {step.error}"
                    await self._start_compensation(execution)
                    return
            
            # All steps completed successfully
            execution.state = SagaState.COMPLETED
            execution.completed_at = datetime.utcnow()
            
            await self._persist_saga_event(execution, "saga_completed")
            logger.info(f"Saga completed successfully: {execution.saga_id}")
            
        except Exception as e:
            logger.error(f"Saga execution error: {e}")
            execution.state = SagaState.FAILED
            execution.error = str(e)
            await self._persist_saga_event(execution, "saga_failed")
        
        finally:
            # Remove from running sagas if completed/failed
            if execution.state in [SagaState.COMPLETED, SagaState.COMPENSATED, SagaState.FAILED]:
                self.running_sagas.pop(execution.saga_id, None)
    
    async def _execute_step(self, execution: SagaExecution, step: SagaStep) -> bool:
        """Execute a single saga step."""
        step.state = StepState.RUNNING
        step.started_at = datetime.utcnow()
        
        await self._persist_saga_event(execution, "step_started", {"step_name": step.name})
        
        for attempt in range(step.retry_count + 1):
            step.attempt_count = attempt + 1
            
            try:
                # Execute step action with timeout
                if asyncio.iscoroutinefunction(step.action):
                    result = await asyncio.wait_for(
                        step.action(execution.definition.context),
                        timeout=step.timeout_seconds
                    )
                else:
                    # Run sync action in executor
                    loop = asyncio.get_event_loop()
                    result = await asyncio.wait_for(
                        loop.run_in_executor(None, step.action, execution.definition.context),
                        timeout=step.timeout_seconds
                    )
                
                # Step succeeded
                step.state = StepState.COMPLETED
                step.completed_at = datetime.utcnow()
                step.result = result
                
                await self._persist_saga_event(
                    execution,
                    "step_completed",
                    {"step_name": step.name, "result": result}
                )
                
                logger.debug(f"Step completed: {step.name}")
                return True
                
            except asyncio.TimeoutError:
                error_msg = f"Step timeout after {step.timeout_seconds}s"
                step.error = error_msg
                logger.warning(f"Step {step.name} timed out (attempt {attempt + 1})")
                
            except Exception as e:
                error_msg = str(e)
                step.error = error_msg
                logger.warning(f"Step {step.name} failed (attempt {attempt + 1}): {error_msg}")
            
            # Retry delay (except for last attempt)
            if attempt < step.retry_count:
                await asyncio.sleep(step.retry_delay_seconds)
        
        # All retries exhausted
        step.state = StepState.FAILED
        step.completed_at = datetime.utcnow()
        
        await self._persist_saga_event(
            execution,
            "step_failed",
            {"step_name": step.name, "error": step.error}
        )
        
        return False
    
    async def _start_compensation(self, execution: SagaExecution) -> None:
        """Start compensation process for failed saga."""
        execution.state = SagaState.COMPENSATING
        execution.compensation_started_at = datetime.utcnow()
        
        await self._persist_saga_event(execution, "compensation_started")
        
        # Compensate completed steps in reverse order
        completed_steps = execution.get_completed_steps()
        
        for step in reversed(completed_steps):
            if step.compensation:
                success = await self._compensate_step(execution, step)
                if not success:
                    logger.error(f"Compensation failed for step: {step.name}")
                    # Continue with other compensations
        
        # Mark compensation as complete
        execution.state = SagaState.COMPENSATED
        execution.compensation_completed_at = datetime.utcnow()
        
        await self._persist_saga_event(execution, "compensation_completed")
        logger.info(f"Saga compensation completed: {execution.saga_id}")
    
    async def _compensate_step(self, execution: SagaExecution, step: SagaStep) -> bool:
        """Compensate a single step."""
        if not step.compensation:
            return True
        
        step.state = StepState.COMPENSATING
        
        await self._persist_saga_event(
            execution,
            "step_compensation_started",
            {"step_name": step.name}
        )
        
        try:
            # Execute compensation with timeout
            if asyncio.iscoroutinefunction(step.compensation):
                await asyncio.wait_for(
                    step.compensation(execution.definition.context, step.result),
                    timeout=step.timeout_seconds
                )
            else:
                # Run sync compensation in executor
                loop = asyncio.get_event_loop()
                await asyncio.wait_for(
                    loop.run_in_executor(
                        None,
                        step.compensation,
                        execution.definition.context,
                        step.result
                    ),
                    timeout=step.timeout_seconds
                )
            
            step.state = StepState.COMPENSATED
            
            await self._persist_saga_event(
                execution,
                "step_compensation_completed",
                {"step_name": step.name}
            )
            
            logger.debug(f"Step compensated: {step.name}")
            return True
            
        except Exception as e:
            step.state = StepState.FAILED
            logger.error(f"Compensation failed for step {step.name}: {e}")
            
            await self._persist_saga_event(
                execution,
                "step_compensation_failed",
                {"step_name": step.name, "error": str(e)}
            )
            
            return False
    
    async def _persist_saga_event(
        self,
        execution: SagaExecution,
        event_type: str,
        data: Optional[Dict[str, Any]] = None
    ) -> None:
        """Persist saga event for audit trail."""
        if not self.event_store:
            return
        
        event_data = {
            "saga_id": execution.saga_id,
            "saga_name": execution.definition.name,
            "saga_state": execution.state.value,
            "current_step_index": execution.current_step_index,
            **(data or {}),
        }
        
        event = Event(
            event_type=f"saga.{event_type}",
            data=event_data,
            metadata=EventMetadata(
                correlation_id=execution.saga_id,
                source="saga_orchestrator",
            ),
        )
        
        await self.event_store.store_event(event)
    
    async def _monitor_sagas(self) -> None:
        """Background task to monitor saga timeouts."""
        while self._running:
            try:
                await asyncio.sleep(30)  # Check every 30 seconds
                
                current_time = datetime.utcnow()
                
                # Check for timed out sagas
                timed_out_sagas = []
                for saga_id, execution in self.running_sagas.items():
                    if (execution.started_at and 
                        execution.state == SagaState.RUNNING and
                        (current_time - execution.started_at).total_seconds() > execution.definition.timeout_seconds):
                        timed_out_sagas.append(saga_id)
                
                # Cancel timed out sagas
                for saga_id in timed_out_sagas:
                    await self.cancel_saga(saga_id, "Saga timeout")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Saga monitor error: {e}")
    
    def get_running_sagas(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all running sagas."""
        return {
            saga_id: {
                "name": execution.definition.name,
                "state": execution.state.value,
                "current_step": execution.current_step_index,
                "total_steps": len(execution.definition.steps),
                "started_at": execution.started_at.isoformat() if execution.started_at else None,
                "error": execution.error,
            }
            for saga_id, execution in self.running_sagas.items()
        }


class SagaManager:
    """High-level saga management interface."""
    
    def __init__(self, orchestrator: SagaOrchestrator):
        self.orchestrator = orchestrator
        self._saga_definitions: Dict[str, type] = {}
    
    def register_saga(self, saga_class: type) -> None:
        """Register a saga class."""
        self._saga_definitions[saga_class.__name__] = saga_class
        logger.info(f"Registered saga: {saga_class.__name__}")
    
    async def start_saga(
        self,
        saga_name: str,
        context: Optional[Dict[str, Any]] = None,
        saga_id: Optional[str] = None,
    ) -> Optional[SagaExecution]:
        """Start a saga by name."""
        if saga_name not in self._saga_definitions:
            logger.error(f"Unknown saga: {saga_name}")
            return None
        
        # Create saga instance
        saga_id = saga_id or str(uuid.uuid4())
        saga_class = self._saga_definitions[saga_name]
        saga_instance = saga_class(saga_id, saga_name)
        
        # Start execution
        return await self.orchestrator.start_saga(saga_instance, context)
    
    def get_registered_sagas(self) -> List[str]:
        """Get list of registered saga names."""
        return list(self._saga_definitions.keys())


# Example saga implementations

class OrderProcessingSaga(Saga):
    """Example saga for order processing."""
    
    async def define_steps(self) -> List[SagaStep]:
        """Define order processing steps."""
        return [
            SagaStep(
                name="validate_order",
                action=self._validate_order,
                compensation=self._cancel_order_validation,
                timeout_seconds=10,
            ),
            SagaStep(
                name="reserve_inventory",
                action=self._reserve_inventory,
                compensation=self._release_inventory,
                timeout_seconds=30,
            ),
            SagaStep(
                name="process_payment",
                action=self._process_payment,
                compensation=self._refund_payment,
                timeout_seconds=60,
            ),
            SagaStep(
                name="ship_order",
                action=self._ship_order,
                compensation=self._cancel_shipment,
                timeout_seconds=120,
            ),
        ]
    
    async def _validate_order(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Validate order step."""
        order_id = context.get("order_id")
        logger.info(f"Validating order: {order_id}")
        
        # Simulate validation
        await asyncio.sleep(0.1)
        
        return {"validated": True, "order_id": order_id}
    
    async def _cancel_order_validation(self, context: Dict[str, Any], result: Any) -> None:
        """Cancel order validation step."""
        logger.info("Cancelling order validation")
        # Cleanup validation state
        
    async def _reserve_inventory(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Reserve inventory step."""
        items = context.get("items", [])
        logger.info(f"Reserving inventory for {len(items)} items")
        
        # Simulate inventory reservation
        await asyncio.sleep(0.2)
        
        return {"reserved_items": items, "reservation_id": str(uuid.uuid4())}
    
    async def _release_inventory(self, context: Dict[str, Any], result: Any) -> None:
        """Release inventory step."""
        reservation_id = result.get("reservation_id")
        logger.info(f"Releasing inventory reservation: {reservation_id}")
        
    async def _process_payment(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Process payment step."""
        amount = context.get("amount")
        logger.info(f"Processing payment: ${amount}")
        
        # Simulate payment processing
        await asyncio.sleep(0.3)
        
        return {"payment_id": str(uuid.uuid4()), "amount": amount}
    
    async def _refund_payment(self, context: Dict[str, Any], result: Any) -> None:
        """Refund payment step."""
        payment_id = result.get("payment_id")
        logger.info(f"Refunding payment: {payment_id}")
        
    async def _ship_order(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Ship order step."""
        order_id = context.get("order_id")
        logger.info(f"Shipping order: {order_id}")
        
        # Simulate shipping
        await asyncio.sleep(0.5)
        
        return {"tracking_number": f"TRACK_{uuid.uuid4().hex[:8].upper()}"}
    
    async def _cancel_shipment(self, context: Dict[str, Any], result: Any) -> None:
        """Cancel shipment step."""
        tracking_number = result.get("tracking_number")
        logger.info(f"Cancelling shipment: {tracking_number}")


class UserRegistrationSaga(Saga):
    """Example saga for user registration."""
    
    async def define_steps(self) -> List[SagaStep]:
        """Define user registration steps."""
        return [
            SagaStep(
                name="create_user_account",
                action=self._create_user_account,
                compensation=self._delete_user_account,
                timeout_seconds=15,
            ),
            SagaStep(
                name="send_welcome_email",
                action=self._send_welcome_email,
                compensation=None,  # No compensation needed for email
                timeout_seconds=30,
            ),
            SagaStep(
                name="create_default_preferences",
                action=self._create_default_preferences,
                compensation=self._delete_preferences,
                timeout_seconds=10,
            ),
        ]
    
    async def _create_user_account(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Create user account step."""
        email = context.get("email")
        logger.info(f"Creating user account: {email}")
        
        await asyncio.sleep(0.1)
        
        user_id = str(uuid.uuid4())
        return {"user_id": user_id, "email": email}
    
    async def _delete_user_account(self, context: Dict[str, Any], result: Any) -> None:
        """Delete user account step."""
        user_id = result.get("user_id")
        logger.info(f"Deleting user account: {user_id}")
        
    async def _send_welcome_email(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Send welcome email step."""
        email = context.get("email")
        logger.info(f"Sending welcome email to: {email}")
        
        await asyncio.sleep(0.2)
        
        return {"email_sent": True}
    
    async def _create_default_preferences(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Create default preferences step."""
        logger.info("Creating default user preferences")
        
        await asyncio.sleep(0.1)
        
        return {"preferences_created": True}
    
    async def _delete_preferences(self, context: Dict[str, Any], result: Any) -> None:
        """Delete preferences step."""
        logger.info("Deleting user preferences")