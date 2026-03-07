"""
Celery task definitions for background campaign processing.
Alternative to the async worker for distributed execution.
"""
from celery import Celery
from datetime import datetime
from config import settings

# Initialize Celery
celery_app = Celery(
    "voice_ai_campaigns",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,  # 5 minute timeout
    worker_prefetch_multiplier=1,
    task_acks_late=True,
)


@celery_app.task(bind=True, max_retries=3)
def process_campaign_task(self, task_id: str):
    """
    Process a single campaign task.
    Called by the scheduler or directly.
    """
    import asyncio
    from database import async_session_factory
    from sqlalchemy import select
    from models import CampaignTask
    
    async def _process():
        async with async_session_factory() as db:
            result = await db.execute(
                select(CampaignTask).where(CampaignTask.id == task_id)
            )
            task = result.scalar_one_or_none()
            
            if not task:
                return {"success": False, "error": "Task not found"}
            
            # Process the task (simplified version)
            # Full implementation in outbound_scheduler.py
            return {"success": True, "task_id": task_id}
    
    try:
        result = asyncio.run(_process())
        return result
    except Exception as e:
        self.retry(countdown=60)


@celery_app.task
def schedule_appointment_reminders():
    """
    Periodic task to create appointment reminder campaigns.
    Run daily to add reminders for next day's appointments.
    """
    import asyncio
    from database import async_session_factory
    from campaigns.outbound_scheduler import outbound_scheduler
    
    async def _schedule():
        async with async_session_factory() as db:
            campaign = await outbound_scheduler.create_appointment_reminder_campaign(
                db, hours_before=24
            )
            await db.commit()
            return {"campaign_id": str(campaign.id)}
    
    return asyncio.run(_schedule())


@celery_app.task
def cleanup_old_campaigns():
    """
    Periodic task to clean up completed/cancelled campaigns.
    Archives old campaign data.
    """
    import asyncio
    from datetime import timedelta
    from database import async_session_factory
    from sqlalchemy import update
    from models import Campaign, CampaignStatus
    
    async def _cleanup():
        cutoff = datetime.utcnow() - timedelta(days=30)
        
        async with async_session_factory() as db:
            # Mark old campaigns as completed
            await db.execute(
                update(Campaign)
                .where(
                    Campaign.status == CampaignStatus.ACTIVE,
                    Campaign.created_at < cutoff,
                )
                .values(
                    status=CampaignStatus.COMPLETED,
                    completed_at=datetime.utcnow(),
                )
            )
            await db.commit()
        
        return {"cleaned": True}
    
    return asyncio.run(_cleanup())


# Celery Beat schedule for periodic tasks
celery_app.conf.beat_schedule = {
    "daily-appointment-reminders": {
        "task": "campaigns.celery_tasks.schedule_appointment_reminders",
        "schedule": 86400.0,  # Once per day
        "options": {"queue": "campaigns"},
    },
    "weekly-cleanup": {
        "task": "campaigns.celery_tasks.cleanup_old_campaigns",
        "schedule": 604800.0,  # Once per week
    },
}
