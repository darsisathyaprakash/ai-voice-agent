"""
Voice AI Agent - FastAPI Application Entry Point
Clinical Appointment Booking System with Real-Time Voice Processing
"""
# CodeRabbit review trigger - Production-ready Voice AI Agent
import asyncio
import uuid
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.middleware.base import BaseHTTPMiddleware
from collections import defaultdict

from config import settings
from database import init_db, close_db
from observability import get_logger
from api.routes import health, patients, doctors, appointments, campaigns
from websocket.voice_handler import VoiceWebSocketHandler
from memory.redis_memory.session_memory import session_memory

logger = get_logger("main")


# ── Rate Limiting Middleware ──
class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple in-memory rate limiter."""
    
    def __init__(self, app, requests_per_minute: int = 100):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.requests: dict[str, list[float]] = defaultdict(list)
    
    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for health checks and WebSocket
        if request.url.path.startswith("/api/health") or request.url.path.startswith("/ws"):
            return await call_next(request)
        
        client_ip = request.client.host if request.client else "unknown"
        current_time = time.time()
        minute_ago = current_time - 60
        
        # Clean old requests
        self.requests[client_ip] = [
            t for t in self.requests[client_ip] if t > minute_ago
        ]
        
        # Check rate limit
        if len(self.requests[client_ip]) >= self.requests_per_minute:
            logger.warning("rate_limit_exceeded", client_ip=client_ip)
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please try again later."}
            )
        
        self.requests[client_ip].append(current_time)
        return await call_next(request)


# ── Request ID Middleware ──
class RequestIdMiddleware(BaseHTTPMiddleware):
    """Add unique request ID to each request."""
    
    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())[:8]
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


# ── Security Headers Middleware ──
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""
    
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        if not settings.DEBUG:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle management."""
    logger.info(
        "application_starting",
        app_name=settings.APP_NAME,
        environment=settings.APP_ENV,
    )
    
    # Validate critical settings
    if not settings.OPENAI_API_KEY or settings.OPENAI_API_KEY == "your-openai-api-key-here":
        logger.error("missing_openai_api_key")
        raise RuntimeError("OPENAI_API_KEY is not configured")
    
    # Initialize services
    try:
        await init_db()
        await session_memory.connect()
    except Exception as e:
        logger.error("initialization_failed", error=str(e))
        raise
    
    logger.info("application_ready")
    
    yield
    
    # Cleanup
    logger.info("application_shutting_down")
    await session_memory.disconnect()
    await close_db()
    logger.info("application_stopped")


app = FastAPI(
    title=settings.APP_NAME,
    description="Real-Time Multilingual Voice AI Agent for Clinical Appointment Booking",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs" if settings.DEBUG else None,
    redoc_url="/api/redoc" if settings.DEBUG else None,
)

# ── Middleware Stack ──
# Add rate limiting (production only)
if not settings.DEBUG:
    app.add_middleware(RateLimitMiddleware, requests_per_minute=100)

# Add request ID tracking
app.add_middleware(RequestIdMiddleware)

# Add security headers
app.add_middleware(SecurityHeadersMiddleware)

# CORS configuration - restrict in production
allowed_origins = ["*"] if settings.DEBUG else [
    "https://yourdomain.com",  # Update with actual domains
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(health.router, prefix="/api", tags=["Health"])
app.include_router(patients.router, prefix="/api/patients", tags=["Patients"])
app.include_router(doctors.router, prefix="/api/doctors", tags=["Doctors"])
app.include_router(appointments.router, prefix="/api/appointments", tags=["Appointments"])
app.include_router(campaigns.router, prefix="/api/campaigns", tags=["Campaigns"])


# Root route for service info
@app.get("/")
async def root():
    """Root endpoint - service information."""
    return {
        "service": "Voice AI Agent API",
        "version": "1.0.0",
        "docs": "/api/docs" if settings.DEBUG else None,
    }


# WebSocket endpoint for voice streaming
voice_handler = VoiceWebSocketHandler()


@app.websocket("/ws/voice")
async def websocket_voice_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time voice conversation.
    
    Protocol:
    1. Client connects and sends initial config: {"patient_phone": "...", "language": "en"}
    2. Client streams audio chunks as binary data
    3. Server responds with synthesized speech audio
    4. Special messages:
       - {"type": "end_turn"}: Signal end of user speech
       - {"type": "barge_in"}: User interrupted
       - {"type": "end_session"}: Close session
    """
    await voice_handler.handle_connection(websocket)


@app.websocket("/ws/voice/{session_id}")
async def websocket_voice_resume(websocket: WebSocket, session_id: str):
    """Resume an existing voice session."""
    await voice_handler.handle_connection(websocket, session_id=session_id)


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    request_id = getattr(request.state, "request_id", "unknown")
    logger.error(
        "unhandled_exception",
        request_id=request_id,
        path=str(request.url),
        error=str(exc),
        error_type=type(exc).__name__,
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "request_id": request_id},
    )


# Validation error handler
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    request_id = getattr(request.state, "request_id", "unknown")
    logger.warning(
        "validation_error",
        request_id=request_id,
        path=str(request.url),
        errors=str(exc.errors()),
    )
    return JSONResponse(
        status_code=422,
        content={
            "detail": "Validation error",
            "errors": exc.errors(),
            "request_id": request_id,
        },
    )


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        workers=1,  # Use 1 worker for WebSocket support
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
    )
