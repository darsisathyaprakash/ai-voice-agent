"""
Structured logging with latency tracking for the voice pipeline.
Uses structlog for JSON-formatted, contextualized logs.
"""
import time
import logging
import structlog
from functools import wraps
from typing import Any, Optional
from contextlib import asynccontextmanager
from config import settings

# ── Log Level Mapping ──
LOG_LEVEL_MAP = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "WARN": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


def _get_log_level(level_name: str) -> int:
    """Get numeric log level from string name."""
    return LOG_LEVEL_MAP.get(level_name.upper(), logging.INFO)


# ── Configure structlog ──
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(
        _get_log_level(settings.LOG_LEVEL)
    ),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)


def get_logger(name: str) -> structlog.BoundLogger:
    return structlog.get_logger(component=name)


class LatencyTracker:
    """Tracks per-stage latency through the voice pipeline."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.stages: dict[str, float] = {}
        self._start_times: dict[str, float] = {}
        self.pipeline_start: Optional[float] = None
        self.logger = get_logger("latency_tracker")

    def start_pipeline(self):
        self.pipeline_start = time.perf_counter()
        self.stages = {}

    def start_stage(self, stage: str):
        self._start_times[stage] = time.perf_counter()

    def end_stage(self, stage: str) -> float:
        if stage not in self._start_times:
            return 0.0
        elapsed_ms = (time.perf_counter() - self._start_times[stage]) * 1000
        self.stages[stage] = elapsed_ms
        del self._start_times[stage]
        return elapsed_ms

    def get_total_latency(self) -> float:
        if self.pipeline_start is None:
            return 0.0
        return (time.perf_counter() - self.pipeline_start) * 1000

    def get_report(self) -> dict[str, Any]:
        total = self.get_total_latency()
        target = settings.TARGET_TOTAL_LATENCY_MS
        report = {
            "session_id": self.session_id,
            "stages": self.stages,
            "total_ms": round(total, 2),
            "target_ms": target,
            "within_target": total <= target,
        }
        # Log warnings for stages exceeding targets
        targets = {
            "stt": settings.TARGET_STT_LATENCY_MS,
            "llm": settings.TARGET_LLM_LATENCY_MS,
            "tts": settings.TARGET_TTS_LATENCY_MS,
        }
        violations = {}
        for stage, target_ms in targets.items():
            if stage in self.stages and self.stages[stage] > target_ms:
                violations[stage] = {
                    "actual_ms": round(self.stages[stage], 2),
                    "target_ms": target_ms,
                }
        if violations:
            report["violations"] = violations
            self.logger.warning(
                "latency_violation",
                session_id=self.session_id,
                violations=violations,
                total_ms=round(total, 2),
            )
        else:
            self.logger.info(
                "pipeline_latency",
                session_id=self.session_id,
                stages=self.stages,
                total_ms=round(total, 2),
            )
        return report


@asynccontextmanager
async def track_stage(tracker: LatencyTracker, stage: str):
    """Async context manager for tracking a pipeline stage."""
    tracker.start_stage(stage)
    try:
        yield
    finally:
        elapsed = tracker.end_stage(stage)
        tracker.logger.debug(
            "stage_completed",
            stage=stage,
            elapsed_ms=round(elapsed, 2),
            session_id=tracker.session_id,
        )


def log_latency(stage: str):
    """Decorator for synchronous functions to log execution time."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start = time.perf_counter()
            result = func(*args, **kwargs)
            elapsed = (time.perf_counter() - start) * 1000
            logger = get_logger(stage)
            logger.info(
                "function_latency",
                function=func.__name__,
                elapsed_ms=round(elapsed, 2),
            )
            return result
        return wrapper
    return decorator


def log_async_latency(stage: str):
    """Decorator for async functions to log execution time."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start = time.perf_counter()
            result = await func(*args, **kwargs)
            elapsed = (time.perf_counter() - start) * 1000
            logger = get_logger(stage)
            logger.info(
                "function_latency",
                function=func.__name__,
                elapsed_ms=round(elapsed, 2),
            )
            return result
        return wrapper
    return decorator
