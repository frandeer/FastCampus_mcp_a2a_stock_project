# Step 4: 고급 기능과 실전 활용

이 단계에서는 실제 프로덕션에서 사용할 수 있는 고급 MCP 서버 기능들을 구현해보겠습니다.

## 🎯 학습 목표

- 인증과 보안 구현
- 로깅과 모니터링
- 에러 처리와 복구
- 성능 최적화
- 실제 배포 준비

## 📝 구현할 고급 기능

### 1. 보안과 인증 (secure_server.py)
```python
# Bearer Token 인증
from fastmcp.server.auth import require_auth

@mcp.tool
@require_auth
def secure_operation(data: str) -> dict:
    return {"result": "인증된 사용자만 접근 가능"}
```

### 2. 로깅과 모니터링 (logging_server.py)
```python
import structlog

logger = structlog.get_logger()

@mcp.tool
def monitored_operation(data: str) -> dict:
    logger.info("작업 시작", data=data)
    # 작업 수행
    logger.info("작업 완료")
    return result
```

### 3. 데이터베이스 연동 (database_server.py)
```python
@mcp.tool
def query_database(sql: str) -> dict:
    # 안전한 SQL 쿼리 실행
    return {"rows": result}
```

### 4. 비동기 작업 처리 (async_server.py)
```python
@mcp.tool
async def async_operation(data: str) -> dict:
    # 비동기 작업 처리
    result = await long_running_task(data)
    return {"result": result}
```

### 5. 캐싱과 성능 최적화 (cache_server.py)
```python
from functools import lru_cache

@mcp.tool
@lru_cache(maxsize=128)
def cached_operation(key: str) -> dict:
    # 캐시된 결과 반환
    return expensive_computation(key)
```

## 🏗️ 실전 프로젝트 예제

### AI Assistant MCP Server
실제 AI 어시스턴트에서 사용할 수 있는 통합 MCP 서버:

- **파일 관리**: 문서 읽기/쓰기, 검색
- **데이터 처리**: CSV/JSON 변환, 분석
- **웹 스크래핑**: 안전한 웹 데이터 수집
- **API 연동**: 외부 서비스 호출
- **리포트 생성**: 자동 보고서 작성

### Claude Desktop 연동
```json
{
  "mcpServers": {
    "my-assistant": {
      "command": "python",
      "args": ["advanced_assistant_server.py"],
      "env": {
        "API_KEY": "your-api-key"
      }
    }
  }
}
```

## 🚀 배포와 운영

### 1. Docker 컨테이너화
```dockerfile
FROM python:3.12-slim
COPY . /app
WORKDIR /app
RUN pip install fastmcp
CMD ["python", "server.py"]
```

### 2. 환경 변수 관리
```python
import os
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("API_KEY")
```

### 3. 헬스 체크
```python
@mcp.tool
def health_check() -> dict:
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "uptime": get_uptime()
    }
```

### 4. 메트릭스 수집
```python
from prometheus_client import Counter, Histogram

request_count = Counter('mcp_requests_total', 'Total requests')
request_duration = Histogram('mcp_request_duration_seconds', 'Request duration')
```

## 💡 Best Practices

### 1. 에러 처리
```python
@mcp.tool
def robust_operation(data: str) -> dict:
    try:
        result = process_data(data)
        return {"status": "success", "data": result}
    except ValueError as e:
        logger.warning("입력 데이터 오류", error=str(e))
        return {"status": "error", "message": "잘못된 입력"}
    except Exception as e:
        logger.error("예상치 못한 오류", error=str(e))
        return {"status": "error", "message": "내부 서버 오류"}
```

### 2. 입력 검증
```python
from pydantic import BaseModel, validator

class InputData(BaseModel):
    name: str
    age: int
    
    @validator('age')
    def age_must_be_positive(cls, v):
        if v <= 0:
            raise ValueError('나이는 양수여야 합니다')
        return v
```

### 3. 리소스 관리
```python
@contextmanager
def database_connection():
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()
```

## 🎓 졸업 프로젝트

이 튜토리얼의 마지막으로, 모든 학습 내용을 종합한 **완전한 MCP 서버**를 만들어보겠습니다:

- ✅ 기본 도구 (계산, 텍스트 처리)
- ✅ 파일 관리 (읽기/쓰기/검색)
- ✅ 데이터 변환 (JSON/CSV/XML)
- ✅ 리소스 제공 (템플릿/설정/스키마)
- ✅ HTTP 서버 (웹 접근 가능)
- ✅ 보안 (인증/권한)
- ✅ 로깅 (구조화된 로그)
- ✅ 모니터링 (메트릭스/헬스체크)
- ✅ 에러 처리 (견고한 오류 관리)

이 서버는 실제 프로덕션 환경에서 사용할 수 있는 수준으로 구현됩니다!