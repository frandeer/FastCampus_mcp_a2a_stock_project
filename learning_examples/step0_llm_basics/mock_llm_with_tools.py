"""
Step 0: Mock LLM + 도구 호출 예제 (API 키 불필요)
실제 OpenAI API 대신 가짜 AI를 사용해서 MCP 개념을 학습

이 예제는:
1. 실제 API 키 없이도 MCP 개념을 체험
2. AI가 도구를 선택하고 호출하는 과정을 시뮬레이션
3. 실제 MCP 시스템의 흐름을 이해할 수 있게 해줌

실제로는 더 똑똑한 AI가 더 복잡한 도구들을 사용하지만,
기본 아이디어는 완전히 동일합니다!
"""

import asyncio
import json
import re
from typing import Dict, Any, List, Tuple

class CalculatorTools:
    """AI가 사용할 수 있는 계산 도구들 (실제 MCP 서버 역할)"""
    
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

class MockAI:
    """가짜 AI - 실제 OpenAI API 대신 사용"""
    
    def __init__(self):
        self.tools = CalculatorTools()
        
        # 간단한 패턴 매칭으로 도구 선택 (실제 AI는 훨씬 더 똑똑함)
        self.patterns = [
            (r'(\d+(?:\.\d+)?)\s*\+\s*(\d+(?:\.\d+)?)', 'add_numbers', '더하기'),
            (r'(\d+(?:\.\d+)?)\s*(?:×|곱하기|곱|x|\*)\s*(\d+(?:\.\d+)?)', 'multiply_numbers', '곱하기'),
            (r'(\d+(?:\.\d+)?)\s*(?:÷|나누기|나눈|/)\s*(\d+(?:\.\d+)?)', 'divide_numbers', '나누기'),
            (r'(\d+(?:\.\d+)?)\s*(?:의|^)\s*(\d+(?:\.\d+)?)\s*(?:제곱|승)', 'power_numbers', '거듭제곱'),
        ]
    
    def analyze_request(self, message: str) -> Tuple[str, str, List[float]]:
        """사용자 요청을 분석해서 도구와 인수 결정"""
        message = message.replace(' ', '')  # 공백 제거
        
        for pattern, tool_name, description in self.patterns:
            match = re.search(pattern, message)
            if match:
                numbers = [float(match.group(i)) for i in range(1, match.lastindex + 1)]
                return tool_name, description, numbers
        
        return None, None, []
    
    async def chat_with_tools(self, user_message: str) -> str:
        """도구를 사용할 수 있는 Mock AI 채팅"""
        print(f"👤 사용자: {user_message}")
        print("🤖 Mock AI가 요청을 분석 중...")
        
        # 1단계: 요청 분석
        tool_name, description, numbers = self.analyze_request(user_message)
        
        if tool_name and numbers:
            print(f"🔧 AI 결정: '{description}' 작업을 위해 {tool_name} 도구 사용")
            print(f"📝 추출된 숫자: {numbers}")
            
            # 2단계: 도구 호출
            print(f"🛠️  도구 호출 중: {tool_name}({numbers})")
            
            try:
                if hasattr(self.tools, tool_name):
                    tool_function = getattr(self.tools, tool_name)
                    if len(numbers) == 2:
                        if tool_name == 'power_numbers':
                            result = tool_function(base=numbers[0], exponent=numbers[1])
                        else:
                            result = tool_function(numbers[0], numbers[1])
                    else:
                        result = {"error": f"잘못된 인수 개수: {len(numbers)}"}
                    
                    print(f"📊 도구 실행 결과: {result}")
                    
                    # 3단계: 결과 기반 응답 생성
                    if 'error' in result:
                        final_answer = f"죄송합니다. 계산 중 오류가 발생했습니다: {result['error']}"
                    else:
                        final_answer = f"계산 결과를 알려드리겠습니다.\n\n"
                        final_answer += f"📊 {result['message']}\n\n"
                        final_answer += f"✨ 답: **{result['result']}**"
                
                else:
                    final_answer = f"죄송합니다. {tool_name} 도구를 찾을 수 없습니다."
                    
            except Exception as e:
                final_answer = f"도구 실행 중 오류가 발생했습니다: {str(e)}"
        
        else:
            # 계산이 아닌 요청
            print("💬 계산 요청이 아님 - 일반 응답 모드")
            
            if "안녕" in user_message or "hello" in user_message.lower():
                final_answer = "안녕하세요! 저는 계산을 도와주는 AI 어시스턴트입니다. 덧셈, 곱셈, 나눗셈, 거듭제곱을 계산할 수 있어요!"
            elif "도움" in user_message or "help" in user_message.lower():
                final_answer = ("제가 도와드릴 수 있는 계산들:\n"
                              "• 덧셈: '25 + 17' 또는 '25 더하기 17'\n"
                              "• 곱셈: '12 × 8' 또는 '12 곱하기 8'\n"
                              "• 나눗셈: '20 ÷ 4' 또는 '20 나누기 4'\n"
                              "• 거듭제곱: '2의 10제곱' 또는 '2^10'")
            else:
                final_answer = "죄송합니다. 계산 요청을 이해하지 못했습니다. 예: '10 + 5', '3 × 7' 같은 형태로 말씀해 주세요."
        
        print(f"🤖 AI 최종 응답:\n{final_answer}")
        return final_answer

async def test_mock_llm_with_tools():
    """Mock LLM + 도구 호출 테스트"""
    print("🚀 Mock LLM + 도구 호출 테스트 시작")
    print("💡 실제 OpenAI API 없이도 MCP 개념을 체험할 수 있습니다!")
    print("=" * 60)
    
    # Mock AI 생성
    mock_ai = MockAI()
    
    # 테스트 케이스들
    test_cases = [
        "25 + 17을 계산해주세요",
        "12 곱하기 8은 얼마인가요?", 
        "144를 12로 나눈 결과를 알려주세요",
        "2의 10제곱은 얼마인가요?",
        "안녕하세요!",  # 계산이 아닌 케이스
        "도움말을 보여주세요",  # 도구 설명
        "50 × 3은 뭐죠?",
    ]
    
    # 각 테스트 실행
    for i, test_message in enumerate(test_cases, 1):
        print(f"\n📋 테스트 {i}")
        print("=" * 30)
        
        result = await mock_ai.chat_with_tools(test_message)
        
        print("✅ 완료!")
        
        # 0.5초 대기 (실제 API 호출 시뮬레이션)
        await asyncio.sleep(0.5)
    
    print("\n" + "=" * 60)
    print("🎉 Mock LLM + 도구 호출 테스트 완료!")
    print()
    print("🧠 핵심 개념 정리:")
    print("  1. ✨ AI가 자연어 요청을 분석해서 필요한 도구 선택")
    print("  2. 🛠️  선택한 도구를 적절한 인수로 호출")  
    print("  3. 📊 도구 실행 결과를 받아서 사용자에게 친절하게 설명")
    print("  4. 🏗️  이것이 바로 MCP + LangGraph + A2A가 하려는 일!")
    print()
    print("🔄 실제 시스템에서는:")
    print("  • 더 똑똑한 GPT-4o-mini가 패턴 인식")
    print("  • 더 많은 도구들 (주식 데이터, 뉴스, 분석 등)")
    print("  • 도구들이 독립적인 MCP 서버로 분리")
    print("  • A2A로 에이전트들이 협업")
    print("  • LangGraph로 복잡한 워크플로우 관리")

if __name__ == "__main__":
    asyncio.run(test_mock_llm_with_tools())