# API Documentation

## Overview

The Voice AI Agent exposes two types of APIs:

1. **REST API** - For management operations (patients, doctors, appointments, campaigns)
2. **WebSocket API** - For real-time voice conversations

## Base URLs

- **Backend (Python)**: `http://localhost:8000`
- **Orchestrator (Node.js)**: `http://localhost:3000`

---

## REST API

### Health & Metrics

#### GET /api/health
Basic health check.

**Response:**
```json
{
  "status": "healthy",
  "service": "Voice AI Agent"
}
```

#### GET /api/health/ready
Readiness probe - checks all dependencies.

**Response:**
```json
{
  "status": "ready",
  "checks": {
    "database": true,
    "redis": true
  }
}
```

#### GET /api/metrics
Latency metrics.

**Response:**
```json
{
  "latency_targets": {
    "stt_ms": 150,
    "llm_ms": 200,
    "tts_ms": 100,
    "total_ms": 450
  }
}
```

---

### Patients

#### POST /api/patients
Create a new patient.

**Request Body:**
```json
{
  "first_name": "John",
  "last_name": "Doe",
  "phone": "+1234567890",
  "email": "john@example.com",
  "preferred_language": "en"
}
```

**Response:** `201 Created`
```json
{
  "id": "uuid",
  "first_name": "John",
  "last_name": "Doe",
  "phone": "+1234567890",
  "email": "john@example.com",
  "preferred_language": "en",
  "preferences": {}
}
```

#### GET /api/patients/{patient_id}
Get patient by ID.

**Response:** `200 OK`
```json
{
  "id": "uuid",
  "first_name": "John",
  "last_name": "Doe",
  "phone": "+1234567890",
  "preferred_language": "en"
}
```

#### GET /api/patients/phone/{phone}
Get patient by phone number.

**Response:** `200 OK` - Same as above

#### PATCH /api/patients/{patient_id}
Update patient information.

**Request Body:**
```json
{
  "preferred_language": "hi"
}
```

#### GET /api/patients/{patient_id}/appointments
Get patient's appointments.

**Query Parameters:**
- `upcoming_only` (boolean, default: false)
- `limit` (integer, default: 10)

**Response:**
```json
{
  "patient_id": "uuid",
  "appointments": [
    {
      "id": "uuid",
      "doctor_id": "uuid",
      "date": "2024-01-20",
      "start_time": "10:00:00",
      "end_time": "10:30:00",
      "status": "scheduled",
      "reason": "Checkup"
    }
  ]
}
```

---

### Doctors

#### GET /api/doctors
List all doctors.

**Query Parameters:**
- `specialization` (string) - Filter by specialty
- `language` (string) - Filter by spoken language
- `active_only` (boolean, default: true)

**Response:**
```json
[
  {
    "id": "uuid",
    "first_name": "Priya",
    "last_name": "Sharma",
    "specialization": "cardiologist",
    "department": "Cardiology",
    "consultation_duration_minutes": 30,
    "is_active": true,
    "languages": ["en", "hi"]
  }
]
```

#### GET /api/doctors/specializations
Get list of available specializations.

**Response:**
```json
{
  "specializations": [
    "cardiologist",
    "dermatologist",
    "general_physician",
    "orthopedic",
    "pediatrician"
  ]
}
```

#### GET /api/doctors/{doctor_id}
Get doctor by ID.

#### GET /api/doctors/{doctor_id}/schedule
Get doctor's weekly schedule.

**Response:**
```json
[
  {
    "id": "uuid",
    "day_of_week": 0,
    "start_time": "09:00:00",
    "end_time": "17:00:00",
    "is_available": true,
    "slot_duration_minutes": 30
  }
]
```

#### GET /api/doctors/{doctor_id}/availability/{date}
Get available slots for a specific date.

**Response:**
```json
{
  "doctor_id": "uuid",
  "doctor_name": "Dr. Priya Sharma",
  "date": "2024-01-20",
  "available_slots": [
    { "start_time": "09:00", "end_time": "09:30" },
    { "start_time": "09:30", "end_time": "10:00" },
    { "start_time": "11:00", "end_time": "11:30" }
  ],
  "slot_count": 3
}
```

---

### Appointments

#### POST /api/appointments
Book a new appointment.

**Request Body:**
```json
{
  "patient_id": "uuid",
  "doctor_id": "uuid",
  "appointment_date": "2024-01-20",
  "start_time": "10:00:00",
  "reason": "Regular checkup",
  "language_used": "en"
}
```

**Response:** `201 Created`
```json
{
  "id": "uuid",
  "patient_id": "uuid",
  "doctor_id": "uuid",
  "appointment_date": "2024-01-20",
  "start_time": "10:00:00",
  "end_time": "10:30:00",
  "status": "scheduled"
}
```

**Error Response:** `409 Conflict`
```json
{
  "detail": {
    "error": "Requested slot is not available",
    "alternatives": [
      { "time": "10:30" },
      { "time": "11:00" }
    ]
  }
}
```

#### GET /api/appointments/{appointment_id}
Get appointment by ID.

#### POST /api/appointments/{appointment_id}/cancel
Cancel an appointment.

**Query Parameters:**
- `reason` (string, optional)

**Response:**
```json
{
  "success": true,
  "message": "Appointment cancelled successfully",
  "appointment_id": "uuid"
}
```

#### POST /api/appointments/{appointment_id}/reschedule
Reschedule an appointment.

**Request Body:**
```json
{
  "new_date": "2024-01-21",
  "new_time": "14:00:00"
}
```

#### POST /api/appointments/{appointment_id}/confirm
Confirm a scheduled appointment.

**Response:**
```json
{
  "appointment_id": "uuid",
  "status": "confirmed"
}
```

#### GET /api/appointments/check-availability
Check if a specific slot is available.

**Query Parameters:**
- `doctor_id` (uuid, required)
- `target_date` (date, required)
- `start_time` (time, required)

**Response:**
```json
{
  "doctor_id": "uuid",
  "date": "2024-01-20",
  "time": "10:00:00",
  "available": true
}
```

---

### Campaigns

#### POST /api/campaigns
Create a new campaign.

**Request Body:**
```json
{
  "name": "January Appointment Reminders",
  "campaign_type": "appointment_reminder",
  "message_template": {
    "en": "Hello {name}, reminder for your appointment tomorrow at {time}",
    "hi": "नमस्ते {name}, कल {time} पर आपकी अपॉइंटमेंट की याद",
    "te": "హలో {name}, రేపు {time} కు మీ అపాయింట్‌మెంట్ రిమైండర్"
  },
  "scheduled_at": "2024-01-19T08:00:00Z"
}
```

**Campaign Types:**
- `appointment_reminder`
- `follow_up_checkup`
- `vaccination_reminder`
- `general_notification`

#### GET /api/campaigns
List campaigns.

**Query Parameters:**
- `status` (string) - Filter by status
- `campaign_type` (string) - Filter by type
- `limit` (integer, default: 50)

#### GET /api/campaigns/{campaign_id}
Get campaign details.

#### POST /api/campaigns/{campaign_id}/start
Start a campaign.

#### POST /api/campaigns/{campaign_id}/pause
Pause an active campaign.

#### GET /api/campaigns/{campaign_id}/tasks
Get tasks for a campaign.

#### GET /api/campaigns/{campaign_id}/stats
Get campaign statistics.

**Response:**
```json
{
  "campaign_id": "uuid",
  "campaign_name": "January Reminders",
  "status": "active",
  "total_tasks": 100,
  "completed": 75,
  "failed": 5,
  "pending": 15,
  "in_progress": 5,
  "completion_rate": 75.0,
  "task_breakdown": {
    "pending": 15,
    "in_progress": 5,
    "completed": 75,
    "failed": 5
  }
}
```

---

## WebSocket API

### Connection

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/voice');
// or through orchestrator
const ws = new WebSocket('ws://localhost:3000/ws/voice');
```

### Protocol

#### Client → Server Messages

**Initialize Session:**
```json
{
  "type": "init",
  "patient_phone": "+1234567890",
  "language": "en"
}
```

**End of User Speech:**
```json
{
  "type": "end_turn"
}
```

**User Interrupted:**
```json
{
  "type": "barge_in"
}
```

**Text Input (for testing):**
```json
{
  "type": "text_input",
  "text": "I want to book an appointment with a cardiologist"
}
```

**End Session:**
```json
{
  "type": "end_session"
}
```

**Audio Data:**
Send binary audio chunks directly.

#### Server → Client Messages

**Session Started:**
```json
{
  "type": "session_started",
  "session_id": "uuid",
  "language": "en"
}
```

**Response Text:**
```json
{
  "type": "response_text",
  "text": "I'd be happy to help you book an appointment...",
  "language": "en"
}
```

**Audio Response:**
Binary audio data (MP3 format).

**Turn Complete:**
```json
{
  "type": "turn_complete",
  "latency": {
    "session_id": "uuid",
    "stages": {
      "stt": 120.5,
      "llm": 180.3,
      "tts": 80.2
    },
    "total_ms": 381.0,
    "target_ms": 450,
    "within_target": true
  }
}
```

**Session Ended:**
```json
{
  "type": "session_ended"
}
```

**Error:**
```json
{
  "type": "error",
  "message": "Something went wrong. Please try again."
}
```

---

## Error Codes

| Status | Description |
|--------|-------------|
| 400 | Bad Request - Invalid input |
| 404 | Not Found - Resource doesn't exist |
| 409 | Conflict - Slot unavailable / duplicate |
| 500 | Internal Server Error |
| 503 | Service Unavailable - Dependencies down |

## Rate Limits

- REST API: 100 requests/minute per IP
- WebSocket: 1 connection per session

## Authentication

Currently no authentication required. For production, implement:
- API keys for REST endpoints
- JWT tokens for WebSocket connections
