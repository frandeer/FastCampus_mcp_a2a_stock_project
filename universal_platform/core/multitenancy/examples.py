"""
Examples of using the Universal Platform Multi-Tenancy system.

This module provides practical examples of how to implement and use
the multi-tenancy features in real applications.
"""

import asyncio
import logging
from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Request, Depends
from pydantic import BaseModel
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Import multi-tenancy components
from .tenant_context import TenantContext, TenantInfo, get_current_tenant, tenant_context
from .isolation import TenantIsolationManager, TenancyModel
from .routing import TenantRouterManager, DomainTenantResolver, HeaderTenantResolver
from .middleware import FastAPITenantMiddleware
from .repository import TenantAwareRepository, TenantModelMixin
from .configuration import TenantConfigurationManager, FileConfigurationProvider, get_tenant_config
from .migration import TenantMigrationManager

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database setup
engine = create_engine("sqlite:///example.db", echo=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# Example 1: Basic Multi-Tenant Models
class User(Base, TenantModelMixin):
    """User model with automatic tenant isolation."""
    
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(100), unique=True, index=True)
    full_name = Column(String(100))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Product(Base, TenantModelMixin):
    """Product model with tenant isolation."""
    
    __tablename__ = "products"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200))
    description = Column(Text)
    price = Column(Integer)  # Price in cents
    is_available = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Order(Base, TenantModelMixin):
    """Order model with tenant isolation."""
    
    __tablename__ = "orders"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer)  # Would be ForeignKey in real app
    product_id = Column(Integer)  # Would be ForeignKey in real app
    quantity = Column(Integer)
    total_amount = Column(Integer)  # Total in cents
    status = Column(String(50), default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)


# Create tables
Base.metadata.create_all(bind=engine)


# Example 2: Multi-Tenancy Setup
def setup_multitenancy():
    """Setup multi-tenancy configuration."""
    
    # Create isolation manager for shared database with row-level security
    isolation_manager = TenantIsolationManager(
        tenancy_model=TenancyModel.MULTI_TENANT_SHARED,
        engine=engine,
        tenant_id_column="tenant_id"
    )
    
    # Setup tenant routing
    router_manager = TenantRouterManager()
    
    # Add domain-based resolver
    domain_resolver = router_manager.add_domain_resolver(is_default=True)
    
    # Configure subdomain patterns
    domain_resolver.add_subdomain_pattern("myapp.com", "{subdomain}")
    domain_resolver.add_subdomain_pattern("localhost", "{subdomain}")
    
    # Add some test tenant mappings
    test_tenants = {
        "acme.myapp.com": TenantInfo(
            tenant_id="acme",
            tenant_name="Acme Corporation",
            domain="acme.myapp.com",
            metadata={"industry": "manufacturing"}
        ),
        "techcorp.myapp.com": TenantInfo(
            tenant_id="techcorp",
            tenant_name="Tech Corp",
            domain="techcorp.myapp.com",
            metadata={"industry": "technology"}
        ),
        "localhost:8000": TenantInfo(
            tenant_id="local",
            tenant_name="Local Development",
            domain="localhost:8000",
            metadata={"environment": "development"}
        )
    }
    
    for domain, tenant_info in test_tenants.items():
        domain_resolver.add_domain_mapping(domain, tenant_info)
    
    # Add header-based resolver as fallback
    router_manager.add_header_resolver(tenant_header="X-Tenant-ID")
    
    # Create composite resolver
    router_manager.create_composite_resolver(["domain", "header"])
    
    # Setup configuration management
    config_manager = TenantConfigurationManager()
    config_manager.add_provider(FileConfigurationProvider("config/"))
    
    return isolation_manager, router_manager, config_manager


# Example 3: Repository Pattern Usage
class UserService:
    """Service class demonstrating tenant-aware operations."""
    
    def __init__(self, isolation_manager: TenantIsolationManager):
        self.user_repo = TenantAwareRepository(User, isolation_manager)
        self.isolation_manager = isolation_manager
    
    def create_user(self, email: str, full_name: str) -> User:
        """Create a new user in the current tenant."""
        user = User(email=email, full_name=full_name)
        return self.user_repo.create(user)
    
    def get_user(self, user_id: int) -> Optional[User]:
        """Get a user by ID (automatically filtered by tenant)."""
        return self.user_repo.find_by_id(user_id)
    
    def get_users(self, limit: int = 100) -> List[User]:
        """Get all users for the current tenant."""
        return self.user_repo.find_all(limit=limit)
    
    def get_active_users(self) -> List[User]:
        """Get active users for the current tenant."""
        return self.user_repo.find_by_criteria({"is_active": True})
    
    def update_user(self, user_id: int, full_name: str = None) -> Optional[User]:
        """Update a user."""
        user = self.get_user(user_id)
        if user:
            if full_name:
                user.full_name = full_name
            return self.user_repo.update(user)
        return None
    
    def delete_user(self, user_id: int) -> bool:
        """Delete a user."""
        return self.user_repo.delete_by_id(user_id)


class ProductService:
    """Service class for product operations."""
    
    def __init__(self, isolation_manager: TenantIsolationManager):
        self.product_repo = TenantAwareRepository(Product, isolation_manager)
    
    def create_product(self, name: str, description: str, price: int) -> Product:
        """Create a new product."""
        product = Product(name=name, description=description, price=price)
        return self.product_repo.create(product)
    
    def get_products(self) -> List[Product]:
        """Get all products for the current tenant."""
        return self.product_repo.find_by_criteria({"is_available": True})
    
    def get_product(self, product_id: int) -> Optional[Product]:
        """Get a product by ID."""
        return self.product_repo.find_by_id(product_id)


class OrderService:
    """Service class for order operations."""
    
    def __init__(self, isolation_manager: TenantIsolationManager):
        self.order_repo = TenantAwareRepository(Order, isolation_manager)
        self.user_service = UserService(isolation_manager)
        self.product_service = ProductService(isolation_manager)
    
    def create_order(self, user_id: int, product_id: int, quantity: int) -> Order:
        """Create a new order."""
        # Validate user and product exist in current tenant
        user = self.user_service.get_user(user_id)
        if not user:
            raise ValueError("User not found")
        
        product = self.product_service.get_product(product_id)
        if not product:
            raise ValueError("Product not found")
        
        total_amount = product.price * quantity
        
        order = Order(
            user_id=user_id,
            product_id=product_id,
            quantity=quantity,
            total_amount=total_amount
        )
        
        return self.order_repo.create(order)
    
    def get_user_orders(self, user_id: int) -> List[Order]:
        """Get all orders for a user."""
        return self.order_repo.find_by_criteria({"user_id": user_id})
    
    def update_order_status(self, order_id: int, status: str) -> Optional[Order]:
        """Update order status."""
        order = self.order_repo.find_by_id(order_id)
        if order:
            order.status = status
            return self.order_repo.update(order)
        return None


# Example 4: FastAPI Application with Multi-Tenancy
def create_app(isolation_manager, router_manager, config_manager):
    """Create FastAPI application with multi-tenancy."""
    
    app = FastAPI(title="Multi-Tenant E-commerce API", version="1.0.0")
    
    # Add tenant middleware
    tenant_middleware = FastAPITenantMiddleware(
        router_manager=router_manager,
        require_tenant=True,
        excluded_paths=["/health", "/docs", "/openapi.json"]
    )
    
    app.middleware("http")(tenant_middleware)
    
    # Initialize services
    user_service = UserService(isolation_manager)
    product_service = ProductService(isolation_manager)
    order_service = OrderService(isolation_manager)
    
    # Pydantic models for API
    class UserCreate(BaseModel):
        email: str
        full_name: str
    
    class UserResponse(BaseModel):
        id: int
        email: str
        full_name: str
        is_active: bool
        tenant_id: str
        
        class Config:
            from_attributes = True
    
    class ProductCreate(BaseModel):
        name: str
        description: str
        price: int
    
    class ProductResponse(BaseModel):
        id: int
        name: str
        description: str
        price: int
        is_available: bool
        tenant_id: str
        
        class Config:
            from_attributes = True
    
    class OrderCreate(BaseModel):
        user_id: int
        product_id: int
        quantity: int
    
    class OrderResponse(BaseModel):
        id: int
        user_id: int
        product_id: int
        quantity: int
        total_amount: int
        status: str
        tenant_id: str
        
        class Config:
            from_attributes = True
    
    # Dependency to get current tenant
    def get_current_tenant_info():
        return get_current_tenant()
    
    # Health check endpoint
    @app.get("/health")
    async def health_check():
        return {"status": "healthy"}
    
    # Tenant info endpoint
    @app.get("/tenant/info")
    async def get_tenant_info(tenant: TenantContext = Depends(get_current_tenant_info)):
        return {
            "tenant_id": tenant.tenant_id,
            "tenant_name": tenant.tenant_name,
            "features": tenant.features,
            "settings": tenant.settings
        }
    
    # User endpoints
    @app.post("/users/", response_model=UserResponse)
    async def create_user(user_data: UserCreate):
        user = user_service.create_user(user_data.email, user_data.full_name)
        return user
    
    @app.get("/users/", response_model=List[UserResponse])
    async def get_users():
        users = user_service.get_users()
        return users
    
    @app.get("/users/{user_id}", response_model=UserResponse)
    async def get_user(user_id: int):
        user = user_service.get_user(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return user
    
    @app.delete("/users/{user_id}")
    async def delete_user(user_id: int):
        success = user_service.delete_user(user_id)
        if not success:
            raise HTTPException(status_code=404, detail="User not found")
        return {"message": "User deleted successfully"}
    
    # Product endpoints
    @app.post("/products/", response_model=ProductResponse)
    async def create_product(product_data: ProductCreate):
        product = product_service.create_product(
            product_data.name,
            product_data.description,
            product_data.price
        )
        return product
    
    @app.get("/products/", response_model=List[ProductResponse])
    async def get_products():
        products = product_service.get_products()
        return products
    
    @app.get("/products/{product_id}", response_model=ProductResponse)
    async def get_product(product_id: int):
        product = product_service.get_product(product_id)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        return product
    
    # Order endpoints
    @app.post("/orders/", response_model=OrderResponse)
    async def create_order(order_data: OrderCreate):
        try:
            order = order_service.create_order(
                order_data.user_id,
                order_data.product_id,
                order_data.quantity
            )
            return order
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    
    @app.get("/users/{user_id}/orders", response_model=List[OrderResponse])
    async def get_user_orders(user_id: int):
        orders = order_service.get_user_orders(user_id)
        return orders
    
    @app.patch("/orders/{order_id}/status")
    async def update_order_status(order_id: int, status: str):
        order = order_service.update_order_status(order_id, status)
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        return {"message": "Order status updated successfully"}
    
    return app


# Example 5: Cross-Tenant Operations (Admin)
class AdminService:
    """Admin service with cross-tenant capabilities."""
    
    def __init__(self, isolation_manager: TenantIsolationManager):
        from .repository import CrossTenantRepository
        self.user_repo = CrossTenantRepository(User, isolation_manager)
        self.product_repo = CrossTenantRepository(Product, isolation_manager)
        self.order_repo = CrossTenantRepository(Order, isolation_manager)
    
    def get_tenant_statistics(self):
        """Get statistics across all tenants."""
        user_stats = self.user_repo.get_tenant_statistics()
        product_stats = self.product_repo.get_tenant_statistics()
        order_stats = self.order_repo.get_tenant_statistics()
        
        return {
            "users": user_stats,
            "products": product_stats,
            "orders": order_stats
        }
    
    def get_tenant_data(self, tenant_id: str):
        """Get all data for a specific tenant."""
        users = self.user_repo.find_by_tenant(tenant_id)
        products = self.product_repo.find_by_tenant(tenant_id)
        orders = self.order_repo.find_by_tenant(tenant_id)
        
        return {
            "tenant_id": tenant_id,
            "users": len(users),
            "products": len(products),
            "orders": len(orders)
        }


# Example 6: Manual Tenant Context Management
async def process_orders_for_tenant(tenant_id: str, isolation_manager: TenantIsolationManager):
    """Example of manual tenant context management."""
    
    # Create tenant context
    tenant_info = TenantInfo(
        tenant_id=tenant_id,
        tenant_name=f"Tenant {tenant_id}"
    )
    tenant_ctx = TenantContext(tenant=tenant_info)
    
    # Use context manager for operations
    with tenant_context(tenant_ctx):
        order_service = OrderService(isolation_manager)
        
        # Get all pending orders for this tenant
        session = isolation_manager.get_session()
        pending_orders = session.query(Order).filter(
            Order.status == "pending"
        ).all()
        
        logger.info(f"Processing {len(pending_orders)} orders for tenant {tenant_id}")
        
        for order in pending_orders:
            # Process order logic here
            order.status = "processed"
            order_service.order_repo.update(order)
            
            logger.info(f"Processed order {order.id} for tenant {tenant_id}")
        
        session.close()


# Example 7: Configuration Usage
async def send_notification(user_id: int, message: str):
    """Example of using tenant-specific configuration."""
    
    # Get tenant-specific notification settings
    email_enabled = get_tenant_config("notifications.email.enabled", True)
    sms_enabled = get_tenant_config("notifications.sms.enabled", False)
    
    # Get integration settings
    sendgrid_api_key = get_tenant_config("integrations.sendgrid.api_key")
    twilio_auth_token = get_tenant_config("integrations.twilio.auth_token")
    
    tenant = get_current_tenant()
    
    if email_enabled and sendgrid_api_key:
        # Send email notification
        logger.info(f"Sending email notification to user {user_id} in tenant {tenant.tenant_id}")
        # Implementation would use SendGrid API
    
    if sms_enabled and twilio_auth_token:
        # Send SMS notification
        logger.info(f"Sending SMS notification to user {user_id} in tenant {tenant.tenant_id}")
        # Implementation would use Twilio API


# Example 8: Testing with Multi-Tenancy
import pytest

@pytest.fixture
def test_isolation_manager():
    """Test fixture for isolation manager."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    
    return TenantIsolationManager(
        tenancy_model=TenancyModel.MULTI_TENANT_SHARED,
        engine=engine
    )

@pytest.fixture
def test_tenant_context():
    """Test fixture for tenant context."""
    tenant_info = TenantInfo(
        tenant_id="test_tenant",
        tenant_name="Test Tenant"
    )
    return TenantContext(tenant=tenant_info)

def test_user_creation(test_isolation_manager, test_tenant_context):
    """Test user creation with tenant context."""
    user_service = UserService(test_isolation_manager)
    
    with tenant_context(test_tenant_context):
        # Create user
        user = user_service.create_user("test@example.com", "Test User")
        
        # Verify tenant isolation
        assert user.tenant_id == "test_tenant"
        
        # Verify user can be retrieved
        retrieved_user = user_service.get_user(user.id)
        assert retrieved_user is not None
        assert retrieved_user.email == "test@example.com"

def test_cross_tenant_isolation(test_isolation_manager):
    """Test that tenants cannot access each other's data."""
    user_service = UserService(test_isolation_manager)
    
    # Create users in different tenants
    tenant1_info = TenantInfo(tenant_id="tenant1", tenant_name="Tenant 1")
    tenant2_info = TenantInfo(tenant_id="tenant2", tenant_name="Tenant 2")
    
    tenant1_context = TenantContext(tenant=tenant1_info)
    tenant2_context = TenantContext(tenant=tenant2_info)
    
    # Create user in tenant 1
    with tenant_context(tenant1_context):
        user1 = user_service.create_user("user1@example.com", "User 1")
        user1_id = user1.id
    
    # Try to access user1 from tenant 2
    with tenant_context(tenant2_context):
        retrieved_user = user_service.get_user(user1_id)
        assert retrieved_user is None  # Should not be able to access


# Example 9: Background Task Processing
async def background_tenant_processor(isolation_manager: TenantIsolationManager):
    """Example of background processing for multiple tenants."""
    
    admin_service = AdminService(isolation_manager)
    
    # Get all tenant IDs (this would come from your tenant management system)
    tenant_ids = ["acme", "techcorp", "startup"]
    
    for tenant_id in tenant_ids:
        try:
            await process_orders_for_tenant(tenant_id, isolation_manager)
            
            # Log tenant statistics
            stats = admin_service.get_tenant_data(tenant_id)
            logger.info(f"Tenant {tenant_id} stats: {stats}")
            
        except Exception as e:
            logger.error(f"Error processing tenant {tenant_id}: {e}")
    
    # Overall statistics
    overall_stats = admin_service.get_tenant_statistics()
    logger.info(f"Overall statistics: {overall_stats}")


# Example 10: Main Application Entry Point
def main():
    """Main entry point demonstrating complete setup."""
    
    # Setup multi-tenancy
    isolation_manager, router_manager, config_manager = setup_multitenancy()
    
    # Create FastAPI app
    app = create_app(isolation_manager, router_manager, config_manager)
    
    # Example usage
    logger.info("Multi-tenant application setup complete")
    logger.info("Available endpoints:")
    logger.info("  POST /users/ - Create user")
    logger.info("  GET /users/ - List users")
    logger.info("  GET /users/{id} - Get user")
    logger.info("  POST /products/ - Create product")
    logger.info("  GET /products/ - List products")
    logger.info("  POST /orders/ - Create order")
    logger.info("  GET /tenant/info - Get tenant information")
    
    logger.info("Test with different tenants:")
    logger.info("  Host: acme.myapp.com or X-Tenant-ID: acme")
    logger.info("  Host: techcorp.myapp.com or X-Tenant-ID: techcorp")
    
    return app


if __name__ == "__main__":
    # Run with: uvicorn examples:main --reload --host 0.0.0.0 --port 8000
    app = main()
    
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")