#!/usr/bin/env python3
"""
Step 4.1: 통합 한국 주식시장 분석 플랫폼
===========================================

이 예제는 LangGraph + A2A 통신의 완전한 통합을 보여줍니다:
- 다중 LangGraph 워크플로우 (Step 2의 개념들)
- A2A 에이전트 간 통신 (Step 3의 개념들)
- 실시간 데이터 스트리밍
- 상태 동기화
- 웹 인터페이스
- 완전한 오케스트레이션

학습 목표:
1. 전체 시스템 아키텍처 이해
2. 다중 컴포넌트 통합 방법
3. 실제 운용 환경 구현
4. 확장 가능한 플랫폼 설계

Korean Market Focus: 삼성전자, LG에너지솔루션, SK하이닉스 포트폴리오 분석
"""

import asyncio
import json
import logging
import websockets
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from enum import Enum
import aiohttp
from aiohttp import web, WSMsgType
import aioredis
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.aioredis import AsyncRedisSaver
from langgraph.prebuilt import ToolInvocation
import uuid
from pydantic import BaseModel

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 시장 상태 열거형
class MarketStatus(Enum):
    OPEN = "open"
    CLOSED = "closed"
    PRE_MARKET = "pre_market"
    AFTER_MARKET = "after_market"

class AnalysisType(Enum):
    TECHNICAL = "technical"
    FUNDAMENTAL = "fundamental"
    SENTIMENT = "sentiment"
    RISK = "risk"

# 데이터 모델들
@dataclass
class StockData:
    symbol: str
    name: str
    price: float
    change: float
    change_percent: float
    volume: int
    timestamp: datetime
    market_cap: Optional[float] = None
    
    def to_dict(self):
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data

@dataclass
class AnalysisResult:
    stock_symbol: str
    analysis_type: AnalysisType
    score: float  # 0-100 점수
    confidence: float  # 0-1 신뢰도
    reasoning: str
    recommendations: List[str]
    timestamp: datetime
    analyst_id: str
    
    def to_dict(self):
        data = asdict(self)
        data['analysis_type'] = self.analysis_type.value
        data['timestamp'] = self.timestamp.isoformat()
        return data

class PlatformState(BaseModel):
    market_status: MarketStatus
    active_stocks: List[str]
    current_analyses: Dict[str, List[AnalysisResult]]
    portfolio_positions: Dict[str, float]
    system_health: Dict[str, bool]
    last_update: datetime

# 중앙 상태 관리자
class StateManager:
    """Redis를 사용한 중앙 상태 관리"""
    
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_url = redis_url
        self.redis: Optional[aioredis.Redis] = None
        
    async def initialize(self):
        """Redis 연결 초기화"""
        self.redis = await aioredis.from_url(self.redis_url)
        logger.info("상태 관리자가 초기화되었습니다")
        
    async def update_stock_data(self, stock_data: StockData):
        """주식 데이터 업데이트"""
        if self.redis:
            await self.redis.hset(
                f"stock:{stock_data.symbol}",
                mapping=stock_data.to_dict()
            )
            await self.redis.publish("stock_updates", json.dumps(stock_data.to_dict()))
            
    async def get_stock_data(self, symbol: str) -> Optional[StockData]:
        """주식 데이터 조회"""
        if self.redis:
            data = await self.redis.hgetall(f"stock:{symbol}")
            if data:
                data_dict = {k.decode(): v.decode() for k, v in data.items()}
                data_dict['timestamp'] = datetime.fromisoformat(data_dict['timestamp'])
                return StockData(**data_dict)
        return None
        
    async def update_analysis(self, analysis: AnalysisResult):
        """분석 결과 업데이트"""
        if self.redis:
            analysis_key = f"analysis:{analysis.stock_symbol}:{analysis.analysis_type.value}"
            await self.redis.hset(analysis_key, mapping=analysis.to_dict())
            await self.redis.publish("analysis_updates", json.dumps(analysis.to_dict()))

# 실시간 데이터 피드 시뮬레이터
class MarketDataFeed:
    """한국 주식시장 실시간 데이터 시뮬레이션"""
    
    def __init__(self, state_manager: StateManager):
        self.state_manager = state_manager
        self.stocks = {
            "005930": {"name": "삼성전자", "base_price": 75000, "volatility": 0.02},
            "373220": {"name": "LG에너지솔루션", "base_price": 450000, "volatility": 0.03},
            "000660": {"name": "SK하이닉스", "base_price": 125000, "volatility": 0.025}
        }
        self.running = False
        
    async def start_feed(self):
        """데이터 피드 시작"""
        self.running = True
        logger.info("실시간 데이터 피드를 시작합니다")
        
        while self.running:
            for symbol, info in self.stocks.items():
                # 가격 변동 시뮬레이션
                import random
                change_percent = random.uniform(-info["volatility"], info["volatility"])
                new_price = info["base_price"] * (1 + change_percent)
                change = new_price - info["base_price"]
                
                stock_data = StockData(
                    symbol=symbol,
                    name=info["name"],
                    price=new_price,
                    change=change,
                    change_percent=change_percent * 100,
                    volume=random.randint(100000, 1000000),
                    timestamp=datetime.now(),
                    market_cap=new_price * 5000000000  # 임시 시가총액
                )
                
                await self.state_manager.update_stock_data(stock_data)
                
            await asyncio.sleep(5)  # 5초마다 업데이트
            
    async def stop_feed(self):
        """데이터 피드 중지"""
        self.running = False
        logger.info("실시간 데이터 피드를 중지합니다")

# LangGraph 기반 분석 워크플로우
class TechnicalAnalysisWorkflow:
    """기술적 분석 워크플로우 (Step 2 개념 활용)"""
    
    def __init__(self, state_manager: StateManager):
        self.state_manager = state_manager
        self.workflow = self._create_workflow()
        
    def _create_workflow(self):
        """분석 워크플로우 생성"""
        
        async def collect_data(state: Dict[str, Any]) -> Dict[str, Any]:
            """데이터 수집"""
            symbol = state["symbol"]
            stock_data = await self.state_manager.get_stock_data(symbol)
            
            state["stock_data"] = stock_data.to_dict() if stock_data else None
            state["step"] = "data_collected"
            logger.info(f"[기술분석] {symbol} 데이터 수집 완료")
            return state
            
        async def analyze_trends(state: Dict[str, Any]) -> Dict[str, Any]:
            """추세 분석"""
            if not state["stock_data"]:
                state["error"] = "데이터 없음"
                return state
                
            # 간단한 추세 분석 로직
            price = state["stock_data"]["price"]
            change_percent = state["stock_data"]["change_percent"]
            
            if change_percent > 2:
                trend = "강한 상승"
                score = 80
            elif change_percent > 0:
                trend = "상승"
                score = 65
            elif change_percent > -2:
                trend = "횡보"
                score = 50
            else:
                trend = "하락"
                score = 30
                
            state["trend_analysis"] = {
                "trend": trend,
                "score": score,
                "reasoning": f"현재 가격 {price:,.0f}원, 변동률 {change_percent:.2f}%"
            }
            state["step"] = "trends_analyzed"
            logger.info(f"[기술분석] {state['symbol']} 추세 분석 완료: {trend}")
            return state
            
        async def generate_signals(state: Dict[str, Any]) -> Dict[str, Any]:
            """매매 신호 생성"""
            if "error" in state:
                return state
                
            trend_analysis = state["trend_analysis"]
            score = trend_analysis["score"]
            
            if score > 70:
                signal = "매수"
                recommendations = ["적극적 매수", "포지션 확대 고려"]
            elif score > 55:
                signal = "관망"
                recommendations = ["소량 매수", "추가 신호 대기"]
            else:
                signal = "매도"
                recommendations = ["포지션 축소", "손실 제한"]
                
            state["signals"] = {
                "signal": signal,
                "recommendations": recommendations,
                "confidence": min(score / 100, 1.0)
            }
            state["step"] = "signals_generated"
            logger.info(f"[기술분석] {state['symbol']} 신호 생성: {signal}")
            return state
            
        # StateGraph 구성
        workflow = StateGraph(dict)
        workflow.add_node("collect_data", collect_data)
        workflow.add_node("analyze_trends", analyze_trends)
        workflow.add_node("generate_signals", generate_signals)
        
        workflow.set_entry_point("collect_data")
        workflow.add_edge("collect_data", "analyze_trends")
        workflow.add_edge("analyze_trends", "generate_signals")
        workflow.add_edge("generate_signals", END)
        
        return workflow.compile()
        
    async def analyze(self, symbol: str) -> AnalysisResult:
        """기술적 분석 실행"""
        initial_state = {"symbol": symbol}
        
        result = await self.workflow.ainvoke(initial_state)
        
        if "error" in result:
            return AnalysisResult(
                stock_symbol=symbol,
                analysis_type=AnalysisType.TECHNICAL,
                score=0,
                confidence=0,
                reasoning=result["error"],
                recommendations=[],
                timestamp=datetime.now(),
                analyst_id="technical_workflow"
            )
            
        signals = result["signals"]
        return AnalysisResult(
            stock_symbol=symbol,
            analysis_type=AnalysisType.TECHNICAL,
            score=result["trend_analysis"]["score"],
            confidence=signals["confidence"],
            reasoning=result["trend_analysis"]["reasoning"],
            recommendations=signals["recommendations"],
            timestamp=datetime.now(),
            analyst_id="technical_workflow"
        )

# A2A 통신을 위한 분석 에이전트
class AnalysisAgent:
    """A2A 통신 기반 분석 에이전트 (Step 3 개념 활용)"""
    
    def __init__(self, agent_id: str, port: int, state_manager: StateManager):
        self.agent_id = agent_id
        self.port = port
        self.state_manager = state_manager
        self.app = web.Application()
        self.setup_routes()
        self.peer_agents: Dict[str, str] = {}  # agent_id -> url 매핑
        
    def setup_routes(self):
        """HTTP 라우트 설정"""
        self.app.router.add_post('/analyze', self.analyze_request)
        self.app.router.add_post('/collaborate', self.collaboration_request)
        self.app.router.add_get('/status', self.status_check)
        
    async def analyze_request(self, request):
        """분석 요청 처리"""
        try:
            data = await request.json()
            symbol = data.get('symbol')
            analysis_type = AnalysisType(data.get('analysis_type', 'technical'))
            
            # 분석 실행 (에이전트별 전문 분야)
            result = await self._perform_analysis(symbol, analysis_type)
            
            # 상태 저장
            await self.state_manager.update_analysis(result)
            
            return web.json_response({
                'status': 'success',
                'analysis': result.to_dict()
            })
            
        except Exception as e:
            logger.error(f"[{self.agent_id}] 분석 요청 오류: {e}")
            return web.json_response(
                {'status': 'error', 'message': str(e)},
                status=500
            )
            
    async def collaboration_request(self, request):
        """다른 에이전트와의 협업 요청"""
        try:
            data = await request.json()
            collaboration_type = data.get('type')
            payload = data.get('payload')
            
            # 협업 처리 로직
            result = await self._handle_collaboration(collaboration_type, payload)
            
            return web.json_response({
                'status': 'success',
                'result': result
            })
            
        except Exception as e:
            logger.error(f"[{self.agent_id}] 협업 요청 오류: {e}")
            return web.json_response(
                {'status': 'error', 'message': str(e)},
                status=500
            )
            
    async def status_check(self, request):
        """에이전트 상태 확인"""
        return web.json_response({
            'agent_id': self.agent_id,
            'status': 'running',
            'timestamp': datetime.now().isoformat()
        })
        
    async def _perform_analysis(self, symbol: str, analysis_type: AnalysisType) -> AnalysisResult:
        """분석 수행 (에이전트별 특화)"""
        stock_data = await self.state_manager.get_stock_data(symbol)
        
        if not stock_data:
            return AnalysisResult(
                stock_symbol=symbol,
                analysis_type=analysis_type,
                score=0,
                confidence=0,
                reasoning="데이터 없음",
                recommendations=[],
                timestamp=datetime.now(),
                analyst_id=self.agent_id
            )
            
        # 에이전트별 특화 분석
        if analysis_type == AnalysisType.FUNDAMENTAL:
            # 기본적 분석
            score = min(stock_data.market_cap / 1000000000000 * 10, 100) if stock_data.market_cap else 50
            reasoning = f"시가총액 {stock_data.market_cap/1000000000000:.1f}조원 기준 평가"
            recommendations = ["장기 투자 관점", "펀더멘털 우수"] if score > 60 else ["주의 필요", "추가 분석 요구"]
            
        elif analysis_type == AnalysisType.SENTIMENT:
            # 센티먼트 분석 (간단한 로직)
            volume_score = min(stock_data.volume / 1000000 * 20, 100)
            score = (volume_score + abs(stock_data.change_percent) * 10) / 2
            reasoning = f"거래량 {stock_data.volume:,}주, 변동성 기준 센티먼트"
            recommendations = ["시장 관심 증가", "모멘텀 활용"] if score > 50 else ["관심 부족", "촉매 필요"]
            
        else:  # RISK 분석
            volatility = abs(stock_data.change_percent)
            risk_score = min(volatility * 20, 100)
            score = 100 - risk_score  # 리스크가 낮을수록 높은 점수
            reasoning = f"변동성 {volatility:.2f}% 기준 리스크 평가"
            recommendations = ["안정적 투자", "리스크 관리 양호"] if score > 70 else ["고위험", "신중한 접근"]
            
        return AnalysisResult(
            stock_symbol=symbol,
            analysis_type=analysis_type,
            score=score,
            confidence=0.8,
            reasoning=reasoning,
            recommendations=recommendations,
            timestamp=datetime.now(),
            analyst_id=self.agent_id
        )
        
    async def _handle_collaboration(self, collaboration_type: str, payload: Dict) -> Dict:
        """협업 처리"""
        if collaboration_type == "consensus_analysis":
            # 다른 에이전트들의 분석 결과 수집 및 통합
            symbol = payload.get('symbol')
            analyses = []
            
            for agent_id, url in self.peer_agents.items():
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.post(
                            f"{url}/analyze",
                            json={'symbol': symbol, 'analysis_type': 'technical'}
                        ) as resp:
                            if resp.status == 200:
                                result = await resp.json()
                                analyses.append(result['analysis'])
                except Exception as e:
                    logger.warning(f"[{self.agent_id}] {agent_id}와의 협업 실패: {e}")
                    
            # 합의 분석 결과 생성
            if analyses:
                avg_score = sum(a['score'] for a in analyses) / len(analyses)
                consensus = {
                    'symbol': symbol,
                    'consensus_score': avg_score,
                    'participating_agents': len(analyses),
                    'recommendations': [rec for a in analyses for rec in a['recommendations']]
                }
                return consensus
                
        return {'status': 'unknown_collaboration_type'}
        
    async def register_peer(self, agent_id: str, url: str):
        """피어 에이전트 등록"""
        self.peer_agents[agent_id] = url
        logger.info(f"[{self.agent_id}] 피어 등록: {agent_id} -> {url}")
        
    async def start(self):
        """에이전트 시작"""
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, 'localhost', self.port)
        await site.start()
        logger.info(f"분석 에이전트 [{self.agent_id}]가 포트 {self.port}에서 시작되었습니다")

# 웹소켓 기반 실시간 클라이언트 인터페이스
class WebSocketHandler:
    """실시간 웹소켓 인터페이스"""
    
    def __init__(self, state_manager: StateManager):
        self.state_manager = state_manager
        self.clients: set = set()
        
    async def register_client(self, websocket):
        """클라이언트 등록"""
        self.clients.add(websocket)
        logger.info(f"새 클라이언트 연결: {len(self.clients)}개 활성")
        
    async def unregister_client(self, websocket):
        """클라이언트 등록 해제"""
        self.clients.discard(websocket)
        logger.info(f"클라이언트 연결 해제: {len(self.clients)}개 활성")
        
    async def broadcast_stock_update(self, stock_data: StockData):
        """주식 데이터 업데이트 브로드캐스트"""
        if self.clients:
            message = {
                'type': 'stock_update',
                'data': stock_data.to_dict()
            }
            await self._broadcast(message)
            
    async def broadcast_analysis_update(self, analysis: AnalysisResult):
        """분석 결과 업데이트 브로드캐스트"""
        if self.clients:
            message = {
                'type': 'analysis_update',
                'data': analysis.to_dict()
            }
            await self._broadcast(message)
            
    async def _broadcast(self, message: Dict):
        """모든 클라이언트에게 메시지 브로드캐스트"""
        if self.clients:
            disconnected = set()
            for client in self.clients:
                try:
                    await client.send(json.dumps(message))
                except websockets.exceptions.ConnectionClosed:
                    disconnected.add(client)
                except Exception as e:
                    logger.error(f"브로드캐스트 오류: {e}")
                    disconnected.add(client)
                    
            # 연결이 끊어진 클라이언트 제거
            self.clients -= disconnected
            
    async def handle_websocket(self, websocket, path):
        """웹소켓 연결 처리"""
        await self.register_client(websocket)
        try:
            # 초기 데이터 전송
            await self._send_initial_data(websocket)
            
            async for message in websocket:
                try:
                    data = json.loads(message)
                    await self._handle_client_message(websocket, data)
                except json.JSONDecodeError:
                    await websocket.send(json.dumps({
                        'type': 'error',
                        'message': 'Invalid JSON format'
                    }))
                except Exception as e:
                    logger.error(f"클라이언트 메시지 처리 오류: {e}")
                    
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            await self.unregister_client(websocket)
            
    async def _send_initial_data(self, websocket):
        """초기 데이터 전송"""
        # 현재 주식 데이터 전송
        stocks = ["005930", "373220", "000660"]
        for symbol in stocks:
            stock_data = await self.state_manager.get_stock_data(symbol)
            if stock_data:
                await websocket.send(json.dumps({
                    'type': 'initial_stock',
                    'data': stock_data.to_dict()
                }))
                
    async def _handle_client_message(self, websocket, data: Dict):
        """클라이언트 메시지 처리"""
        message_type = data.get('type')
        
        if message_type == 'request_analysis':
            symbol = data.get('symbol')
            analysis_type = data.get('analysis_type', 'technical')
            
            # 분석 요청을 적절한 에이전트에게 전달
            # (실제 구현에서는 로드 밸런싱 등을 고려)
            await websocket.send(json.dumps({
                'type': 'analysis_requested',
                'symbol': symbol,
                'analysis_type': analysis_type
            }))

# 마스터 오케스트레이터
class IntegratedMarketPlatform:
    """통합 시장 분석 플랫폼 오케스트레이터"""
    
    def __init__(self):
        self.state_manager = StateManager()
        self.market_feed = MarketDataFeed(self.state_manager)
        self.technical_workflow = TechnicalAnalysisWorkflow(self.state_manager)
        self.websocket_handler = WebSocketHandler(self.state_manager)
        
        # 분석 에이전트들
        self.agents = {
            "fundamental_agent": AnalysisAgent("fundamental_agent", 8001, self.state_manager),
            "sentiment_agent": AnalysisAgent("sentiment_agent", 8002, self.state_manager),
            "risk_agent": AnalysisAgent("risk_agent", 8003, self.state_manager)
        }
        
        self.running = False
        
    async def initialize(self):
        """플랫폼 초기화"""
        logger.info("=== 통합 한국 주식시장 분석 플랫폼 초기화 ===")
        
        # 상태 관리자 초기화
        await self.state_manager.initialize()
        
        # 분석 에이전트 시작
        for agent_id, agent in self.agents.items():
            await agent.start()
            
        # 에이전트 간 피어 등록
        for agent_id, agent in self.agents.items():
            for peer_id, peer_agent in self.agents.items():
                if agent_id != peer_id:
                    await agent.register_peer(peer_id, f"http://localhost:{peer_agent.port}")
                    
        # Redis 구독 설정
        await self._setup_redis_subscriptions()
        
        logger.info("플랫폼 초기화 완료")
        
    async def _setup_redis_subscriptions(self):
        """Redis 구독 설정"""
        async def handle_stock_updates():
            pubsub = self.state_manager.redis.pubsub()
            await pubsub.subscribe("stock_updates")
            
            async for message in pubsub.listen():
                if message['type'] == 'message':
                    try:
                        stock_data_dict = json.loads(message['data'])
                        stock_data_dict['timestamp'] = datetime.fromisoformat(stock_data_dict['timestamp'])
                        stock_data = StockData(**stock_data_dict)
                        await self.websocket_handler.broadcast_stock_update(stock_data)
                    except Exception as e:
                        logger.error(f"주식 업데이트 처리 오류: {e}")
                        
        async def handle_analysis_updates():
            pubsub = self.state_manager.redis.pubsub()
            await pubsub.subscribe("analysis_updates")
            
            async for message in pubsub.listen():
                if message['type'] == 'message':
                    try:
                        analysis_dict = json.loads(message['data'])
                        analysis_dict['timestamp'] = datetime.fromisoformat(analysis_dict['timestamp'])
                        analysis_dict['analysis_type'] = AnalysisType(analysis_dict['analysis_type'])
                        analysis = AnalysisResult(**analysis_dict)
                        await self.websocket_handler.broadcast_analysis_update(analysis)
                    except Exception as e:
                        logger.error(f"분석 업데이트 처리 오류: {e}")
                        
        # 백그라운드 태스크로 실행
        asyncio.create_task(handle_stock_updates())
        asyncio.create_task(handle_analysis_updates())
        
    async def start_platform(self):
        """플랫폼 시작"""
        self.running = True
        logger.info("=== 통합 플랫폼 시작 ===")
        
        # 마켓 데이터 피드 시작
        asyncio.create_task(self.market_feed.start_feed())
        
        # 정기적 분석 실행
        asyncio.create_task(self._periodic_analysis())
        
        # 웹소켓 서버 시작
        websocket_server = websockets.serve(
            self.websocket_handler.handle_websocket,
            "localhost",
            8765
        )
        await websocket_server
        
        logger.info("웹소켓 서버 시작: ws://localhost:8765")
        logger.info("모든 시스템 구성요소가 활성화되었습니다")
        
    async def _periodic_analysis(self):
        """정기적 분석 실행"""
        stocks = ["005930", "373220", "000660"]
        
        while self.running:
            try:
                for symbol in stocks:
                    # 기술적 분석 (LangGraph 워크플로우)
                    technical_result = await self.technical_workflow.analyze(symbol)
                    await self.state_manager.update_analysis(technical_result)
                    
                    # A2A 에이전트 분석 요청
                    for agent_id, agent in self.agents.items():
                        analysis_type = {
                            "fundamental_agent": AnalysisType.FUNDAMENTAL,
                            "sentiment_agent": AnalysisType.SENTIMENT,
                            "risk_agent": AnalysisType.RISK
                        }.get(agent_id, AnalysisType.TECHNICAL)
                        
                        try:
                            async with aiohttp.ClientSession() as session:
                                async with session.post(
                                    f"http://localhost:{agent.port}/analyze",
                                    json={
                                        'symbol': symbol,
                                        'analysis_type': analysis_type.value
                                    }
                                ) as resp:
                                    if resp.status == 200:
                                        result = await resp.json()
                                        logger.info(f"[{agent_id}] {symbol} 분석 완료: {result['analysis']['score']:.1f}점")
                                        
                        except Exception as e:
                            logger.error(f"[{agent_id}] {symbol} 분석 요청 실패: {e}")
                            
                await asyncio.sleep(30)  # 30초마다 분석
                
            except Exception as e:
                logger.error(f"정기 분석 오류: {e}")
                await asyncio.sleep(10)
                
    async def stop_platform(self):
        """플랫폼 중지"""
        self.running = False
        await self.market_feed.stop_feed()
        logger.info("통합 플랫폼이 중지되었습니다")
        
    async def get_platform_status(self) -> Dict:
        """플랫폼 상태 조회"""
        stocks_status = {}
        for symbol in ["005930", "373220", "000660"]:
            stock_data = await self.state_manager.get_stock_data(symbol)
            stocks_status[symbol] = stock_data.to_dict() if stock_data else None
            
        return {
            'platform_status': 'running' if self.running else 'stopped',
            'connected_clients': len(self.websocket_handler.clients),
            'active_agents': len(self.agents),
            'stocks_status': stocks_status,
            'timestamp': datetime.now().isoformat()
        }

# 메인 실행 함수
async def main():
    """메인 실행 함수"""
    platform = IntegratedMarketPlatform()
    
    try:
        # 플랫폼 초기화
        await platform.initialize()
        
        # 플랫폼 시작
        await platform.start_platform()
        
        print("\n=== 통합 한국 주식시장 분석 플랫폼 ===")
        print("웹소켓 연결: ws://localhost:8765")
        print("기본적 분석 에이전트: http://localhost:8001")
        print("센티먼트 분석 에이전트: http://localhost:8002") 
        print("리스크 분석 에이전트: http://localhost:8003")
        print("\n모니터링 대상:")
        print("- 005930: 삼성전자")
        print("- 373220: LG에너지솔루션")
        print("- 000660: SK하이닉스")
        print("\nCtrl+C로 중지")
        
        # 플랫폼 실행 유지
        while platform.running:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("사용자 중지 요청")
    except Exception as e:
        logger.error(f"플랫폼 실행 오류: {e}")
    finally:
        await platform.stop_platform()

if __name__ == "__main__":
    # Python 3.11+ 버전에서는 다음과 같이 실행
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n플랫폼이 안전하게 종료되었습니다.")