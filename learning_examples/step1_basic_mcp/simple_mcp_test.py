"""
Step 1: 간단한 MCP 서버 테스트
HTTP 요청으로 MCP 서버의 SSE 엔드포인트 테스트

이 예제는:
1. 실행 중인 MCP 서버 상태 확인
2. HTTP로 기본 정보 조회  
3. MCP 프로토콜의 실제 동작 이해
"""

import requests
import json
import sys
from pathlib import Path

# 공통 유틸리티 import  
sys.path.append(str(Path(__file__).parent.parent))
from common_utils import get_setting, print_environment_status

def test_mcp_server_simple():
    """간단한 MCP 서버 테스트"""
    
    print("🔗 MCP 서버 간단 테스트")
    print("=" * 50)
    print_environment_status()
    
    # MCP 서버 설정
    host = get_setting('LEARNING_HOST', 'localhost', str) 
    port = get_setting('LEARNING_MCP_PORT', 9000, int)
    
    # 기본 연결 테스트
    print(f"\n🌐 MCP 서버 연결 테스트: http://{host}:{port}")
    
    try:
        # 1. 서버 기본 상태 확인
        response = requests.get(f"http://{host}:{port}", timeout=3)
        print(f"✅ 서버 응답: {response.status_code}")
        
        if response.status_code == 200:
            print("🎉 MCP 서버가 정상적으로 실행 중입니다!")
        else:
            print(f"⚠️ 서버 응답 코드: {response.status_code}")
            
    except requests.exceptions.ConnectionError:
        print("❌ MCP 서버에 연결할 수 없습니다")
        print()
        print("💡 해결 방법:")
        print("  1. 다른 터미널에서 MCP 서버 실행:")
        print("     python learning_examples/step1_basic_mcp/simple_calculator_mcp.py")
        print("  2. 서버가 실행되면 이 스크립트를 다시 실행하세요")
        return False
        
    except Exception as e:
        print(f"❌ 연결 오류: {e}")
        return False
    
    # 2. SSE 엔드포인트 확인
    print(f"\n🔌 SSE 엔드포인트 테스트: http://{host}:{port}/sse")
    
    try:
        response = requests.get(f"http://{host}:{port}/sse", timeout=3)
        print(f"✅ SSE 엔드포인트 응답: {response.status_code}")
        
        if response.status_code == 200:
            print("🎉 MCP SSE 엔드포인트가 정상 작동합니다!")
        
    except Exception as e:
        print(f"⚠️ SSE 엔드포인트 테스트 실패: {e}")
    
    print("\n" + "=" * 50)
    print("🧠 MCP 서버 이해하기:")
    print("  1. 🖥️  MCP 서버는 SSE(Server-Sent Events) 프로토콜 사용")
    print("  2. 🔗 일반 HTTP GET/POST와는 다른 실시간 통신 방식")
    print("  3. 🤖 AI 클라이언트가 이 프로토콜로 도구를 호출")
    print("  4. 📊 구조화된 JSON 메시지로 도구 정보와 결과 전달")
    print()
    print("🎯 다음 단계:")
    print("  - Step 2에서 LangGraph가 이 MCP 서버를 활용")  
    print("  - AI 에이전트가 자동으로 계산 도구를 발견하고 사용")
    print("  - 복잡한 워크플로우에서 여러 도구를 조합해서 사용")
    
    return True

def show_mcp_concept():
    """MCP 개념 시각적 설명"""
    
    print("\n🎓 MCP 동작 원리 (실제 상황)")
    print("=" * 50)
    
    print("""
🔄 MCP 통신 흐름:

1. 🤖 AI 에이전트: "계산이 필요해!"
      ↓
2. 🔍 MCP 클라이언트: "사용 가능한 도구 조회"
      ↓ 
3. 📡 MCP 서버: "add_numbers, multiply_numbers 있어요"
      ↓
4. 🧠 AI: "25 + 17 계산하려면 add_numbers 호출!"
      ↓
5. 🛠️  MCP 서버: add_numbers(25, 17) 실행
      ↓
6. 📊 결과: {"result": 42, "message": "25 + 17 = 42"}
      ↓
7. 🤖 AI: "계산 결과는 42입니다!"

💡 핵심: AI가 도구를 자동으로 발견하고 상황에 맞게 선택!
    """)

if __name__ == "__main__":
    success = test_mcp_server_simple()
    if success:
        show_mcp_concept()