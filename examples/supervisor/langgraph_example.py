#!/usr/bin/env python3
"""
SupervisorAgent LangGraph 예제

SupervisorAgent가 하위 에이전트들을 실제로 호출하고
3가지 워크플로우 패턴(DATA_ONLY, DATA_ANALYSIS, FULL_WORKFLOW)을 검증합니다.
"""
import asyncio
import sys
from pathlib import Path
from uuid import uuid4

import structlog

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from langchain_core.messages import HumanMessage  # noqa: E402

from examples.common.result_parsers import format_workflow_result  # noqa: E402
from src.lg_agents.supervisor_agent import SupervisorAgent  # noqa: E402

logger = structlog.get_logger(__name__)


def print_section_header(title: str):
    """섹션 헤더를 출력합니다."""
    print("=" * 60)
    print(f"  {title}")
    print("=" * 60)

async def test_supervisor_scenarios():
    """다양한 시나리오로 SupervisorAgent를 테스트합니다."""

    # SupervisorAgent 초기화
    print_section_header("SupervisorAgent 초기화")
    print("🔧 SupervisorAgent 생성 중...")

    supervisor = None
    try:
        supervisor = SupervisorAgent()
        print("✅ SupervisorAgent 초기화 성공!")
        print(f"📊 Agent 이름: {supervisor.agent_name}")
        print(f"🛠️ 노드 수: {len(supervisor.NODE_NAMES)}개")

        # 노드 이름들 출력
        node_names = list(supervisor.NODE_NAMES.values())
        print(f"📋 노드 목록: {', '.join(node_names)}")
        print()

    except Exception as e:
        print(f"❌ SupervisorAgent 초기화 실패: {e}")
        return  # Exit early if initialization fails

    # 테스트 시나리오들 정의
    test_scenarios = [
        {
            "num": "TEST1",
            "request": "삼성전자 현재 주가를 조회하고, 매수가 적절한지 분석한 뒤에 평가하고 실제 매수를 시도해주세요.",
        }
    ]

    print_section_header("SupervisorAgent 테스트")

    if supervisor is None:
        print("❌ SupervisorAgent가 초기화되지 않아 테스트를 진행할 수 없습니다.")
        return

    try:
        # SupervisorAgent 실행
        print("🚀 SupervisorAgent 실행 중...")
        result = await supervisor.graph.ainvoke(
            {"messages": [HumanMessage(content=test_scenarios[0]["request"])]},
            config={"configurable": {"thread_id": str(uuid4())}},
        )

        logger.info(f"result: {result}")

        if result.get("success"):
            print("✅ 요청 처리 성공!")

    except Exception as e:
        print(f"🚫 시나리오 실행 오류: {e}")
        import traceback
        print(f"상세 오류: {traceback.format_exc()}")

        print("\n" + "="*60 + "\n")


async def main():
    """메인 실행 함수"""
    print_section_header("SupervisorAgent - LangGraph 예제")
    print("SupervisorAgent를 통한 하위 에이전트 호출 및 워크플로우 검증")
    print()

    await test_supervisor_scenarios()



if __name__ == "__main__":
    asyncio.run(main())