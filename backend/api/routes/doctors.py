"""
Doctor management and availability API endpoints.
"""
from typing import Optional, List
from datetime import date, time
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from pydantic import BaseModel, Field

from database import get_db
from models import Doctor, DoctorSchedule
from observability import get_logger

router = APIRouter()
logger = get_logger("doctors_api")


# ── Pydantic Schemas ──

class DoctorResponse(BaseModel):
    id: UUID
    first_name: str
    last_name: str
    specialization: str
    department: Optional[str]
    consultation_duration_minutes: int
    is_active: bool
    languages: Optional[List[str]]

    class Config:
        from_attributes = True


class ScheduleResponse(BaseModel):
    id: UUID
    day_of_week: int
    start_time: time
    end_time: time
    is_available: bool
    slot_duration_minutes: int

    class Config:
        from_attributes = True


class AvailableSlot(BaseModel):
    start_time: str
    end_time: str


# ── Endpoints ──

@router.get("", response_model=List[DoctorResponse])
async def list_doctors(
    specialization: Optional[str] = None,
    language: Optional[str] = None,
    active_only: bool = Query(True),
    db: AsyncSession = Depends(get_db),
):
    """
    List all doctors with optional filtering.
    
    - specialization: Filter by specialty (cardiologist, dermatologist, etc.)
    - language: Filter by spoken language (en, hi, te)
    - active_only: Only return active doctors
    """
    query = select(Doctor)
    
    if active_only:
        query = query.where(Doctor.is_active == True)
    
    if specialization:
        query = query.where(Doctor.specialization.ilike(f"%{specialization}%"))
    
    if language:
        query = query.where(Doctor.languages.contains([language]))
    
    result = await db.execute(query)
    doctors = result.scalars().all()
    
    return doctors


@router.get("/specializations")
async def list_specializations(db: AsyncSession = Depends(get_db)):
    """Get list of all available specializations."""
    result = await db.execute(
        select(Doctor.specialization)
        .where(Doctor.is_active == True)
        .distinct()
    )
    specializations = [row[0] for row in result.all()]
    return {"specializations": specializations}


@router.get("/{doctor_id}", response_model=DoctorResponse)
async def get_doctor(
    doctor_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get doctor by ID."""
    result = await db.execute(
        select(Doctor).where(Doctor.id == doctor_id)
    )
    doctor = result.scalar_one_or_none()
    
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")
    
    return doctor


@router.get("/{doctor_id}/schedule", response_model=List[ScheduleResponse])
async def get_doctor_schedule(
    doctor_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get doctor's weekly schedule."""
    result = await db.execute(
        select(DoctorSchedule)
        .where(DoctorSchedule.doctor_id == doctor_id)
        .order_by(DoctorSchedule.day_of_week, DoctorSchedule.start_time)
    )
    schedules = result.scalars().all()
    
    return schedules


@router.get("/{doctor_id}/availability/{target_date}")
async def get_doctor_availability(
    doctor_id: UUID,
    target_date: date,
    db: AsyncSession = Depends(get_db),
):
    """
    Get available appointment slots for a doctor on a specific date.
    Returns list of available time slots based on schedule and existing appointments.
    """
    from scheduler.appointment_engine import appointment_engine
    
    # Verify doctor exists
    result = await db.execute(
        select(Doctor).where(Doctor.id == doctor_id)
    )
    doctor = result.scalar_one_or_none()
    
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")
    
    # Get available slots
    slots = await appointment_engine.get_available_slots(
        db, str(doctor_id), target_date
    )
    
    return {
        "doctor_id": str(doctor_id),
        "doctor_name": f"Dr. {doctor.first_name} {doctor.last_name}",
        "date": str(target_date),
        "available_slots": [
            {
                "start_time": slot["start_time"].strftime("%H:%M"),
                "end_time": slot["end_time"].strftime("%H:%M"),
            }
            for slot in slots
        ],
        "slot_count": len(slots),
    }


@router.get("/search/by-specialty/{specialty}")
async def search_doctors_by_specialty(
    specialty: str,
    language: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Search for doctors by specialty name.
    Supports partial matching (e.g., "cardio" matches "cardiologist").
    """
    query = select(Doctor).where(
        and_(
            Doctor.is_active == True,
            Doctor.specialization.ilike(f"%{specialty}%"),
        )
    )
    
    if language:
        query = query.where(Doctor.languages.contains([language]))
    
    result = await db.execute(query)
    doctors = result.scalars().all()
    
    return {
        "specialty_search": specialty,
        "doctors": [
            {
                "id": str(d.id),
                "name": f"Dr. {d.first_name} {d.last_name}",
                "specialization": d.specialization,
                "department": d.department,
                "languages": d.languages,
                "consultation_minutes": d.consultation_duration_minutes,
            }
            for d in doctors
        ],
    }
