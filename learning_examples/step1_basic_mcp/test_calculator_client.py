"""
Step 1: MCP 클라이언트 테스트
MCP 서버에 연결해서 도구를 호출하는 방법을 학습

이 스크립트는:
1. MCP 서버에 연결
2. 사용 가능한 도구 목록 확인  
3. 실제로 계산 도구 호출
4. 결과 출력
"""

import asyncio
import json
from typing import Dict, Any

# MCP 클라이언트를 위한 간단한 HTTP 요청
import aiohttp

class SimpleMCPClient:
    def __init__(self, server_url: str):
        self.server_url = server_url
        
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """MCP 도구 호출"""
        try:
            # FastMCP는 직접 함수를 호출할 수 있는 엔드포인트를 제공합니다
            url = f"{self.server_url.rstrip('/sse')}/{tool_name}"
            
            async with aiohttp.ClientSession() as session:
                # GET 요청으로 매개변수 전달
                async with session.get(
                    url,
                    params=arguments,
                    headers={"Accept": "application/json"}
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        return result
                    else:
                        return {"error": f"HTTP {response.status}: {await response.text()}"}
                        
        except Exception as e:
            return {"error": f"연결 실패: {str(e)}"}

async def test_calculator():
    """계산기 MCP 서버 테스트"""
    print("🧪 MCP 계산기 서버 테스트 시작")
    print("=" * 50)
    
    # MCP 클라이언트 생성 (FastMCP SSE 엔드포인트)
    client = SimpleMCPClient("http://localhost:9000/sse")
    
    # 테스트 케이스들
    test_cases = [
        {
            "name": "덧셈 테스트",
            "tool": "add_numbers",
            "args": {"a": 10, "b": 5}
        },
        {
            "name": "곱셈 테스트", 
            "tool": "multiply_numbers",
            "args": {"a": 7, "b": 8}
        },
        {
            "name": "계산기 정보 조회",
            "tool": "get_calculator_info",
            "args": {}
        }
    ]
    
    # 각 테스트 실행
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n📋 테스트 {i}: {test_case['name']}")
        print(f"🔧 도구: {test_case['tool']}")
        print(f"📝 인수: {test_case['args']}")
        print("-" * 30)
        
        # MCP 도구 호출
        result = await client.call_tool(test_case['tool'], test_case['args'])
        
        # 결과 출력
        print("📤 결과:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
        if "error" not in result:
            print("✅ 성공!")
        else:
            print("❌ 실패!")
            
    print("\n" + "=" * 50)
    print("🎉 MCP 테스트 완료!")

if __name__ == "__main__":
    print("⚠️  주의: MCP 서버가 http://localhost:9000에서 실행 중이어야 합니다!")
    print("💡 서버 실행 방법: python simple_calculator_mcp.py")
    print()
    
    # 테스트 실행
    asyncio.run(test_calculator())