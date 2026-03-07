"""
Language Detection Service for multilingual voice conversations.
Detects English, Hindi, and Telugu from text input.
"""
from typing import Optional
from langdetect import detect, detect_langs, LangDetectException

from observability import get_logger

logger = get_logger("language_detector")


class LanguageDetector:
    """
    Language detection service supporting:
    - English (en)
    - Hindi (hi)
    - Telugu (te)
    """

    # Supported languages mapping
    SUPPORTED_LANGUAGES = {
        "en": "en",  # English
        "hi": "hi",  # Hindi
        "te": "te",  # Telugu
        # Fallback mappings
        "mr": "hi",  # Marathi -> Hindi (similar script)
        "bn": "hi",  # Bengali -> Hindi (similar region)
        "ta": "te",  # Tamil -> Telugu (similar region)
        "kn": "te",  # Kannada -> Telugu (similar region)
        "ml": "te",  # Malayalam -> Telugu (similar region)
    }

    DEFAULT_LANGUAGE = "en"

    async def detect(self, text: str) -> Optional[str]:
        """
        Detect the language of the given text.
        
        Args:
            text: Text to analyze
            
        Returns:
            Language code (en, hi, ta) or None if detection fails
        """
        if not text or len(text.strip()) < 5:
            return None
        
        try:
            # Get detected language probabilities
            detected = detect_langs(text)
            
            if not detected:
                return None
            
            # Get the most likely language
            top_lang = detected[0]
            lang_code = top_lang.lang
            confidence = top_lang.prob
            
            # Map to supported language
            mapped_lang = self.SUPPORTED_LANGUAGES.get(lang_code)
            
            if mapped_lang and confidence >= 0.5:
                logger.debug(
                    "language_detected",
                    detected=lang_code,
                    mapped=mapped_lang,
                    confidence=round(confidence, 2),
                )
                return mapped_lang
            
            # Low confidence, return None
            logger.debug(
                "low_confidence_detection",
                detected=lang_code,
                confidence=round(confidence, 2),
            )
            return None
            
        except LangDetectException as e:
            logger.debug("language_detection_failed", error=str(e))
            return None

    def detect_sync(self, text: str) -> Optional[str]:
        """Synchronous version of detect."""
        if not text or len(text.strip()) < 5:
            return None
        
        try:
            detected = detect(text)
            return self.SUPPORTED_LANGUAGES.get(detected)
        except LangDetectException:
            return None

    async def detect_with_confidence(self, text: str) -> dict:
        """
        Detect language with confidence scores.
        
        Returns dict with detected language and confidence for each supported language.
        """
        result = {
            "detected": None,
            "confidence": 0.0,
            "scores": {"en": 0.0, "hi": 0.0, "te": 0.0},
        }
        
        if not text or len(text.strip()) < 5:
            return result
        
        try:
            detected_langs = detect_langs(text)
            
            for lang_result in detected_langs:
                lang_code = lang_result.lang
                confidence = lang_result.prob
                mapped = self.SUPPORTED_LANGUAGES.get(lang_code)
                
                if mapped and mapped in result["scores"]:
                    result["scores"][mapped] = max(
                        result["scores"][mapped],
                        round(confidence, 3),
                    )
            
            # Find highest scoring supported language
            max_lang = max(result["scores"].items(), key=lambda x: x[1])
            if max_lang[1] >= 0.3:
                result["detected"] = max_lang[0]
                result["confidence"] = max_lang[1]
            
            return result
            
        except LangDetectException:
            return result

    @staticmethod
    def get_language_name(code: str) -> str:
        """Get human-readable language name."""
        names = {
            "en": "English",
            "hi": "Hindi",
            "te": "Telugu",
        }
        return names.get(code, "Unknown")


# Singleton instance
language_detector = LanguageDetector()
