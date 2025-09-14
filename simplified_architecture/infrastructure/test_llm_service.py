"""
LLM Service 테스트
"""

import asyncio
import json
import os
import sys
from pathlib import Path

# 프로젝트 루트 추가
sys.path.append(str(Path(__file__).parent.parent.parent))

from simplified_architecture.infrastructure.llm_service import (
    LLMServiceFactory,
    OpenAILLMService,
    MockLLMService,
    StockAnalysisResponse
)


async def test_mock_service():
    """Mock 서비스 테스트"""
    print("=== Mock LLM Service Test ===")
    
    mock_service = LLMServiceFactory.create_service("mock", delay_seconds=0.1)
    
    # 테스트 데이터
    stock_info = {
        "code": "005930",
        "name": "삼성전자", 
        "sector": "반도체"
    }
    
    market_data = {
        "current_price": 75000,
        "volume": 1500000,
        "market_cap": 500000000000,
        "historical_count": 30
    }
    
    # 다양한 감정 시나리오 테스트
    sentiment_scenarios = [
        {"sentiment": 0.8, "description": "긍정적 뉴스"},
        {"sentiment": 0.2, "description": "부정적 뉴스"}, 
        {"sentiment": 0.5, "description": "중립적 뉴스"}
    ]
    
    for scenario in sentiment_scenarios:
        print(f"\n--- {scenario['description']} 시나리오 ---")
        
        result = await mock_service.analyze_stock(
            stock_info, 
            market_data, 
            {"sentiment": scenario["sentiment"]}
        )
        
        print(f"신호: {result['signal']}")
        print(f"신뢰도: {result['confidence']:.2f}")
        print(f"목표가: {result['target_price']}원" if result['target_price'] else "목표가: 없음")
        print(f"근거: {result['reasoning']}")
        print(f"핵심요인: {', '.join(result['key_factors'])}")
    
    print(f"\nTotal mock service calls: {mock_service.call_count}")


async def test_openai_service():
    """OpenAI 서비스 테스트 (API 키가 있는 경우)"""
    print("\n=== OpenAI LLM Service Test ===")
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("OPENAI_API_KEY not found, skipping OpenAI test")
        return
    
    try:
        openai_service = LLMServiceFactory.create_service(
            "openai",
            model="gpt-4o-mini",
            cache_ttl=60,
            rate_limit_rpm=10
        )
        
        stock_info = {
            "code": "005930", 
            "name": "삼성전자",
            "sector": "반도체"
        }
        
        market_data = {
            "current_price": 75000,
            "volume": 2000000,
            "market_cap": 500000000000,
            "historical_count": 90
        }
        
        news_sentiment = {
            "sentiment": 0.6
        }
        
        print("OpenAI 분석 요청 중...")
        result = await openai_service.analyze_stock(stock_info, market_data, news_sentiment)
        
        print("=== OpenAI 분석 결과 ===")
        print(f"신호: {result['signal']}")
        print(f"신뢰도: {result['confidence']:.2f}")
        print(f"목표가: {result['target_price']}원" if result['target_price'] else "목표가: 없음")
        print(f"근거: {result['reasoning']}")
        print(f"핵심요인: {', '.join(result['key_factors'])}")
        print(f"리스크 평가: {result['risk_assessment']}")
        print(f"투자기간: {result['time_horizon']}")
        
        # 캐시 테스트 - 같은 요청 재실행
        print("\n--- 캐시 테스트 (같은 요청 재실행) ---")
        start_time = asyncio.get_event_loop().time()
        cached_result = await openai_service.analyze_stock(stock_info, market_data, news_sentiment)
        end_time = asyncio.get_event_loop().time()
        
        print(f"캐시된 결과 반환 시간: {(end_time - start_time)*1000:.1f}ms")
        print(f"캐시 결과 일치: {result == cached_result}")
        
    except Exception as e:
        print(f"OpenAI 테스트 실패: {e}")


async def test_error_handling():
    """에러 처리 테스트"""
    print("\n=== Error Handling Test ===")
    
    # 잘못된 API 키로 서비스 생성
    try:
        invalid_service = OpenAILLMService(api_key="invalid-key", timeout=5.0)
        
        stock_info = {"code": "005930", "name": "삼성전자", "sector": "반도체"}
        market_data = {"current_price": 75000, "volume": 1000000}
        news_sentiment = {"sentiment": 0.5}
        
        # 에러 발생 시 폴백 응답 확인
        result = await invalid_service.analyze_stock(stock_info, market_data, news_sentiment)
        
        print("폴백 응답 생성됨:")
        print(f"신호: {result['signal']}")
        print(f"신뢰도: {result['confidence']}")
        print(f"근거: {result['reasoning']}")
        
    except Exception as e:
        print(f"예상된 에러 발생: {e}")


async def test_validation():
    """응답 검증 테스트"""
    print("\n=== Response Validation Test ===")
    
    # StockAnalysisResponse 검증 테스트
    valid_data = {
        "signal": "BUY",
        "confidence": 0.8,
        "target_price": 80000.0,
        "reasoning": "강력한 기술적 분석 신호",
        "key_factors": ["긍정적 뉴스", "높은 거래량", "기술적 돌파"],
        "risk_assessment": "중간 수준 리스크",
        "time_horizon": "중기"
    }
    
    try:
        validated = StockAnalysisResponse(**valid_data)
        print("✅ 유효한 데이터 검증 성공")
        print(f"검증된 신호: {validated.signal}")
        print(f"검증된 신뢰도: {validated.confidence}")
    except Exception as e:
        print(f"❌ 검증 실패: {e}")
    
    # 잘못된 데이터 테스트
    invalid_data = {
        "signal": "INVALID_SIGNAL",  # 잘못된 신호
        "confidence": 1.5,  # 범위 초과
        "target_price": -1000,  # 음수 가격
        "reasoning": "짧음",  # 너무 짧은 근거
        "key_factors": [],  # 빈 리스트
        "risk_assessment": "위험",
        "time_horizon": "즉시"
    }
    
    try:
        StockAnalysisResponse(**invalid_data)
        print("❌ 잘못된 데이터가 통과됨")
    except Exception as e:
        print(f"✅ 잘못된 데이터 검증 실패 (예상됨): {e}")


async def main():
    """메인 테스트 함수"""
    print("🚀 LLM Service 통합 테스트 시작\n")
    
    try:
        await test_mock_service()
        await test_validation()
        await test_error_handling()
        await test_openai_service()
        
        print("\n✅ 모든 테스트 완료!")
        
    except Exception as e:
        print(f"❌ 테스트 실행 중 오류: {e}")


if __name__ == "__main__":
    asyncio.run(main())