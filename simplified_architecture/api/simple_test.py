#!/usr/bin/env python3
"""
Simple verification script for the FastAPI application.
"""

import asyncio
from main import create_app
from dependencies import DependencyContainer


async def test_services():
    """Test that services work correctly."""
    print("🧪 Testing Services...")
    
    container = DependencyContainer()
    await container.startup()
    
    try:
        # Test stock analysis
        analysis_service = container.get_stock_analysis_service()
        result = await analysis_service.analyze_stock("AAPL")
        print(f"✅ Stock Analysis: {result['stock_code']} - {result['recommendation']}")
        
        # Test investment
        investment_service = container.get_investment_service()
        result = await investment_service.execute_investment("AAPL", 1000.0, "market")
        print(f"✅ Investment: {result['transaction_id']} - {result['shares_purchased']} shares")
        
        # Test portfolio
        portfolio_service = container.get_portfolio_service()
        result = await portfolio_service.get_portfolio_summary("user123")
        print(f"✅ Portfolio: ${result['total_value']:.2f} total value, {result['position_count']} positions")
        
    finally:
        await container.shutdown()


def test_app_creation():
    """Test that the FastAPI app can be created."""
    print("\n🏗️  Testing App Creation...")
    
    app = create_app()
    print(f"✅ App created: {app.title}")
    print(f"✅ Version: {app.version}")
    print(f"✅ Docs URL: {app.docs_url}")
    print(f"✅ Routes: {len(app.routes)} endpoints")


async def main():
    """Run tests."""
    print("🚀 FastAPI Simplified Clean Architecture - Quick Test\n")
    
    # Test services
    await test_services()
    
    # Test app creation
    test_app_creation()
    
    print("\n🎉 All tests passed!")
    print("\n💡 To start the server:")
    print("   cd simplified_architecture/api")
    print("   python3 main.py")
    print("\n📚 Then visit:")
    print("   • http://127.0.0.1:8000/docs (Swagger UI)")
    print("   • http://127.0.0.1:8000/redoc (ReDoc)")


if __name__ == "__main__":
    asyncio.run(main())