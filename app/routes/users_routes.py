from fastapi import APIRouter, Depends

from app.controllers import users_controller
from app.core.dependencies import get_current_user

router = APIRouter(tags=["users"])

@router.get("/me")
async def me(current_user=Depends(get_current_user)):
    return current_user

@router.get("/{user_id}")
async def get_user(user_id: int):
    user = await users_controller.get_by_id(user_id)
    if not user:
        raise ValueError("Usuario no encontrado")
    return user
