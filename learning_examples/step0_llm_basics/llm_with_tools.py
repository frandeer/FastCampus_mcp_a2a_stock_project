"""
Step 0: LLM + 도구 호출 예제
OpenAI의 Function Calling 기능을 사용해서 AI가 도구를 호출하는 방법 학습

이 예제는 MCP의 핵심 아이디어를 보여줍니다:
1. AI가 필요에 따라 도구를 선택하고 호출
2. 도구 실행 결과를 받아서 최종 응답 생성
3. 사용자는 복잡한 요청을 자연어로 하기만 하면 됨

이것이 바로 MCP가 하려는 일입니다!
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Dict, Any, List
from openai import AsyncOpenAI

# 공통 유틸리티 import
sys.path.append(str(Path(__file__).parent.parent))
from common_utils import get_api_key, get_setting, print_environment_status

class CalculatorTools:
    """AI가 사용할 수 있는 계산 도구들"""
    
    @staticmethod
    def add_numbers(a: float, b: float) -> Dict[str, Any]:
        """두 숫자 더하기"""
        result = a + b
        return {
            "operation": "addition",
            "inputs": {"a": a, "b": b},
            "result": result,
            "message": f"{a} + {b} = {result}"
        }
    
    @staticmethod
    def multiply_numbers(a: float, b: float) -> Dict[str, Any]:
        """두 숫자 곱하기"""
        result = a * b
        return {
            "operation": "multiplication", 
            "inputs": {"a": a, "b": b},
            "result": result,
            "message": f"{a} × {b} = {result}"
        }
    
    @staticmethod
    def divide_numbers(a: float, b: float) -> Dict[str, Any]:
        """두 숫자 나누기"""
        if b == 0:
            return {
                "operation": "division",
                "inputs": {"a": a, "b": b},
                "error": "0으로 나눌 수 없습니다",
                "result": None
            }
        result = a / b
        return {
            "operation": "division",
            "inputs": {"a": a, "b": b}, 
            "result": result,
            "message": f"{a} ÷ {b} = {result}"
        }
    
    @staticmethod
    def power_numbers(base: float, exponent: float) -> Dict[str, Any]:
        """거듭제곱 계산"""
        result = base ** exponent
        return {
            "operation": "power",
            "inputs": {"base": base, "exponent": exponent},
            "result": result,
            "message": f"{base}^{exponent} = {result}"
        }

class LLMWithTools:
    def __init__(self, api_key: str = None):
        if api_key is None:
            api_key = get_api_key('OPENAI_API_KEY', required=True)
            if not api_key:
                raise ValueError("OpenAI API 키가 필요합니다. .env 파일을 확인하세요.")
        
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = "gpt-4o-mini"
        self.tools = CalculatorTools()
        
        # OpenAI Function Calling용 도구 정의
        self.tool_definitions = [
            {
                "type": "function",
                "function": {
                    "name": "add_numbers",
                    "description": "두 숫자를 더합니다",
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
                    "description": "두 숫자를 곱합니다",
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
                    "name": "divide_numbers", 
                    "description": "첫 번째 숫자를 두 번째 숫자로 나눕니다",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "a": {"type": "number", "description": "나누어지는 수"},
                            "b": {"type": "number", "description": "나누는 수"}
                        },
                        "required": ["a", "b"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "power_numbers",
                    "description": "첫 번째 숫자를 두 번째 숫자만큼 거듭제곱합니다",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "base": {"type": "number", "description": "밑"},
                            "exponent": {"type": "number", "description": "지수"}
                        },
                        "required": ["base", "exponent"]
                    }
                }
            }
        ]
    
    async def chat_with_tools(self, user_message: str) -> str:
        """도구를 사용할 수 있는 AI 채팅"""
        print(f"👤 사용자: {user_message}")
        print("🤖 AI가 생각하고 필요한 도구를 선택 중...")
        
        messages = [
            {
                "role": "system", 
                "content": "당신은 수학 문제를 해결하는 AI 어시스턴트입니다. 계산이 필요하면 제공된 도구를 사용하세요. 결과를 친절하게 설명해주세요."
            },
            {"role": "user", "content": user_message}
        ]
        
        try:
            # 첫 번째 AI 호출 (도구 사용 여부 결정)
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=self.tool_definitions,
                tool_choice="auto"  # AI가 자동으로 도구 사용 여부 결정
            )
            
            response_message = response.choices[0].message
            
            # 도구 호출이 있는지 확인
            if response_message.tool_calls:
                print(f"🔧 AI가 {len(response_message.tool_calls)}개의 도구를 사용하기로 결정했습니다")
                
                # AI의 응답을 메시지에 추가
                messages.append(response_message)
                
                # 각 도구 호출 실행
                for tool_call in response_message.tool_calls:
                    tool_name = tool_call.function.name
                    tool_args = json.loads(tool_call.function.arguments)
                    
                    print(f"  🛠️  도구 호출: {tool_name}({tool_args})")
                    
                    # 도구 실행
                    if hasattr(self.tools, tool_name):
                        tool_function = getattr(self.tools, tool_name)
                        result = tool_function(**tool_args)
                        print(f"  📊 실행 결과: {result}")
                    else:
                        result = {"error": f"알 수 없는 도구: {tool_name}"}
                    
                    # 도구 실행 결과를 메시지에 추가
                    messages.append({
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": tool_name,
                        "content": json.dumps(result, ensure_ascii=False)
                    })
                
                # 도구 결과를 바탕으로 최종 응답 생성
                print("🤖 AI가 도구 결과를 바탕으로 최종 응답을 생성 중...")
                final_response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=messages
                )
                
                final_answer = final_response.choices[0].message.content
                print(f"💬 AI 최종 응답: {final_answer}")
                return final_answer
                
            else:
                # 도구 사용 없이 직접 응답
                answer = response_message.content
                print(f"💬 AI 응답 (도구 사용 안함): {answer}")
                return answer
                
        except Exception as e:
            error_msg = f"AI 호출 실패: {str(e)}"
            print(f"❌ {error_msg}")
            return error_msg

async def test_llm_with_tools():
    """LLM + 도구 호출 테스트"""
    print("🚀 LLM + 도구 호출 테스트 시작")
    print("=" * 60)
    
    # 환경 설정 상태 출력
    print_environment_status()
    
    # API 키 확인 (이미 위에서 출력됨)
    api_key = get_api_key('OPENAI_API_KEY', required=False)
    if not api_key:
        print("\n💡 .env 파일 설정 방법:")
        print("   1. learning_examples/.env.example을 learning_examples/.env로 복사")
        print("   2. OPENAI_API_KEY=your-key-here 설정")
        return
    
    # LLM + 도구 클라이언트 생성
    llm_tools = LLMWithTools()
    
    # 테스트 케이스들
    test_cases = [
        "25 + 17을 계산해주세요",
        "12 곱하기 8은 얼마인가요?", 
        "144를 12로 나눈 결과를 알려주세요",
        "2의 10제곱은 얼마인가요?",
        "복잡한 계산: (10 + 5) × 3을 해주세요",
        "안녕하세요, 날씨가 어떤가요?",  # 도구 없이 응답해야 하는 케이스
    ]
    
    # 각 테스트 실행
    for i, test_message in enumerate(test_cases, 1):
        print(f"\n📋 테스트 {i}")
        print("=" * 30)
        
        result = await llm_tools.chat_with_tools(test_message)
        
        print("✅ 완료!\n")
        
        # API 호출 지연 (.env에서 설정 가능)
        delay = get_setting('LEARNING_API_DELAY', 1, int)
        await asyncio.sleep(delay)
    
    print("=" * 60)
    print("🎉 LLM + 도구 호출 테스트 완료!")
    print()
    print("🧠 핵심 개념 정리:")
    print("  1. AI가 자연어 요청을 분석해서 필요한 도구를 선택")
    print("  2. 선택한 도구를 적절한 인수로 호출")  
    print("  3. 도구 실행 결과를 받아서 사용자에게 친절하게 설명")
    print("  4. 이것이 바로 MCP가 하려는 일입니다!")

if __name__ == "__main__":
    asyncio.run(test_llm_with_tools())