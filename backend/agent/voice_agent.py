"""
Voice Agent - LLM-based conversational agent with tool orchestration.
Handles clinical appointment booking conversations.
"""
import json
import asyncio
from typing import Optional, Any
from openai import AsyncOpenAI

from config import settings
from observability import get_logger
from memory.redis_memory.session_memory import session_memory
from agent.tools import ToolRegistry, tool_registry
from agent.prompts import get_system_prompt

logger = get_logger("voice_agent")


class VoiceAgent:
    """
    LLM-based voice agent for clinical appointment booking.
    
    Features:
    - Multi-language support (English, Hindi, Tamil)
    - Tool calling for appointment operations
    - Conversation memory with context
    - Intent tracking and confirmation handling
    """

    def __init__(self, session_id: str, language: str = "en"):
        self.session_id = session_id
        self.language = language
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = settings.LLM_MODEL
        self.tool_registry = tool_registry

    async def process(self, user_input: str) -> str:
        """
        Process user input and generate response.
        
        Args:
            user_input: Transcribed user speech
            
        Returns:
            Agent response text
        """
        try:
            # Get conversation history
            history = await session_memory.get_history_for_llm(
                self.session_id, last_n=10
            )
            
            # Get pending confirmation if any
            pending = await session_memory.get_pending_confirmation(self.session_id)
            
            # Build messages
            messages = self._build_messages(user_input, history, pending)
            
            # Call LLM with tools
            response = await self._call_llm(messages)
            
            # Process response (may include tool calls)
            final_response = await self._process_response(response, messages)
            
            return final_response
            
        except Exception as e:
            logger.error(
                "agent_error",
                session_id=self.session_id,
                error=str(e),
                error_type=type(e).__name__,
            )
            return self._get_error_response()

    def _build_messages(
        self,
        user_input: str,
        history: list[dict],
        pending: Optional[dict],
    ) -> list[dict]:
        """Build message list for LLM."""
        system_prompt = get_system_prompt(self.language, pending)
        
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history)
        messages.append({"role": "user", "content": user_input})
        
        return messages

    async def _call_llm(self, messages: list[dict]) -> Any:
        """Call LLM with tool definitions."""
        tools = self.tool_registry.get_tool_definitions()
        
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=tools,
            tool_choice="auto",
            temperature=settings.LLM_TEMPERATURE,
            max_tokens=settings.LLM_MAX_TOKENS,
            timeout=settings.LLM_TIMEOUT,
        )
        
        return response

    async def _process_response(
        self,
        response: Any,
        messages: list[dict],
    ) -> str:
        """Process LLM response, handling tool calls if present."""
        message = response.choices[0].message
        
        # If no tool calls, return the content
        if not message.tool_calls:
            return message.content or self._get_fallback_response()
        
        # Process tool calls
        tool_results = []
        for tool_call in message.tool_calls:
            result = await self._execute_tool(tool_call)
            tool_results.append({
                "tool_call_id": tool_call.id,
                "role": "tool",
                "content": json.dumps(result),
            })
            
            logger.info(
                "tool_executed",
                session_id=self.session_id,
                tool=tool_call.function.name,
                result_success=result.get("success", False),
            )
        
        # Add assistant message and tool results to context
        messages.append({
            "role": "assistant",
            "content": message.content,
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in message.tool_calls
            ],
        })
        messages.extend(tool_results)
        
        # Get final response after tool execution
        final_response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=settings.LLM_TEMPERATURE,
            max_tokens=settings.LLM_MAX_TOKENS,
            timeout=settings.LLM_TIMEOUT,
        )
        
        return final_response.choices[0].message.content or self._get_fallback_response()

    async def _execute_tool(self, tool_call: Any) -> dict:
        """Execute a tool call and return the result."""
        tool_name = tool_call.function.name
        
        try:
            arguments = json.loads(tool_call.function.arguments)
        except json.JSONDecodeError:
            return {"success": False, "error": "Invalid tool arguments"}
        
        # Add session context
        arguments["session_id"] = self.session_id
        arguments["language"] = self.language
        
        # Execute tool
        result = await self.tool_registry.execute(tool_name, arguments)
        
        # Handle confirmation requirements
        if result.get("requires_confirmation"):
            await session_memory.set_pending_confirmation(
                self.session_id,
                {
                    "action": tool_name,
                    "details": result.get("confirmation_details", {}),
                },
            )
        
        return result

    def _get_error_response(self) -> str:
        """Get error response in appropriate language."""
        responses = {
            "en": "I'm sorry, I encountered an error. Could you please repeat that?",
            "hi": "मुझे खेद है, कुछ गड़बड़ हो गई। क्या आप कृपया दोहरा सकते हैं?",
            "ta": "மன்னிக்கவும், ஒரு பிழை ஏற்பட்டது. தயவுசெய்து மீண்டும் சொல்ல முடியுமா?",
        }
        return responses.get(self.language, responses["en"])

    def _get_fallback_response(self) -> str:
        """Get fallback response when LLM returns empty."""
        responses = {
            "en": "I'm here to help with your appointment. What would you like to do?",
            "hi": "मैं आपकी अपॉइंटमेंट में मदद के लिए हूं। आप क्या करना चाहेंगे?",
            "ta": "உங்கள் சந்திப்புக்கு உதவ நான் இங்கே இருக்கிறேன். நீங்கள் என்ன செய்ய விரும்புகிறீர்கள்?",
        }
        return responses.get(self.language, responses["en"])
