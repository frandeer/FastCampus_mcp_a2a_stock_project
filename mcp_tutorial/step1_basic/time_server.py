"""
Step 1: 시간 관련 MCP 서버
현재 시간과 날짜 정보를 제공하는 MCP 서버
"""

from fastmcp import FastMCP
from datetime import datetime
import time

# MCP 서버 인스턴스 생성
mcp = FastMCP(name="TimeServer", version="1.0.0")


@mcp.tool
def get_current_time() -> str:
    """현재 시간을 반환합니다 (YYYY-MM-DD HH:MM:SS 형식)"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@mcp.tool
def get_current_date() -> str:
    """오늘 날짜를 반환합니다 (YYYY-MM-DD 형식)"""
    return datetime.now().strftime("%Y-%m-%d")


@mcp.tool
def get_timestamp() -> int:
    """현재 Unix 타임스탬프를 반환합니다"""
    return int(time.time())


@mcp.tool
def format_timestamp(timestamp: int, format_string: str = "%Y-%m-%d %H:%M:%S") -> str:
    """Unix 타임스탬프를 지정된 형식으로 변환합니다"""
    dt = datetime.fromtimestamp(timestamp)
    return dt.strftime(format_string)


@mcp.tool
def get_day_of_week() -> str:
    """오늘이 무슨 요일인지 반환합니다"""
    days = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]
    return days[datetime.now().weekday()]


if __name__ == "__main__":
    print("⏰ 시간 MCP 서버가 시작됩니다...")
    print("사용 가능한 도구: get_current_time, get_current_date, get_timestamp, format_timestamp, get_day_of_week")
    mcp.run()