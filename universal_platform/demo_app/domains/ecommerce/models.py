"""
E-commerce domain data models
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum
from decimal import Decimal
from dataclasses import dataclass, field
from pydantic import BaseModel, Field

from ..shared.models import BaseEntity, EntityStatus


class ProductStatus(str, Enum):
    """Product status enumeration"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    OUT_OF_STOCK = "out_of_stock"
    DISCONTINUED = "discontinued"


class OrderStatus(str, Enum):
    """Order status enumeration"""
    PENDING = "pending"
    CONFIRMED = "confirmed"
    PROCESSING = "processing"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class PaymentStatus(str, Enum):
    """Payment status enumeration"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class PaymentMethod(str, Enum):
    """Payment method enumeration"""
    CREDIT_CARD = "credit_card"
    DEBIT_CARD = "debit_card"
    PAYPAL = "paypal"
    BANK_TRANSFER = "bank_transfer"
    CRYPTO = "crypto"
    CASH_ON_DELIVERY = "cash_on_delivery"


@dataclass
class Product(BaseEntity):
    """Product entity"""
    name: str = ""
    description: Optional[str] = None
    category: str = ""
    sku: str = ""
    price: Decimal = field(default_factory=lambda: Decimal('0.00'))
    currency: str = "USD"
    inventory_quantity: int = 0
    min_stock_level: int = 0
    max_stock_level: int = 1000
    weight_kg: Optional[Decimal] = None
    dimensions: Optional[Dict[str, Decimal]] = None  # length, width, height
    images: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    attributes: Dict[str, Any] = field(default_factory=dict)
    product_status: ProductStatus = ProductStatus.ACTIVE
    supplier_id: Optional[str] = None
    brand: Optional[str] = None
    
    def is_in_stock(self) -> bool:
        """Check if product is in stock"""
        return self.inventory_quantity > 0 and self.product_status == ProductStatus.ACTIVE
    
    def is_low_stock(self) -> bool:
        """Check if product is low stock"""
        return self.inventory_quantity <= self.min_stock_level
    
    def update_inventory(self, quantity_change: int):
        """Update inventory quantity"""
        self.inventory_quantity += quantity_change
        if self.inventory_quantity <= 0:
            self.product_status = ProductStatus.OUT_OF_STOCK
        elif self.product_status == ProductStatus.OUT_OF_STOCK and self.inventory_quantity > 0:
            self.product_status = ProductStatus.ACTIVE


@dataclass
class Customer(BaseEntity):
    """Customer entity"""
    email: str = ""
    first_name: str = ""
    last_name: str = ""
    phone: Optional[str] = None
    birth_date: Optional[datetime] = None
    
    # Address information
    billing_address: Optional[Dict[str, str]] = None
    shipping_addresses: List[Dict[str, str]] = field(default_factory=list)
    
    # Customer preferences
    preferred_currency: str = "USD"
    preferred_language: str = "en"
    marketing_consent: bool = False
    
    # Customer status
    is_verified: bool = False
    loyalty_points: int = 0
    total_orders: int = 0
    total_spent: Decimal = field(default_factory=lambda: Decimal('0.00'))
    last_order_date: Optional[datetime] = None
    
    def get_full_name(self) -> str:
        """Get customer's full name"""
        return f"{self.first_name} {self.last_name}".strip()
    
    def add_loyalty_points(self, points: int):
        """Add loyalty points"""
        self.loyalty_points += points
    
    def update_order_stats(self, order_total: Decimal):
        """Update customer order statistics"""
        self.total_orders += 1
        self.total_spent += order_total
        self.last_order_date = datetime.utcnow()


@dataclass
class CartItem:
    """Shopping cart item"""
    product_id: str
    quantity: int
    unit_price: Decimal
    total_price: Decimal = field(init=False)
    added_at: datetime = field(default_factory=datetime.utcnow)
    
    def __post_init__(self):
        self.total_price = self.unit_price * self.quantity


@dataclass
class OrderItem:
    """Order item"""
    product_id: str
    product_name: str
    sku: str
    quantity: int
    unit_price: Decimal
    total_price: Decimal
    product_attributes: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Order(BaseEntity):
    """Order entity"""
    order_number: str = ""
    customer_id: str = ""
    
    # Order items
    items: List[OrderItem] = field(default_factory=list)
    
    # Pricing
    subtotal: Decimal = field(default_factory=lambda: Decimal('0.00'))
    tax_amount: Decimal = field(default_factory=lambda: Decimal('0.00'))
    shipping_cost: Decimal = field(default_factory=lambda: Decimal('0.00'))
    discount_amount: Decimal = field(default_factory=lambda: Decimal('0.00'))
    total_amount: Decimal = field(default_factory=lambda: Decimal('0.00'))
    currency: str = "USD"
    
    # Shipping information
    shipping_address: Dict[str, str] = field(default_factory=dict)
    billing_address: Dict[str, str] = field(default_factory=dict)
    shipping_method: Optional[str] = None
    tracking_number: Optional[str] = None
    
    # Order status and timing
    order_status: OrderStatus = OrderStatus.PENDING
    order_date: datetime = field(default_factory=datetime.utcnow)
    shipped_date: Optional[datetime] = None
    delivered_date: Optional[datetime] = None
    
    # Payment information
    payment_id: Optional[str] = None
    payment_status: PaymentStatus = PaymentStatus.PENDING
    
    # Additional information
    notes: Optional[str] = None
    source: str = "web"  # web, mobile, api, etc.
    
    def calculate_totals(self):
        """Calculate order totals"""
        self.subtotal = sum(item.total_price for item in self.items)
        self.total_amount = self.subtotal + self.tax_amount + self.shipping_cost - self.discount_amount
    
    def add_item(self, item: OrderItem):
        """Add item to order"""
        self.items.append(item)
        self.calculate_totals()
    
    def remove_item(self, product_id: str):
        """Remove item from order"""
        self.items = [item for item in self.items if item.product_id != product_id]
        self.calculate_totals()
    
    def update_status(self, new_status: OrderStatus):
        """Update order status with timestamp tracking"""
        self.order_status = new_status
        
        if new_status == OrderStatus.SHIPPED and not self.shipped_date:
            self.shipped_date = datetime.utcnow()
        elif new_status == OrderStatus.DELIVERED and not self.delivered_date:
            self.delivered_date = datetime.utcnow()


@dataclass
class Payment(BaseEntity):
    """Payment entity"""
    order_id: str = ""
    customer_id: str = ""
    
    # Payment details
    amount: Decimal = field(default_factory=lambda: Decimal('0.00'))
    currency: str = "USD"
    payment_method: PaymentMethod = PaymentMethod.CREDIT_CARD
    payment_status: PaymentStatus = PaymentStatus.PENDING
    
    # Payment processing
    transaction_id: Optional[str] = None
    gateway_response: Optional[Dict[str, Any]] = None
    processor_fee: Decimal = field(default_factory=lambda: Decimal('0.00'))
    
    # Timing
    processed_at: Optional[datetime] = None
    
    # Security
    risk_score: Optional[float] = None
    fraud_flags: List[str] = field(default_factory=list)
    
    def mark_completed(self, transaction_id: str):
        """Mark payment as completed"""
        self.payment_status = PaymentStatus.COMPLETED
        self.transaction_id = transaction_id
        self.processed_at = datetime.utcnow()
    
    def mark_failed(self, reason: str):
        """Mark payment as failed"""
        self.payment_status = PaymentStatus.FAILED
        self.gateway_response = {"error": reason, "timestamp": datetime.utcnow().isoformat()}


# Pydantic models for API requests/responses

class ProductCreate(BaseModel):
    """Product creation request"""
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    category: str = Field(..., min_length=1, max_length=100)
    sku: str = Field(..., min_length=1, max_length=50)
    price: Decimal = Field(..., gt=0)
    currency: str = Field(default="USD", max_length=3)
    inventory_quantity: int = Field(default=0, ge=0)
    min_stock_level: int = Field(default=0, ge=0)
    max_stock_level: int = Field(default=1000, gt=0)
    weight_kg: Optional[Decimal] = Field(None, gt=0)
    images: Optional[List[str]] = Field(default_factory=list)
    tags: Optional[List[str]] = Field(default_factory=list)
    attributes: Optional[Dict[str, Any]] = Field(default_factory=dict)
    supplier_id: Optional[str] = None
    brand: Optional[str] = Field(None, max_length=100)


class ProductUpdate(BaseModel):
    """Product update request"""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    category: Optional[str] = Field(None, min_length=1, max_length=100)
    price: Optional[Decimal] = Field(None, gt=0)
    inventory_quantity: Optional[int] = Field(None, ge=0)
    min_stock_level: Optional[int] = Field(None, ge=0)
    max_stock_level: Optional[int] = Field(None, gt=0)
    weight_kg: Optional[Decimal] = Field(None, gt=0)
    images: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    attributes: Optional[Dict[str, Any]] = None
    product_status: Optional[ProductStatus] = None
    supplier_id: Optional[str] = None
    brand: Optional[str] = Field(None, max_length=100)


class CustomerCreate(BaseModel):
    """Customer creation request"""
    email: str = Field(..., regex=r'^[^@]+@[^@]+\.[^@]+$')
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    phone: Optional[str] = Field(None, max_length=20)
    billing_address: Optional[Dict[str, str]] = None
    shipping_addresses: Optional[List[Dict[str, str]]] = Field(default_factory=list)
    preferred_currency: str = Field(default="USD", max_length=3)
    preferred_language: str = Field(default="en", max_length=5)
    marketing_consent: bool = Field(default=False)


class OrderCreate(BaseModel):
    """Order creation request"""
    customer_id: str = Field(..., min_length=1)
    items: List[Dict[str, Any]] = Field(..., min_items=1)
    shipping_address: Dict[str, str] = Field(...)
    billing_address: Optional[Dict[str, str]] = None
    shipping_method: Optional[str] = None
    notes: Optional[str] = Field(None, max_length=1000)
    source: str = Field(default="web", max_length=20)


class PaymentCreate(BaseModel):
    """Payment creation request"""
    order_id: str = Field(..., min_length=1)
    payment_method: PaymentMethod = Field(...)
    amount: Optional[Decimal] = Field(None, gt=0)  # If not provided, use order total


class CartItemAdd(BaseModel):
    """Add item to cart request"""
    product_id: str = Field(..., min_length=1)
    quantity: int = Field(..., gt=0)


class InventoryUpdate(BaseModel):
    """Inventory update request"""
    product_id: str = Field(..., min_length=1)
    quantity_change: int = Field(...)
    reason: str = Field(..., min_length=1, max_length=200)