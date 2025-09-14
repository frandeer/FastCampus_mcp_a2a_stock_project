#!/usr/bin/env python3
"""
빠른 MCP 서버 테스트 스크립트
"""

import sys
import subprocess
import asyncio
from pathlib import Path

async def test_basic_server():
    """기본 서버 간단 테스트"""
    print("🧪 기본 MCP 서버 테스트 시작...")
    
    try:
        # 기본 서버 파일 존재 확인
        server_path = Path("basic_server.py")
        if not server_path.exists():
            print("❌ basic_server.py 파일을 찾을 수 없습니다!")
            return False
            
        print("✅ basic_server.py 파일 존재 확인")
        
        # Python 임포트 테스트
        result = subprocess.run([
            sys.executable, "-c", 
            "import sys; sys.path.append('.'); from basic_server import mcp; print('✅ 서버 모듈 임포트 성공')"
        ], capture_output=True, text=True, cwd=Path(__file__).parent)
        
        if result.returncode == 0:
            print(result.stdout.strip())
            print("✅ MCP 서버가 정상적으로 구성되었습니다!")
            return True
        else:
            print(f"❌ 서버 임포트 실패: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ 테스트 중 오류 발생: {e}")
        return False

async def test_all_servers():
    """모든 서버 테스트"""
    servers = [
        "basic_server.py",
        "time_server.py", 
        "calculator_server.py"
    ]
    
    print("🚀 모든 MCP 서버 테스트 시작!")
    print("=" * 50)
    
    success_count = 0
    
    for server in servers:
        server_path = Path(server)
        if server_path.exists():
            print(f"\n🔍 {server} 테스트 중...")
            
            # 모듈 임포트 테스트
            module_name = server.replace('.py', '')
            result = subprocess.run([
                sys.executable, "-c",
                f"import sys; sys.path.append('.'); from {module_name} import mcp; print('✅ {server} 임포트 성공')"
            ], capture_output=True, text=True, cwd=Path(__file__).parent)
            
            if result.returncode == 0:
                print(result.stdout.strip())
                success_count += 1
            else:
                print(f"❌ {server} 임포트 실패")
                print(f"   오류: {result.stderr}")
        else:
            print(f"⚠️  {server} 파일이 존재하지 않습니다")
    
    print("\n" + "=" * 50)
    print(f"🎯 테스트 완료: {success_count}/{len(servers)} 서버 성공")
    
    if success_count == len(servers):
        print("🎉 모든 서버가 정상적으로 작동합니다!")
    else:
        print("⚠️  일부 서버에 문제가 있습니다. 위의 오류를 확인해주세요.")

if __name__ == "__main__":
    asyncio.run(test_all_servers())