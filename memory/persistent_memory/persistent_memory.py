"""
Persistent memory layer backed by PostgreSQL.
Handles patient profiles, language preferences, and appointment history.
"""
import uuid
from datetime import date, datetime
from typing import Optional
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

# Import from backend - these imports work when running from the backend directory
# or when backend is in PYTHONPATH
try:
    from models import Patient, Appointment, AppointmentStatus
    from observability import get_logger
except ImportError:
    # Fallback for different execution contexts
    import sys
    import os
    backend_path = os.path.join(os.path.dirname(__file__), '..', '..', 'backend')
    if backend_path not in sys.path:
        sys.path.insert(0, backend_path)
    from models import Patient, Appointment, AppointmentStatus
    from observability import get_logger

logger = get_logger("persistent_memory")


class PersistentMemory:
    """
    Manages persistent patient data and appointment history in PostgreSQL.
    """

    # ── Patient operations ──

    async def get_patient_by_phone(
        self, db: AsyncSession, phone: str
    ) -> Optional[Patient]:
        result = await db.execute(
            select(Patient).where(Patient.phone == phone)
        )
        return result.scalar_one_or_none()

    async def get_patient_by_id(
        self, db: AsyncSession, patient_id: str
    ) -> Optional[Patient]:
        result = await db.execute(
            select(Patient).where(Patient.id == uuid.UUID(patient_id))
        )
        return result.scalar_one_or_none()

    async def create_patient(
        self,
        db: AsyncSession,
        first_name: str,
        last_name: str,
        phone: str,
        language: str = "en",
        **kwargs,
    ) -> Patient:
        patient = Patient(
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            preferred_language=language,
            **kwargs,
        )
        db.add(patient)
        await db.flush()
        logger.info(
            "patient_created",
            patient_id=str(patient.id),
            phone=phone,
        )
        return patient

    async def update_language_preference(
        self, db: AsyncSession, patient_id: str, language: str
    ):
        await db.execute(
            update(Patient)
            .where(Patient.id == uuid.UUID(patient_id))
            .values(preferred_language=language)
        )
        logger.info(
            "language_preference_updated",
            patient_id=patient_id,
            language=language,
        )

    async def get_patient_language(
        self, db: AsyncSession, patient_id: str
    ) -> str:
        result = await db.execute(
            select(Patient.preferred_language).where(
                Patient.id == uuid.UUID(patient_id)
            )
        )
        lang = result.scalar_one_or_none()
        return lang or "en"

    # ── Appointment history ──

    async def get_appointment_history(
        self,
        db: AsyncSession,
        patient_id: str,
        limit: int = 10,
    ) -> list[Appointment]:
        result = await db.execute(
            select(Appointment)
            .where(Appointment.patient_id == uuid.UUID(patient_id))
            .order_by(Appointment.appointment_date.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_upcoming_appointments(
        self,
        db: AsyncSession,
        patient_id: str,
    ) -> list[Appointment]:
        today = date.today()
        result = await db.execute(
            select(Appointment)
            .where(
                Appointment.patient_id == uuid.UUID(patient_id),
                Appointment.appointment_date >= today,
                Appointment.status.in_([
                    AppointmentStatus.SCHEDULED,
                    AppointmentStatus.CONFIRMED,
                ]),
            )
            .order_by(Appointment.appointment_date, Appointment.start_time)
        )
        return list(result.scalars().all())

    async def get_patient_preferences(
        self, db: AsyncSession, patient_id: str
    ) -> dict:
        result = await db.execute(
            select(Patient.preferences, Patient.preferred_language).where(
                Patient.id == uuid.UUID(patient_id)
            )
        )
        row = result.one_or_none()
        if row:
            prefs = row[0] or {}
            prefs["language"] = row[1]
            return prefs
        return {"language": "en"}


# Singleton
persistent_memory = PersistentMemory()
