"""
Tests for doctor and appointment API endpoints.
"""
import pytest
from datetime import date, timedelta
from uuid import uuid4


class TestDoctorEndpoints:
    """Test suite for doctor operations."""

    @pytest.mark.asyncio
    async def test_list_doctors(self, client):
        """Test listing all doctors."""
        response = await client.get("/api/doctors")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_list_doctors_filter_specialization(self, client):
        """Test filtering doctors by specialization."""
        response = await client.get("/api/doctors?specialization=cardio")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_list_doctors_filter_language(self, client):
        """Test filtering doctors by language."""
        response = await client.get("/api/doctors?language=te")
        # With mock DB, we get empty list (200 status)
        assert response.status_code == 200
        data = response.json()
        # Mock returns empty list, which is valid
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_get_doctor_not_found(self, client):
        """Test getting non-existent doctor."""
        fake_id = str(uuid4())
        response = await client.get(f"/api/doctors/{fake_id}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_list_specializations(self, client):
        """Test listing available specializations."""
        response = await client.get("/api/doctors/specializations")
        assert response.status_code == 200
        data = response.json()
        assert "specializations" in data


class TestAppointmentEndpoints:
    """Test suite for appointment operations."""

    @pytest.mark.asyncio
    async def test_get_appointment_not_found(self, client):
        """Test getting non-existent appointment."""
        fake_id = str(uuid4())
        response = await client.get(f"/api/appointments/{fake_id}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_cancel_appointment_not_found(self, client):
        """Test canceling non-existent appointment."""
        fake_id = str(uuid4())
        response = await client.post(f"/api/appointments/{fake_id}/cancel")
        assert response.status_code in [400, 404]

    @pytest.mark.asyncio
    async def test_appointment_language_validation(self, client):
        """Test appointment language validation accepts en, hi, te."""
        valid_languages = ["en", "hi", "te"]
        for lang in valid_languages:
            # This tests the schema validation
            tomorrow = date.today() + timedelta(days=1)
            data = {
                "patient_id": str(uuid4()),
                "doctor_id": str(uuid4()),
                "appointment_date": str(tomorrow),
                "start_time": "09:00",
                "language_used": lang,
            }
            response = await client.post("/api/appointments", json=data)
            # We expect either validation success or business logic failure
            # but NOT a 422 for language
            assert response.status_code != 422 or "language" not in str(response.json())
