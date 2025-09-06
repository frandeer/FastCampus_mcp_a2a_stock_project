#!/usr/bin/env python3
"""
MCP 서버 설정 및 클라이언트 생성 헬퍼.

표준 패턴으로 MCP 도구를 로딩하기 위한 공통 설정과 유틸리티 함수들을 제공합니다.
"""

import os
from typing import Dict, List

import structlog
from langchain_mcp_adapters.client import MultiServerMCPClient

logger = structlog.get_logger(__name__)


class MCPServerConfig:
    """MCP 서버 설정 관리 클래스"""

    # Docker 환경 감지
    IS_DOCKER = os.getenv("IS_DOCKER", "false").lower() == "true"

    # 로그 출력
    if IS_DOCKER:
        logger.info("Docker environment detected - using container names for MCP servers")
    else:
        logger.info("Local environment detected - using localhost for MCP servers")

    # 표준 MCP 서버 설정 - Docker 환경에 따라 동적으로 설정
    STANDARD_MCP_SERVERS = {
        # 키움 도메인 서버들
        "kiwoom-market-mcp": {
            "transport": "streamable_http",
            "url": f"http://{'kiwoom-market-mcp' if IS_DOCKER else 'localhost'}:8031/mcp/"
        },
        "kiwoom-info-mcp": {
            "transport": "streamable_http",
            "url": f"http://{'kiwoom-info-mcp' if IS_DOCKER else 'localhost'}:8032/mcp/"
        },
        "trading-domain": {
            "transport": "streamable_http",
            "url": f"http://{'kiwoom-trading-mcp' if IS_DOCKER else 'localhost'}:8030/mcp/"
        },
        "investor-domain": {
            "transport": "streamable_http",
            "url": f"http://{'kiwoom-investor-mcp' if IS_DOCKER else 'localhost'}:8033/mcp/"
        },
        "portfolio-domain": {
            "transport": "streamable_http",
            "url": f"http://{'kiwoom-portfolio-mcp' if IS_DOCKER else 'localhost'}:8034/mcp/"
        },

        # 분석 서버들 - FastMCP는 /mcp 경로 사용 (trailing slash 없음)
        "stock-analysis-mcp": {
            "transport": "streamable_http",
            "url": f"http://{'stock-analysis-mcp' if IS_DOCKER else 'localhost'}:8042/mcp"
        },
        "financial-analysis-mcp": {
            "transport": "streamable_http",
            "url": f"http://{'financial-analysis-mcp' if IS_DOCKER else 'localhost'}:8040/mcp"
        },
        "macroeconomic-analysis-mcp": {
            "transport": "streamable_http",
            "url": f"http://{'macroeconomic-analysis-mcp' if IS_DOCKER else 'localhost'}:8041/mcp"
        },

        # 외부 서비스 서버들 - FastMCP는 /mcp 경로 사용 (trailing slash 없음)
        "naver-news-mcp": {
            "transport": "streamable_http",
            "url": f"http://{'naver-news-mcp' if IS_DOCKER else 'localhost'}:8050/mcp"
        },
        "tavily-search-mcp": {
            "transport": "streamable_http",
            "url": f"http://{'tavily-search-mcp' if IS_DOCKER else 'localhost'}:3020/mcp"
        },
    }

    # Agent별 필요한 서버 그룹 정의
    AGENT_SERVER_GROUPS = {
        "data_collector": [
            "kiwoom-market-mcp",
            "kiwoom-info-mcp",
            "naver-news-mcp",
            "tavily-search-mcp"
        ],
        "analysis": [
            "stock-analysis-mcp",
            "financial-analysis-mcp",
            "macroeconomic-analysis-mcp",
            "naver-news-mcp",
            "tavily-search-mcp"
        ],
        "trading": [
            "trading-domain",
            "portfolio-domain",
        ]
    }

    @classmethod
    def get_server_configs(cls, server_names: List[str]) -> Dict[str, Dict[str, str]]:
        """지정된 서버들의 설정을 반환"""
        configs = {}

        for server_name in server_names:
            if server_name in cls.STANDARD_MCP_SERVERS:
                configs[server_name] = cls.STANDARD_MCP_SERVERS[server_name]
            else:
                logger.warning(f"Unknown MCP server: {server_name}")

        return configs

    @classmethod
    def get_agent_server_configs(cls, agent_type: str) -> Dict[str, Dict[str, str]]:
        """Agent 타입에 따른 서버 설정을 반환"""
        if agent_type not in cls.AGENT_SERVER_GROUPS:
            raise ValueError(f"Unknown agent type: {agent_type}")

        server_names = cls.AGENT_SERVER_GROUPS[agent_type]
        return cls.get_server_configs(server_names)


async def create_mcp_client_and_tools(server_configs: Dict[str, Dict[str, str]]):
    """
    표준 패턴으로 MCP 클라이언트 생성 및 도구 로딩

    Args:
        server_configs: MCP 서버 설정 딕셔너리

    Returns:
        tuple: (mcp_client, tools) - 클라이언트와 로딩된 도구들

    Example:
        server_configs = MCPServerConfig.get_agent_server_configs("data_collector")
        client, tools = await create_mcp_client_and_tools(server_configs)
    """
    try:
        if not server_configs:
            raise ValueError("No server configs provided")

        logger.info(f"Creating MCP client for servers: {list(server_configs.keys())}")

        # MultiServerMCPClient 생성
        # NOTE: langchain-mcp-adapters 라이브러리 사용
        mcp_client = MultiServerMCPClient(server_configs)

        # 도구 로딩 - TaskGroup 오류 디버깅을 위해 더 자세한 에러 처리
        try:
            tools = await mcp_client.get_tools()
        except BaseExceptionGroup as eg:
            # TaskGroup에서 발생한 모든 예외 출력
            logger.error(f"TaskGroup errors: {len(eg.exceptions)} exceptions")
            for i, exc in enumerate(eg.exceptions):
                logger.error(f"  Exception {i+1}: {type(exc).__name__}: {exc}")
            raise

        logger.info(f"Successfully loaded {len(tools)} tools from {len(server_configs)} servers")

        return mcp_client, tools

    except Exception as e:
        logger.error(f"Failed to create MCP client and load tools: {e}")
        # 더 자세한 에러 정보 출력
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise


async def load_tools_for_agent(agent_type: str):
    """
    Agent 타입에 맞는 MCP 도구들을 로딩

    Args:
        agent_type: Agent 타입 ("data_collector", "analysis", "trading")

    Returns:
        list: 로딩된 도구들

    Example:
        tools = await load_tools_for_agent("data_collector")
    """
    try:
        server_configs = MCPServerConfig.get_agent_server_configs(agent_type)
        _, tools = await create_mcp_client_and_tools(server_configs)
        return tools

    except Exception as e:
        logger.error(f"Failed to load tools for agent {agent_type}: {e}")
        raise


# 편의 함수들
async def load_data_collector_tools():
    """데이터 수집용 MCP 도구들 로딩"""
    return await load_tools_for_agent("data_collector")


async def load_analysis_tools():
    """분석용 MCP 도구들 로딩"""
    return await load_tools_for_agent("analysis")


async def load_trading_tools():
    """거래용 MCP 도구들 로딩"""
    return await load_tools_for_agent("trading")


# 테스트 함수
async def test_mcp_connections():
    """모든 MCP 서버 연결 테스트"""
    print(" MCP 서버 연결 테스트 시작")

    for agent_type in MCPServerConfig.AGENT_SERVER_GROUPS.keys():
        try:
            print(f"\n {agent_type} Agent용 도구 로딩 테스트...")
            tools = await load_tools_for_agent(agent_type)
            print(f"   성공: {len(tools)}개 도구 로딩됨")

            # 도구 이름들 출력
            tool_names = [tool.name for tool in tools[:5]]  # 처음 5개만
            print(f"  ️ 도구 예시: {tool_names}")

        except Exception as e:
            print(f"   실패: {e}")

    print("\n MCP 서버 연결 테스트 완료")


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_mcp_connections())
