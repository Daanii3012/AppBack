from fastapi import APIRouter, Depends

from app.controllers import groups_controller
from app.core.dependencies import get_current_user
from app.models.group_model import GroupCreate, InviteCreate, InvitationDecision

router = APIRouter(tags=["groups"])

@router.get("")
async def list_groups(current_user=Depends(get_current_user)):
    return await groups_controller.list_for_user(current_user["id"])

@router.get("/invitations")
async def list_invitations(current_user=Depends(get_current_user)):
    return await groups_controller.list_invitations(current_user["id"])

@router.post("")
async def create_group(group_data: GroupCreate, current_user=Depends(get_current_user)):
    return await groups_controller.create_group(current_user["id"], group_data)

@router.get("/{group_id}")
async def get_group(group_id: int, current_user=Depends(get_current_user)):
    return await groups_controller.get_group(group_id, current_user["id"])

@router.post("/{group_id}/invite")
async def invite_user(group_id: int, payload: InviteCreate, current_user=Depends(get_current_user)):
    return await groups_controller.invite_user(group_id, current_user["id"], payload.email)

@router.patch("/invitations/{invitation_id}")
async def respond_invitation(invitation_id: int, payload: InvitationDecision, current_user=Depends(get_current_user)):
    return await groups_controller.respond_invitation(invitation_id, current_user["id"], payload.status)

@router.get("/{group_id}/balance")
async def group_balance(group_id: int, current_user=Depends(get_current_user)):
    return await groups_controller.balance(group_id, current_user["id"])
