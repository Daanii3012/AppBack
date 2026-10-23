from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ExpenseShare(BaseModel):
    user_id: int
    percentage: float = Field(..., gt=0)


class ExpenseCreate(BaseModel):
    title: str = Field(..., min_length=2, max_length=200)
    description: Optional[str] = None
    amount: float = Field(..., gt=0)
    category: Optional[str] = None
    paid_by_id: int
    shares: list[ExpenseShare] = []


class ExpenseShareOut(BaseModel):
    user_id: int
    percentage: float
    amount_due: float


class ExpenseOut(BaseModel):
    id: int
    group_id: int
    created_by_id: int
    paid_by_id: int
    title: str
    description: Optional[str]
    amount: float
    category: Optional[str]
    created_at: Optional[datetime] = None
    expense_date: Optional[datetime] = None
    shares: list[ExpenseShareOut] = []
