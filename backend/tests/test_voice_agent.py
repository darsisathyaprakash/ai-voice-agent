"""
Tests for the voice agent and tool calling.
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


class TestVoiceAgent:
    """Test suite for the voice agent."""

    @pytest.mark.asyncio
    async def test_get_error_response_english(self):
        """Test error response in English."""
        from agent.voice_agent import VoiceAgent

        agent = VoiceAgent(session_id="test-session", language="en")
        response = agent._get_error_response()

        assert response is not None
        assert len(response) > 0
        assert "error" in response.lower() or "sorry" in response.lower()

    @pytest.mark.asyncio
    async def test_get_error_response_telugu(self):
        """Test error response in Telugu."""
        from agent.voice_agent import VoiceAgent

        agent = VoiceAgent(session_id="test-session", language="te")
        response = agent._get_error_response()

        assert response is not None
        assert "క్షమించండి" in response or "లోపం" in response  # Telugu keywords

    @pytest.mark.asyncio
    async def test_get_fallback_response_telugu(self):
        """Test fallback response in Telugu."""
        from agent.voice_agent import VoiceAgent

        agent = VoiceAgent(session_id="test-session", language="te")
        response = agent._get_fallback_response()

        assert response is not None
        assert len(response) > 0

    @pytest.mark.asyncio
    async def test_agent_initialization(self):
        """Test voice agent initialization with different languages."""
        from agent.voice_agent import VoiceAgent

        for lang in ["en", "hi", "te"]:
            agent = VoiceAgent(session_id=f"test-{lang}", language=lang)
            assert agent.language == lang
            assert agent.session_id == f"test-{lang}"


class TestVoiceAgentTools:
    """Test suite for voice agent tool definitions."""

    def test_tool_registry_exists(self):
        """Test that tool registry is available."""
        from agent.tools import tool_registry

        assert tool_registry is not None

    def test_tool_definitions_structure(self):
        """Test that tool definitions have correct structure."""
        from agent.tools import tool_registry

        tools = tool_registry.get_tool_definitions()
        assert isinstance(tools, list)
        assert len(tools) > 0

        for tool in tools:
            assert "type" in tool
            assert tool["type"] == "function"
            assert "function" in tool
            assert "name" in tool["function"]
            assert "description" in tool["function"]
            assert "parameters" in tool["function"]

    def test_check_availability_tool_exists(self):
        """Test that check_availability tool is defined."""
        from agent.tools import tool_registry

        tools = tool_registry.get_tool_definitions()
        tool_names = [t["function"]["name"] for t in tools]
        assert "check_availability" in tool_names

    def test_book_appointment_tool_exists(self):
        """Test that book_appointment tool is defined."""
        from agent.tools import tool_registry

        tools = tool_registry.get_tool_definitions()
        tool_names = [t["function"]["name"] for t in tools]
        assert "book_appointment" in tool_names

    def test_cancel_appointment_tool_exists(self):
        """Test that cancel_appointment tool is defined."""
        from agent.tools import tool_registry

        tools = tool_registry.get_tool_definitions()
        tool_names = [t["function"]["name"] for t in tools]
        assert "cancel_appointment" in tool_names


class TestVoiceHandler:
    """Test suite for WebSocket voice handler."""

    def test_voice_handler_import(self):
        """Test that voice handler can be imported."""
        from websocket.voice_handler import VoiceWebSocketHandler

        handler = VoiceWebSocketHandler()
        assert handler is not None
