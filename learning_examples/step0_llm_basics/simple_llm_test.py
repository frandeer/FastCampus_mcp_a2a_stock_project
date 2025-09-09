"""
Step 0: LLM 기본 연결 테스트
OpenAI GPT-4o-mini와 연결해서 기본 호출이 되는지 확인

이 예제는:
1. OpenAI API를 사용해서 GPT-4o-mini 호출
2. 간단한 질문-응답 테스트
3. 나중에 도구 호출과 연결할 수 있는 기반 구축
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Dict, Any
from openai import AsyncOpenAI

# 공통 유틸리티 import
sys.path.append(str(Path(__file__).parent.parent))
from common_utils import get_api_key, get_setting, print_environment_status

class SimpleLLMClient:
    def __init__(self, api_key: str = None):
        """
        OpenAI 클라이언트 초기화
        
        Args:
            api_key: OpenAI API 키. None이면 .env 파일이나 환경변수에서 가져옴
        """
        if api_key is None:
            api_key = get_api_key('OPENAI_API_KEY', required=True)
            if not api_key:
                raise ValueError(
                    "OpenAI API 키가 필요합니다. "
                    ".env 파일에 OPENAI_API_KEY를 설정하거나 api_key 인수를 전달하세요."
                )
        
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = "gpt-4o-mini"  # GPT-4o-mini 사용
    
    async def simple_chat(self, message: str) -> str:
        """간단한 채팅 호출"""
        try:
            print(f"🤖 AI에게 질문: {message}")
            
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "user", "content": message}
                ],
                max_tokens=500,
                temperature=0.7
            )
            
            answer = response.choices[0].message.content.strip()
            print(f"💬 AI 응답: {answer}")
            return answer
            
        except Exception as e:
            error_msg = f"LLM 호출 실패: {str(e)}"
            print(f"❌ {error_msg}")
            return error_msg
    
    async def chat_with_system_prompt(self, system_prompt: str, user_message: str) -> str:
        """시스템 프롬프트를 포함한 채팅"""
        try:
            print(f"📋 시스템 프롬프트: {system_prompt}")
            print(f"🤖 사용자 질문: {user_message}")
            
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                max_tokens=500,
                temperature=0.7
            )
            
            answer = response.choices[0].message.content.strip()
            print(f"💬 AI 응답: {answer}")
            return answer
            
        except Exception as e:
            error_msg = f"LLM 호출 실패: {str(e)}"
            print(f"❌ {error_msg}")
            return error_msg

async def test_llm_basic():
    """LLM 기본 기능 테스트"""
    print("🚀 LLM 기본 연결 테스트 시작")
    print("=" * 50)
    
    # 환경 설정 상태 출력
    print_environment_status()
    
    # API 키 확인 (이미 위에서 출력됨)
    api_key = get_api_key('OPENAI_API_KEY', required=False)  # 에러 메시지 중복 방지
    if not api_key:
        print("\n💡 .env 파일 설정 방법:")
        print("   1. learning_examples/.env.example을 learning_examples/.env로 복사")
        print("   2. OPENAI_API_KEY=your-key-here 설정")
        return
    
    # LLM 클라이언트 생성
    llm = SimpleLLMClient()
    
    # 테스트 케이스들
    test_cases = [
        {
            "name": "간단한 인사 테스트",
            "type": "simple",
            "message": "안녕하세요! 당신은 누구인가요?"
        },
        {
            "name": "수학 문제 테스트", 
            "type": "simple",
            "message": "15 + 23은 얼마인가요? 계산 과정도 보여주세요."
        },
        {
            "name": "시스템 프롬프트 테스트",
            "type": "system",
            "system_prompt": "당신은 친절한 수학 선생님입니다. 항상 단계별로 설명하고 격려의 말을 해주세요.",
            "user_message": "7 × 8을 계산해주세요."
        }
    ]
    
    # 각 테스트 실행
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n📋 테스트 {i}: {test_case['name']}")
        print("-" * 30)
        
        if test_case['type'] == 'simple':
            result = await llm.simple_chat(test_case['message'])
        elif test_case['type'] == 'system':
            result = await llm.chat_with_system_prompt(
                test_case['system_prompt'], 
                test_case['user_message']
            )
        
        if not result.startswith("LLM 호출 실패"):
            print("✅ 테스트 성공!")
        else:
            print("❌ 테스트 실패!")
            
        print()  # 빈 줄
        
        # API 호출 지연 (.env에서 설정 가능)
        delay = get_setting('LEARNING_API_DELAY', 1, int)
        await asyncio.sleep(delay)
    
    print("=" * 50)
    print("🎉 LLM 기본 테스트 완료!")

if __name__ == "__main__":
    print("💡 사용법:")
    print("1. OpenAI API 키 설정: export OPENAI_API_KEY='your-key'")
    print("2. 실행: python simple_llm_test.py")
    print()
    
    # 테스트 실행
    asyncio.run(test_llm_basic())