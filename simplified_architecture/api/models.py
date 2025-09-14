"""
Pydantic models for request/response validation.

This module contains all API models demonstrating:
- Request/response model separation
- Input validation with constraints
- Response models with computed fields
- Error response standardization
- OpenAPI documentation integration
"""

from typing import List, Optional, Dict, Any, Literal
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, ConfigDict, validator
from pydantic.types import PositiveFloat, PositiveInt


# Base models
class BaseResponse(BaseModel):
    """Base response model with common metadata."""
    
    model_config = ConfigDict(
        json_encoders={
            datetime: lambda v: v.isoformat(),
            Decimal: lambda v: float(v)
        }
    )
    
    timestamp: datetime = Field(
        default_factory=datetime.now,
        description="Response timestamp in ISO format"
    )
    request_id: Optional[str] = Field(
        default=None,
        description="Unique request identifier for tracing"
    )


# Error models
class ErrorDetail(BaseModel):
    """Individual error detail."""
    
    field: str = Field(..., description="Field name that caused the error")
    message: str = Field(..., description="Human-readable error message")
    type: str = Field(..., description="Error type identifier")


class ErrorResponse(BaseModel):
    """Standardized error response model."""
    
    error: str = Field(..., description="Error category")
    message: str = Field(..., description="Human-readable error message")
    details: Optional[List[ErrorDetail]] = Field(
        default=None,
        description="Detailed error information"
    )
    timestamp: datetime = Field(
        default_factory=datetime.now,
        description="Error timestamp"
    )


# Stock Analysis models
class StockAnalysisRequest(BaseModel):
    """Request model for stock analysis."""
    
    include_detailed_metrics: bool = Field(
        default=False,
        description="Include detailed financial metrics in response"
    )
    analysis_period: Literal["1d", "7d", "30d", "90d", "1y"] = Field(
        default="30d",
        description="Analysis time period"
    )


class StockPosition(BaseModel):
    """Stock position information."""
    
    stock_code: str = Field(..., description="Stock symbol")
    shares: PositiveFloat = Field(..., description="Number of shares owned")
    current_price: PositiveFloat = Field(..., description="Current price per share")
    market_value: PositiveFloat = Field(..., description="Current market value")
    cost_basis: PositiveFloat = Field(..., description="Original cost basis")
    unrealized_pnl: float = Field(..., description="Unrealized profit/loss")
    unrealized_pnl_percent: float = Field(..., description="Unrealized P&L percentage")


class StockAnalysisResponse(BaseResponse):
    """Response model for stock analysis."""
    
    stock_code: str = Field(..., description="Stock symbol that was analyzed")
    price: PositiveFloat = Field(..., description="Current stock price")
    change_percent: float = Field(..., description="Price change percentage")
    volume: PositiveInt = Field(..., description="Trading volume")
    recommendation: Literal["BUY", "SELL", "HOLD"] = Field(
        ..., 
        description="Investment recommendation"
    )
    risk_level: Literal["LOW", "MEDIUM", "HIGH"] = Field(
        ..., 
        description="Risk assessment level"
    )
    analyzed_at: datetime = Field(..., description="Analysis timestamp")
    analysis_summary: str = Field(..., description="Brief analysis summary")
    
    # Optional detailed metrics
    detailed_metrics: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Detailed financial metrics (if requested)"
    )


# Investment models
class InvestmentRequest(BaseModel):
    """Request model for investment execution."""
    
    stock_code: str = Field(
        ..., 
        min_length=1,
        max_length=10,
        description="Stock symbol to invest in",
        example="AAPL"
    )
    amount: PositiveFloat = Field(
        ..., 
        ge=1.0,
        le=1000000.0,
        description="Investment amount in USD",
        example=1000.0
    )
    strategy: Literal["market", "limit", "stop_loss", "dca"] = Field(
        default="market",
        description="Investment strategy to use"
    )
    limit_price: Optional[PositiveFloat] = Field(
        default=None,
        description="Limit price for limit orders"
    )
    
    @validator("limit_price")
    def validate_limit_price(cls, v, values):
        """Validate limit price is provided for limit strategy."""
        if values.get("strategy") == "limit" and v is None:
            raise ValueError("limit_price is required for limit strategy")
        return v


class InvestmentResponse(BaseResponse):
    """Response model for investment execution."""
    
    transaction_id: str = Field(..., description="Unique transaction identifier")
    stock_code: str = Field(..., description="Stock symbol invested in")
    amount: PositiveFloat = Field(..., description="Investment amount")
    strategy: str = Field(..., description="Investment strategy used")
    shares_purchased: PositiveFloat = Field(..., description="Number of shares purchased")
    price_per_share: PositiveFloat = Field(..., description="Execution price per share")
    executed_at: datetime = Field(..., description="Execution timestamp")
    status: Literal["EXECUTED", "PENDING", "FAILED"] = Field(
        ..., 
        description="Transaction status"
    )
    fees: PositiveFloat = Field(..., description="Transaction fees")
    total_cost: PositiveFloat = Field(..., description="Total cost including fees")


# Portfolio models
class PortfolioRequest(BaseModel):
    """Request model for portfolio summary."""
    
    user_id: str = Field(
        ..., 
        min_length=1,
        max_length=50,
        description="User identifier",
        example="user123"
    )
    include_positions: bool = Field(
        default=True,
        description="Include detailed position information"
    )
    include_performance: bool = Field(
        default=True,
        description="Include performance metrics"
    )


class PortfolioSummaryResponse(BaseResponse):
    """Response model for portfolio summary."""
    
    user_id: str = Field(..., description="User identifier")
    total_value: PositiveFloat = Field(..., description="Total portfolio value")
    cash_balance: PositiveFloat = Field(..., description="Available cash balance")
    invested_value: PositiveFloat = Field(..., description="Total invested amount")
    positions: List[StockPosition] = Field(..., description="Stock positions")
    total_unrealized_pnl: float = Field(..., description="Total unrealized P&L")
    total_unrealized_pnl_percent: float = Field(..., description="Total unrealized P&L %")
    last_updated: datetime = Field(..., description="Last update timestamp")
    position_count: int = Field(..., description="Number of positions")
    diversification_score: float = Field(
        ..., 
        ge=0.0, 
        le=1.0,
        description="Portfolio diversification score (0-1)"
    )


# Health check model
class HealthResponse(BaseModel):
    """Health check response model."""
    
    status: Literal["healthy", "degraded", "unhealthy"] = Field(
        ..., 
        description="Service health status"
    )
    service: str = Field(..., description="Service name")
    version: str = Field(..., description="Service version")
    timestamp: datetime = Field(
        default_factory=datetime.now,
        description="Health check timestamp"
    )
    checks: Optional[Dict[str, str]] = Field(
        default=None,
        description="Individual health check results"
    )


# API Documentation examples
class APIExamples:
    """OpenAPI documentation examples."""
    
    STOCK_ANALYSIS_REQUEST = {
        "include_detailed_metrics": False,
        "analysis_period": "30d"
    }
    
    STOCK_ANALYSIS_RESPONSE = {
        "stock_code": "AAPL",
        "price": 150.25,
        "change_percent": 2.3,
        "volume": 1000000,
        "recommendation": "BUY",
        "risk_level": "MEDIUM",
        "analyzed_at": "2024-09-13T10:30:00Z",
        "analysis_summary": "Stock AAPL is showing positive momentum",
        "timestamp": "2024-09-13T10:30:00Z",
        "request_id": "req_123456"
    }
    
    INVESTMENT_REQUEST = {
        "stock_code": "AAPL",
        "amount": 1000.0,
        "strategy": "market"
    }
    
    INVESTMENT_RESPONSE = {
        "transaction_id": "TXN-000001",
        "stock_code": "AAPL",
        "amount": 1000.0,
        "strategy": "market",
        "shares_purchased": 6.665,
        "price_per_share": 150.0,
        "executed_at": "2024-09-13T10:30:00Z",
        "status": "EXECUTED",
        "fees": 1.0,
        "total_cost": 1001.0,
        "timestamp": "2024-09-13T10:30:00Z"
    }
    
    PORTFOLIO_REQUEST = {
        "user_id": "user123",
        "include_positions": True,
        "include_performance": True
    }
    
    PORTFOLIO_RESPONSE = {
        "user_id": "user123",
        "total_value": 12103.50,
        "cash_balance": 5000.00,
        "invested_value": 7103.50,
        "positions": [
            {
                "stock_code": "AAPL",
                "shares": 10.0,
                "current_price": 150.25,
                "market_value": 1502.50,
                "cost_basis": 1450.00,
                "unrealized_pnl": 52.50,
                "unrealized_pnl_percent": 3.62
            }
        ],
        "total_unrealized_pnl": -46.50,
        "total_unrealized_pnl_percent": -0.65,
        "last_updated": "2024-09-13T10:30:00Z",
        "position_count": 2,
        "diversification_score": 0.85,
        "timestamp": "2024-09-13T10:30:00Z"
    }