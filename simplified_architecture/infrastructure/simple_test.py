"""
LLM Service 기본 테스트 - 외부 의존성 없이
"""

import asyncio
import json
from typing import Dict, Any


class MockLLMService:
    """테스트용 간단한 목 LLM 서비스"""
    
    def __init__(self):
        self.call_count = 0
        print("✅ Mock LLM Service 초기화 완료")
    
    async def analyze_stock(
        self,
        stock_info: dict,
        market_data: dict,
        news_sentiment: dict
    ) -> dict:
        """모킹된 주식 분석"""
        self.call_count += 1
        
        # 실제 API 호출 시뮬레이션
        await asyncio.sleep(0.1)
        
        stock_code = stock_info.get('code', 'Unknown')
        current_price = market_data.get('current_price', 100)
        sentiment = news_sentiment.get('sentiment', 0.5)
        
        # 간단한 분석 로직
        if sentiment > 0.7:
            signal = "BUY"
            confidence = 0.8
            target_multiplier = 1.1
        elif sentiment < 0.3:
            signal = "SELL" 
            confidence = 0.7
            target_multiplier = 0.9
        else:
            signal = "HOLD"
            confidence = 0.6
            target_multiplier = 1.0
        
        target_price = float(current_price) * target_multiplier if signal != "HOLD" else None
        
        result = {
            'signal': signal,
            'confidence': confidence,
            'target_price': target_price,
            'reasoning': f"분석 #{self.call_count}: 감정 점수 {sentiment:.2f} 기반 분석. " +
                        f"현재가 {current_price:,}원 대비 {'상승' if signal == 'BUY' else '하락' if signal == 'SELL' else '보합'} 전망.",
            'key_factors': [
                f"뉴스 감정 분석: {sentiment:.2f}",
                f"현재 주가: {current_price:,}원",
                f"거래량: {market_data.get('volume', 0):,}주",
                f"분석 신뢰도: {confidence:.1%}"
            ],
            'risk_assessment': f"{'낮음' if confidence > 0.8 else '보통' if confidence > 0.6 else '높음'} - 감정 기반 분석",
            'time_horizon': "중기"
        }
        
        return result


async def test_basic_functionality():
    """기본 기능 테스트"""
    print("🧪 LLM Service 기본 기능 테스트\n")
    
    service = MockLLMService()
    
    # 테스트 데이터
    stock_info = {
        "code": "005930",
        "name": "삼성전자",
        "sector": "반도체"
    }
    
    market_data = {
        "current_price": 75000,
        "volume": 1500000,
        "market_cap": 500000000000
    }
    
    # 다양한 시나리오 테스트
    scenarios = [
        {"sentiment": 0.8, "desc": "📈 긍정적 뉴스"},
        {"sentiment": 0.2, "desc": "📉 부정적 뉴스"}, 
        {"sentiment": 0.5, "desc": "📊 중립적 뉴스"}
    ]
    
    print("=" * 50)
    
    for i, scenario in enumerate(scenarios, 1):
        print(f"\n{i}. {scenario['desc']} 시나리오")
        print("-" * 30)
        
        result = await service.analyze_stock(
            stock_info, 
            market_data, 
            {"sentiment": scenario["sentiment"]}
        )
        
        print(f"🎯 투자 신호: {result['signal']}")
        print(f"🔍 신뢰도: {result['confidence']:.1%}")
        
        if result['target_price']:
            print(f"💰 목표가: {result['target_price']:,.0f}원")
        else:
            print("💰 목표가: 설정 없음")
            
        print(f"📝 분석 근거: {result['reasoning']}")
        print(f"🔑 핵심 요인:")
        for factor in result['key_factors']:
            print(f"   • {factor}")
        print(f"⚠️  리스크: {result['risk_assessment']}")
        print(f"⏰ 투자기간: {result['time_horizon']}")
    
    print("=" * 50)
    print(f"\n✅ 총 {service.call_count}회 분석 완료!")


async def test_protocol_compliance():
    """프로토콜 준수 테스트"""
    print("\n🔍 LLM Service 프로토콜 준수 테스트")
    
    service = MockLLMService()
    
    # 기본 입력
    stock_info = {"code": "000001", "name": "테스트주식", "sector": "테스트"}
    market_data = {"current_price": 50000, "volume": 100000}
    news_sentiment = {"sentiment": 0.6}
    
    result = await service.analyze_stock(stock_info, market_data, news_sentiment)
    
    # 필수 필드 확인
    required_fields = ['signal', 'confidence', 'reasoning', 'key_factors', 'risk_assessment', 'time_horizon']
    
    print("\n필수 응답 필드 확인:")
    for field in required_fields:
        if field in result:
            print(f"  ✅ {field}: {type(result[field]).__name__}")
        else:
            print(f"  ❌ {field}: 누락")
    
    # 데이터 타입 및 값 범위 확인
    print(f"\n데이터 유효성 확인:")
    print(f"  • 신호값 유효성: {'✅' if result['signal'] in ['STRONG_BUY', 'BUY', 'HOLD', 'SELL', 'STRONG_SELL'] else '❌'}")
    print(f"  • 신뢰도 범위: {'✅' if 0.0 <= result['confidence'] <= 1.0 else '❌'}")
    print(f"  • 목표가 양수: {'✅' if result.get('target_price') is None or result['target_price'] > 0 else '❌'}")
    print(f"  • 핵심요인 개수: {'✅' if 1 <= len(result['key_factors']) <= 5 else '❌'}")


async def main():
    """메인 테스트 실행"""
    print("🚀 LLM Service 테스트 시작\n")
    
    try:
        await test_basic_functionality()
        await test_protocol_compliance()
        
        print(f"\n🎉 모든 테스트 성공적으로 완료!")
        
    except Exception as e:
        print(f"\n❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())