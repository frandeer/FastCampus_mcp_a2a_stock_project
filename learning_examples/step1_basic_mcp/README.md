# Step 1: 기본 MCP 서버 학습

## 🎯 학습 목표
MCP (Model Context Protocol)의 기본 개념을 이해하고 간단한 MCP 서버를 만들어봅니다.

## 📚 MCP란?
- **M**odel **C**ontext **P**rotocol
- AI 모델이 외부 도구와 데이터에 접근할 수 있게 해주는 표준 프로토콜
- 쉽게 말해서 "AI가 사용할 수 있는 도구 상자"

## 🏃 실행 방법

### 1단계: MCP 서버 실행
```bash
cd learning_examples/step1_basic_mcp
python simple_calculator_mcp.py
```

서버가 성공적으로 시작되면 다음과 같은 메시지가 표시됩니다:
```
🧮 Simple Calculator MCP 서버 시작...
📍 포트: 9000
🔧 사용 가능한 도구:
  - add_numbers: 덧셈
  - multiply_numbers: 곱셈  
  - get_calculator_info: 계산기 정보
```

### 2단계: 클라이언트 테스트 (새 터미널에서)
```bash
python test_calculator_client.py
```

## 📖 코드 이해하기

### MCP 서버 (`simple_calculator_mcp.py`)
```python
from fastmcp import FastMCP

# MCP 서버 생성
mcp = FastMCP("SimpleCalculator")

# 도구 정의
@mcp.tool()
async def add_numbers(a: float, b: float) -> Dict[str, Any]:
    # 덧셈 로직
    pass
```

### 주요 개념
1. **@mcp.tool()**: 함수를 MCP 도구로 등록
2. **FastMCP**: MCP 서버를 쉽게 만들 수 있는 라이브러리
3. **비동기 처리**: `async/await`로 성능 최적화

## 🔍 확인해볼 점들
- 서버가 포트 9000에서 정상 실행되는지
- 클라이언트가 서버와 성공적으로 통신하는지
- 각 도구가 예상한 결과를 반환하는지

## 🚀 다음 단계
Step 2에서는 LangGraph를 배워보겠습니다!