"""
Universal Domain Abstractions - 범용 비즈니스 추상화
어떤 도메인에든 적용 가능한 신화급 설계 패턴

Design Principles:
- Domain Agnostic: 특정 도메인에 의존하지 않음
- Event-Driven: 모든 변경사항은 이벤트로 처리
- CQRS: Command와 Query 분리
- DDD: 풍부한 도메인 모델
- Extensible: 플러그인으로 확장 가능
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, Generic, List, Optional, Protocol, TypeVar, Union
from uuid import UUID, uuid4
import asyncio
from collections.abc import Awaitable


# ===== 기본 타입 정의 =====
EntityId = TypeVar('EntityId', bound=Union[UUID, str, int])
T = TypeVar('T')
E = TypeVar('E')


class Priority(Enum):
    """우선순위"""
    LOWEST = 1
    LOW = 2
    NORMAL = 3
    HIGH = 4
    HIGHEST = 5
    CRITICAL = 6


class Status(Enum):
    """범용 상태"""
    DRAFT = "DRAFT"
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"
    ARCHIVED = "ARCHIVED"


# ===== 결과 패턴 =====
@dataclass(frozen=True)
class Result(Generic[T, E]):
    """범용 결과 패턴"""
    success: bool
    data: Optional[T] = None
    error: Optional[E] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def ok(cls, data: T, metadata: Dict[str, Any] = None) -> 'Result[T, E]':
        """성공 결과 생성"""
        return cls(success=True, data=data, metadata=metadata or {})
    
    @classmethod
    def fail(cls, error: E, metadata: Dict[str, Any] = None) -> 'Result[T, E]':
        """실패 결과 생성"""
        return cls(success=False, error=error, metadata=metadata or {})
    
    def map(self, func) -> 'Result':
        """함수형 변환"""
        if self.success and self.data is not None:
            try:
                return Result.ok(func(self.data), self.metadata)
            except Exception as e:
                return Result.fail(e, self.metadata)
        return self
    
    def flat_map(self, func) -> 'Result':
        """Monad bind 연산"""
        if self.success and self.data is not None:
            return func(self.data)
        return self


# ===== 도메인 이벤트 =====
@dataclass(frozen=True)
class DomainEvent(ABC):
    """범용 도메인 이벤트"""
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=datetime.now)
    event_type: str = field(init=False)
    aggregate_id: EntityId = field(default=None)
    aggregate_type: str = field(default="")
    version: int = field(default=1)
    correlation_id: Optional[UUID] = None
    causation_id: Optional[UUID] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        object.__setattr__(self, 'event_type', self.__class__.__name__)


# ===== 집합근 (Aggregate Root) =====
class AggregateRoot(ABC, Generic[EntityId]):
    """범용 집합근 기본 클래스"""
    
    def __init__(self, entity_id: EntityId):
        self._id = entity_id
        self._version = 0
        self._events: List[DomainEvent] = []
        self._created_at = datetime.now()
        self._updated_at = datetime.now()
    
    @property
    def id(self) -> EntityId:
        return self._id
    
    @property
    def version(self) -> int:
        return self._version
    
    @property
    def created_at(self) -> datetime:
        return self._created_at
    
    @property
    def updated_at(self) -> datetime:
        return self._updated_at
    
    def get_uncommitted_events(self) -> List[DomainEvent]:
        """커밋되지 않은 이벤트 조회"""
        return self._events.copy()
    
    def mark_events_as_committed(self):
        """이벤트를 커밋됨으로 표시"""
        self._events.clear()
    
    def increment_version(self):
        """버전 증가"""
        self._version += 1
        self._updated_at = datetime.now()
    
    def _add_event(self, event: DomainEvent):
        """이벤트 추가"""
        # aggregate_id와 aggregate_type 자동 설정
        if event.aggregate_id is None:
            object.__setattr__(event, 'aggregate_id', self._id)
        if not event.aggregate_type:
            object.__setattr__(event, 'aggregate_type', self.__class__.__name__)
        
        self._events.append(event)
        self.increment_version()


# ===== 값 객체 =====
@dataclass(frozen=True)
class ValueObject(ABC):
    """범용 값 객체 기본 클래스"""
    
    def __post_init__(self):
        self.validate()
    
    @abstractmethod
    def validate(self):
        """값 객체 유효성 검증"""
        pass


@dataclass(frozen=True)
class Money(ValueObject):
    """범용 화폐 값 객체"""
    amount: Decimal
    currency: str = "USD"
    
    def validate(self):
        if self.amount < 0:
            raise ValueError("Money amount cannot be negative")
        if not self.currency or len(self.currency) != 3:
            raise ValueError("Currency must be 3-character code")
    
    def add(self, other: 'Money') -> 'Money':
        if self.currency != other.currency:
            raise ValueError("Cannot add different currencies")
        return Money(self.amount + other.amount, self.currency)
    
    def subtract(self, other: 'Money') -> 'Money':
        if self.currency != other.currency:
            raise ValueError("Cannot subtract different currencies")
        return Money(self.amount - other.amount, self.currency)
    
    def multiply(self, factor: Union[int, float, Decimal]) -> 'Money':
        return Money(self.amount * Decimal(str(factor)), self.currency)
    
    def divide(self, divisor: Union[int, float, Decimal]) -> 'Money':
        if divisor == 0:
            raise ValueError("Cannot divide by zero")
        return Money(self.amount / Decimal(str(divisor)), self.currency)


@dataclass(frozen=True)
class Percentage(ValueObject):
    """범용 퍼센트 값 객체"""
    value: float  # 0.0 ~ 1.0
    
    def validate(self):
        if not 0.0 <= self.value <= 1.0:
            raise ValueError("Percentage must be between 0.0 and 1.0")
    
    @classmethod
    def from_percent(cls, percent: float) -> 'Percentage':
        """퍼센트 값으로부터 생성 (0~100)"""
        return cls(percent / 100.0)
    
    def to_percent(self) -> float:
        """퍼센트 값으로 변환 (0~100)"""
        return self.value * 100.0
    
    def apply_to(self, amount: Decimal) -> Decimal:
        """금액에 퍼센트 적용"""
        return amount * Decimal(str(self.value))


# ===== 범용 엔티티 =====
@dataclass(frozen=True)
class Address(ValueObject):
    """범용 주소 값 객체"""
    street: str
    city: str
    state: str
    country: str
    postal_code: str
    
    def validate(self):
        if not all([self.street, self.city, self.country]):
            raise ValueError("Street, city, and country are required")


@dataclass(frozen=True)
class ContactInfo(ValueObject):
    """범용 연락처 정보"""
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[Address] = None
    
    def validate(self):
        if self.email and '@' not in self.email:
            raise ValueError("Invalid email format")
        if not any([self.email, self.phone, self.address]):
            raise ValueError("At least one contact method is required")


# ===== 범용 비즈니스 추상화 =====
class BusinessEntity(AggregateRoot[UUID]):
    """범용 비즈니스 엔티티"""
    
    def __init__(
        self,
        entity_id: UUID = None,
        name: str = "",
        description: str = "",
        status: Status = Status.DRAFT,
        priority: Priority = Priority.NORMAL,
        tags: List[str] = None,
        metadata: Dict[str, Any] = None
    ):
        super().__init__(entity_id or uuid4())
        self._name = name
        self._description = description
        self._status = status
        self._priority = priority
        self._tags = tags or []
        self._metadata = metadata or {}
    
    @property
    def name(self) -> str:
        return self._name
    
    @property
    def description(self) -> str:
        return self._description
    
    @property
    def status(self) -> Status:
        return self._status
    
    @property
    def priority(self) -> Priority:
        return self._priority
    
    @property
    def tags(self) -> List[str]:
        return self._tags.copy()
    
    @property
    def metadata(self) -> Dict[str, Any]:
        return self._metadata.copy()
    
    def update_status(self, new_status: Status, reason: str = ""):
        """상태 변경"""
        if self._status != new_status:
            old_status = self._status
            self._status = new_status
            
            # 상태 변경 이벤트 발행
            self._add_event(StatusChanged(
                entity_id=self._id,
                old_status=old_status.value,
                new_status=new_status.value,
                reason=reason
            ))
    
    def add_tag(self, tag: str):
        """태그 추가"""
        if tag not in self._tags:
            self._tags.append(tag)
            self._add_event(TagAdded(entity_id=self._id, tag=tag))
    
    def remove_tag(self, tag: str):
        """태그 제거"""
        if tag in self._tags:
            self._tags.remove(tag)
            self._add_event(TagRemoved(entity_id=self._id, tag=tag))
    
    def update_metadata(self, key: str, value: Any):
        """메타데이터 업데이트"""
        old_value = self._metadata.get(key)
        self._metadata[key] = value
        
        if old_value != value:
            self._add_event(MetadataUpdated(
                entity_id=self._id,
                key=key,
                old_value=old_value,
                new_value=value
            ))


# ===== 범용 도메인 이벤트들 =====
@dataclass(frozen=True)
class StatusChanged(DomainEvent):
    """상태 변경 이벤트"""
    entity_id: UUID
    old_status: str
    new_status: str
    reason: str = ""


@dataclass(frozen=True)
class TagAdded(DomainEvent):
    """태그 추가 이벤트"""
    entity_id: UUID
    tag: str


@dataclass(frozen=True)
class TagRemoved(DomainEvent):
    """태그 제거 이벤트"""
    entity_id: UUID
    tag: str


@dataclass(frozen=True)
class MetadataUpdated(DomainEvent):
    """메타데이터 업데이트 이벤트"""
    entity_id: UUID
    key: str
    old_value: Any
    new_value: Any


# ===== 범용 저장소 인터페이스 =====
class Repository(ABC, Generic[T, EntityId]):
    """범용 저장소 인터페이스"""
    
    @abstractmethod
    async def find_by_id(self, entity_id: EntityId) -> Optional[T]:
        """ID로 엔티티 조회"""
        pass
    
    @abstractmethod
    async def find_all(
        self, 
        filters: Dict[str, Any] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[T]:
        """조건에 따른 엔티티 목록 조회"""
        pass
    
    @abstractmethod
    async def save(self, entity: T) -> Result[T, Exception]:
        """엔티티 저장"""
        pass
    
    @abstractmethod
    async def delete(self, entity_id: EntityId) -> Result[bool, Exception]:
        """엔티티 삭제"""
        pass
    
    @abstractmethod
    async def exists(self, entity_id: EntityId) -> bool:
        """엔티티 존재 여부 확인"""
        pass
    
    @abstractmethod
    async def count(self, filters: Dict[str, Any] = None) -> int:
        """조건에 맞는 엔티티 개수"""
        pass


# ===== 범용 쿼리 인터페이스 =====
@dataclass(frozen=True)
class QuerySpec:
    """범용 쿼리 명세"""
    filters: Dict[str, Any] = field(default_factory=dict)
    sorts: List[tuple] = field(default_factory=list)  # (field, direction)
    limit: Optional[int] = None
    offset: int = 0
    include_fields: Optional[List[str]] = None
    exclude_fields: Optional[List[str]] = None


class QueryHandler(ABC, Generic[T]):
    """범용 쿼리 핸들러"""
    
    @abstractmethod
    async def handle(self, query_spec: QuerySpec) -> Result[List[T], Exception]:
        """쿼리 처리"""
        pass


# ===== 범용 커맨드 인터페이스 =====
@dataclass(frozen=True)
class Command(ABC):
    """범용 커맨드"""
    command_id: UUID = field(default_factory=uuid4)
    issued_at: datetime = field(default_factory=datetime.now)
    issued_by: Optional[str] = None
    correlation_id: Optional[UUID] = None


class CommandHandler(ABC, Generic[T]):
    """범용 커맨드 핸들러"""
    
    @abstractmethod
    async def handle(self, command: Command) -> Result[T, Exception]:
        """커맨드 처리"""
        pass


# ===== 범용 이벤트 시스템 =====
class EventHandler(Protocol):
    """이벤트 핸들러 프로토콜"""
    async def handle(self, event: DomainEvent) -> None: ...


class EventBus(ABC):
    """범용 이벤트 버스"""
    
    @abstractmethod
    async def publish(self, event: DomainEvent) -> None:
        """이벤트 발행"""
        pass
    
    @abstractmethod
    def subscribe(
        self, 
        event_type: type, 
        handler: EventHandler,
        priority: Priority = Priority.NORMAL
    ) -> None:
        """이벤트 구독"""
        pass
    
    @abstractmethod
    def unsubscribe(self, event_type: type, handler: EventHandler) -> None:
        """이벤트 구독 해제"""
        pass


# ===== 범용 작업 단위 =====
class UnitOfWork(ABC):
    """범용 작업 단위 패턴"""
    
    def __init__(self):
        self._repositories = {}
        self._events = []
    
    @abstractmethod
    async def begin(self) -> None:
        """트랜잭션 시작"""
        pass
    
    @abstractmethod
    async def commit(self) -> None:
        """변경사항 커밋 및 이벤트 발행"""
        pass
    
    @abstractmethod
    async def rollback(self) -> None:
        """변경사항 롤백"""
        pass
    
    def register_repository(self, name: str, repository: Repository):
        """저장소 등록"""
        self._repositories[name] = repository
    
    def get_repository(self, name: str) -> Repository:
        """저장소 조회"""
        return self._repositories.get(name)
    
    def add_event(self, event: DomainEvent):
        """이벤트 추가"""
        self._events.append(event)
    
    async def __aenter__(self):
        await self.begin()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            await self.commit()
        else:
            await self.rollback()


# ===== 범용 도메인 서비스 =====
class DomainService(ABC):
    """범용 도메인 서비스"""
    
    def __init__(self, name: str):
        self._name = name
    
    @property
    def name(self) -> str:
        return self._name


# ===== 범용 애플리케이션 서비스 =====
class ApplicationService(ABC):
    """범용 애플리케이션 서비스"""
    
    def __init__(
        self,
        uow: UnitOfWork,
        event_bus: EventBus,
        name: str = ""
    ):
        self._uow = uow
        self._event_bus = event_bus
        self._name = name or self.__class__.__name__
    
    @property
    def name(self) -> str:
        return self._name
    
    async def _publish_events(self, aggregate: AggregateRoot):
        """집합근의 이벤트 발행"""
        events = aggregate.get_uncommitted_events()
        for event in events:
            await self._event_bus.publish(event)
        aggregate.mark_events_as_committed()


# ===== 범용 명세 패턴 =====
class Specification(ABC, Generic[T]):
    """범용 명세 패턴"""
    
    @abstractmethod
    def is_satisfied_by(self, candidate: T) -> bool:
        """명세 만족 여부 확인"""
        pass
    
    def and_(self, other: 'Specification[T]') -> 'Specification[T]':
        """AND 연산"""
        return AndSpecification(self, other)
    
    def or_(self, other: 'Specification[T]') -> 'Specification[T]':
        """OR 연산"""
        return OrSpecification(self, other)
    
    def not_(self) -> 'Specification[T]':
        """NOT 연산"""
        return NotSpecification(self)


class AndSpecification(Specification[T]):
    """AND 명세"""
    def __init__(self, left: Specification[T], right: Specification[T]):
        self._left = left
        self._right = right
    
    def is_satisfied_by(self, candidate: T) -> bool:
        return self._left.is_satisfied_by(candidate) and self._right.is_satisfied_by(candidate)


class OrSpecification(Specification[T]):
    """OR 명세"""
    def __init__(self, left: Specification[T], right: Specification[T]):
        self._left = left
        self._right = right
    
    def is_satisfied_by(self, candidate: T) -> bool:
        return self._left.is_satisfied_by(candidate) or self._right.is_satisfied_by(candidate)


class NotSpecification(Specification[T]):
    """NOT 명세"""
    def __init__(self, spec: Specification[T]):
        self._spec = spec
    
    def is_satisfied_by(self, candidate: T) -> bool:
        return not self._spec.is_satisfied_by(candidate)