"""
Comprehensive unit tests for domain entities with edge cases.
Tests cover validation, business logic, edge cases, and error handling.
"""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import patch
import math

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


class TestStock:
    """Tests for Stock entity."""
    
    def test_valid_stock_creation(self, stock_data_generator):
        """Test creating a valid stock."""
        stock = stock_data_generator()
        assert stock.code == "005930"
        assert stock.name == "삼성전자"
        assert stock.market == "KOSPI"
        assert stock.sector == "반도체"
    
    def test_stock_creation_with_minimal_data(self):
        """Test stock creation with minimal required data."""
        stock = Stock(code="123456", name="Test Company", market="KOSDAQ")
        assert stock.code == "123456"
        assert stock.name == "Test Company"
        assert stock.market == "KOSDAQ"
        assert stock.sector is None
    
    @pytest.mark.parametrize("invalid_code", [
        "",
        "12345",     # Too short
        "1234567",   # Too long
        "ABCDEF",    # Non-numeric
        "12345A",    # Mixed
        None,
    ])
    def test_invalid_stock_code(self, invalid_code):
        """Test stock creation with invalid codes."""
        with pytest.raises(ValueError, match="Stock code must be 6 digits"):
            Stock(code=invalid_code, name="Test", market="KOSPI")
    
    @pytest.mark.parametrize("invalid_name", ["", None])
    def test_invalid_stock_name(self, invalid_name):
        """Test stock creation with invalid names."""
        with pytest.raises(ValueError, match="Stock name is required"):
            Stock(code="123456", name=invalid_name, market="KOSPI")
    
    def test_stock_immutability(self, sample_stock):
        """Test that stock entity is immutable."""
        with pytest.raises(AttributeError):
            sample_stock.code = "999999"


class TestMarketData:
    """Tests for MarketData entity."""
    
    def test_valid_market_data_creation(self, market_data_generator):
        """Test creating valid market data."""
        data = market_data_generator()
        assert data.stock_code == "005930"
        assert data.current_price == Decimal("75000")
        assert data.volume == 1000000
        assert isinstance(data.timestamp, datetime)
    
    def test_market_data_with_optional_fields(self):
        """Test market data creation with optional fields."""
        data = MarketData(
            stock_code="123456",
            current_price=Decimal("50000"),
            volume=500000,
            market_cap=None,  # Optional
            timestamp=datetime.now()
        )
        assert data.market_cap is None
    
    def test_price_change_rate_calculation(self, sample_market_data):
        """Test price change rate calculation."""
        # 10% increase: (75000 - 68181.82) / 68181.82 ≈ 0.1
        previous_price = Decimal("68181.82")
        change_rate = sample_market_data.price_change_rate(previous_price)
        assert abs(change_rate - Decimal("10.00")) < Decimal("0.01")
    
    def test_price_change_rate_zero_change(self, sample_market_data):
        """Test price change rate with no change."""
        same_price = sample_market_data.current_price
        change_rate = sample_market_data.price_change_rate(same_price)
        assert change_rate == Decimal("0")
    
    def test_price_change_rate_decrease(self, sample_market_data):
        """Test price change rate with price decrease."""
        higher_previous = Decimal("100000")  # -25% change
        change_rate = sample_market_data.price_change_rate(higher_previous)
        assert change_rate == Decimal("-25")
    
    @pytest.mark.parametrize("invalid_previous_price", [
        Decimal("0"),
        Decimal("-1000"),
        Decimal("-100.50"),
    ])
    def test_price_change_rate_invalid_previous_price(
        self, sample_market_data, invalid_previous_price
    ):
        """Test price change rate with invalid previous prices."""
        with pytest.raises(ValueError, match="Previous price must be positive"):
            sample_market_data.price_change_rate(invalid_previous_price)
    
    def test_market_data_immutability(self, sample_market_data):
        """Test that market data entity is immutable."""
        with pytest.raises(AttributeError):
            sample_market_data.current_price = Decimal("80000")


class TestAnalysisResult:
    """Tests for AnalysisResult entity."""
    
    def test_valid_analysis_result_creation(self, analysis_result_generator):
        """Test creating valid analysis result."""
        result = analysis_result_generator()
        assert result.stock_code == "005930"
        assert result.signal == InvestmentSignal.BUY
        assert result.confidence == 0.8
        assert result.target_price == Decimal("80000")
        assert result.reasoning == "Test analysis"
    
    def test_analysis_result_without_target_price(self):
        """Test analysis result without target price."""
        result = AnalysisResult(
            stock_code="123456",
            signal=InvestmentSignal.HOLD,
            confidence=0.6,
            target_price=None,
            reasoning="Hold recommendation",
            analyzed_at=datetime.now()
        )
        assert result.target_price is None
    
    @pytest.mark.parametrize("confidence", [0.0, 0.1, 0.5, 0.8, 0.9, 1.0])
    def test_valid_confidence_values(self, confidence):
        """Test analysis result with valid confidence values."""
        result = AnalysisResult(
            stock_code="123456",
            signal=InvestmentSignal.BUY,
            confidence=confidence,
            target_price=Decimal("50000"),
            reasoning="Test",
            analyzed_at=datetime.now()
        )
        assert result.confidence == confidence
    
    @pytest.mark.parametrize("invalid_confidence", [-0.1, -1.0, 1.1, 2.0, 100])
    def test_invalid_confidence_values(self, invalid_confidence):
        """Test analysis result with invalid confidence values."""
        with pytest.raises(ValueError, match="Confidence must be between 0.0 and 1.0"):
            AnalysisResult(
                stock_code="123456",
                signal=InvestmentSignal.BUY,
                confidence=invalid_confidence,
                target_price=Decimal("50000"),
                reasoning="Test",
                analyzed_at=datetime.now()
            )
    
    @pytest.mark.parametrize("invalid_target_price", [
        Decimal("0"),
        Decimal("-1000"),
        Decimal("-0.01"),
    ])
    def test_invalid_target_price(self, invalid_target_price):
        """Test analysis result with invalid target prices."""
        with pytest.raises(ValueError, match="Target price must be positive"):
            AnalysisResult(
                stock_code="123456",
                signal=InvestmentSignal.BUY,
                confidence=0.8,
                target_price=invalid_target_price,
                reasoning="Test",
                analyzed_at=datetime.now()
            )


class TestInvestmentDecision:
    """Tests for InvestmentDecision entity."""
    
    def test_valid_investment_decision_creation(self, sample_investment_decision):
        """Test creating valid investment decision."""
        decision = sample_investment_decision
        assert decision.stock_code == "005930"
        assert decision.action == InvestmentSignal.BUY
        assert decision.quantity == 100
        assert decision.max_price == Decimal("76000")
        assert decision.risk_level == RiskLevel.MEDIUM
        assert not decision.requires_human_approval
    
    def test_calculate_investment_amount_no_max_price(self, sample_investment_decision):
        """Test investment amount calculation without max price."""
        decision = InvestmentDecision(
            stock_code="005930",
            action=InvestmentSignal.BUY,
            quantity=100,
            max_price=None,
            risk_level=RiskLevel.LOW,
            requires_human_approval=False,
            analysis_result=sample_investment_decision.analysis_result
        )
        current_price = Decimal("75000")
        amount = decision.calculate_investment_amount(current_price)
        assert amount == Decimal("7500000")  # 100 * 75000
    
    def test_calculate_investment_amount_with_max_price_limit(
        self, sample_investment_decision
    ):
        """Test investment amount with max price limiting."""
        current_price = Decimal("80000")  # Higher than max_price (76000)
        amount = sample_investment_decision.calculate_investment_amount(current_price)
        assert amount == Decimal("7600000")  # 100 * 76000 (limited by max_price)
    
    def test_calculate_investment_amount_max_price_not_limiting(
        self, sample_investment_decision
    ):
        """Test investment amount with max price not limiting."""
        current_price = Decimal("70000")  # Lower than max_price (76000)
        amount = sample_investment_decision.calculate_investment_amount(current_price)
        assert amount == Decimal("7000000")  # 100 * 70000 (current price used)
    
    @pytest.mark.parametrize("risk_level,expected", [
        (RiskLevel.HIGH, True),
        (RiskLevel.VERY_HIGH, True),
        (RiskLevel.MEDIUM, False),
        (RiskLevel.LOW, False),
    ])
    def test_is_high_risk_by_risk_level(
        self, sample_investment_decision, risk_level, expected
    ):
        """Test high risk determination by risk level."""
        decision = InvestmentDecision(
            stock_code="005930",
            action=InvestmentSignal.BUY,
            quantity=100,
            max_price=Decimal("76000"),
            risk_level=risk_level,
            requires_human_approval=False,
            analysis_result=sample_investment_decision.analysis_result
        )
        investment_amount = Decimal("5000000")  # Below default threshold
        assert decision.is_high_risk(investment_amount) == expected
    
    def test_is_high_risk_by_investment_amount(self, sample_investment_decision):
        """Test high risk determination by investment amount."""
        large_amount = Decimal("15000000")  # Above default threshold (10M)
        assert sample_investment_decision.is_high_risk(large_amount)
    
    def test_is_high_risk_by_low_confidence(self):
        """Test high risk determination by low confidence."""
        low_confidence_analysis = AnalysisResult(
            stock_code="005930",
            signal=InvestmentSignal.BUY,
            confidence=0.5,  # Below 0.6 threshold
            target_price=Decimal("80000"),
            reasoning="Low confidence analysis",
            analyzed_at=datetime.now()
        )
        
        decision = InvestmentDecision(
            stock_code="005930",
            action=InvestmentSignal.BUY,
            quantity=100,
            max_price=Decimal("76000"),
            risk_level=RiskLevel.LOW,
            requires_human_approval=False,
            analysis_result=low_confidence_analysis
        )
        
        small_amount = Decimal("1000000")  # Small amount, low risk level
        assert decision.is_high_risk(small_amount)  # But low confidence triggers high risk
    
    def test_is_high_risk_custom_max_position_size(self, sample_investment_decision):
        """Test high risk with custom max position size."""
        investment_amount = Decimal("8000000")
        custom_max = Decimal("5000000")
        
        # Should be high risk due to custom limit
        assert sample_investment_decision.is_high_risk(investment_amount, custom_max)
        
        # Should not be high risk with higher limit
        higher_max = Decimal("20000000")
        assert not sample_investment_decision.is_high_risk(investment_amount, higher_max)


class TestRiskCalculator:
    """Tests for RiskCalculator domain service."""
    
    def test_calculate_var_basic(self, risk_calculator):
        """Test basic VaR calculation."""
        portfolio_value = Decimal("10000000")  # 1천만원
        volatility = 0.2  # 20%
        confidence_level = 0.95
        
        var = risk_calculator.calculate_var(
            portfolio_value, volatility, confidence_level
        )
        
        # Expected: 10M * 1.65 * 0.2 * 1 = 3.3M
        expected = Decimal("3300000.00")
        assert var == expected
    
    @pytest.mark.parametrize("confidence_level,expected_z_score", [
        (0.90, 1.28),
        (0.95, 1.65),
        (0.99, 2.33),
    ])
    def test_calculate_var_different_confidence_levels(
        self, risk_calculator, confidence_level, expected_z_score
    ):
        """Test VaR calculation with different confidence levels."""
        portfolio_value = Decimal("5000000")
        volatility = 0.15
        
        var = risk_calculator.calculate_var(
            portfolio_value, volatility, confidence_level
        )
        
        expected = portfolio_value * Decimal(str(expected_z_score)) * Decimal("0.15")
        assert var == expected.quantize(Decimal('0.01'))
    
    def test_calculate_var_with_holding_period(self, risk_calculator):
        """Test VaR calculation with different holding periods."""
        portfolio_value = Decimal("10000000")
        volatility = 0.2
        holding_period = 4  # 4 days
        
        var = risk_calculator.calculate_var(
            portfolio_value, volatility, holding_period=holding_period
        )
        
        # Expected: 10M * 1.65 * 0.2 * sqrt(4) = 6.6M
        expected = Decimal("6600000.00")
        assert var == expected
    
    def test_calculate_var_unknown_confidence_level(self, risk_calculator):
        """Test VaR calculation with unknown confidence level (uses default)."""
        portfolio_value = Decimal("1000000")
        volatility = 0.1
        confidence_level = 0.85  # Not in predefined z_scores
        
        var = risk_calculator.calculate_var(
            portfolio_value, volatility, confidence_level
        )
        
        # Should use default z_score of 1.65
        expected = Decimal("165000.00")
        assert var == expected
    
    @pytest.mark.parametrize("invalid_volatility", [-0.1, -1.0, -0.01])
    def test_calculate_var_negative_volatility(self, risk_calculator, invalid_volatility):
        """Test VaR calculation with negative volatility."""
        with pytest.raises(ValueError, match="Volatility cannot be negative"):
            risk_calculator.calculate_var(
                Decimal("1000000"), invalid_volatility
            )
    
    @pytest.mark.parametrize("invalid_confidence", [0.0, 1.0, -0.1, 1.1])
    def test_calculate_var_invalid_confidence_level(
        self, risk_calculator, invalid_confidence
    ):
        """Test VaR calculation with invalid confidence levels."""
        with pytest.raises(ValueError, match="Confidence level must be between 0 and 1"):
            risk_calculator.calculate_var(
                Decimal("1000000"), 0.2, invalid_confidence
            )
    
    @pytest.mark.parametrize("confidence,investment_ratio,volatility,expected", [
        (0.9, 0.1, 0.1, RiskLevel.LOW),      # Low risk scenario
        (0.7, 0.3, 0.2, RiskLevel.MEDIUM),   # Medium risk scenario  
        (0.5, 0.5, 0.3, RiskLevel.HIGH),     # High risk scenario
        (0.3, 0.7, 0.4, RiskLevel.VERY_HIGH) # Very high risk scenario
    ])
    def test_determine_risk_level_scenarios(
        self, risk_calculator, confidence, investment_ratio, volatility, expected
    ):
        """Test risk level determination with various scenarios."""
        risk_level = risk_calculator.determine_risk_level(
            confidence, investment_ratio, volatility
        )
        assert risk_level == expected
    
    def test_determine_risk_level_boundary_cases(self, risk_calculator):
        """Test risk level determination at boundary values."""
        # Test exactly at boundary (0.8 threshold for VERY_HIGH)
        risk_level = risk_calculator.determine_risk_level(
            confidence=0.2,  # (1-0.2)*0.4 = 0.32
            investment_ratio=1.0,  # 1.0*0.4 = 0.4  
            market_volatility=0.4   # 0.4*0.2 = 0.08
            # Total: 0.32 + 0.4 + 0.08 = 0.8 (exactly at threshold)
        )
        assert risk_level == RiskLevel.VERY_HIGH
        
        # Test just below boundary
        risk_level = risk_calculator.determine_risk_level(
            confidence=0.21,  # Slightly higher confidence
            investment_ratio=1.0,
            market_volatility=0.4
        )
        assert risk_level == RiskLevel.HIGH


class TestDomainEvents:
    """Tests for domain events."""
    
    def test_analysis_completed_event_creation(self, sample_analysis_result):
        """Test creation of AnalysisCompleted event."""
        event = AnalysisCompleted(
            occurred_at=datetime.now(),
            event_id="test_event_123",
            stock_code="005930",
            analysis_result=sample_analysis_result
        )
        
        assert event.stock_code == "005930"
        assert event.analysis_result == sample_analysis_result
        assert isinstance(event.occurred_at, datetime)
        assert event.event_id == "test_event_123"
    
    def test_human_approval_required_event_creation(self, sample_investment_decision):
        """Test creation of HumanApprovalRequired event."""
        risk_factors = ["High volatility", "Large position size"]
        event = HumanApprovalRequired(
            occurred_at=datetime.now(),
            event_id="approval_event_123",
            investment_decision=sample_investment_decision,
            risk_factors=risk_factors
        )
        
        assert event.investment_decision == sample_investment_decision
        assert event.risk_factors == risk_factors
        assert isinstance(event.occurred_at, datetime)
    
    def test_trade_executed_event_creation(self):
        """Test creation of TradeExecuted event."""
        event = TradeExecuted(
            occurred_at=datetime.now(),
            event_id="trade_event_123",
            stock_code="005930",
            action=InvestmentSignal.BUY,
            quantity=100,
            executed_price=Decimal("75500"),
            total_amount=Decimal("7550000")
        )
        
        assert event.stock_code == "005930"
        assert event.action == InvestmentSignal.BUY
        assert event.quantity == 100
        assert event.executed_price == Decimal("75500")
        assert event.total_amount == Decimal("7550000")
    
    def test_domain_events_immutability(self, sample_analysis_result):
        """Test that domain events are immutable."""
        event = AnalysisCompleted(
            occurred_at=datetime.now(),
            event_id="test_event_123",
            stock_code="005930",
            analysis_result=sample_analysis_result
        )
        
        with pytest.raises(AttributeError):
            event.stock_code = "999999"


class TestEnumValues:
    """Tests for enum values and behavior."""
    
    def test_investment_signal_enum_values(self):
        """Test all investment signal enum values."""
        expected_values = {
            "STRONG_BUY", "BUY", "HOLD", "SELL", "STRONG_SELL"
        }
        actual_values = {signal.value for signal in InvestmentSignal}
        assert actual_values == expected_values
    
    def test_risk_level_enum_values(self):
        """Test all risk level enum values."""
        expected_values = {"LOW", "MEDIUM", "HIGH", "VERY_HIGH"}
        actual_values = {level.value for level in RiskLevel}
        assert actual_values == expected_values
    
    @pytest.mark.parametrize("signal_value", [
        "STRONG_BUY", "BUY", "HOLD", "SELL", "STRONG_SELL"
    ])
    def test_investment_signal_string_conversion(self, signal_value):
        """Test investment signal creation from string."""
        signal = InvestmentSignal(signal_value)
        assert signal.value == signal_value
    
    @pytest.mark.parametrize("risk_value", ["LOW", "MEDIUM", "HIGH", "VERY_HIGH"])
    def test_risk_level_string_conversion(self, risk_value):
        """Test risk level creation from string."""
        risk = RiskLevel(risk_value)
        assert risk.value == risk_value


class TestEdgeCasesAndBoundaryConditions:
    """Tests for edge cases and boundary conditions."""
    
    def test_zero_quantity_investment_decision(self, sample_analysis_result):
        """Test investment decision with zero quantity."""
        decision = InvestmentDecision(
            stock_code="005930",
            action=InvestmentSignal.BUY,
            quantity=0,
            max_price=Decimal("76000"),
            risk_level=RiskLevel.LOW,
            requires_human_approval=False,
            analysis_result=sample_analysis_result
        )
        
        amount = decision.calculate_investment_amount(Decimal("75000"))
        assert amount == Decimal("0")
    
    def test_very_large_numbers(self):
        """Test handling of very large numbers."""
        large_price = Decimal("999999999999")
        large_volume = 999999999999
        
        market_data = MarketData(
            stock_code="123456",
            current_price=large_price,
            volume=large_volume,
            market_cap=large_price * Decimal("1000000"),  # Very large market cap
            timestamp=datetime.now()
        )
        
        assert market_data.current_price == large_price
        assert market_data.volume == large_volume
    
    def test_precision_handling_in_calculations(self):
        """Test decimal precision in calculations."""
        market_data = MarketData(
            stock_code="123456",
            current_price=Decimal("123.456789"),
            volume=1000,
            market_cap=None,
            timestamp=datetime.now()
        )
        
        # Test that precision is maintained
        previous_price = Decimal("120.123456")
        change_rate = market_data.price_change_rate(previous_price)
        
        # Should maintain precision in calculation
        expected = (Decimal("123.456789") - Decimal("120.123456")) / Decimal("120.123456") * 100
        assert abs(change_rate - expected) < Decimal("0.000001")
    
    def test_datetime_edge_cases(self):
        """Test datetime edge cases."""
        # Test with very old date
        old_date = datetime(1900, 1, 1)
        analysis = AnalysisResult(
            stock_code="123456",
            signal=InvestmentSignal.BUY,
            confidence=0.8,
            target_price=Decimal("50000"),
            reasoning="Old analysis",
            analyzed_at=old_date
        )
        assert analysis.analyzed_at == old_date
        
        # Test with future date
        future_date = datetime(2100, 12, 31)
        analysis = AnalysisResult(
            stock_code="123456",
            signal=InvestmentSignal.SELL,
            confidence=0.7,
            target_price=Decimal("30000"),
            reasoning="Future analysis",
            analyzed_at=future_date
        )
        assert analysis.analyzed_at == future_date