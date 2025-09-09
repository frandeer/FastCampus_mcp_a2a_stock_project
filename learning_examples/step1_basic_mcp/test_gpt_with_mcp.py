"""
Step 1 최종 단계: GPT + MCP 서버 통합
실제 GPT-4o-mini가 실행 중인 MCP 서버의 도구를 사용하는 예제

이것은 Step 0과 Step 1의 완벽한 결합입니다:
- Step 0: GPT가 도구를 선택하고 호출하는 원리
- Step 1: 도구가 별도의 MCP 서버에서 실행

실제 주식 투자 시스템도 이와 동일한 구조입니다!
"""

import asyncio
import json
import sys
from pathlib import Path
from openai import OpenAI

# 공통 유틸리티 import
sys.path.append(str(Path(__file__).parent.parent))
from common_utils import get_api_key, get_setting, print_environment_status

class MCPProxy:
    """MCP 서버를 GPT Function Calling으로 연결하는 프록시"""
    
    def __init__(self):
        """MCP 서버 설정 초기화"""
        self.host = get_setting('LEARNING_HOST', 'localhost', str)
        self.port = get_setting('LEARNING_MCP_PORT', 9000, int)
        self.server_url = f"http://{self.host}:{self.port}"
        
        print(f"🔧 MCP 프록시 초기화: {self.server_url}")
    
    def add_numbers(self, a: float, b: float) -> str:
        """MCP 서버의 add_numbers 도구를 호출 (시뮬레이션)"""
        # 실제로는 MCP 클라이언트로 호출하지만, 여기서는 시뮬레이션
        result = a + b
        response = {
            "operation": "addition",
            "inputs": {"a": a, "b": b},
            "result": result,
            "message": f"{a} + {b} = {result}",
            "server": f"MCP Server ({self.server_url})"
        }
        return json.dumps(response, ensure_ascii=False)
    
    def multiply_numbers(self, a: float, b: float) -> str:
        """MCP 서버의 multiply_numbers 도구를 호출 (시뮬레이션)"""  
        result = a * b
        response = {
            "operation": "multiplication",
            "inputs": {"a": a, "b": b}, 
            "result": result,
            "message": f"{a} × {b} = {result}",
            "server": f"MCP Server ({self.server_url})"
        }
        return json.dumps(response, ensure_ascii=False)
    
    def get_calculator_info(self) -> str:
        """MCP 서버의 정보를 조회 (시뮬레이션)"""
        response = {
            "name": "SimpleCalculator MCP Server",
            "version": "1.0.0", 
            "status": "running",
            "server_url": self.server_url,
            "available_operations": ["add_numbers", "multiply_numbers"],
            "description": "실행 중인 MCP 서버에서 제공하는 계산 도구"
        }
        return json.dumps(response, ensure_ascii=False)

async def gpt_with_mcp_demo():
    """GPT + MCP 서버 통합 데모"""
    
    print("🚀 GPT + MCP 서버 통합 데모")
    print("=" * 50)
    print_environment_status()
    
    # OpenAI 클라이언트 초기화
    api_key = get_api_key('OPENAI_API_KEY', required=True)
    client = OpenAI(api_key=api_key)
    
    # MCP 프록시 초기화
    mcp = MCPProxy()
    
    # GPT Function Calling 도구 정의
    tools = [
        {
            "type": "function",
            "function": {
                "name": "add_numbers",
                "description": "MCP 서버의 덧셈 도구를 사용해서 두 숫자를 더합니다",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "a": {"type": "number", "description": "첫 번째 숫자"},
                        "b": {"type": "number", "description": "두 번째 숫자"}
                    },
                    "required": ["a", "b"]
                }
            }
        },
        {
            "type": "function", 
            "function": {
                "name": "multiply_numbers",
                "description": "MCP 서버의 곱셈 도구를 사용해서 두 숫자를 곱합니다",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "a": {"type": "number", "description": "첫 번째 숫자"},
                        "b": {"type": "number", "description": "두 번째 숫자"}
                    },
                    "required": ["a", "b"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_calculator_info",
                "description": "MCP 서버의 정보와 사용 가능한 계산 도구 목록을 조회합니다",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        }
    ]
    
    # 테스트 시나리오
    test_cases = [
        "MCP 서버에서 25 + 17을 계산해주세요",
        "12 곱하기 8은 얼마인가요? MCP 서버 도구를 사용해서 알려주세요",
        "MCP 서버 정보와 사용 가능한 도구를 알려주세요",
        "복잡한 계산: (10 + 15) × 2를 단계별로 계산해주세요"
    ]
    
    for i, user_message in enumerate(test_cases, 1):
        print(f"\n📋 테스트 {i}: {user_message}")
        print("-" * 60)
        
        messages = [
            {"role": "system", "content": "당신은 MCP(Model Context Protocol) 서버의 도구를 사용할 수 있는 AI 어시스턴트입니다. 사용자의 요청에 따라 적절한 MCP 도구를 선택해서 사용하세요."},
            {"role": "user", "content": user_message}
        ]
        
        print("🤖 GPT가 MCP 도구 선택 중...")
        
        # GPT API 호출
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            tools=tools,
            tool_choice="auto"
        )
        
        assistant_message = response.choices[0].message
        
        # 도구 호출이 있는지 확인
        if assistant_message.tool_calls:
            print(f"🔧 GPT가 {len(assistant_message.tool_calls)}개의 MCP 도구를 사용하기로 결정!")
            
            # 메시지 체인에 도구 호출 추가  
            messages.append({
                "role": "assistant", 
                "content": None,
                "tool_calls": assistant_message.tool_calls
            })
            
            # 각 도구 호출 실행 및 결과 추가
            for tool_call in assistant_message.tool_calls:
                function_name = tool_call.function.name
                arguments = json.loads(tool_call.function.arguments)
                
                print(f"  🛠️  도구 호출: {function_name}({arguments})")
                
                # MCP 프록시를 통해 실제 도구 호출
                if function_name == "add_numbers":
                    result = mcp.add_numbers(arguments["a"], arguments["b"])
                elif function_name == "multiply_numbers":
                    result = mcp.multiply_numbers(arguments["a"], arguments["b"]) 
                elif function_name == "get_calculator_info":
                    result = mcp.get_calculator_info()
                else:
                    result = f"알 수 없는 도구: {function_name}"
                
                print(f"  📊 MCP 서버 결과: {result}")
                
                # 도구 결과를 메시지 체인에 추가
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result
                })
            
            # GPT가 최종 응답 생성
            print("🤖 GPT가 MCP 결과를 바탕으로 최종 응답 생성 중...")
            
            final_response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages
            )
            
            final_message = final_response.choices[0].message.content
            print(f"💬 GPT 최종 응답: {final_message}")
            
        else:
            # 도구 사용 없이 직접 응답
            print("💬 GPT 응답 (도구 사용 안함):", assistant_message.content)
        
        print("✅ 완료!")
        
        # API 호출 간격
        delay = get_setting('LEARNING_API_DELAY', 1, float)
        await asyncio.sleep(delay)
    
    print("\n" + "=" * 60)
    print("🎉 GPT + MCP 서버 통합 데모 완료!")
    print()
    print("🧠 핵심 깨달음:")
    print("  1. 🔗 GPT가 MCP 서버의 도구를 Function Calling으로 호출")
    print("  2. 🛠️  도구는 별도 서버에서 실행 (분산 아키텍처)")
    print("  3. 📊 GPT가 결과를 받아서 자연스럽게 해석")
    print("  4. 🚀 이것이 바로 실제 AI 시스템의 기본 구조!")
    print()
    print("🔄 실제 주식 투자 시스템에서는:")
    print("  - MCP 서버 → 키움증권 API, 뉴스 분석, 웹 검색")
    print("  - GPT → 투자 판단과 전략 수립")
    print("  - LangGraph → 복잡한 투자 워크플로우 관리")
    print("  - A2A → 여러 전문 에이전트들이 협업")

if __name__ == "__main__":
    asyncio.run(gpt_with_mcp_demo())