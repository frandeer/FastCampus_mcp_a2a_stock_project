# 🚀 빠른 시작 가이드 - 통합 한국 주식시장 분석 플랫폼

## ⚡ 3분 안에 시작하기

### 1단계: 플랫폼 실행

```bash
# Step 4 디렉토리로 이동
cd learning_examples/step4_full_integration

# 간소화 버전 실행 (Redis 불필요)
python 4_1_integrated_market_platform_simple.py
```

**실행 성공 시 화면:**
```
============================================================
🚀 통합 한국 주식시장 분석 플랫폼 (간소화 버전)
============================================================
📡 웹소켓 연결: ws://localhost:8765
🤖 기본적 분석 에이전트: http://localhost:8001
💭 센티먼트 분석 에이전트: http://localhost:8002
⚠️  리스크 분석 에이전트: http://localhost:8003

📈 모니터링 대상:
   - 005930: 삼성전자
   - 373220: LG에너지솔루션
   - 000660: SK하이닉스

💡 사용법:
   1. client.html을 웹브라우저에서 열기
   2. '연결' 버튼 클릭하여 실시간 데이터 확인
   3. 분석 버튼들로 AI 분석 결과 확인

⏹️  Ctrl+C로 중지
============================================================
```

### 2단계: 웹 클라이언트 연결

```bash
# 웹브라우저에서 client.html 열기
open client.html  # macOS
# 또는 브라우저에서 file:///경로/client.html 직접 열기
```

### 3단계: 실시간 데이터 확인

1. **연결 버튼 클릭** → 웹소켓 연결
2. **실시간 주식 가격** 자동 업데이트 확인
3. **분석 버튼들** 클릭하여 AI 분석 결과 확인

## 🧪 테스트 명령어

### API 테스트

```bash
# 에이전트 상태 확인
curl http://localhost:8001/status    # 기본적 분석
curl http://localhost:8002/status    # 센티먼트 분석  
curl http://localhost:8003/status    # 리스크 분석

# 직접 분석 요청
curl -X POST http://localhost:8001/analyze \
  -H "Content-Type: application/json" \
  -d '{"symbol": "005930", "analysis_type": "fundamental"}'
```

## 📊 로그 해석

```
INFO - [기술분석] 005930 추세 분석 완료: 상승
INFO - [fundamental_agent] 005930 분석 완료: 100.0점
INFO - [sentiment_agent] 005930 분석 완료: 17.6점
INFO - [risk_agent] 005930 분석 완료: 63.9점
```

- **기술분석**: LangGraph 워크플로우 결과
- **fundamental_agent**: 기본적 분석 (시가총액 기반)
- **sentiment_agent**: 센티먼트 분석 (거래량/변동성 기반)
- **risk_agent**: 리스크 분석 (변동성 기반)

## 🔧 문제 해결

### 포트 충돌 시
```bash
# 포트 사용 확인
lsof -i :8001
lsof -i :8002  
lsof -i :8003
lsof -i :8765

# 프로세스 종료
kill -9 <PID>
```

### WebSocket 연결 실패 시
- 브라우저 콘솔에서 에러 메시지 확인
- 방화벽 설정 확인
- localhost 대신 127.0.0.1 시도

## 🎯 주요 기능 체험

### 1. 실시간 데이터 스트리밍
- 5초마다 주식 가격 업데이트
- 웹소켓을 통한 실시간 브로드캐스트

### 2. LangGraph 워크플로우
- 데이터 수집 → 추세 분석 → 신호 생성
- 메모리 기반 체크포인트

### 3. A2A 에이전트 통신
- HTTP API를 통한 에이전트 간 통신
- 3개 전문 분석 에이전트 협업

### 4. 통합 오케스트레이션
- 30초마다 자동 분석 실행
- 결과 통합 및 실시간 배포

## 📚 다음 단계

1. **설정 변경**: `config.json`에서 분석 주기 조정
2. **실제 데이터 연동**: KIS API 또는 웹 크롤링 추가
3. **UI 개선**: React/Vue.js로 대시보드 구축
4. **알고리즘 고도화**: 머신러닝 모델 통합

---

**🎉 축하합니다! FastCampus MCP A2A 프로젝트의 모든 핵심 개념을 완주했습니다!**