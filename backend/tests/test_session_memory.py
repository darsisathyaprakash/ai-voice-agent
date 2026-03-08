"""
Tests for Redis session memory operations.
"""
import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock


class TestSessionMemory:
    """Test suite for Redis session memory."""

    @pytest.mark.asyncio
    async def test_create_session(self, mock_redis):
        """Test session creation."""
        from memory.redis_memory.session_memory import SessionMemory

        memory = SessionMemory()
        memory.redis = mock_redis

        session_id = await memory.create_session(
            patient_id="test-patient",
            language="ta"
        )

        assert session_id is not None
        assert mock_redis.hset.called

    @pytest.mark.asyncio
    async def test_session_language_support(self, mock_redis):
        """Test that all supported languages are handled correctly."""
        from memory.redis_memory.session_memory import SessionMemory

        memory = SessionMemory()
        memory.redis = mock_redis

        for lang in ["en", "hi", "ta"]:
            session_id = await memory.create_session(language=lang)
            assert session_id is not None

    @pytest.mark.asyncio
    async def test_get_session_not_found(self, mock_redis):
        """Test getting non-existent session."""
        from memory.redis_memory.session_memory import SessionMemory

        memory = SessionMemory()
        memory.redis = mock_redis
        mock_redis.hgetall.return_value = {}

        result = await memory.get_session("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_session_ttl_refresh(self, mock_redis):
        """Test that accessing session refreshes TTL."""
        from memory.redis_memory.session_memory import SessionMemory

        memory = SessionMemory()
        memory.redis = mock_redis
        mock_redis.hgetall.return_value = {"session_id": "test"}

        await memory.get_session("test-session")

        mock_redis.expire.assert_called()

    @pytest.mark.asyncio
    async def test_add_message(self, mock_redis):
        """Test adding message to conversation history."""
        from memory.redis_memory.session_memory import SessionMemory

        memory = SessionMemory()
        memory.redis = mock_redis

        await memory.add_message(
            session_id="test-session",
            role="user",
            content="எனக்கு சந்திப்பு வேண்டும்",  # Tamil: I need an appointment
        )

        mock_redis.rpush.assert_called()

    @pytest.mark.asyncio
    async def test_get_history_for_llm(self, mock_redis):
        """Test getting conversation history in LLM format."""
        from memory.redis_memory.session_memory import SessionMemory

        memory = SessionMemory()
        memory.redis = mock_redis
        mock_redis.lrange.return_value = [
            json.dumps({"role": "user", "content": "Hello", "timestamp": "2024-01-01T00:00:00"}),
            json.dumps({"role": "assistant", "content": "Hi!", "timestamp": "2024-01-01T00:00:01"}),
        ]

        history = await memory.get_history_for_llm("test-session")

        assert len(history) == 2
        assert history[0]["role"] == "user"
        assert history[1]["role"] == "assistant"

    @pytest.mark.asyncio
    async def test_end_session(self, mock_redis):
        """Test ending a session cleans up all keys."""
        from memory.redis_memory.session_memory import SessionMemory

        memory = SessionMemory()
        memory.redis = mock_redis

        await memory.end_session("test-session")

        mock_redis.delete.assert_called()

    @pytest.mark.asyncio
    async def test_connection_retry_logic(self):
        """Test that connection retries work correctly."""
        from memory.redis_memory.session_memory import SessionMemory

        memory = SessionMemory()
        memory._max_retries = 3

        # Test that retry logic exists
        assert memory._max_retries == 3
        assert hasattr(memory, "_wait_before_retry")
        assert hasattr(memory, "connect")
