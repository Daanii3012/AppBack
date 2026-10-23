from fastapi import APIRouter, Depends

from app.controllers import expenses_controller
from app.core.dependencies import get_current_user
from app.models.expense_model import ExpenseCreate

router = APIRouter(tags=["expenses"])

@router.get("/{group_id}/expenses")
async def list_expenses(group_id: int, current_user=Depends(get_current_user)):
    return await expenses_controller.list_expenses(group_id, current_user["id"])

@router.post("/{group_id}/expenses")
async def create_expense(group_id: int, expense: ExpenseCreate, current_user=Depends(get_current_user)):
    return await expenses_controller.create_expense(group_id, current_user["id"], expense)
