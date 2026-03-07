"""
Real-Time Voice WebSocket Handler
Manages the voice processing pipeline with latency optimization.
"""
import json
import asyncio
from typing import Optional
from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database import async_session_factory
from observability import get_logger, LatencyTracker, track_stage
from memory.redis_memory.session_memory import session_memory
from memory.persistent_memory.persistent_memory import persistent_memory
from services.speech_to_text.stt_service import stt_service
from services.text_to_speech.tts_service import tts_service
from services.language_detection.detector import language_detector
from agent.voice_agent import VoiceAgent

logger = get_logger("voice_websocket")


class VoiceWebSocketHandler:
    """
    Handles WebSocket connections for real-time voice conversations.
    
    Pipeline:
    1. Receive audio chunks via WebSocket
    2. Speech-to-Text processing
    3. Language detection (first turn)
    4. LLM Agent processing with tool execution
    5. Text-to-Speech generation
    6. Stream audio response back
    """

    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}
        self.agents: dict[str, VoiceAgent] = {}

    async def handle_connection(
        self,
        websocket: WebSocket,
        session_id: Optional[str] = None,
    ):
        """Main connection handler."""
        await websocket.accept()
        
        try:
            # Initialize session
            config = await self._receive_config(websocket)
            session_id, language = await self._initialize_session(config, session_id)
            
            self.active_connections[session_id] = websocket
            self.agents[session_id] = VoiceAgent(session_id, language)
            
            logger.info(
                "websocket_connected",
                session_id=session_id,
                language=language,
            )
            
            # Send session confirmation
            await websocket.send_json({
                "type": "session_started",
                "session_id": session_id,
                "language": language,
            })
            
            # Main conversation loop
            await self._conversation_loop(websocket, session_id)
            
        except WebSocketDisconnect:
            logger.info("websocket_disconnected", session_id=session_id)
        except Exception as e:
            logger.error(
                "websocket_error",
                session_id=session_id,
                error=str(e),
                error_type=type(e).__name__,
            )
            await self._send_error(websocket, str(e))
        finally:
            await self._cleanup_session(session_id)

    async def _receive_config(self, websocket: WebSocket) -> dict:
        """Receive initial configuration from client."""
        try:
            data = await asyncio.wait_for(
                websocket.receive_json(),
                timeout=10.0,
            )
            return data
        except asyncio.TimeoutError:
            return {}

    async def _initialize_session(
        self,
        config: dict,
        existing_session_id: Optional[str],
    ) -> tuple[str, str]:
        """Initialize or resume a session."""
        patient_phone = config.get("patient_phone")
        language = config.get("language", "en")
        patient_id = None
        
        # Look up patient by phone if provided
        if patient_phone:
            async with async_session_factory() as db:
                patient = await persistent_memory.get_patient_by_phone(db, patient_phone)
                if patient:
                    patient_id = str(patient.id)
                    language = patient.preferred_language or language
        
        # Resume existing session or create new
        if existing_session_id:
            session = await session_memory.get_session(existing_session_id)
            if session:
                return existing_session_id, session.get("language", language)
        
        # Create new session
        session_id = await session_memory.create_session(
            patient_id=patient_id,
            language=language,
        )
        
        return session_id, language

    async def _conversation_loop(self, websocket: WebSocket, session_id: str):
        """Main conversation processing loop."""
        audio_buffer = bytearray()
        
        while True:
            message = await websocket.receive()
            
            if message.get("type") == "websocket.disconnect":
                break
            
            # Handle binary audio data
            if "bytes" in message:
                audio_buffer.extend(message["bytes"])
                continue
            
            # Handle text/JSON messages
            if "text" in message:
                try:
                    data = json.loads(message["text"])
                except json.JSONDecodeError:
                    continue
                
                msg_type = data.get("type")
                
                if msg_type == "end_turn":
                    # Process accumulated audio
                    if audio_buffer:
                        await self._process_turn(
                            websocket, session_id, bytes(audio_buffer)
                        )
                        audio_buffer = bytearray()
                
                elif msg_type == "barge_in":
                    # Handle user interruption
                    await self._handle_barge_in(session_id)
                    audio_buffer = bytearray()
                
                elif msg_type == "end_session":
                    # Close session gracefully
                    await self._send_goodbye(websocket, session_id)
                    break
                
                elif msg_type == "text_input":
                    # Allow text input bypass for testing
                    text = data.get("text", "")
                    if text:
                        await self._process_text_turn(websocket, session_id, text)

    async def _process_turn(
        self,
        websocket: WebSocket,
        session_id: str,
        audio_data: bytes,
    ):
        """Process a complete turn of user speech."""
        tracker = LatencyTracker(session_id)
        tracker.start_pipeline()
        
        try:
            # ── Stage 1: Speech-to-Text ──
            async with track_stage(tracker, "stt"):
                text, detected_lang = await stt_service.transcribe(audio_data)
            
            if not text or not text.strip():
                logger.debug("empty_transcription", session_id=session_id)
                return
            
            logger.info(
                "user_speech",
                session_id=session_id,
                text=text[:100],
                detected_language=detected_lang,
            )
            
            # ── Stage 2: Language Detection (first turn) ──
            session = await session_memory.get_session(session_id)
            session_language = session.get("language", "en")
            
            # Update language if detected differently on first few turns
            turn_count = int(session.get("turn_count", 0))
            if turn_count < 3 and detected_lang and detected_lang != session_language:
                async with track_stage(tracker, "language_detection"):
                    confirmed_lang = await language_detector.detect(text)
                    if confirmed_lang and confirmed_lang != session_language:
                        await session_memory.set_language(session_id, confirmed_lang)
                        session_language = confirmed_lang
                        logger.info(
                            "language_switched",
                            session_id=session_id,
                            new_language=confirmed_lang,
                        )
            
            # Store user message in history
            await session_memory.add_message(session_id, "user", text)
            
            # ── Stage 3: LLM Agent Processing ──
            agent = self.agents.get(session_id)
            if not agent:
                agent = VoiceAgent(session_id, session_language)
                self.agents[session_id] = agent
            
            async with track_stage(tracker, "llm"):
                response = await agent.process(text)
            
            logger.info(
                "agent_response",
                session_id=session_id,
                response=response[:100] if response else "",
            )
            
            # Store assistant response in history
            await session_memory.add_message(session_id, "assistant", response)
            
            # ── Stage 4: Text-to-Speech ──
            async with track_stage(tracker, "tts"):
                audio_response = await tts_service.synthesize(
                    response, session_language
                )
            
            # ── Send Response ──
            # First send text for display
            await websocket.send_json({
                "type": "response_text",
                "text": response,
                "language": session_language,
            })
            
            # Then stream audio
            await websocket.send_bytes(audio_response)
            
            # Send turn completion with metrics
            report = tracker.get_report()
            await websocket.send_json({
                "type": "turn_complete",
                "latency": report,
            })
            
            logger.info(
                "turn_completed",
                session_id=session_id,
                total_ms=report["total_ms"],
                within_target=report["within_target"],
            )
            
        except Exception as e:
            logger.error(
                "turn_processing_error",
                session_id=session_id,
                error=str(e),
                error_type=type(e).__name__,
            )
            await self._send_error(websocket, "Sorry, I couldn't process that. Please try again.")

    async def _process_text_turn(
        self,
        websocket: WebSocket,
        session_id: str,
        text: str,
    ):
        """Process a text input turn (for testing/fallback)."""
        tracker = LatencyTracker(session_id)
        tracker.start_pipeline()
        
        try:
            session = await session_memory.get_session(session_id)
            session_language = session.get("language", "en")
            
            await session_memory.add_message(session_id, "user", text)
            
            agent = self.agents.get(session_id)
            if not agent:
                agent = VoiceAgent(session_id, session_language)
                self.agents[session_id] = agent
            
            async with track_stage(tracker, "llm"):
                response = await agent.process(text)
            
            await session_memory.add_message(session_id, "assistant", response)
            
            async with track_stage(tracker, "tts"):
                audio_response = await tts_service.synthesize(response, session_language)
            
            await websocket.send_json({
                "type": "response_text",
                "text": response,
                "language": session_language,
            })
            
            await websocket.send_bytes(audio_response)
            
            report = tracker.get_report()
            await websocket.send_json({
                "type": "turn_complete",
                "latency": report,
            })
            
        except Exception as e:
            logger.error("text_turn_error", session_id=session_id, error=str(e))
            await self._send_error(websocket, "Sorry, something went wrong.")

    async def _handle_barge_in(self, session_id: str):
        """Handle user barge-in (interruption)."""
        logger.info("barge_in_detected", session_id=session_id)
        # Cancel any ongoing synthesis/playback
        # In a full implementation, this would signal the TTS to stop

    async def _send_goodbye(self, websocket: WebSocket, session_id: str):
        """Send goodbye message and close session."""
        session = await session_memory.get_session(session_id)
        language = session.get("language", "en") if session else "en"
        
        goodbye_messages = {
            "en": "Thank you for calling. Have a great day!",
            "hi": "कॉल करने के लिए धन्यवाद। आपका दिन शुभ हो!",
            "te": "కాల్ చేసినందుకు ధన్యవాదాలు. మీకు శుభ దినం అవ్వుగాక!",
        }
        
        message = goodbye_messages.get(language, goodbye_messages["en"])
        
        await websocket.send_json({
            "type": "response_text",
            "text": message,
            "language": language,
        })
        
        audio = await tts_service.synthesize(message, language)
        await websocket.send_bytes(audio)
        
        await websocket.send_json({"type": "session_ended"})

    async def _send_error(self, websocket: WebSocket, message: str):
        """Send error message to client."""
        try:
            await websocket.send_json({
                "type": "error",
                "message": message,
            })
        except Exception:
            pass

    async def _cleanup_session(self, session_id: Optional[str]):
        """Clean up session resources."""
        if not session_id:
            return
        
        if session_id in self.active_connections:
            del self.active_connections[session_id]
        
        if session_id in self.agents:
            del self.agents[session_id]
        
        logger.info("session_cleaned_up", session_id=session_id)
