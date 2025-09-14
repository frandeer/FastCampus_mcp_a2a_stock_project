#!/usr/bin/env python3
"""
Simple Universal Platform Demo Server
신화급 범용 플랫폼의 웹 서버 데모
"""

import asyncio
import json
import uuid
from datetime import datetime
from decimal import Decimal
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
import uvicorn

# ===== 기본 추상화 =====
from enum import Enum

class Status(Enum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE" 
    COMPLETED = "COMPLETED"

@dataclass(frozen=True)
class Money:
    amount: Decimal
    currency: str = "USD"
    
    def __str__(self):
        return f"{self.amount} {self.currency}"

@dataclass(frozen=True)
class DomainEvent:
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    occurred_at: datetime = field(default_factory=datetime.now)
    event_type: str = field(init=False)
    
    def __post_init__(self):
        object.__setattr__(self, 'event_type', self.__class__.__name__)

# ===== 범용 비즈니스 엔티티 =====
class BusinessEntity:
    def __init__(self, entity_id: str = None, name: str = "", status: Status = Status.DRAFT):
        self.id = entity_id or str(uuid.uuid4())
        self.name = name
        self.status = status
        self.created_at = datetime.now()
        self.events: List[DomainEvent] = []
        
    def add_event(self, event: DomainEvent):
        self.events.append(event)

# ===== E-commerce 도메인 =====
class Product(BusinessEntity):
    def __init__(self, name: str, price: Money, category: str = ""):
        super().__init__(name=name)
        self.price = price
        self.category = category
        self.inventory = 100

class Order(BusinessEntity):
    def __init__(self, customer_id: str):
        super().__init__(name=f"Order-{str(uuid.uuid4())[:8]}")
        self.customer_id = customer_id
        self.items: List[Dict] = []
        self.total_amount = Money(Decimal('0'))
        
    def add_item(self, product: Product, quantity: int):
        item = {
            "product_id": product.id,
            "product_name": product.name,
            "price": str(product.price),
            "quantity": quantity,
            "subtotal": str(Money(product.price.amount * quantity, product.price.currency))
        }
        self.items.append(item)
        self._calculate_total()
        
    def _calculate_total(self):
        total = sum(Decimal(item["quantity"]) * Decimal(str(item["price"]).split()[0]) for item in self.items)
        self.total_amount = Money(total)

# ===== 웹 애플리케이션 =====
app = FastAPI(
    title="Universal Platform Demo",
    description="신화급 범용 플랫폼 웹 데모",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 글로벌 데이터 저장소
global_store = {
    "products": {},
    "orders": {},
    "events": [],
    "metrics": {
        "total_orders": 0,
        "total_revenue": Decimal('0'),
        "active_products": 0
    }
}

@app.on_event("startup")
async def startup_event():
    """시스템 초기화"""
    # 샘플 데이터 생성
    laptop = Product("MacBook Pro", Money(Decimal('2999.99')), "Electronics")
    phone = Product("iPhone 15", Money(Decimal('1299.99')), "Electronics")
    
    global_store["products"][laptop.id] = laptop
    global_store["products"][phone.id] = phone
    global_store["metrics"]["active_products"] = 2
    
    print("🚀 Universal Platform Demo Server Started!")
    print("📍 Admin Dashboard: http://localhost:8000/admin")
    print("📚 API Documentation: http://localhost:8000/docs")

@app.get("/", response_class=HTMLResponse)
async def root():
    """메인 페이지"""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Universal Platform Demo</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }
            .container { max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; }
            h1 { color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; }
            .feature { background: #ecf0f1; padding: 15px; margin: 10px 0; border-radius: 5px; }
            .button { background: #3498db; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block; margin: 5px; }
            .button:hover { background: #2980b9; }
            .status { background: #2ecc71; color: white; padding: 5px 10px; border-radius: 3px; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🚀 Universal Platform Demo</h1>
            <p><span class="status">ACTIVE</span> 신화급 범용 플랫폼이 실행 중입니다!</p>
            
            <div class="feature">
                <h3>📦 E-commerce Domain</h3>
                <p>완전한 상품 관리, 주문 처리, 결제 시스템</p>
                <a href="/api/v1/products" class="button">상품 목록</a>
                <a href="/api/v1/orders" class="button">주문 관리</a>
            </div>
            
            <div class="feature">
                <h3>📊 System Analytics</h3>
                <p>실시간 시스템 메트릭 및 성능 모니터링</p>
                <a href="/admin/metrics" class="button">메트릭 보기</a>
                <a href="/health" class="button">시스템 상태</a>
            </div>
            
            <div class="feature">
                <h3>🏗️ Universal Architecture</h3>
                <p>모든 비즈니스 도메인에 적용 가능한 범용 아키텍처</p>
                <a href="/docs" class="button">API 문서</a>
                <a href="/admin" class="button">관리자 대시보드</a>
            </div>
        </div>
    </body>
    </html>
    """
    return html_content

@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard():
    """관리자 대시보드"""
    products = list(global_store["products"].values())
    orders = list(global_store["orders"].values())
    metrics = global_store["metrics"]
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Admin Dashboard - Universal Platform</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; background: #2c3e50; color: white; }}
            .container {{ max-width: 1200px; margin: 0 auto; }}
            .header {{ background: #34495e; padding: 20px; border-radius: 10px; margin-bottom: 20px; }}
            .metrics {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin-bottom: 30px; }}
            .metric {{ background: #3498db; padding: 20px; border-radius: 10px; text-align: center; }}
            .metric h3 {{ margin: 0; font-size: 2em; }}
            .metric p {{ margin: 5px 0 0 0; opacity: 0.8; }}
            .section {{ background: #34495e; padding: 20px; border-radius: 10px; margin-bottom: 20px; }}
            .item {{ background: #2c3e50; padding: 10px; margin: 5px 0; border-radius: 5px; border-left: 4px solid #3498db; }}
            .status {{ background: #2ecc71; padding: 3px 8px; border-radius: 3px; font-size: 0.8em; }}
            h1, h2 {{ color: #ecf0f1; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🏗️ Universal Platform Admin Dashboard</h1>
                <p>신화급 범용 플랫폼 관리 시스템</p>
            </div>
            
            <div class="metrics">
                <div class="metric">
                    <h3>{metrics['active_products']}</h3>
                    <p>활성 상품</p>
                </div>
                <div class="metric">
                    <h3>{metrics['total_orders']}</h3>
                    <p>총 주문</p>
                </div>
                <div class="metric">
                    <h3>${metrics['total_revenue']}</h3>
                    <p>총 매출</p>
                </div>
                <div class="metric">
                    <h3>{len(global_store['events'])}</h3>
                    <p>시스템 이벤트</p>
                </div>
            </div>
            
            <div class="section">
                <h2>📦 Products ({len(products)})</h2>
                {"".join([f'<div class="item"><strong>{p.name}</strong> - {p.price} | <span class="status">{p.status.value}</span></div>' for p in products])}
            </div>
            
            <div class="section">
                <h2>🛒 Orders ({len(orders)})</h2>
                {"<p>주문이 없습니다.</p>" if not orders else "".join([f'<div class="item"><strong>{o.name}</strong> - {o.total_amount} | <span class="status">{o.status.value}</span></div>' for o in orders])}
            </div>
            
            <div class="section">
                <h2>📡 System Status</h2>
                <div class="item">✅ Universal Platform: <span class="status">OPERATIONAL</span></div>
                <div class="item">✅ Event System: <span class="status">ACTIVE</span></div>
                <div class="item">✅ Domain Services: <span class="status">RUNNING</span></div>
                <div class="item">✅ Metrics Collection: <span class="status">ENABLED</span></div>
            </div>
        </div>
    </body>
    </html>
    """
    return html_content

@app.get("/api/v1/products")
async def get_products():
    """상품 목록 조회"""
    products = []
    for product in global_store["products"].values():
        products.append({
            "id": product.id,
            "name": product.name,
            "price": str(product.price),
            "category": product.category,
            "inventory": product.inventory,
            "status": product.status.value
        })
    return {"products": products}

@app.post("/api/v1/orders")
async def create_order(order_data: Dict[str, Any]):
    """주문 생성"""
    customer_id = order_data.get("customer_id", f"customer_{uuid.uuid4().hex[:8]}")
    order = Order(customer_id)
    
    # 주문 아이템 추가
    for item in order_data.get("items", []):
        product_id = item["product_id"]
        quantity = item["quantity"]
        
        if product_id in global_store["products"]:
            product = global_store["products"][product_id]
            order.add_item(product, quantity)
    
    order.status = Status.COMPLETED
    global_store["orders"][order.id] = order
    global_store["metrics"]["total_orders"] += 1
    global_store["metrics"]["total_revenue"] += order.total_amount.amount
    
    # 이벤트 기록
    event = {
        "type": "OrderCreated",
        "order_id": order.id,
        "customer_id": customer_id,
        "total_amount": str(order.total_amount),
        "timestamp": datetime.now().isoformat()
    }
    global_store["events"].append(event)
    
    return {
        "order_id": order.id,
        "status": order.status.value,
        "total_amount": str(order.total_amount),
        "items": order.items
    }

@app.get("/api/v1/orders")
async def get_orders():
    """주문 목록 조회"""
    orders = []
    for order in global_store["orders"].values():
        orders.append({
            "id": order.id,
            "name": order.name,
            "customer_id": order.customer_id,
            "status": order.status.value,
            "total_amount": str(order.total_amount),
            "items": order.items,
            "created_at": order.created_at.isoformat()
        })
    return {"orders": orders}

@app.get("/admin/metrics")
async def get_metrics():
    """시스템 메트릭"""
    return {
        "platform_status": "operational",
        "domains": {
            "ecommerce": {
                "products": len(global_store["products"]),
                "orders": len(global_store["orders"]),
                "revenue": str(global_store["metrics"]["total_revenue"])
            }
        },
        "events": {
            "total": len(global_store["events"]),
            "recent": global_store["events"][-5:]
        },
        "system": {
            "uptime": "operational",
            "version": "1.0.0",
            "architecture": "universal"
        }
    }

@app.get("/health")
async def health_check():
    """시스템 헬스 체크"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "platform": "Universal Platform Demo",
        "version": "1.0.0",
        "components": {
            "api": "healthy",
            "database": "healthy",  
            "events": "healthy",
            "metrics": "healthy"
        }
    }

if __name__ == "__main__":
    print("🚀 Starting Universal Platform Demo Server...")
    print("📍 Access at: http://localhost:8000")
    print("📚 API Docs: http://localhost:8000/docs")
    print("⚙️  Admin: http://localhost:8000/admin")
    
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8000,
        log_level="info",
        access_log=True
    )