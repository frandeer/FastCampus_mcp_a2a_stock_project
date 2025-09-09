"""
Step 1: 기본 MCP 서버 - 간단한 계산기
MCP (Model Context Protocol)의 기본 개념을 이해하기 위한 예제

MCP란?
- AI 모델이 외부 도구와 데이터에 접근할 수 있게 해주는 표준 프로토콜
- 간단히 말해서 "AI가 사용할 수 있는 도구 상자"
"""

from typing import Dict, Any
import json
import asyncio
import sys
from pathlib import Path
from fastmcp import FastMCP

# 공통 유틸리티 import
sys.path.append(str(Path(__file__).parent.parent))
from common_utils import get_setting, print_environment_status

# MCP 서버 인스턴스 생성
mcp = FastMCP("SimpleCalculator")

@mcp.tool()
async def add_numbers(a: float, b: float) -> Dict[str, Any]:
    """두 숫자를 더하기"""
    result = a + b
    return {
        "operation": "addition",
        "inputs": {"a": a, "b": b},
        "result": result,
        "message": f"{a} + {b} = {result}"
    }

@mcp.tool()
async def multiply_numbers(a: float, b: float) -> Dict[str, Any]:
    """두 숫자를 곱하기"""
    result = a * b
    return {
        "operation": "multiplication", 
        "inputs": {"a": a, "b": b},
        "result": result,
        "message": f"{a} × {b} = {result}"
    }

@mcp.tool()
async def get_calculator_info() -> Dict[str, Any]:
    """계산기 정보 조회"""
    return {
        "name": "Simple Calculator MCP",
        "version": "1.0.0",
        "available_operations": ["add_numbers", "multiply_numbers"],
        "description": "기본적인 수학 계산을 수행하는 MCP 서버입니다"
    }

# 서버 실행 함수
def run_server():
    """MCP 서버를 .env에서 설정한 포트에서 실행"""
    
    # 환경 설정 출력
    print("🧮 Simple Calculator MCP 서버 시작...")
    print("=" * 50)
    print_environment_status()
    
    # 포트 설정 가져오기
    port = get_setting('LEARNING_MCP_PORT', 9000, int)
    host = get_setting('LEARNING_HOST', 'localhost', str)
    
    print(f"\n🚀 서버 시작 중...")
    print(f"📍 호스트: {host}")
    print(f"📍 포트: {port}")
    print("🔧 사용 가능한 도구:")
    print("  - add_numbers: 덧셈")
    print("  - multiply_numbers: 곱셈")
    print("  - get_calculator_info: 계산기 정보")
    print(f"🌐 서버 URL: http://{host}:{port}/sse")
    print("-" * 50)
    
    # 서버 실행 (설정된 포트) - FastMCP가 내부적으로 async를 처리
    mcp.run(transport="sse", host=host, port=port)

if __name__ == "__main__":
    # 서버 실행 (FastMCP는 자체적으로 async를 처리)
    run_server()