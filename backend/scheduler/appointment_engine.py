"""
Appointment Scheduling Engine.
Handles booking, rescheduling, cancellation with conflict detection.
"""
import uuid
from datetime import date, time, datetime, timedelta
from typing import Optional
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from models import (
    Appointment, AppointmentStatus,
    Doctor, DoctorSchedule, Patient,
)
from observability import get_logger

logger = get_logger("appointment_engine")


class AppointmentEngine:
    """
    Appointment scheduling engine with:
    - Double-booking prevention
    - Past-time validation
    - Doctor availability checking
    - Alternative slot suggestions
    """

    async def check_availability(
        self,
        db: AsyncSession,
        doctor_id: str,
        target_date: date,
        start_time: time,
    ) -> bool:
        """
        Check if a specific time slot is available for a doctor.
        
        Rules:
        1. Date must not be in the past
        2. Doctor must have schedule for that day/time
        3. No conflicting appointments
        """
        # Rule 1: Check if date is in the past
        today = date.today()
        if target_date < today:
            logger.debug("past_date_rejected", date=str(target_date))
            return False
        
        if target_date == today and start_time < datetime.now().time():
            logger.debug("past_time_rejected", time=str(start_time))
            return False
        
        # Rule 2: Check doctor schedule
        day_of_week = target_date.weekday()  # 0 = Monday
        
        schedule_query = select(DoctorSchedule).where(
            and_(
                DoctorSchedule.doctor_id == uuid.UUID(doctor_id),
                DoctorSchedule.day_of_week == day_of_week,
                DoctorSchedule.is_available == True,
                DoctorSchedule.start_time <= start_time,
                DoctorSchedule.end_time > start_time,
            )
        ).limit(1)
        
        schedule_result = await db.execute(schedule_query)
        schedule = schedule_result.scalars().first()
        
        if not schedule:
            logger.debug(
                "no_schedule_found",
                doctor_id=doctor_id,
                day=day_of_week,
            )
            return False
        
        # Calculate end time based on slot duration
        end_time = self._add_minutes_to_time(start_time, schedule.slot_duration_minutes)
        
        # Rule 3: Check for conflicting appointments (exclude cancelled/rescheduled)
        conflict_query = select(Appointment).where(
            and_(
                Appointment.doctor_id == uuid.UUID(doctor_id),
                Appointment.appointment_date == target_date,
                # Exclude cancelled and rescheduled appointments using != 
                Appointment.status != AppointmentStatus.CANCELLED,
                Appointment.status != AppointmentStatus.RESCHEDULED,
                or_(
                    # New appointment starts during existing
                    and_(
                        Appointment.start_time <= start_time,
                        Appointment.end_time > start_time,
                    ),
                    # New appointment ends during existing
                    and_(
                        Appointment.start_time < end_time,
                        Appointment.end_time >= end_time,
                    ),
                    # New appointment contains existing
                    and_(
                        Appointment.start_time >= start_time,
                        Appointment.end_time <= end_time,
                    ),
                ),
            )
        )
        
        conflict_result = await db.execute(conflict_query)
        conflicts = conflict_result.scalars().all()
        
        if conflicts:
            logger.debug(
                "slot_conflict_detected",
                doctor_id=doctor_id,
                date=str(target_date),
                time=str(start_time),
                conflicts=len(conflicts),
            )
            return False
        
        return True

    async def get_available_slots(
        self,
        db: AsyncSession,
        doctor_id: str,
        target_date: date,
    ) -> list[dict]:
        """
        Get all available time slots for a doctor on a specific date.
        """
        # Check if date is valid
        if target_date < date.today():
            return []
        
        # Get doctor's schedule for the day
        day_of_week = target_date.weekday()
        
        schedule_query = select(DoctorSchedule).where(
            and_(
                DoctorSchedule.doctor_id == uuid.UUID(doctor_id),
                DoctorSchedule.day_of_week == day_of_week,
                DoctorSchedule.is_available == True,
            )
        ).order_by(DoctorSchedule.start_time)
        
        schedule_result = await db.execute(schedule_query)
        schedules = schedule_result.scalars().all()
        
        if not schedules:
            return []
        
        # Get existing appointments
        appointments_query = select(Appointment).where(
            and_(
                Appointment.doctor_id == uuid.UUID(doctor_id),
                Appointment.appointment_date == target_date,
                Appointment.status != AppointmentStatus.CANCELLED,
                Appointment.status != AppointmentStatus.RESCHEDULED,
            )
        ).order_by(Appointment.start_time)
        
        appointments_result = await db.execute(appointments_query)
        existing_appointments = appointments_result.scalars().all()
        
        # Build list of booked slots
        booked_slots = set()
        for apt in existing_appointments:
            booked_slots.add((apt.start_time, apt.end_time))
        
        # Generate available slots
        available_slots = []
        
        for schedule in schedules:
            slot_duration = schedule.slot_duration_minutes
            current_time = schedule.start_time
            
            # If today, skip past slots
            if target_date == date.today():
                now = datetime.now().time()
                while current_time < now:
                    current_time = self._add_minutes_to_time(current_time, slot_duration)
            
            while current_time < schedule.end_time:
                end_time = self._add_minutes_to_time(current_time, slot_duration)
                
                if end_time > schedule.end_time:
                    break
                
                # Check if slot is available
                is_available = True
                for booked_start, booked_end in booked_slots:
                    if not (end_time <= booked_start or current_time >= booked_end):
                        is_available = False
                        break
                
                if is_available:
                    available_slots.append({
                        "start_time": current_time,
                        "end_time": end_time,
                    })
                
                current_time = end_time
        
        return available_slots

    async def book_appointment(
        self,
        db: AsyncSession,
        patient_id: str,
        doctor_id: str,
        appointment_date: date,
        start_time: time,
        reason: Optional[str] = None,
        language: str = "en",
    ) -> dict:
        """
        Book a new appointment with validation.
        """
        # Verify patient exists
        patient_result = await db.execute(
            select(Patient).where(Patient.id == uuid.UUID(patient_id))
        )
        patient = patient_result.scalar_one_or_none()
        
        if not patient:
            return {"success": False, "error": "Patient not found"}
        
        # Verify doctor exists and is active
        doctor_result = await db.execute(
            select(Doctor).where(
                and_(
                    Doctor.id == uuid.UUID(doctor_id),
                    Doctor.is_active == True,
                )
            )
        )
        doctor = doctor_result.scalar_one_or_none()
        
        if not doctor:
            return {"success": False, "error": "Doctor not found or not available"}
        
        # Check availability
        is_available = await self.check_availability(
            db, doctor_id, appointment_date, start_time
        )
        
        if not is_available:
            # Get alternative slots
            alternatives = await self.get_available_slots(db, doctor_id, appointment_date)
            
            return {
                "success": False,
                "error": "Requested slot is not available",
                "alternatives": [
                    {"time": s["start_time"].strftime("%H:%M")}
                    for s in alternatives[:5]
                ] if alternatives else [],
            }
        
        # Calculate end time
        end_time = self._add_minutes_to_time(
            start_time, doctor.consultation_duration_minutes
        )
        
        # Create appointment
        appointment = Appointment(
            patient_id=uuid.UUID(patient_id),
            doctor_id=uuid.UUID(doctor_id),
            appointment_date=appointment_date,
            start_time=start_time,
            end_time=end_time,
            status=AppointmentStatus.SCHEDULED,
            reason=reason,
            language_used=language,
            booking_source="voice_agent",
        )
        
        db.add(appointment)
        await db.flush()
        
        logger.info(
            "appointment_booked",
            appointment_id=str(appointment.id),
            patient_id=patient_id,
            doctor_id=doctor_id,
            date=str(appointment_date),
            time=str(start_time),
        )
        
        return {
            "success": True,
            "appointment": appointment,
            "doctor_name": f"Dr. {doctor.first_name} {doctor.last_name}",
        }

    async def cancel_appointment(
        self,
        db: AsyncSession,
        appointment_id: str,
        reason: Optional[str] = None,
    ) -> dict:
        """
        Cancel an existing appointment.
        """
        result = await db.execute(
            select(Appointment).where(Appointment.id == uuid.UUID(appointment_id))
        )
        appointment = result.scalar_one_or_none()
        
        if not appointment:
            return {"success": False, "error": "Appointment not found"}
        
        if appointment.status in [
            AppointmentStatus.CANCELLED,
            AppointmentStatus.COMPLETED,
        ]:
            return {
                "success": False,
                "error": f"Cannot cancel appointment with status: {appointment.status}",
            }
        
        # Update appointment
        appointment.status = AppointmentStatus.CANCELLED
        appointment.cancelled_at = datetime.utcnow()
        appointment.cancellation_reason = reason
        
        await db.flush()
        
        logger.info(
            "appointment_cancelled",
            appointment_id=appointment_id,
            reason=reason,
        )
        
        return {
            "success": True,
            "message": "Appointment cancelled successfully",
            "appointment_id": appointment_id,
        }

    async def reschedule_appointment(
        self,
        db: AsyncSession,
        appointment_id: str,
        new_date: date,
        new_time: time,
    ) -> dict:
        """
        Reschedule an appointment to a new date/time.
        """
        result = await db.execute(
            select(Appointment).where(Appointment.id == uuid.UUID(appointment_id))
        )
        old_appointment = result.scalar_one_or_none()
        
        if not old_appointment:
            return {"success": False, "error": "Appointment not found"}
        
        if old_appointment.status in [
            AppointmentStatus.CANCELLED,
            AppointmentStatus.COMPLETED,
            AppointmentStatus.NO_SHOW,
        ]:
            return {
                "success": False,
                "error": f"Cannot reschedule appointment with status: {old_appointment.status}",
            }
        
        # Check new slot availability
        is_available = await self.check_availability(
            db, str(old_appointment.doctor_id), new_date, new_time
        )
        
        if not is_available:
            alternatives = await self.get_available_slots(
                db, str(old_appointment.doctor_id), new_date
            )
            
            return {
                "success": False,
                "error": "Requested slot is not available",
                "alternatives": [
                    {"time": s["start_time"].strftime("%H:%M")}
                    for s in alternatives[:5]
                ] if alternatives else [],
            }
        
        # Get doctor for duration
        doctor_result = await db.execute(
            select(Doctor).where(Doctor.id == old_appointment.doctor_id)
        )
        doctor = doctor_result.scalar_one_or_none()
        
        duration = doctor.consultation_duration_minutes if doctor else 30
        new_end_time = self._add_minutes_to_time(new_time, duration)
        
        # Mark old appointment as rescheduled
        old_appointment.status = AppointmentStatus.RESCHEDULED
        
        # Create new appointment
        new_appointment = Appointment(
            patient_id=old_appointment.patient_id,
            doctor_id=old_appointment.doctor_id,
            appointment_date=new_date,
            start_time=new_time,
            end_time=new_end_time,
            status=AppointmentStatus.SCHEDULED,
            reason=old_appointment.reason,
            language_used=old_appointment.language_used,
            booking_source="voice_agent",
            rescheduled_from=old_appointment.id,
        )
        
        db.add(new_appointment)
        await db.flush()
        
        logger.info(
            "appointment_rescheduled",
            old_appointment_id=appointment_id,
            new_appointment_id=str(new_appointment.id),
            new_date=str(new_date),
            new_time=str(new_time),
        )
        
        return {
            "success": True,
            "appointment": new_appointment,
            "old_appointment_id": appointment_id,
            "message": "Appointment rescheduled successfully",
        }

    async def suggest_alternative_slots(
        self,
        db: AsyncSession,
        doctor_id: str,
        target_date: date,
        preferred_time: Optional[time] = None,
        days_ahead: int = 7,
    ) -> list[dict]:
        """
        Suggest alternative appointment slots.
        Looks ahead multiple days if nothing available on target date.
        """
        suggestions = []
        
        for day_offset in range(days_ahead + 1):
            check_date = target_date + timedelta(days=day_offset)
            
            # Skip past dates
            if check_date < date.today():
                continue
            
            slots = await self.get_available_slots(db, doctor_id, check_date)
            
            if slots:
                # Sort by closeness to preferred time if specified
                if preferred_time:
                    slots.sort(
                        key=lambda s: abs(
                            self._time_to_minutes(s["start_time"]) -
                            self._time_to_minutes(preferred_time)
                        )
                    )
                
                for slot in slots[:3]:  # Top 3 for each day
                    suggestions.append({
                        "date": str(check_date),
                        "start_time": slot["start_time"].strftime("%H:%M"),
                        "end_time": slot["end_time"].strftime("%H:%M"),
                    })
            
            if len(suggestions) >= 10:
                break
        
        return suggestions

    @staticmethod
    def _add_minutes_to_time(t: time, minutes: int) -> time:
        """Add minutes to a time object."""
        dt = datetime.combine(date.today(), t)
        dt += timedelta(minutes=minutes)
        return dt.time()

    @staticmethod
    def _time_to_minutes(t: time) -> int:
        """Convert time to minutes since midnight."""
        return t.hour * 60 + t.minute


# Singleton instance
appointment_engine = AppointmentEngine()
