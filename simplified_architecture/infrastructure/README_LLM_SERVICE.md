# LLM Integration Service

주식 분석을 위한 LLM 통합 서비스로, OpenAI GPT 모델을 활용하여 신뢰할 수 있는 주식 투자 분석을 제공합니다.

## 📋 주요 기능

### 1. OpenAI 통합
- **GPT-4 모델 활용**: 고품질 주식 분석
- **구조화된 출력**: JSON Schema 기반 응답 검증
- **비동기 처리**: 대용량 요청 처리 최적화

### 2. 프롬프트 엔지니어링
- **전문가 페르소나**: 주식 분석가 롤플레이
- **컨텍스트 통합**: 시장 데이터, 뉴스 감정, 기술적 지표 종합
- **위험 인식**: 보수적이고 신중한 분석 접근

### 3. 에러 처리 및 폴백
- **API 장애 대응**: 자동 재시도 및 폴백 메커니즘
- **데이터 검증**: 응답 구조 및 값 범위 검증
- **우아한 저하**: 제한적 데이터로도 기본 분석 제공

### 4. 성능 최적화
- **레이트 리미팅**: API 사용량 제한 준수
- **지능적 캐싱**: 중복 요청 최소화 (5분 TTL)
- **응답 압축**: 토큰 사용량 최적화

### 5. 테스트 지원
- **Mock 서비스**: 개발/테스트용 모킹 구현
- **시나리오 테스트**: 다양한 시장 상황 시뮬레이션

## 🏗 아키텍처

```
LLMService Protocol (Interface)
├── OpenAILLMService (Production)
│   ├── AsyncOpenAI Client
│   ├── Rate Limiter
│   ├── Cache Manager
│   ├── Prompt Templates
│   └── Response Validator
└── MockLLMService (Testing)
    ├── Scenario Simulation
    └── Call Counter
```

## 🚀 사용법

### 기본 사용

```python
from simplified_architecture.infrastructure.llm_service import LLMServiceFactory

# Production 환경
service = LLMServiceFactory.create_service("openai", api_key="your-key")

# 테스트 환경  
service = LLMServiceFactory.create_service("mock")

# 주식 분석 실행
result = await service.analyze_stock(
    stock_info={"code": "005930", "name": "삼성전자", "sector": "반도체"},
    market_data={"current_price": 75000, "volume": 1000000},
    news_sentiment={"sentiment": 0.7}
)
```

### 설정 옵션

```python
service = LLMServiceFactory.create_service(
    "openai",
    model="gpt-4o-mini",          # 사용 모델
    max_retries=3,                # 재시도 횟수
    timeout=30.0,                 # 타임아웃 (초)
    cache_ttl=300,                # 캐시 TTL (초)
    rate_limit_rpm=60             # 분당 요청 제한
)
```

## 📊 응답 형식

```python
{
    "signal": "BUY",                    # 투자 신호
    "confidence": 0.8,                  # 신뢰도 (0.0-1.0)
    "target_price": 82500.0,            # 목표 가격
    "reasoning": "상세한 분석 근거...",   # 분석 근거
    "key_factors": [                    # 핵심 요인 (1-5개)
        "긍정적 뉴스 감정",
        "강한 거래량",
        "기술적 돌파"
    ],
    "risk_assessment": "중간 수준",     # 위험 평가
    "time_horizon": "중기"              # 투자 기간
}
```

## 🔒 보안 및 제한사항

### API 키 관리
- 환경변수 사용 권장: `OPENAI_API_KEY`
- 키 노출 방지를 위한 검증

### 레이트 리미팅
- 기본 제한: 분당 60회 요청
- 자동 대기 및 재시도 메커니즘

### 데이터 검증
- 입력 데이터 정규화
- 응답 구조 검증 (Pydantic)
- 값 범위 검증

## 🧪 테스트

### 간단한 테스트 실행
```bash
python3 simplified_architecture/infrastructure/simple_test.py
```

### 포괄적 테스트 (의존성 설치 필요)
```bash
pip install -r simplified_architecture/infrastructure/requirements.txt
python3 simplified_architecture/infrastructure/test_llm_service.py
```

## 📈 성능 지표

### Mock 서비스
- **응답 시간**: ~100ms
- **처리량**: 제한 없음
- **신뢰성**: 100%

### OpenAI 서비스
- **응답 시간**: 1-3초 (모델 및 네트워크 상태에 따라)
- **처리량**: API 제한에 따라
- **캐시 적중 시**: ~10ms

## 🔧 확장성

### 새로운 LLM 제공업체 추가
1. `LLMService` 프로토콜 구현
2. `LLMServiceFactory`에 새 타입 등록
3. 설정 및 테스트 추가

### 프롬프트 개선
- `PromptTemplates` 클래스에서 템플릿 수정
- A/B 테스트를 통한 효과성 검증

### 캐시 전략 개선
- Redis 등 외부 캐시 저장소 연동
- 분산 환경 지원

## 🚨 주의사항

1. **API 비용**: OpenAI API 사용 시 토큰 기반 과금
2. **데이터 프라이버시**: 민감한 정보 전송 주의
3. **결과 해석**: AI 분석은 참고용이며 투자 결정은 신중히
4. **시장 변동성**: 실시간 데이터와 차이 가능성

## 📚 의존성

- `openai>=1.0.0`: OpenAI API 클라이언트
- `pydantic>=2.0.0`: 데이터 검증
- `aiohttp>=3.8.0`: 비동기 HTTP 클라이언트

## 🔄 업데이트 로그

- **v1.0**: 초기 OpenAI 통합 및 Mock 서비스
- **Future**: Claude, Gemini 등 다중 제공업체 지원 예정