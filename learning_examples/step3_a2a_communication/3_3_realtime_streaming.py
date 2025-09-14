#!/usr/bin/env python3
"""
3.3 실시간 스트리밍 - 삼성SDI 라이브 데이터

Agent 간 실시간 데이터 스트리밍을 학습하는 예제입니다.
삼성SDI(006400) 주식의 실시간 데이터를 WebSocket으로 스트리밍하고,
실시간 분석 결과를 클라이언트에게 전송하는 시나리오를 구현합니다.

학습 목표:
- WebSocket 기반 실시간 통신 이해
- 실시간 데이터 스트리밍 구현
- 양방향 통신과 이벤트 처리
- 다중 클라이언트 관리
- 실시간 분석 및 알림 시스템

구성 요소:
- Streaming Server: 실시간 데이터 스트리밍 서버 (WebSocket)
- Analysis Client: 실시간 분석 클라이언트
- Real-time Data Simulator: 실시간 데이터 시뮬레이터

실행 방법:
python 3_3_realtime_streaming.py --role [server|client|demo] --port [포트번호]
"""

import asyncio
import json
import argparse
import random
import math
from typing import Dict, Any, Optional, List, Set
from pathlib import Path
import sys
from datetime import datetime, timedelta
import aiohttp
from aiohttp import web, WSMsgType, ClientTimeout
import websockets
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


class MessageType(Enum):
    """메시지 타입"""
    PRICE_UPDATE = "price_update"
    ANALYSIS_RESULT = "analysis_result"
    MARKET_ALERT = "market_alert"
    CLIENT_COMMAND = "client_command"
    SYSTEM_STATUS = "system_status"
    SUBSCRIPTION = "subscription"
    ERROR = "error"


class AlertLevel(Enum):
    """알림 레벨"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class PriceData:
    """주가 데이터"""
    symbol: str
    company_name: str
    current_price: float
    price_change: float
    price_change_percent: float
    volume: int
    trading_value: float
    high: float
    low: float
    timestamp: str


@dataclass
class StreamMessage:
    """스트리밍 메시지"""
    message_type: MessageType
    timestamp: str
    data: Dict[str, Any]
    source: str = "StreamingServer"


class RealTimeDataSimulator:
    """
    실시간 데이터 시뮬레이터
    
    삼성SDI의 실시간 주가 데이터를 시뮬레이션합니다.
    """
    
    def __init__(self, symbol: str = "006400", company_name: str = "삼성SDI"):
        self.symbol = symbol
        self.company_name = company_name
        
        # 초기 주가 설정
        self.base_price = 420000  # 삼성SDI 기준가
        self.current_price = self.base_price
        self.daily_high = self.current_price
        self.daily_low = self.current_price
        self.total_volume = 0
        self.total_trading_value = 0.0
        
        # 시뮬레이션 파라미터
        self.volatility = 0.02  # 2% 변동성
        self.trend_factor = 0.001  # 트렌드 요소
        self.volume_base = 50000  # 기본 거래량
        
        # 시장 시간 (9시-15시30분)
        self.market_open = 9
        self.market_close = 15.5
        
        # 이벤트 생성 확률
        self.event_probability = 0.02  # 2% 확률로 특별 이벤트
    
    def is_market_hours(self) -> bool:
        """시장 시간 확인"""
        current_time = datetime.now()
        current_hour = current_time.hour + current_time.minute / 60.0
        return self.market_open <= current_hour <= self.market_close
    
    def generate_price_movement(self) -> float:
        """주가 움직임 생성"""
        # 기본 랜덤 워크
        random_change = random.gauss(0, self.volatility)
        
        # 시장 시간에 따른 활동성 조정
        if self.is_market_hours():
            activity_multiplier = 1.0
            
            # 장 시작/종료 시간에는 변동성 증가
            current_time = datetime.now()
            current_hour = current_time.hour + current_time.minute / 60.0
            
            if 9.0 <= current_hour <= 9.5 or 15.0 <= current_hour <= 15.5:
                activity_multiplier = 1.5  # 50% 더 활발
        else:
            activity_multiplier = 0.1  # 장외시간 저활동성
        
        # 트렌드 추가 (약간의 상승 편향)
        trend_change = self.trend_factor * random.uniform(-1, 1.2)
        
        total_change = (random_change + trend_change) * activity_multiplier
        
        # 급격한 변동 제한 (±5%)
        total_change = max(-0.05, min(0.05, total_change))
        
        return total_change
    
    def generate_special_event(self) -> Optional[Dict[str, Any]]:
        """특별 이벤트 생성"""
        if random.random() > self.event_probability:
            return None
        
        events = [
            {
                "type": "news_impact",
                "title": "삼성SDI, 차세대 배터리 기술 개발 성공",
                "impact": 0.03,  # 3% 상승
                "duration": 5  # 5틱 동안 지속
            },
            {
                "type": "market_rumor",
                "title": "주요 자동차 업체와 대규모 공급계약 체결 임박",
                "impact": 0.025,  # 2.5% 상승
                "duration": 3
            },
            {
                "type": "sector_rotation",
                "title": "2차전지 섹터 로테이션 발생",
                "impact": -0.015,  # -1.5% 하락
                "duration": 4
            },
            {
                "type": "analyst_upgrade",
                "title": "증권사 목표가 상향 조정",
                "impact": 0.02,  # 2% 상승
                "duration": 3
            }
        ]
        
        return random.choice(events)
    
    def update_price(self) -> PriceData:
        """주가 업데이트"""
        # 특별 이벤트 확인
        event = self.generate_special_event()
        
        # 가격 변동 계산
        price_change = self.generate_price_movement()
        
        # 이벤트 영향 추가
        if event:
            price_change += event["impact"]
            logger.info(f"📰 특별 이벤트: {event['title']} (영향: {event['impact']:+.2%})")
        
        # 새 가격 계산
        new_price = self.current_price * (1 + price_change)
        
        # 가격 제한 (기준가 대비 ±30%)
        min_price = self.base_price * 0.7
        max_price = self.base_price * 1.3
        new_price = max(min_price, min(max_price, new_price))
        
        # 가격 변동량 계산
        absolute_change = new_price - self.current_price
        percent_change = (absolute_change / self.current_price) * 100
        
        # 일 최고/최저가 업데이트
        self.daily_high = max(self.daily_high, new_price)
        self.daily_low = min(self.daily_low, new_price)
        
        # 거래량 생성 (변동성에 비례)
        volume_multiplier = 1 + abs(price_change) * 10
        tick_volume = int(self.volume_base * volume_multiplier * random.uniform(0.5, 2.0))
        
        self.total_volume += tick_volume
        tick_trading_value = new_price * tick_volume
        self.total_trading_value += tick_trading_value
        
        # 현재 가격 업데이트
        self.current_price = new_price
        
        # PriceData 객체 생성
        price_data = PriceData(
            symbol=self.symbol,
            company_name=self.company_name,
            current_price=round(new_price),
            price_change=round(absolute_change),
            price_change_percent=round(percent_change, 2),
            volume=self.total_volume,
            trading_value=round(self.total_trading_value),
            high=round(self.daily_high),
            low=round(self.daily_low),
            timestamp=datetime.now().isoformat()
        )
        
        return price_data


class TechnicalAnalyzer:
    """
    실시간 기술적 분석기
    
    실시간 주가 데이터를 받아 기술적 분석을 수행합니다.
    """
    
    def __init__(self, window_size: int = 20):
        self.window_size = window_size
        self.price_history: List[float] = []
        self.volume_history: List[int] = []
        
        # 분석 결과 캐시
        self.last_analysis = None
        self.analysis_cache_time = None
    
    def add_price_data(self, price_data: PriceData):
        """새로운 주가 데이터 추가"""
        self.price_history.append(price_data.current_price)
        self.volume_history.append(price_data.volume)
        
        # 윈도우 크기 유지
        if len(self.price_history) > self.window_size * 2:
            self.price_history = self.price_history[-self.window_size:]
            self.volume_history = self.volume_history[-self.window_size:]
    
    def calculate_moving_average(self, period: int = 5) -> Optional[float]:
        """이동평균 계산"""
        if len(self.price_history) < period:
            return None
        
        return sum(self.price_history[-period:]) / period
    
    def calculate_rsi(self, period: int = 14) -> Optional[float]:
        """RSI 계산"""
        if len(self.price_history) < period + 1:
            return None
        
        gains = []
        losses = []
        
        for i in range(-period, 0):
            change = self.price_history[i] - self.price_history[i-1]
            if change > 0:
                gains.append(change)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(change))
        
        avg_gain = sum(gains) / period
        avg_loss = sum(losses) / period
        
        if avg_loss == 0:
            return 100
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return round(rsi, 2)
    
    def detect_pattern(self) -> Dict[str, Any]:
        """패턴 감지"""
        if len(self.price_history) < 10:
            return {"pattern": "insufficient_data", "confidence": 0}
        
        recent_prices = self.price_history[-10:]
        
        # 상승/하락 추세 감지
        trend_changes = []
        for i in range(1, len(recent_prices)):
            if recent_prices[i] > recent_prices[i-1]:
                trend_changes.append(1)  # 상승
            elif recent_prices[i] < recent_prices[i-1]:
                trend_changes.append(-1)  # 하락
            else:
                trend_changes.append(0)  # 보합
        
        up_count = trend_changes.count(1)
        down_count = trend_changes.count(-1)
        
        if up_count >= 6:
            return {"pattern": "uptrend", "confidence": 0.8}
        elif down_count >= 6:
            return {"pattern": "downtrend", "confidence": 0.8}
        elif abs(up_count - down_count) <= 2:
            return {"pattern": "sideways", "confidence": 0.6}
        else:
            return {"pattern": "mixed", "confidence": 0.4}
    
    def analyze_volume(self) -> Dict[str, Any]:
        """거래량 분석"""
        if len(self.volume_history) < 5:
            return {"status": "insufficient_data"}
        
        recent_volume = sum(self.volume_history[-5:]) / 5
        avg_volume = sum(self.volume_history) / len(self.volume_history)
        
        volume_ratio = recent_volume / avg_volume if avg_volume > 0 else 1
        
        if volume_ratio > 1.5:
            return {"status": "high_volume", "ratio": round(volume_ratio, 2)}
        elif volume_ratio < 0.7:
            return {"status": "low_volume", "ratio": round(volume_ratio, 2)}
        else:
            return {"status": "normal_volume", "ratio": round(volume_ratio, 2)}
    
    def perform_analysis(self, price_data: PriceData) -> Dict[str, Any]:
        """종합 기술적 분석"""
        self.add_price_data(price_data)
        
        # 캐시된 분석 결과 확인 (1초 이내)
        now = datetime.now()
        if (self.last_analysis and self.analysis_cache_time and 
            (now - self.analysis_cache_time).total_seconds() < 1):
            return self.last_analysis
        
        # 새로운 분석 수행
        ma_5 = self.calculate_moving_average(5)
        ma_10 = self.calculate_moving_average(10)
        rsi = self.calculate_rsi()
        pattern = self.detect_pattern()
        volume_analysis = self.analyze_volume()
        
        # 매매 신호 생성
        signal = "HOLD"
        signal_strength = 0
        
        signals = []
        
        # 이동평균 신호
        if ma_5 and ma_10:
            if ma_5 > ma_10 * 1.01:  # 1% 이상 차이
                signals.append(("MA_BULLISH", 0.6))
            elif ma_5 < ma_10 * 0.99:  # 1% 이상 차이
                signals.append(("MA_BEARISH", -0.6))
        
        # RSI 신호
        if rsi:
            if rsi < 30:
                signals.append(("RSI_OVERSOLD", 0.8))
            elif rsi > 70:
                signals.append(("RSI_OVERBOUGHT", -0.8))
        
        # 패턴 신호
        if pattern["confidence"] > 0.6:
            if pattern["pattern"] == "uptrend":
                signals.append(("PATTERN_BULLISH", 0.7))
            elif pattern["pattern"] == "downtrend":
                signals.append(("PATTERN_BEARISH", -0.7))
        
        # 거래량 신호
        if volume_analysis["status"] == "high_volume":
            signals.append(("VOLUME_SURGE", 0.3))
        
        # 종합 신호 계산
        if signals:
            total_strength = sum(strength for _, strength in signals)
            signal_count = len(signals)
            avg_strength = total_strength / signal_count
            
            if avg_strength > 0.5:
                signal = "BUY"
                signal_strength = min(avg_strength, 1.0)
            elif avg_strength < -0.5:
                signal = "SELL"
                signal_strength = max(avg_strength, -1.0)
            else:
                signal = "HOLD"
                signal_strength = avg_strength
        
        analysis_result = {
            "symbol": price_data.symbol,
            "current_price": price_data.current_price,
            "technical_indicators": {
                "ma_5": ma_5,
                "ma_10": ma_10,
                "rsi": rsi
            },
            "pattern_analysis": pattern,
            "volume_analysis": volume_analysis,
            "trading_signal": {
                "signal": signal,
                "strength": round(signal_strength, 2),
                "components": [{"type": sig, "strength": strength} for sig, strength in signals]
            },
            "timestamp": price_data.timestamp,
            "analyzer": "TechnicalAnalyzer"
        }
        
        # 결과 캐시
        self.last_analysis = analysis_result
        self.analysis_cache_time = now
        
        return analysis_result


class StreamingServer:
    """
    실시간 스트리밍 서버
    
    WebSocket을 통해 실시간 주가 데이터와 분석 결과를 클라이언트에게 전송합니다.
    """
    
    def __init__(self, port: int = 8765):
        self.port = port
        self.clients: Set[websockets.WebSocketServerProtocol] = set()
        
        # 데이터 생성기
        self.data_simulator = RealTimeDataSimulator()
        self.analyzer = TechnicalAnalyzer()
        
        # 스트리밍 제어
        self.streaming = False
        self.stream_interval = 1.0  # 1초마다 업데이트
        
        # 구독 관리
        self.subscriptions: Dict[websockets.WebSocketServerProtocol, Set[str]] = {}
    
    async def register_client(self, websocket: websockets.WebSocketServerProtocol):
        """클라이언트 등록"""
        self.clients.add(websocket)
        self.subscriptions[websocket] = set()
        client_id = f"client_{len(self.clients)}"
        logger.info(f"🔗 클라이언트 연결: {client_id} (총 {len(self.clients)}개)")
        
        # 환영 메시지 전송
        welcome_msg = StreamMessage(
            message_type=MessageType.SYSTEM_STATUS,
            timestamp=datetime.now().isoformat(),
            data={
                "status": "connected",
                "client_id": client_id,
                "available_subscriptions": ["price_updates", "analysis_results", "market_alerts"],
                "current_symbol": self.data_simulator.symbol,
                "streaming_active": self.streaming
            }
        )
        
        await websocket.send(json.dumps(asdict(welcome_msg)))
    
    async def unregister_client(self, websocket: websockets.WebSocketServerProtocol):
        """클라이언트 등록 해제"""
        if websocket in self.clients:
            self.clients.remove(websocket)
            if websocket in self.subscriptions:
                del self.subscriptions[websocket]
            logger.info(f"🔌 클라이언트 연결 해제 (총 {len(self.clients)}개)")
    
    async def handle_client_message(self, websocket: websockets.WebSocketServerProtocol, message: str):
        """클라이언트 메시지 처리"""
        try:
            data = json.loads(message)
            command = data.get("command")
            params = data.get("params", {})
            
            logger.info(f"📨 클라이언트 명령 수신: {command}")
            
            response = None
            
            if command == "subscribe":
                # 구독 설정
                subscription_type = params.get("type", "price_updates")
                self.subscriptions[websocket].add(subscription_type)
                response = {
                    "status": "success",
                    "message": f"{subscription_type} 구독 완료",
                    "subscriptions": list(self.subscriptions[websocket])
                }
                
            elif command == "unsubscribe":
                # 구독 해제
                subscription_type = params.get("type")
                if subscription_type in self.subscriptions[websocket]:
                    self.subscriptions[websocket].remove(subscription_type)
                response = {
                    "status": "success",
                    "message": f"{subscription_type} 구독 해제 완료",
                    "subscriptions": list(self.subscriptions[websocket])
                }
                
            elif command == "start_streaming":
                # 스트리밍 시작
                if not self.streaming:
                    self.streaming = True
                    asyncio.create_task(self.start_data_stream())
                    response = {"status": "success", "message": "스트리밍 시작"}
                else:
                    response = {"status": "info", "message": "이미 스트리밍 중"}
                    
            elif command == "stop_streaming":
                # 스트리밍 중지
                self.streaming = False
                response = {"status": "success", "message": "스트리밍 중지"}
                
            elif command == "get_status":
                # 상태 조회
                response = {
                    "streaming_active": self.streaming,
                    "connected_clients": len(self.clients),
                    "current_price": self.data_simulator.current_price,
                    "symbol": self.data_simulator.symbol,
                    "market_hours": self.data_simulator.is_market_hours()
                }
            
            elif command == "set_interval":
                # 업데이트 간격 설정
                interval = params.get("interval", 1.0)
                self.stream_interval = max(0.1, min(10.0, interval))  # 0.1-10초 제한
                response = {
                    "status": "success", 
                    "message": f"업데이트 간격을 {self.stream_interval}초로 설정"
                }
            
            else:
                response = {"status": "error", "message": f"알 수 없는 명령: {command}"}
            
            # 응답 전송
            if response:
                response_msg = StreamMessage(
                    message_type=MessageType.CLIENT_COMMAND,
                    timestamp=datetime.now().isoformat(),
                    data=response
                )
                await websocket.send(json.dumps(asdict(response_msg)))
                
        except Exception as e:
            logger.error(f"❌ 클라이언트 메시지 처리 실패: {str(e)}")
            error_msg = StreamMessage(
                message_type=MessageType.ERROR,
                timestamp=datetime.now().isoformat(),
                data={"error": "message_processing_failed", "details": str(e)}
            )
            await websocket.send(json.dumps(asdict(error_msg)))
    
    async def broadcast_to_subscribers(self, message_type: MessageType, data: Dict[str, Any]):
        """구독자들에게 메시지 브로드캐스트"""
        if not self.clients:
            return
        
        message = StreamMessage(
            message_type=message_type,
            timestamp=datetime.now().isoformat(),
            data=data
        )
        
        message_json = json.dumps(asdict(message))
        
        # 구독 타입에 따른 필터링
        subscription_filter = {
            MessageType.PRICE_UPDATE: "price_updates",
            MessageType.ANALYSIS_RESULT: "analysis_results",
            MessageType.MARKET_ALERT: "market_alerts"
        }
        
        target_subscription = subscription_filter.get(message_type)
        
        disconnected_clients = []
        for client in self.clients:
            try:
                # 구독 확인
                if target_subscription and target_subscription not in self.subscriptions.get(client, set()):
                    continue
                
                await client.send(message_json)
            except websockets.exceptions.ConnectionClosed:
                disconnected_clients.append(client)
            except Exception as e:
                logger.warning(f"⚠️ 클라이언트 전송 실패: {str(e)}")
                disconnected_clients.append(client)
        
        # 연결 해제된 클라이언트 정리
        for client in disconnected_clients:
            await self.unregister_client(client)
    
    async def start_data_stream(self):
        """데이터 스트리밍 시작"""
        logger.info("📊 실시간 데이터 스트리밍 시작")
        
        while self.streaming:
            try:
                # 새로운 주가 데이터 생성
                price_data = self.data_simulator.update_price()
                
                # 주가 데이터 브로드캐스트
                await self.broadcast_to_subscribers(
                    MessageType.PRICE_UPDATE,
                    asdict(price_data)
                )
                
                # 기술적 분석 수행
                analysis_result = self.analyzer.perform_analysis(price_data)
                
                # 분석 결과 브로드캐스트
                await self.broadcast_to_subscribers(
                    MessageType.ANALYSIS_RESULT,
                    analysis_result
                )
                
                # 시장 알림 체크
                await self.check_market_alerts(price_data, analysis_result)
                
                # 로그 출력 (가끔씩만)
                if random.random() < 0.1:  # 10% 확률
                    logger.info(
                        f"📈 {price_data.company_name}: "
                        f"{price_data.current_price:,}원 "
                        f"({price_data.price_change:+,}원, {price_data.price_change_percent:+.2f}%) "
                        f"신호: {analysis_result['trading_signal']['signal']}"
                    )
                
                await asyncio.sleep(self.stream_interval)
                
            except Exception as e:
                logger.error(f"❌ 데이터 스트리밍 중 오류: {str(e)}")
                await asyncio.sleep(1)
        
        logger.info("📊 실시간 데이터 스트리밍 중지")
    
    async def check_market_alerts(self, price_data: PriceData, analysis_result: Dict[str, Any]):
        """시장 알림 확인"""
        alerts = []
        
        # 급격한 가격 변동 확인
        if abs(price_data.price_change_percent) >= 3.0:
            alert_level = AlertLevel.WARNING if abs(price_data.price_change_percent) < 5.0 else AlertLevel.CRITICAL
            alerts.append({
                "level": alert_level.value,
                "title": f"급격한 가격 변동 감지",
                "message": f"{price_data.company_name} {price_data.price_change_percent:+.2f}% 변동",
                "data": {"price_change_percent": price_data.price_change_percent}
            })
        
        # RSI 과매수/과매도 확인
        rsi = analysis_result["technical_indicators"]["rsi"]
        if rsi:
            if rsi > 80:
                alerts.append({
                    "level": AlertLevel.WARNING.value,
                    "title": "과매수 신호",
                    "message": f"RSI {rsi:.1f} - 과매수 구간",
                    "data": {"rsi": rsi}
                })
            elif rsi < 20:
                alerts.append({
                    "level": AlertLevel.WARNING.value,
                    "title": "과매도 신호",
                    "message": f"RSI {rsi:.1f} - 과매도 구간",
                    "data": {"rsi": rsi}
                })
        
        # 강한 매매 신호 확인
        signal = analysis_result["trading_signal"]
        if abs(signal["strength"]) > 0.8:
            alerts.append({
                "level": AlertLevel.INFO.value,
                "title": f"강한 {signal['signal']} 신호",
                "message": f"신호 강도: {signal['strength']:.2f}",
                "data": signal
            })
        
        # 알림 브로드캐스트
        for alert in alerts:
            await self.broadcast_to_subscribers(
                MessageType.MARKET_ALERT,
                alert
            )
    
    async def handle_client(self, websocket: websockets.WebSocketServerProtocol, path: str):
        """클라이언트 연결 처리"""
        await self.register_client(websocket)
        
        try:
            async for message in websocket:
                await self.handle_client_message(websocket, message)
        except websockets.exceptions.ConnectionClosed:
            logger.info("🔌 클라이언트 연결 종료")
        except Exception as e:
            logger.error(f"❌ 클라이언트 처리 중 오류: {str(e)}")
        finally:
            await self.unregister_client(websocket)
    
    async def start_server(self):
        """서버 시작"""
        logger.info(f"🚀 실시간 스트리밍 서버 시작 (포트 {self.port})")
        
        # 자동 스트리밍 시작
        self.streaming = True
        asyncio.create_task(self.start_data_stream())
        
        start_server = websockets.serve(self.handle_client, "localhost", self.port)
        
        logger.info(f"✅ WebSocket 서버가 ws://localhost:{self.port}에서 실행 중")
        logger.info(f"📊 삼성SDI({self.data_simulator.symbol}) 실시간 스트리밍 활성화")
        
        await start_server


class AnalysisClient:
    """
    실시간 분석 클라이언트
    
    스트리밍 서버로부터 실시간 데이터를 받아 처리합니다.
    """
    
    def __init__(self, server_port: int = 8765):
        self.server_uri = f"ws://localhost:{server_port}"
        self.websocket = None
        self.running = False
        
        # 수신 데이터 통계
        self.price_updates_received = 0
        self.analysis_received = 0
        self.alerts_received = 0
        
        # 로컬 분석 데이터
        self.latest_price = None
        self.latest_analysis = None
    
    async def connect(self):
        """서버 연결"""
        try:
            logger.info(f"🔗 스트리밍 서버 연결 중: {self.server_uri}")
            self.websocket = await websockets.connect(self.server_uri)
            logger.info("✅ 스트리밍 서버 연결 성공")
            return True
        except Exception as e:
            logger.error(f"❌ 서버 연결 실패: {str(e)}")
            return False
    
    async def disconnect(self):
        """연결 해제"""
        if self.websocket:
            await self.websocket.close()
            logger.info("🔌 서버 연결 해제")
    
    async def send_command(self, command: str, params: Dict[str, Any] = None):
        """서버에 명령 전송"""
        if not self.websocket:
            logger.error("❌ 서버에 연결되지 않음")
            return False
        
        try:
            message = {
                "command": command,
                "params": params or {},
                "timestamp": datetime.now().isoformat()
            }
            
            await self.websocket.send(json.dumps(message))
            logger.info(f"📤 명령 전송: {command}")
            return True
        except Exception as e:
            logger.error(f"❌ 명령 전송 실패: {str(e)}")
            return False
    
    async def handle_message(self, message_data: Dict[str, Any]):
        """메시지 처리"""
        message_type = MessageType(message_data["message_type"])
        data = message_data["data"]
        timestamp = message_data["timestamp"]
        
        if message_type == MessageType.PRICE_UPDATE:
            self.price_updates_received += 1
            self.latest_price = data
            
            # 주요 변동만 출력
            if abs(data["price_change_percent"]) >= 1.0:
                logger.info(
                    f"📈 가격 업데이트: {data['company_name']} "
                    f"{data['current_price']:,}원 "
                    f"({data['price_change']:+,}원, {data['price_change_percent']:+.2f}%)"
                )
        
        elif message_type == MessageType.ANALYSIS_RESULT:
            self.analysis_received += 1
            self.latest_analysis = data
            
            signal = data["trading_signal"]
            if abs(signal["strength"]) > 0.6:  # 강한 신호만 출력
                logger.info(
                    f"🔍 분석 결과: {signal['signal']} "
                    f"(강도: {signal['strength']:.2f}) "
                    f"RSI: {data['technical_indicators']['rsi']}"
                )
        
        elif message_type == MessageType.MARKET_ALERT:
            self.alerts_received += 1
            level_emoji = {"info": "ℹ️", "warning": "⚠️", "critical": "🚨"}
            emoji = level_emoji.get(data["level"], "📢")
            
            logger.info(f"{emoji} 시장 알림: {data['title']} - {data['message']}")
        
        elif message_type == MessageType.CLIENT_COMMAND:
            logger.info(f"📨 서버 응답: {data.get('message', 'N/A')}")
        
        elif message_type == MessageType.SYSTEM_STATUS:
            logger.info(f"💻 시스템 상태: {data}")
        
        elif message_type == MessageType.ERROR:
            logger.error(f"❌ 서버 오류: {data}")
    
    async def listen_stream(self):
        """스트림 수신 대기"""
        if not self.websocket:
            logger.error("❌ 서버에 연결되지 않음")
            return
        
        logger.info("👂 실시간 스트림 수신 시작")
        self.running = True
        
        try:
            async for message in self.websocket:
                if not self.running:
                    break
                
                try:
                    message_data = json.loads(message)
                    await self.handle_message(message_data)
                except json.JSONDecodeError:
                    logger.error(f"❌ JSON 파싱 실패: {message}")
                except Exception as e:
                    logger.error(f"❌ 메시지 처리 실패: {str(e)}")
        
        except websockets.exceptions.ConnectionClosed:
            logger.info("🔌 서버 연결 종료")
        except Exception as e:
            logger.error(f"❌ 스트림 수신 중 오류: {str(e)}")
        finally:
            self.running = False
    
    def print_statistics(self):
        """수신 통계 출력"""
        print(f"\n📊 수신 통계:")
        print(f"   주가 업데이트: {self.price_updates_received:,}개")
        print(f"   분석 결과: {self.analysis_received:,}개")
        print(f"   시장 알림: {self.alerts_received:,}개")
        
        if self.latest_price:
            print(f"\n💰 최신 주가:")
            print(f"   종목: {self.latest_price['company_name']}")
            print(f"   현재가: {self.latest_price['current_price']:,}원")
            print(f"   변동: {self.latest_price['price_change']:+,}원 ({self.latest_price['price_change_percent']:+.2f}%)")
        
        if self.latest_analysis:
            signal = self.latest_analysis["trading_signal"]
            print(f"\n🔍 최신 분석:")
            print(f"   매매 신호: {signal['signal']}")
            print(f"   신호 강도: {signal['strength']:.2f}")
            
            rsi = self.latest_analysis["technical_indicators"]["rsi"]
            if rsi:
                print(f"   RSI: {rsi:.1f}")


async def run_streaming_server(port: int):
    """스트리밍 서버 실행"""
    server = StreamingServer(port)
    
    print(f"\n{'='*60}")
    print(f"  📡 실시간 스트리밍 서버 실행 중 (포트 {port})")
    print(f"{'='*60}")
    print(f"WebSocket 연결: ws://localhost:{port}")
    print(f"대상 종목: 삼성SDI (006400)")
    print(f"스트리밍: 실시간 주가 + 기술적 분석")
    print(f"\n💡 클라이언트 명령:")
    print(f"  subscribe/unsubscribe - 구독 관리")
    print(f"  start_streaming/stop_streaming - 스트리밍 제어")
    print(f"  get_status - 상태 조회")
    print(f"  set_interval - 업데이트 간격 설정")
    print(f"\n⏹️ 종료: Ctrl+C")
    
    try:
        await server.start_server()
        
        # 서버 유지
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("🔚 스트리밍 서버 종료 중...")


async def run_analysis_client(server_port: int):
    """분석 클라이언트 실행"""
    client = AnalysisClient(server_port)
    
    print(f"\n{'='*60}")
    print(f"  📊 실시간 분석 클라이언트 실행 중")
    print(f"{'='*60}")
    print(f"서버 연결: ws://localhost:{server_port}")
    print(f"자동 구독: price_updates, analysis_results, market_alerts")
    print(f"\n⏹️ 종료: Ctrl+C")
    
    # 서버 연결
    connected = await client.connect()
    if not connected:
        print("❌ 서버 연결 실패")
        return
    
    try:
        # 자동 구독 설정
        await client.send_command("subscribe", {"type": "price_updates"})
        await asyncio.sleep(0.1)
        await client.send_command("subscribe", {"type": "analysis_results"})
        await asyncio.sleep(0.1)
        await client.send_command("subscribe", {"type": "market_alerts"})
        await asyncio.sleep(0.1)
        
        # 스트림 수신 시작
        await client.listen_stream()
        
    except KeyboardInterrupt:
        print("\n🔚 클라이언트 종료 중...")
        client.print_statistics()
    finally:
        await client.disconnect()


async def demonstrate_realtime_streaming():
    """실시간 스트리밍 데모"""
    print(f"\n{'='*60}")
    print(f"  📡 실시간 스트리밍 데모")
    print(f"{'='*60}")
    
    server_port = 8765
    
    print("🚀 서버와 클라이언트를 동시에 시작합니다...")
    
    # 서버 시작
    server = StreamingServer(server_port)
    server_task = asyncio.create_task(server.start_server())
    
    # 서버 준비 대기
    await asyncio.sleep(2)
    
    # 클라이언트 연결
    client = AnalysisClient(server_port)
    connected = await client.connect()
    
    if not connected:
        print("❌ 클라이언트 연결 실패")
        server_task.cancel()
        return
    
    try:
        # 구독 설정
        await client.send_command("subscribe", {"type": "price_updates"})
        await client.send_command("subscribe", {"type": "analysis_results"})  
        await client.send_command("subscribe", {"type": "market_alerts"})
        
        print("✅ 실시간 스트리밍 데모 시작")
        print("📊 삼성SDI 실시간 데이터를 수신합니다...")
        print("⏹️ 종료: Ctrl+C")
        
        # 30초 데모 실행
        demo_duration = 30
        start_time = asyncio.get_event_loop().time()
        
        listen_task = asyncio.create_task(client.listen_stream())
        
        while True:
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed >= demo_duration:
                print(f"\n⏰ {demo_duration}초 데모 완료")
                break
            
            await asyncio.sleep(1)
        
        # 데모 종료
        client.running = False
        listen_task.cancel()
        
        # 통계 출력
        client.print_statistics()
        
        print(f"\n✅ 실시간 스트리밍 데모 성공!")
        
    except KeyboardInterrupt:
        print("\n🔚 데모 사용자 종료")
        client.print_statistics()
    finally:
        await client.disconnect()
        server_task.cancel()


def main():
    parser = argparse.ArgumentParser(description="실시간 스트리밍 데모")
    parser.add_argument("--role", choices=["server", "client", "demo"],
                       help="실행할 역할")
    parser.add_argument("--port", type=int, default=8765,
                       help="서버 포트 번호")
    
    args = parser.parse_args()
    
    if args.role == "server":
        print("📡 실시간 스트리밍 학습을 시작합니다!")
        print("이 예제는 WebSocket을 통한 실시간 데이터 스트리밍을 보여줍니다.")
        asyncio.run(run_streaming_server(args.port))
    elif args.role == "client":
        asyncio.run(run_analysis_client(args.port))
    elif args.role == "demo":
        print("📡 실시간 스트리밍 학습을 시작합니다!")
        print("이 예제는 WebSocket을 통한 실시간 데이터 스트리밍을 보여줍니다.")
        asyncio.run(demonstrate_realtime_streaming())
    else:
        print("사용법:")
        print("  스트리밍 서버: python 3_3_realtime_streaming.py --role server --port 8765")
        print("  분석 클라이언트: python 3_3_realtime_streaming.py --role client --port 8765")
        print("  실시간 데모:     python 3_3_realtime_streaming.py --role demo")


if __name__ == "__main__":
    main()