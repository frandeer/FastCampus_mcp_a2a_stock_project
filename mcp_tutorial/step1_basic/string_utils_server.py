# TODO(human): string_utils_server.py 구현
# 
# 다음 기능들을 가진 MCP 서버를 만들어주세요:
# 
# @mcp.tool
# def get_string_length(text: str) -> int:
#     """문자열의 길이를 반환합니다"""
#     # 구현 필요
# 
# @mcp.tool  
# def reverse_string(text: str) -> str:
#     """문자열을 역순으로 변환합니다"""
#     # 구현 필요
# 
# @mcp.tool
# def to_uppercase(text: str) -> str:
#     """문자열을 대문자로 변환합니다"""
#     # 구현 필요
# 
# @mcp.tool
# def to_lowercase(text: str) -> str:
#     """문자열을 소문자로 변환합니다"""
#     # 구현 필요
# 
# @mcp.tool
# def count_words(text: str) -> int:
#     """문자열의 단어 개수를 세어 반환합니다"""
#     # 구현 필요 (공백으로 구분된 단어 개수)
#
# 기본 템플릿:
# from fastmcp import FastMCP
# mcp = FastMCP(name="StringUtilsServer", version="1.0.0")
# ... 함수들 구현 ...
# if __name__ == "__main__":
#     mcp.run()