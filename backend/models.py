"""
SQLAlchemy ORM models for the clinical appointment booking system.
"""
import uuid
from datetime import date, time, datetime
from typing import Optional, List
from sqlalchemy import (
    String, Integer, Boolean, Date, Time, Text,
    ForeignKey, DateTime, JSON, Enum as SAEnum,
    UniqueConstraint, CheckConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from database import Base
import enum


# ── Enums ──

class AppointmentStatus(str, enum.Enum):
    SCHEDULED = "scheduled"
    CONFIRMED = "confirmed"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"
    RESCHEDULED = "rescheduled"


class CampaignType(str, enum.Enum):
    APPOINTMENT_REMINDER = "appointment_reminder"
    FOLLOW_UP_CHECKUP = "follow_up_checkup"
    VACCINATION_REMINDER = "vaccination_reminder"
    GENERAL_NOTIFICATION = "general_notification"


class CampaignStatus(str, enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TaskStatus(str, enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


# ── Models ──

class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    external_id: Mapped[Optional[str]] = mapped_column(String(64), unique=True)
    first_name: Mapped[str] = mapped_column(String(128))
    last_name: Mapped[str] = mapped_column(String(128))
    phone: Mapped[str] = mapped_column(String(20), unique=True)
    email: Mapped[Optional[str]] = mapped_column(String(255))
    date_of_birth: Mapped[Optional[date]] = mapped_column(Date)
    gender: Mapped[Optional[str]] = mapped_column(String(16))
    preferred_language: Mapped[str] = mapped_column(String(8), default="en")
    medical_record_number: Mapped[Optional[str]] = mapped_column(String(64), unique=True)
    preferences: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    appointments: Mapped[List["Appointment"]] = relationship(back_populates="patient")

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"


class Doctor(Base):
    __tablename__ = "doctors"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    first_name: Mapped[str] = mapped_column(String(128))
    last_name: Mapped[str] = mapped_column(String(128))
    specialization: Mapped[str] = mapped_column(String(128))
    department: Mapped[Optional[str]] = mapped_column(String(128))
    phone: Mapped[Optional[str]] = mapped_column(String(20))
    email: Mapped[Optional[str]] = mapped_column(String(255))
    consultation_duration_minutes: Mapped[int] = mapped_column(Integer, default=30)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    languages: Mapped[Optional[list]] = mapped_column(ARRAY(Text), default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    schedules: Mapped[List["DoctorSchedule"]] = relationship(back_populates="doctor")
    appointments: Mapped[List["Appointment"]] = relationship(back_populates="doctor")

    @property
    def full_name(self) -> str:
        return f"Dr. {self.first_name} {self.last_name}"


class DoctorSchedule(Base):
    __tablename__ = "doctor_schedule"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    doctor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("doctors.id", ondelete="CASCADE")
    )
    day_of_week: Mapped[int] = mapped_column(Integer)  # 0=Monday
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True)
    slot_duration_minutes: Mapped[int] = mapped_column(Integer, default=30)
    max_patients: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    doctor: Mapped["Doctor"] = relationship(back_populates="schedules")


class Appointment(Base):
    __tablename__ = "appointments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE")
    )
    doctor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("doctors.id", ondelete="CASCADE")
    )
    appointment_date: Mapped[date] = mapped_column(Date)
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)
    status: Mapped[str] = mapped_column(
        SAEnum(
            AppointmentStatus,
            name="appointment_status",
            values_callable=lambda x: [e.value for e in x],
        ),
        default=AppointmentStatus.SCHEDULED,
    )
    reason: Mapped[Optional[str]] = mapped_column(Text)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    language_used: Mapped[Optional[str]] = mapped_column(String(8))
    booking_source: Mapped[str] = mapped_column(String(32), default="voice_agent")
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    cancellation_reason: Mapped[Optional[str]] = mapped_column(Text)
    rescheduled_from: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("appointments.id")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    patient: Mapped["Patient"] = relationship(back_populates="appointments")
    doctor: Mapped["Doctor"] = relationship(back_populates="appointments")


class Campaign(Base):
    __tablename__ = "campaigns"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(256))
    campaign_type: Mapped[str] = mapped_column(
        SAEnum(CampaignType, name="campaign_type", native_enum=False, create_constraint=False, length=64, values_callable=lambda x: [e.value for e in x])
    )
    status: Mapped[str] = mapped_column(
        SAEnum(CampaignStatus, name="campaign_status", native_enum=False, create_constraint=False, length=32, values_callable=lambda x: [e.value for e in x]),
        default=CampaignStatus.DRAFT,
    )
    message_template: Mapped[dict] = mapped_column(JSON)
    target_criteria: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)
    scheduled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[Optional[str]] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    tasks: Mapped[List["CampaignTask"]] = relationship(back_populates="campaign")


class CampaignTask(Base):
    __tablename__ = "campaign_tasks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("campaigns.id", ondelete="CASCADE")
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE")
    )
    appointment_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("appointments.id")
    )
    status: Mapped[str] = mapped_column(
        SAEnum(TaskStatus, name="task_status", native_enum=False, create_constraint=False, length=32, values_callable=lambda x: [e.value for e in x]),
        default=TaskStatus.PENDING,
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    last_attempt_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    response_summary: Mapped[Optional[str]] = mapped_column(Text)
    outcome: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)
    scheduled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    campaign: Mapped["Campaign"] = relationship(back_populates="tasks")


class ConversationLog(Base):
    __tablename__ = "conversation_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    session_id: Mapped[str] = mapped_column(String(128))
    patient_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id")
    )
    direction: Mapped[str] = mapped_column(String(16), default="inbound")
    language: Mapped[Optional[str]] = mapped_column(String(8))
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer)
    turns: Mapped[int] = mapped_column(Integer, default=0)
    tool_calls: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    latency_metrics: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)
    outcome: Mapped[Optional[str]] = mapped_column(String(64))
    transcript: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
