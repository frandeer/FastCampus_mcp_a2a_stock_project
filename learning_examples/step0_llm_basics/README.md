# Step 0: LLM 기본 연결 및 도구 호출 학습

## 🎯 학습 목표
- OpenAI GPT-4o-mini와 연결하는 방법 학습
- AI가 도구를 호출하는 기본 개념 이해
- MCP의 핵심 아이디어 체험하기

## 🧠 핵심 개념: AI + 도구 호출
MCP의 핵심 아이디어는 **AI가 필요에 따라 도구를 선택하고 사용하는 것**입니다:

```
사용자: "25 + 17을 계산해주세요"
    ↓
AI: "계산이 필요하네요. add_numbers 도구를 사용하겠습니다"
    ↓  
도구 호출: add_numbers(25, 17)
    ↓
도구 결과: {"result": 42, "message": "25 + 17 = 42"}
    ↓
AI: "계산 결과는 42입니다. 25와 17을 더하면 42가 나옵니다."
```

## 🚀 실행 준비

### 1. 환경 설정 파일 생성
```bash
# .env.example을 .env로 복사
cp learning_examples/.env.example learning_examples/.env

# 실제 OpenAI API 키로 수정
# learning_examples/.env 파일을 열어서
# OPENAI_API_KEY=your-real-openai-api-key-here
```

### 2. API 키 확인 (자동)
- 프로그램 실행시 자동으로 .env 파일에서 로딩
- 안전한 형태로 마스킹되어 표시 (sk-JcsNm...0NnW)

## 🏃 실행 방법

### 예제 1: 기본 LLM 테스트
```bash
cd learning_examples/step0_llm_basics
python simple_llm_test.py
```

**결과 예시:**
```
🚀 LLM 기본 연결 테스트 시작
✅ 환경변수 파일 로딩: /path/to/learning_examples/.env
==================================================
🔧 환경 설정 상태
==================================================
✅ OPENAI_API_KEY: sk-JcsNm...0NnW
🔧 LEARNING_DEBUG_MODE: True
🔧 LEARNING_API_DELAY: 1
==================================================

📋 테스트 1: 간단한 인사 테스트
🤖 AI에게 질문: 안녕하세요! 당신은 누구인가요?
💬 AI 응답: 안녕하세요! 저는 AI 언어 모델로, 다양한 질문에 답하고...
✅ 테스트 성공!
```

### 예제 2: AI + 도구 호출 (핵심!)
```bash
python llm_with_tools.py
```

**결과 예시:**
```
📋 테스트 1
👤 사용자: 25 + 17을 계산해주세요
🤖 AI가 생각하고 필요한 도구를 선택 중...
🔧 AI가 1개의 도구를 사용하기로 결정했습니다
  🛠️  도구 호출: add_numbers({'a': 25, 'b': 17})
  📊 실행 결과: {'operation': 'addition', 'result': 42, 'message': '25 + 17 = 42'}
🤖 AI가 도구 결과를 바탕으로 최종 응답을 생성 중...
💬 AI 최종 응답: 25 + 17 = 42입니다. 덧셈 계산을 통해 결과를 구했습니다.
✅ 완료!
```

## 🔍 주목할 점들

### 1. AI의 자동 도구 선택
- "25 + 17을 계산해주세요" → AI가 `add_numbers` 도구 선택
- "12 곱하기 8은 얼마인가요?" → AI가 `multiply_numbers` 도구 선택
- "안녕하세요" → 계산이 아니므로 도구 사용 안함

### 2. 도구 실행 과정
1. **분석**: AI가 사용자 요청 분석
2. **선택**: 필요한 도구와 인수 결정  
3. **실행**: 도구 호출하고 결과 받기
4. **응답**: 결과를 바탕으로 친절한 설명 생성

### 3. MCP와의 연결점
- **OpenAI Function Calling** = MCP의 기본 아이디어
- **도구 정의** = MCP 서버의 도구 등록
- **AI 선택** = LangGraph의 조건부 라우팅
- **결과 처리** = A2A의 메시지 전달

## 🚀 다음 단계
Step 1에서는 실제 MCP 서버를 만들어서 이 도구들을 독립적인 서비스로 분리해보겠습니다!

## 💡 문제 해결

### .env 파일이 없다고 할 때
```bash
# .env.example을 복사해서 .env 생성
cp learning_examples/.env.example learning_examples/.env

# 실제 API 키로 수정
vim learning_examples/.env
# 또는
code learning_examples/.env
```

### API 키 오류가 날 때
1. `.env` 파일에서 `OPENAI_API_KEY=your-real-key-here` 확인
2. API 키가 유효한지 확인 (OpenAI 계정에서 확인)
3. 환경변수 파일 로딩 메시지 확인

### 패키지 없음 오류가 날 때
```bash
# 프로젝트에 이미 포함되어 있음
uv sync

# 또는 개별 설치
uv add openai python-dotenv
```