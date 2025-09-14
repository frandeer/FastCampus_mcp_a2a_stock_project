"""
Healthcare domain API router (simplified implementation)
"""

from fastapi import APIRouter
from ..shared.models import BaseResponse

HealthcareRouter = APIRouter()


@HealthcareRouter.get("/", tags=["Healthcare"])
async def healthcare_info():
    """Get healthcare domain information"""
    return BaseResponse(
        message="Healthcare domain information",
        data={
            "domain": "healthcare",
            "version": "1.0.0",
            "description": "Healthcare management system with patients, appointments, and records",
            "features": [
                "Patient management",
                "Appointment scheduling",
                "Medical records",
                "Provider management",
                "Insurance processing",
                "Billing and claims"
            ],
            "status": "demo_implementation",
            "endpoints": {
                "patients": "/patients",
                "appointments": "/appointments",
                "records": "/records",
                "providers": "/providers"
            }
        }
    )


@HealthcareRouter.get("/patients", tags=["Healthcare"])
async def list_patients():
    """List patients (demo endpoint)"""
    return BaseResponse(
        message="Patients retrieved successfully",
        data={
            "patients": [
                {
                    "id": "patient-001",
                    "name": "John Smith",
                    "date_of_birth": "1985-06-15",
                    "status": "active",
                    "last_visit": "2024-01-15",
                    "provider": "Dr. Johnson"
                },
                {
                    "id": "patient-002", 
                    "name": "Mary Johnson",
                    "date_of_birth": "1978-12-03",
                    "status": "active",
                    "last_visit": "2024-01-10",
                    "provider": "Dr. Smith"
                }
            ],
            "total": 2
        }
    )


@HealthcareRouter.get("/appointments", tags=["Healthcare"])
async def list_appointments():
    """List appointments (demo endpoint)"""
    return BaseResponse(
        message="Appointments retrieved successfully",
        data={
            "appointments": [
                {
                    "id": "appt-001",
                    "patient_id": "patient-001",
                    "patient_name": "John Smith",
                    "provider": "Dr. Johnson",
                    "date": "2024-01-20",
                    "time": "10:00",
                    "type": "checkup",
                    "status": "scheduled"
                },
                {
                    "id": "appt-002",
                    "patient_id": "patient-002", 
                    "patient_name": "Mary Johnson",
                    "provider": "Dr. Smith",
                    "date": "2024-01-22",
                    "time": "14:30",
                    "type": "consultation",
                    "status": "scheduled"
                }
            ],
            "total": 2
        }
    )


@HealthcareRouter.get("/records", tags=["Healthcare"])
async def list_medical_records():
    """List medical records (demo endpoint)"""
    return BaseResponse(
        message="Medical records retrieved successfully",
        data={
            "records": [
                {
                    "id": "record-001",
                    "patient_id": "patient-001",
                    "date": "2024-01-15",
                    "type": "visit_note",
                    "provider": "Dr. Johnson",
                    "diagnosis": "Annual physical examination",
                    "status": "completed"
                }
            ],
            "total": 1,
            "note": "Full medical records implementation would include HIPAA compliance and detailed medical data models"
        }
    )


@HealthcareRouter.get("/providers", tags=["Healthcare"])
async def list_providers():
    """List healthcare providers (demo endpoint)"""
    return BaseResponse(
        message="Providers retrieved successfully",
        data={
            "providers": [
                {
                    "id": "provider-001",
                    "name": "Dr. Johnson",
                    "specialty": "Family Medicine",
                    "status": "active",
                    "patients_count": 150
                },
                {
                    "id": "provider-002",
                    "name": "Dr. Smith", 
                    "specialty": "Internal Medicine",
                    "status": "active",
                    "patients_count": 200
                }
            ],
            "total": 2
        }
    )