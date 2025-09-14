#!/usr/bin/env python3
"""
2.3 Human-in-the-Loop - SK하이닉스 승인 프로세스

LangGraph의 Human-in-the-Loop 기능을 학습하는 예제입니다.
SK하이닉스(000660) 주식 매매 시 사용자 승인을 받는 워크플로우를 구현합니다.

학습 목표:
- LangGraph의 interrupt 기능 이해
- add_node()와 interrupt_before/interrupt_after 사용법
- 사용자 입력을 기다리고 처리하는 방법
- 승인/거부에 따른 다른 처리 로직 구현

실행 전제 조건:
- 대화형 실행 환경 필요 (터미널에서 직접 실행)
"""

import asyncio
import json
from typing import Annotated, TypedDict, Literal
from pathlib import Path
import sys

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langgraph.graph.message import add_messages
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_openai import ChatOpenAI

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


class ApprovalState(TypedDict):
    """
    승인 프로세스 상태를 관리하는 클래스
    
    사용자 승인 요청과 결과를 포함합니다.
    """
    messages: Annotated[list[BaseMessage], add_messages]
    symbol: str  # 분석 종목 코드
    current_price: float  # 현재 주가
    analysis_summary: dict  # 분석 요약
    trade_recommendation: dict  # 매매 추천
    user_approval: str  # 사용자 승인 결과 (approved/rejected/pending)
    execution_result: dict  # 실행 결과


def print_section(title: str):
    """섹션 구분선 출력"""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)


async def analyze_stock(state: ApprovalState) -> ApprovalState:
    """
    1단계: 주식 분석
    
    SK하이닉스의 기본 분석을 수행합니다.
    """
    print("\n📊 1단계: SK하이닉스 분석 수행 중...")
    
    # 모의 분석 데이터
    symbol = "000660"  # SK하이닉스
    current_price = 128000  # 현재 주가 (원)
    
    analysis_summary = {
        "company_name": "SK하이닉스",
        "current_price": current_price,
        "target_price": 145000,
        "analyst_rating": "매수",
        "technical_score": 75,  # 0-100 점수
        "fundamental_score": 80,
        "market_sentiment": "긍정적",
        "key_factors": [
            "메모리 반도체 사이클 회복 기대",
            "AI 수요 증가로 HBM 매출 확대",
            "공급 부족으로 가격 상승 압력",
            "중국 시장 회복 신호"
        ],
        "risk_factors": [
            "중국 정부 정책 변화 리스크",
            "메모리 가격 변동성",
            "환율 변동 영향"
        ]
    }
    
    print(f"   종목: {analysis_summary['company_name']} ({symbol})")
    print(f"   현재 주가: {current_price:,}원")
    print(f"   목표 주가: {analysis_summary['target_price']:,}원")
    print(f"   애널리스트 등급: {analysis_summary['analyst_rating']}")
    print(f"   기술적 점수: {analysis_summary['technical_score']}/100")
    print(f"   기본적 점수: {analysis_summary['fundamental_score']}/100")
    
    # 상태 업데이트
    state["symbol"] = symbol
    state["current_price"] = current_price
    state["analysis_summary"] = analysis_summary
    state["messages"].append(
        AIMessage(content=f"SK하이닉스({symbol}) 분석 완료. 목표가: {analysis_summary['target_price']:,}원")
    )
    
    await asyncio.sleep(1)
    return state


async def generate_trade_recommendation(state: ApprovalState) -> ApprovalState:
    """
    2단계: 매매 추천 생성
    
    분석 결과를 바탕으로 구체적인 매매 추천을 생성합니다.
    """
    print("\n🎯 2단계: 매매 추천 생성 중...")
    
    analysis = state["analysis_summary"]
    current_price = state["current_price"]
    
    # 종합 점수 계산
    total_score = (analysis["technical_score"] + analysis["fundamental_score"]) / 2
    
    # 매매 추천 생성
    if total_score >= 80:
        action = "매수"
        urgency = "높음"
        position_size = 60
    elif total_score >= 70:
        action = "매수"
        urgency = "보통"
        position_size = 40
    elif total_score >= 60:
        action = "보유"
        urgency = "낮음"
        position_size = 20
    else:
        action = "매도"
        urgency = "높음"
        position_size = 0
    
    trade_recommendation = {
        "action": action,
        "urgency": urgency,
        "position_size": position_size,  # 포트폴리오 대비 비중 (%)
        "quantity": 100,  # 주수
        "entry_price": current_price,
        "target_price": analysis["target_price"],
        "stop_loss": current_price * 0.92,  # 8% 손절
        "expected_return": ((analysis["target_price"] - current_price) / current_price) * 100,
        "risk_level": "중간",
        "time_horizon": "3-6개월",
        "reasoning": f"종합 점수 {total_score:.1f}/100점으로 {action} 추천"
    }
    
    print(f"   📋 매매 추천 내용:")
    print(f"      행동: {trade_recommendation['action']}")
    print(f"      긴급도: {trade_recommendation['urgency']}")
    print(f"      포지션 크기: {trade_recommendation['position_size']}%")
    print(f"      추천 수량: {trade_recommendation['quantity']}주")
    print(f"      진입가: {trade_recommendation['entry_price']:,}원")
    print(f"      목표가: {trade_recommendation['target_price']:,}원")
    print(f"      손절가: {trade_recommendation['stop_loss']:,.0f}원")
    print(f"      예상 수익률: {trade_recommendation['expected_return']:+.1f}%")
    
    # 상태 업데이트
    state["trade_recommendation"] = trade_recommendation
    state["user_approval"] = "pending"  # 승인 대기 상태
    state["messages"].append(
        AIMessage(content=f"매매 추천 생성 완료: {action} {trade_recommendation['quantity']}주")
    )
    
    await asyncio.sleep(1)
    return state


async def request_user_approval(state: ApprovalState) -> ApprovalState:
    """
    3단계: 사용자 승인 요청
    
    이 노드는 interrupt로 설정되어 사용자 입력을 기다립니다.
    """
    print_section("🤔 사용자 승인 요청")
    
    analysis = state["analysis_summary"]
    recommendation = state["trade_recommendation"]
    
    print(f"📊 분석 요약:")
    print(f"   종목: {analysis['company_name']} ({state['symbol']})")
    print(f"   현재가: {state['current_price']:,}원")
    print(f"   목표가: {analysis['target_price']:,}원")
    print(f"   예상 수익률: {recommendation['expected_return']:+.1f}%")
    print(f"   \n🎯 매매 추천:")
    print(f"   행동: {recommendation['action']}")
    print(f"   수량: {recommendation['quantity']}주")
    print(f"   포지션 비중: {recommendation['position_size']}%")
    print(f"   위험 수준: {recommendation['risk_level']}")
    print(f"   \n📈 핵심 호재:")
    for factor in analysis['key_factors'][:2]:  # 주요 2개만 표시
        print(f"   • {factor}")
    
    print(f"\n⚠️  주요 리스크:")
    for risk in analysis['risk_factors'][:2]:  # 주요 2개만 표시  
        print(f"   • {risk}")
    
    # 사용자 입력 대기 (이 노드에서 interrupt가 발생함)
    state["messages"].append(
        AIMessage(content="사용자 승인을 기다리는 중입니다...")
    )
    
    return state


def process_user_decision(state: ApprovalState) -> ApprovalState:
    """
    사용자 입력 처리 함수
    
    실제로는 resume할 때 config에서 사용자 입력을 받아 처리합니다.
    """
    # 이 예제에서는 시뮬레이션을 위해 기본적으로 승인으로 설정
    if state.get("user_approval") == "pending":
        state["user_approval"] = "approved"  # 실제로는 사용자 입력을 받음
    
    return state


async def execute_approved_trade(state: ApprovalState) -> ApprovalState:
    """
    4단계: 승인된 매매 실행
    
    사용자가 승인한 경우에만 실행됩니다.
    """
    print("\n✅ 4단계: 승인된 매매 실행 중...")
    
    recommendation = state["trade_recommendation"]
    
    # 모의 매매 실행
    execution_result = {
        "status": "executed",
        "symbol": state["symbol"],
        "action": recommendation["action"],
        "quantity": recommendation["quantity"],
        "execution_price": state["current_price"] + 500,  # 약간의 슬리피지 반영
        "execution_time": "2024-01-15 14:30:25",
        "order_id": "ORD20240115143025001",
        "commission": 2500,  # 수수료
        "total_amount": (state["current_price"] + 500) * recommendation["quantity"] + 2500
    }
    
    print(f"   📋 매매 체결 내역:")
    print(f"      종목: {execution_result['symbol']}")
    print(f"      행동: {execution_result['action']}")
    print(f"      수량: {execution_result['quantity']}주")
    print(f"      체결가: {execution_result['execution_price']:,}원")
    print(f"      체결시간: {execution_result['execution_time']}")
    print(f"      주문번호: {execution_result['order_id']}")
    print(f"      총 매매대금: {execution_result['total_amount']:,}원")
    
    # 상태 업데이트
    state["execution_result"] = execution_result
    state["messages"].append(
        AIMessage(content=f"매매 실행 완료: {execution_result['action']} {execution_result['quantity']}주 @ {execution_result['execution_price']:,}원")
    )
    
    await asyncio.sleep(1)
    return state


async def handle_rejected_trade(state: ApprovalState) -> ApprovalState:
    """
    거부된 매매 처리
    
    사용자가 거부한 경우 실행됩니다.
    """
    print("\n❌ 매매 요청이 거부되었습니다.")
    
    execution_result = {
        "status": "rejected",
        "reason": "사용자 승인 거부",
        "symbol": state["symbol"],
        "rejected_time": "2024-01-15 14:30:25"
    }
    
    print(f"   거부 사유: {execution_result['reason']}")
    print(f"   거부 시간: {execution_result['rejected_time']}")
    
    # 상태 업데이트
    state["execution_result"] = execution_result
    state["messages"].append(
        AIMessage(content="사용자가 매매를 거부했습니다. 주문을 취소합니다.")
    )
    
    return state


def decide_execution_path(state: ApprovalState) -> Literal["execute", "reject"]:
    """
    실행 경로 결정
    
    사용자 승인 여부에 따라 실행 또는 거부 경로로 분기합니다.
    """
    approval = state.get("user_approval", "pending")
    
    print(f"\n🔀 실행 경로 결정: 승인 상태 '{approval}'")
    
    if approval == "approved":
        print("   → 매매 실행 경로로 이동")
        return "execute"
    else:
        print("   → 매매 거부 처리 경로로 이동")
        return "reject"


async def create_human_in_loop_workflow():
    """
    Human-in-the-Loop 워크플로우 생성
    
    사용자 승인이 필요한 워크플로우를 만듭니다.
    """
    # StateGraph 객체 생성 (체크포인터 추가 - interrupt 지원용)
    workflow = StateGraph(ApprovalState)
    
    # 노드들을 워크플로우에 추가
    workflow.add_node("analyze", analyze_stock)
    workflow.add_node("recommend", generate_trade_recommendation)
    workflow.add_node("approval", request_user_approval)
    workflow.add_node("execute", execute_approved_trade)
    workflow.add_node("reject", handle_rejected_trade)
    
    # 시작점 설정
    workflow.set_entry_point("analyze")
    
    # 순차적 연결
    workflow.add_edge("analyze", "recommend")
    workflow.add_edge("recommend", "approval")
    
    # 승인 단계 후 조건부 라우팅
    workflow.add_conditional_edges(
        "approval",
        decide_execution_path,
        {
            "execute": "execute",
            "reject": "reject"
        }
    )
    
    # 종료 지점
    workflow.add_edge("execute", END)
    workflow.add_edge("reject", END)
    
    # 체크포인터와 함께 컴파일 (interrupt 지원)
    memory = MemorySaver()
    return workflow.compile(checkpointer=memory, interrupt_before=["approval"])


async def main():
    """메인 실행 함수"""
    print_section("LangGraph 2.3: Human-in-the-Loop - SK하이닉스 승인 프로세스")
    
    try:
        # 워크플로우 생성
        print("\n🔧 Human-in-the-Loop 워크플로우 생성 중...")
        app = await create_human_in_loop_workflow()
        
        # 초기 상태와 config 설정
        initial_state = {
            "messages": [HumanMessage(content="SK하이닉스 주식 매매를 검토해주세요.")],
            "symbol": "",
            "current_price": 0,
            "analysis_summary": {},
            "trade_recommendation": {},
            "user_approval": "pending",
            "execution_result": {}
        }
        
        # 스레드 config (체크포인터용)
        config = {"configurable": {"thread_id": "user_approval_demo"}}
        
        print("✅ 워크플로우 생성 완료")
        print("\n🚀 분석 및 추천 단계 시작...")
        
        # 첫 번째 실행 (승인 요청까지)
        result = await app.ainvoke(initial_state, config)
        
        # 승인 단계에서 중단됨 - 사용자 입력 시뮬레이션
        print_section("💭 승인 결정 시뮬레이션")
        print("실제 환경에서는 여기서 사용자 입력을 기다립니다.")
        print("이 데모에서는 자동으로 승인하겠습니다.")
        
        # 사용자 승인 시뮬레이션 (실제로는 사용자 입력 받음)
        user_decision = "approved"  # 또는 "rejected"
        result["user_approval"] = user_decision
        
        print(f"🤖 시뮬레이션 결정: {user_decision}")
        
        # 두 번째 실행 (승인 처리 후 계속)
        print_section("🔄 승인 후 처리 계속...")
        final_result = await app.ainvoke(result, config)
        
        # 최종 결과 출력
        print_section("📋 Human-in-the-Loop 처리 결과")
        
        if final_result.get("execution_result"):
            execution = final_result["execution_result"]
            if execution["status"] == "executed":
                print(f"✅ 매매 성공적으로 실행됨")
                print(f"   종목: {execution['symbol']}")
                print(f"   행동: {execution['action']}")
                print(f"   수량: {execution['quantity']}주")
                print(f"   체결가: {execution['execution_price']:,}원")
                print(f"   주문번호: {execution['order_id']}")
            else:
                print(f"❌ 매매 거부됨: {execution['reason']}")
        
        # 결과를 파일로 저장
        output_dir = Path("./logs")
        output_dir.mkdir(exist_ok=True)
        output_file = output_dir / "sk_hynix_approval_result.json"
        
        result_data = {
            "symbol": final_result["symbol"],
            "current_price": final_result["current_price"],
            "analysis_summary": final_result["analysis_summary"],
            "trade_recommendation": final_result["trade_recommendation"],
            "user_approval": final_result["user_approval"],
            "execution_result": final_result["execution_result"],
            "messages": [msg.content for msg in final_result["messages"]]
        }
        
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(result_data, f, ensure_ascii=False, indent=2)
        
        print(f"\n💾 결과가 {output_file}에 저장되었습니다.")
        
    except Exception as e:
        print(f"\n❌ 실행 중 오류 발생: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("🤔 LangGraph Human-in-the-Loop 학습을 시작합니다!")
    print("이 예제는 사용자 승인을 받는 매매 시스템을 보여줍니다.")
    asyncio.run(main())