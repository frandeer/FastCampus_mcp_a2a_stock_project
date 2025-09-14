"""
LLM Integration Service - OpenAI 기반 주식 분석 서비스

주요 기능:
1. OpenAI GPT-4 모델을 사용한 주식 분석
2. 구조화된 출력 및 응답 검증
3. 에러 핸들링 및 폴백 메커니즘
4. 레이트 리미팅 및 캐싱
5. 테스트용 모킹 서비스
"""

import asyncio
import json
import hashlib
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Dict, Any, Optional, List, Union
import os
import logging

from openai import AsyncOpenAI, APIError, RateLimitError, APITimeoutError
from pydantic import BaseModel, Field, ValidationError

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AnalysisSignal(str, Enum):
    """분석 결과 신호 타입"""
    STRONG_BUY = "STRONG_BUY"
    BUY = "BUY" 
    HOLD = "HOLD"
    SELL = "SELL"
    STRONG_SELL = "STRONG_SELL"


class StockAnalysisResponse(BaseModel):
    """구조화된 주식 분석 응답"""
    signal: AnalysisSignal = Field(description="투자 추천 신호")
    confidence: float = Field(
        ge=0.0, le=1.0, 
        description="분석 신뢰도 (0.0 ~ 1.0)"
    )
    target_price: Optional[float] = Field(
        gt=0, 
        description="목표 주가 (양수)",
        default=None
    )
    reasoning: str = Field(
        min_length=10,
        description="분석 근거 및 이유"
    )
    key_factors: List[str] = Field(
        min_items=1,
        max_items=5,
        description="핵심 분석 요소"
    )
    risk_assessment: str = Field(description="리스크 평가")
    time_horizon: str = Field(
        description="투자 권장 기간 (단기/중기/장기)"
    )


@dataclass
class CacheEntry:
    """캐시 엔트리"""
    data: Dict[str, Any]
    timestamp: datetime
    ttl_seconds: int = 300  # 5분 기본 TTL
    
    @property
    def is_expired(self) -> bool:
        """캐시 만료 여부 확인"""
        return datetime.now() > self.timestamp + timedelta(seconds=self.ttl_seconds)


class RateLimiter:
    """간단한 레이트 리미터"""
    
    def __init__(self, max_requests: int = 60, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: List[float] = []
    
    async def acquire(self) -> bool:
        """요청 허용 여부 확인"""
        now = time.time()
        
        # 윈도우 밖의 오래된 요청들 제거
        self.requests = [req_time for req_time in self.requests 
                        if now - req_time < self.window_seconds]
        
        if len(self.requests) < self.max_requests:
            self.requests.append(now)
            return True
        
        # 레이트 제한에 걸렸으면 잠시 대기
        oldest_request = min(self.requests)
        wait_time = self.window_seconds - (now - oldest_request) + 1
        if wait_time > 0:
            await asyncio.sleep(wait_time)
            return await self.acquire()
        
        return True


class PromptTemplates:
    """주식 분석용 프롬프트 템플릿"""
    
    STOCK_ANALYSIS_SYSTEM = """
당신은 전문 주식 분석가입니다. 주어진 정보를 바탕으로 정확하고 신뢰할 수 있는 주식 분석을 제공해야 합니다.

분석 시 고려사항:
1. 기술적 분석: 가격 동향, 거래량, 시가총액
2. 기본 분석: 섹터 특성, 시장 상황
3. 감정 분석: 뉴스 및 시장 감정
4. 리스크 요소: 변동성, 시장 리스크

분석 결과는 반드시 다음 형식으로 제공하세요:
- signal: 투자 신호 (STRONG_BUY, BUY, HOLD, SELL, STRONG_SELL 중 하나)
- confidence: 0.0~1.0 사이의 신뢰도
- target_price: 목표 주가 (양수, 없으면 null)
- reasoning: 상세한 분석 근거
- key_factors: 핵심 분석 요소 1-5개
- risk_assessment: 리스크 평가
- time_horizon: 투자 기간 권장 (단기/중기/장기)

보수적이고 신중한 분석을 제공하세요.
"""
    
    STOCK_ANALYSIS_USER = """
다음 주식을 분석해주세요:

주식 정보:
- 종목 코드: {stock_code}
- 종목 명: {stock_name}
- 섹터: {sector}

시장 데이터:
- 현재 주가: {current_price}원
- 거래량: {volume:,}주
- 시가총액: {market_cap}원

뉴스 감정 분석:
- 감정 점수: {sentiment_score} (긍정적: 0.5 이상, 부정적: 0.5 미만)

추가 정보:
- 과거 데이터 포인트 수: {historical_count}개

위 정보를 종합하여 투자 분석을 제공해주세요.
"""

    FALLBACK_PROMPT = """
데이터가 제한적인 상황에서 {stock_code} ({stock_name}) 주식에 대한 기본적인 분석을 제공해주세요.
알려진 정보:
- 현재가: {current_price}원
- 섹터: {sector}

보수적인 관점에서 분석해주세요.
"""


class OpenAILLMService:
    """OpenAI 기반 LLM 주식 분석 서비스"""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-4o-mini",
        max_retries: int = 3,
        timeout: float = 30.0,
        cache_ttl: int = 300,
        rate_limit_rpm: int = 60
    ):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key is required")
            
        self.model = model
        self.max_retries = max_retries
        self.timeout = timeout
        
        # OpenAI 클라이언트 초기화
        self.client = AsyncOpenAI(
            api_key=self.api_key,
            timeout=timeout,
            max_retries=max_retries
        )
        
        # 캐시 및 레이트 리미터 초기화
        self.cache: Dict[str, CacheEntry] = {}
        self.cache_ttl = cache_ttl
        self.rate_limiter = RateLimiter(max_requests=rate_limit_rpm)
        
        logger.info(f"OpenAI LLM Service initialized with model: {model}")
    
    def _generate_cache_key(self, stock_info: dict, market_data: dict, news_sentiment: dict) -> str:
        """캐시 키 생성"""
        # 입력 데이터의 해시를 사용하여 캐시 키 생성
        data = {
            "stock": stock_info,
            "market": market_data, 
            "sentiment": news_sentiment
        }
        content = json.dumps(data, sort_keys=True, default=str)
        return hashlib.md5(content.encode()).hexdigest()
    
    def _clean_expired_cache(self):
        """만료된 캐시 엔트리 정리"""
        expired_keys = [
            key for key, entry in self.cache.items() 
            if entry.is_expired
        ]
        for key in expired_keys:
            del self.cache[key]
    
    async def _make_openai_request(self, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        """OpenAI API 요청 실행"""
        await self.rate_limiter.acquire()
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "stock_analysis",
                        "schema": StockAnalysisResponse.model_json_schema(),
                        "strict": True
                    }
                },
                temperature=0.1,  # 낮은 temperature로 일관된 결과
                max_tokens=1000
            )
            
            content = response.choices[0].message.content
            if not content:
                raise ValueError("Empty response from OpenAI")
                
            return json.loads(content)
            
        except (APIError, APITimeoutError, RateLimitError) as e:
            logger.error(f"OpenAI API error: {e}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse OpenAI response: {e}")
            raise ValueError(f"Invalid JSON response: {e}")
    
    def _validate_and_clean_response(self, response_data: Dict[str, Any]) -> Dict[str, Any]:
        """응답 검증 및 정리"""
        try:
            # Pydantic 모델로 검증
            validated = StockAnalysisResponse(**response_data)
            
            # 사전 형태로 변환하되, Decimal 타입 처리
            result = asdict(validated) if hasattr(validated, '__dict__') else dict(validated)
            
            # target_price가 있으면 float에서 Decimal로 변환
            if result.get('target_price') is not None:
                result['target_price'] = float(result['target_price'])
            
            return result
            
        except ValidationError as e:
            logger.error(f"Response validation error: {e}")
            raise ValueError(f"Invalid response format: {e}")
    
    def _create_fallback_response(
        self, 
        stock_info: dict, 
        market_data: dict,
        error_message: str
    ) -> Dict[str, Any]:
        """폴백 응답 생성"""
        logger.warning(f"Using fallback response due to: {error_message}")
        
        # 보수적인 기본 분석
        current_price = market_data.get('current_price', 0)
        
        return {
            'signal': 'HOLD',
            'confidence': 0.3,  # 낮은 신뢰도
            'target_price': None,
            'reasoning': f"제한된 데이터로 인한 보수적 분석. 현재가 {current_price}원 기준으로 추가 정보 수집 후 재분석 권장.",
            'key_factors': [
                "데이터 부족으로 인한 제한적 분석",
                "보수적 접근 필요",
                "추가 정보 수집 권장"
            ],
            'risk_assessment': "높음 - 데이터 부족으로 리스크 평가 제한적",
            'time_horizon': "단기"
        }
    
    async def analyze_stock(
        self,
        stock_info: dict,
        market_data: dict, 
        news_sentiment: dict
    ) -> dict:
        """주식 분석 실행"""
        # 캐시 정리
        self._clean_expired_cache()
        
        # 캐시 확인
        cache_key = self._generate_cache_key(stock_info, market_data, news_sentiment)
        if cache_key in self.cache:
            cached_entry = self.cache[cache_key]
            if not cached_entry.is_expired:
                logger.info("Using cached analysis result")
                return cached_entry.data
        
        try:
            # 프롬프트 준비
            stock_code = stock_info.get('code', 'Unknown')
            stock_name = stock_info.get('name', 'Unknown')
            sector = stock_info.get('sector', 'Unknown')
            
            current_price = market_data.get('current_price', 0)
            volume = market_data.get('volume', 0)
            market_cap = market_data.get('market_cap', 'Unknown')
            
            sentiment_score = news_sentiment.get('sentiment', 0.5)
            historical_count = market_data.get('historical_count', 0)
            
            system_message = PromptTemplates.STOCK_ANALYSIS_SYSTEM
            user_message = PromptTemplates.STOCK_ANALYSIS_USER.format(
                stock_code=stock_code,
                stock_name=stock_name,
                sector=sector,
                current_price=current_price,
                volume=volume,
                market_cap=market_cap,
                sentiment_score=sentiment_score,
                historical_count=historical_count
            )
            
            messages = [
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_message}
            ]
            
            # OpenAI 요청 실행
            response_data = await self._make_openai_request(messages)
            
            # 응답 검증 및 정리
            result = self._validate_and_clean_response(response_data)
            
            # 캐시에 저장
            self.cache[cache_key] = CacheEntry(
                data=result,
                timestamp=datetime.now(),
                ttl_seconds=self.cache_ttl
            )
            
            logger.info(f"Stock analysis completed for {stock_code}: {result['signal']}")
            return result
            
        except Exception as e:
            logger.error(f"LLM analysis failed: {e}")
            # 폴백 응답 반환
            return self._create_fallback_response(stock_info, market_data, str(e))


class MockLLMService:
    """테스트용 목 LLM 서비스"""
    
    def __init__(self, delay_seconds: float = 0.1):
        self.delay_seconds = delay_seconds
        self.call_count = 0
        logger.info("Mock LLM Service initialized")
    
    async def analyze_stock(
        self,
        stock_info: dict,
        market_data: dict,
        news_sentiment: dict
    ) -> dict:
        """모킹된 주식 분석"""
        self.call_count += 1
        
        # 실제 API 호출 시뮬레이션을 위한 지연
        await asyncio.sleep(self.delay_seconds)
        
        stock_code = stock_info.get('code', 'Unknown')
        current_price = market_data.get('current_price', 100)
        sentiment = news_sentiment.get('sentiment', 0.5)
        
        # 간단한 로직으로 신호 결정
        if sentiment > 0.7:
            signal = "BUY"
            confidence = 0.8
        elif sentiment < 0.3:
            signal = "SELL" 
            confidence = 0.7
        else:
            signal = "HOLD"
            confidence = 0.6
        
        # 목표 가격 설정 (현재가 기준으로)
        target_price = float(current_price) * (1.1 if signal == "BUY" else 0.9 if signal == "SELL" else 1.0)
        
        result = {
            'signal': signal,
            'confidence': confidence,
            'target_price': target_price if signal != "HOLD" else None,
            'reasoning': f"모킹된 분석 결과 (호출 #{self.call_count}). 감정 점수 {sentiment:.2f}를 바탕으로 한 분석.",
            'key_factors': [
                f"감정 분석 점수: {sentiment:.2f}",
                f"현재 주가: {current_price}원",
                "테스트용 목 데이터"
            ],
            'risk_assessment': "중간 - 테스트 환경",
            'time_horizon': "중기"
        }
        
        logger.info(f"Mock analysis completed for {stock_code}: {signal}")
        return result


class LLMServiceFactory:
    """LLM 서비스 팩토리"""
    
    @staticmethod
    def create_service(
        service_type: str = "openai",
        **kwargs
    ) -> Union[OpenAILLMService, MockLLMService]:
        """LLM 서비스 생성"""
        if service_type.lower() == "openai":
            return OpenAILLMService(**kwargs)
        elif service_type.lower() == "mock":
            return MockLLMService(**kwargs)
        else:
            raise ValueError(f"Unknown service type: {service_type}")


# 사용 예제
async def example_usage():
    """사용 예제"""
    # Mock 서비스 사용
    mock_service = LLMServiceFactory.create_service("mock")
    
    stock_info = {
        "code": "005930",
        "name": "삼성전자",
        "sector": "반도체"
    }
    
    market_data = {
        "current_price": 75000,
        "volume": 1000000,
        "market_cap": 500000000000
    }
    
    news_sentiment = {
        "sentiment": 0.8
    }
    
    result = await mock_service.analyze_stock(stock_info, market_data, news_sentiment)
    print("Analysis Result:", json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(example_usage())