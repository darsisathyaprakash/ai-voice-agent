"""
Tool definitions and registry for the Voice Agent.
Provides appointment booking tools for LLM function calling.
"""
import json
from datetime import date, time, datetime, timedelta
from typing import Any, Callable, Optional
from dataclasses import dataclass

from database import async_session_factory
from observability import get_logger

logger = get_logger("agent_tools")


@dataclass
class Tool:
    """Tool definition for LLM function calling."""
    name: str
    description: str
    parameters: dict
    handler: Callable


class ToolRegistry:
    """Registry for available agent tools."""

    def __init__(self):
        self.tools: dict[str, Tool] = {}
        self._register_default_tools()

    def register(self, tool: Tool):
        """Register a new tool."""
        self.tools[tool.name] = tool
        logger.debug("tool_registered", tool_name=tool.name)

    def get_tool_definitions(self) -> list[dict]:
        """Get OpenAI-compatible tool definitions."""
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                },
            }
            for tool in self.tools.values()
        ]

    async def execute(self, tool_name: str, arguments: dict) -> dict:
        """Execute a tool by name."""
        if tool_name not in self.tools:
            return {"success": False, "error": f"Unknown tool: {tool_name}"}
        
        tool = self.tools[tool_name]
        try:
            result = await tool.handler(arguments)
            return result
        except Exception as e:
            logger.error(
                "tool_execution_error",
                tool_name=tool_name,
                error=str(e),
            )
            return {"success": False, "error": str(e)}

    def _register_default_tools(self):
        """Register all default appointment tools."""
        self.register(Tool(
            name="check_availability",
            description="Check available appointment slots for a doctor on a specific date. Use this to find when a doctor is free.",
            parameters={
                "type": "object",
                "properties": {
                    "specialty": {
                        "type": "string",
                        "description": "Doctor specialty (e.g., cardiologist, dermatologist, general_physician, orthopedic, pediatrician)",
                    },
                    "doctor_name": {
                        "type": "string",
                        "description": "Specific doctor name if known (optional)",
                    },
                    "date": {
                        "type": "string",
                        "description": "Date to check (YYYY-MM-DD format, or 'today', 'tomorrow', 'next monday', etc.)",
                    },
                },
                "required": ["specialty", "date"],
            },
            handler=check_availability_handler,
        ))

        self.register(Tool(
            name="book_appointment",
            description="Book a new appointment for the patient. Always confirm with the patient before calling this.",
            parameters={
                "type": "object",
                "properties": {
                    "doctor_id": {
                        "type": "string",
                        "description": "UUID of the doctor",
                    },
                    "date": {
                        "type": "string",
                        "description": "Appointment date (YYYY-MM-DD)",
                    },
                    "time": {
                        "type": "string",
                        "description": "Appointment time (HH:MM format)",
                    },
                    "reason": {
                        "type": "string",
                        "description": "Reason for the appointment",
                    },
                },
                "required": ["doctor_id", "date", "time"],
            },
            handler=book_appointment_handler,
        ))

        self.register(Tool(
            name="cancel_appointment",
            description="Cancel an existing appointment. Confirm with patient before canceling.",
            parameters={
                "type": "object",
                "properties": {
                    "appointment_id": {
                        "type": "string",
                        "description": "UUID of the appointment to cancel",
                    },
                    "reason": {
                        "type": "string",
                        "description": "Reason for cancellation (optional)",
                    },
                },
                "required": ["appointment_id"],
            },
            handler=cancel_appointment_handler,
        ))

        self.register(Tool(
            name="reschedule_appointment",
            description="Reschedule an existing appointment to a new date/time.",
            parameters={
                "type": "object",
                "properties": {
                    "appointment_id": {
                        "type": "string",
                        "description": "UUID of the appointment to reschedule",
                    },
                    "new_date": {
                        "type": "string",
                        "description": "New appointment date (YYYY-MM-DD)",
                    },
                    "new_time": {
                        "type": "string",
                        "description": "New appointment time (HH:MM format)",
                    },
                },
                "required": ["appointment_id", "new_date", "new_time"],
            },
            handler=reschedule_appointment_handler,
        ))

        self.register(Tool(
            name="get_patient_appointments",
            description="Get the patient's upcoming or past appointments.",
            parameters={
                "type": "object",
                "properties": {
                    "upcoming_only": {
                        "type": "boolean",
                        "description": "If true, only return upcoming appointments",
                        "default": True,
                    },
                },
                "required": [],
            },
            handler=get_patient_appointments_handler,
        ))

        self.register(Tool(
            name="find_doctors",
            description="Find doctors by specialty or name.",
            parameters={
                "type": "object",
                "properties": {
                    "specialty": {
                        "type": "string",
                        "description": "Doctor specialty to search for",
                    },
                    "language": {
                        "type": "string",
                        "description": "Preferred doctor language (en, hi, te)",
                    },
                },
                "required": ["specialty"],
            },
            handler=find_doctors_handler,
        ))


# ── Tool Handlers ──

def _parse_date(date_str: str) -> date:
    """Parse flexible date string to date object."""
    date_str = date_str.lower().strip()
    today = date.today()
    
    if date_str == "today":
        return today
    elif date_str == "tomorrow":
        return today + timedelta(days=1)
    elif date_str.startswith("next "):
        day_name = date_str[5:]
        days = {
            "monday": 0, "tuesday": 1, "wednesday": 2,
            "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6,
        }
        if day_name in days:
            target_day = days[day_name]
            current_day = today.weekday()
            days_ahead = target_day - current_day
            if days_ahead <= 0:
                days_ahead += 7
            return today + timedelta(days=days_ahead)
    
    # Try parsing as YYYY-MM-DD
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        pass
    
    # Try parsing as DD/MM/YYYY
    try:
        return datetime.strptime(date_str, "%d/%m/%Y").date()
    except ValueError:
        pass
    
    # Default to today if parsing fails
    return today


async def check_availability_handler(args: dict) -> dict:
    """Handle check_availability tool call."""
    from scheduler.appointment_engine import appointment_engine
    from sqlalchemy import select
    from models import Doctor
    
    specialty = args.get("specialty", "")
    date_str = args.get("date", "today")
    target_date = _parse_date(date_str)
    
    async with async_session_factory() as db:
        # Find doctors by specialty
        query = select(Doctor).where(
            Doctor.is_active == True,
            Doctor.specialization.ilike(f"%{specialty}%"),
        )
        result = await db.execute(query)
        doctors = result.scalars().all()
        
        if not doctors:
            return {
                "success": False,
                "error": f"No doctors found with specialty: {specialty}",
                "suggestions": ["cardiologist", "dermatologist", "general_physician", "orthopedic", "pediatrician"],
            }
        
        # Get availability for each doctor
        availability = []
        for doctor in doctors:
            slots = await appointment_engine.get_available_slots(
                db, str(doctor.id), target_date
            )
            if slots:
                availability.append({
                    "doctor_id": str(doctor.id),
                    "doctor_name": f"Dr. {doctor.first_name} {doctor.last_name}",
                    "specialization": doctor.specialization,
                    "date": str(target_date),
                    "available_slots": [
                        {"time": s["start_time"].strftime("%H:%M")}
                        for s in slots[:5]  # Limit to 5 slots
                    ],
                    "total_slots": len(slots),
                })
        
        if not availability:
            # No availability, suggest next few days
            return {
                "success": True,
                "available": False,
                "message": f"No slots available on {target_date}",
                "suggest_alternate_dates": True,
            }
        
        return {
            "success": True,
            "available": True,
            "date": str(target_date),
            "doctors": availability,
        }


async def book_appointment_handler(args: dict) -> dict:
    """Handle book_appointment tool call."""
    from scheduler.appointment_engine import appointment_engine
    from memory.redis_memory.session_memory import session_memory
    
    doctor_id = args.get("doctor_id")
    date_str = args.get("date")
    time_str = args.get("time")
    reason = args.get("reason", "")
    session_id = args.get("session_id")
    language = args.get("language", "en")
    
    if not all([doctor_id, date_str, time_str]):
        return {"success": False, "error": "Missing required fields"}
    
    # Get patient from session
    session = await session_memory.get_session(session_id) if session_id else {}
    patient_id = session.get("patient_id")
    
    if not patient_id:
        return {
            "success": False,
            "error": "Patient not identified. Please provide your phone number.",
        }
    
    target_date = _parse_date(date_str)
    target_time = datetime.strptime(time_str, "%H:%M").time()
    
    async with async_session_factory() as db:
        result = await appointment_engine.book_appointment(
            db=db,
            patient_id=patient_id,
            doctor_id=doctor_id,
            appointment_date=target_date,
            start_time=target_time,
            reason=reason,
            language=language,
        )
        await db.commit()
    
    if result["success"]:
        apt = result["appointment"]
        return {
            "success": True,
            "appointment_id": str(apt.id),
            "doctor_name": result.get("doctor_name", "the doctor"),
            "date": str(apt.appointment_date),
            "time": str(apt.start_time),
            "message": "Appointment booked successfully",
        }
    
    return result


async def cancel_appointment_handler(args: dict) -> dict:
    """Handle cancel_appointment tool call."""
    from scheduler.appointment_engine import appointment_engine
    
    appointment_id = args.get("appointment_id")
    reason = args.get("reason", "Cancelled by patient")
    
    if not appointment_id:
        return {"success": False, "error": "Missing appointment ID"}
    
    async with async_session_factory() as db:
        result = await appointment_engine.cancel_appointment(
            db=db,
            appointment_id=appointment_id,
            reason=reason,
        )
        await db.commit()
    
    return result


async def reschedule_appointment_handler(args: dict) -> dict:
    """Handle reschedule_appointment tool call."""
    from scheduler.appointment_engine import appointment_engine
    
    appointment_id = args.get("appointment_id")
    new_date_str = args.get("new_date")
    new_time_str = args.get("new_time")
    
    if not all([appointment_id, new_date_str, new_time_str]):
        return {"success": False, "error": "Missing required fields"}
    
    new_date = _parse_date(new_date_str)
    new_time = datetime.strptime(new_time_str, "%H:%M").time()
    
    async with async_session_factory() as db:
        result = await appointment_engine.reschedule_appointment(
            db=db,
            appointment_id=appointment_id,
            new_date=new_date,
            new_time=new_time,
        )
        await db.commit()
    
    return result


async def get_patient_appointments_handler(args: dict) -> dict:
    """Handle get_patient_appointments tool call."""
    from memory.persistent_memory.persistent_memory import persistent_memory
    from memory.redis_memory.session_memory import session_memory
    
    session_id = args.get("session_id")
    upcoming_only = args.get("upcoming_only", True)
    
    session = await session_memory.get_session(session_id) if session_id else {}
    patient_id = session.get("patient_id")
    
    if not patient_id:
        return {
            "success": False,
            "error": "Patient not identified",
        }
    
    async with async_session_factory() as db:
        if upcoming_only:
            appointments = await persistent_memory.get_upcoming_appointments(db, patient_id)
        else:
            appointments = await persistent_memory.get_appointment_history(db, patient_id)
    
    return {
        "success": True,
        "appointments": [
            {
                "id": str(apt.id),
                "doctor_id": str(apt.doctor_id),
                "date": str(apt.appointment_date),
                "time": str(apt.start_time),
                "status": apt.status,
                "reason": apt.reason,
            }
            for apt in appointments
        ],
    }


async def find_doctors_handler(args: dict) -> dict:
    """Handle find_doctors tool call."""
    from sqlalchemy import select
    from models import Doctor
    
    specialty = args.get("specialty", "")
    language = args.get("language")
    
    async with async_session_factory() as db:
        query = select(Doctor).where(
            Doctor.is_active == True,
            Doctor.specialization.ilike(f"%{specialty}%"),
        )
        
        if language:
            query = query.where(Doctor.languages.contains([language]))
        
        result = await db.execute(query)
        doctors = result.scalars().all()
    
    if not doctors:
        return {
            "success": True,
            "doctors": [],
            "message": f"No doctors found for specialty: {specialty}",
        }
    
    return {
        "success": True,
        "doctors": [
            {
                "id": str(d.id),
                "name": f"Dr. {d.first_name} {d.last_name}",
                "specialization": d.specialization,
                "department": d.department,
                "languages": d.languages,
                "consultation_minutes": d.consultation_duration_minutes,
            }
            for d in doctors
        ],
    }


# Singleton instance
tool_registry = ToolRegistry()
