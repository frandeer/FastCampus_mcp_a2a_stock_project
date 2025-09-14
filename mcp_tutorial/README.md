# MCP 튜토리얼 - FastMCP로 나만의 MCP 서버 만들기

이 튜토리얼은 FastMCP를 사용해서 MCP (Model Context Protocol) 서버를 단계적으로 만드는 방법을 학습합니다.

## 🎯 학습 목표

1. **기본 MCP 서버** 생성 및 실행
2. **도구(Tools)** 추가하여 기능 확장
3. **리소스(Resources)** 관리 기능 구현
4. **고급 기능** (인증, 로깅, 에러 처리) 구현

## 📁 폴더 구조

```
mcp_tutorial/
├── README.md                    # 이 파일
├── step1_basic/                 # 기본 MCP 서버
├── step2_tools/                 # 도구 추가 단계  
├── step3_resources/             # 리소스 관리 단계
└── step4_advanced/              # 고급 기능 단계
```

## 🛠️ 필요한 환경

- Python 3.8+
- FastMCP 라이브러리 (`pip install fastmcp`)
- 기본적인 Python 지식

## 📋 단계별 가이드

### Step 1: 기본 MCP 서버 (step1_basic/)
- 최소한의 MCP 서버 구현
- STDIO 전송 프로토콜 사용
- 간단한 "Hello World" 기능

### Step 2: 도구 추가 (step2_tools/)
- @mcp.tool 데코레이터 사용법
- 파라미터가 있는 함수 구현
- 다양한 데이터 타입 처리

### Step 3: 리소스 관리 (step3_resources/)
- 파일이나 데이터 리소스 제공
- 동적 리소스 생성
- 리소스 템플릿 활용

### Step 4: 고급 기능 (step4_advanced/)
- HTTP 전송 프로토콜 사용
- 인증 및 보안
- 로깅 및 에러 처리
- 성능 최적화

## 🚀 시작하기

각 단계별 폴더의 README.md를 따라하면서 학습을 진행하세요:

1. `step1_basic/README.md`부터 시작
2. 각 단계의 예제 코드를 실행해보기
3. 연습 문제 해결하기
4. 다음 단계로 진행

## 💡 팁

- 각 단계의 코드를 직접 타이핑해보세요
- 에러가 발생하면 로그를 확인하고 디버깅해보세요
- 자신만의 기능을 추가해보세요
- 완성된 MCP 서버를 실제 Claude Desktop에서 테스트해보세요

## 📚 참고 자료

- [FastMCP 공식 문서](https://gofastmcp.com)
- [MCP 프로토콜 스펙](https://spec.modelcontextprotocol.io)
- [FastCampus MCP A2A 프로젝트](../README.md)