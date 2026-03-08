"""
Patient management API endpoints.
"""
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field

from database import get_db
from models import Patient
from memory.persistent_memory.persistent_memory import persistent_memory
from observability import get_logger

router = APIRouter()
logger = get_logger("patients_api")


# ── Pydantic Schemas ──

class PatientCreate(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=128)
    last_name: str = Field(..., min_length=1, max_length=128)
    phone: str = Field(..., pattern=r"^\+?[0-9]{10,15}$")
    email: Optional[str] = None
    date_of_birth: Optional[str] = None
    gender: Optional[str] = None
    preferred_language: str = Field(default="en", pattern=r"^(en|hi|ta)$")


class PatientUpdate(BaseModel):
    first_name: Optional[str] = Field(None, min_length=1, max_length=128)
    last_name: Optional[str] = Field(None, min_length=1, max_length=128)
    email: Optional[str] = None
    preferred_language: Optional[str] = Field(None, pattern=r"^(en|hi|ta)$")
    preferences: Optional[dict] = None


class PatientResponse(BaseModel):
    id: UUID
    first_name: str
    last_name: str
    phone: str
    email: Optional[str]
    preferred_language: str
    preferences: Optional[dict]

    class Config:
        from_attributes = True


# ── Endpoints ──

@router.get("", response_model=list[PatientResponse])
async def list_patients(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """
    List all patients with pagination.
    """
    result = await db.execute(
        select(Patient)
        .order_by(Patient.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    patients = result.scalars().all()
    return patients


@router.post("", response_model=PatientResponse, status_code=201)
async def create_patient(
    patient_data: PatientCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new patient record."""
    # Check if phone already exists
    existing = await persistent_memory.get_patient_by_phone(db, patient_data.phone)
    if existing:
        raise HTTPException(
            status_code=409,
            detail="Patient with this phone number already exists",
        )
    
    patient = await persistent_memory.create_patient(
        db,
        first_name=patient_data.first_name,
        last_name=patient_data.last_name,
        phone=patient_data.phone,
        language=patient_data.preferred_language,
        email=patient_data.email,
        gender=patient_data.gender,
    )
    
    logger.info("patient_created_via_api", patient_id=str(patient.id))
    return patient


@router.get("/{patient_id}", response_model=PatientResponse)
async def get_patient(
    patient_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get patient by ID."""
    patient = await persistent_memory.get_patient_by_id(db, str(patient_id))
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    return patient


@router.get("/phone/{phone}", response_model=PatientResponse)
async def get_patient_by_phone(
    phone: str,
    db: AsyncSession = Depends(get_db),
):
    """Get patient by phone number."""
    patient = await persistent_memory.get_patient_by_phone(db, phone)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    return patient


@router.patch("/{patient_id}", response_model=PatientResponse)
async def update_patient(
    patient_id: UUID,
    updates: PatientUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update patient information."""
    patient = await persistent_memory.get_patient_by_id(db, str(patient_id))
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    
    update_data = updates.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(patient, key, value)
    
    await db.flush()
    logger.info("patient_updated", patient_id=str(patient_id), fields=list(update_data.keys()))
    return patient


@router.get("/{patient_id}/language")
async def get_patient_language(
    patient_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get patient's preferred language."""
    language = await persistent_memory.get_patient_language(db, str(patient_id))
    return {"patient_id": str(patient_id), "language": language}


@router.put("/{patient_id}/language")
async def update_patient_language(
    patient_id: UUID,
    language: str = Query(..., pattern=r"^(en|hi|ta)$"),
    db: AsyncSession = Depends(get_db),
):
    """Update patient's preferred language."""
    patient = await persistent_memory.get_patient_by_id(db, str(patient_id))
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    
    await persistent_memory.update_language_preference(db, str(patient_id), language)
    return {"patient_id": str(patient_id), "language": language}


@router.get("/{patient_id}/appointments")
async def get_patient_appointments(
    patient_id: UUID,
    upcoming_only: bool = Query(False),
    limit: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Get patient's appointment history or upcoming appointments."""
    patient = await persistent_memory.get_patient_by_id(db, str(patient_id))
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    
    if upcoming_only:
        appointments = await persistent_memory.get_upcoming_appointments(db, str(patient_id))
    else:
        appointments = await persistent_memory.get_appointment_history(db, str(patient_id), limit)
    
    return {
        "patient_id": str(patient_id),
        "appointments": [
            {
                "id": str(apt.id),
                "doctor_id": str(apt.doctor_id),
                "date": str(apt.appointment_date),
                "start_time": str(apt.start_time),
                "end_time": str(apt.end_time),
                "status": apt.status,
                "reason": apt.reason,
            }
            for apt in appointments
        ],
    }
