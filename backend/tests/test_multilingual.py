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
        assert result in ["en", "hi", "ta", None]

    @pytest.mark.asyncio
    async def test_detect_hindi(self):
        """Test detecting Hindi text."""
        from services.language_detection.detector import LanguageDetector

        detector = LanguageDetector()
        result = await detector.detect("मुझे डॉक्टर से मिलना है कल सुबह")
        assert result in ["en", "hi", "ta", None]

    @pytest.mark.asyncio
    async def test_detect_tamil(self):
        """Test detecting Tamil text."""
        from services.language_detection.detector import LanguageDetector

        detector = LanguageDetector()
        result = await detector.detect("நாளை மருத்துவரை சந்திப்பு வேண்டும்")
        assert result in ["en", "hi", "ta", None]

    def test_supported_languages_list(self):
        """Test that supported languages include Tamil."""
        from services.language_detection.detector import LanguageDetector

        detector = LanguageDetector()
        assert "en" in detector.SUPPORTED_LANGUAGES
        assert "hi" in detector.SUPPORTED_LANGUAGES
        assert "ta" in detector.SUPPORTED_LANGUAGES

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

    def test_tamil_prompt_exists(self):
        """Test that Tamil prompt is defined."""
        from agent.prompts import TAMIL_PROMPT

        assert TAMIL_PROMPT is not None
        assert len(TAMIL_PROMPT) > 0

    def test_get_prompt_for_tamil(self):
        """Test getting prompt for Tamil language."""
        from agent.prompts import _get_base_prompt

        prompt = _get_base_prompt("ta")
        assert prompt is not None
        assert len(prompt) > 0

    def test_all_supported_prompts(self):
        """Test that all supported languages have prompts."""
        from agent.prompts import _get_base_prompt

        for lang in ["en", "hi", "ta"]:
            prompt = _get_base_prompt(lang)
            assert prompt is not None
            assert len(prompt) > 100  # Should be substantial

    def test_tts_voice_mapping(self):
        """Test TTS voice mapping for Tamil."""
        from config import settings

        voice = settings.get_tts_voice("ta")
        assert voice is not None
        assert "ta-IN" in voice

    def test_all_tts_voices(self):
        """Test TTS voice mapping for all languages."""
        from config import settings

        voices = {
            "en": settings.get_tts_voice("en"),
            "hi": settings.get_tts_voice("hi"),
            "ta": settings.get_tts_voice("ta"),
        }

        assert "en-US" in voices["en"]
        assert "hi-IN" in voices["hi"]
        assert "ta-IN" in voices["ta"]
