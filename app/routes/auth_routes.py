from fastapi import APIRouter

from app.controllers import users_controller
from app.models.user_model import UserCreate, UserLogin

router = APIRouter(tags=["auth"])

@router.post("/register")
async def register(user: UserCreate):
    return await users_controller.register(user)

@router.post("/login")
async def login(user: UserLogin):
    return await users_controller.login(user)
