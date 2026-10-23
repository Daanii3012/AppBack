from fastapi import APIRouter, Depends

from app.controllers import messages_controller
from app.core.dependencies import get_current_user
from app.models.message_model import MessageCreate

router = APIRouter(tags=["messages"])

@router.get("/{group_id}/messages")
async def list_messages(group_id: int, current_user=Depends(get_current_user)):
    return await messages_controller.list_messages(group_id, current_user["id"])

@router.post("/{group_id}/messages")
async def send_message(group_id: int, payload: MessageCreate, current_user=Depends(get_current_user)):
    return await messages_controller.send_message(group_id, current_user["id"], payload.content)
