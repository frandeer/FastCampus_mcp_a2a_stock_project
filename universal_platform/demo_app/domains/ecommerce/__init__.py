"""
E-commerce Domain

This domain provides a complete e-commerce platform including:
- Product catalog management
- Order processing and fulfillment
- Payment processing
- Inventory management
- Customer management
- Shopping cart functionality
- Pricing and promotions
- Analytics and reporting
"""

from .router import EcommerceRouter
from .domain import EcommerceDomain
from .models import Product, Order, Customer, CartItem, Payment, OrderStatus
from .services import ProductService, OrderService, CustomerService, PaymentService

__all__ = [
    "EcommerceRouter",
    "EcommerceDomain", 
    "Product",
    "Order",
    "Customer",
    "CartItem",
    "Payment",
    "OrderStatus",
    "ProductService",
    "OrderService",
    "CustomerService",
    "PaymentService"
]