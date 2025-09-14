# Step 2: 고급 도구와 기능 추가

이 단계에서는 더 복잡하고 실용적인 MCP 서버 기능들을 구현해보겠습니다.

## 🎯 학습 목표

- 리소스(Resources) 제공 기능 구현
- HTTP 전송 프로토콜 사용
- 파일 시스템 작업 도구
- 데이터 변환 및 처리 도구
- 에러 처리 및 로깅

## 📝 구현할 기능

### 1. 파일 관리 서버 (file_manager_server.py)
- 파일 읽기/쓰기
- 디렉토리 목록 조회
- 파일 정보 확인
- 파일 검색

### 2. 데이터 변환 서버 (data_converter_server.py)
- JSON ↔ CSV 변환
- 텍스트 인코딩 변환
- 데이터 포맷팅

### 3. HTTP 서버 예제 (http_server.py)
- 웹 브라우저에서 접근 가능
- REST API 형태로 도구 제공
- 여러 클라이언트 동시 지원

### 4. 리소스 제공 서버 (resource_server.py)
- 정적 리소스 제공 (템플릿, 스키마 등)
- 동적 리소스 생성
- 리소스 템플릿 활용

## 🛠️ 핵심 개념

### Resources vs Tools
- **Tools**: 클라이언트가 호출하는 함수
- **Resources**: 서버가 제공하는 데이터 (파일, 템플릿, 스키마 등)

### HTTP Transport
```python
if __name__ == "__main__":
    mcp.run(transport="http", host="127.0.0.1", port=8000)
```

### Resource 제공
```python
@mcp.resource("config://settings")
def get_settings() -> str:
    return json.dumps({"version": "1.0", "debug": True})
```

### 고급 도구 기능
```python
@mcp.tool
def process_file(file_path: str, operation: str) -> dict:
    \"\"\"파일을 처리하고 결과를 반환합니다\"\"\"
    try:
        # 파일 처리 로직
        return {"status": "success", "result": result}
    except Exception as e:
        return {"status": "error", "message": str(e)}
```

## 🧪 테스트 방법

### 1. STDIO 모드 테스트
```bash
python file_manager_server.py
```

### 2. HTTP 모드 테스트
```bash
python http_server.py
# 브라우저에서 http://localhost:8000/mcp/ 접속
```

### 3. 클라이언트로 테스트
```python
# HTTP 클라이언트 테스트
from fastmcp import Client
from fastmcp.client.transports import HttpTransport

async with Client(transport=HttpTransport("http://localhost:8000/mcp")) as client:
    result = await client.call_tool("list_files", {"directory": "."})
    print(result)
```

## 💡 실전 활용 예제

### Claude Desktop 연동
```json
{
  "mcpServers": {
    "file-manager": {
      "command": "python",
      "args": ["file_manager_server.py"]
    }
  }
}
```

### API 서버로 배포
```bash
# HTTP 모드로 실행
python http_server.py
# 다른 애플리케이션에서 http://localhost:8000/mcp 로 접근
```

다음 단계: [Step 3: 리소스 관리](../step3_resources/README.md)