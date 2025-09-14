"""
FastAPI routers with dependency injection.

This module demonstrates clean API endpoint design with:
- Proper HTTP status codes
- Dependency injection pattern
- Comprehensive error handling
- OpenAPI documentation
- Input validation and response formatting
"""

from typing import Dict, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status, Path, Body
from fastapi.responses import JSONResponse

from dependencies import (
    StockAnalysisService,
    InvestmentService, 
    PortfolioService,
    get_stock_analysis_service,
    get_investment_service,
    get_portfolio_service
)
from models import (
    StockAnalysisRequest,
    StockAnalysisResponse,
    InvestmentRequest,
    InvestmentResponse,
    PortfolioRequest,
    PortfolioSummaryResponse,
    ErrorResponse,
    APIExamples
)


def create_router() -> APIRouter:
    """
    Factory function to create and configure the main API router.
    
    Returns:
        APIRouter: Configured router with all endpoints
    """
    router = APIRouter()
    
    # Stock Analysis endpoints
    @router.post(
        "/analyze/{stock_code}",
        response_model=StockAnalysisResponse,
        status_code=status.HTTP_200_OK,
        summary="Analyze Stock",
        description="Perform comprehensive analysis of a stock by its symbol",
        responses={
            200: {
                "description": "Stock analysis completed successfully",
                "content": {
                    "application/json": {
                        "example": APIExamples.STOCK_ANALYSIS_RESPONSE
                    }
                }
            },
            400: {
                "description": "Invalid stock code or request parameters",
                "model": ErrorResponse
            },
            404: {
                "description": "Stock not found",
                "model": ErrorResponse
            },
            422: {
                "description": "Validation error",
                "model": ErrorResponse
            },
            500: {
                "description": "Internal server error",
                "model": ErrorResponse
            }
        },
        tags=["Stock Analysis"]
    )
    async def analyze_stock(
        stock_code: str = Path(
            ..., 
            min_length=1,
            max_length=10,
            description="Stock symbol to analyze (e.g., AAPL, GOOGL, TSLA)",
            example="AAPL"
        ),
        request_data: StockAnalysisRequest = Body(
            default=StockAnalysisRequest(),
            description="Analysis parameters",
            example=APIExamples.STOCK_ANALYSIS_REQUEST
        ),
        analysis_service: StockAnalysisService = Depends(get_stock_analysis_service)
    ) -> StockAnalysisResponse:
        """
        Analyze a stock by its symbol.
        
        This endpoint performs comprehensive stock analysis including:
        - Current price and price movements
        - Trading volume analysis
        - Risk assessment
        - Investment recommendation
        - Optional detailed financial metrics
        
        Args:
            stock_code: Stock symbol (e.g., AAPL, GOOGL, TSLA)
            request_data: Analysis parameters
            analysis_service: Injected stock analysis service
            
        Returns:
            StockAnalysisResponse: Comprehensive analysis results
            
        Raises:
            HTTPException: 400 for invalid input, 404 if stock not found
        """
        try:
            # Validate stock code format
            if not stock_code.isalpha():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid stock code format: {stock_code}"
                )
            
            # Perform analysis
            analysis_result = await analysis_service.analyze_stock(stock_code.upper())
            
            # Add detailed metrics if requested
            if request_data.include_detailed_metrics:
                analysis_result["detailed_metrics"] = {
                    "pe_ratio": 25.4,
                    "market_cap": 2500000000000,  # 2.5T
                    "dividend_yield": 0.5,
                    "beta": 1.2,
                    "analysis_period": request_data.analysis_period
                }
            
            # Create response with request tracking
            response = StockAnalysisResponse(
                request_id=str(uuid4()),
                **analysis_result
            )
            
            return response
            
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Analysis failed: {str(e)}"
            )
    
    # Investment endpoints
    @router.post(
        "/invest",
        response_model=InvestmentResponse,
        status_code=status.HTTP_201_CREATED,
        summary="Execute Investment",
        description="Execute an investment order with specified parameters",
        responses={
            201: {
                "description": "Investment executed successfully",
                "content": {
                    "application/json": {
                        "example": APIExamples.INVESTMENT_RESPONSE
                    }
                }
            },
            400: {
                "description": "Invalid investment parameters",
                "model": ErrorResponse
            },
            402: {
                "description": "Insufficient funds",
                "model": ErrorResponse
            },
            422: {
                "description": "Validation error",
                "model": ErrorResponse
            },
            500: {
                "description": "Internal server error",
                "model": ErrorResponse
            }
        },
        tags=["Investment"]
    )
    async def execute_investment(
        investment_data: InvestmentRequest = Body(
            ...,
            description="Investment parameters",
            example=APIExamples.INVESTMENT_REQUEST
        ),
        investment_service: InvestmentService = Depends(get_investment_service)
    ) -> InvestmentResponse:
        """
        Execute an investment order.
        
        This endpoint processes investment orders with various strategies:
        - Market orders: Execute immediately at current market price
        - Limit orders: Execute when price reaches specified limit
        - Stop loss orders: Execute when price drops to stop level
        - Dollar cost averaging: Execute periodic investments
        
        Args:
            investment_data: Investment order parameters
            investment_service: Injected investment service
            
        Returns:
            InvestmentResponse: Investment execution results
            
        Raises:
            HTTPException: 400 for invalid input, 402 for insufficient funds
        """
        try:
            # Additional validation for business rules
            if investment_data.amount < 1.0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Minimum investment amount is $1.00"
                )
            
            if investment_data.amount > 100000.0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Maximum investment amount is $100,000.00"
                )
            
            # Execute investment
            execution_result = await investment_service.execute_investment(
                stock_code=investment_data.stock_code,
                amount=investment_data.amount,
                strategy=investment_data.strategy
            )
            
            # Create response with request tracking
            response = InvestmentResponse(
                request_id=str(uuid4()),
                **execution_result
            )
            
            return response
            
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Investment execution failed: {str(e)}"
            )
    
    # Portfolio endpoints
    @router.get(
        "/portfolio",
        response_model=PortfolioSummaryResponse,
        status_code=status.HTTP_200_OK,
        summary="Get Portfolio Summary",
        description="Retrieve comprehensive portfolio summary for a user",
        responses={
            200: {
                "description": "Portfolio summary retrieved successfully",
                "content": {
                    "application/json": {
                        "example": APIExamples.PORTFOLIO_RESPONSE
                    }
                }
            },
            400: {
                "description": "Invalid user ID",
                "model": ErrorResponse
            },
            404: {
                "description": "Portfolio not found",
                "model": ErrorResponse
            },
            500: {
                "description": "Internal server error",
                "model": ErrorResponse
            }
        },
        tags=["Portfolio"]
    )
    async def get_portfolio_summary(
        user_id: str = "user123",  # Query parameter with default
        include_positions: bool = True,
        include_performance: bool = True,
        portfolio_service: PortfolioService = Depends(get_portfolio_service)
    ) -> PortfolioSummaryResponse:
        """
        Get portfolio summary for a user.
        
        This endpoint provides comprehensive portfolio information including:
        - Total portfolio value and cash balance
        - Individual stock positions with P&L
        - Performance metrics and diversification score
        - Position counts and allocation breakdown
        
        Args:
            user_id: User identifier
            include_positions: Include detailed position information
            include_performance: Include performance metrics
            portfolio_service: Injected portfolio service
            
        Returns:
            PortfolioSummaryResponse: Complete portfolio summary
            
        Raises:
            HTTPException: 400 for invalid input, 404 if portfolio not found
        """
        try:
            # Validate user ID
            if not user_id or len(user_id.strip()) == 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="User ID cannot be empty"
                )
            
            if len(user_id) > 50:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="User ID too long (max 50 characters)"
                )
            
            # Get portfolio data
            portfolio_data = await portfolio_service.get_portfolio_summary(user_id)
            
            # Filter data based on request parameters
            if not include_positions:
                portfolio_data["positions"] = []
                portfolio_data["position_count"] = 0
            
            if not include_performance:
                # Remove performance-related fields
                for key in ["total_unrealized_pnl", "total_unrealized_pnl_percent", "diversification_score"]:
                    portfolio_data.pop(key, None)
            
            # Create response with request tracking
            response = PortfolioSummaryResponse(
                request_id=str(uuid4()),
                **portfolio_data
            )
            
            return response
            
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to retrieve portfolio: {str(e)}"
            )
    
    # Health check endpoint
    @router.get(
        "/health",
        status_code=status.HTTP_200_OK,
        summary="Health Check",
        description="Check the health status of the API service",
        responses={
            200: {
                "description": "Service is healthy",
                "content": {
                    "application/json": {
                        "example": {
                            "status": "healthy",
                            "service": "Stock Analysis API",
                            "version": "1.0.0",
                            "timestamp": "2024-09-13T10:30:00Z",
                            "checks": {
                                "database": "healthy",
                                "external_apis": "healthy",
                                "cache": "healthy"
                            }
                        }
                    }
                }
            },
            503: {
                "description": "Service is unhealthy",
                "model": ErrorResponse
            }
        },
        tags=["Health"]
    )
    async def health_check() -> Dict[str, Any]:
        """
        Perform health check of the API service.
        
        This endpoint checks the health of various system components:
        - Database connectivity
        - External API availability
        - Cache system status
        - Overall service health
        
        Returns:
            Dict[str, Any]: Health status information
        """
        try:
            # Perform health checks (mock implementation)
            health_checks = {
                "database": "healthy",
                "external_apis": "healthy", 
                "cache": "healthy"
            }
            
            # Determine overall status
            overall_status = "healthy"
            if any(status != "healthy" for status in health_checks.values()):
                overall_status = "degraded"
            
            return {
                "status": overall_status,
                "service": "Stock Analysis API",
                "version": "1.0.0",
                "checks": health_checks
            }
            
        except Exception as e:
            # Return 503 for unhealthy status
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Health check failed: {str(e)}"
            )
    
    return router