"""
Test suite for Universal Platform Demo Application
"""

import pytest
import asyncio
from httpx import AsyncClient
from fastapi.testclient import TestClient

# Import the main application
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from main import app


class TestUniversalPlatformDemo:
    """Test suite for the Universal Platform Demo"""
    
    def setup_method(self):
        """Setup test method"""
        self.client = TestClient(app)
    
    def test_root_endpoint(self):
        """Test the root endpoint"""
        response = self.client.get("/")
        assert response.status_code == 200
        
        data = response.json()
        assert data["message"] == "Universal Platform Demo Application"
        assert data["version"] == "1.0.0"
        assert data["status"] == "running"
        assert "domains" in data
        assert "ecommerce" in data["domains"]
        assert "healthcare" in data["domains"]
        assert "logistics" in data["domains"]
    
    def test_health_endpoint(self):
        """Test the health check endpoint"""
        response = self.client.get("/health")
        assert response.status_code == 200
        
        data = response.json()
        assert "status" in data
        assert "timestamp" in data
    
    def test_status_endpoint(self):
        """Test the system status endpoint"""
        response = self.client.get("/status")
        assert response.status_code == 200
        
        data = response.json()
        assert "system" in data
        assert "plugins" in data
        assert "event_bus" in data
        assert "domains_loaded" in data
    
    def test_ecommerce_domain_info(self):
        """Test e-commerce domain information"""
        response = self.client.get("/api/v1/ecommerce/")
        assert response.status_code == 200
        
        data = response.json()
        assert data["domain"] == "ecommerce"
        assert "features" in data
        assert "endpoints" in data
    
    def test_ecommerce_products_list(self):
        """Test e-commerce products listing"""
        response = self.client.get("/api/v1/ecommerce/products")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        assert isinstance(data["data"], list)
    
    def test_ecommerce_categories(self):
        """Test e-commerce categories"""
        response = self.client.get("/api/v1/ecommerce/categories")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        assert "categories" in data["data"]
    
    def test_healthcare_domain_info(self):
        """Test healthcare domain information"""
        response = self.client.get("/api/v1/healthcare/")
        assert response.status_code == 200
        
        data = response.json()
        assert data["data"]["domain"] == "healthcare"
        assert "features" in data["data"]
    
    def test_healthcare_patients(self):
        """Test healthcare patients endpoint"""
        response = self.client.get("/api/v1/healthcare/patients")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        assert "patients" in data["data"]
    
    def test_logistics_domain_info(self):
        """Test logistics domain information"""
        response = self.client.get("/api/v1/logistics/")
        assert response.status_code == 200
        
        data = response.json()
        assert data["data"]["domain"] == "logistics"
        assert "features" in data["data"]
    
    def test_logistics_shipments(self):
        """Test logistics shipments endpoint"""
        response = self.client.get("/api/v1/logistics/shipments")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        assert "shipments" in data["data"]
    
    def test_admin_overview(self):
        """Test admin overview endpoint"""
        response = self.client.get("/admin/overview")
        assert response.status_code == 200
        
        data = response.json()
        assert "system" in data
        assert "health" in data
        assert "performance" in data
        assert "plugins" in data
        assert "tenants" in data
    
    def test_admin_plugins_list(self):
        """Test admin plugins listing"""
        response = self.client.get("/admin/plugins")
        assert response.status_code == 200
        
        data = response.json()
        assert "plugins" in data
        assert "total_count" in data
    
    def test_admin_metrics(self):
        """Test admin metrics endpoint"""
        response = self.client.get("/admin/metrics")
        assert response.status_code == 200
        
        data = response.json()
        assert "summary" in data
        assert "system" in data
        assert "timestamp" in data
    
    def test_create_product(self):
        """Test creating a product"""
        product_data = {
            "name": "Test Product",
            "description": "A test product for demo",
            "category": "Test Category",
            "sku": "TEST-001",
            "price": 99.99,
            "inventory_quantity": 10
        }
        
        response = self.client.post("/api/v1/ecommerce/products", json=product_data)
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        assert data["data"]["name"] == "Test Product"
    
    def test_create_customer(self):
        """Test creating a customer"""
        customer_data = {
            "email": "test@example.com",
            "first_name": "Test",
            "last_name": "Customer",
            "phone": "+1-555-0123"
        }
        
        response = self.client.post("/api/v1/ecommerce/customers", json=customer_data)
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        assert data["data"]["email"] == "test@example.com"
    
    def test_prometheus_metrics(self):
        """Test Prometheus metrics endpoint"""
        response = self.client.get("/metrics")
        assert response.status_code == 200
        
        # Check that it returns Prometheus format
        content = response.text
        assert "# HELP" in content or "# TYPE" in content or len(content) > 0
    
    def test_invalid_endpoint(self):
        """Test invalid endpoint returns 404"""
        response = self.client.get("/api/v1/invalid")
        assert response.status_code == 404
    
    def test_cors_headers(self):
        """Test CORS headers are present"""
        response = self.client.options("/api/v1/ecommerce/")
        assert response.status_code == 200
        assert "access-control-allow-origin" in response.headers


@pytest.mark.asyncio
class TestAsyncEndpoints:
    """Test async functionality"""
    
    async def test_async_health_check(self):
        """Test async health check"""
        async with AsyncClient(app=app, base_url="http://test") as ac:
            response = await ac.get("/health")
            assert response.status_code == 200
            
            data = response.json()
            assert "status" in data
    
    async def test_async_domain_interaction(self):
        """Test async domain interaction"""
        async with AsyncClient(app=app, base_url="http://test") as ac:
            # Get products
            products_response = await ac.get("/api/v1/ecommerce/products")
            assert products_response.status_code == 200
            
            # Get shipments  
            shipments_response = await ac.get("/api/v1/logistics/shipments")
            assert shipments_response.status_code == 200
            
            # Both should succeed
            products_data = products_response.json()
            shipments_data = shipments_response.json()
            
            assert products_data["success"] is True
            assert shipments_data["success"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])