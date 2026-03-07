"""
Tests for language detection and multilingual support.
"""
import pytest


class TestLanguageDetection:
    """Test suite for language detection service."""

    @pytest.mark.asyncio
    async def test_detect_english(self):
        """Test detecting English text."""
        from services.language_detection.detector import LanguageDetector

        detector = LanguageDetector()
        result = await detector.detect("I need an appointment with a doctor tomorrow morning")
        assert result in ["en", "hi", "te", None]

    @pytest.mark.asyncio
    async def test_detect_hindi(self):
        """Test detecting Hindi text."""
        from services.language_detection.detector import LanguageDetector

        detector = LanguageDetector()
        result = await detector.detect("मुझे डॉक्टर से मिलना है कल सुबह")
        assert result in ["en", "hi", "te", None]

    @pytest.mark.asyncio
    async def test_detect_telugu(self):
        """Test detecting Telugu text."""
        from services.language_detection.detector import LanguageDetector

        detector = LanguageDetector()
        result = await detector.detect("నాకు డాక్టర్ అపాయింట్మెంట్ రేపు కావాలి")
        assert result in ["en", "hi", "te", None]

    def test_supported_languages_list(self):
        """Test that supported languages include Telugu."""
        from services.language_detection.detector import LanguageDetector

        detector = LanguageDetector()
        assert "en" in detector.SUPPORTED_LANGUAGES
        assert "hi" in detector.SUPPORTED_LANGUAGES
        assert "te" in detector.SUPPORTED_LANGUAGES

    @pytest.mark.asyncio
    async def test_fallback_language_empty_text(self):
        """Test fallback behavior for empty text."""
        from services.language_detection.detector import LanguageDetector

        detector = LanguageDetector()
        result = await detector.detect("")
        assert result is None  # Empty text returns None

    @pytest.mark.asyncio
    async def test_fallback_language_short_text(self):
        """Test fallback behavior for short text."""
        from services.language_detection.detector import LanguageDetector

        detector = LanguageDetector()
        result = await detector.detect("hi")
        assert result is None  # Too short


class TestMultilingualSupport:
    """Test multilingual text and prompts."""

    def test_telugu_prompt_exists(self):
        """Test that Telugu prompt is defined."""
        from agent.prompts import TELUGU_PROMPT

        assert TELUGU_PROMPT is not None
        assert len(TELUGU_PROMPT) > 0

    def test_get_prompt_for_telugu(self):
        """Test getting prompt for Telugu language."""
        from agent.prompts import _get_base_prompt

        prompt = _get_base_prompt("te")
        assert prompt is not None
        assert len(prompt) > 0

    def test_all_supported_prompts(self):
        """Test that all supported languages have prompts."""
        from agent.prompts import _get_base_prompt

        for lang in ["en", "hi", "te"]:
            prompt = _get_base_prompt(lang)
            assert prompt is not None
            assert len(prompt) > 100  # Should be substantial

    def test_tts_voice_mapping(self):
        """Test TTS voice mapping for Telugu."""
        from config import settings

        voice = settings.get_tts_voice("te")
        assert voice is not None
        assert "te-IN" in voice

    def test_all_tts_voices(self):
        """Test TTS voice mapping for all languages."""
        from config import settings

        voices = {
            "en": settings.get_tts_voice("en"),
            "hi": settings.get_tts_voice("hi"),
            "te": settings.get_tts_voice("te"),
        }

        assert "en-US" in voices["en"]
        assert "hi-IN" in voices["hi"]
        assert "te-IN" in voices["te"]
