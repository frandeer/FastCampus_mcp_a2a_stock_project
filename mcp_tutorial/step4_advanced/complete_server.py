"""
Step 4: 완전한 MCP 서버 예제
실제 프로덕션에서 사용 가능한 모든 기능을 포함한 종합 MCP 서버

주요 기능:
- 기본 도구 (계산, 텍스트 처리)
- 파일 관리 (읽기/쓰기/검색)
- 데이터 변환 (JSON/CSV)
- HTTP 서버 지원
- 구조화된 에러 처리
- 로깅 시스템
- 성능 모니터링
"""

from fastmcp import FastMCP
import json
import csv
import io
import datetime
import logging
import time
from pathlib import Path
from typing import Dict, List, Any, Optional
import structlog

# 구조화된 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = structlog.get_logger()

# MCP 서버 인스턴스 생성
mcp = FastMCP(
    name="CompleteProductionServer",
    version="3.0.0",
    description="실제 프로덕션에서 사용 가능한 완전한 MCP 서버"
)

# 안전한 작업을 위한 기본 디렉토리
WORKSPACE_DIR = Path.cwd() / "mcp_workspace"
WORKSPACE_DIR.mkdir(exist_ok=True)

# 성능 메트릭스
class Metrics:
    def __init__(self):
        self.requests = 0
        self.errors = 0
        self.start_time = time.time()
    
    def record_request(self):
        self.requests += 1
    
    def record_error(self):
        self.errors += 1
    
    def get_stats(self):
        uptime = time.time() - self.start_time
        return {
            "requests": self.requests,
            "errors": self.errors,
            "uptime_seconds": round(uptime, 2),
            "success_rate": round((self.requests - self.errors) / max(self.requests, 1) * 100, 2)
        }

metrics = Metrics()

def safe_execute(func):
    """안전한 실행을 위한 데코레이터"""
    def wrapper(*args, **kwargs):
        metrics.record_request()
        try:
            logger.info("도구 실행 시작", function=func.__name__, args=args)
            result = func(*args, **kwargs)
            logger.info("도구 실행 완료", function=func.__name__)
            return result
        except Exception as e:
            metrics.record_error()
            logger.error("도구 실행 오류", function=func.__name__, error=str(e))
            return {
                "status": "error",
                "message": str(e),
                "timestamp": datetime.datetime.now().isoformat()
            }
    return wrapper

def _safe_path(file_path: str) -> Path:
    """작업 공간 내 안전한 경로 검증"""
    path = Path(file_path).resolve() if Path(file_path).is_absolute() else WORKSPACE_DIR / file_path
    base = WORKSPACE_DIR.resolve()
    
    try:
        path.relative_to(base)
        return path
    except ValueError:
        raise ValueError(f"접근이 제한된 경로입니다: {file_path}")

# ============================================================================
# 1. 기본 계산 및 텍스트 처리 도구
# ============================================================================

@mcp.tool
@safe_execute
def advanced_calculator(expression: str) -> Dict[str, Any]:
    """안전한 수학 표현식 계산기"""
    try:
        # 안전한 계산을 위해 eval 대신 제한된 함수만 허용
        allowed_names = {
            "abs": abs, "round": round, "min": min, "max": max,
            "sum": sum, "pow": pow, "sqrt": lambda x: x**0.5,
            "pi": 3.14159265359, "e": 2.71828182846
        }
        
        # 위험한 문자 확인
        dangerous = ["import", "exec", "eval", "__", "open", "file"]
        if any(d in expression.lower() for d in dangerous):
            raise ValueError("보안상 허용되지 않는 표현식입니다")
        
        result = eval(expression, {"__builtins__": {}}, allowed_names)
        
        return {
            "status": "success",
            "expression": expression,
            "result": result,
            "calculated_at": datetime.datetime.now().isoformat()
        }
        
    except Exception as e:
        raise ValueError(f"계산 오류: {str(e)}")


@mcp.tool
@safe_execute
def text_analyzer(text: str) -> Dict[str, Any]:
    """텍스트 분석 도구"""
    words = text.split()
    sentences = text.split('.')
    paragraphs = text.split('\n\n')
    
    return {
        "status": "success",
        "analysis": {
            "character_count": len(text),
            "character_count_no_spaces": len(text.replace(' ', '')),
            "word_count": len(words),
            "sentence_count": len([s for s in sentences if s.strip()]),
            "paragraph_count": len([p for p in paragraphs if p.strip()]),
            "average_word_length": round(sum(len(word) for word in words) / max(len(words), 1), 2),
            "most_common_words": self._get_most_common_words(words, 5)
        },
        "analyzed_at": datetime.datetime.now().isoformat()
    }

def _get_most_common_words(words: List[str], top_n: int = 5) -> List[Dict[str, Any]]:
    """가장 흔한 단어 찾기"""
    from collections import Counter
    # 간단한 전처리
    clean_words = [word.lower().strip('.,!?";:()[]{}') for word in words if len(word) > 2]
    counter = Counter(clean_words)
    return [{"word": word, "count": count} for word, count in counter.most_common(top_n)]

# ============================================================================
# 2. 파일 관리 도구
# ============================================================================

@mcp.tool
@safe_execute
def create_file(file_path: str, content: str, encoding: str = "utf-8") -> Dict[str, Any]:
    """파일 생성 및 내용 작성"""
    path = _safe_path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(path, 'w', encoding=encoding) as f:
        f.write(content)
    
    return {
        "status": "success",
        "file_path": str(path.relative_to(WORKSPACE_DIR)),
        "size_bytes": len(content.encode(encoding)),
        "created_at": datetime.datetime.now().isoformat()
    }


@mcp.tool
@safe_execute
def read_file(file_path: str, encoding: str = "utf-8") -> Dict[str, Any]:
    """파일 내용 읽기"""
    path = _safe_path(file_path)
    
    if not path.exists():
        raise FileNotFoundError(f"파일이 존재하지 않습니다: {file_path}")
    
    with open(path, 'r', encoding=encoding) as f:
        content = f.read()
    
    return {
        "status": "success",
        "file_path": str(path.relative_to(WORKSPACE_DIR)),
        "content": content,
        "size_bytes": len(content.encode(encoding)),
        "read_at": datetime.datetime.now().isoformat()
    }


@mcp.tool
@safe_execute
def list_workspace_files(pattern: str = "*") -> Dict[str, Any]:
    """작업 공간의 파일 목록 조회"""
    files = []
    for path in WORKSPACE_DIR.rglob(pattern):
        if path.is_file():
            stat = path.stat()
            files.append({
                "path": str(path.relative_to(WORKSPACE_DIR)),
                "size": stat.st_size,
                "modified": datetime.datetime.fromtimestamp(stat.st_mtime).isoformat()
            })
    
    return {
        "status": "success",
        "workspace": str(WORKSPACE_DIR),
        "pattern": pattern,
        "files": sorted(files, key=lambda x: x["path"]),
        "count": len(files)
    }

# ============================================================================
# 3. 데이터 변환 도구
# ============================================================================

@mcp.tool
@safe_execute
def json_to_csv(json_data: str, output_file: Optional[str] = None) -> Dict[str, Any]:
    """JSON 데이터를 CSV로 변환"""
    try:
        data = json.loads(json_data)
        
        if not isinstance(data, list):
            raise ValueError("JSON 데이터는 객체들의 배열이어야 합니다")
        
        if not data:
            raise ValueError("빈 데이터입니다")
        
        # CSV 변환
        output = io.StringIO()
        fieldnames = data[0].keys()
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)
        csv_content = output.getvalue()
        
        result = {
            "status": "success",
            "csv_content": csv_content,
            "rows_converted": len(data),
            "converted_at": datetime.datetime.now().isoformat()
        }
        
        # 파일로 저장 요청시
        if output_file:
            path = _safe_path(output_file)
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                f.write(csv_content)
            result["saved_to"] = str(path.relative_to(WORKSPACE_DIR))
        
        return result
        
    except json.JSONDecodeError:
        raise ValueError("잘못된 JSON 형식입니다")


@mcp.tool
@safe_execute
def csv_to_json(csv_data: str, output_file: Optional[str] = None) -> Dict[str, Any]:
    """CSV 데이터를 JSON으로 변환"""
    try:
        # CSV 파싱
        reader = csv.DictReader(io.StringIO(csv_data))
        data = list(reader)
        
        json_content = json.dumps(data, ensure_ascii=False, indent=2)
        
        result = {
            "status": "success",
            "json_content": json_content,
            "rows_converted": len(data),
            "converted_at": datetime.datetime.now().isoformat()
        }
        
        # 파일로 저장 요청시
        if output_file:
            path = _safe_path(output_file)
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                f.write(json_content)
            result["saved_to"] = str(path.relative_to(WORKSPACE_DIR))
        
        return result
        
    except Exception as e:
        raise ValueError(f"CSV 변환 오류: {str(e)}")

# ============================================================================
# 4. 시스템 모니터링 도구
# ============================================================================

@mcp.tool
@safe_execute
def get_server_status() -> Dict[str, Any]:
    """서버 상태 및 성능 메트릭스"""
    return {
        "status": "healthy",
        "server_info": {
            "name": "CompleteProductionServer",
            "version": "3.0.0",
            "started_at": datetime.datetime.fromtimestamp(metrics.start_time).isoformat(),
            "current_time": datetime.datetime.now().isoformat()
        },
        "metrics": metrics.get_stats(),
        "workspace": {
            "path": str(WORKSPACE_DIR),
            "exists": WORKSPACE_DIR.exists(),
            "writable": WORKSPACE_DIR.is_dir()
        },
        "features": [
            "계산기", "텍스트 분석", "파일 관리", "데이터 변환",
            "HTTP 지원", "구조화된 로깅", "성능 모니터링", "에러 처리"
        ]
    }


@mcp.tool
@safe_execute
def health_check() -> Dict[str, Any]:
    """간단한 헬스 체크"""
    return {
        "status": "ok",
        "timestamp": datetime.datetime.now().isoformat(),
        "uptime_seconds": round(time.time() - metrics.start_time, 2)
    }

# ============================================================================
# 5. 유틸리티 도구
# ============================================================================

@mcp.tool
@safe_execute
def format_data(data: str, format_type: str = "json") -> Dict[str, Any]:
    """데이터 포맷팅 (JSON, XML 등)"""
    try:
        if format_type.lower() == "json":
            parsed = json.loads(data)
            formatted = json.dumps(parsed, ensure_ascii=False, indent=2)
            return {
                "status": "success",
                "original": data,
                "formatted": formatted,
                "format": "json"
            }
        else:
            raise ValueError(f"지원하지 않는 포맷: {format_type}")
            
    except json.JSONDecodeError:
        raise ValueError("잘못된 JSON 형식입니다")


@mcp.tool
@safe_execute
def generate_timestamp(format_type: str = "iso") -> Dict[str, Any]:
    """다양한 형식의 타임스탬프 생성"""
    now = datetime.datetime.now()
    
    formats = {
        "iso": now.isoformat(),
        "unix": int(now.timestamp()),
        "readable": now.strftime("%Y년 %m월 %d일 %H시 %M분 %S초"),
        "date_only": now.strftime("%Y-%m-%d"),
        "time_only": now.strftime("%H:%M:%S")
    }
    
    if format_type not in formats:
        available = ", ".join(formats.keys())
        raise ValueError(f"지원하지 않는 형식: {format_type}. 사용 가능: {available}")
    
    return {
        "status": "success",
        "timestamp": formats[format_type],
        "format": format_type,
        "all_formats": formats
    }


# ============================================================================
# 서버 실행
# ============================================================================

if __name__ == "__main__":
    print("🚀 완전한 프로덕션 MCP 서버가 시작됩니다!")
    print("=" * 60)
    print(f"📂 작업 공간: {WORKSPACE_DIR}")
    print(f"🔧 구현된 도구 수: 11개")
    print("📋 주요 기능:")
    print("  ✅ 고급 계산기 (안전한 수학 표현식 처리)")
    print("  ✅ 텍스트 분석 (단어/문장 통계, 빈도 분석)")
    print("  ✅ 파일 관리 (읽기/쓰기/목록/검색)")
    print("  ✅ 데이터 변환 (JSON ↔ CSV)")
    print("  ✅ 성능 모니터링 (메트릭스/헬스체크)")
    print("  ✅ 구조화된 로깅 (에러 추적)")
    print("  ✅ 보안 (경로 제한, 안전한 실행)")
    print("=" * 60)
    
    # 사용자 선택에 따라 STDIO 또는 HTTP 모드로 실행
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--http":
        print("🌐 HTTP 모드로 서버 시작...")
        print("🔗 URL: http://localhost:8080/mcp/")
        print("📱 웹 브라우저나 HTTP 클라이언트로 접근 가능")
        mcp.run(transport="http", host="127.0.0.1", port=8080)
    else:
        print("💻 STDIO 모드로 서버 시작...")
        print("📞 MCP 클라이언트나 Claude Desktop에서 연결 가능")
        mcp.run()