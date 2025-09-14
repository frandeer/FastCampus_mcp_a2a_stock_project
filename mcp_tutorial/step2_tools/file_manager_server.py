"""
Step 2: 파일 관리 MCP 서버
파일 시스템 작업을 위한 도구들을 제공하는 MCP 서버
"""

from fastmcp import FastMCP
import os
import json
from pathlib import Path
from typing import List, Dict, Any
import datetime

# MCP 서버 인스턴스 생성
mcp = FastMCP(name="FileManagerServer", version="2.0.0")

# 안전한 작업을 위한 기본 디렉토리 설정
SAFE_BASE_DIR = Path.cwd() / "sandbox"
SAFE_BASE_DIR.mkdir(exist_ok=True)


def _safe_path(file_path: str) -> Path:
    """안전한 경로 검증"""
    path = Path(file_path).resolve()
    base = SAFE_BASE_DIR.resolve()
    
    # sandbox 디렉토리 내부인지 확인
    try:
        path.relative_to(base)
        return path
    except ValueError:
        raise ValueError(f"접근이 제한된 경로입니다: {file_path}")


@mcp.tool
def list_files(directory: str = ".") -> Dict[str, Any]:
    """디렉토리의 파일 목록을 반환합니다"""
    try:
        if directory == ".":
            dir_path = SAFE_BASE_DIR
        else:
            dir_path = _safe_path(directory)
        
        if not dir_path.exists():
            return {"status": "error", "message": f"디렉토리가 존재하지 않습니다: {directory}"}
        
        if not dir_path.is_dir():
            return {"status": "error", "message": f"디렉토리가 아닙니다: {directory}"}
        
        files = []
        for item in dir_path.iterdir():
            stat = item.stat()
            files.append({
                "name": item.name,
                "type": "directory" if item.is_dir() else "file",
                "size": stat.st_size,
                "modified": datetime.datetime.fromtimestamp(stat.st_mtime).isoformat()
            })
        
        return {
            "status": "success",
            "directory": str(dir_path.relative_to(SAFE_BASE_DIR)),
            "files": sorted(files, key=lambda x: (x["type"] == "file", x["name"]))
        }
        
    except Exception as e:
        return {"status": "error", "message": str(e)}


@mcp.tool
def read_file(file_path: str, encoding: str = "utf-8") -> Dict[str, Any]:
    """파일의 내용을 읽어서 반환합니다"""
    try:
        path = _safe_path(file_path)
        
        if not path.exists():
            return {"status": "error", "message": f"파일이 존재하지 않습니다: {file_path}"}
        
        if not path.is_file():
            return {"status": "error", "message": f"파일이 아닙니다: {file_path}"}
        
        with open(path, 'r', encoding=encoding) as f:
            content = f.read()
        
        return {
            "status": "success", 
            "file_path": str(path.relative_to(SAFE_BASE_DIR)),
            "content": content,
            "size": len(content),
            "encoding": encoding
        }
        
    except UnicodeDecodeError:
        return {"status": "error", "message": f"파일을 {encoding} 인코딩으로 읽을 수 없습니다"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@mcp.tool
def write_file(file_path: str, content: str, encoding: str = "utf-8") -> Dict[str, Any]:
    """파일에 내용을 씁니다"""
    try:
        path = _safe_path(file_path)
        
        # 상위 디렉토리 생성
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, 'w', encoding=encoding) as f:
            f.write(content)
        
        return {
            "status": "success",
            "file_path": str(path.relative_to(SAFE_BASE_DIR)),
            "bytes_written": len(content.encode(encoding)),
            "encoding": encoding
        }
        
    except Exception as e:
        return {"status": "error", "message": str(e)}


@mcp.tool
def create_directory(directory: str) -> Dict[str, Any]:
    """새 디렉토리를 생성합니다"""
    try:
        path = _safe_path(directory)
        path.mkdir(parents=True, exist_ok=True)
        
        return {
            "status": "success",
            "directory": str(path.relative_to(SAFE_BASE_DIR)),
            "message": "디렉토리가 생성되었습니다"
        }
        
    except Exception as e:
        return {"status": "error", "message": str(e)}


@mcp.tool
def delete_file(file_path: str) -> Dict[str, Any]:
    """파일을 삭제합니다"""
    try:
        path = _safe_path(file_path)
        
        if not path.exists():
            return {"status": "error", "message": f"파일이 존재하지 않습니다: {file_path}"}
        
        if path.is_dir():
            return {"status": "error", "message": "디렉토리는 삭제할 수 없습니다. 파일만 삭제 가능합니다"}
        
        path.unlink()
        
        return {
            "status": "success",
            "file_path": str(path.relative_to(SAFE_BASE_DIR)),
            "message": "파일이 삭제되었습니다"
        }
        
    except Exception as e:
        return {"status": "error", "message": str(e)}


@mcp.tool
def file_info(file_path: str) -> Dict[str, Any]:
    """파일의 상세 정보를 반환합니다"""
    try:
        path = _safe_path(file_path)
        
        if not path.exists():
            return {"status": "error", "message": f"파일이 존재하지 않습니다: {file_path}"}
        
        stat = path.stat()
        
        return {
            "status": "success",
            "file_path": str(path.relative_to(SAFE_BASE_DIR)),
            "type": "directory" if path.is_dir() else "file",
            "size": stat.st_size,
            "created": datetime.datetime.fromtimestamp(stat.st_ctime).isoformat(),
            "modified": datetime.datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "accessible": os.access(path, os.R_OK),
            "writable": os.access(path, os.W_OK)
        }
        
    except Exception as e:
        return {"status": "error", "message": str(e)}


@mcp.tool
def search_files(pattern: str, directory: str = ".") -> Dict[str, Any]:
    """파일명 패턴으로 파일을 검색합니다"""
    try:
        if directory == ".":
            search_dir = SAFE_BASE_DIR
        else:
            search_dir = _safe_path(directory)
        
        if not search_dir.exists() or not search_dir.is_dir():
            return {"status": "error", "message": f"검색할 디렉토리가 존재하지 않습니다: {directory}"}
        
        matches = []
        for item in search_dir.rglob(pattern):
            if item.is_file():
                matches.append({
                    "file_path": str(item.relative_to(SAFE_BASE_DIR)),
                    "size": item.stat().st_size,
                    "modified": datetime.datetime.fromtimestamp(item.stat().st_mtime).isoformat()
                })
        
        return {
            "status": "success",
            "pattern": pattern,
            "search_directory": str(search_dir.relative_to(SAFE_BASE_DIR)),
            "matches": matches,
            "count": len(matches)
        }
        
    except Exception as e:
        return {"status": "error", "message": str(e)}


if __name__ == "__main__":
    print("📁 파일 관리 MCP 서버가 시작됩니다...")
    print(f"📂 작업 디렉토리: {SAFE_BASE_DIR}")
    print("사용 가능한 도구: list_files, read_file, write_file, create_directory,")
    print("               delete_file, file_info, search_files")
    print("🔒 보안: sandbox 디렉토리 내에서만 작업 가능")
    mcp.run()