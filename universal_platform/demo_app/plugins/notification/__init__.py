"""
Notification Plugin

This plugin provides notification services across all domains
"""

import logging
from typing import Dict, Any, List
from datetime import datetime

from ...core.plugins import PluginInterface, plugin_metadata, lifecycle_hook, HookType
from ...core.events import EventBus

logger = logging.getLogger(__name__)


@plugin_metadata(
    name="notification_plugin",
    version="1.0.0",
    description="Cross-domain notification service plugin",
    author="Universal Platform Team",
    dependencies=[]
)
class NotificationPlugin(PluginInterface):
    """Notification plugin for sending alerts and messages across domains"""
    
    def __init__(self):
        self.event_bus = None
        self.notification_queue = []
        self.notification_history = []
        self.notification_preferences = {}
    
    @lifecycle_hook(HookType.INITIALIZE)
    async def initialize(self, context=None):
        """Initialize the notification plugin"""
        try:
            self.event_bus = context.get("event_bus") if context else None
            
            if self.event_bus:
                # Subscribe to important events that need notifications
                await self.event_bus.subscribe("ecommerce.order.created", self._handle_order_notification)
                await self.event_bus.subscribe("ecommerce.payment.failed", self._handle_payment_failed)
                await self.event_bus.subscribe("ecommerce.inventory.low_stock", self._handle_low_stock)
                await self.event_bus.subscribe("healthcare.appointment.scheduled", self._handle_appointment_notification)
                await self.event_bus.subscribe("logistics.shipment.created", self._handle_shipment_notification)
                await self.event_bus.subscribe("logistics.delivery.completed", self._handle_delivery_notification)
                await self.event_bus.subscribe("system.error", self._handle_system_error)
            
            logger.info("Notification plugin initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize notification plugin: {e}")
            raise
    
    @lifecycle_hook(HookType.START)
    async def start(self):
        """Start the notification plugin"""
        try:
            logger.info("Notification plugin started - monitoring for notification events")
            
        except Exception as e:
            logger.error(f"Failed to start notification plugin: {e}")
            raise
    
    @lifecycle_hook(HookType.STOP)
    async def stop(self):
        """Stop the notification plugin"""
        try:
            logger.info("Notification plugin stopped")
            
        except Exception as e:
            logger.error(f"Error stopping notification plugin: {e}")
    
    @lifecycle_hook(HookType.DESTROY)
    async def destroy(self):
        """Destroy the notification plugin"""
        try:
            self.notification_queue.clear()
            self.notification_history.clear()
            logger.info("Notification plugin destroyed")
            
        except Exception as e:
            logger.error(f"Error destroying notification plugin: {e}")
    
    async def send_notification(
        self,
        recipient: str,
        message: str,
        notification_type: str = "info",
        channel: str = "email",
        metadata: Dict[str, Any] = None
    ):
        """Send a notification"""
        try:
            notification = {
                "id": f"notif_{len(self.notification_history) + 1:06d}",
                "recipient": recipient,
                "message": message,
                "type": notification_type,
                "channel": channel,
                "metadata": metadata or {},
                "created_at": datetime.utcnow().isoformat(),
                "status": "sent"
            }
            
            # Add to queue for processing
            self.notification_queue.append(notification)
            
            # Process notification (simplified - in real implementation would use actual services)
            await self._process_notification(notification)
            
            # Add to history
            self.notification_history.append(notification)
            
            logger.info(f"Notification sent: {notification_type} to {recipient}")
            
        except Exception as e:
            logger.error(f"Error sending notification: {e}")
    
    async def _process_notification(self, notification: Dict[str, Any]):
        """Process notification (simulate sending)"""
        try:
            channel = notification["channel"]
            
            if channel == "email":
                # Simulate email sending
                logger.info(f"📧 EMAIL: {notification['message']} -> {notification['recipient']}")
            elif channel == "sms":
                # Simulate SMS sending
                logger.info(f"📱 SMS: {notification['message']} -> {notification['recipient']}")
            elif channel == "push":
                # Simulate push notification
                logger.info(f"🔔 PUSH: {notification['message']} -> {notification['recipient']}")
            elif channel == "webhook":
                # Simulate webhook call
                logger.info(f"🔗 WEBHOOK: {notification['message']} -> {notification['recipient']}")
            
            notification["status"] = "delivered"
            notification["delivered_at"] = datetime.utcnow().isoformat()
            
        except Exception as e:
            logger.error(f"Error processing notification: {e}")
            notification["status"] = "failed"
            notification["error"] = str(e)
    
    # Event handlers for different notification scenarios
    
    async def _handle_order_notification(self, event_type: str, event_data: Dict[str, Any]):
        """Handle order creation notification"""
        try:
            order_id = event_data.get("order_id")
            customer_id = event_data.get("customer_id")
            total_amount = event_data.get("total_amount", 0)
            
            await self.send_notification(
                recipient=f"customer_{customer_id}",
                message=f"Your order {order_id} has been created successfully. Total: ${total_amount:.2f}",
                notification_type="order_confirmation",
                channel="email",
                metadata={"order_id": order_id, "amount": total_amount}
            )
            
        except Exception as e:
            logger.error(f"Error handling order notification: {e}")
    
    async def _handle_payment_failed(self, event_type: str, event_data: Dict[str, Any]):
        """Handle payment failure notification"""
        try:
            payment_id = event_data.get("payment_id")
            order_id = event_data.get("order_id")
            
            await self.send_notification(
                recipient="admin",
                message=f"Payment failed for order {order_id}. Payment ID: {payment_id}",
                notification_type="payment_failure",
                channel="email",
                metadata={"payment_id": payment_id, "order_id": order_id}
            )
            
        except Exception as e:
            logger.error(f"Error handling payment failure notification: {e}")
    
    async def _handle_low_stock(self, event_type: str, event_data: Dict[str, Any]):
        """Handle low stock notification"""
        try:
            product_id = event_data.get("product_id")
            sku = event_data.get("sku")
            current_quantity = event_data.get("current_quantity", 0)
            
            await self.send_notification(
                recipient="inventory_manager",
                message=f"Low stock alert: Product {sku} has only {current_quantity} units remaining",
                notification_type="inventory_alert",
                channel="email",
                metadata={"product_id": product_id, "sku": sku, "quantity": current_quantity}
            )
            
        except Exception as e:
            logger.error(f"Error handling low stock notification: {e}")
    
    async def _handle_appointment_notification(self, event_type: str, event_data: Dict[str, Any]):
        """Handle appointment notification"""
        try:
            appointment_id = event_data.get("appointment_id")
            patient_name = event_data.get("patient_name", "Patient")
            
            await self.send_notification(
                recipient=f"patient_{appointment_id}",
                message=f"Appointment scheduled for {patient_name}. Please check your healthcare portal for details.",
                notification_type="appointment_reminder",
                channel="email",
                metadata={"appointment_id": appointment_id}
            )
            
        except Exception as e:
            logger.error(f"Error handling appointment notification: {e}")
    
    async def _handle_shipment_notification(self, event_type: str, event_data: Dict[str, Any]):
        """Handle shipment creation notification"""
        try:
            tracking_number = event_data.get("tracking_number")
            order_id = event_data.get("order_id")
            
            await self.send_notification(
                recipient=f"order_{order_id}",
                message=f"Your order has been shipped! Tracking number: {tracking_number}",
                notification_type="shipment_update",
                channel="email",
                metadata={"tracking_number": tracking_number, "order_id": order_id}
            )
            
        except Exception as e:
            logger.error(f"Error handling shipment notification: {e}")
    
    async def _handle_delivery_notification(self, event_type: str, event_data: Dict[str, Any]):
        """Handle delivery completion notification"""
        try:
            order_id = event_data.get("order_id")
            
            await self.send_notification(
                recipient=f"order_{order_id}",
                message=f"Your order has been delivered successfully! Thank you for your business.",
                notification_type="delivery_confirmation",
                channel="email",
                metadata={"order_id": order_id}
            )
            
        except Exception as e:
            logger.error(f"Error handling delivery notification: {e}")
    
    async def _handle_system_error(self, event_type: str, event_data: Dict[str, Any]):
        """Handle system error notification"""
        try:
            error_message = event_data.get("message", "Unknown error")
            severity = event_data.get("severity", "error")
            
            if severity in ["critical", "error"]:
                await self.send_notification(
                    recipient="system_admin",
                    message=f"System {severity}: {error_message}",
                    notification_type="system_alert",
                    channel="email",
                    metadata={"severity": severity, "error": error_message}
                )
            
        except Exception as e:
            logger.error(f"Error handling system error notification: {e}")
    
    async def get_notification_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get notification history"""
        return self.notification_history[-limit:]
    
    async def get_notification_stats(self) -> Dict[str, Any]:
        """Get notification statistics"""
        total_notifications = len(self.notification_history)
        
        types_count = {}
        channels_count = {}
        status_count = {}
        
        for notif in self.notification_history:
            notif_type = notif.get("type", "unknown")
            channel = notif.get("channel", "unknown")
            status = notif.get("status", "unknown")
            
            types_count[notif_type] = types_count.get(notif_type, 0) + 1
            channels_count[channel] = channels_count.get(channel, 0) + 1
            status_count[status] = status_count.get(status, 0) + 1
        
        return {
            "total_notifications": total_notifications,
            "notifications_by_type": types_count,
            "notifications_by_channel": channels_count,
            "notifications_by_status": status_count,
            "queue_size": len(self.notification_queue)
        }


# Plugin instance for loading
plugin_instance = NotificationPlugin()