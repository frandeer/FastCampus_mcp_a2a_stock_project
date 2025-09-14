"""
Step 1: 기본 MCP 서버
가장 간단한 MCP 서버 구현
"""

from fastmcp import FastMCP

# MCP 서버 인스턴스 생성
mcp = FastMCP(name="MyFirstServer", version="1.0.0")


@mcp.tool
def hello(name: str) -> str:
    """간단한 인사 기능"""
    return f"안녕하세요, {name}님! MCP 서버에 오신 것을 환영합니다! 🎉"


@mcp.tool  
def goodbye(name: str) -> str:
    """작별 인사 기능"""
    return f"안녕히 가세요, {name}님! 좋은 하루 되세요! 👋"


if __name__ == "__main__":
    print("🚀 기본 MCP 서버가 시작됩니다...")
    print("사용 가능한 도구: hello, goodbye")
    mcp.run()