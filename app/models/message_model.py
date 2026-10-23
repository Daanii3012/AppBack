from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class MessageCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)


class MessageOut(BaseModel):
    id: int
    group_id: int
    sender_id: int
    username: str
    content: str
    sent_at: Optional[datetime] = None
