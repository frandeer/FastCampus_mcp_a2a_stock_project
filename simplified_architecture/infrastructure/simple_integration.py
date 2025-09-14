"""
LLM Service 간단한 통합 예제 - 외부 의존성 없이
"""

import asyncio
import json
from decimal import Decimal
from datetime import datetime
from typing import Dict, Any


# 간단한 Mock LLM Service
class SimpleMockLLMService:
    """간단한 Mock LLM 서비스"""
    
    def __init__(self):
        self.call_count = 0
        print("✅ LLM 서비스 초기화 완료")
    
    async def analyze_stock(
        self,
        stock_info: dict,
        market_data: dict,
        news_sentiment: dict
    ) -> dict:
        """주식 분석"""
        self.call_count += 1
        await asyncio.sleep(0.1)  # API 호출 시뮬레이션
        
        sentiment = news_sentiment.get('sentiment', 0.5)
        current_price = market_data.get('current_price', 0)
        
        # 감정 기반 분석 로직
        if sentiment >= 0.7:
            signal = "BUY"
            confidence = 0.8
            target_multiplier = 1.15
        elif sentiment <= 0.3:
            signal = "SELL"
            confidence = 0.75
            target_multiplier = 0.85
        else:
            signal = "HOLD"
            confidence = 0.6
            target_multiplier = 1.0
        
        target_price = current_price * target_multiplier if signal != "HOLD" else None
        
        return {
            'signal': signal,
            'confidence': confidence,
            'target_price': target_price,
            'reasoning': f"감정 분석 {sentiment:.2f} 기반. {stock_info['name']}의 "
                        f"{'긍정적' if sentiment > 0.6 else '부정적' if sentiment < 0.4 else '중립적'} "
                        f"시장 전망으로 {signal} 권장.",
            'key_factors': [
                f"뉴스 감정 점수: {sentiment:.2f}",
                f"현재가: {current_price:,}원",
                f"섹터: {stock_info.get('sector', 'Unknown')}",
                f"거래량: {market_data.get('volume', 0):,}주"
            ],
            'risk_assessment': f"{'낮음' if confidence > 0.75 else '보통' if confidence > 0.6 else '높음'}",
            'time_horizon': "중기"
        }


# Domain Entities (간소화)
class Stock:
    def __init__(self, code: str, name: str, market: str, sector: str = None):
        self.code = code
        self.name = name
        self.market = market
        self.sector = sector


class MarketData:
    def __init__(self, stock_code: str, current_price: Decimal, volume: int, 
                 market_cap: Decimal = None, timestamp: datetime = None):
        self.stock_code = stock_code
        self.current_price = current_price
        self.volume = volume
        self.market_cap = market_cap
        self.timestamp = timestamp or datetime.now()


class InvestmentSignal:
    def __init__(self, value: str):
        self.value = value


class AnalysisResult:
    def __init__(self, stock_code: str, signal: InvestmentSignal, confidence: float,
                 target_price: Decimal = None, reasoning: str = "", analyzed_at: datetime = None):
        self.stock_code = stock_code
        self.signal = signal
        self.confidence = confidence
        self.target_price = target_price
        self.reasoning = reasoning
        self.analyzed_at = analyzed_at or datetime.now()


# Mock Repositories
class MockStockRepository:
    def __init__(self):
        self.stocks = {
            "005930": Stock("005930", "삼성전자", "KOSPI", "반도체"),
            "000660": Stock("000660", "SK하이닉스", "KOSPI", "반도체"),
            "035720": Stock("035720", "카카오", "KOSPI", "인터넷"),
            "005380": Stock("005380", "현대차", "KOSPI", "자동차"),
            "207940": Stock("207940", "삼성바이오로직스", "KOSPI", "바이오")
        }
    
    async def find_by_code(self, stock_code: str):
        return self.stocks.get(stock_code)


class MockMarketDataRepository:
    def __init__(self):
        self.market_data = {
            "005930": MarketData("005930", Decimal("75000"), 1500000, Decimal("500000000000")),
            "000660": MarketData("000660", Decimal("120000"), 800000, Decimal("90000000000")),
            "035720": MarketData("035720", Decimal("95000"), 1200000, Decimal("40000000000")),
            "005380": MarketData("005380", Decimal("200000"), 600000, Decimal("120000000000")),
            "207940": MarketData("207940", Decimal("850000"), 100000, Decimal("70000000000"))
        }
    
    async def get_current_data(self, stock_code: str):
        return self.market_data.get(stock_code)


class MockNewsRepository:
    def __init__(self):
        self.sentiments = {
            "005930": 0.8,  # 매우 긍정적
            "000660": 0.2,  # 매우 부정적
            "035720": 0.5,  # 중립
            "005380": 0.7,  # 긍정적
            "207940": 0.3   # 부정적
        }
    
    async def get_market_sentiment(self, stock_code: str):
        return self.sentiments.get(stock_code, 0.5)


class MockAnalysisRepository:
    def __init__(self):
        self.analyses = []
    
    async def save_analysis(self, analysis: AnalysisResult):
        self.analyses.append(analysis)
    
    async def find_latest_analysis(self, stock_code: str):
        for analysis in reversed(self.analyses):
            if analysis.stock_code == stock_code:
                return analysis
        return None


class MockEventPublisher:
    async def publish(self, event):
        print(f"📢 이벤트 발행: {type(event).__name__}")


# Simplified Use Case
class AnalyzeStockUseCase:
    """주식 분석 유스케이스"""
    
    def __init__(self, stock_repo, market_data_repo, news_repo, 
                 analysis_repo, llm_service, event_publisher):
        self.stock_repo = stock_repo
        self.market_data_repo = market_data_repo
        self.news_repo = news_repo
        self.analysis_repo = analysis_repo
        self.llm_service = llm_service
        self.event_publisher = event_publisher
    
    async def execute(self, stock_code: str):
        """주식 분석 실행"""
        print(f"\n{'='*60}")
        print(f"📊 주식 분석 시작: {stock_code}")
        print('='*60)
        
        # 1. 기본 데이터 수집
        stock = await self.stock_repo.find_by_code(stock_code)
        if not stock:
            print(f"❌ 주식 정보를 찾을 수 없음: {stock_code}")
            return None
        
        print(f"🏢 종목명: {stock.name}")
        print(f"🏭 섹터: {stock.sector}")
        print(f"📈 시장: {stock.market}")
        
        # 2. 시장 데이터 수집
        market_data = await self.market_data_repo.get_current_data(stock_code)
        if not market_data:
            print("❌ 시장 데이터를 가져올 수 없음")
            return None
        
        print(f"💰 현재가: {market_data.current_price:,}원")
        print(f"📊 거래량: {market_data.volume:,}주")
        
        if market_data.market_cap:
            print(f"🏛️ 시가총액: {market_data.market_cap:,}원")
        
        # 3. 뉴스 감정 분석
        sentiment = await self.news_repo.get_market_sentiment(stock_code)
        sentiment_desc = "매우 긍정적" if sentiment >= 0.8 else \
                        "긍정적" if sentiment >= 0.6 else \
                        "중립적" if sentiment >= 0.4 else \
                        "부정적" if sentiment >= 0.2 else "매우 부정적"
        
        print(f"🌡️ 시장 감정: {sentiment:.2f} ({sentiment_desc})")
        
        # 4. LLM 분석
        print(f"\n🤖 AI 분석 중...")
        
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
        
        llm_result = await self.llm_service.analyze_stock(
            stock_info, market_info, sentiment_info
        )
        
        # 5. 분석 결과 출력
        print(f"\n🎯 AI 분석 결과:")
        print(f"   📊 투자 신호: {llm_result['signal']}")
        print(f"   🔍 신뢰도: {llm_result['confidence']:.1%}")
        
        if llm_result.get('target_price'):
            current = float(market_data.current_price)
            target = llm_result['target_price']
            change = (target - current) / current * 100
            print(f"   🎯 목표가: {target:,.0f}원 ({change:+.1f}%)")
        
        print(f"   📝 분석 근거: {llm_result['reasoning']}")
        print(f"   🔑 핵심 요인:")
        for factor in llm_result['key_factors']:
            print(f"      • {factor}")
        print(f"   ⚠️ 리스크: {llm_result['risk_assessment']}")
        print(f"   ⏰ 투자기간: {llm_result['time_horizon']}")
        
        # 6. 분석 결과 저장
        analysis = AnalysisResult(
            stock_code=stock_code,
            signal=InvestmentSignal(llm_result['signal']),
            confidence=llm_result['confidence'],
            target_price=Decimal(str(llm_result['target_price'])) if llm_result.get('target_price') else None,
            reasoning=llm_result['reasoning']
        )
        
        await self.analysis_repo.save_analysis(analysis)
        
        # 7. 이벤트 발행
        class AnalysisCompleted:
            def __init__(self, stock_code):
                self.stock_code = stock_code
        
        await self.event_publisher.publish(AnalysisCompleted(stock_code))
        
        print(f"✅ 분석 완료 및 저장됨")
        return analysis


async def demo_comprehensive_analysis():
    """종합 분석 데모"""
    print("🚀 LLM 기반 주식 분석 시스템 데모")
    print("=" * 60)
    
    # 의존성 주입
    stock_repo = MockStockRepository()
    market_data_repo = MockMarketDataRepository()
    news_repo = MockNewsRepository()
    analysis_repo = MockAnalysisRepository()
    event_publisher = MockEventPublisher()
    llm_service = SimpleMockLLMService()
    
    # 유스케이스 생성
    analyze_usecase = AnalyzeStockUseCase(
        stock_repo, market_data_repo, news_repo,
        analysis_repo, llm_service, event_publisher
    )
    
    # 다양한 주식 분석
    test_stocks = ["005930", "000660", "035720", "005380", "207940"]
    results = []
    
    for stock_code in test_stocks:
        result = await analyze_usecase.execute(stock_code)
        if result:
            results.append(result)
        await asyncio.sleep(0.3)  # 출력 간격
    
    # 종합 결과 요약
    print(f"\n{'='*60}")
    print(f"📈 분석 결과 종합 요약")
    print('='*60)
    
    signals = {}
    for result in results:
        signal = result.signal.value
        signals[signal] = signals.get(signal, 0) + 1
    
    print(f"📊 총 {len(results)}개 주식 분석 완료:")
    for signal, count in signals.items():
        print(f"   {signal}: {count}개")
    
    print(f"\n🤖 LLM 호출 횟수: {llm_service.call_count}")
    
    # 상위 추천 종목
    buy_stocks = [r for r in results if r.signal.value in ["STRONG_BUY", "BUY"]]
    if buy_stocks:
        buy_stocks.sort(key=lambda x: x.confidence, reverse=True)
        print(f"\n🎯 추천 종목 (신뢰도 순):")
        for stock in buy_stocks[:3]:
            print(f"   {stock.stock_code}: {stock.signal.value} (신뢰도: {stock.confidence:.1%})")
    
    print(f"\n✅ 데모 완료!")


async def main():
    try:
        await demo_comprehensive_analysis()
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())