#!/usr/bin/env python3
"""
2.4 멀티 도구 협업 - NAVER 종합 분석

LangGraph의 멀티 도구 협업을 학습하는 예제입니다.
NAVER(035420) 주식을 여러 분석 도구를 병렬로 사용하여 종합 분석하는 워크플로우를 구현합니다.

학습 목표:
- 여러 도구를 병렬로 실행하는 방법 학습
- 도구 간 데이터 공유와 결과 통합 이해
- 복잡한 분석 파이프라인 구성
- 도구 실행 순서와 의존성 관리

도구별 역할:
- Technical Analyzer: 기술적 분석
- News Analyzer: 뉴스 감성 분석  
- Financial Analyzer: 재무 분석
- Market Analyzer: 시장 분석
"""

import asyncio
import json
from typing import Annotated, TypedDict, Dict, Any
from pathlib import Path
import sys
from datetime import datetime

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langgraph.graph.message import add_messages
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


class MultiToolState(TypedDict):
    """
    멀티 도구 협업 상태를 관리하는 클래스
    
    여러 도구의 분석 결과를 수집하고 통합합니다.
    """
    messages: Annotated[list[BaseMessage], add_messages]
    symbol: str  # 분석 종목 코드
    company_name: str  # 회사명
    current_price: float  # 현재 주가
    
    # 각 도구별 분석 결과
    technical_analysis: Dict[str, Any]  # 기술적 분석 결과
    news_analysis: Dict[str, Any]  # 뉴스 감성 분석 결과
    financial_analysis: Dict[str, Any]  # 재무 분석 결과
    market_analysis: Dict[str, Any]  # 시장 분석 결과
    
    # 통합 결과
    integrated_analysis: Dict[str, Any]  # 종합 분석 결과
    final_score: float  # 최종 투자 점수 (0-100)
    investment_recommendation: str  # 투자 추천


def print_section(title: str):
    """섹션 구분선 출력"""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)


async def initialize_analysis(state: MultiToolState) -> MultiToolState:
    """
    분석 초기화
    
    NAVER의 기본 정보를 설정하고 각 도구 분석을 준비합니다.
    """
    print("\n🚀 분석 초기화 중...")
    
    # NAVER 기본 정보
    symbol = "035420"  # NAVER
    company_name = "네이버"
    current_price = 185000  # 현재 주가 (원)
    
    print(f"   대상 종목: {company_name} ({symbol})")
    print(f"   현재 주가: {current_price:,}원")
    print(f"   분석 시작 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 상태 초기화
    state["symbol"] = symbol
    state["company_name"] = company_name
    state["current_price"] = current_price
    state["technical_analysis"] = {}
    state["news_analysis"] = {}
    state["financial_analysis"] = {}
    state["market_analysis"] = {}
    state["integrated_analysis"] = {}
    state["final_score"] = 0.0
    state["investment_recommendation"] = ""
    
    state["messages"].append(
        AIMessage(content=f"네이버({symbol}) 종합 분석을 시작합니다.")
    )
    
    await asyncio.sleep(0.5)
    return state


async def technical_analysis_tool(state: MultiToolState) -> MultiToolState:
    """
    기술적 분석 도구
    
    차트 패턴, 기술적 지표를 분석합니다.
    """
    print("\n📈 기술적 분석 도구 실행 중...")
    
    # 모의 기술적 분석 (실제로는 MCP 서버 호출)
    await asyncio.sleep(2)  # 분석 시간 시뮬레이션
    
    technical_result = {
        "analysis_type": "technical",
        "timestamp": datetime.now().isoformat(),
        "indicators": {
            "rsi": 62.3,  # RSI
            "macd": {"value": 2.4, "signal": "매수"},
            "bollinger_bands": {"position": "중간대", "squeeze": False},
            "moving_averages": {
                "ma_5": 182000,
                "ma_20": 178000,
                "ma_60": 175000
            }
        },
        "chart_patterns": {
            "trend": "상승 추세",
            "pattern": "컵앤핸들",
            "support": 180000,
            "resistance": 190000
        },
        "volume_analysis": {
            "volume_trend": "증가",
            "volume_ratio": 1.35  # 평균 대비
        },
        "technical_score": 72.5,  # 0-100 점수
        "signals": ["골든크로스 형성", "거래량 증가", "상승 추세 지속"],
        "recommendation": "매수"
    }
    
    print(f"   RSI: {technical_result['indicators']['rsi']} (중립)")
    print(f"   MACD 신호: {technical_result['indicators']['macd']['signal']}")
    print(f"   차트 패턴: {technical_result['chart_patterns']['pattern']}")
    print(f"   기술적 점수: {technical_result['technical_score']}/100")
    
    # 상태 업데이트
    state["technical_analysis"] = technical_result
    state["messages"].append(
        AIMessage(content=f"기술적 분석 완료: 점수 {technical_result['technical_score']}/100")
    )
    
    return state


async def news_analysis_tool(state: MultiToolState) -> MultiToolState:
    """
    뉴스 감성 분석 도구
    
    최근 뉴스와 소셜 미디어 감성을 분석합니다.
    """
    print("\n📰 뉴스 감성 분석 도구 실행 중...")
    
    # 모의 뉴스 감성 분석 (실제로는 MCP 서버 호출)
    await asyncio.sleep(2.5)  # 분석 시간 시뮬레이션
    
    news_result = {
        "analysis_type": "news_sentiment",
        "timestamp": datetime.now().isoformat(),
        "news_summary": {
            "total_articles": 45,
            "positive_count": 28,
            "neutral_count": 12,
            "negative_count": 5,
            "sentiment_score": 76.8  # 0-100 (긍정적)
        },
        "key_topics": [
            "AI 플랫폼 확장",
            "웹툰 글로벌 진출",
            "클라우드 사업 성장",
            "검색 광고 회복"
        ],
        "social_sentiment": {
            "twitter_mentions": 1250,
            "positive_ratio": 0.68,
            "engagement_score": 8.2
        },
        "analyst_reports": {
            "buy_count": 12,
            "hold_count": 3,
            "sell_count": 1,
            "average_target": 210000
        },
        "news_score": 76.8,
        "impact_level": "높음",
        "recommendation": "긍정적"
    }
    
    print(f"   뉴스 기사: {news_result['news_summary']['total_articles']}개")
    print(f"   감성 점수: {news_result['news_summary']['sentiment_score']}/100")
    print(f"   주요 토픽: {', '.join(news_result['key_topics'][:2])}")
    print(f"   애널리스트 목표가: {news_result['analyst_reports']['average_target']:,}원")
    
    # 상태 업데이트
    state["news_analysis"] = news_result
    state["messages"].append(
        AIMessage(content=f"뉴스 감성 분석 완료: 감성 점수 {news_result['news_score']}/100")
    )
    
    return state


async def financial_analysis_tool(state: MultiToolState) -> MultiToolState:
    """
    재무 분석 도구
    
    재무제표와 재무 비율을 분석합니다.
    """
    print("\n💰 재무 분석 도구 실행 중...")
    
    # 모의 재무 분석 (실제로는 MCP 서버 호출)
    await asyncio.sleep(1.8)  # 분석 시간 시뮬레이션
    
    financial_result = {
        "analysis_type": "financial",
        "timestamp": datetime.now().isoformat(),
        "financial_ratios": {
            "per": 15.2,  # 주가수익비율
            "pbr": 2.1,   # 주가순자산비율
            "roe": 11.5,  # 자기자본이익률
            "roa": 8.3,   # 총자산이익률
            "debt_ratio": 22.1,  # 부채비율
            "current_ratio": 2.8  # 유동비율
        },
        "growth_metrics": {
            "revenue_growth_yoy": 12.4,  # 매출 성장률 (전년 동기)
            "profit_growth_yoy": 18.7,   # 순이익 성장률
            "eps_growth": 16.2           # 주당순이익 성장률
        },
        "profitability": {
            "gross_margin": 23.5,    # 매출총이익률
            "operating_margin": 15.8, # 영업이익률
            "net_margin": 12.1       # 순이익률
        },
        "business_segments": {
            "search_platform": {"revenue_ratio": 0.45, "growth": 8.2},
            "commerce": {"revenue_ratio": 0.28, "growth": 15.3},
            "fintech": {"revenue_ratio": 0.15, "growth": 22.1},
            "content": {"revenue_ratio": 0.12, "growth": 35.8}
        },
        "financial_score": 68.5,
        "financial_health": "양호",
        "recommendation": "매수"
    }
    
    print(f"   PER: {financial_result['financial_ratios']['per']} (적정)")
    print(f"   ROE: {financial_result['financial_ratios']['roe']}% (우수)")
    print(f"   매출 성장률: {financial_result['growth_metrics']['revenue_growth_yoy']}%")
    print(f"   재무 점수: {financial_result['financial_score']}/100")
    
    # 상태 업데이트
    state["financial_analysis"] = financial_result
    state["messages"].append(
        AIMessage(content=f"재무 분석 완료: 재무 점수 {financial_result['financial_score']}/100")
    )
    
    return state


async def market_analysis_tool(state: MultiToolState) -> MultiToolState:
    """
    시장 분석 도구
    
    시장 상황과 업종 분석을 수행합니다.
    """
    print("\n🌐 시장 분석 도구 실행 중...")
    
    # 모의 시장 분석 (실제로는 MCP 서버 호출)
    await asyncio.sleep(2.2)  # 분석 시간 시뮬레이션
    
    market_result = {
        "analysis_type": "market",
        "timestamp": datetime.now().isoformat(),
        "market_condition": {
            "kospi": {"value": 2580, "change": 1.2},
            "kosdaq": {"value": 850, "change": 0.8},
            "sector_performance": {
                "internet": 2.1,    # 인터넷업종 수익률
                "platform": 1.8,    # 플랫폼업종 수익률
                "technology": 1.5   # 기술업종 수익률
            }
        },
        "industry_analysis": {
            "industry": "인터넷·게임",
            "market_size": "대형",
            "competition_level": "높음",
            "growth_outlook": "긍정적",
            "key_competitors": ["카카오", "쿠팡", "와이지엔터테인먼트"],
            "market_share": 0.35  # 시장 점유율
        },
        "macro_factors": {
            "digital_transformation": "가속화",
            "ai_adoption": "확산",
            "regulatory_risk": "낮음",
            "global_expansion": "활발"
        },
        "valuation": {
            "sector_average_per": 18.5,
            "relative_valuation": "할인",
            "target_multiple": 20.0
        },
        "market_score": 74.2,
        "market_outlook": "긍정적",
        "recommendation": "매수"
    }
    
    print(f"   업종: {market_result['industry_analysis']['industry']}")
    print(f"   시장 점유율: {market_result['industry_analysis']['market_share']*100:.1f}%")
    print(f"   업종 평균 PER: {market_result['valuation']['sector_average_per']}")
    print(f"   시장 점수: {market_result['market_score']}/100")
    
    # 상태 업데이트
    state["market_analysis"] = market_result
    state["messages"].append(
        AIMessage(content=f"시장 분석 완료: 시장 점수 {market_result['market_score']}/100")
    )
    
    return state


async def integrate_analysis_results(state: MultiToolState) -> MultiToolState:
    """
    분석 결과 통합
    
    모든 도구의 분석 결과를 종합하여 최종 투자 의견을 생성합니다.
    """
    print("\n🔄 분석 결과 통합 중...")
    
    # 각 도구별 점수 수집
    technical_score = state["technical_analysis"].get("technical_score", 0)
    news_score = state["news_analysis"].get("news_score", 0)
    financial_score = state["financial_analysis"].get("financial_score", 0)
    market_score = state["market_analysis"].get("market_score", 0)
    
    # 가중 평균 계산 (각 분야별 중요도 반영)
    weights = {
        "technical": 0.25,   # 기술적 분석 25%
        "news": 0.20,        # 뉴스 감성 20%
        "financial": 0.30,   # 재무 분석 30%
        "market": 0.25       # 시장 분석 25%
    }
    
    final_score = (
        technical_score * weights["technical"] +
        news_score * weights["news"] +
        financial_score * weights["financial"] +
        market_score * weights["market"]
    )
    
    # 투자 추천 결정
    if final_score >= 80:
        recommendation = "적극 매수 (STRONG BUY)"
        confidence = "매우 높음"
    elif final_score >= 70:
        recommendation = "매수 (BUY)"
        confidence = "높음"
    elif final_score >= 60:
        recommendation = "보유 (HOLD)"
        confidence = "보통"
    elif final_score >= 50:
        recommendation = "관망 (NEUTRAL)"
        confidence = "낮음"
    else:
        recommendation = "매도 (SELL)"
        confidence = "매우 낮음"
    
    # 통합 분석 결과
    integrated_result = {
        "integration_timestamp": datetime.now().isoformat(),
        "individual_scores": {
            "technical": technical_score,
            "news": news_score,
            "financial": financial_score,
            "market": market_score
        },
        "weights_applied": weights,
        "final_score": round(final_score, 1),
        "recommendation": recommendation,
        "confidence_level": confidence,
        "key_strengths": [
            "AI 및 플랫폼 사업 성장",
            "탄탄한 재무 구조",
            "긍정적 시장 전망",
            "기술적 상승 신호"
        ],
        "risk_factors": [
            "높은 경쟁 강도",
            "규제 리스크",
            "중국 시장 의존도"
        ],
        "price_target": {
            "target_price": 210000,
            "upside_potential": ((210000 - state["current_price"]) / state["current_price"]) * 100,
            "time_horizon": "6개월"
        }
    }
    
    print(f"\n📊 통합 분석 결과:")
    print(f"   기술적 분석: {technical_score}/100")
    print(f"   뉴스 감성: {news_score}/100")
    print(f"   재무 분석: {financial_score}/100")
    print(f"   시장 분석: {market_score}/100")
    print(f"   \n🎯 최종 결과:")
    print(f"   종합 점수: {integrated_result['final_score']}/100")
    print(f"   투자 추천: {integrated_result['recommendation']}")
    print(f"   목표 주가: {integrated_result['price_target']['target_price']:,}원")
    print(f"   상승 여력: {integrated_result['price_target']['upside_potential']:+.1f}%")
    
    # 상태 업데이트
    state["integrated_analysis"] = integrated_result
    state["final_score"] = integrated_result["final_score"]
    state["investment_recommendation"] = integrated_result["recommendation"]
    
    state["messages"].append(
        AIMessage(content=f"통합 분석 완료: {integrated_result['recommendation']} (점수: {integrated_result['final_score']}/100)")
    )
    
    await asyncio.sleep(1)
    return state


async def create_multi_tool_workflow():
    """
    멀티 도구 협업 워크플로우 생성
    
    여러 도구를 병렬로 실행하고 결과를 통합하는 워크플로우를 만듭니다.
    """
    # StateGraph 객체 생성
    workflow = StateGraph(MultiToolState)
    
    # 노드들을 워크플로우에 추가
    workflow.add_node("initialize", initialize_analysis)
    workflow.add_node("technical", technical_analysis_tool)
    workflow.add_node("news", news_analysis_tool)
    workflow.add_node("financial", financial_analysis_tool)
    workflow.add_node("market", market_analysis_tool)
    workflow.add_node("integrate", integrate_analysis_results)
    
    # 시작점 설정
    workflow.set_entry_point("initialize")
    
    # 초기화 후 모든 분석 도구를 병렬로 실행
    workflow.add_edge("initialize", "technical")
    workflow.add_edge("initialize", "news")
    workflow.add_edge("initialize", "financial")
    workflow.add_edge("initialize", "market")
    
    # 모든 도구가 완료되면 통합 단계로
    workflow.add_edge("technical", "integrate")
    workflow.add_edge("news", "integrate")
    workflow.add_edge("financial", "integrate")
    workflow.add_edge("market", "integrate")
    
    # 통합 완료 후 종료
    workflow.add_edge("integrate", END)
    
    # 워크플로우 컴파일
    return workflow.compile()


async def main():
    """메인 실행 함수"""
    print_section("LangGraph 2.4: 멀티 도구 협업 - NAVER 종합 분석")
    
    try:
        # 워크플로우 생성
        print("\n🔧 멀티 도구 협업 워크플로우 생성 중...")
        app = await create_multi_tool_workflow()
        
        # 초기 상태 설정
        initial_state = {
            "messages": [HumanMessage(content="NAVER 주식을 멀티 도구로 종합 분석해주세요.")],
            "symbol": "",
            "company_name": "",
            "current_price": 0,
            "technical_analysis": {},
            "news_analysis": {},
            "financial_analysis": {},
            "market_analysis": {},
            "integrated_analysis": {},
            "final_score": 0.0,
            "investment_recommendation": ""
        }
        
        print("✅ 워크플로우 생성 완료")
        print("\n🚀 멀티 도구 협업 분석 시작...")
        print("   📈 기술적 분석 도구")
        print("   📰 뉴스 감성 분석 도구")
        print("   💰 재무 분석 도구") 
        print("   🌐 시장 분석 도구")
        print("\n⏳ 모든 도구를 병렬로 실행 중... (약 5초 소요)")
        
        # 워크플로우 실행
        final_state = await app.ainvoke(initial_state)
        
        # 최종 결과 출력
        print_section("📋 NAVER 종합 분석 결과")
        
        integrated = final_state["integrated_analysis"]
        print(f"🏢 종목: {final_state['company_name']} ({final_state['symbol']})")
        print(f"💰 현재 주가: {final_state['current_price']:,}원")
        print(f"\n📊 분야별 점수:")
        for field, score in integrated["individual_scores"].items():
            field_names = {
                "technical": "기술적 분석",
                "news": "뉴스 감성",
                "financial": "재무 분석", 
                "market": "시장 분석"
            }
            print(f"   {field_names[field]}: {score}/100")
        
        print(f"\n🎯 최종 결과:")
        print(f"   종합 점수: {integrated['final_score']}/100")
        print(f"   투자 추천: {integrated['recommendation']}")
        print(f"   신뢰도: {integrated['confidence_level']}")
        print(f"   목표 주가: {integrated['price_target']['target_price']:,}원")
        print(f"   상승 여력: {integrated['price_target']['upside_potential']:+.1f}%")
        
        print(f"\n💪 주요 강점:")
        for strength in integrated["key_strengths"]:
            print(f"   • {strength}")
        
        print(f"\n⚠️ 리스크 요소:")
        for risk in integrated["risk_factors"]:
            print(f"   • {risk}")
        
        # 결과를 파일로 저장
        output_dir = Path("./logs")
        output_dir.mkdir(exist_ok=True)
        output_file = output_dir / "naver_multi_tool_analysis_result.json"
        
        result_data = {
            "symbol": final_state["symbol"],
            "company_name": final_state["company_name"],
            "current_price": final_state["current_price"],
            "technical_analysis": final_state["technical_analysis"],
            "news_analysis": final_state["news_analysis"],
            "financial_analysis": final_state["financial_analysis"],
            "market_analysis": final_state["market_analysis"],
            "integrated_analysis": final_state["integrated_analysis"],
            "final_score": final_state["final_score"],
            "investment_recommendation": final_state["investment_recommendation"],
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
    print("🛠️ LangGraph 멀티 도구 협업 학습을 시작합니다!")
    print("이 예제는 여러 분석 도구를 병렬로 실행하고 결과를 통합하는 과정을 보여줍니다.")
    asyncio.run(main())