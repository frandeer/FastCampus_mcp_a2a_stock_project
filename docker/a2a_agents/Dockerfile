# A2A Expert Agents를 위한 공통 Dockerfile
FROM python:3.12-slim

# 작업 디렉토리 설정
WORKDIR /app

# 시스템 패키지 설치
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Python 의존성 복사 및 설치
COPY ../../pyproject.toml ./
COPY ../../src ./src

# uv 설치 및 의존성 설치
RUN pip install --no-cache-dir uv && \
    uv pip install --system -e .

# A2A 관련 추가 패키지 설치
RUN uv pip install --system \
    langgraph \
    langchain \
    anthropic \
    openai \
    websockets \
    uvicorn[standard]

# 환경 변수 설정
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV AGENT_TYPE=""
ENV AGENT_HOST="0.0.0.0"
ENV AGENT_PORT="8000"

# 실행 사용자 생성 (보안)
RUN adduser --disabled-password --gecos '' appuser && \
    chown -R appuser:appuser /app
USER appuser

# 기본 포트 노출
EXPOSE 8000

# 기본 실행 명령 (환경변수로 AGENT_TYPE을 받아서 실행)
CMD ["sh", "-c", "python -m src.a2a_agents.${AGENT_TYPE:-supervisor}.__main__"]
