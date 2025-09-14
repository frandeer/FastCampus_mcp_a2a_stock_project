#!/usr/bin/env python3
"""
WebSocket 클라이언트 테스트
브라우저 없이 웹소켓 연결을 테스트해볼 수 있습니다.
"""

import asyncio
import websockets
import json

async def test_websocket():
    """웹소켓 연결 테스트"""
    uri = "ws://localhost:8765"
    
    try:
        print("🔌 웹소켓 서버에 연결 중...")
        async with websockets.connect(uri) as websocket:
            print("✅ 연결 성공!")
            
            # 분석 요청 전송
            request = {
                "type": "request_analysis",
                "symbol": "005930",
                "analysis_type": "technical"
            }
            
            await websocket.send(json.dumps(request))
            print(f"📤 분석 요청 전송: {request}")
            
            # 메시지 수신 (최대 10초)
            print("📥 실시간 메시지 수신 중... (10초간)")
            
            for i in range(20):  # 10초간 0.5초씩
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=0.5)
                    data = json.loads(message)
                    
                    if data['type'] == 'welcome':
                        print(f"🎉 {data['message']}")
                        print(f"📈 모니터링 종목: {', '.join(data['stocks'])}")
                        
                    elif data['type'] == 'stock_update':
                        stock = data['data']
                        print(f"📈 {stock['name']} ({stock['symbol']}): {stock['price']:,.0f}원 ({stock['change_percent']:+.2f}%)")
                        
                    elif data['type'] == 'analysis_update':
                        analysis = data['data']
                        print(f"🧠 {analysis['stock_symbol']} {analysis['analysis_type']} 분석: {analysis['score']:.1f}점")
                        print(f"   💡 {analysis['reasoning']}")
                        
                    elif data['type'] == 'analysis_requested':
                        print(f"📊 분석 요청 접수: {data['symbol']} {data['analysis_type']}")
                        
                    else:
                        print(f"📨 메시지: {data}")
                        
                except asyncio.TimeoutError:
                    continue
                    
            print("⏹️  테스트 완료")
            
    except Exception as e:
        print(f"❌ 연결 실패: {e}")
        print("💡 플랫폼이 실행 중인지 확인하세요:")
        print("   python 4_1_integrated_market_platform_simple.py")

if __name__ == "__main__":
    asyncio.run(test_websocket())