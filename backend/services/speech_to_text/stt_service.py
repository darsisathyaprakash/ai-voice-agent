"""
Speech-to-Text Service using Faster Whisper.
Optimized for low-latency transcription of clinical conversations.
"""
import io
import asyncio
from typing import Optional, Tuple
from concurrent.futures import ThreadPoolExecutor
import numpy as np

from config import settings
from observability import get_logger

logger = get_logger("stt_service")

# Thread pool for CPU-bound Whisper processing
_executor = ThreadPoolExecutor(max_workers=2)


class STTService:
    """
    Speech-to-Text service using Faster Whisper.
    Supports multilingual transcription (English, Hindi, Telugu).
    """

    def __init__(self):
        self.model = None
        self._initialized = False

    async def initialize(self):
        """Initialize the Whisper model."""
        if self._initialized:
            return
        
        await asyncio.get_event_loop().run_in_executor(
            _executor, self._load_model
        )
        self._initialized = True
        logger.info(
            "stt_model_loaded",
            model_size=settings.STT_MODEL_SIZE,
            device=settings.STT_DEVICE,
        )

    def _load_model(self):
        """Load Faster Whisper model (runs in thread pool)."""
        from faster_whisper import WhisperModel
        
        self.model = WhisperModel(
            settings.STT_MODEL_SIZE,
            device=settings.STT_DEVICE,
            compute_type=settings.STT_COMPUTE_TYPE,
        )

    async def transcribe(
        self,
        audio_data: bytes,
        language_hint: Optional[str] = None,
    ) -> Tuple[str, Optional[str]]:
        """
        Transcribe audio data to text.
        
        Args:
            audio_data: Raw audio bytes (WAV format expected, 16kHz mono)
            language_hint: Optional language hint (en, hi, ta)
            
        Returns:
            Tuple of (transcribed_text, detected_language)
        """
        if not self._initialized:
            await self.initialize()
        
        # Convert audio bytes to format Whisper expects
        audio_array = await self._process_audio(audio_data)
        
        if audio_array is None or len(audio_array) < 1600:  # Less than 100ms
            return "", None
        
        # Transcribe in thread pool
        result = await asyncio.get_event_loop().run_in_executor(
            _executor,
            self._transcribe_sync,
            audio_array,
            language_hint,
        )
        
        return result

    async def _process_audio(self, audio_data: bytes) -> Optional[np.ndarray]:
        """Convert audio bytes to numpy array."""
        try:
            import soundfile as sf
            
            # Read audio from bytes
            audio_io = io.BytesIO(audio_data)
            audio_array, sample_rate = sf.read(audio_io, dtype='float32')
            
            # Resample to 16kHz if needed
            if sample_rate != 16000:
                # Simple resampling (for production, use librosa.resample)
                ratio = 16000 / sample_rate
                new_length = int(len(audio_array) * ratio)
                audio_array = np.interp(
                    np.linspace(0, len(audio_array), new_length),
                    np.arange(len(audio_array)),
                    audio_array,
                )
            
            # Convert stereo to mono if needed
            if len(audio_array.shape) > 1:
                audio_array = audio_array.mean(axis=1)
            
            return audio_array.astype(np.float32)
            
        except Exception as e:
            logger.error("audio_processing_error", error=str(e))
            return None

    def _transcribe_sync(
        self,
        audio_array: np.ndarray,
        language_hint: Optional[str],
    ) -> Tuple[str, Optional[str]]:
        """Synchronous transcription (runs in thread pool)."""
        try:
            # Language mapping for Whisper
            lang_map = {"en": "en", "hi": "hi", "te": "te"}
            whisper_lang = lang_map.get(language_hint) if language_hint else None
            
            # Transcribe
            segments, info = self.model.transcribe(
                audio_array,
                language=whisper_lang,
                vad_filter=True,  # Voice Activity Detection
                vad_parameters=dict(
                    threshold=0.5,
                    min_speech_duration_ms=250,
                    min_silence_duration_ms=100,
                ),
                beam_size=3,  # Faster but less accurate
                best_of=1,
                temperature=0.0,
            )
            
            # Collect transcribed text
            text_parts = []
            for segment in segments:
                text_parts.append(segment.text.strip())
            
            transcribed_text = " ".join(text_parts).strip()
            detected_language = info.language if info else None
            
            logger.debug(
                "transcription_complete",
                text_length=len(transcribed_text),
                detected_language=detected_language,
            )
            
            return transcribed_text, detected_language
            
        except Exception as e:
            logger.error("transcription_error", error=str(e))
            return "", None

    async def transcribe_stream(
        self,
        audio_chunks: list[bytes],
        language_hint: Optional[str] = None,
    ) -> Tuple[str, Optional[str]]:
        """
        Transcribe streaming audio chunks.
        Concatenates chunks and transcribes as a batch.
        """
        combined_audio = b"".join(audio_chunks)
        return await self.transcribe(combined_audio, language_hint)


# Singleton instance
stt_service = STTService()
