"""
Step 2: HTTP MCP 서버
웹 브라우저에서 접근 가능한 MCP 서버 (포트 8000)
"""

from fastmcp import FastMCP
import json
import datetime
from typing import Dict, Any, List
import random

# MCP 서버 인스턴스 생성
mcp = FastMCP(name="HttpDemoServer", version="2.0.0")


@mcp.tool
def hello_web(name: str, language: str = "ko") -> Dict[str, Any]:
    """웹에서 접근 가능한 다국어 인사 기능"""
    greetings = {
        "ko": f"안녕하세요, {name}님! 웹에서 MCP 서버에 접속하셨네요! 🌐",
        "en": f"Hello, {name}! Welcome to the MCP server via web! 🌐",
        "ja": f"こんにちは、{name}さん！ウェブからMCPサーバーへようこそ！🌐",
        "zh": f"你好，{name}！欢迎通过网络访问MCP服务器！🌐"
    }
    
    return {
        "status": "success",
        "greeting": greetings.get(language, greetings["ko"]),
        "language": language,
        "timestamp": datetime.datetime.now().isoformat(),
        "server_info": "FastMCP HTTP Server"
    }


@mcp.tool
def get_server_status() -> Dict[str, Any]:
    """서버 상태 정보를 반환합니다"""
    return {
        "status": "online",
        "server_name": "HttpDemoServer",
        "version": "2.0.0",
        "uptime": "Running",
        "current_time": datetime.datetime.now().isoformat(),
        "transport": "HTTP",
        "port": 8000,
        "features": [
            "Multi-language support",
            "Real-time status",
            "Data generation",
            "Web accessible"
        ]
    }


@mcp.tool
def generate_sample_data(data_type: str, count: int = 5) -> Dict[str, Any]:
    """샘플 데이터를 생성합니다"""
    try:
        if count > 100:
            return {"status": "error", "message": "최대 100개까지만 생성 가능합니다"}
        
        if data_type == "users":
            names = ["김철수", "이영희", "박민수", "최지영", "정다훈", "한소영", "임대현", "송미래"]
            domains = ["gmail.com", "naver.com", "kakao.com", "yahoo.com"]
            
            data = []
            for i in range(count):
                name = random.choice(names)
                data.append({
                    "id": i + 1,
                    "name": name,
                    "email": f"{name.replace(' ', '').lower()}{i+1}@{random.choice(domains)}",
                    "age": random.randint(20, 65),
                    "created_at": datetime.datetime.now().isoformat()
                })
                
        elif data_type == "products":
            categories = ["전자제품", "의류", "도서", "가구", "스포츠"]
            
            data = []
            for i in range(count):
                category = random.choice(categories)
                data.append({
                    "id": i + 1,
                    "name": f"{category} 상품 {i+1}",
                    "category": category,
                    "price": random.randint(10000, 500000),
                    "stock": random.randint(0, 100),
                    "created_at": datetime.datetime.now().isoformat()
                })
                
        elif data_type == "transactions":
            data = []
            for i in range(count):
                data.append({
                    "id": i + 1,
                    "amount": random.randint(1000, 100000),
                    "type": random.choice(["수입", "지출"]),
                    "description": f"거래 내역 {i+1}",
                    "date": datetime.datetime.now().isoformat()
                })
                
        else:
            return {"status": "error", "message": f"지원하지 않는 데이터 타입: {data_type}"}
        
        return {
            "status": "success",
            "data_type": data_type,
            "count": len(data),
            "data": data,
            "generated_at": datetime.datetime.now().isoformat()
        }
        
    except Exception as e:
        return {"status": "error", "message": str(e)}


@mcp.tool
def format_json(data: str, indent: int = 2) -> Dict[str, Any]:
    """JSON 문자열을 포맷팅합니다"""
    try:
        parsed = json.loads(data)
        formatted = json.dumps(parsed, indent=indent, ensure_ascii=False)
        
        return {
            "status": "success",
            "original": data,
            "formatted": formatted,
            "size_reduction": len(data) - len(formatted)
        }
        
    except json.JSONDecodeError as e:
        return {"status": "error", "message": f"잘못된 JSON 형식: {str(e)}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@mcp.tool
def get_random_quote() -> Dict[str, Any]:
    """랜덤한 명언을 반환합니다"""
    quotes = [
        {
            "text": "성공은 준비된 자에게 기회가 주어질 때 만들어진다.",
            "author": "세네카",
            "category": "성공"
        },
        {
            "text": "배움에 있어서 나이는 장애가 되지 않는다.",
            "author": "공자",
            "category": "학습"
        },
        {
            "text": "작은 발걸음도 계속 걸으면 천 리를 간다.",
            "author": "노자",
            "category": "인내"
        },
        {
            "text": "실패는 성공의 어머니이다.",
            "author": "토마스 에디슨",
            "category": "실패"
        },
        {
            "text": "미래를 예측하는 가장 좋은 방법은 그것을 창조하는 것이다.",
            "author": "피터 드러커",
            "category": "미래"
        }
    ]
    
    quote = random.choice(quotes)
    
    return {
        "status": "success",
        "quote": quote,
        "requested_at": datetime.datetime.now().isoformat()
    }


@mcp.tool
def calculate_stats(numbers: List[float]) -> Dict[str, Any]:
    """숫자 리스트의 통계를 계산합니다"""
    try:
        if not numbers:
            return {"status": "error", "message": "빈 리스트입니다"}
        
        total = sum(numbers)
        count = len(numbers)
        mean = total / count
        sorted_nums = sorted(numbers)
        
        # 중앙값
        mid = count // 2
        if count % 2 == 0:
            median = (sorted_nums[mid-1] + sorted_nums[mid]) / 2
        else:
            median = sorted_nums[mid]
        
        # 분산과 표준편차
        variance = sum((x - mean) ** 2 for x in numbers) / count
        std_dev = variance ** 0.5
        
        return {
            "status": "success",
            "input": numbers,
            "statistics": {
                "count": count,
                "sum": total,
                "mean": round(mean, 2),
                "median": median,
                "min": min(numbers),
                "max": max(numbers),
                "range": max(numbers) - min(numbers),
                "variance": round(variance, 2),
                "standard_deviation": round(std_dev, 2)
            },
            "calculated_at": datetime.datetime.now().isoformat()
        }
        
    except Exception as e:
        return {"status": "error", "message": str(e)}


if __name__ == "__main__":
    print("🌐 HTTP MCP 서버가 시작됩니다...")
    print("🔗 URL: http://localhost:8000/mcp/")
    print("📱 웹 브라우저나 HTTP 클라이언트로 접근 가능합니다")
    print("사용 가능한 도구: hello_web, get_server_status, generate_sample_data,")
    print("               format_json, get_random_quote, calculate_stats")
    print("\n🎯 테스트 방법:")
    print("1. 웹 브라우저에서 http://localhost:8000/mcp/ 접속")
    print("2. MCP 클라이언트로 HTTP 연결")
    print("3. API 형태로 도구 호출")
    
    # HTTP 모드로 서버 실행
    mcp.run(transport="http", host="127.0.0.1", port=8000)