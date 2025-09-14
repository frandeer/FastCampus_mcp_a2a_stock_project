# Step 1: 기본 MCP 서버 만들기

이 단계에서는 가장 간단한 MCP 서버를 만들어보겠습니다.

## 🎯 학습 목표

- FastMCP 기본 사용법 이해
- 최초 MCP 서버 생성 및 실행
- STDIO 전송 프로토콜 사용
- 간단한 "Hello World" 기능 구현

## 📝 구현할 기능

1. **hello()** - 간단한 인사 기능
2. **get_current_time()** - 현재 시간 반환
3. **add_numbers()** - 두 숫자 더하기

## 🛠️ 실습

### 1. 기본 서버 생성

먼저 가장 간단한 MCP 서버를 만들어보세요:

```python
# basic_server.py
from fastmcp import FastMCP

# MCP 서버 인스턴스 생성
mcp = FastMCP(name="MyFirstServer")

@mcp.tool
def hello(name: str) -> str:
    """간단한 인사 기능"""
    return f"안녕하세요, {name}님!"

if __name__ == "__main__":
    mcp.run()
```

### 2. 시간 기능 추가

현재 시간을 반환하는 기능을 추가해보세요:

```python
# time_server.py
from fastmcp import FastMCP
from datetime import datetime

mcp = FastMCP(name="TimeServer")

@mcp.tool
def get_current_time() -> str:
    """현재 시간을 반환합니다"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

if __name__ == "__main__":
    mcp.run()
```

### 3. 계산기 기능 추가

두 숫자를 더하는 기능을 추가해보세요:

```python
# calculator_server.py
from fastmcp import FastMCP

mcp = FastMCP(name="CalculatorServer")

@mcp.tool
def add_numbers(a: float, b: float) -> float:
    """두 숫자를 더합니다"""
    return a + b

@mcp.tool
def multiply_numbers(a: float, b: float) -> float:
    """두 숫자를 곱합니다"""
    return a * b

if __name__ == "__main__":
    mcp.run()
```

## 🧪 테스트 방법

### 1. 직접 실행
```bash
python basic_server.py
```

### 2. MCP 클라이언트로 테스트
```python
# test_client.py
from fastmcp import Client

async def test_server():
    async with Client() as client:
        # 서버 정보 확인
        result = await client.list_tools()
        print("사용 가능한 도구들:", result)
        
        # hello 도구 사용
        response = await client.call_tool("hello", {"name": "FastMCP"})
        print("응답:", response)

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_server())
```

## 💡 핵심 개념

### 1. FastMCP 인스턴스
```python
mcp = FastMCP(name="ServerName")
```
- MCP 서버의 기본 인스턴스
- `name`: 서버의 이름 (클라이언트에서 식별용)

### 2. @mcp.tool 데코레이터
```python
@mcp.tool
def function_name(param: type) -> return_type:
    """함수 설명"""
    return result
```
- 일반 Python 함수를 MCP 도구로 변환
- 타입 힌트 필수 (MCP 스키마 생성용)
- 독스트링이 도구 설명으로 사용됨

### 3. 서버 실행
```python
if __name__ == "__main__":
    mcp.run()
```
- STDIO 전송으로 서버 실행
- 클라이언트가 연결할 때까지 대기

## 🚨 주의사항

1. **타입 힌트 필수**: 모든 파라미터와 반환값에 타입 힌트 필요
2. **독스트링 권장**: 함수 설명을 위해 독스트링 작성
3. **실행 블록**: `if __name__ == "__main__":` 블록 사용

## 🎯 연습 문제

1. 문자열 길이를 반환하는 `get_string_length()` 함수 추가
2. 리스트의 최대값을 찾는 `find_max()` 함수 추가
3. 간단한 문자열 역순 함수 `reverse_string()` 추가

다음 단계: [Step 2: 도구 추가하기](../step2_tools/README.md)