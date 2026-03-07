"""
Unit tests that don't require database or external services.
These are fast, reliable tests for core business logic.
"""
import pytest
from datetime import date, time, timedelta
from uuid import uuid4


class TestConfigSettings:
    """Test configuration settings."""

    def test_tts_voice_english(self):
        """Test English TTS voice configuration."""
        from config import settings
        voice = settings.get_tts_voice("en")
        assert voice == "en-US-AriaNeural"

    def test_tts_voice_hindi(self):
        """Test Hindi TTS voice configuration."""
        from config import settings
        voice = settings.get_tts_voice("hi")
        assert voice == "hi-IN-SwaraNeural"

    def test_tts_voice_telugu(self):
        """Test Telugu TTS voice configuration."""
        from config import settings
        voice = settings.get_tts_voice("te")
        assert voice == "te-IN-ShrutiNeural"

    def test_tts_voice_fallback(self):
        """Test TTS voice fallback for unknown language."""
        from config import settings
        voice = settings.get_tts_voice("unknown")
        assert voice == "en-US-AriaNeural"

    def test_latency_targets(self):
        """Test latency target configurations."""
        from config import settings
        assert settings.TARGET_STT_LATENCY_MS == 150
        assert settings.TARGET_LLM_LATENCY_MS == 200
        assert settings.TARGET_TTS_LATENCY_MS == 100
        assert settings.TARGET_TOTAL_LATENCY_MS == 450


class TestPrompts:
    """Test prompt generation."""

    def test_english_prompt_content(self):
        """Test English prompt has expected content."""
        from agent.prompts import ENGLISH_PROMPT
        assert "appointment" in ENGLISH_PROMPT.lower()
        assert len(ENGLISH_PROMPT) > 200

    def test_hindi_prompt_content(self):
        """Test Hindi prompt exists."""
        from agent.prompts import HINDI_PROMPT
        assert HINDI_PROMPT is not None
        assert len(HINDI_PROMPT) > 200

    def test_telugu_prompt_content(self):
        """Test Telugu prompt exists."""
        from agent.prompts import TELUGU_PROMPT
        assert TELUGU_PROMPT is not None
        assert len(TELUGU_PROMPT) > 200

    def test_get_system_prompt_all_languages(self):
        """Test system prompt generation for all languages."""
        from agent.prompts import get_system_prompt

        for lang in ["en", "hi", "te"]:
            prompt = get_system_prompt(lang, pending_confirmation=None)
            assert prompt is not None
            assert len(prompt) > 100

    def test_get_system_prompt_with_confirmation(self):
        """Test system prompt with pending confirmation."""
        from agent.prompts import get_system_prompt

        pending = {"action": "book_appointment", "details": {"date": "2026-03-08"}}
        prompt = get_system_prompt("en", pending_confirmation=pending)
        assert prompt is not None


class TestToolRegistry:
    """Test tool registry functionality."""

    def test_registry_has_tools(self):
        """Test that tool registry contains tools."""
        from agent.tools import tool_registry
        tools = tool_registry.get_tool_definitions()
        assert len(tools) > 0

    def test_tool_definition_format(self):
        """Test tool definitions follow OpenAI format."""
        from agent.tools import tool_registry
        tools = tool_registry.get_tool_definitions()

        for tool in tools:
            assert tool["type"] == "function"
            assert "function" in tool
            func = tool["function"]
            assert "name" in func
            assert "description" in func
            assert "parameters" in func

    def test_required_tools_exist(self):
        """Test that essential tools are registered."""
        from agent.tools import tool_registry
        tools = tool_registry.get_tool_definitions()
        tool_names = [t["function"]["name"] for t in tools]

        required_tools = [
            "check_availability",
            "book_appointment",
            "cancel_appointment",
        ]
        for required in required_tools:
            assert required in tool_names, f"Missing tool: {required}"


class TestAppointmentEngineUtils:
    """Test appointment engine utility functions."""

    def test_add_minutes_basic(self):
        """Test basic time addition."""
        from scheduler.appointment_engine import AppointmentEngine

        result = AppointmentEngine._add_minutes_to_time(time(9, 0), 30)
        assert result == time(9, 30)

    def test_add_minutes_hour_rollover(self):
        """Test time addition with hour rollover."""
        from scheduler.appointment_engine import AppointmentEngine

        result = AppointmentEngine._add_minutes_to_time(time(9, 45), 30)
        assert result == time(10, 15)

    def test_add_minutes_large(self):
        """Test large minute addition."""
        from scheduler.appointment_engine import AppointmentEngine

        result = AppointmentEngine._add_minutes_to_time(time(9, 0), 120)
        assert result == time(11, 0)

    def test_time_to_minutes_midnight(self):
        """Test midnight conversion."""
        from scheduler.appointment_engine import AppointmentEngine

        result = AppointmentEngine._time_to_minutes(time(0, 0))
        assert result == 0

    def test_time_to_minutes_noon(self):
        """Test noon conversion."""
        from scheduler.appointment_engine import AppointmentEngine

        result = AppointmentEngine._time_to_minutes(time(12, 0))
        assert result == 720

    def test_time_to_minutes_with_minutes(self):
        """Test conversion with minutes."""
        from scheduler.appointment_engine import AppointmentEngine

        result = AppointmentEngine._time_to_minutes(time(9, 30))
        assert result == 570


class TestLanguageDetectorConfig:
    """Test language detector configuration."""

    def test_supported_languages(self):
        """Test supported language mapping."""
        from services.language_detection.detector import LanguageDetector

        detector = LanguageDetector()
        assert detector.SUPPORTED_LANGUAGES["en"] == "en"
        assert detector.SUPPORTED_LANGUAGES["hi"] == "hi"
        assert detector.SUPPORTED_LANGUAGES["te"] == "te"

    def test_fallback_mappings(self):
        """Test regional language fallbacks."""
        from services.language_detection.detector import LanguageDetector

        detector = LanguageDetector()
        # Tamil should map to Telugu (regional proximity)
        assert detector.SUPPORTED_LANGUAGES.get("ta") == "te"
        # Marathi should map to Hindi (script similarity)
        assert detector.SUPPORTED_LANGUAGES.get("mr") == "hi"

    def test_default_language(self):
        """Test default language setting."""
        from services.language_detection.detector import LanguageDetector

        detector = LanguageDetector()
        assert detector.DEFAULT_LANGUAGE == "en"


class TestVoiceAgentResponses:
    """Test voice agent response generation."""

    def test_error_responses_all_languages(self):
        """Test error responses exist for all languages."""
        from agent.voice_agent import VoiceAgent

        for lang in ["en", "hi", "te"]:
            agent = VoiceAgent(session_id="test", language=lang)
            response = agent._get_error_response()
            assert response is not None
            assert len(response) > 10

    def test_fallback_responses_all_languages(self):
        """Test fallback responses exist for all languages."""
        from agent.voice_agent import VoiceAgent

        for lang in ["en", "hi", "te"]:
            agent = VoiceAgent(session_id="test", language=lang)
            response = agent._get_fallback_response()
            assert response is not None
            assert len(response) > 10

    def test_telugu_error_response_has_telugu_text(self):
        """Test Telugu error response contains Telugu script."""
        from agent.voice_agent import VoiceAgent

        agent = VoiceAgent(session_id="test", language="te")
        response = agent._get_error_response()
        # Should contain Telugu Unicode characters (U+0C00 to U+0C7F)
        telugu_chars = [c for c in response if '\u0C00' <= c <= '\u0C7F']
        assert len(telugu_chars) > 0, "Telugu response should contain Telugu script"


class TestObservability:
    """Test logging and observability utilities."""

    def test_get_logger_returns_logger(self):
        """Test logger creation."""
        from observability import get_logger

        logger = get_logger("test_component")
        assert logger is not None

    def test_latency_tracker_initialization(self):
        """Test latency tracker setup."""
        from observability import LatencyTracker

        tracker = LatencyTracker(session_id="test-session")
        assert tracker.session_id == "test-session"
        assert tracker.stages == {}

    def test_latency_tracker_pipeline(self):
        """Test latency tracking workflow."""
        from observability import LatencyTracker

        tracker = LatencyTracker(session_id="test")
        tracker.start_pipeline()
        assert tracker.pipeline_start is not None

        tracker.start_stage("stt")
        import time as time_module
        time_module.sleep(0.01)  # Small delay
        latency = tracker.end_stage("stt")
        assert latency > 0
        assert "stt" in tracker.stages


class TestSessionMemoryStructure:
    """Test session memory data structures."""

    def test_session_memory_has_required_methods(self):
        """Test SessionMemory class has required methods."""
        from memory.redis_memory.session_memory import SessionMemory

        memory = SessionMemory()
        
        # Check required methods exist
        assert hasattr(memory, "connect")
        assert hasattr(memory, "disconnect")
        assert hasattr(memory, "create_session")
        assert hasattr(memory, "get_session")
        assert hasattr(memory, "update_session")
        assert hasattr(memory, "end_session")
        assert hasattr(memory, "add_message")
        assert hasattr(memory, "get_history")
        assert hasattr(memory, "get_history_for_llm")

    def test_session_memory_retry_config(self):
        """Test session memory retry configuration."""
        from memory.redis_memory.session_memory import SessionMemory

        memory = SessionMemory()
        assert memory._max_retries == 3
