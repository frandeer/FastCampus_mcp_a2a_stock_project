"""
LLM Service 통합 예제
UseCase와 LLM Service의 통합 사용법 및 의존성 주입 예제
"""

import asyncio
import json
import sys
from pathlib import Path
from decimal import Decimal
from datetime import datetime

# 프로젝트 루트 추가
sys.path.append(str(Path(__file__).parent.parent.parent))

from simplified_architecture.infrastructure.llm_service import LLMServiceFactory
from simplified_architecture.domain.entities import (
    Stock, MarketData, AnalysisResult, InvestmentSignal
)


class MockStockRepository:
    """테스트용 주식 리포지토리"""
    
    async def find_by_code(self, stock_code: str):
        stocks = {
            "005930": Stock("005930", "삼성전자", "KOSPI", "반도체"),
            "000660": Stock("000660", "SK하이닉스", "KOSPI", "반도체"),
            "035720": Stock("035720", "카카오", "KOSPI", "인터넷")
        }
        return stocks.get(stock_code)


class MockMarketDataRepository:
    """테스트용 시장 데이터 리포지토리"""
    
    async def get_current_data(self, stock_code: str):
        data = {
            "005930": MarketData("005930", Decimal("75000"), 1500000, Decimal("500000000000"), datetime.now()),
            "000660": MarketData("000660", Decimal("120000"), 800000, Decimal("90000000000"), datetime.now()),
            "035720": MarketData("035720", Decimal("95000"), 1200000, Decimal("40000000000"), datetime.now())
        }
        return data.get(stock_code)
    
    async def get_historical_data(self, stock_code: str, start_date, end_date):
        # 임의의 과거 데이터 시뮬레이션
        return list(range(30))  # 30일 데이터


class MockNewsRepository:
    """테스트용 뉴스 리포지토리"""
    
    async def get_market_sentiment(self, stock_code: str):
        sentiments = {
            "005930": 0.7,  # 긍정적
            "000660": 0.3,  # 부정적
            "035720": 0.5   # 중립적
        }
        return sentiments.get(stock_code, 0.5)


class MockAnalysisRepository:
    """테스트용 분석 결과 리포지토리"""
    
    def __init__(self):
        self.analyses = []
    
    async def save_analysis(self, analysis: AnalysisResult):
        self.analyses.append(analysis)
        print(f"💾 분석 결과 저장: {analysis.stock_code} - {analysis.signal.value}")
    
    async def find_latest_analysis(self, stock_code: str):
        for analysis in reversed(self.analyses):
            if analysis.stock_code == stock_code:
                return analysis
        return None


class MockEventPublisher:
    """테스트용 이벤트 발행자"""
    
    async def publish(self, event):
        print(f"📢 이벤트 발행: {event.__class__.__name__} - {getattr(event, 'stock_code', 'N/A')}")


# UseCase 간소화 버전 (LLM 통합에 집중)
class SimpleAnalyzeStockUseCase:
    """간소화된 주식 분석 유스케이스"""
    
    def __init__(
        self,
        stock_repo,
        market_data_repo,
        news_repo,
        analysis_repo,
        llm_service,
        event_publisher
    ):
        self.stock_repo = stock_repo
        self.market_data_repo = market_data_repo
        self.news_repo = news_repo
        self.analysis_repo = analysis_repo
        self.llm_service = llm_service
        self.event_publisher = event_publisher
    
    async def execute(self, stock_code: str):
        """주식 분석 실행"""
        print(f"\n🔍 주식 분석 시작: {stock_code}")
        
        # 1. 기본 데이터 수집
        stock = await self.stock_repo.find_by_code(stock_code)
        if not stock:
            print(f"❌ 주식 정보를 찾을 수 없음: {stock_code}")
            return
        
        print(f"📈 주식 정보: {stock.name} ({stock.sector})")
        
        # 2. 시장 데이터 및 뉴스 감정 수집 (병렬)
        market_data, sentiment = await asyncio.gather(
            self.market_data_repo.get_current_data(stock_code),
            self.news_repo.get_market_sentiment(stock_code)
        )
        
        if not market_data:
            print("❌ 시장 데이터를 가져올 수 없음")
            return
        
        print(f"💰 현재가: {market_data.current_price:,}원")
        print(f"📊 거래량: {market_data.volume:,}주")
        print(f"🌡️  시장 감정: {sentiment:.2f}")
        
        # 3. LLM을 통한 분석
        print("🤖 LLM 분석 중...")
        
        stock_info = {
            "code": stock.code,
            "name": stock.name,
            "sector": stock.sector
        }
        
        market_info = {
            "current_price": float(market_data.current_price),
            "volume": market_data.volume,
            "market_cap": float(market_data.market_cap) if market_data.market_cap else None
        }
        
        sentiment_info = {"sentiment": sentiment}
        
        # LLM 분석 요청
        llm_result = await self.llm_service.analyze_stock(
            stock_info, market_info, sentiment_info
        )
        
        # 4. 분석 결과 출력
        print("\n" + "="*50)
        print("🎯 LLM 분석 결과")
        print("="*50)
        print(f"📊 투자 신호: {llm_result['signal']}")
        print(f"🔍 신뢰도: {llm_result['confidence']:.1%}")
        
        if llm_result.get('target_price'):
            print(f"🎯 목표가: {llm_result['target_price']:,.0f}원")
        
        print(f"📝 분석 근거: {llm_result['reasoning']}")
        print(f"🔑 핵심 요인:")
        for factor in llm_result['key_factors']:
            print(f"   • {factor}")
        print(f"⚠️  리스크 평가: {llm_result['risk_assessment']}")
        print(f"⏰ 투자 기간: {llm_result['time_horizon']}")
        
        # 5. 분석 결과 엔티티 생성 및 저장
        analysis = AnalysisResult(
            stock_code=stock_code,
            signal=InvestmentSignal(llm_result['signal']),
            confidence=llm_result['confidence'],
            target_price=Decimal(str(llm_result['target_price'])) if llm_result.get('target_price') else None,
            reasoning=llm_result['reasoning'],
            analyzed_at=datetime.now()
        )
        
        await self.analysis_repo.save_analysis(analysis)
        
        # 6. 이벤트 발행 (간소화)
        from simplified_architecture.domain.entities import AnalysisCompleted
        event = AnalysisCompleted(
            occurred_at=datetime.now(),
            event_id=f"analysis_{stock_code}_{int(datetime.now().timestamp())}",
            stock_code=stock_code,
            analysis_result=analysis
        )
        await self.event_publisher.publish(event)
        
        print("="*50)
        print("✅ 분석 완료!")
        
        return analysis


async def demo_llm_integration():
    """LLM 통합 데모"""
    print("🚀 LLM Service 통합 데모\n")
    
    # 의존성 생성
    stock_repo = MockStockRepository()
    market_data_repo = MockMarketDataRepository()
    news_repo = MockNewsRepository()
    analysis_repo = MockAnalysisRepository()
    event_publisher = MockEventPublisher()
    
    # LLM 서비스 생성 (Mock 서비스 사용)
    llm_service = LLMServiceFactory.create_service("mock")
    
    # UseCase 생성
    analyze_usecase = SimpleAnalyzeStockUseCase(
        stock_repo=stock_repo,
        market_data_repo=market_data_repo,
        news_repo=news_repo,
        analysis_repo=analysis_repo,
        llm_service=llm_service,
        event_publisher=event_publisher
    )
    
    # 여러 주식 분석
    test_stocks = ["005930", "000660", "035720"]
    
    for stock_code in test_stocks:
        await analyze_usecase.execute(stock_code)
        await asyncio.sleep(0.5)  # 출력 간격
    
    # 분석 이력 확인
    print(f"\n📚 총 {len(analysis_repo.analyses)}개 분석 완료")
    print("\n분석 요약:")
    for analysis in analysis_repo.analyses:
        print(f"  • {analysis.stock_code}: {analysis.signal.value} (신뢰도: {analysis.confidence:.1%})")


async def demo_llm_service_features():
    """LLM 서비스 기능 데모"""
    print("\n🔧 LLM Service 주요 기능 데모")
    print("="*50)
    
    # 1. 캐시 기능 테스트
    print("\n1. 캐시 기능 테스트")
    llm_service = LLMServiceFactory.create_service("mock")
    
    stock_info = {"code": "005930", "name": "삼성전자", "sector": "반도체"}
    market_data = {"current_price": 75000, "volume": 1000000}
    news_sentiment = {"sentiment": 0.6}
    
    # 첫 번째 요청
    start_time = asyncio.get_event_loop().time()
    result1 = await llm_service.analyze_stock(stock_info, market_data, news_sentiment)
    first_duration = asyncio.get_event_loop().time() - start_time
    
    # 두 번째 요청 (캐시된 결과 - Mock의 경우 호출 횟수 차이로 확인)
    start_time = asyncio.get_event_loop().time()
    result2 = await llm_service.analyze_stock(stock_info, market_data, news_sentiment)
    second_duration = asyncio.get_event_loop().time() - start_time
    
    print(f"   첫 번째 요청: {first_duration*1000:.1f}ms")
    print(f"   두 번째 요청: {second_duration*1000:.1f}ms")
    print(f"   Mock 호출 횟수: {llm_service.call_count}")
    
    # 2. 다양한 시장 상황 테스트
    print("\n2. 다양한 시장 상황 대응")
    
    scenarios = [
        {"sentiment": 0.9, "name": "매우 긍정적"},
        {"sentiment": 0.1, "name": "매우 부정적"},
        {"sentiment": 0.5, "name": "중립적"}
    ]
    
    for scenario in scenarios:
        news_data = {"sentiment": scenario["sentiment"]}
        result = await llm_service.analyze_stock(stock_info, market_data, news_data)
        print(f"   {scenario['name']}: {result['signal']} (신뢰도: {result['confidence']:.1%})")


async def main():
    """메인 실행 함수"""
    try:
        await demo_llm_integration()
        await demo_llm_service_features()
        
        print("\n🎉 모든 데모 완료!")
        
    except Exception as e:
        print(f"\n❌ 데모 실행 중 오류: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())