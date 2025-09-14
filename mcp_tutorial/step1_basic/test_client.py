"""
Step 1: MCP 서버 테스트 클라이언트
만든 MCP 서버들을 테스트하는 클라이언트
"""

import asyncio
import subprocess
import sys
from fastmcp import Client


async def test_basic_server():
    """기본 서버 테스트"""
    print("\n🧪 기본 서버 테스트 시작...")
    
    # 서버 프로세스 시작
    server_process = subprocess.Popen(
        [sys.executable, "basic_server.py"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    try:
        # 클라이언트로 연결
        async with Client(
            transport_options={"process": server_process}
        ) as client:
            
            # 사용 가능한 도구 목록 확인
            tools = await client.list_tools()
            print(f"✅ 사용 가능한 도구들: {[tool.name for tool in tools.tools]}")
            
            # hello 도구 테스트
            result = await client.call_tool("hello", {"name": "Alice"})
            print(f"✅ hello 결과: {result.content[0].text}")
            
            # goodbye 도구 테스트
            result = await client.call_tool("goodbye", {"name": "Alice"})
            print(f"✅ goodbye 결과: {result.content[0].text}")
            
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
    finally:
        server_process.terminate()
        server_process.wait()


async def test_calculator_server():
    """계산기 서버 테스트"""
    print("\n🧪 계산기 서버 테스트 시작...")
    
    server_process = subprocess.Popen(
        [sys.executable, "calculator_server.py"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    try:
        async with Client(
            transport_options={"process": server_process}
        ) as client:
            
            # 덧셈 테스트
            result = await client.call_tool("add_numbers", {"a": 10, "b": 5})
            print(f"✅ 10 + 5 = {result.content[0].text}")
            
            # 곱셈 테스트
            result = await client.call_tool("multiply_numbers", {"a": 7, "b": 8})
            print(f"✅ 7 × 8 = {result.content[0].text}")
            
            # 나눗셈 테스트
            result = await client.call_tool("divide_numbers", {"a": 15, "b": 3})
            print(f"✅ 15 ÷ 3 = {result.content[0].text}")
            
            # 0으로 나누기 테스트 (에러 케이스)
            result = await client.call_tool("divide_numbers", {"a": 10, "b": 0})
            print(f"✅ 10 ÷ 0 = {result.content[0].text}")
            
            # 리스트 합계 테스트
            result = await client.call_tool("sum_list", {"numbers": [1, 2, 3, 4, 5]})
            print(f"✅ [1,2,3,4,5]의 합 = {result.content[0].text}")
            
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
    finally:
        server_process.terminate()
        server_process.wait()


async def test_time_server():
    """시간 서버 테스트"""
    print("\n🧪 시간 서버 테스트 시작...")
    
    server_process = subprocess.Popen(
        [sys.executable, "time_server.py"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    try:
        async with Client(
            transport_options={"process": server_process}
        ) as client:
            
            # 현재 시간 테스트
            result = await client.call_tool("get_current_time")
            print(f"✅ 현재 시간: {result.content[0].text}")
            
            # 오늘 날짜 테스트
            result = await client.call_tool("get_current_date")
            print(f"✅ 오늘 날짜: {result.content[0].text}")
            
            # 요일 테스트
            result = await client.call_tool("get_day_of_week")
            print(f"✅ 오늘 요일: {result.content[0].text}")
            
            # 타임스탬프 테스트
            result = await client.call_tool("get_timestamp")
            timestamp = result.content[0].text
            print(f"✅ 현재 타임스탬프: {timestamp}")
            
            # 타임스탬프 포맷 테스트
            result = await client.call_tool("format_timestamp", {
                "timestamp": int(timestamp),
                "format_string": "%Y년 %m월 %d일 %H시 %M분"
            })
            print(f"✅ 포맷된 시간: {result.content[0].text}")
            
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
    finally:
        server_process.terminate()
        server_process.wait()


async def main():
    """메인 테스트 함수"""
    print("🎯 MCP 서버 테스트를 시작합니다!")
    print("=" * 50)
    
    # 각 서버 테스트 실행
    await test_basic_server()
    await test_calculator_server() 
    await test_time_server()
    
    print("\n" + "=" * 50)
    print("🎉 모든 테스트가 완료되었습니다!")


if __name__ == "__main__":
    # asyncio 이벤트 루프 실행
    asyncio.run(main())