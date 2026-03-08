"""
Campaign management API endpoints for outbound calls.
"""
from typing import Optional, List
from datetime import datetime
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from pydantic import BaseModel, Field

from database import get_db
from models import Campaign, CampaignTask, CampaignType, CampaignStatus, TaskStatus
from observability import get_logger

router = APIRouter()
logger = get_logger("campaigns_api")


# ── Pydantic Schemas ──

class CampaignCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=256)
    campaign_type: CampaignType
    message_template: dict = Field(
        ...,
        description="Templates per language: {'en': '...', 'hi': '...', 'ta': '...'}",
    )
    target_criteria: Optional[dict] = None
    scheduled_at: Optional[datetime] = None


class CampaignResponse(BaseModel):
    id: UUID
    name: str
    campaign_type: str
    status: str
    message_template: dict
    target_criteria: Optional[dict]
    scheduled_at: Optional[datetime]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class TaskResponse(BaseModel):
    id: UUID
    campaign_id: UUID
    patient_id: UUID
    appointment_id: Optional[UUID]
    status: str
    attempts: int
    max_attempts: int
    response_summary: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# ── Endpoints ──

@router.post("", response_model=CampaignResponse, status_code=201)
async def create_campaign(
    campaign_data: CampaignCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new outbound campaign."""
    campaign = Campaign(
        name=campaign_data.name,
        campaign_type=campaign_data.campaign_type,
        message_template=campaign_data.message_template,
        target_criteria=campaign_data.target_criteria or {},
        scheduled_at=campaign_data.scheduled_at,
    )
    
    db.add(campaign)
    await db.flush()
    
    logger.info(
        "campaign_created",
        campaign_id=str(campaign.id),
        campaign_type=campaign_data.campaign_type,
    )
    
    return campaign


@router.get("", response_model=List[CampaignResponse])
async def list_campaigns(
    status: Optional[CampaignStatus] = None,
    campaign_type: Optional[CampaignType] = None,
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List campaigns with optional filtering."""
    query = select(Campaign).order_by(Campaign.created_at.desc())
    
    if status:
        query = query.where(Campaign.status == status)
    
    if campaign_type:
        query = query.where(Campaign.campaign_type == campaign_type)
    
    query = query.limit(limit)
    
    result = await db.execute(query)
    campaigns = result.scalars().all()
    
    return campaigns


@router.get("/{campaign_id}", response_model=CampaignResponse)
async def get_campaign(
    campaign_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get campaign by ID."""
    result = await db.execute(
        select(Campaign).where(Campaign.id == campaign_id)
    )
    campaign = result.scalar_one_or_none()
    
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    return campaign


@router.post("/{campaign_id}/start")
async def start_campaign(
    campaign_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Start an existing campaign."""
    result = await db.execute(
        select(Campaign).where(Campaign.id == campaign_id)
    )
    campaign = result.scalar_one_or_none()
    
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    if campaign.status not in [CampaignStatus.DRAFT, CampaignStatus.PAUSED]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot start campaign with status: {campaign.status}",
        )
    
    campaign.status = CampaignStatus.ACTIVE
    campaign.started_at = datetime.utcnow()
    await db.flush()
    
    logger.info("campaign_started", campaign_id=str(campaign_id))
    
    return {"campaign_id": str(campaign_id), "status": "active"}


@router.post("/{campaign_id}/pause")
async def pause_campaign(
    campaign_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Pause an active campaign."""
    result = await db.execute(
        select(Campaign).where(Campaign.id == campaign_id)
    )
    campaign = result.scalar_one_or_none()
    
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    if campaign.status != CampaignStatus.ACTIVE:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot pause campaign with status: {campaign.status}",
        )
    
    campaign.status = CampaignStatus.PAUSED
    await db.flush()
    
    logger.info("campaign_paused", campaign_id=str(campaign_id))
    
    return {"campaign_id": str(campaign_id), "status": "paused"}


@router.get("/{campaign_id}/tasks", response_model=List[TaskResponse])
async def get_campaign_tasks(
    campaign_id: UUID,
    status: Optional[TaskStatus] = None,
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    """Get tasks for a campaign."""
    query = select(CampaignTask).where(
        CampaignTask.campaign_id == campaign_id
    ).order_by(CampaignTask.created_at.desc())
    
    if status:
        query = query.where(CampaignTask.status == status)
    
    query = query.limit(limit)
    
    result = await db.execute(query)
    tasks = result.scalars().all()
    
    return tasks


@router.get("/{campaign_id}/stats")
async def get_campaign_stats(
    campaign_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get statistics for a campaign."""
    result = await db.execute(
        select(Campaign).where(Campaign.id == campaign_id)
    )
    campaign = result.scalar_one_or_none()
    
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    # Get task counts by status
    stats_result = await db.execute(
        select(
            CampaignTask.status,
            func.count(CampaignTask.id),
        )
        .where(CampaignTask.campaign_id == campaign_id)
        .group_by(CampaignTask.status)
    )
    
    stats = {row[0]: row[1] for row in stats_result.all()}
    
    total = sum(stats.values())
    completed = stats.get(TaskStatus.COMPLETED, 0)
    failed = stats.get(TaskStatus.FAILED, 0)
    
    return {
        "campaign_id": str(campaign_id),
        "campaign_name": campaign.name,
        "status": campaign.status,
        "total_tasks": total,
        "completed": completed,
        "failed": failed,
        "pending": stats.get(TaskStatus.PENDING, 0),
        "in_progress": stats.get(TaskStatus.IN_PROGRESS, 0),
        "completion_rate": round(completed / total * 100, 2) if total > 0 else 0,
        "task_breakdown": stats,
    }
