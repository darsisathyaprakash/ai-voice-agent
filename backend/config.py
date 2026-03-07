"""
Central configuration for Voice AI Agent backend services.
Uses pydantic-settings for environment variable management.
"""
from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    # ── Application ──
    APP_NAME: str = "Voice AI Agent"
    APP_ENV: str = "development"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"

    # ── Server ──
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    WORKERS: int = 4

    # ── Database ──
    DATABASE_URL: str = "postgresql+asyncpg://voiceai:voiceai_pass@localhost:5432/voiceai_db"
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 10

    # ── Redis ──
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_SESSION_TTL: int = 1800  # 30 minutes
    REDIS_CACHE_TTL: int = 300     # 5 minutes

    # ── OpenAI / LLM ──
    OPENAI_API_KEY: str = ""
    LLM_MODEL: str = "gpt-4o"
    LLM_TEMPERATURE: float = 0.3
    LLM_MAX_TOKENS: int = 1024
    LLM_TIMEOUT: int = 10

    # ── Speech-to-Text ──
    STT_MODEL_SIZE: str = "base"  # tiny, base, small, medium, large-v3
    STT_DEVICE: str = "cpu"       # cpu or cuda
    STT_COMPUTE_TYPE: str = "int8"

    # ── Text-to-Speech ──
    TTS_DEFAULT_VOICE_EN: str = "en-US-AriaNeural"
    TTS_DEFAULT_VOICE_HI: str = "hi-IN-SwaraNeural"
    TTS_DEFAULT_VOICE_TE: str = "te-IN-ShrutiNeural"

    # ── WebSocket ──
    WS_MAX_MESSAGE_SIZE: int = 1048576  # 1MB
    WS_PING_INTERVAL: int = 30
    WS_PING_TIMEOUT: int = 10

    # ── Latency Targets (ms) ──
    TARGET_STT_LATENCY_MS: int = 150
    TARGET_LLM_LATENCY_MS: int = 200
    TARGET_TTS_LATENCY_MS: int = 100
    TARGET_TOTAL_LATENCY_MS: int = 450

    # ── Campaign ──
    CAMPAIGN_WORKER_INTERVAL: int = 60  # seconds
    CAMPAIGN_MAX_CONCURRENT: int = 5
    CAMPAIGN_MAX_RETRIES: int = 3

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
    }

    def get_tts_voice(self, language: str) -> str:
        voices = {
            "en": self.TTS_DEFAULT_VOICE_EN,
            "hi": self.TTS_DEFAULT_VOICE_HI,
            "te": self.TTS_DEFAULT_VOICE_TE,
        }
        return voices.get(language, self.TTS_DEFAULT_VOICE_EN)


settings = Settings()
