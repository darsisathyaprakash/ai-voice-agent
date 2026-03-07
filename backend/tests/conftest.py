"""
Pytest fixtures for Voice AI Agent tests.
"""
import pytest
import asyncio
from datetime import date, time, timedelta
from uuid import uuid4
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


# ── Event Loop ──

@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# ── Database Fixtures ──

@pytest.fixture
async def db_session():
    """Create a mock database session for testing."""
    mock_session = AsyncMock()
    
    # Create mock result that returns None for scalar_one_or_none
    mock_result = MagicMock()
    mock_result.scalar_one_or_none = MagicMock(return_value=None)
    mock_result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
    
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.flush = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()
    mock_session.add = MagicMock()
    
    yield mock_session


# ── HTTP Client Fixtures ──

@pytest.fixture
async def client() -> AsyncGenerator:
    """Create async HTTP client with mocked dependencies for unit tests.
    
    Note: This uses mocked database - tests should handle empty results.
    For integration tests with real database, use integration_client fixture.
    """
    from httpx import AsyncClient, ASGITransport
    
    # Create mock database session that returns empty results
    async def mock_get_db():
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=None)
        mock_result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.flush = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.rollback = AsyncMock()
        mock_session.add = MagicMock()
        yield mock_session
    
    # Mock session_memory before importing main
    with patch("main.session_memory") as mock_redis:
        mock_redis.connect = AsyncMock()
        mock_redis.disconnect = AsyncMock()
        
        # Mock database init/close but NOT the actual session
        with patch("main.init_db", new=AsyncMock()):
            with patch("main.close_db", new=AsyncMock()):
                # Set a fake API key for testing
                with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key-12345"}):
                    from main import app
                    from database import get_db
                    
                    # Override the database dependency with mock
                    app.dependency_overrides[get_db] = mock_get_db
                    
                    # Override the OPENAI_API_KEY check
                    with patch("config.settings.OPENAI_API_KEY", "test-key-12345"):
                        transport = ASGITransport(app=app)
                        async with AsyncClient(transport=transport, base_url="http://test") as ac:
                            yield ac
                    
                    # Clear the override
                    app.dependency_overrides.clear()


# ── Test Data Fixtures ──

@pytest.fixture
def sample_patient_data():
    """Sample patient data for testing."""
    return {
        "first_name": "John",
        "last_name": "Doe",
        "phone": "+1234567890",
        "email": "john.doe@example.com",
        "preferred_language": "en",
    }


@pytest.fixture
def sample_doctor_data():
    """Sample doctor data for testing."""
    return {
        "first_name": "Jane",
        "last_name": "Smith",
        "specialization": "cardiologist",
        "department": "Cardiology",
        "consultation_duration_minutes": 30,
        "is_active": True,
        "languages": ["en", "hi", "te"],
    }


@pytest.fixture
def sample_appointment_data():
    """Sample appointment data for testing."""
    tomorrow = date.today() + timedelta(days=1)
    return {
        "appointment_date": str(tomorrow),
        "start_time": "09:00",
        "reason": "General checkup",
        "language_used": "en",
    }


# ── Mock Fixtures ──

@pytest.fixture
def mock_openai():
    """Mock OpenAI client for LLM tests."""
    with patch("openai.AsyncOpenAI") as mock:
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock()
        mock.return_value = mock_client
        yield mock_client


@pytest.fixture
def mock_redis():
    """Mock Redis client for session memory tests."""
    mock = AsyncMock()
    mock.ping = AsyncMock(return_value=True)
    mock.hset = AsyncMock()
    mock.hgetall = AsyncMock(return_value={})
    mock.expire = AsyncMock()
    mock.delete = AsyncMock()
    mock.rpush = AsyncMock()
    mock.lrange = AsyncMock(return_value=[])
    mock.exists = AsyncMock(return_value=True)
    mock.hincrby = AsyncMock()
    return mock


@pytest.fixture
def mock_tts():
    """Mock TTS service."""
    with patch("services.text_to_speech.tts_service.TTSService") as mock:
        mock.synthesize = AsyncMock(return_value=b"audio_data")
        yield mock


@pytest.fixture
def mock_stt():
    """Mock STT service."""
    with patch("services.speech_to_text.stt_service.STTService") as mock:
        mock.transcribe = AsyncMock(return_value={"text": "hello", "language": "en"})
        yield mock
