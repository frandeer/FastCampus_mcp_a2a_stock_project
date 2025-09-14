"""
Healthcare domain orchestration (simplified implementation)
"""

import logging
from typing import Dict, Any
from datetime import datetime

from ...core.di import injectable, inject
from ...core.events import EventBus

logger = logging.getLogger(__name__)


@injectable
class HealthcareDomain:
    """Healthcare domain orchestrator (simplified demo implementation)"""
    
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.is_initialized = False
        
        # Demo data
        self.patients = {
            "patient-001": {
                "id": "patient-001",
                "name": "John Smith",
                "date_of_birth": "1985-06-15",
                "status": "active",
                "last_visit": "2024-01-15",
                "provider": "Dr. Johnson"
            },
            "patient-002": {
                "id": "patient-002",
                "name": "Mary Johnson", 
                "date_of_birth": "1978-12-03",
                "status": "active",
                "last_visit": "2024-01-10",
                "provider": "Dr. Smith"
            }
        }
        
        self.appointments = {}
        self.medical_supplies = {}
    
    async def initialize(self):
        """Initialize healthcare domain"""
        try:
            # Setup event subscriptions
            await self.event_bus.subscribe("healthcare.*", self._handle_healthcare_event)
            await self.event_bus.subscribe("ecommerce.order.delivered", self._handle_medical_supply_delivery)
            
            self.is_initialized = True
            
            await self.event_bus.publish("healthcare.domain.initialized", {
                "domain": "healthcare",
                "timestamp": datetime.utcnow().isoformat(),
                "patients_count": len(self.patients)
            })
            
            logger.info("Healthcare domain initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize healthcare domain: {e}")
            raise
    
    async def get_domain_status(self) -> Dict[str, Any]:
        """Get healthcare domain status"""
        return {
            "domain": "healthcare",
            "status": "active" if self.is_initialized else "inactive",
            "statistics": {
                "total_patients": len(self.patients),
                "total_appointments": len(self.appointments),
                "medical_supplies": len(self.medical_supplies)
            },
            "features": [
                "Patient management (demo)",
                "Appointment scheduling (demo)",
                "Medical records (demo)",
                "Cross-domain medical supply ordering"
            ]
        }
    
    async def order_medical_supplies(self, supply_data: Dict[str, Any]):
        """Order medical supplies through e-commerce integration"""
        try:
            # Create supply order event for e-commerce domain
            await self.event_bus.publish("healthcare.supply.order", {
                "supplier_type": "medical",
                "items": supply_data.get("items", []),
                "priority": supply_data.get("priority", "normal"),
                "delivery_address": supply_data.get("delivery_address"),
                "requesting_department": supply_data.get("department")
            })
            
            logger.info("Medical supply order initiated")
            
        except Exception as e:
            logger.error(f"Error ordering medical supplies: {e}")
            raise
    
    async def _handle_healthcare_event(self, event_type: str, event_data: Dict[str, Any]):
        """Handle healthcare domain events"""
        try:
            logger.info(f"Healthcare domain handling event: {event_type}")
            
            if event_type == "healthcare.appointment.scheduled":
                appointment_id = event_data.get("appointment_id")
                self.appointments[appointment_id] = event_data
                
        except Exception as e:
            logger.error(f"Error handling healthcare event: {e}")
    
    async def _handle_medical_supply_delivery(self, event_type: str, event_data: Dict[str, Any]):
        """Handle medical supply delivery from e-commerce"""
        try:
            # Check if this is a medical supply order
            items = event_data.get("items", [])
            medical_items = [item for item in items if "medical" in item.get("category", "").lower()]
            
            if medical_items:
                logger.info(f"Medical supplies delivered: {len(medical_items)} items")
                
                # Update inventory
                for item in medical_items:
                    supply_id = item.get("product_id")
                    if supply_id:
                        self.medical_supplies[supply_id] = {
                            "id": supply_id,
                            "name": item.get("product_name"),
                            "quantity_received": item.get("quantity"),
                            "delivery_date": datetime.utcnow().isoformat()
                        }
                
        except Exception as e:
            logger.error(f"Error handling medical supply delivery: {e}")