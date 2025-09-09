"""
Step 1: 간단한 HTTP API 서버 - MCP 개념 이해용
MCP의 기본 아이디어를 이해하기 위한 간단한 HTTP 서버

이 예제는:
1. HTTP API로 도구 기능 제공
2. JSON 응답으로 구조화된 결과 반환
3. 여러 개의 '도구'를 하나의 서버에서 제공

실제 MCP는 더 복잡한 프로토콜을 사용하지만, 
기본 아이디어는 "AI가 호출할 수 있는 도구들을 API로 제공하는 것"입니다.
"""

import json
import sys
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# 공통 유틸리티 import
sys.path.append(str(Path(__file__).parent.parent))
from common_utils import get_setting, print_environment_status

class CalculatorHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        """GET 요청 처리"""
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        params = parse_qs(parsed_path.query)
        
        # CORS 헤더 설정
        self.send_header('Access-Control-Allow-Origin', '*')
        
        if path == '/add':
            self._handle_add(params)
        elif path == '/multiply':
            self._handle_multiply(params)
        elif path == '/info':
            self._handle_info(params)
        elif path == '/':
            self._handle_root()
        else:
            self._send_error(404, "엔드포인트를 찾을 수 없습니다")
    
    def do_POST(self):
        """POST 요청 처리"""
        content_length = int(self.headers.get('Content-Length', 0))
        if content_length > 0:
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data.decode('utf-8'))
            except:
                data = {}
        else:
            data = {}
        
        path = self.path
        
        # CORS 헤더 설정
        self.send_header('Access-Control-Allow-Origin', '*')
        
        if path == '/add':
            self._handle_add_post(data)
        elif path == '/multiply':
            self._handle_multiply_post(data)
        else:
            self._send_error(404, "엔드포인트를 찾을 수 없습니다")
    
    def _handle_root(self):
        """루트 엔드포인트 - 사용 가능한 도구 목록"""
        response = {
            "name": "Simple Calculator HTTP Server",
            "version": "1.0.0",
            "description": "MCP 개념 학습용 간단한 계산기 서버",
            "available_tools": [
                {
                    "name": "add",
                    "description": "두 숫자 더하기",
                    "method": "GET/POST",
                    "parameters": ["a", "b"],
                    "example": "/add?a=10&b=5"
                },
                {
                    "name": "multiply", 
                    "description": "두 숫자 곱하기",
                    "method": "GET/POST",
                    "parameters": ["a", "b"],
                    "example": "/multiply?a=7&b=8"
                },
                {
                    "name": "info",
                    "description": "서버 정보 조회",
                    "method": "GET",
                    "parameters": [],
                    "example": "/info"
                }
            ]
        }
        self._send_json_response(response)
    
    def _handle_info(self, params):
        """서버 정보 조회"""
        response = {
            "server_name": "Simple Calculator",
            "version": "1.0.0",
            "status": "running",
            "total_requests": getattr(self.server, 'request_count', 0),
            "available_operations": 3,
            "description": "MCP 개념을 이해하기 위한 학습용 계산기 서버입니다"
        }
        self._send_json_response(response)
    
    def _handle_add(self, params):
        """덧셈 처리 - GET 방식"""
        try:
            # params는 딕셔너리이고, 각 값은 리스트입니다
            # 예: {'a': ['10'], 'b': ['5']}
            a = float(params.get('a', [0])[0])
            b = float(params.get('b', [0])[0])
            
            result = a + b
            response = {
                "operation": "addition",
                "method": "GET",
                "inputs": {"a": a, "b": b},
                "result": result,
                "message": f"{a} + {b} = {result}"
            }
            self._send_json_response(response)
            
        except (ValueError, IndexError, TypeError) as e:
            self._send_error(400, f"잘못된 파라미터: {str(e)}")
    
    def _handle_multiply(self, params):
        """곱셈 처리 - GET 방식"""
        try:
            a = float(params.get('a', [0])[0])
            b = float(params.get('b', [0])[0])
            
            result = a * b
            response = {
                "operation": "multiplication",
                "method": "GET", 
                "inputs": {"a": a, "b": b},
                "result": result,
                "message": f"{a} × {b} = {result}"
            }
            self._send_json_response(response)
            
        except (ValueError, IndexError, TypeError) as e:
            self._send_error(400, f"잘못된 파라미터: {str(e)}")
    
    def _handle_add_post(self, data):
        """덧셈 처리 - POST 방식"""
        try:
            a = float(data.get('a', 0))
            b = float(data.get('b', 0))
            
            result = a + b
            response = {
                "operation": "addition",
                "method": "POST",
                "inputs": {"a": a, "b": b},
                "result": result,
                "message": f"{a} + {b} = {result}"
            }
            self._send_json_response(response)
            
        except (ValueError, TypeError) as e:
            self._send_error(400, f"잘못된 JSON 데이터: {str(e)}")
    
    def _handle_multiply_post(self, data):
        """곱셈 처리 - POST 방식"""
        try:
            a = float(data.get('a', 0))
            b = float(data.get('b', 0))
            
            result = a * b
            response = {
                "operation": "multiplication", 
                "method": "POST",
                "inputs": {"a": a, "b": b},
                "result": result,
                "message": f"{a} × {b} = {result}"
            }
            self._send_json_response(response)
            
        except (ValueError, TypeError) as e:
            self._send_error(400, f"잘못된 JSON 데이터: {str(e)}")
    
    def _send_json_response(self, data, status_code=200):
        """JSON 응답 전송"""
        self.send_response(status_code)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        
        json_string = json.dumps(data, ensure_ascii=False, indent=2)
        self.wfile.write(json_string.encode('utf-8'))
    
    def _send_error(self, status_code, message):
        """에러 응답 전송"""
        error_response = {
            "error": True,
            "status_code": status_code,
            "message": message
        }
        self._send_json_response(error_response, status_code)
    
    def log_message(self, format, *args):
        """로그 메시지 출력"""
        print(f"📝 {self.client_address[0]} - {format % args}")

def run_server():
    """HTTP 서버 실행 (.env 설정 사용)"""
    
    # 환경 설정 출력
    print("🌐 Simple HTTP API 서버 시작...")
    print("=" * 50)
    print_environment_status()
    
    # 설정값 가져오기
    host = get_setting('LEARNING_HOST', 'localhost', str)
    port = get_setting('LEARNING_HTTP_PORT', 9001, int)
    
    print(f"\n🚀 HTTP 서버 시작 중...")
    print(f"📍 호스트: {host}")
    print(f"📍 포트: {port}")
    print("🔧 사용 가능한 API:")
    print("  - GET  /add?a=10&b=5      : 덧셈")
    print("  - GET  /multiply?a=7&b=8  : 곱셈")
    print("  - POST /add {a:10, b:5}  : 덧셈 (JSON)")
    print("  - GET  /info             : 서버 정보")
    print(f"🌐 서버 URL: http://{host}:{port}")
    print("-" * 50)
    
    # 서버 실행
    try:
        server_address = (host, port)
        httpd = HTTPServer(server_address, CalculatorHandler)
        print(f"✅ HTTP 서버가 {host}:{port}에서 실행 중...")
        print("⏹️  중단하려면 Ctrl+C를 누르세요")
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 서버 중단 중...")
        httpd.server_close()
        print("✅ 서버가 안전하게 종료되었습니다")
    except Exception as e:
        print(f"❌ 서버 실행 오류: {e}")

if __name__ == "__main__":
    run_server()