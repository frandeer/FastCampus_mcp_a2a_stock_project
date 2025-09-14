"""
Comprehensive unit tests for infrastructure layer adapters.
Tests cover circuit breaker functionality, caching, repository implementations,
and resilient HTTP clients.
"""

import pytest
import asyncio
import aiohttp
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, Mock, patch, MagicMock
import json

from simplified_architecture.domain.entities import (
    Stock,
    MarketData,
    AnalysisResult,
    InvestmentDecision,
    InvestmentSignal,
    RiskLevel,
)
from simplified_architecture.infrastructure.adapters import (
    CircuitBreaker,
    CircuitBreakerState,
    CircuitBreakerConfig,
    InMemoryCache,
    CacheEntry,
    ResilientHTTPClient,
    KiwoomStockRepository,
    KiwoomMarketDataRepository,
    MockTradingRepository,
    InMemoryAnalysisRepository,
)


class TestCircuitBreaker:
    """Tests for Circuit Breaker pattern implementation."""
    
    def test_circuit_breaker_initial_state(self, circuit_breaker):
        """Test circuit breaker initial state."""
        assert circuit_breaker.state == CircuitBreakerState.CLOSED
        assert circuit_breaker.failure_count == 0
        assert circuit_breaker.last_failure_time is None
        assert circuit_breaker.can_execute() is True
    
    def test_circuit_breaker_success_handling(self, circuit_breaker):
        """Test circuit breaker success handling."""
        # Simulate some failures first
        for _ in range(2):
            circuit_breaker.on_failure()
        
        assert circuit_breaker.failure_count == 2
        
        # Success should reset failure count
        circuit_breaker.on_success()
        assert circuit_breaker.failure_count == 0
        assert circuit_breaker.state == CircuitBreakerState.CLOSED
    
    def test_circuit_breaker_failure_threshold(self):
        """Test circuit breaker opens after reaching failure threshold."""
        config = CircuitBreakerConfig(failure_threshold=3, retry_timeout=30)
        cb = CircuitBreaker(config)
        
        # Should be closed initially
        assert cb.state == CircuitBreakerState.CLOSED
        assert cb.can_execute() is True
        
        # Simulate failures up to threshold
        for i in range(2):
            cb.on_failure()
            assert cb.state == CircuitBreakerState.CLOSED
            assert cb.can_execute() is True
        
        # Third failure should open circuit
        cb.on_failure()
        assert cb.state == CircuitBreakerState.OPEN
        assert cb.can_execute() is False
    
    def test_circuit_breaker_half_open_transition(self):
        """Test circuit breaker transitions to half-open after timeout."""
        config = CircuitBreakerConfig(failure_threshold=2, retry_timeout=1)  # 1 second timeout
        cb = CircuitBreaker(config)
        
        # Force circuit to open
        cb.on_failure()
        cb.on_failure()
        assert cb.state == CircuitBreakerState.OPEN
        
        # Should not be able to execute immediately
        assert cb.can_execute() is False
        
        # Wait for retry timeout (simulate by setting next_attempt)
        cb.next_attempt = datetime.now() - timedelta(seconds=1)
        
        # Should transition to half-open and allow execution
        assert cb.can_execute() is True
        assert cb.state == CircuitBreakerState.HALF_OPEN
    
    def test_circuit_breaker_half_open_success(self):
        """Test circuit breaker closes from half-open on success."""
        config = CircuitBreakerConfig(failure_threshold=2)
        cb = CircuitBreaker(config)
        
        # Force to half-open state
        cb.state = CircuitBreakerState.HALF_OPEN
        
        # Success should close the circuit
        cb.on_success()
        assert cb.state == CircuitBreakerState.CLOSED
        assert cb.failure_count == 0
    
    def test_circuit_breaker_half_open_failure(self):
        """Test circuit breaker reopens from half-open on failure."""
        config = CircuitBreakerConfig(failure_threshold=1, retry_timeout=30)
        cb = CircuitBreaker(config)
        
        # Force to half-open state
        cb.state = CircuitBreakerState.HALF_OPEN
        cb.failure_count = 0  # Reset count
        
        # Failure should reopen circuit
        cb.on_failure()
        assert cb.state == CircuitBreakerState.OPEN
        assert cb.can_execute() is False
    
    def test_circuit_breaker_config_validation(self):
        """Test circuit breaker configuration."""
        config = CircuitBreakerConfig(
            failure_threshold=10,
            timeout=120,
            retry_timeout=60
        )
        
        cb = CircuitBreaker(config)
        assert cb.config.failure_threshold == 10
        assert cb.config.timeout == 120
        assert cb.config.retry_timeout == 60


class TestInMemoryCache:
    """Tests for In-Memory Cache implementation."""
    
    @pytest.mark.asyncio
    async def test_cache_basic_operations(self, in_memory_cache):
        """Test basic cache set/get operations."""
        # Test cache miss
        result = await in_memory_cache.get("nonexistent")
        assert result is None
        
        # Test cache set and hit
        test_data = {"key": "value", "number": 42}
        await in_memory_cache.set("test_key", test_data, ttl=300)
        
        cached_result = await in_memory_cache.get("test_key")
        assert cached_result == test_data
    
    @pytest.mark.asyncio
    async def test_cache_expiration(self, in_memory_cache):
        """Test cache entry expiration."""
        # Set with very short TTL
        await in_memory_cache.set("short_lived", "data", ttl=1)
        
        # Should be available immediately
        result = await in_memory_cache.get("short_lived")
        assert result == "data"
        
        # Wait for expiration
        await asyncio.sleep(1.1)
        
        # Should be expired and return None
        result = await in_memory_cache.get("short_lived")
        assert result is None
    
    @pytest.mark.asyncio
    async def test_cache_invalidation_pattern(self, in_memory_cache):
        """Test cache invalidation with pattern."""
        # Set multiple cache entries
        await in_memory_cache.set("user_1_profile", {"name": "User1"})
        await in_memory_cache.set("user_2_profile", {"name": "User2"})
        await in_memory_cache.set("system_config", {"setting": "value"})
        
        # Invalidate entries matching pattern
        await in_memory_cache.invalidate("user_")
        
        # User profiles should be invalidated
        assert await in_memory_cache.get("user_1_profile") is None
        assert await in_memory_cache.get("user_2_profile") is None
        
        # System config should remain
        assert await in_memory_cache.get("system_config") == {"setting": "value"}
    
    @pytest.mark.asyncio
    async def test_cache_invalidation_all(self, in_memory_cache):
        """Test cache invalidation of all entries."""
        # Set multiple entries
        await in_memory_cache.set("key1", "value1")
        await in_memory_cache.set("key2", "value2")
        
        # Invalidate all
        await in_memory_cache.invalidate()
        
        # All should be gone
        assert await in_memory_cache.get("key1") is None
        assert await in_memory_cache.get("key2") is None
    
    @pytest.mark.asyncio
    async def test_cache_concurrent_access(self, in_memory_cache):
        """Test cache concurrent access safety."""
        async def set_operation(key, value):
            await in_memory_cache.set(f"key_{key}", f"value_{value}")
            return f"set_{key}"
        
        async def get_operation(key):
            result = await in_memory_cache.get(f"key_{key}")
            return f"get_{key}_{result}"
        
        # Concurrent set operations
        set_tasks = [set_operation(i, i) for i in range(10)]
        set_results = await asyncio.gather(*set_tasks)
        
        assert len(set_results) == 10
        
        # Concurrent get operations
        get_tasks = [get_operation(i) for i in range(10)]
        get_results = await asyncio.gather(*get_tasks)
        
        assert len(get_results) == 10
        # All should have found their values
        assert all("value_" in result for result in get_results)
    
    def test_cache_entry_expiration_logic(self):
        """Test CacheEntry expiration logic."""
        # Non-expired entry
        entry = CacheEntry("test_data", ttl=60)
        assert not entry.is_expired()
        
        # Expired entry (simulate by setting old creation time)
        entry.created_at = datetime.now() - timedelta(seconds=61)
        assert entry.is_expired()
        
        # Boundary case (exactly at TTL)
        entry.created_at = datetime.now() - timedelta(seconds=60)
        assert entry.is_expired()  # Should be expired at exactly TTL


class TestResilientHTTPClient:
    """Tests for Resilient HTTP Client."""
    
    @pytest.mark.asyncio
    async def test_http_client_context_manager(self):
        """Test HTTP client context manager behavior."""
        client = ResilientHTTPClient("http://test.api", timeout=5)
        
        assert client.session is None
        
        async with client:
            assert client.session is not None
            assert isinstance(client.session, aiohttp.ClientSession)
        
        # Session should be closed after context exit
        assert client.session.closed
    
    @pytest.mark.asyncio
    async def test_http_client_successful_request(self):
        """Test successful HTTP request."""
        client = ResilientHTTPClient("http://test.api")
        
        # Mock response
        mock_response = Mock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"success": True, "data": "test"})
        
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = Mock()
            mock_session_class.return_value = mock_session
            mock_session.request.return_value.__aenter__.return_value = mock_response
            mock_session.request.return_value.__aexit__.return_value = None
            
            async with client:
                client.session = mock_session
                result = await client.request("GET", "/test/endpoint")
        
        assert result == {"success": True, "data": "test"}
        assert client.circuit_breaker.failure_count == 0
    
    @pytest.mark.asyncio
    async def test_http_client_circuit_breaker_open(self):
        """Test HTTP client behavior when circuit breaker is open."""
        client = ResilientHTTPClient("http://test.api")
        client.circuit_breaker.state = CircuitBreakerState.OPEN
        
        async with client:
            result = await client.request("GET", "/test/endpoint")
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_http_client_retry_logic(self):
        """Test HTTP client retry logic with exponential backoff."""
        client = ResilientHTTPClient("http://test.api", max_retries=2)
        
        # Mock failing requests
        call_count = 0
        
        async def mock_request(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            raise aiohttp.ClientError("Connection failed")
        
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = Mock()
            mock_session_class.return_value = mock_session
            mock_session.request = mock_request
            
            async with client:
                client.session = mock_session
                with patch('asyncio.sleep') as mock_sleep:  # Speed up test
                    result = await client.request("GET", "/test/endpoint")
        
        # Should retry max_retries + 1 times (original + retries)
        assert call_count == 3
        assert result is None
        assert client.circuit_breaker.failure_count > 0
        
        # Verify exponential backoff sleep calls
        expected_sleeps = [0, 1, 2]  # 2^0, 2^1, 2^2 seconds
        # Note: First call doesn't sleep, so we expect 2 sleep calls
        assert mock_sleep.call_count == 2
    
    @pytest.mark.asyncio
    async def test_http_client_non_200_status(self):
        """Test HTTP client handling of non-200 status codes."""
        client = ResilientHTTPClient("http://test.api")
        
        # Mock 404 response
        mock_response = Mock()
        mock_response.status = 404
        
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = Mock()
            mock_session_class.return_value = mock_session
            mock_session.request.return_value.__aenter__.return_value = mock_response
            mock_session.request.return_value.__aexit__.return_value = None
            
            async with client:
                client.session = mock_session
                result = await client.request("GET", "/nonexistent")
        
        assert result is None
        # Circuit breaker should register failure
        assert client.circuit_breaker.failure_count > 0


class TestKiwoomStockRepository:
    """Tests for Kiwoom Stock Repository."""
    
    @pytest.fixture
    def kiwoom_stock_repo(self, in_memory_cache):
        """Create KiwoomStockRepository instance for testing."""
        return KiwoomStockRepository(
            api_url="http://test.kiwoom.api",
            api_key="test_api_key",
            cache=in_memory_cache
        )
    
    @pytest.mark.asyncio
    async def test_find_by_code_cache_hit(self, kiwoom_stock_repo, in_memory_cache):
        """Test find_by_code with cache hit."""
        # Pre-populate cache
        stock_data = {
            "code": "005930",
            "name": "삼성전자",
            "market": "KOSPI",
            "sector": "반도체"
        }
        await in_memory_cache.set("stock_info_005930", stock_data)
        
        # Should return cached data without API call
        result = await kiwoom_stock_repo.find_by_code("005930")
        
        assert result is not None
        assert result.code == "005930"
        assert result.name == "삼성전자"
        assert result.market == "KOSPI"
        assert result.sector == "반도체"
    
    @pytest.mark.asyncio
    async def test_find_by_code_api_call_success(self, kiwoom_stock_repo):
        """Test find_by_code with successful API call."""
        api_response = {
            "success": True,
            "data": {
                "code": "000660",
                "name": "SK하이닉스",
                "market": "KOSPI",
                "sector": "반도체"
            }
        }
        
        with patch.object(ResilientHTTPClient, 'request', return_value=api_response):
            result = await kiwoom_stock_repo.find_by_code("000660")
        
        assert result is not None
        assert result.code == "000660"
        assert result.name == "SK하이닉스"
        assert result.sector == "반도체"
    
    @pytest.mark.asyncio
    async def test_find_by_code_api_failure(self, kiwoom_stock_repo):
        """Test find_by_code with API failure."""
        with patch.object(ResilientHTTPClient, 'request', return_value=None):
            result = await kiwoom_stock_repo.find_by_code("999999")
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_find_by_sector_success(self, kiwoom_stock_repo):
        """Test find_by_sector with successful API response."""
        api_response = {
            "success": True,
            "data": [
                {"code": "005930", "name": "삼성전자", "market": "KOSPI"},
                {"code": "000660", "name": "SK하이닉스", "market": "KOSPI"}
            ]
        }
        
        with patch.object(ResilientHTTPClient, 'request', return_value=api_response):
            result = await kiwoom_stock_repo.find_by_sector("반도체")
        
        assert len(result) == 2
        assert result[0].code == "005930"
        assert result[1].code == "000660"
        assert all(stock.sector == "반도체" for stock in result)
    
    @pytest.mark.asyncio
    async def test_search_by_name_no_cache(self, kiwoom_stock_repo):
        """Test search_by_name (should not use cache)."""
        api_response = {
            "success": True,
            "data": [
                {"code": "005930", "name": "삼성전자", "market": "KOSPI", "sector": "반도체"}
            ]
        }
        
        with patch.object(ResilientHTTPClient, 'request', return_value=api_response) as mock_request:
            result = await kiwoom_stock_repo.search_by_name("삼성")
        
        assert len(result) == 1
        assert result[0].name == "삼성전자"
        
        # Verify API was called with correct parameters
        mock_request.assert_called_once()
        call_args = mock_request.call_args
        assert call_args[1]["params"]["query"] == "삼성"


class TestKiwoomMarketDataRepository:
    """Tests for Kiwoom Market Data Repository."""
    
    @pytest.fixture
    def kiwoom_market_repo(self, in_memory_cache):
        """Create KiwoomMarketDataRepository instance for testing."""
        return KiwoomMarketDataRepository(
            api_url="http://test.kiwoom.api",
            api_key="test_api_key",
            cache=in_memory_cache
        )
    
    @pytest.mark.asyncio
    async def test_get_current_data_success(self, kiwoom_market_repo):
        """Test get_current_data with successful API response."""
        api_response = {
            "success": True,
            "data": {
                "price": 75000,
                "volume": 1500000,
                "market_cap": 450000000000000,
                "timestamp": "2024-01-01T09:00:00"
            }
        }
        
        with patch.object(ResilientHTTPClient, 'request', return_value=api_response):
            result = await kiwoom_market_repo.get_current_data("005930")
        
        assert result is not None
        assert result.stock_code == "005930"
        assert result.current_price == Decimal("75000")
        assert result.volume == 1500000
        assert result.market_cap == Decimal("450000000000000")
    
    @pytest.mark.asyncio
    async def test_get_current_data_cache_behavior(self, kiwoom_market_repo, in_memory_cache):
        """Test current data caching behavior."""
        api_response = {
            "success": True,
            "data": {
                "price": 75000,
                "volume": 1000000,
                "timestamp": datetime.now().isoformat()
            }
        }
        
        with patch.object(ResilientHTTPClient, 'request', return_value=api_response) as mock_request:
            # First call should make API request
            result1 = await kiwoom_market_repo.get_current_data("005930")
            assert mock_request.call_count == 1
            
            # Second call should use cache
            result2 = await kiwoom_market_repo.get_current_data("005930")
            assert mock_request.call_count == 1  # No additional API call
            
            # Results should be identical
            assert result1.current_price == result2.current_price
            assert result1.volume == result2.volume
    
    @pytest.mark.asyncio
    async def test_get_historical_data_success(self, kiwoom_market_repo):
        """Test get_historical_data with successful API response."""
        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 1, 31)
        
        api_response = {
            "success": True,
            "data": [
                {
                    "price": 74000,
                    "volume": 1000000,
                    "timestamp": "2024-01-01T09:00:00"
                },
                {
                    "price": 75000,
                    "volume": 1200000,
                    "timestamp": "2024-01-02T09:00:00"
                }
            ]
        }
        
        with patch.object(ResilientHTTPClient, 'request', return_value=api_response):
            result = await kiwoom_market_repo.get_historical_data("005930", start_date, end_date)
        
        assert len(result) == 2
        assert result[0].current_price == Decimal("74000")
        assert result[1].current_price == Decimal("75000")
        assert all(data.stock_code == "005930" for data in result)
    
    @pytest.mark.asyncio
    async def test_get_volume_profile(self, kiwoom_market_repo):
        """Test get_volume_profile delegates to get_historical_data."""
        with patch.object(kiwoom_market_repo, 'get_historical_data', return_value=[]) as mock_historical:
            await kiwoom_market_repo.get_volume_profile("005930", days=30)
        
        mock_historical.assert_called_once()
        call_args = mock_historical.call_args[0]
        assert call_args[0] == "005930"  # stock_code
        
        # Verify date range (approximately 30 days)
        start_date, end_date = call_args[1], call_args[2]
        date_diff = end_date - start_date
        assert abs(date_diff.days - 30) <= 1  # Allow for small timing differences


class TestMockTradingRepository:
    """Tests for Mock Trading Repository."""
    
    @pytest.mark.asyncio
    async def test_initial_account_state(self, mock_trading_repo_instance):
        """Test initial account state."""
        balance = await mock_trading_repo_instance.get_account_balance()
        positions = await mock_trading_repo_instance.get_portfolio_positions()
        
        assert balance == Decimal("10000000")  # 1천만원
        assert len(positions) == 0  # No initial positions
    
    @pytest.mark.asyncio
    async def test_buy_order_execution(self, mock_trading_repo_instance, sample_investment_decision):
        """Test buy order execution."""
        current_price = Decimal("75000")
        
        result = await mock_trading_repo_instance.execute_order(sample_investment_decision, current_price)
        
        assert result["success"] is True
        assert "order_id" in result
        assert result["executed_price"] == current_price
        assert result["executed_quantity"] == sample_investment_decision.quantity
        
        # Verify account state changes
        balance = await mock_trading_repo_instance.get_account_balance()
        expected_balance = Decimal("10000000") - (100 * current_price)
        assert balance == expected_balance
        
        # Verify position created
        positions = await mock_trading_repo_instance.get_portfolio_positions()
        assert len(positions) == 1
        assert positions[0]["stock_code"] == "005930"
        assert positions[0]["quantity"] == 100
    
    @pytest.mark.asyncio
    async def test_insufficient_balance_handling(self, mock_trading_repo_instance):
        """Test handling of insufficient balance."""
        # Create decision that exceeds available balance
        expensive_decision = InvestmentDecision(
            stock_code="999999",
            action=InvestmentSignal.BUY,
            quantity=1000,  # 1000 shares
            max_price=Decimal("50000"),
            risk_level=RiskLevel.LOW,
            requires_human_approval=False,
            analysis_result=AnalysisResult(
                stock_code="999999",
                signal=InvestmentSignal.BUY,
                confidence=0.8,
                target_price=None,
                reasoning="Test",
                analyzed_at=datetime.now()
            )
        )
        
        current_price = Decimal("50000")  # Total: 50M, but balance is only 10M
        
        result = await mock_trading_repo_instance.execute_order(expensive_decision, current_price)
        
        assert result["success"] is False
        assert "Insufficient balance" in result["error"]
        
        # Balance should remain unchanged
        balance = await mock_trading_repo_instance.get_account_balance()
        assert balance == Decimal("10000000")
    
    @pytest.mark.asyncio
    async def test_position_accumulation(self, mock_trading_repo_instance):
        """Test position accumulation with multiple buys."""
        # First buy
        decision1 = InvestmentDecision(
            stock_code="005930",
            action=InvestmentSignal.BUY,
            quantity=50,
            max_price=None,
            risk_level=RiskLevel.LOW,
            requires_human_approval=False,
            analysis_result=AnalysisResult(
                stock_code="005930",
                signal=InvestmentSignal.BUY,
                confidence=0.8,
                target_price=None,
                reasoning="Test",
                analyzed_at=datetime.now()
            )
        )
        
        await mock_trading_repo_instance.execute_order(decision1, Decimal("70000"))
        
        # Second buy at different price
        decision2 = InvestmentDecision(
            stock_code="005930",
            action=InvestmentSignal.BUY,
            quantity=30,
            max_price=None,
            risk_level=RiskLevel.LOW,
            requires_human_approval=False,
            analysis_result=AnalysisResult(
                stock_code="005930",
                signal=InvestmentSignal.BUY,
                confidence=0.8,
                target_price=None,
                reasoning="Test",
                analyzed_at=datetime.now()
            )
        )
        
        await mock_trading_repo_instance.execute_order(decision2, Decimal("80000"))
        
        # Check accumulated position
        positions = await mock_trading_repo_instance.get_portfolio_positions()
        assert len(positions) == 1
        position = positions[0]
        
        assert position["quantity"] == 80  # 50 + 30
        # Average price should be weighted: (50*70000 + 30*80000) / 80 = 73750
        expected_avg_price = Decimal("73750")
        assert position["avg_price"] == expected_avg_price
    
    @pytest.mark.asyncio
    async def test_order_history_tracking(self, mock_trading_repo_instance, sample_investment_decision):
        """Test order history tracking."""
        initial_history_count = len(mock_trading_repo_instance.order_history)
        
        await mock_trading_repo_instance.execute_order(sample_investment_decision, Decimal("75000"))
        
        # Order history should be updated
        assert len(mock_trading_repo_instance.order_history) == initial_history_count + 1
        
        last_order = mock_trading_repo_instance.order_history[-1]
        assert last_order["stock_code"] == "005930"
        assert last_order["action"] == "BUY"
        assert last_order["quantity"] == 100
        assert "timestamp" in last_order
    
    @pytest.mark.asyncio
    async def test_cancel_order_mock(self, mock_trading_repo_instance):
        """Test order cancellation (mock behavior)."""
        result = await mock_trading_repo_instance.cancel_order("ORDER_123456")
        assert result is True  # Mock always returns True


class TestInMemoryAnalysisRepository:
    """Tests for In-Memory Analysis Repository."""
    
    @pytest.mark.asyncio
    async def test_save_and_find_analysis(self, in_memory_analysis_repo, sample_analysis_result):
        """Test saving and finding analysis results."""
        # Initially empty
        result = await in_memory_analysis_repo.find_latest_analysis("005930")
        assert result is None
        
        # Save analysis
        await in_memory_analysis_repo.save_analysis(sample_analysis_result)
        
        # Should be able to retrieve it
        result = await in_memory_analysis_repo.find_latest_analysis("005930")
        assert result is not None
        assert result.stock_code == sample_analysis_result.stock_code
        assert result.signal == sample_analysis_result.signal
        assert result.confidence == sample_analysis_result.confidence
    
    @pytest.mark.asyncio
    async def test_find_latest_analysis_multiple(self, in_memory_analysis_repo, analysis_result_generator):
        """Test finding latest analysis when multiple exist."""
        now = datetime.now()
        
        # Create multiple analyses with different timestamps
        analysis1 = analysis_result_generator(
            stock_code="005930",
            confidence=0.7,
            analyzed_at=now - timedelta(hours=2)  # Older
        )
        analysis2 = analysis_result_generator(
            stock_code="005930",
            confidence=0.8,
            analyzed_at=now - timedelta(hours=1)  # Newer
        )
        
        await in_memory_analysis_repo.save_analysis(analysis1)
        await in_memory_analysis_repo.save_analysis(analysis2)
        
        # Should return the latest one
        latest = await in_memory_analysis_repo.find_latest_analysis("005930")
        assert latest.confidence == 0.8  # From analysis2
        assert latest.analyzed_at == analysis2.analyzed_at
    
    @pytest.mark.asyncio
    async def test_find_analysis_history(self, in_memory_analysis_repo, analysis_result_generator):
        """Test finding analysis history within date range."""
        now = datetime.now()
        
        # Create analyses with different ages
        recent_analysis = analysis_result_generator(
            stock_code="005930",
            confidence=0.8,
            analyzed_at=now - timedelta(days=5)  # Within 30 days
        )
        old_analysis = analysis_result_generator(
            stock_code="005930",
            confidence=0.6,
            analyzed_at=now - timedelta(days=35)  # Older than 30 days
        )
        different_stock = analysis_result_generator(
            stock_code="000660",
            confidence=0.7,
            analyzed_at=now - timedelta(days=10)  # Different stock
        )
        
        await in_memory_analysis_repo.save_analysis(recent_analysis)
        await in_memory_analysis_repo.save_analysis(old_analysis)
        await in_memory_analysis_repo.save_analysis(different_stock)
        
        # Find history for 005930 within last 30 days
        history = await in_memory_analysis_repo.find_analysis_history("005930", days=30)
        
        assert len(history) == 1  # Only recent_analysis should be included
        assert history[0].confidence == 0.8
        assert history[0].stock_code == "005930"
    
    @pytest.mark.asyncio
    async def test_memory_management(self, in_memory_analysis_repo, analysis_result_generator):
        """Test memory management (keeps only latest 100 per stock)."""
        # Create more than 100 analyses for the same stock
        analyses = []
        for i in range(105):
            analysis = analysis_result_generator(
                stock_code="005930",
                confidence=0.5 + (i * 0.001),  # Slightly different confidence
                analyzed_at=datetime.now() - timedelta(minutes=i)
            )
            analyses.append(analysis)
            await in_memory_analysis_repo.save_analysis(analysis)
        
        # Should only keep 100 most recent
        all_analyses = [a for a in in_memory_analysis_repo.analyses if a.stock_code == "005930"]
        assert len(all_analyses) <= 100
        
        # Oldest analysis should have been removed
        confidences = {a.confidence for a in all_analyses}
        assert 0.500 not in confidences  # First analysis should be removed


class TestIntegrationPatterns:
    """Integration tests for adapter patterns."""
    
    @pytest.mark.asyncio
    async def test_repository_with_circuit_breaker_integration(self):
        """Test repository behavior with circuit breaker failures."""
        cache = InMemoryCache()
        repo = KiwoomStockRepository(
            api_url="http://failing.api",
            api_key="test_key",
            cache=cache
        )
        
        # Mock circuit breaker to be open
        with patch.object(ResilientHTTPClient, 'request', return_value=None):
            result = await repo.find_by_code("005930")
        
        assert result is None  # Should fail gracefully
    
    @pytest.mark.asyncio
    async def test_cache_and_repository_integration(self, in_memory_cache):
        """Test cache integration with repository operations."""
        repo = KiwoomStockRepository(
            api_url="http://test.api",
            api_key="test_key",
            cache=in_memory_cache
        )
        
        api_response = {
            "success": True,
            "data": {
                "code": "005930",
                "name": "삼성전자",
                "market": "KOSPI",
                "sector": "반도체"
            }
        }
        
        with patch.object(ResilientHTTPClient, 'request', return_value=api_response) as mock_request:
            # First call should hit API
            result1 = await repo.find_by_code("005930")
            assert mock_request.call_count == 1
            
            # Second call should use cache
            result2 = await repo.find_by_code("005930")
            assert mock_request.call_count == 1  # No additional API call
            
            # Results should be equivalent
            assert result1.code == result2.code
            assert result1.name == result2.name
    
    @pytest.mark.asyncio
    async def test_error_handling_across_layers(self):
        """Test error handling propagation across layers."""
        cache = InMemoryCache()
        repo = KiwoomStockRepository(
            api_url="http://test.api",
            api_key="test_key",
            cache=cache
        )
        
        # Mock HTTP client to raise exception
        with patch.object(ResilientHTTPClient, '__aenter__', side_effect=Exception("Network error")):
            result = await repo.find_by_code("005930")
        
        # Should handle exception gracefully and return None
        assert result is None


class TestPerformancePatterns:
    """Performance-related tests for adapters."""
    
    @pytest.mark.asyncio
    async def test_cache_performance_under_load(self, in_memory_cache):
        """Test cache performance under concurrent load."""
        async def cache_operation(key_suffix):
            await in_memory_cache.set(f"key_{key_suffix}", f"value_{key_suffix}")
            result = await in_memory_cache.get(f"key_{key_suffix}")
            return result == f"value_{key_suffix}"
        
        # Run 100 concurrent cache operations
        tasks = [cache_operation(i) for i in range(100)]
        start_time = asyncio.get_event_loop().time()
        results = await asyncio.gather(*tasks)
        end_time = asyncio.get_event_loop().time()
        
        # All operations should succeed
        assert all(results)
        
        # Should complete reasonably quickly (less than 1 second)
        assert end_time - start_time < 1.0
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_performance_impact(self):
        """Test circuit breaker performance impact."""
        config = CircuitBreakerConfig(failure_threshold=5)
        cb = CircuitBreaker(config)
        
        # Measure can_execute performance
        iterations = 10000
        start_time = asyncio.get_event_loop().time()
        
        for _ in range(iterations):
            cb.can_execute()
        
        end_time = asyncio.get_event_loop().time()
        
        # Should be very fast (sub-millisecond per call)
        avg_time_per_call = (end_time - start_time) / iterations
        assert avg_time_per_call < 0.001  # Less than 1ms per call