# System Architecture

## Overview

The Voice AI Agent is a distributed system designed for real-time multilingual voice conversations. It follows a microservices architecture with clear separation of concerns.

## Architecture Diagram

```
                                    ┌─────────────────────────┐
                                    │    Client Application    │
                                    │  (Mobile/Web/Telephony)  │
                                    └───────────┬─────────────┘
                                                │
                                    ┌───────────▼─────────────┐
                                    │      Load Balancer       │
                                    │     (NGINX/HAProxy)      │
                                    └───────────┬─────────────┘
                                                │
                        ┌───────────────────────┼───────────────────────┐
                        │                       │                       │
            ┌───────────▼───────────┐           │           ┌───────────▼───────────┐
            │   Node.js Orchestrator │           │           │   Node.js Orchestrator │
            │      (Instance 1)      │           │           │      (Instance 2)      │
            │                       │           │           │                       │
            │  ┌─────────────────┐  │           │           │  ┌─────────────────┐  │
            │  │ WebSocket Proxy │  │           │           │  │ WebSocket Proxy │  │
            │  │   API Router    │  │           │           │  │   API Router    │  │
            │  │ Latency Monitor │  │           │           │  │ Latency Monitor │  │
            │  └─────────────────┘  │           │           │  └─────────────────┘  │
            └───────────┬───────────┘           │           └───────────┬───────────┘
                        │                       │                       │
                        └───────────────────────┼───────────────────────┘
                                                │
                        ┌───────────────────────┼───────────────────────┐
                        │                       │                       │
            ┌───────────▼───────────┐           │           ┌───────────▼───────────┐
            │   Python Backend      │           │           │   Python Backend      │
            │    (Instance 1)       │           │           │    (Instance 2)       │
            │                       │           │           │                       │
            │  ┌─────────────────┐  │           │           │  ┌─────────────────┐  │
            │  │  Voice Handler  │  │           │           │  │  Voice Handler  │  │
            │  │   LLM Agent     │  │           │           │  │   LLM Agent     │  │
            │  │  STT Service    │  │           │           │  │  STT Service    │  │
            │  │  TTS Service    │  │           │           │  │  TTS Service    │  │
            │  │  Scheduler      │  │           │           │  │  Scheduler      │  │
            │  └─────────────────┘  │           │           │  └─────────────────┘  │
            └───────────┬───────────┘           │           └───────────┬───────────┘
                        │                       │                       │
                        └───────────────────────┼───────────────────────┘
                                                │
                ┌───────────────────────────────┼───────────────────────────────┐
                │                               │                               │
    ┌───────────▼───────────┐       ┌───────────▼───────────┐       ┌───────────▼───────────┐
    │      PostgreSQL       │       │         Redis          │       │     Celery Workers    │
    │                       │       │                       │       │                       │
    │  ┌─────────────────┐  │       │  ┌─────────────────┐  │       │  ┌─────────────────┐  │
    │  │    Patients     │  │       │  │ Session Memory  │  │       │  │ Campaign Tasks  │  │
    │  │    Doctors      │  │       │  │   - History     │  │       │  │ Scheduled Jobs  │  │
    │  │  Appointments   │  │       │  │   - State       │  │       │  │   Reminders     │  │
    │  │   Campaigns     │  │       │  │   - Intent      │  │       │  │                 │  │
    │  │     Logs        │  │       │  │ Pub/Sub         │  │       │  │                 │  │
    │  └─────────────────┘  │       │  └─────────────────┘  │       │  └─────────────────┘  │
    └───────────────────────┘       └───────────────────────┘       └───────────────────────┘
```

## Component Details

### 1. Node.js Orchestrator

**Purpose:** API gateway, WebSocket proxy, client-facing interface

**Responsibilities:**
- Handle incoming client connections
- Proxy WebSocket streams to Python backend
- Aggregate metrics from backend
- Provide caching layer
- Handle authentication (when implemented)

**Technology:**
- Express.js for REST API
- ws library for WebSocket
- ioredis for Redis caching

### 2. Python Backend (FastAPI)

**Purpose:** Core business logic, voice processing, AI agent

**Responsibilities:**
- Real-time voice pipeline (STT → LLM → TTS)
- LLM agent with tool orchestration
- Appointment scheduling logic
- Database operations

**Key Modules:**
- `websocket/` - WebSocket connection handler
- `agent/` - LLM agent with tools
- `services/` - STT, TTS, language detection
- `scheduler/` - Appointment engine
- `api/` - REST endpoints

### 3. Voice Pipeline

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Voice Pipeline                               │
│                                                                      │
│  ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐   │
│  │  Audio   │ ──► │   STT    │ ──► │   LLM    │ ──► │   TTS    │   │
│  │  Input   │     │ (Whisper)│     │  Agent   │     │  (Edge)  │   │
│  └──────────┘     └──────────┘     └──────────┘     └──────────┘   │
│       │                │                │                │          │
│       │                ▼                ▼                ▼          │
│       │          ┌──────────┐     ┌──────────┐     ┌──────────┐   │
│       │          │ Language │     │   Tool   │     │  Audio   │   │
│       │          │ Detect   │     │Execution │     │  Output  │   │
│       │          └──────────┘     └──────────┘     └──────────┘   │
│       │                                 │                          │
│       │                                 ▼                          │
│       │                          ┌──────────┐                      │
│       │                          │  Memory  │                      │
│       │                          │  Update  │                      │
│       │                          └──────────┘                      │
│       │                                                            │
│       └──────── Latency Tracking Throughout ────────────────────►  │
└─────────────────────────────────────────────────────────────────────┘
```

### 4. Memory Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Memory Architecture                          │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    Session Memory (Redis)                    │   │
│  │                                                               │   │
│  │  session:{id}         → { patient_id, language, intent, ... }│   │
│  │  session:{id}:history → [ {role, content, timestamp}, ... ]  │   │
│  │  session:{id}:state   → { key: value, ... }                  │   │
│  │                                                               │   │
│  │  TTL: 30 minutes (sliding window)                            │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                               │                                     │
│                               │ Patient ID                          │
│                               ▼                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                Persistent Memory (PostgreSQL)                │   │
│  │                                                               │   │
│  │  patients      → { id, name, phone, language, preferences }  │   │
│  │  appointments  → { id, patient, doctor, date, time, status } │   │
│  │  doctors       → { id, name, specialty, schedule }           │   │
│  │  conv_logs     → { session_id, transcript, metrics }         │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

### 5. LLM Agent Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        LLM Agent Architecture                        │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                      System Prompt                           │   │
│  │  - Role: Clinical appointment assistant                      │   │
│  │  - Language: {en|hi|ta}                                      │   │
│  │  - Capabilities: Book, reschedule, cancel, check             │   │
│  │  - Pending confirmation context (if any)                     │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                               │                                     │
│                               ▼                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    Conversation History                      │   │
│  │  [user: "...", assistant: "...", user: "...", ...]          │   │
│  │  (Last 10 turns from Redis)                                  │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                               │                                     │
│                               ▼                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                         GPT-4o                               │   │
│  │  - Tool calling enabled                                      │   │
│  │  - Temperature: 0.3                                          │   │
│  │  - Max tokens: 1024                                          │   │
│  │  - Timeout: 10s                                              │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                               │                                     │
│              ┌────────────────┴────────────────┐                   │
│              ▼                                 ▼                    │
│  ┌─────────────────────┐           ┌─────────────────────┐        │
│  │   Text Response     │           │    Tool Calls       │        │
│  │   (No tools)        │           │                     │        │
│  └─────────────────────┘           └──────────┬──────────┘        │
│                                                │                    │
│                                                ▼                    │
│                                    ┌─────────────────────┐        │
│                                    │   Tool Registry     │        │
│                                    │                     │        │
│                                    │ - check_availability│        │
│                                    │ - book_appointment  │        │
│                                    │ - cancel_appointment│        │
│                                    │ - reschedule        │        │
│                                    │ - find_doctors      │        │
│                                    │ - get_appointments  │        │
│                                    └──────────┬──────────┘        │
│                                                │                    │
│                                                ▼                    │
│                                    ┌─────────────────────┐        │
│                                    │   Tool Execution    │        │
│                                    │   + DB Operations   │        │
│                                    └──────────┬──────────┘        │
│                                                │                    │
│                                                ▼                    │
│                                    ┌─────────────────────┐        │
│                                    │  Final Response     │        │
│                                    │  (with results)     │        │
│                                    └─────────────────────┘        │
└─────────────────────────────────────────────────────────────────────┘
```

## Data Flow

### Inbound Voice Call

```
1. Client connects via WebSocket
2. Sends initialization config { phone, language }
3. Orchestrator proxies to Python backend
4. Backend creates/resumes session in Redis
5. Client streams audio chunks
6. Client signals end_turn
7. Backend processes:
   a. STT: Audio → Text
   b. Language detection (first turns)
   c. LLM Agent: Text → Response + Tools
   d. TTS: Response → Audio
8. Backend streams audio response
9. Client plays audio
10. Repeat 5-9 for conversation
11. Client sends end_session
12. Session logged to PostgreSQL
```

### Appointment Booking Flow

```
1. User: "I need to see a cardiologist tomorrow"
2. Agent detects intent: check_availability
3. Tool call: check_availability(specialty="cardiologist", date="tomorrow")
4. System returns available slots
5. Agent: "Dr. Priya Sharma is available at 10 AM, 11 AM, or 2 PM"
6. User: "10 AM please"
7. Agent requires confirmation
8. Agent: "Shall I book with Dr. Sharma at 10 AM tomorrow?"
9. User: "Yes"
10. Tool call: book_appointment(doctor_id, date, time)
11. System creates appointment
12. Agent: "Your appointment is confirmed for 10 AM tomorrow"
```

## Scalability Considerations

### Horizontal Scaling

| Component | Scaling Strategy |
|-----------|------------------|
| Orchestrator | Multiple instances behind load balancer, sticky sessions for WebSocket |
| Backend | Multiple instances, stateless design, shared Redis for sessions |
| Workers | Scale based on campaign queue depth |
| PostgreSQL | Read replicas for query distribution |
| Redis | Cluster mode for high availability |

### Latency Optimization

1. **Connection pooling** for database and Redis
2. **Async processing** throughout the pipeline
3. **Edge TTS** for low-latency synthesis
4. **VAD filtering** in STT to reduce processing
5. **Model warmup** on startup
6. **Response streaming** where possible

### Resource Requirements

| Component | CPU | Memory | Notes |
|-----------|-----|--------|-------|
| Backend (per instance) | 2 cores | 4GB | More for large STT models |
| Orchestrator (per instance) | 1 core | 1GB | Light proxy work |
| Redis | 1 core | 2GB | Depends on session count |
| PostgreSQL | 2 cores | 4GB | SSD storage recommended |
| Worker | 1 core | 1GB | Per worker instance |

## Security Considerations

1. **API Authentication**: Implement JWT/API keys
2. **WebSocket Auth**: Token validation on connect
3. **Data Encryption**: TLS for all connections
4. **PHI Protection**: Encrypt patient data at rest
5. **Rate Limiting**: Prevent abuse
6. **Audit Logging**: Track all data access
