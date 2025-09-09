"""
Step 1: MCP 클라이언트로 실제 서버 호출하기
실행 중인 SimpleCalculator MCP 서버에 연결해서 계산 도구 사용해보기

이 예제는:
1. 실행 중인 MCP 서버에 연결
2. 사용 가능한 도구 목록 조회
3. 실제로 도구 호출해서 계산
4. 결과를 자연스럽게 해석
"""

import asyncio
import sys
from pathlib import Path

# 공통 유틸리티 import
sys.path.append(str(Path(__file__).parent.parent))
from common_utils import get_setting, print_environment_status

try:
    from fastmcp.client import Client
except ImportError:
    print("❌ FastMCP 클라이언트가 설치되지 않았습니다.")
    print("💡 설치: pip install fastmcp")
    sys.exit(1)

async def test_mcp_client():
    """MCP 클라이언트로 서버 테스트"""
    
    print("🔗 MCP 클라이언트 테스트 시작")
    print("=" * 50)
    print_environment_status()
    
    # MCP 서버 설정
    host = get_setting('LEARNING_HOST', 'localhost', str)
    port = get_setting('LEARNING_MCP_PORT', 9000, int)
    server_url = f"http://{host}:{port}/sse"
    
    print(f"\n🌐 MCP 서버 연결 중: {server_url}")
    
    try:
        # MCP 클라이언트 생성 및 연결
        client = Client("sse", server_url)
        
        print("🔌 서버 연결 중...")
        await client.connect()
        print("✅ MCP 서버 연결 성공!")
        
        # 1. 사용 가능한 도구 목록 조회
        print("\n📋 사용 가능한 도구 목록:")
        print("-" * 30)
        
        tools = await client.list_tools()
        for i, tool in enumerate(tools.tools, 1):
            print(f"  {i}. {tool.name}")
            print(f"     📝 설명: {tool.description}")
            if hasattr(tool, 'inputSchema') and tool.inputSchema:
                if 'properties' in tool.inputSchema:
                    params = list(tool.inputSchema['properties'].keys())
                    print(f"     🔧 파라미터: {', '.join(params)}")
            print()
        
        # 2. 계산 도구들 실제로 사용해보기
        print("🧮 계산 도구 테스트")
        print("=" * 30)
        
        # 덧셈 테스트
        print("📊 테스트 1: 25 + 17")
        result = await client.call_tool("add_numbers", {"a": 25, "b": 17})
        print(f"   결과: {result.content[0].text}")
        
        # 곱셈 테스트  
        print("\n📊 테스트 2: 12 × 8")
        result = await client.call_tool("multiply_numbers", {"a": 12, "b": 8})
        print(f"   결과: {result.content[0].text}")
        
        # 서버 정보 조회
        print("\n📊 테스트 3: 계산기 정보")
        result = await client.call_tool("get_calculator_info", {})
        print(f"   결과: {result.content[0].text}")
        
        print("\n✅ 모든 테스트 완료!")
        print("\n" + "=" * 50)
        print("🎉 MCP 클라이언트 테스트 성공!")
        print()
        print("🧠 핵심 깨달음:")
        print("  1. 🔗 MCP 클라이언트가 서버에 연결")
        print("  2. 📋 사용 가능한 도구 목록을 자동으로 발견") 
        print("  3. 🛠️  도구를 표준화된 방식으로 호출")
        print("  4. 📊 구조화된 결과를 받아서 처리")
        print("  5. 🤖 이것이 바로 AI가 도구를 사용하는 방식!")
        
    except Exception as e:
        print(f"❌ MCP 서버 연결 실패: {e}")
        print()
        print("💡 해결 방법:")
        print("  1. MCP 서버가 실행 중인지 확인:")
        print(f"     python learning_examples/step1_basic_mcp/simple_calculator_mcp.py")
        print("  2. 포트가 열려있는지 확인:")
        print(f"     lsof -i :{port}")
        print("  3. 방화벽 설정 확인")
        
    finally:
        try:
            await client.close()
            print("\n🔌 MCP 클라이언트 연결 종료")
        except:
            pass

if __name__ == "__main__":
    asyncio.run(test_mcp_client())