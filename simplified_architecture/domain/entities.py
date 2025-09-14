"""
Domain Entities - 핵심 비즈니스 객체
순수한 비즈니스 규칙만을 포함하며, 외부 의존성이 없음
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import List, Optional


class InvestmentSignal(Enum):
    """투자 신호"""
    STRONG_BUY = "STRONG_BUY"
    BUY = "BUY"
    HOLD = "HOLD"
    SELL = "SELL"
    STRONG_SELL = "STRONG_SELL"


class RiskLevel(Enum):
    """리스크 수준"""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    VERY_HIGH = "VERY_HIGH"


@dataclass(frozen=True)
class Stock:
    """주식 엔티티"""
    code: str
    name: str
    market: str
    sector: Optional[str] = None
    
    def __post_init__(self):
        if not self.code or len(self.code) != 6:
            raise ValueError("Stock code must be 6 digits")
        if not self.name:
            raise ValueError("Stock name is required")


@dataclass(frozen=True)
class MarketData:
    """시장 데이터"""
    stock_code: str
    current_price: Decimal
    volume: int
    market_cap: Optional[Decimal]
    timestamp: datetime
    
    def price_change_rate(self, previous_price: Decimal) -> Decimal:
        """가격 변화율 계산"""
        if previous_price <= 0:
            raise ValueError("Previous price must be positive")
        return (self.current_price - previous_price) / previous_price * 100


@dataclass(frozen=True)
class AnalysisResult:
    """분석 결과"""
    stock_code: str
    signal: InvestmentSignal
    confidence: float  # 0.0 ~ 1.0
    target_price: Optional[Decimal]
    reasoning: str
    analyzed_at: datetime
    
    def __post_init__(self):
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("Confidence must be between 0.0 and 1.0")
        if self.target_price and self.target_price <= 0:
            raise ValueError("Target price must be positive")


@dataclass(frozen=True)
class InvestmentDecision:
    """투자 결정"""
    stock_code: str
    action: InvestmentSignal
    quantity: int
    max_price: Optional[Decimal]
    risk_level: RiskLevel
    requires_human_approval: bool
    analysis_result: AnalysisResult
    
    def calculate_investment_amount(self, current_price: Decimal) -> Decimal:
        """투자 금액 계산"""
        price_to_use = min(self.max_price or current_price, current_price)
        return Decimal(self.quantity) * price_to_use
    
    def is_high_risk(self, investment_amount: Decimal, 
                    max_position_size: Decimal = Decimal('10000000')) -> bool:
        """고위험 여부 판단"""
        return (
            self.risk_level in [RiskLevel.HIGH, RiskLevel.VERY_HIGH] or
            investment_amount > max_position_size or
            self.analysis_result.confidence < 0.6
        )


# Domain Services - 비즈니스 로직을 캡슐화
class RiskCalculator:
    """리스크 계산 도메인 서비스"""
    
    @staticmethod
    def calculate_var(
        portfolio_value: Decimal,
        volatility: float,
        confidence_level: float = 0.95,
        holding_period: int = 1
    ) -> Decimal:
        """VaR (Value at Risk) 계산"""
        import math
        
        if volatility < 0:
            raise ValueError("Volatility cannot be negative")
        if not 0 < confidence_level < 1:
            raise ValueError("Confidence level must be between 0 and 1")
            
        # Z-score for confidence level (simplified)
        z_scores = {0.90: 1.28, 0.95: 1.65, 0.99: 2.33}
        z_score = z_scores.get(confidence_level, 1.65)
        
        # VaR = Portfolio Value × Z-score × Volatility × √Time
        var = portfolio_value * Decimal(str(z_score)) * Decimal(str(volatility)) * Decimal(str(math.sqrt(holding_period)))
        return var.quantize(Decimal('0.01'))
    
    @staticmethod
    def determine_risk_level(
        confidence: float,
        investment_ratio: float,  # 전체 포트폴리오 대비 비율
        market_volatility: float
    ) -> RiskLevel:
        """리스크 수준 결정"""
        risk_score = (
            (1 - confidence) * 0.4 +
            investment_ratio * 0.4 +
            market_volatility * 0.2
        )
        
        if risk_score >= 0.8:
            return RiskLevel.VERY_HIGH
        elif risk_score >= 0.6:
            return RiskLevel.HIGH
        elif risk_score >= 0.3:
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW


# Domain Events - 도메인에서 발생하는 이벤트
@dataclass(frozen=True)
class DomainEvent(ABC):
    """도메인 이벤트 기본 클래스"""
    occurred_at: datetime
    event_id: str


@dataclass(frozen=True)
class AnalysisCompleted(DomainEvent):
    """분석 완료 이벤트"""
    stock_code: str
    analysis_result: AnalysisResult


@dataclass(frozen=True)
class HumanApprovalRequired(DomainEvent):
    """인간 승인 필요 이벤트"""
    investment_decision: InvestmentDecision
    risk_factors: List[str]


@dataclass(frozen=True)
class TradeExecuted(DomainEvent):
    """거래 실행 이벤트"""
    stock_code: str
    action: InvestmentSignal
    quantity: int
    executed_price: Decimal
    total_amount: Decimal