"""
E-commerce domain API router
"""

import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, Query
from decimal import Decimal

from ...core.di import get_container
from ..shared.models import BaseResponse, ErrorResponse, PaginatedResponse
from .models import (
    ProductCreate, ProductUpdate, CustomerCreate, OrderCreate, PaymentCreate,
    CartItemAdd, InventoryUpdate, ProductStatus, OrderStatus, PaymentMethod
)
from .services import ProductService, CustomerService, OrderService, PaymentService

logger = logging.getLogger(__name__)

# Create router
EcommerceRouter = APIRouter()


# Dependency to get services from DI container
def get_product_service() -> ProductService:
    container = get_container()
    return container.resolve(ProductService)


def get_customer_service() -> CustomerService:
    container = get_container()
    return container.resolve(CustomerService)


def get_order_service() -> OrderService:
    container = get_container()
    return container.resolve(OrderService)


def get_payment_service() -> PaymentService:
    container = get_container()
    return container.resolve(PaymentService)


# Product Management Routes

@EcommerceRouter.get("/", tags=["E-commerce"])
async def ecommerce_info():
    """Get e-commerce domain information"""
    return {
        "domain": "ecommerce",
        "version": "1.0.0",
        "description": "Complete e-commerce platform with products, orders, and payments",
        "features": [
            "Product catalog management",
            "Order processing and fulfillment", 
            "Payment processing",
            "Inventory management",
            "Customer management",
            "Shopping cart functionality"
        ],
        "endpoints": {
            "products": "/products",
            "customers": "/customers", 
            "orders": "/orders",
            "payments": "/payments"
        }
    }


@EcommerceRouter.post("/products", tags=["Products"])
async def create_product(
    product_data: ProductCreate,
    tenant_id: str = "default",
    product_service: ProductService = Depends(get_product_service)
):
    """Create a new product"""
    try:
        product = await product_service.create_product(product_data, tenant_id)
        return BaseResponse(
            message="Product created successfully",
            data={
                "id": product.id,
                "name": product.name,
                "sku": product.sku,
                "price": float(product.price),
                "inventory_quantity": product.inventory_quantity
            }
        )
    except Exception as e:
        logger.error(f"Error creating product: {e}")
        return ErrorResponse(
            message=f"Failed to create product: {str(e)}",
            error_code="PRODUCT_CREATION_FAILED"
        )


@EcommerceRouter.get("/products", tags=["Products"])
async def list_products(
    tenant_id: str = "default",
    category: Optional[str] = Query(None, description="Filter by category"),
    status: Optional[ProductStatus] = Query(None, description="Filter by status"),
    search: Optional[str] = Query(None, description="Search products"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    product_service: ProductService = Depends(get_product_service)
):
    """List products with filtering and pagination"""
    try:
        products = await product_service.list_products(
            tenant_id=tenant_id,
            category=category,
            status=status,
            search=search,
            limit=limit,
            offset=offset
        )
        
        # Convert to response format
        products_data = []
        for product in products:
            products_data.append({
                "id": product.id,
                "name": product.name,
                "description": product.description,
                "category": product.category,
                "sku": product.sku,
                "price": float(product.price),
                "currency": product.currency,
                "inventory_quantity": product.inventory_quantity,
                "status": product.product_status.value,
                "brand": product.brand,
                "images": product.images,
                "tags": product.tags,
                "created_at": product.created_at.isoformat(),
                "is_in_stock": product.is_in_stock(),
                "is_low_stock": product.is_low_stock()
            })
        
        return BaseResponse(
            message="Products retrieved successfully",
            data=products_data
        )
    except Exception as e:
        logger.error(f"Error listing products: {e}")
        return ErrorResponse(
            message=f"Failed to list products: {str(e)}",
            error_code="PRODUCT_LIST_FAILED"
        )


@EcommerceRouter.get("/products/{product_id}", tags=["Products"])
async def get_product(
    product_id: str,
    product_service: ProductService = Depends(get_product_service)
):
    """Get a specific product"""
    try:
        product = await product_service.get_product(product_id)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        
        return BaseResponse(
            message="Product retrieved successfully",
            data={
                "id": product.id,
                "name": product.name,
                "description": product.description,
                "category": product.category,
                "sku": product.sku,
                "price": float(product.price),
                "currency": product.currency,
                "inventory_quantity": product.inventory_quantity,
                "min_stock_level": product.min_stock_level,
                "max_stock_level": product.max_stock_level,
                "weight_kg": float(product.weight_kg) if product.weight_kg else None,
                "dimensions": product.dimensions,
                "images": product.images,
                "tags": product.tags,
                "attributes": product.attributes,
                "status": product.product_status.value,
                "supplier_id": product.supplier_id,
                "brand": product.brand,
                "created_at": product.created_at.isoformat(),
                "updated_at": product.updated_at.isoformat() if product.updated_at else None,
                "is_in_stock": product.is_in_stock(),
                "is_low_stock": product.is_low_stock()
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting product {product_id}: {e}")
        return ErrorResponse(
            message=f"Failed to get product: {str(e)}",
            error_code="PRODUCT_GET_FAILED"
        )


@EcommerceRouter.put("/products/{product_id}", tags=["Products"])
async def update_product(
    product_id: str,
    product_data: ProductUpdate,
    product_service: ProductService = Depends(get_product_service)
):
    """Update a product"""
    try:
        product = await product_service.update_product(product_id, product_data)
        return BaseResponse(
            message="Product updated successfully",
            data={
                "id": product.id,
                "name": product.name,
                "sku": product.sku,
                "price": float(product.price),
                "inventory_quantity": product.inventory_quantity,
                "status": product.product_status.value,
                "updated_at": product.updated_at.isoformat()
            }
        )
    except Exception as e:
        logger.error(f"Error updating product {product_id}: {e}")
        return ErrorResponse(
            message=f"Failed to update product: {str(e)}",
            error_code="PRODUCT_UPDATE_FAILED"
        )


@EcommerceRouter.delete("/products/{product_id}", tags=["Products"])
async def delete_product(
    product_id: str,
    product_service: ProductService = Depends(get_product_service)
):
    """Delete a product"""
    try:
        await product_service.delete_product(product_id)
        return BaseResponse(message="Product deleted successfully")
    except Exception as e:
        logger.error(f"Error deleting product {product_id}: {e}")
        return ErrorResponse(
            message=f"Failed to delete product: {str(e)}",
            error_code="PRODUCT_DELETE_FAILED"
        )


@EcommerceRouter.post("/products/{product_id}/inventory", tags=["Products"])
async def update_inventory(
    product_id: str,
    inventory_data: InventoryUpdate,
    product_service: ProductService = Depends(get_product_service)
):
    """Update product inventory"""
    try:
        await product_service.update_inventory(
            inventory_data.product_id,
            inventory_data.quantity_change,
            inventory_data.reason
        )
        
        # Get updated product
        product = await product_service.get_product(product_id)
        
        return BaseResponse(
            message="Inventory updated successfully",
            data={
                "product_id": product_id,
                "new_quantity": product.inventory_quantity,
                "quantity_change": inventory_data.quantity_change,
                "is_in_stock": product.is_in_stock(),
                "is_low_stock": product.is_low_stock()
            }
        )
    except Exception as e:
        logger.error(f"Error updating inventory for product {product_id}: {e}")
        return ErrorResponse(
            message=f"Failed to update inventory: {str(e)}",
            error_code="INVENTORY_UPDATE_FAILED"
        )


@EcommerceRouter.get("/categories", tags=["Products"])
async def get_categories(
    tenant_id: str = "default",
    product_service: ProductService = Depends(get_product_service)
):
    """Get all product categories"""
    try:
        categories = await product_service.get_categories(tenant_id)
        return BaseResponse(
            message="Categories retrieved successfully",
            data={"categories": categories}
        )
    except Exception as e:
        logger.error(f"Error getting categories: {e}")
        return ErrorResponse(
            message=f"Failed to get categories: {str(e)}",
            error_code="CATEGORIES_GET_FAILED"
        )


# Customer Management Routes

@EcommerceRouter.post("/customers", tags=["Customers"])
async def create_customer(
    customer_data: CustomerCreate,
    tenant_id: str = "default",
    customer_service: CustomerService = Depends(get_customer_service)
):
    """Create a new customer"""
    try:
        customer = await customer_service.create_customer(customer_data, tenant_id)
        return BaseResponse(
            message="Customer created successfully",
            data={
                "id": customer.id,
                "email": customer.email,
                "name": customer.get_full_name(),
                "is_verified": customer.is_verified,
                "loyalty_points": customer.loyalty_points
            }
        )
    except Exception as e:
        logger.error(f"Error creating customer: {e}")
        return ErrorResponse(
            message=f"Failed to create customer: {str(e)}",
            error_code="CUSTOMER_CREATION_FAILED"
        )


@EcommerceRouter.get("/customers", tags=["Customers"])
async def list_customers(
    tenant_id: str = "default",
    search: Optional[str] = Query(None, description="Search customers"),
    verified_only: bool = Query(False, description="Show only verified customers"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    customer_service: CustomerService = Depends(get_customer_service)
):
    """List customers"""
    try:
        customers = await customer_service.list_customers(
            tenant_id=tenant_id,
            search=search,
            verified_only=verified_only,
            limit=limit,
            offset=offset
        )
        
        customers_data = []
        for customer in customers:
            customers_data.append({
                "id": customer.id,
                "email": customer.email,
                "name": customer.get_full_name(),
                "phone": customer.phone,
                "is_verified": customer.is_verified,
                "loyalty_points": customer.loyalty_points,
                "total_orders": customer.total_orders,
                "total_spent": float(customer.total_spent),
                "last_order_date": customer.last_order_date.isoformat() if customer.last_order_date else None,
                "created_at": customer.created_at.isoformat()
            })
        
        return BaseResponse(
            message="Customers retrieved successfully",
            data=customers_data
        )
    except Exception as e:
        logger.error(f"Error listing customers: {e}")
        return ErrorResponse(
            message=f"Failed to list customers: {str(e)}",
            error_code="CUSTOMER_LIST_FAILED"
        )


@EcommerceRouter.get("/customers/{customer_id}", tags=["Customers"])
async def get_customer(
    customer_id: str,
    customer_service: CustomerService = Depends(get_customer_service)
):
    """Get a specific customer"""
    try:
        customer = await customer_service.get_customer(customer_id)
        if not customer:
            raise HTTPException(status_code=404, detail="Customer not found")
        
        return BaseResponse(
            message="Customer retrieved successfully",
            data={
                "id": customer.id,
                "email": customer.email,
                "first_name": customer.first_name,
                "last_name": customer.last_name,
                "phone": customer.phone,
                "birth_date": customer.birth_date.isoformat() if customer.birth_date else None,
                "billing_address": customer.billing_address,
                "shipping_addresses": customer.shipping_addresses,
                "preferred_currency": customer.preferred_currency,
                "preferred_language": customer.preferred_language,
                "marketing_consent": customer.marketing_consent,
                "is_verified": customer.is_verified,
                "loyalty_points": customer.loyalty_points,
                "total_orders": customer.total_orders,
                "total_spent": float(customer.total_spent),
                "last_order_date": customer.last_order_date.isoformat() if customer.last_order_date else None,
                "created_at": customer.created_at.isoformat(),
                "updated_at": customer.updated_at.isoformat() if customer.updated_at else None
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting customer {customer_id}: {e}")
        return ErrorResponse(
            message=f"Failed to get customer: {str(e)}",
            error_code="CUSTOMER_GET_FAILED"
        )


# Order Management Routes

@EcommerceRouter.post("/orders", tags=["Orders"])
async def create_order(
    order_data: OrderCreate,
    tenant_id: str = "default",
    order_service: OrderService = Depends(get_order_service)
):
    """Create a new order"""
    try:
        order = await order_service.create_order(order_data, tenant_id)
        return BaseResponse(
            message="Order created successfully",
            data={
                "id": order.id,
                "order_number": order.order_number,
                "customer_id": order.customer_id,
                "status": order.order_status.value,
                "total_amount": float(order.total_amount),
                "currency": order.currency,
                "created_at": order.created_at.isoformat()
            }
        )
    except Exception as e:
        logger.error(f"Error creating order: {e}")
        return ErrorResponse(
            message=f"Failed to create order: {str(e)}",
            error_code="ORDER_CREATION_FAILED"
        )


@EcommerceRouter.get("/orders", tags=["Orders"])
async def list_orders(
    tenant_id: str = "default",
    customer_id: Optional[str] = Query(None, description="Filter by customer"),
    status: Optional[OrderStatus] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    order_service: OrderService = Depends(get_order_service)
):
    """List orders"""
    try:
        orders = await order_service.list_orders(
            tenant_id=tenant_id,
            customer_id=customer_id,
            status=status,
            limit=limit,
            offset=offset
        )
        
        orders_data = []
        for order in orders:
            orders_data.append({
                "id": order.id,
                "order_number": order.order_number,
                "customer_id": order.customer_id,
                "status": order.order_status.value,
                "subtotal": float(order.subtotal),
                "tax_amount": float(order.tax_amount),
                "shipping_cost": float(order.shipping_cost),
                "total_amount": float(order.total_amount),
                "currency": order.currency,
                "items_count": len(order.items),
                "order_date": order.order_date.isoformat(),
                "shipped_date": order.shipped_date.isoformat() if order.shipped_date else None,
                "delivered_date": order.delivered_date.isoformat() if order.delivered_date else None,
                "payment_status": order.payment_status.value
            })
        
        return BaseResponse(
            message="Orders retrieved successfully",
            data=orders_data
        )
    except Exception as e:
        logger.error(f"Error listing orders: {e}")
        return ErrorResponse(
            message=f"Failed to list orders: {str(e)}",
            error_code="ORDER_LIST_FAILED"
        )


@EcommerceRouter.get("/orders/{order_id}", tags=["Orders"])
async def get_order(
    order_id: str,
    order_service: OrderService = Depends(get_order_service)
):
    """Get a specific order"""
    try:
        order = await order_service.get_order(order_id)
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        
        return BaseResponse(
            message="Order retrieved successfully",
            data={
                "id": order.id,
                "order_number": order.order_number,
                "customer_id": order.customer_id,
                "items": [
                    {
                        "product_id": item.product_id,
                        "product_name": item.product_name,
                        "sku": item.sku,
                        "quantity": item.quantity,
                        "unit_price": float(item.unit_price),
                        "total_price": float(item.total_price)
                    }
                    for item in order.items
                ],
                "subtotal": float(order.subtotal),
                "tax_amount": float(order.tax_amount),
                "shipping_cost": float(order.shipping_cost),
                "discount_amount": float(order.discount_amount),
                "total_amount": float(order.total_amount),
                "currency": order.currency,
                "shipping_address": order.shipping_address,
                "billing_address": order.billing_address,
                "shipping_method": order.shipping_method,
                "tracking_number": order.tracking_number,
                "status": order.order_status.value,
                "payment_status": order.payment_status.value,
                "order_date": order.order_date.isoformat(),
                "shipped_date": order.shipped_date.isoformat() if order.shipped_date else None,
                "delivered_date": order.delivered_date.isoformat() if order.delivered_date else None,
                "notes": order.notes,
                "source": order.source
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting order {order_id}: {e}")
        return ErrorResponse(
            message=f"Failed to get order: {str(e)}",
            error_code="ORDER_GET_FAILED"
        )


@EcommerceRouter.put("/orders/{order_id}/status", tags=["Orders"])
async def update_order_status(
    order_id: str,
    status: OrderStatus,
    order_service: OrderService = Depends(get_order_service)
):
    """Update order status"""
    try:
        order = await order_service.update_order_status(order_id, status)
        return BaseResponse(
            message="Order status updated successfully",
            data={
                "id": order.id,
                "order_number": order.order_number,
                "status": order.order_status.value,
                "updated_at": order.updated_at.isoformat()
            }
        )
    except Exception as e:
        logger.error(f"Error updating order status: {e}")
        return ErrorResponse(
            message=f"Failed to update order status: {str(e)}",
            error_code="ORDER_STATUS_UPDATE_FAILED"
        )


# Payment Routes

@EcommerceRouter.post("/payments", tags=["Payments"])
async def create_payment(
    payment_data: PaymentCreate,
    tenant_id: str = "default",
    payment_service: PaymentService = Depends(get_payment_service)
):
    """Create and process a payment"""
    try:
        payment = await payment_service.create_payment(payment_data, tenant_id)
        return BaseResponse(
            message="Payment processed successfully",
            data={
                "id": payment.id,
                "order_id": payment.order_id,
                "amount": float(payment.amount),
                "currency": payment.currency,
                "payment_method": payment.payment_method.value,
                "status": payment.payment_status.value,
                "transaction_id": payment.transaction_id,
                "processed_at": payment.processed_at.isoformat() if payment.processed_at else None
            }
        )
    except Exception as e:
        logger.error(f"Error creating payment: {e}")
        return ErrorResponse(
            message=f"Failed to process payment: {str(e)}",
            error_code="PAYMENT_PROCESSING_FAILED"
        )


@EcommerceRouter.get("/payments/{payment_id}", tags=["Payments"])
async def get_payment(
    payment_id: str,
    payment_service: PaymentService = Depends(get_payment_service)
):
    """Get a specific payment"""
    try:
        payment = await payment_service.get_payment(payment_id)
        if not payment:
            raise HTTPException(status_code=404, detail="Payment not found")
        
        return BaseResponse(
            message="Payment retrieved successfully",
            data={
                "id": payment.id,
                "order_id": payment.order_id,
                "customer_id": payment.customer_id,
                "amount": float(payment.amount),
                "currency": payment.currency,
                "payment_method": payment.payment_method.value,
                "status": payment.payment_status.value,
                "transaction_id": payment.transaction_id,
                "processor_fee": float(payment.processor_fee),
                "gateway_response": payment.gateway_response,
                "risk_score": payment.risk_score,
                "fraud_flags": payment.fraud_flags,
                "created_at": payment.created_at.isoformat(),
                "processed_at": payment.processed_at.isoformat() if payment.processed_at else None
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting payment {payment_id}: {e}")
        return ErrorResponse(
            message=f"Failed to get payment: {str(e)}",
            error_code="PAYMENT_GET_FAILED"
        )