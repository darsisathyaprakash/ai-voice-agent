"""
Tests for the appointment scheduling engine.
"""
import pytest
from datetime import date, time, timedelta
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock


class TestAppointmentEngine:
    """Test suite for appointment scheduling logic."""

    @pytest.fixture
    def engine(self):
        """Create appointment engine instance."""
        from scheduler.appointment_engine import AppointmentEngine
        return AppointmentEngine()

    @pytest.mark.asyncio
    async def test_reject_past_date(self, engine, db_session):
        """Test that past dates are rejected."""
        yesterday = date.today() - timedelta(days=1)

        result = await engine.check_availability(
            db=db_session,
            doctor_id=str(uuid4()),
            target_date=yesterday,
            start_time=time(9, 0),
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_get_available_slots_past_date(self, engine, db_session):
        """Test available slots returns empty for past date."""
        yesterday = date.today() - timedelta(days=1)

        slots = await engine.get_available_slots(
            db=db_session,
            doctor_id=str(uuid4()),
            target_date=yesterday,
        )

        assert slots == []

    @pytest.mark.asyncio
    async def test_book_appointment_patient_not_found(self, engine, db_session):
        """Test booking with non-existent patient."""
        tomorrow = date.today() + timedelta(days=1)

        result = await engine.book_appointment(
            db=db_session,
            patient_id=str(uuid4()),
            doctor_id=str(uuid4()),
            appointment_date=tomorrow,
            start_time=time(9, 0),
        )

        assert result["success"] is False
        assert "not found" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_cancel_appointment_not_found(self, engine, db_session):
        """Test canceling non-existent appointment."""
        result = await engine.cancel_appointment(
            db=db_session,
            appointment_id=str(uuid4()),
        )

        assert result["success"] is False
        assert "not found" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_reschedule_appointment_not_found(self, engine, db_session):
        """Test rescheduling non-existent appointment."""
        tomorrow = date.today() + timedelta(days=1)

        result = await engine.reschedule_appointment(
            db=db_session,
            appointment_id=str(uuid4()),
            new_date=tomorrow,
            new_time=time(10, 0),
        )

        assert result["success"] is False
        assert "not found" in result["error"].lower()

    def test_add_minutes_to_time(self, engine):
        """Test time arithmetic helper."""
        from scheduler.appointment_engine import AppointmentEngine

        result = AppointmentEngine._add_minutes_to_time(time(9, 0), 30)
        assert result == time(9, 30)

        result = AppointmentEngine._add_minutes_to_time(time(9, 45), 30)
        assert result == time(10, 15)

    def test_time_to_minutes(self, engine):
        """Test time to minutes conversion."""
        from scheduler.appointment_engine import AppointmentEngine

        assert AppointmentEngine._time_to_minutes(time(9, 0)) == 540
        assert AppointmentEngine._time_to_minutes(time(0, 0)) == 0
        assert AppointmentEngine._time_to_minutes(time(12, 30)) == 750
