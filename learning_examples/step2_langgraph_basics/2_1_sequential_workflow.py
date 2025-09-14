#!/usr/bin/env python3
"""
2.1 순차 워크플로우 - 삼성전자 기본 분석

LangGraph의 기본 개념을 학습하는 첫 번째 예제입니다.
삼성전자(005930) 주식을 순차적으로 분석하는 간단한 워크플로우를 구현합니다.

학습 목표:
- LangGraph의 StateGraph 기본 개념 이해
- 노드(Node) 정의와 연결 방법 학습  
- 상태(State) 관리와 데이터 전달 이해
- 순차적 실행 흐름 구현

실행 전제 조건:
- MCP 서버들이 실행 중이어야 함 (./1-run-all-services.sh)
- 주식 분석 서버(포트 8040)가 활성화되어 있어야 함
"""

import asyncio
import json
from typing import Annotated, TypedDict
from pathlib import Path
import sys

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langgraph.graph.message import add_messages
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


class AnalysisState(TypedDict):
    """
    분석 상태를 관리하는 클래스
    
    각 노드에서 생성된 정보를 다음 노드로 전달하기 위해 사용됩니다.
    """
    messages: Annotated[list[BaseMessage], add_messages]
    symbol: str  # 분석 종목 코드
    current_price: float  # 현재 주가
    technical_analysis: dict  # 기술적 분석 결과
    fundamental_analysis: dict  # 기본적 분석 결과
    final_recommendation: str  # 최종 투자 의견


def print_section(title: str):
    """섹션 구분선 출력"""
    print(f"\n{'='*50}")
    print(f"  {title}")
    print('='*50)


async def collect_basic_data(state: AnalysisState) -> AnalysisState:
    """
    1단계: 기본 데이터 수집
    
    삼성전자의 기본 정보를 수집합니다.
    실제 환경에서는 MCP 서버를 통해 실시간 데이터를 가져올 수 있습니다.
    """
    print("\n🔍 1단계: 기본 데이터 수집 중...")
    
    # 모의 데이터 (실제로는 MCP 서버에서 가져옴)
    symbol = "005930"  # 삼성전자
    current_price = 72000  # 현재 주가 (원)
    
    print(f"   종목: 삼성전자 ({symbol})")
    print(f"   현재 주가: {current_price:,}원")
    
    # 상태 업데이트
    state["symbol"] = symbol
    state["current_price"] = current_price
    state["messages"].append(
        AIMessage(content=f"삼성전자({symbol}) 기본 데이터 수집 완료. 현재 주가: {current_price:,}원")
    )
    
    await asyncio.sleep(1)  # 실제 API 호출 시뮬레이션
    return state


async def perform_technical_analysis(state: AnalysisState) -> AnalysisState:
    """
    2단계: 기술적 분석
    
    수집된 주가 데이터를 바탕으로 기술적 분석을 수행합니다.
    """
    print("\n📈 2단계: 기술적 분석 수행 중...")
    
    # 모의 기술적 분석 결과
    technical_data = {
        "rsi": 45.2,  # RSI (상대강도지수)
        "macd_signal": "매수",  # MACD 신호
        "moving_average_20": 71500,  # 20일 이동평균
        "moving_average_60": 70200,  # 60일 이동평균
        "trend": "상승"  # 추세
    }
    
    # 분석 결과 출력
    print(f"   RSI: {technical_data['rsi']} (중립)")
    print(f"   MACD 신호: {technical_data['macd_signal']}")
    print(f"   20일 이평선: {technical_data['moving_average_20']:,}원")
    print(f"   추세: {technical_data['trend']}")
    
    # 상태 업데이트
    state["technical_analysis"] = technical_data
    state["messages"].append(
        AIMessage(content=f"기술적 분석 완료: RSI {technical_data['rsi']}, 추세 {technical_data['trend']}")
    )
    
    await asyncio.sleep(1)  # 분석 시간 시뮬레이션
    return state


async def perform_fundamental_analysis(state: AnalysisState) -> AnalysisState:
    """
    3단계: 기본적 분석 (재무 분석)
    
    삼성전자의 재무 지표를 분석합니다.
    """
    print("\n📊 3단계: 기본적 분석 수행 중...")
    
    # 모의 재무 분석 결과
    fundamental_data = {
        "per": 12.5,  # 주가수익비율
        "pbr": 1.2,   # 주가순자산비율
        "roe": 9.8,   # 자기자본이익률
        "debt_ratio": 15.2,  # 부채비율
        "revenue_growth": 8.5,  # 매출 성장률 (%)
        "rating": "양호"  # 전체 재무 등급
    }
    
    # 분석 결과 출력
    print(f"   PER: {fundamental_data['per']} (적정 수준)")
    print(f"   PBR: {fundamental_data['pbr']} (저평가)")
    print(f"   ROE: {fundamental_data['roe']}% (양호)")
    print(f"   매출 성장률: {fundamental_data['revenue_growth']}%")
    print(f"   재무 등급: {fundamental_data['rating']}")
    
    # 상태 업데이트
    state["fundamental_analysis"] = fundamental_data
    state["messages"].append(
        AIMessage(content=f"기본적 분석 완료: PER {fundamental_data['per']}, 재무 등급 {fundamental_data['rating']}")
    )
    
    await asyncio.sleep(1)  # 분석 시간 시뮬레이션
    return state


async def generate_recommendation(state: AnalysisState) -> AnalysisState:
    """
    4단계: 최종 투자 의견 생성
    
    기술적 분석과 기본적 분석 결과를 종합하여 최종 투자 의견을 제시합니다.
    """
    print("\n💡 4단계: 최종 투자 의견 생성 중...")
    
    # 분석 결과 종합
    tech_score = 0
    fund_score = 0
    
    # 기술적 분석 점수 계산
    rsi = state["technical_analysis"]["rsi"]
    if 30 <= rsi <= 70:  # 중립 구간
        tech_score += 1
    if state["technical_analysis"]["trend"] == "상승":
        tech_score += 1
    
    # 기본적 분석 점수 계산  
    if state["fundamental_analysis"]["per"] < 15:  # PER이 15 미만이면 좋음
        fund_score += 1
    if state["fundamental_analysis"]["pbr"] < 1.5:  # PBR이 1.5 미만이면 좋음
        fund_score += 1
    if state["fundamental_analysis"]["roe"] > 8:  # ROE가 8% 이상이면 좋음
        fund_score += 1
    
    # 최종 점수 계산 (0-5점)
    total_score = tech_score + fund_score
    
    # 투자 의견 결정
    if total_score >= 4:
        recommendation = "매수 (BUY)"
    elif total_score >= 3:
        recommendation = "보유 (HOLD)"
    elif total_score >= 2:
        recommendation = "관망 (NEUTRAL)"
    else:
        recommendation = "매도 (SELL)"
    
    print(f"   기술적 분석 점수: {tech_score}/2")
    print(f"   기본적 분석 점수: {fund_score}/3")
    print(f"   종합 점수: {total_score}/5")
    print(f"   🎯 최종 투자 의견: {recommendation}")
    
    # 상태 업데이트
    state["final_recommendation"] = recommendation
    state["messages"].append(
        AIMessage(content=f"최종 분석 완료: 종합 점수 {total_score}/5, 투자 의견 {recommendation}")
    )
    
    return state


async def create_sequential_workflow():
    """
    순차 워크플로우 생성
    
    각 단계가 순서대로 실행되는 간단한 워크플로우를 만듭니다.
    """
    # StateGraph 객체 생성
    workflow = StateGraph(AnalysisState)
    
    # 노드들을 워크플로우에 추가
    workflow.add_node("collect_data", collect_basic_data)
    workflow.add_node("technical", perform_technical_analysis)
    workflow.add_node("fundamental", perform_fundamental_analysis)
    workflow.add_node("recommend", generate_recommendation)
    
    # 시작점 설정
    workflow.set_entry_point("collect_data")
    
    # 노드 간 연결 (순차적 실행)
    workflow.add_edge("collect_data", "technical")
    workflow.add_edge("technical", "fundamental")  
    workflow.add_edge("fundamental", "recommend")
    workflow.add_edge("recommend", END)
    
    # 워크플로우 컴파일
    return workflow.compile()


async def main():
    """메인 실행 함수"""
    print_section("LangGraph 2.1: 순차 워크플로우 - 삼성전자 분석")
    
    try:
        # 워크플로우 생성
        print("\n🔧 워크플로우 생성 중...")
        app = await create_sequential_workflow()
        
        # 초기 상태 설정
        initial_state = {
            "messages": [HumanMessage(content="삼성전자 주식을 분석해주세요.")],
            "symbol": "",
            "current_price": 0,
            "technical_analysis": {},
            "fundamental_analysis": {},
            "final_recommendation": ""
        }
        
        print("✅ 워크플로우 생성 완료")
        print("\n🚀 분석 시작...")
        
        # 워크플로우 실행
        final_state = await app.ainvoke(initial_state)
        
        # 최종 결과 출력
        print_section("📋 분석 결과 요약")
        print(f"종목: 삼성전자 ({final_state['symbol']})")
        print(f"현재 주가: {final_state['current_price']:,}원")
        print(f"기술적 분석: RSI {final_state['technical_analysis']['rsi']}, 추세 {final_state['technical_analysis']['trend']}")
        print(f"기본적 분석: PER {final_state['fundamental_analysis']['per']}, ROE {final_state['fundamental_analysis']['roe']}%")
        print(f"🎯 최종 투자 의견: {final_state['final_recommendation']}")
        
        # 결과를 파일로 저장
        output_dir = Path("./logs")
        output_dir.mkdir(exist_ok=True)
        output_file = output_dir / "samsung_analysis_result.json"
        
        result_data = {
            "symbol": final_state["symbol"],
            "current_price": final_state["current_price"],
            "technical_analysis": final_state["technical_analysis"],
            "fundamental_analysis": final_state["fundamental_analysis"],
            "final_recommendation": final_state["final_recommendation"],
            "messages": [msg.content for msg in final_state["messages"]]
        }
        
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(result_data, f, ensure_ascii=False, indent=2)
        
        print(f"\n💾 결과가 {output_file}에 저장되었습니다.")
        
    except Exception as e:
        print(f"\n❌ 실행 중 오류 발생: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("👋 LangGraph 기초 학습을 시작합니다!")
    print("이 예제는 삼성전자 주식을 순차적으로 분석하는 과정을 보여줍니다.")
    asyncio.run(main())