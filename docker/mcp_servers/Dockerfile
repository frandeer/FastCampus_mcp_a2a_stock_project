# MCP Servers를 위한 공통 Dockerfile
FROM python:3.12-slim

# 작업 디렉토리 설정
WORKDIR /app

# 시스템 패키지 설치 (healthcheck용 curl 포함)
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 소스코드 복사
COPY src ./src

# NOTE: MCP SDK 및 관련 패키지 설치(일부러 uv 에 있는것보다 적게 설치)
RUN pip install \
    fastmcp \
    httpx \ 
    httpx-sse \
    tavily-python \
    fredapi \
    finance-datareader \
    publicdatareader \
    pandas \
    structlog \
    psutil


# 환경 변수 설정
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV MCP_PORT=9000

# 실행 사용자 생성 (보안)
RUN adduser --disabled-password --gecos '' appuser && \
    chown -R appuser:appuser /app

USER appuser

# 기본 포트 노출
EXPOSE 9000
