from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class GroupCreate(BaseModel):
    title: str = Field(..., min_length=2, max_length=150)
    description: str = Field(..., min_length=2)
    objective: str = Field(..., min_length=2, max_length=255)


class GroupMemberOut(BaseModel):
    id: int
    user_id: int
    username: str
    full_name: str
    role: str
    participation_percentage: float


class GroupOut(BaseModel):
    id: int
    creator_id: int
    title: str
    description: str
    objective: str
    created_at: Optional[datetime] = None


class InviteCreate(BaseModel):
    email: str


class InvitationDecision(BaseModel):
    status: str = Field(..., pattern="^(accepted|rejected|cancelled)$")


class GroupBalanceItem(BaseModel):
    user_id: int
    username: str
    total_owed: float
    total_paid: float
    balance: float


class InviteOut(BaseModel):
    id: int
    group_id: int
    sender_id: int
    recipient_id: int
    recipient_email: str
    status: str
    created_at: Optional[datetime] = None
