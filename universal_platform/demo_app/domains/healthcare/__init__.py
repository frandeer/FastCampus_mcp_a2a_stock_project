"""
Healthcare Domain

This domain provides healthcare management including:
- Patient management
- Appointment scheduling  
- Medical records
- Provider management
- Insurance processing
- Billing and claims
"""

from .router import HealthcareRouter
from .domain import HealthcareDomain

__all__ = ["HealthcareRouter", "HealthcareDomain"]