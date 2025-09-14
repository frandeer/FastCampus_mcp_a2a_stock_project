#!/usr/bin/env python3
"""
3.4 멀티 에이전트 협업 - KOSPI 상위 10개 종목 포트폴리오

다중 에이전트 협업을 학습하는 최종 예제입니다.
KOSPI 상위 10개 종목을 5개의 전문 에이전트가 협업하여 분석하고,
최적의 포트폴리오를 구성하는 완전한 시나리오를 구현합니다.

학습 목표:
- 복수 에이전트 간 역할 분담과 협업
- 워크플로우 조정 및 작업 스케줄링
- 병렬 처리와 결과 통합
- 실전 투자 시스템 구축 경험
- 대규모 에이전트 시스템 아키텍처

에이전트 구성:
- Coordinator Agent: 전체 협업 조정 및 워크플로우 관리
- Data Collector Agent: 다수 종목의 데이터 수집 전담
- Technical Analysis Agent: 기술적 분석 전담
- Fundamental Analysis Agent: 기본적 분석 전담  
- Portfolio Manager Agent: 포트폴리오 관리 및 최종 의사결정

분석 대상: KOSPI 상위 10개 종목

실행 방법:
python 3_4_multi_agent_collaboration.py --role [coordinator|collector|technical|fundamental|portfolio|demo] --port [포트번호]
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
import random
import uuid

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """작업 상태"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class AgentRole(Enum):
    """에이전트 역할"""
    COORDINATOR = "coordinator"
    DATA_COLLECTOR = "data_collector"
    TECHNICAL_ANALYST = "technical_analyst"
    FUNDAMENTAL_ANALYST = "fundamental_analyst"
    PORTFOLIO_MANAGER = "portfolio_manager"


@dataclass
class Task:
    """작업 정의"""
    task_id: str
    task_type: str
    assigned_to: str
    status: TaskStatus
    input_data: Dict[str, Any]
    output_data: Optional[Dict[str, Any]]
    created_at: str
    started_at: Optional[str]
    completed_at: Optional[str]
    error_message: Optional[str]


@dataclass
class AgentInfo:
    """에이전트 정보"""
    agent_id: str
    role: AgentRole
    endpoint: str
    status: str
    capabilities: List[str]
    current_load: int
    max_capacity: int


# KOSPI 상위 10개 종목 (시가총액 기준)
KOSPI_TOP_10 = [
    {"symbol": "005930", "name": "삼성전자", "sector": "기술"},
    {"symbol": "000660", "name": "SK하이닉스", "sector": "반도체"},
    {"symbol": "207940", "name": "삼성바이오로직스", "sector": "바이오"},
    {"symbol": "005380", "name": "현대차", "sector": "자동차"},
    {"symbol": "006400", "name": "삼성SDI", "sector": "배터리"},
    {"symbol": "051910", "name": "LG화학", "sector": "화학"},
    {"symbol": "035420", "name": "NAVER", "sector": "인터넷"},
    {"symbol": "005490", "name": "POSCO홀딩스", "sector": "철강"},
    {"symbol": "068270", "name": "셀트리온", "sector": "바이오"},
    {"symbol": "035720", "name": "카카오", "sector": "인터넷"}
]


class BaseAgent:
    """
    기본 에이전트 클래스
    
    모든 협업 에이전트가 상속받는 공통 기능을 제공합니다.
    """
    
    def __init__(self, agent_id: str, role: AgentRole, port: int):
        self.agent_id = agent_id
        self.role = role
        self.port = port
        self.app = web.Application()
        self.setup_common_routes()
        
        # 에이전트 상태
        self.status = "active"
        self.current_load = 0
        self.max_capacity = 5
        self.active_tasks: Dict[str, Task] = {}
        
        # 다른 에이전트 정보
        self.known_agents: Dict[str, AgentInfo] = {}
    
    def setup_common_routes(self):
        """공통 API 라우트 설정"""
        self.app.router.add_get('/health', self.health_check)
        self.app.router.add_get('/info', self.get_agent_info)
        self.app.router.add_get('/status', self.get_status)
        self.app.router.add_post('/tasks', self.accept_task)
        self.app.router.add_get('/tasks/{task_id}', self.get_task_status)
        self.app.router.add_post('/register_agent', self.register_agent)
    
    async def health_check(self, request):
        """헬스 체크"""
        return web.json_response({
            "status": "healthy",
            "agent_id": self.agent_id,
            "role": self.role.value,
            "timestamp": datetime.now().isoformat(),
            "current_load": self.current_load,
            "max_capacity": self.max_capacity
        })
    
    async def get_agent_info(self, request):
        """에이전트 정보 반환"""
        return web.json_response({
            "agent_id": self.agent_id,
            "role": self.role.value,
            "endpoint": f"http://localhost:{self.port}",
            "capabilities": self.get_capabilities(),
            "current_load": self.current_load,
            "max_capacity": self.max_capacity,
            "status": self.status
        })
    
    async def get_status(self, request):
        """상태 조회"""
        return web.json_response({
            "agent_id": self.agent_id,
            "status": self.status,
            "current_load": self.current_load,
            "active_tasks": len(self.active_tasks),
            "known_agents": len(self.known_agents),
            "timestamp": datetime.now().isoformat()
        })
    
    async def accept_task(self, request):
        """작업 수락"""
        try:
            task_data = await request.json()
            
            # 용량 체크
            if self.current_load >= self.max_capacity:
                return web.json_response({
                    "accepted": False,
                    "reason": "capacity_exceeded",
                    "current_load": self.current_load,
                    "max_capacity": self.max_capacity
                }, status=503)
            
            # Task 객체 생성
            task = Task(
                task_id=task_data["task_id"],
                task_type=task_data["task_type"],
                assigned_to=self.agent_id,
                status=TaskStatus.PENDING,
                input_data=task_data["input_data"],
                output_data=None,
                created_at=datetime.now().isoformat(),
                started_at=None,
                completed_at=None,
                error_message=None
            )
            
            self.active_tasks[task.task_id] = task
            self.current_load += 1
            
            logger.info(f"📋 작업 수락: {self.agent_id} - {task.task_type} ({task.task_id})")
            
            # 비동기로 작업 실행
            asyncio.create_task(self.execute_task(task))
            
            return web.json_response({
                "accepted": True,
                "task_id": task.task_id,
                "estimated_duration": self.estimate_task_duration(task),
                "agent_id": self.agent_id
            })
            
        except Exception as e:
            logger.error(f"❌ 작업 수락 실패 ({self.agent_id}): {str(e)}")
            return web.json_response({
                "accepted": False,
                "reason": "task_acceptance_error",
                "error": str(e)
            }, status=500)
    
    async def get_task_status(self, request):
        """작업 상태 조회"""
        task_id = request.match_info['task_id']
        
        if task_id in self.active_tasks:
            task = self.active_tasks[task_id]
            return web.json_response(asdict(task))
        else:
            return web.json_response({
                "error": "task_not_found",
                "task_id": task_id
            }, status=404)
    
    async def register_agent(self, request):
        """다른 에이전트 등록"""
        try:
            agent_data = await request.json()
            agent_info = AgentInfo(
                agent_id=agent_data["agent_id"],
                role=AgentRole(agent_data["role"]),
                endpoint=agent_data["endpoint"],
                status=agent_data["status"],
                capabilities=agent_data["capabilities"],
                current_load=agent_data["current_load"],
                max_capacity=agent_data["max_capacity"]
            )
            
            self.known_agents[agent_info.agent_id] = agent_info
            logger.info(f"🤖 에이전트 등록: {agent_info.agent_id} ({agent_info.role.value})")
            
            return web.json_response({"success": True, "message": "에이전트 등록 완료"})
            
        except Exception as e:
            logger.error(f"❌ 에이전트 등록 실패: {str(e)}")
            return web.json_response({"error": "registration_failed", "message": str(e)}, status=500)
    
    def get_capabilities(self) -> List[str]:
        """에이전트 능력 반환 (하위 클래스에서 구현)"""
        return ["base_functionality"]
    
    def estimate_task_duration(self, task: Task) -> int:
        """작업 소요 시간 추정 (초)"""
        return 30  # 기본 30초
    
    async def execute_task(self, task: Task):
        """작업 실행 (하위 클래스에서 구현)"""
        try:
            task.status = TaskStatus.IN_PROGRESS
            task.started_at = datetime.now().isoformat()
            
            logger.info(f"🚀 작업 시작: {self.agent_id} - {task.task_type}")
            
            # 기본 작업 시뮬레이션
            await asyncio.sleep(2)
            
            task.output_data = {"message": "기본 작업 완료", "agent": self.agent_id}
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now().isoformat()
            
            logger.info(f"✅ 작업 완료: {self.agent_id} - {task.task_type}")
            
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error_message = str(e)
            task.completed_at = datetime.now().isoformat()
            logger.error(f"❌ 작업 실패: {self.agent_id} - {str(e)}")
        finally:
            self.current_load -= 1
    
    async def start_server(self):
        """서버 시작"""
        logger.info(f"🚀 {self.role.value} 시작: {self.agent_id} (포트 {self.port})")
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, 'localhost', self.port)
        await site.start()
        logger.info(f"✅ 서버가 http://localhost:{self.port}에서 실행 중")
        return runner


class CoordinatorAgent(BaseAgent):
    """
    협업 조정 에이전트
    
    전체 워크플로우를 관리하고 다른 에이전트들의 협업을 조정합니다.
    """
    
    def __init__(self, port: int):
        super().__init__("coordinator_001", AgentRole.COORDINATOR, port)
        self.app.router.add_post('/start_analysis', self.start_portfolio_analysis)
        self.app.router.add_get('/workflow/{workflow_id}', self.get_workflow_status)
        
        # 워크플로우 관리
        self.active_workflows: Dict[str, Dict[str, Any]] = {}
        self.default_agent_ports = {
            AgentRole.DATA_COLLECTOR: 7001,
            AgentRole.TECHNICAL_ANALYST: 7002,
            AgentRole.FUNDAMENTAL_ANALYST: 7003,
            AgentRole.PORTFOLIO_MANAGER: 7004
        }
    
    def get_capabilities(self) -> List[str]:
        return ["workflow_management", "task_coordination", "agent_discovery", "result_aggregation"]
    
    async def start_portfolio_analysis(self, request):
        """포트폴리오 분석 워크플로우 시작"""
        try:
            workflow_id = str(uuid.uuid4())[:8]
            
            logger.info(f"🎯 포트폴리오 분석 워크플로우 시작: {workflow_id}")
            
            # 워크플로우 상태 초기화
            workflow = {
                "workflow_id": workflow_id,
                "status": "initializing",
                "started_at": datetime.now().isoformat(),
                "stocks": KOSPI_TOP_10,
                "tasks": {},
                "results": {},
                "timeline": []
            }
            
            self.active_workflows[workflow_id] = workflow
            
            # 비동기로 워크플로우 실행
            asyncio.create_task(self.execute_portfolio_workflow(workflow_id))
            
            return web.json_response({
                "success": True,
                "workflow_id": workflow_id,
                "message": "포트폴리오 분석 워크플로우 시작됨",
                "stocks_count": len(KOSPI_TOP_10),
                "estimated_duration": "5-10분"
            })
            
        except Exception as e:
            logger.error(f"❌ 워크플로우 시작 실패: {str(e)}")
            return web.json_response({"error": "workflow_start_failed", "message": str(e)}, status=500)
    
    async def get_workflow_status(self, request):
        """워크플로우 상태 조회"""
        workflow_id = request.match_info['workflow_id']
        
        if workflow_id in self.active_workflows:
            return web.json_response(self.active_workflows[workflow_id])
        else:
            return web.json_response({"error": "workflow_not_found"}, status=404)
    
    async def execute_portfolio_workflow(self, workflow_id: str):
        """포트폴리오 분석 워크플로우 실행"""
        workflow = self.active_workflows[workflow_id]
        
        try:
            # 1단계: 에이전트 발견 및 등록
            await self.discover_and_register_agents(workflow)
            
            # 2단계: 데이터 수집
            await self.coordinate_data_collection(workflow)
            
            # 3단계: 병렬 분석
            await self.coordinate_parallel_analysis(workflow)
            
            # 4단계: 포트폴리오 구성
            await self.coordinate_portfolio_construction(workflow)
            
            # 5단계: 결과 취합
            await self.finalize_workflow(workflow)
            
        except Exception as e:
            workflow["status"] = "failed"
            workflow["error"] = str(e)
            workflow["completed_at"] = datetime.now().isoformat()
            logger.error(f"❌ 워크플로우 실행 실패: {str(e)}")
    
    async def discover_and_register_agents(self, workflow: Dict[str, Any]):
        """에이전트 발견 및 등록"""
        workflow["status"] = "discovering_agents"
        workflow["timeline"].append({"step": "agent_discovery", "started_at": datetime.now().isoformat()})
        
        logger.info("🔍 에이전트 발견 중...")
        
        discovered_agents = {}
        
        # 각 역할별 에이전트 발견
        for role, port in self.default_agent_ports.items():
            try:
                timeout = ClientTimeout(total=5)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get(f"http://localhost:{port}/info") as response:
                        if response.status == 200:
                            agent_info = await response.json()
                            discovered_agents[role.value] = agent_info
                            logger.info(f"✅ 에이전트 발견: {agent_info['agent_id']} ({role.value})")
            except Exception:
                logger.warning(f"⚠️ 에이전트 연결 실패: {role.value} (포트 {port})")
        
        workflow["discovered_agents"] = discovered_agents
        workflow["timeline"][-1]["completed_at"] = datetime.now().isoformat()
        workflow["timeline"][-1]["discovered_count"] = len(discovered_agents)
        
        if len(discovered_agents) < 3:  # 최소 3개 에이전트 필요
            raise Exception(f"충분한 에이전트가 발견되지 않음: {len(discovered_agents)}/4")
    
    async def coordinate_data_collection(self, workflow: Dict[str, Any]):
        """데이터 수집 조정"""
        workflow["status"] = "collecting_data"
        workflow["timeline"].append({"step": "data_collection", "started_at": datetime.now().isoformat()})
        
        logger.info("📊 데이터 수집 시작...")
        
        if "data_collector" not in workflow["discovered_agents"]:
            raise Exception("데이터 수집 에이전트가 없습니다")
        
        collector_info = workflow["discovered_agents"]["data_collector"]
        collector_endpoint = f"http://localhost:{self.default_agent_ports[AgentRole.DATA_COLLECTOR]}"
        
        # 데이터 수집 작업 생성
        task_id = f"collect_data_{workflow['workflow_id']}"
        task_data = {
            "task_id": task_id,
            "task_type": "bulk_data_collection",
            "input_data": {
                "stocks": workflow["stocks"],
                "data_types": ["price", "volume", "financial", "news"]
            }
        }
        
        # 작업 전송
        result = await self.send_task_to_agent(collector_endpoint, task_data)
        
        if result["accepted"]:
            workflow["tasks"]["data_collection"] = task_id
            
            # 작업 완료 대기
            await self.wait_for_task_completion(collector_endpoint, task_id, timeout=120)
            
            # 결과 수집
            task_result = await self.get_task_result(collector_endpoint, task_id)
            workflow["results"]["data_collection"] = task_result["output_data"]
            
            workflow["timeline"][-1]["completed_at"] = datetime.now().isoformat()
            workflow["timeline"][-1]["status"] = "completed"
            
            logger.info("✅ 데이터 수집 완료")
        else:
            raise Exception(f"데이터 수집 작업 수락 실패: {result}")
    
    async def coordinate_parallel_analysis(self, workflow: Dict[str, Any]):
        """병렬 분석 조정"""
        workflow["status"] = "analyzing"
        workflow["timeline"].append({"step": "parallel_analysis", "started_at": datetime.now().isoformat()})
        
        logger.info("🔍 병렬 분석 시작...")
        
        # 기술적 분석과 기본적 분석을 병렬로 실행
        analysis_tasks = []
        
        # 기술적 분석 작업
        if "technical_analyst" in workflow["discovered_agents"]:
            tech_task_id = f"technical_analysis_{workflow['workflow_id']}"
            tech_task_data = {
                "task_id": tech_task_id,
                "task_type": "bulk_technical_analysis",
                "input_data": {
                    "stocks": workflow["stocks"],
                    "price_data": workflow["results"]["data_collection"]["price_data"]
                }
            }
            
            tech_endpoint = f"http://localhost:{self.default_agent_ports[AgentRole.TECHNICAL_ANALYST]}"
            analysis_tasks.append(("technical", tech_endpoint, tech_task_data, tech_task_id))
        
        # 기본적 분석 작업
        if "fundamental_analyst" in workflow["discovered_agents"]:
            fund_task_id = f"fundamental_analysis_{workflow['workflow_id']}"
            fund_task_data = {
                "task_id": fund_task_id,
                "task_type": "bulk_fundamental_analysis",
                "input_data": {
                    "stocks": workflow["stocks"],
                    "financial_data": workflow["results"]["data_collection"]["financial_data"]
                }
            }
            
            fund_endpoint = f"http://localhost:{self.default_agent_ports[AgentRole.FUNDAMENTAL_ANALYST]}"
            analysis_tasks.append(("fundamental", fund_endpoint, fund_task_data, fund_task_id))
        
        # 병렬 작업 실행
        workflow["tasks"]["analysis"] = {}
        
        for analysis_type, endpoint, task_data, task_id in analysis_tasks:
            result = await self.send_task_to_agent(endpoint, task_data)
            if result["accepted"]:
                workflow["tasks"]["analysis"][analysis_type] = task_id
                logger.info(f"✅ {analysis_type} 분석 작업 시작: {task_id}")
        
        # 모든 분석 작업 완료 대기
        workflow["results"]["analysis"] = {}
        
        for analysis_type, endpoint, task_data, task_id in analysis_tasks:
            if analysis_type in workflow["tasks"]["analysis"]:
                await self.wait_for_task_completion(endpoint, task_id, timeout=180)
                task_result = await self.get_task_result(endpoint, task_id)
                workflow["results"]["analysis"][analysis_type] = task_result["output_data"]
                logger.info(f"✅ {analysis_type} 분석 완료")
        
        workflow["timeline"][-1]["completed_at"] = datetime.now().isoformat()
        workflow["timeline"][-1]["status"] = "completed"
        
        logger.info("✅ 병렬 분석 완료")
    
    async def coordinate_portfolio_construction(self, workflow: Dict[str, Any]):
        """포트폴리오 구성 조정"""
        workflow["status"] = "constructing_portfolio"
        workflow["timeline"].append({"step": "portfolio_construction", "started_at": datetime.now().isoformat()})
        
        logger.info("💼 포트폴리오 구성 시작...")
        
        if "portfolio_manager" not in workflow["discovered_agents"]:
            raise Exception("포트폴리오 매니저 에이전트가 없습니다")
        
        portfolio_endpoint = f"http://localhost:{self.default_agent_ports[AgentRole.PORTFOLIO_MANAGER]}"
        
        # 포트폴리오 구성 작업
        portfolio_task_id = f"portfolio_construction_{workflow['workflow_id']}"
        portfolio_task_data = {
            "task_id": portfolio_task_id,
            "task_type": "portfolio_optimization",
            "input_data": {
                "stocks": workflow["stocks"],
                "analysis_results": workflow["results"]["analysis"],
                "constraints": {
                    "max_position_size": 0.3,  # 최대 30% 비중
                    "min_position_size": 0.05,  # 최소 5% 비중
                    "max_stocks": 8,  # 최대 8개 종목
                    "target_return": 0.15,  # 목표 수익률 15%
                    "risk_tolerance": "moderate"
                }
            }
        }
        
        # 작업 전송
        result = await self.send_task_to_agent(portfolio_endpoint, portfolio_task_data)
        
        if result["accepted"]:
            workflow["tasks"]["portfolio_construction"] = portfolio_task_id
            
            # 작업 완료 대기
            await self.wait_for_task_completion(portfolio_endpoint, portfolio_task_id, timeout=120)
            
            # 결과 수집
            task_result = await self.get_task_result(portfolio_endpoint, portfolio_task_id)
            workflow["results"]["portfolio"] = task_result["output_data"]
            
            workflow["timeline"][-1]["completed_at"] = datetime.now().isoformat()
            workflow["timeline"][-1]["status"] = "completed"
            
            logger.info("✅ 포트폴리오 구성 완료")
        else:
            raise Exception(f"포트폴리오 구성 작업 수락 실패: {result}")
    
    async def finalize_workflow(self, workflow: Dict[str, Any]):
        """워크플로우 최종화"""
        workflow["status"] = "completed"
        workflow["completed_at"] = datetime.now().isoformat()
        
        # 총 소요 시간 계산
        start_time = datetime.fromisoformat(workflow["started_at"])
        end_time = datetime.fromisoformat(workflow["completed_at"])
        duration = (end_time - start_time).total_seconds()
        
        workflow["duration_seconds"] = duration
        workflow["summary"] = self.generate_workflow_summary(workflow)
        
        logger.info(f"🏁 워크플로우 완료: {workflow['workflow_id']} ({duration:.1f}초)")
    
    def generate_workflow_summary(self, workflow: Dict[str, Any]) -> Dict[str, Any]:
        """워크플로우 요약 생성"""
        portfolio = workflow["results"]["portfolio"]
        
        return {
            "workflow_id": workflow["workflow_id"],
            "total_duration": workflow["duration_seconds"],
            "analyzed_stocks": len(workflow["stocks"]),
            "selected_stocks": len(portfolio["selected_stocks"]),
            "expected_return": portfolio.get("expected_return", "N/A"),
            "risk_level": portfolio.get("risk_level", "N/A"),
            "total_investment": sum(stock["weight"] for stock in portfolio["selected_stocks"]),
            "top_recommendation": portfolio["selected_stocks"][0] if portfolio["selected_stocks"] else None
        }
    
    async def send_task_to_agent(self, endpoint: str, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """에이전트에게 작업 전송"""
        try:
            timeout = ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(f"{endpoint}/tasks", json=task_data) as response:
                    return await response.json()
        except Exception as e:
            logger.error(f"❌ 작업 전송 실패: {str(e)}")
            return {"accepted": False, "error": str(e)}
    
    async def wait_for_task_completion(self, endpoint: str, task_id: str, timeout: int = 60):
        """작업 완료 대기"""
        start_time = asyncio.get_event_loop().time()
        
        while True:
            try:
                client_timeout = ClientTimeout(total=5)
                async with aiohttp.ClientSession(timeout=client_timeout) as session:
                    async with session.get(f"{endpoint}/tasks/{task_id}") as response:
                        if response.status == 200:
                            task_status = await response.json()
                            if task_status["status"] in ["completed", "failed"]:
                                return task_status
                
                # 타임아웃 체크
                if asyncio.get_event_loop().time() - start_time > timeout:
                    raise asyncio.TimeoutError(f"작업 대기 시간 초과: {task_id}")
                
                await asyncio.sleep(2)  # 2초마다 확인
                
            except asyncio.TimeoutError:
                raise
            except Exception as e:
                logger.warning(f"⚠️ 작업 상태 확인 실패: {str(e)}")
                await asyncio.sleep(2)
    
    async def get_task_result(self, endpoint: str, task_id: str) -> Dict[str, Any]:
        """작업 결과 조회"""
        try:
            timeout = ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(f"{endpoint}/tasks/{task_id}") as response:
                    return await response.json()
        except Exception as e:
            logger.error(f"❌ 작업 결과 조회 실패: {str(e)}")
            return {"output_data": None, "error": str(e)}


class DataCollectorAgent(BaseAgent):
    """데이터 수집 에이전트"""
    
    def __init__(self, port: int):
        super().__init__("data_collector_001", AgentRole.DATA_COLLECTOR, port)
    
    def get_capabilities(self) -> List[str]:
        return ["bulk_data_collection", "price_data", "volume_data", "financial_data", "news_data"]
    
    def estimate_task_duration(self, task: Task) -> int:
        return 60  # 60초
    
    async def execute_task(self, task: Task):
        """데이터 수집 실행"""
        try:
            task.status = TaskStatus.IN_PROGRESS
            task.started_at = datetime.now().isoformat()
            
            logger.info(f"📊 대량 데이터 수집 시작: {len(task.input_data['stocks'])}개 종목")
            
            # 데이터 수집 시뮬레이션
            await asyncio.sleep(3)  # 수집 시간 시뮬레이션
            
            collected_data = {
                "price_data": {},
                "volume_data": {},
                "financial_data": {},
                "news_data": {},
                "collection_timestamp": datetime.now().isoformat(),
                "collector_id": self.agent_id
            }
            
            # 각 종목별 데이터 생성
            for stock in task.input_data["stocks"]:
                symbol = stock["symbol"]
                name = stock["name"]
                
                # 주가 데이터
                base_price = random.randint(50000, 500000)
                collected_data["price_data"][symbol] = {
                    "symbol": symbol,
                    "name": name,
                    "current_price": base_price,
                    "day_change": random.randint(-10000, 10000),
                    "day_change_percent": random.uniform(-5.0, 5.0),
                    "volume": random.randint(100000, 10000000),
                    "market_cap": base_price * random.randint(100000000, 1000000000)
                }
                
                # 재무 데이터
                collected_data["financial_data"][symbol] = {
                    "symbol": symbol,
                    "name": name,
                    "per": random.uniform(5.0, 30.0),
                    "pbr": random.uniform(0.5, 5.0),
                    "roe": random.uniform(3.0, 25.0),
                    "debt_ratio": random.uniform(10.0, 80.0),
                    "revenue_growth": random.uniform(-10.0, 30.0),
                    "profit_margin": random.uniform(2.0, 20.0)
                }
                
                # 뉴스 데이터
                collected_data["news_data"][symbol] = {
                    "symbol": symbol,
                    "name": name,
                    "news_count": random.randint(5, 50),
                    "sentiment_score": random.uniform(0.3, 0.8),
                    "positive_ratio": random.uniform(0.4, 0.8),
                    "key_topics": [f"{name} 관련 뉴스", "업계 동향", "실적 전망"]
                }
            
            task.output_data = collected_data
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now().isoformat()
            
            logger.info(f"✅ 데이터 수집 완료: {len(task.input_data['stocks'])}개 종목")
            
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error_message = str(e)
            task.completed_at = datetime.now().isoformat()
            logger.error(f"❌ 데이터 수집 실패: {str(e)}")
        finally:
            self.current_load -= 1


class TechnicalAnalysisAgent(BaseAgent):
    """기술적 분석 에이전트"""
    
    def __init__(self, port: int):
        super().__init__("technical_analyst_001", AgentRole.TECHNICAL_ANALYST, port)
    
    def get_capabilities(self) -> List[str]:
        return ["technical_analysis", "chart_analysis", "indicator_calculation", "trend_analysis"]
    
    def estimate_task_duration(self, task: Task) -> int:
        return 90  # 90초
    
    async def execute_task(self, task: Task):
        """기술적 분석 실행"""
        try:
            task.status = TaskStatus.IN_PROGRESS
            task.started_at = datetime.now().isoformat()
            
            logger.info(f"📈 기술적 분석 시작: {len(task.input_data['stocks'])}개 종목")
            
            # 기술적 분석 시뮬레이션
            await asyncio.sleep(4)
            
            analysis_results = {
                "analysis_type": "technical",
                "analyzed_stocks": {},
                "summary": {
                    "buy_signals": 0,
                    "hold_signals": 0,
                    "sell_signals": 0
                },
                "analysis_timestamp": datetime.now().isoformat(),
                "analyst_id": self.agent_id
            }
            
            price_data = task.input_data["price_data"]
            
            # 각 종목별 기술적 분석
            for stock in task.input_data["stocks"]:
                symbol = stock["symbol"]
                name = stock["name"]
                
                if symbol in price_data:
                    # 기술적 지표 계산 (모의)
                    rsi = random.uniform(20.0, 80.0)
                    macd = random.uniform(-2.0, 2.0)
                    bb_position = random.uniform(0.2, 0.8)
                    
                    # 매매 신호 결정
                    signal_score = 0
                    if rsi < 30:
                        signal_score += 1
                    elif rsi > 70:
                        signal_score -= 1
                    
                    if macd > 0:
                        signal_score += 0.5
                    else:
                        signal_score -= 0.5
                    
                    if bb_position < 0.3:
                        signal_score += 0.5
                    elif bb_position > 0.7:
                        signal_score -= 0.5
                    
                    # 신호 결정
                    if signal_score > 1:
                        signal = "BUY"
                        analysis_results["summary"]["buy_signals"] += 1
                    elif signal_score < -1:
                        signal = "SELL"
                        analysis_results["summary"]["sell_signals"] += 1
                    else:
                        signal = "HOLD"
                        analysis_results["summary"]["hold_signals"] += 1
                    
                    analysis_results["analyzed_stocks"][symbol] = {
                        "symbol": symbol,
                        "name": name,
                        "technical_indicators": {
                            "rsi": round(rsi, 2),
                            "macd": round(macd, 2),
                            "bollinger_position": round(bb_position, 2)
                        },
                        "signal": signal,
                        "signal_strength": abs(signal_score),
                        "technical_score": max(0, min(100, 50 + signal_score * 20))
                    }
            
            task.output_data = analysis_results
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now().isoformat()
            
            logger.info(f"✅ 기술적 분석 완료: 매수 {analysis_results['summary']['buy_signals']}개")
            
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error_message = str(e)
            task.completed_at = datetime.now().isoformat()
            logger.error(f"❌ 기술적 분석 실패: {str(e)}")
        finally:
            self.current_load -= 1


class FundamentalAnalysisAgent(BaseAgent):
    """기본적 분석 에이전트"""
    
    def __init__(self, port: int):
        super().__init__("fundamental_analyst_001", AgentRole.FUNDAMENTAL_ANALYST, port)
    
    def get_capabilities(self) -> List[str]:
        return ["fundamental_analysis", "financial_analysis", "valuation", "industry_analysis"]
    
    def estimate_task_duration(self, task: Task) -> int:
        return 100  # 100초
    
    async def execute_task(self, task: Task):
        """기본적 분석 실행"""
        try:
            task.status = TaskStatus.IN_PROGRESS
            task.started_at = datetime.now().isoformat()
            
            logger.info(f"💰 기본적 분석 시작: {len(task.input_data['stocks'])}개 종목")
            
            # 기본적 분석 시뮬레이션
            await asyncio.sleep(4.5)
            
            analysis_results = {
                "analysis_type": "fundamental",
                "analyzed_stocks": {},
                "summary": {
                    "undervalued": 0,
                    "fairly_valued": 0,
                    "overvalued": 0
                },
                "analysis_timestamp": datetime.now().isoformat(),
                "analyst_id": self.agent_id
            }
            
            financial_data = task.input_data["financial_data"]
            
            # 각 종목별 기본적 분석
            for stock in task.input_data["stocks"]:
                symbol = stock["symbol"]
                name = stock["name"]
                sector = stock["sector"]
                
                if symbol in financial_data:
                    fin_data = financial_data[symbol]
                    
                    # 밸류에이션 점수 계산
                    valuation_score = 0
                    
                    # PER 평가
                    per = fin_data["per"]
                    if per < 10:
                        valuation_score += 2
                    elif per < 20:
                        valuation_score += 1
                    elif per > 30:
                        valuation_score -= 1
                    
                    # PBR 평가
                    pbr = fin_data["pbr"]
                    if pbr < 1:
                        valuation_score += 2
                    elif pbr < 2:
                        valuation_score += 1
                    elif pbr > 3:
                        valuation_score -= 1
                    
                    # ROE 평가
                    roe = fin_data["roe"]
                    if roe > 15:
                        valuation_score += 2
                    elif roe > 10:
                        valuation_score += 1
                    elif roe < 5:
                        valuation_score -= 1
                    
                    # 성장성 평가
                    revenue_growth = fin_data["revenue_growth"]
                    if revenue_growth > 20:
                        valuation_score += 2
                    elif revenue_growth > 10:
                        valuation_score += 1
                    elif revenue_growth < 0:
                        valuation_score -= 2
                    
                    # 평가 결정
                    if valuation_score >= 4:
                        valuation = "UNDERVALUED"
                        analysis_results["summary"]["undervalued"] += 1
                    elif valuation_score <= 0:
                        valuation = "OVERVALUED"
                        analysis_results["summary"]["overvalued"] += 1
                    else:
                        valuation = "FAIRLY_VALUED"
                        analysis_results["summary"]["fairly_valued"] += 1
                    
                    # 목표가 계산 (단순화)
                    current_per = fin_data["per"]
                    target_per = random.uniform(12, 18)  # 적정 PER
                    eps = random.uniform(5000, 50000)  # 예상 EPS
                    target_price = eps * target_per
                    
                    analysis_results["analyzed_stocks"][symbol] = {
                        "symbol": symbol,
                        "name": name,
                        "sector": sector,
                        "financial_metrics": {
                            "per": fin_data["per"],
                            "pbr": fin_data["pbr"],
                            "roe": fin_data["roe"],
                            "revenue_growth": fin_data["revenue_growth"],
                            "profit_margin": fin_data["profit_margin"]
                        },
                        "valuation": valuation,
                        "valuation_score": valuation_score,
                        "target_price": round(target_price),
                        "fundamental_score": max(0, min(100, 50 + valuation_score * 10)),
                        "investment_thesis": f"{sector} 섹터의 {"저평가" if valuation == "UNDERVALUED" else "적정평가" if valuation == "FAIRLY_VALUED" else "고평가"} 종목"
                    }
            
            task.output_data = analysis_results
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now().isoformat()
            
            logger.info(f"✅ 기본적 분석 완료: 저평가 {analysis_results['summary']['undervalued']}개")
            
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error_message = str(e)
            task.completed_at = datetime.now().isoformat()
            logger.error(f"❌ 기본적 분석 실패: {str(e)}")
        finally:
            self.current_load -= 1


class PortfolioManagerAgent(BaseAgent):
    """포트폴리오 관리 에이전트"""
    
    def __init__(self, port: int):
        super().__init__("portfolio_manager_001", AgentRole.PORTFOLIO_MANAGER, port)
    
    def get_capabilities(self) -> List[str]:
        return ["portfolio_optimization", "risk_management", "asset_allocation", "performance_analysis"]
    
    def estimate_task_duration(self, task: Task) -> int:
        return 80  # 80초
    
    async def execute_task(self, task: Task):
        """포트폴리오 최적화 실행"""
        try:
            task.status = TaskStatus.IN_PROGRESS
            task.started_at = datetime.now().isoformat()
            
            logger.info("💼 포트폴리오 최적화 시작")
            
            # 포트폴리오 최적화 시뮬레이션
            await asyncio.sleep(3.5)
            
            analysis_results = task.input_data["analysis_results"]
            constraints = task.input_data["constraints"]
            
            # 종목별 종합 점수 계산
            stock_scores = []
            
            for stock in task.input_data["stocks"]:
                symbol = stock["symbol"]
                name = stock["name"]
                sector = stock["sector"]
                
                # 기술적 분석 점수
                tech_score = 0
                if "technical" in analysis_results and symbol in analysis_results["technical"]["analyzed_stocks"]:
                    tech_score = analysis_results["technical"]["analyzed_stocks"][symbol]["technical_score"]
                
                # 기본적 분석 점수
                fund_score = 0
                if "fundamental" in analysis_results and symbol in analysis_results["fundamental"]["analyzed_stocks"]:
                    fund_score = analysis_results["fundamental"]["analyzed_stocks"][symbol]["fundamental_score"]
                
                # 종합 점수 계산 (기술적 40%, 기본적 60%)
                if tech_score > 0 and fund_score > 0:
                    composite_score = tech_score * 0.4 + fund_score * 0.6
                elif tech_score > 0:
                    composite_score = tech_score * 0.7  # 기술적 분석만 있을 경우
                elif fund_score > 0:
                    composite_score = fund_score * 0.8  # 기본적 분석만 있을 경우
                else:
                    composite_score = 50  # 기본 점수
                
                stock_scores.append({
                    "symbol": symbol,
                    "name": name,
                    "sector": sector,
                    "composite_score": composite_score,
                    "technical_score": tech_score,
                    "fundamental_score": fund_score
                })
            
            # 점수 기준으로 정렬
            stock_scores.sort(key=lambda x: x["composite_score"], reverse=True)
            
            # 포트폴리오 구성
            selected_stocks = []
            total_weight = 0
            max_stocks = min(constraints["max_stocks"], len(stock_scores))
            
            # 상위 종목들 선택 및 가중치 배분
            for i, stock in enumerate(stock_scores[:max_stocks]):
                if stock["composite_score"] >= 60:  # 60점 이상만 선택
                    # 점수에 비례한 가중치 계산
                    base_weight = stock["composite_score"] / 100 * 0.2  # 기본 20% 스케일
                    
                    # 제약조건 적용
                    weight = max(constraints["min_position_size"], 
                               min(constraints["max_position_size"], base_weight))
                    
                    if total_weight + weight <= 1.0:  # 100% 이하 유지
                        selected_stocks.append({
                            "symbol": stock["symbol"],
                            "name": stock["name"],
                            "sector": stock["sector"],
                            "weight": round(weight, 3),
                            "composite_score": round(stock["composite_score"], 1),
                            "rank": i + 1,
                            "rationale": f"종합점수 {stock['composite_score']:.1f}점의 우수 종목"
                        })
                        total_weight += weight
            
            # 가중치 정규화
            if total_weight > 0:
                for stock in selected_stocks:
                    stock["weight"] = round(stock["weight"] / total_weight, 3)
            
            # 포트폴리오 특성 계산
            avg_score = sum(stock["composite_score"] for stock in selected_stocks) / len(selected_stocks) if selected_stocks else 0
            
            # 섹터 다양성 계산
            sectors = set(stock["sector"] for stock in selected_stocks)
            sector_diversity = len(sectors) / len(selected_stocks) if selected_stocks else 0
            
            # 리스크 레벨 결정
            if avg_score > 80:
                risk_level = "Low"
            elif avg_score > 70:
                risk_level = "Moderate"
            else:
                risk_level = "High"
            
            portfolio_result = {
                "optimization_type": "score_based_allocation",
                "selected_stocks": selected_stocks,
                "portfolio_metrics": {
                    "total_stocks": len(selected_stocks),
                    "average_score": round(avg_score, 1),
                    "total_allocation": round(sum(stock["weight"] for stock in selected_stocks), 3),
                    "sector_count": len(sectors),
                    "sector_diversity": round(sector_diversity, 2)
                },
                "expected_return": round(0.08 + (avg_score - 50) / 100 * 0.15, 3),  # 8% + 점수 기반 추가 수익률
                "risk_level": risk_level,
                "recommendation": "매수 추천" if avg_score > 70 else "신중한 접근",
                "rebalancing_frequency": "월 1회",
                "optimization_timestamp": datetime.now().isoformat(),
                "manager_id": self.agent_id
            }
            
            task.output_data = portfolio_result
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now().isoformat()
            
            logger.info(f"✅ 포트폴리오 최적화 완료: {len(selected_stocks)}개 종목 선택")
            
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error_message = str(e)
            task.completed_at = datetime.now().isoformat()
            logger.error(f"❌ 포트폴리오 최적화 실패: {str(e)}")
        finally:
            self.current_load -= 1


async def run_agent(role: str, port: int):
    """에이전트 실행"""
    if role == "coordinator":
        agent = CoordinatorAgent(port)
    elif role == "collector":
        agent = DataCollectorAgent(port)
    elif role == "technical":
        agent = TechnicalAnalysisAgent(port)
    elif role == "fundamental":
        agent = FundamentalAnalysisAgent(port)
    elif role == "portfolio":
        agent = PortfolioManagerAgent(port)
    else:
        raise ValueError(f"알 수 없는 역할: {role}")
    
    runner = await agent.start_server()
    
    try:
        print(f"\n{'='*60}")
        print(f"  🤖 {agent.role.value.replace('_', ' ').title()} 실행 중 (포트 {port})")
        print(f"{'='*60}")
        print(f"에이전트 ID: {agent.agent_id}")
        print(f"능력: {', '.join(agent.get_capabilities())}")
        print(f"최대 동시 작업: {agent.max_capacity}개")
        print(f"\n💡 API 엔드포인트:")
        print(f"  GET  /health - 헬스 체크")
        print(f"  GET  /info - 에이전트 정보")
        print(f"  POST /tasks - 작업 수락")
        print(f"  GET  /tasks/{{task_id}} - 작업 상태 조회")
        
        if role == "coordinator":
            print(f"  POST /start_analysis - 포트폴리오 분석 시작")
            print(f"  GET  /workflow/{{workflow_id}} - 워크플로우 상태 조회")
        
        print(f"\n⏹️ 종료: Ctrl+C")
        
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info(f"{agent.role.value} 종료 중...")
    finally:
        await runner.cleanup()


async def demonstrate_multi_agent_collaboration():
    """멀티 에이전트 협업 데모"""
    print(f"\n{'='*60}")
    print(f"  🤖 멀티 에이전트 협업 데모")
    print(f"{'='*60}")
    
    # 에이전트 포트 설정
    agent_configs = [
        ("coordinator", 7000),
        ("collector", 7001),
        ("technical", 7002),
        ("fundamental", 7003),
        ("portfolio", 7004)
    ]
    
    print("🚀 5개 에이전트를 순차적으로 시작합니다...")
    
    # 에이전트들 생성 및 실행
    agents = []
    runners = []
    
    for role, port in agent_configs:
        if role == "coordinator":
            agent = CoordinatorAgent(port)
        elif role == "collector":
            agent = DataCollectorAgent(port)
        elif role == "technical":
            agent = TechnicalAnalysisAgent(port)
        elif role == "fundamental":
            agent = FundamentalAnalysisAgent(port)
        elif role == "portfolio":
            agent = PortfolioManagerAgent(port)
        
        agents.append(agent)
        runner = await agent.start_server()
        runners.append(runner)
        
        await asyncio.sleep(1)  # 각 에이전트 시작 간격
    
    try:
        # 모든 에이전트 준비 대기
        await asyncio.sleep(3)
        
        print("✅ 모든 에이전트 시작 완료")
        print(f"\n📊 KOSPI 상위 10개 종목 포트폴리오 분석 시작...")
        
        # 워크플로우 시작 (Coordinator에게 요청)
        timeout = ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post("http://localhost:7000/start_analysis") as response:
                if response.status == 200:
                    result = await response.json()
                    workflow_id = result["workflow_id"]
                    
                    print(f"🎯 워크플로우 시작: {workflow_id}")
                    print(f"   분석 종목: {result['stocks_count']}개")
                    print(f"   예상 소요 시간: {result['estimated_duration']}")
                    
                    # 워크플로우 진행 상황 모니터링
                    print(f"\n📈 진행 상황 모니터링...")
                    
                    completed = False
                    last_status = ""
                    
                    while not completed:
                        await asyncio.sleep(5)  # 5초마다 확인
                        
                        try:
                            async with session.get(f"http://localhost:7000/workflow/{workflow_id}") as status_response:
                                if status_response.status == 200:
                                    workflow_status = await status_response.json()
                                    current_status = workflow_status["status"]
                                    
                                    if current_status != last_status:
                                        status_messages = {
                                            "initializing": "🔧 초기화 중...",
                                            "discovering_agents": "🔍 에이전트 발견 중...",
                                            "collecting_data": "📊 데이터 수집 중...",
                                            "analyzing": "🔍 병렬 분석 중...",
                                            "constructing_portfolio": "💼 포트폴리오 구성 중...",
                                            "completed": "✅ 분석 완료!",
                                            "failed": "❌ 분석 실패"
                                        }
                                        
                                        print(f"   {status_messages.get(current_status, current_status)}")
                                        last_status = current_status
                                    
                                    if current_status in ["completed", "failed"]:
                                        completed = True
                                        
                                        if current_status == "completed":
                                            # 최종 결과 출력
                                            summary = workflow_status["summary"]
                                            portfolio = workflow_status["results"]["portfolio"]
                                            
                                            print(f"\n🎯 포트폴리오 분석 완료!")
                                            print(f"   소요 시간: {summary['total_duration']:.1f}초")
                                            print(f"   분석 종목: {summary['analyzed_stocks']}개")
                                            print(f"   선택 종목: {summary['selected_stocks']}개")
                                            print(f"   예상 수익률: {summary['expected_return']:.1%}")
                                            print(f"   리스크 수준: {summary['risk_level']}")
                                            
                                            print(f"\n💼 포트폴리오 구성:")
                                            for stock in portfolio["selected_stocks"][:5]:  # 상위 5개만 표시
                                                print(f"   {stock['rank']}. {stock['name']} ({stock['symbol']}) - {stock['weight']:.1%}")
                                            
                                            print(f"\n✅ 멀티 에이전트 협업 성공!")
                        
                        except Exception as e:
                            logger.warning(f"⚠️ 상태 확인 실패: {str(e)}")
                else:
                    print(f"❌ 워크플로우 시작 실패: {response.status}")
        
        print(f"\n⏹️ 데모 종료를 위해 Ctrl+C를 누르세요...")
        
        while True:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        print("\n🔚 데모 종료 중...")
    finally:
        for runner in runners:
            await runner.cleanup()


def main():
    parser = argparse.ArgumentParser(description="멀티 에이전트 협업 데모")
    parser.add_argument("--role", choices=["coordinator", "collector", "technical", "fundamental", "portfolio", "demo"],
                       help="실행할 에이전트 역할")
    parser.add_argument("--port", type=int, default=7000,
                       help="에이전트 포트 번호")
    
    args = parser.parse_args()
    
    if args.role in ["coordinator", "collector", "technical", "fundamental", "portfolio"]:
        print("🤖 멀티 에이전트 협업 학습을 시작합니다!")
        print("이 예제는 5개의 전문 에이전트가 협업하는 과정을 보여줍니다.")
        asyncio.run(run_agent(args.role, args.port))
    elif args.role == "demo":
        print("🤖 멀티 에이전트 협업 학습을 시작합니다!")
        print("이 예제는 5개의 전문 에이전트가 협업하는 과정을 보여줍니다.")
        asyncio.run(demonstrate_multi_agent_collaboration())
    else:
        print("사용법:")
        print("  Coordinator:     python 3_4_multi_agent_collaboration.py --role coordinator --port 7000")
        print("  Data Collector:  python 3_4_multi_agent_collaboration.py --role collector --port 7001")
        print("  Technical:       python 3_4_multi_agent_collaboration.py --role technical --port 7002")
        print("  Fundamental:     python 3_4_multi_agent_collaboration.py --role fundamental --port 7003")
        print("  Portfolio:       python 3_4_multi_agent_collaboration.py --role portfolio --port 7004")
        print("  협업 데모:        python 3_4_multi_agent_collaboration.py --role demo")


if __name__ == "__main__":
    main()