"""
Text-to-Speech Service using Edge TTS.
Fast, multilingual speech synthesis for real-time voice responses.
"""
import io
import asyncio
from typing import Optional
import edge_tts

from config import settings
from observability import get_logger

logger = get_logger("tts_service")


class TTSService:
    """
    Text-to-Speech service using Microsoft Edge TTS.
    Supports multilingual synthesis (English, Hindi, Telugu).
    """

    def __init__(self):
        self.voices = {
            "en": settings.TTS_DEFAULT_VOICE_EN,
            "hi": settings.TTS_DEFAULT_VOICE_HI,
            "te": settings.TTS_DEFAULT_VOICE_TE,
        }
        self.default_voice = settings.TTS_DEFAULT_VOICE_EN

    async def synthesize(
        self,
        text: str,
        language: str = "en",
        voice: Optional[str] = None,
    ) -> bytes:
        """
        Synthesize text to speech audio.
        
        Args:
            text: Text to convert to speech
            language: Language code (en, hi, ta)
            voice: Optional specific voice override
            
        Returns:
            Audio bytes (MP3 format)
        """
        if not text or not text.strip():
            return b""
        
        selected_voice = voice or self.voices.get(language, self.default_voice)
        
        try:
            # Create TTS communication
            communicate = edge_tts.Communicate(
                text=text,
                voice=selected_voice,
                rate="+0%",  # Normal speed
                pitch="+0Hz",  # Normal pitch
            )
            
            # Collect audio chunks
            audio_chunks = []
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_chunks.append(chunk["data"])
            
            audio_data = b"".join(audio_chunks)
            
            logger.debug(
                "tts_synthesis_complete",
                text_length=len(text),
                audio_size=len(audio_data),
                voice=selected_voice,
            )
            
            return audio_data
            
        except Exception as e:
            logger.error(
                "tts_synthesis_error",
                error=str(e),
                voice=selected_voice,
            )
            return b""

    async def synthesize_streaming(
        self,
        text: str,
        language: str = "en",
    ):
        """
        Stream synthesized audio chunks.
        
        Yields audio chunks as they become available for lower latency.
        """
        selected_voice = self.voices.get(language, self.default_voice)
        
        try:
            communicate = edge_tts.Communicate(
                text=text,
                voice=selected_voice,
            )
            
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    yield chunk["data"]
                    
        except Exception as e:
            logger.error("tts_streaming_error", error=str(e))

    def get_voice_for_language(self, language: str) -> str:
        """Get the default voice for a language."""
        return self.voices.get(language, self.default_voice)

    @staticmethod
    async def list_available_voices() -> list[dict]:
        """List all available voices from Edge TTS."""
        try:
            voices = await edge_tts.list_voices()
            return [
                {
                    "name": v["Name"],
                    "short_name": v["ShortName"],
                    "language": v["Locale"],
                    "gender": v["Gender"],
                }
                for v in voices
            ]
        except Exception as e:
            logger.error("list_voices_error", error=str(e))
            return []


# Singleton instance
tts_service = TTSService()
