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
from fastmcp import FastMCP

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
    """MCP 서버를 포트 9000에서 실행"""
    print("🧮 Simple Calculator MCP 서버 시작...")
    print("📍 포트: 9000")
    print("🔧 사용 가능한 도구:")
    print("  - add_numbers: 덧셈")
    print("  - multiply_numbers: 곱셈")
    print("  - get_calculator_info: 계산기 정보")
    print("-" * 50)
    
    # 서버 실행 (포트 9000) - FastMCP가 내부적으로 async를 처리
    mcp.run(transport="sse", host="localhost", port=9000)

if __name__ == "__main__":
    # 서버 실행
    run_server()