"""
Comprehensive unit tests for application layer use cases with mocking.
Tests cover business logic, error handling, async operations, and integration patterns.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, Mock, patch, call
from typing import List

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
)
from simplified_architecture.application.use_cases import (
    AnalyzeStockUseCase,
    ExecuteInvestmentUseCase,
    GetPortfolioSummaryUseCase,
    AnalysisResult_UC,
    TradingResult_UC,
    Result,
)


class TestAnalyzeStockUseCase:
    """Tests for AnalyzeStockUseCase."""
    
    @pytest.fixture
    def analyze_use_case(
        self,
        mock_stock_repo,
        mock_market_data_repo,
        mock_news_repo,
        mock_analysis_repo,
        mock_llm_service,
        mock_event_publisher,
        risk_calculator,
    ):
        """Create AnalyzeStockUseCase instance with mocked dependencies."""
        return AnalyzeStockUseCase(
            stock_repo=mock_stock_repo,
            market_data_repo=mock_market_data_repo,
            news_repo=mock_news_repo,
            analysis_repo=mock_analysis_repo,
            llm_service=mock_llm_service,
            event_publisher=mock_event_publisher,
            risk_calculator=risk_calculator,
        )
    
    @pytest.mark.asyncio
    async def test_successful_stock_analysis(
        self, analyze_use_case, sample_stock, sample_market_data
    ):
        """Test successful stock analysis flow."""
        # Setup mocks
        analyze_use_case._stock_repo.find_by_code.return_value = sample_stock
        analyze_use_case._market_data_repo.get_current_data.return_value = sample_market_data
        analyze_use_case._news_repo.get_market_sentiment.return_value = 0.6
        analyze_use_case._market_data_repo.get_historical_data.return_value = [
            sample_market_data
        ]
        analyze_use_case._llm_service.analyze_stock.return_value = {
            "signal": "BUY",
            "confidence": 0.85,
            "target_price": 80000,
            "reasoning": "Strong fundamentals and positive sentiment"
        }
        analyze_use_case._analysis_repo.save_analysis.return_value = None
        analyze_use_case._event_publisher.publish.return_value = None
        
        # Execute
        result = await analyze_use_case.execute("005930")
        
        # Verify
        assert result.success is True
        assert result.error_message is None
        assert result.analysis is not None
        assert result.analysis.stock_code == "005930"
        assert result.analysis.signal == InvestmentSignal.BUY
        assert result.analysis.confidence == 0.85
        assert result.analysis.target_price == Decimal("80000")
        
        # Verify repository calls
        analyze_use_case._stock_repo.find_by_code.assert_called_once_with("005930")
        analyze_use_case._market_data_repo.get_current_data.assert_called_once_with("005930")
        analyze_use_case._analysis_repo.save_analysis.assert_called_once()
        analyze_use_case._event_publisher.publish.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_stock_not_found(self, analyze_use_case):
        """Test analysis when stock is not found."""
        analyze_use_case._stock_repo.find_by_code.return_value = None
        
        result = await analyze_use_case.execute("999999")
        
        assert result.success is False
        assert "Stock 999999 not found" in result.error_message
        assert result.analysis is None
    
    @pytest.mark.asyncio
    async def test_market_data_unavailable(self, analyze_use_case, sample_stock):
        """Test analysis when market data is unavailable."""
        analyze_use_case._stock_repo.find_by_code.return_value = sample_stock
        analyze_use_case._market_data_repo.get_current_data.return_value = None
        
        result = await analyze_use_case.execute("005930")
        
        assert result.success is False
        assert "Market data unavailable" in result.error_message
        assert result.analysis is None
    
    @pytest.mark.asyncio
    async def test_parallel_data_collection_with_exceptions(
        self, analyze_use_case, sample_stock, sample_market_data
    ):
        """Test parallel data collection handling exceptions gracefully."""
        # Setup basic data
        analyze_use_case._stock_repo.find_by_code.return_value = sample_stock
        analyze_use_case._market_data_repo.get_current_data.return_value = sample_market_data
        
        # Setup parallel tasks with one exception
        analyze_use_case._news_repo.get_market_sentiment.side_effect = ConnectionError("News API down")
        analyze_use_case._market_data_repo.get_historical_data.return_value = [sample_market_data]
        
        # Setup LLM response
        analyze_use_case._llm_service.analyze_stock.return_value = {
            "signal": "HOLD",
            "confidence": 0.7,
            "target_price": None,
            "reasoning": "Limited data available"
        }
        analyze_use_case._analysis_repo.save_analysis.return_value = None
        analyze_use_case._event_publisher.publish.return_value = None
        
        result = await analyze_use_case.execute("005930")
        
        # Should still succeed with default sentiment
        assert result.success is True
        assert result.analysis.signal == InvestmentSignal.HOLD
        
        # Verify LLM was called with default sentiment (0.0)
        llm_call_args = analyze_use_case._llm_service.analyze_stock.call_args[0]
        sentiment_data = llm_call_args[2]  # Third argument
        assert sentiment_data["sentiment"] == 0.0
    
    @pytest.mark.asyncio
    async def test_llm_confidence_clamping(
        self, analyze_use_case, sample_stock, sample_market_data
    ):
        """Test LLM confidence value clamping to valid range."""
        # Setup mocks
        analyze_use_case._stock_repo.find_by_code.return_value = sample_stock
        analyze_use_case._market_data_repo.get_current_data.return_value = sample_market_data
        analyze_use_case._news_repo.get_market_sentiment.return_value = 0.5
        analyze_use_case._market_data_repo.get_historical_data.return_value = []
        
        # LLM returns invalid confidence values
        analyze_use_case._llm_service.analyze_stock.return_value = {
            "signal": "BUY",
            "confidence": 1.5,  # > 1.0, should be clamped to 1.0
            "target_price": 75000,
            "reasoning": "Test"
        }
        analyze_use_case._analysis_repo.save_analysis.return_value = None
        analyze_use_case._event_publisher.publish.return_value = None
        
        result = await analyze_use_case.execute("005930")
        
        assert result.success is True
        assert result.analysis.confidence == 1.0  # Clamped to 1.0
        
        # Test negative confidence
        analyze_use_case._llm_service.analyze_stock.return_value["confidence"] = -0.1
        result = await analyze_use_case.execute("005930")
        
        assert result.success is True
        assert result.analysis.confidence == 0.0  # Clamped to 0.0
    
    @pytest.mark.asyncio
    async def test_event_publishing(
        self, analyze_use_case, sample_stock, sample_market_data
    ):
        """Test that analysis completed event is properly published."""
        # Setup successful analysis
        analyze_use_case._stock_repo.find_by_code.return_value = sample_stock
        analyze_use_case._market_data_repo.get_current_data.return_value = sample_market_data
        analyze_use_case._news_repo.get_market_sentiment.return_value = 0.3
        analyze_use_case._market_data_repo.get_historical_data.return_value = []
        analyze_use_case._llm_service.analyze_stock.return_value = {
            "signal": "SELL",
            "confidence": 0.9,
            "target_price": 70000,
            "reasoning": "Market downturn expected"
        }
        analyze_use_case._analysis_repo.save_analysis.return_value = None
        analyze_use_case._event_publisher.publish.return_value = None
        
        result = await analyze_use_case.execute("005930")
        
        # Verify event was published
        analyze_use_case._event_publisher.publish.assert_called_once()
        published_event = analyze_use_case._event_publisher.publish.call_args[0][0]
        
        assert isinstance(published_event, AnalysisCompleted)
        assert published_event.stock_code == "005930"
        assert published_event.analysis_result.signal == InvestmentSignal.SELL
        assert "analysis_005930_" in published_event.event_id
    
    @pytest.mark.asyncio
    async def test_exception_handling(self, analyze_use_case, sample_stock):
        """Test exception handling in use case."""
        analyze_use_case._stock_repo.find_by_code.return_value = sample_stock
        analyze_use_case._market_data_repo.get_current_data.side_effect = Exception("Database error")
        
        result = await analyze_use_case.execute("005930")
        
        assert result.success is False
        assert "Database error" in result.error_message
        assert result.analysis is None
    
    @pytest.mark.asyncio
    async def test_llm_service_context_preparation(
        self, analyze_use_case, sample_stock, sample_market_data
    ):
        """Test that LLM service receives properly formatted context."""
        # Setup mocks
        analyze_use_case._stock_repo.find_by_code.return_value = sample_stock
        analyze_use_case._market_data_repo.get_current_data.return_value = sample_market_data
        analyze_use_case._news_repo.get_market_sentiment.return_value = 0.7
        analyze_use_case._market_data_repo.get_historical_data.return_value = [
            sample_market_data, sample_market_data  # 2 historical records
        ]
        analyze_use_case._llm_service.analyze_stock.return_value = {
            "signal": "BUY", "confidence": 0.8, "reasoning": "Test"
        }
        analyze_use_case._analysis_repo.save_analysis.return_value = None
        analyze_use_case._event_publisher.publish.return_value = None
        
        await analyze_use_case.execute("005930")
        
        # Verify LLM service call arguments
        analyze_use_case._llm_service.analyze_stock.assert_called_once()
        call_args = analyze_use_case._llm_service.analyze_stock.call_args[0]
        
        stock_context = call_args[0]
        market_context = call_args[1]
        sentiment_context = call_args[2]
        
        # Verify stock context
        assert stock_context["code"] == "005930"
        assert stock_context["name"] == "삼성전자"
        assert stock_context["sector"] == "반도체"
        
        # Verify market context
        assert market_context["current_price"] == 75000.0
        assert market_context["volume"] == 1000000
        assert market_context["market_cap"] == 450000000000000.0
        
        # Verify sentiment context
        assert sentiment_context["sentiment"] == 0.7


class TestExecuteInvestmentUseCase:
    """Tests for ExecuteInvestmentUseCase."""
    
    @pytest.fixture
    def investment_use_case(
        self,
        mock_analysis_repo,
        mock_trading_repo,
        mock_market_data_repo,
        mock_human_approval_service,
        mock_event_publisher,
        risk_calculator,
    ):
        """Create ExecuteInvestmentUseCase instance with mocked dependencies."""
        return ExecuteInvestmentUseCase(
            analysis_repo=mock_analysis_repo,
            trading_repo=mock_trading_repo,
            market_data_repo=mock_market_data_repo,
            human_approval_service=mock_human_approval_service,
            event_publisher=mock_event_publisher,
            risk_calculator=risk_calculator,
        )
    
    @pytest.mark.asyncio
    async def test_successful_investment_execution_without_approval(
        self, investment_use_case, sample_analysis_result, sample_market_data
    ):
        """Test successful investment execution without human approval."""
        # Setup mocks
        investment_use_case._analysis_repo.find_latest_analysis.return_value = sample_analysis_result
        investment_use_case._market_data_repo.get_current_data.return_value = sample_market_data
        investment_use_case._trading_repo.get_portfolio_positions.return_value = [
            {"stock_code": "123456", "quantity": 100, "value": 5000000}
        ]
        investment_use_case._trading_repo.get_account_balance.return_value = Decimal("10000000")
        investment_use_case._trading_repo.execute_order.return_value = {
            "success": True,
            "order_id": "ORDER_001",
            "executed_price": 75000,
            "executed_quantity": 100
        }
        
        result = await investment_use_case.execute("005930", quantity=100, max_price=Decimal("76000"))
        
        assert result.success is True
        assert result.order_id == "ORDER_001"
        assert result.executed_price == Decimal("75000")
        assert result.executed_quantity == 100
        
        # Verify no human approval was requested
        investment_use_case._human_approval_service.request_approval.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_investment_execution_with_human_approval(
        self, investment_use_case, sample_market_data
    ):
        """Test investment execution requiring human approval."""
        # Create high-risk analysis (low confidence)
        high_risk_analysis = AnalysisResult(
            stock_code="005930",
            signal=InvestmentSignal.BUY,
            confidence=0.4,  # Low confidence triggers high risk
            target_price=Decimal("80000"),
            reasoning="Speculative opportunity",
            analyzed_at=datetime.now()
        )
        
        # Setup mocks
        investment_use_case._analysis_repo.find_latest_analysis.return_value = high_risk_analysis
        investment_use_case._market_data_repo.get_current_data.return_value = sample_market_data
        investment_use_case._trading_repo.get_portfolio_positions.return_value = []
        investment_use_case._trading_repo.get_account_balance.return_value = Decimal("20000000")
        investment_use_case._human_approval_service.request_approval.return_value = True
        investment_use_case._trading_repo.execute_order.return_value = {
            "success": True,
            "order_id": "ORDER_002",
            "executed_price": 75000,
            "executed_quantity": 500
        }
        
        # Large quantity to trigger high risk
        result = await investment_use_case.execute("005930", quantity=500)
        
        assert result.success is True
        assert result.order_id == "ORDER_002"
        
        # Verify human approval was requested
        investment_use_case._human_approval_service.request_approval.assert_called_once()
        investment_use_case._event_publisher.publish.assert_called()
        
        # Verify approval event was published
        approval_calls = [call for call in investment_use_case._event_publisher.publish.call_args_list 
                         if isinstance(call[0][0], HumanApprovalRequired)]
        assert len(approval_calls) == 1
    
    @pytest.mark.asyncio
    async def test_human_approval_denied(
        self, investment_use_case, sample_market_data
    ):
        """Test investment execution when human approval is denied."""
        # High-risk analysis
        high_risk_analysis = AnalysisResult(
            stock_code="005930",
            signal=InvestmentSignal.BUY,
            confidence=0.3,
            target_price=Decimal("80000"),
            reasoning="High risk opportunity",
            analyzed_at=datetime.now()
        )
        
        investment_use_case._analysis_repo.find_latest_analysis.return_value = high_risk_analysis
        investment_use_case._market_data_repo.get_current_data.return_value = sample_market_data
        investment_use_case._trading_repo.get_portfolio_positions.return_value = []
        investment_use_case._trading_repo.get_account_balance.return_value = Decimal("20000000")
        investment_use_case._human_approval_service.request_approval.return_value = False  # Denied
        
        result = await investment_use_case.execute("005930", quantity=1000)
        
        assert result.success is False
        assert "Human approval denied" in result.error_message
        
        # Verify order was not executed
        investment_use_case._trading_repo.execute_order.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_no_analysis_available(self, investment_use_case):
        """Test investment execution when no analysis is available."""
        investment_use_case._analysis_repo.find_latest_analysis.return_value = None
        
        result = await investment_use_case.execute("005930", quantity=100)
        
        assert result.success is False
        assert "No analysis available" in result.error_message
    
    @pytest.mark.asyncio
    async def test_market_data_unavailable_for_execution(
        self, investment_use_case, sample_analysis_result
    ):
        """Test investment execution when market data is unavailable."""
        investment_use_case._analysis_repo.find_latest_analysis.return_value = sample_analysis_result
        investment_use_case._market_data_repo.get_current_data.return_value = None
        
        result = await investment_use_case.execute("005930", quantity=100)
        
        assert result.success is False
        assert "Market data unavailable" in result.error_message
    
    @pytest.mark.asyncio
    async def test_order_execution_failure(
        self, investment_use_case, sample_analysis_result, sample_market_data
    ):
        """Test handling of order execution failure."""
        investment_use_case._analysis_repo.find_latest_analysis.return_value = sample_analysis_result
        investment_use_case._market_data_repo.get_current_data.return_value = sample_market_data
        investment_use_case._trading_repo.get_portfolio_positions.return_value = []
        investment_use_case._trading_repo.get_account_balance.return_value = Decimal("10000000")
        investment_use_case._trading_repo.execute_order.return_value = {
            "success": False,
            "error": "Insufficient margin"
        }
        
        result = await investment_use_case.execute("005930", quantity=100)
        
        assert result.success is False
        assert "Insufficient margin" in result.error_message
    
    @pytest.mark.asyncio
    async def test_risk_level_calculation(
        self, investment_use_case, sample_analysis_result, sample_market_data
    ):
        """Test risk level calculation logic."""
        investment_use_case._analysis_repo.find_latest_analysis.return_value = sample_analysis_result
        investment_use_case._market_data_repo.get_current_data.return_value = sample_market_data
        investment_use_case._trading_repo.get_portfolio_positions.return_value = [
            {"stock_code": "123456", "value": 5000000}  # 500만원 포지션
        ]
        investment_use_case._trading_repo.get_account_balance.return_value = Decimal("5000000")  # 500만원 현금
        investment_use_case._trading_repo.execute_order.return_value = {
            "success": True, "order_id": "ORDER_003"
        }
        
        # Small investment (10% of portfolio) should be low risk
        result = await investment_use_case.execute("005930", quantity=10)  # ~75만원
        
        assert result.success is True
        
        # Verify risk calculation was performed
        # Investment ratio: 750000 / 10000000 = 0.075 (7.5%)
        # With confidence 0.8, should result in LOW or MEDIUM risk
        investment_use_case._trading_repo.execute_order.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_exception_handling_in_investment(
        self, investment_use_case, sample_analysis_result
    ):
        """Test exception handling in investment use case."""
        investment_use_case._analysis_repo.find_latest_analysis.return_value = sample_analysis_result
        investment_use_case._market_data_repo.get_current_data.side_effect = Exception("Connection timeout")
        
        result = await investment_use_case.execute("005930", quantity=100)
        
        assert result.success is False
        assert "Connection timeout" in result.error_message


class TestGetPortfolioSummaryUseCase:
    """Tests for GetPortfolioSummaryUseCase."""
    
    @pytest.fixture
    def portfolio_use_case(
        self,
        mock_trading_repo,
        mock_market_data_repo,
        mock_analysis_repo,
        risk_calculator,
    ):
        """Create GetPortfolioSummaryUseCase instance with mocked dependencies."""
        return GetPortfolioSummaryUseCase(
            trading_repo=mock_trading_repo,
            market_data_repo=mock_market_data_repo,
            analysis_repo=mock_analysis_repo,
            risk_calculator=risk_calculator,
        )
    
    @pytest.mark.asyncio
    async def test_successful_portfolio_summary(
        self, portfolio_use_case, market_data_generator
    ):
        """Test successful portfolio summary generation."""
        # Setup portfolio positions
        portfolio_use_case._trading_repo.get_portfolio_positions.return_value = [
            {"stock_code": "005930", "quantity": 100},
            {"stock_code": "000660", "quantity": 50},
        ]
        portfolio_use_case._trading_repo.get_account_balance.return_value = Decimal("5000000")
        
        # Setup market data for each position
        market_data_005930 = market_data_generator("005930", 75000, 1000000)
        market_data_000660 = market_data_generator("000660", 500000, 500000)
        
        portfolio_use_case._market_data_repo.get_current_data.side_effect = [
            market_data_005930,  # First call for 005930
            market_data_000660,  # Second call for 000660
        ]
        
        result = await portfolio_use_case.execute()
        
        assert result["success"] is True
        assert "portfolio" in result
        
        portfolio = result["portfolio"]
        assert portfolio["cash_balance"] == 5000000.0
        assert portfolio["invested_value"] == 32500000.0  # (100 * 75000) + (50 * 500000)
        assert portfolio["total_value"] == 37500000.0  # invested + cash
        
        # Check positions
        positions = portfolio["positions"]
        assert len(positions) == 2
        
        # Check position details
        samsung_position = next(p for p in positions if p["stock_code"] == "005930")
        assert samsung_position["quantity"] == 100
        assert samsung_position["current_price"] == Decimal("75000")
        assert samsung_position["value"] == Decimal("7500000")
        assert abs(samsung_position["weight"] - 20.0) < 0.01  # 7.5M / 37.5M = 20%
        
        sk_position = next(p for p in positions if p["stock_code"] == "000660")
        assert sk_position["quantity"] == 50
        assert sk_position["value"] == Decimal("25000000")
        assert abs(sk_position["weight"] - 66.67) < 0.01  # 25M / 37.5M ≈ 66.67%
        
        # Check risk metrics
        risk_metrics = portfolio["risk_metrics"]
        assert "var_95" in risk_metrics
        assert "var_percentage" in risk_metrics
        assert risk_metrics["var_95"] > 0
        assert 0 <= risk_metrics["var_percentage"] <= 100
    
    @pytest.mark.asyncio
    async def test_portfolio_summary_with_empty_portfolio(self, portfolio_use_case):
        """Test portfolio summary with no positions."""
        portfolio_use_case._trading_repo.get_portfolio_positions.return_value = []
        portfolio_use_case._trading_repo.get_account_balance.return_value = Decimal("10000000")
        
        result = await portfolio_use_case.execute()
        
        assert result["success"] is True
        portfolio = result["portfolio"]
        assert portfolio["total_value"] == 10000000.0
        assert portfolio["cash_balance"] == 10000000.0
        assert portfolio["invested_value"] == 0.0
        assert len(portfolio["positions"]) == 0
        assert portfolio["risk_metrics"]["var_95"] > 0  # VaR should still be calculated
    
    @pytest.mark.asyncio
    async def test_portfolio_summary_with_zero_quantity_positions(
        self, portfolio_use_case, market_data_generator
    ):
        """Test portfolio summary filters out zero quantity positions."""
        portfolio_use_case._trading_repo.get_portfolio_positions.return_value = [
            {"stock_code": "005930", "quantity": 100},
            {"stock_code": "000660", "quantity": 0},  # Should be filtered out
            {"stock_code": "035720", "quantity": 50},
        ]
        portfolio_use_case._trading_repo.get_account_balance.return_value = Decimal("1000000")
        
        # Setup market data (should only be called for non-zero positions)
        portfolio_use_case._market_data_repo.get_current_data.side_effect = [
            market_data_generator("005930", 75000),
            market_data_generator("035720", 200000),
        ]
        
        result = await portfolio_use_case.execute()
        
        assert result["success"] is True
        positions = result["portfolio"]["positions"]
        assert len(positions) == 2  # Zero quantity position filtered out
        
        stock_codes = {pos["stock_code"] for pos in positions}
        assert stock_codes == {"005930", "035720"}
    
    @pytest.mark.asyncio
    async def test_portfolio_summary_with_market_data_failures(
        self, portfolio_use_case, market_data_generator
    ):
        """Test portfolio summary when some market data is unavailable."""
        portfolio_use_case._trading_repo.get_portfolio_positions.return_value = [
            {"stock_code": "005930", "quantity": 100},
            {"stock_code": "000660", "quantity": 50},
        ]
        portfolio_use_case._trading_repo.get_account_balance.return_value = Decimal("2000000")
        
        # Market data available for first stock, not for second
        portfolio_use_case._market_data_repo.get_current_data.side_effect = [
            market_data_generator("005930", 75000),
            None,  # Market data unavailable for 000660
        ]
        
        result = await portfolio_use_case.execute()
        
        assert result["success"] is True
        positions = result["portfolio"]["positions"]
        assert len(positions) == 1  # Only stock with available market data
        assert positions[0]["stock_code"] == "005930"
    
    @pytest.mark.asyncio
    async def test_portfolio_weight_calculations(
        self, portfolio_use_case, market_data_generator
    ):
        """Test accurate portfolio weight calculations."""
        portfolio_use_case._trading_repo.get_portfolio_positions.return_value = [
            {"stock_code": "005930", "quantity": 100},  # 10M value
            {"stock_code": "000660", "quantity": 25},   # 5M value
        ]
        portfolio_use_case._trading_repo.get_account_balance.return_value = Decimal("5000000")  # 5M cash
        
        portfolio_use_case._market_data_repo.get_current_data.side_effect = [
            market_data_generator("005930", 100000),  # 100 * 100,000 = 10M
            market_data_generator("000660", 200000),  # 25 * 200,000 = 5M
        ]
        
        result = await portfolio_use_case.execute()
        
        # Total portfolio value: 10M + 5M + 5M = 20M
        assert result["portfolio"]["total_value"] == 20000000.0
        
        positions = result["portfolio"]["positions"]
        samsung_pos = next(p for p in positions if p["stock_code"] == "005930")
        sk_pos = next(p for p in positions if p["stock_code"] == "000660")
        
        # Check weights: Samsung 50%, SK 25%
        assert abs(samsung_pos["weight"] - 50.0) < 0.01
        assert abs(sk_pos["weight"] - 25.0) < 0.01
        
        # Verify weights sum to invested percentage (75%)
        total_weight = sum(p["weight"] for p in positions)
        assert abs(total_weight - 75.0) < 0.01  # 15M invested / 20M total = 75%
    
    @pytest.mark.asyncio
    async def test_var_calculation_in_portfolio_summary(self, portfolio_use_case):
        """Test VaR calculation in portfolio summary."""
        portfolio_use_case._trading_repo.get_portfolio_positions.return_value = []
        portfolio_use_case._trading_repo.get_account_balance.return_value = Decimal("10000000")
        
        result = await portfolio_use_case.execute()
        
        # Verify VaR calculation with expected parameters
        risk_metrics = result["portfolio"]["risk_metrics"]
        
        # Expected VaR: 10M * 1.65 * 0.15 = 2.475M
        expected_var = 10000000 * 1.65 * 0.15
        assert abs(risk_metrics["var_95"] - expected_var) < 100  # Allow small rounding differences
        
        # VaR percentage should be around 24.75%
        expected_percentage = expected_var / 10000000 * 100
        assert abs(risk_metrics["var_percentage"] - expected_percentage) < 0.01
    
    @pytest.mark.asyncio
    async def test_portfolio_summary_exception_handling(self, portfolio_use_case):
        """Test exception handling in portfolio summary."""
        portfolio_use_case._trading_repo.get_portfolio_positions.side_effect = Exception("Database error")
        
        result = await portfolio_use_case.execute()
        
        assert result["success"] is False
        assert "Database error" in result["error_message"]


class TestResultPatterns:
    """Tests for Result pattern implementations."""
    
    def test_result_success_creation(self):
        """Test creating successful result."""
        result = Result(success=True)
        assert result.success is True
        assert result.error_message is None
    
    def test_result_failure_creation(self):
        """Test creating failure result."""
        result = Result(success=False, error_message="Operation failed")
        assert result.success is False
        assert result.error_message == "Operation failed"
    
    def test_analysis_result_uc_success(self, sample_analysis_result):
        """Test AnalysisResult_UC with successful analysis."""
        result = AnalysisResult_UC(success=True, analysis=sample_analysis_result)
        assert result.success is True
        assert result.analysis == sample_analysis_result
        assert result.error_message is None
    
    def test_analysis_result_uc_failure(self):
        """Test AnalysisResult_UC with failure."""
        result = AnalysisResult_UC(success=False, error_message="Analysis failed")
        assert result.success is False
        assert result.analysis is None
        assert result.error_message == "Analysis failed"
    
    def test_trading_result_uc_success(self):
        """Test TradingResult_UC with successful trade."""
        result = TradingResult_UC(
            success=True,
            order_id="ORDER_123",
            executed_price=Decimal("75000"),
            executed_quantity=100
        )
        assert result.success is True
        assert result.order_id == "ORDER_123"
        assert result.executed_price == Decimal("75000")
        assert result.executed_quantity == 100
        assert result.error_message is None
    
    def test_trading_result_uc_failure(self):
        """Test TradingResult_UC with failure."""
        result = TradingResult_UC(success=False, error_message="Trade failed")
        assert result.success is False
        assert result.order_id is None
        assert result.executed_price is None
        assert result.executed_quantity is None
        assert result.error_message == "Trade failed"
    
    def test_result_immutability(self):
        """Test that result objects are immutable."""
        result = Result(success=True)
        with pytest.raises(AttributeError):
            result.success = False


class TestAsyncPatterns:
    """Tests for async patterns and error handling."""
    
    @pytest.mark.asyncio
    async def test_concurrent_async_operations(
        self, mock_market_data_repo, mock_news_repo
    ):
        """Test concurrent async operations pattern."""
        # Setup mocks with delays to test concurrency
        async def delayed_market_data():
            await asyncio.sleep(0.1)
            return MarketData(
                stock_code="005930",
                current_price=Decimal("75000"),
                volume=1000000,
                market_cap=None,
                timestamp=datetime.now()
            )
        
        async def delayed_sentiment():
            await asyncio.sleep(0.1)
            return 0.6
        
        mock_market_data_repo.get_historical_data.side_effect = delayed_market_data
        mock_news_repo.get_market_sentiment.side_effect = delayed_sentiment
        
        # Execute concurrent operations
        start_time = asyncio.get_event_loop().time()
        results = await asyncio.gather(
            mock_market_data_repo.get_historical_data("005930", datetime.now(), datetime.now()),
            mock_news_repo.get_market_sentiment("005930"),
            return_exceptions=True
        )
        end_time = asyncio.get_event_loop().time()
        
        # Should complete in ~0.1s (concurrent) rather than ~0.2s (sequential)
        assert end_time - start_time < 0.15
        assert len(results) == 2
        assert not isinstance(results[0], Exception)
        assert not isinstance(results[1], Exception)
    
    @pytest.mark.asyncio
    async def test_async_exception_isolation(self):
        """Test that async exceptions are properly isolated."""
        async def failing_operation():
            raise ValueError("Async operation failed")
        
        async def successful_operation():
            return "Success"
        
        # Test that one failure doesn't affect other operations
        results = await asyncio.gather(
            failing_operation(),
            successful_operation(),
            return_exceptions=True
        )
        
        assert isinstance(results[0], ValueError)
        assert results[1] == "Success"
    
    @pytest.mark.asyncio
    async def test_timeout_handling_pattern(self):
        """Test timeout handling in async operations."""
        async def slow_operation():
            await asyncio.sleep(1.0)  # 1 second delay
            return "Completed"
        
        # Test timeout
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(slow_operation(), timeout=0.1)
        
        # Test successful completion within timeout
        result = await asyncio.wait_for(slow_operation(), timeout=1.5)
        assert result == "Completed"