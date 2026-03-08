"""
Appointment management API endpoints.
"""
from typing import Optional
from datetime import date, time, datetime
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from pydantic import BaseModel, Field

from database import get_db
from models import Appointment, AppointmentStatus, Patient, Doctor
from observability import get_logger

router = APIRouter()
logger = get_logger("appointments_api")


# ── Pydantic Schemas ──

class AppointmentCreate(BaseModel):
    patient_id: UUID
    doctor_id: UUID
    appointment_date: date
    start_time: time
    reason: Optional[str] = None
    language_used: Optional[str] = Field(default="en", pattern=r"^(en|hi|ta)$")


class AppointmentReschedule(BaseModel):
    new_date: date
    new_time: time


class AppointmentResponse(BaseModel):
    id: UUID
    patient_id: UUID
    doctor_id: UUID
    appointment_date: date
    start_time: time
    end_time: time
    status: str
    reason: Optional[str]
    notes: Optional[str]
    language_used: Optional[str]
    booking_source: str
    created_at: datetime

    class Config:
        from_attributes = True


# ── Endpoints ──

@router.get("", response_model=list[AppointmentResponse])
async def list_appointments(
    patient_id: Optional[UUID] = None,
    doctor_id: Optional[UUID] = None,
    status: Optional[AppointmentStatus] = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """
    List appointments with optional filtering.
    """
    query = select(Appointment).order_by(Appointment.appointment_date.desc())
    
    if patient_id:
        query = query.where(Appointment.patient_id == patient_id)
    if doctor_id:
        query = query.where(Appointment.doctor_id == doctor_id)
    if status:
        query = query.where(Appointment.status == status)
    
    query = query.offset(offset).limit(limit)
    
    result = await db.execute(query)
    appointments = result.scalars().all()
    return appointments


@router.post("", response_model=AppointmentResponse, status_code=201)
async def create_appointment(
    appointment_data: AppointmentCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new appointment.
    Validates slot availability and prevents double booking.
    """
    from scheduler.appointment_engine import appointment_engine
    
    result = await appointment_engine.book_appointment(
        db=db,
        patient_id=str(appointment_data.patient_id),
        doctor_id=str(appointment_data.doctor_id),
        appointment_date=appointment_data.appointment_date,
        start_time=appointment_data.start_time,
        reason=appointment_data.reason,
        language=appointment_data.language_used,
    )
    
    if not result["success"]:
        raise HTTPException(
            status_code=409,
            detail=result.get("error", "Unable to book appointment"),
        )
    
    return result["appointment"]


@router.get("/{appointment_id}", response_model=AppointmentResponse)
async def get_appointment(
    appointment_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get appointment by ID."""
    result = await db.execute(
        select(Appointment).where(Appointment.id == appointment_id)
    )
    appointment = result.scalar_one_or_none()
    
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    
    return appointment


@router.post("/{appointment_id}/cancel")
async def cancel_appointment(
    appointment_id: UUID,
    reason: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Cancel an appointment."""
    from scheduler.appointment_engine import appointment_engine
    
    result = await appointment_engine.cancel_appointment(
        db=db,
        appointment_id=str(appointment_id),
        reason=reason,
    )
    
    if not result["success"]:
        raise HTTPException(
            status_code=400,
            detail=result.get("error", "Unable to cancel appointment"),
        )
    
    return result


@router.post("/{appointment_id}/reschedule", response_model=AppointmentResponse)
async def reschedule_appointment(
    appointment_id: UUID,
    reschedule_data: AppointmentReschedule,
    db: AsyncSession = Depends(get_db),
):
    """Reschedule an appointment to a new date/time."""
    from scheduler.appointment_engine import appointment_engine
    
    result = await appointment_engine.reschedule_appointment(
        db=db,
        appointment_id=str(appointment_id),
        new_date=reschedule_data.new_date,
        new_time=reschedule_data.new_time,
    )
    
    if not result["success"]:
        if "alternatives" in result:
            raise HTTPException(
                status_code=409,
                detail={
                    "error": result.get("error"),
                    "alternatives": result["alternatives"],
                },
            )
        raise HTTPException(
            status_code=400,
            detail=result.get("error", "Unable to reschedule appointment"),
        )
    
    return result["appointment"]


@router.post("/{appointment_id}/confirm")
async def confirm_appointment(
    appointment_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Confirm a scheduled appointment."""
    result = await db.execute(
        select(Appointment).where(Appointment.id == appointment_id)
    )
    appointment = result.scalar_one_or_none()
    
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    
    if appointment.status != AppointmentStatus.SCHEDULED:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot confirm appointment with status: {appointment.status}",
        )
    
    appointment.status = AppointmentStatus.CONFIRMED
    await db.flush()
    
    logger.info("appointment_confirmed", appointment_id=str(appointment_id))
    
    return {
        "appointment_id": str(appointment_id),
        "status": "confirmed",
    }


@router.get("/doctor/{doctor_id}/date/{target_date}")
async def get_doctor_appointments(
    doctor_id: UUID,
    target_date: date,
    db: AsyncSession = Depends(get_db),
):
    """Get all appointments for a doctor on a specific date."""
    result = await db.execute(
        select(Appointment).where(
            and_(
                Appointment.doctor_id == doctor_id,
                Appointment.appointment_date == target_date,
                Appointment.status != AppointmentStatus.CANCELLED,
                Appointment.status != AppointmentStatus.RESCHEDULED,
            )
        ).order_by(Appointment.start_time)
    )
    appointments = result.scalars().all()
    
    return {
        "doctor_id": str(doctor_id),
        "date": str(target_date),
        "appointments": [
            {
                "id": str(apt.id),
                "patient_id": str(apt.patient_id),
                "start_time": str(apt.start_time),
                "end_time": str(apt.end_time),
                "status": apt.status,
                "reason": apt.reason,
            }
            for apt in appointments
        ],
    }


@router.get("/check-availability")
async def check_slot_availability(
    doctor_id: UUID,
    target_date: date,
    start_time: time,
    db: AsyncSession = Depends(get_db),
):
    """Check if a specific time slot is available."""
    from scheduler.appointment_engine import appointment_engine
    
    is_available = await appointment_engine.check_availability(
        db=db,
        doctor_id=str(doctor_id),
        target_date=target_date,
        start_time=start_time,
    )
    
    return {
        "doctor_id": str(doctor_id),
        "date": str(target_date),
        "time": str(start_time),
        "available": is_available,
    }
