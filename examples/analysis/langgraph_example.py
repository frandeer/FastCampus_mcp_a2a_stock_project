#!/usr/bin/env python3
"""
Analysis Agent - LangGraph 레벨 직접 호출 예제

AnalysisAgent를 직접 import하여 사용하는 예제입니다.
4차원 통합 분석(기술적, 기본적, 거시경제, 감성분석)을 수행합니다.

실행 전제 조건:
- MCP 서버들이 실행 중이어야 함 (./1-run-all-services.sh)
- 특히 포트 8040(stock-analysis), 8041(financial), 8042(macro), 8050(news)가 활성화되어 있어야 함
"""

import asyncio
import json
import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# 공통 모듈 import
from examples.common.logging import (  # noqa: E402
    LogCapture,
    get_log_filename,
    get_result_filename,
)
from examples.common.server_checks import check_mcp_servers  # noqa: E402
from src.lg_agents.analysis_agent import (  # noqa: E402
    analyze,
    create_analysis_agent,
)


def print_section(title: str):
    """섹션 구분선 출력"""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)


async def main():
    """메인 실행 함수"""

    log_capture = LogCapture()
    log_capture.start_capture()

    try:
        print_section("Analysis Agent - LangGraph 예제")

        # 1. MCP 서버 상태 확인
        if not await check_mcp_servers("analysis"):
            print("\n⚠️ 일부 MCP 서버가 실행되지 않았습니다.")
            print("💡 해결 방법: ./1-run-all-services.sh 실행")
        
        # 2. Analysis Agent 초기화
        print_section("Agent 초기화")
        
        print("create_react_agent 기반 AnalysisAgent 생성 중...")
        agent = await create_analysis_agent(is_debug=True)
        
        if not agent:
            print("❌ AnalysisAgent 생성 실패")
            return

        # 3. 분석 요청 준비 - 구체적인 도구 사용 요청
        print_section("분석 실행")

        test_request = {
            "symbols": ["005930"],
            "collected_data": {
                "price_data": {"status": "available", "last_price": 72000},
                "news_data": {"status": "available", "article_count": 30},
                "financial_data": {"status": "partial"},
            },
            "user_question": """
다음 도구들을 모두 사용해서 통합적인 분석을 수행해주세요.

1. 기술적 분석 (Technical Analysis):
   - calculate_technical_indicators로 RSI, MACD, 볼린저밴드 계산
   - analyze_chart_patterns로 차트 패턴 분석
   - identify_support_resistance로 지지/저항선 확인

2. 기본적 분석 (Fundamental Analysis):
   - get_financial_ratios로 PER, PBR, ROE 등 재무비율 계산
   - analyze_financial_statements로 재무제표 분석
   - compare_industry_peers로 동종업계 비교 분석

3. 거시경제 분석 (Macro Analysis):
   - get_economic_indicators로 경제지표 수집
   - analyze_market_conditions로 시장 상황 분석
   - assess_sector_trends로 섹터 트렌드 평가

4. 감성 분석 (Sentiment Analysis):
   - analyze_news_sentiment로 뉴스 감성 분석
   - get_social_sentiment로 소셜 미디어 감성 측정
   - measure_investor_sentiment로 투자자 심리 지수 확인

모든 차원의 도구를 빠짐없이 호출하여 종합적인 분석을 제공하고,
최종적으로 투자 신호(STRONG_BUY/BUY/HOLD/SELL/STRONG_SELL)를 제시해주세요.""",
        }

        print(f"분석 종목: {test_request['symbols']}")
        print(f"질문: {test_request['user_question'][:100]}...")
        print(f"수집된 데이터 타입: {list(test_request['collected_data'].keys())}")

        print("\n🔄 분석 중... (최대 90초 소요)")
        print("⏳ 여러 도구를 호출하므로 시간이 걸릴 수 있습니다...")

        try:
            result = await asyncio.wait_for(
                analyze(
                    agent=agent,
                    symbols=test_request["symbols"],
                    collected_data=test_request["collected_data"],
                    user_question=test_request["user_question"]
                ),
                timeout=90.0
            )
            print("\n모든 분석 도구 호출 완료")
        except asyncio.TimeoutError:
            print("\n분석 타임아웃 (90초)")
            result = {
                "success": False,
                "error": "Analysis timeout after 90 seconds",
                "messages": []
            }

        # 5. 결과 출력
        print_section("분석 결과")

        if isinstance(result, dict) and result.get("success"):
            print("분석 완료!")

            analysis_result = result.get("result", {})

            tool_calls = analysis_result.get('tool_calls_made', 0)
            print("\n도구 호출 검증:")
            print(f"  - 도구 호출 횟수: {tool_calls}회")

        # 6. 전체 결과를 JSON 파일로 저장
        output_dir = Path("../../logs/examples/langgraph")
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / get_result_filename("analysis_result")
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"\n전체 결과가 {output_file}에 저장되었습니다.")

    except Exception as e:
        print(f"\n실행 중 오류 발생: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        log_capture.stop_capture()
        log_dir = Path("../../logs/examples/langgraph")
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / get_log_filename("analysis_langgraph_log")
        log_capture.save_log(str(log_file))
        print_section("테스트 완료")
        print(f"실행 로그가 {log_file}에 저장되었습니다.")


if __name__ == "__main__":
    asyncio.run(main())