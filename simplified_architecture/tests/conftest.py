"""
Pytest configuration and shared fixtures for simplified architecture tests.
"""

import asyncio
import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Optional, Dict, Any
from unittest.mock import AsyncMock, Mock, MagicMock

# Import domain entities and interfaces
from simplified_architecture.domain.entities import (
    Stock,
    MarketData,
    AnalysisResult,
    InvestmentDecision,
    InvestmentSignal,
    RiskLevel,
    RiskCalculator,
    AnalysisCompleted,
    HumanApprovalRequired,
    TradeExecuted,
)
from simplified_architecture.domain.repositories import (
    StockRepository,
    MarketDataRepository,
    NewsRepository,
    AnalysisRepository,
    TradingRepository,
)
from simplified_architecture.application.use_cases import (
    EventPublisher,
    HumanApprovalService,
    LLMService,
)
from simplified_architecture.infrastructure.adapters import (
    CircuitBreaker,
    CircuitBreakerConfig,
    InMemoryCache,
    MockTradingRepository,
    InMemoryAnalysisRepository,
)


# Pytest event loop configuration
@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# Domain Entity Fixtures
@pytest.fixture
def sample_stock():
    """Sample stock entity for testing."""
    return Stock(
        code="005930",
        name="삼성전자",
        market="KOSPI",
        sector="반도체"
    )


@pytest.fixture
def sample_market_data():
    """Sample market data entity for testing."""
    return MarketData(
        stock_code="005930",
        current_price=Decimal("75000"),
        volume=1000000,
        market_cap=Decimal("450000000000000"),  # 450조원
        timestamp=datetime.now()
    )


@pytest.fixture
def sample_analysis_result():
    """Sample analysis result entity for testing."""
    return AnalysisResult(
        stock_code="005930",
        signal=InvestmentSignal.BUY,
        confidence=0.8,
        target_price=Decimal("80000"),
        reasoning="Strong fundamentals and positive market outlook",
        analyzed_at=datetime.now()
    )


@pytest.fixture
def sample_investment_decision(sample_analysis_result):
    """Sample investment decision entity for testing."""
    return InvestmentDecision(
        stock_code="005930",
        action=InvestmentSignal.BUY,
        quantity=100,
        max_price=Decimal("76000"),
        risk_level=RiskLevel.MEDIUM,
        requires_human_approval=False,
        analysis_result=sample_analysis_result
    )


# Mock Repository Fixtures
@pytest.fixture
def mock_stock_repo():
    """Mock stock repository."""
    repo = Mock(spec=StockRepository)
    repo.find_by_code = AsyncMock()
    repo.find_by_sector = AsyncMock()
    repo.search_by_name = AsyncMock()
    return repo


@pytest.fixture
def mock_market_data_repo():
    """Mock market data repository."""
    repo = Mock(spec=MarketDataRepository)
    repo.get_current_data = AsyncMock()
    repo.get_historical_data = AsyncMock()
    repo.get_volume_profile = AsyncMock()
    return repo


@pytest.fixture
def mock_news_repo():
    """Mock news repository."""
    repo = Mock(spec=NewsRepository)
    repo.get_stock_news = AsyncMock()
    repo.get_market_sentiment = AsyncMock()
    return repo


@pytest.fixture
def mock_analysis_repo():
    """Mock analysis repository."""
    repo = Mock(spec=AnalysisRepository)
    repo.save_analysis = AsyncMock()
    repo.find_latest_analysis = AsyncMock()
    repo.find_analysis_history = AsyncMock()
    return repo


@pytest.fixture
def mock_trading_repo():
    """Mock trading repository."""
    repo = Mock(spec=TradingRepository)
    repo.execute_order = AsyncMock()
    repo.get_account_balance = AsyncMock()
    repo.get_portfolio_positions = AsyncMock()
    repo.cancel_order = AsyncMock()
    return repo


# Mock Service Fixtures
@pytest.fixture
def mock_event_publisher():
    """Mock event publisher."""
    publisher = Mock(spec=EventPublisher)
    publisher.publish = AsyncMock()
    return publisher


@pytest.fixture
def mock_human_approval_service():
    """Mock human approval service."""
    service = Mock(spec=HumanApprovalService)
    service.request_approval = AsyncMock()
    return service


@pytest.fixture
def mock_llm_service():
    """Mock LLM service."""
    service = Mock(spec=LLMService)
    service.analyze_stock = AsyncMock()
    return service


# Infrastructure Component Fixtures
@pytest.fixture
def circuit_breaker():
    """Circuit breaker instance for testing."""
    config = CircuitBreakerConfig(
        failure_threshold=3,
        timeout=30,
        retry_timeout=15
    )
    return CircuitBreaker(config)


@pytest.fixture
def in_memory_cache():
    """In-memory cache instance for testing."""
    return InMemoryCache()


@pytest.fixture
def mock_trading_repo_instance():
    """Real MockTradingRepository instance for integration testing."""
    return MockTradingRepository()


@pytest.fixture
def in_memory_analysis_repo():
    """Real InMemoryAnalysisRepository instance for integration testing."""
    return InMemoryAnalysisRepository()


# Risk Calculator Fixture
@pytest.fixture
def risk_calculator():
    """Risk calculator instance for testing."""
    return RiskCalculator()


# Data Generators
@pytest.fixture
def stock_data_generator():
    """Generator for stock test data."""
    def generate_stock(code="005930", name="삼성전자", market="KOSPI", sector="반도체"):
        return Stock(code=code, name=name, market=market, sector=sector)
    return generate_stock


@pytest.fixture
def market_data_generator():
    """Generator for market data test data."""
    def generate_market_data(
        stock_code="005930",
        price=75000,
        volume=1000000,
        market_cap=None,
        timestamp=None
    ):
        return MarketData(
            stock_code=stock_code,
            current_price=Decimal(str(price)),
            volume=volume,
            market_cap=Decimal(str(market_cap)) if market_cap else None,
            timestamp=timestamp or datetime.now()
        )
    return generate_market_data


@pytest.fixture
def analysis_result_generator():
    """Generator for analysis result test data."""
    def generate_analysis_result(
        stock_code="005930",
        signal=InvestmentSignal.BUY,
        confidence=0.8,
        target_price=80000,
        reasoning="Test analysis",
        analyzed_at=None
    ):
        return AnalysisResult(
            stock_code=stock_code,
            signal=signal,
            confidence=confidence,
            target_price=Decimal(str(target_price)) if target_price else None,
            reasoning=reasoning,
            analyzed_at=analyzed_at or datetime.now()
        )
    return generate_analysis_result


# Async Context Managers for Testing
@pytest.fixture
async def async_context_manager():
    """Helper for testing async context managers."""
    class AsyncContextManager:
        def __init__(self, return_value):
            self.return_value = return_value
            self.entered = False
            self.exited = False
        
        async def __aenter__(self):
            self.entered = True
            return self.return_value
        
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            self.exited = True
            return False
    
    return AsyncContextManager


# Parameterized Test Data
@pytest.fixture
def investment_signals():
    """All investment signal enum values for parameterized tests."""
    return [
        InvestmentSignal.STRONG_BUY,
        InvestmentSignal.BUY,
        InvestmentSignal.HOLD,
        InvestmentSignal.SELL,
        InvestmentSignal.STRONG_SELL,
    ]


@pytest.fixture
def risk_levels():
    """All risk level enum values for parameterized tests."""
    return [
        RiskLevel.LOW,
        RiskLevel.MEDIUM,
        RiskLevel.HIGH,
        RiskLevel.VERY_HIGH,
    ]


@pytest.fixture
def confidence_values():
    """Various confidence values for testing."""
    return [0.0, 0.1, 0.5, 0.8, 0.9, 1.0]


@pytest.fixture
def price_values():
    """Various price values for testing."""
    return [
        Decimal("1000"),
        Decimal("10000"),
        Decimal("50000"),
        Decimal("100000"),
        Decimal("500000"),
    ]


# Exception Fixtures for Error Testing
@pytest.fixture
def common_exceptions():
    """Common exceptions for testing error handling."""
    return [
        ValueError("Test value error"),
        RuntimeError("Test runtime error"),
        ConnectionError("Test connection error"),
        TimeoutError("Test timeout error"),
    ]


# Time-based fixtures
@pytest.fixture
def time_points():
    """Various time points for testing."""
    now = datetime.now()
    return {
        "now": now,
        "hour_ago": now - timedelta(hours=1),
        "day_ago": now - timedelta(days=1),
        "week_ago": now - timedelta(weeks=1),
        "month_ago": now - timedelta(days=30),
    }


# Test data validation helpers
@pytest.fixture
def validation_helpers():
    """Helper functions for validation testing."""
    class ValidationHelpers:
        @staticmethod
        def is_valid_stock_code(code: str) -> bool:
            """Check if stock code is valid format."""
            return isinstance(code, str) and len(code) == 6 and code.isdigit()
        
        @staticmethod
        def is_valid_confidence(confidence: float) -> bool:
            """Check if confidence is in valid range."""
            return 0.0 <= confidence <= 1.0
        
        @staticmethod
        def is_positive_decimal(value: Decimal) -> bool:
            """Check if decimal value is positive."""
            return value > 0
        
        @staticmethod
        def is_recent_timestamp(timestamp: datetime, minutes: int = 5) -> bool:
            """Check if timestamp is recent."""
            return datetime.now() - timestamp <= timedelta(minutes=minutes)
    
    return ValidationHelpers()


# Performance testing fixtures
@pytest.fixture
def performance_thresholds():
    """Performance thresholds for testing."""
    return {
        "fast_operation": 0.1,  # 100ms
        "medium_operation": 1.0,  # 1 second
        "slow_operation": 5.0,  # 5 seconds
    }


# Cleanup fixture
@pytest.fixture(autouse=True)
async def cleanup():
    """Automatic cleanup after each test."""
    yield
    # Cleanup code can be added here if needed
    # For example, clearing caches, resetting mocks, etc.