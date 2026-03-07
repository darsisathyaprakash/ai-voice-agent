"""
Redis-based session memory for the Voice AI Agent.
Stores conversation state with TTL-based expiry.
"""
import json
import uuid
from datetime import datetime
from typing import Any, Optional
import redis.asyncio as redis
from redis.exceptions import RedisError, ConnectionError as RedisConnectionError

# Import from backend - these imports work when running from the backend directory
try:
    from config import settings
    from observability import get_logger
except ImportError:
    import sys
    import os
    backend_path = os.path.join(os.path.dirname(__file__), '..', '..', 'backend')
    if backend_path not in sys.path:
        sys.path.insert(0, backend_path)
    from config import settings
    from observability import get_logger

logger = get_logger("redis_memory")


class SessionMemory:
    """
    Manages ephemeral conversation state in Redis.
    
    Key structure:
        session:{session_id}         → session metadata
        session:{session_id}:history → conversation history (list)
        session:{session_id}:state   → conversation state (hash)
    """

    def __init__(self):
        self.redis: Optional[redis.Redis] = None
        self.ttl = settings.REDIS_SESSION_TTL
        self._connected = False
        self._max_retries = 3

    async def connect(self):
        """Connect to Redis with retry logic."""
        for attempt in range(self._max_retries):
            try:
                self.redis = redis.from_url(
                    settings.REDIS_URL,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5,
                    retry_on_timeout=True,
                )
                await self.redis.ping()
                self._connected = True
                logger.info("redis_connected", url=settings.REDIS_URL)
                return
            except (RedisError, RedisConnectionError) as e:
                logger.warning(
                    "redis_connection_attempt_failed",
                    attempt=attempt + 1,
                    error=str(e)
                )
                if attempt == self._max_retries - 1:
                    raise
                await self._wait_before_retry(attempt)
    
    async def _wait_before_retry(self, attempt: int):
        """Exponential backoff between retries."""
        import asyncio
        wait_time = min(2 ** attempt, 10)  # Max 10 seconds
        await asyncio.sleep(wait_time)

    async def _ensure_connected(self):
        """Ensure Redis connection is active."""
        if not self._connected or not self.redis:
            await self.connect()
        try:
            await self.redis.ping()
        except (RedisError, RedisConnectionError):
            self._connected = False
            await self.connect()

    async def disconnect(self):
        if self.redis:
            await self.redis.close()
            self._connected = False
            logger.info("redis_disconnected")

    # ── Session lifecycle ──

    async def create_session(
        self,
        patient_id: Optional[str] = None,
        language: str = "en",
    ) -> str:
        session_id = str(uuid.uuid4())
        session_data = {
            "session_id": session_id,
            "patient_id": patient_id or "",
            "language": language,
            "intent": "",
            "pending_confirmation": "",
            "created_at": datetime.utcnow().isoformat(),
            "turn_count": "0",
            "is_active": "true",
        }
        key = f"session:{session_id}"
        await self.redis.hset(key, mapping=session_data)
        await self.redis.expire(key, self.ttl)
        logger.info("session_created", session_id=session_id, language=language)
        return session_id

    async def get_session(self, session_id: str) -> Optional[dict]:
        key = f"session:{session_id}"
        data = await self.redis.hgetall(key)
        if not data:
            return None
        # Refresh TTL on access (sliding window)
        await self.redis.expire(key, self.ttl)
        return data

    async def update_session(self, session_id: str, updates: dict[str, str]):
        key = f"session:{session_id}"
        if not await self.redis.exists(key):
            logger.warning("session_not_found", session_id=session_id)
            return
        await self.redis.hset(key, mapping=updates)
        await self.redis.expire(key, self.ttl)

    async def end_session(self, session_id: str):
        keys = [
            f"session:{session_id}",
            f"session:{session_id}:history",
            f"session:{session_id}:state",
        ]
        await self.redis.delete(*keys)
        logger.info("session_ended", session_id=session_id)

    # ── Conversation history ──

    async def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: Optional[dict] = None,
    ):
        key = f"session:{session_id}:history"
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow().isoformat(),
        }
        if metadata:
            message["metadata"] = metadata
        await self.redis.rpush(key, json.dumps(message))
        await self.redis.expire(key, self.ttl)
        # Increment turn count
        session_key = f"session:{session_id}"
        await self.redis.hincrby(session_key, "turn_count", 1)

    async def get_history(
        self, session_id: str, last_n: int = 20
    ) -> list[dict]:
        key = f"session:{session_id}:history"
        messages = await self.redis.lrange(key, -last_n, -1)
        return [json.loads(m) for m in messages]

    async def get_history_for_llm(
        self, session_id: str, last_n: int = 10
    ) -> list[dict[str, str]]:
        """Returns history in OpenAI message format."""
        history = await self.get_history(session_id, last_n)
        return [{"role": m["role"], "content": m["content"]} for m in history]

    # ── State management ──

    async def set_state(self, session_id: str, key: str, value: Any):
        state_key = f"session:{session_id}:state"
        if isinstance(value, (dict, list)):
            value = json.dumps(value)
        await self.redis.hset(state_key, key, str(value))
        await self.redis.expire(state_key, self.ttl)

    async def get_state(self, session_id: str, key: str) -> Optional[str]:
        state_key = f"session:{session_id}:state"
        return await self.redis.hget(state_key, key)

    # ── Intent & confirmation tracking ──

    async def set_intent(self, session_id: str, intent: str):
        await self.update_session(session_id, {"intent": intent})

    async def set_pending_confirmation(self, session_id: str, confirmation: dict):
        await self.update_session(
            session_id,
            {"pending_confirmation": json.dumps(confirmation)},
        )

    async def get_pending_confirmation(self, session_id: str) -> Optional[dict]:
        session = await self.get_session(session_id)
        if session and session.get("pending_confirmation"):
            try:
                return json.loads(session["pending_confirmation"])
            except (json.JSONDecodeError, TypeError):
                return None
        return None

    async def clear_pending_confirmation(self, session_id: str):
        await self.update_session(session_id, {"pending_confirmation": ""})

    # ── Language ──

    async def set_language(self, session_id: str, language: str):
        await self.update_session(session_id, {"language": language})

    async def get_language(self, session_id: str) -> str:
        session = await self.get_session(session_id)
        return session.get("language", "en") if session else "en"


# Singleton instance
session_memory = SessionMemory()
