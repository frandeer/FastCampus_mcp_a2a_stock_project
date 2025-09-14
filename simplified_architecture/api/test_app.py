#!/usr/bin/env python3
"""
Simple test script for the FastAPI application.

This script demonstrates:
- Application startup and basic functionality
- Dependency injection working correctly
- API endpoints responding properly
"""

import asyncio
import json
from typing import Dict, Any

import httpx
from fastapi.testclient import TestClient

from main import create_app


async def test_dependency_injection():
    """Test that dependency injection is working correctly."""
    print("🧪 Testing Dependency Injection...")
    
    app = create_app()
    
    # Test that we can create the app and access dependencies
    async with app.router.lifespan_context(app):
        container = app.state.container
        
        # Test service retrieval
        analysis_service = container.get_stock_analysis_service()
        investment_service = container.get_investment_service()
        portfolio_service = container.get_portfolio_service()
        
        # Test service functionality
        analysis_result = await analysis_service.analyze_stock("AAPL")
        print(f"✅ Stock analysis service working: {analysis_result['stock_code']}")
        
        investment_result = await investment_service.execute_investment("AAPL", 1000.0, "market")
        print(f"✅ Investment service working: {investment_result['transaction_id']}")
        
        portfolio_result = await portfolio_service.get_portfolio_summary("user123")
        print(f"✅ Portfolio service working: {portfolio_result['position_count']} positions")
        
    print("✅ Dependency injection test passed!\n")


def test_api_endpoints():
    """Test API endpoints using TestClient."""
    print("🌐 Testing API Endpoints...")
    
    app = create_app()
    client = TestClient(app)
    
    # Test health check
    response = client.get("/health")
    print(f"Health check: {response.status_code} - {response.json()['status']}")
    assert response.status_code == 200
    
    # Test API health check
    response = client.get("/api/v1/health")
    print(f"API health check: {response.status_code} - {response.json()['status']}")
    assert response.status_code == 200
    
    # Test stock analysis
    response = client.post(
        "/api/v1/analyze/AAPL",
        json={
            "include_detailed_metrics": True,
            "analysis_period": "30d"
        }
    )
    print(f"Stock analysis: {response.status_code}")
    assert response.status_code == 200
    data = response.json()
    print(f"  → Stock: {data['stock_code']}, Price: ${data['price']}, Recommendation: {data['recommendation']}")
    
    # Test investment
    response = client.post(
        "/api/v1/invest",
        json={
            "stock_code": "AAPL",
            "amount": 1000.0,
            "strategy": "market"
        }
    )
    print(f"Investment execution: {response.status_code}")
    assert response.status_code == 201
    data = response.json()
    print(f"  → Transaction: {data['transaction_id']}, Shares: {data['shares_purchased']}")
    
    # Test portfolio
    response = client.get("/api/v1/portfolio?user_id=user123")
    print(f"Portfolio summary: {response.status_code}")
    assert response.status_code == 200
    data = response.json()
    print(f"  → Total Value: ${data['total_value']}, Positions: {data['position_count']}")
    
    print("✅ API endpoints test passed!\n")


def test_error_handling():
    """Test error handling and validation."""
    print("⚠️  Testing Error Handling...")
    
    app = create_app()
    client = TestClient(app)
    
    # Test invalid stock code
    response = client.post("/api/v1/analyze/123INVALID")
    print(f"Invalid stock code: {response.status_code}")
    assert response.status_code == 400
    
    # Test invalid investment amount
    response = client.post(
        "/api/v1/invest",
        json={
            "stock_code": "AAPL",
            "amount": -100.0,  # Invalid negative amount
            "strategy": "market"
        }
    )
    print(f"Invalid investment amount: {response.status_code}")
    assert response.status_code == 422  # Validation error
    
    # Test empty user ID
    response = client.get("/api/v1/portfolio?user_id=")
    print(f"Empty user ID: {response.status_code}")
    assert response.status_code == 400
    
    print("✅ Error handling test passed!\n")


def print_openapi_info():
    """Print OpenAPI schema information."""
    print("📖 OpenAPI Documentation Info...")
    
    app = create_app()
    client = TestClient(app)
    
    # Get OpenAPI schema
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    
    print(f"API Title: {schema['info']['title']}")
    print(f"API Version: {schema['info']['version']}")
    print(f"API Description: {schema['info']['description']}")
    print("\nAvailable endpoints:")
    for path, methods in schema['paths'].items():
        for method, details in methods.items():
            if method != 'parameters':
                print(f"  {method.upper()} {path} - {details.get('summary', 'No summary')}")
    
    print(f"\n📚 Interactive docs available at:")
    print(f"  • Swagger UI: http://127.0.0.1:8000/docs")
    print(f"  • ReDoc: http://127.0.0.1:8000/redoc")
    print()


async def main():
    """Run all tests."""
    print("🚀 Starting FastAPI Simplified Clean Architecture Tests\n")
    
    try:
        # Test dependency injection
        await test_dependency_injection()
        
        # Test API endpoints
        test_api_endpoints()
        
        # Test error handling
        test_error_handling()
        
        # Show OpenAPI info
        print_openapi_info()
        
        print("🎉 All tests passed! The FastAPI application is working correctly.")
        print("\n💡 To start the server, run:")
        print("   python main.py")
        print("   or")
        print("   uvicorn main:app --reload")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())