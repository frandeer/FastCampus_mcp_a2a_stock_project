#!/usr/bin/env python3
"""
3.1 HTTP 통신 기본 - 포스코 데이터 교환

Agent-to-Agent HTTP 통신의 기본을 학습하는 예제입니다.
포스코(005490) 주식을 분석하기 위해 두 에이전트가 HTTP로 통신하는 시나리오를 구현합니다.

학습 목표:
- 에이전트 간 HTTP 통신의 기본 개념 이해
- RESTful API를 통한 데이터 교환
- 비동기 에이전트 간 협업
- 통신 에러 처리 및 타임아웃 관리

에이전트 역할:
- Data Collector Agent: 주식 데이터 수집 전문
- Analysis Agent: 수집된 데이터를 분석하여 투자 의견 제시

실행 방법:
1. 터미널 1: python 3_1_http_basic.py --role collector --port 8080
2. 터미널 2: python 3_1_http_basic.py --role analyzer --port 8081
"""

import asyncio
import json
import argparse
from typing import Dict, Any, Optional
from pathlib import Path
import sys
from datetime import datetime
import aiohttp
from aiohttp import web, ClientTimeout
import logging

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DataCollectorAgent:
    """
    데이터 수집 에이전트
    
    포스코의 주식 데이터를 수집하고 HTTP API를 통해 제공합니다.
    """
    
    def __init__(self, port: int = 8080):
        self.port = port
        self.app = web.Application()
        self.setup_routes()
        self.collected_data = {}
        
    def setup_routes(self):
        """API 라우트 설정"""
        self.app.router.add_get('/health', self.health_check)
        self.app.router.add_get('/data/price/{symbol}', self.get_price_data)
        self.app.router.add_get('/data/financial/{symbol}', self.get_financial_data)
        self.app.router.add_get('/data/news/{symbol}', self.get_news_data)
        self.app.router.add_post('/data/request', self.handle_data_request)
    
    async def health_check(self, request):
        """헬스 체크 엔드포인트"""
        return web.json_response({
            "status": "healthy",
            "agent": "DataCollectorAgent",
            "timestamp": datetime.now().isoformat(),
            "port": self.port
        })
    
    async def get_price_data(self, request):
        """주가 데이터 제공"""
        symbol = request.match_info['symbol']
        logger.info(f"주가 데이터 요청 받음: {symbol}")
        
        # 포스코 데이터 시뮬레이션
        if symbol == "005490":
            await asyncio.sleep(1)  # 데이터 수집 시간 시뮬레이션
            
            price_data = {
                "symbol": symbol,
                "company_name": "POSCO홀딩스",
                "current_price": 285000,
                "day_change": +3500,
                "day_change_percent": +1.24,
                "volume": 892000,
                "market_cap": 25800000000000,  # 시가총액
                "52w_high": 315000,
                "52w_low": 230000,
                "trading_value": 254380000000,  # 거래대금
                "timestamp": datetime.now().isoformat(),
                "data_source": "KRX",
                "collection_agent": "DataCollectorAgent"
            }
            
            # 캐시에 저장
            self.collected_data[f"price_{symbol}"] = price_data
            
            logger.info(f"주가 데이터 제공 완료: {symbol} - {price_data['current_price']:,}원")
            return web.json_response(price_data)
        else:
            return web.json_response(
                {"error": "종목 코드를 찾을 수 없습니다", "symbol": symbol},
                status=404
            )
    
    async def get_financial_data(self, request):
        """재무 데이터 제공"""
        symbol = request.match_info['symbol']
        logger.info(f"재무 데이터 요청 받음: {symbol}")
        
        if symbol == "005490":
            await asyncio.sleep(1.5)  # 재무 데이터 수집 시간
            
            financial_data = {
                "symbol": symbol,
                "company_name": "POSCO홀딩스",
                "financial_ratios": {
                    "per": 8.5,  # 주가수익비율
                    "pbr": 0.9,  # 주가순자산비율
                    "roe": 12.3,  # 자기자본이익률
                    "roa": 6.8,   # 총자산이익률
                    "debt_ratio": 35.2,  # 부채비율
                    "current_ratio": 1.85  # 유동비율
                },
                "business_metrics": {
                    "revenue_ttm": 73500000000000,  # 매출액 (TTM)
                    "operating_profit_ttm": 4200000000000,  # 영업이익
                    "net_profit_ttm": 2800000000000,  # 순이익
                    "total_assets": 85600000000000,  # 총자산
                    "shareholders_equity": 42300000000000  # 자기자본
                },
                "industry_info": {
                    "sector": "철강",
                    "industry": "철강제조업",
                    "market_position": "국내 1위",
                    "global_ranking": "세계 6위"
                },
                "timestamp": datetime.now().isoformat(),
                "data_source": "DART",
                "collection_agent": "DataCollectorAgent"
            }
            
            self.collected_data[f"financial_{symbol}"] = financial_data
            
            logger.info(f"재무 데이터 제공 완료: {symbol}")
            return web.json_response(financial_data)
        else:
            return web.json_response(
                {"error": "재무 데이터를 찾을 수 없습니다", "symbol": symbol},
                status=404
            )
    
    async def get_news_data(self, request):
        """뉴스 데이터 제공"""
        symbol = request.match_info['symbol']
        logger.info(f"뉴스 데이터 요청 받음: {symbol}")
        
        if symbol == "005490":
            await asyncio.sleep(2)  # 뉴스 데이터 수집 시간
            
            news_data = {
                "symbol": symbol,
                "company_name": "POSCO홀딩스",
                "news_summary": {
                    "total_articles": 15,
                    "positive_count": 9,
                    "neutral_count": 4,
                    "negative_count": 2,
                    "sentiment_score": 0.72  # 0-1 (긍정적)
                },
                "key_headlines": [
                    "포스코홀딩스, 친환경 철강 기술 개발 가속화",
                    "2차전지 소재 사업 확장으로 신성장동력 확보",
                    "ESG 경영 강화로 글로벌 경쟁력 제고",
                    "중국 철강 시장 회복으로 수출 증가 기대"
                ],
                "market_topics": [
                    "친환경 철강",
                    "2차전지 소재",
                    "ESG 경영",
                    "글로벌 진출"
                ],
                "analyst_mentions": {
                    "buy_recommendations": 8,
                    "hold_recommendations": 3,
                    "sell_recommendations": 1,
                    "average_target_price": 320000
                },
                "timestamp": datetime.now().isoformat(),
                "data_source": "News APIs",
                "collection_agent": "DataCollectorAgent"
            }
            
            self.collected_data[f"news_{symbol}"] = news_data
            
            logger.info(f"뉴스 데이터 제공 완료: {symbol}")
            return web.json_response(news_data)
        else:
            return web.json_response(
                {"error": "뉴스 데이터를 찾을 수 없습니다", "symbol": symbol},
                status=404
            )
    
    async def handle_data_request(self, request):
        """종합 데이터 요청 처리"""
        try:
            request_data = await request.json()
            symbol = request_data.get("symbol")
            data_types = request_data.get("data_types", ["price", "financial", "news"])
            
            logger.info(f"종합 데이터 요청: {symbol}, 타입: {data_types}")
            
            response = {
                "request_id": f"req_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                "symbol": symbol,
                "requested_types": data_types,
                "collected_data": {},
                "collection_status": {},
                "timestamp": datetime.now().isoformat()
            }
            
            # 요청된 데이터 타입별로 수집
            for data_type in data_types:
                try:
                    if data_type == "price":
                        # 내부 메서드 호출로 데이터 수집
                        mock_request = type('MockRequest', (), {
                            'match_info': {'symbol': symbol}
                        })()
                        result = await self.get_price_data(mock_request)
                        if result.status == 200:
                            response["collected_data"]["price"] = json.loads(result.text)
                            response["collection_status"]["price"] = "success"
                        else:
                            response["collection_status"]["price"] = "failed"
                    
                    elif data_type == "financial":
                        mock_request = type('MockRequest', (), {
                            'match_info': {'symbol': symbol}
                        })()
                        result = await self.get_financial_data(mock_request)
                        if result.status == 200:
                            response["collected_data"]["financial"] = json.loads(result.text)
                            response["collection_status"]["financial"] = "success"
                        else:
                            response["collection_status"]["financial"] = "failed"
                    
                    elif data_type == "news":
                        mock_request = type('MockRequest', (), {
                            'match_info': {'symbol': symbol}
                        })()
                        result = await self.get_news_data(mock_request)
                        if result.status == 200:
                            response["collected_data"]["news"] = json.loads(result.text)
                            response["collection_status"]["news"] = "success"
                        else:
                            response["collection_status"]["news"] = "failed"
                            
                except Exception as e:
                    logger.error(f"데이터 수집 실패 ({data_type}): {str(e)}")
                    response["collection_status"][data_type] = f"error: {str(e)}"
            
            logger.info(f"종합 데이터 수집 완료: {symbol}")
            return web.json_response(response)
            
        except Exception as e:
            logger.error(f"데이터 요청 처리 실패: {str(e)}")
            return web.json_response(
                {"error": "데이터 요청 처리 중 오류 발생", "details": str(e)},
                status=500
            )
    
    async def start_server(self):
        """서버 시작"""
        logger.info(f"🚀 Data Collector Agent 시작 (포트 {self.port})")
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, 'localhost', self.port)
        await site.start()
        logger.info(f"✅ 서버가 http://localhost:{self.port}에서 실행 중")
        return runner


class AnalysisAgent:
    """
    분석 에이전트
    
    Data Collector Agent로부터 데이터를 받아 분석하고 투자 의견을 제시합니다.
    """
    
    def __init__(self, port: int = 8081, collector_port: int = 8080):
        self.port = port
        self.collector_port = collector_port
        self.app = web.Application()
        self.setup_routes()
        
    def setup_routes(self):
        """API 라우트 설정"""
        self.app.router.add_get('/health', self.health_check)
        self.app.router.add_post('/analyze/{symbol}', self.analyze_stock)
        self.app.router.add_get('/status', self.get_status)
    
    async def health_check(self, request):
        """헬스 체크 엔드포인트"""
        return web.json_response({
            "status": "healthy",
            "agent": "AnalysisAgent",
            "timestamp": datetime.now().isoformat(),
            "port": self.port,
            "collector_port": self.collector_port
        })
    
    async def get_status(self, request):
        """상태 확인"""
        # Data Collector Agent 연결 상태 확인
        collector_healthy = await self.check_collector_health()
        
        return web.json_response({
            "analysis_agent": "healthy",
            "data_collector_agent": "healthy" if collector_healthy else "disconnected",
            "collector_url": f"http://localhost:{self.collector_port}",
            "timestamp": datetime.now().isoformat()
        })
    
    async def check_collector_health(self):
        """Data Collector Agent 상태 확인"""
        try:
            timeout = ClientTimeout(total=5)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(f"http://localhost:{self.collector_port}/health") as response:
                    return response.status == 200
        except Exception:
            return False
    
    async def fetch_data_from_collector(self, symbol: str, data_types: list = None):
        """Data Collector Agent로부터 데이터 수집"""
        if data_types is None:
            data_types = ["price", "financial", "news"]
        
        logger.info(f"📡 Collector Agent에서 데이터 수집 중: {symbol}")
        
        try:
            timeout = ClientTimeout(total=30)  # 30초 타임아웃
            async with aiohttp.ClientSession(timeout=timeout) as session:
                request_payload = {
                    "symbol": symbol,
                    "data_types": data_types
                }
                
                async with session.post(
                    f"http://localhost:{self.collector_port}/data/request",
                    json=request_payload
                ) as response:
                    
                    if response.status == 200:
                        data = await response.json()
                        logger.info(f"✅ 데이터 수집 완료: {symbol}")
                        return data
                    else:
                        error_text = await response.text()
                        logger.error(f"❌ 데이터 수집 실패: {response.status} - {error_text}")
                        return None
                        
        except asyncio.TimeoutError:
            logger.error("❌ 데이터 수집 타임아웃")
            return None
        except Exception as e:
            logger.error(f"❌ 데이터 수집 중 오류: {str(e)}")
            return None
    
    async def analyze_stock(self, request):
        """주식 분석 수행"""
        symbol = request.match_info['symbol']
        logger.info(f"📊 주식 분석 시작: {symbol}")
        
        # 1. Data Collector Agent에서 데이터 수집
        collected_data = await self.fetch_data_from_collector(symbol)
        
        if not collected_data:
            return web.json_response(
                {"error": "데이터 수집 실패", "symbol": symbol},
                status=503
            )
        
        # 2. 수집된 데이터 검증
        required_data = collected_data.get("collected_data", {})
        missing_data = []
        
        for data_type in ["price", "financial", "news"]:
            if data_type not in required_data or collected_data["collection_status"].get(data_type) != "success":
                missing_data.append(data_type)
        
        # 3. 분석 수행
        analysis_result = await self.perform_analysis(required_data, missing_data)
        
        # 4. 결과 구성
        response = {
            "analysis_id": f"analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "symbol": symbol,
            "company_name": required_data.get("price", {}).get("company_name", ""),
            "data_collection": {
                "request_id": collected_data.get("request_id"),
                "collection_status": collected_data.get("collection_status"),
                "missing_data": missing_data
            },
            "analysis_result": analysis_result,
            "timestamp": datetime.now().isoformat(),
            "analysis_agent": "AnalysisAgent"
        }
        
        logger.info(f"✅ 분석 완료: {symbol} - {analysis_result['investment_opinion']}")
        return web.json_response(response)
    
    async def perform_analysis(self, data: Dict[str, Any], missing_data: list) -> Dict[str, Any]:
        """실제 분석 로직"""
        logger.info("🔍 데이터 분석 중...")
        
        # 분석 시간 시뮬레이션
        await asyncio.sleep(2)
        
        analysis_scores = {}
        total_score = 0
        max_possible_score = 0
        
        # 주가 분석
        if "price" in data:
            price_data = data["price"]
            current_price = price_data["current_price"]
            high_52w = price_data["52w_high"]
            low_52w = price_data["52w_low"]
            
            # 52주 가격 위치 계산
            price_position = (current_price - low_52w) / (high_52w - low_52w)
            
            if price_position < 0.3:  # 저가권
                price_score = 80
            elif price_position < 0.7:  # 중간가
                price_score = 60
            else:  # 고가권
                price_score = 40
            
            analysis_scores["price"] = {
                "score": price_score,
                "reasoning": f"52주 가격 위치: {price_position:.1%} ({'저가권' if price_position < 0.3 else '중간가' if price_position < 0.7 else '고가권'})",
                "current_price": current_price,
                "price_position": price_position
            }
            
            total_score += price_score
            max_possible_score += 100
        
        # 재무 분석
        if "financial" in data:
            financial_data = data["financial"]
            ratios = financial_data["financial_ratios"]
            
            # PER, PBR, ROE 기반 점수 계산
            per_score = 100 - min((ratios["per"] - 8) * 5, 50) if ratios["per"] > 8 else 90
            pbr_score = 90 if ratios["pbr"] < 1.0 else 70
            roe_score = min(ratios["roe"] * 6, 100)
            
            financial_score = (per_score + pbr_score + roe_score) / 3
            
            analysis_scores["financial"] = {
                "score": financial_score,
                "reasoning": f"PER: {ratios['per']}, PBR: {ratios['pbr']}, ROE: {ratios['roe']}%",
                "per": ratios["per"],
                "pbr": ratios["pbr"],
                "roe": ratios["roe"]
            }
            
            total_score += financial_score
            max_possible_score += 100
        
        # 뉴스 분석
        if "news" in data:
            news_data = data["news"]
            sentiment_score = news_data["news_summary"]["sentiment_score"]
            
            # 감성 점수를 0-100 점수로 변환
            news_score = sentiment_score * 100
            
            analysis_scores["news"] = {
                "score": news_score,
                "reasoning": f"뉴스 감성: {sentiment_score:.2f} ({'긍정적' if sentiment_score > 0.6 else '부정적' if sentiment_score < 0.4 else '중립적'})",
                "sentiment_score": sentiment_score,
                "total_articles": news_data["news_summary"]["total_articles"]
            }
            
            total_score += news_score
            max_possible_score += 100
        
        # 최종 점수 계산
        if max_possible_score > 0:
            final_score = total_score / max_possible_score * 100
        else:
            final_score = 0
        
        # 투자 의견 결정
        if final_score >= 80:
            investment_opinion = "적극 매수 (STRONG BUY)"
            confidence = "높음"
        elif final_score >= 70:
            investment_opinion = "매수 (BUY)"
            confidence = "보통"
        elif final_score >= 60:
            investment_opinion = "보유 (HOLD)"
            confidence = "보통"
        elif final_score >= 50:
            investment_opinion = "관망 (NEUTRAL)"
            confidence = "낮음"
        else:
            investment_opinion = "매도 (SELL)"
            confidence = "높음"
        
        # 신뢰도 조정 (누락된 데이터가 있으면 신뢰도 감소)
        data_completeness = (3 - len(missing_data)) / 3
        if data_completeness < 1.0:
            confidence = "낮음" if confidence == "높음" else confidence
        
        return {
            "final_score": round(final_score, 1),
            "investment_opinion": investment_opinion,
            "confidence": confidence,
            "data_completeness": data_completeness,
            "analysis_breakdown": analysis_scores,
            "missing_data_impact": len(missing_data) > 0,
            "recommendation_basis": f"{len(data) - len(missing_data)}개 데이터 소스 기반"
        }
    
    async def start_server(self):
        """서버 시작"""
        logger.info(f"🚀 Analysis Agent 시작 (포트 {self.port})")
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, 'localhost', self.port)
        await site.start()
        logger.info(f"✅ 서버가 http://localhost:{self.port}에서 실행 중")
        return runner


async def run_collector_agent(port: int):
    """Data Collector Agent 실행"""
    agent = DataCollectorAgent(port)
    runner = await agent.start_server()
    
    try:
        print(f"\n{'='*60}")
        print(f"  📊 Data Collector Agent 실행 중 (포트 {port})")
        print(f"{'='*60}")
        print(f"API 엔드포인트:")
        print(f"  GET  /health - 헬스 체크")
        print(f"  GET  /data/price/{{symbol}} - 주가 데이터")
        print(f"  GET  /data/financial/{{symbol}} - 재무 데이터")
        print(f"  GET  /data/news/{{symbol}} - 뉴스 데이터")
        print(f"  POST /data/request - 종합 데이터 요청")
        print(f"\n💡 테스트:")
        print(f"  curl http://localhost:{port}/health")
        print(f"  curl http://localhost:{port}/data/price/005490")
        print(f"\n⏹️ 종료: Ctrl+C")
        
        # 서버 유지
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("서버 종료 중...")
    finally:
        await runner.cleanup()


async def run_analysis_agent(port: int, collector_port: int):
    """Analysis Agent 실행"""
    agent = AnalysisAgent(port, collector_port)
    runner = await agent.start_server()
    
    try:
        print(f"\n{'='*60}")
        print(f"  📈 Analysis Agent 실행 중 (포트 {port})")
        print(f"{'='*60}")
        print(f"Data Collector Agent: http://localhost:{collector_port}")
        print(f"API 엔드포인트:")
        print(f"  GET  /health - 헬스 체크")
        print(f"  GET  /status - 전체 상태 확인")
        print(f"  POST /analyze/{{symbol}} - 주식 분석")
        print(f"\n💡 테스트:")
        print(f"  curl http://localhost:{port}/health")
        print(f"  curl http://localhost:{port}/status")
        print(f"  curl -X POST http://localhost:{port}/analyze/005490")
        print(f"\n⏹️ 종료: Ctrl+C")
        
        # Data Collector Agent 연결 확인
        await asyncio.sleep(1)
        collector_healthy = await agent.check_collector_health()
        if collector_healthy:
            print(f"✅ Data Collector Agent 연결됨")
        else:
            print(f"⚠️ Data Collector Agent 연결 실패")
            print(f"   먼저 Data Collector Agent를 실행해주세요:")
            print(f"   python 3_1_http_basic.py --role collector --port {collector_port}")
        
        # 서버 유지
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("서버 종료 중...")
    finally:
        await runner.cleanup()


async def demonstrate_communication():
    """통신 데모 실행"""
    print(f"\n{'='*60}")
    print(f"  🤖 Agent-to-Agent HTTP 통신 데모")
    print(f"{'='*60}")
    
    # 두 에이전트 동시 실행
    collector_port = 8080
    analyzer_port = 8081
    
    print("🚀 두 에이전트를 동시에 시작합니다...")
    
    # 에이전트 인스턴스 생성
    collector = DataCollectorAgent(collector_port)
    analyzer = AnalysisAgent(analyzer_port, collector_port)
    
    # 서버 시작
    collector_runner = await collector.start_server()
    analyzer_runner = await analyzer.start_server()
    
    try:
        # 연결 확인
        await asyncio.sleep(2)
        collector_healthy = await analyzer.check_collector_health()
        
        if collector_healthy:
            print("✅ 두 에이전트 모두 정상 실행됨")
            print(f"\n📊 포스코(005490) 분석 데모 시작...")
            
            # 분석 요청 (Analysis Agent가 Collector Agent에 데이터 요청)
            timeout = ClientTimeout(total=60)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(f"http://localhost:{analyzer_port}/analyze/005490") as response:
                    if response.status == 200:
                        result = await response.json()
                        
                        print(f"\n🎯 분석 결과:")
                        print(f"  종목: {result['company_name']} ({result['symbol']})")
                        print(f"  최종 점수: {result['analysis_result']['final_score']}/100")
                        print(f"  투자 의견: {result['analysis_result']['investment_opinion']}")
                        print(f"  신뢰도: {result['analysis_result']['confidence']}")
                        print(f"  데이터 완전성: {result['analysis_result']['data_completeness']*100:.0f}%")
                        
                        # 분석 세부사항
                        breakdown = result['analysis_result']['analysis_breakdown']
                        print(f"\n📈 분석 세부사항:")
                        for category, details in breakdown.items():
                            print(f"  {category}: {details['score']:.1f}점 - {details['reasoning']}")
                        
                        print(f"\n✅ Agent-to-Agent 통신 성공!")
                    else:
                        error_text = await response.text()
                        print(f"❌ 분석 실패: {response.status} - {error_text}")
        else:
            print("❌ 에이전트 연결 실패")
        
        print(f"\n⏹️ 데모 종료를 위해 Ctrl+C를 누르세요...")
        
        # 서버 유지
        while True:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        print("\n🔚 데모 종료 중...")
    finally:
        await collector_runner.cleanup()
        await analyzer_runner.cleanup()


def main():
    parser = argparse.ArgumentParser(description="Agent-to-Agent HTTP 통신 데모")
    parser.add_argument("--role", choices=["collector", "analyzer", "demo"], 
                       help="실행할 에이전트 역할")
    parser.add_argument("--port", type=int, default=8080, 
                       help="에이전트 포트 번호")
    parser.add_argument("--collector-port", type=int, default=8080,
                       help="Collector Agent 포트 (Analyzer 전용)")
    
    args = parser.parse_args()
    
    if args.role == "collector":
        print("🤖 Agent-to-Agent HTTP 통신 학습을 시작합니다!")
        print("이 예제는 두 에이전트 간 HTTP 통신을 보여줍니다.")
        asyncio.run(run_collector_agent(args.port))
    elif args.role == "analyzer":
        asyncio.run(run_analysis_agent(args.port, args.collector_port))
    elif args.role == "demo":
        print("🤖 Agent-to-Agent HTTP 통신 학습을 시작합니다!")
        print("이 예제는 두 에이전트 간 HTTP 통신을 보여줍니다.")
        asyncio.run(demonstrate_communication())
    else:
        print("사용법:")
        print("  데이터 수집 에이전트: python 3_1_http_basic.py --role collector --port 8080")
        print("  분석 에이전트:       python 3_1_http_basic.py --role analyzer --port 8081 --collector-port 8080")
        print("  통신 데모:           python 3_1_http_basic.py --role demo")


if __name__ == "__main__":
    main()