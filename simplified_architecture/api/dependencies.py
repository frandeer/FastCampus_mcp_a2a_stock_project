"""
Dependency injection container for FastAPI application.

This module demonstrates the dependency injection pattern with:
- Service container pattern
- Interface-based dependency injection
- Singleton service management
- Async resource management
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime
import asyncio
import logging

# Configure logging
logger = logging.getLogger(__name__)


# Domain interfaces (would typically be in separate domain module)
class StockAnalysisService(ABC):
    """Interface for stock analysis service."""
    
    @abstractmethod
    async def analyze_stock(self, stock_code: str) -> Dict[str, Any]:
        """Analyze a stock by code."""
        pass


class InvestmentService(ABC):
    """Interface for investment service."""
    
    @abstractmethod
    async def execute_investment(
        self, 
        stock_code: str, 
        amount: float, 
        strategy: str
    ) -> Dict[str, Any]:
        """Execute an investment."""
        pass


class PortfolioService(ABC):
    """Interface for portfolio service."""
    
    @abstractmethod
    async def get_portfolio_summary(self, user_id: str) -> Dict[str, Any]:
        """Get portfolio summary for a user."""
        pass


# Concrete implementations
@dataclass
class StockAnalysisResult:
    """Stock analysis result data class."""
    stock_code: str
    price: float
    change_percent: float
    volume: int
    recommendation: str
    risk_level: str
    analyzed_at: datetime


class MockStockAnalysisService(StockAnalysisService):
    """Mock implementation of stock analysis service."""
    
    async def analyze_stock(self, stock_code: str) -> Dict[str, Any]:
        """
        Mock stock analysis.
        
        Args:
            stock_code: Stock symbol to analyze
            
        Returns:
            Dict containing analysis results
        """
        # Simulate async operation
        await asyncio.sleep(0.1)
        
        # Mock data based on stock code
        mock_data = {
            "AAPL": {"price": 150.25, "change_percent": 2.3, "volume": 1000000},
            "GOOGL": {"price": 2800.50, "change_percent": -1.2, "volume": 500000},
            "TSLA": {"price": 850.75, "change_percent": 5.7, "volume": 2000000},
        }
        
        data = mock_data.get(stock_code.upper(), {
            "price": 100.0, 
            "change_percent": 0.0, 
            "volume": 100000
        })
        
        result = StockAnalysisResult(
            stock_code=stock_code.upper(),
            price=data["price"],
            change_percent=data["change_percent"],
            volume=data["volume"],
            recommendation="HOLD" if abs(data["change_percent"]) < 2 else "BUY" if data["change_percent"] > 0 else "SELL",
            risk_level="MEDIUM" if abs(data["change_percent"]) < 3 else "HIGH",
            analyzed_at=datetime.now()
        )
        
        logger.info(f"Analyzed stock: {stock_code}")
        
        return {
            "stock_code": result.stock_code,
            "price": result.price,
            "change_percent": result.change_percent,
            "volume": result.volume,
            "recommendation": result.recommendation,
            "risk_level": result.risk_level,
            "analyzed_at": result.analyzed_at.isoformat(),
            "analysis_summary": f"Stock {stock_code} is showing {'positive' if result.change_percent > 0 else 'negative'} momentum"
        }


@dataclass
class InvestmentResult:
    """Investment execution result data class."""
    transaction_id: str
    stock_code: str
    amount: float
    strategy: str
    shares_purchased: float
    executed_at: datetime
    status: str


class MockInvestmentService(InvestmentService):
    """Mock implementation of investment service."""
    
    def __init__(self):
        self._transaction_counter = 0
    
    async def execute_investment(
        self, 
        stock_code: str, 
        amount: float, 
        strategy: str
    ) -> Dict[str, Any]:
        """
        Mock investment execution.
        
        Args:
            stock_code: Stock symbol to invest in
            amount: Investment amount in USD
            strategy: Investment strategy
            
        Returns:
            Dict containing execution results
        """
        # Simulate async operation
        await asyncio.sleep(0.2)
        
        self._transaction_counter += 1
        
        # Mock price for calculation
        mock_price = 150.0  # Would typically fetch from analysis service
        shares_purchased = round(amount / mock_price, 4)
        
        result = InvestmentResult(
            transaction_id=f"TXN-{self._transaction_counter:06d}",
            stock_code=stock_code.upper(),
            amount=amount,
            strategy=strategy,
            shares_purchased=shares_purchased,
            executed_at=datetime.now(),
            status="EXECUTED"
        )
        
        logger.info(f"Executed investment: {result.transaction_id}")
        
        return {
            "transaction_id": result.transaction_id,
            "stock_code": result.stock_code,
            "amount": result.amount,
            "strategy": result.strategy,
            "shares_purchased": result.shares_purchased,
            "price_per_share": mock_price,
            "executed_at": result.executed_at.isoformat(),
            "status": result.status,
            "fees": round(amount * 0.001, 2),  # 0.1% fee
            "total_cost": round(amount + (amount * 0.001), 2)
        }


@dataclass
class PortfolioSummary:
    """Portfolio summary data class."""
    user_id: str
    total_value: float
    cash_balance: float
    positions: List[Dict[str, Any]]
    daily_change: float
    daily_change_percent: float
    last_updated: datetime


class MockPortfolioService(PortfolioService):
    """Mock implementation of portfolio service."""
    
    async def get_portfolio_summary(self, user_id: str) -> Dict[str, Any]:
        """
        Mock portfolio summary retrieval.
        
        Args:
            user_id: User identifier
            
        Returns:
            Dict containing portfolio summary
        """
        # Simulate async operation
        await asyncio.sleep(0.1)
        
        # Mock portfolio data
        positions = [
            {
                "stock_code": "AAPL",
                "shares": 10.0,
                "current_price": 150.25,
                "market_value": 1502.50,
                "cost_basis": 1450.00,
                "unrealized_pnl": 52.50,
                "unrealized_pnl_percent": 3.62
            },
            {
                "stock_code": "GOOGL",
                "shares": 2.0,
                "current_price": 2800.50,
                "market_value": 5601.00,
                "cost_basis": 5700.00,
                "unrealized_pnl": -99.00,
                "unrealized_pnl_percent": -1.74
            }
        ]
        
        total_market_value = sum(pos["market_value"] for pos in positions)
        total_cost_basis = sum(pos["cost_basis"] for pos in positions)
        cash_balance = 5000.00
        total_value = total_market_value + cash_balance
        daily_change = total_market_value - total_cost_basis
        daily_change_percent = (daily_change / total_cost_basis) * 100 if total_cost_basis > 0 else 0
        
        summary = PortfolioSummary(
            user_id=user_id,
            total_value=total_value,
            cash_balance=cash_balance,
            positions=positions,
            daily_change=daily_change,
            daily_change_percent=daily_change_percent,
            last_updated=datetime.now()
        )
        
        logger.info(f"Retrieved portfolio for user: {user_id}")
        
        return {
            "user_id": summary.user_id,
            "total_value": round(summary.total_value, 2),
            "cash_balance": summary.cash_balance,
            "invested_value": round(total_market_value, 2),
            "positions": summary.positions,
            "total_unrealized_pnl": round(daily_change, 2),
            "total_unrealized_pnl_percent": round(daily_change_percent, 2),
            "last_updated": summary.last_updated.isoformat(),
            "position_count": len(positions),
            "diversification_score": 0.85  # Mock score
        }


class DependencyContainer:
    """
    Dependency injection container.
    
    Manages service instances and their lifecycles using the container pattern.
    Provides singleton services and handles async initialization/cleanup.
    """
    
    def __init__(self):
        self._services: Dict[str, Any] = {}
        self._initialized = False
    
    async def startup(self) -> None:
        """Initialize all services."""
        if self._initialized:
            return
        
        logger.info("Initializing dependency container...")
        
        # Initialize services (would typically involve database connections, etc.)
        self._services["stock_analysis"] = MockStockAnalysisService()
        self._services["investment"] = MockInvestmentService()
        self._services["portfolio"] = MockPortfolioService()
        
        self._initialized = True
        logger.info("Dependency container initialized successfully")
    
    async def shutdown(self) -> None:
        """Clean up all services."""
        if not self._initialized:
            return
        
        logger.info("Shutting down dependency container...")
        
        # Clean up services (close connections, etc.)
        for service_name, service in self._services.items():
            if hasattr(service, 'close'):
                await service.close()
            logger.info(f"Shut down service: {service_name}")
        
        self._services.clear()
        self._initialized = False
        logger.info("Dependency container shut down successfully")
    
    def get_stock_analysis_service(self) -> StockAnalysisService:
        """Get stock analysis service instance."""
        if not self._initialized:
            raise RuntimeError("Container not initialized")
        return self._services["stock_analysis"]
    
    def get_investment_service(self) -> InvestmentService:
        """Get investment service instance."""
        if not self._initialized:
            raise RuntimeError("Container not initialized")
        return self._services["investment"]
    
    def get_portfolio_service(self) -> PortfolioService:
        """Get portfolio service instance."""
        if not self._initialized:
            raise RuntimeError("Container not initialized")
        return self._services["portfolio"]


# FastAPI dependency providers
def _get_container(request) -> DependencyContainer:
    """FastAPI dependency to get the container from app state."""
    return request.app.state.container


def get_container():
    """FastAPI dependency provider."""
    from fastapi import Request, Depends
    return Depends(_get_container)


def get_stock_analysis_service(
    container: DependencyContainer = get_container()
) -> StockAnalysisService:
    """FastAPI dependency to get stock analysis service."""
    return container.get_stock_analysis_service()


def get_investment_service(
    container: DependencyContainer = get_container()
) -> InvestmentService:
    """FastAPI dependency to get investment service."""
    return container.get_investment_service()


def get_portfolio_service(
    container: DependencyContainer = get_container()
) -> PortfolioService:
    """FastAPI dependency to get portfolio service."""
    return container.get_portfolio_service()