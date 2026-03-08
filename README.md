# 🎙️ Voice AI Agent - Clinical Appointment System

[![Tests](https://img.shields.io/badge/tests-89%2F89%20passing-brightgreen)](./backend/tests)
[![Docker](https://img.shields.io/badge/docker-ready-blue)](./docker-compose.yml)
[![Python](https://img.shields.io/badge/python-3.11+-blue)](./backend)
[![TypeScript](https://img.shields.io/badge/typescript-5.0+-blue)](./frontend)
[![License](https://img.shields.io/badge/license-MIT-green)](./LICENSE)

A production-grade voice AI system that enables real-time voice conversations with patients in multiple languages (English, Hindi, Tamil) for managing clinical appointments.

---

## 📸 Dashboard Screenshots

### System Dashboard
![Dashboard](docs/screenshots/dashboard.png)
*Real-time system health monitoring with database and Redis status*

### Patient Management  
![Patients](docs/screenshots/patients.png)
*Add and manage patient records with multilingual preferences*

### Appointment Booking
![Appointments](docs/screenshots/appointments.png)
*Schedule, reschedule, and cancel appointments*

### Campaign Management
![Campaigns](docs/screenshots/campaigns.png)
*Create multilingual outbound call campaigns*

---

## 🎯 Key Features

- **Real-time Voice Processing**: Sub-450ms latency from speech end to audio response
- **Multilingual Support**: English, Hindi, and Tamil with automatic language detection
- **Appointment Management**: Book, reschedule, cancel appointments with conflict detection
- **Memory Systems**: Session memory (Redis) for conversations, persistent memory (PostgreSQL) for patient data
- **Outbound Campaigns**: Automated appointment reminders and follow-ups
- **Production Ready**: Docker containerized, scalable architecture

---

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose
- OpenAI API key (for GPT-4)

### One-Command Deployment

```bash
# Clone the repository
git clone https://github.com/darsisathyaprakash/ai-voice-agent.git
cd ai-voice-agent

# Configure environment
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY

# Start all services
docker compose up --build -d
```



---

## ✅ Test Results

```
============================= test session starts =============================
platform win32 -- Python 3.13.5, pytest-8.3.4
collected 89 items

tests/test_api_campaigns.py ........                                     [  8%]
tests/test_api_doctors.py .....                                          [ 14%]
tests/test_api_health.py ....                                            [ 18%]
tests/test_api_patients.py .....                                         [ 24%]
tests/test_appointment_engine.py ........                                [ 33%]
tests/test_multilingual.py ..............                                [ 49%]
tests/test_session_memory.py ..........                                  [ 60%]
tests/test_unit.py ..................                                    [ 80%]
tests/test_voice_agent.py .......                                        [100%]

============================= 89 passed ======================================
```

---

## 📊 System Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           Client Application                             │
│                    (Mobile App / Web / Voice Gateway)                    │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │ WebSocket
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     Node.js Orchestrator (Port 3000)                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌──────────────┐   │
│  │   Express   │  │  WebSocket  │  │   Latency   │  │    Redis     │   │
│  │   Router    │  │    Proxy    │  │   Monitor   │  │   Client     │   │
│  └─────────────┘  └─────────────┘  └─────────────┘  └──────────────┘   │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │ WebSocket / HTTP
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    Python Backend (FastAPI - Port 8000)                  │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                      Voice Pipeline                               │  │
│  │  Audio → STT (Whisper) → Lang Detect → LLM Agent → TTS (Edge)    │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌──────────────┐   │
│  │    Agent    │  │  Scheduler  │  │   Memory    │  │   Campaign   │   │
│  │   (Tools)   │  │   Engine    │  │   Layer     │  │   Worker     │   │
│  └─────────────┘  └─────────────┘  └─────────────┘  └──────────────┘   │
└──────────┬──────────────────────────────┬───────────────────────────────┘
           │                              │
           ▼                              ▼
    ┌─────────────┐               ┌─────────────┐
    │ PostgreSQL  │               │    Redis    │
    │  (Data)     │               │  (Sessions) │
    └─────────────┘               └─────────────┘
```

## 📁 Project Structure

```
voice-ai-agent/
├── backend/                    # Python FastAPI Backend
│   ├── api/routes/            # REST API endpoints
│   ├── websocket/             # WebSocket voice handler
│   ├── agent/                 # LLM agent with tools
│   ├── services/              # STT, TTS, language detection
│   ├── scheduler/             # Appointment engine
│   ├── campaigns/             # Outbound call system
│   ├── config.py              # Configuration
│   ├── database.py            # Database connection
│   ├── models.py              # SQLAlchemy ORM models
│   ├── observability.py       # Logging & metrics
│   └── main.py                # Application entry point
├── frontend/                  # React + TypeScript Dashboard
│   ├── src/
│   │   ├── App.tsx            # Main application
│   │   ├── api.ts             # API client
│   │   └── index.css          # TailwindCSS styles
│   ├── package.json
│   └── vite.config.ts         # Vite configuration
├── orchestrator/              # Node.js API gateway
│   └── src/
│       ├── routes/            # API routes
│       ├── services/          # Backend & Redis clients
│       ├── websocket/         # WebSocket proxy
│       └── utils/             # Logging, latency tracking
├── memory/                    # Memory implementations
│   ├── redis_memory/          # Session memory (Redis)
│   └── persistent_memory/     # Patient data (PostgreSQL)
├── database/
│   └── postgres_schema/       # SQL schema & migrations
├── docker/                    # Container configuration
│   ├── Dockerfile.backend
│   ├── Dockerfile.frontend
│   ├── Dockerfile.orchestrator
│   ├── Dockerfile.worker
│   ├── nginx.conf
│   └── docker-compose.yml
└── docs/                      # Documentation
```

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose
- OpenAI API key (for GPT-4)

### 1. Clone and Configure

```bash
cd voice-ai-agent
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY
```

### 2. Start Services

```bash
cd docker
docker-compose up -d
```


```





Dashboard Features:
- System health monitoring
- Patient management
- Doctor directory
- Appointment scheduling
- Campaign management

### 5. Connect via WebSocket

```javascript
const ws = new WebSocket('ws://localhost:3000/ws/voice');

// Initialize session
ws.send(JSON.stringify({
  type: 'init',
  patient_phone: '+1234567890',
  language: 'en'
}));

// Send audio chunks
ws.send(audioBuffer);

// Signal end of speech
ws.send(JSON.stringify({ type: 'end_turn' }));
```

## 🎙️ Voice Pipeline

### Latency Targets

| Stage | Target | Description |
|-------|--------|-------------|
| STT | <150ms | Speech-to-text transcription |
| LLM | <200ms | Agent reasoning & tool calling |
| TTS | <100ms | Text-to-speech synthesis |
| **Total** | **<450ms** | End-to-end response time |

### Pipeline Flow

```
User Audio
    │
    ▼ [WebSocket streaming]
┌─────────────────────────────┐
│  Speech-to-Text (Whisper)   │  ◄── 150ms target
│  - VAD filtering            │
│  - Language hints           │
└─────────────────────────────┘
    │
    ▼
┌─────────────────────────────┐
│    Language Detection       │
│  - Auto-detect from text    │
│  - Persist preference       │
└─────────────────────────────┘
    │
    ▼
┌─────────────────────────────┐
│      LLM Agent (GPT-4)      │  ◄── 200ms target
│  - Tool orchestration       │
│  - Conversation context     │
└─────────────────────────────┘
    │
    ▼
┌─────────────────────────────┐
│    Tool Execution           │
│  - checkAvailability        │
│  - bookAppointment          │
│  - cancelAppointment        │
│  - rescheduleAppointment    │
└─────────────────────────────┘
    │
    ▼
┌─────────────────────────────┐
│   Text-to-Speech (Edge)     │  ◄── 100ms target
│  - Multilingual voices      │
│  - Streaming output         │
└─────────────────────────────┘
    │
    ▼
Audio Response
```

## 🔧 Agent Tools

The LLM agent can call these tools:

| Tool | Description |
|------|-------------|
| `check_availability` | Check doctor availability for a date |
| `book_appointment` | Book a new appointment |
| `cancel_appointment` | Cancel existing appointment |
| `reschedule_appointment` | Move appointment to new time |
| `get_patient_appointments` | List patient's appointments |
| `find_doctors` | Search doctors by specialty |

### Example Tool Call

```json
{
  "action": "check_availability",
  "specialty": "cardiologist",
  "date": "tomorrow"
}
```

## 🌐 Supported Languages

| Language | Code | TTS Voice |
|----------|------|-----------|
| English | en | en-US-AriaNeural |
| Hindi | hi | hi-IN-SwaraNeural |
| Tamil | ta | ta-IN-PallaviNeural |

## 💾 Memory Architecture

### Session Memory (Redis)

```
session:{session_id}           → Session metadata (hash)
session:{session_id}:history   → Conversation history (list)
session:{session_id}:state     → Conversation state (hash)
```

- TTL: 30 minutes (sliding window)
- Stores: intent, language, pending confirmations

### Persistent Memory (PostgreSQL)

- Patient profiles
- Appointment history
- Language preferences
- Doctor records

## 📡 API Reference

### REST Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Health check |
| GET | `/api/patients/{id}` | Get patient |
| POST | `/api/patients` | Create patient |
| GET | `/api/doctors` | List doctors |
| GET | `/api/doctors/{id}/availability/{date}` | Get slots |
| POST | `/api/appointments` | Book appointment |
| POST | `/api/appointments/{id}/cancel` | Cancel |
| POST | `/api/appointments/{id}/reschedule` | Reschedule |
| GET | `/api/campaigns` | List campaigns |
| GET | `/api/campaigns/{id}/stats` | Campaign stats |

### WebSocket Protocol

```javascript
// Client → Server
{ type: 'init', patient_phone: '...', language: 'en' }
{ type: 'end_turn' }           // Signal end of user speech
{ type: 'barge_in' }           // User interrupted
{ type: 'text_input', text: '...' }  // Text input (testing)
{ type: 'end_session' }        // Close session
[Binary: Audio data]           // Audio chunks

// Server → Client
{ type: 'session_started', session_id: '...', language: '...' }
{ type: 'response_text', text: '...', language: '...' }
[Binary: Audio response]
{ type: 'turn_complete', latency: {...} }
{ type: 'session_ended' }
{ type: 'error', message: '...' }
```

## 📊 Database Schema

### Core Tables

- `patients` - Patient records
- `doctors` - Doctor profiles
- `doctor_schedule` - Weekly availability
- `appointments` - Booked appointments
- `campaigns` - Outbound campaigns
- `campaign_tasks` - Individual call tasks
- `conversation_logs` - Analytics

See [001_init.sql](database/postgres_schema/001_init.sql) for full schema.

## 🏃 Running in Development

### Backend Only

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
```

### Orchestrator Only

```bash
cd orchestrator
npm install
npm run dev
```

### Docker Development

```bash
cd docker
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up
```

## 📈 Monitoring

### Metrics Endpoint

```bash
curl http://localhost:3000/api/metrics
```

Returns:
```json
{
  "avgTotal": 320,
  "avgStages": { "stt": 120, "llm": 150, "tts": 50 },
  "p95Total": 420,
  "violationRate": 5.5
}
```

### Structured Logging

All components use JSON-structured logging:

```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "level": "info",
  "component": "voice_agent",
  "session_id": "abc-123",
  "event": "turn_completed",
  "total_ms": 320
}
```

## 🚀 Production Deployment

### Scaling Recommendations

| Component | Instances | Notes |
|-----------|-----------|-------|
| Backend | 2-4 | Behind load balancer |
| Orchestrator | 2-4 | Sticky sessions for WebSocket |
| Campaign Worker | 1-2 | Based on task volume |
| PostgreSQL | 1 (primary) | + read replicas |
| Redis | 1 (cluster) | For high availability |

### Environment Variables

See [.env.example](.env.example) for all configuration options.

Critical settings for production:
- `APP_ENV=production`
- `DEBUG=false`
- `LOG_LEVEL=INFO`
- `DATABASE_POOL_SIZE=50`

## 📝 License

MIT License - See LICENSE for details.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests: `pytest` (backend), `npm test` (orchestrator)
5. Submit a pull request

## 📧 Support

For issues and questions, please open a GitHub issue.
