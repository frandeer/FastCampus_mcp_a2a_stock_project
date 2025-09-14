"""
Infrastructure Adapters - 외부 시스템과의 연결
Clean Architecture의 가장 바깥 계층

Circuit Breaker, Retry, Caching 등 실제 운영에 필요한 패턴 포함
"""

import asyncio
import json
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Optional, Dict, Any
import structlog
from dataclasses import dataclass, field
from enum import Enum
import aiohttp
import hashlib

from ..domain.entities import Stock, MarketData, AnalysisResult, InvestmentDecision
from ..domain.repositories import (
    StockRepository,
    MarketDataRepository, 
    NewsRepository,
    AnalysisRepository,
    TradingRepository
)

logger = structlog.get_logger(__name__)


class CircuitBreakerState(Enum):
    """Circuit Breaker 상태"""
    CLOSED = "CLOSED"      # 정상 동작
    OPEN = "OPEN"          # 차단 상태
    HALF_OPEN = "HALF_OPEN"  # 복구 시도


@dataclass
class CircuitBreakerConfig:
    """Circuit Breaker 설정"""
    failure_threshold: int = 5      # 실패 임계값
    timeout: int = 60               # 타임아웃 (초)
    retry_timeout: int = 30         # 재시도 타임아웃 (초)


class CircuitBreaker:
    """Circuit Breaker 패턴 구현"""
    
    def __init__(self, config: CircuitBreakerConfig = CircuitBreakerConfig()):
        self.config = config
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.last_failure_time = None
        self.next_attempt = datetime.now()
    
    def can_execute(self) -> bool:
        """실행 가능 여부 확인"""
        if self.state == CircuitBreakerState.CLOSED:
            return True
        elif self.state == CircuitBreakerState.OPEN:
            if datetime.now() >= self.next_attempt:
                self.state = CircuitBreakerState.HALF_OPEN
                return True
            return False
        else:  # HALF_OPEN
            return True
    
    def on_success(self):
        """성공 시 호출"""
        self.failure_count = 0
        self.state = CircuitBreakerState.CLOSED
        
    def on_failure(self):
        """실패 시 호출"""
        self.failure_count += 1
        self.last_failure_time = datetime.now()
        
        if self.failure_count >= self.config.failure_threshold:
            self.state = CircuitBreakerState.OPEN
            self.next_attempt = datetime.now() + timedelta(seconds=self.config.retry_timeout)
            logger.warning(f"Circuit breaker opened due to {self.failure_count} failures")


class CacheEntry:
    """캐시 엔트리"""
    
    def __init__(self, data: Any, ttl: int = 300):  # 기본 5분
        self.data = data
        self.created_at = datetime.now()
        self.ttl = ttl
    
    def is_expired(self) -> bool:
        """만료 여부 확인"""
        return datetime.now() > self.created_at + timedelta(seconds=self.ttl)


class InMemoryCache:
    """인메모리 캐시 구현"""
    
    def __init__(self):
        self._cache: Dict[str, CacheEntry] = {}
        self._lock = asyncio.Lock()
    
    async def get(self, key: str) -> Optional[Any]:
        """캐시에서 데이터 조회"""
        async with self._lock:
            entry = self._cache.get(key)
            if entry and not entry.is_expired():
                logger.debug(f"Cache hit for key: {key}")
                return entry.data
            elif entry:
                # 만료된 엔트리 삭제
                del self._cache[key]
                logger.debug(f"Cache miss (expired) for key: {key}")
            else:
                logger.debug(f"Cache miss for key: {key}")
            return None
    
    async def set(self, key: str, data: Any, ttl: int = 300):
        """캐시에 데이터 저장"""
        async with self._lock:
            self._cache[key] = CacheEntry(data, ttl)
            logger.debug(f"Cache set for key: {key}, ttl: {ttl}s")
    
    async def invalidate(self, pattern: str = None):
        """캐시 무효화"""
        async with self._lock:
            if pattern:
                keys_to_remove = [k for k in self._cache.keys() if pattern in k]
                for key in keys_to_remove:
                    del self._cache[key]
                logger.debug(f"Cache invalidated for pattern: {pattern}")
            else:
                self._cache.clear()
                logger.debug("All cache invalidated")


class ResilientHTTPClient:
    """복원력 있는 HTTP 클라이언트"""
    
    def __init__(self, base_url: str, timeout: int = 10, max_retries: int = 3):
        self.base_url = base_url
        self.timeout = timeout
        self.max_retries = max_retries
        self.circuit_breaker = CircuitBreaker()
        self.session = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.timeout)
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def request(self, method: str, endpoint: str, **kwargs) -> Optional[dict]:
        """복원력 있는 HTTP 요청"""
        if not self.circuit_breaker.can_execute():
            logger.warning(f"Circuit breaker is open for {self.base_url}")
            return None
        
        url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        
        for attempt in range(self.max_retries + 1):
            try:
                async with self.session.request(method, url, **kwargs) as response:
                    if response.status == 200:
                        result = await response.json()
                        self.circuit_breaker.on_success()
                        return result
                    else:
                        logger.warning(f"HTTP {response.status} for {url}")
                        
            except Exception as e:
                logger.error(f"HTTP request failed (attempt {attempt + 1}): {e}")
                if attempt < self.max_retries:
                    # Exponential backoff
                    await asyncio.sleep(2 ** attempt)
                else:
                    self.circuit_breaker.on_failure()
        
        return None


# Repository Implementations
class KiwoomStockRepository(StockRepository):
    """키움증권 API를 통한 주식 정보 저장소"""
    
    def __init__(self, api_url: str, api_key: str, cache: InMemoryCache):
        self.api_url = api_url
        self.api_key = api_key
        self.cache = cache
    
    async def find_by_code(self, stock_code: str) -> Optional[Stock]:
        """종목 코드로 주식 정보 조회"""
        cache_key = f"stock_info_{stock_code}"
        
        # 캐시 확인
        cached = await self.cache.get(cache_key)
        if cached:
            return Stock(**cached)
        
        # API 호출
        async with ResilientHTTPClient(self.api_url) as client:
            result = await client.request(
                "GET",
                f"/stock/info/{stock_code}",
                headers={"Authorization": f"Bearer {self.api_key}"}
            )
            
            if result and result.get("success"):
                stock_data = result["data"]
                stock = Stock(
                    code=stock_data["code"],
                    name=stock_data["name"],
                    market=stock_data.get("market", "KOSPI"),
                    sector=stock_data.get("sector")
                )
                
                # 캐시 저장 (1시간)
                await self.cache.set(cache_key, stock.__dict__, ttl=3600)
                return stock
        
        return None
    
    async def find_by_sector(self, sector: str) -> List[Stock]:
        """섹터별 주식 목록 조회"""
        cache_key = f"sector_stocks_{sector}"
        
        cached = await self.cache.get(cache_key)
        if cached:
            return [Stock(**stock_data) for stock_data in cached]
        
        async with ResilientHTTPClient(self.api_url) as client:
            result = await client.request(
                "GET",
                f"/stock/sector/{sector}",
                headers={"Authorization": f"Bearer {self.api_key}"}
            )
            
            if result and result.get("success"):
                stocks = [
                    Stock(
                        code=item["code"],
                        name=item["name"],
                        market=item.get("market", "KOSPI"),
                        sector=sector
                    )
                    for item in result["data"]
                ]
                
                # 캐시 저장 (30분)
                await self.cache.set(cache_key, [s.__dict__ for s in stocks], ttl=1800)
                return stocks
        
        return []
    
    async def search_by_name(self, name: str) -> List[Stock]:
        """종목명으로 주식 검색"""
        # 검색은 캐시하지 않음 (실시간성 중요)
        async with ResilientHTTPClient(self.api_url) as client:
            result = await client.request(
                "GET",
                "/stock/search",
                params={"query": name},
                headers={"Authorization": f"Bearer {self.api_key}"}
            )
            
            if result and result.get("success"):
                return [
                    Stock(
                        code=item["code"],
                        name=item["name"],
                        market=item.get("market", "KOSPI"),
                        sector=item.get("sector")
                    )
                    for item in result["data"]
                ]
        
        return []


class KiwoomMarketDataRepository(MarketDataRepository):
    """키움증권 API를 통한 시장 데이터 저장소"""
    
    def __init__(self, api_url: str, api_key: str, cache: InMemoryCache):
        self.api_url = api_url
        self.api_key = api_key  
        self.cache = cache
    
    async def get_current_data(self, stock_code: str) -> Optional[MarketData]:
        """현재 시장 데이터 조회"""
        cache_key = f"market_data_{stock_code}"
        
        # 단기 캐시 확인 (30초)
        cached = await self.cache.get(cache_key)
        if cached:
            return MarketData(**cached)
        
        async with ResilientHTTPClient(self.api_url) as client:
            result = await client.request(
                "GET",
                f"/market/current/{stock_code}",
                headers={"Authorization": f"Bearer {self.api_key}"}
            )
            
            if result and result.get("success"):
                data = result["data"]
                market_data = MarketData(
                    stock_code=stock_code,
                    current_price=Decimal(str(data["price"])),
                    volume=data["volume"],
                    market_cap=Decimal(str(data["market_cap"])) if data.get("market_cap") else None,
                    timestamp=datetime.fromisoformat(data["timestamp"])
                )
                
                # 30초 캐시
                await self.cache.set(cache_key, market_data.__dict__, ttl=30)
                return market_data
        
        return None
    
    async def get_historical_data(
        self, 
        stock_code: str, 
        start_date: datetime, 
        end_date: datetime
    ) -> List[MarketData]:
        """과거 시장 데이터 조회"""
        # 과거 데이터는 변경되지 않으므로 장기 캐시
        cache_key = f"historical_{stock_code}_{start_date.date()}_{end_date.date()}"
        
        cached = await self.cache.get(cache_key)
        if cached:
            return [MarketData(**item) for item in cached]
        
        async with ResilientHTTPClient(self.api_url) as client:
            result = await client.request(
                "GET",
                f"/market/historical/{stock_code}",
                params={
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat()
                },
                headers={"Authorization": f"Bearer {self.api_key}"}
            )
            
            if result and result.get("success"):
                data_list = [
                    MarketData(
                        stock_code=stock_code,
                        current_price=Decimal(str(item["price"])),
                        volume=item["volume"],
                        market_cap=Decimal(str(item["market_cap"])) if item.get("market_cap") else None,
                        timestamp=datetime.fromisoformat(item["timestamp"])
                    )
                    for item in result["data"]
                ]
                
                # 1일 캐시
                await self.cache.set(cache_key, [d.__dict__ for d in data_list], ttl=86400)
                return data_list
        
        return []
    
    async def get_volume_profile(self, stock_code: str, days: int = 20) -> List[MarketData]:
        """거래량 프로필 조회"""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        return await self.get_historical_data(stock_code, start_date, end_date)


# Mock Trading Repository for Development
class MockTradingRepository(TradingRepository):
    """개발용 Mock 거래 저장소"""
    
    def __init__(self):
        self.account_balance = Decimal('10000000')  # 1천만원
        self.positions = {}
        self.order_history = []
        self.order_counter = 0
    
    async def execute_order(
        self, 
        decision: InvestmentDecision, 
        current_price: Decimal
    ) -> dict:
        """주문 실행 (Mock)"""
        try:
            self.order_counter += 1
            order_id = f"ORDER_{self.order_counter:06d}"
            
            if decision.action in [decision.action.BUY, decision.action.STRONG_BUY]:
                total_cost = Decimal(decision.quantity) * current_price
                
                if total_cost > self.account_balance:
                    return {
                        "success": False,
                        "error": "Insufficient balance"
                    }
                
                # 계좌 잔고 차감
                self.account_balance -= total_cost
                
                # 포지션 추가/업데이트
                if decision.stock_code in self.positions:
                    self.positions[decision.stock_code]["quantity"] += decision.quantity
                    # 평균 단가 계산
                    total_value = (
                        self.positions[decision.stock_code]["avg_price"] * 
                        self.positions[decision.stock_code]["quantity"]
                    ) + total_cost
                    total_quantity = self.positions[decision.stock_code]["quantity"]
                    self.positions[decision.stock_code]["avg_price"] = total_value / total_quantity
                else:
                    self.positions[decision.stock_code] = {
                        "quantity": decision.quantity,
                        "avg_price": current_price
                    }
            
            # 주문 이력 저장
            self.order_history.append({
                "order_id": order_id,
                "stock_code": decision.stock_code,
                "action": decision.action.value,
                "quantity": decision.quantity,
                "executed_price": current_price,
                "timestamp": datetime.now().isoformat()
            })
            
            logger.info(f"Mock order executed: {order_id}")
            
            return {
                "success": True,
                "order_id": order_id,
                "executed_price": current_price,
                "executed_quantity": decision.quantity
            }
            
        except Exception as e:
            logger.error(f"Mock order execution failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_account_balance(self) -> Decimal:
        """계좌 잔고 조회"""
        return self.account_balance
    
    async def get_portfolio_positions(self) -> List[dict]:
        """포트폴리오 포지션 조회"""
        return [
            {
                "stock_code": code,
                "quantity": pos["quantity"],
                "avg_price": pos["avg_price"],
                "value": pos["quantity"] * pos["avg_price"]
            }
            for code, pos in self.positions.items()
            if pos["quantity"] > 0
        ]
    
    async def cancel_order(self, order_id: str) -> bool:
        """주문 취소 (Mock)"""
        # 실제 구현에서는 미체결 주문만 취소 가능
        logger.info(f"Mock order cancellation: {order_id}")
        return True


# In-Memory Analysis Repository
class InMemoryAnalysisRepository(AnalysisRepository):
    """인메모리 분석 결과 저장소"""
    
    def __init__(self):
        self.analyses: List[AnalysisResult] = []
    
    async def save_analysis(self, analysis: AnalysisResult) -> None:
        """분석 결과 저장"""
        self.analyses.append(analysis)
        # 메모리 관리: 각 종목당 최신 100개만 유지
        stock_analyses = [a for a in self.analyses if a.stock_code == analysis.stock_code]
        if len(stock_analyses) > 100:
            # 오래된 분석 결과 제거
            oldest_analysis = min(stock_analyses, key=lambda x: x.analyzed_at)
            self.analyses.remove(oldest_analysis)
    
    async def find_latest_analysis(self, stock_code: str) -> Optional[AnalysisResult]:
        """최신 분석 결과 조회"""
        stock_analyses = [a for a in self.analyses if a.stock_code == stock_code]
        if stock_analyses:
            return max(stock_analyses, key=lambda x: x.analyzed_at)
        return None
    
    async def find_analysis_history(self, stock_code: str, days: int = 30) -> List[AnalysisResult]:
        """분석 이력 조회"""
        cutoff_date = datetime.now() - timedelta(days=days)
        return [
            a for a in self.analyses 
            if a.stock_code == stock_code and a.analyzed_at >= cutoff_date
        ]