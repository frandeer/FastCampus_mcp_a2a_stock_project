"""
Domain Repository Interfaces - 저장소 추상화
의존성 역전 원칙에 따라 Domain이 Infrastructure를 정의
"""

from abc import ABC, abstractmethod
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from .entities import (
    Stock, 
    MarketData, 
    AnalysisResult, 
    InvestmentDecision
)


class StockRepository(ABC):
    """주식 정보 저장소 인터페이스"""
    
    @abstractmethod
    async def find_by_code(self, stock_code: str) -> Optional[Stock]:
        """종목 코드로 주식 정보 조회"""
        pass
    
    @abstractmethod
    async def find_by_sector(self, sector: str) -> List[Stock]:
        """섹터별 주식 목록 조회"""
        pass
    
    @abstractmethod
    async def search_by_name(self, name: str) -> List[Stock]:
        """종목명으로 주식 검색"""
        pass


class MarketDataRepository(ABC):
    """시장 데이터 저장소 인터페이스"""
    
    @abstractmethod
    async def get_current_data(self, stock_code: str) -> Optional[MarketData]:
        """현재 시장 데이터 조회"""
        pass
    
    @abstractmethod
    async def get_historical_data(
        self, 
        stock_code: str, 
        start_date: datetime, 
        end_date: datetime
    ) -> List[MarketData]:
        """과거 시장 데이터 조회"""
        pass
    
    @abstractmethod
    async def get_volume_profile(
        self, 
        stock_code: str, 
        days: int = 20
    ) -> List[MarketData]:
        """거래량 프로필 조회"""
        pass


class NewsRepository(ABC):
    """뉴스 저장소 인터페이스"""
    
    @abstractmethod
    async def get_stock_news(
        self, 
        stock_code: str, 
        hours: int = 24
    ) -> List[dict]:
        """종목 관련 뉴스 조회"""
        pass
    
    @abstractmethod
    async def get_market_sentiment(self, stock_code: str) -> float:
        """시장 감성 점수 조회 (-1.0 ~ 1.0)"""
        pass


class AnalysisRepository(ABC):
    """분석 결과 저장소 인터페이스"""
    
    @abstractmethod
    async def save_analysis(self, analysis: AnalysisResult) -> None:
        """분석 결과 저장"""
        pass
    
    @abstractmethod
    async def find_latest_analysis(self, stock_code: str) -> Optional[AnalysisResult]:
        """최신 분석 결과 조회"""
        pass
    
    @abstractmethod
    async def find_analysis_history(
        self, 
        stock_code: str, 
        days: int = 30
    ) -> List[AnalysisResult]:
        """분석 이력 조회"""
        pass


class TradingRepository(ABC):
    """거래 저장소 인터페이스"""
    
    @abstractmethod
    async def execute_order(
        self, 
        decision: InvestmentDecision, 
        current_price: Decimal
    ) -> dict:
        """주문 실행"""
        pass
    
    @abstractmethod
    async def get_account_balance(self) -> Decimal:
        """계좌 잔고 조회"""
        pass
    
    @abstractmethod
    async def get_portfolio_positions(self) -> List[dict]:
        """포트폴리오 포지션 조회"""
        pass
    
    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool:
        """주문 취소"""
        pass