"""
Step 1: 계산기 MCP 서버
기본적인 수학 계산 기능을 제공하는 MCP 서버
"""

from fastmcp import FastMCP
import math
from typing import List

# MCP 서버 인스턴스 생성
mcp = FastMCP(name="CalculatorServer", version="1.0.0")


@mcp.tool
def add_numbers(a: float, b: float) -> float:
    """두 숫자를 더합니다"""
    return a + b


@mcp.tool
def subtract_numbers(a: float, b: float) -> float:
    """첫 번째 숫자에서 두 번째 숫자를 뺍니다"""
    return a - b


@mcp.tool
def multiply_numbers(a: float, b: float) -> float:
    """두 숫자를 곱합니다"""
    return a * b


@mcp.tool
def divide_numbers(a: float, b: float) -> str:
    """첫 번째 숫자를 두 번째 숫자로 나눕니다"""
    if b == 0:
        return "오류: 0으로 나눌 수 없습니다!"
    return str(a / b)


@mcp.tool
def power(base: float, exponent: float) -> float:
    """거듭제곱을 계산합니다 (base^exponent)"""
    return pow(base, exponent)


@mcp.tool
def square_root(number: float) -> str:
    """제곱근을 계산합니다"""
    if number < 0:
        return "오류: 음수의 제곱근은 계산할 수 없습니다!"
    return str(math.sqrt(number))


@mcp.tool
def sum_list(numbers: List[float]) -> float:
    """숫자 리스트의 합계를 계산합니다"""
    return sum(numbers)


@mcp.tool
def average_list(numbers: List[float]) -> str:
    """숫자 리스트의 평균을 계산합니다"""
    if not numbers:
        return "오류: 빈 리스트의 평균은 계산할 수 없습니다!"
    return str(sum(numbers) / len(numbers))


@mcp.tool
def factorial(n: int) -> str:
    """팩토리얼을 계산합니다 (n!)"""
    if n < 0:
        return "오류: 음수의 팩토리얼은 정의되지 않습니다!"
    return str(math.factorial(n))


if __name__ == "__main__":
    print("🧮 계산기 MCP 서버가 시작됩니다...")
    print("사용 가능한 도구: add_numbers, subtract_numbers, multiply_numbers, divide_numbers,")
    print("               power, square_root, sum_list, average_list, factorial")
    mcp.run()