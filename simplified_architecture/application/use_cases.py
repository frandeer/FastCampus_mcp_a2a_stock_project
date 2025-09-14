"""
Application Use Cases - 비즈니스 유스케이스 구현
Clean Architecture의 Application Layer

의존성 주입을 통해 도메인 로직과 인프라 구현을 분리
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Protocol

from ..domain.entities import (
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
from ..domain.repositories import (
    StockRepository,
    MarketDataRepository,
    NewsRepository,
    AnalysisRepository,
    TradingRepository,
)


# Application Services Protocol
class EventPublisher(Protocol):
    """이벤트 발행자 인터페이스"""
    async def publish(self, event: object) -> None: ...


class HumanApprovalService(Protocol):
    """인간 승인 서비스 인터페이스"""
    async def request_approval(
        self, 
        decision: InvestmentDecision,
        context: dict
    ) -> bool: ...


class LLMService(Protocol):
    """LLM 서비스 인터페이스"""
    async def analyze_stock(
        self,
        stock_info: dict,
        market_data: dict,
        news_sentiment: dict
    ) -> dict: ...


# Result Pattern Implementation
@dataclass(frozen=True)
class Result:
    """결과 패턴 기본 클래스"""
    success: bool
    error_message: Optional[str] = None


@dataclass(frozen=True)
class AnalysisResult_UC(Result):
    """분석 결과"""
    analysis: Optional[AnalysisResult] = None


@dataclass(frozen=True)
class TradingResult_UC(Result):
    """거래 결과"""
    order_id: Optional[str] = None
    executed_price: Optional[Decimal] = None
    executed_quantity: Optional[int] = None


# Use Cases
class AnalyzeStockUseCase:
    """주식 분석 유스케이스"""
    
    def __init__(
        self,
        stock_repo: StockRepository,
        market_data_repo: MarketDataRepository,
        news_repo: NewsRepository,
        analysis_repo: AnalysisRepository,
        llm_service: LLMService,
        event_publisher: EventPublisher,
        risk_calculator: RiskCalculator = RiskCalculator()
    ):
        self._stock_repo = stock_repo
        self._market_data_repo = market_data_repo
        self._news_repo = news_repo
        self._analysis_repo = analysis_repo
        self._llm_service = llm_service
        self._event_publisher = event_publisher
        self._risk_calculator = risk_calculator
    
    async def execute(self, stock_code: str) -> AnalysisResult_UC:
        """주식 분석 실행"""
        try:
            # 1. 데이터 수집
            stock = await self._stock_repo.find_by_code(stock_code)
            if not stock:
                return AnalysisResult_UC(success=False, error_message=f"Stock {stock_code} not found")
            
            market_data = await self._market_data_repo.get_current_data(stock_code)
            if not market_data:
                return AnalysisResult_UC(success=False, error_message="Market data unavailable")
            
            # 2. 병렬로 추가 데이터 수집
            import asyncio
            news_task = self._news_repo.get_market_sentiment(stock_code)
            historical_task = self._market_data_repo.get_historical_data(
                stock_code, 
                datetime.now().replace(day=1), 
                datetime.now()
            )
            
            market_sentiment, historical_data = await asyncio.gather(
                news_task, historical_task, return_exceptions=True
            )
            
            # 3. LLM을 통한 종합 분석
            analysis_context = {
                "stock": {
                    "code": stock.code,
                    "name": stock.name,
                    "sector": stock.sector
                },
                "market_data": {
                    "current_price": float(market_data.current_price),
                    "volume": market_data.volume,
                    "market_cap": float(market_data.market_cap) if market_data.market_cap else None
                },
                "sentiment": float(market_sentiment) if not isinstance(market_sentiment, Exception) else 0.0,
                "historical_performance": len(historical_data) if not isinstance(historical_data, Exception) else 0
            }
            
            llm_result = await self._llm_service.analyze_stock(
                analysis_context["stock"],
                analysis_context["market_data"], 
                {"sentiment": analysis_context["sentiment"]}
            )
            
            # 4. 분석 결과 엔티티 생성
            analysis = AnalysisResult(
                stock_code=stock_code,
                signal=InvestmentSignal(llm_result.get("signal", "HOLD")),
                confidence=min(max(llm_result.get("confidence", 0.5), 0.0), 1.0),
                target_price=Decimal(str(llm_result.get("target_price", 0))) if llm_result.get("target_price") else None,
                reasoning=llm_result.get("reasoning", "Analysis completed"),
                analyzed_at=datetime.now()
            )
            
            # 5. 분석 결과 저장
            await self._analysis_repo.save_analysis(analysis)
            
            # 6. 이벤트 발행
            event = AnalysisCompleted(
                occurred_at=datetime.now(),
                event_id=f"analysis_{stock_code}_{int(datetime.now().timestamp())}",
                stock_code=stock_code,
                analysis_result=analysis
            )
            await self._event_publisher.publish(event)
            
            return AnalysisResult_UC(success=True, analysis=analysis)
            
        except Exception as e:
            return AnalysisResult_UC(success=False, error_message=str(e))


class ExecuteInvestmentUseCase:
    """투자 실행 유스케이스"""
    
    def __init__(
        self,
        analysis_repo: AnalysisRepository,
        trading_repo: TradingRepository,
        market_data_repo: MarketDataRepository,
        human_approval_service: HumanApprovalService,
        event_publisher: EventPublisher,
        risk_calculator: RiskCalculator = RiskCalculator()
    ):
        self._analysis_repo = analysis_repo
        self._trading_repo = trading_repo
        self._market_data_repo = market_data_repo
        self._human_approval_service = human_approval_service
        self._event_publisher = event_publisher
        self._risk_calculator = risk_calculator
    
    async def execute(
        self, 
        stock_code: str, 
        quantity: int,
        max_price: Optional[Decimal] = None
    ) -> TradingResult_UC:
        """투자 실행"""
        try:
            # 1. 최신 분석 결과 조회
            analysis = await self._analysis_repo.find_latest_analysis(stock_code)
            if not analysis:
                return TradingResult_UC(success=False, error_message="No analysis available")
            
            # 2. 현재 시장 데이터 조회
            market_data = await self._market_data_repo.get_current_data(stock_code)
            if not market_data:
                return TradingResult_UC(success=False, error_message="Market data unavailable")
            
            # 3. 포트폴리오 정보 조회
            portfolio_positions = await self._trading_repo.get_portfolio_positions()
            account_balance = await self._trading_repo.get_account_balance()
            
            # 4. 리스크 평가
            investment_amount = Decimal(quantity) * market_data.current_price
            portfolio_value = sum(Decimal(str(pos.get("value", 0))) for pos in portfolio_positions) + account_balance
            investment_ratio = float(investment_amount / portfolio_value) if portfolio_value > 0 else 1.0
            
            risk_level = self._risk_calculator.determine_risk_level(
                confidence=analysis.confidence,
                investment_ratio=investment_ratio,
                market_volatility=0.2  # 단순화된 변동성
            )
            
            # 5. 투자 결정 생성
            decision = InvestmentDecision(
                stock_code=stock_code,
                action=analysis.signal,
                quantity=quantity,
                max_price=max_price,
                risk_level=risk_level,
                requires_human_approval=decision.is_high_risk(investment_amount),
                analysis_result=analysis
            )
            
            # 6. Human-in-the-loop 승인 처리
            if decision.requires_human_approval:
                approval_event = HumanApprovalRequired(
                    occurred_at=datetime.now(),
                    event_id=f"approval_{stock_code}_{int(datetime.now().timestamp())}",
                    investment_decision=decision,
                    risk_factors=[
                        f"Risk level: {risk_level.value}",
                        f"Investment ratio: {investment_ratio:.2%}",
                        f"Analysis confidence: {analysis.confidence:.2%}"
                    ]
                )
                await self._event_publisher.publish(approval_event)
                
                approved = await self._human_approval_service.request_approval(
                    decision,
                    {"risk_factors": approval_event.risk_factors}
                )
                
                if not approved:
                    return TradingResult_UC(success=False, error_message="Human approval denied")
            
            # 7. 거래 실행
            execution_result = await self._trading_repo.execute_order(decision, market_data.current_price)
            
            if not execution_result.get("success", False):
                return TradingResult_UC(
                    success=False, 
                    error_message=execution_result.get("error", "Order execution failed")
                )
            
            return TradingResult_UC(
                success=True,
                order_id=execution_result.get("order_id"),
                executed_price=Decimal(str(execution_result.get("executed_price", 0))),
                executed_quantity=execution_result.get("executed_quantity", 0)
            )
            
        except Exception as e:
            return TradingResult_UC(success=False, error_message=str(e))


class GetPortfolioSummaryUseCase:
    """포트폴리오 요약 조회 유스케이스"""
    
    def __init__(
        self,
        trading_repo: TradingRepository,
        market_data_repo: MarketDataRepository,
        analysis_repo: AnalysisRepository,
        risk_calculator: RiskCalculator = RiskCalculator()
    ):
        self._trading_repo = trading_repo
        self._market_data_repo = market_data_repo
        self._analysis_repo = analysis_repo
        self._risk_calculator = risk_calculator
    
    async def execute(self) -> dict:
        """포트폴리오 요약 조회"""
        try:
            # 병렬로 데이터 조회
            import asyncio
            
            positions_task = self._trading_repo.get_portfolio_positions()
            balance_task = self._trading_repo.get_account_balance()
            
            positions, account_balance = await asyncio.gather(positions_task, balance_task)
            
            # 각 포지션의 현재 가치 계산
            position_values = []
            total_value = Decimal('0')
            
            for position in positions:
                stock_code = position.get("stock_code")
                quantity = position.get("quantity", 0)
                
                if stock_code and quantity > 0:
                    current_data = await self._market_data_repo.get_current_data(stock_code)
                    if current_data:
                        position_value = Decimal(quantity) * current_data.current_price
                        position_values.append({
                            "stock_code": stock_code,
                            "quantity": quantity,
                            "current_price": current_data.current_price,
                            "value": position_value,
                            "weight": 0  # 나중에 계산
                        })
                        total_value += position_value
            
            # 포트폴리오 총 가치
            portfolio_total = total_value + account_balance
            
            # 각 포지션의 비중 계산
            for position in position_values:
                position["weight"] = float(position["value"] / portfolio_total * 100) if portfolio_total > 0 else 0
            
            # 리스크 계산 (단순화된 VaR)
            portfolio_var = self._risk_calculator.calculate_var(
                portfolio_value=portfolio_total,
                volatility=0.15,  # 15% 변동성 가정
                confidence_level=0.95
            )
            
            return {
                "success": True,
                "portfolio": {
                    "total_value": float(portfolio_total),
                    "cash_balance": float(account_balance),
                    "invested_value": float(total_value),
                    "positions": position_values,
                    "risk_metrics": {
                        "var_95": float(portfolio_var),
                        "var_percentage": float(portfolio_var / portfolio_total * 100) if portfolio_total > 0 else 0
                    }
                }
            }
            
        except Exception as e:
            return {
                "success": False,
                "error_message": str(e)
            }