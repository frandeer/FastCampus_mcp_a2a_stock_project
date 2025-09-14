# TODO(human): list_utils_server.py 구현
#
# 다음 기능들을 가진 MCP 서버를 만들어주세요:
#
# @mcp.tool
# def find_max(numbers: List[float]) -> str:
#     """숫자 리스트에서 최대값을 찾습니다"""
#     # 빈 리스트 체크 필요
#     # 구현 필요
#
# @mcp.tool
# def find_min(numbers: List[float]) -> str:
#     """숫자 리스트에서 최소값을 찾습니다"""
#     # 빈 리스트 체크 필요
#     # 구현 필요
#
# @mcp.tool
# def sort_list(numbers: List[float], reverse: bool = False) -> List[float]:
#     """숫자 리스트를 정렬합니다"""
#     # reverse=True면 내림차순, False면 오름차순
#     # 구현 필요
#
# @mcp.tool
# def get_list_length(numbers: List[float]) -> int:
#     """리스트의 길이를 반환합니다"""
#     # 구현 필요
#
# @mcp.tool
# def remove_duplicates(numbers: List[float]) -> List[float]:
#     """리스트에서 중복을 제거합니다 (순서 유지)"""
#     # 구현 필요
#
# 기본 템플릿:
# from fastmcp import FastMCP
# from typing import List
# mcp = FastMCP(name="ListUtilsServer", version="1.0.0")
# ... 함수들 구현 ...
# if __name__ == "__main__":
#     mcp.run()