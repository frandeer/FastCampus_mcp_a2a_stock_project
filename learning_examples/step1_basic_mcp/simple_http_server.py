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
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

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
    
    # TODO(human): 여기에 덧셈과 곱셈 함수를 구현해주세요
    def _handle_add(self, params):
        """덧셈 처리 - GET 방식"""
        # params는 딕셔너리이고, 각 값은 리스트입니다
        # 예: {'a': ['10'], 'b': ['5']}
        pass
    
    def _handle_multiply(self, params):
        """곱셈 처리 - GET 방식"""
        pass
    
    def _handle_add_post(self, data):
        """덧셈 처리 - POST 방식"""
        pass
    
    def _handle_multiply_post(self, data):
        """곱셈 처리 - POST 방식"""
        pass
    
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

def run_server(port=9001):
    """HTTP 서버 실행"""
    print("🧮 Simple Calculator HTTP 서버 시작...")
    print(f"📍 포트: {port}")
    print(f"🌐 URL: http://localhost:{port}")
    print("🔧 사용 가능한 엔드포인트:")
    print("  - GET  /      : 서버 정보 및 도구 목록")
    print("  - GET  /add   : 덧셈 (예: /add?a=10&b=5)")
    print("  - GET  /multiply : 곱셈 (예: /multiply?a=7&b=8)")
    print("  - GET  /info  : 서버 상태 정보")
    print("  - POST /add   : 덧셈 (JSON body)")
    print("  - POST /multiply : 곱셈 (JSON body)")
    print("-" * 50)
    print("💡 테스트 방법:")
    print(f"   curl 'http://localhost:{port}/add?a=10&b=5'")
    print(f"   curl -X POST http://localhost:{port}/add -d '{{\"a\":10,\"b\":5}}' -H 'Content-Type: application/json'")
    print("-" * 50)
    
    server = HTTPServer(('localhost', port), CalculatorHandler)
    server.request_count = 0
    
    try:
        print("✅ 서버 실행 중... (Ctrl+C로 종료)")
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 서버 종료 중...")
        server.shutdown()
        print("👋 서버가 종료되었습니다")

if __name__ == "__main__":
    run_server()