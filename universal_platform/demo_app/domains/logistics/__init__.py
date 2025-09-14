"""
Logistics Domain

This domain provides logistics and supply chain management including:
- Shipment tracking
- Inventory management
- Warehouse operations
- Delivery scheduling
- Route optimization
- Supplier management
"""

from .router import LogisticsRouter
from .domain import LogisticsDomain

__all__ = ["LogisticsRouter", "LogisticsDomain"]