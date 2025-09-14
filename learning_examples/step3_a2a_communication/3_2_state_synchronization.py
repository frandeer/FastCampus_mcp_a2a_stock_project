#!/usr/bin/env python3
"""
3.2 상태 동기화 - 현대차 실시간 동기화

Agent 간 상태 동기화를 학습하는 예제입니다.
현대차(005380) 주식 분석을 위해 여러 에이전트가 공유 상태를 실시간으로 동기화하는 시나리오를 구현합니다.

학습 목표:
- 분산 에이전트 간 상태 동기화 이해
- 중앙집중식 상태 관리 패턴
- 상태 변경 알림(Notification) 메커니즘
- 데이터 일관성 보장 방법
- 버전 관리를 통한 동시성 제어

에이전트 구성:
- State Manager: 중앙 상태 관리자
- Technical Agent: 기술적 분석 담당
- Fundamental Agent: 기본적 분석 담당  
- News Agent: 뉴스 분석 담당

실행 방법:
python 3_2_state_synchronization.py --role [state|technical|fundamental|news|demo] --port [포트번호]
"""

import asyncio
import json
import argparse
from typing import Dict, Any, Optional, List
from pathlib import Path
import sys
from datetime import datetime
import aiohttp
from aiohttp import web, ClientTimeout
import logging
from dataclasses import dataclass, asdict
from enum import Enum
import weakref

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class StateEventType(Enum):
    """상태 이벤트 타입"""
    STATE_UPDATED = "state_updated"
    ANALYSIS_COMPLETED = "analysis_completed"
    DATA_REFRESHED = "data_refreshed"
    AGENT_REGISTERED = "agent_registered"
    AGENT_DISCONNECTED = "agent_disconnected"


@dataclass
class StateEvent:
    """상태 이벤트"""
    event_type: StateEventType
    source_agent: str
    data: Dict[str, Any]
    timestamp: str
    version: int


@dataclass
class AnalysisState:
    """분석 상태 데이터"""
    symbol: str
    company_name: str
    last_updated: str
    version: int
    
    # 기본 데이터
    current_price: Optional[float] = None
    price_change: Optional[float] = None
    volume: Optional[int] = None
    
    # 분석 결과
    technical_analysis: Optional[Dict[str, Any]] = None
    fundamental_analysis: Optional[Dict[str, Any]] = None
    news_analysis: Optional[Dict[str, Any]] = None
    
    # 종합 결과
    overall_score: Optional[float] = None
    investment_opinion: Optional[str] = None
    confidence_level: Optional[str] = None
    
    # 참여 에이전트
    participating_agents: List[str] = None
    
    def __post_init__(self):
        if self.participating_agents is None:
            self.participating_agents = []


class StateManager:
    """
    중앙 상태 관리자
    
    모든 에이전트의 분석 상태를 중앙에서 관리하고 동기화합니다.
    """
    
    def __init__(self, port: int = 9000):
        self.port = port
        self.app = web.Application()
        self.setup_routes()
        
        # 상태 저장소
        self.analysis_state = AnalysisState(
            symbol="005380",
            company_name="현대차",
            last_updated=datetime.now().isoformat(),
            version=1
        )
        
        # 등록된 에이전트들
        self.registered_agents: Dict[str, Dict[str, Any]] = {}
        
        # 이벤트 히스토리
        self.event_history: List[StateEvent] = []
        
        # 상태 락 (동시성 제어)
        self.state_lock = asyncio.Lock()
    
    def setup_routes(self):
        """API 라우트 설정"""
        self.app.router.add_get('/health', self.health_check)
        self.app.router.add_get('/state', self.get_state)
        self.app.router.add_get('/state/version', self.get_state_version)
        self.app.router.add_post('/state/update', self.update_state)
        self.app.router.add_post('/agents/register', self.register_agent)
        self.app.router.add_delete('/agents/{agent_id}', self.unregister_agent)
        self.app.router.add_get('/agents', self.get_registered_agents)
        self.app.router.add_get('/events', self.get_events)
        self.app.router.add_post('/notify', self.broadcast_notification)
    
    async def health_check(self, request):
        """헬스 체크"""
        return web.json_response({
            "status": "healthy",
            "agent": "StateManager",
            "timestamp": datetime.now().isoformat(),
            "port": self.port,
            "registered_agents": len(self.registered_agents),
            "state_version": self.analysis_state.version
        })
    
    async def get_state(self, request):
        """현재 상태 반환"""
        async with self.state_lock:
            return web.json_response({
                "state": asdict(self.analysis_state),
                "timestamp": datetime.now().isoformat()
            })
    
    async def get_state_version(self, request):
        """상태 버전 반환"""
        return web.json_response({
            "version": self.analysis_state.version,
            "last_updated": self.analysis_state.last_updated,
            "timestamp": datetime.now().isoformat()
        })
    
    async def update_state(self, request):
        """상태 업데이트"""
        try:
            update_data = await request.json()
            source_agent = update_data.get("source_agent", "unknown")
            field_updates = update_data.get("updates", {})
            expected_version = update_data.get("expected_version")
            
            logger.info(f"📝 상태 업데이트 요청: {source_agent}")
            
            async with self.state_lock:
                # 버전 체크 (낙관적 락)
                if expected_version and expected_version != self.analysis_state.version:
                    logger.warning(f"❌ 버전 충돌: 기대값 {expected_version}, 실제값 {self.analysis_state.version}")
                    return web.json_response({
                        "error": "version_conflict",
                        "expected_version": expected_version,
                        "current_version": self.analysis_state.version,
                        "message": "상태가 다른 에이전트에 의해 변경되었습니다."
                    }, status=409)
                
                # 상태 업데이트
                for field, value in field_updates.items():
                    if hasattr(self.analysis_state, field):
                        setattr(self.analysis_state, field, value)
                        logger.info(f"   {field} 업데이트")
                
                # 참여 에이전트 추가
                if source_agent not in self.analysis_state.participating_agents:
                    self.analysis_state.participating_agents.append(source_agent)
                
                # 버전 증가 및 타임스탬프 업데이트
                self.analysis_state.version += 1
                self.analysis_state.last_updated = datetime.now().isoformat()
                
                # 이벤트 기록
                event = StateEvent(
                    event_type=StateEventType.STATE_UPDATED,
                    source_agent=source_agent,
                    data=field_updates,
                    timestamp=datetime.now().isoformat(),
                    version=self.analysis_state.version
                )
                self.event_history.append(event)
                
                logger.info(f"✅ 상태 업데이트 완료 (버전: {self.analysis_state.version})")
                
                # 다른 에이전트들에게 알림
                await self.notify_other_agents(source_agent, event)
                
                return web.json_response({
                    "success": True,
                    "new_version": self.analysis_state.version,
                    "updated_fields": list(field_updates.keys()),
                    "timestamp": self.analysis_state.last_updated
                })
                
        except Exception as e:
            logger.error(f"❌ 상태 업데이트 실패: {str(e)}")
            return web.json_response({
                "error": "update_failed",
                "message": str(e)
            }, status=500)
    
    async def register_agent(self, request):
        """에이전트 등록"""
        try:
            agent_data = await request.json()
            agent_id = agent_data.get("agent_id")
            agent_type = agent_data.get("agent_type")
            endpoint = agent_data.get("endpoint")
            
            if not all([agent_id, agent_type, endpoint]):
                return web.json_response({
                    "error": "missing_required_fields",
                    "required": ["agent_id", "agent_type", "endpoint"]
                }, status=400)
            
            # 에이전트 등록
            self.registered_agents[agent_id] = {
                "agent_id": agent_id,
                "agent_type": agent_type,
                "endpoint": endpoint,
                "registered_at": datetime.now().isoformat(),
                "last_seen": datetime.now().isoformat(),
                "status": "active"
            }
            
            logger.info(f"🤖 에이전트 등록: {agent_id} ({agent_type})")
            
            # 등록 이벤트 기록
            event = StateEvent(
                event_type=StateEventType.AGENT_REGISTERED,
                source_agent="StateManager",
                data={"agent_id": agent_id, "agent_type": agent_type},
                timestamp=datetime.now().isoformat(),
                version=self.analysis_state.version
            )
            self.event_history.append(event)
            
            return web.json_response({
                "success": True,
                "message": f"에이전트 {agent_id} 등록 완료",
                "current_state_version": self.analysis_state.version
            })
            
        except Exception as e:
            logger.error(f"❌ 에이전트 등록 실패: {str(e)}")
            return web.json_response({
                "error": "registration_failed",
                "message": str(e)
            }, status=500)
    
    async def unregister_agent(self, request):
        """에이전트 등록 해제"""
        agent_id = request.match_info['agent_id']
        
        if agent_id in self.registered_agents:
            del self.registered_agents[agent_id]
            logger.info(f"🔌 에이전트 연결 해제: {agent_id}")
            
            # 연결 해제 이벤트 기록
            event = StateEvent(
                event_type=StateEventType.AGENT_DISCONNECTED,
                source_agent="StateManager",
                data={"agent_id": agent_id},
                timestamp=datetime.now().isoformat(),
                version=self.analysis_state.version
            )
            self.event_history.append(event)
            
            return web.json_response({"success": True, "message": f"에이전트 {agent_id} 연결 해제 완료"})
        else:
            return web.json_response({"error": "agent_not_found"}, status=404)
    
    async def get_registered_agents(self, request):
        """등록된 에이전트 목록"""
        return web.json_response({
            "agents": list(self.registered_agents.values()),
            "total_count": len(self.registered_agents),
            "timestamp": datetime.now().isoformat()
        })
    
    async def get_events(self, request):
        """이벤트 히스토리"""
        limit = int(request.query.get('limit', 50))
        recent_events = self.event_history[-limit:]
        
        return web.json_response({
            "events": [asdict(event) for event in recent_events],
            "total_count": len(self.event_history),
            "returned_count": len(recent_events),
            "timestamp": datetime.now().isoformat()
        })
    
    async def broadcast_notification(self, request):
        """알림 브로드캐스트"""
        try:
            notification_data = await request.json()
            source_agent = notification_data.get("source_agent", "unknown")
            message = notification_data.get("message", "")
            
            logger.info(f"📢 브로드캐스트: {source_agent} - {message}")
            
            # 모든 에이전트에게 알림 전송
            await self.notify_all_agents(source_agent, {
                "type": "broadcast",
                "message": message,
                "timestamp": datetime.now().isoformat()
            })
            
            return web.json_response({"success": True, "message": "브로드캐스트 완료"})
            
        except Exception as e:
            logger.error(f"❌ 브로드캐스트 실패: {str(e)}")
            return web.json_response({"error": "broadcast_failed", "message": str(e)}, status=500)
    
    async def notify_other_agents(self, source_agent: str, event: StateEvent):
        """다른 에이전트들에게 상태 변경 알림"""
        notification_tasks = []
        
        for agent_id, agent_info in self.registered_agents.items():
            if agent_id != source_agent:  # 자신에게는 알림하지 않음
                task = self.send_notification_to_agent(agent_info, event)
                notification_tasks.append(task)
        
        # 모든 알림을 병렬로 전송
        if notification_tasks:
            await asyncio.gather(*notification_tasks, return_exceptions=True)
    
    async def notify_all_agents(self, source_agent: str, data: Dict[str, Any]):
        """모든 에이전트에게 알림"""
        notification_tasks = []
        
        for agent_id, agent_info in self.registered_agents.items():
            if agent_id != source_agent:
                task = self.send_notification_to_agent(agent_info, data)
                notification_tasks.append(task)
        
        if notification_tasks:
            await asyncio.gather(*notification_tasks, return_exceptions=True)
    
    async def send_notification_to_agent(self, agent_info: Dict[str, Any], data: Any):
        """개별 에이전트에게 알림 전송"""
        try:
            endpoint = agent_info["endpoint"]
            timeout = ClientTimeout(total=5)
            
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(f"{endpoint}/notifications", json=data) as response:
                    if response.status == 200:
                        logger.debug(f"✅ 알림 전송 성공: {agent_info['agent_id']}")
                        # 마지막 응답 시간 업데이트
                        agent_info["last_seen"] = datetime.now().isoformat()
                    else:
                        logger.warning(f"⚠️ 알림 전송 실패: {agent_info['agent_id']} ({response.status})")
                        
        except Exception as e:
            logger.warning(f"⚠️ 에이전트 {agent_info['agent_id']} 알림 전송 오류: {str(e)}")
            # 에이전트가 응답하지 않으면 비활성 상태로 표시
            agent_info["status"] = "inactive"
    
    async def start_server(self):
        """서버 시작"""
        logger.info(f"🚀 State Manager 시작 (포트 {self.port})")
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, 'localhost', self.port)
        await site.start()
        logger.info(f"✅ 서버가 http://localhost:{self.port}에서 실행 중")
        return runner


class AnalysisAgentBase:
    """
    분석 에이전트 기본 클래스
    
    모든 분석 에이전트가 상속받는 공통 기능을 제공합니다.
    """
    
    def __init__(self, agent_id: str, agent_type: str, port: int, state_manager_port: int = 9000):
        self.agent_id = agent_id
        self.agent_type = agent_type
        self.port = port
        self.state_manager_port = state_manager_port
        self.state_manager_url = f"http://localhost:{state_manager_port}"
        
        self.app = web.Application()
        self.setup_common_routes()
        
        # 로컬 상태 (캐시)
        self.local_state_version = 0
        self.local_state = None
        
        # 상태 동기화 태스크
        self.sync_task = None
    
    def setup_common_routes(self):
        """공통 API 라우트 설정"""
        self.app.router.add_get('/health', self.health_check)
        self.app.router.add_post('/notifications', self.handle_notification)
        self.app.router.add_get('/status', self.get_status)
        self.app.router.add_post('/analyze', self.perform_analysis)
    
    async def health_check(self, request):
        """헬스 체크"""
        return web.json_response({
            "status": "healthy",
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "timestamp": datetime.now().isoformat(),
            "port": self.port,
            "local_state_version": self.local_state_version
        })
    
    async def handle_notification(self, request):
        """상태 변경 알림 처리"""
        try:
            notification = await request.json()
            logger.info(f"📨 알림 수신: {self.agent_id}")
            
            # 상태 버전 확인 및 동기화
            if isinstance(notification, dict) and "version" in notification:
                remote_version = notification["version"]
                if remote_version > self.local_state_version:
                    logger.info(f"🔄 상태 동기화 필요: 로컬 {self.local_state_version} < 원격 {remote_version}")
                    await self.sync_state()
            
            return web.json_response({"success": True, "message": "알림 처리 완료"})
            
        except Exception as e:
            logger.error(f"❌ 알림 처리 실패 ({self.agent_id}): {str(e)}")
            return web.json_response({"error": "notification_failed", "message": str(e)}, status=500)
    
    async def get_status(self, request):
        """에이전트 상태"""
        state_manager_connected = await self.check_state_manager_connection()
        
        return web.json_response({
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "local_state_version": self.local_state_version,
            "state_manager_connected": state_manager_connected,
            "last_analysis": getattr(self, 'last_analysis_time', None),
            "timestamp": datetime.now().isoformat()
        })
    
    async def perform_analysis(self, request):
        """분석 수행 (하위 클래스에서 구현)"""
        return web.json_response({
            "error": "not_implemented",
            "message": "하위 클래스에서 구현해야 합니다"
        }, status=501)
    
    async def register_with_state_manager(self):
        """State Manager에 등록"""
        try:
            registration_data = {
                "agent_id": self.agent_id,
                "agent_type": self.agent_type,
                "endpoint": f"http://localhost:{self.port}"
            }
            
            timeout = ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    f"{self.state_manager_url}/agents/register", 
                    json=registration_data
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        logger.info(f"✅ State Manager 등록 성공: {self.agent_id}")
                        
                        # 초기 상태 동기화
                        self.local_state_version = result.get("current_state_version", 0)
                        await self.sync_state()
                        
                        return True
                    else:
                        error_text = await response.text()
                        logger.error(f"❌ State Manager 등록 실패: {response.status} - {error_text}")
                        return False
                        
        except Exception as e:
            logger.error(f"❌ State Manager 등록 중 오류 ({self.agent_id}): {str(e)}")
            return False
    
    async def check_state_manager_connection(self):
        """State Manager 연결 상태 확인"""
        try:
            timeout = ClientTimeout(total=3)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(f"{self.state_manager_url}/health") as response:
                    return response.status == 200
        except Exception:
            return False
    
    async def sync_state(self):
        """상태 동기화"""
        try:
            timeout = ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(f"{self.state_manager_url}/state") as response:
                    if response.status == 200:
                        result = await response.json()
                        self.local_state = result["state"]
                        self.local_state_version = self.local_state["version"]
                        logger.info(f"🔄 상태 동기화 완료: {self.agent_id} (버전 {self.local_state_version})")
                        return True
                    else:
                        logger.error(f"❌ 상태 동기화 실패: {response.status}")
                        return False
                        
        except Exception as e:
            logger.error(f"❌ 상태 동기화 중 오류 ({self.agent_id}): {str(e)}")
            return False
    
    async def update_shared_state(self, updates: Dict[str, Any]):
        """공유 상태 업데이트"""
        try:
            update_data = {
                "source_agent": self.agent_id,
                "updates": updates,
                "expected_version": self.local_state_version
            }
            
            timeout = ClientTimeout(total=15)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    f"{self.state_manager_url}/state/update",
                    json=update_data
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        self.local_state_version = result["new_version"]
                        logger.info(f"✅ 상태 업데이트 성공: {self.agent_id} (버전 {self.local_state_version})")
                        return True
                    elif response.status == 409:  # 버전 충돌
                        logger.warning(f"⚠️ 버전 충돌 발생 - 상태 재동기화: {self.agent_id}")
                        await self.sync_state()
                        return False
                    else:
                        error_text = await response.text()
                        logger.error(f"❌ 상태 업데이트 실패: {response.status} - {error_text}")
                        return False
                        
        except Exception as e:
            logger.error(f"❌ 상태 업데이트 중 오류 ({self.agent_id}): {str(e)}")
            return False
    
    async def start_server(self):
        """서버 시작"""
        logger.info(f"🚀 {self.agent_type} 시작: {self.agent_id} (포트 {self.port})")
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, 'localhost', self.port)
        await site.start()
        logger.info(f"✅ 서버가 http://localhost:{self.port}에서 실행 중")
        
        # State Manager에 등록
        registration_success = await self.register_with_state_manager()
        if not registration_success:
            logger.warning(f"⚠️ State Manager 등록 실패, 독립 모드로 실행: {self.agent_id}")
        
        return runner


class TechnicalAnalysisAgent(AnalysisAgentBase):
    """기술적 분석 에이전트"""
    
    def __init__(self, port: int, state_manager_port: int = 9000):
        super().__init__(
            agent_id="technical_agent",
            agent_type="TechnicalAnalysisAgent", 
            port=port,
            state_manager_port=state_manager_port
        )
    
    async def perform_analysis(self, request):
        """기술적 분석 수행"""
        logger.info(f"📈 기술적 분석 시작: {self.agent_id}")
        
        # 현재 상태 확인
        if not self.local_state:
            await self.sync_state()
        
        # 분석 시간 시뮬레이션
        await asyncio.sleep(2)
        
        # 기술적 분석 수행 (모의)
        technical_result = {
            "rsi": 58.3,
            "macd": {"value": 1.2, "signal": "매수"},
            "moving_averages": {
                "ma_5": 182000,
                "ma_20": 179000,
                "ma_60": 175000,
                "trend": "상승"
            },
            "bollinger_bands": {
                "upper": 185000,
                "middle": 179000,
                "lower": 173000,
                "position": "중간대"
            },
            "volume_analysis": {
                "volume_trend": "증가",
                "volume_ratio": 1.25
            },
            "technical_score": 72.5,
            "analysis_timestamp": datetime.now().isoformat(),
            "analyst": self.agent_id
        }
        
        # 공유 상태 업데이트
        updates = {"technical_analysis": technical_result}
        update_success = await self.update_shared_state(updates)
        
        self.last_analysis_time = datetime.now().isoformat()
        
        if update_success:
            logger.info(f"✅ 기술적 분석 완료 및 상태 업데이트: {self.agent_id}")
            return web.json_response({
                "success": True,
                "analysis": technical_result,
                "state_updated": True,
                "new_version": self.local_state_version
            })
        else:
            logger.warning(f"⚠️ 기술적 분석 완료되었으나 상태 업데이트 실패: {self.agent_id}")
            return web.json_response({
                "success": True,
                "analysis": technical_result,
                "state_updated": False,
                "warning": "상태 업데이트 실패"
            })


class FundamentalAnalysisAgent(AnalysisAgentBase):
    """기본적 분석 에이전트"""
    
    def __init__(self, port: int, state_manager_port: int = 9000):
        super().__init__(
            agent_id="fundamental_agent",
            agent_type="FundamentalAnalysisAgent",
            port=port,
            state_manager_port=state_manager_port
        )
    
    async def perform_analysis(self, request):
        """기본적 분석 수행"""
        logger.info(f"💰 기본적 분석 시작: {self.agent_id}")
        
        # 현재 상태 확인
        if not self.local_state:
            await self.sync_state()
        
        # 분석 시간 시뮬레이션
        await asyncio.sleep(2.5)
        
        # 기본적 분석 수행 (모의)
        fundamental_result = {
            "financial_ratios": {
                "per": 7.8,
                "pbr": 0.8,
                "roe": 9.2,
                "roa": 4.5,
                "debt_ratio": 28.3,
                "current_ratio": 1.92
            },
            "business_metrics": {
                "revenue_growth": 8.5,
                "profit_growth": 12.3,
                "market_share": 0.42,
                "global_ranking": 5
            },
            "industry_analysis": {
                "sector": "자동차",
                "industry_outlook": "긍정적",
                "competitive_position": "우수",
                "ev_transition_readiness": "높음"
            },
            "valuation": {
                "intrinsic_value": 195000,
                "target_price": 210000,
                "valuation_method": "DCF + Multiples"
            },
            "fundamental_score": 78.2,
            "analysis_timestamp": datetime.now().isoformat(),
            "analyst": self.agent_id
        }
        
        # 공유 상태 업데이트
        updates = {"fundamental_analysis": fundamental_result}
        update_success = await self.update_shared_state(updates)
        
        self.last_analysis_time = datetime.now().isoformat()
        
        if update_success:
            logger.info(f"✅ 기본적 분석 완료 및 상태 업데이트: {self.agent_id}")
            return web.json_response({
                "success": True,
                "analysis": fundamental_result,
                "state_updated": True,
                "new_version": self.local_state_version
            })
        else:
            logger.warning(f"⚠️ 기본적 분석 완료되었으나 상태 업데이트 실패: {self.agent_id}")
            return web.json_response({
                "success": True,
                "analysis": fundamental_result,
                "state_updated": False,
                "warning": "상태 업데이트 실패"
            })


class NewsAnalysisAgent(AnalysisAgentBase):
    """뉴스 분석 에이전트"""
    
    def __init__(self, port: int, state_manager_port: int = 9000):
        super().__init__(
            agent_id="news_agent",
            agent_type="NewsAnalysisAgent",
            port=port,
            state_manager_port=state_manager_port
        )
    
    async def perform_analysis(self, request):
        """뉴스 분석 수행"""
        logger.info(f"📰 뉴스 분석 시작: {self.agent_id}")
        
        # 현재 상태 확인
        if not self.local_state:
            await self.sync_state()
        
        # 분석 시간 시뮬레이션
        await asyncio.sleep(3)
        
        # 뉴스 분석 수행 (모의)
        news_result = {
            "news_summary": {
                "total_articles": 32,
                "positive_count": 22,
                "neutral_count": 7,
                "negative_count": 3,
                "sentiment_score": 0.78
            },
            "key_topics": [
                "전기차 시장 확대",
                "배터리 기술 혁신",
                "글로벌 진출 가속화",
                "친환경 모빌리티 전환",
                "자율주행 기술 개발"
            ],
            "market_impact": {
                "short_term_impact": "긍정적",
                "long_term_outlook": "매우 긍정적",
                "key_catalysts": [
                    "전기차 판매 목표 상향",
                    "배터리 공급망 확보",
                    "글로벌 파트너십 확대"
                ]
            },
            "analyst_coverage": {
                "buy_recommendations": 15,
                "hold_recommendations": 4,
                "sell_recommendations": 1,
                "average_target_price": 205000
            },
            "news_score": 76.8,
            "analysis_timestamp": datetime.now().isoformat(),
            "analyst": self.agent_id
        }
        
        # 공유 상태 업데이트
        updates = {"news_analysis": news_result}
        update_success = await self.update_shared_state(updates)
        
        self.last_analysis_time = datetime.now().isoformat()
        
        if update_success:
            logger.info(f"✅ 뉴스 분석 완료 및 상태 업데이트: {self.agent_id}")
            return web.json_response({
                "success": True,
                "analysis": news_result,
                "state_updated": True,
                "new_version": self.local_state_version
            })
        else:
            logger.warning(f"⚠️ 뉴스 분석 완료되었으나 상태 업데이트 실패: {self.agent_id}")
            return web.json_response({
                "success": True,
                "analysis": news_result,
                "state_updated": False,
                "warning": "상태 업데이트 실패"
            })


async def run_state_manager(port: int):
    """State Manager 실행"""
    manager = StateManager(port)
    runner = await manager.start_server()
    
    try:
        print(f"\n{'='*60}")
        print(f"  🏛️ State Manager 실행 중 (포트 {port})")
        print(f"{'='*60}")
        print(f"API 엔드포인트:")
        print(f"  GET  /health - 헬스 체크")
        print(f"  GET  /state - 현재 상태 조회")
        print(f"  POST /state/update - 상태 업데이트")
        print(f"  POST /agents/register - 에이전트 등록")
        print(f"  GET  /agents - 등록된 에이전트 목록")
        print(f"  GET  /events - 이벤트 히스토리")
        print(f"\n💡 테스트:")
        print(f"  curl http://localhost:{port}/health")
        print(f"  curl http://localhost:{port}/state")
        print(f"\n⏹️ 종료: Ctrl+C")
        
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("State Manager 종료 중...")
    finally:
        await runner.cleanup()


async def run_analysis_agent(agent_type: str, port: int, state_manager_port: int):
    """분석 에이전트 실행"""
    if agent_type == "technical":
        agent = TechnicalAnalysisAgent(port, state_manager_port)
    elif agent_type == "fundamental":
        agent = FundamentalAnalysisAgent(port, state_manager_port)
    elif agent_type == "news":
        agent = NewsAnalysisAgent(port, state_manager_port)
    else:
        raise ValueError(f"알 수 없는 에이전트 타입: {agent_type}")
    
    runner = await agent.start_server()
    
    try:
        print(f"\n{'='*60}")
        print(f"  🤖 {agent.agent_type} 실행 중 (포트 {port})")
        print(f"{'='*60}")
        print(f"State Manager: http://localhost:{state_manager_port}")
        print(f"API 엔드포인트:")
        print(f"  GET  /health - 헬스 체크")
        print(f"  GET  /status - 상태 조회")
        print(f"  POST /analyze - 분석 수행")
        print(f"  POST /notifications - 알림 수신")
        print(f"\n💡 테스트:")
        print(f"  curl http://localhost:{port}/health")
        print(f"  curl -X POST http://localhost:{port}/analyze")
        print(f"\n⏹️ 종료: Ctrl+C")
        
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info(f"{agent.agent_type} 종료 중...")
    finally:
        await runner.cleanup()


async def demonstrate_synchronization():
    """상태 동기화 데모"""
    print(f"\n{'='*60}")
    print(f"  🔄 Agent 상태 동기화 데모")
    print(f"{'='*60}")
    
    state_manager_port = 9000
    technical_port = 9001
    fundamental_port = 9002
    news_port = 9003
    
    print("🚀 모든 에이전트를 시작합니다...")
    
    # 에이전트 인스턴스 생성
    manager = StateManager(state_manager_port)
    technical = TechnicalAnalysisAgent(technical_port, state_manager_port)
    fundamental = FundamentalAnalysisAgent(fundamental_port, state_manager_port)
    news = NewsAnalysisAgent(news_port, state_manager_port)
    
    # 서버 시작
    runners = []
    runners.append(await manager.start_server())
    
    # 에이전트들 순차 시작 (등록 시간 확보)
    await asyncio.sleep(1)
    runners.append(await technical.start_server())
    await asyncio.sleep(1)
    runners.append(await fundamental.start_server())
    await asyncio.sleep(1) 
    runners.append(await news.start_server())
    
    try:
        # 연결 확인
        await asyncio.sleep(2)
        
        print("✅ 모든 에이전트 시작 완료")
        print(f"\n📊 현대차(005380) 상태 동기화 데모 시작...")
        
        # 순차 분석 (상태 동기화 확인)
        timeout = ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            
            print(f"\n1️⃣ 기술적 분석 수행...")
            async with session.post(f"http://localhost:{technical_port}/analyze") as response:
                if response.status == 200:
                    result = await response.json()
                    print(f"   ✅ 기술적 분석 완료 (버전: {result.get('new_version', 'N/A')})")
                    print(f"   점수: {result['analysis']['technical_score']}/100")
            
            await asyncio.sleep(2)
            
            print(f"\n2️⃣ 기본적 분석 수행...")
            async with session.post(f"http://localhost:{fundamental_port}/analyze") as response:
                if response.status == 200:
                    result = await response.json()
                    print(f"   ✅ 기본적 분석 완료 (버전: {result.get('new_version', 'N/A')})")
                    print(f"   점수: {result['analysis']['fundamental_score']}/100")
            
            await asyncio.sleep(2)
            
            print(f"\n3️⃣ 뉴스 분석 수행...")
            async with session.post(f"http://localhost:{news_port}/analyze") as response:
                if response.status == 200:
                    result = await response.json()
                    print(f"   ✅ 뉴스 분석 완료 (버전: {result.get('new_version', 'N/A')})")
                    print(f"   점수: {result['analysis']['news_score']}/100")
            
            await asyncio.sleep(1)
            
            # 최종 동기화된 상태 확인
            print(f"\n4️⃣ 최종 동기화 상태 확인...")
            async with session.get(f"http://localhost:{state_manager_port}/state") as response:
                if response.status == 200:
                    final_state = await response.json()
                    state_data = final_state["state"]
                    
                    print(f"\n🎯 최종 동기화 결과:")
                    print(f"   종목: {state_data['company_name']} ({state_data['symbol']})")
                    print(f"   상태 버전: {state_data['version']}")
                    print(f"   참여 에이전트: {len(state_data['participating_agents'])}개")
                    
                    analyses = []
                    if state_data.get('technical_analysis'):
                        analyses.append(f"기술적: {state_data['technical_analysis']['technical_score']:.1f}")
                    if state_data.get('fundamental_analysis'):
                        analyses.append(f"기본적: {state_data['fundamental_analysis']['fundamental_score']:.1f}")
                    if state_data.get('news_analysis'):
                        analyses.append(f"뉴스: {state_data['news_analysis']['news_score']:.1f}")
                    
                    print(f"   분석 점수: {', '.join(analyses)}")
                    
                    if analyses:
                        scores = [float(a.split(':')[1].strip()) for a in analyses]
                        avg_score = sum(scores) / len(scores)
                        
                        if avg_score >= 80:
                            opinion = "적극 매수"
                        elif avg_score >= 70:
                            opinion = "매수"
                        elif avg_score >= 60:
                            opinion = "보유"
                        else:
                            opinion = "관망"
                        
                        print(f"   종합 점수: {avg_score:.1f}/100")
                        print(f"   투자 의견: {opinion}")
                    
                    print(f"\n✅ 상태 동기화 데모 성공!")
        
        print(f"\n⏹️ 데모 종료를 위해 Ctrl+C를 누르세요...")
        
        while True:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        print("\n🔚 데모 종료 중...")
    finally:
        for runner in runners:
            await runner.cleanup()


def main():
    parser = argparse.ArgumentParser(description="Agent 상태 동기화 데모")
    parser.add_argument("--role", choices=["state", "technical", "fundamental", "news", "demo"],
                       help="실행할 에이전트 역할")
    parser.add_argument("--port", type=int, default=9000,
                       help="에이전트 포트 번호")
    parser.add_argument("--state-port", type=int, default=9000,
                       help="State Manager 포트 번호")
    
    args = parser.parse_args()
    
    if args.role == "state":
        print("🔄 Agent 상태 동기화 학습을 시작합니다!")
        print("이 예제는 여러 에이전트 간 상태 동기화를 보여줍니다.")
        asyncio.run(run_state_manager(args.port))
    elif args.role in ["technical", "fundamental", "news"]:
        asyncio.run(run_analysis_agent(args.role, args.port, args.state_port))
    elif args.role == "demo":
        print("🔄 Agent 상태 동기화 학습을 시작합니다!")
        print("이 예제는 여러 에이전트 간 상태 동기화를 보여줍니다.")
        asyncio.run(demonstrate_synchronization())
    else:
        print("사용법:")
        print("  State Manager:    python 3_2_state_synchronization.py --role state --port 9000")
        print("  Technical Agent:  python 3_2_state_synchronization.py --role technical --port 9001")
        print("  Fundamental:      python 3_2_state_synchronization.py --role fundamental --port 9002")
        print("  News Agent:       python 3_2_state_synchronization.py --role news --port 9003")
        print("  동기화 데모:       python 3_2_state_synchronization.py --role demo")


if __name__ == "__main__":
    main()