#!/usr/bin/env python3
"""
2.5 에러 처리 - 카카오 리스크 관리

LangGraph의 에러 처리와 복구 메커니즘을 학습하는 예제입니다.
카카오(035720) 주식 분석 중 발생할 수 있는 다양한 에러 상황을 처리하는 워크플로우를 구현합니다.

학습 목표:
- 다양한 에러 상황 시뮬레이션과 처리
- 재시도 로직 구현
- 부분 실패 처리 방법
- 우아한 실패(Graceful Failure) 구현
- 에러 복구 메커니즘과 대체 경로

에러 시나리오:
- 네트워크 타임아웃
- 데이터 파싱 에러
- API 호출 실패
- 부분 데이터 누락
"""

import asyncio
import json
import random
from typing import Annotated, TypedDict, Dict, Any, Optional
from pathlib import Path
import sys
from datetime import datetime
from enum import Enum

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langgraph.graph.message import add_messages
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


class ErrorType(Enum):
    """에러 타입 정의"""
    NETWORK_TIMEOUT = "network_timeout"
    API_ERROR = "api_error"
    DATA_PARSING_ERROR = "data_parsing_error"
    PARTIAL_DATA_ERROR = "partial_data_error"
    SERVICE_UNAVAILABLE = "service_unavailable"


class ErrorHandlingState(TypedDict):
    """
    에러 처리 상태를 관리하는 클래스
    
    각 단계별 에러 발생과 복구 상황을 추적합니다.
    """
    messages: Annotated[list[BaseMessage], add_messages]
    symbol: str  # 분석 종목 코드
    company_name: str  # 회사명
    current_price: Optional[float]  # 현재 주가
    
    # 분석 결과 (에러로 인해 부분적일 수 있음)
    price_data: Optional[Dict[str, Any]]  # 주가 데이터
    financial_data: Optional[Dict[str, Any]]  # 재무 데이터
    news_data: Optional[Dict[str, Any]]  # 뉴스 데이터
    
    # 에러 추적
    errors_encountered: list[Dict[str, Any]]  # 발생한 에러들
    retry_attempts: Dict[str, int]  # 재시도 횟수
    fallback_used: Dict[str, bool]  # 대체 방법 사용 여부
    
    # 최종 결과
    analysis_result: Optional[Dict[str, Any]]  # 분석 결과 (부분적일 수 있음)
    confidence_level: float  # 신뢰도 (0-1, 에러로 인해 감소 가능)


def print_section(title: str):
    """섹션 구분선 출력"""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)


def simulate_error(error_probability: float = 0.4, error_type: ErrorType = None) -> Optional[Exception]:
    """
    에러 시뮬레이션 함수
    
    Args:
        error_probability: 에러 발생 확률 (0.0-1.0)
        error_type: 강제로 발생시킬 에러 타입
    """
    if error_type or random.random() < error_probability:
        if error_type:
            selected_error = error_type
        else:
            selected_error = random.choice(list(ErrorType))
        
        error_messages = {
            ErrorType.NETWORK_TIMEOUT: "네트워크 연결 시간 초과",
            ErrorType.API_ERROR: "API 서버 응답 오류 (HTTP 500)",
            ErrorType.DATA_PARSING_ERROR: "데이터 파싱 중 오류 발생",
            ErrorType.PARTIAL_DATA_ERROR: "일부 데이터만 수신됨",
            ErrorType.SERVICE_UNAVAILABLE: "서비스 일시적으로 사용 불가"
        }
        
        return Exception(f"{selected_error.value}: {error_messages[selected_error]}")
    
    return None


async def initialize_analysis(state: ErrorHandlingState) -> ErrorHandlingState:
    """
    분석 초기화
    """
    print("\n🚀 카카오 에러 처리 분석 초기화 중...")
    
    # 카카오 기본 정보
    symbol = "035720"  # 카카오
    company_name = "카카오"
    
    print(f"   대상 종목: {company_name} ({symbol})")
    print(f"   에러 처리 시나리오 활성화")
    
    # 상태 초기화
    state["symbol"] = symbol
    state["company_name"] = company_name
    state["current_price"] = None
    state["price_data"] = None
    state["financial_data"] = None
    state["news_data"] = None
    state["errors_encountered"] = []
    state["retry_attempts"] = {"price": 0, "financial": 0, "news": 0}
    state["fallback_used"] = {"price": False, "financial": False, "news": False}
    state["analysis_result"] = None
    state["confidence_level"] = 1.0
    
    state["messages"].append(
        AIMessage(content=f"카카오({symbol}) 에러 처리 분석을 시작합니다.")
    )
    
    await asyncio.sleep(0.5)
    return state


async def fetch_price_data_with_retry(state: ErrorHandlingState) -> ErrorHandlingState:
    """
    주가 데이터 수집 (재시도 로직 포함)
    
    최대 3회까지 재시도하며, 실패 시 대체 데이터 사용
    """
    print("\n📈 주가 데이터 수집 중...")
    
    max_retries = 3
    retry_count = state["retry_attempts"]["price"]
    
    while retry_count < max_retries:
        try:
            # 에러 시뮬레이션
            error = simulate_error(0.5)  # 50% 확률로 에러 발생
            if error:
                raise error
            
            # 성공적인 데이터 수집 시뮬레이션
            await asyncio.sleep(1.5)
            
            price_data = {
                "current_price": 45000,
                "day_change": -1200,
                "day_change_percent": -2.6,
                "volume": 1250000,
                "market_cap": 20500000000000,  # 시가총액
                "high_52w": 58000,
                "low_52w": 40000,
                "data_source": "primary",
                "timestamp": datetime.now().isoformat()
            }
            
            print(f"   ✅ 주가 데이터 수집 성공 (시도 {retry_count + 1}회)")
            print(f"   현재가: {price_data['current_price']:,}원")
            print(f"   전일 대비: {price_data['day_change']:+,}원 ({price_data['day_change_percent']:+.1f}%)")
            
            # 상태 업데이트
            state["price_data"] = price_data
            state["current_price"] = price_data["current_price"]
            state["retry_attempts"]["price"] = retry_count + 1
            
            state["messages"].append(
                AIMessage(content=f"주가 데이터 수집 성공 (재시도 {retry_count}회)")
            )
            
            return state
            
        except Exception as e:
            retry_count += 1
            error_info = {
                "step": "price_data",
                "error": str(e),
                "attempt": retry_count,
                "timestamp": datetime.now().isoformat()
            }
            state["errors_encountered"].append(error_info)
            
            print(f"   ❌ 주가 데이터 수집 실패 ({retry_count}회차): {str(e)}")
            
            if retry_count < max_retries:
                print(f"   🔄 {2 ** retry_count}초 후 재시도...")
                await asyncio.sleep(2 ** retry_count)  # 지수 백오프
            
    # 모든 재시도 실패 - 대체 데이터 사용
    print("   ⚠️ 모든 재시도 실패, 캐시된 데이터 사용")
    
    fallback_price_data = {
        "current_price": 44500,  # 캐시된 가격 (약간 오래됨)
        "day_change": None,  # 일부 데이터 누락
        "day_change_percent": None,
        "volume": None,
        "market_cap": 20000000000000,  # 추정값
        "high_52w": 58000,
        "low_52w": 40000,
        "data_source": "fallback_cache",
        "timestamp": datetime.now().isoformat(),
        "warning": "캐시된 데이터, 정확성 제한됨"
    }
    
    # 신뢰도 감소
    state["confidence_level"] *= 0.8  # 20% 감소
    state["price_data"] = fallback_price_data
    state["current_price"] = fallback_price_data["current_price"]
    state["retry_attempts"]["price"] = retry_count
    state["fallback_used"]["price"] = True
    
    state["messages"].append(
        AIMessage(content="주가 데이터 수집 실패, 캐시된 데이터 사용 (신뢰도 감소)")
    )
    
    return state


async def fetch_financial_data_with_fallback(state: ErrorHandlingState) -> ErrorHandlingState:
    """
    재무 데이터 수집 (부분 실패 허용)
    
    일부 데이터가 실패해도 가용한 데이터로 분석 진행
    """
    print("\n💰 재무 데이터 수집 중...")
    
    financial_data = {
        "basic_info": None,
        "ratios": None,
        "growth": None,
        "warnings": []
    }
    
    # 기본 정보 수집
    try:
        error = simulate_error(0.3)  # 30% 에러 확률
        if error:
            raise error
        
        await asyncio.sleep(1)
        financial_data["basic_info"] = {
            "revenue": 6800000000000,  # 매출액
            "operating_profit": 450000000000,  # 영업이익
            "net_profit": 380000000000,  # 순이익
            "total_assets": 18500000000000  # 총자산
        }
        print("   ✅ 기본 재무정보 수집 성공")
        
    except Exception as e:
        error_info = {
            "step": "financial_basic",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }
        state["errors_encountered"].append(error_info)
        financial_data["warnings"].append("기본 재무정보 수집 실패")
        print(f"   ❌ 기본 재무정보 수집 실패: {str(e)}")
    
    # 재무비율 수집
    try:
        error = simulate_error(0.4)  # 40% 에러 확률
        if error:
            raise error
        
        await asyncio.sleep(0.8)
        financial_data["ratios"] = {
            "per": 22.5,
            "pbr": 1.8,
            "roe": 8.2,
            "debt_ratio": 45.3
        }
        print("   ✅ 재무비율 수집 성공")
        
    except Exception as e:
        error_info = {
            "step": "financial_ratios", 
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }
        state["errors_encountered"].append(error_info)
        financial_data["warnings"].append("재무비율 데이터 수집 실패")
        print(f"   ❌ 재무비율 수집 실패: {str(e)}")
    
    # 성장성 지표 수집
    try:
        error = simulate_error(0.25)  # 25% 에러 확률
        if error:
            raise error
        
        await asyncio.sleep(1.2)
        financial_data["growth"] = {
            "revenue_growth": 15.8,
            "profit_growth": 12.3,
            "eps_growth": 11.7
        }
        print("   ✅ 성장성 지표 수집 성공")
        
    except Exception as e:
        error_info = {
            "step": "financial_growth",
            "error": str(e), 
            "timestamp": datetime.now().isoformat()
        }
        state["errors_encountered"].append(error_info)
        financial_data["warnings"].append("성장성 지표 수집 실패")
        print(f"   ❌ 성장성 지표 수집 실패: {str(e)}")
    
    # 수집된 데이터 품질 평가
    success_count = sum(1 for key in ["basic_info", "ratios", "growth"] if financial_data[key] is not None)
    data_quality = success_count / 3
    
    if data_quality < 0.5:
        print("   ⚠️ 재무 데이터 품질 불량 (50% 미만 수집)")
        state["confidence_level"] *= 0.6
        state["fallback_used"]["financial"] = True
    elif data_quality < 1.0:
        print(f"   ⚠️ 재무 데이터 부분 수집 ({data_quality*100:.0f}%)")
        state["confidence_level"] *= 0.9
    else:
        print("   ✅ 재무 데이터 완전 수집")
    
    state["financial_data"] = financial_data
    state["messages"].append(
        AIMessage(content=f"재무 데이터 수집 완료 (품질: {data_quality*100:.0f}%)")
    )
    
    return state


async def fetch_news_data_with_circuit_breaker(state: ErrorHandlingState) -> ErrorHandlingState:
    """
    뉴스 데이터 수집 (서킷 브레이커 패턴)
    
    연속적인 실패 시 서킷을 열어 추가 요청 방지
    """
    print("\n📰 뉴스 데이터 수집 중...")
    
    # 서킷 브레이커 시뮬레이션
    consecutive_failures = random.randint(0, 4)  # 0-4번 연속 실패
    
    if consecutive_failures >= 3:
        print("   🚫 서킷 브레이커 열림 - 뉴스 서비스 일시 차단")
        print("   대체 뉴스 소스 사용")
        
        # 대체 뉴스 데이터 (제한된 정보)
        news_data = {
            "total_articles": 5,  # 대체 소스는 적은 기사
            "sentiment_score": 0.6,  # 중립적 감성
            "key_topics": ["일반 시장 동향"],
            "data_source": "fallback_news",
            "warning": "주요 뉴스 서비스 이용 불가로 제한된 정보",
            "timestamp": datetime.now().isoformat()
        }
        
        error_info = {
            "step": "news_data",
            "error": "circuit_breaker_open",
            "timestamp": datetime.now().isoformat()
        }
        state["errors_encountered"].append(error_info)
        state["confidence_level"] *= 0.7
        state["fallback_used"]["news"] = True
        
    else:
        # 정상적인 뉴스 데이터 수집
        try:
            error = simulate_error(0.3)
            if error:
                raise error
            
            await asyncio.sleep(2)
            
            news_data = {
                "total_articles": 28,
                "sentiment_score": 0.75,  # 긍정적
                "key_topics": [
                    "카카오톡 비즈니스 확장",
                    "카카오페이 성장",
                    "카카오모빌리티 IPO 준비",
                    "ESG 경영 강화"
                ],
                "positive_articles": 18,
                "negative_articles": 6,
                "neutral_articles": 4,
                "data_source": "primary_news",
                "timestamp": datetime.now().isoformat()
            }
            
            print("   ✅ 뉴스 데이터 수집 성공")
            print(f"   총 기사: {news_data['total_articles']}개")
            print(f"   감성 점수: {news_data['sentiment_score']:.2f} (긍정적)")
            
        except Exception as e:
            error_info = {
                "step": "news_data",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
            state["errors_encountered"].append(error_info)
            
            # 에러 발생 시 최소한의 데이터 제공
            news_data = {
                "total_articles": 0,
                "sentiment_score": 0.5,
                "key_topics": [],
                "data_source": "error_fallback",
                "warning": "뉴스 데이터 수집 실패",
                "timestamp": datetime.now().isoformat()
            }
            
            print(f"   ❌ 뉴스 데이터 수집 실패: {str(e)}")
            state["confidence_level"] *= 0.8
            state["fallback_used"]["news"] = True
    
    state["news_data"] = news_data
    state["messages"].append(
        AIMessage(content=f"뉴스 데이터 수집 완료 (소스: {news_data['data_source']})")
    )
    
    return state


async def analyze_with_partial_data(state: ErrorHandlingState) -> ErrorHandlingState:
    """
    부분 데이터로 분석 수행
    
    수집된 데이터가 불완전해도 가능한 범위에서 분석을 수행합니다.
    """
    print("\n🔍 부분 데이터 기반 분석 수행 중...")
    
    # 데이터 가용성 체크
    available_data = {
        "price": state["price_data"] is not None,
        "financial": state["financial_data"] is not None,
        "news": state["news_data"] is not None
    }
    
    available_count = sum(available_data.values())
    print(f"   가용 데이터: {available_count}/3 ({available_count/3*100:.0f}%)")
    
    # 분석 결과 구성
    analysis_result = {
        "analysis_timestamp": datetime.now().isoformat(),
        "data_completeness": available_count / 3,
        "confidence_level": state["confidence_level"],
        "available_analyses": [],
        "missing_analyses": [],
        "warnings": [],
        "recommendations": []
    }
    
    # 주가 분석
    if available_data["price"]:
        price_data = state["price_data"]
        analysis_result["available_analyses"].append("주가 분석")
        
        if price_data["data_source"] == "fallback_cache":
            analysis_result["warnings"].append("주가 데이터: 캐시된 정보 사용")
        
        # 간단한 주가 분석
        current_price = price_data["current_price"]
        high_52w = price_data["high_52w"]
        low_52w = price_data["low_52w"]
        
        price_position = (current_price - low_52w) / (high_52w - low_52w)
        if price_position > 0.8:
            analysis_result["recommendations"].append("고가권 - 차익 실현 고려")
        elif price_position < 0.2:
            analysis_result["recommendations"].append("저가권 - 매수 기회 검토")
        else:
            analysis_result["recommendations"].append("중간가 - 추가 분석 필요")
    else:
        analysis_result["missing_analyses"].append("주가 분석")
        analysis_result["warnings"].append("주가 데이터 없음 - 가격 분석 불가")
    
    # 재무 분석
    if available_data["financial"]:
        financial_data = state["financial_data"]
        analysis_result["available_analyses"].append("재무 분석")
        
        if financial_data["warnings"]:
            analysis_result["warnings"].extend([f"재무 분석: {w}" for w in financial_data["warnings"]])
        
        # 가용한 재무 데이터로 분석
        if financial_data["ratios"]:
            per = financial_data["ratios"]["per"]
            if per < 20:
                analysis_result["recommendations"].append("PER 적정 수준")
            else:
                analysis_result["recommendations"].append("PER 높은 편 - 성장성 확인 필요")
    else:
        analysis_result["missing_analyses"].append("재무 분석")
    
    # 뉴스 분석
    if available_data["news"]:
        news_data = state["news_data"]
        analysis_result["available_analyses"].append("뉴스 감성 분석")
        
        if "warning" in news_data:
            analysis_result["warnings"].append(f"뉴스 분석: {news_data['warning']}")
        
        sentiment = news_data["sentiment_score"]
        if sentiment > 0.7:
            analysis_result["recommendations"].append("뉴스 감성 긍정적")
        elif sentiment < 0.4:
            analysis_result["recommendations"].append("뉴스 감성 부정적 - 주의 필요")
        else:
            analysis_result["recommendations"].append("뉴스 감성 중립적")
    else:
        analysis_result["missing_analyses"].append("뉴스 감성 분석")
    
    # 전체 투자 의견 (가용한 데이터 기반)
    if available_count >= 2:
        if state["confidence_level"] > 0.8:
            investment_opinion = "매수"
        elif state["confidence_level"] > 0.6:
            investment_opinion = "보유"
        else:
            investment_opinion = "관망"
    else:
        investment_opinion = "데이터 부족으로 판단 보류"
    
    analysis_result["investment_opinion"] = investment_opinion
    
    # 결과 출력
    print(f"   신뢰도: {state['confidence_level']*100:.1f}%")
    print(f"   투자 의견: {investment_opinion}")
    print(f"   경고사항: {len(analysis_result['warnings'])}개")
    
    state["analysis_result"] = analysis_result
    state["messages"].append(
        AIMessage(content=f"부분 데이터 분석 완료: {investment_opinion} (신뢰도: {state['confidence_level']*100:.1f}%)")
    )
    
    await asyncio.sleep(1)
    return state


async def create_error_handling_workflow():
    """
    에러 처리 워크플로우 생성
    
    다양한 에러 상황을 처리하고 복구하는 워크플로우를 만듭니다.
    """
    # StateGraph 객체 생성
    workflow = StateGraph(ErrorHandlingState)
    
    # 노드들을 워크플로우에 추가
    workflow.add_node("initialize", initialize_analysis)
    workflow.add_node("fetch_price", fetch_price_data_with_retry)
    workflow.add_node("fetch_financial", fetch_financial_data_with_fallback)
    workflow.add_node("fetch_news", fetch_news_data_with_circuit_breaker)
    workflow.add_node("analyze", analyze_with_partial_data)
    
    # 시작점 설정
    workflow.set_entry_point("initialize")
    
    # 순차적 실행 (각 단계에서 에러 처리)
    workflow.add_edge("initialize", "fetch_price")
    workflow.add_edge("fetch_price", "fetch_financial")
    workflow.add_edge("fetch_financial", "fetch_news")
    workflow.add_edge("fetch_news", "analyze")
    workflow.add_edge("analyze", END)
    
    # 워크플로우 컴파일
    return workflow.compile()


async def main():
    """메인 실행 함수"""
    print_section("LangGraph 2.5: 에러 처리 - 카카오 리스크 관리")
    
    try:
        # 워크플로우 생성
        print("\n🔧 에러 처리 워크플로우 생성 중...")
        app = await create_error_handling_workflow()
        
        # 초기 상태 설정
        initial_state = {
            "messages": [HumanMessage(content="카카오 주식 분석 시 에러 처리를 시연해주세요.")],
            "symbol": "",
            "company_name": "",
            "current_price": None,
            "price_data": None,
            "financial_data": None,
            "news_data": None,
            "errors_encountered": [],
            "retry_attempts": {"price": 0, "financial": 0, "news": 0},
            "fallback_used": {"price": False, "financial": False, "news": False},
            "analysis_result": None,
            "confidence_level": 1.0
        }
        
        print("✅ 워크플로우 생성 완료")
        print("\n🚀 에러 처리 시나리오 실행...")
        print("   ⚠️ 의도적으로 에러가 발생할 수 있습니다")
        print("   🔄 재시도 및 복구 메커니즘이 동작합니다")
        
        # 워크플로우 실행
        final_state = await app.ainvoke(initial_state)
        
        # 최종 결과 출력
        print_section("📋 에러 처리 결과 보고서")
        
        # 에러 발생 현황
        errors = final_state["errors_encountered"]
        print(f"🚨 발생한 에러: {len(errors)}개")
        if errors:
            for i, error in enumerate(errors, 1):
                print(f"   {i}. [{error['step']}] {error['error']}")
        
        # 재시도 현황
        retries = final_state["retry_attempts"]
        print(f"\n🔄 재시도 현황:")
        for step, count in retries.items():
            print(f"   {step}: {count}회 시도")
        
        # 대체 방법 사용 현황
        fallbacks = final_state["fallback_used"]
        fallback_count = sum(fallbacks.values())
        print(f"\n🛡️ 대체 방법 사용: {fallback_count}개 단계")
        if fallback_count > 0:
            for step, used in fallbacks.items():
                if used:
                    print(f"   {step}: 대체 데이터/방법 사용")
        
        # 분석 결과
        if final_state["analysis_result"]:
            result = final_state["analysis_result"]
            print(f"\n📊 분석 결과:")
            print(f"   데이터 완전성: {result['data_completeness']*100:.0f}%")
            print(f"   분석 신뢰도: {result['confidence_level']*100:.1f}%")
            print(f"   투자 의견: {result['investment_opinion']}")
            
            print(f"\n✅ 수행된 분석:")
            for analysis in result['available_analyses']:
                print(f"   • {analysis}")
            
            if result['missing_analyses']:
                print(f"\n❌ 누락된 분석:")
                for analysis in result['missing_analyses']:
                    print(f"   • {analysis}")
            
            if result['warnings']:
                print(f"\n⚠️ 주의사항:")
                for warning in result['warnings']:
                    print(f"   • {warning}")
        
        # 결과를 파일로 저장
        output_dir = Path("./logs")
        output_dir.mkdir(exist_ok=True)
        output_file = output_dir / "kakao_error_handling_result.json"
        
        result_data = {
            "symbol": final_state["symbol"],
            "company_name": final_state["company_name"],
            "current_price": final_state["current_price"],
            "price_data": final_state["price_data"],
            "financial_data": final_state["financial_data"],
            "news_data": final_state["news_data"],
            "errors_encountered": final_state["errors_encountered"],
            "retry_attempts": final_state["retry_attempts"],
            "fallback_used": final_state["fallback_used"],
            "analysis_result": final_state["analysis_result"],
            "confidence_level": final_state["confidence_level"],
            "messages": [msg.content for msg in final_state["messages"]]
        }
        
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(result_data, f, ensure_ascii=False, indent=2)
        
        print(f"\n💾 결과가 {output_file}에 저장되었습니다.")
        
    except Exception as e:
        print(f"\n❌ 실행 중 복구 불가능한 오류 발생: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("⚠️ LangGraph 에러 처리 학습을 시작합니다!")
    print("이 예제는 다양한 에러 상황과 복구 메커니즘을 보여줍니다.")
    asyncio.run(main())