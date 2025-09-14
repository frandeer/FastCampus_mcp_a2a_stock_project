# Step 3: 리소스 관리와 템플릿

이 단계에서는 MCP의 리소스(Resources) 기능을 활용해보겠습니다.

## 🎯 학습 목표

- MCP 리소스 개념 이해
- 정적 리소스 제공
- 동적 리소스 생성
- 리소스 템플릿 활용
- 프롬프트와 스키마 관리

## 📝 리소스란?

MCP에서 **리소스**는 도구(Tools)와 다른 개념입니다:
- **도구**: 클라이언트가 호출하는 함수
- **리소스**: 서버가 제공하는 읽기 전용 데이터

리소스는 다음과 같은 용도로 사용됩니다:
- 설정 파일
- 템플릿
- 스키마 정의
- 프롬프트 템플릿
- 정적 데이터

## 🛠️ 구현 예제

### 1. 기본 리소스 제공
```python
@mcp.resource("config://settings")
def get_settings() -> str:
    return json.dumps({
        "version": "1.0",
        "debug": True,
        "features": ["logging", "caching"]
    })
```

### 2. 템플릿 리소스
```python
@mcp.resource("template://email")
def get_email_template() -> str:
    return '''
    안녕하세요 {{name}}님,
    
    {{message}}
    
    감사합니다.
    {{sender}}
    '''
```

### 3. 동적 리소스
```python
@mcp.resource("data://current-time")
def get_current_time() -> str:
    return datetime.now().isoformat()
```

## 📂 파일 구조

```
step3_resources/
├── README.md
├── resource_server.py       # 기본 리소스 서버
├── template_server.py       # 템플릿 관리 서버
├── schema_server.py         # 스키마 제공 서버
└── templates/              # 템플릿 파일들
    ├── email.html
    ├── report.md
    └── config.json
```

## 🎯 실습 목표

이 단계에서는 다음과 같은 실용적인 리소스 서버를 만들어보겠습니다:

1. **설정 관리 서버**: 애플리케이션 설정을 리소스로 제공
2. **템플릿 서버**: 이메일, 보고서 등의 템플릿 관리
3. **스키마 서버**: JSON 스키마와 API 문서 제공
4. **통합 리소스 서버**: 모든 기능을 포함한 완전한 예제

각 서버는 실제 프로젝트에서 바로 사용할 수 있는 수준으로 구현됩니다.

다음 단계: [Step 4: 고급 기능](../step4_advanced/README.md)