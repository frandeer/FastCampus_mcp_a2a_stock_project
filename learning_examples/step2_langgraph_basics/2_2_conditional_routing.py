#!/usr/bin/env python3
"""
2.2 조건부 라우팅 - LG전자 조건부 매매

LangGraph의 조건부 라우팅을 학습하는 예제입니다.
LG전자(066570) 주식을 분석하여 조건에 따라 다른 경로로 분기하는 워크플로우를 구현합니다.

학습 목표:
- LangGraph의 조건부 라우팅 이해
- add_conditional_edges() 사용법 학습
- 조건 함수 작성과 활용
- 분기 처리를 통한 유연한 워크플로우 구성

실행 전제 조건:
- MCP 서버들이 실행 중이어야 함 (./1-run-all-services.sh)
"""

import asyncio
import json
from typing import Annotated, TypedDict, Literal
from pathlib import Path
import sys

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langgraph.graph.message import add_messages
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


class TradingState(TypedDict):
    """
    매매 분석 상태를 관리하는 클래스
    
    조건부 라우팅을 위해 분석 결과와 결정 정보를 포함합니다.
    """
    messages: Annotated[list[BaseMessage], add_messages]
    symbol: str  # 분석 종목 코드
    current_price: float  # 현재 주가
    market_condition: str  # 시장 상황 (bull/bear/sideways)
    volatility: float  # 변동성 수준
    analysis_result: dict  # 분석 결과
    trading_signal: str  # 매매 신호
    risk_level: str  # 위험 수준


def print_section(title: str):
    """섹션 구분선 출력"""
    print(f"\n{'='*50}")
    print(f"  {title}")
    print('='*50)


async def collect_market_data(state: TradingState) -> TradingState:
    """
    1단계: 시장 데이터 수집
    
    LG전자의 기본 정보와 시장 상황을 수집합니다.
    """
    print("\n🔍 1단계: 시장 데이터 수집 중...")
    
    # 모의 시장 데이터
    symbol = "066570"  # LG전자
    current_price = 95000  # 현재 주가 (원)
    
    # 시장 상황 분석 (모의 데이터)
    market_indicators = {
        "kospi_change": -0.8,  # KOSPI 변동률 (%)
        "sector_performance": -1.2,  # 전자업종 성과 (%)
        "trading_volume": 1.5,  # 거래량 비율 (평균 대비)
    }
    
    # 시장 상황 판단
    if market_indicators["kospi_change"] > 1.0:
        market_condition = "bull"  # 상승장
    elif market_indicators["kospi_change"] < -1.0:
        market_condition = "bear"  # 하락장
    else:
        market_condition = "sideways"  # 횡보장
    
    # 변동성 계산 (모의)
    volatility = abs(market_indicators["kospi_change"]) + abs(market_indicators["sector_performance"])
    
    print(f"   종목: LG전자 ({symbol})")
    print(f"   현재 주가: {current_price:,}원")
    print(f"   KOSPI 변동률: {market_indicators['kospi_change']}%")
    print(f"   시장 상황: {market_condition}")
    print(f"   변동성 수준: {volatility:.1f}%")
    
    # 상태 업데이트
    state["symbol"] = symbol
    state["current_price"] = current_price
    state["market_condition"] = market_condition
    state["volatility"] = volatility
    state["messages"].append(
        AIMessage(content=f"LG전자({symbol}) 시장 데이터 수집 완료. 시장 상황: {market_condition}, 변동성: {volatility:.1f}%")
    )
    
    await asyncio.sleep(1)
    return state


def decide_analysis_path(state: TradingState) -> Literal["bull_analysis", "bear_analysis", "neutral_analysis"]:
    """
    라우팅 결정 함수
    
    시장 상황에 따라 어떤 분석 경로로 갈지 결정합니다.
    이 함수의 반환값이 다음에 실행될 노드를 결정합니다.
    """
    market_condition = state["market_condition"]
    
    print(f"\n🔀 라우팅 결정: 시장 상황 '{market_condition}'에 따른 분석 경로 선택")
    
    if market_condition == "bull":
        print("   → 상승장 분석 경로로 이동")
        return "bull_analysis"
    elif market_condition == "bear":
        print("   → 하락장 분석 경로로 이동")
        return "bear_analysis"
    else:
        print("   → 중립 시장 분석 경로로 이동")
        return "neutral_analysis"


async def bull_market_analysis(state: TradingState) -> TradingState:
    """
    상승장 분석 경로
    
    시장이 상승할 때의 분석 전략을 적용합니다.
    """
    print("\n📈 상승장 분석 실행 중...")
    
    analysis_result = {
        "strategy": "성장주 중심 매수",
        "risk_assessment": "중간",
        "target_return": 15.0,  # 목표 수익률 (%)
        "stop_loss": 8.0,  # 손절 라인 (%)
        "position_size": 70,  # 포지션 크기 (%)
        "holding_period": "3-6개월"
    }
    
    # 상승장에서는 적극적 매수 신호
    trading_signal = "STRONG_BUY"
    risk_level = "MEDIUM"
    
    print(f"   전략: {analysis_result['strategy']}")
    print(f"   목표 수익률: {analysis_result['target_return']}%")
    print(f"   포지션 크기: {analysis_result['position_size']}%")
    print(f"   매매 신호: {trading_signal}")
    
    # 상태 업데이트
    state["analysis_result"] = analysis_result
    state["trading_signal"] = trading_signal
    state["risk_level"] = risk_level
    state["messages"].append(
        AIMessage(content=f"상승장 분석 완료: {trading_signal} 신호, 목표 수익률 {analysis_result['target_return']}%")
    )
    
    await asyncio.sleep(1)
    return state


async def bear_market_analysis(state: TradingState) -> TradingState:
    """
    하락장 분석 경로
    
    시장이 하락할 때의 분석 전략을 적용합니다.
    """
    print("\n📉 하락장 분석 실행 중...")
    
    analysis_result = {
        "strategy": "방어적 포지션 및 현금 보유",
        "risk_assessment": "높음",
        "target_return": 3.0,  # 목표 수익률 (%) - 보수적
        "stop_loss": 5.0,  # 손절 라인 (%) - 타이트
        "position_size": 30,  # 포지션 크기 (%) - 소규모
        "holding_period": "1-2개월"
    }
    
    # 하락장에서는 관망 또는 매도 신호
    trading_signal = "SELL"
    risk_level = "HIGH"
    
    print(f"   전략: {analysis_result['strategy']}")
    print(f"   목표 수익률: {analysis_result['target_return']}%")
    print(f"   포지션 크기: {analysis_result['position_size']}%")
    print(f"   매매 신호: {trading_signal}")
    
    # 상태 업데이트
    state["analysis_result"] = analysis_result
    state["trading_signal"] = trading_signal
    state["risk_level"] = risk_level
    state["messages"].append(
        AIMessage(content=f"하락장 분석 완료: {trading_signal} 신호, 방어적 포지션 {analysis_result['position_size']}%")
    )
    
    await asyncio.sleep(1)
    return state


async def neutral_market_analysis(state: TradingState) -> TradingState:
    """
    중립 시장 분석 경로
    
    시장이 횡보할 때의 분석 전략을 적용합니다.
    """
    print("\n➡️ 중립 시장 분석 실행 중...")
    
    analysis_result = {
        "strategy": "단기 스윙 매매",
        "risk_assessment": "중간",
        "target_return": 8.0,  # 목표 수익률 (%)
        "stop_loss": 6.0,  # 손절 라인 (%)
        "position_size": 50,  # 포지션 크기 (%)
        "holding_period": "2-4주"
    }
    
    # 중립 시장에서는 보유 또는 조건부 매수
    volatility = state["volatility"]
    if volatility > 2.0:  # 변동성이 높으면
        trading_signal = "HOLD"
    else:
        trading_signal = "BUY"
    
    risk_level = "MEDIUM"
    
    print(f"   전략: {analysis_result['strategy']}")
    print(f"   목표 수익률: {analysis_result['target_return']}%")
    print(f"   포지션 크기: {analysis_result['position_size']}%")
    print(f"   매매 신호: {trading_signal}")
    
    # 상태 업데이트
    state["analysis_result"] = analysis_result
    state["trading_signal"] = trading_signal
    state["risk_level"] = risk_level
    state["messages"].append(
        AIMessage(content=f"중립 시장 분석 완료: {trading_signal} 신호, 스윙 매매 전략")
    )
    
    await asyncio.sleep(1)
    return state


def decide_risk_management_path(state: TradingState) -> Literal["high_risk", "low_risk"]:
    """
    위험 관리 경로 결정 함수
    
    위험 수준에 따라 추가적인 위험 관리 단계로 분기합니다.
    """
    risk_level = state["risk_level"]
    volatility = state["volatility"]
    
    print(f"\n🔀 위험 관리 라우팅: 위험 수준 '{risk_level}', 변동성 {volatility:.1f}%")
    
    if risk_level == "HIGH" or volatility > 2.5:
        print("   → 고위험 관리 프로세스로 이동")
        return "high_risk"
    else:
        print("   → 일반 위험 관리 프로세스로 이동")
        return "low_risk"


async def high_risk_management(state: TradingState) -> TradingState:
    """
    고위험 관리 프로세스
    """
    print("\n⚠️ 고위험 관리 프로세스 실행 중...")
    
    # 위험 조정
    original_position = state["analysis_result"]["position_size"]
    adjusted_position = max(original_position * 0.5, 10)  # 포지션 50% 축소 (최소 10%)
    
    state["analysis_result"]["position_size"] = adjusted_position
    state["analysis_result"]["risk_adjustment"] = "고위험으로 인한 포지션 축소"
    
    print(f"   포지션 크기 조정: {original_position}% → {adjusted_position}%")
    print(f"   추가 모니터링 필요")
    
    state["messages"].append(
        AIMessage(content=f"고위험 관리 적용: 포지션 {original_position}%에서 {adjusted_position}%로 축소")
    )
    
    await asyncio.sleep(1)
    return state


async def low_risk_management(state: TradingState) -> TradingState:
    """
    일반 위험 관리 프로세스
    """
    print("\n✅ 일반 위험 관리 프로세스 실행 중...")
    
    # 일반적인 위험 점검
    state["analysis_result"]["risk_adjustment"] = "정상 위험 수준, 원래 전략 유지"
    
    print("   위험 수준 정상")
    print("   원래 전략 유지")
    
    state["messages"].append(
        AIMessage(content="일반 위험 관리: 정상 위험 수준으로 원래 전략 유지")
    )
    
    await asyncio.sleep(1)
    return state


async def create_conditional_workflow():
    """
    조건부 라우팅 워크플로우 생성
    
    시장 상황과 위험 수준에 따라 다른 경로로 분기하는 워크플로우를 만듭니다.
    """
    # StateGraph 객체 생성
    workflow = StateGraph(TradingState)
    
    # 노드들을 워크플로우에 추가
    workflow.add_node("collect_data", collect_market_data)
    workflow.add_node("bull_analysis", bull_market_analysis)
    workflow.add_node("bear_analysis", bear_market_analysis)
    workflow.add_node("neutral_analysis", neutral_market_analysis)
    workflow.add_node("high_risk", high_risk_management)
    workflow.add_node("low_risk", low_risk_management)
    
    # 시작점 설정
    workflow.set_entry_point("collect_data")
    
    # 첫 번째 조건부 라우팅: 시장 상황에 따른 분석 경로
    workflow.add_conditional_edges(
        "collect_data",
        decide_analysis_path,
        {
            "bull_analysis": "bull_analysis",
            "bear_analysis": "bear_analysis", 
            "neutral_analysis": "neutral_analysis"
        }
    )
    
    # 두 번째 조건부 라우팅: 위험 수준에 따른 관리 경로
    workflow.add_conditional_edges(
        "bull_analysis",
        decide_risk_management_path,
        {
            "high_risk": "high_risk",
            "low_risk": "low_risk"
        }
    )
    
    workflow.add_conditional_edges(
        "bear_analysis",
        decide_risk_management_path,
        {
            "high_risk": "high_risk",
            "low_risk": "low_risk"
        }
    )
    
    workflow.add_conditional_edges(
        "neutral_analysis",
        decide_risk_management_path,
        {
            "high_risk": "high_risk",
            "low_risk": "low_risk"
        }
    )
    
    # 모든 위험 관리 경로는 종료로 이동
    workflow.add_edge("high_risk", END)
    workflow.add_edge("low_risk", END)
    
    # 워크플로우 컴파일
    return workflow.compile()


async def main():
    """메인 실행 함수"""
    print_section("LangGraph 2.2: 조건부 라우팅 - LG전자 조건부 매매")
    
    try:
        # 워크플로우 생성
        print("\n🔧 조건부 라우팅 워크플로우 생성 중...")
        app = await create_conditional_workflow()
        
        # 초기 상태 설정
        initial_state = {
            "messages": [HumanMessage(content="LG전자 주식의 조건부 매매 분석을 해주세요.")],
            "symbol": "",
            "current_price": 0,
            "market_condition": "",
            "volatility": 0,
            "analysis_result": {},
            "trading_signal": "",
            "risk_level": ""
        }
        
        print("✅ 워크플로우 생성 완료")
        print("\n🚀 조건부 분석 시작...")
        
        # 워크플로우 실행
        final_state = await app.ainvoke(initial_state)
        
        # 최종 결과 출력
        print_section("📋 조건부 매매 분석 결과")
        print(f"종목: LG전자 ({final_state['symbol']})")
        print(f"현재 주가: {final_state['current_price']:,}원")
        print(f"시장 상황: {final_state['market_condition']}")
        print(f"변동성: {final_state['volatility']:.1f}%")
        print(f"🎯 매매 신호: {final_state['trading_signal']}")
        print(f"전략: {final_state['analysis_result']['strategy']}")
        print(f"포지션 크기: {final_state['analysis_result']['position_size']}%")
        print(f"위험 조정: {final_state['analysis_result']['risk_adjustment']}")
        
        # 결과를 파일로 저장
        output_dir = Path("./logs")
        output_dir.mkdir(exist_ok=True)
        output_file = output_dir / "lg_conditional_analysis_result.json"
        
        result_data = {
            "symbol": final_state["symbol"],
            "current_price": final_state["current_price"],
            "market_condition": final_state["market_condition"],
            "volatility": final_state["volatility"],
            "trading_signal": final_state["trading_signal"],
            "risk_level": final_state["risk_level"],
            "analysis_result": final_state["analysis_result"],
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
    print("🔀 LangGraph 조건부 라우팅 학습을 시작합니다!")
    print("이 예제는 시장 상황에 따라 다른 분석 경로를 선택하는 과정을 보여줍니다.")
    asyncio.run(main())