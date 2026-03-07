"""
Outbound Campaign Worker.
Background job processor for appointment reminders and follow-up calls.
"""
import asyncio
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy import select, and_, update
from sqlalchemy.ext.asyncio import AsyncSession

from database import async_session_factory
from models import (
    Campaign, CampaignTask, CampaignStatus, TaskStatus,
    CampaignType, Appointment, AppointmentStatus, Patient,
)
from config import settings
from observability import get_logger

logger = get_logger("campaign_worker")


class OutboundCallScheduler:
    """
    Manages outbound call campaigns for:
    - Appointment reminders (24h before)
    - Follow-up checkup reminders
    - Vaccination reminders
    """

    def __init__(self):
        self.is_running = False
        self.max_concurrent = settings.CAMPAIGN_MAX_CONCURRENT
        self.interval = settings.CAMPAIGN_WORKER_INTERVAL

    async def start(self):
        """Start the campaign worker loop."""
        self.is_running = True
        logger.info("campaign_worker_started")
        
        while self.is_running:
            try:
                await self._process_campaigns()
                await asyncio.sleep(self.interval)
            except Exception as e:
                logger.error("campaign_worker_error", error=str(e))
                await asyncio.sleep(10)  # Back off on error

    async def stop(self):
        """Stop the campaign worker."""
        self.is_running = False
        logger.info("campaign_worker_stopped")

    async def _process_campaigns(self):
        """Process pending campaign tasks."""
        async with async_session_factory() as db:
            # Get pending tasks from active campaigns
            query = select(CampaignTask).join(
                Campaign, Campaign.id == CampaignTask.campaign_id
            ).where(
                and_(
                    Campaign.status == CampaignStatus.ACTIVE,
                    CampaignTask.status == TaskStatus.PENDING,
                    CampaignTask.attempts < CampaignTask.max_attempts,
                    # Task is due or overdue
                    (CampaignTask.scheduled_at == None) |
                    (CampaignTask.scheduled_at <= datetime.utcnow()),
                )
            ).limit(self.max_concurrent)
            
            result = await db.execute(query)
            tasks = result.scalars().all()
            
            if not tasks:
                return
            
            logger.info("processing_campaign_tasks", task_count=len(tasks))
            
            # Process tasks concurrently
            await asyncio.gather(*[
                self._process_task(db, task) for task in tasks
            ])
            
            await db.commit()

    async def _process_task(self, db: AsyncSession, task: CampaignTask):
        """Process a single campaign task."""
        try:
            # Mark as in progress
            task.status = TaskStatus.IN_PROGRESS
            task.attempts += 1
            task.last_attempt_at = datetime.utcnow()
            await db.flush()
            
            # Get campaign for message template
            campaign_result = await db.execute(
                select(Campaign).where(Campaign.id == task.campaign_id)
            )
            campaign = campaign_result.scalar_one_or_none()
            
            if not campaign:
                task.status = TaskStatus.FAILED
                return
            
            # Get patient for language preference
            patient_result = await db.execute(
                select(Patient).where(Patient.id == task.patient_id)
            )
            patient = patient_result.scalar_one_or_none()
            
            if not patient:
                task.status = TaskStatus.FAILED
                return
            
            # Prepare outbound call
            # In production, this would integrate with telephony provider
            call_result = await self._initiate_outbound_call(
                patient=patient,
                campaign=campaign,
                task=task,
            )
            
            if call_result["success"]:
                task.status = TaskStatus.COMPLETED
                task.completed_at = datetime.utcnow()
                task.response_summary = call_result.get("summary", "")
                task.outcome = call_result.get("outcome", {})
            else:
                # Retry or fail based on attempts
                if task.attempts >= task.max_attempts:
                    task.status = TaskStatus.FAILED
                else:
                    task.status = TaskStatus.PENDING  # Will retry
            
            logger.info(
                "campaign_task_processed",
                task_id=str(task.id),
                campaign_id=str(task.campaign_id),
                status=task.status,
            )
            
        except Exception as e:
            logger.error(
                "campaign_task_error",
                task_id=str(task.id),
                error=str(e),
            )
            task.status = TaskStatus.FAILED

    async def _initiate_outbound_call(
        self,
        patient: Patient,
        campaign: Campaign,
        task: CampaignTask,
    ) -> dict:
        """
        Initiate an outbound call.
        In production, integrate with telephony provider (Twilio, etc.)
        """
        # Get message in patient's language
        language = patient.preferred_language or "en"
        template = campaign.message_template.get(language) or \
                   campaign.message_template.get("en", "")
        
        # Placeholder for actual telephony integration
        logger.info(
            "outbound_call_initiated",
            patient_phone=patient.phone,
            campaign_type=campaign.campaign_type,
            language=language,
        )
        
        # Simulate successful call
        return {
            "success": True,
            "summary": "Call completed",
            "outcome": {
                "answered": True,
                "language": language,
                "duration_seconds": 60,
            },
        }

    async def create_appointment_reminder_campaign(
        self,
        db: AsyncSession,
        hours_before: int = 24,
    ) -> Campaign:
        """
        Create a campaign for appointment reminders.
        Automatically adds tasks for upcoming appointments.
        """
        campaign = Campaign(
            name=f"Appointment Reminders - {datetime.now().strftime('%Y-%m-%d')}",
            campaign_type=CampaignType.APPOINTMENT_REMINDER,
            message_template={
                "en": "Hello {name}, this is a reminder for your appointment with {doctor} tomorrow at {time}. Reply to confirm or reschedule.",
                "hi": "नमस्ते {name}, यह आपको कल {time} बजे {doctor} के साथ आपकी अपॉइंटमेंट की याद दिलाने के लिए है। पुष्टि करने या फिर से शेड्यूल करने के लिए जवाब दें।",
                "te": "హలో {name}, రేపు {time} కు {doctor} తో మీ అపాయింట్‌మెంట్ గురించి రిమైండర్. నిర్ధారించడానికి లేదా రీషెడ్యూల్ చేయడానికి సమాధానం ఇవ్వండి.",
            },
            status=CampaignStatus.ACTIVE,
        )
        
        db.add(campaign)
        await db.flush()
        
        # Find appointments happening in the next hours_before hours
        reminder_window_start = datetime.utcnow() + timedelta(hours=hours_before - 1)
        reminder_window_end = datetime.utcnow() + timedelta(hours=hours_before + 1)
        
        appointments_result = await db.execute(
            select(Appointment).where(
                and_(
                    Appointment.status.in_([
                        AppointmentStatus.SCHEDULED,
                        AppointmentStatus.CONFIRMED,
                    ]),
                    Appointment.appointment_date >= reminder_window_start.date(),
                    Appointment.appointment_date <= reminder_window_end.date(),
                )
            )
        )
        appointments = appointments_result.scalars().all()
        
        # Create tasks for each appointment
        for apt in appointments:
            task = CampaignTask(
                campaign_id=campaign.id,
                patient_id=apt.patient_id,
                appointment_id=apt.id,
                status=TaskStatus.PENDING,
            )
            db.add(task)
        
        await db.flush()
        
        logger.info(
            "reminder_campaign_created",
            campaign_id=str(campaign.id),
            task_count=len(appointments),
        )
        
        return campaign


# Singleton instance
outbound_scheduler = OutboundCallScheduler()
