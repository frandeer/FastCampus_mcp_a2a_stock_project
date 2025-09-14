"""
E-commerce domain orchestration and initialization
"""

import logging
from typing import Dict, List, Optional, Any

from ...core.di import injectable, inject
from ...core.events import EventBus
from ...core.plugins import PluginSystem
from ..shared.tenant_manager import TenantManager
from ..shared.metrics_collector import MetricsCollector
from .services import ProductService, CustomerService, OrderService, PaymentService

logger = logging.getLogger(__name__)


@injectable
class EcommerceDomain:
    """
    E-commerce domain orchestrator providing:
    - Domain initialization and lifecycle management
    - Service coordination and dependency injection
    - Event handling and cross-service communication
    - Domain-specific metrics and monitoring
    - Plugin integration and extension points
    - Business rule enforcement
    - Performance optimization
    """
    
    def __init__(
        self,
        event_bus: EventBus,
        plugin_system: PluginSystem,
        tenant_manager: TenantManager,
        metrics_collector: MetricsCollector,
        product_service: ProductService,
        customer_service: CustomerService,
        order_service: OrderService,
        payment_service: PaymentService
    ):
        self.event_bus = event_bus
        self.plugin_system = plugin_system
        self.tenant_manager = tenant_manager
        self.metrics_collector = metrics_collector
        self.product_service = product_service
        self.customer_service = customer_service
        self.order_service = order_service
        self.payment_service = payment_service
        
        # Domain state
        self.is_initialized = False
        self.active_campaigns: Dict[str, Any] = {}
        self.business_rules: List[Dict[str, Any]] = []
        
        # Initialize business rules
        self._initialize_business_rules()
    
    async def initialize(self):
        """Initialize the e-commerce domain"""
        try:
            if self.is_initialized:
                logger.warning("E-commerce domain already initialized")
                return
            
            # Initialize services
            await self.product_service.initialize()
            await self.customer_service.initialize()
            await self.order_service.initialize()
            await self.payment_service.initialize()
            
            # Setup domain-specific event subscriptions
            await self._setup_event_subscriptions()
            
            # Register domain metrics
            await self._register_domain_metrics()
            
            # Initialize domain plugins
            await self._initialize_domain_plugins()
            
            # Setup business rule enforcement
            await self._setup_business_rules()
            
            self.is_initialized = True
            
            # Publish domain initialization event
            await self.event_bus.publish("ecommerce.domain.initialized", {
                "domain": "ecommerce",
                "timestamp": self._get_timestamp(),
                "services": ["product", "customer", "order", "payment"],
                "plugins_loaded": len(self.plugin_system.get_loaded_plugins())
            })
            
            logger.info("E-commerce domain initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize e-commerce domain: {e}")
            raise
    
    async def shutdown(self):
        """Shutdown the e-commerce domain"""
        try:
            if not self.is_initialized:
                return
            
            # Publish shutdown event
            await self.event_bus.publish("ecommerce.domain.shutdown", {
                "domain": "ecommerce",
                "timestamp": self._get_timestamp()
            })
            
            self.is_initialized = False
            logger.info("E-commerce domain shut down successfully")
            
        except Exception as e:
            logger.error(f"Error shutting down e-commerce domain: {e}")
    
    async def get_domain_status(self) -> Dict[str, Any]:
        """Get comprehensive domain status"""
        try:
            # Get service statistics
            product_count = len(self.product_service.products)
            customer_count = len(self.customer_service.customers)
            order_count = len(self.order_service.orders)
            payment_count = len(self.payment_service.payments)
            
            # Get recent activity (simplified)
            recent_orders = await self.order_service.list_orders(limit=10)
            recent_payments = [p for p in self.payment_service.payments.values()][-10:]
            
            # Calculate business metrics
            total_revenue = sum(
                float(order.total_amount) for order in self.order_service.orders.values()
                if order.order_status.value in ["delivered", "shipped"]
            )
            
            avg_order_value = total_revenue / max(len(recent_orders), 1)
            
            return {
                "domain": "ecommerce",
                "status": "active" if self.is_initialized else "inactive",
                "initialized_at": self._get_timestamp(),
                "statistics": {
                    "total_products": product_count,
                    "total_customers": customer_count,
                    "total_orders": order_count,
                    "total_payments": payment_count,
                    "total_revenue": total_revenue,
                    "average_order_value": avg_order_value
                },
                "recent_activity": {
                    "recent_orders_count": len(recent_orders),
                    "recent_payments_count": len(recent_payments),
                    "active_campaigns": len(self.active_campaigns)
                },
                "business_rules": {
                    "total_rules": len(self.business_rules),
                    "active_rules": len([r for r in self.business_rules if r.get("active", True)])
                },
                "health": {
                    "services_healthy": True,  # Simplified health check
                    "plugins_loaded": len(self.plugin_system.get_loaded_plugins()),
                    "event_handlers": len(self.event_bus.handlers) if hasattr(self.event_bus, 'handlers') else 0
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting domain status: {e}")
            return {
                "domain": "ecommerce",
                "status": "error",
                "error": str(e)
            }
    
    async def process_order_fulfillment(self, order_id: str):
        """Process order fulfillment workflow"""
        try:
            order = await self.order_service.get_order(order_id)
            if not order:
                raise ValueError(f"Order {order_id} not found")
            
            # Update order status to processing
            await self.order_service.update_order_status(order_id, "processing")
            
            # Publish fulfillment event for logistics domain
            await self.event_bus.publish("ecommerce.order.fulfillment_requested", {
                "order_id": order_id,
                "order_number": order.order_number,
                "customer_id": order.customer_id,
                "items": [
                    {
                        "product_id": item.product_id,
                        "quantity": item.quantity,
                        "sku": item.sku
                    }
                    for item in order.items
                ],
                "shipping_address": order.shipping_address,
                "shipping_method": order.shipping_method
            })
            
            logger.info(f"Order fulfillment initiated for order {order.order_number}")
            
        except Exception as e:
            logger.error(f"Error processing order fulfillment: {e}")
            raise
    
    async def handle_inventory_alert(self, product_id: str):
        """Handle low inventory alert"""
        try:
            product = await self.product_service.get_product(product_id)
            if not product:
                return
            
            # Create reorder alert
            reorder_quantity = product.max_stock_level - product.inventory_quantity
            
            await self.event_bus.publish("ecommerce.inventory.reorder_alert", {
                "product_id": product_id,
                "sku": product.sku,
                "current_quantity": product.inventory_quantity,
                "min_stock_level": product.min_stock_level,
                "suggested_reorder_quantity": reorder_quantity,
                "supplier_id": product.supplier_id
            })
            
            logger.info(f"Reorder alert created for product {product.sku}")
            
        except Exception as e:
            logger.error(f"Error handling inventory alert: {e}")
    
    async def create_marketing_campaign(self, campaign_data: Dict[str, Any]):
        """Create and activate a marketing campaign"""
        try:
            campaign_id = f"campaign_{len(self.active_campaigns) + 1:03d}"
            
            campaign = {
                "id": campaign_id,
                "name": campaign_data.get("name", "Unnamed Campaign"),
                "type": campaign_data.get("type", "discount"),
                "target_audience": campaign_data.get("target_audience", "all"),
                "parameters": campaign_data.get("parameters", {}),
                "start_date": campaign_data.get("start_date"),
                "end_date": campaign_data.get("end_date"),
                "active": True,
                "created_at": self._get_timestamp()
            }
            
            self.active_campaigns[campaign_id] = campaign
            
            await self.event_bus.publish("ecommerce.campaign.created", {
                "campaign_id": campaign_id,
                "campaign_data": campaign
            })
            
            logger.info(f"Marketing campaign created: {campaign['name']}")
            return campaign
            
        except Exception as e:
            logger.error(f"Error creating marketing campaign: {e}")
            raise
    
    def _initialize_business_rules(self):
        """Initialize business rules"""
        self.business_rules = [
            {
                "id": "min_order_value",
                "name": "Minimum Order Value",
                "description": "Enforce minimum order value for free shipping",
                "type": "order_validation",
                "parameters": {"min_value": 50.00},
                "active": True
            },
            {
                "id": "inventory_reserve",
                "name": "Inventory Reservation",
                "description": "Reserve inventory when order is created",
                "type": "inventory_management",
                "parameters": {"reserve_on_order": True},
                "active": True
            },
            {
                "id": "loyalty_points",
                "name": "Loyalty Points Award",
                "description": "Award loyalty points on successful order completion",
                "type": "customer_loyalty",
                "parameters": {"points_per_dollar": 1},
                "active": True
            },
            {
                "id": "fraud_detection",
                "name": "Basic Fraud Detection",
                "description": "Basic fraud detection for payments",
                "type": "payment_security",
                "parameters": {"max_risk_score": 0.8},
                "active": True
            }
        ]
    
    async def _setup_event_subscriptions(self):
        """Setup domain-specific event subscriptions"""
        try:
            # Cross-domain integrations
            await self.event_bus.subscribe("logistics.shipment.created", self._handle_shipment_created)
            await self.event_bus.subscribe("logistics.delivery.completed", self._handle_delivery_completed)
            
            # Internal domain events
            await self.event_bus.subscribe("ecommerce.inventory.low_stock", self._handle_low_stock)
            await self.event_bus.subscribe("ecommerce.order.created", self._handle_order_created)
            await self.event_bus.subscribe("ecommerce.payment.completed", self._handle_payment_completed)
            await self.event_bus.subscribe("ecommerce.customer.created", self._handle_customer_created)
            
            logger.info("E-commerce domain event subscriptions configured")
            
        except Exception as e:
            logger.error(f"Error setting up event subscriptions: {e}")
            raise
    
    async def _register_domain_metrics(self):
        """Register domain-specific metrics"""
        try:
            # Register custom metrics collector for e-commerce
            def collect_ecommerce_metrics():
                return {
                    "active_products": len([p for p in self.product_service.products.values() if p.product_status.value == "active"]),
                    "out_of_stock_products": len([p for p in self.product_service.products.values() if p.product_status.value == "out_of_stock"]),
                    "pending_orders": len([o for o in self.order_service.orders.values() if o.order_status.value == "pending"]),
                    "completed_orders": len([o for o in self.order_service.orders.values() if o.order_status.value == "delivered"]),
                    "total_customers": len(self.customer_service.customers),
                    "verified_customers": len([c for c in self.customer_service.customers.values() if c.is_verified])
                }
            
            self.metrics_collector.register_custom_collector("ecommerce", collect_ecommerce_metrics)
            logger.info("E-commerce domain metrics registered")
            
        except Exception as e:
            logger.error(f"Error registering domain metrics: {e}")
    
    async def _initialize_domain_plugins(self):
        """Initialize domain-specific plugins"""
        try:
            # Load e-commerce specific plugins
            ecommerce_plugins = [
                name for name in self.plugin_system.get_loaded_plugins()
                if "ecommerce" in name.lower()
            ]
            
            for plugin_name in ecommerce_plugins:
                try:
                    # Initialize plugin with domain context
                    plugin_status = await self.plugin_system.get_plugin_status(plugin_name)
                    if plugin_status.get("state") == "RUNNING":
                        logger.info(f"E-commerce plugin active: {plugin_name}")
                except Exception as e:
                    logger.warning(f"Failed to initialize e-commerce plugin {plugin_name}: {e}")
            
        except Exception as e:
            logger.error(f"Error initializing domain plugins: {e}")
    
    async def _setup_business_rules(self):
        """Setup business rule enforcement"""
        try:
            # Subscribe to events that require business rule validation
            await self.event_bus.subscribe("ecommerce.order.pre_create", self._enforce_order_rules)
            await self.event_bus.subscribe("ecommerce.payment.pre_process", self._enforce_payment_rules)
            
            logger.info("Business rule enforcement configured")
            
        except Exception as e:
            logger.error(f"Error setting up business rules: {e}")
    
    # Event handlers
    
    async def _handle_shipment_created(self, event_type: str, event_data: Dict[str, Any]):
        """Handle shipment creation from logistics domain"""
        try:
            order_id = event_data.get("order_id")
            tracking_number = event_data.get("tracking_number")
            
            if order_id and tracking_number:
                # Update order with tracking information
                order = await self.order_service.get_order(order_id)
                if order:
                    order.tracking_number = tracking_number
                    await self.order_service.update_order_status(order_id, "shipped")
                    
                    logger.info(f"Order {order.order_number} marked as shipped with tracking {tracking_number}")
                    
        except Exception as e:
            logger.error(f"Error handling shipment created event: {e}")
    
    async def _handle_delivery_completed(self, event_type: str, event_data: Dict[str, Any]):
        """Handle delivery completion from logistics domain"""
        try:
            order_id = event_data.get("order_id")
            
            if order_id:
                await self.order_service.update_order_status(order_id, "delivered")
                
                order = await self.order_service.get_order(order_id)
                if order:
                    logger.info(f"Order {order.order_number} marked as delivered")
                    
        except Exception as e:
            logger.error(f"Error handling delivery completed event: {e}")
    
    async def _handle_low_stock(self, event_type: str, event_data: Dict[str, Any]):
        """Handle low stock alert"""
        try:
            product_id = event_data.get("product_id")
            if product_id:
                await self.handle_inventory_alert(product_id)
                
        except Exception as e:
            logger.error(f"Error handling low stock event: {e}")
    
    async def _handle_order_created(self, event_type: str, event_data: Dict[str, Any]):
        """Handle order creation"""
        try:
            order_id = event_data.get("order_id")
            if order_id:
                # Trigger fulfillment workflow
                await self.process_order_fulfillment(order_id)
                
        except Exception as e:
            logger.error(f"Error handling order created event: {e}")
    
    async def _handle_payment_completed(self, event_type: str, event_data: Dict[str, Any]):
        """Handle payment completion"""
        try:
            order_id = event_data.get("order_id")
            if order_id:
                # Order already updated to confirmed in PaymentService
                logger.info(f"Payment completed for order {order_id}")
                
        except Exception as e:
            logger.error(f"Error handling payment completed event: {e}")
    
    async def _handle_customer_created(self, event_type: str, event_data: Dict[str, Any]):
        """Handle customer creation"""
        try:
            customer_id = event_data.get("customer_id")
            if customer_id:
                # Award welcome bonus points
                await self.customer_service.update_customer_loyalty_points(customer_id, 50)
                logger.info(f"Welcome bonus awarded to customer {customer_id}")
                
        except Exception as e:
            logger.error(f"Error handling customer created event: {e}")
    
    async def _enforce_order_rules(self, event_type: str, event_data: Dict[str, Any]):
        """Enforce business rules for orders"""
        try:
            # Implement order validation rules
            order_data = event_data.get("order_data", {})
            
            # Example rule: Minimum order value
            min_value_rule = next((r for r in self.business_rules if r["id"] == "min_order_value"), None)
            if min_value_rule and min_value_rule["active"]:
                total_amount = order_data.get("total_amount", 0)
                min_value = min_value_rule["parameters"]["min_value"]
                
                if total_amount < min_value:
                    logger.warning(f"Order below minimum value: {total_amount} < {min_value}")
                    # In a real implementation, this might raise an exception or modify the order
            
        except Exception as e:
            logger.error(f"Error enforcing order rules: {e}")
    
    async def _enforce_payment_rules(self, event_type: str, event_data: Dict[str, Any]):
        """Enforce business rules for payments"""
        try:
            # Implement payment validation rules
            payment_data = event_data.get("payment_data", {})
            
            # Example rule: Fraud detection
            fraud_rule = next((r for r in self.business_rules if r["id"] == "fraud_detection"), None)
            if fraud_rule and fraud_rule["active"]:
                risk_score = payment_data.get("risk_score", 0)
                max_risk = fraud_rule["parameters"]["max_risk_score"]
                
                if risk_score > max_risk:
                    logger.warning(f"High risk payment detected: {risk_score} > {max_risk}")
                    # In a real implementation, this might block the payment
            
        except Exception as e:
            logger.error(f"Error enforcing payment rules: {e}")
    
    def _get_timestamp(self):
        """Get current timestamp"""
        from datetime import datetime
        return datetime.utcnow().isoformat()